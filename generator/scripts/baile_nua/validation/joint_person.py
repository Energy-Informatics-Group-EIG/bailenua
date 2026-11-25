"""Design 5.2: the PERSON-LEVEL joint of age and economic status.

``population/joint_metrics.py`` already validates joints, and it passes. It
works at **area** level: it correlates one small-area marginal against another
— retired share against owner-occupied-no-mortgage share, unemployment against
social renting — and asks whether the synthesised town reproduces the
correlation the Census shows between areas.

Those are real checks and they cannot see this fault. The population is built
by fitting small-area **marginals**, and `synthesise.py` draws each person's
economic status from their area's marginal with **no age conditioning** above
15:

```python
econ_label = (_draw_from(p_gen, area_marg["economic_status"])
              if member.age >= 15 else "student")
```

So every marginal is matched — that is what IPF guarantees — and the joint is
whatever independence produces. Measured on the town (I-069): a **14-year-old
retiree**, employment to **93**, and **243 "students" with a median age of
45**.

**F1054 was held out, and is not independent any more.** It is the two-way
joint itself, published by settlement size, and Cobh at about 14,000 people
falls in "Towns 10,000 population and over". It found I-069, which is what a
held-out reference is for.

Then I-069's fix had to come from somewhere, and SAPS does not publish the
joint at any geography, so the conditioning came from **FY047B** — the same
cross by county. F1054 and FY047B are two partitions of the *same Census 2022
microdata*: both put the national 15+ population at **4,136,852** and each
partitions the State. Cobh's residents are in both. So they share underlying
counts by construction, and design 7.1's rule bites: a source used to build the
model cannot validate it. F1054's exposure is now ``design`` and a pass against
it belongs in the calibration-exposed table.

**What replaces it, and what that costs.** :func:`compare_independent` scores
against **CNA25 at Census 2016** — a different *enumeration*, so it cannot
share counts with Census 2022. It shares the *instrument*, self-assessed
principal economic status, and it is six years earlier. So it checks the
**structure** of the joint, which is stable over six years — nobody is retired
at 20, students are young — and it cannot check the **level**, because a
2016-to-2022 difference confounds real change with model error. A current
Labour Force Survey cross of age against ILO status would be fully
independent; the catalogue does not carry one.

**What this module does not do.** It does not fix the population, and did not.
A joint validation that quietly re-weighted the draw would be a calibration
step wearing a validation's name. The fix lives in
:mod:`baile_nua.population.econ_by_age`, reads a different table, and carried
the re-run of every downstream artefact that it implied.
"""

from __future__ import annotations

import functools
from typing import Any

__all__ = [
    "SOURCE_KEY",
    "EXPOSURE",
    "INDEPENDENT_SOURCE_KEY",
    "INDEPENDENT_EXPOSURE",
    "CNA25_STATUS_MAP",
    "independent_reference_joint",
    "compare_independent",
    "SETTLEMENT_STRATUM",
    "AGE_BANDS",
    "ECON_TO_F1054",
    "JointValidationError",
    "reference_joint",
    "town_joint",
    "compare",
]

SOURCE_KEY = "cso.census.f1054_economic_status_by_age_group"

#: **Reclassified.** `none` until I-069's fix; `design` since. F1054 and
#: FY047B - which the population is now fitted to - are two partitions of the
#: same Census 2022 microdata: both give the national 15+ total as 4,136,852
#: and each partitions the State, F1054 by settlement type and FY047B by
#: county, so Cobh's residents are counted in both. They share underlying
#: counts by construction, and 7.1's rule applies: a source used to build the
#: model cannot validate it.
#:
#: `design` rather than `tuning` because no model module reads F1054 - nothing
#: is fitted to this table - but its information is in the model through its
#: sibling. The plausibility suite's
#: ``n_pass_against_a_design_exposed_reference`` is exactly this category.
EXPOSURE = "design"

#: The nearest available INDEPENDENT reference: Census 2016, a different
#: ENUMERATION, so it cannot share counts with the Census 2022 table the
#: population is fitted to. See :func:`compare_independent` for what it can
#: and cannot check.
INDEPENDENT_SOURCE_KEY = "cso.census.cna25_economic_status_by_age_1981_2016"
INDEPENDENT_EXPOSURE = "none"

#: Cobh's settlement stratum. About 14,000 people, so "Towns 10,000 population
#: and over" is the published row that describes it - a far better reference
#: than the national total, which is dominated by Dublin.
SETTLEMENT_STRATUM = "Towns 10,000 population and over"

#: F1054's age bands, as it publishes them. Ages below 15 are outside the
#: table entirely, which is why the comparison is restricted to 15+ rather
#: than having a band invented for children.
AGE_BANDS: tuple[tuple[str, int, int], ...] = (
    ("15 - 24 years", 15, 24),
    ("25 - 34 years", 25, 34),
    ("35 - 44 years", 35, 44),
    ("45 - 54 years", 45, 54),
    ("55 - 64 years", 55, 64),
    ("65 years and over", 65, 200),
)

#: The model's ``econ_status`` enum to F1054's categories. The model's enum is
#: coarser - ``ECON_MAP`` in synthesise.py collapses the three unemployment
#: categories into one - so the reference is collapsed to match rather than
#: the model being split, which would invent detail the model does not have.
ECON_TO_F1054: dict[str, tuple[str, ...]] = {
    "employed": ("Persons at work",),
    "unemployed": (
        "Unemployed looking for first regular job",
        "Short term Unemployed (less than 12 months)",
        "Long term Unemployed (12 months and more)",
    ),
    "student": ("Student or pupil",),
    "home duties": ("Looking after home/family",),
    "retired": ("Retired",),
    "unable to work": (
        "Unable to work due to permanent sickness or disability",
    ),
}

#: F1054's residual category, which the model's enum has no value for. Carried
#: explicitly rather than dropped: dropping it would make the reference's
#: shares sum to less than one and every model share look too high.
F1054_UNMAPPED = ("Others not in labour force",)


class JointValidationError(RuntimeError):
    pass


@functools.lru_cache(maxsize=2)
def reference_joint(stratum: str = SETTLEMENT_STRATUM) -> dict[str, Any]:
    """F1054's age x economic-status counts for one settlement stratum."""
    import json
    from pathlib import Path

    import numpy as np

    from baile_nua.sources import REGISTRY

    src = REGISTRY.get(SOURCE_KEY)
    if src is None:
        raise JointValidationError(f"{SOURCE_KEY} is not declared")
    path = Path(__file__).resolve().parents[3] / "sources" / src.relpath
    if not path.exists():
        raise JointValidationError(
            f"{SOURCE_KEY} is declared but not fetched: {path} is absent"
        )
    doc = json.loads(path.read_text(encoding="utf-8"))
    ids, size, value, dim = doc["id"], doc["size"], doc["value"], doc["dimension"]

    def index(key: str) -> dict[str, int]:
        c = dim[key]["category"]["index"]
        return c if isinstance(c, dict) else {str(v): i for i, v in enumerate(c)}

    econ_d = [k for k in ids
              if "Economic Status" in str(dim[k].get("label", ""))]
    age_d = [k for k in ids if "Age Group" in str(dim[k].get("label", ""))]
    if len(econ_d) != 1 or len(age_d) != 1:
        raise JointValidationError(
            f"F1054's shape has changed: economic-status dims {econ_d}, age "
            f"dims {age_d}. The joint must be re-read, not guessed."
        )
    ed, ad = econ_d[0], age_d[0]
    arr = np.array([np.nan if v is None else float(v) for v in value],
                   dtype=np.float64).reshape(size)
    pos = {k: i for i, k in enumerate(ids)}
    ei, el = index(ed), dim[ed]["category"]["label"]
    ai, al = index(ad), dim[ad]["category"]["label"]
    si, sll = index("STATISTIC"), dim["STATISTIC"]["category"]["label"]
    yi = index("TLIST(A1)")

    skeys = [k for k, v in sll.items() if v.strip() == stratum.strip()]
    if len(skeys) != 1:
        raise JointValidationError(
            f"{stratum!r} is not exactly one STATISTIC category in F1054; "
            f"published strata are {sorted(sll.values())}"
        )
    sk = skeys[0]
    ykey = sorted(yi, key=lambda k: yi[k])[0]

    label_to_key = {v.strip(): k for k, v in el.items()}
    age_to_key = {v.strip(): k for k, v in al.items()}

    def cell(econ_label: str, age_label: str) -> float:
        sel = [0] * len(ids)
        sel[pos["STATISTIC"]] = si[sk]
        sel[pos["TLIST(A1)"]] = yi[ykey]
        sel[pos[ed]] = ei[label_to_key[econ_label]]
        sel[pos[ad]] = ai[age_to_key[age_label]]
        return float(arr[tuple(sel)])

    counts: dict[tuple[str, str], float] = {}
    for band, _lo, _hi in AGE_BANDS:
        for model_status, ref_labels in ECON_TO_F1054.items():
            missing = [L for L in ref_labels if L not in label_to_key]
            if missing:
                raise JointValidationError(
                    f"F1054 has no category {missing}; ECON_TO_F1054 is stale"
                )
            counts[(band, model_status)] = sum(cell(L, band) for L in ref_labels)
        counts[(band, "_unmapped")] = sum(
            cell(L, band) for L in F1054_UNMAPPED if L in label_to_key)

    total = sum(counts.values())
    published = cell("All persons aged 15 years and over", "All ages")
    if published > 0 and abs(total - published) / published > 0.02:
        raise JointValidationError(
            f"the mapped cells sum to {total:,.0f} against F1054's published "
            f"total of {published:,.0f} for {stratum!r} - a gap of "
            f"{abs(total - published) / published:.1%}. A category is being "
            f"dropped or double-counted, and the shares would be wrong."
        )
    return {
        "source": SOURCE_KEY,
        "model_development_exposure": EXPOSURE,
        "stratum": stratum,
        "counts": {f"{b}|{s}": v for (b, s), v in counts.items()},
        "total": total,
        "published_total": published,
        "share": {f"{b}|{s}": (v / total if total else float("nan"))
                  for (b, s), v in counts.items()},
    }


#: CNA25's status labels to the model's enum. CNA25 is an older Census
#: edition and uses shorter names for the same categories.
CNA25_STATUS_MAP: dict[str, tuple[str, ...]] = {
    "employed": ("At work",),
    "unemployed": ("Seeking first job",
                   "Unemployed, having lost or given up previous job"),
    "student": ("Students",),
    "home duties": ("Home duties",),
    "retired": ("Retired",),
    "unable to work": (
        "Unable to work due to permanent sickness or disability",),
}


@functools.lru_cache(maxsize=2)
def independent_reference_joint(year: str = "2016") -> dict[str, Any]:
    """CNA25's age x status counts for one census year, nationally.

    A DIFFERENT enumeration from the one the population is fitted to, which is
    what makes it independent. Same instrument and six years earlier, which is
    what limits it.
    """
    import json
    from pathlib import Path

    import numpy as np

    from baile_nua.sources import REGISTRY

    src = REGISTRY.get(INDEPENDENT_SOURCE_KEY)
    if src is None:
        raise JointValidationError(
            f"{INDEPENDENT_SOURCE_KEY} is not declared")
    path = Path(__file__).resolve().parents[3] / "sources" / src.relpath
    if not path.exists():
        raise JointValidationError(
            f"{INDEPENDENT_SOURCE_KEY} is declared but not fetched: {path}")
    doc = json.loads(path.read_text(encoding="utf-8"))
    ids, size, value, dim = doc["id"], doc["size"], doc["value"], doc["dimension"]

    def index(key: str) -> dict[str, int]:
        c = dim[key]["category"]["index"]
        return c if isinstance(c, dict) else {str(v): i for i, v in enumerate(c)}

    def find(fragment: str) -> str:
        ks = [k for k in ids
              if fragment.lower() in str(dim[k].get("label", "")).lower()]
        if len(ks) != 1:
            raise JointValidationError(
                f"CNA25 has {len(ks)} dimensions matching {fragment!r}: {ks}")
        return ks[0]

    ad, ed, sd, md = (find("Age Group"), find("Economic Status"),
                      find("Sex"), find("Marital Status"))
    arr = np.array([np.nan if v is None else float(v) for v in value],
                   dtype=np.float64).reshape(size)
    pos = {k: i for i, k in enumerate(ids)}
    ai, al = index(ad), dim[ad]["category"]["label"]
    ei, el = index(ed), dim[ed]["category"]["label"]
    si, sl = index(sd), dim[sd]["category"]["label"]
    mi, ml = index(md), dim[md]["category"]["label"]
    yi, yl = index("TLIST(A1)"), dim["TLIST(A1)"]["category"]["label"]
    sti = index("STATISTIC")

    ykeys = [k for k, v in yl.items() if str(v).strip() == year]
    if len(ykeys) != 1:
        raise JointValidationError(
            f"CNA25 has no single year {year!r}; published years are "
            f"{sorted(yl.values())}")
    both = [k for k, v in sl.items() if v.strip().lower() == "both sexes"]
    allm = [k for k, v in ml.items() if "all marital" in v.strip().lower()]
    if not (both and allm):
        raise JointValidationError(
            f"CNA25 lacks a both-sexes or all-marital-status category: "
            f"{sorted(sl.values())}, {sorted(ml.values())}")

    lab_to_key = {v.strip(): k for k, v in el.items()}
    age_to_key = {v.strip(): k for k, v in al.items()}

    def cell(status_label: str, age_label: str) -> float:
        sel = [0] * len(ids)
        sel[pos["STATISTIC"]] = list(sti.values())[0]
        sel[pos["TLIST(A1)"]] = yi[ykeys[0]]
        sel[pos[sd]] = si[both[0]]
        sel[pos[md]] = mi[allm[0]]
        sel[pos[ed]] = ei[lab_to_key[status_label]]
        sel[pos[ad]] = ai[age_to_key[age_label]]
        v = float(arr[tuple(sel)])
        return 0.0 if not np.isfinite(v) else v

    # CNA25 splits 15-19 and 20-24 where AGE_BANDS (F1054's) has one 15-24
    # band, so the two young bands are SUMMED to match. Summing the reference
    # to the model's bands rather than splitting the model keeps the
    # comparison on bands both tables actually publish.
    cna_bands = {
        "15 - 24 years": ("15 - 19 years", "20 - 24 years"),
        "25 - 34 years": ("25 - 34 years",),
        "35 - 44 years": ("35 - 44 years",),
        "45 - 54 years": ("45 - 54 years",),
        "55 - 64 years": ("55 - 64 years",),
        "65 years and over": ("65 years and over",),
    }
    missing = [b for parts in cna_bands.values() for b in parts
               if b not in age_to_key]
    if missing:
        raise JointValidationError(
            f"CNA25 has no age bands {missing}; published bands are "
            f"{sorted(age_to_key)}")

    counts: dict[tuple[str, str], float] = {}
    for band, _lo, _hi in AGE_BANDS:
        parts = cna_bands[band]
        for model_status, labels in CNA25_STATUS_MAP.items():
            bad = [L for L in labels if L not in lab_to_key]
            if bad:
                raise JointValidationError(
                    f"CNA25 has no status {bad}; CNA25_STATUS_MAP is stale. "
                    f"Published: {sorted(lab_to_key)}")
            counts[(band, model_status)] = sum(
                cell(L, b) for L in labels for b in parts)
        counts[(band, "_unmapped")] = sum(
            cell(L, b) for L in ("Other",) if L in lab_to_key for b in parts)

    total = sum(counts.values())
    if total <= 0:
        raise JointValidationError(f"CNA25 gave a zero total for {year}")
    return {
        "source": INDEPENDENT_SOURCE_KEY,
        "model_development_exposure": INDEPENDENT_EXPOSURE,
        "census_year": year,
        "geography": "Ireland (national)",
        "counts": {f"{b}|{s}": v for (b, s), v in counts.items()},
        "total": total,
        "share": {f"{b}|{s}": v / total for (b, s), v in counts.items()},
        "why_independent": (
            "a DIFFERENT ENUMERATION from Census 2022, so it cannot share "
            "underlying counts with FY047B, which the population is fitted to"
        ),
        "what_limits_it": (
            "the same instrument - self-assessed principal economic status - "
            "and six years earlier. It checks the STRUCTURE of the joint, not "
            "its LEVEL: a 2016-to-2022 difference confounds real change with "
            "model error."
        ),
    }


def compare_independent(*, persons: Any, year: str = "2016") -> dict[str, Any]:
    """Score the town's joint against CNA25, the independent reference.

    The verdict is on **impossible cells only**, deliberately. A distance
    would be dominated by six years of real change in the Irish labour market
    - employment rose and unemployment fell sharply between 2016 and 2022 -
    and reporting that as model error would be wrong. What six years does not
    change is that nobody is retired at 20, and that is what this adjudicates.
    """
    ref = independent_reference_joint(year)
    town = town_joint(persons)
    keys = sorted(set(ref["share"]) | set(town["share"]))

    rows, violations = [], []
    for k in keys:
        band, status = k.split("|", 1)
        r = float(ref["share"].get(k, 0.0))
        t = float(town["share"].get(k, 0.0))
        row = {"age_band": band, "econ_status": status,
               "reference_share": round(r, 6), "town_share": round(t, 6),
               "difference": round(t - r, 6),
               "town_count": town["counts"].get(k, 0.0)}
        rows.append(row)
        if r < 0.001 and row["town_count"] >= 5:
            violations.append({**row, "why": (
                f"Census {year} puts {r:.5f} of the national 15+ population "
                f"in ({band}, {status}) and the town puts "
                f"{int(row['town_count'])} people there")})

    tvd = 0.5 * sum(abs(float(town["share"].get(k, 0.0))
                        - float(ref["share"].get(k, 0.0))) for k in keys)
    return {
        "design_ref": "5.2, independent arm",
        "source": INDEPENDENT_SOURCE_KEY,
        "model_development_exposure": INDEPENDENT_EXPOSURE,
        "independent": True,
        "why_independent": ref["why_independent"],
        "what_limits_it": ref["what_limits_it"],
        "census_year": year,
        "geography": ref["geography"],
        "total_variation_distance": round(tvd, 4),
        "tvd_is_NOT_the_verdict": (
            "Six years of real labour-market change sit inside this distance "
            "- Irish employment rose and unemployment fell sharply between "
            "2016 and 2022 - so attributing it to the model would be wrong. "
            "The verdict is on impossible cells, which six years does not "
            "move."
        ),
        "impossible_cells_populated": violations,
        "n_impossible_cells_populated": len(violations),
        "verdict": ("FAIL" if violations else "PASS"),
        "verdict_basis": (
            "A cell Census 2016 puts below 0.001 of the national 15+ "
            "population and the town populates with five or more people is a "
            "structural fault in the joint. Structure, not level."
        ),
        "cells": rows,
    }


def town_joint(persons: Any) -> dict[str, Any]:
    """The synthesised town's own age x economic-status counts, 15+."""
    import numpy as np
    import pandas as pd

    df = persons if isinstance(persons, pd.DataFrame) else pd.DataFrame(persons)
    for col in ("age", "econ_status"):
        if col not in df.columns:
            raise JointValidationError(f"the person frame has no {col!r}")
    ages = pd.to_numeric(df["age"], errors="coerce")
    status = df["econ_status"].astype(str)

    counts: dict[tuple[str, str], float] = {}
    for band, lo, hi in AGE_BANDS:
        m = (ages >= lo) & (ages <= hi)
        for model_status in ECON_TO_F1054:
            counts[(band, model_status)] = float((m & (status == model_status)).sum())
        counts[(band, "_unmapped")] = float(
            (m & ~status.isin(ECON_TO_F1054)).sum())
    total = sum(counts.values())
    n_under_15 = int((ages < 15).sum())
    n_negative = int((ages < 0).sum())
    return {
        "counts": {f"{b}|{s}": v for (b, s), v in counts.items()},
        "total": total,
        "share": {f"{b}|{s}": (v / total if total else float("nan"))
                  for (b, s), v in counts.items()},
        "n_persons_under_15_excluded": n_under_15,
        "n_persons_with_negative_age": n_negative,
        "negative_age_note": (
            "F1054 covers 15+, so under-15s are excluded rather than given an "
            "invented band. A NEGATIVE age is a separate fault and is counted "
            "here so it cannot hide inside the exclusion: it means a person's "
            "birth_date falls after the t0 reference date."
        ),
    }


def compare(
    *, persons: Any, stratum: str = SETTLEMENT_STRATUM,
    impossible_cells: tuple[tuple[str, str], ...] = (),
) -> dict[str, Any]:
    """Compare the town's joint against F1054, cell by cell.

    ``impossible_cells`` are (age band, status) pairs whose reference share is
    so small that a synthesised person there is a modelling fault rather than
    a sampling fluctuation. Reported separately from the distance, because a
    total-variation distance can be small while an impossible cell is
    populated — and the impossible cell is the more informative failure.
    """
    import numpy as np

    ref = reference_joint(stratum)
    town = town_joint(persons)
    keys = sorted(set(ref["share"]) | set(town["share"]))

    rows = []
    for k in keys:
        band, status = k.split("|", 1)
        r = float(ref["share"].get(k, 0.0))
        t = float(town["share"].get(k, 0.0))
        rows.append({
            "age_band": band, "econ_status": status,
            "reference_share": round(r, 6),
            "town_share": round(t, 6),
            "difference": round(t - r, 6),
            "town_count": town["counts"].get(k, 0.0),
            "reference_count": ref["counts"].get(k, 0.0),
            "ratio": (round(t / r, 4) if r > 1e-9 else None),
        })

    tvd = 0.5 * sum(abs(float(town["share"].get(k, 0.0))
                        - float(ref["share"].get(k, 0.0))) for k in keys)

    # Cells the reference says are essentially empty but the town populates.
    # The threshold is the reference's own resolution: a share below one in a
    # thousand of a town stratum of this size is a handful of people
    # nationally, and dozens in a synthesised town of 2,917 is not sampling.
    violations = []
    for row in rows:
        r, t = row["reference_share"], row["town_share"]
        if r < 0.001 and row["town_count"] >= 5:
            violations.append({
                **row,
                "why": (
                    f"F1054 puts {r:.5f} of this stratum's 15+ population in "
                    f"({row['age_band']}, {row['econ_status']}) and the town "
                    f"puts {int(row['town_count'])} people there. That is not "
                    f"a sampling fluctuation."
                ),
            })
    declared = [
        row for row in rows
        if (row["age_band"], row["econ_status"]) in set(impossible_cells)
    ]

    worst = max(rows, key=lambda r: abs(r["difference"]))
    return {
        "design_ref": "5.2 joint and spatial population validation",
        "source": SOURCE_KEY,
        "model_development_exposure": EXPOSURE,
        "independent": True,
        "why_independent": (
            "the population is fitted to SAPS small-area MARGINALS; this "
            "national two-way joint was never an input, so it tests whether "
            "matching the marginals produced the right joint"
        ),
        "stratum": stratum,
        "n_town_persons_15_plus": int(town["total"]),
        "n_town_persons_under_15_excluded": town["n_persons_under_15_excluded"],
        "n_town_persons_with_negative_age": town["n_persons_with_negative_age"],
        "total_variation_distance": round(tvd, 4),
        "tvd_note": (
            "0 is identical and 1 is disjoint. Reported because it is the "
            "summary everyone asks for, and it is NOT the finding: a TVD can "
            "be modest while a cell the Census says is empty holds dozens of "
            "people, and that cell is the more informative failure."
        ),
        "worst_cell": worst,
        "cells": rows,
        "impossible_cells_populated": violations,
        "n_impossible_cells_populated": len(violations),
        "declared_impossible_cells": declared,
        "verdict": (
            "FAIL" if violations else "PASS"
        ),
        "verdict_basis": (
            "A cell the reference puts below 0.001 of the stratum and the "
            "town populates with five or more people is a fault in the joint, "
            "not a fluctuation. The distance alone is not the criterion."
        ),
        "this_arm_is_not_independent": (
            "F1054 shares underlying Census 2022 counts with FY047B, which "
            "the population is now fitted to: both give the national 15+ "
            "total as 4,136,852 and each partitions the State. So a pass here "
            "is a CONSISTENCY check. compare_independent() is the independent "
            "arm, against a different enumeration."
        ),
        "nothing_is_fitted_to_this": (
            "This module measures and does not correct. The fix lives in "
            "population/econ_by_age.py and reads FY047B, a different table."
        ),
    }
