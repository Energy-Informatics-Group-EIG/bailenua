"""U25: domestic hot water - draw events, tank or instantaneous, immersion.

Why this subsystem exists
-------------------------
The E1 gas comparison's own docstring named its gap: *"DBERNG01 measures
everything that passes the gas meter - space heating, hot water, cooking where
the hob is gas, and the boiler's own losses - and E1 models only space
heating"*. The simulated-to-published ratio sat at **0.308**. U25 builds the
three missing terms so that U22's comfort-taking work has something real to
measure; a ratio of 0.3 cannot tell comfort-taking from a missing subsystem.

Where the numbers come from
---------------------------
U30 searched all 13,086 PxStat tables for `hot water`, `water heating`,
`immersion` and `cooking fuel` and found **zero hits for every one** (sweep
flags A-05, A-27). There is no CSO series for this. The Irish reference is the
regulatory methodology: SEAI's DEAP manual, declared as
``seai.deap.manual_4_2_7`` and transcribed into ``data/deap_hot_water.yaml``
with each value's table and section. Table 3 gives primary circuit losses,
Table 3a combi losses, Table 2 the cylinder temperature factors, and Section
4.5(d) the 110-litre / 1.672 kWh-per-day cylinder that anchors standing loss.

Demand is built the other way round
-----------------------------------
DEAP derives hot water demand from **floor area**, after SAP 10. This model
does not, and the choice is deliberate: U25 asks for draw events, and the
activity engine already simulates showering, bathing, washing up and cooking
with HETUS-derived durations. So a draw is generated from the activity that
causes it, and DEAP's floor-area figure is kept as the thing the result is
**judged against** rather than the thing assumed. That is the difference
between a model that reproduces a reference by construction and one that can
disagree with it.

The shower is the part that is not assumed: DEAP applies a minimum of 6 L/min
to every mixer shower, so the volume is that rate times the duration the
activity engine drew. Bath capacity and tap flow rates DEAP takes from
manufacturers' product data and publishes no default for, so those stay
declared assumptions, flagged in the data file with the search behind them.

Two rules that are easy to get wrong
------------------------------------
**A draw is not a tank volume.** A 40 degC draw from a 60 degC tank is mostly
tank water but not all of it: it mixes with the cold feed, so the litres taken
from the tank are ``V * (T_draw - T_cold) / (T_tank - T_cold)``. Charging the
full drawn volume to the tank would overstate hot water energy by roughly the
mixing fraction - about 40% at a 60 degC tank and a 10 degC feed.

**An electric shower is not water heating.** DEAP is explicit: an electric
shower *"uses electricity directly rather than from the water heating
system"*. It is an instantaneous electric load that must never also be charged
to the cylinder, and the appliance layer already models it as a load. So a
household with an electric shower draws no tank water for showering.
"""

from __future__ import annotations

import dataclasses
import functools
import math
from pathlib import Path
from typing import Any

__all__ = [
    "DHW_DATA_PATH",
    "SPECIFIC_HEAT_WATER_KWH_PER_L_K",
    "DHWSystem",
    "TankState",
    "DrawEvent",
    "deap_figures",
    "draw_for_activity",
    "cold_feed_temperature_c",
    "standby_loss_w",
    "primary_circuit_loss_kwh_yr",
    "combi_additional_loss_kwh_yr",
    "tank_step",
    "instantaneous_step",
    "DRAW_ACTIVITIES",
    "draw_schedule",
    "simulate_dhw_day",
    "shower_water_minutes",
    "dhw_system_for",
    "immersion_permitted_on",
    "cooking_fuel_for",
    "COOKING_FUELS",
    "cooking_fuel_shares",
]

DHW_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "deap_hot_water.yaml"

#: 4.18 kJ/(kg K) over 3600 kJ/kWh, with 1 litre taken as 1 kg. Physical
#: constant, not a calibration choice.
SPECIFIC_HEAT_WATER_KWH_PER_L_K = 4.18 / 3600.0


@functools.lru_cache(maxsize=1)
def deap_figures() -> dict[str, Any]:
    """The transcribed DEAP figures, with their provenance block."""
    import yaml

    data = yaml.safe_load(DHW_DATA_PATH.read_text(encoding="utf-8"))
    if "provenance" not in data:
        raise ValueError(
            f"{DHW_DATA_PATH} has no provenance block; every value in it has "
            f"to name the document it was transcribed from"
        )
    return data


@dataclasses.dataclass(frozen=True)
class DHWSystem:
    """How one dwelling makes its hot water.

    ``kind`` decides whether there is a tank at all:

    ``cylinder_indirect``
        A cylinder heated through a primary circuit from the main boiler, with
        an immersion as backup. The common Irish arrangement.
    ``cylinder_immersion``
        A cylinder whose main water heater is the immersion itself.
    ``combi``
        Instantaneous from the boiler, no store, Table 3a losses.
    ``instantaneous_electric``
        Electric shower or point-of-use heater only, no store.
    """

    kind: str
    tank_litres: float | None = None
    has_cylinder_thermostat: bool = True
    primary_pipework_insulated: bool = True
    has_immersion: bool = True
    immersion_rated_w: float = 3000.0
    #: PV surplus diverted to the immersion rather than exported.
    has_pv_diverter: bool = False
    #: The thermostat setpoint and the band it reheats across.
    setpoint_c: float = 60.0
    deadband_c: float = 5.0
    #: A diverter may take the tank above the thermostat setpoint, because
    #: surplus PV is otherwise exported for less than it is worth. Capped well
    #: below scalding: this is a declared control choice, not a DEAP figure.
    diverter_setpoint_c: float = 70.0
    #: Boiler coil output available to the cylinder.
    coil_rated_w: float = 12_000.0
    #: Whether the boiler serves space heating and water heating on a single
    #: interlocked control. DEAP docks 5% from efficiency when it does not.
    interlocked: bool = True

    @property
    def has_tank(self) -> bool:
        return self.kind in ("cylinder_indirect", "cylinder_immersion")

    def __post_init__(self) -> None:
        if self.kind not in _KINDS:
            raise ValueError(f"unknown DHW system kind {self.kind!r}")
        if self.has_tank and not self.tank_litres:
            raise ValueError(f"{self.kind} needs a tank volume")
        if not self.has_tank and self.tank_litres:
            raise ValueError(
                f"{self.kind} is instantaneous and cannot have a tank volume; "
                f"a combi's store is a storage combi, which is a cylinder"
            )
        if self.has_pv_diverter and not self.has_immersion:
            raise ValueError(
                "a PV diverter heats water through the immersion, so a "
                "dwelling cannot have one without the other"
            )
        if self.deadband_c <= 0:
            raise ValueError("a thermostat with no deadband would cycle every step")


_KINDS = (
    "cylinder_indirect", "cylinder_immersion", "combi", "instantaneous_electric",
)


@dataclasses.dataclass
class TankState:
    """Single-node tank. Stratification is not modelled, and that is declared.

    A real cylinder stratifies, and a stratified model would draw hotter water
    for longer before the thermostat saw the drop. A single node therefore
    slightly understates useful draw at the end of a long draw-off and
    slightly overstates how early reheat begins. The error is in the shape of
    one event, not in the annual energy, which is what U25 is for; 7.9's tell
    audit is the right place to revisit it.
    """

    temp_c: float
    #: Cumulative, kWh, so the energy balance can be closed per day.
    useful_draw_kwh: float = 0.0
    standby_loss_kwh: float = 0.0
    coil_input_kwh: float = 0.0
    immersion_input_kwh: float = 0.0
    diverted_pv_kwh: float = 0.0
    n_draw_events: int = 0
    litres_drawn: float = 0.0
    #: Draws the tank could not serve at temperature.
    n_unmet_draws: int = 0


@dataclasses.dataclass(frozen=True)
class DrawEvent:
    activity: str
    litres: float
    delivered_c: float
    #: True when the draw is served by an instantaneous electric appliance and
    #: must NOT be charged to the water-heating system (DEAP Section 4).
    electric_direct: bool = False


def shower_water_minutes(episode_min: float, gen: Any = None) -> float:
    """How long the water runs inside a shower_bath episode.

    Not the episode length. The episode is time in the bathroom and runs to 25
    minutes in the activity engine; the water runs for a fraction of it. The
    first version of this charged DEAP's 6 L/min across the whole episode,
    which made a 150-litre shower and put household hot water at about 800
    litres a day - six times plausible, and 70 to 85% of it showers.

    Capped by the episode, because a five-minute visit to the bathroom cannot
    contain a seven-minute shower.
    """
    a = deap_figures()["assumptions"]
    median = float(a["shower_water_minutes_median"])
    cap = float(a["shower_water_minutes_max"])
    if gen is not None:
        # Lognormal: shower length is right-skewed, and a symmetric draw
        # would put as many two-minute showers as twelve-minute ones.
        drawn = float(gen.lognormal(math.log(median), 0.35))
    else:
        drawn = median
    return max(min(drawn, cap, float(episode_min)), 0.0)


def draw_for_activity(
    activity: str,
    *,
    duration_min: float,
    n_people: int = 1,
    is_bath: bool = False,
    electric_shower: bool = False,
    gen: Any = None,
) -> DrawEvent | None:
    """The hot water one activity interval draws, or None if it draws none."""
    f = deap_figures()
    a = f["assumptions"]
    delivered = float(a["draw_temperature_c"])

    if activity == "shower_bath":
        if is_bath:
            return DrawEvent(activity, float(a["bath_volume_l"]), delivered)
        rate = float(f["demand"]["mixer_shower_minimum_l_per_min"])
        litres = rate * shower_water_minutes(duration_min, gen)
        # DEAP: an electric shower draws electricity directly, not from the
        # water-heating system. Returned as an event so the caller can see
        # the volume, flagged so it is never charged to the cylinder twice.
        return DrawEvent(activity, litres, delivered, electric_direct=electric_shower)
    if activity == "personal_care":
        # Hand and face washing, scaled by how long it went on but with a
        # floor: a basin is filled once whatever the duration.
        basins = max(1.0, float(duration_min) / 10.0)
        return DrawEvent(activity, float(a["hand_wash_l"]) * basins, delivered)
    if activity == "washing_up":
        return DrawEvent(activity, float(a["washing_up_l"]), delivered)
    if activity == "cooking":
        return DrawEvent(activity, float(a["kitchen_tap_other_l"]), delivered)
    return None


def cold_feed_temperature_c(day_of_year: int) -> float:
    """Mains water temperature, varied over the year about its mean.

    A fixed feed temperature would understate winter hot water energy and
    overstate summer, and the seasonal split is exactly what U22 will be
    looking at. The amplitude is a declared assumption; the mean is the one in
    the data file. Mains water lags air temperature, so the minimum is put at
    the end of February rather than at the solstice.
    """
    mean = float(deap_figures()["assumptions"]["cold_feed_temperature_c"])
    amplitude = 4.0
    phase_days = 59.0
    return mean - amplitude * math.cos(
        2.0 * math.pi * (float(day_of_year) - phase_days) / 365.0
    )


def standby_loss_w(system: DHWSystem, *, tank_c: float, ambient_c: float) -> float:
    """Cylinder standing loss, anchored on DEAP's 110 L / 1.672 kWh/day.

    DEAP states that pair together in Section 4.5(d), which makes it the one
    figure a modelled tank can be judged against. Two scalings are applied to
    it, both declared:

    * **volume**, as the two-thirds power rather than linearly. Loss is
      through a surface and volume grows faster than surface area, so a
      250-litre cylinder does not lose twice what a 125-litre one does.
    * **temperature**, by the actual tank-to-ambient difference against the
      difference DEAP's figure implies, times Table 2's temperature factor for
      the cylinder type. Without this the loss would not fall as the tank
      cools, and a tank left to go cold would keep losing heat it no longer
      had.
    """
    if not system.has_tank:
        return 0.0
    f = deap_figures()
    default = f["default_cylinder"]
    base_kwh_day = float(default["loss_factor_kwh_per_day"])
    base_litres = float(default["volume_l"])

    factors = f["cylinder_temperature_factors"]["values"]
    key = (
        "cylinder_immersion_main_water_heater"
        if system.kind == "cylinder_immersion" else "cylinder_indirect"
    )
    temperature_factor = float(factors[key])

    volume_scale = (float(system.tank_litres) / base_litres) ** (2.0 / 3.0)
    # DEAP's figure is a daily loss for a cylinder held at its setpoint. The
    # reference difference is taken as the setpoint over a heated-space
    # ambient, which is what a cylinder in an airing cupboard sees.
    reference_delta = system.setpoint_c - 20.0
    actual_delta = max(tank_c - ambient_c, 0.0)
    delta_scale = actual_delta / reference_delta if reference_delta > 0 else 0.0

    kwh_per_day = base_kwh_day * volume_scale * temperature_factor * delta_scale
    return kwh_per_day * 1000.0 / 24.0


def primary_circuit_loss_kwh_yr(system: DHWSystem) -> float:
    """DEAP Table 3, selected by the system's own pipework and thermostat."""
    values = deap_figures()["primary_circuit_losses_kwh_yr"]["values"]
    if system.kind == "combi":
        return float(values["combi_boiler"])
    if system.kind == "instantaneous_electric":
        return 0.0
    if system.kind == "cylinder_immersion":
        return float(values["electric_immersion_heater"])
    insulated = "insulated" if system.primary_pipework_insulated else "uninsulated"
    stat = "with" if system.has_cylinder_thermostat else "no"
    return float(values[f"boiler_{insulated}_{stat}_cylinder_thermostat"])


def combi_additional_loss_kwh_yr(
    system: DHWSystem, *, daily_litres: float, keep_hot: str = "none"
) -> float:
    """DEAP Table 3a, including its scaling below 100 litres a day.

    The scaling is not a detail. A one-person household drawing 60 litres a
    day takes 0.6 of the figure, and applying the flat 600 kWh to every combi
    would put 240 kWh a year of pure loss into every small household.
    """
    if system.kind != "combi":
        return 0.0
    block = deap_figures()["combi_additional_losses_kwh_yr"]
    values = block["values"]
    key = {
        "none": "instantaneous_without_keep_hot",
        "time_clocked": "instantaneous_keep_hot_time_clocked",
        "always": "instantaneous_keep_hot_not_time_clocked",
    }.get(keep_hot)
    if key is None:
        raise ValueError(f"unknown keep_hot mode {keep_hot!r}")
    loss = float(values[key])
    if daily_litres < 100.0:
        loss *= max(daily_litres, 0.0) / 100.0
    return loss


def _tank_volume_for_draw(
    litres: float, *, delivered_c: float, tank_c: float, cold_c: float
) -> float:
    """How much of a mixed draw comes out of the tank."""
    if tank_c <= cold_c:
        return 0.0
    if delivered_c <= cold_c:
        return 0.0
    fraction = (delivered_c - cold_c) / (tank_c - cold_c)
    return float(litres) * min(max(fraction, 0.0), 1.0)


def tank_step(
    state: TankState,
    system: DHWSystem,
    *,
    dt_s: float,
    draws: tuple[DrawEvent, ...] = (),
    ambient_c: float = 20.0,
    cold_feed_c: float = 10.0,
    pv_surplus_w: float = 0.0,
    coil_available: bool = True,
    immersion_permitted: bool = False,
) -> dict[str, Any]:
    """Advance one tank by ``dt_s``: draw, lose, then reheat.

    Order matters and is not arbitrary. Drawing before reheating is what a
    real cylinder does - the thermostat responds to the cold feed arriving,
    not in anticipation of it - and reheating first would let the tank meet a
    draw it should have failed.
    """
    if not system.has_tank:
        raise ValueError(f"{system.kind} has no tank; use instantaneous_step")
    if dt_s <= 0:
        raise ValueError("dt_s must be positive")

    mass_l = float(system.tank_litres or 0.0)
    heat_capacity = mass_l * SPECIFIC_HEAT_WATER_KWH_PER_L_K   # kWh per K
    hours = dt_s / 3600.0

    # 1. Draws.
    #
    # The energy a draw carries is referenced to the TANK temperature, not the
    # delivered one. 48 litres delivered at 40 degC from a 10 degC feed needs
    # 1.672 kWh, and all of it comes out of the tank: 28.8 litres of 60 degC
    # water times a 50 K drop. An earlier version of this multiplied the
    # tank-side volume by the DELIVERED rise instead - 28.8 litres times 30 K -
    # and recorded 1.003 kWh for a draw that actually cooled the tank by 1.672.
    # The tank-side mixing was right, so the two sides disagreed and the
    # energy-closure invariant would have caught it; the assertion at the end
    # of this function now catches it here instead.
    useful_kwh = 0.0
    temp_before = state.temp_c
    for draw in draws:
        if draw.electric_direct:
            # DEAP Section 4: charged to electricity, never to the cylinder.
            continue
        if state.temp_c <= draw.delivered_c:
            # The tank cannot reach the delivered temperature at all.
            state.n_unmet_draws += 1
            continue
        needed = _tank_volume_for_draw(
            draw.litres, delivered_c=draw.delivered_c,
            tank_c=state.temp_c, cold_c=cold_feed_c,
        )
        if needed <= 0.0:
            state.n_unmet_draws += 1
            continue
        served = min(needed, mass_l)
        if served < needed:
            # Served in part: a long draw-off that outran the cylinder.
            state.n_unmet_draws += 1
        useful_kwh += (
            served * SPECIFIC_HEAT_WATER_KWH_PER_L_K
            * (state.temp_c - cold_feed_c)
        )
        # Replacing `served` litres with cold feed mixes the tank down.
        state.temp_c += (cold_feed_c - state.temp_c) * (served / mass_l)
        state.n_draw_events += 1
        state.litres_drawn += draw.litres
    state.useful_draw_kwh += useful_kwh

    if heat_capacity > 0 and draws:
        # The draw side of the energy balance, closed before anything else
        # touches the tank: what the water carried away must equal what the
        # tank lost. This is the assertion that would have caught the 40%
        # error above at the point it was made.
        drawn_from_tank_kwh = (temp_before - state.temp_c) * heat_capacity
        if abs(drawn_from_tank_kwh - useful_kwh) > 1e-9 + 1e-6 * abs(useful_kwh):
            raise AssertionError(
                f"DHW draw energy does not close: the water carried "
                f"{useful_kwh:.6f} kWh and the tank lost "
                f"{drawn_from_tank_kwh:.6f} kWh"
            )

    # 2. Standing loss.
    loss_w = standby_loss_w(system, tank_c=state.temp_c, ambient_c=ambient_c)
    loss_kwh = loss_w * hours / 1000.0
    if heat_capacity > 0:
        state.temp_c -= loss_kwh / heat_capacity
    state.standby_loss_kwh += loss_kwh

    # 3. Reheat. The diverter runs first: surplus PV is otherwise exported for
    #    less than it is worth, so a diverter should take the tank up before
    #    any fuel is burned.
    diverted_kwh = 0.0
    if system.has_pv_diverter and pv_surplus_w > 0.0:
        headroom_k = max(system.diverter_setpoint_c - state.temp_c, 0.0)
        wanted_kwh = headroom_k * heat_capacity
        available_kwh = min(
            pv_surplus_w, system.immersion_rated_w
        ) * hours / 1000.0
        diverted_kwh = min(wanted_kwh, available_kwh)
        if heat_capacity > 0:
            state.temp_c += diverted_kwh / heat_capacity
        state.diverted_pv_kwh += diverted_kwh

    coil_kwh = 0.0
    immersion_kwh = 0.0
    if state.temp_c < system.setpoint_c - system.deadband_c:
        wanted_kwh = (system.setpoint_c - state.temp_c) * heat_capacity
        if system.kind == "cylinder_indirect" and coil_available:
            rated_kwh = system.coil_rated_w * hours / 1000.0
            coil_kwh = min(wanted_kwh, rated_kwh)
            if heat_capacity > 0:
                state.temp_c += coil_kwh / heat_capacity
        elif system.has_immersion and (
            system.kind == "cylinder_immersion" or immersion_permitted
        ):
            # For an INDIRECT cylinder the immersion is a backup the occupant
            # switches on, not an automatic fallback, and `immersion_permitted`
            # is the caller saying so. DEAP Section 4.6: "supplementary
            # electric water heating should be disregarded if provided only for
            # backup where the principal water heating system is from a central
            # heating boiler", and "Supplementary electric water heating should
            # be assumed during the summer months where operation of the main
            # water heating system results in provision of space heating."
            #
            # An earlier version reheated from the immersion whenever the coil
            # happened to be unavailable, which is a different and wrong rule:
            # it would put electric immersion load into midwinter in every home
            # whose boiler was briefly off, and it was found because the
            # draw-side energy balance in a test came out 0.07% short - the
            # immersion had quietly put heat back in.
            rated_kwh = system.immersion_rated_w * hours / 1000.0
            immersion_kwh = min(wanted_kwh, rated_kwh)
            if heat_capacity > 0:
                state.temp_c += immersion_kwh / heat_capacity
    state.coil_input_kwh += coil_kwh
    state.immersion_input_kwh += immersion_kwh

    return {
        "tank_c": state.temp_c,
        "useful_draw_kwh": useful_kwh,
        "standby_loss_kwh": loss_kwh,
        "coil_input_kwh": coil_kwh,
        "immersion_input_kwh": immersion_kwh,
        "diverted_pv_kwh": diverted_kwh,
        "immersion_w": (immersion_kwh * 1000.0 / hours) if hours else 0.0,
        "diverter_w": (diverted_kwh * 1000.0 / hours) if hours else 0.0,
    }


def instantaneous_step(
    system: DHWSystem,
    *,
    draws: tuple[DrawEvent, ...] = (),
    cold_feed_c: float = 10.0,
) -> dict[str, Any]:
    """A combi or point-of-use heater: energy follows the draw, with no store."""
    if system.has_tank:
        raise ValueError(f"{system.kind} has a tank; use tank_step")
    useful_kwh = 0.0
    electric_kwh = 0.0
    for draw in draws:
        energy = (
            draw.litres * SPECIFIC_HEAT_WATER_KWH_PER_L_K
            * max(draw.delivered_c - cold_feed_c, 0.0)
        )
        if draw.electric_direct or system.kind == "instantaneous_electric":
            electric_kwh += energy
        else:
            useful_kwh += energy
    return {
        "useful_draw_kwh": useful_kwh,
        "electric_direct_kwh": electric_kwh,
        "litres": sum(d.litres for d in draws),
    }


# --------------------------------------------------------------------------- #
# The minute kernel.
#
# A year of 50 homes is 26.3 million home-minutes, and `tank_step` is scalar
# Python. The RC physics has the same problem and solves it the same way: a
# numba kernel with ``fastmath=False``, because determinism across worker
# counts is a gate criterion (E1-2) and fastmath reorders floating-point
# operations.
#
# The kernel reproduces `tank_step`'s semantics exactly, including the order -
# draw, then standing loss, then diverter, then reheat - and
# `test_the_kernel_and_the_step_agree` holds the two to each other so the fast
# path cannot drift from the readable one.
# --------------------------------------------------------------------------- #

import numpy as np

try:
    from numba import njit

    _HAVE_NUMBA = True
except ImportError:                                  # pragma: no cover
    _HAVE_NUMBA = False

    def njit(*a, **k):                               # type: ignore[misc]
        def deco(fn):
            return fn
        return deco if not a else a[0]


@njit(cache=True, fastmath=False)
def _dhw_day_kernel(
    draw_l,                 # litres delivered per minute
    pv_surplus_w,           # surplus available to a diverter, per minute
    ambient_c,              # air around the cylinder, per minute
    tank_c0,
    tank_litres,
    heat_capacity,          # kWh per K
    loss_w_per_k,
    setpoint_c,
    deadband_c,
    diverter_setpoint_c,
    immersion_rated_w,
    coil_rated_w,
    cold_feed_c,
    delivered_c,
    has_diverter,
    immersion_allowed,
    coil_allowed,
    c_water,                # kWh per litre per K
):
    n = draw_l.shape[0]
    tank = np.empty(n, dtype=np.float64)
    immersion = np.zeros(n, dtype=np.float64)
    coil = np.zeros(n, dtype=np.float64)
    diverter = np.zeros(n, dtype=np.float64)

    t = tank_c0
    hours = 1.0 / 60.0
    useful_kwh = 0.0
    standby_kwh = 0.0
    coil_kwh = 0.0
    immersion_kwh = 0.0
    diverted_kwh = 0.0
    unmet = 0
    litres = 0.0

    for i in range(n):
        # 1. draw
        v = draw_l[i]
        if v > 0.0:
            litres += v
            if t <= delivered_c:
                unmet += 1
            else:
                frac = (delivered_c - cold_feed_c) / (t - cold_feed_c)
                if frac < 0.0:
                    frac = 0.0
                elif frac > 1.0:
                    frac = 1.0
                needed = v * frac
                served = needed
                if served > tank_litres:
                    served = tank_litres
                    unmet += 1
                useful_kwh += served * c_water * (t - cold_feed_c)
                t += (cold_feed_c - t) * (served / tank_litres)

        # 2. standing loss
        delta = t - ambient_c[i]
        if delta < 0.0:
            delta = 0.0
        loss_w = loss_w_per_k * delta
        lk = loss_w * hours / 1000.0
        t -= lk / heat_capacity
        standby_kwh += lk

        # 3. diverter, before any fuel is burned
        if has_diverter and pv_surplus_w[i] > 0.0:
            headroom = diverter_setpoint_c - t
            if headroom > 0.0:
                want = headroom * heat_capacity
                avail_w = pv_surplus_w[i]
                if avail_w > immersion_rated_w:
                    avail_w = immersion_rated_w
                avail = avail_w * hours / 1000.0
                got = want if want < avail else avail
                t += got / heat_capacity
                diverted_kwh += got
                diverter[i] = got * 1000.0 / hours

        # 4. reheat
        if t < setpoint_c - deadband_c:
            want = (setpoint_c - t) * heat_capacity
            if coil_allowed:
                rated = coil_rated_w * hours / 1000.0
                got = want if want < rated else rated
                t += got / heat_capacity
                coil_kwh += got
                coil[i] = got * 1000.0 / hours
            elif immersion_allowed:
                rated = immersion_rated_w * hours / 1000.0
                got = want if want < rated else rated
                t += got / heat_capacity
                immersion_kwh += got
                immersion[i] = got * 1000.0 / hours

        tank[i] = t

    return (tank, immersion, coil, diverter,
            useful_kwh, standby_kwh, coil_kwh, immersion_kwh, diverted_kwh,
            float(unmet), litres)


#: Activities that draw hot water, and whether the draw is one-per-occurrence
#: or scales with how long it went on.
DRAW_ACTIVITIES = ("shower_bath", "personal_care", "washing_up", "cooking")


def draw_schedule(
    intervals: Any,
    *,
    n_minutes: int = 1440,
    bath_fraction: float = 0.15,
    electric_shower: bool = False,
    gen: Any = None,
) -> np.ndarray:
    """Litres per minute from the day's activity intervals.

    Draws are spread across the minutes of the activity rather than dropped on
    its first minute. A shower genuinely runs for its duration, and putting 48
    litres into one minute would create a 100 kW instantaneous reheat demand
    that no cylinder or feeder would ever see - the sort of artefact 7.9's tell
    audit exists to catch.

    ``bath_fraction`` is a declared assumption: the share of shower_bath
    occurrences taken as a bath rather than a shower. DEAP distinguishes the
    two and publishes no split, and U30 found nothing in PxStat.
    """
    out = np.zeros(int(n_minutes), dtype=np.float64)
    for iv in intervals:
        if getattr(iv, "location_kind", "building") != "building":
            continue
        activity = getattr(iv, "activity", "")
        if activity not in DRAW_ACTIVITIES:
            continue
        start = max(int(iv.start_min), 0)
        end = min(int(iv.end_min), int(n_minutes))
        if end <= start:
            continue
        duration = float(end - start)
        is_bath = False
        if activity == "shower_bath" and gen is not None:
            is_bath = bool(gen.random() < bath_fraction)
        event = draw_for_activity(
            activity, duration_min=duration, is_bath=is_bath,
            electric_shower=electric_shower, gen=gen,
        )
        if event is None or event.electric_direct:
            # An electric shower is an electrical load, not a tank draw
            # (DEAP Section 4). The appliance layer already carries it.
            continue
        if activity == "shower_bath" and is_bath:
            # A bath is run over a few minutes at the start, not over the
            # whole time someone spends in the bathroom.
            fill = min(int(duration), 8)
            out[start:start + max(fill, 1)] += event.litres / max(fill, 1)
        elif activity == "shower_bath":
            # Spread over the minutes the water actually runs, at the start of
            # the episode: people shower and then dry, not the other way
            # round. Dropping the whole volume on one minute would create a
            # reheat spike no cylinder or feeder would ever see.
            running = max(int(round(event.litres / 6.0)), 1)
            running = min(running, int(duration))
            out[start:start + running] += event.litres / running
        else:
            out[start:end] += event.litres / duration
    return out


def simulate_dhw_day(
    system: DHWSystem,
    state: TankState,
    *,
    draw_l: np.ndarray,
    pv_surplus_w: np.ndarray | None = None,
    ambient_c: np.ndarray | float = 20.0,
    day_of_year: int = 1,
    immersion_permitted: bool = False,
    coil_available: bool = True,
    immersion_available: bool = True,
) -> dict[str, Any]:
    """One day of one cylinder, at minute resolution, advancing ``state``.

    ``immersion_available`` is how an appliance-failure disruption reaches the
    hot water. The immersion used to be an appliance, so a failure of it was a
    failure of a load; now that the cylinder owns it, a failure has to reach
    the cylinder or the disruption would do nothing at all - and for an
    immersion-fed cylinder it means no hot water, which is the whole point of
    simulating a disruption.
    """
    if not system.has_tank:
        raise ValueError(f"{system.kind} has no tank; use instantaneous_step")
    n = int(draw_l.shape[0])
    mass = float(system.tank_litres or 0.0)
    heat_capacity = mass * SPECIFIC_HEAT_WATER_KWH_PER_L_K

    f = deap_figures()
    default = f["default_cylinder"]
    factors = f["cylinder_temperature_factors"]["values"]
    key = (
        "cylinder_immersion_main_water_heater"
        if system.kind == "cylinder_immersion" else "cylinder_indirect"
    )
    volume_scale = (mass / float(default["volume_l"])) ** (2.0 / 3.0)
    reference_delta = system.setpoint_c - 20.0
    loss_w_per_k = (
        float(default["loss_factor_kwh_per_day"]) * 1000.0 / 24.0
        * volume_scale * float(factors[key]) / reference_delta
    )

    amb = (
        np.full(n, float(ambient_c), dtype=np.float64)
        if np.isscalar(ambient_c) else np.asarray(ambient_c, dtype=np.float64)
    )
    pv = (
        np.zeros(n, dtype=np.float64) if pv_surplus_w is None
        else np.asarray(pv_surplus_w, dtype=np.float64)
    )
    cold = cold_feed_temperature_c(day_of_year)
    delivered = float(f["assumptions"]["draw_temperature_c"])

    coil_allowed = bool(coil_available and system.kind == "cylinder_indirect")
    immersion_allowed = bool(
        system.has_immersion and immersion_available
        and (system.kind == "cylinder_immersion" or immersion_permitted)
    )
    diverter_allowed = bool(
        system.has_pv_diverter and immersion_available
    )

    (tank, immersion_w, coil_w, diverter_w, useful, standby, coil_kwh,
     imm_kwh, div_kwh, unmet, litres) = _dhw_day_kernel(
        np.ascontiguousarray(draw_l, dtype=np.float64),
        np.ascontiguousarray(pv, dtype=np.float64),
        np.ascontiguousarray(amb, dtype=np.float64),
        float(state.temp_c), mass, heat_capacity, loss_w_per_k,
        float(system.setpoint_c), float(system.deadband_c),
        float(system.diverter_setpoint_c), float(system.immersion_rated_w),
        float(system.coil_rated_w), float(cold), delivered,
        diverter_allowed, immersion_allowed, coil_allowed,
        SPECIFIC_HEAT_WATER_KWH_PER_L_K,
    )

    state.temp_c = float(tank[-1])
    state.useful_draw_kwh += float(useful)
    state.standby_loss_kwh += float(standby)
    state.coil_input_kwh += float(coil_kwh)
    state.immersion_input_kwh += float(imm_kwh)
    state.diverted_pv_kwh += float(div_kwh)
    state.n_unmet_draws += int(unmet)
    state.litres_drawn += float(litres)

    return {
        "tank_c": tank,
        "immersion_w": immersion_w,
        "coil_heat_w": coil_w,
        "diverter_w": diverter_w,
        "useful_draw_kwh": float(useful),
        "standby_loss_kwh": float(standby),
        "coil_input_kwh": float(coil_kwh),
        "immersion_input_kwh": float(imm_kwh),
        "diverted_pv_kwh": float(div_kwh),
        "litres": float(litres),
        "n_unmet": int(unmet),
        "cold_feed_c": float(cold),
    }


def dhw_system_for(building: Any, *, has_pv: bool = False) -> DHWSystem | None:
    """The hot water system a dwelling has, from its own fabric and era.

    Returns ``None`` for a dwelling the model has no water-heating story for,
    rather than inventing one.

    The assignments are declared, and the reasoning is the point of writing it
    out rather than burying it in branches:

    * **A gas or oil boiler** gets an indirect cylinder with an immersion
      backup, which is the ordinary Irish arrangement. Whether the primary
      pipework is insulated and whether there is a cylinder thermostat are
      taken from the era, because that is what DEAP Table 3's rows distinguish
      and both roughly quadruple the loss when absent (360 against 1,220
      kWh/yr). DEAP's own instruction is that hidden pipework must be assumed
      **uninsulated** unless it can be proven otherwise, so the older stock
      takes the worse figures rather than the better ones.
    * **Direct electric and storage heaters** get an immersion-fed cylinder,
      since there is no wet circuit to heat one indirectly.
    * **A heat pump** gets an indirect cylinder too - DEAP's Table 3 rows say
      "boiler / heat pump" - but at a lower setpoint, because a heat pump's
      COP falls as the flow temperature rises and 60 degC is punishing for one.
    * **Solid fuel** gets a cylinder only where there is a back boiler; a stove
      with no back boiler heats no water, and a dwelling like that genuinely
      has an immersion and nothing else.

    ``has_pv`` enables the diverter rather than assuming it: a diverter is a
    device somebody buys, and only a home with PV has any reason to.
    """
    fuel = str(getattr(building, "heating_fuel", "") or "").lower()
    system = str(getattr(building, "heating_system", "") or "").lower()
    year = int(getattr(building, "build_year", 1980) or 1980)
    notes = getattr(building, "notes", {}) or {}
    litres = notes.get("dhw_tank_litres")

    # Modern construction: insulated primary pipework and a cylinder
    # thermostat are both regulatory expectations by then.
    insulated = year >= 1991
    thermostat = year >= 1979

    if "heat pump" in system:
        return DHWSystem(
            kind="cylinder_indirect",
            tank_litres=float(litres or 180.0),
            has_cylinder_thermostat=True,
            primary_pipework_insulated=True,
            has_immersion=True,
            has_pv_diverter=bool(has_pv),
            # A heat pump pays for every extra kelvin of flow temperature in
            # COP, so a heat-pump cylinder is run cooler and larger.
            setpoint_c=50.0,
            coil_rated_w=6000.0,
        )
    if "district" in fuel or "district" in system or "community" in system:
        # DEAP Section 4.5 covers this case and gives the fallback explicitly:
        # "the calculation should assume that the dwelling has a cylinder of
        # 110 litres and loss factor of 1.672 kWh/day. Primary circuit loss
        # for insulated pipework and cylinder thermostat should be included".
        # So this is not a gap - the transcribed default_cylinder block IS the
        # rule for it.
        default = deap_figures()["default_cylinder"]
        return DHWSystem(
            kind="cylinder_indirect",
            tank_litres=float(litres or default["volume_l"]),
            has_cylinder_thermostat=True,
            primary_pipework_insulated=True,
            has_immersion=True,
            has_pv_diverter=bool(has_pv),
        )
    # LPG is a gas boiler: DEAP Table 4b's heading is "Gas boilers (including
    # LPG)". An earlier version tested for "gas" in the fuel string and so
    # left every LPG dwelling with no water heating at all, which the town's
    # own fuel census caught - 4 of 1,092.
    if "gas" in fuel or "lpg" in fuel or "oil" in fuel:
        return DHWSystem(
            kind="cylinder_indirect",
            tank_litres=float(litres or 150.0),
            has_cylinder_thermostat=thermostat,
            primary_pipework_insulated=insulated,
            has_immersion=True,
            has_pv_diverter=bool(has_pv),
        )
    if "solid fuel" in system or "stove" in system:
        if not litres:
            # No back boiler and no tank: the immersion is all there is.
            return DHWSystem(
                kind="cylinder_immersion", tank_litres=120.0,
                has_pv_diverter=bool(has_pv),
            )
        return DHWSystem(
            kind="cylinder_indirect", tank_litres=float(litres),
            has_cylinder_thermostat=thermostat,
            primary_pipework_insulated=insulated,
            has_pv_diverter=bool(has_pv),
        )
    if "electric" in fuel or "storage" in system:
        return DHWSystem(
            kind="cylinder_immersion",
            tank_litres=float(litres or 120.0),
            has_pv_diverter=bool(has_pv),
        )
    return None


def immersion_permitted_on(day_of_year: int) -> bool:
    """DEAP 4.6's summer rule, as a date test.

    *"Supplementary electric water heating should be assumed during the summer
    months where operation of the main water heating system results in
    provision of space heating."* Outside the heating season a boiler run for
    hot water also heats a house that does not want heating, so the immersion
    is used instead. May to September inclusive, which is the Irish
    non-heating season; the boundary months are the declared part.
    """
    # Day-of-year boundaries for 1 May and 30 September in a non-leap year.
    return 121 <= int(day_of_year) <= 273


#: The cooking-fuel mix a dwelling can be assigned.
COOKING_FUELS = ("electricity", "natural gas", "gas hob electric oven")


@functools.lru_cache(maxsize=1)
def cooking_fuel_shares() -> dict[str, Any]:
    """Cooking fuel conditional on a gas connection, from published data.

    This was a declared assumption of 0.45 until U30's coverage test forced
    the search that found the tables. The derivation, and its two caveats:

    **HEBEU34** gives the unconditional urban share by main cooking fuel, and
    **HEBEU106** the urban share by main heating fuel, from the same survey
    and year. The model needs the share CONDITIONAL on having a gas supply -
    an oil-heated house in Cobh has no gas to cook on - so:

        P(cooks with gas | connected) = P(cooks with gas) / P(gas connected)

    *Caveat one.* P(gas connected) is taken as the share heating with natural
    gas. A dwelling can be connected for cooking alone, so that is a LOWER
    bound on connections and the derived conditional share is therefore an
    UPPER bound. Stated rather than hidden: it biases gas cooking up, which
    biases the gas-meter comparison up, which is the direction that would be
    caught by DBERNG01 rather than concealed by it.

    *Caveat two.* The tables are 2024 and T0 is 2022. Used for a structural
    share and not a level, which is the PL-AREA-01 lesson.

    The three-way split is the part worth having. "Combination of electricity
    and gas" is not noise - it is the common arrangement of a gas hob with an
    electric oven, and the model already prices hob and oven separately.
    """
    import itertools
    import json

    from baile_nua.sources import REGISTRY, require

    def read(key: str) -> tuple[list[str], dict[str, list[str]], dict]:
        doc = json.loads(require(key).read_text(encoding="utf-8"))
        ids = doc["id"]
        labels = {
            i: list(doc["dimension"][i]["category"]["label"].values())
            for i in ids
        }
        values = doc["value"]
        cells = {
            combo: (values[k] if isinstance(values, list)
                    else values.get(str(k)))
            for k, combo in enumerate(
                itertools.product(*[labels[i] for i in ids])
            )
        }
        return ids, labels, cells

    def urban_share(key: str, fuel_match: str) -> float:
        ids, labels, cells = read(key)
        loc_dim = next(
            i for i in ids
            if any(str(v).startswith("Urban") for v in labels[i])
        )
        fuel_dim = next(
            i for i in ids
            if i != loc_dim and len(labels[i]) > 1
            and any("gas" in str(v).lower() for v in labels[i])
        )
        loc = next(v for v in labels[loc_dim] if str(v).startswith("Urban"))
        total = 0.0
        for fuel in labels[fuel_dim]:
            if fuel_match.lower() not in str(fuel).lower():
                continue
            key_t = tuple(
                loc if i == loc_dim else (fuel if i == fuel_dim else labels[i][0])
                for i in ids
            )
            v = cells.get(key_t)
            if v is not None:
                total += float(v)
        return total

    cook_key = "cso.cooking.hebeu34_cooking_fuel_urban_rural"
    heat_key = "cso.cooking.hebeu106_heating_fuel_urban_rural"

    gas_only = urban_share(cook_key, "Natural gas")
    combination = urban_share(cook_key, "Combination of electricity and gas")
    connected = urban_share(heat_key, "Natural gas")
    if connected <= 0:
        raise LookupError(f"{heat_key} gives no urban natural-gas share")

    p_gas_only = min(gas_only / connected, 1.0)
    p_combination = min(combination / connected, 1.0 - p_gas_only)
    return {
        "natural gas": p_gas_only,
        "gas hob electric oven": p_combination,
        "electricity": max(1.0 - p_gas_only - p_combination, 0.0),
        "_derivation": {
            "unconditional_cooks_with_gas_only_pct": gas_only,
            "unconditional_cooks_with_combination_pct": combination,
            "urban_gas_heated_pct_as_connection_proxy": connected,
            "sources": [cook_key, heat_key],
            "shas": [
                json.loads(
                    REGISTRY[k].manifest_path.read_text(encoding="utf-8")
                )["sha256"][:12]
                for k in (cook_key, heat_key)
            ],
            "caveat_upper_bound": (
                "The denominator is the share HEATING with natural gas, which "
                "is a lower bound on connections, so these conditional shares "
                "are upper bounds. That biases gas cooking up and so biases "
                "the gas-meter comparison up, which DBERNG01 would catch."
            ),
            "caveat_vintage": "Tables are 2024; T0 is 2022.",
            "replaced": (
                "a declared assumption of 0.45 for the combined gas share. "
                "The data gives "
                f"{(gas_only + combination) / connected:.3f}, which is close "
                "enough to be reassuring and sourced enough to keep."
            ),
        },
    }


def cooking_fuel_for(building: Any, gen: Any) -> str:
    """One of :data:`COOKING_FUELS`, drawn once per dwelling.

    Conditioned on having a gas supply rather than drawn independently: an
    oil-heated house in Cobh has no gas to cook on.
    """
    fuel = str(getattr(building, "heating_fuel", "") or "").lower()
    if "natural gas" not in fuel and "lpg" not in fuel:
        return "electricity"
    shares = cooking_fuel_shares()
    u = float(gen.random())
    if u < shares["natural gas"]:
        return "natural gas"
    if u < shares["natural gas"] + shares["gas hob electric oven"]:
        return "gas hob electric oven"
    return "electricity"
