# E1 gate report — Baile Nua / HRSD_Occupants

> **UNVALIDATED SIMULATION EVIDENCE: E1 engineering candidate**
>
> Engineering verification only. No behavioural calibration is claimed.

**Gate verdict: PASS** — 8 of 8 E1 criteria met.

Design revision 3, architecture frozen 8 October 2026. This report is generated from the artefacts listed against each criterion; the generator reads JSON and XML and has no number of its own.

## What this is, and what it is not

This is **engineering verification**. It establishes that the implementation does what the design says: that the physics closes, that the same inputs give the same bytes, that ground truth does not reach the observable layer, that a year of the estate runs and can be replayed. It establishes **nothing whatever about realism**. E1 reaches validation level V0 only.

In particular: the activity engine is flagged **VERIFIED, NOT CALIBRATED** (E0-2 / U04) because HETUS has no Irish data in any wave (I-008); the appliance trigger rates are declared assumptions tuned against one CSO table and checked against a second held-out one (I-027); and no behavioural, intervention-response or privacy claim is made or supported.

## 1. Pass or fail per E1 criterion (design 9.2)

| # | Criterion | Verdict | Measured | Evidence |
| --- | --- | --- | --- | --- |
| E1-1 | V0 invariants: zero failures. | **PASS** | 7 pass, 0 fail, 1 skipped of 8 | `v1/evidence/v0_invariants.json` |
| E1-2 | Byte-identical outputs at 1, 8 and maximum workers. | **PASS** | workers [1, 8, 12]; 11 files compared by SHA-256 per pair; checkpoint chain heads match | `v1/evidence/worker_determinism.json` |
| E1-3 | Every negative control rejected by its intended test for its recorded reason. | **PASS** | 31 of 31 controls passed; not passing: none | `v1/evidence/negative_controls.json` |
| E1-4 | Population matches public Cobh SAPS marginals. | **PASS** | 23 marginals; 23 within the simultaneous (Bonferroni) band at alpha=0.05; worst abs z 2.07 against a critical 3.72 | `v1/evidence/saps_marginals.json` |
| E1-5 | A complete one-year run of the 50-home, about 140-person estate, integrating weather, occupancy, appliances, physics and observation, with at least one life event and one disruption, and replayed deterministically. | **PASS** | 365 days, 50 homes, 147 people; 1 life event and 2397 disruptions; 100 home-days replayed from checkpoints across 84 days with 0 mismatches (worst absolute difference 0.0) | `v1/run_diagnostics.json`, `v1/evidence/checkpoint_replay.json` |
| E1-6 | MIMIC T1, T9 and T10 pass with at least 10,000 unique participants (5.14 counters). | **PASS** | T1 PASS, T9 PASS, T10 PASS; 11,869 unique synthetic participants | `v1/evidence/mimic_tests_T1_T10.json` |
| E1-7 | The report states engineering verification only: no behavioural calibration is claimed. | **PASS** | Every artefact carries the label and the claim; the activity engine is flagged VERIFIED, NOT CALIBRATED throughout | `this report, every section header and every artefact` |
| E1-8 | Runtime, memory and storage measured and published. | **PASS** | 2.308 s per estate-day, 111.372 ms per home-day, peak RSS 8,531 MB, 735.4 MB for the estate-year (41.3 kB per home-day); full town projected at 18.5 h and 23.53 GB with the x1.5 margin | `v1/run_diagnostics.json` |

**E1-1.** A skipped invariant is reported as skipped, never as a pass; each skip carries its reason in the artefact.

**E1-2.** Compared as Parquet bytes, not as equal floats: a dtype that lands differently is a difference the consumer sees.

**E1-3.** Every control is now rejected by its intended test for its recorded reason, and every magnitude is justified by a power analysis against its own check's resolution rather than chosen (I-034). NC-D2-03's fault is unchanged - 10% of the one-person mass moved - and so is the single-realisation band; what changed is that the fault is now pointed at a check with the power to see it. Section 7 gives the margins.

**E1-4.** Both verdicts are reported in the artefact: the simultaneous band is the one that decides, because 23 marginals tested at a per-test level is 23 chances to fail (I-016).

**E1-5.** The replay restores each day's opening state from its checkpoint and compares against the DELIVERED Parquet, not against a copy kept inside the checkpoint.

**E1-6.** The five 5.14 counters are reported separately below and are never summed.

## 2. The five MIMIC counters (design 5.14)

Reported separately and **never summed**. `baile_nua/mimic/counters.py` raises `CounterMergeRefused` on `int()` and `total()`, so the sum cannot be taken by accident.

| Counter | Value |
| --- | --- |
| `unique_synthetic_participants` | 11,869 |
| `completed_sessions` | 21,803 |
| `completed_responses` | 294,592 |
| `linked_baile_nua_panel_participants` | 1,219 |
| `unlinked_extended_pool_participants` | 10,650 |

The E1 target of 10,000 refers to **unique participants** (E0-5 / U16). Measured 11,869: **met**. Repeated sessions never count as unique participants.

### T1 to T10

| Test | Title | Required at E1 | Outcome | Pass criterion | Finding |
| --- | --- | --- | --- | --- | --- |
| T1 | API and schema conformance | **yes** | **PASS** | 0 integrity errors; forbidden fields always rejected; 10,000+ unique participants |  |
| T9 | Dashboard aggregates | **yes** | **PASS** | exact match; n < 15 cells suppressed; synthetic banner shown |  |
| T10 | Position-bias check | **yes** | **PASS** | detects only when planted |  |

## 3. U03: the two scale-down methods compared, and a recommendation

Both methods were built and scored on marginal, joint and spatial error over 10 seeds. Joint and spatial error are BETWEEN-SMALL-AREA quantities (D-012): SAPS publishes no individual-level cross-tabulation, so there is no joint distribution to compare against and an individual-level joint claim would be unfalsifiable.

| Method | n_people | n_households | n_areas_kept | spatial_coverage | marginal_mean_tvd | marginal_max_abs_z | joint_mean_abs_difference | spatial_morans_mean_abs_difference | spatial_dissimilarity_mean_abs_difference |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| proportional | 2,935 | 1,092 | 53 | 1 ± 0 | 0.009448 ± 0 | 2.071 ± 4.7e-16 | 0.04891 ± 0 | 0.008155 ± 4.1e-18 | 0.009859 ± 0 |
| whole_area_stratified | 2930 ± 1.7 | 1101 ± 37 | 14.3 ± 1.3 | 0.2698 ± 0.024 | 0.03589 ± 0.006 | 6.914 ± 2.3 | 0.1293 ± 0.045 | 0.1052 ± 0.035 | 0.04367 ± 0.012 |

**Recommendation: proportional.** Its mean joint error over 10 seeds is 0.04891 against 0.1293 for the alternative - a gap of 0.08038 against a seed-to-seed standard deviation of 0.04529, so the ordering is a property of the methods rather than of the draw. The same method is recommended on every one of the 10 seeds. It is also the only one of the two that satisfies R03 on every seed: proportional True, whole_area_stratified False.

> This **contradicts the design's expectation**. Design 5.2 step 2 leans towards whole_area_stratified as the method that should preserve joint structure better, by keeping whole small areas. The measurement says the opposite, and the spatial-coverage column is why: keeping WHOLE areas means keeping FEWER of them. Measured coverage {'proportional': 1.0, 'whole_area_stratified': 0.27} - the stratified method retains about 27% of Cobh's 53 small areas, so two thirds of the town is simply absent from it, and its between-area structure is measured over what is left. It also fails R03's household-count range. The recommendation follows the measurement.

## 4. Benchmarks, and whether the full town fits this Mac

Measured on Intel(R) Core(TM) i9-8950HK CPU @ 2.90GHz, 32.0 GB, 12 logical CPUs, Python 3.12.6.

| Quantity | Measured (estate) |
| --- | --- |
| Homes x days | 50 x 365 = 18,250 home-days (26,280,000 home-minutes) |
| Simulation, per estate-day | 2.308 s (median 2.209 s, p95 2.955 s) |
| Writing, per estate-day | 3.251 s (58% of runtime) |
| Per home-day, total | 111.372 ms (46.164 ms simulating, the rest writing) |
| Whole estate-year | 0.56 h = 0.23 h simulating + 0.33 h writing (plus 29.96 s town synthesis and 16.76 s weather) |
| Peak resident memory | 8,531 MB |
| Storage, estate-year | 735.4 MB (41.3 kB per home-day) |

| Dataset | Rows | Bytes | Bytes per row |
| --- | --- | --- | --- |
| D11 | 54,301 | 502,423 | 9.25 |
| D13 | 1,449,871 | 36,382,761 | 25.09 |
| D16 | 1,752,000 | 128,730,428 | 73.48 |
| D18 | 66,097,553 | 530,966,269 | 8.03 |
| D19 | 3,521,520 | 74,507,968 | 21.16 |

### Does the full town fit?

Scaling the estate to the town's 1,092 homes is a factor of 21.84. With the x1.5 margin U21 asks for:

- **Runtime: 18.5 h** for one town-year (12.33 h at the measured rate, x1.5) — of which 5.11 h simulating and 7.22 h writing.
- **Storage: 23.53 GB** for one town-year (15.68 GB measured-rate, x1.5). For the ten years E2 needs: **235.3 GB** with the margin.
- **Memory: bounded, not scaled.** The naive projection scales peak RSS by the number of homes, which is the wrong model for this run and is reported only to show why: the writer streams and flushes monthly, so resident memory is bounded by one month of one estate's rows plus the town at t0, not by the year. Storage is what scales.

The margin's basis: U21. Covers the serial phase-A share, which does not scale linearly in homes, and the town-wide t0 synthesis, which is already full-town in this measurement.

Simulation and writing are reported separately because they scale the same way but are nothing like the same size: writing D18 observations at 1-minute resolution costs several times what simulating them does. Anyone planning E2 needs the split, not the total.

**The answer.** One town-year fits comfortably in runtime and in disk. The binding constraint is the **ten-year** package E2 needs, and it is disk rather than time or memory: the dominant dataset by far is D18, the 1-minute observation layer, at about 8 bytes a row and tens of millions of rows per estate-year. Measured free disk on this machine: **116.7 GB** of 931.5 GB (`v1/evidence/machine.json`). The ten-year projection above should be read against that figure, and D-009's decision not to store 1-minute building state was taken for exactly this reason - but D18 is an observable deliverable and cannot be dropped the same way. Whether E2 reduces the observation interval, stores a subset of homes at full rate, or needs external storage is a decision for week 2, and the numbers to take it with are in this table.

## 5. Energy against the CSO: what is verified and what is not

D24 holds 113 targets read from registered CSO files (`v1/evidence/d24_calibration_targets.json`). None of them makes E1 a calibrated model; they are what turn "the physics closes" into "the physics closes **and** the magnitudes are the right size", which is a different and weaker claim than calibration but a much stronger one than closure alone.

| Quantity | Simulated | CSO target | Ratio |
| --- | --- | --- | --- |
| Electricity per dwelling, fossil-heated (49 homes) | 3,429 kWh/yr | 5,405 kWh/yr (DBEREL01) | 0.71 |
| Electricity per dwelling, electrically heated (1 home) | 8,712 kWh/yr | 2,999 kWh/yr (DBEREL01) | 2.90 |
| Space heat, gas-heated (49 homes) | 3,576 kWh/yr (30.9 kWh/m²) | 10,587 kWh/yr (DBERNG01) | 0.32 |

Electricity sits at 0.71 of its cell for the fossil-heated homes, which is where it belongs: DBEREL01 covers ALL household electricity, so a gas-heated dwelling cannot reach the part of its cell that is space heating.

**The gas ratio of 0.32 is the most informative number in this report, and it is not a failure.** Four things sit between simulated space heat and a measured gas meter, and three of them are simply not modelled at E1: hot water (there is no tank — see the stream writer's `UNMODELLED_D16_FIELDS`), gas cooking, and boiler losses. The fourth is the interesting one.

The E1 estate is a **modern** estate, because Cobh's small areas 047106015 and 047106012 are: **84% of its homes are A or B rated**, its mean build year is 2005 against the town's 1974, and its mean specific heat loss is 1.44 W/K/m² against the town's 2.45. Simulated space heat of 30.9 kWh/m²/yr is right for an A- or B-rated dwelling, whose design demand is roughly 25 to 45. The physics is also internally consistent: simulated heat is 0.52 of its own gross heat-loss-times-degree-days figure, which is squarely in the 0.4 to 0.7 a dwelling should show once solar and internal gains are credited.

**But DBERNG01 says real A–B homes burn almost as much gas as real F–G homes.** Within every dwelling type the spread across BER bands is only 4 to 7%, and A–B rated detached houses consume *more* gas (14,618 kWh) than F–G ones (13,292), while consumption varies 84% *across* dwelling types. That is comfort-taking: a better-insulated home is heated warmer, longer and in more rooms, and a poorly insulated one is heated less because it costs more. Measured consumption tracks dwelling **size**, not fabric quality.

E1's thermostat holds a fixed setpoint on a fixed timer and has no comfort-taking at all, so on a well-insulated estate it must under-predict measured consumption — and does. **This gap is reported rather than fitted** (D-022). Closing it by adjusting the fabric or the setpoint would hide a behavioural mechanism inside physical parameters, and would make those parameters wrong for every other purpose. Design 5.3 locates the mechanism in COM-B; wiring it into the thermostat is week 2 work. A test pins what the CSO data says, so that nobody later adjusts the physics to make consumption fall with the rating and believes they have improved it.

### Does the fit generalise? The held-out axis

DBEREL01 and DBERNG01 cross dwelling type with BER band, and both the appliance trigger rates and the floor-area corrections were checked against them, so they can only report that a fit was made. DBEREL02 and DBERNG02 cross the **same dwellings** with period of construction — an axis nothing was fitted to, which D02 already carries as `year_built_band`, and whose sources are declared and asserted to carry exposure `none` before anything is compared (D-015, D-021).

| | fitted axis (BER band) | held-out axis (construction period) |
| --- | --- | --- |
| Electricity, fossil-heated | 0.71 | 0.60 |
| Space heat against gas | 0.32 | 0.33 |

**The ratios barely move.** Gas goes from 0.32 on the axis that was fitted to 0.33 on the axis that was not. So the gap in section 5 is **not an artefact of fitting to the BER axis**: the model is equally far from the data on an axis it never saw, which is what a systematic unmodelled term looks like and what a fitting artefact does not.

And the held-out axis says something the fitted one could not:

| Period of construction | dwellings | simulated | CSO gas | ratio |
| --- | --- | --- | --- | --- |
| 1967-1999 | 4 | 3,731 kWh/yr | 8,799 kWh/yr | 0.41 |
| 2000-2004 | 41 | 3,496 kWh/yr | 10,114 kWh/yr | 0.33 |
| 2005-2023 | 4 | 4,240 kWh/yr | 11,851 kWh/yr | 0.33 |

The ratio falls from **0.41** for the 1967-1999 dwellings to **0.33** for the 2000-2004 ones: the newer and better-built the dwelling, the further the model falls below what its occupants actually burn. That is the comfort-taking signature exactly, measured on an axis nothing was fitted to, and it is the strongest evidence in this report that the gap is behavioural rather than a defect in the physics — which is why D-022 reports it instead of closing it.

It can say whether the ratios on an UNFITTED axis look like the ratios on the fitted one. If they do, the fit generalises across construction era; if the unfitted axis is much worse, the fit was to the BER axis specifically. It cannot say the model is calibrated: the gas cells still contain hot water, gas cooking and boiler losses that E1 does not model, and the estate is only 50 dwellings spanning few eras.

## 6. Archetype coverage: every kind of dwelling, run end to end

Archetype COVERAGE, not an estate. These homes are drawn from across the town to exercise every archetype the engine contains; they are not contiguous, do not share a feeder, and are not the E1 estate. No realism claim whatever.

26 homes x 7 days = 182 home-days. Physics residual 7.4e-13, energy closure 2.8e-16. **All dimensions complete: True.**

| Dimension | In the town | Exercised | Complete | Why it matters |
| --- | --- | --- | --- | --- |
| `ber_letter` | 7 | 7 | **yes** | specific heat loss ranges from about 1.5 to 4.8 W/K/m2 across the bands, so the solver's stiffness varies with it |
| `dwelling_type` | 4 | 4 | **yes** | party-wall fraction and glazing area differ by type |
| `heating_system` | 9 | 9 | **yes** | the heat-pump COP path, storage-heater scheduling and the direct-electric COP-1 path are different code |
| `sensor_tier` | 4 | 4 | **yes** | T1 carries two channels and T4 carries ten |

The estate alone could not show this, having no dwelling rated below C. Heat delivered rises steeply as the rating worsens, peaking at E, and then **stops rising** — while the achieved indoor temperature falls below the setpoint and stays there. That is not a defect: it is the emitter saturating. A dwelling whose fabric loses heat faster than its radiators can supply it does not get hotter bills without limit, it gets colder rooms, which is what the two columns together say and what the closed-loop thermostat makes possible (I-033). An open-loop controller would have shown heat rising without bound and the temperature holding, which is the opposite of how a real under-heated home behaves.

Delivered heat 13.7 to 92.8 kWh/day; achieved living temperature 18.3 °C at the best rating down to 16.0 °C at the worst.

| BER | home-days | heat, kWh/day | mean living temp |
| --- | --- | --- | --- |
| A | 21 | 13.72 | 18.28 °C |
| B | 49 | 24.71 | 17.56 °C |
| C | 56 | 35.12 | 17.54 °C |
| D | 14 | 54.42 | 15.98 °C |
| E | 14 | 92.81 | 16.08 °C |
| F | 14 | 87.16 | 15.99 °C |
| G | 14 | 74.35 | 16.28 °C |

## 7. Can each control actually fail? Magnitudes against resolutions

A negative control whose magnitude sits below its check's resolution cannot fail, and a control that cannot fail tests nothing. NC-D2-03 was in exactly that position and the first response was to file it as a recognised limitation (I-020); the amendment (I-034) is that **every control's magnitude is now set from a power analysis against its own check's resolution**, and is audited.

### The household-size marginal, measured three ways

| Question | Answer |
| --- | --- |
| Smallest shift the single-realisation band can see, with no noise | **12.82%** = 34.3 households |
| What the planted 10% shift produces | max abs z **2.1332** against a critical 2.7344 — below the band |
| Power of the same check on a genuine random draw of 1,092 | **42.6%** at 10%; 95% power needs 20% |
| Households needed for 95% power at 10% | **3,664** — Cobh has 5,257, the scaled town has 1,092 |
| False-positive rate at zero shift | 0.0595 against a declared alpha of 0.05 — the band is calibrated |

So 1,092 households do not carry the information to resolve a 10% shift whatever check is applied. The magnitude was the problem, not the care taken in applying the check.

### What made a fix possible, and it is not more seeds

The generator is **deterministic** in this marginal: across 40 independent seeds, in both the correct and the shifted arm, the across-run standard deviation of the household-size shares is **1.7e-16**. It reproduces its control totals exactly. Household type is the same; age band and sex do vary.

That is the whole key. The acceptance band is the multinomial sampling error of a 1,092-household *draw* — about 0.013018 in proportion near p = 0.25 — while the generator's own run-to-run error is zero. The band is therefore **about 28x (0.013 against 0.00046, the integerisation floor)** wider than the precision of the thing it tests, so a bias comfortably inside it is still an unambiguous defect. The band is not wrong; it is the right band for "could a town this size look like this by chance". It is the wrong band for "is the generator biased".

### The ensemble generator-bias check

`marginal_acceptance` is untouched and keeps its own control (NC-D2-05, a 40% shift, above the 12.82% resolution). The new check tests the ensemble mean of K runs against what the generator is contracted to reproduce, at the generator's own measured precision: standard error `max(sd/sqrt(K), half a household / n)` with a Bonferroni t band on K-1 degrees of freedom.

**K = 20**, minimum 4. Two independent routes agree. Information: a random draw needs 3,664 households for 95% power, the town has 1,092, so 3.36 -> K=4. Measured: bootstrapped over 40 correct and 40 shifted runs, K=4 is the smallest K with power >= 0.95 and false-positive rate <= 0.05.

20 rather than 4 because the standard deviation is estimated from the same K runs, so the band is a t quantile on K-1 degrees of freedom: 6.895 at K=4 against 3.074 at K=20, where the asymptotic value is 2.734. At K=20 the check pays 13% for estimating its own variance instead of 152%, and it keeps teeth on the marginals that genuinely do vary between seeds (age band SD up to 0.0032, sex 0.0074).

| | fires at |
| --- | --- |
| Single-realisation band | **34.3 households** |
| Ensemble check, K = 20 | **1.5 households** |
| The planted 10% shift moves | **26.8 households** |

Measured power **1.0**, false-positive rate **0.0**, margin about 16x. Power and false-positive rate are 1.0 and 0.0 exactly, not to within Monte Carlo error: with an across-run standard deviation of zero every bootstrap draw of K runs gives the identical statistic, so the rates are deterministic.

### The false-positive control changed the design

The literal instruction — test the ensemble mean against SAPS — **fails**, and measurably. Testing the ensemble mean against RAW SAPS proportions rejects a CORRECT population at every K from 4 upwards: measured max |z| 54.9 against a t band of 6.90 at K=4 and 3.07 at K=20.

The declared person-total repair moves the two-person share by -0.0251 and the three-person share by +0.0228 so the scaled town satisfies both of R03's ranges, which Cobh's real 2.6913 persons per household makes jointly unsatisfiable otherwise (I-012, D-010). That is larger than the 10% shift being planted, and it is deliberate and necessary.

The ensemble tests the generator against the target the declared procedure produces, and the target's own deviation from SAPS is bounded separately and reported. Two questions, two references, both checked - collapsing them into one is how a check becomes either blind or always-firing. The target's deviation from SAPS is 1.9827 against a budget of 2.7344: **within budget = True**.

### Every control audited

26 audited — 24 deterministic, 2 statistical. **Below their own resolution: none.** The split matters: for a check whose detection is an exact predicate the resolution is the threshold, and the quantity to report is the margin.

| Control | Kind | Fires at | Margin |
| --- | --- | --- | --- |
| NC-W2-02 | deterministic | 23.0 | 1.07x the band edge |
| NC-D2-04 | deterministic | anything above 6.5 W/K/m2 | 13% above the ceiling |
| NC-W2-03 | deterministic | apartment < every house type | 1.13x the band edge |
| NC-W2-08 | deterministic | 0.463 | 1.31x the band edge |
| NC-W2-07 | deterministic | 1.5414 | 1.54x the band edge |
| NC-W2-01 | deterministic | 1.0 | 1.60x the band edge |
| NC-W2-04 | deterministic | HAS02 share + 0.12 | 2.20x the band edge |
| NC-W2-05 | deterministic | 3x the national ratio (3.92) | 2.55x the band edge |
| NC-D2-02 | deterministic | any gap below 274 days | 183 days below the threshold, a factor of 3.0 |
| NC-D2-05 | deterministic | a 12.82% shift, giving max /z/ 2.7344 | 3.1x the resolution in shift fraction |
| NC-W2-06 | deterministic | 0.05 | 5.00x the band edge |
| T10-planted-arm | statistical | first-position share 27.41% for 95% power at alpha=0.01 | 8.1x the minimum detectable departure from 25% |
| NC-D3-02 | statistical | first-position share 29.9% for 95% power at alpha=1e-06 | 9.2x the minimum detectable departure from 25% |
| NC-D2-03 | deterministic | 1.5 households (t band 3.074 on 19 df, standard-error floor of half a household in 1,092) | 16x the resolution |
| NC-D1-01 | deterministic | any single entity changing | 22x the minimum |
| NC-D4-02 | deterministic | 0.1% of gross daily throughput | 30x the tolerance |
| NC-D4-01 | deterministic | any overlap of one minute or more | 60x the minimum |
| NC-D1-02 | deterministic | any name matching '(?i)occupan' | exact match, no margin needed |
| NC-D1-03 | deterministic | any name in the hidden-layer or MIMIC-latent set | exact match |
| NC-D1-04 | deterministic | any OBS field with an empty mechanism | exact |
| NC-D1-05 | deterministic | any value outside the declared enum | exact |
| NC-D2-01 | deterministic | any parent outside [16, 50] at birth | 16 years below the lower bound |
| NC-D3-01 | deterministic | any name matching '(?i)medical' | exact match |
| NC-D5-01 | deterministic | any name matching '(?i)occupan' | exact match |
| NC-D5-02 | deterministic | any difference at all, about 1e-13 W in double precision | about 14 orders of magnitude |
| NC-D6-01 | deterministic | any difference at all | about 10 orders of magnitude |

**Thinnest margin: NC-W2-02 at 1.07x.** 24.6 C is I-032's measured value exactly. The margin is only 1.07x the band edge, and deliberately: the band's upper edge is 23 C and the real fault sat at 24.6, so a control planted far beyond it would not demonstrate that the band is placed correctly. This is the thinnest margin in the set and the audit flags it. 5 other controls also sit under 2x and are listed below.

**T10 was audited although it is an E1-6 criterion rather than a negative control.** Planted first-position share 44.66% realised at n=7,516 responses from a 1.6 odds multiplier (measured power 1.000); fires at first-position share 27.41% for 95% power at alpha=0.01; margin 8.1x the minimum detectable departure from 25%. A planted effect below its test's resolution would make T10 pass for the wrong reason. It is not: the clean arm's 126,007 responses give chi-square 0.978 at p = 0.81, so the test is not simply always firing.

## 8. Negative controls: expected against observed

Each control declares the check that must reject it and the message fragment that identifies **why**. A generic failure, or a failure in another check, is classified as a harness defect rather than a pass.

| Control | Intended test | Expected | Observed | Outcome |
| --- | --- | --- | --- | --- |
| NC-D1-01 — Order-dependent RNG mutation | `tests.test_determinism.test_draws_are_order_independent` | tests.test_determinism.test_draws_are_order_independent raises AssertionError containing 'depend on execution order' | AssertionError: RNG draws depend on execution order: 22 of 24 entities changed value when visited in a different order (first: P-000002). Design 8.2 requires a counter-based RNG whose results do no... | **PASS** |
| NC-D1-02 — GT column in an OBS file (occupancy count in an edge export) | `baile_nua.schema.access.audit_frame (tests.test_leakage)` | baile_nua.schema.access.audit_frame (tests.test_leakage) raises LeakageError containing 'R09' | LeakageError: D19 (edge_exports): forbidden field name(s) present - 'occupancy_count' matches '(?i)occupan'. R09 / E0-8: no occupancy, presence or person-level field is ever transmitted; design 5.1... | **PASS** |
| NC-D1-03 — MIMIC latent trait column in an observable export | `baile_nua.schema.access.assert_no_forbidden_patterns` | baile_nua.schema.access.assert_no_forbidden_patterns raises LeakageError containing 'person-level field' | LeakageError: D19 (edge_exports): forbidden field name(s) present - 'privacy' matches 'person-level field (design 5.1 hidden layer or 5.14 MIMIC latent)'. R09 / E0-8: no occupancy, presence or pers... | **PASS** |
| NC-D1-04 — OBS field with no declared real-world mechanism | `baile_nua.schema.model.load (tests.test_schema)` | baile_nua.schema.model.load (tests.test_schema) raises Exception containing 'must name the real-world mechanism' | SchemaError: D99 (nc_obs_no_mechanism) is OBS, so design 6.5 rule 1 applies: every field must name the real-world mechanism that would produce it. Fields with no mechanism: ['true_flexibility_poten... | **PASS** |
| NC-D1-05 — Enum violation in a ground-truth dataset | `baile_nua.schema.validate.validate_frame` | baile_nua.schema.validate.validate_frame raises ValidationError containing 'not in enum' | ValidationError: 1 schema violation(s) in D11:   - D11.zone: values ['spaceship'] are not in enum zone = ['bathroom', 'bedroom', 'hall', 'in_transit', 'kitchen', 'living', 'out_of_model', 'outside'... | **PASS** |
| NC-D2-01 — A population with a 10-year-old parent | `baile_nua.population.households.check_plausibility` | baile_nua.population.households.check_plausibility raises PlausibilityViolation containing 'parent age at birth' | PlausibilityViolation: 4 plausibility violation(s); first: {'household_id': 'H-NC0001', 'rule': 'parent age at birth in [16, 50] for sex F', 'detail': 'P-NC0001 (age 10, F) would have been 0 at the... | **PASS** |
| NC-D2-02 — Siblings born three months apart who are not twins | `baile_nua.population.households.check_plausibility` | baile_nua.population.households.check_plausibility raises PlausibilityViolation containing 'siblings' | PlausibilityViolation: 1 plausibility violation(s); first: {'household_id': 'H-NC0002', 'rule': 'siblings >= 274 days apart unless twins', 'detail': 'ages 6 and 6.25 differ by less than 0.75 years'} | **PASS** |
| NC-D2-04 — A building whose derived fabric is outside the plausible Irish range | `baile_nua.physics.archetype.derive_rc` | baile_nua.physics.archetype.derive_rc raises Exception containing 'outside the published plausible range' | ImplausibleFabricError: derived specific heat loss 8.76 W/(m2 K) is outside the published plausible range [0.25, 6.5] for a detached of 30 m2 built pre 1919 rated G. Fabric parameters are not silen... | **PASS** |
| NC-D2-05 — Household-size marginal with 40% of one category shifted | `baile_nua.population.joint_metrics.marginal_acceptance` | baile_nua.population.joint_metrics.marginal_acceptance raises MarginalShiftDetected containing 'exceeds the simultaneous band' | MarginalShiftDetected: marginal rejected: observed max /z/ 8.5288 exceeds the simultaneous band 2.7344 over 8 categories (total variation distance 0.0985) | **PASS** |
| NC-D3-01 — A D25 participant frame carrying an ADR-004 forbidden field | `baile_nua.schema.access.assert_no_forbidden_patterns` | baile_nua.schema.access.assert_no_forbidden_patterns raises LeakageError containing 'medical_device_dependence' | LeakageError: D25 (mimic_export): forbidden field name(s) present - 'medical_device_dependence' matches '(?i)medical'. R09 / E0-8: no occupancy, presence or person-level field is ever transmitted; ... | **PASS** |
| NC-D3-02 — Responses in which display position drives the choice | `chi-square on chosen_display_position (T10)` | chi-square on chosen_display_position (T10) raises PositionBiasDetected containing 'display position predicts the choice' | PositionBiasDetected: display position predicts the choice: position 1 chosen 69.6% of the time against an expected 25.0%, chi2=4248.8, p=0.00e+00. Design 5.14's T10 requires position to carry no i... | **PASS** |
| NC-D4-01 — A person present in two buildings at the same time | `baile_nua.validation.invariants.check_no_double_occupancy` | baile_nua.validation.invariants.check_no_double_occupancy raises InvariantViolation containing 'P-000001' | InvariantViolation: 1 V0 invariant(s) violated (design 7.2, zero tolerance):   - no_double_occupancy [7.2 / R23 / 5.4]: 1 violation(s)       {'person_id': 'P-000001', 'kind': 'overlapping_presence'... | **PASS** |
| NC-D4-02 — A daily energy balance with a 3% heat-balance leak | `baile_nua.validation.invariants.check_energy_closure` | baile_nua.validation.invariants.check_energy_closure raises InvariantViolation containing 'closure' | InvariantViolation: 1 V0 invariant(s) violated (design 7.2, zero tolerance):   - energy_closure [7.2 (relative tolerance 0.001)]: 20 violation(s)       {'kind': 'energy_does_not_close', 'building_i... | **PASS** |
| NC-D5-01 — An edge export with an occupancy column added after build_export | `baile_nua.io.write_dataset (schema access audit)` | baile_nua.io.write_dataset (schema access audit) raises LeakageError containing 'occupancy' | LeakageError: D19 (edge_exports): forbidden field name(s) present - 'occupancy_count' matches '(?i)occupan'. R09 / E0-8: no occupancy, presence or person-level field is ever transmitted; design 5.1... | **PASS** |
| NC-D5-02 — A non-deterministic appliance render | `byte equality of two renders from one signature_seed` | byte equality of two renders from one signature_seed raises RenderNotDeterministic containing 'differs by up to' | RenderNotDeterministic: the same cycle rendered twice from the same signature_seed differs by up to 73.4 W. Design 8.2 requires every draw to come from the counter-based stream keyed by the entity ... | **PASS** |
| NC-D6-01 — Shared mutable state between households in the day loop | `order-independence of per-household results` | order-independence of per-household results raises SharedStateDetected containing 'changed their result' | SharedStateDetected: 50 of 50 households changed their result when the estate was run in a different order (first: H-000000, 7571.411627 against 7572.115224 Wh). Design 8.2 forbids shared mutable s... | **PASS** |
| NC-W2-01 — A package whose electricity is 1.6x its CSO cell (the I-027 fault) | `baile_nua.plausibility PL-ELEC-01` | baile_nua.plausibility PL-ELEC-01 raises PlausibilityCheckFired containing 'PL-ELEC-01 rejected the package' | PlausibilityCheckFired: plausibility check PL-ELEC-01 rejected the package: measured 1.6 against 0.40 to 1.00 of the DBEREL01 cell (tolerance ratio in [0.40, 1.00]) | **PASS** |
| NC-W2-02 — A package with a 24.6 C annual median indoor temperature (I-032) | `baile_nua.plausibility PL-TEMP-01` | baile_nua.plausibility PL-TEMP-01 raises PlausibilityCheckFired containing 'PL-TEMP-01 rejected the package' | PlausibilityCheckFired: plausibility check PL-TEMP-01 rejected the package: measured {'median_c': 25.68, 'share_above_28c': 0.3261, 'max_c': 53.47} against declared band [A]: median 15-23 C, <=5% a... | **PASS** |
| NC-W2-03 — A package whose apartments are larger than its terraces (I-031) | `baile_nua.plausibility PL-AREA-01` | baile_nua.plausibility PL-AREA-01 raises PlausibilityCheckFired containing 'PL-AREA-01 rejected the package' | PlausibilityCheckFired: plausibility check PL-AREA-01 rejected the package: measured {'apartment': 120.8, 'detached': 130.6, 'semi-detached': 107.2, 'terraced': 106.9} against {'nda08_year': '2022'... | **PASS** |
| NC-W2-04 — An appliance ownership prior of 1.00 against a HAS02 share near 0.5 | `baile_nua.plausibility PL-APPL-01` | baile_nua.plausibility PL-APPL-01 raises PlausibilityCheckFired containing 'PL-APPL-01 rejected the package' | PlausibilityCheckFired: plausibility check PL-APPL-01 rejected the package: measured 4 of 5 base priors within band against HAS02 2019 ownership share, -0.20/+0.12 (tolerance base prior within -0.2... | **PASS** |
| NC-W2-05 — A town whose electricity-to-gas ratio is ten times the national one | `baile_nua.plausibility PL-MIX-01` | baile_nua.plausibility PL-MIX-01 raises PlausibilityCheckFired containing 'PL-MIX-01 rejected the package' | PlausibilityCheckFired: plausibility check PL-MIX-01 rejected the package: measured 13.069 against {'sei01_year': '2022', 'national_elec_over_gas_ratio': 1.307} (tolerance simulated ratio in [0.25,... | **PASS** |
| NC-W2-06 — An ownership slope of 0.25 per person against an HS219 slope of 0.029 | `baile_nua.plausibility PL-APPLSIZE-01` | baile_nua.plausibility PL-APPLSIZE-01 raises PlausibilityCheckFired containing 'PL-APPLSIZE-01 rejected the package' | PlausibilityCheckFired: plausibility check PL-APPLSIZE-01 rejected the package: measured 4 of 5 slopes within band against HS219 2015 slope, +/-0.05 per person (tolerance slope within +/-0.05 per p... | **PASS** |
| NC-W2-07 — Room counts independent of dwelling type, with every marginal intact | `baile_nua.population.joint_f2063 PL-ROOMS-01` | baile_nua.population.joint_f2063 PL-ROOMS-01 raises PlausibilityCheckFired containing 'PL-ROOMS-01 rejected the package' | PlausibilityCheckFired: PL-ROOMS-01 rejected the package | **PASS** |
| NC-W2-08 — A year with no seasonality: load spread too evenly to be real | `baile_nua.plausibility PL-PEAK-01` | baile_nua.plausibility PL-PEAK-01 raises PlausibilityCheckFired containing 'PL-PEAK-01 rejected the package' | PlausibilityCheckFired: plausibility check PL-PEAK-01 rejected the package: measured {'load_factor': 0.6059, 'peak_over_mean': 1.6504, 'mean_day_peak_hour': 18, 'mean_day_trough_hour': 4, 'overnigh... | **PASS** |
| NC-GC-01 — A T6 null cohort with a causal effect secretly planted in it | `baile_nua.mimic.gc_modes.assess (causally_unrelated arm)` | baile_nua.mimic.gc_modes.assess (causally_unrelated arm) raises NullControlDetectedAnEffect containing 'SOFTWARE_DEFECT' | NullControlDetectedAnEffect: the T6 null control reported SOFTWARE_DEFECT: incremental R2 0.05006 exceeds the detectable floor on data with a planted effect of exactly zero and an OBSERVED confound... | **PASS** |
| NC-GC-02 — The non-identifiable G-C mode with the correlation lowered to r = 0.97 | `baile_nua.mimic.gc_modes.assess (non_identifiable arm)` | baile_nua.mimic.gc_modes.assess (non_identifiable arm) raises ModeIsNotAdversarial containing 'recoverable' | ModeIsNotAdversarial: the non-identifiable mode reported SOFTWARE_DEFECT: the difference +0.98 is distinguishable from zero (standard error 0.11), so the separate effects ARE recoverable here and t... | **PASS** |
| NC-GC-03 — A cohort claiming no latent classes while containing three | `baile_nua.mimic.gc_modes.cluster_validity_gap` | baile_nua.mimic.gc_modes.cluster_validity_gap raises ClusterGateDetectedPlantedClusters containing 'found structure' | ClusterGateDetectedPlantedClusters: the validity gate found structure the cohort denied having: a silhouette of 0.795 at k = 3 stands +53.59 SD above the no-structure reference, on data with no lat... | **PASS** |
| NC-JOINT-01 — A population with the right economic-status marginal and I-069's wrong joint | `baile_nua.validation.joint_person.compare` | baile_nua.validation.joint_person.compare raises JointValidationRejectedTheBrokenPopulation containing 'impossible cells populated' | JointValidationRejectedTheBrokenPopulation: joint_person returned 'FAIL' with 6 impossible cells populated and a total variation distance of 0.4291 - it rejected a population whose economic status ... | **PASS** |
| NC-VENUE-01 — A presence record placing one person at a venue and at home at once | `baile_nua.validation.venue_presence.check_venue_presence_consistency` | baile_nua.validation.venue_presence.check_venue_presence_consistency raises VenueCheckRejectedTheBrokenRecord containing 'person_at_a_venue_and_at_... | VenueCheckRejectedTheBrokenRecord: the venue check rejected the record: person_at_a_venue_and_at_home_at_once=1, person_in_two_places_at_once=1 | **PASS** |
| NC-EXPORT-01 — A compliance-only export that still carries the interval energy series | `tests/test_export_configurations_differ.py (energy-presence check)` | tests/test_export_configurations_differ.py (energy-presence check) raises ExportCheckFoundTheEnergySeries containing 'carries the interval energy s... | ExportCheckFoundTheEnergySeries: the compliance_only export carries the interval energy series, so its inference risk is home_30min's - measured at an occupancy AUC of 0.8655. This is I-067, and th... | **PASS** |
| NC-D2-03 — Household-size marginal with 10% of its mass shifted (ensemble generator-bias check) | `baile_nua.validation.ensemble_control.check_generator_bias (K=20 runs)` | baile_nua.validation.ensemble_control.check_generator_bias (K=20 runs) raises EnsembleBiasDetected containing 'generator bias detected' | EnsembleBiasDetected: generator bias detected: over K=20 runs the ensemble mean household-size marginal departs from the control totals the generator was given by max /z/ 50.0, against a Bonferroni... | **PASS** |

## 9. Known failures and recognised limitations

- **NC-D2-04 has a margin of only 1.13x** over its check's threshold (13% above the ceiling). Not a failure, and deliberate in this case, but it is the control closest to being unable to fire: The thinnest margin of any deterministic control, and deliberately so: the control exists to show the ceiling bites, and a fault far beyond it would not test the ceiling's position. The earlier version of this control used a 400 m2 house and came out INSIDE the range, which is the failure mode a 1.13 margin is one step away from.

- **NC-W2-01 has a margin of only 1.60x** over its check's threshold (1.60x the band edge). Not a failure, and deliberate in this case, but it is the control closest to being unable to fire: 1.60 is chosen, not arbitrary: E1's first device layer measured 16.35 kWh/home/day against a Co. Cork mean of 4,186 kWh/year for everything, which is a ratio of about 1.43 (I-027). The control plants slightly worse than the real defect so the check is shown to catch the fault that actually occurred.

- **NC-W2-02 has a margin of only 1.07x** over its check's threshold (1.07x the band edge). Not a failure, and deliberate in this case, but it is the control closest to being unable to fire: 24.6 C is I-032's measured value exactly. The margin is only 1.07x the band edge, and deliberately: the band's upper edge is 23 C and the real fault sat at 24.6, so a control planted far beyond it would not demonstrate that the band is placed correctly. This is the thinnest margin in the set and the audit flags it.

- **NC-W2-03 has a margin of only 1.13x** over its check's threshold (1.13x the band edge). Not a failure, and deliberate in this case, but it is the control closest to being unable to fire: I-031's actual measurement: the town's apartment median was 120.8 m2 against a terraced median of 106.9. An ordering predicate has no numeric band, so the margin is the ratio by which the ordering was violated.

- **NC-W2-07 has a margin of only 1.54x** over its check's threshold (1.54x the band edge). Not a failure, and deliberate in this case, but it is the control closest to being unable to fire: PL-ROOMS-01 requires at least half of the census gradient, and Cork County's detached-minus-apartment gap is 3.0828 rooms, so the band edge is 1.5414 rooms. The control plants INDEPENDENCE - room counts shuffled across dwelling types - which is I-031's actual regime and drives the gap to approximately zero, a margin of 1.5414 rooms below the edge. Reported as an absolute margin rather than a ratio because the planted value is zero and a ratio against zero is undefined; the audit's margin_ratio carries the rooms of headroom instead.

- **NC-W2-08 has a margin of only 1.31x** over its check's threshold (1.31x the band edge). Not a failure, and deliberate in this case, but it is the control closest to being unable to fire: A year in which every day is LP1's own average day. No seasonal and no day-to-day variation, so the only thing wrong with it is that the load is spread too evenly - which is what the upper bound exists to catch, and one of the tells 7.9 audits for. The magnitude needs no tuning: a mean-day-repeated year has a load factor of 0.6059 against a band edge of 0.4630 (LP1's 0.4129 plus the 0.05 allowance) by construction. It is surgical - the evening peak hour is 18:00 and the overnight taper 1.72, both LP1's own values - so it fires on the load-factor term alone and not by being implausible in every respect.

- **V0 invariant `no_child_alone` was not evaluated.** D11 presence is collected for the first 14 days only (a year of 1-minute presence for 147 people is 77 million rows for no E1 purpose), and the check needs every person's whole day. It is enforced INSIDE the activity engine for every day of the run by _enforce_child_supervision, and tested there; this package-level re-check is what is skipped, not the invariant.

## 10. ISSUES.md summary

101 issues raised. By severity: **Critical** 2, **High** 20, **Medium** 29, **Low** 12, **unstated** 37. Six are defects in MIMIC itself, recorded for its maintainers; nothing was edited in MIMIC.

| ID | Severity | Status | Title |
| --- | --- | --- | --- |
| I-001 | Critical | not stated | MIMIC local instance would write to PRODUCTION |
| I-002 | High | not stated | Production credentials in plaintext in the working tree |
| I-003 | Medium | not stated | `mimic_sd_generator.php` age-band separator defect |
| I-004 | Medium | closed | Brief paths did not resolve |
| I-005 | High | not stated | Execution machine is below the U21 minimum |
| I-006 | High | not stated | No test-mode rate-limit allowance exists in MIMIC |
| I-007 | Low | not stated | 10,000 unique participants cannot come from the E1 estate |
| I-008 | High | not stated | Eurostat HETUS has no Irish data in any wave |
| I-009 | Low | closed | Met Éireann historical-data host moved |
| I-010 | Medium | closed | CSO SAPS small-area file has no place names |
| I-011 | Medium | not stated | SAPS 2022 cannot supply two distributions the design needs |
| I-012 | Medium | not stated | R03's two targets are barely jointly satisfiable at Cobh's real household size |
| I-013 | Medium | not stated | The measured U03 comparison contradicts the design's own recommendation |
| I-014 | Low | not stated | No public Irish surname frequencies, and no non-Irish given-name lists |
| I-015 | Low | not stated | No authoritative public-figure register was found |
| I-016 | Medium | needs Brian's ruling | The Day-1 marginal threshold was mis-specified |
| I-017 | High | closed | Met Éireann station 1575 is Malin Head, not Roches Point |
| I-018 | Low | closed | CSO PxStat returns a bare 403 for an over-size CSV request |
| I-019 | Medium | not stated | Four physics input sets are declared assumptions |
| I-020 | Medium | not stated | The Day-2 "marginals shifted 10%" control is below the test's resolution |
| I-021 | High | not stated | Both MIMIC migrations fail on MySQL 8.0, including the GDPR compliance one |
| I-022 | Medium | not stated | MIMIC's compose file publishes MySQL on all interfaces |
| I-023 | High | not stated | MIMIC's "deterministic mulberry32" RNG overflows to float |
| I-024 | Low | not stated | `api/session.php` does not return the factorial `context_key` |
| I-025 | Critical | not stated | U17 and U19 are incompatible with MIMIC as it stands |
| I-026 | Medium | closed | PHP OPcache delayed the pool marker, mis-tagging a whole test arm |
| I-027 | High | Fixed, with a declared tuning exposure | The device layer had no public target, and was 40% over the national mean |
| I-028 | High | Fixed | The activity engine fragmented the day into 45 episodes |
| I-029 | High | Fixed | Six HETUS activity codes were mis-assigned |
| I-030 | Medium | Fixed, by reversing a Day-1 choice | The manifest's own content hash dominated the entire pipeline |
| I-031 | High | Fixed | Apartments were the size of houses, and the heating target could not see it |
| I-032 | High | Fixed | The F1 physics applied horizontal irradiance to vertical windows, and had no path for heat to leave |
| I-033 | High | Fixed | The thermostat proportioned on the outdoor temperature and never looked at the room |
| I-034 | High | Fixed, with a design amendment | Negative-control magnitudes were chosen, not derived; I-020 was the wrong response |
| I-035 | Medium | Open, needs Brian's ruling | The week 2/3 brief cites design content that does not exist in the frozen r3 |
| I-036 | CRITICAL | Open, blocks week 3 step 5 | U24's `<SSD_PATH>` is unsubstituted, and no external drive exists |
| I-037 | Low | Out of scope by decision | No "family of towns" mode: the generator is one calibrated town |
| I-038 | Medium | Open, needs the file | Design revision 4 is not present; DECISIONS.md Part C retained |
| I-039 | Medium | Open, declared gap | Three U27 plausibility families have no published Irish reference |
| I-040 | Low | Fixed (now checked) | Seven appliance ownership priors were assumptions that did not need to be |
| I-041 | Medium | Fixed | A declared source with a mappable row left unmapped |
| I-042 | Low | OPEN | The appliance ownership slopes are twice the published ones |
| I-043 | Medium | OPEN, | U30 cannot close I-039; peak demand is not in PxStat |
| I-039 | Medium | Closed for the | CLOSED at the aggregate level: ESB Networks Standard Load Profile LP1 |
| I-044 | Medium | OPEN, a known and declared failure | The simulated town has no overnight taper |
| I-045 | Low | OPEN, bounded and | Hot water volume rests on an unsourceable shower duration |
| I-046 | Medium | Fixed, and fixed by a mechanism rather than by noticing | A phrase search concluded "nothing published" and was wrong |
| I-047 | High | Fixed | Boiler vintage was read from the dwelling's build year |
| I-048 | Medium | OPEN as a | Comfort-taking cannot reproduce DBERNG01's flatness, and what that points at |
| I-049 | Medium | OPEN; blocks | Neither slice spans U22's held-out validation axis |
| I-049 | unstated | not stated | CLOSED by U31: the held-out slice exists and U22 passes on it |
| I-044 | unstated | not stated | CLOSED: the overnight taper, and a computation that was being thrown away |
| I-050 | Medium | OPEN, with the better metric identified | The overnight taper is a two-point ratio and can be moved by either point |
| I-051 | Low | OPEN, | The overnight profile is too low from 00:00 to 02:00 in both slices |
| I-050 | unstated | not stated | extended: distance-to-reference is the wrong scoring for a structurally one-sided metric |
| I-051 | unstated | not stated | CLOSED on the sleep timing; the residual is in a different layer |
| I-052 | Medium | OPEN, | The activity-to-load mix is wrong at the day's boundaries |
| I-053 | High | FIXED in the same step | Two vital-statistics sources were declared under the wrong matrix and never consumed |
| I-054 | Medium | OPEN, closes with the week 3 fabric work (I-048) | Fabric-retrofit D20 labels describe a change the week-2 series does not contain |
| I-055 | High | OPEN | the overnight drift is real, is NOT the DER assets, and the assets are masking it |
| I-056 | Medium | OPEN — worked around locally, root cause not fixed | `SynthBuilding`'s DER flags are undeclared attributes, so `dataclasses.replace` drops them |
| I-057 | High | OPEN, needs a declared | the ten-year run uses 2022's weather ten times |
| I-058 | Medium | OPEN | two plausibility checks score against calibration inputs, and the suite counts them as sourced |
| I-059 | High | FIXED, and the test re-run | the held-out slice's membership depends on the quantity under test |
| I-060 | Medium | declaration corrected; the check is kept and relabelled | U32's awake-share fit is a consistency check, not an independent validation |
| I-061 | Low | OPEN — resolving it is a schema change | `exposure` is declared per source, but DEAP's uses are section-level |
| I-062 | unstated | not stated | `retrofit_heat_pump` and `der_smart_controls` were reported "applied" and changed nothing |
| I-063 | unstated | not stated | ten D20 labels point at a step DEAP rates at zero |
| I-064 | unstated | not stated | the DEAP emitter derating applies to converted heat pumps, not to the town's own |
| I-065 | unstated | not stated | the model's declared move rate sits above the bound Census 2022 implies |
| I-066 | unstated | not stated | the provenance record could not see a library downgrade |
| I-067 | unstated | not stated | `compliance_only` exports the full energy series; the mitigation does not exist |
| I-068 | unstated | not stated | nobody in Baile Nua is ever away |
| I-069 | unstated | not stated | the population matches every marginal and gets the age × economic-status joint wrong by a third |
| I-070 | unstated | not stated | 33 people are in the town before they are born |
| I-071 | unstated | not stated | the build has two definitions of a person's age |
| I-072 | unstated | not stated | D28–D31 are built; E2-7 still fails, on D31's market series |
| I-073 | unstated | not stated | the tell audit's first run found four tells in the delivered observable view |
| I-074 | unstated | not stated | the observable view announces that it is synthetic, in all 26 manifests |
| I-075 | unstated | not stated | the MIMIC panel exists and is not linked *in time* |
| I-076 | unstated | not stated | D19's schema made design 7.8's `compliance_only` mitigation impossible to represent |
| I-077 | unstated | not stated | my regeneration chain reported "U31 ARTEFACT OK" from two-day-old inputs |
| I-078 | unstated | not stated | the engine conflated "outdoors" with "away from home" |
| I-079 | unstated | not stated | twice in one session I changed the model while a multi-process build was in flight |
| I-080 | unstated | not stated | I edited a running shell script and it restarted itself, destroying two hours of work |
| I-081 | unstated | not stated | the checkpoint recorded the hot water cylinder and the restore threw it away |
| I-082 | unstated | not stated | E1's gate report cited evidence older than the run it describes |
| I-083 | unstated | not stated | the youngest children wake latest, because an adult chronotype rule was extrapolated to toddlers |
| I-084 | unstated | not stated | the replay harness built a different model from the run, and reported it as a state gap |
| I-085 | unstated | not stated | D-075 cites a U31 comfort-off arm that was never run on the new population |
| I-086 | unstated | not stated | `w3_town_network_venues.json` quotes a stale projection and a stale free-disk figure, and cites a file that disagrees with it |
| I-087 | Medium | REPORT-TO-MIMIC | MIMIC's public API permits exactly one session per participant, so a panel cannot have waves on one id |
| I-088 | unstated | not stated | every year of the decade uses 2022's weather and 2022's calendar |
| I-089 | unstated | not stated | the scale basis structurally omits writer-flush cost, and E2-3's PASS rests on it |
| I-090 | unstated | not stated | model code was committed while both runs were in flight, so neither run's code state is recoverable |
| I-091 | unstated | not stated | the written D09 and the written D05 describe different populations |
| I-092 | unstated | not stated | the exporter imported the engine before the source registry |
| I-093 | unstated | not stated | two assumption-flag references in the merged export layer that no sweep entry names |
| I-094 | unstated | not stated | D27's three-band plan is four years out of vintage |
| I-095 | unstated | not stated | D21 surfaced two internal inconsistencies in D08 that no aggregate check would notice |
| I-096 | High | REPORT-TO-MIMIC | the researcher dashboard returns 504 on a waved panel, and the cause is the legacy bundle |

## 11. Decisions needed for weeks 2 and 3

### U03 — which scale-down method

Both are built and the method is a parameter; no default is hard-wired (D-013). The measurement recommends **proportional**. The choice is a section-11 decision and is put to Brian, not applied unilaterally.

### U11 — the section 7 margins

Still provisional (E0-4). Every threshold is in `config/thresholds.yaml` and labelled provisional in output. Two of them have now been exercised against real measurements and need settling: the 0.1% daily energy closure (met with four orders of magnitude to spare) and the marginal-shift detection resolution, which NC-D2-03 shows is about 12.8% at 1,092 homes and not the 10% design 9.3 assumes.

### U20 — which edge export configuration

All four are built and none is marked default, because design 7.8 defers the choice to after the inference test, which is week 3 work. E1 writes all four so that the test has something to compare.

### R09 / 7.8 — the inference claim

E1 establishes only that **no occupancy field is transmitted**. It does not and cannot establish that occupancy is not inferable; `edge/export.py` states that boundary in code. The inference test is week 3 (E0-8).

### The device layer's calibration status

Simulated annual electricity per dwelling now sits at 3,535 kWh against D24's CSO targets, with 33% of fossil-heated dwellings within +/-30% of their dwelling-type-and-BER cell. That is an engineering sanity check, not calibration: whether it is good enough is a WP1 question, and the held-out DBEREL02 comparison is the one to settle it against.

### MIMIC T2, T3 and T4

Started rather than E1-required, and each falls short for a reason that is a property of the instrument rather than of the implementation. Whether week 2 should change the instrument - a second probe pair for T4, a non-linear estimator for T2, larger planted separation for T3 - or accept the limitation, is a decision.

### Comfort-taking: the largest gap in the model

Measured space heat reaches only about a third of the CSO's gas figure, and the shortfall WIDENS with how new the dwelling is - from 0.43 for 1967-1999 homes to 0.19 for post-2005 ones - on an axis nothing was fitted to. E1's thermostat holds a fixed setpoint on a fixed timer; real occupants of well-insulated homes take the improvement as warmth rather than as saving. Design 5.3 locates the mechanism in COM-B and E1 deliberately does not wire it into the thermostat (D-022). Week 2 has to decide whether to build it, and if so whether the setpoint, the hours, or both respond to fabric and to price - because until it exists no consumption claim of any kind can be made, and the ablations design 9.4 asks for in week 2 will all be measured against a model that under-heats good houses.

### Whether one estate is the right E1 slice

The estate is faithful and homogeneous: 84% A or B rated, mean build year 2005, 49 of 50 homes on gas, no dwelling rated below C, no heat pump and no storage heater. That is what Cobh's small areas 047106015 and 047106012 are, and E0-7 asked for one estate. It means the year run exercises a narrow slice of the archetype library, which is why section 6 exists as a separate coverage run. Week 2 should decide whether to add a second, older estate, or to go to the full town earlier than planned.

### Storage for the ten-year E2 package

One town-year projects to 23.2 GB with the margin; ten years is 232 GB against 77.8 GB free on this machine. D-009 already declined to store 1-minute building state for this reason, but D18 is the observable deliverable and cannot be dropped the same way. Reduce the observation interval, keep a subset of homes at full rate, or find external storage - and the choice changes what the privacy inference test in 7.8 can be run on, so it is not purely an infrastructure decision.

### Hot water

There is no tank and no hot-water demand in E1, which is a large part of why the gas comparison lands where it does and which the stream writer records in UNMODELLED_D16_FIELDS. The immersion heater exists as an appliance with a load signature but heats nothing. Design 5.7 includes DHW; it was out of E1's scope and needs to be in week 2's, because it is both a sizeable load and the one most strongly tied to occupancy.

### The six MIMIC issues

I-021 to I-026 are recorded for MIMIC's maintainers and nothing was edited in MIMIC. Two are High and one is Critical. Someone has to decide who fixes them and when, because weeks 2 and 3 run against the same instance.

## 12. Test suite and provenance

`pytest`: **751 tests, 4 failures, 0 errors, 1 skipped** in 1323.6 s (`v1/evidence/junit.xml`).

69 public sources registered, each with URL, licence, SHA-256, intended use and model-development exposure in `sources/SOURCES.md`. Nothing can be read that is not declared there: `baile_nua.sources.require` re-hashes a file on every use and refuses it if the bytes have changed.

Model-development exposure (design 7.1): **design** 5, **none** 56, **tuning** 8.

8 sources are declared `tuning`-exposed, meaning a model parameter was adjusted against them: `cso.census.fy047b_economic_status_by_age_and_county`, `cso.cooking.hebeu106_heating_fuel_urban_rural`, `cso.cooking.hebeu34_cooking_fuel_urban_rural`, `cso.electricity.dbere101_by_dwelling_ber`, `cso.gas.dberng01_by_dwelling_ber`, `cso.housing.trs05_floor_area_by_authority`, `eurostat.hetus.tus_00startime`, `seai.ber.research_tool`. Design 7.1 makes **any validation claim that touches a tuning-exposed source a blocking failure**, which is why the construction-period tables are held out, asserted to stay unexposed, and reported separately in section 5 (D-015, D-021). Declaring the exposure is not a formality: it is what stops the same number being used to fit a parameter and then to vindicate it.

**No CER/ISSDA or other licensed or restricted data is used anywhere.** 4 sources are listed as deliberately not used, with a reason each: CER Smart Metering trial (ISSDA), CSO POWSCAR commuting microdata, Irish time-use diary microdata, IDEAL (UK). CER/ISSDA is named explicitly: True.

Master seed `20261008`; checkpoint chain head `98c6b38427643d6233ce496606a196156f33399c274b1b53b2c07a0fde2eb61a`; 365 checkpoints, chain verified.

Coupling: **C1**. E1 runs coupling mode C1: 15-minute network epochs with a 1-minute device and physics step. The epoch barrier aggregates net load onto the feeder; it does NOT solve a power flow. Design 8.2 marks C2 mandatory for network-sensitive research and design 9.3 moves C2, the co-simulation timing contract and pandapower to weeks 2 and 3. No voltage, loading, curtailment or network-constraint claim is made from E1 output.

---

> **UNVALIDATED SIMULATION EVIDENCE: E1 engineering candidate**
>
> Engineering verification only. No behavioural calibration is claimed.
