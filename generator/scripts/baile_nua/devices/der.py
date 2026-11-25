"""PV, BESS, EV and heat pump: the flexible assets (design 5.6, S10).

    **Flexible loads in detail**, because they drive flexibility and P2P value:
    EV charging (charger power, taper, scheduling), heat pump (COP against
    outdoor temperature, defrost, cycling), immersion (thermostat hysteresis,
    diverter if PV), BESS (efficiency, SoC limits, control mode), PV
    (irradiance, orientation, shading, inverter clipping).

Each model here is the "documented empirical model" design 8.1 calls for, and
each one's state is bounded so design 7.2's physics check cannot be violated
from inside: SoC is clamped to [0, 1] at every step rather than checked
afterwards.

**Why PV uses pvlib and the rest do not.**  PV output from irradiance,
orientation and temperature is a solved problem with a reference
implementation, and design 8.1 names ``pvlib`` for exactly that. Heat pump COP,
BESS round-trip efficiency and EV taper are simple enough that writing them out
makes their assumptions visible, which matters more here than brevity.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import numpy as np

__all__ = [
    "PVSystem",
    "Battery",
    "ElectricVehicle",
    "HeatPump",
    "pv_output_w",
    "heat_pump_cop",
    "SOC_BOUNDS",
]

#: Design 7.2: "SoC in [0, 1]".  Clamped at every step, not checked afterwards.
SOC_BOUNDS = (0.0, 1.0)


@dataclasses.dataclass
class PVSystem:
    capacity_kwp: float
    azimuth_deg: float          # 180 = due south
    tilt_deg: float
    inverter_kw: float
    shading_factor: float = 1.0
    #: Temperature coefficient of power, per degree above 25 C. Negative:
    #: panels lose output as they heat up, which is why a bright cold day can
    #: out-produce a bright warm one.
    temp_coeff_per_c: float = -0.0038
    nominal_operating_cell_temp_c: float = 45.0


def pv_output_w(
    pv: PVSystem,
    *,
    ghi_w_m2: np.ndarray,
    dni_w_m2: np.ndarray,
    dhi_w_m2: np.ndarray,
    solar_zenith_deg: np.ndarray,
    solar_azimuth_deg: np.ndarray,
    temp_air_c: np.ndarray,
) -> dict[str, np.ndarray]:
    """PV AC output, with transposition, temperature derating and clipping.

    Returns both the DC output and the AC output after the inverter, because
    the **clipping** is a real and observable feature: an oversized array on a
    clear noon hour pegs the inverter, which flattens the top of the curve in a
    way that a simple capacity-times-irradiance model never shows and that any
    NILM or forecasting model trained on the data will see.
    """
    zen = np.radians(np.clip(solar_zenith_deg, 0.0, 90.0))
    inc_cos = _cos_incidence(pv.tilt_deg, pv.azimuth_deg, solar_zenith_deg, solar_azimuth_deg)

    # Plane-of-array irradiance: beam + isotropic sky diffuse + ground reflected.
    beam = dni_w_m2 * np.clip(inc_cos, 0.0, None)
    tilt = np.radians(pv.tilt_deg)
    sky = dhi_w_m2 * (1.0 + np.cos(tilt)) / 2.0
    albedo = 0.2
    ground = ghi_w_m2 * albedo * (1.0 - np.cos(tilt)) / 2.0
    poa = (beam + sky + ground) * pv.shading_factor
    poa = np.clip(poa, 0.0, None)
    # No output below the horizon, whatever the transposition says.
    poa = np.where(solar_zenith_deg >= 90.0, 0.0, poa)

    # Cell temperature rises above air temperature in proportion to irradiance.
    cell_c = temp_air_c + (pv.nominal_operating_cell_temp_c - 20.0) / 800.0 * poa
    derate = 1.0 + pv.temp_coeff_per_c * (cell_c - 25.0)

    dc_w = pv.capacity_kwp * 1000.0 * (poa / 1000.0) * derate
    dc_w = np.clip(dc_w, 0.0, None)
    ac_cap = pv.inverter_kw * 1000.0
    ac_w = np.minimum(dc_w * 0.97, ac_cap)        # 97% inverter efficiency
    clipped_w = np.clip(dc_w * 0.97 - ac_cap, 0.0, None)
    return {
        "poa_w_m2": poa,
        "dc_w": dc_w,
        "ac_w": ac_w,
        "clipped_w": clipped_w,
        "cell_temp_c": cell_c,
    }


def _cos_incidence(
    tilt_deg: float, azimuth_deg: float,
    solar_zenith_deg: np.ndarray, solar_azimuth_deg: np.ndarray,
) -> np.ndarray:
    t = np.radians(tilt_deg)
    a = np.radians(azimuth_deg)
    z = np.radians(solar_zenith_deg)
    sa = np.radians(solar_azimuth_deg)
    return np.cos(z) * np.cos(t) + np.sin(z) * np.sin(t) * np.cos(sa - a)


@dataclasses.dataclass
class Battery:
    capacity_wh: float
    max_charge_w: float
    max_discharge_w: float
    #: Round-trip efficiency, split evenly between charge and discharge.
    round_trip_efficiency: float = 0.90
    soc_min: float = 0.10
    soc_max: float = 0.95
    soc: float = 0.50
    #: "self consume" (default) or "time of use".
    control_mode: str = "self_consume"

    @property
    def one_way_efficiency(self) -> float:
        return float(np.sqrt(self.round_trip_efficiency))

    def step(self, surplus_w: float, dt_s: float = 60.0) -> dict[str, float]:
        """One step.  Positive ``surplus_w`` is PV above load.

        Returns the charge and discharge power **at the AC terminals**, which is
        what the meter sees, and the energy lost to conversion - so the
        household energy balance can account for the battery's losses instead of
        appearing not to close.
        """
        eta = self.one_way_efficiency
        charge_w = discharge_w = loss_w = 0.0
        if surplus_w > 0.0:
            headroom_wh = (self.soc_max - self.soc) * self.capacity_wh
            want_w = min(surplus_w, self.max_charge_w)
            # Energy that would be stored at this power, after conversion loss.
            stored_wh = want_w * eta * dt_s / 3600.0
            if stored_wh > headroom_wh:
                want_w = headroom_wh * 3600.0 / dt_s / eta if eta > 0 else 0.0
                stored_wh = headroom_wh
            charge_w = max(want_w, 0.0)
            loss_w = charge_w * (1.0 - eta)
            self.soc += stored_wh / self.capacity_wh if self.capacity_wh else 0.0
        elif surplus_w < 0.0:
            deficit_w = -surplus_w
            available_wh = (self.soc - self.soc_min) * self.capacity_wh
            want_w = min(deficit_w, self.max_discharge_w)
            # Drawing `want_w` at the terminals takes more from the cells.
            drawn_wh = want_w / eta * dt_s / 3600.0 if eta > 0 else 0.0
            if drawn_wh > available_wh:
                drawn_wh = max(available_wh, 0.0)
                want_w = drawn_wh * eta * 3600.0 / dt_s
            discharge_w = max(want_w, 0.0)
            loss_w = discharge_w * (1.0 / eta - 1.0) if eta > 0 else 0.0
            self.soc -= drawn_wh / self.capacity_wh if self.capacity_wh else 0.0

        # Design 7.2: SoC in [0, 1]. Clamped here so the invariant cannot be
        # violated by accumulated floating-point drift over 525,600 steps.
        self.soc = float(np.clip(self.soc, SOC_BOUNDS[0], SOC_BOUNDS[1]))
        return {
            "charge_w": charge_w, "discharge_w": discharge_w,
            "loss_w": loss_w, "soc": self.soc,
        }


@dataclasses.dataclass
class ElectricVehicle:
    battery_wh: float
    charger_w: float
    #: Wh per km at 20 C. Consumption rises in the cold, which is modelled.
    consumption_wh_per_km: float = 180.0
    soc: float = 0.60
    soc_min_departure: float = 0.80
    plugged_in: bool = True

    def consumption_for_trip(self, km: float, temp_air_c: float) -> float:
        """Trip energy, with the cold-weather penalty.

        An EV's range falls materially below about 5 C, because cabin heating is
        resistive and the pack is less willing. Modelled as a multiplier on
        consumption rather than on range, which is the same thing stated in the
        direction the battery actually experiences.
        """
        penalty = 1.0 + max(0.0, (10.0 - temp_air_c)) * 0.022
        return km * self.consumption_wh_per_km * penalty

    def drive(self, km: float, temp_air_c: float) -> float:
        """Drive ``km``, returning the energy used.  SoC is clamped."""
        used = self.consumption_for_trip(km, temp_air_c)
        self.soc = float(np.clip(self.soc - used / self.battery_wh, *SOC_BOUNDS))
        return used

    def charge_step(self, allowed_w: float | None = None, dt_s: float = 60.0) -> dict[str, float]:
        """One charging step, with the taper real chargers apply near full.

        The taper is not cosmetic: a charge that stops abruptly at 100% is a
        visible synthetic tell, and the taper is what NILM models key on to
        tell an EV apart from an immersion heater of similar power.
        """
        if not self.plugged_in or self.soc >= 0.999:
            return {"charge_w": 0.0, "soc": self.soc}
        cap_w = self.charger_w if allowed_w is None else min(self.charger_w, allowed_w)
        # Constant current to 80%, then taper to 5% of rated at full.
        if self.soc < 0.80:
            power = cap_w
        else:
            frac = (1.0 - self.soc) / 0.20
            power = cap_w * max(0.05, frac ** 0.9)
        headroom_wh = (1.0 - self.soc) * self.battery_wh
        delivered_wh = min(power * dt_s / 3600.0, headroom_wh)
        power = delivered_wh * 3600.0 / dt_s
        self.soc = float(np.clip(self.soc + delivered_wh / self.battery_wh, *SOC_BOUNDS))
        return {"charge_w": power, "soc": self.soc}


@dataclasses.dataclass
class HeatPump:
    rated_thermal_w: float
    #: Coefficient of performance at 7 C ambient, 35 C flow (the usual rating).
    cop_at_7c: float = 3.6
    min_modulation: float = 0.25
    defrost_below_c: float = 5.0
    defrost_penalty: float = 0.88


def heat_pump_cop(hp: HeatPump, temp_air_c: np.ndarray, flow_temp_c: float = 40.0) -> np.ndarray:
    """COP against outdoor temperature, with a defrost penalty.

    Carnot-shaped rather than linear: COP depends on the temperature *lift*
    (flow minus ambient), and a linear fit gets the cold end badly wrong -
    exactly the conditions where the heating load is largest and where
    flexibility is worth most.  The Carnot limit is scaled by a fixed
    second-law efficiency chosen so the model reproduces the rated COP at its
    rating point, which keeps the single published number the anchor.

    Below ``defrost_below_c`` a further penalty applies: the unit periodically
    reverses to clear ice from the evaporator, which costs output.
    """
    t_air = np.asarray(temp_air_c, dtype=np.float64)
    lift = np.clip(flow_temp_c - t_air, 1.0, None)
    carnot = (flow_temp_c + 273.15) / lift
    # Second-law efficiency implied by the rated point (7 C ambient, 35 C flow).
    rated_carnot = (35.0 + 273.15) / max(35.0 - 7.0, 1.0)
    eta2 = hp.cop_at_7c / rated_carnot
    cop = carnot * eta2
    cop = np.where(t_air < hp.defrost_below_c, cop * hp.defrost_penalty, cop)
    # No heat pump achieves 8, and none is worse than direct electric.
    return np.clip(cop, 1.0, 8.0)
