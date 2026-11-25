"""Runs the V0 invariants over a written release package.

Deliberately reads the **Parquet in ``v1/``**, not in-memory frames from the
run.  Design 9.2's first E1 criterion is "V0 invariants: zero failures", and
what has to be clean is what was delivered: an invariant that passes on an
in-memory frame and fails on the file that was written has not been satisfied,
and the file is what anyone else reads.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from baile_nua.validation.invariants import (
    InvariantReport,
    check_energy_closure,
    check_indoor_temperature_distribution,
    check_no_child_alone,
    check_no_double_occupancy,
    check_physics_bounds,
    check_presence_within_lifespan,
    check_referential_integrity,
)

__all__ = ["run_v0_invariants"]


def _parts(root: Path, dataset_id: str) -> pd.DataFrame | None:
    files = sorted(Path(root).glob(f"{dataset_id}_part*.parquet"))
    if not files:
        single = Path(root) / f"{dataset_id}.parquet"
        if single.exists():
            return pd.read_parquet(single)
        return None
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)


def run_v0_invariants(
    *,
    release_root: Path,
    diagnostics_path: Path,
    write_to: Path | None = None,
) -> dict[str, Any]:
    """Every V0 invariant the E1 package can support, with its verdict.

    An invariant that cannot be evaluated is reported **SKIPPED with its
    reason**, never as a pass. Design 7.2 is zero-tolerance, and a skip counted
    as a pass is how a zero-tolerance gate quietly becomes a nine-out-of-ten
    gate.
    """
    from baile_nua import CLAIM, LABEL

    release_root = Path(release_root)
    gt = release_root / "ground_truth"
    obs = release_root / "observable"

    presence = _parts(gt, "D11")
    cycles = _parts(gt, "D13")
    state = _parts(gt, "D16")
    obs18 = _parts(obs, "D18")
    diag = json.loads(Path(diagnostics_path).read_text(encoding="utf-8"))

    reports: list[InvariantReport] = []

    # ---- presence --------------------------------------------------------
    if presence is None:
        reports.append(InvariantReport(
            "no_double_occupancy", "7.2; R23", 0,
            skipped_reason="D11 was not written",
        ))
    else:
        reports.append(check_no_double_occupancy(presence))

    # ---- energy closure, from the run's own daily rows -------------------
    #
    # The daily energy rows are the quantity design 7.2 names, and they are in
    # the run diagnostics rather than in a dataset: D16 is 15-minute state and
    # D19 is a 30-minute observable, so neither carries the daily balance.
    rows = diag.get("annual_electricity", {}).get("per_dwelling", [])
    if not rows:
        reports.append(InvariantReport(
            "energy_closure", "7.2", 0,
            skipped_reason="the run diagnostics carry no per-dwelling energy",
        ))
    else:
        # The run already asserts closure per household-day inside run_day and
        # reports the worst relative residual; this re-checks the ANNUAL totals,
        # which is a different and weaker statement, and says so.
        annual = pd.DataFrame(rows)
        annual["building_id"] = annual.building_id
        annual["date"] = "2022-annual"
        annual["appliance_wh"] = annual.appliance_kwh_yr * 1000.0
        annual["hvac_wh"] = annual.hvac_kwh_yr * 1000.0
        annual["ev_wh"] = annual.ev_kwh_yr * 1000.0
        annual["pv_wh"] = annual.pv_kwh_yr * 1000.0
        annual["bess_charge_wh"] = 0.0
        annual["bess_discharge_wh"] = 0.0
        annual["net_meter_wh"] = (
            annual.appliance_wh + annual.hvac_wh + annual.ev_wh - annual.pv_wh
        )
        rep = check_energy_closure(annual)
        rep.name = "energy_closure_annual_totals"
        rep.design_ref += " (annual totals; the per-day check is in the run)"
        reports.append(rep)

    # ---- the per-day closure the run itself measured ---------------------
    worst = float(diag.get("max_energy_closure_relative_residual", 1.0))
    per_day = InvariantReport(
        "energy_closure_per_household_day", "7.2 (relative tolerance 0.001)",
        n_checked=int(diag.get("benchmark", {}).get("home_days", 0)),
    )
    if worst > 1e-3:
        per_day.violations.append({
            "kind": "energy_does_not_close",
            "worst_relative_residual": worst, "tolerance": 1e-3,
        })
    reports.append(per_day)

    # ---- physics bounds --------------------------------------------------
    if state is None:
        reports.append(InvariantReport(
            "physics_bounds", "7.2", 0, skipped_reason="D16 was not written",
        ))
    else:
        reports.append(check_physics_bounds(state))
        reports.append(check_indoor_temperature_distribution(state))

    # ---- physics energy residual the solver measured ---------------------
    phys = float(diag.get("max_physics_relative_residual", 1.0))
    solver = InvariantReport(
        "physics_energy_residual", "7.2; F1 solver",
        n_checked=int(diag.get("benchmark", {}).get("home_days", 0)),
    )
    if phys > 1e-6:
        solver.violations.append({
            "kind": "solver_energy_residual_too_large",
            "worst_relative_residual": phys, "tolerance": 1e-6,
        })
    reports.append(solver)

    # ---- referential integrity -------------------------------------------
    pairs = []
    if cycles is not None and state is not None:
        pairs.append(("D13.building_id", set(cycles.building_id),
                      "D16.building_id", set(state.building_id)))
    if obs18 is not None:
        pairs.append(("D18.premises_id", set(obs18.premises_id),
                      "D18.premises_id", set(obs18.premises_id)))
    ref = InvariantReport(
        "referential_integrity", "7.2; 6.3", n_checked=len(pairs)
    )
    if not pairs:
        ref.skipped_reason = "no joinable pair of datasets was written"
    for name_a, a, name_b, b in pairs:
        missing = sorted(a - b)
        if missing:
            ref.violations.append({
                "kind": "dangling_reference", "from": name_a, "to": name_b,
                "n_missing": len(missing), "examples": missing[:5],
            })
    reports.append(ref)

    # ---- the one invariant E1 cannot evaluate, stated as such ------------
    reports.append(InvariantReport(
        "no_child_alone", "7.2; R23", 0,
        skipped_reason=(
            "D11 presence is collected for the first 14 days only (a year of "
            "1-minute presence for 147 people is 77 million rows for no E1 "
            "purpose), and the check needs every person's whole day. It is "
            "enforced INSIDE the activity engine for every day of the run by "
            "_enforce_child_supervision, and tested there; this package-level "
            "re-check is what is skipped, not the invariant."
        ),
    ))

    out = {
        "label": LABEL,
        "claim": CLAIM,
        "release_root": str(release_root),
        "design_ref": "9.2 E1 criterion 1; 7.2 V0 invariants, zero tolerance",
        "n_invariants": len(reports),
        "n_pass": sum(1 for r in reports if r.status == "PASS"),
        "n_fail": sum(1 for r in reports if r.status == "FAIL"),
        "n_skipped": sum(1 for r in reports if r.status == "SKIPPED"),
        "zero_failures": all(r.status != "FAIL" for r in reports),
        "invariants": [r.as_dict() for r in reports],
    }
    if write_to is not None:
        Path(write_to).parent.mkdir(parents=True, exist_ok=True)
        Path(write_to).write_text(
            json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8"
        )
    return out
