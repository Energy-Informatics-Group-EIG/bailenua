"""U22: the comfort-taking ablation, and the measurement it exists to make.

A mechanism that has only ever been run switched on has not been tested. This
module runs the mixed-age slice twice - comfort-taking off and on - and
measures the two things U22 names:

**The calibration axis, DBERNG01.** Measured gas varies only **4 to 7%** across
BER bands within a dwelling type, and A-B rated detached houses burn **more**
gas than F-G ones. A fixed-setpoint model cannot do that: halve the heat loss
and the space heat halves. So the question is whether the simulated spread
across the fabric range collapses towards the published flatness when the
mechanism is on.

**The held-out axis, DBERNG02.** U22's condition: *"the space-heat ratio
gradient (0.43 for 1967-99, 0.19 for post-2005 at E1) must shrink once hot
water, gas cooking and boiler losses are in."* DBERNG02 is dwelling type by
period of construction, declared held-out, and nothing in the mechanism is
allowed to see it. Design 7.1 requires the separation.

Why the mixed-age slice and not the E1 estate
---------------------------------------------
The E1 estate is 84% A or B rated with a mean build year of 2005, and its
construction-period cells hold **four dwellings each**. A gradient measured on
four homes against four homes is noise, and reporting one would be worse than
reporting nothing. The U23/U29 mixed-age slice exists for this: 60 homes
spanning 1868 to 1995, 86.7% pre-1980, all seven BER letters.

What the ablation cannot show
-----------------------------
That the mechanism is *right*. It can show that the mechanism moves the model
towards the published data on an axis it was set against, and towards or away
from it on an axis it has never seen. The second is the one worth reading.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

__all__ = [
    "ABLATION_ARMS",
    "run_arm",
    "compare",
    "write_ablation",
]

#: The two arms, and nothing else: U22 asks whether comfort-taking earns its
#: place, which is a question about its presence and absence.
ABLATION_ARMS = ("off", "on")


def run_arm(
    arm: str,
    *,
    out_root: Path,
    master_seed: int = 20261008,
    days: int | None = None,
    slice_kind: str = "u23_mixed_age",
    strength: float = 1.0,
    frozen_household_ids: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """One arm. No package is written: an ablation wants the diagnostics.

    ``strength`` scales the declared comfort-taking amplitudes, for the
    calibration sweep against DBERNG01. It exists because the question "is the
    mechanism strong enough" cannot be answered by running it at one strength,
    and because the answer turned out to be bounded by something other than
    the data: see the indoor-temperature floor in the artefact.
    """
    from baile_nua.engine.e1_run import run_year

    if arm not in ABLATION_ARMS:
        raise ValueError(f"unknown arm {arm!r}; expected one of {ABLATION_ARMS}")
    root = Path(out_root) / arm
    root.mkdir(parents=True, exist_ok=True)
    return run_year(
        master_seed=master_seed,
        out_root=root,
        checkpoint_root=root / "checkpoints",
        days=days,
        collect_presence_days=0,
        slice_kind=slice_kind,
        comfort_taking=(arm == "on"),
        comfort_strength=float(strength),
        write_package=False,
        frozen_household_ids=frozen_household_ids,
    )


def _frame(diagnostics: dict[str, Any]) -> pd.DataFrame:
    rows = diagnostics.get("annual_electricity", {}).get("per_dwelling")
    if not rows:
        raise LookupError("the arm's diagnostics carry no per-dwelling rows")
    return pd.DataFrame(rows)


def _spread_across(frame: pd.DataFrame, by: str, value: str) -> dict[str, Any]:
    """Relative spread of a quantity across the levels of one axis.

    Reported as max/min and as a percentage, because DBERNG01's own figure is
    quoted as a percentage spread ("only 4 to 7% across BER bands").

    Means are taken per level and then compared. A pooled standard deviation
    would mix the spread BETWEEN bands - the quantity of interest - with the
    spread within them, which is dwelling size and is supposed to be large.
    """
    sub = frame.dropna(subset=[by, value])
    if sub.empty:
        return {"evaluable": False, "reason": f"no rows with {by} and {value}"}
    means = sub.groupby(by)[value].mean()
    counts = sub.groupby(by)[value].size()
    # Levels with one dwelling are not a level; they are one dwelling.
    keep = counts[counts >= 2].index
    means = means.loc[means.index.intersection(keep)]
    if len(means) < 2:
        return {
            "evaluable": False,
            "reason": f"fewer than two levels of {by} with at least 2 dwellings",
            "counts": {str(k): int(v) for k, v in counts.items()},
        }
    lo, hi = float(means.min()), float(means.max())
    return {
        "evaluable": True,
        "levels": {str(k): round(float(v), 1) for k, v in means.items()},
        "counts": {str(k): int(counts[k]) for k in means.index},
        "min": round(lo, 1),
        "max": round(hi, 1),
        "max_over_min": round(hi / lo, 4) if lo > 0 else None,
        "spread_pct": round((hi / lo - 1.0) * 100.0, 1) if lo > 0 else None,
    }


def _gradient(frame: pd.DataFrame) -> dict[str, Any]:
    """The held-out construction-period ratio, oldest against newest."""
    sub = frame.dropna(subset=["year_built_band"])
    if "meter_gas_kwh_yr" not in sub.columns:
        return {"evaluable": False, "reason": "no meter gas figure"}
    sub = sub.dropna(subset=["meter_gas_kwh_yr", "d24_gas_target_kwh_yr"])
    if sub.empty:
        return {"evaluable": False, "reason": "no gas dwellings with a target"}
    sub = sub.assign(ratio=sub.meter_gas_kwh_yr / sub.d24_gas_target_kwh_yr)
    means = sub.groupby("year_built_band").ratio.mean()
    counts = sub.groupby("year_built_band").ratio.size()
    keep = counts[counts >= 2].index
    means = means.loc[means.index.intersection(keep)]
    if len(means) < 2:
        return {
            "evaluable": False,
            "reason": "fewer than two construction bands with 2+ dwellings",
            "counts": {str(k): int(v) for k, v in counts.items()},
        }
    order = sorted(means.index)
    oldest, newest = order[0], order[-1]
    return {
        "evaluable": True,
        "by_band": {str(k): round(float(v), 4) for k, v in means.items()},
        "counts": {str(k): int(counts[k]) for k in means.index},
        "oldest_band": str(oldest),
        "newest_band": str(newest),
        "oldest_ratio": round(float(means[oldest]), 4),
        "newest_ratio": round(float(means[newest]), 4),
        "gradient_oldest_over_newest": (
            round(float(means[oldest] / means[newest]), 4)
            if means[newest] > 0 else None
        ),
    }


def compare(off: dict[str, Any], on: dict[str, Any]) -> dict[str, Any]:
    """The measurement. Reports what moved and in which direction."""
    from baile_nua import CLAIM, LABEL

    f_off, f_on = _frame(off), _frame(on)
    out: dict[str, Any] = {
        "label": LABEL,
        "claim": CLAIM,
        "decision": "U22",
        "design_ref": "D-022; 7.1 (calibration and validation disjoint); 5.3 COM-B",
        "question": (
            "Does comfort-taking move simulated gas towards the published "
            "flatness across the fabric range, and what does it do to the "
            "held-out construction-period gradient?"
        ),
        "slice": {
            "n_homes": int(on.get("slice", {}).get("n_homes", len(f_on))),
            "n_people": int(on.get("slice", {}).get("n_people", 0)),
            "why_this_slice": (
                "The E1 estate is 84% A/B rated with four dwellings per "
                "construction-period cell. A gradient on four against four is "
                "noise. The U23/U29 mixed-age slice spans 1868 to 1995 with "
                "all seven BER letters."
            ),
        },
        "arms": {},
        "moved": {},
    }

    for name, frame in (("off", f_off), ("on", f_on)):
        gas = frame[frame.heating_fuel == "natural gas"] \
            if "heating_fuel" in frame.columns else frame
        out["arms"][name] = {
            "n_dwellings": int(len(frame)),
            "n_gas": int(len(gas)),
            "mean_space_heat_kwh_yr": round(
                float(frame.space_heat_kwh_yr.mean()), 1
            ),
            "mean_space_heat_kwh_m2_yr": round(
                float(frame.space_heat_kwh_m2_yr.mean()), 1
            ),
            "mean_indoor_temp_c": (
                round(float(frame.temp_living_mean_c.mean()), 2)
                if "temp_living_mean_c" in frame.columns else None
            ),
            # The calibration axis: spread of space heat per m2 across BER.
            "space_heat_per_m2_across_ber": _spread_across(
                frame, "ber_group", "space_heat_kwh_m2_yr"
            ),
            "gas_meter_across_ber": _spread_across(
                gas, "ber_group", "meter_gas_kwh_yr"
            ),
            # The held-out axis.
            "heldout_construction_gradient": _gradient(gas),
        }

    a, b = out["arms"]["off"], out["arms"]["on"]

    def _delta(path: str, key: str) -> dict[str, Any]:
        x, y = a[path], b[path]
        if not (x.get("evaluable") and y.get("evaluable")):
            return {"evaluable": False}
        return {
            "evaluable": True,
            "off": x.get(key), "on": y.get(key),
            "change": (
                round(y[key] - x[key], 4)
                if x.get(key) is not None and y.get(key) is not None else None
            ),
        }

    out["moved"] = {
        "ber_spread_pct_space_heat_per_m2": _delta(
            "space_heat_per_m2_across_ber", "spread_pct"
        ),
        "ber_spread_pct_gas_meter": _delta("gas_meter_across_ber", "spread_pct"),
        "heldout_gradient": _delta(
            "heldout_construction_gradient", "gradient_oldest_over_newest"
        ),
        "mean_space_heat_kwh_yr": {
            "off": a["mean_space_heat_kwh_yr"],
            "on": b["mean_space_heat_kwh_yr"],
            "change_pct": round(
                (b["mean_space_heat_kwh_yr"] / a["mean_space_heat_kwh_yr"] - 1)
                * 100.0, 2
            ) if a["mean_space_heat_kwh_yr"] else None,
        },
    }
    out["reference"] = {
        "dberng01_ber_spread_pct": "4 to 7 within every dwelling type",
        "dberng01_inversion": (
            "A-B detached 14,618 kWh against F-G 13,292 - the better band "
            "burns MORE"
        ),
        "dberng01_dwelling_type_spread_pct": 84,
        "e1_heldout_gradient": (
            "0.43 for 1967-99 against 0.19 for post-2005, measured on space "
            "heat alone with no boiler efficiency"
        ),
        "sources": [
            "cso.gas.dberng01_by_dwelling_ber (calibration axis)",
            "cso.gas.dberng02_by_dwelling_construction (held out)",
        ],
    }
    return out


def write_ablation(
    *, work_root: Path, out_path: Path, days: int | None = None,
    master_seed: int = 20261008, progress: Any = None,
) -> dict[str, Any]:
    """Run both arms and write the comparison."""
    arms: dict[str, dict[str, Any]] = {}
    for arm in ABLATION_ARMS:
        if progress:
            progress(f"ablation arm {arm}")
        arms[arm] = run_arm(
            arm, out_root=work_root, master_seed=master_seed, days=days
        )
    rec = compare(arms["off"], arms["on"])
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rec, indent=2, sort_keys=True, default=str) + "\n",
                   encoding="utf-8")
    return rec
