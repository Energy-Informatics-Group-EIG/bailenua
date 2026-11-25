"""Tests for dwelling geometry: floor area, rooms and bedrooms (I-031).

The fault these catch was invisible for five days because nothing compared a
dwelling's size to anything. SAPS publishes room counts and no areas, so the
metres-squared-per-room relationship was assumed - and the apartment value was
assumed *larger* than a detached house's, which put the town's apartment median
above its terraced median and produced a 285.7 m2 three-bedroom flat. That flat
then drew 13.6 MWh a year of space heat, which is what finally surfaced it,
through the one electrically heated home in the estate.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import baile_nua.sources_registry  # noqa: F401  (declares the sources)
from baile_nua.calibration.targets import floor_area_target
from baile_nua.population import saps
from baile_nua.population.buildings import (
    AREA_PER_ROOM_M2,
    DWELLING_SIZE_RANK,
    MIN_ROOMS_OVER_BEDROOMS,
    _apportion,
    allocate_rooms,
)


def test_area_per_room_decreases_with_dwelling_size():
    """An apartment's rooms are smaller than a detached house's.

    The fault was an apartment at 26.0 m2 a room against a detached house at
    24.0. Stated as an ordering rather than as values, because the values are
    declared assumptions and the ordering is not in doubt.
    """
    order = ["bedsit", "apartment", "terraced", "semi-detached", "detached"]
    areas = [AREA_PER_ROOM_M2[k] for k in order]
    assert areas == sorted(areas), (
        f"area per room must not decrease with dwelling size: "
        f"{dict(zip(order, areas))}"
    )
    assert AREA_PER_ROOM_M2["apartment"] < AREA_PER_ROOM_M2["detached"]


def test_room_and_bedroom_marginals_support_the_declared_margin():
    """MIN_ROOMS_OVER_BEDROOMS must be feasible against the published data.

    This is the test that set the value. The first value was 2, on a
    recollection of what the Census's rooms question excludes; the optimal rank
    pairing of Cobh's own room and bedroom marginals makes a margin of 2
    infeasible for about 15% of dwellings and a margin of 0 infeasible for
    0.04%. A constraint the data denies would force the synthesis to break a
    published marginal to satisfy it.
    """
    m = saps.build_marginals()
    rooms_m = m["rooms"].by_small_area
    beds_m = m["bedrooms"].by_small_area

    def numeric(label: str) -> int:
        return 8 if str(label).endswith("+") else int(label)

    total = infeasible = 0
    for sa in rooms_m.index:
        r_counts = rooms_m.loc[sa].drop(labels=["not stated"], errors="ignore")
        b_counts = beds_m.loc[sa].drop(labels=["not stated"], errors="ignore")
        n = int(round(r_counts.sum()))
        if n <= 0:
            continue
        # Sorting both ascending and pairing rank for rank is the assignment
        # that MAXIMISES satisfaction, so a violation here is the data's.
        r = sorted(numeric(x) for x in _apportion(r_counts, n))
        b = sorted(numeric(x) for x in _apportion(b_counts, n))
        k = min(len(r), len(b))
        total += k
        infeasible += sum(
            1 for i in range(k) if r[i] < b[i] + MIN_ROOMS_OVER_BEDROOMS
        )
    rate = infeasible / max(total, 1)
    assert rate <= 0.01, (
        f"a margin of {MIN_ROOMS_OVER_BEDROOMS} is infeasible for {rate:.1%} of "
        f"dwellings ({infeasible} of {total}) even under the optimal pairing of "
        f"the published marginals. Either the margin is wrong about what the "
        f"Census counts, or satisfying it requires breaking a marginal."
    )


def test_allocate_rooms_preserves_the_marginal_exactly():
    """The allocation is a permutation: no published count is created or lost."""
    gen = np.random.default_rng(7)
    labels = ["1", "2", "2", "3", "4", "5", "5", "6", "7", "8+"]
    types = ["apartment", "apartment", "terraced", "terraced", "semi-detached",
             "semi-detached", "detached", "detached", "detached", "apartment"]
    beds = [1, 2, 2, 3, 3, 3, 4, 4, 5, 1]
    out = allocate_rooms(labels, dwelling_types=types, bedrooms=beds, gen=gen)
    assert sorted(out) == sorted(labels), (
        "the room marginal changed: the allocation must only permute labels"
    )
    assert len(out) == len(types)


def test_allocate_rooms_gives_apartments_fewer_rooms_than_detached_houses():
    gen = np.random.default_rng(11)
    n = 200
    labels = [str(1 + i % 7) for i in range(n)]
    types = (["apartment"] * (n // 2)) + (["detached"] * (n - n // 2))
    beds = [2] * (n // 2) + [4] * (n - n // 2)
    out = allocate_rooms(labels, dwelling_types=types, bedrooms=beds, gen=gen)

    def numeric(label: str) -> int:
        return 8 if label.endswith("+") else int(label)

    apt = np.mean([numeric(out[i]) for i in range(n) if types[i] == "apartment"])
    det = np.mean([numeric(out[i]) for i in range(n) if types[i] == "detached"])
    assert apt < det, f"apartments got {apt:.2f} rooms against detached {det:.2f}"


def test_allocate_rooms_is_deterministic_for_a_given_generator_state():
    labels = [str(1 + i % 6) for i in range(60)]
    types = ["apartment", "terraced", "detached"] * 20
    beds = [1, 2, 4] * 20
    a = allocate_rooms(labels, dwelling_types=types, bedrooms=beds,
                       gen=np.random.default_rng(3))
    b = allocate_rooms(labels, dwelling_types=types, bedrooms=beds,
                       gen=np.random.default_rng(3))
    assert a == b


@pytest.mark.slow
def test_the_synthesised_town_has_plausible_dwelling_geometry():
    """The whole-town check, against TRS05 and against dwelling-type ordering."""
    from baile_nua.population.synthesise import synthesise_t0

    town = synthesise_t0(master_seed=20261008)
    f = pd.DataFrame([
        {"type": b.dwelling_type, "fa": b.floor_area_m2,
         "rooms": b.rooms, "beds": b.bedrooms}
        for b in town.buildings
    ])

    # No dwelling may have fewer rooms than bedrooms.
    bad = f[f.rooms < f.beds + MIN_ROOMS_OVER_BEDROOMS]
    assert bad.empty, (
        f"{len(bad)} dwellings have fewer than bedrooms+"
        f"{MIN_ROOMS_OVER_BEDROOMS} rooms:\n{bad.head().to_string()}"
    )

    # Median floor area must increase with dwelling size.
    med = f.groupby("type").fa.median()
    order = [t for t in ("apartment", "terraced", "semi-detached", "detached")
             if t in med.index]
    values = [float(med[t]) for t in order]
    assert values == sorted(values), (
        f"median floor area must increase with dwelling size: "
        f"{dict(zip(order, [round(v, 1) for v in values]))}"
    )

    # Against the only public Irish figure: a LOWER bound, because rentals are
    # smaller and more apartment-heavy than the whole stock.
    bound = float(floor_area_target().value)
    town_median = float(f.fa.median())
    assert town_median > bound, (
        f"the town median floor area is {town_median:.1f} m2, at or below "
        f"TRS05's Co. Cork RENTAL median of {bound} m2. Rentals skew smaller, "
        f"so the whole stock should sit above it."
    )
    assert town_median < 2.0 * bound, (
        f"the town median floor area is {town_median:.1f} m2, more than twice "
        f"TRS05's rental median of {bound} m2, which no plausible "
        f"owner-occupied premium explains."
    )

    # An apartment the size of a detached house is the specific fault of I-031.
    assert float(f[f.type == "apartment"].fa.max()) < 200.0, (
        f"the largest apartment is {f[f.type == 'apartment'].fa.max():.1f} m2"
    )


def test_dwelling_size_rank_covers_every_schema_dwelling_type():
    """Every declared dwelling type must have a size rank and an area per room.

    Read from ``Schema.enums``, not from the field's own ``enum`` attribute:
    that attribute holds the enum's NAME ("dwelling_type"), and iterating it
    yields its characters. The first version of this test did exactly that,
    compared a set of single letters against the size ranks, and then - when
    pointed at ``enum_values``, which is None - compared the empty set and
    passed vacuously. A test that cannot fail is worse than no test, because it
    reads as coverage.
    """
    from baile_nua.schema import load

    declared = set(load().enums["dwelling_type"])
    assert declared, "the dwelling_type enum resolved to nothing"
    assert "apartment" in declared and "detached" in declared, (
        f"the dwelling_type enum does not look like dwelling types: {declared}"
    )
    missing_rank = declared - set(DWELLING_SIZE_RANK)
    assert not missing_rank, (
        f"these dwelling types have no size rank, so allocate_rooms would "
        f"treat them as mid-sized by default: {sorted(missing_rank)}"
    )
    missing_area = declared - set(AREA_PER_ROOM_M2)
    assert not missing_area, (
        f"these dwelling types have no area per room, so their floor area "
        f"would fall back to a default: {sorted(missing_area)}"
    )
