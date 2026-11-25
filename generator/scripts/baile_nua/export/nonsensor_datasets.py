"""D28 - D31, from :mod:`baile_nua.observation.nonsensor`.

The generators already exist and are frozen.  What was missing was the ground
truth to hand them and a writer to put their frames on disk, which is all this
module is: it assembles ``truth_by_premises`` and ``traits`` from the run's own
t0 state and its own D11 presence rows, calls the four builders, and emits.

**Nothing here degrades anything.**  Every error rate, omission, bias and
non-response is the frozen module's, declared in its ``PLANTED_RATES`` and
re-estimated from the emitted data by ``test_nonsensor_65_rules``.  This module
only chooses what counts as the truth being observed, and each choice is named
in the part's manifest.

**Two enum vocabularies do not line up, and are mapped here.**  D31's rows come
out with ``quality`` in ``{good, estimated, missing}`` and ``provenance`` in
``{measured, gap_filled}``, and ``datasets.yaml`` declares ``quality_flag =
[ok, estimated, missing, suspect, drift, fault]`` and ``provenance_code =
[metered, estimated, interpolated, operator-recorded, respondent-reported,
modelled]``.  So ``good -> ok``, ``measured -> metered`` and ``gap_filled ->
interpolated``, recorded as a conversion.  That is a renaming at the export
boundary and not a change of meaning; it is also a real mismatch between a
frozen generator and the schema, and it is reported as a finding rather than
patched in either place.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from baile_nua.export.context import ExportError, RunContext
from baile_nua.export.writer import emit

__all__ = [
    "D31_QUALITY_MAP", "D31_PROVENANCE_MAP",
    "SETPOINT_BASE_C", "SETPOINT_PER_COMFORT_C",
    "build_traits", "build_truth_by_premises", "occupied_weekday_hours",
    "export_d28", "export_d29", "export_d30", "export_d31",
]

#: Frozen-generator vocabulary -> the schema's declared enum.
D31_QUALITY_MAP: dict[str, str] = {
    "good": "ok", "estimated": "estimated", "missing": "missing",
}
D31_PROVENANCE_MAP: dict[str, str] = {
    "measured": "metered", "gap_filled": "interpolated",
}

#: The setpoint the thermostat is ASKED for, as ``engine.run.EstateRunner``
#: computes it:
#:
#:     setpoint = 20.0 + 0.6 * float(np.clip(people[0].comfort, -2, 2))
#:
#: mirrored here because the runner computes it inside the day loop and does
#: not retain it, and D29's ``q_comfort_preference_c`` needs the truth its
#: respondent is misremembering.  Two constants, named, with
#: ``test_export_setpoint_constants_match_the_engine`` asserting that the
#: engine's own source still says this.  The comfort-taking shift is NOT
#: mirrored: it is read off the frozen runner, which is why the context builds
#: one.
SETPOINT_BASE_C = 20.0
SETPOINT_PER_COMFORT_C = 0.6


# --------------------------------------------------------------------------- #
# the truth these four datasets observe
# --------------------------------------------------------------------------- #

def _head_of(ctx: RunContext, household_id: str) -> Any:
    """The household member whose answers the study records.

    The head, as ``D08.role`` declares it; the lowest person id otherwise, so
    the choice never depends on dict order.
    """
    people = sorted(ctx.slice.households.get(household_id, ()),
                    key=lambda p: p.person_id)
    if not people:
        return None
    for p in people:
        if str(p.role) == "head":
            return p
    return people[0]


def build_traits(ctx: RunContext) -> dict[str, dict[str, float]]:
    """``{premises_id: {privacy, env, instTrust, satisficer}}``.

    The household head's own standardised traits.  Design 6.4's point about
    D28 is that "homes that accept sensors aren't typical", and the generator
    conditions selection on exactly these; the values never leave GT.
    """
    persons = ctx.town.persons.set_index("person_id")
    out: dict[str, dict[str, float]] = {}
    for hh_id, b in sorted(ctx.slice.buildings.items()):
        head = _head_of(ctx, hh_id)
        if head is None:
            continue
        row = persons.loc[head.person_id]
        out[b.premises_id] = {
            "privacy": float(row["privacy"]),
            "env": float(row["env"]),
            "instTrust": float(row["instTrust"]),
            "satisficer": float(row["satisficer"]),
        }
    return out


def occupied_weekday_hours(ctx: RunContext) -> dict[str, float]:
    """Mean weekday hours per building with at least one person at home.

    Read from the run's OWN D11 presence rows, not recomputed: D11 is the
    no-double-occupancy source and the only record of who was where.  Returned
    per building, keyed by building id.

    D11 is collected for a limited number of days (``collect_presence_days``),
    so this is a mean over the days the run actually recorded, which the
    caller records as a limitation.
    """
    import pyarrow.parquet as pq

    paths = sorted((ctx.run_root / "ground_truth").glob("D11_part*.parquet"))
    if not paths:
        raise ExportError(
            f"no D11 part under {ctx.run_root}/ground_truth, so there is no "
            f"record of who was at home and `occupied_weekday_hours` cannot be "
            f"derived. Defaulting it would hand the survey generator a flat "
            f"truth and make its occupancy answers meaningless."
        )
    frames = []
    for path in paths:
        frame = pq.read_table(
            path, columns=["start", "end", "location_kind", "location_id"]
        ).to_pandas()
        frames.append(frame[frame["location_kind"] == "building"])
    pres = pd.concat(frames, ignore_index=True)
    if pres.empty:
        raise ExportError("D11 carries no building-located presence rows")

    buildings = sorted(pres["location_id"].dropna().unique().tolist())
    index_of = {b: i for i, b in enumerate(buildings)}
    bidx = pres["location_id"].map(index_of).to_numpy(dtype=np.int64)
    t0 = ctx.t0
    start = pd.Series(pd.to_datetime(pres["start"], utc=True))
    end = pd.Series(pd.to_datetime(pres["end"], utc=True))
    off_a = ((start - t0).dt.total_seconds() // 60).to_numpy(dtype=np.int64)
    off_b = ((end - t0).dt.total_seconds() // 60).to_numpy(dtype=np.int64)
    n_min = int(off_b.max()) + 1
    n_days = -(-n_min // 1440)
    width = n_days * 1440

    # Difference array, so the whole thing is two scatter-adds and a cumsum
    # rather than a Python loop over a million intervals.
    diff = np.zeros((len(buildings), width + 1), dtype=np.int32)
    np.add.at(diff, (bidx, np.clip(off_a, 0, width)), 1)
    np.add.at(diff, (bidx, np.clip(off_b + 1, 0, width)), -1)
    occupied = np.cumsum(diff[:, :width], axis=1) > 0

    minute_index = pd.date_range(t0, periods=width, freq="1min", tz="UTC")
    is_weekday = np.asarray(minute_index.dayofweek) < 5
    day_of = np.arange(width) // 1440
    weekdays = sorted({int(d) for d in day_of[is_weekday]})
    if not weekdays:
        raise ExportError(
            "the recorded presence span contains no weekday, so a weekday "
            "occupancy figure cannot be derived from it"
        )
    per_day = occupied.reshape(len(buildings), n_days, 1440).sum(axis=2) / 60.0
    mean_hours = per_day[:, weekdays].mean(axis=1)
    return {b: float(round(mean_hours[i], 2)) for b, i in index_of.items()}


def build_truth_by_premises(ctx: RunContext) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """The GT a respondent, an assessor or an installer could know.

    Returns the map and a record of where each field came from, which goes
    into the manifest of every part built from it.
    """
    persons = ctx.town.persons.set_index("person_id")
    buildings = ctx.town.buildings_frame.set_index("building_id")
    occ = occupied_weekday_hours(ctx)
    shifts = getattr(ctx.runner, "comfort_shift", {}) or {}

    out: dict[str, dict[str, Any]] = {}
    for hh_id, b in sorted(ctx.slice.buildings.items()):
        bid = b.building_id
        row = buildings.loc[bid]
        people = sorted(ctx.slice.households.get(hh_id, ()),
                        key=lambda p: p.person_id)
        head = _head_of(ctx, hh_id)
        n_children = sum(1 for p in people if int(p.age) < 18)
        pv = ctx.slice.pv.get(hh_id)
        shift = float((shifts.get(hh_id) or {}).get("setpoint_shift_c", 0.0))
        comfort = (float(persons.loc[head.person_id, "comfort"])
                   if head is not None else 0.0)
        env = float(persons.loc[head.person_id, "env"]) if head is not None else 0.0
        out[b.premises_id] = {
            "household_size": len(people),
            "children_under_18": int(n_children),
            "occupied_weekday_hours": float(occ.get(bid, 0.0)),
            "dwelling_type": str(row["dwelling_type"]),
            "heating_system": str(row["heating_system"]),
            "has_pv": pv is not None,
            "has_ev": bool(getattr(b, "has_ev", False)),
            "appliances": sorted(ctx.slice.owned.get(hh_id, {})),
            # The MIMIC mapping D25.environmental_concern declares for itself:
            # "round(3 + 1.05 * latent), clamped 1 to 5".
            "env_behaviour_score": float(
                min(5, max(1, round(3 + 1.05 * env)))),
            "comfort_preference_c": float(
                SETPOINT_BASE_C
                + SETPOINT_PER_COMFORT_C * float(np.clip(comfort, -2, 2))
                + shift),
            # ---- D30's own fields ----
            "ber_band": str(row["ber_band"]),
            "ber_kwh_m2_yr": float(row["ber_kwh_m2_yr"]),
            "retrofitted": False,
            "floor_area_m2": float(row["floor_area_m2"]),
            "build_year": int(row["build_year"]),
            "pv_kwp": (float(pv.capacity_kwp) if pv is not None else None),
            "pv_azimuth_deg": (float(pv.azimuth_deg) if pv is not None else None),
            "pv_install_date": None,
        }
    provenance = {
        "household_size, children_under_18": "the slice's own household composition at t0",
        "occupied_weekday_hours": (
            "the run's own D11 presence rows: mean weekday hours with at least "
            "one person located at the building"
        ),
        "dwelling_type, heating_system, ber_band, ber_kwh_m2_yr, "
        "floor_area_m2, build_year": "the t0 synthesis's own buildings frame (D02)",
        "has_pv, pv_kwp, pv_azimuth_deg": "the slice's PV systems",
        "has_ev": "the slice building's own has_ev flag, set by build_slice's DER draw",
        "appliances": "the slice's drawn appliance stock (the keys of E1Slice.owned)",
        "env_behaviour_score": (
            "the head's `env` latent through the mapping D25.environmental_concern "
            "declares: round(3 + 1.05 * latent), clamped 1 to 5"
        ),
        "comfort_preference_c": (
            f"{SETPOINT_BASE_C} + {SETPOINT_PER_COMFORT_C} * clip(head.comfort, "
            f"-2, 2), as engine.run computes the asked-for setpoint, plus the "
            f"comfort-taking shift read off the frozen runner"
        ),
        "retrofitted": (
            f"False for every home: this run applied "
            f"{int(ctx.diagnostics.get('n_passport_effects_applied') or 0)} "
            f"passport effects, so no recorded BER can be stale through a "
            f"retrofit and D30's staleness mechanism has nothing to act on"
        ),
        "pv_install_date, ber_assessed_at, shading_category": (
            "NOT SUPPLIED: the model holds no install date, no assessment date "
            "and no shading category, so the generator's own declared default "
            "or null applies and the corresponding D30 columns are null or "
            "dated from that default"
        ),
    }
    return out, provenance


def _assert_generator_base(ctx: RunContext, base_iso: str, which: str) -> list[str]:
    """The nonsensor generators date their own timelines from fixed stamps."""
    base = pd.Timestamp(base_iso, tz="UTC")
    if base.year == ctx.t0.year:
        return []
    return [
        f"{which} dates its timeline from {base.isoformat()}, which the frozen "
        f"generator hard-codes, while this run starts at {ctx.t0.isoformat()}. "
        f"The two are in different years, so the recorded dates do not sit "
        f"inside the simulated span."
    ]


# --------------------------------------------------------------------------- #
# D28  study_protocol
# --------------------------------------------------------------------------- #

def export_d28(ctx: RunContext) -> dict[str, Any]:
    from baile_nua.observation import nonsensor as NS

    traits = build_traits(ctx)
    n_years = max(1, math.ceil(ctx.n_days / 365))
    rec = NS.build_study_protocol(
        premises=sorted(traits), traits=traits,
        master_seed=ctx.master_seed, n_years=n_years,
    )
    return emit(
        rec["rows"], "D28", ctx,
        source=(
            f"observation.nonsensor.build_study_protocol(premises=<the run's "
            f"{len(traits)} premises>, traits=<the head's privacy/env/instTrust>, "
            f"master_seed={ctx.master_seed}, n_years={n_years})"
        ),
        limitations=[
            "the trait vector is the HOUSEHOLD HEAD's, taken as the person "
            "whose D08 role is 'head' and the lowest person id otherwise; the "
            "generator takes one trait per premises and the model has one per "
            "person",
            *_assert_generator_base(ctx, "2022-01-01", "D28"),
        ],
        extra={
            "d28_planted": rec.get("planted"),
            "d28_observed": rec.get("observed"),
            "d28_true_selection_stays_in_gt": (
                "the generator returns the true consent probability in its own "
                "record and it is NOT written here; D28 carries only what the "
                "study team logged (design 6.4 item 1)"
            ),
        },
    )


# --------------------------------------------------------------------------- #
# D29  household_survey
# --------------------------------------------------------------------------- #

def export_d29(ctx: RunContext) -> dict[str, Any]:
    from baile_nua.observation import nonsensor as NS

    traits = build_traits(ctx)
    truth, provenance = build_truth_by_premises(ctx)
    rec = NS.build_household_survey(
        truth_by_premises=truth, traits=traits,
        master_seed=ctx.master_seed, waves=(1, 2),
    )
    return emit(
        rec["rows"], "D29", ctx,
        source=(
            f"observation.nonsensor.build_household_survey over the run's "
            f"{len(truth)} premises, waves (1, 2)"
        ),
        limitations=[
            "`occupied_weekday_hours` is a mean over the days D11 was "
            "collected, which is fewer than the simulated span: the runner "
            "collects presence for `collect_presence_days` days, not the whole "
            "run",
            "`q_comfort_preference_c` observes a setpoint reconstructed from "
            "the comfort trait and the frozen runner's comfort-taking shift; "
            "the runner computes it per day inside the loop and retains none",
            *_assert_generator_base(ctx, "2022-03-01", "D29"),
        ],
        extra={
            "d29_planted": rec.get("planted"),
            "d29_truth_provenance": provenance,
            "d29_no_latent_trait_appears": rec.get("no_latent_trait_appears"),
        },
    )


# --------------------------------------------------------------------------- #
# D30  recorded_metadata
# --------------------------------------------------------------------------- #

def export_d30(ctx: RunContext) -> dict[str, Any]:
    from baile_nua.observation import nonsensor as NS

    truth, provenance = build_truth_by_premises(ctx)
    rec = NS.build_recorded_metadata(
        truth_by_premises=truth, master_seed=ctx.master_seed)
    return emit(
        rec["rows"], "D30", ctx,
        source=(
            f"observation.nonsensor.build_recorded_metadata over the run's "
            f"{len(truth)} premises"
        ),
        limitations=[
            "the BER-staleness mechanism - a retrofitted home whose recorded "
            "band is still its pre-retrofit band - has nothing to act on: this "
            "run applied no passport retrofit, so `retrofitted` is False "
            "everywhere and every recorded band is the current one, degraded "
            "only by the record's other error mechanisms",
            "`recorded_at` is dated from the generator's own declared default "
            "assessment date, because the model holds no BER assessment date",
            "`rec_pv_install_date` and `rec_shading` are null: the model holds "
            "no install date and no shading category to record",
        ],
        extra={"d30_planted": rec.get("planted"),
               "d30_truth_provenance": provenance},
    )


# --------------------------------------------------------------------------- #
# D31  external_series
# --------------------------------------------------------------------------- #

def export_d31(ctx: RunContext) -> dict[str, Any]:
    from baile_nua.observation import nonsensor as NS

    rec = NS.build_external_series(
        realisation=ctx.weather, master_seed=ctx.master_seed)
    frame = rec["rows"].copy()

    bad_q = sorted(set(frame["quality"].dropna()) - set(D31_QUALITY_MAP))
    bad_p = sorted(set(frame["provenance"].dropna()) - set(D31_PROVENANCE_MAP))
    if bad_q or bad_p:
        raise ExportError(
            f"build_external_series emitted quality {bad_q} and provenance "
            f"{bad_p}, which this module has no declared mapping onto "
            f"datasets.yaml's quality_flag and provenance_code enums. Mapping "
            f"an unknown label by guess would change what the publisher is "
            f"said to have claimed about its own value."
        )
    frame["quality"] = frame["quality"].map(D31_QUALITY_MAP)
    frame["provenance"] = frame["provenance"].map(D31_PROVENANCE_MAP)
    frame = frame.sort_values(["series_id", "ts"]).reset_index(drop=True)

    station_col = (
        "station" if "station" in ctx.weather.station_hourly.columns
        else ("station_or_zone"
              if "station_or_zone" in ctx.weather.station_hourly.columns
              else None)
    )
    return emit(
        frame, "D31", ctx,
        source=(
            f"observation.nonsensor.build_external_series(realisation=<this "
            f"run's realisation {ctx.weather.realisation_id}>)"
        ),
        conversions=[{
            "field": "quality",
            "map": dict(D31_QUALITY_MAP),
            "why": (
                "the frozen generator emits 'good' and datasets.yaml declares "
                "quality_flag = [ok, estimated, missing, suspect, drift, "
                "fault]. A renaming at the export boundary, reported as a "
                "mismatch between the generator and the schema."
            ),
        }, {
            "field": "provenance",
            "map": dict(D31_PROVENANCE_MAP),
            "why": (
                "the generator emits 'measured' and 'gap_filled'; "
                "provenance_code declares 'metered' and 'interpolated'"
            ),
        }],
        limitations=[
            # The generator's own recorded limitation (I-072), repeated here
            # rather than paraphrased.
            f"PARTIAL: {', '.join(NS.D31_NOT_BUILT['series_not_built'])} are "
            f"NOT built. {NS.D31_NOT_BUILT['why']} {NS.D31_NOT_BUILT['consequence']}",
            (
                "the generator reads the station name from a `station` column "
                "and the weather realisation publishes it as "
                f"`{station_col}`, so the station label falls back to the "
                "generator's own default. A column-name mismatch between two "
                "frozen modules, reported and not patched."
                if station_col != "station" else
                "station label read from the realisation's `station` column"
            ),
        ],
        extra={
            "d31_series_built": rec.get("series_built"),
            "d31_planted": rec.get("planted"),
            "d31_observed": rec.get("observed"),
            "d31_not_built": NS.D31_NOT_BUILT,
            "d31_one_realisation": rec.get("one_realisation_drives_everything"),
        },
    )
