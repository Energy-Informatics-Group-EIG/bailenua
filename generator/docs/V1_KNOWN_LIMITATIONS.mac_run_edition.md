# v1 — known limitations

**Status: v1 scope is FROZEN as of 2026-10-15 16:45.** Engine `v1-engine-freeze-2.3`.
No further boundary merges, branch deploys or engine changes until the run
finishes. Every item below is accepted for v1 and carried to v2
(`docs/V2_PLAN.md`); none is a defect to be fixed in place.

Every claim here was measured against the shipped 2015 package or read from the
running configuration. Where a figure contradicts an earlier status note, the
measurement is given and the note is marked superseded.

---

## 1. The population does not vary with the simulated year (P-7, accepted for v1 only)

`synthesise_t0` takes no year and no as-of date; `T0` is pinned at 2022-01-01.
Every segment logs the same **1092 homes, 2917 people**.

So each year's output contains every dwelling that exists in the 2022 census
stock, including estates completed later than the simulated year — **Cluain Ard
(completed 2019)** appears in 2015 drawing load four years before it was built,
and **Belgard (completed 2024)** nine years before. The same holds for every
year before each estate completes.

**What is still correct for its year:** weather, calendar, behaviour, physics,
tariffs and every sourced input. The limitation is confined to *which dwellings
exist when*.

**How to read v1:** a twelve-year behavioural and physical replay on a **fixed
2022 town**, not a study of dwelling-stock growth. The map's year slider reads
`valid_from`/`valid_to` from D01/D02 and will therefore disagree with the data
for any year before an estate completes. Logged as I-119.

Accepted **for v1 only**. v2 moves T0 to 2015 with estate gating; see
`docs/V2_PLAN.md` §1.

## 2. Six datasets are absent from every year

Each absence is recorded in the per-segment `export_report.json` with its own
reason, so the package states what it does not contain rather than omitting it
silently. `export_failed: 0` is correct: these are absences, not failures.

| dataset | why absent |
|---|---|
| **D03** building passport | converted from `pkg/evidence/wp5_tenyear.json`, which only a run that steps the ten-year life course produces. The replay steps none and `replay_supervisor.py` never passes `passport_schedule` to `run_year`, so no passport event is ever created. |
| **D09** life events | same artefact, same cause. |
| **D20** change labels | same artefact, same cause. |
| **D12** trips | no trip row survives the day. `activity.engine` computes travel only for EV state of charge; `DayResult` has no `trips` field and `StreamWriter` has no D12 buffer. |
| **D25** MIMIC participant panel | owned by the MIMIC exporter, not by this package. |
| **D26** MIMIC answer key | owned by the MIMIC exporter, not by this package. |

**D03/D09/D20 could not have been back-filled into v1.** The only
`wp5_tenyear.json` on disk (six byte-identical copies, 404,982 B, in the agent
worktrees' `v1/evidence/`) describes `span 2022-2031`, `year_index 0 = 2022`,
slice `u23_mixed_age, 60 homes`. Two independent guards correctly reject it:
`from_evidence._epoch` requires the artefact's day 0 to equal the package's
`t0` (2022-01-01 against 2015-01-01 — a seven-year error that would silently
displace every event), and a 60-home population beside 1,092 homes would
recreate **I-091**, where D03/D09/D20 shared no person with D05/D06/D08 and
every D21 biography's life-event section read "no record covers this date".

The export side is plumbed correctly and is not the gap: the supervisor creates
`<pkg>/evidence/` and proves it writable, and passes `relocate={}` so these
three would land in the segment's own package. Only the input is missing.

This is the **same root cause as §1** — the life-course machinery is built on a
2022 origin (`span 2022-2031`). One gap, three symptoms: the fixed population,
the three absent datasets, and the early estates.

## 3. D18 appears only from 2019, and is era-gated

D18 is streamed by the engine, not by the export package. `d18_era_gating` is
**true** in the live configuration, so D18 is written only for the years in
which its device era exists — first appearing in late 2019. 2015-2018 carry no
D18 rows, by design, not by failure.

Gating measured **9.78 GB** against **121.1 GB** ungated. The gated figure is
still a projection from agent A's measurement; the first real number arrives
when 2019 completes.

D23 also records why D18 is excluded from each year's `n_days` evidence:
"D18's device clock error is modelled rather than corrected, so its timestamps
run past the end of the simulated span."

## 4. D11 presence covers 14 days of each 365-day year, not the whole year

`collect_presence_days = seg["sim_day_offset"] + 14`, so presence is retained
for the first **14** days of each segment and discarded thereafter. Verified in
the shipped 2015 package through D23's own `n_days_evidence`:

| dataset | min | max |
|---|---|---|
| D11 | 2015-01-01T00:00 | **2015-01-14T23:59** |
| D13, D16, D19 | 2015-01-01T00:00 | 2015-12-31T23:45/59 |

2015 holds **1,149,976** D11 rows across those 14 days.

**Consequence for D29 and D30.** Both glob D11 for `location_kind == "building"`
and raise when there is none. They are present and non-empty (D29 2,184 rows,
D30 1,092 rows), but they describe **14 days**, not a year. Before the 14 Oct
23:55 restart the default of 14 was tested against the *global* `sim_day` and
every segment starts at offset ≥ 31, so presence would have been collected on
**no day of any year** and D29/D30 would have failed in all twelve (D-141).
The restart fixed that; it did not widen the window.

## 5. 2015 ran on a different engine from 2016-2026

| segment | engine | code digest |
|---|---|---|
| warmup_2014 (discarded) | freeze-2.2 | `7f4a65594ec78de8…` |
| **2015** | **freeze-2.2** | **`7f4a65594ec78de8…`** |
| 2016 … 2026 | freeze-2.3 | `05328f32a44b8c94…` |

The 11:25 restart moved the run from freeze-2.2 to freeze-2.3 at the 2015/2016
boundary. v1 is therefore **not homogeneous in engine version**: year one was
produced by a different engine from years two through twelve. The differences
carried by 2.3 are A's D18 era gating (no effect before 2019), agent D's D04
and D24 exporters, and the I-115/I-116 supervisor changes.

2015 was brought level on the export side afterwards by
`scripts/export_catchup.py` (see `2015/export_catchup_log.json` and
`export_report_catchup_20261015-112812.json`), which added **D04** and **D24**.
Engine-streamed datasets were not and cannot be re-derived without re-running
the year.

**`ENGINE.json` does not exist for 2015.** The per-segment engine record was
added with the 2.3 restart and is written after a segment's `run_segment`
returns, so 2016-2026 will each carry one and 2015 will not.

## 6. D23's recorded engine identity is wrong (I-115)

Read from the shipped 2015 `D23_part000.parquet`:

```
label          = UNVALIDATED SIMULATION EVIDENCE: E1 engineering candidate
code_version   = 0.1.0a1+e1-reconstructed
code_git_sha   = fdef6279bc44aac507503bf96972c5fd80ed0420-reconstructed
code_tree_hash = 3e647f947ca6fa74c91fd40db5e8530e417d2a2d78145010b7a363fcb5d639f9-reconstructed-at-fdef627
```

D23 does **not** record freeze-2.2 or digest `7f4a65594ec78de8…`, which is what
2015 actually ran on. The sha it does record, `fdef627`, is the `agent-d`
worktree's HEAD — not an engine any year was run on.

So **D23 cannot be used as the provenance of record for v1.** The authoritative
per-year engine identity is each segment's `DONE.json` (`code_digest`,
`conf_digest`) plus `RUN_DIGESTS.json` at the run root, and `ENGINE.json` for
2016 onward. The v1 release notes must say this explicitly.

D23 also records `run_root` through the legacy symlink path
(`/Users/brianoregan/Desktop/HRSD_Occupants/work/…`) rather than `~/hrsd`.
Cosmetic, but it is a path that depends on a symlink existing.

## 7. D24's calibration targets are substituted outside 2016-2023

`build_d24`'s CSO targets cover **2016-2023** only. 2015, 2024, 2025 and 2026
therefore receive substituted targets. The substitution is recorded as such in
each year's D24 rather than presented as a measured target.

D24 declares no assumption field and the schema defines none, so the provenance
validator reports one honest failing cross-check rather than a weakened one
(P-1, D-145). That finding stands in v1.

## 8. D15 `is_dst` — measured correct; the earlier note is superseded

The morning note recorded I-111 as "January mean 1.0, July mean 0.0 over
525,600 rows", i.e. inverted. Measured directly in the shipped 2015 package:

| month | mean(`is_dst`) | rows |
|---|---|---|
| January | **0.0** | 44,640 |
| July | **1.0** | 44,640 |

That is the correct polarity for Ireland. **2015's shipped D15 is not
inverted.** The `fix-i111-d15-dst` branch remains unmerged, so this records the
state of the *data*, not of the code; whatever route I-110/the export catchup
took, the published flags read correctly. `is_dst` has no consumer in the
engine, so it affects published flags and not watts (I-110/I-111).

## 9. The memory gate is evaluated every 30 simulated days (I-113)

The RSS gate (`rss_gate_mb: 18432`, `rss_warn_mb: 8192`) is checked at the
30-day flush points, not continuously. A spike between two flushes is not seen.
Documented and accepted; making it continuous means touching a running process.

Observed headroom: 2015 peaked at **15,402 MB**, 83.6% of the gate, and was
flat from day 210 to the end of the year. Growth is **step-wise, not linear** —
`+4,372`, `0`, `+283`, `+1,463`, `+1,718`, then zero for 186 days. Three
successive linear forecasts of a trip were wrong in both directions (P-5); no
forecast is offered here.

## 10. B2 upload is skipped; every package is local (D-125)

Per-year upload with verification is specified but no credential exists and key
rotation is unconfirmed. **No upload has been attempted.** All twelve packages
are local only. Carried to v2.

## 11. One suite failure is pre-existing (I-101)

`test_sleep_timing.py::test_a_non_worker_wakes_later…` fails on the freeze-1
tree as well, so it is not introduced by v1: 1 failed, 1070 passed, 35 skipped.
`verify_chain()` returns `None` and raises on failure — no exception is the
pass.

## 12. Resume is segment-granular; a restart re-runs the whole year

There is no mid-segment resume. Every path in `replay_supervisor.py` restores
from the **previous** segment's final checkpoint (`:477`, `:586`); the per-day
checkpoints exist for chain verification, not restart. A reboot or crash mid-2016
re-runs 2016 from day 1.

Cost observed: the 15:30 reboot caught 2016 at sim_day 443 (segment day 47) and
cost all 47 days. The incomplete attempt is renamed aside, never deleted
(`:296-300`, D-135) — `2016.partial.1792074940` holds it.

Flushes fire on the **global** `sim_day % 30 == 29` (`e1_run.py:1077`), so
2016's flush points are 419, 449, 479 … A flush-point resume would have
recovered to 419 and saved 24 of those 47 days. Not built for v1; see
`docs/V2_PLAN.md` §5.

## 13. Measuring the live tree costs the run real progress (D-151)

A full-tree walk while the replay runs is not free. Two `gen_structure.py` runs
(`os.walk` over 60,672 paths) plus repeated `du -sh` over 21 GB produced a
single **3,535-second** per-day gap and cost about an hour; `fseventsd` held
100% of a core throughout. `.metadata_never_index` now sits at the tree root.

Per-year sizes must be summed from the part sidecar manifests and `DONE.json`
`row_counts`, never from the filesystem. Full-tree walks belong at a boundary.

This also means **published per-day rate figures must say what else touched the
machine**. 2015 ran at **107.9 s/day** (its `DONE.json`). 2016 under daytime
load and concurrent tree walks ran at a median of **135 s/day**, with 87 s/day
seen on an untouched tree. The rate is a property of the host, not the engine.

## 14. Indoor peak above the assumed 40 °C ceiling, accepted from 2020 (PL-TEMP-01)

*Added 2026-10-17 on the EC2 instance.* 2020's U27 check PL-TEMP-01 failed: the
peak living-zone temperature was **41.15 °C** against a ceiling of 40 °C, which
is a declared assumption `[A]` with **no published source**. The median
(18.96 °C) and the share above 28 °C (0.03 %) were in line with 2015–2019 (peaks
37.19–39.86 °C). Accepted by Brian on 2026-10-17 through an ops-only override
(`~/hrsd_occupants/ops/finish_segment.py`) for 2020 and later years, only while
the peak is ≤ 45 °C, the median is within 17.80–20.01 °C and the share above
28 °C is ≤ 0.5 %; otherwise the year still blocks. Each acceptance is recorded in
that year's `DONE.json` (`u27_accepted_exceedances`). Engine and configuration
unchanged. The driver of the peak is not yet known (`docs/V2_PLAN.md` EC2-2).
The EC2 release edition (`V1_KNOWN_LIMITATIONS.draft.md` §15) carries the full
text.

## 15. Peak-RSS gate exceeded from 2023, accepted as an operational exception

*Added 2026-10-18 on the EC2 instance.* 2023's simulation peaked at **23,716 MB**
RSS against the 18,432 MB gate (`rss_gate_mb`), which grows with D18 1-minute
coverage (2022: 18.3 GB; 2023: 23.7 GB); U27 and all other checks passed.
Approved by Brian on 2026-10-18 as a v1 operational exception with no output
impact: for 2023–2026 the ops layer accepts a gate failure only while the peak
is ≤ 40 GB and it is the only failure, and records it in that year's
`DONE.json` (`rss_gate_exception`). Engine and configuration unchanged.
Making the gate year-aware is `docs/V2_PLAN.md` EC2-3. Full text:
`V1_KNOWN_LIMITATIONS.draft.md` §16.

---

## Carried to v2

Every item above, plus: P-7(b) T0 = 2015 with estate gating and Census 2022
held-out validation; D03/D09/D20 at run level; D12 trips; flush-point resume;
engine profiling to ≤80 s/day; MIMIC D25/D26 post-pass; B2 upload. See
`docs/V2_PLAN.md`.
