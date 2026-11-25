"""ESB Networks Standard Load Profile LP1, as a peak and load-factor reference.

This is I-039's answer, and U30 is why it is here rather than in PxStat: the
sweep searched the whole 13,086-table CSO catalogue for `peak demand`, `peak
load`, `maximum demand`, `load factor`, `ADMD` and `after diversity` and found
**zero** hits (I-043). The quantity is published, by the network operator.

LP1, "Urban Domestic 24 Hour", is a settlement profile for the Irish retail
market: a Demand Energy Coefficient for every quarter-hour of the year,
unitised so the year sums to 1.0. That unitisation is what makes it usable
here - the load factor falls straight out of it with no denominator borrowed
from another source and no assumption at all:

    load factor = mean coefficient / peak coefficient

Measured from the 2022 file: **load factor 0.4129**, annual peak quarter-hour
**2.422x** the annual mean, mean-day peak at **18:00** (1.63x the daily mean)
and trough at **04:00** (0.45x).

Three things about it have to be stated plainly, because each one bounds what
the check built on it may claim.

**It is after-diversity.** LP1 is the aggregate of the whole urban domestic
class, not a dwelling. A single household's load factor is far lower - its
peak is a kettle and a shower coinciding - and no public Irish source gives
it, because that needs smart-meter or sub-metered microdata, which in Ireland
means CER/ISSDA and the brief forbids it. After-diversity is the right
instrument for feeder loading (S11) and the wrong one for one house.

**Diversity grows with the number of customers aggregated.** LP1 aggregates
roughly two million meters; Baile Nua has about 1,100 and the E1 slice has 50.
A smaller aggregate is spikier, so its load factor is legitimately lower.
LP1 therefore bounds a small aggregate from ABOVE only, and
:data:`MIN_HOMES_FOR_A_LOWER_BOUND` is where the lower bound starts to apply.

**Resolution matters in the same direction.** A peak measured over one minute
is at least as high as one measured over fifteen, so a 1-minute load factor is
a lower bound on the quarter-hourly one. The check reads D19's 15-minute
intervals rather than D18's 1-minute channels precisely so the comparison is
resolution-matched - and because 15-minute views are what U28 keeps for every
home, so this check keeps working on the ten-year town package.

The annual peak is not used as a timing test, for a reason worth recording:
LP1 2022's annual peak quarter-hour is **2022-12-27 at 13:45**, a Christmas-
week midday cooking peak rather than the usual evening one. A naive "the peak
must fall between 16:00 and 21:00" test would have been written, and would have
been wrong about the reference. The mean diurnal shape is stable where the
annual maximum is not.
"""

from __future__ import annotations

import datetime
import functools
from collections import defaultdict
from typing import Any

from baile_nua.sources import require

__all__ = [
    "SLP_KEY",
    "DOMESTIC_SHEET",
    "LOAD_FACTOR_UPPER_ALLOWANCE",
    "LOAD_FACTOR_LOWER_ALLOWANCE",
    "MIN_HOMES_FOR_A_LOWER_BOUND",
    "PEAK_HOUR_TOLERANCE",
    "MIN_OVERNIGHT_TAPER",
    "OVERNIGHT_HOURS",
    "OVERNIGHT_SHAPE_HALVING",
    "overnight_shape_band",
    "overnight_shape_mad",
    "lp1_reference",
]

SLP_KEY = "esbn.rmds.slp_indexes_2022"

#: LP1 is urban domestic. Cobh is a town of about 14,000, so urban is the
#: right class; LP3 is the rural equivalent and LP2/LP4 are the night-saver
#: variants, whose overnight storage-heating load puts their load factor near
#: 0.60 and which would flatter any model compared against them.
DOMESTIC_SHEET = "LP1"

#: How far above the reference load factor a package may sit. Small, because
#: both the diversity and the resolution arguments push the measured value
#: DOWN: a town of 1,100 is spikier than two million meters, and a shorter
#: measurement interval cannot lower a peak. Exceeding the national class is
#: therefore not a tolerance question but a sign that load has been spread too
#: evenly - which is also one of the tells 7.9 audits for.
LOAD_FACTOR_UPPER_ALLOWANCE = 0.05

#: How far below, once the aggregate is large enough for the comparison to
#: bind. A load factor far under the class's at town scale means the modelled
#: peak is much sharper than reality, which overstates feeder loading - the
#: S11 risk this check exists to catch.
LOAD_FACTOR_LOWER_ALLOWANCE = 0.15

#: Below this many homes, LP1 bounds only from above. 1,000 is chosen as the
#: order at which Baile Nua's own aggregate (about 1,100 homes) sits, and is
#: declared rather than fitted: the E1 slice of 50 homes measures 0.26 against
#: LP1's 0.41, which is the expected direction and magnitude for an aggregate
#: that small and is not evidence of a fault.
MIN_HOMES_FOR_A_LOWER_BOUND = 1000

#: Hours. The mean-day peak hour must land within this of LP1's.
PEAK_HOUR_TOLERANCE = 1

#: The hours the overnight shape is compared across, in clock order from the
#: evening peak's decline to the morning rise.
OVERNIGHT_HOURS: tuple[int, ...] = (22, 23, 0, 1, 2, 3, 4, 5, 6)

#: U32. The overnight term is the whole SHAPE across those hours, not a ratio
#: of two of them, and the band is derived from LP1 rather than declared:
#:
#:     band = mean |1.0 - LP1(h)| over OVERNIGHT_HOURS, halved
#:
#: That is "the check must reject a profile with no overnight shape at all, by
#: a factor of two". A flat profile - every hour at the daily mean - is the
#: degenerate case this check exists to catch, and anchoring on it means the
#: threshold is a property of the reference instead of a number chosen to let
#: the current model through. It comes out at about 0.19.
#:
#: Why the change (I-050). The taper was `mean(00:00) / mean(04:00)`, and the
#: week 2 step 4 ablation improved it by making the model worse: removing
#: chronotype synchronised the town, which raised the 22:00 peak and lowered
#: the 04:00 trough, so the ratio moved through its DENOMINATOR while midnight
#: did not move at all. A two-point ratio can be shifted by either point.
#:
#: The shape metric reverses that verdict and two others, which is the reason
#: to prefer it: it ranks the synchronised town WORSE than the full model
#: (0.094 against 0.085), and it ranks the young E1 estate worst of the three
#: real cases (0.162) where the taper ranked it best - because the estate's
#: 06:00 sits at 0.37 against LP1's 0.58, an early-morning deficit a
#: midnight-to-04:00 ratio cannot see.
OVERNIGHT_SHAPE_HALVING = 2.0

#: Kept as a SECONDARY metric (U32): reported in the detail, never gating.
#: It is the quantity I-044 was diagnosed and fixed against, so dropping it
#: would make that history unreadable.
#:
#: The overnight taper: the mean 00:00 hour over the mean 04:00 hour.
#:
#: This replaced a trough-HOUR test, and the reason is worth keeping. LP1 falls
#: steadily from 0.77x the daily mean at midnight to 0.45x at 04:00 - people go
#: to bed - so its trough hour is 04:00. The model's overnight is FLAT: 0.44x
#: at 00:00 and 0.46x at 04:00. Its argmin therefore lands on hour 0, four
#: hours "away" from the reference, on a difference of 0.02 between hours that
#: are indistinguishable. The argmin of a near-constant function is not a
#: statistic.
#:
#: The taper ratio is, and it says what the argmin only hinted at: the model
#: has no overnight decline at all. 1.25 is declared below LP1's measured 1.71
#: to allow a town whose occupancy mix differs from the national class, while
#: still asserting the qualitative fact that a domestic profile falls after
#: midnight. The model measures 0.96 and fails it.
MIN_OVERNIGHT_TAPER = 1.25


def _minutes(value: Any) -> int | None:
    """Excel gives these times as time, datetime or timedelta by column."""
    if isinstance(value, datetime.timedelta):
        return int(value.total_seconds() // 60)
    if isinstance(value, (datetime.time, datetime.datetime)):
        return value.hour * 60 + value.minute
    return None


@functools.lru_cache(maxsize=4)
def lp1_reference(sheet: str = DOMESTIC_SHEET) -> dict[str, Any]:
    """Load factor, peak-to-mean and mean diurnal shape for one SLP class."""
    import json

    import openpyxl

    from baile_nua.sources import REGISTRY

    path = require(SLP_KEY)
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb[sheet]
        title = None
        times: list[int] = []
        values: list[float] = []
        acc: dict[int, float] = defaultdict(float)
        cnt: dict[int, int] = defaultdict(int)
        peak = 0.0
        peak_at: tuple[str, int] | None = None
        for row in ws.iter_rows(values_only=True):
            if not row:
                continue
            if title is None and isinstance(row[0], str) \
                    and row[0].startswith("Load Profile"):
                title = row[0]
            if isinstance(row[1], str) and row[1] == "Date":
                times = [m for m in (_minutes(t) for t in row[2:])
                         if m is not None]
                continue
            if not hasattr(row[1], "year"):
                continue
            day = row[1]
            cells = [v for v in row[2:] if isinstance(v, (int, float))]
            for i, v in enumerate(cells):
                # Zeros are the daylight-saving gap, not a demand of zero for
                # a whole customer class. Including them would depress the
                # mean and flatter the load factor.
                if v <= 0 or i >= len(times):
                    continue
                values.append(float(v))
                minute = times[i] % 1440
                acc[minute] += v
                cnt[minute] += 1
                if v > peak:
                    peak, peak_at = float(v), (str(day.date()), times[i])
    finally:
        wb.close()

    if not values:
        raise LookupError(f"{SLP_KEY}: sheet {sheet!r} held no coefficients")

    n = len(values)
    mean = sum(values) / n
    diurnal = {m: acc[m] / cnt[m] for m in sorted(acc)}
    day_mean = sum(diurnal.values()) / len(diurnal)
    hourly: dict[int, float] = {}
    for minute, v in diurnal.items():
        hourly.setdefault(minute // 60, []).append(v)  # type: ignore[arg-type]
    hour_mean = {h: sum(vs) / len(vs) for h, vs in hourly.items()}  # type: ignore[union-attr]

    sha = json.loads(
        REGISTRY[SLP_KEY].manifest_path.read_text(encoding="utf-8")
    )["sha256"]
    return {
        "source_key": SLP_KEY,
        "sha256": sha,
        "sheet": sheet,
        "title": title,
        "year": "2022",
        "n_intervals": n,
        "interval_minutes": 15,
        "sum_of_coefficients": round(sum(values), 6),
        "load_factor": round(mean / peak, 6),
        "peak_over_mean": round(peak / mean, 6),
        "annual_peak_at": {
            "date": peak_at[0] if peak_at else None,
            "minute_of_day": peak_at[1] if peak_at else None,
            "note": (
                "A Christmas-week midday cooking peak, not an evening one, "
                "which is why the timing test uses the mean diurnal shape "
                "and not the annual maximum."
            ),
        },
        "mean_day_peak_hour": max(hour_mean, key=hour_mean.get),
        "mean_day_trough_hour": min(hour_mean, key=hour_mean.get),
        "overnight_taper_00_over_04": round(
            hour_mean[0] / hour_mean[4], 4
        ) if 0 in hour_mean and hour_mean.get(4) else None,
        "mean_day_peak_over_day_mean": round(
            max(hour_mean.values()) / day_mean, 4
        ),
        "hourly_shape_over_day_mean": {
            h: round(v / day_mean, 4) for h, v in sorted(hour_mean.items())
        },
        # The quarter-hourly mean day, keyed by minute-of-day. Exposed because
        # NC-W2-08 builds its planted package from it: a year in which every
        # day is the average day has no seasonal or day-to-day variation, and
        # its load factor is therefore far too high. That is a real synthetic-
        # data failure mode and it needs no tuning to construct.
        "mean_diurnal_over_day_mean": {
            m: round(v / day_mean, 6) for m, v in sorted(diurnal.items())
        },
    }


def overnight_shape_band(reference: dict[str, Any] | None = None) -> float:
    """The acceptance band, derived from LP1 rather than declared.

    Half the deviation a profile with NO overnight shape would show. Derived
    so that the threshold is a property of the published reference and cannot
    drift into being a number chosen to admit whatever the model currently
    does.
    """
    ref = reference or lp1_reference()
    shape = {int(h): float(v) for h, v in ref["hourly_shape_over_day_mean"].items()}
    flat = sum(abs(1.0 - shape[h]) for h in OVERNIGHT_HOURS) / len(OVERNIGHT_HOURS)
    return flat / OVERNIGHT_SHAPE_HALVING


def overnight_shape_mad(
    hourly_over_day_mean: dict[Any, float],
    reference: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Mean absolute deviation from LP1 across the overnight hours.

    Mean absolute rather than root-mean-square: the question is whether the
    whole overnight profile sits where the meters say, and a squared penalty
    would let a check be dominated by one hour. The per-hour deviations are
    returned as well, because "the shape is wrong" is not actionable and "06:00
    is 0.21 low" is.
    """
    ref = reference or lp1_reference()
    lp1 = {int(h): float(v) for h, v in ref["hourly_shape_over_day_mean"].items()}
    model = {int(h): float(v) for h, v in hourly_over_day_mean.items()}
    missing = [h for h in OVERNIGHT_HOURS if h not in model]
    if missing:
        raise LookupError(f"the profile has no hours {missing}")
    per_hour = {
        h: round(model[h] - lp1[h], 4) for h in OVERNIGHT_HOURS
    }
    mad = sum(abs(v) for v in per_hour.values()) / len(per_hour)
    band = overnight_shape_band(ref)
    worst = max(per_hour, key=lambda h: abs(per_hour[h]))
    return {
        "hours": list(OVERNIGHT_HOURS),
        "mad": round(mad, 4),
        "band": round(band, 4),
        "within_band": bool(mad <= band),
        "deviation_by_hour": per_hour,
        "worst_hour": worst,
        "worst_deviation": per_hour[worst],
        "flat_profile_mad": round(band * OVERNIGHT_SHAPE_HALVING, 4),
        "band_basis": (
            "half the deviation a profile with no overnight shape at all "
            "would show against LP1, derived from the reference rather than "
            "declared"
        ),
        "model": {h: round(model[h], 4) for h in OVERNIGHT_HOURS},
        "reference": {h: round(lp1[h], 4) for h in OVERNIGHT_HOURS},
    }


#: The epoch length LP1 is published at. Anything shorter is below the
#: source's resolution and cannot be measured from it.
LP1_PUBLISHED_EPOCH_MINUTES = 15


def max_epoch_ramp(sheet: str = DOMESTIC_SHEET) -> dict[str, Any]:
    """The largest change in LP1 between adjacent quarter-hours, as a fraction.

    Needed by the 8.2 timing contract. The contract shrinks the network
    envelope by a "staleness margin", and the margin has to cover how much a
    connection's load can move between one network solve and the next. LP1 is
    the settlement profile for an urban domestic connection, so its own
    maximum quarter-hour ramp is a PUBLISHED per-connection ramp rather than
    one measured from our own output - which matters, because a margin
    calibrated on the model would make the contract's guarantee circular.

    Ramps are taken only between adjacent intervals **within the same day**.
    The reader skips the daylight-saving zeros, and differencing across a skip
    would invent a jump that the profile does not contain.

    It is an after-diversity ramp: LP1 is a customer-class profile, so a
    single dwelling's ramp is larger. That makes the margin derived here a
    LOWER bound on what a single connection needs, and the contract's test is
    written knowing that.
    """
    import json
    from collections import defaultdict

    import openpyxl

    from baile_nua.sources import REGISTRY

    path = require(SLP_KEY)
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    by_day: dict[str, list[tuple[int, float]]] = defaultdict(list)
    all_values: list[float] = []
    try:
        ws = wb[sheet]
        times: list[int] = []
        for row in ws.iter_rows(values_only=True):
            if not row:
                continue
            if isinstance(row[1], str) and row[1] == "Date":
                times = [m for m in (_minutes(t) for t in row[2:])
                         if m is not None]
                continue
            if not hasattr(row[1], "year"):
                continue
            day = str(row[1].date())
            cells = [v for v in row[2:] if isinstance(v, (int, float))]
            for i, v in enumerate(cells):
                if v <= 0 or i >= len(times):
                    continue
                by_day[day].append((times[i], float(v)))
                all_values.append(float(v))
    finally:
        wb.close()

    if not all_values:
        raise LookupError(f"{SLP_KEY}: sheet {sheet!r} held no coefficients")

    mean = sum(all_values) / len(all_values)
    worst = 0.0
    worst_at: tuple[str, int] | None = None
    n_pairs = 0
    ramps: list[float] = []
    for day, pairs in by_day.items():
        pairs.sort()
        for (t0, v0), (t1, v1) in zip(pairs, pairs[1:]):
            if t1 - t0 != LP1_PUBLISHED_EPOCH_MINUTES:
                continue              # a gap: do not difference across it
            r = abs(v1 - v0) / mean
            ramps.append(r)
            n_pairs += 1
            if r > worst:
                worst, worst_at = r, (day, t1)

    ramps.sort()
    sha = json.loads(
        REGISTRY[SLP_KEY].manifest_path.read_text(encoding="utf-8")
    )["sha256"]
    return {
        "source_key": SLP_KEY,
        "sha256": sha,
        "sheet": sheet,
        "epoch_minutes": LP1_PUBLISHED_EPOCH_MINUTES,
        "n_adjacent_pairs": n_pairs,
        "max_ramp_fraction_of_mean": worst,
        "max_ramp_at": worst_at,
        "p99_ramp_fraction_of_mean": ramps[int(0.99 * len(ramps))],
        "p999_ramp_fraction_of_mean": ramps[int(0.999 * len(ramps))],
        "median_ramp_fraction_of_mean": ramps[len(ramps) // 2],
        "note": (
            "An after-diversity ramp for a customer class, so a single "
            "dwelling's ramp is larger. A margin derived from it is a LOWER "
            "bound on what one connection needs."
        ),
    }
