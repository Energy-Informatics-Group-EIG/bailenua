"""U25: domestic hot water, boiler losses and gas cooking.

Every value these modules use is transcribed by hand from a PDF, because U30
established there is no machine-readable Irish source for any of it: the PxStat
sweep found zero hits for `hot water`, `water heating`, `immersion` and
`cooking fuel` across all 13,086 tables. Hand transcription is the weakest link
in the chain, so these tests check the transcription against the document's own
structure as well as checking the physics.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

import baile_nua.sources_registry  # noqa: F401
from baile_nua.physics.boiler import (
    BoilerSpec,
    annual_fuel_terms,
    boiler_efficiency,
    fuel_input_kwh,
    gas_cooking_fuel_kwh,
)
from baile_nua.physics.dhw import (
    SPECIFIC_HEAT_WATER_KWH_PER_L_K,
    DHWSystem,
    TankState,
    cold_feed_temperature_c,
    combi_additional_loss_kwh_yr,
    deap_figures,
    draw_for_activity,
    instantaneous_step,
    primary_circuit_loss_kwh_yr,
    standby_loss_w,
    tank_step,
)
from baile_nua.sources import REGISTRY


# --------------------------------------------------------------------------- #
# provenance: the weakest link gets the tightest test
# --------------------------------------------------------------------------- #

def test_every_deap_figure_names_its_table_or_section():
    """A hand-transcribed number without a citation is a number from memory."""
    f = deap_figures()
    for key, block in f.items():
        if key in ("provenance", "assumptions", "gas_cooking"):
            continue
        assert isinstance(block, dict), key
        assert "table" in block or "section" in block or "deap_scope_note" in block, (
            f"{key} cites neither a table nor a section of the DEAP manual"
        )


def test_the_provenance_block_matches_the_declared_source():
    """The file must point at the source actually on disk."""
    prov = deap_figures()["provenance"]
    src = REGISTRY[prov["source_key"]]
    manifest = json.loads(src.manifest_path.read_text(encoding="utf-8"))
    assert manifest["sha256"].startswith(prov["source_sha256"]), (
        f"data/deap_hot_water.yaml claims it was read from "
        f"{prov['source_sha256']} but the fetched document hashes to "
        f"{manifest['sha256'][:12]}. Re-read the values before trusting them."
    )
    assert prov["machine_readable"] is False


def test_the_assumptions_carry_the_search_that_justifies_them():
    """I-040's rule: an [A] flag records what was searched."""
    for block in (deap_figures()["assumptions"], deap_figures()["gas_cooking"]):
        assert block["evidence_tag"] == "[A]"
        assert "zero hits" in block["searched"]
        assert "PxStat" in block["searched"]


# --------------------------------------------------------------------------- #
# the trap that cost 40% of hot water energy
# --------------------------------------------------------------------------- #

def test_draw_energy_is_referenced_to_the_tank_not_the_tap():
    """48 litres at 40 C from a 60 C tank is 1.672 kWh, not 1.003.

    All of the energy comes out of the tank: 28.8 litres of 60 C water falling
    50 K. Referencing the tank-side volume to the DELIVERED rise instead - 28.8
    litres times 30 K - understates hot water by the mixing fraction, about
    40% at these temperatures. The first version of `tank_step` did exactly
    that, and because the tank-side mixing was right, the two sides disagreed.
    """
    system = DHWSystem(kind="cylinder_indirect", tank_litres=150.0)
    state = TankState(temp_c=60.0)
    draw = draw_for_activity("shower_bath", duration_min=8.0)
    # 7.5 minutes of running water in an 8-minute bathroom episode, at DEAP's
    # 6 L/min minimum.
    assert draw.litres == pytest.approx(45.0)

    out = tank_step(state, system, dt_s=900.0, draws=(draw,), cold_feed_c=10.0)
    independent = (
        draw.litres * SPECIFIC_HEAT_WATER_KWH_PER_L_K * (40.0 - 10.0)
    )
    assert out["useful_draw_kwh"] == pytest.approx(independent, rel=1e-9)
    assert out["useful_draw_kwh"] == pytest.approx(1.568, abs=0.005)


def test_the_draw_side_energy_balance_is_asserted_in_the_step():
    """The guard, exercised: what the water carries equals what the tank loses."""
    system = DHWSystem(kind="cylinder_indirect", tank_litres=120.0)
    state = TankState(temp_c=58.0)
    heat_capacity = 120.0 * SPECIFIC_HEAT_WATER_KWH_PER_L_K
    before = state.temp_c
    draws = tuple(
        draw_for_activity("washing_up", duration_min=20.0) for _ in range(3)
    )
    # Reheat is disabled so the tank's own temperature change isolates the
    # draw: no coil, and no immersion either, since for an indirect cylinder
    # the immersion is a backup the occupant switches on (DEAP 4.6) and not an
    # automatic fallback. Leaving it permitted here is what revealed that the
    # module had the fallback wrong.
    out = tank_step(
        state, system, dt_s=1.0, draws=draws, cold_feed_c=12.0,
        coil_available=False, immersion_permitted=False, ambient_c=58.0,
    )
    lost = (before - state.temp_c) * heat_capacity
    assert out["useful_draw_kwh"] == pytest.approx(lost, rel=1e-6)


def test_an_electric_shower_is_never_charged_to_the_cylinder():
    """DEAP Section 4 is explicit, and double-charging it is the easy error.

    "Number of electric showers (this uses electricity directly rather than
    from the water heating system)". The appliance layer already models the
    electric shower as a load, so the cylinder must see nothing.
    """
    system = DHWSystem(kind="cylinder_indirect", tank_litres=150.0)
    state = TankState(temp_c=60.0)
    draw = draw_for_activity(
        "shower_bath", duration_min=8.0, electric_shower=True
    )
    assert draw.electric_direct is True
    out = tank_step(state, system, dt_s=900.0, draws=(draw,), cold_feed_c=10.0)
    assert out["useful_draw_kwh"] == 0.0
    assert state.n_draw_events == 0
    # The tank still cools, but only by its standing loss over the step - not
    # by a drop that would mean the shower had been served from it twice.
    expected_drop = out["standby_loss_kwh"] / (
        150.0 * SPECIFIC_HEAT_WATER_KWH_PER_L_K
    )
    assert 60.0 - state.temp_c == pytest.approx(expected_drop, rel=1e-6)
    assert expected_drop < 0.1


def test_an_instantaneous_electric_draw_is_electricity_not_fuel():
    system = DHWSystem(kind="instantaneous_electric")
    draw = draw_for_activity("shower_bath", duration_min=6.0)
    out = instantaneous_step(system, draws=(draw,), cold_feed_c=10.0)
    assert out["useful_draw_kwh"] == 0.0
    assert out["electric_direct_kwh"] > 0.0


# --------------------------------------------------------------------------- #
# losses, against the DEAP tables
# --------------------------------------------------------------------------- #

def test_the_standing_loss_is_anchored_on_deaps_own_cylinder():
    """DEAP's 110 L at 1.672 kWh/day, with Table 2's 0.60 factor applied.

    Section 4.5(d) is the one place the manual states a volume and a loss
    together, which is what makes it the figure a modelled tank can be judged
    against.
    """
    f = deap_figures()
    volume = float(f["default_cylinder"]["volume_l"])
    declared = float(f["default_cylinder"]["loss_factor_kwh_per_day"])
    factor = float(
        f["cylinder_temperature_factors"]["values"]["cylinder_indirect"]
    )
    system = DHWSystem(kind="cylinder_indirect", tank_litres=volume)
    watts = standby_loss_w(system, tank_c=system.setpoint_c, ambient_c=20.0)
    kwh_day = watts * 24.0 / 1000.0
    assert kwh_day == pytest.approx(declared * factor, rel=1e-6)


def test_the_standing_loss_falls_as_the_tank_cools():
    """Otherwise a tank left to go cold keeps losing heat it no longer has."""
    system = DHWSystem(kind="cylinder_indirect", tank_litres=150.0)
    hot = standby_loss_w(system, tank_c=60.0, ambient_c=20.0)
    warm = standby_loss_w(system, tank_c=40.0, ambient_c=20.0)
    cold = standby_loss_w(system, tank_c=20.0, ambient_c=20.0)
    assert hot > warm > 0.0
    assert cold == pytest.approx(0.0)
    assert warm == pytest.approx(hot / 2.0, rel=1e-6)


def test_a_bigger_cylinder_loses_more_but_not_proportionally():
    """Loss is through a surface; volume grows faster than surface area."""
    small = DHWSystem(kind="cylinder_indirect", tank_litres=110.0)
    big = DHWSystem(kind="cylinder_indirect", tank_litres=220.0)
    a = standby_loss_w(small, tank_c=60.0, ambient_c=20.0)
    b = standby_loss_w(big, tank_c=60.0, ambient_c=20.0)
    assert a < b < 2.0 * a


def test_primary_circuit_losses_come_from_table_3():
    """Every branch must land on a published row, including the zeroes."""
    values = deap_figures()["primary_circuit_losses_kwh_yr"]["values"]
    insulated = DHWSystem(
        kind="cylinder_indirect", tank_litres=150.0,
        primary_pipework_insulated=True, has_cylinder_thermostat=True,
    )
    assert primary_circuit_loss_kwh_yr(insulated) == values[
        "boiler_insulated_with_cylinder_thermostat"
    ] == 360
    bare = DHWSystem(
        kind="cylinder_indirect", tank_litres=150.0,
        primary_pipework_insulated=False, has_cylinder_thermostat=False,
    )
    assert primary_circuit_loss_kwh_yr(bare) == 1220
    assert primary_circuit_loss_kwh_yr(DHWSystem(kind="combi")) == 0
    immersion = DHWSystem(kind="cylinder_immersion", tank_litres=120.0)
    assert primary_circuit_loss_kwh_yr(immersion) == 0


def test_a_cylinder_thermostat_halves_the_primary_loss():
    """The shape of Table 3, which is the reason to model the thermostat."""
    with_stat = DHWSystem(
        kind="cylinder_indirect", tank_litres=150.0,
        primary_pipework_insulated=False, has_cylinder_thermostat=True,
    )
    without = DHWSystem(
        kind="cylinder_indirect", tank_litres=150.0,
        primary_pipework_insulated=False, has_cylinder_thermostat=False,
    )
    assert primary_circuit_loss_kwh_yr(with_stat) * 2 == pytest.approx(
        primary_circuit_loss_kwh_yr(without)
    )


def test_the_combi_loss_scales_below_a_hundred_litres_a_day():
    """Table 3a's note, which matters for every small household.

    Applying the flat 600 kWh to a one-person home drawing 60 litres a day
    would put 240 kWh/year of pure loss into it that DEAP does not claim.
    """
    combi = DHWSystem(kind="combi")
    full = combi_additional_loss_kwh_yr(combi, daily_litres=150.0)
    small = combi_additional_loss_kwh_yr(combi, daily_litres=60.0)
    assert full == 600.0
    assert small == pytest.approx(600.0 * 0.6)
    assert combi_additional_loss_kwh_yr(
        combi, daily_litres=150.0, keep_hot="always"
    ) == 900.0
    # And nothing for a system that has no combi.
    tank = DHWSystem(kind="cylinder_indirect", tank_litres=150.0)
    assert combi_additional_loss_kwh_yr(tank, daily_litres=150.0) == 0.0


# --------------------------------------------------------------------------- #
# the thermostat, the immersion and the diverter
# --------------------------------------------------------------------------- #

def test_the_thermostat_reheats_only_below_the_deadband():
    system = DHWSystem(
        kind="cylinder_indirect", tank_litres=150.0,
        setpoint_c=60.0, deadband_c=5.0,
    )
    just_inside = TankState(temp_c=56.0)
    out = tank_step(just_inside, system, dt_s=60.0, ambient_c=60.0)
    assert out["coil_input_kwh"] == 0.0
    below = TankState(temp_c=50.0)
    out = tank_step(below, system, dt_s=60.0, ambient_c=50.0)
    assert out["coil_input_kwh"] > 0.0


def test_an_immersion_only_cylinder_reheats_electrically():
    system = DHWSystem(kind="cylinder_immersion", tank_litres=120.0)
    state = TankState(temp_c=45.0)
    out = tank_step(state, system, dt_s=600.0, ambient_c=45.0)
    assert out["immersion_input_kwh"] > 0.0
    assert out["coil_input_kwh"] == 0.0
    assert out["immersion_w"] <= system.immersion_rated_w + 1e-6


def test_the_diverter_runs_before_any_fuel_is_burned():
    """Surplus PV is otherwise exported for less than it is worth."""
    system = DHWSystem(
        kind="cylinder_indirect", tank_litres=150.0, has_pv_diverter=True,
    )
    state = TankState(temp_c=50.0)
    out = tank_step(
        state, system, dt_s=1800.0, pv_surplus_w=3000.0, ambient_c=50.0,
    )
    assert out["diverted_pv_kwh"] > 0.0
    assert out["coil_input_kwh"] == 0.0, (
        "the coil fired while PV surplus was available to the immersion"
    )


def test_the_diverter_may_exceed_the_thermostat_but_not_its_own_cap():
    system = DHWSystem(
        kind="cylinder_indirect", tank_litres=100.0, has_pv_diverter=True,
        setpoint_c=60.0, diverter_setpoint_c=70.0,
    )
    state = TankState(temp_c=68.0)
    for _ in range(20):
        tank_step(state, system, dt_s=1800.0, pv_surplus_w=3000.0,
                  ambient_c=68.0)
    assert state.temp_c <= system.diverter_setpoint_c + 1e-6
    assert state.temp_c > system.setpoint_c


def test_a_diverter_without_an_immersion_is_refused():
    with pytest.raises(ValueError, match="cannot have one without the other"):
        DHWSystem(
            kind="cylinder_indirect", tank_litres=150.0,
            has_immersion=False, has_pv_diverter=True,
        )


def test_a_tank_volume_on_an_instantaneous_system_is_refused():
    with pytest.raises(ValueError, match="is instantaneous"):
        DHWSystem(kind="combi", tank_litres=150.0)
    with pytest.raises(ValueError, match="needs a tank volume"):
        DHWSystem(kind="cylinder_indirect")
    with pytest.raises(ValueError, match="has no tank"):
        tank_step(TankState(temp_c=60.0), DHWSystem(kind="combi"), dt_s=60.0)


# --------------------------------------------------------------------------- #
# the cold feed
# --------------------------------------------------------------------------- #

def test_the_cold_feed_is_coldest_in_late_winter_not_at_the_solstice():
    """Mains water lags air temperature, and the lag is the point.

    A fixed feed temperature would understate winter hot water energy and
    overstate summer - exactly the axis U22 looks along.
    """
    temps = {d: cold_feed_temperature_c(d) for d in range(1, 366)}
    coldest = min(temps, key=temps.get)
    warmest = max(temps, key=temps.get)
    assert 40 <= coldest <= 80, f"coldest day is {coldest}, not late winter"
    assert 220 <= warmest <= 260, f"warmest day is {warmest}, not late summer"
    mean = float(deap_figures()["assumptions"]["cold_feed_temperature_c"])
    assert sum(temps.values()) / len(temps) == pytest.approx(mean, abs=0.1)


def test_a_winter_draw_costs_more_than_the_same_draw_in_summer():
    system = DHWSystem(kind="cylinder_indirect", tank_litres=150.0)
    draw = draw_for_activity("shower_bath", duration_min=8.0)
    energies = []
    for day in (15, 196):
        state = TankState(temp_c=60.0)
        out = tank_step(
            state, system, dt_s=900.0, draws=(draw,),
            cold_feed_c=cold_feed_temperature_c(day),
        )
        energies.append(out["useful_draw_kwh"])
    assert energies[0] > energies[1]


# --------------------------------------------------------------------------- #
# boiler efficiency: U22's confound
# --------------------------------------------------------------------------- #

def test_the_era_efficiency_spread_is_the_one_table_4b_publishes():
    """55% to 83%: the plant difference U22 has to separate from behaviour."""
    oldest = BoilerSpec(
        fuel="natural gas", build_year=1960, floor_mounted=True,
        fan_assisted_flue=False,
    )
    newest = BoilerSpec(fuel="natural gas", build_year=2015, condensing=True)
    a = boiler_efficiency(oldest)
    b = boiler_efficiency(newest)
    assert a["gross_seasonal_efficiency"] == pytest.approx(0.55)
    assert b["gross_seasonal_efficiency"] == pytest.approx(0.83)
    assert a["row"] == "floor_mounted_pre_1979"
    # The same delivered heat costs half again as much fuel in the old home,
    # before any behaviour is considered.
    ratio = fuel_input_kwh(10_000, oldest) / fuel_input_kwh(10_000, newest)
    assert ratio == pytest.approx(0.83 / 0.55, rel=1e-6)
    assert 1.4 < ratio < 1.6


def test_efficiency_rises_monotonically_with_era_for_oil():
    years = (1970, 1990, 2010)
    effs = [
        boiler_efficiency(BoilerSpec(fuel="oil", build_year=y))["efficiency"]
        for y in years
    ]
    assert effs == sorted(effs)
    assert effs[0] == pytest.approx(0.65)


def test_every_efficiency_traces_to_a_published_row():
    table = deap_figures()["boiler_gross_seasonal_efficiency_pct"]
    for fuel in ("natural gas", "oil"):
        for year in (1950, 1975, 1985, 1997, 2000, 2020):
            for condensing in (False, True):
                spec = BoilerSpec(
                    fuel=fuel, build_year=year, condensing=condensing,
                )
                got = boiler_efficiency(spec)
                assert got["group"] in table, got
                assert got["row"] in table[got["group"]], got
                assert 0.4 < got["efficiency"] <= 0.9


def test_the_interlock_penalty_is_deaps_five_percent():
    base = BoilerSpec(fuel="natural gas", build_year=2015, condensing=True)
    docked = BoilerSpec(
        fuel="natural gas", build_year=2015, condensing=True, interlocked=False,
    )
    a = boiler_efficiency(base)["efficiency"]
    b = boiler_efficiency(docked)["efficiency"]
    assert b == pytest.approx(a * 0.95)


def test_a_heat_pump_is_not_a_table_4b_boiler():
    """Table 4b covers gas (including LPG) and oil. Refusing beats guessing."""
    with pytest.raises(ValueError, match="Table 4b covers gas"):
        boiler_efficiency(BoilerSpec(fuel="heat pump", build_year=2020))
    with pytest.raises(ValueError, match="district heating is Section 4.5"):
        boiler_efficiency(BoilerSpec(fuel="district", build_year=2010))


def test_lpg_takes_the_gas_rows():
    """Table 4b's heading is "Gas boilers (including LPG)".

    Testing only for "gas" in the fuel string excluded every LPG dwelling,
    which the town's own fuel census caught: 4 of 1,092 had no hot water
    system at all.
    """
    lpg = boiler_efficiency(BoilerSpec(fuel="LPG", build_year=2005))
    gas = boiler_efficiency(BoilerSpec(fuel="natural gas", build_year=2005))
    assert lpg["efficiency"] == gas["efficiency"]
    assert lpg["group"] == "gas_1998_or_later"


def test_the_coil_heat_duty_is_not_added_to_the_standing_loss():
    """The double-count this parameter exists to prevent.

    A simulated tank measures the heat the coil put in, and that figure
    already includes making up the standing loss - the thermostat was
    responding to it. Adding the useful draw and the standing loss on top
    would count both twice.
    """
    spec = BoilerSpec(fuel="natural gas", build_year=2015, condensing=True)
    measured = annual_fuel_terms(
        spec=spec, space_heat_kwh=5000.0, dhw_boiler_heat_kwh=2200.0,
    )
    summed = annual_fuel_terms(
        spec=spec, space_heat_kwh=5000.0, dhw_useful_kwh=1800.0,
        dhw_standby_kwh=400.0,
    )
    # Same duty, reached two ways, so the same fuel.
    assert measured["meter_fuel_kwh"] == pytest.approx(
        summed["meter_fuel_kwh"], rel=1e-9
    )
    assert measured["terms"]["dhw_boiler_heat_kwh"] == 2200.0
    assert "already inside it" in measured["terms"]["dhw_duty_from"]
    # And passing all three must not inflate the duty.
    both = annual_fuel_terms(
        spec=spec, space_heat_kwh=5000.0, dhw_boiler_heat_kwh=2200.0,
        dhw_useful_kwh=1800.0, dhw_standby_kwh=400.0,
    )
    assert both["meter_fuel_kwh"] == pytest.approx(
        measured["meter_fuel_kwh"], rel=1e-9
    )


# --------------------------------------------------------------------------- #
# gas cooking, and the itemised meter total
# --------------------------------------------------------------------------- #

def test_gas_cooking_is_a_ratio_on_an_already_sized_load():
    """The declared assumption is one ratio, not a new annual energy."""
    out = gas_cooking_fuel_kwh(hob_useful_kwh=200.0, oven_useful_kwh=150.0)
    assert out["hob_ratio_gas_over_electric"] > 1.5
    assert out["oven_ratio_gas_over_electric"] > 1.0
    assert out["hob_gas_kwh"] > 200.0
    assert out["evidence_tag"] == "[A]"
    assert out["total_gas_kwh"] == pytest.approx(
        out["hob_gas_kwh"] + out["oven_gas_kwh"]
    )


def test_the_meter_total_is_itemised_and_adds_up():
    """A single total that happened to match would say nothing about why."""
    spec = BoilerSpec(fuel="natural gas", build_year=1985, floor_mounted=True,
                      fan_assisted_flue=False)
    out = annual_fuel_terms(
        spec=spec, space_heat_kwh=8000.0, dhw_useful_kwh=1800.0,
        dhw_standby_kwh=366.0, primary_circuit_kwh=360.0,
        hob_useful_kwh=200.0, oven_useful_kwh=150.0, gas_cooking=True,
    )
    t = out["terms"]
    heat = (t["space_heat_useful_kwh"] + t["dhw_useful_kwh"]
            + t["dhw_standby_kwh"] + t["primary_circuit_kwh"])
    expected = (
        heat / out["efficiency"]
        + t["combi_additional_kwh_at_meter"]
        + t["gas_cooking_kwh_at_meter"]
    )
    assert out["meter_fuel_kwh"] == pytest.approx(expected, rel=1e-9)
    assert out["combustion_loss_kwh"] == pytest.approx(
        heat / out["efficiency"] - heat, rel=1e-9
    )


def test_table_3a_losses_are_already_at_the_meter():
    """They are stated in kWh/year of fuel, so dividing again would double-count."""
    spec = BoilerSpec(fuel="natural gas", build_year=2015, condensing=True,
                      combi=True)
    out = annual_fuel_terms(
        spec=spec, space_heat_kwh=0.0, dhw_useful_kwh=0.0,
        dhw_standby_kwh=0.0, combi_additional_kwh=600.0,
    )
    assert out["meter_fuel_kwh"] == pytest.approx(600.0)


def test_u25_closes_most_of_the_gas_gap_it_was_built_for():
    """The point of U25, as an arithmetic check rather than a promise.

    E1 measured a simulated-to-published gas ratio of 0.308 with space heat
    alone. Adding hot water, its losses and combustion efficiency has to move
    that ratio a long way up - not to 1.0, since this is one dwelling's
    arithmetic and not the town's, but the direction and rough size are the
    claim U25 is making and are worth pinning.
    """
    spec = BoilerSpec(fuel="natural gas", build_year=1985, floor_mounted=True,
                      fan_assisted_flue=False)
    space_only = 8000.0
    withall = annual_fuel_terms(
        spec=spec, space_heat_kwh=space_only, dhw_useful_kwh=1800.0,
        dhw_standby_kwh=366.0, primary_circuit_kwh=360.0,
        hob_useful_kwh=200.0, oven_useful_kwh=150.0, gas_cooking=True,
    )["meter_fuel_kwh"]
    uplift = withall / space_only
    assert uplift > 1.5, (
        f"U25 only lifted the meter figure to {uplift:.2f}x space heat; the "
        f"E1 ratio of 0.308 needs roughly a 3x uplift to reach 1.0 and this "
        f"is meant to supply most of it"
    )


def test_an_indirect_cylinders_immersion_is_a_backup_not_a_fallback():
    """DEAP 4.6, and the bug that found it.

    An earlier `tank_step` reheated from the immersion whenever the coil was
    unavailable. That is not DEAP's rule - supplementary electric heating is
    disregarded when it is only backup, and assumed in SUMMER when running the
    boiler would also heat the house - and it would have put electric
    immersion load into midwinter in every home whose boiler was briefly off.
    """
    system = DHWSystem(kind="cylinder_indirect", tank_litres=150.0)

    state = TankState(temp_c=45.0)
    out = tank_step(
        state, system, dt_s=600.0, ambient_c=45.0, coil_available=False,
    )
    assert out["immersion_input_kwh"] == 0.0, (
        "the immersion ran as an automatic fallback for a boiler-fed cylinder"
    )
    assert out["coil_input_kwh"] == 0.0

    summer = TankState(temp_c=45.0)
    out = tank_step(
        summer, system, dt_s=600.0, ambient_c=45.0, coil_available=False,
        immersion_permitted=True,
    )
    assert out["immersion_input_kwh"] > 0.0

    # An immersion-fed cylinder has no coil to wait for and always heats.
    direct = DHWSystem(kind="cylinder_immersion", tank_litres=120.0)
    always = TankState(temp_c=45.0)
    out = tank_step(always, direct, dt_s=600.0, ambient_c=45.0)
    assert out["immersion_input_kwh"] > 0.0


def test_the_shower_water_runs_for_less_than_the_bathroom_episode():
    """The 800-litres-a-day bug, as a test.

    `shower_bath` is time in the bathroom - undressing, showering, drying,
    grooming - and the activity engine draws episodes up to 25 minutes.
    Charging DEAP's 6 L/min across the whole episode made a 150-litre shower
    and put household hot water at about 800 litres a day, 70 to 85% of it
    showers. The running time is now separate, and capped by the episode so a
    short visit cannot contain a long shower.
    """
    from baile_nua.physics.dhw import shower_water_minutes

    a = deap_figures()["assumptions"]
    median = float(a["shower_water_minutes_median"])
    cap = float(a["shower_water_minutes_max"])

    # A long episode gets the declared running time, not the episode length.
    assert shower_water_minutes(25.0) == pytest.approx(median)
    long_draw = draw_for_activity("shower_bath", duration_min=25.0)
    assert long_draw.litres == pytest.approx(6.0 * median)
    assert long_draw.litres < 60.0, (
        f"a 25-minute bathroom episode drew {long_draw.litres:.0f} litres; "
        f"the episode is not the shower"
    )

    # A short episode caps it: five minutes in the bathroom is at most a
    # five-minute shower.
    assert shower_water_minutes(4.0) == pytest.approx(4.0)
    short = draw_for_activity("shower_bath", duration_min=4.0)
    assert short.litres == pytest.approx(24.0)

    # And the draw never exceeds the declared maximum, however long the
    # episode or however the lognormal falls.
    gen = np.random.default_rng(7)
    for _ in range(200):
        assert shower_water_minutes(60.0, gen) <= cap + 1e-9


def test_household_hot_water_stays_under_deaps_all_water_ceiling():
    """PL-DHW-01's quantity, at the draw-schedule level.

    DEAP publishes no hot water volume, but it does publish a water
    efficiency target of 125 litres per person per day for ALL water, hot and
    cold - and hot water is a subset, so the target bounds it. This is the
    cheap guard; the gas meter is the arbiter.
    """
    from baile_nua.physics.dhw import draw_schedule

    ceiling = float(
        deap_figures()["demand"]["water_efficiency_target_l_per_person_day"]
    )

    class _Iv:
        def __init__(self, activity, start, end):
            self.activity = activity
            self.start_min = start
            self.end_min = end
            self.location_kind = "building"

        @property
        def duration_min(self):
            return self.end_min - self.start_min

    # A heavy but realistic day for three people: a shower each, washing up
    # twice, three cooking episodes and a round of personal care each.
    intervals = [
        _Iv("shower_bath", 420, 445), _Iv("shower_bath", 450, 470),
        _Iv("shower_bath", 1300, 1320),
        _Iv("washing_up", 540, 555), _Iv("washing_up", 1140, 1160),
        _Iv("cooking", 480, 510), _Iv("cooking", 720, 750),
        _Iv("cooking", 1080, 1140),
        _Iv("personal_care", 400, 415), _Iv("personal_care", 405, 420),
        _Iv("personal_care", 1330, 1345),
    ]
    litres = float(draw_schedule(intervals).sum())
    per_person = litres / 3.0
    assert per_person < ceiling, (
        f"{per_person:.0f} L/person/day of HOT water against DEAP's "
        f"{ceiling:.0f} L/person/day for all water, hot and cold"
    )
    assert per_person > 15.0, (
        f"{per_person:.0f} L/person/day means the draw model has effectively "
        f"stopped drawing hot water"
    )
