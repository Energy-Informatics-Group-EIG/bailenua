"""I-111: D15's `is_dst` must agree with the calendar, and with daylight.

I-110 fixed the inversion in `CalendarDay.is_dst` and recorded its blast radius
as the calendar and the D14 `DST` event kind. It missed that the weather layer
builds the same flag by a second route. `tzdata` models Europe/Dublin the way
Irish law describes it, IST standard with a negative correction in winter, so
`t.dst()` is -1 h in January and `bool(-3600.0)` is True - which labelled every
winter minute as summer time in a `required: true` column of a shipped
observable.

These tests pin the convention in both places at once, so the next person to
change one is told about the other.
"""
from __future__ import annotations

import pandas as pd
import pytest

import baile_nua.sources_registry  # noqa: F401  - populates REGISTRY
from baile_nua.engine.calendar import build_calendar
from baile_nua.weather.site import build_realisation

SEED = 20251010
ONE_HOUR = pd.Timedelta(hours=1)


def _is_dst_frame(year: int) -> pd.DataFrame:
    real = build_realisation(year=year, master_seed=SEED,
                             minute_resolution=False, days=None)
    df = real.site_hourly[["is_dst"]].copy()
    df["month"] = df.index.month
    return df


@pytest.mark.parametrize("year", [2015, 2022])
def test_summer_is_dst_and_winter_is_not(year: int) -> None:
    """January is winter and July is summer. The old code said the reverse."""
    df = _is_dst_frame(year)
    assert df.loc[df["month"] == 1, "is_dst"].mean() == 0.0
    assert df.loc[df["month"] == 7, "is_dst"].mean() == 1.0


@pytest.mark.parametrize("year", [2015, 2022])
def test_d15_agrees_with_the_calendar_day_by_day(year: int) -> None:
    """The two routes to the same flag must not disagree on any day."""
    df = _is_dst_frame(year)
    by_day = df.groupby(df.index.tz_convert("Europe/Dublin").date)["is_dst"]
    # `CalendarDay.date` is a pandas Timestamp and the groupby keys are
    # `datetime.date`, so normalise - keying on the Timestamp matched nothing
    # and the comparison passed vacuously on code known to be wrong.
    cal = {d.date.date(): d.is_dst for d in build_calendar(year)}
    # A transition day is half one and half the other in the hourly series, so
    # compare the day's majority against the calendar's single verdict.
    compared = [(day, series) for day, series in by_day if day in cal]
    assert len(compared) > 350, (
        f"only {len(compared)} days lined up against the calendar; the keys "
        f"are not comparable and this assertion would pass vacuously")
    disagree = [str(day) for day, series in compared
                if bool(series.mean() >= 0.5) != cal[day]]
    assert disagree == [], f"D15 and the calendar disagree on {disagree[:5]}"


def test_the_flag_is_never_taken_from_tzdata_dst() -> None:
    """The construct that caused I-111, asserted to be absent.

    Kept as a test rather than a comment because the inversion is invisible in
    output unless you look at the right month: a reviewer reading
    `bool(t.dst().total_seconds())` has no reason to suspect it.
    """
    import inspect

    from baile_nua.weather import site as site_mod

    code = "\n".join(
        line.split("#", 1)[0] for line in inspect.getsource(site_mod).splitlines())
    assert ".dst()" not in code, (
        "`dst()` is -1 h in an Irish winter and truthy; decide summer time by "
        "the UTC offset instead (I-111)")


def test_tzdata_still_behaves_the_way_the_issue_describes() -> None:
    """If this ever fails, tzdata changed and I-111's reasoning needs re-reading."""
    jan = pd.Timestamp("2022-01-15 12:00").tz_localize("Europe/Dublin")
    jul = pd.Timestamp("2022-07-15 12:00").tz_localize("Europe/Dublin")
    assert jan.dst() == -ONE_HOUR and jan.utcoffset() == pd.Timedelta(0)
    assert jul.dst() == pd.Timedelta(0) and jul.utcoffset() == ONE_HOUR
