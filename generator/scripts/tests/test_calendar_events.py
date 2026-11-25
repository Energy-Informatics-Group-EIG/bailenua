"""WP6: the event engine, R20's coverage audit and K09's shared drivers.

R20's acceptance test is that every D14 event class is present **with a
source**. That is two claims, and the interesting failure is the second: a
class can look covered because rows exist for it while nothing at all backs
the rate those rows were drawn from. So the audit separates "absent from the
generated year" from "present but unsourced", and both fail.

K09's lesson sets the other half. Validating every *pair* of ten event kinds
is combinatorially hopeless, so design 5.10 validates by class and by shared
driver - which only works if the driver is recorded and honest. A storm and an
outage that were drawn independently and happen to coincide would look exactly
like a storm that caused an outage, and a model that learned the real
correlation would be penalised for being right.
"""

from __future__ import annotations

import pandas as pd
import pytest

import baile_nua.sources_registry  # noqa: F401
from baile_nua.engine import calendar_events as E
from baile_nua.engine.calendar import OUT_OF_SCOPE_AT_E1

SEED = 20251010

#: Nine storm days, standing in for the weather realisation's output.
STORMS = [
    pd.Timestamp(f"2022-{m:02d}-{d:02d}")
    for m, d in ((1, 5), (1, 18), (2, 7), (2, 18), (2, 21), (3, 2),
                 (10, 30), (11, 14), (12, 9))
]


@pytest.fixture(scope="module")
def events():
    return E.build_events(year=2022, master_seed=SEED, storm_days=STORMS)


# --------------------------------------------------------------------------- #
# R20
# --------------------------------------------------------------------------- #

def test_every_d14_event_kind_is_generated(events):
    audit = E.coverage_audit(events)
    assert not audit["missing_from_the_year"], audit["missing_from_the_year"]
    assert audit["n_kinds"] == 10


def test_every_generated_kind_has_a_source_or_a_declared_flag(events):
    """The failure R20 actually names: rows exist and nothing backs them."""
    audit = E.coverage_audit(events)
    assert not audit["present_but_unsourced"], audit["present_but_unsourced"]
    assert audit["passes_r20"]
    # And the split is reported, because "covered" at three sourced, two legal
    # and six assumed is a different claim from "covered" at ten sourced.
    assert audit["n_sourced"] >= 3
    assert audit["n_legal"] >= 2


def test_the_assumed_kinds_carry_a_search_record():
    """I-040 again: an [A] class records what was searched."""
    flagged = {
        s.assumption_flag for s in E.EVENT_SOURCES.values() if s.assumption_flag
    }
    assert flagged, "no event class is flagged, which cannot be right"
    assert E.EVENT_SEARCH_RECORD
    terms = {t for t, _n, _v in E.EVENT_SEARCH_RECORD}
    assert len(terms) == len(E.EVENT_SEARCH_RECORD), "a term is recorded twice"
    for key, spec in E.ASSUMED_EVENT_RATES.items():
        assert spec["flag"], key
        assert len(spec["note"]) > 30, key


def test_the_zero_hit_event_searches_still_return_zero():
    """If the CSO publishes one of these, the record is stale."""
    from baile_nua.validation.assumption_sweep import load_catalogue, search

    cat = load_catalogue()
    zeros = [(t, v) for t, n, v in E.EVENT_SEARCH_RECORD if n == 0]
    assert zeros
    for term, verdict in zeros:
        hits = search(term, cat)
        assert not hits, (
            f"{term!r} is recorded as ZERO ({verdict}) but returns "
            f"{len(hits)}: {[h.matrix for h in hits][:5]}"
        )


def test_the_sport_substring_collision_is_real():
    """The clearest case in the sweep that a hit count is not evidence."""
    from baile_nua.validation.assumption_sweep import load_catalogue, search

    hits = search(r"[Ss]port", load_catalogue())
    assert len(hits) > 100, len(hits)
    # Every one of the first several is a TRANSPORT table, not a fixture list.
    assert any("Transport" in h.title or "transport" in h.title for h in hits)


def test_wp6_closes_the_e1_out_of_scope_list():
    """calendar.py named what E1 did not do; WP6 has to actually do it."""
    kinds = set(E.EVENT_KINDS)
    # Each out-of-scope entry maps onto at least one kind now generated.
    assert {"festival", "market", "cruise day", "sport", "roadworks"} <= kinds
    assert len(OUT_OF_SCOPE_AT_E1) >= 5          # the list it closes
    # Phases were on that list too.
    assert set(E.EVENT_PHASES) == {
        "preparation", "main", "recovery", "rebound"
    }


# --------------------------------------------------------------------------- #
# K09 and 5.10
# --------------------------------------------------------------------------- #

def test_every_event_names_a_driver_that_really_generates_it(events):
    audit = E.driver_audit(events)
    assert audit["clean"], audit["violations"][:10]
    assert set(audit["by_driver"]) <= set(E.SHARED_DRIVERS)
    assert len(audit["by_driver"]) == len(E.SHARED_DRIVERS), (
        f"only {sorted(audit['by_driver'])} of "
        f"{sorted(E.SHARED_DRIVERS)} drivers produced anything"
    )


def test_outages_only_happen_on_storm_days(events):
    """The shared driver, demonstrated rather than asserted.

    An outage drawn independently of the weather would put the lights out on a
    calm day, and then a model that learned the real storm-outage correlation
    would be marked wrong for learning it.
    """
    storm_days = {s.normalize() for s in STORMS}
    outages = [e for e in events if e.event_kind == "outage" and e.phase == "main"]
    assert outages, "no outage was generated at all"
    for o in outages:
        assert o.start.normalize() in storm_days, (
            f"outage {o.instance_id} on {o.start.date()}, which is not a "
            f"storm day - the shared driver has been bypassed"
        )


def test_no_sport_fixture_survives_a_storm_day(events):
    """The other half of the same driver: a storm cancels the fixture."""
    storm_days = {s.normalize() for s in STORMS}
    for e in events:
        if e.event_kind == "sport" and e.phase == "main":
            assert e.start.normalize() not in storm_days, e.instance_id


def test_markets_and_festivals_only_happen_on_cruise_days(events):
    """The cruise driver carries TBA11's sourced seasonality to both."""
    cruise = {
        e.start.normalize() for e in events
        if e.event_kind == "cruise day" and e.phase == "main"
    }
    for kind in ("market", "festival"):
        rows = [e for e in events if e.event_kind == kind and e.phase == "main"]
        assert rows, kind
        for e in rows:
            assert e.start.normalize() in cruise, (
                f"{e.instance_id} is not on a cruise day, so its timing does "
                f"not inherit TBA11's seasonality and is simply invented"
            )


def test_roadworks_are_scheduled_into_school_holidays(events):
    """Also a shared driver: the institutional year schedules both."""
    terms = [
        (e.start.normalize(), e.end.normalize()) for e in events
        if e.event_kind == "school term" and e.phase == "main"
    ]
    assert terms
    rw = [e for e in events if e.event_kind == "roadworks" and e.phase == "main"]
    assert rw
    in_term = 0
    for e in rw:
        if any(a <= e.start.normalize() <= b for a, b in terms):
            in_term += 1
    assert in_term <= 1, (
        f"{in_term} of {len(rw)} roadworks spells start inside a school term; "
        f"the institutional-year driver is supposed to place them in the gaps"
    )


def test_the_coincidence_report_excludes_state_kinds(events):
    """A six-week term overlapping a fixture is a Saturday, not a coincidence."""
    rep = E.coincidence_report(events)
    assert rep["state_kinds_excluded"] == ["roadworks", "school term"]
    for ex in rep["unexplained_examples"]:
        assert not (set(ex["kinds"]) & set(E.STATE_KINDS)), ex
    # Most coincidences should be explained; a calendar where none were would
    # mean the drivers are not actually driving anything.
    assert rep["explained_share"] is None or rep["explained_share"] > 0.5, rep


# --------------------------------------------------------------------------- #
# the sourced quantities
# --------------------------------------------------------------------------- #

def test_cruise_calls_come_from_tba10_and_the_year_is_not_silently_swapped():
    """2020 and 2021 are absent from TBA10; a silent fallback would hide that."""
    c = E.cruise_calls_cork(2022)
    assert c["year_used"] == 2022 and not c["substituted"]
    assert c["calls"] == 81
    assert c["passengers"] == 115062
    assert 1000 < c["passengers_per_call"] < 2500
    # The pandemic years really are missing, and the substitution is reported.
    gap = E.cruise_calls_cork(2020)
    assert gap["substituted"] is True
    assert gap["year_used"] != 2020
    assert 2020 not in gap["published_years"]


def test_the_cruise_season_is_the_published_one():
    """TBA11: no calls in deep winter, a peak in August."""
    sh = E.cruise_month_shares()
    assert abs(sum(sh.values()) - 1.0) < 1e-9
    for m in (1, 2, 11, 12):
        assert sh[m] == 0.0, f"month {m} has cruise calls, which TBA11 denies"
    assert max(sh, key=lambda k: sh[k]) == 8, sh
    assert sum(sh[m] for m in (5, 6, 7, 8, 9)) > 0.85, sh


def test_the_generated_cruise_days_follow_the_published_seasonality(events):
    """The source has to reach the output, not just the module."""
    days = [
        e.start for e in events
        if e.event_kind == "cruise day" and e.phase == "main"
    ]
    assert len(days) == E.cruise_calls_cork(2022)["calls"]
    for d in days:
        assert d.month not in (1, 2, 11, 12), (
            f"a cruise call was generated in {d.strftime('%B')}, which TBA11 "
            f"says never happens"
        )


def test_the_school_absence_floor_is_derived_from_sca42():
    """And the assumed daily rate has to sit above it."""
    floor = E.school_absence_floor()
    assert 0.0 < floor < 0.10
    assumed = float(E.ASSUMED_EVENT_RATES["school_day_absence"]["value"])
    assert assumed > floor, (
        f"the assumed daily absence rate {assumed} is below the floor "
        f"{floor:.4f} that SCA42's chronic absence alone implies"
    )


def test_dst_is_computed_from_the_rule_not_transcribed():
    """Directive 2000/84/EC is a rule, so it should be right for any year."""
    for year, march, october in (
        (2022, 27, 30), (2023, 26, 29), (2024, 31, 27), (2025, 30, 26),
    ):
        tr = E._dst_transitions(year)
        assert [t.day for t, _ in tr] == [march, october], (year, tr)
        for ts, _name in tr:
            assert ts.dayofweek == 6, ts        # always a Sunday
            # And always the LAST Sunday: a week later is the next month.
            assert (ts + pd.Timedelta(days=7)).month != ts.month


# --------------------------------------------------------------------------- #
# schema conformance and determinism
# --------------------------------------------------------------------------- #

def test_every_row_satisfies_the_d14_enums(events):
    for e in events:
        assert e.event_kind in E.EVENT_KINDS, e.instance_id
        assert e.event_class in E.EVENT_CLASSES, e.instance_id
        assert e.phase in E.EVENT_PHASES, e.instance_id
        assert e.footprint in E.EVENT_FOOTPRINTS, e.instance_id
        assert e.source_ref, e.instance_id
        assert e.end >= e.start, e.instance_id
        if e.footprint in ("street", "estate"):
            assert e.footprint_ids, (
                f"{e.instance_id} has a {e.footprint} footprint and names no "
                f"ids, so nothing can tell which street or estate it hit"
            )


def test_instance_ids_are_unique(events):
    ids = [e.instance_id for e in events]
    assert len(ids) == len(set(ids))


def test_every_main_event_has_the_phases_its_kind_declares(events):
    stems = {}
    for e in events:
        stem, _, phase = e.instance_id.rpartition("-")
        stems.setdefault(stem, set()).add(phase)
    for stem, phases in stems.items():
        assert "main" in phases, stem
    # At least one kind must actually produce each phase, or PHASE_PLAN is
    # declaring tails that never appear.
    produced = {e.phase for e in events}
    assert produced == set(E.EVENT_PHASES), produced


def test_the_event_year_is_reproducible():
    a = E.build_events(year=2022, master_seed=SEED, storm_days=STORMS)
    b = E.build_events(year=2022, master_seed=SEED, storm_days=STORMS)
    assert [x.instance_id for x in a] == [x.instance_id for x in b]
    assert [x.start for x in a] == [x.start for x in b]
    c = E.build_events(year=2022, master_seed=SEED + 1, storm_days=STORMS)
    assert [x.instance_id for x in a] != [x.instance_id for x in c], (
        "a different seed produced an identical calendar, so the seed is "
        "not reaching the draws"
    )


def test_storms_come_from_the_weather_and_not_from_a_draw():
    """Design 6.5 rule 2: a storm day coincides with the wind that caused it."""
    few = E.build_events(year=2022, master_seed=SEED, storm_days=STORMS[:2])
    storm_rows = [
        e for e in few if e.event_kind == "storm" and e.phase == "main"
    ]
    assert len(storm_rows) == 2, len(storm_rows)
    assert {e.start.normalize() for e in storm_rows} == {
        s.normalize() for s in STORMS[:2]
    }
    none = E.build_events(year=2022, master_seed=SEED, storm_days=[])
    assert not [e for e in none if e.event_kind == "storm"]
    # And with no storms there are no outages either, because the outage is
    # generated from the storm rather than alongside it.
    assert not [e for e in none if e.event_kind == "outage"]
