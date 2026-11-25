"""I-075: the linked MIMIC panel must be linked *in time*, not just to a person.

The issue I-075 names the test it wants:

    a test that fails if a linked session's ``simulated_session_date`` is null

That is :func:`test_every_linked_wave_carries_a_simulated_session_date`, and it
is the reason this file exists.  The rest checks the properties a *panel* has
that a snapshot does not: a shared wave calendar, 8 to 15 sessions per person
inside it, one participant per (person, wave), and answers that differ between a
person's own waves.

The population is fabricated here rather than synthesised.  ``synthesise_t0``
takes about 40 seconds and reads the SAPS sources, and none of what is under
test depends on the real marginals - what is under test is the wave schedule.
``test_mimic_panel_artefact`` checks the real run's artefact instead, when one
is present.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from baile_nua.mimic import crosswalk
from baile_nua.mimic.counters import CounterMergeRefused, MimicCounters
from baile_nua.mimic.panel import (
    MAX_SESSIONS,
    MIN_SESSIONS,
    N_WAVES,
    PanelPerson,
    WAVE_CALENDAR_END,
    WAVE_CALENDAR_START,
    build_panel,
    panel_summary,
    wave_calendar,
)

pytestmark = pytest.mark.mimic

SEED = 20261008
ARTEFACT = Path(__file__).resolve().parents[2] / "v1" / "evidence" / "mimic_tests_T1_T10.json"


# --------------------------------------------------------------------------- #
# A small fabricated population, shaped like the frozen one
# --------------------------------------------------------------------------- #

def _population(n: int = 60) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(7)
    persons, states, membership = [], [], []
    for i in range(n):
        pid = f"P-{i:06d}"
        hid = f"H-{i // 3:06d}"
        bid = f"B-{i // 3:06d}"
        # A spread of ages that includes minors who become adults mid-decade.
        age_at_t0 = int(rng.integers(8, 85))
        birth = dt.date(2022 - age_at_t0, 1 + i % 12, 1 + i % 28)
        lat = {k: float(rng.normal(0, 1)) for k in crosswalk.MIMIC_LATENTS
               if k != "satisficer"}
        persons.append({
            "person_id": pid, "birth_date": birth, "death_date": None,
            "sex": "F" if i % 2 else "M",
            "education_level": f"ISCED {i % 9}",
            **lat, "satisficer": int(i % 7 == 0),
            "stated_gap": float(rng.uniform(0, 0.6)),
            "lambda_self": 0.4, "lambda_coop": 0.3, "lambda_altru": 0.3,
            "big5_o": 0.1, "big5_c": 0.2, "big5_e": -0.1, "big5_a": 0.0,
            "big5_n": 0.3, "chronotype": 0.0, "habit_strength": 0.5,
            "lapse_rate": 0.05, "attention": 0.7,
            # High so most people are selected and the schedule is exercised.
            "response_propensity": float(rng.uniform(0.75, 0.95)),
            "mcv_latent": [float(v) for v in rng.normal(0, 1, 10)],
        })
        states.append({
            "person_id": pid, "household_id": hid,
            "econ_status": ["employed", "retired", "student", "home duties"][i % 4],
            "work_pattern": ["fixed day", "shift", "none", "part-time"][i % 4],
            "remote_share": 0.8 if i % 9 == 0 else 0.0,
            "income_quintile": 1 + i % 5,
        })
        membership.append({
            "membership_id": f"M-{i:06d}", "person_id": pid,
            "household_id": hid, "building_id": bid,
        })
    buildings = pd.DataFrame([
        {"building_id": f"B-{j:06d}", "version": 1,
         "dwelling_type": ["detached", "semi-detached", "terraced", "apartment"][j % 4],
         "tenure": ["owner-occupied with mortgage", "rented private",
                    "rented social", "rent free"][j % 4],
         "heating_system": "heat pump" if j % 5 == 0 else "gas boiler"}
        for j in range((n // 3) + 1)
    ])
    return {
        "persons": pd.DataFrame(persons), "states": pd.DataFrame(states),
        "membership": pd.DataFrame(membership), "buildings": buildings,
    }


@pytest.fixture(scope="module")
def panel():
    people, diag = build_panel(master_seed=SEED, **_population())
    return people, diag


# --------------------------------------------------------------------------- #
# The wave calendar
# --------------------------------------------------------------------------- #

def test_the_wave_calendar_spans_the_simulated_decade():
    cal = wave_calendar()
    assert len(cal) == N_WAVES
    assert cal[0] == WAVE_CALENDAR_START
    assert cal[-1] == WAVE_CALENDAR_END
    assert cal == sorted(cal), "waves must be in calendar order"
    assert len(set(cal)) == len(cal), "two waves must not share a nominal date"
    # The decade the ten-year life course covers (wp5_tenyear.json: 2022-2031).
    assert cal[0].year == 2022 and cal[-1].year == 2031


def test_a_panel_needs_at_least_two_waves():
    with pytest.raises(ValueError):
        wave_calendar(n_waves=1)


# --------------------------------------------------------------------------- #
# I-075's own test
# --------------------------------------------------------------------------- #

def test_every_linked_wave_carries_a_simulated_session_date(panel):
    """I-075: *"a test that fails if a linked session's date is null"*."""
    people, _ = panel
    assert people, "the fabricated population produced no panel at all"
    undated = [p.pool_person_id for p in people if not p.simulated_session_date]
    assert not undated, (
        f"{len(undated)} linked panel sessions have no simulated_session_date "
        f"(e.g. {undated[:5]}); that is exactly the I-075 defect - the panel "
        f"exists and is not linked in time"
    )


def test_the_dates_lie_inside_the_simulated_decade(panel):
    people, _ = panel
    dates = [dt.date.fromisoformat(p.simulated_session_date) for p in people]
    assert min(dates) >= WAVE_CALENDAR_START
    assert max(dates) <= WAVE_CALENDAR_END


def test_the_panel_spans_more_than_one_year(panel):
    """A snapshot would pass every test above and fail this one."""
    people, _ = panel
    years = {p.simulated_session_date[:4] for p in people}
    assert len(years) >= 8, f"only {sorted(years)} covered; a panel is not a snapshot"


def test_sessions_per_person_are_inside_the_design_range(panel):
    """8 to 15 sessions each, for anyone who was an adult when the panel opened.

    A person who was 14 at t0 cannot answer the 2022 waves - MIMIC has no age
    band below 18 - so their realised count is lower by however many waves they
    were still a minor for.  Those are counted separately in the diagnostics.
    Someone who answered wave 1 was an adult at the start, and since age only
    increases no later wave of theirs can have been skipped: for them the
    realised count must equal the drawn count, and the drawn count must be in
    the design's range.
    """
    people, diag = panel
    by_person: dict[str, list[PanelPerson]] = {}
    for p in people:
        by_person.setdefault(str(p.linked_person_id), []).append(p)
    checked = 0
    for person, ps in by_person.items():
        waves = [p.wave for p in ps]
        assert len(waves) <= MAX_SESSIONS, f"{person} has {len(waves)} sessions"
        assert len(set(waves)) == len(waves), f"{person} answers a wave twice"
        assert MIN_SESSIONS <= ps[0].n_waves <= MAX_SESSIONS, (
            f"{person} was given {ps[0].n_waves} sessions; the design asks for "
            f"{MIN_SESSIONS} to {MAX_SESSIONS}"
        )
        if min(waves) == 1:                      # an adult when the panel opened
            checked += 1
            assert len(waves) == ps[0].n_waves, (
                f"{person} answered wave 1, so no wave of theirs can have been "
                f"skipped, yet {ps[0].n_waves - len(waves)} are missing"
            )
            assert len(waves) >= MIN_SESSIONS
    assert checked > 0, "nobody was an adult at the opening wave"
    assert diag["waves_skipped_because_still_a_minor"] >= 0


def test_one_participant_per_person_and_wave(panel):
    people, _ = panel
    keys = [(p.linked_person_id, p.wave) for p in people]
    assert len(set(keys)) == len(keys)
    ids = [p.pool_person_id for p in people]
    assert len(set(ids)) == len(ids), "the seed-tree key must be unique per wave"


def test_a_wave_key_names_its_person_and_its_wave(panel):
    people, _ = panel
    for p in people[:50]:
        assert p.pool_person_id == f"{p.linked_person_id}-w{p.wave:02d}"


def test_no_participant_is_a_minor(panel):
    """MIMIC has no age band below 18, so a minor cannot hold a profile."""
    people, _ = panel
    assert all(p.age >= 18 for p in people)
    assert all(p.age_band in crosswalk.MIMIC_VALUE_SETS["age_band"] for p in people)


def test_age_advances_across_a_persons_own_waves(panel):
    """The snapshot is at t0; a wave in 2031 must not report the 2022 age."""
    people, _ = panel
    by_person: dict[str, list[tuple[int, int]]] = {}
    for p in people:
        by_person.setdefault(str(p.linked_person_id), []).append((p.wave, p.age))
    moved = 0
    for waves in by_person.values():
        ages = [a for _, a in sorted(waves)]
        assert ages == sorted(ages), "age must not go backwards between waves"
        if len(set(ages)) > 1:
            moved += 1
    assert moved > 0, "nobody aged between waves; the dates are not being used"


def test_the_profile_uses_mimics_own_value_sets(panel):
    people, _ = panel
    vs = crosswalk.MIMIC_VALUE_SETS
    for p in people[:200]:
        prof = p.mimic_profile()
        for field in ("age_band", "sex", "household_size", "children_present",
                      "employment_status", "work_pattern", "dwelling_type",
                      "ownership_status", "urban_rural_island", "income_band"):
            assert prof[field] in vs[field], (
                f"{field}={prof[field]!r} is not in MIMIC's value set"
            )
        assert set(prof["der_ownership"]) <= set(vs["der_ownership_values"])
        for f in ("environmental_concern", "trust_in_automation",
                  "comfort_sensitivity"):
            assert 1 <= prof[f] <= 5
        assert set(crosswalk.MIMIC_PRIMARY_FIELDS) <= set(prof)


def test_the_u18_losses_are_recorded_per_participant(panel):
    """MIMIC cannot say "not in employment" or carry PV; both must be visible."""
    people, _ = panel
    lost = [l for p in people for l in p.u18_information_lost]
    assert any("work_pattern" in l for l in lost)
    assert any("der_ownership" in l for l in lost)


def test_the_panel_is_deterministic():
    pop = _population()
    a, da = build_panel(master_seed=SEED, **pop)
    b, db = build_panel(master_seed=SEED, **pop)
    assert [p.pool_person_id for p in a] == [p.pool_person_id for p in b]
    assert [p.simulated_session_date for p in a] == [p.simulated_session_date for p in b]
    assert da["sessions_per_person"] == db["sessions_per_person"]


def test_a_different_seed_gives_a_different_schedule():
    pop = _population()
    a, _ = build_panel(master_seed=SEED, **pop)
    b, _ = build_panel(master_seed=SEED + 1, **pop)
    assert [p.pool_person_id for p in a] != [p.pool_person_id for p in b]


def test_the_summary_reports_dated_and_undated_separately(panel):
    people, _ = panel
    s = panel_summary(people)
    assert s["n_undated"] == 0
    assert s["n_dated"] == s["n_wave_participants"] == len(people)
    assert s["n_distinct_persons"] < s["n_wave_participants"], (
        "a panel has more sessions than people; otherwise it is a snapshot"
    )


def test_the_diagnostics_name_the_mimic_limitation(panel):
    _, diag = panel
    assert "I-087" in diag["mimic_limitation"]
    assert diag["n_wave_participants"] > diag["n_persons_with_at_least_one_wave"]


# --------------------------------------------------------------------------- #
# The counting rule the waves make load-bearing
# --------------------------------------------------------------------------- #

def test_repeated_sessions_cannot_inflate_the_participant_count():
    """The five counters are over respondents; summing them is refused."""
    c = MimicCounters(unique_participants=10, linked_panel_participants=4,
                      unlinked_pool_participants=6)
    assert c.as_dict()["unique_synthetic_participants"] == 10
    with pytest.raises(CounterMergeRefused):
        c.total()
    with pytest.raises(ValueError):
        MimicCounters(unique_participants=10, linked_panel_participants=8,
                      unlinked_pool_participants=6)


def test_the_runner_reads_the_date_off_the_person():
    """``run_batch`` need not be told one date: each wave carries its own."""
    from baile_nua.mimic import runner as runner_mod

    src = Path(runner_mod.__file__).read_text(encoding="utf-8")
    assert 'getattr(person, "simulated_session_date", None)' in src, (
        "the runner must take the simulated date off the person, or a batch "
        "cannot mix waves with different dates (I-075)"
    )
    assert 'getattr(person, "linked_person_id", None)' in src


# --------------------------------------------------------------------------- #
# The real run's artefact, when one has been produced
# --------------------------------------------------------------------------- #

@pytest.mark.skipif(not ARTEFACT.is_file(), reason=f"no artefact at {ARTEFACT}")
def test_mimic_panel_artefact():
    doc = json.loads(ARTEFACT.read_text(encoding="utf-8"))
    assert "i075" in doc, (
        f"{ARTEFACT} has no 'i075' block, so it was written before the wave "
        f"schedule existed: it is the stale snapshot artefact, not evidence "
        f"about a panel linked in time. Re-run baile_nua.mimic.e1_run."
    )
    i075 = doc["i075"]
    assert i075["simulated_session_date_passed"] is True
    assert i075["n_dated_panel_sessions"] > 0, (
        "the artefact records no dated panel session, which is I-075 unfixed"
    )
    assert i075["n_distinct_simulated_session_dates"] > 1
    panel_batch = doc["batches"]["panel"]
    assert panel_batch["config"]["n_dated_sessions"] == panel_batch["config"][
        "n_mimic_participant_rows"], (
        "every panel participant must be dated; an undated one is I-075"
    )
    lo, hi = i075["span"]
    assert lo[:4] == "2022" and hi[:4] == "2031"
    c = doc["counters"]
    assert (c["linked_baile_nua_panel_participants"]
            + c["unlinked_extended_pool_participants"]
            <= c["unique_synthetic_participants"])
    assert c["linked_baile_nua_panel_participants"] < panel_batch["config"][
        "n_mimic_participant_rows"], (
        "the linked counter must count people, not wave sessions"
    )
