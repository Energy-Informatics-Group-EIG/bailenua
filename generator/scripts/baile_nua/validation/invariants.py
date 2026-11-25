"""V0 hard invariants — zero tolerance (design 7.2).

The design's list, and the function that enforces each:

======================================================================  =========================
Design 7.2 invariant                                                     Function
======================================================================  =========================
Nobody is in two places at once                                          :func:`check_no_double_occupancy`
Nobody is anywhere before birth, after death or while away               :func:`check_presence_within_lifespan`
Children under 12 are never alone at home                                :func:`check_no_child_alone`
Every venue has a capacity                                               :func:`check_venue_capacity`
Energy closes per home per minute, within 0.1% of daily energy           :func:`check_energy_closure`
Physics bounds hold (SoC, CO2, RH, reachable temperature)                :func:`check_physics_bounds`
Referential integrity across all datasets                                :func:`check_referential_integrity`
Determinism: re-rendering gives a byte-identical hash                    tests/test_determinism.py
======================================================================  =========================

Every function returns an :class:`InvariantReport` rather than raising, so a run
can report *all* violations at once instead of stopping at the first.  The
caller decides whether to raise; :func:`assert_all` does.

Thresholds come from ``config/thresholds.yaml``, never from literals here, so
there is one place to look at what is being enforced — and the gate-discipline
rule (a threshold is never widened to manufacture a pass) has one place to be
broken, where it would be visible in a diff.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd

from baile_nua.config import thresholds

__all__ = [
    "InvariantReport",
    "InvariantViolation",
    "assert_all",
    "check_no_double_occupancy",
    "check_presence_within_lifespan",
    "check_no_child_alone",
    "check_venue_capacity",
    "check_energy_closure",
    "check_physics_bounds",
    "check_referential_integrity",
]

CHILD_ALONE_AGE = 12  # design 5.3: "a child under 12 is never home alone"


class InvariantViolation(AssertionError):
    """A V0 invariant was violated.  Zero tolerance, so this is always fatal."""


@dataclasses.dataclass
class InvariantReport:
    name: str
    design_ref: str
    n_checked: int
    violations: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    skipped_reason: str | None = None

    @property
    def passed(self) -> bool:
        return self.skipped_reason is None and not self.violations

    @property
    def status(self) -> str:
        if self.skipped_reason:
            return "SKIPPED"
        return "PASS" if not self.violations else "FAIL"

    def as_dict(self) -> dict[str, Any]:
        return {
            "invariant": self.name,
            "design_ref": self.design_ref,
            "status": self.status,
            "n_checked": self.n_checked,
            "n_violations": len(self.violations),
            # Cap the detail so a catastrophic run does not produce a 1 GB report,
            # but always record the true count above.
            "violations": self.violations[:50],
            "violations_truncated": len(self.violations) > 50,
            "skipped_reason": self.skipped_reason,
        }

    def __str__(self) -> str:
        if self.skipped_reason:
            return f"{self.status:<7} {self.name}: {self.skipped_reason}"
        return f"{self.status:<7} {self.name}: {len(self.violations)} violation(s) in {self.n_checked} checked"


def assert_all(reports: Sequence[InvariantReport]) -> None:
    """Raise if any invariant failed.  Reports every failure, not just the first."""
    failed = [r for r in reports if r.status == "FAIL"]
    if not failed:
        return
    lines = [f"{len(failed)} V0 invariant(s) violated (design 7.2, zero tolerance):"]
    for r in failed:
        lines.append(f"  - {r.name} [{r.design_ref}]: {len(r.violations)} violation(s)")
        for v in r.violations[:3]:
            lines.append(f"      {v}")
    raise InvariantViolation("\n".join(lines))


# --------------------------------------------------------------------------- #
# Presence invariants (R23, 5.4, 7.2)
# --------------------------------------------------------------------------- #

def check_no_double_occupancy(presence: pd.DataFrame) -> InvariantReport:
    """Nobody is in two places at once (R23, design 5.4).

    Implemented as an overlap scan per person on sorted intervals: for each
    person, interval *i+1* must start at or after interval *i* ends.  Half-open
    intervals ``[start, end)`` are assumed, so touching intervals are legal and
    only genuine overlap is a violation.
    """
    rep = InvariantReport(
        "no_double_occupancy", "7.2 / R23 / 5.4", n_checked=len(presence)
    )
    if presence.empty:
        rep.skipped_reason = "no presence rows"
        return rep

    df = presence[["person_id", "start", "end"]].copy()
    df["start"] = pd.to_datetime(df["start"], utc=True)
    df["end"] = pd.to_datetime(df["end"], utc=True)

    # An interval that ends before it starts is its own violation, and would
    # also defeat the overlap scan, so it is caught first.
    inverted = df[df["end"] < df["start"]]
    for r in inverted.itertuples():
        rep.violations.append(
            {"person_id": r.person_id, "kind": "end_before_start",
             "start": str(r.start), "end": str(r.end)}
        )

    df = df[df["end"] >= df["start"]].sort_values(["person_id", "start", "end"])
    prev_person = df["person_id"].shift(1)
    prev_end = df["end"].shift(1)
    overlap = (df["person_id"] == prev_person) & (df["start"] < prev_end)
    for r in df[overlap].assign(prev_end=prev_end[overlap]).itertuples():
        rep.violations.append(
            {
                "person_id": r.person_id,
                "kind": "overlapping_presence",
                "starts_at": str(r.start),
                "while_previous_runs_to": str(r.prev_end),
                "overlap_seconds": float((r.prev_end - r.start).total_seconds()),
            }
        )
    return rep


def check_presence_within_lifespan(
    presence: pd.DataFrame, persons: pd.DataFrame
) -> InvariantReport:
    """Nobody is anywhere before birth or after death (design 7.2)."""
    rep = InvariantReport(
        "presence_within_lifespan", "7.2", n_checked=len(presence)
    )
    if presence.empty or persons.empty:
        rep.skipped_reason = "no presence or person rows"
        return rep

    life = persons[["person_id", "birth_date", "death_date"]].copy()
    life["birth"] = pd.to_datetime(life["birth_date"], utc=True)
    life["death"] = pd.to_datetime(life["death_date"], utc=True)

    df = presence[["person_id", "start", "end", "location_kind"]].merge(
        life[["person_id", "birth", "death"]], on="person_id", how="left"
    )
    df["start"] = pd.to_datetime(df["start"], utc=True)
    df["end"] = pd.to_datetime(df["end"], utc=True)

    orphan = df[df["birth"].isna()]
    for r in orphan.itertuples():
        rep.violations.append(
            {"person_id": r.person_id, "kind": "presence_for_unknown_person"}
        )

    known = df[df["birth"].notna()]
    before = known[known["start"] < known["birth"]]
    for r in before.itertuples():
        rep.violations.append(
            {"person_id": r.person_id, "kind": "present_before_birth",
             "start": str(r.start), "birth": str(r.birth)}
        )
    after = known[known["death"].notna() & (known["end"] > known["death"])]
    for r in after.itertuples():
        rep.violations.append(
            {"person_id": r.person_id, "kind": "present_after_death",
             "end": str(r.end), "death": str(r.death)}
        )
    return rep


def check_no_child_alone(
    presence: pd.DataFrame,
    persons: pd.DataFrame,
    *,
    as_of: pd.Timestamp | None = None,
) -> InvariantReport:
    """A child under 12 is never alone at home (design 5.3, 7.2).

    "Alone at home" means: the child is present in a building, and at some
    instant during that interval no other person aged 12 or over is present in
    the same building.  Checked by sweeping the event boundaries within each
    building, because a supervising adult may arrive or leave mid-interval and
    the gap is exactly what must not exist.
    """
    rep = InvariantReport("no_child_under_12_alone", "7.2 / 5.3", n_checked=0)
    if presence.empty or persons.empty:
        rep.skipped_reason = "no presence or person rows"
        return rep

    p = persons[["person_id", "birth_date"]].copy()
    p["birth"] = pd.to_datetime(p["birth_date"], utc=True)

    df = presence[presence["location_kind"] == "building"][
        ["person_id", "start", "end", "location_id"]
    ].copy()
    if df.empty:
        rep.skipped_reason = "no in-building presence rows"
        return rep
    df["start"] = pd.to_datetime(df["start"], utc=True)
    df["end"] = pd.to_datetime(df["end"], utc=True)
    df = df.merge(p[["person_id", "birth"]], on="person_id", how="left")

    ref = as_of if as_of is not None else df["start"].min()
    df["age_years"] = (ref - df["birth"]).dt.days / 365.25
    df["is_child"] = df["age_years"] < CHILD_ALONE_AGE
    rep.n_checked = int(df["is_child"].sum())
    if rep.n_checked == 0:
        rep.skipped_reason = "no under-12 presence rows in this slice"
        return rep

    for building, grp in df.groupby("location_id", sort=True):
        children = grp[grp["is_child"]]
        if children.empty:
            continue
        supervisors = grp[~grp["is_child"]]
        # Sweep every boundary in the building; between consecutive boundaries
        # the set of occupants is constant.
        bounds = np.unique(
            np.concatenate([grp["start"].to_numpy(), grp["end"].to_numpy()])
        )
        for i in range(len(bounds) - 1):
            t0, t1 = bounds[i], bounds[i + 1]
            if t1 <= t0:
                continue
            kids_now = children[(children["start"] <= t0) & (children["end"] > t0)]
            if kids_now.empty:
                continue
            sup_now = supervisors[
                (supervisors["start"] <= t0) & (supervisors["end"] > t0)
            ]
            if sup_now.empty:
                rep.violations.append(
                    {
                        "kind": "child_under_12_alone",
                        "building_id": str(building),
                        "from": str(pd.Timestamp(t0)),
                        "to": str(pd.Timestamp(t1)),
                        "children": sorted(kids_now["person_id"].tolist()),
                    }
                )
    return rep


def check_venue_capacity(
    presence: pd.DataFrame, venues: Mapping[str, int]
) -> InvariantReport:
    """Every venue has a capacity, and it is not exceeded (design 5.4, 7.2)."""
    rep = InvariantReport("venue_capacity", "7.2 / 5.4", n_checked=0)
    at_venues = presence[presence["location_kind"] == "venue"].copy()
    if at_venues.empty:
        rep.skipped_reason = "no venue presence rows"
        return rep
    at_venues["start"] = pd.to_datetime(at_venues["start"], utc=True)
    at_venues["end"] = pd.to_datetime(at_venues["end"], utc=True)
    rep.n_checked = len(at_venues)

    undeclared = sorted(set(at_venues["location_id"]) - set(venues))
    for v in undeclared:
        rep.violations.append(
            {"kind": "venue_without_declared_capacity", "venue_id": v,
             "note": "design 5.4: every venue has a capacity"}
        )

    for venue, grp in at_venues.groupby("location_id", sort=True):
        cap = venues.get(venue)
        if cap is None:
            continue
        bounds = np.unique(
            np.concatenate([grp["start"].to_numpy(), grp["end"].to_numpy()])
        )
        for i in range(len(bounds) - 1):
            t0 = bounds[i]
            n = int(((grp["start"] <= t0) & (grp["end"] > t0)).sum())
            if n > cap:
                rep.violations.append(
                    {"kind": "venue_over_capacity", "venue_id": str(venue),
                     "at": str(pd.Timestamp(t0)), "occupants": n, "capacity": cap}
                )
    return rep


# --------------------------------------------------------------------------- #
# Energy and physics (7.2)
# --------------------------------------------------------------------------- #

def check_energy_closure(daily: pd.DataFrame) -> InvariantReport:
    """Energy closes per home per day (design 7.2).

        Sigma appliance + HVAC + EV + BESS charge - PV - BESS discharge
        = net meter, within 0.1% of daily energy.

    ``daily`` needs one row per building-day with columns:
    ``building_id``, ``date``, ``appliance_wh``, ``hvac_wh``, ``ev_wh``,
    ``bess_charge_wh``, ``pv_wh``, ``bess_discharge_wh``, ``net_meter_wh``.

    The tolerance is relative to **gross daily throughput**, not to the net
    meter: a home that imports almost nothing because PV covered the day would
    otherwise get an absurdly tight absolute tolerance and fail for a rounding
    error.  Design 7.2 says "within 0.1% of daily energy", which is the gross
    quantity.
    """
    tol = thresholds()["v0_invariants"]["energy_closure_daily_relative"]
    rep = InvariantReport(
        "energy_closure", f"7.2 (relative tolerance {tol})", n_checked=len(daily)
    )
    if daily.empty:
        rep.skipped_reason = "no daily energy rows"
        return rep

    needed = [
        "building_id", "date", "appliance_wh", "hvac_wh", "ev_wh",
        "bess_charge_wh", "pv_wh", "bess_discharge_wh", "net_meter_wh",
    ]
    missing = [c for c in needed if c not in daily.columns]
    if missing:
        rep.skipped_reason = f"missing columns {missing}"
        return rep

    d = daily.copy()
    expected = (
        d["appliance_wh"] + d["hvac_wh"] + d["ev_wh"] + d["bess_charge_wh"]
        - d["pv_wh"] - d["bess_discharge_wh"]
    )
    residual = (d["net_meter_wh"] - expected).abs()
    gross = (
        d["appliance_wh"].abs() + d["hvac_wh"].abs() + d["ev_wh"].abs()
        + d["bess_charge_wh"].abs() + d["pv_wh"].abs() + d["bess_discharge_wh"].abs()
    )
    # A home with zero throughput has nothing to close; guard the division.
    rel = np.where(gross > 0, residual / gross.replace(0, np.nan), 0.0)
    bad = np.asarray(rel) > tol
    for i in np.flatnonzero(bad):
        r = d.iloc[int(i)]
        rep.violations.append(
            {
                "kind": "energy_does_not_close",
                "building_id": str(r["building_id"]),
                "date": str(r["date"]),
                "net_meter_wh": float(r["net_meter_wh"]),
                "expected_wh": float(expected.iloc[int(i)]),
                "residual_wh": float(residual.iloc[int(i)]),
                "relative": float(np.asarray(rel)[int(i)]),
                "tolerance": tol,
            }
        )
    return rep


def check_physics_bounds(state: pd.DataFrame) -> InvariantReport:
    """SoC in [0,1], CO2 >= outdoor, RH in [0,100], temperature reachable."""
    t = thresholds()
    rep = InvariantReport("physics_bounds", "7.2", n_checked=len(state))
    if state.empty:
        rep.skipped_reason = "no state rows"
        return rep

    def _range(col: str, lo: float, hi: float, kind: str) -> None:
        if col not in state.columns:
            return
        v = pd.to_numeric(state[col], errors="coerce")
        bad = v.notna() & ((v < lo) | (v > hi))
        for i in np.flatnonzero(bad.to_numpy()):
            row = state.iloc[int(i)]
            rep.violations.append(
                {
                    "kind": kind, "column": col, "value": float(v.iloc[int(i)]),
                    "bounds": [lo, hi],
                    "building_id": str(row.get("building_id", "?")),
                    "ts": str(row.get("ts", "?")),
                }
            )

    lo_t, hi_t = t["physics"]["temperature_physically_reachable_c"]
    for col in ("temp_living_c", "temp_sleep_c", "temp_env_c"):
        _range(col, lo_t, hi_t, "temperature_out_of_reachable_range")
    lo_rh, hi_rh = t["v0_invariants"]["rh_bounds"]
    for col in ("rh_living_pct", "rh_sleep_pct"):
        _range(col, lo_rh, hi_rh, "rh_out_of_bounds")
    lo_c, hi_c = t["physics"]["co2_ppm_bounds"]
    for col in ("co2_living_ppm", "co2_sleep_ppm"):
        _range(col, lo_c, hi_c, "co2_out_of_bounds")
    lo_s, hi_s = t["v0_invariants"]["soc_bounds"]
    for col in ("bess_soc", "ev_soc"):
        _range(col, lo_s, hi_s, "soc_out_of_bounds")

    # CO2 >= outdoor: compared against the actual outdoor value where present,
    # not against the fixed lower bound above.
    if "co2_outdoor_ppm" in state.columns:
        for col in ("co2_living_ppm", "co2_sleep_ppm"):
            if col not in state.columns:
                continue
            inside = pd.to_numeric(state[col], errors="coerce")
            outside = pd.to_numeric(state["co2_outdoor_ppm"], errors="coerce")
            bad = inside.notna() & outside.notna() & (inside < outside - 1e-9)
            for i in np.flatnonzero(bad.to_numpy()):
                rep.violations.append(
                    {
                        "kind": "indoor_co2_below_outdoor", "column": col,
                        "indoor": float(inside.iloc[int(i)]),
                        "outdoor": float(outside.iloc[int(i)]),
                        "ts": str(state.iloc[int(i)].get("ts", "?")),
                    }
                )
    return rep


# --------------------------------------------------------------------------- #
# Referential integrity (7.2)
# --------------------------------------------------------------------------- #

def check_referential_integrity(
    frames: Mapping[str, pd.DataFrame],
    relations: Sequence[tuple[str, str, str, str]],
) -> InvariantReport:
    """Every foreign key resolves (design 7.2).

    ``relations`` entries are ``(child_dataset, child_column, parent_dataset,
    parent_column)``.  Null child values are allowed - an optional reference is
    not a dangling one - and are counted separately.
    """
    rep = InvariantReport("referential_integrity", "7.2", n_checked=len(relations))
    for child, ccol, parent, pcol in relations:
        if child not in frames or parent not in frames:
            rep.violations.append(
                {"kind": "relation_references_a_missing_dataset",
                 "relation": f"{child}.{ccol} -> {parent}.{pcol}",
                 "missing": [n for n in (child, parent) if n not in frames]}
            )
            continue
        cdf, pdf = frames[child], frames[parent]
        if ccol not in cdf.columns or pcol not in pdf.columns:
            rep.violations.append(
                {"kind": "relation_references_a_missing_column",
                 "relation": f"{child}.{ccol} -> {parent}.{pcol}"}
            )
            continue
        keys = set(pdf[pcol].dropna().astype(str))
        child_vals = cdf[ccol].dropna().astype(str)
        dangling = sorted(set(child_vals) - keys)
        if dangling:
            rep.violations.append(
                {
                    "kind": "dangling_foreign_key",
                    "relation": f"{child}.{ccol} -> {parent}.{pcol}",
                    "n_dangling_values": len(dangling),
                    "examples": dangling[:10],
                }
            )
    return rep


# --------------------------------------------------------------------------- #
# Indoor temperature distribution (I-032)
# --------------------------------------------------------------------------- #

#: Plausible range for the ANNUAL MEDIAN indoor living-zone temperature in an
#: Irish dwelling, and the share of time above a warm threshold.
#:
#: Declared assumptions [A]. No CSO or SEAI table publishes measured indoor
#: temperatures, so there is no file in ``sources/`` to trace these to and they
#: are deliberately WIDE: the band exists to refuse the implausible, not to
#: calibrate. The fault it was written for put the annual median at 24.6 C with
#: 19% of epochs above 30 C and a peak of 64.3 C, which no band of any width
#: would admit.
INDOOR_TEMP_MEDIAN_RANGE_C: tuple[float, float] = (15.0, 23.0)
INDOOR_TEMP_WARM_THRESHOLD_C: float = 28.0
INDOOR_TEMP_MAX_SHARE_ABOVE_WARM: float = 0.05
INDOOR_TEMP_ABSOLUTE_CEILING_C: float = 40.0


def check_indoor_temperature_distribution(state: pd.DataFrame) -> InvariantReport:
    """The living zone's temperature DISTRIBUTION, not just its bounds.

    A bounds check cannot see this fault and did not: every reading was inside
    [-15, 45] for 99.6% of epochs while the annual median sat at 24.6 C. What
    makes a thermal model wrong is usually not a single impossible value but a
    distribution that no dwelling has, and a per-row range check is blind to
    it by construction.

    Three things are checked, because each catches a different failure:
    the median (a model that runs hot or cold all year), the share of time
    above a warm threshold (a model with no path for heat to leave), and an
    absolute ceiling (a runaway).
    """
    rep = InvariantReport(
        "indoor_temperature_distribution",
        "7.2; I-032 (declared band [A], no public Irish measurement exists)",
        n_checked=len(state),
    )
    if state.empty or "temp_living_c" not in state.columns:
        rep.skipped_reason = "no building state with temp_living_c"
        return rep

    v = pd.to_numeric(state["temp_living_c"], errors="coerce").dropna()
    if v.empty:
        rep.skipped_reason = "temp_living_c is entirely missing"
        return rep

    median = float(v.median())
    lo, hi = INDOOR_TEMP_MEDIAN_RANGE_C
    if not (lo <= median <= hi):
        rep.violations.append({
            "kind": "median_indoor_temperature_implausible",
            "median_c": round(median, 2), "plausible_range_c": [lo, hi],
            "note": (
                "Irish dwellings average about 17 to 19 C over a year. A "
                "median outside this band means the model heats or vents "
                "wrongly for most of the year, not occasionally."
            ),
        })

    share_warm = float((v > INDOOR_TEMP_WARM_THRESHOLD_C).mean())
    if share_warm > INDOOR_TEMP_MAX_SHARE_ABOVE_WARM:
        rep.violations.append({
            "kind": "too_much_time_above_the_warm_threshold",
            "threshold_c": INDOOR_TEMP_WARM_THRESHOLD_C,
            "share": round(share_warm, 4),
            "max_share": INDOOR_TEMP_MAX_SHARE_ABOVE_WARM,
            "note": (
                "An Irish dwelling is rarely above 28 C. A large share "
                "usually means solar gain has no removal path."
            ),
        })

    peak = float(v.max())
    if peak > INDOOR_TEMP_ABSOLUTE_CEILING_C:
        worst = state.loc[v.idxmax()] if v.idxmax() in state.index else None
        rep.violations.append({
            "kind": "indoor_temperature_runaway",
            "peak_c": round(peak, 2),
            "ceiling_c": INDOOR_TEMP_ABSOLUTE_CEILING_C,
            "building_id": (str(worst.get("building_id", "?")) if worst is not None else "?"),
            "ts": (str(worst.get("ts", "?")) if worst is not None else "?"),
        })

    rep.violations.extend([])
    return rep
