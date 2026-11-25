"""The semi-Markov activity and household engine (design 5.3, R15, R16, R23).

    **Semi-Markov core.**  Each person moves through about 30 activity states.
    Duration distributions are explicit, not geometric, and conditioned on
    person type, day type, season, time since waking and previous activity.

    **Household coupling.**  Joint activities planned at household level;
    shared resources as queues with priority rules, which produces realistic
    morning stagger; caring constraints; negotiation weighted by decision
    authority; influence at a slow timescale.

    **Bounded rationality.**  Agents act on habit first and only deliberate
    when a trigger is noticed... They satisfice rather than optimise... and have
    a calibrated lapse rate.

**What "semi-Markov" buys and why it matters here.**  In a plain Markov chain
the time spent in a state is geometric, so the probability of leaving is the
same in minute 1 and minute 90.  People do not cook that way.  A semi-Markov
process draws an explicit *duration* on entry, so cooking lasts about as long as
cooking lasts, and the hazard of stopping rises as it goes on.  That is what
makes appliance cycles land in plausible blocks rather than flickering.

**The presence invariant is structural, not checked afterwards.**  The engine
emits exactly one interval per person per minute by construction - a person's
day is a partition of the 1,440 minutes - so R23 ("cannot be in two places at
once") cannot be violated by an activity the engine schedules.  The invariant
test in :mod:`baile_nua.validation.invariants` still runs, because the *other*
sources of presence (trips, venue assignment, cross-household visits) can
violate it and because a check that is never run is not a check.
"""

from __future__ import annotations

import dataclasses
import functools
import math
from collections import defaultdict
from typing import Any

import numpy as np

from baile_nua.activity.hetus import (
    ACTIVITY_CODES,
    CALIBRATION_FLAG,
    ECON_TO_WSTATUS,
    hetus_diurnal,
    hetus_time_spent,
    hetus_time_spent_by_status,
    irish_departure_profile,
    irish_journey_time_profile,
)
from baile_nua.rng import SeedTree, Stream

__all__ = [
    "ActivityInterval",
    "PersonDay",
    "PersonProfile",
    "HouseholdDay",
    "ActivityEngine",
    "SHARED_RESOURCES",
    "MINUTES_PER_DAY",
    "CALIBRATION_FLAG",
]

MINUTES_PER_DAY = 1440

#: Shared resources modelled as queues with priority (design 5.3).
#: ``capacity`` is how many people can use it at once; the morning stagger the
#: design asks for emerges from the shower having capacity 1.
SHARED_RESOURCES: dict[str, dict[str, Any]] = {
    "shower": {"capacity": 1, "activities": ("shower_bath",), "zone": "bathroom"},
    "kitchen": {"capacity": 2, "activities": ("cooking", "washing_up"), "zone": "kitchen"},
    "tv_room": {"capacity": 6, "activities": ("tv_screens",), "zone": "living"},
    "car": {"capacity": 1, "activities": ("travel_commute", "travel_other"), "zone": "in_transit"},
}

#: Activities that are planned at household level and pull members in
#: (design 5.3 "joint activities").
JOINT_ACTIVITIES: dict[str, dict[str, Any]] = {
    "eating_main": {
        "typical_minute": 18 * 60 + 30,
        "spread_min": 45,
        "duration_min": 35,
        "pull_by_role": {"head": 0.92, "partner": 0.92, "child": 0.95, "parent": 0.85, "other": 0.55},
        "weekend_shift_min": 30,
    },
    "tv_screens": {
        "typical_minute": 20 * 60,
        "spread_min": 60,
        "duration_min": 95,
        "pull_by_role": {"head": 0.70, "partner": 0.72, "child": 0.60, "parent": 0.65, "other": 0.40},
        "weekend_shift_min": 15,
    },
}

#: Minimum and maximum plausible duration per activity, minutes. Bounds, not
#: targets: the duration is drawn from a distribution and clipped here so a
#: tail draw cannot produce a four-hour shower.
def _minutes_for(spec: dict[str, Any], by_code: dict[str, float]) -> float | None:
    """A modelled activity's minute target, summed over its HETUS codes.

    Returns ``None`` when no code of the activity is present at all, so a
    missing target stays visible rather than becoming a zero that looks like
    "nobody does this".  A code that IS present but NaN contributes nothing and
    the rest still sum - HETUS suppresses small cells, and dropping the whole
    activity because one of four codes is suppressed would be worse.

    A negative weight is a subtraction, which is how travel_other is
    AC9A minus AC913 rather than a declared share of AC9A.
    """
    total = 0.0
    seen = False
    for code, weight in spec["hetus"]:
        v = by_code.get(code)
        if v is None or (isinstance(v, float) and math.isnan(v)):
            continue
        seen = True
        total += float(v) * float(weight)
    if not seen:
        return None
    return max(total, 0.0)


DURATION_BOUNDS: dict[str, tuple[int, int]] = {
    "sleep": (180, 660), "nap": (15, 90),
    "personal_care": (5, 40), "shower_bath": (5, 25), "dressing": (3, 20),
    "cooking": (5, 90), "washing_up": (5, 30),
    "eating_main": (15, 75), "eating_snack": (5, 25),
    "laundry": (10, 60), "cleaning": (10, 90), "diy_repairs": (20, 180),
    "gardening": (20, 180), "childcare": (10, 180), "adult_care": (10, 180),
    "work_at_workplace": (180, 600), "work_at_home": (60, 540),
    "school": (240, 420), "study_at_home": (20, 180),
    "tv_screens": (20, 240), "reading": (10, 120), "hobbies": (20, 180),
    "social_at_home": (30, 240), "social_out": (45, 300),
    "sport_exercise": (30, 120), "shopping": (15, 90), "religion_civic": (30, 90),
    "travel_commute": (3, 150), "travel_other": (3, 60),
    "idle_at_home": (5, 120),
}


@dataclasses.dataclass
class ActivityInterval:
    person_id: str
    start_min: int
    end_min: int
    activity: str
    zone: str
    location_kind: str          # building | venue | in_transit | out_of_model
    trigger: str                # routine | joint plan | event | signal | disruption | lapse
    deliberated: bool
    joint_with: list[str] = dataclasses.field(default_factory=list)

    @property
    def duration_min(self) -> int:
        return self.end_min - self.start_min


@dataclasses.dataclass
class PersonProfile:
    """What the activity engine needs to know about a person.

    A narrow view on purpose: the engine takes the few fields it uses rather
    than a whole D05/D08 row, so it cannot accidentally depend on something the
    observable layer must never see.
    """

    person_id: str
    age: int
    sex: str
    role: str
    econ_status: str
    work_pattern: str
    remote_share: float
    chronotype: float
    habit_strength: float
    lapse_rate: float
    attention: float
    comfort: float
    health_state: str = "well"
    caring_load: str = "none"
    school_year: int | None = None
    vehicle_access: str = "none"

    @property
    def is_child(self) -> bool:
        return self.age < 18

    @property
    def is_worker(self) -> bool:
        return self.econ_status in ("employed", "self-employed")

    @property
    def is_student(self) -> bool:
        return self.econ_status == "student" or (5 <= self.age <= 18)


@dataclasses.dataclass
class PersonDay:
    person_id: str
    intervals: list[ActivityInterval]
    diagnostics: dict[str, Any] = dataclasses.field(default_factory=dict)

    def covers_the_day(self) -> bool:
        """Exactly one activity per minute, no gaps and no overlap."""
        if not self.intervals:
            return False
        s = sorted(self.intervals, key=lambda i: i.start_min)
        if s[0].start_min != 0 or s[-1].end_min != MINUTES_PER_DAY:
            return False
        return all(a.end_min == b.start_min for a, b in zip(s, s[1:]))

    def minutes_by_activity(self) -> dict[str, int]:
        out: dict[str, int] = defaultdict(int)
        for i in self.intervals:
            out[i.activity] += i.duration_min
        return dict(out)

    def at_home_minutes(self) -> int:
        return sum(i.duration_min for i in self.intervals if i.location_kind == "building")


@dataclasses.dataclass
class HouseholdDay:
    household_id: str
    sim_day: int
    person_days: dict[str, PersonDay]
    joint_plans: list[dict[str, Any]]
    queue_log: list[dict[str, Any]]
    diagnostics: dict[str, Any] = dataclasses.field(default_factory=dict)


#: The latest a worker or student wakes on a workday, derived from Cobh's own
#: Census departure distribution rather than declared: the 95th-percentile
#: departure band's end, less a getting-ready margin.
#:
#: This exists because U32 widened the wake distribution from a UK donor while
#: the commute comes from an Irish source. The Irish anchor has to bind: a
#: model in which 1% of Cobh's workers wake at 12:40 would be using HETUS to
#: overrule SAPS, which is backwards.
_GETTING_READY_MARGIN_MIN = 40


@functools.lru_cache(maxsize=1)
def _latest_workday_wake() -> int:
    from baile_nua.activity.hetus import irish_departure_profile

    prof = irish_departure_profile()
    bands, shares = prof["bands"], prof["shares"]
    total = sum(shares.values())
    cum = 0.0
    latest = 9 * 60
    for key in sorted(shares, key=lambda k: bands[k][0]):
        cum += shares[key] / total
        # The band's START, not its end: 95% of Cobh's workers have departed
        # by the start of the band that crosses the 95th percentile. Taking
        # the end gave 11:00, and so a cap of 10:20, which is not a workday
        # wake time for anybody holding a job.
        latest = bands[key][0]
        if cum >= 0.95:
            break
    return int(latest - _GETTING_READY_MARGIN_MIN)


_LATEST_WORKDAY_WAKE = _latest_workday_wake()


@functools.lru_cache(maxsize=1)
def _workday_wake_spread() -> float:
    """How much of HETUS's all-days wake spread a workday permits.

    Derived so that a worker at the 90th percentile wakes exactly at the
    Census-derived cap, rather than being clipped there. Comes out near 0.7,
    which reads as "the commute compresses the spread of workday waking to
    about seventy per cent of the all-days spread" - a statement about
    Cobh's commute meeting a UK dispersion, with both sides sourced.
    """
    from baile_nua.activity.sleep_timing import (
        offset_at_quantile,
        waketime_offsets,
    )

    base_wake = 7 * 60 + 10
    headroom = _LATEST_WORKDAY_WAKE - base_wake
    q90 = offset_at_quantile(waketime_offsets()["offsets"], 0.90)
    if q90 <= 0:
        return 1.0
    return float(min(max(headroom / q90, 0.2), 1.0))


_WORKDAY_WAKE_SPREAD = _workday_wake_spread()


#: Activities whose zone is ``outside`` and which happen AT THE DWELLING.
#:
#: The engine mapped every ``outside`` zone to ``location_kind="venue"``, which
#: conflates two different meanings of the word: "outdoors" and "away from
#: home". Gardening is the first: a person gardening is at their own building,
#: in their own garden, and recording them as being at a venue made 6,042
#: presence rows in a 14-day town run carry ``location_kind="venue"`` with no
#: venue to name - which is what the WP7 venue-consistency criterion found.
#:
#: Named as a set rather than special-cased, because the same conflation
#: applies to anything else outdoors-but-at-home that is added later: hanging
#: washing, DIY in a yard, a smoke on the step.
OUTDOORS_BUT_AT_HOME: frozenset[str] = frozenset({"gardening"})


class ActivityEngine:
    """Generates one household-day of activities for every member.

    Construction loads the HETUS targets and the Irish anchors once; generating
    a household-day is then pure computation against them, addressed through the
    seed tree so it is reproducible from ``(household_id, sim_day)`` alone.
    """

    def __init__(
        self, seed_tree: SeedTree, *, geo: str = "UK", wave: int = 2010,
        duration_weighted_timing: bool = False,
    ) -> None:
        self.tree = seed_tree
        # I-052, week 3 step 3. False is the delivered model: HETUS's
        # participation curves alone decide when an activity happens. True
        # restores the superseded weight - participation x daily duration
        # target - as an ablation arm, so the change is measured against LP1
        # rather than asserted.
        self.duration_weighted_timing = bool(duration_weighted_timing)
        ts = hetus_time_spent(geo=geo, wave=wave)
        self._targets = self._build_targets(ts)
        self._status_targets = self._build_status_targets(
            hetus_time_spent_by_status(geo=geo, wave=wave)
        )
        self._diurnal = self._build_diurnal(hetus_diurnal(geo=geo, wave=wave))
        self._departure = irish_departure_profile()
        self._journey = irish_journey_time_profile()
        self.calibration_flag = CALIBRATION_FLAG

    # -- targets -------------------------------------------------------------

    @staticmethod
    def _build_targets(ts: Any) -> dict[tuple[str, str], dict[str, float]]:
        """Daily minute targets per activity, by (sex, HETUS age group).

        HETUS's age groups are its own (``Y25-44`` and so on) and are kept
        rather than re-banded, so a target is never interpolated across a
        boundary HETUS itself drew.
        """
        out: dict[tuple[str, str], dict[str, float]] = {}
        for (sex, age), grp in ts.groupby(["sex", "age"]):
            by_code = grp.set_index("acl00")["minutes"].to_dict()
            per_activity: dict[str, float] = {}
            for name, spec in ACTIVITY_CODES.items():
                mins = _minutes_for(spec, by_code)
                if mins is None:
                    continue
                per_activity[name] = mins
            if per_activity:
                out[(str(sex), str(age))] = per_activity
        if not out:
            raise RuntimeError("no HETUS targets could be built")
        return out

    @staticmethod
    def _build_status_targets(ts: Any) -> dict[tuple[str, str], dict[str, float]]:
        """Daily minute targets per activity, by (sex, HETUS labour status)."""
        out: dict[tuple[str, str], dict[str, float]] = {}
        for (sex, status), grp in ts.groupby(["sex", "wstatus"]):
            by_code = grp.set_index("acl00")["minutes"].to_dict()
            per_activity: dict[str, float] = {}
            for name, spec in ACTIVITY_CODES.items():
                mins = _minutes_for(spec, by_code)
                if mins is None:
                    continue
                per_activity[name] = mins
            if per_activity:
                out[(str(sex), str(status))] = per_activity
        return out

    @staticmethod
    def _build_diurnal(dn: Any) -> dict[str, np.ndarray]:
        """Participation rate per minute of day, per HETUS broad group.

        The 10-minute slots are expanded to minutes by holding each slot's
        value, rather than interpolating: a participation rate is a rate over
        the slot, not a point sample at its start.
        """
        out: dict[str, np.ndarray] = {}
        for code, grp in dn[dn.sex == "T"].groupby("acl00"):
            arr = np.zeros(MINUTES_PER_DAY, dtype=np.float64)
            g = grp.sort_values("minute_of_day")
            mins = g["minute_of_day"].to_numpy()
            vals = g["participation_pct"].to_numpy() / 100.0
            for i, m in enumerate(mins):
                end = int(mins[i + 1]) if i + 1 < len(mins) else MINUTES_PER_DAY
                arr[int(m):end] = vals[i]
            # HETUS's day starts at 04:00; slots past midnight wrap.
            out[str(code)] = arr
        return out

    #: Which HETUS broad diurnal group each engine activity belongs to.
    _DIURNAL_GROUP: dict[str, str] = {
        "sleep": "AC0A", "nap": "AC0A", "personal_care": "AC0A",
        "shower_bath": "AC0A", "dressing": "AC0A",
        "eating_main": "AC02", "eating_snack": "AC02",
        "work_at_workplace": "AC1_2_TR", "work_at_home": "AC1_2_TR",
        "school": "AC1_2_TR", "study_at_home": "AC1_2_TR",
        "cooking": "AC3_TR", "washing_up": "AC3_TR", "laundry": "AC3_TR",
        "cleaning": "AC3_TR", "diy_repairs": "AC3_TR", "gardening": "AC3_TR",
        "childcare": "AC3_TR", "adult_care": "AC3_TR", "shopping": "AC3_TR",
        "tv_screens": "AC82",
        "reading": "AC4-8A", "hobbies": "AC4-8A", "social_at_home": "AC4-8A",
        "social_out": "AC4-8A", "sport_exercise": "AC4-8A",
        "religion_civic": "AC4-8A", "idle_at_home": "AC4-8A",
        "travel_commute": "AC9E", "travel_other": "AC9E",
    }

    @staticmethod
    def _hetus_age_group(age: int) -> str:
        if age < 20:
            return "Y15-20"
        if age < 25:
            return "Y20-24"
        if age < 45:
            return "Y25-44"
        if age < 65:
            return "Y45-64"
        if age < 75:
            return "Y65-74"
        return "Y_GE65"

    def targets_for(self, person: PersonProfile) -> dict[str, float]:
        """This person's daily minute targets.

        **Labour status first, age second.**  Design 5.3 wants durations
        "conditioned on person type", and labour status is by far the stronger
        conditioner: a full-time worker spends 5:07 a day on employment against
        2:37 for all persons. An age-only target makes every worker look like
        the population average, which flattens exactly the weekday occupancy
        difference the whole model exists to represent.

        HETUS has no row for under-15s, so a child falls back to the youngest
        band that exists; the fallback chain is explicit so a substitution is a
        visible choice rather than a silent default.
        """
        wstatus = ECON_TO_WSTATUS.get(person.econ_status)
        if person.is_child and person.age >= 5:
            wstatus = "EDUC"
        if person.work_pattern == "part-time" and wstatus == "EMP_FT":
            wstatus = "EMP_PT"
        if wstatus:
            for key in ((person.sex, wstatus), ("T", wstatus)):
                if key in self._status_targets:
                    return dict(self._status_targets[key])
        for key in (
            (person.sex, self._hetus_age_group(person.age)),
            ("T", self._hetus_age_group(person.age)),
            (person.sex, "TOTAL"),
            ("T", "TOTAL"),
        ):
            if key in self._targets:
                return dict(self._targets[key])
        raise RuntimeError(f"no HETUS target for {person.person_id}")

    # -- duration sampling ---------------------------------------------------

    def _draw_duration(
        self, activity: str, mean_min: float, gen: np.random.Generator,
        *, habit_strength: float,
    ) -> int:
        """Draw an explicit duration - the semi-Markov part.

        Lognormal, because durations are positive and right-skewed (most meals
        are 30 minutes, a few are two hours, none is negative), which a normal
        distribution cannot represent and a geometric distribution gets wrong at
        both ends.

        A strongly habitual person has a *tighter* duration distribution: doing
        the same thing for the same length of time is what habit means. That is
        design 5.3's habit strength acting on duration rather than only on
        choice.
        """
        lo, hi = DURATION_BOUNDS.get(activity, (5, 240))
        mean = float(np.clip(mean_min, lo, hi))
        # Habit tightens the spread from cv 0.55 down to 0.22.
        cv = 0.55 - 0.33 * float(np.clip(habit_strength, 0.0, 1.0))
        sigma = math.sqrt(math.log(1.0 + cv * cv))
        mu = math.log(max(mean, 1.0)) - 0.5 * sigma * sigma
        draw = float(gen.lognormal(mu, sigma))
        return int(np.clip(round(draw), lo, hi))

    def _diurnal_weight(self, activity: str, minute: int, chronotype: float) -> float:
        """How likely this activity is at this minute, from the HETUS profile.

        The person's chronotype shifts the profile: a late chronotype reads the
        profile as though it were earlier, which moves their whole day later.
        That is design 5.2's "chronotype | hours offset | Shifts the sleep
        window", applied to every activity rather than only to sleep, because a
        late riser also eats and showers later.
        """
        group = self._DIURNAL_GROUP.get(activity)
        prof = self._diurnal.get(group) if group else None
        if prof is None:
            return 1.0
        shifted = int((minute - chronotype * 60.0) % MINUTES_PER_DAY)
        return float(prof[shifted]) + 1e-4

    # -- the day skeleton ----------------------------------------------------

    def _sleep_window(
        self, person: PersonProfile, gen: np.random.Generator, *, is_workday: bool
    ) -> tuple[int, int]:
        """Wake and bed minutes, with the SPREAD taken from HETUS (U32, I-051).

        Returned as (wake, bed) in minutes from midnight, with bed on a clock
        that runs past 1440 for a bedtime after midnight; the engine wraps the
        night itself.

        **Medians stay Irish, spread comes from the UK donor.** The wake median
        is anchored to Cobh's own Census travel-to-work and time-leaving-home
        tables and the sleep duration to the design; what HETUS supplies is how
        much people differ, which transfers between countries far better than
        when they get up.

        What this replaced, and why. The old form was
        ``bed = wake - N(8.4h, 35min)`` with wake itself at sigma 22 minutes,
        giving a bedtime standard deviation near 41 minutes and a
        10th-to-90th-percentile range of about 106 minutes. HETUS UK's share
        asleep by time of day implies **187 minutes** and a tail reaching past
        02:50. A distribution that narrow cannot produce anyone still awake at
        one in the morning however its centre is placed, and that is what
        PL-PEAK-01 measured: 0.1% of the town awake at 02:00 against HETUS's
        6.9% (I-051).

        **Chronotype selects the quantile** rather than adding an offset of its
        own, so the population's marginal spread comes out as the source's
        instead of the source's convolved with the trait. The night-to-night
        jitter is small and separate: the same person is not at a different
        point of the population distribution every evening.
        """
        from baile_nua.activity import sleep_timing as st

        # ---- the Irish medians, unchanged ------------------------------
        # A workday structures the day only for somebody who has one. A
        # retired or unemployed person's Tuesday is not organised around a
        # commute, so they take the unstructured base even on a workday -
        # which the earlier version did not, and which was putting 29.5% of
        # the town awake at 06:00 against HETUS's 13.6%.
        structured = is_workday and (person.is_worker or person.is_student)
        base_wake = 7 * 60 + 10 if structured else 8 * 60 + 40
        if person.is_child:
            base_wake -= 10
        if person.age >= 70:
            base_wake -= 25
        sleep_target = 8.4 * 60 if not person.is_child else 9.6 * 60
        if person.age >= 70:
            sleep_target -= 25

        # ---- the HETUS spread ------------------------------------------
        # One quantile for the person, from their chronotype, plus a small
        # night-to-night wobble around it.
        u = st.quantile_for_chronotype(person.chronotype)
        # A small night-to-night wobble, and no more. The published curve is a
        # population-time cross-section, so it already contains both
        # between-person and within-person variation; adding a minute-scale
        # jitter on top of the offsets widened the result past the source and
        # put the early wake tail at 04:43 against HETUS's 06:10.
        u = float(np.clip(u + gen.normal(0.0, 0.03), 0.01, 0.99))
        wake_off = st.offset_at_quantile(st.waketime_offsets()["offsets"], u)
        bed_off = st.offset_at_quantile(st.bedtime_offsets()["offsets"], u)
        if structured:
            # The commute compresses the workday wake spread rather than
            # truncating it. Clipping at the cap piled 16.9% of workers onto a
            # single minute, which is a spike and not a distribution; damping
            # is monotone and keeps the shape. The factor is derived, not
            # declared: it is what puts the 90th percentile exactly at the cap.
            wake_off *= _WORKDAY_WAKE_SPREAD

        # Each of the two times gets its own HETUS spread about its own Irish
        # median. An earlier version computed bed from wake plus a bedtime
        # offset, which gave the bedtime BOTH spreads: its 10-to-90 range came
        # out at 389 minutes against the source's 187, its median moved from
        # 22:46 to 23:34, and a tenth of the town was pinned against the clip.
        # The same double-counting the chronotype mapping was designed to
        # avoid, committed one line further down.
        wake = base_wake + wake_off
        # A worker or student on a workday is bound by the commute, and the
        # commute comes from an IRISH source. So the Irish anchor caps the
        # UK-derived spread rather than the other way round - and a
        # non-worker keeps the full tail, which is where sleeping in
        # legitimately lives.
        wake = int(np.clip(wake, 4 * 60, 12 * 60))

        # The Irish median bedtime, from the design's sleep duration and a
        # FIXED wake anchor - not from this person's drawn wake, which would
        # inherit the wake spread on top of the bedtime one, and not from
        # their own base either.
        #
        # The fixed anchor matters. Giving non-workers the later wake base
        # fixed the morning (06:00 went from +0.159 to +0.054 against HETUS)
        # and broke the evening: because bedtime was derived from each
        # person's own base, a retired person waking at 08:40 was sent to bed
        # 90 minutes later too, and 23:00 went to +0.227. Waking later does
        # not mean going to bed later by the same amount - it means sleeping
        # longer, which is what HETUS implies anyway: its median bedtime near
        # 22:25 and median wake near 07:54 are about nine and a half hours
        # apart, where the design's target is 8.4.
        #
        # So bedtime is anchored once and wake is not, and the difference
        # between a worker's night and a non-worker's comes out as duration.
        bed_median_clock = (7 * 60 + 10) + MINUTES_PER_DAY - sleep_target
        bed_clock = bed_median_clock + bed_off
        # The band the source covers: 19:00 to just past 03:00. Taken from the
        # curve's own support rather than declared, so the top percentile is
        # not pinned against a clip the source does not imply.
        return wake, int(np.clip(bed_clock, 19 * 60, 27 * 60 + 30))

    def _work_window(
        self, person: PersonProfile, gen: np.random.Generator, *, is_workday: bool
    ) -> tuple[int, int, int, bool] | None:
        """Departure, arrival-home and journey minutes, from the IRISH anchors.

        Departure time comes from Cobh's own Census band distribution
        (SAPS T11_2) and journey time from T11_3 - not from HETUS, which has no
        Irish row. This is the Irish recalibration U04 asked for, applied to the
        quantity that most affects occupancy and the morning peak.
        """
        if not is_workday:
            return None
        if person.is_student and not person.is_worker:
            # School hours are set by the school day, not by a commute band.
            start = 9 * 60 + int(gen.normal(0, 8))
            length = 6 * 60 + 20 + int(gen.normal(0, 15))
            travel = int(np.clip(gen.normal(14, 6), 4, 45))
            return start - travel, start + length + travel, travel, False
        if not person.is_worker:
            return None

        remote_today = float(gen.random()) < float(np.clip(person.remote_share, 0.0, 1.0))
        if remote_today:
            return None    # works at home; no commute window

        bands = self._departure["bands"]
        shares = self._departure["shares"]
        labels = sorted(shares)
        p = np.array([shares[k] for k in labels], dtype=np.float64)
        band = labels[int(gen.choice(len(labels), p=p / p.sum()))]
        lo, hi = bands[band]
        depart = int(gen.integers(lo, hi + 1))

        jb = self._journey["bands"]
        js = self._journey["shares"]
        jl = sorted(js)
        jp = np.array([js[k] for k in jl], dtype=np.float64)
        jband = jl[int(gen.choice(len(jl), p=jp / jp.sum()))]
        jlo, jhi = jb[jband]
        journey = int(gen.integers(jlo, jhi + 1))

        if person.work_pattern == "shift":
            # Shift work moves the whole window; the Census departure bands
            # describe the daytime commute, so a shift worker is shifted off it.
            depart = int((depart + gen.choice([-6 * 60, 6 * 60, 8 * 60])) % MINUTES_PER_DAY)
        hours = 8.0 if person.work_pattern != "part-time" else 4.5
        length = int(gen.normal(hours * 60, 28))
        return depart, depart + journey + length + journey, journey, False

    # -- the main entry point ------------------------------------------------

    def generate_household_day(
        self,
        household_id: str,
        people: list[PersonProfile],
        *,
        sim_day: int,
        is_workday: bool,
        is_school_day: bool,
        season: str,
        disruptions: dict[str, list[dict[str, Any]]] | None = None,
        was_workday: bool | None = None,
    ) -> HouseholdDay:
        """One household-day: every member's minute-by-minute activity.

        Order of work, which matters:

        1. **Skeletons.** Each person's sleep and work/school windows, from
           chronotype and the Irish Census anchors.
        2. **Joint plans.** Household-level activities (the evening meal, family
           TV), planned once and then offered to members by role.
        3. **Fill.** The gaps between fixed blocks are filled from the HETUS
           duration targets, weighted by the HETUS diurnal profile.
        4. **Shared-resource queues.** Contention is resolved by priority, which
           is what produces the morning stagger rather than everyone showering
           at 07:30.
        5. **Lapses.** A calibrated lapse rate perturbs the result.
        """
        disruptions = disruptions or {}
        people = sorted(people, key=lambda p: p.person_id)
        hh_gen = self.tree.generator(
            Stream.HOUSEHOLD_COUPLING, entity=household_id, sim_day=sim_day
        )

        # ---- 2. joint plans, at household level ----------------------------
        joint_plans: list[dict[str, Any]] = []
        for name, spec in JOINT_ACTIVITIES.items():
            shift = 0 if is_workday else spec["weekend_shift_min"]
            centre = spec["typical_minute"] + shift + int(hh_gen.normal(0, spec["spread_min"] / 2))
            joint_plans.append(
                {
                    "activity": name,
                    "start_min": int(np.clip(centre, 10 * 60, 23 * 60)),
                    "duration_min": int(
                        max(10, hh_gen.normal(spec["duration_min"], spec["duration_min"] * 0.22))
                    ),
                    "pull_by_role": spec["pull_by_role"],
                    "participants": [],
                }
            )

        # ---- 1 and 3. per-person skeleton and fill -------------------------
        person_days: dict[str, PersonDay] = {}
        for person in people:
            gen = self.tree.generator(
                Stream.ACTIVITY_SEQUENCE, entity=person.person_id, sim_day=sim_day
            )
            dgen = self.tree.generator(
                Stream.ACTIVITY_DURATION, entity=person.person_id, sim_day=sim_day
            )
            # I-044: yesterday's bedtime, re-drawn from the same counter-based
            # stream yesterday used. None on day 0, where there is no
            # yesterday and the day legitimately starts asleep.
            prev_bed: int | None = None
            if sim_day > 0:
                prev_gen = self.tree.generator(
                    Stream.ACTIVITY_SEQUENCE, entity=person.person_id,
                    sim_day=sim_day - 1,
                )
                _w, prev_bed = self._sleep_window(
                    person, prev_gen,
                    is_workday=(was_workday if was_workday is not None
                                else is_workday),
                )
            person_days[person.person_id] = self._generate_person_day(
                person, gen, dgen,
                prev_bed_minute=prev_bed,
                sim_day=sim_day, is_workday=is_workday,
                is_school_day=is_school_day, season=season,
                joint_plans=joint_plans, hh_gen=hh_gen,
                disruptions=disruptions.get(person.person_id, []),
            )

        # ---- 4. shared-resource queues -------------------------------------
        queue_log = self._resolve_shared_resources(person_days, people, hh_gen)

        # ---- 5. caring constraint: no under-12 alone ------------------------
        care_log = self._enforce_child_supervision(person_days, people, hh_gen)

        return HouseholdDay(
            household_id=household_id,
            sim_day=sim_day,
            person_days=person_days,
            joint_plans=joint_plans,
            queue_log=queue_log,
            diagnostics={
                "n_people": len(people),
                "is_workday": is_workday,
                "is_school_day": is_school_day,
                "season": season,
                "calibration_flag": self.calibration_flag,
                "queue_deferrals": len(queue_log),
                "supervision_adjustments": len(care_log),
                "supervision_log": care_log[:10],
                "all_days_cover_1440_minutes": all(
                    d.covers_the_day() for d in person_days.values()
                ),
            },
        )

    # -- one person's day ----------------------------------------------------

    def _generate_person_day(
        self,
        person: PersonProfile,
        gen: np.random.Generator,
        dgen: np.random.Generator,
        *,
        sim_day: int,
        is_workday: bool,
        is_school_day: bool,
        season: str,
        joint_plans: list[dict[str, Any]],
        hh_gen: np.random.Generator,
        disruptions: list[dict[str, Any]],
        prev_bed_minute: int | None = None,
    ) -> PersonDay:
        # A minute-indexed plan; None means "not yet decided".
        plan: list[str | None] = [None] * MINUTES_PER_DAY
        triggers: dict[int, str] = {}
        joint_at: dict[int, list[str]] = {}

        illness = any(d.get("kind") == "illness" for d in disruptions)
        remote_forced = any(d.get("kind") == "remote_work" for d in disruptions)

        def place(a: int, b: int, activity: str, trigger: str) -> None:
            for m in range(max(a, 0), min(b, MINUTES_PER_DAY)):
                if plan[m] is None:
                    plan[m] = activity
                    triggers[m] = trigger

        # ---- sleep -----------------------------------------------------
        wake, bed = self._sleep_window(person, gen, is_workday=is_workday)
        # I-044. The small hours belong to YESTERDAY's bedtime, not to this
        # day's midnight.
        #
        # `_sleep_window` already draws bedtimes as late as 02:30 and the
        # branch below already understood that "a bedtime past midnight means
        # this day ends AWAKE". But `place(0, wake, "sleep")` then claimed
        # minutes 0 to wake unconditionally, so a person who went to bed at
        # 01:30 was overwritten as asleep from 00:00 and the late bedtime was
        # computed and discarded. The result was that NOBODY in the town was
        # awake after midnight, on any night: the awake share went 0.33 at
        # 23:00 and 0.00 at 00:00, and the aggregate load fell to its standby
        # floor at exactly midnight.
        #
        # That is what PL-PEAK-01 caught. ESB Networks' LP1 falls from 0.77x
        # the daily mean at midnight to 0.45x at 04:00 - a taper of 1.72 -
        # because real households wind down through the small hours. The model
        # measured 0.95, which is no taper at all.
        #
        # `prev_bed_minute` is yesterday's drawn bedtime on a 0-to-26:30 clock.
        # It is recoverable deterministically because the RNG is counter-based
        # and keyed by (person, sim_day), so asking for sim_day - 1 gives
        # exactly the number yesterday's own generation used.
        sleep_starts_at = 0
        if prev_bed_minute is not None and prev_bed_minute > MINUTES_PER_DAY:
            sleep_starts_at = min(prev_bed_minute - MINUTES_PER_DAY, wake)
        place(sleep_starts_at, wake, "sleep", "routine")
        if bed < MINUTES_PER_DAY:
            place(bed, MINUTES_PER_DAY, "sleep", "routine")
        # A bedtime past midnight means this day ends AWAKE, and tomorrow's
        # own `place(sleep_starts_at, wake)` now accounts for the sleep. The
        # old branch here tried to wrap it and did two wrong things: the first
        # call was a silent no-op (its end minute was 0, so the range was
        # empty) and the second placed a single minute of sleep at 23:59,
        # which showed up as 19% of all sleep intervals being one or two
        # minutes long.

        # ---- illness: home-bound, more sleep ----------------------------
        if illness:
            place(wake, wake + int(gen.integers(60, 240)), "sleep", "disruption")

        # ---- morning routine -------------------------------------------
        m = wake
        for act in ("personal_care", "shower_bath", "dressing"):
            if act == "shower_bath" and float(gen.random()) > 0.62:
                continue   # not everyone showers every morning
            target = self.targets_for(person).get(act, 10.0)
            dur = self._draw_duration(act, target, dgen, habit_strength=person.habit_strength)
            place(m, m + dur, act, "routine")
            m += dur
        # breakfast. The duration target is HETUS's for this person, not a
        # hard-coded 15 minutes: every other episode in the day is drawn
        # around a target from `targets_for`, and breakfast was the one place
        # a clock number stood in for the source.
        dur = self._draw_duration(
            "eating_snack", self.targets_for(person).get("eating_snack", 15.0),
            dgen, habit_strength=person.habit_strength)
        place(m, m + dur, "eating_snack", "routine")
        m += dur

        # ---- work or school --------------------------------------------
        work = None if illness else self._work_window(
            person, gen, is_workday=is_workday and not remote_forced
        )
        if work is not None:
            depart, home, journey, _ = work
            place(depart, depart + journey, "travel_commute", "routine")
            activity = "school" if (person.is_student and not person.is_worker) else "work_at_workplace"
            place(depart + journey, home - journey, activity, "routine")
            place(home - journey, home, "travel_commute", "routine")
        elif person.is_worker and is_workday and not illness:
            # Working from home: the day is anchored to office hours, not to a
            # commute, which is why remote days flatten the morning peak.
            start = 9 * 60 + int(gen.normal(0, 25))
            length = int(gen.normal(7.4 * 60, 45))
            place(start, start + length, "work_at_home", "routine")

        # ---- joint plans: offered by role, accepted probabilistically ----
        for jp in joint_plans:
            p_accept = jp["pull_by_role"].get(person.role, 0.5)
            if illness and jp["activity"] != "eating_main":
                p_accept *= 0.4
            if float(hh_gen.random()) > p_accept:
                continue
            a, b = jp["start_min"], jp["start_min"] + jp["duration_min"]
            # Only if the person is free and at home for that whole block.
            if any(plan[x] is not None for x in range(a, min(b, MINUTES_PER_DAY))):
                continue
            place(a, b, jp["activity"], "joint plan")
            jp["participants"].append(person.person_id)
            for x in range(a, min(b, MINUTES_PER_DAY)):
                joint_at.setdefault(x, []).append(jp["activity"])

        # ---- caring obligations ----------------------------------------
        if person.caring_load in ("child", "both") and not person.is_child:
            for _ in range(int(gen.integers(1, 4))):
                start = int(gen.integers(wake + 60, min(bed, MINUTES_PER_DAY) - 60))
                dur = self._draw_duration("childcare", 45.0, dgen,
                                          habit_strength=person.habit_strength)
                place(start, start + dur, "childcare", "routine")
        if person.caring_load in ("elderly", "both") and not person.is_child:
            start = int(gen.integers(wake + 120, min(bed, MINUTES_PER_DAY) - 90))
            dur = self._draw_duration("adult_care", 60.0, dgen,
                                      habit_strength=person.habit_strength)
            place(start, start + dur, "adult_care", "routine")

        # ---- fill the gaps from the HETUS targets, diurnally weighted ----
        #
        # Each activity carries a BUDGET: its HETUS daily target, decremented as
        # the day fills. Without it the fill concentrated on whichever activity
        # had the highest diurnal weight - measured, 338 minutes of television
        # against a HETUS target of 142 - because the non-deliberate path takes
        # the argmax and nothing stopped it taking the same one all evening.
        #
        # Budgets also make the daily totals match HETUS, which is what design
        # 7.3's "time-use activity shares within survey sampling error" row
        # actually compares. Activities already placed by the skeleton (sleep,
        # work, the joint meal) are charged against their budgets first, so the
        # fill only spends what is left.
        targets = self.targets_for(person)
        fillable = [
            a for a in targets
            if a not in ("sleep", "work_at_workplace", "school", "travel_commute")
            and targets[a] > 0.5
        ]
        if illness:
            fillable = [a for a in fillable
                        if ACTIVITY_CODES[a]["zone"] not in ("outside",)]

        budget: dict[str, float] = {}
        already: dict[str, int] = defaultdict(int)
        for v in plan:
            if v is not None:
                already[v] += 1
        for a in fillable:
            lo_a, _hi_a = DURATION_BOUNDS.get(a, (5, 240))
            if targets[a] < lo_a:
                # A LOW-FREQUENCY activity, and it needs an occurrence
                # probability rather than a budget.
                #
                # A daily target below one episode's minimum length does not
                # mean a few minutes every day. Sport at 4 minutes a day is
                # really 30 minutes twice a week; laundry at 7 minutes a day is
                # really 25 minutes three times a week. Treating such a target
                # as a daily budget had two failure modes in turn: before the
                # episode floor it produced a 2-minute daily sliver of sport,
                # and after the floor it excluded the activity from contention
                # for ever, so no washing machine in the estate ever ran.
                #
                # So the target is spent as a whole episode on a fraction of
                # days. Mean-preserving exactly: E[minutes] = p * length =
                # target, by construction of p.
                length = self._draw_duration(
                    a, lo_a, dgen, habit_strength=person.habit_strength
                )
                p_day = min(targets[a] / max(length, 1), 1.0)
                budget[a] = float(length) if float(dgen.random()) < p_day else 0.0
                budget[a] = max(budget[a] - already.get(a, 0), 0.0)
                continue
            # The budget is a DAY'S DRAW around the target, not a flat ceiling.
            #
            # A flat 1.35x headroom put every always-available activity at
            # exactly 1.34x its target - measured across four different person
            # types, television came out at 1.34, 1.34, 1.35 and 1.34 - because
            # such an activity fills to its cap every single day. A
            # mean-preserving lognormal draw instead gives the right long-run
            # average while still letting an individual day run long or short,
            # which is what a day actually does.
            #
            # cv 0.45 is wide on purpose: day-to-day variation in how long one
            # person watches television is large, and design 7.3 compares the
            # DISTRIBUTION of daily profiles, not only the mean.
            cv = 0.45
            sigma = math.sqrt(math.log(1.0 + cv * cv))
            mu = math.log(max(targets[a], 1.0)) - 0.5 * sigma * sigma
            draw = float(dgen.lognormal(mu, sigma))
            budget[a] = max(min(draw, targets[a] * 3.0) - already.get(a, 0), 0.0)

        guard = 0
        while None in plan and guard < 4000:
            guard += 1
            start = plan.index(None)
            # How long the gap is.
            end = start
            while end < MINUTES_PER_DAY and plan[end] is None:
                end += 1
            gap = end - start
            weights = np.array(
                [
                    # I-052, week 3 step 3. The HETUS participation curve
                    # ALONE decides when, with the budget acting only as a
                    # gate on what is still available.
                    #
                    # It used to be multiplied by `(targets[a] + 1.0)`, the
                    # activity's daily duration target, and that double-counts
                    # duration: a participation rate is already the share of
                    # people doing the activity at that minute, which embeds
                    # how prevalent it is AND how long it lasts. Multiplying by
                    # the daily total again gives every long activity a
                    # standing advantage at every minute of the day, which is
                    # how television and late appliance cycles came to run on
                    # past the hour the meters say they stop - the 1.59x
                    # over-draw per awake person at 23:00 that I-052 measured.
                    #
                    # The daily totals do not need this factor and never did:
                    # `budget[a]` is drawn around `targets[a]` and decremented
                    # by every episode placed, so how MUCH of each activity a
                    # person does is governed there. The weight only has to say
                    # WHEN, and HETUS publishes exactly that.
                    #
                    # What this gives up, stated because it is a real cost:
                    # HETUS's diurnal table is published per broad group, so
                    # activities sharing a group - reading, hobbies,
                    # social_at_home and four others all sit in AC4-8A - now
                    # share a curve and are chosen between on budget alone. The
                    # old factor broke those ties by duration. That tie-break
                    # was not evidence; it was the same double count, and
                    # pretending HETUS distinguishes within a group it does not
                    # publish within is worse than admitting it cannot.
                    self._diurnal_weight(a, start, person.chronotype)
                    # D-078. The tie-break HETUS cannot make. Its diurnal
                    # table is published per BROAD GROUP - nine engine
                    # activities share AC3_TR and seven share AC4-8A - so
                    # inside a group the participation curve is identical and
                    # something has to choose. The REMAINING budget does:
                    #
                    #   * it is flat in the minute within a scheduling pass,
                    #     so the TIME profile is still the participation curve
                    #     alone, which is what step 3 required;
                    #   * it is drawn around the HETUS time-spent target and
                    #     decremented by every episode placed, so the daily
                    #     totals stay HETUS's;
                    #   * an activity SELF-DEPRIORITISES as it is consumed,
                    #     which the static target could not do. The static
                    #     weight kept an almost-spent activity at full weight,
                    #     so it was chosen and then truncated to its remnant -
                    #     the I-028 pathology, 45 episodes per person-day
                    #     against a diary's 20 to 25, a third of them one or
                    #     two minutes long.
                    #
                    # +1.0 so that an activity at the floor of its budget is
                    # not weighted at exactly zero while still being eligible.
                    * ((targets[a] + 1.0) if self.duration_weighted_timing
                       else budget.get(a, 0.0) + 1.0)
                    # A budget with less than one whole episode left in it
                    # removes the activity from contention. The test used to be
                    # ">= 1.0 minute", and spending a 2-minute remnant as a
                    # 2-minute episode is how the engine came to emit 45
                    # activity episodes per person-day against the 20 to 25 a
                    # real diary records - a third of them one or two minutes
                    # long, late in the evening, as every budget ran down
                    # together (I-028).
                    * (1.0 if budget.get(a, 0.0) >= DURATION_BOUNDS.get(a, (5, 240))[0]
                       else 0.0)
                    for a in fillable
                ],
                dtype=np.float64,
            )
            if weights.sum() <= 0:
                # Every budget is spent but the day is not full.
                #
                # Dumping the remainder into "idle_at_home" was the obvious
                # thing and it was wrong: it put 261 minutes a day of idling on
                # a retired person against a 38-minute target, a factor of 6.8,
                # and the surplus landed on one activity instead of on the
                # activities that person actually does. A real person whose
                # planned day runs short does MORE of what they do.
                #
                # So the budgets are reopened in proportion to the person's own
                # targets, sized to the remaining free time. The activity MIX is
                # preserved; only the totals stretch.
                remaining = sum(
                    1 for v in plan[start:] if v is None
                ) + sum(1 for v in plan[:start] if v is None)
                tgt_sum = sum(targets[a] for a in fillable) or 1.0
                for a in fillable:
                    budget[a] = max(budget.get(a, 0.0),
                                    remaining * targets[a] / tgt_sum)
                # The same participation-only weight as above. Reopening the
                # budgets changes how much is available, not when it happens.
                weights = np.array(
                    [
                        self._diurnal_weight(a, start, person.chronotype)
                        * ((targets[a] + 1.0) if self.duration_weighted_timing
                           else budget.get(a, 0.0) + 1.0)
                        * (1.0 if budget.get(a, 0.0)
                           >= DURATION_BOUNDS.get(a, (5, 240))[0] else 0.0)
                        for a in fillable
                    ],
                    dtype=np.float64,
                )
                if weights.sum() <= 0:
                    # Genuinely nothing left to assign: only then is it idle.
                    place(start, end, "idle_at_home", "routine")
                    continue
            # Bounded rationality: habit first, deliberation only sometimes
            # (design 5.3). A habitual, inattentive person takes the
            # highest-weight option; otherwise they sample.
            # Only activities that FIT the gap are candidates. Choosing first
            # and truncating afterwards is what put a 31-minute social_out into
            # a gap against its own 45-minute floor: the duration bound then
            # describes nothing, because any gap could override it.
            fits = np.array(
                [1.0 if DURATION_BOUNDS.get(a, (5, 240))[0] <= gap else 0.0
                 for a in fillable],
                dtype=np.float64,
            )
            if (weights * fits).sum() > 0:
                weights = weights * fits
            deliberate = float(gen.random()) < person.attention * (1.0 - person.habit_strength * 0.6)
            if deliberate:
                activity = fillable[int(gen.choice(len(fillable), p=weights / weights.sum()))]
            else:
                activity = fillable[int(np.argmax(weights))]
            lo, _hi = DURATION_BOUNDS.get(activity, (5, 240))

            # A gap too short to hold one real episode of ANY fillable activity
            # is absorbed by whatever is next to it, not filled with a sliver.
            # A real diary has no two-minute gaps between activities because a
            # real person does not change what they are doing for two minutes;
            # the gap is an artefact of placing fixed blocks, so it belongs to
            # the activity it interrupts.
            floor = min(DURATION_BOUNDS.get(a, (5, 240))[0] for a in fillable)
            if gap < floor:
                if start > 0 and plan[start - 1] is not None:
                    neighbour = str(plan[start - 1])
                    place(start, end, neighbour, triggers.get(start - 1, "routine"))
                elif end < MINUTES_PER_DAY and plan[end] is not None:
                    place(start, end, str(plan[end]), triggers.get(end, "routine"))
                else:
                    place(start, end, activity, "routine")
                continue

            dur = min(
                gap,
                int(budget.get(activity, gap)) or gap,
                self._draw_duration(activity, max(targets[activity], lo), dgen,
                                    habit_strength=person.habit_strength),
            )
            # Never shorter than one episode of this activity: the budget caps
            # how MANY minutes it gets over the day, not how short one sitting
            # may be.
            if dur < lo:
                dur = min(gap, lo)
            place(start, start + dur, activity, "routine")
            budget[activity] = max(budget.get(activity, 0.0) - dur, 0.0)

        for i, v in enumerate(plan):
            if v is None:
                plan[i] = "idle_at_home"
                triggers[i] = "routine"

        # ---- bracket out-of-home activities with travel ------------------
        #
        # A person who goes shopping does not teleport. Without this, realised
        # travel came out at 49 minutes a day against HETUS's 127 - about 60%
        # short - because travel only ever appeared as the commute. Bracketing
        # each out-of-home block with a short trip either side both fixes the
        # budget and puts the travel where it actually happens, which matters
        # for D12 trips and for the EV state of charge.
        plan = self._bracket_with_travel(plan, triggers, person, dgen)

        # ---- lapses (design 5.3 "a calibrated lapse rate") ---------------
        n_lapses = int(gen.poisson(person.lapse_rate * 3.0))
        for _ in range(n_lapses):
            at = int(gen.integers(wake, min(bed, MINUTES_PER_DAY)))
            triggers[at] = "lapse"

        intervals = self._to_intervals(person, plan, triggers, joint_at)
        return PersonDay(
            person_id=person.person_id,
            intervals=intervals,
            diagnostics={
                "wake_min": wake,
                "bed_min": bed,
                "work_window": work,
                "illness": illness,
                "n_lapses": n_lapses,
                "n_intervals": len(intervals),
                "fill_iterations": guard,
                "minutes_by_activity": {},
            },
        )

    @staticmethod
    def _bracket_with_travel(
        plan: list[str | None],
        triggers: dict[int, str],
        person: PersonProfile,
        gen: np.random.Generator,
    ) -> list[str | None]:
        """Put a short trip either side of each out-of-home block.

        The trip is taken out of the block itself, not added to the day, so the
        day still partitions 1,440 minutes exactly and the presence invariant
        stays structural. A block too short to give up the time is left alone -
        a five-minute errand is not worth modelling a trip for.
        """
        out = list(plan)
        away = {
            a for a, spec in ACTIVITY_CODES.items()
            if spec["zone"] == "outside" and a not in ("work_at_workplace", "school")
        }
        m = 0
        n = len(out)
        while m < n:
            act = out[m]
            if act not in away:
                m += 1
                continue
            end = m
            while end < n and out[end] == act:
                end += 1
            block = end - m
            # Need room for a trip each way plus something worth going for -
            # and "something worth going for" is the activity's OWN floor, not
            # a flat 10 minutes. With a flat 10 the bracket could cut a
            # 45-minute-floor social_out down to a 10-minute core, so the
            # duration bound described nothing. The leg shrinks to fit rather
            # than the bracket being skipped, because skipping it lost the
            # travel the day is supposed to contain.
            core = DURATION_BOUNDS.get(str(act), (5, 240))[0]
            leg = int(np.clip(gen.normal(9, 4), 3, 25))
            leg = min(leg, max((block - core) // 2, 0))
            if leg >= 3:
                for k in range(m, m + leg):
                    out[k] = "travel_other"
                    triggers[k] = "routine"
                for k in range(end - leg, end):
                    out[k] = "travel_other"
                    triggers[k] = "routine"
            m = end
        return out

    @staticmethod
    def _to_intervals(
        person: PersonProfile,
        plan: list[str | None],
        triggers: dict[int, str],
        joint_at: dict[int, list[str]],
    ) -> list[ActivityInterval]:
        """Collapse the minute plan into intervals.

        This is where the presence invariant becomes structural: the plan is a
        complete partition of 1,440 minutes, so the intervals it collapses to
        are contiguous and non-overlapping by construction.
        """
        out: list[ActivityInterval] = []
        start = 0
        for m in range(1, MINUTES_PER_DAY + 1):
            if m == MINUTES_PER_DAY or plan[m] != plan[start]:
                activity = str(plan[start])
                spec = ACTIVITY_CODES.get(activity, {"zone": "living"})
                zone = str(spec["zone"])
                kind = (
                    "in_transit" if zone == "in_transit"
                    # Outdoors AT HOME is not a venue: see
                    # OUTDOORS_BUT_AT_HOME.
                    else "building" if activity in OUTDOORS_BUT_AT_HOME
                    else "venue" if zone == "outside"
                    else "building"
                )
                out.append(
                    ActivityInterval(
                        person_id=person.person_id,
                        start_min=start, end_min=m,
                        activity=activity, zone=zone, location_kind=kind,
                        trigger=triggers.get(start, "routine"),
                        deliberated=triggers.get(start) == "joint plan",
                        joint_with=list(dict.fromkeys(joint_at.get(start, []))),
                    )
                )
                start = m
        return out

    # -- shared resources: the morning stagger -------------------------------

    def _resolve_shared_resources(
        self,
        person_days: dict[str, PersonDay],
        people: list[PersonProfile],
        gen: np.random.Generator,
    ) -> list[dict[str, Any]]:
        """Resolve contention for shared resources by priority (design 5.3).

            Shared resources (one shower, one hot-water tank, one car, one TV
            room, one kitchen) are modelled as queues with priority rules, which
            produces realistic morning stagger.

        **Why this produces stagger rather than just moving people.**  Each
        person independently wants the shower at about the same time, because
        their morning routines are anchored to similar wake times.  Deferring
        the lower-priority claimant by the length of the current occupancy - not
        by a random amount - means the second person starts exactly when the
        first finishes, the third after the second, and so on.  The stagger is
        therefore an emergent consequence of a capacity-1 resource, which is
        what design 7.3's "morning stagger" statistic measures.

        Priority: whoever has to leave earliest goes first, which is how
        households actually settle it.  Ties break on person id, so the result
        does not depend on iteration order.
        """
        by_person = {p.person_id: p for p in people}
        # Departure minute, or a large number for someone with nowhere to be.
        def priority(pid: str) -> tuple[int, str]:
            d = person_days[pid].diagnostics.get("work_window")
            depart = d[0] if d else 10_000
            return (int(depart), pid)

        log: list[dict[str, Any]] = []
        for res_name, spec in sorted(SHARED_RESOURCES.items()):
            capacity = int(spec["capacity"])
            acts = set(spec["activities"])
            # Claims on this resource: (start, end, person_id, interval index)
            claims: list[tuple[int, int, str, int]] = []
            for pid, day in person_days.items():
                for ix, iv in enumerate(day.intervals):
                    if iv.activity in acts:
                        claims.append((iv.start_min, iv.end_min, pid, ix))
            if len(claims) <= capacity:
                continue
            # Sweep time; whenever more than `capacity` are active, defer the
            # lowest-priority claimant to just after the current occupant.
            claims.sort(key=lambda c: (c[0], priority(c[2])))
            active: list[tuple[int, str]] = []       # (end, person_id)
            for start, end, pid, ix in claims:
                active = [(e, p) for (e, p) in active if e > start]
                if len(active) < capacity:
                    active.append((end, pid))
                    continue
                # Defer: start when the earliest-finishing occupant is done.
                active.sort()
                free_at = active[0][0]
                shift = free_at - start
                if shift <= 0:
                    continue
                day = person_days[pid]
                moved = self._shift_interval(day, ix, shift)
                log.append(
                    {
                        "resource": res_name, "person_id": pid,
                        "wanted_at": start, "deferred_to": start + shift,
                        "shift_min": shift, "applied": moved,
                        "reason": f"{res_name} at capacity {capacity}",
                    }
                )
                active.append((end + shift, pid))
        return log

    @staticmethod
    def _shift_interval(day: PersonDay, ix: int, shift: int) -> bool:
        """Move one interval later by ``shift``, taking the time from the next.

        Returns False if there is not enough room, in which case the claim is
        left alone and the log records that the deferral could not be applied -
        a household with a single shower and five people leaving at 07:30
        genuinely cannot satisfy everyone, and pretending otherwise would hide
        the constraint.
        """
        if ix + 1 >= len(day.intervals) or shift <= 0:
            return False
        cur = day.intervals[ix]
        nxt = day.intervals[ix + 1]
        if nxt.duration_min <= shift:
            return False
        prev_end = cur.start_min
        cur.start_min += shift
        cur.end_min += shift
        nxt.start_min += shift
        if ix > 0:
            day.intervals[ix - 1].end_min = cur.start_min
        else:
            cur.start_min = prev_end
            cur.end_min = prev_end + (cur.end_min - cur.start_min)
        return True

    # -- caring constraint ---------------------------------------------------

    def _enforce_child_supervision(
        self,
        person_days: dict[str, PersonDay],
        people: list[PersonProfile],
        gen: np.random.Generator,
    ) -> list[dict[str, Any]]:
        """A child under 12 is never home alone (design 5.3, and a V0 invariant).

        Enforced here rather than left to the invariant check, because the
        invariant's job is to *detect* a violation and this is where the model
        is supposed to prevent one.  Where a gap is found, the supervising adult
        with the least to give up - the one whose activity at that minute is
        most flexible - is brought home.

        Adults are chosen in sorted id order among those tied on flexibility, so
        the outcome does not depend on dict ordering.
        """
        kids = [p for p in people if p.age < 12]
        if not kids:
            return []
        adults = sorted((p for p in people if p.age >= 18), key=lambda p: p.person_id)
        if not adults:
            return []   # a household of only children: caught by the invariant

        # Flexibility ranking: what an adult can be pulled out of most easily.
        flexible = {
            "idle_at_home": 0, "tv_screens": 1, "reading": 2, "hobbies": 3,
            "social_at_home": 4, "cleaning": 5, "gardening": 6, "shopping": 7,
            "social_out": 8, "sport_exercise": 9, "religion_civic": 10,
            "work_at_home": 40, "childcare": 50, "adult_care": 50,
            "eating_main": 60, "cooking": 61, "sleep": 80,
            "work_at_workplace": 95, "school": 95, "travel_commute": 96,
        }

        def at(pid: str, minute: int) -> ActivityInterval | None:
            for iv in person_days[pid].intervals:
                if iv.start_min <= minute < iv.end_min:
                    return iv
            return None

        log: list[dict[str, Any]] = []
        minute = 0
        while minute < MINUTES_PER_DAY:
            kid_home = [
                k for k in kids
                if (iv := at(k.person_id, minute)) and iv.location_kind == "building"
            ]
            if not kid_home:
                minute += 1
                continue
            supervised = any(
                (iv := at(a.person_id, minute)) and iv.location_kind == "building"
                for a in adults
            )
            if supervised:
                minute += 1
                continue

            # Find how long the unsupervised run lasts, so one fix covers it.
            end = minute
            while end < MINUTES_PER_DAY:
                k_home = any(
                    (iv := at(k.person_id, end)) and iv.location_kind == "building"
                    for k in kids
                )
                a_home = any(
                    (iv := at(a.person_id, end)) and iv.location_kind == "building"
                    for a in adults
                )
                if not k_home or a_home:
                    break
                end += 1

            best: tuple[int, str] | None = None
            for a in adults:
                iv = at(a.person_id, minute)
                if iv is None:
                    continue
                cost = flexible.get(iv.activity, 30)
                if best is None or cost < best[0]:
                    best = (cost, a.person_id)
            if best is None:
                minute = end
                continue
            cost, pid = best
            # Replace that adult's activity over the run with childcare at home.
            replaced = self._replace_span(person_days[pid], minute, end, "childcare")
            log.append(
                {
                    "from_min": minute, "to_min": end,
                    "children": [k.person_id for k in kid_home],
                    "supervisor": pid, "displaced_cost": cost,
                    "applied": replaced,
                    "rule": "a child under 12 is never home alone (design 5.3)",
                }
            )
            minute = end
        return log

    @staticmethod
    def _replace_span(day: PersonDay, a: int, b: int, activity: str) -> bool:
        """Overwrite ``[a, b)`` of a person's day with ``activity`` at home."""
        spec = ACTIVITY_CODES.get(activity, {"zone": "living"})
        plan: list[str] = []
        trig: dict[int, str] = {}
        for iv in sorted(day.intervals, key=lambda i: i.start_min):
            for m in range(iv.start_min, iv.end_min):
                plan.append(iv.activity)
                trig[m] = iv.trigger
        if len(plan) != MINUTES_PER_DAY:
            return False
        for m in range(max(a, 0), min(b, MINUTES_PER_DAY)):
            plan[m] = activity
            trig[m] = "disruption"
        rebuilt: list[ActivityInterval] = []
        start = 0
        pid = day.person_id
        for m in range(1, MINUTES_PER_DAY + 1):
            if m == MINUTES_PER_DAY or plan[m] != plan[start]:
                act = plan[start]
                sp = ACTIVITY_CODES.get(act, {"zone": "living"})
                zone = str(sp["zone"])
                # The same mapping as the primary site, and it has to be the
                # same: this one rebuilds intervals after a joint plan, and a
                # person gardening before a negotiation but at a venue after
                # it would be two different people.
                kind = ("in_transit" if zone == "in_transit"
                        else "building" if act in OUTDOORS_BUT_AT_HOME
                        else "venue" if zone == "outside" else "building")
                rebuilt.append(
                    ActivityInterval(
                        person_id=pid, start_min=start, end_min=m, activity=act,
                        zone=zone, location_kind=kind,
                        trigger=trig.get(start, "routine"), deliberated=False,
                    )
                )
                start = m
        day.intervals = rebuilt
        return True
