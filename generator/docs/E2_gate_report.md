# E2 gate report - Baile Nua simulation candidate

**UNVALIDATED SIMULATION EVIDENCE: E2 engineering candidate**  
Engineering verification only. No behavioural calibration is claimed.

Generated from artefacts by `baile_nua.report.e2_gate`. Every figure below is read from the artefact named beside it; a missing key raises rather than printing a placeholder, so a number that is not in an artefact cannot appear here.

---

## 1. Verdict per E2 criterion

Design 9.2's gate table: *"Full town, 10 years, invariants clean. Coupling-lag test passes. Scale benchmarks within hardware. Physical consistency at F1/F2. Event coverage complete. Privacy inference test run and reported. D28 to D31 pass the 6.5 tests."*

The town figures below come from `work/town4/town_diagnostics.json`, which is the newest `work/town*/town_diagnostics.json` by mtime - chosen by timestamp rather than from a hard-coded preference order, so the report cannot cite a run it did not read.

| # | criterion | verdict | measured | artefacts |
| --- | --- | --- | --- | --- |
| E2-1 | Full town, 10 years, invariants clean | **FAIL** | full town 1092 homes for **14 days** under C2, against the 3650 days the criterion requires; 10 years on the **u23_mixed_age, 60 homes** (not the full town); ten-year invariants clean=True; any_fail=False, any_no_data=False | `work/town4/town_diagnostics.json`, `v1/evidence/wp5_tenyear.json`, `v1/evidence/machine.json` |
| E2-2 | Coupling-lag test passes | **PASS** | all_regimes_pass=True | `v1/evidence/w2_steps6to9.json` |
| E2-3 | Scale benchmarks within hardware | **PASS** | measured 14.59 h per town-year under C2 against a projected 12.33 h bare and 18.5 h with U21's margin; peak RSS 7905.6 MB of 32.0 GB | `work/town4/town_diagnostics.json`, `v1/run_diagnostics.json` |
| E2-4 | Physical consistency at F1/F2 | **PASS** | max physics relative residual 1.037e-12; max energy closure relative residual 4.512e-16 | `work/town4/town_diagnostics.json` |
| E2-5 | Event coverage complete | **PASS** | 10 event kinds; missing_from_the_year=[]; present_but_unsourced=[]; 3 sourced, 2 legal instrument, 6 [A] | `v1/evidence/w2_steps6to9.json` |
| E2-6 | Privacy inference test run and reported | **PASS** | home_15min: occupancy AUC 0.8621 (95% hi 0.8631), FAILS SCREENING, home_30min: occupancy AUC 0.8655 (95% hi 0.8669), FAILS SCREENING | `v1/evidence/privacy_inference_u20.json` |
| E2-7 | D28 to D31 pass the 6.5 tests | **FAIL** | D28, D29 and D30 built and passing rules 1 and 3; D31 carries its weather series only; rule 4 NOT EVALUABLE | `scripts/tests/test_nonsensor_65_rules.py`, `docs/ISSUES.md (I-072)` |

**Gate verdict: FAIL - 5 of 7 criteria met, 2 failed.**

Failing: **E2-1, E2-7**. Each is scored PASS or FAIL exactly as design 9.2 writes the criterion. A criterion that is not met now is a FAIL with its measured basis, never a deferral on the strength of a run that is scheduled.

**E2-1.** **FAILS on the conjunction.** The criterion asks for one run that is the full town AND ten years AND invariants clean. The full-town run is 14 of 3650 days (0.4% of the decade), and the decade that did run is on the u23_mixed_age, 60 homes, not the town. Invariants are clean on the decade that ran (True), so the clean clause is met and the COVERAGE clause is not. Every part has run and not all at once.

The measured basis for why: a full-town decade is 146 run hours extrapolated from the measured 14.59 h per town-year, and 56.5 GB without D18, against 116.7 GB free - so it fits the disk and not the week. Reported as a **failure with a measured basis, not a deferral**: the criterion is not met now, whatever is scheduled.

*Evidence:* `work/town4/town_diagnostics.json`, `v1/evidence/wp5_tenyear.json`, `v1/evidence/machine.json`

**E2-2.** The 1-minute device and physics step against the 15-minute network epoch. C2 now exists, so the contract is a statement about a coupling that solves something.

*Evidence:* `v1/evidence/w2_steps6to9.json`

**E2-3.** Measured on the full town rather than extrapolated. The power flow is 14.5% of runtime and has its own line, because a projection built from simulate plus write alone under-predicts C2 by exactly that.

*Evidence:* `work/town4/town_diagnostics.json`, `v1/run_diagnostics.json`

**E2-4.** Both at machine precision. F3 (EnergyPlus) is out of scope by E1's own declaration and is not claimed.

*Evidence:* `work/town4/town_diagnostics.json`

**E2-5.** Complete in the sense the criterion asks: every declared kind occurs and every one has a source or a registered [A]. NOT a claim that the event RATES are right - five of ten kinds are [A].

*Evidence:* `v1/evidence/w2_steps6to9.json`

**E2-6.** The criterion is that the test is RUN and REPORTED, and it was, for the first time. The RESULT fails design 7.8's screening threshold and is reported in full, including that the attack does not beat a time-of-day baseline - which design 7.8 also requires and which says something different.

*Evidence:* `v1/evidence/privacy_inference_u20.json`

**E2-7.** Not built: ['wholesale_price', 'carbon_intensity', 'system_demand', 'flex_event']. Their publishers are EirGrid and SEMO and neither is declared in SOURCES.md. The standing rule is that every source is declared before use, and acquiring two new publishers' series - with their licences, their revision conventions and their time-zone handling - is a source-acquisition exercise rather than a generator. So D31 carries the weather series it can source and not the market series. Rule 4's test needs a real reference package and there is none, so it is unevaluated rather than scored.

*Evidence:* `scripts/tests/test_nonsensor_65_rules.py`, `docs/ISSUES.md (I-072)`

---

## 2. Independent checks

**Table 1 of 2 tables that are deliberately NOT combined.** I-058's rule: a source used to build the model cannot validate it. The checks below are the only ones scored against a reference declared at `model_development_exposure = "none"`, so they are the only ones that are independent evidence. The split is read from the register's own exposure field, so a source that is re-declared - as F1054 was, from `none` to `design`, once the population was fitted to its sibling FY047B - moves table on its own.

**4 independent checks.**

| check | reference | exposure class | artefact |
| --- | --- | --- | --- |
| U31 old/new gas gradient (D-073) | `cso.gas.dberng02_by_dwelling_construction` | `none` (independent) | `v1/evidence/u31_newpop_prereg.json` |
| Age x economic-status joint, independent arm | `cso.census.cna25_economic_status_by_age_1981_2016` | `none` (independent) | `v1/evidence/w3_joint_population.json` |
| Gross move rate (U33) | `cso.census.sap2022_usual_residence_one_year_ago_by_town` | `none` (independent) | `v1/evidence/wp5_tenyear.json` |
| Overnight load per awake person (I-052) | `esbn.rmds.slp_indexes_2022` | `none` (independent) | `v1/evidence/i052_lp1_timing.json` |

## 3. Checks scored against a calibration input or a design-exposed reference

**Table 2 of 2. These are consistency checks, not independent validations.** A pass here means the model agrees with something it was built from. These rows must never be added to the table above: a combined count of "checks that passed" would read as independence that this half does not have.

**4 calibration-exposed checks**, kept separate from the 4 independent ones above. The two counts are reported as two counts.

| check | reference | exposure class | artefact |
| --- | --- | --- | --- |
| Age x economic-status joint, scorer | `cso.census.f1054_economic_status_by_age_group` | **`design`** (calibration-exposed) | `v1/evidence/w3_joint_population.json` |
| Annual gas PL-GAS-01 | `cso.gas.dberng01_by_dwelling_ber` | **`tuning`** (calibration-exposed) | `v1/evidence/plausibility.json` |
| Retrofit and control magnitudes | `seai.deap.manual_4_2_7` | **`design`** (calibration-exposed) | `v1/evidence/wp5_tenyear.json` |
| School venue capacity | `cso.education.eda49_schools_and_pupils_by_teacher_size` | **`design`** (calibration-exposed) | `v1/evidence/w3_town_network_venues.json` |

### 3.1 The plausibility suite's pass counts, reported as three numbers and never as one

Read from `v1/evidence/plausibility.json`.

| pass count | value | what it means |
| --- | --- | --- |
| `n_pass_independent` | **6** | Independent evidence. Scored against a reference at exposure `none`. |
| `n_pass_against_a_calibration_input` | **2** | NOT independent. The model agreeing with a source it was fitted to. |
| `n_pass_against_a_design_exposed_reference` | **1** | NOT independent. Nothing is fitted to the reference, but its information is in the model through a sibling table. |

These three are reported separately and are NEVER added into one figure. Their sum would read as that many independent corroborations, and only n_pass_independent is independent: the other two are the model agreeing with a source it was built from, which is a consistency check. The suite's own n_pass and n_pass_sourced are reported beside them as the suite's totals, and are not a substitute for the partition.

The suite's own totals, for completeness and not as a substitute for the partition above: 12 checks, 10 pass, 0 fail, 2 not evaluable; 9 of the passes are against a source and 1 against an unsourced `[A]` band.

**9 further sources appear in neither table.** Declared `design`, `selection` or `tuning` and scored against by no check in either table. Design 7.1: a source used to build the model cannot validate it, so these appear in the source-use register and in neither results table. The count is derived from the register's own exposure field.

## 4. U31 against D-073, the pre-registered criterion

Gradient **1.5936 -> 1.4134** on one population with frozen membership. **passes_all_four = True**; criterion_edited = False.

*Evidence:* `v1/evidence/u31_newpop_prereg.json`, and the off-arm question answered in `v1/evidence/u31_off_arm_question.json`. The four conditions are scored against D-073's literal pre-registered thresholds, not against the new population's own measured before-values.

## 5. Design 9.4's week-3 acceptance criteria

Scored separately from the E2 gate. *Evidence:* `work/town4/town_diagnostics.json` and `v1/evidence/w3_town_network_venues.json`.

| criterion | verdict | measured |
| --- | --- | --- |
| feeder loading within physical limits | **PASS** | max transformer 29.44%, max line 56.513%, 1344 of 1344 epochs solved, 0 non-converged |
| venue presence consistent with person presence | **PASS** | {"person_in_two_places_at_once": 0, "venue_rows_with_no_venue_id": 0, "venues_named_but_not_declared": [], "person_at_a_venue_and_at_home_at_once": 0, "person_minutes_at_venues": 8776710, "venue_occupancy_minutes": 8776710, "the_two_records_agree": true} |
| measured scale within the day 6 projection | **PASS** | Strip the power flow, which the C1 projection could not have included, and the measured town-year is 12.47 h against a projected 12.73 h - 2% under. With the flow it is 14.59 h, which is 76% of the 19.1 h the projection allows with U21's x1.5 margin. |

### 5.1 The scale figure's caveats, in full

Quoted rather than paraphrased, from `v1/evidence/w3_town_network_venues.json`. The scale PASS does not mean the cost is linear in homes, and it was not measured on an idle machine.

**`scale.per_home_day_cost_at_scale`**

> 115.003 ms per home-day on 50 homes against 112.64 on 1,092 - the per-home-day cost FALLS by 2.1% at town scale.
>
> Which is favourable, and is also why the projection over-predicted. A run has per-DAY costs that do not scale with the number of homes - Phase A's serial town-level resolution, the weather slice, the writer's per-day bookkeeping - and on 50 homes those are divided among 50. The Day 6 projection multiplied the 50-home per-home-day figure by 21.84, carrying that small-slice overhead 21.84 times with it. At town scale the same fixed costs are spread over 1,092 homes, so the real per-home cost is lower.
>
> This is the direction a scale-up projection should err in, and it is the reason the measured C1-equivalent town-year came in UNDER the bare projection rather than inside the margin. It is not evidence that the cost is linear in homes: it is evidence that it is sub-linear, which the projection did not assume and which no earlier measurement could have shown.
>

**`scale.runtime_was_measured_under_contention`**

> The three full-town runs of this session measured 12.80, 13.52 and 14.59 hours per town-year, and the differences are CONTENTION rather than the model: each ran alongside a different number of ten-year year-processes on the same twelve cores. All three are inside U21's margin, and the largest is the one to quote, because a figure measured on a busy machine bounds the cost from ABOVE and a figure measured on an idle one does not. The per-home-day cost is the contention-free comparison and it is reported beside it.
>

**`scale.storage_reading`**

> A town-decade WITHOUT D18 is 56.5 GB against 130.4 GB free as measured now, so it fits. WITH D18 the projection is 156.8 GB (235.3 with margin), which does not. That is I-036, and it is why the full ten-year town run is reported as a requirement with a measured basis rather than as a run that happened.
>

## 6. Tell audit (design 7.9 item 4)

4 data findings and 26 manifest disclosures; highest severity **critical**. Adversarial analyst run: **False** - design 7.9 requires both, and an automated pass finds only the tells somebody thought of.

## 7. Delivery packages (design 6.3)

All separation rules pass: **False**. Observable view blind-safe: **False**. 74 limitations shipped in the evidence view, read from the issue log.

---

**UNVALIDATED SIMULATION EVIDENCE: E2 engineering candidate.** E1 regression: FAIL 7/8.
