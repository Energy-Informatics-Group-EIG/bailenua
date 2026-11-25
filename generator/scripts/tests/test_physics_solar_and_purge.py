"""Tests for solar transposition and purge ventilation (I-032).

Why these did not exist before, and what that cost. The physics suite checked
the energy balance (which closes whatever heat the solver delivers), the
derived fabric parameters (which are per square metre and so blind to the area
being wrong) and the solver's stability. Nothing checked the TEMPERATURE the
model actually produces. The annual median living-zone temperature came out at
24.6 C against an Irish 17 to 19, 19% of epochs exceeded 30 C and one dwelling
reached 64.3 C, through a full year of simulation and 206 passing tests.
"""

from __future__ import annotations

import numpy as np
import pytest

from baile_nua.physics.rc import (
    GLAZING_ORIENTATION_SHARES,
    PURGE_ACH_MAX,
    PURGE_SPAN_C,
    PURGE_START_C,
    RCState,
    ThermalParams,
    THERMOSTAT_BAND_C,
    glazing_incident_w_m2,
    simulate_day,
)


def _params(**kw) -> ThermalParams:
    base = dict(
        r_ie=0.01, r_ea=0.004, r_zz=0.02, r_inf=0.01,
        c_living=2.0e7, c_sleep=1.2e7, c_env=4.0e7,
        solar_aperture_m2=7.0, vol_living_m3=150.0, vol_sleep_m3=110.0,
        ach_base=0.4, heat_emitter_w=9000.0,
    )
    base.update(kw)
    return ThermalParams(**base)


def _run(n=1440, *, ambient, incident, heat=0.0, purge=True, start=20.0):
    return simulate_day(
        _params(), RCState(temp_living_c=start, temp_sleep_c=start - 1.0,
                           temp_env_c=start - 2.0),
        temp_ambient=np.full(n, ambient), ghi=np.full(n, incident),
        internal_gain_living_w=np.full(n, 300.0),
        internal_gain_sleep_w=np.zeros(n),
        heat_living_w=np.full(n, heat), heat_sleep_w=np.zeros(n),
        occupants_living=np.full(n, 2.0), occupants_sleep=np.zeros(n),
        purge=purge,
    )


# --------------------------------------------------------------------------- #
# transposition
# --------------------------------------------------------------------------- #

def test_summer_glazing_receives_far_less_than_the_horizontal():
    """A high sun gives a vertical window much less than the ground gets.

    This is the error that doubled summer solar gain: the solver multiplied the
    effective aperture by the global HORIZONTAL irradiance, and windows are
    vertical.
    """
    one = np.array([1.0])
    inc = glazing_incident_w_m2(
        ghi_w_m2=one * 850.0, dni_w_m2=one * 700.0, dhi_w_m2=one * 200.0,
        solar_zenith_deg=one * 35.0, solar_azimuth_deg=one * 180.0,
    )[0]
    assert inc < 850.0 * 0.5, (
        f"with the sun 35 degrees from vertical the glazing received "
        f"{inc:.0f} W/m2 against a horizontal 850, a ratio of "
        f"{inc / 850:.2f}. A vertical surface should get well under half."
    )
    assert inc > 100.0, "the transposition cannot leave summer glazing dark"


def test_the_seasonal_relationship_reverses():
    """In winter a vertical surface does BETTER relative to the horizontal.

    A low sun strikes a south wall nearly square on while grazing the ground.
    The horizontal-irradiance error therefore has the wrong sign in BOTH
    seasons, overstating summer and understating winter, which is why it
    produced an implausible annual median alongside a plausible winter.
    """
    one = np.array([1.0])
    summer = glazing_incident_w_m2(
        ghi_w_m2=one * 850.0, dni_w_m2=one * 700.0, dhi_w_m2=one * 200.0,
        solar_zenith_deg=one * 35.0, solar_azimuth_deg=one * 180.0,
    )[0] / 850.0
    winter = glazing_incident_w_m2(
        ghi_w_m2=one * 180.0, dni_w_m2=one * 350.0, dhi_w_m2=one * 60.0,
        solar_zenith_deg=one * 72.0, solar_azimuth_deg=one * 180.0,
    )[0] / 180.0
    assert winter > summer, (
        f"glazing-to-horizontal ratio is {summer:.2f} in summer and "
        f"{winter:.2f} in winter; it must be the other way round"
    )


def test_no_solar_gain_below_the_horizon():
    one = np.array([1.0])
    assert glazing_incident_w_m2(
        ghi_w_m2=one * 50.0, dni_w_m2=one * 100.0, dhi_w_m2=one * 50.0,
        solar_zenith_deg=one * 95.0, solar_azimuth_deg=one * 10.0,
    )[0] == 0.0


def test_glazing_shares_sum_to_one():
    total = sum(GLAZING_ORIENTATION_SHARES.values())
    assert abs(total - 1.0) < 1e-9, f"shares sum to {total}"


def test_a_south_only_dwelling_beats_a_north_only_one_in_winter():
    one = np.array([1.0])
    kw = dict(
        ghi_w_m2=one * 180.0, dni_w_m2=one * 350.0, dhi_w_m2=one * 60.0,
        solar_zenith_deg=one * 72.0, solar_azimuth_deg=one * 180.0,
    )
    south = glazing_incident_w_m2(**kw, shares={"south": 1.0})[0]
    north = glazing_incident_w_m2(**kw, shares={"north": 1.0})[0]
    assert south > 2.0 * north, (
        f"south glazing {south:.0f} against north {north:.0f} W/m2 with the "
        f"sun due south; the orientation must matter"
    )


# --------------------------------------------------------------------------- #
# purge ventilation
# --------------------------------------------------------------------------- #

def test_purge_raises_the_air_change_rate_only_when_overheating():
    cool = _run(ambient=8.0, incident=20.0)
    assert np.isclose(cool["ach_used"].max(), 0.4, atol=0.05), (
        f"purge fired in a cold dwelling: max ach {cool['ach_used'].max():.2f}"
    )
    hot = _run(ambient=20.0, incident=400.0)
    assert hot["ach_used"].max() > 0.4 + 0.5 * PURGE_ACH_MAX, (
        f"purge did not fire in an overheating dwelling: max ach "
        f"{hot['ach_used'].max():.2f}"
    )


def test_purge_does_not_fire_when_outside_is_hotter_than_inside():
    """Opening a window on a hotter day makes things worse."""
    r = _run(ambient=34.0, incident=10.0, start=26.0)
    assert np.isclose(r["ach_used"].max(), 0.4, atol=0.05), (
        f"purge vented with outside hotter than inside: max ach "
        f"{r['ach_used'].max():.2f}"
    )


def test_purge_lowers_the_peak_and_keeps_the_balance_closed():
    with_p = _run(ambient=19.0, incident=450.0)
    without = _run(ambient=19.0, incident=450.0, purge=False)
    assert with_p["temps"][:, 0].max() < without["temps"][:, 0].max()
    for r in (with_p, without):
        assert abs(r["energy_j"]["relative_residual"]) < 1e-6, (
            "purge must not break the energy balance"
        )


def test_the_purge_ramp_has_no_limit_cycle():
    """A switch would chatter; a ramp must not.

    Checked as the absence of large minute-to-minute swings in the air change
    rate once purge is active.
    """
    r = _run(ambient=19.0, incident=450.0)
    ach = r["ach_used"]
    active = ach > 0.45
    if active.sum() < 60:
        pytest.skip("purge never became active in this scenario")
    jumps = np.abs(np.diff(ach[active]))
    assert jumps.max() < PURGE_ACH_MAX * 0.5, (
        f"the air change rate jumps by up to {jumps.max():.2f} between "
        f"consecutive minutes, which is a limit cycle rather than a ramp"
    )


# --------------------------------------------------------------------------- #
# the temperature the model actually produces
# --------------------------------------------------------------------------- #

def test_a_bright_warm_day_cannot_overheat_past_a_plausible_ceiling():
    """The check that was missing. 64.3 C was reached in the first full run.

    An Irish dwelling on the hottest, brightest day of 2022 can reach the high
    twenties indoors and does not reach the thirties for long. A ceiling of
    35 C is generous and still refuses the fault.
    """
    r = _run(ambient=24.0, incident=500.0, start=22.0)
    peak = float(r["temps"][:, 0].max())
    assert peak < 35.0, (
        f"the living zone reached {peak:.1f} C with 24 C outside and 500 W/m2 "
        f"on the glazing. No Irish dwelling does that, and the model has no "
        f"mechanism by which heat leaves if this fails."
    )


def test_a_cold_day_with_the_heating_off_does_not_fall_below_ambient():
    r = _run(ambient=2.0, incident=0.0, start=18.0)
    assert float(r["temps"][:, 0].min()) >= 2.0 - 1e-6, (
        "the living zone fell below ambient with no cooling present"
    )


def test_purge_thresholds_are_in_a_defensible_range():
    """The values are declared assumptions; the range they sit in is not."""
    assert 22.0 <= PURGE_START_C <= 27.0, (
        f"purge starts at {PURGE_START_C} C. Below 22 it would vent a "
        f"comfortably warm room in winter; above 27 it would not prevent the "
        f"overheating it exists for."
    )
    assert 1.0 <= PURGE_SPAN_C <= 8.0
    assert 1.0 <= PURGE_ACH_MAX <= 6.0, (
        f"{PURGE_ACH_MAX} air changes an hour at full purge. An open window on "
        f"a still day is worth roughly 2 to 4 in the room it serves."
    )


def test_purge_never_runs_while_the_heating_is_on():
    """A dwelling must not heat and vent at the same time.

    Found by a test whose scenario applied 3 kW continuously with no
    thermostat in front of it: the dwelling climbed past the purge threshold
    and vented at 2.12 air changes an hour while still being heated, which is
    burning fuel to warm the outdoors. A thermostat has priority over a
    window.
    """
    n = 1440
    r = simulate_day(
        _params(), RCState(temp_living_c=26.0, temp_sleep_c=25.0, temp_env_c=24.0),
        temp_ambient=np.full(n, 8.0), ghi=np.zeros(n),
        internal_gain_living_w=np.full(n, 300.0),
        internal_gain_sleep_w=np.zeros(n),
        heat_living_w=np.full(n, 4000.0), heat_sleep_w=np.zeros(n),
        occupants_living=np.full(n, 2.0), occupants_sleep=np.zeros(n),
    )
    assert np.isclose(r["ach_used"].max(), 0.4, atol=0.05), (
        f"the dwelling vented at up to {r['ach_used'].max():.2f} air changes "
        f"an hour while 4 kW of heat was being delivered"
    )


# --------------------------------------------------------------------------- #
# the thermostat (I-033)
# --------------------------------------------------------------------------- #

def _thermostat_run(*, ambient, setpoint=20.5, incident=0.0, n=1440, closed=True):
    cap_l = np.full(n, 9000.0 * 0.75)
    cap_s = np.full(n, 9000.0 * 0.25)
    kw = {}
    if closed:
        kw = dict(
            setpoint_living_c=np.full(n, setpoint),
            setpoint_sleep_c=np.full(n, setpoint - 3.0),
        )
    else:
        # The old behaviour: a fraction of the emitter decided from the
        # OUTDOOR temperature and applied regardless of the room.
        frac = float(np.clip((setpoint - ambient) / 18.0, 0.0, 1.0))
        cap_l = cap_l * frac
        cap_s = cap_s * frac
    return simulate_day(
        _params(), RCState(temp_living_c=18.0, temp_sleep_c=17.0, temp_env_c=12.0),
        temp_ambient=np.full(n, ambient), ghi=np.full(n, incident),
        internal_gain_living_w=np.full(n, 300.0),
        internal_gain_sleep_w=np.zeros(n),
        heat_living_w=cap_l, heat_sleep_w=cap_s,
        occupants_living=np.full(n, 2.0), occupants_sleep=np.zeros(n),
        **kw,
    )


def test_the_thermostat_holds_the_setpoint_instead_of_sailing_past_it():
    """The fault: a 40 C peak in nearly every month, one of them at 22:15.

    The controller proportioned on the OUTDOOR temperature and never looked at
    the room, so it applied a fixed fraction of the emitter for the whole
    timer window however warm the room already was.
    """
    r = _thermostat_run(ambient=2.0, setpoint=20.5)
    peak = float(r["temps"][:, 0].max())
    assert peak < 20.5 + 2.0, (
        f"the living zone reached {peak:.1f} C against a 20.5 C setpoint"
    )
    assert float(r["temps"][:, 0].mean()) > 19.0, (
        "the thermostat undershot: the room never reached its setpoint"
    )


def test_open_loop_control_is_what_overheated_and_is_still_reproducible():
    """Kept reproducible so a negative control can demonstrate the fault."""
    closed = _thermostat_run(ambient=2.0, closed=True)
    openl = _thermostat_run(ambient=2.0, closed=False)
    assert float(openl["temps"][:, 0].max()) > float(closed["temps"][:, 0].max()) + 10.0
    assert (
        openl["energy_kwh"]["heat_delivered"]
        > 3.0 * closed["energy_kwh"]["heat_delivered"]
    ), (
        "open-loop control delivered "
        f"{openl['energy_kwh']['heat_delivered']:.0f} kWh against closed-loop's "
        f"{closed['energy_kwh']['heat_delivered']:.0f}; the fault was roughly a "
        f"factor of four and must stay visible"
    )


def test_the_thermostat_responds_to_solar_gain():
    """A bright day must need less heat. Open-loop control could not do this."""
    dark = _thermostat_run(ambient=8.0, incident=0.0)
    bright = _thermostat_run(ambient=8.0, incident=250.0)
    assert (
        bright["energy_kwh"]["heat_delivered"]
        < dark["energy_kwh"]["heat_delivered"] - 0.5
    ), (
        f"heat delivered was {bright['energy_kwh']['heat_delivered']:.2f} kWh "
        f"with 250 W/m2 on the glazing against "
        f"{dark['energy_kwh']['heat_delivered']:.2f} in the dark; a thermostat "
        f"that sees the room must back off when the sun warms it"
    )


def test_heat_delivered_is_what_the_thermostat_called_for():
    """D16 publishes heat_delivered_w; it must not be the capacity offered."""
    r = _thermostat_run(ambient=14.0, setpoint=20.5)
    applied = r["heat_applied_w"]
    assert applied.max() <= 9000.0 + 1e-6
    assert applied.min() >= 0.0
    # On a mild day the thermostat must modulate rather than run flat out.
    assert applied.max() > 0.0 and float(np.median(applied)) < 9000.0 * 0.9, (
        "the thermostat ran at full output all day on a 14 C day"
    )
    # The energy balance must use the applied heat, not the capacity.
    from_balance = r["energy_kwh"]["heat_delivered"]
    from_series = float(applied.sum()) / 60.0 / 1000.0
    assert abs(from_balance - from_series) < 1e-6, (
        f"the balance says {from_balance:.4f} kWh and the series says "
        f"{from_series:.4f}; one of them is the capacity"
    )


def test_the_sleeping_zone_is_held_cooler_than_the_living_zone():
    r = _thermostat_run(ambient=4.0, setpoint=20.5)
    assert float(r["temps"][:, 1].mean()) < float(r["temps"][:, 0].mean()) - 1.0, (
        "the setback on the sleeping zone has no effect, so the two zones are "
        "not worth having"
    )


def test_thermostat_band_is_narrow_enough_to_hold_and_wide_enough_not_to_chatter():
    assert 0.3 <= THERMOSTAT_BAND_C <= 2.5, (
        f"a {THERMOSTAT_BAND_C} K proportional band. A real room thermostat "
        f"modulates over about half a kelvin to one and a half."
    )
