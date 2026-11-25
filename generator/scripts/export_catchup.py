#!/usr/bin/env python3
"""Re-run the per-year export post-pass over a year that is already finished.

Why this exists: the replay's per-year post-pass runs ONCE, inside the
supervisor, at the end of each segment.  A dataset the post-pass could not
write at that moment - because the running supervisor predates the exporter, or
because a per-dataset failure was recorded rather than raised (D-138) - is
missing from that year's package and nothing will go back for it.  The 2015
package is the first case: the replay that produces it is running from the main
checkout, so the D24 exporter on this branch is not in it, and 2015 will land
without D24.

**It is safe to run against an already-exported package.**  Two rules:

*Nothing is deleted.*  ``baile_nua.export.writer.cleanup_stale_parts`` unlinks
the parts of a dataset before re-writing it, which is right inside a run and
wrong for a catch-up: it would destroy the part it is replacing before knowing
the replacement succeeds.  So every existing part of every requested dataset is
MOVED into ``<segment>/superseded/<timestamp>/`` first, keeping its path, and
the export then finds nothing to unlink.  If the re-export fails, the moved
parts are still there and the move is reported.

*The year's own record is added to, not overwritten.*  The original
``export_report.json`` is left exactly as the run wrote it; the catch-up writes
``export_report_catchup_<timestamp>.json`` beside it and appends an entry to
``export_catchup_log.json``, so the year carries both what the run produced and
what was added afterwards.

**It refuses to touch an unfinished segment.**  Without ``DONE.json`` the
segment is either running or failed, and exporting from a half-written run root
would read a package the engine is still streaming into.

Usage::

    python scripts/export_catchup.py work/replay_2015_2026/2015 D24
    python scripts/export_catchup.py work/replay_2015_2026/2015 D04 D24
    python scripts/export_catchup.py --dry-run work/replay_2015_2026/2015 D24
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

#: The three release packages a part can live in.
PACKAGES = ("ground_truth", "observable", "evidence")


def _now() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def existing_parts(pkg: Path, dataset_id: str) -> list[Path]:
    """Every part and sidecar manifest of ``dataset_id`` already in ``pkg``."""
    out: list[Path] = []
    for package in PACKAGES:
        base = pkg / package
        if not base.is_dir():
            continue
        out += sorted(base.glob(f"{dataset_id}_part*"))
    return out


def move_aside(pkg: Path, dataset_ids: list[str], stamp: str,
               *, dry_run: bool = False) -> list[dict]:
    """Move existing parts into ``<pkg>/../superseded/<stamp>/``.

    Moved rather than deleted: the part being replaced is the only copy of
    what the run produced, and a re-export that fails halfway must not have
    destroyed it on the way in.
    """
    dest_root = pkg.parent / "superseded" / stamp
    moved: list[dict] = []
    for dataset_id in dataset_ids:
        for path in existing_parts(pkg, dataset_id):
            rel = path.relative_to(pkg)
            dest = dest_root / rel
            moved.append({"dataset_id": dataset_id, "from": str(path),
                          "to": str(dest)})
            if dry_run:
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(dest))
    return moved


def catchup(segment: Path, dataset_ids: list[str], *,
            dry_run: bool = False, force_unfinished: bool = False) -> dict:
    """Export ``dataset_ids`` into a finished segment's package."""
    from replay_supervisor import prepare_evidence_package

    segment = segment if segment.is_absolute() else (PROJECT / segment)
    pkg = segment / "pkg"
    stamp = _now()

    if not pkg.is_dir():
        raise SystemExit(f"{pkg} does not exist: not an exported segment")
    if not (pkg / "run_diagnostics.json").is_file():
        raise SystemExit(
            f"{pkg}/run_diagnostics.json is missing, so the run's master seed "
            f"and slice kind cannot be read. Every exporter is keyed to the "
            f"seed the run recorded."
        )
    done = segment / "DONE.json"
    if not done.is_file() and not force_unfinished:
        raise SystemExit(
            f"{done} does not exist, so this segment either is still running "
            f"or failed. Exporting from a run root the engine may still be "
            f"streaming into would read a half-written package. Pass "
            f"--force-unfinished only if you know the segment is quiescent."
        )

    record: dict = {
        "catchup_at": stamp,
        "segment": segment.name,
        "package": str(pkg),
        "datasets_requested": list(dataset_ids),
        "dry_run": bool(dry_run),
        "reason": (
            "the per-year post-pass runs once, inside the supervisor; a "
            "dataset it could not write then is missing from the year's "
            "package and nothing else goes back for it"
        ),
    }
    record["evidence_package"] = prepare_evidence_package(pkg)
    record["moved_aside"] = move_aside(pkg, dataset_ids, stamp, dry_run=dry_run)
    if dry_run:
        record["would_run"] = (
            f"export_all({pkg}, {pkg}, which={dataset_ids}, relocate={{}})")
        return record

    from baile_nua.export import export_all

    rep = export_all(pkg, pkg, which=dataset_ids, relocate={},
                     run_name=f"replay {segment.name} catch-up {stamp}")
    # Only the datasets actually asked for: export_all reports on all 31, and
    # a catch-up record that repeats the whole account would read as a claim
    # to have re-exported the year.
    record["datasets"] = {
        d: r for d, r in (rep.get("datasets") or {}).items()
        if d in set(dataset_ids)
    }
    record["n_written"] = sum(
        1 for r in record["datasets"].values() if r.get("verdict") == "written")
    record["n_failed"] = sum(
        1 for r in record["datasets"].values() if r.get("verdict") == "failed")
    record["partially_conformant"] = {
        d: r.get("null_required_fields")
        for d, r in record["datasets"].items() if r.get("null_required_fields")
    }

    # The run's own report is left alone; the catch-up is written beside it.
    (segment / f"export_report_catchup_{stamp}.json").write_text(
        json.dumps(record, indent=2, default=str) + "\n", encoding="utf-8")
    log_path = segment / "export_catchup_log.json"
    log = json.loads(log_path.read_text(encoding="utf-8")) if log_path.is_file() else []
    log.append({k: record[k] for k in (
        "catchup_at", "datasets_requested", "n_written", "n_failed",
        "partially_conformant")})
    log_path.write_text(json.dumps(log, indent=2, default=str) + "\n",
                        encoding="utf-8")
    return record


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("segment", type=Path,
                    help="a segment directory, e.g. work/replay_2015_2026/2015")
    ap.add_argument("datasets", nargs="+", help="dataset ids, e.g. D24")
    ap.add_argument("--dry-run", action="store_true",
                    help="say what would move and what would run; write nothing")
    ap.add_argument("--force-unfinished", action="store_true",
                    help="export a segment with no DONE.json (know why first)")
    args = ap.parse_args(argv)

    ids = [d.upper() for d in args.datasets]
    rec = catchup(args.segment, ids, dry_run=args.dry_run,
                  force_unfinished=args.force_unfinished)
    print(json.dumps(rec, indent=2, default=str))
    return 1 if rec.get("n_failed") else 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONHASHSEED", "0")
    raise SystemExit(main())
