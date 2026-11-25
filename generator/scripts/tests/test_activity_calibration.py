"""Tests for the activity-to-HETUS mapping and the episode structure.

Every test here exists because something was wrong and the suite did not
notice.  162 tests passed while ``laundry`` drew its target from Eurostat's
handicraft code and the engine emitted 45 activity episodes per person-day.
The lesson is specific: the old tests checked that totals matched HETUS, and
both faults were invisible in a total.  A wrong code still yields *a* number,
and fragmenting a correct total into slivers does not change it.
"""

from __future__ import annotations

import numpy as np
import pytest

import baile_nua.sources_registry  # noqa: F401  (declares the sources)
from baile_nua.activity.engine import (
    DURATION_BOUNDS,
    ActivityEngine,
    PersonProfile,
)
from baile_nua.activity.hetus import ACTIVITY_CODES, acl00_labels, hetus_time_spent, mapping_audit
from baile_nua.rng import SeedTree

#: For each modelled activity, a word that MUST appear in the official label of
#: at least one HETUS code it draws on.
#:
#: This is the test that catches a mis-assigned code, and it is written from the
#: ACTIVITY NAME rather than from the mapping, so it is an independent
#: statement of intent rather than a restatement of the table.  Every one of the
#: six faults in I-029 fails it: AC33A's label is "Handicraft and producing
#: textiles and other care for textiles", which does not contain "laundry".
REQUIRED_WORD: dict[str, tuple[str, ...]] = {
    "sleep": ("sleep",),
    "nap": ("sleep",),
    "personal_care": ("personal care",),
    "shower_bath": ("personal care",),
    "dressing": ("personal care",),
    "cooking": ("food",),
    "washing_up": ("dish",),
    "eating_main": ("eating",),
    "eating_snack": ("eating",),
    "laundry": ("laundry", "ironing"),
    "cleaning": ("cleaning", "upkeep"),
    "diy_repairs": ("repair", "construction"),
    "gardening": ("garden",),
    "childcare": ("child",),
    "adult_care": ("family member", "help"),
    "work_at_workplace": ("employment", "job"),
    "work_at_home": ("employment", "job"),
    "school": ("school", "university"),
    "study_at_home": ("homework", "study"),
    "tv_screens": ("television",),
    "reading": ("reading",),
    "hobbies": ("hobbies", "computing", "games", "radio"),
    "social_at_home": ("visiting", "feasts"),
    "social_out": ("social",),
    "sport_exercise": ("sport", "walking"),
    "shopping": ("shopping",),
    "religion_civic": ("organisational", "participatory", "entertainment"),
    "travel_commute": ("travel",),
    "travel_other": ("travel",),
    "idle_at_home": ("resting",),
}


def test_every_hetus_code_exists_in_the_official_codelist():
    """mapping_audit raises on an unknown code; this pins the behaviour."""
    rows = mapping_audit()
    assert rows, "the audit returned nothing"
    assert all(r["official_label"] for r in rows)


def test_every_activity_maps_to_a_code_whose_label_matches_its_name():
    """The independent check on the mapping (I-029).

    Fails loudly and names the activity, the code and the label, because the
    useful part of this test is the message: "laundry -> AC33A (Handicraft...)"
    is the whole diagnosis.
    """
    labels = acl00_labels()
    missing = set(ACTIVITY_CODES) - set(REQUIRED_WORD)
    assert not missing, (
        f"these activities have no expected label word declared: {sorted(missing)}. "
        f"A new activity must declare what its HETUS code should MEAN, or this "
        f"test silently stops covering it."
    )
    bad: list[str] = []
    for activity, spec in sorted(ACTIVITY_CODES.items()):
        words = REQUIRED_WORD[activity]
        # Only codes that CONTRIBUTE (positive weight) have to match: travel_other
        # subtracts AC913, and a subtracted code is not what the activity is.
        texts = [
            labels[code].lower()
            for code, weight in spec["hetus"] if float(weight) > 0
        ]
        if not any(w in t for w in words for t in texts):
            codes = [c for c, w in spec["hetus"] if float(w) > 0]
            bad.append(
                f"{activity} -> {codes} labelled {texts}, none containing any of {words}"
            )
    assert not bad, "HETUS code mis-assigned:\n  " + "\n  ".join(bad)


#: HETUS leaves that are deliberately NOT modelled, with their reason.
#:
#: Named individually so the partition test can be exact rather than tolerant.
#: A tolerance wide enough to swallow an unmodelled 20 minutes is also wide
#: enough to swallow a double-counted 20 minutes, and those are opposite faults.
UNMODELLED_LEAVES: dict[str, str] = {
    "AC33A": "handicraft and producing textiles: no load signature and no "
             "bearing on occupancy",
    "AC342": "tending domestic animals: Cobh is a town, and SAPS gives no "
             "livestock keeping in the urban small areas",
    "AC343": "caring for pets: indoor, no distinct load, folded into whatever "
             "the person is otherwise doing",
    "AC344": "walking the dog: an out-of-home absence, but HETUS gives it 7 "
             "minutes a day against sport_exercise's 19 - modelling it "
             "separately would add an activity state without adding a "
             "distinguishable occupancy pattern",
    "AC42": "informal help to other households: an absence from home, like "
            "social_out, but with no separate load or trip pattern in E1",
}


def test_the_mapping_partitions_the_day_without_double_counting():
    """Mapped codes plus the named unmodelled leaves must be the whole day.

    HETUS's six top-level codes sum to exactly 1,440 minutes - verified here on
    three different (sex, age) groups, not assumed - and every code the engine
    maps is a leaf beneath one of them.  So the mapped leaves plus the leaves
    deliberately left out must reconstruct the day to within integer-minute
    rounding.

    This is the test that distinguishes "a code is missing" from "two codes
    overlap", which no per-activity total can: a parent mapped alongside its own
    child inflates the sum, and a missing leaf deflates it, and both leave every
    individual target looking reasonable.

    The first version of this test was itself wrong: it treated AC99NSP and
    AC90NSP as additions to the day when they sit INSIDE the aggregates, and so
    it reported a 38-minute excess where there was none.
    """
    ts = hetus_time_spent()
    top = ["AC0", "AC1_TR", "AC2", "AC3", "AC4-8", "AC9A"]
    for sex, age in [("T", "TOTAL"), ("F", "Y25-44"), ("M", "Y45-64")]:
        tot = {
            r.acl00: r.minutes
            for r in ts[(ts.sex == sex) & (ts.age == age)].itertuples()
        }
        day = sum(float(tot.get(c, 0.0)) for c in top)
        assert abs(day - 1440.0) <= 2.0, (
            f"{sex}/{age}: the six top-level HETUS codes sum to {day:.0f}, not "
            f"1,440. Either a code has been misread or AC9A is not the whole of "
            f"travel, and every target below depends on which."
        )

        # nap is a declared share of sleep and would double-count; the three
        # split codes are exhaustive within themselves, so add them whole.
        mapped = 0.0
        for a, spec in ACTIVITY_CODES.items():
            if a == "nap":
                continue
            for code, weight in spec["hetus"]:
                if abs(float(weight)) == 1.0:
                    mapped += float(weight) * float(tot.get(code, 0.0))
        for code in ("AC02", "AC03", "AC1_TR"):
            mapped += float(tot.get(code, 0.0))
        left_out = sum(float(tot.get(c, 0.0)) for c in UNMODELLED_LEAVES)

        assert abs(mapped + left_out - day) <= 6.0, (
            f"{sex}/{age}: mapped leaves {mapped:.0f} + deliberately "
            f"unmodelled {left_out:.0f} = {mapped + left_out:.0f}, but the day "
            f"is {day:.0f}. A shortfall means a leaf is unmapped and "
            f"undeclared; an excess means a parent is mapped alongside its own "
            f"child."
        )


def test_unmodelled_leaves_are_small_and_declared():
    """What is left out must be both named and minor."""
    ts = hetus_time_spent()
    tot = {
        r.acl00: r.minutes
        for r in ts[(ts.sex == "T") & (ts.age == "TOTAL")].itertuples()
    }
    left_out = sum(float(tot.get(c, 0.0)) for c in UNMODELLED_LEAVES)
    assert left_out <= 45.0, (
        f"{left_out:.0f} minutes a day are left unmodelled. Past about 45 "
        f"minutes the omission starts to matter for occupancy, and the leaf "
        f"needs an activity state rather than an entry in a dictionary."
    )
    assert all(len(v) > 20 for v in UNMODELLED_LEAVES.values()), (
        "every unmodelled leaf needs a real reason, not a placeholder"
    )


def _sample_person_days(n_days: int = 2):
    tree = SeedTree(20261008)
    eng = ActivityEngine(tree)
    people = [
        PersonProfile(person_id="P-0001", age=42, sex="F", role="spouse",
                      econ_status="employed", work_pattern="full-time day",
                      remote_share=0.0, chronotype=0.1, habit_strength=0.5,
                      lapse_rate=0.1, attention=0.5, comfort=0.0),
        PersonProfile(person_id="P-0002", age=45, sex="M", role="head",
                      econ_status="employed", work_pattern="full-time day",
                      remote_share=0.3, chronotype=-0.2, habit_strength=0.6,
                      lapse_rate=0.1, attention=0.4, comfort=0.2),
        PersonProfile(person_id="P-0003", age=11, sex="M", role="child",
                      econ_status="student", work_pattern="none",
                      remote_share=0.0, chronotype=0.0, habit_strength=0.4,
                      lapse_rate=0.2, attention=0.3, comfort=0.0,
                      school_year=7),
        PersonProfile(person_id="P-0004", age=71, sex="F", role="other",
                      econ_status="retired", work_pattern="none",
                      remote_share=0.0, chronotype=-0.4, habit_strength=0.8,
                      lapse_rate=0.05, attention=0.6, comfort=0.5),
    ]
    out = []
    for day in range(n_days):
        hd = eng.generate_household_day(
            "H-000001", people, sim_day=day, is_workday=(day % 7 < 5),
            is_school_day=(day % 7 < 5), season="winter",
            disruptions={p.person_id: [] for p in people},
        )
        out.extend(hd.person_days.values())
    return out


def test_episodes_per_person_day_is_diary_plausible():
    """Episode COUNT, not just total minutes (I-028).

    A time-use diary records roughly 20 to 30 distinct activity episodes per
    person-day.  The engine emitted 45, because an activity whose budget had two
    minutes left in it was placed as a two-minute episode.  Total minutes were
    unaffected, so every existing test passed.
    """
    days = _sample_person_days()
    counts = [len(d.intervals) for d in days]
    mean = float(np.mean(counts))
    assert 18.0 <= mean <= 34.0, (
        f"{mean:.1f} activity episodes per person-day. A real diary records "
        f"about 20 to 30. Above that the day is fragmented into slivers; below "
        f"it, the day is too coarse to drive appliances."
    )


def test_almost_no_episode_is_shorter_than_its_declared_floor():
    """DURATION_BOUNDS declares a floor per activity; it must be respected.

    Exempt: the last episode of the day, which the 1,440-minute boundary can
    truncate, and sleep, whose floor describes a night rather than the tail of
    one.
    """
    days = _sample_person_days()
    violations = []
    for d in days:
        for iv in d.intervals:
            if iv.end_min >= 1440 or iv.activity == "sleep":
                continue
            lo = DURATION_BOUNDS.get(iv.activity, (5, 240))[0]
            if iv.duration_min < lo:
                violations.append(
                    f"{iv.activity} {iv.duration_min}min < floor {lo} "
                    f"at {iv.start_min}"
                )
    total = sum(len(d.intervals) for d in days)
    rate = len(violations) / max(total, 1)
    assert rate <= 0.05, (
        f"{rate:.1%} of episodes are shorter than their declared floor "
        f"({len(violations)} of {total}). Examples: {violations[:5]}"
    )


def test_low_frequency_activities_still_happen():
    """An activity whose daily target is below its episode floor must occur.

    The episode floor, applied naively, excluded every such activity from
    contention for ever: no washing machine in the estate ran, because laundry
    could never be selected. The occurrence-probability path is what fixes it,
    and this is the test that it is still there.
    """
    days = _sample_person_days(n_days=14)
    seen = {iv.activity for d in days for iv in d.intervals}
    low_frequency = {"laundry", "cleaning", "sport_exercise", "hobbies"}
    missing = low_frequency - seen
    assert not missing, (
        f"over {len(days)} person-days, these never happened at all: "
        f"{sorted(missing)}. A daily target below one episode's minimum length "
        f"means a full episode on some days, not nothing on every day."
    )
