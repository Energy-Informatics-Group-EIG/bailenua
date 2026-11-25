"""Intervention replay by forking, and the refusal that makes it honest.

Design 8.2's three replays have three different guarantees, and the rule that
matters most is the one that is easiest to read past:

    The replay API refuses to present an isolated single-household replay as a
    town-wide counterfactual. Any intervention forces a town fork.

So the central test here is that :func:`counterfactual` *raises* on a
household-scoped fork. A single-household replay is cheap and tempting, and it
would be wrong in a way that does not announce itself: the home's own load
would respond correctly while every coupled quantity around it stayed at its
baseline, so the estimate would miss exactly the coupled effect the
intervention was interesting for.

The other half is common random numbers. Because the tree is counter-based and
holds no state, the same coordinate gives the same number in any fork for
free - so the question is not whether the numbers are common but whether the
same COORDINATES are visited. These tests build forks that visit matching and
mismatching coordinate sets on purpose and check that the audit can tell them
apart, including the case that matters: an entity the intervention does not
touch which decouples anyway.
"""

from __future__ import annotations

import pytest

import baile_nua.sources_registry  # noqa: F401
from baile_nua.checkpoint import Checkpoint, CheckpointStore
from baile_nua.engine.fork import (
    HOUSEHOLD_SCOPE,
    TOWN_SCOPE,
    DrawRecorder,
    Intervention,
    RecordingSeedTree,
    ReplayRefused,
    counterfactual,
    crn_audit,
    fork_household,
    fork_town,
    observation_replay_is_byte_identical,
)
from baile_nua.rng import SeedTree, Stream

SEED = 20251010
HOUSEHOLDS = [f"H-{i:03d}" for i in range(12)]


@pytest.fixture
def store(tmp_path):
    st = CheckpointStore(tmp_path / "ckpt")
    prev = None
    for day in range(3):
        cp = Checkpoint(
            sim_day=day, date_iso=f"2022-01-{day + 1:02d}", run_id="RUN-TEST",
            master_seed=SEED,
            household_state={h: {"occupants": 2 + (i % 3)}
                             for i, h in enumerate(HOUSEHOLDS)},
            building_state={f"B-{i:03d}": {"temp_living_c": 20.0}
                            for i in range(len(HOUSEHOLDS))},
            previous_hash=prev,
        )
        st.put(cp)
        prev = cp.chain_hash()
    return st


@pytest.fixture
def intervention():
    return Intervention(
        intervention_id="IV-TARIFF-01", kind="tariff", from_sim_day=2,
        parameters={"evening_rate_c_per_kwh": 42.0},
        touches_entities=("H-000", "H-001"),
        may_change_draw_count_in=("APPLIANCE_TRIGGER",),
    )


# --------------------------------------------------------------------------- #
# the refusal
# --------------------------------------------------------------------------- #

def test_a_single_household_fork_cannot_be_a_town_counterfactual(
    store, intervention
):
    """Design 8.2's explicit rule, and the point of the module."""
    base = fork_household(
        store=store, sim_day=2, household_id="H-000", fork_id="F-BASE",
    )
    treat = fork_household(
        store=store, sim_day=2, household_id="H-000", fork_id="F-TREAT",
        intervention=intervention,
    )
    assert base.scope == HOUSEHOLD_SCOPE
    with pytest.raises(ReplayRefused, match="town fork"):
        counterfactual(
            baseline=base, treated=treat,
            outcome_baseline={"H-000": 4000.0},
            outcome_treated={"H-000": 3600.0},
        )


def test_a_household_fork_is_still_allowed_for_inspection(store):
    """The refusal is about inference, not about looking at one home."""
    f = fork_household(
        store=store, sim_day=1, household_id="H-003", fork_id="F-LOOK",
    )
    assert f.entities == ("H-003",)
    assert not f.is_town_wide
    assert f.parent_chain_hash


def test_forking_a_household_that_does_not_exist_is_refused(store):
    with pytest.raises(ReplayRefused, match="no household"):
        fork_household(
            store=store, sim_day=1, household_id="H-999", fork_id="F-X",
        )


def test_forking_a_day_that_was_never_simulated_is_refused(store):
    with pytest.raises(ReplayRefused, match="no checkpoint"):
        fork_town(store=store, sim_day=99, intervention=None, fork_id="F-X")


def test_forking_after_the_intervention_has_taken_effect_is_refused(store):
    """Otherwise the intervention ends up inside the baseline."""
    late = Intervention(
        intervention_id="IV-EARLY", kind="tariff", from_sim_day=0,
        parameters={},
    )
    with pytest.raises(ReplayRefused, match="already taken effect"):
        fork_town(store=store, sim_day=2, intervention=late, fork_id="F-X")


def test_two_forks_from_different_states_cannot_be_compared(store, intervention):
    base = fork_town(store=store, sim_day=1, intervention=None, fork_id="F-B")
    treat = fork_town(
        store=store, sim_day=2, intervention=intervention, fork_id="F-T",
    )
    with pytest.raises(ReplayRefused, match="different states"):
        counterfactual(
            baseline=base, treated=treat,
            outcome_baseline={h: 4000.0 for h in HOUSEHOLDS},
            outcome_treated={h: 3800.0 for h in HOUSEHOLDS},
        )


def test_a_baseline_that_carries_an_intervention_is_refused(store, intervention):
    other = Intervention(
        intervention_id="IV-OTHER", kind="setpoint", from_sim_day=2,
        parameters={},
    )
    base = fork_town(store=store, sim_day=2, intervention=other, fork_id="F-B")
    treat = fork_town(
        store=store, sim_day=2, intervention=intervention, fork_id="F-T",
    )
    with pytest.raises(ReplayRefused, match="two treatments"):
        counterfactual(
            baseline=base, treated=treat,
            outcome_baseline={h: 4000.0 for h in HOUSEHOLDS},
            outcome_treated={h: 3800.0 for h in HOUSEHOLDS},
        )


def test_a_treated_fork_with_no_intervention_is_refused(store):
    base = fork_town(store=store, sim_day=2, intervention=None, fork_id="F-B")
    treat = fork_town(store=store, sim_day=2, intervention=None, fork_id="F-T")
    with pytest.raises(ReplayRefused, match="nothing to estimate"):
        counterfactual(
            baseline=base, treated=treat,
            outcome_baseline={h: 4000.0 for h in HOUSEHOLDS},
            outcome_treated={h: 3800.0 for h in HOUSEHOLDS},
        )


# --------------------------------------------------------------------------- #
# the fork commits to a state, not a date
# --------------------------------------------------------------------------- #

def test_a_fork_commits_to_the_checkpoint_chain_hash(store, intervention):
    f = fork_town(
        store=store, sim_day=2, intervention=intervention, fork_id="F-T",
    )
    assert f.parent_chain_hash == store.get(2).chain_hash()
    assert f.is_town_wide
    assert set(f.entities) >= set(HOUSEHOLDS)
    # The fork's own hash commits to the intervention as well as the state, so
    # the same fork point with a different intervention is a different fork.
    other = Intervention(
        intervention_id="IV-TARIFF-01", kind="tariff", from_sim_day=2,
        parameters={"evening_rate_c_per_kwh": 99.0},
    )
    g = fork_town(store=store, sim_day=2, intervention=other, fork_id="F-T")
    assert f.content_hash() != g.content_hash()


def test_the_same_fork_point_and_intervention_hash_identically(
    store, intervention
):
    a = fork_town(store=store, sim_day=2, intervention=intervention, fork_id="F")
    b = fork_town(store=store, sim_day=2, intervention=intervention, fork_id="F")
    assert a.content_hash() == b.content_hash()


# --------------------------------------------------------------------------- #
# common random numbers
# --------------------------------------------------------------------------- #

def test_the_same_coordinate_gives_the_same_number_in_any_fork():
    """What the counter-based tree buys for free, demonstrated."""
    a = SeedTree(SEED).generator(Stream.APPLIANCE_TRIGGER, entity="H-005",
                                 sim_day=7, draw=3)
    b = SeedTree(SEED).generator(Stream.APPLIANCE_TRIGGER, entity="H-005",
                                 sim_day=7, draw=3)
    assert a.random() == b.random()
    c = SeedTree(SEED).generator(Stream.APPLIANCE_TRIGGER, entity="H-005",
                                 sim_day=7, draw=4)
    assert SeedTree(SEED).generator(
        Stream.APPLIANCE_TRIGGER, entity="H-005", sim_day=7, draw=3
    ).random() != c.random()


def _run(recorder, *, extra_draws_for=()):
    """A toy run: every household draws twice, some draw a third time."""
    tree = RecordingSeedTree(SEED, recorder)
    out = {}
    for h in HOUSEHOLDS:
        total = 0.0
        n = 3 if h in extra_draws_for else 2
        for d in range(n):
            total += float(
                tree.generator(Stream.APPLIANCE_TRIGGER, entity=h, sim_day=2,
                               draw=d).random()
            )
        out[h] = total
    return out


def test_entities_the_intervention_does_not_touch_stay_paired(intervention):
    rb, rt = DrawRecorder(), DrawRecorder()
    _run(rb)
    _run(rt, extra_draws_for=("H-000", "H-001"))
    audit = crn_audit(baseline=rb, treated=rt, intervention=intervention)
    assert set(audit["decoupled"]) == {"H-000", "H-001"}
    assert len(audit["paired"]) == len(HOUSEHOLDS) - 2
    assert audit["clean"], audit
    assert 0.0 < audit["crn_share"] < 1.0


def test_an_untouched_entity_that_decouples_is_a_finding_not_noise(intervention):
    """The failure the audit exists for.

    If an entity the intervention never names changes its draw count, then
    something leaked: a shared counter, an ordering dependence, a global. Every
    paired statistic over that entity is comparing two different random
    sequences while reporting the variance of one, and nothing else in the
    pipeline would notice.
    """
    rb, rt = DrawRecorder(), DrawRecorder()
    _run(rb)
    _run(rt, extra_draws_for=("H-000", "H-007"))      # H-007 is not touched
    audit = crn_audit(baseline=rb, treated=rt, intervention=intervention)
    assert not audit["clean"]
    assert audit["decoupled_but_not_touched_by_the_intervention"] == ["H-007"]


def test_an_undeclared_stream_changing_draw_count_is_a_finding(intervention):
    rb, rt = DrawRecorder(), DrawRecorder()
    _run(rb)
    out = _run(rt)
    # A stream the intervention log never declared it would touch.
    tree = RecordingSeedTree(SEED, rt)
    tree.generator(Stream.SENSOR_NOISE, entity="H-000", sim_day=2, draw=0)
    audit = crn_audit(baseline=rb, treated=rt, intervention=intervention)
    assert not audit["clean"]
    assert "SENSOR_NOISE" in audit["undeclared_streams_that_changed_draw_count"]


def test_identical_runs_are_fully_paired(intervention):
    rb, rt = DrawRecorder(), DrawRecorder()
    _run(rb)
    _run(rt)
    audit = crn_audit(baseline=rb, treated=rt, intervention=intervention)
    assert audit["n_decoupled"] == 0
    assert audit["crn_share"] == 1.0
    assert audit["clean"]


# --------------------------------------------------------------------------- #
# the counterfactual statistic
# --------------------------------------------------------------------------- #

def test_the_paired_statistic_uses_only_the_paired_entities(store, intervention):
    base = fork_town(store=store, sim_day=2, intervention=None, fork_id="F-B")
    treat = fork_town(
        store=store, sim_day=2, intervention=intervention, fork_id="F-T",
    )
    rb, rt = DrawRecorder(), DrawRecorder()
    _run(rb)
    _run(rt, extra_draws_for=("H-000", "H-001"))
    audit = crn_audit(baseline=rb, treated=rt, intervention=intervention)

    ob = {h: 4000.0 + 10.0 * i for i, h in enumerate(HOUSEHOLDS)}
    ot = {h: v - 200.0 for h, v in ob.items()}
    # The two decoupled homes get a wildly different outcome, which must NOT
    # be allowed into the paired mean.
    ot["H-000"] = 1.0
    ot["H-001"] = 1.0

    res = counterfactual(
        baseline=base, treated=treat, outcome_baseline=ob,
        outcome_treated=ot, audit=audit,
    )
    assert res["n_paired"] == len(HOUSEHOLDS) - 2
    assert res["paired_mean_difference"] == pytest.approx(-200.0)
    assert res["paired_sd"] == pytest.approx(0.0, abs=1e-9)
    assert res["n_unpaired"] == 2
    assert res["unpaired_mean_difference"] < -3000.0
    assert res["pooling_note"]


def test_the_variance_is_reported_and_not_merely_the_mean(store, intervention):
    base = fork_town(store=store, sim_day=2, intervention=None, fork_id="F-B")
    treat = fork_town(
        store=store, sim_day=2, intervention=intervention, fork_id="F-T",
    )
    ob = {h: 4000.0 for h in HOUSEHOLDS}
    ot = {h: 4000.0 - 100.0 * (i % 5) for i, h in enumerate(HOUSEHOLDS)}
    res = counterfactual(
        baseline=base, treated=treat, outcome_baseline=ob, outcome_treated=ot,
    )
    assert res["n_paired"] == len(HOUSEHOLDS)
    assert res["paired_sd"] > 0.0
    assert res["paired_se"] == pytest.approx(
        res["paired_sd"] / len(HOUSEHOLDS) ** 0.5
    )
    lo, hi = res["paired_ci95"]
    assert lo < res["paired_mean_difference"] < hi
    assert res["intervention_hash"]
    assert res["parent_chain_hash"] == store.get(2).chain_hash()


def test_observation_replay_states_its_own_guarantee(store):
    ok = observation_replay_is_byte_identical(
        store=store, sim_day=1, digest_a="abc", digest_b="abc",
    )
    assert ok["guarantee"] == "byte-identical"
    assert ok["identical"]
    bad = observation_replay_is_byte_identical(
        store=store, sim_day=1, digest_a="abc", digest_b="abd",
    )
    assert not bad["identical"]
