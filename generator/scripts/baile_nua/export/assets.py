"""D04 ``assets``, as far as the frozen model actually parameterises an asset.

D04 was in :mod:`baile_nua.export.absent` and its recorded reason was right
about the two fields it named: ``make_model_synth`` and
``failure_hazard_scale`` have no model in E1, and inventing either would be a
parameter the physics never saw.  What the reason did NOT establish is that
every OTHER field is unavailable too, and most of them are: the engine draws an
appliance stock with ages, draws PV with a capacity, an azimuth and a tilt,
builds each dwelling's hot water system with a tank volume in litres and an
immersion rating, and constructs a battery, a vehicle and a charger from named
constants.  So this module writes the asset rows the model holds and leaves the
rest null, which is the version of D04 that is true.

**Nothing here is invented.**  Every populated cell is read off a model object
or off one of the run's own written parts, and every null is a column the model
has no value for, named in ``NULL_REQUIRED`` (for required columns) or
``NULL_OPTIONAL`` (for the rest) with the reason.  That list is handed to
:func:`baile_nua.io.write_dataset`, which records it in the part's manifest, so
the part cannot be mistaken for a fully conformant one.

**Everything is rebuilt from the structural state, not re-simulated.**  The
asset state is a deterministic function of the master seed, so this module
reads it off ``RunContext.slice`` (``owned``, ``pv``, ``thermal``,
``has_battery``, ``has_ev``) and off ``physics.dhw.dhw_system_for``, which is
the identical call ``engine.run.EstateRunner`` makes.  Exactly one column is
read from a written part rather than rebuilt - ``signature_id``, from the run's
own D13 cycles - because which signature an appliance keys into is decided per
cycle inside the day loop and is not structural.

**Several asset classes are parameterised by constants in the frozen engine**,
not by a draw: ``engine.run.EstateRunner`` builds every battery as 5 kWh /
2.5 kW and every EV as 58 kWh on a 7.4 kW charger, and ``engine.run`` builds a
heat pump on the dwelling's own emitter rating at the default COP.  Those
constants are mirrored here as named module constants with
``test_export_d04_d24`` asserting that the engine's source still says so - the
same arrangement ``nonsensor_datasets.SETPOINT_BASE_C`` already uses, and for
the same reason: the runner computes them inside a loop and retains nothing.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from baile_nua.physics import dhw as dhw_mod

from baile_nua.export.context import RunContext
from baile_nua.export.writer import emit

__all__ = [
    "BESS_CAPACITY_WH",
    "BESS_MAX_CHARGE_W",
    "BESS_MAX_DISCHARGE_W",
    "BESS_ROUND_TRIP_EFFICIENCY",
    "EV_BATTERY_WH",
    "EV_CHARGER_W",
    "HEAT_PUMP_COP_AT_7C",
    "DIRECT_ELECTRIC_EFFICIENCY",
    "IMMERSION_EFFICIENCY",
    "ASSET_CLASSES",
    "NULL_REQUIRED",
    "NULL_OPTIONAL",
    "signature_id_by_asset",
    "build_d04_rows",
    "export_d04",
]

# --------------------------------------------------------------------------- #
# the frozen engine's own DER constants, mirrored
# --------------------------------------------------------------------------- #
#: ``engine.run.EstateRunner`` builds every household battery with exactly
#: these, and the only per-household draw is the initial state of charge -
#: which is a state, not an asset parameter, and so is not a D04 column.
BESS_CAPACITY_WH = 5000.0
BESS_MAX_CHARGE_W = 2500.0
BESS_MAX_DISCHARGE_W = 2500.0
#: ``devices.der.Battery.round_trip_efficiency``'s default, which the engine
#: does not override.
BESS_ROUND_TRIP_EFFICIENCY = 0.90

#: Likewise every EV: ``der_mod.ElectricVehicle(battery_wh=58_000.0,
#: charger_w=7400.0, ...)``.  The charger is a separate D04 asset class, and
#: ``charger_w`` is the only number the model holds about it.
EV_BATTERY_WH = 58_000.0
EV_CHARGER_W = 7400.0

#: ``devices.der.HeatPump.cop_at_7c``'s default, which ``engine.run`` does not
#: override when it builds ``HeatPump(rated_thermal_w=tp.heat_emitter_w)``.
#: The COP the physics USES varies with ambient temperature and with the
#: emitter adjustment; this is the rating-point figure, which is what an asset
#: record carries.
HEAT_PUMP_COP_AT_7C = 3.6
#: ``engine.run``: "direct electric: COP 1", in the code and in a comment.
DIRECT_ELECTRIC_EFFICIENCY = 1.0

#: An immersion heater is resistive, and ``physics.dhw._simulate_tank`` says so
#: arithmetically: the electrical rating caps the heat delivered to the tank
#: one for one (``rated = immersion_rated_w * hours / 1000``, then
#: ``immersion_kwh += got``), and ``engine.run`` charges the same ``immersion_w``
#: as electrical load. So 1.0 is read off the model, not assumed of resistive
#: heaters in general.
IMMERSION_EFFICIENCY = 1.0

#: The six classes ``datasets.yaml`` declares for ``asset_class``.
ASSET_CLASSES: tuple[str, ...] = (
    "appliance", "heating", "pv", "bess", "charger", "vehicle",
)

# --------------------------------------------------------------------------- #
# what is left null, and why
# --------------------------------------------------------------------------- #
#: REQUIRED columns left null, with the reason.  These are the declared-null
#: exemptions: present in the frame, null in every row or in the rows of the
#: classes named, and recorded in the part's manifest.
NULL_REQUIRED: dict[str, str] = {
    "make_model_synth": (
        "NO SOURCE. The field's own note says it 'drives signature variation', "
        "and in the frozen build the model-to-model spread is drawn ONCE PER "
        "CYCLE by devices.signatures (`model_cv`, one draw per cycle applied "
        "to the whole shape), not once per asset. So there is no per-asset "
        "model label to write: a label invented here would imply a per-asset "
        "variation the renderer does not apply. Unchanged from the reason D04 "
        "carried in export.absent."
    ),
    "failure_hazard_scale": (
        "NO SOURCE as a Weibull scale. The field's note says 'Weibull scale, "
        "drives 5.3 appliance failure' and appliance failure in the frozen "
        "build is not a lifetime draw at all: lifecourse.events draws an "
        "`appliance_failure` DISRUPTION and engine.run puts the appliance out "
        "of service for a fixed seven days "
        "(`failed_appliances[k] = sim_day + 7`). There is no hazard parameter "
        "to read. Unchanged from the reason D04 carried in export.absent."
    ),
    "install_date": (
        "POPULATED for appliance rows, NULL for every heating, pv, bess, "
        "charger and vehicle row. The appliance draw carries `age_years`, so "
        "the install date is t0 minus that age - arithmetic on a model "
        "quantity, recorded as a derivation. Nothing else in the structural "
        "state carries a date of any kind: `build_slice`'s DER block draws a "
        "capacity, an azimuth and a tilt and stops, `dhw_system_for` returns a "
        "volume and a rating and no age, and D30's own provenance already "
        "records `pv_install_date` as NOT SUPPLIED for the same reason. A "
        "dated install would have to come from a D03 passport event, and this "
        "run applies none to an asset."
    ),
    "age_years_at_t0": (
        "POPULATED for appliance rows, NULL for every other row, for the same "
        "reason as install_date: `age_years` exists only in the appliance "
        "stock draw."
    ),
}

#: OPTIONAL columns left null, with the reason.  Not exemptions - the schema
#: already permits the null - but a reader is owed the reason just the same.
NULL_OPTIONAL: dict[str, str] = {
    "valid_to": (
        "every asset row is version 1 and open-ended: D04's version history is "
        "driven by D03 passport events and this run applies none of them to an "
        "asset, so no row has been superseded"
    ),
    "owner_person_id": (
        "null everywhere. The model attaches the vehicle and the charger to "
        "the BUILDING (`build_slice` sets `b.has_ev`), not to a person. D05 "
        "carries a per-person `vehicle_access`, but reading an owner off it "
        "would be an inference about which resident the car belongs to, and "
        "the model never makes it."
    ),
    "rated_power_w": (
        "null for appliances; populated for the space-heating row (the "
        "dwelling's emitter rating), the coil-fed hot water store, the "
        "immersion, pv, bess and charger. "
        "`_draw_stock` sets `rated_power_w = 0.0` as an explicit placeholder - "
        "its own comment says the power comes from the signature library at "
        "render time - so writing the 0.0 through would claim a zero-power "
        "device. Null for the vehicle: the model holds the car's battery and "
        "its charger's power, and no traction rating."
    ),
    "capacity": (
        "populated for pv (kWp), bess (Wh), vehicle (Wh, the traction battery, "
        "following the BESS convention the unit note sets) and the hot water "
        "store (litres, the unit note's own for a tank); null for appliance, "
        "charger, the immersion and the space-heating row, none of which has a "
        "capacity in the model - heat_emitter_w is a power, not a store"
    ),
    "efficiency": (
        "populated for bess (round-trip) and for heating where the model holds "
        "a conversion efficiency - the heat pump's rating-point COP, 1.0 for "
        "direct electric, which engine.run states as 'COP 1', and 1.0 for the "
        "immersion, which physics.dhw converts one for one. Null for an "
        "oil, gas, LPG, solid-fuel or district-heating dwelling: the engine "
        "computes no electrical conversion for them ('oil or gas: not "
        "electric') and so holds no efficiency. Null for pv: the model has a "
        "shading factor, a temperature coefficient and an inverter rating, and "
        "none of the three is a module efficiency."
    ),
    "signature_id": (
        "populated for an appliance that ran at least one cycle in this run, "
        "read from the run's OWN D13 rows (`asset_id` -> `signature_id`); null "
        "for an appliance that never ran, and for every non-appliance class, "
        "which the signature library does not cover"
    ),
    "pv_azimuth_deg, pv_tilt_deg": "populated for pv only; the columns are pv's",
    "building_id": (
        "populated for every row: every asset the model holds belongs to a "
        "dwelling"
    ),
}


# --------------------------------------------------------------------------- #
# the one thing read from the run rather than rebuilt
# --------------------------------------------------------------------------- #

def signature_id_by_asset(ctx: RunContext) -> dict[str, str]:
    """``{asset_id: signature_id}`` from the run's own D13 appliance cycles.

    The signature an asset keys into is a property of the asset, and the only
    place the run records the pairing is D13, which the engine streams.  Read
    rather than recomputed, for the reason ``occupied_weekday_hours`` reads
    D11 rather than recomputing presence: the written part is the record.

    An asset that ran no cycle gets no entry, and its ``signature_id`` stays
    null.  Absent D13 is not an error here: it costs the column, not the
    dataset, and the limitation says so.
    """
    import pyarrow.parquet as pq

    out: dict[str, str] = {}
    for path in sorted((ctx.run_root / "ground_truth").glob("D13_part*.parquet")):
        frame = pq.read_table(
            path, columns=["asset_id", "signature_id"]).to_pandas()
        pairs = frame.dropna().drop_duplicates()
        for asset_id, signature_id in zip(pairs["asset_id"], pairs["signature_id"]):
            out.setdefault(str(asset_id), str(signature_id))
    return out


# --------------------------------------------------------------------------- #
# the rows
# --------------------------------------------------------------------------- #

def _blank(ctx: RunContext, *, asset_id: str, building_id: str,
           asset_class: str, asset_type: str) -> dict[str, Any]:
    """One row with every column present and every unsourced one null."""
    return {
        "asset_id": asset_id,
        "version": 1,
        "valid_from": ctx.t0,
        "valid_to": None,
        "building_id": building_id,
        "owner_person_id": None,
        "asset_class": asset_class,
        "asset_type": asset_type,
        "make_model_synth": None,
        "rated_power_w": None,
        "capacity": None,
        "efficiency": None,
        "install_date": None,
        "age_years_at_t0": None,
        "failure_hazard_scale": None,
        "signature_id": None,
        "device_mode": "rendered",
        "pv_azimuth_deg": None,
        "pv_tilt_deg": None,
        "seed": int(ctx.master_seed),
    }


def build_d04_rows(ctx: RunContext) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Every asset row the frozen model holds, plus a provenance record."""
    signatures = signature_id_by_asset(ctx)
    buildings = ctx.town.buildings_frame.set_index("building_id")
    rows: list[dict[str, Any]] = []

    for hh_id, b in sorted(ctx.slice.buildings.items()):
        bid = str(b.building_id)
        meta = buildings.loc[bid]

        # ---- appliance: the one class the engine DRAWS per asset ----------
        for asset_type, asset in sorted(ctx.slice.owned.get(hh_id, {}).items()):
            age = float(asset["age_years"])
            row = _blank(ctx, asset_id=str(asset["asset_id"]), building_id=bid,
                         asset_class="appliance", asset_type=asset_type)
            row["age_years_at_t0"] = age
            # t0 minus the drawn age, to the day. The age is a float year and
            # the schema's column is a date, so the day is the resolution the
            # schema asks for and the derivation is recorded as such.
            row["install_date"] = (
                ctx.t0 - pd.Timedelta(days=age * 365.25)).date()
            row["signature_id"] = signatures.get(str(asset["asset_id"]))
            rows.append(row)

        # ---- heating: type from D02, emitter rating from the thermal params
        system = str(meta["heating_system"])
        fuel = str(meta["heating_fuel"])
        thermal = ctx.slice.thermal.get(hh_id)
        row = _blank(ctx, asset_id=f"A-{bid[2:]}-HEAT", building_id=bid,
                     asset_class="heating", asset_type=system)
        if thermal is not None:
            row["rated_power_w"] = float(thermal.heat_emitter_w)
        if system == "heat pump":
            row["efficiency"] = HEAT_PUMP_COP_AT_7C
        elif fuel == "electricity":
            row["efficiency"] = DIRECT_ELECTRIC_EFFICIENCY
        rows.append(row)

        # ---- hot water: the store, and the immersion in it --------------
        #
        # `dhw_system_for(b, has_pv=...)` is the SAME call
        # `engine.run.EstateRunner.__init__` makes - same frozen function,
        # same two arguments - so this is not a second implementation of the
        # mechanism, and `test_export_d04_d24` asserts the runner's call site
        # still reads that way. Called directly rather than through
        # `ctx.runner.dhw_systems` because it needs none of the runner: it is a
        # pure function of the dwelling and whether the dwelling has PV.
        dhw = dhw_mod.dhw_system_for(b, has_pv=(hh_id in ctx.slice.pv))
        if dhw is not None:
            if dhw.has_tank:
                row = _blank(ctx, asset_id=f"A-{bid[2:]}-DHW",
                             building_id=bid, asset_class="heating",
                             asset_type=dhw.kind)
                # litres, which is the unit D04's own note declares for a tank.
                row["capacity"] = float(dhw.tank_litres)
                if dhw.kind == "cylinder_indirect":
                    # Coil-fed from the main boiler: the coil is what rates the
                    # store's heat input. A cylinder_immersion store is heated
                    # by the immersion, which is its own row below.
                    row["rated_power_w"] = float(dhw.coil_rated_w)
                rows.append(row)
            if dhw.has_immersion:
                row = _blank(ctx, asset_id=f"A-{bid[2:]}-IMM",
                             building_id=bid, asset_class="heating",
                             asset_type="immersion")
                row["rated_power_w"] = float(dhw.immersion_rated_w)
                row["efficiency"] = IMMERSION_EFFICIENCY
                rows.append(row)

        # ---- pv --------------------------------------------------------
        pv = ctx.slice.pv.get(hh_id)
        if pv is not None:
            row = _blank(ctx, asset_id=f"A-{bid[2:]}-PV", building_id=bid,
                         asset_class="pv", asset_type="roof_pv")
            row["capacity"] = float(pv.capacity_kwp)
            row["rated_power_w"] = float(pv.inverter_kw) * 1000.0
            row["pv_azimuth_deg"] = float(pv.azimuth_deg)
            row["pv_tilt_deg"] = float(pv.tilt_deg)
            rows.append(row)

        # ---- bess ------------------------------------------------------
        if bool(getattr(b, "has_battery", False)):
            row = _blank(ctx, asset_id=f"A-{bid[2:]}-BESS", building_id=bid,
                         asset_class="bess", asset_type="home_battery")
            row["capacity"] = BESS_CAPACITY_WH
            row["rated_power_w"] = BESS_MAX_CHARGE_W
            row["efficiency"] = BESS_ROUND_TRIP_EFFICIENCY
            rows.append(row)

        # ---- vehicle and its charger -----------------------------------
        if bool(getattr(b, "has_ev", False)):
            row = _blank(ctx, asset_id=f"A-{bid[2:]}-EV", building_id=bid,
                         asset_class="vehicle", asset_type="battery_electric")
            row["capacity"] = EV_BATTERY_WH
            rows.append(row)
            row = _blank(ctx, asset_id=f"A-{bid[2:]}-CHG", building_id=bid,
                         asset_class="charger", asset_type="ev_charger")
            row["rated_power_w"] = EV_CHARGER_W
            rows.append(row)

    provenance = {
        "appliance": (
            "engine.e1_run._draw_stock, through the rebuilt slice: asset_id "
            "and age_years are the draw's own, install_date is t0 minus "
            "age_years, and signature_id is read from the run's own D13 rows"
        ),
        "heating": (
            "asset_type is D02's heating_system and rated_power_w is the "
            "dwelling's own heat_emitter_w from ThermalParams, which is the "
            "rating the physics applies. efficiency is the frozen default COP "
            "for a heat pump and 1.0 for direct electric; nothing for a "
            "non-electric fuel, which the engine does not convert"
        ),
        "heating: hot water": (
            "physics.dhw.dhw_system_for(building, has_pv=...), the same call "
            "engine.run.EstateRunner makes. The store's capacity is its "
            "tank_litres - litres, which is the unit D04's own note declares "
            "for a tank - and its rated_power_w is coil_rated_w where the coil "
            "is what heats it. The immersion is a row of its own, rated at "
            "immersion_rated_w, at efficiency 1.0 because physics.dhw puts the "
            "immersion's electrical watts into the tank one for one. This "
            "recovers the immersion as an asset: it left the appliance "
            "ownership table at U25 because it is part of the hot water "
            "system, not an appliance with a load signature"
        ),
        "pv": (
            "the slice's own der.PVSystem: capacity is capacity_kwp, "
            "rated_power_w is inverter_kw x 1000 (the inverter is what rates "
            "the system's power), and the azimuth and tilt are the draw's"
        ),
        "bess": (
            f"engine.run.EstateRunner's own constants, mirrored in this module "
            f"and asserted against the engine's source: {BESS_CAPACITY_WH} Wh, "
            f"{BESS_MAX_CHARGE_W} W, round trip "
            f"{BESS_ROUND_TRIP_EFFICIENCY}. Presence is the slice's "
            f"has_battery flag"
        ),
        "vehicle, charger": (
            f"the same constants: {EV_BATTERY_WH} Wh traction battery on a "
            f"{EV_CHARGER_W} W charger. Presence is the slice's has_ev flag"
        ),
        "asset_type": (
            "the model's own label in every case: the appliance key for an "
            "appliance, D02's heating_system for the space-heating row, the "
            "DHWSystem kind for the store, 'immersion' for the immersion, and "
            "roof_pv / home_battery / battery_electric / ev_charger for the "
            "four classes the model names only by a boolean"
        ),
        "device_mode": (
            "'rendered' for every row: design 5.6's live mode is the "
            "render-on-demand path, and every asset in this run is rendered by "
            "the signature library during the day loop"
        ),
        "asset_id for the non-appliance classes": (
            "MINTED here, deterministically, as A-<building id without its "
            "prefix>-{HEAT,DHW,IMM,PV,BESS,EV,CHG}. The engine mints appliance ids the "
            "same way and mints none for the others. An identifier is a key, "
            "not a measurement: nothing is claimed by it, and the alternative "
            "is a required primary key left null"
        ),
        "seed": (
            "the run's master seed on every row. The per-asset draws come off "
            "the counter-based seed tree, which derives a generator from the "
            "master seed and a (stream, entity, sim_day) key rather than "
            "storing a per-asset seed, so the master seed is the only seed "
            "that exists to record"
        ),
    }
    return rows, provenance


def export_d04(ctx: RunContext) -> dict[str, Any]:
    """D04 for the assets the frozen model parameterises."""
    rows, provenance = build_d04_rows(ctx)
    frame = pd.DataFrame(rows).sort_values(
        ["building_id", "asset_class", "asset_id"]).reset_index(drop=True)
    by_class = {
        k: int(v) for k, v in
        frame["asset_class"].value_counts().sort_index().items()
    }
    n_sig = int(frame["signature_id"].notna().sum())
    n_appl = by_class.get("appliance", 0)
    return emit(
        frame, "D04", ctx,
        source=(
            "the rebuilt slice's own asset state (engine.e1_run.build_slice: "
            "owned, pv, thermal, has_battery, has_ev) plus the run's own D13 "
            "rows for signature_id"
        ),
        conversions=[
            {"field": "install_date",
             "from": "engine.e1_run._draw_stock's age_years",
             "rule": "t0 - age_years x 365.25, floored to the day",
             "applies_to": "appliance rows only"},
            {"field": "rated_power_w",
             "from": "der.PVSystem.inverter_kw",
             "rule": "kW -> W, x 1000",
             "applies_to": "pv rows only"},
        ],
        limitations=[
            "t0 state only: every row is version 1 with an open valid_to. D04 "
            "declares grain 'asset x version' and the version history is "
            "driven by D03 passport events, of which this run applies "
            f"{int(ctx.diagnostics.get('n_passport_effects_applied') or 0)} to "
            "an asset",
            f"{n_sig} of {n_appl} appliance rows carry a signature_id: the "
            "rest ran no D13 cycle in this run, and an appliance that never "
            "ran leaves no record of which signature it keys into",
            "every non-appliance row carries a MINTED asset_id; "
            "the engine mints one only for appliances",
            "every required column this dataset cannot fill is listed in "
            "null_required_fields in the part's manifest, with its reason",
        ],
        extra={
            "d04_rows_by_asset_class": by_class,
            "d04_truth_provenance": provenance,
            "d04_null_optional_fields": dict(sorted(NULL_OPTIONAL.items())),
            "d04_engine_constants_mirrored": {
                "BESS_CAPACITY_WH": BESS_CAPACITY_WH,
                "BESS_MAX_CHARGE_W": BESS_MAX_CHARGE_W,
                "BESS_MAX_DISCHARGE_W": BESS_MAX_DISCHARGE_W,
                "BESS_ROUND_TRIP_EFFICIENCY": BESS_ROUND_TRIP_EFFICIENCY,
                "EV_BATTERY_WH": EV_BATTERY_WH,
                "EV_CHARGER_W": EV_CHARGER_W,
                "HEAT_PUMP_COP_AT_7C": HEAT_PUMP_COP_AT_7C,
                "DIRECT_ELECTRIC_EFFICIENCY": DIRECT_ELECTRIC_EFFICIENCY,
                "asserted_by": "scripts/tests/test_export_d04_d24.py",
            },
        },
        null_required=dict(NULL_REQUIRED),
    )
