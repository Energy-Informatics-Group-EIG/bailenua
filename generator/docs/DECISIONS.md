# Baile Nua / HRSD_Occupants — DECISION LOG

**UNVALIDATED SIMULATION EVIDENCE: E1 engineering candidate**

Decisions taken during implementation. Architectural decisions are frozen at design
revision 3 (8 October 2026) and are **not** reopened here; this log records E0
decisions as given, and implementation clarifications made under them (design §13:
"implementation clarifications are recorded without reopening it").

## Part A — E0 decisions, as approved by Brian O'Regan, 8 October 2026

Taken as binding inputs. Not re-litigated.

| # | Item | Decision as approved | Where it binds the code |
| --- | --- | --- | --- |
| E0-1 | U03 scale-down | Build **both** methods (whole small areas, stratified; and proportional scaling), compare joint **and** spatial error, recommend one in the E1 report | `population/scale_down.py`, both methods implemented; `population/joint_metrics.py` scores them; recommendation in the E1 gate report |
| E0-2 | U04 time-use source | No Irish microdata. Use public aggregates (Eurostat HETUS) with Irish recalibration where possible. Activity engine flagged **VERIFIED, NOT CALIBRATED** | `activity/` modules carry the flag; every report line states it |
| E0-3 | U08 calendar | Simulated calendar 2022–2031, Census 2022 as t0. **E1 slice simulates 2022** | `engine/calendar.py` t0 = 2022-01-01; E1 run is calendar year 2022 |
| E0-4 | U11 thresholds | §7 margins are **provisional** | Thresholds live in one place (`config/thresholds.yaml`) and are labelled provisional in output |
| E0-5 | U16 MIMIC pools | Two pools; the 10,000 target is **unique participants**; keep the five separate counters (§5.14) | `mimic/counters.py` holds exactly five counters and refuses to sum them |
| E0-6 | U21 hardware | Run on this Mac. Benchmark on Day 6, report whether the full town fits | `bench/` measures on this machine; see I-005 for the gap to the U21 minimum |
| E0-7 | E1 scope | 50 homes, ~140 people, one full year (2022), C1 coupling, ≥1 life event and ≥1 disruption, plus a MIMIC export of ≥10,000 unique participants | `config/e1_scope.yaml` is the single definition; the runner refuses to exceed it |
| E0-8 | R09 interpretation | No occupancy field is ever transmitted; inference risk is measured later (§7.8) | `edge/export.py` has a field allow-list; the leakage test fails CI on any breach. No §7.8 inference test is run or claimed at E1 |

## Part B — Implementation decisions taken in this run

| ID | Date | Decision | Reason | Reversible? |
| --- | --- | --- | --- | --- |
| D-001 | 2026-10-08 | The binding design document is the revision-3 file found at the project root, copied to `docs/Baile_Nua_Technical_Design_Review_r3.md`; originals preserved byte-identical under `docs/source_pdf/` | The brief named a path that did not exist; the file present is revision 3 with the architecture frozen, which is what the brief describes | Yes |
| D-001a | 2026-10-10 | **Amended: the single design reference is now `docs/Baile_Nua_Technical_Design_Review_r4.md`.** r4 was found at the project root (139,468 bytes, modified 10 Oct 01:13) and moved into `docs/`. Verified before adopting: section 9.6 "Progress against gates" present, U01 to **U31** declared in the section 11 table, and Appendix A "HRSD\_Occupants Log" present at line 1171. r3 is retained unmodified as the frozen revision it is | r4's architecture is frozen at revision 3 and unchanged, so adopting it changes no architecture — it adds 6.4, 6.5, 7.9, 9.6, U22 to U31 and Appendix A, which is exactly the content Part C and I-035 were standing in for. Four earlier checks found r4 absent (I-038); it was saved after the fourth | Yes |
| D-002 | 2026-10-08 | `<MIMIC_PATH>` resolved to `/Users/brianoregan/Documents/GitHub/mimic` | Unsubstituted placeholder in the brief. Confirmed by `web/mimic/mimic_sd_generator.php`, `database/schema.sql` at schema_version 1.1, and the three public API endpoints named in §5.14 | Yes |
| D-003 | 2026-10-08 | The local MIMIC instance runs from an isolated **copy** at `work/mimic_local/`, never from the MIMIC repo itself | I-001: the repo's `config/local.php` wins over env vars and points at production. Copying is the only way to get a local-only instance without editing MIMIC, which the brief forbids | Yes |
| D-004 | 2026-10-08 | Python 3.12 for the `baile_nua` venv | Design requires 3.11+. 3.12 has wheels for numba, pyarrow and duckdb on x86_64 macOS; 3.14 (the default `python3` here) does not yet for numba | Yes |
| D-005 | 2026-10-08 | One YAML file (`baile_nua/schema/datasets.yaml`) is the single source of truth for all datasets, and generates validators, the data dictionary and the access-class allow-lists | Design §8.5: "one YAML schema generating validators and docs" | No (architectural) |
| D-006 | 2026-10-08 | Access class is carried **in the schema**, not in code, and the leakage test is generated from it | §5.1/§6.3 GT/OBS/META separation must be mechanical, not a convention a developer can forget | No (architectural) |
| D-007 | 2026-10-08 | Observable IDs are HMAC-SHA256-derived opaque strings keyed by **premises**, with the key held only in the ground-truth crosswalk | §6.3 "IDs are opaque random strings, not sequential"; §6.4 item 2 "keyed by premises, not household" | No (architectural) |
| D-008 | 2026-10-08 | Philox-4x32-10 counter-based RNG, keyed `(master_seed, stream, entity_id, sim_day, draw_counter)`, implemented over `numpy.random.Philox` | §8.2 reproducibility contract. Counter-based so results do not depend on execution order or worker count | No (architectural) |
| D-009 | 2026-10-08 | The E1 slice does not store 1-minute building state (U07 option b); daily checkpoints plus deterministic re-run, with cached hot slices | U07 recommendation (b), reinforced by I-005: only ~89 GB of disk is free | Yes |
| D-010 | 2026-10-08 | The scale-down factor is the **midpoint of the feasible interval** derived from both of R03's acceptance ranges and Cobh's measured 2.6913 persons per household, recomputed each run (0.207110 → 2,930 people, 1,089 homes) — not `3000 / cobh_people` | I-012: the 3,000-person anchor gives 1,115 homes, outside R03's 1,000–1,100 range, and R04 forbids distorting the household-size mix to fix it. An empty interval raises rather than silently picking a side | Yes |
| D-011 | 2026-10-08 | "Area type" for U03 method (a)'s stratification is **electoral division × tenure tertile**, derived from the data | SAPS's own `UR_Category` is constant across all 53 Cobh small areas ("2. Satellite urban towns"), so stratifying on it would collapse method (a) to an unstratified sample and the U03 comparison would not test what it claims to | Yes |
| D-012 | 2026-10-08 | Joint and spatial fidelity are measured as **between-small-area** quantities (Spearman association across areas, Moran's I, dissimilarity index), and every report says so | SAPS publishes no individual-level cross-tabulation, so there is no joint distribution to compare against. Claiming individual-level joint validation would be unfalsifiable, which design 7 forbids | No (architectural) |
| D-013 | 2026-10-08 | Both U03 methods stay in the code and the method is a parameter; **no default is hard-wired** | E0-1 reserved the choice for the E1 report and U03 is a section-11 decision. I-013's measured recommendation (proportional) is put to Brian, not applied unilaterally | Yes |
| D-014 | 2026-10-09 | Shared appliances are triggered once per household **episode** — a maximal run of overlapping intervals of the same activity in the same zone — and only `electric_shower` stays per-person. `SHARED_WITHIN_EPISODE` and `PER_PERSON_APPLIANCES` must between them cover every appliance in `TRIGGERS`, enforced by a raise | I-027. Triggers fire per activity interval and the activity engine emits one interval per *person*, so a family of three sitting down to dinner boiled the kettle three times. Zone is part of the grouping because two people watching television together share one set and two watching in different rooms do not | No (architectural) |
| D-015 | 2026-10-09 | DBEREL01 (dwelling type × BER band) is declared with `model_development_exposure="tuning"` and DBEREL02 (dwelling type × period of construction) with `"none"`, and the D24 reader **raises** if DBEREL02's declaration ever changes | I-027 and design 7.1. The appliance trigger rates were fitted to DBEREL01, so it cannot also measure whether they generalise. DBEREL02 crosses the same dwellings on an axis the fitting never saw, and D02 already carries `year_built_band`. A held-out target that has quietly been used for tuning is worse than no held-out target, because it supports a claim that is not true | No (architectural) |
| D-016 | 2026-10-09 | An activity whose HETUS daily target is **below its own episode floor** is spent as an occurrence probability `p = target / drawn_episode_length` rather than as a daily budget | I-028. Such a target does not mean a few minutes every day — sport at 6 minutes a day is 20 minutes twice a week. Treating it as a daily budget gave a 2-minute daily sliver of sport before the episode floor and, after the floor, excluded the activity for ever, so no washing machine in the estate ever ran. The form is mean-preserving by construction | Yes |
| D-017 | 2026-10-09 | The checkpoint for day N records the state at the **start** of day N and is written before the day is run; D16 is written at the 15-minute C1 epoch rather than per minute | The checkpoint plus the exchange log are exactly the inputs day N consumes, which is what makes a one-day replay possible; written afterwards it would record end-of-day state and "replaying day N" would in fact run day N+1 from the wrong calendar day. For D16, the thermal time constants are 15 to 140 hours, so a 15-minute sample loses none of the dynamics, and 15 minutes is the epoch the rest of C1 already runs on — the 1-minute step is kept inside the solver and in the device and observation layers, where it matters | Yes |
| D-018 | 2026-10-09 | The E1 estate's seed small area is chosen as the one whose **own mean household size is closest to the town's**, among areas holding at least 60% of the estate, and is then filled from its nearest neighbours by OSi centroid distance; order *within* an area is a seeded permutation | E0-7 fixes both 50 homes and about 140 people, which is 2.8 per home against the town's 2.671, while Cobh's small areas genuinely range from about 2.0 to 3.4. Most contiguous blocks of 50 therefore miss 140 badly. This is a selection on the outcome and is declared as such: the alternative buys spatial tidiness at the cost of a slice that is not a miniature of the town, and E1 exists to exercise the engine on a miniature of the town. The permutation matters separately — `building_id` order is household-size descending, so "the first 40 of 44" silently takes the forty biggest households, which is what returned 176 people | Yes |
| D-019 | 2026-10-09 | The dataset manifest's content hash (`hash_frame`) is **row-order sensitive** and column-order independent, reversing the Day-1 choice; the old behaviour is kept as `hash_frame_row_order_independent` | I-030. The row-wise canonical-JSON hash cost 32.8 s of a 47 s writer — several times the simulation it was recording — and, more importantly, pointed the wrong way: a row-order independent hash calls two different byte streams "the same content", and design 9.2's criterion is *byte-identical* output. It could only ever hide a determinism failure. Every dataset is written in a deterministic order anyway, so there is no legitimate reordering for it to absorb | Yes |
| D-020 | 2026-10-09 | Room counts are allocated to dwellings by size rank (dwelling type and bedrooms) with jitter, preserving the SAPS room marginal exactly; `MIN_ROOMS_OVER_BEDROOMS = 0`, set by a feasibility test on the published marginals rather than assumed | I-031. Independence between marginals is the right default, but it emitted eight-room apartments and five-bedroom dwellings with three rooms — not "no correlation" but violations of a logical constraint. The margin itself had to come from the data: at margin 2 the published room and bedroom marginals are jointly infeasible for 14.8% of dwellings even under the optimal pairing, so the constraint, not the data, was wrong | Yes |
| D-021 | 2026-10-09 | The tuned/held-out source split is mirrored on both fuels: DBEREL01 and DBERNG01 (dwelling type × BER band) are `tuning`; DBEREL02 and DBERNG02 (dwelling type × construction period) are `none` and asserted to stay so | I-027 and I-031. 49 of the 50 estate homes heat with gas, so the electricity target cannot see their heating at all — which is how a 285 m² apartment survived five days of tests. Covering both fuels with the same split is what lets the report say whether the physics and device layers *generalise*, rather than only that they were fitted | No (architectural) |
| D-022 | 2026-10-09 | The flatness of measured gas consumption across BER bands is treated as a **finding to report**, not a target to fit. The physics keeps its fixed setpoint and schedule at E1 | DBERNG01 shows gas use varying only 4–7% across BER bands within a dwelling type, and A–B detached houses using *more* gas than F–G, while varying 84% across dwelling types. That is comfort-taking, a behavioural mechanism design 5.3 locates in COM-B and which E1 deliberately does not wire into the thermostat. Fitting the physics to reproduce a behavioural effect would hide the gap instead of measuring it, and would make the fabric parameters wrong for every other purpose | Yes |
| D-023 | 2026-10-09 | Solar gain is computed from the irradiance **incident on the glazing**, transposed onto vertical planes at the four cardinal orientations with an even glazing split; purge ventilation is closed-loop inside the solver, gated on outside being cooler and on no heat being delivered | I-032. `aperture × GHI` applied a horizontal-surface value to vertical windows and had the wrong sign in both seasons, and the F1 network had no heat-removal path at all, so the annual median living temperature was 24.6 °C against an Irish 17–19. The even orientation split is DEAP's own assumption for a dwelling of unknown orientation and the conservative one for overheating; real orientations are available from the OSi footprints in weeks 2–3 | Yes |
| D-024 | 2026-10-09 | Any series the solver uses is **carried on its result** and consumed by the writer, never recomputed downstream; the solver reports the air change rate it actually applied | I-032. The writer recomputed D16's `solar_gain_w` from the weather, so once the solver moved to the glazing plane the published energy balance would have described a different run from the one that happened. The same duplication was about to be repeated for the purge air change rate | No (architectural) |
| D-025 | 2026-10-09 | The room thermostat lives **inside** the solver, proportioning on the indoor temperature over a 1.5 K band; `_heating_schedule` supplies only emitter availability and the setpoint, and the solver reports the heat actually delivered | I-033. The controller proportioned on the OUTDOOR temperature and never looked at the room, so it overshot to 40 °C in nearly every month and could not let solar or internal gain displace any heating — 216 kWh against 52 on the same day. A thermostat has to see the room, and the room is what the solver computes, so the controller belongs there and nowhere else | No (architectural) |
| D-026 | 2026-10-09 | **Power analysis for the household-size marginal check, and the ensemble generator-bias check built on it.** Single-realisation deterministic resolution **12.82%** (34.3 households); the planted 10% shift (26.8 households) gives max \|z\| 2.1332 against a critical 2.7344 and is **below** it. On a genuine random draw of 1,092 households the same check has **42.6% power** at 10%, needs **20%** for 95% power, and would need **3,664 households** to reach 95% power at 10% — against Cobh's real 5,257 and the scaled town's 1,092. The generator is **deterministic** in this marginal (across-run SD 1.7e-16 over 40 seeds, in both the correct and the shifted arm). New ensemble check at **K = 20** runs (minimum 4), judging the ensemble mean against the control totals the generator was given, with a standard-error floor of half a household and a Bonferroni **t** band on K−1 df: measured power **1.0**, false-positive rate **0.0**, firing at **1.5 households** against the single-realisation band's 34.3 | The acceptance band is the multinomial sampling error of a 1,092-household draw (≈0.013 near p=0.25) while the generator's own run-to-run error is zero, so the band is ≈28× wider than the precision of the thing it tests and a bias well inside it is still an unambiguous defect. That is not a fault in the band — it is the right band for "could a town this size look like this by chance" — it is the wrong band for "is the generator biased", which is what a shifted-marginal control asks. K = 20 rather than the minimum 4 because the SD is estimated from the same K runs: the t band is 6.895 at K=4 against 3.074 at K=20 (asymptote 2.734), so the check pays 13% for estimating its own variance instead of 152%, and retains teeth on the marginals that genuinely vary (age band SD ≤0.0032, sex 0.0074). Artefact: `v1/evidence/marginal_power_analysis.json` | Yes |
| D-027 | 2026-10-09 | The ensemble check tests the generator against **the control totals the declared procedure produces**, and the deviation of those totals from raw SAPS is bounded separately by `ENSEMBLE_TARGET_VS_SAPS_MAX_ABS_Z` = 2.7344 (currently 1.9827) | Forced by the false-positive control, measured not argued. Taking "test the ensemble mean against SAPS" literally **rejects a correct population** at every K from 4 upwards — max \|z\| 54.9 against a t band of 6.90 at K=4 — because the deliberate person-total repair moves the two-person share by −0.0251 and the three-person share by +0.0228 to satisfy both of R03's ranges (I-012, D-010), which is *larger* than the 10% fault being planted. Two questions need two references: "does the generator reproduce its target" and "is the target faithful to SAPS". Collapsing them into one number is how a check becomes either blind or always-firing, and the bound on the second is what stops the declared repair growing into an undeclared bias | No (architectural) |

## Part C — implementation decisions taken under r4's rulings

**The U-decisions that were here have been retired into design revision 4.**

`docs/Baile_Nua_Technical_Design_Review_r4.md` arrived on 10 October 2026 and is
now the single design reference (D-001 amended). It declares **U01 to U31** in
its section 11 decision table and records progress against the gates in its new
**section 9.6**, with the full task history in **Appendix A**. Part C existed
only because r4 did not: U22 to U28 were approved in the week 2/3 brief on 9
October, one day after r3 was frozen, so they were recorded here from the prompt
(I-035, I-038). That gap is closed.

| Retired from here | Now declared in |
| --- | --- |
| U03 (settled), U22, U23, U24, U25, U26, U27, U28, U28a, U29, U30, I-039 | r4 section 11 (the decision table), and section 9.6 for I-039 |
| their measured outcomes | r4 section 9.6 (progress against gates) |
| the task history behind them | r4 Appendix A |

**Wording checked, not assumed.** Each retired row was compared against r4's
own text before removal, and the substance matches in every case — including
U28, where r4 carries both the original ruling and the task-7 storage-fallback
amendment, and U31, whose r4 row says *"used only for evaluation, never fitted
on"*, which is what `slice_u31.py` enforces. Two differences of emphasis rather
than substance are worth recording:

* r4's decision table states each ruling and its options; Part C also carried
  the **measured outcome** in a status column. Those outcomes are in r4 section
  9.6 at headline precision, and at full precision in the artefacts
  (`v1/evidence/package_projection_u28.json`,
  `assumption_sweep_u30.json`, `ablation_u22.json`, `heldout_u31.json`) and in
  `PROGRESS.md`. Nothing was lost by removing the duplicate.
* r4's header line says revision 4 "adds ... decisions U22 to U28", but the
  document itself declares **U29, U30 and U31** as well. The table is the
  authority; the header undercounts its own content.

**One ruling was NOT retired, because r4 does not contain it.** Checking each
row against r4 before removing it found that the **seed-variance** ruling has no
counterpart there: `grep` for "family of towns", "seed variance", "across
seeds", "sampling variation" and `I-037` across r4 returns nothing. It is
Brian's ruling and it is load-bearing — it is why the across-seed SD of fitted
control totals being exactly zero is recorded as correct rather than as a
defect — so it stays below, flagged, rather than being retired into a document
that would have dropped it. This is the whole reason each row was checked
individually instead of the section being deleted wholesale.

| ID | Date | Decision | Reason | Brian to confirm |
| --- | --- | --- | --- | --- |
| Seed variance | 2026-10-09 | The generator reproduces control totals exactly across seeds; that is correct for one calibrated town. A "family of towns" mode (sampling variation) is out of scope for now | Recorded per instruction. **Not present in r4** — if revision 5 should carry it, this is the text | Recorded as I-037; still awaiting a home in the design document |

**What stays here, and why.** The rows below are mine, not Brian's: they are
implementation decisions taken while carrying out the rulings above, and r4
does not record them. They continue to be numbered D-nnn and to live in this
log, which is what Part B is for — Part C is retained as their heading rather
than deleted so the D-numbers keep a stable home and existing cross-references
still resolve.

| ID | Date | Decision | Reason | Brian to confirm |
| --- | --- | --- | --- | --- |
| D-051 | 2026-10-10 | U31's held-out slice is **stratified and not contiguous**, **gas-only**, and **not people-band constrained**, each departure declared in its diagnostics | D-018 and D-028 selected contiguous blocks because R01 wants estates and 6.4 wants a sub-metered subset sharing a feeder. No feeder study runs on this slice, and Cobh's pre-1980 and post-2005 stock are in different parts of the town, so contiguity would cost exactly the coverage the comparison needs. DBERNG02 is a gas meter reading, so a dwelling burning no gas contributes nothing. E0-7's people band sizes the SIMULATED slice; this one's constraint is enough dwellings per cell to take a mean, and forcing the band would fight the stratification | Yes |
| D-052 | 2026-10-10 | The two groups are **balanced in size** (30 and 30) and the slice is checked to be balanced on **floor area** before use | The difference of two means has its standard error dominated by the smaller cell, so equal allocation minimises it. And DBERNG01's actual finding is that measured consumption tracks dwelling SIZE - so a size-confounded slice could not separate fabric from size, and any gradient on it would be partly a size effect wearing a fabric label. Measured: Welch p = 0.754 on floor area (balanced) and p = 3.5e-08 on specific heat loss (contrasted, 1.82x) | Yes |
| D-053 | 2026-10-10 | Nothing is fitted on the held-out slice, and it is enforced rather than intended: `EVALUATION_ONLY`, a test that the ablation's default slice is not this one, a test pinning the comfort-taking amplitudes, and the U23 DER guarantee deliberately skipped | 7.1 requires calibration and validation to stay disjoint. A slice that quietly became a calibration set would make U22's validation worthless while still producing numbers, which is worse than producing none. The DER guarantee is a declared intervention that assigns an adoption the stochastic draw did not make; doing that to an evaluation sample would change what is being evaluated | Yes |
| D-054 | 2026-10-10 | The small hours belong to **yesterday's** drawn bedtime, recovered from the (person, sim_day - 1) stream rather than carried as state; the runner supplies yesterday's day type from the calendar | I-044. `place(0, wake, "sleep")` claimed minutes 0 to wake unconditionally, so every bedtime past midnight was computed and discarded and nobody in the town was awake after midnight on any night. Re-drawing from the counter-based stream is exact, needs no state to cross the day boundary, and so leaves multi-worker determinism and checkpoint replay untouched - carrying a last-night field in `HouseholdState` would have put a behavioural quantity into the reproducibility contract for no gain. Yesterday's day type matters because a Friday night runs later than a Sunday one | Yes |
| U32 | **Overnight metric and sleep timing, 10 Oct 2026.** Replace PL-PEAK-01's two-point taper with a whole-overnight-shape check (22:00-06:00 against LP1), keep the taper as a secondary metric, and fix the bedtime transition only from a time-use source | I-050: the step 4 ablation improved the two-point taper by making the model worse. I-051: the overnight profile ran low from 00:00 to 02:00 | **Both parts done.** Part 1: the gating term is the mean absolute deviation across 22:00-06:00, band **derived** from LP1 as half what a shapeless profile would show (0.1901), taper reported but not gating. Part 2: bedtime and wake spread taken from HETUS UK AC0A, medians left Irish-anchored; awake-share MAD **0.0283** on the mixed-age slice. The 06:00 deficit halved (-0.21 to -0.11) and did not close; the residual is the activity-to-load mix, not the sleep timing (I-051). PL-PEAK-01 passes at 0.1467 where the old taper would have failed at 1.2013 |
| D-055 | 2026-10-10 | PL-PEAK-01's overnight band is **derived from LP1**, as half the deviation a profile with no overnight shape would show | A band set just above the worst observed slice would be fitted to pass. Anchoring on the degenerate case the check exists to reject makes the threshold a property of the published reference: the check must reject a shapeless profile by a factor of two. It comes out at 0.1901 and is recomputed from the source rather than typed in | Yes |
| D-056 | 2026-10-10 | Sleep timing takes its **spread** from HETUS UK and its **medians** from Irish sources; where the two meet, the Irish anchor bounds the UK one | The wake median is anchored to Cobh's Census travel-to-work tables and the commute to its departure bands, so taking the centre from a UK donor would overwrite an Irish measurement with a foreign one. Dispersion transfers between countries far better than when people get up. And the direction of binding matters: a model in which 1% of Cobh's workers wake at 12:40 would be using HETUS to overrule SAPS, so the Census-derived cap damps the UK spread by a derived 0.732 rather than clipping it - clipping piled 16.9% of workers onto a single minute | Yes |
| D-057 | 2026-10-10 | Chronotype **selects the sleep-timing quantile** rather than adding an offset of its own; bedtime is anchored once, independently of each person's wake base | Adding an hourly offset on top of a sourced distribution would widen the population's marginal past the source - which happened twice in building this: computing bedtime from the drawn wake gave it both spreads (10-90 range 389 minutes against the source's 187, median displaced 48 minutes, a tenth of the town pinned at the clip), and giving non-workers a later wake base pushed their bedtime 90 minutes later too, sending 23:00 to +0.227. Waking later means sleeping longer, not going to bed later, which is what HETUS implies anyway | Yes |
| D-028 | 2026-10-09 | The U23 mixed-age slice selects its seed small area by a **declared objective** (pre-1980 share, D–G share, BER-letter count, penalised for departing from the town's household size) and then **searches** the seed areas for one whose slice also satisfies E0-7's people band and the pre-1980 floor. The band is a hard constraint, never a term in the objective. `slice_kind` defaults to `"e1_estate"` so every E1 artefact reproduces unchanged | The first selector made the people band a penalty weighted 0.8 against an age reward of 1.0, and the best-scoring seed gave **112 people against a 115 lower bound** — three short. Re-weighting until it fitted would have been choosing the weights to get the answer; searching the seeds is the same work done honestly, and it raises `U23Infeasible` when no seed satisfies both | Yes |
| D-029 | 2026-10-09 | Where the DER adoption draw yields none of a type U23 requires, the adoption is assigned to the **highest-propensity home under the same model** and the assignment is recorded in `der_guarantees` | PV, battery and EV adoption are stochastic, so a 50-home slice can legitimately draw zero batteries (p=0.35 of PV homes). U23 requires at least one because the slice exists to exercise those paths. The model's rates are unchanged and the town-wide draw is untouched — this is a declared guarantee on the slice, not a correction to the model. In the event none was needed: the slice drew 6 PV, 1 battery and 6 EVs | Yes |
| D-030 | 2026-10-09 | The week 2 slice size is a **separate named scope** (`week2_slice` in `config/e1_scope.yaml`) and `assert_within_e1_scope` takes a `scope_name`; the E1 `slice` block is untouched at 50 homes | U29 asked for 60 homes. Raising `slice.n_homes` would have raised the ceiling that every E1 artefact was produced and re-verified under, and the E1 gate's scope assertion would then no longer be the assertion that gate passed. Two scopes cost one parameter and keep E1 reproducible against exactly what E0-7 approved | Yes |
| D-031 | 2026-10-09 | The slice's people count is tested to equal the **sum of its households' actual sizes** (`test_household_sizes_are_taken_as_the_data_give_them`) | U29's "keep household sizes as the data give them" needs an assertion, not an intention. Without it, a future selector could meet the people band by adjusting a household rather than by choosing which part of the town to simulate — and that is fabricating population to satisfy a scope constraint | Yes |
| D-032 | 2026-10-09 | The U30 sweep **computes** its hits and **declares** only its verdicts: each flag carries its search terms and what evidence would retire it, both written before searching, and the terms are run over a declared catalogue source with a date and a SHA-256 | A verdict of "nothing public exists" is a decision to keep an assumption, and as prose it would never fail when the CSO published something. `ZERO_HIT_CLAIMS` makes the decisive negatives machine-checked, so the day one starts matching, the suite says so - that is good news, not a broken test | Yes |
| D-033 | 2026-10-09 | Searches run over table titles **and the label of every dimension**; a term matching more than 300 tables is failed as not a search | HS023 is titled "Households" - everything that makes it the answer to the ownership-slope assumption is in its dimensions, and that is how HAS02 was missed. The breadth guard exists because unanchored `BER\b` matches 932 tables through "Number" and "Member"; a term that matches hundreds has drowned, not searched | Yes |
| D-034 | 2026-10-09 | A verdict of `RETIRED` requires the source declared, fetched **and scored against**; a source found but not yet used is `SOURCE_FOUND` and must name the step that will use it | An unused source retires nothing - that is precisely what happened to HAS02 for four days. The distinction is enforced in `AssumptionFlag.__post_init__`, so the sweep cannot claim a retirement it has not made | Yes |
| D-035 | 2026-10-09 | Where a reference publishes **overlapping** categories, the model's value is checked against the feasible **interval** of their union, with the interval's width reported | HBS refrigeration categories sum past 100% (Refrigerator 25.6%, Refrigerator with freezer 81.6%), so the share with ANY refrigerator - what the model's single prior means - is bounded, not published. A first version of this check scored 0.99 against 81.6% and failed, which was comparing a union against a part: a flaw in the check, not the model. Discarding the appliance would have been the other error; the valid inference is the interval, declared as weak (width 0.184) rather than presented as tight | Yes |
| D-036 | 2026-10-09 | F2063 validates the rooms x dwelling-type joint and **may not be used to tune** `ROOM_ALLOCATION_STRENGTH` or `DWELLING_SIZE_RANK` | Those constants were set before the sweep found F2063, so the table judges them: the model reproduces 85% of Cork County's detached-minus-apartment gradient (2.63 of 3.08 rooms) and sits within 0.29 rooms of every conditional mean. That is the first time the I-031 fix has been checked against external data rather than against a feasibility test. Fitting the constants to it would turn validation into calibration and the source's declaration would have to change with it (I-040) | Yes |
| D-037 | 2026-10-09 | PL-PEAK-01 reads **one named D19 export view** at a single interval length, and raises if the view is absent or the lengths are mixed | D19 holds four configurations of the same energy - `home_15min`, `home_30min`, `compliance_only` and a pre-summed `estate_aggregate`. Summing its rows counted the estate about four times and reported 9.2 kW per home against the diagnostics' own 1.49 kW. The run diagnostics' independently computed `feeder_peak_w_per_home` is now a test, and it agrees to within 2% - that cross-check is what caught it | Yes |
| D-038 | 2026-10-09 | The overnight term is a taper **ratio** (mean 00:00 over mean 04:00), not a trough **hour** | The model's overnight is flat, so its argmin landed on hour 0 against LP1's 04:00 - a four-hour error resting on a 0.02 difference between indistinguishable hours. The argmin of a near-constant function is not a statistic. The ratio says what the argmin only hinted at, and the check fails on it either way, so the band was not chosen to produce a verdict | Yes |
| D-039 | 2026-10-09 | PL-PEAK-01's load-factor band is **asymmetric**: at most 0.05 above LP1's, and at most 0.15 below only once 1,000 homes are aggregated | Both the diversity and the resolution arguments push the measured value down - a town of 1,100 is spikier than two million meters, and a peak measured over a shorter interval cannot be lower. Exceeding the national class is therefore not a tolerance question but a sign that load has been spread too evenly, which is one of the tells 7.9 audits for. The E1 slice's 0.2565 against LP1's 0.4129 is the expected direction and size for 50 homes, not a fault | Yes |
| D-040 | 2026-10-09 | A plausibility check the package is known to fail is declared in `KNOWN_FAILURES` with its issue, not tolerated and not skipped | I-044 is a real defect and the suite must keep saying so. The list is two-sided: a new failure still breaks the suite, and a listed failure that starts PASSING also breaks it, so an entry cannot outlive the defect it describes | Yes |
| D-041 | 2026-10-09 | A plausibility failure the package is known to have is declared once, in `KNOWN_PLAUSIBILITY_FAILURES`, and both the run hook and the test read it | U27's write hook refuses to deliver a package that contradicts a published reference, and after I-044 that meant refusing every run on a defect already written down. Two different events looked identical to it: a defect with an issue number and a defect nobody knew about. The hook now announces a known failure loudly with its issue every run and raises only on an undeclared one. Two rules stop it becoming a waiver - a listed failure that starts PASSING is an error, and every entry must name an issue that exists in ISSUES.md | Yes |
| D-042 | 2026-10-09 | The immersion heater is a **cylinder** device, not an appliance; `electric_shower` stays an appliance | Modelling the immersion on the tank while it was also an appliance with a load signature would have charged every immersion twice, for two different lots of hot water. The electric shower is genuinely an appliance and DEAP says so: it "uses electricity directly rather than from the water heating system", so `draw_schedule` takes no tank draw for a home that has one. The appliance-failure disruption now reaches the cylinder, which it had to - once the appliance was gone the disruption would otherwise have done nothing | Yes |
| D-043 | 2026-10-09 | Hot water DEMAND is built from draw events tied to simulated activities, not from DEAP's floor-area route, and DEAP's figure is kept as the thing the result is judged against | U25 asks for draw events, and the activity engine already simulates showering, bathing, washing up and cooking with HETUS durations. Deriving demand from floor area the way DEAP does would make the model reproduce the reference by construction and unable to disagree with it. The shower volume is the part that is not assumed: DEAP's 6 L/min minimum times the minutes the water runs | Yes |
| D-044 | 2026-10-09 | The minutes a shower's water **runs** are separate from the length of the `shower_bath` episode, capped by it, and declared | Charging 6 L/min across the whole episode - time in the bathroom, up to 25 minutes - made 150-litre showers and about 800 litres a day per household, 70 to 85% of all hot water. DEAP publishes the flow rate and not the duration, so the duration is a declared assumption; PL-DHW-01 bounds its consequence against DEAP's own 125 L/person/day all-water target rather than leaving it unchecked | Yes |
| D-045 | 2026-10-09 | The cooking-fuel share is **derived** from HEBEU34 and HEBEU106 rather than declared, and assigned three ways: all-gas, gas hob with electric oven, all-electric | U30's phrase search for `cooking fuel` found nothing and was wrong - the CSO's tables are titled "Main fuel used for cooking in households" (I-046). The share conditional on a gas connection is P(cooks with gas) / P(gas connected) = 14%/48% and 9%/48%, both from the same survey and year so the ratio does not straddle two definitions. The "combination" category is not a residual: it is a gas hob with an electric oven, and the model already priced hob and oven separately. Two caveats travel with the derivation rather than being buried - the denominator is gas HEATING, a lower bound on connections, so the shares are upper bounds; and the tables are 2024 against a T0 of 2022, so they set a structural share and not a level | Yes |
| D-046 | 2026-10-09 | A sweep search term should be the **subject noun**, not the phrase a reader expects; the breadth guard exists to make that affordable | A phrase tests one word order. `cooking fuel` and `gas cooking` both missed six tables that say "fuel used for cooking". The sweep already knew dimension labels matter more than titles - that is how HAS02 and HS023 were found - and now also knows the term itself has to be short. `BROAD_TERM_LIMIT` at 300 is what makes a plain term safe to use rather than something to avoid | Yes |
| D-047 | 2026-10-09 | Comfort-taking is **three COM-B terms with different drivers**, not one amplitude | A single knob fitted to DBERNG01's flatness would reproduce the flatness and tell us nothing. Three terms can disagree with the data, and the falsifiable consequence is that prebound is a COST response: the same leaky dwelling takes -1.50 K from a quintile-1 local-authority household and -0.00 K from a well-off owner. No fabric correction can produce that | Yes |
| D-048 | 2026-10-09 | The mechanism is centred on the town's **median** specific heat loss, not its mean | The distribution is right-skewed - 0.63 to 6.49 W/K/m2, median 2.08 against mean 2.46 - so centring on the mean would put most dwellings on the rebound side and give the mechanism a net warming effect on the town instead of a redistribution across the fabric range. Comfort-taking redistributes; a test pins that the town-mean shift stays small against the spread it creates | Yes |
| D-049 | 2026-10-09 | The comfort-taking strength is **not fitted** to DBERNG01, and the sweep is published instead | DBERNG01 is the declared calibration axis so fitting would have been permitted. But the mechanism saturates at 45% spread against a 4-7% target, so a fitted strength would buy nothing except the appearance of calibration while costing a kelvin of indoor temperature. The declared amplitudes stand and the sweep sits beside them so a reader can see what each strength costs | Yes |
| D-050 | 2026-10-09 | `write_package=False` makes an ablation arm affordable, and a skipped plausibility suite says "NOT RUN" rather than nothing | Writing D18 and D19 is about 60% of a run and an ablation needs the diagnostics, not the package. The difference between a mechanism compared against its own absence and one asserted to work is whether the comparison was cheap enough to actually run. The storage projection returns None rather than 0 GB for an unwritten package, because a projected 0 GB would read as a measurement | Yes |
| D-058 | 2026-10-10 | A D20 label's `detectable_from_tier` is **derived** from the sensor channels its text appeals to, not declared alongside it | The schema defines the field as "the lowest tier at which it is theoretically observable", which is a claim about channels, and `TIER_DEVICES` says which channels each tier has. So the tier is computed, and the acceptance test re-derives it: a label claiming something its tier cannot see fails, and so does one pitched higher than it needs to be, because "lowest" is part of the contract. The evidence that this is the rule the design meant rather than one invented to pass is that it reproduces all four of design 5.9's hand-written Mary tiers - T1, T2, T1, T3 - which were written before any of this existed | Yes |
| D-059 | 2026-10-10 | The hazard integrated **at draw time** is recorded and compared against the exposure-based expectation, every run | The VSA36 parity reweighting multiplied each woman's rate by a parity share, which rescaled every rate downwards and lost 12% of the births: 10.15 integrated against an exposure expectation of 11.52. From the outside that is indistinguishable from a model missing its target, and no vital-statistics interval would have caught it - 10.15 was comfortably inside the CI. The fix normalises the parity weights to mean 1.0 within each band so the published band rate is preserved exactly, and the comparison stays as a permanent check because the bug class is invisible without it | Yes |
| D-060 | 2026-10-10 | A **vacant dwelling** stays in the slice with an empty household and is held at frost protection, rather than being dropped | WP5's ten-year life course produces vacancies. Dropping the building would take a connected house out of the feeder aggregate, and the move-out label's own claim - that load falls to a standing baseline - would then describe a premises that is not in the data. The runner raised `IndexError` on `people[0]` for an empty household, which is the right failure for a state it had never been told could exist. 7 C is `[A]` (A-40) and deliberately narrow: DEAP has no vacancy case, and the quantity it moves is a standing baseline rather than a peak | Yes |
| D-061 | 2026-10-10 | The vacancy rate is an **outcome**, not a quota: the chain refills vacancies and never empties a home to hit a target | VAC04 puts Cork County at 5 to 6 per cent and the slice starts fully occupied, so year one can only approach that from below. A selector that vacated homes to reach the published rate would be fabricating moves to satisfy a statistic. The test is therefore two claims - the rate never EXCEEDS the published maximum, and once the chain has run a year it sits INSIDE the published range - and the first version, which asserted the range from year one, failed correctly | Yes |
| D-062 | 2026-10-10 | Fabric retrofit and extension produce their **D03 passport events and D20 labels** but do **not** change the RC parameters in week 2 | I-048 defers the fabric work to week 3 and the standing instruction is no fabric tuning now. Suppressing the passport events instead would make the ten-year building history wrong in order to make a week-2 package self-consistent - the events are ground truth about what happened to the building. The consequence is real and recorded as I-054: a detector scored against a `retrofit_fabric` label in a week-2 package scores a false negative through no fault of its own, for 8 fabric retrofits and 10 extensions. It is in the run diagnostics and asserted by a test, so week 3 has to come back and flip it | Yes |
| D-063 | 2026-10-10 | Every declared JSON-stat source's own `label` is compared against the registry's declared `title`, with a threshold **measured from the corpus** | I-053: two vital-statistics sources were declared under crossed matrices - births pointing at VSA09, which publishes deaths - and neither carried an age dimension at all. Nothing had ever opened them, because sweep flag A-25 scheduled their first use for week 2 step 5, so the registry's claim went untested for a week. A declared source that nothing consumes is an unverified claim. Across the 34 fetched cubes the lowest real content-word overlap is 0.40, where a title adds dimension breakdowns the CSO's short label omits; the two I-053 cases score 0.00. The threshold sits at 0.25, and a test asserts the guard still fails on the historical error | Yes |
| D-064 | 2026-10-10 | R20's event coverage audit separates "**absent from the generated year**" from "**present but unsourced**", and the split of sourced, legal and assumed is reported rather than totalled | A class can look covered because rows exist for it while nothing backs the rate they were drawn from, which is the failure R20 actually names. Reporting "ten of ten covered" would hide that three are sourced, two are legal instruments and six are `[A]`. The one event class that most distinguishes Cobh from a generic Irish town - a cruise call landing 1,420 passengers into a town of 3,000 - is the one with a real source, TBA10 and TBA11 | Yes |
| D-065 | 2026-10-10 | Correlated events come from a **shared driver** that each event names, and `driver_audit` refuses an event claiming a driver that does not generate it | Design 5.10 says compound correlation comes from shared drivers. Outages drawn independently of the weather would put the lights out on a calm day, and a model that had learned the real storm-outage correlation would then be penalised for being right. K09 adds the reason it has to be recorded: a pairwise matrix over ten event kinds is not validatable, so validation is by class and by driver, which is only possible if the driver is in the data. 86% of multi-kind days are driver-explained and 5 are genuine chance overlaps. State kinds are excluded from the count - a six-week term overlapping a fixture is a Saturday, and counting it buried the five that meant something | Yes |
| D-066 | 2026-10-10 | The 8.2 staleness margin is **derived from LP1's measured maximum quarter-hour ramp** (0.256 of mean), not from the model's own output | The margin's job is to cover how much a connection can move between network solves. Measuring that from our own series would have the model certifying itself - the contract's guarantee would be circular. LP1 is the settlement profile for an urban domestic connection, so its largest published quarter-hour ramp is a published per-connection ramp. It is an after-diversity ramp, so it is a LOWER bound on what one dwelling needs, and the coupling-lag test is written knowing that | Yes |
| D-067 | 2026-10-10 | The conservative envelope is the **minimum of the connection's headroom and its share of the upstream element's**, not the connection's alone | A literal reading of 8.2's wording gave per-connection headroom only, and twenty homes each inside their own 12 kW service limit collectively overloaded a 40 kW feeder. C1 then extracted 1,213 kWh against C2's 908 **while causing the violations**, because a 15-minute commitment is made before a 15-minute-old solve can reveal the overload - which is exactly the gain from stale information the contract forbids. It appears only when the binding element is upstream, so a test at one operating point would have certified a broken contract. The equal share is conservative and is a choice; a real allocation is a network calculation, which is week 3 | Yes |
| D-068 | 2026-10-10 | Envelope tightening and relaxation are rates **per unit of time**, not per epoch | Tightening by a fixed factor per violating epoch made C2, with 1440 epochs a day against C1's 96, tighten up to fifteen times as hard for the same physical violations. The two coupling modes would then have differed because of epoch counting rather than because of staleness, which is precisely the confound that makes a coupling-lag test meaningless. Violations are reported in MINUTES for the same reason: a quarter-hour overload is one row at C1 and fifteen at C2 | Yes |
| D-069 | 2026-10-10 | A counterfactual **refuses** a household-scoped fork, and paired and unpaired entities are reported separately rather than pooled | Design 8.2's explicit rule is that any intervention forces a town fork, and a single-household replay is cheap and tempting and would be wrong invisibly: the home's own load would respond correctly while the feeder, the venues and the later events stayed at baseline, so the estimate would miss exactly the coupled effect the intervention was interesting for. On CRN, the counter-based tree makes the same coordinate give the same number for free, so what is actually measured is whether the same coordinates are VISITED - and an entity the intervention does not touch that decouples anyway is a finding, because a paired statistic over it compares two random sequences while reporting the variance of one | Yes |
| D-070 | 2026-10-10 | Every G-C mode declares its expected outcome **class** in advance, and the expected class is often not PASS | Design 5.14 separates a software defect from a recognised limitation, and under the non-identifiable mode a correct estimator *must* fail to recover separate coefficients. Treating that as a bug sends the MIMIC team chasing a property of the design matrix; treating it as a pass hides that the quantity is not recoverable. So a mode coming out PASS where a limitation was declared is itself a finding - an estimator that recovers non-identifiable parameters is recovering its own prior | Yes |
| D-071 | 2026-10-10 | T6's statistic is **incremental cross-validated** R², and the null control's confounder is deliberately **observed** | In sample, adding any column can only raise R², so an in-sample test would find predictive value in pure noise and the null would pass by construction - a test demonstrates exactly that on the null cohort. And the confounder has to be observed for the null to be fair: with a hidden confounder, stated willingness would legitimately carry information about revealed behaviour and a correct method using it would be marked defective. The null returns -0.0001 against a minimum detectable 0.0039, while the linked arm returns +0.094, so the negative result is informative rather than vacuous | Yes |
| D-072 | 2026-10-10 | Three G-C acceptance criteria were **wrong before they were right**, and each was corrected by the data rather than by argument | The non-identifiable mode used r = 0.97 while claiming non-identifiability "at any sample size": false, because variance inflation there is only about 17 and the coefficients come back with standard errors near 0.054. Its criterion then went through a fixed standard-error threshold and half the coefficient gap before arriving at the textbook statement - under collinearity prediction is identified and coefficient inference is not. And the cluster mode compared a silhouette against a declared 0.25, which the data refused: k-means on one correlated Gaussian scores 0.31, because splitting any blob in two gives a respectable silhouette. It now compares against the same statistic on Gaussian data with the data's own covariance, 0.314 against 0.330 +/- 0.010 | Yes |
| D-073 | 2026-10-11 | **Pre-registered before running U31.** Under the sourced BER fabric the old/new gas gradient must **fall** from 1.6158; the old-stock at-meter ratio must **fall** from 1.1806 and the new-stock ratio must **rise** from 0.7307, each paired-significant at p < 0.05; both must move **towards 1.0**; and the gradient must **not** fall below 1.0. Expected magnitude, stated but not a pass condition: gradient ≈ **1.21** | Written and committed before the run, because the fabric was derived from a source (SEAI BER Research Tool) that is now tuning-exposed, and U31 is the only independent evidence that the change earns its keep. A criterion chosen after seeing the gradient would be worthless. The magnitude is derived from the fabric alone and never from U31: the envelope heat-loss coefficient moves by **x0.924** on the old group and **x1.657** on the new (measured on the held-out slice's own 60 dwellings), and space heat is **58.8%** of old-group meter gas and **41.5%** of new-group (`heldout_u31.json`), which gives 1.1806 x 0.955 = 1.13 and 0.7307 x 1.273 = 0.93, hence 1.21. It is an expectation and not a gate because space heat is not exactly proportional to envelope HLC — infiltration is a separate path, and comfort-taking will partly offset the new group's rise, since a leakier dwelling has a higher cost per degree and takes more prebound | Yes |

### D-073 pre-registration, in full

Committed **before** the fabric change was wired in and before U31 was re-run.
The table row above is the summary; this is the criterion as written, so that
the outcome can be read against it without interpretation.

**Why pre-register at all.** The fabric is now derived from the SEAI BER
Research Tool, which is therefore tuning-exposed for fabric (I-058) and can
never validate it. The held-out gas axis is the only independent evidence that
the change is an improvement rather than a re-parameterisation. A pass
criterion written after seeing the new gradient would carry no information.

**Baseline, from `v1/evidence/heldout_u31.json` (`gradient.on`, `groups.*.on`):**

| quantity | value |
| --- | --- |
| old-stock at-meter ratio (1974–1998, n=30) | 1.1806 |
| new-stock at-meter ratio (2005–2021, n=30) | 0.7307 |
| gradient, old / new | **1.6158** |
| residual gap significance | t = 4.371, p = 7.85e-05 |

**Predicted direction — these are the pass conditions, all four required:**

1. **The gradient falls.** New gradient < 1.6158.
2. **Each group moves the right way, significantly.** The old-stock mean ratio
   falls and the new-stock mean ratio rises, each tested paired by dwelling
   at p < 0.05. Paired because the same 60 dwellings are simulated before and
   after, so the comparison can and should remove between-dwelling variance.
3. **Both move towards 1.0.** |old − 1| falls *and* |new − 1| falls. Without
   this, a gradient could shrink because both ratios drifted the same way,
   which would not be the fabric error being corrected.
4. **No overshoot.** The gradient must not fall below 1.0. Below 1.0 the model
   would over-consume on *new* stock relative to old — the same error
   inverted, which is not a fix.

**Expected magnitude — stated, and explicitly NOT a pass condition:**

gradient ≈ **1.21**, from old 1.1806 → ≈1.13 and new 0.7307 → ≈0.93.

Derived from the fabric and the existing artefact only, never from U31's
gradient: the envelope heat-loss coefficient on the held-out slice's own
dwellings moves by ×0.924 (old group, p10 0.617, p90 1.447) and ×1.657 (new
group, p10 1.286, p90 2.303) when the era×multiplier fabric is replaced by the
assessed conditional; space heat is 58.8% of old-group meter gas and 41.5% of
new-group. It is not a gate because space heat is not exactly proportional to
envelope HLC — infiltration is a separate path, the solver carries thermal
mass and solar gains, and comfort-taking will partly offset the new group's
rise because a leakier dwelling has a higher cost per degree and takes more
prebound.

**Declared failure modes, to be reported as failures if they occur:**

* the gradient rises, or does not fall significantly → the fabric change does
  not earn its keep on the independent axis, whatever it did to the U-value
  comparison it was built from;
* either group moves the wrong way → the correction is not acting as the
  mechanism predicts;
* the gradient falls below 1.0 → over-correction, and the old/new error has
  been inverted rather than removed.

**Watch items, not pass conditions.** PL-GAS-01 is expected to **fall** on the
mixed-age slice (old stock loses heat loss; 0.983 against a band of [0.25,
1.00]) and to **rise** on the E1 estate (modern stock gains heat loss; 0.331).
The E1 direction is the one to watch, because the band's upper edge is 1.00 and
PL-GAS-01 is itself scored against a calibration input (I-058), so it cannot
adjudicate this either way.

**U31 remains evaluation-only.** Nothing is fitted on it, and no parameter will
be changed after seeing any number it produces. If the criterion fails, the
failure is reported and the fabric question returns to the evidence rather
than to the amplitudes.
| D-074 | 2026-10-11 | Wall, roof, floor and window U-values come from SEAI's **assessed** distribution conditional on (era cell, BER band); the BER-band multiplier is **not** also applied to them. Door, thermal bridging and infiltration keep the era table and stay `[A]` | The multiplier is the mechanism I-048 showed to be wrong — capped at 0.55, it cannot reach a deeply retrofitted old house (floor 2.1 x 0.55 = 1.155 against an assessed 0.25) and it penalises a modern dwelling whose fabric meets the regulations whatever its band. Applying it on top of the assessed conditional would count the band twice, because the conditional already depends on it. The source publishes no door U-value, no bridging factor and no air-change rate, so those three keep the era table; `derive_rc` reports `fabric_sourced_share_of_hlc`, measured at **0.34 to 0.73**, so the claim can be checked rather than taken on trust | Yes |
| D-075 | 2026-10-11 | The comfort-taking reference moves from **2.08 to 1.813** W/K/m², and this is **not** a new choice | D-048 defines the reference as the town's median specific heat loss. Sourcing the fabric narrowed the town from 0.63–6.49 W/K/m² (factor 10.3, median 2.08) to 0.859–5.642 (factor 6.6, median 1.813), which is what I-048 predicted. So the median moved and the declared rule says the reference follows. `test_the_reference_is_the_towns_median_not_its_mean` caught it before anything was run — the constant was stale by 0.27 W/K/m² and the suite said so. The consequence for U31 is stated rather than hidden: the measured change is the fabric **plus** this entailed re-centring, and U31's comfort-**off** arm isolates the pure fabric effect at no extra cost, because the reference does not apply there | Yes |
| D-076 | 2026-10-11 | A D03 passport event changes the fabric **from its effective day**, at the day boundary, and its U-values are **published**: DEAP Table S3's filled-cavity wall (0.6 for bands A–G) and Table S4's roof at the declared depth for a retrofit; DEAP Table S2 band L for an extension's new fabric | I-054: 45% of the decade's building changes were absent from the series, so a detector scored against those labels scored a false negative through no fault of its own. The day boundary rather than mid-day because a day's energy balance must describe one building. The U-values are published because the fabric is already derived from a tuning-exposed source — a retrofit magnitude chosen to move the gas ratio would be the same mistake twice. **Raising the BER band was the first design and was rejected as circular**: the fabric is derived from the conditional *keyed on the band*, so moving the band moves the fabric by whatever the assessed population correlates with, not by what insulating a wall does. What stays `[A]` is the loft depth (DEAP publishes the U-value per depth, not the depth installed), the extension's area share, and which measures a retrofit comprises | Yes |
| D-077 | 2026-10-11 | The U31 driver and gradient computation move **into the repository** (`validation/heldout_u31.py`) | The committed `heldout_u31.json` was produced by a driver that lived only in a scratchpad directory. The statistics were in the repository; the code that called them and wrote the artefact was not, so a committed evidence artefact could not be regenerated from the repository — whatever its contents claimed. Moved with its statistics unchanged (the same paired `ttest_rel` within groups, the same Welch test for the residual gap, the same gradient definition), and verified by reproducing the baseline exactly: gradient off 1.7682, on 1.6158, old 1.1806, new 0.7307. Re-running U31 must not quietly become a different test | Yes |

---

### D-078 — activity placement weight: pre-registered before measuring the third arm

**Written and committed before running the arm.** Week 3 step 3, I-052.

The standing instruction is that activity timings must come from HETUS
participation curves and **must never be adjusted to match LP1**. Two arms have
been measured against LP1 and the third is pre-registered here so that its
outcome cannot be read as a fit.

**What has been measured** (`work/i052/*/lp1_score.json`), mean absolute
relative deviation of load per awake person over hours 22–06:

| arm | placement weight | MARD vs LP1 |
| --- | --- | --- |
| `duration_weighted` | `participation(a,m) × (target[a] + 1)` — the week-2 model | **0.1720** |
| `participation_only` | `participation(a,m)` — week 3 step 3 as instructed | **0.2882** |

So removing the duration factor made the LP1 score **worse**, and that is
reported as it stands. It is not a reason to revert, because reverting on the
strength of an LP1 score is the one thing the instruction forbids.

**The diagnosis, stated before the third arm is run.** The removal did two
things, not one:

1. it stopped double-counting duration in the *time* profile — a participation
   rate already embeds prevalence and duration, so multiplying by the daily
   total gave long activities a standing advantage at every minute. This part
   is a defect and its removal is right whatever LP1 says;
2. it also destroyed the **within-group tie-break**, and that part was doing
   necessary work. HETUS publishes the diurnal table at *broad group* level:
   nine engine activities share `AC3_TR` — cooking, washing up, laundry,
   cleaning, DIY, gardening, childcare, adult care, shopping — and seven share
   `AC4-8A`. Inside a group the participation curve is identical, so
   participation-only picks near-uniformly, and the electrically heavy members
   (cooking, laundry) are diluted among alternatives that draw nothing
   (gardening, shopping, childcare away from home). That is why the evening
   fell: 22:00 went from 0.97× to 0.62× and 23:00 from 0.94× to 0.50×.

HETUS cannot break that tie — it does not publish within the group — so
*something* must, and the question is what.

**The third arm, and why it is the principled answer rather than a knob.**
Weight `participation(a,m) × remaining_budget(a)`. The budget is drawn around
the HETUS time-spent target and **decremented by every episode placed**, so:

* the *time* profile is HETUS's participation curve alone, unchanged from arm 2
  — the budget is flat in `m` within a day's scheduling pass;
* the *daily totals* remain the HETUS targets, as they already did;
* an activity **self-deprioritises as it is consumed**, which is ordinary
  proportional-fair scheduling and is the construction the static target could
  not provide. Arm 1's static weight kept an almost-spent activity at full
  weight, so it was chosen and then truncated to its remnant — which is the
  documented I-028 pathology, 45 episodes per person-day against the 20–25 a
  real diary records, a third of them one or two minutes long.

**Predicted direction, recorded before the run:** arm 3's MARD should fall
below arm 2's 0.2882, because the dilution mechanism above is removed. Whether
it falls below arm 1's 0.1720 is **not predicted and not a pass condition** —
arm 1 carries the double count, so it is not a target to beat.

**What happens on each outcome, decided in advance:**

* **arm 3 below arm 2** → arm 3 is delivered. The diagnosis is confirmed and
  the double count is still gone.
* **arm 3 at or above arm 2** → the diagnosis is wrong. Arm 3 is *still*
  delivered, because the structural argument for removing the double count and
  for decrementing weights does not depend on the score, and the result is
  recorded as an open failure against LP1 rather than reverted.
* **either way**, no activity timing, trigger rate or ownership prior is
  touched afterwards to move the number. If the delivered arm fits LP1 worse
  than the superseded one, that is an issue to raise, not a result to tune
  away.

**Why arm 1 is not simply kept.** It fits LP1 better and it is the arm with a
known defect in it. Choosing it on the score would be selecting a model because
it matches the one reference the project has sworn never to fit to — the exact
failure the exposure discipline exists to prevent. The superseded arm is kept as
a runnable ablation (`BehaviourSwitches.duration_weighted_timing`) so the
comparison stays reproducible.

**No fourth arm.** One diagnosis, one fix, one measurement, reported.

---

### D-079 — WP7 town scale-up: a new scope, C2, and a bounded window

Week 3, design 9.4. `assert_within_e1_scope` says "scale-up is gated by a
decision, not decided at a call site", so this is that decision.

**A new scope, not a raised ceiling.** `town_scaleup` is declared alongside
`slice`, `week2_slice` and `heldout_slice` rather than by editing any of them.
Every E1 and week-2 artefact was produced under a scope that forbade the town,
and that must stay true of those artefacts: the E1 gate report says the town
scale-up was out of scope for E1, and it was.

| | `slice` (E1) | `week2_slice` | `town_scaleup` |
| --- | --- | --- | --- |
| homes | 50 | 60 | **1,092** |
| people | ~140 | ~133 | **2,917** |
| coupling | C1 | C1 | **C2** |
| power flow | none | none | **solved per epoch** |

2,917 people against design 9.4's "3,000 people". The town is what the
synthesis produces from Cobh's SAPS; it is not padded to hit a round number.

**C2, and why it could not come earlier.** `NETWORK_CLAIM` has said since E1
that no voltage, loading or network-constraint claim may be made, because the
epoch barrier aggregates net power and solves nothing. Design 9.4's week-3
criterion is "feeder loading within physical limits", which is a claim about a
solved power flow. `baile_nua/network/lv.py` is that flow, and `solve_network`
turns C1 into C2. It is **off by default**, so every earlier artefact
reproduces under the mode it was produced in — the coupling mode is a property
of a run, not something a later week retrofits onto it.

**14 days, not 365, and the reason is measured.** The Day 6 projection
(`v1/evidence/e1_gate_report.json`) puts a full-town year at **15.07 run
hours** and **15.74 GB**, and a full-town decade at **157.4 GB** — **236 GB**
with U21's 1.5× margin — against the **77.8 GB** of free disk recorded in
`machine.json`. The decade does not fit on the disk. That is I-036, and it is a
measurement rather than a caution.

So the window is bounded and what it is for is stated:

* a **rate** measured on the real full town, so the week-3 criterion "measured
  scale within the Day 6 projection" is checked against a full-town run rather
  than against a slice scaled by 21.84×;
* the criteria that need the whole town and a solved flow — venue presence
  against person presence, feeder loading — answered on the whole town;
* the decade reported as a **requirement with a measured basis**, not as a run
  that happened.

**What is not claimed.** Voltage. The LV topology is `[A]` (A-49): the
connections per feeder, the feeder span and the service-drop length are
declared, because ESB Networks does not publish Cobh's actual LV circuits, and
voltage drop is a line integral along exactly those quantities. Transformer and
feeder **loading** is a ratio of powers and is insensitive to how connections
are arranged on a circuit — a 400 kVA substation serving 40 homes sits at the
same loading whether they are on one circuit or four — so loading is the claim
and `lv.assert_voltage_is_not_a_claim()` raises.

**What is sourced.** Every electrical parameter: cable resistance, reactance
and thermal rating and transformer rating, short-circuit and no-load losses all
come from pandapower's standard-type catalogue (NAYY 4x150 SE, NAYY 4x50 SE,
0.4 and 0.63 MVA 20/0.4 kV). Not one impedance is written in this build. The
voltage limits are EN 50160 and the ESB Networks Distribution Code: 230 V
±10%. The loading limit is 100% of a thermal rating, which is the definition of
a rating and not a threshold anyone here chose.

---

### D-080 — D-073 is scored on the comfort-taking-ON arm, and E2-1's verdict is derived rather than asserted

Two readings settled while re-issuing the E2 gate report. Neither is a new
choice; both are a decision about how an existing criterion is read, recorded
so it is not re-litigated.

**1. D-073 requires no comfort-off arm, and this is a reading of D-073's own
text rather than a concession.** The pre-registration's baseline table is
sourced in its own words to `heldout_u31.json`'s `gradient.on` and
`groups.*.on`; its condition 2 writes the pairing axis as *"the same 60
dwellings are simulated before and after"*, which is the fabric change. So all
four conditions are ON-arm quantities compared across two fabric
configurations. `work/u31_newpop_{before,after}/` carry only `on/` and the
criterion is still fully evaluable — verified by recomputing every figure in
`u31_newpop_prereg.json` from those two files alone, which reproduced them
exactly. **U31 PASSES as written**, and the verdict is restated unchanged.

The reason this needed deciding is that `heldout_u31.gradient_report(root)`
*does* require both an `off/` and an `on/` directory, which reads like a
missing arm. It is not: that function is the **comfort-taking ablation**
reporter and takes one root, while D-073 compares two. The word "arm" names
two different axes one layer apart. What the missing off arm does cost is
D-075's claimed decomposition of fabric from the entailed reference
re-centring — logged as I-085, not as a U31 failure.

**2. E2-1's verdict is now derived from the artefacts instead of being the
literal string `"FAIL"`.** The old code asserted the verdict it expected. That
was the right answer for the wrong reason: it would have kept saying FAIL after
a full-town decade landed. It now scores the criterion as the conjunction
design 9.2 writes — full town AND ten years AND invariants clean — against
`days >= 3650` on the newest full-town run and the ten-year run's own slice.
The verdict is **unchanged at FAIL**, now with the clause that fails named:
the full-town run is 14 of 3650 days and the decade that ran is on
`u23_mixed_age, 60 homes`. Invariants on the decade that ran are clean, so the
*clean* clause is met and the *coverage* clause is not. **Reported as a failure
with a measured basis, never as a deferral.**

**3. The three plausibility pass counts are rendered as three numbers.**
`n_pass_independent` = 6, `n_pass_against_a_calibration_input` = 2,
`n_pass_against_a_design_exposed_reference` = 1 now appear as three rows with
what each means, read from `plausibility.json` through `_need`, with the reason
they are never added stated beside them: their sum would assert nine
independent corroborations where there are six. The suite's own `n_pass` and
`n_pass_sourced` are printed as the suite's totals and explicitly not as a
substitute for the partition. The independent and calibration-exposed check
tables stay two tables, each labelled "Table 1 of 2" / "Table 2 of 2" with the
exposure class spelled out per row, so neither can be read as the whole.

Report rendering only. Nothing under `engine/`, `physics/`, `population/`,
`lifecourse/` or `behaviour/` was touched.

---

## D-090 — D23 is written with a provenance class on every field, not with the tag's hash

**Decision.** D23 is written for both finished runs. `code_git_sha`,
`code_tree_hash` and `code_version` are reconstructed from the nearest commit
at or before each run's start — **not** from `v1-engine-freeze` — and every
one of the sixteen declared fields carries a provenance class in
`parameters.field_provenance`, drawn from a closed set of seven:
`captured_at_run_time`, `derived_from_run_time_filesystem`,
`reconstructed_and_verified`, `reconstructed_from_git_history`,
`computed_at_export_time`, `assigned_by_exporter`, `not_established`.

**Why not the tag.** Because the tag is not the runs' code, and that is a fact
about this repository rather than a worry: model code was committed while both
runs were in flight (I-090). Writing the tag's tree hash would publish a
checksum that is false for the data beside it.

**Why the distinction is visible without opening a JSON column.** `run_id`
begins `D23-RECONSTRUCTED-`; `code_git_sha` ends `-reconstructed`;
`code_tree_hash` ends `-reconstructed-at-<sha7>`. A decorated identity string
is this project's existing idiom, not a new one: `manifest.git_sha` already
returns `<sha>-dirty`, `uncommitted-no-head` and `git-unavailable`.
`design_revision` is an int and cannot be decorated, which is exactly why
`field_provenance` is the authority and the suffixes are only the warning.
`test_d23_the_reconstructed_suffix_matches_the_provenance_class` asserts the
two never disagree.

**Two fields are better than reconstructed and say so.** `schema_version` and
`design_revision` are read from `schema/datasets.yaml` at the tag **and** that
file is byte-identical between each run's commit and the tag, so they are
classed `reconstructed_and_verified` — still not captured, and no longer
capable of being wrong.

**`outputs` covers the engine-streamed parts only** (D11, D13, D16, D18, D19)
plus `run_diagnostics.json`, hashed at export time. The exported parts under
the same roof were written by the export layer and not by the run, and their
bytes change on every re-export; including them would both misattribute them
and make the field stale immediately.

**`input_sources` is the declared corpus with each file's retrieval-time
SHA-256**, taken from each source's own manifest — a record made before the
run — with an explicit statement that *which* of them the run read was never
recorded.

---

## D-091 — a D21 biography is self-citing, and oddness in one is a result

**Decision.** `source_record_ids` is built from the sentences, not alongside
them. Each sentence is a `Sentence(text, ids)`; the renderer appends the ids in
square brackets to the sentence itself; `source_record_ids` is the sorted union.
So the Markdown can be checked against the column **in both directions**, and
`test_d21_the_column_and_the_narrative_cite_the_same_records` does exactly
that, while `test_d21_every_cited_record_id_resolves_to_a_row` resolves every
id to a primary key of the written part it names. A sentence with no ids is
refused at render time rather than written.

**`as_of` is the dates the record changes** — every `valid_from` / `valid_to`
of the person's D06 and D08 intervals, every D09 event date, bounded to the
run's span, plus the run's first and last day. A fixed calendar would mostly
produce identical rows; the change dates are where a biography can differ from
the one before it.

**Nothing is interpreted.** No comparison between people, no inference across
fields, no summary judgement, and a trait value is rendered as a number in the
schema's own name and scale — never as an adjective. Design 5.13 forbids
labelling a person, and "strongly environmentalist" would be the generator's
word rather than the record's. `cluster_label` is written null, which
`schema.validate` enforces because the field is declared `forbidden`.

**A biography that reads oddly is not smoothed.** The declared purpose is that
a reader can catch an implausible synthetic life no aggregate check would
notice, so a null field produces an absent sentence rather than a hedge, and an
inconsistent pair of fields is rendered plainly in one sentence. It worked on
the first row read: see I-095.

**D05 is the only source that cannot be missing.** D06, D08 and D09 each
contribute a section, and a section with no rows says so. The 14-day town run
forced this: it stepped no life course and has no D09 at all, and refusing to
write D21 for it would have turned "this run records no life events" into
"this dataset is missing".

---

## D-092 — D27 is a record only, every magnitude is fetched and cited, and three things stay assumed

**Decision.** D27 is written as OBS for both runs: three plans (flat,
day/night, three-band ToU), one assigned per household, labelled synthetic on
its face. **The engine does not read it and `control_mode` is unchanged**, and
that is asserted over the source tree rather than promised:
`test_d27_the_engine_cannot_read_the_tariff` fails if any module under
`engine/`, `physics/`, `devices/`, `behaviour/`, `activity/`, `observation/`,
`population/` or `lifecourse/` imports `baile_nua.export` at all, and
`test_d27_no_frozen_layer_names_the_rate_card` fails if one so much as names a
D27 field or a tariff code as a string.

**Seven sources were declared and fetched before use**, and every magnitude on
the card traces to one:

| Magnitude | Source | Retrieved |
| --- | --- | --- |
| flat and day/night unit rates, their urban standing charges | Electric Ireland Standard Electricity Price Plan, 1 May 2022 | 2026-10-12 |
| day / night / peak rates, the standing charge, and the only published band hours | Electric Ireland Home Electric+ Standard Smart Tariff, 1 Nov 2024 | 2026-10-12 |
| export payment: its existence, its published 16–25 c/kWh range, its regulated floor of zero | CRU202454 Clean Export Guarantee decision, 18 June 2024 | 2026-10-12 |
| standard domestic connection capacity (12 kVA) | ESB Networks Basis of Charges for Connection to the Distribution System | 2026-10-12 |
| the regulator's own decomposition of a domestic bill, as a shape check | CRU202389 Energy Monitoring Report for 2022 | 2026-10-12 |
| plan mix across the town | CSO HEBEU88, tariff type by urban/rural (2024) | 2026-10-12 |
| independent check on the unit-rate LEVEL | CSO TMEGB03, residential electricity prices by consumption band | 2026-10-12 |

All seven are `intended_use="reference"` and
`model_development_exposure="none"`, and the exposure is `none` in the
strongest available sense: the layers that could be exposed are structurally
unable to see the data.

**Five of the seven are PDFs, and the project's rule for a reference that is
not machine-readable applies** — the rule the DEAP manual's own
`substitute_flag` states. Each figure is transcribed into
`export/tariffs.TARIFF_RATES` with its page and the exact published wording,
and `test_d27_every_sourced_rate_is_in_its_cited_document` searches for that
wording in the fetched bytes. The comparison strips all whitespace, because the
published PDFs' own text layer carries stray spaces inside numbers — the
NightSaver standing charge extracts as `€327 .04`.

**Two derivations are stated rather than published.** The standing charge is
the published annual urban charge over 365 (a supplier's annual figure is a
365-day figure and 2022 is not a leap year). The export rate is the **midpoint**
of the CRU's published range, with both ends and the regulated floor carried in
`rate_schedule` so a reader can take a different point from the same evidence.
`max_import_kw` converts a published kVA at unity power factor, stated on the
dataset.

**Three things stay assumed**, each with a flag and a search record in the
sweep's own `AssumptionFlag` form:

* **A-92** the day/night plan's band hours. The 2022 schedule publishes rates
  and no hours; the window is carried from the smart tariff's published
  `Night Hours: 23:00 – 08:00`. PxStat returns zero hits for `night rate`,
  `night saver` and `day/night` over 13,086 tables, and a test asserts that
  negative result still holds, because a meter switching time is a term of a
  connection and not a statistic.
* **A-97** the three-band plan's vintage (I-094).
* **A-96** `flex_contract_terms` and `trial_arm`, written null because no
  aggregator contract and no recruitment randomisation exist in this run.

**Five flags that stood before the fetch are kept with verdict `RETIRED`** and
the source that closed each (A-90 rates, A-91 mix, A-93 standing charge, A-94
export rate, A-95 connection capacity), so the record shows what was assumed
and what closed it rather than only the present state. A-91's retirement is the
I-040 lesson paying off: a search over the declared PxStat catalogue found
HEBEU88 where an earlier note would have recorded a conclusion.

**The plan mix is the published urban share, renormalised.** HEBEU88's urban
row gives Standard 46%, Day/Night 21%, Smart 12%, Other NEC suppressed,
unknown 20%. The three known shares are renormalised to 0.582 / 0.266 / 0.152
and the suppressed and unknown shares are reported on the dataset rather than
reassigned: a non-answer is not evidence for a tariff.

**The supplier name is synthetic even though the rates are real.** The plan
mix, the per-premises assignment and the premises themselves are not that
supplier's, so presenting the rows as its customer records would be a claim
about the company. The rate source is cited field by field instead.

**Plan assignment is counter-based** on a stream declared in `export/`
(`EXPORT_TARIFF_PLAN_STREAM = 20001`) using `rng.splitmix64` and
`rng.stable_entity_id` — the same Philox construction as
`SeedTree.generator`, not a second RNG. `rng.Stream` is inside the freeze and
appending a member to it would invalidate every checkpoint, so the id is
declared here and
`test_d27_the_export_stream_cannot_collide_with_a_declared_one` asserts it is
disjoint from, and above, every declared `Stream` value.

**`max_export_kw` is read off the run, not assumed**: it is the installed PV
inverter rating from the frozen DER stock, and 0.0 where the premises has no
PV. The notification process is not modelled, so the notified capacity is
taken to equal what is installed — stated as a conversion.
### D-081 — BN-1: D17's observable view, and the two things it refuses to publish

**Decision.** `D17_aggregate` is declared in `datasets.yaml` as an OBS dataset
with nine fields and written into the observable package beside D18 and D19.
D17 itself stays **GT** and keeps every field it had; the view is in addition
to it, not instead of it. The view carries exactly the three things BN-1 names
and nothing else:

| what | fields | where the value comes from |
| --- | --- | --- |
| the connection register | `premises_id`, `substation_ref`, `feeder_ref` | `TownNetwork.assignment`, which is how the network was built |
| the asset register's ratings | `transformer_rated_kva`, `feeder_rated_a` | pandapower's standard types: the transformer's `sn_mva` and the feeder cable's `max_i_ka`. Catalogue values, so neither is a number written in this build |
| the metering | `p_kw_measured`, `q_kvar_measured` | the same epoch powers D17 records, projected |

plus `record_kind` (which of the operator's three records a row is) and `ts`.

**Why the view is a projection and not a second computation.** Every measured
power in it equals the D17 row for the same element and the same epoch,
exactly — asserted by
`test_every_measured_power_equals_the_ground_truth_row_it_views`. A view that
recomputed its own numbers could disagree with the truth it is a view of and
nothing downstream would notice. The `p_kw` sign convention — positive for
import at **every** element kind — is inherited rather than restated, which is
the error `lv.d17_rows` already made once at the transformer's LV terminal.

**The two refusals, and why each one is a refusal rather than an omission.**

*No voltage, anywhere in the view.* `lv.assert_voltage_is_not_a_claim()` raises
unconditionally. The LV topology is `[A]`, registered as A-49: ESB Networks
does not publish Cobh's circuits, so the connections per feeder (24), the
feeder span (300 m) and the service drop (15 m) are declared — and voltage drop
is a line integral along exactly those three quantities. D17 still records the
computed voltage, because the schema has the field and hiding a computed
quantity from ground truth is not honesty. Putting it in an **observable**
dataset is different in kind: it would present a declared assumption to a model
developer as a measurement of something real.

*No per-element loading.* Loading is GT and stays GT. The ratings and the
measurements are both published because BN-1 names both; their **ratio** is
not. A DSO holding both can of course form it — which is inherent in BN-1's own
request and is why the refusal is stated as "the dataset does not publish it"
rather than as "it cannot be derived".

*No per-connection power.* A register row names a premises and carries no
measurement; a measurement row names an element and never a premises. An
aggregate view that carried per-customer power would not be aggregate.
Asserted by `test_the_view_publishes_no_per_connection_power`.

**Field naming, and why it is not `feeder_id`.** `feeder_id` is a GT field of
D01, and `test_gt_and_obs_field_names_overlap_only_on_declared_join_keys`
fails on any GT/OBS name collision outside `SHARED_JOIN_KEYS`. The sanctioned
remedies are to add the name to that list or to rename one side. Adding it
would widen the leakage exemption, so the side that was renamed is the new
one: `feeder_ref` and `substation_ref`, which also say what they are — the
operator's own asset-register references. Only `ts` and `premises_id` are used
from `SHARED_JOIN_KEYS`, both of which were already there.

**No `gt_counterpart` is declared, and the dataset says why.** 6.5's too-good
test bounds an OBS field's agreement with its GT counterpart by a calibrated
error model's upper bound. E1 renders no instrument error for **network**
metering — D18 is the only dataset with a device error model — so a measurement
here equals the quantity D17 records, there is no calibrated model to bound
agreement against, and declaring a counterpart would invite a test to bound
agreement against nothing. That is stated in the dataset's `notes` and
asserted by `test_the_view_declares_no_gt_counterpart_and_says_why`.

**The register is written once per run, not once per epoch.** The LV topology
is built once and does not change within a run, so repeating 1,092 membership
rows on every epoch would publish the same register 35,040 times a town-year.

**What was NOT added.** No `n_premises_on_element` aggregate, no quality or
provenance columns, no outage column — BN-1 names none of them, and the
instruction was to add only what it names.

---

# D-100 to D-122 — the 2015–2026 historical replay (PLAYBOOK v3, approved 2026-10-14)

The 2022–2031 synthetic decade is retired and replaced by a real-data chained
replay of **1 Jan 2015 → 30 Sep 2026** (4,291 days, 3 leap days), followed by a
nightly live forward mode. Approved against `PLAYBOOK_v3.md`; scope additions R
and S appended as `PLAYBOOK_v3.1.md`.

## The governing decision: outcomes emerge

Baile Nua becomes a **training set in which comfort, bills and energy poverty
are computed from physics and household finances, never scripted.** Occupants
persist from 2015 through the chain, so a household has a history. A home with
PV, a heat pump and good fabric must feel the 2022 crisis less **because its
bill is smaller**, not because a rule says so.

Two standing rules follow, and they are in the playbook as Rules 10 and 11:

* **Outcomes are never imposed.** No comfort level, bill, poverty rate or
  crisis response is written as a target; each is compared against a source
  only at a validation gate.
* **Calibrated totals, endogenous selection.** A propensity model may decide
  *who* adopts a technology; only the sourced series decides *how many*.
  Implemented as a ranked allocation: score propensity from income, tenure, BER
  and the household's own bill burden, take the top *N* from the sourced series.

## Settled decisions

**D-100 (was D1) — CER/ISSDA is not used.** It is licensed and the brief
forbids it (`sources/SOURCES.md:25`, and it is listed as deliberately not
used). Validation uses ESB Networks Standard Load Profiles, EirGrid demand
shape and CSO counts instead.

**D-101 (D2) — D18 is scoped, never dropped.** Kept for homes enrolled with
PARA//EL, from their enrolment date only. At the agreed 30% enrolment that is
~9.5 GB against a 66 GB base, ~76 GB total, inside the 110 GiB free. Sized from
the measured 27.1 kB per home-day (estate-year, 506.4 MB over 18,250
home-days), 1-minute basis as an upper bound.

**D-102 (D3) — COVID deaths are reported, not claimed.** The behaviour is
modelled; the deaths are a labelled Poisson draw beside the cited national
age-specific rate. Every IFR, seroprevalence and national death figure is
fetched and cited **before** it is written. The arithmetic is not computed until
I-106 is fixed: census-correct, the 85+ band goes from 10 people to about 34 and
the expectation rises roughly 2.5 to 3 times.

**D-103 (D4) — Abbeylands construction loads and LEC/MV are a separate
proposal**, in the playbook backlog, flagged **needed before live mode reaches
2027**. Venues draw no electrical load today and MV is a slack `ext_grid` by
explicit design decision (`network/lv.py:254`).

**D-104 (D5) — geometry stays abstract.** Logged as I-107: the BNIT 3D map
holds dwelling positions while all 206 D01 features are `POINT EMPTY`. A future
alignment project exports map positions keyed to D01/D02 ids rather than
fabricating polygons, which `export/structural.py` refuses on principle.

**D-105 (D6) — transport goes to BNIT**, per R02. Mode shift is an
intervention.

**D-106 (D7) — acquire Census 2016 SAPS and age forward** to 1 Jan 2015.
Back-projecting the 2022 base is demographically backwards.

**D-107 (D8) — FX-BN-05 and T-OBS are FLEXUS obligations, not Baile Nua's.**
FX-BN-05 requires one town-year under 24 h wall time; the replay measures
10.44 h/year. T-OBS requires ten years of OBS; the replay supplies 11.75. The
FLEXUS spec is updated to "the 2015–2026 replay" separately.

**D-108 (D9) — acquire ESB Networks SLPs per year 2015–2025** and validate per
year, rather than against 2022 alone.

**D-109 (D10) — the DST defect is logged now as I-105.** The simulation grid is
UTC (`MINUTES_PER_DAY = 1440`, `stream_writer.py:195`) while
`export/tariffs.py:344` declares `BAND_CLOCK` as the Europe/Dublin local clock,
so day and night rates are an hour out for roughly seven months of every
simulated year — including the published estate-year.

**D-110 (D11) — `sim_day` runs continuously 0 → 4,290.** The `SeedTree` is
keyed on (seed, entity, `sim_day`), so a year restarting at 0 would re-draw
2015's random numbers. Adding the year to the seed entity was rejected: it
would make every year's draws differ from the equivalent day of a single-pass
run, defeating the chain.

**D-111 (D12) — enrolment.** PARA//EL/EdgeWare enrolment from **1 Jan 2021,
ramping to 30% of dwellings by 30 Sep 2026**, skewed toward homes with PV, heat
pumps or EVs and toward estates with an energy co-op. **A-numbered programme
assumption**; no sourced enrolment series exists or can exist, and the failed
search is recorded with the A-number.

**D-112 (D13) — Part V.** Cluain Ard (2019): **10% social**. Belgard (2024):
**20% — 10% social plus 10% affordable/cost-rental**, A-numbered on the
assumption that the land was purchased after 1 Aug 2021 under the Affordable
Housing Act 2021.

**D-113 (D14) — crisis-response persistence only if the evidence supports it.**
If the studies are equivocal, no persistence is modelled and that is stated.

**D-114 (D15) — estate sizes and mix** derive from CSO new dwelling completions
(NDA) for the Cobh / Cork County area in 2019 and 2024, scaled to the town,
with dwelling-type mix from the same series. Any residual is A-numbered.

**D-115 (D16) — Phase 16 is split.** 16a (PARA//EL observation) needs no LEC or
FLEXUS build and is gated on the chained run alone, per FX-BN-04. 16b
(flexibility services) stays gated on both builds.

**D-116 (D17) — measure the write-flush overlap before building it.** Writes
are ~49% of runtime (50.7 s against 52.3 s on town14), but the run was measured
I/O bound on 12 Oct ("write time overtook sim time, 119.4 s against 104.4 s"),
so a background flush may buy nothing. One instrumented month, inline against
backgrounded, before any work.

**D-117 (D18) — the heating-response elasticity.** Acquire the SEAI/CSO/ESRI
studies in Phase 0 and report the sourced Irish elasticity at G0. **If no Irish
estimate exists, use an A-numbered value from the closest cited international
evidence** (UK/EU energy-crisis studies) with a **low/central/high sensitivity
range run as variants. The response is never dropped altogether.**

**D-118 (D19) — both energy-poverty measures, never averaged, neither
primary.** The ESRI expenditure measure (energy spend above 10% of disposable
income) and the CSO SILC subjective measure ("unable to keep home adequately
warm") disagree by construction: a well-insulated low-income home can pass one
and fail the other. Validation scores against SILC, because that is what SILC
publishes.

**D-119 (D20) — income tracks the life course.** Household income follows
life-course employment events, anchored to the SILC distribution by year.
Redrawing annually was rejected: it would destroy the cohort continuity the
emergent-outcomes framing exists to create.

**D-120 (D21) — the NILM error model is A-numbered**, built from published NILM
benchmark accuracy — per-appliance F1, precision and recall on public datasets
such as REDD, UK-DALE and REFIT — cited, and **worse for low-power and
multi-state appliances**. Scoring against GT appliance truth is labelled
**indicative**.

**D-121 (D22) — consent tiers** come from PARA//EL's own sharing levels: local
only / aggregate to EdgeWare / flexibility-level sharing. A-numbered split
among enrolled homes: **15% local only, 35% aggregate, 50% flexibility-level**,
skewed to flexibility-level for PV, heat-pump and EV homes. The tiers are named
in the Phase 19 view specification so its tests assert against them.

**D-122 — scope additions R and S** are approved and appended as
`PLAYBOOK_v3.1.md`: per-year upload to a private Backblaze B2 bucket (R), and a
per-year estate timeline JSON export for the BNIT map's year slider (S).

**D-123 — SEAI grant data for 2015–2018: a declared fallback.** The National
Retrofit Plan Full Year Reports begin at **2019**, and a search result claims
SEAI publishes "full datasets for all schemes from 2015 onwards" but that
download page has not been located. If scheme-level data for 2015–2018 does not
exist:

* **fall back to SEAI annual report totals by scheme and by year**, and
* **flag the 2015–2018 segment as COARSER than 2019–2026** on the dataset
  itself, not only in a note — the uptake series then carries a declared
  granularity break at 2019, in the same way the SILC deprivation series carries
  a definitional break at 2020 (D-118).

Consequence to state plainly: Phase 11's ranked allocation (Rule 11) needs a
**count per scheme per year** to hold the national total exactly. An annual
report total still supplies that count, so the allocation mechanism is
unaffected; what is lost is the **measure mix within a scheme** for those four
years, which becomes an A-numbered split carried from the earliest year where
the mix is published. Recorded rather than discovered later.

**G0 is held** until the SEAI downloads land. Everything else in §3 of the
playbook is either acquired with a manifest or dropped with a written reason.

**D-124 — the chain needs no new state capture, and Phase 17 shrinks.** I had
reported that `Checkpoint.person_state` was "carried and ignored", the I-081
shape. **That was wrong and is corrected here.** `run.py:1196` writes the
checkpoint with `household_state=` only, so `person_state`, `building_state`
and `asset_state` are declared on the dataclass and **never populated**.

`HouseholdState` documents itself as "**What carries from one day to the next
for one household**" and carries `rc` zone temperatures, `battery_soc`,
`ev_soc`, `failed_appliances` and `dhw_tank_c`. The restore-coverage test
`test_every_key_the_checkpoint_writes_is_read_back_by_restore` guarantees
`as_dict` and `restore` stay in step — it is the structural half of I-081 and it
already exists.

**The consequence for chaining:** a year boundary is just another day boundary.
Nothing carries person-level activity, location or routine across a *day*
boundary either — activities are drawn per day from the seed tree, which is
deterministic on (seed, entity, `sim_day`) — so none of it needs carrying across
a *year* boundary. The user's list of carried state (zone temperatures, tanks,
battery and EV SOC, appliances mid-cycle) is therefore satisfied by
`HouseholdState` as it stands, except "appliances mid-cycle", which does not
exist as state because the appliance model resolves within a day.

Phase 17 therefore reduces to: (a) `sim_day` continuous 0 → 4,290 so the seed
tree does not repeat (D-110), (b) loading the previous year's final checkpoint
at the start of the next, and (c) a calendar and weather that span years
(Phase 2). Re-estimated at **~6 elapsed hours, not 13.5**.

**D-125 — B2 upload is blocked and not worked around.** No B2 credential exists
in the keychain (searched by service name; no values read), and scope R's own
pre-flight requires the user to confirm the old credentials were rotated. Rule 1
stops for anything needing credentials. Per-year packages will be built,
checked and verified locally and left **unuploaded**; no year is marked
delivered on the strength of a local package.

**D-126 — Rehearsal A PASSED; the chain is sound.** Re-ran the checkpoint
replay against the freeze-2.1 checkpoints, because the on-disk artefact was
dated 12 Oct 00:14 while the checkpoints were written 13 Oct 16:28 — the exact
I-081 trap the project's own test docstring describes ("the replay artefact had
been measured eleven hours before the tank existed and was quoted unchanged
afterwards").

Result: **100 home-days over 84 days, 0 mismatches, worst absolute difference
0.0, `exact_replay: True`**, artefact re-dated 14 Oct 15:39. A day restored
from a checkpoint reproduces exactly, so `HouseholdState` carries everything a
boundary needs and the chained run needs no new state capture (D-124).

**D-127 — public holidays 2015-2026 derived and triple-verified.** No
acquisition gap. Rules from the WRC statutory list (`sources/wrc/`, acquired and
manifested); dates derived and checked against three independent anchors — the
sourced in-code 2022 table, the WRC 2026 list, and ten published Easter
Mondays — all three MATCH. Written to
`sources/derived/irish_public_holidays_2015_2026.csv` with its derivation and
verification recorded in the manifest.

**Correction, 2026-10-15 (I-114).** That last sentence was wrong twice over. No
manifest was written at the time, and the file was afterwards extended
backwards to 2014 for the Dec-2014 warm-up, so the path named here —
`…_2015_2026.csv` — is not the file the engine reads. The real file is
`sources/derived/irish_public_holidays_2014_2026.csv` and its manifest now
exists. Found by agent C's provenance pass, which resolved every cited source
against the manifests and returned this as the only UNSOURCED cell in 32
datasets; no test could have caught it, because nothing tests that a manifest
exists.

**D-128 — STOPPED on school terms, per rule 1.** Not rule-derivable; published
per year in Department of Education circulars; `gov.ie` and `circulars.gov.ie`
both return **HTTP 403** to programmatic fetch, and the standing instruction
forbids spoofing a user agent. `data.gov.ie` has **0** school-holiday datasets.
The only school-term data on disk is `SCHOOL_TERMS_2022`.

This is "a missing source with no sourced fallback", which rule 1 reserves for
the user. Three options were put to them: (a) manual download, recommended;
(b) derive a calendar anchored to the sourced holidays and A-number it;
(c) carry 2022's terms to all twelve years. **Option (b) and (c) are NOT taken
unilaterally** — either would make a whole calendar dimension an assumption
across twelve years, which is the class of decision rule 1 holds back.
Everything not depending on school terms continues.

**D-129 — the circular-sourced school calendar is used for ALL years, 2022
included.** The alternative was to keep `SCHOOL_TERMS_2022` for 2022 so every
existing artefact reproduced bit-for-bit, and use derived data only for other
years. Rejected: it would make 2022 the one year whose school calendar came
from a different and demonstrably wrong source (I-109, five days), and a replay
whose claim is that the dates are real cannot carry a hand-built year in the
middle. The cost is that 2022 output changes and some suite assertions may
move; that is classified, not absorbed.

**D-130 — `is_school_day` is retained and two sector fields are added.**
`CalendarDay` keeps `is_school_day` so the ~20 existing call sites and tests
continue to work, and gains `is_school_day_primary` and
`is_school_day_post_primary`. `is_school_day` is defined as **primary**, which
is the sector the activity engine's school-age population mostly belongs to;
the post-primary field is available where the distinction matters. Chosen over
"either sector" because an OR would mark the primary February Monday-to-
Wednesday as a school day for primary pupils, which is what I-109 is about.

**D-131 — close-date semantics in the circulars are read in two forms.** The DoE
circulars state mid-terms **inclusively** ("close *from* Monday 27th October
*to* Friday 31st October inclusive") but state Christmas, Easter and summer as a
**final day plus a reopening day** ("close *on* Friday 19th December 2014, which
will be the final day of the school term"; "re-open *on* Monday 5th January
2015"). Read naively as inclusive, the second form loses one school day at the
start of every Christmas, Easter and summer break. `_closed_days` therefore
treats the two forms differently and says so. Verified: 19 Dec 2014 is a school
day, 22 Dec is not; 6 Jan 2022 and 25 Apr 2022 are school days, 5 Jan and
19-22 Apr are not.

**D-132 — a calendar request before 2014-09-01 is refused, not guessed.** The
school-break table starts at school year 2014/15, so earlier dates have no
rows covering them and every weekday would read as a school day. `build_calendar`
raises `CalendarSourceMissing` rather than return a silently wrong calendar.
The replay's warm-up starts 2014-12-01, inside coverage.

**D-133 — one master seed for the whole chain; a per-year seed is recorded but
NOT fed to the model.** Instruction 1d asked for "seed per year derived
deterministically from a master seed and recorded". Deriving a *different* seed
per year and using it would break the thing the chain exists for: the
population comes from `synthesise_t0(master_seed)`, so a new seed each year
would give a **different town each year** and destroy the cohort continuity
that the whole emergent-outcomes framing (§1.1) depends on. Per-day variation
already comes from the seed tree, which is keyed on
(seed, entity, **sim_day**) — which is exactly why `sim_day` must run
continuously 0..4,290 (D-110).

So: **one master seed**, used throughout and recorded in every segment's
manifest; and a per-year **seed-of-record** derived as
`sha256(f"{master_seed}:{year}")[:16]`, written into the manifest for
provenance and **never passed to the model**. The manifest says which is which,
so no later reader can mistake the recorded value for an input.

**D-134 — `was_workday` is None on the first day of each chained segment.**
`run.py` looked up yesterday's day type as `self.calendar[day.sim_day - 1]`,
an ABSOLUTE index. Two bugs: in a chained segment it indexes past the end of
the list, and on `sim_day == 0` the guard `if day.sim_day > 0` was the only
thing preventing `calendar[-1]` from silently using **the last day of the year**
as the day before 1 January. The lookup is now relative to the runner's
`sim_day_origin`.

On a segment's first day yesterday belongs to the previous segment, whose
calendar this runner does not hold, so the value is `None` — which is what the
first day of any run has always used. That is **12 days out of 4,322** (0.28%),
each a 1 January, and it affects only the "was yesterday a workday" input to
activity generation. Carrying the previous segment's trailing calendar day
through would fix it, but it also needs that day's weather row, and the extra
plumbing is more risk than 0.28% of one input is worth. Recorded rather than
hidden.

**D-135 — resume is per SEGMENT, and an incomplete segment is renamed aside.**
A killed segment is re-run from the previous segment's final checkpoint rather
than from its own latest checkpoint. Two reasons, and the first is correctness:
`StreamWriter` numbers its Parquet parts from zero, so resuming mid-segment
into an existing package directory would leave the dead attempt's
higher-numbered parts in place and the package would silently hold two
attempts. The decade scheduler guarded this the same way — rename aside, never
remove — and the supervisor now does too, logging each rename to
`retries.log`.

The cost is stated: a crash late in a year loses that year's compute, up to
~10.4 h. Mid-segment resume is possible — `restore` works from any checkpoint,
and the calendar can start on any date — but it needs the partial package kept
and the parts renumbered across two directories, which is more machinery than
the saving is worth for a run with twelve boundaries. Nothing is lost
permanently: every attempt's checkpoints are kept.

**D-136 — Phase 2 suite classification: 2 failed / 1,071 passed / 35 skipped
(1:27:22). Exactly one test moved, and it is not a data change.**

| test | verdict |
|---|---|
| `test_sleep_timing::test_a_non_worker_wakes_later_without_going_to_bed_later` | **I-101, unchanged.** Identical numbers to every previous run (470.0 vs 443.0 + 30). Pre-dates the freeze; accepted. |
| `test_datasets_catalogue::test_the_document_on_disk_is_what_the_generator_produces` | **catalogue staleness, attributable in full.** |

The catalogue diff is **12 lines and contains no dataset row, row count, schema
or status change**: the `Generated` timestamp, the `Git HEAD` line moving from
`77316d5` to the Phase 2 commit `34c72c5`, three file-pattern counts in a
directory listing (because `v1/evidence/small_area_areas_itm2157.csv` and new
`sources/` files were added since the last render), and the footer repeating the
timestamp and HEAD. Fixed by regenerating and committing.

**Nothing moved because of I-109 or I-110**, and the reason matters: the
committed `v1/` package was produced **before** Phase 2, and the catalogue reads
the package on disk rather than re-simulating. So the five wrong school days and
the inverted DST flag are still present in the shipped artefacts and will only
be corrected when `v1/` is next rebuilt. The consequence I flagged is real but
**deferred, not absent** — which is exactly why those artefacts are being marked
superseded rather than left to look current.

**D-137 — D12 (trips) DEFERRED, not skipped silently.** `activity/engine.py:1167`
computes trips "for D12 trips and for the EV state of charge", but nothing
retains them: `DayResult` has no trips field and `StreamWriter` has no D12
buffer. Retaining them is the same shape as adding D10 — a field on
`DayResult`, a writer buffer, schema conformance and tests — comfortably over
the 2-hour bar the user set, so it is deferred by their own condition.

**EV state of charge is unaffected.** The trips exist transiently within the
day and already drive SoC; what is missing is only the persisted row. Nothing
in the replay is wrong because of this; D12 is simply absent.

**D-138 — the per-year export records failures rather than raising.** A dataset
whose inputs a configuration never produced is a finding, not a crash. D29 and
D30 need a D11 part to derive `occupied_weekday_hours` and refuse to default it
("defaulting it would hand the survey generator a flat truth"); D03, D09 and
D20 need a life-course artefact. Raising would lose a ten-hour year over one
dataset. Each year's `DONE.json` carries `export_written` and `export_failed`
so nothing goes missing quietly.

**D-139 — the agent tracker is `status/AGENTS.md`, not `status/PROGRESS.md`.**
The brief asked for one line per agent in `PROGRESS.md`, but that file is
machine-written: `replay_supervisor.write_progress` rewrites it in full every
600 s, so any hand-added line would survive at most ten minutes and would then
vanish without trace — worse than not writing it. The agent table lives in a
sibling file the supervisor does not own, and `AGENTS.md` names `PROGRESS.md`
as its companion so neither is read alone.

**D-140 — a worktree gets the gitignored source data as a symlink farm of
individual files, not as a directory symlink.** The 2.1 GB of acquired source
data is gitignored, so a fresh worktree checks out only 76 tracked files under
`sources/` (manifests, `.gitkeep`, `SOURCES.md`) and every acquisition-dependent
test fails for want of data that is present on the machine.

My first attempt replaced the whole `sources/` directory with one symlink. That
works for reading and is quietly destructive for committing: git sees a symlink
where it expects a tree, reports all 1,480 lines of tracked manifest under
`sources/` as deleted, and `git add -A` commits the deletion of the entire
source register. I did exactly that and had to amend the commit, which is the
only reason it was caught before four agents did the same thing.

So the tracked tree stays real and only the 100 files git does NOT track are
symlinked in, each at its own path. Reading is unchanged — every path resolves
as before — and `git status` is clean. All four agents were told to stage files
explicitly and never to use `git add -A`. The lesson generalises: a symlink
standing in for a directory that contains tracked files is a trap, because the
breakage shows up only at commit time and looks like an intended deletion.
---

# B-D-001 to B-D-003 — the Obsidian vault at `vault/`

**B-D-001 — `scripts/build_vault.py` regenerates `vault/` from the repository
and owns nothing else.** One note per entity — 32 datasets, 80 source
manifests, 64 assumptions, 132 decisions, 110 issues, 149 modules, 21 phases,
21 gates, 3 estates, 18 events, 7 roles, 3 privacy tiers, 5 named obligations,
12 years and 4 index notes — each with YAML frontmatter (`type`, `id`,
`status`, `tags`) and `[[wikilinks]]` to what it touches, so the graph view is
the project's own dependency graph rather than a drawing of one. Writes land
only under `vault/`; every other path is opened read-only. A re-run deletes
only files already in `vault/` that carry the script's own `generated_by`
stamp, and leaves anything else alone, so a hand-written note in the vault
survives. Iteration is sorted and every value derived, so re-running over
unchanged inputs produces byte-identical files — verified by rebuilding twice
and comparing digests.

**B-D-002 — no issue BODY reaches the vault; only the register row, the
heading and the status token.** `docs/ISSUES.md` quotes production
credentials and a production host (I-001, I-002) in its evidence sections, so
copying those bodies into a vault that is meant to be opened and browsed would
re-publish them. What crosses instead is the summary-table cells, the heading
title, the status word and the set of identifiers the body names — which is
enough to link an issue to the datasets, modules, phases and decisions it
affects, and carries no prose that could quote a secret. Everything that does
cross, from any file, passes the release gate's own secret patterns
(`scripts/replay_supervisor.py:139`) plus e-mail and opaque-token patterns, and
the finished vault is re-scanned before the script exits: a hit is a non-zero
exit, not a warning. Module notes carry a path and the first line of the
docstring and nothing else — read with `ast`, so no module is imported and no
code body is reproduced.

**B-D-003 — three ambiguities in the inputs are resolved by derivation, and
the derivation is recorded on the note rather than hidden.**

* *Join direction.* `datasets.yaml` declares keys but not which dataset owns
  one. A field carrying an `id_prefix` declares its entity (`person_id` → D05,
  `household_id` → D06, `building_id` → D02, `asset_id` → D04); otherwise a
  dataset whose first field is the key and whose `grain` names the same entity
  declares it (`feature_id` → D01, `signature_id` → D22, `participant_id` →
  D25, `device_id` → D18, `event_id` → D09, `edge_id` → D07, `run_id` → D23,
  `series_id` → D31). `premises_id` resists both and is taken from Appendix B's
  prose — "a `building_id`, which is metered as a `premises_id`" — so D02 owns
  it. Upstream and downstream then fall out: upstream declares a key you carry,
  downstream carries a key you declare. Appendix B's diagram is read for its
  key list, not parsed as a graph; the per-dataset "Joins" sections are carried
  separately as what is observed on disk.
* *`Dnn` in the playbook.* PLAYBOOK v3.1 numbers its own decisions D1–D22 and
  writes them bold — "(**D13**)" — which collides with dataset ids D11–D22.
  A bold `Dnn` inside the playbook is resolved through DECISIONS.md's own
  "(was D1)" / "(D19)" aliases to the `D-1nn` that superseded it, and removed
  before dataset ids are harvested. Without this, Phase 9 claimed to touch D13
  and D15 when it was citing D-112 and D-114.
* *Two assumption registers.* `validation/assumption_sweep.ASSUMPTION_FLAGS`
  holds A-01 to A-51 and `export/tariffs.TARIFF_ASSUMPTIONS` holds A-90 to
  A-97; DECISIONS.md cites both, so both are loaded and each note names the
  register it came from. The registers are the authority on how many
  assumptions exist, as the sweep says of itself, rather than a count of `[A]`
  in the documents.

**What the vault records as absent rather than filling in.**
`PLAYBOOK_v3.1.md` is untracked, so it is not in this worktree; the builder
searches the repository root, `docs/`, and finally the live tree's root, and
`MOC_Run` records which copy was read. `work/replay_2015_2026/` does not exist
in this worktree, and the live one belongs to a running process, so every year
2015–2026 is marked **pending** with its planned days, hours and release offset
from §6 and no invented row counts; `--replay-root` points the builder at a
run directory once one is safe to read. Events are the playbook's own phrases,
each verified present in the file before its note is written and flagged
`unverified` if not found. The playbook publishes no enumerated privacy-tier
list, so the tiers in the vault are the schema's three access classes — the
mechanical ones, enforced by the generated leakage test — with LC-AMI-01,
LC-AMI-03, FX-BN-04, FX-BN-05 and T-OBS beside them as the named obligations
the role views are tested against.

**D-141 — the replay was restarted ~1 h into 2015 to fix presence retention,
with the user's explicit approval.** `run_day`'s `collect_presence` flag is
gated on `day.sim_day < collect_presence_days`, the **global** sim_day, against
a default of 14. Every delivered segment starts at offset 31 or later, so
presence was collected on no day of any delivered year and D29/D30 — which glob
D11 for `location_kind == "building"` and raise when there is none — would have
failed in all twelve. Agent D found it; all three code sites were verified.

The supervisor now passes `collect_presence_days = seg["sim_day_offset"] + 14`,
keeping the original intent of the first fortnight of each segment.

Safe to change mid-run because `collect_presence` is a **retention** flag:
`engine/run.py:500-511` records that `_venue_for` is addressed through the
counter-based seed tree on its own (person, day, activity) key, so resolving it
every day "advances no other stream and changes no other draw". Row volume
changes; no draw does.

Restarting cost the hour of 2015 already computed. Waiting for the 2015/2016
boundary would have shipped 2015 without D11 presence, D29 and D30, and
recovering it later needs a **9.7 h re-run**, because presence rows are
engine-streamed and no export pass can back-fill them. That asymmetry — one
hour now against ten hours later — is the whole of the argument.

Confirmed clean: `digests()` covers only `scripts/baile_nua/**`, so the
engine digest stayed `7f4a65594ec78de8…`, the warm-up's `DONE.json` validated
and the segment was skipped; the 2015 partial was renamed aside to
`2015.partial.1792018532` and never deleted (D-135); and the rebuild reproduced
the same town, slice and network figures — 1,092 homes, 2,917 people, 89
venues, 1,092 connections, 53 substations, 2,238 buses.

**Confirmed empirically at 00:48**, which matters because the whole decision
rested on a code reading. The sim_day 59 flush wrote
`work/replay_2015_2026/2015/pkg/ground_truth/D11_part000.parquet`, 6.23 MB,
**1,149,976 rows**, of which **879,418 carry `location_kind == "building"`** —
the rows D29 and D30 glob for and raise without. Before the restart that count
would have been zero for every one of the twelve delivered years. The
distribution is sane too: 879,418 building, 164,340 in_transit, 106,218 venue.
For scale, town14's 14 days wrote 1,130,417 rows, so a comparable fortnight at
town scope is the right order.

**D-142 — engine-touching branches are held out of the main checkout while the
replay runs.** `digests()` is computed once at startup and stamped into every
segment's `DONE.json`, so editing anything under `scripts/baile_nua/**` mid-run
would make those stamps claim a digest the tree no longer has. `agent-B-phase2`
was merged because it is digest-neutral — verified, not assumed, by recomputing
the digest after the merge. `fix-i111-d15-dst` and `agent-D-phase2` and
`agent-A-phase2` all touch `baile_nua` and wait for the next restart, after a
full suite in the main checkout. The cost of waiting is bounded because both
catch-ups already exist and are verified: `regen_d15_dst.py` for D15 and agent
D's `export_catchup.py` for D04/D24.
**C-D-001 — the provenance table is DERIVED, and the page says it is inferred.**
The spec asks for "every upstream source" per dataset. Nothing in this tree
declares that: `schema/datasets.yaml` has no `sources` key, `sources_registry.py`
has no `datasets` key, and D24 carries `source_key` per TARGET, never per
dataset. So `scripts/gen_provenance.py` infers the mapping through three
channels and publishes which channel each citation came from, in the cell, so a
reader can reject one claim without rejecting the page:

1. the **producer** — `export.dispatch.EXPORTERS`, or the `StreamWriter` method
   that buffers the dataset, found by reading which method names it;
2. the dataset's **subsystem** package, from the schema's own `subsystem` field
   and the design r4 §4 subsystem table (`SUBSYSTEM_PACKAGES`);
3. any other module that **names the dataset id**.

The alternative — a dataset-to-source dictionary typed into the generator — was
rejected for the reason the catalogue generator already gives for attributing
validation links from the artefacts rather than from a mapping: it goes stale
and nothing notices. The cost is that the inference is wrong in both directions,
and the page states that in its own second section rather than leaving a reader
to discover it.

**C-D-002 — scoring modules are excluded from upstream attribution.** A source
that only `plausibility/`, `validation/`, `report/` or `calibration/` reads is
one the model is compared **against**. Listing it as upstream would be a false
provenance claim and would also erase the independence the exposure register
exists to protect (I-058, I-060). `tests/test_source_exposure_consistency.py`
already draws this line and the generator reuses it. Consequence: 2 sources D24
reads targets from are not upstream of any dataset, which the page publishes as
`scoring-only` in its own table and the validator accepts as an answer.

**C-D-003 — a module naming more than 10 datasets is a registry, not a builder.**
`report/datasets_md.py` names all 32, `release/packages.py` 28,
`export/dispatch.py` 27. Counting those mentions as build evidence gave D28 the
tariff corpus and D22 the whole sweep catalogue. The producer module is exempt,
because it is the producer by declaration rather than by mention. The measured
gap in this tree is between 8 and 12 mentions, so the limit sits inside it.

**C-D-004 — two scripts, not one with a `--validate` flag.**
`gen_provenance.py` derives provenance from the code; `validate_provenance.py`
parses `docs/PROVENANCE.md` as published and checks it against D23 and D24. Had
the validator imported the generator's model instead, it would never read the
page, and a page that had drifted — hand-edited, or generated from an older
tree — would pass. The validator imports the generator for exactly one thing:
the declared assumption registries, to tell a typo from a real flag id.

**C-D-005 — the validator exits 2 when a check could not run, not 0.** An unrun
check must never read as a pass. Missing page, unparseable table, no D23 part
file, no pyarrow: all 2. 1 means the page and the datasets genuinely disagree.
0 only when every check ran and agreed.

**C-D-006 — the D24 assumption cross-check cannot be satisfied today, and is
reported rather than weakened.** The spec asks that "the assumption numbers in
the table must match what D24 declares". D24 declares none: its 113 targets on
disk carry no assumption field, and the schema's D24 does not declare one either
— its seventeen fields are target, source and tolerance columns. The assumption
registries the page actually rests on are
`validation.assumption_sweep.ASSUMPTION_FLAGS` (56 flags) and
`export.tariffs.TARIFF_ASSUMPTIONS` (8). So `D24-ASSUMPTIONS` reports
`d24-declares-none` as a disagreement and the validator exits nonzero. Making
it pass would mean either deleting the check or declaring the registries to be
D24, and neither is true. Closing it properly means D24 growing an assumption
column, which is a schema decision and not an export one.

**C-D-007 — citing the whole register does not close the D23 coverage check.**
`export/run_manifest.py` iterates `REGISTRY` to build D23's `input_sources`, so
D23 genuinely cites every declared source and the page says so. Letting that
citation stand in for 69 individual answers would make the coverage check
unfailable. It is recorded as a fact about D23's provenance and the per-source
accounting is done from the page's `scoring-only` / `read-but-unattributed` /
`read-by-nothing` table instead.

**D-143 — the D18 proof moves to the 2015/2016 boundary, and the 2019 switch is
retired.** The plan was to restart on 2.3 at the 1 Jan 2019 boundary, only if a
byte-identical proof passed, with the proof restoring the final 2018 checkpoint.
That put a mandatory, unattended, all-or-nothing gate at 16 Oct 16:00 with no
slack behind it.

It is unnecessary. Two facts make it so:

1. `scripts/prove_2_3_switch.py` is fully parameterised — `--ckpt`, `--start`,
   `--sim-day-offset` — so the proof it performs is "does the new engine
   reproduce the old engine's non-D18 output for one restored day". That claim
   is not specific to 2018. Proving it at the **2015/2016** boundary proves
   exactly the same thing, about the same code, 24 hours earlier and with the
   session attended.
2. The era model's first smart-meter install on the real town slice is
   **2019-10-02**, from the sourced ESB anchor that the rollout commenced late
   2019. So with gating ON, 2016, 2017 and 2018 emit **zero** D18 rows — not by
   a date check bolted on top, but because no home has a meter yet. Agent A
   tested this with an ungated control, so the emptiness is demonstrably the
   gate and not a stub.

Together: enable `d18_era_gating` **and** clear `omit_datasets` at the 2016
boundary, once the proof passes there. 2016-2018 then write no D18 because
nothing is fitted, 2019 onward write it as homes are fitted, and **no
configuration changes at the 2019 boundary at all**. The switch that needed a
deadline stops existing.

Both halves are required and A flagged why: a gated D18 that is still in
`omit_datasets` is no D18 at all.

If the proof fails at the 2016 boundary, nothing is enabled, the replay
continues exactly as it is, and the fallback is unchanged — D18 added later as
a post-pass. The cost of trying early is one restored day of compute.

**D-144 — adding an exporter makes every existing package non-conformant, and
the reference packages must be back-filled at the boundary.** Agent D moved D04
out of `ABSENT` and into `EXPORTERS`. That is the right change, and it has a
consequence nobody declared: `test_export_dataset_schemas` treats a dataset
with an exporter and no part as an **unaccounted absence** — "either export it
or record why it cannot be exported" — and `v1` and `work/town4/pkg` were both
exported before D04 had an exporter. Four tests that had been *skipping* turned
into failures, which is the test doing precisely its job.

Recording why the absence is excusable was the wrong fix: D04 *can* be exported
now, so a recorded reason would have been false. `ABSENT` means "cannot be
built", not "was not built yet".

So D04 was exported into both reference targets, which also proved the
exporter end to end on real packages rather than on fixtures:

| target | out_root | rows |
|---|---|---|
| estate-year | `v1/ground_truth/` | **771** |
| town-14day | `v1/ground_truth/town14/` | **16,894** |

`test_export_dataset_schemas` is then **103 passed, 30 skipped, 0 failed**, and
the part validates through D's `permit_null_required` mechanism —
`schema_conformance: partial` with `age_years_at_t0`, `failure_hazard_scale`,
`install_date` and `make_model_synth` declared null because the model holds no
value for them.

**One trap worth naming.** The part must be written to the **out_root**, not
the run root. `export_all('work/town4/pkg', 'work/town4/pkg', …)` writes a part
the test cannot see, because that target's package root is `v1` with subdir
`town14`. The first attempt did exactly that and the failure message was
unchanged, which reads like the export having had no effect at all.

**Done in the worktree only, and deliberately not committed.** Those two
manifests describe an export that exists in `~/hrsd-wt-int`, not in the live
tree. Committing them would assert parts that are not there — the I-114 failure
mode exactly. The live `v1` is back-filled as part of the boundary post-pass,
with `DATASETS.md` regenerated in the same step so the catalogue and the disk
agree in one commit rather than two.

**D-145 — P-1 closed: D24's missing assumption column stays missing, and the
validator keeps failing honestly.** The provenance brief asked the validator to
cross-check the page's assumption numbers against what D24 declares. D24
declares none: its 113 targets carry no assumption field and the schema's D24
defines none either — seventeen fields, all target, source and tolerance
columns. Agent C reported it as `d24-declares-none` and made the validator
**exit nonzero** rather than weaken the check.

That stands, on the user's decision. Closing it would mean D24 growing a column
mid-replay, which means either re-exporting D24 for every year or letting the
years disagree about a dataset's shape — and a deliverable whose columns change
part-way through twelve years is a defect no documentation repairs. A check
that fails for a true reason is worth more than one that passes because it was
lowered to fit; that is the same rule that governs every gate here.

The assumption registers the page actually rests on remain
`validation.assumption_sweep.ASSUMPTION_FLAGS` (56) and
`export.tariffs.TARIFF_ASSUMPTIONS` (8), and `docs/PROVENANCE.md` says so in
its own second section.

**D-146 — P-2 closed: the public holidays are statute, and the WRC page is only
a cross-check.** The licence question is answered by naming the real source:
the **Organisation of Working Time Act 1997, Schedule 2, as amended** — amended
by the Holidays (Employees) Act and subsequent instruments that added
St Brigid's Day from 2023 and the one-off public holiday of 18 March 2022, both
of which the table already carries and both now attributed to the statute
rather than to a web page.

Statute is not licensed material in the sense the manifest was worrying about:
it is the law, reproducible by anyone, and quoting the dates it fixes needs no
permission. The WRC page keeps its place in the register as a **cross-check**
on the derived dates, not as the authority for them, which is also the
honest description of how it was used — the rules came from statute and the
dates were verified against three independent anchors (D-127).

So the "re-use terms not stated, TO CONFIRM before redistribution" caveat is
withdrawn from the derived table. It remains on the WRC HTML itself, which is
still a web page with no stated terms, and which nothing now depends on.

**D-147 — P-5 settled: pre-emption is allowed, bounded by the two-hour rule.**
The user's decision: if a planned boundary is within two hours, stop there
rather than risk a gate trip. That is a better rule than either of the ones I
was choosing between — it neither forbids pre-emption nor licenses stopping the
run whenever a projection looks bad, and it uses the boundary, where stopping
is already free, as the natural place to act.

As it happens the gate never tripped. 2015 reached its end with the peak flat
for the last ninety simulated days, so the first application of the rule is the
planned 2015/2016 boundary itself.

**P-3 and P-4 unchanged on the user's decision:** B2 stays local, nothing is
deleted.

**D-150 — P-6 answered: the codec is already zstd-9, the level is not the lever,
and the 19.8% that IS available sits below the threshold for applying it.**

Every dataset in 2015's package is already **ZSTD**, written at level 9
(`io.py:98-99`), so P-6's conditional ("if it isn't zstd") does not arise.
Tested anyway on 2015's real D16 and D19 parts, with losslessness checked on the
decoded data:

| variant | D16 part000 | vs now | write |
|---|---|---|---|
| as written, zstd-9, row groups 98,304 | 210.1 MB | — | — |
| zstd-9, **row groups as written** | 210.0 MB | **−0.0%** | 4.5 s |
| zstd-9, default row groups | 173.0 MB | −17.6% | 4.1 s |
| zstd-15 | 172.4 MB | −18.0% | 22.2 s |
| zstd-22 | 172.3 MB | −18.0% | 75.7 s |
| zstd-9/15 + `byte_stream_split` on floats | 173.0/172.4 MB | −17.6/−18.0% | — |

**The compression level is not the lever.** Level 15 buys **0.4 percentage
points** over level 9 for five times the write time, and 22 buys nothing more
for eighteen times. `byte_stream_split` — the usual remedy for float columns —
changes nothing here, on 11 of 15 float columns.

**Row-group size is the whole effect**, because `io.py:103` pins
`row_group_size=100_000` and a 3M-row part is written as 31 small groups that
each compress independently:

| rows per group | size | vs now |
|---|---|---|
| 98,304 (current) | 210.0 MB | −0.0% |
| 200,000 | 196.6 MB | −6.4% |
| 500,000 | 180.2 MB | −14.2% |
| 1,048,576 | 173.0 MB | −17.6% |
| 3,040,128 (whole part) | 168.6 MB | **−19.8%** |

**Not applied.** The rule was ">25% and lossless"; the maximum available is
**19.8%**, so the condition is not met and the writer is unchanged. It is worth
**~10.5 GB** over the run and is available on request — with one caveat that
argues for leaving it: a larger row group buffers more rows in memory before
writing, and memory is the thing that has cost this run the most trouble
(I-113, I-116, I-117). Trading ~10 GB of disk, which is not scarce, for
pressure on RAM, which is, is the wrong direction while 28 GB of disk margin
remains.

**On the losslessness check itself:** my first attempt hashed Arrow *buffers*
and reported every variant — including the zstd-9 control, which cannot differ
— as lossy. Re-encoding changes chunk boundaries and null-bitmap padding, so
buffers differ while every value is identical. Switched to `Table.equals`,
Arrow's logical comparison, after which all variants verify lossless. A
control that "fails" is the signal that the test is wrong, not the subject.
**D-D-001 — a required column may be NULL only if the null is DECLARED, with a
reason, in the part's own manifest.** D04 and D24 are each partly derivable and
partly not, and the two ways out of that are both forbidden: filling a required
field with a plausible number, and lowering the schema so the gap stops
showing. So `schema.validate.validate_frame` gained `permit_null_required` and
`io.write_dataset` gained `null_required={field: reason}`. It is deliberately
narrow: it relaxes only the required-null check (type, enum, `forbidden` and
the leakage audit all still run), the column must still be present, naming a
field that is not declared required is an error rather than a no-op, a reason
is mandatory, and every accepted exemption is written into the sidecar manifest
as `schema_conformance: partial` plus `null_required_fields`. Defaults are
empty, so a fully conformant part records `schema_conformance: "full"` and no
existing caller changes behaviour.

**D-D-002 — D04 is written as a per-year post-pass, with four required columns
declared null.** `export.assets.export_d04`, registered in
`export.dispatch.EXPORTERS`. No engine change: the asset state is a
deterministic function of the master seed and is rebuilt through
`RunContext.slice`, as D01/D02/D05-D08/D14/D15 already are. 16,894 rows on the
town run across all six declared asset classes, including the hot water store
(litres) and the immersion, which `physics.dhw.dhw_system_for` holds and which
the old absent reason never considered. `make_model_synth` and
`failure_hazard_scale` stay null for exactly the reasons that entry gave - the
model variation is drawn per CYCLE, and failure is a fixed seven-day outage,
not a Weibull - and `install_date` and `age_years_at_t0` are null for every
non-appliance row because nothing but the appliance draw carries an age. The
old reason is kept verbatim in `absent.SUPERSEDED_VERBATIM`. Full column-level
account in `docs/D04_D24_D29_D30_export_notes.md`.

**D-D-003 — D24's absent entry was half right, and the half that stands is now
carried by the data.** The packaging half is gone: the per-year post-pass
already creates `<year>/pkg/evidence/`, as it must for D22 and D23, and it now
PROVES the directory is usable with a probe write
(`replay_supervisor.prepare_evidence_package`) and records the proof in the
year's export report, so a read-only volume is reported as itself rather than
as three mysterious dataset failures. The schema half stands: `domain`,
`tolerance`, `tolerance_kind`, `evidence_tag` and `provisional` have no source
and are declared nulls under D-D-001. Eleven columns are filled, exactly as
that entry's own `field_mapping` said they could be.

**D-D-004 — a D24 part may carry targets for a DIFFERENT year than the run,
but only while it says so.** `build_d24(year)` reads published CSO tables and
raises `TargetError` on the first missing cell rather than guessing. The tables
cover 2016-2023; the replay spans 2014-2026. So `targets_for_year` asks for the
run's own year first and falls back to 2022 - `build_d24`'s own default, and
the year of the committed `v1/evidence/d24_calibration_targets.json` - when the
sources do not reach it, returning the substitution as a record that goes into
the part's manifest and its limitations. 2015, 2024, 2025 and 2026 get
substituted targets, asserted in a test so a change in source coverage fires.
A D24 row is a published reference statistic rather than an output of the
simulated year, and every row records the year it was built for inside
`value_json`, so the substitution costs a reader nothing as long as it is
stated.

**D-D-005 — the replay config does NOT satisfy D29/D30's D11 dependency, and
the fix is reported rather than made.** D29 and D30 both reach
`occupied_weekday_hours`, which requires at least one
`<run_root>/ground_truth/D11_part*.parquet` with a building-located row
spanning a weekday, and refuses to default it. D11 is written only while
`day.sim_day < collect_presence_days`; the default is 14, `sim_day` is GLOBAL
across the replay (`sim_day=sim_day_offset + i`, D-110), and
`replay_supervisor.run_segment` does not pass `collect_presence_days`. Every
kept segment starts at offset 31 or later, so NO delivered year collects a
presence row and D29/D30 fail in every one; the only segment under the gate is
`warmup_2014`, which is discarded. Passing
`collect_presence_days=seg["sim_day_offset"] + 14` would fix it and would
perturb nothing - `collect_presence` is a retention flag, and the engine's own
comment says resolving the venue on every day "advances no other stream and
changes no other draw" - but it changes a RUNNING replay's per-day behaviour
and the volume of a ground-truth dataset, so it is the coordinator's call.
Asserted both ways in `scripts/tests/test_d29_d30_need_d11.py`, so the test
fires if the config or the engine default moves.

**D-D-006 — a year's export post-pass can be re-run, and a re-run moves parts
aside instead of deleting them.** `scripts/export_catchup.py`. The post-pass
runs once, inside the supervisor, so a dataset it could not write then is
missing from that year's package and nothing goes back for it - which is
exactly 2015's position, since the replay producing it runs from the main
checkout and has no D24 exporter. The catch-up refuses a segment with no
`DONE.json` (still running, or failed, and its package may be half-written),
moves every existing part of the requested datasets into
`<segment>/superseded/<timestamp>/` so `cleanup_stale_parts` finds nothing to
unlink, leaves the run's own `export_report.json` untouched and writes
`export_report_catchup_<timestamp>.json` beside it. Writing it found a real
bug: a D24-ONLY export raised `SourceError` claiming a declared source was not
declared, because `build_d24` resolves targets through `sources.REGISTRY` and
nothing had imported `sources_registry` yet - a full `export_all` starts at D01
and imports it on the way, so only a single-dataset caller hits it.
**A-D-139 — D18 is gated per home on three eras, not on one enrolment flag.**
D-101 scoped D18 to "homes enrolled with PARA//EL, from their enrolment date
only". That is one boundary where the real data has two. A home that had its
meter exchanged in 2021 but never enrolled is not unobserved: ESB Networks
publishes its half-hourly import and export. Modelling it as unobserved would
discard the one observable the majority of Irish homes actually have, and would
make the dataset's coverage a property of this project's fictional programme
rather than of the national rollout. So there are three eras — nothing, then
30-minute import/export from the install date, then the full 1-minute device mix
from enrolment — and `observation/era.py` is the single definition. Cost: 0.89 GB
for the meter era on top of D-101's ~9.5 GB, measured. `docs/D18_ERA_GATING.md`.

**A-D-140 — install dates are STRATIFIED against the sourced curve, not drawn
independently.** The home at rank `r` of `N` gets the quantile `(r + 0.5) / N`,
so the number installed by any day is exactly `round(share · N)` and the
realised share can differ from the sourced curve by at most `0.5 / N` — 0.00046
at town scope, and that is the measured worst case over all 4,291 days. An
independent uniform draw per home reproduces the curve only in expectation, and
at the 50-home estate scope it would miss it by several homes, which would make
"the gate tracks the sourced rollout" an unfalsifiable claim at the only scope
small enough to inspect by hand. The ranking key still comes from the seed tree
per premises, so *which* homes they are is seeded; only the *count* is fixed.

**A-D-141 — a home cannot be enrolled before its meter exists, and enrolment is
filled from the eligible pool.** D-111 gives enrolment its own ramp with no
reference to the rollout, but PARA//EL's import and export channels are the
meter's own registers read over its HAN port — an edge device has nothing to
read before the exchange. So eligibility opens on the install date and each
day's A-99 target is filled from the eligible homes in propensity order, which
keeps the enrolment *total* exactly on the ramp (the project's standing rule:
calibrated totals, endogenous selection) while making the *sequence* physically
possible. Measured at town scope: `shortfall_days = 0`, so the constraint costs
nothing; any future shortfall is reported in the run's diagnostics rather than
silently enrolling a home that has no meter.

**A-D-142 — D-111's "estates with an energy co-op" is implemented as a seeded
per-estate offset, and said so.** The population synthesis holds **no co-op
attribute**: there is no energy co-op in the town model today, and
`lambda_coop` in `population/traits.py` is a person's cooperation trait, not an
organisation. Three options were available — drop the term, synthesise a co-op,
or realise the term as an estate-level offset. Dropping it would silently
contradict a settled decision; synthesising a co-op is a population-model change
well outside this task and would put a fabricated institution in D01/D02. The
offset reproduces the **observable consequence** the decision cares about —
enrolment clusters by estate instead of spreading evenly — without pretending to
read something that does not exist, and the module says in terms that if a co-op
is ever synthesised this term should read it instead of drawing. A-99.

**A-D-143 — the 30-minute era publishes the INTERVAL MEAN, not a spot reading.**
`observe_channel` samples a 1-minute truth at the device's interval, so the
cheap implementation of a half-hourly meter is to let it pick one minute in
thirty. That would publish an instantaneous power stamped as half-hourly
consumption: it would not close an energy balance against D16 or D19, and
"identical error patterns" of exactly that kind are what the 7.9 tell audit looks
for. So the truth is replaced by its 30-minute block means before observation
(`stream_writer.interval_mean_held`), which preserves the day's energy exactly,
and the reporting phase is pinned to 0 because a data service's intervals are
clock-aligned while a device's phase is its own. A-100.

**A-D-144 — the gate is OFF by default and the switch is a config edit.**
`StreamWriter(d18_era_gating=False)` and `run_year(d18_era_gating=False)`, for
the same reason `omit_datasets` defaults empty and `solve_network` defaults
False: every existing artefact, the published estate-year included, was written
ungated and must keep reproducing byte for byte. `run_segment` reads
`cfg.get("d18_era_gating", False)`, so turning it on at the 2019 boundary is two
lines of `replay_config.json` and no Python edited under time pressure.
2015–2018 are **not** re-run: they are already correct — those years have no D18
because nothing was fitted, which is exactly what the gate would produce — and
re-running them to write an empty dataset would cost about 43 hours.

**A-D-145 — the 2019 switch is proved byte for byte, not argued.** Two new RNG
streams were *appended* (79, 80) and the seed tree is counter-based, so no other
subsystem's sequence can move; the device-age change is confined to the D18
branch. That argument is sound and it is still not a proof.
`scripts/prove_2_3_switch.py` restores the final 2018 checkpoint, runs
2019-01-01 twice from it — gate on, gate off — and compares every file of both
packages byte for byte, ignoring D18. Bytes, not row counts or content hashes:
`write_dataset` is already configured for determinism, so anything short of
identical bytes leaves room for a difference a summary statistic does not see.
It exits 1 on any non-D18 difference and **2 if D18 itself came out identical**,
because a run in which the gate did not engage proves nothing and must not be
read as a pass. The comparison logic is importable and has its own tests, so it
was verified before the 2018 checkpoint existed.

**D-148 — each year now runs as a fresh subprocess, restored from the previous
year's checkpoint.** Every segment used to run in one long-lived process, so
`ru_maxrss` never reset at a year boundary and any per-day accumulation
compounded across all twelve years. That is how I-117's retained power-flow
dicts — 4.15 GB over the replay — took the gate to 88% of its budget. Fixing
that one accumulator helps; making the process boundary coincide with the year
boundary means **the next one cannot compound either, whether or not anybody
finds it**. Memory is reclaimed by the only mechanism that cannot be forgotten:
process exit.

`main()` gained an `--only NAME` child mode that **reuses the existing loop**
rather than duplicating the skip-if-DONE, restore-from-previous, export and
sentinel logic — a second copy of that would drift from this one. The parent
(`supervise()`) spawns one child per not-done segment, keeps the three-attempt
retry, and reads `DONE.json` back as the contract across the process boundary,
since the child already wrote it. `--in-process` keeps the old arrangement, for
the proof below and for comparing the two.

**Digest-neutral, verified rather than asserted.** The change touches
`scripts/replay_supervisor.py` and `scripts/replay_config.json` only — **zero**
files under `scripts/baile_nua`, which is the whole of what `digests()` covers.

**Proved by `scripts/prove_subprocess_per_year.sh`**, three runs on a
two-segment estate-scale config, fingerprinted on the checkpoint chains, which
are the simulated state:

| run | s1 | s2 |
|---|---|---|
| A subprocess, uninterrupted | `a2f24b63…` | `106a3982…` |
| B child killed during s2, then resumed | `a2f24b63…` | `106a3982…` |
| C **old single-process** (`--in-process`) | `a2f24b63…` | `106a3982…` |

C is the one that matters: A == C shows the new process arrangement computes
what the old one did, rather than merely being self-consistent with itself.
A == B shows a killed child leaves no state the resume cannot reproduce — in
this run the parent's own retry re-spawned the child and completed it, which is
the path a real failure would take.

**The proof script asserts the fingerprint is non-empty.** Its first run
returned `EMPTY` for all three arrangements, because my test config omitted
`label` and every run died early — and `EMPTY == EMPTY` reported two PASS
lines. Without that guard this decision would rest on a comparison of nothing
against nothing.

**D-149 — an 8 GB RSS warning, logged and not fatal.** `rss_warn_mb: 8192` in
the config, written once per segment to `progress.log` when current RSS first
passes it. On a 32 GB machine the 18,432 MB gate is an abort ceiling, not a
target; last night the only signal that anything was accumulating was the gate
figure creeping toward its own limit, by which point the question is whether to
abandon a ten-hour year. A warning at 8 GB makes accumulation visible while it
is still cheap to investigate.

**D-151 — do not walk the live tree while the replay runs; my own measuring
cost it an hour.** 2016's per-day gaps went 103, 101, 104, **3535**, 116, 765,
334, … and the 3,535-second gap ran **12:08:26 to 13:07:21**, which brackets
exactly two `gen_structure.py` runs — each an `os.walk` of 60,672 paths with an
`lstat` per entry — plus repeated `du -sh` over 21 GB for the P-8 re-measure.
The replay lost about an hour of progress to a documentation task.

`fseventsd` sat at 100% of a core throughout and `mdworker` at 22%, which is
the downstream cost: a full-tree stat storm generates an FSEvents flood, and
the tree had just moved to `~/hrsd`, so Spotlight was re-indexing 21 GB at a
new location at the same time.

**Two things change.**

1. `.metadata_never_index` now sits at the tree root, which tells Spotlight not
   to index it. The run writes thousands of checkpoint and Parquet files; none
   of them is anything a desktop search should return. Reversible — delete the
   file.
2. **Measurement must come from the manifests, not the filesystem.** Every part
   already carries its own `rows` and byte size in its sidecar manifest, and
   every segment's `DONE.json` carries `row_counts`. A per-year size can be
   summed from those without stat-ing a single Parquet file. `STRUCTURE.md`
   regeneration and any full-tree walk belong at a segment boundary, when the
   engine is stopped anyway.

**I got the diagnosis wrong first.** At 13:06 I measured three consecutive
gaps of 103, 101 and 104 seconds, concluded the rate had "settled" and that
`fseventsd` had "approximately zero" measured impact, and declined to act. The
three gaps I sampled were real; generalising from them was not. The median over
the whole segment is 136 s against 2015's 108, and the outliers are minutes
long. Sampling the quiet part of an erratic series and calling it the rate is
the same error as fitting a slope across a step (I-116), twice in one day.
