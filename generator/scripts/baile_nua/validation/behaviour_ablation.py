"""Week 2 step 4: WP4 behaviour depth, with ablations.

r4 section 9.4's acceptance for this step is three words - *"ablations degrade
fit as expected"* - and the last two carry the weight. An ablation that merely
changes the answer proves nothing: a model can be perturbed in a hundred ways
that move a number. What has to be shown is that removing a mechanism makes the
model fit **published Irish data** worse, in the direction the mechanism's
purpose predicts.

So every arm declares, before it runs, which metric it expects to degrade and
why. Three outcomes are then possible and all three are informative:

``DEGRADED_AS_PREDICTED``
    The mechanism earns its place.
``NO_EFFECT``
    The mechanism is inert on every metric. That is a finding about the
    mechanism, not a passing grade - a mechanism that changes nothing
    measurable is either wrongly wired or not worth its complexity.
``IMPROVED``
    Removing it made the fit **better**. The strongest possible finding, and
    the one most likely to be buried by an ablation suite that only checks for
    movement.

The metrics are fit to published references, never to the model's own previous
output
--------------------------------------------------------------------------------
Every number below is a comparison against a declared Irish source:

=========================  ====================================================
metric                     reference
=========================  ====================================================
``gas_meter_ratio``        DBERNG01, dwelling type x BER band
``ber_spread_pct``         DBERNG01's measured 4 to 7% spread across BER bands
``load_factor``            ESB Networks LP1, urban domestic 24-hour
``overnight_taper``        LP1's 1.72 fall from midnight to 04:00
``peak_hour_error``        LP1's mean-day peak at 18:00
``indoor_temp_c``          PL-TEMP-01's declared band (the one unsourced one)
=========================  ====================================================

Using the model's own baseline as the reference would make every ablation
"degrade fit" by construction, which is the trap this file is written to avoid.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import ClassVar, Any

import numpy as np
import pandas as pd

__all__ = [
    "BehaviourSwitches",
    "ABLATION_ARMS",
    "FIT_METRICS",
    "arm_switches",
    "measure_fit",
    "classify",
    "compare_matrix",
]


@dataclasses.dataclass(frozen=True)
class BehaviourSwitches:
    """Which behaviour mechanisms are engaged. All on is the delivered model."""

    #: U22. Rebound in efficient homes, prebound in poor ones.
    comfort_taking: bool = True
    #: Per-person sleep and activity timing offsets. Off means every person
    #: shares one schedule, which should sharpen the aggregate peak.
    chronotype: bool = True
    #: Person-to-person variation in how strongly routine binds. Off means one
    #: fixed habit strength for everyone, so durations vary less between
    #: people and more within them.
    habit_variation: bool = True
    #: Heating is available only when somebody is home. Off means the timer
    #: runs regardless, which is what a model with no occupancy coupling does
    #: and what design 7.8's privacy work assumes is NOT the case.
    occupancy_gated_heating: bool = True
    #: I-052, week 3 step 3. Whether the activity PLACEMENT weight multiplies
    #: HETUS's participation curve by each activity's daily duration target.
    #:
    #: It used to, and that was a double count: a participation rate already
    #: embeds how prevalent an activity is and how long it lasts, so weighting
    #: by the daily total again gave every long activity a standing advantage
    #: at every minute. The daily totals are governed by the budget, which is
    #: drawn around the HETUS target and decremented per episode, so the
    #: placement weight only has to say WHEN.
    #:
    #: ``False`` is the delivered model: timings come from the participation
    #: curves alone. ``True`` restores the old weight, as an ablation arm, so
    #: the change can be MEASURED against LP1 rather than argued for.
    duration_weighted_timing: bool = False

    def as_dict(self) -> dict[str, bool]:
        return dataclasses.asdict(self)

    #: Switches whose DELIVERED value is False, so `all_on` must not require
    #: them. `duration_weighted_timing` is an ablation that restores a
    #: superseded behaviour rather than a mechanism that can be turned off.
    #: ClassVar, not a field: as a field it appeared in `as_dict()` and would
    #: have been written into every ablation artefact as a switch.
    _DELIVERED_FALSE: ClassVar[tuple[str, ...]] = ("duration_weighted_timing",)

    @property
    def all_on(self) -> bool:
        d = dataclasses.asdict(self)
        return (all(v for k, v in d.items() if k not in self._DELIVERED_FALSE)
                and not any(d[k] for k in self._DELIVERED_FALSE if k in d))


#: What each arm turns off, and what it must degrade to earn its mechanism.
#:
#: `expects` names metrics and the direction the FIT should move in. "worse"
#: is defined per metric in :data:`FIT_METRICS`, against the published
#: reference - never against the baseline arm.
ABLATION_ARMS: tuple[dict[str, Any], ...] = (
    {
        "arm": "full",
        "off": (),
        "expects": (),
        "why": "The delivered model. Every other arm is read against this.",
    },
    {
        "arm": "no_comfort_taking",
        "off": ("comfort_taking",),
        "expects": ("ber_spread_pct", "gas_meter_ratio"),
        "why": (
            "U22's purpose is to flatten simulated gas across the fabric "
            "range towards DBERNG01's measured 4 to 7%. Without it the spread "
            "should widen and the old-stock overshoot should grow."
        ),
    },
    {
        "arm": "no_chronotype",
        "off": ("chronotype",),
        "expects": ("load_factor", "overnight_taper"),
        "why": (
            "Chronotype is what stops the town acting as one household. "
            "Without it every person wakes, sleeps and cooks on the same "
            "schedule, so the aggregate peak should sharpen - a LOWER load "
            "factor than LP1's - and the overnight taper should steepen "
            "unnaturally because everyone goes to bed at once."
        ),
    },
    {
        "arm": "no_habit_variation",
        "off": ("habit_variation",),
        "expects": ("load_factor",),
        "why": (
            "Habit strength sets how tightly each person's durations cluster. "
            "One fixed value for everyone removes a source of between-person "
            "diversity, so the aggregate should be slightly peakier. Expected "
            "to be the weakest of the four, and declared as such rather than "
            "discovered."
        ),
    },
    {
        "arm": "no_occupancy_gated_heating",
        "off": ("occupancy_gated_heating",),
        "expects": ("gas_meter_ratio", "load_factor"),
        "why": (
            "Heating an empty house is both more gas and a flatter profile. "
            "This is also the mechanism design 7.8's privacy work depends on: "
            "if heating did not follow occupancy, occupancy would not be "
            "inferable from the meter, and the whole threat model would be "
            "moot. So this arm is a check on the premise of week 3's privacy "
            "tests as much as on the energy fit."
        ),
    },
)


#: How each metric's fit is scored against its published reference. ``worse``
#: returns True when the arm's value fits the reference LESS well than the
#: baseline's does.
FIT_METRICS: dict[str, dict[str, Any]] = {
    "gas_meter_ratio": {
        "reference": 1.0,
        "source": "cso.gas.dberng01_by_dwelling_ber",
        "note": "simulated meter gas over the published cell; 1.0 is perfect",
    },
    "ber_spread_pct": {
        "reference": 5.5,
        "source": "cso.gas.dberng01_by_dwelling_ber",
        "note": "DBERNG01's 4 to 7% spread across BER bands; midpoint taken",
    },
    "load_factor": {
        "reference": 0.412955,
        "source": "esbn.rmds.slp_indexes_2022",
        "note": "LP1 urban domestic 24-hour",
    },
    "overnight_taper": {
        "reference": 1.721,
        "source": "esbn.rmds.slp_indexes_2022",
        "note": "LP1's midnight-to-04:00 fall",
    },
    "peak_hour_error": {
        "reference": 0.0,
        "source": "esbn.rmds.slp_indexes_2022",
        "note": "hours away from LP1's mean-day peak at 18:00; 0 is perfect",
    },
    "indoor_temp_c": {
        "reference": 19.0,
        "source": "declared band (PL-TEMP-01, unsourced - I-032)",
        "note": "mid-band; the one metric here with no published reference",
    },
}


def arm_switches(arm: str) -> BehaviourSwitches:
    """The switch set for a named arm."""
    spec = next((a for a in ABLATION_ARMS if a["arm"] == arm), None)
    if spec is None:
        raise ValueError(
            f"unknown arm {arm!r}; declared arms are "
            f"{[a['arm'] for a in ABLATION_ARMS]}"
        )
    return BehaviourSwitches(**{name: False for name in spec["off"]})


def measure_fit(diagnostics: dict[str, Any]) -> dict[str, Any]:
    """The six fit metrics, from one arm's diagnostics."""
    rows = diagnostics.get("annual_electricity", {}).get("per_dwelling") or []
    if not rows:
        raise LookupError("the arm's diagnostics carry no per-dwelling rows")
    frame = pd.DataFrame(rows)
    gas = frame[frame.heating_fuel == "natural gas"] \
        if "heating_fuel" in frame.columns else frame
    out: dict[str, Any] = {}

    if "meter_gas_kwh_yr" in gas.columns:
        paired = gas.dropna(subset=["meter_gas_kwh_yr", "d24_gas_target_kwh_yr"])
        if len(paired):
            out["gas_meter_ratio"] = round(float(
                (paired.meter_gas_kwh_yr / paired.d24_gas_target_kwh_yr).mean()
            ), 4)
        # Spread of meter gas across BER bands, between-band means only.
        means = paired.groupby("ber_group").meter_gas_kwh_yr.mean()
        counts = paired.groupby("ber_group").meter_gas_kwh_yr.size()
        means = means.loc[means.index.intersection(counts[counts >= 2].index)]
        if len(means) >= 2 and means.min() > 0:
            out["ber_spread_pct"] = round(
                float((means.max() / means.min() - 1.0) * 100.0), 1
            )
    if "temp_living_mean_c" in frame.columns:
        out["indoor_temp_c"] = round(float(frame.temp_living_mean_c.mean()), 2)

    # From the run's own feeder shape, not from a written package: an
    # ablation arm writes none, and the acceptance criterion needs the fit to
    # be measurable without one.
    shape = diagnostics.get("feeder_shape") or {}
    if shape.get("measured"):
        out["load_factor"] = shape["load_factor"]
        if shape.get("overnight_taper_00_over_04") is not None:
            out["overnight_taper"] = shape["overnight_taper_00_over_04"]
        out["peak_hour_error"] = abs(int(shape["mean_day_peak_hour"]) - 18)
    return out


def classify(
    arm: dict[str, Any], baseline: dict[str, Any], measured: dict[str, Any]
) -> dict[str, Any]:
    """Did this arm degrade what it said it would?

    Fit is distance from the published reference. An arm degrades a metric
    when its distance is larger than the baseline's.
    """
    results: dict[str, Any] = {}
    for metric in arm["expects"]:
        if metric not in measured or metric not in baseline:
            results[metric] = {"evaluable": False, "reason": "not measured"}
            continue
        ref = float(FIT_METRICS[metric]["reference"])
        d_base = abs(float(baseline[metric]) - ref)
        d_arm = abs(float(measured[metric]) - ref)
        results[metric] = {
            "evaluable": True,
            "reference": ref,
            "baseline": baseline[metric],
            "arm": measured[metric],
            "baseline_distance": round(d_base, 4),
            "arm_distance": round(d_arm, 4),
            "degraded": bool(d_arm > d_base),
            "improved": bool(d_arm < d_base),
        }
    evaluable = [r for r in results.values() if r.get("evaluable")]
    any_degraded = any(r["degraded"] for r in evaluable)
    any_improved = any(r["improved"] for r in evaluable)
    verdict = (
        "DEGRADED_AS_PREDICTED" if any_degraded
        else "IMPROVED" if any_improved
        else "NO_EFFECT"
    )
    return {
        "arm": arm["arm"],
        "turned_off": list(arm["off"]),
        "expected_to_degrade": list(arm["expects"]),
        "why": arm["why"],
        "metrics": results,
        "verdict": verdict,
        "verdict_note": {
            "DEGRADED_AS_PREDICTED": "the mechanism earns its place",
            "NO_EFFECT": (
                "the mechanism is inert on every metric it was expected to "
                "affect. A finding about the mechanism, not a pass: it is "
                "either wrongly wired or not worth its complexity."
            ),
            "IMPROVED": (
                "removing the mechanism made the fit BETTER. The strongest "
                "finding available here and the one an ablation suite that "
                "only checked for movement would have hidden."
            ),
        }[verdict],
    }


def compare_matrix(arms: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Assemble the matrix. ``arms`` maps arm name to its diagnostics."""
    from baile_nua import CLAIM, LABEL

    if "full" not in arms:
        raise ValueError(
            "the matrix needs the 'full' arm as its baseline; every other "
            "arm is read against it"
        )
    fits = {name: measure_fit(d) for name, d in arms.items()}
    baseline = fits["full"]
    classified = [
        classify(spec, baseline, fits[spec["arm"]])
        for spec in ABLATION_ARMS
        if spec["arm"] in fits and spec["expects"]
    ]
    return {
        "label": LABEL,
        "claim": CLAIM,
        "step": "week 2 step 4 (WP4 behaviour depth)",
        "design_ref": "r4 9.4: ablations degrade fit as expected",
        "what_fit_means": (
            "Distance from a PUBLISHED reference, never from this model's own "
            "baseline. Scoring against the baseline would make every ablation "
            "degrade fit by construction."
        ),
        "metrics": {k: dict(v) for k, v in FIT_METRICS.items()},
        "fits": fits,
        "arms": classified,
        "n_degraded_as_predicted": sum(
            1 for c in classified if c["verdict"] == "DEGRADED_AS_PREDICTED"
        ),
        "n_no_effect": sum(1 for c in classified if c["verdict"] == "NO_EFFECT"),
        "n_improved": sum(1 for c in classified if c["verdict"] == "IMPROVED"),
        "acceptance_met": all(
            c["verdict"] == "DEGRADED_AS_PREDICTED" for c in classified
        ),
    }
