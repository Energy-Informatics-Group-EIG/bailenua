"""PL-ROOMS-01: the rooms x dwelling-type joint against Census 2022.

I-031 - a 285.7 m2 three-bedroom apartment - happened because room counts were
drawn independently of dwelling type while every published MARGINAL stayed
correct. No marginal check could have caught it. These tests pin the joint
check that can, and pin that it still rejects the regime that caused it.
"""

from __future__ import annotations

import pytest

import baile_nua.sources_registry  # noqa: F401
from baile_nua.population.joint_f2063 import (
    COUNTY,
    LEVEL_TOLERANCE_ROOMS,
    MIN_GRADIENT_SHARE,
    SAPS_ROOM_CAP,
    TYPE_MAP,
    county_rooms_by_dwelling_type,
    rooms_by_dwelling_type_acceptance,
)
from baile_nua.population.synthesise import synthesise_t0

SEED = 20261008


@pytest.fixture(scope="module")
def reference():
    return county_rooms_by_dwelling_type()


@pytest.fixture(scope="module")
def town_joint():
    town = synthesise_t0(master_seed=SEED)
    dt = [b.dwelling_type for b in town.buildings]
    rm = [b.rooms for b in town.buildings]
    return dt, rm


# --------------------------------------------------------------------------- #
# the reference
# --------------------------------------------------------------------------- #

def test_the_census_reference_is_strongly_ordered(reference):
    """The joint has real content: 3.4 rooms to 6.4 across dwelling types."""
    means = {k: v["mean_rooms"] for k, v in reference.items()
             if k != "_reference"}
    assert means["apartment"] < means["terraced"] < means["semi-detached"] \
        < means["detached"]
    assert means["detached"] - means["apartment"] > 2.5, (
        "the gradient this check scores has collapsed in the source; "
        f"{means}"
    )


def test_the_reference_is_cork_county_not_cork_city(reference):
    """Cobh is in the county area; the city is a different housing stock."""
    assert reference["_reference"]["county"] == COUNTY == "Cork County Council"
    assert reference["_reference"]["census_year"] == "2022"


def test_the_reference_is_collapsed_onto_the_saps_categories(reference):
    """Like compared with like, or the model looks small for no reason.

    SAPS tops out at "8 or more rooms" and the model reads that as 8. F2063
    goes to "10 or more". A county mean that counted nine- and ten-room
    dwellings at their true size would be compared against a model that cannot
    express them.
    """
    for dtype, block in reference.items():
        if dtype == "_reference":
            continue
        rooms = [int(r) for r in block["share_by_rooms"]]
        assert max(rooms) <= SAPS_ROOM_CAP, (
            f"{dtype} carries a {max(rooms)}-room class the model's marginal "
            f"cannot express"
        )
        # Shares are stored rounded to six decimals over up to eight
        # classes, so the sum can miss one by a few times 5e-7. The
        # tolerance is that rounding, not a modelling allowance.
        assert abs(sum(block["share_by_rooms"].values()) - 1.0) < 1e-5


def test_both_apartment_categories_are_counted(reference):
    """The census splits purpose-built from converted; the model has one type."""
    assert len(TYPE_MAP["apartment"]) == 2
    assert reference["apartment"]["n_dwellings"] > 5_000


# --------------------------------------------------------------------------- #
# the town
# --------------------------------------------------------------------------- #

def test_the_town_passes_the_joint_check(town_joint):
    """The I-031 fix, validated against external data for the first time.

    The fix was judged by a feasibility test (what room/bedroom combinations
    are possible). This judges it against what Cork County's dwellings
    actually are.
    """
    dt, rm = town_joint
    rec = rooms_by_dwelling_type_acceptance(dt, rm)
    assert rec["passed"], rec["per_dwelling_type"]
    assert rec["ordering_ok"] is True
    assert rec["levels_ok"] is True
    assert rec["gradient"]["passed"] is True


def test_every_dwelling_type_is_within_a_room_of_the_county(town_joint):
    dt, rm = town_joint
    rec = rooms_by_dwelling_type_acceptance(dt, rm)
    for row in rec["per_dwelling_type"]:
        if row["delta_rooms"] is None:
            continue
        assert abs(row["delta_rooms"]) <= LEVEL_TOLERANCE_ROOMS, row


def test_the_declared_room_allocation_strength_reproduces_most_of_the_gradient(
    town_joint,
):
    """What the check is actually for.

    ROOM_ALLOCATION_STRENGTH was set as a judgement - "strong without making
    room count a function of type". This measures the consequence of that
    judgement against the census, and the measurement is the point of the
    test: the number is recorded here so a future change to the constant
    cannot quietly move it.
    """
    dt, rm = town_joint
    g = rooms_by_dwelling_type_acceptance(dt, rm)["gradient"]
    share = g["share_of_census_gradient"]
    assert share >= MIN_GRADIENT_SHARE
    assert 0.80 <= share <= 0.95, (
        f"the modelled gradient is {share:.3f} of the census gradient, "
        f"outside the 0.80-0.95 this was measured at. Above 1.0 would mean "
        f"room count has become nearly a function of dwelling type, which "
        f"real stock is not; well below would be drifting back towards the "
        f"independent draw."
    )


# --------------------------------------------------------------------------- #
# the fault it exists to catch
# --------------------------------------------------------------------------- #

def test_independence_is_rejected_with_every_marginal_intact(town_joint):
    """I-031's regime, on the town's own room multiset.

    The shuffle keeps the rooms marginal and the dwelling-type marginal
    exactly as published - only the pairing changes. That is precisely the
    fault that shipped, and precisely what a marginal check cannot see.
    """
    dt, rm = town_joint
    independent = sorted(rm, key=lambda r: (r * 7919) % 104729)
    rec = rooms_by_dwelling_type_acceptance(dt, independent)
    assert not rec["passed"]
    assert sorted(independent) == sorted(rm), "the multiset must be untouched"
    assert rec["gradient"]["share_of_census_gradient"] < MIN_GRADIENT_SHARE


def test_an_inverted_joint_is_rejected(town_joint):
    """Apartments larger than detached houses: I-031's shape, exaggerated."""
    dt, rm = town_joint
    order = sorted(range(len(dt)), key=lambda i: rm[i])
    inverted = list(rm)
    # Give the apartments the largest room counts.
    apts = [i for i in order if dt[i] == "apartment"]
    biggest = sorted(rm, reverse=True)[: len(apts)]
    for i, v in zip(apts, biggest):
        inverted[i] = v
    rec = rooms_by_dwelling_type_acceptance(dt, inverted)
    assert not rec["passed"]
    assert rec["ordering_ok"] is False


def test_the_check_declares_it_may_not_be_used_to_tune(town_joint):
    """Validation, not calibration - the HAS02 rule (I-040)."""
    dt, rm = town_joint
    rec = rooms_by_dwelling_type_acceptance(dt, rm)
    assert rec["intended_use"] == "validation"
    assert "ROOM_ALLOCATION_STRENGTH" in rec["may_not_be_used_to_tune"]
    assert rec["tolerance"]["declared_before_measuring"] is True


def test_mismatched_inputs_are_refused():
    with pytest.raises(ValueError, match="same length"):
        rooms_by_dwelling_type_acceptance(["detached"], [4, 5])
