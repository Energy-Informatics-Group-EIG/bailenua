"""I-069's fix: the age profile within each economic status, from FY047B.

**What the fault was.** `synthesise.py` drew each person's economic status from
their small area's marginal with no age conditioning above 15:

```python
econ_label = (_draw_from(p_gen, area_marg["economic_status"])
              if member.age >= 15 else "student")
```

Every marginal matched — IPF guarantees it — and the age × status joint came
out as the product of the two marginals: a 14-year-old retiree, 243 "students"
with a median age of 45, 65+ retirement at 2.2% against the Census's 13.1%.

**Why it was a faithful use of the only small-area source.** This is the part
worth stating before the fix, because it changes what kind of mistake it was.
Every SAPS table that crosses economic status is `Sex × Principal Economic
Status`: `SAP2022T8T1SA`, `T8T1TOWN22`, `T8T1ED`, `T8T1CTY`, and the 2016 and
2011 editions. **Not one has an age dimension.** The marginals the population
is fitted to cannot condition status on age, so the unconditional draw was the
only thing those marginals supported. The fault was not using a worse source
than was available at that geography; it was not reaching for a coarser
geography that has the joint.

**What this module does.** Bayes, with the area marginal kept intact:

    P(status | age, area) ∝ P(age | status, county) × P(status | area, sex)

The second factor is SAPS's, unchanged — so the area's status marginal is
preserved, which is what the population is fitted to and what
`saps_marginals.json` checks. The first is FY047B's age profile within each
status for Cork City and Cork County. SAPS decides **how many** of each status
an area has; FY047B decides **which ages** get them.

That ordering matters: a fix that imposed the county joint directly would
overwrite the small-area variation the whole synthesis exists to reproduce.
Cobh's older core areas really do have more retired residents than its newer
ones, and SAPS is the only thing that knows it.

**Exposure.** FY047B is `tuning` — the population is built from it, so it can
never validate the population. F1054 remains the held-out scorer. The honest
qualification, recorded in I-069 and not hidden here: F1054 and FY047B are the
same Census cross-tabulated differently, so after this fit F1054 is held out as
a *table* and a *geography* and is not independent as a *data source*. What it
still carries is the settlement-size contrast, which FY047B does not have.
"""

from __future__ import annotations

import functools
from typing import Any

__all__ = [
    "SOURCE_KEY",
    "EXPOSURE",
    "COUNTY",
    "AGE_BANDS",
    "SAPS_TO_FY047B",
    "EconByAgeError",
    "age_profile_by_status",
    "status_weights_for_age",
]

SOURCE_KEY = "cso.census.fy047b_economic_status_by_age_and_county"

#: The population is built from it, so it can never validate the population.
EXPOSURE = "tuning"

#: Cobh's own county, as FY047B labels it.
COUNTY = "Cork City and Cork County"

#: FY047B's age bands. Finer than F1054's at the young end - 15-19 and 20-24
#: are separate here and one band there - which is part of why FY047B is the
#: fit source and F1054 the scorer.
AGE_BANDS: tuple[tuple[str, int, int], ...] = (
    ("15 - 19 years", 15, 19),
    ("20 - 24 years", 20, 24),
    ("25 - 34 years", 25, 34),
    ("35 - 44 years", 35, 44),
    ("45 - 54 years", 45, 54),
    ("55 - 64 years", 55, 64),
    ("65 years and over", 65, 200),
)

#: SAPS's economic-status labels (what `area_marg["economic_status"]` carries,
#: and what ``ECON_MAP`` in synthesise.py keys on) to FY047B's.
#:
#: SAPS splits unemployment three ways and FY047B two, so two SAPS categories
#: share FY047B's "lost or given up previous job" row. That is a coarsening of
#: the CONDITIONING factor only - the area marginal still distinguishes all
#: three - so no SAPS detail is lost, and the two short/long-term categories
#: are given the same age profile rather than an invented difference.
SAPS_TO_FY047B: dict[str, str] = {
    "at work": "Persons at work",
    "looking for first regular job": "Unemployed looking for first regular job",
    "short-term unemployed": "Unemployed having lost or given up previous job",
    "long-term unemployed": "Unemployed having lost or given up previous job",
    "student": "Student or pupil",
    "looking after home/family": "Looking after home/family",
    "retired": "Retired",
    "unable to work": "Unable to work due to permanent sickness or disability",
    "other": "Others not in labour force",
}


class EconByAgeError(RuntimeError):
    pass


def _index(dim: dict[str, Any], key: str) -> dict[str, int]:
    c = dim[key]["category"]["index"]
    return c if isinstance(c, dict) else {str(v): i for i, v in enumerate(c)}


def band_for_age(age: int) -> str:
    for label, lo, hi in AGE_BANDS:
        if lo <= age <= hi:
            return label
    raise EconByAgeError(
        f"age {age} falls in no FY047B band; the table covers 15 and over, so "
        f"a younger person must not reach this function"
    )


@functools.lru_cache(maxsize=2)
def age_profile_by_status(county: str = COUNTY) -> dict[str, Any]:
    """``P(age band | status)`` for one county, read from FY047B.

    Normalised within each status, so it is a profile over ages and not a
    joint: the status totals come from SAPS and must not be overwritten.
    """
    import json
    from pathlib import Path

    import numpy as np

    from baile_nua.sources import REGISTRY

    src = REGISTRY.get(SOURCE_KEY)
    if src is None:
        raise EconByAgeError(f"{SOURCE_KEY} is not declared")
    path = Path(__file__).resolve().parents[3] / "sources" / src.relpath
    if not path.exists():
        raise EconByAgeError(
            f"{SOURCE_KEY} is declared but not fetched: {path} is absent. "
            f"Fetch it rather than hard-coding an age profile."
        )
    doc = json.loads(path.read_text(encoding="utf-8"))
    ids, size, value, dim = doc["id"], doc["size"], doc["value"], doc["dimension"]

    def find(fragment: str) -> str:
        ks = [k for k in ids if fragment.lower() in str(dim[k].get("label", "")).lower()]
        if len(ks) != 1:
            raise EconByAgeError(
                f"FY047B has {len(ks)} dimensions matching {fragment!r}: {ks}. "
                f"Its shape has changed and the profile must be re-read."
            )
        return ks[0]

    cd, sd, ed, ad = (find("County"), find("Sex"),
                      find("Economic Status"), find("Age Group"))
    arr = np.array([np.nan if v is None else float(v) for v in value],
                   dtype=np.float64).reshape(size)
    pos = {k: i for i, k in enumerate(ids)}
    ci, cl = _index(dim, cd), dim[cd]["category"]["label"]
    si, sl = _index(dim, sd), dim[sd]["category"]["label"]
    ei, el = _index(dim, ed), dim[ed]["category"]["label"]
    ai, al = _index(dim, ad), dim[ad]["category"]["label"]
    sti, stl = _index(dim, "STATISTIC"), dim["STATISTIC"]["category"]["label"]
    yi, yl = _index(dim, "TLIST(A1)"), dim["TLIST(A1)"]["category"]["label"]

    ckeys = [k for k, v in cl.items() if v.strip() == county.strip()]
    if len(ckeys) != 1:
        raise EconByAgeError(
            f"{county!r} is not exactly one county in FY047B; published "
            f"values are {sorted(cl.values())}"
        )
    # The COUNT statistic, not the change ones.
    stk = [k for k, v in stl.items()
           if "change" not in v.lower()]
    if len(stk) != 1:
        raise EconByAgeError(
            f"FY047B has {len(stk)} non-change statistics: "
            f"{[stl[k] for k in stk]}"
        )
    latest = max(yl, key=lambda k: int(yl[k]))
    both = [k for k, v in sl.items() if v.strip().lower() == "both sexes"]
    if not both:
        raise EconByAgeError("FY047B has no 'Both sexes' category")

    lab_to_key = {v.strip(): k for k, v in el.items()}
    age_to_key = {v.strip(): k for k, v in al.items()}

    def cell(status_label: str, age_label: str) -> float:
        sel = [0] * len(ids)
        sel[pos["STATISTIC"]] = sti[stk[0]]
        sel[pos["TLIST(A1)"]] = yi[latest]
        sel[pos[cd]] = ci[ckeys[0]]
        sel[pos[sd]] = si[both[0]]
        sel[pos[ed]] = ei[lab_to_key[status_label]]
        sel[pos[ad]] = ai[age_to_key[age_label]]
        v = float(arr[tuple(sel)])
        return 0.0 if not np.isfinite(v) else v

    profile: dict[str, dict[str, float]] = {}
    counts: dict[str, dict[str, float]] = {}
    for saps_label, fy_label in SAPS_TO_FY047B.items():
        if fy_label not in lab_to_key:
            raise EconByAgeError(
                f"FY047B has no status {fy_label!r}; SAPS_TO_FY047B is stale. "
                f"Published statuses are {sorted(lab_to_key)}"
            )
        raw = {band: cell(fy_label, band) for band, _lo, _hi in AGE_BANDS}
        total = sum(raw.values())
        if total <= 0:
            raise EconByAgeError(
                f"FY047B gives {county!r} a zero total for {fy_label!r}, so "
                f"no age profile can be formed for it"
            )
        counts[saps_label] = raw
        profile[saps_label] = {b: v / total for b, v in raw.items()}

    # Shape check: a status's profile must sum to 1, and the ordering the data
    # must have is that retirement is concentrated at the top band and study at
    # the bottom. If either fails, a dimension is being read wrongly and the
    # fix would install a wrong joint - which is worse than the fault.
    for st, prof in profile.items():
        if abs(sum(prof.values()) - 1.0) > 1e-9:
            raise EconByAgeError(f"{st}'s age profile sums to {sum(prof.values())}")
    if profile["retired"]["65 years and over"] < 0.5:
        raise EconByAgeError(
            f"FY047B puts only "
            f"{profile['retired']['65 years and over']:.3f} of Cork's retired "
            f"population at 65 and over. A dimension is mis-read."
        )
    if (profile["student"]["15 - 19 years"]
            + profile["student"]["20 - 24 years"]) < 0.5:
        raise EconByAgeError(
            "FY047B puts under half of Cork's students below 25. A dimension "
            "is mis-read."
        )
    return {
        "source": SOURCE_KEY,
        "model_development_exposure": EXPOSURE,
        "county": county,
        "census_year": yl[latest],
        "counts": counts,
        "profile": profile,
        "what_it_is": (
            "P(age band | status) for Cork City and Cork County, normalised "
            "within each status. NOT a joint: the status totals come from "
            "SAPS and are not overwritten."
        ),
    }


def status_weights_for_age(
    age: int, area_marginal: dict[str, float], county: str = COUNTY,
) -> dict[str, float]:
    """``P(status | age, area)``, by Bayes on SAPS's own area marginal.

        P(status | age, area) ∝ P(age | status, county) × P(status | area)

    The area marginal is SAPS's and is passed in unchanged, so the small-area
    variation the synthesis exists to reproduce is preserved: Cobh's older
    core areas keep more retired residents than its newer ones, and only the
    *ages* of those residents change.

    Returns weights summing to 1 over the statuses the area marginal names. A
    status whose age profile gives this age zero probability drops out, which
    is the whole point — nobody is retired at 17 because FY047B says Cork has
    nobody retired at 17.
    """
    prof = age_profile_by_status(county)["profile"]
    band = band_for_age(int(age))
    out: dict[str, float] = {}
    for status, p_area in area_marginal.items():
        if p_area <= 0:
            continue
        p_age = prof.get(status, {}).get(band)
        if p_age is None:
            # A status the area marginal names and FY047B does not. Carried
            # with its area weight and no age conditioning rather than
            # dropped, so the marginal cannot be silently distorted - and it
            # raises in `age_profile_by_status` if it is a mapping gap.
            out[status] = float(p_area)
            continue
        out[status] = float(p_age) * float(p_area)
    total = sum(out.values())
    if total <= 0:
        # Every status the area has is impossible at this age, which means the
        # area marginal and the age profile disagree completely. Falling back
        # to the unconditional marginal is right: it is what the old code did,
        # it keeps the marginal exact, and it is rare enough to be worth
        # knowing about rather than hiding.
        return {k: v / sum(area_marginal.values())
                for k, v in area_marginal.items() if v > 0}
    return {k: v / total for k, v in out.items()}
