"""U31: the held-out gas gradient, run from the repository rather than a script.

The U31 artefact in `v1/evidence/heldout_u31.json` was produced by a driver that
lived only in a scratchpad directory. The statistics were in the repository —
`validation.ablation.run_arm` does the simulation — but the thin driver that
called it, and the code that computed the gradient and wrote the artefact, were
not. A committed evidence artefact that cannot be regenerated from the
repository is not reproducible, whatever its contents say.

So this module is that driver, moved in unchanged in its statistics: the same
paired `ttest_rel` by dwelling within each construction group, the same Welch
`ttest_ind` for the residual gap between groups, the same gradient definition
(mean old ratio over mean new ratio). Re-running U31 must not quietly become a
different test.

**U31 is evaluation-only.** Nothing is fitted on it. The slice is compared
against DBERNG02 (dwelling type x period of construction), which is declared
held out at exposure `none`, while the mechanisms were set against DBERNG01
(dwelling type x BER band). After week 3 the fabric is additionally derived
from SEAI's BER Research Tool, which is tuning-exposed for fabric (I-058), so
this axis is the only independent evidence that a fabric change is an
improvement rather than a re-parameterisation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from baile_nua.engine.slice_u31 import construction_group

__all__ = ["run_arms", "load_arm", "gradient_report", "GROUPS",
           "U31MembershipError"]


class U31MembershipError(RuntimeError):
    """The two arms are not the same sample, so no paired test is possible."""


def _direction(mean_change: float) -> str:
    """"down", "up", or "undetermined" - never a direction for a NaN.

    `"down" if x < 0 else "up"` reports "up" for a NaN, because `nan < 0` is
    False. That turned an unmeasurable result into the predicted one.
    """
    import math

    if mean_change is None or math.isnan(float(mean_change)):
        return "undetermined"
    return "down" if float(mean_change) < 0 else "up"

GROUPS: tuple[str, ...] = ("old", "new")


def run_arms(
    *, out_root: Path, arms: tuple[str, ...] = ("off", "on"),
) -> dict[str, Path]:
    """Simulate the held-out slice with comfort-taking off and on."""
    from baile_nua.validation.ablation import run_arm

    written: dict[str, Path] = {}
    for arm in arms:
        diag = run_arm(arm, out_root=out_root, slice_kind="u31_heldout")
        path = out_root / arm / "diagnostics.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(diag, indent=2, default=str))
        written[arm] = path
    return written


def load_arm(root: Path, arm: str) -> tuple[dict[str, Any], pd.DataFrame]:
    """One arm's diagnostics and its gas-heated per-dwelling frame."""
    doc = json.loads((root / arm / "diagnostics.json").read_text())
    frame = pd.DataFrame(doc["annual_electricity"]["per_dwelling"])
    frame["grp"] = frame.build_year.map(construction_group)
    gas = frame[
        (frame.heating_fuel == "natural gas") & frame.meter_gas_kwh_yr.notna()
    ].copy()
    gas["ratio"] = gas.meter_gas_kwh_yr / gas.d24_gas_target_kwh_yr
    return doc, gas


def gradient_report(root: Path) -> dict[str, Any]:
    """The gradient, the paired within-group tests and the residual gap.

    Identical in statistics to the version that produced the first U31
    artefact.
    """
    doc_off, off = load_arm(root, "off")
    doc_on, on = load_arm(root, "on")
    joined = off.set_index("building_id")[["grp", "ratio"]].join(
        on.set_index("building_id")[["grp", "ratio"]],
        lsuffix="_off", rsuffix="_on",
    )
    rec: dict[str, Any] = {"groups": {}, "paired_by_dwelling": {}}
    for group in GROUPS:
        s_off = off[off.grp == group]
        s_on = on[on.grp == group]
        rec["groups"][group] = {
            "n": int(len(s_off)),
            "build_years": [int(s_off.build_year.min()),
                            int(s_off.build_year.max())],
            "mean_floor_area_m2": round(float(s_off.floor_area_m2.mean()), 1),
            "mean_published_cell_kwh_yr": round(
                float(s_off.d24_gas_target_kwh_yr.mean()), 0),
            "off": _arm_block(s_off),
            "on": _arm_block(s_on),
        }
        sub = joined[joined.grp_off == group]
        delta = sub.ratio_on - sub.ratio_off
        # A paired test needs both arms present for every dwelling. If the
        # join left any NaN, the two arms are not the same sample and the
        # paired statistic is meaningless - so say so rather than returning
        # NaN, which the direction test below would silently read as "up".
        #
        # This is not hypothetical. Week 3's fabric change moved every
        # dwelling's specific heat loss, the U31 selector CONTRASTS on
        # specific heat loss (D-052), and only 20 of 60 dwellings survived
        # into the new selection. The paired p came back NaN and a
        # `nan < 0` comparison reported the predicted direction for a group
        # whose ratio had in fact moved the other way.
        n_missing = int(delta.isna().sum())
        if n_missing:
            raise U31MembershipError(
                f"group {group!r}: {n_missing} of {len(sub)} dwellings are "
                f"present in only one arm, so no paired test is possible. "
                f"The two arms are different samples. Freeze the selection "
                f"with `frozen_household_ids` to compare like with like."
            )
        t, p = stats.ttest_rel(sub.ratio_on, sub.ratio_off)
        rec["paired_by_dwelling"][group] = {
            "mean_change_in_ratio": round(float(delta.mean()), 4),
            "ci95": [round(float(delta.mean() - 1.96 * delta.sem()), 4),
                     round(float(delta.mean() + 1.96 * delta.sem()), 4)],
            "paired_t": round(float(t), 3), "p": float(f"{p:.3e}"),
            "direction_predicted": "down" if group == "old" else "up",
            "direction_observed": _direction(delta.mean()),
        }
    o_off = joined[joined.grp_off == "old"].ratio_off
    n_off = joined[joined.grp_off == "new"].ratio_off
    o_on = joined[joined.grp_off == "old"].ratio_on
    n_on = joined[joined.grp_off == "new"].ratio_on
    gap_off = float(o_off.mean() - n_off.mean())
    gap_on = float(o_on.mean() - n_on.mean())
    t_res, p_res = stats.ttest_ind(o_on, n_on, equal_var=False)
    rec["gradient"] = {
        "definition": "mean(old ratio) / mean(new ratio)",
        "off": round(float(o_off.mean() / n_off.mean()), 4),
        "on": round(float(o_on.mean() / n_on.mean()), 4),
        "shrank": bool(gap_on < gap_off),
        "gap_off": round(gap_off, 4), "gap_on": round(gap_on, 4),
        # Guarded: with no gap in the baseline arm there is no share of it to
        # close, and dividing would raise. Real data has a gap - that is what
        # the slice is selected for - but a degenerate arm should report
        # "undefined" rather than crash the whole report.
        "share_of_gap_closed": (
            round(1.0 - gap_on / gap_off, 4) if abs(gap_off) > 1e-12 else None
        ),
        "residual_gap_still_significant": {
            "t": round(float(t_res), 3), "p": float(f"{p_res:.3e}")},
    }
    rec["slice"] = doc_on["slice"].get("estate_selection")
    rec["evaluation_only"] = True
    rec["per_dwelling"] = {
        arm: frame[["building_id", "grp", "build_year", "ber_band",
                    "floor_area_m2", "space_heat_kwh_yr", "meter_gas_kwh_yr",
                    "d24_gas_target_kwh_yr", "ratio",
                    "temp_living_mean_c"]].to_dict("records")
        for arm, frame in (("off", off), ("on", on))
    }
    return rec


def _arm_block(sub: pd.DataFrame) -> dict[str, Any]:
    return {
        "mean_space_heat_kwh_yr": round(float(sub.space_heat_kwh_yr.mean()), 0),
        "mean_meter_gas_kwh_yr": round(float(sub.meter_gas_kwh_yr.mean()), 0),
        "mean_ratio": round(float(sub.ratio.mean()), 4),
        "mean_indoor_temp_c": round(float(sub.temp_living_mean_c.mean()), 2),
    }
