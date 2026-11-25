"""The observation model, S12 (design 5.11, 6.5; datasets D18, D31).

    Each device type has a measurement model: resolution, accuracy class,
    quantisation and clock drift; reporting interval; communication gaps
    (bursty, weather-correlated); failure and replacement (meter swap, CT
    mis-orientation, sensor battery death, inverter firmware change).

    Sensor tiers are drawn per home (R10), so detection difficulty varies
    across the town as it would in practice.

**What makes this an observation model rather than noise.**  Each imperfection
below is a *named real-world mechanism* (design 6.5 rule 1), and each is
reversible in principle by someone who knows the mechanism:

* **quantisation** - a meter reports to its display resolution, so a 1 W
  reading from a meter with 10 W resolution is not possible;
* **clock drift** - an unsynchronised device's timestamps walk, so two devices
  in the same home disagree about when a minute began;
* **weather-correlated gaps** - radio links fail more in heavy rain, so gaps
  cluster on wet days instead of being uniform, which is what defeats a naive
  gap-filler;
* **CT mis-orientation** - a clamp fitted backwards reports negative power, and
  it stays backwards until someone notices;
* **battery death** - a battery sensor stops, and stays stopped until a visit.

Uniform white noise on every channel would be none of these, and the tell audit
(7.9) specifically looks for "identical error patterns across homes".
"""

from __future__ import annotations

import dataclasses
from typing import Any

import numpy as np

from baile_nua.rng import SeedTree, Stream

__all__ = [
    "DeviceSpec",
    "DEVICE_SPECS",
    "TIER_DEVICES",
    "observe_channel",
    "ObservationResult",
]


@dataclasses.dataclass(frozen=True)
class DeviceSpec:
    """One device class's measurement model."""

    channel: str
    unit: str
    #: Reporting interval in seconds (design 3.1 S12: "1 Hz to 30 min").
    interval_s: int
    #: Display/transmission resolution; a reading is a multiple of this.
    quantum: float
    #: Accuracy class as a relative standard deviation.
    accuracy_rel: float
    #: Additive noise floor in the channel's unit.
    noise_abs: float
    #: Clock drift in seconds per day, before any resynchronisation.
    clock_drift_s_per_day: float
    #: Base probability that a reporting interval is missing.
    gap_rate: float
    #: How much heavy rain multiplies the gap rate (radio attenuation).
    gap_rain_multiplier: float
    #: Probability per year that the device fails outright.
    failure_rate_per_year: float
    #: Slow calibration drift, relative per year.
    drift_rel_per_year: float
    mechanism: str


#: The device classes, one per observable channel family.
DEVICE_SPECS: dict[str, DeviceSpec] = {
    "import_w": DeviceSpec(
        "import_w", "W", 1, 1.0, 0.005, 2.0, 0.6, 0.0008, 3.0, 0.004, 0.002,
        mechanism="the smart meter's own active-import register, read at its "
                  "reporting interval",
    ),
    "export_w": DeviceSpec(
        "export_w", "W", 1, 1.0, 0.005, 2.0, 0.6, 0.0008, 3.0, 0.004, 0.002,
        mechanism="the smart meter's active-export register",
    ),
    "ct_circuit": DeviceSpec(
        "ct_circuit", "W", 1, 5.0, 0.020, 8.0, 4.5, 0.0040, 4.0, 0.030, 0.012,
        mechanism="a clamp-on current transformer on a consumer-unit circuit, "
                  "which infers power from current and assumes the voltage",
    ),
    "temp": DeviceSpec(
        "temp", "degC", 300, 0.1, 0.004, 0.25, 12.0, 0.0090, 6.0, 0.060, 0.004,
        mechanism="a battery room sensor reporting on its own schedule",
    ),
    "rh": DeviceSpec(
        "rh", "percent", 300, 0.5, 0.020, 2.0, 12.0, 0.0090, 6.0, 0.080, 0.012,
        mechanism="the humidity element of the same room sensor, which ages "
                  "faster than its thermistor",
    ),
    "co2": DeviceSpec(
        # 3% a year is the realistic NDIR drift once auto-baselining is doing
        # its job. An earlier 11% a year compounded to a 42% error over three
        # years, which no sensor in service would reach - auto-baselining exists
        # precisely to stop it.
        "co2", "ppm", 300, 1.0, 0.030, 25.0, 12.0, 0.0110, 7.0, 0.090, 0.030,
        mechanism="an NDIR CO2 sensor, which drifts and is usually "
                  "auto-baselined to the lowest reading it has seen",
    ),
    "pir": DeviceSpec(
        # 0.0015 per minute-slot, not 0.015: the earlier rate lost 17% of a
        # PIR's day, which would make an occupancy benchmark unsolvable for the
        # wrong reason.
        "pir", "bool", 60, 1.0, 0.0, 0.0, 15.0, 0.0015, 9.0, 0.000, 0.000,
        mechanism="a passive-infrared occupancy sensor, which reports movement "
                  "rather than presence and misses a still person",
    ),
    "inverter_w": DeviceSpec(
        "inverter_w", "W", 300, 10.0, 0.015, 10.0, 8.0, 0.0120, 5.0, 0.020, 0.008,
        mechanism="the PV inverter's own telemetry, polled over the local "
                  "network and lost whenever the inverter restarts",
    ),
    "bess_soc": DeviceSpec(
        "bess_soc", "percent", 300, 1.0, 0.010, 0.5, 8.0, 0.0120, 5.0, 0.020, 0.015,
        mechanism="the battery management system's own state-of-charge "
                  "estimate, which is itself a model rather than a measurement",
    ),
    "charger_w": DeviceSpec(
        "charger_w", "W", 60, 10.0, 0.010, 10.0, 6.0, 0.0100, 6.0, 0.020, 0.006,
        mechanism="the EV charge point's metering, reported when a session is "
                  "active and silent otherwise",
    ),
}

#: Which channels each sensor tier has (design 5.11, R10, U06).
TIER_DEVICES: dict[str, tuple[str, ...]] = {
    "T1": ("import_w", "export_w"),
    "T2": ("import_w", "export_w", "temp", "ct_circuit"),
    "T3": ("import_w", "export_w", "temp", "rh", "co2", "ct_circuit"),
    "T4": ("import_w", "export_w", "temp", "rh", "co2", "pir", "ct_circuit",
           "inverter_w", "bess_soc", "charger_w"),
}


@dataclasses.dataclass
class ObservationResult:
    """What a device reported, and what it did to the truth to get there."""

    ts_offset_s: np.ndarray      # device clock minus true clock, per sample
    value: np.ndarray            # NaN where the reading never arrived
    quality: list[str]
    provenance: list[str]
    diagnostics: dict[str, Any]


def observe_channel(
    truth: np.ndarray,
    *,
    channel_family: str,
    device_id: str,
    seed_tree: SeedTree,
    sim_day: int,
    rain_mm: np.ndarray | None = None,
    device_age_years: float = 1.0,
    failed_from_index: int | None = None,
    ct_reversed: bool = False,
    interval_s: int | None = None,
    phase_min: int | None = None,
) -> ObservationResult:
    """Turn a true 1-minute series into what one device would have reported.

    ``truth`` is at 1-minute resolution; the device's own interval is applied by
    sampling, so a 5-minute sensor returns a value every fifth minute and NaN
    between - which is what a real series looks like and what any model trained
    on it must handle.

    ``interval_s`` and ``phase_min`` override the device class's own reporting
    interval and its phase within that interval.  Both default to ``None``,
    which is the device class's own behaviour, so every existing call renders
    exactly what it rendered before.

    They exist for the smart-meter era (``observation/era.py``, A-100): the same
    meter that reports its import register every minute to a PARA//EL edge
    device publishes it every **30 minutes** through the programme's data
    service, clock-aligned rather than on a phase of its own, and before
    enrolment that service is the only way the reading leaves the house.  That
    is one device reporting on two schedules, not two devices, so it is the
    interval that is overridden and not the device class.  Passing
    ``phase_min`` also suppresses the phase draw, because a clock-aligned
    interval has nothing to draw.
    """
    spec = DEVICE_SPECS.get(channel_family)
    if spec is None:
        raise KeyError(
            f"unknown channel family {channel_family!r}; known: {sorted(DEVICE_SPECS)}"
        )
    n = len(truth)
    gen = seed_tree.generator(Stream.SENSOR_NOISE, entity=device_id, sim_day=sim_day)
    ggen = seed_tree.generator(Stream.SENSOR_GAP, entity=device_id, sim_day=sim_day)
    dgen = seed_tree.generator(Stream.SENSOR_DRIFT, entity=device_id, sim_day=sim_day)

    value = np.asarray(truth, dtype=np.float64).copy()
    quality = ["ok"] * n
    provenance = ["metered"] * n

    # ---- 1. reporting interval: only some minutes carry a reading ---------
    effective_interval_s = spec.interval_s if interval_s is None else int(interval_s)
    if effective_interval_s <= 0:
        raise ValueError(
            f"interval_s must be positive, got {effective_interval_s}"
        )
    step = max(effective_interval_s // 60, 1)
    reported = np.zeros(n, dtype=bool)
    # A device's phase within its interval is its own, not aligned to the hour,
    # so two 5-minute sensors in the same home report on different minutes.
    if phase_min is not None:
        phase = int(phase_min) % step
    else:
        phase = int(gen.integers(0, step)) if step > 1 else 0
    reported[phase::step] = True

    # ---- 2. calibration drift: a slow multiplicative error ----------------
    drift = 1.0 + spec.drift_rel_per_year * device_age_years * float(dgen.normal(1.0, 0.3))
    value *= drift

    # ---- 3. CT mis-orientation: a clamp fitted backwards -------------------
    if ct_reversed and channel_family in ("ct_circuit", "import_w"):
        value = -value

    # ---- 4. accuracy and noise floor --------------------------------------
    if spec.accuracy_rel > 0 or spec.noise_abs > 0:
        value = value * (1.0 + gen.normal(0.0, spec.accuracy_rel, n)) + gen.normal(
            0.0, spec.noise_abs, n
        )

    # ---- 5. quantisation: a reading is a multiple of the resolution --------
    if spec.quantum > 0:
        value = np.round(value / spec.quantum) * spec.quantum

    # ---- 6. clock drift, with periodic resynchronisation ------------------
    #
    # Drift does not grow without bound: a mains device syncs over the network
    # and a battery device is corrected whenever it is touched. Modelled as a
    # resync every `resync_days`, so the offset sawtooths rather than running
    # away - an earlier version accumulated 11 minutes on a room sensor, which
    # would have made cross-device alignment impossible for a reason no real
    # installation has.
    resync_days = 7 if effective_interval_s <= 60 else 30
    days_since_sync = sim_day % resync_days
    drift_s = (
        spec.clock_drift_s_per_day * days_since_sync * float(gen.normal(1.0, 0.25))
    )
    ts_offset = np.full(n, drift_s, dtype=np.float64)

    # ---- 7. gaps, weather-correlated --------------------------------------
    rate = np.full(n, spec.gap_rate, dtype=np.float64)
    if rain_mm is not None:
        heavy = np.asarray(rain_mm, dtype=np.float64) > 1.0
        rate = np.where(heavy, rate * spec.gap_rain_multiplier, rate)
    # Gaps are BURSTY: a radio link that drops stays down for a while. A
    # Bernoulli draw per sample would give isolated single-minute holes, which
    # a gap-filler handles trivially and which real data does not look like.
    gap = np.zeros(n, dtype=bool)
    i = 0
    n_bursts = 0
    while i < n:
        if float(ggen.random()) < rate[i]:
            length = int(np.clip(ggen.geometric(0.18), 1, 240))
            gap[i:i + length] = True
            n_bursts += 1
            i += length
        else:
            i += 1

    # ---- 8. outright failure ---------------------------------------------
    if failed_from_index is not None and 0 <= failed_from_index < n:
        gap[failed_from_index:] = True

    out = np.where(reported & ~gap, value, np.nan)
    for i in range(n):
        if not reported[i]:
            quality[i] = "missing"
            provenance[i] = "estimated"
        elif gap[i]:
            quality[i] = "missing"
            provenance[i] = "estimated"
        elif ct_reversed and channel_family in ("ct_circuit", "import_w"):
            quality[i] = "suspect"
        elif abs(drift - 1.0) > 0.05:
            quality[i] = "drift"

    return ObservationResult(
        ts_offset_s=ts_offset,
        value=out,
        quality=quality,
        provenance=provenance,
        diagnostics={
            "channel_family": channel_family,
            "interval_s": effective_interval_s,
            "interval_s_declared": spec.interval_s,
            "reporting_phase_min": phase,
            "calibration_drift": round(drift, 5),
            "clock_drift_s": round(drift_s, 2),
            "n_reported_slots": int(reported.sum()),
            "n_gap_minutes": int((gap & reported).sum()),
            "n_gap_bursts": n_bursts,
            "gap_fraction_of_slots": round(
                float((gap & reported).sum()) / max(int(reported.sum()), 1), 5
            ),
            "ct_reversed": ct_reversed,
            "failed_from_index": failed_from_index,
            "mechanism": spec.mechanism,
        },
    )
