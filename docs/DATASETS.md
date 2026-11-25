# Baile Nua: HRSD_Occupants Dataset Catalogue

### Synthetic occupants of an Irish town, calibrated to Cobh

**UNVALIDATED SIMULATION EVIDENCE: E1 engineering candidate**

> **v1 candidate. Not a release. Do not use for published results.**

| | |
|---|---|
| Version | v1 candidate |
| Generated | 2026-10-12T12:01:59 |
| Git HEAD | `574e59f65f167e0ff086c0422f3e484f262eb4fc` |
| Schema version | 1.0.0 |
| Design revision | 3, as the schema file declares it — the newest design document on disk is `Baile_Nua_Technical_Design_Review_r4.md` (see Appendix D.6) |

### Headline figures

| | | from |
|---|---|---|
| Town residents | 2,917 | `work/town*/town_diagnostics.json` |
| Town homes | 1,092 | `work/town*/town_diagnostics.json` |
| Residents in this package | 147 | `v1/run_diagnostics.json` |
| Homes in this package | 50 | `v1/run_diagnostics.json` |
| Years covered, life course | 2022-2031 (10 years) | `v1/evidence/wp5_tenyear.json` |
| Time coverage, this package | 2022-01-01 00:00:00+00:00 → 2023-01-01 00:00:10.678580951+00:00 | timestamp statistics of every present dataset; the latest is `D18.ts`, which carries past the simulated year because the device clock error in D18 is modelled rather than corrected |
| Datasets declared | 31 | `schema/datasets.yaml` |
| Datasets present in v1 | 5 | files on disk |
| Datasets partial | 4 | rows in an evidence artefact |
| Datasets missing from v1 | 22 | absence on disk |
| Total size of `v1/` | 737.1 MB | `stat()` |

### The three delivery packages

| Package | Who it is for |
|---|---|
| **Observable view** | model developers, BNIT experiments, blind evaluators |
| **Ground-truth view** | scoring services and diagnosis only; never a model under test |
| **Evidence view** | everyone; it accompanies every release |

Every figure in this document is read from the files it names. The per-dataset descriptions draw on design revision 4; every factual claim beside them is checked against disk, and where there is no artefact there is no number.

<div style="page-break-after: always;"></div>

## Contents

### Observable

| Dataset | Title | Class | Status |
|---|---|---|---|
| [D18](#d18) | Rendered device readings with noise and gaps | OBS | present |
| [D19](#d19) | What leaves each home: aggregates, energy profile, flexibility compliance | OBS | present |
| [D25](#d25) | HRSD participants, profiles, MCV, sessions and responses in MIMIC schema 1.1 | OBS | missing |
| [D27](#d27) | Supplier tariff, ToU and export rates, switches, flexibility and P2P terms, connection limits | OBS | missing |
| [D28](#d28) | Recruitment, response rates, consent to sensors, dropouts, trial arms and periods | OBS | missing |
| [D29](#d29) | Questionnaire answers with calibrated reporting error and non-response | OBS | missing |
| [D30](#d30) | Recorded building and asset data, stale or wrong at realistic rates | OBS | missing |
| [D31](#d31) | Station weather, wholesale prices, carbon intensity, system demand, flex events | OBS | missing |

### Ground truth (+ observable view)

| Dataset | Title | Class | Status |
|---|---|---|---|
| [D03](#d03) | Dated building events (extension, retrofit, asset added or removed) | GT | partial |
| [D17](#d17) | Feeder and transformer loading, voltages, outages | GT | missing |

### Ground truth

| Dataset | Title | Class | Status |
|---|---|---|---|
| [D01](#d01) | Parcels, streets, venues, network topology | GT | missing |
| [D02](#d02) | HRSD_Buildings: fabric, archetype, BER, systems, physics parameters | GT | missing |
| [D04](#d04) | Appliances, heating, PV, BESS, chargers, vehicles, with owner and lifetime | GT | missing |
| [D05](#d05) | HRSD_Occupants: persistent characteristics and trait vector | GT | missing |
| [D06](#d06) | Who lives where, from when to when | GT | missing |
| [D07](#d07) | Kin, partner, carer, friend, co-worker edges | GT | missing |
| [D08](#d08) | Evolving states, slowly changing (SCD-2) | GT | missing |
| [D09](#d09) | Births, deaths, moves, jobs, health states, decisions | GT | partial |
| [D10](#d10) | Person activity intervals with location and co-participants | GT | missing |
| [D11](#d11) | Person location intervals - the no-double-occupancy source | GT | present |
| [D12](#d12) | Origin, destination, mode, vehicle, distance | GT | missing |
| [D13](#d13) | Cycle start/end, programme, signature ID, energy | GT | present |
| [D14](#d14) | Event instances, phases, footprint, attendance | GT | missing |
| [D15](#d15) | True site weather and solar geometry driving physics and behaviour | GT | missing |
| [D16](#d16) | Zone temps, RH, CO2, DHW, heat delivered | GT | present |
| [D20](#d20) | Ground-truth labels for detector scoring (onset, type, persistence) | GT | partial |
| [D21](#d21) | Human-readable narratives generated from D05 to D09 | GT | missing |
| [D26](#d26) | Crosswalk to person_id, true traits, planted segments, propensity, gap, test settings | GT | missing |

### Evidence

| Dataset | Title | Class | Status |
|---|---|---|---|
| [D22](#d22) | Appliance waveform templates and variation parameters | META | missing |
| [D23](#d23) | Code and data versions, parameters, seeds, checksums | META | missing |
| [D24](#d24) | Every empirical target with source, version and tolerance | META | partial |

### Appendices

- [A. Folder tree of `v1/`](#appendix-a)
- [B. Keys and joins](#appendix-b)
- [C. Conventions](#appendix-c)
- [D. Design against disk](#appendix-d)
- [E. Glossary](#appendix-e)

<div style="page-break-after: always;"></div>

<a id="d01"></a>

## D01 · Parcels, streets, venues, network topology

The town's geography: parcels, streets, venues and the topology of the low-voltage network. It is the substrate every other dataset refers to when it says where something is, and it does not change during a run.

**Key points**

- One row is one geographic feature — a parcel, a street segment, a venue or a network element.
- Built once at t0 from the small-area boundaries and the venue stock, then held fixed.
- Carries the feature geometry, so it is the only dataset whose declared storage is GeoParquet rather than Parquet.
- Ground truth: the network topology tells a model where the constraints are, which is part of what a network model is supposed to infer.

**Facts**

| | |
|---|---|
| Class | GT — Ground truth. Never given to a model under test. |
| Package | Ground truth |
| Path | not present in `v1/` |
| Format | declared `geoparquet` |
| Partitioning | none declared |
| Rows | — |
| Size | — |
| Time span | — |
| Resolution | feature |
| Primary key | grain `feature` |
| Status | **missing** |

**Schema** — not available: the dataset is not on disk in `v1/`. It is **missing**.

The declared schema has 9 fields: `feature_id`, `feature_kind`, `geometry_wkt`, `venue_type`, `capacity`, `feeder_id`, `estate_id`, `valid_from`, `valid_to`.

**Sample** — none: no rows on disk in `v1/`.

**Joins**

- No join keys present on disk for this dataset.

**Validation**

No check in the artefacts names this dataset, and no module opens it by name. That is a statement about the evidence on disk, not a claim that the dataset is unchecked.

Links are attributed from the artefacts themselves — a check is listed where its own record names the dataset — rather than from a mapping kept in the generator, which would go stale.

<div style="page-break-after: always;"></div>

<a id="d02"></a>

## D02 · HRSD_Buildings: fabric, archetype, BER, systems, physics parameters

Every dwelling's fabric, archetype, BER, heating system and the physics parameters derived from them. This is the input the thermal model solves and the truth that a building-stock estimator is trying to recover.

**Key points**

- One row is one building at one version; a passport event in D03 closes a version and opens the next.
- The element U-values are derived from the assessed-fabric source, which is why that source can calibrate the model and cannot validate it.
- Holds both the as-built and the current state, so a retrofit's before and after are both recoverable.
- Ground truth. The observable counterparts are the recorded metadata in D30, which is stale and wrong at realistic rates.
- Must not be joined to an observable dataset to score a model that was given D30: that compares a model against its own input.

**Facts**

| | |
|---|---|
| Class | GT — Ground truth. Never given to a model under test. |
| Package | Ground truth |
| Path | not present in `v1/` |
| Format | declared `parquet` |
| Partitioning | none declared |
| Rows | — |
| Size | — |
| Time span | — |
| Resolution | building x version |
| Primary key | grain `building x version` |
| Status | **missing** |

**Schema** — not available: the dataset is not on disk in `v1/`. It is **missing**.

The declared schema has 34 fields: `building_id`, `version`, `valid_from`, `valid_to`, `premises_id`, `estate_id`, `dwelling_type`, `build_year`, `floor_area_m2`, `storeys`, `archetype_id`, `ber_band`, `ber_kwh_m2_yr`, `heating_fuel`, `heating_system`, `heating_control`, `tenure`, `sri_class`, `sri_score`, `rc_r_ie`, `rc_r_ea`, `rc_r_zz`, `rc_r_inf`, `rc_c_living`, `rc_c_sleep`, `rc_c_env`, `rc_solar_aperture_m2`, `rc_vol_living_m3`, `rc_vol_sleep_m3`, `ach_base`, `heat_emitter_w`, `dhw_tank_litres`, `fidelity_tier`, `seed`.

**Sample** — none: no rows on disk in `v1/`.

**Joins**

- No join keys present on disk for this dataset.

**Validation**

No check in the artefacts names this dataset, and no module opens it by name. That is a statement about the evidence on disk, not a claim that the dataset is unchecked.

Links are attributed from the artefacts themselves — a check is listed where its own record names the dataset — rather than from a mapping kept in the generator, which would go stale.

<div style="page-break-after: always;"></div>

<a id="d03"></a>

## D03 · Dated building events (extension, retrofit, asset added or removed)

The building passport: dated events that change a dwelling — an extension, a fabric retrofit, an asset added or removed. Each event changes the physics from its own date onward rather than from the start of the year it falls in.

**Key points**

- One row is one dated change to one building.
- Drives the dwelling's version history in D02 and the asset lifetimes in D04.
- Has a redacted observable view: that an event occurred and when, without the parameters that say what it did.
- The un-redacted form is ground truth — it is the answer to the change-detection task that D20 scores.

**Facts**

| | |
|---|---|
| Class | GT — Ground truth. Never given to a model under test. |
| Package | Ground truth (+ observable view) |
| Path | `v1/evidence/wp5_tenyear.json` |
| Format | declared `parquet` |
| Partitioning | none declared |
| Rows | 45 (in an evidence artefact) |
| Size | — |
| Time span | `effective_day` 31 → 3621 (day index from the run's first day, not a date) |
| Resolution | event |
| Primary key | grain `event` |
| Status | **partial** |

**Schema** — not available: the dataset is not on disk in `v1/`. It is **partial**.

Rows exist outside the released packages:

| Artefact | Key | Rows | Columns |
|---|---|---|---|
| `v1/evidence/wp5_tenyear.json` | `d03_passport_events` | 45 | building_id, decided_day, driver, effective_day, event_type, from_ver… |

The declared schema has 10 fields: `passport_event_id`, `building_id`, `event_type`, `effective_at`, `decided_at`, `from_version`, `to_version`, `parameters_changed`, `driver`, `life_event_id`.

**Sample** — five rows as they are held in `v1/evidence/wp5_tenyear.json`. The dataset has no released Parquet part, so these are the rows there are.

| `passport_event_id` | `building_id` | `event_type` | `measure` | `effective_day` | `decided_day` | `from_version` | `to_version` | `parameters_changed` | `driver` | `life_event_id` |
|---|---|---|---|---|---|---|---|---|---|---|
| BP-B-000841-2022-retr… | B-000841 | retrofit | retrofit_fabric | 331 | 241 | 1 | 2 | {"rc_r_ie": "changed"… | WP5 ten-year life cou… | LE-2022-RETROFIT_FABR… |
| BP-B-000856-2022-der_… | B-000856 | asset added | der_battery | 34 | 0 | 1 | 2 | {"bess_kwh": "changed… | WP5 ten-year life cou… | LE-2022-DER_BATTERY-0… |
| BP-B-000862-2022-der_… | B-000862 | asset added | der_pv | 45 | 0 | 1 | 2 | {"pv_kwp": "changed",… | WP5 ten-year life cou… | LE-2022-DER_PV-0001 |
| BP-B-000866-2022-exte… | B-000866 | extension | extension | 134 | 44 | 1 | 2 | {"floor_area_m2": "ch… | WP5 ten-year life cou… | LE-2022-EXTENSION-0001 |
| BP-B-000867-2022-der_… | B-000867 | asset added | der_smart_controls | 147 | 57 | 1 | 2 | {"heating_control": "… | WP5 ten-year life cou… | LE-2022-DER_SMART_CON… |

**Joins**

- **Masked view:** this dataset is ground truth with an observable view — redacted: the event occurred and its date, without the parameters
- Declared observable view: `D03_redacted`
- `building_id` → D02 fabric, D03 passport, D16 state, D01 geography

**Validation**

No check in the artefacts names this dataset, and no module opens it by name. That is a statement about the evidence on disk, not a claim that the dataset is unchecked.

Links are attributed from the artefacts themselves — a check is listed where its own record names the dataset — rather than from a mapping kept in the generator, which would go stale.

<div style="page-break-after: always;"></div>

<a id="d04"></a>

## D04 · Appliances, heating, PV, BESS, chargers, vehicles, with owner and lifetime

Appliances, heating plant, PV, batteries, chargers and vehicles, each with an owner and a lifetime. It is where a device comes from and when it stops existing.

**Key points**

- One row is one asset at one version, owned by a household or a building.
- Lifetimes are dated, so an asset installed mid-run is absent before its date and present after it.
- The appliance rows are what the cycle generator draws from, and they key into the signature library in D22.
- Ground truth. Observable traces of these assets appear in D18, D19 and the recorded metadata in D30.

**Facts**

| | |
|---|---|
| Class | GT — Ground truth. Never given to a model under test. |
| Package | Ground truth |
| Path | not present in `v1/` |
| Format | declared `parquet` |
| Partitioning | none declared |
| Rows | — |
| Size | — |
| Time span | — |
| Resolution | asset x version |
| Primary key | grain `asset x version` |
| Status | **missing** |

**Schema** — not available: the dataset is not on disk in `v1/`. It is **missing**.

The declared schema has 20 fields: `asset_id`, `version`, `valid_from`, `valid_to`, `building_id`, `owner_person_id`, `asset_class`, `asset_type`, `make_model_synth`, `rated_power_w`, `capacity`, `efficiency`, `install_date`, `age_years_at_t0`, `failure_hazard_scale`, `signature_id`, `device_mode`, `pv_azimuth_deg`, `pv_tilt_deg`, `seed`.

**Sample** — none: no rows on disk in `v1/`.

**Joins**

- No join keys present on disk for this dataset.

**Validation**

No check in the artefacts names this dataset, and no module opens it by name. That is a statement about the evidence on disk, not a claim that the dataset is unchecked.

Links are attributed from the artefacts themselves — a check is listed where its own record names the dataset — rather than from a mapping kept in the generator, which would go stale.

<div style="page-break-after: always;"></div>

<a id="d05"></a>

## D05 · HRSD_Occupants: persistent characteristics and trait vector

The persons dataset, HRSD_Occupants proper: each resident's persistent characteristics and trait vector. It is the population the whole simulation is about.

**Key points**

- One row is one person, with the attributes that do not change and the latent traits that drive behaviour.
- Synthesised to match the published small-area marginals for Cobh, with the age by economic-status joint conditioned on a county-level source.
- Traits are latent by construction: no observable dataset carries them, and the MIMIC answer key in D26 is the only place they are crosswalked.
- Ground truth, and the most sensitive in the release: a model given D05 has been given the answer to every inference task in the privacy threat model.
- Must never reach a model under test, and must not be joined to D25 outside the scoring service.

**Facts**

| | |
|---|---|
| Class | GT — Ground truth. Never given to a model under test. |
| Package | Ground truth |
| Path | not present in `v1/` |
| Format | declared `parquet` |
| Partitioning | none declared |
| Rows | — |
| Size | — |
| Time span | — |
| Resolution | person |
| Primary key | grain `person` |
| Status | **missing** |

**Schema** — not available: the dataset is not on disk in `v1/`. It is **missing**.

The declared schema has 41 fields: `person_id`, `given_name`, `family_name`, `birth_date`, `death_date`, `sex`, `country_of_birth`, `nationality`, `ethnicity_census`, `first_language`, `other_languages`, `years_in_ireland`, `education_level`, `trans`, `community`, `env`, `autonomy`, `comfort`, `conditional`, `privacy`, `instTrust`, `idvZ`, `satisficer`, `stated_gap`, `lambda_self`, `lambda_coop`, `lambda_altru`, `big5_o`, `big5_c`, `big5_e`, `big5_a`, `big5_n`, `chronotype`, `habit_strength`, `lapse_rate`, `attention`, `response_propensity`, `mcv_latent`, `synthetic`, `seed`, `pool`.

**Sample** — none: no rows on disk in `v1/`.

**Joins**

- No join keys present on disk for this dataset.

**Validation**

No check in the artefacts names this dataset, and no module opens it by name. That is a statement about the evidence on disk, not a claim that the dataset is unchecked.

Links are attributed from the artefacts themselves — a check is listed where its own record names the dataset — rather than from a mapping kept in the generator, which would go stale.

<div style="page-break-after: always;"></div>

<a id="d06"></a>

## D06 · Who lives where, from when to when

Household membership over time: who lives where, from when to when. Every household-level quantity in the release is only well defined against this dataset.

**Key points**

- One row is one person's residence in one household over one interval.
- Opened and closed by the move, birth, death and separation events in D09.
- An interval-valued dataset, so a household's size on a given day is a query rather than a column.
- Ground truth: occupancy is the quantity the privacy threat model treats as the thing an attacker wants.

**Facts**

| | |
|---|---|
| Class | GT — Ground truth. Never given to a model under test. |
| Package | Ground truth |
| Path | not present in `v1/` |
| Format | declared `parquet` |
| Partitioning | none declared |
| Rows | — |
| Size | — |
| Time span | — |
| Resolution | interval |
| Primary key | grain `interval` |
| Status | **missing** |

**Schema** — not available: the dataset is not on disk in `v1/`. It is **missing**.

The declared schema has 9 fields: `membership_id`, `person_id`, `household_id`, `building_id`, `valid_from`, `valid_to`, `role`, `reason_in`, `reason_out`.

**Sample** — none: no rows on disk in `v1/`.

**Joins**

- No join keys present on disk for this dataset.

**Validation**

No check in the artefacts names this dataset, and no module opens it by name. That is a statement about the evidence on disk, not a claim that the dataset is unchecked.

Links are attributed from the artefacts themselves — a check is listed where its own record names the dataset — rather than from a mapping kept in the generator, which would go stale.

<div style="page-break-after: always;"></div>

<a id="d07"></a>

## D07 · Kin, partner, carer, friend, co-worker edges

The relationship graph: kin, partner, carer, friend and co-worker edges between people, valid over intervals. It is what makes a household a household rather than a set of people in a building.

**Key points**

- One row is one directed or undirected edge over one interval.
- Partnering and separation events in D09 create and end the partner edges; caring load follows the carer edges.
- Edges are what joint activity planning reads when it decides that two people do something together.
- Ground truth, and re-identifying in combination: a graph of this kind is distinctive even without attributes.

**Facts**

| | |
|---|---|
| Class | GT — Ground truth. Never given to a model under test. |
| Package | Ground truth |
| Path | not present in `v1/` |
| Format | declared `parquet` |
| Partitioning | none declared |
| Rows | — |
| Size | — |
| Time span | — |
| Resolution | edge x interval |
| Primary key | grain `edge x interval` |
| Status | **missing** |

**Schema** — not available: the dataset is not on disk in `v1/`. It is **missing**.

The declared schema has 7 fields: `edge_id`, `person_a`, `person_b`, `edge_type`, `valid_from`, `valid_to`, `strength`.

**Sample** — none: no rows on disk in `v1/`.

**Joins**

- No join keys present on disk for this dataset.

**Validation**

No check in the artefacts names this dataset, and no module opens it by name. That is a statement about the evidence on disk, not a claim that the dataset is unchecked.

Links are attributed from the artefacts themselves — a check is listed where its own record names the dataset — rather than from a mapping kept in the generator, which would go stale.

<div style="page-break-after: always;"></div>

<a id="d08"></a>

## D08 · Evolving states, slowly changing (SCD-2)

Person states that evolve slowly — employment, health, caring load, work pattern — recorded as slowly changing dimensions so that every state has a from and a to.

**Key points**

- One row is one person's state over one interval, closed when the state changes.
- Transitions are driven by the dated hazards in the life-course module and appear as events in D09.
- Distinguishes the persistent layer in D05 from the evolving layer here, which is what lets a biography be reconstructed.
- Ground truth: health state in particular is a special category of personal data in the real world and is treated as the most sensitive field in the synthetic one.

**Facts**

| | |
|---|---|
| Class | GT — Ground truth. Never given to a model under test. |
| Package | Ground truth |
| Path | not present in `v1/` |
| Format | declared `parquet` |
| Partitioning | none declared |
| Rows | — |
| Size | — |
| Time span | — |
| Resolution | interval |
| Primary key | grain `interval` |
| Status | **missing** |

**Schema** — not available: the dataset is not on disk in `v1/`. It is **missing**.

The declared schema has 21 fields: `state_id`, `person_id`, `valid_from`, `valid_to`, `household_id`, `role`, `econ_status`, `occupation_soc`, `occupation_isco08`, `industry_nace`, `workplace_venue_id`, `work_pattern`, `remote_share`, `school_venue_id`, `school_year`, `health_state`, `caring_load`, `caring_hours_week`, `decision_authority`, `vehicle_access`, `income_quintile`.

**Sample** — none: no rows on disk in `v1/`.

**Joins**

- No join keys present on disk for this dataset.

**Validation**

No check in the artefacts names this dataset, and no module opens it by name. That is a statement about the evidence on disk, not a claim that the dataset is unchecked.

Links are attributed from the artefacts themselves — a check is listed where its own record names the dataset — rather than from a mapping kept in the generator, which would go stale.

<div style="page-break-after: always;"></div>

<a id="d09"></a>

## D09 · Births, deaths, moves, jobs, health states, decisions

Life events: births, deaths, moves, job changes, health-state onsets and household decisions, each with its date and the people it involves. It is the spine of the life-course model and the reason the town changes over a decade.

**Key points**

- One row is one event, dated, typed, and tied to the person or household it happened to.
- Every event type is driven by a hazard that is either taken from an Irish published rate or flagged as an assumption with a search record.
- Events are what open and close the intervals in D06 and D08, so this dataset and those two must reconcile exactly.
- Ground truth. The observable consequence of an event is a change in the load, which is what a detector is asked to find.
- Must not be used as a feature by a model whose task is to detect the events it records.

**Facts**

| | |
|---|---|
| Class | GT — Ground truth. Never given to a model under test. |
| Package | Ground truth |
| Path | `v1/evidence/wp5_tenyear.json` |
| Format | declared `parquet` |
| Partitioning | none declared |
| Rows | 250 (in an evidence artefact) |
| Size | — |
| Time span | `effective_day` 17 → 3625 (day index from the run's first day, not a date) |
| Resolution | event |
| Primary key | grain `event` |
| Status | **partial** |

**Schema** — not available: the dataset is not on disk in `v1/`. It is **partial**.

Rows exist outside the released packages:

| Artefact | Key | Rows | Columns |
|---|---|---|---|
| `v1/evidence/wp5_tenyear.json` | `d09_life_events` | 250 | building_id, cause, decided_day, effective_day, event_id, event_type,… |

The declared schema has 9 fields: `event_id`, `event_type`, `effective_at`, `decided_at`, `persons`, `household_id`, `building_id`, `cause`, `observable_effects`.

**Sample** — five rows as they are held in `v1/evidence/wp5_tenyear.json`. The dataset has no released Parquet part, so these are the rows there are.

| `event_id` | `event_type` | `effective_day` | `decided_day` | `persons` | `household_id` | `building_id` | `cause` | `observable_effects` |
|---|---|---|---|---|---|---|---|---|
| LE-2022-DEATH-0001 | death | 359 | — | ["P-002747"] | H-001012 | B-001012 | mortality hazard, age… | {"occupancy": "one fe… |
| LE-2022-DEATH-0002 | death | 223 | — | ["P-002749"] | H-001013 | B-001013 | mortality hazard, age… | {"occupancy": "one fe… |
| LE-2022-DEATH-0003 | death | 122 | — | ["P-002760"] | H-001023 | B-001023 | mortality hazard, age… | {"occupancy": "one fe… |
| LE-2022-BIRTH-0001 | birth | 241 | — | ["P-WP5-00001"] | H-000867 | B-000867 | age-specific fertilit… | {"occupancy": "one mo… |
| LE-2022-PARTNERING-00… | partnering | 52 | — | ["P-002301", "P-WP5-0… | H-000850 | B-000850 | union formation, age … | {"occupancy": "one mo… |

**Joins**

- `building_id` → D02 fabric, D03 passport, D16 state, D01 geography
- `household_id` → D06 membership, D04 assets

**Validation**

No check in the artefacts names this dataset, and no module opens it by name. That is a statement about the evidence on disk, not a claim that the dataset is unchecked.

Links are attributed from the artefacts themselves — a check is listed where its own record names the dataset — rather than from a mapping kept in the generator, which would go stale.

<div style="page-break-after: always;"></div>

<a id="d10"></a>

## D10 · Person activity intervals with location and co-participants

Activity intervals: what each person is doing, where, and with whom. Appliance use, presence and the heating demand all follow from it, so it is the layer where behaviour becomes energy.

**Key points**

- One row is one person doing one thing over one interval.
- Timings are driven by time-use participation curves and are not adjusted to match any load profile.
- Carries co-participants, so a joint activity is recoverable rather than inferred from coincidence.
- Partitioned by year and month in its declared storage, because a town-decade of activity intervals is too large for one file.
- Ground truth: an activity label is the thing a non-intrusive load-monitoring model is trying to produce.

**Facts**

| | |
|---|---|
| Class | GT — Ground truth. Never given to a model under test. |
| Package | Ground truth |
| Path | not present in `v1/` |
| Format | declared `parquet` |
| Partitioning | by year, month |
| Rows | — |
| Size | — |
| Time span | — |
| Resolution | interval |
| Primary key | grain `interval` |
| Status | **missing** |

**Schema** — not available: the dataset is not on disk in `v1/`. It is **missing**.

The declared schema has 11 fields: `activity_id`, `person_id`, `start`, `end`, `activity_code`, `hetus_code`, `location_id`, `zone`, `joint_with`, `trigger`, `deliberated`.

**Sample** — none: no rows on disk in `v1/`.

**Joins**

- No join keys present on disk for this dataset.

**Validation**

No check in the artefacts names this dataset, and no module opens it by name. That is a statement about the evidence on disk, not a claim that the dataset is unchecked.

Links are attributed from the artefacts themselves — a check is listed where its own record names the dataset — rather than from a mapping kept in the generator, which would go stale.

<div style="page-break-after: always;"></div>

<a id="d11"></a>

## D11 · Person location intervals - the no-double-occupancy source

Presence: where each person is over each interval, at home or away and at which venue. It is the source the no-double-occupancy invariant is checked against.

**Key points**

- One row is one person in one place over one interval.
- Derived from the activity intervals, with outdoor-but-at-home activities recorded at the person's own building rather than at a venue.
- Collected for the opening days of a run rather than the whole year: a year of minute-resolution presence for the estate is tens of millions of rows and no check reads them.
- Ground truth, and the direct target of the occupancy-inference attack measured in the privacy artefact.
- Must not appear, in any aggregated form, in a dataset sent to a device or an evaluator.

**Facts**

| | |
|---|---|
| Class | GT — Ground truth. Never given to a model under test. |
| Package | Ground truth |
| Path | `v1/ground_truth/D11_part*.parquet` (1 part) |
| Format | declared `parquet` ; on disk Parquet |
| Partitioning | by year, month ; on disk 1 sequential parts |
| Rows | 54,301 |
| Size | 490.6 kB |
| Time span | — |
| Resolution | not a time series |
| Primary key | grain `interval` ; id columns on disk: `presence_id`, `person_id`, `location_id` |
| Status | **present** |
| Leakage audit | — |
| Part hash | `896045b64c2e59e1…` (part 0) |

**Schema** — types, null counts and ranges from the Parquet footers; descriptions and units from `schema/datasets.yaml`.

| Column | Type | Unit | Nulls | Min | Max | Declared |
|---|---|---|---|---|---|---|
| `presence_id` | string | — | no nulls | PR-00000-000000 | PR-00013-003351 | required |
| `person_id` | string | — | no nulls | P-000625 | P-000795 | required |
| `start` | timestamp[ns, tz=UTC] | — | no nulls | 2022-01-01 00:00:00+00:00 | 2022-01-14 23:58:00+00:00 | required |
| `end` | timestamp[ns, tz=UTC] | — | no nulls | 2022-01-01 06:51:00+00:00 | 2022-01-14 23:59:00+00:00 | required |
| `location_kind` | string | — | no nulls | building | venue | required |
| `location_id` | string | — | 12,987 null (23.9%) | B-000206 | B-000262 | optional |
| `zone` | string | — | no nulls | bathroom | utility | required |

<details><summary>Column descriptions, as declared</summary>

| Column | Declared description |
|---|---|
| `location_kind` | building \| venue \| in_transit \| out_of_model |

</details>

**Sample** — the first five rows of part 0, as written. Identity-bearing columns would be withheld; this dataset carries none.

| `presence_id` | `person_id` | `start` | `end` | `location_kind` | `location_id` | `zone` |
|---|---|---|---|---|---|---|
| PR-00000-000000 | P-000625 | 2022-01-01 00:00:00+00:… | 2022-01-01 07:45:00+00:… | building | B-000206 | bedroom |
| PR-00000-000001 | P-000625 | 2022-01-01 07:45:00+00:… | 2022-01-01 08:02:00+00:… | building | B-000206 | bathroom |
| PR-00000-000002 | P-000625 | 2022-01-01 08:02:00+00:… | 2022-01-01 08:12:00+00:… | building | B-000206 | bathroom |
| PR-00000-000003 | P-000625 | 2022-01-01 08:12:00+00:… | 2022-01-01 08:20:00+00:… | building | B-000206 | bedroom |
| PR-00000-000004 | P-000625 | 2022-01-01 08:20:00+00:… | 2022-01-01 08:45:00+00:… | building | B-000206 | living |

**Joins**

- `person_id` → D05 persons, D08 states, D09 events, D10 activities

**Validation**

V0 invariants naming this dataset, from `v1/evidence/v0_invariants.json`:

| Invariant | Checked | Violations | Status |
|---|---|---|---|
| no_child_alone | 0 | 0 | **SKIPPED** |

Links are attributed from the artefacts themselves — a check is listed where its own record names the dataset — rather than from a mapping kept in the generator, which would go stale.

<div style="page-break-after: always;"></div>

<a id="d12"></a>

## D12 · Origin, destination, mode, vehicle, distance

Trips: origin, destination, mode, vehicle and distance. It connects the activity layer to the vehicle layer, and it is what makes an electric vehicle's state of charge a consequence of someone's day rather than a schedule.

**Key points**

- One row is one trip by one person.
- Generated from the activity sequence, so a trip exists only where an activity requires someone to be somewhere else.
- Drives vehicle energy use, including the cold-weather consumption penalty.
- Ground truth: trip patterns are among the most re-identifying data about a person that exists.

**Facts**

| | |
|---|---|
| Class | GT — Ground truth. Never given to a model under test. |
| Package | Ground truth |
| Path | not present in `v1/` |
| Format | declared `parquet` |
| Partitioning | none declared |
| Rows | — |
| Size | — |
| Time span | — |
| Resolution | event |
| Primary key | grain `event` |
| Status | **missing** |

**Schema** — not available: the dataset is not on disk in `v1/`. It is **missing**.

The declared schema has 10 fields: `trip_id`, `person_id`, `start`, `end`, `origin_id`, `destination_id`, `mode`, `vehicle_asset_id`, `distance_km`, `purpose`.

**Sample** — none: no rows on disk in `v1/`.

**Joins**

- No join keys present on disk for this dataset.

**Validation**

No check in the artefacts names this dataset, and no module opens it by name. That is a statement about the evidence on disk, not a claim that the dataset is unchecked.

Links are attributed from the artefacts themselves — a check is listed where its own record names the dataset — rather than from a mapping kept in the generator, which would go stale.

<div style="page-break-after: always;"></div>

<a id="d13"></a>

## D13 · Cycle start/end, programme, signature ID, energy

Appliance cycles: when each appliance ran, on which programme, with which signature and how much energy it used. It is the answer key for load disaggregation.

**Key points**

- One row is one cycle of one appliance.
- Cycles are placed by the activity that calls for them, not by a diary, so a wash follows someone deciding to do laundry.
- Carries the signature identifier, which keys into the signature library in D22 and makes the waveform reproducible.
- Ground truth. The observable counterpart is the aggregate in D18 and D19, which is what a disaggregation model is given.
- Must not be joined to D18 by a model under test: that is the label it is being asked to predict.

**Facts**

| | |
|---|---|
| Class | GT — Ground truth. Never given to a model under test. |
| Package | Ground truth |
| Path | `v1/ground_truth/D13_part*.parquet` (13 parts) |
| Format | declared `parquet` ; on disk Parquet |
| Partitioning | by year, month ; on disk 13 sequential parts |
| Rows | 1,449,871 |
| Size | 34.7 MB |
| Time span | — |
| Resolution | not a time series |
| Primary key | grain `event` ; id columns on disk: `cycle_id`, `asset_id`, `building_id`, `signature_id`, `caused_by_activity_id` |
| Status | **present** |
| Leakage audit | — |
| Part hash | `f6ea60b5c322d8df…` (part 0) |

**Schema** — types, null counts and ranges from the Parquet footers; descriptions and units from `schema/datasets.yaml`.

| Column | Type | Unit | Nulls | Min | Max | Declared |
|---|---|---|---|---|---|---|
| `cycle_id` | string | — | no nulls | C-B-000206-00000-0001 | C-B-000262-00364-0079 | required |
| `asset_id` | string | — | no nulls | A-000206-00 | A-000262-13 | required |
| `building_id` | string | — | no nulls | B-000206 | B-000262 | required |
| `start` | timestamp[ns, tz=UTC] | — | no nulls | 2022-01-01 00:00:00+00:00 | 2022-12-31 23:50:00+00:00 | required |
| `end` | timestamp[ns, tz=UTC] | — | no nulls | 2022-01-01 00:21:00+00:00 | 2022-12-31 23:59:00+00:00 | required |
| `programme` | string | — | no nulls | 1.5 L | viewing | required |
| `signature_id` | string | — | no nulls | SIG-DISH-ECO | SIG-WASH-ECO40 | required |
| `signature_seed` | int64 | — | no nulls | 1947924508179 | 4611686008817472700 | required |
| `energy_wh` | double | Wh *(derived)* | no nulls | 9.1688438954015 | 5841.585988688332 | required |
| `peak_w` | double | W *(derived)* | no nulls | 60.0 | 8500.0 | required |
| `caused_by_activity_id` | string | — | 1,449,871 null (100.0%) | — | — | optional |
| `flexible` | bool | — | no nulls | False | True | required |
| `shifted_by_min` | int64 | — | no nulls | 0 | 0 | required |

<details><summary>Column descriptions, as declared</summary>

| Column | Declared description |
|---|---|
| `start` | 1 s precision |
| `programme` | eco 40, kettle 1.5 L, ... |
| `signature_seed` | drives 1 Hz rendering |
| `caused_by_activity_id` | causal link back to D10 |

</details>

**Sample** — the first five rows of part 0, as written. Identity-bearing columns would be withheld; this dataset carries none.

| `cycle_id` | `asset_id` | `building_id` | `start` | `end` | `programme` | `signature_id` | `signature_seed` | `energy_wh` | `peak_w` | `caused_by_activity_id` | `flexible` | `shifted_by_min` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C-B-000206-00000-0001 | A-000206-05 | B-000206 | 2022-01-01 13:42:00+00:… | 2022-01-01 13:44:00+00:… | 1.5 L | SIG-KETTLE | 979036346254456657 | 134.67604876820425 | 2800.0 | — | False | 0 |
| C-B-000206-00000-0002 | A-000206-05 | B-000206 | 2022-01-01 13:04:00+00:… | 2022-01-01 13:06:00+00:… | 1.5 L | SIG-KETTLE | 1819667861632278596 | 127.6290462163796 | 2800.0 | — | False | 0 |
| C-B-000206-00000-0003 | A-000206-04 | B-000206 | 2022-01-01 12:03:00+00:… | 2022-01-01 12:22:00+00:… | medium ring | SIG-HOB | 2247463029891054313 | 281.2569861852443 | 1800.0 | — | False | 0 |
| C-B-000206-00000-0004 | A-000206-05 | B-000206 | 2022-01-01 12:04:00+00:… | 2022-01-01 12:06:00+00:… | 1.5 L | SIG-KETTLE | 1288140347136538612 | 116.6670422468746 | 2800.0 | — | False | 0 |
| C-B-000206-00000-0005 | A-000206-04 | B-000206 | 2022-01-01 14:37:00+00:… | 2022-01-01 14:54:00+00:… | medium ring | SIG-HOB | 1375022473878156104 | 261.39215167431394 | 1800.0 | — | False | 0 |

**Joins**

- `building_id` → D02 fabric, D03 passport, D16 state, D01 geography
- `signature_id` → D22 signature library

**Validation**

No check in the artefacts names this dataset, and no module opens it by name. That is a statement about the evidence on disk, not a claim that the dataset is unchecked.

Links are attributed from the artefacts themselves — a check is listed where its own record names the dataset — rather than from a mapping kept in the generator, which would go stale.

<div style="page-break-after: always;"></div>

<a id="d14"></a>

## D14 · Event instances, phases, footprint, attendance

Calendar events: holidays, school terms, storms, outages and the rest, each with its phases, footprint and attendance. It is the shared context that makes many households change behaviour on the same day.

**Key points**

- One row is one instance of one event kind, with its phase and spatial footprint.
- Every declared kind must occur in a full year, and each one has a source or a registered assumption; the event coverage audit checks both.
- Footprint matters: a storm is town-wide, a school term applies to households with children, an outage is a feeder.
- Ground truth as the event list, though the fact of a storm or a bank holiday is also in the external series in D31.

**Facts**

| | |
|---|---|
| Class | GT — Ground truth. Never given to a model under test. |
| Package | Ground truth |
| Path | not present in `v1/` |
| Format | declared `parquet` |
| Partitioning | none declared |
| Rows | — |
| Size | — |
| Time span | — |
| Resolution | event |
| Primary key | grain `event` |
| Status | **missing** |

**Schema** — not available: the dataset is not on disk in `v1/`. It is **missing**.

The declared schema has 11 fields: `instance_id`, `event_kind`, `event_class`, `phase`, `start`, `end`, `footprint`, `footprint_ids`, `attendance_prob`, `shared_driver`, `source_ref`.

**Sample** — none: no rows on disk in `v1/`.

**Joins**

- No join keys present on disk for this dataset.

**Validation**

No check in the artefacts names this dataset, and no module opens it by name. That is a statement about the evidence on disk, not a claim that the dataset is unchecked.

Links are attributed from the artefacts themselves — a check is listed where its own record names the dataset — rather than from a mapping kept in the generator, which would go stale.

<div style="page-break-after: always;"></div>

<a id="d15"></a>

## D15 · True site weather and solar geometry driving physics and behaviour

The true site weather and solar geometry that drives the physics: temperature, irradiance, wind, humidity and rain at minute resolution. It is what the building actually experienced.

**Key points**

- One row is one minute of site weather.
- Downscaled from the published station records for the two stations nearest the town.
- Ground truth, and distinct from D31: the observable station weather has outages, gap-fills and the station's own location.
- A model given D15 has been given a weather input no real operator has, which is why the observable series is a separate dataset rather than a flag on this one.

**Facts**

| | |
|---|---|
| Class | GT — Ground truth. Never given to a model under test. |
| Package | Ground truth |
| Path | not present in `v1/` |
| Format | declared `parquet` |
| Partitioning | none declared |
| Rows | — |
| Size | — |
| Time span | — |
| Resolution | 1 min |
| Primary key | grain `1 min` |
| Status | **missing** |

**Schema** — not available: the dataset is not on disk in `v1/`. It is **missing**.

The declared schema has 16 fields: `ts`, `site_id`, `temp_air_c`, `rh_pct`, `wind_speed_ms`, `wind_dir_deg`, `ghi_w_m2`, `dni_w_m2`, `dhi_w_m2`, `solar_zenith_deg`, `solar_azimuth_deg`, `sunrise_utc`, `sunset_utc`, `is_dst`, `precip_mm`, `realisation_id`.

**Sample** — none: no rows on disk in `v1/`.

**Joins**

- No join keys present on disk for this dataset.

**Validation**

No check in the artefacts names this dataset, and no module opens it by name. That is a statement about the evidence on disk, not a claim that the dataset is unchecked.

Links are attributed from the artefacts themselves — a check is listed where its own record names the dataset — rather than from a mapping kept in the generator, which would go stale.

<div style="page-break-after: always;"></div>

<a id="d16"></a>

## D16 · Zone temps, RH, CO2, DHW, heat delivered

Building state at minute resolution: zone temperatures, relative humidity, CO₂, the hot water cylinder and the heat delivered. It is the physics model's own output and the state that carries across the day boundary.

**Key points**

- One row is one building at one minute.
- Checkpointed daily, so any single day can be restored and re-simulated; the replay test compares exactly this dataset against a restored re-run.
- Holds the cylinder temperature as well as the fabric temperatures, because both carry overnight and a restore that forgot either would diverge by morning.
- Ground truth: indoor temperature is what a thermal-model estimator is trying to infer from the load.
- Comfort claims must not be read from it as though it were measured — it is the model's own state, not an observation.

**Facts**

| | |
|---|---|
| Class | GT — Ground truth. Never given to a model under test. |
| Package | Ground truth |
| Path | `v1/ground_truth/D16_part*.parquet` (13 parts) |
| Format | declared `re-run on demand (U07 option b, decision D-009); hot slices cached` ; on disk Parquet |
| Partitioning | none declared ; on disk 13 sequential parts |
| Rows | 1,752,000 |
| Size | 122.8 MB |
| Time span | `ts` 2022-01-01 00:00:00+00:00 → 2022-12-31 23:45:00+00:00 |
| Resolution | 15 min between rows for one building (derived from a sample) |
| Primary key | grain `1 min, checkpointed daily` ; id columns on disk: `ts`, `building_id` |
| Status | **present** |
| Leakage audit | — |
| Part hash | `a684f72cd869c9a6…` (part 0) |

**Schema** — types, null counts and ranges from the Parquet footers; descriptions and units from `schema/datasets.yaml`.

| Column | Type | Unit | Nulls | Min | Max | Declared |
|---|---|---|---|---|---|---|
| `ts` | timestamp[ns, tz=UTC] | — | no nulls | 2022-01-01 00:00:00+00:00 | 2022-12-31 23:45:00+00:00 | required |
| `building_id` | string | — | no nulls | B-000206 | B-000262 | required |
| `temp_living_c` | double | degC *(derived)* | no nulls | 6.038787421434929 | 35.37407544486939 | required |
| `temp_sleep_c` | double | degC *(derived)* | no nulls | 5.944296966123854 | 27.85155574921111 | required |
| `temp_env_c` | double | degC *(derived)* | no nulls | 5.781774151127792 | 27.052169987632997 | required |
| `rh_living_pct` | double | percent *(derived)* | no nulls | 55.0 | 55.0 | required |
| `co2_living_ppm` | double | ppm *(derived)* | no nulls | 420.0 | 2866.3129464952913 | required |
| `co2_sleep_ppm` | double | ppm *(derived)* | no nulls | 420.00000000000074 | 4077.3711353419344 | required |
| `dhw_tank_c` | double | degC *(derived)* | no nulls | 39.16908704474034 | 70.0 | optional |
| `heat_delivered_w` | double | W *(derived)* | no nulls | -0.0 | 9222.492883727185 | required |
| `internal_gain_w` | double | W *(derived)* | no nulls | -0.0 | 21217.167043966605 | required |
| `solar_gain_w` | double | W *(derived)* | no nulls | -0.0 | 5580.425157587506 | required |
| `ach_effective` | double | — | no nulls | 0.2732384435504024 | 3.4598486002541113 | required |
| `occupants_living` | int64 | — | no nulls | 0 | 6 | required |
| `occupants_sleep` | int64 | — | no nulls | 0 | 6 | required |

<details><summary>Column descriptions, as declared</summary>

| Column | Declared description |
|---|---|
| `ach_effective` | includes behavioural window opening |

</details>

**Sample** — the first five rows of part 0, as written. Identity-bearing columns would be withheld; this dataset carries none.

| `ts` | `building_id` | `temp_living_c` | `temp_sleep_c` | `temp_env_c` | `rh_living_pct` | `co2_living_ppm` | `co2_sleep_ppm` | `dhw_tank_c` | `heat_delivered_w` | `internal_gain_w` | `solar_gain_w` | `ach_effective` | `occupants_living` | `occupants_sleep` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2022-01-01 00:00:00+00:… | B-000206 | 18.054831557936602 | 17.399542226169576 | 12.753590227773453 | 55.0 | 420.0 | 559.7629010437519 | 58.361493396589374 | 0.0 | 193.68244664420402 | 0.0 | 0.37348676662556274 | 0 | 6 |
| 2022-01-01 00:15:00+00:… | B-000206 | 17.443231582377067 | 16.700821828943315 | 12.880471715350028 | 55.0 | 420.0 | 805.5592745308726 | 58.28081931084441 | 0.0 | 119.86312029847802 | 0.0 | 0.37348676662556274 | 0 | 6 |
| 2022-01-01 00:30:00+00:… | B-000206 | 16.922135527512427 | 16.167620546788495 | 12.987575311014108 | 55.0 | 420.0 | 1029.3787761564993 | 58.199181952182 | 0.0 | 201.00959943308348 | 0.0 | 0.37348676662556274 | 0 | 6 |
| 2022-01-01 00:45:00+00:… | B-000206 | 16.472362644017352 | 15.761194990718508 | 13.078753616273229 | 55.0 | 420.0 | 1233.1863775349993 | 58.116758106253315 | 0.0 | 94.6453729391042 | 0.0 | 0.37348676662556274 | 0 | 6 |
| 2022-01-01 01:00:00+00:… | B-000206 | 16.087321511334075 | 15.451339741976078 | 13.15678339619993 | 55.0 | 420.0 | 1418.771360425076 | 58.03366565821446 | 0.0 | 194.99852919665426 | 0.0 | 0.37348676662556274 | 0 | 6 |

**Joins**

- `building_id` → D02 fabric, D03 passport, D16 state, D01 geography

**Validation**

Opened directly by: `scripts/baile_nua/plausibility/checks.py:374`.

Links are attributed from the artefacts themselves — a check is listed where its own record names the dataset — rather than from a mapping kept in the generator, which would go stale.

<div style="page-break-after: always;"></div>

<a id="d17"></a>

## D17 · Feeder and transformer loading, voltages, outages

Network state: feeder and transformer loading, voltages and outages at minute resolution, from the quasi-static power flow. It is the electrical consequence of everything the households do.

**Key points**

- One row is one network element at one minute.
- Produced by solving the network at the coupling epoch, so it exists only for runs in the coupled mode.
- Has an aggregate observable view — feeder and transformer totals rather than per element — because per-element state would hand a model the answer to the state-estimation task.
- The voltages are not a validated claim: the topology is an assumption, and the module refuses to let them be quoted as one.
- Ground truth per element; the aggregate view is the released form.

**Facts**

| | |
|---|---|
| Class | GT — Ground truth. Never given to a model under test. |
| Package | Ground truth (+ observable view) |
| Path | not present in `v1/` |
| Format | declared `parquet` |
| Partitioning | none declared |
| Rows | — |
| Size | — |
| Time span | — |
| Resolution | 1 min |
| Primary key | grain `1 min` |
| Status | **missing** |

**Schema** — not available: the dataset is not on disk in `v1/`. It is **missing**.

The declared schema has 10 fields: `ts`, `element_id`, `element_kind`, `p_kw`, `q_kvar`, `voltage_pu`, `loading_pct`, `outage`, `coupling_mode`, `epoch_staleness_s`.

**Sample** — none: no rows on disk in `v1/`.

**Joins**

- **Masked view:** this dataset is ground truth with an observable view — aggregate: feeder and transformer totals, not per element
- Declared observable view: `D17_aggregate`

**Validation**

No check in the artefacts names this dataset, and no module opens it by name. That is a statement about the evidence on disk, not a claim that the dataset is unchecked.

Links are attributed from the artefacts themselves — a check is listed where its own record names the dataset — rather than from a mapping kept in the generator, which would go stale.

<div style="page-break-after: always;"></div>

<a id="d18"></a>

## D18 · Rendered device readings with noise and gaps

Observations: the rendered device readings, with the noise, quantisation, clock error and gaps that real meters and sensors produce. This is what a sensor would have seen, and it is the principal observable dataset.

**Key points**

- One row is one reading from one channel at one device-native timestamp.
- Rendered from the ground-truth series through a declared error model per channel, with a provenance code and a quality flag on every value.
- Carries a sensor tier per premises, so a home with a cheap meter and a home with a research-grade one are different in the data rather than in a footnote.
- Observable: this is the dataset a model under test is given.
- It is the largest dataset in the release by a wide margin, which is why the ten-year slice omits it.

**Facts**

| | |
|---|---|
| Class | OBS — Observable. What a device, respondent, assessor or operator would see. |
| Package | Observable |
| Path | `v1/observable/D18_part*.parquet` (13 parts) |
| Format | declared `rendered on demand; cached slices` ; on disk Parquet |
| Partitioning | none declared ; on disk 13 sequential parts |
| Rows | 66,097,553 |
| Size | 506.4 MB |
| Time span | `ts` 2022-01-01 00:00:00+00:00 → 2023-01-01 00:00:10.678580951+00:00 |
| Resolution | 1 min between rows for one premises (derived from a sample) |
| Primary key | declared `keyed_by: premises` ; id columns on disk: `device_id`, `premises_id`, `ts` |
| Status | **present** |
| Leakage audit | passed: no GT-class or forbidden field names present |
| Part hash | `e1ca358d167f11e3…` (part 0) |

**Schema** — types, null counts and ranges from the Parquet footers; descriptions and units from `schema/datasets.yaml`.

| Column | Type | Unit | Nulls | Min | Max | Declared |
|---|---|---|---|---|---|---|
| `device_id` | string | — | no nulls | DEV-MPRN-00B4DDA0621CC6AC… | DEV-MPRN-FECC1C4894CC3DF0… | required |
| `premises_id` | string | — | no nulls | MPRN-00B4DDA0621CC6AC64 | MPRN-FECC1C4894CC3DF0C3 | required |
| `channel` | string | — | no nulls | charger_w | temp | required |
| `ts` | timestamp[ns, tz=UTC] | — | no nulls | 2022-01-01 00:00:00+00:00 | 2023-01-01 00:00:10.67858… | required |
| `value` | double | — | no nulls | -40.0 | 307375.0 | optional |
| `quality` | string | — | no nulls | drift | ok | required |
| `tier` | string | — | no nulls | T1 | T4 | required |
| `provenance` | string | — | no nulls | metered | metered | required |
| `unit` | string | — | no nulls | W | ppm | required |

<details><summary>Column descriptions, as declared</summary>

| Column | Declared description |
|---|---|
| `device_id` | the device's own identifier as the data-collection platform records it |
| `premises_id` | the meter point the device is registered against (6.4 item 2: keyed by premises, not household) |
| `channel` | import_w, export_w, ct_ev, temp_living, co2_living, pir_hall, ... |
| `ts` | the device clock at the moment of sampling, including its drift |
| `value` | the device's quantised reading; null where the reading never arrived |
| `quality` | the collection platform's own quality assessment of the reading |
| `tier` | the sensor package consented to and installed at this premises |
| `provenance` | how the platform obtained the value: metered, estimated, interpolated |
| `unit` | the unit configured for the channel |

</details>

**Sample** — the first five rows of part 0, as written. Identity-bearing columns would be withheld; this dataset carries none.

| `device_id` | `premises_id` | `channel` | `ts` | `value` | `quality` | `tier` | `provenance` | `unit` |
|---|---|---|---|---|---|---|---|---|
| DEV-MPRN-12648450D5BDED… | MPRN-12648450D5BDED39DD | import_w | 2022-01-01 00:00:00+00:… | 225.0 | ok | T1 | metered | W |
| DEV-MPRN-12648450D5BDED… | MPRN-12648450D5BDED39DD | import_w | 2022-01-01 00:01:00+00:… | 224.0 | ok | T1 | metered | W |
| DEV-MPRN-12648450D5BDED… | MPRN-12648450D5BDED39DD | import_w | 2022-01-01 00:02:00+00:… | 221.0 | ok | T1 | metered | W |
| DEV-MPRN-12648450D5BDED… | MPRN-12648450D5BDED39DD | import_w | 2022-01-01 00:03:00+00:… | 226.0 | ok | T1 | metered | W |
| DEV-MPRN-12648450D5BDED… | MPRN-12648450D5BDED39DD | import_w | 2022-01-01 00:04:00+00:… | 227.0 | ok | T1 | metered | W |

**Joins**

- `premises_id` → D18, D19, D27 to D30 (the meter-boundary identity of a home)
- `value` observes `D16/D13/D17 true quantity` — agreement with it must not exceed the error model's bound

**Validation**

Plausibility checks whose own record in `v1/evidence/plausibility.json` names this dataset:

| Check | Quantity | Exposure | Outcome |
|---|---|---|---|
| PL-PEAK-01 | aggregate (after-diversity) load factor and diurnal… | none | **PASS** |

Links are attributed from the artefacts themselves — a check is listed where its own record names the dataset — rather than from a mapping kept in the generator, which would go stale.

<div style="page-break-after: always;"></div>

<a id="d19"></a>

## D19 · What leaves each home: aggregates, energy profile, flexibility compliance

Edge exports: what actually leaves each home across the meter boundary, at the settlement interval, under each of the declared export configurations. It is the network-side observable, and the one the privacy work is about.

**Key points**

- One row is one premises over one settlement interval under one export configuration.
- The configurations differ in what they reveal, and a configuration that claims to reveal less must contain less — which is tested against the others rather than against the schema.
- The compliance-only configuration deliberately carries no interval energy at all, so its energy columns are null by design and the requirement on them is conditional.
- Observable, and the input to the occupancy-inference attack: the finer the interval, the more an attacker recovers.
- The export configuration column must be filtered before any aggregate is computed, or the same home is counted several times.

**Facts**

| | |
|---|---|
| Class | OBS — Observable. What a device, respondent, assessor or operator would see. |
| Package | Observable |
| Path | `v1/observable/D19_part*.parquet` (13 parts) |
| Format | declared `parquet` ; on disk Parquet |
| Partitioning | none declared ; on disk 13 sequential parts |
| Rows | 3,521,520 |
| Size | 71.1 MB |
| Time span | `interval_start` 2022-01-01 00:00:00+00:00 → 2022-12-31 23:45:00+00:00 |
| Resolution | 15, 30 min intervals (mixed; filter the view column) |
| Primary key | declared `keyed_by: premises` ; id columns on disk: `premises_id`, `flex_event_id` |
| Status | **present** |
| Leakage audit | passed: no GT-class or forbidden field names present |
| Part hash | `c1501d39c88ba09d…` (part 0) |

**Schema** — types, null counts and ranges from the Parquet footers; descriptions and units from `schema/datasets.yaml`.

| Column | Type | Unit | Nulls | Min | Max | Declared |
|---|---|---|---|---|---|---|
| `premises_id` | string | — | no nulls | ESTATE-EST-047106012 | MPRN-FECC1C4894CC3DF0C3 | required |
| `interval_start` | timestamp[ns, tz=UTC] | — | no nulls | 2022-01-01 00:00:00+00:00 | 2022-12-31 23:45:00+00:00 | required |
| `interval_end` | timestamp[ns, tz=UTC] | — | no nulls | 2022-01-01 00:15:00+00:00 | 2023-01-01 00:00:00+00:00 | required |
| `import_wh` | double | Wh *(derived)* | 876,000 null (24.9%) | -0.0 | 37974.36125247425 | optional |
| `export_wh` | double | Wh *(derived)* | 876,000 null (24.9%) | -0.0 | 4267.068484287943 | optional |
| `interval_peak_w` | double | W *(derived)* | 876,000 null (24.9%) | -0.0 | 372431.8786237178 | optional |
| `interval_min_w` | double | W *(derived)* | 876,000 null (24.9%) | -0.0 | 61526.993772425485 | optional |
| `building_energy_profile.mean_w` | double | W *(derived)* | 876,000 null (24.9%) | -0.0 | 75948.72 | leaf of `building_energy_profile` |
| `building_energy_profile.peak_to_mean` | double | — | 876,000 null (24.9%) | -0.0 | 30.0 | leaf of `building_energy_profile` |
| `building_energy_profile.interval_min` | int64 | — | 876,000 null (24.9%) | 15 | 30 | leaf of `building_energy_profile` |
| `flex_event_id` | string | — | 3,521,520 null (100.0%) | — | — | optional |
| `flex_compliance_pct` | double | percent *(derived)* | 3,521,520 null (100.0%) | — | — | optional |
| `export_config` | string | — | no nulls | compliance_only | home_30min | required |
| `quality` | string | — | no nulls | ok | ok | required |

A dotted name is a leaf of a struct column: the Parquet footer flattens a struct, so the file physically carries the leaves while the dataset logically carries the parent.

<details><summary>Column descriptions, as declared</summary>

| Column | Declared description |
|---|---|
| `premises_id` | the meter point the edge device is commissioned against |
| `interval_start` | the export interval boundary agreed in the data contract |
| `interval_end` | as above |
| `import_wh` | conditionally required: present for every export configuration that carries a profile, absent for compliance_only (I-067). Enforced by test, not by t… |
| `export_wh` | conditionally required; see import_wh |
| `interval_peak_w` | named distinctly from D13.peak_w, which is a per-cycle peak: the two must never be joined. Conditionally required; see import_wh |
| `interval_min_w` | conditionally required; see import_wh |
| `building_energy_profile` | the building energy profile the edge device publishes under the data contract (R09) |
| `flex_event_id` | the identifier of the flexibility request the home was asked to serve |
| `flex_compliance_pct` | the edge device's own assessment of delivery against the request |
| `export_config` | the export configuration in force (7.8: home 30 min, home 15 min, estate aggregate, compliance only) |
| `quality` | the edge device's quality assessment of the interval |

</details>

**Sample** — the first five rows of part 0, as written. Identity-bearing columns would be withheld; this dataset carries none.

| `premises_id` | `interval_start` | `interval_end` | `import_wh` | `export_wh` | `interval_peak_w` | `interval_min_w` | `building_energy_profile` | `flex_event_id` | `flex_compliance_pct` | `export_config` | `quality` |
|---|---|---|---|---|---|---|---|---|---|---|---|
| MPRN-12648450D5BDED39DD | 2022-01-01 00:00:00+00:… | 2022-01-01 00:30:00+00:… | — | — | — | — | — | — | — | compliance_only | ok |
| MPRN-12648450D5BDED39DD | 2022-01-01 00:30:00+00:… | 2022-01-01 01:00:00+00:… | — | — | — | — | — | — | — | compliance_only | ok |
| MPRN-12648450D5BDED39DD | 2022-01-01 01:00:00+00:… | 2022-01-01 01:30:00+00:… | — | — | — | — | — | — | — | compliance_only | ok |
| MPRN-12648450D5BDED39DD | 2022-01-01 01:30:00+00:… | 2022-01-01 02:00:00+00:… | — | — | — | — | — | — | — | compliance_only | ok |
| MPRN-12648450D5BDED39DD | 2022-01-01 02:00:00+00:… | 2022-01-01 02:30:00+00:… | — | — | — | — | — | — | — | compliance_only | ok |

The rows above are the literal first five, and every measure in them is null — correct, and uninformative. The first five rows in which `import_wh` is populated:

| `premises_id` | `interval_start` | `interval_end` | `import_wh` | `export_wh` | `interval_peak_w` | `interval_min_w` | `building_energy_profile.mean_w` | `building_energy_profile.peak_to_mean` | `building_energy_profile.interval_min` | `flex_event_id` | `flex_compliance_pct` | `export_config` | `quality` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ESTATE-EST-047106012 | 2022-01-01 00:00:00… | 2022-01-01 00:30:00… | 4381.196552252413 | 0.0 | 11248.760032425662 | 6621.597818777181 | 8762.39 | 1.284 | 30 | — | — | estate_aggregate | ok |
| ESTATE-EST-047106012 | 2022-01-01 00:30:00… | 2022-01-01 01:00:00… | 3901.3790513445715 | 0.0 | 11278.364542007648 | 3992.6122184979986 | 7802.76 | 1.445 | 30 | — | — | estate_aggregate | ok |
| ESTATE-EST-047106012 | 2022-01-01 01:00:00… | 2022-01-01 01:30:00… | 4630.392135289398 | 0.0 | 11863.323238515239 | 6808.8309271933895 | 9260.78 | 1.281 | 30 | — | — | estate_aggregate | ok |
| ESTATE-EST-047106012 | 2022-01-01 01:30:00… | 2022-01-01 02:00:00… | 3989.4642311443044 | 0.0 | 11584.275992065674 | 4542.467851025011 | 7978.93 | 1.452 | 30 | — | — | estate_aggregate | ok |
| ESTATE-EST-047106012 | 2022-01-01 02:00:00… | 2022-01-01 02:30:00… | 4745.2611495013425 | 0.0 | 12451.327759712982 | 7126.193845762124 | 9490.52 | 1.312 | 30 | — | — | estate_aggregate | ok |

**Joins**

- `premises_id` → D18, D19, D27 to D30 (the meter-boundary identity of a home)

**Validation**

Plausibility checks whose own record in `v1/evidence/plausibility.json` names this dataset:

| Check | Quantity | Exposure | Outcome |
|---|---|---|---|
| PL-PEAK-01 | aggregate (after-diversity) load factor and diurnal… | none | **PASS** |

Opened directly by: `scripts/baile_nua/plausibility/checks.py:679`.

Links are attributed from the artefacts themselves — a check is listed where its own record names the dataset — rather than from a mapping kept in the generator, which would go stale.

<div style="page-break-after: always;"></div>

<a id="d20"></a>

## D20 · Ground-truth labels for detector scoring (onset, type, persistence)

Change labels: the ground-truth onset, type and persistence of every change a detector could be asked to find. It is the scoring key for the change-detection task.

**Key points**

- One row is one labelled change, with its onset date, class and whether it persists.
- Labels are tiered by how observable the change is, so a scoring service can report performance separately for the easy and the hard ones.
- Derived from the life events in D09 and the passport events in D03, and must reconcile with both.
- Scoring API only, never released: its own schema says so, and a model that has seen it has seen the answers.

**Facts**

| | |
|---|---|
| Class | GT — Ground truth. Never given to a model under test. |
| Package | Ground truth |
| Path | `v1/evidence/wp5_tenyear.json` |
| Format | declared `parquet` |
| Partitioning | none declared |
| Rows | 253 (in an evidence artefact) |
| Size | — |
| Time span | `true_onset_day` 17 → 3625 (day index from the run's first day, not a date) |
| Resolution | event |
| Primary key | grain `event` |
| Status | **partial** |

**Schema** — not available: the dataset is not on disk in `v1/`. It is **partial**.

Rows exist outside the released packages:

| Artefact | Key | Rows | Columns |
|---|---|---|---|
| `v1/evidence/wp5_tenyear.json` | `d20_change_labels` | 253 | building_id, change_class, detectable_from_tier, label_id, observable… |

The declared schema has 9 fields: `label_id`, `building_id`, `change_class`, `true_onset`, `true_end`, `persistence`, `source_event_ids`, `detectable_from_tier`, `observable_change_text`.

**Sample** — five rows as they are held in `v1/evidence/wp5_tenyear.json`. The dataset has no released Parquet part, so these are the rows there are.

| `label_id` | `building_id` | `change_class` | `true_onset_day` | `true_end_day` | `persistence` | `source_event_ids` | `detectable_from_tier` | `observable_change_text` |
|---|---|---|---|---|---|---|---|---|
| CL-LE-2022-DEATH-0001… | B-001012 | structural | 359 | — | permanent | ["LE-2022-DEATH-0001"] | T1 | withheld |
| CL-LE-2022-DEATH-0002… | B-001013 | structural | 223 | — | permanent | ["LE-2022-DEATH-0002"] | T1 | withheld |
| CL-LE-2022-DEATH-0003… | B-001023 | structural | 122 | — | permanent | ["LE-2022-DEATH-0003"] | T1 | withheld |
| CL-LE-2022-BIRTH-0001… | B-000867 | structural | 241 | — | permanent | ["LE-2022-BIRTH-0001"] | T1 | withheld |
| CL-LE-2022-PARTNERING… | B-000850 | structural | 52 | — | permanent | ["LE-2022-PARTNERING-… | T1 | withheld |

**Joins**

- `building_id` → D02 fabric, D03 passport, D16 state, D01 geography

**Validation**

No check in the artefacts names this dataset, and no module opens it by name. That is a statement about the evidence on disk, not a claim that the dataset is unchecked.

Links are attributed from the artefacts themselves — a check is listed where its own record names the dataset — rather than from a mapping kept in the generator, which would go stale.

<div style="page-break-after: always;"></div>

<a id="d21"></a>

## D21 · Human-readable narratives generated from D05 to D09

Biographies: human-readable narratives of each person's life, generated from the persistent, evolving and event datasets. They exist so a reader can sanity-check a synthetic life that no aggregate check would catch as implausible.

**Key points**

- One row is one person at one date, as text.
- Generated from the other datasets rather than authored, so a biography that reads strangely is evidence about the model.
- Declared as JSON or Markdown rather than Parquet, because the payload is prose.
- Ground truth, and free text: it contains, in readable form, everything the structured ground truth contains.

**Facts**

| | |
|---|---|
| Class | GT — Ground truth. Never given to a model under test. |
| Package | Ground truth |
| Path | not present in `v1/` |
| Format | declared `json` |
| Partitioning | none declared |
| Rows | — |
| Size | — |
| Time span | — |
| Resolution | person x date |
| Primary key | grain `person x date` |
| Status | **missing** |

**Schema** — not available: the dataset is not on disk in `v1/`. It is **missing**.

The declared schema has 5 fields: `person_id`, `as_of`, `narrative_md`, `source_record_ids`, `cluster_label`.

**Sample** — none: no rows on disk in `v1/`.

**Joins**

- No join keys present on disk for this dataset.

**Validation**

No check in the artefacts names this dataset, and no module opens it by name. That is a statement about the evidence on disk, not a claim that the dataset is unchecked.

Links are attributed from the artefacts themselves — a check is listed where its own record names the dataset — rather than from a mapping kept in the generator, which would go stale.

<div style="page-break-after: always;"></div>

<a id="d22"></a>

## D22 · Appliance waveform templates and variation parameters

The signature library: appliance waveform templates and the parameters that vary them. It is metadata rather than data about the town — the same library would serve another town.

**Key points**

- One row is one appliance signature template.
- Keyed by the signature identifier that appears on every cycle in D13, which is what makes a cycle's waveform reproducible.
- Declared as Parquet alongside compressed arrays, because a waveform is a vector rather than a scalar.
- Metadata: it ships in the evidence package, not with the data.

**Facts**

| | |
|---|---|
| Class | META — Provenance and calibration. |
| Package | Evidence |
| Path | not present in `v1/` |
| Format | declared `parquet + npz` |
| Partitioning | none declared |
| Rows | — |
| Size | — |
| Time span | — |
| Resolution | signature |
| Primary key | grain `signature` |
| Status | **missing** |

**Schema** — not available: the dataset is not on disk in `v1/`. It is **missing**.

The declared schema has 14 fields: `signature_id`, `appliance_type`, `programme`, `source_dataset`, `source_licence`, `template_hz`, `template_w`, `duration_s`, `energy_wh_nominal`, `var_power_cv`, `var_duration_cv`, `ageing_power_per_year`, `irish_specific`, `evidence_status`.

**Sample** — none: no rows on disk in `v1/`.

**Joins**

- No join keys present on disk for this dataset.

**Validation**

No check in the artefacts names this dataset, and no module opens it by name. That is a statement about the evidence on disk, not a claim that the dataset is unchecked.

Links are attributed from the artefacts themselves — a check is listed where its own record names the dataset — rather than from a mapping kept in the generator, which would go stale.

<div style="page-break-after: always;"></div>

<a id="d23"></a>

## D23 · Code and data versions, parameters, seeds, checksums

Run manifests: the code and data versions, parameters, seeds and checksums for every run. It is what makes a figure in a report traceable to the run that produced it.

**Key points**

- One row is one run.
- Records the master seed and the library versions, because a run whose dependency versions are unknown cannot be reproduced.
- Held as JSON in the repository as well as in the object store, so the provenance survives the data being moved.
- Metadata, and the first thing to read when two runs disagree.

**Facts**

| | |
|---|---|
| Class | META — Provenance and calibration. |
| Package | Evidence |
| Path | not present in `v1/` |
| Format | declared `json` |
| Partitioning | none declared |
| Rows | — |
| Size | — |
| Time span | — |
| Resolution | run |
| Primary key | grain `run` |
| Status | **missing** |

**Schema** — not available: the dataset is not on disk in `v1/`. It is **missing**.

The declared schema has 16 fields: `run_id`, `created_at_utc`, `label`, `code_version`, `code_git_sha`, `code_tree_hash`, `schema_version`, `design_revision`, `master_seed`, `coupling_mode`, `scope`, `input_sources`, `parameters`, `outputs`, `checkpoint_chain_head`, `environment`.

**Sample** — none: no rows on disk in `v1/`.

**Joins**

- No join keys present on disk for this dataset.

**Validation**

No check in the artefacts names this dataset, and no module opens it by name. That is a statement about the evidence on disk, not a claim that the dataset is unchecked.

Links are attributed from the artefacts themselves — a check is listed where its own record names the dataset — rather than from a mapping kept in the generator, which would go stale.

<div style="page-break-after: always;"></div>

<a id="d24"></a>

## D24 · Every empirical target with source, version and tolerance

Calibration targets: every empirical quantity the model is calibrated or compared against, with its source, version, tolerance and exposure class. It is the register that decides which checks count as independent.

**Key points**

- One row is one target statistic from one source.
- Carries the exposure class, which is what separates a check that validates the model from one that reports the model agreeing with its own input.
- Every target names a file in the sources tree, so no calibration number in the project is unsourced.
- Metadata: it ships in the evidence package with the sources themselves.

**Facts**

| | |
|---|---|
| Class | META — Provenance and calibration. |
| Package | Evidence |
| Path | `v1/evidence/d24_calibration_targets.json` |
| Format | declared `parquet + citation file` |
| Partitioning | none declared |
| Rows | 113 (in an evidence artefact) |
| Size | — |
| Time span | — |
| Resolution | statistic |
| Primary key | grain `statistic` |
| Status | **partial** |

**Schema** — not available: the dataset is not on disk in `v1/`. It is **partial**.

Rows exist outside the released packages:

| Artefact | Key | Rows | Columns |
|---|---|---|---|
| `v1/evidence/d24_calibration_targets.json` | `(the artefact is the dataset)` | 113 | conditioned_on, exposure, quantity, scope_note, source_key, source_sh… |

The declared schema has 17 fields: `target_id`, `statistic`, `domain`, `value`, `value_json`, `unit`, `tolerance`, `tolerance_kind`, `source_file`, `source_sha256`, `source_url`, `source_licence`, `retrieved_at`, `intended_use`, `model_development_exposure`, `evidence_tag`, `provisional`.

**Sample** — five rows as they are held in `v1/evidence/d24_calibration_targets.json`. The dataset has no released Parquet part, so these are the rows there are.

| `target_id` | `quantity` | `unit` | `value` | `conditioned_on` | `source_key` | `source_sha256` | `source_title` | `year` | `exposure` | `scope_note` |
|---|---|---|---|---|---|---|---|---|---|---|
| D24-ELEC-apartment-A-… | mean annual household… | kWh per dwelling per … | 2999.0 | {"dwelling_type": "ap… | cso.electricity.dbere… | d0082edfdcfd08b94a15d… | Household Electricity… | 2022 | tuning | Covers ALL household … |
| D24-ELEC-apartment-C-… | mean annual household… | kWh per dwelling per … | 5077.0 | {"dwelling_type": "ap… | cso.electricity.dbere… | d0082edfdcfd08b94a15d… | Household Electricity… | 2022 | tuning | Covers ALL household … |
| D24-ELEC-apartment-D-… | mean annual household… | kWh per dwelling per … | 4969.0 | {"dwelling_type": "ap… | cso.electricity.dbere… | d0082edfdcfd08b94a15d… | Household Electricity… | 2022 | tuning | Covers ALL household … |
| D24-ELEC-apartment-E-… | mean annual household… | kWh per dwelling per … | 4740.0 | {"dwelling_type": "ap… | cso.electricity.dbere… | d0082edfdcfd08b94a15d… | Household Electricity… | 2022 | tuning | Covers ALL household … |
| D24-ELEC-apartment-F-… | mean annual household… | kWh per dwelling per … | 3904.0 | {"dwelling_type": "ap… | cso.electricity.dbere… | d0082edfdcfd08b94a15d… | Household Electricity… | 2022 | tuning | Covers ALL household … |

**Joins**

- No join keys present on disk for this dataset.

**Validation**

No check in the artefacts names this dataset, and no module opens it by name. That is a statement about the evidence on disk, not a claim that the dataset is unchecked.

Links are attributed from the artefacts themselves — a check is listed where its own record names the dataset — rather than from a mapping kept in the generator, which would go stale.

<div style="page-break-after: always;"></div>

<a id="d25"></a>

## D25 · HRSD participants, profiles, MCV, sessions and responses in MIMIC schema 1.1

The MIMIC export: HRSD participants, profiles, moral-choice vectors, sessions and responses, delivered through the MIMIC API in its own schema. It is the stated-preference half of the project, beside the measured half.

**Key points**

- One row is a participant, a session or a response, depending on the table.
- Delivered through the MIMIC API against a local instance, never a remote or production one.
- A subset of participants is linked to the synthetic population; the rest are an unlinked pool, so a linkage attack cannot assume every participant is a resident.
- Observable on the MIMIC side: this is what a researcher analysing the panel would hold.
- The crosswalk back to a person is in D26 and is not part of this dataset.

**Facts**

| | |
|---|---|
| Class | OBS — Observable. What a device, respondent, assessor or operator would see. |
| Package | Observable |
| Path | not present in `v1/` |
| Format | declared `MIMIC MySQL via the public API; Parquet copy` |
| Partitioning | none declared |
| Rows | — |
| Size | — |
| Time span | — |
| Resolution | participant, session, response |
| Primary key | grain `participant, session, response` |
| Status | **missing** |

**Schema** — not available: the dataset is not on disk in `v1/`. It is **missing**.

The declared schema has 29 fields: `participant_id`, `consent_version`, `consent_granted_at`, `mcv_position`, `age_band`, `reported_sex`, `household_size`, `children_present`, `employment_status`, `reported_work_pattern`, `reported_dwelling_type`, `ownership_status`, `region_country`, `region_nuts3`, `urban_rural_island`, `income_band`, `der_ownership`, `environmental_concern`, `trust_in_automation`, `comfort_sensitivity`, `mcv_01_to_10`, `profile_optional`, `session_id`, `chosen_signal`, `chosen_display_position`, `display_permutation`, `latency_ms`, `is_probe`, `is_probe_repeat`.

**Sample** — none: no rows on disk in `v1/`.

**Joins**

- No join keys present on disk for this dataset.

**Validation**

No check in the artefacts names this dataset, and no module opens it by name. That is a statement about the evidence on disk, not a claim that the dataset is unchecked.

Links are attributed from the artefacts themselves — a check is listed where its own record names the dataset — rather than from a mapping kept in the generator, which would go stale.

<div style="page-break-after: always;"></div>

<a id="d26"></a>

## D26 · Crosswalk to person_id, true traits, planted segments, propensity, gap, test settings

The MIMIC answer key: the crosswalk from participant to person, the true traits, the planted segments, response propensity and stated-preference gap. It is how a panel analysis is scored.

**Key points**

- One row is one participant.
- Holds the planted structure — the segments and effects a correct analysis should recover — which is what makes the panel a test rather than a dataset.
- Carries the stated-against-revealed gap per participant, so a model that assumes stated preference predicts behaviour can be shown to be wrong by construction.
- Scoring only. Releasing it would make every MIMIC test unfalsifiable.

**Facts**

| | |
|---|---|
| Class | GT — Ground truth. Never given to a model under test. |
| Package | Ground truth |
| Path | not present in `v1/` |
| Format | declared `parquet` |
| Partitioning | none declared |
| Rows | — |
| Size | — |
| Time span | — |
| Resolution | participant |
| Primary key | grain `participant` |
| Status | **missing** |

**Schema** — not available: the dataset is not on disk in `v1/`. It is **missing**.

The declared schema has 15 fields: `participant_id`, `person_id`, `pool`, `true_traits`, `planted_segment`, `planted_null_mode`, `response_propensity`, `stated_gap`, `satisficer`, `planted_position_bias`, `planted_context_effect`, `generator`, `gc_mode`, `simulated_session_date`, `test_mode_settings`.

**Sample** — none: no rows on disk in `v1/`.

**Joins**

- No join keys present on disk for this dataset.

**Validation**

No check in the artefacts names this dataset, and no module opens it by name. That is a statement about the evidence on disk, not a claim that the dataset is unchecked.

Links are attributed from the artefacts themselves — a check is listed where its own record names the dataset — rather than from a mapping kept in the generator, which would go stale.

<div style="page-break-after: always;"></div>

<a id="d27"></a>

## D27 · Supplier tariff, ToU and export rates, switches, flexibility and P2P terms, connection limits

Tariffs and contracts: each home's supplier tariff, time-of-use and export rates, switch dates, flexibility and peer-to-peer contract terms, and its connection limits. It is the commercial context a flexibility model needs.

**Key points**

- One row is one home over one interval of one contract.
- Includes the import and export capacity limits, so a dispatch that would breach the connection is representable as a breach.
- Switch dates matter: a home that changed supplier mid-run has two tariffs, and a model that assumes one will misprice it.
- Observable — it is what a utility or an aggregator would hold — while the market rules themselves are metadata.

**Facts**

| | |
|---|---|
| Class | OBS — Observable. What a device, respondent, assessor or operator would see. |
| Package | Observable |
| Path | not present in `v1/` |
| Format | declared `parquet` |
| Partitioning | none declared |
| Rows | — |
| Size | — |
| Time span | — |
| Resolution | home x interval |
| Primary key | declared `keyed_by: premises` |
| Status | **missing** — the edge-export contract view is not written by E1's runner |

**Schema** — not available: the dataset is not on disk in `v1/`. It is **missing**.

Reason recorded on disk, in `v1/evidence/delivery_packages.json`: *the edge-export contract view is not written by E1's runner*

The declared schema has 14 fields: `premises_id`, `valid_from`, `valid_to`, `supplier`, `tariff_code`, `tariff_kind`, `rate_schedule`, `standing_charge_eur_day`, `export_rate_eur_kwh`, `max_import_kw`, `max_export_kw`, `der_notification_ref`, `flex_contract_terms`, `trial_arm`.

**Sample** — none: no rows on disk in `v1/`.

**Joins**

- No join keys present on disk for this dataset.

**Validation**

No check in the artefacts names this dataset, and no module opens it by name. That is a statement about the evidence on disk, not a claim that the dataset is unchecked.

Links are attributed from the artefacts themselves — a check is listed where its own record names the dataset — rather than from a mapping kept in the generator, which would go stale.

<div style="page-break-after: always;"></div>

<a id="d28"></a>

## D28 · Recruitment, response rates, consent to sensors, dropouts, trial arms and periods

The study protocol: recruitment, response rates, consent to sensors, dropouts, trial arms and periods. It is the administrative record of how the data came to exist, and the mechanism by which it is incomplete.

**Key points**

- One row is one premises and one protocol event — recruited, consented, installed, dropped out.
- The selection mechanism is ground truth: who joins the study is not random, and a model that ignores that will generalise badly from the sample.
- Carries incomplete consent records, installer delays and arm-assignment deviations, because real protocols have all three.
- Observable as the record; the reason behind each gap is not observable.

**Facts**

| | |
|---|---|
| Class | OBS — Observable. What a device, respondent, assessor or operator would see. |
| Package | Observable |
| Path | not present in `v1/` |
| Format | declared `parquet + protocol document` |
| Partitioning | none declared |
| Rows | — |
| Size | — |
| Time span | — |
| Resolution | premises x event |
| Primary key | declared `keyed_by: premises` |
| Status | **missing** — built in observation/nonsensor.py and not yet written into a package by the runner; D31 carries weather only (I-072) |

**Schema** — not available: the dataset is not on disk in `v1/`. It is **missing**.

Reason recorded on disk, in `v1/evidence/delivery_packages.json`: *built in observation/nonsensor.py and not yet written into a package by the runner; D31 carries weather only (I-072)*

The declared schema has 10 fields: `premises_id`, `protocol_event`, `recorded_at`, `recruitment_route`, `consent_sensors`, `tier_consented`, `install_delay_days`, `trial_arm`, `arm_deviation`, `withdrawal_reason`.

**Sample** — none: no rows on disk in `v1/`.

**Joins**

- No join keys present on disk for this dataset.

**Validation**

No check in the artefacts names this dataset, and no module opens it by name. That is a statement about the evidence on disk, not a claim that the dataset is unchecked.

Links are attributed from the artefacts themselves — a check is listed where its own record names the dataset — rather than from a mapping kept in the generator, which would go stale.

<div style="page-break-after: always;"></div>

<a id="d29"></a>

## D29 · Questionnaire answers with calibrated reporting error and non-response

The household survey: questionnaire answers with calibrated reporting error and non-response. It is what people say, as distinct from what the sensors recorded.

**Key points**

- One row is one premises in one survey wave.
- Error is modelled rather than added: unit and item non-response that depends on circumstances, social-desirability bias, recall error, satisficing and answers going stale between waves.
- The true values are in the ground-truth datasets, which is what makes the reporting error measurable rather than assumed.
- Observable. The gap between a survey answer and the truth is one of the things the release exists to let people study.

**Facts**

| | |
|---|---|
| Class | OBS — Observable. What a device, respondent, assessor or operator would see. |
| Package | Observable |
| Path | not present in `v1/` |
| Format | declared `parquet` |
| Partitioning | none declared |
| Rows | — |
| Size | — |
| Time span | — |
| Resolution | premises x wave |
| Primary key | declared `keyed_by: premises` |
| Status | **missing** — built in observation/nonsensor.py and not yet written into a package by the runner; D31 carries weather only (I-072) |

**Schema** — not available: the dataset is not on disk in `v1/`. It is **missing**.

Reason recorded on disk, in `v1/evidence/delivery_packages.json`: *built in observation/nonsensor.py and not yet written into a package by the runner; D31 carries weather only (I-072)*

The declared schema has 15 fields: `premises_id`, `wave`, `responded_at`, `q_household_size`, `q_children_under_18`, `q_occupied_weekday_hours`, `q_dwelling_type`, `q_heating_system`, `q_has_pv`, `q_has_ev`, `q_appliances`, `q_env_behaviour_score`, `q_comfort_preference_c`, `straightlined`, `item_nonresponse_count`.

**Sample** — none: no rows on disk in `v1/`.

**Joins**

- `q_appliances` observes `D04 appliance stock` — agreement with it must not exceed the error model's bound
- `q_children_under_18` observes `D06 membership under 18` — agreement with it must not exceed the error model's bound
- `q_dwelling_type` observes `D02.dwelling_type` — agreement with it must not exceed the error model's bound
- `q_has_ev` observes `D04 vehicle asset is EV` — agreement with it must not exceed the error model's bound
- `q_has_pv` observes `D04 pv asset present` — agreement with it must not exceed the error model's bound
- `q_heating_system` observes `D02.heating_system` — agreement with it must not exceed the error model's bound
- `q_household_size` observes `D06.membership count` — agreement with it must not exceed the error model's bound
- `q_occupied_weekday_hours` observes `D11 presence hours` — agreement with it must not exceed the error model's bound

**Validation**

No check in the artefacts names this dataset, and no module opens it by name. That is a statement about the evidence on disk, not a claim that the dataset is unchecked.

Links are attributed from the artefacts themselves — a check is listed where its own record names the dataset — rather than from a mapping kept in the generator, which would go stale.

<div style="page-break-after: always;"></div>

<a id="d30"></a>

## D30 · Recorded building and asset data, stale or wrong at realistic rates

Recorded metadata: the BER, floor area, PV capacity, dates, orientation and shading as some administrative record holds them — stale or wrong at realistic rates. It is the building data a real analyst actually gets.

**Key points**

- One row is one premises at one version of the record.
- Wrong in the ways records are wrong: missing fields, values that predate a retrofit, unit and transcription errors, conflicts between assessor and installer, and records for assets since removed.
- The true values are in D02 and D04, so the error can be quantified instead of asserted.
- Observable, and the right input for any model whose real-world counterpart would be given a BER certificate rather than a fabric model.

**Facts**

| | |
|---|---|
| Class | OBS — Observable. What a device, respondent, assessor or operator would see. |
| Package | Observable |
| Path | not present in `v1/` |
| Format | declared `parquet` |
| Partitioning | none declared |
| Rows | — |
| Size | — |
| Time span | — |
| Resolution | premises x version |
| Primary key | declared `keyed_by: premises` |
| Status | **missing** — built in observation/nonsensor.py and not yet written into a package by the runner; D31 carries weather only (I-072) |

**Schema** — not available: the dataset is not on disk in `v1/`. It is **missing**.

Reason recorded on disk, in `v1/evidence/delivery_packages.json`: *built in observation/nonsensor.py and not yet written into a package by the runner; D31 carries weather only (I-072)*

The declared schema has 16 fields: `premises_id`, `record_version`, `recorded_at`, `record_source`, `rec_ber_band`, `rec_ber_kwh_m2_yr`, `rec_floor_area_m2`, `rec_dwelling_type`, `rec_build_year`, `rec_heating_system`, `rec_pv_kwp`, `rec_pv_install_date`, `rec_pv_azimuth_deg`, `rec_shading`, `record_conflict`, `asset_since_removed`.

**Sample** — none: no rows on disk in `v1/`.

**Joins**

- `rec_ber_band` observes `D02.ber_band` — agreement with it must not exceed the error model's bound
- `rec_ber_kwh_m2_yr` observes `D02.ber_kwh_m2_yr` — agreement with it must not exceed the error model's bound
- `rec_build_year` observes `D02.build_year` — agreement with it must not exceed the error model's bound
- `rec_dwelling_type` observes `D02.dwelling_type` — agreement with it must not exceed the error model's bound
- `rec_floor_area_m2` observes `D02.floor_area_m2` — agreement with it must not exceed the error model's bound
- `rec_heating_system` observes `D02.heating_system` — agreement with it must not exceed the error model's bound
- `rec_pv_azimuth_deg` observes `D04.pv_azimuth_deg` — agreement with it must not exceed the error model's bound
- `rec_pv_install_date` observes `D04.install_date` — agreement with it must not exceed the error model's bound
- `rec_pv_kwp` observes `D04.capacity for pv` — agreement with it must not exceed the error model's bound

**Validation**

No check in the artefacts names this dataset, and no module opens it by name. That is a statement about the evidence on disk, not a claim that the dataset is unchecked.

Links are attributed from the artefacts themselves — a check is listed where its own record names the dataset — rather than from a mapping kept in the generator, which would go stale.

<div style="page-break-after: always;"></div>

<a id="d31"></a>

## D31 · Station weather, wholesale prices, carbon intensity, system demand, flex events

External series: station weather, wholesale prices, carbon intensity, system demand and flexibility-service events. It is the published context anyone could download, with the defects published data has.

**Key points**

- One row is one observation of one series at its own native resolution.
- Distinct from D15: this is the station's reading, with outages and gap-filled values, not the weather at the dwelling.
- Includes revised and later-corrected values, so a model trained on the first publication of a price series can be shown to have used data that no longer exists.
- Observable, and the only observable dataset whose contents are, in the real world, public.

**Facts**

| | |
|---|---|
| Class | OBS — Observable. What a device, respondent, assessor or operator would see. |
| Package | Observable |
| Path | not present in `v1/` |
| Format | declared `parquet` |
| Partitioning | none declared |
| Rows | — |
| Size | — |
| Time span | — |
| Resolution | series-native |
| Primary key | grain `series-native` |
| Status | **missing** — built in observation/nonsensor.py and not yet written into a package by the runner; D31 carries weather only (I-072) |

**Schema** — not available: the dataset is not on disk in `v1/`. It is **missing**.

Reason recorded on disk, in `v1/evidence/delivery_packages.json`: *built in observation/nonsensor.py and not yet written into a package by the runner; D31 carries weather only (I-072)*

The declared schema has 10 fields: `series_id`, `ts`, `value`, `unit`, `station_or_zone`, `quality`, `provenance`, `revision`, `realisation_id`, `segment`.

**Sample** — none: no rows on disk in `v1/`.

**Joins**

- `value` observes `D15 for weather series` — agreement with it must not exceed the error model's bound

**Validation**

No check in the artefacts names this dataset, and no module opens it by name. That is a statement about the evidence on disk, not a claim that the dataset is unchecked.

Links are attributed from the artefacts themselves — a check is listed where its own record names the dataset — rather than from a mapping kept in the generator, which would go stale.

<div style="page-break-after: always;"></div>

<a id="appendix-a"></a>

## Appendix A · Folder tree of `v1/`

Folder sizes from `stat()` over every file beneath them. Within a folder, files are grouped by name pattern — a part number collapses to `*` — and the groups are listed largest first.

```
v1/       737.1 MB   total
├── evidence/                  1.6 MB
│   ├── wp5_tenyear.json                 1 file(s)   395.5 kB
│   ├── assumption_sweep_u30.json        1 file(s)   268.5 kB
│   ├── e1_gate_report.json              1 file(s)   166.6 kB
│   ├── d24_calibration_targets.json     1 file(s)   113.5 kB
│   ├── junit.xml                        1 file(s)   101.4 kB
│   ├── w2_steps6to9.json                1 file(s)    47.3 kB
│   ├── data_dictionary.md               1 file(s)    46.1 kB
│   ├── delivery_packages.json           1 file(s)    42.5 kB
│   └── … 32 further name pattern(s)       32 file(s)   428.9 kB
├── ground_truth/            158.0 MB
│   ├── D16_part*.parquet               13 file(s)   122.8 MB
│   ├── D13_part*.parquet               13 file(s)    34.7 MB
│   ├── D11_part*.parquet                1 file(s)   490.6 kB
│   ├── D16_part*.manifest.json         13 file(s)    15.0 kB
│   ├── D13_part*.manifest.json         13 file(s)    10.0 kB
│   └── D11_part*.manifest.json          1 file(s)      657 B
├── observable/              577.4 MB
│   ├── D18_part*.parquet               13 file(s)   506.4 MB
│   ├── D19_part*.parquet               13 file(s)    71.1 MB
│   ├── D19_part*.manifest.json         13 file(s)    11.2 kB
│   └── D18_part*.manifest.json         13 file(s)     9.3 kB
├── .DS_Store                  8.0 kB
└── run_diagnostics.json      95.4 kB
```

<div style="page-break-after: always;"></div>

<a id="appendix-b"></a>

## Appendix B · Keys and joins

```
                    small_area  (CSO small-area code, e.g. 047106012)
                         │
                         │  every dwelling sits in exactly one
                         ▼
  D01 town_geo ──── building_id (B-) ──── D02 fabric ──── D03 passport
                         │                    │
                         │                    └──── D04 assets (A-)
                         │                                 │
                         │                          signature_id → D22
                         ▼
                   household_id (H-) ──── D06 membership ──┐
                         │                                 │
                         ▼                                 ▼
                   person_id (P-) ──── D05 persons    D07 relationships
                         │
        ┌────────────────┼────────────────┬──────────────┐
        ▼                ▼                ▼              ▼
  D08 states      D10 activities    D11 presence    D12 trips
        │                │                                │
        └──── D09 life events ──── D20 change labels      │
                         │                                │
                         ▼                                ▼
                   D13 appliance cycles              vehicle state
                         │
                         ▼   the meter boundary: GT becomes OBS
                   premises_id (MPRN-)
                         │
        ┌────────────────┼────────────────┬──────────────┐
        ▼                ▼                ▼              ▼
  D18 observations  D19 edge exports  D27 tariffs   D28-D30 records

  timestamp: every series is keyed by a UTC instant. Interval datasets
  carry interval_start and interval_end; point series carry ts.
```

The identifier prefixes are declared in the schema: `P-` person, `H-` household, `B-` building, `A-` asset, `V-` venue, `MPRN-` premises.

`premises_id` is the join that matters most, because it is the line where ground truth becomes observable. A person has a `person_id`, lives in a `household_id`, which occupies a `building_id`, which is metered as a `premises_id`. Everything on the observable side of that line is keyed by premises and nothing on it is keyed by person — which is the privacy property the leakage test enforces, not a convention.

<div style="page-break-after: always;"></div>

<a id="appendix-c"></a>

## Appendix C · Conventions

| | |
|---|---|
| Time zone | UTC timestamptz; Europe/Dublin views are derived |
| Timestamp convention | **Period start.** Verified on disk: interval datasets carry both `interval_start` and `interval_end`, so the convention is in the data rather than in this document; a point series' `ts` is the instant of the reading. |
| Half-hour indexing | A settlement interval is identified by its start instant, not by an ordinal. Checked across every column on disk and every column the schema declares: no half-hour or settlement-period number exists in either. An ordinal is ambiguous across a daylight-saving boundary and a UTC instant is not. |
| Unit, energy | `Wh` |
| Unit, power | `W` |
| Unit, temperature | `degC` |
| Unit, relative_humidity | `percent` |
| Unit, co2 | `ppm` |
| Unit, distance | `km` |
| Energy against power | Interval datasets carry energy in Wh for the interval and, separately, the peak and minimum power in W within it. Dividing the one by the other recovers the mean power and loses the peak, which is the quantity a network cares about. |
| Missing data | A value absent by mechanism is **null**, and the reason is carried in the quality flag and the provenance code on the same row. A value suppressed by an export configuration is also null, and typed `float64` rather than object, so the file's schema does not change when a column happens to be entirely absent. |
| Zero against null | Zero means measured as zero. Null means not measured. The distinction is load-bearing: a gas dwelling's heat-pump electricity is zero by construction, and a meter outage is null. |

<div style="page-break-after: always;"></div>

<a id="appendix-d"></a>

## Appendix D · Design against disk

A list, not a plan. Nothing here is fixed by this document.

### D.1 Declared datasets with no released Parquet part in `v1/`

| Dataset | Title | Class | Status | Rows found elsewhere | Reason recorded on disk |
|---|---|---|---|---|---|
| D01 | Parcels, streets, venues, network topology | GT | missing | none | — |
| D02 | HRSD_Buildings: fabric, archetype, BER, systems, physics parameters | GT | missing | none | — |
| D03 | Dated building events (extension, retrofit, asset added or removed) | GT | partial | v1/evidence/wp5_tenyear.json (45 rows) | — |
| D04 | Appliances, heating, PV, BESS, chargers, vehicles, with owner and lifetime | GT | missing | none | — |
| D05 | HRSD_Occupants: persistent characteristics and trait vector | GT | missing | none | — |
| D06 | Who lives where, from when to when | GT | missing | none | — |
| D07 | Kin, partner, carer, friend, co-worker edges | GT | missing | none | — |
| D08 | Evolving states, slowly changing (SCD-2) | GT | missing | none | — |
| D09 | Births, deaths, moves, jobs, health states, decisions | GT | partial | v1/evidence/wp5_tenyear.json (250 rows) | — |
| D10 | Person activity intervals with location and co-participants | GT | missing | none | — |
| D12 | Origin, destination, mode, vehicle, distance | GT | missing | none | — |
| D14 | Event instances, phases, footprint, attendance | GT | missing | none | — |
| D15 | True site weather and solar geometry driving physics and behaviour | GT | missing | none | — |
| D17 | Feeder and transformer loading, voltages, outages | GT | missing | none | — |
| D20 | Ground-truth labels for detector scoring (onset, type, persistence) | GT | partial | v1/evidence/wp5_tenyear.json (253 rows) | — |
| D21 | Human-readable narratives generated from D05 to D09 | GT | missing | none | — |
| D22 | Appliance waveform templates and variation parameters | META | missing | none | — |
| D23 | Code and data versions, parameters, seeds, checksums | META | missing | none | — |
| D24 | Every empirical target with source, version and tolerance | META | partial | v1/evidence/d24_calibration_targets.json (113 rows) | — |
| D25 | HRSD participants, profiles, MCV, sessions and responses in MIMIC schema 1.1 | OBS | missing | none | — |
| D26 | Crosswalk to person_id, true traits, planted segments, propensity, gap, test settings | GT | missing | none | — |
| D27 | Supplier tariff, ToU and export rates, switches, flexibility and P2P terms, connection limits | OBS | missing | none | the edge-export contract view is not written by E1's runner |
| D28 | Recruitment, response rates, consent to sensors, dropouts, trial arms and periods | OBS | missing | none | built in observation/nonsensor.py and not yet written into … |
| D29 | Questionnaire answers with calibrated reporting error and non-response | OBS | missing | none | built in observation/nonsensor.py and not yet written into … |
| D30 | Recorded building and asset data, stale or wrong at realistic rates | OBS | missing | none | built in observation/nonsensor.py and not yet written into … |
| D31 | Station weather, wholesale prices, carbon intensity, system demand, flex events | OBS | missing | none | built in observation/nonsensor.py and not yet written into … |

### D.2 Declared columns absent from the rows that exist

Covers present datasets, where the comparison is against the Parquet schema, and partial ones, where it is against the keys of the rows held in an evidence artefact.

| Dataset | Declared column | Required | Compared against |
|---|---|---|---|
| D03 | `effective_at` | yes | artefact rows |
| D03 | `decided_at` | no | artefact rows |
| D09 | `effective_at` | yes | artefact rows |
| D09 | `decided_at` | no | artefact rows |
| D20 | `true_onset` | yes | artefact rows |
| D20 | `true_end` | no | artefact rows |
| D24 | `statistic` | yes | artefact rows |
| D24 | `domain` | yes | artefact rows |
| D24 | `value_json` | no | artefact rows |
| D24 | `tolerance` | yes | artefact rows |
| D24 | `tolerance_kind` | yes | artefact rows |
| D24 | `source_file` | yes | artefact rows |
| D24 | `source_url` | yes | artefact rows |
| D24 | `source_licence` | yes | artefact rows |
| D24 | `retrieved_at` | yes | artefact rows |
| D24 | `intended_use` | yes | artefact rows |
| D24 | `model_development_exposure` | yes | artefact rows |
| D24 | `evidence_tag` | yes | artefact rows |
| D24 | `provisional` | yes | artefact rows |

### D.2b Keys in the artefact rows that the schema does not declare

| Dataset | Key on disk |
|---|---|
| D03 | `decided_day` |
| D03 | `effective_day` |
| D03 | `measure` |
| D09 | `decided_day` |
| D09 | `effective_day` |
| D20 | `true_end_day` |
| D20 | `true_onset_day` |
| D24 | `conditioned_on` |
| D24 | `exposure` |
| D24 | `quantity` |
| D24 | `scope_note` |
| D24 | `source_key` |
| D24 | `source_title` |
| D24 | `year` |

### D.3 Columns on disk that the schema does not declare

None.

### D.4 Declared storage against storage on disk

| Dataset | Declared | On disk |
|---|---|---|
| D01 | geoparquet | absent |
| D02 | parquet | absent |
| D03 | parquet | JSON inside an evidence artefact |
| D04 | parquet | absent |
| D05 | parquet | absent |
| D06 | parquet | absent |
| D07 | parquet | absent |
| D08 | parquet | absent |
| D09 | parquet | JSON inside an evidence artefact |
| D10 | parquet | absent |
| D12 | parquet | absent |
| D14 | parquet | absent |
| D15 | parquet | absent |
| D16 | re-run on demand (U07 option b, decision D-009); hot slices cached | Parquet |
| D17 | parquet | absent |
| D18 | rendered on demand; cached slices | Parquet |
| D20 | parquet | JSON inside an evidence artefact |
| D21 | json | absent |
| D22 | parquet + npz | absent |
| D23 | json | absent |
| D24 | parquet + citation file | JSON inside an evidence artefact |
| D25 | MIMIC MySQL via the public API; Parquet copy | absent |
| D26 | parquet | absent |
| D27 | parquet | absent |
| D28 | parquet + protocol document | absent |
| D29 | parquet | absent |
| D30 | parquet | absent |
| D31 | parquet | absent |

### D.5 Datasets present on disk that the schema does not declare

None.

### D.6 Schema revision against design revision

`schema/datasets.yaml` declares `design_revision: 3` and `design_frozen` with it, while the newest design document on disk is `docs/Baile_Nua_Technical_Design_Review_r4.md` — revision 4. Every dataset manifest written by the engine stamps the schema's number, so the parts on disk say revision 3 too. Which of the two is authoritative is not recorded anywhere, and this document does not decide it.

<div style="page-break-after: always;"></div>

<a id="appendix-e"></a>

## Appendix E · Glossary

| Term | Meaning |
|---|---|
| **GT** | Ground truth. Never given to a model under test. Released in the `ground_truth` package. |
| **OBS** | Observable. What a device, respondent, assessor or operator would see. Released in the `observable` package. |
| **META** | Provenance and calibration. Released in the `evidence` package. |
| **T1 to T4** | Two different tier systems share the names. **Sensor tiers** T1 to T4 rank how well a premises is instrumented, from a basic meter to research-grade sub-metering, and appear per premises in the observable data. **Label tiers** T1 to T4 rank how observable a change in D20 is, so a detector's score can be reported separately for changes that are easy and hard to see. |
| **Exposure class** | How a source was used before it was compared against. `none` — never used to build the model, so a pass against it is independent evidence. `design` — its information reached the model through a design choice or a sibling table. `selection` — used to choose between model variants. `tuning` — a parameter was fitted to it. A source used to build the model cannot validate it, so the three pass counts are reported separately and never summed. |
| **E1 / E2** | The engineering gates. E1 is the eight-criterion verification of the estate-year: invariants, determinism, negative controls, marginals, a complete replayed year, the MIMIC tests, the no-calibration claim, and measured cost. E2 is the seven-criterion gate at town and decade scale: the full town over ten years, the coupling-lag contract, scale within hardware, physical consistency, event coverage, the privacy test, and the non-sensor datasets. |
| **Fidelity tiers F1 to F3** | How the physics is solved. F1 and F2 are the resistance-capacitance models used here; F3 is a full building-energy simulation and is out of scope by E1's own declaration. |
| **Coupling modes C1, C2** | C1 runs the households without solving the network. C2 solves a quasi-static power flow at the coupling epoch, so the network state exists and the per-epoch cost is real. |
| **GT, OBS, META** | See above. The distinction is enforced by the schema and by a leakage test, not by where a file sits. |
| **Provenance code** | Why a value is what it is — measured, rendered, imputed, gap-filled, suppressed — carried on the value rather than inferred from its absence. |
| **Quality flag** | Whether the value should be trusted, on the same row as the value. |

---

Generated by `scripts/baile_nua/report/datasets_md.py` at 2026-10-12T12:01:59 from git `574e59f65f16`. Read-only on `v1/`.

