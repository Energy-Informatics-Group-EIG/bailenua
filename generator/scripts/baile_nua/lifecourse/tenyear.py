"""WP5: the ten-year life course, 2022-2031 (design 5.3, 5.9; D09, D03, D20).

Design 5.3 asks for ten years of a population that actually changes - births,
deaths, moves in and out through a vacancy chain, partnering, separation,
children leaving, employment changes, health states, retrofits and DER
adoption - and gives no hazard for any of them.
:mod:`baile_nua.lifecourse.hazards` closes that: nine of the eleven are
published Irish rates, five are ``[A]`` with a published bound and a search
record.

Three things make this scoreable rather than decorative.

**Every event is dated and caused.** A D09 :class:`~.events.LifeEvent` row
carries the cause; the cause is ground truth and goes to the scoring API, never
to a model.

**Every event that changes the building is a D03 passport event.** A retrofit,
an extension or an asset added or removed bumps the building's version and
records which parameters changed, so the building's state at any date is
reconstructible from the passport rather than from a note.

**Every event carries D20 change labels, and the tier is computed, not
declared.** The schema says ``detectable_from_tier`` is "the lowest tier at
which it is theoretically observable". That is a claim about channels, and
:data:`TIER_DEVICES` says which channels each tier has - so the tier is
*derived* from the channels a label's text actually appeals to
(:func:`lowest_tier_for`) and the acceptance test re-derives it. A label whose
text claims something its tier cannot see fails the test; so does one whose
tier is higher than it needs to be, because "lowest" is part of the contract.

That rule was written against the four hand-written Mary labels (design 5.9)
and reproduces all four of their tiers - T1, T2, T1, T3 - which is the
evidence that it is the rule the design meant, rather than one invented to
make this module pass.

What is NOT modelled, and why: new dwellings. URA26/URA27 publish completions,
but the slice is a fixed set of 60 existing buildings and E1's scope freezes
it, so a ten-year run cannot add homes without leaving the approved scope.
Moves therefore circulate households through the existing stock and its
vacancies, which is also what makes the vacancy chain a chain.
"""

from __future__ import annotations

import dataclasses
import math
from typing import Any, Callable, Iterable

import numpy as np

from baile_nua.lifecourse import hazards as HZ
from baile_nua.lifecourse.events import (
    ChangeLabel,
    LifeEvent,
    check_label_text,
    mary_scenario,
)
from baile_nua.observation.sensors import TIER_DEVICES
from baile_nua.rng import SeedTree, Stream

__all__ = [
    "TenYearConfig",
    "TenYearResult",
    "PassportEvent",
    "TierEvidence",
    "EVENT_EVIDENCE",
    "lowest_tier_for",
    "run_life_course",
    "check_invariants",
    "vital_statistics_intervals",
    "YearState",
    "MEASURE_REACHES_THE_SERIES",
    "OCCUPANCY_EVENTS",
    "occupancy_schedule",
    "passport_schedule",
]

START_YEAR = 2022
N_YEARS = 10
DAYS_PER_YEAR = 365


# --------------------------------------------------------------------------- #
# Tiers: which channels a claim appeals to, and therefore what can see it
# --------------------------------------------------------------------------- #

#: Tiers in increasing order of instrumentation.
TIER_ORDER: tuple[str, ...] = ("T1", "T2", "T3", "T4")


def lowest_tier_for(channels: Iterable[str]) -> str:
    """The lowest tier whose channel set contains every channel named.

    This is the whole of the ``detectable_from_tier`` contract. A label that
    says "wet-appliance cycle count rises" appeals to ``ct_circuit``, which T1
    does not have and T2 does, so the label is T2 - not because anyone decided
    so but because T1 cannot see it.
    """
    want = frozenset(channels)
    if not want:
        raise ValueError(
            "a D20 label must name at least one channel: a label that appeals "
            "to no measurement is not detectable at any tier, and recording it "
            "as T1 would be a free true positive for every detector."
        )
    for tier in TIER_ORDER:
        if want <= frozenset(TIER_DEVICES[tier]):
            return tier
    raise ValueError(
        f"no sensor tier carries all of {sorted(want)}; the highest, T4, has "
        f"{sorted(TIER_DEVICES['T4'])}. Either the channel name is wrong or "
        f"the change is not observable at all, and an unobservable change "
        f"must not be given a tier."
    )


@dataclasses.dataclass(frozen=True)
class TierEvidence:
    """What one kind of change is observable *in*, and for how long."""

    change_class: str          # safety | equipment | routine deviation | structural
    persistence: str           # transient | persistent | permanent
    channels: tuple[str, ...]
    text: str
    #: ``None`` for a change that never ends.
    duration_days: int | None = None

    @property
    def tier(self) -> str:
        return lowest_tier_for(self.channels)


#: One entry per event type the life course can produce. The text is written
#: in observable terms only (R25) and is passed through ``check_label_text``,
#: which refuses a label that names a cause.
EVENT_EVIDENCE: dict[str, TierEvidence] = {
    "birth": TierEvidence(
        change_class="structural", persistence="permanent",
        channels=("import_w",),
        text=("Overnight load no longer falls to a flat baseline between 01:00 "
              "and 05:00; wet-appliance running time per week rises"),
    ),
    "death": TierEvidence(
        change_class="structural", persistence="permanent",
        channels=("import_w",),
        text=("Occupied-hours pattern becomes consistent with one fewer "
              "occupant; daytime load falls towards a near-constant baseline"),
    ),
    "move_out": TierEvidence(
        change_class="structural", persistence="permanent",
        channels=("import_w",),
        text=("Load falls to a standing baseline with no daily activity "
              "structure and no hot-water draws"),
    ),
    "household_dissolved": TierEvidence(
        change_class="structural", persistence="permanent",
        channels=("import_w",),
        text=("Load falls to a standing baseline with no daily activity "
              "structure, following a period of declining occupied hours"),
    ),
    "move_in": TierEvidence(
        change_class="structural", persistence="permanent",
        channels=("import_w",),
        text=("A daily activity structure appears where load was a flat "
              "standing baseline"),
    ),
    "partnering": TierEvidence(
        change_class="structural", persistence="permanent",
        channels=("import_w",),
        text=("Occupied-hours pattern becomes consistent with one more "
              "occupant; evening load rises and broadens"),
    ),
    "separation": TierEvidence(
        change_class="structural", persistence="permanent",
        channels=("import_w",),
        text=("Occupied-hours pattern becomes consistent with one fewer "
              "occupant; evening load falls and narrows"),
    ),
    "child_leaves_home": TierEvidence(
        change_class="structural", persistence="permanent",
        channels=("import_w", "co2"),
        text=("Evening and late-night load fall; one sleeping zone's overnight "
              "CO2 settles at a level consistent with nobody sleeping there"),
    ),
    "employment_change": TierEvidence(
        change_class="routine deviation", persistence="persistent",
        channels=("import_w",),
        text=("Weekday daytime load no longer falls to the unoccupied "
              "baseline between 09:00 and 17:00, while weekends are unchanged"),
    ),
    "health_state_onset": TierEvidence(
        change_class="routine deviation", persistence="persistent",
        channels=("import_w", "temp"),
        text=("Weekday daytime occupancy rises and the living-zone "
              "temperature is held one to two degrees higher for more hours "
              "of the day"),
    ),
    # --- building changes: D03 passport events -----------------------------
    "retrofit_fabric": TierEvidence(
        change_class="equipment", persistence="permanent",
        channels=("temp",),
        # A fabric retrofit on a gas- or oil-heated home moves almost no
        # electricity, so T1 genuinely cannot see it; the free-running
        # temperature decay can.
        text=("Free-running living-zone temperature decay slows: the same "
              "outdoor conditions produce a smaller indoor fall per hour "
              "with no heat delivered"),
    ),
    "retrofit_heat_pump": TierEvidence(
        change_class="equipment", persistence="permanent",
        channels=("import_w",),
        text=("A sustained multi-hour load of one to three kilowatts appears "
              "on cold days where none existed, correlated with outdoor "
              "temperature"),
    ),
    "der_pv": TierEvidence(
        change_class="equipment", persistence="permanent",
        channels=("export_w",),
        text=("Daytime export appears, peaking near solar noon and scaling "
              "with clear-sky conditions"),
    ),
    "der_battery": TierEvidence(
        change_class="equipment", persistence="permanent",
        channels=("import_w", "export_w", "bess_soc"),
        # Net load alone is ambiguous between a battery and a changed routine;
        # the state of charge is what identifies it, and only T4 has it.
        text=("Stored-energy state of charge cycles daily between a lower and "
              "an upper bound, with charge and discharge mirrored in net "
              "import and export"),
    ),
    "der_smart_controls": TierEvidence(
        change_class="equipment", persistence="permanent",
        channels=("import_w", "temp"),
        text=("Heating delivery becomes a sequence of shorter modulated "
              "intervals and the living-zone temperature band narrows"),
    ),
    "extension": TierEvidence(
        change_class="structural", persistence="permanent",
        channels=("temp",),
        text=("Heat input needed to hold the same living-zone temperature "
              "rises against the same outdoor conditions"),
    ),
}


# --------------------------------------------------------------------------- #
# D03 Building Energy Passport
# --------------------------------------------------------------------------- #

@dataclasses.dataclass
class PassportEvent:
    """A D03 row: a dated change to the building itself."""

    passport_event_id: str
    building_id: str
    event_type: str
    #: I-062. The WP5 measure this event installs. ``event_type`` is D03's own
    #: vocabulary and is too coarse to dispatch on: all four DER and heat-pump
    #: measures are "asset added", so an engine keying on it could only apply
    #: one of them or none. Carried on the internal record and NOT on
    #: ``as_d03_row``, which stays exactly as D03's schema defines it.
    measure: str
    effective_day: int
    decided_day: int | None
    from_version: int
    to_version: int
    parameters_changed: dict[str, Any]
    driver: str
    life_event_id: str | None

    def as_row(self) -> dict[str, Any]:
        """The internal record: sim-day integers, as the engine uses them."""
        return dataclasses.asdict(self)

    def as_d03_row(self, start_date: str = "2022-01-01") -> dict[str, Any]:
        """A row conforming to D03's schema, with real timestamps.

        D03 requires ``effective_at`` and optionally ``decided_at``, both
        timestamps. The engine works in sim-day integers, which is right for
        the engine and wrong for the dataset - and a mismatch that nothing
        would have caught until week 3 wrote D17 and D03 for the network work,
        because neither is written to a package yet. Checked by
        ``test_schema_conformance_of_the_new_dataset_rows``.
        """
        import pandas as pd

        base = pd.Timestamp(start_date).tz_localize("UTC")
        return {
            "passport_event_id": self.passport_event_id,
            "building_id": self.building_id,
            "event_type": self.event_type,
            "effective_at": (base + pd.Timedelta(days=self.effective_day)),
            "decided_at": (
                None if self.decided_day is None
                else base + pd.Timedelta(days=self.decided_day)
            ),
            "from_version": self.from_version,
            "to_version": self.to_version,
            "parameters_changed": self.parameters_changed,
            "driver": self.driver,
            "life_event_id": self.life_event_id,
        }


#: Which measures a retrofit or asset change can apply, keyed to the HEBEU37
#: category whose prevalence bounds how many homes may end up with it, and to
#: the D02 parameters the passport event changes.
MEASURES: dict[str, dict[str, Any]] = {
    "retrofit_fabric": {
        "hebeu37": None,                     # fabric is not an HEBEU37 category
        "parameters": ("rc_r_ie", "rc_r_ea", "rc_r_inf", "ber_band", "ber_kwh_m2_yr"),
        "passport_event_type": "retrofit",
    },
    "retrofit_heat_pump": {
        "hebeu37": "Heat pump",
        "parameters": ("heating_system", "heating_fuel", "ber_kwh_m2_yr"),
        "passport_event_type": "asset added",
    },
    "der_pv": {
        "hebeu37": "Photovoltaic (PV) solar panel",
        "parameters": ("pv_kwp", "pv_azimuth_deg", "pv_tilt_deg"),
        "passport_event_type": "asset added",
    },
    "der_battery": {
        "hebeu37": "Battery",
        "parameters": ("bess_kwh", "bess_kw"),
        "passport_event_type": "asset added",
    },
    "der_smart_controls": {
        "hebeu37": "Smart heating controls",
        "parameters": ("heating_control", "sri_class", "sri_score"),
        "passport_event_type": "asset added",
    },
    "extension": {
        "hebeu37": None,
        "parameters": ("floor_area_m2", "rc_c_living", "rc_vol_living_m3"),
        "passport_event_type": "extension",
    },
}


# --------------------------------------------------------------------------- #
# configuration and state
# --------------------------------------------------------------------------- #

@dataclasses.dataclass
class TenYearConfig:
    master_seed: int
    start_year: int = START_YEAR
    n_years: int = N_YEARS
    slice_kind: str = "u23_mixed_age"
    #: Mary's move-in is a scripted test case and runs alongside the
    #: stochastic events, in the first year, on the day e1_run already uses.
    mary_year_index: int = 0
    mary_move_in_day: int = 188


@dataclasses.dataclass
class Person:
    person_id: str
    age: int
    sex: str
    role: str
    econ_status: str
    household_id: str
    health_state: str = "well"
    partner_id: str | None = None
    parity: int = 0
    alive: bool = True
    resident: bool = True
    #: Which year index they left the slice in, if they did.
    left_year: int | None = None


@dataclasses.dataclass
class Dwelling:
    building_id: str
    household_id: str | None
    version: int = 1
    measures: set[str] = dataclasses.field(default_factory=set)
    vacant_since_year: int | None = None


@dataclasses.dataclass
class YearState:
    """The population and stock as they stand at the START of one year."""

    year: int
    year_index: int
    persons: dict[str, Person]
    dwellings: dict[str, Dwelling]
    households: dict[str, list[str]]        # household_id -> person_ids

    def n_people(self) -> int:
        return sum(1 for p in self.persons.values() if p.alive and p.resident)

    def n_occupied(self) -> int:
        return sum(1 for d in self.dwellings.values() if d.household_id is not None)

    def vacancy_rate(self) -> float:
        n = len(self.dwellings)
        return (n - self.n_occupied()) / n if n else 0.0


@dataclasses.dataclass
class TenYearResult:
    events: list[LifeEvent]
    labels: list[ChangeLabel]
    passport_events: list[PassportEvent]
    per_year: list[dict[str, Any]]
    counts: dict[str, int]
    invariants: dict[str, Any]
    vital_check: dict[str, Any]
    hazard_record: dict[str, Any]
    states: list[YearState] = dataclasses.field(default_factory=list)


# --------------------------------------------------------------------------- #
# hazard lookup helpers
# --------------------------------------------------------------------------- #

def _band_5yr(age: int) -> str:
    """The VSA08/PEA01 five-year band label an age falls in."""
    if age < 1:
        return "Under 1 year"
    if age < 5:
        return "1 - 4 years"
    if age >= 85:
        return "85 years and over"
    lo = (age // 5) * 5
    return f"{lo} - {lo + 4} years"


def _fertility_band(age: int) -> str | None:
    if age < 15 or age >= 50:
        return None
    lo = (age // 5) * 5
    return f"{lo} - {lo + 4} years"


def _single_year_label(age: int, available: set[str]) -> str | None:
    lab = f"{age} years"
    return lab if lab in available else None


@dataclasses.dataclass
class HazardTables:
    """Every published rate this run uses, read once."""

    fertility: dict[str, float]
    parity: dict[str, dict[int, float]]
    death: dict[tuple[str, str], float]
    marriage: dict[tuple[str, str], float]
    separation_job: dict[tuple[str, str], float]
    der: dict[str, float]
    chronic: dict[str, float]
    vacancy_cork: dict[str, float]
    vacancy_flows: dict[str, Any]
    net_migration: dict[str, float]
    assumed: dict[str, float]
    shas: dict[str, str]

    @classmethod
    def load(cls) -> "HazardTables":
        return cls(
            fertility=HZ.fertility_rates_by_age(),
            parity=HZ.parity_shares_by_age(),
            death=HZ.death_rates_by_age_sex(),
            marriage=HZ.marriage_rates_by_age_sex(),
            separation_job=HZ.job_separation_rate_by_age_sex(),
            der=HZ.der_prevalence(),
            chronic=HZ.chronic_condition_prevalence_50_plus(),
            vacancy_cork=HZ.vacancy_rate_cork_county(),
            vacancy_flows=HZ.vacancy_flow_rates(),
            net_migration=HZ.net_migration_per_1000(),
            assumed={a.flag: a.value for a in HZ.ASSUMED_HAZARDS},
            shas=HZ.source_shas(),
        )

    # -- per-person annual probabilities ------------------------------------

    def p_death(self, person: Person) -> float:
        return self.death.get((person.sex, _band_5yr(person.age)), 0.0) / 1000.0

    def p_birth(self, person: Person) -> float:
        """The published band rate, with no parity adjustment."""
        if person.sex != "Female":
            return 0.0
        band = _fertility_band(person.age)
        if band is None:
            return 0.0
        return self.fertility.get(band, 0.0) / 1000.0

    def parity_weight(self, person: Person) -> float:
        """How much more or less likely this parity is, before normalising.

        VSA36 gives the share of a band's births at each parity. The share is
        a RELATIVE weight only: used directly it rescales every woman's rate
        downwards and the band loses births, which is what the integrated
        hazard caught - 10.15 against an exposure expectation of 11.52. The
        caller normalises these weights to mean 1.0 within the band, so the
        parity term decides WHO gives birth and the published band rate
        decides HOW MANY do.
        """
        shares = self.parity.get(f"{person.age} years")
        if not shares:
            return 1.0
        return shares.get(person.parity, 0.0)

    def p_partner(self, person: Person) -> float:
        avail = {k[1] for k in self.marriage}
        lab = _single_year_label(person.age, avail)
        if lab is None:
            return 0.0
        return self.marriage.get((person.sex, lab), 0.0) / 1000.0

    def p_employment_change(self, person: Person) -> float:
        avail = {k[1] for k in self.separation_job}
        lab = _single_year_label(person.age, avail)
        if lab is None:
            return 0.0
        return self.separation_job.get((person.sex, lab), 0.0)

    def p_separation(self) -> float:
        return self.assumed["A-25c"]

    def p_move_out(self) -> float:
        return self.assumed["A-25b"]

    def p_child_leaves(self) -> float:
        return self.assumed["A-25d"]

    def p_health_onset(self, person: Person) -> float:
        if person.age < 50:
            return self.assumed["A-25e"]
        # At 50+ the onset rate is set so that HSPAE122's 1-or-more prevalence
        # is the stock it builds to over the remaining years, rather than an
        # assumed number: p such that the cohort reaches the published share.
        target = self.chronic.get("1 or more chronic conditions", 0.0)
        years_left = max(85 - person.age, 1)
        return 1.0 - (1.0 - target) ** (1.0 / years_left)

    def p_measure(self, measure: str) -> float:
        return self.assumed["A-25f"]

    def measure_cap(self, measure: str) -> float | None:
        """The HEBEU37 prevalence a measure's ten-year total must not exceed."""
        cat = MEASURES[measure]["hebeu37"]
        return None if cat is None else self.der.get(cat)


# --------------------------------------------------------------------------- #
# the run
# --------------------------------------------------------------------------- #

def _event_id(kind: str, year: int, n: int) -> str:
    return f"LE-{year}-{kind.upper()}-{n:04d}"


def _label_for(
    *, event: LifeEvent, building_id: str, evidence: TierEvidence, suffix: str
) -> ChangeLabel:
    """Build the D20 label for an event, with its tier DERIVED from channels."""
    end = (
        None if evidence.duration_days is None
        else event.effective_day + evidence.duration_days
    )
    return ChangeLabel(
        label_id=f"CL-{event.event_id}-{suffix}",
        building_id=building_id,
        change_class=evidence.change_class,
        true_onset_day=event.effective_day,
        true_end_day=end,
        persistence=evidence.persistence,
        source_event_ids=[event.event_id],
        detectable_from_tier=evidence.tier,
        observable_change_text=check_label_text(evidence.text),
    )


def run_life_course(
    *,
    config: TenYearConfig,
    persons: dict[str, Person],
    dwellings: dict[str, Dwelling],
    households: dict[str, list[str]],
    mary: dict[str, Any] | None = None,
) -> TenYearResult:
    """Run the ten-year life course and return every event, label and passport row.

    One annual step per year. Hazards are annual, so an event's day within the
    year is drawn uniformly - except the scripted Mary move-in, which is dated.

    Draws come from the counter-based tree keyed on the year, so year 7 is
    reproducible without replaying years 1 to 6 (the same property the daily
    engine relies on).
    """
    tab = HazardTables.load()
    tree = SeedTree(config.master_seed)

    events: list[LifeEvent] = []
    labels: list[ChangeLabel] = []
    passports: list[PassportEvent] = []
    per_year: list[dict[str, Any]] = []
    states: list[YearState] = []
    counts: dict[str, int] = {}
    exposure: dict[str, float] = {}
    next_person = 1
    next_hh = 1
    #: The hazard actually integrated over the draws actually taken, per event
    #: type. Compared against the exposure-based expectation in the vital
    #: check: if the two disagree the EXPOSURE accounting is wrong, which is a
    #: different bug from an unlucky seed and is invisible without this.
    integrated: dict[str, float] = {}

    def draw(kind: str, p_event: float) -> bool:
        integrated[kind] = integrated.get(kind, 0.0) + p_event
        return bool(gen.random() < p_event)

    persons = {k: dataclasses.replace(v) for k, v in persons.items()}
    dwellings = {k: dataclasses.replace(v, measures=set(v.measures))
                 for k, v in dwellings.items()}
    households = {k: list(v) for k, v in households.items()}
    hh_to_building = {
        d.household_id: bid for bid, d in dwellings.items()
        if d.household_id is not None
    }

    def bump(kind: str, n: int = 1) -> None:
        counts[kind] = counts.get(kind, 0) + n

    def building_of(hh_id: str) -> str | None:
        return hh_to_building.get(hh_id)

    def emit(
        kind: str, *, year_index: int, day: int, person_ids: list[str],
        household_id: str | None, cause: str, effects: dict[str, Any],
        decided_day: int | None = None, building_id: str | None = None,
    ) -> LifeEvent:
        bid = building_id or (building_of(household_id) if household_id else None)
        ev = LifeEvent(
            event_id=_event_id(kind, config.start_year + year_index,
                               counts.get(kind, 0) + 1),
            event_type=kind,
            effective_day=year_index * DAYS_PER_YEAR + day,
            decided_day=decided_day,
            persons=person_ids,
            household_id=household_id,
            building_id=bid,
            cause=cause,
            observable_effects=effects,
        )
        events.append(ev)
        bump(kind)
        ev_block = EVENT_EVIDENCE.get(kind)
        if ev_block is not None and bid is not None:
            labels.append(_label_for(
                event=ev, building_id=bid, evidence=ev_block, suffix="01",
            ))
        return ev

    for yi in range(config.n_years):
        year = config.start_year + yi
        state = YearState(
            year=year, year_index=yi,
            persons={k: dataclasses.replace(v) for k, v in persons.items()},
            dwellings={k: dataclasses.replace(v, measures=set(v.measures))
                       for k, v in dwellings.items()},
            households={k: list(v) for k, v in households.items()},
        )
        states.append(state)

        gen = tree.generator(Stream.LIFE_COURSE, entity="wp5", sim_day=yi)
        year_events_before = len(events)

        # ---- exposure, counted before anything changes it -----------------
        live = [p for p in persons.values() if p.alive and p.resident]
        exposure["person_years"] = exposure.get("person_years", 0.0) + len(live)
        exposure["household_years"] = (
            exposure.get("household_years", 0.0)
            + sum(1 for h in households.values() if h)
        )
        exposure["woman_years_15_49"] = exposure.get("woman_years_15_49", 0.0) + sum(
            1 for p in live if p.sex == "Female" and 15 <= p.age < 50
        )
        for p in live:
            b = _band_5yr(p.age)
            exposure[f"py:{p.sex}:{b}"] = exposure.get(f"py:{p.sex}:{b}", 0.0) + 1
            fb = _fertility_band(p.age)
            if p.sex == "Female" and fb:
                exposure[f"wy:{fb}"] = exposure.get(f"wy:{fb}", 0.0) + 1
            # Partnering exposure: the single adults actually at risk, keyed
            # the way VSA49 is keyed, so the expected count uses the published
            # rate at the ages the slice really had.
            if p.partner_id is None and p.age >= 18 and p.role != "child":
                exposure[f"sy:{p.sex}:{p.age}"] = (
                    exposure.get(f"sy:{p.sex}:{p.age}", 0.0) + 1
                )

        def day() -> int:
            return int(gen.integers(0, DAYS_PER_YEAR))

        # ---- 1. deaths ----------------------------------------------------
        for p in sorted(live, key=lambda x: x.person_id):
            if draw("death", tab.p_death(p)):
                p.alive = False
                p.resident = False
                p.left_year = yi
                hh = households.get(p.household_id, [])
                if p.person_id in hh:
                    hh.remove(p.person_id)
                if p.partner_id and p.partner_id in persons:
                    persons[p.partner_id].partner_id = None
                emit("death", year_index=yi, day=day(), person_ids=[p.person_id],
                     household_id=p.household_id,
                     cause=(f"mortality hazard, age {p.age} {p.sex}, from VSA08 "
                            f"deaths over PEA01 population"),
                     effects={"occupancy": "one fewer occupant"})

        # ---- 2. births ----------------------------------------------------
        # Two passes. The parity weights are normalised to mean 1.0 WITHIN
        # each fertility band, so VSA104's published band rate is preserved
        # exactly and VSA36 only redistributes those births across parities.
        eligible = sorted(
            [x for x in persons.values()
             if x.alive and x.resident and tab.p_birth(x) > 0.0],
            key=lambda x: x.person_id,
        )
        by_band: dict[str, list[Person]] = {}
        for x in eligible:
            band = _fertility_band(x.age)
            if band:
                by_band.setdefault(band, []).append(x)
        scale: dict[str, float] = {}
        for band, women in by_band.items():
            ws = [tab.parity_weight(w) for w in women]
            mean_w = sum(ws) / len(ws) if ws else 0.0
            # A band in which every weight is zero would lose its births
            # entirely; fall back to no parity adjustment rather than to zero.
            scale[band] = (1.0 / mean_w) if mean_w > 0 else 0.0
        for p in eligible:
            band = _fertility_band(p.age)
            w = tab.parity_weight(p) * scale.get(band or "", 0.0)
            if scale.get(band or "", 0.0) == 0.0:
                w = 1.0
            p_event = min(tab.p_birth(p) * w, 1.0)
            if not draw("birth", p_event):
                continue
            pid = f"P-WP5-{next_person:05d}"
            next_person += 1
            persons[pid] = Person(
                person_id=pid, age=0,
                sex=("Female" if gen.random() < 0.5 else "Male"),
                role="child", econ_status="child",
                household_id=p.household_id,
            )
            households.setdefault(p.household_id, []).append(pid)
            p.parity += 1
            emit("birth", year_index=yi, day=day(), person_ids=[pid],
                 household_id=p.household_id,
                 cause=(f"age-specific fertility, mother aged {p.age}, "
                        f"parity {p.parity - 1} to {p.parity}, from VSA104 "
                        f"South-West with VSA36 parity shares normalised to "
                        f"preserve the band rate"),
                 effects={"occupancy": "one more occupant, an infant"})

        # ---- 3. partnering ------------------------------------------------
        singles = sorted(
            [p for p in persons.values()
             if p.alive and p.resident and p.partner_id is None
             and p.age >= 18 and p.role != "child"],
            key=lambda x: x.person_id,
        )
        for p in singles:
            if p.partner_id is not None:
                continue
            if not draw("partnering", tab.p_partner(p)):
                continue
            # The partner moves in from outside the slice: pairing two slice
            # residents would halve the population for free and is not what a
            # 60-home slice inside a 1,092-home town does.
            pid = f"P-WP5-{next_person:05d}"
            next_person += 1
            partner = Person(
                person_id=pid, age=max(p.age + int(gen.integers(-4, 5)), 18),
                sex=("Male" if p.sex == "Female" else "Female"),
                role="partner", econ_status="at work",
                household_id=p.household_id, partner_id=p.person_id,
            )
            persons[pid] = partner
            p.partner_id = pid
            households.setdefault(p.household_id, []).append(pid)
            emit("partnering", year_index=yi, day=day(),
                 person_ids=[p.person_id, pid], household_id=p.household_id,
                 cause=(f"union formation, age {p.age} {p.sex}, from VSA49 "
                        f"marriage rates by single year of age"),
                 effects={"occupancy": "one more adult occupant"})

        # ---- 4. separation ------------------------------------------------
        seen: set[str] = set()
        for p in sorted([x for x in persons.values()
                         if x.alive and x.resident and x.partner_id],
                        key=lambda x: x.person_id):
            if p.person_id in seen or p.partner_id in seen:
                continue
            seen.add(p.person_id)
            seen.add(p.partner_id or "")
            if not draw("separation", tab.p_separation()):
                continue
            leaver = persons[p.partner_id] if p.partner_id in persons else None
            if leaver is None:
                continue
            p.partner_id = None
            leaver.partner_id = None
            leaver.resident = False
            leaver.left_year = yi
            hh = households.get(leaver.household_id, [])
            if leaver.person_id in hh:
                hh.remove(leaver.person_id)
            emit("separation", year_index=yi, day=day(),
                 person_ids=[p.person_id, leaver.person_id],
                 household_id=p.household_id,
                 cause=("union dissolution, [A] A-25c: no separation or divorce "
                        "transition rate is published for Ireland; bounded by "
                        "CD565's divorced-and-separated stock"),
                 effects={"occupancy": "one fewer adult occupant"})

        # ---- 5. children leaving home -------------------------------------
        for p in sorted([x for x in persons.values()
                         if x.alive and x.resident and x.role == "child"
                         and 18 <= x.age <= 34],
                        key=lambda x: x.person_id):
            if not draw("child_leaves_home", tab.p_child_leaves()):
                continue
            p.resident = False
            p.left_year = yi
            hh = households.get(p.household_id, [])
            if p.person_id in hh:
                hh.remove(p.person_id)
            emit("child_leaves_home", year_index=yi, day=day(),
                 person_ids=[p.person_id], household_id=p.household_id,
                 cause=(f"child leaves the parental home at {p.age}, [A] A-25d: "
                        f"only EA036's age-20 stock is published"),
                 effects={"occupancy": "one fewer adult occupant, a bedroom "
                                       "falls out of use"})

        # ---- 6. employment change -----------------------------------------
        for p in sorted([x for x in persons.values()
                         if x.alive and x.resident and 16 <= x.age < 70],
                        key=lambda x: x.person_id):
            if not draw("employment_change", tab.p_employment_change(p)):
                continue
            was = p.econ_status
            p.econ_status = (
                "unemployed" if was == "at work"
                else "at work" if was in ("unemployed", "inactive") else was
            )
            if p.econ_status == was:
                continue
            emit("employment_change", year_index=yi, day=day(),
                 person_ids=[p.person_id], household_id=p.household_id,
                 cause=(f"job separation hazard at age {p.age} {p.sex}, from "
                        f"JCA01 separations over employees; {was} to "
                        f"{p.econ_status}"),
                 effects={"weekday_daytime": "home during working hours" if
                          p.econ_status != "at work" else "away during "
                          "working hours"})

        # ---- 7. health states ---------------------------------------------
        for p in sorted([x for x in persons.values()
                         if x.alive and x.resident and x.health_state == "well"],
                        key=lambda x: x.person_id):
            if not draw("health_state_onset", tab.p_health_onset(p)):
                continue
            p.health_state = "chronic"
            emit("health_state_onset", year_index=yi, day=day(),
                 person_ids=[p.person_id], household_id=p.household_id,
                 cause=(f"chronic health-state onset at {p.age}; "
                        + ("built to HSPAE122's 1-or-more prevalence at 50+"
                           if p.age >= 50 else
                           "[A] A-25e: HSPAE122 starts at 50, nothing is "
                           "published below it")),
                 effects={"home_hours": "more hours at home",
                          "setpoint": "higher for longer"})

        # ---- 7b. households that have emptied out -------------------------
        # Deaths, separations and children leaving can take the LAST member of
        # a household. Without this sweep the dwelling stayed marked occupied
        # by a household with no members - which the invariants caught, and
        # which is a modelling gap rather than an invariant worth relaxing: a
        # home whose last occupant has gone is vacant, and that is an
        # observable change with its own label.
        for hh_id in sorted([h for h, m in households.items() if not m]):
            bid = building_of(hh_id)
            if bid is None:
                continue
            dwellings[bid].household_id = None
            dwellings[bid].vacant_since_year = yi
            hh_to_building.pop(hh_id, None)
            emit("household_dissolved", year_index=yi, day=day(),
                 person_ids=[], household_id=hh_id, building_id=bid,
                 cause=("the household's last member died, separated out or "
                        "left; the dwelling becomes vacant and enters the "
                        "vacancy chain"),
                 effects={"occupancy": "the dwelling becomes vacant"})

        # ---- 8. moves out, which create vacancies -------------------------
        for hh_id in sorted([h for h, m in households.items() if m]):
            if not draw("move_out", tab.p_move_out()):
                continue
            bid = building_of(hh_id)
            if bid is None:
                continue
            members = list(households[hh_id])
            for pid in members:
                persons[pid].resident = False
                persons[pid].left_year = yi
            households[hh_id] = []
            dwellings[bid].household_id = None
            dwellings[bid].vacant_since_year = yi
            hh_to_building.pop(hh_id, None)
            emit("move_out", year_index=yi, day=day(), person_ids=members,
                 household_id=hh_id, building_id=bid,
                 cause=("gross household out-move, [A] A-25b: EP006 publishes "
                        "NET migration only; bounded by VAC17's gross vacancy "
                        "flows"),
                 effects={"occupancy": "the dwelling becomes vacant"})

        # ---- 9. the vacancy chain: moves in fill vacancies ----------------
        # VAC17's two flows balance at a ratio near 1.0, and VAC04 puts Cork
        # County's vacancy rate at 5 to 6 per cent. So vacancies are refilled
        # at the rate that holds the stock flat around that level, rather than
        # at an assumed in-migration rate: the chain is what closes it.
        pub = sorted(tab.vacancy_cork.values())
        target_rate = (sum(pub) / len(pub)) / 100.0
        vacant = sorted([bid for bid, d in dwellings.items()
                         if d.household_id is None])
        n_allowed_vacant = int(math.floor(target_rate * len(dwellings)))
        to_fill = max(len(vacant) - n_allowed_vacant, 0)
        for bid in vacant[:to_fill]:
            hh_id = f"HH-WP5-{next_hh:05d}"
            next_hh += 1
            size = int(gen.integers(1, 5))
            members = []
            for _ in range(size):
                pid = f"P-WP5-{next_person:05d}"
                next_person += 1
                age = int(gen.integers(20, 70))
                persons[pid] = Person(
                    person_id=pid, age=age,
                    sex=("Female" if gen.random() < 0.5 else "Male"),
                    role="adult", econ_status="at work", household_id=hh_id,
                )
                members.append(pid)
            households[hh_id] = members
            dwellings[bid].household_id = hh_id
            dwellings[bid].vacant_since_year = None
            hh_to_building[hh_id] = bid
            emit("move_in", year_index=yi, day=day(), person_ids=members,
                 household_id=hh_id, building_id=bid,
                 cause=("vacancy chain refill, holding the stock at VAC04's "
                        "Cork County vacancy rate with VAC17's balanced flows"),
                 effects={"occupancy": f"the dwelling is occupied by {size}"})

        # ---- 10. retrofits and DER, each a D03 passport event -------------
        # Measures are drawn first and then applied IN DATE ORDER, because the
        # passport version chain is chronological. Applying them in iteration
        # order produced a chain that jumped backwards once two measures landed
        # on the same building in one year - caught by the invariant, and a
        # genuine bug rather than an invariant to loosen: a passport whose
        # versions do not follow its dates cannot reconstruct the building.
        for bid in sorted(dwellings):
            d = dwellings[bid]
            if d.household_id is None:
                continue                      # nobody to decide
            fired: list[tuple[int, str]] = []
            for measure in sorted(MEASURES):
                if measure in d.measures:
                    continue
                cap = tab.measure_cap(measure)
                if cap is not None:
                    have = sum(1 for x in dwellings.values() if measure in x.measures)
                    if have >= cap * len(dwellings):
                        continue              # the HEBEU37 prevalence bound
                if not draw(measure, tab.p_measure(measure)):
                    continue
                fired.append((day(), measure))
            for dd, measure in sorted(fired):
                d.measures.add(measure)
                ev = emit(measure, year_index=yi, day=dd, person_ids=[],
                          household_id=d.household_id, building_id=bid,
                          cause=(f"{measure} adopted, [A] A-25f: PxStat "
                                 f"publishes no retrofit rate (zero tables for "
                                 f"'retrofit'); bounded by HEBEU37's 2024 "
                                 f"prevalence"),
                          decided_day=max(yi * DAYS_PER_YEAR + dd - 90, 0),
                          effects={"building": f"{measure} in place"})
                spec = MEASURES[measure]
                passports.append(PassportEvent(
                    passport_event_id=f"BP-{bid}-{year}-{measure}",
                    building_id=bid,
                    event_type=str(spec["passport_event_type"]),
                    measure=measure,
                    effective_day=ev.effective_day,
                    decided_day=ev.decided_day,
                    from_version=d.version,
                    to_version=d.version + 1,
                    parameters_changed={k: "changed" for k in spec["parameters"]},
                    driver=(f"WP5 ten-year life course, {measure}; hazard "
                            f"[A] A-25f bounded by HEBEU37"),
                    life_event_id=ev.event_id,
                ))
                d.version += 1

        # ---- 11. the scripted Mary scenario -------------------------------
        if mary is not None and yi == config.mary_year_index:
            m_event, m_labels = mary_scenario(
                household_id=str(mary["household_id"]),
                building_id=str(mary["building_id"]),
                mary_person_id=str(mary["mary_person_id"]),
                incoming_person_ids=[f"P-MARY-{i:02d}" for i in range(1, 5)],
                move_in_day=config.mary_move_in_day,
            )
            events.append(m_event)
            labels.extend(m_labels)
            bump("mary_move_in")
            hh = households.setdefault(str(mary["household_id"]), [])
            for i, pid in enumerate([f"P-MARY-{i:02d}" for i in range(1, 5)]):
                persons[pid] = Person(
                    person_id=pid, age=(34, 36, 7, 4)[i],
                    sex=("Female", "Male", "Female", "Male")[i],
                    role=("adult", "partner", "child", "child")[i],
                    econ_status=("at work", "at work", "child", "child")[i],
                    household_id=str(mary["household_id"]),
                )
                hh.append(pid)

        # ---- age everyone, then close the year ----------------------------
        for p in persons.values():
            if p.alive:
                p.age += 1

        per_year.append({
            "year": year,
            "year_index": yi,
            "n_people": sum(1 for p in persons.values() if p.alive and p.resident),
            "n_households": sum(1 for h in households.values() if h),
            "n_occupied_dwellings": sum(
                1 for d in dwellings.values() if d.household_id is not None
            ),
            "n_dwellings": len(dwellings),
            "vacancy_rate": round(
                (len(dwellings) - sum(1 for d in dwellings.values()
                                      if d.household_id is not None))
                / len(dwellings), 4
            ),
            "events_this_year": len(events) - year_events_before,
            "measures_in_place": sum(len(d.measures) for d in dwellings.values()),
        })

    final = YearState(
        year=config.start_year + config.n_years, year_index=config.n_years,
        persons=persons, dwellings=dwellings, households=households,
    )
    states.append(final)

    return TenYearResult(
        events=events, labels=labels, passport_events=passports,
        per_year=per_year, counts=counts,
        invariants=check_invariants(states, events, labels, passports),
        vital_check=vital_statistics_intervals(
            counts, exposure, tab, integrated=integrated,
        ),
        hazard_record={
            "sourced": [dataclasses.asdict(h) for h in HZ.HAZARD_SOURCES],
            "assumed": [dataclasses.asdict(a) for a in HZ.ASSUMED_HAZARDS],
            "search_record": [
                {"term": t, "tables_returned": n, "verdict": v}
                for t, n, v in HZ.SEARCH_RECORD
            ],
            "source_sha256": HZ.source_shas(),
            "donor_note": HZ.DONOR_NOTE,
        },
        states=states,
    )


# --------------------------------------------------------------------------- #
# acceptance
# --------------------------------------------------------------------------- #

def check_invariants(
    states: list[YearState],
    events: list[LifeEvent],
    labels: list[ChangeLabel],
    passports: list[PassportEvent],
) -> dict[str, Any]:
    """The ten-year invariants. Every one is a failure if it fires."""
    failures: list[str] = []

    # -- population bookkeeping --------------------------------------------
    for st in states:
        seen: dict[str, str] = {}
        for hh_id, members in st.households.items():
            for pid in members:
                if pid in seen:
                    failures.append(
                        f"{st.year}: person {pid} is in two households "
                        f"({seen[pid]} and {hh_id})"
                    )
                seen[pid] = hh_id
        for hh_id, members in st.households.items():
            for pid in members:
                p = st.persons.get(pid)
                if p is None:
                    failures.append(f"{st.year}: household {hh_id} lists unknown {pid}")
                elif not p.alive:
                    failures.append(f"{st.year}: dead person {pid} still in {hh_id}")
                elif not p.resident:
                    failures.append(f"{st.year}: non-resident {pid} still in {hh_id}")

    # -- ages move forward, once per year ----------------------------------
    for a, b in zip(states, states[1:]):
        for pid, pa in a.persons.items():
            pb = b.persons.get(pid)
            if pb is None or not pa.alive:
                continue
            if pb.alive and pb.age != pa.age + 1:
                failures.append(
                    f"{pid} aged {pa.age}->{pb.age} between {a.year} and {b.year}"
                )

    # -- nobody comes back from the dead -----------------------------------
    dead: set[str] = set()
    for st in states:
        for pid, p in st.persons.items():
            if pid in dead and p.alive:
                failures.append(f"{pid} is alive again in {st.year}")
            if not p.alive:
                dead.add(pid)

    # -- one household per dwelling, one dwelling per household ------------
    for st in states:
        occ: dict[str, str] = {}
        for bid, d in st.dwellings.items():
            if d.household_id is None:
                continue
            if d.household_id in occ:
                failures.append(
                    f"{st.year}: household {d.household_id} occupies "
                    f"{occ[d.household_id]} and {bid}"
                )
            occ[d.household_id] = bid
        for bid, d in st.dwellings.items():
            if d.household_id is not None and not st.households.get(d.household_id):
                failures.append(
                    f"{st.year}: {bid} is occupied by {d.household_id}, "
                    f"which has no members"
                )

    # -- every resident person lives somewhere ------------------------------
    # The population the life course reports and the population the SLICE
    # simulates have to be the same people. A resident whose household holds
    # no dwelling is in neither: they would be counted in the vital-statistics
    # exposure and simulated by nobody.
    for st in states:
        housed = {
            d.household_id for d in st.dwellings.values()
            if d.household_id is not None
        }
        for pid, pr in st.persons.items():
            if not (pr.alive and pr.resident):
                continue
            if pr.household_id not in housed:
                failures.append(
                    f"{st.year}: resident {pid} is in household "
                    f"{pr.household_id}, which occupies no dwelling"
                )

    # -- the stock is fixed -------------------------------------------------
    n0 = len(states[0].dwellings)
    for st in states:
        if len(st.dwellings) != n0:
            failures.append(
                f"{st.year}: {len(st.dwellings)} dwellings, was {n0}; the slice "
                f"is a fixed set of buildings"
            )

    # -- events are inside the run and ordered ------------------------------
    horizon = (len(states) - 1) * DAYS_PER_YEAR
    for ev in events:
        if not 0 <= ev.effective_day <= horizon:
            failures.append(f"{ev.event_id} effective_day {ev.effective_day} "
                            f"outside 0..{horizon}")
        if ev.decided_day is not None and ev.decided_day > ev.effective_day:
            failures.append(f"{ev.event_id} was decided after it took effect")

    # -- every label points at a real event, and its tier is the lowest ----
    ids = {ev.event_id for ev in events}
    for lab in labels:
        for sid in lab.source_event_ids:
            if sid not in ids:
                failures.append(f"{lab.label_id} cites unknown event {sid}")
        if lab.detectable_from_tier not in TIER_DEVICES:
            failures.append(
                f"{lab.label_id} has tier {lab.detectable_from_tier!r}, which "
                f"is not a sensor tier"
            )
        if not 0 <= lab.true_onset_day <= horizon:
            failures.append(f"{lab.label_id} onset {lab.true_onset_day} outside run")
        if lab.true_end_day is not None and lab.true_end_day < lab.true_onset_day:
            failures.append(f"{lab.label_id} ends before it starts")

    # -- passport versions form an unbroken chain per building -------------
    by_building: dict[str, list[PassportEvent]] = {}
    for pe in passports:
        by_building.setdefault(pe.building_id, []).append(pe)
    for bid, evs in by_building.items():
        evs = sorted(evs, key=lambda e: (e.effective_day, e.from_version))
        for a, b in zip(evs, evs[1:]):
            if b.from_version != a.to_version:
                failures.append(
                    f"{bid}: passport version jumps {a.to_version} -> "
                    f"{b.from_version}"
                )
        for pe in evs:
            if pe.to_version != pe.from_version + 1:
                failures.append(
                    f"{pe.passport_event_id} moves version by "
                    f"{pe.to_version - pe.from_version}, not 1"
                )
            if pe.life_event_id is not None and pe.life_event_id not in ids:
                failures.append(
                    f"{pe.passport_event_id} cites unknown life event "
                    f"{pe.life_event_id}"
                )

    return {
        "n_checks": 10,
        "failures": failures,
        "clean": not failures,
        "n_states": len(states),
        "n_events": len(events),
        "n_labels": len(labels),
        "n_passport_events": len(passports),
    }


def _poisson_interval(mean: float, z: float = 1.96) -> tuple[float, float]:
    """A normal-approximation interval on a Poisson count.

    Used rather than an exact interval because the acceptance question is
    whether the realised count is consistent with the published rate at the
    exposure this slice actually had, and the exposure is in the hundreds of
    person-years where the approximation holds. Where the expected count is
    below 10 the interval is widened to the exact Poisson quantiles, because
    the approximation goes negative there and a lower bound of zero would
    make the test unfalsifiable.
    """
    if mean <= 0:
        return (0.0, 0.0)
    if mean >= 10.0:
        sd = math.sqrt(mean)
        return (max(mean - z * sd, 0.0), mean + z * sd)
    from scipy import stats

    return (float(stats.poisson.ppf(0.025, mean)),
            float(stats.poisson.ppf(0.975, mean)))


def vital_statistics_intervals(
    counts: dict[str, int], exposure: dict[str, float], tab: HazardTables,
    *, integrated: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Are births, deaths and moves inside the published rate's interval?

    The expected count is the PUBLISHED rate times the exposure this run
    actually had - person-years by age and sex for deaths, woman-years by age
    band for births - so the comparison is against the source and not against
    a figure of ours.
    """
    rows: list[dict[str, Any]] = []

    expected_deaths = 0.0
    for key, py in exposure.items():
        if not key.startswith("py:"):
            continue
        _, sex, band = key.split(":", 2)
        rate = tab.death.get((sex, band))
        if rate is not None:
            expected_deaths += py * rate / 1000.0

    expected_births = 0.0
    for key, wy in exposure.items():
        if not key.startswith("wy:"):
            continue
        band = key.split(":", 1)[1]
        rate = tab.fertility.get(band)
        if rate is not None:
            expected_births += wy * rate / 1000.0

    expected_partnering = 0.0
    avail = {k[1] for k in tab.marriage}
    for key, sy in exposure.items():
        if not key.startswith("sy:"):
            continue
        _, sex, age = key.split(":", 2)
        lab = _single_year_label(int(age), avail)
        if lab is not None:
            rate = tab.marriage.get((sex, lab))
            if rate is not None:
                expected_partnering += sy * rate / 1000.0

    # U33, week 3 step 4. The move-out interval now comes from Census 2022's
    # "usual residence one year ago" for Cobh itself, not from the model's own
    # declared rate applied to the model's own household-years - which
    # compared the model to itself and carried no evidence about Ireland.
    # The declared hazard is unchanged; only the interval is sourced. [A]
    # A-25b is now about the person-to-household conversion rather than about
    # the absence of a source.
    household_years = exposure.get("household_years", 0.0)
    move_proxy: dict[str, Any] | None = None
    try:
        from baile_nua.lifecourse import move_rate as MR

        move_proxy = MR.move_rate_proxy(
            declared_rate=tab.p_move_out(), household_years=household_years,
            observed=int(counts.get("move_out", 0)),
        )
        expected_moves = household_years * MR.person_move_rate()
        move_basis = (
            f"Census 2022 SAP2022T2T3TOWN22, '{MR.TOWN_LABEL}': "
            f"{move_proxy['census_counts'].get('Same Address', 0):,.0f} of "
            f"{move_proxy['census_counts'].get('Total', 0):,.0f} residents "
            f"aged 1+ at the same address one year before Census Day, so a "
            f"person move rate of "
            f"{move_proxy['census_person_move_rate_per_year']:.6f} per year, "
            f"applied to this run's household-years. [A] A-25b: the person "
            f"rate bounds the HOUSEHOLD rate from above, because an "
            f"individual move adds a person-move and not a household-move. "
            f"The model's declared rate is "
            f"{move_proxy['declared_household_move_rate_per_year']:.6f}"
        )
        move_sourced = True
    except Exception as exc:                       # noqa: BLE001
        # A missing or changed source must not silently restore the
        # self-referential criterion: it reverts, and it says so in the basis
        # so the artefact records that the sourced test did not run.
        expected_moves = household_years * tab.p_move_out()
        move_basis = (
            f"[A] A-25b gross out-move rate applied to this run's "
            f"household-years. THE SOURCED U33 PROXY DID NOT RUN: "
            f"{type(exc).__name__}: {exc}. This is therefore an "
            f"internal-consistency test, not agreement with a source."
        )
        move_sourced = False

    for name, observed, expected, basis in (
        ("death", counts.get("death", 0), expected_deaths,
         "VSA08 deaths over PEA01 population, by age band and sex, applied to "
         "this run's person-years"),
        ("birth", counts.get("birth", 0), expected_births,
         "VSA104 South-West age-specific fertility applied to this run's "
         "woman-years by age band. The VSA36 parity weights are normalised to "
         "mean 1.0 within each band, so the band rate is preserved exactly "
         "and the expectation is the unmodified published rate"),
        ("partnering", counts.get("partnering", 0), expected_partnering,
         "VSA49 marriages per 1,000 by single year of age and sex, applied to "
         "the single-adult years this run actually had"),
        ("move_out", counts.get("move_out", 0), expected_moves, move_basis),
    ):
        lo, hi = _poisson_interval(expected)
        integ = (integrated or {}).get(name)
        rows.append({
            "event": name,
            "observed": observed,
            "expected": round(expected, 2),
            "ci95": [round(lo, 2), round(hi, 2)],
            "within": bool(lo <= observed <= hi),
            # The hazard integrated over the draws actually taken. If this
            # disagrees with `expected`, the exposure accounting is wrong and
            # the interval is being computed against the wrong denominator -
            # which looks exactly like a model that misses its target.
            "integrated_hazard": None if integ is None else round(integ, 2),
            "integrated_matches_exposure": (
                None if integ is None or expected <= 0
                else bool(abs(integ - expected) / expected < 0.10)
            ),
            "sourced": (move_sourced if name == "move_out"
                        else name in ("death", "birth", "partnering")),
            "basis": basis,
        })

    sourced = [r for r in rows if r["sourced"]]
    return {
        "rows": rows,
        "u33_move_rate_proxy": move_proxy,
        "all_sourced_within": all(r["within"] for r in sourced),
        "all_within": all(r["within"] for r in rows),
        "exposure": {k: v for k, v in exposure.items() if ":" not in k},
    }


# --------------------------------------------------------------------------- #
# adapter: the E1 slice in, the life course's own view out
# --------------------------------------------------------------------------- #

def from_slice(sl: Any) -> tuple[dict[str, Person], dict[str, Dwelling],
                                 dict[str, list[str]]]:
    """Read the life course's starting state off an :class:`E1Slice`.

    A narrow view, for the same reason ``PersonProfile`` is narrow: the life
    course needs age, sex, role and economic status and nothing else, so it
    cannot come to depend on something the observable layer must never see.
    """
    persons: dict[str, Person] = {}
    households: dict[str, list[str]] = {}
    dwellings: dict[str, Dwelling] = {}

    for hh_id, members in sorted(sl.households.items()):
        households[hh_id] = [p.person_id for p in members]
        for p in members:
            persons[p.person_id] = Person(
                person_id=p.person_id,
                age=int(p.age),
                # The activity engine's sex field; normalised to the label the
                # CSO tables use, because the hazard lookup is by that label.
                sex=("Female" if str(p.sex).lower().startswith("f") else "Male"),
                role=str(p.role),
                econ_status=str(p.econ_status),
                household_id=hh_id,
                health_state=str(getattr(p, "health_state", "well")),
            )
        b = sl.buildings[hh_id]
        dwellings[b.building_id] = Dwelling(
            building_id=b.building_id, household_id=hh_id,
        )

    # Partner each household's two eldest adults, so that the separation and
    # partnering hazards have couples to act on. The slice carries roles but
    # not couple identity, and inventing a richer relationship structure here
    # would be inventing population structure in the wrong module.
    for hh_id, members in households.items():
        adults = sorted(
            [persons[p] for p in members
             if persons[p].age >= 18 and persons[p].role != "child"],
            key=lambda x: (-x.age, x.person_id),
        )
        if len(adults) >= 2:
            adults[0].partner_id = adults[1].person_id
            adults[1].partner_id = adults[0].person_id
    return persons, dwellings, households


# --------------------------------------------------------------------------- #
# applying a year's state back to the slice, so the year can be SIMULATED
# --------------------------------------------------------------------------- #

#: What a measure changes in the simulation, and what it does not yet.
#:
#: PV, battery, heat pump and smart controls are asset changes the engine
#: already models, so they are applied. Fabric retrofit and extension change
#: the RC parameters, which is the week 3 fabric work (I-048, "no fabric
#: tuning now") - their D03 passport events and D20 labels are recorded in
#: full, and the thermal parameters are deliberately NOT touched in week 2.
#: That gap is real and is recorded rather than hidden: a detector scored
#: against a fabric-retrofit label in a week-2 package would be scored against
#: a change the series does not yet contain.
MEASURE_APPLIED_IN_WEEK2: dict[str, bool] = {
    "retrofit_fabric": False,
    "extension": False,
    "retrofit_heat_pump": True,
    "der_pv": True,
    "der_battery": True,
    "der_smart_controls": True,
}

#: What this map actually meant, now that week 3 has measured it (I-062).
#:
#: ``True`` here meant "``apply_year_to_slice`` sets the slice field", which is
#: not the same claim as "the series changes", and for two of the four it was
#: not true: ``retrofit_heat_pump`` and ``der_smart_controls`` wrote keys into
#: ``owned`` that nothing in the engine reads. Measured one mutation at a time
#: against every ``*_wh`` field, not inferred - see I-062.
#:
#: Kept rather than corrected in place, because the ten-year artefacts already
#: published it and a reader of those needs to be able to find out what it
#: claimed. :data:`MEASURE_REACHES_THE_SERIES` is what to read instead.
MEASURE_REACHES_THE_SERIES: dict[str, str] = {
    "retrofit_fabric": "week 3, dated: physics/retrofit.py scales the fabric",
    "extension": "week 3, dated: physics/retrofit.py adds envelope and volume",
    "retrofit_heat_pump": (
        "week 3, dated: physics/passport_assets.py switches heating_system "
        "and heating_fuel and applies DEAP Table 4c(4). Before week 3 it set "
        "owned['heat_pump'], which nothing reads - the series did not move"
    ),
    "der_pv": "week 2, start-of-year; week 3, dated",
    "der_battery": "week 2, start-of-year; week 3, dated",
    "der_smart_controls": (
        "week 3, dated, and sourced to no effect on a boiler home: DEAP "
        "publishes a temperature adjustment of 0 for every control category "
        "from a room thermostat upward. Only a heat-pump home moves, by Table "
        "4c(4)'s 0.70 -> 0.75. Before week 3 it set "
        "owned['smart_heating_control'], which nothing reads"
    ),
}

#: Which D09 event types change who lives in a dwelling, and by how many.
#: ``+1``/``-1`` are per named person; ``move_in``/``move_out`` carry a list.
OCCUPANCY_EVENTS: dict[str, int] = {
    "birth": +1,
    "death": -1,
    "move_in": +1,
    "move_out": -1,
    "partnering": +1,
    "child_leaves_home": -1,
    "mary_move_in": +1,
    "household_dissolved": -1,
}


def occupancy_schedule(
    *, result: "TenYearResult", sl: Any, year_index: int, master_seed: int,
) -> dict[int, list[dict[str, Any]]]:
    """Dated occupancy changes for one year, keyed by day of that year.

    I-054's third kind of dated event, and the only one with no declared
    quantity in it. ``apply_year_to_slice`` gives the household composition as
    it stands at the **start** of the year, which is correct as a baseline and
    wrong as the whole story: a birth on day 200 used to appear in the series
    on day 0 of the following year, while its D20 label pointed at day 200.

    Arrivals are returned as ``PersonProfile`` objects built the same way
    ``apply_year_to_slice`` builds them - :func:`_trait_draws` on the
    life-course stream - so a person who arrives mid-year is drawn from the
    same distributions as one who was there at t0.

    Returns ``{day_of_year: [{household_key, arrivals, departures, events}]}``
    against the slice's own household keys, because the runner is keyed by
    those and not by the life course's household ids: over ten years a
    building's occupants change but the premises does not.
    """
    from baile_nua.activity.engine import PersonProfile

    lo = year_index * DAYS_PER_YEAR
    hi = lo + DAYS_PER_YEAR
    tree = SeedTree(master_seed)
    gen = tree.generator(Stream.LIFE_COURSE, entity="apply", sim_day=year_index)

    ages = [p.age for ppl in sl.households.values() for p in ppl]
    age_mean = float(np.mean(ages)) if ages else 40.0
    age_sd = float(np.std(ages)) if ages else 20.0
    known = {p.person_id: p for ppl in sl.households.values() for p in ppl}
    bid_to_hh = {b.building_id: hh for hh, b in sl.buildings.items()}

    # Everyone the life course knows about, from the LAST state, so an
    # arrival's age and status can be looked up after the fact.
    roster: dict[str, Any] = {}
    for st in result.states:
        roster.update(st.persons)

    by_day: dict[int, dict[str, dict[str, Any]]] = {}
    for ev in result.events:
        delta = OCCUPANCY_EVENTS.get(ev.event_type)
        if delta is None or ev.building_id is None:
            continue
        if not (lo <= ev.effective_day < hi):
            continue
        hh = bid_to_hh.get(ev.building_id)
        if hh is None:
            continue                       # a dwelling outside the slice
        day = ev.effective_day - lo
        slot = by_day.setdefault(day, {}).setdefault(
            hh, {"household_key": hh, "building_id": ev.building_id,
                 "arrivals": [], "departures": [], "events": []})
        slot["events"].append({"event_id": ev.event_id,
                               "event_type": ev.event_type})
        for pid in ev.persons:
            if delta < 0:
                slot["departures"].append(pid)
                continue
            if pid in known:
                slot["arrivals"].append(known[pid])
                continue
            lp = roster.get(pid)
            if lp is None:
                # Named as arriving but absent from every state: a
                # bookkeeping error in the life course, not an occupancy
                # change. Recorded in the slot so it is visible rather than
                # dropped.
                slot.setdefault("unresolved", []).append(pid)
                continue
            tr = _trait_draws(gen, lp.age, age_mean, age_sd)
            slot["arrivals"].append(PersonProfile(
                person_id=pid, age=lp.age,
                sex=("female" if lp.sex == "Female" else "male"),
                role=lp.role, econ_status=lp.econ_status,
                work_pattern=("day" if lp.econ_status == "at work" else "none"),
                remote_share=0.0,
                chronotype=tr["chronotype"],
                habit_strength=tr["habit_strength"],
                lapse_rate=tr["lapse_rate"],
                attention=tr["attention"],
                comfort=tr["comfort"],
                health_state=lp.health_state,
                caring_load="none",
                school_year=(max(lp.age - 4, 0) if 4 <= lp.age <= 18 else None),
                vehicle_access="none",
            ))
    return {d: list(v.values()) for d, v in sorted(by_day.items())}


def passport_schedule(
    *, result: "TenYearResult", year_index: int,
) -> dict[int, list["PassportEvent"]]:
    """Every D03 passport event falling inside one year, keyed by day of year.

    All of them, which is the week-3 change: the week-2 caller filtered to
    ``("retrofit", "extension")`` because the asset measures were applied
    through the slice at the start of the year. They are dated now, so the
    filter is gone and the engine dispatches on ``PassportEvent.measure``.
    """
    lo = year_index * DAYS_PER_YEAR
    hi = lo + DAYS_PER_YEAR
    out: dict[int, list[PassportEvent]] = {}
    for pe in result.passport_events:
        if lo <= pe.effective_day < hi:
            out.setdefault(pe.effective_day - lo, []).append(pe)
    return {d: sorted(v, key=lambda e: e.passport_event_id)
            for d, v in sorted(out.items())}


def _trait_draws(gen: Any, age: int, age_mean: float, age_sd: float) -> dict[str, float]:
    """Traits for a person who arrives mid-run, from the town's own formulas.

    The coefficients are :mod:`baile_nua.population.traits`'s, not new ones: a
    person who moves in during year 4 has to be drawn from the same
    distributions as the people who were there in year 1, or the slice's trait
    distribution drifts over ten years for no modelled reason.
    """
    age_z = (age - age_mean) / age_sd if age_sd > 0 else 0.0
    return {
        "chronotype": float(np.clip(-0.9 * age_z + gen.normal(0, 0.8), -3.0, 3.0)),
        "habit_strength": float(
            np.clip(0.55 + 0.12 * age_z + gen.normal(0, 0.15), 0.05, 0.98)
        ),
        "lapse_rate": float(
            np.clip(0.08 - 0.02 * age_z + gen.normal(0, 0.03), 0.005, 0.40)
        ),
        "attention": float(
            np.clip(0.60 - 0.08 * abs(age_z) + gen.normal(0, 0.15), 0.05, 0.98)
        ),
        "comfort": float(gen.normal(0, 1)),
    }


def apply_year_to_slice(
    sl: Any, state: YearState, *, master_seed: int, year_index: int
) -> Any:
    """Return the slice as it stands at the start of ``state``'s year.

    Mutates nothing: the original slice is the year-1 fixture and other runs
    depend on it being unchanged.

    That claim was false in the first version and the ten-year run did not
    expose it. ``has_battery`` is carried on the BUILDING, not in the ``owned``
    map, so setting it reached through to ``sl.buildings`` and the original
    slice's battery count went from 3 to 6 after applying year ten. Each
    per-year run is a separate process that calls this once, so no committed
    result is affected - which is exactly why it survived: the one usage
    pattern in production is the one that cannot see the bug. Two years applied
    in a single process would have leaked the later year's assets into the
    earlier year's answer, silently.

    The buildings are therefore copied before anything is assigned to them.
    """
    import copy as _copy
    import dataclasses as _dc

    from baile_nua.activity.engine import PersonProfile

    tree = SeedTree(master_seed)
    gen = tree.generator(Stream.LIFE_COURSE, entity="apply", sim_day=year_index)

    # The age distribution the traits are referenced to: the slice's own, at
    # year 1, so the reference does not move as the population ages.
    ages = [p.age for ppl in sl.households.values() for p in ppl]
    age_mean = float(np.mean(ages)) if ages else 40.0
    age_sd = float(np.std(ages)) if ages else 20.0

    original: dict[str, Any] = {
        p.person_id: p for ppl in sl.households.values() for p in ppl
    }

    # Keyed by the slice's own household id PER BUILDING, not by the
    # life-course household id. Over ten years a building's occupants change -
    # a household moves out and another moves in - but the premises does not,
    # and the slice is keyed by premises. Keying by the life-course household
    # instead dropped every vacancy-chain refill, because those households do
    # not exist in `sl.buildings`: year 2031 came out with 24 vacant homes and
    # 83 people against the life course's 3 and 142.
    bid_to_hh = {b.building_id: hh for hh, b in sl.buildings.items()}
    households: dict[str, list[Any]] = {}
    for bid, d in sorted(state.dwellings.items()):
        slice_hh = bid_to_hh.get(bid)
        if slice_hh is None:
            continue
        pids = (
            list(state.households.get(d.household_id, []))
            if d.household_id is not None else []
        )
        people: list[Any] = []
        for pid in pids:
            lp = state.persons[pid]
            base = original.get(pid)
            if base is not None:
                people.append(_dc.replace(
                    base, age=lp.age, econ_status=lp.econ_status,
                    health_state=lp.health_state,
                ))
                continue
            # Someone who arrived during the run: born, partnered in, or
            # moved in from outside the slice.
            tr = _trait_draws(gen, lp.age, age_mean, age_sd)
            people.append(PersonProfile(
                person_id=pid, age=lp.age,
                sex=("female" if lp.sex == "Female" else "male"),
                role=lp.role, econ_status=lp.econ_status,
                work_pattern=("day" if lp.econ_status == "at work" else "none"),
                remote_share=0.0,
                chronotype=tr["chronotype"],
                habit_strength=tr["habit_strength"],
                lapse_rate=tr["lapse_rate"],
                attention=tr["attention"],
                comfort=tr["comfort"],
                health_state=lp.health_state,
                caring_load="none",
                school_year=(max(lp.age - 4, 0) if 4 <= lp.age <= 18 else None),
                vehicle_access="none",
            ))
        # An empty list IS the vacancy: the premises stays in the slice and
        # keeps its standing load (run.py VACANT_FROST_SETPOINT_C), because a
        # vacant house is still connected to the feeder.
        households[slice_hh] = people

    pv = dict(sl.pv)
    owned = {k: {kk: dict(vv) for kk, vv in v.items()} for k, v in sl.owned.items()}
    # Copies, not references: a measure applied below writes to the building.
    #
    # copy.copy, NOT dataclasses.replace. `has_battery` and `has_ev` are not
    # declared fields of SynthBuilding - e1_run assigns them after
    # construction and every reader uses getattr(..., False) - so
    # dataclasses.replace silently DROPS them. Using it here lost the three
    # t0 batteries: applying year one to the slice produced a slice with no
    # batteries at all, where the original had three. copy.copy preserves
    # __dict__ and therefore the undeclared attributes.
    buildings = {k: _copy.copy(v) for k, v in sl.buildings.items()}
    applied: dict[str, int] = {}
    deferred: dict[str, int] = {}
    for bid, d in sorted(state.dwellings.items()):
        hh = bid_to_hh.get(bid)
        if hh is None:
            continue
        for measure in sorted(d.measures):
            if not MEASURE_APPLIED_IN_WEEK2.get(measure, False):
                deferred[measure] = deferred.get(measure, 0) + 1
                continue
            applied[measure] = applied.get(measure, 0) + 1
            if measure == "der_pv" and hh not in pv:
                from baile_nua.devices import der as der_mod

                # The SAME draw the slice uses at t0 (e1_run.build_slice), so
                # a system fitted in year 6 is drawn from the same
                # distribution as one fitted before the run started.
                kwp = float(np.clip(gen.normal(4.0, 1.2), 1.5, 8.0))
                pv[hh] = der_mod.PVSystem(
                    capacity_kwp=kwp,
                    azimuth_deg=float(np.clip(gen.normal(180.0, 40.0), 90.0, 270.0)),
                    tilt_deg=float(np.clip(gen.normal(32.0, 6.0), 12.0, 45.0)),
                    inverter_kw=min(kwp * 0.92, 5.0),
                    shading_factor=float(np.clip(gen.normal(0.94, 0.05), 0.70, 1.0)),
                )
            elif measure == "retrofit_heat_pump":
                owned.setdefault(hh, {})["heat_pump"] = {
                    "owned": True, "added_by": "WP5 retrofit",
                }
            elif measure == "der_battery":
                # Carried on the building, which is where the engine reads it,
                # so this writes to the COPY rather than to the slice.
                buildings[hh].has_battery = True
            elif measure == "der_smart_controls":
                owned.setdefault(hh, {})["smart_heating_control"] = {
                    "owned": True, "added_by": "WP5 DER adoption",
                }

    diag = dict(sl.diagnostics)
    diag.update({
        "wp5_year": state.year,
        "wp5_year_index": state.year_index,
        "n_homes": len(households),
        "n_people": sum(len(v) for v in households.values()),
        "n_vacant": sum(1 for v in households.values() if not v),
        "wp5_measures_applied": applied,
        "wp5_measures_deferred_to_week3_fabric": deferred,
        "wp5_deferral_note": (
            "Fabric retrofit and extension change the RC parameters, which is "
            "the week 3 fabric work (I-048). Their D03 passport events and D20 "
            "labels are recorded; the thermal parameters are untouched in "
            "week 2, so a detector scored against those labels in a week-2 "
            "package would be scored against a change the series does not "
            "contain."
        ),
    })
    return _dc.replace(
        sl, households=households, pv=pv, owned=owned, buildings=buildings,
        diagnostics=diag,
    )
