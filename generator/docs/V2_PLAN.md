# V2 plan — instance addendum

> **Merge note.** `docs/V2_PLAN.md` exists on the Mac but was not in
> `hrsd_occupants.tgz`. This file was started on the EC2 instance on
> 2026-10-16 and holds only the entries raised here. Merge them into the Mac's
> copy (as new numbered items) rather than letting either file replace the other.

## EC2-1 — U27 plausibility suite loads whole-year datasets into memory (OOM on Linux)

**Seen:** v1 replay on EC2 (`r7a.2xlarge`, 61 GiB RAM, no swap), 2015 segment,
16 Oct 2026. All 365 simulated days finished at 15:15:44 UTC (child peak RSS
about 9.6 GB). Then `run_year` wrote `run_diagnostics.json` and called the U27
suite (`baile_nua.plausibility.write_suite`, from `engine/e1_run.py` after
line 1305). Within 83 s the child reached **63.2 GB anon RSS** and the kernel
OOM killer ended it (15:17:07, `oom-kill`, `task_memcg=/system.slice/baile-nua-v1.service`).
systemd restarted the supervisor, which renamed the attempt aside
(`2015.partial.1792163952`, kept) and re-ran 2015 from day 0. The cost was 4 h 07 min.

**Cause:** `plausibility/suite.py::_package()` reads every part of D16, D13,
D18 and D19 for the whole year, with every column, into pandas at once
(`pd.concat([pd.read_parquet(f) for f in files])`). D16 alone is 13 parts of
about 0.23 GB compressed Parquet per year. Memory therefore grows with the
segment's length and the town's size, not with what each check needs, and
the concat briefly holds each dataset twice. On the Mac (32 GB) this finished
only because macOS swaps and compresses memory. Linux with no swap does not.

**Why the run's guard did not catch it:** the supervisor's memory gate runs in
the per-day progress callback. Nothing calls that callback during the
plausibility or export post-pass, so nothing limits memory there.

**v1 handling (no engine or config change):** a 96 GB swapfile
(`/swapfile.baile-nua`) and `MemoryHigh=52G` on `baile-nua-v1.service`, so
the suite pages out rather than being killed, and the shared instance keeps
about 9 GB of RAM. Expect each year's U27 step to run slower while it is paging.

**v2 fix:**
1. In `_package()`, read only the columns each check uses (pass the column
   list through `pd.read_parquet(columns=...)`). Better still, compute the
   checks' aggregates part by part, or with DuckDB over the Parquet glob, so
   peak memory does not depend on segment length.
2. Never concatenate a whole year of D16 in memory. If a check needs the whole
   series, give it an iterator over parts.
3. Extend the memory gate to the post-run phases. Run U27 and the export
   post-pass under a current-RSS watchdog, or as their own subprocess with an
   `RLIMIT_AS` or cgroup limit, so a blow-up is a recorded failure and not a
   kernel kill that throws away a simulated year.
4. Make a restart after a crash in the post-run phases resume from the
   segment's final checkpoint instead of re-simulating the year. The
   checkpoints for all 365 days were intact and chain-verified.
5. Regression test: run U27 on a 365-day town package under a memory limit
   (for example 16 GB) and assert that it finishes.

## EC2-2 — PL-TEMP-01: indoor peak above the assumed 40 °C ceiling (2020 on)

**What happened (2026-10-17).** 2020's U27 check PL-TEMP-01 failed: peak
living-zone temperature **41.15 °C** against a ceiling of 40 °C. The median
(18.96 °C) and the share of epochs above 28 °C (0.03 %) were in line with
2015–2019 (peaks 37.19–39.86 °C, medians 18.80–19.01 °C). The 40 °C ceiling is a
declared assumption `[A]` with no published source (`tolerance_basis: "declared,
not sourced"`).

**v1 handling (no engine or config change):** accepted and documented. From 2020
`~/hrsd_occupants/ops/finish_segment.py` accepts a PL-TEMP-01 FAIL only while the
peak is ≤ 45 °C, the median is within 17.80–20.01 °C and the share above 28 °C is
≤ 0.5 %, and records it in the year's `DONE.json` (`u27_accepted_exceedances`).
Anything else still blocks. Because `KNOWN_PLAUSIBILITY_FAILURES` is frozen,
`run_year` still raises, and each such year costs an in-process retry, stopped by
the watchdog, before the post-pass is finished outside the engine.

**v2 work:**
1. Find what drives the peak: from 2020's D16, the dwelling(s), zone and
   timestamps of every living-zone epoch above 40 °C (and above 38 °C for
   context), and from D02/D04/D13/D15 the cause: solar gain through the
   `rc_solar_aperture_m2` aperture in a heatwave, an emitter or appliance left
   on, a low-capacitance zone, or a control fault. Then check whether the same
   dwellings hold the 2015–2019 peaks.
2. Source the ceiling. Look for measured Irish or UK indoor-temperature data
   (for example monitored-dwelling or overheating studies) and replace the
   declared 40 °C with a sourced peak, or a high percentile such as the 99.99th,
   which a single epoch cannot fail. Record the source in the registry and in
   D24.
3. If the peak is a model defect, fix it in the engine. If it is plausible, put
   PL-TEMP-01's new form in the engine's own check rather than an ops override.
   Either way, retire the ops override.
4. Let U27 report the location (building, zone, timestamp) of an extreme it
   fails on, so the next one can be diagnosed from `plausibility.json` alone.

## EC2-3 — The peak-RSS gate is one fixed figure; D18 1-minute memory grows each year (2023 on)

**What happened (2026-10-18).** 2023 was blocked by the supervisor's year check:
simulation peak RSS **23,716 MB** against `rss_gate_mb: 18432`. U27 and every
other check passed. Peak RSS rises with the home-days recording D18 at 1-minute
resolution, about 9.8 GB + 0.27 MB per such home-day: 9.4–9.8 GB to 2020,
13.2 GB in 2021 (10,372 home-days), 18.3 GB in 2022 (31,175), 23.7 GB in 2023
(51,979). Every later year exceeds the gate. Separately, the in-run check never
fires on Linux: `_current_rss_mb` reads `ps` output in macOS units, 1000 times
too low, so the gate acts only after the year has finished.

**v1 handling (no engine or config change):** an operational exception approved
by Brian. For 2023–2026 `~/hrsd_occupants/ops/finish_segment.py` accepts the
gate failure only while the peak is ≤ 40 GB and it is the only failure, and
records it in `DONE.json` (`rss_gate_exception`). Swap raised from 96 to 200 GB
for U27.

**v2 work:**
1. Make the gate year-aware: derive each segment's limit from its expected D18
   era coverage (home-days by era, known before the year starts) plus a margin,
   or set it per segment in the replay config, instead of one figure for all
   years.
2. Find what holds the D18 1-minute rows in memory through the year (RSS climbs
   steadily from day 1 to day 365) and flush it at the 30-day points like the
   other streamed datasets, so peak RSS stops depending on the year.
3. Fix `_current_rss_mb` for Linux (read `/proc/self/status` VmRSS, or psutil)
   so the in-run gate and the 8 GB warning work there.
4. Extend the gate to the post-run phases (with EC2-1).

## EC2-4 — Small record and schema fixes found while writing the v1 release (2026-10-19)

None affects a simulated number; each makes a published record say what the run did.

1. **D23 row identity.** The D23 part manifest records `d23_freeze_tag =
   v1-engine-freeze-2.3` from `ENGINE.json`, but the D23 row's `code_version`,
   `code_git_sha` and `code_tree_hash` are still reconstructed from git and name
   the first freeze (`fdef627`). Fill the row from `ENGINE.json` too, and drop
   the stale E1 `network_claim` from `parameters`.
2. **D14 `attendance_prob`.** One struct in every year: 2022 has an extra `all`
   field and a different field order. Fix the field set and order at write time.
3. **D16 declared grain.** `datasets.yaml` says 1 minute; the engine writes
   15 minutes (`D16_EPOCH_MINUTES`). Make the schema say 15 minutes, or make the
   epoch configurable and declared.
4. **Partial years.** 2026's `*_kwh_yr` diagnostics are nine-month sums under
   annual names; record the day count beside them, or annualise and say so.
5. **All-null timestamp columns** (D05 `death_date`, D30 `rec_pv_install_date`)
   are written timezone-naive; give them the declared `timestamp[ns, tz=UTC]`
   type even when empty.
