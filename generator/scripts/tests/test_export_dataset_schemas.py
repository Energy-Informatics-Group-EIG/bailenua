"""One schema test per dataset, over every exported package on disk.

For each of the 31 datasets ``datasets.yaml`` declares, and for each export
target, this asserts four things about what is actually on disk:

1. every declared **required** field is present as a column;
2. there is **no undeclared top-level column**;
3. every declared **type** is compatible with the Parquet type written;
4. **access-class separation** holds - the part sits in the release package its
   access class dictates, its sidecar manifest says so, and its columns pass
   the same leakage audit :mod:`baile_nua.io` runs on every write.

**Top-level, and why it matters.**  D19's ``building_energy_profile`` is a
struct, and the Parquet footer flattens it: ``ParquetFile.schema.names`` says
``mean_w, peak_to_mean, interval_min`` where the schema declares one JSON
field.  A test written against the flat view therefore fails D19 for three
undeclared columns that do not exist.  So every comparison here is against
``schema_arrow.names``, which keeps a struct as one named field, and
:func:`test_d19_struct_is_flattened_by_the_footer` pins that difference so the
reason cannot be forgotten.

**An absent dataset is skipped with its reason, never passed.**  A dataset with
no part on disk is skipped and the skip message is the reason recorded in
:mod:`baile_nua.export.absent` - and a dataset that is absent with NO recorded
reason FAILS, because an unaccounted absence is the one thing this file exists
to catch.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import baile_nua
from baile_nua.export.absent import (
    EVIDENCE_PACKAGE_NOTE,
    OWNED_ELSEWHERE,
    reason_for,
)
from baile_nua.export.dispatch import ALL_DATASETS, WRITTEN_BY_THE_ENGINE
from baile_nua.export.from_evidence import artefact_path, artefact_present
from baile_nua.schema import load
from baile_nua.schema.access import audit_frame, package_for

PROJECT_ROOT = Path(baile_nua.__file__).resolve().parents[2]

#: ``(name, run_root, out_root, subdir)``.  Add a target here and all 31
#: tests follow it.  ``run_root`` is carried so an absence can be checked
#: against what that run actually produced: the 14-day town run stepped no
#: life course, so it has no ten-year artefact and therefore no D03, D09 or
#: D20 rows to convert - an absence with a reason, not an unaccounted one.
EXPORT_TARGETS: tuple[tuple[str, Path, Path, str | None], ...] = (
    ("estate-year", PROJECT_ROOT / "v1", PROJECT_ROOT / "v1", None),
    ("town-14day", PROJECT_ROOT / "work" / "town4" / "pkg",
     PROJECT_ROOT / "v1", "town14"),
)

#: Schema type -> the Arrow types that may carry it.
TYPE_OK: dict[str, Any] = {
    "string": lambda t: pa.types.is_string(t) or pa.types.is_large_string(t),
    "enum": lambda t: pa.types.is_string(t) or pa.types.is_large_string(t),
    "int": pa.types.is_integer,
    "float": lambda t: pa.types.is_floating(t) or pa.types.is_decimal(t),
    "bool": pa.types.is_boolean,
    "timestamp": pa.types.is_timestamp,
    "date": lambda t: pa.types.is_date(t) or pa.types.is_timestamp(t),
    # A `json` field may arrive as an object (Arrow struct or map), as a
    # serialised string, or as an ARRAY - a JSON array is JSON, and D29's
    # `q_appliances` is a ticked list of appliance names. The schema has a
    # separate `list[...]` type for a typed sequence, so a `json` field
    # carrying a list is a loose DECLARATION rather than a wrong value, and
    # it is reported as a schema finding rather than failed here.
    "json": lambda t: (pa.types.is_struct(t) or pa.types.is_map(t)
                       or pa.types.is_string(t) or pa.types.is_large_string(t)
                       or pa.types.is_list(t) or pa.types.is_large_list(t)),
}


def _list_ok(declared: str, t: pa.DataType) -> bool:
    return pa.types.is_list(t) or pa.types.is_large_list(t)


def _dir_for(out_root: Path, subdir: str | None, package: str) -> Path:
    base = out_root / package
    return base / subdir if subdir else base


def _parts(
    run_root: Path, out_root: Path, subdir: str | None, dataset_id: str
) -> list[Path]:
    """Where this dataset's parts live for this target.

    The five the engine streams were written by the RUN, into its own run
    root, and are not re-exported; everything else is written by this package
    into the out root (under ``subdir`` where one is given). Looking for a
    streamed part in the out root is how the town target first reported five
    datasets missing that were sitting in ``work/town4/pkg`` all along.
    """
    schema = load()
    package = package_for(dataset_id, schema)
    if dataset_id in WRITTEN_BY_THE_ENGINE:
        return sorted((run_root / package).glob(f"{dataset_id}_part*.parquet"))
    return sorted(
        _dir_for(out_root, subdir, package).glob(f"{dataset_id}_part*.parquet")
    )


def _engine_wrote(run_root: Path) -> dict[str, Any] | None:
    """What the run's OWN storage report says it streamed, or None.

    ``StreamWriter.storage_report()`` lands in the run's diagnostics, so
    whether a run wrote D18 is a fact on disk and not a guess: the 14-day town
    run was given ``omit_datasets={'D18'}`` and its report lists D11, D13, D16
    and D19 only.
    """
    import json

    path = run_root / "run_diagnostics.json"
    if not path.is_file():
        return None
    diag = json.loads(path.read_text(encoding="utf-8"))
    return (((diag.get("benchmark") or {}).get("storage") or {})
            .get("by_dataset"))


def _skip_reason(dataset_id: str, target: str, run_root: Path) -> str:
    schema = load()
    if dataset_id in WRITTEN_BY_THE_ENGINE:
        streamed = _engine_wrote(run_root)
        if streamed is not None and dataset_id not in streamed:
            return (
                f"{dataset_id} absent from {target}: the RUN did not stream "
                f"it. Its own storage report in "
                f"{run_root / 'run_diagnostics.json'} lists "
                f"{sorted(streamed)}, so the dataset was omitted at run time "
                f"(StreamWriter takes omit_datasets) and there is nothing for "
                f"an exporter to do about it"
            )
    if package_for(dataset_id, schema) == "evidence":
        return f"{dataset_id} absent from {target}: {EVIDENCE_PACKAGE_NOTE}"
    if dataset_id in ("D03", "D09", "D20") and not artefact_present(run_root):
        return (
            f"{dataset_id} absent from {target}: the run at {run_root} carries "
            f"no {artefact_path(run_root).name}, so it stepped no life course "
            f"and produced no passport event, life event or change label to "
            f"convert"
        )
    # I-091. A dataset whose rows describe a DIFFERENT run was relocated into
    # that run's own package under v1/<package>/<run>/, so it is absent from
    # this target on purpose. Checked against the filesystem rather than a
    # list, so the reason names the run and the row count that are actually
    # there: D09's 250 events are the WP5 decade's 60-home slice at seed
    # 20251010 and share no person with the estate-year's D05, which is what
    # made every biography's life-event section read "no record" (Agent F
    # measured it). The parts are still schema-tested, by
    # test_relocated_run_parts_conform_to_their_declared_schema below.
    pkg_dir = _dir_for(out_root_for(target), None, package_for(dataset_id, schema))
    for sub in sorted(d for d in pkg_dir.glob("*") if d.is_dir()):
        found = sorted(sub.glob(f"{dataset_id}_part*.parquet"))
        if found:
            return (
                f"{dataset_id} absent from {target} on purpose: its rows "
                f"describe the `{sub.name}` run, not this one, so they live "
                f"in {sub} ({len(found)} part(s)). Relocated under I-091 "
                f"because they shared no person with this target's D05."
            )
    recorded = reason_for(dataset_id)
    if recorded is None:
        return ""
    return (
        f"{dataset_id} absent from {target}, recorded reason: "
        f"{recorded['reason']} NEEDS: {recorded.get('needs')}"
    )


def _ids() -> list[str]:
    return [f"{name}:{d}"
            for name, _rr, _or, _s in EXPORT_TARGETS for d in ALL_DATASETS]


_CASES = [(name, run_root, out_root, sub, d)
          for name, run_root, out_root, sub in EXPORT_TARGETS
          for d in ALL_DATASETS]


@pytest.mark.parametrize(
    ("target", "run_root", "out_root", "subdir", "dataset_id"),
    _CASES, ids=_ids(),
)
def test_written_parquet_matches_the_declared_schema(
    target: str, run_root: Path, out_root: Path, subdir: str | None,
    dataset_id: str,
) -> None:
    schema = load()
    ds = schema[dataset_id]
    parts = _parts(run_root, out_root, subdir, dataset_id)

    if not parts:
        reason = _skip_reason(dataset_id, target, run_root)
        if not reason:
            pytest.fail(
                f"{dataset_id} ({ds.name}) has no Parquet part under "
                f"{_dir_for(out_root, subdir, package_for(dataset_id, schema))} "
                f"(nor, for an engine-streamed dataset, under "
                f"{run_root / package_for(dataset_id, schema)}) "
                f"for target {target!r}, and no reason is recorded for its "
                f"absence - not in baile_nua.export.absent.ABSENT, not in "
                f"OWNED_ELSEWHERE, and not written by the engine. An "
                f"unaccounted absence is exactly what this test exists to "
                f"catch: either export it or record why it cannot be exported."
            )
        pytest.skip(reason)

    declared = set(ds.field_map)
    required = set(ds.required_fields)
    for path in parts:
        pf = pq.ParquetFile(path)
        # schema_arrow, not schema: the footer flattens a struct field into
        # its leaves (see the module docstring and the D19 test below).
        arrow = pf.schema_arrow
        names = list(arrow.names)

        assert len(names) == len(set(names)), (
            f"{path.name}: duplicate top-level column names {names}")

        missing = sorted(required - set(names))
        assert not missing, (
            f"{path.name}: declared required field(s) {missing} are not "
            f"columns. Columns on disk: {names}")

        undeclared = sorted(set(names) - declared)
        assert not undeclared, (
            f"{path.name}: top-level column(s) {undeclared} are not declared "
            f"in datasets.yaml for {dataset_id}. The schema is the single "
            f"source of truth (D-005), so this is a finding about the writer "
            f"or about the schema, never a licence to widen the test.")

        for name in names:
            field = ds.field_map[name]
            t = arrow.field(name).type
            if field.type.startswith("list["):
                assert _list_ok(field.type, t), (
                    f"{path.name}.{name}: declared {field.type}, written as {t}")
                continue
            check = TYPE_OK.get(field.type)
            assert check is not None, (
                f"{dataset_id}.{name}: schema declares type {field.type!r}, "
                f"which this test has no compatibility rule for")
            assert check(t), (
                f"{path.name}.{name}: declared {field.type}, written as {t}")
            if field.type == "timestamp":
                assert t.tz is not None, (
                    f"{path.name}.{name}: declared timestamp and written "
                    f"without a time zone; the units block declares "
                    f"'UTC timestamptz'")


# Marked `leakage` so it is reported with the rest of design 5.1's suite, the
# way ci.sh reports each criterion separately.
@pytest.mark.leakage
@pytest.mark.parametrize(
    ("target", "run_root", "out_root", "subdir", "dataset_id"),
    _CASES, ids=_ids(),
)
def test_written_parquet_respects_access_class_separation(
    target: str, run_root: Path, out_root: Path, subdir: str | None,
    dataset_id: str,
) -> None:
    """GT never in an observable package, and no GT field name in an OBS one."""
    import json

    schema = load()
    parts = _parts(run_root, out_root, subdir, dataset_id)
    if not parts:
        reason = _skip_reason(dataset_id, target, run_root)
        if not reason:
            pytest.fail(
                f"{dataset_id} absent from {target} with no recorded reason; "
                f"see test_written_parquet_matches_the_declared_schema")
        pytest.skip(reason)

    expected_package = package_for(dataset_id, schema)
    for path in parts:
        assert expected_package in path.parts, (
            f"{path}: {dataset_id} is access class "
            f"{schema[dataset_id].access_class}, which design 6.3 places in "
            f"{expected_package}/, and the path does not go through it")
        for other in ("observable", "ground_truth", "evidence"):
            if other != expected_package:
                assert other not in path.parts, (
                    f"{path}: also sits under {other}/, so the three packages "
                    f"are not separate")

        names = list(pq.ParquetFile(path).schema_arrow.names)
        # The same audit baile_nua.io runs on every write: declared fields,
        # no GT-class field name in an OBS dataset, no forbidden pattern.
        audit_frame(names, dataset_id, schema)

        manifest = path.parent / f"{path.stem}.manifest.json"
        assert manifest.is_file(), f"{path}: no sidecar manifest"
        meta = json.loads(manifest.read_text(encoding="utf-8"))
        assert meta["access_class"] == schema[dataset_id].access_class, (
            f"{manifest}: manifest says access_class {meta['access_class']!r}, "
            f"schema says {schema[dataset_id].access_class!r}")
        assert meta["release_package"] == expected_package, (
            f"{manifest}: manifest says release_package "
            f"{meta['release_package']!r}, schema implies {expected_package!r}")
        assert set(meta["columns"]) == set(names), (
            f"{manifest}: the manifest's column list and the Parquet "
            f"top-level columns disagree")
        if schema[dataset_id].access_class == "OBS":
            assert "leakage_audit" in meta, (
                f"{manifest}: an OBS part must carry the leakage_audit stamp")


# --------------------------------------------------------------------------- #
# the two facts the tests above depend on
# --------------------------------------------------------------------------- #

def test_d19_struct_is_flattened_by_the_footer() -> None:
    """Pin the reason the tests compare top-level names.

    If this ever stops being true, the schema tests above are comparing the
    wrong thing and should be revisited rather than quietly adjusted.
    """
    parts = _parts(PROJECT_ROOT / "v1", PROJECT_ROOT / "v1", None, "D19")
    if not parts:
        pytest.skip("D19 is not on disk in v1/observable")
    pf = pq.ParquetFile(parts[0])
    assert "building_energy_profile" in pf.schema_arrow.names
    assert pa.types.is_struct(
        pf.schema_arrow.field("building_energy_profile").type)
    flat = set(pf.schema.names)
    assert "building_energy_profile" not in flat, (
        "the footer no longer flattens the struct; the top-level comparison "
        "in this module was written because it did")
    assert {"mean_w", "peak_to_mean", "interval_min"} <= flat


def test_every_declared_dataset_is_accounted_for() -> None:
    """All 31 are exported, engine-written, owned elsewhere, or reasoned about."""
    from baile_nua.export.dispatch import EXPORTERS

    unaccounted = [
        d for d in ALL_DATASETS
        if d not in EXPORTERS
        and d not in WRITTEN_BY_THE_ENGINE
        and d not in OWNED_ELSEWHERE
        and reason_for(d) is None
    ]
    assert not unaccounted, (
        f"datasets with no exporter and no recorded reason: {unaccounted}")
    assert len(ALL_DATASETS) == len(load().datasets), (
        "datasets.yaml no longer declares 31 datasets")


def out_root_for(target: str) -> Path:
    """The out root for a target name, from EXPORT_TARGETS."""
    for name, _run, out, _sub in EXPORT_TARGETS:
        if name == target:
            return Path(out)
    raise AssertionError(f"unknown target {target}")


def test_relocated_run_parts_conform_to_their_declared_schema():
    """I-091's relocated parts are still held to the schema.

    Moving a dataset into the run it describes must not move it out of
    coverage. This walks every run subdirectory under every package and checks
    each part it finds against datasets.yaml, so D03, D09 and D20 under
    wp5_decade are tested exactly as they were when they sat at the top level
    - and so is anything a later run puts there.
    """
    import pyarrow.parquet as pq

    schema = load()
    checked = 0
    for pkg in ("observable", "ground_truth", "evidence"):
        base = PROJECT_ROOT / "v1" / pkg
        if not base.is_dir():
            continue
        for sub in sorted(d for d in base.iterdir() if d.is_dir()):
            for part in sorted(sub.glob("D*_part*.parquet")):
                ds = part.name.split("_part")[0]
                try:
                    declared = {f.name for f in schema[ds].fields}
                except KeyError:
                    continue
                on_disk = {n.split(".", 1)[0]
                           for n in pq.ParquetFile(part).schema_arrow.names}
                undeclared = sorted(on_disk - declared)
                assert not undeclared, (
                    f"{part} carries columns the schema does not declare: "
                    f"{undeclared}")
                assert package_for(ds, schema) == pkg, (
                    f"{part} sits in {pkg} but {ds} is declared for "
                    f"{package_for(ds, schema)}")
                checked += 1
    assert checked > 0, (
        "no relocated run parts were found, so this test asserted nothing; "
        "if the relocation under I-091 was undone, delete this test")


def test_relocated_datasets_are_not_at_the_top_level(tmp_path) -> None:
    """I-103. The pipeline, not a person, keeps the I-091 relocation.

    040e9de settled I-091 by MOVING D03, D09 and D20 into
    `v1/ground_truth/wp5_decade/` - their rows are the WP5 decade's, a 60-home
    u23_mixed_age slice at seed 20251010, and they had been sitting beside the
    estate-year's 50-home seed-20261008 D05/D06/D08 while sharing no person at
    all with them. Moved, but not re-plumbed: `export_all` still listed them in
    EXPORTERS and still wrote them to `<out_root>/ground_truth/`, so the
    relocation survived exactly until the next export.

    It did not survive the freeze-2 rebuild. `python -m baile_nua.export v1 v1`
    recreated all three at the top level, byte-identical to the relocated
    copies, and reported `n_failed: 0` while doing it. The new top-level D09
    shared 0 of 147 persons with the estate-year's D05, which is I-091 as first
    reported.

    This asserts the fix at both ends: the registry says where they belong, and
    an export into a scratch out_root puts them there rather than at the top.
    """
    from baile_nua.export.dispatch import RELOCATED_TO_RUN, export_all

    assert RELOCATED_TO_RUN == {"D03": "wp5_decade", "D09": "wp5_decade",
                                "D20": "wp5_decade"}, (
        "the relocation registry changed; I-091's packaging decision is that a "
        "dataset lives under the run its rows describe, so a change here needs "
        "a reason recorded with it")

    report = export_all(PROJECT_ROOT / "v1", tmp_path,
                        which=sorted(RELOCATED_TO_RUN), run_name="i103-guard")

    for ds, run in sorted(RELOCATED_TO_RUN.items()):
        rec = report["datasets"][ds]
        if rec.get("verdict") != "written":
            # The run root may carry no life course to convert; that is an
            # absence, not a relocation failure, and it is reported elsewhere.
            continue
        assert rec.get("relocated_to_run") == run, (
            f"{ds} was written without recording that it belongs to {run}")
        top = sorted(tmp_path.glob(f"*/{ds}_part*.parquet"))
        assert not top, (
            f"{ds} was written to the top level of a package at {top}, which "
            f"is exactly what I-091 decided against and I-103 found happening "
            f"again. It belongs under <package>/{run}/.")
        placed = sorted(tmp_path.glob(f"*/{run}/{ds}_part*.parquet"))
        assert placed, (
            f"{ds} is recorded written and relocated to {run}, but no part "
            f"landed under <package>/{run}/ in {tmp_path}")


def test_the_delivered_package_has_no_relocated_dataset_at_its_top_level() -> None:
    """The same guard, against `v1/` as delivered rather than a scratch tree."""
    from baile_nua.export.dispatch import RELOCATED_TO_RUN

    offenders = []
    for ds, run in sorted(RELOCATED_TO_RUN.items()):
        for pkg in ("observable", "ground_truth", "evidence"):
            if sorted((PROJECT_ROOT / "v1" / pkg).glob(f"{ds}_part*.parquet")):
                offenders.append(f"v1/{pkg}/{ds}_part*.parquet (belongs in {run}/)")
    assert not offenders, (
        "relocated datasets found at a package top level in the delivered "
        "package: " + "; ".join(offenders) + ". An export run put them back "
        "(I-103); move them under the run they describe and check the registry "
        "in export/dispatch.py is being honoured.")
