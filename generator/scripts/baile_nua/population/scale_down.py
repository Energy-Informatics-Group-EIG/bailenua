"""U03: scaling Cobh to about 3,000 people — both methods (E0-1, design 5.2 step 2).

E0-1, as approved:

    Build both methods (whole small areas, stratified; and proportional
    scaling), compare joint **and** spatial error, recommend one in the E1
    report.

Design 5.2 step 2 and review-2 finding A4 are explicit that marginals alone are
not enough:

    Validation covers marginals and also the joint and spatial structure:
    household composition by age of members, age-economic status-tenure
    dependencies, car ownership by household type, commuting accessibility, and
    spatial segregation indices across estates.  The method with the smaller
    joint-distribution error is recommended.

**What is measurable, and what is not.**  SAPS publishes marginals per small
area, not individual-level joint tables, so a true joint distribution for Cobh
does not exist in the public data and cannot be the yardstick.  What *is*
available, and what A4 is really about, is the **between-small-area structure**:
within one small area the marginal categories co-occur, so across the 53 areas
there is a real covariance between (say) social renting and no-car households.
That covariance is the joint structure the two methods treat differently:

* **Method (a), whole small areas sampled with stratification**, keeps each
  retained area's own joint signature exactly intact, but represents the town
  with a subsample of areas, so it can miss or over-weight an area type.
* **Method (b), proportional scaling of all small areas**, keeps every area and
  therefore the full spatial extent, but multiplies each area's counts by a
  common factor and rounds, which smooths small categories toward zero and
  flattens the between-area contrast.

Both are built here.  Neither is privileged in code; the recommendation comes
from the measurement in :mod:`baile_nua.population.joint_metrics`.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Literal

import numpy as np
import pandas as pd

from baile_nua.population.saps import Marginal, cobh_small_areas, load_cobh_saps
from baile_nua.reduce import sorted_sum
from baile_nua.rng import SeedTree, Stream

__all__ = [
    "ScaleDownPlan",
    "Method",
    "ScaleTargetError",
    "feasible_scale_factor",
    "scale_whole_areas_stratified",
    "scale_proportional",
    "build_both",
    "TARGET_PEOPLE",
    "TARGET_HOMES_RANGE",
]

Method = Literal["whole_area_stratified", "proportional"]

#: R03: "about 3,000 people (about 1,000 to 1,100 homes)".
#: Design 12 R03 acceptance: 2,900 to 3,100 people; 1,000 to 1,100 homes.
TARGET_PEOPLE = 3000
TARGET_PEOPLE_RANGE = (2900, 3100)
TARGET_HOMES_RANGE = (1000, 1100)


class ScaleTargetError(RuntimeError):
    """R03's two acceptance ranges cannot both be met without distorting the mix."""


def feasible_scale_factor(
    *,
    cobh_people: int,
    cobh_households: int,
    people_range: tuple[int, int] = TARGET_PEOPLE_RANGE,
    homes_range: tuple[int, int] = TARGET_HOMES_RANGE,
) -> tuple[float, dict[str, Any]]:
    """Pick the scale factor from R03's *two* acceptance ranges, not from one number.

    Why this is not simply ``3000 / cobh_people``.  Measured on the real data
    (Census 2022 SAPS, Cobh built-up area): 14,148 people in 5,257 private
    households, so **2.691 persons per household**.  R03 asks for about 3,000
    people *and* 1,000 to 1,100 homes, which implies 2.727 to 3.000 persons per
    household.  Cobh's real ratio is below that band, so:

    * anchoring on 3,000 people gives **1,115 homes** - outside R03's homes range;
    * anchoring on 1,100 homes gives **2,960 people** - inside R03's people range.

    The two constraints are therefore jointly satisfiable, but only over a narrow
    window of scale factors, and the naive "3,000 people" anchor is outside it.
    Forcing both by adjusting household sizes is not an option: R04 requires the
    scale-down to preserve Cobh's mix, and the household-size distribution is one
    of the marginals being preserved.

    So the factor is the **midpoint of the feasible interval**, computed from the
    data each time rather than written down, and an empty interval raises rather
    than silently picking a side.  See DECISIONS.md D-010 and ISSUES.md I-012.
    """
    lo = max(people_range[0] / cobh_people, homes_range[0] / cobh_households)
    hi = min(people_range[1] / cobh_people, homes_range[1] / cobh_households)
    info = {
        "cobh_people": cobh_people,
        "cobh_households": cobh_households,
        "cobh_persons_per_household": round(cobh_people / cobh_households, 4),
        "r03_implied_persons_per_household": [
            round(people_range[0] / homes_range[1], 3),
            round(people_range[1] / homes_range[0], 3),
        ],
        "factor_interval_from_people_range": [
            round(people_range[0] / cobh_people, 6),
            round(people_range[1] / cobh_people, 6),
        ],
        "factor_interval_from_homes_range": [
            round(homes_range[0] / cobh_households, 6),
            round(homes_range[1] / cobh_households, 6),
        ],
        "feasible_factor_interval": [round(lo, 6), round(hi, 6)],
    }
    if lo > hi:
        raise ScaleTargetError(
            f"R03's people range {people_range} and homes range {homes_range} cannot "
            f"both be met at Cobh's real {cobh_people / cobh_households:.3f} persons "
            f"per household without distorting the household-size mix, which R04 "
            f"forbids. Feasible factor interval is empty: "
            f"[{lo:.6f}, {hi:.6f}]. This is a design contradiction, not an "
            f"implementation choice - see ISSUES.md."
        )
    factor = (lo + hi) / 2.0
    info["chosen_factor"] = round(factor, 6)
    info["implied_people"] = int(round(cobh_people * factor))
    info["implied_households"] = int(round(cobh_households * factor))
    return factor, info


@dataclasses.dataclass
class ScaleDownPlan:
    """How many households and people each small area contributes to Baile Nua."""

    method: Method
    #: index = small-area code; columns = households, people, weight
    per_small_area: pd.DataFrame
    #: Scaled marginals, same shape as the originals (category counts).
    marginals: dict[str, pd.DataFrame]
    town_marginals: dict[str, pd.Series]
    n_people: int
    n_households: int
    #: Areas kept (method a may keep a subset; method b keeps all).
    areas_kept: list[str]
    diagnostics: dict[str, Any] = dataclasses.field(default_factory=dict)

    @property
    def meets_r03(self) -> bool:
        return (
            TARGET_PEOPLE_RANGE[0] <= self.n_people <= TARGET_PEOPLE_RANGE[1]
            and TARGET_HOMES_RANGE[0] <= self.n_households <= TARGET_HOMES_RANGE[1]
        )

    def summary(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "n_people": self.n_people,
            "n_households": self.n_households,
            "n_areas_kept": len(self.areas_kept),
            "meets_r03_ranges": self.meets_r03,
            "r03_people_range": list(TARGET_PEOPLE_RANGE),
            "r03_homes_range": list(TARGET_HOMES_RANGE),
            **self.diagnostics,
        }


# --------------------------------------------------------------------------- #
# Integer apportionment
# --------------------------------------------------------------------------- #

def _largest_remainder(values: np.ndarray, total: int) -> np.ndarray:
    """Apportion ``total`` across ``values`` proportionally, as integers.

    Largest-remainder (Hare) apportionment.  Used rather than ``round()``
    because independent rounding does not sum to the target - over 53 areas and
    68 age-sex categories the drift is tens of people, which would break the
    R03 acceptance range for a reason that has nothing to do with the method
    being tested.

    Ties in the remainder are broken by index order, which is small-area code
    order, so the result is deterministic and worker-count independent.
    """
    if total <= 0 or values.sum() <= 0:
        return np.zeros(len(values), dtype=np.int64)
    exact = values.astype(np.float64) / float(values.sum()) * float(total)
    floor = np.floor(exact).astype(np.int64)
    short = int(total - floor.sum())
    if short > 0:
        rema = exact - floor
        # argsort is stable, so equal remainders keep index (id) order
        order = np.argsort(-rema, kind="stable")
        floor[order[:short]] += 1
    elif short < 0:
        rema = exact - floor
        order = np.argsort(rema, kind="stable")
        floor[order[: -short]] -= 1
    return floor


def _is_child_label(label: str) -> bool:
    """True for an age-by-sex category whose whole band is under 18.

    Parsed from the label rather than listed, so a change in CSO banding is
    picked up.  Labels are of the form ``"0_M"``, ``"20_24_F"``, ``"GE_85_M"``.
    """
    import re

    m = re.match(r"^(.+)_[MF]$", label)
    if not m:
        return False
    band = m.group(1)
    if band.startswith("GE"):
        return False
    parts = band.split("_")
    try:
        hi = int(parts[-1]) if len(parts) <= 2 else int(parts[1])
    except ValueError:
        return False
    return hi < 18


#: Numeric household size for each household_size marginal label.
_SIZE_VALUE: dict[str, int] = {
    "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8+": 8,
}


def _repair_person_total(
    counts: np.ndarray, labels: list[str], target_people: int
) -> tuple[np.ndarray, int]:
    """Nudge a household-size distribution to hit a person total exactly.

    Plain largest-remainder apportionment of the size distribution gets the
    *household* count right and the *person* count wrong, and the error is
    systematic rather than random: the rarest categories are the largest
    households, so they round to zero first.  Measured on Cobh at a scale factor
    of 0.207, size-7 households went from 30 to 2 and size-8+ from 15 to **0**,
    pulling mean household size from 2.678 down to 2.630.

    The repair moves one household at a time between adjacent size categories -
    a size-2 becomes a size-3, say - which keeps the household count fixed while
    changing the person count by one.  Moves are taken from the category whose
    share is currently most over-represented, so the distribution's shape is
    disturbed as little as possible.  Returns the repaired counts and the
    residual.
    """
    out = counts.copy()
    sizes = np.array([_SIZE_VALUE.get(l, 0) for l in labels], dtype=np.int64)
    if not sizes.any():
        return out, 0
    for _ in range(10_000):
        people = int((out * sizes).sum())
        gap = target_people - people
        if gap == 0:
            return out, 0
        step = 1 if gap > 0 else -1
        # Prefer moving a household up (or down) one size, from the donor
        # category with the most households, to the adjacent category.
        best = None
        for i in range(len(out)):
            j = i + step
            if not (0 <= j < len(out)):
                continue
            if out[i] <= 0:
                continue
            if sizes[j] - sizes[i] != step:
                continue
            if best is None or out[i] > out[best[0]]:
                best = (i, j)
        if best is None:
            break
        i, j = best
        out[i] -= 1
        out[j] += 1
    people = int((out * sizes).sum())
    return out, target_people - people


def _scale_marginals(
    marginals: dict[str, Marginal],
    area_weights: pd.Series,
    *,
    keep: list[str],
) -> tuple[dict[str, pd.DataFrame], dict[str, pd.Series], dict[str, Any]]:
    """Scale every marginal by per-area weights, keeping integer totals.

    Within each small area, categories are apportioned by largest remainder to
    the area's scaled total, so each area's own category *shares* are preserved
    as closely as integers allow and the area totals are exact.

    The ``household_size`` marginal gets an extra repair pass so that the
    *person* total is preserved as well as the household total - see
    :func:`_repair_person_total` for why plain rounding is not enough.
    """
    out_sa: dict[str, pd.DataFrame] = {}
    out_town: dict[str, pd.Series] = {}
    repair: dict[str, Any] = {"areas_repaired": 0, "residual_people": 0, "moves": 0}
    for key, m in marginals.items():
        src = m.by_small_area.loc[keep]
        labels = list(src.columns)
        rows = {}
        for sa in keep:
            counts = src.loc[sa].to_numpy(dtype=np.float64)
            w = float(area_weights[sa])
            target = int(round(counts.sum() * w))
            if key == "age_by_sex":
                # Apportion children and adults SEPARATELY, each to its own
                # scaled target.
                #
                # Apportioning all 68 age-sex categories against one area total
                # drives most of them to 0 or 1 in an area of ~55 people, and in
                # 20 of Cobh's 53 areas it drove the child categories to zero
                # while leaving the household-type counts intact - so the area
                # declared "with children" households it had no children for.
                # Repairing that afterwards meant moving 68 people from young
                # adult bands into teen bands, which shifted those bands' shares
                # by enough to fail the R04 sampling-error band on its own.
                #
                # Stratifying the apportionment preserves each area's child/adult
                # split exactly, which is the quantity the household structure
                # depends on, and removes the need for the repair.
                child_idx = [
                    i for i, lab in enumerate(labels) if _is_child_label(lab)
                ]
                adult_idx = [i for i in range(len(labels)) if i not in set(child_idx)]
                scaled = np.zeros(len(labels), dtype=np.int64)
                for idx in (child_idx, adult_idx):
                    if not idx:
                        continue
                    sub = counts[idx]
                    sub_target = int(round(sub.sum() * w))
                    scaled[idx] = _largest_remainder(sub, sub_target)
            else:
                scaled = _largest_remainder(counts, target)
            if key == "household_size":
                sizes = np.array([_SIZE_VALUE.get(l, 0) for l in labels], dtype=np.int64)
                people_full = int((counts * sizes).sum())
                people_target = int(round(people_full * w))
                before = int((scaled * sizes).sum())
                scaled, residual = _repair_person_total(scaled, labels, people_target)
                after = int((scaled * sizes).sum())
                if after != before:
                    repair["areas_repaired"] += 1
                    repair["moves"] += abs(after - before)
                repair["residual_people"] += abs(residual)
            rows[sa] = scaled
        frame = pd.DataFrame(rows, index=labels).T
        frame.index.name = src.index.name
        out_sa[key] = frame.sort_index()
        out_town[key] = out_sa[key].sum(axis=0).astype("int64")
    return out_sa, out_town, repair


# --------------------------------------------------------------------------- #
# "Area type" for method (a)'s stratification
# --------------------------------------------------------------------------- #

def _area_type_strata(
    marginals: dict[str, Marginal], saps: pd.DataFrame, sas: pd.DataFrame
) -> pd.Series:
    """Define "area type" from the data, for U03 method (a)'s stratification.

    The obvious stratifier does not work.  SAPS's own urban/rural classification
    (``UR_Category``) is **constant across all 53 of Cobh's small areas** - every
    one is "2. Satellite urban towns" - so stratifying on it would produce a
    single stratum and reduce method (a) to an unstratified random sample.

    The heterogeneity that actually exists in Cobh, measured:

    ======================================  =====================
    Quantity, per small area                 Range across the 53
    ======================================  =====================
    Persons per household                    1.65 to 3.96
    Social-renting share of households       0.00 to 0.74
    People                                   131 to 699
    ======================================  =====================

    So "area type" is defined as **electoral division x tenure tertile**: the
    urban/rural split that does vary, crossed with terciles of the social-renting
    share.  That forces a stratified sample to span both the harbour-front social
    housing and the owner-occupied suburbs, which is the spatial segregation
    design 5.2 step 2 asks to be preserved.

    Tertile edges come from the data, so they move with the data rather than
    being pinned to numbers that happened to hold in 2022.
    """
    tenure = marginals["tenure"].by_small_area
    social_share = (tenure["rented social"] / tenure.sum(axis=1)).fillna(0.0)
    # Rank-based tertiles: robust to the long right tail (one area is 74% social).
    ranks = social_share.rank(method="first", pct=True)
    tertile = pd.cut(
        ranks, bins=[0.0, 1 / 3, 2 / 3, 1.0], labels=["low", "mid", "high"],
        include_lowest=True,
    ).astype(str)
    ed = sas["ed_english"].reindex(social_share.index).fillna("?")
    return (ed + "|social-" + tertile).reindex(saps.index).rename("stratum")


# --------------------------------------------------------------------------- #
# Method (a): whole small areas, sampled with stratification
# --------------------------------------------------------------------------- #

def scale_whole_areas_stratified(
    marginals: dict[str, Marginal],
    *,
    master_seed: int,
    target_people: int | None = None,
) -> ScaleDownPlan:
    """U03 option (a): keep whole small areas, stratified by area type, then reweight.

    Stratification is on the SAPS urban/rural category (``UR_Category``) crossed
    with the electoral division, because those are the two axes along which
    Cobh's 53 areas actually differ: the harbour-front urban core versus the
    rural hinterland.  Within each stratum, areas are drawn without replacement
    in a seeded random order until the stratum's share of the 3,000-person target
    is met.

    "Then reweighted" (the design's own wording) matters: whole areas cannot sum
    to exactly 3,000, so the retained areas carry a common weight that brings the
    total onto target.  The weight is close to 1, which is the point of the
    method - each retained area is close to its real self.
    """
    sas = cobh_small_areas().frame.set_index("sa_code")
    saps = load_cobh_saps().set_index("GEOGID")
    people = marginals["age_by_sex"].by_small_area.sum(axis=1)
    households = marginals["household_size"].by_small_area.sum(axis=1)

    strata = _area_type_strata(marginals, saps, sas)

    total_people = int(people.sum())
    total_households = int(households.sum())
    if target_people is None:
        factor, factor_info = feasible_scale_factor(
            cobh_people=total_people, cobh_households=total_households
        )
        target_people = int(round(total_people * factor))
    else:
        factor_info = {"chosen_factor": target_people / total_people, "override": True}
    tree = SeedTree(master_seed)

    kept: list[str] = []
    per_stratum: dict[str, dict[str, Any]] = {}
    # Fixed stratum order so the result does not depend on dict iteration.
    for stratum in sorted(strata.unique()):
        members = sorted(strata.index[strata == stratum])
        stratum_people = int(people.loc[members].sum())
        # Proportional allocation: each stratum keeps its share of the town.
        stratum_target = stratum_people / total_people * target_people
        gen = tree.generator(Stream.POPULATION_SCALE_DOWN, entity=stratum, sim_day=0)
        order = [members[i] for i in gen.permutation(len(members))]
        taken: list[str] = []
        running = 0.0
        for sa in order:
            if running >= stratum_target:
                break
            taken.append(sa)
            running += float(people.loc[sa])
        # A stratum whose smallest area already overshoots still contributes one
        # area: dropping it entirely would lose that area type from the town,
        # which is exactly the representativeness the method exists to protect.
        if not taken and members:
            taken = [min(members, key=lambda s: people.loc[s])]
            running = float(people.loc[taken[0]])
        kept.extend(taken)
        per_stratum[stratum] = {
            "n_areas_available": len(members),
            "n_areas_kept": len(taken),
            "people_available": stratum_people,
            "people_target": round(stratum_target, 1),
            "people_kept_before_reweight": int(running),
        }

    kept = sorted(kept)
    kept_people = int(people.loc[kept].sum())
    weight = target_people / kept_people if kept_people else 1.0
    weights = pd.Series(weight, index=kept)

    sa_marg, town_marg, repair = _scale_marginals(marginals, weights, keep=kept)
    n_people = int(town_marg["age_by_sex"].sum())
    n_households = int(town_marg["household_size"].sum())

    per_sa = pd.DataFrame(
        {
            "households": sa_marg["household_size"].sum(axis=1),
            "people": sa_marg["age_by_sex"].sum(axis=1),
            "weight": weights,
            "people_full": people.loc[kept],
            "households_full": households.loc[kept],
            "stratum": strata.loc[kept],
        }
    )
    return ScaleDownPlan(
        method="whole_area_stratified",
        per_small_area=per_sa,
        marginals=sa_marg,
        town_marginals=town_marg,
        n_people=n_people,
        n_households=n_households,
        areas_kept=kept,
        diagnostics={
            "n_strata": len(per_stratum),
            "common_reweight_factor": round(weight, 6),
            "people_kept_before_reweight": kept_people,
            "fraction_of_areas_kept": round(len(kept) / len(people), 4),
            "per_stratum": per_stratum,
            "scale_target": factor_info,
            "size_person_total_repair": repair,
            "note": (
                "Each retained small area keeps its own joint signature; the town "
                "is represented by a subsample of areas."
            ),
        },
    )


# --------------------------------------------------------------------------- #
# Method (b): proportional scaling of all small areas
# --------------------------------------------------------------------------- #

def scale_proportional(
    marginals: dict[str, Marginal],
    *,
    target_people: int | None = None,
) -> ScaleDownPlan:
    """U03 option (b): keep every small area, scaled by one common factor.

    No randomness: the method is fully determined by the target, so no stream is
    drawn.  That is itself a difference worth recording - method (a)'s result
    depends on a seed, method (b)'s does not.
    """
    people = marginals["age_by_sex"].by_small_area.sum(axis=1)
    households = marginals["household_size"].by_small_area.sum(axis=1)
    keep = sorted(people.index.tolist())
    if target_people is None:
        factor, factor_info = feasible_scale_factor(
            cobh_people=int(people.sum()), cobh_households=int(households.sum())
        )
    else:
        factor = target_people / float(people.sum())
        factor_info = {"chosen_factor": factor, "override": True}
    weights = pd.Series(factor, index=keep)

    sa_marg, town_marg, repair = _scale_marginals(marginals, weights, keep=keep)
    n_people = int(town_marg["age_by_sex"].sum())
    n_households = int(town_marg["household_size"].sum())

    per_sa = pd.DataFrame(
        {
            "households": sa_marg["household_size"].sum(axis=1),
            "people": sa_marg["age_by_sex"].sum(axis=1),
            "weight": weights,
            "people_full": people.loc[keep],
            "households_full": households.loc[keep],
        }
    )
    # How much small-category detail the rounding destroyed: the share of
    # (area, category) cells that were non-zero in Cobh and are zero after
    # scaling. This is the concrete cost of method (b) and is reported, not hidden.
    zeroed = kept_nonzero = 0
    for key, scaled in sa_marg.items():
        orig = marginals[key].by_small_area.loc[keep]
        nz = orig.to_numpy() > 0
        kept_nonzero += int(nz.sum())
        zeroed += int(((scaled.to_numpy() == 0) & nz).sum())

    return ScaleDownPlan(
        method="proportional",
        per_small_area=per_sa,
        marginals=sa_marg,
        town_marginals=town_marg,
        n_people=n_people,
        n_households=n_households,
        areas_kept=keep,
        diagnostics={
            "common_scale_factor": round(factor, 6),
            "scale_target": factor_info,
            "size_person_total_repair": repair,
            "fraction_of_areas_kept": 1.0,
            "cells_nonzero_in_cobh": kept_nonzero,
            "cells_rounded_to_zero": zeroed,
            "fraction_of_detail_lost_to_rounding": round(zeroed / kept_nonzero, 4)
            if kept_nonzero
            else 0.0,
            "deterministic_without_a_seed": True,
            "note": (
                "Every small area is kept, so the town's full spatial extent "
                "survives, but each area's counts are smoothed and small "
                "categories round to zero."
            ),
        },
    )


def build_both(
    marginals: dict[str, Marginal], *, master_seed: int
) -> dict[Method, ScaleDownPlan]:
    """Both U03 candidates, as E0-1 requires."""
    return {
        "whole_area_stratified": scale_whole_areas_stratified(
            marginals, master_seed=master_seed
        ),
        "proportional": scale_proportional(marginals),
    }
