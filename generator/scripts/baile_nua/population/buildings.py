"""HRSD_Buildings at t0 (design 5.2, 5.7, S03; datasets D02, D04).

    Buildings (HRSD_Buildings): fabric, archetype, BER, age, systems, appliance
    stock, DER, Building Energy Passport.  (design 3.1 S03)

R11 keeps this layer separate from the people layer: no person attribute is
stored on a building table, and the schema test
``test_no_person_attribute_sits_on_a_building_table`` enforces it.

**What each attribute is conditioned on, and where it comes from:**

=====================  =========================================================
Attribute              Source
=====================  =========================================================
house vs apartment     SAPS Table 6.1 marginal, per small area (real Census)
detached/semi/terraced CSO EBA02 conditional split for Co. Cork (real BER data)
year built             SAPS Table 6.2 marginal, per small area (real Census)
rooms, bedrooms        SAPS Tables 6.4 and 6.9 marginals (real Census)
floor area             conditioned on rooms and dwelling type; the area-per-room
                       relationship is an assumption, flagged [A] (I-019)
BER band               CSO EBA02, conditional on dwelling type AND year built -
                       a genuine joint distribution, not independent marginals
heating fuel           SAPS Table 6.5 marginal (real Census)
heating system         fuel plus the CSO EBQ02 heat-pump share for the
                       South-West region, which is how "Electricity" is split
                       into heat pump and direct electric
RC parameters          forward from Part L U-values and envelope areas
                       (physics.archetype), asserted plausible
sensor tier            drawn against the household's privacy trait (design 5.13:
                       "tier uptake correlates with traits as it would in
                       reality"), with realistic uptake per U06 option (a)
=====================  =========================================================

Marginals are consumed **in sorted small-area order and apportioned by largest
remainder**, so each area's Census distribution is reproduced exactly rather
than sampled, and the result does not depend on iteration order.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import numpy as np
import pandas as pd

from baile_nua.ids import IdMinter, gt_id
from baile_nua.physics.archetype import (
    ImplausibleFabricError,
    RCParameters,
    derive_rc,
)
from baile_nua.population import ber as ber_mod
from baile_nua.rng import SeedTree, Stream

__all__ = [
    "SynthBuilding",
    "generate_buildings",
    "AREA_PER_ROOM_M2",
    "MIN_ROOMS_OVER_BEDROOMS",
    "ROOM_ALLOCATION_STRENGTH",
    "DWELLING_SIZE_RANK",
    "allocate_rooms",
    "STOREYS_BY_TYPE",
    "SENSOR_TIER_UPTAKE",
]

#: Floor area per habitable room, m2, by dwelling type. [A] (I-019, I-031)
#:
#: SAPS publishes room counts but no floor areas, and neither EBA02 nor EBQ02
#: carries floor area, so the relationship has to be assumed. The level is
#: anchored to TRS05: Co. Cork rental properties had a median total floor area
#: of 89.4 m2 in 2021, which bounds the stock median from BELOW because rentals
#: skew smaller and apartment-heavier than owner-occupied housing.
#:
#: **The apartment figure was wrong and it mattered (I-031.)** It was 26.0 -
#: MORE area per room than a detached house at 24.0 - which is backwards: an
#: apartment's rooms are smaller than a detached house's, not larger. Combined
#: with room counts drawn independently of dwelling type, it put the town's
#: apartment median at 120.8 m2 against a detached median of 129.5, produced a
#: 285.7 m2 three-bedroom apartment, and through it 13.6 MWh a year of space
#: heat in a C3-rated flat - 3.7 times the CSO's measured figure for its cell.
AREA_PER_ROOM_M2: dict[str, float] = {
    "detached": 24.0, "semi-detached": 21.0, "terraced": 19.5,
    "apartment": 18.0, "bedsit": 16.0,
}

#: How many rooms a dwelling must have beyond its bedrooms.
#:
#: **Derived from the published marginals, not assumed.** The first value here
#: was 2 - bedrooms plus a kitchen and a living room - on the reasoning that
#: SAPS counts habitable rooms and excludes bathrooms and hallways. A
#: feasibility test on Cobh's own SAPS room and bedroom marginals refuted it:
#: with the OPTIMAL rank pairing of the two published distributions,
#:
#:     margin 0 (rooms >= bedrooms)        2 of 5,167 dwellings infeasible (0.04%)
#:     margin 1 (rooms >= bedrooms + 1)  272 of 5,167 infeasible (5.3%)
#:     margin 2 (rooms >= bedrooms + 2)  764 of 5,167 infeasible (14.8%)
#:
#: So the Census's two questions do not have the base I assumed: its rooms
#: question excludes kitchenettes and counts only a kitchen large enough to
#: use as a room, which many dwellings do not have. A margin of 2 would force
#: the synthesis to break one published marginal to satisfy a constraint the
#: data denies - and the constraint, not the data, is what was wrong.
#:
#: The constraint is still worth having at margin 0: the independent draw
#: produced five-bedroom dwellings with three rooms, which no definition of
#: "room" permits. Independence is the right default between attributes that
#: COULD vary freely; it is not a licence to emit a dwelling that cannot exist.
#: ``test_room_and_bedroom_marginals_support_the_declared_margin`` pins this
#: number to the feasibility test, so it cannot drift back to a guess.
MIN_ROOMS_OVER_BEDROOMS: int = 0

#: How strongly room count is allocated by dwelling size rank.
#:
#: 0.0 would restore full independence and its impossible dwellings; 1.0 would
#: make rooms a deterministic function of type and bedrooms, which real stock is
#: not. The allocation is monotone in expectation and preserves the SAPS room
#: marginal exactly, because it only ever permutes the apportioned labels.
ROOM_ALLOCATION_STRENGTH: float = 0.75

#: Dwelling types in ascending typical size, for that allocation.
DWELLING_SIZE_RANK: dict[str, int] = {
    "bedsit": 0, "apartment": 1, "terraced": 2, "semi-detached": 3, "detached": 4,
}

#: Minimum and typical storey counts. Apartments are single-storey units; R01
#: forbids high-rise, so an apartment is in a low block rather than a tower.
STOREYS_BY_TYPE: dict[str, int] = {
    "detached": 2, "semi-detached": 2, "terraced": 2, "apartment": 1, "bedsit": 1,
}

#: Sensor tier uptake (U06 option (a): "realistic uptake, most homes meter
#: only"). The base rates are the study's consent outcome, and design 5.13 adds
#: that privacy strictness "drives each home's sensor tier and Jetson consent,
#: so tier uptake correlates with traits as it would in reality". [A]
SENSOR_TIER_UPTAKE: dict[str, float] = {"T1": 0.72, "T2": 0.18, "T3": 0.07, "T4": 0.03}


@dataclasses.dataclass
class SynthBuilding:
    building_id: str
    premises_id: str          # opaque, observable; keyed to the property
    gt_premises_key: str
    small_area: str
    estate_id: str
    household_id: str | None
    dwelling_type: str
    build_year: int
    year_built_band: str
    floor_area_m2: float
    storeys: int
    rooms: int
    bedrooms: int
    archetype_id: str
    ber_band: str
    ber_kwh_m2_yr: float
    heating_fuel: str
    heating_system: str
    heating_control: str
    tenure: str
    sensor_tier: str
    rc: RCParameters
    seed: int
    notes: dict[str, Any] = dataclasses.field(default_factory=dict)

    def d02_row(self) -> dict[str, Any]:
        """The D02 row.  Deliberately contains no person attribute (R11)."""
        return {
            "building_id": self.building_id,
            "version": 1,
            "valid_from": "2022-01-01T00:00:00Z",
            "valid_to": None,
            "premises_id": self.premises_id,
            "estate_id": self.estate_id,
            "dwelling_type": self.dwelling_type,
            "build_year": self.build_year,
            "floor_area_m2": round(self.floor_area_m2, 2),
            "storeys": self.storeys,
            "archetype_id": self.archetype_id,
            "ber_band": self.ber_band,
            "ber_kwh_m2_yr": round(self.ber_kwh_m2_yr, 2),
            "heating_fuel": self.heating_fuel,
            "heating_system": self.heating_system,
            "heating_control": self.heating_control,
            "tenure": self.tenure,
            "sri_class": None,
            "sri_score": None,
            "rc_r_ie": self.rc.r_ie,
            "rc_r_ea": self.rc.r_ea,
            "rc_r_zz": self.rc.r_zz,
            "rc_r_inf": self.rc.r_inf,
            "rc_c_living": self.rc.c_living,
            "rc_c_sleep": self.rc.c_sleep,
            "rc_c_env": self.rc.c_env,
            "rc_solar_aperture_m2": round(self.rc.solar_aperture_m2, 3),
            "rc_vol_living_m3": round(self.rc.vol_living_m3, 2),
            "rc_vol_sleep_m3": round(self.rc.vol_sleep_m3, 2),
            "ach_base": round(self.rc.ach_base, 4),
            "heat_emitter_w": round(self.rc.heat_emitter_w, 1),
            "dhw_tank_litres": self.notes.get("dhw_tank_litres"),
            "fidelity_tier": "F2" if self.sensor_tier in ("T3", "T4") else "F1",
            "seed": self.seed,
        }


def _apportion(counts: pd.Series, total: int) -> list[str]:
    """Expand a category->count marginal into a list of ``total`` labels.

    Largest remainder, in sorted label order, so the realised distribution
    matches the Census marginal as closely as integers allow and the sequence is
    deterministic.
    """
    labels = sorted(counts.index)
    w = np.array([float(counts[l]) for l in labels], dtype=np.float64)
    if w.sum() <= 0 or total <= 0:
        return []
    exact = w / w.sum() * total
    n = np.floor(exact).astype(np.int64)
    short = int(total - n.sum())
    if short > 0:
        order = np.argsort(-(exact - n), kind="stable")
        n[order[:short]] += 1
    elif short < 0:
        order = np.argsort(exact - n, kind="stable")
        n[order[: -short]] -= 1
    out: list[str] = []
    for lab, k in zip(labels, n):
        out.extend([lab] * int(k))
    return out


#: SAPS year-built band -> representative construction year range.
_BAND_YEARS: dict[str, tuple[int, int]] = {
    "pre 1919": (1860, 1918), "1919-1945": (1919, 1945),
    "1946-1960": (1946, 1960), "1961-1970": (1961, 1970),
    "1971-1980": (1971, 1980), "1981-1990": (1981, 1990),
    "1991-2000": (1991, 2000), "2001-2010": (2001, 2010),
    "2011-2015": (2011, 2015), "2016 or later": (2016, 2021),
    "not stated": (1960, 2000),
}

#: SAPS central-heating fuel -> (schema heating_fuel, candidate systems).
_FUEL_SYSTEMS: dict[str, tuple[str, tuple[str, ...]]] = {
    "oil": ("oil", ("oil boiler",)),
    "natural gas": ("natural gas", ("gas boiler",)),
    "electricity": ("electricity", ("heat pump", "direct electric", "storage heaters")),
    "coal": ("solid fuel", ("solid fuel stove",)),
    "peat": ("solid fuel", ("solid fuel stove",)),
    "wood": ("solid fuel", ("wood stove",)),
    "LPG": ("LPG", ("LPG boiler",)),
    "other": ("district", ("district heating",)),
    "none": ("electricity", ("direct electric",)),
    "not stated": ("oil", ("oil boiler",)),
}


def _median_band_by_era(cond: pd.DataFrame) -> dict[tuple[str, str], str]:
    """Median BER band per (dwelling type, era), measured from the BER data.

    Used by ``physics.archetype.fabric_multiplier`` to decide whether a given
    building's band is better or worse than its era implies.  Measured rather
    than assumed, so the fabric multiplier is anchored to Co. Cork's actual
    stock.
    """
    from baile_nua.physics.archetype import BAND_ORDER, AGGREGATE_TO_MID

    order = {b: i for i, b in enumerate(BAND_ORDER)}
    out: dict[tuple[str, str], str] = {}
    for (dt, era), grp in cond.groupby(["dwelling_type", "year_built_band"]):
        g = grp[grp["share"] > 0].copy()
        if g.empty:
            continue
        g["ix"] = g["ber_band"].map(lambda b: order.get(AGGREGATE_TO_MID.get(b, b), 99))
        g = g.sort_values("ix")
        cum = g["share"].cumsum()
        med = g.loc[cum >= 0.5].iloc[0]["ber_band"]
        out[(dt, era)] = AGGREGATE_TO_MID.get(med, med)
    return out


def allocate_rooms(
    room_labels: list[str],
    *,
    dwelling_types: list[str],
    bedrooms: list[int],
    gen: Any,
) -> list[str]:
    """Allocate the area's apportioned room labels to its dwellings.

    **Preserves the SAPS room marginal exactly.** The returned list is a
    permutation of ``room_labels``, so every published count is used once and
    the marginal is untouched. What changes is *which dwelling gets which*.

    Two things are enforced that independence could not:

    *Logical consistency.* A dwelling with ``b`` bedrooms needs at least
    ``b + MIN_ROOMS_OVER_BEDROOMS`` habitable rooms, because SAPS counts
    bedrooms, kitchen and living room and excludes bathrooms and hallways. The
    independent draw produced five-bedroom dwellings with three rooms.

    *Size ordering.* Apartments do not have more rooms than detached houses.
    The independent draw gave them the same distribution, and with the
    then-wrong apartment area per room that produced a 285.7 m2 flat and,
    through it, 13.6 MWh a year of space heat in a C3-rated apartment.

    The ordering is monotone in expectation rather than deterministic:
    dwellings are ranked by (type size, bedrooms) with jitter whose width is
    set by ``ROOM_ALLOCATION_STRENGTH``, so the association is strong without
    making room count a function of type. Real stock has spread.
    """
    n = len(dwelling_types)
    if not room_labels or n == 0:
        return list(room_labels)

    def numeric(label: str) -> int:
        return 8 if str(label).endswith("+") else int(label)

    labels = sorted(room_labels, key=numeric)

    strength = float(ROOM_ALLOCATION_STRENGTH)
    span = max(len(DWELLING_SIZE_RANK), 1) + (max(bedrooms) if bedrooms else 0) + 1
    keys = []
    for i in range(n):
        base = (
            DWELLING_SIZE_RANK.get(dwelling_types[i], 2) * 1.0
            + 0.6 * float(bedrooms[i])
        )
        jitter = (1.0 - strength) * span * float(gen.random())
        keys.append((base + jitter, i))
    order = [i for _k, i in sorted(keys)]

    out: list[str] = [""] * n
    for slot, i in enumerate(order):
        out[i] = labels[slot] if slot < len(labels) else labels[-1]

    # Repair the logical constraint by SWAPPING, which keeps the multiset of
    # labels intact. A swap is chosen over a redraw precisely so the marginal
    # cannot drift.
    def shortfall(i: int) -> int:
        return (bedrooms[i] + MIN_ROOMS_OVER_BEDROOMS) - numeric(out[i])

    for _sweep in range(3):
        bad = [i for i in range(n) if shortfall(i) > 0]
        if not bad:
            break
        spare = sorted(
            (i for i in range(n) if shortfall(i) < 0),
            key=lambda i: numeric(out[i]), reverse=True,
        )
        for i in sorted(bad, key=shortfall, reverse=True):
            for j in list(spare):
                if j == i:
                    continue
                a, b = out[i], out[j]
                if numeric(b) >= bedrooms[i] + MIN_ROOMS_OVER_BEDROOMS and (
                    numeric(a) >= bedrooms[j] + MIN_ROOMS_OVER_BEDROOMS
                ):
                    out[i], out[j] = b, a
                    spare.remove(j)
                    break
    return out


def generate_buildings(
    scaled_marginals: dict[str, pd.DataFrame],
    households: list[Any],
    *,
    master_seed: int,
    privacy_by_household: dict[str, float] | None = None,
) -> tuple[list[SynthBuilding], dict[str, Any]]:
    """One building per household, matching each small area's Census marginals.

    ``privacy_by_household`` maps household id to the decision-maker's privacy
    trait, so sensor tier correlates with it as design 5.13 requires. Passing it
    in rather than reaching into the person layer keeps R11's separation intact:
    this function never sees a person record.
    """
    tree = SeedTree(master_seed)
    minter = IdMinter(master_seed)

    acc = scaled_marginals["accommodation_type"]
    yrs = scaled_marginals["year_built"]
    rooms_m = scaled_marginals["rooms"]
    beds_m = scaled_marginals["bedrooms"]
    heat_m = scaled_marginals["central_heating"]
    ten_m = scaled_marginals["tenure"]

    house_split = ber_mod.conditional_dwelling_split()
    cond = ber_mod.ber_given_type_and_age()
    medians = _median_band_by_era(cond)
    hp_share = ber_mod.heating_system_split()["heat_pump_share_of_assessed"]

    by_area: dict[str, list[Any]] = {}
    for hh in households:
        by_area.setdefault(hh.small_area, []).append(hh)

    buildings: list[SynthBuilding] = []
    diag: dict[str, Any] = {
        "band_redraws": 0, "band_fallbacks": 0, "implausible_rejections": 0,
        "per_small_area": {}, "heat_pump_share_used": hp_share,
    }
    counter = 0

    for sa in sorted(by_area):
        hhs = sorted(by_area[sa], key=lambda h: h.household_id)
        n = len(hhs)
        gen = tree.generator(Stream.BUILDING_FABRIC, entity=sa, sim_day=0)
        sysgen = tree.generator(Stream.BUILDING_SYSTEMS, entity=sa, sim_day=0)
        tiergen = tree.generator(Stream.SENSOR_TIER, entity=sa, sim_day=0)

        # Census marginals, apportioned to this area's household count.
        acc_list = _apportion(acc.loc[sa], n)
        yr_list = _apportion(yrs.loc[sa].drop(labels=["not stated"], errors="ignore"), n)
        rm_list = _apportion(rooms_m.loc[sa].drop(labels=["not stated"], errors="ignore"), n)
        bd_list = _apportion(beds_m.loc[sa].drop(labels=["not stated"], errors="ignore"), n)
        ht_list = _apportion(heat_m.loc[sa].drop(labels=["not stated"], errors="ignore"), n)
        tn_list = _apportion(ten_m.loc[sa].drop(labels=["not stated"], errors="ignore"), n)

        # Shuffle each independently so the marginals are not spuriously
        # correlated by construction; real dependence is introduced only where
        # there is evidence for it (BER on type and age), or where independence
        # would emit a dwelling that cannot exist - rooms against bedrooms and
        # dwelling type (see allocate_rooms and I-031).
        for lst in (acc_list, yr_list, rm_list, bd_list, ht_list, tn_list):
            if lst:
                perm = gen.permutation(len(lst))
                lst[:] = [lst[i] for i in perm]

        def pick(lst, i, default):
            return lst[i] if i < len(lst) else default

        # ---- dwelling type and bedrooms first, then rooms conditioned on them
        #
        # Two passes rather than one, because the room allocation has to see
        # every dwelling's type and bedroom count before it can decide which
        # dwelling gets which published room count.
        dtypes: list[str] = []
        beds: list[int] = []
        for i in range(n):
            acc_label = pick(acc_list, i, "house or bungalow")
            if acc_label == "house or bungalow":
                split = house_split["house"]
                labs = sorted(split)
                dtypes.append(str(gen.choice(labs, p=[split[k] for k in labs])))
            elif acc_label == "flat or apartment":
                dtypes.append("apartment")
            elif acc_label == "bed-sit":
                dtypes.append("bedsit")
            else:
                dtypes.append("detached")   # caravan/mobile: nearest schema type
            beds_lab = pick(bd_list, i, "3")
            beds.append(
                5 + int(gen.integers(0, 2)) if beds_lab == "5+" else int(beds_lab)
            )
        rm_list = allocate_rooms(
            rm_list, dwelling_types=dtypes, bedrooms=beds, gen=gen
        )

        for i, hh in enumerate(hhs):
            counter += 1
            bid = gt_id("building", counter)
            gt_key = f"{bid}#premises"
            acc_label = pick(acc_list, i, "house or bungalow")
            # Drawn in the first pass above: the Census gives house against
            # apartment, and the split WITHIN houses comes from CSO BER.
            dtype = dtypes[i]

            era = pick(yr_list, i, "1971-1980")
            lo_y, hi_y = _BAND_YEARS.get(era, (1960, 2000))
            build_year = int(gen.integers(lo_y, hi_y + 1))

            rooms_lab = pick(rm_list, i, "5")
            rooms = 8 + int(gen.integers(0, 3)) if rooms_lab == "8+" else int(rooms_lab)
            bedrooms = beds[i]
            storeys = STOREYS_BY_TYPE.get(dtype, 2)
            if dtype in ("detached", "semi-detached", "terraced") and rooms <= 3:
                storeys = 1

            area_per_room = AREA_PER_ROOM_M2.get(dtype, 21.0)
            floor_area = float(
                max(28.0, rooms * area_per_room * (0.88 + 0.24 * gen.random()))
            )

            # BER conditional on dwelling type AND year built (real joint data).
            sub = cond[(cond["dwelling_type"] == dtype) & (cond["year_built_band"] == _ber_era(era))]
            if sub.empty or sub["share"].sum() <= 0:
                sub = cond[cond["dwelling_type"] == dtype]
            bands = sub["ber_band"].tolist()
            probs = np.array(sub["share"].tolist(), dtype=np.float64)
            probs = probs / probs.sum() if probs.sum() > 0 else None

            median_band = medians.get((dtype, _ber_era(era)), "C2")
            rc = None
            band = "C2"
            band_primary = 0.0
            rejections: list[str] = []
            for attempt in range(8):
                band = str(gen.choice(bands, p=probs)) if bands else "C2"
                pos = float(gen.random())
                try:
                    rc = derive_rc(
                        ber_band=band, era_median_band=median_band,
                        floor_area_m2=floor_area, dwelling_type=dtype,
                        year_built_band=era, storeys=storeys, n_bedrooms=bedrooms,
                        band_position=pos,
                    )
                    band_primary = pos
                    if attempt:
                        diag["band_redraws"] += attempt
                    break
                except ImplausibleFabricError as exc:
                    diag["implausible_rejections"] += 1
                    rejections.append(f"{band}: {exc}")
                    continue
            if rc is None:
                # Every drawn band gave implausible fabric for this geometry.
                # Walk the band scale from best to worst and take the first that
                # is plausible: an unusually small or exposed dwelling is better
                # represented by a better-than-typical fabric than by being
                # dropped from the town. Recorded, with the rejected attempts.
                from baile_nua.physics.archetype import BAND_ORDER

                diag["band_fallbacks"] += 1
                for cand in BAND_ORDER:
                    try:
                        rc = derive_rc(
                            ber_band=cand, era_median_band=median_band,
                            floor_area_m2=floor_area, dwelling_type=dtype,
                            year_built_band=era, storeys=storeys,
                            n_bedrooms=bedrooms, band_position=0.5,
                        )
                        band, band_primary = cand, 0.5
                        break
                    except ImplausibleFabricError:
                        continue
                if rc is None:
                    raise ImplausibleFabricError(
                        f"no BER band gives plausible fabric for a {dtype} of "
                        f"{floor_area:.0f} m2 built {era} over {storeys} storey(s). "
                        f"Attempts: {rejections[:3]}"
                    )
                diag.setdefault("fallback_examples", []).append(
                    {
                        "building": bid, "dwelling_type": dtype, "era": era,
                        "floor_area_m2": round(floor_area, 1), "storeys": storeys,
                        "band_used": band, "n_rejected": len(rejections),
                    }
                )

            from baile_nua.physics.archetype import (
                band_energy_kwh_m2_yr,
                resolve_aggregate_band,
            )

            # EBA02 aggregates C, D, E and F-G; the schema needs a definite
            # band, so the aggregate is resolved using the position already
            # drawn. The fabric was derived from the aggregate's span, which is
            # the wider (more conservative) range, and the fine band is what the
            # building is recorded as.
            fine_band = resolve_aggregate_band(band, band_primary)
            primary, _frac = band_energy_kwh_m2_yr(fine_band, band_primary)
            band = fine_band

            fuel_label = pick(ht_list, i, "oil")
            fuel, systems = _FUEL_SYSTEMS.get(fuel_label, _FUEL_SYSTEMS["not stated"])
            if fuel == "electricity" and len(systems) > 1:
                # Split electricity into heat pump vs resistance using the real
                # regional heat-pump share, weighted up for newer dwellings
                # because that is where heat pumps actually are.
                p_hp = hp_share * (2.2 if era in ("2011-2015", "2016 or later") else 0.5)
                r = float(sysgen.random())
                system = (
                    "heat pump" if r < min(p_hp, 0.9)
                    else ("storage heaters" if r < min(p_hp, 0.9) + 0.35 else "direct electric")
                )
                if system == "heat pump":
                    fuel = "heat pump"
            else:
                system = systems[0]

            control = str(
                sysgen.choice(
                    ["timer", "thermostat", "timer + thermostat", "TRV + thermostat", "manual"],
                    p=[0.18, 0.22, 0.30, 0.22, 0.08],
                )
            )

            # Sensor tier, correlated with the household's privacy trait.
            priv = (privacy_by_household or {}).get(hh.household_id, 0.0)
            tier = _draw_tier(tiergen, priv)

            buildings.append(
                SynthBuilding(
                    building_id=bid,
                    premises_id=minter.observable_premises_id(gt_key),
                    gt_premises_key=gt_key,
                    small_area=sa,
                    estate_id=f"EST-{sa}",
                    household_id=hh.household_id,
                    dwelling_type=dtype,
                    build_year=build_year,
                    year_built_band=era,
                    floor_area_m2=floor_area,
                    storeys=storeys,
                    rooms=rooms,
                    bedrooms=bedrooms,
                    archetype_id=f"{dtype}|{era}|{band}",
                    ber_band=band,
                    ber_kwh_m2_yr=primary,
                    heating_fuel=fuel,
                    heating_system=system,
                    heating_control=control,
                    tenure=pick(tn_list, i, "owner-occupied with mortgage"),
                    sensor_tier=tier,
                    rc=rc,
                    seed=int(tree.generator(Stream.BUILDING_FABRIC, bid).integers(0, 2**62)),
                    notes={
                        "dhw_tank_litres": (
                            None if system in ("direct electric",)
                            else float(120 + 30 * max(bedrooms - 2, 0))
                        ),
                        "accommodation_label_census": acc_label,
                    },
                )
            )
        diag["per_small_area"][sa] = {"n_buildings": n}

    diag["n_buildings"] = len(buildings)
    diag["crosswalk_rows"] = len(minter)
    return buildings, diag


def _ber_era(saps_band: str) -> str:
    """Map a SAPS year-built band onto EBA02's construction periods.

    The two classifications differ: SAPS has eleven bands from "pre 1919",
    EBA02 has "1700-1977", "1978-1999", then five-year periods. Mapping is
    explicit rather than fuzzy-matched so a mismatch is visible.
    """
    mapping = {
        "pre 1919": "1700-1977", "1919-1945": "1700-1977",
        "1946-1960": "1700-1977", "1961-1970": "1700-1977",
        "1971-1980": "1700-1977", "1981-1990": "1978-1999",
        "1991-2000": "1978-1999", "2001-2010": "2005-2009",
        "2011-2015": "2010-2014", "2016 or later": "2015-2019",
        "not stated": "1978-1999",
    }
    return mapping.get(saps_band, "1978-1999")


def _draw_tier(gen: np.random.Generator, privacy_z: float) -> str:
    """Draw a sensor tier, shifted down by the household's privacy strictness.

    Design 5.13: "Privacy strictness drives each home's sensor tier and Jetson
    consent, so tier uptake correlates with traits as it would in reality."  A
    privacy-conscious household is more likely to accept meter-only.
    """
    base = np.array([SENSOR_TIER_UPTAKE[t] for t in ("T1", "T2", "T3", "T4")])
    # Tilt: higher privacy shifts mass toward T1. exp(-k * z * rank) keeps all
    # tiers reachable, so the correlation is realistic rather than deterministic.
    ranks = np.array([0.0, 1.0, 2.0, 3.0])
    tilt = np.exp(-0.55 * float(privacy_z) * ranks)
    w = base * tilt
    w = w / w.sum()
    return str(gen.choice(["T1", "T2", "T3", "T4"], p=w))
