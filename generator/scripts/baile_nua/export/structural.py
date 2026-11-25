"""The t0 datasets: D01, D02, D05-D08, D14, D15, D22.

Every one of these is a deterministic function of the run's master seed, so
none of them has to be re-simulated to be exported: the context rebuilds the
town, the weather realisation, the calendar and the slice with the seed the
run recorded, and these functions select and shape what the frozen
constructors already produced.

Two of the nine need something the constructors do not carry, and both are
recorded in the part's manifest rather than quietly filled:

``D01``
    The model has venues, feeders and transformers.  It has no parcels, no
    streets and no farms, and no coordinate for anything but a small-area
    centroid, so ``geometry_wkt`` follows
    :meth:`baile_nua.population.venues.Venue.as_d01_row`'s own convention - a
    declared ``POINT EMPTY`` carrying the small area or estate it belongs to -
    rather than a fabricated polygon that would read as surveyed geometry.

``D15``
    ``sunrise_utc`` and ``sunset_utc`` are declared required and the weather
    realisation carries neither.  They are not modelled quantities: for a
    fixed site and date they are astronomy, so they are computed here with
    pvlib for ``COBH_SITE`` - the same library and the same site constants
    ``weather/site.py`` uses for the zenith and azimuth that ARE in the
    realisation.  Recorded as an export-layer derivation.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from baile_nua.export.context import ExportError, RunContext
from baile_nua.export.writer import emit

__all__ = [
    "export_d01", "export_d02", "export_d05", "export_d06", "export_d07",
    "export_d08", "export_d14", "export_d15", "export_d22",
]


# --------------------------------------------------------------------------- #
# D01  town_geo
# --------------------------------------------------------------------------- #

def _no_geometry(what: str) -> str:
    """``geometry_wkt`` for a feature the model sites but does not place.

    The same shape ``Venue.as_d01_row`` writes, for the same reason: a
    coordinate the model never had, written as a coordinate, is indistinguishable
    from a surveyed one.
    """
    return f"POINT EMPTY  /* {what} */"


def export_d01(ctx: RunContext) -> dict[str, Any]:
    """D01 from the venue stock and the LV topology the run connected."""
    from baile_nua.network.lv import build_town_network
    from baile_nua.population.venues import build_venues, person_frame_from_town

    rows: list[dict[str, Any]] = []
    t0 = ctx.t0

    persons = person_frame_from_town(ctx.town)
    venues = build_venues(persons=persons)["venues"]
    for v in venues:
        rows.append(v.as_d01_row(valid_from=t0.date().isoformat()))

    tn = build_town_network(buildings=ctx.slice.buildings)
    estate_of_feeder = {
        feeder: sub for _bid, (sub, feeder) in sorted(tn.assignment.items())
    }
    n_by_feeder: dict[str, int] = {}
    for _bid, (_sub, feeder) in tn.assignment.items():
        n_by_feeder[feeder] = n_by_feeder.get(feeder, 0) + 1
    estate_by_sub: dict[str, str] = {}
    for _bid, (sub, _feeder) in sorted(tn.assignment.items()):
        estate_by_sub[sub] = next(
            (b.estate_id for b in ctx.slice.buildings.values()
             if tn.assignment.get(b.building_id, (None, None))[0] == sub),
            None,
        )
    trafo_sizes = (tn.diagnostics or {}).get("trafo_sizes") or {}

    for sub in sorted(tn.trafo_by_substation):
        estate = estate_by_sub.get(sub)
        rows.append({
            "feature_id": sub,
            "feature_kind": "transformer",
            "geometry_wkt": _no_geometry(
                f"substation of estate {estate}; type "
                f"{trafo_sizes.get(sub, 'unrecorded')}; LV topology is [A] A-49, "
                f"which does not site it"),
            "venue_type": None,
            "capacity": None,
            "feeder_id": None,
            "estate_id": estate,
            "valid_from": t0,
            "valid_to": None,
        })
    for feeder in sorted(tn.head_line_by_feeder):
        sub = estate_of_feeder.get(feeder)
        rows.append({
            "feature_id": feeder,
            "feature_kind": "feeder",
            "geometry_wkt": _no_geometry(
                f"feeder from substation {sub}; a radial chain of cable "
                f"sections, [A] A-49, with no route"),
            "venue_type": None,
            # The number of connections the feeder carries. D01's `capacity`
            # note is about venues; for a feeder this is the only count the
            # topology actually declares, and it is named in the manifest so
            # it is not read as an ampacity.
            "capacity": int(n_by_feeder.get(feeder, 0)),
            "feeder_id": feeder,
            "estate_id": estate_by_sub.get(sub) if sub else None,
            "valid_from": t0,
            "valid_to": None,
        })

    frame = pd.DataFrame(rows)
    venues_engaged = _venues_engaged(ctx)
    return emit(
        frame, "D01", ctx,
        source=(
            "population.venues.build_venues over the town's own person frame, "
            "plus network.lv.build_town_network over the slice's buildings"
        ),
        conversions=[{
            "field": "geometry_wkt",
            "how": (
                "declared POINT EMPTY with the small area or estate in a "
                "comment, following Venue.as_d01_row's own convention"
            ),
            "why": (
                "the model holds no coordinate for a venue, a substation or a "
                "feeder route; only small-area centroids exist, and a "
                "fabricated polygon would read as surveyed geometry"
            ),
        }, {
            "field": "capacity",
            "how": "connection count for a feeder; the venue capacity for a venue",
            "why": "the topology declares no ampacity",
        }],
        limitations=[
            "feature kinds 'parcel', 'street' and 'farm' are declared by the "
            "schema and have no model: the town is built from small-area "
            "marginals and a dwelling stock, not from a parcel fabric or a "
            "street graph, so no row of those kinds is written",
            "declared storage is geoparquet; written as Parquet with the "
            "declared geometry_wkt string column, because the schema declares "
            "no binary geometry column for a GeoParquet writer to use",
            f"venues were {'engaged' if venues_engaged else 'NOT engaged'} by "
            f"this run, read from whether its D11 venue rows carry a location_id",
        ],
        extra={
            "d01_feature_counts": frame["feature_kind"].value_counts().to_dict(),
            "d01_venues_engaged_by_this_run": venues_engaged,
            "d01_network_diagnostics": tn.diagnostics,
        },
    )


def _venues_engaged(ctx: RunContext) -> bool:
    """Did this run attach venue ids to its presence rows?"""
    import pyarrow.parquet as pq

    for path in sorted((ctx.run_root / "ground_truth").glob("D11_part*.parquet")):
        tbl = pq.read_table(path, columns=["location_kind", "location_id"])
        frame = tbl.to_pandas()
        venue = frame[frame["location_kind"] == "venue"]
        if len(venue) and venue["location_id"].notna().any():
            return True
    return False


# --------------------------------------------------------------------------- #
# D02, D05 - D08: the t0 population, restricted to the slice
# --------------------------------------------------------------------------- #

def _slice_note(ctx: RunContext) -> str:
    return (
        f"the town's t0 synthesis restricted to the {len(ctx.household_ids)} "
        f"households of slice kind {ctx.slice_kind!r}; the synthesis itself "
        f"covers {len(ctx.town.buildings)} dwellings and "
        f"{len(ctx.town.persons)} people"
    )


def export_d02(ctx: RunContext) -> dict[str, Any]:
    """D02 from ``synthesise_t0``'s own buildings frame."""
    frame = ctx.town.buildings_frame
    out = frame[frame["building_id"].isin(set(ctx.building_ids))].copy()
    out = out.sort_values("building_id").reset_index(drop=True)
    _expect(out, len(ctx.building_ids), "D02", "buildings")
    return emit(
        out, "D02", ctx,
        source="population.synthesise.synthesise_t0().buildings_frame",
        limitations=[
            "version 1 throughout: a D03 passport event bumps the version, and "
            f"this run applied {int(ctx.diagnostics.get('n_passport_effects_applied') or 0)}",
            _slice_note(ctx),
        ],
    )


def export_d05(ctx: RunContext) -> dict[str, Any]:
    """D05 from ``synthesise_t0``'s own person frame."""
    frame = ctx.town.persons
    out = frame[frame["person_id"].isin(set(ctx.person_ids))].copy()
    out = out.sort_values("person_id").reset_index(drop=True)
    _expect(out, len(ctx.person_ids), "D05", "persons")
    return emit(
        out, "D05", ctx,
        source="population.synthesise.synthesise_t0().persons",
        limitations=[_slice_note(ctx)],
    )


def export_d06(ctx: RunContext) -> dict[str, Any]:
    """D06 from ``synthesise_t0``'s own membership frame."""
    frame = ctx.town.membership
    out = frame[frame["household_id"].isin(set(ctx.household_ids))].copy()
    out = out.sort_values(["household_id", "person_id"]).reset_index(drop=True)
    return emit(
        out, "D06", ctx,
        source="population.synthesise.synthesise_t0().membership",
        limitations=[
            "t0 intervals only: valid_to is open everywhere, because the "
            "membership this run started from is the membership it ended with "
            "unless a D09 move closed it, and the life course that produces "
            "those is the ten-year run, not this one",
            _slice_note(ctx),
        ],
    )


def export_d07(ctx: RunContext) -> dict[str, Any]:
    """D07, restricted to edges with BOTH ends inside the slice.

    Both ends, not one: an edge to a person who is not in the package is a
    dangling reference, and a reader joining D07 to D05 would silently lose it.
    """
    frame = ctx.town.relationships
    inside = set(ctx.person_ids)
    out = frame[frame["person_a"].isin(inside) & frame["person_b"].isin(inside)].copy()
    out = out.sort_values("edge_id").reset_index(drop=True)
    n_half = int(
        len(frame[frame["person_a"].isin(inside) ^ frame["person_b"].isin(inside)])
    )
    return emit(
        out, "D07", ctx,
        source="population.synthesise.synthesise_t0().relationships",
        limitations=[
            f"{n_half} town edges with exactly one end in the slice are "
            f"dropped: an edge to a person the package does not contain is a "
            f"dangling reference",
            _slice_note(ctx),
        ],
    )


def export_d08(ctx: RunContext) -> dict[str, Any]:
    """D08 from ``synthesise_t0``'s own state frame."""
    frame = ctx.town.states
    out = frame[frame["household_id"].isin(set(ctx.household_ids))].copy()
    out = out.sort_values(["person_id", "valid_from"]).reset_index(drop=True)
    return emit(
        out, "D08", ctx,
        source="population.synthesise.synthesise_t0().states",
        limitations=[
            "one open interval per person: SCD-2 closure comes from the life "
            "course (D09), which this run did not step",
            _slice_note(ctx),
        ],
    )


def _expect(frame: pd.DataFrame, n: int, dataset_id: str, what: str) -> None:
    if len(frame) != n:
        raise ExportError(
            f"{dataset_id}: selected {len(frame)} {what} for a slice of {n}. "
            f"The slice and the synthesis disagree, which means the export "
            f"would not describe the run on disk."
        )


# --------------------------------------------------------------------------- #
# D14  calendar_events
# --------------------------------------------------------------------------- #

def export_d14(ctx: RunContext) -> dict[str, Any]:
    """D14 from ``build_events``, driven by THIS run's weather realisation.

    ``storm_days`` is taken from the run's own realisation through
    :func:`baile_nua.engine.calendar.storm_days_from_weather`, which is the
    bridge design 6.5 rule 2 names: the storm events and the wind that caused
    them are then the same thing rather than two agreeing draws.
    """
    from baile_nua.engine.calendar import storm_days_from_weather
    from baile_nua.engine.calendar_events import build_events

    storms = storm_days_from_weather(ctx.weather.site_hourly)
    storm_days = (
        [pd.Timestamp(d) for d in storms]
        if not isinstance(storms, dict)
        else [pd.Timestamp(d) for d in storms.get("storm_days", [])]
    )
    estates = tuple(sorted({b.estate_id for b in ctx.slice.buildings.values()}))
    events = build_events(
        year=ctx.year, master_seed=ctx.master_seed,
        storm_days=storm_days, estate_ids=estates,
    )
    rows = []
    for e in events:
        rows.append({
            "instance_id": e.instance_id,
            "event_kind": e.event_kind,
            "event_class": e.event_class,
            "phase": e.phase,
            "start": pd.Timestamp(e.start, tz="UTC") if e.start.tzinfo is None
                     else e.start,
            "end": pd.Timestamp(e.end, tz="UTC") if e.end.tzinfo is None
                   else e.end,
            "footprint": e.footprint,
            "footprint_ids": e.footprint_ids,
            "attendance_prob": e.attendance_prob,
            "shared_driver": e.shared_driver,
            "source_ref": e.source_ref,
        })
    frame = pd.DataFrame(rows).sort_values(
        ["start", "instance_id"]).reset_index(drop=True)
    return emit(
        frame, "D14", ctx,
        source=(
            f"engine.calendar_events.build_events(year={ctx.year}, "
            f"master_seed={ctx.master_seed}, storm_days=<this run's "
            f"realisation>, estate_ids={estates})"
        ),
        conversions=[{
            "field": "start, end",
            "how": "localised to UTC where build_events returned naive stamps",
            "why": "the schema declares timestamptz and the units block says UTC",
        }],
        limitations=[
            "build_events is WP6 and the day loop does not call it: the runner "
            "consumed engine.calendar.CalendarDay (holiday, term, storm, DST "
            "flags per day), not these instances. D14 is therefore consistent "
            "with the run by construction - same year, same seed, same "
            "realisation's storm days - rather than read back from it",
            "street_ids keeps build_events' own default, because the model has "
            "no street graph; footprint_ids on a street-footprint row carries "
            "that default and not a surveyed street",
            f"{len(storm_days)} storm days came from this run's weather realisation",
        ],
        extra={"d14_n_storm_days": len(storm_days),
               "d14_estate_ids": list(estates)},
    )


# --------------------------------------------------------------------------- #
# D15  weather
# --------------------------------------------------------------------------- #

#: D15's declared field names, so the realisation's extra columns are dropped
#: by name rather than by position.
_D15_DECLARED: frozenset[str] = frozenset({
    "ts", "site_id", "temp_air_c", "rh_pct", "wind_speed_ms", "wind_dir_deg",
    "ghi_w_m2", "dni_w_m2", "dhi_w_m2", "solar_zenith_deg",
    "solar_azimuth_deg", "sunrise_utc", "sunset_utc", "is_dst", "precip_mm",
    "realisation_id",
})


def export_d15(ctx: RunContext) -> dict[str, Any]:
    """D15 from the run's own 1-minute site truth, plus solar rise and set."""
    import pvlib

    from baile_nua.weather.station import COBH_SITE

    wx = ctx.weather
    frame = wx.site_minute.copy()
    index = pd.DatetimeIndex(frame.index)
    if index.tz is None:
        index = index.tz_localize("UTC")
    frame = frame.reset_index(drop=True)
    frame.insert(0, "ts", index)

    days = pd.DatetimeIndex(sorted(set(index.normalize())))
    rst = pvlib.solarposition.sun_rise_set_transit_spa(
        days, COBH_SITE.latitude, COBH_SITE.longitude)
    sunrise = pd.to_datetime(rst["sunrise"], utc=True)
    sunset = pd.to_datetime(rst["sunset"], utc=True)
    key = index.normalize()
    frame["sunrise_utc"] = key.map(dict(zip(days, sunrise)))
    frame["sunset_utc"] = key.map(dict(zip(days, sunset)))

    # Dropped HERE, not left to coerce_frame. `write_dataset` audits the
    # INCOMING columns, so an undeclared one is a refusal and not a silent
    # drop - which is the right behaviour and means the exporter has to say
    # out loud which realisation columns the schema does not declare.
    undeclared = sorted(set(frame.columns) - set(_D15_DECLARED))
    frame = frame.drop(columns=undeclared)

    return emit(
        frame, "D15", ctx,
        source=f"weather.site.build_realisation({ctx.year}, "
               f"master_seed={ctx.master_seed}).site_minute",
        conversions=[{
            "field": "ts",
            "how": "the site_minute DatetimeIndex promoted to a column",
            "why": "the schema declares ts as a field",
        }, {
            "field": "sunrise_utc, sunset_utc",
            "how": (
                "pvlib.solarposition.sun_rise_set_transit_spa for "
                f"COBH_SITE ({COBH_SITE.latitude}, {COBH_SITE.longitude}), "
                "per calendar day, broadcast over that day's minutes"
            ),
            "why": (
                "both are declared required and the weather realisation carries "
                "neither. They are astronomy for a fixed site and date, not a "
                "modelled quantity, and this is the library and the site "
                "constant weather/site.py already uses for the zenith and "
                "azimuth that ARE in the realisation. DERIVED IN THE EXPORT "
                "LAYER, not read from the run."
            ),
        }],
        limitations=[
            "the realisation's `pressure_hpa` and `cloud_modifier` columns are "
            "dropped: the schema declares neither, and coerce_frame would drop "
            "them silently, so they are named here instead",
            f"{len(frame):,} minute rows, the run's own span of {ctx.n_days} days",
        ],
        extra={
            "d15_realisation_id": wx.realisation_id,
            "d15_dropped_columns": undeclared,
        },
    )


# --------------------------------------------------------------------------- #
# D22  signature_library
# --------------------------------------------------------------------------- #

def export_d22(ctx: RunContext) -> dict[str, Any]:
    """D22 straight from the frozen signature library's own D22 rows."""
    from baile_nua.devices.signatures import D22_rows

    frame = pd.DataFrame(D22_rows()).sort_values(
        "signature_id").reset_index(drop=True)
    return emit(
        frame, "D22", ctx,
        source="devices.signatures.D22_rows()",
        limitations=[
            "declared storage is 'parquet + npz'; the waveform travels in the "
            "Parquet `template_w` list and no npz is written, because the "
            "library holds the shape as a parameterised template rather than "
            "as a measured array",
            "every row is source_dataset='synthetic-template': the sub-metered "
            "datasets U05 names are not ingested in this build, which the "
            "rows' own evidence_status says in full",
        ],
    )
