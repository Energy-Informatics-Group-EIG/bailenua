"""WP6: the full event engine, S06 / D14 (design 5.10, R20, R21, K09).

:mod:`baile_nua.engine.calendar` implements what the E1 one-year run needed -
Irish public holidays, school terms, DST and storms taken from the weather -
and names the rest in ``OUT_OF_SCOPE_AT_E1``. This module closes that list.

D14 lists ten event kinds: holiday, school term, storm, outage, festival,
cruise day, market, sport, roadworks and DST. R20's acceptance test is an
**event coverage audit**: every listed class present *with a source*. So
:data:`EVENT_SOURCES` pairs each kind with either a declared source or an
``[A]`` flag carrying its search record, and :func:`coverage_audit` is the
test rather than a claim.

**Shared drivers, not independent draws.** Design 5.10 is explicit that
compound correlation comes from shared drivers. Storms and outages are not
two independent processes that happen to coincide: the storm *causes* the
outage. Cruise days and markets are not independent either - a market day is
scheduled onto a cruise call because that is when the visitors are there. So
every correlated pair in :data:`SHARED_DRIVERS` is generated from one driver,
and :func:`driver_audit` refuses an event that claims a driver it was not
generated from. K09's lesson is the reason: validating every *pair* of event
types is combinatorially hopeless, so the design validates by class and by
shared driver, which is only possible if the driver is recorded.

**Phases.** Each instance carries one of preparation, main, recovery or
rebound, because an event's load signature is not a step function: a storm has
a day of stocking up before it, the main event, and a recovery; a holiday has
a rebound as deferred laundry and shopping catch up. A phase is a separate D14
row with the same ``instance_id`` stem, so a detector can be scored on the
phase it actually found.

**What is NOT claimed.** The Cobh-specific calendar - which festival, which
market day, which GAA fixture - is not published as open data in any form
found. What IS published is the cruise calendar's *volume and seasonality*
(TBA10, TBA11), and Cobh is a cruise port, so the one event class that most
distinguishes this town from a generic Irish town is the one with a real
source. The rest are ``[A]`` with frequencies that are declared, bounded where
a bound exists, and labelled.
"""

from __future__ import annotations

import dataclasses
import json
from typing import Any, Iterable

import numpy as np
import pandas as pd

from baile_nua.rng import SeedTree, Stream
from baile_nua.sources import REGISTRY, require

__all__ = [
    "EVENT_KINDS",
    "STATE_KINDS",
    "EVENT_CLASSES",
    "EVENT_PHASES",
    "EVENT_FOOTPRINTS",
    "EventInstance",
    "EVENT_SOURCES",
    "EventSource",
    "SHARED_DRIVERS",
    "EVENT_SEARCH_RECORD",
    "PHASE_PLAN",
    "cruise_calls_cork",
    "cruise_month_shares",
    "chronic_absence_bound",
    "build_events",
    "coverage_audit",
    "driver_audit",
    "coincidence_report",
]

#: D14's ``event_kind`` vocabulary, verbatim from the schema note.
EVENT_KINDS: tuple[str, ...] = (
    "holiday", "school term", "storm", "outage", "festival", "cruise day",
    "market", "sport", "roadworks", "DST",
)

#: The schema enums these rows have to satisfy.
EVENT_CLASSES: tuple[str, ...] = ("predictable", "recurring", "irregular",
                                  "exceptional")
EVENT_PHASES: tuple[str, ...] = ("preparation", "main", "recovery", "rebound")
EVENT_FOOTPRINTS: tuple[str, ...] = ("home", "street", "estate", "town", "region")


@dataclasses.dataclass
class EventInstance:
    """One D14 row."""

    instance_id: str
    event_kind: str
    event_class: str
    phase: str
    start: pd.Timestamp
    end: pd.Timestamp
    footprint: str
    footprint_ids: list[str] | None
    attendance_prob: dict[str, float] | None
    shared_driver: str | None
    source_ref: str

    def as_row(self) -> dict[str, Any]:
        d = dataclasses.asdict(self)
        d["start"] = self.start.isoformat()
        d["end"] = self.end.isoformat()
        return d

    def covers(self, day: pd.Timestamp) -> bool:
        return self.start.normalize() <= day.normalize() <= self.end.normalize()


@dataclasses.dataclass(frozen=True)
class EventSource:
    """What backs one event kind: a declared source, or a labelled assumption."""

    kind: str
    source_key: str | None
    #: Free text for the D14 ``source_ref`` column.
    source_ref: str
    #: ``""`` when sourced; an ``A-xx`` flag id when assumed.
    assumption_flag: str = ""

    @property
    def sourced(self) -> bool:
        return self.source_key is not None or self.source_ref.startswith("legal:")


#: R20's audit table. A kind is covered when it names either a declared source
#: or an assumption flag; a kind with neither fails :func:`coverage_audit`.
EVENT_SOURCES: dict[str, EventSource] = {
    "holiday": EventSource(
        kind="holiday", source_key=None,
        source_ref=(
            "legal: Organisation of Working Time Act 1997 Schedule 2 as "
            "amended, plus the 2022 one-off public holiday. A public holiday "
            "is a legal fact rather than a statistic, so the source is the "
            "instrument that creates it and not a CSO table."
        ),
    ),
    "DST": EventSource(
        kind="DST", source_key=None,
        source_ref=(
            "legal: Directive 2000/84/EC - summer time begins on the last "
            "Sunday in March and ends on the last Sunday in October, which is "
            "a rule and so is COMPUTED here rather than transcribed."
        ),
    ),
    "school term": EventSource(
        kind="school term", source_key="cso.education.sca42_primary_absence_by_county",
        source_ref=(
            "Department of Education term circulars for the dates; SCA42 for "
            "the attendance bound. The DATES have no PxStat source: UA16 was "
            "fetched and discarded because its weekly series is 15 irregular "
            "enrolment snapshots, not an attendance series, so it cannot be "
            "differenced into a term calendar."
        ),
        assumption_flag="A-41",
    ),
    "storm": EventSource(
        kind="storm", source_key="met.eireann.historical_hourly",
        source_ref=(
            "Met Eireann's own hourly observations: a storm event is derived "
            "from the wind in the weather realisation, so the storm and the "
            "wind that caused it cannot disagree (design 6.5 rule 2)."
        ),
    ),
    "cruise day": EventSource(
        kind="cruise day", source_key="cso.tourism.tba10_cruise_visits_by_port",
        source_ref=(
            "TBA10 for the Port of Cork's annual calls and passenger volume, "
            "TBA11 for the month-of-arrival distribution. The one event class "
            "that most distinguishes Cobh from a generic Irish town, and it "
            "has a real source."
        ),
    ),
    "outage": EventSource(
        kind="outage", source_key=None,
        source_ref=(
            "[A] A-42: no PxStat table publishes electricity supply "
            "interruptions. Outages are generated FROM storms rather than "
            "independently, so their frequency inherits the storm frequency, "
            "which is sourced."
        ),
        assumption_flag="A-42",
    ),
    "festival": EventSource(
        kind="festival", source_key=None,
        source_ref="[A] A-43: zero PxStat tables for 'festival'.",
        assumption_flag="A-43",
    ),
    "market": EventSource(
        kind="market", source_key=None,
        source_ref=(
            "[A] A-43: no published market calendar. Market days are "
            "generated from the cruise driver where they coincide, so their "
            "timing inherits a sourced seasonality."
        ),
        assumption_flag="A-43",
    ),
    "sport": EventSource(
        kind="sport", source_key=None,
        source_ref=(
            "[A] A-43: 'sport' matches 115 tables, none of them a fixture "
            "list or an attendance series - the matches are road freight "
            "TRANSPORT and travel tables, which is a substring collision."
        ),
        assumption_flag="A-43",
    ),
    "roadworks": EventSource(
        kind="roadworks", source_key=None,
        source_ref="[A] A-43: zero PxStat tables for 'roadwork'.",
        assumption_flag="A-43",
    ),
}


#: ``(search term, tables returned, verdict)`` for the assumed event classes.
EVENT_SEARCH_RECORD: tuple[tuple[str, int, str], ...] = (
    (r"[Cc]ruise", 2,
     "TBA10 cruise ships and passenger visits by PORT (Cork is one of the "
     "eleven) and TBA11 the same by MONTH OF ARRIVAL. Both ADOPTED."),
    (r"[Ss]chool [Yy]ear|[Tt]erm dates", 4,
     "SCA42 and SCA31 are chronic-absence rates - the share of children "
     "absent TWENTY DAYS OR MORE in a year - which is not a daily absence "
     "rate. UA16 'Enrolments by week' turned out to be 15 irregular snapshot "
     "dates across several years, not a weekly series. So term DATES are not "
     "published as a statistic and SCA42 serves as a lower bound on absence."),
    (r"[Ff]estival", 0, "ZERO tables."),
    (r"roadwork", 0, "ZERO tables."),
    (r"electricity.*interrupt|[Mm]inutes [Ll]ost", 0,
     "ZERO tables. Supply reliability is published by the regulator and the "
     "network operator, not the statistics office - the same split that put "
     "the load profiles at ESB Networks rather than in PxStat (I-043)."),
    (r"[Ss]port", 115,
     "115 tables and not one of them is a fixture list or an attendance "
     "series: the matches are road freight TRANSPORT activity and travel "
     "tables, where 'sport' is a substring of 'transport'. A hit count is not "
     "evidence - this is the clearest case of it in the whole sweep."),
    (r"[Ee]lection", 41,
     "Constituency populations and survey tables broken down by voting "
     "status. No election-date calendar, and elections are not in D14's list "
     "in any case."),
    (r"[Oo]vernight stay|[Tt]ourism", 7,
     "Tourism expenditure and satellite accounts - money, not day counts. "
     "TBA10/TBA11 are the day counts."),
)


#: Design 5.10: compound correlation comes from SHARED DRIVERS. Each entry is
#: ``driver -> the kinds it generates``, and nothing in that list may be drawn
#: independently.
SHARED_DRIVERS: dict[str, tuple[str, ...]] = {
    # A storm causes outages, and it cancels outdoor sport. Drawing these
    # separately would put an outage on a calm day and a storm with the lights
    # on, and then any model that learned the real correlation would be
    # penalised for being right.
    "winter_storm": ("storm", "outage", "sport"),
    # A cruise call is why a market is scheduled and why a street festival is
    # programmed for that day. The driver carries the sourced seasonality.
    "cruise_call": ("cruise day", "market", "festival"),
    # The school calendar and the public-holiday calendar are both fixed by
    # the same institutional year, and roadworks are scheduled INTO school
    # holidays on purpose, which is why they coincide.
    "institutional_year": ("school term", "holiday", "roadworks"),
    # DST is its own driver: it moves human routines and nothing else.
    "clock_change": ("DST",),
}

#: Phases per kind: ``(preparation days before, recovery days after, rebound
#: days after that)``. Zero means the phase does not exist for that kind.
PHASE_PLAN: dict[str, tuple[int, int, int]] = {
    "holiday": (1, 0, 2),        # stock up before; laundry and shopping after
    "school term": (0, 0, 0),    # a term is a state, not an event with a tail
    "storm": (1, 2, 0),          # stock up, then clear up
    "outage": (0, 1, 1),         # no preparation: that is what makes it an outage
    "festival": (1, 1, 0),
    "cruise day": (0, 0, 0),     # the town's load changes on the day only
    "market": (0, 0, 0),
    "sport": (0, 0, 1),          # the rebound is the catch-up after a fixture
    "roadworks": (0, 0, 0),      # a state for its duration
    "DST": (0, 1, 0),            # the week after a clock change is the recovery
}

#: Kinds that are a STATE rather than an occurrence. A school term runs for
#: six weeks and roadworks for a fortnight, so they overlap almost everything
#: by construction; counting that as a coincidence makes the coincidence
#: report say nothing. The first version did exactly that: 46 of 91 multi-kind
#: days were "school term plus a sport fixture", which is not a coincidence,
#: it is a Saturday in term time.
STATE_KINDS: frozenset[str] = frozenset({"school term", "roadworks"})

#: Which class each kind belongs to, against the schema enum.
KIND_CLASS: dict[str, str] = {
    "holiday": "predictable",
    "school term": "predictable",
    "DST": "predictable",
    "cruise day": "recurring",
    "market": "recurring",
    "sport": "recurring",
    "festival": "recurring",
    "storm": "irregular",
    "roadworks": "irregular",
    "outage": "exceptional",
}

#: Which footprint each kind has.
KIND_FOOTPRINT: dict[str, str] = {
    "holiday": "region",
    "school term": "region",
    "DST": "region",
    "storm": "region",
    "cruise day": "town",
    "festival": "town",
    "market": "town",
    "sport": "town",
    "roadworks": "street",
    "outage": "estate",
}


# --------------------------------------------------------------------------- #
# the sourced quantities
# --------------------------------------------------------------------------- #

class EventSourceError(RuntimeError):
    pass


def _cube(key: str) -> tuple[dict[str, list[str]], Any]:
    doc = json.loads(require(key).read_text(encoding="utf-8"))
    ids, size = doc["id"], doc["size"]
    labs = {
        i: list(doc["dimension"][i]["category"]["label"].values()) for i in ids
    }
    val = doc["value"]

    def get(**sel: str) -> float | None:
        off = 0
        for i, n in zip(ids, size):
            off = off * n + labs[i].index(sel[i])
        v = val[off] if isinstance(val, list) else val.get(str(off))
        return None if v is None else float(v)

    return labs, get


def cruise_calls_cork(year: int | None = None) -> dict[str, Any]:
    """TBA10: the Port of Cork's cruise calls and passengers.

    If the requested year is not published the nearest published year is used
    and the substitution is RETURNED rather than hidden, because 2020 and 2021
    are absent from the table and a silent fallback would make a pandemic year
    look like a normal one.
    """
    labs, get = _cube("cso.tourism.tba10_cruise_visits_by_port")
    years = [int(y) for y in labs["TLIST(A1)"]]
    want = year if year is not None else years[-1]
    used = want if want in years else min(years, key=lambda y: abs(y - want))
    calls = get(C01855V02284="Cork", **{"TLIST(A1)": str(used)},
                STATISTIC="Cruise Ships Visits to Irish Ports")
    pax = get(C01855V02284="Cork", **{"TLIST(A1)": str(used)},
              STATISTIC="Passenger Visits to Irish Ports")
    if not calls:
        raise EventSourceError(f"TBA10 has no Cork cruise calls for {used}")
    return {
        "year_requested": want,
        "year_used": used,
        "substituted": used != want,
        "calls": int(calls),
        "passengers": int(pax) if pax else None,
        "passengers_per_call": (pax / calls) if pax else None,
        "published_years": years,
    }


def cruise_month_shares(year: int | None = None) -> dict[int, float]:
    """TBA11: the month-of-arrival distribution, as shares summing to 1."""
    labs, get = _cube("cso.tourism.tba11_cruise_visits_by_month")
    years = [int(y) for y in labs["TLIST(A1)"]]
    used = year if (year is not None and year in years) else years[-1]
    months = [m for m in labs["C01885V02316"] if m != "All months"]
    raw: dict[int, float] = {}
    for i, m in enumerate(months, start=1):
        v = get(C01885V02316=m, **{"TLIST(A1)": str(used)},
                STATISTIC="Cruise Ships Visits to Irish Ports")
        raw[i] = float(v or 0.0)
    total = sum(raw.values())
    if total <= 0:
        raise EventSourceError(f"TBA11 has no monthly cruise calls for {used}")
    return {m: v / total for m, v in raw.items()}


def chronic_absence_bound(county: str = "Cork") -> dict[str, Any]:
    """SCA42: the share of primary children absent 20+ days in the year.

    A BOUND, not a rate: this is chronic absence over a whole school year, so
    it says a daily absence rate cannot be negligible, and nothing more.
    """
    labs, get = _cube("cso.education.sca42_primary_absence_by_county")
    years = labs["TLIST(A1)"]
    stat = labs["STATISTIC"][0]
    for y in reversed(years):
        v = get(STATISTIC=stat, **{"TLIST(A1)": y}, C02451V02968=county,
                C03549V04284="All schools", C03550V04285="Schools - All areas")
        if v is not None:
            return {
                "county": county, "year": int(y),
                "pct_absent_20_days_or_more": v,
                "construct": (
                    "the share of children absent for TWENTY DAYS OR MORE in "
                    "the school year - chronic absence, not a daily rate"
                ),
            }
    raise EventSourceError(f"SCA42 has no figure for {county}")


# --------------------------------------------------------------------------- #
# the assumed frequencies, each labelled and bounded where a bound exists
# --------------------------------------------------------------------------- #

#: ``[A]`` A-42 / A-43. These are not fitted to anything and are not tuned
#: against model output; they are round numbers chosen for transparency, and
#: each one says what constrains it.
ASSUMED_EVENT_RATES: dict[str, dict[str, Any]] = {
    "outage_per_storm": {
        "value": 0.25, "flag": "A-42",
        "note": (
            "a quarter of storm days produce a local outage. Inherits the "
            "storm frequency, which comes from the weather, so the only "
            "assumed quantity is the conditional probability - not the rate"
        ),
    },
    "outage_hours": {
        "value": (1, 6), "flag": "A-42",
        "note": "duration range in hours; no published Irish distribution found",
    },
    "market_per_cruise_call": {
        "value": 0.45, "flag": "A-43",
        "note": (
            "a market is scheduled onto a cruise call about half the time. "
            "Inherits TBA11's sourced seasonality through the driver"
        ),
    },
    "festival_days_per_year": {
        "value": 6, "flag": "A-43",
        "note": (
            "six festival days a year, placed on cruise calls where possible "
            "so that the correlation is the shared driver's and not invented"
        ),
    },
    "sport_fixtures_per_year": {
        "value": 34, "flag": "A-43",
        "note": (
            "roughly weekly through the GAA and soccer seasons. 'sport' "
            "matches 115 PxStat tables and none is a fixture list"
        ),
    },
    "roadworks_spells_per_year": {
        "value": 3, "flag": "A-43",
        "note": "three spells a year, scheduled into school holidays",
    },
    "roadworks_days": {
        "value": (3, 14), "flag": "A-43",
        "note": (
            "spell length in days. No published distribution: roadworks "
            "returns zero PxStat tables, and the local-authority schedules "
            "that would carry it are not open data"
        ),
    },
    "school_day_absence": {
        "value": 0.07, "flag": "A-41",
        "note": (
            "daily absence probability on a school day. BOUNDED BELOW by "
            "SCA42: 21.8 per cent of Cork primary children miss 20 or more "
            "days of a roughly 183-day year, so a daily rate of 0.218 * "
            "20 / 183 = 0.024 is the floor from chronic absence alone, before "
            "any short absence. 0.07 sits above that floor"
        ),
    },
}


def school_absence_floor() -> float:
    """The floor SCA42 puts under the daily absence rate.

    Derived rather than declared: if 21.8 per cent of children miss at least
    20 days of a 183-day school year, those children alone contribute
    0.218 x 20 / 183 to the daily absence rate. Short absences are on top, so
    this is a floor.
    """
    b = chronic_absence_bound()
    return (b["pct_absent_20_days_or_more"] / 100.0) * 20.0 / 183.0


# --------------------------------------------------------------------------- #
# generation
# --------------------------------------------------------------------------- #

def _dst_transitions(year: int) -> list[tuple[pd.Timestamp, str]]:
    """Computed from Directive 2000/84/EC, not transcribed.

    Summer time begins on the last Sunday in March and ends on the last
    Sunday in October. A rule can be computed, and computing it means the
    calendar is right for every year rather than for the year someone typed.
    """
    out = []
    for month, name in ((3, "summer time begins"), (10, "summer time ends")):
        days = pd.date_range(f"{year}-{month:02d}-01", periods=31, freq="D")
        sundays = [d for d in days if d.month == month and d.dayofweek == 6]
        out.append((sundays[-1], name))
    return out


def _phase_rows(
    *, stem: str, kind: str, start: pd.Timestamp, end: pd.Timestamp,
    footprint: str, footprint_ids: list[str] | None,
    attendance: dict[str, float] | None, driver: str, source_ref: str,
) -> list[EventInstance]:
    """Expand one event into its phase rows (design 5.10)."""
    prep, recov, rebound = PHASE_PLAN[kind]
    rows = [EventInstance(
        instance_id=f"{stem}-main", event_kind=kind, event_class=KIND_CLASS[kind],
        phase="main", start=start, end=end, footprint=footprint,
        footprint_ids=footprint_ids, attendance_prob=attendance,
        shared_driver=driver, source_ref=source_ref,
    )]
    if prep:
        rows.append(EventInstance(
            instance_id=f"{stem}-prep", event_kind=kind,
            event_class=KIND_CLASS[kind], phase="preparation",
            start=start - pd.Timedelta(days=prep),
            end=start - pd.Timedelta(days=1),
            footprint=footprint, footprint_ids=footprint_ids,
            attendance_prob=attendance, shared_driver=driver,
            source_ref=source_ref,
        ))
    if recov:
        rows.append(EventInstance(
            instance_id=f"{stem}-recov", event_kind=kind,
            event_class=KIND_CLASS[kind], phase="recovery",
            start=end + pd.Timedelta(days=1),
            end=end + pd.Timedelta(days=recov),
            footprint=footprint, footprint_ids=footprint_ids,
            attendance_prob=attendance, shared_driver=driver,
            source_ref=source_ref,
        ))
    if rebound:
        off = recov + 1
        rows.append(EventInstance(
            instance_id=f"{stem}-rebound", event_kind=kind,
            event_class=KIND_CLASS[kind], phase="rebound",
            start=end + pd.Timedelta(days=off),
            end=end + pd.Timedelta(days=off + rebound - 1),
            footprint=footprint, footprint_ids=footprint_ids,
            attendance_prob=attendance, shared_driver=driver,
            source_ref=source_ref,
        ))
    return rows


def build_events(
    *,
    year: int,
    master_seed: int,
    storm_days: Iterable[pd.Timestamp] = (),
    estate_ids: tuple[str, ...] = ("E-001",),
    street_ids: tuple[str, ...] = ("S-001",),
) -> list[EventInstance]:
    """Every D14 event instance for one year, generated from shared drivers.

    ``storm_days`` comes from the weather realisation, so the storm events and
    the wind that caused them are the same thing rather than two agreeing
    draws (design 6.5 rule 2).
    """
    from baile_nua.engine.calendar import (
        IRISH_PUBLIC_HOLIDAYS_2022,
        SCHOOL_TERMS_2022,
    )

    gen = SeedTree(master_seed).generator(
        Stream.LIFE_COURSE, entity="wp6_events", sim_day=year,
    )
    rows: list[EventInstance] = []
    src = EVENT_SOURCES

    # ---- driver: clock_change -------------------------------------------
    for ts, name in _dst_transitions(year):
        rows += _phase_rows(
            stem=f"EV-{year}-DST-{ts.strftime('%m%d')}", kind="DST",
            start=ts, end=ts, footprint=KIND_FOOTPRINT["DST"],
            footprint_ids=None,
            attendance=None, driver="clock_change",
            source_ref=src["DST"].source_ref + f" ({name})",
        )

    # ---- driver: institutional_year --------------------------------------
    # Holidays and school terms are both set by the institutional year, and
    # roadworks are scheduled INTO the school holidays, which is why they
    # coincide. Generating roadworks independently would decouple them.
    holidays = (
        IRISH_PUBLIC_HOLIDAYS_2022 if year == 2022
        else {}
    )
    for date, label in sorted(holidays.items()):
        ts = pd.Timestamp(date)
        rows += _phase_rows(
            stem=f"EV-{year}-HOL-{ts.strftime('%m%d')}", kind="holiday",
            start=ts, end=ts, footprint=KIND_FOOTPRINT["holiday"],
            footprint_ids=None,
            attendance={"all": 1.0}, driver="institutional_year",
            source_ref=src["holiday"].source_ref + f" ({label})",
        )

    term_spans: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    if year == 2022:
        absence = float(ASSUMED_EVENT_RATES["school_day_absence"]["value"])
        for a, b, label in SCHOOL_TERMS_2022:
            sa, sb = pd.Timestamp(a), pd.Timestamp(b)
            term_spans.append((sa, sb))
            rows += _phase_rows(
                stem=f"EV-{year}-TERM-{sa.strftime('%m%d')}",
                kind="school term", start=sa, end=sb,
                footprint=KIND_FOOTPRINT["school term"], footprint_ids=None,
                attendance={"child": 1.0 - absence},
                driver="institutional_year",
                source_ref=src["school term"].source_ref + f" ({label})",
            )

    # Roadworks in the school holidays: the gaps between term spans.
    gaps: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    for (_, a_end), (b_start, _) in zip(term_spans, term_spans[1:]):
        if (b_start - a_end).days > 4:
            gaps.append((a_end + pd.Timedelta(days=1),
                         b_start - pd.Timedelta(days=1)))
    n_rw = int(ASSUMED_EVENT_RATES["roadworks_spells_per_year"]["value"])
    lo_d, hi_d = ASSUMED_EVENT_RATES["roadworks_days"]["value"]
    for i in range(n_rw):
        if gaps:
            g = gaps[int(gen.integers(0, len(gaps)))]
            span = max((g[1] - g[0]).days, 1)
            start = g[0] + pd.Timedelta(days=int(gen.integers(0, span)))
        else:
            start = pd.Timestamp(f"{year}-01-01") + pd.Timedelta(
                days=int(gen.integers(0, 365))
            )
        dur = int(gen.integers(lo_d, hi_d + 1))
        rows += _phase_rows(
            stem=f"EV-{year}-RW-{i:02d}", kind="roadworks",
            start=start, end=start + pd.Timedelta(days=dur - 1),
            footprint=KIND_FOOTPRINT["roadworks"],
            footprint_ids=[street_ids[int(gen.integers(0, len(street_ids)))]],
            attendance=None, driver="institutional_year",
            source_ref=src["roadworks"].source_ref,
        )

    # ---- driver: winter_storm -------------------------------------------
    storms = sorted(pd.Timestamp(d).normalize() for d in storm_days)
    p_outage = float(ASSUMED_EVENT_RATES["outage_per_storm"]["value"])
    lo_h, hi_h = ASSUMED_EVENT_RATES["outage_hours"]["value"]
    for i, ts in enumerate(storms):
        rows += _phase_rows(
            stem=f"EV-{year}-STORM-{ts.strftime('%m%d')}", kind="storm",
            start=ts, end=ts, footprint=KIND_FOOTPRINT["storm"],
            footprint_ids=None, attendance=None, driver="winter_storm",
            source_ref=src["storm"].source_ref,
        )
        if gen.random() < p_outage:
            hours = int(gen.integers(lo_h, hi_h + 1))
            start = ts + pd.Timedelta(hours=int(gen.integers(0, 24 - hours)))
            rows += _phase_rows(
                stem=f"EV-{year}-OUT-{ts.strftime('%m%d')}", kind="outage",
                start=start, end=start + pd.Timedelta(hours=hours),
                footprint=KIND_FOOTPRINT["outage"],
                footprint_ids=[estate_ids[int(gen.integers(0, len(estate_ids)))]],
                attendance=None, driver="winter_storm",
                source_ref=src["outage"].source_ref,
            )

    # Sport: fixtures through the season, and a storm day cancels the fixture.
    n_sport = int(ASSUMED_EVENT_RATES["sport_fixtures_per_year"]["value"])
    storm_set = set(storms)
    placed = 0
    week = 0
    while placed < n_sport and week < 52:
        ts = (pd.Timestamp(f"{year}-01-01")
              + pd.Timedelta(days=week * 7 + int(gen.integers(5, 7))))
        week += 1
        if ts.year != year:
            continue
        if ts.normalize() in storm_set:
            continue              # cancelled by the shared driver, not by a draw
        rows += _phase_rows(
            stem=f"EV-{year}-SPORT-{placed:02d}", kind="sport",
            start=ts, end=ts, footprint=KIND_FOOTPRINT["sport"],
            footprint_ids=None,
            attendance={"adult": 0.12, "child": 0.18},
            driver="winter_storm", source_ref=src["sport"].source_ref,
        )
        placed += 1

    # ---- driver: cruise_call --------------------------------------------
    calls = cruise_calls_cork(year)
    shares = cruise_month_shares(year)
    pax_per_call = calls["passengers_per_call"] or 0.0
    months = [m for m, s in shares.items() if s > 0]
    weights = np.array([shares[m] for m in months], dtype=float)
    weights = weights / weights.sum()
    p_market = float(ASSUMED_EVENT_RATES["market_per_cruise_call"]["value"])
    n_fest = int(ASSUMED_EVENT_RATES["festival_days_per_year"]["value"])
    cruise_days: list[pd.Timestamp] = []
    for i in range(calls["calls"]):
        m = int(months[int(gen.choice(len(months), p=weights))])
        dim = pd.Period(f"{year}-{m:02d}").days_in_month
        ts = pd.Timestamp(f"{year}-{m:02d}-{int(gen.integers(1, dim + 1)):02d}")
        cruise_days.append(ts)
        rows += _phase_rows(
            stem=f"EV-{year}-CRUISE-{i:03d}", kind="cruise day",
            start=ts, end=ts, footprint=KIND_FOOTPRINT["cruise day"],
            footprint_ids=None,
            attendance={"visitors": pax_per_call},
            driver="cruise_call", source_ref=src["cruise day"].source_ref,
        )
        if gen.random() < p_market:
            rows += _phase_rows(
                stem=f"EV-{year}-MKT-{i:03d}", kind="market",
                start=ts, end=ts, footprint=KIND_FOOTPRINT["market"],
                footprint_ids=None, attendance={"adult": 0.25},
                driver="cruise_call", source_ref=src["market"].source_ref,
            )
    for i, ts in enumerate(sorted(cruise_days)[:n_fest]):
        rows += _phase_rows(
            stem=f"EV-{year}-FEST-{i:02d}", kind="festival",
            start=ts, end=ts, footprint=KIND_FOOTPRINT["festival"],
            footprint_ids=None, attendance={"adult": 0.30, "child": 0.35},
            driver="cruise_call", source_ref=src["festival"].source_ref,
        )

    rows.sort(key=lambda r: (r.start, r.instance_id))
    return rows


# --------------------------------------------------------------------------- #
# the audits: R20, K09, R21
# --------------------------------------------------------------------------- #

def coverage_audit(events: Iterable[EventInstance]) -> dict[str, Any]:
    """R20: every listed class present, with a source.

    Two failures are possible and they are different. A kind can be *absent*
    from the generated year, which means the engine does not produce it at
    all. Or it can be present with no source behind it, which is the failure
    R20 actually names - a class that looks covered because rows exist.
    """
    present: dict[str, int] = {}
    for e in events:
        present[e.event_kind] = present.get(e.event_kind, 0) + 1
    rows = []
    for kind in EVENT_KINDS:
        s = EVENT_SOURCES.get(kind)
        rows.append({
            "event_kind": kind,
            "instances": present.get(kind, 0),
            "present": present.get(kind, 0) > 0,
            "source_key": None if s is None else s.source_key,
            "assumption_flag": "" if s is None else s.assumption_flag,
            "has_source_or_flag": bool(
                s is not None and (s.source_key or s.assumption_flag
                                   or s.source_ref.startswith("legal:"))
            ),
            "source_ref": "" if s is None else s.source_ref,
        })
    missing = [r["event_kind"] for r in rows if not r["present"]]
    unsourced = [r["event_kind"] for r in rows if not r["has_source_or_flag"]]
    return {
        "rows": rows,
        "n_kinds": len(EVENT_KINDS),
        "missing_from_the_year": missing,
        "present_but_unsourced": unsourced,
        "passes_r20": not missing and not unsourced,
        "n_sourced": sum(1 for r in rows if r["source_key"]),
        "n_assumed": sum(1 for r in rows if r["assumption_flag"]),
        "n_legal": sum(
            1 for r in rows if r["source_ref"].startswith("legal:")
        ),
    }


def driver_audit(events: Iterable[EventInstance]) -> dict[str, Any]:
    """K09: every event names a driver, and the driver really generates it.

    An event whose ``shared_driver`` does not list its kind would be a claimed
    correlation that the generator did not actually produce - exactly the
    thing design 5.10 warns against, and invisible without this check.
    """
    bad: list[str] = []
    counts: dict[str, int] = {}
    for e in events:
        if not e.shared_driver:
            bad.append(f"{e.instance_id}: no shared_driver")
            continue
        kinds = SHARED_DRIVERS.get(e.shared_driver)
        if kinds is None:
            bad.append(f"{e.instance_id}: unknown driver {e.shared_driver!r}")
        elif e.event_kind not in kinds:
            bad.append(
                f"{e.instance_id}: driver {e.shared_driver!r} does not "
                f"generate {e.event_kind!r}"
            )
        counts[e.shared_driver] = counts.get(e.shared_driver, 0) + 1
    return {
        "by_driver": counts,
        "violations": bad,
        "clean": not bad,
        "n_drivers": len(SHARED_DRIVERS),
    }


def coincidence_report(events: Iterable[EventInstance]) -> dict[str, Any]:
    """R21's coincidence half: which kinds land on the same day, and why.

    Reported by shared driver rather than as a pairwise matrix, because K09
    says a pairwise matrix over ten kinds is not validatable. What matters is
    whether a coincidence is EXPLAINED - produced by a driver both kinds
    belong to - or unexplained.

    :data:`STATE_KINDS` are excluded from the coincidence count and reported
    as background context instead. A six-week school term overlaps every
    fixture and every cruise call in it; calling that a coincidence buries the
    ones that mean something.
    """
    by_day: dict[pd.Timestamp, set[str]] = {}
    drivers_by_day: dict[pd.Timestamp, set[str]] = {}
    state_days: dict[pd.Timestamp, set[str]] = {}
    for e in events:
        if e.phase != "main":
            continue
        span = pd.date_range(e.start.normalize(), e.end.normalize(), freq="D")
        target = state_days if e.event_kind in STATE_KINDS else by_day
        for d in span:
            target.setdefault(d, set()).add(e.event_kind)
            if e.shared_driver and e.event_kind not in STATE_KINDS:
                drivers_by_day.setdefault(d, set()).add(e.shared_driver)
    explained = unexplained = 0
    examples: list[dict[str, Any]] = []
    for d, kinds in sorted(by_day.items()):
        if len(kinds) < 2:
            continue
        drv = drivers_by_day.get(d, set())
        shared = [
            k for k in SHARED_DRIVERS
            if k in drv and len(kinds & set(SHARED_DRIVERS[k])) >= 2
        ]
        if shared:
            explained += 1
        else:
            unexplained += 1
            if len(examples) < 8:
                examples.append({
                    "date": d.date().isoformat(),
                    "kinds": sorted(kinds), "drivers": sorted(drv),
                    "state_context": sorted(state_days.get(d, set())),
                })
    total = explained + unexplained
    return {
        "days_with_two_or_more_event_kinds": total,
        "explained_by_a_shared_driver": explained,
        "unexplained_coincidences": unexplained,
        "explained_share": (explained / total) if total else None,
        "unexplained_examples": examples,
        "state_kinds_excluded": sorted(STATE_KINDS),
        "state_day_counts": {
            k: sum(1 for v in state_days.values() if k in v)
            for k in sorted(STATE_KINDS)
        },
        "note": (
            "An unexplained coincidence is not a bug: two independent drivers "
            "can land on one day by chance, and a calendar in which they "
            "never did would be wrong. What would be a bug is a coincidence "
            "the generator produced deliberately without recording the "
            "driver, and driver_audit catches that."
        ),
    }
