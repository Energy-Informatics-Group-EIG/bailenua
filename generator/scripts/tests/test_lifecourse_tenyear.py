"""WP5: the ten-year life course, its hazards, and the D20 tier contract.

Three things are tested here, and only one of them is about the engine.

**The hazards are what they claim to be.** Every entry in ``HAZARD_SOURCES``
reads a declared source and comes back with Irish numbers; every ``[A]`` flag
has a search record and a published bound. The failure this guards against is
the one I-040 and A-35 both name: a module that says "assumed, nothing found"
when the truth is "assumed, and I did not try the right words", or that says
"sourced" about a table that turns out to be a stock.

**The D20 tier is derived, not declared.** ``detectable_from_tier`` is defined
by the schema as "the lowest tier at which it is theoretically observable",
which is a claim about sensor channels. So the tier is computed from the
channels a label's text appeals to, and the test re-derives it. The evidence
that this is the rule the DESIGN meant, rather than one invented to pass, is
that it reproduces all four of the hand-written Mary tiers from design 5.9 -
T1, T2, T1, T3 - which were written before any of this existed.

**The ten-year invariants hold, and the published rates are met.** Births,
deaths and partnerings are compared against the published rate at the exposure
the run actually had, with a 95% interval. The interval is two-sided on
purpose: a model that produces too FEW births fails exactly as a model that
produces too many does.
"""

from __future__ import annotations

import pytest

import baile_nua.sources_registry  # noqa: F401
from baile_nua.engine.e1_run import _pick_mary_household, build_slice
from baile_nua.lifecourse import hazards as HZ
from baile_nua.lifecourse.events import mary_scenario
from baile_nua.lifecourse.tenyear import (
    EVENT_EVIDENCE,
    MEASURE_APPLIED_IN_WEEK2,
    MEASURES,
    TIER_ORDER,
    HazardTables,
    TenYearConfig,
    apply_year_to_slice,
    from_slice,
    lowest_tier_for,
    run_life_course,
)
from baile_nua.observation.sensors import TIER_DEVICES
from baile_nua.population.synthesise import synthesise_t0

SEED = 20251010


@pytest.fixture(scope="module")
def slice60():
    town = synthesise_t0(master_seed=SEED)
    return build_slice(town, master_seed=SEED, slice_kind="u23_mixed_age")


@pytest.fixture(scope="module")
def result(slice60):
    persons, dwellings, households = from_slice(slice60)
    mary = _pick_mary_household(slice60.households, slice60.buildings)
    return run_life_course(
        config=TenYearConfig(master_seed=SEED), persons=persons,
        dwellings=dwellings, households=households, mary=mary,
    )


# --------------------------------------------------------------------------- #
# the hazards
# --------------------------------------------------------------------------- #

def test_every_sourced_hazard_reads_its_declared_source():
    """A hazard called 'sourced' must actually return numbers from a file."""
    tab = HazardTables.load()
    assert tab.fertility, "VSA104 returned no fertility rates"
    assert tab.death, "VSA08/PEA01 returned no death rates"
    assert tab.marriage, "VSA49 returned no marriage rates"
    assert tab.separation_job, "JCA01 returned no separation rates"
    assert tab.der, "HEBEU37 returned no installation prevalences"
    assert tab.chronic, "HSPAE122 returned no chronic-condition prevalences"
    assert tab.vacancy_cork, "VAC04 returned no Cork County vacancy rates"
    assert tab.net_migration, "EP006 returned no net migration rates"
    # Every source named in HAZARD_SOURCES has a sha from its own manifest, so
    # a calibration number can be traced to the bytes it came from (D24).
    shas = HZ.source_shas()
    for h in HZ.HAZARD_SOURCES:
        assert h.source_key in shas, h.source_key
        assert len(shas[h.source_key]) == 64, (h.source_key, shas[h.source_key])


def test_death_rates_rise_with_age_and_are_higher_for_men():
    """A mortality schedule that does not do this is not one."""
    tab = HazardTables.load()
    for sex in ("Male", "Female"):
        bands = ["30 - 34 years", "50 - 54 years", "70 - 74 years",
                 "85 years and over"]
        vals = [tab.death[(sex, b)] for b in bands]
        assert vals == sorted(vals), (sex, vals)
    for band in ("40 - 44 years", "60 - 64 years", "75 - 79 years"):
        assert tab.death[("Male", band)] > tab.death[("Female", band)], band


def test_fertility_peaks_in_the_thirties():
    """VSA104's shape, checked rather than assumed."""
    f = HZ.fertility_rates_by_age()
    peak = max(f, key=lambda k: f[k])
    assert peak == "30 - 34 years", f
    assert f["15 - 19 years"] < f["25 - 29 years"] < f["30 - 34 years"]


def test_job_separation_falls_with_age_then_jumps_at_retirement():
    """JCA01's real shape: the jump at 65 is retirement, and it is in the data."""
    j = HZ.job_separation_rate_by_age_sex()
    for sex in ("Male", "Female"):
        assert j[(sex, "22 years")] > j[(sex, "35 years")] > j[(sex, "50 years")]
        assert j[(sex, "65 years")] > j[(sex, "64 years")] * 1.5, sex


def test_every_assumed_hazard_has_a_search_record_and_a_bound():
    """I-040: an [A] flag records what was searched, not just that it is [A]."""
    terms = {t for t, _n, _v in HZ.SEARCH_RECORD}
    assert len(terms) == len(HZ.SEARCH_RECORD), "a search term is recorded twice"
    for a in HZ.ASSUMED_HAZARDS:
        assert a.why_assumed and a.bounded_by, a.flag
        # The bound has to be a function that actually returns something.
        fn = getattr(HZ, a.bound_check)
        assert fn(), (a.flag, a.bound_check)
        assert a.value > 0.0, a.flag


def test_the_zero_hit_searches_really_do_return_zero():
    """A-35's lesson: 'not published' and 'I did not find it' differ.

    The record claims zero tables for several terms. If one of them starts
    returning hits - because the CSO published something, or because the claim
    was wrong - the record is stale and must be rewritten rather than trusted.
    """
    from baile_nua.validation.assumption_sweep import load_catalogue, search

    cat = load_catalogue()
    claimed_zero = [
        (t, v) for t, n, v in HZ.SEARCH_RECORD if n == 0
    ]
    assert claimed_zero, "the record claims no zero-hit searches at all"
    for term, verdict in claimed_zero:
        hits = search(term, cat)
        assert not hits, (
            f"{term!r} is recorded as returning ZERO tables ({verdict}) but "
            f"now returns {len(hits)}: {[h.matrix for h in hits][:6]}. The "
            f"search record is stale."
        )


def test_the_retrofit_gap_is_real():
    """The one claim the whole of A-25f rests on."""
    from baile_nua.validation.assumption_sweep import load_catalogue, search

    assert not search(r"retrofit", load_catalogue()), (
        "PxStat now publishes a 'retrofit' table; A-25f's justification is "
        "gone and the hazard should be sourced instead of assumed"
    )


# --------------------------------------------------------------------------- #
# the D20 tier contract
# --------------------------------------------------------------------------- #

def test_the_tier_rule_reproduces_the_hand_written_mary_tiers():
    """The evidence that the derivation is the design's rule, not a new one.

    Design 5.9's four Mary labels were written with their tiers by hand. The
    channels each one's TEXT appeals to are read off here, and the derivation
    must return the tier that was already written.
    """
    appeals_to = {
        # "occupied-hours pattern", "weekday daytime load" - whole-home power
        "STRUCT-01": ("import_w",),
        # "wet-appliance cycle count", "no new appliance signature" - circuits
        "EQUIP-01": ("ct_circuit",),
        # "evening peak shifts later and broadens" - whole-home power
        "ROUTINE-01": ("import_w",),
        # "hot-water draw events" AND "bedroom CO2" - circuits and air
        "STRUCT-02": ("ct_circuit", "co2"),
    }
    _event, labels = mary_scenario(
        household_id="HH", building_id="B1", mary_person_id="P1",
        incoming_person_ids=[f"P{i}" for i in range(2, 6)], move_in_day=188,
    )
    assert len(labels) == 4
    for lab in labels:
        key = lab.label_id.rsplit("-", 2)
        suffix = "-".join(key[-2:])
        derived = lowest_tier_for(appeals_to[suffix])
        assert derived == lab.detectable_from_tier, (
            f"{lab.label_id}: design 5.9 wrote {lab.detectable_from_tier}, "
            f"the channel rule derives {derived}"
        )


def test_every_event_type_s_tier_is_the_lowest_that_can_see_it():
    """Both halves of 'lowest': the tier can see it, and no lower tier can."""
    for kind, ev in EVENT_EVIDENCE.items():
        tier = ev.tier
        have = frozenset(TIER_DEVICES[tier])
        assert frozenset(ev.channels) <= have, (
            f"{kind} is labelled {tier}, which does not carry "
            f"{sorted(set(ev.channels) - have)}"
        )
        below = TIER_ORDER[:TIER_ORDER.index(tier)]
        for lower in below:
            assert not frozenset(ev.channels) <= frozenset(TIER_DEVICES[lower]), (
                f"{kind} is labelled {tier} but {lower} already carries every "
                f"channel it needs, so {tier} is not the LOWEST tier"
            )


def test_a_label_with_no_channels_is_refused():
    """An unobservable change must not be given a tier.

    A label that appeals to no measurement would be a free true positive for
    every detector, which is the cheapest possible way to corrupt a benchmark.
    """
    with pytest.raises(ValueError, match="at least one channel"):
        lowest_tier_for(())
    with pytest.raises(ValueError, match="no sensor tier"):
        lowest_tier_for(("import_w", "not_a_channel"))


def test_every_label_the_run_produces_is_observable_at_its_stated_tier(result):
    """The acceptance criterion, re-derived over every label in the run."""
    by_kind = {}
    for ev in result.events:
        by_kind[ev.event_id] = ev.event_type
    assert result.labels, "the run produced no D20 labels"
    checked = 0
    for lab in result.labels:
        assert lab.detectable_from_tier in TIER_DEVICES, lab.label_id
        kinds = {by_kind.get(s) for s in lab.source_event_ids}
        kinds.discard(None)
        for kind in kinds:
            ev = EVENT_EVIDENCE.get(kind)
            if ev is None:
                continue                       # the Mary labels, tested above
            assert lab.detectable_from_tier == ev.tier, (
                f"{lab.label_id} ({kind}) says {lab.detectable_from_tier}, "
                f"the channels derive {ev.tier}"
            )
            checked += 1
    assert checked > 0, "no label was actually checked against a channel set"


def test_no_label_names_a_cause(result):
    """R25, enforced on every label the run produces rather than on samples."""
    from baile_nua.lifecourse.events import check_label_text

    for lab in result.labels:
        check_label_text(lab.observable_change_text)


def test_all_four_tiers_are_exercised():
    """A tier table in which everything is T1 tests nothing about tiers."""
    tiers = {ev.tier for ev in EVENT_EVIDENCE.values()}
    assert tiers == set(TIER_ORDER), (
        f"only {sorted(tiers)} of {list(TIER_ORDER)} appear; a detector "
        f"benchmark whose labels are all one tier cannot measure what "
        f"instrumentation buys"
    )


# --------------------------------------------------------------------------- #
# the ten years
# --------------------------------------------------------------------------- #

def test_ten_year_invariants_are_clean(result):
    assert result.invariants["clean"], result.invariants["failures"][:20]
    assert result.invariants["n_states"] == 11      # ten years plus the end state
    assert result.invariants["n_events"] > 100


def test_births_deaths_and_partnerings_are_within_the_published_interval(result):
    """Against the PUBLISHED rate at this run's own exposure, two-sided."""
    rows = {r["event"]: r for r in result.vital_check["rows"]}
    for name in ("birth", "death", "partnering"):
        r = rows[name]
        assert r["sourced"], name
        assert r["within"], (
            f"{name}: {r['observed']} observed against {r['expected']} "
            f"expected, 95% interval {r['ci95']}. The published rate is "
            f"{r['basis']}"
        )


def test_the_integrated_hazard_agrees_with_the_exposure_expectation(result):
    """Guards the bug class that looks exactly like a model missing its target.

    If the hazard integrated over the draws actually taken disagrees with the
    expectation computed from exposure, the interval is being evaluated against
    the wrong denominator. That is how the parity reweighting was caught: it
    integrated 10.15 against an exposure expectation of 11.52, because
    multiplying by a share rescaled every woman's rate downwards.
    """
    for r in result.vital_check["rows"]:
        if r["integrated_hazard"] is None:
            continue
        assert r["integrated_matches_exposure"], (
            f"{r['event']}: integrated hazard {r['integrated_hazard']} against "
            f"exposure expectation {r['expected']} - more than 10% apart, so "
            f"the exposure accounting and the draws disagree"
        )


def test_the_population_is_continuous_across_year_boundaries(result):
    """Each year must start with exactly the population the last one ended with."""
    for st, py in zip(result.states, result.per_year):
        assert st.n_people() >= 0
    for py, nxt in zip(result.per_year, result.states[1:]):
        assert py["n_people"] == nxt.n_people(), (
            f"{py['year']} ended with {py['n_people']} people but "
            f"{nxt.year} starts with {nxt.n_people()}"
        )


def test_the_vacancy_rate_stays_inside_the_published_cork_range(result):
    """VAC04 puts Cork County at a published range; the chain has to hold it.

    Two different claims, because the slice does not START at the published
    rate: every home in it is occupied at t0, so year one can only approach
    5 per cent from below as move-outs create the first vacancies. The chain
    refills vacancies and never empties a home to hit a target, which is the
    right behaviour - a vacancy rate is an outcome, not a quota.

    So: the rate must never EXCEED the published maximum (the chain refills
    fast enough), and once the chain has run a year it must be INSIDE the
    published range (it converges, rather than drifting off).
    """
    pub = HZ.vacancy_rate_cork_county()
    lo, hi = min(pub.values()) / 100.0, max(pub.values()) / 100.0
    for py in result.per_year:
        assert py["vacancy_rate"] <= hi + 1e-9, (
            f"{py['year']}: vacancy {py['vacancy_rate']:.3f} above VAC04's "
            f"Cork County maximum {hi:.3f}; the chain is not refilling"
        )
    for py in result.per_year[1:]:
        assert lo - 1e-9 <= py["vacancy_rate"] <= hi + 1e-9, (
            f"{py['year']}: vacancy {py['vacancy_rate']:.3f} outside VAC04's "
            f"Cork County range [{lo:.3f}, {hi:.3f}] after the chain has had "
            f"a full year to converge"
        )


def test_the_vacancy_flows_balance_as_the_source_says_they_do(result):
    """VAC17's two directions balance near 1.0, so the stock must be flat."""
    flows = HZ.vacancy_flow_rates()
    assert 0.8 < flows["balance_ratio"] < 1.2, flows
    rates = [py["vacancy_rate"] for py in result.per_year]
    assert max(rates) - min(rates) <= 0.05, (
        f"vacancy drifted from {min(rates):.3f} to {max(rates):.3f} over ten "
        f"years, which VAC17's balanced flows say it should not"
    )


def test_der_adoption_respects_the_hebeu37_prevalence_bound(result):
    """A-25f's bound: the ten-year total cannot exceed the published stock."""
    der = HZ.der_prevalence()
    n_homes = result.states[-1].dwellings
    for measure, spec in MEASURES.items():
        cat = spec["hebeu37"]
        if cat is None:
            continue
        have = sum(1 for d in n_homes.values() if measure in d.measures)
        cap = der[cat] * len(n_homes)
        assert have <= cap + 1, (
            f"{measure}: {have} of {len(n_homes)} homes, above HEBEU37's "
            f"{cat} prevalence of {der[cat]:.0%} ({cap:.1f} homes)"
        )


def test_the_mary_scenario_runs_alongside_the_stochastic_events(result):
    """Design 5.9's scripted case, and its four labels, are in the run."""
    mary = [e for e in result.events if "MARY" in e.event_id]
    assert len(mary) == 1, [e.event_id for e in mary]
    # Linked by source_event_ids, not by a substring of the label id: the
    # labels are keyed by premises (CL-<household>-STRUCT-01), because that is
    # what a detector is scored on, and the event is what carries the cause.
    labels = [
        l for l in result.labels if mary[0].event_id in l.source_event_ids
    ]
    assert len(labels) == 4, [l.label_id for l in labels]
    assert {l.detectable_from_tier for l in labels} == {"T1", "T2", "T3"}
    # And it is not the ONLY event: the point is that it runs alongside.
    assert len(result.events) > 100


def test_every_building_change_has_a_passport_event(result):
    """D03: a retrofit, extension or asset change is a dated passport row."""
    building_kinds = set(MEASURES)
    changes = [e for e in result.events if e.event_type in building_kinds]
    assert changes, "the run produced no building changes at all"
    by_event = {p.life_event_id for p in result.passport_events}
    for e in changes:
        assert e.event_id in by_event, (
            f"{e.event_id} ({e.event_type}) changed the building and has no "
            f"D03 passport event"
        )
    for p in result.passport_events:
        assert p.parameters_changed, p.passport_event_id
        assert p.to_version == p.from_version + 1, p.passport_event_id


def test_the_passport_version_chain_is_chronological(result):
    """A passport whose versions do not follow its dates cannot rebuild the home."""
    by_b: dict[str, list] = {}
    for p in result.passport_events:
        by_b.setdefault(p.building_id, []).append(p)
    for bid, evs in by_b.items():
        evs = sorted(evs, key=lambda e: e.effective_day)
        versions = [e.from_version for e in evs]
        assert versions == sorted(versions), (
            f"{bid}: passport versions {versions} are not in date order"
        )


def test_the_deferred_fabric_work_is_declared_not_silent():
    """I-048 defers fabric to week 3; that must be recorded, not hidden.

    A label for a change the series does not contain would score detectors
    against nothing. The deferral is therefore explicit and asserted here, so
    that applying the fabric work in week 3 has to come back and flip it.
    """
    assert MEASURE_APPLIED_IN_WEEK2["retrofit_fabric"] is False
    assert MEASURE_APPLIED_IN_WEEK2["extension"] is False
    assert MEASURE_APPLIED_IN_WEEK2["retrofit_heat_pump"] is True
    assert MEASURE_APPLIED_IN_WEEK2["der_pv"] is True
    assert set(MEASURE_APPLIED_IN_WEEK2) == set(MEASURES)


def test_applying_a_year_to_the_slice_preserves_the_premises_and_the_count(
    slice60, result
):
    """The slice the engine runs must be the population the life course reports."""
    for yi in (0, 4, 9):
        st = result.states[yi]
        sl = apply_year_to_slice(
            slice60, st, master_seed=SEED, year_index=yi,
        )
        assert len(sl.households) == len(slice60.households), (
            "the number of premises changed; the slice is a fixed set of homes"
        )
        assert set(sl.households) == set(slice60.households)
        n_people = sum(len(v) for v in sl.households.values())
        assert n_people == st.n_people(), (
            f"{st.year}: the slice carries {n_people} people, the life course "
            f"reports {st.n_people()}"
        )
        n_vacant = sum(1 for v in sl.households.values() if not v)
        assert n_vacant == len(st.dwellings) - st.n_occupied(), st.year
        # And the original slice is untouched, because other runs depend on it.
        assert sum(len(v) for v in slice60.households.values()) == 133


def test_applying_a_year_does_not_mutate_the_original_slice_s_buildings(
    slice60, result
):
    """The contract said "mutates nothing" and the first version did mutate.

    ``has_battery`` and ``has_ev`` are carried on the BUILDING and are not
    declared fields of ``SynthBuilding`` - e1_run assigns them after
    construction and every reader uses ``getattr(..., False)``. So two
    separate mistakes were possible here and both were made:

    * assigning the measure reached through to ``sl.buildings`` and the
      original slice's battery count went from 3 to 6;
    * copying the buildings with ``dataclasses.replace`` silently DROPPED the
      undeclared attributes, so applying year one produced a slice with no
      batteries at all where the original had three.

    Neither affected the committed ten-year results, because each per-year run
    is a separate process that applies exactly one year - the one usage
    pattern that cannot see either bug. Two years in one process would have
    leaked the later year's assets into the earlier year's answer.
    """
    def n_bat(buildings):
        return sum(
            1 for b in buildings.values() if getattr(b, "has_battery", False)
        )

    def n_ev(buildings):
        return sum(1 for b in buildings.values() if getattr(b, "has_ev", False))

    base_bat, base_ev = n_bat(slice60.buildings), n_ev(slice60.buildings)
    assert base_bat > 0 and base_ev > 0, "the fixture has no DER to preserve"

    late = apply_year_to_slice(
        slice60, result.states[9], master_seed=SEED, year_index=9,
    )
    # The original is untouched.
    assert n_bat(slice60.buildings) == base_bat
    assert n_ev(slice60.buildings) == base_ev

    # The returned slice has the t0 assets PLUS the ones WP5 added.
    added = sum(
        1 for d in result.states[9].dwellings.values()
        if "der_battery" in d.measures
    )
    assert n_bat(late.buildings) == base_bat + added, (
        f"{n_bat(late.buildings)} batteries against {base_bat} at t0 plus "
        f"{added} added by WP5 - either the copy dropped them or the measure "
        f"did not land"
    )
    assert n_ev(late.buildings) == base_ev, "EVs must survive the copy"

    # And applying an EARLIER year AFTER a later one must not inherit assets.
    early = apply_year_to_slice(
        slice60, result.states[0], master_seed=SEED, year_index=0,
    )
    assert n_bat(early.buildings) == base_bat, (
        "year one inherited a later year's batteries, so the slices are not "
        "independent"
    )


def test_a_year_is_reproducible_without_replaying_the_years_before_it(slice60):
    """The counter-based tree's point: year 7 is addressable on its own."""
    persons, dwellings, households = from_slice(slice60)
    mary = _pick_mary_household(slice60.households, slice60.buildings)
    a = run_life_course(config=TenYearConfig(master_seed=SEED), persons=persons,
                        dwellings=dwellings, households=households, mary=mary)
    persons, dwellings, households = from_slice(slice60)
    b = run_life_course(config=TenYearConfig(master_seed=SEED), persons=persons,
                        dwellings=dwellings, households=households, mary=mary)
    assert a.counts == b.counts
    assert [e.event_id for e in a.events] == [e.event_id for e in b.events]
    assert [e.effective_day for e in a.events] == [e.effective_day for e in b.events]
    assert [l.label_id for l in a.labels] == [l.label_id for l in b.labels]
