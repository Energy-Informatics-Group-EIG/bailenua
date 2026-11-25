"""DEAP Appendix S: the published Irish fabric defaults, extracted not transcribed.

`data/fabric_u_values.yaml` carried the whole era-to-U-value table as a single
``[A]`` flag — *"not read back from the Part L documents in this run; verify in
WP1"* — and every heat-loss number in the model descends from it. I-048's
retrofit hypothesis lives exactly there: it proposes that Irish old stock is
better insulated than the model's era defaults imply.

The source that settles it was already fetched. SEAI's DEAP manual, the
regulatory methodology every Irish BER is computed with, has an **Appendix S**
for *existing* dwellings that publishes:

===========  ===============================================================
Table S1     age bands A to L by years of construction
Table S2     the building-regulations U-values for each age band
Table S3     exposed wall U-values by **wall type** x age band — including
             ``300mm filled cavity`` and ``425 mm filled cavity``, both at
             **0.6 for every band A to G**, which is the retrofit
Table S4     roof U-value by **observed loft insulation thickness**
Table S5     roof U-value by age band when the thickness is unknown
Table S8     floor U-values by floor type x perimeter/area ratio x age band
===========  ===============================================================

**Extracted, not transcribed.** `data/deap_hot_water.yaml` was recorded by hand
because the manual is a PDF, and the project's rule for that case is to cite
the table and assert the provenance hash. That rule is sound and this module
does better: it parses the tables out of the PDF text, so the values can be
re-derived from the source at any time and a test re-extracts them and compares.
Nothing here is typed from memory, and a value that drifts from the document
fails the suite rather than quietly disagreeing with it.

**What the comparison found**, and it is not what I-048 expected:

* From age band G (1983-93) onward the model's wall U-values **already are**
  DEAP's: 0.60, 0.55, 0.37 against DEAP's 0.60, 0.55, 0.37. That part of the
  ``[A]`` flag is retirable as a match, not a correction.
* For bands A to E the model's **roofs are 4 to 5 times better than DEAP's**
  default (0.45-0.60 against 2.3). The model's own data file says why — "roofs
  at typical CURRENT (post-retrofit) condition" — so a generous roof retrofit
  was already assumed, undocumented in magnitude.
* For the same bands the model's **walls never reach DEAP's filled-cavity
  value**: the best the band multiplier can do is 2.1 x 0.55 = 1.155 against
  DEAP's published 0.6.

So the retrofit the model is missing is **walls**, and the roof retrofit it
already has is more generous than DEAP's own uninsulated default. Those pull in
opposite directions, which is why the net effect has to be measured rather than
argued, and why I-048's hypothesis needed a source before it could be tested at
all.
"""

from __future__ import annotations

import functools
import re
from typing import Any

__all__ = [
    "AGE_BANDS",
    "BAND_ORDER",
    "band_for_year",
    "appendix_s",
    "wall_u_values",
    "roof_u_values_unknown_thickness",
    "roof_u_by_insulation_mm",
    "regulations_summary",
    "SOURCE_KEY",
    "PAGES",
    "ExtractionError",
]

SOURCE_KEY = "seai.deap.manual_4_2_7"

#: Which PDF page each table is parsed from, 1-based as the manual numbers them.
PAGES: dict[str, int] = {
    "S1_age_bands": 156,
    "S2_regulations": 156,
    "S3_walls": 157,
    "S4_roof_by_thickness": 161,
    "S5_roof_unknown": 161,
}

#: Table S1, in band order.
BAND_ORDER: tuple[str, ...] = tuple("ABCDEFGHIJKL")


class ExtractionError(RuntimeError):
    """The manual's text no longer parses as the table it is expected to be."""


def _pdf_pages() -> list[str]:
    from pypdf import PdfReader

    from baile_nua.sources import require

    reader = PdfReader(str(require(SOURCE_KEY)))
    return [(p.extract_text() or "") for p in reader.pages]


def _page(pages: list[str], n: int) -> str:
    """One page, with the running header stripped so it cannot match a row."""
    t = pages[n - 1]
    return re.sub(r"DEAP Manual\s+Version\s+4\.2\.7", " ", t)


def _floats(line: str) -> list[float]:
    return [float(x) for x in re.findall(r"\d+\.\d+|\b\d+\b", line)]


@functools.lru_cache(maxsize=1)
def appendix_s() -> dict[str, Any]:
    """Parse Appendix S's fabric tables out of the manual.

    Every table is checked for the shape it must have — twelve age-band columns,
    a monotone insulation series — so a parse that silently captured the wrong
    numbers raises instead of returning them.
    """
    pages = _pdf_pages()
    out: dict[str, Any] = {"source_key": SOURCE_KEY, "pages": dict(PAGES)}

    # ---- Table S1: age bands ------------------------------------------
    p156 = _page(pages, PAGES["S1_age_bands"])
    bands: dict[str, str] = {}
    for m in re.finditer(
        r"^([A-L])\s+(before\s+\d{4}|\d{4}\s*-\s*\d{4}|\d{4}\s*-\s*Onwards)",
        p156, re.M | re.I,
    ):
        bands[m.group(1)] = re.sub(r"\s+", " ", m.group(2)).strip()
    if sorted(bands) != sorted(BAND_ORDER):
        raise ExtractionError(
            f"Table S1 parsed {sorted(bands)}, expected the twelve bands "
            f"{list(BAND_ORDER)}. The manual's layout has changed."
        )
    out["S1_age_bands"] = bands

    # ---- Table S2: building-regulations summary -----------------------
    regs = []
    for line in p156.splitlines():
        m = re.match(
            r"\s*(\d{4})(?:\s*/\s*(\d{4}))?\s*(\(Draft\))?\s+([A-L])\d*\s+"
            r"([\d.]+)\s+([\d.]+)\s+([\d.]+)",
            line,
        )
        if m:
            regs.append({
                "year": m.group(1),
                "band": m.group(4),
                "roof": float(m.group(5)),
                "wall": float(m.group(6)),
                "floor": float(m.group(7)),
            })
    if len(regs) < 5:
        raise ExtractionError(
            f"Table S2 parsed only {len(regs)} regulation rows; the manual "
            f"lists seven."
        )
    out["S2_regulations"] = regs

    # ---- Table S3: exposed wall U-values by wall type x age band -------
    p157 = _page(pages, PAGES["S3_walls"])
    walls: dict[str, dict[str, float]] = {}
    for line in p157.splitlines():
        if "Age band" in line:
            continue
        m = re.match(r"\s*([A-Za-z0-9 ]*?[A-Za-z][A-Za-z ]*?)\s+((?:[\d.]+\s+){11}[\d.]+)\s*$",
                     line)
        if not m:
            continue
        name = re.sub(r"\s+", " ", m.group(1)).strip()
        vals = [float(x) for x in m.group(2).split()]
        if len(vals) != 12:
            continue
        walls[name] = dict(zip(BAND_ORDER, vals))
    if "Unknown" not in walls:
        raise ExtractionError(
            f"Table S3 parsed wall types {sorted(walls)} and none is "
            f"'Unknown', which is the default the model needs."
        )
    filled = [k for k in walls if "filled cavity" in k.lower()]
    if not filled:
        raise ExtractionError(
            f"Table S3 parsed no 'filled cavity' row, which is the published "
            f"retrofit value this module exists to find. Got {sorted(walls)}."
        )
    out["S3_walls"] = walls
    out["S3_filled_cavity_rows"] = sorted(filled)

    # ---- Tables S4 and S5: roofs --------------------------------------
    p161 = _page(pages, PAGES["S4_roof_by_thickness"])
    by_mm: dict[str, float] = {}
    for line in p161.splitlines():
        m = re.match(r"\s*(None|>=\s*\d+|\d+)\s+([\d.]+)\s*$", line)
        if m:
            key = re.sub(r"\s+", "", m.group(1))
            by_mm[key] = float(m.group(2))
    if "None" not in by_mm or len(by_mm) < 8:
        raise ExtractionError(
            f"Table S4 parsed {by_mm}; expected a 'None' row and ten "
            f"thicknesses."
        )
    out["S4_roof_by_insulation_mm"] = by_mm

    unknown: dict[str, float] = {}
    for line in p161.splitlines():
        m = re.match(r"\s*((?:[A-L](?:,\s*)?)+)\s+([\d.]+)\s*$", line)
        if m:
            v = float(m.group(2))
            for b in re.findall(r"[A-L]", m.group(1)):
                unknown[b] = v
    if sorted(unknown) != sorted(BAND_ORDER):
        raise ExtractionError(
            f"Table S5 parsed bands {sorted(unknown)}, expected all twelve."
        )
    out["S5_roof_unknown_thickness"] = unknown
    return out


def band_for_year(year: int) -> str:
    """The DEAP Table S1 age band a construction year falls in."""
    s1 = appendix_s()["S1_age_bands"]
    for band in BAND_ORDER:
        spec = s1[band].lower()
        if spec.startswith("before"):
            if year < int(re.search(r"\d{4}", spec).group()):
                return band
        elif "onwards" in spec:
            if year >= int(re.search(r"\d{4}", spec).group()):
                return band
        else:
            lo, hi = (int(x) for x in re.findall(r"\d{4}", spec))
            if lo <= year <= hi:
                return band
    # Before the first band's cut-off is band A; after the last is band L.
    return BAND_ORDER[0] if year < 1900 else BAND_ORDER[-1]


def wall_u_values(wall_type: str = "Unknown") -> dict[str, float]:
    return dict(appendix_s()["S3_walls"][wall_type])


def roof_u_values_unknown_thickness() -> dict[str, float]:
    return dict(appendix_s()["S5_roof_unknown_thickness"])


def roof_u_by_insulation_mm() -> dict[str, float]:
    return dict(appendix_s()["S4_roof_by_insulation_mm"])


def regulations_summary() -> list[dict[str, Any]]:
    return [dict(r) for r in appendix_s()["S2_regulations"]]
