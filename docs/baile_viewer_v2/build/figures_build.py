#!/usr/bin/env python3
"""
Baile Nua v1: build pre-computed figure data for the PHP viewer.

Reads the v1 release (local Parquet where present, otherwise B2 via S3) with
DuckDB, aggregates each figure to a small JSON file, and writes:

    <out>/index.json            tabs -> figures (with available years)
    <out>/<figure_id>.json      one file per figure (or <id>@<year>.json)

Upload <out>/ to b2eig:hrsd-occupants/v1/figures/ afterwards.

Read-only with respect to the release. Never prints credentials.

Env (only needed for years whose Parquet is not local):
    B2_KEY_ID, B2_APP_KEY        read key for the bucket
    B2_ENDPOINT                  default s3.eu-central-003.backblazeb2.com
    B2_BUCKET                    default hrsd-occupants

Usage:
    python3 figures_build.py --local-root ~/hrsd_occupants/hrsd/work/replay_2015_2026 \
        --out ~/hrsd_occupants/figures --profile-year 2025
    python3 figures_build.py ... --only weather,energy     # subset of tabs
"""
import argparse, glob, json, math, os, sys, time, traceback
import duckdb

YEARS = [int(y) for y in os.environ.get('FIG_YEARS','').split(',') if y] or list(range(2015, 2027))
TZ = "Europe/Dublin"
LABEL = "UNVALIDATED SIMULATION EVIDENCE: E1 engineering candidate. Synthetic town; no real people or premises."
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
BER_ORDER = ["A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2", "C3", "D1", "D2", "E1", "E2", "F", "G"]

ap = argparse.ArgumentParser()
ap.add_argument("--local-root", default=os.path.expanduser("~/hrsd_occupants/hrsd/work/replay_2015_2026"))
ap.add_argument("--out", default=os.path.expanduser("~/hrsd_occupants/figures"))
ap.add_argument("--profile-year", type=int, default=2025, help="year used for single-year figures")
ap.add_argument("--only", default="", help="comma list of tabs to build")
ap.add_argument("--memory", default="24GB")
ap.add_argument("--threads", type=int, default=6)
args = ap.parse_args()
PY = args.profile_year
os.makedirs(args.out, exist_ok=True)
ONLY = set(t for t in args.only.split(",") if t)

con = duckdb.connect()
con.execute(f"SET memory_limit='{args.memory}'; SET threads={args.threads}; SET TimeZone='UTC';")
for ext in ("icu", "httpfs"):
    try:
        con.execute(f"INSTALL {ext}; LOAD {ext};")
    except Exception as e:
        print(f"warning: extension {ext}: {e}", file=sys.stderr)
_s3_ready = False

def s3_ready():
    global _s3_ready
    if _s3_ready:
        return
    kid, key = os.environ.get("B2_KEY_ID"), os.environ.get("B2_APP_KEY")
    if not (kid and key):
        raise RuntimeError("B2_KEY_ID / B2_APP_KEY not set and Parquet not local")
    ep = os.environ.get("B2_ENDPOINT", "s3.eu-central-003.backblazeb2.com")
    region = ep.split(".")[1]
    con.execute("CREATE OR REPLACE SECRET b2 (TYPE s3, KEY_ID ?, SECRET ?, ENDPOINT ?, REGION ?, URL_STYLE 'path')",
                [kid, key, ep, region])
    _s3_ready = True

BUCKET = os.environ.get("B2_BUCKET", "hrsd-occupants")

def src(year, pkg, ds):
    """SQL-quoted list of Parquet parts for a dataset-year (local first, then B2)."""
    local = sorted(glob.glob(os.path.join(args.local_root, str(year), "pkg", pkg, f"{ds}_part*.parquet")))
    if not local:  # alternative local layout
        local = sorted(glob.glob(os.path.join(args.local_root, str(year), pkg, f"{ds}_part*.parquet")))
    if local:
        return "[" + ",".join("'" + p.replace("'", "''") + "'" for p in local) + "]"
    s3_ready()
    return f"'s3://{BUCKET}/v1/{year}/{pkg}/{ds}_part*.parquet'"

def meta_json(year, rel):
    """Read a small JSON file of a year (local first, then B2)."""
    for p in (os.path.join(args.local_root, str(year), "pkg", rel),
              os.path.join(args.local_root, str(year), rel),
              os.path.expanduser(f"~/hrsd_occupants/ops/state/meta/{year}/{os.path.basename(rel)}")):
        if os.path.exists(p):
            with open(p) as f:
                return json.load(f)
    s3_ready()
    txt = con.execute(f"SELECT content FROM read_text('s3://{BUCKET}/v1/{year}/{rel}')").fetchone()[0]
    return json.loads(txt)

def q(sql):
    return con.execute(sql).fetchall()

def num(v, nd=3):
    if v is None:
        return None
    try:
        f = float(v)
    except Exception:
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return round(f, nd)

INDEX = {}
TABS = [
    ("overview", "Overview"), ("buildings", "Buildings"), ("people", "People"),
    ("weather", "Weather"), ("energy", "Energy"), ("comfort", "Comfort"),
    ("appliances", "Appliances"), ("behaviour", "Behaviour"),
    ("network", "Network"), ("meters", "Smart meters"), ("tariffs", "Tariffs"),
]

def emit(tab, fid, fig, year=None):
    fig.setdefault("label", LABEL)
    fig["id"] = fid
    name = f"{fid}@{year}" if year else fid
    with open(os.path.join(args.out, name + ".json"), "w") as f:
        json.dump(fig, f, separators=(",", ":"), default=str)
    entry = INDEX.setdefault(tab, {}).setdefault(fid, {"id": fid, "title": fig.get("title", fid), "years": []})
    if year:
        entry["years"].append(year)

def run(tab, fn):
    if ONLY and tab not in ONLY:
        return
    t0 = time.time()
    try:
        fn()
        print(f"[ok] {tab} in {time.time()-t0:.0f}s", flush=True)
    except Exception:
        print(f"[FAIL] {tab}", file=sys.stderr)
        traceback.print_exc()

def bar(title, labels, series, unit="", note="", stacked=False, horizontal=False):
    return {"kind": "bar", "title": title, "labels": labels, "series": series, "unit": unit,
            "note": note, "stacked": stacked, "horizontal": horizontal}

def line(title, labels, series, unit="", note="", xlabel=""):
    return {"kind": "line", "title": title, "labels": labels, "series": series, "unit": unit, "note": note, "xlabel": xlabel}

def heat(title, x, y, z, unit="", note=""):
    return {"kind": "heatmap", "title": title, "x": x, "y": y, "z": z, "unit": unit, "note": note}

# ---------------------------------------------------------------- overview
def overview():
    done = {}
    for y in YEARS:
        try:
            done[y] = meta_json(y, "_segment/DONE.json")
        except Exception as e:
            print(f"  DONE.json {y}: {e}", file=sys.stderr)
    ys = [y for y in YEARS if y in done]
    total_rows = sum(sum((done[y].get("row_counts") or {}).values()) for y in ys)
    emit("overview", "ov_kpi", {"kind": "kpi", "title": "Release at a glance", "items": [
        {"label": "Simulated years", "value": f"{len(ys)}", "sub": "1 Jan 2015 to 30 Sep 2026"},
        {"label": "Homes / people", "value": "1,092 / 2,917", "sub": "calibrated to Cobh, Co. Cork"},
        {"label": "Rows", "value": f"{total_rows/1e9:.2f} bn", "sub": "26 datasets"},
        {"label": "Simulated days", "value": f"{sum(int(done[y].get('days', 0)) for y in ys):,}", "sub": "one master seed"},
    ]})
    big = ["D18", "D19", "D16", "D13", "D10"]
    series = []
    for ds in big:
        series.append({"name": ds, "data": [num((done[y].get("row_counts") or {}).get(ds, 0) / 1e6, 2) for y in ys]})
    series.append({"name": "Other", "data": [num(sum(v for k, v in (done[y].get("row_counts") or {}).items() if k not in big) / 1e6, 2) for y in ys]})
    emit("overview", "ov_rows", bar("Rows per year by dataset", [str(y) for y in ys], series, "million rows", stacked=True,
         note="D18 (smart-meter observations) grows with the meter rollout from Oct 2019."))
    emit("overview", "ov_speed", bar("Simulation speed", [str(y) for y in ys],
         [{"name": "s per simulated day", "data": [num(done[y].get("s_per_day"), 1) for y in ys]}], "s/day"))
    emit("overview", "ov_rss", bar("Peak simulation memory", [str(y) for y in ys],
         [{"name": "peak RSS", "data": [num((done[y].get("peak_rss_mb") or 0) / 1024, 1) for y in ys]}], "GB",
         note="Years 2023 to 2026 exceeded the frozen 18 GB gate and were accepted as an ops-only exception (no output impact)."))
    # U27 matrix
    rows, checks = [], []
    for y in ys:
        try:
            pl = meta_json(y, "evidence/plausibility.json")
        except Exception:
            continue
        res = {r.get("check_id"): r.get("outcome") for r in pl.get("results", [])}
        for c in res:
            if c not in checks:
                checks.append(c)
        rows.append((y, res))
    emit("overview", "ov_u27", {"kind": "table", "title": "U27 plausibility checks by year",
         "columns": ["year"] + checks,
         "rows": [[str(y)] + [res.get(c, "") for c in checks] for y, res in rows],
         "note": "PL-TEMP-01 FAIL in 2020, 2024 and 2025 was accepted under pre-declared bounds. NO_DATA in 2026: annual checks need 350+ days."})
    # D18 era from run_diagnostics
    eras, labels = {}, []
    for y in ys:
        try:
            rd = meta_json(y, "run_diagnostics.json")
            e = ((rd.get("benchmark") or {}).get("d18_era") or {}).get("home_days_by_era") or {}
        except Exception:
            e = {}
        labels.append(str(y))
        for k in ("none", "meter_30min", "full_1min"):
            eras.setdefault(k, []).append(int(e.get(k, 0)))
    emit("meters", "m_era", bar("Home-days by metering era", labels,
         [{"name": {"none": "No smart meter", "meter_30min": "Smart meter (30 min)", "full_1min": "Study enrolment (1 min)"}[k], "data": v}
          for k, v in eras.items()], "home-days", stacked=True))

# ---------------------------------------------------------------- buildings
def counts(sql):
    r = q(sql)
    return [str(a) for a, _ in r], [int(b) for _, b in r]

def buildings():
    s = src(PY, "ground_truth", "D02")
    for col, title in (("dwelling_type", "Dwelling type"), ("heating_fuel", "Heating fuel"), ("tenure", "Tenure"),
                       ("heating_control", "Heating control")):
        lab, val = counts(f"SELECT {col}, count(*) FROM read_parquet({s}) GROUP BY 1 ORDER BY 2 DESC")
        emit("buildings", f"b_{col}", bar(title, lab, [{"name": "homes", "data": val}], "homes", horizontal=True))
    r = dict(q(f"SELECT ber_band, count(*) FROM read_parquet({s}) GROUP BY 1"))
    lab = [b for b in BER_ORDER if b in r] + [b for b in r if b not in BER_ORDER]
    emit("buildings", "b_ber", bar("BER band", lab, [{"name": "homes", "data": [int(r[b]) for b in lab]}], "homes",
         note="Asset rating; operational energy can diverge (performance gap)."))
    lab, val = counts(f"SELECT (floor(build_year/10)*10)::INT AS d, count(*) FROM read_parquet({s}) GROUP BY 1 ORDER BY 1")
    emit("buildings", "b_era", bar("Construction decade", [f"{l}s" for l in lab], [{"name": "homes", "data": val}], "homes"))
    lab, val = counts(f"SELECT (floor(floor_area_m2/20)*20)::INT AS a, count(*) FROM read_parquet({s}) GROUP BY 1 ORDER BY 1")
    emit("buildings", "b_area", bar("Floor area", [f"{l}–{int(l)+20}" for l in lab], [{"name": "homes", "data": val}], "homes",
         note="20 m² bins."))
    r = q(f"SELECT dwelling_type, avg(ber_kwh_m2_yr), count(*) FROM read_parquet({s}) GROUP BY 1 ORDER BY 2")
    emit("buildings", "b_ber_by_type", bar("Mean BER rating by dwelling type", [a for a, _, _ in r],
         [{"name": "kWh/m²/yr", "data": [num(b, 0) for _, b, _ in r]}], "kWh/m²/yr", horizontal=True))

# ---------------------------------------------------------------- people
def people():
    s5, s6 = src(PY, "ground_truth", "D05"), src(PY, "ground_truth", "D06")
    ref = f"DATE '{PY}-07-01'"
    r = q(f"""SELECT least(floor(date_diff('year', birth_date, {ref})/5)*5, 85)::INT AS band, sex, count(*)
              FROM read_parquet({s5}) GROUP BY 1,2 ORDER BY 1""")
    bands = sorted(set(a for a, _, _ in r))
    lab = [f"{b}–{b+4}" if b < 85 else "85+" for b in bands]
    d = {(a, b): c for a, b, c in r}
    emit("people", "p_age", bar(f"Age and sex, mid-{PY}", lab,
         [{"name": "Female", "data": [d.get((b, "F"), 0) for b in bands]},
          {"name": "Male", "data": [d.get((b, "M"), 0) for b in bands]}], "people"))
    lab, val = counts(f"""SELECT n, count(*) FROM (SELECT household_id, count(*) n FROM read_parquet({s6})
                          WHERE valid_to IS NULL GROUP BY 1) GROUP BY 1 ORDER BY 1""")
    emit("people", "p_hh", bar("Household size", lab, [{"name": "households", "data": val}], "households"))
    lab, val = counts(f"SELECT role, count(*) FROM read_parquet({s6}) WHERE valid_to IS NULL GROUP BY 1 ORDER BY 2 DESC")
    emit("people", "p_role", bar("Household role", lab, [{"name": "people", "data": val}], "people", horizontal=True))
    lab, val = counts(f"SELECT education_level, count(*) FROM read_parquet({s5}) GROUP BY 1 ORDER BY 2 DESC")
    emit("people", "p_edu", bar("Education level (ISCED)", lab, [{"name": "people", "data": val}], "people", horizontal=True))
    lab, val = counts(f"SELECT round(chronotype*2)/2 AS c, count(*) FROM read_parquet({s5}) GROUP BY 1 ORDER BY 1")
    emit("people", "p_chrono", bar("Chronotype (sleep-window shift)", lab, [{"name": "people", "data": val}], "people",
         note="Hours relative to the population mean."))

# ---------------------------------------------------------------- weather
def weather():
    temp, ghi = [], []
    for y in YEARS:
        s = src(y, "ground_truth", "D15")
        r = dict((m, (t, g)) for m, t, g in q(f"""
            SELECT month(ts AT TIME ZONE '{TZ}') m, avg(temp_air_c), sum(ghi_w_m2)/60/1000
            FROM read_parquet({s}) WHERE year(ts AT TIME ZONE '{TZ}') = {y} GROUP BY 1"""))
        temp.append([num(r[m][0], 2) if m in r else None for m in range(1, 13)])
        ghi.append([num(r[m][1], 1) if m in r else None for m in range(1, 13)])
        dh = q(f"""SELECT dayofyear(ts AT TIME ZONE '{TZ}') d, hour(ts AT TIME ZONE '{TZ}') h, avg(temp_air_c)
                   FROM read_parquet({s}) WHERE year(ts AT TIME ZONE '{TZ}') = {y} GROUP BY 1,2""")
        nd = max([a for a, _, _ in dh] or [1])
        z = [[None] * nd for _ in range(24)]
        for d, h, t in dh:
            z[h][d - 1] = num(t, 1)
        emit("weather", "w_dayhour", heat(f"Air temperature by day and hour", list(range(1, nd + 1)), list(range(24)), z, "°C",
             note="Site weather (D15), local time."), year=y)
    emit("weather", "w_temp_month", heat("Mean air temperature by month", MONTHS, [str(y) for y in YEARS], temp, "°C"))
    emit("weather", "w_ghi_month", heat("Solar irradiation by month", MONTHS, [str(y) for y in YEARS], ghi, "kWh/m²",
         note="Global horizontal irradiation."))

# ---------------------------------------------------------------- energy
def energy():
    imp, exp_, monthly = [], [], []
    for y in YEARS:
        s = src(y, "observable", "D19")
        r = dict((m, (i, e)) for m, i, e in q(f"""
            SELECT month(interval_start AT TIME ZONE '{TZ}'), sum(import_wh)/1e6, sum(export_wh)/1e6
            FROM read_parquet({s}) WHERE export_config='estate_aggregate' GROUP BY 1"""))
        monthly.append([num(r[m][0], 1) if m in r else None for m in range(1, 13)])
        imp.append(num(sum(v[0] or 0 for v in r.values()), 0))
        exp_.append(num(sum(v[1] or 0 for v in r.values()), 0))
    emit("energy", "e_annual", bar("Estate electricity import and export", [str(y) for y in YEARS],
         [{"name": "Import", "data": imp}, {"name": "Export", "data": exp_}], "MWh",
         note="D19 estate_aggregate series. 2026 covers Jan to Sep."))
    emit("energy", "e_month", heat("Estate import by month", MONTHS, [str(y) for y in YEARS], monthly, "MWh"))
    s = src(PY, "observable", "D19")
    seasons = {"Winter": (12, 1, 2), "Spring": (3, 4, 5), "Summer": (6, 7, 8), "Autumn": (9, 10, 11)}
    prof = {}
    for name, ms in seasons.items():
        r = q(f"""SELECT hour(t)*2 + (minute(t)>=30)::INT slot, avg(import_wh / (epoch(interval_end)-epoch(interval_start)) * 3600)/1000
                  FROM (SELECT interval_start AT TIME ZONE '{TZ}' t, * FROM read_parquet({s}) WHERE export_config='estate_aggregate')
                  WHERE month(t) IN {ms} GROUP BY 1 ORDER BY 1""")
        prof[name] = dict(r)
    slots = list(range(48))
    emit("energy", "e_profile", line(f"Average estate load by time of day, {PY}", [f"{s//2:02d}:{'30' if s%2 else '00'}" for s in slots],
         [{"name": n, "data": [num(p.get(sl), 1) for sl in slots]} for n, p in prof.items()], "kW", xlabel="local time"))
    qs = [i / 100 for i in range(0, 101)]
    r = q(f"""SELECT quantile_cont(import_wh / (epoch(interval_end)-epoch(interval_start)) * 3600 / 1000, {qs})
              FROM read_parquet({s}) WHERE export_config='estate_aggregate'""")[0][0]
    emit("energy", "e_ldc", line(f"Estate load duration curve, {PY}", [f"{100-int(p*100)}%" for p in qs],
         [{"name": "estate import", "data": [num(v, 1) for v in reversed(r)]}], "kW", xlabel="share of time load is exceeded"))
    r = q(f"""SELECT (floor(kwh/500)*500)::INT b, count(*) FROM (SELECT premises_id, sum(import_wh)/1000 kwh FROM read_parquet({s})
              WHERE export_config='home_15min' GROUP BY 1) GROUP BY 1 ORDER BY 1""")
    emit("energy", "e_home_annual", bar(f"Annual electricity import per home, {PY}", [f"{a:,}–{a+500:,}" for a, _ in r],
         [{"name": "homes", "data": [int(b) for _, b in r]}], "homes", note="Homes exporting home_15min profiles; 500 kWh bins."))

# ---------------------------------------------------------------- comfort
def comfort():
    tm = []
    for y in YEARS:
        s = src(y, "ground_truth", "D16")
        r = dict(q(f"SELECT month(ts AT TIME ZONE '{TZ}'), avg(temp_living_c) FROM read_parquet({s}) GROUP BY 1"))
        tm.append([num(r.get(m), 2) for m in range(1, 13)])
    emit("comfort", "c_temp_month", heat("Mean living-room temperature by month", MONTHS, [str(y) for y in YEARS], tm, "°C"))
    s = src(PY, "ground_truth", "D16")
    r = q(f"""SELECT floor(temp_living_c*2)/2 b, count(*) FROM read_parquet({s})
              WHERE month(ts AT TIME ZONE '{TZ}') IN (12,1,2) GROUP BY 1 ORDER BY 1""")
    tot = sum(c for _, c in r) or 1
    emit("comfort", "c_temp_hist", bar(f"Winter living-room temperature, {PY}", [f"{a:.1f}" for a, _ in r],
         [{"name": "share of home-intervals", "data": [num(100 * c / tot, 3) for _, c in r]}], "%", note="Dec, Jan, Feb; 0.5 °C bins."))
    r = q(f"""SELECT least(floor(co2_living_ppm/100)*100, 3000)::INT b, count(*) FROM read_parquet({s}) GROUP BY 1 ORDER BY 1""")
    tot = sum(c for _, c in r) or 1
    emit("comfort", "c_co2", bar(f"Living-room CO₂, {PY}", [f"{a}" if a < 3000 else "3000+" for a, _ in r],
         [{"name": "share", "data": [num(100 * c / tot, 3) for _, c in r]}], "%", note="100 ppm bins."))
    sw = src(PY, "ground_truth", "D15")
    r = q(f"""WITH h AS (SELECT CAST(ts AT TIME ZONE '{TZ}' AS DATE) d, avg(heat_delivered_w)/1000 kw FROM read_parquet({s}) GROUP BY 1),
                   w AS (SELECT CAST(ts AT TIME ZONE '{TZ}' AS DATE) d, avg(temp_air_c) t FROM read_parquet({sw}) GROUP BY 1)
              SELECT w.t, h.kw FROM h JOIN w USING (d) ORDER BY 1""")
    emit("comfort", "c_heat_vs_temp", {"kind": "scatter", "title": f"Daily heat delivered vs outdoor temperature, {PY}",
         "series": [{"name": "days", "data": [{"x": num(a, 2), "y": num(b, 3)} for a, b in r]}],
         "xlabel": "daily mean outdoor temperature (°C)", "unit": "kW per home (mean)"})

# ---------------------------------------------------------------- appliances
def appliances():
    s = src(PY, "ground_truth", "D13")
    r = q(f"""SELECT programme, sum(energy_wh)/1e6 FROM read_parquet({s}) GROUP BY 1 ORDER BY 2 DESC LIMIT 15""")
    emit("appliances", "a_energy", bar(f"Appliance energy by programme, {PY} (top 15)", [a for a, _ in r],
         [{"name": "MWh", "data": [num(b, 1) for _, b in r]}], "MWh", horizontal=True))
    r = q(f"""SELECT hour(start AT TIME ZONE '{TZ}') h, isodow(start AT TIME ZONE '{TZ}') >= 6 we, count(*)
              FROM read_parquet({s}) GROUP BY 1,2""")
    days = dict(q(f"""SELECT isodow(d) >= 6, count(*) FROM (SELECT DISTINCT CAST(start AT TIME ZONE '{TZ}' AS DATE) d FROM read_parquet({s})) GROUP BY 1"""))
    d = {(h, we): c for h, we, c in r}
    emit("appliances", "a_hour", line(f"Appliance cycle starts by hour, {PY}", [f"{h:02d}:00" for h in range(24)],
         [{"name": "Weekday", "data": [num(d.get((h, False), 0) / max(days.get(False, 1), 1), 0) for h in range(24)]},
          {"name": "Weekend", "data": [num(d.get((h, True), 0) / max(days.get(True, 1), 1), 0) for h in range(24)]}],
         "cycles per day (estate)", xlabel="local time"))
    r = q(f"""SELECT programme, avg(flexible::INT)*100, avg((shifted_by_min>0)::INT)*100 FROM read_parquet({s})
              GROUP BY 1 HAVING count(*) > 10000 ORDER BY 2 DESC LIMIT 15""")
    emit("appliances", "a_flex", bar(f"Flexible and shifted cycles, {PY}", [a for a, _, _ in r],
         [{"name": "Flexible", "data": [num(b, 1) for _, b, _ in r]}, {"name": "Shifted by a signal", "data": [num(c, 2) for _, _, c in r]}],
         "% of cycles", horizontal=True))

# ---------------------------------------------------------------- behaviour
def behaviour():
    s = src(PY, "ground_truth", "D10")
    weeks = [(f"{PY}-01-12", f"{PY}-01-19"), (f"{PY}-04-13", f"{PY}-04-20"), (f"{PY}-07-13", f"{PY}-07-20"), (f"{PY}-10-12", f"{PY}-10-19")]
    union = " UNION ALL ".join(
        f"SELECT unnest(generate_series(TIMESTAMPTZ '{a} 00:30:00+00', TIMESTAMPTZ '{b} 00:00:00+00', INTERVAL 1 HOUR)) t" for a, b in weeks)
    lo, hi = weeks[0][0], weeks[-1][1]
    r = q(f"""WITH t AS ({union}),
                   a AS (SELECT person_id, start, "end", activity_code FROM read_parquet({s})
                         WHERE "end" > TIMESTAMPTZ '{lo} 00:00:00+00' AND start < TIMESTAMPTZ '{hi} 00:00:00+00')
              SELECT hour(t.t AT TIME ZONE '{TZ}') h, isodow(t.t AT TIME ZONE '{TZ}') >= 6 we, a.activity_code, count(*)
              FROM t JOIN a ON a.start <= t.t AND a."end" > t.t GROUP BY 1,2,3""")
    tot = {}
    for h, we, c, n in r:
        tot[c] = tot.get(c, 0) + n
    top = [c for c, _ in sorted(tot.items(), key=lambda kv: -kv[1])[:7]]
    for we, name in ((False, "Weekday"), (True, "Weekend")):
        agg = {}
        for h, w, c, n in r:
            if w != we:
                continue
            k = c if c in top else "Other"
            agg[(h, k)] = agg.get((h, k), 0) + n
        hours = list(range(24))
        tot_h = {h: sum(v for (hh, _), v in agg.items() if hh == h) or 1 for h in hours}
        emit("behaviour", f"bh_{name.lower()}", bar(f"What people are doing, {name.lower()}s ({PY} sample weeks)",
             [f"{h:02d}" for h in hours],
             [{"name": k, "data": [num(100 * agg.get((h, k), 0) / tot_h[h], 1) for h in hours]} for k in top + ["Other"]],
             "% of people", stacked=True, note="Four sample weeks (Jan, Apr, Jul, Oct), sampled at half past each hour."))

# ---------------------------------------------------------------- network
def network():
    z = []
    for y in YEARS:
        s = src(y, "ground_truth", "D17")
        r = dict(q(f"""SELECT month(ts AT TIME ZONE '{TZ}'), quantile_cont(loading_pct, 0.95) FROM read_parquet({s})
                       WHERE element_kind='transformer' GROUP BY 1"""))
        z.append([num(r.get(m), 1) for m in range(1, 13)])
    emit("network", "n_load_month", heat("Transformer loading, 95th percentile by month", MONTHS, [str(y) for y in YEARS], z, "% of rating"))
    s = src(PY, "ground_truth", "D17")
    r = q(f"""SELECT element_id, max(loading_pct) FROM read_parquet({s}) WHERE loading_pct IS NOT NULL
              GROUP BY 1 ORDER BY 2 DESC LIMIT 20""")
    emit("network", "n_top", bar(f"Highest peak loading by network element, {PY}", [a for a, _ in r],
         [{"name": "peak loading", "data": [num(b, 1) for _, b in r]}], "% of rating", horizontal=True))
    r = q(f"""SELECT round(voltage_pu*200)/200 b, count(*) FROM read_parquet({s}) WHERE voltage_pu IS NOT NULL GROUP BY 1 ORDER BY 1""")
    tot = sum(c for _, c in r) or 1
    emit("network", "n_volt", bar(f"Voltage distribution, {PY}", [f"{a:.3f}" for a, _ in r],
         [{"name": "share", "data": [num(100 * c / tot, 3) for _, c in r]}], "%", note="Per unit, 0.005 bins."))

# ---------------------------------------------------------------- meters
def meters():
    years = [y for y in YEARS if y >= 2019]
    ch, qual, prem = {}, {}, []
    for y in years:
        s = src(y, "observable", "D18")
        for c, n in q(f"SELECT channel, count(*) FROM read_parquet({s}) GROUP BY 1"):
            ch.setdefault(c, {})[y] = n
        tot = 0
        rq = q(f"SELECT quality, count(*) FROM read_parquet({s}) GROUP BY 1")
        tot = sum(n for _, n in rq) or 1
        for c, n in rq:
            qual.setdefault(c, {})[y] = 100 * n / tot
        prem.append(int(q(f"SELECT count(DISTINCT premises_id) FROM read_parquet({s}) WHERE channel='import_w'")[0][0]))
    order = sorted(ch, key=lambda c: -sum(ch[c].values()))
    top = order[:6]
    series = [{"name": c, "data": [num(ch[c].get(y, 0) / 1e6, 2) for y in years]} for c in top]
    if len(order) > 6:
        series.append({"name": "Other", "data": [num(sum(ch[c].get(y, 0) for c in order[6:]) / 1e6, 2) for y in years]})
    emit("meters", "m_channels", bar("Observation rows by channel", [str(y) for y in years], series, "million rows", stacked=True))
    emit("meters", "m_premises", bar("Premises with smart-meter import data", [str(y) for y in years],
         [{"name": "premises", "data": prem}], "premises", note="Distinct premises with an import_w channel in the year."))
    qorder = [k for k in ("ok", "estimated", "missing", "suspect", "drift", "fault") if k in qual] + [k for k in qual if k not in ("ok", "estimated", "missing", "suspect", "drift", "fault")]
    emit("meters", "m_quality", bar("Reading quality", [str(y) for y in years],
         [{"name": k, "data": [num(qual[k].get(y, 0), 2) for y in years]} for k in qorder], "% of readings", stacked=True))

# ---------------------------------------------------------------- tariffs
def tariffs():
    s = src(PY, "observable", "D27")
    for col, title in (("tariff_kind", "Tariff type"), ("supplier", "Supplier")):
        lab, val = counts(f"SELECT {col}, count(DISTINCT premises_id) FROM read_parquet({s}) GROUP BY 1 ORDER BY 2 DESC")
        emit("tariffs", f"t_{col}", bar(f"{title}, {PY}", lab, [{"name": "premises", "data": val}], "premises", horizontal=True))
    r = q(f"""SELECT (export_rate_eur_kwh IS NOT NULL) has, count(DISTINCT premises_id) FROM read_parquet({s}) GROUP BY 1""")
    d = dict(r)
    emit("tariffs", "t_export", bar(f"Premises with an export rate, {PY}", ["With export rate", "Without"],
         [{"name": "premises", "data": [int(d.get(True, 0)), int(d.get(False, 0))]}], "premises"))

for tab, fn in (("overview", overview), ("buildings", buildings), ("people", people), ("weather", weather),
                ("energy", energy), ("comfort", comfort), ("appliances", appliances), ("behaviour", behaviour),
                ("network", network), ("meters", meters), ("tariffs", tariffs)):
    run(tab, fn)

# merge with an existing index so --only runs keep other tabs
idx_path = os.path.join(args.out, "index.json")
old = {}
if os.path.exists(idx_path):
    try:
        old = {t["id"]: {f["id"]: f for f in t["figures"]} for t in json.load(open(idx_path))["tabs"]}
    except Exception:
        old = {}
for t, figs in INDEX.items():
    old[t] = figs
out = {"label": LABEL, "built": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()), "profile_year": PY,
       "tabs": [{"id": t, "title": title, "figures": list(old[t].values())} for t, title in TABS if t in old]}
json.dump(out, open(idx_path, "w"), indent=1)
print(f"wrote {idx_path}")
