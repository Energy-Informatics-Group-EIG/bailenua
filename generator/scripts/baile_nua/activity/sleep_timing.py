"""U32 part 2: bedtime and wake-time spread, from a time-use source (I-051).

What was wrong
--------------
I-051 recorded that the model's overnight load sat too low from 00:00 to 02:00
and guessed that bedtimes were too early. The source says otherwise, and the
distinction matters: HETUS UK's **share asleep by time of day** (code AC0A)
gives

=======  =============  ==============
hour     HETUS awake    model awake
=======  =============  ==============
00:00    14.5%          8.4%
01:00    8.8%           1.2%
02:00    6.9%           0.1%
=======  =============  ==============

The model's median bedtime is if anything slightly late. What it lacks is
**spread and a right tail**: ``bed = wake - N(8.4h, 35min)`` with wake itself
drawn at sigma 22 minutes gives a bedtime standard deviation near 41 minutes,
so a 10th-to-90th-percentile range of about +/-53 minutes. HETUS implies about
+/-100 minutes with a tail reaching past 02:00. A distribution that narrow
cannot produce people who are still up at one in the morning, however its
centre is placed.

What this module does, and does not do
--------------------------------------
It supplies **shape only**: the quantile offsets of bedtime and wake time
relative to their own medians. The medians stay where the model already puts
them, because they are anchored to Irish data - the wake anchor comes from
Cobh's Census travel-to-work and time-leaving-home tables - and HETUS is a UK
donor. Taking the centre from the UK would overwrite an Irish measurement with
a foreign one; taking the spread from it replaces a declared guess with a
measurement of how much people differ, which is a far more transportable
quantity than when they get up.

How the curve becomes a distribution
------------------------------------
``asleep(t)`` runs from a floor of about 3.7% (daytime nappers and shift
workers, who are asleep at 14:00) to a peak of 94.5% at 04:00. It never
reaches 0 or 1, so the normalisation is declared rather than assumed:

    F_bed(t) = (asleep(t) - floor) / (peak - floor)

read as "the fraction of people who sleep at night who have gone to bed by t".
The morning side is the mirror image. Both are read off the published
ten-minute bands, so the tail is the measured tail and not an extrapolation.

Chronotype carries the spread
-----------------------------
The person's ``chronotype`` selects their quantile rather than adding an offset
of its own. A late chronotype draws from the late tail, an early one from the
early tail, and the population's marginal distribution comes out as HETUS's -
the town's chronotype has a standard deviation of 1.31, so mapping it through
a normal CDF gives near-uniform quantiles. Adding a separate hourly offset on
top, as the old code did, would widen the result past the source.

It also means the step 4 ablation still works and still means something:
``no_chronotype`` sets every chronotype to zero, so everyone draws the median
and the spread collapses - which is the right degradation and is why that arm
sharpens the aggregate peak.

Evidence tag
------------
**[A], a UK-to-Ireland transfer under U04.** Ireland is in neither HETUS wave
(I-008), which is why the whole activity engine uses the UK as its structural
donor and why the activity layer is flagged VERIFIED, NOT CALIBRATED. These
parameters inherit that flag. The search behind it: U30 swept all 13,086 PxStat
tables and found **no Irish time-use survey** - the only matches for `time use`
are well-being tables on satisfaction with the amount of leisure time (sweep
flag A-01). So there is no Irish sleep-timing distribution to prefer, and the
transfer is of a dispersion rather than a level, which is the weakest claim
that still fixes the defect.
"""

from __future__ import annotations

import csv
import functools
import math
from typing import Any

__all__ = [
    "SOURCE_KEY",
    "DONOR_GEO",
    "DONOR_WAVE",
    "EVIDENCE_TAG",
    "SEARCH_RECORD",
    "asleep_share_curve",
    "bedtime_offsets",
    "waketime_offsets",
    "offset_at_quantile",
    "quantile_for_chronotype",
    "VALIDATION_HOURS",
    "awake_share_reference",
    "awake_share_fit",
]

SOURCE_KEY = "eurostat.hetus.tus_00startime"
DONOR_GEO = "UK"
DONOR_WAVE = "2010"
SLEEP_CODE = "AC0A"

EVIDENCE_TAG = "[A]"

SEARCH_RECORD = (
    "U30 swept all 13,086 PxStat tables on 9 Oct 2026. `time use` and "
    "`time-use` match only well-being tables on SATISFACTION with the amount "
    "of leisure time (WBA39, WBA40, WBB63-66), which measure contentment and "
    "not duration; `time budget` and `diary` match nothing. Ireland is in "
    "neither HETUS wave (I-008). So there is no Irish sleep-timing "
    "distribution to prefer over the UK donor, and this is a transfer of "
    "DISPERSION rather than of level - the medians stay anchored to Cobh's "
    "own Census travel-to-work and time-leaving-home tables."
)

#: The quantiles the offsets are tabulated at. Dense in the tails, because the
#: tail is the thing being fixed: the old distribution's failure was at the
#: 95th percentile and beyond, where the people still awake at 01:00 live.
QUANTILES: tuple[float, ...] = (
    0.01, 0.02, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50,
    0.60, 0.70, 0.80, 0.90, 0.95, 0.98, 0.99,
)


@functools.lru_cache(maxsize=1)
def asleep_share_curve() -> dict[int, float]:
    """Share asleep by minute-of-day, from the declared HETUS source.

    Keyed by the start minute of each published ten-minute band. Both sexes
    and the 2010 wave, which is the wave the rest of the activity engine uses.
    """
    from baile_nua.sources import require

    path = require(SOURCE_KEY)
    acc: dict[int, list[float]] = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if (row.get("geo") != DONOR_GEO
                    or row.get("acl00") != SLEEP_CODE
                    or row.get("sex") != "T"
                    or row.get("TIME_PERIOD") != DONOR_WAVE):
                continue
            band = row.get("startime") or ""
            if not (band.startswith("H") and "-" in band and len(band) == 10):
                continue
            try:
                minute = int(band[1:3]) * 60 + int(band[3:5])
                value = float(row["OBS_VALUE"])
            except (ValueError, KeyError):
                continue
            acc.setdefault(minute, []).append(value)
    if len(acc) < 100:
        raise LookupError(
            f"{SOURCE_KEY} gave only {len(acc)} time bands for "
            f"{DONOR_GEO}/{SLEEP_CODE}; the curve needs the full day"
        )
    return {m: sum(v) / len(v) / 100.0 for m, v in sorted(acc.items())}


def _normalised(curve: dict[int, float]) -> tuple[float, float]:
    """The floor and peak the CDF is normalised against."""
    return min(curve.values()), max(curve.values())


def _invert(
    points: list[tuple[float, int]], q: float
) -> float:
    """Linear interpolation of a monotone (fraction, minute) table."""
    points = sorted(points)
    if q <= points[0][0]:
        return float(points[0][1])
    if q >= points[-1][0]:
        return float(points[-1][1])
    for (f0, m0), (f1, m1) in zip(points, points[1:]):
        if f0 <= q <= f1:
            if f1 == f0:
                return float(m0)
            return float(m0) + (q - f0) / (f1 - f0) * (m1 - m0)
    return float(points[-1][1])


@functools.lru_cache(maxsize=1)
def bedtime_offsets() -> dict[str, Any]:
    """Bedtime quantiles as minutes from the median, from the evening side.

    Clock minutes run past midnight (25 * 60 is 01:00 the next day) so the
    curve stays monotone across the boundary, which is where the tail lives.
    """
    curve = asleep_share_curve()
    floor, peak = _normalised(curve)
    span = peak - floor
    points: list[tuple[float, int]] = []
    # 19:00 through 05:00, as a continuous evening-to-small-hours run.
    for minute in list(range(19 * 60, 24 * 60, 10)) + list(range(0, 5 * 60, 10)):
        if minute not in curve:
            continue
        clock = minute if minute >= 19 * 60 else minute + 24 * 60
        frac = (curve[minute] - floor) / span
        points.append((min(max(frac, 0.0), 1.0), clock))
    # Enforce monotonicity: the published series wobbles by a tenth of a point
    # here and there, and a CDF that steps backwards would invert wrongly.
    points.sort(key=lambda p: p[1])
    cleaned: list[tuple[float, int]] = []
    running = 0.0
    for frac, clock in points:
        running = max(running, frac)
        cleaned.append((running, clock))
    median = _invert(cleaned, 0.5)
    return {
        "median_clock_minute": median,
        "offsets": {q: round(_invert(cleaned, q) - median, 1) for q in QUANTILES},
        "floor": round(floor, 4),
        "peak": round(peak, 4),
        "n_points": len(cleaned),
        "evidence_tag": EVIDENCE_TAG,
        "source": SOURCE_KEY,
        "donor": f"{DONOR_GEO} {DONOR_WAVE}",
    }


@functools.lru_cache(maxsize=1)
def waketime_offsets() -> dict[str, Any]:
    """Wake-time quantiles as minutes from the median, from the morning side."""
    curve = asleep_share_curve()
    floor, peak = _normalised(curve)
    span = peak - floor
    points: list[tuple[float, int]] = []
    for minute in range(3 * 60, 13 * 60, 10):
        if minute not in curve:
            continue
        # Fraction already woken by this minute.
        frac = 1.0 - (curve[minute] - floor) / span
        points.append((min(max(frac, 0.0), 1.0), minute))
    points.sort(key=lambda p: p[1])
    cleaned: list[tuple[float, int]] = []
    running = 0.0
    for frac, minute in points:
        running = max(running, frac)
        cleaned.append((running, minute))
    median = _invert(cleaned, 0.5)
    return {
        "median_clock_minute": median,
        "offsets": {q: round(_invert(cleaned, q) - median, 1) for q in QUANTILES},
        "n_points": len(cleaned),
        "evidence_tag": EVIDENCE_TAG,
        "source": SOURCE_KEY,
        "donor": f"{DONOR_GEO} {DONOR_WAVE}",
    }


def offset_at_quantile(offsets: dict[float, float], q: float) -> float:
    """Interpolate the tabulated offsets at an arbitrary quantile."""
    qs = sorted(offsets)
    q = min(max(float(q), qs[0]), qs[-1])
    for a, b in zip(qs, qs[1:]):
        if a <= q <= b:
            if b == a:
                return float(offsets[a])
            w = (q - a) / (b - a)
            return float(offsets[a]) * (1.0 - w) + float(offsets[b]) * w
    return float(offsets[qs[-1]])


#: The town's chronotype standard deviation, used to map the trait onto a
#: quantile. Measured from the synthesised population (1.31) rather than
#: declared, so the mapping stays centred if the trait's distribution changes.
CHRONOTYPE_SD = 1.31


def quantile_for_chronotype(chronotype: float) -> float:
    """The sleep-timing quantile a person's chronotype puts them at.

    A normal CDF, so a chronotype of zero is the median and the trait's own
    spread becomes an approximately uniform spread over quantiles. This is
    what makes the population's marginal bedtime distribution come out as
    HETUS's rather than as HETUS convolved with something else.
    """
    z = float(chronotype) / CHRONOTYPE_SD
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


#: The hours the awake-share validation is scored across. 21:00 to 08:00, the
#: range U32 names: the evening wind-down, the small hours and the morning
#: rise, which together are what the overnight load shape is made of.
VALIDATION_HOURS: tuple[int, ...] = (
    21, 22, 23, 0, 1, 2, 3, 4, 5, 6, 7, 8,
)


def awake_share_reference() -> dict[int, float]:
    """HETUS's share AWAKE by hour, the quantity the model is scored against.

    The complement of the asleep curve, normalised the same way: the floor
    (daytime nappers and shift workers, about 3.7%) and the peak (94.5% at
    04:00) are both taken out, so this reads as "the share of people who sleep
    at night who are awake at hour h".

    **This is a consistency check, not an independent validation** (I-060).
    The bedtime and wake offsets in :func:`bedtime_offsets` and
    :func:`waketime_offsets` are derived from the *same* ``asleep_share_curve``,
    so scoring the model against this curve asks whether the implementation
    reproduces the distribution it was given — through chronotype quantiles,
    the workday damping, the clip bounds and the day-boundary handling, any of
    which can fail. That is a real and useful question: it is how the fit went
    from 0.0621 to 0.0283. What it cannot do is evidence that Irish sleep
    timing resembles the model's, because the model was built from this curve.

    It is still the right thing to check first. An overnight load shape that
    matched LP1 while the awake curve did not would mean the model had got the
    right electricity for the wrong reason — and LP1, at exposure ``none``, is
    the independent check on the load shape.
    """
    curve = asleep_share_curve()
    floor, peak = _normalised(curve)
    span = peak - floor
    by_hour: dict[int, list[float]] = {}
    for minute, share in curve.items():
        norm = (share - floor) / span
        by_hour.setdefault(minute // 60, []).append(min(max(norm, 0.0), 1.0))
    return {
        h: round(1.0 - sum(v) / len(v), 4)
        for h, v in sorted(by_hour.items())
    }


def awake_share_fit(
    model_awake_by_hour: dict[int, float]
) -> dict[str, Any]:
    """Score the model's awake share against HETUS's, hour by hour.

    Mean absolute deviation over :data:`VALIDATION_HOURS`, with the per-hour
    deviations returned: "the sleep timing is wrong" is not actionable and
    "02:00 is 6.8 points low" is.
    """
    ref = awake_share_reference()
    model = {int(h): float(v) for h, v in model_awake_by_hour.items()}
    missing = [h for h in VALIDATION_HOURS if h not in model or h not in ref]
    if missing:
        raise LookupError(f"no awake share for hours {missing}")
    dev = {h: round(model[h] - ref[h], 4) for h in VALIDATION_HOURS}
    mad = sum(abs(v) for v in dev.values()) / len(dev)
    worst = max(dev, key=lambda h: abs(dev[h]))
    return {
        "hours": list(VALIDATION_HOURS),
        "mad": round(mad, 4),
        "deviation_by_hour": dev,
        "worst_hour": worst,
        "worst_deviation": dev[worst],
        "model": {h: round(model[h], 4) for h in VALIDATION_HOURS},
        "reference": {h: ref[h] for h in VALIDATION_HOURS},
        "source": SOURCE_KEY,
        "donor": f"{DONOR_GEO} {DONOR_WAVE}",
        "evidence_tag": EVIDENCE_TAG,
        "search_record": SEARCH_RECORD,
    }
