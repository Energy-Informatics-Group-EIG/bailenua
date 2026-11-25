"""D03, D09 and D20 out of the evidence JSON, as the schema declares them.

Appendix D.2 and D.2b record the mismatch these functions close: the ten-year
artefact ``v1/evidence/wp5_tenyear.json`` carries ``effective_day``,
``decided_day``, ``true_onset_day`` and ``true_end_day`` - day INDICES - where
the schema declares ``effective_at``, ``decided_at``, ``true_onset`` and
``true_end`` as timestamps.

**The origin is read, not assumed.**  Day zero is :attr:`RunContext.t0`, which
:mod:`baile_nua.export.context` reads from the earliest timestamp in the run's
own Parquet parts.  The artefact's own calendar is then checked against it -
its ``years`` list carries ``year_index`` 0 against a calendar year - and a
disagreement raises instead of silently shifting every event by a year.

**Whose rows these are.**  The ten-year life course is a DIFFERENT run from the
estate year the artefact sits beside: a 60-home ``u23_mixed_age`` slice under
its own master seed.  That is recorded in every part's manifest, because a
reader joining these building ids to D02's would otherwise find nothing and
have no way to know why.
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from baile_nua.export.context import ArtefactAbsent, ExportError, RunContext
from baile_nua.export.writer import emit

__all__ = [
    "TENYEAR_ARTEFACT",
    "artefact_path",
    "artefact_present",
    "D09_EVENT_TYPE_MAP",
    "export_d03", "export_d09", "export_d20",
]

#: Relative to the run root's sibling evidence directory.
TENYEAR_ARTEFACT = "evidence/wp5_tenyear.json"

#: The WP5 life course's event vocabulary against ``datasets.yaml``'s
#: ``life_event_type`` enum.
#:
#: This mapping is the EXPORT's, not the model's, and it is lossy in two
#: places: four WP5 values collapse onto two enum members, so a reader of D09
#: cannot tell a fabric retrofit from a heat-pump retrofit, or PV from a
#: battery from smart controls.  The original value is therefore appended to
#: ``cause``, which is the row's own provenance field, so nothing is destroyed.
#:
#: ``household_dissolved`` has no member at all.  It is a HOUSEHOLD-level
#: consequence - its ``persons`` list is empty and its cause says "the
#: household's last member died, separated out or left" - and the nearest
#: declared member is the composition change it produces.  Recorded as a
#: schema gap in the export record, not as a clean fit.
D09_EVENT_TYPE_MAP: dict[str, str] = {
    "birth": "birth",
    "death": "death",
    "move in": "move in",
    "move_in": "move in",
    "move_out": "move out",
    "child_leaves_home": "move out",
    "household_dissolved": "move out",
    "partnering": "partnering",
    "separation": "separation",
    "employment_change": "job change",
    "retirement": "retirement",
    "health_state_onset": "health change",
    "retrofit_fabric": "retrofit decision",
    "retrofit_heat_pump": "retrofit decision",
    "der_pv": "DER decision",
    "der_battery": "DER decision",
    "der_smart_controls": "DER decision",
    "extension": "extension",
}

#: Which mappings lose information, and what a reader of D09 can no longer see.
D09_LOSSY: dict[str, str] = {
    "retrofit decision": "retrofit_fabric and retrofit_heat_pump are indistinguishable",
    "DER decision": "der_pv, der_battery and der_smart_controls are indistinguishable",
    "move out": (
        "move_out, child_leaves_home and household_dissolved are "
        "indistinguishable; household_dissolved has NO declared member and is "
        "mapped to the composition change it produces"
    ),
}


# --------------------------------------------------------------------------- #
# the artefact and its calendar
# --------------------------------------------------------------------------- #

def artefact_path(run_root: Any) -> Any:
    """Where a run's ten-year life-course artefact would be."""
    from pathlib import Path

    return Path(run_root) / TENYEAR_ARTEFACT


def artefact_present(run_root: Any) -> bool:
    """Does this run carry one?  A run with no life course has no D03/D09/D20."""
    return artefact_path(run_root).is_file()


def _load(ctx: RunContext) -> dict[str, Any]:
    path = artefact_path(ctx.run_root)
    if not path.exists():
        raise ArtefactAbsent(
            f"{path} does not exist, so D03, D09 and D20 have no rows to "
            f"convert from this run. The three are partial precisely because "
            f"the only copy of them on disk is inside that artefact, and a run "
            f"that did not step a life course never produced any: there is no "
            f"passport event, no life event and no change label to convert. "
            f"An ABSENCE, not a failure."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _epoch(ctx: RunContext, doc: dict[str, Any]) -> dict[str, Any]:
    """Check the artefact's own calendar against the run's start date.

    Returns the evidence stanza.  Raises if the two disagree: every event in
    three datasets is positioned from this one timestamp, so a silent
    year-sized error here would be invisible and total.
    """
    years = doc.get("years") or []
    if not years:
        raise ExportError(
            "the ten-year artefact carries no `years` list, so its day indices "
            "have no stated calendar origin to check the run's t0 against"
        )
    first = min(years, key=lambda y: int(y["year_index"]))
    if int(first["year_index"]) != 0:
        raise ExportError(
            f"the artefact's earliest year_index is {first['year_index']}, not "
            f"0, so day 0 is not the start of {first['year']}"
        )
    artefact_epoch = pd.Timestamp(f"{int(first['year'])}-01-01", tz="UTC")
    if artefact_epoch != ctx.t0:
        raise ExportError(
            f"the artefact's day 0 is {artefact_epoch.isoformat()} (its "
            f"years list starts at year_index 0, year {first['year']}) but the "
            f"run's own earliest written timestamp is {ctx.t0.isoformat()}. "
            f"Converting day indices against the wrong origin would move every "
            f"event in D03, D09 and D20 by a whole year, and nothing "
            f"downstream would notice."
        )
    span = str(doc.get("span") or "")
    last = max(years, key=lambda y: int(y["year_index"]))
    expected_span = f"{int(first['year'])}-{int(last['year'])}"
    return {
        "day_zero_utc": ctx.t0.isoformat(),
        "day_zero_read_from": ctx.t0_evidence,
        "artefact_day_zero_utc": artefact_epoch.isoformat(),
        "artefact_day_zero_read_from": (
            "wp5_tenyear.json years[year_index == 0].year, 1 January"
        ),
        "artefact_span": span,
        "artefact_span_matches_years_list": span == expected_span,
        "artefact_master_seed": doc.get("master_seed"),
        "artefact_slice": doc.get("slice"),
        "artefact_n_years": doc.get("n_years_simulated"),
    }


def _other_run_note(doc: dict[str, Any]) -> str:
    return (
        f"these rows come from the ten-year life course, not from the run they "
        f"are written beside: slice {doc.get('slice')!r}, master seed "
        f"{doc.get('master_seed')}, span {doc.get('span')!r}. Its building and "
        f"person ids are its own and do not all join to this package's D02 and "
        f"D05."
    )


def _day_conversion(fields: list[tuple[str, str]], ctx: RunContext) -> list[dict[str, Any]]:
    return [{
        "field": to,
        "from": frm,
        "how": (
            f"day index -> {ctx.t0.isoformat()} + index days, at UTC midnight"
        ),
        "why": (
            "Appendix D.2/D.2b: the artefact carries a day index and the "
            "schema declares a timestamp. The origin is the run's own earliest "
            "written timestamp, cross-checked against the artefact's years list."
        ),
    } for frm, to in fields]


# --------------------------------------------------------------------------- #
# D03  building_passport
# --------------------------------------------------------------------------- #

def export_d03(ctx: RunContext) -> dict[str, Any]:
    doc = _load(ctx)
    evidence = _epoch(ctx, doc)
    src = doc.get("d03_passport_events") or []
    if not src:
        raise ExportError("the artefact carries no d03_passport_events rows")

    rows = []
    for r in src:
        driver = str(r["driver"])
        measure = r.get("measure")
        if measure and str(measure) not in driver:
            driver = f"{driver} | wp5 measure: {measure}"
        rows.append({
            "passport_event_id": r["passport_event_id"],
            "building_id": r["building_id"],
            "event_type": r["event_type"],
            "effective_at": ctx.day_to_timestamp(r.get("effective_day")),
            "decided_at": ctx.day_to_timestamp(r.get("decided_day")),
            "from_version": r["from_version"],
            "to_version": r["to_version"],
            "parameters_changed": r.get("parameters_changed") or {},
            "driver": driver,
            "life_event_id": r.get("life_event_id"),
        })
    frame = pd.DataFrame(rows).sort_values(
        ["effective_at", "passport_event_id"]).reset_index(drop=True)
    return emit(
        frame, "D03", ctx,
        source=f"{TENYEAR_ARTEFACT}:d03_passport_events",
        conversions=_day_conversion(
            [("effective_day", "effective_at"), ("decided_day", "decided_at")],
            ctx,
        ) + [{
            "field": "driver",
            "from": "measure",
            "how": (
                "the artefact's `measure` key appended to `driver` where the "
                "driver text did not already contain it"
            ),
            "why": (
                "Appendix D.2b: `measure` is on disk and the schema does not "
                "declare it, so coerce_frame would drop it silently. Folded "
                "into the field that already carries the model and reason."
            ),
        }],
        limitations=[
            _other_run_note(doc),
            "parameters_changed carries the CHANGED flag per parameter, not "
            "the before and after values; the paired values are in the same "
            "artefact under dated_passport_physics.effects, which the schema "
            "declares no column for",
        ],
        extra={"export_day_index_conversion": evidence},
    )


# --------------------------------------------------------------------------- #
# D09  life_events
# --------------------------------------------------------------------------- #

def export_d09(ctx: RunContext) -> dict[str, Any]:
    doc = _load(ctx)
    evidence = _epoch(ctx, doc)
    src = doc.get("d09_life_events") or []
    if not src:
        raise ExportError("the artefact carries no d09_life_events rows")

    unmapped = sorted({
        str(r["event_type"]) for r in src
        if str(r["event_type"]) not in D09_EVENT_TYPE_MAP
    })
    if unmapped:
        raise ExportError(
            f"the artefact carries life-course event types this export has no "
            f"declared mapping for: {unmapped}. datasets.yaml's "
            f"`life_event_type` enum is "
            f"[birth, death, move in, move out, partnering, separation, job "
            f"change, retirement, health change, retrofit decision, DER "
            f"decision, extension]. Guessing a member would mislabel an event; "
            f"this is a schema finding for the coordinator, not something the "
            f"exporter may decide."
        )

    counts: dict[str, int] = {}
    rows = []
    for r in src:
        original = str(r["event_type"])
        mapped = D09_EVENT_TYPE_MAP[original]
        counts[f"{original} -> {mapped}"] = counts.get(
            f"{original} -> {mapped}", 0) + 1
        cause = str(r["cause"])
        if original != mapped:
            cause = f"{cause} | wp5 event_type: {original}"
        rows.append({
            "event_id": r["event_id"],
            "event_type": mapped,
            "effective_at": ctx.day_to_timestamp(r.get("effective_day")),
            "decided_at": ctx.day_to_timestamp(r.get("decided_day")),
            "persons": list(r.get("persons") or []),
            "household_id": r.get("household_id"),
            "building_id": r.get("building_id"),
            "cause": cause,
            "observable_effects": r.get("observable_effects") or {},
        })
    frame = pd.DataFrame(rows).sort_values(
        ["effective_at", "event_id"]).reset_index(drop=True)
    return emit(
        frame, "D09", ctx,
        source=f"{TENYEAR_ARTEFACT}:d09_life_events",
        conversions=_day_conversion(
            [("effective_day", "effective_at"), ("decided_day", "decided_at")],
            ctx,
        ) + [{
            "field": "event_type",
            "how": "mapped onto the declared life_event_type enum",
            "mapping": counts,
            "lossy": D09_LOSSY,
            "why": (
                "the WP5 life course emits 17 event types and the enum "
                "declares 12; the mapping is the EXPORT's and the original "
                "value is appended to `cause` wherever it differs, so nothing "
                "is destroyed"
            ),
        }],
        limitations=[
            _other_run_note(doc),
            "`household_dissolved` has no declared enum member: it is a "
            "household-level consequence with an empty `persons` list, mapped "
            "to 'move out' because that is the composition change it produces. "
            "A SCHEMA FINDING, reported and not edited.",
            "two WP5 retrofit types and three DER types collapse onto one enum "
            "member each; see the event_type conversion's `lossy` note",
        ],
        extra={"export_day_index_conversion": evidence},
    )


# --------------------------------------------------------------------------- #
# D20  change_labels
# --------------------------------------------------------------------------- #

def export_d20(ctx: RunContext) -> dict[str, Any]:
    doc = _load(ctx)
    evidence = _epoch(ctx, doc)
    src = doc.get("d20_change_labels") or []
    if not src:
        raise ExportError("the artefact carries no d20_change_labels rows")

    rows = []
    for r in src:
        rows.append({
            "label_id": r["label_id"],
            "building_id": r["building_id"],
            "change_class": r["change_class"],
            "true_onset": ctx.day_to_timestamp(r.get("true_onset_day")),
            "true_end": ctx.day_to_timestamp(r.get("true_end_day")),
            "persistence": r["persistence"],
            "source_event_ids": list(r.get("source_event_ids") or []),
            "detectable_from_tier": r["detectable_from_tier"],
            "observable_change_text": r["observable_change_text"],
        })
    frame = pd.DataFrame(rows).sort_values(
        ["true_onset", "label_id"]).reset_index(drop=True)
    return emit(
        frame, "D20", ctx,
        source=f"{TENYEAR_ARTEFACT}:d20_change_labels",
        conversions=_day_conversion(
            [("true_onset_day", "true_onset"), ("true_end_day", "true_end")],
            ctx,
        ),
        limitations=[
            _other_run_note(doc),
            "D20's own access_note says 'Scoring API only. Never released, not "
            "even in the ground-truth package handed to a model.' It is written "
            "into the ground_truth package because release/packages.py lists it "
            "in GROUND_TRUTH_DATASETS and states that the labels are held for "
            "the scoring API. Whoever hands a package to a model under test "
            "must still withhold this part.",
            "day resolution: an onset is midnight on its day, because the "
            "artefact records a day index and not a time of day",
        ],
        extra={"export_day_index_conversion": evidence,
               "access_note": (
                   "scoring API only; withhold from any package given to a "
                   "model under test")},
    )
