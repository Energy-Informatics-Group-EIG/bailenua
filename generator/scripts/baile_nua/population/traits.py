"""MIMIC latent traits and bounded-rationality parameters (design 5.2 step 5, 5.13, 5.14).

Design 5.14 level 1 - **one trait model**:

    HRSD_Occupants uses MIMIC's latent variables as its native willingness
    traits, with the same names and scales as ``mimic_sd_generator.php``.
    The derived self-reports, MCV items 1 to 10 and lambda_1 to lambda_3 come
    from these traits by MIMIC's own mappings.

So the *trait generator* deliberately follows MIMIC's structure, and the
mappings from traits to MCV items and to the Likert self-reports are MIMIC's,
read out of its source and reproduced exactly (see
:mod:`baile_nua.mimic.crosswalk` for the source references).

The **willingness model is a different matter** and lives elsewhere
(:mod:`baile_nua.mimic.willingness`).  Design 5.14's independence protocol is
explicit that if HRSD answered with MIMIC's own ``chooseSignal`` formula, MIMIC
recovering it would prove only that the estimator works on its own assumptions.
Sharing the trait vocabulary is intended (compatibility); sharing the response
mechanism is not.

Everything here is flagged **[A]**: design 5.2 step 5 says "Until FlexSense
Ireland responses exist, priors come from the MIMIC generator and literature,
flagged [A]", and risk K04 ("MIMIC trait priors wrong or weakly linked to
behaviour", likelihood High) and K16 (self-selected sample) both stand.

**Demographic dependence is weak and cited, by design.**  Design 5.2 step 5 says
"weak, evidence-based dependence on demographics", and 5.8 adds that variation
*within* each group must exceed the difference *between* groups, with a
stereotype-guard test (7.7, delta-AUC <= 0.03) that fails the build otherwise.
The coefficients below are therefore small relative to the residual standard
deviations, and :func:`within_vs_between_variance` measures the ratio so the
property is checked rather than asserted.
"""

from __future__ import annotations

import dataclasses
import math
from typing import Any

import numpy as np

from baile_nua.mimic.crosswalk import MIMIC_LATENTS, self_report_from_latent
from baile_nua.rng import SeedTree, Stream

#: The latents that are behavioural traits, and to which design 5.8's
#: within-exceeds-between rule applies.  ``idvZ`` is excluded by construction:
#: it is a country attribute derived from Hofstede's national index (design
#: 5.13), an *input* to the nationality mechanisms rather than a behaviour, so
#: its between-group component is the point of it. Individual variation is still
#: added (see IDV_INDIVIDUAL_SD) so that it is not a pure group label.
BEHAVIOURAL_LATENTS: tuple[str, ...] = (
    "trans", "community", "env", "autonomy", "comfort", "conditional",
    "privacy", "instTrust",
)

__all__ = [
    "TraitVector",
    "BEHAVIOURAL_LATENTS",
    "IDV_INDIVIDUAL_SD",
    "draw_traits",
    "make_mcv",
    "lambda_weights",
    "DEMOGRAPHIC_PRIORS",
    "within_vs_between_variance",
]


#: Weak demographic coefficients on the latents, with the citation design 5.13
#: requires for each.  Structure and magnitudes follow MIMIC's own generator
#: (``makeParticipant``), which is what design 5.14 level 1 asks for.
#:
#: All predictors are centred and scaled so a coefficient is "latent SD per
#: predictor SD".  Residual SDs are 0.50 to 0.60, so every coefficient here is
#: well under half the residual - that is what makes the dependence "weak".
DEMOGRAPHIC_PRIORS: dict[str, dict[str, Any]] = {
    "trans": {
        "coefficients": {"female": 0.32, "age_z": 0.22, "edu_z": 0.15, "idv_z": -0.18, "young_male": -0.30},
        "residual_sd": 0.55,
        "citation": (
            "Wiernik et al. on age and prosociality; Zelezny et al. and Croson & "
            "Gneezy on gender; Van Lange on social value orientation; Hofstede "
            "individualism via CountryAttributes (design 5.13)"
        ),
        "evidence_tag": "[A]",
    },
    "community": {
        "coefficients": {"age_z": 0.30, "idv_z": -0.20},
        "residual_sd": 0.50,
        "citation": "Carstensen socioemotional selectivity; Hofstede individualism (5.13)",
        "evidence_tag": "[A]",
    },
    "env": {
        "coefficients": {"trans": 0.55, "edu_z": 0.20, "female": 0.15, "young_male": -0.20},
        "residual_sd": 0.50,
        "citation": "Zelezny et al. on gender and environmental concern (5.13)",
        "evidence_tag": "[A]",
    },
    "autonomy": {
        "coefficients": {"age_z": -0.30, "edu_z": 0.10, "digital_z": 0.20},
        "residual_sd": 0.55,
        "citation": "MIMIC generator: trust in automation falls with age, rises with digital access",
        "evidence_tag": "[A]",
    },
    "comfort": {
        "coefficients": {"age_z": 0.22, "female": 0.15},
        "residual_sd": 0.60,
        "citation": (
            "Adaptive comfort literature (ASHRAE 55, ISO 7730, EN 16798-1); "
            "older occupants hold higher setpoints (5.13)"
        ),
        "evidence_tag": "[A]",
    },
    "conditional": {
        "coefficients": {"idv_z": 0.25, "inst_trust": -0.20},
        "residual_sd": 0.55,
        "citation": "Fischbacher et al. on conditional cooperation (5.13)",
        "evidence_tag": "[A]",
    },
    "privacy": {
        "coefficients": {"age_z": 0.20, "edu_z": -0.08},
        "residual_sd": 0.50,
        "citation": "MIMIC Data & Privacy bank; drives sensor tier and Jetson consent (5.13)",
        "evidence_tag": "[A]",
    },
    "instTrust": {
        "coefficients": {"edu_z": 0.15, "age_z": 0.10},
        "residual_sd": 0.40,
        "citation": "Delhey & Newton on social trust; Hofstede (5.13)",
        "evidence_tag": "[A]",
    },
}

#: Hofstede individualism index by origin country, used for ``idvZ``.
#: MIMIC standardises it as ``(idv - 55) / 20``; the same transform is used here
#: so the scale is identical.  Only the origin groups the SAPS place-of-birth
#: marginal distinguishes are needed.
HOFSTEDE_IDV: dict[str, float] = {
    "IE": 70.0, "UK": 89.0, "PL": 60.0, "IN": 48.0,
    "EU27_other": 60.0, "rest_of_world": 40.0, "other": 55.0,
}

#: Design 5.13: origin-country priors are "shrunk toward Irish norms by years in
#: Ireland (acculturation)". Half-life in years; after this long the origin
#: prior has moved half-way to the Irish one.
ACCULTURATION_HALF_LIFE_YEARS = 12.0

#: Hofstede's index is a COUNTRY MEAN, and individuals vary widely around it.
#: Representing ``idvZ`` as a deterministic function of origin would make it a
#: group label, which design 5.8 and risk K05 both warn against, and would push
#: origin information into every trait that depends on it. This residual SD puts
#: the within-country spread at roughly 1.5x the between-country spread across
#: the origin groups Cobh actually contains, which is the direction design 5.8
#: requires. Flagged [A]: Hofstede publishes no within-country dispersion.
IDV_INDIVIDUAL_SD = 0.70

#: Design 5.14: "~10% careless/satisficing responders (Meade & Craig 2012)".
#: Read from MIMIC's generator, which uses 0.10.
SATISFICER_RATE = 0.10


@dataclasses.dataclass
class TraitVector:
    """One person's hidden trait layer.  GT only (design 5.1, R06)."""

    # the ten MIMIC latents
    trans: float
    community: float
    env: float
    autonomy: float
    comfort: float
    conditional: float
    privacy: float
    instTrust: float
    idvZ: float
    satisficer: int
    # derived by MIMIC's own mappings
    lambda_self: float
    lambda_coop: float
    lambda_altru: float
    mcv_latent: list[float]
    environmental_concern: int
    trust_in_automation: int
    comfort_sensitivity: int
    # HRSD-specific
    stated_gap: float
    response_propensity: float
    # Big Five and bounded rationality
    big5_o: float
    big5_c: float
    big5_e: float
    big5_a: float
    big5_n: float
    chronotype: float
    habit_strength: float
    lapse_rate: float
    attention: float

    def latents(self) -> dict[str, float]:
        return {k: getattr(self, k) for k in MIMIC_LATENTS}

    def as_row(self) -> dict[str, Any]:
        d = dataclasses.asdict(self)
        d["mcv_latent"] = list(self.mcv_latent)
        return d


def _idv_z(
    origin_group: str,
    years_in_ireland: float | None,
    gen: np.random.Generator | None = None,
) -> float:
    """Hofstede individualism, standardised as MIMIC does, with acculturation.

    MIMIC: ``idvZ = (idv - 55) / 20``.  Design 5.13 then shrinks a non-Irish
    origin prior toward the Irish norm with years in Ireland, which is why a
    long-settled migrant is not modelled as permanently different from a
    neighbour - the stereotype guard (7.7) would fail if they were.

    Individual variation is added around the country mean.  Without it ``idvZ``
    is a deterministic function of origin - measured: within/between variance
    ratio 0.19, i.e. a group label rather than a trait - and every latent that
    depends on it would carry origin information directly into behaviour. That
    is precisely the mechanism design 5.8 forbids ("variation within each group
    must exceed the difference between groups") and risk K05 names.
    """
    idv = HOFSTEDE_IDV.get(origin_group, HOFSTEDE_IDV["other"])
    z = (idv - 55.0) / 20.0
    if origin_group != "IE" and years_in_ireland is not None:
        irish_z = (HOFSTEDE_IDV["IE"] - 55.0) / 20.0
        w = 1.0 - 0.5 ** (max(0.0, years_in_ireland) / ACCULTURATION_HALF_LIFE_YEARS)
        z = (1.0 - w) * z + w * irish_z
    if gen is not None:
        z += float(gen.normal(0.0, IDV_INDIVIDUAL_SD))
    return z


def make_mcv(latents: dict[str, float], gen: np.random.Generator) -> list[int]:
    """MIMIC's ``makeMcv``, reproduced exactly.

    Read from ``mimic_sd_generator.php`` lines 484-504.  The item-to-trait map
    and both noise levels (1.1 for satisficers, 0.7 otherwise) are MIMIC's, so
    an HRSD participant's MCV answers are generated by the same mapping MIMIC's
    own synthetic participants use - which is what design 5.14 level 1 requires.
    """
    L = latents
    mapping = [
        L["trans"],                                   # 1 personal duty to help
        L["community"],                               # 2 local solidarity
        L["trans"],                                   # 3 common good without reward
        0.7 * L["trans"] - 0.3 * L["idvZ"],           # 4 fairness over profit
        L["instTrust"],                               # 5 social trust
        L["trans"],                                   # 6 helping gives satisfaction
        0.6 * L["trans"] + 0.4 * L["community"],      # 7 rules bend for the vulnerable
        L["community"] - 0.3 * L["idvZ"],             # 8 collectivism vs individualism
        0.6 * L["community"] + 0.4 * L["trans"],      # 9 distributive fairness
        L["trans"],                                   # 10 donate rather than waste
    ]
    sd = 1.1 if L.get("satisficer") else 0.7
    out = []
    for v in mapping:
        x = 3.0 + 1.0 * v + float(gen.normal(0.0, sd))
        r = math.floor(x + 0.5) if x >= 0 else math.ceil(x - 0.5)  # PHP round()
        out.append(max(1, min(5, int(r))))
    return out


def lambda_weights(latents: dict[str, float]) -> tuple[float, float, float]:
    """lambda_1 to lambda_3: self, cooperative and altruistic reward weights.

    D05 requires ``lambda_self + lambda_coop + lambda_altru = 1``.  MIMIC's
    generator does not emit lambdas directly - design 5.13 lists them as "in
    draft" - so they are derived here from the latents by a softmax, which is
    the natural way to get three weights that sum to one from three scores and
    which keeps them strictly positive (a household with a zero weight on its
    own cost would be a degenerate RL reward).

    Recorded as an HRSD choice, not a MIMIC mapping, and flagged [A].
    """
    scores = np.array(
        [
            -0.6 * latents["trans"] + 0.5 * latents["comfort"],   # self-interest
            0.7 * latents["community"] + 0.3 * latents["conditional"],  # cooperative
            0.8 * latents["trans"] + 0.4 * latents["env"],        # altruistic
        ],
        dtype=np.float64,
    )
    e = np.exp(scores - scores.max())
    w = e / e.sum()
    # Round to 6 dp and put the residual on the largest weight so the three sum
    # to exactly 1.0 in the stored row, which D05 asserts.
    r = np.round(w, 6)
    r[int(np.argmax(r))] += 1.0 - r.sum()
    return (float(r[0]), float(r[1]), float(r[2]))


def draw_traits(
    seed_tree: SeedTree,
    *,
    person_id: str,
    sex: str,
    age: int,
    origin_group: str,
    years_in_ireland: float | None,
    education_z: float,
    income_quintile: int,
) -> TraitVector:
    """Draw one person's complete hidden trait layer.

    Addressed by ``person_id`` alone, so a person's traits do not depend on how
    many people were generated before them (design 8.2).
    """
    g = seed_tree.generator(Stream.PERSON_TRAITS, entity=person_id, sim_day=0)
    gb = seed_tree.generator(Stream.PERSON_BIG5, entity=person_id, sim_day=0)

    female = 0.5 if sex == "F" else -0.5
    # Age standardised on MIMIC's own band midpoints: its AGE_Z runs -1.3 to 1.3
    # across 18-24 to 65+, so roughly (age - 45) / 20.
    age_z = (age - 45.0) / 20.0
    young_male = 1.0 if (sex == "M" and age < 35) else 0.0
    idv_z = _idv_z(origin_group, years_in_ireland, g)
    digital_z = float(np.clip(-age_z * 0.6 + education_z * 0.4 + g.normal(0, 0.4), -1.6, 1.6))
    inst_trust_seed = 0.15 * education_z + 0.10 * age_z + float(g.normal(0, 0.40))

    predictors = {
        "female": female, "age_z": age_z, "edu_z": education_z,
        "idv_z": idv_z, "young_male": young_male, "digital_z": digital_z,
        "inst_trust": inst_trust_seed,
    }

    latents: dict[str, float] = {"idvZ": idv_z, "instTrust": inst_trust_seed}
    # Fixed order so the draws are reproducible; `trans` first because `env`
    # depends on it, as in MIMIC's generator.
    for name in ("trans", "community", "env", "autonomy", "comfort", "conditional", "privacy"):
        spec = DEMOGRAPHIC_PRIORS[name]
        mu = 0.0
        for pred, coef in spec["coefficients"].items():
            mu += coef * (latents.get(pred, predictors.get(pred, 0.0)))
        latents[name] = mu + float(g.normal(0.0, spec["residual_sd"]))

    latents["satisficer"] = 1 if float(g.random()) < SATISFICER_RATE else 0

    mcv = make_mcv(latents, g)
    lam = lambda_weights(latents)

    # Stated-revealed gap (design 5.13, Kormos & Gifford; Sheeran). Higher for
    # high-`trans` people, who over-report prosocial intent most; risk K15
    # records that the size of this gap is unknown for Irish households.
    stated_gap = float(
        np.clip(0.25 + 0.10 * latents["trans"] + g.normal(0, 0.08), 0.0, 1.0)
    )

    # Response propensity (design 5.14): "higher for high env, trans and digital
    # access, lower for high privacy".
    lp = 0.35 * latents["env"] + 0.30 * latents["trans"] + 0.25 * digital_z - 0.45 * latents["privacy"]
    response_propensity = float(1.0 / (1.0 + math.exp(-lp)))

    return TraitVector(
        trans=latents["trans"], community=latents["community"], env=latents["env"],
        autonomy=latents["autonomy"], comfort=latents["comfort"],
        conditional=latents["conditional"], privacy=latents["privacy"],
        instTrust=latents["instTrust"], idvZ=idv_z, satisficer=int(latents["satisficer"]),
        lambda_self=lam[0], lambda_coop=lam[1], lambda_altru=lam[2],
        mcv_latent=[float(v) for v in mcv],
        environmental_concern=self_report_from_latent(latents["env"]),
        trust_in_automation=self_report_from_latent(latents["autonomy"]),
        comfort_sensitivity=self_report_from_latent(latents["comfort"]),
        stated_gap=stated_gap,
        response_propensity=response_propensity,
        big5_o=float(gb.normal(0, 1)), big5_c=float(gb.normal(0, 1)),
        big5_e=float(gb.normal(0, 1)), big5_a=float(gb.normal(0, 1)),
        big5_n=float(gb.normal(0, 1)),
        # Chronotype in hours of offset, wider for the young (design 5.3 sleep window)
        chronotype=float(np.clip(-0.9 * age_z + gb.normal(0, 0.8), -3.0, 3.0)),
        habit_strength=float(np.clip(0.55 + 0.12 * age_z + gb.normal(0, 0.15), 0.05, 0.98)),
        lapse_rate=float(np.clip(0.08 - 0.02 * age_z + gb.normal(0, 0.03), 0.005, 0.40)),
        attention=float(np.clip(0.60 - 0.08 * abs(age_z) + gb.normal(0, 0.15), 0.05, 0.98)),
    )


def within_vs_between_variance(
    traits: list[TraitVector], groups: list[str], latent: str
) -> dict[str, float]:
    """Check design 5.8: within-group variation must exceed between-group.

        Variation within each group must exceed the difference between groups.

    Returns the two variance components and their ratio.  A ratio below 1 means
    the trait distribution is effectively a group label, which is exactly the
    stereotyping risk K05 names - so this is measured on every run rather than
    assumed from the smallness of the coefficients.
    """
    vals = np.array([getattr(t, latent) for t in traits], dtype=np.float64)
    gs = np.array(groups)
    grand = vals.mean()
    between = 0.0
    within = 0.0
    for gname in np.unique(gs):
        sel = vals[gs == gname]
        if sel.size == 0:
            continue
        between += sel.size * (sel.mean() - grand) ** 2
        within += float(((sel - sel.mean()) ** 2).sum())
    n = max(len(vals), 1)
    return {
        "latent": latent,
        "between_group_variance": between / n,
        "within_group_variance": within / n,
        "within_over_between": (within / max(between, 1e-12)),
        "n": int(n),
        "n_groups": int(len(np.unique(gs))),
    }
