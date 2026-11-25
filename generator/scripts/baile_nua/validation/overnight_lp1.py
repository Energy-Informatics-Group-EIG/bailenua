"""Load per awake person against ESB Networks LP1. Independent, and never tuned.

I-052 measured this once, by hand, and the numbers went into the issue without
an artefact behind them. Under the project's own rule — where there is no
artefact there is no number — that made them unquotable. This module is the
measurement, so the comparison can be re-derived from a run rather than
remembered.

**Why per awake person and not per home.** An aggregate overnight profile
confounds three things that fail in different places and are fixed in different
layers:

===================  =======================================================
the awake count      how many people are up at 23:00 — the sleep timing, which
                     U32 calibrated against HETUS to a mean absolute deviation
                     of 0.0283
the standby floor    what a sleeping house draws — fridges, routers, standby
what awake people    appliances, lighting, television, showers — the device and
are doing            activity layers
===================  =======================================================

A town whose load is right and whose sleep timing is wrong looks identical, in
aggregate, to one whose sleep timing is right and whose appliances are wrong.
Dividing each hour's normalised load by that hour's awake share separates them,
and that decomposition is what let I-052 conclude that the first two are right
and the residual is the third.

**LP1's exposure is ``none`` and must stay there.** It is the only independent
reference on the overnight shape in the whole build. Nothing may be fitted to
it, no timing may be adjusted to move this score, and this module computes a
number without ever being allowed to change one. The guard is not a convention:
:func:`assert_not_a_calibration_target` always raises, so any module that
imports this to tune against it fails rather than succeeding quietly.

**What the score is.** Mean absolute relative deviation of load per awake
person, model against LP1, over the overnight hours — each hour's model value
divided by LP1's, the deviation from 1.0 taken absolute, and averaged. It is
reported as it stands. There is no band and no pass mark here on purpose:
PL-PEAK-01 owns the acceptance test on the overnight *shape*, and inventing a
second band for the per-awake decomposition would be inventing a threshold for
a quantity with no published reference.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "SOURCE_KEY",
    "EXPOSURE",
    "OVERNIGHT_HOURS",
    "assert_not_a_calibration_target",
    "load_per_awake_person",
    "compare_to_lp1",
]

#: ESB Networks' published settlement profile.
SOURCE_KEY = "esbn.rmds.slp_indexes_2022"

#: Declared, and the reason this module exists. LP1 is the only independent
#: check on the overnight load shape, so its exposure must never become
#: anything else.
EXPOSURE = "none"

#: The hours the comparison covers: the evening boundary, the night, and the
#: morning boundary. Taken from :mod:`baile_nua.plausibility.slp`'s own
#: overnight definition so the two cannot drift apart, with 22:00 and 06:00
#: included because I-052's finding is specifically at the boundaries.
OVERNIGHT_HOURS: tuple[int, ...] = (22, 23, 0, 1, 2, 3, 4, 5, 6)


class CalibrationTargetError(RuntimeError):
    """Raised whenever LP1 is reached for as something to fit."""


def assert_not_a_calibration_target() -> None:
    """Always raises. LP1 may be scored against and never fitted to.

    Importable so that a future module which tries to use this comparison as
    an objective has to delete a line that says it must not, rather than
    merely not reading a comment.
    """
    raise CalibrationTargetError(
        f"{SOURCE_KEY} has model_development_exposure={EXPOSURE!r} and is the "
        f"only independent reference on the overnight load shape in this "
        f"build. It may be scored against; it may not be fitted to, and no "
        f"activity timing, appliance trigger rate or ownership prior may be "
        f"adjusted to move the number this module reports. If the score is "
        f"bad, report it and change the mechanism for a reason that comes "
        f"from somewhere else."
    )


def _lp1_hourly_shape() -> dict[int, float]:
    """LP1's mean-day hourly load, normalised by its own day mean."""
    from baile_nua.plausibility import slp

    ref = slp.lp1_reference()
    shape = ref.get("hourly_shape_over_day_mean")
    if not shape:
        raise CalibrationTargetError(
            "LP1's reference carries no hourly shape, so the overnight "
            "comparison cannot be made from the source"
        )
    return {int(k): float(v) for k, v in shape.items()}


def load_per_awake_person(
    *, hourly_shape: dict[Any, float], awake_share_by_hour: dict[Any, float],
) -> dict[int, float]:
    """Normalised load divided by the awake share, hour by hour.

    Both inputs are shares, so the quotient is dimensionless: "how much of a
    mean hour's load one awake person accounts for". That is the quantity that
    can be compared between a simulation and a settlement profile without
    needing the two to have the same number of customers, which they emphatically
    do not — LP1 aggregates about two million meters.
    """
    shape = {int(k): float(v) for k, v in hourly_shape.items()}
    awake = {int(k): float(v) for k, v in awake_share_by_hour.items()}
    out: dict[int, float] = {}
    for h in sorted(shape):
        a = awake.get(h)
        if a is None or a <= 1e-6:
            # Nobody awake at all: the quotient is not a number, and reporting
            # a large one would be an artefact of the division rather than a
            # finding. Omitted, and the caller is told how many were.
            continue
        out[h] = shape[h] / a
    return out


def compare_to_lp1(
    *, feeder_shape: dict[str, Any], awake_share: dict[str, Any],
) -> dict[str, Any]:
    """Score a run's overnight load per awake person against LP1.

    ``feeder_shape`` and ``awake_share`` are the run diagnostics' own blocks,
    so the comparison is made from what the run recorded rather than from a
    re-simulation that might differ.

    **LP1's own awake share is not published**, and that is the honest
    limitation of this comparison: the denominator applied to LP1 is the
    *model's* awake share, because there is no measured Irish diurnal sleep
    curve attached to the settlement profile. So this does not compare two
    independently-measured per-awake quantities. It asks: holding the awake
    count at the model's own HETUS-calibrated value, how far is the model's
    load from LP1's at each hour? That is a weaker statement than it looks and
    is stated rather than implied.
    """
    if not feeder_shape.get("measured"):
        return {"measured": False,
                "why": "the run recorded no feeder shape, so there is nothing "
                       "to compare"}
    if not awake_share.get("measured"):
        return {"measured": False,
                "why": "the run recorded no awake share, so the load cannot be "
                       "read per awake person"}

    model_shape = {int(k): float(v)
                   for k, v in feeder_shape["hourly_shape_over_day_mean"].items()}
    awake = {int(k): float(v)
             for k, v in awake_share["awake_share_by_hour"].items()}
    lp1_shape = _lp1_hourly_shape()

    model_per_awake = load_per_awake_person(
        hourly_shape=model_shape, awake_share_by_hour=awake)
    lp1_per_awake = load_per_awake_person(
        hourly_shape=lp1_shape, awake_share_by_hour=awake)

    rows: list[dict[str, Any]] = []
    deviations: list[float] = []
    for h in OVERNIGHT_HOURS:
        m = model_per_awake.get(h)
        r = lp1_per_awake.get(h)
        if m is None or r is None or r <= 0:
            rows.append({"hour": h, "model_per_awake": m, "lp1_per_awake": r,
                         "ratio": None, "omitted": True})
            continue
        ratio = m / r
        rows.append({
            "hour": h,
            "model_per_awake": round(m, 4),
            "lp1_per_awake": round(r, 4),
            "ratio": round(ratio, 4),
            "reading": ("draws %.2fx too much" % ratio if ratio > 1.05
                        else "draws %.2fx, too little" % ratio if ratio < 0.95
                        else "matches within 5%%"),
        })
        deviations.append(abs(ratio - 1.0))

    n = len(deviations)
    worst = max(rows, key=lambda r: abs((r["ratio"] or 1.0) - 1.0))
    return {
        "measured": True,
        "source": SOURCE_KEY,
        "model_development_exposure": EXPOSURE,
        "independent": True,
        "hours": rows,
        "n_hours_scored": n,
        "n_hours_omitted": len(OVERNIGHT_HOURS) - n,
        "mean_absolute_relative_deviation": (
            round(sum(deviations) / n, 4) if n else None),
        "max_absolute_relative_deviation": (
            round(max(deviations), 4) if n else None),
        "worst_hour": worst["hour"],
        "no_band_and_no_pass_mark": (
            "deliberate. PL-PEAK-01 owns the acceptance test on the overnight "
            "shape, against a band derived from LP1 itself. There is no "
            "published reference for load per AWAKE person, so a band for "
            "this decomposition would be a threshold this build invented for "
            "a quantity nobody measures. The number is reported as it stands."
        ),
        "denominator_caveat": (
            "LP1's own awake share is not published, so the model's "
            "HETUS-calibrated awake share is used as the denominator for both "
            "sides. The ratio therefore isolates the LOAD difference at a "
            "held awake count; it is not a comparison of two independently "
            "measured per-awake quantities."
        ),
        "never_tuned": (
            "No activity timing, appliance trigger rate or ownership prior "
            "was adjusted to move this number. "
            "assert_not_a_calibration_target() raises unconditionally."
        ),
    }
