"""SEAI/CSO Building Energy Rating data for Co. Cork (design 5.2, 5.7; closes I-011).

Two gaps in SAPS that this fills, both found by reading the glossary rather than
assuming the columns existed:

1. **SAPS publishes no detached / semi-detached / terraced split.**  Table 6.1
   has only House/Bungalow, Flat/Apartment, Bed-Sit and Caravan.  The schema's
   ``dwelling_type`` enum, the archetype library (design 5.7) and U18's
   "Terraced" gap all need the split, and terraced matters physically - two
   party walls rather than one.
2. **SAPS records heating *fuel*, not heating *system*.**  A heat pump and a
   direct electric resistance system are both "Electricity", yet their COP
   differs by a factor of three or more and dominates the heating load.

CSO **EBA02** (from the SEAI BER register) is a genuine *joint* table, not a set
of marginals: BER band x dwelling type x main space-heating fuel x year of
construction x county.  That is strictly better than what the design assumed was
available, because it means a building's BER can be conditioned on its dwelling
type, age and fuel together rather than drawn from independent marginals.

CSO **EBQ02** adds renewable-energy penetration (heat pump, solar, both, none)
by NUTS3 region, which is how the electricity-heated homes are split into heat
pumps and direct electric.

**The Census stays the anchor.**  BER coverage is not a census: it covers
dwellings that have been assessed, which over-represents new builds and
properties recently sold or let.  So BER is used only for *conditional* shapes -
the split within houses, and the system within a fuel - while every *marginal*
that SAPS publishes (the house/apartment ratio, the fuel shares, the year-built
distribution) is held to SAPS.  :func:`conditional_dwelling_split` and
:func:`heating_system_split` return conditional distributions for exactly that
reason.
"""

from __future__ import annotations

import functools
import json
from typing import Any

import numpy as np
import pandas as pd

from baile_nua.sources import require

__all__ = [
    "COBH_COUNTY",
    "COBH_NUTS3_NAME",
    "ber_table",
    "conditional_dwelling_split",
    "ber_given_type_and_age",
    "heating_system_split",
    "HOUSE_TYPES",
    "APARTMENT_TYPES",
]

#: Cobh is in Co. Cork, which CSO reports separately from Cork City.
COBH_COUNTY = "Co. Cork"
#: NUTS3 for Cork, read from the OSi small-area attributes (not recalled).
COBH_NUTS3_NAME = "South-West"

HOUSE_TYPES = (
    "Detached house", "Semi-detached house", "End of terrace house",
    "Mid-terrace house", "House (not stated)",
)
APARTMENT_TYPES = (
    "Ground-floor apartment", "Mid-floor apartment", "Top-floor apartment",
    "Apartment (not stated)", "Basement dwelling", "Maisonette",
)

#: How BER dwelling types map onto the schema's ``dwelling_type`` enum.
#: "not stated" is apportioned over the stated categories rather than becoming
#: its own type, because the schema has no "not stated" dwelling and inventing
#: one would propagate a data-quality artefact into the physics.
TYPE_TO_ENUM: dict[str, str] = {
    "Detached house": "detached",
    "Semi-detached house": "semi-detached",
    "End of terrace house": "terraced",
    "Mid-terrace house": "terraced",
    "Ground-floor apartment": "apartment",
    "Mid-floor apartment": "apartment",
    "Top-floor apartment": "apartment",
    "Apartment (not stated)": "apartment",
    "Basement dwelling": "apartment",
    "Maisonette": "apartment",
}


def _jsonstat_to_frame(path, drop_totals: bool = True) -> pd.DataFrame:
    """Flatten a JSON-stat 2.0 cube into a tidy frame.

    JSON-stat stores the cube as a flat value list in row-major order over the
    declared dimension sizes, with nulls for suppressed or absent cells.  It is
    flattened explicitly here rather than with a library so the index arithmetic
    is visible and testable: getting it wrong would silently transpose two
    dimensions and produce a plausible-looking but wrong distribution.
    """
    doc = json.loads(path.read_text(encoding="utf-8"))
    ids: list[str] = doc["id"]
    sizes: list[int] = doc["size"]
    dim = doc["dimension"]
    labels = {k: list(dim[k]["category"]["label"].values()) for k in ids}

    raw = doc["value"]
    if isinstance(raw, dict):
        # Sparse form: {"flat_index": value}
        total = int(np.prod(sizes))
        values: list[Any] = [None] * total
        for k, v in raw.items():
            values[int(k)] = v
    else:
        values = list(raw)

    # Row-major strides, last dimension fastest.
    strides = [1] * len(sizes)
    for i in range(len(sizes) - 2, -1, -1):
        strides[i] = strides[i + 1] * sizes[i + 1]

    cols: dict[str, list] = {k: [] for k in ids}
    vals: list[float] = []
    for flat, v in enumerate(values):
        if v is None:
            continue
        rem = flat
        coords = []
        for i in range(len(sizes)):
            coords.append(rem // strides[i])
            rem = rem % strides[i]
        for k, c in zip(ids, coords):
            cols[k].append(labels[k][c])
        vals.append(float(v))

    frame = pd.DataFrame(cols)
    frame["value"] = vals
    # Rename the opaque CSO dimension codes to something readable.
    rename = {k: dim[k].get("label", k) for k in ids}
    frame = frame.rename(columns=rename)
    if drop_totals:
        for c in frame.columns:
            if c == "value":
                continue
            mask = frame[c].astype(str).str.lower().str.startswith(("all ", "all"))
            frame = frame[~mask]
    return frame.reset_index(drop=True)


@functools.lru_cache(maxsize=1)
def ber_table() -> pd.DataFrame:
    """EBA02 for Co. Cork: BER x dwelling type x fuel x year built, by year.

    Returns the cumulative stock as most recently reported, which is what a
    building-stock distribution needs - the series is cumulative BER
    certificates issued, so the latest year is the fullest picture.
    """
    frame = _jsonstat_to_frame(require("cso.ber.eba02_by_county"))
    county_col = next(c for c in frame.columns if "county" in c.lower())
    frame = frame[frame[county_col] == COBH_COUNTY]
    if frame.empty:
        raise RuntimeError(f"no rows for {COBH_COUNTY!r} in EBA02")
    year_col = next(c for c in frame.columns if c.lower() in ("year", "tlist(a1)"))
    latest = sorted(frame[year_col].unique())[-1]
    frame = frame[frame[year_col] == latest].copy()
    frame.attrs["reference_year"] = latest
    frame.attrs["county"] = COBH_COUNTY
    return frame.reset_index(drop=True)


def _col(frame: pd.DataFrame, *needles: str) -> str:
    for c in frame.columns:
        low = c.lower()
        if all(n in low for n in needles):
            return c
    raise KeyError(f"no column matching {needles} in {list(frame.columns)}")


def conditional_dwelling_split() -> dict[str, dict[str, float]]:
    """How houses and apartments divide into the schema's dwelling types.

    Returns ``{"house": {...}, "apartment": {...}}`` with each inner dict summing
    to 1.  Conditional on purpose: the house/apartment *ratio* comes from the
    Census marginal (SAPS Table 6.1), and only the split *within* each is taken
    from BER, because BER coverage over-represents recently assessed dwellings.
    """
    frame = ber_table()
    tcol = _col(frame, "dwelling")
    out: dict[str, dict[str, float]] = {}
    for group, members in (("house", HOUSE_TYPES), ("apartment", APARTMENT_TYPES)):
        sub = frame[frame[tcol].isin(members)]
        totals = sub.groupby(tcol)["value"].sum()
        # Apportion "not stated" over the stated types in proportion.
        stated = {k: v for k, v in totals.items() if "not stated" not in k.lower()}
        not_stated = float(sum(v for k, v in totals.items() if "not stated" in k.lower()))
        s = sum(stated.values())
        if s <= 0:
            continue
        enum_totals: dict[str, float] = {}
        for k, v in stated.items():
            enum = TYPE_TO_ENUM[k]
            enum_totals[enum] = enum_totals.get(enum, 0.0) + v + not_stated * (v / s)
        tot = sum(enum_totals.values())
        out[group] = {k: v / tot for k, v in sorted(enum_totals.items())}
    return out


def ber_given_type_and_age() -> pd.DataFrame:
    """BER band distribution conditional on dwelling type and year of construction.

    This is the joint structure SAPS cannot give.  Used to draw a building's BER
    once its type and age are fixed by the Census marginals, so that - as in
    reality - a pre-1919 terrace and a 2016 detached house do not draw from the
    same BER distribution.
    """
    frame = ber_table()
    tcol, bcol, acol = _col(frame, "dwelling"), _col(frame, "ber"), _col(frame, "construction")
    g = (
        frame.groupby([tcol, acol, bcol])["value"].sum().reset_index()
        .rename(columns={tcol: "dwelling_type_ber", acol: "year_built_band", bcol: "ber_band"})
    )
    g["dwelling_type"] = g["dwelling_type_ber"].map(TYPE_TO_ENUM)
    g = g.dropna(subset=["dwelling_type"])
    tot = g.groupby(["dwelling_type", "year_built_band"])["value"].transform("sum")
    g["share"] = np.where(tot > 0, g["value"] / tot, 0.0)
    return g.sort_values(["dwelling_type", "year_built_band", "ber_band"]).reset_index(drop=True)


@functools.lru_cache(maxsize=1)
def heating_system_split() -> dict[str, Any]:
    """Split electrically-heated homes into heat pumps and direct electric.

    From EBQ02's renewable-energy dimension for the South-West region, which is
    Cork.  Without this, design 5.7's heating-system model cannot distinguish a
    heat pump from resistance heating, and the two differ by a factor of three or
    more in delivered heat per unit of electricity.
    """
    frame = _jsonstat_to_frame(require("cso.ber.ebq02_renewables"))
    rcol = next(
        (c for c in frame.columns if "region" in c.lower() or "nuts" in c.lower()),
        None,
    )
    if rcol is not None:
        sub = frame[frame[rcol] == COBH_NUTS3_NAME]
        if sub.empty:
            sub = frame
    else:
        sub = frame
    ncol = next(
        c for c in sub.columns
        if "renewable" in c.lower() or "solar" in c.lower() or "heat pump" in c.lower()
    )
    ycol = next((c for c in sub.columns if c.lower() in ("quarter", "tlist(q1)")), None)
    if ycol is not None:
        latest = sorted(sub[ycol].unique())[-1]
        sub = sub[sub[ycol] == latest]
    totals = sub.groupby(ncol)["value"].sum()
    grand = float(totals.sum())
    shares = {k: float(v) / grand for k, v in totals.items()} if grand > 0 else {}
    hp = sum(v for k, v in shares.items() if "heat pump" in k.lower())
    solar = sum(v for k, v in shares.items() if "solar" in k.lower())
    return {
        "region": COBH_NUTS3_NAME,
        "shares": shares,
        "heat_pump_share_of_assessed": hp,
        "solar_share_of_assessed": solar,
        "note": (
            "Shares of BER-ASSESSED dwellings, which over-represent new builds. "
            "Used only to split within the Census electricity-fuel category, "
            "never as a town-wide penetration rate."
        ),
    }
