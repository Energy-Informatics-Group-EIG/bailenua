"""U33: a sourced proxy for the household move rate, from Census 2022.

The ten-year vital-statistics check tests four event counts against intervals.
Three are sourced — deaths from VSA08 over PEA01, births from VSA104's
age-specific fertility, partnering from VSA49's marriage rates. The fourth,
``move_out``, was not:

    "[A] A-25b gross out-move rate applied to this run's household-years. This
    is NOT a vital-statistics interval: it tests internal consistency of an
    assumed rate, not agreement with a source"

So the check was comparing the model to itself. A count inside that interval
said only that the hazard integrated to the rate it was declared at, which the
integrated-hazard check already asserts for every event. It carried no evidence
about Ireland at all.

**What was missed, and why.** A-25b's ``retires_if`` asked for "a published
Irish gross in-migration or out-migration rate, as opposed to the net figure",
and the sweep searched ``internal migration`` and ``household formation``. It
found EP006 and PEB08, which publish NET migration, and correctly concluded
that a net rate cannot set a gross one. The verdict was right about migration
*estimates* and wrong about where else to look: the quantity is also a **Census
question**. Every resident is asked where they usually lived one year before
Census Day, and SAP2022 publishes the answer at **town** level — so for Cobh
itself, not for Cork County and not for the South-West.

**Cobh, Census 2022** (``SAP2022T2T3TOWN22``, "Cobh, Co Cork"):

====================  ========
Same Address            13,008
Elsewhere in county        598
Elsewhere in Ireland        92
Outside Ireland            145
**Total**             **13,843**
====================  ========

A move from one Cobh address to another is counted: the question is about the
previous *address*, and a previous address inside Co Cork falls in "Elsewhere
in county". So intra-town moves are in the numerator, which is what the model's
vacancy-chain refill represents.

**What stays ``[A]``, and it is the whole of the conversion** (A-25b):

*Persons, not households.* The Census counts people; the model's hazard is per
household. A household that moves takes everyone with it, and for whole-household
moves the two rates are **equal** — ``h x H x s`` persons move out of ``N = H x s``,
which is ``h``. But a move that takes one person and not a household — a young
adult leaving home, someone moving in with a partner — adds to the person count
without being a household move. So the person rate is the household rate *plus*
the individual-move rate, and the Census figure therefore bounds the household
rate from **above**:

    household move rate <= 0.0603 per household-year

*In, not out.* The question asks where a *current* resident used to live, so it
counts moves **into** Cobh. The model's hazard is a move **out**. The two balance
only in a stationary population, and Cobh's grew slightly between 2016 and 2022.

*One window, observed once.* April 2021 to April 2022 included the tail of the
Covid restrictions, which suppressed moving. The rate may be low for the decade.
This is recorded as a direction, not corrected for: adjusting it would be
replacing a measurement with a guess.

**Nothing is fitted to this.** The declared hazard keeps its value; the proxy
decides the *interval* the observed count is tested against, which is what makes
the test evidence rather than a tautology. Exposure stays ``none``.
"""

from __future__ import annotations

import functools
from typing import Any

__all__ = [
    "SOURCE_KEY",
    "EXPOSURE",
    "TOWN_LABEL",
    "SAME_ADDRESS_LABEL",
    "MoveRateError",
    "census_move_table",
    "person_move_rate",
    "household_move_rate_bound",
    "move_rate_proxy",
]

SOURCE_KEY = "cso.census.sap2022_usual_residence_one_year_ago_by_town"

#: Nothing is fitted to it: the hazard keeps its declared value and this sets
#: the interval the observed count is tested against.
EXPOSURE = "none"

#: The town the model is calibrated to, as SAP2022 labels it.
TOWN_LABEL = "Cobh, Co Cork"

#: The category that is *not* a move.
SAME_ADDRESS_LABEL = "Same Address"


class MoveRateError(RuntimeError):
    """The Census table did not yield the town or the categories it must."""


def _index(dim: dict[str, Any], key: str) -> dict[str, int]:
    """JSON-stat permits a category index as an object or an ordered array."""
    cat = dim[key]["category"]["index"]
    if isinstance(cat, dict):
        return {str(k): int(v) for k, v in cat.items()}
    return {str(v): i for i, v in enumerate(cat)}


@functools.lru_cache(maxsize=1)
def census_move_table(town: str = TOWN_LABEL) -> dict[str, Any]:
    """One town's row of the Census migration question, read from the source.

    Raises rather than returning a default for any shape the table must have
    and does not: a silently-wrong denominator here would move an acceptance
    interval, which is the worst place for one.
    """
    import json
    from pathlib import Path

    import numpy as np

    from baile_nua.sources import REGISTRY

    src = REGISTRY.get(SOURCE_KEY)
    if src is None:
        raise MoveRateError(
            f"{SOURCE_KEY} is not declared, so the move-rate proxy has no "
            f"source. Declare it in sources_registry before using it (D24)."
        )
    path = Path(__file__).resolve().parents[3] / "sources" / src.relpath
    if not path.exists():
        raise MoveRateError(
            f"{SOURCE_KEY} is declared but not fetched: {path} is absent. "
            f"Fetch the source rather than hard-coding the figures."
        )
    doc = json.loads(path.read_text(encoding="utf-8"))
    ids, size, value = doc["id"], doc["size"], doc["value"]
    dim = doc["dimension"]

    res_dims = [k for k in ids if "Residence" in dim[k].get("label", "")
                or k.startswith("C0378")]
    town_dims = [k for k in ids if "Town" in dim[k].get("label", "")
                 or k.startswith("C0416")]
    if len(res_dims) != 1 or len(town_dims) != 1:
        raise MoveRateError(
            f"expected exactly one residence dimension and one town dimension "
            f"in {SOURCE_KEY}; found {res_dims} and {town_dims}. The table's "
            f"shape has changed and the figures must be re-read, not guessed."
        )
    rd, td = res_dims[0], town_dims[0]
    res_i, res_lab = _index(dim, rd), dim[rd]["category"]["label"]
    town_i, town_lab = _index(dim, td), dim[td]["category"]["label"]

    keys = [k for k, v in town_lab.items() if v == town]
    if len(keys) != 1:
        near = sorted(v for v in town_lab.values() if town.split(",")[0] in v)
        raise MoveRateError(
            f"{town!r} does not appear exactly once in {SOURCE_KEY}'s town "
            f"dimension (found {len(keys)}). Nearest labels: {near[:5]}"
        )
    tk = keys[0]

    arr = np.array([np.nan if v is None else float(v) for v in value],
                   dtype=np.float64).reshape(size)
    pos = {k: i for i, k in enumerate(ids)}
    counts: dict[str, float] = {}
    for cat_key, i in sorted(res_i.items(), key=lambda kv: kv[1]):
        sl = [0] * len(ids)
        sl[pos[rd]] = i
        sl[pos[td]] = town_i[tk]
        counts[str(res_lab[cat_key])] = float(arr[tuple(sl)])

    if SAME_ADDRESS_LABEL not in counts:
        raise MoveRateError(
            f"{SOURCE_KEY} has no {SAME_ADDRESS_LABEL!r} category; published "
            f"categories are {sorted(counts)}. Without it a move cannot be "
            f"distinguished from a non-move."
        )
    total = counts.get("Total")
    parts = {k: v for k, v in counts.items() if k != "Total"}
    if total is None:
        total = sum(parts.values())
    elif abs(sum(parts.values()) - total) > 1.0:
        raise MoveRateError(
            f"{SOURCE_KEY}: the published categories sum to "
            f"{sum(parts.values()):,.0f} against a published total of "
            f"{total:,.0f} for {town!r}. One of them is being read wrongly."
        )
    if total <= 0:
        raise MoveRateError(f"{SOURCE_KEY}: {town!r} has a total of {total}")

    moved = total - counts[SAME_ADDRESS_LABEL]
    return {
        "source": SOURCE_KEY,
        "town": town,
        "counts": counts,
        "total": total,
        "n_moved": moved,
        "categories_counted_as_a_move": sorted(
            k for k in parts if k != SAME_ADDRESS_LABEL),
    }


def person_move_rate(town: str = TOWN_LABEL) -> float:
    """Share of residents aged 1+ who were at a different address a year before."""
    t = census_move_table(town)
    return float(t["n_moved"]) / float(t["total"])


def household_move_rate_bound(town: str = TOWN_LABEL) -> dict[str, Any]:
    """The person rate, and why it is an UPPER bound on the household rate.

    For whole-household moves the two rates are equal. Individual moves add
    person-moves without household-moves, so the person rate is the household
    rate plus the individual-move rate, and therefore bounds it from above.
    """
    r = person_move_rate(town)
    return {
        "person_move_rate_per_year": round(r, 6),
        "bounds_household_rate": "above",
        "why": (
            "a household that moves takes everyone with it, so for whole-"
            "household moves the person rate EQUALS the household rate "
            "(h x H x s movers out of H x s residents). A move that takes one "
            "person and not a household - leaving home, moving in with a "
            "partner - adds to the person count and not to the household "
            "count, so the person rate is the household rate plus the "
            "individual-move rate."
        ),
        "a_flag": "A-25b",
        "a_flag_is_now_about": (
            "the person-to-household conversion, not the absence of a source. "
            "The rate itself is observed on Cobh; splitting it between "
            "whole-household moves and individual moves is what remains "
            "unsourced."
        ),
    }


def move_rate_proxy(
    *, declared_rate: float, household_years: float, observed: int,
    town: str = TOWN_LABEL,
) -> dict[str, Any]:
    """The U33 replacement: test ``move_out`` against the Census, not itself.

    ``declared_rate`` is the model's own hazard, passed in so the comparison
    can report both and so this module never reaches into the hazard table —
    which is what would turn a reference into a calibration target.
    """
    from baile_nua.lifecourse.tenyear import _poisson_interval

    table = census_move_table(town)
    rate = person_move_rate(town)
    expected = household_years * rate
    lo, hi = _poisson_interval(expected)
    declared_expected = household_years * float(declared_rate)
    return {
        "criterion": "U33, week 3 step 4",
        "replaces": (
            "the internal-consistency criterion, which applied the model's own "
            "declared rate to the model's own household-years and therefore "
            "compared the model to itself"
        ),
        "source": SOURCE_KEY,
        "model_development_exposure": EXPOSURE,
        "sourced": True,
        "proxy_flagged_a": "A-25b",
        "town": town,
        "census_counts": table["counts"],
        "census_person_move_rate_per_year": round(rate, 6),
        "declared_household_move_rate_per_year": round(float(declared_rate), 6),
        "declared_over_census": round(float(declared_rate) / rate, 4) if rate else None,
        "household_years": round(household_years, 2),
        "observed": int(observed),
        "expected_under_census_rate": round(expected, 2),
        "ci95_under_census_rate": [round(lo, 2), round(hi, 2)],
        "within": bool(lo <= observed <= hi),
        "expected_under_declared_rate": round(declared_expected, 2),
        "the_bound": household_move_rate_bound(town),
        "caveats": (
            "The Census counts moves INTO the town (where a current resident "
            "used to live); the hazard is a move OUT, and the two balance only "
            "in a stationary population. The window is April 2021 to April "
            "2022, which included the tail of the Covid restrictions and so "
            "may understate the decade's mobility. Neither is corrected for: "
            "an adjustment would replace a measurement with a guess."
        ),
        "nothing_is_fitted": (
            "The declared hazard keeps its value. This decides the INTERVAL "
            "the observed count is tested against, which is what makes the "
            "test evidence instead of a tautology."
        ),
    }
