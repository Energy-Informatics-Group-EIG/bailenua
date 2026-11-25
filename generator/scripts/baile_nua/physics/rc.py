"""F1/F2 grey-box RC building physics, Numba-compiled (design 5.7, 8.2).

    F1  Two-zone grey-box RC      Whole-home energy, flexibility estimation,
                                  forecasting, DR.  Used in all homes.
    F2  Room-level multi-zone RC  Room occupancy, comfort, CO2/RH, sensor
                                  placement.  Homes with room sensors (T3, T4).

The F1 network, per building, is a 4R3C model: two air nodes (living and
sleeping) and one envelope node.

    living ──R_ie──┐                        ┌── R_inf ── ambient
                   ├── envelope ── R_ea ──  ambient
    sleeping ─R_ie─┘
    living ──R_zz── sleeping

State: ``[T_living, T_sleep, T_env]``.  Driven by ambient temperature, solar
gain through the aperture, internal gains from occupants and appliances, and
delivered heat.

**Why an implicit step.** The explicit Euler step is only stable while
``dt < 2 * C_min / sum(1/R)``, and the air nodes have small capacitance - for a
well-insulated flat the air node's own time constant is a few minutes, so a
1-minute explicit step sits right at the stability boundary and a draughty
minute can make it oscillate or diverge. The solver therefore uses a
**semi-implicit (backward Euler) step**, which is unconditionally stable for
this network and lets the 1-minute step the design mandates be taken safely at
any parameter value. Each step solves a 3x3 system, which Numba does directly.

**Energy conservation is checked, not assumed.** :func:`simulate_day` returns
the energy balance residual, and design 7.2 requires it within 0.1% of daily
energy.  The residual is computed from the same arrays the state came from, so
it cannot agree by construction.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import numpy as np

try:
    from numba import njit

    _HAVE_NUMBA = True
except ImportError:  # pragma: no cover
    _HAVE_NUMBA = False

    def njit(*a, **k):  # type: ignore[misc]
        def deco(fn):
            return fn
        return deco if not a else a[0]

__all__ = [
    "RCState",
    "ThermalParams",
    "simulate_minutes",
    "simulate_day",
    "glazing_incident_w_m2",
    "GLAZING_ORIENTATION_SHARES",
    "PURGE_START_C",
    "PURGE_SPAN_C",
    "PURGE_ACH_MAX",
    "THERMOSTAT_BAND_C",
    "co2_step",
    "CO2_OUTDOOR_PPM",
    "CO2_PER_PERSON_L_S",
    "MOISTURE_PER_PERSON_G_H",
]

#: Outdoor CO2, ppm. Design 7.2 requires indoor CO2 >= outdoor.
CO2_OUTDOOR_PPM = 420.0
#: CO2 generation per sedentary adult, litres per second. ~0.005 l/s is the
#: standard figure for 1.2 met.
CO2_PER_PERSON_L_S = 0.0052
#: Moisture generation per person, grams per hour, at rest.
MOISTURE_PER_PERSON_G_H = 55.0
#: Sensible heat per person at rest, W.
#: Proportional band of the room thermostat, in kelvin (I-033).
#:
#: A real room thermostat modulates over roughly half a kelvin to a kelvin and
#: a half. 1.5 K is the wide end, chosen because the solver steps at one minute
#: and a narrower band would chatter without changing the daily energy.
THERMOSTAT_BAND_C: float = 1.5

#: Purge ventilation: the DEAP overheating assessment's own mechanism (I-032).
#:
#: Design 5.7 specifies a grey-box RC network and says nothing about how heat
#: leaves an overheating dwelling, because a calculation that only ever heats
#: does not need to know. The F1 model therefore had no path at all, and a
#: sunny Irish August put the annual median living temperature at 24.6 C.
#:
#: Ireland's DEAP (and the UK SAP it derives from) handles this in its
#: overheating assessment by assuming windows are opened in summer, raising the
#: air change rate well above the background infiltration. These values are
#: that mechanism: a ramp starting at the temperature at which people reliably
#: open windows, reaching full purge a few degrees above it.
#:
#: Declared assumptions [A] in their exact values; the mechanism is not in
#: doubt and its absence was a clear error.
PURGE_START_C: float = 24.0
#: Degrees above PURGE_START_C at which purge reaches its maximum.
PURGE_SPAN_C: float = 4.0
#: Air changes per hour added at full purge. An open window on a still day is
#: worth roughly 2 to 4 ach in the room it serves; 3.0 across the dwelling is
#: the middle of that and well below a through-draught.
PURGE_ACH_MAX: float = 3.0

SENSIBLE_HEAT_PER_PERSON_W = 75.0


@dataclasses.dataclass
class ThermalParams:
    """One building's F1 parameters, as stored in D02."""

    r_ie: float
    r_ea: float
    r_zz: float
    r_inf: float
    c_living: float
    c_sleep: float
    c_env: float
    solar_aperture_m2: float
    vol_living_m3: float
    vol_sleep_m3: float
    ach_base: float
    heat_emitter_w: float

    def as_array(self) -> np.ndarray:
        return np.array(
            [
                self.r_ie, self.r_ea, self.r_zz, self.r_inf,
                self.c_living, self.c_sleep, self.c_env,
                self.solar_aperture_m2, self.vol_living_m3, self.vol_sleep_m3,
                self.ach_base, self.heat_emitter_w,
            ],
            dtype=np.float64,
        )


@dataclasses.dataclass
class RCState:
    temp_living_c: float
    temp_sleep_c: float
    temp_env_c: float
    co2_living_ppm: float = CO2_OUTDOOR_PPM
    co2_sleep_ppm: float = CO2_OUTDOOR_PPM
    rh_living_pct: float = 55.0

    def as_array(self) -> np.ndarray:
        return np.array(
            [self.temp_living_c, self.temp_sleep_c, self.temp_env_c,
             self.co2_living_ppm, self.co2_sleep_ppm, self.rh_living_pct],
            dtype=np.float64,
        )


@njit(cache=True, fastmath=False)
def _solve3(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Solve a 3x3 system by Gaussian elimination with partial pivoting.

    Written out rather than calling ``np.linalg.solve`` because Numba's
    ``nopython`` mode supports only a subset of linalg and a 3x3 solve is
    faster inline.  ``fastmath=False`` throughout this module: the
    reproducibility contract (design 8.2) forbids it, because fast-math lets
    the compiler reassociate float operations and the results then depend on
    the compiler rather than on the model.
    """
    m = a.copy()
    v = b.copy()
    x = np.zeros(3, dtype=np.float64)
    for col in range(3):
        piv = col
        big = abs(m[col, col])
        for row in range(col + 1, 3):
            if abs(m[row, col]) > big:
                big = abs(m[row, col])
                piv = row
        if piv != col:
            for k in range(3):
                tmp = m[col, k]
                m[col, k] = m[piv, k]
                m[piv, k] = tmp
            tmp = v[col]
            v[col] = v[piv]
            v[piv] = tmp
        d = m[col, col]
        if d == 0.0:
            d = 1e-12
        for row in range(col + 1, 3):
            f = m[row, col] / d
            for k in range(col, 3):
                m[row, k] -= f * m[col, k]
            v[row] -= f * v[col]
    for col in range(2, -1, -1):
        acc = v[col]
        for k in range(col + 1, 3):
            acc -= m[col, k] * x[k]
        d = m[col, col]
        if d == 0.0:
            d = 1e-12
        x[col] = acc / d
    return x


@njit(cache=True, fastmath=False)
def simulate_minutes(
    params: np.ndarray,
    state0: np.ndarray,
    temp_ambient: np.ndarray,
    ghi: np.ndarray,
    internal_gain_living_w: np.ndarray,
    internal_gain_sleep_w: np.ndarray,
    heat_living_w: np.ndarray,
    heat_sleep_w: np.ndarray,
    occupants_living: np.ndarray,
    occupants_sleep: np.ndarray,
    extra_ach: np.ndarray,
    dt_s: float,
    purge_start_c: float,
    purge_span_c: float,
    purge_ach_max: float,
    setpoint_living_c: np.ndarray,
    setpoint_sleep_c: np.ndarray,
    thermostat_band_c: float,
) -> tuple:
    """Step the F1 network for ``len(temp_ambient)`` minutes.

    Returns ``(temps, co2, energy)`` where ``temps`` is ``(n, 3)``, ``co2`` is
    ``(n, 2)``, ``energy`` is the six-element balance
    ``[heat_in_J, solar_J, internal_J, loss_fabric_J, loss_vent_J, stored_J]``
    and ``ach_used`` is the air change rate applied each minute, background
    plus requested plus purge.
    """
    r_ie, r_ea, r_zz, r_inf = params[0], params[1], params[2], params[3]
    c_liv, c_slp, c_env = params[4], params[5], params[6]
    aperture, vol_liv, vol_slp = params[7], params[8], params[9]
    ach_base = params[10]

    n = temp_ambient.shape[0]
    temps = np.zeros((n, 3), dtype=np.float64)
    co2 = np.zeros((n, 2), dtype=np.float64)
    # The air change rate the solver ACTUALLY used, reported rather than
    # recomputed downstream. D16 publishes ach_effective, and recomputing the
    # purge formula in the writer is how the published solar gain came to
    # differ from the one the solver saw.
    ach_used = np.zeros(n, dtype=np.float64)
    # The heat actually DELIVERED, as opposed to the capacity offered. D16
    # publishes heat_delivered_w and the thermostat is what decides it.
    heat_applied = np.zeros(n, dtype=np.float64)

    t_liv = state0[0]
    t_slp = state0[1]
    t_env = state0[2]
    c_liv_ppm = state0[3]
    c_slp_ppm = state0[4]

    # Split the infiltration conductance between the two zones by volume, so a
    # larger zone loses proportionally more air.
    vol_total = vol_liv + vol_slp
    if vol_total <= 0.0:
        vol_total = 1.0
    frac_liv = vol_liv / vol_total
    frac_slp = 1.0 - frac_liv

    g_ie = 1.0 / r_ie if r_ie > 0.0 else 0.0
    g_ea = 1.0 / r_ea if r_ea > 0.0 else 0.0
    g_zz = 1.0 / r_zz if r_zz > 0.0 else 0.0

    heat_j = 0.0
    solar_j = 0.0
    internal_j = 0.0
    loss_fabric_j = 0.0
    loss_vent_j = 0.0

    for i in range(n):
        ta = temp_ambient[i]
        # Infiltration conductance this minute: background, plus any window
        # opening the behaviour model has requested, plus PURGE ventilation.
        #
        # Purge is closed-loop on the solved temperature and it is physics, not
        # behaviour dressed up: an overheating dwelling vents, through opened
        # windows in a real home and through the DEAP overheating assessment's
        # own assumed purge rate in a calculation. Without it the F1 model had
        # no path at all by which heat could leave a sunny house, and the
        # consequence was not a tail: the ANNUAL MEDIAN living-zone temperature
        # came out at 24.6 C against an Irish 17 to 19, 19% of epochs exceeded
        # 30 C and one dwelling reached 64.3 C (I-032).
        #
        # It ramps rather than switching, so there is no limit cycle, and it
        # only ever helps when outside is cooler than inside - opening a window
        # on a hotter day makes things worse, and a model that vented anyway
        # would cool houses with warm air.
        # ---- the thermostat, closed-loop on the ROOM (I-033) -------------
        #
        # heat_living_w and heat_sleep_w are the emitter output AVAILABLE this
        # minute - zero outside the timer window or when nobody is home - and
        # the thermostat decides how much of it is called for, from the
        # temperature of the room itself.
        #
        # It used to be decided outside the solver from the OUTDOOR
        # temperature: demand = (setpoint - temp_air) / 18, applied for the
        # whole window regardless of how warm the room already was. That is not
        # a thermostat, it is weather compensation with the room thermostat
        # missing, and it has two consequences. The room sails past its
        # setpoint - a 40 C peak appeared in nearly every month of the year,
        # including at 22:15 in August - and the heating cannot respond to
        # solar or internal gain at all, so a bright winter day still gets full
        # output.
        sp_liv = setpoint_living_c[i]
        if sp_liv > -273.0:
            call_liv = (sp_liv - t_liv) / thermostat_band_c
            if call_liv < 0.0:
                call_liv = 0.0
            elif call_liv > 1.0:
                call_liv = 1.0
            q_heat_liv = heat_living_w[i] * call_liv
        else:
            q_heat_liv = heat_living_w[i]

        sp_slp = setpoint_sleep_c[i]
        if sp_slp > -273.0:
            call_slp = (sp_slp - t_slp) / thermostat_band_c
            if call_slp < 0.0:
                call_slp = 0.0
            elif call_slp > 1.0:
                call_slp = 1.0
            q_heat_slp = heat_sleep_w[i] * call_slp
        else:
            q_heat_slp = heat_sleep_w[i]

        ach = ach_base + extra_ach[i]
        # No purge while heat is being delivered. A thermostat has priority
        # over a window: a dwelling that is both heating and venting is
        # burning fuel to warm the outdoors, and the real sequence is that the
        # thermostat cuts the heat first. Without this condition a cold
        # dwelling under continuous heat input vented at 2.12 air changes an
        # hour, which a test caught only because it set the heat with no
        # thermostat in front of it.
        if q_heat_liv <= 0.0 and t_liv > purge_start_c and ta < t_liv:
            ramp = (t_liv - purge_start_c) / purge_span_c
            if ramp > 1.0:
                ramp = 1.0
            ach += purge_ach_max * ramp
        ach_used[i] = ach
        heat_applied[i] = q_heat_liv + q_heat_slp
        g_inf_total = 0.33 * ach * vol_total
        g_inf_liv = g_inf_total * frac_liv
        g_inf_slp = g_inf_total * frac_slp

        # ``ghi`` is now the irradiance INCIDENT ON THE GLAZING, computed by
        # glazing_incident_w_m2 from the façade orientations. It was the global
        # HORIZONTAL irradiance, which is the single largest error the physics
        # had: at an Irish summer noon a horizontal surface receives 700 to 900
        # W/m2 while a vertical south façade receives 400 to 500 and a north
        # one under 150, because the sun is high. Applying the horizontal value
        # to vertical windows roughly doubled summer solar gain, and August's
        # mean solar gain came out at 1,436 W against 287 W of internal gain.
        q_sol = aperture * ghi[i]
        q_int_liv = internal_gain_living_w[i] + SENSIBLE_HEAT_PER_PERSON_W * occupants_living[i]
        q_int_slp = internal_gain_sleep_w[i] + SENSIBLE_HEAT_PER_PERSON_W * occupants_sleep[i]

        # Backward Euler: (C/dt + G) T_new = C/dt T_old + sources.
        a = np.zeros((3, 3), dtype=np.float64)
        b = np.zeros(3, dtype=np.float64)

        a[0, 0] = c_liv / dt_s + g_ie + g_zz + g_inf_liv
        a[0, 1] = -g_zz
        a[0, 2] = -g_ie
        b[0] = c_liv / dt_s * t_liv + q_sol + q_int_liv + q_heat_liv + g_inf_liv * ta

        a[1, 0] = -g_zz
        a[1, 1] = c_slp / dt_s + g_ie + g_zz + g_inf_slp
        a[1, 2] = -g_ie
        b[1] = c_slp / dt_s * t_slp + q_int_slp + q_heat_slp + g_inf_slp * ta

        a[2, 0] = -g_ie
        a[2, 1] = -g_ie
        a[2, 2] = c_env / dt_s + 2.0 * g_ie + g_ea
        b[2] = c_env / dt_s * t_env + g_ea * ta

        x = _solve3(a, b)
        t_liv_new = x[0]
        t_slp_new = x[1]
        t_env_new = x[2]

        # Energy accounting, on the SOLVED state so the balance is a real check.
        heat_j += (q_heat_liv + q_heat_slp) * dt_s
        solar_j += q_sol * dt_s
        internal_j += (q_int_liv + q_int_slp) * dt_s
        loss_fabric_j += g_ea * (t_env_new - ta) * dt_s
        loss_vent_j += (
            g_inf_liv * (t_liv_new - ta) + g_inf_slp * (t_slp_new - ta)
        ) * dt_s

        t_liv = t_liv_new
        t_slp = t_slp_new
        t_env = t_env_new
        temps[i, 0] = t_liv
        temps[i, 1] = t_slp
        temps[i, 2] = t_env

        # ---- CO2, one well-mixed box per zone ---------------------------
        # dC/dt = (generation - ventilation * (C - C_out)) / V
        gen_liv = CO2_PER_PERSON_L_S * occupants_living[i] * 1000.0   # ml/s
        gen_slp = CO2_PER_PERSON_L_S * occupants_sleep[i] * 1000.0
        q_liv_m3_s = ach * vol_liv / 3600.0
        q_slp_m3_s = ach * vol_slp / 3600.0
        # ml/s into m3 gives ppm directly: 1 ml/m3 = 1 ppm.
        if vol_liv > 0.0:
            dc = (gen_liv / vol_liv - q_liv_m3_s / vol_liv * (c_liv_ppm - CO2_OUTDOOR_PPM)) * dt_s
            c_liv_ppm += dc
        if vol_slp > 0.0:
            dc = (gen_slp / vol_slp - q_slp_m3_s / vol_slp * (c_slp_ppm - CO2_OUTDOOR_PPM)) * dt_s
            c_slp_ppm += dc
        # Physical floor: indoor CO2 can never fall below outdoor (design 7.2).
        if c_liv_ppm < CO2_OUTDOOR_PPM:
            c_liv_ppm = CO2_OUTDOOR_PPM
        if c_slp_ppm < CO2_OUTDOOR_PPM:
            c_slp_ppm = CO2_OUTDOOR_PPM
        co2[i, 0] = c_liv_ppm
        co2[i, 1] = c_slp_ppm

    stored_j = (
        c_liv * (t_liv - state0[0])
        + c_slp * (t_slp - state0[1])
        + c_env * (t_env - state0[2])
    )
    energy = np.array(
        [heat_j, solar_j, internal_j, loss_fabric_j, loss_vent_j, stored_j],
        dtype=np.float64,
    )
    return temps, co2, energy, ach_used, heat_applied


def simulate_day(
    params: ThermalParams,
    state0: RCState,
    *,
    temp_ambient: np.ndarray,
    ghi: np.ndarray,
    internal_gain_living_w: np.ndarray,
    internal_gain_sleep_w: np.ndarray,
    heat_living_w: np.ndarray,
    heat_sleep_w: np.ndarray,
    occupants_living: np.ndarray,
    occupants_sleep: np.ndarray,
    extra_ach: np.ndarray | None = None,
    dt_s: float = 60.0,
    purge: bool = True,
    setpoint_living_c: np.ndarray | None = None,
    setpoint_sleep_c: np.ndarray | None = None,
) -> dict[str, Any]:
    """Run one day (or any span) and report the state plus the energy balance.

    ``ghi`` is the irradiance **incident on the glazing**, not the global
    horizontal: see :func:`glazing_incident_w_m2`. ``purge=False`` disables
    purge ventilation, which exists so a negative control can show what the
    model does without it.

    ``heat_living_w`` and ``heat_sleep_w`` are the emitter output **available**
    each minute, and the setpoint arrays are what the thermostat compares the
    room against. Where a setpoint is ``-999`` (or the array is omitted) the
    available output is applied in full, open-loop - which is what the model
    did everywhere before I-033, and which is kept only so that a negative
    control can show the 40 C peaks it produced.
    """
    n = len(temp_ambient)
    for name, arr in (
        ("ghi", ghi), ("internal_gain_living_w", internal_gain_living_w),
        ("internal_gain_sleep_w", internal_gain_sleep_w),
        ("heat_living_w", heat_living_w), ("heat_sleep_w", heat_sleep_w),
        ("occupants_living", occupants_living), ("occupants_sleep", occupants_sleep),
    ):
        if len(arr) != n:
            raise ValueError(f"{name} has length {len(arr)}, expected {n}")
    extra = np.zeros(n, dtype=np.float64) if extra_ach is None else np.ascontiguousarray(
        extra_ach, dtype=np.float64
    )
    OPEN_LOOP = -999.0
    sp_liv = (
        np.full(n, OPEN_LOOP) if setpoint_living_c is None
        else np.ascontiguousarray(setpoint_living_c, dtype=np.float64)
    )
    sp_slp = (
        np.full(n, OPEN_LOOP) if setpoint_sleep_c is None
        else np.ascontiguousarray(setpoint_sleep_c, dtype=np.float64)
    )
    for name, arr in (("setpoint_living_c", sp_liv), ("setpoint_sleep_c", sp_slp)):
        if len(arr) != n:
            raise ValueError(f"{name} has length {len(arr)}, expected {n}")

    temps, co2, energy, ach_used, heat_applied = simulate_minutes(
        params.as_array(), state0.as_array(),
        np.ascontiguousarray(temp_ambient, dtype=np.float64),
        np.ascontiguousarray(ghi, dtype=np.float64),
        np.ascontiguousarray(internal_gain_living_w, dtype=np.float64),
        np.ascontiguousarray(internal_gain_sleep_w, dtype=np.float64),
        np.ascontiguousarray(heat_living_w, dtype=np.float64),
        np.ascontiguousarray(heat_sleep_w, dtype=np.float64),
        np.ascontiguousarray(occupants_living, dtype=np.float64),
        np.ascontiguousarray(occupants_sleep, dtype=np.float64),
        extra, dt_s,
        PURGE_START_C if purge else 1e9,
        PURGE_SPAN_C,
        PURGE_ACH_MAX if purge else 0.0,
        sp_liv, sp_slp, THERMOSTAT_BAND_C,
    )

    heat_j, solar_j, internal_j, loss_fab_j, loss_vent_j, stored_j = energy
    gain_j = heat_j + solar_j + internal_j
    loss_j = loss_fab_j + loss_vent_j
    residual_j = gain_j - loss_j - stored_j
    # Relative to total gross energy through the building, which is the
    # quantity design 7.2 means by "within 0.1% of daily energy".
    gross_j = abs(heat_j) + abs(solar_j) + abs(internal_j) + abs(loss_j) + abs(stored_j)
    relative = abs(residual_j) / gross_j if gross_j > 0 else 0.0

    return {
        "temps": temps,
        "ach_used": ach_used,
        "heat_applied_w": heat_applied,
        "co2": co2,
        "final_state": RCState(
            temp_living_c=float(temps[-1, 0]),
            temp_sleep_c=float(temps[-1, 1]),
            temp_env_c=float(temps[-1, 2]),
            co2_living_ppm=float(co2[-1, 0]),
            co2_sleep_ppm=float(co2[-1, 1]),
            rh_living_pct=state0.rh_living_pct,
        ),
        "energy_j": {
            "heat_delivered": float(heat_j),
            "solar_gain": float(solar_j),
            "internal_gain": float(internal_j),
            "loss_fabric": float(loss_fab_j),
            "loss_ventilation": float(loss_vent_j),
            "stored_change": float(stored_j),
            "residual": float(residual_j),
            "gross": float(gross_j),
            "relative_residual": float(relative),
        },
        "energy_kwh": {
            "heat_delivered": float(heat_j) / 3.6e6,
            "solar_gain": float(solar_j) / 3.6e6,
            "internal_gain": float(internal_j) / 3.6e6,
            "loss_total": float(loss_j) / 3.6e6,
        },
        "n_steps": n,
        "dt_s": dt_s,
    }


def co2_step(
    c_ppm: float, occupants: float, volume_m3: float, ach: float, dt_s: float = 60.0
) -> float:
    """One CO2 step, exposed for testing the mass balance independently."""
    if volume_m3 <= 0:
        return c_ppm
    gen = CO2_PER_PERSON_L_S * occupants * 1000.0
    q = ach * volume_m3 / 3600.0
    c_new = c_ppm + (gen / volume_m3 - q / volume_m3 * (c_ppm - CO2_OUTDOOR_PPM)) * dt_s
    return max(c_new, CO2_OUTDOOR_PPM)


#: How a dwelling's glazing is distributed over the cardinal orientations.
#:
#: DEAP's standard assumption for a dwelling of unknown orientation is an even
#: split, and that is what this is. A real estate has a street axis and so a
#: real bias, which weeks 2 and 3 can take from the OSi building footprints;
#: E1 has no orientation data and an even split is the honest default. It is
#: also the conservative one for overheating: it neither assumes every window
#: faces north nor that every window faces south.
GLAZING_ORIENTATION_SHARES: dict[str, float] = {
    "south": 0.25, "east": 0.25, "west": 0.25, "north": 0.25,
}

_AZIMUTH_OF = {"south": 180.0, "east": 90.0, "west": 270.0, "north": 0.0}


def glazing_incident_w_m2(
    *,
    ghi_w_m2: np.ndarray,
    dni_w_m2: np.ndarray,
    dhi_w_m2: np.ndarray,
    solar_zenith_deg: np.ndarray,
    solar_azimuth_deg: np.ndarray,
    shares: dict[str, float] | None = None,
) -> np.ndarray:
    """Mean irradiance on the dwelling's glazing, W/m2 of glazing.

    **Why this exists (I-032).** The solver multiplied the effective solar
    aperture by the global HORIZONTAL irradiance. Windows are vertical. At an
    Irish summer noon a horizontal surface receives 700 to 900 W/m2 while a
    vertical south façade receives 400 to 500 and a north one under 150,
    because the sun is high; in midwinter the relationship reverses, since a
    low sun strikes a south wall almost square on while grazing the ground.
    Using the horizontal value for vertical glazing therefore roughly doubled
    summer gain and understated winter gain - the error has the wrong sign in
    both seasons, which is why it showed up as an annual median temperature of
    24.6 C alongside a plausible-looking winter.

    The transposition is the isotropic-sky model, the same one the PV module
    uses, applied to a vertical plane at each orientation and averaged by the
    glazing share. Isotropic rather than anisotropic because it is the
    conservative choice for a vertical surface and needs no extra parameters.
    """
    shares = shares or GLAZING_ORIENTATION_SHARES
    total = sum(shares.values())
    if total <= 0:
        raise ValueError("glazing orientation shares sum to zero")

    zen = np.asarray(solar_zenith_deg, dtype=np.float64)
    azi = np.asarray(solar_azimuth_deg, dtype=np.float64)
    ghi = np.asarray(ghi_w_m2, dtype=np.float64)
    dni = np.asarray(dni_w_m2, dtype=np.float64)
    dhi = np.asarray(dhi_w_m2, dtype=np.float64)

    # Vertical plane: tilt 90 degrees, so sky view factor and ground view
    # factor are both one half.
    sky = dhi * 0.5
    ground = ghi * 0.2 * 0.5          # albedo 0.2, the DEAP default

    out = np.zeros_like(ghi)
    zr = np.radians(zen)
    for name, share in sorted(shares.items()):
        surf_az = np.radians(_AZIMUTH_OF[name])
        # cos(incidence) on a vertical surface of azimuth surf_az.
        cos_i = np.sin(zr) * np.cos(np.radians(azi) - surf_az)
        beam = dni * np.clip(cos_i, 0.0, None)
        poa = beam + sky + ground
        out += (share / total) * np.clip(poa, 0.0, None)

    # Nothing below the horizon, whatever the transposition says.
    return np.where(zen >= 90.0, 0.0, out)
