#!/usr/bin/env python3
"""Fill the v1 release-doc drafts from the run records (spec §10 item 2).

    release_fill.py --out DIR [--partial]

Reads hrsd/docs/{RELEASE_NOTES_v1,PROVENANCE,V1_KNOWN_LIMITATIONS}.draft.md and
writes DIR/<name>.md with every {{YYYY.key}} and {{total.key}} replaced from
DONE.json, ENGINE.json, export_report.json, run_diagnostics.json, the part
manifests, children.log and ops/state/<year>.UPLOADED.json. No Parquet is read.
{{MANUAL: ...}} placeholders are left for a person and listed at the end.

It also checks the claims the drafts make about "every year" (one engine,
chain verified, 18 written / 0 failed, the same absent datasets, U27 with no
failure outside the accepted PL-TEMP-01 bounds, peak RSS within the gate or an
accepted 2023-2026 exception, D11 ending on 14 January, manifests equal to
row_counts) and exits 1
if any fails.

Writing into hrsd/docs is refused until all 13 segments are DONE and 2015-2026
are UPLOADED: ops/end_guard.sh treats those file names on v1/docs/ as a
completion condition, so they must not exist early. --partial fills what
exists so far, for a preview elsewhere.
"""
import argparse, datetime as dt, glob, json, os, re, sys

HRSD = os.path.expanduser("~/hrsd_occupants/hrsd")
RUN = os.environ.get("RUN", f"{HRSD}/work/replay_2015_2026")
STATE = os.environ.get("STATE", os.path.expanduser("~/hrsd_occupants/ops/state"))
B2_DEST = os.environ.get("B2_DEST", "b2eig:hrsd-occupants/v1")
DRAFTS = ["RELEASE_NOTES_v1", "PROVENANCE", "V1_KNOWN_LIMITATIONS"]
YEARS = [str(y) for y in range(2015, 2027)]
PRICE = (0.61, 0.70)  # US$/h, same estimate as end_guard.sh
RSS_GATE_MB, RSS_EXC_MB, RSS_EXC_YEARS = 18432, 40960, range(2023, 2027)  # finish_segment.RSS_OVERRIDE
STREAMED = {"D10", "D11", "D13", "D16", "D17", "D17_aggregate", "D18", "D19"}
ABSENT = {"D03", "D09", "D12", "D20", "D25", "D26"}


def load(p):
    return json.load(open(p)) if os.path.exists(p) else None


def year_values(seg, digests):
    d = load(f"{RUN}/{seg}/DONE.json")
    if d is None:
        return None, []
    e = load(f"{RUN}/{seg}/ENGINE.json") or {}
    x = load(f"{RUN}/{seg}/export_report.json") or {}
    g = load(f"{RUN}/{seg}/pkg/run_diagnostics.json") or {}
    u = load(f"{STATE}/{seg}.UPLOADED.json")
    rows = d.get("row_counts") or {}
    b = g.get("benchmark") or {}
    era = (b.get("d18_era") or {}).get("home_days_by_era") or {}
    d18_bytes = (((b.get("storage") or {}).get("by_dataset") or {}).get("D18") or {}).get("bytes", 0)
    attempts = 1 + len(glob.glob(f"{RUN}/{seg}.partial.*")) + len(glob.glob(f"{RUN}/{seg}.superseded.*"))
    dig_ok = d.get("code_digest") == digests.get("code_digest") and d.get("conf_digest") == digests.get("conf_digest")
    v = {
        "days": d["days"], "sim_day": f"{d['sim_day'][0]}–{d['sim_day'][1]}",
        "rows": f"{sum(rows.values()):,}", "_rows": sum(rows.values()),
        "D18_rows": f"{rows.get('D18', 0):,}" + ("" if rows.get("D18") else " (gated)"), "_d18": rows.get("D18", 0),
        "D11_rows": f"{rows.get('D11', 0):,}", "D18_gb": f"{d18_bytes / 1e9:.2f}", "_d18_bytes": d18_bytes,
        "era_meter": f"{era.get('meter_30min', 0):,}", "era_full": f"{era.get('full_1min', 0):,}",
        "wall_h": d.get("wall_h"), "s_per_day": d.get("s_per_day"), "finished": d.get("finished"),
        "seed_of_record": d.get("seed_of_record"), "chain_head": (g.get("checkpoint_chain_head") or "")[:16],
        "digests": "match" if dig_ok else "**DIFFER**", "attempts": attempts, "_attempts": attempts,
        "peak_rss": f"{d.get('peak_rss_mb'):,}" if d.get("peak_rss_mb") else "?",
        "_rss_exc": d.get("rss_gate_exception"),
    }
    if u:
        v.update(gb=f"{u['remote_bytes'] / 1e9:.2f}", _bytes=u["remote_bytes"], objects=u["remote_objects"],
                 _objects=u["remote_objects"], check="0 differences", dest=u["dest"])
    # claims the drafts make about every year
    bad = []
    if not dig_ok: bad.append("code/conf digest differs from RUN_DIGESTS.json")
    if e.get("engine_tag") != "v1-engine-freeze-2.3": bad.append(f"ENGINE.json tag {e.get('engine_tag')!r}")
    if d.get("chain_verify") != "chain verified": bad.append(f"chain_verify {d.get('chain_verify')!r}")
    if not (d.get("scan") or {}).get("clean"): bad.append("package scan not clean")
    rss, exc = d.get("peak_rss_mb") or 0, d.get("rss_gate_exception")
    if rss > RSS_GATE_MB and not (exc and seg.isdigit() and int(seg) in RSS_EXC_YEARS and rss <= RSS_EXC_MB):
        bad.append(f"peak RSS {rss} MB over the gate without an accepted exception")
    if seg == "warmup_2014":
        return v, bad
    if (d.get("export_written"), d.get("export_failed")) != (18, 0):
        bad.append(f"export {d.get('export_written')} written / {d.get('export_failed')} failed")
    not_written = {k for k, r in (x.get("datasets") or {}).items() if r.get("verdict") != "written"}
    if not_written != STREAMED | ABSENT: bad.append(f"not-written set differs: {sorted(not_written ^ (STREAMED | ABSENT))}")
    pl = g.get("plausibility") or {}
    acc = d.get("u27_accepted_exceedances") or []
    if pl.get("n_checks") != 12 or pl.get("n_fail") != len(acc) or any(a.get("check_id") != "PL-TEMP-01" for a in acc):
        bad.append(f"U27 {pl.get('n_checks')} checks, {pl.get('n_fail')} fail, {len(acc)} accepted")
    v["_accepted"] = acc
    pt = load(f"{RUN}/{seg}/pkg/evidence/plausibility.json") or {}
    v["_temp"] = next((r for r in pt.get("results") or [] if r.get("check_id") == "PL-TEMP-01"), None)
    v["u27"] = (f"{pl.get('n_pass')} pass / {pl.get('n_fail')} fail" + (f" ({len(acc)} accepted)" if acc else "")
                + f" / {pl.get('n_not_evaluable')} not evaluable"
                + (f" / {pl.get('n_no_data')} NO_DATA" if pl.get("n_no_data") else ""))
    ev = (((x.get("run") or {}).get("run_t0_evidence") or {}).get("read_from") or {}).get("D11") or {}
    if not str(ev.get("max", "")).startswith(f"{seg}-01-14T23:59"): bad.append(f"D11 ends {ev.get('max')}")
    if (b.get("n_homes"), b.get("n_people")) != (1092, 2917): bad.append(f"population {b.get('n_homes')}/{b.get('n_people')}")
    man = {}
    for m in glob.glob(f"{RUN}/{seg}/pkg/*/*.manifest.json"):
        j = json.load(open(m)); man[j["dataset_id"]] = man.get(j["dataset_id"], 0) + (j.get("rows") or 0)
    if man != rows: bad.append("part manifests disagree with DONE.json row_counts")
    if not u: bad.append("not UPLOADED")
    return v, bad


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--partial", action="store_true", help="fill what exists; leave missing years as placeholders")
    a = ap.parse_args()

    digests = load(f"{RUN}/RUN_DIGESTS.json") or {}
    vals, problems = {}, []
    for seg in ["warmup_2014"] + YEARS:
        v, bad = year_values(seg, digests)
        if v is not None:
            vals[seg] = v
        problems += [f"{seg}: {p}" for p in bad]
    done = [y for y in YEARS if y in vals and "_bytes" in vals[y]]
    complete = "warmup_2014" in vals and len(done) == len(YEARS)

    out = os.path.realpath(a.out)
    if out == os.path.realpath(f"{HRSD}/docs") and not complete:
        sys.exit("refused: final names in hrsd/docs only after all 13 segments are DONE and 2015-2026 UPLOADED")
    if not complete and not a.partial:
        sys.exit(f"only {len(done)}/12 years uploaded; use --partial for a preview")

    tot = {}
    if done:
        ys = [vals[y] for y in done]
        tot = {"days": f"{sum(v['days'] for v in ys):,}", "rows": f"{sum(v['_rows'] for v in ys):,}",
               "gb": f"{sum(v['_bytes'] for v in ys) / 1e9:.2f}", "objects": f"{sum(v['_objects'] for v in ys):,}",
               "D18_rows": f"{sum(v['_d18'] for v in ys):,}", "D18_gb": f"{sum(v['_d18_bytes'] for v in ys) / 1e9:.2f}",
               "wall_h": f"{sum(v['wall_h'] for v in ys):.1f}"}
        first = re.match(r"(\S+ \S+)", open(f"{RUN}/children.log").readline()).group(1)
        last = max(vals[s]["finished"] for s in vals)
        h = (dt.datetime.fromisoformat(last) - dt.datetime.fromisoformat(first)).total_seconds() / 3600
        tot.update(run_start=first, run_end=last, elapsed_h=f"{h:.1f}",
                   cost=f"{h:.1f} h × US${PRICE[0]:.2f}–{PRICE[1]:.2f}/h = US${h * PRICE[0]:,.0f}–{h * PRICE[1]:,.0f}")
        tot["u27_by_year"] = "; ".join(f"{y} {vals[y].get('u27', '?')}" for y in done)
        rows_acc = [f"| {y} | {a['measured'].get('max_c')} | {a['measured'].get('median_c')} | "
                    f"{100 * a['measured'].get('share_above_28c', 0):.2f} % |"
                    for y in done for a in vals[y].get("_accepted", [])]
        tot["u27_accepted_rows"] = "\n".join(rows_acc) or "| none | | | |"
        tot["peak_rss_by_year"] = "; ".join(f"{y} {vals[y]['peak_rss']} MB" for y in done)
        excs = [(y, vals[y]["_rss_exc"]) for y in done if vals[y].get("_rss_exc")]
        tot["rss_exception_rows"] = "\n".join(
            f"| {y} | {e['peak_rss_mb']:,} | {e['gate_mb']:,} | {e['accepted_max_mb']:,} |" for y, e in excs) or "| none | | | |"
        tot["rss_exception_rows_short"] = "\n".join(
            f"| {y} | {e['peak_rss_mb']:,} | {e['accepted_max_mb']:,} |" for y, e in excs) or "| none | | |"
        later = []
        for y in done:
            t = vals[y].get("_temp")
            if int(y) >= 2021 and t:
                m = t.get("measured") or {}
                verdict = "**FAIL, accepted**" if vals[y].get("_accepted") else t.get("outcome", "?").lower()
                later.append(f"| {y} | {m.get('max_c')} | {m.get('median_c')} | {100 * m.get('share_above_28c', 0):.2f} % | {verdict} |")
        tot["u27_temp_rows_from_2021"] = "\n".join(later)
        resim = [y for y in done if glob.glob(f"{RUN}/{y}.partial.*")]
        stopped = [y for y in done if glob.glob(f"{RUN}/{y}.superseded.*")]
        tot["attempts_note"] = (
            ("Every year's published package is its first simulation"
             + (f" except {', '.join(resim)}, which was simulated twice" if resim else "") + ".")
            + (f" {', '.join(stopped)} each also have an in-process retry that was stopped within minutes"
               " and kept as `<year>.superseded.<ts>`; the finished first simulation is the one published."
               if stopped else ""))
        if not complete:
            tot = {k: v if k in ("run_start", "run_end", "attempts_note", "u27_by_year", "u27_accepted_rows",
                                 "u27_temp_rows_from_2021", "peak_rss_by_year", "rss_exception_rows",
                                 "rss_exception_rows_short") else f"{v} (to {done[-1]})"
                   for k, v in tot.items()}

    def sub(m):
        scope, key = m.group(1), m.group(2)
        src = tot if scope == "total" else vals.get(scope, {})
        return str(src[key]) if key in src else m.group(0)

    os.makedirs(out, exist_ok=True)
    left = {}
    for name in DRAFTS:
        text = open(f"{HRSD}/docs/{name}.draft.md").read()
        text = re.sub(r"\A<!--.*?-->\n+", "", text, flags=re.S)  # the draft banner
        text = re.sub(r"\{\{(total|\d{4})\.([A-Za-z0-9_]+)\}\}", sub, text)
        left[name] = re.findall(r"\{\{(?!MANUAL)[^}]*\}\}", text), re.findall(r"\{\{MANUAL:[^}]*\}\}", text, flags=re.S)
        open(f"{out}/{name}.md", "w").write(text)

    print(f"wrote {len(DRAFTS)} files to {out}; years filled: {', '.join(done) or 'none'}")
    for name, (auto, manual) in left.items():
        print(f"  {name}.md: {len(auto)} unfilled data placeholder(s), {len(manual)} MANUAL item(s)")
    print("every-year checks: " + ("all hold" if not problems else f"{len(problems)} FAILED"))
    for p in problems:
        print(f"  {p}")
    sys.exit(1 if problems and complete else 0)


if __name__ == "__main__":
    main()
