"""D24 ``calibration_targets``, from the generator that already builds them.

D24 was in :mod:`baile_nua.export.absent` for two reasons and they are not
equally true any more.

*The packaging reason is gone.*  The old entry ends "D24 is META, so its
release package is ``v1/evidence/`` - outside the paths this export was
permitted to write".  The per-year replay export creates
``<year>/pkg/evidence/`` before it calls ``export_all`` (it has to: D22 and D23
are META too and land there), so a META dataset can be placed.  That half of
the objection was about one caller's permissions, not about the data.

*The schema reason stands exactly as recorded, and is written into the data.*
Five required fields have no source: ``domain``, ``tolerance``,
``tolerance_kind``, ``evidence_tag`` and ``provisional``.  They are left null,
named in :data:`NULL_REQUIRED` with the reason, and recorded in the part's
manifest, so the part cannot be read as a complete D24.  Filling ``domain``
with one of its six declared values would misclassify 113 household
energy-consumption targets; deriving a float ``tolerance`` from the prose bands
in ``plausibility/checks.py`` would invent a number the checks never state.

Eleven of the seventeen columns ARE filled, from the artefact and the source
register, exactly as the old entry's own ``field_mapping`` said they could be.
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from baile_nua.export.context import ExportError, RunContext
from baile_nua.export.writer import emit

__all__ = [
    "NULL_REQUIRED",
    "RENAMED",
    "COMPOSITE_KEY_SEPARATOR",
    "FALLBACK_TARGET_YEAR",
    "targets_for_year",
    "build_d24_rows",
    "export_d24",
]

#: The year the targets are built for when the run's own year is not in the
#: published sources.  ``calibration.targets.build_d24``'s own default, and the
#: year of the committed ``v1/evidence/d24_calibration_targets.json``.
#:
#: The replay spans 2014-2026 and the CSO tables behind D24 cover 2016-2023, so
#: the first segment and the last three ask for a year that does not exist in
#: the sources: ``build_d24(2015)`` raises TargetError on the first missing cell
#: and ``build_d24(2026)`` on another, by design - "fix the reader rather than
#: guessing".  Neither is something an exporter may fix, so the fallback is
#: taken, RECORDED on the part, and every row carries the year it was actually
#: built for inside ``value_json``.  A D24 row is a published reference
#: statistic, not an output of the simulated year, so a year's package carrying
#: the nearest available targets is a weaker claim than carrying none - but only
#: while the substitution is stated, which is what ``targets_year_note`` is for.
FALLBACK_TARGET_YEAR = 2022

#: ``artefact key -> D24 column``.  Two renames, both recorded as conversions.
RENAMED: dict[str, str] = {
    "quantity": "statistic",
    "exposure": "model_development_exposure",
}

#: One target's ``source_key`` names TWO registered sources joined like this
#: (the per-meter target divides one series by another).  The register fields
#: are resolved per part and rejoined with the same separator rather than one
#: of the two being picked, which would misattribute half the arithmetic.
COMPOSITE_KEY_SEPARATOR = " + "

#: REQUIRED columns left null, with the reason.  Verbatim in substance from the
#: entry D24 carried in :mod:`baile_nua.export.absent`: the finding is
#: unchanged, it is now carried by the data instead of standing in place of it.
NULL_REQUIRED: dict[str, str] = {
    "domain": (
        "NO SOURCE. Declared as 'population | activity | appliance | physics | "
        "weather | mimic'. The targets on disk are household electricity, "
        "household gas and median rental floor area, and none of those is any "
        "of the six. Any value would be a misclassification, so the finding is "
        "a SCHEMA question for Appendix D: what `domain` means for an "
        "energy-consumption target."
    ),
    "tolerance": (
        "NO SOURCE as a float. The tolerances that exist are PROSE and are "
        "stated per plausibility CHECK rather than per target - "
        "'ratio in [0.40, 1.00]', 'between 15 and 125 litres per person per "
        "day', in plausibility/checks.py - so there is no number to put in a "
        "declared float column, and no mapping from a check's band to a "
        "target's tolerance."
    ),
    "tolerance_kind": (
        "NO SOURCE. Declared 'absolute | relative | sampling-error-band'. The "
        "generator emits nothing of the kind and neither does the artefact on "
        "disk; it would have to be inferred from a tolerance that does not "
        "exist."
    ),
    "evidence_tag": (
        "NO SOURCE. Declared '[C] | [P] | [A] | [U]'. The string appears "
        "nowhere in the build: not on CalibrationTarget, not in the artefact, "
        "not in the source register."
    ),
    "provisional": (
        "NO SOURCE. 'E0-4 / U11: section 7 margins are provisional' is a "
        "statement about the margins in the design document, and nothing in "
        "the build records which target it applies to. A blanket True or False "
        "would be a claim about all 113."
    ),
}


def _register_fields(source_key: str) -> dict[str, str | None]:
    """The source register's own fields for one target's ``source_key``."""
    import baile_nua.sources_registry  # noqa: F401  (declares the sources)
    from baile_nua import sources

    parts = [p.strip() for p in str(source_key).split(COMPOSITE_KEY_SEPARATOR)]
    missing = [p for p in parts if p not in sources.REGISTRY]
    if missing:
        raise ExportError(
            f"D24 target names source key(s) {missing}, which are not in "
            f"sources.REGISTRY. Every D24 row must trace to a declared source; "
            f"writing the row without its register fields would make the "
            f"dataset's own rule - 'no calibration number is hard-coded from "
            f"memory' - unverifiable for that row."
        )
    srcs = [sources.REGISTRY[p] for p in parts]
    manifests = [sources.manifest_for(s) for s in srcs]
    retrieved = [str((m or {}).get("retrieved_at") or "") for m in manifests]
    return {
        "source_file": COMPOSITE_KEY_SEPARATOR.join(s.relpath for s in srcs),
        "source_url": COMPOSITE_KEY_SEPARATOR.join(s.url for s in srcs),
        "source_licence": COMPOSITE_KEY_SEPARATOR.join(s.licence for s in srcs),
        "intended_use": COMPOSITE_KEY_SEPARATOR.join(
            str(s.intended_use) for s in srcs),
        # The EARLIEST retrieval of the parts: a composite target is only as
        # current as its oldest input, and taking the latest would overstate
        # how fresh the row is.
        "retrieved_at": (min(r for r in retrieved if r) if any(retrieved)
                         else None),
    }


def targets_for_year(year: int) -> tuple[dict[str, Any], dict[str, Any]]:
    """``build_d24`` for ``year``, falling back and SAYING SO when it cannot.

    The targets are a function of the sources and of the target year, not of
    the run: ``build_d24(year)`` reads registered files at their recorded
    SHA-256.  The run's own year is asked for first, so a year inside the
    sources' coverage gets its own targets.  Outside it, ``build_d24`` raises
    ``TargetError`` naming the missing cell, and this takes
    :data:`FALLBACK_TARGET_YEAR` and returns the substitution as a record
    rather than swallowing it.  The caller puts that record in the part's
    manifest and in its limitations.
    """
    # Before `build_d24` reads a source: it resolves every target through
    # `sources.REGISTRY`, which importing `sources_registry` populates. Omit it
    # and a D24-only export raises SourceError from the first target, which
    # reads as "the source is not declared" when the source IS declared and
    # the declaring module simply had not been imported yet. It only shows
    # when D24 runs FIRST - a full export_all starts at D01, which imports the
    # registry on the way - so the catch-up pass, which runs D24 alone, is
    # exactly the caller that hits it. The same trap `RunContext.slice`
    # documents.
    import baile_nua.sources_registry  # noqa: F401  (declares the sources)
    from baile_nua.calibration.targets import TargetError, build_d24

    try:
        return build_d24(int(year)), {
            "requested_year": int(year),
            "built_for_year": int(year),
            "substituted": False,
            "note": "the run's own year is in the sources' coverage",
        }
    except TargetError as exc:
        artefact = build_d24(FALLBACK_TARGET_YEAR)
        return artefact, {
            "requested_year": int(year),
            "built_for_year": int(FALLBACK_TARGET_YEAR),
            "substituted": True,
            "note": (
                f"the published sources behind D24 carry no {int(year)} cell, "
                f"so the targets were built for {FALLBACK_TARGET_YEAR} "
                f"instead. A D24 row is a published reference statistic rather "
                f"than an output of the simulated year, and every row records "
                f"the year it was built for inside value_json; the comparison "
                f"a {int(year)} package can make against these targets is "
                f"therefore against {FALLBACK_TARGET_YEAR} statistics, which "
                f"is what a reader must know before using them."
            ),
            "build_d24_refused_because": f"{type(exc).__name__}: {exc}",
        }


def build_d24_rows(ctx: RunContext) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Every D24 row, from ``calibration.targets.build_d24``."""
    artefact, year_note = targets_for_year(ctx.year)
    targets = list(artefact["targets"])
    if not targets:
        raise ExportError(
            f"calibration.targets.build_d24 produced no targets "
            f"({year_note['built_for_year']})."
        )

    rows: list[dict[str, Any]] = []
    for t in targets:
        reg = _register_fields(t["source_key"])
        value = t.get("value")
        scalar = isinstance(value, (int, float)) and not isinstance(value, bool)
        # Everything the artefact carries that the schema declares no column
        # for travels in value_json rather than being dropped. The schema's own
        # note for the field is "for vector or table targets", and the
        # table-valued target is exactly the one whose `value` is a dict.
        payload = {
            "conditioned_on": t.get("conditioned_on") or {},
            "not_declared_by_the_schema": {
                "source_key": t.get("source_key"),
                "source_title": t.get("source_title"),
                "year": t.get("year"),
                "scope_note": t.get("scope_note"),
            },
        }
        if not scalar and value is not None:
            payload["value"] = value
        rows.append({
            "target_id": str(t["target_id"]),
            "statistic": str(t["quantity"]),
            "domain": None,
            "value": (float(value) if scalar else None),
            "value_json": json.dumps(payload, sort_keys=True),
            "unit": str(t["unit"]),
            "tolerance": None,
            "tolerance_kind": None,
            "source_file": reg["source_file"],
            "source_sha256": str(t["source_sha256"]),
            "source_url": reg["source_url"],
            "source_licence": reg["source_licence"],
            "retrieved_at": reg["retrieved_at"],
            "intended_use": reg["intended_use"],
            "model_development_exposure": str(t["exposure"]),
            "evidence_tag": None,
            "provisional": None,
        })

    provenance = {
        "target_id, unit, source_sha256": "the artefact's own, unchanged",
        "statistic": "the artefact's `quantity`, RENAMED",
        "model_development_exposure": "the artefact's `exposure`, RENAMED",
        "value": (
            "the artefact's `value` where it is a scalar; null for the one "
            "table-valued target, whose table travels in value_json"
        ),
        "value_json": (
            "a JSON object carrying `conditioned_on`, the artefact keys the "
            "schema declares no column for (source_key, source_title, year, "
            "scope_note), and `value` when it is a table. Serialised as a JSON "
            "string so a column of objects with different key sets stays one "
            "column"
        ),
        "source_file, source_url, source_licence, intended_use": (
            "sources.REGISTRY[source_key], per the register; joined with "
            f"{COMPOSITE_KEY_SEPARATOR!r} for the one target built from two "
            "sources"
        ),
        "retrieved_at": (
            "the source's own per-file manifest (sources.manifest_for); the "
            "EARLIEST of the two for the composite target"
        ),
        "targets_year": year_note,
        **{k: v for k, v in NULL_REQUIRED.items()},
    }
    return rows, provenance


def export_d24(ctx: RunContext) -> dict[str, Any]:
    """D24 with eleven columns filled and five declared null."""
    rows, provenance = build_d24_rows(ctx)
    frame = pd.DataFrame(rows).sort_values("target_id").reset_index(drop=True)
    return emit(
        frame, "D24", ctx,
        source=(
            f"calibration.targets.build_d24(year="
            f"{provenance['targets_year']['built_for_year']})"),
        conversions=[
            {"field": "statistic", "from": "the artefact's `quantity`",
             "rule": "renamed, value unchanged"},
            {"field": "model_development_exposure",
             "from": "the artefact's `exposure`",
             "rule": "renamed, value unchanged"},
            {"field": "value_json", "from": "conditioned_on and the undeclared "
             "artefact keys", "rule": "serialised as a JSON string"},
            {"field": "source_file, source_url, source_licence, intended_use, "
                      "retrieved_at",
             "from": "sources.REGISTRY and the per-file manifests",
             "rule": "looked up by source_key; composite keys joined with "
                     f"{COMPOSITE_KEY_SEPARATOR!r}, retrieved_at taking the "
                     "earliest part"},
        ],
        limitations=[
            "five of seventeen required columns are null by declaration - "
            "domain, tolerance, tolerance_kind, evidence_tag, provisional - "
            "each with its reason in null_required_fields in this part's "
            "manifest. This is the SCHEMA finding D24 carried in "
            "export.absent, now carried by the data",
            provenance["targets_year"]["note"],
            "the artefact's `scope_note` - what a comparison against a target "
            "can and cannot establish - has no declared column and travels "
            "inside value_json, where a reader has to know to look for it",
        ],
        extra={"d24_truth_provenance": provenance,
               "d24_targets_year": provenance["targets_year"],
               "d24_n_targets": int(len(frame))},
        null_required=dict(NULL_REQUIRED),
    )
