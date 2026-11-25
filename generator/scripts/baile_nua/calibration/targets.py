"""Readers for the D24 calibration targets.

Design 5.6 and 7.2 need the device layer to be checkable, and until now it was
not: appliance trigger rates were declared assumptions [A] with nothing to
score them against, and the first E1 estate consequently drew 16.35 kWh per
home per day of appliance electricity alone - roughly 40% above the national
mean for *all* household electricity, heating included (I-027).

**The tuning split matters and is deliberate.**  DBEREL01 (dwelling type x BER
band) is declared in the source register with model_development_exposure
"tuning", because the trigger rates were adjusted against it.  DBEREL02
(dwelling type x period of construction) is declared "none" and must stay that
way: it crosses the same dwellings on an axis the tuning never saw, so it is
the only one of the two that can say whether the fit generalises.  Design 7.1
requires that exposure be recorded; keeping the two tables apart is what makes
the record mean something.
"""

from __future__ import annotations

import dataclasses
import itertools
import json
from typing import Any

from baile_nua.sources import REGISTRY, require

__all__ = [
    "CalibrationTarget",
    "TargetError",
    "build_d24",
    "electricity_by_construction_targets",
    "electricity_per_dwelling_targets",
    "floor_area_target",
    "gas_by_construction_targets",
    "gas_per_dwelling_targets",
    "meter_distribution_target",
    "per_meter_target",
    "write_d24",
]


class TargetError(RuntimeError):
    """A target's cell is missing from its source, or the source changed shape."""


@dataclasses.dataclass(frozen=True)
class CalibrationTarget:
    """One D24 row.  ``value`` was read from ``source_key`` at ``source_sha256``."""

    target_id: str
    quantity: str
    unit: str
    value: Any
    conditioned_on: dict[str, str]
    source_key: str
    source_sha256: str
    source_title: str
    year: int
    exposure: str
    #: What a comparison against this target can and cannot establish.
    scope_note: str

    def as_row(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


# --------------------------------------------------------------------------- #
# JSON-stat reading
# --------------------------------------------------------------------------- #

def _read_jsonstat(key: str) -> tuple[dict[str, Any], dict[tuple[str, ...], Any], str]:
    """Open a registered JSON-stat source and index it by label tuple.

    Indexing by *label* rather than by code deliberately: a code like
    ``C03440V04149`` means nothing in a report, and if the CSO re-codes a
    dimension the label lookup fails loudly instead of silently returning the
    wrong cell.
    """
    path = require(key)
    doc = json.loads(path.read_text(encoding="utf-8"))
    ids = doc["id"]
    labels = [list(doc["dimension"][i]["category"]["label"].values()) for i in ids]
    values = doc["value"]
    cells: dict[tuple[str, ...], Any] = {}
    for i, combo in enumerate(itertools.product(*labels)):
        cells[combo] = values[i] if isinstance(values, list) else values.get(str(i))
    man = json.loads(
        REGISTRY[key].manifest_path.read_text(encoding="utf-8")
    )
    return doc, cells, str(man["sha256"])


def _cell(cells: dict[tuple[str, ...], Any], combo: tuple[str, ...], key: str) -> float:
    if combo not in cells:
        raise TargetError(
            f"{key} has no cell {combo}. The table's dimension labels have "
            f"changed; fix the reader rather than guessing a nearby cell."
        )
    v = cells[combo]
    if v is None:
        raise TargetError(f"{key} cell {combo} is suppressed or empty (None).")
    return float(v)


# --------------------------------------------------------------------------- #
# The targets
# --------------------------------------------------------------------------- #

#: DBEREL01's dwelling labels mapped to the schema's ``dwelling_type`` enum.
#: "Mid-terrace" and "End of terrace" both map to ``terraced``: the schema has
#: one terraced category, and collapsing two source rows into one target is
#: honest only if the collapse is stated, which is what this mapping is.
_DWELLING_MAP: dict[str, str] = {
    "Apartment": "apartment",
    "Mid-terrace house": "terraced",
    "End of terrace house": "terraced",
    "Semi-detached house": "semi-detached",
    "Detached house": "detached",
}

#: DBEREL01's BER axis mapped to the schema's band letters.  The source bands
#: A-B and F-G are coarser than the schema's A1..G, so a target applies to a
#: GROUP of bands; the group is named rather than silently assigned to one.
_BER_GROUPS: dict[str, tuple[str, ...]] = {
    "A - B": ("A1", "A2", "A3", "B1", "B2", "B3"),
    "C": ("C1", "C2", "C3"),
    "D": ("D1", "D2"),
    "E": ("E1", "E2"),
    "F- G": ("F", "G"),
}


def electricity_per_dwelling_targets(year: int = 2022) -> list[CalibrationTarget]:
    """Mean annual household electricity by dwelling type and BER band (DBEREL01).

    The pattern in this table is worth stating, because it looks wrong and is
    not: A-B rated detached houses consume *more* electricity than F-G ones
    (7,979 against 4,156 kWh in 2022).  A better BER does not mean less
    electricity, it means the heating is more likely to be a heat pump - the BER
    axis confounds fabric with fuel.  So a model that heats with gas must not be
    scored against the A-B cell, and the comparison has to be made within
    heating fuel.  The target carries that in its scope note.
    """
    key = "cso.electricity.dbere101_by_dwelling_ber"
    doc, cells, sha = _read_jsonstat(key)
    stat = list(doc["dimension"]["STATISTIC"]["category"]["label"].values())[0]
    unit = "kWh per dwelling per year"
    out: list[CalibrationTarget] = []
    for src_dw, schema_dw in _DWELLING_MAP.items():
        for src_ber, bands in _BER_GROUPS.items():
            v = _cell(cells, (stat, str(year), src_dw, src_ber), key)
            out.append(
                CalibrationTarget(
                    target_id=f"D24-ELEC-{schema_dw}-{src_ber.replace(' ', '')}"
                              f"-{src_dw.split()[0].lower()}",
                    quantity="mean annual household electricity consumption",
                    unit=unit,
                    value=v,
                    conditioned_on={
                        "dwelling_type": schema_dw,
                        "source_dwelling_label": src_dw,
                        "ber_bands": ",".join(bands),
                        "source_ber_label": src_ber,
                    },
                    source_key=key, source_sha256=sha,
                    source_title=REGISTRY[key].title, year=year,
                    exposure=REGISTRY[key].model_development_exposure,
                    scope_note=(
                        "Covers ALL household electricity, so a dwelling heated "
                        "electrically belongs in this cell and a gas-heated one "
                        "does not reach it on appliances alone. The BER axis "
                        "confounds fabric with heating fuel, so compare within "
                        "fuel. BER-rated dwellings are a selected subset of the "
                        "stock (newer and recently transacted homes are "
                        "over-represented), which biases the level, not the "
                        "ordering."
                    ),
                )
            )
        v = _cell(cells, (stat, str(year), src_dw, "All BER ratings"), key)
        out.append(
            CalibrationTarget(
                target_id=f"D24-ELEC-{schema_dw}-allBER-{src_dw.split()[0].lower()}",
                quantity="mean annual household electricity consumption",
                unit=unit, value=v,
                conditioned_on={
                    "dwelling_type": schema_dw,
                    "source_dwelling_label": src_dw, "ber_bands": "all",
                    "source_ber_label": "All BER ratings",
                },
                source_key=key, source_sha256=sha,
                source_title=REGISTRY[key].title, year=year,
                exposure=REGISTRY[key].model_development_exposure,
                scope_note=(
                    "The dwelling-type marginal. Mixes heating fuels in the "
                    "proportions of the BER-rated stock, which is not Cobh's "
                    "proportions, so it bounds rather than fixes the level."
                ),
            )
        )
    return out


def electricity_by_construction_targets(year: int = 2022) -> list[CalibrationTarget]:
    """The held-out check: DBEREL02, dwelling type x period of construction.

    Exposure must read "none" for every row this returns.  If it ever reads
    "tuning", the held-out check has been spent and the generalisation claim in
    the E1 report is void - so it is asserted here rather than trusted.
    """
    key = "cso.electricity.dbere102_by_dwelling_construction"
    if REGISTRY[key].model_development_exposure != "none":
        raise TargetError(
            f"{key} is declared with exposure "
            f"{REGISTRY[key].model_development_exposure!r}, but it is the "
            f"held-out table. A held-out target that has been used for tuning "
            f"is not held out; either restore the declaration or stop calling "
            f"this a generalisation check."
        )
    doc, cells, sha = _read_jsonstat(key)
    stat = list(doc["dimension"]["STATISTIC"]["category"]["label"].values())[0]
    periods = [
        p for p in doc["dimension"][doc["id"][3]]["category"]["label"].values()
    ]
    out: list[CalibrationTarget] = []
    for src_dw, schema_dw in _DWELLING_MAP.items():
        for period in periods:
            v = _cell(cells, (stat, str(year), src_dw, period), key)
            out.append(
                CalibrationTarget(
                    target_id=f"D24-ELECHO-{schema_dw}-{period.replace(' ', '')}"
                              f"-{src_dw.split()[0].lower()}",
                    quantity="mean annual household electricity consumption",
                    unit="kWh per dwelling per year", value=v,
                    conditioned_on={
                        "dwelling_type": schema_dw,
                        "source_dwelling_label": src_dw,
                        "period_of_construction": period,
                    },
                    source_key=key, source_sha256=sha,
                    source_title=REGISTRY[key].title, year=year,
                    exposure="none",
                    scope_note=(
                        "HELD OUT. Not used to set any model parameter. D02 "
                        "carries year_built_band, so the simulated estate can be "
                        "scored on this axis without the axis having been fitted."
                    ),
                )
            )
    return out


def meter_distribution_target(year: int = 2022) -> CalibrationTarget:
    """The national distribution of residential meters by annual kWh (MEC06).

    A mean is a weak target: a model can hit 4,000 kWh on average while giving
    every home 4,000 kWh, which is exactly the failure mode R10 (heterogeneity)
    exists to prevent.  This target is the whole distribution, so it scores
    spread as well as level.
    """
    key = "cso.electricity.mec06_residential_meters"
    doc, cells, sha = _read_jsonstat(key)
    stat = "Residential Electricity Meters"
    bands = list(doc["dimension"][doc["id"][2]]["category"]["label"].values())
    counts = {
        b: _cell(cells, (stat, str(year), b), key)
        for b in bands if b != "All kWh consumptions"
    }
    total = _cell(cells, (stat, str(year), "All kWh consumptions"), key)
    if abs(sum(counts.values()) - total) > 1.0:
        raise TargetError(
            f"{key}: the bands sum to {sum(counts.values()):,.0f} but the "
            f"'All kWh consumptions' row says {total:,.0f}. The table is not "
            f"internally consistent and must not be used as a target."
        )
    return CalibrationTarget(
        target_id="D24-ELEC-METER-DISTRIBUTION",
        quantity="distribution of residential electricity meters by annual consumption band",
        unit="meter count per band",
        value={"bands": counts, "total": total},
        conditioned_on={"sector": "residential", "geography": "State"},
        source_key=key, source_sha256=sha,
        source_title=REGISTRY[key].title, year=year,
        exposure=REGISTRY[key].model_development_exposure,
        scope_note=(
            "National, not Cobh, and per METER: the 2,736 meters at or below "
            "0 kWh are vacant or newly connected premises, which the simulated "
            "estate has none of, so the lowest band is expected to be empty in "
            "simulation and that is not a failure. Scores spread, which a mean "
            "cannot."
        ),
    )


def per_meter_target(year: int = 2022, county: str = "Co. Cork") -> CalibrationTarget:
    """Mean annual kWh per residential meter in Co. Cork (MEC03 / MEC07).

    Two tables, one target: MEC03 gives the residential GWh and MEC07 the
    residential meter count, both by county.  Neither is usable alone.
    """
    k_c = "cso.electricity.mec03_by_county_sector"
    k_m = "cso.electricity.mec07_meters_by_county"
    doc_c, cells_c, sha_c = _read_jsonstat(k_c)
    doc_m, cells_m, sha_m = _read_jsonstat(k_m)
    stat_c = list(doc_c["dimension"]["STATISTIC"]["category"]["label"].values())[0]
    gwh = _cell(cells_c, (stat_c, str(year), county, "10 Residential"), k_c)
    meters = _cell(cells_m, ("Residential Electricity Meters", str(year), county), k_m)
    return CalibrationTarget(
        target_id="D24-ELEC-PER-METER-CORK",
        quantity="mean annual electricity consumption per residential meter",
        unit="kWh per meter per year",
        value=round(gwh * 1e6 / meters, 1),
        conditioned_on={
            "county": county, "sector": "residential",
            "numerator": f"{gwh:,.0f} GWh (MEC03)",
            "denominator": f"{meters:,.0f} meters (MEC07)",
        },
        source_key=f"{k_c} + {k_m}",
        source_sha256=f"{sha_c} + {sha_m}",
        source_title=f"{REGISTRY[k_c].title}; {REGISTRY[k_m].title}",
        year=year, exposure="none",
        scope_note=(
            "Geographically matched to Cobh's county and keyed to the METER, "
            "which is design 6.4's observable unit. Co. Cork includes rural "
            "areas with larger, oil-heated dwellings, so the county mean sits "
            "above a town-only mean; MEC05's urban-to-rural ratio bounds how "
            "far above. Includes vacant metered premises in the denominator, "
            "which pulls the mean down."
        ),
    )


def build_d24(year: int = 2022) -> dict[str, Any]:
    """The whole D24 calibration_targets dataset."""
    from baile_nua import CLAIM, LABEL

    tuned = electricity_per_dwelling_targets(year)
    held_out = electricity_by_construction_targets(year)
    gas_tuned = gas_per_dwelling_targets(year)
    gas_held_out = gas_by_construction_targets(year)
    rows = [t.as_row() for t in tuned + held_out + gas_tuned + gas_held_out]
    rows.append(meter_distribution_target(year).as_row())
    rows.append(per_meter_target(year).as_row())
    rows.append(floor_area_target().as_row())
    exposures = sorted({r["exposure"] for r in rows})
    return {
        "dataset": "D24",
        "name": "calibration_targets",
        "label": LABEL,
        "claim": CLAIM,
        "year": year,
        "n_targets": len(rows),
        "exposures_present": exposures,
        "rule": (
            "No literal statistic appears in this module. Every value was read "
            "from a registered file in sources/ at the recorded SHA-256."
        ),
        "targets": rows,
    }


def write_d24(path: str | Any, year: int = 2022) -> dict[str, Any]:
    """Write D24 to ``path`` as JSON and return it."""
    from pathlib import Path

    d = build_d24(year)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return d


def gas_per_dwelling_targets(year: int = 2022) -> list[CalibrationTarget]:
    """Mean annual gas consumption by dwelling type and BER band (DBERNG01).

    The target the estate actually needs. Forty-nine of its fifty homes heat
    with gas, so their space heat never reaches the electricity meter and
    DBEREL01 cannot see it at all; in a gas-heated dwelling the gas meter *is*
    space heating plus hot water, which makes this the direct check on the F1
    physics and the heating schedule - the largest energy term in the model.

    Unlike the electricity table, the BER axis here does NOT confound fuel:
    every dwelling in it burns gas, so a better rating should mean less gas,
    monotonically. That is a check in itself and the scope note says so.
    """
    key = "cso.gas.dberng01_by_dwelling_ber"
    doc, cells, sha = _read_jsonstat(key)
    stat = list(doc["dimension"]["STATISTIC"]["category"]["label"].values())[0]
    out: list[CalibrationTarget] = []
    for src_dw, schema_dw in _DWELLING_MAP.items():
        for src_ber, bands in list(_BER_GROUPS.items()) + [
            ("All BER ratings", ("all",))
        ]:
            try:
                v = _cell(cells, (stat, str(year), src_dw, src_ber), key)
            except TargetError:
                continue        # a suppressed cell is absent, not zero
            out.append(
                CalibrationTarget(
                    target_id=f"D24-GAS-{schema_dw}-{src_ber.replace(' ', '')}"
                              f"-{src_dw.split()[0].lower()}",
                    quantity="mean annual household gas consumption",
                    unit="kWh per dwelling per year",
                    value=v,
                    conditioned_on={
                        "dwelling_type": schema_dw,
                        "source_dwelling_label": src_dw,
                        "ber_bands": ",".join(bands),
                        "source_ber_label": src_ber,
                        "heating_fuel": "natural gas (by construction: gas meters only)",
                    },
                    source_key=key, source_sha256=sha,
                    source_title=REGISTRY[key].title, year=year,
                    exposure=REGISTRY[key].model_development_exposure,
                    scope_note=(
                        "Gas-metered dwellings only, so every dwelling in the "
                        "cell burns gas and the BER axis does not confound fuel "
                        "the way DBEREL01's does: a better rating should mean "
                        "less gas, monotonically. Covers space heating AND hot "
                        "water, so a simulated space-heat figure alone belongs "
                        "below the cell, not at it. Cooking gas is included "
                        "where the dwelling has a gas hob."
                    ),
                )
            )
    return out


def gas_by_construction_targets(year: int = 2022) -> list[CalibrationTarget]:
    """The held-out heating check: DBERNG02, dwelling type x construction period."""
    key = "cso.gas.dberng02_by_dwelling_construction"
    if REGISTRY[key].model_development_exposure != "none":
        raise TargetError(
            f"{key} is declared with exposure "
            f"{REGISTRY[key].model_development_exposure!r}, but it is the "
            f"held-out gas table. Either restore the declaration or stop "
            f"calling the heating comparison a generalisation check."
        )
    doc, cells, sha = _read_jsonstat(key)
    stat = list(doc["dimension"]["STATISTIC"]["category"]["label"].values())[0]
    periods = list(doc["dimension"][doc["id"][3]]["category"]["label"].values())
    out: list[CalibrationTarget] = []
    for src_dw, schema_dw in _DWELLING_MAP.items():
        for period in periods:
            try:
                v = _cell(cells, (stat, str(year), src_dw, period), key)
            except TargetError:
                continue
            out.append(
                CalibrationTarget(
                    target_id=f"D24-GASHO-{schema_dw}-{period.replace(' ', '')}"
                              f"-{src_dw.split()[0].lower()}",
                    quantity="mean annual household gas consumption",
                    unit="kWh per dwelling per year", value=v,
                    conditioned_on={
                        "dwelling_type": schema_dw,
                        "source_dwelling_label": src_dw,
                        "period_of_construction": period,
                        "heating_fuel": "natural gas",
                    },
                    source_key=key, source_sha256=sha,
                    source_title=REGISTRY[key].title, year=year,
                    exposure="none",
                    scope_note=(
                        "HELD OUT, mirroring DBEREL02. Not used to set any "
                        "model parameter. D02 carries year_built_band, so the "
                        "estate can be scored on this axis without the axis "
                        "having been fitted."
                    ),
                )
            )
    return out


def floor_area_target(year: int = 2021, county: str = "Cork County Council") -> CalibrationTarget:
    """Median floor area of Co. Cork rental properties (TRS05).

    The only public Irish floor-area figure in PxStat, and it bounds from
    BELOW: rentals skew smaller and apartment-heavier than the whole stock, so
    the town median should sit above this, not at it. Stated that way because a
    bound used as a point estimate is how a correct model gets "corrected".
    """
    key = "cso.housing.trs05_floor_area_by_authority"
    doc, cells, sha = _read_jsonstat(key)
    stat = "Median Total Floor Area of RTB properties"
    v = _cell(cells, (stat, str(year), county), key)
    return CalibrationTarget(
        target_id="D24-FLOOR-AREA-CORK-RENTAL-MEDIAN",
        quantity="median total floor area of rental properties",
        unit="m2 per dwelling",
        value=v,
        conditioned_on={
            "local_authority": county, "tenure": "rented (RTB-registered)",
            "matched_to": "BER records",
        },
        source_key=key, source_sha256=sha,
        source_title=REGISTRY[key].title, year=year,
        exposure=REGISTRY[key].model_development_exposure,
        scope_note=(
            "A LOWER BOUND on the whole-stock median, not a point estimate: "
            "rentals are smaller and more apartment-heavy than owner-occupied "
            "housing. Cork County Council is the authority covering Cobh. "
            "Latest year available is 2021, not 2022."
        ),
    )
