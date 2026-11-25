# Baile Nua v1 — bucket structure (`b2eig:hrsd-occupants`)

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

## 1. Bucket overview

Before the release documents were added, the bucket held **2,607 objects, 81.76 GB** (decimal GB, 10⁹ bytes) under two top-level prefixes; `v1/docs/` adds four small Markdown files.

| prefix | objects | GB | written (UTC) | what it is |
|---|---:|---:|---|---|
| `v1/` | 2,600 | 80.01 | 2026-10-16 → 2026-10-19 | **The v1 release.** The 2015 – 30 Sep 2026 replay run on EC2, one folder per simulated year plus `docs/`. Use this. |
| `HRSD_Occupants/` | 7 | 1.74 | 2026-10-12 | An older backup snapshot from the Mac, taken before the replay. **Not a release; do not use for results** (below). |

### `v1/`

| path | objects | GB | written (UTC) |
|---|---:|---:|---|
| `v1/2015/` | 201 | 5.88 | 2026-10-16 15:38 → 19:42 |
| `v1/2016/` | 201 | 5.90 | 2026-10-16 19:55 → 00:01 |
| `v1/2017/` | 201 | 5.88 | 2026-10-17 00:12 → 04:23 |
| `v1/2018/` | 203 | 5.89 | 2026-10-17 04:29 → 08:43 |
| `v1/2019/` | 211 | 5.88 | 2026-10-17 08:46 → 13:04 |
| `v1/2020/` | 243 | 5.93 | 2026-10-17 13:03 → 19:29 |
| `v1/2021/` | 227 | 6.28 | 2026-10-17 19:37 → 23:58 |
| `v1/2022/` | 227 | 6.88 | 2026-10-18 00:10 → 05:19 |
| `v1/2023/` | 227 | 7.52 | 2026-10-18 05:23 → 13:53 |
| `v1/2024/` | 229 | 8.18 | 2026-10-18 14:08 → 21:18 |
| `v1/2025/` | 229 | 8.81 | 2026-10-18 21:15 → 05:22 |
| `v1/2026/` | 201 | 6.99 | 2026-10-19 05:16 → 11:43 |
| `v1/docs/` | 4 | < 0.01 | 2026-10-19 (the release documents, §6; not in the counts below) |
| **total (years)** | **2,600** | **80.01** | |

### `HRSD_Occupants/` — the 12 October snapshot

`HRSD_Occupants/v1-candidate-2026-10-12/` is a **backup snapshot of the Mac working
tree** taken on 12 Oct 2026 at 10:29–10:32 UTC, four days before the EC2 replay
started. Its own `SNAPSHOT.md` labels it *"Backup snapshot. Not a release. Do not
use for results."* It was taken from git HEAD `574e59f` on branch `test`, with a
dirty working tree (51 entries), when the E1 gate stood at FAIL (one stale
criterion), E2 at 5 PASS / 2 FAIL and U31 pending. Its data are a **50-home,
147-person slice** (small areas 047106012 and 047106015, master seed 20261008)
on an engine state before the v1 freeze, so nothing in it is comparable with `v1/`.

| object | bytes | what it holds |
|---|---:|---|
| `MANIFEST.sha256` | 68,128 | SHA-256 of every file inside each archive (586) and of the 5 archives |
| `SNAPSHOT.md` | 5,642 | what the snapshot is, git state, gate status, open issues, how to verify |
| `docs.tar.zst` | 1,418,679 | `docs/` (10 files) |
| `scripts.tar.zst` | 776,566 | `scripts/` (189 files; virtualenv and caches excluded) |
| `sources.tar.zst` | 450,322,651 | `sources/`: the downloaded source data (131 files, 2.0 GB uncompressed) |
| `v1.tar.zst` | 644,105,653 | the Mac `v1/` tree of the 50-home slice (147 files) |
| `work_superseded.tar.zst` | 643,587,921 | `work/superseded/` only, kept for provenance (109 files) |

Archives are `tar` + `zstd -10`, paths relative to the Mac project root. The
snapshot was verified at creation (586 files + 5 archives, 0 mismatches). It is
kept as provenance for the pre-freeze state; it is not referenced by `v1/`.

## 2. Path conventions

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
  constant, null or approximate).
  Across `v1/` there are 1,258 Parquet parts and
  1,258 manifests.
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

## 3. Per year

Files and GB are what is on B2 under `v1/<year>/` (including `_segment/`). Rows are the sum of `row_counts` in the year's `DONE.json`, which equal the part manifests.

| year | days | files | GB | rows | D18 rows | sim peak RSS, MB | run notes |
|---|---:|---:|---:|---:|---:|---:|---|
| 2015 | 365 | 201 | 5.88 | 186,527,871 | 0 | 9,465 | first attempt OOM-killed in U27; year re-simulated |
| 2016 | 366 | 201 | 5.90 | 187,049,268 | 0 | 9,468 | — |
| 2017 | 365 | 201 | 5.88 | 186,528,345 | 0 | 9,446 | — |
| 2018 | 365 | 203 | 5.89 | 186,497,378 | 0 | 9,406 | — |
| 2019 | 365 | 211 | 5.88 | 186,680,145 | 216,754 | 9,441 | D18 starts 2019-10-02 |
| 2020 | 366 | 243 | 5.93 | 192,147,037 | 5,201,585 | 9,809 | U27 PL-TEMP-01 FAIL accepted (indoor peak 41.15 °C > 40 °C); 14 parts per streamed dataset (flush alignment); post-pass completed by `ops/finish_segment.py` |
| 2021 | 365 | 227 | 6.28 | 234,267,835 | 47,850,813 | 13,177 | — |
| 2022 | 365 | 227 | 6.88 | 309,479,811 | 123,091,117 | 18,331 | — |
| 2023 | 365 | 227 | 7.52 | 387,630,902 | 201,141,005 | 23,716 | RSS gate exception (23,716 MB > 18,432 MB gate, ≤ 40,960 accepted); post-pass completed by `ops/finish_segment.py` |
| 2024 | 366 | 229 | 8.18 | 469,171,131 | 282,188,959 | 28,997 | U27 PL-TEMP-01 FAIL accepted (indoor peak 41.38 °C > 40 °C); RSS gate exception (28,997 MB > 18,432 MB gate, ≤ 40,960 accepted); post-pass completed by `ops/finish_segment.py` |
| 2025 | 365 | 229 | 8.81 | 547,936,032 | 361,444,721 | 34,259 | U27 PL-TEMP-01 FAIL accepted (indoor peak 43.3 °C > 40 °C); RSS gate exception (34,259 MB > 18,432 MB gate, ≤ 40,960 accepted); post-pass completed by `ops/finish_segment.py` |
| 2026 | 273 | 201 | 6.99 | 459,898,507 | 320,525,256 | 38,103 | RSS gate exception (38,103 MB > 18,432 MB gate, ≤ 40,960 accepted); ends 30 Sep 2026; 5 annual U27 checks `NO_DATA` (273 days); post-pass completed by `ops/finish_segment.py` |
| **total** | **4,291** | **2,600** | **80.01** | **3,533,814,262** | **1,341,660,210** | | |

Every year: one engine (`v1-engine-freeze-2.3`, code digest `05328f32a44b8c94…`,
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

## 4. Datasets

D01–D31 as declared in `datasets.yaml` (design revision 3, schema 1.0.0), plus `D17_aggregate`, D17's observable view. **26 datasets are in `v1/`** (25 in 2015–2018, before D18 exists); **6 are absent from every year** (D03, D09, D12, D20, D25, D26).

### 4.1 Index

| ID | name | package | parts / year | rows 2015 | rows 2025 | rows 2015–2026 | status |
|---|---|---|---|---:|---:|---:|---|
| [D01](#d01) | `town_geo` | ground_truth | 1 | 206 | 206 | 2,472 | present |
| [D02](#d02) | `buildings` | ground_truth | 1 | 1,092 | 1,092 | 13,104 | present |
| [D03](#d03) | `building_passport` | (ground_truth) | — | — | — | — | **absent** |
| [D04](#d04) | `assets` | ground_truth | 1 | 16,894 | 16,894 | 202,728 | present |
| [D05](#d05) | `persons` | ground_truth | 1 | 2,917 | 2,917 | 35,004 | present |
| [D06](#d06) | `household_membership` | ground_truth | 1 | 2,917 | 2,917 | 35,004 | present |
| [D07](#d07) | `relationships` | ground_truth | 1 | 3,022 | 3,022 | 36,264 | present |
| [D08](#d08) | `person_states` | ground_truth | 1 | 2,917 | 2,917 | 35,004 | present |
| [D09](#d09) | `life_events` | (ground_truth) | — | — | — | — | **absent** |
| [D10](#d10) | `activities` | ground_truth | 11–14 | 29,592,589 | 29,629,500 | 348,048,802 | present |
| [D11](#d11) | `presence` | ground_truth | 1–2 | 1,149,976 | 1,149,466 | 13,731,536 | present |
| [D12](#d12) | `trips` | (ground_truth) | — | — | — | — | **absent** |
| [D13](#d13) | `appliance_cycles` | ground_truth | 11–14 | 32,137,916 | 32,064,901 | 376,743,372 | present |
| [D14](#d14) | `calendar_events` | ground_truth | 1 | 173 | 227 | 2,599 | present |
| [D15](#d15) | `weather` | ground_truth | 1 | 525,600 | 525,600 | 6,179,040 | present |
| [D16](#d16) | `building_state` | ground_truth | 11–14 | 38,263,680 | 38,263,680 | 449,834,112 | present |
| [D17](#d17) | `network_state` | ground_truth | 11–14 | 4,099,680 | 4,099,680 | 48,196,512 | present |
| [D17_aggregate](#d17_aggregate) | `network_state_aggregate` | observable | 11–14 | 4,100,772 | 4,100,772 | 48,209,616 | present |
| [D18](#d18) | `observations` | observable | 4–14 | 0 | 361,444,721 | 1,341,660,210 | present from 2019 |
| [D19](#d19) | `edge_exports` | observable | 11–14 | 76,544,880 | 76,544,880 | 899,874,192 | present |
| [D20](#d20) | `change_labels` | (ground_truth) | — | — | — | — | **absent** |
| [D21](#d21) | `biographies` | ground_truth | 1 | 5,834 | 5,834 | 70,008 | present |
| [D22](#d22) | `signature_library` | evidence | 1 | 19 | 19 | 228 | present |
| [D23](#d23) | `run_manifests` | evidence | 1 | 1 | 1 | 12 | present |
| [D24](#d24) | `calibration_targets` | evidence | 1 | 113 | 113 | 1,356 | present |
| [D25](#d25) | `mimic_export` | (observable) | — | — | — | — | **absent** |
| [D26](#d26) | `mimic_answer_key` | (ground_truth) | — | — | — | — | **absent** |
| [D27](#d27) | `tariffs_contracts` | observable | 1 | 1,092 | 1,092 | 13,104 | present |
| [D28](#d28) | `study_protocol` | observable | 1 | 2,225 | 2,225 | 26,799 | present |
| [D29](#d29) | `household_survey` | observable | 1 | 2,184 | 2,184 | 26,208 | present |
| [D30](#d30) | `recorded_metadata` | observable | 1 | 1,092 | 1,092 | 13,104 | present |
| [D31](#d31) | `external_series` | observable | 1 | 70,080 | 70,080 | 823,872 | present |

### 4.2 Rows per year

| dataset | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| D01 | 206 | 206 | 206 | 206 | 206 | 206 | 206 | 206 | 206 | 206 | 206 | 206 |
| D02 | 1,092 | 1,092 | 1,092 | 1,092 | 1,092 | 1,092 | 1,092 | 1,092 | 1,092 | 1,092 | 1,092 | 1,092 |
| D04 | 16,894 | 16,894 | 16,894 | 16,894 | 16,894 | 16,894 | 16,894 | 16,894 | 16,894 | 16,894 | 16,894 | 16,894 |
| D05 | 2,917 | 2,917 | 2,917 | 2,917 | 2,917 | 2,917 | 2,917 | 2,917 | 2,917 | 2,917 | 2,917 | 2,917 |
| D06 | 2,917 | 2,917 | 2,917 | 2,917 | 2,917 | 2,917 | 2,917 | 2,917 | 2,917 | 2,917 | 2,917 | 2,917 |
| D07 | 3,022 | 3,022 | 3,022 | 3,022 | 3,022 | 3,022 | 3,022 | 3,022 | 3,022 | 3,022 | 3,022 | 3,022 |
| D08 | 2,917 | 2,917 | 2,917 | 2,917 | 2,917 | 2,917 | 2,917 | 2,917 | 2,917 | 2,917 | 2,917 | 2,917 |
| D10 | 29,592,589 | 29,698,522 | 29,610,287 | 29,594,318 | 29,592,442 | 29,667,972 | 29,571,402 | 29,608,981 | 29,631,217 | 29,689,653 | 29,629,500 | 22,161,919 |
| D11 | 1,149,976 | 1,149,370 | 1,128,179 | 1,150,803 | 1,149,150 | 1,150,076 | 1,149,126 | 1,126,771 | 1,127,903 | 1,149,836 | 1,149,466 | 1,150,880 |
| D13 | 32,137,916 | 32,215,309 | 32,142,469 | 32,104,821 | 32,074,346 | 32,141,280 | 32,049,076 | 32,005,473 | 32,083,334 | 32,156,556 | 32,064,901 | 23,567,891 |
| D14 | 173 | 177 | 193 | 219 | 236 | 234 | 201 | 252 | 226 | 237 | 227 | 224 |
| D15 | 525,600 | 527,040 | 525,600 | 525,600 | 525,600 | 527,040 | 525,600 | 525,600 | 525,600 | 527,040 | 525,600 | 393,120 |
| D16 | 38,263,680 | 38,368,512 | 38,263,680 | 38,263,680 | 38,263,680 | 38,368,512 | 38,263,680 | 38,263,680 | 38,263,680 | 38,368,512 | 38,263,680 | 28,619,136 |
| D17 | 4,099,680 | 4,110,912 | 4,099,680 | 4,099,680 | 4,099,680 | 4,110,912 | 4,099,680 | 4,099,680 | 4,099,680 | 4,110,912 | 4,099,680 | 3,066,336 |
| D17_aggregate | 4,100,772 | 4,112,004 | 4,100,772 | 4,100,772 | 4,100,772 | 4,112,004 | 4,100,772 | 4,100,772 | 4,100,772 | 4,112,004 | 4,100,772 | 3,067,428 |
| D18 | 0 | 0 | 0 | 0 | 216,754 | 5,201,585 | 47,850,813 | 123,091,117 | 201,141,005 | 282,188,959 | 361,444,721 | 320,525,256 |
| D19 | 76,544,880 | 76,754,592 | 76,544,880 | 76,544,880 | 76,544,880 | 76,754,592 | 76,544,880 | 76,544,880 | 76,544,880 | 76,754,592 | 76,544,880 | 57,251,376 |
| D21 | 5,834 | 5,834 | 5,834 | 5,834 | 5,834 | 5,834 | 5,834 | 5,834 | 5,834 | 5,834 | 5,834 | 5,834 |
| D22 | 19 | 19 | 19 | 19 | 19 | 19 | 19 | 19 | 19 | 19 | 19 | 19 |
| D23 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| D24 | 113 | 113 | 113 | 113 | 113 | 113 | 113 | 113 | 113 | 113 | 113 | 113 |
| D27 | 1,092 | 1,092 | 1,092 | 1,092 | 1,092 | 1,092 | 1,092 | 1,092 | 1,092 | 1,092 | 1,092 | 1,092 |
| D28 | 2,225 | 2,258 | 2,225 | 2,225 | 2,225 | 2,258 | 2,225 | 2,225 | 2,225 | 2,258 | 2,225 | 2,225 |
| D29 | 2,184 | 2,184 | 2,184 | 2,184 | 2,184 | 2,184 | 2,184 | 2,184 | 2,184 | 2,184 | 2,184 | 2,184 |
| D30 | 1,092 | 1,092 | 1,092 | 1,092 | 1,092 | 1,092 | 1,092 | 1,092 | 1,092 | 1,092 | 1,092 | 1,092 |
| D31 | 70,080 | 70,272 | 70,080 | 70,080 | 70,080 | 70,272 | 70,080 | 70,080 | 70,080 | 70,272 | 70,080 | 52,416 |

### 4.3 Absent datasets

Each absence is recorded, with its reason, in every year's `_segment/export_report.json` (`datasets.<ID>.verdict = "not written"`). They are absences by design of the frozen engine, not export failures.

| ID | name | why absent |
|---|---|---|
| <a id="d03"></a>D03 | `building_passport` — Dated building events (extension, retrofit, asset added or removed) | Built from `evidence/wp5_tenyear.json`, which only a run that steps the ten-year life course writes. The replay steps none, so no passport event exists. |
| <a id="d09"></a>D09 | `life_events` — Births, deaths, moves, jobs, health states, decisions | Same artefact and cause as D03. |
| <a id="d12"></a>D12 | `trips` — Origin, destination, mode, vehicle, distance | No trip row survives the day: the engine computes travel only for EV state of charge; there is no trips output or D12 buffer. |
| <a id="d20"></a>D20 | `change_labels` — Ground-truth labels for detector scoring (onset, type, persistence) | Same artefact and cause as D03. |
| <a id="d25"></a>D25 | `mimic_export` — HRSD participants, profiles, MCV, sessions and responses in MIMIC schema 1.1 | Owned by the MIMIC exporter, not by this package. |
| <a id="d26"></a>D26 | `mimic_answer_key` — Crosswalk to person_id, true traits, planted segments, propensity, gap, test settings | Owned by the MIMIC exporter, not by this package. |

See `V1_KNOWN_LIMITATIONS.md` §2 for the detail.

### 4.4 Present datasets

For each: what it is, its grain and key, where it lives, and its full schema. **Type** is the Parquet/Arrow type on disk. **Unit** comes from `datasets.yaml` where declared, otherwise from the column-name suffix, marked *(name)*. **Meaning** is the field's note or observation mechanism from `datasets.yaml`; ⚠ marks a caveat from the part manifest (`unmodelled_fields`) or the export's `partially_conformant` record. The schema is identical in every year unless stated. Keys are the natural key implied by the grain; the writer does not enforce uniqueness.

<a id="d01"></a>
#### D01 · `town_geo` — Parcels, streets, venues, network topology

The town's geography: parcels, streets, venues and the topology of the low-voltage network.

| | |
|---|---|
| access class / package | GT / `ground_truth/` |
| grain | one row per geographic feature (parcel, street, venue, feeder, transformer) (declared: *feature*) |
| key | `feature_id`, `valid_from` |
| path | `v1/<year>/ground_truth/D01_part<NNN>.parquet` |
| parts | 1 part in 12 years |
| rows | 2,472 over 12 years; per year in §4.2 |
| size on B2 | 0.00 GB over 12 years |
| years present | 2015–2026 |
| schema conformance | full |
| time span, 2025 (`valid_from`) | 2025-01-01 00:00:00 → 2025-01-01 00:00:00 |

| column | type | unit | req. | meaning |
|---|---|---|---|---|
| `feature_id` | string |  | yes | V- for venues, else synthetic key |
| `feature_kind` | string |  | yes | parcel \| street \| venue \| feeder \| transformer \| farm |
| `geometry_wkt` | string |  | yes | feature geometry as WKT |
| `venue_type` | string |  | no | school, shop, pub, church, GAA club, workplace |
| `capacity` | int64 |  | no | design 5.4: every venue has a capacity |
| `feeder_id` | string |  | no | LV feeder the feature is on |
| `estate_id` | string |  | no | estate the building belongs to |
| `valid_from` | timestamp[ns, tz=UTC] |  | yes | start of the validity interval (UTC) |
| `valid_to` | timestamp[ns, tz=UTC] |  | no | end of the validity interval; null = still valid |

<a id="d02"></a>
#### D02 · `buildings` — HRSD_Buildings: fabric, archetype, BER, systems, physics parameters

Every dwelling's fabric, archetype, BER, heating system and the physics parameters derived from them.

| | |
|---|---|
| access class / package | GT / `ground_truth/` |
| grain | building × version; 1,092 buildings, one version each in v1 (declared: *building x version*) |
| key | `building_id`, `version` |
| path | `v1/<year>/ground_truth/D02_part<NNN>.parquet` |
| parts | 1 part in 12 years |
| rows | 13,104 over 12 years; per year in §4.2 |
| size on B2 | 0.00 GB over 12 years |
| years present | 2015–2026 |
| schema conformance | full |
| time span, 2025 (`valid_from`) | 2022-01-01 00:00:00 → 2022-01-01 00:00:00 |

| column | type | unit | req. | meaning |
|---|---|---|---|---|
| `building_id` | string |  | yes | building key (`B-`) |
| `version` | int64 |  | yes | bumped by a D03 passport event |
| `valid_from` | timestamp[ns, tz=UTC] |  | yes | start of the validity interval (UTC) |
| `valid_to` | timestamp[ns, tz=UTC] |  | no | end of the validity interval; null = still valid |
| `premises_id` | string |  | yes | GT side of the opaque observable key |
| `estate_id` | string |  | yes | estate the building belongs to |
| `dwelling_type` | string |  | yes | one of: detached, semi-detached, terraced, apartment, bedsit |
| `build_year` | int64 |  | yes | year of construction |
| `floor_area_m2` | double | m² *(name)* | yes | floor area |
| `storeys` | int64 |  | yes | number of storeys |
| `archetype_id` | string |  | yes | building archetype the fabric was drawn from |
| `ber_band` | string |  | yes | asset rating; operation may diverge (5.7 performance gap); one of: A1, A2, A3, B1, B2, B3, C1, C2, C3, D1, D2, E1, E2, F, G |
| `ber_kwh_m2_yr` | double | kWh/m²/yr *(name)* | yes | BER primary energy rating |
| `heating_fuel` | string |  | yes | one of: electricity, natural gas, oil, solid fuel, LPG, heat pump, district |
| `heating_system` | string |  | yes | heating system type |
| `heating_control` | string |  | yes | timer \| thermostat \| TRV \| manual |
| `tenure` | string |  | yes | one of: owner-occupied with mortgage, owner-occupied no mortgage, rented private, rented social, rent free |
| `sri_class` | string |  | no | ISO 52120-1 building automation class |
| `sri_score` | double |  | no | smart readiness indicator score |
| `rc_r_ie` | double | K/W | yes | indoor-envelope resistance |
| `rc_r_ea` | double | K/W | yes | envelope-ambient resistance |
| `rc_r_zz` | double | K/W | yes | living-sleeping inter-zone resistance |
| `rc_r_inf` | double | K/W | yes | infiltration path |
| `rc_c_living` | double | J/K | yes | F1 RC model: living-zone heat capacity |
| `rc_c_sleep` | double | J/K | yes | F1 RC model: sleeping-zone heat capacity |
| `rc_c_env` | double | J/K | yes | F1 RC model: envelope heat capacity |
| `rc_solar_aperture_m2` | double | m² *(name)* | yes | F1 RC model: effective solar aperture |
| `rc_vol_living_m3` | double | m³ *(name)* | yes | F1 RC model: living-zone air volume |
| `rc_vol_sleep_m3` | double | m³ *(name)* | yes | F1 RC model: sleeping-zone air volume |
| `ach_base` | double | 1/h | yes | background infiltration |
| `heat_emitter_w` | double | W *(name)* | yes | maximum deliverable heat |
| `dhw_tank_litres` | double | L *(name)* | no | hot water cylinder volume |
| `fidelity_tier` | string |  | yes | one of: F1, F2, F3 |
| `seed` | int64 |  | yes | RNG seed the row was drawn with |

<a id="d04"></a>
#### D04 · `assets` — Appliances, heating, PV, BESS, chargers, vehicles, with owner and lifetime

Appliances, heating plant, PV, batteries, chargers and vehicles, each with an owner and a lifetime.

| | |
|---|---|
| access class / package | GT / `ground_truth/` |
| grain | asset × version (declared: *asset x version*) |
| key | `asset_id`, `version` |
| path | `v1/<year>/ground_truth/D04_part<NNN>.parquet` |
| parts | 1 part in 12 years |
| rows | 202,728 over 12 years; per year in §4.2 |
| size on B2 | 0.00 GB over 12 years |
| years present | 2015–2026 |
| schema conformance | partial: required fields listed in null_required_fields are null by declaration, because the model holds no value for them |
| time span, 2025 (`valid_from`) | 2025-01-01 00:00:00 → 2025-01-01 00:00:00 |

| column | type | unit | req. | meaning |
|---|---|---|---|---|
| `asset_id` | string |  | yes | asset key (`A-`) |
| `version` | int64 |  | yes | row version, bumped by a change event |
| `valid_from` | timestamp[ns, tz=UTC] |  | yes | start of the validity interval (UTC) |
| `valid_to` | timestamp[ns, tz=UTC] |  | no | end of the validity interval; null = still valid |
| `building_id` | string |  | no | building key (`B-`) |
| `owner_person_id` | string |  | no | vehicles and personal devices |
| `asset_class` | string |  | yes | appliance \| heating \| pv \| bess \| charger \| vehicle |
| `asset_type` | string |  | yes | kettle, washer, heat_pump, immersion, ... |
| `make_model_synth` | string |  | yes | synthetic model label, drives signature variation ⚠ NO SOURCE. |
| `rated_power_w` | double | W *(name)* | no | rated electrical power |
| `capacity` | double | Wh for BESS, kWp for PV, litres for tanks | no | capacity (asset-specific: e.g. battery or vehicle energy, venue places) |
| `efficiency` | double |  | no | rated efficiency |
| `install_date` | date32[day] |  | yes | ⚠ POPULATED for appliance rows, NULL for every heating, pv, bess, charger and vehicle row. |
| `age_years_at_t0` | double | years *(name)* | yes | ⚠ POPULATED for appliance rows, NULL for every other row, for the same reason as install_date: `age_years` exists only in the appliance stock draw. |
| `failure_hazard_scale` | double |  | yes | Weibull scale, drives 5.3 appliance failure ⚠ NO SOURCE as a Weibull scale. |
| `signature_id` | string |  | no | -> D22 |
| `device_mode` | string |  | yes | 5.6 rendered vs live; one of: rendered, live |
| `pv_azimuth_deg` | double | degrees *(name)* | no | PV array azimuth |
| `pv_tilt_deg` | double | degrees *(name)* | no | PV array tilt |
| `seed` | int64 |  | yes | RNG seed the row was drawn with |

<a id="d05"></a>
#### D05 · `persons` — HRSD_Occupants: persistent characteristics and trait vector

The persons dataset, HRSD_Occupants proper: each resident's persistent characteristics and trait vector.

| | |
|---|---|
| access class / package | GT / `ground_truth/` |
| grain | one row per person (2,917) (declared: *person*) |
| key | `person_id` |
| path | `v1/<year>/ground_truth/D05_part<NNN>.parquet` |
| parts | 1 part in 12 years |
| rows | 35,004 over 12 years; per year in §4.2 |
| size on B2 | 0.01 GB over 12 years |
| years present | 2015–2026 |
| schema conformance | full |
| time span, 2025 (`death_date`) | None → None |

| column | type | unit | req. | meaning |
|---|---|---|---|---|
| `person_id` | string |  | yes | person key (`P-`) |
| `given_name` | string |  | yes | synthetic, uniqueness-checked |
| `family_name` | string |  | yes | synthetic family name |
| `birth_date` | date32[day] |  | yes | date of birth (synthetic) |
| `death_date` | timestamp[ns] |  | no | set by D09 |
| `sex` | string |  | yes | one of: F, M |
| `country_of_birth` | string |  | yes | ISO 3166-1 alpha-2 |
| `nationality` | string |  | yes | ISO 3166-1 alpha-2 |
| `ethnicity_census` | string |  | yes | CSO category; synthesis and stereotype-guard only |
| `first_language` | string |  | yes | ISO 639-1 |
| `other_languages` | list<element: string> |  | no | other languages (ISO 639-1) |
| `years_in_ireland` | double |  | no | drives idvZ acculturation shrinkage (5.13) |
| `education_level` | string |  | yes | ISCED; evolves via D08 while in education |
| `trans` | double | z-score | yes | MIMIC latent trait (same name and scale as the MIMIC generator) |
| `community` | double | z-score | yes | MIMIC latent trait (same name and scale as the MIMIC generator) |
| `env` | double | z-score | yes | MIMIC latent trait (same name and scale as the MIMIC generator) |
| `autonomy` | double | z-score | yes | MIMIC latent trait (same name and scale as the MIMIC generator) |
| `comfort` | double | z-score | yes | MIMIC latent trait (same name and scale as the MIMIC generator) |
| `conditional` | double | z-score | yes | MIMIC latent trait (same name and scale as the MIMIC generator) |
| `privacy` | double | z-score | yes | MIMIC latent trait (same name and scale as the MIMIC generator) |
| `instTrust` | double | z-score | yes | MIMIC latent trait (same name and scale as the MIMIC generator) |
| `idvZ` | double | z-score | yes | cultural individualism from origin country, shrunk by acculturation |
| `satisficer` | int64 |  | yes | careless-responder flag |
| `stated_gap` | double | 0 to 1 | yes | stated vs revealed willingness (5.13) |
| `lambda_self` | double |  | yes | lambda_1; the three sum to 1 |
| `lambda_coop` | double |  | yes | lambda_2 |
| `lambda_altru` | double |  | yes | lambda_3 |
| `big5_o` | double | z-score | yes | Big Five: openness |
| `big5_c` | double | z-score | yes | Big Five: conscientiousness |
| `big5_e` | double | z-score | yes | Big Five: extraversion |
| `big5_a` | double | z-score | yes | Big Five: agreeableness |
| `big5_n` | double | z-score | yes | Big Five: neuroticism |
| `chronotype` | double | hours | yes | shifts the sleep window |
| `habit_strength` | double | 0 to 1 | yes | strength of routine (habit) in activity choice |
| `lapse_rate` | double | 0 to 1 | yes | rate of lapses from routine |
| `attention` | double | 0 to 1 | yes | propensity to deliberate over a choice rather than follow habit |
| `response_propensity` | double | 0 to 1 | yes | 5.14 MIMIC opt-in propensity |
| `mcv_latent` | list<element: double> |  | yes | 10 MCV item latents, MIMIC makeMcv mapping |
| `synthetic` | bool |  | yes | R27/K12: every record carries the synthetic flag |
| `seed` | int64 |  | yes | RNG seed the row was drawn with |
| `pool` | string |  | no | BN-panel for simulated townspeople; HRSD-pool for the unlinked extended pool; one of: BN-panel, HRSD-pool |

<a id="d06"></a>
#### D06 · `household_membership` — Who lives where, from when to when

Household membership over time: who lives where, from when to when.

| | |
|---|---|
| access class / package | GT / `ground_truth/` |
| grain | person × household membership spell (declared: *interval*) |
| key | `membership_id` |
| path | `v1/<year>/ground_truth/D06_part<NNN>.parquet` |
| parts | 1 part in 12 years |
| rows | 35,004 over 12 years; per year in §4.2 |
| size on B2 | 0.00 GB over 12 years |
| years present | 2015–2026 |
| schema conformance | full |
| time span, 2025 (`valid_from`) | 2022-01-01 00:00:00 → 2022-01-01 00:00:00 |

| column | type | unit | req. | meaning |
|---|---|---|---|---|
| `membership_id` | string |  | yes | membership spell key |
| `person_id` | string |  | yes | person key (`P-`) |
| `household_id` | string |  | yes | household key (`H-`) |
| `building_id` | string |  | yes | building key (`B-`) |
| `valid_from` | timestamp[ns, tz=UTC] |  | yes | start of the validity interval (UTC) |
| `valid_to` | timestamp[ns, tz=UTC] |  | no | end of the validity interval; null = still valid |
| `role` | string |  | yes | one of: head, partner, child, parent, lodger, other |
| `reason_in` | string |  | no | t0 \| birth \| move in \| partnering \| returning |
| `reason_out` | string |  | no | why the spell ended |

<a id="d07"></a>
#### D07 · `relationships` — Kin, partner, carer, friend, co-worker edges

The relationship graph: kin, partner, carer, friend and co-worker edges between people, valid over intervals.

| | |
|---|---|
| access class / package | GT / `ground_truth/` |
| grain | one row per relationship edge (declared: *edge x interval*) |
| key | `edge_id` |
| path | `v1/<year>/ground_truth/D07_part<NNN>.parquet` |
| parts | 1 part in 12 years |
| rows | 36,264 over 12 years; per year in §4.2 |
| size on B2 | 0.00 GB over 12 years |
| years present | 2015–2026 |
| schema conformance | full |
| time span, 2025 (`valid_from`) | 2022-01-01 00:00:00 → 2022-01-01 00:00:00 |

| column | type | unit | req. | meaning |
|---|---|---|---|---|
| `edge_id` | string |  | yes | edge key |
| `person_a` | string |  | yes | one end of the edge (`P-`) |
| `person_b` | string |  | yes | other end of the edge (`P-`) |
| `edge_type` | string |  | yes | partner \| parent_of \| sibling \| carer_of \| friend \| co_worker \| neighbour |
| `valid_from` | timestamp[ns, tz=UTC] |  | yes | start of the validity interval (UTC) |
| `valid_to` | timestamp[ns, tz=UTC] |  | no | end of the validity interval; null = still valid |
| `strength` | double | 0 to 1 | no | drives 5.3 influence |

<a id="d08"></a>
#### D08 · `person_states` — Evolving states, slowly changing (SCD-2)

Person states that evolve slowly — employment, health, caring load, work pattern — recorded as slowly changing dimensions so that every state has a from and a to.

| | |
|---|---|
| access class / package | GT / `ground_truth/` |
| grain | person × state spell (SCD-2) (declared: *interval*) |
| key | `state_id` (`person_id` × validity) |
| path | `v1/<year>/ground_truth/D08_part<NNN>.parquet` |
| parts | 1 part in 12 years |
| rows | 35,004 over 12 years; per year in §4.2 |
| size on B2 | 0.00 GB over 12 years |
| years present | 2015–2026 |
| schema conformance | full |
| time span, 2025 (`valid_from`) | 2022-01-01 00:00:00 → 2022-01-01 00:00:00 |

| column | type | unit | req. | meaning |
|---|---|---|---|---|
| `state_id` | string |  | yes | state spell key |
| `person_id` | string |  | yes | person key (`P-`) |
| `valid_from` | timestamp[ns, tz=UTC] |  | yes | start of the validity interval (UTC) |
| `valid_to` | timestamp[ns, tz=UTC] |  | no | end of the validity interval; null = still valid |
| `household_id` | string |  | yes | household key (`H-`) |
| `role` | string |  | yes | one of: head, partner, child, parent, lodger, other |
| `econ_status` | string |  | yes | one of: employed, self-employed, unemployed, student, retired, home duties, unable to work |
| `occupation_soc` | string |  | no | SOC 2010 |
| `occupation_isco08` | string |  | no | mapped for MIMIC compatibility (5.13) |
| `industry_nace` | string |  | no | NACE rev2 |
| `workplace_venue_id` | string |  | no | workplace venue (`V-`) |
| `work_pattern` | string |  | yes | one of: fixed day, shift, part-time, irregular, none |
| `remote_share` | double | 0 to 1 of working days | yes | share of work done remotely |
| `school_venue_id` | string |  | no | school venue (`V-`) |
| `school_year` | int64 |  | no | school year |
| `health_state` | string |  | yes | U09: generic functional states only, never diagnoses; one of: well, short illness, reduced mobility, home-bound, recovering |
| `caring_load` | string |  | yes | one of: none, child, elderly, both |
| `caring_hours_week` | double | h/week *(name)* | yes | hours of care given per week |
| `decision_authority` | double | 0 to 1 within household | yes | share of household decision authority: 1/n for each of n adults, 0 for children |
| `vehicle_access` | string |  | yes | one of: none, shared, own |
| `income_quintile` | int64 |  | yes | household income quintile |

<a id="d10"></a>
#### D10 · `activities` — Person activity intervals with location and co-participants

Activity intervals: what each person is doing, where, and with whom.

| | |
|---|---|
| access class / package | GT / `ground_truth/` |
| grain | person × activity interval, minute boundaries; about 74 per home-day (declared: *interval*) |
| key | `activity_id` |
| path | `v1/<year>/ground_truth/D10_part<NNN>.parquet` |
| parts | 13 parts in 10 years, 14 parts in 1 year, 11 parts in 1 year |
| rows | 348,048,802 over 12 years; per year in §4.2 |
| size on B2 | 2.47 GB over 12 years |
| years present | 2015–2026 |
| schema conformance | full |
| time span, 2025 (`start`) | 2025-01-01 00:00:00 → 2025-12-31 23:59:00 |

| column | type | unit | req. | meaning |
|---|---|---|---|---|
| `activity_id` | string |  | yes | activity interval key |
| `person_id` | string |  | yes | person key (`P-`) |
| `start` | timestamp[ns, tz=UTC] |  | yes | 1 s precision |
| `end` | timestamp[ns, tz=UTC] |  | yes | interval end (UTC) |
| `activity_code` | string |  | yes | ~30 codes, mapped to HETUS |
| `hetus_code` | string |  | yes | the HETUS aggregate this maps to |
| `location_id` | string |  | no | where the person is (building or venue key) |
| `zone` | string |  | yes | one of: living, kitchen, bedroom, bathroom, utility, hall, outside, in_transit, out_of_model |
| `joint_with` | list<element: string> |  | no | co-participants (`P-` list) |
| `trigger` | string |  | yes | one of: routine, joint plan, event, signal, disruption, lapse |
| `deliberated` | bool |  | yes | true if a decision process ran (5.3 bounded rationality) |

<a id="d11"></a>
#### D11 · `presence` — Person location intervals - the no-double-occupancy source

Presence: where each person is over each interval, at home or away and at which venue.

| | |
|---|---|
| access class / package | GT / `ground_truth/` |
| grain | person × location interval, minute boundaries; **first 14 days of each year only** (declared: *interval*) |
| key | `presence_id` |
| path | `v1/<year>/ground_truth/D11_part<NNN>.parquet` |
| parts | 1 part in 6 years, 2 parts in 6 years |
| rows | 13,731,536 over 12 years; per year in §4.2 |
| size on B2 | 0.08 GB over 12 years |
| years present | 2015–2026 |
| coverage | Presence is collected for the **first 14 days** of each year only (`collect_presence_days`), 1 Jan 00:00 to 14 Jan 23:59. |
| schema conformance | full |
| time span, 2025 (`start`) | 2025-01-01 00:00:00 → 2025-01-14 23:59:00 |

| column | type | unit | req. | meaning |
|---|---|---|---|---|
| `presence_id` | string |  | yes | presence interval key |
| `person_id` | string |  | yes | person key (`P-`) |
| `start` | timestamp[ns, tz=UTC] |  | yes | interval start (UTC, inclusive) |
| `end` | timestamp[ns, tz=UTC] |  | yes | interval end (UTC) |
| `location_kind` | string |  | yes | building \| venue \| in_transit \| out_of_model |
| `location_id` | string |  | no | where the person is (building or venue key) |
| `zone` | string |  | yes | one of: living, kitchen, bedroom, bathroom, utility, hall, outside, in_transit, out_of_model |

<a id="d13"></a>
#### D13 · `appliance_cycles` — Cycle start/end, programme, signature ID, energy

Appliance cycles: when each appliance ran, on which programme, with which signature and how much energy it used.

| | |
|---|---|
| access class / package | GT / `ground_truth/` |
| grain | appliance cycle; about 81 per home-day (declared: *event*) |
| key | `cycle_id` |
| path | `v1/<year>/ground_truth/D13_part<NNN>.parquet` |
| parts | 13 parts in 10 years, 14 parts in 1 year, 11 parts in 1 year |
| rows | 376,743,372 over 12 years; per year in §4.2 |
| size on B2 | 9.06 GB over 12 years |
| years present | 2015–2026 |
| schema conformance | full |
| time span, 2025 (`start`) | 2025-01-01 00:00:00 → 2025-12-31 23:59:00 |

| column | type | unit | req. | meaning |
|---|---|---|---|---|
| `cycle_id` | string |  | yes | appliance cycle key |
| `asset_id` | string |  | yes | asset key (`A-`) |
| `building_id` | string |  | yes | building key (`B-`) |
| `start` | timestamp[ns, tz=UTC] |  | yes | 1 s precision |
| `end` | timestamp[ns, tz=UTC] |  | yes | interval end (UTC) |
| `programme` | string |  | yes | eco 40, kettle 1.5 L, ... |
| `signature_id` | string |  | yes | waveform template (D22) |
| `signature_seed` | int64 |  | yes | drives 1 Hz rendering |
| `energy_wh` | double | Wh *(name)* | yes | energy used by the cycle |
| `peak_w` | double | W *(name)* | yes | peak power in the cycle |
| `caused_by_activity_id` | string |  | no | causal link back to D10 |
| `flexible` | bool |  | yes | whether the cycle could be shifted |
| `shifted_by_min` | int64 | min *(name)* | yes | minutes the cycle was shifted by a signal |

<a id="d14"></a>
#### D14 · `calendar_events` — Event instances, phases, footprint, attendance

Calendar events: holidays, school terms, storms, outages and the rest, each with its phases, footprint and attendance.

| | |
|---|---|
| access class / package | GT / `ground_truth/` |
| grain | event instance × phase (declared: *event*) |
| key | `instance_id`, `phase` |
| path | `v1/<year>/ground_truth/D14_part<NNN>.parquet` |
| parts | 1 part in 12 years |
| rows | 2,599 over 12 years; per year in §4.2 |
| size on B2 | 0.00 GB over 12 years |
| years present | 2015–2026 |
| schema conformance | full |
| time span, 2025 (`start`) | 2025-01-07 00:00:00 → 2025-10-27 00:00:00 |
| schema note | `attendance_prob` is `struct<adult, child, visitors>` in every year except **2022**, where it is `struct<all, child, adult, visitors>` |

| column | type | unit | req. | meaning |
|---|---|---|---|---|
| `instance_id` | string |  | yes | event instance key |
| `event_kind` | string |  | yes | holiday \| school term \| storm \| outage \| festival \| cruise day \| market \| sport \| roadworks \| DST |
| `event_class` | string |  | yes | one of: predictable, recurring, irregular, exceptional |
| `phase` | string |  | yes | one of: preparation, main, recovery, rebound |
| `start` | timestamp[ns, tz=UTC] |  | yes | interval start (UTC, inclusive) |
| `end` | timestamp[ns, tz=UTC] |  | yes | interval end (UTC) |
| `footprint` | string |  | yes | one of: home, street, estate, town, region |
| `footprint_ids` | list<element: string> |  | no | keys of the buildings/venues the event touches |
| `attendance_prob` | struct<adult: double, child: double, visitors: double> |  | no | by demographic |
| `shared_driver` | string |  | no | 5.10: compound correlation comes from shared drivers, not independent draws |
| `source_ref` | string |  | yes | -> D24 / SOURCES.md |

<a id="d15"></a>
#### D15 · `weather` — True site weather and solar geometry driving physics and behaviour

The true site weather and solar geometry that drives the physics: temperature, irradiance, wind, humidity and rain at minute resolution.

| | |
|---|---|
| access class / package | GT / `ground_truth/` |
| grain | site × **1 minute** (1,440 rows per day) (declared: *1 min*) |
| key | `ts`, `site_id` |
| path | `v1/<year>/ground_truth/D15_part<NNN>.parquet` |
| parts | 1 part in 12 years |
| rows | 6,179,040 over 12 years; per year in §4.2 |
| size on B2 | 0.29 GB over 12 years |
| years present | 2015–2026 |
| schema conformance | full |
| time span, 2025 (`ts`) | 2025-01-01 00:00:00 → 2025-12-31 23:59:00 |

| column | type | unit | req. | meaning |
|---|---|---|---|---|
| `ts` | timestamp[ns, tz=UTC] |  | yes | instant of the row (UTC) |
| `site_id` | string |  | yes | weather site |
| `temp_air_c` | double | °C *(name)* | yes | air temperature |
| `rh_pct` | double | % *(name)* | yes | relative humidity |
| `wind_speed_ms` | double | m/s *(name)* | yes | wind speed |
| `wind_dir_deg` | double | degrees *(name)* | yes | wind direction |
| `ghi_w_m2` | double | W/m² *(name)* | yes | global horizontal irradiance |
| `dni_w_m2` | double | W/m² *(name)* | yes | direct normal irradiance |
| `dhi_w_m2` | double | W/m² *(name)* | yes | diffuse horizontal irradiance |
| `solar_zenith_deg` | double | degrees *(name)* | yes | solar zenith angle |
| `solar_azimuth_deg` | double | degrees *(name)* | yes | solar azimuth angle |
| `sunrise_utc` | timestamp[ns, tz=UTC] |  | yes | sunrise that day (UTC) |
| `sunset_utc` | timestamp[ns, tz=UTC] |  | yes | sunset that day (UTC) |
| `is_dst` | bool |  | yes | 3.2: DST is an explicit event shifting routines, not the UTC series |
| `precip_mm` | double | mm *(name)* | yes | precipitation in the interval |
| `realisation_id` | string |  | yes | ties D15 and D31 to the same realisation |

<a id="d16"></a>
#### D16 · `building_state` — Zone temps, RH, CO2, DHW, heat delivered

Building state (written every 15 minutes by design, `D16_EPOCH_MINUTES`; the solver itself steps at 1 minute): zone temperatures, relative humidity, CO₂, the hot water cylinder and the heat delivered.

| | |
|---|---|
| access class / package | GT / `ground_truth/` |
| grain | building × **15 minutes** (96 rows per building-day), the network epoch; the schema declares 1 minute (declared: *1 min, checkpointed daily*) |
| key | `building_id`, `ts` |
| path | `v1/<year>/ground_truth/D16_part<NNN>.parquet` |
| parts | 13 parts in 10 years, 14 parts in 1 year, 11 parts in 1 year |
| rows | 449,834,112 over 12 years; per year in §4.2 |
| size on B2 | 32.97 GB over 12 years |
| years present | 2015–2026 |
| schema conformance | full |
| time span, 2025 (`ts`) | 2025-01-01 00:00:00 → 2025-12-31 23:45:00 |

| column | type | unit | req. | meaning |
|---|---|---|---|---|
| `ts` | timestamp[ns, tz=UTC] |  | yes | instant of the row (UTC) |
| `building_id` | string |  | yes | building key (`B-`) |
| `temp_living_c` | double | °C *(name)* | yes | living-zone air temperature |
| `temp_sleep_c` | double | °C *(name)* | yes | sleeping-zone air temperature |
| `temp_env_c` | double | °C *(name)* | yes | envelope (fabric) node temperature of the RC model |
| `rh_living_pct` | double | % *(name)* | yes | ⚠ written constant: F1 has no moisture balance |
| `co2_living_ppm` | double | ppm *(name)* | yes | living-zone CO₂ |
| `co2_sleep_ppm` | double | ppm *(name)* | yes | sleeping-zone CO₂ |
| `dhw_tank_c` | double | °C *(name)* | no | hot water cylinder temperature |
| `heat_delivered_w` | double | W *(name)* | yes | heat delivered by the heating system |
| `internal_gain_w` | double | W *(name)* | yes | internal heat gains (people, appliances) |
| `solar_gain_w` | double | W *(name)* | yes | solar heat gain |
| `ach_effective` | double |  | yes | includes behavioural window opening ⚠ the fabric base rate PLUS the purge ventilation the solver applied; F1 still has no occupant window-opening behaviour, so above the purge threshold this is a thermostat on the air change rate rather than a person at a window (I-032) |
| `occupants_living` | int64 |  | yes | people in the living zone |
| `occupants_sleep` | int64 |  | yes | people in the sleeping zone |

<a id="d17"></a>
#### D17 · `network_state` — Feeder and transformer loading, voltages, outages

Network state: feeder and transformer loading, voltages and outages at minute resolution, from the quasi-static power flow.

| | |
|---|---|
| access class / package | GT / `ground_truth/` |
| grain | network element × **15 minutes**: 117 elements (64 feeders, 53 transformers/substations) (declared: *1 min*) |
| key | `element_id`, `ts` |
| path | `v1/<year>/ground_truth/D17_part<NNN>.parquet` |
| parts | 13 parts in 10 years, 14 parts in 1 year, 11 parts in 1 year |
| rows | 48,196,512 over 12 years; per year in §4.2 |
| size on B2 | 1.69 GB over 12 years |
| years present | 2015–2026 |
| schema conformance | full |
| time span, 2025 (`ts`) | 2025-01-01 00:00:00 → 2025-12-31 23:45:00 |

| column | type | unit | req. | meaning |
|---|---|---|---|---|
| `ts` | timestamp[ns, tz=UTC] |  | yes | instant of the row (UTC) |
| `element_id` | string |  | yes | network element (feeder or transformer) |
| `element_kind` | string |  | yes | feeder \| transformer \| connection |
| `p_kw` | double | kW *(name)* | yes | active power |
| `q_kvar` | double | kvar *(name)* | no | reactive power |
| `voltage_pu` | double | per unit *(name)* | no | voltage |
| `loading_pct` | double | % *(name)* | no | loading against rating |
| `outage` | bool |  | yes | element out of service |
| `coupling_mode` | string |  | yes | one of: C1, C2, C3 |
| `epoch_staleness_s` | int64 | s *(name)* | yes | 8.2 timing contract: the staleness stamp on the published state |

<a id="d17_aggregate"></a>
#### D17_aggregate · `network_state_aggregate` — D17's observable view: connection register, asset ratings, feeder-head and substation measurements

D17's observable view: what a distribution operator would actually hold about its low-voltage network.

| | |
|---|---|
| access class / package | OBS / `observable/` |
| grain | record × 15 minutes: the connection register (one row per premises) plus feeder-head and substation measurements (declared: *one row per premises in the register; one row per (epoch, element) for a measurement*) |
| key | `record_kind`, `premises_id` / `feeder_ref` / `substation_ref`, `ts` |
| path | `v1/<year>/observable/D17_aggregate_part<NNN>.parquet` |
| parts | 13 parts in 10 years, 14 parts in 1 year, 11 parts in 1 year |
| rows | 48,209,616 over 12 years; per year in §4.2 |
| size on B2 | 0.80 GB over 12 years |
| years present | 2015–2026 |
| schema conformance | full |
| time span, 2025 (`ts`) | 2025-01-01 00:00:00 → 2025-12-31 23:45:00 |

| column | type | unit | req. | meaning |
|---|---|---|---|---|
| `record_kind` | string |  | yes | which of the operator's three LV records this row is: a connection-register entry, a feeder-head measurement, or a substation measurement; one of: connection_register, feeder_head, substation |
| `ts` | timestamp[ns, tz=UTC] |  | yes | the timestamp the operator's system stamps on the record: the metering timestamp of a measurement, or the as-at instant of the connection register |
| `premises_id` | string |  | no | the MPRN as it appears in the operator's connection register; null on a measurement row, which names a network element and not a customer |
| `substation_ref` | string |  | yes | the distribution substation's reference in the operator's asset register; every LV connection and every LV circuit is recorded against exactly one |
| `feeder_ref` | string |  | no | the LV circuit's reference in the operator's asset register; null on a substation measurement, which sits upstream of every circuit |
| `transformer_rated_kva` | double | kVA | no | the distribution transformer's nameplate rating, read off the operator's asset register; null where the row's subject is not a transformer |
| `feeder_rated_a` | double | A | no | the feeder cable's thermal current rating, from the cable type recorded in the operator's asset register; null where the row's subject is not a circuit |
| `p_kw_measured` | double | kW | no | the active power the feeder-pillar or substation CT metering reports for the epoch, positive for import; null on a register row, which carries no measurement |
| `q_kvar_measured` | double | kvar | no | the reactive power the same CT metering reports for the epoch; null on a register row |

<a id="d18"></a>
#### D18 · `observations` — Rendered device readings with noise and gaps

Observations: the rendered device readings, with the noise, quantisation, clock error and gaps that real meters and sensors produce.

| | |
|---|---|
| access class / package | OBS / `observable/` |
| grain | device × channel × device-native interval: 30-minute import/export in the smart-meter era, 1-minute (and event-driven) channels for enrolled homes (declared: *device-native*) |
| key | `device_id`, `channel`, `ts` |
| path | `v1/<year>/observable/D18_part<NNN>.parquet` |
| parts | 13 parts in 5 years, 4 parts in 1 year, 14 parts in 1 year, 11 parts in 1 year |
| rows | 1,341,660,210 over 8 years; per year in §4.2 |
| size on B2 | 10.89 GB over 8 years |
| years present | 2019–2026 (era-gated) |
| coverage | **Era-gated** (`d18_era_gating: true`): rows only for home-days in a device era. First smart-meter install **2019-10-02**, last 2025-08-29; 906 of 1,092 homes ever metered; first 1-minute study enrolment 2021-01-05, 328 homes ever enrolled. 2015–2018 have no D18; 2019 starts on 2019-10-02. |
| schema conformance | full |
| time span, 2025 (`ts`) | 2025-01-01 00:00:00 → 2026-01-01 00:08:33 |

| column | type | unit | req. | meaning |
|---|---|---|---|---|
| `device_id` | string |  | yes | the device's own identifier as the data-collection platform records it |
| `premises_id` | string |  | yes | the meter point the device is registered against (6.4 item 2: keyed by premises, not household) |
| `channel` | string |  | yes | import_w, export_w, ct_ev, temp_living, co2_living, pir_hall, ...; on disk: `import_w`, `export_w` (meter era, 30 min) and, for enrolled homes, `ct_circuit`, `charger_w`, `inverter_w`, `temp`, `rh`, `co2`, `pir` |
| `ts` | timestamp[ns, tz=UTC] |  | yes | the device clock at the moment of sampling, including its drift |
| `value` | double |  | no | the device's quantised reading; null where the reading never arrived (observes D16/D13/D17 true quantity); unit in the row's `unit` column |
| `quality` | string |  | yes | the collection platform's own quality assessment of the reading; one of: ok, estimated, missing, suspect, drift, fault |
| `tier` | string |  | yes | the sensor package consented to and installed at this premises; one of: T1, T2, T3, T4 |
| `provenance` | string |  | yes | how the platform obtained the value: metered, estimated, interpolated; one of: metered, estimated, interpolated, operator-recorded, respondent-reported, modelled |
| `unit` | string |  | yes | the unit configured for the channel |

<a id="d19"></a>
#### D19 · `edge_exports` — What leaves each home: aggregates, energy profile, flexibility compliance

Edge exports: what actually leaves each home across the meter boundary, at the settlement interval, under each of the declared export configurations.

| | |
|---|---|
| access class / package | OBS / `observable/` |
| grain | premises × interval × export configuration: `compliance_only` (30 min), `home_15min` (15 min) and one `estate_aggregate` series (declared: *15/30 min*) |
| key | `premises_id`, `export_config`, `interval_start` |
| path | `v1/<year>/observable/D19_part<NNN>.parquet` |
| parts | 13 parts in 10 years, 14 parts in 1 year, 11 parts in 1 year |
| rows | 899,874,192 over 12 years; per year in §4.2 |
| size on B2 | 21.71 GB over 12 years |
| years present | 2015–2026 |
| schema conformance | full |
| time span, 2025 (`interval_start`) | 2025-01-01 00:00:00 → 2025-12-31 23:45:00 |

| column | type | unit | req. | meaning |
|---|---|---|---|---|
| `premises_id` | string |  | yes | the meter point the edge device is commissioned against |
| `interval_start` | timestamp[ns, tz=UTC] |  | yes | the export interval boundary agreed in the data contract |
| `interval_end` | timestamp[ns, tz=UTC] |  | yes | as above |
| `import_wh` | double | Wh *(name)* | no | conditionally required: present for every export configuration that carries a profile, absent for compliance_only (I-067). Enforced by test, not by this flag. |
| `export_wh` | double | Wh *(name)* | no | conditionally required; see import_wh |
| `interval_peak_w` | double | W *(name)* | no | named distinctly from D13.peak_w, which is a per-cycle peak: the two must never be joined. Conditionally required; see import_wh |
| `interval_min_w` | double | W *(name)* | no | conditionally required; see import_wh |
| `building_energy_profile` | struct<mean_w: double, peak_to_mean: double, interval_min: int64> |  | no | the building energy profile the edge device publishes under the data contract (R09) |
| `flex_event_id` | string |  | no | the identifier of the flexibility request the home was asked to serve |
| `flex_compliance_pct` | double | % *(name)* | no | the edge device's own assessment of delivery against the request |
| `export_config` | string |  | yes | the export configuration in force (7.8: home 30 min, home 15 min, estate aggregate, compliance only) |
| `quality` | string |  | yes | the edge device's quality assessment of the interval; one of: ok, estimated, missing, suspect, drift, fault |

<a id="d21"></a>
#### D21 · `biographies` — Human-readable narratives generated from D05 to D09

Biographies: human-readable narratives of each person's life, generated from the persistent, evolving and event datasets.

| | |
|---|---|
| access class / package | GT / `ground_truth/` |
| grain | person × as-of date (declared: *person x date*) |
| key | `person_id`, `as_of` |
| path | `v1/<year>/ground_truth/D21_part<NNN>.parquet` |
| parts | 1 part in 12 years |
| rows | 70,008 over 12 years; per year in §4.2 |
| size on B2 | 0.01 GB over 12 years |
| years present | 2015–2026 |
| schema conformance | full |

| column | type | unit | req. | meaning |
|---|---|---|---|---|
| `person_id` | string |  | yes | person key (`P-`) |
| `as_of` | date32[day] |  | yes | date the narrative describes |
| `narrative_md` | string |  | yes | 5.2 step 6: generated from structured records only, never free-written |
| `source_record_ids` | list<element: string> |  | yes | every sentence traces to a record |
| `cluster_label` | string |  | no | 5.13: no person is ever labelled by cluster. Present only so the schema test can assert it is always null. |

<a id="d22"></a>
#### D22 · `signature_library` — Appliance waveform templates and variation parameters

The signature library: appliance waveform templates and the parameters that vary them.

| | |
|---|---|
| access class / package | META / `evidence/` |
| grain | one row per appliance waveform template (declared: *signature*) |
| key | `signature_id` |
| path | `v1/<year>/evidence/D22_part<NNN>.parquet` |
| parts | 1 part in 12 years |
| rows | 228 over 12 years; per year in §4.2 |
| size on B2 | 0.00 GB over 12 years |
| years present | 2015–2026 |
| schema conformance | full |

| column | type | unit | req. | meaning |
|---|---|---|---|---|
| `signature_id` | string |  | yes | waveform template (D22) |
| `appliance_type` | string |  | yes | appliance type |
| `programme` | string |  | yes | appliance programme |
| `source_dataset` | string |  | yes | UK-DALE \| REFIT \| REDD \| IDEAL \| synthetic-template |
| `source_licence` | string |  | yes | licence of the source |
| `template_hz` | double | Hz *(name)* | yes | template sample rate |
| `template_w` | list<element: double> | W *(name)* | yes | template power trace |
| `duration_s` | int64 | s *(name)* | yes | nominal duration |
| `energy_wh_nominal` | double |  | yes | nominal energy per cycle |
| `var_power_cv` | double |  | yes | model-to-model variation, so two kettles are never identical |
| `var_duration_cv` | double |  | yes | coefficient of variation of duration |
| `ageing_power_per_year` | double |  | yes | power drift per year of age |
| `irish_specific` | bool |  | yes | K07: electric shower, immersion, storage heater |
| `evidence_status` | string |  | yes | [C] cited \| [A] assumption \| synthetic placeholder |

<a id="d23"></a>
#### D23 · `run_manifests` — Code and data versions, parameters, seeds, checksums

Run manifests: the code and data versions, parameters, seeds and checksums for every run.

| | |
|---|---|
| access class / package | META / `evidence/` |
| grain | one row per run (the year) (declared: *run*) |
| key | `run_id` |
| path | `v1/<year>/evidence/D23_part<NNN>.parquet` |
| parts | 1 part in 12 years |
| rows | 12 over 12 years; per year in §4.2 |
| size on B2 | 0.00 GB over 12 years |
| years present | 2015–2026 |
| schema conformance | full |
| time span, 2025 (`created_at_utc`) | 2026-10-19 05:08:17 → 2026-10-19 05:08:17 |

| column | type | unit | req. | meaning |
|---|---|---|---|---|
| `run_id` | string |  | yes | run key |
| `created_at_utc` | timestamp[ns, tz=UTC] |  | yes | when the record was written |
| `label` | string |  | yes | every output is labelled UNVALIDATED SIMULATION EVIDENCE |
| `code_version` | string |  | yes | engine version label |
| `code_git_sha` | string |  | yes | engine commit |
| `code_tree_hash` | string |  | yes | hash of the source tree, so an uncommitted edit is visible |
| `schema_version` | string |  | yes | schema version |
| `design_revision` | int64 |  | yes | design revision |
| `master_seed` | int64 |  | yes | the run's master seed |
| `coupling_mode` | string |  | yes | one of: C1, C2, C3 |
| `scope` | string |  | yes | the E1 scope actually run |
| `input_sources` | string |  | yes | every sources/ file used, with its SHA-256 |
| `parameters` | string |  | yes | run parameters (JSON) |
| `outputs` | string |  | yes | path -> SHA-256 for every file written |
| `checkpoint_chain_head` | string |  | no | head of the checkpoint hash chain |
| `environment` | string |  | yes | python, numpy, platform, core count |

<a id="d24"></a>
#### D24 · `calibration_targets` — Every empirical target with source, version and tolerance

Calibration targets: every empirical quantity the model is calibrated or compared against, with its source, version, tolerance and exposure class.

| | |
|---|---|
| access class / package | META / `evidence/` |
| grain | one row per empirical target (declared: *statistic*) |
| key | `target_id` |
| path | `v1/<year>/evidence/D24_part<NNN>.parquet` |
| parts | 1 part in 12 years |
| rows | 1,356 over 12 years; per year in §4.2 |
| size on B2 | 0.00 GB over 12 years |
| years present | 2015–2026 |
| schema conformance | partial: required fields listed in null_required_fields are null by declaration, because the model holds no value for them |

| column | type | unit | req. | meaning |
|---|---|---|---|---|
| `target_id` | string |  | yes | target key |
| `statistic` | string |  | yes | the statistic the target is for |
| `domain` | string |  | yes | population \\| activity \\| appliance \\| physics \\| weather \\| mimic ⚠ NO SOURCE. |
| `value` | double |  | no | the value, in the row's `unit` |
| `value_json` | string |  | no | for vector or table targets |
| `unit` | string |  | yes | unit of `value` on this row |
| `tolerance` | double |  | yes | ⚠ NO SOURCE as a float. |
| `tolerance_kind` | string |  | yes | absolute \\| relative \\| sampling-error-band ⚠ NO SOURCE. |
| `source_file` | string |  | yes | path under sources/ |
| `source_sha256` | string |  | yes | SHA-256 of the source file |
| `source_url` | string |  | yes | where the source was retrieved |
| `source_licence` | string |  | yes | licence of the source |
| `retrieved_at` | date32[day] |  | yes | when the source was retrieved |
| `intended_use` | string |  | yes | 7.1 source-use register: calibration \| validation \| reference |
| `model_development_exposure` | string |  | yes | 7.1: did it influence design, model selection or tuning? |
| `evidence_tag` | string |  | yes | [C] \\| [P] \\| [A] \\| [U] ⚠ NO SOURCE. |
| `provisional` | bool |  | yes | E0-4 / U11: section 7 margins are provisional ⚠ NO SOURCE. |

<a id="d27"></a>
#### D27 · `tariffs_contracts` — Supplier tariff, ToU and export rates, switches, flexibility and P2P terms, connection limits

Tariffs and contracts: each home's supplier tariff, time-of-use and export rates, switch dates, flexibility and peer-to-peer contract terms, and its connection limits.

| | |
|---|---|
| access class / package | OBS / `observable/` |
| grain | premises × tariff spell (declared: *home x interval*) |
| key | `premises_id`, `valid_from` |
| path | `v1/<year>/observable/D27_part<NNN>.parquet` |
| parts | 1 part in 12 years |
| rows | 13,104 over 12 years; per year in §4.2 |
| size on B2 | 0.00 GB over 12 years |
| years present | 2015–2026 |
| schema conformance | full |
| time span, 2025 (`valid_from`) | 2025-01-01 00:00:00 → 2025-01-01 00:00:00 |

| column | type | unit | req. | meaning |
|---|---|---|---|---|
| `premises_id` | string |  | yes | the meter point on the supply contract |
| `valid_from` | timestamp[ns, tz=UTC] |  | yes | the contract start the supplier recorded |
| `valid_to` | timestamp[ns, tz=UTC] |  | no | the contract end the supplier recorded |
| `supplier` | string |  | yes | the supplier of record |
| `tariff_code` | string |  | yes | the tariff the account is on |
| `tariff_kind` | string |  | yes | flat \| day-night \| ToU \| U10: existing retail tariffs only in the base model |
| `rate_schedule` | string |  | yes | the published rate card |
| `standing_charge_eur_day` | double | EUR/day *(name)* | yes | the published standing charge |
| `export_rate_eur_kwh` | double | EUR/kWh *(name)* | no | the published clean-export guarantee rate |
| `max_import_kw` | double | kW *(name)* | yes | the connection capacity on the network operator's record |
| `max_export_kw` | double | kW *(name)* | yes | the export capacity notified to and accepted by the network operator |
| `der_notification_ref` | string |  | no | the DER notification reference the operator issued |
| `flex_contract_terms` | string |  | no | the aggregator contract terms on file |
| `trial_arm` | string |  | no | the arm this premises was randomised to at recruitment (6.4 item 5) |

<a id="d28"></a>
#### D28 · `study_protocol` — Recruitment, response rates, consent to sensors, dropouts, trial arms and periods

The study protocol: recruitment, response rates, consent to sensors, dropouts, trial arms and periods.

| | |
|---|---|
| access class / package | OBS / `observable/` |
| grain | premises × recruitment protocol event (declared: *premises x event*) |
| key | `premises_id`, `protocol_event`, `recorded_at` |
| path | `v1/<year>/observable/D28_part<NNN>.parquet` |
| parts | 1 part in 12 years |
| rows | 26,799 over 12 years; per year in §4.2 |
| size on B2 | 0.00 GB over 12 years |
| years present | 2015–2026 |
| schema conformance | full |
| time span, 2025 (`recorded_at`) | 2022-01-01 00:00:00 → 2022-12-31 00:00:00 |

| column | type | unit | req. | meaning |
|---|---|---|---|---|
| `premises_id` | string |  | yes | the premises the study recorded against |
| `protocol_event` | string |  | yes | invited \| responded \| declined \| consented \| installed \| withdrew \| dropped_out \| randomised |
| `recorded_at` | timestamp[ns, tz=UTC] |  | yes | when the study team entered the record, which may lag the event |
| `recruitment_route` | string |  | yes | how the household was approached |
| `consent_sensors` | string |  | no | 6.5 rule 3: consent records are sometimes incomplete |
| `tier_consented` | string |  | no | the sensor package the household agreed to; one of: T1, T2, T3, T4 |
| `install_delay_days` | int64 | days *(name)* | no | the gap between consent and the installer attending |
| `trial_arm` | string |  | no | the arm the randomisation list assigned |
| `arm_deviation` | string |  | no | the study team's note of non-compliance or crossover |
| `withdrawal_reason` | string |  | no | the reason the household gave, where they gave one |

<a id="d29"></a>
#### D29 · `household_survey` — Questionnaire answers with calibrated reporting error and non-response

The household survey: questionnaire answers with calibrated reporting error and non-response.

| | |
|---|---|
| access class / package | OBS / `observable/` |
| grain | premises × questionnaire wave (declared: *premises x wave*) |
| key | `premises_id`, `wave` |
| path | `v1/<year>/observable/D29_part<NNN>.parquet` |
| parts | 1 part in 12 years |
| rows | 26,208 over 12 years; per year in §4.2 |
| size on B2 | 0.00 GB over 12 years |
| years present | 2015–2026 |
| schema conformance | full |
| time span, 2025 (`responded_at`) | 2022-03-01 00:00:00 → 2023-04-14 00:00:00 |

| column | type | unit | req. | meaning |
|---|---|---|---|---|
| `premises_id` | string |  | yes | the premises the questionnaire was sent to |
| `wave` | int64 |  | yes | the survey wave the study ran |
| `responded_at` | timestamp[ns, tz=UTC] |  | no | when the respondent submitted; null for unit non-response |
| `q_household_size` | int64 |  | no | the respondent's own count of people in the home (observes D06.membership count) |
| `q_children_under_18` | int64 |  | no | the respondent's answer (observes D06 membership under 18) |
| `q_occupied_weekday_hours` | double | h *(name)* | no | optimistic occupancy is a calibrated bias (6.5 rule 3) (observes D11 presence hours) |
| `q_dwelling_type` | string |  | no | the respondent's answer (observes D02.dwelling_type) |
| `q_heating_system` | string |  | no | the respondent's answer, which may be out of date (observes D02.heating_system) |
| `q_has_pv` | string |  | no | the respondent's recollection (observes D04 pv asset present) |
| `q_has_ev` | string |  | no | the respondent's recollection (observes D04 vehicle asset is EV) |
| `q_appliances` | list<element: string> |  | no | the respondent ticking a list, with omissions (observes D04 appliance stock) |
| `q_env_behaviour_score` | int64 |  | no | over-reported by design (6.5 rule 3) |
| `q_comfort_preference_c` | double | °C *(name)* | no | the respondent's stated preferred temperature |
| `straightlined` | bool |  | yes | derived by the survey platform from answer variance, as a real platform would flag it |
| `item_nonresponse_count` | int64 |  | yes | count of items the respondent left blank |

<a id="d30"></a>
#### D30 · `recorded_metadata` — Recorded building and asset data, stale or wrong at realistic rates

Recorded metadata: the BER, floor area, PV capacity, dates, orientation and shading as some administrative record holds them — stale or wrong at realistic rates.

| | |
|---|---|
| access class / package | OBS / `observable/` |
| grain | premises × recorded version (declared: *premises x version*) |
| key | `premises_id`, `record_version` |
| path | `v1/<year>/observable/D30_part<NNN>.parquet` |
| parts | 1 part in 12 years |
| rows | 13,104 over 12 years; per year in §4.2 |
| size on B2 | 0.00 GB over 12 years |
| years present | 2015–2026 |
| schema conformance | full |
| time span, 2025 (`recorded_at`) | 2015-06-01 00:00:00 → 2015-06-01 00:00:00 |

| column | type | unit | req. | meaning |
|---|---|---|---|---|
| `premises_id` | string |  | yes | the premises the record is filed against |
| `record_version` | int64 |  | yes | the version of the administrative record |
| `recorded_at` | timestamp[ns, tz=UTC] |  | yes | when the assessor or installer filed it |
| `record_source` | string |  | yes | BER assessor \| installer \| operator \| self-declared |
| `rec_ber_band` | string |  | no | the band on the published BER certificate, which predates any later retrofit (observes D02.ber_band) |
| `rec_ber_kwh_m2_yr` | double | kWh/m²/yr *(name)* | no | the figure on the certificate (observes D02.ber_kwh_m2_yr) |
| `rec_floor_area_m2` | double | m² *(name)* | no | subject to m2/ft2 unit errors (6.5 rule 3) (observes D02.floor_area_m2) |
| `rec_dwelling_type` | string |  | no | the assessor's classification (observes D02.dwelling_type) |
| `rec_build_year` | int64 |  | no | the year on the record (observes D02.build_year) |
| `rec_heating_system` | string |  | no | the system recorded at assessment (observes D02.heating_system) |
| `rec_pv_kwp` | double | kWp *(name)* | no | subject to kW/kWp confusion (observes D04.capacity for pv) |
| `rec_pv_install_date` | timestamp[ns] |  | no | the date on the notification (observes D04.install_date) |
| `rec_pv_azimuth_deg` | double | degrees *(name)* | no | the orientation the installer recorded, at release-level coarseness (observes D04.pv_azimuth_deg) |
| `rec_shading` | string |  | no | the installer's shading note |
| `record_conflict` | string |  | no | a note where two sources disagree (assessor against installer) |
| `asset_since_removed` | bool |  | yes | true where the record still lists an asset that has since gone, because nobody told the register |

<a id="d31"></a>
#### D31 · `external_series` — Station weather, wholesale prices, carbon intensity, system demand, flex events

External series: station weather, wholesale prices, carbon intensity, system demand and flexibility-service events.

| | |
|---|---|
| access class / package | OBS / `observable/` |
| grain | series × timestamp: 8 hourly station series from Roches Point (real historical weather) (declared: *series-native*) |
| key | `series_id`, `ts` |
| path | `v1/<year>/observable/D31_part<NNN>.parquet` |
| parts | 1 part in 12 years |
| rows | 823,872 over 12 years; per year in §4.2 |
| size on B2 | 0.00 GB over 12 years |
| years present | 2015–2026 |
| schema conformance | full |
| time span, 2025 (`ts`) | 2025-01-01 00:00:00 → 2025-12-31 23:00:00 |

| column | type | unit | req. | meaning |
|---|---|---|---|---|
| `series_id` | string |  | yes | the publisher's own series identifier |
| `ts` | timestamp[ns, tz=UTC] |  | yes | the publisher's timestamp, on the publisher's interval convention |
| `value` | double |  | no | the published value; null during a station outage or publication gap (observes D15 for weather series) |
| `unit` | string |  | yes | as published |
| `station_or_zone` | string |  | yes | 6.4 item 7: the nearest official station, not the true site microclimate |
| `quality` | string |  | yes | the publisher's quality flag, including gap-filled values; one of: ok, estimated, missing, suspect, drift, fault |
| `provenance` | string |  | yes | measured, estimated or interpolated, as the publisher states; one of: metered, estimated, interpolated, operator-recorded, respondent-reported, modelled |
| `revision` | int64 |  | yes | the publication revision; prices and demand are revised after the fact |
| `realisation_id` | string |  | yes | the weather realisation this series is consistent with (6.5 rule 2: one realisation drives everything) |
| `segment` | string |  | yes | real historical \| generated projection (6.5 rule 2) |

## 5. `_segment/` and evidence files

### `_segment/` (added by the ops layer when the year was uploaded)

| file | what it is |
|---|---|
| `DONE.json` | the year's completion record (fields below) |
| `ENGINE.json` | engine identity for the year: `segment`, `engine_tag`, `code_digest`, `conf_digest`, `d18_era_gating`, `written_before_export` |
| `RUN_DIGESTS.json` | the run-wide engine identity the year must match: `code_digest`, `conf_digest`, `master_seed`, `note` |
| `export_report.json` | the export post-pass report: per-dataset verdict and reason, written/failed lists, totals, absent datasets, null-required fields |
| `verify_segment.log` | output of `scripts/verify_segment.py`: DONE, chain, checkpoints, D11, D15 `is_dst`, scan, rows vs manifests → PASS |

**`DONE.json`** fields:

| field | meaning |
|---|---|
| `segment` | the year |
| `days` | simulated days |
| `sim_day` | [first, last] global simulated day |
| `wall_h` | wall-clock hours for the year |
| `s_per_day` | seconds per simulated day |
| `peak_rss_mb` | simulation-phase peak memory, MB |
| `row_counts` | rows per dataset (equals the part manifests) |
| `chain_verify` | "chain verified" when the checkpoint hash chain verified |
| `export_written / export_failed` | datasets written by the export post-pass (18) and failed (0) |
| `scan` | secret/personal-data scan: `clean`, `hits` |
| `discarded` | true only for the discarded warm-up |
| `finished` | completion time (UTC) |
| `code_digest / conf_digest` | engine and configuration digests |
| `master_seed` | 20251010, one for the whole run (D-133) |
| `seed_of_record / seed_of_record_note` | a per-year hash for provenance only; not passed to the model |
| `b2_upload, provisional` | constants, not run state: `b2_upload` reads "SKIPPED - no credential …" in years the supervisor finished and "handled by ~/hrsd_occupants/ops/post_year.sh" in years the ops layer finished; `provisional` is always true. Every year was uploaded and checked |
| `u27_accepted_exceedances` | present only in 2020, 2024, 2025: the accepted PL-TEMP-01 failure, measured values and bounds |
| `rss_gate_exception` | present only in 2023–2026: peak, gate, accepted maximum, approval |
| `post_pass_resumed_by` | present where the ops layer completed the post-pass after the simulation |

Example (2026, abridged):

```json
{
  "segment": "2026",
  "days": 273,
  "sim_day": [
    4049,
    4321
  ],
  "wall_h": 3.47,
  "s_per_day": 45.7,
  "peak_rss_mb": 38102.9,
  "chain_verify": "chain verified",
  "export_written": 18,
  "export_failed": 0,
  "finished": "2026-10-19 11:34:28",
  "master_seed": 20251010,
  "seed_of_record": "acdff548202657a3",
  "row_counts": {
    "D16": 28619136,
    "D18": 320525256,
    "D19": 57251376,
    "…": "…"
  },
  "code_digest": "05328f32a44b8c94…",
  "rss_gate_exception": {
    "peak_rss_mb": 38102.9,
    "gate_mb": 18432,
    "accepted_max_mb": 40960,
    "approved": "…"
  }
}
```

### `run_diagnostics.json` (pkg root, written by the engine)

Top-level fields: `label`, `claim`, `coupling_mode`, `passport_effects`, `n_passport_effects_applied`, `n_passport_effects_that_changed_the_physics`, `passport_effects_with_no_rated_effect`, `occupancy_effects`, `n_occupancy_effects_applied`, `network_claim`, `master_seed`, `slice`, `mary`, `n_activity_intervals`, `n_appliance_cycles`, `max_physics_relative_residual`, `max_energy_closure_relative_residual`, `feeder_peak_w`, `feeder_peak_w_per_home`, `checkpoint_chain_head`, `benchmark`, `feeder_shape`, `awake_share`, `venues`, `network`, `behaviour_switches`, `annual_electricity`, `plausibility`.

The ones most used: `benchmark` (machine, `n_homes`, `n_people`, `n_days`, per-day timings, `peak_rss_mb`, `storage.by_dataset`, `d18_era` with home-days by era and the rollout record), `max_physics_relative_residual` and `max_energy_closure_relative_residual` (solver closure), `checkpoint_chain_head`, `plausibility` (the U27 summary), `annual_electricity`, `feeder_peak_w`, `mary` (the design 5.9 move-in scenario) and `network_claim`/`coupling_mode`.

Example (`benchmark.d18_era`, 2026):

```json
{
  "home_days_by_era": {
    "none": 50778,
    "meter_30min": 163702,
    "full_1min": 83636
  },
  "n_ever_metered": 906,
  "first_install": "2019-10-02",
  "last_install": "2025-08-29",
  "first_enrolment": "2021-01-05",
  "meter_era_channels": [
    "import_w",
    "export_w"
  ],
  "meter_era_interval_s": 1800
}
```

### `evidence/plausibility.json` (U27)

Summary fields: `label`, `claim`, `design_ref`, `package_root`, `n_checks`, `by_outcome`, `families`, `n_pass`, `n_fail`, `n_not_evaluable`, `n_no_data`, `n_sourced`, `n_unsourced`, `n_pass_sourced`, `n_pass_unsourced_band`, `all_evaluable_checks_pass`, `unsourced_families`, `n_pass_independent`, `n_pass_against_a_calibration_input`, `n_pass_against_a_design_exposed_reference`, `checks_against_calibration_inputs`, `rule`.

`results` holds one record per check (12) with `check_id`, `quantity`, `family`, `outcome` (`PASS`, `FAIL`, `NOT_EVALUABLE`, `NO_DATA`), `sourced`, `measured`, `reference`, `source_key`, `source_sha256`, `source_exposure`, `tolerance`, `tolerance_basis`, `detail` and `note` (why a check could not be evaluated). The checks: `PL-DHW-01`, `PL-APPL-02`, `PL-APPLSIZE-01`, `PL-ELEC-01`, `PL-GAS-01`, `PL-APPL-01`, `PL-AREA-01`, `PL-MIX-01`, `PL-TEMP-01`, `PL-APPLSHARE-01`, `PL-EVHP-01`, `PL-PEAK-01`.

Example (2025, PL-TEMP-01, abridged):

```json
{
  "check_id": "PL-TEMP-01",
  "quantity": "indoor living-zone temperature distribution",
  "family": "indoor temperature",
  "outcome": "FAIL",
  "sourced": false,
  "measured": {
    "median_c": 19.27,
    "share_above_28c": 0.0008,
    "max_c": 43.3
  },
  "tolerance": "median 15-23 C; <=5% above 28 C; peak <=40 C [A]"
}
```

### `evidence/` Parquet (D22, D23, D24)

D22 (appliance waveform templates), D23 (the run's identity record: code, schema, seed, parameters, outputs, checkpoint chain head) and D24 (every empirical target with source, version and tolerance) are datasets like the others; their schemas are in §4.

## 6. `docs/`

| file | purpose |
|---|---|
| `RELEASE_NOTES_v1.md` | what v1 is, per-year figures, how it was run, the checks, and the accepted exceptions |
| `PROVENANCE.md` | run provenance (engine tag, digests, seed, inputs, environment, each year's chain head) and dataset provenance (sources, licences, transforms) |
| `V1_KNOWN_LIMITATIONS.md` | everything v1 does not do, or does with a caveat, and what is carried to v2 |
| `V1_BUCKET_STRUCTURE.md` | this file: what is in the bucket and how it is laid out |

## 7. Known limitations, in brief

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

