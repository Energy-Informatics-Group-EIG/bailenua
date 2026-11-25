"""U32 part 2: sleep timing from a time-use source (I-051).

The whole point of this module is that a declared guess was replaced by a
measurement, so the tests are mostly about the chain holding: the source is
read, the spread comes from it, the medians do not, and the two sources meet in
the right order of precedence.

Three errors were made building it and each has a test, because each would have
produced a plausible-looking distribution rather than an error:

* bedtime computed from the drawn wake, so it carried both spreads;
* a hard cap on workday waking, which piled 16.9% of workers onto one minute;
* non-workers given a later wake base, which dragged their bedtime with it.
"""

from __future__ import annotations

import numpy as np
import pytest

import baile_nua.sources_registry  # noqa: F401
from baile_nua.activity import sleep_timing as st
from baile_nua.activity.engine import (
    _LATEST_WORKDAY_WAKE,
    _WORKDAY_WAKE_SPREAD,
    ActivityEngine,
)
from baile_nua.engine.calendar import build_calendar
from baile_nua.engine.e1_run import build_slice
from baile_nua.population.synthesise import synthesise_t0
from baile_nua.rng import SeedTree, Stream
from baile_nua.sources import REGISTRY

SEED = 20261008
MINUTES = 1440


@pytest.fixture(scope="module")
def town():
    return synthesise_t0(master_seed=SEED)


@pytest.fixture(scope="module")
def windows(town):
    """Drawn (wake, bed) pairs across a week, with each person's status."""
    cal = build_calendar(2022)
    sl = build_slice(town, master_seed=SEED, calendar=cal,
                     slice_kind="u23_mixed_age")
    eng = ActivityEngine(SeedTree(SEED))
    rows = []
    for day in cal[20:27]:
        for hh, people in sorted(sl.households.items()):
            for p in people:
                gen = eng.tree.generator(
                    Stream.ACTIVITY_SEQUENCE, entity=p.person_id,
                    sim_day=day.sim_day,
                )
                wake, bed = eng._sleep_window(p, gen, is_workday=day.is_workday)
                rows.append({
                    "wake": wake, "bed": bed,
                    "structured": day.is_workday and (p.is_worker or p.is_student),
                })
    return rows


# --------------------------------------------------------------------------- #
# the chain to the source
# --------------------------------------------------------------------------- #

def test_the_curve_is_read_from_the_declared_source():
    src = REGISTRY[st.SOURCE_KEY]
    assert src.manifest_path.exists(), "the HETUS start-time source is unfetched"
    curve = st.asleep_share_curve()
    assert len(curve) >= 140, f"only {len(curve)} time bands"
    # A sleep curve has to look like one: high at 04:00, low at 15:00.
    assert curve[4 * 60] > 0.9
    assert curve[15 * 60] < 0.1


def test_the_parameters_carry_the_uk_transfer_flag_and_the_search():
    """U04's donor flag, and I-040's rule that a flag records a search."""
    assert st.EVIDENCE_TAG == "[A]"
    assert st.DONOR_GEO == "UK"
    for phrase in ("13,086", "Ireland is in neither HETUS wave", "DISPERSION"):
        assert phrase in st.SEARCH_RECORD, phrase
    assert REGISTRY[st.SOURCE_KEY].substitute_flag, (
        "the source itself should carry the UK-donor flag"
    )


def test_the_spread_comes_from_the_source_and_is_wide():
    """The defect was narrowness, not placement.

    The old form gave a 10-to-90 bedtime range near 106 minutes. The source
    implies about 187, with a tail past 02:50 - and without that tail nobody
    is ever awake at one in the morning, however the centre is placed.
    """
    offsets = st.bedtime_offsets()["offsets"]
    span = st.offset_at_quantile(offsets, 0.90) - st.offset_at_quantile(offsets, 0.10)
    assert 150 <= span <= 230, f"bedtime 10-90 span is {span:.0f} minutes"
    assert st.offset_at_quantile(offsets, 0.99) > 200, (
        "the right tail is gone, which is the thing that was wrong"
    )
    wake = st.waketime_offsets()["offsets"]
    assert st.offset_at_quantile(wake, 0.90) - st.offset_at_quantile(wake, 0.10) > 180


def test_chronotype_maps_monotonically_onto_quantiles():
    qs = [st.quantile_for_chronotype(c) for c in (-3, -2, -1, 0, 1, 2, 3)]
    assert qs == sorted(qs)
    assert st.quantile_for_chronotype(0.0) == pytest.approx(0.5)
    assert 0.0 < qs[0] < 0.1 and 0.9 < qs[-1] < 1.0


# --------------------------------------------------------------------------- #
# the three errors
# --------------------------------------------------------------------------- #

def test_bedtime_does_not_inherit_the_wake_spread(windows):
    """The first error: bedtime computed from the drawn wake carried both.

    Symptoms were a 10-to-90 range of 389 minutes against the source's 187, a
    median displaced from 22:46 to 23:34, and a tenth of the population pinned
    against the clip.
    """
    beds = np.array([r["bed"] for r in windows], dtype=float)
    span = float(np.percentile(beds, 90) - np.percentile(beds, 10))
    assert span < 300, (
        f"bedtime 10-90 span is {span:.0f} minutes; the source implies about "
        f"187 and double-counting gave 389"
    )
    pinned = float((beds >= 27 * 60 + 29).mean())
    assert pinned < 0.02, f"{pinned:.1%} of bedtimes are pinned at the clip"


def test_the_workday_wake_cap_damps_rather_than_truncates(windows):
    """The second error: a hard cap piled 16.9% of workers onto one minute."""
    assert 0.2 < _WORKDAY_WAKE_SPREAD < 1.0
    structured = np.array(
        [r["wake"] for r in windows if r["structured"]], dtype=float
    )
    assert structured.size > 50
    # A pile-up is mass on ONE minute, not mass above the cap: the damping
    # puts the 90th percentile at the cap by construction, so about a tenth of
    # workers rising later than it is the intended shape and not a spike. The
    # first version of this test measured the tail and failed on the design.
    counts = np.bincount(structured.astype(int))
    busiest = float(counts.max() / structured.size)
    assert busiest < 0.04, (
        f"{busiest:.1%} of workers wake at the single minute "
        f"{int(counts.argmax()) // 60:02d}:{int(counts.argmax()) % 60:02d}, "
        f"which is a spike and not a distribution - the hard cap put 16.9% "
        f"on one minute"
    )
    # And the distribution still reaches past the cap rather than stopping.
    assert structured.max() > _LATEST_WORKDAY_WAKE, (
        "no worker rises later than the cap, so it is still truncating"
    )


def test_the_irish_anchor_bounds_the_uk_spread():
    """Precedence: the commute is Irish, the dispersion is a UK donor.

    A model in which 1% of Cobh's workers wake at 12:40 would be using HETUS
    to overrule SAPS, which is backwards.
    """
    # The cap comes from the Census departure distribution, not a constant.
    assert 8 * 60 <= _LATEST_WORKDAY_WAKE <= 10 * 60, (
        f"the workday wake cap is "
        f"{_LATEST_WORKDAY_WAKE // 60:02d}:{_LATEST_WORKDAY_WAKE % 60:02d}, "
        f"which is not a plausible latest rising time for somebody with a job"
    )
    # And it is derived: the 95th-percentile band's START, less a margin.
    from baile_nua.activity.engine import (
        _GETTING_READY_MARGIN_MIN,
        _latest_workday_wake,
    )
    assert _latest_workday_wake() == _LATEST_WORKDAY_WAKE
    assert _GETTING_READY_MARGIN_MIN > 0


def test_a_non_worker_wakes_later_without_going_to_bed_later(town):
    """The third error: a later wake base dragged the bedtime with it.

    Fixing the morning broke the evening - 23:00 went to +0.227 against HETUS -
    because bedtime was derived from each person's own wake base. Waking later
    means sleeping LONGER, which is what the source implies anyway: its median
    bed-to-wake gap is about nine and a half hours against the design's 8.4.
    """
    cal = build_calendar(2022)
    sl = build_slice(town, master_seed=SEED, calendar=cal,
                     slice_kind="u23_mixed_age")
    eng = ActivityEngine(SeedTree(SEED))
    workday = next(d for d in cal[20:27] if d.is_workday)
    beds = {"worker": [], "non_worker": []}
    wakes = {"worker": [], "non_worker": []}
    for hh, people in sorted(sl.households.items()):
        for p in people:
            gen = eng.tree.generator(
                Stream.ACTIVITY_SEQUENCE, entity=p.person_id,
                sim_day=workday.sim_day,
            )
            wake, bed = eng._sleep_window(p, gen, is_workday=True)
            key = "worker" if (p.is_worker or p.is_student) else "non_worker"
            beds[key].append(bed)
            wakes[key].append(wake)
    for key in ("worker", "non_worker"):
        assert len(beds[key]) > 20, key
    # Non-workers wake later...
    assert np.median(wakes["non_worker"]) > np.median(wakes["worker"]) + 30
    # ...and do NOT go to bed correspondingly later.
    bed_gap = float(np.median(beds["non_worker"]) - np.median(beds["worker"]))
    assert abs(bed_gap) < 20, (
        f"non-workers' median bedtime differs by {bed_gap:+.0f} minutes from "
        f"workers'; bedtime should be anchored independently of the wake base"
    )


# --------------------------------------------------------------------------- #
# the validation against the source
# --------------------------------------------------------------------------- #

def test_the_awake_share_reference_is_a_plausible_curve():
    ref = st.awake_share_reference()
    assert ref[3] < 0.02, "almost nobody is awake at 03:00"
    assert ref[13] > 0.9, "almost everybody is awake at 13:00"
    assert ref[0] > ref[1] > ref[2], "the small hours should still be falling"
    assert 0.05 < ref[0] < 0.20


def test_the_model_matches_the_awake_share_curve(town):
    """The first validation, before any energy metric: it is the source.

    An overnight load shape that matched LP1 while this did not would mean the
    model had the right electricity for the wrong reason.
    """
    cal = build_calendar(2022)
    sl = build_slice(town, master_seed=SEED, calendar=cal,
                     slice_kind="u23_mixed_age")
    eng = ActivityEngine(SeedTree(SEED))
    awake = np.zeros(MINUTES)
    n = 0
    for day in cal[20:27]:
        for hh, people in sorted(sl.households.items()):
            hd = eng.generate_household_day(
                hh, people, sim_day=day.sim_day, is_workday=day.is_workday,
                is_school_day=day.is_school_day, season=day.season,
                was_workday=cal[day.sim_day - 1].is_workday,
            )
            for pd_ in hd.person_days.values():
                n += 1
                for iv in pd_.intervals:
                    if iv.activity not in ("sleep", "nap"):
                        awake[iv.start_min:iv.end_min] += 1
    awake /= max(n, 1)
    fit = st.awake_share_fit(
        {h: float(awake[h * 60:(h + 1) * 60].mean()) for h in range(24)}
    )
    assert fit["mad"] < 0.05, (
        f"awake-share MAD against HETUS is {fit['mad']:.4f}; it measured "
        f"0.0283 when U32 was done, and 0.0621 before the fixes"
    )
    # The small hours are the thing that was broken, so they are pinned tighter.
    for hour in (1, 2, 3, 4):
        assert abs(fit["deviation_by_hour"][hour]) < 0.03, (
            f"{hour:02d}:00 deviates by "
            f"{fit['deviation_by_hour'][hour]:+.3f}"
        )
    # And somebody is awake after midnight, which was the original defect.
    assert fit["model"][0] > 0.02
