"""G-C generator modes and the T6 null control (design 5.14, K17).

K17 is the risk this whole module answers: "Circularity: MIMIC is tested on
data generated with its own assumptions, so passing proves little." G-C is the
answer, and the answer only works if the mechanisms really are different - so
each mode declares, in advance, which assumption it breaks and what the right
answer is. The right answer is often not "pass": design 5.14 separates a
**software defect** (wrong result where the method should work) from a
**recognised limitation** (correct implementation failing where the method
can't work), and a mode that comes out PASS where a limitation was expected is
itself a finding, because an estimator that recovers non-identifiable
parameters is recovering its own prior.

Every acceptance criterion in here is derived from the data rather than
declared, and three of them took more than one attempt:

* The non-identifiable mode first used r = 0.97 and claimed the coefficients
  were unrecoverable "at any sample size". The assessment said otherwise, and
  it was right: at r = 0.97 the variance inflation is only ~17, so with
  n = 2000 the standard errors are near 0.054 and the coefficients are
  perfectly estimable. Correlation is not collinearity sufficient to destroy
  identification.
* The criterion for that mode then went through two more wrong statistics - a
  fixed standard-error threshold, then half the gap between the coefficients -
  before arriving at the textbook one: under collinearity PREDICTION is
  identified and inference on individual coefficients is not.
* The cluster mode first compared a silhouette against a declared 0.25. The
  data refused it: k-means on a single correlated Gaussian scores about 0.31,
  because splitting any blob in two produces a respectable silhouette. A raw
  silhouette is not calibrated against a null, so it is now compared against
  the same statistic computed on Gaussian data with the data's own
  covariance.
"""

from __future__ import annotations

import numpy as np
import pytest

import baile_nua.sources_registry  # noqa: F401
from baile_nua.mimic import gc_modes as G
from baile_nua.mimic import tests as T

SEED = 11
N = 2000


# --------------------------------------------------------------------------- #
# the modes are what the design says they are
# --------------------------------------------------------------------------- #

def test_all_five_design_5_14_gc_modes_exist():
    """The design lists five. All five, no extras, no substitutes."""
    assert set(G.GC_MODES) == {
        "wrong_assumptions", "non_identifiable", "continuous_no_clusters",
        "causally_unrelated", "differential_non_response",
    }
    for mode in G.GC_MODES.values():
        assert mode.design_phrase, mode.mode_id
        assert mode.breaks, mode.mode_id
        assert mode.expected_class in (
            "PASS", "RECOGNISED_LIMITATION", "SOFTWARE_DEFECT"
        ), mode.mode_id


def test_every_mode_declares_its_expected_class_before_it_is_run():
    """A verdict chosen after seeing the result is not a verdict."""
    for mode_id, mode in G.GC_MODES.items():
        cohort = G.generate(mode_id, n=200, master_seed=SEED)
        # The cohort carries the SAME declared expectation as the mode table,
        # so the two cannot drift apart and be reconciled after the fact.
        assert cohort.expected_class == mode.expected_class, mode_id
        assert cohort.expected_note


def test_every_mode_comes_out_as_declared():
    """The acceptance criterion, over all five modes plus T6's linked arm."""
    rep = G.gc_report(n=N, master_seed=SEED)
    assert rep["all_as_declared"], rep["not_as_declared"]
    assert rep["n_modes"] == 6
    assert "machinery verification only" in rep["claim"]
    assert "K17" in rep["claim"]


def test_the_outcome_classes_actually_differ_across_modes():
    """If every mode returned the same class, the taxonomy would be decorative."""
    classes = {m.expected_class for m in G.GC_MODES.values()}
    assert classes == {"PASS", "RECOGNISED_LIMITATION"}, classes
    rep = G.gc_report(n=N, master_seed=SEED)
    observed = {r["observed_class"] for r in rep["modes"]}
    assert len(observed) >= 2, observed


# --------------------------------------------------------------------------- #
# mode 2: non-identifiability, and the three corrections it took
# --------------------------------------------------------------------------- #

def test_the_non_identifiable_mode_is_actually_non_identifying():
    """Prediction intact, inference impossible - the textbook signature."""
    c = G.generate("non_identifiable", n=N, master_seed=SEED)
    a = G.assess(c, seed=1)
    st = a.statistics
    assert a.observed_class == "RECOGNISED_LIMITATION", a.detail
    # Near-perfect negative error correlation is the mechanism.
    assert st["error_correlation"] < -0.99, st["error_correlation"]
    # The contrast's standard error dwarfs the sum's.
    assert st["se_ratio_difference_over_sum"] > 10.0, st
    assert st["difference_interval_covers_zero"]
    assert st["prediction_intact"]
    # And the planted difference is substantial, so covering zero is a real
    # failure of identification rather than a small true difference.
    assert abs(st["planted_difference"]) > 1.0


def test_at_r_0_97_the_coefficients_are_recoverable_and_the_mode_says_so():
    """The correction itself, as a test.

    This is the value the first version used while claiming the coefficients
    were unrecoverable at any sample size. They are recoverable, and the
    assessment has to report that the mode is not adversarial rather than
    passing it.
    """
    c = G.build_non_identifiable(n=N, master_seed=SEED, rho=0.97)
    a = G.assess(c, seed=1)
    assert a.observed_class == "SOFTWARE_DEFECT", a.detail
    assert "recoverable" in a.detail
    assert max(a.statistics["se_t1"], a.statistics["se_t2"]) < 0.2, (
        "at r = 0.97 with n = 2000 the standard errors should be near 0.05; "
        "if they are not, the arithmetic behind the correction is wrong"
    )


def test_variance_inflation_is_what_separates_the_two_correlations():
    """The quantity that actually changed, stated arithmetically."""
    for rho, expected_vif in ((0.97, 17.0), (0.9995, 1000.0)):
        vif = 1.0 / (1.0 - rho ** 2)
        assert vif == pytest.approx(expected_vif, rel=0.05), (rho, vif)


# --------------------------------------------------------------------------- #
# mode 3: the cluster gate, and why a declared silhouette cut-off failed
# --------------------------------------------------------------------------- #

def test_a_single_gaussian_scores_a_respectable_silhouette():
    """The measurement that refused the first version's 0.25 threshold.

    k-means on one correlated Gaussian returns about 0.31, because splitting
    any blob in two produces a decent silhouette. Comparing that against a
    constant tests nothing, which is why the gate uses a reference
    distribution.
    """
    rng = np.random.default_rng(7)
    cov = np.array([[1.0, 0.5, 0.3], [0.5, 1.0, 0.4], [0.3, 0.4, 1.0]])
    blob = rng.multivariate_normal(np.zeros(3), cov, 2000)
    best = G._best_silhouette(blob, ks=(2, 3, 4), seed=1)
    assert 0.25 < best["best_score"] < 0.45, (
        f"a single Gaussian scored {best['best_score']:.3f}; the premise that "
        f"a declared 0.25 cut-off would reject it is what failed"
    )


def test_the_gap_reference_absorbs_that_and_rejects_the_blob():
    rng = np.random.default_rng(7)
    cov = np.array([[1.0, 0.5, 0.3], [0.5, 1.0, 0.4], [0.3, 0.4, 1.0]])
    blob = rng.multivariate_normal(np.zeros(3), cov, 2000)
    gate = G.cluster_validity_gap(blob, ks=(2, 3, 4), n_reference=10, seed=1)
    assert gate["gap_z"] < G._GAP_REJECT_Z, gate
    # The reference scores about what the data does, which is the point.
    assert gate["reference_mean"] == pytest.approx(gate["observed"], abs=0.08)


def test_the_gate_still_finds_real_clusters():
    """Sensitivity. A gate that always rejects would pass mode 3 for ever."""
    rng = np.random.default_rng(99)
    centres = np.array([[-4.0, -4.0, 0.0], [4.0, -4.0, 0.0], [0.0, 4.0, 0.0]])
    real = np.vstack([
        rng.multivariate_normal(c, np.eye(3) * 0.6, 500) for c in centres
    ])
    gate = G.cluster_validity_gap(real, ks=(2, 3, 4), n_reference=10, seed=1)
    assert gate["gap_z"] > G._GAP_REJECT_Z * 3, gate
    assert gate["best_k"] == 3, gate["scores"]


# --------------------------------------------------------------------------- #
# T6 and its null control
# --------------------------------------------------------------------------- #

def test_t6_finds_a_planted_link():
    o = T.t6_linked_panel_predictive_validity(n=N, master_seed=SEED)
    assert o.outcome == "PASS", o.detail
    assert o.observed["incremental_cv_r2"] > \
        o.observed["minimum_detectable_incremental_r2"]
    assert o.observed["powered"]
    assert o.planted_truth["causal_effect"] > 0.0


def test_the_t6_null_control_reports_no_predictive_value():
    """Design 5.14: MIMIC must not report predictive or causal value."""
    o = T.t6_null_causal_link_control(n=N, master_seed=SEED)
    assert o.outcome == "PASS", o.detail
    assert o.planted_truth["causal_effect_of_stated"] == 0.0
    assert o.observed["incremental_cv_r2"] <= \
        o.observed["minimum_detectable_incremental_r2"]
    # Out of sample a useless regressor makes the fit slightly WORSE, which is
    # what makes the null falsifiable rather than true by construction.
    assert o.observed["incremental_cv_r2"] < 0.01


def test_the_null_control_is_powered_or_its_negative_result_means_nothing():
    """The standing rule: every negative control is power-analysed."""
    o = T.t6_null_causal_link_control(n=N, master_seed=SEED)
    assert o.observed["powered"], o.observed
    linked = T.t6_linked_panel_predictive_validity(n=N, master_seed=SEED)
    mdi = o.observed["minimum_detectable_incremental_r2"]
    assert linked.observed["incremental_cv_r2"] > 10.0 * mdi, (
        "the linked arm's effect is not comfortably above the null arm's "
        "detection floor, so a clean null result would be uninformative"
    )


def test_the_null_s_confounder_is_observed_and_that_matters():
    """A hidden confounder would make the null a trap for a correct method."""
    c = G.generate(G.T6_NULL_MODE, n=N, master_seed=SEED)
    assert c.planted["confounder_is_observed"] is True
    # Stated willingness DOES correlate with revealed behaviour - that is the
    # whole difficulty - and the correlation has to survive into the data or
    # the null would be trivially passed.
    r = float(np.corrcoef(c.stated, c.revealed)[0, 1])
    assert r > 0.4, (
        f"stated and revealed correlate at only {r:.2f}; the null is supposed "
        f"to be a cohort where the association is real and the causal effect "
        f"is zero, not one where there is no association to be fooled by"
    )


def test_an_in_sample_test_would_have_passed_the_null_by_construction():
    """Why the statistic is cross-validated, demonstrated rather than claimed."""
    c = G.generate(G.T6_NULL_MODE, n=N, master_seed=SEED).observed()
    base = np.column_stack([c.demographics, c.opportunity])
    in_base = G.ols(base, c.revealed)
    in_full = G.ols(np.column_stack([base, c.stated.reshape(-1, 1)]),
                    c.revealed)
    # In sample, adding the column always helps - even here, where it has no
    # causal effect at all.
    assert in_full["r2"] >= in_base["r2"]
    cv = G.incremental_r2(baseline_x=base, extra_x=c.stated.reshape(-1, 1),
                          y=c.revealed, seed=3)
    assert cv["incremental_cv_r2"] < 1e-3, cv
    assert (in_full["r2"] - in_base["r2"]) > cv["incremental_cv_r2"], (
        "the in-sample gain is not larger than the cross-validated one, so "
        "this cohort does not demonstrate the problem the CV design avoids"
    )


def test_t6_states_that_it_is_internal_consistency_only():
    """Design 5.14 item 4, which a reader of the result has to see."""
    for o in (T.t6_linked_panel_predictive_validity(n=400, master_seed=SEED),
              T.t6_null_causal_link_control(n=400, master_seed=SEED)):
        assert "machinery verification only" in o.claim
        assert o.e1_required is False
    linked = T.t6_linked_panel_predictive_validity(n=400, master_seed=SEED)
    assert "not that the link exists in people" in linked.claim.lower() or \
        "NOT that the link exists in people" in linked.claim


# --------------------------------------------------------------------------- #
# mode 5 and mode 1
# --------------------------------------------------------------------------- #

def test_differential_non_response_really_shifts_the_responders():
    c = G.generate("differential_non_response", n=3000, master_seed=SEED)
    assert c.n_responded < c.n
    a = G.assess(c, seed=1)
    assert a.observed_class == "RECOGNISED_LIMITATION", a.detail
    assert abs(a.statistics["cohens_d"]) > 0.2
    # The observed view must drop the non-responders, as an analyst's would.
    o = c.observed()
    assert o.n == c.n_responded
    assert len(o.revealed) == o.n


def test_the_lexicographic_mode_is_not_well_described_by_an_additive_fit():
    c = G.generate("wrong_assumptions", n=N, master_seed=SEED)
    a = G.assess(c, seed=1)
    assert a.observed_class == "RECOGNISED_LIMITATION", a.detail
    assert a.statistics["threshold_over_additive"] > 1.0
    # Respondents really did each use one attribute.
    shares = c.planted["decisive_attribute_shares"]
    assert abs(sum(shares) - 1.0) < 1e-9
    assert all(0.2 < s < 0.45 for s in shares), shares


# --------------------------------------------------------------------------- #
# the tools
# --------------------------------------------------------------------------- #

def test_incremental_r2_is_negative_for_a_pure_noise_column():
    """The property the whole null test rests on."""
    rng = np.random.default_rng(5)
    n = 1500
    x = rng.normal(0, 1, (n, 3))
    y = x @ np.array([1.0, -0.5, 0.25]) + rng.normal(0, 1, n)
    noise = rng.normal(0, 1, (n, 1))
    out = G.incremental_r2(baseline_x=x, extra_x=noise, y=y, seed=1)
    assert out["incremental_cv_r2"] < 0.002, out
    # Whereas a column that genuinely matters shows up.
    real = (y * 0.5 + rng.normal(0, 0.5, n)).reshape(-1, 1)
    out2 = G.incremental_r2(baseline_x=x, extra_x=real, y=y, seed=1)
    assert out2["incremental_cv_r2"] > 0.05, out2


def test_t6_power_refuses_to_call_an_underpowered_null_informative():
    small = G.t6_power(n=30, effect_cv_r2=0.002)
    assert not small["powered"], small
    big = G.t6_power(n=2000, effect_cv_r2=0.09)
    assert big["powered"], big
    assert big["minimum_detectable_incremental_r2"] < 0.01


def test_the_modes_are_reproducible():
    a = G.gc_report(n=600, master_seed=SEED)
    b = G.gc_report(n=600, master_seed=SEED)
    assert [r["observed_class"] for r in a["modes"]] == \
        [r["observed_class"] for r in b["modes"]]
    c = G.gc_report(n=600, master_seed=SEED + 1)
    assert [r["mode_id"] for r in a["modes"]] == [r["mode_id"] for r in c["modes"]]
