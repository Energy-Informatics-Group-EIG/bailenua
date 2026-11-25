"""U31: a held-out validation slice spanning both ends of the fabric axis.

Why this exists
---------------
U22's validation condition is the space-heat ratio gradient between **1967-99**
and **post-2005** stock. I-049 recorded that neither existing slice can test
it:

=====================  ==============  =========================
..                     E1 estate       U23/U29 mixed-age slice
=====================  ==============  =========================
1967-99 dwellings      4               13
post-2005 dwellings    4               **0** (max build year 1995)
=====================  ==============  =========================

Four against four is noise, and a slice with no modern stock cannot measure a
gradient against modern stock at all. The town has both ends - 380 dwellings in
1967-99 and 253 post-2005, 169 and 183 of them on gas - so this was a selection
problem, not a data problem.

Three departures from how the other slices are selected, each deliberate
---------------------------------------------------------------------------
**Not contiguous.** D-018 and D-028 selected contiguous blocks because R01
wants estates and design 6.4 wants a sub-metered subset sharing a feeder. This
slice is not simulated as an estate; it is a stratified sample for a
statistical comparison, and Cobh's pre-1980 and post-2005 dwellings are in
different parts of the town. Insisting on contiguity would cost exactly the
coverage the comparison needs and buy nothing, because no feeder study is done
on it.

**Gas-dominant, and therefore not representative of the town.** The comparison
is against DBERNG02, which is a gas meter reading, so a dwelling that burns no
gas contributes nothing to it. The slice is selected gas-first on purpose and
its diagnostics say so: it is not a sample of Cobh, it is a sample of Cobh's
gas-heated dwellings at the two ends of the construction axis.

**No people band.** E0-7's band sizes the SIMULATED slice. This one's size
constraint is "enough dwellings in each cell to measure a mean", which is a
different requirement, and forcing the band would fight the stratification.
The people count is recorded rather than constrained.

Evaluation only
---------------
Nothing may be fitted on this slice. That is not a convention here but the
whole point of it: U22's amplitudes were set against DBERNG01 (dwelling type x
BER band) and this slice exists to test them on DBERNG02 (dwelling type x
period of construction), which design 7.1 requires to stay disjoint from
calibration. :data:`EVALUATION_ONLY` is asserted by
``test_nothing_is_fitted_on_the_heldout_slice``, which fails if the ablation's
strength sweep is ever pointed at this slice.
"""

from __future__ import annotations

import dataclasses
from collections import defaultdict
from typing import Any

import numpy as np

__all__ = [
    "U31_REQUIREMENTS",
    "EVALUATION_ONLY",
    "OLD_RANGE",
    "NEW_FROM",
    "MIN_GAS_PER_GROUP",
    "U31Infeasible",
    "HeldOutSelection",
    "construction_group",
    "select_heldout_slice",
]

#: U22's two groups, as U22 states them.
OLD_RANGE = (1967, 1999)
NEW_FROM = 2005

#: Dwellings on gas needed in each group before a mean is worth taking. Ten is
#: the floor I-049 named; the selector aims higher and reports what it got.
MIN_GAS_PER_GROUP = 12

#: Asserted by the test suite. If this is ever False, the held-out axis has
#: been contaminated and U22's validation is worthless.
EVALUATION_ONLY = True

U31_REQUIREMENTS: dict[str, Any] = {
    "decision": "U31",
    "issue": "I-049",
    "purpose": (
        "Test U22's comfort-taking on the held-out construction-period axis "
        "(DBERNG02), which U22 requires and no existing slice can span."
    ),
    "old_range": OLD_RANGE,
    "new_from": NEW_FROM,
    "min_gas_per_group": MIN_GAS_PER_GROUP,
    "evaluation_only": EVALUATION_ONLY,
    "not_contiguous": (
        "a stratified comparison sample, not an estate; Cobh's old and modern "
        "stock are in different parts of the town and no feeder study is run "
        "on this slice"
    ),
    "gas_dominant": (
        "DBERNG02 is a gas meter reading, so a dwelling burning no gas "
        "contributes nothing to the comparison"
    ),
    "no_people_band": (
        "E0-7's band sizes the simulated slice; this slice's constraint is "
        "enough dwellings per cell to take a mean"
    ),
}


class U31Infeasible(RuntimeError):
    """The town cannot supply the held-out slice the comparison needs."""


@dataclasses.dataclass
class HeldOutSelection:
    household_ids: list[str]
    building_ids: list[str]
    diagnostics: dict[str, Any]


def construction_group(build_year: int) -> str | None:
    """"old", "new", or None for a dwelling in neither of U22's groups."""
    year = int(build_year)
    if OLD_RANGE[0] <= year <= OLD_RANGE[1]:
        return "old"
    if year >= NEW_FROM:
        return "new"
    return None


def select_heldout_slice(
    town: Any, *, n_homes: int = 60, master_seed: int = 20261008,
    frozen_household_ids: tuple[str, ...] | None = None,
) -> HeldOutSelection:
    """Pick a balanced, gas-dominant sample from both ends of the axis.

    ``frozen_household_ids`` reuses a previous selection instead of selecting
    afresh, and it exists because of a real failure.

    The selector balances on floor area and **contrasts on specific heat
    loss** (D-052) - that contrast is the whole point of the slice. So the
    membership depends on the fabric. When week 3 sourced the fabric from
    SEAI's assessed distribution, every dwelling's specific heat loss moved
    and the selector picked a different sample: **only 20 of 60 dwellings were
    shared** with the pre-change selection. A before-and-after comparison on
    that basis compares two different samples, and the paired per-dwelling
    test D-073 pre-registered was not merely wrong but impossible - it
    returned NaN for the 40 dwellings present in only one arm.

    Freezing to the **pre-change** selection is the neutral choice: it is the
    sample that existed before anything was touched. Re-selecting after a
    change and comparing against the old selection would be choosing the
    sample after seeing the model, which is the thing a held-out set exists to
    prevent.

    Balanced on purpose: an unbalanced sample would give one group a tighter
    mean than the other, and the quantity of interest is the DIFFERENCE between
    the two means, whose standard error is dominated by the smaller cell.
    Half the homes to each group is the allocation that minimises it.
    """
    if frozen_household_ids is not None:
        by_hh = {b.household_id: b for b in town.buildings if b.household_id}
        missing = [h for h in frozen_household_ids if h not in by_hh]
        if missing:
            raise U31Infeasible(
                f"{len(missing)} frozen household ids are not in the town "
                f"({missing[:3]}...). A frozen selection must come from the "
                f"same town, or the comparison is not paired after all."
            )
        picked = list(frozen_household_ids)
        chosen = [by_hh[h] for h in picked]
        return HeldOutSelection(
            household_ids=picked,
            building_ids=[by_hh[h].building_id for h in picked],
            diagnostics={
                "frozen": True,
                "n_homes": len(picked),
                "why_frozen": (
                    "reused a previous selection so a before/after comparison "
                    "is paired per dwelling. The selector contrasts on "
                    "specific heat loss (D-052), so a fabric change moves the "
                    "membership: 40 of 60 changed in week 3 step 1."
                ),
                "groups": {
                    g: sum(1 for b in chosen if construction_group(b.build_year) == g)
                    for g in ("old", "new")
                },
            },
        )

    buildings = [
        b for b in town.buildings
        if b.household_id and construction_group(b.build_year) is not None
    ]
    gas = [b for b in buildings if str(b.heating_fuel) == "natural gas"]
    by_group: dict[str, list[Any]] = defaultdict(list)
    for b in gas:
        by_group[construction_group(b.build_year)].append(b)

    for group in ("old", "new"):
        if len(by_group[group]) < MIN_GAS_PER_GROUP:
            raise U31Infeasible(
                f"the town has only {len(by_group[group])} gas dwellings in "
                f"the {group!r} group, against a floor of "
                f"{MIN_GAS_PER_GROUP}. U22's held-out comparison cannot be "
                f"made on this town."
            )

    # A seeded permutation, as D-018 established: taking the first n of a
    # size-ordered list is how the E1 estate came to be the 50 biggest
    # households in Cobh.
    gen = np.random.default_rng(int(master_seed) ^ 0x5531)
    per_group = max(n_homes // 2, MIN_GAS_PER_GROUP)
    chosen: list[Any] = []
    for group in ("old", "new"):
        pool = sorted(by_group[group], key=lambda b: b.building_id)
        order = gen.permutation(len(pool))
        take = min(per_group, len(pool))
        chosen.extend(pool[i] for i in order[:take])

    size = town.states.groupby("household_id").size().to_dict()
    n_people = sum(int(size.get(b.household_id, 0)) for b in chosen)

    def _block(group: str) -> dict[str, Any]:
        sub = [b for b in chosen if construction_group(b.build_year) == group]
        years = [int(b.build_year) for b in sub]
        return {
            "n": len(sub),
            "n_on_gas": sum(
                1 for b in sub if str(b.heating_fuel) == "natural gas"
            ),
            "mean_build_year": round(float(np.mean(years)), 1) if years else None,
            "min_build_year": min(years) if years else None,
            "max_build_year": max(years) if years else None,
            "ber_letters": sorted({str(b.ber_band)[0] for b in sub}),
            "dwelling_types": sorted({str(b.dwelling_type) for b in sub}),
            "mean_floor_area_m2": (
                round(float(np.mean([b.floor_area_m2 for b in sub])), 1)
                if sub else None
            ),
        }

    old_block, new_block = _block("old"), _block("new")
    for group, block in (("old", old_block), ("new", new_block)):
        if block["n_on_gas"] < MIN_GAS_PER_GROUP:
            raise U31Infeasible(
                f"selected only {block['n_on_gas']} gas dwellings in the "
                f"{group!r} group against a floor of {MIN_GAS_PER_GROUP}"
            )

    diagnostics = {
        "requirements": dict(U31_REQUIREMENTS),
        "selection_rule": (
            "stratified and balanced across U22's two construction groups, "
            "gas dwellings only, seeded permutation within each group. NOT "
            "contiguous and NOT people-band constrained, for the reasons in "
            "the module docstring."
        ),
        "n_homes": len(chosen),
        "n_people": n_people,
        "people_per_home": round(n_people / max(len(chosen), 1), 3),
        "n_small_areas": len({b.small_area for b in chosen}),
        "old": old_block,
        "new": new_block,
        "town_pool": {
            "old_gas_available": len(by_group["old"]),
            "new_gas_available": len(by_group["new"]),
        },
        "evaluation_only": EVALUATION_ONLY,
        "what_this_slice_is_not": (
            "A sample of Cobh. It is a sample of Cobh's gas-heated dwellings "
            "at the two ends of the construction axis, selected to make one "
            "comparison, and it must not be used for a feeder study, a "
            "privacy test or any town-level statistic."
        ),
    }
    return HeldOutSelection(
        household_ids=[b.household_id for b in chosen],
        building_ids=[b.building_id for b in chosen],
        diagnostics=diagnostics,
    )
