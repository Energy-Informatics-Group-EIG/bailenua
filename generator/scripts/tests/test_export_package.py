"""The export package's own contracts, independent of what is on disk.

Three things it cannot be allowed to get wrong silently:

* the two setpoint constants it mirrors from the frozen engine;
* the enum maps it applies at the D31 boundary, which must still be onto the
  declared enums;
* the day-index conversion, which must refuse a wrong origin rather than shift
  every event by a year.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

import baile_nua
from baile_nua.export import nonsensor_datasets as NSX
from baile_nua.export.context import ExportError, RunContext
from baile_nua.schema import load

PROJECT_ROOT = Path(baile_nua.__file__).resolve().parents[2]


def test_export_setpoint_constants_match_the_engine() -> None:
    """D29's comfort truth mirrors one line of ``engine.run``; pin that line.

    The runner computes the asked-for setpoint inside the day loop and retains
    none of it, so :mod:`baile_nua.export.nonsensor_datasets` mirrors the two
    constants. I-084's lesson is that a second implementation of a frozen
    mechanism drifts in silence, so this asserts the engine's own source still
    says what the mirror assumes. If the engine changes, this fails - which is
    the point; it is not a reason to loosen the assertion.
    """
    src = (Path(baile_nua.__file__).parent / "engine" / "run.py").read_text(
        encoding="utf-8")
    expected = (
        f"setpoint = {NSX.SETPOINT_BASE_C} + {NSX.SETPOINT_PER_COMFORT_C} * "
        f"float(np.clip(people[0].comfort, -2, 2))"
    )
    assert expected in src, (
        f"engine/run.py no longer contains {expected!r}, so "
        f"nonsensor_datasets.SETPOINT_BASE_C / SETPOINT_PER_COMFORT_C no "
        f"longer mirror the engine, and D29's q_comfort_preference_c would be "
        f"observing a setpoint the model never asked for."
    )


def test_d31_enum_maps_land_inside_the_declared_enums() -> None:
    schema = load()
    quality = set(schema.enums["quality_flag"])
    provenance = set(schema.enums["provenance_code"])
    bad_q = sorted(set(NSX.D31_QUALITY_MAP.values()) - quality)
    bad_p = sorted(set(NSX.D31_PROVENANCE_MAP.values()) - provenance)
    assert not bad_q, f"D31 quality map targets {bad_q}, not in quality_flag"
    assert not bad_p, f"D31 provenance map targets {bad_p}, not in provenance_code"


def test_d09_event_type_map_lands_inside_the_declared_enum() -> None:
    from baile_nua.export.from_evidence import D09_EVENT_TYPE_MAP

    declared = set(load().enums["life_event_type"])
    bad = sorted(set(D09_EVENT_TYPE_MAP.values()) - declared)
    assert not bad, f"D09 event_type map targets {bad}, not in life_event_type"


def test_day_index_conversion_refuses_a_wrong_origin(tmp_path: Path) -> None:
    """The one error that would be invisible: a day-zero off by a year."""
    from baile_nua.export import from_evidence

    ctx = RunContext(run_root=tmp_path, out_root=tmp_path)
    ctx.t0 = pd.Timestamp("2023-01-01", tz="UTC")
    doc = {"years": [{"year": 2022, "year_index": 0},
                     {"year": 2031, "year_index": 9}], "span": "2022-2031"}
    with pytest.raises(ExportError, match="whole year"):
        from_evidence._epoch(ctx, doc)


def test_day_index_conversion_accepts_the_matching_origin(tmp_path: Path) -> None:
    from baile_nua.export import from_evidence

    ctx = RunContext(run_root=tmp_path, out_root=tmp_path)
    ctx.t0 = pd.Timestamp("2022-01-01", tz="UTC")
    doc = {"years": [{"year": 2022, "year_index": 0},
                     {"year": 2031, "year_index": 9}], "span": "2022-2031"}
    ev = from_evidence._epoch(ctx, doc)
    assert ev["artefact_span_matches_years_list"] is True
    assert ctx.day_to_timestamp(17) == pd.Timestamp("2022-01-18", tz="UTC")
    assert ctx.day_to_timestamp(None) is None


def test_emit_refuses_an_empty_frame(tmp_path: Path) -> None:
    """An empty part would read as 'the model produced nothing'."""
    from baile_nua.export.writer import emit

    ctx = RunContext(run_root=tmp_path, out_root=tmp_path)
    with pytest.raises(ExportError, match="not an honest absence"):
        emit(pd.DataFrame(), "D02", ctx, source="a test")


def test_absent_entries_name_a_required_field_or_an_owner() -> None:
    """A recorded absence has to say what is missing, not just that it is."""
    from baile_nua.export.absent import ABSENT

    for dataset_id, rec in sorted(ABSENT.items()):
        assert rec["reason"].strip(), f"{dataset_id}: empty reason"
        assert rec["needs"].strip(), f"{dataset_id}: no `needs`"
        declared = set(load()[dataset_id].field_map)
        unknown = sorted(set(rec["missing_required"]) - declared)
        assert not unknown, (
            f"{dataset_id}: missing_required names {unknown}, which "
            f"datasets.yaml does not declare for it")
