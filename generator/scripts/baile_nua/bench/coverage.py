"""Archetype coverage: does the engine run every KIND of dwelling?

The E1 estate is one real estate, and a real estate is homogeneous. Cobh's
small areas 047106015 and 047106012 are modern: **84% of the estate is A or B
rated, its mean build year is 2005 against the town's 1974, and 49 of its 50
homes heat with gas**. There is no D, E, F or G rated dwelling in it, no heat
pump, no storage heater, no oil boiler and no solid fuel.

That is faithful - it is what those streets are - and it leaves a hole. A
year of the estate never executes the heat-pump COP path, the storage-heater
schedule, or the physics of a G-rated dwelling with a specific heat loss four
times the estate's. Those paths have unit tests; they have never been run
through a whole day of the real pipeline.

So this is a separate, smaller run over a deliberately **diverse** set of
dwellings drawn from the whole town, and it is labelled as coverage rather
than presented as part of the estate. It answers one question: does every
archetype the town contains survive a day of the full pipeline, with the
energy balance closing and the temperatures plausible? It makes no claim about
realism, and its homes are not an estate - they do not share a feeder and are
not contiguous.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

__all__ = ["run_archetype_coverage"]

#: The dimensions coverage is measured over, and why each one matters.
COVERAGE_DIMENSIONS: dict[str, str] = {
    "heating_system": "the heat-pump COP path, storage-heater scheduling and "
                      "the direct-electric COP-1 path are different code",
    "ber_letter": "specific heat loss ranges from about 1.5 to 4.8 W/K/m2 "
                  "across the bands, so the solver's stiffness varies with it",
    "dwelling_type": "party-wall fraction and glazing area differ by type",
    "sensor_tier": "T1 carries two channels and T4 carries ten",
}


def run_archetype_coverage(
    *,
    master_seed: int,
    days: int = 7,
    out_path: Path | None = None,
    per_cell: int = 2,
) -> dict[str, Any]:
    """Run ``days`` days over a diverse sample and report what was exercised."""
    import baile_nua.sources_registry  # noqa: F401
    from baile_nua import CLAIM, LABEL
    from baile_nua.engine.calendar import build_calendar
    from baile_nua.engine.e1_run import build_slice
    from baile_nua.engine.e1_run import build_runner
    from baile_nua.lifecourse.events import draw_disruptions
    from baile_nua.population.synthesise import synthesise_t0
    from baile_nua.rng import SeedTree
    from baile_nua.weather.site import build_realisation

    town = synthesise_t0(master_seed=master_seed)
    wx = build_realisation(2022, master_seed=master_seed, days=days + 1)
    calendar = build_calendar(2022, weather_hourly=wx.site_hourly)[:days]
    tree = SeedTree(master_seed)

    # ---- pick a diverse sample ------------------------------------------
    #
    # Stratified on heating system first, because that is the dimension with
    # genuinely different code behind it, then topped up to cover every BER
    # letter and dwelling type that the town contains at all.
    by_hh = {b.household_id: b for b in town.buildings if b.household_id}
    chosen: dict[str, Any] = {}

    def want(key: str, value: Any) -> list[str]:
        return sorted(
            h for h, b in by_hh.items()
            if (getattr(b, key) if key != "ber_letter" else b.ber_band[0]) == value
        )

    for dim in ("heating_system", "ber_letter", "dwelling_type", "sensor_tier"):
        values = sorted({
            (b.ber_band[0] if dim == "ber_letter" else getattr(b, dim))
            for b in by_hh.values()
        })
        for value in values:
            pool = [h for h in want(dim, value) if h not in chosen]
            have = sum(
                1 for h, b in chosen.items()
                if (b.ber_band[0] if dim == "ber_letter" else getattr(b, dim)) == value
            )
            for h in pool[: max(per_cell - have, 0)]:
                chosen[h] = by_hh[h]

    hh_ids = sorted(chosen)

    # ---- build the slice over exactly those homes ------------------------
    #
    # build_slice selects its own estate, so this reuses the town-wide
    # synthesis and assembles the pieces directly rather than pretending the
    # sample is an estate.
    full = build_slice(town, master_seed=master_seed, calendar=build_calendar(2022))
    from baile_nua.engine.e1_run import _draw_stock
    from baile_nua.physics.rc import ThermalParams
    from baile_nua.activity.engine import PersonProfile

    states = town.states.set_index("person_id")
    persons = town.persons.set_index("person_id")
    ref = pd.Timestamp("2022-01-01")
    households: dict[str, list[PersonProfile]] = {}
    for row in town.states.itertuples():
        if row.household_id not in chosen:
            continue
        p = persons.loc[row.person_id]
        households.setdefault(row.household_id, []).append(
            PersonProfile(
                person_id=row.person_id,
                age=int((ref.date() - p.birth_date).days // 365.25),
                sex=str(p.sex), role=str(row.role), econ_status=str(row.econ_status),
                work_pattern=str(row.work_pattern), remote_share=float(row.remote_share),
                chronotype=float(p.chronotype), habit_strength=float(p.habit_strength),
                lapse_rate=float(p.lapse_rate), attention=float(p.attention),
                comfort=float(p.comfort), health_state=str(row.health_state),
                caring_load=str(row.caring_load),
                school_year=(int(row.school_year) if not pd.isna(row.school_year) else None),
                vehicle_access=str(row.vehicle_access),
            )
        )
    hh_ids = [h for h in hh_ids if h in households]
    buildings = {h: chosen[h] for h in hh_ids}
    thermal = {
        h: ThermalParams(
            r_ie=b.rc.r_ie, r_ea=b.rc.r_ea, r_zz=b.rc.r_zz, r_inf=b.rc.r_inf,
            c_living=b.rc.c_living, c_sleep=b.rc.c_sleep, c_env=b.rc.c_env,
            solar_aperture_m2=b.rc.solar_aperture_m2,
            vol_living_m3=b.rc.vol_living_m3, vol_sleep_m3=b.rc.vol_sleep_m3,
            ach_base=b.rc.ach_base, heat_emitter_w=b.rc.heat_emitter_w,
        )
        for h, b in buildings.items()
    }
    owned = {
        h: _draw_stock(
            tree.generator(__import__(
                "baile_nua.rng", fromlist=["Stream"]).Stream.APPLIANCE_STOCK,
                entity=h, sim_day=0),
            n_people=len(households[h]), building=buildings[h],
        )
        for h in hh_ids
    }
    month_of_day = [d.month for d in build_calendar(2022)]
    disruptions = {
        h: draw_disruptions(
            household_id=h, person_ids=[p.person_id for p in households[h]],
            worker_ids=[p.person_id for p in households[h] if p.is_worker],
            seed_tree=tree, year_days=365, month_of_day=month_of_day,
        )
        for h in hh_ids
    }

    # Through the factory, like every other caller (I-084). This harness
    # builds its own households rather than taking an E1Slice, and they carry
    # no income quintile - so None is passed EXPLICITLY. The argument has no
    # default, which is the point: the last omission of it was silent.
    runner = build_runner(
        master_seed=master_seed, calendar=calendar, households=households,
        buildings=buildings, thermal=thermal, owned=owned, pv={},
        weather_minute=wx.site_minute, income_quintile=None,
    )

    rows: list[dict[str, Any]] = []
    worst_physics = worst_closure = 0.0
    for day in calendar:
        exchange = runner.phase_a(day, disruptions)
        result = runner.run_day(day, exchange)
        worst_physics = max(worst_physics, result.diagnostics["max_physics_relative_residual"])
        worst_closure = max(worst_closure, result.diagnostics["max_energy_closure_relative_residual"])
        for r in result.energy_rows:
            rows.append({**r, "sim_day": day.sim_day})

    frame = pd.DataFrame(rows)
    bid_to_hh = {b.building_id: h for h, b in buildings.items()}
    frame["heating_system"] = [buildings[bid_to_hh[b]].heating_system for b in frame.building_id]
    frame["ber_letter"] = [buildings[bid_to_hh[b]].ber_band[0] for b in frame.building_id]
    frame["dwelling_type"] = [buildings[bid_to_hh[b]].dwelling_type for b in frame.building_id]
    frame["sensor_tier"] = [buildings[bid_to_hh[b]].sensor_tier for b in frame.building_id]

    town_values = {
        "heating_system": sorted({b.heating_system for b in by_hh.values()}),
        "ber_letter": sorted({b.ber_band[0] for b in by_hh.values()}),
        "dwelling_type": sorted({b.dwelling_type for b in by_hh.values()}),
        "sensor_tier": sorted({b.sensor_tier for b in by_hh.values()}),
    }
    coverage: dict[str, Any] = {}
    for dim, values in town_values.items():
        ran = sorted(set(frame[dim].unique()))
        coverage[dim] = {
            "in_the_town": values,
            "exercised": ran,
            "missing": sorted(set(values) - set(ran)),
            "complete": not (set(values) - set(ran)),
            "why_it_matters": COVERAGE_DIMENSIONS[dim],
            "per_value": {
                str(v): {
                    "n_home_days": int((frame[dim] == v).sum()),
                    "mean_heat_kwh_day": round(
                        float(frame.loc[frame[dim] == v, "heat_delivered_kwh"].mean()), 2
                    ),
                    "mean_living_temp_c": round(
                        float(frame.loc[frame[dim] == v, "temp_living_mean_c"].mean()), 2
                    ),
                    "min_living_temp_c": round(
                        float(frame.loc[frame[dim] == v, "temp_living_min_c"].min()), 2
                    ),
                }
                for v in ran
            },
        }

    out = {
        "label": LABEL,
        "claim": CLAIM,
        "purpose": (
            "Archetype COVERAGE, not an estate. These homes are drawn from "
            "across the town to exercise every archetype the engine contains; "
            "they are not contiguous, do not share a feeder, and are not the "
            "E1 estate. No realism claim whatever."
        ),
        "master_seed": master_seed,
        "n_days": len(calendar),
        "n_homes": len(hh_ids),
        "n_home_days": int(len(frame)),
        "max_physics_relative_residual": worst_physics,
        "max_energy_closure_relative_residual": worst_closure,
        "coverage": coverage,
        "all_dimensions_complete": all(c["complete"] for c in coverage.values()),
        "estate_homogeneity_this_addresses": {
            "note": (
                "The E1 estate is 84% A or B rated with a mean build year of "
                "2005 and 49 of 50 homes on gas, because that is what Cobh's "
                "small areas 047106015 and 047106012 are. Faithful, and no "
                "coverage of the rest of the library."
            ),
        },
    }
    if out_path is not None:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(
            json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8"
        )
    return out
