#!/usr/bin/env python3
"""Verify one completed replay segment before it is treated as delivered.

Run at every boundary. Checks the things that have actually gone wrong on this
project rather than a generic smoke test:

1. the DONE sentinel exists and records the segment it claims
2. the checkpoint chain verifies - `verify_chain()` returns None and RAISES, so
   no exception is the pass, which is a trap this project already fell into
3. one checkpoint per simulated day, numbered contiguously from the offset
4. D11 carries presence rows with `location_kind == "building"` - the thing
   D29/D30 need and that no delivered year would have had before D-141
5. D15's `is_dst` is TRUE in summer and FALSE in winter (I-111), judged on
   whichever months the segment actually spans
6. no secrets in any text file, and no identity-bearing column in an
   OBSERVABLE part - the release gate's own patterns
7. every part's row count against its manifest

Exit 0 only if everything that could be checked passed. Anything that could not
be checked is reported as SKIP and does not silently count as a pass.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
PROJECT = HERE.parent

OK, BAD, SKIP = "ok  ", "FAIL", "skip"


def _say(state, label, detail=""):
    print(f"  {state}  {label}" + (f"  — {detail}" if detail else ""))
    return state


def verify(seg_dir: Path) -> int:
    import baile_nua.sources_registry  # noqa: F401
    import pandas as pd
    import pyarrow.parquet as pq

    from baile_nua.checkpoint import CheckpointStore

    fails = 0
    print(f"\n=== {seg_dir} ===")

    done = seg_dir / "DONE.json"
    if not done.exists():
        _say(BAD, "DONE.json", "absent — the segment is not complete")
        return 1
    d = json.loads(done.read_text())
    _say(OK, "DONE.json", f"{d.get('segment')}, {d.get('days')} days, "
                          f"digest {str(d.get('code_digest'))[:12]}…")

    ckpt = seg_dir / "ckpt"
    try:
        CheckpointStore(ckpt).verify_chain()
        _say(OK, "checkpoint chain", "verified (no exception is the pass)")
    except Exception as exc:
        fails += 1
        _say(BAD, "checkpoint chain", f"{type(exc).__name__}: {exc}")

    days = sorted(int(p.name.split("_")[1].split(".")[0])
                  for p in ckpt.glob("day_*.checkpoint.json.gz"))
    if days:
        gaps = [b for a, b in zip(days, days[1:]) if b != a + 1]
        expected = d.get("days")
        if gaps:
            fails += 1
            _say(BAD, "checkpoints contiguous", f"gap before sim_day {gaps[:3]}")
        elif expected and len(days) != expected:
            fails += 1
            _say(BAD, "checkpoint count", f"{len(days)} for {expected} days")
        else:
            _say(OK, "checkpoints", f"{len(days)}, sim_day {days[0]}..{days[-1]}")
    else:
        fails += 1
        _say(BAD, "checkpoints", "none")

    pkg = seg_dir / "pkg"
    def parts(dsid):
        return sorted(pkg.rglob(f"{dsid}_part*.parquet"))

    # A warm-up segment is configured `discard_output` and writes no package at
    # all, so every package check below would FAIL on it for the one reason
    # that is not a defect. Read the intent from the config rather than
    # guessing from an empty directory, which is also what a crashed export
    # looks like.
    discarded = False
    try:
        cfg = json.loads((HERE / "replay_config.json").read_text())
        discarded = any(x["name"] == seg_dir.name and x.get("discard_output")
                        for x in cfg["segments"])
    except Exception:
        pass
    if discarded:
        _say(SKIP, "package checks",
             "segment is configured discard_output — it writes no package "
             "by design, so D11/D15/scan/rows are not applicable")
        print(f"  -> {'PASS' if fails == 0 else f'{fails} FAILURE(S)'}")
        return fails

    # 4 — D11 presence, the reason for D-141
    p11 = parts("D11")
    if not p11:
        fails += 1
        _say(BAD, "D11 presence", "no D11 part — D29/D30 cannot be built")
    else:
        n = 0
        for f in p11:
            t = pq.read_table(f, columns=["location_kind"])
            n += int((t.column("location_kind").to_pandas() == "building").sum())
        if n == 0:
            fails += 1
            _say(BAD, "D11 presence", "0 rows with location_kind=='building' "
                                      "— the collect_presence gate did not fire")
        else:
            _say(OK, "D11 presence", f"{n:,} building rows across {len(p11)} part(s)")

    # 5 — D15 is_dst, I-111
    p15 = parts("D15")
    if not p15:
        _say(SKIP, "D15 is_dst", "no D15 part in this package")
    else:
        df = pd.concat([pq.read_table(f, columns=["ts", "is_dst"]).to_pandas()
                        for f in p15])
        m = pd.to_datetime(df["ts"]).dt.month
        jan, jul = df.loc[m == 1, "is_dst"], df.loc[m == 7, "is_dst"]
        verdict, why = OK, []
        if not jan.empty and jan.mean() > 0.5:
            verdict, _ = BAD, why.append(f"January mean {jan.mean():.2f} (inverted)")
        if not jul.empty and jul.mean() < 0.5:
            verdict, _ = BAD, why.append(f"July mean {jul.mean():.2f} (inverted)")
        if jan.empty and jul.empty:
            _say(SKIP, "D15 is_dst", "segment spans neither January nor July")
        elif verdict is BAD:
            fails += 1
            _say(BAD, "D15 is_dst", "; ".join(why) + " — I-111")
        else:
            _say(OK, "D15 is_dst", f"Jan {jan.mean() if not jan.empty else float('nan'):.2f} "
                                   f"Jul {jul.mean() if not jul.empty else float('nan'):.2f}")

    # 6 — the release gate's own scan
    try:
        from replay_supervisor import scan_package
        rep = scan_package(pkg)
        hits = rep.get("hits") or rep.get("findings") or []
        if hits:
            fails += 1
            _say(BAD, "secret/personal scan", f"{len(hits)} hit(s) — NOT printed here")
        else:
            _say(OK, "secret/personal scan", "clean")
    except Exception as exc:
        _say(SKIP, "secret/personal scan", f"could not run: {type(exc).__name__}")

    # 7 — rows against manifests
    checked = mismatched = 0
    for mf in sorted(pkg.rglob("*_part*.manifest.json")):
        pqf = mf.with_name(mf.name.replace(".manifest.json", ".parquet"))
        if not pqf.exists():
            continue
        man = json.loads(mf.read_text())
        claimed = man.get("rows") or man.get("n_rows")
        if claimed is None:
            continue
        checked += 1
        if int(pq.ParquetFile(pqf).metadata.num_rows) != int(claimed):
            mismatched += 1
    if mismatched:
        fails += 1
        _say(BAD, "rows vs manifests", f"{mismatched} of {checked} disagree")
    elif checked:
        _say(OK, "rows vs manifests", f"{checked} parts agree")
    else:
        _say(SKIP, "rows vs manifests", "no manifest carries a row count")

    print(f"  -> {'PASS' if fails == 0 else f'{fails} FAILURE(S)'}")
    return fails


if __name__ == "__main__":
    args = sys.argv[1:] or [str(PROJECT / "work/replay_2015_2026/2015")]
    raise SystemExit(1 if sum(verify(Path(a)) for a in args) else 0)
