"""U25: boiler losses and gas cooking - the other two terms the gas meter sees.

The E1 gas comparison measured a simulated-to-published ratio of **0.308** and
its docstring named why: DBERNG01 is a meter reading, so it contains space
heating, hot water, cooking where the hob is gas, and the boiler's own losses,
while E1 modelled space heating alone. :mod:`baile_nua.physics.dhw` adds hot
water. This module adds the other two.

Boiler efficiency is where U22's confound lives
-----------------------------------------------
DEAP Table 4b gives gross seasonal efficiency by boiler type and era, and the
spread is wide: **55%** for a floor-mounted gas boiler from before 1979 against
**83%** for a modern condensing one. So an old dwelling burns half again as
much gas for the same delivered heat *before any behaviour is considered*.

That matters for U22 specifically. The E1 space-heat ratio gradient - 0.43 for
1967-99 against 0.19 for post-2005 - was measured with **no** boiler
efficiency at all, which means every bit of the era difference in that ratio
was being attributed to the model's physics and behaviour. Some of it is
plainly the boiler. U22 cannot separate comfort-taking from plant efficiency
until the plant efficiency is in, which is why U25 comes first.

Gas cooking has no reference, and the chain says so
---------------------------------------------------
DEAP excludes cooking from its boundary and U30 found zero PxStat hits for
`cooking fuel`. Rather than invent an annual gas-cooking figure, this module
takes the useful cooking energy the appliance layer already produces and
re-delivers it at a gas burner's pan-side efficiency. The declared assumption
is then a single ratio - roughly two to one on the hob - rather than a new
energy from nothing, and the direction of it is not in doubt.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from baile_nua.physics.dhw import deap_figures

__all__ = [
    "BoilerSpec",
    "boiler_efficiency",
    "fuel_input_kwh",
    "gas_cooking_fuel_kwh",
    "annual_fuel_terms",
]


@dataclasses.dataclass(frozen=True)
class BoilerSpec:
    """A dwelling's heat generator, as DEAP Table 4b classifies it."""

    fuel: str                     # "natural gas" | "oil" | other
    build_year: int
    condensing: bool = False
    combi: bool = False
    #: Floor-mounted, balanced or open flue: the oldest gas arrangement, and
    #: the only one DEAP gives a 55% default for.
    floor_mounted: bool = False
    fan_assisted_flue: bool = True
    permanent_pilot: bool = False
    #: DEAP docks 5% when space and water heating are not interlocked.
    interlocked: bool = True

    def __post_init__(self) -> None:
        if self.build_year < 1800 or self.build_year > 2100:
            raise ValueError(f"implausible build year {self.build_year}")


def boiler_efficiency(spec: BoilerSpec) -> dict[str, Any]:
    """Gross seasonal efficiency as a fraction, with the Table 4b row used.

    Returns the row name as well as the number so that a dwelling's efficiency
    can be traced to a line of the published table rather than to this
    function's branching.
    """
    table = deap_figures()["boiler_gross_seasonal_efficiency_pct"]
    fuel = str(spec.fuel).lower()

    # Table 4b's heading is "Gas boilers (including LPG)", so LPG takes the
    # gas rows. Testing only for "gas" silently excluded it.
    if "gas" in fuel or "lpg" in fuel:
        if spec.build_year >= 1998:
            block, group = table["gas_1998_or_later"], "gas_1998_or_later"
            if spec.condensing:
                row = ("condensing_permanent_pilot" if spec.permanent_pilot
                       else "condensing_automatic_ignition")
            else:
                row = ("non_condensing_permanent_pilot" if spec.permanent_pilot
                       else "non_condensing_automatic_ignition")
        elif spec.fan_assisted_flue:
            block = table["gas_pre_1998_fan_assisted_flue"]
            group = "gas_pre_1998_fan_assisted_flue"
            if spec.condensing:
                row = "condensing_combi" if spec.combi else "condensing"
            elif spec.combi:
                row = "combi"
            else:
                row = "high_or_unknown_thermal_capacity"
        else:
            block = table["gas_pre_1998_balanced_or_open_flue"]
            group = "gas_pre_1998_balanced_or_open_flue"
            if spec.combi:
                row = "combi"
            elif spec.floor_mounted:
                row = ("floor_mounted_pre_1979" if spec.build_year < 1979
                       else "floor_mounted_1979_to_1997")
            else:
                row = "wall_mounted"
    elif "oil" in fuel:
        block, group = table["oil"], "oil"
        if spec.condensing:
            row = "condensing_combi" if spec.combi else "condensing"
        elif spec.combi:
            row = ("combi_1998_or_later" if spec.build_year >= 1998
                   else "combi_pre_1998")
        elif spec.build_year >= 1998:
            row = "standard_1998_or_later"
        elif spec.build_year >= 1985:
            row = "standard_1985_to_1997"
        else:
            row = "standard_pre_1985"
    else:
        raise ValueError(
            f"Table 4b covers gas (including LPG) and oil boilers; "
            f"{spec.fuel!r} is neither. Solid fuel is Table 4a, heat pumps are "
            f"HARP/Appendix N, and district heating is Section 4.5 with a "
            f"distribution loss factor rather than a boiler efficiency."
        )

    gross = float(block[row]) / 100.0
    penalty = 0.0
    if not spec.interlocked:
        penalty = float(deap_figures()["boiler_interlock"][
            "efficiency_penalty_if_not_interlocked"
        ])
    return {
        "efficiency": gross * (1.0 - penalty),
        "gross_seasonal_efficiency": gross,
        "interlock_penalty": penalty,
        "table": "Table 4b",
        "group": group,
        "row": row,
        "serves_water_heating_too": True,
    }


def fuel_input_kwh(useful_kwh: float, spec: BoilerSpec) -> float:
    """Fuel at the meter for a given useful heat delivered.

    DEAP's note on Table 4b is applied as written: *"The same seasonal
    efficiencies should be assumed for water heating when hot water is
    supplied from a boiler system."* One efficiency, both duties.
    """
    if useful_kwh < 0:
        raise ValueError("useful heat cannot be negative")
    eff = boiler_efficiency(spec)["efficiency"]
    if eff <= 0:
        raise ValueError(f"non-positive efficiency for {spec}")
    return float(useful_kwh) / eff


def gas_cooking_fuel_kwh(
    *, hob_useful_kwh: float = 0.0, oven_useful_kwh: float = 0.0
) -> dict[str, Any]:
    """Gas at the meter for cooking the appliance layer already sized.

    The appliance signatures give ELECTRIC cooking energy. The useful energy
    into the food is that times the electric pan-side efficiency; delivering
    the same useful energy with gas needs it divided by the gas efficiency. So
    the gas figure is the electric one times a ratio, and the ratio is the
    only declared assumption.
    """
    c = deap_figures()["gas_cooking"]
    hob_ratio = float(c["hob_pan_side_efficiency_electric"]) / float(
        c["hob_pan_side_efficiency_gas"]
    )
    oven_ratio = float(c["oven_efficiency_electric"]) / float(
        c["oven_efficiency_gas"]
    )
    hob_gas = float(hob_useful_kwh) * hob_ratio
    oven_gas = float(oven_useful_kwh) * oven_ratio
    return {
        "hob_gas_kwh": hob_gas,
        "oven_gas_kwh": oven_gas,
        "total_gas_kwh": hob_gas + oven_gas,
        "hob_ratio_gas_over_electric": hob_ratio,
        "oven_ratio_gas_over_electric": oven_ratio,
        "evidence_tag": c["evidence_tag"],
        "searched": c["searched"],
    }


def annual_fuel_terms(
    *,
    spec: BoilerSpec,
    space_heat_kwh: float,
    dhw_useful_kwh: float = 0.0,
    dhw_standby_kwh: float = 0.0,
    dhw_boiler_heat_kwh: float | None = None,
    hob_useful_kwh: float = 0.0,
    oven_useful_kwh: float = 0.0,
    primary_circuit_kwh: float = 0.0,
    combi_additional_kwh: float = 0.0,
    gas_cooking: bool = False,
) -> dict[str, Any]:
    """Everything the meter sees, itemised so the comparison can be read.

    Itemised deliberately. A single total that happened to match DBERNG01
    would say nothing about whether it matched for the right reasons, and the
    E1 ratio of 0.308 was informative precisely because the missing terms were
    named rather than absorbed into a fudge factor.
    """
    eff = boiler_efficiency(spec)
    efficiency = eff["efficiency"]

    # `dhw_boiler_heat_kwh` is the heat the boiler coil actually put INTO the
    # cylinder, which a simulated tank measures directly. It already includes
    # making up the standing loss, because that is what the thermostat was
    # responding to - so when it is given, the useful draw and the standby
    # loss must NOT be added on top. Adding all three would count the standing
    # loss twice and the draws twice over.
    #
    # When it is not given, the two terms are summed instead, which is the
    # right arithmetic for a dwelling whose tank was not simulated.
    if dhw_boiler_heat_kwh is not None:
        dhw_duty = float(dhw_boiler_heat_kwh)
    else:
        dhw_duty = float(dhw_useful_kwh) + float(dhw_standby_kwh)

    # Primary losses are heat that left the system, so the fuel to cover them
    # passes through the same efficiency as everything else.
    heat_duties = (
        float(space_heat_kwh) + dhw_duty + float(primary_circuit_kwh)
    )
    fuel = heat_duties / efficiency
    # Table 3a's combi losses are already stated at the meter, in kWh/year of
    # fuel, so they are NOT divided again by the efficiency.
    fuel += float(combi_additional_kwh)

    cooking = {"total_gas_kwh": 0.0}
    if gas_cooking:
        cooking = gas_cooking_fuel_kwh(
            hob_useful_kwh=hob_useful_kwh, oven_useful_kwh=oven_useful_kwh
        )
        fuel += cooking["total_gas_kwh"]

    return {
        "meter_fuel_kwh": fuel,
        "efficiency": efficiency,
        "efficiency_row": f"{eff['group']}.{eff['row']}",
        "interlock_penalty": eff["interlock_penalty"],
        "terms": {
            "space_heat_useful_kwh": float(space_heat_kwh),
            "dhw_boiler_heat_kwh": dhw_duty,
            "dhw_duty_from": (
                "measured coil input (standing loss already inside it)"
                if dhw_boiler_heat_kwh is not None
                else "useful draw plus standing loss"
            ),
            "dhw_useful_kwh": float(dhw_useful_kwh),
            "dhw_standby_kwh": float(dhw_standby_kwh),
            "primary_circuit_kwh": float(primary_circuit_kwh),
            "combi_additional_kwh_at_meter": float(combi_additional_kwh),
            "gas_cooking_kwh_at_meter": float(cooking["total_gas_kwh"]),
        },
        "combustion_loss_kwh": heat_duties / efficiency - heat_duties,
    }


# --------------------------------------------------------------------------- #
# Boiler vintage is not dwelling vintage (I-047).
#
# DEAP Table 4b is indexed by the BOILER's age - its rows are "Gas boilers
# 1998 or later", "pre-1998 with fan-assisted flue", "floor mounted,
# pre-1979". The first version of the gas accounting read the DWELLING's build
# year into those rows, which gave a house built in 1975 a 55%-efficient
# floor-mounted boiler in 2022.
#
# A house built in 1975 is on its second or third boiler. Gas boilers last
# roughly 15 to 25 years, so by T0 almost every pre-2000 dwelling has a
# post-2000 appliance, and the conflation inflated fuel for the whole old
# stock by up to 83/55 = 1.51x. It showed up as a simulated-to-published gas
# ratio of 2.11 on the mixed-age slice, against 0.83 on the modern E1 estate -
# the error only bites where the dwelling is old, which is exactly where U22
# is measured.
# --------------------------------------------------------------------------- #

#: Mean service life of a domestic gas or oil boiler, years. Declared [A]:
#: U30's sweep found nothing in PxStat on appliance age, and DEAP takes the
#: boiler from the assessment rather than modelling its replacement. The
#: DIRECTION is not in doubt - boilers are replaced and dwellings are not -
#: and the consequence of getting the exact figure wrong is bounded, because
#: any lifetime under about 45 years puts a pre-1980 dwelling on a post-1998
#: boiler, which is the row that matters.
BOILER_MEAN_LIFE_YEARS = 19.0

#: Ireland's Part L required condensing boilers for replacements from 2008, so
#: a boiler installed from then is condensing. Dated rather than assumed: this
#: is a regulatory boundary, not a market share.
CONDENSING_MANDATORY_FROM = 2008


def boiler_vintage(
    *, build_year: int, t0_year: int = 2022, gen: Any = None,
    mean_life_years: float = BOILER_MEAN_LIFE_YEARS,
) -> dict[str, Any]:
    """When this dwelling's current boiler was installed.

    The original boiler is replaced on roughly ``mean_life_years``, so the
    installed appliance dates from the last replacement before T0 - or from
    the build, for a dwelling newer than one service life.

    Drawn rather than fixed, because a cohort of identical dwellings does not
    replace its boilers in the same year, and a deterministic vintage would
    put a whole construction band on one Table 4b row and so manufacture the
    very band-to-band step that the BER flatness is about.
    """
    age_at_t0 = max(t0_year - int(build_year), 0)
    if gen is not None:
        # Uniform over the last service life: a boiler in service at T0 is
        # equally likely to be at any point in its life, which is the
        # renewal-process result for a flat replacement hazard and needs no
        # further assumption.
        years_since_install = float(gen.uniform(0.0, mean_life_years))
    else:
        years_since_install = mean_life_years / 2.0
    vintage = int(round(t0_year - years_since_install))
    if age_at_t0 < years_since_install:
        # Newer than one service life: still on its original boiler.
        vintage = int(build_year)
    return {
        "vintage": vintage,
        "dwelling_build_year": int(build_year),
        "still_original": vintage == int(build_year),
        "condensing": vintage >= CONDENSING_MANDATORY_FROM,
        "why": (
            "DEAP Table 4b is indexed by the boiler's age, not the dwelling's. "
            "A dwelling older than one service life is on a replacement "
            "appliance (I-047)."
        ),
    }


def boiler_spec_for(
    building: Any, *, t0_year: int = 2022, gen: Any = None
) -> BoilerSpec:
    """A BoilerSpec whose vintage is the boiler's, not the dwelling's."""
    build_year = int(getattr(building, "build_year", 1980) or 1980)
    v = boiler_vintage(build_year=build_year, t0_year=t0_year, gen=gen)
    vintage = int(v["vintage"])
    return BoilerSpec(
        fuel=str(getattr(building, "heating_fuel", "") or ""),
        build_year=vintage,
        condensing=bool(v["condensing"]),
        # A pre-1979 FLOOR-MOUNTED boiler is only reachable by a dwelling
        # still on its original appliance, which after a replacement draw is
        # rare rather than automatic.
        floor_mounted=vintage < 1979,
        fan_assisted_flue=vintage >= 1991,
    )
