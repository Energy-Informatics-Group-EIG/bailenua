"""The E1 slice driver: 50 homes, ~140 people, calendar year 2022 (E0-7).

Assembles everything into the run design 9.2 requires of E1:

    A complete one-year run of the 50-home, about 140-person estate,
    integrating weather, occupancy, appliances, physics and observation, with at
    least one life event and one disruption, and replayed deterministically.

**How the estate is chosen.**  The 50 homes are the largest contiguous block
from one small area, falling back to adjacent small areas in sorted code order
until 50 are found.  Contiguity matters: design 6.4 item 6 wants a sub-metered
*subset*, R01 wants estates, and a scattered sample of 50 homes from across the
town would not be an estate and could not share a feeder.
"""

from __future__ import annotations

import dataclasses
import json
import os
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from baile_nua.activity.engine import PersonProfile
from baile_nua.config import ScopeError, assert_within_e1_scope, e1_scope
from baile_nua.devices import der as der_mod
from baile_nua.engine.calendar import build_calendar
from baile_nua.engine.run import EPOCH_MINUTES, MINUTES_PER_DAY, EstateRunner, NETWORK_CLAIM
from baile_nua.engine.stream_writer import StreamWriter
from baile_nua.lifecourse.events import draw_disruptions, mary_scenario
from baile_nua.physics import passport_assets as assets_mod
from baile_nua.physics.rc import ThermalParams
from baile_nua.rng import SeedTree, Stream

__all__ = [
    "E1Slice",
    "PlausibilityFailure",
    "select_estate",
    "build_slice",
    "build_runner",
    "build_runner_for_slice",
    "run_year",
]


class PlausibilityFailure(RuntimeError):
    """A written package contradicts a published Irish reference (U27).

    Raised AFTER the package is written, so the thing that was rejected can be
    looked at. A gate failure that deletes its own evidence is worse than one
    that reports it.
    """


@dataclasses.dataclass
class E1Slice:
    household_ids: list[str]
    households: dict[str, list[PersonProfile]]
    buildings: dict[str, Any]
    thermal: dict[str, ThermalParams]
    owned: dict[str, dict[str, dict[str, Any]]]
    pv: dict[str, der_mod.PVSystem]
    disruptions: dict[str, list[Any]]
    mary: dict[str, Any]
    diagnostics: dict[str, Any]
    #: U22. Income quintile per household, from `town.states`, which is what
    #: the comfort-taking mechanism's affordability term needs. Carried on the
    #: slice rather than looked up in the runner so the runner keeps taking a
    #: narrow view of the population (the same reason PersonProfile is narrow).
    income_quintile: dict[str, int] = dataclasses.field(default_factory=dict)


def select_estate(
    town: Any, *, n_homes: int, target_people: int, master_seed: int
) -> dict[str, Any]:
    """Pick the estate: a contiguous block of ``n_homes``, sized to E0-7.

    Two properties are wanted at once and they pull against each other.

    *Contiguity.*  Design 6.4 item 6 wants a sub-metered **subset** and R01
    wants estates, so the 50 homes must be neighbours sharing a feeder, not 50
    homes scattered across the town.  The unit of contiguity available is the
    small area, and adjacency between small areas is measured from the OSi
    centroids - real distance, not alphabetical order.

    *Representativeness.*  E0-7 fixes **both** 50 homes and about 140 people,
    which is 2.8 people per home against the town's 2.671.  Cobh's small areas
    genuinely range from about 2.0 to 3.4 people per household, so most
    contiguous blocks of 50 miss 140 badly: the first version of this function
    returned 176 people.

    The starting small area is therefore chosen as the one whose own mean
    household size is closest to the town's, among areas large enough to form
    most of an estate.  That is a selection on the outcome and is declared as
    such: the alternative, taking the largest or the first area, buys spatial
    tidiness at the cost of a slice that is not a miniature of the town, and E1
    exists to exercise the engine on a miniature of the town.

    Order **within** an area is a seeded permutation, never ``building_id``
    order.  Building ids are assigned household-size-descending, so taking "the
    first 40 of 44" by id silently takes the forty biggest households - which is
    what inflated the first estate to 3.52 people per home.
    """
    by_area: dict[str, list[Any]] = {}
    for b in town.buildings:
        if b.household_id:
            by_area.setdefault(b.small_area, []).append(b)
    size = town.states.groupby("household_id").size().to_dict()

    def area_people(sa: str) -> int:
        return sum(int(size.get(b.household_id, 0)) for b in by_area[sa])

    town_mean = sum(size.values()) / max(len(size), 1)
    # Large enough to supply most of the estate on its own, so the fill from
    # neighbours is a minority of the homes.
    eligible = [sa for sa in by_area if len(by_area[sa]) >= int(0.6 * n_homes)]
    if not eligible:
        eligible = sorted(by_area, key=lambda sa: -len(by_area[sa]))[:5]
    seed_area = min(
        sorted(eligible),
        key=lambda sa: abs(area_people(sa) / len(by_area[sa]) - town_mean),
    )

    # Neighbours of the seed area, nearest first, by centroid distance.
    from baile_nua.population import saps

    cents = saps.cobh_small_areas().frame.set_index("sa_code")
    if seed_area in cents.index:
        lon0 = float(cents.at[seed_area, "centroid_lon"])
        lat0 = float(cents.at[seed_area, "centroid_lat"])

        def dist(sa: str) -> float:
            if sa not in cents.index:
                return float("inf")
            dlon = (float(cents.at[sa, "centroid_lon"]) - lon0) * np.cos(np.radians(lat0))
            dlat = float(cents.at[sa, "centroid_lat"]) - lat0
            return float(np.hypot(dlon, dlat))
    else:                                   # pragma: no cover - defensive
        def dist(sa: str) -> float:
            return 0.0 if sa == seed_area else 1.0

    order = sorted(by_area, key=lambda sa: (dist(sa), sa))
    tree = SeedTree(master_seed)
    picked: list[str] = []
    used: list[str] = []
    for sa in order:
        if len(picked) >= n_homes:
            break
        homes = sorted(by_area[sa], key=lambda x: x.building_id)
        gen = tree.generator(Stream.ESTATE_SELECTION, entity=sa, sim_day=0)
        perm = gen.permutation(len(homes))
        for i in perm:
            if len(picked) >= n_homes:
                break
            picked.append(homes[int(i)].household_id)
        used.append(sa)
    if len(picked) < n_homes:
        raise RuntimeError(
            f"only {len(picked)} households available; the E1 slice needs {n_homes}"
        )
    picked = sorted(picked)
    people = sum(int(size.get(h, 0)) for h in picked)
    return {
        "household_ids": picked,
        "small_areas": used,
        "seed_area": seed_area,
        "n_people": people,
        "people_per_home": round(people / n_homes, 3),
        "town_people_per_home": round(town_mean, 3),
        "target_people": target_people,
        "deviation_from_target_people": people - target_people,
        "selection_rule": (
            "seed small area chosen for mean household size closest to the "
            "town's, then nearest neighbours by OSi centroid distance; order "
            "within an area is a seeded permutation, never building_id order"
        ),
    }


def build_slice(
    town: Any,
    *,
    master_seed: int,
    n_homes: int | None = None,
    calendar: list[Any] | None = None,
    slice_kind: str = "e1_estate",
    frozen_household_ids: tuple[str, ...] | None = None,
) -> E1Slice:
    """Build a slice from the synthesised town.

    ``slice_kind`` selects which. ``"e1_estate"`` is the E1 estate, kept as a
    regression fixture on U23's instruction and still the default so that
    every E1 artefact reproduces unchanged. ``"u23_mixed_age"`` is the week 2
    slice: older, with a BER spread reaching D to G and the DER archetypes
    U23 requires.
    """
    # Which approved slice applies depends on which slice is being built.
    scope_name = {
        "u23_mixed_age": "week2_slice",
        "u31_heldout": "heldout_slice",
        "town": "town_scaleup",
    }.get(slice_kind, "slice")
    scope = e1_scope()[scope_name]
    n_homes = n_homes or int(scope["n_homes"])
    assert_within_e1_scope(
        n_homes=n_homes, coupling_mode=scope["coupling_mode"],
        year=int(scope["calendar_year"]), scope_name=scope_name,
    )
    tree = SeedTree(master_seed)
    if slice_kind == "u23_mixed_age":
        from baile_nua.engine.slice_u23 import select_mixed_age_slice

        chosen = select_mixed_age_slice(
            town, n_homes=n_homes,
            target_people=int(scope["n_people_target"]),
            people_tolerance=int(scope["n_people_tolerance"]),
            master_seed=master_seed,
        )
        estate = {"household_ids": chosen.household_ids, **chosen.diagnostics}
    elif slice_kind == "u31_heldout":
        from baile_nua.engine.slice_u31 import select_heldout_slice

        chosen = select_heldout_slice(
            town, n_homes=n_homes, master_seed=master_seed,
            frozen_household_ids=frozen_household_ids,
        )
        estate = {"household_ids": chosen.household_ids, **chosen.diagnostics}
    elif slice_kind == "town":
        # WP7, D-079. No selection at all, which is the point: a town "slice"
        # that chose dwellings would be a slice, and the week-3 criteria -
        # venue presence against person presence, feeder loading - are about
        # the whole town. Every dwelling the synthesis produced, in id order.
        ids = sorted(b.household_id for b in town.buildings
                     if b.household_id is not None)
        estate = {
            "household_ids": tuple(ids),
            "selection": "none: every dwelling in the town",
            "n_homes": len(ids),
        }
    elif slice_kind == "e1_estate":
        estate = select_estate(
            town, n_homes=n_homes, target_people=int(scope["n_people_target"]),
            master_seed=master_seed,
        )
    else:
        raise ValueError(
            f"unknown slice_kind {slice_kind!r}; expected 'u23_mixed_age' (the "
            f"week 2 slice), 'u31_heldout' (U22's held-out validation slice), "
            f"'town' (WP7's full-town scale-up, D-079) or 'e1_estate' (the "
            f"regression fixture U23 says to keep)"
        )
    hh_set = set(estate["household_ids"])

    b_by_hh = {b.household_id: b for b in town.buildings if b.household_id in hh_set}
    persons = town.persons.set_index("person_id")
    ref = pd.Timestamp("2022-01-01")

    households: dict[str, list[PersonProfile]] = {}
    for row in town.states.itertuples():
        if row.household_id not in hh_set:
            continue
        p = persons.loc[row.person_id]
        age = int((ref.date() - p.birth_date).days // 365.25)
        households.setdefault(row.household_id, []).append(
            PersonProfile(
                person_id=row.person_id, age=age, sex=str(p.sex), role=str(row.role),
                econ_status=str(row.econ_status), work_pattern=str(row.work_pattern),
                remote_share=float(row.remote_share), chronotype=float(p.chronotype),
                habit_strength=float(p.habit_strength), lapse_rate=float(p.lapse_rate),
                attention=float(p.attention), comfort=float(p.comfort),
                health_state=str(row.health_state), caring_load=str(row.caring_load),
                school_year=(int(row.school_year) if not pd.isna(row.school_year) else None),
                vehicle_access=str(row.vehicle_access),
            )
        )

    thermal: dict[str, ThermalParams] = {}
    owned: dict[str, dict[str, dict[str, Any]]] = {}
    pv: dict[str, der_mod.PVSystem] = {}
    for hh_id, b in sorted(b_by_hh.items()):
        thermal[hh_id] = ThermalParams(
            r_ie=b.rc.r_ie, r_ea=b.rc.r_ea, r_zz=b.rc.r_zz, r_inf=b.rc.r_inf,
            c_living=b.rc.c_living, c_sleep=b.rc.c_sleep, c_env=b.rc.c_env,
            solar_aperture_m2=b.rc.solar_aperture_m2,
            vol_living_m3=b.rc.vol_living_m3, vol_sleep_m3=b.rc.vol_sleep_m3,
            ach_base=b.rc.ach_base, heat_emitter_w=b.rc.heat_emitter_w,
        )
        gen = tree.generator(Stream.APPLIANCE_STOCK, entity=hh_id, sim_day=0)
        dgen = tree.generator(Stream.DER_STOCK, entity=hh_id, sim_day=0)
        n_people = len(households.get(hh_id, []))
        owned[hh_id] = _draw_stock(gen, n_people=n_people, building=b)

        # DER at t0: PV, battery and EV adoption, gated on tenure and roof as
        # design 5.9's DER row requires (a renter does not fit panels).
        is_owner = "owner" in str(b.tenure)
        has_roof = b.dwelling_type in ("detached", "semi-detached", "terraced")
        p_pv = 0.16 if (is_owner and has_roof) else 0.01
        if float(dgen.random()) < p_pv:
            kwp = float(np.clip(dgen.normal(4.0, 1.2), 1.5, 8.0))
            pv[hh_id] = der_mod.PVSystem(
                capacity_kwp=kwp,
                azimuth_deg=float(np.clip(dgen.normal(180.0, 40.0), 90.0, 270.0)),
                tilt_deg=float(np.clip(dgen.normal(32.0, 6.0), 12.0, 45.0)),
                inverter_kw=min(kwp * 0.92, 5.0),
                shading_factor=float(np.clip(dgen.normal(0.94, 0.05), 0.70, 1.0)),
            )
        b.has_battery = bool(hh_id in pv and float(dgen.random()) < 0.35)
        b.has_ev = bool(is_owner and float(dgen.random()) < 0.14)

    # ---- U23: guarantee at least one of each required DER -----------------
    #
    # PV, battery and EV adoption are stochastic draws, so a 50-home slice can
    # legitimately come out with none of a kind: at p=0.35 of PV homes, the
    # expected battery count in a slice with five PV systems is under two and
    # zero is perfectly possible. U23 requires at least one of each because the
    # slice exists to exercise those code paths.
    #
    # So where a draw yields none, the adoption is assigned to the home with
    # the highest propensity under the SAME model rather than to an arbitrary
    # one, and the assignment is recorded. This is a declared guarantee, not a
    # correction to the adoption model: the model's rates are unchanged and the
    # town-wide draw is untouched.
    der_guarantees: list[dict[str, Any]] = []
    if slice_kind == "u23_mixed_age":
        def propensity(hh_id: str) -> tuple[float, str]:
            b = b_by_hh[hh_id]
            owner = 1.0 if "owner" in str(b.tenure) else 0.0
            roof = 1.0 if b.dwelling_type in (
                "detached", "semi-detached", "terraced"
            ) else 0.0
            return (owner + roof + b.floor_area_m2 / 1000.0, hh_id)

        if not pv:
            best = max(sorted(b_by_hh), key=propensity)
            gen = tree.generator(Stream.DER_STOCK, entity=f"guarantee-pv-{best}")
            kwp = float(np.clip(gen.normal(4.0, 1.2), 1.5, 8.0))
            pv[best] = der_mod.PVSystem(
                capacity_kwp=kwp,
                azimuth_deg=float(np.clip(gen.normal(180.0, 40.0), 90.0, 270.0)),
                tilt_deg=float(np.clip(gen.normal(32.0, 6.0), 12.0, 45.0)),
                inverter_kw=min(kwp * 0.92, 5.0),
                shading_factor=float(np.clip(gen.normal(0.94, 0.05), 0.70, 1.0)),
            )
            der_guarantees.append({
                "der": "PV", "household_id": best,
                "reason": "the stochastic draw yielded none in this slice",
            })
        if not any(getattr(b, "has_battery", False) for b in b_by_hh.values()):
            host = sorted(pv)[0]
            b_by_hh[host].has_battery = True
            der_guarantees.append({
                "der": "BESS", "household_id": host,
                "reason": (
                    "none drawn; assigned to a PV home, since the adoption "
                    "model only ever pairs a battery with PV"
                ),
            })
        if not any(getattr(b, "has_ev", False) for b in b_by_hh.values()):
            best = max(
                (h for h, b in b_by_hh.items() if "owner" in str(b.tenure)),
                key=propensity, default=sorted(b_by_hh)[0],
            )
            b_by_hh[best].has_ev = True
            der_guarantees.append({
                "der": "EV", "household_id": best,
                "reason": "none drawn; assigned to the highest-propensity owner",
            })

    # ---- disruptions for the year (at least one, by construction) ---------
    # The disruption schedule is always a WHOLE year, even when the run is a
    # few days: illness is seasonal, and drawing a year's disruptions against a
    # three-day month table would make January the only month that exists.
    # A short run then simply encounters the first few days of that schedule,
    # which is what a short run should be - a prefix of the year, not a
    # different year.
    full_year = calendar if (calendar and len(calendar) >= 365) else build_calendar(2022)
    month_of_day = [d.month for d in full_year]
    disruptions: dict[str, list[Any]] = {}
    for hh_id, people in sorted(households.items()):
        disruptions[hh_id] = draw_disruptions(
            household_id=hh_id,
            person_ids=[p.person_id for p in people],
            worker_ids=[p.person_id for p in people if p.is_worker],
            seed_tree=tree, year_days=365, month_of_day=month_of_day,
        )

    # ---- the Mary scenario: the life event E1 requires ---------------------
    mary_hh = _pick_mary_household(households, b_by_hh)
    mary_event, mary_labels = mary_scenario(
        household_id=mary_hh["household_id"],
        building_id=mary_hh["building_id"],
        mary_person_id=mary_hh["mary_person_id"],
        incoming_person_ids=[f"P-MARY-IN-{i + 1}" for i in range(4)],
        move_in_day=mary_hh["move_in_day"],
    )

    n_people = sum(len(v) for v in households.values())
    # U31's held-out slice is not people-band constrained, and the scope says
    # so explicitly rather than by omitting a key: E0-7's band sizes the
    # SIMULATED slice, and this one's constraint is enough gas dwellings in
    # each construction group to take a mean. Forcing the band would fight the
    # stratification the comparison depends on.
    if not scope.get("people_band_applies", True):
        tol = target = None
    else:
        tol = int(scope["n_people_tolerance"])
        target = int(scope["n_people_target"])
    if target is not None and abs(n_people - target) > tol:
        raise ScopeError(
            f"the estate holds {n_people} people; E0-7 says about {target} and "
            f"e1_scope.yaml allows +/-{tol}. Widening the tolerance to admit "
            f"this estate would be weakening an acceptance condition: fix the "
            f"selection instead (the usual cause is an order that correlates "
            f"with household size)."
        )
    # U22: income quintile per household, for the comfort-taking affordability
    # term. Household-level in Census terms and drawn once per household by
    # the population layer, so the first row per household is the household's.
    quintile: dict[str, int] = {}
    if hasattr(town, "states") and "income_quintile" in town.states.columns:
        for hh, q in (
            town.states.groupby("household_id").income_quintile.first().items()
        ):
            if hh in b_by_hh:
                quintile[str(hh)] = int(q)

    return E1Slice(
        household_ids=estate["household_ids"],
        households=households, buildings=b_by_hh, thermal=thermal,
        owned=owned, pv=pv, disruptions=disruptions,
        income_quintile=quintile,
        mary={
            "event": dataclasses.asdict(mary_event),
            "labels": [dataclasses.asdict(l) for l in mary_labels],
            "household": mary_hh,
        },
        diagnostics={
            "n_homes": len(b_by_hh),
            "n_people": n_people,
            "people_per_home": round(n_people / max(len(b_by_hh), 1), 3),
            "small_areas": sorted({b.small_area for b in b_by_hh.values()}),
            "n_with_pv": len(pv),
            "n_with_battery": sum(1 for b in b_by_hh.values() if getattr(b, "has_battery", False)),
            "n_with_ev": sum(1 for b in b_by_hh.values() if getattr(b, "has_ev", False)),
            "sensor_tiers": {
                t: sum(1 for b in b_by_hh.values() if b.sensor_tier == t)
                for t in ("T1", "T2", "T3", "T4")
            },
            "heating_systems": {
                s: sum(1 for b in b_by_hh.values() if b.heating_system == s)
                for s in sorted({b.heating_system for b in b_by_hh.values()})
            },
            "n_disruptions_total": sum(len(v) for v in disruptions.values()),
            "n_life_events": 1,
            "slice_kind": slice_kind,
            "estate_selection": {
                k: v for k, v in estate.items() if k != "household_ids"
            },
            "der_guarantees": der_guarantees,
            "e1_scope_enforced": True,
        },
    )


def _draw_stock(
    gen: np.random.Generator, *, n_people: int, building: Any
) -> dict[str, dict[str, Any]]:
    """Draw a household's appliance stock from the ownership priors."""
    from baile_nua.devices.appliances import OWNERSHIP_PRIORS

    is_owner = "owner" in str(building.tenure)
    out: dict[str, dict[str, Any]] = {}
    for i, (appliance, prior) in enumerate(sorted(OWNERSHIP_PRIORS.items())):
        p = float(prior["base"]) + float(prior.get("per_person", 0.0)) * max(n_people - 2, 0)
        if is_owner:
            p += float(prior.get("owner_bonus", 0.0))
        if appliance == "electric_shower" and building.heating_fuel in ("natural gas",):
            p *= 0.75     # a gas home more often has a mixer shower
        if float(gen.random()) > min(p, 0.999):
            continue
        out[appliance] = {
            "asset_id": f"A-{building.building_id[2:]}-{i:02d}",
            "age_years": float(np.clip(gen.exponential(6.0), 0.1, 25.0)),
            "rated_power_w": 0.0,
        }
    return out


def _pick_mary_household(
    households: dict[str, list[PersonProfile]], buildings: dict[str, Any]
) -> dict[str, Any]:
    """Find the household that best matches Mary: a lone working adult.

    Design 5.9 describes Mary as working 9 to 5 with an EV.  A one-person
    working household is what makes the move-in detectable - the change from one
    occupant to five is the largest structural change the estate can offer, and
    design 5.12's structural tier is what it is meant to test.
    """
    candidates = [
        (hh_id, people) for hh_id, people in sorted(households.items())
        if len(people) == 1 and people[0].is_worker and 30 <= people[0].age <= 65
    ]
    if not candidates:
        candidates = [
            (hh_id, people) for hh_id, people in sorted(households.items())
            if len(people) <= 2
        ]
    if not candidates:
        candidates = sorted(households.items())
    hh_id, people = candidates[0]
    return {
        "household_id": hh_id,
        "building_id": buildings[hh_id].building_id,
        "mary_person_id": people[0].person_id,
        "mary_age": people[0].age,
        "mary_econ_status": people[0].econ_status,
        "household_size_before": len(people),
        "household_size_after": len(people) + 4,
        # Mid-year, so there are months of baseline either side - which design
        # 5.12's structural tier needs ("at least one full weekly cycle" before
        # and after, and holidays and illness ruled out).
        "move_in_day": 188,
        "move_in_date": "2022-07-08",
    }


# --------------------------------------------------------------------------- #
# the year run
# --------------------------------------------------------------------------- #

def build_runner(
    *, master_seed: int, calendar, households, buildings, thermal, owned, pv,
    weather_minute, income_quintile, **extra,
):
    """The ONE place an :class:`EstateRunner` is constructed for the E1 estate.

    I-084. The delivered year passed ``income_quintile=sl.income_quintile``
    and the replay harness did not, so the replay simulated households whose
    comfort shift was computed without their income quintile and compared the
    result against data produced with it. That is not a reproducibility
    failure in the model; it is the harness quietly running a different model,
    and it accounted for all of the residual that was left after I-081: 41 of
    100 sampled home-days, divergence beginning the moment the morning heating
    first mattered and growing through the day to 0.67 C.

    Two things made it survive. The replay reported a state gap, which is
    where a reader looks first, and the determinism arm compared three runs
    against EACH OTHER - all three built the runner the same wrong way, so
    they agreed perfectly and said nothing about whether either matched the
    delivered run.

    So the construction lives here and the callers pass only what they differ
    in. A constructor argument added to the runner is now added in one place,
    and `test_the_harness_builds_the_runner_the_same_way_as_the_run` asserts
    that nothing constructs an EstateRunner outside it.
    """
    runner = EstateRunner(
        master_seed=master_seed, households=households, buildings=buildings,
        thermal=thermal, owned=owned, pv=pv,
        weather_minute=weather_minute, calendar=calendar,
        income_quintile=income_quintile,
        **extra,
    )
    runner.initialise()
    return runner


def build_runner_for_slice(sl, wx, calendar, *, master_seed: int, **extra):
    """:func:`build_runner` for the three callers that have an :class:`E1Slice`.

    ``income_quintile`` has no default in :func:`build_runner` precisely so
    that it cannot be left out again; this passes the slice's own, which is
    what the delivered year passes.
    """
    return build_runner(
        master_seed=master_seed, calendar=calendar,
        households=sl.households, buildings=sl.buildings, thermal=sl.thermal,
        owned=sl.owned, pv=sl.pv, weather_minute=wx.site_minute,
        income_quintile=sl.income_quintile, **extra,
    )


def run_year(
    *,
    master_seed: int,
    out_root: Path,
    checkpoint_root: Path,
    days: int | None = None,
    collect_presence_days: int = 14,
    progress: Any = None,
    slice_kind: str = "e1_estate",
    comfort_taking: bool = True,
    comfort_strength: float = 1.0,
    behaviour: Any = None,
    write_package: bool = True,
    omit_datasets: frozenset[str] = frozenset(),
    slice_transform: Any = None,
    passport_schedule: dict[int, list[Any]] | None = None,
    occupancy_schedule: dict[int, list[dict[str, Any]]] | None = None,
    frozen_household_ids: tuple[str, ...] | None = None,
    solve_network: bool = False,
    with_venues: bool = False,
    year: int = 2022,
    start: str | None = None,
    end: str | None = None,
    sim_day_offset: int = 0,
    restore_from: Any = None,
    d18_era_gating: bool = False,
) -> dict[str, Any]:
    """The E1 run: one estate, one calendar year, every layer engaged.

    ``d18_era_gating`` turns on the per-home D18 observability eras
    (``observation/era.py``, D-101/D-111): no D18 before a home's smart-meter
    install date, 30-minute import and export until its PARA//EL enrolment
    date, and the full 1-minute device mix only from enrolment. Off by default
    for the same reason ``solve_network`` is - every earlier artefact was
    written ungated and must keep reproducing - and the supervisor turns it on
    from the 2019 segment onwards.

    ``with_venues`` loads the WP7 venue layer, so a non-building presence row
    carries the venue it happened at instead of ``location_id=None``. Off by
    default for the same reason as ``solve_network``: every earlier artefact
    was written without it and must keep reproducing.

    ``solve_network`` turns C1 into C2 (design 8.2): the epoch barrier still
    aggregates net power, and now a quasi-static power flow is solved on it
    through :mod:`baile_nua.network.lv`. Off by default, so every E1 and week-2
    artefact reproduces under C1 exactly as it was produced - the mode a run
    used is a property of that run, not something a later week retrofits onto
    it.

    Written to stream rather than to accumulate.  A year of 50 homes at
    1-minute resolution is 26.3 million home-minutes, and holding the minute
    series for every home and day would need tens of gigabytes for no reason:
    each day's rows are appended to a per-dataset buffer and flushed monthly.
    What the benchmark measures is therefore a real streaming run, not a
    best-case fit-in-memory one, which is the honest thing to project the full
    town from.
    """
    import gc
    import resource

    from baile_nua import CLAIM, LABEL
    from baile_nua.population.synthesise import synthesise_t0
    from baile_nua.weather.site import build_realisation

    out_root = Path(out_root)
    checkpoint_root = Path(checkpoint_root)
    t_start = time.time()
    timings: dict[str, float] = {}

    def say(msg: str) -> None:
        if progress is not None:
            progress(msg)

    # ---- the town, the weather, the calendar, the slice -------------------
    t = time.time()
    town = synthesise_t0(master_seed=master_seed)
    timings["town_s"] = round(time.time() - t, 2)
    say(f"town: {len(town.buildings)} homes, {len(town.persons)} people "
        f"in {timings['town_s']}s")

    t = time.time()
    # Phase 2. `year`/`start`/`end` default to the 2022 whole year, so every
    # existing call site produces exactly what it produced before. The chained
    # replay passes a year, or a window for the December-2014 warm-up and the
    # truncated final year, plus a `sim_day_offset` so sim_day runs
    # continuously 0..4290 across the whole span (D-110): the seed tree is
    # keyed on sim_day and restarting it at zero would re-draw an earlier
    # year's random numbers.
    wx = build_realisation(year, master_seed=master_seed, days=days,
                           start=start, end=end)
    timings["weather_s"] = round(time.time() - t, 2)
    if start is not None:
        calendar = build_calendar(start=start, end=end,
                                  weather_hourly=wx.site_hourly,
                                  sim_day_offset=sim_day_offset)
    else:
        calendar = build_calendar(year, weather_hourly=wx.site_hourly,
                                  sim_day_offset=sim_day_offset)
    if days is not None:
        calendar = calendar[:days]
    say(f"weather: {len(wx.site_minute):,} minute rows in {timings['weather_s']}s")

    t = time.time()
    sl = build_slice(town, master_seed=master_seed, calendar=calendar,
                     slice_kind=slice_kind,
                     frozen_household_ids=frozen_household_ids)
    if slice_transform is not None:
        # WP5: the ten-year life course evolves the slice between years -
        # births, deaths, moves, employment and health changes - and hands
        # back the composition for THIS year. Applied here, after selection
        # and before the runner is built, so the life course does not have to
        # know anything about the runner and the runner does not have to know
        # a life course exists.
        sl = slice_transform(sl)
    timings["slice_s"] = round(time.time() - t, 2)
    say(f"slice: {sl.diagnostics['n_homes']} homes, {sl.diagnostics['n_people']} people, "
        f"{sl.diagnostics['n_disruptions_total']} disruptions, 1 life event")

    from baile_nua.physics import retrofit as retrofit_mod

    bid_to_hh_for_passport = {
        b.building_id: hh for hh, b in sl.buildings.items()
    }
    runner = build_runner_for_slice(
        sl, wx, calendar, master_seed=master_seed,
        checkpoint_root=checkpoint_root,
        comfort_taking=comfort_taking,
        comfort_strength=comfort_strength,
        behaviour=behaviour,
        sim_day_origin=sim_day_offset,
    )

    # ---- the year --------------------------------------------------------
    # U22/week 2 step 4. An ablation wants the diagnostics, not the package,
    # and writing D18 and D19 is roughly 60% of the run - 3.5s of 6s a day.
    # Skipping it makes an ablation arm affordable enough to actually run,
    # which is the difference between a mechanism that was compared against
    # its own absence and one that was asserted to work.
    #
    # The default is True, so the delivered path is unchanged: a package that
    # is not written is also not checked by the U27 hook, and that must never
    # be the normal case.
    writer = (
        StreamWriter(out_root, master_seed=master_seed,
                     omit_datasets=omit_datasets,
                     d18_era_gating=d18_era_gating)
        if write_package else None
    )
    day_times: list[float] = []
    write_times: list[float] = []
    physics_residuals: list[float] = []
    closure_residuals: list[float] = []
    feeder_peaks: list[float] = []
    # Week 2 step 4. The annual 15-minute estate profile, accumulated from the
    # per-day aggregate the runner already computes. This makes the load
    # factor, the overnight taper and the peak hour available WITHOUT a written
    # package, which is what lets an ablation arm be measured on them.
    feeder_profile: list[np.ndarray] = []
    network_times: list[float] = []
    asleep_sum: np.ndarray | None = None
    asleep_person_days = 0.0
    asleep_n_days = 0
    annual_wh: dict[str, dict[str, float]] = {}
    chain_head: str | None = None
    n_cycles = n_intervals = 0

    # S11 / C2. Built ONCE: the topology does not change within a run, and
    # rebuilding it per day would make the per-day cost the build cost (about
    # 30s for the full town) rather than the solve cost (about 0.2s an epoch).
    # WP7 venues. Built from the TOWN, not the slice: a school serves the town
    # and a slice of 60 homes would size the stock at one of everything.
    venue_record: dict[str, Any] | None = None
    if with_venues:
        from baile_nua.population import venues as ven_mod

        pframe = ven_mod.person_frame_from_town(town)
        built = ven_mod.build_venues(persons=pframe)
        assignment = ven_mod.assign_persistent_venues(
            persons=pframe, venues=built["venues"], master_seed=master_seed)
        runner.venue_assignment = assignment
        by_type: dict[str, list[str]] = {}
        for v in built["venues"]:
            by_type.setdefault(v.venue_type, []).append(v.venue_id)
        runner.venues_by_type = {k: sorted(v) for k, v in by_type.items()}
        venue_record = {
            "counts": built["counts"],
            "capacities": built["capacities"],
            "demand": built["demand"],
            "school_size_source": built["school_size_source"],
            "a_flag_id": built["a_flag_id"],
            "a_flags": built["a_flags"],
            "counts_are_derived_not_declared":
                built["counts_are_derived_not_declared"],
            "n_assigned_a_school": sum(
                1 for a in assignment.values() if a.get("school_venue_id")),
            "n_assigned_a_workplace": sum(
                1 for a in assignment.values() if a.get("workplace_venue_id")),
            "d01_rows": [v.as_d01_row() for v in built["venues"]],
        }
        if progress:
            progress(
                f"venues: {sum(built['counts'].values())} across "
                f"{len(built['counts'])} types {built['counts']}"
            )

    town_net = None
    network_epochs: list[dict[str, Any]] = []
    # D17 rows are now WRITTEN, one day at a time, so only the count is kept
    # here. Accumulating them for the whole run was a latent memory cost that
    # bought nothing: a town-year at C2 is 365 x 96 epochs x about 123
    # elements, so the discarded list reached roughly four million row dicts
    # in order to report its own length (I-091).
    n_d17_rows = 0
    if solve_network:
        from baile_nua.network import lv as lv_mod

        town_net = lv_mod.build_town_network(buildings=sl.buildings)
        if progress:
            progress(
                f"network: {town_net.diagnostics['n_connections']} connections, "
                f"{town_net.diagnostics['n_substations']} substations, "
                f"{town_net.diagnostics['n_feeders']} feeders, "
                f"{town_net.diagnostics['n_buses']} buses (C2)"
            )

    passport_effects: list[dict[str, Any]] = []
    occupancy_effects: list[dict[str, Any]] = []
    # Phase 2 / D-124. The chain restores the previous year's final state here,
    # which is the whole of what a year boundary needs: `HouseholdState` is the
    # model's own definition of "what carries from one day to the next", and a
    # year boundary is just another day boundary. Rehearsal A measured this -
    # 100 home-days over 84 days, 0 mismatches, exact replay - so a restored
    # day reproduces an uninterrupted one.
    #
    # `restore` refuses a partial restore, so a checkpoint from a different
    # slice fails loudly rather than mixing two towns.
    if restore_from is not None:
        n_restored = runner.restore(restore_from)
        if progress:
            progress(f"restored {n_restored} households from "
                     f"sim_day {restore_from.sim_day}")

    for day in calendar:
        t = time.time()
        # I-054. A D03 passport event changes the building FROM ITS DATE: the
        # fabric has one state before and another after, and the version in
        # D03 is the boundary. Applied at the day boundary, before Phase A,
        # so the whole day runs on one consistent fabric - a mid-day change
        # would make the day's energy balance describe two buildings.
        for event in (passport_schedule or {}).get(day.sim_day, ()):
            hh = bid_to_hh_for_passport.get(event.building_id)
            if hh is None or hh not in runner.thermal:
                continue
            building = sl.buildings[hh]
            # I-062. Dispatch on the MEASURE, not on D03's `event_type`:
            # all four DER and heat-pump measures are "asset added", so an
            # engine keying on the event type could only ever apply one of
            # them. Events written before `measure` existed fall back to the
            # event type, which is enough for the two fabric kinds.
            measure = getattr(event, "measure", None) or {
                "retrofit": "retrofit_fabric", "extension": "extension",
            }.get(event.event_type, event.event_type)
            rec: dict[str, Any] = {
                "passport_event_id": getattr(event, "passport_event_id", None),
                "building_id": event.building_id,
                "event_type": event.event_type,
                "measure": measure,
                "effective_day": day.sim_day,
            }

            if measure in ("retrofit_fabric", "extension"):
                tp_before = runner.thermal[hh]
                if measure == "retrofit_fabric":
                    after, effect = retrofit_mod.apply_fabric_retrofit(
                        tp=tp_before, building=building,
                        effective_day=day.sim_day,
                    )
                else:
                    after, effect = retrofit_mod.apply_extension(
                        tp=tp_before, building=building,
                        effective_day=day.sim_day,
                    )
                runner.thermal[hh] = after
                if measure == "extension":
                    building.floor_area_m2 = effect.floor_area_after_m2
                runner.wp5_measures.setdefault(hh, set()).add(measure)
                # I-054. The fabric is not the only thing a fabric event
                # changes. The comfort shift is a standing function of the
                # dwelling's specific heat loss, computed once in the runner's
                # constructor, and a retrofit that leaves it stale changes the
                # fabric without changing the household's response to it -
                # half an event. Same for the hot-water system's standing
                # losses. Re-derived here, and what moved goes in the record.
                rederived = assets_mod.recompute_derived_household_state(
                    runner=runner, hh=hh, building=building,
                )
                rec.update({
                    "hlc_before_w_per_k": effect.hlc_before_w_per_k,
                    "hlc_after_w_per_k": effect.hlc_after_w_per_k,
                    "hlc_ratio": round(effect.hlc_ratio, 4),
                    "floor_area_before_m2": effect.floor_area_before_m2,
                    "floor_area_after_m2": effect.floor_area_after_m2,
                    "u_after": effect.u_after,
                    "source": effect.source,
                    "changed": True,
                    "rederived": rederived,
                })
            elif measure in ("retrofit_heat_pump", "der_smart_controls",
                             "der_pv", "der_battery"):
                gen = runner.tree.generator(
                    Stream.BUILDING_SYSTEMS,
                    entity=f"{hh}:{measure}", sim_day=day.sim_day,
                )
                if measure == "retrofit_heat_pump":
                    eff = assets_mod.apply_heat_pump_retrofit(
                        runner=runner, hh=hh, building=building,
                        effective_day=day.sim_day,
                    )
                elif measure == "der_smart_controls":
                    eff = assets_mod.apply_smart_controls(
                        runner=runner, hh=hh, building=building,
                        effective_day=day.sim_day,
                    )
                elif measure == "der_pv":
                    eff = assets_mod.apply_pv_install(
                        runner=runner, hh=hh, building=building,
                        effective_day=day.sim_day, gen=gen,
                    )
                else:
                    eff = assets_mod.apply_battery_install(
                        runner=runner, hh=hh, building=building,
                        effective_day=day.sim_day, gen=gen,
                    )
                runner.wp5_measures.setdefault(hh, set()).add(measure)
                rec.update(eff.as_record())
            else:
                rec.update({"changed": False, "source": "",
                            "note": f"no dated handler for measure {measure!r}"})
            passport_effects.append(rec)

        # I-054's third kind. No declared quantity: the effect is whatever one
        # more or one fewer person does to the activity engine, the metabolic
        # gains, the hot-water draws and the occupancy gate on the heating.
        for slot in (occupancy_schedule or {}).get(day.sim_day, ()):
            hh = slot["household_key"]
            if hh not in runner.households:
                continue
            eff = assets_mod.apply_occupancy_change(
                runner=runner, hh=hh, building=sl.buildings[hh],
                effective_day=day.sim_day,
                arrivals=tuple(slot.get("arrivals") or ()),
                departures=tuple(slot.get("departures") or ()),
            )
            r = eff.as_record()
            r["source_events"] = slot.get("events")
            if slot.get("unresolved"):
                r["unresolved_person_ids"] = slot["unresolved"]
            occupancy_effects.append(r)
        exchange = runner.phase_a(day, sl.disruptions)
        # Checkpoint BEFORE the day: the checkpoint plus the exchange log are
        # the day's inputs, and that pairing is what the replay test restores.
        chain_head = runner.checkpoint(day, exchange)
        result = runner.run_day(
            day, exchange, collect_presence=(day.sim_day < collect_presence_days)
        )
        day_times.append(time.time() - t)

        physics_residuals.append(result.diagnostics["max_physics_relative_residual"])
        closure_residuals.append(
            result.diagnostics["max_energy_closure_relative_residual"]
        )
        feeder_peaks.append(result.diagnostics["feeder_peak_w"])
        feeder_profile.append(np.asarray(result.feeder_epoch_w, dtype=np.float64))

        d17_day: list[dict[str, Any]] = []
        if town_net is not None:
            from baile_nua.network import lv as lv_mod

            # Timed separately. The first version of this left the power flow
            # between the simulate timer and the write timer, so its cost fell
            # in a gap and `run_s` reported a C2 run as though it had been C1 -
            # and the design's own note says "anyone planning E2 needs the
            # split, not the total".
            tn_t = time.time()
            per = result.net_epoch_w_by_building
            n_epochs = len(result.feeder_epoch_w)
            for e in range(n_epochs):
                # "record", not "raise": a town-scale run must not abort on one
                # over-stressed epoch, and must not skip it either. A flow that
                # will not converge is counted against the week-3 criterion by
                # lv.loading_report.
                r = lv_mod.solve_epoch(
                    town_net,
                    net_w_by_building={b: float(v[e]) for b, v in per.items()},
                    on_nonconvergence="record",
                )
                r["sim_day"] = day.sim_day
                r["epoch"] = e
                # Keep only what `lv.loading_report` reads, plus the two keys
                # that locate an epoch (I-117).
                #
                # The full dict is 10,809 B measured, of which 8,949 B is
                # `feeder_head_loading_pct` (64 feeders) and
                # `trafo_loading_pct` (53 substations) - and
                # `loading_report` reads NEITHER. At 96 epochs a day that is
                # 0.35 GB a year and **4.15 GB over the 4,291-day replay**,
                # retained to compute five aggregates and a length. The
                # reduced dict is 832 B, 8% of it.
                #
                # This matters more than it looks because every segment runs
                # in the SAME process: `ru_maxrss` never resets at a year
                # boundary, so the cost accumulates monotonically across all
                # twelve years and shows up as the step-wise RSS growth that
                # took the gate to 88%.
                #
                # Exactly the shape of I-091, which the comment above
                # `n_d17_rows` describes - that one was found and this one,
                # four lines away, was not.
                #
                # A NON-CONVERGED epoch keeps its full dict: those are rare,
                # they are the only ones worth diagnosing, and
                # `loading_report` counts them against the criterion.
                network_epochs.append(r if not r.get("converged") else {
                    "converged": True,
                    "max_trafo_loading_pct": r["max_trafo_loading_pct"],
                    "max_feeder_loading_pct": r["max_feeder_loading_pct"],
                    "max_line_loading_pct": r["max_line_loading_pct"],
                    "vm_pu_min": r["vm_pu_min"],
                    "sim_day": r["sim_day"],
                    "epoch": r["epoch"],
                })
                if r.get("converged"):
                    ts = day.date + pd.Timedelta(minutes=EPOCH_MINUTES * e)
                    d17_day.extend(lv_mod.d17_rows(
                        town_net, ts=ts, coupling_mode="C2",
                        # The flow is solved on the epoch just ended, so the
                        # load it used is one epoch old at the moment of the
                        # solve. D17 carries that rather than implying the
                        # flow saw the instant it is stamped with.
                        epoch_staleness_s=EPOCH_MINUTES * 60,
                    ))
            network_times.append(time.time() - tn_t)
            n_d17_rows += len(d17_day)
        # I-052. Accumulated as a running sum rather than kept per day: the
        # quantity wanted is the mean day, and 365 x 1440 floats per run is
        # 4 MB for no reason.
        if result.asleep_by_minute is not None:
            asleep_sum = (asleep_sum + result.asleep_by_minute
                          if asleep_sum is not None
                          else result.asleep_by_minute.copy())
            asleep_person_days += result.n_people_total
            asleep_n_days += 1
        n_cycles += result.n_cycles
        n_intervals += result.n_activity_intervals

        for row in result.energy_rows:
            acc = annual_wh.setdefault(
                row["building_id"],
                {k: 0.0 for k in ("appliance_wh", "hvac_wh", "ev_wh", "pv_wh",
                                  "import_wh", "export_wh", "net_meter_wh",
                                  "heat_delivered_kwh",
                                  # U25
                                  "dhw_wh", "dhw_useful_kwh",
                                  "dhw_standby_kwh", "dhw_coil_kwh",
                                  "dhw_immersion_kwh", "dhw_diverted_pv_kwh",
                                  "dhw_litres", "cooking_hob_useful_wh",
                                  "cooking_oven_useful_wh",
                                  # U22. Summed over days, divided below: the
                                  # check that comfort-taking is not buying
                                  # flatness with an implausible indoor
                                  # temperature. PL-TEMP-01 guards the
                                  # package; the ablation has to see it too.
                                  "temp_living_mean_c_days",
                                  "temp_living_min_c_days")},
            )
            for k in acc:
                if k == "temp_living_mean_c_days":
                    acc[k] += float(row.get("temp_living_mean_c", 0.0) or 0.0)
                elif k == "temp_living_min_c_days":
                    acc[k] += float(row.get("temp_living_min_c", 0.0) or 0.0)
                else:
                    acc[k] += float(row.get(k, 0.0) or 0.0)

        tw = time.time()
        if writer is not None:
            if d17_day:
                # Before add_day, which is what flushes: after it, the day's
                # network rows would be filed in the next part.
                writer.add_network_day(day, d17_day, town_net, sl)
            writer.add_day(day, result, runner, sl)
        if day.sim_day % 30 == 29 or day.sim_day == calendar[-1].sim_day:
            if writer is not None:
                writer.flush()
            gc.collect()
        write_times.append(time.time() - tw)
        if day.sim_day % 30 == 29 or day.sim_day == calendar[-1].sim_day:
            say(f"  day {day.sim_day + 1}/{len(calendar)} "
                f"(sim {np.mean(day_times[-30:]):.2f}s + write "
                f"{np.mean(write_times[-30:]):.2f}s per day, "
                f"peak RSS {_peak_rss_mb():,.0f} MB)")

    tw = time.time()
    if writer is not None:
        writer.close()
    write_times.append(time.time() - tw)
    timings["simulate_s"] = round(sum(day_times), 2)
    timings["write_s"] = round(sum(write_times), 2)
    # Kept for continuity, and now explicitly the SUM of the two: the first
    # version called the simulation time alone "run_s" and projected the full
    # town from it, which under-stated the town by about five times, because
    # writing D18 at 1-minute resolution costs several times what simulating it
    # does. A projection that leaves out the dominant term is not a projection.
    # S11 / C2. Its own line, because it is a third cost and not part of
    # either of the other two: 1,344 power flows on the full town's 2,238-bus
    # network is a sixth of a C2 run, and a projection built from
    # simulate + write alone would under-predict C2 by exactly that.
    timings["network_s"] = round(sum(network_times), 2)
    timings["network_share_of_runtime"] = (
        round(timings["network_s"]
              / max(timings["simulate_s"] + timings["write_s"]
                    + timings["network_s"], 1e-9), 4))
    timings["run_s"] = round(
        timings["simulate_s"] + timings["write_s"] + timings["network_s"], 2)
    timings["total_s"] = round(time.time() - t_start, 2)

    # ---- the feeder shape, against ESB Networks LP1 ----------------------
    #
    # Computed here rather than only inside PL-PEAK-01 because an ablation arm
    # writes no package, and "ablations degrade fit as expected" needs the fit
    # to be measurable without one.
    shape: dict[str, Any] = {"measured": False}
    if feeder_profile:
        prof = np.concatenate(feeder_profile)
        positive = prof[prof > 0]
        if positive.size and prof.max() > 0:
            mean_w = float(positive.mean())
            peak_w = float(prof.max())
            per_day = prof.reshape(-1, MINUTES_PER_DAY // 15)
            mean_day = per_day.mean(axis=0)
            hourly = mean_day.reshape(24, 4).mean(axis=1)
            day_mean = float(hourly.mean())
            shape = {
                "measured": True,
                "n_intervals": int(prof.size),
                "interval_minutes": 15,
                "load_factor": round(mean_w / peak_w, 4),
                "peak_w": round(peak_w, 1),
                "mean_day_peak_hour": int(np.argmax(hourly)),
                "mean_day_trough_hour": int(np.argmin(hourly)),
                "overnight_taper_00_over_04": (
                    round(float(hourly[0] / hourly[4]), 4)
                    if hourly[4] > 0 else None
                ),
                "hourly_shape_over_day_mean": {
                    int(h): round(float(v) / day_mean, 4)
                    for h, v in enumerate(hourly)
                },
                "reference": (
                    "ESB Networks LP1 urban domestic 24-hour: load factor "
                    "0.4130, taper 1.721, mean-day peak 18:00, trough 04:00"
                ),
                "note": (
                    "The estate's own aggregate, so its load factor is lower "
                    "than LP1's by construction - LP1 aggregates about two "
                    "million meters. PL-PEAK-01 applies the bounds; this is "
                    "the measurement."
                ),
            }
    # I-052, week 3 step 3. The awake share by hour, from the simulation's own
    # sleep intervals, so the overnight load can be read per awake person. This
    # is the decomposition that separated three confounded things in I-052: the
    # awake count, the standby floor and what awake people are doing.
    awake: dict[str, Any] = {"measured": False}
    if asleep_sum is not None and asleep_n_days and asleep_person_days > 0:
        people_per_day = asleep_person_days / asleep_n_days
        mean_asleep = asleep_sum / asleep_n_days
        awake_share_minute = 1.0 - (mean_asleep / max(people_per_day, 1e-9))
        by_hour = awake_share_minute.reshape(24, 60).mean(axis=1)
        awake = {
            "measured": True,
            "n_days": asleep_n_days,
            "mean_people_per_day": round(people_per_day, 2),
            "awake_share_by_hour": {
                int(h): round(float(v), 6) for h, v in enumerate(by_hour)
            },
            "definition": (
                "the share of the modelled population not in a 'sleep' or "
                "'nap' activity, averaged over every simulated day and over "
                "the sixty minutes of each hour. Wherever they are: a person "
                "awake and out of the house is awake."
            ),
        }
    diagnostics_feeder_shape = shape
    diagnostics_awake = awake

    # ---- benchmark -------------------------------------------------------
    n_homes = sl.diagnostics["n_homes"]
    home_days = n_homes * len(calendar)
    # An ablation arm writes no package, so there is no storage to report.
    # An empty dict rather than a fabricated zero: a projection of 0 GB would
    # be read as a measurement.
    storage = writer.storage_report() if writer is not None else {
        "measured": False,
        "reason": "ablation arm; write_package=False, so nothing was written",
    }
    bench = {
        "machine": _machine(),
        "n_homes": n_homes,
        "n_people": sl.diagnostics["n_people"],
        "n_days": len(calendar),
        "home_days": home_days,
        "home_minutes": home_days * MINUTES_PER_DAY,
        "mean_s_per_day": round(float(np.mean(day_times)), 3),
        "median_s_per_day": round(float(np.median(day_times)), 3),
        "p95_s_per_day": round(float(np.percentile(day_times, 95)), 3),
        "mean_write_s_per_day": round(float(np.mean(write_times)), 3),
        "mean_total_s_per_day": round(
            float(np.mean(day_times)) + float(np.mean(write_times)), 3
        ),
        "ms_per_home_day": round(
            1000.0 * (sum(day_times) + sum(write_times)) / max(home_days, 1), 3
        ),
        "ms_per_home_day_simulation_only": round(
            1000.0 * sum(day_times) / max(home_days, 1), 3
        ),
        "write_share_of_runtime": round(
            sum(write_times) / max(sum(day_times) + sum(write_times), 1e-9), 3
        ),
        "peak_rss_mb": round(_peak_rss_mb(), 1),
        "storage": storage,
        # Phase 12. How much of D18 the run declined to write, and why. An
        # ungated run says so explicitly rather than omitting the key, so a
        # gated and an ungated package are distinguishable from diagnostics
        # alone and nobody has to infer it from a row count.
        "d18_era": (
            writer.era_report() if writer is not None
            else {"d18_era_gating": False}
        ),
        "timings": timings,
    }
    bench["full_town_projection"] = _project_full_town(
        bench, n_town_homes=len(town.buildings)
    )

    diagnostics = {
        "label": LABEL,
        "claim": CLAIM,
        "coupling_mode": "C1",
        # I-054: what the dated passport events actually did to the fabric.
        # Empty when no schedule was supplied, which is every run but the
        # ten-year one.
        "passport_effects": passport_effects,
        "n_passport_effects_applied": len(passport_effects),
        # I-062. An event that reached the physics and moved nothing is NOT
        # an applied effect, and the two counts are reported separately so a
        # reader cannot mistake one for the other again.
        "n_passport_effects_that_changed_the_physics": sum(
            1 for r in passport_effects if r.get("changed")),
        "passport_effects_with_no_rated_effect": [
            {k: r.get(k) for k in
             ("passport_event_id", "measure", "effective_day", "note")}
            for r in passport_effects if not r.get("changed")
        ],
        "occupancy_effects": occupancy_effects,
        "n_occupancy_effects_applied": len(occupancy_effects),
        "network_claim": NETWORK_CLAIM,
        "master_seed": master_seed,
        "slice": sl.diagnostics,
        "mary": sl.mary,
        "n_activity_intervals": n_intervals,
        "n_appliance_cycles": n_cycles,
        "max_physics_relative_residual": max(physics_residuals),
        "max_energy_closure_relative_residual": max(closure_residuals),
        "feeder_peak_w": max(feeder_peaks),
        "feeder_peak_w_per_home": round(max(feeder_peaks) / max(n_homes, 1), 1),
        "checkpoint_chain_head": chain_head,
        "benchmark": bench,
        "feeder_shape": diagnostics_feeder_shape,
        "awake_share": diagnostics_awake,
        "coupling_mode": ("C2" if town_net is not None else "C1"),
        "venues": (venue_record if venue_record is not None else {
            "loaded": False,
            "note": (
                "WP7's venue layer was not loaded, so every non-building "
                "presence row carries location_id=None and the week-3 "
                "criterion 'venue presence consistent with person presence' "
                "cannot be answered from this run. Not answering it is not "
                "the same as passing it."
            ),
        }),
        "network": (
            {
                "topology": town_net.diagnostics,
                "loading": __import__(
                    "baile_nua.network.lv", fromlist=["x"]
                ).loading_report(network_epochs),
                "n_epochs_solved": len(network_epochs),
                "n_d17_rows": n_d17_rows,
            }
            if town_net is not None else
            {
                "solved": False,
                "claim": NETWORK_CLAIM,
            }
        ),
        "behaviour_switches": (
            behaviour.as_dict() if behaviour is not None else None
        ),
        "annual_electricity": _annual_vs_d24(
            annual_wh, sl, n_days=len(calendar), master_seed=master_seed
        ),
    }
    # `run_diagnostics.json` is written whether or not a package is, so the
    # directory has to exist either way. It did not: with write_package=False
    # only the StreamWriter created out_root, so every ablation arm and every
    # network smoke run ended in FileNotFoundError AFTER paying for the whole
    # simulation.
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "run_diagnostics.json").write_text(
        json.dumps(diagnostics, indent=2, default=str) + "\n", encoding="utf-8"
    )

    # ---- U27: the plausibility suite runs on every package write ---------
    #
    # After the diagnostics are written, not before, so that a package which
    # fails is still on disk to be inspected. A suite that aborted the run
    # would destroy the evidence of what it rejected, and thirty minutes of
    # simulation with it.
    if not write_package:
        # No package, nothing to check. Said out loud rather than skipped
        # silently, because "the suite did not run" and "the suite passed"
        # must never look the same in a log.
        say(
            "plausibility: NOT RUN - this is an ablation arm with "
            "write_package=False, so there is no package to check. The "
            "delivered path always writes."
        )
        diagnostics["plausibility"] = {
            "ran": False,
            "reason": "ablation arm; no package written",
        }
        (out_root / "run_diagnostics.json").write_text(
            json.dumps(diagnostics, indent=2, default=str), encoding="utf-8"
        )
        return diagnostics

    from baile_nua.plausibility import write_suite

    plaus = write_suite(
        package_root=out_root,
        out_path=out_root / "evidence" / "plausibility.json",
        diagnostics_path=out_root / "run_diagnostics.json",
    )
    diagnostics["plausibility"] = {
        k: v for k, v in plaus.items() if k != "results"
    }
    (out_root / "run_diagnostics.json").write_text(
        json.dumps(diagnostics, indent=2, default=str) + "\n", encoding="utf-8"
    )
    say(
        f"plausibility: {plaus['n_pass']} pass "
        f"({plaus['n_pass_sourced']} sourced), {plaus['n_fail']} fail, "
        f"{plaus['n_not_evaluable']} not evaluable"
    )
    if not plaus["all_evaluable_checks_pass"]:
        from baile_nua.plausibility.suite import KNOWN_PLAUSIBILITY_FAILURES

        failed = [
            r["check_id"] for r in plaus["results"] if r["outcome"] == "FAIL"
        ]
        known = [c for c in failed if c in KNOWN_PLAUSIBILITY_FAILURES]
        unknown = [c for c in failed if c not in KNOWN_PLAUSIBILITY_FAILURES]
        for cid in known:
            # Loud, every run, with the issue number. A known failure that
            # stops being mentioned is a known failure on its way to being
            # forgotten.
            say(
                f"plausibility: {cid} FAILS, and is a declared known failure "
                f"tracked as {KNOWN_PLAUSIBILITY_FAILURES[cid]}. The package "
                f"carries the failure in evidence/plausibility.json."
            )
        if unknown:
            raise PlausibilityFailure(
                f"the written package fails {len(unknown)} plausibility "
                f"check(s) that are NOT declared known failures: {unknown}. "
                f"U27 makes these a standing requirement, so a package that "
                f"contradicts a published Irish reference is not delivered "
                f"quietly. The package and its report are on disk at "
                f"{out_root} for inspection; see evidence/plausibility.json."
                + (
                    f" (Also failing, and declared: {known}.)" if known else ""
                )
            )
    return diagnostics


def _peak_rss_mb() -> float:
    """Peak resident set size, in MB.

    ``ru_maxrss`` is bytes on macOS and kilobytes on Linux, which is a classic
    way to report a 1,000x wrong memory figure.  Decided by platform rather
    than by magnitude, because a magnitude test would be a guess.
    """
    import platform
    import resource

    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return raw / (1024.0 * 1024.0) if platform.system() == "Darwin" else raw / 1024.0


def _machine() -> dict[str, Any]:
    import platform
    import subprocess

    out: dict[str, Any] = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
    }
    try:
        out["cpu_brand"] = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        out["memory_gb"] = round(
            int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True,
                               text=True, timeout=10).stdout.strip()) / 1024**3, 1
        )
    except Exception as exc:                        # pragma: no cover
        out["sysctl_error"] = str(exc)
    out.update(free_space())
    return out


def free_space(path: str = "/") -> dict[str, Any]:
    """Free and total disk, measured. U21 / I-005 depend on the real number.

    Quoting a figure recorded earlier in the week would be a statistic from
    memory in all but name: disk fills as the run writes, and the number that
    matters is the one at the time of the claim.
    """
    import shutil as _shutil

    usage = _shutil.disk_usage(path)
    return {
        "disk_path": path,
        "disk_total_gb": round(usage.total / 1024**3, 1),
        "disk_free_gb": round(usage.free / 1024**3, 1),
        "disk_used_gb": round(usage.used / 1024**3, 1),
    }


def _project_full_town(bench: dict[str, Any], *, n_town_homes: int) -> dict[str, Any]:
    """Project the full town from the measured estate, with U21's x1.5 margin.

    Scaling is linear in homes and that is stated rather than assumed: phase A
    is serial and town-wide, so it does NOT scale linearly, and the projection
    is therefore a lower bound on time. The x1.5 margin the brief asks for is
    what covers that, and the phase-A share is reported so the reader can see
    how much of the margin it needs.
    """
    factor = n_town_homes / max(bench["n_homes"], 1)
    run_s = bench["timings"]["run_s"] * factor
    sim_s = bench["timings"]["simulate_s"] * factor
    write_s = bench["timings"]["write_s"] * factor
    # None, not zero, when nothing was written. A storage projection of 0 GB
    # from an ablation arm would be read as a measurement, and the whole
    # purpose of the U21 margin is that these figures get planned against.
    measured_bytes = bench["storage"].get("total_bytes")
    storage_gb = (
        measured_bytes * factor / 1024**3 if measured_bytes is not None
        else None
    )
    mem_gb = bench["peak_rss_mb"] * factor / 1024.0
    machine_gb = bench["machine"].get("memory_gb")
    return {
        "n_town_homes": n_town_homes,
        "scale_factor": round(factor, 2),
        "projected_run_hours": round(run_s / 3600.0, 2),
        "projected_run_hours_with_margin": round(1.5 * run_s / 3600.0, 2),
        "projected_simulate_hours": round(sim_s / 3600.0, 2),
        "projected_write_hours": round(write_s / 3600.0, 2),
        "runtime_note": (
            "Simulation and writing are reported separately because they "
            "scale the same way but are nothing like the same size: writing "
            "D18 observations at 1-minute resolution costs several times what "
            "simulating them does. Anyone planning E2 needs the split, not "
            "the total."
        ),
        "projected_storage_gb_ten_years": (
            round(storage_gb * 10.0, 1) if storage_gb is not None else None
        ),
        "projected_storage_gb_ten_years_with_margin": (
            round(1.5 * storage_gb * 10.0, 1) if storage_gb is not None else None
        ),
        "projected_storage_gb": (
            round(storage_gb, 2) if storage_gb is not None else None
        ),
        "projected_storage_gb_with_margin": (
            round(1.5 * storage_gb, 2) if storage_gb is not None else None
        ),
        "storage_measured": storage_gb is not None,
        "projected_peak_rss_gb_if_naive": round(mem_gb, 2),
        "machine_memory_gb": machine_gb,
        "memory_note": (
            "The naive projection scales peak RSS by the number of homes, which "
            "is the wrong model for this run and is reported only to show why: "
            "the writer streams and flushes monthly, so resident memory is "
            "bounded by one month of one estate's rows plus the town at t0, not "
            "by the year. Storage is what scales."
        ),
        "margin": 1.5,
        "margin_basis": (
            "U21. Covers the serial phase-A share, which does not scale "
            "linearly in homes, and the town-wide t0 synthesis, which is "
            "already full-town in this measurement."
        ),
    }


def _meter_gas_kwh(
    building: Any, acc: dict[str, float], *, n_days: int,
    master_seed: int = 20261008,
) -> dict[str, Any] | None:
    """Everything the gas meter sees for one dwelling (U25).

    Returns ``None`` for a dwelling that burns no gas, rather than a zero that
    would then be averaged in with the gas homes.

    The three terms E1 was missing are all here, and the itemisation is the
    point: a single total that happened to match DBERNG01 would say nothing
    about whether it matched for the right reasons.
    """
    from baile_nua.physics.boiler import annual_fuel_terms
    from baile_nua.physics.dhw import dhw_system_for, primary_circuit_loss_kwh_yr

    fuel = str(getattr(building, "heating_fuel", "") or "").lower()
    cooks_with_gas = bool(acc.get("cooking_hob_useful_wh", 0.0)
                          or acc.get("cooking_oven_useful_wh", 0.0))
    if "natural gas" not in fuel and "lpg" not in fuel:
        return None

    # I-047: the BOILER's vintage, not the dwelling's. DEAP Table 4b is
    # indexed by the appliance's age, and a house built in 1975 is on its
    # second or third boiler. Reading the dwelling's year into those rows gave
    # the whole old stock 55%-efficient floor-mounted boilers and inflated its
    # gas by up to 1.51x.
    from baile_nua.physics.boiler import boiler_spec_for
    from baile_nua.rng import SeedTree, Stream

    gen = SeedTree(int(master_seed)).generator(
        Stream.BUILDING_SYSTEMS,
        entity=f"{getattr(building, 'building_id', '')}:boiler",
    )
    spec = boiler_spec_for(building, gen=gen)
    system = dhw_system_for(building)
    # An annual figure, prorated: a three-day run must not be charged a year
    # of primary-circuit loss.
    primary = primary_circuit_loss_kwh_yr(system) * (n_days / 365.0) \
        if system else 0.0

    out = annual_fuel_terms(
        spec=spec,
        space_heat_kwh=float(acc["heat_delivered_kwh"]),
        dhw_boiler_heat_kwh=float(acc["dhw_coil_kwh"]),
        primary_circuit_kwh=float(primary),
        hob_useful_kwh=float(acc.get("cooking_hob_useful_wh", 0.0)) / 1000.0,
        oven_useful_kwh=float(acc.get("cooking_oven_useful_wh", 0.0)) / 1000.0,
        gas_cooking=cooks_with_gas,
    )
    # Derived rather than carried: the per-day energy row has the label as a
    # string, and the annual accumulator sums floats, so a string cannot be
    # accumulated through it. Which of the two cooking appliances had its
    # electricity suppressed is the same information and does accumulate.
    hob = float(acc.get("cooking_hob_useful_wh", 0.0))
    oven = float(acc.get("cooking_oven_useful_wh", 0.0))
    if hob > 0.0 and oven > 0.0:
        label = "natural gas"
    elif hob > 0.0:
        label = "gas hob electric oven"
    else:
        label = "electricity"
    out["cooks_with_gas"] = cooks_with_gas
    out["cooking_fuel"] = label
    return out


def _annual_vs_d24(
    annual_wh: dict[str, dict[str, float]], sl: E1Slice, *, n_days: int = 365,
    master_seed: int = 20261008
) -> dict[str, Any]:
    """Compare simulated annual electricity per dwelling against D24.

    The comparison is made WITHIN heating fuel, because DBEREL01's BER axis
    confounds fabric with fuel: an A-rated detached house consumes more
    electricity than an F-rated one, since the better-rated home is the one
    with a heat pump. Scoring a gas-heated simulated home against the A-B cell
    would be comparing a home that does not heat with electricity against homes
    that do.
    """
    from baile_nua.calibration import electricity_per_dwelling_targets
    from baile_nua.calibration.targets import gas_per_dwelling_targets

    targets = {
        (t.conditioned_on["dwelling_type"], t.conditioned_on["source_ber_label"]): t
        for t in electricity_per_dwelling_targets(2022)
    }
    gas_targets = {
        (t.conditioned_on["dwelling_type"], t.conditioned_on["source_ber_label"]): t
        for t in gas_per_dwelling_targets(2022)
    }
    bid_to_hh = {b.building_id: hh for hh, b in sl.buildings.items()}
    rows: list[dict[str, Any]] = []
    for bid, acc in sorted(annual_wh.items()):
        b = sl.buildings[bid_to_hh[bid]]
        # U25: hot water is electricity too, wherever the immersion or the
        # diverter ran. Leaving `dhw_wh` out here would have understated every
        # electrically heated home's annual total.
        total_kwh = (
            acc["appliance_wh"] + acc["hvac_wh"] + acc["ev_wh"] + acc["dhw_wh"]
        ) / 1000.0
        band = _ber_group(b.ber_band)
        t = targets.get((b.dwelling_type, band))
        rows.append(
            {
                "building_id": bid,
                "dwelling_type": b.dwelling_type,
                # U22's held-out axis. The construction period has to be on
                # the row the ablation reads, or the gradient DBERNG02 is the
                # reference for cannot be computed from it.
                "year_built_band": b.year_built_band,
                "build_year": int(b.build_year),
                "ber_band": b.ber_band,
                "ber_group": band,
                "heating_fuel": b.heating_fuel,
                "heats_with_electricity": b.heating_fuel in ("electricity", "heat pump"),
                "simulated_kwh_yr": round(total_kwh, 1),
                "appliance_kwh_yr": round(acc["appliance_wh"] / 1000.0, 1),
                "dhw_elec_kwh_yr": round(acc["dhw_wh"] / 1000.0, 1),
                "dhw_useful_kwh_yr": round(acc["dhw_useful_kwh"], 1),
                "dhw_standby_kwh_yr": round(acc["dhw_standby_kwh"], 1),
                "dhw_coil_kwh_yr": round(acc["dhw_coil_kwh"], 1),
                "dhw_immersion_kwh_yr": round(acc["dhw_immersion_kwh"], 1),
                "dhw_diverted_pv_kwh_yr": round(acc["dhw_diverted_pv_kwh"], 1),
                "dhw_litres_yr": round(acc["dhw_litres"], 0),
                "temp_living_mean_c": round(
                    acc["temp_living_mean_c_days"] / max(n_days, 1), 2
                ),
                "temp_living_daily_min_mean_c": round(
                    acc["temp_living_min_c_days"] / max(n_days, 1), 2
                ),
                "hvac_kwh_yr": round(acc["hvac_wh"] / 1000.0, 1),
                "ev_kwh_yr": round(acc["ev_wh"] / 1000.0, 1),
                "pv_kwh_yr": round(acc["pv_wh"] / 1000.0, 1),
                "import_kwh_yr": round(acc["import_wh"] / 1000.0, 1),
                "d24_target_kwh_yr": (float(t.value) if t else None),
                "d24_target_id": (t.target_id if t else None),
                "space_heat_kwh_yr": round(acc["heat_delivered_kwh"], 1),
                "space_heat_kwh_m2_yr": round(
                    acc["heat_delivered_kwh"] / max(b.floor_area_m2, 1.0), 1
                ),
                "floor_area_m2": round(b.floor_area_m2, 1),
                "ber_kwh_m2_yr": round(b.ber_kwh_m2_yr, 1),
                "d24_gas_target_kwh_yr": (
                    float(gt.value) if (gt := gas_targets.get((b.dwelling_type, band)))
                    else None
                ),
                "d24_gas_target_id": (gt.target_id if gt else None),
            }
        )
        # U25: the three terms the E1 comparison named as missing.
        meter = _meter_gas_kwh(b, acc, n_days=n_days, master_seed=master_seed)
        if meter is not None:
            rows[-1].update({
                "meter_gas_kwh_yr": round(meter["meter_fuel_kwh"], 1),
                "boiler_efficiency": round(meter["efficiency"], 4),
                "boiler_efficiency_row": meter["efficiency_row"],
                "gas_combustion_loss_kwh_yr": round(
                    meter["combustion_loss_kwh"], 1
                ),
                "gas_dhw_boiler_heat_kwh_yr": round(
                    meter["terms"]["dhw_boiler_heat_kwh"], 1
                ),
                "gas_primary_circuit_kwh_yr": round(
                    meter["terms"]["primary_circuit_kwh"], 1
                ),
                "gas_cooking_kwh_yr": round(
                    meter["terms"]["gas_cooking_kwh_at_meter"], 1
                ),
                "cooks_with_gas": meter["cooks_with_gas"],
                "cooking_fuel": meter["cooking_fuel"],
                "cooking_hob_useful_kwh_yr": round(
                    acc.get("cooking_hob_useful_wh", 0.0) / 1000.0, 1
                ),
                "cooking_oven_useful_kwh_yr": round(
                    acc.get("cooking_oven_useful_wh", 0.0) / 1000.0, 1
                ),
            })
    frame = pd.DataFrame(rows)
    elec = frame[frame.heats_with_electricity]
    fossil = frame[~frame.heats_with_electricity]
    gas = frame[frame.heating_fuel == "natural gas"]
    return {
        "per_dwelling": rows,
        "summary": {
            "n_dwellings": len(frame),
            "mean_simulated_kwh_yr": round(float(frame.simulated_kwh_yr.mean()), 1),
            "median_simulated_kwh_yr": round(float(frame.simulated_kwh_yr.median()), 1),
            "fossil_heated": _fuel_block(fossil),
            "electrically_heated": _fuel_block(elec),
            "gas_heated_space_heat": _gas_block(gas),
        },
        "comparison_rule": (
            "Compared within heating fuel. DBEREL01 covers ALL household "
            "electricity, so a gas-heated dwelling can only be expected to "
            "reach the part of its cell that is not space heating, while an "
            "electrically heated one should reach the whole of it."
        ),
    }


def _gas_block(frame: pd.DataFrame) -> dict[str, Any]:
    """Simulated SPACE HEAT against DBERNG01's gas cell, with the gap named.

    The comparison is deliberately one-sided. DBERNG01 measures everything that
    passes the gas meter - space heating, hot water, cooking where the hob is
    gas, and the boiler's own losses - and E1 models only space heating: there
    is no hot water tank (see the stream writer's UNMODELLED_D16_FIELDS) and no
    boiler efficiency. So the simulated figure MUST sit below the cell, and how
    far below is the quantity of interest. A simulated space heat ABOVE the
    cell would be unambiguously wrong; one at 60 to 80% of it is what a model
    with no hot water and no combustion losses should produce.

    **U25 ended that state of affairs**, and this function now reports both
    ratios. The space-heat-only one is kept because it is the E1 measurement
    and the thing the gap was quantified by; the meter one is the comparison
    the model can now actually make. The paragraph above is left as written
    because it is the record of what the number meant when it was 0.308.
    """
    if frame.empty:
        return {"n": 0}
    paired = frame.dropna(subset=["d24_gas_target_kwh_yr"])
    out: dict[str, Any] = {
        "n": int(len(frame)),
        "mean_space_heat_kwh_yr": round(float(frame.space_heat_kwh_yr.mean()), 1),
        "mean_space_heat_kwh_m2_yr": round(
            float(frame.space_heat_kwh_m2_yr.mean()), 1
        ),
        "mean_ber_kwh_m2_yr": round(float(frame.ber_kwh_m2_yr.mean()), 1),
        "mean_floor_area_m2": round(float(frame.floor_area_m2.mean()), 1),
        "n_paired_with_a_gas_target": int(len(paired)),
    }
    if len(paired):
        ratio = paired.space_heat_kwh_yr / paired.d24_gas_target_kwh_yr
        out.update({
            "mean_d24_gas_target_kwh_yr": round(
                float(paired.d24_gas_target_kwh_yr.mean()), 1
            ),
            "mean_ratio_space_heat_over_gas_target": round(float(ratio.mean()), 3),
            "share_between_0p5_and_1p0_of_target": round(
                float(((ratio >= 0.5) & (ratio <= 1.0)).mean()), 3
            ),
            "share_above_target": round(float((ratio > 1.0).mean()), 3),
        })
        # U25. The comparison the gap was named for: everything the meter
        # sees, against what the meter published. Reported ALONGSIDE the
        # space-heat-only ratio rather than replacing it, because the pair is
        # the measurement - the distance between them is what hot water,
        # cooking and combustion losses are worth.
        if "meter_gas_kwh_yr" in paired.columns:
            meter = paired.dropna(subset=["meter_gas_kwh_yr"])
            if len(meter):
                mratio = meter.meter_gas_kwh_yr / meter.d24_gas_target_kwh_yr
                out.update({
                    "n_with_a_meter_figure": int(len(meter)),
                    "mean_meter_gas_kwh_yr": round(
                        float(meter.meter_gas_kwh_yr.mean()), 1
                    ),
                    "mean_ratio_meter_over_gas_target": round(
                        float(mratio.mean()), 3
                    ),
                    "meter_share_within_plus_minus_30pct": round(
                        float(((mratio >= 0.7) & (mratio <= 1.3)).mean()), 3
                    ),
                    "meter_share_above_target": round(
                        float((mratio > 1.0).mean()), 3
                    ),
                    "mean_boiler_efficiency": round(
                        float(meter.boiler_efficiency.mean()), 4
                    ),
                    "mean_combustion_loss_kwh_yr": round(
                        float(meter.gas_combustion_loss_kwh_yr.mean()), 1
                    ),
                    "mean_dhw_boiler_heat_kwh_yr": round(
                        float(meter.gas_dhw_boiler_heat_kwh_yr.mean()), 1
                    ),
                    "mean_primary_circuit_kwh_yr": round(
                        float(meter.gas_primary_circuit_kwh_yr.mean()), 1
                    ),
                    "mean_gas_cooking_kwh_yr": round(
                        float(meter.gas_cooking_kwh_yr.mean()), 1
                    ),
                    "n_cooking_with_gas": int(meter.cooks_with_gas.sum()),
                    "cooking_fuel_mix": {
                        str(k): int(v) for k, v in
                        meter.cooking_fuel.value_counts().items()
                    },
                    "uplift_meter_over_space_heat": round(
                        float(
                            meter.meter_gas_kwh_yr.mean()
                            / max(meter.space_heat_kwh_yr.mean(), 1e-9)
                        ), 3
                    ),
                })
    out["interpretation"] = (
        "Two ratios, and the pair is the point. Simulated SPACE HEAT must sit "
        "below the gas cell, because the cell also contains hot water, gas "
        "cooking and the boiler's own losses - that is what the E1 figure of "
        "0.308 measured. The METER figure includes all three (U25), so it is "
        "the one that should approach 1.0, and a meter figure far ABOVE the "
        "cell would mean a term has been double-counted or an efficiency is "
        "too low."
    )
    return out


def _fuel_block(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {"n": 0}
    sim = frame.simulated_kwh_yr
    tgt = frame.d24_target_kwh_yr.dropna()
    out = {
        "n": int(len(frame)),
        "mean_simulated_kwh_yr": round(float(sim.mean()), 1),
        "p10_simulated_kwh_yr": round(float(sim.quantile(0.10)), 1),
        "p90_simulated_kwh_yr": round(float(sim.quantile(0.90)), 1),
        "mean_d24_target_kwh_yr": (round(float(tgt.mean()), 1) if len(tgt) else None),
    }
    if len(tgt):
        paired = frame.dropna(subset=["d24_target_kwh_yr"])
        ratio = paired.simulated_kwh_yr / paired.d24_target_kwh_yr
        out["mean_ratio_simulated_over_target"] = round(float(ratio.mean()), 3)
        out["share_within_plus_minus_30pct"] = round(
            float(((ratio >= 0.7) & (ratio <= 1.3)).mean()), 3
        )
    return out


def _ber_group(band: str) -> str:
    """Map a schema BER band to DBEREL01's coarser axis."""
    b = str(band).upper()
    if b.startswith("A") or b.startswith("B"):
        return "A - B"
    if b.startswith("C"):
        return "C"
    if b.startswith("D"):
        return "D"
    if b.startswith("E"):
        return "E"
    return "F- G"
