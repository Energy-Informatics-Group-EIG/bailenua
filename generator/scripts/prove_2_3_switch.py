#!/usr/bin/env python3
"""Prove that switching on D18 era gating changes D18 and nothing else.

The claim being proved
----------------------
Phase 12 adds per-home observability eras (``baile_nua/observation/era.py``):
no D18 before a home's smart-meter install date, 30-minute import and export
until its PARA//EL enrolment date, the full 1-minute device mix from enrolment.
The replay's 2015-2018 segments are already on disk and were produced by the
engine as it stood. Turning the gate on at the 2019 boundary is only safe if it
touches **D18 alone**: if it also perturbed D10, D11, D13, D16, D17, D17_aggregate
or D19, then the 2019 package would not be a continuation of the 2018 one, and
the chain's whole point - one town, one seed, one continuous history - would be
quietly broken.

"Should not" is not a proof. This script measures it.

What it does
------------
1. restores a checkpoint (by default the final checkpoint of the 2018 segment);
2. runs **one simulated day** from it with ``d18_era_gating=True``;
3. runs the **same** day from the **same** checkpoint with
   ``d18_era_gating=False``, which is the engine's existing behaviour;
4. compares every file of both packages **byte for byte**, ignoring D18;
5. exits **non-zero** on any difference, and prints each one.

Exit codes, which are the whole interface for an unattended run:

====  ========================================================================
0     every non-D18 dataset is byte-identical AND D18 differs: safe to switch
1     a non-D18 difference: do NOT switch; both packages are kept for inspection
2     non-D18 matches but D18 is identical too, so the gate did not engage and
      the run proves nothing: do NOT switch
3     the proof could not be run - no 2018 checkpoint, or its chain does not
      verify. Not a failure of the gate; the absence of a proof.
====  ========================================================================

Both arms set ``omit_datasets=frozenset()`` rather than the replay's
``["D18"]``: the point is to write D18 in the gated arm, and a dataset that is
not written cannot be compared.

Byte for byte, not row counts and not content hashes. ``io.write_dataset`` is
configured for determinism - no writer version in the footer, fixed row-group
size - so two identical runs produce identical files, and anything short of
identical bytes would leave room for a difference that a summary statistic
happens not to see. When bytes do differ the script reports whether the
manifests' ``content_hash_sha256`` differ too, which separates "the rows
changed" from "only the encoding did".

Running it
----------
The 2018 final checkpoint does not exist until the replay reaches it (about 16
October 2026, 12:47, at the measured 96.1 s/day). Until then this script cannot
run end to end, which is why its
comparison logic is a separate, importable function with its own tests in
``scripts/tests/test_d18_era_gating.py``.

    scripts/.venv/bin/python scripts/prove_2_3_switch.py \
        --checkpoint-root work/replay_2015_2026/2018/ckpt

Add ``--baseline <dir>`` to compare against an existing ungated package instead
of producing one, which halves the run time when a suitable one is to hand.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Iterable

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
sys.path.insert(0, str(HERE))

#: The datasets whose bytes this proof deliberately does not compare. D18 is
#: the dataset the change exists to alter; everything else must be identical.
DEFAULT_IGNORE = frozenset({"D18"})

#: The replay's own parameters, so the proof runs the same engine
#: configuration the segments did (scripts/replay_config.json).
REPLAY_CONFIG = HERE / "replay_config.json"


# --------------------------------------------------------------------------- #
# the comparison - the part that is testable without a 2018 checkpoint
# --------------------------------------------------------------------------- #

@dataclasses.dataclass(frozen=True)
class Difference:
    """One way in which two packages are not the same."""

    kind: str          # "only_in_a" | "only_in_b" | "size" | "bytes"
    relpath: str
    dataset: str | None
    detail: str

    def __str__(self) -> str:
        ds = self.dataset or "-"
        return f"{self.kind:10s} {ds:14s} {self.relpath}  {self.detail}"


def dataset_of(relpath: str) -> str | None:
    """The dataset id a package file belongs to, or ``None`` if it is not a part.

    Split on ``"_part"`` and not on the first underscore: ``D17_aggregate`` is a
    dataset id with an underscore in it, and splitting on that filed its files
    under ``D17``. ``StreamWriter.storage_report`` learned the same lesson.
    """
    name = Path(relpath).name
    if "_part" not in name:
        return None
    return name.split("_part")[0]


def package_files(root: Path) -> dict[str, Path]:
    """Every file under ``root``, keyed by path relative to it.

    Directories are not entries and empty directories are therefore invisible,
    which is correct: a package is its files.
    """
    root = Path(root)
    out: dict[str, Path] = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            out[str(p.relative_to(root))] = p
    return out


def _sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            b = fh.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _manifest_content_hash(path: Path) -> str | None:
    """``content_hash_sha256`` from the sidecar manifest of a Parquet part."""
    if path.suffix != ".parquet":
        return None
    sidecar = path.parent / f"{path.stem}.manifest.json"
    if not sidecar.exists():
        return None
    try:
        return json.loads(sidecar.read_text()).get("content_hash_sha256")
    except (ValueError, OSError):
        return None


#: Files that legitimately differ between two sequential runs, with the parts
#: allowed to differ. Compared as JSON with these pruned, rather than
#: byte-for-byte.
#:
#: Without this the proof CANNOT PASS - not for the engine under test, but for
#: any engine, including one compared against itself. `run_diagnostics.json`
#: carries wall-clock timings, the machine's free disk and the peak RSS, none
#: of which two sequential runs can match. The first real run of this script
#: reported FAIL on exactly these and on nothing else, while all six non-D18
#: Parquet datasets were byte-identical.
#:
#: Every entry is a subtree observed to differ in that run and justified here;
#: this is a list of what is allowed to vary, not a switch that turns the
#: comparison off. Dataset BYTES are still compared in full, so pruning
#: `benchmark/storage` loses no rigour - a dataset that changed size would
#: fail on its own file first.
VOLATILE_JSON: dict[str, tuple[tuple[str, ...], ...]] = {
    "run_diagnostics.json": (
        ("benchmark", "timings"),              # wall clock
        ("benchmark", "machine"),              # free/used disk, measured live
        ("benchmark", "storage"),              # includes D18's size: the intended change
        ("benchmark", "full_town_projection"), # derived from the timings above
        ("benchmark", "d18_era"),              # the era report the gated arm adds
        ("benchmark", "peak_rss_mb"),
        ("benchmark", "mean_s_per_day"),
        ("benchmark", "mean_total_s_per_day"),
        ("benchmark", "mean_write_s_per_day"),
        ("benchmark", "median_s_per_day"),
        ("benchmark", "p95_s_per_day"),
        ("benchmark", "ms_per_home_day"),
        ("benchmark", "ms_per_home_day_simulation_only"),
        ("benchmark", "write_share_of_runtime"),
        # The plausibility block is embedded here as well as in its own file,
        # and carries the arm's output directory. Pruning it only in
        # evidence/plausibility.json left this copy failing - the second time
        # this list was incomplete, and the second time the comparison caught
        # it rather than passing.
        ("plausibility", "package_root"),
    ),
    "evidence/plausibility.json": (
        ("package_root",),                     # the arm's own output directory
        ("plausibility", "package_root"),
    ),
}


def _prune(obj, paths):
    """A deep copy with `paths` removed, for comparing what should not vary."""
    import copy

    out = copy.deepcopy(obj)
    for path in paths:
        node = out
        for key in path[:-1]:
            if not isinstance(node, dict) or key not in node:
                node = None
                break
            node = node[key]
        if isinstance(node, dict):
            node.pop(path[-1], None)
    return out


def _volatile_json_matches(rel: str, pa: Path, pb: Path) -> bool | None:
    """True/False if `rel` is a known volatile JSON, else None."""
    spec = VOLATILE_JSON.get(rel)
    if spec is None:
        return None
    try:
        a = json.loads(pa.read_text(encoding="utf-8"))
        b = json.loads(pb.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return _prune(a, spec) == _prune(b, spec)


def compare_packages(
    a: Path, b: Path, *, ignore: Iterable[str] = DEFAULT_IGNORE,
) -> list[Difference]:
    """Byte-for-byte comparison of two written packages, ignoring some datasets.

    ``a`` is the candidate (the gated arm) and ``b`` the reference (the ungated
    arm); the ``only_in_*`` kinds are named from that side. A file whose name
    carries no ``_part`` - a package-level manifest, an evidence file - belongs
    to no dataset and is always compared, because ``ignore`` names datasets and
    not directories.

    Returns a list, empty when the two are identical. It returns rather than
    raises so that a caller can report every difference instead of the first.
    """
    skip = frozenset(ignore)
    fa, fb = package_files(a), package_files(b)
    diffs: list[Difference] = []
    for rel in sorted(set(fa) | set(fb)):
        ds = dataset_of(rel)
        if ds is not None and ds in skip:
            continue
        pa, pb = fa.get(rel), fb.get(rel)
        if pa is None:
            diffs.append(Difference("only_in_b", rel, ds, "absent from the candidate"))
            continue
        if pb is None:
            diffs.append(Difference("only_in_a", rel, ds, "absent from the reference"))
            continue
        verdict = _volatile_json_matches(rel, pa, pb)
        if verdict is True:
            continue
        if verdict is False:
            diffs.append(Difference(
                "bytes", rel, ds,
                "differs outside the fields a sequential run is allowed to "
                "vary (see VOLATILE_JSON)"))
            continue
        sa, sb = pa.stat().st_size, pb.stat().st_size
        if sa != sb:
            diffs.append(Difference(
                "size", rel, ds, f"{sa} bytes vs {sb}"))
            continue
        if _sha256(pa) != _sha256(pb):
            ha, hb = _manifest_content_hash(pa), _manifest_content_hash(pb)
            if ha is not None and hb is not None and ha == hb:
                detail = (
                    "bytes differ but the manifests' content_hash_sha256 "
                    "agrees, so the ROWS are the same and only the encoding "
                    "moved - still a difference, and still a failure"
                )
            else:
                detail = (
                    f"bytes differ; content_hash {str(ha)[:16]} vs {str(hb)[:16]}"
                )
            diffs.append(Difference("bytes", rel, ds, detail))
    return diffs


# --------------------------------------------------------------------------- #
# the run
# --------------------------------------------------------------------------- #

def _final_checkpoint(ckpt_root: Path):
    from baile_nua.checkpoint import CheckpointStore

    store = CheckpointStore(ckpt_root)
    days = sorted(
        int(p.name.split("_")[1].split(".")[0])
        for p in Path(ckpt_root).glob("day_*.checkpoint.json.gz")
    )
    if not days:
        raise RuntimeError(
            f"no checkpoint under {ckpt_root}. The 2018 segment's checkpoints "
            f"do not exist until the replay reaches them; there is nothing to "
            f"restore and nothing to prove yet."
        )
    # Verified AFTER the existence check, so "the segment has not got here
    # yet" reports as that rather than as a broken chain.
    store.verify_chain()
    return store.get(days[-1])


def _run_one_day(
    *, cfg: dict, restore_from, out_root: Path, ckpt_root: Path,
    start: str, end: str, sim_day_offset: int, gated: bool,
) -> dict:
    import baile_nua.sources_registry  # noqa: F401
    from baile_nua.engine.e1_run import run_year

    out_root.mkdir(parents=True, exist_ok=True)
    ckpt_root.mkdir(parents=True, exist_ok=True)
    return run_year(
        master_seed=cfg["master_seed"],
        out_root=out_root,
        checkpoint_root=ckpt_root,
        slice_kind=cfg["slice_kind"],
        # Empty, NOT the replay's ["D18"]: the gated arm has to write D18 for
        # the gate to be exercised at all, and a dataset that is not written
        # cannot be compared.
        omit_datasets=frozenset(),
        solve_network=cfg["solve_network"],
        with_venues=cfg["with_venues"],
        year=int(start[:4]),
        start=start,
        end=end,
        sim_day_offset=sim_day_offset,
        restore_from=restore_from,
        d18_era_gating=gated,
        progress=lambda m: print(f"  [{'gated' if gated else 'ungated'}] {m}"),
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--checkpoint-root",
        default="work/replay_2015_2026/2018/ckpt",
        help="directory of the segment whose FINAL checkpoint is restored",
    )
    ap.add_argument(
        "--start", default="2019-01-01",
        help="the single day to simulate (the first day after the checkpoint)",
    )
    ap.add_argument(
        "--sim-day-offset", type=int, default=1492,
        help="the 2019 segment's sim_day_offset from replay_config.json",
    )
    ap.add_argument(
        "--out", default=None,
        help="working directory for the two packages (default: a temp dir "
             "under work/, kept so a difference can be inspected)",
    )
    ap.add_argument(
        "--baseline", default=None,
        help="an existing UNGATED package for this same day, to compare "
             "against instead of running the ungated arm",
    )
    ap.add_argument(
        "--keep", action="store_true",
        help="keep the packages even when they match (they are always kept "
             "when they do not)",
    )
    args = ap.parse_args(argv)

    cfg = json.loads(REPLAY_CONFIG.read_text())
    ckpt_root = (PROJECT / args.checkpoint_root
                 if not Path(args.checkpoint_root).is_absolute()
                 else Path(args.checkpoint_root))
    # A checkpoint that is missing or whose chain does not verify is NOT a
    # proof failure, and it must not be reported with the same exit code: 1
    # means "do not switch, the gate changed something it should not have",
    # and 3 means "the proof could not be run at all". Conflating them at a
    # boundary nobody is watching is how a switch gets made or skipped for the
    # wrong reason.
    try:
        restore_from = _final_checkpoint(ckpt_root)
    except SystemExit:
        raise
    except Exception as exc:
        print(f"CANNOT RUN: {type(exc).__name__}: {exc}")
        print("  The 2018 checkpoint must exist and its chain must verify "
              "before this proof means anything. Exit 3 is not a failure of "
              "the gate; it is the absence of a proof.")
        return 3
    print(f"restoring sim_day {restore_from.sim_day} from {ckpt_root}")

    work = Path(args.out) if args.out else (
        PROJECT / "work" / f"prove_2_3_switch_{restore_from.sim_day}"
    )
    gated_pkg = work / "gated" / "pkg"
    print(f"gated arm   -> {gated_pkg}")
    diag_gated = _run_one_day(
        cfg=cfg, restore_from=restore_from, out_root=gated_pkg,
        ckpt_root=work / "gated" / "ckpt", start=args.start, end=args.start,
        sim_day_offset=args.sim_day_offset, gated=True,
    )
    era = (diag_gated.get("benchmark") or {}).get("d18_era", {})
    print(f"  era report: {json.dumps(era)}")

    if args.baseline:
        ref_pkg = (Path(args.baseline) if Path(args.baseline).is_absolute()
                   else PROJECT / args.baseline)
        print(f"reference   <- {ref_pkg} (supplied)")
    else:
        ref_pkg = work / "ungated" / "pkg"
        print(f"ungated arm -> {ref_pkg}")
        _run_one_day(
            cfg=cfg, restore_from=restore_from, out_root=ref_pkg,
            ckpt_root=work / "ungated" / "ckpt", start=args.start,
            end=args.start, sim_day_offset=args.sim_day_offset, gated=False,
        )

    diffs = compare_packages(gated_pkg, ref_pkg, ignore=DEFAULT_IGNORE)
    files = {
        rel for rel in package_files(gated_pkg)
        if (dataset_of(rel) or "") not in DEFAULT_IGNORE
    }
    print()
    print(f"compared {len(files)} non-D18 files")
    if diffs:
        print(f"FAIL: {len(diffs)} difference(s). Era gating changed more "
              f"than D18.")
        for d in diffs:
            print(f"  {d}")
        print(f"\nboth packages kept under {work}")
        return 1
    # D18 itself must have CHANGED, or the gate did nothing and the proof is
    # vacuous: a run that writes the same D18 either way has not been gated.
    d18_gated = sorted(
        p for rel, p in package_files(gated_pkg).items()
        if dataset_of(rel) == "D18" and p.suffix == ".parquet"
    )
    d18_ref = sorted(
        p for rel, p in package_files(ref_pkg).items()
        if dataset_of(rel) == "D18" and p.suffix == ".parquet"
    )
    same_d18 = (
        len(d18_gated) == len(d18_ref)
        and all(_sha256(x) == _sha256(y) for x, y in zip(d18_gated, d18_ref))
    )
    if same_d18 and d18_ref:
        print("FAIL: every non-D18 dataset matches, but D18 is identical too. "
              "The gate did not engage, so this run proves nothing.")
        print(f"both packages kept under {work}")
        return 2
    print("PASS: every non-D18 dataset is byte-identical, and D18 differs.")
    if not args.keep:
        shutil.rmtree(work, ignore_errors=True)
        print(f"removed {work}")
    else:
        print(f"kept {work}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
