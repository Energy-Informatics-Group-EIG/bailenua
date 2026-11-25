"""Tests for the U23 mixed-age slice, and that the E1 estate still reproduces.

U23 replaces the E1 estate "with a mixed-age slice of the same size: pre-1980
homes, BER spread including D to G, and at least one heat pump, PV system, BESS
and EV", and keeps the E1 estate as a regression fixture. Both halves are
tested: the new slice meets every requirement, and the old one is byte-for-byte
the same selection it was, so every E1 artefact still reproduces.
"""

from __future__ import annotations

import pytest

import baile_nua.sources_registry  # noqa: F401  (declares the sources)
from baile_nua.engine.calendar import build_calendar
from baile_nua.engine.e1_run import build_slice
from baile_nua.engine.slice_u23 import (
    MIN_PRE_1980_SHARE,
    REQUIRED_BER_LETTERS,
    U23_REQUIREMENTS,
    U23Infeasible,
    select_mixed_age_slice,
)
from baile_nua.population.synthesise import synthesise_t0

SEED = 20261008


@pytest.fixture(scope="module")
def town():
    return synthesise_t0(master_seed=SEED)


@pytest.fixture(scope="module")
def u23(town):
    cal = build_calendar(2022)
    return build_slice(town, master_seed=SEED, calendar=cal,
                       slice_kind="u23_mixed_age")


@pytest.fixture(scope="module")
def e1(town):
    cal = build_calendar(2022)
    return build_slice(town, master_seed=SEED, calendar=cal,
                       slice_kind="e1_estate")


def test_every_u23_requirement_is_declared_as_a_predicate():
    """A requirement nobody wrote down cannot be checked."""
    assert set(U23_REQUIREMENTS) >= {
        "n_homes", "pre_1980_share", "ber_letters_present",
        "at_least_one_heat_pump", "at_least_one_pv", "at_least_one_bess",
        "at_least_one_ev", "people_in_e0_7_band",
    }
    for key, text in U23_REQUIREMENTS.items():
        assert len(text) > 10, f"{key} has no readable requirement"


def test_the_slice_is_mixed_age_and_substantially_pre_1980(u23):
    es = u23.diagnostics["estate_selection"]
    assert es["pre_1980_share"] >= MIN_PRE_1980_SHARE, (
        f"pre-1980 share {es['pre_1980_share']} below the declared floor "
        f"{MIN_PRE_1980_SHARE}"
    )
    # Mixed, not uniformly old: a span of eras, not a museum.
    assert es["max_build_year"] - es["min_build_year"] >= 50, (
        f"build years span only {es['max_build_year'] - es['min_build_year']} "
        f"years, which is not mixed-age"
    )
    # And materially older than the E1 estate, which is the point of U23.
    assert es["mean_build_year"] < 1990.0


def test_the_ber_spread_includes_d_through_g(u23):
    es = u23.diagnostics["estate_selection"]
    missing = set(REQUIRED_BER_LETTERS) - set(es["ber_letters_present"])
    assert not missing, f"BER letters missing from the slice: {sorted(missing)}"


def test_the_slice_contains_every_required_archetype(u23):
    d = u23.diagnostics
    es = d["estate_selection"]
    assert es["n_heat_pumps"] >= 1, "U23 requires at least one heat pump"
    assert d["n_with_pv"] >= 1, "U23 requires at least one PV system"
    assert d["n_with_battery"] >= 1, "U23 requires at least one battery"
    assert d["n_with_ev"] >= 1, "U23 requires at least one EV"


def test_the_slice_respects_the_e0_7_people_band(u23):
    """E0-7's band is a hard constraint on U23, not a term in its objective.

    The first selector made it a penalty weighted 0.8 against an age reward of
    1.0, and the best-scoring seed gave 112 people against a 115 lower bound.
    Re-weighting until it fitted would have been choosing the weights to get
    the answer.
    """
    es = u23.diagnostics["estate_selection"]
    assert es["people_within_e0_7_band"], (
        f"{es['n_people']} people against a target of {es['target_people']} "
        f"+/-{es['people_tolerance']}"
    )
    assert es["n_seed_areas_tried"] > 1, (
        "the feasibility search tried one seed, so it is not a search"
    )


def test_every_substitution_is_recorded_with_what_it_was_for(u23):
    for sub in u23.diagnostics["estate_selection"]["substitutions"]:
        assert sub["for"], "a substitution with no stated purpose"
        assert "note" in sub and len(sub["note"]) > 20


def test_every_der_guarantee_is_recorded(u23):
    for g in u23.diagnostics.get("der_guarantees", []):
        assert g["der"] in ("PV", "BESS", "EV")
        assert g["household_id"]
        assert len(g["reason"]) > 20, (
            "a guaranteed adoption must say why it was needed, or it is "
            "indistinguishable from the adoption model's own output"
        )


def test_the_slice_exercises_more_of_the_library_than_the_e1_estate(u23, e1):
    """The reason U23 exists, measured rather than asserted."""
    u_sys = set(u23.diagnostics["heating_systems"])
    e_sys = set(e1.diagnostics["heating_systems"])
    assert len(u_sys) > len(e_sys), (
        f"the mixed-age slice exercises {len(u_sys)} heating systems against "
        f"the E1 estate's {len(e_sys)}; it was supposed to widen coverage"
    )
    u_tiers = {k for k, v in u23.diagnostics["sensor_tiers"].items() if v}
    assert len(u_tiers) == 4, f"only tiers {sorted(u_tiers)} are present"


def test_the_e1_estate_is_unchanged_as_a_regression_fixture(e1):
    """U23 keeps it, so every E1 artefact must still reproduce from it."""
    d = e1.diagnostics
    assert d["slice_kind"] == "e1_estate"
    assert d["n_homes"] == 50
    assert d["n_people"] == 147, (
        f"the E1 estate now holds {d['n_people']} people, not the 147 every "
        f"E1 artefact was computed from"
    )
    assert d["estate_selection"]["seed_area"] == "047106015"
    assert d["estate_selection"]["small_areas"] == ["047106015", "047106012"]


def test_the_default_slice_kind_is_still_the_e1_estate(town):
    """So an un-updated caller reproduces E1 rather than silently changing."""
    cal = build_calendar(2022)
    default = build_slice(town, master_seed=SEED, calendar=cal)
    assert default.diagnostics["slice_kind"] == "e1_estate"


def test_the_slice_is_deterministic(town):
    cal = build_calendar(2022)
    a = build_slice(town, master_seed=SEED, calendar=cal,
                    slice_kind="u23_mixed_age")
    b = build_slice(town, master_seed=SEED, calendar=cal,
                    slice_kind="u23_mixed_age")
    assert a.household_ids == b.household_ids
    assert a.diagnostics["estate_selection"]["seed_area"] == \
        b.diagnostics["estate_selection"]["seed_area"]


def test_an_unknown_slice_kind_is_refused(town):
    cal = build_calendar(2022)
    with pytest.raises(ValueError, match="unknown slice_kind"):
        build_slice(town, master_seed=SEED, calendar=cal, slice_kind="whatever")


def test_infeasibility_is_raised_rather_than_papered_over(town):
    """If no slice can satisfy both decisions, that is a conflict to report.

    Forced here by demanding a people band no older Cobh area can reach, which
    is the situation U23 and E0-7 nearly produced for real.
    """
    with pytest.raises(U23Infeasible, match="conflict between two approved"):
        select_mixed_age_slice(
            town, n_homes=50, target_people=400, people_tolerance=5,
            master_seed=SEED,
        )


# --------------------------------------------------------------------------- #
# U29: resized to about 60 homes so the people band has headroom
# --------------------------------------------------------------------------- #

def test_the_week2_slice_is_sixty_homes_and_declared_separately(u23):
    """U29. Declared as its own scope, never by editing the E1 slice.

    Two named scopes rather than one editable number, so growing the week 2
    slice cannot silently raise the ceiling on the E1 slice that every E1
    artefact was produced under.
    """
    from baile_nua.config import e1_scope, week2_slice

    cfg = e1_scope()
    assert cfg["slice"]["n_homes"] == 50, (
        "the E1 slice's approved size changed; every E1 artefact was produced "
        "at 50 homes"
    )
    assert week2_slice()["n_homes"] == 60
    assert u23.diagnostics["n_homes"] == 60


def test_the_people_band_now_has_headroom(u23):
    """The point of U29: 115 was the lower bound exactly, with none."""
    es = u23.diagnostics["estate_selection"]
    target = es["target_people"]
    tol = es["people_tolerance"]
    people = es["n_people"]
    assert es["people_within_e0_7_band"]
    headroom = min(people - (target - tol), (target + tol) - people)
    assert headroom >= 10, (
        f"{people} people leaves only {headroom} of headroom to the nearer "
        f"band edge ({target} +/-{tol}). U29 resized the slice precisely so "
        f"that a later change costing a few people cannot break the band."
    )


def test_resizing_did_not_cost_any_u23_requirement(u23):
    """Sixty homes must still satisfy everything fifty did."""
    d = u23.diagnostics
    es = d["estate_selection"]
    assert es["pre_1980_share"] >= MIN_PRE_1980_SHARE
    assert not set(REQUIRED_BER_LETTERS) - set(es["ber_letters_present"])
    assert es["n_heat_pumps"] >= 1
    assert d["n_with_pv"] >= 1 and d["n_with_battery"] >= 1 and d["n_with_ev"] >= 1
    assert len(d["heating_systems"]) >= 5


def test_household_sizes_are_taken_as_the_data_give_them(u23, town):
    """U29: "Keep household sizes as the data give them".

    The slice's people count must equal the sum of its households' actual
    sizes. If the selector ever adjusted a household to hit the people band,
    this fails - and the band would then be met by changing the population
    rather than by choosing which part of it to simulate.
    """
    size = town.states.groupby("household_id").size().to_dict()
    expected = sum(int(size.get(h, 0)) for h in u23.household_ids)
    assert u23.diagnostics["n_people"] == expected
    assert sum(len(v) for v in u23.households.values()) == expected


def test_the_e1_slice_scope_still_refuses_sixty_homes():
    """The E1 ceiling must be unaffected by the week 2 one."""
    from baile_nua.config import ScopeError, assert_within_e1_scope

    with pytest.raises(ScopeError, match="exceeds the approved slice of 50"):
        assert_within_e1_scope(
            n_homes=60, coupling_mode="C1", year=2022, scope_name="slice",
        )
    # And the week 2 scope permits it.
    assert_within_e1_scope(
        n_homes=60, coupling_mode="C1", year=2022, scope_name="week2_slice",
    )
    with pytest.raises(ScopeError, match="unknown scope"):
        assert_within_e1_scope(
            n_homes=10, coupling_mode="C1", year=2022, scope_name="nonsense",
        )
