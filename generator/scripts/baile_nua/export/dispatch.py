"""One entry point: :func:`export_all`.

Parameterised by an input run root and an output root, and by nothing else.
The same call exports the estate year, the 14-day town run, or
``work/town_decade/year_YYYY/`` when it exists::

    export_all("v1", "v1")
    export_all("work/town4/pkg", "v1", subdir="town14")
    export_all("work/town_decade/year_2023", "work/town_decade/year_2023")

What it returns is the whole account: what was written, with rows and bytes;
what was not, with the recorded reason; and what failed, with the error.  A
failure is reported as a failure and never as an absence.
"""

from __future__ import annotations

import dataclasses

from typing import Any, Callable, Iterable

from baile_nua.export import (
    assets,
    biographies,
    calibration_targets,
    from_evidence,
    nonsensor_datasets,
    run_manifest,
    structural,
    tariffs,
)
from baile_nua.export.absent import ABSENT, OWNED_ELSEWHERE, reason_for
from baile_nua.export.context import ArtefactAbsent, RunContext

__all__ = [
    "EXPORTERS",
    "WRITTEN_BY_THE_ENGINE",
    "ALL_DATASETS",
    "RELOCATED_TO_RUN",
    "export_all",
]

#: ``dataset_id -> exporter``.  The datasets this package can write.
EXPORTERS: dict[str, Callable[[RunContext], dict[str, Any]]] = {
    "D01": structural.export_d01,
    "D02": structural.export_d02,
    "D03": from_evidence.export_d03,
    "D04": assets.export_d04,
    "D05": structural.export_d05,
    "D06": structural.export_d06,
    "D07": structural.export_d07,
    "D08": structural.export_d08,
    "D09": from_evidence.export_d09,
    "D14": structural.export_d14,
    "D15": structural.export_d15,
    "D20": from_evidence.export_d20,
    "D21": biographies.export_d21,
    "D22": structural.export_d22,
    "D23": run_manifest.export_d23,
    "D24": calibration_targets.export_d24,
    "D27": tariffs.export_d27,
    "D28": nonsensor_datasets.export_d28,
    "D29": nonsensor_datasets.export_d29,
    "D30": nonsensor_datasets.export_d30,
    "D31": nonsensor_datasets.export_d31,
}

#: Written by :class:`~baile_nua.engine.stream_writer.StreamWriter` during the
#: run itself.  This package never writes them: they are the run's own output
#: and re-deriving them would mean re-simulating the year.
WRITTEN_BY_THE_ENGINE: tuple[str, ...] = (
    "D10", "D11", "D13", "D16", "D17", "D17_aggregate", "D18", "D19",
)

#: ``dataset_id -> run``.  Datasets whose ROWS describe a different run than
#: the one being exported, and which therefore belong in that run's own
#: package rather than beside the estate-year's.
#:
#: I-091 established this as a packaging decision and 040e9de carried it out by
#: MOVING the three files by hand: D03, D09 and D20 are the WP5 decade's rows -
#: a 60-home u23_mixed_age slice at seed 20251010 - and they sat beside the
#: estate-year's 50-home, seed-20261008 D05/D06/D08 while sharing no person at
#: all with them, which made every biography's life-event section read "no
#: record covers this date".
#:
#: Moved, but not re-plumbed, so the relocation survived only until the next
#: export. I-103: `python -m baile_nua.export v1 v1` during the freeze-2 rebuild
#: recreated all three at the top level, byte-identical to the relocated copies,
#: and reported n_failed: 0 while doing it. This registry is the fix - the
#: pipeline now writes them where they belong instead of leaving it to whoever
#: remembers to move them.
RELOCATED_TO_RUN: dict[str, str] = {
    "D03": "wp5_decade",
    "D09": "wp5_decade",
    "D20": "wp5_decade",
}

#: Every declared dataset id, in ``schema/datasets.yaml`` declaration order.
#: Hardcoded rather than read from the schema on purpose: the point of
#: ``test_every_declared_dataset_is_accounted_for`` is to catch drift
#: between this list and the schema, which deriving it would hide.
#: BN-1 added ``D17_aggregate``, the first id with an underscore (I-099).
ALL_DATASETS: tuple[str, ...] = (
    *(f"D{i:02d}" for i in range(1, 18)),
    "D17_aggregate",
    *(f"D{i:02d}" for i in range(18, 32)),
)


def export_all(
    run_root: Any,
    out_root: Any,
    *,
    which: Iterable[str] | None = None,
    subdir: str | None = None,
    run_name: str | None = None,
    relocate: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Export every dataset this package can write from ``run_root``.

    ``which`` restricts the set; everything else is still reported, so a
    partial export's record still says what the whole package looks like.
    """
    ctx = RunContext.open(run_root, out_root, subdir=subdir, run_name=run_name)
    asked = (None if which is None
             else {str(w).upper() for w in which})

    records: dict[str, dict[str, Any]] = {}
    for dataset_id in ALL_DATASETS:
        if dataset_id in WRITTEN_BY_THE_ENGINE:
            records[dataset_id] = {
                "verdict": "written by the engine",
                "reason": (
                    "streamed by engine.stream_writer.StreamWriter during the "
                    "run; this package does not rewrite it"
                ),
            }
            continue
        if dataset_id in OWNED_ELSEWHERE:
            records[dataset_id] = reason_for(dataset_id) or {}
            continue
        if dataset_id in ABSENT:
            records[dataset_id] = reason_for(dataset_id) or {}
            continue
        exporter = EXPORTERS.get(dataset_id)
        if exporter is None:
            records[dataset_id] = {
                "verdict": "not written",
                "reason": (
                    "no exporter and no recorded reason: a gap in THIS package, "
                    "which is itself the finding"
                ),
            }
            continue
        if asked is not None and dataset_id not in asked:
            records[dataset_id] = {
                "verdict": "skipped",
                "reason": f"not in which={sorted(asked)}",
            }
            continue
        # I-091 / I-103. A dataset whose rows describe another run is written
        # into THAT run's package, not beside the estate-year's. Only when the
        # caller did not already name a subdir: an explicit --subdir is the
        # caller exporting one specific run and must win.
        # `relocate` defaults to the registry. The 2015-2026 replay passes {}:
        # its life course IS the run, so D03/D09/D20 describe THIS run and
        # there is no separate wp5_decade package to file them under (I-103).
        table = RELOCATED_TO_RUN if relocate is None else relocate
        use_ctx = ctx
        relocated_to = None
        if subdir is None and dataset_id in table:
            relocated_to = table[dataset_id]
            use_ctx = dataclasses.replace(ctx, subdir=relocated_to)
        try:
            records[dataset_id] = exporter(use_ctx)
            if relocated_to is not None and isinstance(
                    records[dataset_id], dict):
                records[dataset_id]["relocated_to_run"] = relocated_to
                records[dataset_id]["relocated_because"] = (
                    "its rows describe the "
                    f"{relocated_to} run, not this one (I-091); written under "
                    f"<package>/{relocated_to}/ so the claim the package makes "
                    "about itself stays true (I-103)"
                )
        except ArtefactAbsent as exc:
            # An absence, not a failure: this run carries no such artefact.
            records[dataset_id] = {
                "verdict": "not written",
                "reason": str(exc),
                "missing_required": [],
                "needs": (
                    "a run root that carries the artefact; the ten-year life "
                    "course produces it"
                ),
            }
        except Exception as exc:                      # reported, not swallowed
            records[dataset_id] = {
                "verdict": "failed",
                "error_type": type(exc).__name__,
                "error": str(exc),
            }

    written = [d for d, r in records.items() if r.get("verdict") == "written"]
    failed = [d for d, r in records.items() if r.get("verdict") == "failed"]
    return {
        "label": _label(),
        "run": ctx.provenance(),
        "out_root": str(ctx.out_root),
        "subdir": subdir,
        "datasets": records,
        "n_written": len(written),
        "n_failed": len(failed),
        "written": sorted(written),
        "failed": sorted(failed),
        "total_bytes": int(sum(
            int(r.get("bytes") or 0) for r in records.values())),
        "total_rows": int(sum(
            int(r.get("rows") or 0) for r in records.values())),
    }


def _label() -> str:
    from baile_nua.schema import load

    return load().label
