"""The declared U27 plausibility checks.

One entry per major output named in U27. Each states its source, its tolerance
and the basis for that tolerance; the three with no published Irish reference
are declared UNSOURCED with the issue that records the gap, because a suite
that quietly omitted them would read as coverage it does not have.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from baile_nua.plausibility.suite import PlausibilityCheck, read_jsonstat

__all__ = ["CHECKS"]

_DWELLING_MAP = {
    "Apartment": "apartment",
    "Mid-terrace house": "terraced",
    "End of terrace house": "terraced",
    "Semi-detached house": "semi-detached",
    "Detached house": "detached",
}


#: Simulated year. A reference from after it cannot validate it.
T0_YEAR = "2022"


def _year_at_or_before_t0(years: list[str], *, t0: str = T0_YEAR) -> str:
    """The latest reference year not after t0, else the earliest available.

    PxStat tables often carry projected or partial future years: NDA08 runs to
    2026, and the first version of the floor-area check took its latest year
    and validated a 2022 simulation against a 2026 figure. Where a table stops
    before t0 - HAS02 ends in 2019 - its latest year is used and the gap is
    reported, because a stale reference is a limitation to state and a future
    one is simply the wrong number.
    """
    eligible = [y for y in years if y <= t0]
    return max(eligible) if eligible else min(years)


def _diag(pkg: dict[str, Any]) -> dict[str, Any]:
    d = pkg.get("diagnostics")
    if not d:
        raise LookupError("no run_diagnostics.json in the package")
    return d


#: A run shorter than this cannot be compared to an annual reference.
MIN_DAYS_FOR_AN_ANNUAL_CHECK = 350


def _require_a_full_year(pkg: dict[str, Any]) -> int:
    """Refuse an annual comparison on a partial-year run.

    Found by the suite's own write hook on a three-day smoke run: the annual
    electricity and gas checks compared three days of accumulated energy
    against a yearly CSO figure and failed, as they had to.

    Scaling the partial total up would be worse than refusing it. A
    three-day run in January is three days of peak heating, so annualising it
    over-states gas by roughly a factor of two, and the check would then pass
    or fail on the arithmetic of the extrapolation rather than on the model.
    NO_DATA is the honest outcome, and it is reported rather than skipped.
    """
    d = _diag(pkg)
    n_days = int(d.get("benchmark", {}).get("n_days", 0))
    if n_days < MIN_DAYS_FOR_AN_ANNUAL_CHECK:
        raise LookupError(
            f"the run covers {n_days} days; an annual reference needs at "
            f"least {MIN_DAYS_FOR_AN_ANNUAL_CHECK}. Extrapolating a partial "
            f"year would make the verdict depend on which season it covered."
        )
    return n_days


# --------------------------------------------------------------------------- #
# 1. annual electricity by dwelling type and BER band
# --------------------------------------------------------------------------- #

def _check_electricity(pkg: dict[str, Any]):
    _require_a_full_year(pkg)
    d = _diag(pkg)
    rows = d.get("annual_electricity", {}).get("per_dwelling")
    if not rows:
        raise LookupError("no per-dwelling annual electricity in the diagnostics")
    frame = pd.DataFrame(rows)
    fossil = frame[~frame.heats_with_electricity]
    if fossil.empty:
        raise LookupError("no fossil-heated dwellings to compare")
    paired = fossil.dropna(subset=["d24_target_kwh_yr"])
    ratio = (paired.simulated_kwh_yr / paired.d24_target_kwh_yr).mean()
    # A fossil-heated dwelling's ELECTRICITY must sit below the cell, which
    # covers all household electricity including electric heating, and above
    # the point where it would imply no appliances at all.
    passed = bool(0.40 <= ratio <= 1.00)
    return (
        round(float(ratio), 3),
        "0.40 to 1.00 of the DBEREL01 cell",
        passed,
        {
            "n_dwellings": int(len(paired)),
            "mean_simulated_kwh_yr": round(float(paired.simulated_kwh_yr.mean()), 1),
            "mean_reference_kwh_yr": round(float(paired.d24_target_kwh_yr.mean()), 1),
            "why_a_band_not_a_point": (
                "DBEREL01 covers ALL household electricity, so a gas-heated "
                "dwelling cannot reach its cell: the part that is space "
                "heating is on the gas meter. The upper bound is 1.00 because "
                "exceeding it would mean the simulated appliances alone use "
                "more than real homes use for everything."
            ),
        },
    )


# --------------------------------------------------------------------------- #
# 2. annual gas (space heat) by dwelling type and BER band
# --------------------------------------------------------------------------- #

def _check_gas(pkg: dict[str, Any]):
    _require_a_full_year(pkg)
    d = _diag(pkg)
    block = d.get("annual_electricity", {}).get("summary", {}).get(
        "gas_heated_space_heat"
    )
    if not block or not block.get("n"):
        raise LookupError("no gas-heated space-heat summary in the diagnostics")
    ratio = float(block["mean_ratio_space_heat_over_gas_target"])
    # Simulated SPACE HEAT against a GAS METER, which also carries hot water,
    # gas cooking and boiler losses. Below 1.0 necessarily; the lower bound is
    # where space heat would be an implausibly small share of a gas bill.
    passed = bool(0.25 <= ratio <= 1.00)
    return (
        round(ratio, 3),
        "0.25 to 1.00 of the DBERNG01 cell",
        passed,
        {
            "n_dwellings": int(block["n"]),
            "mean_space_heat_kwh_yr": block["mean_space_heat_kwh_yr"],
            "mean_reference_kwh_yr": block["mean_d24_gas_target_kwh_yr"],
            "why_the_band_is_wide": (
                "Space heating is typically 60 to 80% of an Irish gas bill, so "
                "a model with no hot water, no gas cooking and no boiler "
                "losses should land below that. The band's lower edge is set "
                "at 0.25 until U25 adds those three terms, at which point it "
                "tightens - U22's acceptance test is that this ratio RISES."
            ),
            "above_1_would_be_unambiguously_wrong": True,
        },
    )


# --------------------------------------------------------------------------- #
# 3. appliance ownership (HAS02) - the [A] priors, finally scoreable
# --------------------------------------------------------------------------- #

#: Model appliance -> HAS02 appliance type. Only exact correspondences.
_HAS02_MAP = {
    "washing_machine": "Washing machine",
    "tumble_dryer": "Clothes dryer",
    "dishwasher": "Dishwasher",
    "microwave": "Microwave",
    # Added by U30. HAS02 has carried 'Colour television' at 96.3% (2019)
    # since the source was declared, and the map did not use it - the I-040
    # mistake a second time, inside the source that taught it: a declared
    # table with a mappable row left unmapped. The model's prior is 0.96.
    "television": "Colour television",
}

#: Refrigeration is the one appliance neither HAS02 nor the HBS can score
#: directly. Both publish OVERLAPPING sub-types - HAS02 2019: Fridge 40.2%,
#: Fridge with separate freezer 83.9%, Deep freeze 34.7%; HBS 2015:
#: Refrigerator 25.6%, Refrigerator with freezer 81.6% - which sum past 100%,
#: so a household can appear in two of them and the UNION is not published.
#: The model has a single refrigeration appliance, so its prior represents
#: that union.
#:
#: Comparing the prior against one sub-type would compare a union against a
#: part, which is what a first version of this check did: it scored 0.99
#: against 81.6% and failed. The valid inference from non-exclusive shares is
#: an interval - the union is at least the largest part and at most their sum,
#: capped at one - so that is what is checked, with the interval's width
#: reported so nobody mistakes a wide band for a tight result.
_OVERLAPPING_GROUPS: dict[str, tuple[str, ...]] = {
    "fridge_freezer": ("Refrigerator", "Refrigerator with freezer"),
}


def _check_appliance_ownership(pkg: dict[str, Any]):
    from baile_nua.devices.appliances import OWNERSHIP_PRIORS

    _doc, cells, _sha = read_jsonstat("cso.appliances.has02_ownership")
    stat = "Households who possess a household applicance"
    years = sorted({k[1] for k in cells if k[0] == stat})
    year = _year_at_or_before_t0(years)

    rows, bad = [], []
    for appliance, has02 in sorted(_HAS02_MAP.items()):
        ref = cells.get((stat, year, "Yes", has02))
        if ref is None:
            continue
        prior = float(OWNERSHIP_PRIORS[appliance]["base"])
        ref_frac = float(ref) / 100.0
        # The prior is a BASE rate before per-person and owner adjustments, so
        # it should sit at or below the population share rather than on it.
        ok = (ref_frac - 0.20) <= prior <= (ref_frac + 0.12)
        rows.append({
            "appliance": appliance, "has02_type": has02,
            "has02_share": round(ref_frac, 4),
            "model_base_prior": prior, "within": ok,
        })
        if not ok:
            bad.append(appliance)
    if not rows:
        raise LookupError("no HAS02 appliance types mapped")
    return (
        f"{len(rows) - len(bad)} of {len(rows)} base priors within band",
        f"HAS02 {year} ownership share, -0.20/+0.12",
        not bad,
        {
            "year_used": year,
            "reference_is_stale_by_years": max(int(T0_YEAR) - int(year), 0),
            "per_appliance": rows, "outside_band": bad,
            "why_asymmetric": (
                "The prior is a BASE rate, raised by per-person and "
                "owner-occupier terms before use, so it should sit at or below "
                "the population share. The band is wider below for that "
                "reason and tight above, where exceeding the national share "
                "before any adjustment would be an error."
            ),
            "note": (
                "Five of the fifteen OWNERSHIP_PRIORS stop being declared "
                "assumptions here. The Day-5 comment said 'SAPS publishes no "
                "appliance ownership', which is true and was taken to mean no "
                "public source existed; SILC's HAS02 does. The earlier "
                "version of this note said seven of nineteen, which was wrong "
                "on both counts: there are fifteen priors, and HAS02 mapped "
                "four until U30 added `television`. PL-APPL-02 takes the "
                "covered set to six of fifteen."
            ),
        },
    )


# --------------------------------------------------------------------------- #
# 4. floor area by dwelling type (NDA08, modern end; TRS05, lower bound)
# --------------------------------------------------------------------------- #

def _check_floor_area(pkg: dict[str, Any]):
    _doc, cells, _sha = read_jsonstat("cso.housing.nda08_new_dwelling_size_by_type")
    stat = "Average New Dwelling Size"
    years = sorted({k[1] for k in cells if k[0] == stat})
    year = _year_at_or_before_t0(years)
    ref = {
        "apartment": cells.get((stat, year, "Apartment")),
        "scheme house": cells.get((stat, year, "Scheme house")),
        "single house": cells.get((stat, year, "Single house")),
    }
    if not any(ref.values()):
        raise LookupError("NDA08 has no values for the latest year")

    d = _diag(pkg)
    rows = d.get("annual_electricity", {}).get("per_dwelling")
    if not rows:
        raise LookupError("no per-dwelling rows carrying floor area")
    frame = pd.DataFrame(rows)
    if "floor_area_m2" not in frame.columns:
        raise LookupError("the package's per-dwelling rows carry no floor area")

    med = frame.groupby("dwelling_type").floor_area_m2.median().to_dict()
    # NDA08 is NEW dwellings, so it bounds the modern end. The ordering is the
    # falsifiable part and holds for any era: an apartment is smaller than a
    # house.
    apt = med.get("apartment")
    houses = [v for k, v in med.items() if k != "apartment"]
    ordering_ok = (apt is None) or (not houses) or (apt < min(houses))
    apt_ok = True
    if apt is not None and ref["apartment"]:
        # Within a factor of two of the new-build apartment mean, either way:
        # the stock spans eras this reference does not.
        apt_ok = 0.5 * float(ref["apartment"]) <= apt <= 2.0 * float(ref["apartment"])
    passed = bool(ordering_ok and apt_ok)
    return (
        {k: round(float(v), 1) for k, v in sorted(med.items())},
        {"nda08_year": year, **{k: v for k, v in ref.items() if v}},
        passed,
        {
            "apartment_smaller_than_every_house_type": bool(ordering_ok),
            "apartment_within_2x_of_new_build_mean": bool(apt_ok),
            "why_only_a_factor_of_two": (
                "NDA08 covers new dwellings and the simulated stock spans "
                "1860 to 2021, so the levels legitimately differ. The "
                "ORDERING does not: an apartment is smaller than a house in "
                "every era, and I-031's fault was exactly that ordering "
                "inverting."
            ),
        },
    )


# --------------------------------------------------------------------------- #
# 5. residential fuel mix (SEI01) - the one check that sees the balance
# --------------------------------------------------------------------------- #

def _check_fuel_mix(pkg: dict[str, Any]):
    _require_a_full_year(pkg)
    _doc, cells, _sha = read_jsonstat("cso.energy.sei01_energy_balance")
    stat = "Energy Balance"
    years = sorted({k[2] for k in cells if k[0] == stat}) if cells else []
    if not years:
        raise LookupError("SEI01 has no years")
    year = _year_at_or_before_t0(years)

    def ktoe(fuel: str) -> float | None:
        v = cells.get((stat, fuel, year, "Residential")) or cells.get(
            (stat, "Residential", year, fuel)
        )
        return float(v) if v is not None else None

    elec = ktoe("Electricity")
    gas = ktoe("Natural gas")
    if elec is None or gas is None:
        raise LookupError(
            f"SEI01 does not expose Residential electricity and gas for {year} "
            f"on the axis order tried"
        )
    ref_ratio = elec / gas

    d = _diag(pkg)
    summary = d.get("annual_electricity", {}).get("summary", {})
    gasblock = summary.get("gas_heated_space_heat", {})
    fossil = summary.get("fossil_heated", {})
    if not gasblock.get("n") or not fossil.get("n"):
        raise LookupError("no fuel blocks in the diagnostics")
    sim_elec = float(fossil["mean_simulated_kwh_yr"])
    sim_gas = float(gasblock["mean_space_heat_kwh_yr"])
    sim_ratio = sim_elec / max(sim_gas, 1e-9)
    # Wide band: the simulated gas figure is space heat only, so the simulated
    # ratio is biased UP against a national balance that includes hot water
    # and cooking in the gas term.
    passed = bool(0.25 <= sim_ratio <= 3.0 * ref_ratio)
    return (
        round(sim_ratio, 3),
        {"sei01_year": year, "national_elec_over_gas_ratio": round(ref_ratio, 3)},
        passed,
        {
            "simulated_electricity_kwh_yr": round(sim_elec, 1),
            "simulated_space_heat_kwh_yr": round(sim_gas, 1),
            "why_the_upper_bound_is_3x": (
                "The simulated gas term is space heat ALONE while the national "
                "balance's gas includes hot water and cooking, so the "
                "simulated ratio is biased upward by construction. Three times "
                "the national ratio is where that bias stops explaining it."
            ),
            "this_is_the_only_check_that_sees_the_balance": (
                "Every other reference checks one fuel at a time and cannot "
                "detect a town that gets each right separately and the "
                "relationship between them wrong."
            ),
        },
    )


# --------------------------------------------------------------------------- #
# 6. indoor temperature distribution - UNSOURCED
# --------------------------------------------------------------------------- #

def _check_indoor_temperature(pkg: dict[str, Any]):
    frame = pkg.get("D16")
    if frame is None or "temp_living_c" not in frame.columns:
        raise LookupError("no D16 with temp_living_c in the package")
    v = pd.to_numeric(frame.temp_living_c, errors="coerce").dropna()
    return (
        {
            "median_c": round(float(v.median()), 2),
            "share_above_28c": round(float((v > 28).mean()), 4),
            "max_c": round(float(v.max()), 2),
        },
        "declared band [A]: median 15-23 C, <=5% above 28 C, peak <=40 C",
        bool(15.0 <= float(v.median()) <= 23.0
             and float((v > 28).mean()) <= 0.05
             and float(v.max()) <= 40.0),
        {"n_epochs": int(len(v))},
    )


# --------------------------------------------------------------------------- #
# U30: the Household Budget Survey. HAS02 (SILC) gave seven appliances; the HBS
# gives thirteen, and gives them BY HOUSEHOLD SIZE - which is the quantity the
# `per_person` slopes assume and the quantity the code's own comment called
# not-in-doubt-only-its-slope. Found by searching dimension LABELS: HS023's
# title is the bare word "Households".
# --------------------------------------------------------------------------- #

#: Model appliance -> the HBS appliance categories that make it up. Television
#: is the sum of the two TV categories, because the HBS asks how many sets a
#: household has and the model asks only whether it has one.
_HBS_MAP: dict[str, tuple[str, ...]] = {
    "washing_machine": ("Washing machine",),
    "tumble_dryer": ("Tumble dryer",),
    "dishwasher": ("Dishwasher",),
    "microwave": ("Microwave oven",),
    "television": ("One TV set only", "Two or more TV sets"),
}

#: Household-size categories in HS219, and the occupancy each stands for.
#: "6 + Persons" is read as 6: the model's own ownership term saturates with
#: ``max(n_people - 2, 0)`` and the open class cannot be read as more without
#: inventing a mean household size for it.
_HBS_SIZES: tuple[tuple[str, int], ...] = (
    ("1 person", 1), ("2 persons", 2), ("3 persons", 3),
    ("4 persons", 4), ("5 persons", 5), ("6 + Persons", 6),
)

#: Declared band for the per-person slope, before measuring. HS219's shares
#: come from a survey of roughly 6,800 households, so a slope fitted over five
#: size classes carries a standard error of order 0.01 per person. 0.05 is five
#: times that: generous, because the model's base and owner-occupier terms
#: interact with the slope, and still tight enough to reject a slope of the
#: wrong sign or an order-of-magnitude error - which is what a declared
#: constant is actually at risk of.
SLOPE_TOLERANCE_PER_PERSON = 0.05

#: Below this, the published relationship is flat and the model should not
#: claim one.
FLAT_SLOPE_THRESHOLD = 0.01


def _hbs_share(cells, appliance: str, size_label: str, year: str) -> float | None:
    """Total ownership share for a model appliance, as a fraction."""
    total = 0.0
    seen = False
    for cat in _HBS_MAP[appliance]:
        v = cells.get(("Households", cat, size_label, year))
        if v is not None:
            total += float(v)
            seen = True
    return (total / 100.0) if seen else None


def _check_hbs_ownership(pkg: dict[str, Any]):
    """PL-APPL-02: base priors against the HBS's thirteen appliances."""
    from baile_nua.devices.appliances import OWNERSHIP_PRIORS

    _doc, cells, _sha = read_jsonstat(
        "cso.appliances.hs023_hbs_appliances_urban_rural"
    )
    years = sorted({k[3] for k in cells})
    year = _year_at_or_before_t0(years)

    rows, bad = [], []
    for appliance in sorted(_HBS_MAP):
        total = 0.0
        seen = False
        for cat in _HBS_MAP[appliance]:
            v = cells.get(("Households", cat, "State", year))
            if v is not None:
                total += float(v)
                seen = True
        if not seen:
            continue
        ref_frac = total / 100.0
        prior = float(OWNERSHIP_PRIORS[appliance]["base"])
        # Same asymmetric reasoning as PL-APPL-01: the prior is a BASE rate,
        # raised by per-person and owner terms before use, so it belongs at or
        # below the population share.
        ok = (ref_frac - 0.20) <= prior <= (ref_frac + 0.12)
        rows.append({
            "appliance": appliance,
            "hbs_categories": list(_HBS_MAP[appliance]),
            "hbs_share": round(ref_frac, 4),
            "model_base_prior": prior,
            "within": ok,
        })
        if not ok:
            bad.append(appliance)
    # The overlapping refrigeration categories, as an interval rather than a
    # point. A deep freeze is deliberately left out of the group: it is a
    # supplementary appliance, not the household's refrigerator, and adding it
    # would only widen an upper bound already capped at one.
    for appliance, parts in sorted(_OVERLAPPING_GROUPS.items()):
        shares = []
        for cat in parts:
            v = cells.get(("Households", cat, "State", year))
            if v is not None:
                shares.append(float(v) / 100.0)
        if not shares:
            continue
        lower = max(shares)
        upper = min(1.0, sum(shares))
        prior = float(OWNERSHIP_PRIORS[appliance]["base"])
        # This appliance has no per-person or owner term, so the base rate IS
        # the ownership probability and the logical bound applies to it
        # directly, with no asymmetric allowance.
        ok = lower <= prior <= upper
        rows.append({
            "appliance": appliance,
            "hbs_categories": list(parts),
            "categories_overlap": True,
            "union_share_lower_bound": round(lower, 4),
            "union_share_upper_bound": round(upper, 4),
            "interval_width": round(upper - lower, 4),
            "model_base_prior": prior,
            "within": ok,
            "why_an_interval": (
                "The published categories are not mutually exclusive and sum "
                "past 100%, so the share of households with ANY refrigerator "
                "- which is what the model's single prior means - is bounded, "
                "not published. A point comparison against one sub-type would "
                "compare a union against a part."
            ),
        })
        if not ok:
            bad.append(appliance)

    if not rows:
        raise LookupError("no HBS appliance types mapped")
    return (
        f"{len(rows) - len(bad)} of {len(rows)} base priors within band",
        f"HBS {year} ownership share, -0.20/+0.12",
        not bad,
        {
            "year_used": year,
            "reference_is_stale_by_years": max(int(T0_YEAR) - int(year), 0),
            "per_appliance": rows,
            "outside_band": bad,
            "what_this_adds_over_has02": (
                "`television`, as 'One TV set only' plus 'Two or more TV "
                "sets', and `fridge_freezer` as 'Refrigerator with freezer'. "
                "HAS02 maps four appliances; this maps six. The HBS also "
                "publishes vacuum cleaner, home computer and games console, "
                "which this model does not simulate."
            ),
        },
    )


def _check_ownership_slope(pkg: dict[str, Any]):
    """PL-APPLSIZE-01: the `per_person` slopes against HS219.

    The model's ownership probability is
    ``base + per_person * max(n_people - 2, 0)``, so HS219's ownership by
    household size scores the slope directly - and at two persons it scores
    ``base`` with nothing added, which is a sharper comparison than a national
    average.
    """
    from baile_nua.devices.appliances import OWNERSHIP_PRIORS

    _doc, cells, _sha = read_jsonstat(
        "cso.appliances.hs219_hbs_appliances_by_household_size"
    )
    years = sorted({k[3] for k in cells})
    year = _year_at_or_before_t0(years)

    rows, bad = [], []
    for appliance in sorted(_HBS_MAP):
        prior = OWNERSHIP_PRIORS.get(appliance)
        if prior is None:
            continue
        pts = [
            (n, _hbs_share(cells, appliance, label, year))
            for label, n in _HBS_SIZES
        ]
        pts = [(n, v) for n, v in pts if v is not None]
        # Fit over the range the model's term is active on: two persons and up.
        active = [(n, v) for n, v in pts if n >= 2]
        if len(active) < 3:
            continue
        mean_n = sum(n for n, _ in active) / len(active)
        mean_v = sum(v for _, v in active) / len(active)
        denom = sum((n - mean_n) ** 2 for n, _ in active)
        published = (
            sum((n - mean_n) * (v - mean_v) for n, v in active) / denom
            if denom else 0.0
        )
        modelled = float(prior.get("per_person", 0.0))
        magnitude_ok = abs(modelled - published) <= SLOPE_TOLERANCE_PER_PERSON
        if abs(published) < FLAT_SLOPE_THRESHOLD:
            # Published relationship is flat; the model must not invent one.
            sign_ok = modelled < 2.0 * FLAT_SLOPE_THRESHOLD
            shape = "flat"
        else:
            sign_ok = (modelled > 0) == (published > 0)
            shape = "rising" if published > 0 else "falling"
        ok = bool(magnitude_ok and sign_ok)
        at_two = dict(pts).get(2)
        rows.append({
            "appliance": appliance,
            "published_slope_per_person": round(published, 4),
            "model_per_person": modelled,
            "published_shape": shape,
            "sign_ok": sign_ok,
            "magnitude_ok": magnitude_ok,
            "within": ok,
            "hs219_share_at_2_persons": (
                None if at_two is None else round(at_two, 4)
            ),
            "model_base_prior": float(prior["base"]),
            "curve": [
                {"household_size": n, "hs219_share": round(v, 4),
                 "model_p": round(
                     float(prior["base"])
                     + modelled * max(n - 2, 0), 4)}
                for n, v in pts
            ],
        })
        if not ok:
            bad.append(appliance)
    if not rows:
        raise LookupError("no HS219 appliance types mapped")
    return (
        f"{len(rows) - len(bad)} of {len(rows)} slopes within band",
        f"HS219 {year} slope, +/-{SLOPE_TOLERANCE_PER_PERSON} per person",
        not bad,
        {
            "year_used": year,
            "reference_is_stale_by_years": max(int(T0_YEAR) - int(year), 0),
            "per_appliance": rows,
            "outside_band": bad,
            "model_form": "base + per_person * max(n_people - 2, 0)",
            "why_this_matters": (
                "The code's comment on these slopes read 'the sub-linearity "
                "is not in doubt, only its slope'. HS219 publishes the slope. "
                "This is the U30 find that most directly contradicts an [A] "
                "comment: the quantity named as unmeasured is a published "
                "dimension of a survey the CSO has run since 1951."
            ),
            "may_not_be_used_to_tune": (
                "The slopes were set on Day 5 and HS219 was found on 9 Oct "
                "2026, so this reference judges them. Fitting them to it "
                "would make the source calibration, not validation, and its "
                "declaration would have to change (I-040)."
            ),
        },
    )


# --------------------------------------------------------------------------- #
# I-039 / PL-PEAK-01: feeder loading, against ESB Networks' LP1.
#
# U30 established that PxStat publishes nothing on this - zero hits for every
# phrasing of peak and load factor across 13,086 tables (I-043). ESB Networks
# publishes it: LP1 Urban Domestic 24 Hour, quarter-hourly coefficients summing
# to 1.0 over the year, from which a load factor needs no other input.
#
# Read from D19's 15-minute intervals, not D18's 1-minute channels, for two
# reasons: the reference is quarter-hourly, so the comparison is
# resolution-matched rather than biased by measuring the peak more finely than
# the reference does; and 15-minute views are what U28 keeps for every home, so
# this check still runs on the ten-year town package.
# --------------------------------------------------------------------------- #

def _check_peak_and_load_factor(pkg: dict[str, Any]):
    from baile_nua.plausibility.slp import (
        LOAD_FACTOR_LOWER_ALLOWANCE,
        LOAD_FACTOR_UPPER_ALLOWANCE,
        MIN_HOMES_FOR_A_LOWER_BOUND,
        MIN_OVERNIGHT_TAPER,
        PEAK_HOUR_TOLERANCE,
        lp1_reference,
        overnight_shape_mad,
    )

    #: Which D19 view to read, in order of preference. D19 holds FOUR export
    #: configurations of the same energy - home_15min, home_30min,
    #: compliance_only and a pre-summed estate_aggregate - so summing its rows
    #: without choosing one counts the estate about four times. A first version
    #: of this check did exactly that and reported 9.2 kW per home against the
    #: diagnostics' own 1.49 kW. One view is selected by name, and an
    #: ambiguous selection raises rather than being silently summed.
    PREFERRED_VIEWS = ("home_15min", "home_30min")

    ref = lp1_reference()
    frame = pkg.get("D19")
    if frame is None or frame.empty:
        raise LookupError("the package holds no D19 export view")
    for col in ("premises_id", "interval_start", "interval_end", "import_wh"):
        if col not in frame.columns:
            raise LookupError(f"D19 carries no {col}")

    view = None
    if "export_config" in frame.columns:
        present = set(frame.export_config.unique())
        view = next((v for v in PREFERRED_VIEWS if v in present), None)
        if view is None:
            raise LookupError(
                f"D19 holds none of the per-home views {PREFERRED_VIEWS}; it "
                f"has {sorted(present)}. Summing across configurations would "
                f"count the same energy more than once."
            )
        frame = frame[frame.export_config == view]

    minutes = (
        (frame.interval_end - frame.interval_start)
        .dt.total_seconds().div(60).round().astype("int64")
    )
    durations = sorted(minutes.unique().tolist())
    if len(durations) != 1:
        raise LookupError(
            f"the chosen D19 view mixes interval lengths {durations}; a load "
            f"factor is resolution-dependent and cannot be taken across them"
        )
    interval_minutes = int(durations[0])
    intervals_per_day = 1440 // interval_minutes

    n_homes = int(frame.premises_id.nunique())
    series = frame.groupby("interval_start", sort=True).import_wh.sum()
    if series.empty:
        raise LookupError("D19 held no intervals")

    n_intervals = int(len(series))
    n_days = n_intervals / float(intervals_per_day)
    if n_days < MIN_DAYS_FOR_AN_ANNUAL_CHECK:
        # The same refusal as the annual energy checks, for the same reason: a
        # load factor is an annual quantity against an annual profile, and a
        # few winter days would make the verdict turn on which days they were.
        raise LookupError(
            f"the package covers {n_days:.0f} days of D19; a load factor is "
            f"an annual quantity and LP1 is an annual profile, so fewer than "
            f"{MIN_DAYS_FOR_AN_ANNUAL_CHECK} days cannot be compared"
        )

    mean = float(series.mean())
    peak = float(series.max())
    if peak <= 0:
        raise LookupError("D19's aggregate import is zero throughout")
    load_factor = mean / peak

    index = pd.DatetimeIndex(series.index)
    by_hour = series.groupby(index.hour).mean()
    peak_hour = int(by_hour.idxmax())
    trough_hour = int(by_hour.idxmin())

    upper = ref["load_factor"] + LOAD_FACTOR_UPPER_ALLOWANCE
    upper_ok = bool(load_factor <= upper)
    lower_applies = n_homes >= MIN_HOMES_FOR_A_LOWER_BOUND
    lower = ref["load_factor"] - LOAD_FACTOR_LOWER_ALLOWANCE
    lower_ok = bool(load_factor >= lower) if lower_applies else None
    peak_hour_ok = bool(
        abs(peak_hour - ref["mean_day_peak_hour"]) <= PEAK_HOUR_TOLERANCE
    )
    day_mean = float(by_hour.mean())
    hourly = {int(h): float(v) / day_mean for h, v in by_hour.items()}

    # U32. The gating overnight term is the whole SHAPE from 22:00 to 06:00
    # against LP1, not a ratio of two hours. I-050: the step 4 ablation
    # improved the two-point taper by making the model worse - synchronising
    # the town moved the 04:00 denominator while midnight did not move at all.
    shape = None
    shape_ok = None
    try:
        shape = overnight_shape_mad(hourly)
        shape_ok = bool(shape["within_band"])
    except LookupError:
        shape = None

    # The taper stays as a SECONDARY metric: reported, never gating. It is the
    # quantity I-044 was diagnosed and fixed against, so dropping it would make
    # that history unreadable.
    taper = (
        float(by_hour.loc[0] / by_hour.loc[4])
        if 0 in by_hour.index and 4 in by_hour.index and by_hour.loc[4]
        else None
    )
    taper_ok = None if taper is None else bool(taper >= MIN_OVERNIGHT_TAPER)

    terms = [upper_ok, peak_hour_ok]
    if shape_ok is not None:
        terms.append(shape_ok)
    if lower_ok is not None:
        terms.append(lower_ok)

    return (
        {
            "load_factor": round(load_factor, 4),
            "peak_over_mean": round(peak / mean, 4),
            "mean_day_peak_hour": peak_hour,
            "mean_day_trough_hour": trough_hour,
            "overnight_taper_00_over_04": (
                None if taper is None else round(taper, 4)
            ),
            # Wh in an interval to the average W over it.
            "aggregate_peak_w": round(peak * (60.0 / interval_minutes), 1),
            "aggregate_peak_w_per_home": round(
                peak * (60.0 / interval_minutes) / max(n_homes, 1), 1
            ),
        },
        {
            "load_factor": ref["load_factor"],
            "peak_over_mean": ref["peak_over_mean"],
            "mean_day_peak_hour": ref["mean_day_peak_hour"],
            "mean_day_trough_hour": ref["mean_day_trough_hour"],
            "overnight_taper_00_over_04": ref["overnight_taper_00_over_04"],
            "min_overnight_taper": MIN_OVERNIGHT_TAPER,
            "overnight_shape_band": (
                shape["band"] if shape else None
            ),
        },
        all(terms),
        {
            "reference": {k: ref[k] for k in (
                "source_key", "sha256", "sheet", "title", "year",
                "load_factor", "peak_over_mean", "mean_day_peak_hour",
                "mean_day_trough_hour", "annual_peak_at",
            )},
            "n_homes_aggregated": n_homes,
            "n_intervals": n_intervals,
            "n_days": round(n_days, 1),
            "read_from": (
                "D19's 15-minute intervals, matching LP1's quarter-hourly "
                "resolution. D18's 1-minute channels would measure the peak "
                "more finely than the reference does, which can only lower "
                "the load factor, and 15-minute views are what U28 keeps for "
                "every home so this check survives to the ten-year package."
            ),
            "load_factor_upper_bound": round(upper, 4),
            "load_factor_upper_ok": upper_ok,
            "load_factor_lower_bound_applies": lower_applies,
            "load_factor_lower_bound": round(lower, 4) if lower_applies else None,
            "load_factor_lower_ok": lower_ok,
            "view_read": view,
            "interval_minutes": interval_minutes,
            "mean_day_peak_hour_ok": peak_hour_ok,
            # U32: the gating overnight term.
            "overnight_shape": shape,
            "overnight_shape_ok": shape_ok,
            # Secondary, reported but not gating (I-050).
            "overnight_taper_ok": taper_ok,
            "why_the_taper_is_no_longer_gating": (
                "A two-point ratio can be moved by either point. The week 2 "
                "step 4 ablation improved this taper from 1.199 to 1.285 by "
                "removing chronotype - which synchronised the town, raised "
                "the 22:00 peak and lowered the 04:00 trough, while midnight "
                "did not move at all. The shape metric ranks that same arm "
                "WORSE, which is why it gates and this does not (I-050, U32)."
            ),
            "mean_day_trough_hour_is_reported_not_tested": (
                "LP1's overnight falls steadily from 0.77x the daily mean at "
                "midnight to 0.45x at 04:00, so its trough hour is 04:00. A "
                "flat overnight profile's argmin lands wherever noise puts "
                "it, which is not a statistic, so the taper RATIO is tested "
                "and the trough hour only reported."
            ),
            "hourly_shape_over_day_mean": {
                int(h): round(float(v) / day_mean, 4)
                for h, v in by_hour.items()
            },
            "why_the_lower_bound_may_not_apply": (
                f"LP1 aggregates about two million meters; this package "
                f"aggregates {n_homes}. A smaller aggregate is legitimately "
                f"spikier, so LP1 bounds it from above only until "
                f"{MIN_HOMES_FOR_A_LOWER_BOUND} homes."
            ),
            "what_is_still_unsourced": (
                "An INDIVIDUAL household's peak and load factor. LP1 is "
                "after-diversity, the right instrument for feeder loading and "
                "the wrong one for one dwelling; a single household's peak "
                "needs smart-meter or sub-metered microdata, which in Ireland "
                "means CER/ISSDA and the brief forbids it. I-043 keeps that "
                "half open."
            ),
        },
    )


# --------------------------------------------------------------------------- #
# U25 / PL-DHW-01: hot water volume, against the one published bound there is.
#
# DEAP publishes no hot water volume. What it publishes is a WATER EFFICIENCY
# target - "not more than 125 litres per person per day (all water use, hot and
# cold)" - and hot water is a subset of all water, so the target is a hard
# ceiling on it even though it is not a target for it. That is the whole of the
# published evidence, and the check says so rather than implying more.
#
# The check exists because the first version of the draw model put household
# hot water at about 800 litres a day: DEAP's 6 L/min was charged across the
# whole shower_bath EPISODE, which is time in the bathroom and runs to 25
# minutes, giving a 150-litre shower. Nothing caught it except noticing. This
# is what catches it next time.
# --------------------------------------------------------------------------- #

def _check_hot_water_volume(pkg: dict[str, Any]):
    from baile_nua.physics.dhw import deap_figures

    _require_a_full_year(pkg)
    d = _diag(pkg)
    rows = d.get("annual_electricity", {}).get("per_dwelling")
    if not rows:
        raise LookupError("no per-dwelling rows")
    frame = pd.DataFrame(rows)
    if "dhw_litres_yr" not in frame.columns:
        raise LookupError("the package carries no hot water volume")
    n_people = int(d.get("slice", {}).get("n_people", 0))
    if n_people <= 0:
        raise LookupError("the diagnostics record no occupant count")

    n_days = int(d.get("benchmark", {}).get("n_days", 0)) or 365
    litres_per_person_day = (
        float(frame.dhw_litres_yr.sum()) / n_people / n_days
    )
    ceiling = float(
        deap_figures()["demand"]["water_efficiency_target_l_per_person_day"]
    )
    # A floor too, because a model that drew almost no hot water would also
    # pass a ceiling. 15 L/person/day is below any plausible household and is
    # declared as the point at which the subsystem has effectively stopped
    # working rather than as a target.
    floor = 15.0
    ok = floor <= litres_per_person_day <= ceiling
    return (
        round(litres_per_person_day, 1),
        f"at most {ceiling:.0f} L/person/day (DEAP all-water target), "
        f"at least {floor:.0f}",
        ok,
        {
            "litres_per_person_per_day": round(litres_per_person_day, 2),
            "n_people": n_people,
            "n_days": n_days,
            "deap_all_water_target": ceiling,
            "share_of_the_all_water_target": round(
                litres_per_person_day / ceiling, 3
            ),
            "why_a_ceiling_and_not_a_target": (
                "DEAP publishes no hot water volume. It publishes a water "
                "EFFICIENCY target of 125 L/person/day for all water use, hot "
                "and cold, and hot water is a subset of all water - so the "
                "target bounds it from above without being a target for it. "
                "The hot/cold split is not published, so the check claims no "
                "more than the bound."
            ),
            "what_this_catches": (
                "The first draw model charged DEAP's 6 L/min across the whole "
                "shower_bath episode, which is time in the bathroom and runs "
                "to 25 minutes. That made 150-litre showers and about 800 "
                "litres a day per household, and nothing caught it except "
                "noticing."
            ),
            "arbiter_note": (
                "The real external constraint on hot water volume is the gas "
                "meter: DBERNG01 contains it, so PL-GAS-01 bounds it from "
                "both sides once U25's terms are in. This check is the cheap "
                "guard, not the arbiter."
            ),
        },
    )


CHECKS: tuple[PlausibilityCheck, ...] = (
    PlausibilityCheck(
        check_id="PL-DHW-01", family="hot water volume",
        quantity="hot water drawn, litres per person per day",
        source_key="seai.deap.manual_4_2_7",
        reference_note=(
            "DEAP Appendix I's water efficiency target: 'not more than 125 "
            "litres per person per day (all water use, hot and cold)'. Hot "
            "water is a subset, so this is a ceiling on it rather than a "
            "target for it, and the hot/cold split is not published."
        ),
        tolerance="between 15 and 125 litres per person per day",
        tolerance_basis=(
            "The ceiling is DEAP's published all-water target, which bounds a "
            "subset of itself. The floor is declared: a model drawing under 15 "
            "L/person/day has effectively stopped drawing hot water, and a "
            "ceiling alone would pass that. U30 found zero PxStat hits for "
            "hot water, so there is no better reference to use."
        ),
        measure=_check_hot_water_volume,
    ),
    PlausibilityCheck(
        check_id="PL-APPL-02", family="appliance ownership",
        quantity="appliance ownership base priors against the HBS's thirteen appliances",
        source_key="cso.appliances.hs023_hbs_appliances_urban_rural",
        reference_note=(
            "HS023 share of households possessing each of thirteen "
            "appliances. Found by U30's sweep of dimension labels; its title "
            "is the single word 'Households'."
        ),
        tolerance="base prior within -0.20/+0.12 of the national share",
        tolerance_basis=(
            "The same asymmetric reasoning as PL-APPL-01: a base rate is "
            "raised by per-person and owner terms before use, so it belongs "
            "at or below the population share."
        ),
        measure=_check_hbs_ownership,
    ),
    PlausibilityCheck(
        check_id="PL-APPLSIZE-01", family="appliance ownership",
        quantity="ownership slope per additional occupant",
        source_key="cso.appliances.hs219_hbs_appliances_by_household_size",
        reference_note=(
            "HS219 ownership by household size, 1 to 6+ persons. The model's "
            "term is base + per_person * max(n_people - 2, 0), so this scores "
            "the slope directly and, at two persons, the base with nothing "
            "added."
        ),
        tolerance=(
            f"slope within +/-{SLOPE_TOLERANCE_PER_PERSON} per person of the "
            f"published slope, and of the published sign"
        ),
        tolerance_basis=(
            "HS219 covers roughly 6,800 households, so a slope fitted over "
            "five size classes has a standard error of order 0.01 per person; "
            "0.05 is five times that, generous because base and owner terms "
            "interact with the slope, and still tight enough to reject a "
            "wrong sign or an order-of-magnitude error."
        ),
        measure=_check_ownership_slope,
    ),
    PlausibilityCheck(
        check_id="PL-ELEC-01", family="annual electricity",
        quantity="mean annual household electricity, fossil-heated dwellings, "
                 "as a ratio of its DBEREL01 dwelling-type x BER cell",
        source_key="cso.electricity.dbere101_by_dwelling_ber",
        reference_note="DBEREL01, 2022, mean kWh per dwelling by type and band.",
        tolerance="ratio in [0.40, 1.00]",
        tolerance_basis=(
            "The cell covers ALL household electricity, so a gas-heated home "
            "cannot reach it; exceeding 1.00 would mean simulated appliances "
            "alone beat real homes' total."
        ),
        measure=_check_electricity,
    ),
    PlausibilityCheck(
        check_id="PL-GAS-01", family="annual gas",
        quantity="mean simulated space heat, gas-heated dwellings, as a ratio "
                 "of its DBERNG01 dwelling-type x BER cell",
        source_key="cso.gas.dberng01_by_dwelling_ber",
        reference_note="DBERNG01, 2022, mean gas kWh per dwelling by type and band.",
        tolerance="ratio in [0.25, 1.00]",
        tolerance_basis=(
            "Space heat is 60-80% of an Irish gas bill; with no hot water, gas "
            "cooking or boiler losses the model must land below that. The "
            "lower edge tightens once U25 adds them - U22's acceptance test is "
            "that this ratio rises."
        ),
        measure=_check_gas,
    ),
    PlausibilityCheck(
        check_id="PL-APPL-01", family="appliance ownership",
        quantity="appliance ownership base priors against SILC HAS02",
        source_key="cso.appliances.has02_ownership",
        reference_note="HAS02 share of households possessing each appliance.",
        tolerance="base prior within -0.20/+0.12 of the national share",
        tolerance_basis=(
            "The prior is a base rate before per-person and owner-occupier "
            "adjustments, so it should sit at or below the national share: "
            "wide below, tight above."
        ),
        measure=_check_appliance_ownership,
    ),
    PlausibilityCheck(
        check_id="PL-AREA-01", family="floor area",
        quantity="median floor area by dwelling type",
        source_key="cso.housing.nda08_new_dwelling_size_by_type",
        reference_note="NDA08 average new dwelling size by type, latest year.",
        tolerance=(
            "apartment smaller than every house type, and within a factor of "
            "two of the new-build apartment mean"
        ),
        tolerance_basis=(
            "NDA08 is new dwellings and the stock spans 1860-2021, so levels "
            "legitimately differ; the ORDERING does not, and I-031 was exactly "
            "that ordering inverting."
        ),
        measure=_check_floor_area,
    ),
    PlausibilityCheck(
        check_id="PL-MIX-01", family="fuel mix",
        quantity="simulated electricity-to-gas ratio against the national "
                 "residential energy balance",
        source_key="cso.energy.sei01_energy_balance",
        reference_note="SEI01 Residential final consumption by fuel, ktoe.",
        tolerance="simulated ratio in [0.25, 3x the national ratio]",
        tolerance_basis=(
            "The simulated gas term is space heat alone while the national gas "
            "term includes hot water and cooking, biasing the simulated ratio "
            "upward by construction."
        ),
        measure=_check_fuel_mix,
    ),
    PlausibilityCheck(
        check_id="PL-TEMP-01", family="indoor temperature",
        quantity="indoor living-zone temperature distribution",
        source_key=None,
        unsourced_issue="I-032 (band declared [A]); see also I-039",
        reference_note=(
            "No CSO or SEAI table publishes measured Irish indoor "
            "temperatures. The band used by the V0 invariant - annual median "
            "15 to 23 C, at most 5% of epochs above 28 C, peak at most 40 C - "
            "is a declared assumption whose job is to refuse the implausible, "
            "not to calibrate. The fault it was written for (median 24.6 C, "
            "19% above 30 C, peak 64.3 C) would fail a band of any width."
        ),
        tolerance="median 15-23 C; <=5% above 28 C; peak <=40 C [A]",
        tolerance_basis="declared, not sourced",
        has_declared_band=True,
        measure=_check_indoor_temperature,
    ),
    PlausibilityCheck(
        check_id="PL-APPLSHARE-01", family="appliance energy shares",
        quantity="share of household electricity by appliance",
        source_key=None,
        unsourced_issue="I-039",
        reference_note=(
            "PxStat publishes appliance OWNERSHIP (HAS02, now checked) but no "
            "end-use energy breakdown. SEAI's residential sector reports carry "
            "one, as narrative PDF tables rather than a machine-readable "
            "series, so it cannot be registered as a source and read at run "
            "time under the brief's rules."
        ),
        tolerance="none declared",
        tolerance_basis="unsourced",
        measure=lambda pkg: (None, None, False, {}),
    ),
    PlausibilityCheck(
        check_id="PL-EVHP-01", family="EV and heat-pump consumption",
        quantity="annual EV charging and heat-pump electricity per dwelling",
        source_key=None,
        unsourced_issue="I-039",
        reference_note=(
            "PxStat has EV ownership (NTA43-49, HEBEU55-90) and public "
            "charge-point consumption (MEC08), and heat-pump PENETRATION "
            "(EBQ02, already registered), but no domestic kWh for either. "
            "DBEREL01's A-B cells are heat-pump-heavy and give an indirect "
            "check, which PL-ELEC-01 already exercises."
        ),
        tolerance="none declared",
        tolerance_basis="unsourced",
        measure=lambda pkg: (None, None, False, {}),
    ),
    PlausibilityCheck(
        check_id="PL-PEAK-01", family="peak and load factor",
        quantity="aggregate (after-diversity) load factor and diurnal shape",
        source_key="esbn.rmds.slp_indexes_2022",
        reference_note=(
            "ESB Networks Standard Load Profile LP1, Urban Domestic 24 Hour, "
            "2022: quarter-hourly Demand Energy Coefficients summing to 1.0 "
            "over the year, so the load factor needs no other input. "
            "Measured: load factor 0.4129, annual peak 2.422x the mean, "
            "mean-day peak 18:00, trough 04:00. U30 established that PxStat "
            "publishes nothing on this (I-043); the network operator does."
        ),
        tolerance=(
            "load factor at most 0.05 above LP1's, and - once at least 1,000 "
            "homes are aggregated - at most 0.15 below; mean-day peak hour "
            "within one hour of LP1's; overnight SHAPE across 22:00 to 06:00 "
            "within a mean absolute deviation of about 0.19 of LP1's, that "
            "band being half what a profile with no overnight shape would "
            "show"
        ),
        tolerance_basis=(
            "Asymmetric because both the diversity and the resolution "
            "arguments push the measured value DOWN: a town of 1,100 is "
            "spikier than two million meters, and a peak measured over a "
            "shorter interval cannot be lower. Exceeding the national class "
            "is therefore a sign that load has been spread too evenly rather "
            "than a tolerance question. The timing terms use the mean diurnal "
            "shape because LP1's own annual peak is a Christmas-week midday "
            "cooking peak, so an annual-peak window test would have been "
            "wrong about the reference. The overnight term is the whole shape "
            "rather than a 00:00-over-04:00 ratio, and its band is derived "
            "from LP1 rather than declared: a ratio of two hours can be moved "
            "by either of them, which an ablation demonstrated (I-050, U32)."
        ),
        measure=_check_peak_and_load_factor,
    ),
)
