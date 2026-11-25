"""Assessed element U-values from SEAI's BER Research Tool (I-048, week 3 step 1).

`data/fabric_u_values.yaml` derived every dwelling's fabric from its
construction era and then nudged it with a BER-band multiplier capped at 0.55,
and the whole table was one ``[A]`` flag: *"not read back from the Part L
documents in this run; verify in WP1"*. I-048 proposed that Irish old stock is
better insulated than that implies, and could not be tested because nothing
published said what the real fabric was.

**The retrofit state did not have to be assumed at all.** SEAI's National BER
Research Tool - CC-BY 4.0, listed on data.gov.ie - publishes the *assessed*
U-value of every element of every rated dwelling, with its year of
construction, its BER band and its dwelling type. So rather than assuming what
fraction of old dwellings have filled cavities, the model can read the U-value
distribution **conditional on (era, band)** straight from the source. The BER
band already encodes the retrofit state; this says what U-value that state
corresponds to.

That matters for how this module may be used. The brief's rule is that
retrofit-state shares must be sourced or ``[A]`` with a search record, and
**never chosen to close the U31 gradient**. There is no share here to choose:
the numbers are medians of an assessed population, and
:data:`SEARCH_RECORD` records that PxStat has nothing, which is why the SEAI
dataset was sought in the first place.

What the comparison found, over the town's 1,092 dwellings against about 1.08
million assessed existing dwellings:

==============================  ==========================
model / assessed wall U-value   median
==============================  ==========================
old stock (pre-1919 to 1961-80) **1.97**
new stock (1981-2000, 2001+)    **0.75**
ratio between them              **2.6**
==============================  ==========================

and the worst cells are exactly the ones I-048 named: a pre-1919 dwelling
rated A or B is modelled at 1.16 to 1.58 W/m2K where the assessed median is
0.25 to 0.37, four to five times too lossy, because the band multiplier bottoms
out at 0.55. For unretrofitted old stock (bands F, G) the model is about right.

I-048 inferred "roughly 1.8x steeper than the meters say" from the gas
divergence. This measures 2.6x from element U-values against an assessed
population - a different quantity, a different source, the same direction and
order. One mechanism accounts for both halves of that divergence: the model
over-states loss on retrofitted old stock and under-states it on new stock.

**What this is not.** BER coverage is not a census; the project's own
``ber.py`` records that it "over-represents recently assessed dwellings". So
the *marginal* distribution over dwellings is biased and is not used. What is
used is the U-value **conditional** on (era, band, type), which that bias
affects far less, restricted to ``TypeofRating = 'Existing'`` so new-build
ratings do not contaminate the retrofit question.
"""

from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Any

__all__ = [
    "SOURCE_KEY",
    "FABRIC_EXPOSURE",
    "assert_not_a_fabric_validation_reference",
    "VALIDATES_FABRIC",
    "SEARCH_RECORD",
    "ERA_CELLS",
    "BAND_LETTERS",
    "CACHE_PATH",
    "MIN_CELL_N",
    "assessed_u_values",
    "era_cell",
    "u_for",
    "u_for_cell",
    "build_cache",
    "AssessedFabricError",
]

SOURCE_KEY = "seai.ber.research_tool"

#: This dataset is **tuning-exposed for fabric**. The model's element U-values
#: are derived from it, so it can never afterwards validate fabric: modelled
#: against assessed U-values would come out at 1.0 by construction and read as
#: agreement. Design 7.1 keeps calibration and validation disjoint, and this is
#: the calibration side.
FABRIC_EXPOSURE = "tuning"
VALIDATES_FABRIC = False

#: What the I-048 measurement was, and when. The 1.913 old / 0.750 new
#: divergence was measured BEFORE this source influenced the model, which is
#: what makes it a finding rather than a description of a fit. Re-running the
#: same comparison after the derivation is wired in is not a validation.
I048_MEASURED_BEFORE_EXPOSURE = True

#: The independent axis that DOES validate fabric, since this one cannot:
#: gas. DBERNG01 (dwelling type x BER band) is the tuned reference; DBERNG02
#: (dwelling type x period of construction) is held out at exposure "none" and
#: U31 is evaluation-only. A fabric change earns its keep by moving the gas
#: ratio and the U31 gradient, not by agreeing with the table it came from.
FABRIC_VALIDATION_SOURCES = (
    "cso.gas.dberng01_by_dwelling_ber",
    "cso.gas.dberng02_by_dwelling_construction",
)


def assert_not_a_fabric_validation_reference(context: str = "") -> None:
    """Refuse to let this dataset be used to validate the fabric it derived.

    Call this from anything that compares modelled fabric against a reference.
    It always raises, because there is no legitimate way to use this source
    that way - the point is to make the attempt loud rather than to allow it
    under a flag.
    """
    raise AssessedFabricError(
        f"{SOURCE_KEY} is TUNING-EXPOSED for fabric: the model's element "
        f"U-values are derived from it, so comparing modelled against "
        f"assessed U-values would come out at 1.0 by construction and read as "
        f"agreement (design 7.1 keeps calibration and validation disjoint). "
        f"The independent fabric validation is gas: "
        f"{', '.join(FABRIC_VALIDATION_SOURCES)}, with DBERNG02 held out and "
        f"U31 evaluation-only."
        + (f" Context: {context}" if context else "")
    )

#: Where the extracted conditional is cached. The raw source is 1.5 GB of
#: tab-separated text and querying it takes about a minute, which is too slow
#: for a unit test and pointless to repeat - but the cache is BUILT from the
#: source by :func:`build_cache` and a test rebuilds it and compares, so the
#: cached values cannot drift from the dataset they claim to come from.
CACHE_PATH = Path(__file__).resolve().parents[1] / "data" / "fabric_assessed.json"

#: Era cells, chosen to be wide enough that every (era, band) cell has a usable
#: count. Measured: the smallest cell is about 700 dwellings.
ERA_CELLS: tuple[str, ...] = ("pre1919", "1919-1960", "1961-1980",
                              "1981-2000", "2001+")

BAND_LETTERS: tuple[str, ...] = ("A", "B", "C", "D", "E", "F", "G")

#: A cell with fewer than this many assessed dwellings is not published here.
#: Not a privacy threshold - the source is already anonymised and aggregated -
#: but a precision one: a median over 50 dwellings is not a population value.
MIN_CELL_N = 100


class AssessedFabricError(RuntimeError):
    pass


#: ``(search term, tables returned, verdict)``. The I-040 rule: an ``[A]`` flag
#: records what was searched. These searches are why the SEAI dataset was
#: sought rather than assumed, so they belong with the result.
SEARCH_RECORD: tuple[tuple[str, int, str], ...] = (
    (r"[Ii]nsulat", 0, "ZERO tables across all 13,086. PxStat publishes "
                       "nothing on insulation, in any title or dimension."),
    (r"[Cc]avity", 0, "ZERO."),
    (r"[Aa]ttic", 0, "ZERO."),
    (r"[Ll]oft", 0, "ZERO."),
    (r"[Uu].value", 0, "ZERO. No PxStat table publishes a U-value."),
    (r"[Ff]abric", 0, "ZERO."),
    (r"[Hh]eat loss", 0, "ZERO."),
    (r"[Gg]lazing", 0, "ZERO."),
    (r"[Rr]oof", 0, "ZERO."),
    (r"[Rr]etrofit", 0, "ZERO - already recorded under A-25f for the "
                        "adoption rate; it is equally empty for the state."),
    (r"[Bb]etter [Ee]nergy", 0, "ZERO. The SEAI grant scheme's own name "
                                "returns nothing."),
    (r"[Ww]armer [Hh]omes", 0, "ZERO."),
    (r"[Ee]nergy [Uu]pgrade", 0, "ZERO."),
    (r"[Dd]eep [Rr]etrofit", 0, "ZERO."),
    (r"[Gg]rant[s]? paid", 0, "ZERO."),
    (r"[Hh]ome [Ee]nergy", 0, "ZERO."),
    (r"[Ww]all [Ii]nsulation", 0, "ZERO."),
    (r"[Ww]all", 14,
     "Fourteen hits and every one is 'wallet/purse' - the TRA trust-survey "
     "tables. A substring collision, like 'sport' inside 'transport' "
     "(A-43). A hit count is not evidence."),
    ("SEAI National BER Research Tool (not PxStat)", 1,
     "FOUND, and it is better than a penetration share: it publishes the "
     "ASSESSED U-value of every element of every rated dwelling with its "
     "year of construction and BER band. CC-BY 4.0 on data.gov.ie. "
     "ADOPTED - so no retrofit-state share is assumed anywhere."),
)


def era_cell(build_year: int) -> str:
    """Which era cell a construction year falls in."""
    if build_year < 1919:
        return "pre1919"
    if build_year <= 1960:
        return "1919-1960"
    if build_year <= 1980:
        return "1961-1980"
    if build_year <= 2000:
        return "1981-2000"
    return "2001+"


def build_cache(*, write: bool = True) -> dict[str, Any]:
    """Query the BER Research Tool and extract the conditional U-values.

    Reads the 1.5 GB tab-separated extract with DuckDB, as the project's
    convention requires for anything this size.

    Two traps in this dataset, both found the hard way and both guarded:

    * every string value is **space-padded to a fixed width**, so
      ``"TypeofRating" = 'Existing'`` matches nothing and ``TRIM`` is
      mandatory. A query without it returns an empty frame rather than an
      error, which is the worst way to be wrong.
    * ``EnergyRating`` carries the full band (``A1``, ``C2``), so the letter
      has to be taken from the first character to get cells with usable
      counts.
    """
    import zipfile

    import duckdb

    from baile_nua.sources import REGISTRY, require

    archive = require(SOURCE_KEY)
    with zipfile.ZipFile(archive) as zf:
        member = next(
            n for n in zf.namelist() if n.lower().endswith(".txt")
            and "readme" not in n.lower()
        )
        tmp = archive.parent / member
        if not tmp.exists():
            zf.extract(member, path=archive.parent)

    con = duckdb.connect()
    con.execute("SET TimeZone='UTC'")
    rows = con.execute(
        """
        WITH r AS (
          SELECT TRY_CAST("Year_of_Construction" AS INTEGER) AS yr,
                 TRIM("EnergyRating") AS band,
                 TRY_CAST("UValueWall"   AS DOUBLE) AS u_wall,
                 TRY_CAST("UValueRoof"   AS DOUBLE) AS u_roof,
                 TRY_CAST("UValueFloor"  AS DOUBLE) AS u_floor,
                 TRY_CAST("UValueWindow" AS DOUBLE) AS u_win
          FROM read_csv(?, delim='\t', header=true, ignore_errors=true,
                        all_varchar=true)
          WHERE TRIM("TypeofRating") = 'Existing'
        )
        SELECT CASE WHEN yr < 1919 THEN 'pre1919'
                    WHEN yr <= 1960 THEN '1919-1960'
                    WHEN yr <= 1980 THEN '1961-1980'
                    WHEN yr <= 2000 THEN '1981-2000'
                    ELSE '2001+' END AS era,
               SUBSTR(band, 1, 1) AS band_letter,
               COUNT(*) AS n,
               MEDIAN(u_wall) AS wall_p50,
               QUANTILE_CONT(u_wall, 0.25) AS wall_p25,
               QUANTILE_CONT(u_wall, 0.75) AS wall_p75,
               MEDIAN(u_roof) AS roof_p50,
               MEDIAN(u_floor) AS floor_p50,
               MEDIAN(u_win) AS window_p50
        FROM r
        WHERE yr BETWEEN 1700 AND 2026 AND band <> ''
          AND u_wall BETWEEN 0.05 AND 5 AND u_roof BETWEEN 0.05 AND 8
          AND u_floor BETWEEN 0.05 AND 5 AND u_win BETWEEN 0.3 AND 7
        GROUP BY 1, 2
        HAVING COUNT(*) >= ?
        ORDER BY 1, 2
        """,
        [str(tmp), MIN_CELL_N],
    ).fetchall()
    if not rows:
        raise AssessedFabricError(
            "the BER Research Tool query returned no cells. The most likely "
            "cause is the fixed-width padding: every string value in this "
            "dataset is space-padded, so a comparison without TRIM silently "
            "matches nothing."
        )

    manifest = json.loads(
        REGISTRY[SOURCE_KEY].manifest_path.read_text(encoding="utf-8")
    )
    cells: dict[str, dict[str, Any]] = {}
    for (era, band, n, w50, w25, w75, r50, f50, g50) in rows:
        cells[f"{era}|{band}"] = {
            "era": era, "band": band, "n": int(n),
            "wall_p50": round(float(w50), 4),
            "wall_p25": round(float(w25), 4),
            "wall_p75": round(float(w75), 4),
            "roof_p50": round(float(r50), 4),
            "floor_p50": round(float(f50), 4),
            "window_p50": round(float(g50), 4),
        }
    out = {
        "source_key": SOURCE_KEY,
        "source_sha256": manifest["sha256"],
        "rating_type": "Existing",
        "min_cell_n": MIN_CELL_N,
        "n_cells": len(cells),
        "n_assessed_dwellings": sum(c["n"] for c in cells.values()),
        "cells": cells,
        "note": (
            "Medians of ASSESSED element U-values, conditional on era cell and "
            "BER band letter, over existing-dwelling ratings. The BER band "
            "already encodes the retrofit state; this says what U-value that "
            "state corresponds to, so no retrofit penetration share is "
            "assumed anywhere."
        ),
        "coverage_caveat": (
            "BER coverage is not a census and over-represents recently "
            "assessed dwellings, so the MARGINAL distribution is biased and "
            "is not used. The conditional on (era, band) is what is used."
        ),
    }
    if write:
        CACHE_PATH.write_text(json.dumps(out, indent=2))
    return out


@functools.lru_cache(maxsize=1)
def assessed_u_values() -> dict[str, Any]:
    """The cached conditional, with its source hash checked against the registry."""
    from baile_nua.sources import REGISTRY

    if not CACHE_PATH.exists():
        raise AssessedFabricError(
            f"{CACHE_PATH.name} is missing. Build it with "
            f"`fabric_assessed.build_cache()`; it is derived from "
            f"{SOURCE_KEY} and is not hand-written."
        )
    doc = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(
        REGISTRY[SOURCE_KEY].manifest_path.read_text(encoding="utf-8")
    )
    if doc.get("source_sha256") != manifest["sha256"]:
        raise AssessedFabricError(
            f"{CACHE_PATH.name} was built from source sha "
            f"{str(doc.get('source_sha256'))[:16]}... and the registered "
            f"source is now {manifest['sha256'][:16]}.... Rebuild it rather "
            f"than trusting a cache of different bytes."
        )
    return doc


def u_for_cell(era: str, ber_band: str, element: str = "wall") -> float:
    """The assessed median for an era CELL and band, with a band fallback.

    Separate from :func:`u_for` because ``derive_rc`` knows the model's era
    *label* rather than the construction year, and mapping label to cell
    belongs with the caller's own era definitions.
    """
    cells = assessed_u_values()["cells"]
    letter = str(ber_band)[:1].upper()
    key = f"{era}|{letter}"
    if key in cells:
        return float(cells[key][f"{element}_p50"])
    order = list(BAND_LETTERS)
    if letter not in order:
        raise AssessedFabricError(f"unknown BER band {ber_band!r}")
    i = order.index(letter)
    for offset in range(1, len(order)):
        for j in (i - offset, i + offset):
            if 0 <= j < len(order):
                k2 = f"{era}|{order[j]}"
                if k2 in cells:
                    return float(cells[k2][f"{element}_p50"])
    raise AssessedFabricError(
        f"no assessed cell for era {era!r} at any band"
    )


def u_for(build_year: int, ber_band: str, element: str = "wall") -> float:
    """The assessed median U-value for a dwelling's era and band.

    Falls back along the band letter rather than to an era average: a band G
    dwelling whose exact cell is thin is far better served by the nearest
    published band in the same era than by that era's mean, which mixes
    retrofitted and unretrofitted stock.
    """
    cells = assessed_u_values()["cells"]
    era = era_cell(int(build_year))
    letter = str(ber_band)[:1].upper()
    key = f"{era}|{letter}"
    if key in cells:
        return float(cells[key][f"{element}_p50"])
    order = list(BAND_LETTERS)
    if letter not in order:
        raise AssessedFabricError(f"unknown BER band {ber_band!r}")
    i = order.index(letter)
    for offset in range(1, len(order)):
        for j in (i - offset, i + offset):
            if 0 <= j < len(order):
                k2 = f"{era}|{order[j]}"
                if k2 in cells:
                    return float(cells[k2][f"{element}_p50"])
    raise AssessedFabricError(
        f"no assessed cell for era {era!r} at any band; the cache is empty "
        f"for that era"
    )
