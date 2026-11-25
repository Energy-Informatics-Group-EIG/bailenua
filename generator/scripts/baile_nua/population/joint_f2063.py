"""PL-ROOMS-01: the rooms x dwelling-type joint, against Census 2022 (F2063).

Why this check exists
---------------------
I-031 was the worst flaw this project has found: a 285.7 m2 three-bedroom
apartment burning 13.6 MWh a year of space heat. Two causes combined, and the
second was that room counts were drawn **independently** of dwelling type, so
an apartment had a detached house's room distribution.

The fix (``assign_rooms`` in :mod:`baile_nua.population.buildings`) ranks
dwellings by size and bedrooms and permutes the SAPS room labels along that
ranking, which preserves the published marginal exactly and makes the
association monotone in expectation. But the STRENGTH of the association,
``ROOM_ALLOCATION_STRENGTH``, is a declared constant: it was set so the
association would be "strong without making room count a function of type",
which is a judgement, not a measurement.

The U30 sweep found the measurement. Census 2022 F2063 publishes rooms x
bedrooms x year built x dwelling type by county, which is the joint whose
absence made the independent draw look unavoidable. SAPS publishes the
marginals separately - that part of the old note was right - but the
county-level census table publishes the joint.

Declared validation, not calibration
------------------------------------
``ROOM_ALLOCATION_STRENGTH`` was set before this table was found, so the table
can judge it. Nothing here may be used to tune it: if this check fails, that
is a finding for ISSUES.md, and any later change to the constant against this
reference changes the source's declaration from ``validation`` to
``calibration`` with it. Same rule as HAS02 under I-040.

The band, declared before measuring
-----------------------------------
1. **Ordering.** An apartment's mean room count is below every house type's.
   Hard, and exactly what I-031 violated.
2. **Level**, within :data:`LEVEL_TOLERANCE_ROOMS` of the county conditional
   mean. One room, because rooms are integer-valued and one room is the
   variable's own granularity; Cobh is a harbour town with an older, more
   terraced core than Cork County as a whole, so levels legitimately differ,
   and the tolerance says by less than one room.
3. **Gradient**, at least :data:`MIN_GRADIENT_SHARE` of the county's
   detached-minus-apartment gap. This is the term that scores the assumed
   constant: the gap is what ``ROOM_ALLOCATION_STRENGTH`` controls, and a gap
   near zero is the I-031 regime. Half, rather than all, because Cobh's
   narrower stock mix compresses the spread.

Comparing like with like
------------------------
SAPS tops out at "8 or more rooms" and the model's own ``numeric()`` reads
that as 8. F2063 goes to "10 or more". Collapsing the census distribution onto
the SAPS categories before taking a mean is therefore not a convenience: a
county mean that counts nine- and ten-room dwellings at their true size would
be compared against a model that cannot express them, and the model would look
systematically small for a reason that is an artefact of the marginal it was
given.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from baile_nua.sources import REGISTRY, require

__all__ = [
    "F2063_KEY",
    "COUNTY",
    "LEVEL_TOLERANCE_ROOMS",
    "MIN_GRADIENT_SHARE",
    "SAPS_ROOM_CAP",
    "TYPE_MAP",
    "county_rooms_by_dwelling_type",
    "rooms_by_dwelling_type_acceptance",
    "write_joint_report",
]

F2063_KEY = "cso.census2022.f2063_rooms_bedrooms_year_type"

#: Cobh is in the Cork County Council area (Cork City Council is the city).
COUNTY = "Cork County Council"

LEVEL_TOLERANCE_ROOMS = 1.0
MIN_GRADIENT_SHARE = 0.5

#: SAPS's open top category. The model cannot represent more, so neither may
#: the reference it is judged against.
SAPS_ROOM_CAP = 8

#: Model dwelling_type -> the F2063 categories that make it up. Both apartment
#: categories are summed: the model has one `apartment` type and the census
#: separates purpose-built blocks from conversions.
TYPE_MAP: dict[str, tuple[str, ...]] = {
    "detached": ("Detached house",),
    "semi-detached": ("Semi- detached house",),
    "terraced": ("Terraced house",),
    "apartment": (
        "Flat or apartment in a purpose- built block",
        "Flat or apartment in a converted house or commercial building",
    ),
    "bedsit": ("Bed-sit",),
}

_EXCLUDED_ROOM_LABELS = ("All households", "Not stated")


def _rooms_to_saps_category(label: str) -> int | None:
    """"6 rooms" -> 6; "10 or more rooms" -> 8, the SAPS cap."""
    head = str(label).split()[0]
    if head.isdigit():
        return min(int(head), SAPS_ROOM_CAP)
    return None


def _read_cells() -> tuple[dict[str, list[str]], dict[tuple, Any], str]:
    path = require(F2063_KEY)
    doc = json.loads(path.read_text(encoding="utf-8"))
    ids = doc["id"]
    labels = {
        i: list(doc["dimension"][i]["category"]["label"].values()) for i in ids
    }
    values = doc["value"]
    cells = {
        combo: (values[k] if isinstance(values, list) else values.get(str(k)))
        for k, combo in enumerate(
            itertools.product(*[labels[i] for i in ids])
        )
    }
    sha = json.loads(
        REGISTRY[F2063_KEY].manifest_path.read_text(encoding="utf-8")
    )["sha256"]
    # Position of each dimension, so the lookup does not depend on order.
    order = {
        "rooms": ids.index("C02729V03297"),
        "bedrooms": ids.index("C04081V04842"),
        "year": ids.index("C01936V02368"),
        "type": ids.index("C02010V02440"),
        "county": ids.index("C03789V04537"),
    }
    by_key: dict[tuple, Any] = {}
    for combo, v in cells.items():
        by_key[(
            combo[order["rooms"]], combo[order["bedrooms"]],
            combo[order["year"]], combo[order["type"]],
            combo[order["county"]],
        )] = v
    return labels, by_key, str(sha)


def county_rooms_by_dwelling_type(
    county: str = COUNTY,
) -> dict[str, dict[str, Any]]:
    """P(rooms | dwelling type) for one county, on the SAPS room categories."""
    labels, cells, sha = _read_cells()
    room_labels = [
        r for r in labels["C02729V03297"] if r not in _EXCLUDED_ROOM_LABELS
    ]
    out: dict[str, dict[str, Any]] = {}
    for model_type, census_types in TYPE_MAP.items():
        counts: dict[int, float] = {}
        for room_label in room_labels:
            cat = _rooms_to_saps_category(room_label)
            if cat is None:
                continue
            total = 0.0
            for ct in census_types:
                v = cells.get(
                    (room_label, "All Households", "All years", ct, county)
                )
                if v is not None:
                    total += float(v)
            counts[cat] = counts.get(cat, 0.0) + total
        n = sum(counts.values())
        if n <= 0:
            continue
        out[model_type] = {
            "n_dwellings": int(round(n)),
            "share_by_rooms": {
                str(k): round(v / n, 6) for k, v in sorted(counts.items())
            },
            "mean_rooms": round(
                sum(k * v for k, v in counts.items()) / n, 4
            ),
        }
    if not out:
        raise LookupError(f"F2063 has no rows for county {county!r}")
    out["_reference"] = {
        "source_key": F2063_KEY,
        "sha256": sha,
        "county": county,
        "census_year": "2022",
        "slice": (
            "all bedrooms, all years built; rooms collapsed onto the SAPS "
            f"categories with {SAPS_ROOM_CAP}+ as the open top class"
        ),
    }
    return out


def rooms_by_dwelling_type_acceptance(
    dwelling_types: Sequence[str],
    rooms: Sequence[int],
    *,
    county: str = COUNTY,
) -> dict[str, Any]:
    """Score the modelled joint against the census one.

    Takes the two columns rather than a frame so it can be called on a town,
    on a slice, or on a D02 export without any of them having to agree on a
    container.
    """
    if len(dwelling_types) != len(rooms):
        raise ValueError("dwelling_types and rooms must be the same length")
    ref = county_rooms_by_dwelling_type(county)

    model: dict[str, dict[str, Any]] = {}
    for dtype, r in zip(dwelling_types, rooms):
        bucket = model.setdefault(str(dtype), {"n": 0, "sum": 0})
        bucket["n"] += 1
        bucket["sum"] += min(int(r), SAPS_ROOM_CAP)
    for dtype, b in model.items():
        b["mean_rooms"] = round(b["sum"] / b["n"], 4) if b["n"] else None

    rows: list[dict[str, Any]] = []
    for dtype in sorted(model):
        r = ref.get(dtype)
        m = model[dtype]
        delta = (
            round(m["mean_rooms"] - r["mean_rooms"], 4) if r else None
        )
        rows.append({
            "dwelling_type": dtype,
            "n_modelled": m["n"],
            "model_mean_rooms": m["mean_rooms"],
            "census_mean_rooms": (r["mean_rooms"] if r else None),
            "delta_rooms": delta,
            "within_level_tolerance": (
                None if delta is None else abs(delta) <= LEVEL_TOLERANCE_ROOMS
            ),
        })

    # 1. Ordering.
    apt = model.get("apartment", {}).get("mean_rooms")
    houses = {
        k: v["mean_rooms"] for k, v in model.items()
        if k in ("detached", "semi-detached", "terraced")
    }
    ordering_ok = (
        None if (apt is None or not houses)
        else all(apt < h for h in houses.values())
    )

    # 2. Levels.
    level_flags = [r["within_level_tolerance"] for r in rows
                   if r["within_level_tolerance"] is not None]
    levels_ok = all(level_flags) if level_flags else None

    # 3. Gradient: the term that scores ROOM_ALLOCATION_STRENGTH.
    gradient: dict[str, Any] = {"evaluable": False}
    det = model.get("detached", {}).get("mean_rooms")
    ref_det = ref.get("detached", {}).get("mean_rooms")
    ref_apt = ref.get("apartment", {}).get("mean_rooms")
    if None not in (apt, det, ref_det, ref_apt):
        model_gap = round(det - apt, 4)
        census_gap = round(ref_det - ref_apt, 4)
        share = round(model_gap / census_gap, 4) if census_gap else None
        gradient = {
            "evaluable": True,
            "model_detached_minus_apartment_rooms": model_gap,
            "census_detached_minus_apartment_rooms": census_gap,
            "share_of_census_gradient": share,
            "min_required_share": MIN_GRADIENT_SHARE,
            "passed": bool(share is not None and share >= MIN_GRADIENT_SHARE),
            "what_it_scores": (
                "ROOM_ALLOCATION_STRENGTH, the declared constant controlling "
                "how strongly room count tracks dwelling type. A share near "
                "zero is the I-031 regime (independent draw); a share above "
                "one would mean room count has become nearly a function of "
                "type, which real stock is not."
            ),
        }

    checks = [ordering_ok, levels_ok]
    if gradient["evaluable"]:
        checks.append(gradient["passed"])
    passed = all(c for c in checks if c is not None)

    return {
        "label": "UNVALIDATED SIMULATION EVIDENCE",
        "check_id": "PL-ROOMS-01",
        "quantity": "mean habitable rooms by dwelling type",
        "reference": ref["_reference"],
        "tolerance": {
            "ordering": "apartment mean rooms below every house type",
            "level_rooms": LEVEL_TOLERANCE_ROOMS,
            "min_gradient_share": MIN_GRADIENT_SHARE,
            "declared_before_measuring": True,
            "basis": (
                "Rooms are integer-valued, so one room is the variable's own "
                "granularity, and Cobh's older more terraced core differs "
                "from the county as a whole: levels may differ, by less than "
                "one room. The gradient term is the one that scores the "
                "assumed constant."
            ),
        },
        "intended_use": "validation",
        "may_not_be_used_to_tune": (
            "ROOM_ALLOCATION_STRENGTH and DWELLING_SIZE_RANK were set before "
            "F2063 was found (U30). Tuning them against it would turn this "
            "source from validation into calibration, and its declaration "
            "would have to change with it (I-040)."
        ),
        "ordering_ok": ordering_ok,
        "levels_ok": levels_ok,
        "gradient": gradient,
        "passed": bool(passed),
        "per_dwelling_type": rows,
    }


def write_joint_report(
    dwelling_types: Sequence[str],
    rooms: Sequence[int],
    path: Path | None = None,
    *,
    county: str = COUNTY,
) -> Path:
    rec = rooms_by_dwelling_type_acceptance(dwelling_types, rooms, county=county)
    out = path or (
        Path(__file__).resolve().parents[3] / "v1" / "evidence"
        / "joint_rooms_f2063.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    return out
