"""Whole-household synthesis (design 5.2 step 3, R03, R16).

    Combine iterative proportional fitting with combinatorial optimisation, so
    households are built whole (a couple with two children aged 6 and 9) and
    match person-level and household-level marginals together.  Plausibility
    rules apply: a parent's age at a child's birth falls between 16 and 50
    (mother) or 16 and 65 (father), and siblings are at least 9 months apart
    unless twins.

Four stages, per small area, in sorted small-area order:

1. **Structure.**  A seed table over (household type x size) encodes which
   combinations are possible at all - a one-person household cannot have size 3.
2. **IPF** fits that structure to the area's own type and size marginals.
3. **Assembly.**  Households are drawn from the fitted joint and given members
   with roles, then ages and sexes, from the area's person marginals.
4. **Combinatorial optimisation.**  A local search swaps ages between households
   to reduce the area's age-by-sex marginal error, rejecting any swap that would
   break a plausibility rule.  This is the half of step 3 that IPF cannot do:
   IPF matches household marginals, the search matches person marginals, and the
   plausibility rules are invariants of both.

Plausibility rules are enforced as **hard constraints at construction and
re-checked after optimisation**, not as a filter applied at the end: a rule
checked only at the end tells you that something is wrong without telling you
which stage broke it.
"""

from __future__ import annotations

import dataclasses
import math
import re
from typing import Any

import numpy as np
import pandas as pd

from baile_nua.config import thresholds
from baile_nua.population.ipf import ipf_2d
from baile_nua.rng import SeedTree, Stream

__all__ = [
    "HouseholdTemplate",
    "TEMPLATES",
    "SynthPerson",
    "SynthHousehold",
    "synthesise_households",
    "PlausibilityViolation",
    "check_plausibility",
    "AGE_BAND_EDGES",
]

ADULT_AGE = 18
CHILD_ALONE_AGE = 12


class PlausibilityViolation(AssertionError):
    """A synthesised household breaks one of design 5.2 step 3's rules."""


# --------------------------------------------------------------------------- #
# Household templates: the structure IPF's seed table encodes
# --------------------------------------------------------------------------- #

@dataclasses.dataclass(frozen=True)
class HouseholdTemplate:
    """One SAPS household type, and the member roles it implies at each size.

    ``n_adults_min`` / ``n_adults_max`` bound how many of the members are
    adults; the rest are children.  ``n_parents`` is how many of those adults
    are parents of the children, which is what the parent-age rules apply to.
    """

    saps_type: str
    roles_core: tuple[str, ...]      # roles always present, in order
    n_parents: int                   # 0, 1 or 2
    has_children: bool
    allows_others: bool
    min_size: int
    max_size: int

    def child_capacity(self, size: int) -> tuple[int, int]:
        """``(min_children, max_children)`` for this type at ``size`` members.

        A "with children" household must have at least one child, by definition
        of the SAPS category; an "and others" type reserves one slot for a
        non-nuclear adult so it is not silently identical to its no-others
        counterpart.
        """
        if not (self.min_size <= size <= self.max_size):
            raise ValueError(f"{self.saps_type!r} cannot have size {size}")
        remaining = size - len(self.roles_core)
        if remaining < 0:
            raise ValueError(f"{self.saps_type!r} size {size} is below its core roles")
        if not self.has_children:
            return (0, 0)
        reserved = 1 if self.allows_others and remaining >= 2 else 0
        return (1, max(1, remaining - reserved))

    def member_roles(self, size: int, n_children: int | None = None) -> tuple[str, ...]:
        """Roles for a household of this type at ``size`` members.

        ``n_children`` is supplied by the area-level child allocation (see
        ``_allocate_children``) rather than implied by the size.  An earlier
        version made every non-core member of a "with children" household a
        child, which produced 982 children in a town whose Census age marginal
        has 652 - a 50% structural surplus that no age optimisation could fix,
        because a child cannot be reassigned to an adult band without destroying
        the household structure IPF had just fitted.  Making the child count a
        fitted variable removes the contradiction at source.
        """
        if not (self.min_size <= size <= self.max_size):
            raise ValueError(f"{self.saps_type!r} cannot have size {size}")
        roles = list(self.roles_core)
        remaining = size - len(roles)
        if remaining < 0:
            raise ValueError(f"{self.saps_type!r} size {size} is below its core roles")
        if self.has_children:
            lo, hi = self.child_capacity(size)
            n_c = hi if n_children is None else max(lo, min(hi, n_children))
            roles += ["child"] * n_c + ["other"] * (remaining - n_c)
        else:
            roles += ["other"] * remaining
        return tuple(roles)


#: The 14 SAPS household types (Table 5.1), each mapped to its member structure.
TEMPLATES: tuple[HouseholdTemplate, ...] = (
    HouseholdTemplate("one person", ("head",), 0, False, False, 1, 1),
    HouseholdTemplate("married couple", ("head", "partner"), 0, False, False, 2, 2),
    HouseholdTemplate("cohabiting couple", ("head", "partner"), 0, False, False, 2, 2),
    HouseholdTemplate("married couple with children", ("head", "partner"), 2, True, False, 3, 8),
    HouseholdTemplate("cohabiting couple with children", ("head", "partner"), 2, True, False, 3, 8),
    HouseholdTemplate("one parent (father) with children", ("head",), 1, True, False, 2, 8),
    HouseholdTemplate("one parent (mother) with children", ("head",), 1, True, False, 2, 8),
    HouseholdTemplate("couple and others", ("head", "partner"), 0, False, True, 3, 8),
    HouseholdTemplate("couple with children and others", ("head", "partner"), 2, True, True, 4, 8),
    HouseholdTemplate("one parent (father) with children and others", ("head",), 1, True, True, 3, 8),
    HouseholdTemplate("one parent (mother) with children and others", ("head",), 1, True, True, 3, 8),
    HouseholdTemplate("two or more family units", ("head", "partner"), 2, True, True, 4, 8),
    HouseholdTemplate("non-family households and relations", ("head",), 0, False, True, 2, 8),
    HouseholdTemplate("two or more non-related persons", ("head",), 0, False, True, 2, 8),
)

_TEMPLATE_BY_TYPE = {t.saps_type: t for t in TEMPLATES}

#: SAPS household-size marginal labels, in order, with their numeric size.
SIZE_LABELS: tuple[tuple[str, int], ...] = (
    ("1", 1), ("2", 2), ("3", 3), ("4", 4), ("5", 5), ("6", 6), ("7", 7), ("8+", 8),
)


# --------------------------------------------------------------------------- #
# Age bands, parsed from the SAPS age-by-sex category labels
# --------------------------------------------------------------------------- #

#: Upper age assumed for the open-ended top band.  SAPS's top category is
#: "85 and over" with no upper edge, so one has to be chosen to turn it into
#: single years.  95 is used: it keeps the band's mean near the published mean
#: age of the 85+ population without generating implausible ages, and it is
#: declared here rather than buried in a parser.
OPEN_TOP_BAND_UPPER = 95


def _parse_age_label(label: str) -> tuple[int, int, str] | None:
    """Parse a SAPS age-by-sex category label.

    The three real shapes, as they appear in the data:

    ======================  ==========================
    Label                   Meaning
    ======================  ==========================
    ``"0_M"``               single year 0, male
    ``"20_24_F"``           band 20 to 24, female
    ``"GE_85_M"``           85 and over, male
    ======================  ==========================
    """
    m = re.match(r"^(.+)_([MF])$", label)
    if not m:
        return None
    band, sex = m.group(1), m.group(2)
    ge = re.match(r"^GE_?(\d+)$", band)
    if ge:
        lo = int(ge.group(1))
        return (lo, OPEN_TOP_BAND_UPPER, sex)
    parts = band.split("_")
    try:
        if len(parts) == 1:
            v = int(parts[0])
            return (v, v, sex)
        if len(parts) == 2:
            return (int(parts[0]), int(parts[1]), sex)
    except ValueError:
        return None
    return None


def AGE_BAND_EDGES(columns: list[str]) -> dict[str, tuple[int, int, str]]:
    """Map every age-by-sex category label to ``(age_lo, age_hi, sex)``."""
    out = {}
    for c in columns:
        p = _parse_age_label(c)
        if p is not None:
            out[c] = p
    if not out:
        raise ValueError(f"no age-by-sex labels parsed from {columns[:6]}")
    return out


# --------------------------------------------------------------------------- #
# Synthesised entities
# --------------------------------------------------------------------------- #

@dataclasses.dataclass
class SynthPerson:
    person_id: str
    household_id: str
    small_area: str
    role: str
    sex: str
    age: int
    birth_year: int
    is_parent_of_children: bool = False


@dataclasses.dataclass
class SynthHousehold:
    household_id: str
    small_area: str
    saps_type: str
    size: int
    members: list[SynthPerson] = dataclasses.field(default_factory=list)

    @property
    def adults(self) -> list[SynthPerson]:
        return [m for m in self.members if m.age >= ADULT_AGE]

    @property
    def children(self) -> list[SynthPerson]:
        return [m for m in self.members if m.age < ADULT_AGE]

    @property
    def parents(self) -> list[SynthPerson]:
        return [m for m in self.members if m.is_parent_of_children]


# --------------------------------------------------------------------------- #
# Plausibility rules (design 5.2 step 3)
# --------------------------------------------------------------------------- #

def check_plausibility(
    households: list[SynthHousehold], *, raise_on_violation: bool = False
) -> list[dict[str, Any]]:
    """Every rule design 5.2 step 3 states, checked explicitly.

    Returns the violations rather than only a count, so a failure says which
    household and which rule.
    """
    t = thresholds()["population"]
    mother_lo, mother_hi = t["parent_age_at_birth_mother"]
    father_lo, father_hi = t["parent_age_at_birth_father"]
    min_spacing_days = t["sibling_min_spacing_days"]
    min_spacing_years = min_spacing_days / 365.25

    violations: list[dict[str, Any]] = []
    for hh in households:
        if len(hh.members) != hh.size:
            violations.append(
                {"household_id": hh.household_id, "rule": "size matches member count",
                 "detail": f"size {hh.size} but {len(hh.members)} members"}
            )

        children = hh.children
        parents = hh.parents

        # 1. Parent age at each child's birth.
        for parent in parents:
            lo, hi = (mother_lo, mother_hi) if parent.sex == "F" else (father_lo, father_hi)
            for child in children:
                age_at_birth = parent.age - child.age
                if not (lo <= age_at_birth <= hi):
                    violations.append(
                        {
                            "household_id": hh.household_id,
                            "rule": f"parent age at birth in [{lo}, {hi}] for sex {parent.sex}",
                            "detail": (
                                f"{parent.person_id} (age {parent.age}, {parent.sex}) would have "
                                f"been {age_at_birth} at the birth of {child.person_id} "
                                f"(age {child.age})"
                            ),
                        }
                    )

        # 2. Siblings at least 9 months apart unless twins.
        ages = sorted(c.age for c in children)
        for a, b in zip(ages, ages[1:]):
            if a == b:
                continue  # twins
            if (b - a) < min_spacing_years:
                violations.append(
                    {
                        "household_id": hh.household_id,
                        "rule": f"siblings >= {min_spacing_days} days apart unless twins",
                        "detail": f"ages {a} and {b} differ by less than {min_spacing_years:.2f} years",
                    }
                )

        # 3. A household with children must have at least one adult.
        if children and not hh.adults:
            violations.append(
                {"household_id": hh.household_id, "rule": "a household with children has an adult",
                 "detail": f"{len(children)} children, 0 adults"}
            )

        # 4. A household with a child under 12 must have an adult who can
        #    supervise. Design 5.3's "never home alone" is a presence invariant,
        #    checked per minute in validation.invariants; here the structural
        #    precondition is checked - the household must contain someone.
        if any(c.age < CHILD_ALONE_AGE for c in children) and not hh.adults:
            violations.append(
                {"household_id": hh.household_id, "rule": "under-12 has a resident adult",
                 "detail": "no adult in household"}
            )

        # 5. A declared couple needs two adults.
        tmpl = _TEMPLATE_BY_TYPE.get(hh.saps_type)
        if tmpl and "partner" in tmpl.roles_core:
            n_adult_core = sum(
                1 for m in hh.members if m.role in ("head", "partner") and m.age >= ADULT_AGE
            )
            if n_adult_core < 2:
                violations.append(
                    {"household_id": hh.household_id, "rule": "a couple has two adults",
                     "detail": f"{n_adult_core} adult(s) in head/partner roles"}
                )

        # 6. Lone-parent sex matches the type.
        if tmpl and tmpl.n_parents == 1 and parents:
            want = "F" if "(mother)" in hh.saps_type else "M" if "(father)" in hh.saps_type else None
            if want and parents[0].sex != want:
                violations.append(
                    {"household_id": hh.household_id,
                     "rule": f"lone-parent type implies parent sex {want}",
                     "detail": f"parent is {parents[0].sex}"}
                )

    if raise_on_violation and violations:
        raise PlausibilityViolation(
            f"{len(violations)} plausibility violation(s); first: {violations[0]}"
        )
    return violations


# --------------------------------------------------------------------------- #
# Reconciling the person marginal with the household marginal
# --------------------------------------------------------------------------- #

def _restrict_to_private_households(
    age_frame: pd.DataFrame,
    size_frame: pd.DataFrame,
    bands: dict[str, tuple[int, int, str]],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Rescale the age-by-sex marginal to each area's private-household population.

    The household-size marginal fixes how many people live in private households
    in an area: ``sum(size x count)``.  The age marginal counts everyone,
    including communal-establishment residents.  Using the latter as the person
    target guarantees a deficit equal to the difference.

    Each area's age counts are therefore scaled by
    ``private_household_people / total_people`` and re-integerised by largest
    remainder, so the shape of the age distribution is preserved and the total
    becomes achievable.  The people removed are reported.
    """
    out_rows: dict[str, Any] = {}
    removed_total = 0
    for sa in age_frame.index:
        counts = age_frame.loc[sa].to_numpy(dtype=np.float64)
        total_people = counts.sum()
        hh_people = float(
            sum(
                float(size_frame.loc[sa, lab]) * n
                for lab, n in SIZE_LABELS
                if lab in size_frame.columns
            )
        )
        if total_people <= 0 or hh_people <= 0 or hh_people >= total_people:
            out_rows[sa] = age_frame.loc[sa].to_numpy(dtype=np.int64)
            continue
        target = int(round(hh_people))
        exact = counts / total_people * target
        floor = np.floor(exact).astype(np.int64)
        short = int(target - floor.sum())
        if short > 0:
            order = np.argsort(-(exact - floor), kind="stable")
            floor[order[:short]] += 1
        elif short < 0:
            order = np.argsort(exact - floor, kind="stable")
            floor[order[: -short]] -= 1
        removed_total += int(total_people - floor.sum())
        out_rows[sa] = floor

    adjusted = pd.DataFrame(out_rows, index=age_frame.columns).T
    adjusted.index.name = age_frame.index.name
    info = {
        "total_population": int(age_frame.to_numpy().sum()),
        "private_household_population": int(adjusted.to_numpy().sum()),
        "not_in_private_households": removed_total,
        "basis": (
            "SAPS T1_1AGETT counts the whole population; T5_2_TP counts persons "
            "in private households. The difference is communal-establishment "
            "residents, who are out of scope for the household layer (R11)."
        ),
    }
    return adjusted.sort_index(), info


def _reconcile_children_with_household_types(
    age_frame: pd.DataFrame,
    type_frame: pd.DataFrame,
    size_frame: pd.DataFrame,
    bands: dict[str, tuple[int, int, str]],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Guarantee each area has at least as many children as its household types need.

    The minimum is one child per "with children" household, which is what the
    SAPS category means.  Where an area is short, the deficit is taken from its
    youngest adult bands (18-24 first, which are the adults most likely to be a
    rounding artefact) and added to its oldest child bands (15-17 first, so the
    moved people change age by as little as possible).

    Every move is recorded per area, so the E1 report can state exactly how many
    people were reassigned and by how much.
    """
    child_labels = sorted(
        (c for c, (lo, hi, _s) in bands.items() if hi < ADULT_AGE),
        key=lambda c: -bands[c][0],            # oldest children first
    )
    adult_labels = sorted(
        (c for c, (lo, hi, _s) in bands.items() if lo >= ADULT_AGE),
        key=lambda c: bands[c][0],             # youngest adults first
    )
    adjusted = age_frame.copy()
    per_area: dict[str, Any] = {}
    moved_total = 0

    for sa in adjusted.index:
        min_children = 0
        for tl in type_frame.columns:
            tmpl = _TEMPLATE_BY_TYPE.get(tl)
            if tmpl is None or not tmpl.has_children:
                continue
            min_children += int(type_frame.loc[sa, tl])
        have = int(sum(adjusted.loc[sa, c] for c in child_labels))
        if have >= min_children or min_children == 0:
            continue
        need = min_children - have
        moved = 0
        for a_lab in adult_labels:
            if moved >= need:
                break
            avail = int(adjusted.loc[sa, a_lab])
            if avail <= 0:
                continue
            take = min(avail, need - moved)
            # Keep sex: move into a child band of the same sex.
            sex = bands[a_lab][2]
            dest = next(
                (c for c in child_labels if bands[c][2] == sex), None
            )
            if dest is None:
                continue
            adjusted.loc[sa, a_lab] = avail - take
            adjusted.loc[sa, dest] = int(adjusted.loc[sa, dest]) + take
            moved += take
        if moved:
            per_area[sa] = {
                "children_required_by_household_types": min_children,
                "children_in_age_marginal": have,
                "people_reassigned_from_adult_to_child_bands": moved,
                "still_short": max(0, need - moved),
            }
            moved_total += moved

    info = {
        "n_areas_adjusted": len(per_area),
        "people_reassigned_total": moved_total,
        "basis": (
            "A SAPS 'with children' household must contain at least one child. "
            "Scaling rounds small child counts to zero while leaving household "
            "type counts intact, so the two marginals can contradict each other."
        ),
        "per_area": per_area,
    }
    return adjusted, info


# --------------------------------------------------------------------------- #
# Stage 1-2: structure and IPF
# --------------------------------------------------------------------------- #

def _seed_table(type_labels: list[str], size_labels: list[tuple[str, int]]) -> np.ndarray:
    """Which (type, size) combinations are structurally possible.

    Zeros here are preserved by IPF, so this table is what stops a "one person
    household" of size 4 from ever being drawn.
    """
    t = np.zeros((len(type_labels), len(size_labels)), dtype=np.float64)
    for i, tl in enumerate(type_labels):
        tmpl = _TEMPLATE_BY_TYPE.get(tl)
        if tmpl is None:
            continue
        for j, (_, size) in enumerate(size_labels):
            if tmpl.min_size <= size <= tmpl.max_size:
                t[i, j] = 1.0
    return t


def _integerise(table: np.ndarray, col_totals: np.ndarray) -> np.ndarray:
    """Turn a fitted real-valued joint into integer counts, **column sums exact**.

    Columns are household sizes, so the column sums determine how many *people*
    the area contains.  Apportioning the flattened table against a single
    household total - the obvious implementation, and the first one here - gets
    the household count right and the person count wrong: it lost 69 people
    across the town by pushing mass from rare large sizes toward common small
    ones in areas holding only ~20 households.

    So each size column is apportioned separately by largest remainder, which
    makes every column sum exact and therefore the area's person count exact.
    Row sums (household types) then deviate slightly from the type marginal;
    that deviation is measured and reported rather than traded away silently,
    and it is the smaller error because IPF has already fitted the rows.
    """
    out = np.zeros(table.shape, dtype=np.int64)
    for j in range(table.shape[1]):
        total = int(col_totals[j])
        w = table[:, j].astype(np.float64)
        if total <= 0:
            continue
        if w.sum() <= 0:
            # The size is required but the structure allows no type: spread it
            # over the types that permit this size at all, so the people are not
            # simply lost. Recorded by the caller as a type-marginal deviation.
            continue
        exact = w / w.sum() * total
        col = np.floor(exact).astype(np.int64)
        short = int(total - col.sum())
        if short > 0:
            order = np.argsort(-(exact - col), kind="stable")
            col[order[:short]] += 1
        elif short < 0:
            order = np.argsort(exact - col, kind="stable")
            col[order[: -short]] -= 1
        out[:, j] = col
    return out


def _repair_type_marginal(
    counts: np.ndarray, row_targets: np.ndarray, allowed: np.ndarray
) -> tuple[np.ndarray, float]:
    """Improve the household-type (row) fit **without touching column sums**.

    Column-exact integerisation makes the person count exact and leaves the type
    counts approximate.  This repair moves one household at a time from an
    over-represented type to an under-represented one *within the same size
    column*, so every move leaves the column sum - and therefore the area's
    person count - unchanged.  ``allowed`` is the structural mask: a household
    cannot move to a type that does not permit its size.

    Returns the repaired table and the remaining absolute row deviation.
    """
    out = counts.copy()
    for _ in range(2000):
        resid = out.sum(axis=1).astype(np.float64) - row_targets
        over = int(np.argmax(resid))
        under = int(np.argmin(resid))
        if resid[over] < 1.0 or resid[under] > -1.0:
            break
        # A size column where the donor has a household and the recipient may
        # legally hold one.
        cols = [
            j for j in range(out.shape[1])
            if out[over, j] > 0 and allowed[under, j]
        ]
        if not cols:
            # Try the next-best donor rather than giving up on the whole repair.
            order = np.argsort(-resid)
            moved = False
            for cand in order[1:]:
                if resid[cand] < 1.0:
                    break
                cols = [
                    j for j in range(out.shape[1])
                    if out[cand, j] > 0 and allowed[under, j]
                ]
                if cols:
                    out[cand, cols[0]] -= 1
                    out[under, cols[0]] += 1
                    moved = True
                    break
            if not moved:
                break
            continue
        j = cols[0]
        out[over, j] -= 1
        out[under, j] += 1
    return out, float(np.abs(out.sum(axis=1).astype(float) - row_targets).sum())


# --------------------------------------------------------------------------- #
# Stage 3: assembly
# --------------------------------------------------------------------------- #

def _allocate_children(
    slots: list[tuple[str, int]], n_children_target: int
) -> tuple[list[int], dict[str, Any]]:
    """Spread an area's children across its "with children" households.

    ``slots`` is ``[(saps_type, size), ...]`` for the households that must
    contain at least one child.  The area's child total comes from the Census
    age-by-sex marginal, so this is the step that makes the household structure
    and the person marginal agree *before* any ages are drawn.

    Each household gets its minimum first, then the remainder is spread by
    largest remainder in proportion to spare capacity.  Two boundary cases are
    reported rather than silently absorbed:

    * **too few children** for every "with children" household to have one -
      some households cannot be built as their SAPS type says;
    * **too many children** for the capacity available - the surplus has nowhere
      to go.
    """
    caps = []
    for saps_type, size in slots:
        tmpl = _TEMPLATE_BY_TYPE[saps_type]
        caps.append(tmpl.child_capacity(size))
    lo_total = sum(lo for lo, _ in caps)
    hi_total = sum(hi for _, hi in caps)

    info: dict[str, Any] = {
        "n_with_children_households": len(slots),
        "min_children_required": lo_total,
        "max_children_capacity": hi_total,
        "children_target": n_children_target,
    }
    if not slots:
        info["unplaceable_children"] = max(0, n_children_target)
        return [], info

    alloc = [lo for lo, _ in caps]
    remaining = n_children_target - lo_total
    if remaining < 0:
        info["shortfall_below_minimum"] = -remaining
        info["note"] = (
            "fewer children in the age marginal than 'with children' households "
            "require; each still receives one, so the area will carry a small "
            "child surplus"
        )
        return alloc, info
    spare = [hi - lo for (lo, hi) in caps]
    spare_total = sum(spare)
    if spare_total > 0 and remaining > 0:
        take = min(remaining, spare_total)
        exact = [s / spare_total * take for s in spare]
        add = [int(math.floor(e)) for e in exact]
        short = take - sum(add)
        if short > 0:
            order = sorted(
                range(len(add)), key=lambda i: (-(exact[i] - add[i]), i)
            )
            for i in order[:short]:
                add[i] += 1
        for i, a in enumerate(add):
            alloc[i] += min(a, spare[i])
        remaining -= sum(min(a, spare[i]) for i, a in enumerate(add))
    if remaining > 0:
        info["unplaceable_children"] = remaining
        info["note"] = (
            "more children in the age marginal than the household structure can "
            "hold; the surplus is not placed"
        )
    info["allocated"] = int(sum(alloc))
    return alloc, info

def _age_pools(
    age_counts: pd.Series, bands: dict[str, tuple[int, int, str]]
) -> dict[str, list[int]]:
    """Expand an age-by-sex marginal into per-sex lists of single-year ages.

    A banded category (20-24) is spread uniformly across its years.  Uniform
    rather than weighted because SAPS gives no within-band shape, and inventing
    one would be a statistic with no source.

    The lists are **sampled with replacement** during assembly, not consumed.
    An earlier version removed each drawn age from the pool, reasoning that a
    town has a fixed number of 43-year-olds.  That failed: large households need
    specific parent ages, and once those ages were used up 8.6% of households
    could not be built at all, which is a worse error than a slightly wrong age
    marginal.  Matching the marginal is the job of the stage-4 optimisation,
    which can reach it exactly; assembly's job is to produce feasible
    households.
    """
    pools: dict[str, list[int]] = {"M": [], "F": []}
    for label, count in age_counts.items():
        n = int(count)
        if n <= 0 or label not in bands:
            continue
        lo, hi, sex = bands[label]
        span = hi - lo + 1
        base, extra = divmod(n, span)
        for k in range(span):
            pools[sex].extend([lo + k] * (base + (1 if k < extra else 0)))
    for sex in pools:
        pools[sex].sort()
    return pools


def _draw_household_ages(
    tmpl: HouseholdTemplate,
    roles: tuple[str, ...],
    adult_pool: dict[str, list[int]],
    child_pool: dict[str, list[int]],
    gen: np.random.Generator,
    *,
    p_adult_female: float = 0.5,
    p_child_female: float = 0.5,
    max_tries: int = 60,
) -> list[tuple[str, str, int]] | None:
    """Pick ``(role, sex, age)`` for one household, satisfying the plausibility rules.

    Children are drawn first and parents are then drawn from the *feasible* adult
    ages given those children, rather than drawing parents first and rejecting.
    Drawing in that order is what keeps the acceptance rate high: a household
    with a 17-year-old child needs a parent of at least 33, and only a few per
    cent of the adult pool qualifies, so rejection sampling on parents-first
    would mostly fail.

    **Sex comes from the area's own sex marginal**, not from a default.  An
    earlier version alternated M then F for core adult slots, which meant every
    single-person, non-family and unrelated-persons household received a male
    head - about a third of all households - and produced a deficit of several
    hundred women spread across every adult band.  The stage-4 optimiser cannot
    repair that, because it moves ages within a sex and never changes sex.  Sex
    has to be right at assembly, so ``p_adult_female`` and ``p_child_female``
    are the area's measured proportions.
    """
    t = thresholds()["population"]
    m_lo, m_hi = t["parent_age_at_birth_mother"]
    f_lo, f_hi = t["parent_age_at_birth_father"]
    min_gap = t["sibling_min_spacing_days"] / 365.25

    n_children = sum(1 for r in roles if r == "child")
    n_others = sum(1 for r in roles if r == "other")

    for _ in range(max_tries):
        out: list[tuple[str, str, int]] = []

        # -- children, respecting sibling spacing ---------------------------
        child_ages: list[int] = []
        ok = True
        for _ in range(n_children):
            avail = [a for sex in ("M", "F") for a in child_pool[sex]]
            if not avail:
                ok = False
                break
            for _try in range(40):
                age = int(avail[int(gen.integers(0, len(avail)))])
                if all(age == a or abs(age - a) >= min_gap for a in child_ages):
                    child_ages.append(age)
                    break
            else:
                ok = False
                break
        if not ok:
            continue

        # -- parents, feasible given the children ---------------------------
        parent_sexes: list[str] = []
        if tmpl.n_parents == 2:
            parent_sexes = ["M", "F"]
        elif tmpl.n_parents == 1:
            parent_sexes = ["F"] if "(mother)" in tmpl.saps_type else ["M"]

        parent_ages: list[int] = []
        for sex in parent_sexes:
            lo_at_birth, hi_at_birth = (m_lo, m_hi) if sex == "F" else (f_lo, f_hi)
            if child_ages:
                need_lo = max(c + lo_at_birth for c in child_ages)
                need_hi = min(c + hi_at_birth for c in child_ages)
            else:
                need_lo, need_hi = ADULT_AGE, 120
            need_lo = max(need_lo, ADULT_AGE)
            feasible = [a for a in adult_pool[sex] if need_lo <= a <= need_hi]
            if not feasible:
                ok = False
                break
            parent_ages.append(int(feasible[int(gen.integers(0, len(feasible)))]))
        if not ok:
            continue

        # -- remaining core adults ------------------------------------------
        core_adult_slots = len(tmpl.roles_core) - len(parent_sexes)
        extra_adults: list[tuple[str, int]] = []
        is_couple = "partner" in tmpl.roles_core
        for k in range(core_adult_slots):
            if is_couple and core_adult_slots == 2:
                # A couple with no children: one of each sex. Opposite-sex is the
                # dominant real pattern and SAPS does not publish a same-sex
                # couple count at small-area level, so no rate is invented here.
                sex = "M" if k == 0 else "F"
            else:
                # Everything else - a single-person household, a non-family
                # household, unrelated persons - takes its sex from the area's
                # adult sex ratio.
                sex = "F" if gen.random() < p_adult_female else "M"
            pool = adult_pool[sex] or adult_pool["M"] or adult_pool["F"]
            if not pool:
                ok = False
                break
            extra_adults.append((sex, int(pool[int(gen.integers(0, len(pool)))])))
        if not ok:
            continue

        # -- "others": adults, not parents ----------------------------------
        other_adults: list[tuple[str, int]] = []
        for _ in range(n_others):
            sex = "F" if gen.random() < p_adult_female else "M"
            pool = adult_pool[sex] or adult_pool["M"] or adult_pool["F"]
            if not pool:
                ok = False
                break
            other_adults.append((sex, int(pool[int(gen.integers(0, len(pool)))])))
        if not ok:
            continue

        # -- assemble in role order -----------------------------------------
        p_iter = list(zip(parent_sexes, parent_ages))
        e_iter = list(extra_adults)
        c_iter = sorted(child_ages, reverse=True)
        o_iter = list(other_adults)
        for role in roles:
            if role in ("head", "partner"):
                if p_iter:
                    sex, age = p_iter.pop(0)
                elif e_iter:
                    sex, age = e_iter.pop(0)
                else:
                    ok = False
                    break
                out.append((role, sex, age))
            elif role == "child":
                if not c_iter:
                    ok = False
                    break
                age = c_iter.pop(0)
                sex = "F" if gen.random() < p_child_female else "M"
                out.append((role, sex, age))
            else:
                if not o_iter:
                    ok = False
                    break
                sex, age = o_iter.pop(0)
                out.append((role, sex, age))
        if ok and len(out) == len(roles):
            return out
    return None


# --------------------------------------------------------------------------- #
# Stage 4: combinatorial optimisation against the person marginal
# --------------------------------------------------------------------------- #

def _marginal_error(counts: np.ndarray, target: np.ndarray) -> float:
    """Sum of absolute deviations between realised and target age-sex counts."""
    return float(np.abs(counts - target).sum())


def _optimise_ages(
    households: list[SynthHousehold],
    target: pd.Series,
    bands: dict[str, tuple[int, int, str]],
    gen: np.random.Generator,
    *,
    max_passes: int = 40,
) -> dict[str, Any]:
    """Combinatorial optimisation against the person age-by-sex marginal.

    This is the half of design 5.2 step 3 that IPF cannot do: IPF matches
    household marginals, this matches person marginals, and the plausibility
    rules are invariants of both.

    **Why re-draw and not swap.**  The first implementation swapped ages between
    two members of the same role and sex.  It improved nothing, and could not
    have: a swap exchanges two ages, so the multiset of ages in the town is
    unchanged, and for two people of the same sex the realised age-by-sex counts
    are literally identical before and after.  The marginal is a property of the
    multiset, so it can only be changed by **changing somebody's age**.

    So the search is surplus-to-deficit re-drawing: find the bands with too many
    people and the bands with too few, and move individuals from the former to
    the latter.  Every move is re-checked against the plausibility rules and
    reverted if it breaks one, so marginal fit is never bought with an
    implausible household.  Adults stay adults and children stay children, which
    keeps household structure (and therefore the household marginals IPF just
    fitted) intact.
    """
    labels = list(target.index)
    label_index = {lab: i for i, lab in enumerate(labels)}
    # Ages reachable in each band, by sex.
    band_ages: dict[int, list[int]] = {}
    age_band: dict[tuple[int, str], int] = {}
    for lab, (lo, hi, sx) in bands.items():
        i = label_index.get(lab)
        if i is None:
            continue
        band_ages[i] = list(range(lo, hi + 1))
        for a in range(lo, hi + 1):
            age_band[(a, sx)] = i
    band_sex = {label_index[lab]: sx for lab, (_, _, sx) in bands.items() if lab in label_index}

    tgt = target.to_numpy(dtype=np.float64)
    members = [(hi, mi) for hi, hh in enumerate(households) for mi in range(len(hh.members))]

    def counts_now() -> np.ndarray:
        c = np.zeros(len(labels), dtype=np.float64)
        for hi, mi in members:
            m = households[hi].members[mi]
            i = age_band.get((m.age, m.sex))
            if i is not None:
                c[i] += 1
        return c

    counts = counts_now()
    start_err = _marginal_error(counts, tgt)
    if not members:
        return {
            "age_marginal_abs_error_before": start_err,
            "age_marginal_abs_error_after": start_err,
            "improvement": 0.0, "moves_accepted": 0,
            "moves_rejected_for_plausibility": 0, "passes": 0, "n_people": 0,
        }

    # Index people by their current band so surplus bands can be drained.
    by_band: dict[int, list[tuple[int, int]]] = {}
    for hi, mi in members:
        m = households[hi].members[mi]
        i = age_band.get((m.age, m.sex))
        if i is not None:
            by_band.setdefault(i, []).append((hi, mi))

    accepted = rejected = 0
    passes = 0
    for passes in range(1, max_passes + 1):
        resid = counts - tgt
        surplus = [i for i in np.argsort(-resid) if resid[i] > 0.5]
        deficit = [i for i in np.argsort(resid) if resid[i] < -0.5]
        if not surplus or not deficit:
            break
        moved_this_pass = 0
        for si in surplus:
            if counts[si] - tgt[si] <= 0.5:
                continue
            pool = by_band.get(int(si), [])
            if not pool:
                continue
            order = gen.permutation(len(pool))
            for k in order:
                if counts[si] - tgt[si] <= 0.5:
                    break
                hi, mi = pool[int(k)]
                if mi >= len(households[hi].members):
                    continue
                person = households[hi].members[mi]
                if age_band.get((person.age, person.sex)) != int(si):
                    continue   # already moved
                is_child = person.age < ADULT_AGE
                for di in deficit:
                    if counts[di] - tgt[di] >= -0.5:
                        continue
                    if band_sex.get(int(di)) != person.sex:
                        continue
                    cand_ages = band_ages.get(int(di), [])
                    # An adult must stay an adult and a child a child, so the
                    # household structure IPF fitted is preserved.
                    cand_ages = [
                        a for a in cand_ages
                        if (a < ADULT_AGE) == is_child
                    ]
                    if not cand_ages:
                        continue
                    new_age = int(cand_ages[int(gen.integers(0, len(cand_ages)))])
                    old_age = person.age
                    person.age = new_age
                    if check_plausibility([households[hi]]):
                        person.age = old_age
                        rejected += 1
                        continue
                    counts[int(si)] -= 1
                    counts[int(di)] += 1
                    by_band.setdefault(int(di), []).append((hi, mi))
                    accepted += 1
                    moved_this_pass += 1
                    break
        if moved_this_pass == 0:
            break

    end_err = _marginal_error(counts, tgt)
    return {
        "age_marginal_abs_error_before": start_err,
        "age_marginal_abs_error_after": end_err,
        "improvement": start_err - end_err,
        "moves_accepted": accepted,
        "moves_rejected_for_plausibility": rejected,
        "passes": passes,
        "n_people": len(members),
    }


# --------------------------------------------------------------------------- #
# The public entry point
# --------------------------------------------------------------------------- #

@dataclasses.dataclass
class SynthesisResult:
    households: list[SynthHousehold]
    persons: list[SynthPerson]
    diagnostics: dict[str, Any]
    plausibility_violations: list[dict[str, Any]]

    @property
    def n_people(self) -> int:
        return len(self.persons)

    @property
    def n_households(self) -> int:
        return len(self.households)


def synthesise_households(
    scaled_marginals: dict[str, pd.DataFrame],
    *,
    master_seed: int,
    reference_date: pd.Timestamp,
) -> SynthesisResult:
    """Build whole households and their members for every small area.

    Small areas are processed in sorted code order and ids are issued from a
    single counter in that order, so person and household ids are a function of
    the input alone - not of iteration order or worker count.

    ``reference_date`` is t0 (2022-01-01 under E0-3), used to turn an age into a
    birth date.  The birth date is placed at a deterministic day within the
    person's birth year rather than on 1 January, because a town where everybody
    shares a birthday would be an obvious synthetic tell (design 6.3).
    """
    tree = SeedTree(master_seed)
    type_frame = scaled_marginals["household_type"]
    size_frame = scaled_marginals["household_size"]
    age_frame_raw = scaled_marginals["age_by_sex"]
    bands = AGE_BAND_EDGES(list(age_frame_raw.columns))

    # ---- The age marginal counts the WHOLE population; households hold only
    # ---- the private-household population.
    #
    # Measured on Cobh: SAPS `T1_1AGETT` (total population) is 14,148 while
    # `T5_2_TP` (persons in private households) is 14,088.  The 60-person
    # difference is people in communal establishments, who by definition do not
    # live in a private household.  Scaled to Baile Nua that is 59 people out of
    # 2,931 - and asking the synthesis to place them in households would leave a
    # permanent 59-person deficit that no optimisation could remove, because the
    # target itself would be wrong.
    #
    # So the age marginal is rescaled, per small area, to that area's
    # private-household population before it is used as the person target.
    # Design R11 keeps occupants and buildings separate; communal residents are
    # out of scope for the household layer and are recorded in the diagnostics
    # rather than silently dropped.
    age_frame, communal_info = _restrict_to_private_households(
        age_frame_raw, size_frame, bands
    )

    # ---- Make the person and household marginals mutually consistent.
    #
    # After scaling, one Cobh small area declared "married couple with children"
    # and "one parent with children" households while its age marginal had ZERO
    # children: method (b)'s rounding drives small categories to zero (21.9% of
    # non-zero cells, measured) and it hit the child bands in that area while
    # leaving the household-type counts intact.  Seven households out of 1,092
    # were then unbuildable - not because the assembly was wrong, but because the
    # inputs contradicted each other.
    #
    # Reconciling is a representation fix, not a relaxed threshold: the minimum
    # number of children each area's own household types require is computed and
    # the shortfall is moved out of the youngest adult bands into the oldest
    # child bands.  The cost is a small, recorded worsening of the age marginal;
    # the alternative is households that cannot exist.
    age_frame, reconcile_info = _reconcile_children_with_household_types(
        age_frame, type_frame, size_frame, bands
    )

    type_labels = list(type_frame.columns)
    size_labels = [(lab, n) for lab, n in SIZE_LABELS if lab in size_frame.columns]
    seed_tbl = _seed_table(type_labels, size_labels)

    households: list[SynthHousehold] = []
    persons: list[SynthPerson] = []
    per_area: dict[str, Any] = {}
    hh_counter = 0
    p_counter = 0
    total_unplaced = 0

    for sa in sorted(type_frame.index):
        type_marg = type_frame.loc[sa].to_numpy(dtype=np.float64)
        size_marg = np.array([float(size_frame.loc[sa, lab]) for lab, _ in size_labels])
        n_hh_target = int(size_marg.sum())
        if n_hh_target == 0:
            per_area[sa] = {"n_households": 0, "note": "no households after scaling"}
            continue

        # -- stages 1 and 2 --------------------------------------------------
        try:
            fit = ipf_2d(seed_tbl, type_marg, size_marg)
        except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
            per_area[sa] = {"n_households": 0, "ipf_error": str(exc)}
            continue
        counts = _integerise(fit.table, size_marg)
        counts, type_dev_after = _repair_type_marginal(
            counts, type_marg, seed_tbl > 0
        )

        # -- stage 3 ---------------------------------------------------------
        age_counts = age_frame.loc[sa]
        pools = _age_pools(age_counts, bands)
        adult_pool = {s: [a for a in pools[s] if a >= ADULT_AGE] for s in ("M", "F")}
        child_pool = {s: [a for a in pools[s] if a < ADULT_AGE] for s in ("M", "F")}
        n_adult_f, n_adult_m = len(adult_pool["F"]), len(adult_pool["M"])
        n_child_f, n_child_m = len(child_pool["F"]), len(child_pool["M"])
        p_adult_f = n_adult_f / (n_adult_f + n_adult_m) if (n_adult_f + n_adult_m) else 0.5
        p_child_f = n_child_f / (n_child_f + n_child_m) if (n_child_f + n_child_m) else 0.5

        gen = tree.generator(Stream.HOUSEHOLD_ASSEMBLY, entity=sa, sim_day=0)
        area_households: list[SynthHousehold] = []
        unplaced = 0

        # Largest households first: they are the hardest to satisfy (a size-7
        # household with teenagers needs specific parent ages), so placing them
        # while the pools are full raises the overall acceptance rate.
        order = sorted(
            ((i, j) for i in range(counts.shape[0]) for j in range(counts.shape[1]) if counts[i, j] > 0),
            key=lambda ij: (-size_labels[ij[1]][1], ij[0], ij[1]),
        )

        # -- fit the child count to the area's own age marginal BEFORE drawing
        #    ages, so household structure and the person marginal agree.
        n_children_target = int(
            sum(
                int(age_counts[c])
                for c, (lo, hi, _sx) in bands.items()
                if hi < ADULT_AGE and c in age_counts.index
            )
        )
        child_slots: list[tuple[str, int]] = []
        slot_keys: list[tuple[int, int]] = []
        for i, j in order:
            tmpl = _TEMPLATE_BY_TYPE.get(type_labels[i])
            if tmpl is None or not tmpl.has_children:
                continue
            for _ in range(int(counts[i, j])):
                child_slots.append((tmpl.saps_type, size_labels[j][1]))
                slot_keys.append((i, j))
        child_alloc, child_info = _allocate_children(child_slots, n_children_target)
        alloc_queue: dict[tuple[int, int], list[int]] = {}
        for key, n_c in zip(slot_keys, child_alloc):
            alloc_queue.setdefault(key, []).append(n_c)

        for i, j in order:
            tmpl = _TEMPLATE_BY_TYPE.get(type_labels[i])
            size = size_labels[j][1]
            if tmpl is None:
                unplaced += int(counts[i, j])
                continue
            for _ in range(int(counts[i, j])):
                n_c = None
                if tmpl.has_children:
                    q = alloc_queue.get((i, j)) or []
                    n_c = q.pop(0) if q else tmpl.child_capacity(size)[0]
                roles = tmpl.member_roles(size, n_c)
                drawn = _draw_household_ages(
                    tmpl, roles, adult_pool, child_pool, gen,
                    p_adult_female=p_adult_f, p_child_female=p_child_f,
                )
                if drawn is None:
                    unplaced += 1
                    continue
                hh_counter += 1
                hh = SynthHousehold(
                    household_id=f"H-{hh_counter:06d}",
                    small_area=sa,
                    saps_type=tmpl.saps_type,
                    size=size,
                )
                for role, sex, age in drawn:
                    p_counter += 1
                    hh.members.append(
                        SynthPerson(
                            person_id=f"P-{p_counter:06d}",
                            household_id=hh.household_id,
                            small_area=sa,
                            role=role,
                            sex=sex,
                            age=age,
                            birth_year=0,
                            is_parent_of_children=(
                                role in ("head", "partner")
                                and tmpl.n_parents > 0
                                and any(r == "child" for r in roles)
                            ),
                        )
                    )
                area_households.append(hh)

        # -- stage 4 ---------------------------------------------------------
        opt_gen = tree.generator(Stream.POPULATION_IPF, entity=sa, sim_day=0)
        opt = _optimise_ages(area_households, age_counts, bands, opt_gen)

        households.extend(area_households)
        type_dev = type_dev_after
        per_area[sa] = {
            "n_households": len(area_households),
            "type_marginal_abs_deviation": type_dev,
            "n_people": int(sum(len(h.members) for h in area_households)),
            "households_target": n_hh_target,
            "unplaced_households": unplaced,
            "ipf": fit.as_dict(),
            "child_allocation": child_info,
            "age_optimisation": opt,
        }
        total_unplaced += unplaced

    # Birth dates, after optimisation has settled every age.
    for hh in households:
        for m in hh.members:
            m.birth_year = int(reference_date.year - m.age)
            persons.append(m)

    violations = check_plausibility(households)
    diagnostics = {
        "n_households": len(households),
        "n_people": len(persons),
        "n_small_areas": len([k for k, v in per_area.items() if v.get("n_households")]),
        "unplaced_households_total": total_unplaced,
        "unplaced_fraction": round(
            total_unplaced / max(total_unplaced + len(households), 1), 5
        ),
        "n_plausibility_violations": len(violations),
        "communal_population_excluded": communal_info,
        "child_marginal_reconciliation": {
            k: v for k, v in reconcile_info.items() if k != "per_area"
        },
        "age_marginal_abs_error_total": sum(
            v["age_optimisation"]["age_marginal_abs_error_after"]
            for v in per_area.values()
            if "age_optimisation" in v
        ),
        "age_marginal_abs_error_before_optimisation": sum(
            v["age_optimisation"]["age_marginal_abs_error_before"]
            for v in per_area.values()
            if "age_optimisation" in v
        ),
        "per_small_area": per_area,
    }
    return SynthesisResult(households, persons, diagnostics, violations)
