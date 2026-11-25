"""Week 2 step 4: WP4 behaviour depth, with ablations.

r4 section 9.4's acceptance is "ablations degrade fit as expected". These tests
pin the two things that make that statement mean anything: fit is measured
against PUBLISHED references rather than against the model's own baseline, and
each arm declares what it should degrade before it runs.

The matrix itself is an artefact produced by five year-long runs, so it is not
rebuilt here. What is tested is the machinery that decides what the matrix
means - because a classifier that called everything a pass would produce a
clean artefact and tell us nothing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import baile_nua.sources_registry  # noqa: F401
from baile_nua.sources import REGISTRY
from baile_nua.validation.behaviour_ablation import (
    ABLATION_ARMS,
    FIT_METRICS,
    BehaviourSwitches,
    arm_switches,
    classify,
    compare_matrix,
    measure_fit,
)

ROOT = Path(__file__).resolve().parents[2]
ARTEFACT = ROOT / "v1" / "evidence" / "behaviour_ablation_w2s4.json"


# --------------------------------------------------------------------------- #
# the thing that makes an ablation suite honest
# --------------------------------------------------------------------------- #

def test_fit_is_measured_against_published_references_not_the_baseline():
    """Scoring against the baseline would make every ablation degrade fit.

    That is the trap this suite is written to avoid: if "worse" meant
    "different from the full model", then every perturbation would pass and
    the acceptance criterion would be unfalsifiable.
    """
    for name, spec in FIT_METRICS.items():
        assert "reference" in spec, name
        assert "source" in spec, name
        if "declared band" in spec["source"]:
            # The one metric with no published source is flagged as such.
            assert "unsourced" in spec["source"]
            continue
        key = spec["source"]
        assert key in REGISTRY, (
            f"{name} cites {key!r}, which is not a declared source"
        )
        assert REGISTRY[key].manifest_path.exists(), (
            f"{name} cites {key!r}, which was never fetched"
        )


def test_every_arm_declares_what_it_should_degrade_before_running():
    """"As expected" requires an expectation on the record."""
    for spec in ABLATION_ARMS:
        if spec["arm"] == "full":
            assert spec["off"] == () and spec["expects"] == ()
            continue
        assert spec["off"], spec["arm"]
        assert spec["expects"], (
            f"{spec['arm']} turns something off without saying what that "
            f"should degrade, so its result cannot be right or wrong"
        )
        for metric in spec["expects"]:
            assert metric in FIT_METRICS, (spec["arm"], metric)
        assert len(spec["why"]) > 60, spec["arm"]


def test_an_arm_that_improves_the_fit_is_reported_not_passed():
    """The outcome an ablation suite is most likely to bury."""
    arm = {
        "arm": "x", "off": ("comfort_taking",),
        "expects": ("gas_meter_ratio",), "why": "y" * 70,
    }
    # Baseline sits further from 1.0 than the arm does, so removing the
    # mechanism IMPROVED the fit.
    out = classify(arm, {"gas_meter_ratio": 1.40}, {"gas_meter_ratio": 1.10})
    assert out["verdict"] == "IMPROVED"
    assert "BETTER" in out["verdict_note"] or "better" in out["verdict_note"]
    assert out["metrics"]["gas_meter_ratio"]["improved"] is True


def test_an_inert_mechanism_is_reported_not_passed():
    arm = {
        "arm": "x", "off": ("habit_variation",),
        "expects": ("load_factor",), "why": "y" * 70,
    }
    out = classify(arm, {"load_factor": 0.25}, {"load_factor": 0.25})
    assert out["verdict"] == "NO_EFFECT"
    assert "inert" in out["verdict_note"]


def test_a_degraded_arm_passes():
    arm = {
        "arm": "x", "off": ("comfort_taking",),
        "expects": ("gas_meter_ratio",), "why": "y" * 70,
    }
    out = classify(arm, {"gas_meter_ratio": 1.40}, {"gas_meter_ratio": 1.70})
    assert out["verdict"] == "DEGRADED_AS_PREDICTED"


def test_the_matrix_refuses_to_assemble_without_its_baseline():
    with pytest.raises(ValueError, match="needs the 'full' arm"):
        compare_matrix({"no_chronotype": {"annual_electricity": {
            "per_dwelling": [{"heating_fuel": "natural gas"}]}}})


# --------------------------------------------------------------------------- #
# the switches
# --------------------------------------------------------------------------- #

def test_the_delivered_model_has_every_switch_on():
    assert BehaviourSwitches().all_on is True
    assert arm_switches("full").all_on is True


def test_each_arm_turns_off_exactly_what_it_declares():
    """Every mechanism that is False in an arm must be one the arm declares.

    "False" and "turned off" were the same thing until
    `duration_weighted_timing` arrived (D-078), and they are not the same
    thing: that switch's DELIVERED value is False, because it restores a
    SUPERSEDED placement weight rather than disabling a mechanism. It is
    excluded by name through `BehaviourSwitches._DELIVERED_FALSE` rather than
    by a special case here, so a second switch of the same kind cannot be
    added without declaring it.

    It is deliberately NOT in ABLATION_ARMS. The r4 9.4 criterion on ablations
    is that they degrade fit, and this one does the opposite: the superseded
    weight scores BETTER against LP1 (MARD 0.1720 against the delivered
    0.1763, `i052_lp1_timing.json`). Listing it as an ablation would make a
    true statement - it changes the fit - under a heading that claims the
    wrong direction. It is kept runnable for reproducibility, which is a
    different purpose from an ablation arm, and D-078 records why the
    better-fitting arm is not the delivered one.
    """
    delivered_false = set(BehaviourSwitches._DELIVERED_FALSE)
    for spec in ABLATION_ARMS:
        sw = arm_switches(spec["arm"]).as_dict()
        off = {k for k, v in sw.items() if not v} - delivered_false
        assert off == set(spec["off"]), (spec["arm"], off, spec["off"])
        for k in delivered_false:
            assert sw.get(k) is False, (
                f"{spec['arm']} sets {k} to True. A switch whose delivered "
                f"value is False must stay False in every ablation arm, or "
                f"the arm is comparing two changes at once."
            )


def test_an_unknown_arm_is_refused():
    with pytest.raises(ValueError, match="unknown arm"):
        arm_switches("no_such_mechanism")


# --------------------------------------------------------------------------- #
# the artefact the five runs produced
# --------------------------------------------------------------------------- #

@pytest.mark.skipif(not ARTEFACT.exists(), reason="matrix not yet run")
def test_the_recorded_matrix_meets_the_acceptance_criterion():
    """r4 9.4: ablations degrade fit as expected."""
    rec = json.loads(ARTEFACT.read_text(encoding="utf-8"))
    assert rec["acceptance_met"] is True
    assert rec["n_degraded_as_predicted"] == len(rec["arms"])
    assert rec["n_no_effect"] == 0
    assert rec["n_improved"] == 0
    assert "never from this model's own baseline" in rec["what_fit_means"]


@pytest.mark.skipif(not ARTEFACT.exists(), reason="matrix not yet run")
def test_comfort_taking_is_the_strongest_arm_and_occupancy_the_broadest():
    """Not a tautology: which arm does what is a measured result.

    Comfort-taking exists to flatten gas across the fabric range, so it should
    dominate the BER spread. Occupancy-gated heating touches gas, the load
    factor AND the peak hour, because heating an empty house changes how much,
    how flat and when.
    """
    rec = json.loads(ARTEFACT.read_text(encoding="utf-8"))
    fits = rec["fits"]
    assert fits["no_comfort_taking"]["ber_spread_pct"] > \
        fits["full"]["ber_spread_pct"] + 20, (
        "removing comfort-taking barely widened the BER spread, which is the "
        "one thing it is for"
    )
    # Occupancy gating moves the peak hour off LP1's 18:00; nothing else does.
    assert fits["no_occupancy_gated_heating"]["peak_hour_error"] > 0
    assert fits["full"]["peak_hour_error"] == 0


@pytest.mark.skipif(not ARTEFACT.exists(), reason="matrix not yet run")
def test_the_privacy_premise_holds():
    """Design 7.8 assumes occupancy is inferable from the meter.

    That assumption only holds if heating actually follows occupancy. This arm
    is therefore a check on the premise of week 3's privacy tests as much as
    on the energy fit: if ungating heating changed nothing, there would be no
    occupancy signal in the meter to attack.
    """
    rec = json.loads(ARTEFACT.read_text(encoding="utf-8"))
    ungated = next(
        a for a in rec["arms"] if a["arm"] == "no_occupancy_gated_heating"
    )
    assert ungated["verdict"] == "DEGRADED_AS_PREDICTED", (
        "ungating heating from occupancy changed nothing measurable, which "
        "would mean the meter carries no occupancy signal and design 7.8's "
        "threat model has nothing to find"
    )
