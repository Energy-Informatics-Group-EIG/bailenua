---
type: "index"
id: "MOC_Run"
status: "generated"
tags:
  - "index"
  - "moc"
playbook: "/Users/brianoregan/Desktop/HRSD_Occupants/PLAYBOOK_v3.1.md"
years_complete: 0
phases: 21
gates: 21
modules: 149
generated_by: "scripts/build_vault.py"
---

# MOC — The 2015–2026 replay

Playbook read from `/Users/brianoregan/Desktop/HRSD_Occupants/PLAYBOOK_v3.1.md`.

**Playbook status:** Approved 2026-10-14. Phase 0 in progress. Phase 1 starts on your word after the G0 report.

## The boundary (§1.2)

| layer | where | content |
|---|---|---|
| Base replay | Baile Nua | GT at full resolution, all 4,291 days; observable layer by era; household finance and emergent outcomes |
| 16a observation | BNIT, edge emulator per FX-BN-04 | PARA//EL/EdgeWare sensing for enrolled homes from enrolment date. Needs no LEC or FLEXUS build |
| 16b flexibility | BNIT, over the frozen replay | LEC programmes, signals, offers, delivery, settlement via BN-6/BN-7. Gated on the LEC and FLEXUS builds |
| Role views | BNIT | the seven role-scoped views, from the coupled run |

> The replay is frozen before any coupled run reads it. No coupled run writes into a base package.

## What sits in Baile Nua and what sits in BNIT (§1.2)

| scope | Baile Nua | BNIT |
|---|---|---|
| A–C, E, G, H, I, J, K, P | yes | — |
| D COVID restrictions, WFH, mortality | yes | — |
| F estates, growth, amenities | yes (projection-labelled after today) | alternative trajectories |
| F Abbeylands construction loads, LEC/MV | backlog, §11 | — |
| F/I transport, modes, CMATS, mode shift | — | yes |
| M uptake, endogenous selection, calibrated totals | yes | alternative uptake rates |
| N observable layer eras 1–2 | yes | era 3: enrolment + D18 (16a) |
| O crisis behaviour, bill-burden driven | yes | — |
| Household finance, comfort, energy poverty | yes | — |
| Flexibility services, any year | — | yes (16b) |
| Role-scoped views | — | yes |

## Phases and gates

| phase | title | effort | gate | status |
|---|---|---|---|---|
| [[Phase 00]] | Baseline, decisions, issue logging | 2 d | [[G0]] | in progress |
| [[Phase 01]] | Population defects | 5 d | [[G1]] | pending |
| [[Phase 02]] | Time axis | 6 d | [[G2]] | pending |
| [[Phase 03]] | DST and clocks | 5 d | [[G3]] | pending |
| [[Phase 04]] | Population base and the census checkpoint | 6 d | [[G4]] | pending |
| [[Phase 05]] | Vintaged rates and two price regimes | 7 d | [[G5]] | pending |
| [[Phase 06]] | Market and system data | 5 d | [[G6]] | pending |
| [[Phase 07]] | Life course and housing chain | 8 d | [[G7]] | pending |
| [[Phase 08]] | Institutional population and COVID behaviour | 10 d | [[G8]] | pending |
| [[Phase 09]] | Town growth and amenities | 8 d | [[G9]] | pending |
| [[Phase 10]] | Household finance | 8 d | [[G10]] | pending |
| [[Phase 11]] | M: technology uptake, endogenously selected | 7 d | [[G11]] | pending |
| [[Phase 12]] | N: observable layer by era | 7 d | [[G12]] | pending |
| [[Phase 13]] | O: crisis behaviour, bill-burden driven | 9 d | [[G13]] | pending |
| [[Phase 14]] | Emergent outcomes dataset | 5 d | [[G14]] | pending |
| [[Phase 15]] | Policy events, behaviour, data flaws | 6 d | [[G15]] | pending |
| [[Phase 16]] | Validation | 7 d | [[G16]] | pending |
| [[Phase 17]] | P: chained production | 6 d + 5.12 d runtime | [[G17]] | pending |
| [[Phase 18]] | 16a: PARA//EL / EdgeWare observation | 10 d | [[G18]] | pending |
| [[Phase 19]] | Role-scoped data views | 6 d | [[G19]] | pending |
| [[Phase 20]] | 16b: Flexibility services | 10 d | [[G20]] | pending |

## Years

| year | days | status | rows | packages |
|---|---|---|---|---|
| [[Year 2015]] | 365 | pending | — | — |
| [[Year 2016]] | 366 | pending | — | — |
| [[Year 2017]] | 365 | pending | — | — |
| [[Year 2018]] | 365 | pending | — | — |
| [[Year 2019]] | 365 | pending | — | — |
| [[Year 2020]] | 366 | pending | — | — |
| [[Year 2021]] | 365 | pending | — | — |
| [[Year 2022]] | 365 | pending | — | — |
| [[Year 2023]] | 365 | pending | — | — |
| [[Year 2024]] | 366 | pending | — | — |
| [[Year 2025]] | 365 | pending | — | — |
| [[Year 2026]] | 273 | pending | — | — |

Run sentinels are read from `work/replay_2015_2026/<year>/DONE.json` inside this worktree only. The live run's own directory is never opened.

## Estates

[[Cluain Ard]], [[Belgard]], [[Abbeylands]]

## Events

[[Cluain Ard completion 2019]], [[Belgard completion 2024]], [[Abbeylands phased completion to 2027]], [[SEM SMP to I-SEM switch]], [[COVID restrictions]], [[Vaccine rollout by age band]], [[Smart-meter rollout]], [[PARA--EL enrolment ramp]], [[Energy crisis]], [[Electricity credits]], [[MSS export payments]], [[Smoky coal ban]], [[Temporary-protection arrivals]], [[Recovery with conditional persistence]], [[One-off public holiday 18 March 2022]], [[St Brigid's Day holiday begins]], [[DST transitions across the span]], [[Census 2022 as t0 and as a test]]

## FLEXUS-family roles and privacy tiers

[[role_Homeowner_occupant]], [[role_PARA_EL]], [[role_EdgeWare]], [[role_FLEXUS]], [[role_DSO_LEC]], [[role_Regulator_CRU]], [[role_Modeller_researcher]]

[[tier_GT]], [[tier_META]], [[tier_OBS]], [[constraint_LC-AMI-01]], [[constraint_LC-AMI-03]], [[constraint_FX-BN-04]], [[constraint_FX-BN-05]], [[constraint_T-OBS]]

## Playbook open decisions (§8)

| ref | became | question | recommendation |
|---|---|---|---|
| D18 | [[D-117]] | The behavioural elasticity of heating response to bill burden (Phase 13) is the number the whole crisis layer turns on, and I do not know whether a usable Irish estimate exists. | Acquire the SEAI/CSO/ESRI studies in Phase 0 and report the elasticity you can source before Phase 13 starts. If no Irish estimate exists, the options are an A-numbered value with a sensitivity range, or no behavioural response at all — and I would rather tell you that at G0 than discover it in … |
| D19 | [[D-118]] | Which energy-poverty measure is primary (Phase 14). The ESRI expenditure measure and the SILC subjective measure disagree by construction — a well-insulated low-income home can pass one and fail the other. | Report both, never averaged, and name neither primary. The disagreement is informative. Validation in Phase 16 scores against SILC because that is what SILC publishes. |
| D20 | [[D-119]] | Income dynamics. SILC gives distributions by year, not household trajectories. A household's income over 11.75 years can follow the distribution's drift, or be redrawn each year, or track employment events from the life course. | Track the life course — employment change is already an event type — with the distribution as the anchor. Redrawing annually would destroy the cohort continuity that §1.1 exists to create. |
| D21 | [[D-120]] | NILM error model (Phase 18). Scoring PARA//EL's inferred appliances against GT needs a realistic error characterisation, and I have no source for PARA//EL's actual accuracy. | Supply measured PARA//EL accuracy if it exists; otherwise an A-numbered error model with the failed search recorded, and the scoring reported as indicative only. |
| D22 | [[D-121]] | Consent levels (Phases 18–19). "Presence where consented" and "shares upward only by the home's consented level" imply a consent model per home that does not exist. | A sourced or A-numbered consent distribution set in Phase 18, with the tiers named in the view specification so Phase 19's tests can assert against them. |

*These are the playbook's own D18–D22, not the `D-nnn` of `docs/DECISIONS.md`; they are left as text so the two numbering schemes cannot be confused.*

## Modules by package

### baile_nua (37)

| module | purpose | writes |
|---|---|---|
| [[baile_nua]] | Baile Nua / HRSD_Occupants — synthetic Irish town generator. | — |
| [[baile_nua.activity]] | activity subsystem (see docs/Baile_Nua_Technical_Design_Review_r3.md). | — |
| [[baile_nua.behaviour]] | Occupant behaviour mechanisms that are not activity scheduling. | — |
| [[baile_nua.bench]] | bench subsystem (see docs/Baile_Nua_Technical_Design_Review_r3.md). | — |
| [[baile_nua.calibration]] | D24 calibration targets: every target number, read from a file in sources/. | — |
| [[baile_nua.checkpoint]] | Hash-chained daily checkpoints and the daily exchange log (design 8.2). | — |
| [[baile_nua.cli]] | Command line entry points. | — |
| [[baile_nua.config]] | Configuration, loaded from YAML rather than written into call sites. | — |
| [[baile_nua.data]] | data subsystem (see docs/Baile_Nua_Technical_Design_Review_r3.md). | — |
| [[baile_nua.devices]] | devices subsystem (see docs/Baile_Nua_Technical_Design_Review_r3.md). | — |
| [[baile_nua.docgen]] | Generate the data dictionary for the evidence view from ``datasets.yaml``. | — |
| [[baile_nua.edge]] | edge subsystem (see docs/Baile_Nua_Technical_Design_Review_r3.md). | — |
| [[baile_nua.engine]] | engine subsystem (see docs/Baile_Nua_Technical_Design_Review_r3.md). | — |
| [[baile_nua.export]] | Dataset exporters: the declared datasets the frozen engine does not stream. | — |
| [[baile_nua.hashing]] | Canonical hashing. | — |
| [[baile_nua.ids]] | Identifier policy. | — |
| [[baile_nua.io]] | Validated, deterministic dataset I/O. | — |
| [[baile_nua.lifecourse]] | lifecourse subsystem (see docs/Baile_Nua_Technical_Design_Review_r3.md). | — |
| [[baile_nua.manifest]] | Run manifests (D23) — design 3.3 and 8.5. | — |
| [[baile_nua.mimic]] | HRSD -> MIMIC alignment (design 5.13, 5.14). | — |
| [[baile_nua.network]] | S11: the town's electrical network. | — |
| [[baile_nua.observation]] | observation subsystem (see docs/Baile_Nua_Technical_Design_Review_r3.md). | — |
| [[baile_nua.physics]] | physics subsystem (see docs/Baile_Nua_Technical_Design_Review_r3.md). | — |
| [[baile_nua.plausibility]] | U27: output plausibility against published Irish references. | — |
| [[baile_nua.population]] | population subsystem (see docs/Baile_Nua_Technical_Design_Review_r3.md). | — |
| [[baile_nua.privacy]] | Design 7.8: privacy inference risk of exported data. | — |
| [[baile_nua.reduce]] | Canonical reductions (design 8.2: "Floating-point sums run in fixed order"). | — |
| [[baile_nua.release]] | Release-package policy and storage projection (U28, R13). | — |
| [[baile_nua.render]] | render subsystem (see docs/Baile_Nua_Technical_Design_Review_r3.md). | — |
| [[baile_nua.report]] | The E1 gate report, generated from artefacts only. | — |
| [[baile_nua.rl]] | RL interface schema stub (design 9.3 day 1, design 7.6). | — |
| [[baile_nua.rng]] | Counter-based RNG and seed tree (design 8.2, reproducibility contract). | — |
| [[baile_nua.schema]] | Schema subsystem: ``datasets.yaml`` is the single source of truth (D-005). | — |
| [[baile_nua.sources]] | Source acquisition and the source-use register (brief; | — |
| [[baile_nua.sources_registry]] | The declared public sources for this build. | — |
| [[baile_nua.validation]] | Verification and validation harnesses (design 7). | — |
| [[baile_nua.weather]] | weather subsystem (see docs/Baile_Nua_Technical_Design_Review_r3.md). | — |

### baile_nua.activity (3)

| module | purpose | writes |
|---|---|---|
| [[baile_nua.activity.engine]] | The semi-Markov activity and household engine (design 5.3, R15, R16, R23). | — |
| [[baile_nua.activity.hetus]] | HETUS activity targets, and the Irish anchoring (design 5.3; | — |
| [[baile_nua.activity.sleep_timing]] | U32 part 2: bedtime and wake-time spread, from a time-use source (I-051). | — |

### baile_nua.behaviour (1)

| module | purpose | writes |
|---|---|---|
| [[baile_nua.behaviour.comfort_taking]] | U22: comfort-taking - rebound in efficient homes, prebound in poor ones. | — |

### baile_nua.bench (2)

| module | purpose | writes |
|---|---|---|
| [[baile_nua.bench.coverage]] | Archetype coverage: does the engine run every KIND of dwelling? The E1 estate is one real estate, and a real … | — |
| [[baile_nua.bench.determinism]] | The reproducibility contract, measured rather than asserted. | — |

### baile_nua.calibration (1)

| module | purpose | writes |
|---|---|---|
| [[baile_nua.calibration.targets]] | Readers for the D24 calibration targets. | — |

### baile_nua.devices (3)

| module | purpose | writes |
|---|---|---|
| [[baile_nua.devices.appliances]] | Activity-to-appliance triggering and the household electrical model (design 5.6, S10). | — |
| [[baile_nua.devices.der]] | PV, BESS, EV and heat pump: the flexible assets (design 5.6, S10). | — |
| [[baile_nua.devices.signatures]] | The appliance signature library, D22 (design 5.6, U05, risk K07). | — |

### baile_nua.edge (1)

| module | purpose | writes |
|---|---|---|
| [[baile_nua.edge.export]] | The edge export boundary, S13 / D19 (R09, E0-8, design 5.12, 7.8). | — |

### baile_nua.engine (9)

| module | purpose | writes |
|---|---|---|
| [[baile_nua.engine.calendar]] | The simulated calendar, S06 (design 5.10, E0-3 / U08, R20). | — |
| [[baile_nua.engine.calendar_events]] | WP6: the full event engine, S06 / D14 (design 5.10, R20, R21, K09). | — |
| [[baile_nua.engine.coupling]] | C2 coupling and the 8.2 co-simulation timing and safety contract. | — |
| [[baile_nua.engine.e1_run]] | The E1 slice driver: 50 homes, ~140 people, calendar year 2022 (E0-7). | — |
| [[baile_nua.engine.fork]] | Intervention replay by forking, with common random numbers (design 8.2). | — |
| [[baile_nua.engine.run]] | The E1 run engine: one full year of the 50-home estate (design 8.2, E0-7). | — |
| [[baile_nua.engine.slice_u23]] | The U23 mixed-age slice, and why it is selected differently from E1's. | — |
| [[baile_nua.engine.slice_u31]] | U31: a held-out validation slice spanning both ends of the fabric axis. | — |
| [[baile_nua.engine.stream_writer]] | Streams one estate-year to Parquet, one dataset at a time. | [[D10]], [[D11]], [[D13]], [[D16]], [[D17]], [[D17_aggregate]], [[D18]], [[D19]] |

### baile_nua.export (11)

| module | purpose | writes |
|---|---|---|
| [[baile_nua.export.__main__]] | ``python -m baile_nua.export <run_root> <out_root> [--subdir S] [--only D01,D02]`` Prints the export record … | — |
| [[baile_nua.export.absent]] | Why a declared dataset is NOT written, per dataset, in one place. | — |
| [[baile_nua.export.biographies]] | D21 - biographies, rendered from the written D05, D06, D08 and D09 parts. | [[D21]] |
| [[baile_nua.export.context]] | The run a set of exporters is pointed at, and the state they share. | — |
| [[baile_nua.export.dispatch]] | One entry point: :func:`export_all`. | — |
| [[baile_nua.export.from_evidence]] | D03, D09 and D20 out of the evidence JSON, as the schema declares them. | [[D03]], [[D09]], [[D20]] |
| [[baile_nua.export.nonsensor_datasets]] | D28 - D31, from :mod:`baile_nua.observation.nonsensor`. | [[D28]], [[D29]], [[D30]], [[D31]] |
| [[baile_nua.export.run_manifest]] | D23 - run manifests, written for runs that recorded no manifest of their own. | [[D23]] |
| [[baile_nua.export.structural]] | The t0 datasets: D01, D02, D05-D08, D14, D15, D22. | [[D01]], [[D02]], [[D05]], [[D06]], [[D07]], [[D08]], [[D14]], [[D15]], [[D22]] |
| [[baile_nua.export.tariffs]] | D27 - tariffs and contracts, as a RECORD ONLY. | [[D27]] |
| [[baile_nua.export.writer]] | One way out of this package: :func:`emit`. | — |

### baile_nua.lifecourse (4)

| module | purpose | writes |
|---|---|---|
| [[baile_nua.lifecourse.events]] | Life events and disruptions, S05 (design 5.9, 5.3, R08, R17; | — |
| [[baile_nua.lifecourse.hazards]] | WP5 life-course hazards, every one either published or declared (D24, I-040). | — |
| [[baile_nua.lifecourse.move_rate]] | U33: a sourced proxy for the household move rate, from Census 2022. | — |
| [[baile_nua.lifecourse.tenyear]] | WP5: the ten-year life course, 2022-2031 (design 5.3, 5.9; | — |

### baile_nua.mimic (12)

| module | purpose | writes |
|---|---|---|
| [[baile_nua.mimic.counters]] | The five MIMIC counters (design 5.14, E0-5 / U16). | — |
| [[baile_nua.mimic.crosswalk]] | MIMIC schema 1.1 crosswalk and schema diff (design 5.14 levels 1 and 2). | — |
| [[baile_nua.mimic.datasets]] | D25 (mimic_export, OBS) and D26 (mimic_answer_key, GT) from a MIMIC run. | — |
| [[baile_nua.mimic.e1_run]] | Rebuild the MIMIC panel and re-measure T1, T9 and T10 (E1 criterion 6). | — |
| [[baile_nua.mimic.extended_pool]] | The HRSD extended pool (design 5.14, U16 pool 2). | — |
| [[baile_nua.mimic.gc_modes]] | G-C: the adversarial generators, and the T6 null control (design 5.14). | — |
| [[baile_nua.mimic.panel]] | The linked Baile Nua panel, in survey waves across the decade (I-075). | — |
| [[baile_nua.mimic.provision]] | Provision a LOCAL-ONLY MIMIC instance (ISSUES.md I-001). | — |
| [[baile_nua.mimic.runner]] | The HRSD runner: synthetic participants through MIMIC's PUBLIC API (5.14 level 3). | — |
| [[baile_nua.mimic.tests]] | MIMIC verification tests T1 to T10 (design 5.14). | — |
| [[baile_nua.mimic.verify]] | MIMIC-side verification: database integrity, dashboard, purge (design 5.14 T1/T9). | — |
| [[baile_nua.mimic.willingness]] | The HRSD willingness model, generator G-B (design 5.14 independence protocol). | — |

### baile_nua.network (1)

| module | purpose | writes |
|---|---|---|
| [[baile_nua.network.lv]] | S11: the town's LV network, and the first solved power flow in the build. | — |

### baile_nua.observation (2)

| module | purpose | writes |
|---|---|---|
| [[baile_nua.observation.nonsensor]] | Design 6.4's non-sensor datasets, under 6.5's rules: D28, D29, D30, D31. | — |
| [[baile_nua.observation.sensors]] | The observation model, S12 (design 5.11, 6.5; | — |

### baile_nua.physics (9)

| module | purpose | writes |
|---|---|---|
| [[baile_nua.physics.archetype]] | Deriving F1/F2 grey-box RC parameters from the BER asset rating (design 5.7). | — |
| [[baile_nua.physics.boiler]] | U25: boiler losses and gas cooking - the other two terms the gas meter sees. | — |
| [[baile_nua.physics.deap_appendix_s]] | DEAP Appendix S: the published Irish fabric defaults, extracted not transcribed. | — |
| [[baile_nua.physics.deap_controls]] | DEAP Tables 4c and 4e: what a heating *system* change does, extracted not chosen. | — |
| [[baile_nua.physics.dhw]] | U25: domestic hot water - draw events, tank or instantaneous, immersion. | — |
| [[baile_nua.physics.fabric_assessed]] | Assessed element U-values from SEAI's BER Research Tool (I-048, week 3 step 1). | — |
| [[baile_nua.physics.passport_assets]] | Dated asset and occupancy events: the rest of I-054, and the I-062 fix. | — |
| [[baile_nua.physics.rc]] | F1/F2 grey-box RC building physics, Numba-compiled (design 5.7, 8.2). | — |
| [[baile_nua.physics.retrofit]] | Passport events that change the physics from their date (I-054, week 3 step 1). | — |

### baile_nua.plausibility (3)

| module | purpose | writes |
|---|---|---|
| [[baile_nua.plausibility.checks]] | The declared U27 plausibility checks. | — |
| [[baile_nua.plausibility.slp]] | ESB Networks Standard Load Profile LP1, as a peak and load-factor reference. | — |
| [[baile_nua.plausibility.suite]] | The U27 plausibility suite: declared checks, measured outputs, verdicts. | — |

### baile_nua.population (13)

| module | purpose | writes |
|---|---|---|
| [[baile_nua.population.ber]] | SEAI/CSO Building Energy Rating data for Co. | — |
| [[baile_nua.population.buildings]] | HRSD_Buildings at t0 (design 5.2, 5.7, S03; | — |
| [[baile_nua.population.econ_by_age]] | I-069's fix: the age profile within each economic status, from FY047B. | — |
| [[baile_nua.population.households]] | Whole-household synthesis (design 5.2 step 3, R03, R16). | — |
| [[baile_nua.population.ipf]] | Iterative proportional fitting (design 5.2 step 3, design 8.1). | — |
| [[baile_nua.population.joint_f2063]] | PL-ROOMS-01: the rooms x dwelling-type joint, against Census 2022 (F2063). | — |
| [[baile_nua.population.joint_metrics]] | Joint and spatial fidelity metrics for the U03 comparison (design 5.2 step 2). | — |
| [[baile_nua.population.names]] | Synthetic names (design 5.2 step 6, R26, R27, risk K12). | — |
| [[baile_nua.population.saps]] | CSO Census 2022 SAPS ingest for Cobh (design 5.2 step 1, R04, D24). | — |
| [[baile_nua.population.scale_down]] | U03: scaling Cobh to about 3,000 people — both methods (E0-1, design 5.2 step 2). | — |
| [[baile_nua.population.synthesise]] | The t0 population pipeline (design 5.2; | — |
| [[baile_nua.population.traits]] | MIMIC latent traits and bounded-rationality parameters (design 5.2 step 5, 5.13, 5.14). | — |
| [[baile_nua.population.venues]] | WP7 venues: where people are when they are not at home. | — |

### baile_nua.privacy (2)

| module | purpose | writes |
|---|---|---|
| [[baile_nua.privacy.inference]] | Design 7.8's inference attacks, measured against Baile Nua's own ground truth. | — |
| [[baile_nua.privacy.threat_model]] | Design 7.8's threat model, which the design requires **before** U20. | — |

### baile_nua.release (4)

| module | purpose | writes |
|---|---|---|
| [[baile_nua.release.packages]] | Design 6.3: the three delivery packages, and the rules that keep them apart. | — |
| [[baile_nua.release.policy]] | What the release package materialises, and what it renders on demand. | — |
| [[baile_nua.release.storage]] | Is there a genuinely external drive, and how much room is really on it? This exists because of I-036. | — |
| [[baile_nua.release.tell_audit]] | Design 7.9 item 4: the automated tell audit. | — |

### baile_nua.report (4)

| module | purpose | writes |
|---|---|---|
| [[baile_nua.report.artefacts]] | Produces the remaining E1 evidence artefacts. | — |
| [[baile_nua.report.datasets_md]] | The dataset catalogue, generated from the files on disk. | — |
| [[baile_nua.report.e1_gate]] | Builds ``docs/E1_gate_report.md`` from test artefacts only. | — |
| [[baile_nua.report.e2_gate]] | The E2 gate report, generated from artefacts so a figure cannot be typed. | — |

### baile_nua.rl (1)

| module | purpose | writes |
|---|---|---|
| [[baile_nua.rl.interface]] | The RL information boundary, as data (design 7.6). | — |

### baile_nua.schema (3)

| module | purpose | writes |
|---|---|---|
| [[baile_nua.schema.access]] | Access-class enforcement: GT / OBS / META separation. | — |
| [[baile_nua.schema.model]] | Parse and validate ``datasets.yaml`` into typed objects. | — |
| [[baile_nua.schema.validate]] | Validators generated from ``datasets.yaml``. | — |

### baile_nua.validation (19)

| module | purpose | writes |
|---|---|---|
| [[baile_nua.validation.ablation]] | U22: the comfort-taking ablation, and the measurement it exists to make. | — |
| [[baile_nua.validation.assumption_sweep]] | U30: sweep every remaining ``[A]`` assumption flag against PxStat. | — |
| [[baile_nua.validation.behaviour_ablation]] | Week 2 step 4: WP4 behaviour depth, with ablations. | — |
| [[baile_nua.validation.control_power_audit]] | Every negative control's magnitude, against its check's resolution. | — |
| [[baile_nua.validation.controls_day1]] | Negative controls for Day 1 (design 9.3 row 1). | — |
| [[baile_nua.validation.controls_day2]] | Negative controls for Day 2 (design 9.3 row 2). | — |
| [[baile_nua.validation.controls_day3to6]] | Negative controls for days 3 to 6, as design 9.3 names them. | — |
| [[baile_nua.validation.controls_plausibility]] | Expected-failure negative controls for the U27 plausibility suite. | — |
| [[baile_nua.validation.controls_week2]] | Negative controls for the G-C generator modes and the T6 null control. | — |
| [[baile_nua.validation.controls_week3]] | Week-3 negative controls: deliberately broken artefacts the checks must reject. | — |
| [[baile_nua.validation.e1_invariants]] | Runs the V0 invariants over a written release package. | — |
| [[baile_nua.validation.ensemble_control]] | The generator-bias ensemble check, and the NC-D2-03 controls built on it. | — |
| [[baile_nua.validation.heldout_u31]] | U31: the held-out gas gradient, run from the repository rather than a script. | — |
| [[baile_nua.validation.invariants]] | V0 hard invariants — zero tolerance (design 7.2). | — |
| [[baile_nua.validation.joint_person]] | Design 5.2: the PERSON-LEVEL joint of age and economic status. | — |
| [[baile_nua.validation.negative_control]] | Negative-control harness with expected-failure assertions. | — |
| [[baile_nua.validation.overnight_lp1]] | Load per awake person against ESB Networks LP1. | — |
| [[baile_nua.validation.power]] | Power analysis for the marginal-acceptance checks. | — |
| [[baile_nua.validation.venue_presence]] | Design 9.4 week 3: "venue presence consistent with person presence". | — |

### baile_nua.weather (2)

| module | purpose | writes |
|---|---|---|
| [[baile_nua.weather.site]] | The single weather realisation: D15 site truth and D31 station observable. | — |
| [[baile_nua.weather.station]] | Met Éireann station data, and the one weather realisation (design 6.5 rule 2). | — |

### build_vault (1)

| module | purpose | writes |
|---|---|---|
| [[build_vault]] | Regenerate the Obsidian vault at ``vault/`` from the repository. | — |

### replay_supervisor (1)

| module | purpose | writes |
|---|---|---|
| [[replay_supervisor]] | Supervisor for the chained 2015-2026 historical replay. | — |

## Index

[[MOC_Datasets]], [[MOC_Sources]], [[MOC_Decisions]]
