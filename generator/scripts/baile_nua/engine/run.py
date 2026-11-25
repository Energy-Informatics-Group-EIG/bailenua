"""The E1 run engine: one full year of the 50-home estate (design 8.2, E0-7).

Design 8.2's two-phase day, in C1 coupling (E0-7):

    **Phase A, plan (serial, deterministic).**  At 04:00 each simulated day,
    town-level resolution runs in fixed ID order... The output is a frozen daily
    exchange log.

    **Phase B, execute (parallel).**  Households simulate the day in 15-minute
    epochs.  Inside an epoch each household is independent... Nothing crosses
    households except through the exchange log or the barrier.

    **Epoch barrier.**  Network power flow runs on all homes' net load...  All
    reductions run in sorted ID order.

**What C1 means for E1 and what it does not.**  C1 is 15-minute network epochs
with a 1-minute device and physics step.  The network solve at the barrier is a
*feeder aggregation* here rather than a full power flow: design 9.3's revision-3
table moves C2, the timing contract and `pandapower` to weeks 2 and 3, and
design 8.2 marks C2 "mandatory for network-sensitive research", so E1 makes no
network claim at all.  :data:`NETWORK_CLAIM` says so, and travels with the
output.

**Why the structure is worth keeping even without the power flow.**  The
two-phase day is what makes the run reproducible at any worker count: Phase A
resolves everything that crosses households, serially and in id order, and
freezes it; Phase B then cannot create a cross-household dependency even by
mistake, because the only thing it can read is a frozen log.
"""

from __future__ import annotations

import dataclasses
from concurrent.futures import ThreadPoolExecutor
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from baile_nua.activity.engine import ActivityEngine, PersonProfile
from baile_nua.checkpoint import Checkpoint, CheckpointStore, ExchangeLog
from baile_nua.devices import appliances as appl
from baile_nua.devices import der as der_mod
from baile_nua.engine.calendar import CalendarDay
from baile_nua.behaviour import comfort_taking as comfort_mod
from baile_nua.physics import dhw as dhw_mod
from baile_nua.physics.rc import (
    RCState,
    ThermalParams,
    glazing_incident_w_m2,
    simulate_day,
)
from baile_nua.reduce import sorted_sum_arrays
from baile_nua.rng import SeedTree, Stream

__all__ = [
    "HouseholdState",
    "DayResult",
    "EstateRunner",
    "NETWORK_CLAIM",
    "MINUTES_PER_DAY",
    "EPOCH_MINUTES",
]

MINUTES_PER_DAY = 1440
#: C1: 15-minute network epochs (design 8.2 coupling modes).
EPOCH_MINUTES = 15

NETWORK_CLAIM = (
    "E1 runs coupling mode C1: 15-minute network epochs with a 1-minute device "
    "and physics step. The epoch barrier aggregates net load onto the feeder; "
    "it does NOT solve a power flow. Design 8.2 marks C2 mandatory for "
    "network-sensitive research and design 9.3 moves C2, the co-simulation "
    "timing contract and pandapower to weeks 2 and 3. No voltage, loading, "
    "curtailment or network-constraint claim is made from E1 output."
)


@dataclasses.dataclass
class HouseholdState:
    """What carries from one day to the next for one household."""

    household_id: str
    building_id: str
    rc: RCState
    battery: der_mod.Battery | None
    ev: der_mod.ElectricVehicle | None
    #: Appliances out of service, and the day they return.
    failed_appliances: dict[str, int] = dataclasses.field(default_factory=dict)
    #: U25. The cylinder temperature carries across days like the RC state
    #: does, and so it has to be in the checkpoint: a replay that restored the
    #: fabric temperatures but not the tank would diverge on the first morning
    #: shower. That is the reproducibility contract doing its job rather than
    #: an inconvenience.
    dhw: dhw_mod.TankState | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "household_id": self.household_id,
            "building_id": self.building_id,
            "rc": dataclasses.asdict(self.rc),
            "battery_soc": self.battery.soc if self.battery else None,
            "ev_soc": self.ev.soc if self.ev else None,
            "failed_appliances": dict(self.failed_appliances),
            "dhw_tank_c": self.dhw.temp_c if self.dhw else None,
        }


@dataclasses.dataclass
class DayResult:
    sim_day: int
    date: str
    n_households: int
    n_activity_intervals: int
    n_cycles: int
    #: Per-household daily energy rows, for the closure invariant.
    energy_rows: list[dict[str, Any]]
    #: Feeder net load at 15-minute epochs, summed in sorted id order.
    feeder_epoch_w: np.ndarray
    presence_rows: list[dict[str, Any]]
    diagnostics: dict[str, Any]
    #: One day of 1-minute series per building, for the observation and export
    #: layers. Held for ONE day only - about 37 MB for 50 homes - and dropped
    #: when the day's rows have been written. The alternative, re-simulating to
    #: observe, would make the observation layer unable to see the same truth
    #: the ground-truth datasets record, which is the one thing it must do.
    series: dict[str, dict[str, np.ndarray]] = dataclasses.field(default_factory=dict)
    #: The day's appliance cycles, as D13 rows want them.
    cycles: list[Any] = dataclasses.field(default_factory=list)
    #: I-052. Estate-wide people asleep per minute, and the estate's headcount,
    #: so the overnight load can be read per AWAKE person rather than per home.
    asleep_by_minute: np.ndarray | None = None
    n_people_total: float = 0.0
    #: S11 / C2. Per-connection net power at the 15-minute epoch barrier,
    #: ``{building_id: array of EPOCHS_PER_DAY}``. The input a quasi-static
    #: power flow needs; the feeder total cannot serve, because it is already
    #: the quantity the flow would be asked to produce.
    net_epoch_w_by_building: dict[str, np.ndarray] = dataclasses.field(
        default_factory=dict)
    #: D10. The day's activity intervals, flattened in sorted household order
    #: and already resolved to what D10's ten fields need. The engine
    #: materialises these every day and used to drop them, keeping only the
    #: count; carried here so the writer can buffer them like D11 and D13.
    #: Held for ONE day and dropped once the day's rows are buffered.
    activity_rows: list[dict[str, Any]] = dataclasses.field(
        default_factory=list)


#: The setpoint a vacant dwelling is held at. Frost protection, not comfort:
#: nobody is asking for 20 C in an empty house. DEAP has no vacancy case, so
#: this is a declared assumption [A] - but a narrow one, because a vacant
#: home's heat demand at 7 C is close to nothing for most of the Irish year
#: and the quantity it changes is a standing baseline, not a peak.
VACANT_FROST_SETPOINT_C = 7.0


class EstateRunner:
    """Runs the E1 estate for a span of days."""

    def __init__(
        self,
        *,
        master_seed: int,
        households: dict[str, list[PersonProfile]],
        buildings: dict[str, Any],
        thermal: dict[str, ThermalParams],
        owned: dict[str, dict[str, dict[str, Any]]],
        pv: dict[str, der_mod.PVSystem],
        weather_minute: pd.DataFrame,
        calendar: list[CalendarDay],
        checkpoint_root: Path | None = None,
        income_quintile: dict[str, int] | None = None,
        comfort_taking: bool = True,
        comfort_strength: float = 1.0,
        behaviour: Any = None,
        sim_day_origin: int = 0,
    ) -> None:
        #: Phase 2. The sim_day that `weather_minute` row 0 belongs to.
        #:
        #: `run_day` slices the weather at `sim_day * MINUTES_PER_DAY`, which
        #: assumes the array starts at sim_day 0. A chained segment carries a
        #: `sim_day_offset` so the seed tree never repeats across years
        #: (D-110), but its weather array still starts at its own row 0 - so
        #: the lookup has to be relative. Defaults to 0, which is exactly the
        #: old behaviour for every existing caller.
        self.sim_day_origin = int(sim_day_origin)
        self.tree = SeedTree(master_seed)
        self.households = {k: sorted(v, key=lambda p: p.person_id) for k, v in households.items()}
        # Week 2 step 4 ablations. Applied to the ENGINE's copy of the person
        # profiles, not to the synthesised population: the population is the
        # town and must not change between arms, or the arms would differ in
        # who lives there as well as in how they behave.
        _b = behaviour
        if _b is not None and not (_b.chronotype and _b.habit_variation):
            flattened: dict[str, list[PersonProfile]] = {}
            for hh, people in self.households.items():
                flattened[hh] = [
                    dataclasses.replace(
                        pp,
                        chronotype=(pp.chronotype if _b.chronotype else 0.0),
                        habit_strength=(
                            pp.habit_strength if _b.habit_variation else 0.5
                        ),
                    )
                    for pp in people
                ]
            self.households = flattened
        self.buildings = buildings
        self.thermal = thermal
        self.owned = owned
        self.pv = pv
        self.weather = weather_minute
        self.calendar = calendar
        self.activity = ActivityEngine(
            self.tree,
            duration_weighted_timing=getattr(
                behaviour, "duration_weighted_timing", False),
        )
        # U25. One DHWSystem per household, built once from the dwelling's own
        # fuel, era and tank, with the diverter enabled only where there is PV
        # to divert. A dwelling the assignment has no story for would be left
        # with no hot water at all, so it is an error rather than a None: the
        # town's own fuel census found LPG and district heating missing that
        # way, 10 dwellings of 1,092.
        self.dhw_systems: dict[str, dhw_mod.DHWSystem] = {}
        self.cooking_fuel: dict[str, str] = {}
        # U22. Comfort-taking, as an ABLATION switch: the mechanism's whole
        # claim is that it flattens simulated gas across the fabric range the
        # way DBERNG01 does, and a claim like that is only worth anything if
        # the model can be run without it and compared.
        # Week 2 step 4. The behaviour switch set, defaulting to all-on (the
        # delivered model). `comfort_taking` stays a separate argument because
        # U22's ablation predates the matrix and its artefacts cite it.
        from baile_nua.validation.behaviour_ablation import BehaviourSwitches

        self.behaviour = behaviour or BehaviourSwitches()
        self.comfort_taking = bool(comfort_taking) and self.behaviour.comfort_taking
        # Scales the declared amplitudes, for the DBERNG01 calibration sweep.
        self.comfort_spec = dataclasses.replace(
            comfort_mod.DEFAULT_SPEC,
            rebound_k_per_ln_cost=(
                comfort_mod.DEFAULT_SPEC.rebound_k_per_ln_cost
                * float(comfort_strength)
            ),
            prebound_k_per_ln_cost=(
                comfort_mod.DEFAULT_SPEC.prebound_k_per_ln_cost
                * float(comfort_strength)
            ),
            rebound_max_hours_fraction=min(
                comfort_mod.DEFAULT_SPEC.rebound_max_hours_fraction
                * float(comfort_strength), 0.9
            ),
            prebound_max_hours_fraction=min(
                comfort_mod.DEFAULT_SPEC.prebound_max_hours_fraction
                * float(comfort_strength), 0.9
            ),
        )
        self.comfort_strength = float(comfort_strength)
        self.income_quintile = dict(income_quintile or {})
        self.comfort_shift: dict[str, dict[str, Any]] = {}
        for hh_id, b in sorted(buildings.items()):
            system = dhw_mod.dhw_system_for(b, has_pv=hh_id in pv)
            if system is None:
                raise ValueError(
                    f"no hot water system for {hh_id}: heating_fuel="
                    f"{getattr(b, 'heating_fuel', None)!r}, heating_system="
                    f"{getattr(b, 'heating_system', None)!r}. Every dwelling "
                    f"heats water somehow; add the case rather than leaving "
                    f"the dwelling without it."
                )
            self.dhw_systems[hh_id] = system
            # Static per dwelling and household, so computed once. The
            # mechanism never sees the weather or the day: it is a standing
            # preference, not a daily decision.
            if self.comfort_taking:
                loss = comfort_mod.specific_loss_w_k_m2(
                    thermal[hh_id], getattr(b, "floor_area_m2", 0.0)
                )
                self.comfort_shift[hh_id] = comfort_mod.comfort_shift(
                    specific_loss_w_k_m2=loss,
                    income_quintile=self.income_quintile.get(hh_id),
                    tenure=getattr(b, "tenure", None),
                    spec=self.comfort_spec,
                )
            # Drawn once per dwelling from its own stream, so the draw does
            # not shift when anything else about the day changes.
            self.cooking_fuel[hh_id] = dhw_mod.cooking_fuel_for(
                b, self.tree.generator(
                    Stream.BUILDING_SYSTEMS, entity=f"{hh_id}:cooking"
                )
            )
        # I-054/I-062. DEAP Table 4c(4)'s efficiency adjustment for the
        # emitter a heat pump is connected to, per household. Populated ONLY
        # by a dated WP5 conversion (physics/passport_assets.py); a dwelling
        # that had a heat pump at t0 is absent from this map and keeps its
        # existing treatment. That asymmetry is deliberate and recorded as
        # I-064 rather than smuggled in: applying the derating retroactively
        # to the town's t0 heat pumps would move the E1 baseline and every
        # committed result, which is a separate decision from adding the
        # conversion that was missing.
        # WP7 venues. ``{person_id: {"school_venue_id", "workplace_venue_id"}}``
        # for the persistent types, and the venue stock for the per-visit
        # ones. Empty by default: a run without venues records
        # location_id=None exactly as every run did before WP7, so no earlier
        # artefact changes.
        self.venue_assignment: dict[str, dict[str, Any]] = {}
        self.venues_by_type: dict[str, list[str]] = {}
        self.hp_emitter_adjustment: dict[str, float] = {}
        #: WP5 measures installed on each dwelling during the run, so a later
        #: event can see what an earlier one did - smart controls fitted
        #: before a heat-pump conversion must still earn the compensated
        #: adjustment.
        self.wp5_measures: dict[str, set[str]] = {}
        self.store = CheckpointStore(checkpoint_root) if checkpoint_root else None
        self.state: dict[str, HouseholdState] = {}
        self._chain_head: str | None = None

    # -- initial state --------------------------------------------------------

    def _venue_for(self, iv: Any, sim_day: int) -> str | None:
        """Which venue a non-building interval happens at, if venues are loaded.

        Persistent types come from the person's own assignment, so a child is
        at the SAME school every day - which is what makes venue presence and
        person presence comparable at all; if the venue were redrawn daily the
        acceptance criterion would be a statement about a draw.

        Per-visit types are drawn from the stock of that type on a counter-
        based stream keyed by (person, day, activity), so the draw is
        reproducible and independent of what any other person does.
        """
        from baile_nua.population.venues import VENUE_TYPES

        if not self.venues_by_type:
            return None
        for vtype, spec in VENUE_TYPES.items():
            if iv.activity not in spec["activities"]:
                continue
            if spec["persistent"]:
                a = self.venue_assignment.get(iv.person_id) or {}
                key = ("school_venue_id" if "school" in vtype
                       else "workplace_venue_id")
                return a.get(key)
            pool = self.venues_by_type.get(vtype) or []
            if not pool:
                return None
            gen = self.tree.generator(
                Stream.VENUE_CHOICE,
                entity=f"{iv.person_id}:venue:{iv.activity}", sim_day=sim_day,
            )
            return pool[int(gen.integers(0, len(pool)))]
        return None

    def initialise(self) -> None:
        """Set each household's day-0 state.

        Indoor temperatures start at a plausible January value rather than at
        the setpoint, so the first days are a warm-up rather than a step change;
        the first week is excluded from any statistic that cares.
        """
        for hh_id in sorted(self.households):
            b = self.buildings[hh_id]
            gen = self.tree.generator(Stream.BUILDING_SYSTEMS, entity=hh_id, sim_day=0)
            batt = None
            ev = None
            if getattr(b, "has_battery", False):
                batt = der_mod.Battery(
                    capacity_wh=5000.0, max_charge_w=2500.0,
                    max_discharge_w=2500.0, soc=float(gen.uniform(0.3, 0.7)),
                )
            if getattr(b, "has_ev", False):
                ev = der_mod.ElectricVehicle(
                    battery_wh=58_000.0, charger_w=7400.0,
                    soc=float(gen.uniform(0.4, 0.9)),
                )
            system = self.dhw_systems[hh_id]
            # Started a little below setpoint rather than at it, for the same
            # reason the fabric starts at a January temperature: the first
            # days are a warm-up, not a step change.
            tank = dhw_mod.TankState(
                temp_c=float(system.setpoint_c - gen.uniform(0.0, 8.0))
            )
            self.state[hh_id] = HouseholdState(
                household_id=hh_id,
                building_id=b.building_id,
                dhw=tank,
                rc=RCState(
                    temp_living_c=float(gen.uniform(16.0, 19.5)),
                    temp_sleep_c=float(gen.uniform(14.5, 18.0)),
                    temp_env_c=float(gen.uniform(12.0, 15.0)),
                ),
                battery=batt, ev=ev,
            )

    # -- Phase A --------------------------------------------------------------

    def phase_a(
        self, day: CalendarDay, disruptions: dict[str, list[Any]]
    ) -> ExchangeLog:
        """Town-level resolution, serial and in fixed id order (design 8.2).

        Everything that crosses households is decided here and frozen, so
        Phase B cannot create a cross-household dependency.
        """
        log = ExchangeLog(sim_day=day.sim_day, date_iso=day.date.date().isoformat())
        log.calendar_events = [
            {
                "kind": "public holiday" if day.is_public_holiday else "ordinary day",
                "name": day.holiday_name,
                "is_workday": day.is_workday,
                "is_school_day": day.is_school_day,
                "season": day.season,
                "dst_transition": day.dst_transition,
                "is_storm_day": day.is_storm_day,
            }
        ]
        # Disruptions active today, resolved household by household in id order.
        today: dict[str, list[dict[str, Any]]] = {}
        health: dict[str, str] = {}
        for hh_id in sorted(self.households):
            active = [
                {
                    "kind": d.kind, "person_id": d.person_id,
                    "disruption_id": d.disruption_id, **d.detail,
                }
                for d in disruptions.get(hh_id, [])
                if d.active_on(day.sim_day)
            ]
            if active:
                today[hh_id] = active
            for a in active:
                if a["kind"] == "illness" and a.get("person_id"):
                    health[a["person_id"]] = "short illness"
        log.disruptions = today
        log.health_transitions = health
        return log.freeze()

    # -- Phase B --------------------------------------------------------------

    def _run_household(
        self,
        hh_id: str,
        day: CalendarDay,
        exchange: ExchangeLog,
        wxa: dict[str, Any],
        *,
        collect_presence: bool = False,
    ) -> dict[str, Any]:
        """One household's day.  A pure function of its own state and the day.

        Extracted from :meth:`run_day` so that the parallel region is a
        function rather than a loop body.  That is what makes the determinism
        contract testable rather than merely asserted: the only things this
        touches are ``self.state[hh_id]`` - which no other household reads -
        and read-only inputs, so mapping it across workers in any order and
        reducing in sorted id order must give the same bytes as running it
        serially.

        ``wxa`` is the day's weather as plain arrays, sliced once by the caller.
        Re-slicing the DataFrame per household would be both slower and a
        shared-object read from several workers at once.
        """
        temp_air = wxa["temp_air"]
        ghi = wxa["ghi"]
        dni = wxa["dni"]
        dhi = wxa["dhi"]
        zen = wxa["zen"]
        azi = wxa["azi"]
        glazing = wxa["glazing"]
        rain_day = wxa["rain_day"]
        ghi_day = wxa["ghi_day"]

        people = self.households[hh_id]
        presence_rows: list[dict[str, Any]] = []
        st = self.state[hh_id]
        disr = {
            p.person_id: [
                d for d in exchange.disruptions.get(hh_id, [])
                if d.get("person_id") in (p.person_id, None)
            ]
            for p in people
        }

        # ---- activities ------------------------------------------------
        hd = self.activity.generate_household_day(
            hh_id, people, sim_day=day.sim_day,
            is_workday=day.is_workday, is_school_day=day.is_school_day,
            season=day.season, disruptions=disr,
            # I-044: yesterday's day type, because a person's bedtime last
            # night is what decides whether they are awake in these small
            # hours - and a Friday night runs later than a Sunday one.
            was_workday=self._was_workday(day),
        )
        all_intervals = [iv for pd_ in hd.person_days.values() for iv in pd_.intervals]
        n_intervals = len(all_intervals)

        # ---- D10 rows --------------------------------------------------
        #
        # The intervals above, carried out of the day rather than dropped.
        # NOTHING is computed here that the day did not already compute:
        # `location_id` is resolved exactly as the D11 presence rows below
        # resolve it - the dwelling for an at-home interval, `_venue_for`
        # otherwise - so the two datasets cannot disagree about where a
        # person was. `_venue_for` is addressed through the counter-based
        # seed tree on a (person, day, activity) key of its own, so
        # resolving it on every day rather than only the first
        # `collect_presence_days` advances no other stream and changes no
        # other draw.
        activity_rows = [
            {
                "person_id": iv.person_id,
                "start_min": iv.start_min,
                "end_min": iv.end_min,
                "activity": iv.activity,
                "zone": iv.zone,
                "joint_with": list(iv.joint_with),
                "trigger": iv.trigger,
                "deliberated": bool(iv.deliberated),
                "location_id": (
                    st.building_id if iv.location_kind == "building"
                    else self._venue_for(iv, day.sim_day)
                ),
            }
            for iv in all_intervals
        ]

        # I-052. How many of this household's people are ASLEEP each minute,
        # wherever they are. Needed because the overnight comparison against
        # LP1 is only interpretable per awake person: a town whose load is
        # right and whose sleep timing is wrong looks the same, in aggregate,
        # as one whose sleep timing is right and whose appliances are wrong.
        # Dividing by the awake count separates them, which is how I-052
        # established that the standby floor and the awake count are both
        # right and the residual is what awake people are doing.
        asleep = np.zeros(MINUTES_PER_DAY, dtype=np.float64)
        for iv in all_intervals:
            if iv.activity in ("sleep", "nap"):
                asleep[iv.start_min:iv.end_min] += 1.0

        # ---- occupancy by minute and zone ------------------------------
        occ_living = np.zeros(MINUTES_PER_DAY, dtype=np.float64)
        occ_sleep = np.zeros(MINUTES_PER_DAY, dtype=np.float64)
        occupied = np.zeros(MINUTES_PER_DAY, dtype=bool)
        for iv in all_intervals:
            if iv.location_kind != "building":
                continue
            occupied[iv.start_min:iv.end_min] = True
            if iv.zone == "bedroom":
                occ_sleep[iv.start_min:iv.end_min] += 1.0
            else:
                occ_living[iv.start_min:iv.end_min] += 1.0
            if collect_presence:
                presence_rows.append(
                    {
                        "person_id": iv.person_id, "sim_day": day.sim_day,
                        "start_min": iv.start_min, "end_min": iv.end_min,
                        "location_kind": iv.location_kind,
                        "location_id": st.building_id, "zone": iv.zone,
                        "activity": iv.activity,
                    }
                )
                continue
        if collect_presence:
            for iv in all_intervals:
                if iv.location_kind != "building":
                    presence_rows.append(
                        {
                            "person_id": iv.person_id, "sim_day": day.sim_day,
                            "start_min": iv.start_min, "end_min": iv.end_min,
                            "location_kind": iv.location_kind,
                            # WP7. Was None on every venue row ever written,
                            # which is why check_venue_capacity - written,
                            # exported and documented - could never have
                            # passed: it groups by location_id.
                            "location_id": self._venue_for(iv, day.sim_day),
                            "zone": iv.zone,
                            "activity": iv.activity,
                        }
                    )

        # ---- appliance cycles ------------------------------------------
        owned = {
            k: v for k, v in self.owned.get(hh_id, {}).items()
            if st.failed_appliances.get(k, -1) < day.sim_day
        }
        cycles = appl.trigger_cycles(
            building_id=st.building_id, activities=all_intervals, owned=owned,
            seed_tree=self.tree, sim_day=day.sim_day,
            rain_mm_day=rain_day, ghi_day_wh_m2=ghi_day,
            ghi_by_minute=ghi, occupied_by_minute=occupied,
        )
        n_cycles = len(cycles)
        # U25. A gas-cooking home must not also draw the electricity for it,
        # so the hob and oven cycles are not rendered to a load at all; their
        # energy comes back as `_suppressed_wh` and becomes gas at the meter.
        # Three-way, from HEBEU34 and HEBEU106 rather than a single declared
        # share: all-gas, a gas hob with an electric oven (the "combination"
        # the CSO publishes, and the common real arrangement), or all electric.
        cooking = self.cooking_fuel.get(hh_id, "electricity")
        if cooking == "natural gas":
            suppressed_types = appl.COOKING_TYPES
        elif cooking == "gas hob electric oven":
            suppressed_types = frozenset({"hob"})
        else:
            suppressed_types = None
        cooks_with_gas = suppressed_types is not None
        cats = appl.render_household_minutes(
            cycles, n_minutes=MINUTES_PER_DAY,
            suppress_types=suppressed_types,
        )
        suppressed = cats.pop("_suppressed_wh", {}) or {}

        # ---- heating demand from the physics ---------------------------
        tp = self.thermal[hh_id]
        # Motivation: the comfort trait, as before.
        #
        # A VACANT dwelling has no comfort trait to read, because it has
        # nobody in it. WP5's ten-year life course produces vacancies - a
        # household moves out, or its last member dies - and a vacant house is
        # not absent from the network: it keeps its standing load and, if it
        # has heating at all, frost protection. Without this the runner raised
        # IndexError on `people[0]`, which is the right failure for an empty
        # household it had never been told could exist.
        if not people:
            setpoint = VACANT_FROST_SETPOINT_C
        else:
            setpoint = 20.0 + 0.6 * float(np.clip(people[0].comfort, -2, 2))
        # U22: opportunity and capability. The dwelling's cost per degree and
        # the household's means, as a shift on the temperature ASKED FOR and a
        # scaling of the window - never on the fabric (D-022).
        ct = self.comfort_shift.get(hh_id)
        hours_multiplier = 1.0
        sleep_zone_fraction = 1.0
        if ct is not None:
            setpoint += float(ct["setpoint_shift_c"])
            hours_multiplier = float(ct["hours_multiplier"])
            sleep_zone_fraction = float(ct["sleep_zone_heated_fraction"])
        heat_living, heat_sleep, sp_living, sp_sleep = self._heating_schedule(
            tp, st.rc, temp_air, occupied, setpoint, day,
            hours_multiplier=hours_multiplier,
            sleep_zone_fraction=sleep_zone_fraction,
            gate_on_occupancy=self.behaviour.occupancy_gated_heating,
        )
        internal_living = cats["appliance_w"] * 0.85
        phys = simulate_day(
            tp, st.rc,
            # The solver's solar term is aperture x incident, and the incident
            # irradiance is on the GLAZING (I-032). Passing GHI here applied a
            # horizontal-surface value to vertical windows.
            temp_ambient=temp_air, ghi=glazing,
            internal_gain_living_w=internal_living,
            internal_gain_sleep_w=np.zeros(MINUTES_PER_DAY),
            heat_living_w=heat_living, heat_sleep_w=heat_sleep,
            setpoint_living_c=sp_living, setpoint_sleep_c=sp_sleep,
            occupants_living=occ_living, occupants_sleep=occ_sleep,
        )
        physics_residual = float(phys["energy_j"]["relative_residual"])
        st.rc = phys["final_state"]

        # ---- heating electricity, via the heat pump COP where relevant --
        b = self.buildings[hh_id]
        # The heat the thermostat actually called for, not the capacity that
        # was available. Using the capacity would charge the home for heat it
        # never used, and would make the electricity and gas comparisons wrong
        # by the thermostat's duty cycle.
        heat_total = phys["heat_applied_w"]
        if getattr(b, "heating_system", "") == "heat pump":
            hp = der_mod.HeatPump(rated_thermal_w=tp.heat_emitter_w)
            cop = der_mod.heat_pump_cop(hp, temp_air)
            # I-062. DEAP Table 4c(4): a heat pump on the emitter it is
            # actually connected to, not on its rating-plate emitter. A
            # conversion that keeps the dwelling's existing radiators runs at
            # 0.70 of rated efficiency, which is the regulator's own figure
            # and the difference between modelling a retrofit and flattering
            # one. Absent for a t0 heat pump: see I-064.
            adj = self.hp_emitter_adjustment.get(hh_id)
            if adj is not None:
                cop = cop * float(adj)
            hvac_w = heat_total / np.clip(cop, 1.0, None)
        elif getattr(b, "heating_fuel", "") == "electricity":
            hvac_w = heat_total          # direct electric: COP 1
        else:
            hvac_w = np.zeros(MINUTES_PER_DAY)   # oil or gas: not electric

        # ---- PV, EV and battery ----------------------------------------
        pv_w = np.zeros(MINUTES_PER_DAY)
        if hh_id in self.pv:
            pv_w = der_mod.pv_output_w(
                self.pv[hh_id], ghi_w_m2=ghi, dni_w_m2=dni, dhi_w_m2=dhi,
                solar_zenith_deg=zen, solar_azimuth_deg=azi, temp_air_c=temp_air,
            )["ac_w"]

        ev_w = cats["ev_w"].copy()
        if st.ev is not None:
            ev_w = self._ev_day(st, day, temp_air, occupied)

        bess_c = np.zeros(MINUTES_PER_DAY)
        bess_d = np.zeros(MINUTES_PER_DAY)
        # NaN rather than zero where there is no battery: a home without
        # one has no state of charge, and zero would be a reading saying
        # the battery is empty. The observation layer skips an all-NaN
        # channel, which is how "no device fitted" reaches D18 as absence
        # rather than as a false measurement.
        bess_soc = np.full(MINUTES_PER_DAY, np.nan)
        if st.battery is not None:
            load = cats["appliance_w"] + hvac_w + ev_w
            for m in range(MINUTES_PER_DAY):
                r = st.battery.step(float(pv_w[m] - load[m]))
                bess_c[m] = r["charge_w"]
                bess_d[m] = r["discharge_w"]
                bess_soc[m] = st.battery.soc * 100.0

        # ---- hot water (U25) -------------------------------------------
        #
        # Run after the appliances and the physics because it needs both: the
        # draws come from the activity intervals, and the cylinder sits in the
        # dwelling so its standing loss depends on the air around it.
        dhw_system = self.dhw_systems[hh_id]
        dhw_state = st.dhw
        gen_dhw = self.tree.generator(
            Stream.BUILDING_SYSTEMS, entity=f"{hh_id}:dhw", sim_day=day.sim_day
        )
        has_electric_shower = "electric_shower" in owned
        draw_l = dhw_mod.draw_schedule(
            all_intervals, n_minutes=MINUTES_PER_DAY,
            electric_shower=has_electric_shower, gen=gen_dhw,
        )
        # Surplus PV, which is what a diverter actually sees: generation less
        # the house load before the tank is considered. Computing it from the
        # pre-DHW load is correct and also avoids a circularity - the diverter
        # cannot be sized from a load it is part of.
        pre_dhw_load = cats["appliance_w"] + hvac_w + ev_w
        pv_surplus = np.clip(pv_w - pre_dhw_load, 0.0, None)
        dhw_out = dhw_mod.simulate_dhw_day(
            dhw_system, dhw_state,
            draw_l=draw_l,
            pv_surplus_w=pv_surplus,
            # The airing cupboard follows the living zone, not the outdoor
            # air: a cylinder indoors loses heat to a heated house, and that
            # heat is not wasted - it is a gain to the dwelling, which DEAP
            # also accounts for.
            ambient_c=phys["temps"][:, 0],
            day_of_year=day.date.timetuple().tm_yday,
            immersion_permitted=dhw_mod.immersion_permitted_on(
                day.date.timetuple().tm_yday
            ),
            # An appliance-failure disruption on the immersion now reaches the
            # cylinder. It used to land on an appliance that the DHW rework
            # removed, which would have made the disruption a no-op.
            immersion_available=(
                st.failed_appliances.get("immersion_heater", -1) < day.sim_day
            ),
        )
        dhw_w = dhw_out["immersion_w"] + dhw_out["diverter_w"]

        # ---- the energy balance (design 7.2) ---------------------------
        bal = appl.household_day_energy(
            appliance_w=cats["appliance_w"], hvac_w=hvac_w, ev_w=ev_w,
            bess_charge_w=bess_c, bess_discharge_w=bess_d, pv_w=pv_w,
            dhw_w=dhw_w,
        )
        closure_residual = float(bal["relative_residual"])
        series = {
            "net_w": bal["net_w"],
            "appliance_w": cats["appliance_w"],
            "hvac_w": hvac_w,
            "ev_w": ev_w,
            "pv_w": pv_w,
            "bess_charge_w": bess_c,
            "bess_discharge_w": bess_d,
            "bess_soc_pct": bess_soc,
            "temp_living_c": phys["temps"][:, 0],
            "temp_sleep_c": phys["temps"][:, 1],
            "temp_env_c": phys["temps"][:, 2],
            "co2_living_ppm": phys["co2"][:, 0],
            "co2_sleep_ppm": phys["co2"][:, 1],
            "dhw_w": dhw_w,
            "dhw_tank_c": dhw_out["tank_c"],
            "heat_delivered_w": heat_total,
            "internal_gain_w": internal_living,
            "solar_incident_w_m2": glazing,
            "ach_effective": phys["ach_used"],
            "occupants_living": occ_living,
            "occupants_sleep": occ_sleep,
            "occupied": occupied.astype(np.float64),
        }

        energy_row = {
            "building_id": st.building_id, "date": day.date.date().isoformat(),
            "appliance_wh": bal["terms_wh"]["appliance_wh"],
            "hvac_wh": bal["terms_wh"]["hvac_wh"],
            "ev_wh": bal["terms_wh"]["ev_wh"],
            "bess_charge_wh": bal["terms_wh"]["bess_charge_wh"],
            "bess_discharge_wh": bal["terms_wh"]["bess_discharge_wh"],
            "pv_wh": bal["terms_wh"]["pv_wh"],
            "net_meter_wh": bal["net_meter_wh"],
            "import_wh": bal["import_wh"],
            "export_wh": bal["export_wh"],
            "dhw_wh": bal["terms_wh"]["dhw_wh"],
            "dhw_useful_kwh": dhw_out["useful_draw_kwh"],
            "dhw_standby_kwh": dhw_out["standby_loss_kwh"],
            "dhw_coil_kwh": dhw_out["coil_input_kwh"],
            "dhw_immersion_kwh": dhw_out["immersion_input_kwh"],
            "dhw_diverted_pv_kwh": dhw_out["diverted_pv_kwh"],
            "dhw_litres": dhw_out["litres"],
            "cooks_with_gas": cooks_with_gas,
            "cooking_fuel": cooking,
            "cooking_hob_useful_wh": float(suppressed.get("hob", 0.0)),
            "cooking_oven_useful_wh": float(suppressed.get("oven", 0.0)),
            "dhw_unmet_draws": dhw_out["n_unmet"],
            "heat_delivered_kwh": phys["energy_kwh"]["heat_delivered"],
            "temp_living_mean_c": float(phys["temps"][:, 0].mean()),
            "temp_living_min_c": float(phys["temps"][:, 0].min()),
            "co2_living_max_ppm": float(phys["co2"][:, 0].max()),
        "battery_soc_end": st.battery.soc if st.battery else None,
        "ev_soc_end": st.ev.soc if st.ev else None,
        }

        # ---- appliance failures from the exchange log -------------------
        for d in exchange.disruptions.get(hh_id, []):
            if d.get("kind") == "appliance_failure" and d.get("appliance"):
                st.failed_appliances[d["appliance"]] = day.sim_day + 7

        return {
            "household_id": hh_id,
            "building_id": st.building_id,
            # I-052. NOT in the per-minute series dict above: that dict is
            # D18's columns, so putting them there would have silently added
            # two fields to the delivered 1-minute dataset - one of them a
            # scalar among arrays.
            "asleep_by_minute": asleep,
            "n_people": float(len(people)),
            "n_intervals": n_intervals,
            "n_cycles": n_cycles,
            "cycles": cycles,
            "physics_residual": physics_residual,
            "closure_residual": closure_residual,
            "net_w": bal["net_w"],
            "series": series,
            "energy_row": energy_row,
            "presence_rows": presence_rows,
            "activity_rows": activity_rows,
        }


    def run_day(
        self,
        day: CalendarDay,
        exchange: ExchangeLog,
        *,
        collect_presence: bool = False,
        workers: int = 1,
    ) -> DayResult:
        """One simulated day for the whole estate.

        Households are independent within the day, so this loops over them in
        sorted id order; the loop is the parallel region in a worker build, and
        running it serially gives the same answer, which is the property the
        determinism test checks.
        """
        t0 = time.time()
        lo = (day.sim_day - self.sim_day_origin) * MINUTES_PER_DAY
        hi = lo + MINUTES_PER_DAY
        wx = self.weather.iloc[lo:hi]
        if len(wx) != MINUTES_PER_DAY:
            raise ValueError(
                f"weather slice for day {day.sim_day} (row {lo}, origin "
                f"{self.sim_day_origin}) has {len(wx)} minutes, expected "
                f"{MINUTES_PER_DAY}"
            )
        rain = wx["precip_mm"].to_numpy(dtype=np.float64)
        # Sliced once, read-only, and handed to every household: a DataFrame
        # slice per household would be both slower and a concurrent read of a
        # shared pandas object.
        _ghi = wx["ghi_w_m2"].to_numpy(dtype=np.float64)
        _dni = wx["dni_w_m2"].to_numpy(dtype=np.float64)
        _dhi = wx["dhi_w_m2"].to_numpy(dtype=np.float64)
        _zen = wx["solar_zenith_deg"].to_numpy(dtype=np.float64)
        _azi = wx["solar_azimuth_deg"].to_numpy(dtype=np.float64)
        wxa = {
            "temp_air": wx["temp_air_c"].to_numpy(dtype=np.float64),
            "ghi": _ghi,
            "dni": _dni,
            "dhi": _dhi,
            "zen": _zen,
            "azi": _azi,
            # Irradiance on the GLAZING, not the horizontal. Computed once for
            # the estate because it depends only on the sun and the orientation
            # mix, not on the dwelling (I-032).
            "glazing": glazing_incident_w_m2(
                ghi_w_m2=_ghi, dni_w_m2=_dni, dhi_w_m2=_dhi,
                solar_zenith_deg=_zen, solar_azimuth_deg=_azi,
            ),
            "rain_day": float(rain.sum()),
            "ghi_day": float(_ghi.sum()) / 60.0,
        }

        energy_rows: list[dict[str, Any]] = []
        presence_rows: list[dict[str, Any]] = []
        activity_rows: list[dict[str, Any]] = []
        net_by_household: dict[str, np.ndarray] = {}
        series: dict[str, dict[str, np.ndarray]] = {}
        all_cycles: list[Any] = []
        n_intervals = n_cycles = 0
        physics_residuals: list[float] = []
        closure_residuals: list[float] = []

        # ---- the parallel region ------------------------------------------
        #
        # Households are independent within the day, so this is a MAP over
        # households, reduced in sorted id order afterwards. Serial and
        # threaded execution must produce the same bytes, which is what the
        # determinism test checks at 1, 8 and max workers.
        ids = sorted(self.households)
        if workers and workers > 1:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {
                    hh_id: pool.submit(
                        self._run_household, hh_id, day, exchange, wxa,
                        collect_presence=collect_presence,
                    )
                    for hh_id in ids
                }
                # Collected in sorted id order, NOT in completion order: the
                # reduction below is order-sensitive in the last bits, and
                # as_completed would make the result depend on scheduling.
                per_household = [futures[hh_id].result() for hh_id in ids]
        else:
            per_household = [
                self._run_household(
                    hh_id, day, exchange, wxa, collect_presence=collect_presence,
                )
                for hh_id in ids
            ]

        asleep_total: np.ndarray | None = None
        n_people_total = 0.0
        for r in per_household:
            n_intervals += r["n_intervals"]
            n_cycles += r["n_cycles"]
            all_cycles.extend(r["cycles"])
            physics_residuals.append(r["physics_residual"])
            closure_residuals.append(r["closure_residual"])
            net_by_household[r["building_id"]] = r["net_w"]
            series[r["building_id"]] = r["series"]
            energy_rows.append(r["energy_row"])
            presence_rows.extend(r["presence_rows"])
            activity_rows.extend(r["activity_rows"])
            asleep_total = (asleep_total + r["asleep_by_minute"]
                            if asleep_total is not None
                            else r["asleep_by_minute"].copy())
            n_people_total += r["n_people"]


        # ---- epoch barrier: feeder aggregation in sorted id order ----------
        feeder_minute = sorted_sum_arrays(net_by_household) if net_by_household else np.zeros(
            MINUTES_PER_DAY
        )
        feeder_epoch = feeder_minute.reshape(
            MINUTES_PER_DAY // EPOCH_MINUTES, EPOCH_MINUTES
        ).mean(axis=1)
        # S11 / C2. Per-connection net power at the SAME epoch barrier, which
        # is what a power flow needs: the feeder total is already the answer a
        # power flow would be asked to produce, so solving from it would be
        # circular. Averaged over the epoch, not sampled at its start, because
        # the epoch's load is what the quasi-static flow is a statement about.
        #
        # Built in sorted id order like the feeder sum, so a worker build and a
        # serial build hand the solver the same dict in the same order.
        net_epoch_by_building = {
            bid: net_by_household[bid].reshape(
                MINUTES_PER_DAY // EPOCH_MINUTES, EPOCH_MINUTES).mean(axis=1)
            for bid in sorted(net_by_household)
        }

        return DayResult(
            sim_day=day.sim_day,
            date=day.date.date().isoformat(),
            n_households=len(self.households),
            n_activity_intervals=n_intervals,
            n_cycles=n_cycles,
            energy_rows=energy_rows,
            feeder_epoch_w=feeder_epoch,
            presence_rows=presence_rows,
            activity_rows=activity_rows,
            series=series,
            cycles=all_cycles,
            asleep_by_minute=asleep_total,
            n_people_total=n_people_total,
            net_epoch_w_by_building=net_epoch_by_building,
            diagnostics={
                "elapsed_s": round(time.time() - t0, 3),
                "max_physics_relative_residual": max(physics_residuals) if physics_residuals else 0.0,
                "max_energy_closure_relative_residual": max(closure_residuals) if closure_residuals else 0.0,
                "feeder_peak_w": float(feeder_epoch.max()),
                "feeder_min_w": float(feeder_epoch.min()),
                "coupling_mode": "C1",
                "epoch_minutes": EPOCH_MINUTES,
                "network_claim": NETWORK_CLAIM,
            },
        )

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def _heating_schedule(
        tp: ThermalParams, rc: RCState, temp_air: np.ndarray,
        occupied: np.ndarray, setpoint: float, day: CalendarDay,
        hours_multiplier: float = 1.0,
        sleep_zone_fraction: float = 1.0,
        gate_on_occupancy: bool = True,
    ) -> tuple[np.ndarray, np.ndarray]:
        """The timer: when the emitter is AVAILABLE, and at what setpoint.

        Returns ``(capacity_living, capacity_sleep, setpoint_living,
        setpoint_sleep)``. The thermostat itself lives inside the solver,
        because it has to see the room: this function decides only when the
        boiler may fire and what temperature is being asked for.

        Heating runs in two windows on a workday and one long one otherwise,
        and only when someone is home - which is the behaviour that makes the
        heating load respond to occupancy, and therefore makes occupancy
        inferable from the meter, which is what design 7.8 is about.

        What this used to do instead (I-033): it computed
        ``demand = (setpoint - outdoor_temperature) / 18`` and applied that
        fraction of the emitter for the whole window, never looking at the
        room. The room therefore sailed past its setpoint - a 40 C peak in
        nearly every month, including one at 22:15 in August - and the heating
        could not respond to solar or internal gain, so a bright winter day
        still got full output.
        """
        OPEN_LOOP = -999.0
        cap_l = np.zeros(MINUTES_PER_DAY)
        cap_s = np.zeros(MINUTES_PER_DAY)
        sp_l = np.full(MINUTES_PER_DAY, OPEN_LOOP)
        sp_s = np.full(MINUTES_PER_DAY, OPEN_LOOP)
        if day.season == "summer":
            windows = [(7 * 60, 8 * 60)]      # hot water only, in effect
        elif day.is_workday:
            windows = [(6 * 60 + 30, 9 * 60), (16 * 60 + 30, 22 * 60 + 30)]
        else:
            windows = [(8 * 60, 22 * 60 + 30)]
        # U22. Comfort-taking shortens or lengthens the window, and this term
        # carries more of the effect than the setpoint does: real prebound is
        # heating one room for two hours rather than the house for eight, not
        # sitting at 17 degC all evening.
        #
        # Shortened from the START of each window and extended at the END. A
        # household economising puts the heating on later rather than turning
        # it off before bed, and one taking comfort leaves it on longer in the
        # evening. Trimming symmetrically would have moved the morning window
        # earlier for a rebound household, which is the opposite of what the
        # extra comfort is for.
        if abs(hours_multiplier - 1.0) > 1e-9:
            adjusted = []
            for a, b in windows:
                length = b - a
                new_length = max(int(round(length * hours_multiplier)), 0)
                if new_length <= 0:
                    continue
                if new_length < length:
                    adjusted.append((a + (length - new_length), b))
                else:
                    adjusted.append((a, min(a + new_length, MINUTES_PER_DAY)))
            windows = adjusted

        # The sleeping zone is held cooler, which is what people actually do
        # and what makes the two zones worth having.
        setback = 3.0
        for a, b in windows:
            hi = min(b, MINUTES_PER_DAY)
            if hi <= a:
                continue
            seg = slice(a, hi)
            # Week 2 step 4: with occupancy gating off, the timer runs
            # regardless of whether anyone is home. That is both more gas and
            # a flatter profile - and it is the premise design 7.8's privacy
            # work rests on, since heating that did not follow occupancy would
            # make occupancy un-inferable from the meter.
            live = occupied[seg] if gate_on_occupancy else np.ones_like(
                occupied[seg], dtype=bool
            )
            cap_l[seg] = np.where(live, tp.heat_emitter_w * 0.75, 0.0)
            # U22: closing rooms. A prebounding household heats the living
            # space and lets the bedrooms go, which removes that zone's
            # losses rather than scaling its setpoint - the only way to
            # flatten consumption across a tenfold fabric range.
            cap_s[seg] = np.where(
                live, tp.heat_emitter_w * 0.25 * sleep_zone_fraction, 0.0
            )
            sp_l[seg] = np.where(live, setpoint, OPEN_LOOP)
            sp_s[seg] = np.where(live, setpoint - setback, OPEN_LOOP)
        return cap_l, cap_s, sp_l, sp_s

    def _ev_day(
        self, st: HouseholdState, day: CalendarDay,
        temp_air: np.ndarray, occupied: np.ndarray,
    ) -> np.ndarray:
        """Mary's EV pattern: unplug about 08:00, plug back in about 17:00.

        Design 5.9 names this as the built-in test signature, so it is
        implemented as such rather than as generic charging: the unplug and
        plug-in times are what the edge detector keys on, and they must survive
        a household composition change unchanged (which is the point of the
        Mary scenario).
        """
        ev = st.ev
        out = np.zeros(MINUTES_PER_DAY)
        if ev is None:
            return out
        gen = self.tree.generator(Stream.MOBILITY, entity=st.household_id, sim_day=day.sim_day)
        if day.is_workday:
            unplug = 8 * 60 + int(gen.normal(0, 12))
            plug = 17 * 60 + int(gen.normal(0, 18))
            km = float(np.clip(gen.normal(38.0, 12.0), 3.0, 140.0))
            ev.plugged_in = False
            ev.drive(km, float(temp_air[max(unplug, 0):min(plug, MINUTES_PER_DAY)].mean()))
            ev.plugged_in = True
            start = max(min(plug, MINUTES_PER_DAY - 1), 0)
        else:
            start = 10 * 60 + int(gen.integers(0, 240))
            if float(gen.random()) < 0.45:
                km = float(np.clip(gen.normal(22.0, 15.0), 2.0, 120.0))
                ev.drive(km, float(temp_air.mean()))
        for m in range(start, MINUTES_PER_DAY):
            r = ev.charge_step()
            out[m] = r["charge_w"]
            if r["charge_w"] <= 0.0:
                break
        return out

    def _was_workday(self, day: CalendarDay) -> bool | None:
        """Yesterday's day type, or None when this runner cannot know it.

        I-044: a person's bedtime last night decides whether they are awake in
        the small hours, and a Friday night runs later than a Sunday one.

        The lookup must be RELATIVE to this runner's calendar. A chained
        segment carries a `sim_day_offset` so the seed tree never repeats
        across years (D-110), so `calendar[day.sim_day - 1]` indexed past the
        end of a 365-entry list - or, on sim_day 0, wrapped to the LAST day of
        the year and silently used December's day type for 1 January.

        On the first day of a segment, yesterday belongs to the PREVIOUS
        segment and this runner does not hold its calendar, so the answer is
        None - the same value the very first day of any run has always used.
        That is 12 days out of 4,322 in the replay (D-134).
        """
        i = day.sim_day - self.sim_day_origin - 1
        if i < 0:
            return None
        return self.calendar[i].is_workday

    # -- checkpointing --------------------------------------------------------

    def restore(self, cp: Checkpoint) -> int:
        """Restore household state from a checkpoint.  Returns how many.

        Everything in :class:`HouseholdState` is restored, and anything the
        checkpoint does not carry is a gap the replay test will find: restoring
        a day and re-running it must reproduce that day exactly, so a piece of
        state the checkpoint forgot shows up as a divergence naming the
        household and the quantity. A whole-year re-run cannot find such a gap,
        because it never restores anything - it recomputes from day zero.
        """
        restored = 0
        for hh_id, d in sorted(cp.household_state.items()):
            st = self.state.get(hh_id)
            if st is None:
                raise KeyError(
                    f"checkpoint for day {cp.sim_day} holds household {hh_id}, "
                    f"which is not in this estate. Replaying one run's "
                    f"checkpoints against another run's slice would silently "
                    f"compare different towns."
                )
            st.rc = RCState(**d["rc"])
            if st.battery is not None and d.get("battery_soc") is not None:
                st.battery.soc = float(d["battery_soc"])
            if st.ev is not None and d.get("ev_soc") is not None:
                st.ev.soc = float(d["ev_soc"])
            st.failed_appliances = {
                k: int(v) for k, v in dict(d.get("failed_appliances", {})).items()
            }
            # U25's tank. The checkpoint has CARRIED `dhw_tank_c` since U25 was
            # wired in and this method ignored it, so every replayed day began
            # with the cylinder at its construction temperature instead of the
            # one the run recorded - and diverged on the morning reheat exactly
            # as U25's own docstring predicted it would. The gap was invisible
            # because the replay artefact was measured eleven hours BEFORE the
            # tank existed and was never re-measured (I-081).
            #
            # Only `temp_c` is restored, and that is sufficient rather than
            # partial: the other TankState fields are cumulative run totals
            # that `simulate_dhw_day` reports per day through its RETURN value,
            # so nothing written to D13, D16 or D19 reads them.
            if st.dhw is not None and d.get("dhw_tank_c") is not None:
                st.dhw.temp_c = float(d["dhw_tank_c"])
            restored += 1
        if restored != len(self.state):
            raise ValueError(
                f"checkpoint restored {restored} of {len(self.state)} "
                f"households. A partial restore makes a replay compare a "
                f"restored household against a warmed-up one."
            )
        return restored

    def checkpoint(self, day: CalendarDay, exchange: ExchangeLog) -> str | None:
        """Write a hash-chained checkpoint for the state at the start of ``day``.

        Called BEFORE the day is run, which is what makes a one-day replay
        possible: the checkpoint for day N plus the exchange log for day N are
        exactly the inputs day N consumes. Writing it after the day instead
        would record the state at the END of day N, and replaying "day N" from
        it would in fact be running day N+1 from the wrong calendar day.
        """
        if self.store is None:
            return None
        cp = Checkpoint(
            sim_day=day.sim_day,
            date_iso=day.date.date().isoformat(),
            run_id="E1-estate",
            master_seed=self.tree.master_seed,
            household_state={k: v.as_dict() for k, v in sorted(self.state.items())},
            previous_hash=self._chain_head,
        )
        self._chain_head = self.store.put(cp, exchange)
        return self._chain_head
