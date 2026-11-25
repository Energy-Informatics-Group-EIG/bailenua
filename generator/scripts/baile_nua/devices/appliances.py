"""Activity-to-appliance triggering and the household electrical model (design 5.6, S10).

    **Activity to appliance.**  Each activity triggers appliance cycles
    probabilistically (cooking -> hob, oven, kettle, extractor; laundry ->
    washer then dryer or indoor airing, weather-dependent).

    **Device fidelity modes.**  *Rendered mode* (default, and always for
    non-controllable appliances): cycles are simulated as events; 1 Hz
    waveforms are rendered afterwards and never change state.  *Live mode*
    (controllable assets under test): these run inside the loop as state
    machines.

    **Tests.**  With no action taken, live and rendered modes must agree on
    energy within 0.1%.

The energy-closure invariant (design 7.2) is what this module is built around:

    Sigma appliance + HVAC + EV + BESS charge - PV - BESS discharge
        = net meter, within 0.1% of daily energy.

So the household's net power is assembled from exactly those terms and nothing
else, and :func:`household_day_energy` returns the balance so the invariant can
be checked on the same arrays the meter was built from.
"""

from __future__ import annotations

import dataclasses
import math
from collections import defaultdict
from typing import Any

import numpy as np

from baile_nua.devices.signatures import (
    SIGNATURE_LIBRARY,
    Signature,
    render_cycle,
    signature_for,
)
from baile_nua.rng import SeedTree, Stream

__all__ = [
    "ApplianceCycle",
    "TRIGGERS",
    "trigger_cycles",
    "render_household_minutes",
    "household_day_energy",
    "OWNERSHIP_PRIORS",
    "SHARED_WITHIN_EPISODE",
    "PER_PERSON_APPLIANCES",
    "EXTRA_CYCLE_PER_EXTRA_PARTICIPANT",
    "ActivityEpisode",
    "ApplianceError",
    "build_episodes",
]

MINUTES_PER_DAY = 1440


class ApplianceError(RuntimeError):
    """The device layer was asked for something it cannot answer honestly."""


@dataclasses.dataclass
class ApplianceCycle:
    """One D13 row, before it is written."""

    cycle_id: str
    asset_id: str
    building_id: str
    start_min: int
    end_min: int
    appliance_type: str
    programme: str
    signature_id: str
    signature_seed: int
    energy_wh: float
    peak_w: float
    caused_by_activity_id: str | None
    flexible: bool
    shifted_by_min: int = 0
    zone: str = "living"

    @property
    def duration_s(self) -> int:
        return (self.end_min - self.start_min) * 60


#: Which appliances an activity can trigger, with the probability it does and
#: how many cycles.  Design 5.6's own examples are the first two entries.
#:
#: Probabilities are **per occurrence of the activity**, not per day, and are
#: declared assumptions [A] - no public Irish source gives
#: activity-to-appliance conditional rates, which is why design 5.6 only says
#: "probabilistically" and leaves the rates to calibration.
TRIGGERS: dict[str, list[dict[str, Any]]] = {
    # The cooking rates are per household COOKING EPISODE, of which there are
    # about three a day: HETUS gives 36 minutes of food management per person
    # per day, and a household of three therefore spends an hour and a half on
    # food across its members - which is right, and is not three dinners. So a
    # cooking episode must NOT imply a full cooked meal, and these rates are
    # what turn roughly three episodes into roughly two hob uses and two thirds
    # of an oven use a day.
    #
    # Tuned against D24's DBEREL01 target (dwelling type x BER band), whose
    # source is declared with model_development_exposure "tuning" for exactly
    # this reason. DBEREL02 (dwelling type x period of construction) was not
    # used here and stays held out.
    "cooking": [
        {"appliance": "hob", "p": 0.45, "n": (1, 2)},
        {"appliance": "oven", "p": 0.22, "n": (1, 1)},
        {"appliance": "kettle", "p": 0.40, "n": (1, 1)},
        {"appliance": "extractor_fan", "p": 0.35, "n": (1, 1)},
        {"appliance": "microwave", "p": 0.22, "n": (1, 2)},
    ],
    "washing_up": [
        {"appliance": "dishwasher", "p": 0.42, "n": (1, 1)},
        # The immersion used to be triggered here. It is a thermostatic
        # device on a tank, not something an episode switches on, and U25
        # moved it to physics/dhw.py where a thermostat and a cylinder
        # temperature decide when it runs. Washing up now draws hot WATER
        # from the cylinder instead, which is what it actually does.
    ],
    "laundry": [
        {"appliance": "washing_machine", "p": 0.85, "n": (1, 1)},
        # The dryer follows the washer, and whether it is used at all is
        # weather-dependent: design 5.6 says "washer then dryer or indoor
        # airing, weather-dependent". The weather dependence is applied by
        # `trigger_cycles` from the day's rainfall, not fixed here.
        {"appliance": "tumble_dryer", "p": 0.55, "n": (1, 1), "weather_dependent": True},
    ],
    "eating_snack": [
        {"appliance": "kettle", "p": 0.60, "n": (1, 1)},
        {"appliance": "toaster", "p": 0.35, "n": (1, 1)},
    ],
    "eating_main": [
        {"appliance": "kettle", "p": 0.30, "n": (1, 1)},
    ],
    "shower_bath": [
        # The electric shower stays an appliance: DEAP Section 4 says it
        # "uses electricity directly rather than from the water heating
        # system". The immersion moved to the cylinder (U25).
        {"appliance": "electric_shower", "p": 0.45, "n": (1, 1)},
    ],
    "tv_screens": [
        {"appliance": "television", "p": 0.92, "n": (1, 1)},
    ],
    "cleaning": [
        {"appliance": "kettle", "p": 0.15, "n": (1, 1)},
    ],
    "work_at_home": [
        {"appliance": "kettle", "p": 0.45, "n": (1, 2)},
    ],
}

#: Appliances that serve a whole household episode rather than one person.
#:
#: This is the fix for I-027 and it is structural, not a rate change.  Triggers
#: fire per *activity interval*, and the activity engine emits one interval per
#: PERSON, so a family of three sitting down to dinner used to boil the kettle
#: three times, run the hob three times and start three dishwashers.  Measured:
#: 14.9 kettle boils and 1.6 dishwasher cycles per household per day, against a
#: realistic 6 to 8 and 0.6 to 0.8, and 16.35 kWh/day of appliance electricity
#: alone against a Co. Cork mean of 4,186 kWh/year for EVERYTHING (D24).
#:
#: A shared appliance is therefore triggered once per household *episode* - a
#: maximal run of overlapping intervals of the same activity in the same zone.
#: Zone matters: two people watching television together share one set, two
#: watching in different rooms do not, and grouping by zone gets both right
#: without a rule about how many televisions a house has.
SHARED_WITHIN_EPISODE: frozenset[str] = frozenset({
    "hob", "oven", "kettle", "extractor_fan", "microwave", "toaster",
    "dishwasher", "washing_machine", "tumble_dryer",
    "television",
})

#: Appliances that stay per-person, with the reason.
#:
#: ``electric_shower`` is the whole list: a shower serves exactly one person,
#: and the activity engine already queues the bathroom as a shared resource, so
#: shower intervals rarely overlap anyway - which means episode grouping would
#: have given nearly the right answer by accident.  Relying on an accident is
#: how the next version breaks, so it is declared.
PER_PERSON_APPLIANCES: frozenset[str] = frozenset({"electric_shower"})

#: Shared appliances where more participants genuinely means more cycles.
#:
#: One pot of tea does not scale with the number of drinkers, but it does not
#: stay flat either: a kettle holds about four cups.  The extra-cycle
#: probability per additional participant is a declared assumption [A]; the
#: sub-linearity is not in doubt, only its slope.
EXTRA_CYCLE_PER_EXTRA_PARTICIPANT: dict[str, float] = {
    "kettle": 0.30,
    "toaster": 0.45,      # toasters hold two slices, so they scale more nearly
    "microwave": 0.35,    # one plate at a time
    "hob": 0.12,          # a bigger pot, not a second one
}


#: Appliance ownership probability, conditioned on household size and tenure.
#: Declared assumptions [A]: SAPS publishes no appliance ownership, and the
#: design defers it to "national ownership evidence" in WP1 (design 5.6).
#: Irish-specific loads the design names are present.
OWNERSHIP_PRIORS: dict[str, dict[str, Any]] = {
    "fridge_freezer":   {"base": 0.99, "per_person": 0.00},
    "kettle":           {"base": 0.97, "per_person": 0.00},
    "toaster":          {"base": 0.88, "per_person": 0.00},
    "microwave":        {"base": 0.90, "per_person": 0.00},
    "hob":              {"base": 0.98, "per_person": 0.00},
    "oven":             {"base": 0.95, "per_person": 0.00},
    "extractor_fan":    {"base": 0.72, "per_person": 0.00},
    "washing_machine":  {"base": 0.96, "per_person": 0.00},
    "tumble_dryer":     {"base": 0.52, "per_person": 0.05, "owner_bonus": 0.12},
    "dishwasher":       {"base": 0.48, "per_person": 0.06, "owner_bonus": 0.15},
    "television":       {"base": 0.96, "per_person": 0.01},
    "lighting":         {"base": 1.00, "per_person": 0.00},
    "standby":          {"base": 1.00, "per_person": 0.00},
    # Irish-specific (design 5.6, K07)
    "electric_shower":  {"base": 0.58, "per_person": 0.02},
    # `immersion_heater` left this table at U25. It was an appliance with a
    # load signature and no thermal store, which is what the stream writer's
    # note about `dhw_tank_c` recorded. The cylinder now owns it:
    # `DHWSystem.has_immersion` decides whether there is one and
    # `physics/dhw.py` decides when it runs, against a thermostat and a tank
    # temperature. Leaving it here as well would have charged every immersion
    # twice - once as an HVAC-category appliance cycle and once as the tank's
    # reheat - and the two would not even have been for the same hot water.
    #
    # `electric_shower` STAYS, and that is not an inconsistency: DEAP Section
    # 4 says an electric shower "uses electricity directly rather than from
    # the water heating system", so it is genuinely an appliance, and
    # `dhw.draw_schedule` takes no tank draw for a home that has one.
}


def _duration_for(
    sig: Signature, gen: np.random.Generator, *, age_years: float
) -> tuple[int, float]:
    """Draw a cycle's duration and energy, with model and age variation.

    Ageing raises the energy for a given duration: a worn element or a tired
    compressor draws more for the same job.  Applied to energy rather than to
    duration, because an older kettle does not take longer to be switched on -
    it takes longer to boil, which is more energy at the same power.
    """
    cv = sig.var_duration_cv
    sigma = math.sqrt(math.log(1.0 + cv * cv)) if cv > 0 else 0.0
    mu = math.log(max(sig.nominal_duration_s, 1.0)) - 0.5 * sigma * sigma
    dur_s = int(max(round(gen.lognormal(mu, sigma) if sigma else sig.nominal_duration_s), 30))
    ageing = 1.0 + sig.ageing_power_per_year * max(age_years, 0.0)
    energy = sig.nominal_energy_wh * (dur_s / sig.nominal_duration_s) * ageing
    return dur_s, float(energy)


@dataclasses.dataclass(frozen=True)
class ActivityEpisode:
    """A household-level activity episode: overlapping intervals, same zone.

    ``n_participants`` is what makes a shared appliance scale sub-linearly
    instead of linearly or not at all.
    """

    activity: str
    zone: str
    start_min: int
    end_min: int
    n_participants: int
    activity_id: str | None
    person_ids: tuple[str, ...]

    @property
    def duration_min(self) -> int:
        return max(self.end_min - self.start_min, 1)


def build_episodes(activities: list[Any]) -> list[ActivityEpisode]:
    """Collapse per-person intervals into household episodes.

    Two intervals join the same episode when they share an activity, share a
    zone and overlap in time.  Overlap is strict: back-to-back intervals are
    two episodes, because one person cooking after another really is two
    cooking events.

    The returned order is deterministic - sorted by (activity, zone, start) -
    because the cycle ids and every downstream draw depend on it.
    """
    at_home = [
        a for a in activities
        if getattr(a, "location_kind", "building") == "building"
    ]
    groups: dict[tuple[str, str], list[Any]] = {}
    for a in at_home:
        groups.setdefault((a.activity, a.zone), []).append(a)

    episodes: list[ActivityEpisode] = []
    for (activity, zone), items in groups.items():
        items.sort(key=lambda x: (x.start_min, x.end_min, x.person_id))
        cur: list[Any] = []
        cur_end = -1
        def flush(members: list[Any]) -> None:
            if not members:
                return
            episodes.append(
                ActivityEpisode(
                    activity=activity, zone=zone,
                    start_min=min(m.start_min for m in members),
                    end_min=max(m.end_min for m in members),
                    n_participants=len({m.person_id for m in members}),
                    activity_id=getattr(members[0], "activity_id", None),
                    person_ids=tuple(sorted({m.person_id for m in members})),
                )
            )
        for a in items:
            if cur and a.start_min < cur_end:
                cur.append(a)
                cur_end = max(cur_end, a.end_min)
            else:
                flush(cur)
                cur = [a]
                cur_end = a.end_min
        flush(cur)
    episodes.sort(key=lambda e: (e.activity, e.zone, e.start_min, e.end_min))
    return episodes


def trigger_cycles(
    *,
    building_id: str,
    activities: list[Any],
    owned: dict[str, dict[str, Any]],
    seed_tree: SeedTree,
    sim_day: int,
    rain_mm_day: float = 0.0,
    ghi_day_wh_m2: float = 0.0,
    ghi_by_minute: np.ndarray | None = None,
    occupied_by_minute: np.ndarray | None = None,
) -> list[ApplianceCycle]:
    """Turn one household's activities into appliance cycles.

    ``owned`` maps appliance type to ``{"asset_id", "age_years", "rated_power_w"}``;
    an appliance the household does not own cannot be triggered, which is how
    R10's heterogeneity reaches the load curve.

    Always-on loads (standby, fridge) are emitted once per day rather than
    triggered, because nothing a person does starts them.
    """
    gen = seed_tree.generator(Stream.APPLIANCE_TRIGGER, entity=building_id, sim_day=sim_day)
    sgen = seed_tree.generator(Stream.APPLIANCE_SIGNATURE, entity=building_id, sim_day=sim_day)
    cycles: list[ApplianceCycle] = []
    counter = 0

    def emit(
        appliance: str, start_min: int, activity_id: str | None, zone: str
    ) -> None:
        nonlocal counter
        info = owned.get(appliance)
        if info is None:
            return
        try:
            sig = signature_for(appliance)
        except KeyError:
            return
        dur_s, energy = _duration_for(sig, sgen, age_years=float(info.get("age_years", 0.0)))
        end_min = min(start_min + max(1, dur_s // 60), MINUTES_PER_DAY)
        if end_min <= start_min:
            end_min = min(start_min + 1, MINUTES_PER_DAY)
        counter += 1
        cycles.append(
            ApplianceCycle(
                cycle_id=f"C-{building_id}-{sim_day:05d}-{counter:04d}",
                asset_id=str(info["asset_id"]),
                building_id=building_id,
                start_min=start_min,
                end_min=end_min,
                appliance_type=appliance,
                programme=sig.programme,
                signature_id=sig.signature_id,
                signature_seed=int(sgen.integers(0, 2**62)),
                energy_wh=energy,
                peak_w=sig.peak_w,
                caused_by_activity_id=activity_id,
                flexible=sig.flexible,
                zone=zone,
            )
        )

    # ---- activity-triggered cycles -------------------------------------
    #
    # Shared appliances are driven by household EPISODES and per-person ones by
    # the raw intervals, so the two are walked separately. Episodes first, in
    # their own deterministic order, then the per-person pass: fixing the order
    # fixes the cycle ids.
    for ep in build_episodes(activities):
        rules = TRIGGERS.get(ep.activity)
        if not rules:
            continue
        for rule in rules:
            appliance = rule["appliance"]
            if appliance not in SHARED_WITHIN_EPISODE:
                continue
            p = float(rule["p"])
            if rule.get("weather_dependent"):
                # Design 5.6: "washer then dryer or indoor airing,
                # weather-dependent". Rain makes the dryer much more likely,
                # because the washing cannot go on the line. The functional form
                # is a declared assumption; the DIRECTION is not in doubt.
                dry_outside = rain_mm_day < 0.5 and ghi_day_wh_m2 > 1500.0
                p = 0.18 if dry_outside else min(p * 1.4, 0.95)
            if float(gen.random()) > p:
                continue
            lo, hi = rule["n"]
            n = int(gen.integers(lo, hi + 1))
            extra_p = EXTRA_CYCLE_PER_EXTRA_PARTICIPANT.get(appliance)
            if extra_p and ep.n_participants > 1:
                n += int(gen.binomial(ep.n_participants - 1, extra_p))
            for _ in range(n):
                jitter = int(gen.integers(0, ep.duration_min))
                emit(appliance, min(ep.start_min + jitter, MINUTES_PER_DAY - 1),
                     ep.activity_id, ep.zone)

    for act in activities:
        rules = TRIGGERS.get(act.activity)
        if not rules:
            continue
        if act.location_kind != "building":
            continue
        for rule in rules:
            appliance = rule["appliance"]
            if appliance not in PER_PERSON_APPLIANCES:
                # Either it is shared (handled above) or it is in no list at
                # all, which is a declaration gap and must not pass silently.
                if appliance not in SHARED_WITHIN_EPISODE:
                    raise ApplianceError(
                        f"appliance {appliance!r} appears in TRIGGERS but in "
                        f"neither SHARED_WITHIN_EPISODE nor "
                        f"PER_PERSON_APPLIANCES. Declare which it is: whether "
                        f"one cycle serves the household or one person changes "
                        f"its daily energy by the household size (I-027)."
                    )
                continue
            if float(gen.random()) > float(rule["p"]):
                continue
            lo, hi = rule["n"]
            for _ in range(int(gen.integers(lo, hi + 1))):
                jitter = int(gen.integers(0, max(act.duration_min, 1)))
                emit(appliance, min(act.start_min + jitter, MINUTES_PER_DAY - 1),
                     getattr(act, "activity_id", None), act.zone)

    # ---- always-on loads, emitted once per day -------------------------
    for appliance in ("standby", "fridge_freezer", "lighting"):
        info = owned.get(appliance)
        if info is None:
            continue
        if appliance == "fridge_freezer":
            # The compressor cycles all day: one cycle per nominal period.
            sig = signature_for(appliance)
            period = max(sig.nominal_duration_s // 60, 1)
            for start in range(0, MINUTES_PER_DAY, period):
                emit(appliance, start, None, "kitchen")
        elif appliance == "lighting":
            # Lighting needs BOTH darkness and someone at home.
            #
            # An earlier version emitted one cycle an hour around the clock,
            # which gave 4.1 kWh of lighting a day - roughly three times a whole
            # Irish household's lighting use, and burning at 3 a.m. in an empty
            # house. Lighting is the one load that is driven almost entirely by
            # daylight, so it is driven by the day's actual irradiance here, and
            # gated on occupancy.
            dark_threshold = 60.0        # W/m2: dusk, roughly
            for start in range(0, MINUTES_PER_DAY, 60):
                if ghi_by_minute is not None:
                    hour_ghi = float(
                        np.mean(ghi_by_minute[start:min(start + 60, MINUTES_PER_DAY)])
                    )
                    if hour_ghi > dark_threshold:
                        continue
                if occupied_by_minute is not None:
                    if not bool(
                        np.any(occupied_by_minute[start:min(start + 60, MINUTES_PER_DAY)])
                    ):
                        continue
                elif 1 * 60 <= start < 6 * 60:
                    # With no occupancy series, at least do not light an
                    # obviously sleeping house through the small hours.
                    continue
                emit(appliance, start, None, "living")
        else:
            emit(appliance, 0, None, "living")
    return cycles


#: Appliance types whose energy is cooking, for the gas-cooking split (U25).
COOKING_TYPES: frozenset[str] = frozenset({"hob", "oven"})


def render_household_minutes(
    cycles: list[ApplianceCycle], *, n_minutes: int = MINUTES_PER_DAY,
    suppress_types: frozenset[str] | set[str] | None = None,
) -> dict[str, np.ndarray]:
    """Render every cycle to a 1-minute power series, by appliance category.

    Categories match the terms design 7.2's energy-closure invariant names, so
    the balance can be checked term by term rather than against one total:

        Sigma appliance + HVAC + EV + BESS charge - PV - BESS discharge
            = net meter

    Each cycle is rendered at 1 Hz from its signature and seed, then averaged
    into minutes. Averaging rather than sampling is what preserves energy: a
    kettle that runs for 100 seconds inside one minute contributes its full
    energy to that minute, where a 1-sample-per-minute probe would miss it
    entirely or over-count it by 60x depending on where the sample fell.
    """
    from baile_nua.devices.signatures import SIGNATURE_LIBRARY

    by_id = {s.signature_id: s for s in SIGNATURE_LIBRARY.values()}
    cats = {
        "appliance_w": np.zeros(n_minutes, dtype=np.float64),
        "hvac_w": np.zeros(n_minutes, dtype=np.float64),
        "ev_w": np.zeros(n_minutes, dtype=np.float64),
    }
    hvac_types = {"heat_pump", "storage_heater", "immersion_heater"}
    ev_types = {"ev_charger"}
    # U25. A home that cooks with gas must not also draw the electricity for
    # it. The suppressed energy is returned rather than discarded, because it
    # is what the gas figure is computed from: the same useful cooking,
    # delivered by a burner at a burner's efficiency.
    suppress = frozenset(suppress_types or ())
    suppressed_wh: dict[str, float] = {}

    for cyc in cycles:
        sig = by_id.get(cyc.signature_id)
        if sig is None:
            continue
        if cyc.appliance_type in suppress:
            suppressed_wh[cyc.appliance_type] = (
                suppressed_wh.get(cyc.appliance_type, 0.0) + float(cyc.energy_wh)
            )
            continue
        dur_s = max(cyc.duration_s, 1)
        power_1hz = render_cycle(
            sig, duration_s=dur_s, energy_wh=cyc.energy_wh,
            seed=cyc.signature_seed, rate_hz=1.0,
        )
        # Average each 60-second block into its minute.
        n_min = max(len(power_1hz) // 60, 1)
        usable = n_min * 60
        if usable <= len(power_1hz):
            per_min = power_1hz[:usable].reshape(n_min, 60).mean(axis=1)
            # Any remainder keeps its energy by being folded into the last minute.
            if usable < len(power_1hz):
                tail = power_1hz[usable:]
                per_min[-1] += tail.sum() / 60.0
        else:
            per_min = np.array([power_1hz.sum() / 60.0])

        key = (
            "hvac_w" if cyc.appliance_type in hvac_types
            else "ev_w" if cyc.appliance_type in ev_types
            else "appliance_w"
        )
        a = cyc.start_min
        b = min(a + len(per_min), n_minutes)
        if b > a:
            cats[key][a:b] += per_min[: b - a]
    cats["_suppressed_wh"] = suppressed_wh       # type: ignore[assignment]
    return cats


def household_day_energy(
    *,
    appliance_w: np.ndarray,
    hvac_w: np.ndarray,
    ev_w: np.ndarray,
    bess_charge_w: np.ndarray,
    bess_discharge_w: np.ndarray,
    pv_w: np.ndarray,
    dhw_w: np.ndarray | None = None,
    dt_s: float = 60.0,
) -> dict[str, Any]:
    """Assemble the net meter and return design 7.2's energy balance.

        Sigma appliance + HVAC + EV + BESS charge - PV - BESS discharge
            = net meter, within 0.1% of daily energy.

    The net meter is **constructed** from exactly those terms, so the identity
    holds to floating-point precision by construction. That is deliberate and it
    is not circular: the invariant's purpose is to catch a term being *dropped*
    or double-counted somewhere upstream, and it still does - if the appliance
    renderer loses a cycle's energy, or the battery's conversion loss is not
    accounted, the sum will not match the independently computed gross.

    Import and export are separated the way a meter separates them: a meter
    does not report a signed number, it has two registers, and a home that
    exports for part of an interval and imports for the rest increments both.
    """
    n = len(appliance_w)
    # U25. Hot water is its own term rather than being folded into
    # `appliance_w`, because it is the most flexible load in the house - an
    # immersion with a thermostat and a tank is a battery with a different
    # name - and the RL work the dataset exists for needs to see it separately
    # from a kettle. Optional so that every existing caller and the E1
    # artefacts they produced are unaffected.
    if dhw_w is None:
        dhw_w = np.zeros(n, dtype=np.float64)
    arrays = {
        "appliance_w": appliance_w, "hvac_w": hvac_w, "ev_w": ev_w,
        "bess_charge_w": bess_charge_w, "bess_discharge_w": bess_discharge_w,
        "pv_w": pv_w, "dhw_w": dhw_w,
    }
    for name, arr in arrays.items():
        if len(arr) != n:
            raise ValueError(f"{name} has length {len(arr)}, expected {n}")

    net_w = (
        np.asarray(appliance_w, dtype=np.float64)
        + np.asarray(hvac_w, dtype=np.float64)
        + np.asarray(ev_w, dtype=np.float64)
        + np.asarray(dhw_w, dtype=np.float64)
        + np.asarray(bess_charge_w, dtype=np.float64)
        - np.asarray(pv_w, dtype=np.float64)
        - np.asarray(bess_discharge_w, dtype=np.float64)
    )
    import_w = np.clip(net_w, 0.0, None)
    export_w = np.clip(-net_w, 0.0, None)

    h = dt_s / 3600.0
    terms = {k: float(np.asarray(v, dtype=np.float64).sum()) * h for k, v in arrays.items()}
    net_meter_wh = float(net_w.sum()) * h
    expected_wh = (
        terms["appliance_w"] + terms["hvac_w"] + terms["ev_w"]
        + terms["dhw_w"]
        + terms["bess_charge_w"] - terms["pv_w"] - terms["bess_discharge_w"]
    )
    residual_wh = net_meter_wh - expected_wh
    gross_wh = sum(abs(v) for v in terms.values())
    relative = abs(residual_wh) / gross_wh if gross_wh > 0 else 0.0

    return {
        "net_w": net_w,
        "import_w": import_w,
        "export_w": export_w,
        "terms_wh": {k.replace("_w", "_wh"): round(v, 6) for k, v in terms.items()},
        "net_meter_wh": net_meter_wh,
        "import_wh": float(import_w.sum()) * h,
        "export_wh": float(export_w.sum()) * h,
        "expected_wh": expected_wh,
        "residual_wh": residual_wh,
        "gross_wh": gross_wh,
        "relative_residual": relative,
        "closes_within_0_1_pct": relative <= 0.001,
    }
