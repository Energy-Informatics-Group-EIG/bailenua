---
type: "index"
id: "MOC_Decisions"
status: "generated"
tags:
  - "index"
  - "moc"
decisions: 134
assumptions: 64
issues: 113
open_issues: 25
generated_by: "scripts/build_vault.py"
---

# MOC — Decisions, assumptions and issues

134 decisions, 64 assumptions and 113 issues.

## Decisions

| id | date | title | reversible |
|---|---|---|---|
| [[E0-1]] | 2026-10-08 | U03 scale-down | binding input |
| [[E0-2]] | 2026-10-08 | U04 time-use source | binding input |
| [[E0-3]] | 2026-10-08 | U08 calendar | binding input |
| [[E0-4]] | 2026-10-08 | U11 thresholds | binding input |
| [[E0-5]] | 2026-10-08 | U16 MIMIC pools | binding input |
| [[E0-6]] | 2026-10-08 | U21 hardware | binding input |
| [[E0-7]] | 2026-10-08 | E1 scope | binding input |
| [[E0-8]] | 2026-10-08 | R09 interpretation | binding input |
| [[D-001]] | 2026-10-08 | The binding design document is the revision-3 file found at the project root, copied to … | Yes |
| [[D-001a]] | 2026-10-10 | Amended: the single design reference is now docs/Baile_Nua_Technical_Design_Review_r4.md. | Yes |
| [[D-002]] | 2026-10-08 | <MIMIC_PATH> resolved to /Users/brianoregan/Documents/GitHub/mimic | Yes |
| [[D-003]] | 2026-10-08 | The local MIMIC instance runs from an isolated copy at work/mimic_local/, never from the … | Yes |
| [[D-004]] | 2026-10-08 | Python 3.12 for the baile_nua venv | Yes |
| [[D-005]] | 2026-10-08 | One YAML file (baile_nua/schema/datasets.yaml) is the single source of truth for all … | No (architectural) |
| [[D-006]] | 2026-10-08 | Access class is carried in the schema, not in code, and the leakage test is generated … | No (architectural) |
| [[D-007]] | 2026-10-08 | Observable IDs are HMAC-SHA256-derived opaque strings keyed by premises, with the key … | No (architectural) |
| [[D-008]] | 2026-10-08 | Philox-4x32-10 counter-based RNG, keyed (master_seed, stream, entity_id, sim_day, … | No (architectural) |
| [[D-009]] | 2026-10-08 | The E1 slice does not store 1-minute building state (U07 option b); | Yes |
| [[D-010]] | 2026-10-08 | The scale-down factor is the midpoint of the feasible interval derived from both of R03's … | Yes |
| [[D-011]] | 2026-10-08 | "Area type" for U03 method (a)'s stratification is electoral division × tenure tertile, … | Yes |
| [[D-012]] | 2026-10-08 | Joint and spatial fidelity are measured as between-small-area quantities (Spearman … | No (architectural) |
| [[D-013]] | 2026-10-08 | Both U03 methods stay in the code and the method is a parameter; | Yes |
| [[D-014]] | 2026-10-09 | Shared appliances are triggered once per household episode — a maximal run of overlapping … | No (architectural) |
| [[D-015]] | 2026-10-09 | DBEREL01 (dwelling type × BER band) is declared with model_development_exposure="tuning" … | No (architectural) |
| [[D-016]] | 2026-10-09 | An activity whose HETUS daily target is below its own episode floor is spent as an … | Yes |
| [[D-017]] | 2026-10-09 | The checkpoint for day N records the state at the start of day N and is written before … | Yes |
| [[D-018]] | 2026-10-09 | The E1 estate's seed small area is chosen as the one whose own mean household size is … | Yes |
| [[D-019]] | 2026-10-09 | The dataset manifest's content hash (hash_frame) is row-order sensitive and column-order … | Yes |
| [[D-020]] | 2026-10-09 | Room counts are allocated to dwellings by size rank (dwelling type and bedrooms) with … | Yes |
| [[D-021]] | 2026-10-09 | The tuned/held-out source split is mirrored on both fuels: DBEREL01 and DBERNG01 … | No (architectural) |
| [[D-022]] | 2026-10-09 | The flatness of measured gas consumption across BER bands is treated as a finding to … | Yes |
| [[D-023]] | 2026-10-09 | Solar gain is computed from the irradiance incident on the glazing, transposed onto … | Yes |
| [[D-024]] | 2026-10-09 | Any series the solver uses is carried on its result and consumed by the writer, never … | No (architectural) |
| [[D-025]] | 2026-10-09 | The room thermostat lives inside the solver, proportioning on the indoor temperature over … | No (architectural) |
| [[D-026]] | 2026-10-09 | Power analysis for the household-size marginal check, and the ensemble generator-bias … | 2.1332 against a critical 2.7344 and is … |
| [[D-027]] | 2026-10-09 | The ensemble check tests the generator against the control totals the declared procedure … | z\ |
| [[D-028]] | 2026-10-09 | The U23 mixed-age slice selects its seed small area by a declared objective (pre-1980 … | Yes |
| [[D-029]] | 2026-10-09 | Where the DER adoption draw yields none of a type U23 requires, the adoption is assigned … | Yes |
| [[D-030]] | 2026-10-09 | The week 2 slice size is a separate named scope (week2_slice in config/e1_scope.yaml) and … | Yes |
| [[D-031]] | 2026-10-09 | The slice's people count is tested to equal the sum of its households' actual sizes … | Yes |
| [[D-032]] | 2026-10-09 | The U30 sweep computes its hits and declares only its verdicts: each flag carries its … | Yes |
| [[D-033]] | 2026-10-09 | Searches run over table titles and the label of every dimension; | Yes |
| [[D-034]] | 2026-10-09 | A verdict of RETIRED requires the source declared, fetched and scored against; | Yes |
| [[D-035]] | 2026-10-09 | Where a reference publishes overlapping categories, the model's value is checked against … | Yes |
| [[D-036]] | 2026-10-09 | F2063 validates the rooms x dwelling-type joint and may not be used to tune … | Yes |
| [[D-037]] | 2026-10-09 | PL-PEAK-01 reads one named D19 export view at a single interval length, and raises if the … | Yes |
| [[D-038]] | 2026-10-09 | The overnight term is a taper ratio (mean 00:00 over mean 04:00), not a trough hour | Yes |
| [[D-039]] | 2026-10-09 | PL-PEAK-01's load-factor band is asymmetric: at most 0.05 above LP1's, and at most 0.15 … | Yes |
| [[D-040]] | 2026-10-09 | A plausibility check the package is known to fail is declared in KNOWN_FAILURES with its … | Yes |
| [[D-041]] | 2026-10-09 | A plausibility failure the package is known to have is declared once, in … | Yes |
| [[D-042]] | 2026-10-09 | The immersion heater is a cylinder device, not an appliance; | Yes |
| [[D-043]] | 2026-10-09 | Hot water DEMAND is built from draw events tied to simulated activities, not from DEAP's … | Yes |
| [[D-044]] | 2026-10-09 | The minutes a shower's water runs are separate from the length of the shower_bath … | Yes |
| [[D-045]] | 2026-10-09 | The cooking-fuel share is derived from HEBEU34 and HEBEU106 rather than declared, and … | Yes |
| [[D-046]] | 2026-10-09 | A sweep search term should be the subject noun, not the phrase a reader expects; | Yes |
| [[D-047]] | 2026-10-09 | Comfort-taking is three COM-B terms with different drivers, not one amplitude | Yes |
| [[D-048]] | 2026-10-09 | The mechanism is centred on the town's median specific heat loss, not its mean | Yes |
| [[D-049]] | 2026-10-09 | The comfort-taking strength is not fitted to DBERNG01, and the sweep is published instead | Yes |
| [[D-050]] | 2026-10-09 | write_package=False makes an ablation arm affordable, and a skipped plausibility suite … | Yes |
| [[D-051]] | 2026-10-10 | U31's held-out slice is stratified and not contiguous, gas-only, and not people-band … | Yes |
| [[D-052]] | 2026-10-10 | The two groups are balanced in size (30 and 30) and the slice is checked to be balanced … | Yes |
| [[D-053]] | 2026-10-10 | Nothing is fitted on the held-out slice, and it is enforced rather than intended: … | Yes |
| [[D-054]] | 2026-10-10 | The small hours belong to yesterday's drawn bedtime, recovered from the (person, sim_day … | Yes |
| [[D-055]] | 2026-10-10 | PL-PEAK-01's overnight band is derived from LP1, as half the deviation a profile with no … | Yes |
| [[D-056]] | 2026-10-10 | Sleep timing takes its spread from HETUS UK and its medians from Irish sources; | Yes |
| [[D-057]] | 2026-10-10 | Chronotype selects the sleep-timing quantile rather than adding an offset of its own; | Yes |
| [[D-058]] | 2026-10-10 | A D20 label's detectable_from_tier is derived from the sensor channels its text appeals … | Yes |
| [[D-059]] | 2026-10-10 | The hazard integrated at draw time is recorded and compared against the exposure-based … | Yes |
| [[D-060]] | 2026-10-10 | A vacant dwelling stays in the slice with an empty household and is held at frost … | Yes |
| [[D-061]] | 2026-10-10 | The vacancy rate is an outcome, not a quota: the chain refills vacancies and never … | Yes |
| [[D-062]] | 2026-10-10 | Fabric retrofit and extension produce their D03 passport events and D20 labels but do not … | Yes |
| [[D-063]] | 2026-10-10 | Every declared JSON-stat source's own label is compared against the registry's declared … | Yes |
| [[D-064]] | 2026-10-10 | R20's event coverage audit separates "absent from the generated year" from "present but … | Yes |
| [[D-065]] | 2026-10-10 | Correlated events come from a shared driver that each event names, and driver_audit … | Yes |
| [[D-066]] | 2026-10-10 | The 8.2 staleness margin is derived from LP1's measured maximum quarter-hour ramp (0.256 … | Yes |
| [[D-067]] | 2026-10-10 | The conservative envelope is the minimum of the connection's headroom and its share of … | Yes |
| [[D-068]] | 2026-10-10 | Envelope tightening and relaxation are rates per unit of time, not per epoch | Yes |
| [[D-069]] | 2026-10-10 | A counterfactual refuses a household-scoped fork, and paired and unpaired entities are … | Yes |
| [[D-070]] | 2026-10-10 | Every G-C mode declares its expected outcome class in advance, and the expected class is … | Yes |
| [[D-071]] | 2026-10-10 | T6's statistic is incremental cross-validated R², and the null control's confounder is … | Yes |
| [[D-072]] | 2026-10-10 | Three G-C acceptance criteria were wrong before they were right, and each was corrected … | Yes |
| [[D-073]] | 2026-10-11 | pre-registration, in full | Yes |
| [[D-074]] | 2026-10-11 | Wall, roof, floor and window U-values come from SEAI's assessed distribution conditional … | Yes |
| [[D-075]] | 2026-10-11 | The comfort-taking reference moves from 2.08 to 1.813 W/K/m², and this is not a new choice | Yes |
| [[D-076]] | 2026-10-11 | A D03 passport event changes the fabric from its effective day, at the day boundary, and … | Yes |
| [[D-077]] | 2026-10-11 | The U31 driver and gradient computation move into the repository … | Yes |
| [[D-078]] |  | activity placement weight: pre-registered before measuring the third arm |  |
| [[D-079]] |  | WP7 town scale-up: a new scope, C2, and a bounded window |  |
| [[D-080]] |  | D-073 is scored on the comfort-taking-ON arm, and E2-1's verdict is derived rather than … |  |
| [[D-081]] |  | BN-1: D17's observable view, and the two things it refuses to publish |  |
| [[D-090]] |  | D23 is written with a provenance class on every field, not with the tag's hash |  |
| [[D-091]] |  | a D21 biography is self-citing, and oddness in one is a result |  |
| [[D-092]] |  | D27 is a record only, every magnitude is fetched and cited, and three things stay assumed |  |
| [[D-100]] |  | CER/ISSDA is not used. |  |
| [[D-101]] |  | D18 is scoped, never dropped. |  |
| [[D-102]] |  | COVID deaths are reported, not claimed. |  |
| [[D-103]] |  | Abbeylands construction loads and LEC/MV are a separate proposal |  |
| [[D-104]] |  | geometry stays abstract. |  |
| [[D-105]] |  | transport goes to BNIT |  |
| [[D-106]] |  | acquire Census 2016 SAPS and age forward |  |
| [[D-107]] |  | FX-BN-05 and T-OBS are FLEXUS obligations, not Baile Nua's. |  |
| [[D-108]] |  | acquire ESB Networks SLPs per year 2015–2025 |  |
| [[D-109]] |  | the DST defect is logged now as I-105. |  |
| [[D-110]] |  | sim_day runs continuously 0 → 4,290. |  |
| [[D-111]] |  | enrolment. |  |
| [[D-112]] |  | Part V. |  |
| [[D-113]] |  | crisis-response persistence only if the evidence supports it. |  |
| [[D-114]] |  | estate sizes and mix |  |
| [[D-115]] |  | Phase 16 is split. |  |
| [[D-116]] |  | measure the write-flush overlap before building it. |  |
| [[D-117]] |  | the heating-response elasticity. |  |
| [[D-118]] |  | both energy-poverty measures, never averaged, neither primary. |  |
| [[D-119]] |  | income tracks the life course. |  |
| [[D-120]] |  | the NILM error model is A-numbered |  |
| [[D-121]] |  | consent tiers |  |
| [[D-122]] |  | scope additions R and S |  |
| [[D-123]] |  | SEAI grant data for 2015–2018: a declared fallback. |  |
| [[D-124]] |  | the chain needs no new state capture, and Phase 17 shrinks. |  |
| [[D-125]] |  | B2 upload is blocked and not worked around. |  |
| [[D-126]] |  | Rehearsal A PASSED; the chain is sound. |  |
| [[D-127]] |  | public holidays 2015-2026 derived and triple-verified. |  |
| [[D-128]] |  | STOPPED on school terms, per rule 1. |  |
| [[D-129]] |  | the circular-sourced school calendar is used for ALL years, 2022 included. |  |
| [[D-130]] |  | is_school_day is retained and two sector fields are added. |  |
| [[D-131]] |  | close-date semantics in the circulars are read in two forms. |  |
| [[D-132]] |  | a calendar request before 2014-09-01 is refused, not guessed. |  |
| [[D-133]] |  | one master seed for the whole chain; a per-year seed is recorded but NOT fed to the model. |  |
| [[D-134]] |  | was_workday is None on the first day of each chained segment. |  |
| [[D-135]] |  | resume is per SEGMENT, and an incomplete segment is renamed aside. |  |
| [[D-136]] |  | Phase 2 suite classification: 2 failed / 1,071 passed / 35 skipped (1:27:22). Exactly one … |  |
| [[D-137]] |  | D12 (trips) DEFERRED, not skipped silently. |  |
| [[D-138]] |  | the per-year export records failures rather than raising. |  |
| [[D-139]] |  | the agent tracker is status/AGENTS.md, not status/PROGRESS.md. |  |
| [[D-140]] |  | a worktree gets the gitignored source data as a symlink farm of individual files, not as … |  |

## Assumptions

| id | subject | verdict |
|---|---|---|
| [[A-01]] | HETUS UK donor for Irish time use | KEPT |
| [[A-02]] | ACL00 code substitution for adult care | WRONG_INSTRUMENT |
| [[A-03]] | donor diary day weight of exactly 1.0 | WRONG_INSTRUMENT |
| [[A-04]] | appliance ownership base rates that a source covers | RETIRED |
| [[A-05]] | appliance ownership base rates no source covers | KEPT |
| [[A-06]] | ownership slope per additional occupant | RETIRED |
| [[A-07]] | extra appliance cycles per extra occupant | KEPT |
| [[A-08]] | appliance power signature templates | WRONG_INSTRUMENT |
| [[A-09]] | indoor temperature plausibility band | KEPT |
| [[A-10]] | room count given dwelling type and bedrooms | RETIRED |
| [[A-11]] | floor area per habitable room | KEPT |
| [[A-12]] | heating fuel given dwelling type | SOURCE_FOUND |
| [[A-13]] | detached / semi-detached / terraced split | SOURCE_FOUND |
| [[A-14]] | electricity split: heat pump vs direct electric | KEPT |
| [[A-15]] | fabric U-values by construction era | RETIRED |
| [[A-16]] | BER band boundaries and DEAP primary-energy scope | WRONG_INSTRUMENT |
| [[A-17]] | archetype thermal parameters | WRONG_INSTRUMENT |
| [[A-18]] | performance gap: rated vs actual energy | SOURCE_FOUND |
| [[A-19]] | purge ventilation and thermostat parameters | WRONG_INSTRUMENT |
| [[A-20]] | urban heat bias and Linke turbidity | KEPT |
| [[A-21]] | MIMIC trait priors | KEPT |
| [[A-22]] | within-country trait dispersion | WRONG_INSTRUMENT |
| [[A-23]] | G-B willingness priors | KEPT |
| [[A-24]] | sensor tier uptake correlated with traits | KEPT |
| [[A-25]] | life-course event rates | RETIRED |
| [[A-25b]] | gross household turnover | SOURCE_FOUND |
| [[A-25c]] | union dissolution rate | KEPT |
| [[A-25d]] | children leaving the parental home | KEPT |
| [[A-25e]] | chronic health-state onset under 50 | KEPT |
| [[A-25f]] | annual retrofit and DER adoption rate | KEPT |
| [[A-26]] | POWSCAR commuting microdata substitute | WRONG_INSTRUMENT |
| [[A-27]] | appliance share of household electricity | KEPT |
| [[A-28]] | EV charging and heat-pump kWh per dwelling | KEPT |
| [[A-29]] | aggregate (after-diversity) load factor and shape | RETIRED |
| [[A-30]] | an individual dwelling's peak and load factor | KEPT |
| [[A-31]] | hot water draw volumes | KEPT |
| [[A-32]] | minutes a shower's water runs | KEPT |
| [[A-33]] | share of dwellings that cook with gas | RETIRED |
| [[A-34]] | gas versus electric cooking efficiency | KEPT |
| [[A-35]] | heating affordability by income and tenure | KEPT |
| [[A-36]] | comfort-taking amplitudes | KEPT |
| [[A-37]] | boiler service life | KEPT |
| [[A-38]] | sleep-timing spread and tail | KEPT |
| [[A-39]] | disruption rates and durations | KEPT |
| [[A-40]] | the setpoint of a vacant dwelling | KEPT |
| [[A-41]] | school term dates and daily school absence | SOURCE_FOUND |
| [[A-42]] | electricity outage frequency and duration | WRONG_INSTRUMENT |
| [[A-43]] | local event programme - festivals, markets, sport, roadworks | KEPT |
| [[A-44]] | the safety layer's occupant floor and envelope dynamics | KEPT |
| [[A-45]] | loft insulation depth a fabric retrofit installs | KEPT |
| [[A-46]] | floor area an extension adds | KEPT |
| [[A-47]] | which measures a fabric retrofit comprises | KEPT |
| [[A-48]] | the emitter a converted heat pump is connected to | KEPT |
| [[A-49]] | the town's LV network topology | KEPT |
| [[A-50]] | how many venues the town has, and where | SOURCE_FOUND |
| [[A-51]] | reporting-error and non-response rates for D28 to D31 | KEPT |
| [[A-90]] | D27 retail rate magnitudes | RETIRED |
| [[A-91]] | D27 plan mix across the town | RETIRED |
| [[A-92]] | D27 band boundaries for the day/night plan | KEPT |
| [[A-93]] | D27 standing charge | RETIRED |
| [[A-94]] | D27 export rate under the Clean Export Guarantee | RETIRED |
| [[A-95]] | D27 maximum import capacity | RETIRED |
| [[A-96]] | D27 flexibility contract terms and trial arm | KEPT |
| [[A-97]] | D27 three-band plan is four years out of vintage | KEPT |

## Issues by status

### CLOSED (8)

[[I-004]], [[I-009]], [[I-010]], [[I-011]], [[I-017]], [[I-018]], [[I-026]], [[I-092]]

### MITIGATED (8)

[[I-001]], [[I-008]], [[I-012]], [[I-014]], [[I-015]], [[I-022]], [[I-024]], [[I-025]]

### OPEN (25)

[[I-005]], [[I-006]], [[I-007]], [[I-013]], [[I-016]], [[I-019]], [[I-020]], [[I-082]], [[I-083]], [[I-088]], [[I-089]], [[I-090]], [[I-091]], [[I-093]], [[I-094]], [[I-095]], [[I-100]], [[I-101]], [[I-103]], [[I-104]], [[I-105]], [[I-106]], [[I-107]], [[I-108]], [[I-109]]

### REPORT-TO-MIMIC (6)

[[I-002]], [[I-003]], [[I-021]], [[I-023]], [[I-087]], [[I-096]]

### UNSTATED (66)

[[I-027]], [[I-028]], [[I-029]], [[I-030]], [[I-031]], [[I-032]], [[I-033]], [[I-034]], [[I-035]], [[I-036]], [[I-037]], [[I-038]], [[I-039]], [[I-040]], [[I-041]], [[I-042]], [[I-043]], [[I-044]], [[I-045]], [[I-046]], [[I-047]], [[I-048]], [[I-049]], [[I-050]], [[I-051]], [[I-052]], [[I-053]], [[I-054]], [[I-055]], [[I-056]], [[I-057]], [[I-058]], [[I-059]], [[I-060]], [[I-061]], [[I-062]], [[I-063]], [[I-064]], [[I-065]], [[I-066]], [[I-067]], [[I-068]], [[I-069]], [[I-070]], [[I-071]], [[I-072]], [[I-073]], [[I-074]], [[I-075]], [[I-076]], [[I-077]], [[I-078]], [[I-079]], [[I-080]], [[I-081]], [[I-084]], [[I-085]], [[I-086]], [[I-097]], [[I-098]], [[I-099]], [[I-102]], [[I-110]], [[I-111]], [[I-112]], [[I-113]]
