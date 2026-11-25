# Baile Nua v1 — release notes

**UNVALIDATED SIMULATION EVIDENCE: E1 engineering candidate.** Engineering
verification only; no behavioural calibration is claimed. Read
`V1_KNOWN_LIMITATIONS.md` before using any of it.

Released 2026-10-19. Engine `v1-engine-freeze-2.3`.

## What v1 is

A minute-resolution behavioural and physical replay of one Irish town (the
Cobh small areas: **1,092 homes, 2,917 people**) from **1 January 2015 to
30 September 2026**, preceded by a discarded one-month warm-up (December 2014).
That is **4,291 simulated days** in twelve yearly packages, plus 31 warm-up days.

The population is the 2022 census town throughout, so v1 is a twelve-year replay
on a **fixed 2022 town**, not a study of dwelling-stock growth
(`V1_KNOWN_LIMITATIONS.md` §1). Weather, calendar, tariffs, behaviour and
physics follow the simulated year.

The network runs coupled: the replay solves the LV power flow every 15-minute
epoch (`coupling_mode: C2`, `solve_network: true`). The `network_claim` text in
each `run_diagnostics.json` still describes E1's C1 mode; it is stale
(`V1_KNOWN_LIMITATIONS.md` §14).

## Where it is

| what | path |
|---|---|
| a year's package | `b2eig:hrsd-occupants/v1/<year>/` with `ground_truth/`, `observable/`, `evidence/`, `run_diagnostics.json` |
| that year's run record | `b2eig:hrsd-occupants/v1/<year>/_segment/`: `DONE.json`, `ENGINE.json`, `export_report.json`, `RUN_DIGESTS.json`, `verify_segment.log` |
| these documents | `b2eig:hrsd-occupants/v1/docs/` (listed under *Documents* below) |

Every Parquet part has a sidecar `*.manifest.json` with its dataset, access
class, row count, schema conformance, `file_sha256` and `content_hash_sha256`.
The warm-up is verified and not published (`discard_output: true`).

## Per year

| year | days | rows | GB on B2 | objects | D18 rows | wall h | s/day | finished (UTC) | `rclone check` |
|---|---|---|---|---|---|---|---|---|---|
| 2015 | 365 | 186,527,871 | 5.88 | 201 | 0 (gated) | 4.3 | 42.4 | 2026-10-16 19:39:07 | 0 differences |
| 2016 | 366 | 187,049,268 | 5.90 | 201 | 0 (gated) | 4.31 | 42.4 | 2026-10-17 00:00:03 | 0 differences |
| 2017 | 365 | 186,528,345 | 5.88 | 201 | 0 (gated) | 4.29 | 42.4 | 2026-10-17 04:19:47 | 0 differences |
| 2018 | 365 | 186,497,378 | 5.89 | 203 | 0 (gated) | 4.31 | 42.5 | 2026-10-17 08:40:13 | 0 differences |
| 2019 | 365 | 186,680,145 | 5.88 | 211 | 216,754 | 4.31 | 42.5 | 2026-10-17 13:00:56 | 0 differences |
| 2020 | 366 | 192,147,037 | 5.93 | 243 | 5,201,585 | 4.16 | 40.9 | 2026-10-17 19:19:04 | 0 differences |
| 2021 | 365 | 234,267,835 | 6.28 | 227 | 47,850,813 | 4.56 | 45.0 | 2026-10-17 23:55:19 | 0 differences |
| 2022 | 365 | 309,479,811 | 6.88 | 227 | 123,091,117 | 5.23 | 51.5 | 2026-10-18 05:11:10 | 0 differences |
| 2023 | 365 | 387,630,902 | 7.52 | 227 | 201,141,005 | 4.41 | 43.5 | 2026-10-18 13:53:09 | 0 differences |
| 2024 | 366 | 469,171,131 | 8.18 | 229 | 282,188,959 | 4.52 | 44.5 | 2026-10-18 21:10:37 | 0 differences |
| 2025 | 365 | 547,936,032 | 8.81 | 229 | 361,444,721 | 4.56 | 45.0 | 2026-10-19 05:14:47 | 0 differences |
| 2026 (to 30 Sep) | 273 | 459,898,507 | 6.99 | 201 | 320,525,256 | 3.47 | 45.7 | 2026-10-19 11:34:28 | 0 differences |
| **total** | **4,291** | **3,533,814,262** | **80.01** | **2,600** | **1,341,660,210** | **52.4** | | | |

*Rows* is the sum of `DONE.json` `row_counts` over 25 datasets, 26 once D18
appears in 2019 (D17_aggregate counted on its own); it matches the part manifests. *GB* and *objects* are what
`rclone size` reported on B2 after upload, including `_segment/`. *Wall h* and
*s/day* are from `DONE.json`. For years the supervisor finished (2015–2019,
2021, 2022) they cover the simulation, including its 30-day flushes, up to the
end of `run_year`; the export post-pass adds about 14 minutes a year and is not
included. For years the ops layer finished (2020, 2023–2026) they are the span
of the year's daily checkpoints plus the post-pass (about 1.5 minutes), so the
end-of-year U27 step and the time lost to the stopped retry are not included.

## What each year contains

The same in every year delivered (`release_fill.py` re-checks this across all
twelve at the end):

* **Engine-streamed (7):** D10 activities, D11 presence, D13 appliance cycles,
  D16 building state, D17 network state, D17_aggregate, D19 edge exports. D18
  observations from 2019 onward (era-gated, `V1_KNOWN_LIMITATIONS.md` §3).
* **Written by the export post-pass (18):** D01, D02, D04, D05, D06, D07, D08,
  D14, D15, D21, D22, D23, D24, D27, D28, D29, D30, D31. `export_failed: 0` in
  every year. D04 and D24 are `schema_conformance: partial`: required fields the
  model holds no value for are null by declaration and listed in each manifest's
  `null_required_fields`.
* **Absent, each with its reason in `export_report.json` (6):** D03, D09, D20
  (no ten-year life-course artefact), D12 (trips are not retained), D25 and D26
  (owned by the MIMIC exporter). See `V1_KNOWN_LIMITATIONS.md` §2.
* **D11 presence covers days 1–14 of each year**, not the whole year
  (`V1_KNOWN_LIMITATIONS.md` §4).
* **D16 building state is written every 15 minutes** (`D16_EPOCH_MINUTES = 15`,
  the network epoch; 96 rows per building-day), although `datasets.yaml`
  declares a 1-minute grain. The solver itself steps at 1 minute
  (`V1_KNOWN_LIMITATIONS.md` §17).
* **Part files.** Streamed datasets are flushed on every 30th *global* simulated
  day, so a year's first and last parts are partial: 13 parts in most years,
  **14 in 2020** (3 + 12 × 30 + 3 days) and 11 in 2026. Read a dataset as the
  union of its parts.
* **D14 `attendance_prob`** is `struct<adult, child, visitors>` in every year
  except **2022**, where it is `struct<all, child, adult, visitors>`
  (`V1_KNOWN_LIMITATIONS.md` §19). Every other dataset has the same schema in
  every year.

## Identity of record

Every segment, including the warm-up, ran on one engine and one configuration:

| | |
|---|---|
| engine tag | `v1-engine-freeze-2.3` (repo at `v1-engine-freeze-2.3-4-g7eb40a9`; none of the four commits after the tag touches `scripts/baile_nua` or `scripts/replay_config.json`) |
| code digest (`scripts/baile_nua/**/*.py`) | `05328f32a44b8c94e900c2c0ca718ce83fb89569256582d169e3179cdf2eb163` |
| config digest (`scripts/baile_nua/**/*.{yaml,json}`) | `e0ab1c8351e1e15308cd4de2d5ab83da0869f41ba12963c92715265330698e1d` |
| replay config | `scripts/replay_config.json`, sha256 `6f1e4fc4c367a28c79e0c3cab224fb69b8b7daf50a7461ee62114d83c0570de8` |
| master seed | `20251010`, one seed for the whole chain (D-133); each year's `seed_of_record` is provenance only and never reaches the model |

The authoritative per-year identity is that year's `_segment/DONE.json`
(`code_digest`, `conf_digest`) and `_segment/ENGINE.json`, with
`RUN_DIGESTS.json` at the run root. Each year restores from the previous year's
final checkpoint, and `DONE.json` `chain_verify` records that the year's
checkpoint chain verified. `PROVENANCE.md` lists each year's chain head and seed
of record.

D23 inside each package is built by the export and reads `ENGINE.json` under
I-115. Checked in all twelve years: each D23 **part manifest** records
`d23_freeze_tag = v1-engine-freeze-2.3`, the code and config digests above and
`d23_engine_version_source = "recorded by the run (ENGINE.json)"`. The D23
**data row**, however, still carries git-reconstructed labels
(`code_version = 0.1.0a1+e1-reconstructed`, `code_git_sha = fdef627…-reconstructed`,
the original `v1-engine-freeze` tag), which are not the engine any year ran on.
Use `DONE.json`/`ENGINE.json` (or the D23 manifest), not the D23 row, as the
provenance of record (`V1_KNOWN_LIMITATIONS.md` §6).

**Two fields in `DONE.json` are stale and must be ignored.** The frozen
supervisor writes `"b2_upload": "SKIPPED - no credential, rotation unconfirmed
(D-125)"` and `"provisional": true` as constants (`replay_supervisor.py:564`).
Every year *was* uploaded and checked; the record of that is the presence of
`_segment/` on B2 and the per-year `rclone check` above
(`V1_KNOWN_LIMITATIONS.md` §10). Years finished by `ops/finish_segment.py`
(2020 and 2023–2026) carry `"b2_upload": "handled by
~/hrsd_occupants/ops/post_year.sh"` and a `post_pass_resumed_by` field instead.

## How it was run

| | |
|---|---|
| host | AWS EC2 `r7a.2xlarge` (8 vCPU, 61 GiB), eu-west-1, Ubuntu 24.04.4 LTS, kernel 7.0.0-1014-aws, Python 3.12.3; shared with another project, whose load had no measurable effect on the rate |
| environment | venv built from the Mac's exact `pip freeze`. The nine libraries that can change a simulated number match the Mac: numpy 2.2.6, pandas 2.3.3, pyarrow 25.0.1, duckdb 1.5.6, numba 0.62.1, scipy 1.18.1, pvlib 0.16.1, pandapower 3.5.6, pypdf 6.20.0. BLAS/OpenMP threads pinned to 1 |
| inputs | `sources/` verified by sha256 against its manifests before the run: all 81 manifested files matched |
| pre-run checks | engine digest matched; test suite 1,199 passed, 17 failed, 44 skipped, all 17 explained (`V1_KNOWN_LIMITATIONS.md` §11); smoke test (warm-up plus 7 days) passed `verify_segment.py` with 18 datasets exported and none failed; it was **not** compared byte-for-byte with the Mac, whose smoke outputs were not in the transfer (fingerprints kept in `~/hrsd_occupants/ops/logs/smoke_fingerprint.txt`); kill/resume byte-identical to an uninterrupted run, both for a killed year child and for a whole-supervisor crash and restart |
| supervision | `scripts/replay_supervisor.py`, one subprocess per year (D-148), under systemd (`baile-nua-v1.service`), with an ops layer outside the frozen tree (`~/hrsd_occupants/ops/`): watchdog, per-year verification and upload, email alerts, loop guard |
| per year, before upload | `verify_segment.py` on the package; a scan for credential strings; then `rclone copy --checksum` and `rclone check` with 0 differences required |
| run start | 2026-10-16 10:56:04 UTC (first child spawned) |
| run end | 2026-10-19 11:34:28 UTC (last `DONE.json`) |
| elapsed | 72.6 h, including the lost attempt below and every post-pass |
| compute cost estimate | 72.6 h × US$0.61–0.70/h = US$44–51 (on-demand r7a.2xlarge eu-west-1 at US$0.61–0.70/h, an estimate not checked against the AWS bill; EBS and B2 storage excluded) |

**Attempts.** Every year's published package is its first simulation except 2015, which was simulated twice. 2020, 2023, 2024, 2025, 2026 each also have an in-process retry that was stopped within minutes and kept as `<year>.superseded.<ts>`; the finished first simulation is the one published. In 2015 the first attempt simulated all
365 days and was then killed for running out of memory in the U27 plausibility
step, which loads the whole year of D13/D16/D18/D19 into memory (63 GB on a
61 GiB host). The supervisor renamed it aside as `2015.partial.1792163952`
(kept, never deleted, D-135) and re-ran the year from the warm-up checkpoint,
which cost about 4.3 h. After a 96 GB swapfile and `MemoryHigh=52G` were added,
U27 held 49.7–53.2 GB resident and completed every year, with the rest in swap.
Swap use grew with D18: systemd recorded swap peaks of 94.2 GB over 2021–2023,
then 128.7 GB (2024), **158.8 GB (2025)** and 126.0 GB (2026), so swap was
raised to 200 GB on 2026-10-18 before 2024's U27. Logged as EC2-1 in
`docs/V2_PLAN.md`.

In 2020 the year simulated in full and `run_year` then stopped on U27 check
PL-TEMP-01 (below). The supervisor began an in-process retry from day 0; it was
stopped and kept as `2020.superseded.1792257925`, and the finished attempt was
restored and completed by `ops/finish_segment.py` without re-simulating.
2023–2026 were finished the same way: the supervisor failed each of them on
the memory gate, and 2024 and 2025 first on PL-TEMP-01 inside `run_year`. The
stopped retries
are kept as `2023.superseded.1792323002`, `2024.superseded.1792357691`,
`2025.superseded.1792386739` and `2026.superseded.1792409588`. No year was
re-simulated after 2015.

## Checks every year passed

From each year's `DONE.json`, `run_diagnostics.json` and the ops log
(`release_fill.py` re-checks every year at the end):

* checkpoint chain verified; `verify_segment.py` passed;
* export: 18 written, 0 failed; secret and personal-data scan clean; no B2 key
  string in any text file;
* physics residual ≤ 3.3 × 10⁻¹² relative; energy closure ≤ 6.3 × 10⁻¹⁶
  relative (maxima over all twelve years);
* U27 plausibility, 12 checks: **10 pass, 2 not evaluable** (PL-APPLSHARE-01,
  PL-EVHP-01: no reference) in 2015–2019 and 2021–2023; **9 pass, 1 FAIL
  accepted, 2 not evaluable** in 2020, 2024 and 2025 (PL-TEMP-01, below); and in
  **2026, 5 pass, 2 not evaluable and 5 `NO_DATA`**. 2026 has 273 days, and
  PL-DHW-01, PL-ELEC-01, PL-GAS-01, PL-MIX-01 and PL-PEAK-01 compare annual
  quantities that need at least 350; U27 does not extrapolate a partial year.
  No other check failed in any year. Per year: 2015 10 pass / 0 fail / 2 not evaluable; 2016 10 pass / 0 fail / 2 not evaluable; 2017 10 pass / 0 fail / 2 not evaluable; 2018 10 pass / 0 fail / 2 not evaluable; 2019 10 pass / 0 fail / 2 not evaluable; 2020 9 pass / 1 fail (1 accepted) / 2 not evaluable; 2021 10 pass / 0 fail / 2 not evaluable; 2022 10 pass / 0 fail / 2 not evaluable; 2023 10 pass / 0 fail / 2 not evaluable; 2024 9 pass / 1 fail (1 accepted) / 2 not evaluable; 2025 9 pass / 1 fail (1 accepted) / 2 not evaluable; 2026 5 pass / 0 fail / 2 not evaluable / 5 NO_DATA. In a full
  year the 10 passes split as 6 against independent references, 2 against sources the model
  was calibrated on (PL-ELEC-01, PL-GAS-01: consistency checks, not validation),
  1 against a design-exposed reference and 1 against a declared band. Three
  families have no published source: EV and heat-pump consumption, appliance
  energy shares, indoor temperature;
* simulation-phase peak RSS within the 18 GB gate (`rss_gate_mb: 18432`) in
  2015–2022: 9.4–9.8 GB to 2020, then rising with D18 1-minute coverage. From
  2023 the gate is exceeded and accepted as an operational exception (below).
  Per year: 2015 9,465.1 MB; 2016 9,467.5 MB; 2017 9,446.4 MB; 2018 9,405.5 MB; 2019 9,441.2 MB; 2020 9,809.3 MB; 2021 13,176.8 MB; 2022 18,331.3 MB; 2023 23,716.1 MB; 2024 28,996.8 MB; 2025 34,258.6 MB; 2026 38,102.9 MB.

## Accepted U27 exceedances

U27 is a standing requirement: a year that fails a plausibility check is not
delivered. One exception was approved on 2026-10-17 (Brian O'Regan, "accept and
document") and is applied by the ops layer only; the engine and configuration
are unchanged.

**PL-TEMP-01, indoor living-zone temperature.** Its band is a declared
assumption `[A]`, not a published reference: annual median 15–23 °C, at most 5 %
of epochs above 28 °C, peak at most 40 °C. No CSO or SEAI table publishes
measured Irish indoor temperatures, so **the 40 °C ceiling has no published
source**. In 2020 the peak reached 41.15 °C while the median (18.96 °C) and the
share above 28 °C (0.03 %) stayed where they were in 2015–2019 (peaks 37.19–39.86 °C,
medians 18.80–19.01 °C).

From 2020 a PL-TEMP-01 failure is accepted only while **all** of these hold;
outside them, or if any other check fails, the year still blocks:

| | accepted while |
|---|---|
| peak | ≤ 45 °C |
| median | 17.80–20.01 °C (the 2015–2019 range ± 1 °C) |
| share of epochs above 28 °C | ≤ 0.5 % |

Each accepted exceedance is recorded in that year's `_segment/DONE.json` under
`u27_accepted_exceedances`, with the measured values, the declared band and the
bounds it was accepted within. The package's own `evidence/plausibility.json`
still reports the FAIL unchanged.

| year | peak °C | median °C | share > 28 °C |
|---|---|---|---|
| 2020 | 41.15 | 18.96 | 0.03 % |
| 2024 | 41.38 | 19.04 | 0.03 % |
| 2025 | 43.3 | 19.27 | 0.08 % |

Which dwelling and room drive the peak is not yet known; finding out, and
sourcing the ceiling, is in `docs/V2_PLAN.md` (EC2-2) and
`V1_KNOWN_LIMITATIONS.md` §15.

## Operational exception: the peak-RSS gate (2023–2026)

The supervisor's year check fails a year whose simulation-phase peak RSS is
above `rss_gate_mb` (18,432 MB, frozen configuration). Peak RSS grows with the
number of home-days recording D18 at 1-minute resolution: 9.4–9.8 GB to 2020,
13.2 GB in 2021, 18.3 GB in 2022 and 23.7 GB in 2023. The gate was set as a
fixed figure for the Mac's 32 GB, before D18 1-minute coverage grew through the
decade, and every year from 2023 exceeds it.

Approved on 2026-10-18 (Brian O'Regan) as a **v1 operational exception with no
output impact**: for 2023–2026 the ops layer (`ops/finish_segment.py`) accepts a
gate failure only while the peak is **≤ 40 GB (40,960 MB)** and nothing else in
the year check fails. The gate measures memory, not results: the simulation,
its checkpoints and every published file are what an unexceeded run writes. The
engine and configuration are unchanged. Each acceptance is recorded in that
year's `_segment/DONE.json` under `rss_gate_exception`.

| year | peak RSS, MB | gate, MB | accepted up to, MB |
|---|---|---|---|
| 2023 | 23,716.1 | 18,432 | 40,960 |
| 2024 | 28,996.8 | 18,432 | 40,960 |
| 2025 | 34,258.6 | 18,432 | 40,960 |
| 2026 | 38,102.9 | 18,432 | 40,960 |

Making the gate year-aware is in `docs/V2_PLAN.md` (EC2-3) and
`V1_KNOWN_LIMITATIONS.md` §16.

## Reading it

* Each year stands alone: its package holds everything for that year, with its
  own D01/D02/D05–D08 (the same town every year).
* Ground truth (`ground_truth/`, access class GT) and the observable view
  (`observable/`, OBS) are kept apart; each manifest states its
  `access_class` and `release_package`.
* D18 timestamps carry modelled device clock error and are deliberately not
  corrected, so they run past the end of the year they belong to.
* 2026 ends on 30 September (273 days). Its annual U27 checks are `NO_DATA`, and
  the `*_kwh_yr` figures in its `run_diagnostics.json` are nine-month sums
  (`V1_KNOWN_LIMITATIONS.md` §18).
* `run_diagnostics.json` holds the town summary, the feeder shape, annual
  electricity per dwelling, the benchmark and the U27 result.

## Documents

All in `b2eig:hrsd-occupants/v1/docs/`:

| file | what it is |
|---|---|
| `RELEASE_NOTES_v1.md` | this file |
| `PROVENANCE.md` | run provenance (engine, configuration, seed, inputs, environment, each year's chain head) and dataset provenance (sources, licences, transforms) |
| `V1_KNOWN_LIMITATIONS.md` | everything v1 does not do, or does with a caveat, and what is carried to v2 |
| `V1_BUCKET_STRUCTURE.md` | the bucket's layout: every prefix, path convention and dataset with its grain, key, part counts, rows per year and full schema, plus the `_segment/` and evidence files |

## Changes since the Mac run

The Mac replay that preceded this (2015 on freeze-2.2, later years on 2.3, no
upload) is **superseded and not part of v1**. v1 was re-run from the warm-up on
the instance with one engine throughout. As a result, Mac-run limitations §5
(mixed engines), §10 (no upload) and the 2015 export catch-up no longer apply;
see `V1_KNOWN_LIMITATIONS.md`.
