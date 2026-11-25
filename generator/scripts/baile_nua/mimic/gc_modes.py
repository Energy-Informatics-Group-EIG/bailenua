"""G-C: the adversarial generators, and the T6 null control (design 5.14).

Design 5.14's independence protocol runs MIMIC's analytics on three
structurally different generators:

    G-A, MIMIC's own ``chooseSignal``: the well-specified baseline.
    G-B, the HRSD willingness model: independent, with interactions, response
    styles, fatigue and the stated-revealed gap.
    G-C, adversarial: latent classes, extreme response styles, position bias,
    non-stationarity. MIMIC passes only if its conclusions track each
    generator's truth. How far it degrades under G-B and G-C is reported as a
    finding, not hidden.

and is explicit that only G-C counts as independent at the level of the
data-generating mechanism, because G-B deliberately shares MIMIC's trait
vocabulary.

The five modes, verbatim from the design, are implemented as
:data:`GC_MODES`. Each one plants a truth and **declares in advance what the
right answer is** - and the right answer is often not "pass". Design 5.14
separates three outcomes:

    pass; **software defect** (wrong result where the method should work);
    **recognised limitation** (correct implementation failing where the
    method can't work, for example parameter recovery under
    non-identifiability). Limitations are reported to the MIMIC team as
    findings, not bugs.

That distinction is the reason this module exists. Under the non-identifiable
mode a correct estimator *must* fail to recover separate coefficients, so
treating that failure as a bug would send the MIMIC team chasing a defect
that is a property of the design matrix. And treating it as a pass would be
worse: it would hide that the quantity is not recoverable. So the expected
class is written down per mode before anything is run, and a mode that comes
out PASS where RECOGNISED_LIMITATION was expected is itself a finding -
because an estimator that recovers non-identifiable parameters is recovering
its own prior.

**K17, which this is all for.** "Circularity: MIMIC is tested on data
generated with its own assumptions, so passing proves little." G-C is the
answer to that, and the answer only works if the mechanisms really are
different - so each mode's docstring says what MIMIC assumes and which part
of it the mode breaks.
"""

from __future__ import annotations

import dataclasses
import math
from typing import Any, Callable

import numpy as np

from baile_nua.rng import SeedTree, Stream

__all__ = [
    "GCMode",
    "GC_MODES",
    "Cohort",
    "generate",
    "incremental_r2",
    "ols",
    "assess",
    "ModeAssessment",
    "gc_report",
    "cluster_validity_gap",
    "T6_NULL_MODE",
    "T6_LINKED_MODE",
    "t6_power",
]

#: The two modes T6 uses: one with a planted causal link, one without.
T6_LINKED_MODE = "linked_causal"
T6_NULL_MODE = "causally_unrelated"


@dataclasses.dataclass
class Cohort:
    """A generated cohort, with the truth that was planted in it."""

    mode: str
    n: int
    #: Observed covariates a fair baseline model is entitled to use.
    demographics: np.ndarray
    opportunity: np.ndarray
    #: The stated Flex Profile score, which is what MIMIC would compute.
    stated: np.ndarray
    #: Revealed flexibility in Baile Nua: the behaviour to be predicted.
    revealed: np.ndarray
    #: True where the respondent answered; False where they are MNAR-missing.
    responded: np.ndarray
    planted: dict[str, Any]
    expected_class: str
    expected_note: str

    @property
    def n_responded(self) -> int:
        return int(self.responded.sum())

    def observed(self) -> "Cohort":
        """The cohort as an analyst would see it: responders only."""
        m = self.responded
        return dataclasses.replace(
            self, n=int(m.sum()), demographics=self.demographics[m],
            opportunity=self.opportunity[m], stated=self.stated[m],
            revealed=self.revealed[m], responded=self.responded[m],
        )


@dataclasses.dataclass(frozen=True)
class GCMode:
    """One adversarial generator mode."""

    mode_id: str
    title: str
    design_phrase: str
    #: What MIMIC assumes, and which part of it this mode breaks.
    breaks: str
    #: PASS | RECOGNISED_LIMITATION | SOFTWARE_DEFECT, declared in advance.
    expected_class: str
    expected_note: str
    build: Callable[..., Cohort]


# --------------------------------------------------------------------------- #
# small linear tools, so no estimator library is required
# --------------------------------------------------------------------------- #

def ols(x: np.ndarray, y: np.ndarray) -> dict[str, Any]:
    """Least squares with an intercept, and the fit statistics that matter."""
    x = np.atleast_2d(np.asarray(x, dtype=float))
    if x.shape[0] != len(y):
        x = x.T
    design = np.column_stack([np.ones(len(y)), x])
    beta, *_ = np.linalg.lstsq(design, np.asarray(y, dtype=float), rcond=None)
    fitted = design @ beta
    resid = np.asarray(y, dtype=float) - fitted
    ss_res = float(resid @ resid)
    centred = np.asarray(y, dtype=float) - float(np.mean(y))
    ss_tot = float(centred @ centred)
    k = design.shape[1]
    n = len(y)
    # The standard errors come from the same decomposition, so a
    # non-identifiable design shows up here as an enormous SE rather than as a
    # confident wrong number - which is the whole point of mode 2.
    try:
        xtx_inv = np.linalg.pinv(design.T @ design)
        sigma2 = ss_res / max(n - k, 1)
        se = np.sqrt(np.maximum(np.diag(xtx_inv) * sigma2, 0.0))
    except np.linalg.LinAlgError:              # pragma: no cover
        se = np.full(k, np.nan)
    return {
        "beta": beta,
        "se": se,
        # The full covariance, because under near-collinearity the interesting
        # quantities are CONTRASTS: the sum of two collinear coefficients is
        # estimated precisely and their difference is not, and neither fact is
        # visible in the diagonal alone.
        "cov": xtx_inv * (ss_res / max(n - k, 1)),
        "r2": 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan"),
        "adj_r2": (
            1.0 - (ss_res / max(n - k, 1)) / (ss_tot / max(n - 1, 1))
            if ss_tot > 0 else float("nan")
        ),
        "ss_res": ss_res,
        "n": n,
        "k": k,
        "condition_number": float(np.linalg.cond(design)),
    }


def incremental_r2(
    *, baseline_x: np.ndarray, extra_x: np.ndarray, y: np.ndarray,
    folds: int = 5, seed: int = 0,
) -> dict[str, Any]:
    """Does ``extra_x`` predict ``y`` beyond ``baseline_x``?

    Cross-validated, because in-sample R² can only rise when a column is
    added: an in-sample test would report predictive value for a column of
    pure noise and the T6 null control would pass by construction. Out of
    sample a useless column makes the fit *worse*, which is what makes the
    null falsifiable.
    """
    y = np.asarray(y, dtype=float)
    n = len(y)
    rng = np.random.default_rng(seed)
    order = rng.permutation(n)
    cuts = np.array_split(order, folds)

    def cv_sse(x: np.ndarray) -> float:
        x = np.atleast_2d(np.asarray(x, dtype=float))
        if x.shape[0] != n:
            x = x.T
        total = 0.0
        for i in range(folds):
            test = cuts[i]
            train = np.concatenate([cuts[j] for j in range(folds) if j != i])
            d_tr = np.column_stack([np.ones(len(train)), x[train]])
            d_te = np.column_stack([np.ones(len(test)), x[test]])
            beta, *_ = np.linalg.lstsq(d_tr, y[train], rcond=None)
            r = y[test] - d_te @ beta
            total += float(r @ r)
        return total

    base = np.atleast_2d(np.asarray(baseline_x, dtype=float))
    if base.shape[0] != n:
        base = base.T
    ext = np.atleast_2d(np.asarray(extra_x, dtype=float))
    if ext.shape[0] != n:
        ext = ext.T

    sse_base = cv_sse(base)
    sse_full = cv_sse(np.column_stack([base, ext]))
    centred = y - float(np.mean(y))
    ss_tot = float(centred @ centred)
    return {
        "cv_r2_baseline": 1.0 - sse_base / ss_tot if ss_tot else float("nan"),
        "cv_r2_full": 1.0 - sse_full / ss_tot if ss_tot else float("nan"),
        "incremental_cv_r2": (sse_base - sse_full) / ss_tot if ss_tot else 0.0,
        "n": n,
        "folds": folds,
        "note": (
            "Cross-validated. In sample, adding any column can only raise R2, "
            "so an in-sample version of this test would find predictive value "
            "in noise and the null control would pass by construction."
        ),
    }


# --------------------------------------------------------------------------- #
# the five modes
# --------------------------------------------------------------------------- #

def _gen(master_seed: int, mode: str) -> np.random.Generator:
    return SeedTree(master_seed).generator(
        Stream.PERSON_TRAITS, entity=f"gc:{mode}", sim_day=0,
    )


def _demographics(g: np.random.Generator, n: int) -> np.ndarray:
    """Age, income quintile and household size, standardised.

    Observed covariates, so a fair baseline model is entitled to them. T6's
    null is "no effect BEYOND demographics and opportunity", which only means
    anything if the baseline actually gets them.
    """
    age = g.normal(0.0, 1.0, n)
    income = g.normal(0.0, 1.0, n)
    size = g.normal(0.0, 1.0, n)
    return np.column_stack([age, income, size])


def _opportunity(g: np.random.Generator, n: int, demo: np.ndarray) -> np.ndarray:
    """Whether the home CAN flex: assets, tenure, heating type.

    Correlated with demographics, as it is in reality - a higher income
    quintile owns more of the assets that make flexibility possible - because
    an orthogonal opportunity term would make the baseline model's job
    artificially easy.
    """
    assets = 0.45 * demo[:, 1] + g.normal(0.0, 1.0, n)
    tenure = 0.30 * demo[:, 1] + g.normal(0.0, 1.0, n)
    return np.column_stack([assets, tenure])


def build_wrong_assumptions(*, n: int = 2000, master_seed: int = 0) -> Cohort:
    """Mode 1: responses from a mechanism MIMIC does not model.

    MIMIC assumes a weighted additive utility over attributes. Here the
    respondent is **lexicographic**: they rank by their single most important
    attribute and ignore the rest unless it ties. A weighted model fitted to
    lexicographic choices recovers coefficients that describe nothing - it
    will find a weight on every attribute when the respondent used one.

    Expected class is RECOGNISED_LIMITATION: the estimator is working, the
    functional form is wrong, and no amount of data fixes that.
    """
    g = _gen(master_seed, "wrong_assumptions")
    demo = _demographics(g, n)
    opp = _opportunity(g, n, demo)
    attrs = g.normal(0.0, 1.0, (n, 3))
    # Each respondent's single decisive attribute.
    decisive = g.integers(0, 3, n)
    threshold = g.normal(0.0, 0.5, n)
    stated = np.array([
        attrs[i, decisive[i]] for i in range(n)
    ])
    # Revealed flexibility follows the SAME lexicographic rule, hard-
    # thresholded, so there is a real link but not one an additive model finds.
    revealed = (stated > threshold).astype(float) * 2.0 + g.normal(0.0, 0.4, n)
    return Cohort(
        mode="wrong_assumptions", n=n, demographics=demo, opportunity=opp,
        stated=stated, revealed=revealed,
        responded=np.ones(n, dtype=bool),
        planted={
            "rule": "lexicographic with a per-respondent threshold",
            "decisive_attribute_shares": [
                float((decisive == k).mean()) for k in range(3)
            ],
            "additive_weights": None,
        },
        expected_class="RECOGNISED_LIMITATION",
        expected_note=(
            "An additive estimator fitted to a lexicographic rule returns "
            "weights for attributes the respondent never traded off. The "
            "estimator is correct; the functional form is wrong."
        ),
    )


def build_non_identifiable(*, n: int = 2000, master_seed: int = 0,
                           rho: float = 0.9995) -> Cohort:
    """Mode 2: correlated latent traits whose separate effects can't be recovered.

    The design's own example of a recognised limitation. Two latents both
    drive the outcome; their SUM is recoverable and their separate
    coefficients are not.

    What a correct estimator must do here is report a standard error large
    enough that the two coefficients cannot be told apart, not a confident
    number. An estimator that returns tight intervals on separately
    unidentifiable coefficients is recovering its own prior, and that would
    be a SOFTWARE_DEFECT dressed as a pass.

    **The correlation had to be raised, and that was a real correction.** The
    first version used r = 0.97 and declared the coefficients
    non-identifiable "at any sample size". That is false, and the assessment
    said so: at r = 0.97 the variance inflation factor is 1/(1 - 0.97^2) =
    16.9, so with n = 2000 the standard errors come back around 0.054 and the
    separate coefficients ARE estimable. Correlation is not the same thing as
    collinearity sufficient to destroy identification. r = 0.9995 gives a
    variance inflation of about 1000, which is non-identifiability in the
    sense the design means.
    """
    g = _gen(master_seed, "non_identifiable")
    demo = _demographics(g, n)
    opp = _opportunity(g, n, demo)
    z = g.normal(0.0, 1.0, n)
    t1 = z
    t2 = rho * z + math.sqrt(max(1.0 - rho ** 2, 1e-12)) * g.normal(0.0, 1.0, n)
    b1, b2 = 0.8, -0.3
    revealed = b1 * t1 + b2 * t2 + 0.25 * opp[:, 0] + g.normal(0.0, 0.6, n)
    stated = 0.5 * (t1 + t2) + g.normal(0.0, 0.3, n)
    return Cohort(
        mode="non_identifiable", n=n, demographics=demo, opportunity=opp,
        stated=stated, revealed=revealed, responded=np.ones(n, dtype=bool),
        planted={
            "rho": rho, "beta_t1": b1, "beta_t2": b2,
            "recoverable_sum": b1 + b2,
            "latents": np.column_stack([t1, t2]),
        },
        expected_class="RECOGNISED_LIMITATION",
        expected_note=(
            f"At r = {rho} the variance inflation is about "
            f"{1.0 / max(1.0 - rho ** 2, 1e-12):.0f}, so the separate "
            f"coefficients are not identified. The sum {b1 + b2:.2f} is "
            f"recoverable; a tight interval on either one alone would be the "
            f"estimator reporting its prior."
        ),
    )


def build_continuous_no_clusters(*, n: int = 2000, master_seed: int = 0) -> Cohort:
    """Mode 3: apparent clusters arising from continuous distributions only.

    A single multivariate normal. Any segmentation will still return k
    centroids - k-means always does - so the question is whether MIMIC's
    validity gate REJECTS them. Expected class is PASS, because rejecting
    clusters that are not there is something the method can do; failing to
    reject them is a software defect, not a limitation.
    """
    g = _gen(master_seed, "continuous_no_clusters")
    demo = _demographics(g, n)
    opp = _opportunity(g, n, demo)
    # One correlated blob, no latent classes at all.
    cov = np.array([[1.0, 0.5, 0.3], [0.5, 1.0, 0.4], [0.3, 0.4, 1.0]])
    latents = g.multivariate_normal(np.zeros(3), cov, n)
    stated = latents.mean(axis=1)
    revealed = 0.6 * stated + 0.3 * opp[:, 0] + g.normal(0.0, 0.7, n)
    return Cohort(
        mode="continuous_no_clusters", n=n, demographics=demo,
        opportunity=opp, stated=stated, revealed=revealed,
        responded=np.ones(n, dtype=bool),
        planted={"k_true": 1, "latents": latents, "covariance": cov.tolist()},
        expected_class="PASS",
        expected_note=(
            "There are no classes. A validity gate that reports k > 1 with "
            "confidence has found structure in a single Gaussian, which is a "
            "defect rather than a limitation."
        ),
    )


def build_causally_unrelated(*, n: int = 2000, master_seed: int = 0) -> Cohort:
    """Mode 4, and the T6 null control: a shared confounder, no causal path.

    Stated willingness and revealed flexibility share a confounder that is
    **observed** - it sits inside demographics and opportunity. So stated
    willingness correlates with revealed behaviour and has no effect on it,
    and design 5.14's null is exactly that: "stated willingness has no effect
    on revealed flexibility beyond demographics and opportunity. MIMIC must
    not report predictive or causal value."

    The confounder has to be observed for the null to be a fair test. If it
    were hidden, stated willingness would legitimately carry information
    about revealed behaviour and an estimator that used it would be right -
    so a null built on an unobserved confounder would fail a correct method
    and call it a defect.
    """
    g = _gen(master_seed, "causally_unrelated")
    demo = _demographics(g, n)
    opp = _opportunity(g, n, demo)
    # The confounder IS the income quintile and the asset index, both observed.
    conf = 0.7 * demo[:, 1] + 0.7 * opp[:, 0]
    stated = 0.9 * conf + g.normal(0.0, 0.8, n)
    # No stated term. Revealed depends on the confounder and on nothing the
    # survey measures beyond it.
    revealed = 0.9 * conf + 0.2 * demo[:, 0] + g.normal(0.0, 0.8, n)
    return Cohort(
        mode="causally_unrelated", n=n, demographics=demo, opportunity=opp,
        stated=stated, revealed=revealed, responded=np.ones(n, dtype=bool),
        planted={
            "causal_effect_of_stated": 0.0,
            "confounder_is_observed": True,
            "confounder_loadings": {"income": 0.7, "assets": 0.7},
        },
        expected_class="PASS",
        expected_note=(
            "The planted causal effect is exactly zero and the confounder is "
            "observed, so a correct method conditioning on demographics and "
            "opportunity must find no incremental predictive value. Finding "
            "some is a defect."
        ),
    )


def build_linked_causal(*, n: int = 2000, master_seed: int = 0,
                        effect: float = 0.45) -> Cohort:
    """T6's positive arm: a genuine causal link, planted.

    Not a G-C mode - it is the control for the control. Without it, "the null
    found nothing" is uninformative: a procedure that finds nothing in every
    cohort would pass the null and be useless. This arm is what shows the
    procedure can find an effect of the size the null is powered against.
    """
    g = _gen(master_seed, "linked_causal")
    demo = _demographics(g, n)
    opp = _opportunity(g, n, demo)
    conf = 0.5 * demo[:, 1] + 0.5 * opp[:, 0]
    # A trait that the survey measures and that genuinely moves behaviour.
    disposition = g.normal(0.0, 1.0, n)
    stated = 0.6 * conf + 0.9 * disposition + g.normal(0.0, 0.5, n)
    revealed = (
        0.9 * conf + effect * disposition + 0.2 * demo[:, 0]
        + g.normal(0.0, 0.8, n)
    )
    return Cohort(
        mode="linked_causal", n=n, demographics=demo, opportunity=opp,
        stated=stated, revealed=revealed, responded=np.ones(n, dtype=bool),
        planted={"causal_effect_of_disposition": effect,
                 "confounder_is_observed": True},
        expected_class="PASS",
        expected_note=(
            "A real effect is planted, so the procedure must FIND incremental "
            "predictive value. This arm is what makes the null arm's negative "
            "result informative rather than vacuous."
        ),
    )


def build_differential_non_response(*, n: int = 3000,
                                    master_seed: int = 0) -> Cohort:
    """Mode 5: missing-not-at-random responses and dropout.

    Response probability depends on the latent disposition itself, so
    responders are not a random subset: the engaged answer and the
    indifferent do not. Any estimate from responders alone is biased for the
    population, and the bias does not shrink with sample size.

    Expected class is RECOGNISED_LIMITATION: selection on an unobserved
    cause is not something an estimator can undo without an assumption it
    cannot test. What MIMIC *can* do is detect the imbalance, which is what
    T5 self-selection is for, so this mode is also a cross-check that the two
    tests do not contradict each other.
    """
    g = _gen(master_seed, "differential_non_response")
    demo = _demographics(g, n)
    opp = _opportunity(g, n, demo)
    disposition = g.normal(0.0, 1.0, n)
    stated = 0.9 * disposition + g.normal(0.0, 0.4, n)
    revealed = 0.5 * disposition + 0.3 * opp[:, 0] + g.normal(0.0, 0.7, n)
    # MNAR: the probability of answering rises with the very disposition the
    # survey is trying to measure.
    p = 1.0 / (1.0 + np.exp(-(0.2 + 1.1 * disposition)))
    responded = g.random(n) < p
    return Cohort(
        mode="differential_non_response", n=n, demographics=demo,
        opportunity=opp, stated=stated, revealed=revealed,
        responded=responded,
        planted={
            "response_depends_on": "the latent disposition (MNAR)",
            "response_logit": {"intercept": 0.2, "slope": 1.1},
            "population_mean_disposition": 0.0,
            "responder_mean_disposition": float(disposition[responded].mean()),
            "response_rate": float(responded.mean()),
        },
        expected_class="RECOGNISED_LIMITATION",
        expected_note=(
            "Selection on an unobserved cause cannot be undone without an "
            "untestable assumption. The responder mean is shifted from the "
            "population mean by construction, and that shift is the finding."
        ),
    )


GC_MODES: dict[str, GCMode] = {
    "wrong_assumptions": GCMode(
        mode_id="wrong_assumptions", title="Wrong assumptions",
        design_phrase=("responses from a mechanism MIMIC doesn't model, such "
                       "as a lexicographic or threshold rule"),
        breaks="MIMIC's weighted additive utility over attributes",
        expected_class="RECOGNISED_LIMITATION",
        expected_note="an additive fit to a lexicographic rule describes nothing",
        build=build_wrong_assumptions,
    ),
    "non_identifiable": GCMode(
        mode_id="non_identifiable", title="Non-identifiable",
        design_phrase=("correlated latent traits whose separate effects can't "
                       "be recovered"),
        breaks="the assumption that trait effects are separately estimable",
        expected_class="RECOGNISED_LIMITATION",
        expected_note="the sum is recoverable; the parts are not",
        build=build_non_identifiable,
    ),
    "continuous_no_clusters": GCMode(
        mode_id="continuous_no_clusters", title="Continuous, no clusters",
        design_phrase=("apparent clusters arising from continuous "
                       "distributions only"),
        breaks="the assumption that a segmentation reflects latent classes",
        expected_class="PASS",
        expected_note="rejecting clusters that are not there is achievable",
        build=build_continuous_no_clusters,
    ),
    "causally_unrelated": GCMode(
        mode_id="causally_unrelated", title="Causally unrelated",
        design_phrase=("survey answers that predict behaviour but don't cause "
                       "it, through a shared confounder"),
        breaks="the inference from predictive association to causal value",
        expected_class="PASS",
        expected_note="with the confounder observed, conditioning must kill it",
        build=build_causally_unrelated,
    ),
    "differential_non_response": GCMode(
        mode_id="differential_non_response", title="Differential non-response",
        design_phrase="missing-not-at-random responses and dropout",
        breaks="the assumption that responders represent the population",
        expected_class="RECOGNISED_LIMITATION",
        expected_note="selection on an unobserved cause cannot be undone",
        build=build_differential_non_response,
    ),
}


def generate(mode: str, *, n: int = 2000, master_seed: int = 0) -> Cohort:
    """Build one cohort from a named mode (G-C, or T6's linked arm)."""
    if mode == T6_LINKED_MODE:
        return build_linked_causal(n=n, master_seed=master_seed)
    if mode not in GC_MODES:
        raise KeyError(
            f"unknown generator mode {mode!r}; G-C modes are "
            f"{sorted(GC_MODES)} and T6's positive arm is {T6_LINKED_MODE!r}"
        )
    return GC_MODES[mode].build(n=n, master_seed=master_seed)


def t6_power(
    *, n: int, effect_cv_r2: float, alpha: float = 0.05
) -> dict[str, Any]:
    """Can T6's null arm detect an effect of the size the linked arm plants?

    A null control that is simply underpowered reports "no effect" for every
    cohort and certifies nothing - the standing rule is that every negative
    control is power-analysed with an expected failure. Here the detectable
    effect is expressed in incremental cross-validated R², because that is
    what the test statistic is.

    The approximation is the usual one for an F test on a single added
    regressor: the non-centrality is ``n * f2`` with
    ``f2 = dR2 / (1 - R2_full)``, and 80% power at alpha needs a
    non-centrality of about 7.85.
    """
    f2 = effect_cv_r2 / max(1.0 - effect_cv_r2, 1e-9)
    ncp = n * f2
    required_ncp = 7.85
    return {
        "n": n,
        "effect_incremental_cv_r2": effect_cv_r2,
        "cohen_f2": f2,
        "noncentrality": ncp,
        "required_noncentrality_for_80pc_power": required_ncp,
        "powered": ncp >= required_ncp,
        "minimum_detectable_incremental_r2": required_ncp / (n + required_ncp),
        "alpha": alpha,
        "note": (
            "If this is not powered, a null result from T6 means nothing: the "
            "test would have missed a real effect of the planted size too."
        ),
    }


# --------------------------------------------------------------------------- #
# assessing each mode on what it is actually about
# --------------------------------------------------------------------------- #

@dataclasses.dataclass
class ModeAssessment:
    """What a mode found, and whether that is the declared right answer."""

    mode_id: str
    expected_class: str
    observed_class: str
    statistics: dict[str, Any]
    detail: str

    @property
    def as_declared(self) -> bool:
        return self.observed_class == self.expected_class

    def as_dict(self) -> dict[str, Any]:
        d = dataclasses.asdict(self)
        d["as_declared"] = self.as_declared
        d["statistics"] = {
            k: (v if not isinstance(v, np.ndarray) else v.tolist())
            for k, v in self.statistics.items()
        }
        return d


def assess(cohort: Cohort, *, seed: int = 0) -> ModeAssessment:
    """Run the check each mode is FOR, not one statistic for all five.

    Each mode breaks a different assumption, so each is assessed on the
    quantity that assumption governs. Running incremental R² on all five would
    report a large number for four of them and say nothing about the thing
    those four were built to probe.
    """
    o = cohort.observed()
    base = np.column_stack([o.demographics, o.opportunity])
    stats: dict[str, Any] = {}

    if cohort.mode == "non_identifiable":
        # The quantity at stake is whether the SEPARATE coefficients come back
        # with honest uncertainty. Fit with both latents in the design.
        lat = cohort.planted["latents"]
        fit = ols(np.column_stack([lat, cohort.opportunity[:, 0]]),
                  cohort.revealed)
        b1, b2 = float(fit["beta"][1]), float(fit["beta"][2])
        se1, se2 = float(fit["se"][1]), float(fit["se"][2])
        truth1 = cohort.planted["beta_t1"]
        truth2 = cohort.planted["beta_t2"]
        sum_err = abs((b1 + b2) - cohort.planted["recoverable_sum"])
        # Honest uncertainty means the interval covers the truth; a tight
        # interval that misses it is the estimator reporting its prior.
        covers1 = abs(b1 - truth1) <= 1.96 * se1
        covers2 = abs(b2 - truth2) <= 1.96 * se2
        stats.update({
            "beta_t1": b1, "beta_t2": b2, "se_t1": se1, "se_t2": se2,
            "planted_t1": truth1, "planted_t2": truth2,
            "sum_recovered": b1 + b2,
            "sum_error": sum_err,
            "condition_number": fit["condition_number"],
            "interval_covers_t1": bool(covers1),
            "interval_covers_t2": bool(covers2),
        })
        # The criterion is DERIVED, and it took two attempts to find the
        # right statistic. "Their separate effects can't be recovered" is a
        # statement about CONTRASTS: under near-perfect collinearity the SUM
        # of the two coefficients is estimated precisely while their
        # DIFFERENCE is not, because the errors are almost perfectly
        # negatively correlated. So the test is exactly that - the sum's
        # interval is tight and covers the planted sum, and the difference's
        # interval covers zero even though the planted difference is 1.1.
        #
        # A fixed standard-error threshold was the first attempt and it hid
        # that r = 0.97 leaves the coefficients fully estimable; half the gap
        # between the coefficients was the second, and it ignores that the two
        # errors are not independent.
        cov = fit["cov"]
        v1, v2, c12 = cov[1, 1], cov[2, 2], cov[1, 2]
        se_sum = float(np.sqrt(max(v1 + v2 + 2 * c12, 0.0)))
        se_diff = float(np.sqrt(max(v1 + v2 - 2 * c12, 0.0)))
        planted_diff = truth1 - truth2
        diff = b1 - b2
        diff_covers_zero = abs(diff) <= 1.96 * se_diff

        # PREDICTION is the identified quantity, not a hand-built sum. That
        # was the third attempt and the first correct one: with rho = 0.9995
        # the combination the data identifies is b1 + rho * b2, not b1 + b2,
        # so comparing the fitted sum against b1 + b2 flagged a 0.033
        # discrepancy that was arithmetic rather than estimation. The textbook
        # statement avoids the trap entirely - under collinearity the fit
        # predicts as well as the true model while inference on the individual
        # coefficients is impossible - and it needs no knowledge of rho.
        oracle = cohort.planted["beta_t1"] * cohort.planted["latents"][:, 0] \
            + cohort.planted["beta_t2"] * cohort.planted["latents"][:, 1]
        pred_fit = incremental_r2(
            baseline_x=cohort.opportunity[:, 0].reshape(-1, 1),
            extra_x=cohort.planted["latents"], y=cohort.revealed, seed=seed,
        )
        pred_oracle = incremental_r2(
            baseline_x=cohort.opportunity[:, 0].reshape(-1, 1),
            extra_x=oracle.reshape(-1, 1), y=cohort.revealed, seed=seed,
        )
        prediction_intact = (
            pred_oracle["cv_r2_full"] - pred_fit["cv_r2_full"]
        ) <= 0.01
        planted_diff = truth1 - truth2
        stats.update({
            "se_sum": se_sum, "se_difference": se_diff,
            "se_ratio_difference_over_sum":
                se_diff / se_sum if se_sum > 0 else float("inf"),
            "planted_difference": planted_diff,
            "recovered_difference": diff,
            "difference_interval_covers_zero": bool(diff_covers_zero),
            "error_correlation": float(c12 / np.sqrt(v1 * v2)),
            "cv_r2_with_both_latents": pred_fit["cv_r2_full"],
            "cv_r2_with_the_true_predictor": pred_oracle["cv_r2_full"],
            "prediction_intact": bool(prediction_intact),
        })
        if prediction_intact and diff_covers_zero:
            obs = "RECOGNISED_LIMITATION"
            detail = (
                f"PREDICTION is unaffected - cross-validated R2 of "
                f"{pred_fit['cv_r2_full']:.4f} against the true predictor's "
                f"{pred_oracle['cv_r2_full']:.4f} - while INFERENCE on the "
                f"separate coefficients is impossible: the difference comes "
                f"back at {diff:+.2f} with a standard error of "
                f"{se_diff:.2f}, an interval covering zero although the "
                f"planted difference is {planted_diff:+.2f}. The two errors "
                f"correlate at {stats['error_correlation']:+.4f}, which is "
                f"exactly what makes the contrast unrecoverable while the "
                f"total is fine. The estimator is correct; the design matrix "
                f"is the limitation."
            )
        elif not diff_covers_zero:
            obs = "SOFTWARE_DEFECT"
            detail = (
                f"the difference {diff:+.2f} is distinguishable from zero "
                f"(standard error {se_diff:.2f}), so the separate effects ARE "
                f"recoverable here and the mode is not generating the "
                f"non-identifiability it claims."
            )
        else:
            obs = "SOFTWARE_DEFECT"
            detail = (
                f"prediction itself degraded: cross-validated R2 "
                f"{pred_fit['cv_r2_full']:.4f} against the true predictor's "
                f"{pred_oracle['cv_r2_full']:.4f}. Collinearity should leave "
                f"prediction intact, so something beyond the design matrix is "
                f"wrong."
            )

    elif cohort.mode == "wrong_assumptions":
        # The additive model will fit something. The question is whether its
        # weights describe the respondents' actual rule. They used ONE
        # attribute each; an additive fit spreads weight over all three.
        inc = incremental_r2(baseline_x=base,
                             extra_x=o.stated.reshape(-1, 1),
                             y=o.revealed, seed=seed)
        fit = ols(o.stated.reshape(-1, 1), o.revealed)
        # A lexicographic rule is a step function: the additive fit's residuals
        # are structured, not noise. Measure it by how much better a threshold
        # fit does out of sample.
        thr = np.median(o.stated)
        step = (o.stated > thr).astype(float).reshape(-1, 1)
        inc_step = incremental_r2(baseline_x=base, extra_x=step,
                                  y=o.revealed, seed=seed)
        stats.update({
            "additive_incremental_cv_r2": inc["incremental_cv_r2"],
            "threshold_incremental_cv_r2": inc_step["incremental_cv_r2"],
            "decisive_attribute_shares":
                cohort.planted["decisive_attribute_shares"],
            "additive_r2": fit["r2"],
        })
        # The planted rule is a threshold, so a threshold feature must explain
        # at least as much as the linear one. If the additive form were
        # adequate, the two would be indistinguishable.
        ratio = inc_step["incremental_cv_r2"] / max(
            inc["incremental_cv_r2"], 1e-9
        )
        stats["threshold_over_additive"] = ratio
        if ratio > 1.0:
            obs = "RECOGNISED_LIMITATION"
            detail = (
                f"a single threshold feature explains "
                f"{inc_step['incremental_cv_r2']:.3f} of variance against the "
                f"additive form's {inc['incremental_cv_r2']:.3f} - a ratio of "
                f"{ratio:.2f}. The additive functional form is the limitation, "
                f"and no sample size fixes it."
            )
        else:
            obs = "PASS"
            detail = (
                "the additive form matched or beat the threshold form, so on "
                "this cohort the misspecification did not bite."
            )

    elif cohort.mode == "continuous_no_clusters":
        # A validity gate, not a clusterer: k-means always returns k
        # centroids, so what is tested is whether the gap statistic refuses
        # them. Compared against the SAME statistic on a cohort that really
        # does have classes would be the full test; here the question is
        # simply whether the single Gaussian is called single.
        lat = cohort.planted["latents"]
        gate = cluster_validity_gap(lat, ks=(2, 3, 4), n_reference=12,
                                    seed=seed)
        stats.update({
            "k_true": cohort.planted["k_true"],
            "best_k": gate["best_k"],
            "observed_silhouette": gate["observed"],
            "reference_mean": gate["reference_mean"],
            "reference_sd": gate["reference_sd"],
            "gap_z": gate["gap_z"],
            "reject_above_z": _GAP_REJECT_Z,
            "scores": gate["scores"],
        })
        if gate["gap_z"] < _GAP_REJECT_Z:
            obs = "PASS"
            detail = (
                f"the best silhouette over k = 2 to 4 is "
                f"{gate['observed']:.3f}, and a single Gaussian with the same "
                f"covariance scores {gate['reference_mean']:.3f} +/- "
                f"{gate['reference_sd']:.3f} - a gap of "
                f"{gate['gap_z']:+.2f} SD. Indistinguishable from no "
                f"structure, which is the planted truth."
            )
        else:
            obs = "SOFTWARE_DEFECT"
            detail = (
                f"a silhouette of {gate['observed']:.3f} at k = "
                f"{gate['best_k']} stands {gate['gap_z']:+.2f} SD above the "
                f"no-structure reference, on data with no latent classes."
            )

    elif cohort.mode in ("causally_unrelated", "linked_causal"):
        inc = incremental_r2(baseline_x=base,
                             extra_x=o.stated.reshape(-1, 1),
                             y=o.revealed, seed=seed)
        power = t6_power(n=o.n, effect_cv_r2=max(inc["incremental_cv_r2"],
                                                 _T6_REFERENCE_EFFECT))
        mdi = power["minimum_detectable_incremental_r2"]
        stats.update({**inc, "minimum_detectable_incremental_r2": mdi,
                      "powered": power["powered"]})
        planted_zero = cohort.planted.get("causal_effect_of_stated") == 0.0
        found = inc["incremental_cv_r2"] > mdi
        if planted_zero and not found:
            obs = "PASS"
            detail = (
                f"incremental cross-validated R2 is "
                f"{inc['incremental_cv_r2']:+.5f}, below the minimum "
                f"detectable {mdi:.4f} at n = {o.n}: no predictive value "
                f"beyond demographics and opportunity, which is the planted "
                f"truth. MIMIC must report none."
            )
        elif planted_zero and found:
            obs = "SOFTWARE_DEFECT"
            detail = (
                f"incremental R2 {inc['incremental_cv_r2']:.5f} exceeds the "
                f"detectable floor on data with a planted effect of exactly "
                f"zero and an OBSERVED confounder: predictive value was "
                f"reported where there is none."
            )
        elif not planted_zero and found:
            obs = "PASS"
            detail = (
                f"the planted effect was found: incremental R2 "
                f"{inc['incremental_cv_r2']:.4f} against a detectable floor "
                f"of {mdi:.4f}."
            )
        else:
            obs = "SOFTWARE_DEFECT"
            detail = (
                f"a real effect was planted and incremental R2 came back at "
                f"{inc['incremental_cv_r2']:.5f}, below the detectable floor: "
                f"the procedure missed it."
            )

    else:   # differential_non_response
        pop = cohort.stated
        resp = cohort.stated[cohort.responded]
        shift = float(resp.mean() - pop.mean())
        pooled = float(np.sqrt(
            (pop.var(ddof=1) + resp.var(ddof=1)) / 2.0
        ))
        d = shift / pooled if pooled else float("nan")
        fit_all = ols(np.column_stack([cohort.demographics,
                                       cohort.opportunity]), cohort.revealed)
        fit_resp = ols(base, o.revealed)
        stats.update({
            "response_rate": cohort.planted["response_rate"],
            "stated_mean_population": float(pop.mean()),
            "stated_mean_responders": float(resp.mean()),
            "selection_shift": shift,
            "cohens_d": d,
            "r2_population": fit_all["r2"],
            "r2_responders": fit_resp["r2"],
        })
        if abs(d) > 0.2:
            obs = "RECOGNISED_LIMITATION"
            detail = (
                f"responders' mean stated willingness is {shift:+.3f} from "
                f"the population's, a standardised shift of {d:+.2f} at a "
                f"{cohort.planted['response_rate']:.0%} response rate. "
                f"Selection on an unobserved cause cannot be undone without "
                f"an untestable assumption; the shift is the finding."
            )
        else:
            obs = "SOFTWARE_DEFECT"
            detail = (
                f"the MNAR mechanism produced a standardised shift of only "
                f"{d:+.2f}, so the mode is not generating the selection it "
                f"claims to and would certify a method against nothing."
            )

    return ModeAssessment(
        mode_id=cohort.mode, expected_class=cohort.expected_class,
        observed_class=obs, statistics=stats, detail=detail,
    )


#: How far above the no-structure reference a silhouette must stand before
#: clusters are accepted. A z-score against a reference distribution the data
#: itself generates, so nothing here is a declared silhouette cut-off.
#:
#: The first version DID declare one - 0.25 - and the data refused it:
#: k-means on a single correlated Gaussian scores about 0.31, because
#: splitting any blob in two produces a respectable silhouette. A raw
#: silhouette is not calibrated against a null, so comparing one to a
#: constant tests nothing. The gap approach compares it against the same
#: statistic computed on Gaussian data with the same covariance, which is
#: the standard construction and is derived rather than chosen.
_GAP_REJECT_Z = 3.0

#: The effect size T6's power calculation is referenced against when the
#: observed increment is smaller - so a null result is compared to the
#: smallest effect the linked arm is built to plant, not to zero.
_T6_REFERENCE_EFFECT = 0.02


def cluster_validity_gap(
    x: np.ndarray, *, ks: tuple[int, ...] = (2, 3, 4), n_reference: int = 12,
    seed: int = 0,
) -> dict[str, Any]:
    """Is the best silhouette larger than a structureless reference gives?

    The reference is drawn from a single Gaussian with the data's own mean and
    covariance, so it has no clusters by construction. Whatever score the
    clusterer manufactures out of one blob, the reference manufactures too,
    and only an excess over that counts as structure.
    """
    x = np.asarray(x, dtype=float)
    obs = _best_silhouette(x, ks=ks, seed=seed)
    mu = x.mean(axis=0)
    cov = np.cov(x, rowvar=False)
    rng = np.random.default_rng(seed + 991)
    ref = []
    for b in range(n_reference):
        sample = rng.multivariate_normal(mu, cov, len(x))
        ref.append(_best_silhouette(sample, ks=ks, seed=seed + b + 1)
                   ["best_score"])
    ref_arr = np.array(ref, dtype=float)
    m, sd = float(ref_arr.mean()), float(ref_arr.std(ddof=1))
    return {
        "observed": obs["best_score"],
        "best_k": obs["best_k"],
        "scores": obs["scores"],
        "reference_mean": m,
        "reference_sd": sd,
        "n_reference": n_reference,
        "gap_z": (obs["best_score"] - m) / sd if sd > 0 else 0.0,
        "note": (
            "The reference has the data's covariance and no clusters, so it "
            "absorbs the silhouette that k-means manufactures from any blob. "
            "Only an excess over it is structure."
        ),
    }


def _best_silhouette(
    x: np.ndarray, *, ks: tuple[int, ...] = (2, 3, 4), seed: int = 0
) -> dict[str, Any]:
    """Best mean silhouette over k, by k-means. No sklearn dependency.

    A compact Lloyd's algorithm, because the point is the VALIDITY GATE and
    not the clusterer: whatever finds the centroids, a single Gaussian must
    not score well.
    """
    x = np.asarray(x, dtype=float)
    rng = np.random.default_rng(seed)
    scores: dict[int, float] = {}
    for k in ks:
        centres = x[rng.choice(len(x), size=k, replace=False)]
        labels = np.zeros(len(x), dtype=int)
        for _ in range(25):
            d = ((x[:, None, :] - centres[None, :, :]) ** 2).sum(axis=2)
            new = d.argmin(axis=1)
            if np.array_equal(new, labels):
                break
            labels = new
            for j in range(k):
                if (labels == j).any():
                    centres[j] = x[labels == j].mean(axis=0)
        # Mean silhouette on a subsample: the full pairwise matrix is O(n^2)
        # and the statistic is stable well before the whole cohort.
        idx = rng.choice(len(x), size=min(len(x), 600), replace=False)
        xs, ls = x[idx], labels[idx]
        dist = np.sqrt(((xs[:, None, :] - xs[None, :, :]) ** 2).sum(axis=2))
        sil = []
        for i in range(len(xs)):
            same = ls == ls[i]
            same[i] = False
            if not same.any():
                continue
            a = dist[i, same].mean()
            others = [dist[i, ls == j].mean() for j in set(ls) if j != ls[i]]
            if not others:
                continue
            b = min(others)
            sil.append((b - a) / max(a, b))
        scores[k] = float(np.mean(sil)) if sil else float("nan")
    best_k = max(scores, key=lambda kk: scores[kk])
    return {"scores": scores, "best_k": best_k, "best_score": scores[best_k]}


def gc_report(*, n: int = 2000, master_seed: int = 0) -> dict[str, Any]:
    """Run all five G-C modes plus T6's linked arm, and classify each."""
    rows = []
    for mode in list(GC_MODES) + [T6_LINKED_MODE]:
        c = generate(mode, n=n, master_seed=master_seed)
        rows.append(assess(c).as_dict())
    return {
        "modes": rows,
        "n_modes": len(rows),
        "all_as_declared": all(r["as_declared"] for r in rows),
        "not_as_declared": [
            r["mode_id"] for r in rows if not r["as_declared"]
        ],
        "claim": (
            "(a) machinery verification only; not behavioural validity "
            "(design 5.14). G-C answers K17: MIMIC is otherwise tested on "
            "data generated with its own assumptions."
        ),
    }
