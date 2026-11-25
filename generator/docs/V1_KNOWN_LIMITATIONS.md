# v1 — known limitations

**v1 scope was frozen on 2026-10-15 at 16:45.** Engine `v1-engine-freeze-2.3`,
code digest `05328f32a44b8c94…`, for every segment. Every item below is accepted
for v1 and carried to v2 (`docs/V2_PLAN.md`); none is a defect to be fixed in
place.

This version describes the **EC2 run**, which re-ran the whole replay from the
warm-up on one engine. It replaces the Mac-run edition: items that run settled
are marked *resolved*, and every figure here comes from the EC2 packages'
metadata. A figure measured only on the Mac is labelled as such.

---

## 1. The population does not vary with the simulated year (P-7, I-119; accepted for v1 only)

`synthesise_t0` takes no year and no as-of date; `T0` is pinned at 2022-01-01.
Every segment's `run_diagnostics.json` records the same **1,092 homes, 2,917
people** (119 with PV, 44 with a battery, 105 with an EV).

So each year contains every dwelling in the 2022 census stock, including
estates completed after the simulated year. **Cluain Ard (completed 2019)**
draws load in 2015, four years before it was built, and **Belgard (completed
2024)** nine years before. The same holds for every year before each estate
completes.

**Still correct for its year:** weather, calendar, behaviour, physics, tariffs
and every sourced input. The limitation is confined to *which dwellings exist
when*.

**How to read v1:** a twelve-year behavioural and physical replay on a **fixed
2022 town**, not a study of dwelling-stock growth. The map's year slider reads
`valid_from`/`valid_to` from D01/D02, so it will disagree with the data for any
year before an estate completes.

v2 moves T0 to 2015 with estate gating (`docs/V2_PLAN.md` §1).

## 2. Six datasets are absent from every year

Each absence is recorded in the year's `export_report.json` with its reason, so
the package says what it does not contain rather than leaving it out silently.
`export_failed: 0` is correct: these are absences, not failures. The same six in
all twelve years (re-checked by `ops/release_fill.py` at release).

| dataset | why absent |
|---|---|
| **D03** building passport | converted from `pkg/evidence/wp5_tenyear.json`, which only a run that steps the ten-year life course produces. The replay steps none, so no passport event is ever created. |
| **D09** life events | same artefact, same cause. |
| **D20** change labels | same artefact, same cause. |
| **D12** trips | no trip row survives the day. `activity.engine` computes travel only for EV state of charge; `DayResult` has no `trips` field and `StreamWriter` has no D12 buffer. |
| **D25** MIMIC participant panel | owned by the MIMIC exporter, not by this package. |
| **D26** MIMIC answer key | owned by the MIMIC exporter, not by this package. |

**D03/D09/D20 could not have been back-filled.** The only `wp5_tenyear.json`
that exists describes `span 2022-2031` for a 60-home slice. Two guards reject
it: `from_evidence._epoch` requires the artefact's day 0 to equal the package's
`t0` (a seven-year error that would displace every event), and 60 homes beside
1,092 would recreate I-091, where D03/D09/D20 shared no person with D05/D06/D08.
This is the **same root cause as §1**: the life-course machinery is built on a
2022 origin.

`run_diagnostics.json` also carries the design 5.9 "Mary" move-in scenario
under `mary` (household H-000023, a family of four moving in with Mary on
`move_in_date` 2022-07-08). **It does not reach the replay's physics in any
year:** occupancy changes are applied only through the run's occupancy schedule
(`engine/e1_run.py`, `apply_occupancy_change`), and `occupancy_effects` is empty
and `n_occupancy_effects_applied` and `n_passport_effects_applied` are 0 in all
twelve years, 2022 included. The `mary` block is a description of the scenario,
not a record of it happening, and with D09/D20 absent there is no dataset row
for it either.

## 3. D18 appears only from late 2019, and is era-gated

D18 (rendered device readings) is streamed by the engine. `d18_era_gating` is
**true** in the configuration and in every `ENGINE.json`, so D18 is written only
for home-days whose device era exists. The run's rollout, from
`run_diagnostics.json` `benchmark.d18_era`:

| | |
|---|---|
| first meter install | 2019-10-02 |
| last meter install | 2025-08-29 |
| homes ever metered | 906 of 1,092 (186 never; final share 0.83) |
| first study enrolment (1-minute era) | 2021-01-05 |
| homes ever enrolled | 328 (D-111 / A-99) |
| meter-era channels | `import_w`, `export_w` at 1,800 s |

2015–2018 have no D18 rows by design: every home-day is in era `none`
(398,580 home-days, 399,672 in 2016).

| year | D18 rows | D18 GB (local, from the benchmark) | home-days meter_30min | home-days full_1min |
|---|---|---|---|---|
| 2019 | 216,754 | 0.00 | 2,268 | 0 |
| 2020 | 5,201,585 | 0.04 | 54,419 | 0 |
| 2021 | 47,850,813 | 0.40 | 116,163 | 10,372 |
| 2022 | 123,091,117 | 1.00 | 167,521 | 31,175 |
| 2023 | 201,141,005 | 1.64 | 218,547 | 51,979 |
| 2024 | 282,188,959 | 2.29 | 237,687 | 73,010 |
| 2025 | 361,444,721 | 2.93 | 233,072 | 93,642 |
| 2026 | 320,525,256 | 2.59 | 163,702 | 83,636 |
| **total** | **1,341,660,210** | **10.89** | | |

Before the run, gating was projected at **9.78 GB** against 121.1 GB ungated
(agent A's measurement); the measured total above replaces that projection.

D18 timestamps carry modelled device clock error, which is deliberately not
corrected, so they run past the end of the simulated span. For that reason D18
is excluded from each year's `n_days` evidence in `export_report.json`.

## 4. D11 presence covers 14 days of each year, not the whole year

`collect_presence_days = seg["sim_day_offset"] + 14`, so presence is kept for
the first **14** days of each segment and discarded after that. Each year's
`export_report.json` `run_t0_evidence` shows it:

| year | D11 first | D11 last | D13/D16/D19 last |
|---|---|---|---|
| 2015 | 2015-01-01T00:00 | **2015-01-14T23:59** | 2015-12-31T23:45/59 |
| 2016 | 2016-01-01T00:00 | **2016-01-14T23:59** | 2016-12-31T23:45/59 |
| 2017 | 2017-01-01T00:00 | **2017-01-14T23:59** | 2017-12-31T23:45/59 |
| 2018 | 2018-01-01T00:00 | **2018-01-14T23:59** | 2018-12-31T23:45/59 |
| 2019–2026 | each `YYYY-01-01T00:00` | **each `YYYY-01-14T23:59`** | each year's last day (2026: 2026-09-30) |

D11 rows per year: 2015 1,149,976, 2016 1,149,370, 2017
1,128,179, 2018 1,150,803, 2019 1,149,150, 2020
1,150,076, 2021 1,149,126, 2022 1,126,771, 2023
1,127,903, 2024 1,149,836, 2025 1,149,466, 2026
1,150,880.

**Consequence for D29 and D30.** Both read D11 for `location_kind ==
"building"`. They are present and non-empty (D29 2,184 rows and D30 1,092 rows
in each year so far), but they describe **14 days**, not a year. Before the
D-141 restart of the Mac run, the 14-day window was tested against the global
`sim_day`, which would have collected presence on no day of any year. The fix is
in the frozen engine; it did not widen the window.

## 5. Engine homogeneity — *resolved in the EC2 run*

The Mac run produced 2015 on freeze-2.2 and later years on 2.3. The EC2 run
re-ran everything from the warm-up on freeze-2.3: every `DONE.json` records code
digest `05328f32a44b8c94…` and config digest `e0ab1c8351e1e153…`, and every
segment, 2015 included, has an `ENGINE.json`. The 2015 export catch-up
(`export_catchup.py`) was not needed: D04 and D24 are produced by the normal
post-pass every year. Both digests match in all 13 `DONE.json` files and every
`ENGINE.json` records `v1-engine-freeze-2.3` (re-checked by
`ops/release_fill.py` at release).

## 6. D23's recorded engine identity (I-115)

On the Mac, 2015's D23 recorded a reconstructed identity (`code_git_sha =
fdef627…-reconstructed`), which is not an engine any year ran on. I-115 is
fixed in freeze-2.3 **in the D23 part manifest only**. Read for all twelve EC2
years:

| where | field | value in every year |
|---|---|---|
| D23 manifest | `d23_freeze_tag` | `v1-engine-freeze-2.3` |
| D23 manifest | `d23_engine_code_digest` / `d23_engine_conf_digest` | `05328f32a44b8c94…` / `e0ab1c8351e1e153…` (correct) |
| D23 manifest | `d23_engine_version_source` | `recorded by the run (ENGINE.json)` |
| D23 row | `code_version` | `0.1.0a1+e1-reconstructed` |
| D23 row | `code_git_sha` | `fdef6279bc44…-reconstructed` (the original `v1-engine-freeze` tag) |
| D23 row | `code_tree_hash` | `3e647f94…-reconstructed-at-fdef627` |

The row's fields are reconstructed from git and suffixed as such, so they cannot
be mistaken for a recorded value, but they name the first freeze, not 2.3. Its
`parameters.captured_run_parameters.network_claim` also repeats the stale E1
text (§14). Read the engine identity from the manifest, not the row.

Whatever D23 says, the **provenance of record is `_segment/DONE.json` and
`_segment/ENGINE.json` for each year, plus `RUN_DIGESTS.json`**. D23 is built
inside the export and is not independent of what it describes.

## 7. D24's calibration targets are substituted outside 2016–2023

`build_d24`'s CSO targets cover **2016–2023** only, so 2015, 2024, 2025 and 2026
receive substituted targets. Each year's D24 records the substitution as such
rather than presenting it as a measured target.

D24 declares no assumption field and the schema defines none, so the provenance
validator reports one failing cross-check rather than a weakened one (P-1,
D-145). D04 and D24 are both `schema_conformance: partial` in every year's
manifest: required fields the model holds no value for are null by declaration
and listed in `null_required_fields`.

## 8. D15 `is_dst` — fixed in the frozen code; measured correct in every EC2 year

I-111 (D15 `is_dst` inverted because `tzdata` gives Europe/Dublin a negative
winter DST offset) is fixed in the frozen engine: `weather/site.py:241` decides
by the UTC offset (`+1 h` is summer). On the Mac, the shipped 2015 D15 read
January mean 0.0 and July mean 1.0 over 525,600 rows, which is correct. That
was a different package. On EC2, `verify_segment.py` measured it in every
year: mean `is_dst` **0.00 in January and 1.00 in July in all twelve years**
(each year's `_segment/verify_segment.log`). `is_dst` has no consumer in the engine, so it affects the published
flag, not the watts.

## 9. Memory: the 18 GB gate covers the simulation, not U27 (I-113, EC2-1)

The RSS gate (`rss_gate_mb: 18432`, `rss_warn_mb: 8192`) is checked at the
30-day flush points, not continuously, so a spike between two flushes is not
seen. On Linux the in-run check never trips at all: the supervisor reads current
RSS in macOS units, 1000 times too low, so the gate acts only in the end-of-year
check, on the engine's correct `peak_rss_mb`. With one subprocess per year
(D-148), the simulation phase peaked at 9.4–9.8 GB to 2020 and then grew with
D18 1-minute coverage: 13.2 GB in 2021, 18.3 GB in 2022, 23.7 GB in 2023. From
2023 the gate is exceeded and accepted as an operational exception (§16). Per
year: 2015 9,465.1 MB; 2016 9,467.5 MB; 2017 9,446.4 MB; 2018 9,405.5 MB; 2019 9,441.2 MB; 2020 9,809.3 MB; 2021 13,176.8 MB; 2022 18,331.3 MB; 2023 23,716.1 MB; 2024 28,996.8 MB; 2025 34,258.6 MB; 2026 38,102.9 MB.

**The gate does not cover the U27 plausibility suite**, which runs after the
last day and loads the whole year of D13/D16/D18/D19 into memory
(`plausibility/suite.py::_package`). On the instance it held 49.7–53.2 GB
resident in every year (the `MemoryHigh=52G` limit), with the rest in swap.
The first 2015 attempt was OOM-killed there at 63 GB (§12). The run completes
only because the host has swap (96 GB, raised to 200 GB on 2026-10-18 after
2023's U27 used 94.2 GB of it) and the service has `MemoryHigh=52G`; without
swap it did not complete on this 61 GiB host. The
`peak_rss_mb` in each `DONE.json` comes from the benchmark, written before U27,
so it does not show this peak. Logged as EC2-1 in `docs/V2_PLAN.md`, with the
v2 fixes: read only the columns each check uses, compute U27 part by part, and
extend the memory gate to the post-run phases. From 2019, D18 adds to what U27
loads, so the swap it needs grows each year:

| year(s) | U27 resident peak (watch.log, 10-min samples) | swap peak |
|---|---|---|
| 2015–2020 | 49.7–53.0 GB | ≤ 69 % of 96 GB (10-min samples) |
| 2021–2023 | 52.4–53.2 GB | 94.2 GB of 96 GB (systemd, the run of 17–18 Oct) |
| 2024 | 53.1 GB | 128.7 GB (systemd) |
| 2025 | 53.0 GB | **158.8 GB** (systemd) |
| 2026 | 53.1 GB | 126.0 GB (systemd; 273 days) |

From 2024 the run needed the 200 GB of swap added on 2026-10-18; 2025 would not
have completed with the original 96 GB.

## 10. Two `DONE.json` fields are stale constants

`"provisional": true` is a constant in every `DONE.json`. `"b2_upload":
"SKIPPED - no credential, rotation unconfirmed (D-125)"` is a constant in the
years the frozen supervisor finished (2015–2019, 2021, 2022); the years the ops
layer finished (2020, 2023–2026) say `"handled by
~/hrsd_occupants/ops/post_year.sh"` instead. Both are written as constants
(`replay_supervisor.py:564-565`, `ops/finish_segment.py`) and say nothing about
the upload itself. **Every year was uploaded** to `b2eig:hrsd-occupants/v1/<year>/` and
checked with `rclone check` showing 0 differences, by the ops layer outside the
frozen tree (`~/hrsd_occupants/ops/post_year.sh`). The evidence is the year's
`_segment/` directory on B2 and the release notes' per-year table. (The Mac-run
limitation "B2 upload is skipped" is resolved.)

## 11. Test suite on the instance: 17 failures, all explained

`pytest` on the instance: **1,199 passed, 17 failed, 44 skipped**.

| failures | cause | affects results? |
|---|---|---|
| 1 | `test_sleep_timing.py::test_a_non_worker_wakes_later…` (I-101); fails on the freeze-1 tree too, with identical numbers | no, pre-existing |
| 12 | `test_export_dataset_schemas.py`, schema and access-class tests on the town 14-day package (D10, D11, D13, D16, D18, D19), which need `work/town4`, a Mac-only artefact excluded from the transfer | no, missing fixture |
| 3 | `test_gen_provenance.py`: the committed `PROVENANCE.md` is stale against the freeze (it still lists D04/D24 as not written and D18 as omitted) | no; `PROVENANCE.md` is regenerated for the release |
| 1 | `test_datasets_catalogue.py::test_the_document_on_disk_is_what_the_generator_produces`: `DATASETS.md` differs from its generator's output | no, cosmetic |

## 12. Resume is segment-granular; a failed year re-runs from day 1

There is no mid-segment resume. The supervisor restores from the **previous**
segment's final checkpoint (D-135); the per-day checkpoints exist for chain
verification, not restart. `run_year` holds whole-year state in memory and only
writes it at the end (annual energy for D24, sleep statistics, energy closure,
`benchmark.n_days`), so resuming mid-year cannot reproduce the package an
uninterrupted year writes.

Cost on the instance: 2015's first attempt finished all 365 days and was
OOM-killed in U27 (§9). It was renamed aside as `2015.partial.1792163952`
(kept, D-135) and the year re-ran from day 1, which cost about 4.3 h.
Every year's published package is its first simulation except 2015, which was simulated twice. 2020, 2023, 2024, 2025, 2026 each also have an in-process retry that was stopped within minutes and kept as `<year>.superseded.<ts>`; the finished first simulation is the one published.

2020 and 2023–2026 each show two attempts: the finished simulation, and an
in-process retry the supervisor started after its year check failed (PL-TEMP-01
or the memory gate, §15–16). Each retry was stopped within minutes and kept as
`<year>.superseded.<ts>`; no year after 2015 was re-simulated.

Since then, the ops layer re-runs only the post-pass when a year's simulation
has finished and only its post-pass failed (`ops/finish_segment.py`, tested to
give byte-identical Parquet output). A crash mid-simulation still re-runs the
year. v2 adds flush-point resume (`docs/V2_PLAN.md`).

## 13. Run rate is a property of the host

On the instance (r7a.2xlarge, 8 vCPU, threads pinned to 1), the in-loop
benchmark's simulation time stayed at **18.5–19.0 s per day** in every year,
while writing grew with D18 from **16.0 s (2015–2019) to 21.6 s (2026)**.
`DONE.json` gives 42.4–42.5 s/day for 2015–2019, 45.0 (2021) and 51.5 (2022);
the 30-day flushes, network solve and the year's end account for the rest. For
2020 and 2023–2026 `DONE.json`'s figure (40.9–45.7 s/day) is measured
differently, from the checkpoint span (release notes, *Per year*). The instance is shared
with another project; its daytime load had no measurable effect.

The Mac run's figures (107.9 s/day for 2015, a median of 135 s/day under
concurrent tree walks, D-151) describe that host, not the engine.

## 14. `network_claim` in `run_diagnostics.json` is stale text

Every `run_diagnostics.json` records `coupling_mode: "C2"`, and the run solves
the LV power flow each epoch (`solve_network: true`; about 2,000 s of network
solve per year in `benchmark.timings`). Its `network_claim` field, however, is
the E1 constant `engine/run.py::NETWORK_CLAIM`: "E1 runs coupling mode C1 … it
does NOT solve a power flow … No voltage, loading, curtailment or
network-constraint claim is made from E1 output". **`coupling_mode` is the
accurate field.** The text was not updated when C2 was added (DECISIONS: C2
turns on with `solve_network`), and it cannot change under the freeze.

**v1 policy: E1's wording stands.** D17 and D17_aggregate do contain the C2
power-flow solution (active and reactive power, `voltage_pu`, `loading_pct`
and outages for 64 feeders and 53 transformers every 15 minutes), published as
engineering output. It has not been compared with measured network data, so no
voltage, loading, curtailment or network-constraint claim is made from v1
either.

## 15. Indoor peak above the assumed 40 °C ceiling, accepted from 2020 (PL-TEMP-01, EC2-2)

U27 check PL-TEMP-01 tests the living-zone temperature distribution against a
**declared band `[A]`**: annual median 15–23 °C, at most 5 % of epochs above
28 °C, peak at most 40 °C. Its `tolerance_basis` is "declared, not sourced". No
CSO or SEAI table publishes measured Irish indoor temperatures, so **the 40 °C
ceiling is an assumption with no published source**. Its stated job is to refuse
the implausible (the fault it was written for had a median of 24.6 °C, 19 %
above 30 °C and a peak of 64.3 °C), not to calibrate.

| year | peak °C | median °C | share > 28 °C | outcome |
|---|---|---|---|---|
| 2015 | 39.82 | 18.80 | 0.02 % | pass |
| 2016 | 39.33 | 18.97 | 0.02 % | pass |
| 2017 | 39.86 | 18.94 | 0.02 % | pass |
| 2018 | 37.19 | 19.01 | 0.13 % | pass |
| 2019 | 38.71 | 19.00 | 0.03 % | pass |
| 2020 | **41.15** | 18.96 | 0.03 % | **FAIL, accepted** |
| 2021 | 38.72 | 18.99 | 0.19 % | pass |
| 2022 | 38.51 | 19.2 | 0.15 % | pass |
| 2023 | 37.77 | 19.21 | 0.04 % | pass |
| 2024 | 41.38 | 19.04 | 0.03 % | **FAIL, accepted** |
| 2025 | 43.3 | 19.27 | 0.08 % | **FAIL, accepted** |
| 2026 | 39.16 | 19.59 | 0.39 % | pass |

2020's peak broke the ceiling while its median and tail stayed in line with
2015–2019. The peak is a maximum, so a single epoch above 40 °C anywhere in
the town fails the check, out of 38.4 million epochs in 2020. Which dwelling and room drives it, and why (solar gain,
an emitter left on, a small zone), is **not known**: the metadata does not say,
and finding out means reading D16.

**What v1 does.** From 2020 the ops layer (`ops/finish_segment.py`, approved
2026-10-17) accepts a PL-TEMP-01 failure only while the peak is ≤ 45 °C, the
median is within 17.80–20.01 °C (the 2015–2019 range ± 1 °C) and the share above
28 °C is ≤ 0.5 %. Outside any of those bounds, or with any other check failing,
the year still blocks. Each acceptance is recorded in that year's `DONE.json`
(`u27_accepted_exceedances`). The package's `evidence/plausibility.json` keeps
the FAIL as U27 wrote it; nothing in the package is altered. The engine's own
`KNOWN_PLAUSIBILITY_FAILURES` register is unchanged (frozen), so `run_year`
still raises on it, and such a year is completed by `finish_segment.py` after
the watchdog restores the finished attempt (§12).

**How to read it.** Treat the upper tail of D16 living-zone temperatures from
2020 on as unverified until the driver is found. Annual medians and the share
above 28 °C are unaffected by the exception.

## 16. Peak-RSS gate exceeded from 2023, accepted as an operational exception (EC2-3)

**What happened.** 2023's simulation peaked at **23,716 MB** RSS against the
18,432 MB gate (`rss_gate_mb`, frozen configuration), and the supervisor's year
check failed on that alone; U27 passed and every other check passed. Peak RSS
tracks the home-days recording D18 at 1-minute resolution: about 9.8 GB plus
0.27 MB per such home-day (2021: 10,372 home-days, 13.2 GB; 2022: 31,175,
18.3 GB; 2023: 51,979, 23.7 GB). The gate is a fixed figure set for the Mac's
32 GB, so it does not allow for that growth, and every later year exceeded it:
29.0 GB in 2024, 34.3 GB in 2025 and 38.1 GB in the nine months of 2026, all
within the 40 GB accepted.

**What v1 does.** Approved 2026-10-18 (Brian O'Regan) as a v1 operational
exception with no output impact: for 2023–2026, `ops/finish_segment.py` accepts
the gate failure only while the peak is ≤ 40 GB (40,960 MB) and it is the only
failure in the year check. Each acceptance is recorded in that year's
`DONE.json` (`rss_gate_exception`). The engine and configuration are unchanged.
As with §15, the supervisor still fails such a year in-process, and it is
completed by `finish_segment.py` after the watchdog restores the finished
attempt (§12).

| year | peak RSS, MB | accepted up to, MB |
|---|---|---|
| 2023 | 23,716.1 | 40,960 |
| 2024 | 28,996.8 | 40,960 |
| 2025 | 34,258.6 | 40,960 |
| 2026 | 38,102.9 | 40,960 |

**How to read it.** The gate is a resource guard, not a result check. No
published file depends on it. It means v1 needs a host with more than 18 GB for
2023 onward, and about 40 GB plus swap for U27 (§9).

## 17. D16 is written every 15 minutes, not at the declared 1 minute

`datasets.yaml` declares D16's grain as "1 min, checkpointed daily". The frozen
engine writes it at the 15-minute network epoch instead (`D16_EPOCH_MINUTES = 15`
in `engine/stream_writer.py`): **96 rows per building-day**, `ts` on :00, :15,
:30 and :45. The reason given in the code is that the thermal time constants
are 15 to 140 hours, so a 15-minute sample loses none of the dynamics; the
solver itself still steps at 1 minute, as do the device and observation layers
(D18). Use D18 or D13 for sub-15-minute behaviour. D16 `rh_living_pct` is a
constant (no moisture balance) and `ach_effective` includes the solver's purge
ventilation, not occupant window opening; both are stated in every D16 part
manifest's `unmodelled_fields`.

## 18. 2026 is a nine-month year, and its annual U27 checks are `NO_DATA`

2026 runs from 1 January to **30 September** (273 days). Five U27 checks compare
annual quantities that need at least 350 days, and U27 refuses to extrapolate a
partial year (the verdict would depend on the season covered), so in 2026 they
return `NO_DATA`: PL-DHW-01 (hot water), PL-ELEC-01 (annual electricity),
PL-GAS-01 (annual gas), PL-MIX-01 (fuel mix) and PL-PEAK-01 (load factor
against LP1). 2026's U27 is therefore **5 pass, 2 not evaluable, 5 `NO_DATA`**,
against 10 pass and 2 not evaluable in a full year. Annual figures in 2026's
`run_diagnostics.json` are nine-month sums under annual names: for example
`annual_electricity.summary.mean_simulated_kwh_yr` is 3,440.5 kWh in 2026
against 4,806.0 in 2025. Do not compare 2026's "annual" values with full years
without scaling them.

## 19. D14 `attendance_prob` has a different struct in 2022

D14's `attendance_prob` is `struct<adult: double, child: double, visitors:
double>` in eleven years and `struct<all: double, child: double, adult: double,
visitors: double>` in **2022**: an extra `all` field and a different field
order. Readers that concatenate years by position, or that require one schema
across years, must handle 2022 separately or select fields by name. Every other
dataset's Parquet schema is identical in every year it appears (checked from
the footers of all twelve years).

---

## Carried to v2

Every item above, plus: P-7(b) T0 = 2015 with estate gating and Census 2022
held-out validation; D03/D09/D20 at run level; D12 trips; flush-point resume;
U27 memory (EC2-1); engine profiling; MIMIC D25/D26 post-pass;
`DONE.json` recording the real upload state; `network_claim` from the run's
coupling mode; the >40 °C indoor peak's driver and a sourced ceiling
for PL-TEMP-01 (EC2-2); a year-aware memory gate and D18 1-minute
memory growth (EC2-3); D23's row recording the engine identity it already has in
its manifest; one D14 `attendance_prob` struct; and a schema grain for D16 that
says what is written. See `docs/V2_PLAN.md`.
