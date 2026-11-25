#!/usr/bin/env python3
"""Supervisor for the chained 2015-2026 historical replay.

A plain Python process. Nothing in here calls out to anything; it is meant to
be started by launchd and left alone for about five days.

What it does, in order, for each segment of `replay_config.json`:

  1. skip the segment if its DONE sentinel exists (idempotent restart);
  2. restore the previous segment's final checkpoint, after verifying the
     recorded hash chain - a corrupt chain stops the run rather than seeding
     the next year from a state nobody can vouch for;
  3. simulate the segment, checkpointing every day (finer than the monthly
     requirement, and it is what `EstateRunner` already does);
  4. run the year's checks, build its package, scan it for secrets and personal
     data, and only then write DONE;
  5. on failure, retry from the last checkpoint up to twice, then write
     status/BLOCKED.md and exit cleanly.

Design notes that matter:

* **One master seed throughout** (D-133). A per-year seed would give a
  different town each year and destroy the cohort continuity the replay exists
  for. A per-year `seed_of_record` is written into each manifest for provenance
  and is never passed to the model.
* **`sim_day` is continuous 0..4290** (D-110), because the seed tree is keyed
  on it; restarting at zero each year would re-draw an earlier year's numbers.
  The warm-up sits at negative sim_day so it cannot collide.
* **The warm-up's output is discarded, its state is carried.** It is burn-in
  for thermal mass, tanks and SOC; nothing from December 2014 is published.
* **B2 upload is a separate, skipped step** (D-125): no credential exists and
  rotation is unconfirmed. Packages are built and verified locally.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import resource
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
sys.path.insert(0, str(HERE))

CONFIG = HERE / os.environ.get("REPLAY_CONFIG", "replay_config.json")
STATUS = PROJECT / "status"
PROGRESS_EVERY_S = 600


# --------------------------------------------------------------------------- #
# status
# --------------------------------------------------------------------------- #

def _now() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def write_last(line: str) -> None:
    STATUS.mkdir(parents=True, exist_ok=True)
    (STATUS / "LAST.txt").write_text(f"{_now()}  {line}\n")


def write_progress(cfg: dict, state: dict) -> None:
    STATUS.mkdir(parents=True, exist_ok=True)
    segs = cfg["segments"]
    done = [s["name"] for s in segs if state["done"].get(s["name"])]
    cur = state.get("current")
    lines = [
        "# Replay — live status",
        "",
        f"Updated **{_now()}**. Written by `scripts/replay_supervisor.py`; do not hand-edit.",
        "",
        "| | |",
        "|---|---|",
        f"| Run | `{cfg['label']}` |",
        f"| Engine | {state.get('engine_tag','?')} code `{state.get('code_digest','?')[:16]}…` |",
        f"| Segments done | **{len(done)} of {len(segs)}** |",
        f"| Current | {cur or '—'} |",
        f"| Day | {state.get('day_in_seg','—')} of {state.get('days_in_seg','—')} |",
        f"| Peak RSS | {state.get('peak_rss_mb','—')} MB (gate {cfg['rss_gate_mb']} MB) |",
        f"| Last checkpoint | {state.get('last_ckpt','—')} |",
        f"| Errors | {state.get('errors') or 'none'} |",
        "",
        "## Per segment",
        "",
        "| segment | days | status | wall | ETA / finished |",
        "|---|---|---|---|---|",
    ]
    for s in segs:
        n = s["_days"]
        st = state["done"].get(s["name"])
        if st:
            lines.append(f"| {s['name']} | {n} | **DONE** | {st.get('wall_h','?')} h | {st.get('finished','?')} |")
        elif s["name"] == cur:
            d = state.get("day_in_seg") or 0
            pct = 100.0 * d / n if n else 0
            rate = state.get("s_per_day") or 103.0
            eta = dt.datetime.now() + dt.timedelta(seconds=(n - d) * rate)
            lines.append(f"| {s['name']} | {n} | running **{pct:.1f}%** | — | {eta:%d %b %H:%M} |")
        else:
            lines.append(f"| {s['name']} | {n} | pending | — | — |")
    rate = state.get("s_per_day") or 103.0
    remaining = sum(s["_days"] for s in segs if not state["done"].get(s["name"]))
    lines += ["", f"Remaining {remaining} simulated days at {rate:.0f} s/day "
              f"≈ **{remaining*rate/3600:.1f} h**.", "",
              "B2 upload is a separate, skipped step (D-125): no credential, "
              "rotation unconfirmed. Packages are local only.", ""]
    (STATUS / "PROGRESS.md").write_text("\n".join(lines))


def write_blocked(seg: str, err: str, tb: str) -> None:
    STATUS.mkdir(parents=True, exist_ok=True)
    (STATUS / "BLOCKED.md").write_text(
        f"# BLOCKED — {_now()}\n\n"
        f"Segment **{seg}** failed three times (initial attempt plus two "
        f"retries from its last checkpoint) and the supervisor has stopped "
        f"cleanly. Nothing was deleted; the segment's checkpoints are intact "
        f"and a fixed run resumes from them.\n\n"
        f"## Error\n\n```\n{err}\n```\n\n## Traceback\n\n```\n{tb}\n```\n\n"
        f"## To resume\n\n"
        f"Fix the cause, remove this file, and the launchd agent restarts the "
        f"supervisor on its next keep-alive cycle. Completed segments are "
        f"skipped by their DONE sentinels.\n"
    )


# --------------------------------------------------------------------------- #
# checks
# --------------------------------------------------------------------------- #

SECRET_PATTERNS = [
    re.compile(r"(?i)\b(api[_-]?key|apikey|secret|password|passwd|token|"
               r"access[_-]?key|auth[_-]?token)\b\s*[=:]\s*\S{6,}"),
    re.compile(r"\b(AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{20,}|"
               r"sk-[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{10,})"),
    re.compile(r"://[^/\s:]+:[^/\s@]+@"),
]
#: Identity-bearing column names that must not appear in an OBSERVABLE part.
PERSONAL_IN_OBS = ("person_id", "birth_date", "ppsn", "eircode", "email", "phone")


def scan_package(pkg: Path) -> dict:
    """Secrets in any text file; identity-bearing columns in observable parts."""
    import pyarrow.parquet as pq
    hits: list[str] = []
    for p in sorted(pkg.rglob("*")):
        if not p.is_file():
            continue
        if p.suffix in (".json", ".md", ".txt", ".csv"):
            try:
                t = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for rx in SECRET_PATTERNS:
                if rx.search(t):
                    hits.append(f"secret-pattern in {p.relative_to(pkg)}")
                    break
        if p.suffix == ".parquet" and "observable" in p.parts:
            try:
                names = set(pq.ParquetFile(p).schema_arrow.names)
            except Exception:
                continue
            bad = sorted(names & set(PERSONAL_IN_OBS))
            if bad:
                hits.append(f"identity columns {bad} in observable {p.name}")
    return {"clean": not hits, "hits": hits}


def prepare_evidence_package(pkg: Path) -> dict:
    """Make ``<pkg>/evidence/`` exist and PROVE the export can write into it.

    D22, D23 and D24 are META, and :func:`baile_nua.io.write_dataset` refuses
    to place a META dataset anywhere but ``<out_root>/evidence/``.  The
    directory alone is not the permission: a read-only or full volume creates
    the same shape and fails at the first write, and the export layer would
    then record three datasets as "failed" with an errno for a reason.

    So the directory is created and a probe file is written and removed, and
    what happened is RETURNED rather than raised.  Raising here would lose a
    ten-hour year to a directory permission, which is the same judgement
    D-138 already made about a per-dataset failure: the year is recorded with
    the finding on it, not abandoned.
    """
    out = {"path": str(pkg / "evidence"),
           "needed_by": ["D22", "D23", "D24"],
           "created": False, "writable": False, "error": None}
    try:
        (pkg / "evidence").mkdir(parents=True, exist_ok=True)
        out["created"] = True
        probe = pkg / "evidence" / ".write_probe"
        probe.write_text("probe\n", encoding="utf-8")
        probe.unlink()
        out["writable"] = True
    except OSError as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"
    return out


def check_year(pkg: Path, diag: dict, days: int, rss_gate_mb: int) -> dict:
    """Row counts, no NaN, invariants, RSS. Returns {ok, failures, counts}."""
    import pyarrow.parquet as pq
    import math
    fails: list[str] = []
    counts: dict[str, int] = {}
    for p in sorted(pkg.rglob("*.parquet")):
        ds = p.name.split("_part")[0]
        try:
            f = pq.ParquetFile(p)
        except Exception as exc:
            fails.append(f"{p.name} unreadable: {exc}")
            continue
        counts[ds] = counts.get(ds, 0) + f.metadata.num_rows
        if f.metadata.num_rows == 0:
            fails.append(f"{p.name} has zero rows")
    if not counts:
        fails.append("the package contains no Parquet parts at all")
    bench = diag.get("benchmark", {})
    n_days = bench.get("n_days")
    if n_days not in (None, days):
        fails.append(f"diagnostics say {n_days} days, the segment is {days}")
    peak = bench.get("peak_rss_mb")
    if peak and peak > rss_gate_mb:
        fails.append(f"peak RSS {peak} MB exceeds the {rss_gate_mb} MB gate")
    for key in ("max_physics_relative_residual",
                "max_energy_closure_relative_residual"):
        v = diag.get(key)
        if v is None:
            continue
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            fails.append(f"{key} is {v}")
    plaus = diag.get("plausibility") or {}
    if isinstance(plaus, dict):
        nf = plaus.get("n_fail")
        if nf:
            fails.append(f"plausibility reports {nf} failures")
    return {"ok": not fails, "failures": fails, "counts": counts,
            "peak_rss_mb": peak}


# --------------------------------------------------------------------------- #
# the run
# --------------------------------------------------------------------------- #

def _current_rss_mb() -> float:
    """This process's CURRENT resident set, in MB.

    macOS has no /proc and psutil is not installed, so ask `ps`. Returns 0.0 if
    that fails, which deliberately cannot trip the gate: losing the gate for one
    cycle is recoverable, aborting a ten-hour segment because `ps` hiccuped is
    not. The peak figure alongside it still records what the run demanded.
    """
    try:
        out = subprocess.run(
            ["/bin/ps", "-o", "rss=", "-p", str(os.getpid())],
            capture_output=True, text=True, timeout=10)
        return int(out.stdout.strip()) / 1024.0
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0.0


def digests() -> tuple[str, str]:
    def d(pats):
        root = HERE / "baile_nua"
        files: list[Path] = []
        for p in pats:
            files.extend(root.rglob(p))
        o = hashlib.sha256()
        for f in sorted(files, key=lambda q: str(q)):
            o.update(f"{hashlib.sha256(f.read_bytes()).hexdigest()}  "
                     f"{f.relative_to(root)}\n".encode())
        return o.hexdigest()
    return d(("*.py",)), d(("*.yaml", "*.yml", "*.json"))


def run_segment(cfg: dict, seg: dict, state: dict, restore_from):
    import baile_nua.sources_registry  # noqa: F401
    from baile_nua.checkpoint import CheckpointStore
    from baile_nua.engine.e1_run import run_year

    out_root = PROJECT / cfg["out_root"] / seg["name"]
    # An incomplete segment is RENAMED ASIDE before it is re-run, never written
    # into. `StreamWriter` numbers its Parquet parts from zero, so re-running
    # into a dirty directory leaves the previous attempt's higher-numbered
    # parts behind and the package silently contains two attempts. This is the
    # hazard the decade scheduler guarded the same way - renamed aside, never
    # removed - and the reason it is safe to retry at all.
    if out_root.exists() and not (out_root / "DONE.json").exists():
        aside = out_root.with_name(f"{seg['name']}.partial.{int(time.time())}")
        out_root.rename(aside)
        with (PROJECT / cfg["out_root"] / "retries.log").open("a", buffering=1) as fh:
            fh.write(f"{_now()}  {seg['name']}: incomplete attempt renamed to "
                     f"{aside.name} (never deleted)\n")
    pkg = out_root / "pkg"
    ckpt = out_root / "ckpt"
    pkg.mkdir(parents=True, exist_ok=True)
    ckpt.mkdir(parents=True, exist_ok=True)

    state["current"] = seg["name"]
    state["days_in_seg"] = seg["_days"]
    state["day_in_seg"] = 0
    t0 = time.time()
    last_write = [0.0]

    def progress(msg: str) -> None:
        m = re.search(r"day (\d+)/(\d+)", msg)
        if m:
            # The engine reports the ABSOLUTE sim_day, which in a chained
            # segment is offset, so "day 21/7" is day 7 of a 7-day segment.
            # Subtracting the offset keeps the percentage honest.
            state["day_in_seg"] = int(m.group(1)) - seg["sim_day_offset"]
            el = time.time() - t0
            # Divide by days done IN THIS SEGMENT, not by the absolute sim_day
            # (I-112). The numerator is this segment's elapsed time, so an
            # absolute denominator - which counts every day of every prior
            # year - understated the rate 2.15x in 2015 and would have
            # understated it ~15.8x by 2026. Measured truth was 96.1 s/day
            # against a reported 60.
            state["s_per_day"] = el / max(state["day_in_seg"], 1)
        # The gate is on CURRENT resident memory; the PEAK is reported but
        # never gates (I-116).
        #
        # `ru_maxrss` is a monotone high-water mark: it only ever rises, and it
        # keeps rising because each 30-day flush spikes higher than the last.
        # Gating on it means a single historical spike aborts the segment and
        # every retry of it, forever, while the process sits at half a
        # gigabyte - measured: peak 11,938 MB against a current RSS of 0.47 GB.
        # That is a time bomb, not a guard: it fires once and then always.
        #
        # Current RSS is the live condition and the one worth acting on. Peak
        # is still recorded, because it is the only evidence of what the run
        # actually demanded, and it is what I-113 relies on to catch a spike
        # between two 30-day checks.
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6
        state["peak_rss_mb"] = round(peak, 1)
        state["rss_mb"] = round(_current_rss_mb(), 1)
        # A WARNING well below the gate, so accumulation is visible while it
        # is still cheap to investigate (I-118). Last night the only signal
        # that anything was accumulating was the gate figure creeping toward
        # its own limit, which is far too late to be useful - by then the
        # question is whether to abandon a ten-hour year.
        warn_mb = float(cfg.get("rss_warn_mb", 8192))
        if state["rss_mb"] > warn_mb and not state.get("_warned_rss"):
            state["_warned_rss"] = True
            with (out_root / "progress.log").open("a", buffering=1) as fh:
                fh.write(f"[{_now()}] WARNING current RSS "
                         f"{state['rss_mb']:.0f} MB passed the "
                         f"{warn_mb:.0f} MB warning mark (gate "
                         f"{cfg['rss_gate_mb']} MB, machine has 32 GB)\n")
        if state["rss_mb"] > cfg["rss_gate_mb"]:
            raise MemoryError(
                f"current RSS {state['rss_mb']:.0f} MB exceeded the "
                f"{cfg['rss_gate_mb']} MB gate during {seg['name']} "
                f"(peak so far {peak:.0f} MB)")
        with (out_root / "progress.log").open("a", buffering=1) as fh:
            fh.write(f"[{_now()}] {msg}\n")
        if time.time() - last_write[0] > PROGRESS_EVERY_S:
            last_write[0] = time.time()
            write_progress(cfg, state)
            write_last(f"{seg['name']} day {state['day_in_seg']}/{seg['_days']} "
                       f"RSS {state['peak_rss_mb']} MB")

    diag = run_year(
        master_seed=cfg["master_seed"],
        out_root=pkg,
        checkpoint_root=ckpt,
        slice_kind=cfg["slice_kind"],
        progress=progress,
        write_package=not seg["discard_output"],
        omit_datasets=frozenset(cfg["omit_datasets"]),
        solve_network=cfg["solve_network"],
        with_venues=cfg["with_venues"],
        year=seg["year"],
        start=seg["start"],
        end=seg["end"],
        sim_day_offset=seg["sim_day_offset"],
        # `run_day(collect_presence=day.sim_day < collect_presence_days)` tests
        # the GLOBAL sim_day against a default of 14. Every delivered segment
        # starts at offset 31 or later, so the default collected presence on no
        # day of any delivered year, and D29/D30 - which glob D11 for
        # `location_kind == "building"` and raise when there is none - would
        # have failed in all twelve. Offsetting it keeps the original intent:
        # the first 14 days of each segment.
        #
        # Safe to change mid-run: `collect_presence` is a RETENTION flag.
        # `engine/run.py:500-511` records that `_venue_for` is addressed
        # through the counter-based seed tree on a (person, day, activity) key
        # of its own, so resolving it every day "advances no other stream and
        # changes no other draw". Row volume changes; no draw does.
        collect_presence_days=seg["sim_day_offset"] + 14,
        restore_from=restore_from,
        # Phase 12. Per-home D18 observability eras (docs/D18_ERA_GATING.md).
        # Read from the config with a False default, so the supervisor behaves
        # exactly as it did until the config says otherwise - the switch at the
        # 2019 boundary is then a config edit and not a code edit made under
        # time pressure. Gated against the byte-for-byte proof in
        # scripts/prove_2_3_switch.py, which must exit 0 first.
        d18_era_gating=bool(cfg.get("d18_era_gating", False)),
    )
    wall = time.time() - t0
    # `verify_chain` returns None and RAISES ChainError at the first broken
    # link, so "no exception" is the pass. Treating its return value as a
    # verdict would have read None as falsey and reported every clean chain as
    # a failure.
    CheckpointStore(ckpt).verify_chain()
    state["last_ckpt"] = str(ckpt)
    return diag, wall, "chain verified"


def final_checkpoint(cfg: dict, seg: dict):
    """The last checkpoint of a segment, after verifying the recorded chain."""
    from baile_nua.checkpoint import CheckpointStore
    ckpt = PROJECT / cfg["out_root"] / seg["name"] / "ckpt"
    if not ckpt.exists():
        return None
    store = CheckpointStore(ckpt)
    try:
        store.verify_chain()
    except Exception as exc:
        raise RuntimeError(
            f"the checkpoint chain for {seg['name']} does not verify: {exc}. "
            f"Refusing to seed the next segment from a state nobody can vouch "
            f"for."
        ) from exc
    days = sorted(int(p.name.split("_")[1].split(".")[0])
                  for p in ckpt.glob("day_*.checkpoint.json.gz"))
    return store.get(days[-1]) if days else None


def main(only: str | None = None) -> int:
    """Run segments. With `only`, run exactly that one segment and return.

    The `only` path is the CHILD of the per-year subprocess arrangement
    (D-148). It reuses this function unchanged rather than duplicating the
    skip-if-DONE, restore-from-previous, export and sentinel logic, because a
    second copy of that would drift from this one.
    """
    cfg = json.loads(CONFIG.read_text())
    for s in cfg["segments"]:
        a = dt.date.fromisoformat(s["start"]); b = dt.date.fromisoformat(s["end"])
        s["_days"] = (b - a).days + 1
    code, conf = digests()
    state = {"done": {}, "errors": None, "code_digest": code,
             "engine_tag": os.environ.get("REPLAY_ENGINE_TAG", "v1-engine-freeze-2.2")}
    root = PROJECT / cfg["out_root"]
    root.mkdir(parents=True, exist_ok=True)
    (root / "RUN_DIGESTS.json").write_text(json.dumps(
        {"code_digest": code, "conf_digest": conf, "master_seed": cfg["master_seed"],
         "note": "one master seed throughout (D-133); per-year seed_of_record is "
                 "provenance only and is never passed to the model"}, indent=2) + "\n")

    for s in cfg["segments"]:
        sent = root / s["name"] / "DONE.json"
        if sent.exists():
            state["done"][s["name"]] = json.loads(sent.read_text())
    write_progress(cfg, state)

    prev = None
    for i, seg in enumerate(cfg["segments"]):
        if seg["name"] in state["done"]:
            prev = seg
            continue
        if only is not None and seg["name"] != only:
            # A child runs one year. Segments run in order and every earlier
            # one carries a DONE sentinel by the time this runs, so the first
            # not-done segment IS `only`; anything after it belongs to the
            # next child.
            break
        restore = final_checkpoint(cfg, prev) if prev is not None else None
        for attempt in range(3):
            try:
                write_last(f"{seg['name']} starting (attempt {attempt+1}/3)")
                diag, wall, verify = run_segment(cfg, seg, state, restore)
                pkgdir = root / seg["name"] / "pkg"

                # ---- engine identity, for D23 --------------------------
                # Written HERE, before the export, because D23 is built by the
                # export post-pass and the segment's DONE.json does not exist
                # until after it. A twelve-year chained replay does not run on
                # one engine - 2015 on freeze-2.2, later years on whatever the
                # supervisor was restarted with, and the D18 era gating turns
                # on at the 2019 boundary - so D23 must record the engine of
                # the year it describes rather than a constant.
                (root / seg["name"] / "ENGINE.json").write_text(json.dumps({
                    "segment": seg["name"],
                    "engine_tag": state.get("engine_tag"),
                    "code_digest": state.get("code_digest"),
                    "conf_digest": conf,
                    "d18_era_gating": bool(cfg.get("d18_era_gating", False)),
                    "written_before_export": True,
                }, indent=2) + "\n")

                # ---- per-year export post-pass -------------------------
                # run_year streams only what the ENGINE writes; every other
                # dataset comes from the export layer, which reads a FINISHED
                # run root. Without this a year held 7 datasets, not ~26.
                #
                # relocate={} because the replay's own life course produces
                # D03/D09/D20 - there is no separate wp5_decade run to file
                # them under, which is what the registry assumes (I-103).
                if not seg["discard_output"]:
                    from baile_nua.export import export_all
                    # D22, D23 and D24 are META and `io.write_dataset` refuses
                    # to place a META dataset anywhere but <out_root>/evidence/.
                    # Creating the directory is not enough to know the export
                    # can use it - the year's package may sit on a full or
                    # read-only volume - so it is PROVED with a probe write,
                    # and the proof travels in the export report.
                    evidence = prepare_evidence_package(pkgdir)
                    rep = export_all(pkgdir, pkgdir, relocate={},
                                     run_name=f"replay {seg['name']}")
                    rep["evidence_package"] = evidence
                    rep["partially_conformant"] = {
                        d: r.get("null_required_fields")
                        for d, r in (rep.get("datasets") or {}).items()
                        if r.get("null_required_fields")
                    }
                    (root / seg["name"] / "export_report.json").write_text(
                        json.dumps(rep, indent=2, default=str) + "\n")
                    # A failed or absent dataset is a FINDING, recorded on the
                    # year, not a crash. Raising here would block a 10-hour
                    # year over one dataset whose inputs this configuration
                    # never produced - which is how D29/D30 behave without a
                    # D11 part, and how D03/D09/D20 behave without a life-
                    # course artefact. The year's DONE.json carries the list so
                    # nothing is silently missing.
                    state["exported"] = rep["n_written"]
                    state["export_failed"] = rep.get("n_failed", 0)
                if seg["discard_output"]:
                    res = {"ok": True, "failures": [], "counts": {},
                           "peak_rss_mb": state.get("peak_rss_mb")}
                    scan = {"clean": True, "hits": []}
                else:
                    res = check_year(pkgdir, diag, seg["_days"], cfg["rss_gate_mb"])
                    scan = scan_package(pkgdir)
                if not res["ok"]:
                    raise RuntimeError("year checks failed: " + "; ".join(res["failures"]))
                if not scan["clean"]:
                    raise RuntimeError("secret/personal scan failed: " + "; ".join(scan["hits"]))
                rec = {
                    "segment": seg["name"], "days": seg["_days"],
                    "sim_day": [seg["sim_day_offset"], seg["sim_day_offset"] + seg["_days"] - 1],
                    "wall_h": round(wall / 3600, 2),
                    "s_per_day": round(wall / seg["_days"], 1),
                    "peak_rss_mb": res.get("peak_rss_mb") or state.get("peak_rss_mb"),
                    "row_counts": res["counts"], "chain_verify": str(verify),
                    "export_written": state.get("exported"),
                    "export_failed": state.get("export_failed"),
                    "scan": scan, "discarded": seg["discard_output"],
                    "finished": _now(),
                    "code_digest": code, "conf_digest": conf,
                    "master_seed": cfg["master_seed"],
                    "seed_of_record": hashlib.sha256(
                        f"{cfg['master_seed']}:{seg['year']}".encode()).hexdigest()[:16],
                    "seed_of_record_note": "provenance only; NOT passed to the model (D-133)",
                    "b2_upload": "SKIPPED - no credential, rotation unconfirmed (D-125)",
                    "provisional": True,
                }
                (root / seg["name"] / "DONE.json").write_text(json.dumps(rec, indent=2) + "\n")
                state["done"][seg["name"]] = rec
                state["current"] = None
                write_progress(cfg, state)
                write_last(f"{seg['name']} DONE in {rec['wall_h']} h, "
                           f"{rec['s_per_day']} s/day, peak {rec['peak_rss_mb']} MB")
                prev = seg
                break
            except Exception as exc:
                tb = traceback.format_exc()
                state["errors"] = f"{seg['name']} attempt {attempt+1}: {exc}"
                write_progress(cfg, state)
                write_last(f"{seg['name']} FAILED attempt {attempt+1}/3: {exc}")
                with (root / "errors.log").open("a", buffering=1) as fh:
                    fh.write(f"\n==== {_now()} {seg['name']} attempt {attempt+1}\n{tb}\n")
                if attempt == 2:
                    write_blocked(seg["name"], str(exc), tb)
                    return 1
                try:
                    restore = final_checkpoint(cfg, prev) if prev is not None else None
                except Exception:
                    restore = None
                time.sleep(20)
    write_last("ALL SEGMENTS DONE")
    write_progress(cfg, state)
    return 0


def supervise() -> int:
    """Run each year as a FRESH SUBPROCESS, restored from the year before.

    Why (D-148): every segment used to run in one long-lived process, so
    `ru_maxrss` never reset at a year boundary and any per-day accumulation
    compounded across all twelve years - which is how I-117's 4.15 GB of
    retained power-flow dicts took the gate to 88% of its budget. Fixing that
    one accumulator helps; making the process boundary coincide with the year
    boundary means the NEXT one cannot compound either, whether or not anybody
    finds it.

    Digest-neutral by construction: nothing under `scripts/baile_nua` changes,
    and `digests()` covers only that tree. The child restores from the previous
    year's verified checkpoint through exactly the same `final_checkpoint` ->
    `run_year(restore_from=...)` path the in-process version used, so the
    simulation it performs is the same one.

    The contract between parent and child is `DONE.json` on disk, which the
    child already wrote. The parent reads it back rather than returning a
    value through the process boundary.
    """
    cfg = json.loads(CONFIG.read_text())
    for sg in cfg["segments"]:
        a = dt.date.fromisoformat(sg["start"]); b = dt.date.fromisoformat(sg["end"])
        sg["_days"] = (b - a).days + 1
    root = PROJECT / cfg["out_root"]
    root.mkdir(parents=True, exist_ok=True)

    for seg in cfg["segments"]:
        sent = root / seg["name"] / "DONE.json"
        if sent.exists():
            continue
        ok = False
        for attempt in range(3):
            write_last(f"{seg['name']} spawning child (attempt {attempt+1}/3)")
            with (root / "children.log").open("a", buffering=1) as fh:
                fh.write(f"{_now()}  {seg['name']} attempt {attempt+1}: spawning\n")
            proc = subprocess.run(
                [sys.executable, "-u", str(Path(__file__).resolve()),
                 "--only", seg["name"]],
                cwd=str(Path(__file__).resolve().parent))
            if proc.returncode == 0 and sent.exists():
                ok = True
                with (root / "children.log").open("a", buffering=1) as fh:
                    fh.write(f"{_now()}  {seg['name']}: child exited 0, sentinel "
                             f"present\n")
                break
            with (root / "children.log").open("a", buffering=1) as fh:
                fh.write(f"{_now()}  {seg['name']}: child exited "
                         f"{proc.returncode}, sentinel "
                         f"{'present' if sent.exists() else 'ABSENT'}\n")
            time.sleep(20)
        if not ok:
            # The child writes BLOCKED.md on its own third failure; this covers
            # the case where it died without getting that far - killed, OOM,
            # or an exception outside its own handler.
            if not (PROJECT / "status" / "BLOCKED.md").exists():
                write_blocked(seg["name"],
                              f"child process failed three times, last exit "
                              f"{proc.returncode}",
                              "see work/replay_2015_2026/children.log and "
                              "errors.log")
            return 1
    write_last("ALL SEGMENTS DONE")
    return 0


if __name__ == "__main__":
    if "--only" in sys.argv:
        raise SystemExit(main(only=sys.argv[sys.argv.index("--only") + 1]))
    if "--in-process" in sys.argv:
        # The old single-process behaviour, kept for the kill/resume proof and
        # for comparing the two arrangements.
        raise SystemExit(main())
    raise SystemExit(supervise())
