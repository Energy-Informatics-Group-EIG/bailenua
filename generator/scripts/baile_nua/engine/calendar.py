"""The simulated calendar, S06 (design 5.10, E0-3 / U08, R20).

E0-3: the calendar runs 2022 to 2031 with Census 2022 as t0, and **E1 simulates
2022**.

E1 implements the calendar classes the one-year estate run needs, with the
Irish ones real rather than approximated:

* **public holidays** - Ireland's nine 2022 public holidays, including the
  one-off 18 March 2022 holiday, which is the kind of detail a generated
  calendar gets wrong and which moved load that week;
* **school terms** - the Irish school year, which is what makes a child's
  weekday differ in July from February;
* **DST transitions** - explicit events (design 3.2: "DST transitions are
  explicit events that shift human routines but not the UTC series");
* **storms** - named storms are taken from the weather realisation rather than
  invented, so a storm day coincides with the wind that caused it (design 6.5
  rule 2: "Storm days in the event engine coincide with the weather that causes
  them").

Everything else R20 lists - local events, faith calendars, cruise days, markets,
elections, roadworks - is week 2 (design 9.3's revision-3 table moves the full
event engine to WP6), and :data:`OUT_OF_SCOPE_AT_E1` names them so the E1
report can say what is missing rather than implying coverage.
"""

from __future__ import annotations

import csv
import functools
from pathlib import Path

import dataclasses
from typing import Any

import numpy as np
import pandas as pd

__all__ = [
    "IRISH_PUBLIC_HOLIDAYS_2022",
    "SCHOOL_TERMS_2022",
    "OUT_OF_SCOPE_AT_E1",
    "CalendarDay",
    "build_calendar",
    "storm_days_from_weather",
]

#: Ireland's public holidays in 2022.  Nine, not eight: 18 March 2022 was a
#: one-off holiday, and 1 February became the new St Brigid's Day holiday only
#: from 2023, so 2022 has the extra March date and not the February one.
#: Getting this wrong shifts a whole week's load pattern.
IRISH_PUBLIC_HOLIDAYS_2022: dict[str, str] = {
    "2022-01-01": "New Year's Day",
    "2022-03-17": "St Patrick's Day",
    "2022-03-18": "One-off public holiday (2022 only)",
    "2022-04-18": "Easter Monday",
    "2022-05-02": "May Day",
    "2022-06-06": "June Bank Holiday",
    "2022-08-01": "August Bank Holiday",
    "2022-10-31": "October Bank Holiday",
    "2022-12-25": "Christmas Day",
    "2022-12-26": "St Stephen's Day",
}

#: The Irish school year in 2022, as term intervals.  Primary and
#: post-primary differ by a few days at the edges; the common pattern is used
#: and the simplification is declared.
SCHOOL_TERMS_2022: tuple[tuple[str, str, str], ...] = (
    ("2022-01-05", "2022-02-18", "spring term, first half"),
    ("2022-02-28", "2022-04-08", "spring term, second half"),
    ("2022-04-19", "2022-06-24", "summer term"),
    ("2022-08-29", "2022-10-28", "autumn term, first half"),
    ("2022-11-07", "2022-12-21", "autumn term, second half"),
)

class CalendarSourceMissing(RuntimeError):
    """A sourced calendar table is absent.  There is deliberately no fallback."""


#: What R20 asks for that E1 does not implement, named so the report can say so.
OUT_OF_SCOPE_AT_E1: tuple[str, ...] = (
    "local event programmes (festivals, concerts, markets)",
    "faith and cultural calendars (Ramadan, Eid, Diwali, Orthodox Easter)",
    "cruise-ship days and tourism seasonality",
    "college terms as distinct from school terms",
    "elections, roadworks, transport disruption, infrastructure maintenance",
    "agricultural and sporting calendars",
    "compound event correlation beyond storm-and-weather",
    "event preparation, recovery and rebound phases",
    "spatial propagation of events across estates",
)


@dataclasses.dataclass
class CalendarDay:
    sim_day: int
    date: pd.Timestamp
    is_weekend: bool
    is_public_holiday: bool
    holiday_name: str | None
    is_school_day: bool
    #: Phase 2 / I-109. The February mid-term differs by SECTOR - primary closes
    #: the Thursday and Friday only, post-primary the whole week - so one flag
    #: cannot be right for both. ``is_school_day`` keeps its existing meaning of
    #: PRIMARY (D-130), which is the sector the school-age population mostly
    #: sits in, and both sectors are carried explicitly beside it.
    is_school_day_primary: bool
    is_school_day_post_primary: bool
    is_workday: bool
    season: str
    month: int
    is_dst: bool
    dst_transition: str | None
    is_storm_day: bool
    storm_detail: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        d = dataclasses.asdict(self)
        d["date"] = self.date.isoformat()
        return d


def _season(month: int) -> str:
    # Irish meteorological seasons, which start a month earlier than the
    # astronomical ones: spring is February to April.
    return {
        12: "winter", 1: "winter", 2: "spring", 3: "spring", 4: "spring",
        5: "summer", 6: "summer", 7: "summer", 8: "autumn", 9: "autumn",
        10: "autumn", 11: "winter",
    }[month]


# --------------------------------------------------------------------------- #
# Phase 2: per-year holidays and school breaks, from sourced tables
# --------------------------------------------------------------------------- #

#: The school-break table begins at school year 2014/15, so a date before that
#: year starts has NO break rows covering it and every weekday would read as a
#: school day - silently wrong rather than loudly absent. Requests earlier than
#: this are refused. The replay's warm-up begins 2014-12-01, inside coverage.
SCHOOL_COVERAGE_FROM = "2014-09-01"

#: Earliest and latest year the sourced tables cover.  The replay needs
#: December 2014 for its warm-up and ends 2026-09-30.
SOURCED_YEARS = (2014, 2026)

_HOLIDAYS_CSV = "sources/derived/irish_public_holidays_2014_2026.csv"
_BREAKS_CSV = "sources/derived/school_breaks.csv"


def _project_root() -> Path:
    """Reuse `sources.PROJECT_ROOT` rather than recompute a parent count.

    This module sits one level deeper than ``sources.py``, so copying its
    ``parents[2]`` here pointed at ``scripts/`` instead of the project root.
    Importing the one definition removes the chance of that drifting again.
    """
    from baile_nua.sources import PROJECT_ROOT
    return PROJECT_ROOT


@functools.lru_cache(maxsize=1)
def sourced_holidays() -> dict[pd.Timestamp, str]:
    """``{date -> name}`` for 2014-2026, from the derived table.

    Derived from the statutory rules and verified against three independent
    anchors - the sourced in-code 2022 table, the WRC's published 2026 list and
    ten published Easter Mondays.  See the table's own manifest.
    """
    path = _project_root() / _HOLIDAYS_CSV
    if not path.exists():
        raise CalendarSourceMissing(
            f"{_HOLIDAYS_CSV} is not on disk, so no year's holidays can be "
            f"built. This is a sourced table, not a fallback: there is no "
            f"silent default. Regenerate it or restore it from the snapshot."
        )
    out: dict[pd.Timestamp, str] = {}
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            out[pd.Timestamp(row["date"])] = row["name"]
    return out


@functools.lru_cache(maxsize=1)
def sourced_school_breaks() -> tuple[dict[str, Any], ...]:
    """The DoE standardisation circulars' breaks, per school year and sector."""
    path = _project_root() / _BREAKS_CSV
    if not path.exists():
        raise CalendarSourceMissing(
            f"{_BREAKS_CSV} is not on disk, so no year's school calendar can "
            f"be built. Extracted from DoE circulars 0016/2014, 0009/2017, "
            f"0005/2020 and 0072/2022; there is no fallback."
        )
    with path.open(newline="", encoding="utf-8") as fh:
        return tuple(dict(r) for r in csv.DictReader(fh))


def _closed_days(sector: str) -> set[pd.Timestamp]:
    """Every date on which ``sector`` is closed for a standardised break.

    The circulars use two different wordings and they mean different things.

    * Mid-terms are stated **inclusively**: "close *from* Monday 27th October
      *to* Friday 31st October inclusive". Both endpoints are shut.
    * Christmas, Easter and summer are stated as a **final day and a reopening
      day**: "close *on* Friday 19th December 2014, which will be the final day
      of the school term" and "re-open *on* Monday 5th January 2015". So the
      stated close date is the last day OPEN, and the reopening date is the
      first day open again - the break is the days strictly between them.

    Reading the second form as inclusive, which is the obvious mistake, loses a
    school day at the start of every Christmas, Easter and summer break.
    """
    INCLUSIVE = ("october_midterm", "february_midterm")
    shut: set[pd.Timestamp] = set()
    for row in sourced_school_breaks():
        if row["sector"] not in (sector, "both"):
            continue
        a = pd.Timestamp(row["start_or_close"])
        b = pd.Timestamp(row["end_or_reopen"])
        if row["break"] in INCLUSIVE:
            start, end = a, b
        else:
            start, end = a + pd.Timedelta(days=1), b - pd.Timedelta(days=1)
        if end >= start:
            shut.update(pd.date_range(start, end, freq="D"))
    return shut


def storm_days_from_weather(
    hourly: pd.DataFrame,
    *,
    gust_threshold_ms: float = 17.0,
    min_hours: int = 3,
) -> dict[str, dict[str, Any]]:
    """Identify storm days from the weather realisation itself.

    Design 6.5 rule 2: "Storm days in the event engine coincide with the
    weather that causes them."  So storms are **derived** from the wind in the
    realisation rather than drawn independently - which is the difference
    between a storm day and a day labelled "storm".

    17 m/s sustained is roughly Met Éireann's yellow wind-warning level; three
    hours of it distinguishes a storm from a gusty afternoon.
    """
    if "wind_speed_ms" not in hourly.columns:
        return {}
    w = pd.to_numeric(hourly["wind_speed_ms"], errors="coerce")
    over = w >= gust_threshold_ms
    by_day = over.groupby(hourly.index.date).sum()
    peak = w.groupby(hourly.index.date).max()
    out: dict[str, dict[str, Any]] = {}
    for day, hours in by_day.items():
        if hours >= min_hours:
            out[str(day)] = {
                "hours_above_threshold": int(hours),
                "peak_wind_ms": round(float(peak[day]), 2),
                "threshold_ms": gust_threshold_ms,
                "derived_from": "the weather realisation's own wind series",
            }
    return out


def build_calendar(
    year: int | None = None,
    *,
    weather_hourly: pd.DataFrame | None = None,
    start: str | pd.Timestamp | None = None,
    end: str | pd.Timestamp | None = None,
    sim_day_offset: int = 0,
) -> list[CalendarDay]:
    """Build a calendar for a whole year, or for an arbitrary date range.

    ``build_calendar(2022)`` still means exactly what it meant - a whole
    calendar year - so every existing call site keeps working.  Phase 2 adds
    two things it could not do before:

    * **any year from 2014 to 2026**, because the holidays and school breaks now
      come from sourced tables rather than from one hand-built year.  The old
      behaviour raised ``NotImplementedError`` for anything but 2022.
    * **an arbitrary date range** via ``start``/``end``, which is what the
      December-2014 warm-up and the truncated final year of the replay need.
      A range may cross a year boundary.

    ``sim_day_offset`` sets the ``sim_day`` of the first day.  The chained
    replay runs ``sim_day`` continuously from 0 across all 4,291 days, because
    the seed tree is keyed on it and restarting at zero would re-draw an
    earlier year's random numbers (D-110).

    ``weather_hourly`` is the site series; when given, storm days come from it,
    so no storm exists without the wind that caused it.
    """
    if (year is None) == (start is None):
        raise ValueError(
            "pass either year= for a whole calendar year, or start=/end= for a "
            "range - not both and not neither"
        )
    if year is not None:
        lo, hi = SOURCED_YEARS
        if not lo <= year <= hi:
            raise CalendarSourceMissing(
                f"no sourced calendar for {year}: the holiday and school-break "
                f"tables cover {lo} to {hi}. There is no fallback - a year "
                f"outside the tables would be an invented calendar."
            )
        first = pd.Timestamp(f"{year}-01-01")
        last = pd.Timestamp(f"{year}-12-31")
    else:
        first = pd.Timestamp(start)
        last = pd.Timestamp(end) if end is not None else first + pd.Timedelta(days=364)
        lo, hi = SOURCED_YEARS
        for y in range(int(first.year), int(last.year) + 1):
            if not lo <= y <= hi:
                raise CalendarSourceMissing(
                    f"the range {first.date()}..{last.date()} needs year {y}, "
                    f"and the sourced tables cover {lo} to {hi} only."
                )

    if first < pd.Timestamp(SCHOOL_COVERAGE_FROM):
        raise CalendarSourceMissing(
            f"{first.date()} is before {SCHOOL_COVERAGE_FROM}, and the school-"
            f"break table starts at school year 2014/15. Nothing covers the "
            f"earlier dates, so every weekday would read as a school day - "
            f"wrong, and silently so. Refused rather than guessed."
        )
    days = pd.date_range(first, last, freq="D")
    holidays = sourced_holidays()
    shut_primary = _closed_days("primary")
    shut_post = _closed_days("post_primary")
    storms = (storm_days_from_weather(weather_hourly)
              if weather_hourly is not None else {})

    # Summer time for Europe/Dublin, by UTC OFFSET rather than by dst().
    #
    # I-110. `dst()` is the wrong predicate for Ireland and returns True in
    # WINTER. Since the Standard Time (Amendment) Act 1971 Irish Standard Time
    # (UTC+1) is the STANDARD, and winter GMT is modelled in the IANA database
    # as a negative DST adjustment, so `bool(t.dst())` is non-zero from late
    # October to late March. The old code used it directly, so `is_dst` was
    # inverted and the two transition labels were swapped.
    #
    # The offset is unambiguous: +1 h is summer time, 0 h is winter. Evaluated
    # at 12:00 UTC rather than midnight so a transition lands on the Sunday it
    # actually happens on - at 00:00 UTC the spring change (01:00 UTC) has not
    # occurred yet, which put it a day late.
    noon = pd.DatetimeIndex(days + pd.Timedelta(hours=12)).tz_localize(
        "UTC").tz_convert("Europe/Dublin")
    dst = np.array([t.utcoffset() == pd.Timedelta(hours=1) for t in noon])

    out: list[CalendarDay] = []
    for i, d in enumerate(days):
        is_hol = d in holidays
        is_we = d.dayofweek >= 5
        transition = None
        if i > 0 and dst[i] != dst[i - 1]:
            # Into summer time is the clocks going forward.
            transition = "spring forward" if dst[i] else "fall back"
        # A school day is a weekday that is neither a public holiday nor inside
        # a standardised break for that sector.
        open_primary = bool(not is_we and not is_hol and d not in shut_primary)
        open_post = bool(not is_we and not is_hol and d not in shut_post)
        out.append(
            CalendarDay(
                sim_day=sim_day_offset + i,
                date=d,
                is_weekend=bool(is_we),
                is_public_holiday=bool(is_hol),
                holiday_name=holidays.get(d),
                is_school_day=open_primary,
                is_school_day_primary=open_primary,
                is_school_day_post_primary=open_post,
                is_workday=bool(not is_we and not is_hol),
                season=_season(int(d.month)),
                month=int(d.month),
                is_dst=bool(dst[i]),
                dst_transition=transition,
                is_storm_day=bool(storms.get(d.date()) is not None),
                storm_detail=storms.get(d.date()),
            )
        )
    return out


