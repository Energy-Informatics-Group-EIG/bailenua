# Baile Nua: Technical Design Review

Oct 8, 2026 · @Brian O Regan

**Status: design review checkpoint. No data generation, code or development is authorised until this design is independently reviewed and approved.**

**Revision 4 (9 October 2026); architecture frozen at revision 3 and unchanged. Revision 4 adds 6.4 and 6.5, 7.9, 9.6, decisions U22 to U28 and Appendix A. Export this revision to docs/ as r4 so Claude Code works from it (I-035).** This revision responds to independent reviews 1 and 2 (ChatGPT). Review 2's verdict: conditional architectural acceptance, E0 closed pending a targeted revision 3. Findings A1 to A4 and V1 to V5 are addressed, and E0 now waits on the approval table in section 13. Review 3 accepted all nine findings and recommended freezing the architecture. From here, any architectural change goes through the review log; implementation clarifications are recorded without reopening it. The changes are listed in the review log in section 13.

This document proposes the full technical design for Baile Nua, a synthetic Irish harbour town calibrated to Cobh, with HRSD\_Occupants (the people layer) treated in the most depth. It consolidates every requirement agreed in conversation on 8 October 2026 and the lessons taken from the MIMIC repository.

Every statement carries one of four tags:

| Tag | Meaning |
| --- | --- |
| **\[C\]** Confirmed | Stated or chosen by Brian in conversation; listed in section 2 |
| **\[P\]** Proposed | A design choice recommended here, awaiting approval |
| **\[A\]** Assumption | Taken as true for design purposes; must be checked |
| **\[U\]** Unresolved | Needs a decision or evidence before the relevant work package starts |

No figures for Cobh, Irish time use or appliance ownership are quoted here. They will be extracted from the named sources in work package 1, with provenance, rather than recalled. This design does not claim that Baile Nua data is or will be indistinguishable from real data. That claim can only be made per task, after the benchmarks in section 7 pass.

## 1. Executive summary

Baile Nua will be a seeded, deterministic simulation of about 3,000 synthetic people in roughly 1,100 homes and the town around them, run for 10 years. It produces two things: a hidden ground truth (who did what, where, why and when) and the realistic sensor and meter observations that a deployed system would actually see.

The design rests on six choices:

1. **People first, as causes.** Each occupant has one persistent town-wide identity. Persistent traits (including a MIMIC-derived willingness vector), evolving states and life events *cause* activities. Activities cause appliance use, occupancy and travel. Physics turns those into energy and indoor climate. Nothing is painted onto a load curve. \[C\]\[P\]
2. **Calibrated, not invented.** Population structure is sampled from CSO Census 2022 small areas for Cobh. Routines come from time-use diaries, appliance ownership from national surveys, and load signatures from public sub-metered datasets. \[C\]\[P\]
3. **Events, not time slices.** Ground truth is stored as typed intervals (activity, appliance cycle, trip, life event). Any resolution from 1 Hz to 30 minutes is rendered on demand from seeds, identically every time. \[C\]
4. **Privacy-shaped observation.** Each home is modelled with a smart meter, tiered sensors and a Jetson Orin edge running PARA//EL. Change detection runs inside the home, and only aggregates, the building energy profile and flexibility compliance leave it. \[C\]
5. **Base model only.** No FLEXUS-family solution runs inside Baile Nua. Scenarios, interventions and detection experiments live in BNIT. \[C\]
6. **Fitness is proven by use, not appearance.** Acceptance depends on TSTR against TRTR on independent real datasets for each task, RL sim-to-real tests, causal and intervention checks, and privacy and memorisation tests. Discriminator AUC near 0.5 is necessary but not sufficient. \[C\]

Baile Nua is also built as a **test population for MIMIC**. Its people share MIMIC's trait model and coding, and at least 10,000 of them will take part in MIMIC through its own API, so MIMIC's analytics can be scored against known truth (5.14). \[C\]

The build starts with a **minimal valid slice**: one estate of about 50 homes and 140 people for one year, taken end to end through every gate. Only then does it scale to the town and to 10 years. The largest scientific risk is causal and intervention-response fidelity. Historical data cannot show how real people would respond to signals they have never seen, so that claim stays explicitly bounded until field evidence exists.

## 2. Confirmed requirements register

All 33 requirements below were stated or chosen by Brian. They are binding inputs to this design, and section 12 traces each one to a component, a validation method and an acceptance criterion.

| ID | Requirement | Source |
| --- | --- | --- |
| R01 | Baile Nua is a hyper-realistic synthetic Irish harbour town in Co. Cork. It has a town centre, estates, commercial and industrial zones, roads and traffic lights, LV/MV/HV network, a solar farm and a wind farm, and no high-rise. | Prior Baile Nua brief |
| R02 | Baile Nua is a base model. FLEXUS-family tools are not integrated. Scenarios and interventions run in BNIT. | Prior brief |
| R03 | Population is about 3,000 people (about 1,000 to 1,100 homes) and behaves like a typical Irish town. | Conversation |
| R04 | Calibrate to one real town: **Cobh**, scaled down from CSO small-area data while preserving its mix. | Q&A |
| R05 | Occupants are realistic in demographics, traits, behaviours, willingness, routines, jobs, schooling, caring and home roles. | Conversation |
| R06 | Every occupant carries MIMIC latent traits (SO/RC/CP/AL willingness, λ₁ to λ₃, comfort sensitivity, trust, privacy) as hidden ground truth. The MIMIC engine itself stays outside Baile Nua. | Q&A |
| R07 | Nationality and ethnic differences are modelled through evidenced mechanisms (household size, cooking, setpoints, festivals, trips home, tenure), not direct per-group multipliers. Irish/non-Irish mix comes from Census. | Q&A |
| R08 | Life events are modelled: births, deaths, moves in and out, extensions, retrofits and new DER. A Building Energy Passport records building events. | Conversation, prior brief |
| R09 | Change detection runs inside each home. Only aggregates, the building energy profile and flexibility compliance leave the building. Occupancy never crosses the network. Interpretation (7.8, awaiting Brian's confirmation): no occupancy field is transmitted; the residual risk of inferring occupancy from exports is measured, not assumed away. | Q&A |
| R10 | Each home has a smart meter, tiered sensors, EV/inverter data where present, and a Jetson Orin running HEMS, PARA//EL and local ML. Homes differ in demographics, socio-economics, BER, age, location and DER. | Q&A |
| R11 | HRSD\_Occupants is about occupants, not houses. Buildings are a separate layer. | Q&A |
| R12 | Data must be NILM-grade enough to improve flexibility and P2P forecasting. | Q&A |
| R13 | Ground truth is stored as events plus seeds, with 1 Hz and coarser data rendered deterministically on demand. | Q&A |
| R14 | The simulation runs for 10 years. | Q&A |
| R15 | The behaviour model is a hybrid: time-use calibrated semi-Markov scheduling, MIMIC-trait modulation, bounded rationality, social interaction and physical constraints. | Q&A |
| R16 | Households are coupled systems. This covers shared-resource conflict, caring, decision authority, visitors and absences, synchronisation, negotiation, influence, and evolving composition, employment, health and caring. | Q&A |
| R17 | Disruptions are modelled: illness, remote working, appliance failure, unplanned visitors. | Q&A |
| R18 | Behaviour runs across timescales from minutes to seasons to long-term adaptation, with habit, imperfect information and occasional irrational decisions. | Q&A |
| R19 | All behaviour is probabilistically calibrated and validated for temporal, spatial and cross-variable consistency. | Q&A |
| R20 | Calendar effects cover the Irish calendar, local events, faith and cultural festivals and shocks. They also cover daylight-saving changes, sunrise and sunset, tourism, commuting, college terms, shift work, agriculture, sport, concerts, markets, elections, roadworks, transport disruption and infrastructure maintenance. | Q&A |
| R21 | Events have preparation, duration, recovery and rebound phases. They are classed as predictable, recurring, irregular or exceptional, and have probabilistic attendance, spatial propagation and compound correlation (for example storm plus outage). They are validated on diversity, coincidence and extremes. | Q&A |
| R22 | Acceptance is functional equivalence: TSTR and TRTR (plus TSTS and TRTS) across forecasting, occupancy, anomaly detection, NILM, DR, flexibility, optimisation and control. RL sim-to-real must cover safety and constraints, and the data must pass uncertainty, adversarial, memorisation and privacy tests with explicit thresholds and confidence intervals. | Q&A, design brief |
| R23 | Each person has one town-wide ID, is present across homes, workplaces, schools and clubs, and cannot be in two places at once. | Q&A, design brief |
| R24 | Edge detection is adaptive, hierarchical and confidence-aware. Safety events are caught in seconds to minutes, assets in minutes to hours, routine deviations within 24 h, and structural change is confirmed progressively over 7 days or more. | Q&A |
| R25 | Each detection carries timestamp, onset, confidence, evidence, uncertainty and a suspected/provisional/confirmed status. Detection infers behaviour, not causes. No structural change is confirmed from short-term anomalies alone. | Q&A |
| R26 | Each person has a fictional, culturally and age-appropriate name and an evolving life profile, with persistent traits, evolving states, stochastic behaviour and observations kept separate. Biographies are human-readable, and ML/RL sees only what is observable in deployment. | Q&A |
| R27 | Identities are explicitly synthetic, do not reproduce real people, preserve diversity and avoid deterministic stereotyping. | Q&A |
| R28 | Design review comes before implementation, with the deliverables listed in the brief. | Design brief |
| R29 | Align HRSD\_Occupants with MIMIC as closely as possible: one trait model, MIMIC coding and the MIMIC session process. | Conversation, 8 Oct |
| R30 | Generate 10,000+ HRSD-derived entries into MIMIC to test the MIMIC tool. | Conversation, 8 Oct |
| R31 | Every release ships as three packages: observable view, ground-truth view and evidence view (6.3). | Adopted 8 Oct, from review |
| R32 | Blind consumer evaluation with a tell audit, run by an analyst who has never seen this design (7.9). | Adopted 8 Oct, from review |
| R33 | The observable view behaves like a real field study: study protocol and selection, meter-point keying, imperfect surveys, recorded vs true metadata, embedded trial, sub-metered subset, external series, operator log (6.4, 6.5). | Adopted 8 Oct |

## 3. Technical architecture

Baile Nua is proposed as 13 subsystems in four tiers. Static synthesis builds the town and its people once. A slow life-course loop changes them day by day. A fast co-simulation loop runs a 1-minute step where behaviour and building physics feed back on each other. A rendering and observation tier then turns ground truth into what sensors would see. \[P\]

### 3.1 Subsystems

| ID | Subsystem | Main inputs | Main outputs | Native resolution | Tag |
| --- | --- | --- | --- | --- | --- |
| S01 | **Environment**: weather, solar geometry, daylight, tides | Met Éireann hourly series (Cork Airport file already in MIMIC `version_1`), solar position model | Air temp, RH, wind, irradiance (GHI/DNI/DHI), sunrise/sunset, DST flags | 1 min (interpolated from hourly, stochastic sub-hour irradiance) | P |
| S02 | **Geography and infrastructure**: parcels, streets, venues, LV/MV/HV network, solar and wind farms | Cobh morphology (OSi/OSM-derived, synthetic layout), ESB Networks design norms | Spatial graph, venue registry, feeder topology, travel-time matrix | Static, versioned on change | P |
| S03 | **Buildings (HRSD\_Buildings)**: fabric, archetype, BER, age, systems, appliance stock, DER, Building Energy Passport | SEAI BER database distributions, Census dwelling type and age, archetype library | Per-building physics parameters, asset register, passport log | Static plus event changes | C/P |
| S04 | **Population synthesis (HRSD\_Occupants, static)** | CSO Census 2022 SAPS for Cobh small areas, CSO nationality and household tables | Persons, households, relationships, traits, names, initial states | Once at t0 | C/P |
| S05 | **Life-course engine** | CSO vital statistics, migration, labour force, school, retirement, adoption-curve evidence | Life events (birth, death, move, job change, illness, retrofit and DER decisions) | Daily | C/P |
| S06 | **Calendar and exogenous events** | Irish public holidays, school and college terms, local event programmes, faith calendars, storm and outage history, tariff schedules | Event instances with prep, duration, recovery and rebound phases, attendance probabilities, spatial footprint | Event-defined, minimum 1 min | C/P |
| S07 | **Activity and household engine** | Time-use diaries, S04/S05 states, S06 events, S09 indoor conditions, MIMIC traits | Per-person activity intervals and location, household negotiation outcomes | 1 min step, intervals stored | C/P |
| S08 | **Mobility** | S07 location changes, S02 travel times, vehicle registry | Trips, mode, vehicle state, EV SoC and plug events | 1 min | P |
| S09 | **Building physics and IEQ** | S01, S03, S07 occupancy and internal gains, heating controls | Zone temperatures, RH, CO₂, heat demand, DHW tank state | 1 min | P |
| S10 | **Appliance and electrical** | S07 activities, S03 stock, S08 EV, S09 heat pump and immersion demand, PV/BESS models | Appliance cycles with signature IDs, PV output, BESS dispatch, household net power | Cycles as events; power rendered at 1 Hz | C/P |
| S11 | **Network** | S10 net power per connection, S02 topology | Feeder and transformer loading, voltages, outages | 1 min (quasi-static power flow) | P |
| S12 | **Observation model** | All ground truth | Meter, CT, sensor, inverter and charger readings with noise, drift, gaps and failures; plus non-sensor observation models (surveys, records, study protocol, operator log, external series), each with its own provenance (6.5) | Device-native: 1 Hz to 30 min | C/P |
| S13 | **Edge export boundary** | S12 per home | Only what leaves the home: aggregates, energy profile, flexibility compliance | Contracted interval (proposed 15 and 30 min) | C |

BNIT sits outside Baile Nua and consumes the S12 (inside-home) and S13 (network-side) views. It never sees ground truth except through a separate scoring interface for labelled experiments. \[C\]

### 3.2 Coupling and time

- **Feedback loop at 1 minute.** S07 (people), S09 (physics) and S10 (devices) are co-simulated in lock-step. A cold living room can make Mary turn up the heating, and a running tumble dryer adds internal gains. \[P\]
- **No feedback at 1 Hz.** Within-minute waveforms (motor start-up, compressor cycling, element switching) are rendered after the fact from signature libraries. They never change state, so on-demand rendering stays exactly reproducible. Controllable devices under test are the exception: in control mode they run live (5.6). \[P\]
- **Slow loop daily.** S05 updates life states at 04:00 each simulated day. Decisions with lead times (retrofit, EV purchase, move) are scheduled forward as pending events. \[P\]
- **Town-wide clock.** All subsystems use one UTC clock with Europe/Dublin local-time views. DST transitions are explicit events that shift human routines but not the UTC series. \[P\]

### 3.3 Interfaces

Subsystems talk only through typed, versioned event and state tables (section 6), never through shared mutable memory. Each run is defined by a manifest naming code version, input data versions, parameter set and master seed, so any subsystem can be re-run for any home and period and give identical output. \[P\]

## 4. System interaction and dependency diagram

&#91;embedded content: Baile Nua system interaction · 13 subsystems, 4 tiers\]

Evidence calibrates the static town. The daily life-course and calendar tiers set the conditions for the 1-minute loop, where people, physics, devices and the network co-evolve. Static parameters also feed every lower tier, which isn't drawn to keep the picture readable. Ground truth flows to sensors only through the observation model, and BNIT sees in-home data through the edge, the network-side view through S13, and labels only through the scoring API.

## 5. Modelling methodology

The methodology runs one causal chain throughout: **who people are → what state they are in → what they do and where → what devices and physics do as a result → what sensors record**. Each link is a separately calibrated, separately testable model.

### 5.1 Four-layer state model for every person \[C\]

| Layer | Changes | Examples | Visible to ML/RL? |
| --- | --- | --- | --- |
| Persistent characteristics | Never, or almost never | Birth date, sex, country of birth, first language, MIMIC trait vector, Big Five, chronotype, habit strength | No (ground truth only) |
| Evolving states | Days to years | Age, household, employment, workplace, school year, health state, caring load, vehicle, remote-work share | No |
| Stochastic behaviour | Minutes to days | Activity, location, appliance use, setpoint changes, lapses | No |
| Observations | Device-native | Meter, sensor, charger and inverter readings | Yes, and only those available at that home's tier |

A leakage test in CI fails any benchmark dataset that contains a column from the first three layers (section 7.6).

### 5.2 Population synthesis (S04)

1. **Small-area targets.** Extract CSO Census 2022 SAPS tables for every Cobh small area: age by sex, household composition, nationality, ethnicity, language, education, principal economic status, socio-economic group, industry, occupation, tenure, dwelling type and age, central heating fuel, car availability and travel to work. \[C\]\[P\]
2. **Scale-down.** Build both candidates, (a) whole small areas sampled with stratification and (b) proportional scaling of all small areas, and compare them before U03 is finalised. Validation covers marginals and also the joint and spatial structure: household composition by age of members, age–economic status–tenure dependencies, car ownership by household type, commuting accessibility, and spatial segregation indices across estates. The method with the smaller joint-distribution error is recommended. \[U\]
3. **Joint fitting.** Combine iterative proportional fitting with combinatorial optimisation, so households are built whole (a couple with two children aged 6 and 9) and match person-level and household-level marginals together. Plausibility rules apply: a parent's age at a child's birth falls between 16 and 50 (mother) or 16 and 65 (father), and siblings are at least 9 months apart unless twins. \[P\]
4. **Commuting.** Use CSO POWSCAR flows from Census 2022 where the release allows, so each worker gets a workplace (in town, Cork city, Ringaskiddy, elsewhere or remote) and a mode. \[P\]\[U\]
5. **Traits.** Draw the MIMIC latent vector (trans, community, env, autonomy, comfort, conditional, privacy, instTrust, idvZ, satisficer; MIMIC's names and scales, 5.14) with weak, evidence-based dependence on demographics. Until FlexSense Ireland responses exist, priors come from the MIMIC generator and literature, flagged \[A\]. Each person also gets Big Five scores, chronotype and habit strength. \[C\]\[A\]
6. **Names and biographies.** Draw first names by birth year and origin from CSO baby-name tables and equivalent national lists, and surnames from origin-matched lists. Reject any full-name combination that matches a public-figure list or appears more than once in town. Biographies are generated from structured records only, never free-written. \[C\]\[P\]

### 5.3 Activity and household engine (S07) \[C\]\[P\]

- **Semi-Markov core.** Each person moves through about 30 activity states (sleep, personal care, cooking, eating, laundry, cleaning, TV and screens, work at home, school, care of others, leisure out, travel, and so on). Duration distributions are explicit, not geometric, and conditioned on person type, day type, season, time since waking and previous activity. Fitted to time-use diaries (U04 covers which ones).
- **Household coupling.**
  - Joint activities (evening meal, Sunday dinner, family TV) are planned at household level, then members are pulled in with a probability set by their age and role.
  - Shared resources (one shower, one hot-water tank, one car, one TV room, one kitchen) are modelled as queues with priority rules, which produces realistic morning stagger.
  - Caring constraints: a child under 12 is never home alone, and school runs, elderly-relative visits and minding grandchildren are scheduled obligations.
  - Negotiation of thermostat setpoint, appliance timing and spend is a weighted bargain set by decision authority (who pays the bill, who owns the house), comfort sensitivity and MIMIC traits.
  - Influence works at a slow timescale: habits drift toward household members and, more weakly, toward neighbours and co-workers.
- **Bounded rationality.** Agents act on habit first and only deliberate when a trigger is noticed. Notice probability depends on attention, salience and information. They satisfice rather than optimise, and are present-biased about future costs. They have memory, including fatigue after repeated flexibility asks, and a calibrated lapse rate (heating left on when out, lights left on, forgotten EV plug-in).
- **Willingness link.** For any choice with a self-versus-shared trade-off (accept a ToU shift, export or self-consume, let the HEMS act), the probability of each SO/RC/CP/AL-type response comes from a multinomial logit on the MIMIC traits and the context (grid stress, visibility, reward, comfort cost). This reuses the structure of MIMIC's `chooseSignal`, re-fitted on real responses when available.
- **Disruptions.** Illness episodes (seasonal hazard, contagious within households), unplanned visitors, appliance failures (hazard by age, with repair lag and behaviour workarounds such as a laundrette run), weather days and remote-work days all perturb the schedule.

### 5.4 Town-wide identity and presence (S07, S08) \[C\]

Every person is at exactly one location at every minute: a zone of a building, a venue, in transit, or outside the model boundary. A hard invariant check runs after every simulated day and fails the run on any violation. Venue occupancy (school, shops, pubs, church, GAA club, workplaces) is the sum of the people placed there, so commercial and public buildings inherit realistic occupancy.

### 5.5 Mobility (S08) \[P\]

Trips are created from location changes. Mode choice depends on distance, car availability, weather, rail timetable (Cobh to Cork commuter line) and habit. Vehicles are entities with owner, type, efficiency and, for EVs, battery state. EV state of charge follows driven distance and temperature-dependent consumption. Plug-in decisions use habit, state of charge, tariff and the MIMIC traits, which yields the 08:00 unplug and 17:00 plug-in signatures in Mary's example.

### 5.6 Appliances, hot water and DER (S10) \[C\]\[P\]

- **Ownership.** Each home's appliance stock is drawn from national ownership evidence, conditioned on household type, income band and dwelling age. Irish-specific loads are included: electric showers, immersion heaters, storage heaters and tumble dryers.
- **Activity to appliance.** Each activity triggers appliance cycles probabilistically (cooking → hob, oven, kettle, extractor; laundry → washer then dryer or indoor airing, weather-dependent).
- **Signature library.** Each cycle references a signature from a library built from public sub-metered datasets (UK-DALE, REFIT, REDD, IDEAL; U05). Signatures have model-to-model and age-related variation, so two kettles are never identical.
- **Flexible loads in detail**, because they drive flexibility and P2P value: EV charging (charger power, taper, scheduling), heat pump (COP against outdoor temperature, defrost, cycling), immersion (thermostat hysteresis, diverter if PV), BESS (efficiency, SoC limits, control mode), PV (irradiance, orientation, shading, inverter clipping).
- **Hot water.** Draw events from showers, baths, sinks and dishes feed a tank or instantaneous model.

**Device fidelity modes** (for RL and control) \[P\]

- **Rendered mode** (default, and always for non-controllable appliances). Cycles are simulated as events; 1 Hz waveforms are rendered afterwards and never change state.
- **Live mode** (controllable assets under test: EV charger, heat pump, immersion, BESS, PV inverter). These run inside the loop as state machines at their control resolution: 1 second for fast-response services, 1 minute otherwise. Agent actions then change device state, SoC, temperatures and the meter. Rendered signatures of other appliances are superimposed.
- **Out of scope for v1.** Sub-second power-electronics dynamics (inverter control loops, grid-forming behaviour). Any experiment needing them must name a different simulator.
- **Tests.** With no action taken, live and rendered modes must agree on energy within 0.1%. A step-response test checks each live device against its specification.

### 5.7 Building physics and IEQ (S09) \[P\]

- **Thermal.** One grey-box RC model per building (3R2C or 4R2C, two zones: living and sleeping), with parameters drawn per archetype. The reference is the asset rating (BER/DEAP), but operational behaviour is allowed to diverge from it. The performance gap is modelled, not hidden.
- **Heating systems.** Gas or oil boilers, heat pumps, storage heaters, solid-fuel stoves and direct electric, each with a controls model (timer, thermostat, TRVs, manual override).
- **IEQ.** CO₂ follows a mass balance (occupants, ventilation, window opening). RH follows a moisture balance (cooking, showers, indoor clothes drying, ventilation). Window opening is behavioural and depends on comfort, weather and habit.
- **Changes.** Extensions and retrofits change parameters on a dated event and write to the Building Energy Passport.

**Physical fidelity tiers, chosen per task** \[P\]

| Tier | Model | Adequate for | Used in |
| --- | --- | --- | --- |
| F1 | Two-zone grey-box RC | Whole-home energy, flexibility estimation, forecasting, DR | All homes |
| F2 | Room-level multi-zone RC (living, kitchen, each bedroom, bathroom) | Room occupancy, comfort, CO₂/RH, sensor placement | Homes with room sensors (T3 and T4) |
| F3 | EnergyPlus co-simulation (FMU) | Advanced HVAC control research; reference checks | Sample of archetypes only |

Each task in 7.5 declares the tier it needs. Fidelity test: F1 and F2 are compared with F3 on reference archetypes (annual heat demand error, zone-temperature RMSE, peak heat timing), with tolerances set per task. A task can't claim results from a tier that failed its fidelity test. Three levels are kept apart: numerical verification (solver correctness, energy balance), cross-model agreement (F1/F2 against F3), and empirical validation against measured buildings (S-track). Agreement with EnergyPlus is not physical validity; no task can claim physical validity without the empirical level.

### 5.8 Nationality and ethnicity mechanisms \[C\]

The mix comes from Census. Behaviour differs only through mechanisms that each require a cited source before they are switched on:

- household size and multi-generational living
- cooking practices (duration, appliance mix, timing)
- thermal preference and setpoint
- faith and cultural calendar (Ramadan meal timing, Eid, Diwali, Orthodox Easter)
- trips home (timing and length)
- tenure and dwelling type
- shift-work share by sector
- remittance-driven cost sensitivity

Variation within each group must exceed the difference between groups. A **stereotype guard** test (section 7) fails the build if a classifier can predict nationality from a home's load profile much better than from household size and tenure alone. A mechanism without evidence stays off and is listed in the evidence-gap register.

### 5.9 Life-course engine (S05) \[C\]\[P\]

| Event | Model | Effect on observable data |
| --- | --- | --- |
| Birth | Age- and parity-specific fertility hazard; pregnancy as a 9-month state | Parental leave, night activity, laundry and heating up |
| Death | Age and sex life tables, with seasonal excess | Household shrinks; possible vacancy and re-let or sale |
| Move out / move in | Hazard by life stage and tenure; vacancy chain re-fills homes from an in-migrant pool | New household, new routines, asset continuity |
| Household change | Partnering, separation, children leaving or returning, elderly relative moving in | Composition and caring load shift |
| Employment | Job start, loss, change, retirement, shift work, remote-work share | Weekday occupancy changes |
| Health state | Generic functional states (short illness, reduced mobility, home-bound, recovering), never diagnoses | More time at home, higher setpoints |
| Extension / retrofit | Triggered by household growth, income, grant availability, house sale | Passport event; physics parameters change |
| DER adoption | Diffusion with peer effects (visible neighbour PV), gated by tenure, roof, income, traits and policy | New asset signatures |

**Mary's case** is a built-in test scenario. Mary works 9 to 5 on weekdays and her EV unplugs about 08:00 and plugs back in about 17:00. On a dated event, her daughter's family of four moves in. Ground truth records the move, the new routines and the changed load; the edge detector must find it (section 5.12).

### 5.10 Calendar and event engine (S06) \[C\]

Every event instance has a type (predictable, recurring, irregular or exceptional), phases (preparation, main, recovery, rebound), a spatial footprint (home, street, estate, town, region), attendance probabilities by demographic, and links to weather, tariffs and the grid.

Compound correlations come from shared drivers, not independent draws. A storm raises outage probability, school-closure probability and home occupancy together. A cruise-ship day raises town-centre footfall, traffic and commercial load.

The full set required by R20 is in scope. Each class gets an evidence source and a validation statistic (section 7).

### 5.11 Observation model (S12) \[C\]\[P\]

Each device type has a measurement model:

- resolution, accuracy class, quantisation and clock drift
- reporting interval
- communication gaps (bursty, weather-correlated)
- failure and replacement (meter swap, CT mis-orientation, sensor battery death, inverter firmware change)

Sensor tiers are drawn per home (R10), so detection difficulty varies across the town as it would in practice.

### 5.12 Edge change detection: what Baile Nua must support \[C\]

Detection runs on the in-home Jetson (PARA//EL), and only its outputs leave the home. Baile Nua does not detect anything itself. Its job is to provide the observable inputs and the labelled ground truth so that BNIT can score detectors.

| Tier | Examples | Target latency | Minimum evidence before "confirmed" |
| --- | --- | --- | --- |
| Safety-critical | Sustained heater with no occupancy, abnormal overnight inactivity for a lone elderly occupant, overload | Seconds to minutes | Rule plus corroborating sensor |
| Equipment signature | New EV, PV, heat pump or BESS; appliance failure | Minutes to hours | Repeated signature cycles |
| Routine deviation | Mary at home on a weekday | ≤ 24 h | Flag only; never confirmed alone |
| Structural change | Household of 1 now behaves like a household of 4 | Progressive, ≥ 7 days | Persistent multi-signal change across ≥ 1 full weekly cycle, holidays and illness ruled out |

Every detection record carries: timestamp, estimated onset, confidence, uncertainty interval, supporting evidence, and a status of suspected, provisional or confirmed. The detector reports what changed in observable behaviour ("occupied-hours pattern consistent with 3 to 5 occupants"), never a cause ("a family moved in"). \[C\]

### 5.13 MIMIC alignment: what Baile Nua inherits \[P\]

Baile Nua inherits MIMIC's behavioural science, its realism lessons and its governance register. It also adopts MIMIC's trait model and coding scheme, so every synthetic adult can take part in MIMIC as a participant (5.14). \[C\] The table maps each MIMIC element to its role here; items marked *added* were missing from the first draft of this review.

| MIMIC element | Role in Baile Nua | Status |
| --- | --- | --- |
| SO/RC/CP/AL signals, conditional vs unconditional cooperation (Fischbacher et al.) | Response options in every willingness choice (5.3) | In draft |
| λ₁ to λ₃ behavioural coefficients | Household reward weights in the RL environment (7.6) | In draft |
| Latent traits and `chooseSignal` logit structure | Trait vector (D05) and willingness model | In draft |
| Context conditions (normal vs stress, private vs visible; Bateson et al. observability) | Visibility to neighbours and grid stress as explicit context variables in every willingness choice | *Added* |
| D2 Discover, then validate | Baile Nua stores continuous traits only, never cluster labels. Clusters must be *discoverable* from Baile Nua data by the same pipeline MIMIC runs on real responses. | *Added* |
| Fastidious Factor | Emerges from the trait distribution (low comfort tolerance, high escalation) rather than being assigned; a validation check confirms a comparable segment appears | *Added* |
| Cluster reification risk | No person is labelled by cluster in GT or biographies | *Added* |
| Stated–revealed and intention–behaviour gaps (Kormos & Gifford; Sheeran) | Each person has a separate *stated* willingness (what they would answer in MIMIC) and *revealed* willingness (what they do), linked by a calibrated gap. BNIT can then "survey" Baile Nua and face the same gap real studies face. | *Added* |
| Careless responders and probe-pair inconsistency (Meade & Craig) | A realistic share of synthetic people answer inconsistently when surveyed by BNIT | *Added* |
| Moral and Community Values mini-survey (10 items) | Each person carries latent MCV scores derived from traits, as MIMIC's generator does | *Added* |
| COM-B | Every behaviour is gated by Capability (knowledge, skill), Opportunity (asset, tariff, time at home) and Motivation (traits). It explains why willing people still don't act. | *Added* |
| Self-Determination Theory, motivation crowding | Payments can reduce intrinsic CP/AL behaviour over time | *Added* |
| Prospect theory, focus theory of norms | Loss framing and descriptive-norm effects in the bounded-rationality model | *Added* |
| Socioemotional selectivity, age, gender and SVO priors (Carstensen; Wiernik; Zelezny; Croson & Gneezy; Van Lange) | Weak, cited demographic dependence of traits (5.2 step 5) | *Added* |
| Hofstede, social trust (Delhey & Newton), `CountryAttributes` | Origin-country priors for non-Irish-born residents, shrunk toward Irish norms by years in Ireland (acculturation) and checked by the stereotype guard | *Added* |
| Privacy strictness (Data & Privacy bank) | Drives each home's sensor tier and Jetson consent, so tier uptake correlates with traits as it would in reality | *Added* |
| Cold start and drift | Preferences drift seasonally and with tariffs and norms, separate from habit drift | *Added* |
| Self-selection bias (AAPOR non-probability guidance) | MIMIC/FlexSense samples are self-selected, so trait priors are post-stratified to Cobh demographics before use | *Added* |
| Adaptive comfort, ASHRAE 55, ISO 7730, EN 16798-1 | Comfort bands in the occupant model (setpoint and window decisions) and the RL discomfort penalty | *Added* |
| DNAS ontology, IEA EBC Annex 66/79 | Occupant behaviour expressed in Drivers–Needs–Actions–Systems terms in the schema | *Added* |
| Energy performance gap (de Wilde) | Asset vs operational divergence (5.7) | In draft |
| ISO 52120-1, SRI, EPBD 2024/1275 | Building automation class and SRI score per building in D02 (links to the SRI tool) | *Added* |
| NUTS3, ISCED, ISCO-08, EU-SILC, UN census definitions | Codes in D05/D08; CSO's SOC occupations mapped to ISCO-08 for MIMIC compatibility | *Added* (ISCED in draft) |
| ODD protocol (Grimm et al. 2020) | Baile Nua is documented as an agent-based model in ODD form before any results are reported | *Added*, conformance |
| GDPR, ISSDA licence terms, DPIA | Real calibration and validation data (CER/ISSDA, IDEAL) are used under licence; a DPIA covers that use. Synthetic outputs carry no personal data. | *Added*, conformance |
| EU AI Act | Classification of any control component trained on Baile Nua, with oversight logging | *Added*, conformance |
| ICC/ESOMAR Code 2025 (AI and synthetic data) | Disclosure that data are synthetic, with human oversight of generation | *Added*, conformance |
| FAIR, DDI, TOP, preregistration | Release metadata in DDI-lite form; benchmarks pre-registered (7.5) | In draft, DDI *added* |
| ALLEA, ISO/IEC 27001, IEEE 7000 | Research integrity, platform security, value-based design traceability | *Added*, benchmark |

The MIMIC elicitation-specific items (survey response psychology, back-translation, CCSG, WCAG, ISO 9241-210, ISO 20252, Belmont, Helsinki, Menlo, AoIR) apply to MIMIC's data collection. Baile Nua relies on them indirectly through the quality of any MIMIC data it is calibrated on.

### 5.14 HRSD → MIMIC: synthetic participants for testing MIMIC \[C\]\[P\]

Baile Nua will feed at least 10,000 synthetic participants into MIMIC (R30). Each one answers QANDA scenarios exactly as a real person would through the MIMIC Decision Engine, so MIMIC can be tested end to end against a population whose true traits, clusters and behaviour are known. HRSD\_Occupants is therefore aligned to MIMIC at three levels: the trait model, the data coding, and the session process.

**Level 1: one trait model.** HRSD\_Occupants uses MIMIC's latent variables as its native willingness traits, with the same names and scales as `mimic_sd_generator.php`:

- `trans` (self-transcendence)
- `community`
- `env` (environmental concern)
- `autonomy` (trust in automation)
- `comfort`
- `conditional` (conditional cooperation)
- `privacy`
- `instTrust` (institutional trust)
- `idvZ` (cultural individualism, from origin country and acculturation)
- `satisficer` (careless-responder flag)

The derived self-reports (environmental concern, trust in automation, comfort sensitivity on 1 to 5), MCV items 1 to 10 and λ₁ to λ₃ come from these traits by MIMIC's own mappings. The *revealed* behaviour in Baile Nua uses the same traits, plus the stated–revealed gap (5.13).

**Level 2: identical coding.** The export writes MIMIC schema 1.1 fields with MIMIC's own value sets:

| MIMIC table.field | HRSD source | Mapping note |
| --- | --- | --- |
| `participants.id` | person\_id | New UUID per participant; crosswalk kept in the GT answer key (D26), never in MIMIC |
| `profiles.consent_version` | Constant | `SYNTHETIC-HRSD-v1`, so MIMIC's existing purge (`LIKE 'SYNTHETIC%'`) and synthetic banner work unchanged |
| `age_band` | birth\_date at the session date | 18–24 … 65+ (MIMIC bands) |
| `sex` | sex | Female, Male |
| `household_size`, `children_present` | D06 membership on the session date | 1 … 5+; Yes/No for anyone under 18 |
| `employment_status`, `work_pattern` | D08 econ\_status, work\_pattern, remote\_share | Full-time, Part-time, Unemployed, Student, Retired; Office, Remote, Shift, Irregular. **Gap:** MIMIC has no "home duties" value (U18) |
| `dwelling_type`, `ownership_status` | D02, tenure | **Gap:** MIMIC has no "Terraced", a common Cobh house type (U18) |
| `region_country`, `region_nuts3`, `urban_rural_island` | Constant | IE, the real NUTS3 code for Cork's region, Urban |
| `income_band` | Household income quintile | 1 to 5 |
| `der_ownership` | D04 on the session date | JSON list from PV, Battery, EV, HP, None |
| `environmental_concern`, `trust_in_automation`, `comfort_sensitivity` | Stated traits | round(3 + 1.05 × latent), clamped 1 to 5, as MIMIC |
| `profile_optional.*` (10 permitted fields) | D05, D08, D04, sensor tier, social graph | e.g. `home_automation_level` ← sensor tier; `energy_bill_responsibility` ← decision authority |
| `profile_mcv.mcv_01..10` | Traits via MIMIC `makeMcv` mapping | 1 to 5 Likert |
| Forbidden fields (health, fitness, mobility, medical device, country of birth) | Never exported | A negative-test batch deliberately sends them and must be rejected by `ProfileService` |

**Level 3: the real session process.** Synthetic participants go through MIMIC's **public API** (`api/session.php`, `api/response.php`, `api/consent.php`), not straight into the database. This exercises:

- session composition: 11 balanced items, 1 random item and 1 probe repeat
- the randomised MCV position (pre or post)
- option-order randomisation, validation and rate limiting (a test-mode allowance for the HRSD runner, U19)

The HRSD runner sees only the presented scenario and its displayed order, and answers with:

- the HRSD willingness model applied to the four signals, never to screen position (position bias is planted only in test mode T10)
- response latency (lognormal, slower with age and early items, faster for satisficers)
- realistic abandonment

**Volume plan to reach 10,000+.** Baile Nua has roughly 2,200 to 2,400 adults \[A\], so it cannot supply 10,000 *participants* alone. Two pools are proposed (U16):

1. **Baile Nua panel (linked).** Every adult who would plausibly respond completes repeated sessions in survey waves across the 10 simulated years. At 8 to 15 sessions each (100 to 200 micro-decisions, MIMIC's own resolution target), that is over 10,000 *sessions*. Every answer links to that person's simulated behaviour, which is the unique value of HRSD.
2. **HRSD extended pool (unlinked).** The same person generator, without the time simulation, creates 10,000+ further participants from full-size Cobh, other Irish small areas and, with `CountryAttributes` priors, the EU-27. This tests MIMIC's country analytics at scale.

**Response propensity.** Who opts in is modelled: higher for high `env`, `trans` and digital access, lower for high `privacy`. MIMIC therefore receives a realistically self-selected sample, and its post-stratification can be scored against the full-population truth.

**What HRSD lets us test in MIMIC.** Each test has a planted truth and a pass/fail criterion fixed before running:

| ID | Test | Planted truth | Pass criterion \[P\] |
| --- | --- | --- | --- |
| T1 | API and schema conformance | 10,000+ unique participants (counters below) | 0 integrity errors; forbidden fields always rejected |
| T2 | Parameter recovery | Known trait–choice coefficients | 95% CI coverage 90 to 98%; bias < 0.1 SD |
| T3 | Cluster discovery | (a) Planted k segments; (b) **null mode with no clusters** | (a) Adjusted Rand ≥ 0.7; (b) MIMIC's validity gate rejects clusters |
| T4 | Probe reliability and careless detection | Known satisficers and consistency | Probe agreement matches generated rate; careless-flag recall ≥ 0.7 |
| T5 | Self-selection and post-stratification | Known population means | Post-stratified estimate CI contains the true mean |
| T6 | Predictive validity (linked panel) | Revealed behaviour in Baile Nua | Flex Profile predicts revealed flexibility above a demographics-and-opportunity baseline; in the null causal-link control, MIMIC must reject any predictive claim |
| T7 | Context effects (AMCE) | Known context-b shift | Estimated effect CI contains the planted effect |
| T8 | Drift across waves | Planted seasonal and tariff drift | Drift detected; no drift found in a no-drift control |
| T9 | Dashboard aggregates | Known group PI values | Exact match; n < 15 cells suppressed; synthetic banner shown |
| T10 | Position-bias check | None planted, then planted | Detects only when planted |

**Avoiding circularity.** If HRSD answered with MIMIC's own `chooseSignal` formula, MIMIC recovering it would prove only that the estimator works on its own assumptions. HRSD's willingness model is therefore written independently. It adds interactions, non-linearities, response styles, fatigue and the stated–revealed gap, so MIMIC is tested under realistic misspecification. These tests verify MIMIC's machinery. They never validate that real people behave this way; that needs real participants.

**Independence protocol** \[P\]

1. **Two claims kept apart.** (a) *Machinery verification*: can MIMIC recover known structure, reject structure that isn't there, and flag careless responders? HRSD can test this. (b) *Behavioural validity*: do real people's MIMIC answers reflect their real behaviour? HRSD cannot test this; it needs real participants with metered behaviour. Every T-result is labelled (a).
2. **Three generators.** MIMIC's analytics run on structurally different generators:
   - G-A, MIMIC's own `chooseSignal`: the well-specified baseline.
   - G-B, the HRSD willingness model: independent, with interactions, response styles, fatigue and the stated–revealed gap.
   - G-C, adversarial: latent classes, extreme response styles, position bias, non-stationarity. MIMIC passes only if its conclusions track each generator's truth. How far it degrades under G-B and G-C is reported as a finding, not hidden.
3. **Specification firewall.** G-B's functional form and parameters come from cited literature and are frozen in D24 before any MIMIC estimator is run on its output. Any later change is logged in the review log with a reason.
4. **T6 is internal consistency only.** Linked-panel predictive validity shows that MIMIC can recover the link HRSD planted, not that the link exists in people.

**G-C modes** (independence defined at the level of the data-generating mechanism):

- **Wrong assumptions:** responses from a mechanism MIMIC doesn't model, such as a lexicographic or threshold rule.
- **Non-identifiable:** correlated latent traits whose separate effects can't be recovered.
- **Continuous, no clusters:** apparent clusters arising from continuous distributions only.
- **Causally unrelated:** survey answers that predict behaviour but don't cause it, through a shared confounder.
- **Differential non-response:** missing-not-at-random responses and dropout.

G-B shares MIMIC's trait vocabulary and schema, which is intended for compatibility. It is therefore *not* counted as independent for behavioural mechanism; only G-C modes are.

**T6 null causal-link control.** In this mode, stated willingness has no effect on revealed flexibility beyond demographics and opportunity. MIMIC must not report predictive or causal value.

**Verify vs diagnose.** Each test outcome is classed as **pass**, **software defect** (wrong result where the method should work) or **recognised limitation** (correct implementation failing where the method can't work, for example parameter recovery under non-identifiability). Limitations are reported to the MIMIC team as findings, not bugs.

**Counters, reported separately and never merged:**

- unique synthetic participants
- completed sessions
- completed responses
- linked Baile Nua panel participants
- unlinked extended-pool participants

Repeated sessions never count as unique participants. The E1 target of 10,000 refers to unique participants.

**First finding from reviewing the MIMIC code.** In `mimic_sd_generator.php` the education adjustment checks the age band `'55-64'` with a hyphen, but the bands are defined with an en-dash (`'55–64'`). The adjustment never fires for 55 to 64 year-olds. T1-style conformance tests would catch this class of error.

## 6. Dataset inventory and data dictionary

Baile Nua is proposed as 31 datasets in three access classes: **GT** (ground truth, never given to models under test), **OBS** (observable, what a device or the edge would see) and **META** (provenance and calibration). Everything is keyed to stable IDs and a run manifest. \[P\]

### 6.1 Inventory

| ID | Dataset | Purpose | Grain | Class | Storage |
| --- | --- | --- | --- | --- | --- |
| D01 | `town_geo` | Parcels, streets, venues, network topology | Feature | GT | GeoParquet |
| D02 | `buildings` (HRSD\_Buildings) | Fabric, archetype, BER, systems, physics parameters | Building × version | GT | Parquet |
| D03 | `building_passport` | Dated building events (extension, retrofit, asset added or removed) | Event | GT, with a redacted OBS view | Parquet |
| D04 | `assets` | Appliances, heating, PV, BESS, chargers, vehicles, with owner and lifetime | Asset × version | GT | Parquet |
| D05 | `persons` (HRSD\_Occupants) | Persistent characteristics and trait vector | Person | GT | Parquet |
| D06 | `household_membership` | Who lives where, from when to when | Interval | GT | Parquet |
| D07 | `relationships` | Kin, partner, carer, friend, co-worker edges | Edge × interval | GT | Parquet |
| D08 | `person_states` | Evolving states, slowly changing (SCD-2) | Interval | GT | Parquet |
| D09 | `life_events` | Births, deaths, moves, jobs, health states, decisions | Event | GT | Parquet |
| D10 | `activities` | Person activity intervals with location and co-participants | Interval | GT | Parquet, partitioned by year/month |
| D11 | `presence` | Person location intervals (the no-double-occupancy source) | Interval | GT | Parquet |
| D12 | `trips` | Origin, destination, mode, vehicle, distance | Event | GT | Parquet |
| D13 | `appliance_cycles` | Cycle start/end, programme, signature ID, energy | Event | GT | Parquet |
| D14 | `calendar_events` | Event instances, phases, footprint, attendance | Event | GT | Parquet |
| D15 | `weather` | True site weather and solar geometry driving physics and behaviour | 1 min | GT (observable station weather is D31) | Parquet |
| D16 | `building_state` | Zone temps, RH, CO₂, DHW, heat delivered | 1 min, checkpointed daily | GT | Parquet (or re-run, U07) |
| D17 | `network_state` | Feeder and transformer loading, voltages, outages | 1 min | GT, with an aggregate OBS view | Parquet |
| D18 | `observations` | Rendered device readings with noise and gaps | Device-native | OBS | Rendered on demand; cached slices |
| D19 | `edge_exports` | What leaves each home: aggregates, profile, compliance | 15/30 min | OBS (network-side) | Parquet |
| D20 | `change_labels` | Ground-truth labels for detector scoring (onset, type, persistence) | Event | GT (scoring API only) | Parquet |
| D21 | `biographies` | Human-readable narratives generated from D05 to D09 | Person × date | GT | JSON/Markdown |
| D22 | `signature_library` | Appliance waveform templates and variation parameters | Signature | META | Parquet + NPZ |
| D23 | `run_manifests` | Code and data versions, parameters, seeds, checksums | Run | META | JSON in git + object store |
| D24 | `calibration_targets` | Every empirical target with source, version and tolerance | Statistic | META | Parquet + citation file |
| D25 | mimic\_export | HRSD participants, profiles, MCV, sessions and responses in MIMIC schema 1.1, delivered through the MIMIC API | Participant, session, response | OBS (MIMIC-side) | MIMIC MySQL via API; Parquet copy |
| D26 | mimic\_answer\_key | Crosswalk to person\_id, true traits, planted segments, response propensity, stated gap, test-mode settings | Participant | GT (scoring only) | Parquet |
| D27 | tariffs\_contracts | Per-home supplier tariff, time-of-use and export rates, switch dates, flexibility and P2P contract terms, connection limits (maximum import and export capacity), DER grid notifications; market rules in META | Home × interval | OBS (what a utility or aggregator would hold) | Parquet |
| D28 | study\_protocol | Recruitment, response rates, consent to sensors, dropouts, trial arms and periods (6.4) | Premises × event | OBS; selection mechanism in GT | Parquet + protocol document |
| D29 | household\_survey | Questionnaire answers with calibrated reporting error and non-response | Premises × wave | OBS; true values in GT | Parquet |
| D30 | recorded\_metadata | Recorded building and asset data (BER, floor area, PV size, dates, orientation, shading), stale or wrong at realistic rates | Premises × version | OBS; true values in D02/D04 | Parquet |
| D31 | external\_series | Station weather, wholesale prices, carbon intensity, system demand, flexibility-service events | Series-native | OBS | Parquet |

### 6.2 Data dictionary: core entities

All times are UTC (`timestamptz`), and local-time views are derived. Energy is in Wh, power in W, temperature in °C, RH in %, CO₂ in ppm and distance in km. IDs are stable strings with a type prefix (`P-` person, `H-` household, `B-` building, `A-` asset, `V-` venue).

**D05 `persons`**

| Field | Type | Unit / values | Notes |
| --- | --- | --- | --- |
| person\_id | string | `P-000001` | Persistent, town-wide |
| given\_name, family\_name | string |  | Synthetic, uniqueness-checked |
| birth\_date | date |  |  |
| death\_date | date, null |  | Set by D09 |
| sex | enum | F, M | As recorded in Census tables |
| country\_of\_birth, nationality | ISO 3166 |  | From SAPS mix |
| ethnicity\_census | enum | CSO categories | Used only for synthesis and stereotype-guard tests |
| first\_language, other\_languages | ISO 639 |  |  |
| education\_level | enum | ISCED | Evolves by D08 while in education |
| trans, community, env, autonomy, comfort, conditional, privacy, instTrust, idvZ | float | z-score | MIMIC latents; same names and scales as mimic\_sd\_generator (5.14) |
| stated\_gap (stated vs revealed willingness), satisficer (0/1) | float | 0 to 1 |  |
| lambda\_self, lambda\_coop, lambda\_altru | float | sum = 1 | λ₁ to λ₃ |
| big5\_o, \_c, \_e, \_a, \_n | float | z-score |  |
| chronotype | float | hours offset | Shifts the sleep window |
| habit\_strength, lapse\_rate, attention | float | 0 to 1 | Bounded-rationality parameters |
| seed | int64 |  | Person sub-seed |

**D08 `person_states`** (one row per state interval)

| Field | Type | Unit / values |
| --- | --- | --- |
| person\_id, valid\_from, valid\_to | string, timestamptz |  |
| household\_id, role | string, enum | head, partner, child, parent, lodger, other |
| econ\_status | enum | employed, self-employed, unemployed, student, retired, home duties, unable to work |
| occupation\_soc, industry\_nace | string | SOC 2010, NACE rev2 |
| workplace\_venue\_id, work\_pattern | string, enum | fixed day, shift, part-time, irregular |
| remote\_share | float | 0 to 1 of working days |
| school\_venue\_id, school\_year | string, int |  |
| health\_state | enum | well, short illness, reduced mobility, home-bound, recovering |
| caring\_load | enum + float | none, child, elderly, both; hours/week |
| decision\_authority | float | 0 to 1 within household |
| vehicle\_access | enum | none, shared, own |

**D10 `activities`**

| Field | Type | Unit / values |
| --- | --- | --- |
| activity\_id, person\_id | string |  |
| start, end | timestamptz | 1 s precision |
| activity\_code | enum | about 30 codes, mapped to HETUS |
| location\_id, zone | string, enum | living, kitchen, bedroom, bathroom, utility, outside |
| joint\_with | string\[\] | Co-participants |
| trigger | enum | routine, joint plan, event, signal, disruption, lapse |
| deliberated | bool | True if a decision process ran |

**D13 `appliance_cycles`**

| Field | Type | Unit / values |
| --- | --- | --- |
| cycle\_id, asset\_id, building\_id | string |  |
| start, end | timestamptz | 1 s precision |
| programme | string | e.g. eco 40, kettle 1.5 L |
| signature\_id, signature\_seed | string, int64 | Drives 1 Hz rendering |
| energy\_wh, peak\_w | float | Wh, W |
| caused\_by\_activity\_id | string | Causal link back to D10 |
| flexible, shifted\_by\_min | bool, int | Whether the start was moved and by how much |

**D09 `life_events`**

| Field | Type | Unit / values |
| --- | --- | --- |
| event\_id, event\_type | string, enum | birth, death, move in, move out, partnering, separation, job change, retirement, health change, retrofit decision, DER decision, extension |
| effective\_at, decided\_at | timestamptz | Lead time |
| persons, household\_id, building\_id | string\[\] |  |
| cause | string | Model and driver that fired |
| observable\_effects | json | Expected signal changes (for D20) |

**D18 `observations`**

| Field | Type | Unit / values |
| --- | --- | --- |
| device\_id, building\_id, channel | string | e.g. import\_w, export\_w, ct\_ev, temp\_living, co2\_living, pir\_hall |
| ts | timestamptz | Device-native |
| value | float, null | Null = gap |
| quality | enum | ok, estimated, missing, suspect |
| tier | enum | T1 meter only to T4 full sensing plus Jetson |

**D20 `change_labels`**

| Field | Type | Unit / values |
| --- | --- | --- |
| label\_id, building\_id | string |  |
| change\_class | enum | safety, equipment, routine deviation, structural |
| true\_onset, true\_end | timestamptz |  |
| persistence | enum | transient, persistent, permanent |
| source\_event\_ids | string\[\] | D09, D03, D14 links |
| detectable\_from\_tier | enum | Lowest sensor tier at which it is theoretically observable |

Full dictionaries for D01 to D04, D06, D07, D11, D12, D14 to D17, D19 and D21 to D24 follow the same pattern. They will be completed in WP0 as a versioned YAML schema, the single source used to generate DDL, validators and documentation. \[P\]

### 6.3 Delivery packages

Every release ships as three separate packages, built from the access classes above. \[P\]

| Package | Contents | Who receives it |
| --- | --- | --- |
| **Observable view** | OBS datasets only (D18, D19, D27 to D31, the redacted D03 and the aggregate D17 views), with a full data dictionary. Every value carries a **provenance code** (metered, estimated, interpolated, operator-recorded) and a **quality flag** (ok, estimated, missing, suspect, drift, fault). The operator log holds what a utility or operator would really know: tariff switches, meter replacements, DER notifications, outage reports. | Model developers, BNIT experiments, blind evaluators |
| **Ground-truth view** | GT datasets (people, activities, appliance cycles, life events, causal links, D20 labels, D26 answer key) | Scoring services and diagnosis only; never a model under test |
| **Evidence view** | Calibration sources, source-use register, validation results with uncertainty, fidelity tiers passed, limitations, version history, and the list of tasks for which equivalence is shown | Everyone; it accompanies every release |

The observable view must avoid synthetic "tells":

- IDs are opaque random strings, not sequential `P-000001` style.
- Timestamps carry realistic jitter and clock drift.
- Values are not suspiciously round.
- Meter swaps, firmware changes and reporting gaps occur at realistic rates.

A **tell audit** (7.9) checks this. The synthetic flag lives in the release manifest, which the evaluation organiser holds.

### 6.4 What a real dataset would also contain

A researcher who believed Baile Nua was real would also expect the imperfections and context that come with real field data. These eight additions make the observable view behave like a real study, not a clean simulation. Adopted by Brian on 8 October 2026 (R33). \[C\]

| # | Addition | What it adds | Where | Why it matters |
| --- | --- | --- | --- | --- |
| 1 | **Study protocol and selection** | A coherent fictional study: recruitment route, invitation and response rates, who declined sensors, dropouts and withdrawals over 10 years. Selection is driven by traits (privacy, env, trust) and circumstances. | D28 `study_protocol` (OBS); true selection mechanism in GT | Analysts can't judge bias without it; homes that accept sensors aren't typical |
| 2 | **Meter-point keying** | Observable data keyed by premises (an opaque meter-point ID that stays with the property), not by household. New occupants, sales and lettings appear under the same ID with no announcement. | D18, D19, D27 keys; household link only in GT | It's the real ambiguity change detectors face, as in Mary's case |
| 3 | **Imperfect household surveys** | Recruitment and follow-up questionnaires with calibrated reporting error: misreported appliances, optimistic occupancy, forgotten or outdated DER, item non-response, and answers drifting out of date | D29 `household_survey` (OBS); true values in GT | Real studies pair meters with surveys that disagree with them |
| 4 | **Recorded vs true building data** | Recorded BER, floor area, heating system, PV size and install dates, sometimes stale or wrong at realistic rates; site details for PV (orientation, roof area, shading) at release-level coarseness | D30 `recorded_metadata` (OBS); true values in D02/D04 | Models must cope with wrong metadata, as in practice |
| 5 | **Embedded randomised trial** | Tariff and stimulus arms (for example time-of-use, feedback, flexibility requests) with a control group, randomised at recruitment, run for defined periods | Arm assignment in D27 and D28; response in OBS | Behavioural response can only be learnt where an intervention happened; mirrors the CER trial design |
| 6 | **Labelled sub-metered subset** | 20 to 50 homes with appliance-level channels and an installer log, including mislabelled and failed channels | Extra D18 channels at tier T4 | Supervised training data for NILM and occupancy, as in real studies |
| 7 | **Realistic external series** | Weather from the nearest official station (not the true Cobh microclimate used by the physics), wholesale prices, grid carbon intensity, system demand and flexibility-service events | D31 `external_series` (OBS); true local weather stays in D15 as GT | The gap between station and site weather is itself realistic |
| 8 | **Operator incident log** | Outage reports, meter replacements, firmware updates, reporting failures, as a network operator or aggregator would record them, with occasional omissions | Operator log in the observable package (6.3) | Explains breaks in the data the way real logs do, imperfectly |

None of this changes the architecture. These are not sensor or meter outputs; each has its own observation model and provenance inside S12, under the rules in 6.5. Selection effects (1) and the embedded trial (5) also feed the S-track, because they let Baile Nua replicate how real studies are biased and how trial effects are estimated.

### 6.5 Observation rules for non-sensor datasets

D28 to D31 and the operator log are produced by **observation models of human and administrative processes**, not by sensors. Each one specifies its collection mechanism (who records what, when, from which source), its error model and its provenance code. Four rules apply, each with automated tests. \[C\]

**1. Strictly observational (no ground-truth leakage)**

- Every OBS field must name the real-world mechanism that would produce it: a respondent answering, an assessor recording, an installer logging, a station measuring. A field with no such mechanism is rejected at schema level.
- Survey answers come from what the respondent would plausibly know or believe, never straight from GT. Latent traits, true occupancy schedules and causal links never appear.
- **Too-good test:** agreement between each OBS field and its GT counterpart must not exceed the calibrated error rate's upper bound. A survey that matches the truth too well fails.
- **Join test:** OBS datasets must not reconcile perfectly with each other where real ones wouldn't (survey household size against meter-point occupancy, recorded PV size against inverter data).
- The existing leakage test (5.1) is extended to D28 to D31.

**2. Temporally and causally consistent external data**

- **One weather realisation drives everything.** Station weather (D31) and true site weather (D15, GT) come from the same realisation, related by a downscaling and offset model (coastal exposure, elevation, shelter). Physics, behaviour, PV and prices all see the same weather on the same day.
- **Years up to the present** use real historical series (Met Éireann station data, wholesale prices, system demand, carbon intensity), aligned to the simulated calendar under U08.
- **Projected years** use generated series that preserve the real joint structure: prices correlated with wind, demand and temperature; carbon intensity with the generation mix. Storm days in the event engine coincide with the weather that causes them.
- Real versus generated segments are recorded in the evidence view only, so they don't become a tell.
- **Tests:** cross-correlation between weather, prices, demand and Baile Nua load matches the reference structure. No event occurs without its weather cause. No series is misaligned in time (DST, time zone, interval-end vs interval-start conventions).

**3. Realistically imperfect**

| Dataset | Imperfections modelled |
| --- | --- |
| D29 surveys | Unit and item non-response that depends on traits and circumstances; social-desirability bias (environmental behaviour over-reported); recall error; satisficing and straight-lining; answers going out of date between waves; occasional inconsistent answers within one questionnaire |
| D30 records | Missing fields; stale values (BER pre-retrofit, PV never updated); transcription and unit errors (kW against kWp, m² against ft²); conflicts between sources (assessor against installer); records for assets since removed |
| D28 protocol | Incomplete consent records; dropouts with and without stated reasons; installer delays; arm-assignment deviations (non-compliance, crossover) |
| D31 external | Station outages and gap-filled values; revised price data; occasional bad readings later corrected |
| Operator log | Omitted and late entries; free-text inconsistencies; duplicate tickets |

Error rates are calibrated against survey-methodology and administrative-data quality evidence where available, and flagged \[A\] where not. **Test:** each planted rate is recovered from the data within tolerance.

**4. Blind-evaluation safe**

- The tell audit (7.9) gains items for these datasets: survey distributions too clean, protocol documents too tidy, station-to-site weather differences implausible, record errors too uniform, and identical error patterns across homes.
- The adversarial analyst must also try to use D28 to D31 to separate synthetic from real. Any feature that does so above chance is fixed or logged as a limitation before a blind round.
- **Test:** a classifier given only D28 to D31 features can't separate Baile Nua from the real reference package beyond the discriminator screen in 7.3.

## 7. Verification, validation and benchmarking framework

Baile Nua is accepted for a task only when it passes five levels in order, each falsifiable and each able to fail. Passing a lower level never implies passing a higher one. This follows the HRSD principle that a check which has never failed has not been tested: every check below ships with a deliberately broken "negative control" dataset that it must reject. \[C\]\[P\]

| Level | Question | Evidence type | Passing proves |
| --- | --- | --- | --- |
| V0 Verification | Is the code doing what the model says? | Unit tests, invariants, conservation | Correct implementation, nothing about realism |
| V1 Visual plausibility | Does it look right to an expert? | Blind expert review | Nothing on its own; it screens obvious faults |
| V2 Statistical fidelity | Do distributions, dependencies and extremes match real data? | Distance metrics, discriminators | Similar appearance at the tested aggregations |
| V3 Causal fidelity | Do responses to changes match real responses? | Natural experiments, trial treatment effects | Plausible intervention response, within tested ranges only |
| V4 Functional equivalence | Do models trained on it work on real data? | TSTR vs TRTR, RL sim-to-real | Fitness for that task only |

### 7.1 Reference data and independence

- **Calibration sources** (allowed to shape parameters): CSO Census 2022 SAPS and POWSCAR, CSO vital statistics, SEAI BER database, time-use diaries, the signature datasets in D22, and Met Éireann.
- **Validation sources** (never used for calibration): the CER/ISSDA Irish smart metering trial with its household surveys and tariff treatments, the IDEAL UK dataset (homes with sensors and occupant surveys), UK-DALE and REFIT house splits not used for signatures, and any O-CEI or Beaufort lab data that becomes available. Exact splits are fixed and hashed in D24 before any comparison is run. \[P\]\[U\]
- A source-use register in D24 records each dataset's use per household, site, time period, geography and model-development exposure (whether it influenced design choices, model selection or tuning). Calibration and validation may share a corpus only if the validation units are disjoint on the dimension relevant to the claim, and never if they influenced model selection or tuning. Any validation result that touched tuning-exposed data is a blocking failure.

### 7.2 V0 Verification: hard invariants (zero tolerance)

- Nobody is in two places at once, and nobody is anywhere before birth, after death or while away.
- Children under 12 are never alone at home; every venue has a capacity.
- Energy closes per home per minute: Σ appliance + HVAC + EV + BESS charge − PV − BESS discharge = net meter, within 0.1% of daily energy.
- Physics bounds hold: SoC in \[0, 1\], CO₂ ≥ outdoor, RH in \[0, 100\], indoor temperature in a physically reachable range given heat input.
- Referential integrity holds across all 31 datasets, and every row traces to a manifest.
- **Determinism**: re-rendering any home-period from its seed gives a byte-identical hash.

### 7.3 V2 Statistical fidelity

| Aspect | Metric | Aggregations | Proposed threshold \[P\] |
| --- | --- | --- | --- |
| Marginals | Wasserstein-1 and KS on daily energy, peak, load factor | Home, feeder, town | Within the bootstrapped real-vs-real spread (95% CI) |
| Dependencies | Distance between correlation matrices; mutual information between household attributes and load features | Home | Within real-vs-real spread |
| Temporal | ACF at lags of 30 min, 1 day and 1 week; spectra; weekday/weekend and seasonal shape | Home, town | Within real-vs-real spread |
| Diversity | ADMD against number of homes; coincidence factor; entropy of daily-profile clusters | 1 to 1,000 homes | ADMD curve inside the real 95% band at every N |
| Extremes | Generalised Pareto tail fit of peaks; cold-snap and storm-day behaviour | Feeder, town | Tail index CI overlaps real |
| Occupancy | Daily presence profile by household type; time-use activity shares | Person | Within time-use survey sampling error |
| Discriminator | Classifier (gradient boosting + 1D CNN) on real vs synthetic home-days | 30 min, 1 min, 1 Hz | AUC upper 95% CI ≤ 0.60, reported per aggregation |

The discriminator threshold is a screen, not a pass. AUC near 0.5 at 30 minutes says nothing about 1 Hz.

### 7.4 V3 Causal and intervention fidelity

Matching historical distributions does not prove intervention response. \[C\]

- **Tariff treatments.** Replicate the CER trial's tariff and stimulus arms in Baile Nua with matched households. Compare simulated treatment effects (peak reduction, load shift) with the trial's published and recomputed effects.
- **Natural experiments.** Cold snaps, storms with outages, holiday periods and, if suitable data exist, COVID-era remote working. Compare the simulated change in occupancy and load with the observed change.
- **Counterfactual consistency.** The same household with and without an event must differ only downstream of that event (twin-run test with shared seeds).
- **Bounded claim.** Response to interventions never seen in real data (for example novel P2P incentives) is reported as **unvalidated**, with a sensitivity analysis over MIMIC-trait priors. It is never presented as evidence.

### 7.5 V4 Functional equivalence

Each task is run under four regimes:

- **TRTR** (train real, test real): the reference.
- **TSTR** (train synthetic, test real): the decisive test.
- **TSTS** (train synthetic, test synthetic): internal sanity check.
- **TRTS** (train real, test synthetic): checks the synthetic data is not easier or harder than real.

Models, hyper-parameter budgets and test sets are identical across regimes and pre-registered.

| Task | Model families | Primary metric | Proposed acceptance \[P\] |
| --- | --- | --- | --- |
| Day-ahead home load forecast | Gradient boosting, TFT/N-HiTS | nRMSE, pinball loss | TSTR ≤ 1.10 × TRTR, upper 95% CI |
| Feeder/town forecast | Same | nRMSE, peak error | TSTR ≤ 1.05 × TRTR |
| Occupancy prediction | HMM, gradient boosting, CNN | F1, Brier | TSTR ≥ 0.90 × TRTR |
| NILM (EV, HP, immersion, shower, wet goods) | Seq2point, event-based | F1, energy error | TSTR ≥ 0.85 × TRTR per appliance |
| Anomaly and change detection | Change-point, isolation forest, Bayesian online | AUPRC, latency, false alarms per household-month | TSTR AUPRC ≥ 0.85 × TRTR; false alarms not above TRTR CI |
| DR baseline and flexibility estimate | CBL methods, ML baselines | Bias, RMSE of estimated flex | TSTR bias within ±5% of TRTR |
| Optimisation and control | MPC, RL | Cost, comfort violation, constraint violation | See 7.6 |

Acceptance also requires **calibration** (expected calibration error not worse than TRTR CI), a robustness check under shifted test conditions, and TRTS within 10% of TRTR. Each acceptance is stated as a non-inferiority margin with both an absolute and a relative part, oriented by metric direction (for example nRMSE: TSTR ≤ TRTR + max(0.02, 10% of TRTR)), so it stays well-behaved when reference performance is near zero. Confidence intervals use a hierarchical block bootstrap that resamples households, then contiguous weeks, with feeder and weather-day clusters kept intact to respect shared exposure. For network-level claims the resampling unit is the whole feeder, and common-shock days (storms, cold snaps, town events) are resampled as blocks across all feeders, because resampling households within a feeder understates dependence. **Failure condition:** any primary metric outside tolerance means Baile Nua is *not fit* for that task, and the result is published as such.

### 7.6 RL environment and sim-to-real

- **Interface.** A Gymnasium-compatible environment hosted by BNIT, with Baile Nua as transition dynamics. One agent runs per home (HEMS) or per estate (EdgeWare). \[P\]
- **State.** Only OBS at that home's tier, plus tariff, weather forecast and grid signal. The ground-truth occupancy and traits are excluded, which the leakage test enforces. \[C\]
- **Actions.** Heat pump setpoint and pre-heat, immersion window, EV charge rate and window, BESS power, appliance-start suggestions (accepted or ignored by the occupant model), and flexibility bids.
- **Reward.** Cost and revenue, discomfort (degree-minutes outside the occupant's comfort band), flexibility compliance, override penalty, with λ₁ to λ₃ weights per household as in MIMIC.
- **Safety constraints.** Hard limits on temperatures for vulnerable occupants, minimum EV departure charge, BESS SoC limits and feeder thermal limits. Any violation in evaluation is logged and counted.
- **Disturbances and interventions.** Held-out event types, behaviour drift, asset changes, sensor faults and extreme weather, none seen in training.
- **Sim-to-real.** Stage 1: replay against real-data-driven simulators built from the validation sources. Stage 2: hardware-in-the-loop at the Beaufort lab. Stage 3: a supervised pilot (for example O-CEI sites). Acceptance: regret against a real-trained policy ≤ 10%, constraint-violation rate not higher than the real-trained policy, and override rate within its CI.

**RL information boundary** \[P\]

| Interface | Contents | Training | Inference |
| --- | --- | --- | --- |
| Observations | OBS at the home's sensor tier, tariff, weather forecast, grid signal, last clip/reject notice | Allowed | Allowed |
| Actions | Device setpoints, windows, rates, bids | Allowed | Allowed |
| Training reward | Scalar only, computed from GT (including latent comfort bands and λ weights) | Allowed as a scalar, with no decomposition exposed | Not available |
| Evaluation metrics | Cost, comfort minutes, violations, overrides, regret | Never fed to the agent | Never |
| Privileged GT scoring | Occupancy, traits, D20 labels | Forbidden | Forbidden |

Two leakage checks enforce this. A probe test trains a small model to predict GT occupancy or traits from the agent's internal state. Agents may legitimately infer occupancy and traits from permitted observations, so the test targets only the excess: the probe on the agent's state must not beat a probe trained on the same OBS history the agent received. The gap, not raw probe accuracy, measures privileged leakage. An interface audit confirms that no reward components or diagnostics reach the agent. Privileged information may be used in training only through the scalar reward. Algorithms that need more (for example asymmetric actor-critic) must declare it, and their results are reported separately.

### 7.7 Privacy, memorisation and fairness

- **Memorisation.** Distance to closest record from synthetic to real must not be smaller than real holdout to real training. A membership-inference attack must score AUC ≤ 0.55. This applies wherever real data informed a generator (signatures, diaries).
- **Identity.** No synthetic person matches a real person on name plus birth year plus small area.
- **Stereotype guard.** Nationality must not be predictable from load beyond what household size, tenure and dwelling explain: ΔAUC ≤ 0.03.
- **Leakage test.** Benchmark datasets must not contain GT-class columns.

### 7.8 Privacy inference risk of exported data

R09 ("occupancy never crosses the network") is implemented as: **no occupancy, presence or person-level field is ever transmitted**. That alone doesn't make exports safe, because aggregate energy profiles are known to reveal presence and routines. Baile Nua can measure this residual risk directly, because it has ground truth. \[C\]\[P\]

- **Attacks.** Train an occupancy classifier, a household-size estimator, a holiday detector and a routine-change detector on the D19 export view of some homes, and test them on others.
- **Export configurations compared.** Home-level 30 min, home-level 15 min, estate aggregate (EdgeWare), and compliance-only.
- **Proposed acceptance.** A configuration is acceptable only if occupancy-inference AUC is ≤ 0.60 (upper 95% CI) at home level, compared with a prior-only baseline.
- **If a configuration fails.** Coarser intervals, aggregation at estate level, calibrated noise (differential privacy), or sending compliance results only.
- **The trade-off is a decision (U20).** Settlement may need home-level data, so privacy against settlement accuracy needs Brian's ruling. The result also feeds PARA//EL and EdgeWare design.

**Threat model first** (required before U20 is decided):

- **Attacker classes:** network operator or aggregator with routine data access; a party holding repeated releases; an informed neighbour who knows the household's routine.
- **Target information:** occupancy now, absence periods (holidays), household size, routine change.
- **Observation duration:** one day to years.
- **Access level:** single export versus linked releases.
- **Consequences:** burglary timing, profiling, inference about the people in the home.

AUC ≤ 0.60 stays only as a **screening** threshold. Each export configuration also reports:

- precision and recall at operational attack thresholds
- attack advantage over prior-only and time-of-day baselines
- leakage across multiple periods and repeated releases
- membership and attribute inference where relevant
- the utility cost of each mitigation (settlement and flexibility-estimate accuracy)

Home-level and estate-level results are reported separately. Differential privacy is only claimed with a defined protected unit, privacy budget, composition across releases, and measured utility loss. Passing these tests does not establish privacy or GDPR compliance; it informs the DPIA.

### 7.9 Blind consumer evaluation protocol

This is a further, independent validation route. An analyst (an AI system or a human team) who doesn't know the data's origin during analysis must reach the same useful conclusions, and build models as effective, as they would from real data. \[P\]

1. **Setup.** The organiser prepares two observable-view packages with identical structure: one Baile Nua slice and one real dataset of comparable scope (from the S-track sources), or two Baile Nua slices with a real one held back. The analyst must never have seen this design or its reviews, so neither model instance used in this review qualifies; a fresh session or a different model is used. The analyst is told the data "may be real or synthetic" and agrees to the protocol beforehand. Synthetic provenance stays with the organiser and is disclosed after the blind phase.
2. **Tasks.** The analyst:
   1. characterises the population, buildings and energy system
   2. identifies behavioural patterns, anomalies and changes
   3. builds forecasting and flexibility models
   4. explains relationships and quantifies uncertainty
   5. recommends interventions with estimated effects
3. **Scoring.**
   - Findings on Baile Nua are scored against Baile Nua's hidden ground truth.
   - Findings on the real package are scored against real outcomes.
   - Conclusions and models from the synthetic package are re-tested on the real one; this is the decisive comparison.
   - "Which one is synthetic?" is asked last and reported as a secondary result.
4. **Tell audit.** Before each blind round, an automated pass and an adversarial analyst look for synthetic giveaways (ID patterns, timestamp regularity, missing failure modes, implausible joint values). Every tell found is fixed or logged as a limitation.
5. **Claim boundary.** Passing a blind evaluation shows that analysis transfers for the tasks and scope tested. It doesn't show that the data is real, and it can't replace S3 for any task.

The protocol runs at the S-track, after S2 data access, with a reduced pilot on open data after S1.

## 8. Implementation architecture

The recommendation is a Python generator with Numba-compiled hot loops, Parquet as the system of record, DuckDB for analysis, and PostgreSQL/PostGIS for metadata and geography. The whole run fits on one multi-core workstation or edge server; no cluster is needed for v1. BNIT and the web tools can stay in Brian's existing PHP/MySQL/MongoDB stack and read Parquet exports or an API. \[P\]

### 8.1 Components by maturity

| Component | Approach | Maturity |
| --- | --- | --- |
| Population synthesis | IPF + combinatorial optimisation (e.g. `ipfn`, PopulationSim-style) | Established method |
| Activity engine | Custom semi-Markov with household coordination; CREST demand model as structural reference | Custom; household negotiation needs research |
| Bounded-rationality and MIMIC willingness | Custom logit and habit model, MIMIC `chooseSignal` structure | Research: priors unvalidated until FlexSense data |
| Building physics | Custom grey-box RC in Numba; sample archetypes cross-checked against EnergyPlus | Established method, custom code |
| Heat pump, PV, BESS, EV models | `pvlib` for PV; documented empirical models for the rest | Established |
| Network | `pandapower` quasi-static power flow | Established |
| Signature rendering | Custom template + variation generator from public datasets | Custom; fidelity needs validation |
| Life-course engine | Discrete-time hazard models (dynamic microsimulation pattern) | Established method, custom code |
| Event engine | Custom, with shared latent drivers for compound events | Custom; compound correlation needs research |
| Observation model | Custom per device class | Custom |
| Benchmarks | scikit-learn, LightGBM, PyTorch, NILMTK, Gymnasium, Stable-Baselines3 | Established |

### 8.2 Execution model

**Coupling: a two-phase day with 15-minute epochs** \[P\]

1. **Phase A, plan (serial, deterministic).** At 04:00 each simulated day, town-level resolution runs in fixed ID order. It covers life events, illness contagion, event attendance, school and work schedules, venue assignment with capacity checks, shared vehicles and pre-drawn cross-household contacts (visits, minding grandchildren). The output is a frozen **daily exchange log**.
2. **Phase B, execute (parallel).** Households simulate the day in 15-minute epochs. Inside an epoch each household is independent: people, devices and physics step at 1 minute. Nothing crosses households except through the exchange log or the barrier.
3. **Epoch barrier.** Network power flow runs on all homes' net load. Network state (voltage, curtailment, outage status) is broadcast for the next epoch, and venue and commercial-building occupancy is aggregated. All reductions run in sorted ID order.

This approximation has known limits:

- Network feedback reaches homes with a lag of up to 15 minutes. Outages are pre-scheduled by S06, so they apply at the exact minute.
- Inverter volt-var response uses the previous epoch's voltage.
- Truly spontaneous minute-level interactions between households (a neighbour calls in on seeing a light on) are pre-drawn in Phase A rather than reactive. \[A\]

**Coupling-lag test.** Run the estate with 1-minute and 15-minute epochs. Compared: feeder peak, curtailed energy, venue occupancy (within 1%), plus voltage magnitude and violation duration, transformer and cable overload duration, curtailment onset and duration, ramp rates, coincident peaks, and controller decisions and constraint violations. Each metric has its own tolerance \[P\].

**Reproducibility contract** \[P\]

- **Order-independent randomness.** A counter-based RNG (Philox) is keyed by master seed, stream, entity ID, simulated day and draw counter. Results don't depend on execution order or worker count.
- **No shared mutable state.** Cross-household data moves only through the exchange log and barrier messages. Floating-point sums run in fixed order; no fast-math.
- **Checkpoints.** Full household and town state is saved at every day start, content-hashed and chained. `replay(home, day range)` = checkpoint + recorded exchange log, giving byte-identical output.
- **Upstream edits.** Changing history (for example a life event) invalidates every downstream checkpoint in the hash chain. Re-simulation restarts from the earliest affected one.
- **Tests in CI.** Identical hashes at 1, 8 and maximum workers. Replay of 100 random home-days per run. An injected order-dependent mutation must be caught.

**Coupling modes** \[P\]

| Mode | Network coupling | Device step | Use | Status |
| --- | --- | --- | --- | --- |
| C1 | 15-minute epochs | 1 min | Town generation, population and behaviour, long-term energy, general forecasting | Default |
| C2 | 1-minute epochs | 1 min (1 s for live devices) | Flexibility, feeder constraints, voltage, curtailment, network-aware control | **Mandatory** for network-sensitive research unless a task-specific equivalence test shows C1 is adequate |
| C3 | 1-minute quasi-static network | 1 s for live devices | Fast controllable-device experiments | Does **not** model 1-second network dynamics. Tasks where those matter must name a dedicated fast network model. |

**Co-simulation timing and safety contract** (applies to C1 to C3) \[P\]

Within each network interval k, the order is fixed:

1. The network state from solve k−1 is published, with a staleness stamp.
2. Agent actions for the interval are received, timestamped and logged.
3. A **local safety layer** checks every action against device limits (power, SoC, temperature bands for vulnerable occupants, minimum EV departure charge) and against a **conservative network envelope**. The envelope is the per-connection import and export headroom from solve k−1, shrunk by a staleness margin. Actions outside it are clipped or rejected, and the clip is logged and returned to the agent.
4. Devices step at their own resolution using only the accepted actions.
5. The power flow for interval k is solved on the realised net load.
6. Any violation is recorded as an event, and the envelope for k+1 tightens automatically.

This means a controller can never gain flexibility from stale network information. Violations that still occur within an interval are counted against the controller in evaluation. They are never silently corrected.

**Three kinds of replay** \[P\]

| Kind | What it does | Guarantee |
| --- | --- | --- |
| Observation replay | Reproduces an existing run, or any home and period of it, from checkpoint plus exchange log | Byte-identical |
| Intervention replay | **Forks** the whole coupled town at a checkpoint and re-simulates every coupled state downstream (households, venues, network, later events) | Deterministic given the fork point and intervention log |
| Counterfactual comparison | Compares two forks using common random numbers for draws the intervention can't affect | Paired differences with reported variance |

The replay API refuses to present an isolated single-household replay as a town-wide counterfactual. Any intervention forces a town fork.

### 8.3 Storage and APIs

- **Parquet** for data, partitioned by dataset, year and building. Zstandard compression.
- **DuckDB** for analysis and validation queries; PostgreSQL/PostGIS for geography, manifests and the scoring API.
- **Render API** (FastAPI): `render(building_id, channels, start, end, rate)` returns 1 Hz to 30 min series from events and seeds, with an LRU cache of hot slices.
- **Scoring API**: detectors submit change records and receive precision, recall and latency against D20, without ever seeing D20.

### 8.4 Indicative scale \[A\]

These are unmeasured order-of-magnitude estimates. They are replaced on Day 6 of week 1 by benchmarks on the estate slice: runtime, peak memory and storage per home-day, projected to the full town with a ×1.5 margin. Scale-up (E2) proceeds only if the measured projection fits the hardware.

| Item | Estimate for 3,000 people, 1,100 homes, 10 years |
| --- | --- |
| Activity intervals | About 0.4 billion rows (about 40 per person per day) |
| Appliance cycles | About 0.1 to 0.2 billion rows |
| Building physics steps | About 6 billion at 1 min; a cheap RC update, so CPU-hours rather than days with Numba |
| Stored ground truth | Tens of GB without 1-min physics state; a few hundred GB with it |
| One home-year at 1 Hz, one channel | About 31.5 million samples, rendered in seconds |
| Hardware | 32 to 64 cores, 128 to 256 GB RAM, 2 to 4 TB NVMe; GPU only for benchmarks |

### 8.5 Engineering discipline

- Git monorepo. The YAML schema generates DDL, validators and docs.
- Data versioning with DVC or lakeFS.
- CI runs on every commit: unit tests, property-based tests (Hypothesis) for invariants, determinism hash tests, the negative-control suite and the leakage test.
- Containers pin every dependency.
- Releases follow the HRSD pattern (v1, v2, …) with a datasheet, a FAIR metadata block, a validation report and a list of known failures for each release.

## 9. Implementation plan and gates (AI-assisted)

With Claude Code building around the clock, coding is no longer the bottleneck. The targets are a **working minimal implementation at the end of week 1 (E1)** and a **full-town, 10-year simulation candidate at the end of week 3 (E2)**. These are engineering targets. They say nothing about scientific validity, which is gated separately and can't be dated in advance. \[P\]

### 9.1 What sets elapsed time

| Driver | Covers | Controlled by | Effect on schedule |
| --- | --- | --- | --- |
| Agent coding | Code, tests, schema, documentation | Claude Code | Days; no longer limiting |
| Compute | Simulation runs, calibration loops, benchmarks, model training | Hardware | Hours to days per full-town iteration; measured on Day 6 |
| Data access | CER/ISSDA, Irish time-use microdata, POWSCAR | External bodies | Unknown; blocks scientific gates only |
| Human decisions | U-decisions (section 11), gate approvals | Brian | Hours if batched; blocking ones before Day 1 |
| Scientific validation | Real-data fidelity, causal tests, TSTR/TRTR, RL sim-to-real | Evidence | Cannot be promised a date |

### 9.2 Two tracks of gates

Engineering gates never need restricted data. Scientific gates never block engineering. Every gate is an automated report: tests, negative controls, a run manifest with hashes, and an explicit pass or fail per criterion.

| Gate | Track | When | Passes when | Releases |
| --- | --- | --- | --- | --- |
| E0 Design approval | Both | Before Day 1 | This design approved; E0 approval table complete (U03, U04, U08, U11, U16, U21, E1 scope, R09 interpretation); data-access applications submitted | Week 1 |
| E1 Engineering proof of concept | Engineering | End of week 1 | V0 invariants: zero failures. Byte-identical outputs at 1, 8 and maximum workers. Every negative control rejected by its intended test for its recorded reason. Population matches public Cobh SAPS marginals. A complete one-year run of the 50-home, about 140-person estate, integrating weather, occupancy, appliances, physics and observation, with at least one life event and one disruption, and replayed deterministically. MIMIC T1, T9 and T10 pass with at least 10,000 unique participants (5.14 counters). The report states engineering verification only: no behavioural calibration is claimed. Runtime, memory and storage measured and published. | Weeks 2 and 3 |
| E2 Simulation candidate | Engineering | End of week 3 | Full town, 10 years, invariants clean. Coupling-lag test passes. Scale benchmarks within hardware. Physical consistency at F1/F2. Event coverage complete. Privacy inference test run and reported. D28 to D31 pass the 6.5 tests. | Scientific track on the candidate |
| S1 Open-data fidelity | Scientific | Any time after E1 | V2 against openly available data (IDEAL, UK-DALE, REFIT, SEAI BER, CSO aggregates) | Evidence for S2 |
| S2 Irish fidelity | Scientific | After CER/ISSDA access | V2, discriminator and V3 tariff-trial replication on Irish data | S3 |
| S3 Functional equivalence | Scientific | After S2 | V4 TSTR/TRTR per task; RL sim-to-real stage 1 | Task-specific acceptance |
| R1 Release | Both | After S3 for each named task | Independent review, leakage checks, uncertainty reporting, list of validated uses, documented limitations | ML/RL release |

The earlier gates map as follows: G1 → E1 (engineering parts) and S1 (real-data parts); G2 and G3 → E2; G4 → R1.

**BNIT experiments on an unvalidated candidate** (agreed in review 2) are allowed from E2, under five conditions:

- Every output is labelled **UNVALIDATED SIMULATION EVIDENCE**.
- No claims of real-world effectiveness, safety, transferability or deployment readiness are made.
- The environment version, assumptions and fidelity limits accompany every result.
- These results can't satisfy S3 or R1.
- Any real-world or safety-critical control deployment needs separate approval.

**Gate passage depends on evidence, not elapsed time.** The week 1 and week 3 dates are targets only.

### 9.3 Week 1, day by day (engineering proof of concept)

| Day | Work | Automated acceptance (pass/fail) | Negative control that must fail |
| --- | --- | --- | --- |
| 0 (Brian) | Approve design (E0); settle blocking decisions; submit data-access applications; confirm hardware | Decisions logged in the review log | None |
| 1 | WP0: repo, YAML schema → DDL and validators, counter-based RNG and seed tree, checkpoint format, CI with invariant, leakage and determinism suites | CI green; schema diff against MIMIC 1.1 lists only the U18 gaps | Order-dependent RNG mutation; GT column in an OBS file |
| 2 | WP2: Cobh SAPS (public), scale-down, households, MIMIC traits, names, buildings at t0 | SAPS marginals within sampling tolerance; zero plausibility violations; name uniqueness | A population with a 10-year-old parent; marginals shifted 10% |
| 3 | WP-M1: MIMIC crosswalk, API runner, extended pool to 10,000+; T1, T9, T10 (T2 to T5 and T7 started) | 10,000+ completed participants; forbidden fields rejected; purge removes all | Forbidden-field batch; a planted position bias T10 must detect |
| 4 | WP3 part 1: estate of 50 homes; weather; F1/F2 physics; activity engine core with household coupling; presence | Presence invariant; physics energy balance; activity shares within time-use tolerance (open-data proxy flagged until WP1 delivers) | A person scheduled in two places; a heat-balance leak |
| 5 | WP3 part 2: devices and DER (live and rendered modes), observation model, render API, edge export | Energy closure within 0.1%; render determinism; export contains no GT | Export with an occupancy field; a non-deterministic render |
| 6 | Benchmarks and reproducibility: runtime, memory and storage per home-day; full-town projection with ×1.5 margin; parallel determinism; checkpoint replay of 100 random home-days | Projection fits hardware; all hashes identical | Shared mutable state injected into one worker |
| 7 | E1 gate report: results, known failures, decisions needed for weeks 2 and 3 | Report generated from CI artefacts only | None |

**Negative-control rule.** Each broken dataset declares its intended test and an **expected failure assertion** (the specific check and message). It passes only if that test fails for that reason. A generic non-zero exit, or a failure in another test, counts as a harness defect.

**Revision 3 effect on week 1.**

| Change | Effect on week 1 |
| --- | --- |
| Full one-year estate run with a life event and a disruption | Adds about one agent-day. Day 5 adds minimal life-event and disruption hooks; Day 6 runs the year. Acceptance is not weakened. |
| Comparing two scale-down methods with joint validation | About half a day on Day 2 |
| Expected-failure assertions; separate MIMIC counters; RL interface schema | Small; absorbed in Days 1 and 3 |
| C2 and C3 modes, intervention forking, G-C modes, privacy threat model | Moved to weeks 2 and 3; E1 needs only C1 plus contract tests |

Week 1 may therefore run to eight days. If it does, the date moves, not the tests.

### 9.4 Weeks 2 and 3 (full-town candidate)

| Week | Work | Automated acceptance |
| --- | --- | --- |
| 2 | WP4 behaviour depth and S08 mobility/EV; WP5 life course over 10 years on the estate, Mary scenario, D20 labels; WP6 calendar and events; C2 coupling and the timing contract (8.2); intervention replay by forking; G-C generator modes and the T6 null control (5.14) | Ablations degrade fit as expected; 10-year invariants clean; every D20 label observable at its tier; coupling-lag test (1-min vs 15-min epochs) within tolerance |
| 3 | WP7 town scale-up to 3,000 people, venues, S11 network; joint and spatial population validation (5.2); full 10-year run; WP-M2 linked MIMIC panel; privacy threat model and inference tests (7.8); E2 report | Venue presence consistent with person presence; feeder loading within physical limits; measured scale within the Day 6 projection; privacy test reported |

### 9.5 Evidence-dependent work (no dates)

- **WP1 data access and calibration targets.** Starts on Day 0. Public sources are used first and flagged; restricted sources replace them as they arrive.
- **S1 to S3 and WP8 validation campaign.** Runs on the E2 candidate, or on E1 for S1.
- **WP9 RL environment and sim-to-real.** Stage 1 needs S2 data; stage 2 needs Beaufort lab time.
- **WP10 release (R1).** Per validated task only.

Total agent build time to E2 is about three weeks \[A\]. The remaining duration depends on data access and evidence. The earlier 42 person-month figure was a human-engineering estimate and no longer applies.

### 9.6 Progress against gates

**E1 (9 October 2026): PASS, 8 of 8 after rework (first run 04:46: FAIL, 7 of 8).** The full report is `docs/E1_gate_report.md`; the task history is in Appendix A.

- **Passed:**
  - V0 invariants 7/7 (one skip, with its reason)
  - byte-identical Parquet at 1, 8 and 12 workers
  - 100 home-days replayed with zero difference
  - 23/23 SAPS marginals inside the simultaneous band
  - MIMIC T1, T9 and T10 with 11,664 unique participants
  - a full 2022 run of the 50-home, 147-person estate
  - benchmarks published
- **E1-3 (failed, then fixed).** Negative control NC-D2-03 (a 10% household-size shift) was not detected. A single realisation of about 1,100 homes resolves only about 12.8%. The 10% magnitude was set in this design without a power analysis, so this was a design defect, not only a code one (U26). Resolved at 09:28: a K = 20 ensemble check detects it, with power analysis and an audit of all 18 controls (Appendix A, task 2). The ensemble is judged against the declared procedure's own target, and that target's deviation from raw SAPS is bounded separately.
- **Scale.** One town-year fits the Mac (16.2 h, 23.2 GB including the ×1.5 margin). The ten-year E2 package (232 GB) doesn't fit the 77.8 GB free (K10, U24).
- **Key scientific finding.** Simulated space heat reaches 0.31 of CSO measured gas, and 0.32 on the held-out construction-period axis. The ratio falls from 0.43 for 1967–99 homes to 0.19 for post-2005 homes. That pattern is consistent with comfort-taking in efficient homes, plus three unmodelled loads (hot water, gas cooking, boiler losses). It is reported as a gap, not closed by tuning the physics (U22, U25).
- **Lesson.** Seven defects (I-027 to I-033) were found only by checks on the model's actual outputs, while 162 to 206 unit tests passed. These included appliance electricity 40% high, a 285 m² apartment and a 24.6 °C median indoor temperature (K21, U27).

**Week 2 progress (9 October, 11:18).**

- **Step 1 (U27), done.** The plausibility suite is built and runs on every package write. On the E1 package, simulated space heat is 0.308 of CSO measured gas (PL-GAS-01). That ratio is the acceptance test hot water, gas cooking and boiler losses (U25) and comfort-taking (U22) must raise.
- **Step 2 (U23), in progress.** A mixed-age slice was taken from Cobh's real older core rather than sampled: mean build year 1962 (E1 estate: 2005), 84% pre-1980, all BER letters A to G, six heating systems including a heat pump, PV, BESS and EV present. It has 115 people, at the lower bound of the E1 people band, because older-core households are smaller. The E1 estate is kept as a regression fixture.

**Week 2 progress (9 October, 19:00).** 405 tests pass.

- **U29, done.** Mixed-age slice at 60 homes and 131 people, with headroom.
- **U30, done.** 37 assumption flags swept against all 13,086 PxStat tables: 5 retired, 4 now sourced, 19 kept with search records, 9 found to use the wrong instrument.
- **I-039, closed at aggregate level.** ESB Networks' published LP1 domestic profile gives a peak and load-factor reference. The new check PL-PEAK-01 fails honestly on the overnight taper (I-044, owned by the behaviour work).
- **U25, done.** Hot water, gas cooking and boiler losses raise simulated against measured gas from 0.312 to 0.785 on the E1 estate, with nothing fitted.
- **I-047, the main finding.** A boiler error had hidden a modern-stock shortfall and inflated the old-stock excess, so the two partly cancelled. Corrected, the model responds to fabric about 1.8 times more steeply than metered gas does, in both directions.
- **U22, half done.** Comfort-taking flattens that response by about 30 points but saturates at 45%, short of the 4 to 7% spread in DBERNG01. The held-out test needs a slice spanning 1967–99 and post-2005 homes (I-049, U31). The remaining gap points to retrofits compressing the real heat-loss spread relative to BER labels, a week 3 fabric question (I-048).

## 10. Risk register

The three highest risks are unvalidated intervention response, missing Irish time-use evidence, and data-access delays. Each has a mitigation that keeps the claim honest even when the risk materialises.

| ID | Risk | Likelihood | Impact | Mitigation | Owner |
| --- | --- | --- | --- | --- | --- |
| K01 | Intervention response (to novel tariffs, P2P, HEMS asks) cannot be validated from historical data | High | High | Bound claims (7.4); sensitivity analysis over MIMIC priors; CER treatment replication; plan a field pilot | Brian |
| K02 | No recent Irish time-use diary microdata available | Medium | High | Use the best Irish source available, transfer from HETUS/UK TUS with Irish calibration on CER occupancy proxies; flag as \[A\] | WP1 lead |
| K03 | Delays in CER/ISSDA, IDEAL or CSO microdata access | Medium | High | Apply in WP0; design the slice so it can run on public aggregates first | WP1 lead |
| K04 | MIMIC trait priors wrong or weakly linked to behaviour | High | Medium | Treat as \[A\]; re-fit when FlexSense Ireland data arrive; report ablations with traits removed | Brian |
| K05 | Stereotyping through nationality mechanisms | Medium | High | Evidence-gated mechanisms; stereotype-guard test (7.7); external review | Reviewer |
| K06 | Overfitting to calibration data (memorisation) | Medium | High | Strict split hashing; DCR and membership-inference tests | WP8 lead |
| K07 | Signature library too small or too UK-centric for Irish appliances (electric showers, immersions) | High | Medium | Prioritise Irish captures at the Beaufort lab; mark appliances without local signatures | WP3 lead |
| K08 | Household negotiation and influence models have little quantitative evidence | High | Medium | Start simple and ablate; validate only emergent statistics (stagger, coincidence) | WP4 lead |
| K09 | Combinatorial explosion of event types makes compound validation impossible | Medium | Medium | Validate by class and by shared driver, not every pair | WP6 lead |
| K10 | Storage or compute larger than estimated | Low | Medium | Materialised in E1: 10-year package 232 GB against 77.8 GB free. Mitigation: daily checkpoints with re-run (U07), external SSD (U24) | WP3 lead |
| K11 | Scope creep from rich requirements delays the minimal slice | High | High | E1 fixes slice scope; anything new enters through the decision log | Brian |
| K12 | Synthetic names or biographies resemble real Cobh residents | Low | High | Name-combination uniqueness and public-figure check; no real addresses; synthetic flag in every record | WP2 lead |
| K13 | Detection benchmarks reward detectors that infer causes or sensitive states | Medium | High | Scoring only on observable-change labels (R25); review of detector outputs | BNIT lead |
| K14 | Validation datasets differ from Cobh (UK homes, 2009-era Irish homes) | High | Medium | Report domain gap; adjust for era and climate; never claim Cobh-level fidelity from UK data alone | WP8 lead |
| K15 | Stated–revealed gap size unknown for Irish households, so synthetic MIMIC answers and behaviour are linked by a guessed gap | High | Medium | Use the Kormos & Gifford range as prior; re-fit when FlexSense responses can be matched to metered behaviour | Brian |
| K16 | MIMIC/FlexSense trait priors come from a self-selected sample and over-represent engaged, prosocial people | High | High | Post-stratify to Cobh demographics; sensitivity runs with a less prosocial prior | WP2 lead |
| K17 | Circularity: MIMIC is tested on data generated with its own assumptions, so passing proves little | High | High | Independent willingness model with misspecification (5.14); null-mode tests; never report T-tests as real-world validation | Brian |
| K18 | Exported aggregates still reveal occupancy and routines, so the privacy claim is weaker than R09 implies | High | High | Inference-risk test (7.8); configurable export granularity; decision U20 | Brian |
| K19 | Non-determinism from parallel execution, float ordering or hidden state breaks replay | Medium | High | Reproducibility contract (8.2): counter-based RNG, sorted reductions, hash-chained checkpoints, multi-worker hash tests in CI | Engineering |
| K20 | The 15-minute epoch lag distorts network-coupled results (voltage control, curtailment) | Medium | Medium | Coupling-lag test; 1-minute epochs for network studies | Engineering |
| K21 | Tests check internal consistency but not the numbers the model produces, so wrong outputs pass (materialised in E1) | High | High | Output plausibility targets (U27); distributional invariants on written packages | Engineering |

## 11. Critical design decisions and unresolved questions

Thirty-one decisions are listed; U22 to U27 arose from the E1 run (9.6). U03 (proportional scaling) and U22 to U27 were approved by Brian on 9 October with the week 2 prompt (Appendix A, task 5). U03, U04, U08, U11, U16 and U21 block E0 (see the E0 approval table in section 13); the rest can be settled before their own work package starts.

| ID | Decision | Alternatives | Trade-off | Recommendation |
| --- | --- | --- | --- | --- |
| U01 | Do visitors, tourists, cruise passengers and in-commuters exist as persons? | (a) Full persons; (b) lightweight transient pool; (c) aggregate footfall only | (a) costly, (c) breaks venue presence logic | **(b)** transient persons with IDs, no life course |
| U02 | Model boundary for out-of-town work and school | (a) "Outside" state; (b) simulate Cork city venues | (b) doubles scope | **(a)**, with travel time and return-time distributions |
| U03 | Scaling Cobh to about 3,000 | (a) Whole small areas sampled; (b) proportional scaling of all | (a) keeps real spatial clustering; (b) smooths it | **Measured in E1: (b) proportional scaling had the smaller joint and spatial error, so the rule selects (b); Brian to confirm** |
| U04 | Time-use diary source | (a) Irish survey if microdata exist; (b) HETUS/UK TUS with Irish recalibration | Irish data may be old or unavailable | **(a)** if accessible, else **(b)**, flagged \[A\] |
| U05 | Signature datasets and licences | UK-DALE, REFIT, REDD, IDEAL, Beaufort lab captures | Licence terms and UK bias | Confirm licences in WP1; add Irish lab captures |
| U06 | Sensor tier mix across homes | (a) Realistic uptake (most homes meter only); (b) designed mix for experiments | (a) realistic, (b) balanced for testing | **(a)** in the base town; BNIT can re-tier |
| U07 | Store 1-min building state or re-run on demand | (a) Store; (b) daily checkpoints + re-run | (a) hundreds of GB; (b) slower queries | **(b)**, with cached hot slices |
| U08 | Simulated calendar years | (a) 2022 to 2031 (Census base year); (b) 2026 to 2035 (current) | (a) aligns with Census; (b) aligns with today's tariffs and DER | **(a)** with Census as t0; future years as projections |
| U09 | Granularity of health states | (a) Generic functional states; (b) named conditions | (b) adds sensitivity, little energy value | **(a)** only |
| U10 | Are static retail tariffs (including smart ToU) part of the base model? | (a) Yes, base; (b) all tariffs in BNIT | (b) leaves base behaviour unrealistic | **(a)** for existing retail tariffs; dynamic and flex signals stay in BNIT |
| U11 | Numeric acceptance thresholds in section 7 | Approve, tighten, or set per use case | Too loose proves nothing; too tight is never met | Approve as provisional, review at E1 |
| U12 | Independent reviewer for E0 and R1 | Internal colleague, external academic, ChatGPT cross-review plus a human | Independence vs availability | One human domain expert, plus model cross-review |
| U13 | Naming and versioning | HRSD\_Occupants inside Baile Nua vs a separate product | Clarity across HRSD and Baile Nua | Baile Nua vX with HRSD\_Occupants and HRSD\_Buildings as named layers |
| U14 | Link commercial buildings to Horizon Plaza (HRSD) models | Reuse vs new | Reuse saves effort but mixes scales | Reuse archetypes only |
| U15 | Generate safety-critical scenarios (prolonged inactivity of a lone older person) | Include as generic inactivity labels, or exclude | Needed to test the safety tier; must avoid medical framing | **Include** as observable inactivity only |
| U16 | How to reach 10,000+ MIMIC entries | (a) Baile Nua panel only (sessions); (b) extended pool only (participants); (c) both | (a) gives linked behaviour but about 2,300 participants; (b) gives scale without behaviour | (c) both pools, each marked in D26 |
| U17 | Synthetic marker in MIMIC | (a) consent\_version marker only; (b) also add participants.is\_synthetic | Schema 1.1 has no is\_synthetic column; the purge already handles both | (b), plus a pool code (BN-panel or HRSD-pool) in the marker |
| U18 | MIMIC value gaps found for Irish homes | Add "Home duties" and "Terraced" to MIMIC, or map to Other | Mapping to Other loses information MIMIC needs for Ireland | Add both values to MIMIC (a MIMIC change, not a Baile Nua one) |
| U19 | Session timing and rate limits | (a) Real-time API calls with a test-mode allowance; (b) back-dated direct import | (a) tests the real path but timestamps are run-time; (b) keeps simulated dates but skips API logic | (a) for testing, with the simulated date carried in D26 |
| U20 | Export granularity: privacy against settlement accuracy | (a) Home-level 15/30 min; (b) estate aggregate via EdgeWare; (c) compliance only; (d) home-level with calibrated noise | (a) is best for settlement and worst for privacy; (c) the reverse | Decide after the 7.8 test at E2; build all four as configurations |
| U21 | Execution environment and hardware | (a) Brian's own server; (b) cloud sandbox; (c) university compute | Benchmarks only mean something on the real target | Name the target machine at E0; see the E0 approval table |
| U22 | Build comfort-taking (rebound and prebound) in week 2 | (a) Behavioural mechanism; (b) tune physics; (c) defer | (b) hides the mechanism and breaks fabric parameters for every other use | (a), validated on the held-out construction-period axis |
| U23 | Slice composition | (a) Keep the modern estate (84% A/B, nothing below C, no heat pump); (b) mixed-age estate | (a) is unrepresentative of Cobh stock | (b), with pre-1980 homes and at least one heat pump, PV and EV |
| U24 | Storage for the 10-year package | (a) Apply U07: daily checkpoints, re-run on demand; (b) external SSD; (c) both | 232 GB measured against 77.8 GB free | (c) |
| U25 | Domestic hot water in week 2 | Add now, or defer | Needed for immersion flexibility and the gas gap | Add in week 2, with gas cooking and boiler losses |
| U26 | Negative-control magnitudes | (a) Enlarge the shift until detected; (b) power analysis plus ensemble generator-bias check, keeping 10% | (a) makes the test pass rather than right | Done 9 Oct: (b) implemented and audited across all 18 controls (I-034) |
| U27 | Output plausibility targets as a standing requirement | Every major output checked against a published Irish reference (energy by dwelling type, indoor temperature, appliance shares, floor areas) | E1 showed unit tests pass while outputs are wrong | Adopt; add to the V0/V2 suites before week 2 |
| U28 | Observation storage (D18) for the 10-year town (I-036) | (a) External SSD only; (b) apply R13 fully: D18 rendered on demand, release package holds 1-minute channels only for the sensored and sub-metered subset and the smart-meter 30-minute series for every home; (c) shorter span | 232 GB against 74 GiB free; full-rate D18 for every home contradicts R13 and D18's own "rendered on demand" storage rule | Decided 9 Oct (task 6): (b), plus an external SSD (about 2 TB) for headroom; privacy tests (7.8) run on the 15/30-minute export view, which (b) keeps. Amended (task 7): (b) still projected 93.7 GB with margin against 74.5 GB free, so without the SSD, T3/T4 1-minute channels are also rendered on demand and only the sub-metered subset is materialised |
| U29 | Mixed-age slice size: older-core households are smaller (2.0 to 2.4 people), so 50 homes sit exactly on the 115-person lower bound | (a) Accept the tightness; (b) about 60 homes; (c) widen the people tolerance | (a) breaks on any change; (c) weakens a test | (b): realistic household sizes, people within band with headroom |
| U30 | Sweep all remaining \[A\] flags against PxStat | Sweep now, or later | I-040 showed assumptions persisting where data existed | Now (about an hour); every \[A\] records what was searched |
| U31 | Held-out validation slice for comfort-taking (I-049) | (a) New selector for a slice spanning 1967-99 and post-2005; (b) defer to week 3 town | (b) leaves U22 unvalidated through week 2 | (a), used only for evaluation, never fitted on |

### 11.1 Where realism cannot yet be demonstrated

- **Intervention response** to signals that have never existed in Irish homes. Required evidence: randomised or quasi-experimental field data (O-CEI, REAP-type pilots).
- **MIMIC trait to behaviour link.** Required: matched MIMIC/FlexSense responses and metered behaviour for the same households.
- **Household negotiation and influence** dynamics. Required: intra-household sub-metering with diaries.
- **Nationality mechanisms** beyond household size and tenure. Required: Irish studies linking origin to practices and metered energy.
- **1 Hz Irish appliance signatures** (electric showers, immersion with diverters). Required: lab or field captures.
- **Rare compound events** at town scale. Required: long, local, high-resolution records, which are scarce.

Until that evidence exists, these components carry \[A\] in every release and are excluded from any equivalence claim.

## 12. Traceability matrix

Every confirmed requirement maps to at least one component, one validation method and one acceptance criterion. None is unmapped.

| Req | Component(s) | Dataset(s) | Validation | Acceptance criterion | WP |
| --- | --- | --- | --- | --- | --- |
| R01 | S02, S03, S11 | D01, D02, D17 | V1 review; network checks | Layout and network pass design norms; no high-rise | WP2, WP7 |
| R02 | Architecture boundary | All | Code review; no FLEXUS imports | Zero solution code in the Baile Nua repo | WP0 |
| R03 | S04 | D05, D06 | Synthesis report | 2,900 to 3,100 people; 1,000 to 1,100 homes | WP2 |
| R04 | S04 | D24 | Marginal fit to Cobh SAPS | Every SAPS marginal within the sampling-error band | WP2 |
| R05 | S04, S05, S07 | D05, D08, D10 | V2 occupancy and time-use | Activity shares within survey error | WP3, WP4 |
| R06 | S04, S07 | D05 | Trait distribution check; ablation | Traits present for 100% of persons; absent from OBS | WP2, WP4 |
| R07 | Section 5.8 mechanisms | D05, D10, D13 | Stereotype guard | ΔAUC ≤ 0.03; every mechanism cited | WP4, WP8 |
| R08 | S05, S03 | D03, D09 | 10-year demographic drift | Births, deaths, moves within vital-statistics CIs | WP5 |
| R09 | S12, S13 | D18, D19 | Export audit | D19 contains no occupancy-level or GT field; inference-risk test (7.8) reported per export configuration | WP3 |
| R10 | S03, S12 | D02, D04, D18 | Tier and heterogeneity report | Tier mix and asset mix match targets | WP2, WP3 |
| R11 | Data model | D05 to D11 vs D02 to D04 | Schema review | No person attribute stored on building tables | WP0 |
| R12 | S10, D22 | D13, D18 | NILM TSTR | TSTR F1 ≥ 0.85 × TRTR for flexible loads | WP8 |
| R13 | Render API, seed tree | D13, D18, D23 | Determinism hash test | Byte-identical re-renders | WP0, WP3 |
| R14 | S05 | All temporal | 10-year run | Complete run, invariants clean | WP5 |
| R15 | S07 | D10 | V2 time use; ablation | Within survey error; ablations degrade fit | WP3, WP4 |
| R16 | S07 | D10, D07 | Stagger and synchrony statistics | Morning stagger and joint meals within reference band | WP4 |
| R17 | S07, S05 | D09, D10 | Disruption frequency check | Rates within cited ranges | WP4 |
| R18 | S07 | D10 | Lapse, habit and fatigue tests | Observable lapse rates within reference | WP4 |
| R19 | All | D24 | V2 full suite | All V2 rows pass | WP8 |
| R20 | S06 | D14 | Event coverage audit | Every listed class present with a source | WP6 |
| R21 | S06 | D14, D17 | Coincidence, rebound, extremes | ADMD and tail tests pass | WP6, E2 |
| R22 | Benchmarks, RL env | All OBS | V4, 7.6, 7.7 | Section 7 thresholds | WP8, WP9 |
| R23 | S07, S08 | D11 | Presence invariant | Zero violations | WP3 |
| R24 | D20, scoring API | D20 | Detector benchmark | Latency per tier reported with CI | WP5, WP8 |
| R25 | Scoring API | D20 | Output audit | Records carry all required fields; no cause labels | WP5 |
| R26 | S04, D21, leakage test | D05, D08, D21 | Leakage and consistency tests | Zero GT columns in benchmarks; biographies consistent with records | WP2, WP8 |
| R27 | S04 name generator | D05 | Identity and uniqueness checks | Zero matches with public-figure list; unique names | WP2 |
| R28 | This document | All | Design review | Signed approval in section 13 | E0 |
| R29 | S04 trait model, D25 crosswalk | D05, D25 | Schema diff against MIMIC 1.1; trait-name audit | Zero unmapped MIMIC fields except the gaps listed in U18 | WP2, WP-M1 |
| R30 | HRSD API runner | D25, D26 | Tests T1 to T10 (5.14) | At least 10,000 completed synthetic participants; T1 to T10 pass or are reported as MIMIC findings | WP-M1, WP-M2 |
| R31 | Release packaging | All, by access class | Package audit; leakage test | Observable package contains zero GT fields; evidence view present for every release | WP10 |
| R32 | Blind evaluation protocol | Observable packages, real reference package | 7.9 protocol; tell audit | Conclusions and models transfer to real data within section 7 margins; all tells fixed or logged | S-track |
| R33 | S12 non-sensor observation models | D28 to D31, operator log, extra D18 channels | 6.5 tests: too-good, join, consistency, planted-rate recovery, blind-safety | All 6.5 tests pass at E2 | Weeks 2 and 3 |

## 13. DESIGN REVIEW: AWAITING APPROVAL

**No data generation, implementation code or development is authorised until this design is independently reviewed and approved.** Approval (gate E0) releases week 1 engineering work only. Each later stage is released by its own engineering or scientific gate (9.2).

The reviewer is asked to confirm or amend:

- [ ] Requirements R01 to R33 are complete and correctly stated (section 2)
- [ ] The architecture and its 1-minute co-simulation boundary (section 3)
- [ ] The modelling methodology, especially the household coupling and nationality mechanisms (section 5)
- [ ] The dataset inventory and GT/OBS/META separation (section 6)
- [ ] Validation levels V0 to V4 and the provisional thresholds (section 7, U11)
- [ ] The technology stack (section 8)
- [ ] The plan, the E1 minimal slice and the two gate tracks (section 9)
- [ ] The risk register (section 10)
- [ ] Decisions U01 to U21, and the HRSD → MIMIC test plan (5.14) (section 11)

| Role | Name | Decision | Date |
| --- | --- | --- | --- |
| Design owner | Brian O'Regan |  |  |
| Independent reviewer | (U12) |  |  |
| Model cross-review |  |  |  |

### E0 approval table (Brian)

E0 opens when every row below is set to "Approve default" or "Change" (with the change written in). All other U-decisions are settled at their own gates.

| # | Item | Recommended default | Consequence of the default | If changed | Decision |
| --- | --- | --- | --- | --- | --- |
| 1 | U03 Scale Cobh to about 3,000 | Build both methods; pick the one with smaller joint and spatial error (5.2) | Half a day extra on Day 2; the choice is made from evidence | Pick one now and skip the comparison | Pending |
| 2 | U04 Time-use source | Irish diaries if accessible; meanwhile HETUS/UK TUS with Irish recalibration, flagged as an assumption | E1 activity engine is verified, not calibrated | Wait for Irish data before building the activity engine (delays E1) | Pending |
| 3 | U08 Simulated years | 2022 to 2031, Census 2022 as t0 | Census-aligned; 2026 onward are projections | 2026 to 2035: aligned to today's tariffs and DER, but t0 needs projecting from 2022 | Pending |
| 4 | U11 Acceptance thresholds | Section 7 margins as provisional; reviewed at E1 and S1 | Testing starts with explicit, revisable margins | Set tighter or task-specific margins now | Pending |
| 5 | U16 Reaching 10,000+ MIMIC entries | Both pools: linked town panel and unlinked extended pool; 10,000 counted as unique participants | Volume plus linked behaviour; counters kept separate | Panel only (about 2,300 unique participants) or pool only (no linked behaviour) | Pending |
| 6 | U21 Execution environment | Brian names the machine. Minimum: 32 to 64 cores, 128 to 256 GB RAM, 2 to 4 TB NVMe; E1 may run in a cloud sandbox if Day 6 benchmarks show it fits | Benchmarks are measured on the real target | A smaller machine: E2 scale may not fit, found on Day 6 | Pending |
| 7 | E1 scope | 50 homes, about 140 people, one year, C1 coupling, one life event and one disruption, MIMIC export of 10,000 unique participants | Week 1 may run to about eight days | Narrow (for example no MIMIC in E1) or widen | Pending |
| 8 | R09 interpretation | No occupancy field transmitted; inference risk measured and reported (7.8) | Honest privacy claim; feeds U20 and the DPIA | Stricter: no home-level export at all | Pending |

### Review log

Record every change proposed during review here, with who proposed it, why, and the outcome.

| # | Section | Proposed by | Change and reason | Outcome |
| --- | --- | --- | --- | --- |
| 1 | 5.13, 5.14 | Brian | Align with MIMIC as closely as possible; generate 10,000+ HRSD entries into MIMIC to test it | Accepted: R29, R30, 5.14, D25, D26, U16 to U19 |
| 2 | 9 | Brian | Plan for AI-assisted build, not human person-months | Accepted: section 9 rewritten |
| 3 | 8.2 | ChatGPT review 1 | Daily parallelism conflicts with minute-level coupling | Accepted: two-phase day, 15-minute epochs, coupling-lag test |
| 4 | 5.6, 3.2 | ChatGPT review 1 | Post-hoc 1 Hz rendering can't capture control effects | Accepted: live mode for controllable devices; sub-second dynamics out of scope |
| 5 | 9.2 | ChatGPT review 1 | G1 depends on data that may be delayed | Accepted: separate engineering (E) and scientific (S) gates |
| 6 | 5.14 | ChatGPT review 1 | Passing MIMIC tests can't show real-world validity | Accepted: independence protocol, three generators, claims labelled |
| 7 | 8.2 | ChatGPT review 1 | Seeds alone don't guarantee reproducibility | Accepted: reproducibility contract with checkpoints and replay |
| 8 | 5.7 | ChatGPT review 1 | Two-zone RC is not enough for every task | Accepted: fidelity tiers F1 to F3, declared per task |
| 9 | 7.8 | ChatGPT review 1 | Aggregates can reveal occupancy | Accepted: inference-risk test, U20 |
| 10 | 8.4 | ChatGPT review 1 | Scale estimates unmeasured | Accepted: measured on Day 6; E2 depends on it |
| 11 | 7.2 | ChatGPT review 1 | Dataset count inconsistency (24 vs 26) | Fixed |
| 12 | 8.2 | ChatGPT review 2 (A1, Q1) | Common timing and safety contract; C1/C2/C3 modes; wider lag-test metrics | Accepted: contract with conservative network envelope; C2 mandatory for network-sensitive work |
| 13 | 8.2 | ChatGPT review 2 (A2) | Interventions break single-household replay | Accepted: observation replay, intervention forking, counterfactual comparison |
| 14 | 7.6 | ChatGPT review 2 (A3) | Privileged information can leak through reward or diagnostics | Accepted: five-interface boundary, scalar reward only, probe and audit tests |
| 15 | 5.2 | ChatGPT review 2 (A4) | Marginals don't prove joint or spatial representativeness | Accepted: both scale-down methods built and compared on joint and spatial metrics |
| 16 | 7.1, 7.5, 5.7, 7.8 | ChatGPT review 2 (V1 to V4, Q2) | Non-inferiority margins; source-use register; physical validity levels; privacy threat model and wider metrics | Accepted |
| 17 | 5.14, 9.2, 9.3 | ChatGPT review 2 (Q3, Q4, V5) | Full-year E1 slice; participant counters; expected-failure negative controls; G-C modes; T6 null control; verify vs diagnose; old gate references | Accepted; week 1 may run to about eight days |
| 18 | 9.2 | Claude, agreed in review 2 | BNIT experiments on the E2 candidate before scientific validation | Accepted with five conditions; labelled UNVALIDATED SIMULATION EVIDENCE |
| 19 | All | ChatGPT review 3 | Accept A1 to A4 and V1 to V5; freeze architecture; proceed to E0 table | Architecture frozen at revision 3 |
| 20 | 7.6, 7.5 | ChatGPT review 3 | Leakage probe must measure excess over valid inference; feeder-level resampling for network claims | Recorded as implementation clarifications |
| 21 | 6.3, 7.9, D27 | ChatGPT, answering Brian's question | Three delivery packages; blind consumer evaluation; tariffs, contracts and connection limits; provenance and quality codes | Adopted by Brian (R31, R32) |
| 22 | 6.4, D28 to D31 | Claude, answering Brian's question | Study protocol and selection, meter-point keying, imperfect surveys, recorded vs true metadata, embedded trial, sub-metered subset, external series, operator incident log | Adopted by Brian (R33); observation rules added in 6.5 |
| 23 | 6.5, D15, 3.1, 9.2 | ChatGPT review 4 | Verify D28 to D31 are observational, temporally consistent, realistically imperfect and blind-safe; non-sensor outputs need their own observation models | Accepted: 6.5 rules and tests; D15 reclassified to GT with D31 as station weather; S12 scope clarified; E2 criterion added |
| 24 | 9.3, 9.6, 7 | CC, task 2 (E1 rework) | Negative-control magnitudes set by power analysis; generator-bias checks run as seed ensembles; population checks use two references (procedure target, and target vs SAPS); controls must be auto-discovered by the test suite | Accepted as implementation rules; no architectural change |

## Appendix A. HRSD\_Occupants Log

Every task given to Claude Code (CC) for HRSD\_Occupants, plus operational facts about what it runs and creates (environments, containers, generated data), newest first. Each row gives the date issued, the task, its status and outcome, and the sections of this review it changed. Root folder: `/Users/brianoregan/Desktop/HRSD_Occupants`.

| # | Date issued | Task | Status | Outcome | Review sections updated |
| --- | --- | --- | --- | --- | --- |
| 9 | 10 Oct 2026, 00:3x | r4 saved in docs/ (retire Part C). U31/I-049: build a held-out slice spanning 1967-99 and post-2005 and run the U22 held-out half, evaluation only. I-048: schedule the retrofit hypothesis for week 3 fabric work, no tuning now. I-044: fix the overnight taper within step 4. Then week 2 steps 4 to 9 and W2 checkpoint. | Pending send | Not yet sent | 9.6, 11 (U31) |
| 8 | 9 Oct 2026, 11:2x | U29: grow the mixed-age slice to about 60 homes so people sit inside the band with headroom. U30: sweep every \[A\] flag against PxStat and record what was searched. I-039: find or build a peak and load-factor reference before S11. Then U25 and U22. | Done | Done 9 Oct, 19:00; 405 passed, 1 skipped. U29: slice 60 homes, 131 people, 16 of headroom. U30: 37 \[A\] flags swept over 13,086 PxStat tables (5 retired, 4 source found, 19 kept, 9 wrong instrument). I-039 closed at aggregate level with ESB Networks LP1 profile; PL-PEAK-01 now sourced and failing honestly (I-044, overnight taper). U25: gas ratio 0.312 to 0.785 on the E1 estate, nothing fitted. I-047: a boiler error had masked a modern-stock shortfall and inflated old-stock excess; corrected, the model's fabric response is about 1.8 times steeper than metered gas in both directions (consistent with DBERNG01). U22: comfort-taking flattens simulated gas by about 30 points but saturates at 45% and can't reach DBERNG01's 4 to 7%; held-out half blocked, needs a slice spanning 1967-99 and post-2005 (I-049); residual points to retrofit compressing real heat-loss spread (I-048, week 3). r4 still not on disk. | 11 (U29, U30) |
| 7 | 9 Oct 2026, 10:3x | r4 delivered to docs/ (Claude exported it; Brian saves it): retire DECISIONS.md Part C into r4. Storage fallback (U28 amended): if no external SSD is attached when the full 10-year town run is reached, D18\_sensored is also rendered on demand and only the sub-metered subset is materialised; keep the ×1.5 margin. Continue with the plausibility suite and week 2. | Done | Sent about 10:40, done by 11:10. (1) r4 still not on disk: Brian had not yet saved the exported file into docs/, so Part C was kept and nothing was claimed. (2) U28 fallback fits: 47.06 GB raw, 70.59 GB with margin against 74.54 GB free (3.9 GB spare); week 3 step 5 proceeds under it. A drive detector now rejects the internal Vault disk image by protocol and backing file. Byte-identical re-render test proved on Parquet bytes, covering the dropped channels. | 11 (U28 amended) |
| 6 | 9 Oct 2026, 10:25 | Rulings for I-035 and I-036 (U28): use design review r4 in docs/ as the single reference; apply R13 fully (D18 rendered on demand); release package holds smart-meter 30-minute series for all homes, 15-minute D19 views, and 1-minute/1 Hz D18 only for T3/T4 tiers and the sub-metered subset; privacy tests on the export views; re-project the 10-year package and run it only if it fits 74 GiB with ×1.5 margin; continue week 2 step 1 | Done | Done 10:31. U28 re-projection (scaled from the E1 measurement, with a self-check that caught and fixed a projection bug): 10-year town 62.46 GB raw, 93.69 GB with ×1.5 margin, against 74.5 GB free, so it doesn't fit and CC won't run it. Largest: D18\_sensored 33.83 GB (T3/T4 at 1 minute, 10% of homes, 54% of package), D19 16.02, D13 events 7.36, D18 meter 2.87, D16 2.29. 10 years on the slice 4.54 GB and a town-year 9.37 GB fit. I-038: r4 not on the Mac, so Part C of DECISIONS.md was kept (provisional) and now includes U28. CC moved on to the U27 plausibility suite. | 11 (U28 decided: option b plus SSD) |
| 5 | 9 Oct 2026, 10:12 | Weeks 2 and 3 to gate E2. Preconditions: task 4 done and suite green, E1 PASS regenerates. Week 2: plausibility suite (U27), mixed-age slice (U23), hot water, gas cooking and boiler losses (U25), comfort-taking (U22), behaviour depth and mobility/EV, 10-year life course on the slice, calendar and events, C2 coupling and timing contract, intervention forking, G-C modes and T6 null control, W2 checkpoint. Week 3: full town and network, joint and spatial validation, 6.4 observable additions with 6.5 tests, privacy threat model and attacks, full 10-year run (storage on external drive, U24), linked MIMIC panel, three delivery packages and tell audit, E2 gate report. | Running | Started 10:12. Preconditions: (1) PASS; (2) PASS, E1 8/8 regenerates byte-identically (sha 1c004a00f2e4750f); (3) partial, I-035: CC's local r3 copy has no 9.6 or U22 to U27, so these were recorded in DECISIONS.md Part C from the prompt. BLOCKING I-036: \<SSD\_PATH> not set and no external drive attached; /Volumes/Vault is an encrypted sparse bundle on the internal disk, not extra space. 10-year town package 232 GB against 74 GiB free; D18 dominates (531 MB, 66.1M rows per estate-year). CC will stop before the full 10-year run and proceeds with week 2 step 1 (plausibility suite) meanwhile. Progress at 11:18: step 1 done 11:10 (U27 plausibility suite built and run on the E1 package; issues I-039 and I-040; PL-GAS-01 ratio 0.308 is the acceptance test that U25 and U22 must raise; full suite 277 passed, 1 skipped; commit 5dc44f1). Step 2 (U23) in progress: mixed-age slice selected from Cobh's older core small areas (047107xxx): mean build year 1962 (E1 estate 2005), 84% pre-1980, BER A to G, one heat pump, six heating systems, PV/BESS/EV all present, 115 people (lower bound of the E0-7 people band); E1 estate kept unchanged as regression fixture. CC context near auto-compact; PROGRESS.md carries state. Steps 1 and 2 done by 11:20. U27 detail: all six evaluable checks pass on E1 (indoor median 19.92 °C); appliance shares, EV/heat-pump consumption and peak/load factor have no machine-readable Irish source (I-039, all 13,086 PxStat tables searched), so feeder peaks are unchecked; SILC HAS02 found for appliance ownership, retiring 7 assumed priors (I-040); 23 controls audited, none below resolution. Raised: slice sits exactly on the 115-person lower bound (U29); sweep all remaining \[A\] flags against PxStat (U30). Next: U25 then U22. Needs U28. Approves U03 and U22 to U27. | 11 (U03, U22 to U27 approved) |
| 4 | 9 Oct 2026, about 09:30 | Fix the test import gap properly and re-run the full suite | Done | Done (confirmed 10:22 as task 5 precondition 1). 17 of 17 controls declared and collected by pytest; CLI and suite share import\_all\_controls(). Full suite: 251 passed, 1 skipped, 0 failures (8 min 10 s). | Pending |
| 3 | Recorded 9 Oct 2026, 08:37 (started 8 Oct, about 22:30, during task 1) | Environment: local MIMIC instance in Docker, project bailenua-mimic-local (mysql-1: MySQL 8 on port 33199; web-1: MIMIC web and API on port 18099), started by CC from MIMIC's own docker-compose so synthetic participants never touch the live MIMIC | Running | Holds the 11,664 unique synthetic participants created in task 1 (marker SYNTHETIC-HRSD-v1). Idle (about 5.7% CPU). Not needed by task 2; safe to stop (data kept), delete only after MIMIC testing ends. | None (operational record) |
| 2 | 9 Oct 2026, 08:2x | Fix NC-D2-03 so E1-3 passes. Claude recommended replacing this with: power analysis for the check; an ensemble generator-bias check over K seeds with the 10% shift kept; a false-positive control; the power-analysis rule applied to all negative controls; regenerate the E1 report. | Done | Done 9 Oct, 09:28. E1 now PASS, 8 of 8. Power analysis (D-026): one realisation of 1,092 homes resolves only 12.8%; 95% power at 10% needs 3,664 households. The generator is deterministic in this marginal (across-seed SD about 1e-16), so a K = 20 ensemble check detects NC-D2-03 at max \|z\| 50 against a band of 3.07, and a correct generator passes. Design change: the ensemble tests against the declared procedure's own target; that target's deviation from raw SAPS is bounded separately (two references). Audit I-034: 18 controls, none below resolution (thinnest NC-D2-04 at 1.13×). Found that 8 of 17 negative controls were never in the pytest suite (CLI only); discovery now shared. | 9.6, 11 (U26) |
| 1 | 8 Oct 2026, evening | E1 engineering proof of concept (week 1 prompt): schema, seeds, CI, Cobh population with both scale-down methods, MIMIC export, 50-home estate for 2022, benchmarks, E1 gate report | Done, gate failed | E1 FAIL, 7 of 8 criteria met (E1-3: NC-D2-03 not detected below the check's 12.8% resolution). 11,664 unique MIMIC participants; 147-person estate run for all of 2022; issues I-027 to I-033; space heat 0.31 of CSO gas (held-out 0.32); proportional scaling measured better (U03). Report finished 9 Oct, about 04:46. | 9.6, 10 (K10, K21), 11 (U03, U22 to U27) |
