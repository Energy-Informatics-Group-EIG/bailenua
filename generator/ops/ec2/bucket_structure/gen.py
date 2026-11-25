"""Write hrsd/docs/STRUCTURE.md from facts.json (footers), lsjson.json (B2 inventory),
DONE.json, manifests, datasets.yaml and DATASETS.md prose. No Parquet rows are read."""
import collections, json, os, re, sys
import yaml

SP, OUT = sys.argv[1], sys.argv[2]
HRSD = os.path.expanduser("~/hrsd_occupants/hrsd")
RUN = f"{HRSD}/work/replay_2015_2026"
YEARS = [str(y) for y in range(2015, 2027)]
F = json.load(open(f"{SP}/facts.json"))
L = json.load(open(f"{SP}/lsjson.json"))
Y = yaml.safe_load(open(f"{HRSD}/scripts/baile_nua/schema/datasets.yaml"))
YD = Y["datasets"]
DONE = {y: json.load(open(f"{RUN}/{y}/DONE.json")) for y in YEARS}
XR = json.load(open(f"{RUN}/2026/export_report.json"))
DIAG26 = json.load(open(f"{RUN}/2026/pkg/run_diagnostics.json"))
ROWS = F["rows"]

# one-line descriptions: first sentence of each dataset's prose paragraph in DATASETS.md
prose = {}
txt = open(f"{HRSD}/DATASETS.md").read()
for m in re.finditer(r"^## (D\d\d(?:_aggregate)?) · .*?\n\n(.+?)\n", txt, flags=re.M):
    s = m[2].strip()
    prose[m[1]] = re.split(r"(?<=[.])\s", s, 1)[0]

gb = lambda b: f"{b / 1e9:.2f}"
n = lambda x: f"{x:,}"
out = []
w = out.append

# ---------------------------------------------------------------- inventory
pref = collections.defaultdict(lambda: [0, 0, None, None])
for x in L:
    p = x["Path"].split("/")
    k = p[0] + "/" if p[0] != "v1" else f"v1/{p[1]}/"
    t = x["ModTime"][:16].replace("T", " ")
    v = pref[k]; v[0] += 1; v[1] += x["Size"]; v[2] = min(v[2] or t, t); v[3] = max(v[3] or t, t)
v1_n = sum(v[0] for k, v in pref.items() if k.startswith("v1/"))
v1_b = sum(v[1] for k, v in pref.items() if k.startswith("v1/"))
old = pref["HRSD_Occupants/"]
total_n, total_b = len(L), sum(x["Size"] for x in L)
year_files = {y: pref[f"v1/{y}/"] for y in YEARS}

def ds_files(y, ds):
    return [x for x in L if re.match(rf"v1/{y}/\w+/{ds}_part\d+\.parquet$", x["Path"])]

w("""# Baile Nua v1 — bucket structure (`b2eig:hrsd-occupants`)

`v1/docs/V1_BUCKET_STRUCTURE.md`

*Generated 2026-10-19 on the EC2 instance from a read-only `rclone lsjson -R` of the
bucket, the Parquet footers (schema and column statistics only; no rows read),
each year's `DONE.json` and part manifests, `scripts/baile_nua/schema/datasets.yaml`
and the dataset prose in `DATASETS.md`. Local Parquet was used for 2020–2026; for
2015–2019, whose local Parquet was deleted after verification, the footers were
read from B2.*

**Label carried by every dataset:** `UNVALIDATED SIMULATION EVIDENCE: E1 engineering
candidate`. Everything here is synthetic: a simulated town of 1,092 homes and 2,917
people calibrated to Cobh, Co. Cork. No row describes a real person or premises.

## Contents

1. [Bucket overview](#1-bucket-overview)
2. [Path conventions](#2-path-conventions)
3. [Per year](#3-per-year)
4. [Datasets](#4-datasets)
5. [`_segment/` and evidence files](#5-_segment-and-evidence-files)
6. [`docs/`](#6-docs)
7. [Known limitations, in brief](#7-known-limitations-in-brief)
""")

# ---------------------------------------------------------------- 1
w("## 1. Bucket overview\n")
w(f"Before the release documents were added, the bucket held **{n(total_n)} objects, {gb(total_b)} GB**"
  f" (decimal GB, 10⁹ bytes) under two top-level prefixes; `v1/docs/` adds four small Markdown files.\n")
w("| prefix | objects | GB | written (UTC) | what it is |\n|---|---:|---:|---|---|")
w(f"| `v1/` | {n(v1_n)} | {gb(v1_b)} | 2026-10-16 → 2026-10-19 | **The v1 release.** "
  "The 2015 – 30 Sep 2026 replay run on EC2, one folder per simulated year plus `docs/`. "
  "Use this. |")
w(f"| `HRSD_Occupants/` | {old[0]} | {gb(old[1])} | {old[2][:10]} | An older backup snapshot "
  "from the Mac, taken before the replay. **Not a release; do not use for results** (below). |")
w("")
w("### `v1/`\n")
w("| path | objects | GB | written (UTC) |\n|---|---:|---:|---|")
for y in YEARS:
    v = year_files[y]
    w(f"| `v1/{y}/` | {v[0]} | {gb(v[1])} | {v[2]} → {v[3][11:]} |")
w("| `v1/docs/` | 4 | < 0.01 | 2026-10-19 (the release documents, §6; not in the counts below) |")
w(f"| **total (years)** | **{n(v1_n)}** | **{gb(v1_b)}** | |\n")

w("""### `HRSD_Occupants/` — the 12 October snapshot

`HRSD_Occupants/v1-candidate-2026-10-12/` is a **backup snapshot of the Mac working
tree** taken on 12 Oct 2026 at 10:29–10:32 UTC, four days before the EC2 replay
started. Its own `SNAPSHOT.md` labels it *"Backup snapshot. Not a release. Do not
use for results."* It was taken from git HEAD `574e59f` on branch `test`, with a
dirty working tree (51 entries), when the E1 gate stood at FAIL (one stale
criterion), E2 at 5 PASS / 2 FAIL and U31 pending. Its data are a **50-home,
147-person slice** (small areas 047106012 and 047106015, master seed 20261008)
on an engine state before the v1 freeze, so nothing in it is comparable with `v1/`.

| object | bytes | what it holds |
|---|---:|---|""")
desc = {"v1.tar.zst": "the Mac `v1/` tree of the 50-home slice (147 files)",
        "scripts.tar.zst": "`scripts/` (189 files; virtualenv and caches excluded)",
        "docs.tar.zst": "`docs/` (10 files)",
        "sources.tar.zst": "`sources/`: the downloaded source data (131 files, 2.0 GB uncompressed)",
        "work_superseded.tar.zst": "`work/superseded/` only, kept for provenance (109 files)",
        "MANIFEST.sha256": "SHA-256 of every file inside each archive (586) and of the 5 archives",
        "SNAPSHOT.md": "what the snapshot is, git state, gate status, open issues, how to verify"}
for x in sorted((x for x in L if x["Path"].startswith("HRSD_Occupants/")), key=lambda x: x["Path"]):
    name = x["Path"].rsplit("/", 1)[1]
    w(f"| `{name}` | {n(x['Size'])} | {desc.get(name, '')} |")
w("""
Archives are `tar` + `zstd -10`, paths relative to the Mac project root. The
snapshot was verified at creation (586 files + 5 archives, 0 mismatches). It is
kept as provenance for the pre-freeze state; it is not referenced by `v1/`.
""")

# ---------------------------------------------------------------- 2
part_counts = collections.Counter()
for x in L:
    if x["Path"].startswith("v1/") and x["Path"].endswith(".parquet"):
        part_counts["parquet"] += 1
    elif x["Path"].startswith("v1/") and x["Path"].endswith(".manifest.json"):
        part_counts["manifest"] += 1
w("""## 2. Path conventions

```
v1/
├── <year>/                         2015 … 2026, one folder per simulated year
│   ├── ground_truth/               access class GT: never given to a model under test
│   │   ├── <DS>_part<NNN>.parquet
│   │   └── <DS>_part<NNN>.manifest.json
│   ├── observable/                 access class OBS: what a device, respondent,
│   │   └── …                       assessor or operator would see
│   ├── evidence/                   access class META: provenance and calibration
│   │   ├── D22/D23/D24 parts + manifests
│   │   └── plausibility.json       the year's U27 plausibility suite result
│   ├── run_diagnostics.json        the engine's own run record for the year
│   └── _segment/                   run metadata added by the ops layer (§5)
│       ├── DONE.json  ENGINE.json  RUN_DIGESTS.json
│       ├── export_report.json
│       └── verify_segment.log
└── docs/                           release documents (§6)
```

* **A year folder is one simulated calendar year**, 1 Jan 00:00 to 31 Dec 23:59
  UTC, except 2026, which ends on **30 Sep 2026** (273 days). Each year was
  simulated in its own process, continuing from the previous year's final
  checkpoint (warm-up from Dec 2014), with one master seed (20251010).
* **The three packages are the access classes** from `datasets.yaml`:
  `ground_truth/` (GT), `observable/` (OBS), `evidence/` (META). The access class
  of every column is enforced at schema level; observable datasets are keyed by
  `premises_id` (`MPRN-…`), never by person.
* **Part files.** `<DS>_part<NNN>.parquet`, `NNN` zero-padded from `000`, written in
  time order. Datasets the engine streams during the year (D10, D11, D13, D16,
  D17, D17_aggregate, D18, D19) are flushed on every 30th *global* simulated day,
  so a year's first and last parts are partial: 13 parts in most years, 14 in
  2020 (3 + 12 × 30 + 3 days) and 11 in 2026. Datasets written once
  per year by the export post-pass have a single `part000`. **Read a dataset as
  the union of its parts**; parts are not partitions by any key.
* **Every Parquet part has a sibling `.manifest.json`** with `dataset_id`,
  `dataset_name`, `access_class`, `release_package`, `part`, `rows`, `columns`,
  `file_sha256`, `content_hash_sha256`, `schema_version` (1.0.0),
  `design_revision` (3), `schema_conformance` (`full` or `partial`), `streamed`,
  `label`, `calibration_status` and `unmodelled_fields` (column → why it is
  constant, null or approximate).""" + f"""
  Across `v1/` there are {n(part_counts['parquet'])} Parquet parts and
  {n(part_counts['manifest'])} manifests.
* **Time.** Every instant is `timestamp[ns, tz=UTC]`. Calendar dates are
  `date32` (D04 `install_date`, D05 `birth_date`, D21 `as_of`, D24
  `retrieved_at`). Two columns are timezone-naive `timestamp[ns]` only because
  they are entirely null in v1: D05 `death_date` and D30 `rec_pv_install_date`.
  Interval datasets carry `start`/`end` or `interval_start`/`interval_end`, period
  start inclusive; point series carry `ts`. Europe/Dublin views are derived, not
  stored. D18 timestamps include modelled device clock drift, so a year's D18
  can run a few minutes past 31 Dec.
* **Units** (declared in `datasets.yaml`): energy Wh, power W, temperature °C,
  relative humidity %, CO₂ ppm, distance km. Column-name suffixes follow them
  (`_wh`, `_w`, `_c`, `_pct`, `_ppm`, `_kw`, `_m2`, …).
* **Nulls.** Null means not measured or not modelled; zero means measured as zero.
  A required column that the frozen engine cannot populate is written null and
  explained in the part manifest and in `export_report.json` →
  `partially_conformant`.
* **Identifier prefixes:** `P-` person, `H-` household, `B-` building, `A-` asset,
  `V-` venue, `MPRN-` premises (opaque observable key, tied to the property).
* **`v1/docs/`** holds the release documents. They are not per year.
""")

# ---------------------------------------------------------------- 3
w("## 3. Per year\n")
w("Files and GB are what is on B2 under `v1/<year>/` (including `_segment/`). Rows are the "
  "sum of `row_counts` in the year's `DONE.json`, which equal the part manifests.\n")
w("| year | days | files | GB | rows | D18 rows | sim peak RSS, MB | run notes |\n|---|---:|---:|---:|---:|---:|---:|---|")
tot = [0, 0, 0, 0, 0]
for y in YEARS:
    d = DONE[y]; rows = sum(d["row_counts"].values()); v = year_files[y]
    notes = []
    for a in d.get("u27_accepted_exceedances") or []:
        notes.append(f"U27 PL-TEMP-01 FAIL accepted (indoor peak {a['measured']['max_c']} °C > 40 °C)")
    if d.get("rss_gate_exception"):
        notes.append(f"RSS gate exception ({n(round(d['rss_gate_exception']['peak_rss_mb']))} MB > 18,432 MB gate, ≤ 40,960 accepted)")
    if y == "2015":
        notes.append("first attempt OOM-killed in U27; year re-simulated")
    if y == "2019":
        notes.append("D18 starts 2019-10-02")
    if y == "2020":
        notes.append("14 parts per streamed dataset (flush alignment)")
    if y == "2026":
        notes.append("ends 30 Sep 2026; 5 annual U27 checks `NO_DATA` (273 days)")
    if d.get("post_pass_resumed_by") and y not in ("2015",):
        notes.append("post-pass completed by `ops/finish_segment.py`")
    tot[0] += d["days"]; tot[1] += v[0]; tot[2] += v[1]; tot[3] += rows; tot[4] += d["row_counts"].get("D18", 0)
    w(f"| {y} | {d['days']} | {v[0]} | {gb(v[1])} | {n(rows)} | {n(d['row_counts'].get('D18', 0))} | "
      f"{n(round(d['peak_rss_mb']))} | {'; '.join(notes) or '—'} |")
w(f"| **total** | **{n(tot[0])}** | **{n(tot[1])}** | **{gb(tot[2])}** | **{n(tot[3])}** | **{n(tot[4])}** | | |\n")
w("""Every year: one engine (`v1-engine-freeze-2.3`, code digest `05328f32a44b8c94…`,
config digest `e0ab1c8351e1e153…`), checkpoint chain verified, 18 datasets
written and 0 failed by the export, secret and personal-data scan clean,
`verify_segment.py` PASS, and `rclone check` 0 differences after upload. U27 ran
12 checks: 10 pass and 2 not evaluable (PL-APPLSHARE-01, PL-EVHP-01: no reference)
in 2015–2019 and 2021–2023; 9 pass, 1 accepted FAIL and 2 not evaluable in 2020,
2024 and 2025; and in **2026, 5 pass, 2 not evaluable and 5 `NO_DATA`**, because
PL-DHW-01, PL-ELEC-01, PL-GAS-01, PL-MIX-01 and PL-PEAK-01 compare annual
quantities and need at least 350 days, and 2026 has 273. The U27 suite does not
extrapolate a partial year. Rows grow from 2021 because D18 grows with smart-meter rollout
and the 1-minute study enrolment.

**The two operational exceptions** (both ops-only, engine and config unchanged,
approved by Brian O'Regan and recorded in the year's `_segment/DONE.json`):

* **PL-TEMP-01** (2020, 2024, 2025): the U27 indoor-temperature check fails when
  any living-zone epoch exceeds 40 °C, a declared ceiling with no published
  source. It was accepted only while the peak stays ≤ 45 °C, the median within
  17.80–20.01 °C and the share above 28 °C ≤ 0.5 % (`u27_accepted_exceedances`).
  The package's `evidence/plausibility.json` still reports the FAIL.
* **Peak-RSS gate** (2023–2026): the supervisor's year check fails a year whose
  simulation peak memory exceeds 18,432 MB. Peak memory grows with D18 1-minute
  coverage. Accepted up to 40,960 MB as an operational exception with no output
  impact (`rss_gate_exception`).
""")

# ---------------------------------------------------------------- 4
GLOSS = {
    "ts": "instant of the row (UTC)", "start": "interval start (UTC, inclusive)", "end": "interval end (UTC)",
    "interval_start": "interval start (UTC, inclusive)", "interval_end": "interval end (UTC)",
    "valid_from": "start of the validity interval (UTC)", "valid_to": "end of the validity interval; null = still valid",
    "building_id": "building key (`B-`)", "person_id": "person key (`P-`)", "household_id": "household key (`H-`)",
    "premises_id": "premises key (`MPRN-`), the observable side of the meter boundary", "asset_id": "asset key (`A-`)",
    "estate_id": "estate the building belongs to", "version": "row version, bumped by a change event",
    "seed": "RNG seed the row was drawn with", "quality": "quality flag", "provenance": "how the value was obtained",
    "unit": "unit of `value` on this row", "value": "the value, in the row's `unit`", "realisation_id": "weather realisation the row belongs to",
    "segment": "which weather segment the row comes from", "revision": "data revision number",
}
GLOSS.update({
    "geometry_wkt": "feature geometry as WKT", "feeder_id": "LV feeder the feature is on",
    "build_year": "year of construction", "floor_area_m2": "floor area", "storeys": "number of storeys",
    "archetype_id": "building archetype the fabric was drawn from", "ber_kwh_m2_yr": "BER primary energy rating",
    "heating_system": "heating system type", "sri_score": "smart readiness indicator score",
    "rc_c_living": "F1 RC model: living-zone heat capacity", "rc_c_sleep": "F1 RC model: sleeping-zone heat capacity",
    "rc_c_env": "F1 RC model: envelope heat capacity", "rc_solar_aperture_m2": "F1 RC model: effective solar aperture",
    "rc_vol_living_m3": "F1 RC model: living-zone air volume", "rc_vol_sleep_m3": "F1 RC model: sleeping-zone air volume",
    "dhw_tank_litres": "hot water cylinder volume", "rated_power_w": "rated electrical power",
    "capacity": "capacity (asset-specific: e.g. battery or vehicle energy, venue places)", "efficiency": "rated efficiency",
    "pv_azimuth_deg": "PV array azimuth", "pv_tilt_deg": "PV array tilt", "family_name": "synthetic family name",
    "birth_date": "date of birth (synthetic)", "other_languages": "other languages (ISO 639-1)",
    "big5_o": "Big Five: openness", "big5_c": "Big Five: conscientiousness", "big5_e": "Big Five: extraversion",
    "big5_a": "Big Five: agreeableness", "big5_n": "Big Five: neuroticism",
    "habit_strength": "strength of routine (habit) in activity choice", "lapse_rate": "rate of lapses from routine",
    "attention": "propensity to deliberate over a choice rather than follow habit", "membership_id": "membership spell key", "reason_out": "why the spell ended",
    "edge_id": "edge key", "person_a": "one end of the edge (`P-`)", "person_b": "other end of the edge (`P-`)",
    "state_id": "state spell key", "workplace_venue_id": "workplace venue (`V-`)", "remote_share": "share of work done remotely",
    "school_venue_id": "school venue (`V-`)", "school_year": "school year", "caring_hours_week": "hours of care given per week",
    "decision_authority": "share of household decision authority: 1/n for each of n adults, 0 for children", "income_quintile": "household income quintile",
    "activity_id": "activity interval key", "location_id": "where the person is (building or venue key)",
    "joint_with": "co-participants (`P-` list)", "presence_id": "presence interval key", "cycle_id": "appliance cycle key",
    "signature_id": "waveform template (D22)", "energy_wh": "energy used by the cycle", "peak_w": "peak power in the cycle",
    "flexible": "whether the cycle could be shifted", "shifted_by_min": "minutes the cycle was shifted by a signal",
    "instance_id": "event instance key", "footprint_ids": "keys of the buildings/venues the event touches",
    "site_id": "weather site", "temp_air_c": "air temperature", "rh_pct": "relative humidity", "wind_speed_ms": "wind speed",
    "wind_dir_deg": "wind direction", "ghi_w_m2": "global horizontal irradiance", "dni_w_m2": "direct normal irradiance",
    "dhi_w_m2": "diffuse horizontal irradiance", "solar_zenith_deg": "solar zenith angle", "solar_azimuth_deg": "solar azimuth angle",
    "sunrise_utc": "sunrise that day (UTC)", "sunset_utc": "sunset that day (UTC)", "precip_mm": "precipitation in the interval",
    "temp_living_c": "living-zone air temperature", "temp_sleep_c": "sleeping-zone air temperature",
    "temp_env_c": "envelope (fabric) node temperature of the RC model", "co2_living_ppm": "living-zone CO₂", "co2_sleep_ppm": "sleeping-zone CO₂",
    "dhw_tank_c": "hot water cylinder temperature", "heat_delivered_w": "heat delivered by the heating system",
    "internal_gain_w": "internal heat gains (people, appliances)", "solar_gain_w": "solar heat gain",
    "occupants_living": "people in the living zone", "occupants_sleep": "people in the sleeping zone",
    "element_id": "network element (feeder or transformer)", "p_kw": "active power", "q_kvar": "reactive power",
    "voltage_pu": "voltage", "loading_pct": "loading against rating", "outage": "element out of service",
    "as_of": "date the narrative describes", "appliance_type": "appliance type", "programme": "appliance programme",
    "source_licence": "licence of the source", "template_hz": "template sample rate", "template_w": "template power trace",
    "duration_s": "nominal duration", "energy_wh_nominal": "nominal energy per cycle",
    "var_duration_cv": "coefficient of variation of duration", "ageing_power_per_year": "power drift per year of age",
    "run_id": "run key", "created_at_utc": "when the record was written", "code_version": "engine version label",
    "code_git_sha": "engine commit", "schema_version": "schema version", "design_revision": "design revision",
    "master_seed": "the run's master seed", "parameters": "run parameters (JSON)", "checkpoint_chain_head": "head of the checkpoint hash chain",
    "target_id": "target key", "statistic": "the statistic the target is for", "source_sha256": "SHA-256 of the source file",
    "source_url": "where the source was retrieved", "retrieved_at": "when the source was retrieved",
})

SUFFIX = [("_kwh_m2_yr", "kWh/m²/yr"), ("_w_m2", "W/m²"), ("_eur_kwh", "EUR/kWh"), ("_eur_day", "EUR/day"),
          ("_kwh", "kWh"), ("_wh", "Wh"), ("_kwp", "kWp"), ("_kva", "kVA"), ("_kvar", "kvar"), ("_kw", "kW"),
          ("_w", "W"), ("_c", "°C"), ("_pct", "%"), ("_ppm", "ppm"), ("_m2", "m²"), ("_m3", "m³"), ("_mm", "mm"),
          ("_litres", "L"), ("_speed_ms", "m/s"), ("_s", "s"), ("_hz", "Hz"), ("_deg", "degrees"), ("_pu", "per unit"),
          ("_hours_week", "h/week"), ("_hours", "h"), ("_by_min", "min"), ("_days", "days"), ("_years", "years"),
          ("_years_at_t0", "years"), ("_rated_a", "A")]
YUNIT = {"degC": "°C", "percent": "%"}

def unit_of(col, f):
    if f and f.get("unit"):
        return YUNIT.get(f["unit"], f["unit"])
    for s, u in SUFFIX:
        if col.endswith(s):
            return u + " *(name)*"
    return ""

KEYS = {
    "D01": "`feature_id`, `valid_from`", "D02": "`building_id`, `version`", "D04": "`asset_id`, `version`",
    "D05": "`person_id`", "D06": "`membership_id`", "D07": "`edge_id`", "D08": "`state_id` (`person_id` × validity)",
    "D10": "`activity_id`", "D11": "`presence_id`", "D13": "`cycle_id`", "D14": "`instance_id`, `phase`",
    "D15": "`ts`, `site_id`", "D16": "`building_id`, `ts`", "D17": "`element_id`, `ts`",
    "D17_aggregate": "`record_kind`, `premises_id` / `feeder_ref` / `substation_ref`, `ts`",
    "D18": "`device_id`, `channel`, `ts`", "D19": "`premises_id`, `export_config`, `interval_start`",
    "D21": "`person_id`, `as_of`", "D22": "`signature_id`", "D23": "`run_id`", "D24": "`target_id`",
    "D27": "`premises_id`, `valid_from`", "D28": "`premises_id`, `protocol_event`, `recorded_at`",
    "D29": "`premises_id`, `wave`", "D30": "`premises_id`, `record_version`", "D31": "`series_id`, `ts`",
}
GRAIN = {
    "D01": "one row per geographic feature (parcel, street, venue, feeder, transformer)",
    "D02": "building × version; 1,092 buildings, one version each in v1",
    "D04": "asset × version", "D05": "one row per person (2,917)", "D06": "person × household membership spell",
    "D07": "one row per relationship edge", "D08": "person × state spell (SCD-2)",
    "D10": "person × activity interval, minute boundaries; about 74 per home-day",
    "D11": "person × location interval, minute boundaries; **first 14 days of each year only**",
    "D13": "appliance cycle; about 81 per home-day",
    "D14": "event instance × phase", "D15": "site × **1 minute** (1,440 rows per day)",
    "D16": "building × **15 minutes** (96 rows per building-day), the network epoch; the schema declares 1 minute",
    "D17": "network element × **15 minutes**: 117 elements (64 feeders, 53 transformers/substations)",
    "D17_aggregate": "record × 15 minutes: the connection register (one row per premises) plus feeder-head and substation measurements",
    "D18": "device × channel × device-native interval: 30-minute import/export in the smart-meter era, 1-minute (and event-driven) channels for enrolled homes",
    "D19": "premises × interval × export configuration: `compliance_only` (30 min), `home_15min` (15 min) and one `estate_aggregate` series",
    "D21": "person × as-of date", "D22": "one row per appliance waveform template", "D23": "one row per run (the year)",
    "D24": "one row per empirical target", "D27": "premises × tariff spell", "D28": "premises × recruitment protocol event",
    "D29": "premises × questionnaire wave", "D30": "premises × recorded version",
    "D31": "series × timestamp: 8 hourly station series from Roches Point (real historical weather)",
}
ERA = {
    "D18": "**Era-gated** (`d18_era_gating: true`): rows only for home-days in a device era. "
           "First smart-meter install **2019-10-02**, last 2025-08-29; 906 of 1,092 homes ever metered; "
           "first 1-minute study enrolment 2021-01-05, 328 homes ever enrolled. 2015–2018 have no D18; "
           "2019 starts on 2019-10-02.",
    "D11": "Presence is collected for the **first 14 days** of each year only (`collect_presence_days`), "
           "1 Jan 00:00 to 14 Jan 23:59.",
}
ORDER = ["D%02d" % i for i in range(1, 32)]
ORDER.insert(ORDER.index("D18"), "D17_aggregate")
absent = {k: v for k, v in XR["datasets"].items() if v.get("verdict") == "not written"}
pc = XR.get("partially_conformant") or {}

w("## 4. Datasets\n")
w("D01–D31 as declared in `datasets.yaml` (design revision 3, schema 1.0.0), plus "
  "`D17_aggregate`, D17's observable view. **26 datasets are in `v1/`** (25 in 2015–2018, "
  "before D18 exists); **6 are absent from every year** (D03, D09, D12, D20, D25, D26).\n")
w("### 4.1 Index\n")
w("| ID | name | package | parts / year | rows 2015 | rows 2025 | rows 2015–2026 | status |\n|---|---|---|---|---:|---:|---:|---|")
for ds in ORDER:
    y = YD.get(ds, {})
    if ds in F["datasets"]:
        yrs = F["datasets"][ds]
        pcs = sorted({v["parts"] for v in yrs.values()})
        allr = sum(ROWS[yy].get(ds, 0) for yy in YEARS)
        w(f"| [{ds}](#{ds.lower()}) | `{y.get('name')}` | {yrs[max(yrs)]['category']} | "
          f"{'–'.join(map(str, [pcs[0], pcs[-1]])) if len(pcs) > 1 else pcs[0]} | {n(ROWS['2015'].get(ds, 0))} | "
          f"{n(ROWS['2025'].get(ds, 0))} | {n(allr)} | present{' from 2019' if ds == 'D18' else ''} |")
    else:
        w(f"| [{ds}](#{ds.lower()}) | `{y.get('name')}` | ({Y['access_classes'][y['access_class']]['released_in']}) | — | — | — | — | **absent** |")
w("")
w("### 4.2 Rows per year\n")
pres = [ds for ds in ORDER if ds in F["datasets"]]
w("| dataset | " + " | ".join(YEARS) + " |\n|---|" + "---:|" * len(YEARS))
for ds in pres:
    w(f"| {ds} | " + " | ".join(n(ROWS[yy].get(ds, 0)) for yy in YEARS) + " |")
w("")
w("### 4.3 Absent datasets\n")
w("Each absence is recorded, with its reason, in every year's `_segment/export_report.json` "
  "(`datasets.<ID>.verdict = \"not written\"`). They are absences by design of the frozen engine, not "
  "export failures.\n")
w("| ID | name | why absent |\n|---|---|---|")
why = {
    "D03": "Built from `evidence/wp5_tenyear.json`, which only a run that steps the ten-year life course writes. The replay steps none, so no passport event exists.",
    "D09": "Same artefact and cause as D03.",
    "D20": "Same artefact and cause as D03.",
    "D12": "No trip row survives the day: the engine computes travel only for EV state of charge; there is no trips output or D12 buffer.",
    "D25": "Owned by the MIMIC exporter, not by this package.",
    "D26": "Owned by the MIMIC exporter, not by this package.",
}
for ds in ["D03", "D09", "D12", "D20", "D25", "D26"]:
    w(f"| <a id=\"{ds.lower()}\"></a>{ds} | `{YD[ds]['name']}` — {YD[ds]['title']} | {why[ds]} |")
w("\nSee `V1_KNOWN_LIMITATIONS.md` §2 for the detail.\n")

w("### 4.4 Present datasets\n")
w("For each: what it is, its grain and key, where it lives, and its full schema. **Type** is the "
  "Parquet/Arrow type on disk. **Unit** comes from `datasets.yaml` where declared, otherwise from the "
  "column-name suffix, marked *(name)*. **Meaning** is the field's note or observation mechanism from "
  "`datasets.yaml`; ⚠ marks a caveat from the part manifest (`unmodelled_fields`) or the export's "
  "`partially_conformant` record. The schema is identical in every year unless stated. Keys are the "
  "natural key implied by the grain; the writer does not enforce uniqueness.\n")

def esc(s):
    return str(s).replace("|", "\\|").replace("\n", " ")

def first_sentence(s, lim=300):
    s = esc(s).strip()
    s = re.split(r"(?<=[.])\s", s, 1)[0]
    return s if len(s) <= lim else s[:lim].rsplit(" ", 1)[0] + " …"

man = F["manifests"]
for ds in pres:
    y = YD.get(ds, {}); yrs = F["datasets"][ds]; last = yrs[max(yrs)]
    fields = {f["name"]: f for f in y.get("fields", [])}
    unm = {}
    for yy, m in man.get(ds, {}).items():
        unm.update(m.get("unmodelled_fields") or {})
    conf = sorted({m.get("schema_conformance") for m in man.get(ds, {}).values()} - {None})
    first_year = min(yrs)
    w(f"<a id=\"{ds.lower()}\"></a>\n#### {ds} · `{y.get('name')}` — {y.get('title')}\n")
    pr = prose.get(ds, "")
    if ds == "D16":
        pr = pr.replace("at minute resolution", "(written every 15 minutes by design, `D16_EPOCH_MINUTES`; the solver itself steps at 1 minute)")
    w(f"{pr}\n")
    pcs = collections.Counter(v["parts"] for v in yrs.values())
    pc_txt = ", ".join(f"{k} part{'s' if k > 1 else ''} in {c} year{'s' if c > 1 else ''}" for k, c in sorted(pcs.items(), key=lambda t: -t[1]))
    gbytes = sum(v["bytes"] for v in yrs.values())
    w("| | |\n|---|---|")
    w(f"| access class / package | {y.get('access_class')} / `{last['category']}/` |")
    w(f"| grain | {GRAIN.get(ds, y.get('grain'))} (declared: *{esc(y.get('grain'))}*) |")
    w(f"| key | {KEYS.get(ds, '—')} |")
    w(f"| path | `v1/<year>/{last['category']}/{ds}_part<NNN>.parquet` |")
    w(f"| parts | {pc_txt} |")
    w(f"| rows | {n(sum(ROWS[yy].get(ds, 0) for yy in YEARS))} over {len(yrs)} years; per year in §4.2 |")
    w(f"| size on B2 | {gb(gbytes)} GB over {len(yrs)} years |")
    w(f"| years present | {first_year}–2026{' (era-gated)' if ds == 'D18' else ''} |")
    if ds in ERA:
        w(f"| coverage | {ERA[ds]} |")
    w(f"| schema conformance | {', '.join(conf) or '—'} |")
    tsr = yrs["2025"]["ts"] if "2025" in yrs else {}
    if tsr:
        c0 = next(iter(tsr)); w(f"| time span, 2025 (`{c0}`) | {tsr[c0][0][:19]} → {tsr[c0][1][:19]} |")
    if ds == "D14":
        w("| schema note | `attendance_prob` is `struct<adult, child, visitors>` in every year except **2022**, where it is `struct<all, child, adult, visitors>` |")
    w("")
    w("| column | type | unit | req. | meaning |\n|---|---|---|---|---|")
    for col, typ in last["schema"]:
        f = fields.get(col)
        mean = ""
        if f:
            mean = f.get("notes") or f.get("mechanism") or ""
            if f.get("type") == "enum" and f.get("enum"):
                vals = Y["enums"].get(f["enum"])
                if vals:
                    mean = (mean + "; " if mean else "") + "one of: " + ", ".join(map(str, vals))
            if f.get("gt_counterpart"):
                mean += f" (observes {f['gt_counterpart']})"
        if f and f.get("mimic_trait") and not mean:
            mean = "MIMIC latent trait (same name and scale as the MIMIC generator)"
        mean = mean or GLOSS.get(col, "")
        if ds == "D18" and col == "channel":
            mean += ("; on disk: `import_w`, `export_w` (meter era, 30 min) and, for enrolled homes, `ct_circuit`, "
                     "`charger_w`, `inverter_w`, `temp`, `rh`, `co2`, `pir`")
        if ds == "D18" and col == "value":
            mean += "; unit in the row's `unit` column"
        cav = unm.get(col) or (pc.get(ds) or {}).get(col)
        if cav:
            mean = (esc(mean) + " " if mean else "") + "⚠ " + first_sentence(cav)
        req = "yes" if f and f.get("required") else ("no" if f else "")
        w(f"| `{col}` | {esc(typ)} | {unit_of(col, f)} | {req} | {esc(mean) or '—'} |")
    w("")

# ---------------------------------------------------------------- 5
d26 = DONE["2026"]
w("## 5. `_segment/` and evidence files\n")
w("### `_segment/` (added by the ops layer when the year was uploaded)\n")
w("| file | what it is |\n|---|---|")
w("| `DONE.json` | the year's completion record (fields below) |")
w("| `ENGINE.json` | engine identity for the year: `segment`, `engine_tag`, `code_digest`, `conf_digest`, `d18_era_gating`, `written_before_export` |")
w("| `RUN_DIGESTS.json` | the run-wide engine identity the year must match: `code_digest`, `conf_digest`, `master_seed`, `note` |")
w("| `export_report.json` | the export post-pass report: per-dataset verdict and reason, written/failed lists, totals, absent datasets, null-required fields |")
w("| `verify_segment.log` | output of `scripts/verify_segment.py`: DONE, chain, checkpoints, D11, D15 `is_dst`, scan, rows vs manifests → PASS |")
w("")
w("**`DONE.json`** fields:\n")
w("| field | meaning |\n|---|---|")
DF = [("segment", "the year"), ("days", "simulated days"), ("sim_day", "[first, last] global simulated day"),
      ("wall_h", "wall-clock hours for the year"), ("s_per_day", "seconds per simulated day"),
      ("peak_rss_mb", "simulation-phase peak memory, MB"), ("row_counts", "rows per dataset (equals the part manifests)"),
      ("chain_verify", "\"chain verified\" when the checkpoint hash chain verified"),
      ("export_written / export_failed", "datasets written by the export post-pass (18) and failed (0)"),
      ("scan", "secret/personal-data scan: `clean`, `hits`"), ("discarded", "true only for the discarded warm-up"),
      ("finished", "completion time (UTC)"), ("code_digest / conf_digest", "engine and configuration digests"),
      ("master_seed", "20251010, one for the whole run (D-133)"),
      ("seed_of_record / seed_of_record_note", "a per-year hash for provenance only; not passed to the model"),
      ("b2_upload, provisional", "constants, not run state: `b2_upload` reads \"SKIPPED - no credential …\" in years the supervisor finished and \"handled by ~/hrsd_occupants/ops/post_year.sh\" in years the ops layer finished; `provisional` is always true. Every year was uploaded and checked"),
      ("u27_accepted_exceedances", "present only in 2020, 2024, 2025: the accepted PL-TEMP-01 failure, measured values and bounds"),
      ("rss_gate_exception", "present only in 2023–2026: peak, gate, accepted maximum, approval"),
      ("post_pass_resumed_by", "present where the ops layer completed the post-pass after the simulation")]
for k, v in DF:
    w(f"| `{k}` | {v} |")
w("\nExample (2026, abridged):\n")
ex = {k: d26[k] for k in ("segment", "days", "sim_day", "wall_h", "s_per_day", "peak_rss_mb", "chain_verify",
                          "export_written", "export_failed", "finished", "master_seed", "seed_of_record")}
ex["row_counts"] = {k: d26["row_counts"][k] for k in ("D16", "D18", "D19")} | {"…": "…"}
ex["code_digest"] = d26["code_digest"][:16] + "…"
ex["rss_gate_exception"] = {k: d26["rss_gate_exception"][k] for k in ("peak_rss_mb", "gate_mb", "accepted_max_mb")} | {"approved": "…"}
w("```json\n" + json.dumps(ex, indent=2, ensure_ascii=False) + "\n```\n")

w("### `run_diagnostics.json` (pkg root, written by the engine)\n")
w("Top-level fields: " + ", ".join(f"`{k}`" for k in DIAG26) + ".\n")
w("The ones most used: `benchmark` (machine, `n_homes`, `n_people`, `n_days`, per-day timings, "
  "`peak_rss_mb`, `storage.by_dataset`, `d18_era` with home-days by era and the rollout record), "
  "`max_physics_relative_residual` and `max_energy_closure_relative_residual` (solver closure), "
  "`checkpoint_chain_head`, `plausibility` (the U27 summary), `annual_electricity`, `feeder_peak_w`, "
  "`mary` (the design 5.9 move-in scenario) and `network_claim`/`coupling_mode`.\n")
era = DIAG26["benchmark"]["d18_era"]
w("Example (`benchmark.d18_era`, 2026):\n")
w("```json\n" + json.dumps({k: era[k] for k in ("home_days_by_era", "n_ever_metered", "first_install", "last_install",
                                                  "first_enrolment", "meter_era_channels", "meter_era_interval_s")}, indent=2) + "\n```\n")
w("### `evidence/plausibility.json` (U27)\n")
pl = json.load(open(f"{RUN}/2025/pkg/evidence/plausibility.json"))
w("Summary fields: " + ", ".join(f"`{k}`" for k in pl if k != "results") + ".\n")
w("`results` holds one record per check (12) with `check_id`, `quantity`, `family`, `outcome` "
  "(`PASS`, `FAIL`, `NOT_EVALUABLE`, `NO_DATA`), `sourced`, `measured`, `reference`, `source_key`, "
  "`source_sha256`, `source_exposure`, `tolerance`, `tolerance_basis`, `detail` and `note` "
  "(why a check could not be evaluated). The checks: "
  + ", ".join(f"`{r['check_id']}`" for r in pl["results"]) + ".\n")
r = next(r for r in pl["results"] if r["check_id"] == "PL-TEMP-01")
w("Example (2025, PL-TEMP-01, abridged):\n")
w("```json\n" + json.dumps({k: r.get(k) for k in ("check_id", "quantity", "family", "outcome", "sourced", "measured", "tolerance")},
                         indent=2, ensure_ascii=False) + "\n```\n")
w("### `evidence/` Parquet (D22, D23, D24)\n")
w("D22 (appliance waveform templates), D23 (the run's identity record: code, schema, seed, parameters, "
  "outputs, checkpoint chain head) and D24 (every empirical target with source, version and tolerance) are "
  "datasets like the others; their schemas are in §4.\n")

# ---------------------------------------------------------------- 6
w("## 6. `docs/`\n")
w("| file | purpose |\n|---|---|")
w("| `RELEASE_NOTES_v1.md` | what v1 is, per-year figures, how it was run, the checks, and the accepted exceptions |")
w("| `PROVENANCE.md` | run provenance (engine tag, digests, seed, inputs, environment, each year's chain head) and dataset provenance (sources, licences, transforms) |")
w("| `V1_KNOWN_LIMITATIONS.md` | everything v1 does not do, or does with a caveat, and what is carried to v2 |")
w("| `V1_BUCKET_STRUCTURE.md` | this file: what is in the bucket and how it is laid out |")
w("")

# ---------------------------------------------------------------- 7
w("""## 7. Known limitations, in brief

The full list, with evidence, is `V1_KNOWN_LIMITATIONS.md` in `v1/docs/`. The
ones that change how the data should be read:

1. **The population does not change with the simulated year.** Every year has the
   same 1,092 homes and 2,917 people, synthesised for a 2022 origin, so estates
   completed after a given year still draw load in it.
2. **Six datasets are absent** (D03, D09, D12, D20, D25, D26; §4.3).
3. **D18 exists only from 2019-10-02 and is era-gated** by smart-meter rollout and
   1-minute study enrolment, so its volume grows each year.
4. **D11 covers the first 14 days of each year only**, so D29 and D30, which read
   it, describe 14 days, not a year.
5. **D16 is sampled every 15 minutes by design**, not at the declared 1 minute
   (the thermal time constants are 15–140 h), and `rh_living_pct` is a
   constant (no moisture balance); `ach_effective` includes purge ventilation, not
   occupant window opening.
6. **Accepted U27 exceedance:** PL-TEMP-01's 40 °C indoor ceiling is unsourced;
   its failure was accepted in 2020, 2024 and 2025 within bounds (§3). In 2026,
   five annual U27 checks return `NO_DATA` because the year has 273 days.
7. **Peak-RSS gate exception** for 2023–2026 (§3): a resource guard, not a result
   check; no output is affected.
8. **Two `DONE.json` fields are constants, not run state:** `b2_upload` says
   "SKIPPED" in the years the frozen supervisor finished, and `provisional` is
   always true, yet every year was uploaded and checked (the evidence is each
   year's `_segment/` on B2).
9. **Some required columns are null by construction** where the frozen engine has
   no model for them (for example D04 `failure_hazard_scale`); each is explained in
   the part manifest and `export_report.json`.
10. Nothing here is validated against behaviour: the label *UNVALIDATED SIMULATION
    EVIDENCE: E1 engineering candidate* applies to every file.
""")

open(OUT, "w").write("\n".join(out) + "\n")
print(OUT, len(out), "blocks", os.path.getsize(OUT), "bytes")
