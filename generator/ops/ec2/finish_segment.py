#!/usr/bin/env python3
"""Finish a segment whose SIMULATION completed but whose post-pass did not.

    finish_segment.py <segment>            do it
    finish_segment.py <segment> --check    exit 0 if the segment qualifies, 3 if not

Run by ops/pre_start.sh before the supervisor starts, so a crash in the
post-run phases (U27 plausibility, export post-pass, year checks) does not make
the supervisor rename the year aside and re-simulate it from day 0.

A segment qualifies only if ALL of these hold - otherwise it is left exactly as
it is and the supervisor's own D-135 behaviour (rename aside, re-run the
segment) applies:
  * no DONE.json
  * pkg/run_diagnostics.json exists and its benchmark.n_days equals the
    segment's day count (run_year writes it only after the last day, after the
    final flush)
  * one checkpoint per day, contiguous from the segment's offset, and the
    recorded chain verifies

The steps are the ones run_year and replay_supervisor.main run after the last
day, in the same order and through the same functions, so the package is the
one an uninterrupted run writes. Nothing here re-simulates and nothing is
deleted. No change to scripts/baile_nua or the replay config.

The one difference from run_year: a PL-TEMP-01 failure inside TEMP_OVERRIDE's
bounds is accepted and recorded in DONE.json (u27_accepted_exceedances), where
run_year would raise. From 2020 that is how such a year gets finished: the child
raises, the watchdog restores the finished attempt, and this script completes it.
Likewise, for 2023-2026 a check_year peak-RSS gate failure up to RSS_OVERRIDE's
40 GB is accepted and recorded (rss_gate_exception).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import sys
import time
from pathlib import Path

HRSD = Path("/home/ubuntu/hrsd_occupants/hrsd")
SCRIPTS = HRSD / "scripts"
sys.path.insert(0, str(SCRIPTS))
os.chdir(SCRIPTS)

import replay_supervisor as sup  # noqa: E402  (digests, check_year, scan_package, ...)


def _seg(cfg: dict, name: str) -> dict:
    for s in cfg["segments"]:
        a = dt.date.fromisoformat(s["start"]); b = dt.date.fromisoformat(s["end"])
        s["_days"] = (b - a).days + 1
    return next(s for s in cfg["segments"] if s["name"] == name)


def qualifies(cfg: dict, seg: dict) -> tuple[bool, str]:
    root = sup.PROJECT / cfg["out_root"] / seg["name"]
    if not root.is_dir():
        return False, "no segment directory"
    if (root / "DONE.json").exists():
        return False, "already DONE"
    dpath = root / "pkg" / "run_diagnostics.json"
    if not dpath.is_file():
        return False, "no run_diagnostics.json: the simulation did not finish"
    try:
        n = json.loads(dpath.read_text())["benchmark"]["n_days"]
    except Exception as exc:
        return False, f"run_diagnostics.json unreadable: {exc}"
    if n != seg["_days"]:
        return False, f"diagnostics say {n} days, the segment is {seg['_days']}"
    days = sorted(int(p.name.split("_")[1].split(".")[0])
                  for p in (root / "ckpt").glob("day_*.checkpoint.json.gz"))
    want = list(range(seg["sim_day_offset"], seg["sim_day_offset"] + seg["_days"]))
    if days != want:
        return False, f"checkpoints {len(days)} not contiguous {want[0]}..{want[-1]}"
    from baile_nua.checkpoint import CheckpointStore
    try:
        CheckpointStore(root / "ckpt").verify_chain()
    except Exception as exc:
        return False, f"checkpoint chain does not verify: {exc}"
    return True, "simulation complete, post-pass incomplete"


# ---- accepted U27 exceedance (ops-only override, approved by Brian 2026-10-17) --
# PL-TEMP-01's 40 C indoor peak is a declared assumption with no published
# source. 2020 measured 41.15 C with a normal median and tail. From 2020 on, a
# PL-TEMP-01 FAIL is accepted, and recorded in DONE.json, only while ALL hold;
# outside them, or with any other check failing, the year still blocks.
TEMP_OVERRIDE = {
    "check_id": "PL-TEMP-01",
    "from_year": 2020,
    "max_peak_c": 45.0,
    # 2015-2019 measured medians 18.80, 18.97, 18.94, 19.01, 19.00, +/- 1 C
    "median_c": (17.80, 20.01),
    "max_share_above_28c": 0.005,
    "approved": "Brian O'Regan, 2026-10-17: accept and document",
    "ceiling_note": "40 C peak is an assumed ceiling [A], not from a published source",
}


# ---- peak-RSS gate exception (ops-only, approved by Brian 2026-10-18) ---------
# check_year fails a year whose simulation peak RSS exceeds rss_gate_mb (18432,
# frozen config). Peak RSS grows with the D18 full_1min home-days (2022 18.3 GB,
# 2023 23.7 GB), so every year from 2023 exceeds it. For 2023-2026 a gate failure
# is accepted, and recorded in DONE.json, only while the peak is <= 40 GB and it
# is the only failure. A v1 operational exception: no output is affected.
RSS_OVERRIDE = {
    "from_year": 2023, "to_year": 2026,
    "max_peak_mb": 40960,
    "approved": "Brian O'Regan, 2026-10-18: ops-only override, v1 operational exception",
    "note": "memory gate only; the simulation and its outputs are unaffected",
}


def rss_exception(year: int, res: dict, gate_mb: int) -> dict | None:
    """The DONE.json record if check_year's RSS failure is accepted, else None."""
    o = RSS_OVERRIDE
    peak = res.get("peak_rss_mb")
    msg = f"peak RSS {peak} MB exceeds the {gate_mb} MB gate"
    if (msg not in res["failures"] or not o["from_year"] <= year <= o["to_year"]
            or not isinstance(peak, (int, float)) or peak > o["max_peak_mb"]):
        return None
    return {"check": "replay_supervisor.check_year peak RSS gate", "peak_rss_mb": peak,
            "gate_mb": gate_mb, "accepted_max_mb": o["max_peak_mb"],
            "approved": o["approved"], "note": o["note"],
            "accepted_by": "~/hrsd_occupants/ops/finish_segment.py (ops-only; engine and config unchanged)"}


def accepted_exceedances(year: int, results: list[dict]) -> tuple[list[dict], list[str]]:
    """(accepted records, failures still blocking) for a U27 result list."""
    o = TEMP_OVERRIDE
    accepted, blocking = [], []
    for r in results:
        if r.get("outcome") != "FAIL":
            continue
        m = r.get("measured") or {}
        ok = (r["check_id"] == o["check_id"] and year >= o["from_year"]
              and isinstance(m.get("max_c"), (int, float)) and m["max_c"] <= o["max_peak_c"]
              and isinstance(m.get("median_c"), (int, float))
              and o["median_c"][0] <= m["median_c"] <= o["median_c"][1]
              and isinstance(m.get("share_above_28c"), (int, float))
              and m["share_above_28c"] <= o["max_share_above_28c"])
        if not ok:
            blocking.append(r["check_id"])
            continue
        accepted.append({
            "check_id": r["check_id"], "quantity": r.get("quantity"), "measured": m,
            "declared_band": r.get("reference"), "tolerance_basis": r.get("tolerance_basis"),
            "accepted_within": {"peak_c_max": o["max_peak_c"], "median_c": list(o["median_c"]),
                                "share_above_28c_max": o["max_share_above_28c"]},
            "approved": o["approved"], "note": o["ceiling_note"],
            "accepted_by": "~/hrsd_occupants/ops/finish_segment.py (ops-only; engine and config unchanged)",
        })
    return accepted, blocking


def finish(cfg: dict, seg: dict) -> dict:
    import baile_nua.sources_registry  # noqa: F401
    root = sup.PROJECT / cfg["out_root"] / seg["name"]
    pkg = root / "pkg"
    dpath = pkg / "run_diagnostics.json"
    diag = json.loads(dpath.read_text())
    log = (root / "progress.log").open("a", buffering=1)
    say = lambda m: log.write(f"[{sup._now()}] [ops/finish_segment] {m}\n")
    say("resuming the post-pass only; the simulation finished and is not re-run")
    t0 = time.time()

    # ---- the tail of run_year (engine/e1_run.py, U27) --------------------
    if not seg["discard_output"] and "plausibility" not in diag:
        from baile_nua.plausibility import write_suite
        plaus = write_suite(package_root=pkg,
                            out_path=pkg / "evidence" / "plausibility.json",
                            diagnostics_path=dpath)
        diag["plausibility"] = {k: v for k, v in plaus.items() if k != "results"}
        dpath.write_text(json.dumps(diag, indent=2, default=str) + "\n", encoding="utf-8")
        say(f"plausibility: {plaus['n_pass']} pass ({plaus['n_pass_sourced']} sourced), "
            f"{plaus['n_fail']} fail, {plaus['n_not_evaluable']} not evaluable")
        if not plaus["all_evaluable_checks_pass"]:
            from baile_nua.plausibility.suite import KNOWN_PLAUSIBILITY_FAILURES
            failed = [r["check_id"] for r in plaus["results"] if r["outcome"] == "FAIL"]
            unknown = [c for c in failed if c not in KNOWN_PLAUSIBILITY_FAILURES]
            _, still = accepted_exceedances(seg["year"], plaus["results"])
            unknown = [c for c in unknown if c in still]
            for cid in failed:
                if cid in KNOWN_PLAUSIBILITY_FAILURES:
                    say(f"plausibility: {cid} FAILS, declared known failure "
                        f"{KNOWN_PLAUSIBILITY_FAILURES[cid]}")
            if unknown:
                raise RuntimeError(f"U27: undeclared plausibility failures {unknown}")

    # ---- replay_supervisor.run_segment, after run_year -------------------
    from baile_nua.checkpoint import CheckpointStore
    CheckpointStore(root / "ckpt").verify_chain()
    code, conf = sup.digests()
    tag = os.environ.get("REPLAY_ENGINE_TAG", "v1-engine-freeze-2.3")

    # ---- replay_supervisor.main, the per-segment post-pass ---------------
    (root / "ENGINE.json").write_text(json.dumps({
        "segment": seg["name"], "engine_tag": tag, "code_digest": code,
        "conf_digest": conf, "d18_era_gating": bool(cfg.get("d18_era_gating", False)),
        "written_before_export": True,
    }, indent=2) + "\n")
    exported = failed_n = None
    if not seg["discard_output"]:
        from baile_nua.export import export_all
        evidence = sup.prepare_evidence_package(pkg)
        rep = export_all(pkg, pkg, relocate={}, run_name=f"replay {seg['name']}")
        rep["evidence_package"] = evidence
        rep["partially_conformant"] = {
            d: r.get("null_required_fields")
            for d, r in (rep.get("datasets") or {}).items() if r.get("null_required_fields")}
        (root / "export_report.json").write_text(json.dumps(rep, indent=2, default=str) + "\n")
        exported, failed_n = rep["n_written"], rep.get("n_failed", 0)
        res = sup.check_year(pkg, diag, seg["_days"], cfg["rss_gate_mb"])
        scan = sup.scan_package(pkg)
    else:
        res = {"ok": True, "failures": [], "counts": {},
               "peak_rss_mb": diag.get("benchmark", {}).get("peak_rss_mb")}
        scan = {"clean": True, "hits": []}
    accepted: list[dict] = []
    ppath = pkg / "evidence" / "plausibility.json"
    if not seg["discard_output"] and ppath.is_file():
        results = json.loads(ppath.read_text()).get("results") or []
        accepted, still = accepted_exceedances(seg["year"], results)
        nf = (diag.get("plausibility") or {}).get("n_fail")
        if accepted and not still and nf == len(accepted):
            res["failures"] = [f for f in res["failures"] if f != f"plausibility reports {nf} failures"]
            res["ok"] = not res["failures"]
            for a in accepted:
                say(f"plausibility: {a['check_id']} FAILS (peak {a['measured'].get('max_c')} C, median "
                    f"{a['measured'].get('median_c')} C, >28 C share {a['measured'].get('share_above_28c')}); "
                    f"ACCEPTED within the ops override bounds and recorded in DONE.json")
        elif still:
            say(f"plausibility: failures outside the ops override bounds: {still}")
    rss_exc = rss_exception(seg["year"], res, cfg["rss_gate_mb"])
    if rss_exc:
        res["failures"] = [f for f in res["failures"] if not f.startswith("peak RSS ")]
        res["ok"] = not res["failures"]
        say(f"year checks: peak RSS {rss_exc['peak_rss_mb']} MB over the {rss_exc['gate_mb']} MB gate; "
            f"ACCEPTED (<= {rss_exc['accepted_max_mb']} MB, ops override) and recorded in DONE.json")
    if not res["ok"]:
        raise RuntimeError("year checks failed: " + "; ".join(res["failures"]))
    if not scan["clean"]:
        raise RuntimeError("secret/personal scan failed: " + "; ".join(scan["hits"]))

    # Wall time of the simulation, from its own checkpoints, plus this post-pass.
    ck = sorted((root / "ckpt").glob("day_*.checkpoint.json.gz"))
    sim_s = ck[-1].stat().st_mtime - ck[0].stat().st_mtime
    wall = sim_s + (time.time() - t0)
    rec = {
        "segment": seg["name"], "days": seg["_days"],
        "sim_day": [seg["sim_day_offset"], seg["sim_day_offset"] + seg["_days"] - 1],
        "wall_h": round(wall / 3600, 2), "s_per_day": round(wall / seg["_days"], 1),
        "peak_rss_mb": res.get("peak_rss_mb"),
        "row_counts": res["counts"], "chain_verify": "chain verified",
        "export_written": exported, "export_failed": failed_n,
        "scan": scan, "discarded": seg["discard_output"], "finished": sup._now(),
        "code_digest": code, "conf_digest": conf, "master_seed": cfg["master_seed"],
        "seed_of_record": hashlib.sha256(
            f"{cfg['master_seed']}:{seg['year']}".encode()).hexdigest()[:16],
        "seed_of_record_note": "provenance only; NOT passed to the model (D-133)",
        "b2_upload": "handled by ~/hrsd_occupants/ops/post_year.sh (status/UPLOADS.md)",
        "provisional": True,
        **({"u27_accepted_exceedances": accepted} if accepted else {}),
        **({"rss_gate_exception": rss_exc} if rss_exc else {}),
        "post_pass_resumed_by": "~/hrsd_occupants/ops/finish_segment.py after the "
                                "supervisor process ended in the post-run phase; "
                                "simulation not re-run; wall_h excludes the time lost",
    }
    (root / "DONE.json").write_text(json.dumps(rec, indent=2) + "\n")
    say(f"DONE written by ops/finish_segment ({time.time() - t0:.0f} s post-pass)")
    return rec


if __name__ == "__main__":
    name = sys.argv[1]
    cfg = json.loads(sup.CONFIG.read_text())
    seg = _seg(cfg, name)
    ok, why = qualifies(cfg, seg)
    print(f"{name}: {why}")
    if "--check" in sys.argv:
        raise SystemExit(0 if ok else 3)
    if not ok:
        raise SystemExit(3)
    rec = finish(cfg, seg)
    print(f"{name}: DONE, {sum(rec['row_counts'].values()):,} rows")
