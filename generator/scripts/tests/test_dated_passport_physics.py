"""A passport event must change the physics, and the test fails if it does not.

This is the instrument I-062 was missing. ``apply_year_to_slice`` counted every
WP5 measure it applied into ``wp5_measures_applied``, the ten-year artefact
published that count, and nothing anywhere asked whether setting a slice field
*did* anything. Two of the four asset measures set a field the engine never
reads, so seventeen of the decade's forty-seven passport events were reported
as applied while leaving the series bit-for-bit unchanged.

So the test is written the way the fault would have been caught: run the same
day twice, once with the event and once without, and **fail when the two are
identical**. Not "assert the handler was called" - that would have passed
throughout - and not "assert the slice field is set", which is the assertion
that was effectively being made and was worthless.

Three things each event type is held to:

1. **the event's own dwelling moves.** At least one energy field differs.
2. **no other dwelling moves.** A dated event reaches into one household; if
   the estate shifts, the event has perturbed shared state or an RNG stream,
   which would make every ablation and every held-out comparison meaningless.
3. **the direction is the one the mechanism claims.** A retrofit must not raise
   heat loss; a heat-pump conversion must move space heat off the gas meter.
   A test that only checked "something changed" would pass on a sign error.

``der_smart_controls`` on a boiler home is the deliberate exception, and it is
asserted to change *nothing* - because DEAP publishes no effect for it and the
honest record of that is a no-op with a reason attached, not an invented
saving. The test pins both halves: no change on a boiler home, and a change on
a heat-pump home, where DEAP Table 4c(4) does publish one.
"""

from __future__ import annotations

import copy

import numpy as np
import pytest

import baile_nua.sources_registry  # noqa: F401  (declares the sources)
from baile_nua.activity.engine import PersonProfile
from baile_nua.engine.calendar import build_calendar
from baile_nua.engine.e1_run import build_slice
from baile_nua.engine.run import EstateRunner
from baile_nua.physics import passport_assets as assets_mod
from baile_nua.physics import retrofit as retrofit_mod
from baile_nua.population.synthesise import synthesise_t0
from baile_nua.rng import Stream
from baile_nua.weather.site import build_realisation

SEED = 20251010

#: Two January days. A heating measure cannot show up on a summer day, and a
#: test that ran one would report a true mechanism as inert.
N_DAYS = 2


@pytest.fixture(scope="module")
def estate():
    """The slice, the weather and a January calendar, built once."""
    town = synthesise_t0(master_seed=SEED)
    wx = build_realisation(2022, master_seed=SEED, days=N_DAYS + 2)
    calendar = build_calendar(2022, weather_hourly=wx.site_hourly)[:N_DAYS]
    sl = build_slice(town, master_seed=SEED, calendar=calendar,
                     slice_kind="u23_mixed_age")
    return sl, wx, calendar


def _run(estate, *, mutate=None, mutate_on_day=0):
    """Run the estate, optionally applying one dated event at a day boundary.

    ``mutate(runner, hh, building)`` is called before the day's Phase A, which
    is where the engine applies a real passport event, so the arm being
    measured is the one the engine actually runs rather than a hand-built
    approximation of it.
    """
    sl, wx, calendar = estate
    buildings = {k: copy.copy(v) for k, v in sl.buildings.items()}
    runner = EstateRunner(
        master_seed=SEED,
        households={k: list(v) for k, v in sl.households.items()},
        buildings=buildings, thermal=dict(sl.thermal),
        owned={k: {kk: dict(vv) for kk, vv in v.items()}
               for k, v in sl.owned.items()},
        pv=dict(sl.pv), weather_minute=wx.site_minute, calendar=calendar,
    )
    runner.initialise()
    effects = []
    totals: dict[str, dict[str, float]] = {}
    for day in calendar:
        if mutate is not None and day.sim_day == mutate_on_day:
            effects.append(mutate(runner, day))
        exchange = runner.phase_a(day, sl.disruptions)
        result = runner.run_day(day, exchange)
        for row in result.energy_rows:
            acc = totals.setdefault(row["building_id"], {})
            for k, v in row.items():
                # EVERY numeric field, not just `*_wh`. Collecting only the
                # watt-hour terms made this harness report a working fabric
                # retrofit as inert: a gas dwelling's `hvac_wh` is zero by
                # construction - run.py puts no gas heating on the electricity
                # meter - so the whole effect of insulating it lands in
                # `heat_delivered_kwh` and the indoor temperatures. A test
                # whose observable cannot see the mechanism is worse than no
                # test, because it reports a false negative with confidence.
                if isinstance(v, bool) or not isinstance(v, (int, float)):
                    continue
                acc[k] = acc.get(k, 0.0) + float(v)
    return totals, effects, runner, buildings


def _moved(before: dict, after: dict, bid: str, *, tol: float = 1e-6) -> dict:
    """Every numeric field of the energy row that differs for one dwelling."""
    out = {}
    for k in sorted(set(before.get(bid, {})) | set(after.get(bid, {}))):
        b = before.get(bid, {}).get(k, 0.0)
        a = after.get(bid, {}).get(k, 0.0)
        if abs(a - b) > tol:
            out[k] = (round(b, 2), round(a, 2))
    return out


def _n_other_dwellings_moved(before: dict, after: dict, bid: str) -> list[str]:
    return [h for h in sorted(before) if h != bid and _moved(before, after, h)]


def _pick(sl, *, want_heat_pump: bool = False) -> str:
    """A household with no assets yet, heated the way the test needs."""
    for hh, b in sorted(sl.buildings.items()):
        if getattr(b, "has_battery", False) or hh in sl.pv:
            continue
        is_hp = getattr(b, "heating_system", "") == "heat pump"
        if is_hp is want_heat_pump and sl.households.get(hh):
            return hh
    pytest.skip(f"no slice dwelling with want_heat_pump={want_heat_pump}")


# --------------------------------------------------------------------------- #
# the four asset measures
# --------------------------------------------------------------------------- #

def test_a_heat_pump_conversion_changes_the_physics(estate):
    """I-062's first inert measure.

    Before week 3 this measure set ``owned[hh]["heat_pump"]``, which the runner
    never reads; the dwelling kept its gas boiler and the series did not move
    by a single watt-hour. Seven of the decade's events.
    """
    sl, _, _ = estate
    hh = _pick(sl, want_heat_pump=False)
    bid = sl.buildings[hh].building_id
    base, _, _, _ = _run(estate)

    def mutate(runner, day):
        return assets_mod.apply_heat_pump_retrofit(
            runner=runner, hh=hh, building=runner.buildings[hh],
            effective_day=day.sim_day,
        )

    after, effects, _, buildings = _run(estate, mutate=mutate)
    moved = _moved(base, after, bid)

    assert moved, (
        "a heat-pump conversion left the dwelling's energy series identical. "
        "This is exactly I-062: the measure is recorded as applied and the "
        "physics does not know about it. Check that the handler sets "
        "building.heating_system and heating_fuel, which is what run.py reads."
    )
    assert effects[0].changed is True
    # The conversion must put space heat ON the electricity meter. The energy
    # row carries no gas field - gas is derived downstream from
    # `heat_delivered_kwh` for a dwelling whose heating fuel is gas - so the
    # observable here is `hvac_wh`, which is zero for a gas boiler by
    # construction (run.py: "oil or gas: not electric") and positive for a
    # heat pump. A conversion that left it at zero would not have happened.
    assert buildings[hh].heating_system == "heat pump"
    assert buildings[hh].heating_fuel == "electricity"
    assert "hvac_wh" in moved, (
        f"the dwelling's heating electricity did not move: {moved}. hvac_wh "
        f"is zero for a gas boiler and positive for a heat pump, so a real "
        f"conversion cannot leave it unchanged."
    )
    b, a = moved["hvac_wh"]
    assert b == 0.0 and a > 0.0, (
        f"hvac_wh went {b} -> {a}; a gas dwelling must start at zero heating "
        f"electricity and end above it"
    )
    bi, ai = moved["import_wh"]
    assert ai > bi, (
        f"import fell from {bi} to {ai} after moving space heat onto the "
        f"electricity meter, which is the wrong direction"
    )
    # The dwelling's heat DEMAND is a property of its fabric and its
    # occupants, not of what burns to meet it, so it must be roughly
    # unchanged. A conversion that moved it has changed the building.
    assert "heat_delivered_kwh" not in moved or abs(
        moved["heat_delivered_kwh"][1] - moved["heat_delivered_kwh"][0]
    ) < 0.25 * max(moved["heat_delivered_kwh"][0], 1.0), (
        f"delivered heat moved from {moved.get('heat_delivered_kwh')} on a "
        f"fuel switch; the fabric and the occupants did not change, so the "
        f"demand should not have"
    )
    assert not _n_other_dwellings_moved(base, after, bid), (
        "converting one dwelling moved another dwelling's series, so the "
        "event has perturbed shared state or an RNG stream"
    )


def test_the_heat_pump_conversion_carries_deaps_emitter_derating(estate):
    """DEAP Table 4c(4)'s 0.70, which is the number that keeps it honest.

    A heat pump dropped into an un-retrofitted house keeps radiators sized for
    70 degC flow. Without the derating the conversion looks far better than the
    regulator says it is, and the dwellings WP5 converts are mostly old stock.
    """
    from baile_nua.physics import deap_controls as DC

    sl, _, _ = estate
    hh = _pick(sl, want_heat_pump=False)
    bid = sl.buildings[hh].building_id

    def mutate_with(runner, day):
        return assets_mod.apply_heat_pump_retrofit(
            runner=runner, hh=hh, building=runner.buildings[hh],
            effective_day=day.sim_day,
        )

    def mutate_without(runner, day):
        eff = assets_mod.apply_heat_pump_retrofit(
            runner=runner, hh=hh, building=runner.buildings[hh],
            effective_day=day.sim_day,
        )
        runner.hp_emitter_adjustment.pop(hh, None)   # the un-derated arm
        return eff

    derated, effects, _, _ = _run(estate, mutate=mutate_with)
    plain, _, _, _ = _run(estate, mutate=mutate_without)

    adj = DC.heat_pump_emitter_adjustment(compensation=False)
    assert adj == pytest.approx(0.70), (
        f"DEAP Table 4c(4)'s standard-radiator adjustment read as {adj}, not "
        f"0.70; the extraction or the manual version has changed"
    )
    assert effects[0].fields_after["hp_emitter_adjustment"] == adj
    moved = _moved(plain, derated, bid)
    assert moved, (
        "the emitter derating changed nothing, so run.py is not applying "
        "self.hp_emitter_adjustment to the COP"
    )
    # A derated COP means MORE electricity for the same delivered heat.
    el = [k for k in moved if k in ("hvac_wh", "import_wh", "net_meter_wh")]
    assert el, f"derating the COP moved no electricity field: {moved}"
    for k in el:
        b, a = moved[k]
        assert a > b, (
            f"{k} fell from {b} to {a} when the COP was derated by {adj}; a "
            f"less efficient heat pump must use more electricity, not less"
        )


def test_pv_fitted_mid_year_changes_the_physics(estate):
    sl, _, _ = estate
    hh = _pick(sl, want_heat_pump=False)
    bid = sl.buildings[hh].building_id
    base, _, _, _ = _run(estate)

    def mutate(runner, day):
        gen = runner.tree.generator(
            Stream.BUILDING_SYSTEMS, entity=f"{hh}:der_pv", sim_day=day.sim_day)
        return assets_mod.apply_pv_install(
            runner=runner, hh=hh, building=runner.buildings[hh],
            effective_day=day.sim_day, gen=gen,
        )

    after, effects, _, _ = _run(estate, mutate=mutate)
    moved = _moved(base, after, bid)
    assert moved, "a PV install left the series identical"
    assert effects[0].changed is True
    assert "pv_wh" in moved and moved["pv_wh"][1] > 0.0
    b, a = moved["import_wh"]
    assert a < b, f"import rose from {b} to {a} after fitting PV"
    assert not _n_other_dwellings_moved(base, after, bid)


def test_a_battery_fitted_mid_year_changes_the_physics(estate):
    """The one that needed the state object as well as the flag.

    ``initialise`` builds the ``Battery`` on the household's day-0 state from
    ``building.has_battery``, so setting the flag alone after initialise would
    leave a household flagged as having a battery whose state has none.
    """
    sl, _, _ = estate
    hh = _pick(sl, want_heat_pump=False)
    bid = sl.buildings[hh].building_id
    base, _, _, _ = _run(estate)

    def mutate(runner, day):
        gen = runner.tree.generator(
            Stream.BUILDING_SYSTEMS, entity=f"{hh}:der_battery",
            sim_day=day.sim_day)
        return assets_mod.apply_battery_install(
            runner=runner, hh=hh, building=runner.buildings[hh],
            effective_day=day.sim_day, gen=gen,
        )

    after, effects, runner, _ = _run(estate, mutate=mutate)
    moved = _moved(base, after, bid)
    assert moved, "a battery install left the series identical"
    assert effects[0].changed is True
    assert runner.state[hh].battery is not None, (
        "the dwelling is flagged as having a battery but its runner state has "
        "none, so the flag was set without constructing the device"
    )
    assert not _n_other_dwellings_moved(base, after, bid)


def test_smart_controls_do_nothing_on_a_boiler_home_and_say_so(estate):
    """The deliberate exception, pinned in both directions.

    DEAP publishes no rated effect for improving a boiler home's controls
    beyond the room thermostat every dwelling here already has. So this asserts
    the *absence* of a change together with the presence of a reason - which is
    the opposite of I-062, where the absence of a change came with a claim that
    it had been applied.
    """
    sl, _, _ = estate
    hh = _pick(sl, want_heat_pump=False)
    bid = sl.buildings[hh].building_id
    base, _, _, _ = _run(estate)

    def mutate(runner, day):
        return assets_mod.apply_smart_controls(
            runner=runner, hh=hh, building=runner.buildings[hh],
            effective_day=day.sim_day,
        )

    after, effects, _, _ = _run(estate, mutate=mutate)
    eff = effects[0]
    assert eff.changed is False
    assert "NO RATED EFFECT" in eff.note
    assert "Table 4e" in eff.note, (
        "a measure recorded as having no effect must name the source that "
        "says so, or it is indistinguishable from an unimplemented one"
    )
    assert not _moved(base, after, bid), (
        "smart controls moved a boiler home's series, but DEAP publishes no "
        "adjustment for it. A magnitude has been introduced from somewhere "
        "other than the source."
    )


def test_smart_controls_do_change_a_heat_pump_home(estate):
    """And DEAP does publish an effect there: Table 4c(4), 0.70 -> 0.75."""
    from baile_nua.physics import deap_controls as DC

    sl, _, _ = estate
    hh = _pick(sl, want_heat_pump=False)
    bid = sl.buildings[hh].building_id

    def convert_only(runner, day):
        return assets_mod.apply_heat_pump_retrofit(
            runner=runner, hh=hh, building=runner.buildings[hh],
            effective_day=day.sim_day,
        )

    def convert_then_controls(runner, day):
        eff = assets_mod.apply_heat_pump_retrofit(
            runner=runner, hh=hh, building=runner.buildings[hh],
            effective_day=day.sim_day,
        )
        assets_mod.apply_smart_controls(
            runner=runner, hh=hh, building=runner.buildings[hh],
            effective_day=day.sim_day,
        )
        return eff

    plain, _, _, _ = _run(estate, mutate=convert_only)
    smart, _, _, _ = _run(estate, mutate=convert_then_controls)
    moved = _moved(plain, smart, bid)
    assert moved, (
        "load or weather compensation on a heat-pump home changed nothing, "
        "but DEAP Table 4c(4) publishes 0.70 -> 0.75 for exactly this case"
    )
    assert DC.heat_pump_emitter_adjustment(compensation=True) == pytest.approx(0.75)
    el = [k for k in moved if k in ("hvac_wh", "import_wh", "net_meter_wh")]
    for k in el:
        b, a = moved[k]
        assert a < b, (
            f"{k} rose from {b} to {a} when compensation was fitted; a more "
            f"efficient heat pump must use less electricity"
        )


# --------------------------------------------------------------------------- #
# occupancy
# --------------------------------------------------------------------------- #

def test_a_person_arriving_mid_year_changes_the_physics(estate):
    """I-054's third kind, and the only one with no declared quantity.

    A birth on day 200 used to appear in the series on day 0 of the *following*
    year while its D20 label pointed at day 200.
    """
    sl, _, _ = estate
    hh = _pick(sl, want_heat_pump=False)
    bid = sl.buildings[hh].building_id
    base, _, _, _ = _run(estate)

    newcomer = PersonProfile(
        person_id="P-TEST-ARRIVAL", age=34, sex="female", role="adult",
        econ_status="at work", work_pattern="day", remote_share=0.0,
        chronotype=0.0, habit_strength=0.55, lapse_rate=0.08, attention=0.5,
        comfort=0.5, health_state="well", caring_load="none",
        school_year=None, vehicle_access="none",
    )

    def mutate(runner, day):
        return assets_mod.apply_occupancy_change(
            runner=runner, hh=hh, building=runner.buildings[hh],
            effective_day=day.sim_day, arrivals=(newcomer,),
        )

    after, effects, runner, _ = _run(estate, mutate=mutate)
    assert effects[0].changed is True
    assert "P-TEST-ARRIVAL" in effects[0].fields_after["person_ids"]
    moved = _moved(base, after, bid)
    assert moved, (
        "a person moved in and the dwelling's energy series did not move. An "
        "extra occupant adds metabolic gain, hot-water draws and appliance "
        "cycles, and gates the heating differently."
    )
    assert not _n_other_dwellings_moved(base, after, bid), (
        "one household gaining an occupant moved another household's series. "
        "With counter-based RNG this must not happen: each person's draws are "
        "keyed on their own id, so an arrival shifts nobody else's stream."
    )


def test_a_person_leaving_mid_year_changes_the_physics(estate):
    sl, _, _ = estate
    hh = next((h for h, ppl in sorted(sl.households.items())
               if len(ppl) >= 2 and not getattr(sl.buildings[h], "has_battery", False)),
              None)
    if hh is None:
        pytest.skip("no multi-person household in the slice")
    bid = sl.buildings[hh].building_id
    leaver = sorted(p.person_id for p in sl.households[hh])[0]
    base, _, _, _ = _run(estate)

    def mutate(runner, day):
        return assets_mod.apply_occupancy_change(
            runner=runner, hh=hh, building=runner.buildings[hh],
            effective_day=day.sim_day, departures=(leaver,),
        )

    after, effects, _, _ = _run(estate, mutate=mutate)
    assert effects[0].changed is True
    assert leaver not in effects[0].fields_after["person_ids"]
    assert _moved(base, after, bid), (
        "an occupant left and the dwelling's energy series did not move"
    )
    assert not _n_other_dwellings_moved(base, after, bid)


# --------------------------------------------------------------------------- #
# the fabric events, held to the same standard
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("measure", ["retrofit_fabric", "extension"])
def test_a_fabric_event_changes_the_physics(estate, measure):
    """These two were already dated; the test is new and applies to them too.

    Added because the standard has to be uniform: a test that held the new
    handlers to "it must change something" and exempted the existing ones
    would leave the same hole in a different place.
    """
    sl, _, _ = estate
    hh = _pick(sl, want_heat_pump=False)
    bid = sl.buildings[hh].building_id
    base, _, _, _ = _run(estate)

    def mutate(runner, day):
        tp = runner.thermal[hh]
        b = runner.buildings[hh]
        if measure == "retrofit_fabric":
            after_tp, eff = retrofit_mod.apply_fabric_retrofit(
                tp=tp, building=b, effective_day=day.sim_day)
        else:
            after_tp, eff = retrofit_mod.apply_extension(
                tp=tp, building=b, effective_day=day.sim_day)
            b.floor_area_m2 = eff.floor_area_after_m2
        runner.thermal[hh] = after_tp
        assets_mod.recompute_derived_household_state(runner=runner, hh=hh, building=b)
        return eff

    after, effects, _, _ = _run(estate, mutate=mutate)
    eff = effects[0]
    assert _moved(base, after, bid), f"a {measure} left the series identical"
    assert not _n_other_dwellings_moved(base, after, bid)
    if measure == "retrofit_fabric":
        assert eff.hlc_ratio < 1.0, (
            f"a fabric retrofit raised the heat-loss coefficient "
            f"(ratio {eff.hlc_ratio}); insulating a cavity cannot do that"
        )
    else:
        assert eff.hlc_ratio > 1.0, (
            f"an extension lowered the heat-loss coefficient absolutely "
            f"(ratio {eff.hlc_ratio}); adding envelope adds loss, and the "
            f"dilution it also causes is in the SPECIFIC loss, not this"
        )
        assert eff.floor_area_after_m2 > eff.floor_area_before_m2


def test_a_fabric_event_re_derives_the_comfort_shift(estate):
    """The half-applied event I-054 left behind.

    The comfort shift is a standing function of the dwelling's specific heat
    loss, computed once in the runner's constructor. A retrofit that leaves it
    stale changes the fabric without changing the household's response to it,
    which is half an event: the dwelling gets cheaper to heat and the occupants
    go on economising as if it had not.
    """
    sl, _, _ = estate
    hh = _pick(sl, want_heat_pump=False)
    _, _, calendar = estate
    base_runner = _run(estate)[2]
    if not base_runner.comfort_taking:
        pytest.skip("comfort-taking is off, so there is no shift to re-derive")
    before = dict(base_runner.comfort_shift.get(hh) or {})

    tp, eff = retrofit_mod.apply_fabric_retrofit(
        tp=base_runner.thermal[hh], building=base_runner.buildings[hh],
        effective_day=0,
    )
    base_runner.thermal[hh] = tp
    out = assets_mod.recompute_derived_household_state(
        runner=base_runner, hh=hh, building=base_runner.buildings[hh],
    )
    after = base_runner.comfort_shift[hh]

    assert "comfort_shift" in out
    assert after != before, (
        "the dwelling's heat loss fell by a ratio of "
        f"{eff.hlc_ratio} and its comfort shift did not move. The household "
        "is economising against a cost per degree the retrofit removed."
    )
    # A cheaper dwelling to heat takes MORE comfort, not less: prebound falls.
    assert after["setpoint_shift_c"] >= before["setpoint_shift_c"] - 1e-9, (
        f"specific loss fell and the setpoint shift went DOWN "
        f"({before['setpoint_shift_c']} -> {after['setpoint_shift_c']}), "
        f"which inverts the prebound mechanism"
    )


def test_every_wp5_measure_has_a_dated_handler():
    """No measure may be left without one, which is how I-062 happened.

    The authority is WP5's own ``MEASURES`` table, not a list in this file: a
    sixth measure added to the life course shows up here as a failure rather
    than silently joining the inert two.
    """
    from baile_nua.lifecourse.tenyear import MEASURES, MEASURE_REACHES_THE_SERIES

    missing = sorted(set(MEASURES) - set(MEASURE_REACHES_THE_SERIES))
    assert not missing, (
        f"these WP5 measures have no statement of whether they reach the "
        f"series: {missing}. I-062 is what happens when one does not."
    )
    for measure, how in MEASURE_REACHES_THE_SERIES.items():
        assert "week 3, dated" in how or "dated" in how, (
            f"{measure} is not dated: {how}"
        )
