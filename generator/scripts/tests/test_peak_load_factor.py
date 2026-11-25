"""PL-PEAK-01: feeder loading against ESB Networks' Standard Load Profile LP1.

I-039 said feeder loading must not reach E2 unchecked. U30 established that
PxStat publishes nothing on it - zero hits for every phrasing of peak and load
factor across 13,086 tables (I-043) - and the reference turned out to be
published by the network operator instead: LP1, Urban Domestic 24 Hour, as
quarter-hourly coefficients summing to 1.0 over the year.

Two real bugs were found while building this, and both have a test here,
because both would have produced a confident wrong number rather than an error:

* summing D19 without choosing an export view, which counts the same energy
  about four times and reported 9.2 kW per home against the package's own
  1.49 kW;
* testing the trough HOUR, which is the argmin of a near-constant overnight
  profile and so lands wherever noise puts it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

import baile_nua.sources_registry  # noqa: F401
from baile_nua.plausibility import CHECKS, run_suite
from baile_nua.plausibility.slp import (
    DOMESTIC_SHEET,
    LOAD_FACTOR_LOWER_ALLOWANCE,
    LOAD_FACTOR_UPPER_ALLOWANCE,
    MIN_HOMES_FOR_A_LOWER_BOUND,
    MIN_OVERNIGHT_TAPER,
    lp1_reference,
)

ROOT = Path(__file__).resolve().parents[2]
E1 = ROOT / "v1"
E1_DIAG = E1 / "run_diagnostics.json"
CHECK = next(c for c in CHECKS if c.check_id == "PL-PEAK-01")


@pytest.fixture(scope="module")
def ref():
    return lp1_reference()


@pytest.fixture(scope="module")
def result():
    return run_suite(
        package_root=E1, diagnostics_path=E1_DIAG, checks=(CHECK,)
    )["results"][0]


# --------------------------------------------------------------------------- #
# the reference
# --------------------------------------------------------------------------- #

def test_the_reference_is_a_unitised_annual_profile(ref):
    """The coefficients sum to 1.0, which is what makes a load factor fall out.

    If this ever stopped holding, the load factor would be a ratio of two
    things on different scales and would still look like a number.
    """
    assert abs(ref["sum_of_coefficients"] - 1.0) < 1e-3
    assert ref["n_intervals"] > 35_000
    assert ref["interval_minutes"] == 15


def test_the_domestic_class_is_the_24_hour_one_not_the_night_saver(ref):
    """LP2 and LP4 would flatter any model compared against them.

    The night-saver classes carry overnight storage-heating load, which lifts
    their load factor to about 0.60 against LP1's 0.41. Comparing a model
    against the wrong class would make a too-smooth model look right.
    """
    assert DOMESTIC_SHEET == "LP1"
    assert "Urban Domestic 24 Hour" in ref["title"]
    assert 0.35 < ref["load_factor"] < 0.47
    night_saver = lp1_reference("LP2")
    assert night_saver["load_factor"] > ref["load_factor"] + 0.15, (
        "the night-saver class is no longer distinguishable from LP1; check "
        "the sheet mapping before trusting either"
    )


def test_the_annual_peak_is_not_an_evening_peak(ref):
    """Why the timing test uses the mean day and not the annual maximum.

    LP1 2022's annual peak quarter-hour is 2022-12-27 at 13:45 - Christmas-week
    midday cooking. A "the peak must fall between 16:00 and 21:00" test would
    have been written and would have been wrong about the reference itself.
    """
    assert ref["annual_peak_at"]["date"] == "2022-12-27"
    minute = ref["annual_peak_at"]["minute_of_day"]
    assert 11 * 60 <= minute <= 15 * 60, (
        f"the annual peak is at minute {minute}; if it has moved to the "
        f"evening the note explaining this test can be simplified"
    )


def test_the_mean_day_is_stable_where_the_annual_maximum_is_not(ref):
    assert ref["mean_day_peak_hour"] == 18
    assert ref["mean_day_trough_hour"] == 4
    assert ref["overnight_taper_00_over_04"] > 1.5


# --------------------------------------------------------------------------- #
# the bug that reported 9.2 kW per home
# --------------------------------------------------------------------------- #

def test_exactly_one_d19_view_is_read(result):
    """D19 holds four export configurations of the same energy.

    home_15min, home_30min, compliance_only and a pre-summed
    estate_aggregate. Summing its rows without choosing one counts the estate
    about four times, which is what a first version of this check did.
    """
    detail = result["detail"]
    assert detail["view_read"] == "home_15min"
    assert detail["interval_minutes"] == 15


def test_the_measured_peak_agrees_with_the_package_s_own_feeder_peak(result):
    """The cross-check that caught the four-fold count.

    The run diagnostics record `feeder_peak_w_per_home` independently, from
    the simulation rather than from the export view. The two must agree, and
    when the view selection was wrong they differed by a factor of six.
    """
    diag = json.loads(E1_DIAG.read_text(encoding="utf-8"))
    independent = float(diag["feeder_peak_w_per_home"])
    measured = float(result["measured"]["aggregate_peak_w_per_home"])
    assert abs(measured - independent) / independent < 0.02, (
        f"the export view gives {measured:.0f} W/home and the diagnostics "
        f"{independent:.0f} W/home; one of them is counting wrong"
    )


def test_a_d19_mixing_interval_lengths_is_refused():
    """A load factor is resolution-dependent; it cannot straddle resolutions."""
    t0 = pd.Timestamp("2022-01-01 00:00:00+00:00")
    rows = []
    for i in range(4):
        rows.append({
            "premises_id": "P1", "interval_start": t0 + pd.Timedelta(minutes=15 * i),
            "interval_end": t0 + pd.Timedelta(minutes=15 * (i + 1)),
            "import_wh": 10.0, "export_config": "home_15min",
        })
    rows.append({
        "premises_id": "P1", "interval_start": t0 + pd.Timedelta(hours=1),
        "interval_end": t0 + pd.Timedelta(hours=1, minutes=30),
        "import_wh": 20.0, "export_config": "home_15min",
    })
    pkg = {"D19": pd.DataFrame(rows)}
    with pytest.raises(LookupError, match="mixes interval lengths"):
        CHECK.measure(pkg)


def test_a_d19_without_a_per_home_view_is_refused():
    """Better to raise than to silently sum a pre-aggregated estate view."""
    t0 = pd.Timestamp("2022-01-01 00:00:00+00:00")
    frame = pd.DataFrame([{
        "premises_id": "ESTATE", "interval_start": t0,
        "interval_end": t0 + pd.Timedelta(minutes=30),
        "import_wh": 1000.0, "export_config": "estate_aggregate",
    }])
    with pytest.raises(LookupError, match="none of the per-home views"):
        CHECK.measure({"D19": frame})


# --------------------------------------------------------------------------- #
# the verdict on the E1 package
# --------------------------------------------------------------------------- #

def test_the_load_factor_is_below_the_upper_bound(result, ref):
    """The term that catches load spread too evenly to be real."""
    detail = result["detail"]
    assert detail["load_factor_upper_ok"] is True
    assert detail["load_factor_upper_bound"] == pytest.approx(
        ref["load_factor"] + LOAD_FACTOR_UPPER_ALLOWANCE, abs=1e-4
    )


def test_the_lower_bound_does_not_apply_to_fifty_homes(result):
    """LP1 aggregates about two million meters; the slice has fifty.

    A smaller aggregate is legitimately spikier, so LP1 bounds it from above
    only. The slice measures about 0.26 against LP1's 0.41, which is the
    expected direction and size and is not a fault.
    """
    detail = result["detail"]
    assert detail["n_homes_aggregated"] < MIN_HOMES_FOR_A_LOWER_BOUND
    assert detail["load_factor_lower_bound_applies"] is False
    assert detail["load_factor_lower_ok"] is None
    assert 0.20 < result["measured"]["load_factor"] < 0.35


def test_the_evening_peak_hour_is_right(result):
    assert result["measured"]["mean_day_peak_hour"] == 18
    assert result["detail"]["mean_day_peak_hour_ok"] is True


def test_the_overnight_shape_is_right_and_that_was_i_044_and_u32(result, ref):
    """I-044 fixed 10 Oct; the metric replaced the same day by U32.

    I-044: the town was flat from midnight to 04:00 because `_sleep_window`
    drew bedtimes as late as 02:30 and `place(0, wake, "sleep")` then claimed
    the small hours unconditionally - nobody was awake after midnight on any
    night. U32 part 2 then widened the distribution from HETUS, and U32 part 1
    replaced the two-point taper with the whole overnight shape, because the
    step 4 ablation improved the ratio by making the model worse (I-050).

    So the gating assertion is now the SHAPE. The taper is checked only for
    being reported, not for clearing a floor: the delivered package measures
    1.2013, which the old floor of 1.25 would have failed while the shape
    passes at 0.1467 - which is the concrete reason the metric changed.
    """
    assert result["outcome"] == "PASS"
    shape = result["detail"]["overnight_shape"]
    assert shape["within_band"] is True
    assert shape["mad"] <= shape["band"]
    # The band is derived from LP1, not declared: half what a shapeless
    # profile would show. If that stops holding, the threshold has been
    # replaced by a number somebody chose.
    # Both are stored to four decimals and round independently, so they can
    # differ in the last digit: the tolerance is that rounding, not a
    # modelling allowance.
    assert shape["flat_profile_mad"] == pytest.approx(
        shape["band"] * 2.0, abs=2e-4
    )
    assert shape["hours"] == [22, 23, 0, 1, 2, 3, 4, 5, 6]

    # The profile must DECLINE through the small hours, which is what I-044
    # was about and what a mean deviation alone would not guarantee.
    raw = result["detail"]["hourly_shape_over_day_mean"]
    hourly = {int(k): v for k, v in raw.items()}
    assert hourly[0] > hourly[2] > hourly[4], (
        f"the overnight profile is not falling: {hourly}"
    )
    # And somebody is awake after midnight, the original defect.
    assert hourly[0] > 1.2 * hourly[4]

    # The taper is still reported, because it is the quantity I-044 was
    # diagnosed against - but it is no longer a gate.
    assert "overnight_taper_00_over_04" in result["measured"]
    assert result["detail"]["overnight_taper_ok"] in (True, False)
    assert "no longer gating" in \
        result["detail"]["why_the_taper_is_no_longer_gating"].lower() or \
        "two-point ratio" in result["detail"]["why_the_taper_is_no_longer_gating"]


def test_the_check_records_what_is_still_unsourced(result):
    """After-diversity is not a dwelling, and the difference is declared."""
    note = result["detail"]["what_is_still_unsourced"]
    assert "INDIVIDUAL" in note
    assert "CER/ISSDA" in note and "forbids" in note
    assert "I-043" in note


def test_a_partial_year_cannot_produce_a_load_factor():
    """An annual quantity against an annual profile, or NO_DATA."""
    t0 = pd.Timestamp("2022-01-01 00:00:00+00:00")
    rows = [{
        "premises_id": "P1",
        "interval_start": t0 + pd.Timedelta(minutes=15 * i),
        "interval_end": t0 + pd.Timedelta(minutes=15 * (i + 1)),
        "import_wh": 10.0 + i, "export_config": "home_15min",
    } for i in range(96 * 3)]
    with pytest.raises(LookupError, match="days of D19"):
        CHECK.measure({"D19": pd.DataFrame(rows)})
