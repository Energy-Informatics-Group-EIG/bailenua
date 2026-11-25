"""Tests pinning the marginal-check power analysis (D-026, I-034).

These exist so the 10% fault cannot quietly be pointed back at a check that
cannot see it, and so the numbers in the gate report cannot drift from the
numbers the analysis produced.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import baile_nua.sources_registry  # noqa: F401  (declares the sources)
from baile_nua.population.joint_metrics import (
    ENSEMBLE_DETERMINISTIC_SD_TOLERANCE,
    ENSEMBLE_SE_FLOOR_HOUSEHOLDS,
    ENSEMBLE_TARGET_VS_SAPS_MAX_ABS_Z,
    contracted_reference,
    ensemble_marginal_acceptance,
    marginal_acceptance,
    marginal_error,
)
from baile_nua.validation.control_power_audit import audit_all
from baile_nua.validation.ensemble_control import (
    ENSEMBLE_K,
    ENSEMBLE_K_MINIMUM,
)
from baile_nua.validation.power import (
    ShiftSpec,
    bonferroni_z,
    deterministic_resolution,
    random_sample_power,
    shift_counts,
)

#: Cobh's household-size marginal, as NC-D2-03 uses it.
REF = pd.Series(
    {"1": 1290, "2": 1509, "3": 920, "4": 921, "5": 435, "6": 137, "7": 30, "8+": 15}
)
N_TOWN = 1092
SPEC = ShiftSpec(source="1", sink="4", fraction=0.10)


def test_the_power_module_agrees_with_the_band_it_analyses():
    """If the band changes, the analysis must not keep the old critical value.

    The power module reproduces the Bonferroni critical value rather than
    importing it, so that the two can be compared. This is the comparison.
    """
    errors = marginal_error(
        _reference_marginal(), {"household_size": _scaled(REF)}
    )
    _detail, summary = marginal_acceptance(errors)
    assert np.isclose(
        summary["z_crit_simultaneous_bonferroni"], bonferroni_z(8, 0.05), atol=1e-4
    ), (
        f"the power analysis uses {bonferroni_z(8, 0.05):.4f} and the band uses "
        f"{summary['z_crit_simultaneous_bonferroni']}; one of them has drifted"
    )


def _scaled(counts: pd.Series) -> pd.Series:
    return (counts.astype(float) * (N_TOWN / float(counts.sum()))).round().astype(int)


def _reference_marginal():
    from baile_nua.population.saps import Marginal, MarginalSpec

    spec = MarginalSpec(
        key="household_size", unit="household", saps_table="T5_2",
        categories={k: (k,) for k in REF.index}, total_column=None,
        design_ref="power analysis",
    )
    return {
        "household_size": Marginal(
            spec=spec, by_small_area=pd.DataFrame([REF.to_dict()], index=["ALL"]),
            town_total=REF, total_declared=int(REF.sum()),
            total_from_categories=int(REF.sum()),
        )
    }


# --------------------------------------------------------------------------- #
# the resolution, and the fact that 10% is below it
# --------------------------------------------------------------------------- #

def test_the_single_realisation_resolution_is_about_thirteen_percent():
    """The number that disqualified NC-D2-03's original magnitude."""
    r = deterministic_resolution(REF, n=N_TOWN, spec=SPEC)
    assert 0.12 < r.deterministic_resolution_fraction < 0.14, (
        f"resolution came out at {r.deterministic_resolution_fraction:.4%}; "
        f"the analysis recorded in D-026 says 12.82%, and the gate report "
        f"quotes it"
    )


def test_the_planted_ten_percent_shift_is_below_that_resolution():
    """The whole reason the control had to be re-pointed.

    Asserted rather than described: if a later change to the band or to the
    reference made 10% detectable, this test fails and the amendment can be
    revisited on evidence instead of being carried forward out of habit.
    """
    r = deterministic_resolution(REF, n=N_TOWN, spec=SPEC)
    assert not r.planted_detected
    assert r.planted_max_abs_z < bonferroni_z(8, 0.05), (
        f"the 10% shift gives max |z| {r.planted_max_abs_z:.4f} against a "
        f"critical {bonferroni_z(8, 0.05):.4f}"
    )
    assert 2.0 < r.planted_max_abs_z < 2.3


def test_the_forty_percent_control_is_above_the_resolution():
    """NC-D2-05 must stay detectable by the single-realisation band."""
    r = deterministic_resolution(
        REF, n=N_TOWN, spec=ShiftSpec(source="1", sink="4", fraction=0.40)
    )
    assert r.planted_detected
    assert r.planted_max_abs_z > 2.0 * bonferroni_z(8, 0.05)


def test_the_band_is_calibrated_at_its_declared_alpha():
    """The calibration check on the whole analysis.

    A simultaneous band at alpha=0.05 must reject an unshifted random draw at
    about 0.05. If it did not, neither the band nor any power number derived
    from it could be trusted.
    """
    curve = random_sample_power(
        REF, n=N_TOWN, fractions=(0.0,), spec=SPEC, n_trials=4000
    )
    fpr = float(curve.rejection_rate.iloc[0])
    assert 0.02 <= fpr <= 0.09, (
        f"false-positive rate {fpr:.4f} at a declared alpha of 0.05"
    )


def test_a_random_draw_of_the_town_cannot_see_ten_percent_either():
    """Not merely this check: 1,092 households do not carry the information.

    Power is about 0.43, so even an optimal test on a genuine random draw
    would miss the fault more often than not. The magnitude was the problem,
    not the care taken in applying the check.
    """
    curve = random_sample_power(
        REF, n=N_TOWN, fractions=(0.10,), spec=SPEC, n_trials=4000
    )
    power = float(curve.rejection_rate.iloc[0])
    assert 0.30 < power < 0.55, f"power at the planted 10% shift is {power:.3f}"


# --------------------------------------------------------------------------- #
# the ensemble check
# --------------------------------------------------------------------------- #

def _runs(counts: pd.Series, k: int) -> list[pd.Series]:
    """K identical runs: what a deterministic generator actually produces."""
    return [counts.copy() for _ in range(k)]


def test_the_ensemble_check_detects_the_ten_percent_shift():
    correct = _scaled(REF)
    shifted = _scaled(shift_counts(REF, SPEC))
    p_ref = correct.astype(float) / float(correct.sum())
    _d, summary = ensemble_marginal_acceptance(p_ref, _runs(shifted, ENSEMBLE_K))
    assert summary["verdict"] == "FAIL"
    assert summary["observed_max_abs_z"] > 5.0 * summary["t_crit_bonferroni"], (
        f"detected, but only at max |z| {summary['observed_max_abs_z']} against "
        f"a band of {summary['t_crit_bonferroni']}; the measured margin is "
        f"about 16x and a much thinner one would mean the check is marginal"
    )


def test_the_ensemble_check_passes_a_correct_generator():
    """The false-positive control, as a unit test as well as a control."""
    correct = _scaled(REF)
    p_ref = correct.astype(float) / float(correct.sum())
    _d, summary = ensemble_marginal_acceptance(p_ref, _runs(correct, ENSEMBLE_K))
    assert summary["verdict"] == "PASS"
    assert summary["observed_max_abs_z"] == 0.0


def test_the_ensemble_check_refuses_a_single_run():
    """One run cannot distinguish bias from variability, and must not pretend to."""
    correct = _scaled(REF)
    p_ref = correct.astype(float) / float(correct.sum())
    with pytest.raises(ValueError, match="at least 2 runs"):
        ensemble_marginal_acceptance(p_ref, _runs(correct, 1))


def test_the_se_floor_is_the_integerisation_granularity():
    """Half a household: the finest deviation the generator can express.

    Pinned because it is the only thing standing between a deterministic
    marginal and a division by zero, and because an arbitrary floor would make
    the check's sensitivity arbitrary.
    """
    assert ENSEMBLE_SE_FLOOR_HOUSEHOLDS == 0.5
    correct = _scaled(REF)
    p_ref = correct.astype(float) / float(correct.sum())
    _d, summary = ensemble_marginal_acceptance(p_ref, _runs(correct, ENSEMBLE_K))
    assert summary["generator_is_deterministic_in_this_marginal"], (
        f"across-run SD came out at {summary['max_across_run_sd']:.3e}, above "
        f"the {ENSEMBLE_DETERMINISTIC_SD_TOLERANCE:.0e} tolerance, so the "
        f"generator is no longer deterministic in this marginal and the "
        f"ensemble's power now does come from averaging"
    )
    assert summary["se_floor_binding_in_n_categories"] == 8
    # The tolerance must sit between floating-point noise and real variation.
    assert 1e-15 < ENSEMBLE_DETERMINISTIC_SD_TOLERANCE < 1e-4


def test_k_is_at_least_the_power_analysis_minimum():
    assert ENSEMBLE_K >= ENSEMBLE_K_MINIMUM
    assert ENSEMBLE_K_MINIMUM == 4, (
        "the minimum K is derived from 3,664 households for 95% power against "
        "a 10% shift divided by the town's 1,092; if either changes, re-derive "
        "it rather than editing this number"
    )


def test_the_ensemble_against_raw_saps_rejects_a_correct_population():
    """The measurement that forced the two-reference design.

    Kept as a test because it is the justification for not taking "test the
    ensemble mean against SAPS" literally, and because if the person-total
    repair were ever removed this test would fail and the design could be
    simplified.
    """
    from baile_nua.population import saps, scale_down

    reference = saps.build_marginals()
    plan = scale_down.build_both(reference, master_seed=1)["proportional"]
    saps_town = reference["household_size"].town_total
    target = plan.marginals["household_size"].sum(axis=0)
    cr = contracted_reference(saps_town, target)

    correct_runs = _runs(target.astype(int), ENSEMBLE_K)
    _d, against_saps = ensemble_marginal_acceptance(
        cr["saps_proportions"], correct_runs
    )
    assert against_saps["verdict"] == "FAIL", (
        "a correct population now passes against raw SAPS, so the declared "
        "person-total repair has gone and the two-reference design can be "
        "revisited"
    )
    _d2, against_target = ensemble_marginal_acceptance(
        cr["reference_proportions"], correct_runs
    )
    assert against_target["verdict"] == "PASS"


def test_the_declared_repair_stays_inside_its_budget():
    from baile_nua.population import saps, scale_down

    reference = saps.build_marginals()
    plan = scale_down.build_both(reference, master_seed=1)["proportional"]
    cr = contracted_reference(
        reference["household_size"].town_total,
        plan.marginals["household_size"].sum(axis=0),
    )
    assert cr["target_vs_saps_max_abs_z"] <= ENSEMBLE_TARGET_VS_SAPS_MAX_ABS_Z, (
        f"the person-total repair now moves the marginal "
        f"{cr['target_vs_saps_max_abs_z']} standard errors from SAPS, beyond "
        f"its budget of {ENSEMBLE_TARGET_VS_SAPS_MAX_ABS_Z}. It may use the "
        f"sampling-error budget and may not exceed it (D-010)."
    )


# --------------------------------------------------------------------------- #
# the audit of every control
# --------------------------------------------------------------------------- #

def test_no_control_is_below_its_own_check_s_resolution():
    """The amendment, enforced (I-034)."""
    audit = audit_all(n_trials=1500)
    assert audit["all_adequate"], (
        f"these controls cannot fire their own checks: "
        f"{audit['controls_below_their_resolution']}"
    )


def test_every_control_declares_a_margin():
    audit = audit_all(n_trials=1500)
    for row in audit["audits"]:
        assert row["check_fires_at"], f"{row['control_id']} has no threshold"
        assert row["margin"], f"{row['control_id']} has no margin"
        assert row["kind"] in ("deterministic", "statistical")


def test_the_audit_covers_every_registered_control():
    """A control added without an audit entry must fail this, not pass silently."""
    import baile_nua.validation.controls_day1  # noqa: F401
    import baile_nua.validation.controls_day2  # noqa: F401
    import baile_nua.validation.controls_day3to6  # noqa: F401
    import baile_nua.validation.controls_week3  # noqa: F401
    import baile_nua.validation.ensemble_control  # noqa: F401
    from baile_nua.validation.negative_control import REGISTRY

    audited = {r["control_id"] for r in audit_all(n_trials=200)["audits"]}
    missing = set(REGISTRY) - audited
    assert not missing, (
        f"these registered controls have no power-audit entry, so their "
        f"magnitudes are unjustified: {sorted(missing)}"
    )
