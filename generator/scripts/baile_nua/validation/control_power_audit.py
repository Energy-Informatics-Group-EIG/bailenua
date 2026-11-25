"""Every negative control's magnitude, against its check's resolution.

The amendment this implements (I-034): **a negative control's magnitude must be
set from a power analysis, not chosen.**  NC-D2-03's 10% shift was chosen
because design 9.3 says "marginals shifted 10%", and it turned out to sit below
its check's 12.82% resolution, so the control could not fail and therefore
tested nothing.  That is not a property of that one control; it is a gap in how
all of them were specified.

So every control is audited here, and the audit distinguishes two kinds,
because a single notion of "power" does not apply to both.

**Deterministic controls.**  Detection is an exact predicate with no sampling
distribution: a field name matches a pattern or it does not; two presence
intervals overlap or they do not; a derived heat loss is outside a published
range or it is not.  For these the resolution is the threshold itself, the
power is 1 at any magnitude past it, and the quantity to report is the
**margin** - how far the planted fault sits beyond the point where the check
fires.  A margin close to 1 is the warning sign, because it means the control
is nearly inside the noise of its own construction.

**Statistical controls.**  Detection depends on a sampling distribution, so the
magnitude has to be set against a measured power curve.  Two exist: NC-D3-02's
planted position bias, and - though it is a criterion rather than a control -
MIMIC T10's planted arm, which is audited here because E1-6 depends on it.

A control whose margin cannot be stated is a control nobody can defend, which
is why every entry carries one.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

__all__ = ["ControlAudit", "CONTROL_AUDITS", "audit_all", "write_audit"]


@dataclasses.dataclass
class ControlAudit:
    """One control's magnitude set against what its check can see."""

    control_id: str
    kind: str                       # "deterministic" | "statistical"
    detected_quantity: str
    planted_magnitude: str
    check_fires_at: str
    margin: str
    margin_ratio: float | None      # planted / threshold, where meaningful
    adequate: bool
    note: str = ""

    def as_row(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


#: Declared audits for the deterministic controls.
#:
#: Each names the quantity the check actually tests, the threshold at which it
#: fires, and where the planted fault sits. These are not estimates: the checks
#: have no sampling distribution, so the numbers are exact.
CONTROL_AUDITS: tuple[ControlAudit, ...] = (
    ControlAudit(
        "NC-D1-01", "deterministic",
        "number of entities whose RNG draw changes with visit order",
        "22 of 24 entities change", "any single entity changing",
        "22x the minimum", 22.0, True,
        "A counter-based RNG either depends on order or it does not; the "
        "control plants a mutation that affects almost every entity.",
    ),
    ControlAudit(
        "NC-D1-02", "deterministic",
        "field-name match against D19's forbidden patterns",
        "a column named occupancy_count", "any name matching '(?i)occupan'",
        "exact match, no margin needed", None, True,
        "Name-based refusal is a predicate on strings. There is no magnitude "
        "to get wrong, and that is the point of refusing by name rather than "
        "by inspecting values.",
    ),
    ControlAudit(
        "NC-D1-03", "deterministic",
        "field-name match against the schema-derived person-level list",
        "a column named privacy (a MIMIC latent)",
        "any name in the hidden-layer or MIMIC-latent set",
        "exact match", None, True,
        "The list is derived from the schema, so it cannot fall behind the "
        "fields it is meant to cover (the I-020-era fix to NC-D1-03).",
    ),
    ControlAudit(
        "NC-D1-04", "deterministic",
        "presence of a mechanism string on every OBS field",
        "an OBS dataset with one field lacking a mechanism",
        "any OBS field with an empty mechanism",
        "exact", None, True,
        "Enforced at schema load, so the broken dataset cannot even be "
        "constructed.",
    ),
    ControlAudit(
        "NC-D1-05", "deterministic",
        "enum membership of a categorical value",
        "the value 'spaceship' in D11.zone",
        "any value outside the declared enum",
        "exact", None, True,
    ),
    ControlAudit(
        "NC-D2-01", "deterministic",
        "parent age at the child's birth, against the plausible range",
        "a parent aged 10 (so 0 at the birth)",
        "any parent outside [16, 50] at birth",
        "16 years below the lower bound", None, True,
        "The margin is in years and is large; a control planting a parent "
        "aged 15 would have a margin of one year and would be the kind of "
        "thing this audit exists to flag.",
    ),
    ControlAudit(
        "NC-D2-02", "deterministic",
        "gap between non-twin siblings' birth dates",
        "91 days (three months)", "any gap below 274 days",
        "183 days below the threshold, a factor of 3.0", 3.0, True,
    ),
    ControlAudit(
        "NC-D2-04", "deterministic",
        "derived specific heat loss against the published plausible range",
        "7.34 W/K/m2", "anything above 6.5 W/K/m2",
        "13% above the ceiling", 1.129, True,
        "The thinnest margin of any deterministic control, and deliberately "
        "so: the control exists to show the ceiling bites, and a fault far "
        "beyond it would not test the ceiling's position. The earlier version "
        "of this control used a 400 m2 house and came out INSIDE the range, "
        "which is the failure mode a 1.13 margin is one step away from.",
    ),
    ControlAudit(
        "NC-D2-05", "deterministic",
        "max |z| of the household-size marginal against the simultaneous band",
        "a 40% mass shift, giving max |z| 8.53",
        "a 12.82% shift, giving max |z| 2.7344",
        "3.1x the resolution in shift fraction", 3.12, True,
        "This is the control that demonstrates the single-realisation band "
        "works where it is applicable. Its magnitude is now justified by the "
        "same power analysis that disqualified NC-D2-03's.",
    ),
    ControlAudit(
        "NC-D3-01", "deterministic",
        "field-name match against D25's ADR-004 forbidden patterns",
        "a column named medical_device_dependence",
        "any name matching '(?i)medical'",
        "exact match", None, True,
    ),
    ControlAudit(
        "NC-D4-01", "deterministic",
        "overlap between two presence intervals for one person",
        "a 60-minute overlap in two different buildings",
        "any overlap of one minute or more",
        "60x the minimum", 60.0, True,
    ),
    ControlAudit(
        "NC-D4-02", "deterministic",
        "relative residual of the daily energy balance",
        "a 3% shortfall", "0.1% of gross daily throughput",
        "30x the tolerance", 30.0, True,
        "Chosen at 3% precisely because it is small enough to pass a plot and "
        "large enough to be unambiguous; the audit confirms it is 30 times "
        "the threshold rather than near it.",
    ),
    ControlAudit(
        "NC-D5-01", "deterministic",
        "field-name match on a D19 export after build_export has returned",
        "a column named occupancy_count",
        "any name matching '(?i)occupan'",
        "exact match", None, True,
    ),
    ControlAudit(
        "NC-D5-02", "deterministic",
        "byte equality of two renders from one signature seed",
        "2% multiplicative noise, about 40 W on a 2 kW cycle",
        "any difference at all, about 1e-13 W in double precision",
        "about 14 orders of magnitude", None, True,
        "Exact-equality checks have effectively unbounded resolution, which "
        "is why determinism is tested by equality and not by a tolerance.",
    ),
    ControlAudit(
        "NC-D6-01", "deterministic",
        "equality of per-household results between two execution orders",
        "a shared accumulator worth about 1e-6 of the running total",
        "any difference at all",
        "about 10 orders of magnitude", None, True,
    ),
    # ---- week 3's three controls --------------------------------------- #
    # Added late: all three were registered and exercised by the harness for
    # two days with no entry here, so `test_the_audit_covers_every_registered_
    # control` failed in the full suite and passed when run alone - the other
    # test module that imports controls_week3 is what put them in the
    # REGISTRY. A control with no audited magnitude is a control whose
    # magnitude nobody justified, which is the whole of I-034.
    ControlAudit(
        "NC-JOINT-01", "statistical",
        "people in an age x economic-status cell the reference puts below "
        "0.001 of the 15+ population",
        "I-069's independence defect at n=1,200 people",
        "5 or more people in such a cell",
        "6.0x the smallest population that detects it in 12 of 12 trials "
        "(n=200)", 6.0, True,
        "The only week-3 control with a sampled power curve, because it is "
        "the only one whose check counts PEOPLE and can therefore pass by "
        "being small: v1/evidence/nc_joint01_power.json measures 9 of 12 "
        "detections at n=100 and 12 of 12 from n=200 up. The town's own 15+ "
        "population is 2,267, which is 11.3x the resolution, so a pass on the "
        "town is evidence rather than an artefact of its size.",
    ),
    ControlAudit(
        "NC-VENUE-01", "deterministic",
        "minutes in which one person is recorded at a venue and at home at "
        "once",
        "one person overlapping for 300 minutes (09:00-15:00 against "
        "10:00-16:40)",
        "any single overlapping minute",
        "300x the minimum", 300.0, True,
        "A presence contradiction is a predicate on interval overlap, so the "
        "resolution is one minute and there is no sampling distribution. The "
        "magnitude that needed justifying is the OTHER side: the venue holds "
        "3 people against a declared capacity of 50, so the check cannot be "
        "rejecting the record for being over capacity, and the control's "
        "must-still-pass arm asserts exactly that.",
    ),
    ControlAudit(
        "NC-EXPORT-01", "deterministic",
        "whether a compliance-only export carries the interval energy series "
        "at all",
        "a full day's half-hourly import series, 48 intervals summing to "
        "about 7.6 kWh",
        "any non-null interval energy summing above zero",
        "exact: presence, not size", None, True,
        "I-067 rebuilt. There is deliberately no magnitude to tune, because "
        "the defect was never about how much energy leaked - the pre-fix "
        "mitigation carried exactly the same 163,137,265.9 Wh as the "
        "configuration it was offered as safer than. A threshold on the "
        "quantity would have passed it.",
    ),
)


def _plausibility_audits() -> list[ControlAudit]:
    """The U27 plausibility controls (U26: every new control power-analysed).

    Every plausibility check is a deterministic predicate - a measured value
    against a declared band, with no sampling distribution - so the resolution
    is the band edge and the quantity to report is the margin. Magnitudes and
    their reasoning live beside the controls themselves, in
    `controls_plausibility.PLAUSIBILITY_CONTROL_MAGNITUDES`, so a control and
    its justification cannot drift apart.
    """
    from baile_nua.validation.controls_plausibility import (
        PLAUSIBILITY_CONTROL_MAGNITUDES as MAG,
    )

    out: list[ControlAudit] = []
    for cid, m in sorted(MAG.items()):
        out.append(ControlAudit(
            cid, "deterministic", m["quantity"],
            f"{m['planted']}", f"{m['band_edge']}",
            f"{m['margin_ratio']:.2f}x the band edge",
            float(m["margin_ratio"]), True, m["note"],
        ))
    return out


def _gc_mode_audits() -> list[ControlAudit]:
    """The G-C and T6 controls (U26: every new control power-analysed).

    These are not all of one kind, and saying so matters.

    **NC-GC-01** is statistical: the T6 null control's statistic is an
    incremental cross-validated R2 and it has a sampling distribution, so the
    resolution is the minimum detectable effect from the F-test
    non-centrality - which is computed, not declared, by
    ``gc_modes.t6_power``.

    **NC-GC-02** is a fixed point rather than a magnitude: the control hands
    the mode the exact correlation (r = 0.97) at which the first version of it
    silently stopped being adversarial. The margin is the ratio of variance
    inflation between the two correlations, which is what actually changed.

    **NC-GC-03** is statistical: a gap z-score against a reference
    distribution the data itself generates, so the resolution is the
    reference's own standard deviation.
    """
    from baile_nua.mimic import gc_modes as gc

    out: list[ControlAudit] = []

    # NC-GC-01: planted effect against the minimum detectable effect.
    linked = gc.generate(gc.T6_LINKED_MODE, n=2000, master_seed=4242)
    a = gc.assess(linked, seed=1)
    planted = float(a.statistics["incremental_cv_r2"])
    mdi = float(a.statistics["minimum_detectable_incremental_r2"])
    out.append(ControlAudit(
        "NC-GC-01", "statistical",
        "incremental cross-validated R2 of the Flex Profile over a "
        "demographics-and-opportunity baseline",
        f"{planted:.4f} incremental cv R2 (and 0.55 x stated added directly "
        f"in the control itself, which is larger again)",
        f"{mdi:.4f}, the minimum detectable incremental R2 at n = 2000 from "
        f"the F-test non-centrality",
        f"{planted / mdi:.1f}x the detectable floor",
        planted / mdi, True,
        "The null arm's clean result is only informative because the linked "
        "arm detects an effect of this size. An underpowered null reports no "
        "effect for every cohort and certifies nothing.",
    ))

    # NC-GC-02: the correlation at which the mode stops being adversarial.
    vif_real = 1.0 / (1.0 - 0.9995 ** 2)
    vif_broken = 1.0 / (1.0 - 0.97 ** 2)
    out.append(ControlAudit(
        "NC-GC-02", "deterministic",
        "whether the difference between two collinear coefficients is "
        "distinguishable from zero",
        f"r = 0.97, variance inflation {vif_broken:.0f} - the value the first "
        f"version of the mode used, at which the coefficients ARE recoverable",
        f"r = 0.9995, variance inflation {vif_real:.0f}, where the "
        f"difference's interval covers zero",
        f"{vif_real / vif_broken:.0f}x the variance inflation",
        vif_real / vif_broken, True,
        "Not a chosen magnitude: it is the exact value at which this mode "
        "really did stop being adversarial during the build, turned into a "
        "permanent test.",
    ))

    # NC-GC-03: the cluster gap, against its own reference distribution.
    rng = np.random.default_rng(99)
    centres = np.array([[-4.0, -4.0, 0.0], [4.0, -4.0, 0.0], [0.0, 4.0, 0.0]])
    real = np.vstack([
        rng.multivariate_normal(c, np.eye(3) * 0.6, 700) for c in centres
    ])
    gate = gc.cluster_validity_gap(real, ks=(2, 3, 4), n_reference=8, seed=1)
    out.append(ControlAudit(
        "NC-GC-03", "statistical",
        "best-k silhouette measured against a no-structure reference with the "
        "same covariance",
        f"three classes at 8 sigma separation: gap z = {gate['gap_z']:+.1f}",
        f"z = {gc._GAP_REJECT_Z}, the acceptance threshold",
        f"{abs(gate['gap_z']) / gc._GAP_REJECT_Z:.1f}x the threshold",
        abs(gate["gap_z"]) / gc._GAP_REJECT_Z, True,
        "The complement of mode 3: without this, a gate that rejected "
        "clusters unconditionally would pass the continuous-no-clusters mode "
        "forever while detecting nothing.",
    ))
    return out


def _chi2_position_power(
    *, n: int, first_share: float, alpha: float, n_trials: int, seed: int = 7,
) -> float:
    """Power of the four-position chi-square test at a given first-position share."""
    rng = np.random.default_rng(seed)
    rest = (1.0 - first_share) / 3.0
    p = np.array([first_share, rest, rest, rest])
    crit = stats.chi2.ppf(1.0 - alpha, 3)
    draws = rng.multinomial(n, p, size=n_trials).astype(float)
    expected = n / 4.0
    chi2 = ((draws - expected) ** 2 / expected).sum(axis=1)
    return float((chi2 > crit).mean())


def _min_detectable_share(
    *, n: int, alpha: float, target_power: float = 0.95,
    n_trials: int = 4000, tol: float = 1e-4,
) -> float:
    """Smallest first-position share detected with ``target_power``."""
    lo, hi = 0.25, 0.95
    if _chi2_position_power(
        n=n, first_share=hi, alpha=alpha, n_trials=n_trials
    ) < target_power:
        return float("nan")
    while hi - lo > tol:
        mid = 0.5 * (lo + hi)
        if _chi2_position_power(
            n=n, first_share=mid, alpha=alpha, n_trials=n_trials
        ) >= target_power:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def _statistical_audits(n_trials: int = 4000) -> list[ControlAudit]:
    """The two controls whose detection depends on a sampling distribution."""
    out: list[ControlAudit] = []

    # NC-D3-02: 70% first-position share, n = 4,000, rejected at p < 1e-6.
    n, alpha, planted = 4000, 1e-6, 0.70
    mds = _min_detectable_share(n=n, alpha=alpha, n_trials=n_trials)
    power = _chi2_position_power(
        n=n, first_share=planted, alpha=alpha, n_trials=n_trials
    )
    excess = (planted - 0.25) / (mds - 0.25) if mds == mds else float("nan")
    out.append(ControlAudit(
        "NC-D3-02", "statistical",
        "chi-square on the chosen display position, 4 positions, 3 df",
        f"first-position share {planted:.0%} at n={n:,} "
        f"(measured power {power:.3f})",
        f"first-position share {mds:.1%} for 95% power at alpha={alpha:g}",
        f"{excess:.1f}x the minimum detectable departure from 25%",
        float(excess), bool(power >= 0.95),
        "A deliberately unambiguous magnitude: the control's job is to prove "
        "the detector fires, and T10's own arm is the graded version.",
    ))

    # MIMIC T10's planted arm. Not a negative control, but E1-6 depends on it,
    # so its magnitude needs the same justification.
    n10, alpha10, observed_share = 7516, 0.01, 0.4466
    mds10 = _min_detectable_share(n=n10, alpha=alpha10, n_trials=n_trials)
    power10 = _chi2_position_power(
        n=n10, first_share=observed_share, alpha=alpha10, n_trials=n_trials
    )
    excess10 = (
        (observed_share - 0.25) / (mds10 - 0.25) if mds10 == mds10 else float("nan")
    )
    out.append(ControlAudit(
        "T10-planted-arm", "statistical",
        "chi-square on the chosen display position in the planted MIMIC arm",
        f"first-position share {observed_share:.2%} realised at n={n10:,} "
        f"responses from a 1.6 odds multiplier (measured power {power10:.3f})",
        f"first-position share {mds10:.2%} for 95% power at alpha={alpha10:g}",
        f"{excess10:.1f}x the minimum detectable departure from 25%",
        float(excess10), bool(power10 >= 0.95),
        "Audited although it is an E1-6 criterion rather than a negative "
        "control, because the same question applies: a planted effect below "
        "its test's resolution would make T10 pass for the wrong reason. It "
        "is not - the margin is large - and the clean arm's 126,007 responses "
        "give chi-square 0.978 at p = 0.81, so the test is not simply always "
        "firing.",
    ))
    return out


def _ensemble_audit() -> ControlAudit:
    """NC-D2-03 after the amendment, in households rather than percentages."""
    from baile_nua.validation.ensemble_control import ENSEMBLE_K

    n = 1092
    t_crit = float(stats.t.ppf(1.0 - 0.05 / 16.0, ENSEMBLE_K - 1))
    fires_at_households = t_crit * 0.5          # SE floor is half a household
    planted_households = 25.0                   # measured, worst category '4'
    return ControlAudit(
        "NC-D2-03", "deterministic",
        "ensemble-mean household-size marginal against the control totals the "
        "generator was given, at the generator's own run-to-run precision",
        f"{planted_households:.0f} households in the worst category "
        f"(a 10% mass shift), giving max |z| 50.0",
        f"{fires_at_households:.1f} households "
        f"(t band {t_crit:.3f} on {ENSEMBLE_K - 1} df, standard-error floor "
        f"of half a household in {n:,})",
        f"{planted_households / fires_at_households:.0f}x the resolution",
        float(planted_households / fires_at_households), True,
        "Deterministic because the generator's across-run standard deviation "
        "on this marginal is 1.7e-16 - it reproduces its control totals "
        "exactly - so the ensemble check's resolution is set by the "
        "integerisation granularity, not by sampling noise. Before the "
        "amendment this control was pointed at the single-realisation band, "
        "whose resolution is 34 households, and the 25-household fault could "
        "not fire it.",
    )


def audit_all(n_trials: int = 4000) -> dict[str, Any]:
    """Every control's magnitude against its check's resolution."""
    from baile_nua import CLAIM, LABEL

    rows = (
        list(CONTROL_AUDITS)
        + [_ensemble_audit()]
        + _plausibility_audits()
        + _gc_mode_audits()
        + _statistical_audits(n_trials)
    )
    rows.sort(key=lambda r: r.control_id)
    inadequate = [r.control_id for r in rows if not r.adequate]
    thin = [
        r.control_id for r in rows
        if r.margin_ratio is not None and r.margin_ratio < 2.0
    ]
    return {
        "label": LABEL,
        "claim": CLAIM,
        "design_ref": "9.3 negative-control rule; I-034 amendment; D-026",
        "rule": (
            "A negative control's magnitude must be set from a power analysis "
            "against its own check's resolution, not chosen from the design's "
            "prose. A control whose magnitude sits below its check's "
            "resolution cannot fail and therefore tests nothing."
        ),
        "n_controls_audited": len(rows),
        "n_deterministic": sum(1 for r in rows if r.kind == "deterministic"),
        "n_statistical": sum(1 for r in rows if r.kind == "statistical"),
        "controls_below_their_resolution": inadequate,
        "controls_with_a_margin_under_2x": thin,
        "all_adequate": not inadequate,
        "audits": [r.as_row() for r in rows],
    }


def write_audit(path: str | Path, n_trials: int = 4000) -> dict[str, Any]:
    out = audit_all(n_trials)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8")
    return out
