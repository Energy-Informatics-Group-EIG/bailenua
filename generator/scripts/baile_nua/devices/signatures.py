"""The appliance signature library, D22 (design 5.6, U05, risk K07).

    **Signature library.**  Each cycle references a signature from a library
    built from public sub-metered datasets (UK-DALE, REFIT, REDD, IDEAL; U05).
    Signatures have model-to-model and age-related variation, so two kettles are
    never identical.

**Status, stated plainly.**  The public sub-metered datasets named in U05 are
**not** ingested in this build: UK-DALE and REFIT are large downloads whose
licences U05 itself defers to WP1, and E1 is engineering verification rather
than signature fidelity.  The library here is therefore a **parameterised
template library** - each template is a piecewise power profile with declared
parameters - and every signature carries ``source_dataset =
'synthetic-template'`` and ``evidence_status = '[A]'`` in D22, so nothing
downstream can mistake it for a measured waveform.

Risk K07 already records that the signature library is the weakest link
("too small or too UK-centric for Irish appliances"), and the Irish-specific
loads the design names - electric showers, immersion heaters, storage heaters -
are flagged ``irish_specific`` so the gap is visible per appliance rather than
as a general caveat.

**What the templates do get right**, because the energy-closure invariant
depends on it: a template's integral is its declared energy, exactly. The 1 Hz
rendering is a *shape* applied to a known energy, so a rendered cycle can never
disagree with the cycle's recorded ``energy_wh`` - which is what makes design
7.2's 0.1% closure achievable at all.
"""

from __future__ import annotations

import dataclasses
import math
from typing import Any

import numpy as np

__all__ = [
    "Signature",
    "SIGNATURE_LIBRARY",
    "render_cycle",
    "signature_for",
    "D22_rows",
]


@dataclasses.dataclass(frozen=True)
class Signature:
    """One appliance template.

    ``shape`` is a list of ``(fraction_of_duration, relative_power)`` knots.
    Power is relative, so the template is scaled to the cycle's rated power and
    then normalised so its integral equals the cycle's energy exactly.
    """

    signature_id: str
    appliance_type: str
    programme: str
    nominal_duration_s: int
    nominal_energy_wh: float
    peak_w: float
    shape: tuple[tuple[float, float], ...]
    #: Model-to-model spread, as a coefficient of variation.
    var_power_cv: float
    var_duration_cv: float
    #: Fractional power increase per year of age (a worn element draws more).
    ageing_power_per_year: float
    irish_specific: bool
    #: Whether a controller can move or modulate this load (design 5.6).
    flexible: bool
    controllable_live: bool = False
    notes: str = ""


def _flat(level: float = 1.0) -> tuple[tuple[float, float], ...]:
    return ((0.0, level), (1.0, level))


#: The library.  Irish-specific loads the design names explicitly are present
#: and flagged: electric shower, immersion heater, storage heater, tumble dryer.
SIGNATURE_LIBRARY: dict[str, Signature] = {
    # -- wet goods: distinctive multi-phase profiles -----------------------
    "washer_eco40": Signature(
        "SIG-WASH-ECO40", "washing_machine", "eco 40-60", 10_800, 925.8, 2100.0,
        # fill, heat (the big block), wash, rinses, spin.
        # The heat block is 7% of a 3-hour cycle, about 13 minutes at 2.1 kW,
        # which is what gets an eco-40 cycle to its ~0.74 kWh. An earlier
        # version held full power for 17% of the cycle and implied 2.2 kWh -
        # three times a real eco-40 - which the energy-consistency assertion
        # caught.
        ((0.00, 0.03), (0.04, 0.03), (0.05, 1.00), (0.12, 1.00), (0.14, 0.03),
         (0.62, 0.03), (0.64, 0.08), (0.78, 0.04), (0.88, 0.22), (0.97, 0.22),
         (1.00, 0.02)),
        0.12, 0.10, 0.004,
        irish_specific=False, flexible=True, controllable_live=False,
        notes="The heating block is what makes a washer identifiable to NILM.",
    ),
    "washer_quick": Signature(
        "SIG-WASH-QUICK", "washing_machine", "quick 30", 1_800, 491.2, 2100.0,
        ((0.00, 0.08), (0.06, 1.00), (0.30, 1.00), (0.34, 0.10), (0.70, 0.10),
         (0.80, 0.55), (0.98, 0.55), (1.00, 0.04)),
        0.12, 0.12, 0.004,
        irish_specific=False, flexible=True, controllable_live=False,
    ),
    "dryer_condenser": Signature(
        "SIG-DRY-COND", "tumble_dryer", "cottons", 7_200, 3365.4, 2700.0,
        # A condenser dryer modulates: the heater duty-cycles down as the load
        # dries, so the mean is around half the peak rather than near it.
        ((0.00, 0.95), (0.25, 0.95), (0.55, 0.52), (0.85, 0.35), (0.95, 0.20),
         (1.00, 0.08)),
        0.10, 0.14, 0.005,
        irish_specific=True, flexible=True, controllable_live=False,
        notes="Irish-relevant: high tumble-dryer use follows a wet climate.",
    ),
    "dishwasher_eco": Signature(
        "SIG-DISH-ECO", "dishwasher", "eco 50", 12_600, 896.7, 2100.0,
        # Two heat blocks (main wash and final rinse), each short, which is what
        # keeps an eco-50 cycle near its ~0.9 kWh over 3.5 hours.
        ((0.000, 0.04), (0.030, 1.00), (0.040, 1.00), (0.060, 0.03),
         (0.550, 0.03), (0.580, 0.95), (0.586, 0.95), (0.626, 0.03),
         (0.920, 0.14), (1.000, 0.02)),
        0.10, 0.08, 0.004,
        irish_specific=False, flexible=True, controllable_live=False,
    ),
    # -- kitchen: short, sharp, frequent ----------------------------------
    "kettle_1l5": Signature(
        "SIG-KETTLE", "kettle", "1.5 L", 150, 116.7, 2800.0, _flat(1.0),
        0.07, 0.18, 0.002,
        irish_specific=False, flexible=False, controllable_live=False,
        notes="Near-rectangular; the classic NILM test case.",
    ),
    "toaster": Signature(
        "SIG-TOAST", "toaster", "medium", 180, 55.0, 1100.0, _flat(1.0),
        0.09, 0.20, 0.002,
        irish_specific=False, flexible=False, controllable_live=False,
    ),
    "microwave": Signature(
        "SIG-MICRO", "microwave", "reheat", 180, 59.4, 1250.0,
        ((0.0, 1.0), (0.5, 1.0), (0.52, 0.0), (0.6, 1.0), (1.0, 1.0)),
        0.08, 0.25, 0.002,
        irish_specific=False, flexible=False, controllable_live=False,
        notes="Duty-cycles its magnetron, so the profile is chopped.",
    ),
    "oven_bake": Signature(
        "SIG-OVEN", "oven", "bake 180C", 3_600, 1153.0, 2400.0,
        # Thermostat cycling after the initial heat-up.
        #
        # A thermostat SWITCHES; it does not ramp. The first version placed its
        # turning points far apart - (0.20, 0.10) then (0.30, 1.00) - and the
        # shape is linearly interpolated, so the element spent the whole 10% of
        # the cycle sliding between off and full and averaged 0.55 across it.
        # The shape's mean came out at 0.63 of rating, which made a one-hour
        # bake 1.51 kWh against a real 1.0 to 1.2, and the oven the single
        # largest appliance in the estate.
        #
        # The transitions are now one hundredth of the cycle wide, which is a
        # square wave to within the 1-minute render step, and the duty cycle
        # after preheat is about 25% - which is what a 2.4 kW element holding
        # 180 C in an insulated box actually does. Mean 0.4804 of rating.
        ((0.00, 1.00), (0.25, 1.00), (0.26, 0.08), (0.40, 0.08), (0.41, 1.00),
         (0.46, 1.00), (0.47, 0.08), (0.60, 0.08), (0.61, 1.00), (0.66, 1.00),
         (0.67, 0.08), (0.80, 0.08), (0.81, 1.00), (0.86, 1.00), (0.87, 0.08),
         (1.00, 0.08)),
        0.10, 0.22, 0.004,
        irish_specific=False, flexible=False, controllable_live=False,
    ),
    "hob_ring": Signature(
        "SIG-HOB", "hob", "medium ring", 900, 208.8, 1800.0,
        ((0.0, 1.0), (0.15, 1.0), (0.2, 0.35), (1.0, 0.35)),
        0.14, 0.30, 0.003,
        irish_specific=False, flexible=False, controllable_live=False,
    ),
    "extractor": Signature(
        "SIG-EXTRACT", "extractor_fan", "medium", 1_200, 43.3, 130.0, _flat(1.0),
        0.12, 0.30, 0.002,
        irish_specific=False, flexible=False, controllable_live=False,
    ),
    # -- always-on and cyclic ---------------------------------------------
    "fridge_freezer": Signature(
        "SIG-FRIDGE", "fridge_freezer", "compressor cycle", 1_800, 22.1, 95.0,
        ((0.0, 1.0), (0.45, 1.0), (0.46, 0.02), (1.0, 0.02)),
        0.15, 0.20, 0.008,
        irish_specific=False, flexible=False, controllable_live=False,
        notes="Runs all year; its cycling is the background against which "
              "everything else is detected.",
    ),
    "standby_base": Signature(
        "SIG-STANDBY", "standby", "always on", 86_400, 1440.0, 60.0, _flat(1.0),
        0.25, 0.02, 0.0,
        irish_specific=False, flexible=False, controllable_live=False,
        notes="Router, set-top boxes, chargers: the floor of the load curve.",
    ),
    # -- entertainment and lighting ---------------------------------------
    "tv_led": Signature(
        "SIG-TV", "television", "viewing", 3_600, 92.6, 95.0,
        ((0.0, 1.0), (1.0, 0.95)), 0.22, 0.40, 0.003,
        irish_specific=False, flexible=False, controllable_live=False,
    ),
    "lighting_evening": Signature(
        # 75 W is a whole-house LED lighting load with several rooms lit, which
        # is where Irish housing now sits. An earlier 180 W gave 2.05 kWh a day
        # of lighting - three times a modern household's total - because it was
        # an incandescent-era figure.
        "SIG-LIGHT", "lighting", "evening", 3_600, 70.5, 75.0,
        ((0.0, 0.8), (0.3, 1.0), (0.8, 1.0), (1.0, 0.7)),
        0.30, 0.35, 0.002,
        irish_specific=False, flexible=False, controllable_live=False,
    ),
    # -- Irish-specific loads the design names -----------------------------
    "electric_shower": Signature(
        "SIG-SHOWER", "electric_shower", "8.5 kW", 420, 991.7, 8500.0, _flat(1.0),
        0.08, 0.28, 0.003,
        irish_specific=True, flexible=False, controllable_live=False,
        notes="Design 5.6 and K07 both single this out: a very large, very "
              "short load that dominates the instantaneous peak and has no "
              "equivalent in most UK sub-metered datasets.",
    ),
    "immersion_heater": Signature(
        "SIG-IMMERSION", "immersion_heater", "sink 30 min", 1_800, 1399.6, 2900.0,
        ((0.0, 1.0), (0.93, 1.0), (1.0, 0.0)),
        0.06, 0.25, 0.003,
        irish_specific=True, flexible=True, controllable_live=True,
        notes="Thermostat hysteresis makes the tail abrupt. Flexible and "
              "controllable: the classic Irish hot-water shifting load.",
    ),
    "storage_heater": Signature(
        "SIG-STORAGE", "storage_heater", "night charge", 25_200, 9216.1, 1350.0,
        ((0.0, 1.0), (0.95, 1.0), (1.0, 0.0)),
        0.08, 0.10, 0.004,
        irish_specific=True, flexible=True, controllable_live=True,
        notes="Charges on the night rate; the original demand-shifting device.",
    ),
    # -- flexible and controllable assets ----------------------------------
    "ev_charger_7kw": Signature(
        "SIG-EV-7K", "ev_charger", "7.4 kW AC", 10_800, 19913.1, 7400.0,
        # constant current, then taper as the pack fills
        ((0.0, 1.0), (0.75, 1.0), (0.88, 0.6), (0.97, 0.25), (1.0, 0.05)),
        0.04, 0.35, 0.001,
        irish_specific=False, flexible=True, controllable_live=True,
        notes="The taper is what distinguishes a real charge from a square wave.",
    ),
    "heat_pump_cycle": Signature(
        "SIG-HP", "heat_pump", "space heating", 3_600, 1769.4, 3000.0,
        # Compressor inrush, then modulated running at about 60% of rated,
        # which is where an inverter-driven heat pump actually sits.
        ((0.0, 1.30), (0.05, 0.62), (0.90, 0.60), (0.95, 0.12), (1.0, 0.08)),
        0.09, 0.30, 0.005,
        irish_specific=False, flexible=True, controllable_live=True,
        notes="The start-up spike is the compressor inrush; COP is applied by "
              "the device model, not by the signature.",
    ),
}


def shape_mean(sig: Signature, n: int = 2000) -> float:
    """Mean of the signature's relative-power shape over its duration."""
    x = np.array([a for a, _ in sig.shape], dtype=np.float64)
    y = np.array([b for _, b in sig.shape], dtype=np.float64)
    t = np.linspace(0.0, 1.0, n, endpoint=False)
    return float(np.interp(t, x, y).mean())


def energy_implied_by_shape(sig: Signature) -> float:
    """Energy the device's own rating and shape imply, Wh.

    ``peak_w`` and ``shape`` are **device properties**: a kettle has a rated
    element and draws it flat; a heat pump modulates to a fraction of rated.
    Energy is therefore a *consequence*, not an independent declaration, and
    declaring it separately lets the three disagree.

    They did disagree. The first version declared energies that implied peaks of
    4,048 W for an 1,800 W hob ring and 3,051 W for a 2,800 W kettle, because
    the renderer rescales to the declared energy and the shape could not deliver
    it within the rating. :func:`assert_library_consistent` now refuses the
    library unless every signature's declared energy is within 2% of the energy
    its own rating and shape imply.
    """
    return sig.peak_w * shape_mean(sig) * (sig.nominal_duration_s / 3600.0)


class SignatureInconsistent(ValueError):
    """A signature's declared energy, rating and shape cannot all be true."""


def assert_library_consistent(tolerance: float = 0.02) -> dict[str, float]:
    """Refuse the library if any signature's energy contradicts its rating.

    Called at import time, so an inconsistent signature cannot reach a
    simulation: a rendered cycle that exceeds its appliance's rating would
    appear in D18 as a measurement no real meter could have produced, and the
    tell audit (7.9) would find it.
    """
    report: dict[str, float] = {}
    bad: list[str] = []
    for key, sig in SIGNATURE_LIBRARY.items():
        implied = energy_implied_by_shape(sig)
        ratio = sig.nominal_energy_wh / implied if implied > 0 else float("inf")
        report[key] = round(ratio, 4)
        if not (1.0 - tolerance) <= ratio <= (1.0 + tolerance):
            bad.append(
                f"{key}: declared {sig.nominal_energy_wh:.1f} Wh but its "
                f"{sig.peak_w:.0f} W rating and shape imply {implied:.1f} Wh "
                f"(ratio {ratio:.2f})"
            )
    if bad:
        raise SignatureInconsistent(
            "signature library is internally inconsistent:\n  - " + "\n  - ".join(bad)
        )
    return report


def signature_for(appliance_type: str, programme: str | None = None) -> Signature:
    """Find a signature by appliance type, and optionally programme."""
    for sig in SIGNATURE_LIBRARY.values():
        if sig.appliance_type == appliance_type and (
            programme is None or sig.programme == programme
        ):
            return sig
    for sig in SIGNATURE_LIBRARY.values():
        if sig.appliance_type == appliance_type:
            return sig
    raise KeyError(
        f"no signature for appliance_type={appliance_type!r}; known: "
        f"{sorted({s.appliance_type for s in SIGNATURE_LIBRARY.values()})}"
    )


def render_cycle(
    sig: Signature,
    *,
    duration_s: int,
    energy_wh: float,
    seed: int,
    rate_hz: float = 1.0,
) -> np.ndarray:
    """Render one cycle's power series from its signature and seed.

    **Exact energy by construction.**  The shape is interpolated, perturbed by
    the signature's model-to-model variation, then rescaled so that the
    integral equals ``energy_wh`` exactly.  That is what lets design 7.2's
    energy closure hold to 0.1%: a rendered waveform can never disagree with
    the energy its cycle recorded, however the shape is perturbed.

    **Deterministic from the seed alone** (design 7.2 / R13): the same
    ``(signature, duration, energy, seed, rate)`` always gives byte-identical
    output, which is what the render API's determinism test checks.
    """
    n = max(int(round(duration_s * rate_hz)), 1)
    t = np.linspace(0.0, 1.0, n, endpoint=False)

    knots_x = np.array([k[0] for k in sig.shape], dtype=np.float64)
    knots_y = np.array([k[1] for k in sig.shape], dtype=np.float64)
    shape = np.interp(t, knots_x, knots_y)

    gen = np.random.default_rng(seed)
    # Model-to-model variation: one draw per cycle, applied to the whole shape,
    # because two different kettles differ in level rather than in jitter.
    level = float(1.0 + gen.normal(0.0, sig.var_power_cv))
    level = max(level, 0.3)
    # Within-cycle measurement-scale ripple, small and zero-mean.
    ripple = 1.0 + gen.normal(0.0, 0.02, n)
    power = np.clip(shape * level * ripple, 0.0, None)

    # Rescale to the exact energy. energy_wh = sum(power_w) * dt_h.
    dt_h = 1.0 / (3600.0 * rate_hz)
    total = float(power.sum()) * dt_h
    if total > 0:
        power *= energy_wh / total
    return power


def D22_rows() -> list[dict[str, Any]]:
    """The library as D22 rows, with provenance that does not overclaim."""
    out = []
    for key, s in sorted(SIGNATURE_LIBRARY.items()):
        out.append(
            {
                "signature_id": s.signature_id,
                "appliance_type": s.appliance_type,
                "programme": s.programme,
                "source_dataset": "synthetic-template",
                "source_licence": "n/a (parameterised template, not measured data)",
                "template_hz": 1.0,
                "template_w": [float(v) for _, v in s.shape],
                "duration_s": s.nominal_duration_s,
                "energy_wh_nominal": s.nominal_energy_wh,
                "var_power_cv": s.var_power_cv,
                "var_duration_cv": s.var_duration_cv,
                "ageing_power_per_year": s.ageing_power_per_year,
                "irish_specific": s.irish_specific,
                "evidence_status": (
                    "[A] parameterised template. The public sub-metered datasets "
                    "named in U05 (UK-DALE, REFIT, REDD, IDEAL) are NOT ingested "
                    "in this build; their licences are deferred to WP1 and E1 is "
                    "engineering verification, not signature fidelity. Risk K07 "
                    "applies in full."
                ),
            }
        )
    return out


# Import-time guard: an inconsistent signature must not reach a simulation,
# because a rendered cycle exceeding its appliance's rating would appear in D18
# as a measurement no real meter could have produced, and the tell audit (7.9)
# would find it. Checked here rather than in a test so it cannot be skipped.
_CONSISTENCY = assert_library_consistent()  # import-time guard
