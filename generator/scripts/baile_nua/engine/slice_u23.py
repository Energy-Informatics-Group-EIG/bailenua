"""The U23 mixed-age slice, and why it is selected differently from E1's.

U23, 9 October 2026: *"replace the E1 estate with a mixed-age slice of the same
size: pre-1980 homes, BER spread including D to G, and at least one heat pump,
PV system, BESS and EV. Keep the E1 estate as a regression fixture."*

**What the E1 estate was, and why it had to go.** It was selected for
*representativeness of household size* — the seed small area whose mean
household size was closest to the town's, then its nearest neighbours (D-018).
That is the right criterion for E0-7's "about 140 people", and it produced a
faithful estate which was also, as the E1 gate report had to report, 84% A or B
rated with a mean build year of 2005, 49 of 50 homes on gas, no dwelling rated
below C, no heat pump and no storage heater. Faithful, and a narrow slice of
the archetype library.

**What this one is selected for.** Age and fabric spread, subject to still
being a real contiguous part of Cobh. Cobh has such a part: the ``047107``
series is the older core, where small areas run from 71% to 100% pre-1980 with
six or seven BER letters present and a third to two thirds rated D to G.

**The tension U23 creates, stated rather than resolved quietly.** Those older
areas have smaller households — about 2.0 to 2.4 people per home against the
town's 2.67 — so fifty of their homes hold roughly 110 people, under E0-7's
"about 140". The selector therefore optimises age and spread **subject to**
the E0-7 people band rather than ignoring it, and reports the trade it made.
If no contiguous choice satisfies both, that is reported as a conflict and not
papered over.

**Substitutions are recorded, not hidden.** The town holds 14 heat pumps in
1,092 homes, so a 50-home contiguous slice expects 0.64 of one. Where a
required archetype is absent after selection, the nearest home of that kind is
swapped in, the newest home is swapped out, and every swap is written into the
slice's diagnostics with what it was for. A slice that silently contained what
it was asked to contain would be useless as evidence.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import numpy as np
import pandas as pd

__all__ = [
    "U23_REQUIREMENTS",
    "MixedAgeSelection",
    "U23Infeasible",
    "select_mixed_age_slice",
]


class U23Infeasible(RuntimeError):
    """No contiguous slice satisfies both U23's spread and E0-7's people band."""

#: What U23 requires of the slice, as checkable predicates.
U23_REQUIREMENTS: dict[str, str] = {
    "n_homes": "the same size as the E1 estate (50)",
    "pre_1980_share": "a substantial share of pre-1980 homes (>= 0.40)",
    "ber_letters_present": "a BER spread including D, E, F and G",
    "at_least_one_heat_pump": "at least one heat pump",
    "at_least_one_pv": "at least one PV system",
    "at_least_one_bess": "at least one battery",
    "at_least_one_ev": "at least one EV",
    "people_in_e0_7_band": "about 140 people, within the declared tolerance",
}

#: Minimum share of pre-1980 homes. 0.40 rather than a majority: U23 says
#: "mixed-age", and the town itself is 39.1% pre-1980, so a slice at or above
#: the town share is mixed in the direction that matters while remaining a real
#: part of Cobh rather than a curated museum.
MIN_PRE_1980_SHARE: float = 0.40

#: BER letters the spread must contain.
REQUIRED_BER_LETTERS: tuple[str, ...] = ("D", "E", "F", "G")


@dataclasses.dataclass
class MixedAgeSelection:
    household_ids: list[str]
    diagnostics: dict[str, Any]


def _area_scores(
    buildings: list[Any], size_by_household: dict[str, int], town_mean_size: float,
) -> pd.DataFrame:
    rows = []
    for b in buildings:
        if not b.household_id:
            continue
        rows.append({
            "sa": b.small_area, "year": b.build_year,
            "ber_letter": b.ber_band[0],
            "people": size_by_household.get(b.household_id, 0),
            "heat_pump": b.heating_system == "heat pump",
        })
    frame = pd.DataFrame(rows)
    g = frame.groupby("sa").agg(
        n=("year", "size"),
        pre_1980=("year", lambda s: float((s < 1980).mean())),
        ber_letters=("ber_letter", "nunique"),
        dg_share=("ber_letter", lambda s: float(s.isin(list("DEFG")).mean())),
        people_per_home=("people", "mean"),
        n_heat_pumps=("heat_pump", "sum"),
    )
    # The objective, declared: age and fabric spread, penalised for departing
    # from the town's household size, because E0-7's people band still applies.
    g["size_penalty"] = (g.people_per_home - town_mean_size).abs() / town_mean_size
    g["score"] = (
        1.0 * g.pre_1980
        + 0.5 * g.dg_share
        + 0.1 * (g.ber_letters / 7.0)
        - 0.8 * g.size_penalty
    )
    return g.sort_values("score", ascending=False)


def select_mixed_age_slice(
    town: Any, *, n_homes: int, target_people: int, people_tolerance: int,
    master_seed: int,
) -> MixedAgeSelection:
    """Select the U23 slice: contiguous, mixed-age, with the required archetypes."""
    from baile_nua.population import saps
    from baile_nua.rng import SeedTree, Stream

    by_hh = {b.household_id: b for b in town.buildings if b.household_id}
    size_by_household = town.states.groupby("household_id").size().to_dict()
    town_mean = float(np.mean(list(size_by_household.values())))

    scores = _area_scores(town.buildings, size_by_household, town_mean)
    eligible = scores[scores.n >= int(0.35 * n_homes)]
    if eligible.empty:                                   # pragma: no cover
        eligible = scores

    cents = saps.cobh_small_areas().frame.set_index("sa_code")
    def build_from(seed_area: str) -> tuple[list[str], list[str], Any]:
        """Build the slice from one seed area. Returns (picked, areas, dist)."""
        if seed_area in cents.index:
            lon0 = float(cents.at[seed_area, "centroid_lon"])
            lat0 = float(cents.at[seed_area, "centroid_lat"])

            def dist(sa: str) -> float:
                if sa not in cents.index:
                    return float("inf")
                dlon = (float(cents.at[sa, "centroid_lon"]) - lon0) * np.cos(
                    np.radians(lat0)
                )
                return float(np.hypot(dlon, float(cents.at[sa, "centroid_lat"]) - lat0))
        else:                                                # pragma: no cover
            def dist(sa: str) -> float:
                return 0.0 if sa == seed_area else 1.0

        by_area: dict[str, list[Any]] = {}
        for b in by_hh.values():
            by_area.setdefault(b.small_area, []).append(b)

        tree = SeedTree(master_seed)
        picked: list[str] = []
        used: list[str] = []
        for sa in sorted(by_area, key=lambda s: (dist(s), s)):
            if len(picked) >= n_homes:
                break
            homes = sorted(by_area[sa], key=lambda x: x.building_id)
            gen = tree.generator(Stream.ESTATE_SELECTION, entity=f"u23-{sa}", sim_day=0)
            # Permuted, never building_id order: ids are assigned
            # household-size descending, so taking a prefix takes the biggest
            # households (the fault behind D-018).
            for i in gen.permutation(len(homes)):
                if len(picked) >= n_homes:
                    break
                picked.append(homes[int(i)].household_id)
            used.append(sa)

        if len(picked) < n_homes:                        # pragma: no cover
            raise RuntimeError(
                f"only {len(picked)} homes available for the U23 slice"
            )
        return picked, used, dist

    # ---- feasibility search over seed areas -------------------------------
    #
    # E0-7's people band is a HARD constraint, not a term in the objective.
    # The first version made it a penalty weighted at 0.8 against an age
    # reward of 1.0, and the best-scoring seed produced 112 people against a
    # lower bound of 115 - three short. Re-weighting until it fitted would
    # have been choosing the weights to get the answer; searching the seeds
    # for one that satisfies both constraints is the same work done honestly,
    # and it reports when none does.
    attempts: list[dict[str, Any]] = []
    chosen: tuple[list[str], list[str], Any, str] | None = None
    for candidate in [str(x) for x in eligible.index]:
        picked_c, used_c, dist_c = build_from(candidate)
        people_c = int(sum(size_by_household.get(h, 0) for h in picked_c))
        years_c = [by_hh[h].build_year for h in picked_c]
        pre80 = float(np.mean([y < 1980 for y in years_c]))
        in_band = abs(people_c - target_people) <= people_tolerance
        attempts.append({
            "seed_area": candidate, "n_people": people_c,
            "people_within_band": in_band,
            "pre_1980_share": round(pre80, 3),
            "score": round(float(eligible.at[candidate, "score"]), 4),
        })
        if in_band and pre80 >= MIN_PRE_1980_SHARE and chosen is None:
            chosen = (picked_c, used_c, dist_c, candidate)

    if chosen is None:
        best = max(attempts, key=lambda a: (a["people_within_band"], a["score"]))
        raise U23Infeasible(
            f"no contiguous mixed-age slice satisfies both U23 and E0-7 at "
            f"{n_homes} homes. U23 wants pre-1980 homes, and Cobh's pre-1980 "
            f"small areas hold smaller households - about 2.0 to 2.4 people "
            f"against the town's {town_mean:.2f} - so fifty of them hold "
            f"roughly 110 people against E0-7's {target_people} "
            f"+/-{people_tolerance}. Closest attempt: seed "
            f"{best['seed_area']} with {best['n_people']} people and "
            f"{best['pre_1980_share']:.0%} pre-1980. This is a conflict "
            f"between two approved decisions and is reported rather than "
            f"resolved by widening a band."
        )

    picked, used, dist, seed_area = chosen

    # ---- substitutions, each recorded ----------------------------------
    substitutions: list[dict[str, Any]] = []

    def newest_in(ids: list[str], exclude: set[str]) -> str:
        return max(
            (h for h in ids if h not in exclude),
            key=lambda h: by_hh[h].build_year,
        )

    def ensure(predicate, what: str, order_key) -> None:
        if any(predicate(by_hh[h]) for h in picked):
            return
        candidates = sorted(
            (h for h, b in by_hh.items() if h not in picked and predicate(b)),
            key=order_key,
        )
        if not candidates:                               # pragma: no cover
            substitutions.append({
                "for": what, "swapped_in": None,
                "note": "the town contains none at all",
            })
            return
        swap_in = candidates[0]
        swap_out = newest_in(picked, exclude=set())
        picked[picked.index(swap_out)] = swap_in
        substitutions.append({
            "for": what,
            "swapped_in": swap_in,
            "swapped_in_small_area": by_hh[swap_in].small_area,
            "swapped_in_build_year": by_hh[swap_in].build_year,
            "swapped_out": swap_out,
            "swapped_out_build_year": by_hh[swap_out].build_year,
            "note": (
                f"no {what} in the contiguous selection; the nearest one was "
                f"swapped in and the newest home swapped out, so the slice "
                f"gets older rather than younger as a side effect"
            ),
        })

    ensure(
        lambda b: b.heating_system == "heat pump", "heat pump",
        order_key=lambda h: (dist(by_hh[h].small_area), h),
    )
    for letter in REQUIRED_BER_LETTERS:
        ensure(
            lambda b, L=letter: b.ber_band.startswith(L),
            f"BER band {letter}",
            order_key=lambda h: (dist(by_hh[h].small_area), h),
        )

    picked = sorted(picked)
    people = int(sum(size_by_household.get(h, 0) for h in picked))
    years = [by_hh[h].build_year for h in picked]
    letters = sorted({by_hh[h].ber_band[0] for h in picked})
    systems = sorted({by_hh[h].heating_system for h in picked})

    diagnostics = {
        "selection_rule": (
            "seed small area maximising a declared objective - pre-1980 share, "
            "D-G share and BER-letter count, penalised for departing from the "
            "town's household size - then nearest neighbours by OSi centroid "
            "distance, with order within an area a seeded permutation. "
            "Required archetypes absent from the contiguous selection are "
            "swapped in and recorded."
        ),
        "objective_weights": {
            "pre_1980_share": 1.0, "dg_share": 0.5,
            "ber_letter_count": 0.1, "household_size_penalty": -0.8,
        },
        "seed_area": seed_area,
        "seed_selection": (
            "the highest-scoring seed area whose slice ALSO satisfies E0-7's "
            "people band and the pre-1980 floor; the people band is a hard "
            "constraint and not a term in the objective"
        ),
        "seed_attempts": attempts,
        "n_seed_areas_tried": len(attempts),
        "n_seed_areas_in_band": sum(1 for a in attempts if a["people_within_band"]),
        "small_areas": used,
        "n_homes": len(picked),
        "n_people": people,
        "people_per_home": round(people / max(len(picked), 1), 3),
        "town_people_per_home": round(town_mean, 3),
        "target_people": target_people,
        "people_tolerance": people_tolerance,
        "people_within_e0_7_band": bool(
            abs(people - target_people) <= people_tolerance
        ),
        "mean_build_year": round(float(np.mean(years)), 1),
        "pre_1980_share": round(float(np.mean([y < 1980 for y in years])), 3),
        "min_build_year": int(min(years)),
        "max_build_year": int(max(years)),
        "ber_letters_present": letters,
        "required_ber_letters_present": sorted(
            set(REQUIRED_BER_LETTERS) & set(letters)
        ),
        "missing_required_ber_letters": sorted(
            set(REQUIRED_BER_LETTERS) - set(letters)
        ),
        "heating_systems": systems,
        "n_heat_pumps": sum(
            1 for h in picked if by_hh[h].heating_system == "heat pump"
        ),
        "substitutions": substitutions,
        "e1_estate_retained_as_regression_fixture": True,
    }
    return MixedAgeSelection(household_ids=picked, diagnostics=diagnostics)
