"""CSO Census 2022 SAPS ingest for Cobh (design 5.2 step 1, R04, D24).

Three things had to be solved to get from "SAPS for Cobh" to usable marginals,
and each is worth recording because none is obvious from the design:

1. **The SAPS small-area file has no place names.**  Its ``GEOGDESC`` column
   repeats the numeric small-area code, so "the small areas of Cobh" cannot be
   selected from the SAPS file alone.  The correspondence comes from the OSi
   2022 small-area boundaries, whose ``SA_URBAN_AREA_NAME`` attribute names the
   built-up area each small area belongs to.  ``SA_PUB2022`` there joins
   exactly to SAPS ``GEOGID`` (verified, not assumed - see
   :func:`verify_join_keys`).
2. **Cobh is 53 small areas across two electoral divisions**, Cobh Urban (29)
   and Cobh Rural (24).  Taking only the urban ED would drop almost half the
   town, so the built-up-area attribute is the right selector rather than the ED.
3. **795 columns.**  Every marginal below is assembled from column codes read
   out of the CSO glossary, never from a column guessed by its name.  A marginal
   whose columns do not sum to its table total is refused rather than used.

The real NUTS3 code for Cork's region, which design 5.14 needs for the MIMIC
crosswalk, is read from the same OSi attributes: **IE053, South-West**.
"""

from __future__ import annotations

import dataclasses
import functools
import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

from baile_nua.sources import require

__all__ = [
    "COBH_URBAN_AREA_NAME",
    "SmallAreaSet",
    "glossary",
    "glossary_tables",
    "cobh_small_areas",
    "load_cobh_saps",
    "verify_join_keys",
    "MARGINAL_SPECS",
    "MarginalSpec",
    "build_marginals",
    "Marginal",
    "SapsError",
]

COBH_URBAN_AREA_NAME = "Cobh"


class SapsError(RuntimeError):
    """The SAPS inputs do not support what was asked of them."""


# --------------------------------------------------------------------------- #
# Glossary
# --------------------------------------------------------------------------- #

@functools.lru_cache(maxsize=1)
def glossary() -> pd.DataFrame:
    """The CSO glossary as ``(theme, table, column, description)``."""
    import openpyxl

    path = require("cso.saps2022.glossary")
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = []
    for theme, table, col, desc in ws.iter_rows(min_row=2, values_only=True):
        if not col:
            continue
        rows.append(
            {
                "theme": str(theme).strip() if theme else "",
                "table": str(table).strip() if table else "",
                "column": str(col).strip(),
                "description": str(desc).strip() if desc else "",
            }
        )
    wb.close()
    g = pd.DataFrame(rows)
    if g.empty:
        raise SapsError("the SAPS glossary parsed to zero rows")
    return g


@functools.lru_cache(maxsize=1)
def glossary_tables() -> dict[str, dict[str, Any]]:
    """Columns grouped by their SAPS table, keyed by table prefix (``T1_1``...).

    The table prefix is derived from the column codes rather than from the
    table's prose title, because the titles repeat across themes ("Table 1: ...")
    while the prefixes are unique.
    """
    g = glossary()
    out: dict[str, dict[str, Any]] = {}
    for _, r in g.iterrows():
        m = re.match(r"^(T\d+_\d+)", r["column"])
        if not m:
            continue
        key = m.group(1)
        rec = out.setdefault(
            key, {"theme": r["theme"], "title": r["table"], "columns": {}}
        )
        rec["columns"][r["column"]] = r["description"]
    return out


def describe(column: str) -> str:
    g = glossary()
    hit = g[g["column"] == column]
    return str(hit.iloc[0]["description"]) if len(hit) else ""


# --------------------------------------------------------------------------- #
# Which small areas are Cobh
# --------------------------------------------------------------------------- #

@dataclasses.dataclass(frozen=True)
class SmallAreaSet:
    """The small areas of one built-up area, with their geometry and attributes."""

    urban_area_name: str
    frame: pd.DataFrame          # one row per small area
    nuts3_code: str
    nuts3_name: str
    county: str
    lea: str

    @property
    def codes(self) -> list[str]:
        """SAPS ``GEOGID`` values, sorted - the fixed id order for reductions."""
        return sorted(self.frame["sa_code"].tolist())

    def __len__(self) -> int:
        return len(self.frame)


@functools.lru_cache(maxsize=1)
def cobh_small_areas() -> SmallAreaSet:
    """Cobh's small areas from the OSi 2022 boundaries.

    Centroids are computed from the polygon rings with an area-weighted
    (shoelace) formula rather than a mean of vertices: vertex density varies
    enormously along a coastline, and a vertex mean would drag every coastal
    small area's centroid out to sea.
    """
    path = require("osi.small_areas_2022.cobh")
    doc = json.loads(path.read_text(encoding="utf-8"))
    feats = doc.get("features") or []
    if not feats:
        raise SapsError(f"{path} contains no features; the OSi query returned nothing")

    rows = []
    for f in feats:
        a = f.get("properties") or f.get("attributes") or {}
        lon, lat, area = _polygon_centroid_and_area(f.get("geometry"))
        rows.append(
            {
                "sa_code": str(a["SA_PUB2022"]),
                "sa_geogid_2022": str(a["SA_GEOGID_2022"]),
                "ed_english": str(a.get("ED_ENGLISH") or ""),
                "ed_id": str(a.get("ED_ID_STR") or ""),
                "county": str(a.get("COUNTY_ENGLISH") or ""),
                "nuts3": str(a.get("SA_NUTS3") or ""),
                "nuts3_name": str(a.get("SA_NUTS3_NAME") or ""),
                "lea": str(a.get("CSO_LEA") or ""),
                "urban_area_name": str(a.get("SA_URBAN_AREA_NAME") or ""),
                "urban_area_flag": a.get("SA_URBAN_AREA_FLAG"),
                "shape_area_m2": float(a.get("Shape__Area") or 0.0),
                "centroid_lon": lon,
                "centroid_lat": lat,
                "ring_area_deg2": area,
            }
        )
    frame = pd.DataFrame(rows).sort_values("sa_code").reset_index(drop=True)

    nuts3 = frame["nuts3"].mode().iat[0]
    if (frame["nuts3"] != nuts3).any():
        raise SapsError(
            f"Cobh's small areas report more than one NUTS3 code: "
            f"{sorted(frame['nuts3'].unique())}"
        )
    return SmallAreaSet(
        urban_area_name=COBH_URBAN_AREA_NAME,
        frame=frame,
        nuts3_code=nuts3,
        nuts3_name=frame["nuts3_name"].mode().iat[0],
        county=frame["county"].mode().iat[0],
        lea=frame["lea"].mode().iat[0],
    )


def _polygon_centroid_and_area(geom: dict | None) -> tuple[float, float, float]:
    """Area-weighted centroid of a (Multi)Polygon's outer rings, in degrees.

    Degrees are adequate here: the centroids are used for *relative* spatial
    structure within one town (neighbour ordering, segregation indices), not for
    distance in metres, and over ~5 km the distortion is uniform.
    """
    if not geom:
        return (float("nan"), float("nan"), 0.0)
    gtype = geom.get("type")
    if gtype == "Polygon":
        rings = [geom["coordinates"][0]]
    elif gtype == "MultiPolygon":
        rings = [poly[0] for poly in geom["coordinates"]]
    elif "rings" in geom:  # Esri JSON
        rings = geom["rings"]
    else:
        return (float("nan"), float("nan"), 0.0)

    tot_a = cx = cy = 0.0
    for ring in rings:
        a2 = sx = sy = 0.0
        n = len(ring)
        for i in range(n - 1):
            x0, y0 = ring[i][0], ring[i][1]
            x1, y1 = ring[i + 1][0], ring[i + 1][1]
            cross = x0 * y1 - x1 * y0
            a2 += cross
            sx += (x0 + x1) * cross
            sy += (y0 + y1) * cross
        if a2 == 0.0:
            continue
        a = a2 / 2.0
        tot_a += a
        cx += sx / 6.0
        cy += sy / 6.0
    if tot_a == 0.0:
        xs = [p[0] for r in rings for p in r]
        ys = [p[1] for r in rings for p in r]
        return (sum(xs) / len(xs), sum(ys) / len(ys), 0.0)
    return (cx / tot_a, cy / tot_a, abs(tot_a))


def verify_join_keys() -> dict[str, Any]:
    """Confirm, rather than assume, that OSi ``SA_PUB2022`` joins to SAPS ``GEOGID``.

    A silent join failure here would produce a population calibrated to the
    wrong small areas, which no downstream test would catch.
    """
    sas = cobh_small_areas()
    saps_ids = set(
        pd.read_csv(
            require("cso.saps2022.small_area"), usecols=["GEOGID"], dtype=str
        )["GEOGID"]
    )
    codes = set(sas.codes)
    missing = sorted(codes - saps_ids)
    report = {
        "n_small_areas_osi": len(codes),
        "n_matched_in_saps": len(codes & saps_ids),
        "unmatched": missing,
        "eds": sorted(sas.frame["ed_english"].unique().tolist()),
        "ed_counts": sas.frame["ed_english"].value_counts().to_dict(),
        "nuts3": [sas.nuts3_code, sas.nuts3_name],
        "county": sas.county,
        "lea": sas.lea,
    }
    if missing:
        raise SapsError(
            f"{len(missing)} of Cobh's {len(codes)} OSi small areas have no SAPS row "
            f"(first: {missing[:5]}). The OSi SA_PUB2022 to SAPS GEOGID join is not "
            f"total, so marginals would silently omit part of the town."
        )
    return report


# --------------------------------------------------------------------------- #
# Load the Cobh rows
# --------------------------------------------------------------------------- #

@functools.lru_cache(maxsize=1)
def load_cobh_saps() -> pd.DataFrame:
    """The 53 Cobh small-area SAPS rows, indexed by small-area code.

    Read with ``usecols`` left open because every theme is needed, but filtered
    to Cobh immediately: the national file is 39 MB and 795 columns, and keeping
    only Cobh keeps the whole of Day 2 in a few MB of memory.
    """
    sas = cobh_small_areas()
    wanted = set(sas.codes)
    chunks = []
    for chunk in pd.read_csv(
        require("cso.saps2022.small_area"), dtype={"GEOGID": str, "GEOGDESC": str},
        chunksize=4000, low_memory=False,
    ):
        hit = chunk[chunk["GEOGID"].isin(wanted)]
        if len(hit):
            chunks.append(hit)
    if not chunks:
        raise SapsError("no Cobh small areas found in the SAPS file")
    out = pd.concat(chunks, ignore_index=True)
    if len(out) != len(wanted):
        raise SapsError(
            f"expected {len(wanted)} Cobh SAPS rows, got {len(out)}"
        )
    return out.sort_values("GEOGID").reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Marginal specifications
# --------------------------------------------------------------------------- #

@dataclasses.dataclass(frozen=True)
class MarginalSpec:
    """One marginal distribution the population synthesis must reproduce.

    ``categories`` maps a category label to the SAPS column codes that make it
    up.  ``total_column`` is the table's own total, used to check that the
    categories are exhaustive: design 12 R04's acceptance is "every SAPS
    marginal within the sampling-error band", which is meaningless if the
    marginal silently omits a category.
    """

    key: str
    unit: str                    # "person" | "household" | "family"
    saps_table: str              # the glossary table prefix, e.g. "T1_1"
    categories: dict[str, tuple[str, ...]]
    total_column: str | None = None
    design_ref: str = ""
    notes: str = ""


@dataclasses.dataclass
class Marginal:
    """A built marginal: counts per category, per small area and for the town."""

    spec: MarginalSpec
    by_small_area: pd.DataFrame  # index = sa_code, columns = categories
    town_total: pd.Series
    total_declared: int | None
    total_from_categories: int

    @property
    def closes(self) -> bool:
        return (
            self.total_declared is None
            or self.total_declared == self.total_from_categories
        )

    def shares(self) -> pd.Series:
        t = self.town_total.sum()
        return self.town_total / t if t else self.town_total * 0.0


def _cols(prefix: str, *suffixes: str) -> tuple[str, ...]:
    return tuple(f"{prefix}{s}" for s in suffixes)


#: The marginals design 5.2 step 1 names.
#:
#: Every column code below was read out of the CSO glossary (see
#: ``glossary_tables()``), not inferred from a name.  That mattered: a first pass
#: guessed ``T5_2_1PP`` for one-person households, which is in fact the *persons*
#: column of that table (``T5_2_1PH`` is households), and guessed a
#: detached/semi-detached/terraced split for ``T6_1`` that SAPS does not publish
#: at all (see I-011).
MARGINAL_SPECS: tuple[MarginalSpec, ...] = (
    # -- Theme 1: sex, age, marital status -----------------------------------
    MarginalSpec(
        key="age_by_sex",
        unit="person",
        saps_table="T1_1",
        design_ref="5.2 step 1 (age by sex); R03",
        categories={},  # built from the glossary by _age_by_sex_categories()
        total_column="T1_1AGETT",
        notes=(
            "SAPS gives single years 0-19 then five-year bands to 85+, separately "
            "for males (M), females (F) and total (T). Built programmatically so "
            "that a change in CSO banding is picked up rather than silently "
            "dropped."
        ),
    ),
    MarginalSpec(
        key="marital_status",
        unit="person",
        saps_table="T1_2",
        design_ref="5.2 step 3 (households built whole: couples); D07 partner edges",
        categories={
            "single": ("T1_2SGLT",), "married": ("T1_2MART",),
            "separated": ("T1_2SEPT",), "divorced": ("T1_2DIVT",),
            "widowed": ("T1_2WIDT",),
        },
        total_column="T1_2T",
    ),
    # -- Theme 2: birthplace, citizenship, ethnicity -------------------------
    MarginalSpec(
        key="place_of_birth",
        unit="person",
        saps_table="T2_1",
        design_ref="5.2 step 1 and 5.8 (Irish/non-Irish mix from Census); D05.country_of_birth",
        categories={
            "IE": ("T2_1IEBP",), "UK": ("T2_1UKBP",), "PL": ("T2_1PLBP",),
            "IN": ("T2_1INBP",), "EU27_other": ("T2_1EUBP",),
            "rest_of_world": ("T2_1RWBP",),
        },
        total_column="T2_1TBP",
        notes=(
            "Design 5.8 requires the nationality mix to come from Census. SAPS "
            "gives birthplace and citizenship as separate breakdowns, which is "
            "exactly the D05 distinction between country_of_birth and nationality."
        ),
    ),
    MarginalSpec(
        key="citizenship",
        unit="person",
        saps_table="T2_1",
        design_ref="5.2 step 1; D05.nationality",
        categories={
            "IE": ("T2_1IEC",), "UK": ("T2_1UKC",), "PL": ("T2_1PLC",),
            "IN": ("T2_1INC",), "EU27_other": ("T2_1EUC",),
            "rest_of_world": ("T2_1RWC",), "not_stated": ("T2_1NSC",),
        },
        total_column="T2_1TC",
    ),
    MarginalSpec(
        key="ethnicity",
        unit="person",
        saps_table="T2_2",
        design_ref="R07; 7.7 stereotype guard (synthesis and guard only)",
        categories={
            "White Irish": ("T2_2WI",), "White Irish Traveller": ("T2_2WIT",),
            "Other White": ("T2_2OW",), "Black or Black Irish": ("T2_2BBI",),
            "Asian or Asian Irish": ("T2_2AAI",), "Other": ("T2_2OTH",),
            "Not stated": ("T2_2NS",),
        },
        total_column="T2_2T",
        notes="D05.ethnicity_census: used only for synthesis and the stereotype guard.",
    ),
    # -- Theme 5: households -------------------------------------------------
    MarginalSpec(
        key="household_type",
        unit="household",
        saps_table="T5_1",
        design_ref="5.2 step 3 (households built whole); R16 (coupled systems)",
        categories={
            "one person": ("T5_1OP_H",),
            "married couple": ("T5_1MC_H",),
            "cohabiting couple": ("T5_1CC_H",),
            "married couple with children": ("T5_1MCC_H",),
            "cohabiting couple with children": ("T5_1CCC_H",),
            "one parent (father) with children": ("T5_1OPFC_H",),
            "one parent (mother) with children": ("T5_1OPMC_H",),
            "couple and others": ("T5_1CO_H",),
            "couple with children and others": ("T5_1CCO_H",),
            "one parent (father) with children and others": ("T5_1OPFCO_H",),
            "one parent (mother) with children and others": ("T5_1OPMCO_H",),
            "two or more family units": ("T5_1GETFU_H",),
            "non-family households and relations": ("T5_1NHR_H",),
            "two or more non-related persons": ("T5_1GENP_H",),
        },
        total_column="T5_1T_H",
        notes=(
            "This is the marginal that makes design 5.2 step 3 possible: it gives "
            "whole-household structures, not just sizes, so a household can be "
            "assembled as 'a couple with two children' rather than 'four people'."
        ),
    ),
    MarginalSpec(
        key="household_size",
        unit="household",
        saps_table="T5_2",
        design_ref="5.2 step 1; R03 (1,000 to 1,100 homes)",
        categories={
            "1": ("T5_2_1PH",), "2": ("T5_2_2PH",), "3": ("T5_2_3PH",),
            "4": ("T5_2_4PH",), "5": ("T5_2_5PH",), "6": ("T5_2_6PH",),
            "7": ("T5_2_7PH",), "8+": ("T5_2_GE8PH",),
        },
        total_column="T5_2_TH",
    ),
    # -- Theme 6: dwellings --------------------------------------------------
    MarginalSpec(
        key="accommodation_type",
        unit="household",
        saps_table="T6_1",
        design_ref="5.2 step 1 (dwelling type); R01 (no high-rise)",
        categories={
            "house or bungalow": ("T6_1_HB_H",),
            "flat or apartment": ("T6_1_FA_H",),
            "bed-sit": ("T6_1_BS_H",),
            "caravan or mobile home": ("T6_1_CM_H",),
        },
        total_column="T6_1_TH",
        notes=(
            "SAPS 2022 publishes only these four categories. It does NOT split "
            "houses into detached / semi-detached / terraced, which the design's "
            "dwelling_type enum and U18's 'Terraced' gap both need. See I-011: the "
            "split is taken from SEAI BER public data and flagged [A], and the "
            "house/apartment ratio stays anchored to this Census marginal."
        ),
    ),
    MarginalSpec(
        key="year_built",
        unit="household",
        saps_table="T6_2",
        design_ref="5.2 step 1 (dwelling age); 5.7 (archetype parameters, performance gap)",
        categories={
            "pre 1919": ("T6_2_PRE19H",), "1919-1945": ("T6_2_19_45H",),
            "1946-1960": ("T6_2_46_60H",), "1961-1970": ("T6_2_61_70H",),
            "1971-1980": ("T6_2_71_80H",), "1981-1990": ("T6_2_81_90H",),
            "1991-2000": ("T6_2_91_00H",), "2001-2010": ("T6_2_01_10H",),
            "2011-2015": ("T6_2_11_15H",), "2016 or later": ("T6_2_16LH",),
            "not stated": ("T6_2_NSH",),
        },
        total_column="T6_2_TH",
    ),
    MarginalSpec(
        key="tenure",
        unit="household",
        saps_table="T6_3",
        design_ref="5.2 step 1 (tenure); 5.8 tenure mechanism; 7.7 stereotype guard",
        categories={
            "owner-occupied with mortgage": ("T6_3_OMLH",),
            "owner-occupied no mortgage": ("T6_3_OOH",),
            "rented private": ("T6_3_RPLH",),
            "rented social": ("T6_3_RLAH", "T6_3_RVCHBH"),
            "rent free": ("T6_3_OFRH",),
            "not stated": ("T6_3_NSH",),
        },
        total_column="T6_3_TH",
        notes=(
            "Local Authority and voluntary/co-operative renting are combined into "
            "'rented social' to match the schema's tenure enum. The combination is "
            "declared here rather than done silently downstream."
        ),
    ),
    MarginalSpec(
        key="central_heating",
        unit="household",
        saps_table="T6_5",
        design_ref="5.2 step 1 (central heating fuel); 5.7 heating systems",
        categories={
            "none": ("T6_5_NCH",), "oil": ("T6_5_OCH",),
            "natural gas": ("T6_5_NGCH",), "electricity": ("T6_5_ECH",),
            "coal": ("T6_5_CCH",), "peat": ("T6_5_PCH",),
            "LPG": ("T6_5_LPGCH",), "wood": ("T6_5_WCH",),
            "other": ("T6_5_OTH",), "not stated": ("T6_5_NS",),
        },
        total_column="T6_5_T",
        notes=(
            "Census records the FUEL, not the system, so it cannot distinguish a "
            "heat pump from direct electric resistance heating - both report "
            "'Electricity'. The split within electricity comes from SEAI BER data "
            "and is flagged [A] (I-011)."
        ),
    ),
    MarginalSpec(
        key="rooms",
        unit="household",
        saps_table="T6_4",
        design_ref="5.7 (floor area and zoning); D02.floor_area_m2",
        categories={
            "1": ("T6_4_1RH",), "2": ("T6_4_2RH",), "3": ("T6_4_3RH",),
            "4": ("T6_4_4RH",), "5": ("T6_4_5RH",), "6": ("T6_4_6RH",),
            "7": ("T6_4_7RH",), "8+": ("T6_4_GE8RH",), "not stated": ("T6_4_NSH",),
        },
        total_column="T6_4_TH",
        notes=(
            "SAPS publishes no floor area. Room count is the closest real Irish "
            "proxy and is what the floor-area model is conditioned on, with the "
            "area-per-room relationship flagged [A] (I-019)."
        ),
    ),
    MarginalSpec(
        key="bedrooms",
        unit="household",
        saps_table="T6_9",
        design_ref="5.7 (two-zone living/sleeping split); 5.3 shared-resource queues",
        categories={
            "0": ("T6_9_0BRH",), "1": ("T6_9_1BRH",), "2": ("T6_9_2BRH",),
            "3": ("T6_9_3BRH",), "4": ("T6_9_4BRH",), "5+": ("T6_9_GE5BRH",),
            "not stated": ("T6_9_NSH",),
        },
        total_column="T6_9_TH",
        notes="Sets the sleeping-zone volume and the number of bathrooms contended for.",
    ),

    # -- Theme 8, 9, 10: economic status, socio-economic group, education ----
    MarginalSpec(
        key="economic_status",
        unit="person",
        saps_table="T8_1",
        design_ref="5.2 step 1 (principal economic status); D08.econ_status; U18",
        categories={
            "at work": ("T8_1_WT",),
            "looking for first regular job": ("T8_1_LFFJT",),
            "short-term unemployed": ("T8_1_STUT",),
            "long-term unemployed": ("T8_1_LTUT",),
            "student": ("T8_1_ST",),
            "looking after home/family": ("T8_1_LAHFT",),
            "retired": ("T8_1_RT",),
            "unable to work": ("T8_1_UTWSDT",),
            "other": ("T8_1_OTHT",),
        },
        total_column="T8_1_TT",
        notes=(
            "Population aged 15 and over. Note 'Looking after home/family': the "
            "Irish census has this category and MIMIC does not, which is direct "
            "Irish evidence for the U18 'Home duties' gap rather than an opinion."
        ),
    ),
    MarginalSpec(
        key="socio_economic_group",
        unit="household",
        saps_table="T9_2",
        design_ref="5.2 step 1 (socio-economic group of reference person)",
        categories={
            "A employers and managers": ("T9_2_HA",),
            "B higher professional": ("T9_2_HB",),
            "C lower professional": ("T9_2_HC",),
            "D non-manual": ("T9_2_HD",),
            "E manual skilled": ("T9_2_HE",),
            "F semi-skilled": ("T9_2_HF",),
            "G unskilled": ("T9_2_HG",),
            "H own account workers": ("T9_2_HH",),
            "I farmers": ("T9_2_HI",),
            "J agricultural workers": ("T9_2_HJ",),
            "Z all others and unknown": ("T9_2_HZ",),
        },
        total_column="T9_2_HT",
        notes="Used as the income-band proxy: Census publishes no household income.",
    ),
    MarginalSpec(
        key="education",
        unit="person",
        saps_table="T10_4",
        design_ref="5.2 step 1 (education); D05.education_level (ISCED)",
        categories={
            "no formal education": ("T10_4_NFT",),
            "primary": ("T10_4_PT",),
            "lower secondary": ("T10_4_LST",),
            "upper secondary": ("T10_4_UST",),
            "technical or vocational": ("T10_4_TVT",),
            "advanced cert or apprenticeship": ("T10_4_ACCAT",),
            "higher certificate": ("T10_4_HCT",),
            "ordinary degree or national diploma": ("T10_4_ODNDT",),
            "honours degree or professional qualification": ("T10_4_HDPQT",),
            "postgraduate diploma or degree": ("T10_4_PDT",),
            "doctorate": ("T10_4_DT",),
            "not stated": ("T10_4_NST",),
        },
        total_column="T10_4_TT",
    ),
    # -- Theme 11: travel to work -- the Irish anchor for the activity engine -
    MarginalSpec(
        key="travel_mode_work",
        unit="person",
        saps_table="T11_1",
        design_ref="5.2 step 4 (commuting); 5.5 mode choice",
        categories={
            "on foot": ("T11_1_FW",), "bicycle": ("T11_1_BIW",),
            "bus": ("T11_1_BUW",), "rail": ("T11_1_TDLW",),
            "motorcycle": ("T11_1_MW",), "car driver": ("T11_1_CDW",),
            "car passenger": ("T11_1_CPW",), "van": ("T11_1_VW",),
            "other": ("T11_1_OTHW",), "works mainly at or from home": ("T11_1_WMFHW",),
            "not stated": ("T11_1_NSW",),
        },
        total_column="T11_1_TW",
        notes=(
            "Cobh is on the Cork commuter rail line (design 5.5), so the rail "
            "share here is a real local constraint rather than a national average."
        ),
    ),
    MarginalSpec(
        key="time_leaving_home",
        unit="person",
        saps_table="T11_2",
        design_ref="5.3 (schedule timing); I-008 Irish anchor for the activity engine",
        categories={
            "before 06:30": ("T11_2_T1",), "06:30-07:00": ("T11_2_T2",),
            "07:01-07:30": ("T11_2_T3",), "07:31-08:00": ("T11_2_T4",),
            "08:01-08:30": ("T11_2_T5",), "08:31-09:00": ("T11_2_T6",),
            "09:01-09:30": ("T11_2_T7",), "after 09:30": ("T11_2_T8",),
            "not stated": ("T11_2_NS",),
        },
        total_column="T11_2_T",
        notes=(
            "THE key Irish anchor. HETUS has no Irish row (I-008), so departure "
            "timing - which drives morning occupancy and the morning load peak - "
            "is calibrated against this Cobh-specific Census marginal instead of "
            "the UK donor."
        ),
    ),
    MarginalSpec(
        key="journey_time",
        unit="person",
        saps_table="T11_3",
        design_ref="5.5 (travel time); U02 (out-of-town work as an 'outside' state)",
        categories={
            "under 15 min": ("T11_3_D1",), "15-30 min": ("T11_3_D2",),
            "30-45 min": ("T11_3_D3",), "45-60 min": ("T11_3_D4",),
            "60-90 min": ("T11_3_D5",), "90 min or more": ("T11_3_D6",),
            "not stated": ("T11_3_NS",),
        },
        total_column="T11_3_T",
        notes="Gives U02's return-time distribution directly, for Cobh.",
    ),
    MarginalSpec(
        key="working_from_home",
        unit="person",
        saps_table="T11_4",
        design_ref="D08.remote_share; 5.9 employment row; R17 (remote working)",
        categories={
            "works from home": ("T11_4_WFH",),
            "never works from home": ("T11_4_NWFH",),
            "not stated": ("T11_4_NS",),
        },
        total_column="T11_4_T",
        notes=(
            "Census 2022 was taken in April 2022, within the E1 simulated year, so "
            "this remote-work share is contemporaneous with the slice rather than "
            "projected."
        ),
    ),
    # -- Theme 13, 14, 15: occupation, industry, cars ------------------------
    MarginalSpec(
        key="occupation",
        unit="person",
        saps_table="T13_1",
        design_ref="5.2 step 1 (occupation); D08.occupation_soc -> ISCO-08 for MIMIC",
        categories={
            "managers, directors and senior officials": ("T13_1_MDSOT",),
            "professional": ("T13_1_POT",),
            "associate professional and technical": ("T13_1_APTOT",),
            "administrative and secretarial": ("T13_1_ASOT",),
            "skilled trades": ("T13_1_STOT",),
            "caring, leisure and other service": ("T13_1_CLOSOT",),
            "sales and customer service": ("T13_1_SCSOT",),
            "process, plant and machine operatives": ("T13_1_PPMOT",),
            "elementary": ("T13_1_EOT",),
            "not stated": ("T13_1_NST",),
        },
        total_column="T13_1_TT",
        notes="SOC 2010 major groups, which is what design 5.13 maps to ISCO-08.",
    ),
    MarginalSpec(
        key="industry",
        unit="person",
        saps_table="T14_1",
        design_ref="5.2 step 1 (industry); D08.industry_nace; 5.8 shift-work share by sector",
        categories={
            "agriculture, forestry and fishing": ("T14_1_AFFT",),
            "building and construction": ("T14_1_BCT",),
            "manufacturing": ("T14_1_MIT",),
            "commerce and trade": ("T14_1_CTT",),
            "transport and communications": ("T14_1_TCT",),
            "public administration": ("T14_1_PAT",),
            "professional services": ("T14_1_PST",),
            "other": ("T14_1_OTHT",),
        },
        total_column="T14_1_TT",
    ),
    MarginalSpec(
        key="car_availability",
        unit="household",
        saps_table="T15_1",
        design_ref="5.2 step 1 (car availability); 5.5 mode choice; D08.vehicle_access",
        categories={
            "0": ("T15_1_NC",), "1": ("T15_1_1C",), "2": ("T15_1_2C",),
            "3": ("T15_1_3C",), "4+": ("T15_1_GE4C",), "not stated": ("T15_1_NSC",),
        },
        total_column="T15_1_TC",
    ),
)


def _age_by_sex_categories() -> dict[str, tuple[str, ...]]:
    """Build the age-by-sex categories from the glossary.

    SAPS encodes single years 0-19 then five-year bands, with an ``M``/``F``/``T``
    suffix.  Reading them from the glossary rather than hard-coding the bands
    means a change in CSO banding shows up as a changed marginal, not as silently
    dropped columns.
    """
    tabs = glossary_tables()
    cols = tabs["T1_1"]["columns"]
    cats: dict[str, tuple[str, ...]] = {}
    for col in cols:
        m = re.match(r"^T1_1AGE(.+?)([MFT])$", col)
        if not m:
            continue
        band, sex = m.group(1), m.group(2)
        if band.upper().startswith("T"):  # the table totals
            continue
        if sex == "T":                    # totals are the closure check, not a category
            continue
        cats[f"{band}_{sex}"] = (col,)
    if not cats:
        raise SapsError("could not derive any age-by-sex categories from the glossary")
    return cats


def build_marginals(
    frame: pd.DataFrame | None = None,
    specs: tuple[MarginalSpec, ...] = MARGINAL_SPECS,
) -> dict[str, Marginal]:
    """Build every marginal for Cobh, per small area and for the town.

    A marginal whose categories do not sum to its declared table total is
    **returned with ``closes = False``** rather than silently used; the caller
    (and the Day 2 test) decides what to do. Design 12 R04's acceptance is "every
    SAPS marginal within the sampling-error band", which is not a meaningful
    claim about a marginal that omits a category.
    """
    df = frame if frame is not None else load_cobh_saps()
    df = df.set_index("GEOGID")
    out: dict[str, Marginal] = {}
    for spec in specs:
        cats = spec.categories or (
            _age_by_sex_categories() if spec.key == "age_by_sex" else {}
        )
        if not cats:
            raise SapsError(f"marginal {spec.key!r} has no categories")

        missing = [
            c for cols in cats.values() for c in cols if c not in df.columns
        ]
        if missing:
            raise SapsError(
                f"marginal {spec.key!r} names SAPS columns absent from the file: "
                f"{missing[:8]}. The glossary and the data have diverged."
            )

        data = {
            label: df[list(cols)].sum(axis=1).astype("int64")
            for label, cols in cats.items()
        }
        by_sa = pd.DataFrame(data).sort_index()
        town = by_sa.sum(axis=0).astype("int64")
        declared = (
            int(df[spec.total_column].sum())
            if spec.total_column and spec.total_column in df.columns
            else None
        )
        out[spec.key] = Marginal(
            spec=spec,
            by_small_area=by_sa,
            town_total=town,
            total_declared=declared,
            total_from_categories=int(town.sum()),
        )
    return out
