#!/bin/bash
# Assembles the mechanical half of status/MORNING.md at 08:00.
# Reads only: status/PROGRESS.md, each segment's DONE.json, the live ckpt dir,
# logs/watch.log. No full-tree walk (D-151).
. /home/ubuntu/hrsd_occupants/ops/env.sh; R="$HRSD"
exec "$PY" - "$R" <<'PY'
import json, re, subprocess, sys, time
from datetime import datetime, timedelta
from pathlib import Path
R = Path(sys.argv[1]); run = R/"work/replay_2015_2026"
SEGS = ["warmup_2014"] + [str(y) for y in range(2015, 2027)]
DAYS = {"warmup_2014":31,"2015":365,"2016":366,"2017":365,"2018":365,"2019":365,
        "2020":366,"2021":365,"2022":365,"2023":365,"2024":366,"2025":365,"2026":273}
L = []
L.append(f"# Morning report — {datetime.now():%Y-%m-%d, %H:%M}\n")
L.append("Mechanical section written by `~/hrsd_occupants/ops/morning.sh` (port of `scripts/morning_summary.sh`). "
         "v1 scope is frozen; see `docs/V1_KNOWN_LIMITATIONS.md`. "
         "v2 progress in `docs/V2_PLAN.md`.\n")

done, cur = [], None
for s in SEGS:
    dj = run/s/"DONE.json"
    if dj.is_file():
        try: done.append((s, json.loads(dj.read_text())))
        except Exception: pass
    elif (run/s).is_dir(): cur = s

L.append("## Segments\n")
L.append("| segment | days | status | s/day | peak RSS | finished |")
L.append("|---|---|---|---|---|---|")
for s, d in done:
    L.append(f"| {s} | {d.get('days','?')} | DONE | {d.get('s_per_day','?')} | "
             f"{d.get('peak_rss_mb','?')} MB | {d.get('finished','?')} |")
if cur:
    ck = sorted((run/cur/"ckpt").glob("day_*.checkpoint.json.gz"))
    if ck:
        ts = [p.stat().st_mtime for p in ck]
        day = int(re.search(r"day_0*(\d+)", ck[-1].name).group(1))
        gaps = [b-a for a, b in zip(ts, ts[1:])] or [0]
        g = sorted(gaps); med = g[len(g)//2]
        clean = [x for x in gaps if x <= 2*med] or gaps
        rate = sum(clean)/len(clean)
        inseg = len(ck)
        L.append(f"| **{cur}** | {DAYS.get(cur,'?')} | running {inseg} d "
                 f"({100*inseg/DAYS.get(cur,1):.1f}%) | {rate:.0f} (stalls excl) "
                 f"| — | sim_day {day} |")
        rem = DAYS.get(cur,0)-inseg + sum(DAYS[s] for s in SEGS
                                          if s not in dict(done) and s != cur)
        eta = datetime.now()+timedelta(seconds=rem*rate)
        L.append(f"\n**{rem} simulated days left at {rate:.0f} s/day → "
                 f"{rem*rate/3600:.0f} h, all years done ~{eta:%d %b %H:%M}.**\n")
        L.append(f"Stalls excluded from the rate: "
                 f"{len(gaps)-len(clean)} of {len(gaps)} gaps "
                 f"(median {med:.0f}s).\n")

L.append("## Host, last 24 ticks\n```")
wl = R/"logs/watch.log"
if wl.is_file():
    L.append("\n".join(wl.read_text().splitlines()[-24:]))
L.append("```\n")
up = R/"status/UPLOADS.md"
L.append("## B2 uploads\n")
L.append("\n".join(up.read_text().splitlines()[4:]) if up.is_file() else "(no upload yet)")
L.append("")
for f in ("BLOCKED.md", "UPLOAD_FAILED.md"):
    if (R/"status"/f).is_file(): L.append(f"**status/{f} exists.**\n")
L.append("## Carried open items\n")
L.append("- **P-7** accepted for v1 only (2022 population). v2 moves T0 to 2015.")
L.append("- **P-8** recommendation (b) accept and monitor; re-measure disk before acting.")
L.append("- D03/D09/D20/D12/D25/D26 absent from every year, by cause, not failure.")
L.append("- No boundary merges or engine changes until v1 finishes. "
         "Intervene only on BLOCKED or a crash.\n")
m = R/"status/MORNING.md"
if m.is_file():                      # never clobber an uncommitted report
    arc = R/"status/morning"; arc.mkdir(exist_ok=True)
    head = m.read_text().splitlines()[0] if m.read_text() else ""
    stamp = "".join(c for c in head if c.isdigit())[:8] or time.strftime("%Y%m%d")
    (arc/f"MORNING_{stamp}.md").write_text(m.read_text())
m.write_text("\n".join(L)+"\n")
print(f"wrote {R/'status/MORNING.md'} ({len(L)} lines)")
PY
