# Baile Nua: HRSD_Occupants Dataset Catalogue

### Synthetic occupants of an Irish town, calibrated to Cobh

**UNVALIDATED SIMULATION EVIDENCE: E1 engineering candidate**

> **v1 candidate. Not a release. Do not use for published results.**

| | |
|---|---|
| Version | v1 candidate |
| Generated | 2026-10-15T11:31:27 |
| Git HEAD | `0a56db5463afc92efa5f077ed604ef52fa9ae8cc` |
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
| Datasets declared | 32 | `schema/datasets.yaml` |
| Datasets present in v1, any run | 30 | Parquet parts on disk |
| — of which in the delivered estate-year | 25 | `v1/*/` |
| — of which in the `town14` run | 19 | `v1/*/town14/` |
| — of which in the `wp5_decade` run | 3 | `v1/*/wp5_decade/` |
| Datasets partial | 1 | rows in an evidence artefact |
| Datasets missing from v1 | 1 | absence on disk |
| Total size of `v1/` | 789.9 MB | `stat()` |

> **The `town14` run's engine-streamed datasets are not in `v1/`.** The C2 14-day full-town run writes D10, D11, D13, D16, D17, D19 and D17_aggregate, and only D17 and D17_aggregate are filed here — they are the two datasets no other run can produce, because the estate-year is C1 and D17 reads a solved power flow. The other five stay in the run root, at **`work/town4/pkg/{ground_truth,observable}/`**, where the run wrote them; D10, D11, D13, D16 and D19 are listed present above on the strength of the estate-year's own copies, which are a different slice at a different seed. Anyone wanting the town's 1,092-home versions should read the run root, not this package.

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
| [D17_aggregate](#d17_aggregate) | D17's observable view: connection register, asset ratings, feeder-head and substation measurements | OBS | present |
| [D18](#d18) | Rendered device readings with noise and gaps | OBS | present |
| [D19](#d19) | What leaves each home: aggregates, energy profile, flexibility compliance | OBS | present |
| [D25](#d25) | HRSD participants, profiles, MCV, sessions and responses in MIMIC schema 1.1 | OBS | present |
| [D27](#d27) | Supplier tariff, ToU and export rates, switches, flexibility and P2P terms, connection limits | OBS | present |
| [D28](#d28) | Recruitment, response rates, consent to sensors, dropouts, trial arms and periods | OBS | present |
| [D29](#d29) | Questionnaire answers with calibrated reporting error and non-response | OBS | present |
| [D30](#d30) | Recorded building and asset data, stale or wrong at realistic rates | OBS | present |
| [D31](#d31) | Station weather, wholesale prices, carbon intensity, system demand, flex events | OBS | present |

### Ground truth (+ observable view)

| Dataset | Title | Class | Status |
|---|---|---|---|
| [D03](#d03) | Dated building events (extension, retrofit, asset added or removed) | GT | present |
| [D17](#d17) | Feeder and transformer loading, voltages, outages | GT | present |

### Ground truth

| Dataset | Title | Class | Status |
|---|---|---|---|
| [D01](#d01) | Parcels, streets, venues, network topology | GT | present |
| [D02](#d02) | HRSD_Buildings: fabric, archetype, BER, systems, physics parameters | GT | present |
| [D04](#d04) | Appliances, heating, PV, BESS, chargers, vehicles, with owner and lifetime | GT | present |
| [D05](#d05) | HRSD_Occupants: persistent characteristics and trait vector | GT | present |
| [D06](#d06) | Who lives where, from when to when | GT | present |
| [D07](#d07) | Kin, partner, carer, friend, co-worker edges | GT | present |
| [D08](#d08) | Evolving states, slowly changing (SCD-2) | GT | present |
| [D09](#d09) | Births, deaths, moves, jobs, health states, decisions | GT | present |
| [D10](#d10) | Person activity intervals with location and co-participants | GT | present |
| [D11](#d11) | Person location intervals - the no-double-occupancy source | GT | present |
| [D12](#d12) | Origin, destination, mode, vehicle, distance | GT | missing |
| [D13](#d13) | Cycle start/end, programme, signature ID, energy | GT | present |
| [D14](#d14) | Event instances, phases, footprint, attendance | GT | present |
| [D15](#d15) | True site weather and solar geometry driving physics and behaviour | GT | present |
| [D16](#d16) | Zone temps, RH, CO2, DHW, heat delivered | GT | present |
| [D20](#d20) | Ground-truth labels for detector scoring (onset, type, persistence) | GT | present |
| [D21](#d21) | Human-readable narratives generated from D05 to D09 | GT | present |
| [D26](#d26) | Crosswalk to person_id, true traits, planted segments, propensity, gap, test settings | GT | present |

### Evidence

| Dataset | Title | Class | Status |
|---|---|---|---|
| [D22](#d22) | Appliance waveform templates and variation parameters | META | present |
| [D23](#d23) | Code and data versions, parameters, seeds, checksums | META | present |
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
| Path | `v1/ground_truth/D01_part*.parquet` (1 part) |
| Format | declared `geoparquet` ; on disk Parquet |
| Partitioning | none declared ; on disk 1 sequential parts |
| Rows | 96 |
| Size | 7.3 kB |
| Time span | — |
| Resolution | not a time series |
| Primary key | grain `feature` ; id columns on disk: `feature_id`, `feeder_id`, `estate_id` |
| Present for | estate-year (96 rows, 7.3 kB); town14 (206 rows, 8.5 kB) |
| Status | **present** |
| Leakage audit | — |
| Part hash | `cbb3fa21295d0580…` (part 0) |

**Schema** — types, null counts and ranges from the Parquet footers; descriptions and units from `schema/datasets.yaml`.

| Column | Type | Unit | Nulls | Min | Max | Declared |
|---|---|---|---|---|---|---|
| `feature_id` | string | — | no nulls | FDR-EST-047106012-00 | VEN-WORK-054 | required |
| `feature_kind` | string | — | no nulls | feeder | venue | required |
| `geometry_wkt` | string | — | no nulls | POINT EMPTY  /* feeder fr… | POINT EMPTY  /* substatio… | required |
| `venue_type` | string | — | 5 null (5.2%) | college | workplace | optional |
| `capacity` | int64 | — | 2 null (2.1%) | 15 | 25088 | optional |
| `feeder_id` | string | — | 93 null (96.9%) | FDR-EST-047106012-00 | FDR-EST-047106015-01 | optional |
| `estate_id` | string | — | 91 null (94.8%) | EST-047106012 | EST-047106015 | optional |
| `valid_from` | timestamp[ns, tz=UTC] | — | no nulls | 2022-01-01 00:00:00+00:00 | 2022-01-01 00:00:00+00:00 | required |
| `valid_to` | timestamp[ns, tz=UTC] | — | 96 null (100.0%) | — | — | optional |

<details><summary>Column descriptions, as declared</summary>

| Column | Declared description |
|---|---|
| `feature_id` | V- for venues, else synthetic key |
| `feature_kind` | parcel \| street \| venue \| feeder \| transformer \| farm |
| `venue_type` | school, shop, pub, church, GAA club, workplace |
| `capacity` | design 5.4: every venue has a capacity |

</details>

**Sample** — the first five rows of part 0, as written. Identity-bearing columns would be withheld; this dataset carries none.

| `feature_id` | `feature_kind` | `geometry_wkt` | `venue_type` | `capacity` | `feeder_id` | `estate_id` | `valid_from` | `valid_to` |
|---|---|---|---|---|---|---|---|---|
| VEN-PRIM-000 | venue | POINT EMPTY  /* small a… | primary_school | 173 | — | — | 2022-01-01 00:00:00+00:… | — |
| VEN-PRIM-001 | venue | POINT EMPTY  /* small a… | primary_school | 173 | — | — | 2022-01-01 00:00:00+00:… | — |
| VEN-PRIM-002 | venue | POINT EMPTY  /* small a… | primary_school | 173 | — | — | 2022-01-01 00:00:00+00:… | — |
| VEN-COLL-000 | venue | POINT EMPTY  /* small a… | college | 25088 | — | — | 2022-01-01 00:00:00+00:… | — |
| VEN-SECO-000 | venue | POINT EMPTY  /* small a… | secondary_school | 173 | — | — | 2022-01-01 00:00:00+00:… | — |

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
| Path | `v1/ground_truth/D02_part*.parquet` (1 part) |
| Format | declared `parquet` ; on disk Parquet |
| Partitioning | none declared ; on disk 1 sequential parts |
| Rows | 50 |
| Size | 27.2 kB |
| Time span | — |
| Resolution | not a time series |
| Primary key | grain `building x version` ; id columns on disk: `building_id`, `premises_id`, `estate_id`, `archetype_id` |
| Present for | estate-year (50 rows, 27.2 kB); town14 (1,092 rows, 154.5 kB) |
| Status | **present** |
| Leakage audit | — |
| Part hash | `94007c52b983a64a…` (part 0) |

**Schema** — types, null counts and ranges from the Parquet footers; descriptions and units from `schema/datasets.yaml`.

| Column | Type | Unit | Nulls | Min | Max | Declared |
|---|---|---|---|---|---|---|
| `building_id` | string | — | no nulls | B-000206 | B-000262 | required |
| `version` | int64 | — | no nulls | 1 | 1 | required |
| `valid_from` | timestamp[ns, tz=UTC] | — | no nulls | 2022-01-01 00:00:00+00:00 | 2022-01-01 00:00:00+00:00 | required |
| `valid_to` | timestamp[ns, tz=UTC] | — | 50 null (100.0%) | — | — | optional |
| `premises_id` | string | — | no nulls | MPRN-00B4DDA0621CC6AC64 | MPRN-FECC1C4894CC3DF0C3 | required |
| `estate_id` | string | — | no nulls | EST-047106012 | EST-047106015 | required |
| `dwelling_type` | string | — | no nulls | apartment | terraced | required |
| `build_year` | int64 | — | no nulls | 1983 | 2015 | required |
| `floor_area_m2` | double | — | no nulls | 52.71 | 211.73 | required |
| `storeys` | int64 | — | no nulls | 1 | 2 | required |
| `archetype_id` | string | — | no nulls | apartment\|1991-2000\|A3 | terraced\|2001-2010\|C3 | required |
| `ber_band` | string | — | no nulls | A1 | C3 | required |
| `ber_kwh_m2_yr` | double | — | no nulls | 0.48 | 224.75 | required |
| `heating_fuel` | string | — | no nulls | electricity | natural gas | required |
| `heating_system` | string | — | no nulls | direct electric | gas boiler | required |
| `heating_control` | string | — | no nulls | TRV + thermostat | timer + thermostat | required |
| `tenure` | string | — | no nulls | owner-occupied no mortgage | rented social | required |
| `sri_class` | string | — | 50 null (100.0%) | — | — | optional |
| `sri_score` | double | — | 50 null (100.0%) | — | — | optional |
| `rc_r_ie` | double | K/W | no nulls | 0.0011816318418368058 | 0.00843815633020259 | required |
| `rc_r_ea` | double | K/W | no nulls | 0.0027571409642858802 | 0.019689031437139376 | required |
| `rc_r_zz` | double | K/W | no nulls | 0.009345287824895972 | 0.016135543709410498 | required |
| `rc_r_inf` | double | K/W | no nulls | 0.014581808004197446 | 0.05781095350967471 | required |
| `rc_c_living` | double | J/K | no nulls | 1432447.366974181 | 5205714.814054861 | required |
| `rc_c_sleep` | double | J/K | no nulls | 853962.3755191313 | 4482211.298755904 | required |
| `rc_c_env` | double | J/K | no nulls | 13442000.355393732 | 52676876.09460275 | required |
| `rc_solar_aperture_m2` | double | — | no nulls | 3.179 | 16.807 | required |
| `rc_vol_living_m3` | double | — | no nulls | 80.75 | 308.28 | required |
| `rc_vol_sleep_m3` | double | — | no nulls | 49.34 | 258.97 | required |
| `ach_base` | double | 1/h | no nulls | 0.2732 | 0.5188 | required |
| `heat_emitter_w` | double | W *(derived)* | no nulls | 1604.0 | 9222.5 | required |
| `dhw_tank_litres` | double | — | 1 null (2.0%) | 120.0 | 240.0 | optional |
| `fidelity_tier` | string | — | no nulls | F1 | F2 | required |
| `seed` | int64 | — | no nulls | 106440751615625399 | 4437332782998339155 | required |

<details><summary>Column descriptions, as declared</summary>

| Column | Declared description |
|---|---|
| `version` | bumped by a D03 passport event |
| `premises_id` | GT side of the opaque observable key |
| `ber_band` | asset rating; operation may diverge (5.7 performance gap) |
| `heating_control` | timer \| thermostat \| TRV \| manual |
| `sri_class` | ISO 52120-1 building automation class |
| `rc_r_ie` | indoor-envelope resistance |
| `rc_r_ea` | envelope-ambient resistance |
| `rc_r_zz` | living-sleeping inter-zone resistance |
| `rc_r_inf` | infiltration path |
| `ach_base` | background infiltration |
| `heat_emitter_w` | maximum deliverable heat |

</details>

**Sample** — the first five rows of part 0, as written. Identity-bearing columns would be withheld; this dataset carries none.

| `building_id` | `version` | `valid_from` | `valid_to` | `premises_id` | `estate_id` | `dwelling_type` | `build_year` | `floor_area_m2` | `storeys` | `archetype_id` | `ber_band` | `ber_kwh_m2_yr` | `heating_fuel` | `heating_system` | `heating_control` | `tenure` | `sri_class` | `sri_score` | `rc_r_ie` | `rc_r_ea` | `rc_r_zz` | `rc_r_inf` | `rc_c_living` | `rc_c_sleep` | `rc_c_env` | `rc_solar_aperture_m2` | `rc_vol_living_m3` | `rc_vol_sleep_m3` | `ach_base` | `heat_emitter_w` | `dhw_tank_litres` | `fidelity_tier` | `seed` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B-000206 | 1 | 2022-01-01 00:00:00+00:… | — | MPRN-12648450D5BDED39DD | EST-047106012 | semi-detached | 2004 | 111.22 | 2 | semi-detached\|2001-201… | B3 | 131.98 | natural gas | gas boiler | TRV + thermostat | owner-occupied with mor… | — | — | 0.0022647583742096133 | 0.0052844362064890975 | 0.01289405466307465 | 0.02805777257136855 | 3203146.416206241 | 1801769.8591160106 | 28361192.22682609 | 7.848 | 185.07 | 104.1 | 0.3735 | 4807.8 | 120.0 | F1 | 681392230955446831 |
| B-000207 | 1 | 2022-01-01 00:00:00+00:… | — | MPRN-BD3C756F354C00E282 | EST-047106012 | apartment | 2003 | 58.44 | 1 | apartment\|2001-2010\|B2 | B2 | 106.84 | natural gas | gas boiler | timer | rented private | — | — | 0.006642839366545328 | 0.015499958521939097 | 0.01257776027335616 | 0.053489066707261536 | 1472743.9121206475 | 1157155.9309519369 | 14902765.77741131 | 3.35 | 85.09 | 66.86 | 0.3728 | 1826.3 | 150.0 | F2 | 3804317820222063980 |
| B-000210 | 1 | 2022-01-01 00:00:00+00:… | — | MPRN-34401714421FC71D21 | EST-047106012 | semi-detached | 1996 | 103.26 | 2 | semi-detached\|1991-200… | B3 | 133.28 | natural gas | gas boiler | timer | owner-occupied with mor… | — | — | 0.0021640886463832098 | 0.005049540174894156 | 0.013381559796614718 | 0.024767940384651084 | 3271410.2626765002 | 1840168.2727555311 | 28965611.700781506 | 7.286 | 171.83 | 96.66 | 0.4557 | 5119.4 | 120.0 | F2 | 2353780907890178562 |
| B-000211 | 1 | 2022-01-01 00:00:00+00:… | — | MPRN-B1500C9DF4503BF2CF | EST-047106012 | detached | 2001 | 114.43 | 2 | detached\|2001-2010\|B3 | B3 | 135.73 | natural gas | gas boiler | timer | owner-occupied with mor… | — | — | 0.001837899738216582 | 0.0042884327225053585 | 0.012712162358370692 | 0.026016297947549845 | 3295466.816003937 | 1853700.0840022143 | 29178612.433368184 | 9.083 | 190.4 | 107.1 | 0.3915 | 5767.7 | 120.0 | F1 | 227208941335089736 |
| B-000212 | 1 | 2022-01-01 00:00:00+00:… | — | MPRN-00B4DDA0621CC6AC64 | EST-047106012 | detached | 2010 | 113.68 | 2 | detached\|2001-2010\|A3 | A3 | 52.28 | natural gas | gas boiler | TRV + thermostat | owner-occupied with mor… | — | — | 0.0026239626368915504 | 0.006122579486080284 | 0.012753998066803048 | 0.029213146474345874 | 3273882.671128318 | 1841559.002509679 | 28987502.81728198 | 9.024 | 189.16 | 106.4 | 0.351 | 4248.9 | 120.0 | F1 | 1099474213054181869 |

**Joins**

- `building_id` → D02 fabric, D03 passport, D16 state, D01 geography
- `premises_id` → D18, D19, D27 to D30 (the meter-boundary identity of a home)

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
| Path | `v1/ground_truth/wp5_decade/D03_part*.parquet` (1 part) |
| Format | declared `parquet` ; on disk Parquet |
| Partitioning | none declared ; on disk 1 sequential parts |
| Rows | 45 |
| Size | 13.9 kB |
| Time span | `effective_day` 31 → 3621 (day index from the run's first day, not a date) |
| Resolution | not a time series |
| Primary key | grain `event` ; id columns on disk: `passport_event_id`, `building_id`, `life_event_id` |
| Present for | wp5_decade (45 rows, 13.9 kB) |
| Status | **present** |
| Leakage audit | — |
| Part hash | `c4ce049ee97faaba…` (part 0) |

**Schema** — types, null counts and ranges from the Parquet footers; descriptions and units from `schema/datasets.yaml`.

| Column | Type | Unit | Nulls | Min | Max | Declared |
|---|---|---|---|---|---|---|
| `passport_event_id` | string | — | no nulls | BP-B-000786-2029-der_pv | BP-B-001022-2022-extension | required |
| `building_id` | string | — | no nulls | B-000786 | B-001022 | required |
| `event_type` | string | — | no nulls | asset added | retrofit | required |
| `effective_at` | timestamp[ns, tz=UTC] | — | no nulls | 2022-02-01 00:00:00+00:00 | 2031-12-01 00:00:00+00:00 | required |
| `decided_at` | timestamp[ns, tz=UTC] | — | no nulls | 2022-01-01 00:00:00+00:00 | 2031-09-02 00:00:00+00:00 | optional |
| `from_version` | int64 | — | no nulls | 1 | 3 | required |
| `to_version` | int64 | — | no nulls | 2 | 4 | required |
| `parameters_changed.heating_control` | string | — | 35 null (77.8%) | changed | changed | leaf of `parameters_changed` |
| `parameters_changed.sri_class` | string | — | 35 null (77.8%) | changed | changed | leaf of `parameters_changed` |
| `parameters_changed.sri_score` | string | — | 35 null (77.8%) | changed | changed | leaf of `parameters_changed` |
| `parameters_changed.bess_kwh` | string | kWh *(derived)* | 42 null (93.3%) | changed | changed | leaf of `parameters_changed` |
| `parameters_changed.bess_kw` | string | kW *(derived)* | 42 null (93.3%) | changed | changed | leaf of `parameters_changed` |
| `parameters_changed.pv_kwp` | string | — | 39 null (86.7%) | changed | changed | leaf of `parameters_changed` |
| `parameters_changed.pv_azimuth_deg` | string | — | 39 null (86.7%) | changed | changed | leaf of `parameters_changed` |
| `parameters_changed.pv_tilt_deg` | string | — | 39 null (86.7%) | changed | changed | leaf of `parameters_changed` |
| `parameters_changed.floor_area_m2` | string | — | 38 null (84.4%) | changed | changed | leaf of `parameters_changed` |
| `parameters_changed.rc_c_living` | string | — | 38 null (84.4%) | changed | changed | leaf of `parameters_changed` |
| `parameters_changed.rc_vol_living_m3` | string | — | 38 null (84.4%) | changed | changed | leaf of `parameters_changed` |
| `parameters_changed.heating_system` | string | — | 38 null (84.4%) | changed | changed | leaf of `parameters_changed` |
| `parameters_changed.heating_fuel` | string | — | 38 null (84.4%) | changed | changed | leaf of `parameters_changed` |
| `parameters_changed.ber_kwh_m2_yr` | string | — | 26 null (57.8%) | changed | changed | leaf of `parameters_changed` |
| `parameters_changed.rc_r_ie` | string | — | 33 null (73.3%) | changed | changed | leaf of `parameters_changed` |
| `parameters_changed.rc_r_ea` | string | — | 33 null (73.3%) | changed | changed | leaf of `parameters_changed` |
| `parameters_changed.rc_r_inf` | string | — | 33 null (73.3%) | changed | changed | leaf of `parameters_changed` |
| `parameters_changed.ber_band` | string | — | 33 null (73.3%) | changed | changed | leaf of `parameters_changed` |
| `driver` | string | — | no nulls | WP5 ten-year life course,… | WP5 ten-year life course,… | required |
| `life_event_id` | string | — | no nulls | LE-2022-DER_BATTERY-0001 | LE-2031-RETROFIT_FABRIC-0… | optional |

A dotted name is a leaf of a struct column: the Parquet footer flattens a struct, so the file physically carries the leaves while the dataset logically carries the parent.

<details><summary>Column descriptions, as declared</summary>

| Column | Declared description |
|---|---|
| `driver` | the model and reason that fired it |

</details>

**Sample** — the first five rows of part 0, as written. Identity-bearing columns would be withheld; this dataset carries none.

| `passport_event_id` | `building_id` | `event_type` | `effective_at` | `decided_at` | `from_version` | `to_version` | `parameters_changed.heating_control` | `parameters_changed.sri_class` | `parameters_changed.sri_score` | `parameters_changed.bess_kwh` | `parameters_changed.bess_kw` | `parameters_changed.pv_kwp` | `parameters_changed.pv_azimuth_deg` | `parameters_changed.pv_tilt_deg` | `parameters_changed.floor_area_m2` | `parameters_changed.rc_c_living` | `parameters_changed.rc_vol_living_m3` | `parameters_changed.heating_system` | `parameters_changed.heating_fuel` | `parameters_changed.ber_kwh_m2_yr` | `parameters_changed.rc_r_ie` | `parameters_changed.rc_r_ea` | `parameters_changed.rc_r_inf` | `parameters_changed.ber_band` | `driver` | `life_event_id` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| BP-B-001019-2022-der_sm… | B-001019 | asset added | 2022-02-01 00:00:00+00:… | 2022-01-01 00:00:00+00:… | 1 | 2 | changed | changed | changed | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | WP5 ten-year life cours… | LE-2022-DER_SMART_CONTR… |
| BP-B-000856-2022-der_ba… | B-000856 | asset added | 2022-02-04 00:00:00+00:… | 2022-01-01 00:00:00+00:… | 1 | 2 | — | — | — | changed | changed | — | — | — | — | — | — | — | — | — | — | — | — | — | WP5 ten-year life cours… | LE-2022-DER_BATTERY-0001 |
| BP-B-000862-2022-der_pv | B-000862 | asset added | 2022-02-15 00:00:00+00:… | 2022-01-01 00:00:00+00:… | 1 | 2 | — | — | — | — | — | changed | changed | changed | — | — | — | — | — | — | — | — | — | — | WP5 ten-year life cours… | LE-2022-DER_PV-0001 |
| BP-B-000866-2022-extens… | B-000866 | extension | 2022-05-15 00:00:00+00:… | 2022-02-14 00:00:00+00:… | 1 | 2 | — | — | — | — | — | — | — | — | changed | changed | changed | — | — | — | — | — | — | — | WP5 ten-year life cours… | LE-2022-EXTENSION-0001 |
| BP-B-000867-2022-der_sm… | B-000867 | asset added | 2022-05-28 00:00:00+00:… | 2022-02-27 00:00:00+00:… | 1 | 2 | changed | changed | changed | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | WP5 ten-year life cours… | LE-2022-DER_SMART_CONTR… |

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
| Path | `v1/ground_truth/D04_part*.parquet` (1 part) |
| Format | declared `parquet` ; on disk Parquet |
| Partitioning | none declared ; on disk 1 sequential parts |
| Rows | 771 |
| Size | 23.4 kB |
| Time span | — |
| Resolution | not a time series |
| Primary key | grain `asset x version` ; id columns on disk: `asset_id`, `building_id`, `owner_person_id`, `signature_id` |
| Present for | estate-year (771 rows, 23.4 kB); town14 (16,894 rows, 244.1 kB) |
| Status | **present** |
| Leakage audit | — |
| Part hash | `b4dc9de019433395…` (part 0) |

**Schema** — types, null counts and ranges from the Parquet footers; descriptions and units from `schema/datasets.yaml`.

| Column | Type | Unit | Nulls | Min | Max | Declared |
|---|---|---|---|---|---|---|
| `asset_id` | string | — | no nulls | A-000206-00 | A-000262-IMM | required |
| `version` | int64 | — | no nulls | 1 | 1 | required |
| `valid_from` | timestamp[ns, tz=UTC] | — | no nulls | 2022-01-01 00:00:00+00:00 | 2022-01-01 00:00:00+00:00 | required |
| `valid_to` | timestamp[ns, tz=UTC] | — | 771 null (100.0%) | — | — | optional |
| `building_id` | string | — | no nulls | B-000206 | B-000262 | optional |
| `owner_person_id` | string | — | 771 null (100.0%) | — | — | optional |
| `asset_class` | string | — | no nulls | appliance | vehicle | required |
| `asset_type` | string | — | no nulls | battery_electric | washing_machine | required |
| `make_model_synth` | string | — | 771 null (100.0%) | — | — | required |
| `rated_power_w` | double | W *(derived)* | 611 null (79.2%) | 1604.0276080801998 | 12000.0 | optional |
| `capacity` | double | Wh for BESS, kWp for PV, litres for tanks | 710 null (92.1%) | 3.459720080089999 | 58000.0 | optional |
| `efficiency` | double | — | 720 null (93.4%) | 1.0 | 1.0 | optional |
| `install_date` | date32[day] | — | 167 null (21.7%) | 1996-12-31 | 2021-11-25 | required |
| `age_years_at_t0` | double | — | 167 null (21.7%) | 0.1 | 25.0 | required |
| `failure_hazard_scale` | double | — | 771 null (100.0%) | — | — | required |
| `signature_id` | string | — | 167 null (21.7%) | SIG-DISH-ECO | SIG-WASH-ECO40 | optional |
| `device_mode` | string | — | no nulls | rendered | rendered | required |
| `pv_azimuth_deg` | double | — | 766 null (99.4%) | 152.01776350698438 | 193.49148862147223 | optional |
| `pv_tilt_deg` | double | — | 766 null (99.4%) | 28.453890994817062 | 39.33662560718766 | optional |
| `seed` | int64 | — | no nulls | 20261008 | 20261008 | required |

<details><summary>Column descriptions, as declared</summary>

| Column | Declared description |
|---|---|
| `owner_person_id` | vehicles and personal devices |
| `asset_class` | appliance \| heating \| pv \| bess \| charger \| vehicle |
| `asset_type` | kettle, washer, heat_pump, immersion, ... |
| `make_model_synth` | synthetic model label, drives signature variation |
| `failure_hazard_scale` | Weibull scale, drives 5.3 appliance failure |
| `signature_id` | -> D22 |
| `device_mode` | 5.6 rendered vs live |

</details>

**Sample** — the first five rows of part 0, as written. Identity-bearing columns would be withheld; this dataset carries none.

| `asset_id` | `version` | `valid_from` | `valid_to` | `building_id` | `owner_person_id` | `asset_class` | `asset_type` | `make_model_synth` | `rated_power_w` | `capacity` | `efficiency` | `install_date` | `age_years_at_t0` | `failure_hazard_scale` | `signature_id` | `device_mode` | `pv_azimuth_deg` | `pv_tilt_deg` | `seed` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A-000206-00 | 1 | 2022-01-01 00:00:00+00:… | — | B-000206 | — | appliance | dishwasher | — | — | — | — | 2014-10-27 | 7.181111903753646 | — | SIG-DISH-ECO | rendered | — | — | 20261008 |
| A-000206-02 | 1 | 2022-01-01 00:00:00+00:… | — | B-000206 | — | appliance | extractor_fan | — | — | — | — | 2017-11-09 | 4.14358649878957 | — | SIG-EXTRACT | rendered | — | — | 20261008 |
| A-000206-03 | 1 | 2022-01-01 00:00:00+00:… | — | B-000206 | — | appliance | fridge_freezer | — | — | — | — | 2018-05-24 | 3.6071343361473867 | — | SIG-FRIDGE | rendered | — | — | 20261008 |
| A-000206-04 | 1 | 2022-01-01 00:00:00+00:… | — | B-000206 | — | appliance | hob | — | — | — | — | 2007-04-08 | 14.732872703431685 | — | SIG-HOB | rendered | — | — | 20261008 |
| A-000206-05 | 1 | 2022-01-01 00:00:00+00:… | — | B-000206 | — | appliance | kettle | — | — | — | — | 2018-10-15 | 3.21354983037987 | — | SIG-KETTLE | rendered | — | — | 20261008 |

**Joins**

- `building_id` → D02 fabric, D03 passport, D16 state, D01 geography
- `signature_id` → D22 signature library

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
| Path | `v1/ground_truth/D05_part*.parquet` (1 part) |
| Format | declared `parquet` ; on disk Parquet |
| Partitioning | none declared ; on disk 1 sequential parts |
| Rows | 147 |
| Size | 58.1 kB |
| Time span | — |
| Resolution | not a time series |
| Primary key | grain `person` ; id columns on disk: `person_id` |
| Present for | estate-year (147 rows, 58.1 kB); town14 (2,917 rows, 681.2 kB) |
| Status | **present** |
| Leakage audit | — |
| Part hash | `eb546738f61553ba…` (part 0) |

**Schema** — types, null counts and ranges from the Parquet footers; descriptions and units from `schema/datasets.yaml`.

| Column | Type | Unit | Nulls | Min | Max | Declared |
|---|---|---|---|---|---|---|
| `person_id` | string | — | no nulls | P-000625 | P-000795 | required |
| `given_name` | string | — | no nulls | Aidan | Zofia | required |
| `family_name` | string | — | no nulls | Ali | Wiśniewski | required |
| `birth_date` | date32[day] | — | no nulls | 1952-12-29 | 2021-05-24 | required |
| `death_date` | timestamp[ns] | — | 147 null (100.0%) | — | — | optional |
| `sex` | string | — | no nulls | F | M | required |
| `country_of_birth` | string | — | no nulls | EU | XX | required |
| `nationality` | string | — | no nulls | EU | XX | required |
| `ethnicity_census` | string | — | no nulls | Asian or Asian Irish | White Irish Traveller | required |
| `first_language` | string | — | no nulls | en | pl | required |
| `other_languages.list.element` | BYTE_ARRAY | — | 119 null (81.0%) | en | en | leaf of `other_languages` |
| `years_in_ireland` | double | — | 119 null (81.0%) | 2.0 | 42.0 | optional |
| `education_level` | string | — | no nulls | ISCED 0 | ISCED 7 | required |
| `trans` | double | z-score | no nulls | -2.225338814482659 | 1.3411055251304105 | required |
| `community` | double | z-score | no nulls | -1.605647167285375 | 1.0185969146276597 | required |
| `env` | double | z-score | no nulls | -2.6095535503014187 | 1.3294258607157388 | required |
| `autonomy` | double | z-score | no nulls | -1.0416161293510129 | 2.0736078653796466 | required |
| `comfort` | double | z-score | no nulls | -1.6835753164140466 | 1.4200525848773202 | required |
| `conditional` | double | z-score | no nulls | -1.5028242657326336 | 1.812201794941958 | required |
| `privacy` | double | z-score | no nulls | -1.8855550350878092 | 1.4507722397667062 | required |
| `instTrust` | double | z-score | no nulls | -1.290086600678597 | 1.1094488864806167 | required |
| `idvZ` | double | z-score | no nulls | -1.0422708470976487 | 2.4536289661139032 | required |
| `satisficer` | int64 | — | no nulls | 0 | 1 | required |
| `stated_gap` | double | 0 to 1 | no nulls | -0.0 | 0.45542413703659246 | required |
| `lambda_self` | double | — | no nulls | 0.090924 | 0.85792 | required |
| `lambda_coop` | double | — | no nulls | 0.093006 | 0.6808730000000001 | required |
| `lambda_altru` | double | — | no nulls | 0.014465 | 0.7717669999999999 | required |
| `big5_o` | double | z-score | no nulls | -2.5890989237199626 | 2.0064817575084604 | required |
| `big5_c` | double | z-score | no nulls | -3.3151100701756184 | 2.233265342549568 | required |
| `big5_e` | double | z-score | no nulls | -2.7089635351619368 | 2.6415444795334126 | required |
| `big5_a` | double | z-score | no nulls | -3.5294961412974786 | 2.780262201108231 | required |
| `big5_n` | double | z-score | no nulls | -2.3599102957379703 | 3.638506503797639 | required |
| `chronotype` | double | hours | no nulls | -2.1971175138160985 | 3.0 | required |
| `habit_strength` | double | 0 to 1 | no nulls | 0.05 | 0.9473989780209173 | required |
| `lapse_rate` | double | 0 to 1 | no nulls | 0.018376203568684857 | 0.19279214526891497 | required |
| `attention` | double | 0 to 1 | no nulls | 0.11636555143924121 | 0.8501681581542293 | required |
| `response_propensity` | double | 0 to 1 | no nulls | 0.2309020510922099 | 0.8006044641880812 | required |
| `mcv_latent.list.element` | DOUBLE | — | no nulls | 1.0 | 5.0 | leaf of `mcv_latent` |
| `synthetic` | bool | — | no nulls | True | True | required |
| `seed` | int64 | — | no nulls | 13454800804242536 | 4610129665842562699 | required |
| `pool` | string | — | no nulls | BN-panel | BN-panel | optional |

A dotted name is a leaf of a struct column: the Parquet footer flattens a struct, so the file physically carries the leaves while the dataset logically carries the parent.

<details><summary>Column descriptions, as declared</summary>

| Column | Declared description |
|---|---|
| `given_name` | synthetic, uniqueness-checked |
| `death_date` | set by D09 |
| `country_of_birth` | ISO 3166-1 alpha-2 |
| `nationality` | ISO 3166-1 alpha-2 |
| `ethnicity_census` | CSO category; synthesis and stereotype-guard only |
| `first_language` | ISO 639-1 |
| `years_in_ireland` | drives idvZ acculturation shrinkage (5.13) |
| `education_level` | ISCED; evolves via D08 while in education |
| `idvZ` | cultural individualism from origin country, shrunk by acculturation |
| `satisficer` | careless-responder flag |
| `stated_gap` | stated vs revealed willingness (5.13) |
| `lambda_self` | lambda_1; the three sum to 1 |
| `lambda_coop` | lambda_2 |
| `lambda_altru` | lambda_3 |
| `chronotype` | shifts the sleep window |
| `response_propensity` | 5.14 MIMIC opt-in propensity |
| `mcv_latent` | 10 MCV item latents, MIMIC makeMcv mapping |
| `synthetic` | R27/K12: every record carries the synthetic flag |
| `pool` | BN-panel for simulated townspeople; HRSD-pool for the unlinked extended pool |

</details>

**Sample** — the first five rows of part 0, as written. Identity-bearing columns would be withheld; this dataset carries none.

| `person_id` | `given_name` | `family_name` | `birth_date` | `death_date` | `sex` | `country_of_birth` | `nationality` | `ethnicity_census` | `first_language` | `other_languages` | `years_in_ireland` | `education_level` | `trans` | `community` | `env` | `autonomy` | `comfort` | `conditional` | `privacy` | `instTrust` | `idvZ` | `satisficer` | `stated_gap` | `lambda_self` | `lambda_coop` | `lambda_altru` | `big5_o` | `big5_c` | `big5_e` | `big5_a` | `big5_n` | `chronotype` | `habit_strength` | `lapse_rate` | `attention` | `response_propensity` | `mcv_latent` | `synthetic` | `seed` | `pool` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P-000625 | withheld | withheld | withheld | — | M | IE | IE | White Irish | en | — | — | ISCED 2 | -0.5100176088912322 | 0.8872656269335117 | -0.5996114480224405 | -0.4430269391256851 | 0.026999988774989298 | 0.10191852338110592 | 0.2360605333978409 | 0.532740779765498 | 0.24026871770016212 | 0 | 0.2624902424481779 | 0.360484 | 0.502502 | 0.137014 | 0.2698172725621182 | 0.3641210667956818 | -0.2858487955440986 | -1.486275044467419 | 0.2713957730859106 | -0.8904547948198677 | 0.6434471520306614 | 0.09833493519154242 | 0.7634789221414271 | 0.35503627774260693 | [1.0, 4.0, 2.0, 3.0, 4.… | True | 1839910485623800108 | BN-panel |
| P-000626 | withheld | withheld | withheld | — | F | IE | IE | Other White | en | — | — | ISCED 3 | -0.08091739742326773 | 0.6014659839426781 | -0.22572900491095765 | 0.5135867332799158 | 0.4101728539043335 | 0.5597224655387065 | -0.028126756759284437 | -0.260287647699705 | -0.20891914258793176 | 0 | 0.3690751719384866 | 0.326487 | 0.4565499999999999 | 0.216963 | 1.01799040299227 | -0.06825351351856887 | 1.4576984213693214 | 0.31889676485308177 | -1.252755790431659 | 1.4668943878808491 | 0.763226744397628 | 0.12793014693936147 | 0.6486172349795455 | 0.47568098164085637 | [3.0, 3.0, 4.0, 4.0, 4.… | True | 443166849308066425 | BN-panel |
| P-000627 | withheld | withheld | withheld | — | F | IE | IE | White Irish | en | — | — | ISCED 1 | 0.5239508614386796 | -1.2101872102759235 | -0.015438289681987988 | 0.9761592022884056 | 0.14327870947492938 | 0.03383370743003852 | -0.3793854830236854 | -1.290086600678597 | 0.0729248608316222 | 0 | 0.3165348564317117 | 0.28748 | 0.158682 | 0.5538379999999999 | -0.44075423257015706 | -0.30277096604737075 | -0.6888053442471674 | -0.07566105121003122 | 0.12592890495224499 | 1.2674188140582112 | 0.20582244732203048 | 0.10449780411219056 | 0.3839251216657419 | 0.5708154819149328 | [3.0, 2.0, 3.0, 3.0, 1.… | True | 4544629898078058353 | BN-panel |
| P-000628 | withheld | withheld | withheld | — | M | IE | IE | White Irish | en | — | — | ISCED 1 | -0.5744450879333841 | -0.951759795670206 | -1.9003994824284753 | -0.34074757851110704 | -0.4088211202359296 | -0.013272276142658135 | -1.8855550350878092 | -0.8275748380904039 | 1.571763513199803 | 0 | 0.2203936520336044 | 0.5877800000000001 | 0.261356 | 0.150864 | -1.0395056764739812 | -3.3151100701756184 | -1.315760465833556 | -0.8043460440843384 | -0.6077544063711516 | 1.3370549801664098 | 0.5769974188609399 | 0.12262281083776391 | 0.20258400876125132 | 0.5337233921897112 | [2.0, 2.0, 2.0, 3.0, 2.… | True | 113818451499049183 | BN-panel |
| P-000629 | withheld | withheld | withheld | — | M | IE | IE | White Irish | en | — | — | ISCED 1 | -2.209257068980087 | -0.8263653667783175 | -2.0764399827699003 | 0.8901633067523169 | 0.18820210236125756 | 1.7041799114588048 | -0.35071768595993635 | -0.7481737566183028 | 1.9566893027364047 | 0 | 0.0 | 0.8038080000000001 | 0.181727 | 0.014465 | 0.6873197044621774 | 1.0253368372687628 | 1.9370415171837148 | -0.2854353719198725 | -0.6569820893854663 | 1.8947562693326814 | 0.6489996056424052 | 0.09630534662527698 | 0.5876338064535536 | 0.2657026324098337 | [1.0, 4.0, 1.0, 1.0, 3.… | True | 2327633312901983738 | BN-panel |

**Joins**

- `person_id` → D05 persons, D08 states, D09 events, D10 activities

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
| Path | `v1/ground_truth/D06_part*.parquet` (1 part) |
| Format | declared `parquet` ; on disk Parquet |
| Partitioning | none declared ; on disk 1 sequential parts |
| Rows | 147 |
| Size | 6.6 kB |
| Time span | — |
| Resolution | not a time series |
| Primary key | grain `interval` ; id columns on disk: `membership_id`, `person_id`, `household_id`, `building_id` |
| Present for | estate-year (147 rows, 6.6 kB); town14 (2,917 rows, 25.5 kB) |
| Status | **present** |
| Leakage audit | — |
| Part hash | `8822481394ae3601…` (part 0) |

**Schema** — types, null counts and ranges from the Parquet footers; descriptions and units from `schema/datasets.yaml`.

| Column | Type | Unit | Nulls | Min | Max | Declared |
|---|---|---|---|---|---|---|
| `membership_id` | string | — | no nulls | M-P-000625-0001 | M-P-000795-0001 | required |
| `person_id` | string | — | no nulls | P-000625 | P-000795 | required |
| `household_id` | string | — | no nulls | H-000206 | H-000262 | required |
| `building_id` | string | — | no nulls | B-000206 | B-000262 | required |
| `valid_from` | timestamp[ns, tz=UTC] | — | no nulls | 2022-01-01 00:00:00+00:00 | 2022-01-01 00:00:00+00:00 | required |
| `valid_to` | timestamp[ns, tz=UTC] | — | 147 null (100.0%) | — | — | optional |
| `role` | string | — | no nulls | child | partner | required |
| `reason_in` | string | — | no nulls | t0 | t0 | optional |
| `reason_out` | string | — | 147 null (100.0%) | — | — | optional |

<details><summary>Column descriptions, as declared</summary>

| Column | Declared description |
|---|---|
| `reason_in` | t0 \| birth \| move in \| partnering \| returning |

</details>

**Sample** — the first five rows of part 0, as written. Identity-bearing columns would be withheld; this dataset carries none.

| `membership_id` | `person_id` | `household_id` | `building_id` | `valid_from` | `valid_to` | `role` | `reason_in` | `reason_out` |
|---|---|---|---|---|---|---|---|---|
| M-P-000625-0001 | P-000625 | H-000206 | B-000206 | 2022-01-01 00:00:00+00:… | — | head | t0 | — |
| M-P-000626-0001 | P-000626 | H-000206 | B-000206 | 2022-01-01 00:00:00+00:… | — | partner | t0 | — |
| M-P-000627-0001 | P-000627 | H-000206 | B-000206 | 2022-01-01 00:00:00+00:… | — | child | t0 | — |
| M-P-000628-0001 | P-000628 | H-000206 | B-000206 | 2022-01-01 00:00:00+00:… | — | child | t0 | — |
| M-P-000629-0001 | P-000629 | H-000206 | B-000206 | 2022-01-01 00:00:00+00:… | — | child | t0 | — |

**Joins**

- `building_id` → D02 fabric, D03 passport, D16 state, D01 geography
- `household_id` → D06 membership, D04 assets
- `person_id` → D05 persons, D08 states, D09 events, D10 activities

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
| Path | `v1/ground_truth/D07_part*.parquet` (1 part) |
| Format | declared `parquet` ; on disk Parquet |
| Partitioning | none declared ; on disk 1 sequential parts |
| Rows | 205 |
| Size | 5.8 kB |
| Time span | — |
| Resolution | not a time series |
| Primary key | grain `edge x interval` ; id columns on disk: `edge_id` |
| Present for | estate-year (205 rows, 5.8 kB); town14 (3,022 rows, 25.2 kB) |
| Status | **present** |
| Leakage audit | — |
| Part hash | `84cf5edab9404c73…` (part 0) |

**Schema** — types, null counts and ranges from the Parquet footers; descriptions and units from `schema/datasets.yaml`.

| Column | Type | Unit | Nulls | Min | Max | Declared |
|---|---|---|---|---|---|---|
| `edge_id` | string | — | no nulls | E-H-000206-001 | E-H-000256-002 | required |
| `person_a` | string | — | no nulls | P-000625 | P-000787 | required |
| `person_b` | string | — | no nulls | P-000626 | P-000788 | required |
| `edge_type` | string | — | no nulls | carer_of | sibling | required |
| `valid_from` | timestamp[ns, tz=UTC] | — | no nulls | 2022-01-01 00:00:00+00:00 | 2022-01-01 00:00:00+00:00 | required |
| `valid_to` | timestamp[ns, tz=UTC] | — | 205 null (100.0%) | — | — | optional |
| `strength` | double | 0 to 1 | no nulls | 0.7 | 0.95 | optional |

<details><summary>Column descriptions, as declared</summary>

| Column | Declared description |
|---|---|
| `edge_type` | partner \| parent_of \| sibling \| carer_of \| friend \| co_worker \| neighbour |
| `strength` | drives 5.3 influence |

</details>

**Sample** — the first five rows of part 0, as written. Identity-bearing columns would be withheld; this dataset carries none.

| `edge_id` | `person_a` | `person_b` | `edge_type` | `valid_from` | `valid_to` | `strength` |
|---|---|---|---|---|---|---|
| E-H-000206-001 | P-000625 | P-000626 | partner | 2022-01-01 00:00:00+00:… | — | 0.9 |
| E-H-000206-002 | P-000625 | P-000627 | parent_of | 2022-01-01 00:00:00+00:… | — | 0.95 |
| E-H-000206-003 | P-000625 | P-000627 | carer_of | 2022-01-01 00:00:00+00:… | — | 0.9 |
| E-H-000206-004 | P-000625 | P-000628 | parent_of | 2022-01-01 00:00:00+00:… | — | 0.95 |
| E-H-000206-005 | P-000625 | P-000628 | carer_of | 2022-01-01 00:00:00+00:… | — | 0.9 |

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
| Path | `v1/ground_truth/D08_part*.parquet` (1 part) |
| Format | declared `parquet` ; on disk Parquet |
| Partitioning | none declared ; on disk 1 sequential parts |
| Rows | 147 |
| Size | 14.8 kB |
| Time span | — |
| Resolution | not a time series |
| Primary key | grain `interval` ; id columns on disk: `state_id`, `person_id`, `household_id`, `workplace_venue_id`, `school_venue_id` |
| Present for | estate-year (147 rows, 14.8 kB); town14 (2,917 rows, 39.8 kB) |
| Status | **present** |
| Leakage audit | — |
| Part hash | `a999782aefd49752…` (part 0) |

**Schema** — types, null counts and ranges from the Parquet footers; descriptions and units from `schema/datasets.yaml`.

| Column | Type | Unit | Nulls | Min | Max | Declared |
|---|---|---|---|---|---|---|
| `state_id` | string | — | no nulls | S-P-000625-0001 | S-P-000795-0001 | required |
| `person_id` | string | — | no nulls | P-000625 | P-000795 | required |
| `valid_from` | timestamp[ns, tz=UTC] | — | no nulls | 2022-01-01 00:00:00+00:00 | 2022-01-01 00:00:00+00:00 | required |
| `valid_to` | timestamp[ns, tz=UTC] | — | 147 null (100.0%) | — | — | optional |
| `household_id` | string | — | no nulls | H-000206 | H-000262 | required |
| `role` | string | — | no nulls | child | partner | required |
| `econ_status` | string | — | no nulls | employed | unemployed | required |
| `occupation_soc` | string | — | 66 null (44.9%) | administrative and secret… | skilled trades | optional |
| `occupation_isco08` | string | — | 147 null (100.0%) | — | — | optional |
| `industry_nace` | string | — | 66 null (44.9%) | building and construction | transport and communicati… | optional |
| `workplace_venue_id` | string | — | 147 null (100.0%) | — | — | optional |
| `work_pattern` | string | — | no nulls | fixed day | shift | required |
| `remote_share` | double | 0 to 1 of working days | no nulls | -0.0 | 0.9367875188697771 | required |
| `school_venue_id` | string | — | 147 null (100.0%) | — | — | optional |
| `school_year` | int64 | — | 100 null (68.0%) | 1 | 13 | optional |
| `health_state` | string | — | no nulls | well | well | required |
| `caring_load` | string | — | no nulls | child | none | required |
| `caring_hours_week` | double | — | no nulls | -0.0 | 0.0 | required |
| `decision_authority` | double | 0 to 1 within household | no nulls | -0.0 | 1.0 | required |
| `vehicle_access` | string | — | no nulls | none | shared | required |
| `income_quintile` | int64 | — | no nulls | 1 | 5 | required |

<details><summary>Column descriptions, as declared</summary>

| Column | Declared description |
|---|---|
| `occupation_soc` | SOC 2010 |
| `occupation_isco08` | mapped for MIMIC compatibility (5.13) |
| `industry_nace` | NACE rev2 |
| `health_state` | U09: generic functional states only, never diagnoses |

</details>

**Sample** — the first five rows of part 0, as written. Identity-bearing columns would be withheld; this dataset carries none.

| `state_id` | `person_id` | `valid_from` | `valid_to` | `household_id` | `role` | `econ_status` | `occupation_soc` | `occupation_isco08` | `industry_nace` | `workplace_venue_id` | `work_pattern` | `remote_share` | `school_venue_id` | `school_year` | `health_state` | `caring_load` | `caring_hours_week` | `decision_authority` | `vehicle_access` | `income_quintile` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S-P-000625-0001 | P-000625 | 2022-01-01 00:00:00+00:… | — | H-000206 | head | employed | associate professional … | — | professional services | — | fixed day | 0.0 | — | — | well | child | 0.0 | 0.3333333333333333 | none | 5 |
| S-P-000626-0001 | P-000626 | 2022-01-01 00:00:00+00:… | — | H-000206 | partner | employed | professional | — | transport and communica… | — | part-time | 0.0 | — | — | well | child | 0.0 | 0.3333333333333333 | shared | 5 |
| S-P-000627-0001 | P-000627 | 2022-01-01 00:00:00+00:… | — | H-000206 | child | student | — | — | — | — | none | 0.0 | — | 7 | well | none | 0.0 | 0.0 | none | 5 |
| S-P-000628-0001 | P-000628 | 2022-01-01 00:00:00+00:… | — | H-000206 | child | student | — | — | — | — | none | 0.0 | — | 7 | well | none | 0.0 | 0.0 | none | 5 |
| S-P-000629-0001 | P-000629 | 2022-01-01 00:00:00+00:… | — | H-000206 | child | student | — | — | — | — | none | 0.0 | — | 9 | well | none | 0.0 | 0.0 | none | 5 |

**Joins**

- `household_id` → D06 membership, D04 assets
- `person_id` → D05 persons, D08 states, D09 events, D10 activities

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
| Path | `v1/ground_truth/wp5_decade/D09_part*.parquet` (1 part) |
| Format | declared `parquet` ; on disk Parquet |
| Partitioning | none declared ; on disk 1 sequential parts |
| Rows | 250 |
| Size | 18.1 kB |
| Time span | `effective_day` 17 → 3625 (day index from the run's first day, not a date) |
| Resolution | not a time series |
| Primary key | grain `event` ; id columns on disk: `event_id`, `household_id`, `building_id` |
| Present for | wp5_decade (250 rows, 18.1 kB) |
| Status | **present** |
| Leakage audit | — |
| Part hash | `a118455c40680bc7…` (part 0) |

**Schema** — types, null counts and ranges from the Parquet footers; descriptions and units from `schema/datasets.yaml`.

| Column | Type | Unit | Nulls | Min | Max | Declared |
|---|---|---|---|---|---|---|
| `event_id` | string | — | no nulls | LE-2022-BIRTH-0001 | LE-H-000843-MARY-MOVEIN | required |
| `event_type` | string | — | no nulls | DER decision | separation | required |
| `effective_at` | timestamp[ns, tz=UTC] | — | no nulls | 2022-01-18 00:00:00+00:00 | 2031-12-05 00:00:00+00:00 | required |
| `decided_at` | timestamp[ns, tz=UTC] | — | 204 null (81.6%) | 2022-01-01 00:00:00+00:00 | 2031-09-02 00:00:00+00:00 | optional |
| `persons.list.element` | BYTE_ARRAY | — | 47 null (18.8%) | P-002158 | P-WP5-00100 | leaf of `persons` |
| `household_id` | string | — | no nulls | H-000786 | HH-WP5-00034 | optional |
| `building_id` | string | — | no nulls | B-000786 | B-001023 | optional |
| `cause` | string | — | no nulls | age-specific fertility, m… | vacancy chain refill, hol… | required |
| `observable_effects.home_hours` | string | — | 224 null (89.6%) | more hours at home | more hours at home | leaf of `observable_effects` |
| `observable_effects.setpoint` | string | — | 224 null (89.6%) | higher for longer | higher for longer | leaf of `observable_effects` |
| `observable_effects.occupancy` | string | — | 146 null (58.4%) | 1 occupant becomes 5 | the dwelling is occupied … | leaf of `observable_effects` |
| `observable_effects.building` | string | — | 205 null (82.0%) | der_battery in place | retrofit_heat_pump in pla… | leaf of `observable_effects` |
| `observable_effects.hot_water` | string | — | 249 null (99.6%) | shower and hot-water draw… | shower and hot-water draw… | leaf of `observable_effects` |
| `observable_effects.laundry` | string | — | 249 null (99.6%) | washer and dryer cycles r… | washer and dryer cycles r… | leaf of `observable_effects` |
| `observable_effects.evening_load` | string | — | 249 null (99.6%) | cooking and screen load r… | cooking and screen load r… | leaf of `observable_effects` |
| `observable_effects.weekday_daytime` | string | — | 174 null (69.6%) | away during working hours | the house is no longer em… | leaf of `observable_effects` |
| `observable_effects.ev` | string | — | 249 null (99.6%) | Mary's EV pattern (unplug… | Mary's EV pattern (unplug… | leaf of `observable_effects` |

A dotted name is a leaf of a struct column: the Parquet footer flattens a struct, so the file physically carries the leaves while the dataset logically carries the parent.

<details><summary>Column descriptions, as declared</summary>

| Column | Declared description |
|---|---|
| `decided_at` | lead time for decisions with one |
| `cause` | the model and driver that fired |
| `observable_effects` | expected signal changes, for D20 |

</details>

**Sample** — the first five rows of part 0, as written. Identity-bearing columns would be withheld; this dataset carries none.

| `event_id` | `event_type` | `effective_at` | `decided_at` | `persons` | `household_id` | `building_id` | `cause` | `observable_effects.home_hours` | `observable_effects.setpoint` | `observable_effects.occupancy` | `observable_effects.building` | `observable_effects.hot_water` | `observable_effects.laundry` | `observable_effects.evening_load` | `observable_effects.weekday_daytime` | `observable_effects.ev` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| LE-2022-HEALTH_STATE_ON… | health change | 2022-01-18 00:00:00+00:… | — | ['P-002317'] | H-000854 | B-000854 | chronic health-state on… | more hours at home | higher for longer | — | — | — | — | — | — | — |
| LE-2022-MOVE_OUT-0001 | move out | 2022-01-20 00:00:00+00:… | — | ['P-002289', 'P-002290'… | H-000848 | B-000848 | gross household out-mov… | — | — | the dwelling becomes va… | — | — | — | — | — | — |
| LE-2022-DER_SMART_CONTR… | DER decision | 2022-02-01 00:00:00+00:… | 2022-01-01 00:00:00+00:… | [] | H-001019 | B-001019 | der_smart_controls adop… | — | — | — | der_smart_controls in p… | — | — | — | — | — |
| LE-2022-DER_BATTERY-0001 | DER decision | 2022-02-04 00:00:00+00:… | 2022-01-01 00:00:00+00:… | [] | H-000856 | B-000856 | der_battery adopted, [A… | — | — | — | der_battery in place | — | — | — | — | — |
| LE-2022-DER_PV-0001 | DER decision | 2022-02-15 00:00:00+00:… | 2022-01-01 00:00:00+00:… | [] | H-000862 | B-000862 | der_pv adopted, [A] A-2… | — | — | — | der_pv in place | — | — | — | — | — |

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
| Path | `v1/ground_truth/D10_part*.parquet` (13 parts) |
| Format | declared `parquet` ; on disk Parquet |
| Partitioning | by year, month ; on disk 13 sequential parts |
| Rows | 1,431,181 |
| Size | 13.5 MB |
| Time span | — |
| Resolution | not a time series |
| Primary key | grain `interval` ; id columns on disk: `activity_id`, `person_id`, `location_id` |
| Present for | estate-year (1,431,181 rows, 13.5 MB) |
| Status | **present** |
| Leakage audit | — |
| Part hash | `ef05ea84edc29b0a…` (part 0) |

**Schema** — types, null counts and ranges from the Parquet footers; descriptions and units from `schema/datasets.yaml`.

| Column | Type | Unit | Nulls | Min | Max | Declared |
|---|---|---|---|---|---|---|
| `activity_id` | string | — | no nulls | AC-00000-000000 | AC-00364-004796 | required |
| `person_id` | string | — | no nulls | P-000625 | P-000795 | required |
| `start` | timestamp[ns, tz=UTC] | — | no nulls | 2022-01-01 00:00:00+00:00 | 2022-12-31 23:57:00+00:00 | required |
| `end` | timestamp[ns, tz=UTC] | — | no nulls | 2022-01-01 06:51:00+00:00 | 2022-12-31 23:59:00+00:00 | required |
| `activity_code` | string | — | no nulls | adult_care | work_at_workplace | required |
| `hetus_code` | string | — | no nulls | AC01 | AC9A+AC913 | required |
| `location_id` | string | — | 344,400 null (24.1%) | B-000206 | B-000262 | optional |
| `zone` | string | — | no nulls | bathroom | utility | required |
| `joint_with.list.element` | BYTE_ARRAY | — | 1,374,431 null (96.0%) | eating_main | tv_screens | leaf of `joint_with` |
| `trigger` | string | — | no nulls | disruption | routine | required |
| `deliberated` | bool | — | no nulls | False | True | required |

A dotted name is a leaf of a struct column: the Parquet footer flattens a struct, so the file physically carries the leaves while the dataset logically carries the parent.

<details><summary>Column descriptions, as declared</summary>

| Column | Declared description |
|---|---|
| `start` | 1 s precision |
| `activity_code` | ~30 codes, mapped to HETUS |
| `hetus_code` | the HETUS aggregate this maps to |
| `deliberated` | true if a decision process ran (5.3 bounded rationality) |

</details>

**Sample** — the first five rows of part 0, as written. Identity-bearing columns would be withheld; this dataset carries none.

| `activity_id` | `person_id` | `start` | `end` | `activity_code` | `hetus_code` | `location_id` | `zone` | `joint_with` | `trigger` | `deliberated` |
|---|---|---|---|---|---|---|---|---|---|---|
| AC-00000-000000 | P-000625 | 2022-01-01 00:00:00+00:… | 2022-01-01 07:45:00+00:… | sleep | AC01 | B-000206 | bedroom | [] | routine | False |
| AC-00000-000001 | P-000625 | 2022-01-01 07:45:00+00:… | 2022-01-01 08:02:00+00:… | personal_care | AC03 | B-000206 | bathroom | [] | routine | False |
| AC-00000-000002 | P-000625 | 2022-01-01 08:02:00+00:… | 2022-01-01 08:12:00+00:… | shower_bath | AC03 | B-000206 | bathroom | [] | routine | False |
| AC-00000-000003 | P-000625 | 2022-01-01 08:12:00+00:… | 2022-01-01 08:20:00+00:… | dressing | AC03 | B-000206 | bedroom | [] | routine | False |
| AC-00000-000004 | P-000625 | 2022-01-01 08:20:00+00:… | 2022-01-01 08:45:00+00:… | eating_snack | AC02 | B-000206 | living | [] | routine | False |

**Joins**

- `person_id` → D05 persons, D08 states, D09 events, D10 activities

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
| Present for | estate-year (54,301 rows, 490.6 kB) |
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
| Present for | estate-year (1,449,871 rows, 34.7 MB) |
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
| Path | `v1/ground_truth/D14_part*.parquet` (1 part) |
| Format | declared `parquet` ; on disk Parquet |
| Partitioning | none declared ; on disk 1 sequential parts |
| Rows | 244 |
| Size | 14.4 kB |
| Time span | — |
| Resolution | not a time series |
| Primary key | grain `event` ; id columns on disk: `instance_id` |
| Present for | estate-year (244 rows, 14.4 kB); town14 (252 rows, 14.4 kB) |
| Status | **present** |
| Leakage audit | — |
| Part hash | `0e4f10e0bc990f06…` (part 0) |

**Schema** — types, null counts and ranges from the Parquet footers; descriptions and units from `schema/datasets.yaml`.

| Column | Type | Unit | Nulls | Min | Max | Declared |
|---|---|---|---|---|---|---|
| `instance_id` | string | — | no nulls | EV-2022-CRUISE-000-main | EV-2022-TERM-1107-main | required |
| `event_kind` | string | — | no nulls | DST | sport | required |
| `event_class` | string | — | no nulls | irregular | recurring | required |
| `phase` | string | — | no nulls | main | recovery | required |
| `start` | timestamp[ns, tz=UTC] | — | no nulls | 2021-12-31 00:00:00+00:00 | 2022-12-27 00:00:00+00:00 | required |
| `end` | timestamp[ns, tz=UTC] | — | no nulls | 2021-12-31 00:00:00+00:00 | 2022-12-28 00:00:00+00:00 | required |
| `footprint` | string | — | no nulls | region | town | required |
| `footprint_ids.list.element` | BYTE_ARRAY | — | 241 null (98.8%) | S-001 | S-001 | leaf of `footprint_ids` |
| `attendance_prob.all` | double | — | 214 null (87.7%) | 1.0 | 1.0 | leaf of `attendance_prob` |
| `attendance_prob.child` | double | — | 153 null (62.7%) | 0.18 | 0.9299999999999999 | leaf of `attendance_prob` |
| `attendance_prob.adult` | double | — | 123 null (50.4%) | 0.12 | 0.3 | leaf of `attendance_prob` |
| `attendance_prob.visitors` | double | — | 163 null (66.8%) | 1420.5185185185185 | 1420.5185185185185 | leaf of `attendance_prob` |
| `shared_driver` | string | — | no nulls | clock_change | winter_storm | optional |
| `source_ref` | string | — | no nulls | Department of Education t… | legal: Organisation of Wo… | required |

A dotted name is a leaf of a struct column: the Parquet footer flattens a struct, so the file physically carries the leaves while the dataset logically carries the parent.

<details><summary>Column descriptions, as declared</summary>

| Column | Declared description |
|---|---|
| `event_kind` | holiday \| school term \| storm \| outage \| festival \| cruise day \| market \| sport \| roadworks \| DST |
| `attendance_prob` | by demographic |
| `shared_driver` | 5.10: compound correlation comes from shared drivers, not independent draws |
| `source_ref` | -> D24 / SOURCES.md |

</details>

**Sample** — the first five rows of part 0, as written. Identity-bearing columns would be withheld; this dataset carries none.

| `instance_id` | `event_kind` | `event_class` | `phase` | `start` | `end` | `footprint` | `footprint_ids` | `attendance_prob.all` | `attendance_prob.child` | `attendance_prob.adult` | `attendance_prob.visitors` | `shared_driver` | `source_ref` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| EV-2022-HOL-0101-prep | holiday | predictable | preparation | 2021-12-31 00:00:00+00:… | 2021-12-31 00:00:00+00:… | region | — | 1.0 | — | — | — | institutional_year | legal: Organisation of … |
| EV-2022-HOL-0101-main | holiday | predictable | main | 2022-01-01 00:00:00+00:… | 2022-01-01 00:00:00+00:… | region | — | 1.0 | — | — | — | institutional_year | legal: Organisation of … |
| EV-2022-HOL-0101-rebound | holiday | predictable | rebound | 2022-01-02 00:00:00+00:… | 2022-01-03 00:00:00+00:… | region | — | 1.0 | — | — | — | institutional_year | legal: Organisation of … |
| EV-2022-TERM-0105-main | school term | predictable | main | 2022-01-05 00:00:00+00:… | 2022-02-18 00:00:00+00:… | region | — | — | 0.9299999999999999 | — | — | institutional_year | Department of Education… |
| EV-2022-SPORT-00-main | sport | recurring | main | 2022-01-06 00:00:00+00:… | 2022-01-06 00:00:00+00:… | town | — | — | 0.18 | 0.12 | — | winter_storm | [A] A-43: 'sport' match… |

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
| Path | `v1/ground_truth/D15_part*.parquet` (1 part) |
| Format | declared `parquet` ; on disk Parquet |
| Partitioning | none declared ; on disk 1 sequential parts |
| Rows | 525,600 |
| Size | 23.5 MB |
| Time span | `ts` 2022-01-01 00:00:00+00:00 → 2022-12-31 23:59:00+00:00 |
| Resolution | not derived |
| Primary key | grain `1 min` ; id columns on disk: `ts`, `site_id`, `realisation_id` |
| Present for | estate-year (525,600 rows, 23.5 MB); town14 (20,160 rows, 806.4 kB) |
| Status | **present** |
| Leakage audit | — |
| Part hash | `290f505df35049ac…` (part 0) |

**Schema** — types, null counts and ranges from the Parquet footers; descriptions and units from `schema/datasets.yaml`.

| Column | Type | Unit | Nulls | Min | Max | Declared |
|---|---|---|---|---|---|---|
| `ts` | timestamp[ns, tz=UTC] | — | no nulls | 2022-01-01 00:00:00+00:00 | 2022-12-31 23:59:00+00:00 | required |
| `site_id` | string | — | no nulls | Cobh | Cobh | required |
| `temp_air_c` | double | degC *(derived)* | no nulls | -3.1525 | 26.4475 | required |
| `rh_pct` | double | percent *(derived)* | no nulls | 35.5 | 100.0 | required |
| `wind_speed_ms` | double | — | no nulls | 0.42184408 | 23.2014244 | required |
| `wind_dir_deg` | double | — | no nulls | -0.0 | 360.0 | required |
| `ghi_w_m2` | double | — | no nulls | -0.0 | 1104.7531908330325 | required |
| `dni_w_m2` | double | — | no nulls | -0.0 | 971.7464566780316 | required |
| `dhi_w_m2` | double | — | no nulls | -0.0 | 782.0695116541084 | required |
| `solar_zenith_deg` | double | — | no nulls | 28.807537531679714 | 151.08109684721106 | required |
| `solar_azimuth_deg` | double | — | no nulls | 4.888265527171768 | 353.4035444415348 | required |
| `sunrise_utc` | timestamp[ns, tz=UTC] | — | no nulls | 2022-01-01 08:40:33.48453… | 2022-12-31 08:40:39.29371… | required |
| `sunset_utc` | timestamp[ns, tz=UTC] | — | no nulls | 2022-01-01 16:33:07.58570… | 2022-12-31 16:31:50.28459… | required |
| `is_dst` | bool | — | no nulls | False | True | required |
| `precip_mm` | double | — | no nulls | -0.0 | 0.17833333333333332 | required |
| `realisation_id` | string | — | no nulls | REAL-2022-20261008 | REAL-2022-20261008 | required |

<details><summary>Column descriptions, as declared</summary>

| Column | Declared description |
|---|---|
| `is_dst` | 3.2: DST is an explicit event shifting routines, not the UTC series |
| `realisation_id` | ties D15 and D31 to the same realisation |

</details>

**Sample** — the first five rows of part 0, as written. Identity-bearing columns would be withheld; this dataset carries none.

| `ts` | `site_id` | `temp_air_c` | `rh_pct` | `wind_speed_ms` | `wind_dir_deg` | `ghi_w_m2` | `dni_w_m2` | `dhi_w_m2` | `solar_zenith_deg` | `solar_azimuth_deg` | `sunrise_utc` | `sunset_utc` | `is_dst` | `precip_mm` | `realisation_id` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2022-01-01 00:00:00+00:… | Cobh | 12.6475 | 83.5 | 11.81163424 | 170.0 | 0.0 | 0.0 | 0.0 | 150.32443174904444 | 342.8556689488427 | 2022-01-01 08:40:33.484… | 2022-01-01 16:33:07.585… | True | 0.0 | REAL-2022-20261008 |
| 2022-01-01 00:01:00+00:… | Cobh | 12.654166666666667 | 83.46666666666667 | 11.825695709333333 | 170.0 | 0.0 | 0.0 | 0.0 | 150.33256022089495 | 337.3269102094019 | 2022-01-01 08:40:33.484… | 2022-01-01 16:33:07.585… | True | 0.0 | REAL-2022-20261008 |
| 2022-01-01 00:02:00+00:… | Cobh | 12.660833333333334 | 83.43333333333334 | 11.839757178666666 | 170.0 | 0.0 | 0.0 | 0.0 | 150.34068869274543 | 331.798151469961 | 2022-01-01 08:40:33.484… | 2022-01-01 16:33:07.585… | True | 0.0 | REAL-2022-20261008 |
| 2022-01-01 00:03:00+00:… | Cobh | 12.6675 | 83.4 | 11.853818648 | 170.0 | 0.0 | 0.0 | 0.0 | 150.34881716459594 | 326.26939273052017 | 2022-01-01 08:40:33.484… | 2022-01-01 16:33:07.585… | True | 0.0 | REAL-2022-20261008 |
| 2022-01-01 00:04:00+00:… | Cobh | 12.674166666666668 | 83.36666666666666 | 11.867880117333334 | 170.0 | 0.0 | 0.0 | 0.0 | 150.35694563644643 | 320.74063399107933 | 2022-01-01 08:40:33.484… | 2022-01-01 16:33:07.585… | True | 0.0 | REAL-2022-20261008 |

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
| Present for | estate-year (1,752,000 rows, 122.8 MB) |
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
| Path | `v1/ground_truth/town14/D17_part*.parquet` (1 part) |
| Format | declared `parquet` ; on disk Parquet |
| Partitioning | none declared ; on disk 1 sequential parts |
| Rows | 157,248 |
| Size | 5.2 MB |
| Time span | `ts` 2022-01-01 00:00:00+00:00 → 2022-01-14 23:45:00+00:00 |
| Resolution | not derived |
| Primary key | grain `1 min` ; id columns on disk: `ts`, `element_id` |
| Present for | town14 (157,248 rows, 5.2 MB) |
| Status | **present** |
| Leakage audit | — |
| Part hash | `ccefa1abeff4b819…` (part 0) |

**Schema** — types, null counts and ranges from the Parquet footers; descriptions and units from `schema/datasets.yaml`.

| Column | Type | Unit | Nulls | Min | Max | Declared |
|---|---|---|---|---|---|---|
| `ts` | timestamp[ns, tz=UTC] | — | no nulls | 2022-01-01 00:00:00+00:00 | 2022-01-14 23:45:00+00:00 | required |
| `element_id` | string | — | no nulls | FDR-EST-047106003-00 | SUB-EST-047107029 | required |
| `element_kind` | string | — | no nulls | feeder | transformer | required |
| `p_kw` | double | kW *(derived)* | no nulls | -1.6406065624786765 | 118.7151846901117 | required |
| `q_kvar` | double | — | no nulls | -0.33903075941204114 | 24.32326356277967 | optional |
| `voltage_pu` | double | — | no nulls | 0.9897469379231888 | 1.0000997770027138 | optional |
| `loading_pct` | double | percent *(derived)* | no nulls | 0.003800637030022208 | 56.51299792616028 | optional |
| `outage` | bool | — | no nulls | False | False | required |
| `coupling_mode` | string | — | no nulls | C2 | C2 | required |
| `epoch_staleness_s` | int64 | — | no nulls | 900 | 900 | required |

<details><summary>Column descriptions, as declared</summary>

| Column | Declared description |
|---|---|
| `element_kind` | feeder \| transformer \| connection |
| `epoch_staleness_s` | 8.2 timing contract: the staleness stamp on the published state |

</details>

**Sample** — the first five rows of part 0, as written. Identity-bearing columns would be withheld; this dataset carries none.

| `ts` | `element_id` | `element_kind` | `p_kw` | `q_kvar` | `voltage_pu` | `loading_pct` | `outage` | `coupling_mode` | `epoch_staleness_s` |
|---|---|---|---|---|---|---|---|---|---|
| 2022-01-01 00:00:00+00:… | SUB-EST-047106003 | transformer | 6.3502849885177435 | 1.27810219180917 | 0.999562884087149 | 1.952015299665305 | False | C2 | 900 |
| 2022-01-01 00:00:00+00:… | SUB-EST-047106005 | transformer | 3.915255679487334 | 0.788663924992352 | 0.9997213114322047 | 1.3312122873091428 | False | C2 | 900 |
| 2022-01-01 00:00:00+00:… | SUB-EST-047106006/01 | transformer | 6.441874838996769 | 1.3033228192461863 | 0.9995559288232836 | 1.9756578003324694 | False | C2 | 900 |
| 2022-01-01 00:00:00+00:… | SUB-EST-047106006/02 | transformer | 4.872573616121018 | 0.9836823203835017 | 0.999658667409642 | 1.5753065866166556 | False | C2 | 900 |
| 2022-01-01 00:00:00+00:… | SUB-EST-047106007 | transformer | 6.261688816246347 | 1.2655179897951794 | 0.9995678896206946 | 1.929633501378052 | False | C2 | 900 |

**Joins**

- **Masked view:** this dataset is ground truth with an observable view — aggregate: feeder and transformer totals, not per element
- Declared observable view: `D17_aggregate`

**Validation**

No check in the artefacts names this dataset, and no module opens it by name. That is a statement about the evidence on disk, not a claim that the dataset is unchecked.

Links are attributed from the artefacts themselves — a check is listed where its own record names the dataset — rather than from a mapping kept in the generator, which would go stale.

<div style="page-break-after: always;"></div>

<a id="d17_aggregate"></a>

## D17_aggregate · D17's observable view: connection register, asset ratings, feeder-head and substation measurements

D17's observable view: what a distribution operator would actually hold about its low-voltage network. The connection register — which MPRN sits on which feeder and which substation — the asset register's transformer and feeder ratings, and the feeder-head and substation power measurements.

**Key points**

- Three kinds of row in one table, told apart by `record_kind`: a connection-register entry, a feeder-head measurement, or a substation measurement. The register is written once per run, because the topology is built once and does not change within it.
- Both ratings are catalogue values of the pandapower standard types the network is built from, so neither is a number written in this build.
- No voltage, anywhere. The topology is a declared assumption and voltage drop is a line integral along exactly the declared feeder span, so publishing a per-unit voltage to a model developer would present an assumption as a measurement.
- No per-element loading: that ratio is ground truth. The ratings and the measurements are both here because the change request names them; their ratio is not published.
- No per-connection power. A register row names a premises and carries no measurement; a measurement row names an element and never a premises.
- Every measured power equals the ground-truth row for the same element and epoch exactly: the view is a projection of the truth, not a second computation of it. Observable, so this is what a model developer is given.

**Facts**

| | |
|---|---|
| Class | OBS — Observable. What a device, respondent, assessor or operator would see. |
| Package | Observable |
| Path | `v1/observable/town14/D17_aggregate_part*.parquet` (1 part) |
| Format | declared `parquet` ; on disk Parquet |
| Partitioning | none declared ; on disk 1 sequential parts |
| Rows | 158,340 |
| Size | 2.5 MB |
| Time span | `ts` 2022-01-01 00:00:00+00:00 → 2022-01-14 23:45:00+00:00 |
| Resolution | not derived |
| Primary key | declared `keyed_by: premises` ; id columns on disk: `ts`, `premises_id` |
| Present for | town14 (158,340 rows, 2.5 MB) |
| Status | **present** |
| Leakage audit | passed: no GT-class or forbidden field names present |
| Part hash | `bd71d19346af6a9c…` (part 0) |

**Schema** — types, null counts and ranges from the Parquet footers; descriptions and units from `schema/datasets.yaml`.

| Column | Type | Unit | Nulls | Min | Max | Declared |
|---|---|---|---|---|---|---|
| `record_kind` | string | — | no nulls | connection_register | substation | required |
| `ts` | timestamp[ns, tz=UTC] | — | no nulls | 2022-01-01 00:00:00+00:00 | 2022-01-14 23:45:00+00:00 | required |
| `premises_id` | string | — | 157,248 null (99.3%) | MPRN-0021F646759989E064 | MPRN-FF61C456088F1D0665 | optional |
| `substation_ref` | string | — | no nulls | SUB-EST-047106003 | SUB-EST-047107029 | required |
| `feeder_ref` | string | — | 71,232 null (45.0%) | FDR-EST-047106003-00 | FDR-EST-047107029-00 | optional |
| `transformer_rated_kva` | double | kVA | 87,108 null (55.0%) | 400.0 | 630.0 | optional |
| `feeder_rated_a` | double | A | 72,324 null (45.7%) | 270.0 | 270.0 | optional |
| `p_kw_measured` | double | kW | 1,092 null (0.7%) | -1.6406065624786765 | 118.7151846901117 | optional |
| `q_kvar_measured` | double | kvar | 1,092 null (0.7%) | -0.33903075941204114 | 24.32326356277967 | optional |

<details><summary>Column descriptions, as declared</summary>

| Column | Declared description |
|---|---|
| `record_kind` | which of the operator's three LV records this row is: a connection-register entry, a feeder-head measurement, or a substation measurement |
| `ts` | the timestamp the operator's system stamps on the record: the metering timestamp of a measurement, or the as-at instant of the connection register |
| `premises_id` | the MPRN as it appears in the operator's connection register; null on a measurement row, which names a network element and not a customer |
| `substation_ref` | the distribution substation's reference in the operator's asset register; every LV connection and every LV circuit is recorded against exactly one |
| `feeder_ref` | the LV circuit's reference in the operator's asset register; null on a substation measurement, which sits upstream of every circuit |
| `transformer_rated_kva` | the distribution transformer's nameplate rating, read off the operator's asset register; null where the row's subject is not a transformer |
| `feeder_rated_a` | the feeder cable's thermal current rating, from the cable type recorded in the operator's asset register; null where the row's subject is not a circu… |
| `p_kw_measured` | the active power the feeder-pillar or substation CT metering reports for the epoch, positive for import; null on a register row, which carries no mea… |
| `q_kvar_measured` | the reactive power the same CT metering reports for the epoch; null on a register row |

</details>

**Sample** — the first five rows of part 0, as written. Identity-bearing columns would be withheld; this dataset carries none.

| `record_kind` | `ts` | `premises_id` | `substation_ref` | `feeder_ref` | `transformer_rated_kva` | `feeder_rated_a` | `p_kw_measured` | `q_kvar_measured` |
|---|---|---|---|---|---|---|---|---|
| connection_register | 2022-01-01 00:00:00+00:… | MPRN-7D094B670D094BEC3C | SUB-EST-047106003 | FDR-EST-047106003-00 | — | — | — | — |
| connection_register | 2022-01-01 00:00:00+00:… | MPRN-A3394A55E335A51AF7 | SUB-EST-047106003 | FDR-EST-047106003-01 | — | — | — | — |
| connection_register | 2022-01-01 00:00:00+00:… | MPRN-4C4F46CF2294F3C94A | SUB-EST-047106003 | FDR-EST-047106003-00 | — | — | — | — |
| connection_register | 2022-01-01 00:00:00+00:… | MPRN-844212A0C93F67B0FF | SUB-EST-047106003 | FDR-EST-047106003-01 | — | — | — | — |
| connection_register | 2022-01-01 00:00:00+00:… | MPRN-803459C9B52098ED40 | SUB-EST-047106003 | FDR-EST-047106003-00 | — | — | — | — |

**Joins**

- `premises_id` → D18, D19, D27 to D30 (the meter-boundary identity of a home)

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
| Present for | estate-year (66,097,553 rows, 506.4 MB) |
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
| Present for | estate-year (3,521,520 rows, 71.1 MB) |
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
| Path | `v1/ground_truth/wp5_decade/D20_part*.parquet` (1 part) |
| Format | declared `parquet` ; on disk Parquet |
| Partitioning | none declared ; on disk 1 sequential parts |
| Rows | 253 |
| Size | 12.7 kB |
| Time span | `true_onset_day` 17 → 3625 (day index from the run's first day, not a date) |
| Resolution | not a time series |
| Primary key | grain `event` ; id columns on disk: `label_id`, `building_id` |
| Present for | wp5_decade (253 rows, 12.7 kB) |
| Status | **present** |
| Leakage audit | — |
| Part hash | `933ae0dc34ea6116…` (part 0) |

**Schema** — types, null counts and ranges from the Parquet footers; descriptions and units from `schema/datasets.yaml`.

| Column | Type | Unit | Nulls | Min | Max | Declared |
|---|---|---|---|---|---|---|
| `label_id` | string | — | no nulls | CL-H-000843-EQUIP-01 | CL-LE-2031-RETROFIT_FABRI… | required |
| `building_id` | string | — | no nulls | B-000786 | B-001023 | required |
| `change_class` | string | — | no nulls | equipment | structural | required |
| `true_onset` | timestamp[ns, tz=UTC] | — | no nulls | 2022-01-18 00:00:00+00:00 | 2031-12-05 00:00:00+00:00 | required |
| `true_end` | timestamp[ns, tz=UTC] | — | 252 null (99.6%) | 2022-07-28 00:00:00+00:00 | 2022-07-28 00:00:00+00:00 | optional |
| `persistence` | string | — | no nulls | permanent | transient | required |
| `source_event_ids.list.element` | BYTE_ARRAY | — | no nulls | LE-2022-BIRTH-0001 | LE-H-000843-MARY-MOVEIN | leaf of `source_event_ids` |
| `detectable_from_tier` | string | — | no nulls | T1 | T4 | required |
| `observable_change_text` | string | — | no nulls | A daily activity structur… | Wet-appliance cycle count… | required |

A dotted name is a leaf of a struct column: the Parquet footer flattens a struct, so the file physically carries the leaves while the dataset logically carries the parent.

<details><summary>Column descriptions, as declared</summary>

| Column | Declared description |
|---|---|
| `source_event_ids` | links to D09, D03, D14 |
| `detectable_from_tier` | lowest tier at which it is theoretically observable |
| `observable_change_text` | R25: what changed in observable behaviour, never a cause |

</details>

**Sample** — the first five rows of part 0, as written. Identity-bearing columns would be withheld; this dataset carries none.

| `label_id` | `building_id` | `change_class` | `true_onset` | `true_end` | `persistence` | `source_event_ids` | `detectable_from_tier` | `observable_change_text` |
|---|---|---|---|---|---|---|---|---|
| CL-LE-2022-HEALTH_STATE… | B-000854 | routine deviation | 2022-01-18 00:00:00+00:… | — | persistent | ['LE-2022-HEALTH_STATE_… | T2 | withheld |
| CL-LE-2022-MOVE_OUT-000… | B-000848 | structural | 2022-01-20 00:00:00+00:… | — | permanent | ['LE-2022-MOVE_OUT-0001… | T1 | withheld |
| CL-LE-2022-DER_SMART_CO… | B-001019 | equipment | 2022-02-01 00:00:00+00:… | — | permanent | ['LE-2022-DER_SMART_CON… | T2 | withheld |
| CL-LE-2022-DER_BATTERY-… | B-000856 | equipment | 2022-02-04 00:00:00+00:… | — | permanent | ['LE-2022-DER_BATTERY-0… | T4 | withheld |
| CL-LE-2022-DER_PV-0001-… | B-000862 | equipment | 2022-02-15 00:00:00+00:… | — | permanent | ['LE-2022-DER_PV-0001'] | T1 | withheld |

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
| Path | `v1/ground_truth/D21_part*.parquet` (1 part) |
| Format | declared `json` ; on disk Parquet |
| Partitioning | none declared ; on disk 1 sequential parts |
| Rows | 294 |
| Size | 39.7 kB |
| Time span | — |
| Resolution | not a time series |
| Primary key | grain `person x date` ; id columns on disk: `person_id` |
| Present for | estate-year (294 rows, 39.7 kB); town14 (5,834 rows, 543.9 kB) |
| Status | **present** |
| Leakage audit | — |
| Part hash | `bacc00c68847022e…` (part 0) |

**Schema** — types, null counts and ranges from the Parquet footers; descriptions and units from `schema/datasets.yaml`.

| Column | Type | Unit | Nulls | Min | Max | Declared |
|---|---|---|---|---|---|---|
| `person_id` | string | — | no nulls | P-000625 | P-000795 | required |
| `as_of` | date32[day] | — | no nulls | 2022-01-01 | 2022-12-31 | required |
| `narrative_md` | string | — | no nulls | # Aidan Brennan (P-000736… | # Zofia Nowak (P-000730) … | required |
| `source_record_ids.list.element` | BYTE_ARRAY | — | no nulls | D05:P-000625 | D08:S-P-000795-0001 | leaf of `source_record_ids` |
| `cluster_label` | string | — | 294 null (100.0%) | — | — | optional |

A dotted name is a leaf of a struct column: the Parquet footer flattens a struct, so the file physically carries the leaves while the dataset logically carries the parent.

<details><summary>Column descriptions, as declared</summary>

| Column | Declared description |
|---|---|
| `narrative_md` | 5.2 step 6: generated from structured records only, never free-written |
| `source_record_ids` | every sentence traces to a record |
| `cluster_label` | 5.13: no person is ever labelled by cluster. Present only so the schema test can assert it is always null. |

</details>

**Sample** — the first five rows of part 0, as written. Identity-bearing columns would be withheld; this dataset carries none.

| `person_id` | `as_of` | `narrative_md` | `source_record_ids` | `cluster_label` |
|---|---|---|---|---|
| P-000625 | 2022-01-01 | withheld | ['D05:P-000625', 'D06:M… | — |
| P-000625 | 2022-12-31 | withheld | ['D05:P-000625', 'D06:M… | — |
| P-000626 | 2022-01-01 | withheld | ['D05:P-000626', 'D06:M… | — |
| P-000626 | 2022-12-31 | withheld | ['D05:P-000626', 'D06:M… | — |
| P-000627 | 2022-01-01 | withheld | ['D05:P-000627', 'D06:M… | — |

**Joins**

- `person_id` → D05 persons, D08 states, D09 events, D10 activities

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
| Path | `v1/evidence/D22_part*.parquet` (1 part) |
| Format | declared `parquet + npz` ; on disk Parquet |
| Partitioning | none declared ; on disk 1 sequential parts |
| Rows | 19 |
| Size | 11.5 kB |
| Time span | — |
| Resolution | not a time series |
| Primary key | grain `signature` ; id columns on disk: `signature_id` |
| Present for | estate-year (19 rows, 11.5 kB); town14 (19 rows, 11.5 kB) |
| Status | **present** |
| Leakage audit | — |
| Part hash | `fe375b21ccaf0272…` (part 0) |

**Schema** — types, null counts and ranges from the Parquet footers; descriptions and units from `schema/datasets.yaml`.

| Column | Type | Unit | Nulls | Min | Max | Declared |
|---|---|---|---|---|---|---|
| `signature_id` | string | — | no nulls | SIG-DISH-ECO | SIG-WASH-QUICK | required |
| `appliance_type` | string | — | no nulls | dishwasher | washing_machine | required |
| `programme` | string | — | no nulls | 1.5 L | viewing | required |
| `source_dataset` | string | — | no nulls | synthetic-template | synthetic-template | required |
| `source_licence` | string | — | no nulls | n/a (parameterised templa… | n/a (parameterised templa… | required |
| `template_hz` | double | — | no nulls | 1.0 | 1.0 | required |
| `template_w.list.element` | DOUBLE | — | no nulls | -0.0 | 1.3 | leaf of `template_w` |
| `duration_s` | int64 | — | no nulls | 150 | 86400 | required |
| `energy_wh_nominal` | double | — | no nulls | 22.1 | 19913.1 | required |
| `var_power_cv` | double | — | no nulls | 0.04 | 0.3 | required |
| `var_duration_cv` | double | — | no nulls | 0.02 | 0.4 | required |
| `ageing_power_per_year` | double | — | no nulls | -0.0 | 0.008 | required |
| `irish_specific` | bool | — | no nulls | False | True | required |
| `evidence_status` | string | — | no nulls | [A] parameterised templat… | [A] parameterised templat… | required |

A dotted name is a leaf of a struct column: the Parquet footer flattens a struct, so the file physically carries the leaves while the dataset logically carries the parent.

<details><summary>Column descriptions, as declared</summary>

| Column | Declared description |
|---|---|
| `source_dataset` | UK-DALE \| REFIT \| REDD \| IDEAL \| synthetic-template |
| `var_power_cv` | model-to-model variation, so two kettles are never identical |
| `irish_specific` | K07: electric shower, immersion, storage heater |
| `evidence_status` | [C] cited \| [A] assumption \| synthetic placeholder |

</details>

**Sample** — the first five rows of part 0, as written. Identity-bearing columns would be withheld; this dataset carries none.

| `signature_id` | `appliance_type` | `programme` | `source_dataset` | `source_licence` | `template_hz` | `template_w` | `duration_s` | `energy_wh_nominal` | `var_power_cv` | `var_duration_cv` | `ageing_power_per_year` | `irish_specific` | `evidence_status` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SIG-DISH-ECO | dishwasher | eco 50 | synthetic-template | n/a (parameterised temp… | 1.0 | [0.04, 1.0, 1.0, 0.03, … | 12600 | 896.7 | 0.1 | 0.08 | 0.004 | False | [A] parameterised templ… |
| SIG-DRY-COND | tumble_dryer | cottons | synthetic-template | n/a (parameterised temp… | 1.0 | [0.95, 0.95, 0.52, 0.35… | 7200 | 3365.4 | 0.1 | 0.14 | 0.005 | True | [A] parameterised templ… |
| SIG-EV-7K | ev_charger | 7.4 kW AC | synthetic-template | n/a (parameterised temp… | 1.0 | [1.0, 1.0, 0.6, 0.25, 0… | 10800 | 19913.1 | 0.04 | 0.35 | 0.001 | False | [A] parameterised templ… |
| SIG-EXTRACT | extractor_fan | medium | synthetic-template | n/a (parameterised temp… | 1.0 | [1.0, 1.0] | 1200 | 43.3 | 0.12 | 0.3 | 0.002 | False | [A] parameterised templ… |
| SIG-FRIDGE | fridge_freezer | compressor cycle | synthetic-template | n/a (parameterised temp… | 1.0 | [1.0, 1.0, 0.02, 0.02] | 1800 | 22.1 | 0.15 | 0.2 | 0.008 | False | [A] parameterised templ… |

**Joins**

- `signature_id` → D22 signature library

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
| Path | `v1/evidence/D23_part*.parquet` (1 part) |
| Format | declared `json` ; on disk Parquet |
| Partitioning | none declared ; on disk 1 sequential parts |
| Rows | 1 |
| Size | 33.3 kB |
| Time span | — |
| Resolution | not a time series |
| Primary key | grain `run` ; id columns on disk: `run_id` |
| Present for | estate-year (1 rows, 33.3 kB); town14 (1 rows, 37.3 kB) |
| Status | **present** |
| Leakage audit | — |
| Part hash | `147aa95df3e29d99…` (part 0) |

**Schema** — types, null counts and ranges from the Parquet footers; descriptions and units from `schema/datasets.yaml`.

| Column | Type | Unit | Nulls | Min | Max | Declared |
|---|---|---|---|---|---|---|
| `run_id` | string | — | no nulls | D23-RECONSTRUCTED-estate-… | D23-RECONSTRUCTED-estate-… | required |
| `created_at_utc` | timestamp[ns, tz=UTC] | — | no nulls | 2026-10-13 15:32:42.14584… | 2026-10-13 15:32:42.14584… | required |
| `label` | string | — | no nulls | UNVALIDATED SIMULATION EV… | UNVALIDATED SIMULATION EV… | required |
| `code_version` | string | — | no nulls | 0.1.0a1+e1-reconstructed | 0.1.0a1+e1-reconstructed | required |
| `code_git_sha` | string | — | no nulls | fdef6279bc44aac507503bf96… | fdef6279bc44aac507503bf96… | required |
| `code_tree_hash` | string | — | no nulls | 3e647f947ca6fa74c91fd40db… | 3e647f947ca6fa74c91fd40db… | required |
| `schema_version` | string | — | no nulls | 1.0.0 | 1.0.0 | required |
| `design_revision` | int64 | — | no nulls | 3 | 3 | required |
| `master_seed` | int64 | — | no nulls | 20261008 | 20261008 | required |
| `coupling_mode` | string | — | no nulls | C1 | C1 | required |
| `scope` | string | — | no nulls | {"coupling_mode": "C1", "… | {"coupling_mode": "C1", "… | required |
| `input_sources` | string | — | no nulls | — | — | required |
| `parameters` | string | — | no nulls | — | — | required |
| `outputs` | string | — | no nulls | — | — | required |
| `checkpoint_chain_head` | string | — | no nulls | 98c6b38427643d6233ce49660… | 98c6b38427643d6233ce49660… | optional |
| `environment` | string | — | no nulls | {"_provenance": "the subs… | {"_provenance": "the subs… | required |

<details><summary>Column descriptions, as declared</summary>

| Column | Declared description |
|---|---|
| `label` | every output is labelled UNVALIDATED SIMULATION EVIDENCE |
| `code_tree_hash` | hash of the source tree, so an uncommitted edit is visible |
| `scope` | the E1 scope actually run |
| `input_sources` | every sources/ file used, with its SHA-256 |
| `outputs` | path -> SHA-256 for every file written |
| `environment` | python, numpy, platform, core count |

</details>

**Sample** — the first five rows of part 0, as written. Identity-bearing columns would be withheld; this dataset carries none.

| `run_id` | `created_at_utc` | `label` | `code_version` | `code_git_sha` | `code_tree_hash` | `schema_version` | `design_revision` | `master_seed` | `coupling_mode` | `scope` | `input_sources` | `parameters` | `outputs` | `checkpoint_chain_head` | `environment` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D23-RECONSTRUCTED-estat… | 2026-10-13 15:32:42.145… | UNVALIDATED SIMULATION … | 0.1.0a1+e1-reconstructed | fdef6279bc44aac507503bf… | 3e647f947ca6fa74c91fd40… | 1.0.0 | 3 | 20261008 | C1 | {"coupling_mode": "C1",… | {"_provenance": "the DE… | {"captured_run_paramete… | {"_excluded": "parts wr… | 98c6b38427643d6233ce496… | {"_provenance": "the su… |

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
| Path | `v1/observable/D25_part*.parquet` (1 part) |
| Format | declared `MIMIC MySQL via the public API; Parquet copy` ; on disk Parquet |
| Partitioning | none declared ; on disk 1 sequential parts |
| Rows | 294,695 |
| Size | 2.6 MB |
| Time span | — |
| Resolution | not a time series |
| Primary key | grain `participant, session, response` ; id columns on disk: `participant_id`, `session_id` |
| Present for | estate-year (294,695 rows, 2.6 MB) |
| Status | **present** |
| Leakage audit | passed: no GT-class or forbidden field names present |
| Part hash | `661c86b066922608…` (part 0) |

**Schema** — types, null counts and ranges from the Parquet footers; descriptions and units from `schema/datasets.yaml`.

| Column | Type | Unit | Nulls | Min | Max | Declared |
|---|---|---|---|---|---|---|
| `participant_id` | string | — | no nulls | 00005bcb-93a3-4f56-bd40-3… | fffe5623-4c56-4570-9e10-1… | required |
| `consent_version` | string | — | no nulls | SYNTHETIC-HRSD-v1-BN-panel | SYNTHETIC-HRSD-v1-HRSD-po… | required |
| `consent_granted_at` | timestamp[ns, tz=UTC] | — | no nulls | 2026-10-12 12:58:08+00:00 | 2026-10-12 15:30:23+00:00 | required |
| `mcv_position` | string | — | no nulls | post | pre | required |
| `age_band` | string | — | no nulls | 18–24 | 65+ | required |
| `reported_sex` | string | — | no nulls | Female | Male | required |
| `household_size` | string | — | no nulls | 1 | 5+ | required |
| `children_present` | string | — | no nulls | No | Yes | required |
| `employment_status` | string | — | no nulls | Full-time | Unemployed | required |
| `reported_work_pattern` | string | — | no nulls | Irregular | Shift | required |
| `reported_dwelling_type` | string | — | no nulls | Apartment | Semi-Detached | required |
| `ownership_status` | string | — | no nulls | Other | Social | required |
| `region_country` | string | — | no nulls | AT | SK | required |
| `region_nuts3` | string | — | no nulls | AT-01 | SK-09 | required |
| `urban_rural_island` | string | — | no nulls | Island | Urban | required |
| `income_band` | string | — | no nulls | 1 | 5 | required |
| `der_ownership` | string | — | no nulls | ["EV","HP"] | ["PV"] | required |
| `environmental_concern` | int64 | — | no nulls | 1 | 5 | required |
| `trust_in_automation` | int64 | — | no nulls | 1 | 5 | required |
| `comfort_sensitivity` | int64 | — | no nulls | 1 | 5 | required |
| `mcv_01_to_10.list.element` | INT64 | — | 5,756 null (2.0%) | 1 | 5 | leaf of `mcv_01_to_10` |
| `profile_optional` | string | — | no nulls | {"community_energy_member… | {"community_energy_member… | optional |
| `session_id` | string | — | 103 null (0.0%) | 0002606b-205e-4a94-b8ff-2… | ffff84c7-5165-40d8-a7ac-9… | optional |
| `chosen_signal` | string | — | 103 null (0.0%) | AL | SO | optional |
| `chosen_display_position` | int64 | — | 103 null (0.0%) | 1 | 4 | optional |
| `display_permutation` | string | — | 103 null (0.0%) | ["AL","CP","RC","SO"] | ["SO","RC","CP","AL"] | optional |
| `latency_ms` | int64 | — | 103 null (0.0%) | 350 | 56058 | optional |
| `is_probe` | bool | — | 103 null (0.0%) | False | True | optional |
| `is_probe_repeat` | bool | — | 103 null (0.0%) | False | True | optional |

A dotted name is a leaf of a struct column: the Parquet footer flattens a struct, so the file physically carries the leaves while the dataset logically carries the parent.

<details><summary>Column descriptions, as declared</summary>

| Column | Declared description |
|---|---|
| `participant_id` | the UUID MIMIC issues when consent is granted |
| `consent_version` | SYNTHETIC-HRSD-v1-<pool>; MIMIC's LIKE 'SYNTHETIC%' purge and banner work unchanged (U17) |
| `consent_granted_at` | the server clock when consent was recorded |
| `mcv_position` | MIMIC's own randomisation of where the MCV block falls |
| `age_band` | MIMIC bands use an en-dash; see I-003 |
| `reported_sex` | self-reported. Named distinctly from D05.sex (GT, persistent layer) so the two cannot be joined; MIMIC's own column name is preserved in mimic_field. |
| `household_size` | the participant's own count of people in the home |
| `children_present` | the participant's answer about anyone under 18 |
| `employment_status` | U18 gap: MIMIC has no 'Home duties' value |
| `reported_work_pattern` | self-reported. Named distinctly from D08.work_pattern (GT, evolving layer). |
| `reported_dwelling_type` | self-reported, named distinctly from D02.dwelling_type (GT). U18 gap: MIMIC has no 'Terraced' value, a common Cobh house type. |
| `ownership_status` | the participant's selection |
| `region_country` | the participant's selection |
| `region_nuts3` | the participant's selection |
| `urban_rural_island` | the participant's selection |
| `income_band` | the participant's selection |
| `der_ownership` | the participant's recollection of what is installed |
| `environmental_concern` | round(3 + 1.05 * latent), clamped 1 to 5, as MIMIC |
| `trust_in_automation` | the participant's self-report |
| `comfort_sensitivity` | the participant's self-report |
| `mcv_01_to_10` | the participant's Likert answers to the 10 Moral and Community Values items |
| `profile_optional` | design 5.14: the 10 permitted fields. e.g. home_automation_level <- sensor tier; energy_bill_responsibility <- decision authority. ADR-004 exclusions… |
| `session_id` | the session MIMIC created |
| `chosen_signal` | the option the participant chose |
| `chosen_display_position` | where that option happened to appear on screen |
| `display_permutation` | MIMIC's own option-order randomisation for that item |
| `latency_ms` | wall time between the item being shown and answered |
| `is_probe` | MIMIC's own item flag |
| `is_probe_repeat` | MIMIC's own item flag |

</details>

**Sample** — the first five rows of part 0, as written. Identity-bearing columns would be withheld; this dataset carries none.

| `participant_id` | `consent_version` | `consent_granted_at` | `mcv_position` | `age_band` | `reported_sex` | `household_size` | `children_present` | `employment_status` | `reported_work_pattern` | `reported_dwelling_type` | `ownership_status` | `region_country` | `region_nuts3` | `urban_rural_island` | `income_band` | `der_ownership` | `environmental_concern` | `trust_in_automation` | `comfort_sensitivity` | `mcv_01_to_10` | `profile_optional` | `session_id` | `chosen_signal` | `chosen_display_position` | `display_permutation` | `latency_ms` | `is_probe` | `is_probe_repeat` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 00005bcb-93a3-4f56-bd40… | SYNTHETIC-HRSD-v1-HRSD-… | 2026-10-12 13:32:28+00:… | post | 65+ | Male | 4 | No | Full-time | Remote | Detached | Owner | SK | SK-06 | Rural | 3 | ["PV","Battery"] | 3 | 3 | 4 | [4, 5, 5, 4, 3, 4, 4, 5… | {"community_energy_memb… | 43a9ef10-9a2e-4b5c-b747… | CP | 4 | ["RC","SO","AL","CP"] | 16358 | False | False |
| 00005bcb-93a3-4f56-bd40… | SYNTHETIC-HRSD-v1-HRSD-… | 2026-10-12 13:32:28+00:… | post | 65+ | Male | 4 | No | Full-time | Remote | Detached | Owner | SK | SK-06 | Rural | 3 | ["PV","Battery"] | 3 | 3 | 4 | [4, 5, 5, 4, 3, 4, 4, 5… | {"community_energy_memb… | 43a9ef10-9a2e-4b5c-b747… | AL | 3 | ["CP","RC","AL","SO"] | 7098 | False | False |
| 00005bcb-93a3-4f56-bd40… | SYNTHETIC-HRSD-v1-HRSD-… | 2026-10-12 13:32:28+00:… | post | 65+ | Male | 4 | No | Full-time | Remote | Detached | Owner | SK | SK-06 | Rural | 3 | ["PV","Battery"] | 3 | 3 | 4 | [4, 5, 5, 4, 3, 4, 4, 5… | {"community_energy_memb… | 43a9ef10-9a2e-4b5c-b747… | AL | 1 | ["AL","SO","CP","RC"] | 3311 | True | False |
| 00005bcb-93a3-4f56-bd40… | SYNTHETIC-HRSD-v1-HRSD-… | 2026-10-12 13:32:28+00:… | post | 65+ | Male | 4 | No | Full-time | Remote | Detached | Owner | SK | SK-06 | Rural | 3 | ["PV","Battery"] | 3 | 3 | 4 | [4, 5, 5, 4, 3, 4, 4, 5… | {"community_energy_memb… | 43a9ef10-9a2e-4b5c-b747… | CP | 1 | ["CP","SO","AL","RC"] | 6537 | True | True |
| 00005bcb-93a3-4f56-bd40… | SYNTHETIC-HRSD-v1-HRSD-… | 2026-10-12 13:32:28+00:… | post | 65+ | Male | 4 | No | Full-time | Remote | Detached | Owner | SK | SK-06 | Rural | 3 | ["PV","Battery"] | 3 | 3 | 4 | [4, 5, 5, 4, 3, 4, 4, 5… | {"community_energy_memb… | 43a9ef10-9a2e-4b5c-b747… | AL | 4 | ["CP","SO","RC","AL"] | 7869 | False | False |

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
| Path | `v1/ground_truth/D26_part*.parquet` (1 part) |
| Format | declared `parquet` ; on disk Parquet |
| Partitioning | none declared ; on disk 1 sequential parts |
| Rows | 23,456 |
| Size | 1.9 MB |
| Time span | — |
| Resolution | not a time series |
| Primary key | grain `participant` ; id columns on disk: `participant_id`, `person_id` |
| Present for | estate-year (23,456 rows, 1.9 MB) |
| Status | **present** |
| Leakage audit | — |
| Part hash | `2c8a8d5ed238fdb1…` (part 0) |

**Schema** — types, null counts and ranges from the Parquet footers; descriptions and units from `schema/datasets.yaml`.

| Column | Type | Unit | Nulls | Min | Max | Declared |
|---|---|---|---|---|---|---|
| `participant_id` | string | — | no nulls | 00005bcb-93a3-4f56-bd40-3… | fffe5623-4c56-4570-9e10-1… | required |
| `person_id` | string | — | no nulls | HP-0000001 | T10-HP-0000600 | required |
| `pool` | string | — | no nulls | BN-panel | HRSD-pool | required |
| `true_traits` | string | — | no nulls | {"autonomy":-0.0005963695… | {"autonomy":5.73932517936… | required |
| `planted_segment` | string | — | 23,456 null (100.0%) | — | — | optional |
| `planted_null_mode` | bool | — | no nulls | False | False | required |
| `response_propensity` | double | — | no nulls | 0.13374257242545526 | 0.8521608602037171 | required |
| `stated_gap` | double | — | no nulls | -0.0 | 0.6573028139353545 | required |
| `satisficer` | bool | — | no nulls | False | True | required |
| `planted_position_bias` | double | — | no nulls | -0.0 | 1.6 | required |
| `planted_context_effect` | string | — | no nulls | {"grid_stress":{"cooperat… | {"grid_stress":{"cooperat… | optional |
| `generator` | string | — | no nulls | G-B | G-B | required |
| `gc_mode` | string | — | 23,456 null (100.0%) | — | — | optional |
| `simulated_session_date` | date32[day] | — | 10,650 null (45.4%) | 2022-01-01 | 2031-12-31 | optional |
| `test_mode_settings` | string | — | no nulls | {"gb_spec_hash":"c53995d9… | {"gb_spec_hash":"c53995d9… | required |

<details><summary>Column descriptions, as declared</summary>

| Column | Declared description |
|---|---|
| `true_traits` | the ten MIMIC latents as generated |
| `planted_segment` | T3: the k segments planted, or null in null mode |
| `planted_null_mode` | T3(b): no clusters planted |
| `planted_position_bias` | T10: 0 in the clean batch, non-zero in the planted batch |
| `planted_context_effect` | T7 AMCE |
| `generator` | 5.14 independence protocol: G-A \| G-B \| G-C |
| `gc_mode` | wrong assumptions \| non-identifiable \| continuous no clusters \| causally unrelated \| differential non-response |
| `simulated_session_date` | U19: the API timestamps are run-time, the simulated date is carried here |

</details>

**Sample** — the first five rows of part 0, as written. Identity-bearing columns would be withheld; this dataset carries none.

| `participant_id` | `person_id` | `pool` | `true_traits` | `planted_segment` | `planted_null_mode` | `response_propensity` | `stated_gap` | `satisficer` | `planted_position_bias` | `planted_context_effect` | `generator` | `gc_mode` | `simulated_session_date` | `test_mode_settings` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 4f7ce564-00d3-4d9b-83ce… | HP-0000001 | HRSD-pool | {"autonomy":0.373931914… | — | False | 0.43608466074793895 | 0.33292477924894825 | False | 0.0 | withheld | G-B | — | — | {"gb_spec_hash":"c53995… |
| e0daf53b-6dde-4390-8862… | HP-0000002 | HRSD-pool | {"autonomy":-0.96653979… | — | False | 0.332503070326863 | 0.28142816508882246 | False | 0.0 | withheld | G-B | — | — | {"gb_spec_hash":"c53995… |
| 665917a9-bdc5-4ca8-bf8d… | HP-0000003 | HRSD-pool | {"autonomy":0.448776423… | — | False | 0.32261794921789333 | 0.26023534681442856 | False | 0.0 | withheld | G-B | — | — | {"gb_spec_hash":"c53995… |
| 84194f49-c87e-492b-bb37… | HP-0000004 | HRSD-pool | {"autonomy":0.025622564… | — | False | 0.3376100306429528 | 0.27773856022183485 | False | 0.0 | withheld | G-B | — | — | {"gb_spec_hash":"c53995… |
| fe7f8784-4ad3-4690-8840… | HP-0000005 | HRSD-pool | {"autonomy":0.899908259… | — | False | 0.4853930442764806 | 0.24972851078489 | True | 0.0 | withheld | G-B | — | — | {"gb_spec_hash":"c53995… |

**Joins**

- `person_id` → D05 persons, D08 states, D09 events, D10 activities

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
| Path | `v1/observable/D27_part*.parquet` (1 part) |
| Format | declared `parquet` ; on disk Parquet |
| Partitioning | none declared ; on disk 1 sequential parts |
| Rows | 50 |
| Size | 15.6 kB |
| Time span | — |
| Resolution | not a time series |
| Primary key | declared `keyed_by: premises` ; id columns on disk: `premises_id` |
| Present for | estate-year (50 rows, 15.6 kB); town14 (1,092 rows, 31.9 kB) |
| Status | **present** — the edge-export contract view is not written by E1's runner |
| Leakage audit | passed: no GT-class or forbidden field names present |
| Part hash | `9e5e098ca46dbdc6…` (part 0) |

**Schema** — types, null counts and ranges from the Parquet footers; descriptions and units from `schema/datasets.yaml`.

| Column | Type | Unit | Nulls | Min | Max | Declared |
|---|---|---|---|---|---|---|
| `premises_id` | string | — | no nulls | MPRN-00B4DDA0621CC6AC64 | MPRN-FECC1C4894CC3DF0C3 | required |
| `valid_from` | timestamp[ns, tz=UTC] | — | no nulls | 2022-01-01 00:00:00+00:00 | 2022-01-01 00:00:00+00:00 | required |
| `valid_to` | timestamp[ns, tz=UTC] | — | 50 null (100.0%) | — | — | optional |
| `supplier` | string | — | no nulls | Baile Nua Synthetic Suppl… | Baile Nua Synthetic Suppl… | required |
| `tariff_code` | string | — | no nulls | BN-SYNTH-24H-EI20220501 | BN-SYNTH-TOU3-EI20241101 | required |
| `tariff_kind` | string | — | no nulls | ToU | flat | required |
| `rate_schedule` | string | — | no nulls | — | — | required |
| `standing_charge_eur_day` | double | — | no nulls | 0.687041 | 0.97663 | required |
| `export_rate_eur_kwh` | double | kWh *(derived)* | no nulls | 0.205 | 0.205 | optional |
| `max_import_kw` | double | kW *(derived)* | no nulls | 12.0 | 12.0 | required |
| `max_export_kw` | double | kW *(derived)* | no nulls | -0.0 | 5.0 | required |
| `der_notification_ref` | string | — | 45 null (90.0%) | SYNTH-DER-MPRN-4E588069FD… | SYNTH-DER-MPRN-B619017C8C… | optional |
| `flex_contract_terms` | string | — | 50 null (100.0%) | — | — | optional |
| `trial_arm` | string | — | 50 null (100.0%) | — | — | optional |

<details><summary>Column descriptions, as declared</summary>

| Column | Declared description |
|---|---|
| `premises_id` | the meter point on the supply contract |
| `valid_from` | the contract start the supplier recorded |
| `valid_to` | the contract end the supplier recorded |
| `supplier` | the supplier of record |
| `tariff_code` | the tariff the account is on |
| `tariff_kind` | flat \| day-night \| ToU \| U10: existing retail tariffs only in the base model |
| `rate_schedule` | the published rate card |
| `standing_charge_eur_day` | the published standing charge |
| `export_rate_eur_kwh` | the published clean-export guarantee rate |
| `max_import_kw` | the connection capacity on the network operator's record |
| `max_export_kw` | the export capacity notified to and accepted by the network operator |
| `der_notification_ref` | the DER notification reference the operator issued |
| `flex_contract_terms` | the aggregator contract terms on file |
| `trial_arm` | the arm this premises was randomised to at recruitment (6.4 item 5) |

</details>

**Sample** — the first five rows of part 0, as written. Identity-bearing columns would be withheld; this dataset carries none.

| `premises_id` | `valid_from` | `valid_to` | `supplier` | `tariff_code` | `tariff_kind` | `rate_schedule` | `standing_charge_eur_day` | `export_rate_eur_kwh` | `max_import_kw` | `max_export_kw` | `der_notification_ref` | `flex_contract_terms` | `trial_arm` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| MPRN-12648450D5BDED39DD | 2022-01-01 00:00:00+00:… | — | Baile Nua Synthetic Sup… | BN-SYNTH-TOU3-EI20241101 | ToU | {"assumption_flags": {"… | 0.687041 | 0.205 | 12.0 | 0.0 | — | — | — |
| MPRN-BD3C756F354C00E282 | 2022-01-01 00:00:00+00:… | — | Baile Nua Synthetic Sup… | BN-SYNTH-NIGHTSAVER-EI2… | day-night | {"assumption_flags": {"… | 0.97663 | 0.205 | 12.0 | 0.0 | — | — | — |
| MPRN-34401714421FC71D21 | 2022-01-01 00:00:00+00:… | — | Baile Nua Synthetic Sup… | BN-SYNTH-TOU3-EI20241101 | ToU | {"assumption_flags": {"… | 0.687041 | 0.205 | 12.0 | 0.0 | — | — | — |
| MPRN-B1500C9DF4503BF2CF | 2022-01-01 00:00:00+00:… | — | Baile Nua Synthetic Sup… | BN-SYNTH-24H-EI20220501 | flat | {"assumption_flags": {"… | 0.745342 | 0.205 | 12.0 | 0.0 | — | — | — |
| MPRN-00B4DDA0621CC6AC64 | 2022-01-01 00:00:00+00:… | — | Baile Nua Synthetic Sup… | BN-SYNTH-24H-EI20220501 | flat | {"assumption_flags": {"… | 0.745342 | 0.205 | 12.0 | 0.0 | — | — | — |

**Joins**

- `premises_id` → D18, D19, D27 to D30 (the meter-boundary identity of a home)

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
| Path | `v1/observable/D28_part*.parquet` (1 part) |
| Format | declared `parquet + protocol document` ; on disk Parquet |
| Partitioning | none declared ; on disk 1 sequential parts |
| Rows | 101 |
| Size | 8.2 kB |
| Time span | — |
| Resolution | not a time series |
| Primary key | declared `keyed_by: premises` ; id columns on disk: `premises_id` |
| Present for | estate-year (101 rows, 8.2 kB); town14 (2,225 rows, 27.5 kB) |
| Status | **present** — built in observation/nonsensor.py and not yet written into a package by the runner; D31 carries weather only (I-072) |
| Leakage audit | passed: no GT-class or forbidden field names present |
| Part hash | `9401376ca12e4c81…` (part 0) |

**Schema** — types, null counts and ranges from the Parquet footers; descriptions and units from `schema/datasets.yaml`.

| Column | Type | Unit | Nulls | Min | Max | Declared |
|---|---|---|---|---|---|---|
| `premises_id` | string | — | no nulls | MPRN-00B4DDA0621CC6AC64 | MPRN-FECC1C4894CC3DF0C3 | required |
| `protocol_event` | string | — | no nulls | consented | withdrew | required |
| `recorded_at` | timestamp[ns, tz=UTC] | — | no nulls | 2022-01-03 00:00:00+00:00 | 2022-10-25 00:00:00+00:00 | required |
| `recruitment_route` | string | — | no nulls | community group | word of mouth | required |
| `consent_sensors` | string | — | 50 null (49.5%) | no | yes | optional |
| `tier_consented` | string | — | 65 null (64.4%) | T1 | T4 | optional |
| `install_delay_days` | int64 | — | 66 null (65.3%) | 3 | 53 | optional |
| `trial_arm` | string | — | 65 null (64.4%) | control | time-of-use tariff | optional |
| `arm_deviation` | string | — | 66 null (65.3%) | crossover | none | optional |
| `withdrawal_reason` | string | — | 101 null (100.0%) | — | — | optional |

<details><summary>Column descriptions, as declared</summary>

| Column | Declared description |
|---|---|
| `premises_id` | the premises the study recorded against |
| `protocol_event` | invited \| responded \| declined \| consented \| installed \| withdrew \| dropped_out \| randomised |
| `recorded_at` | when the study team entered the record, which may lag the event |
| `recruitment_route` | how the household was approached |
| `consent_sensors` | 6.5 rule 3: consent records are sometimes incomplete |
| `tier_consented` | the sensor package the household agreed to |
| `install_delay_days` | the gap between consent and the installer attending |
| `trial_arm` | the arm the randomisation list assigned |
| `arm_deviation` | the study team's note of non-compliance or crossover |
| `withdrawal_reason` | the reason the household gave, where they gave one |

</details>

**Sample** — the first five rows of part 0, as written. Identity-bearing columns would be withheld; this dataset carries none.

| `premises_id` | `protocol_event` | `recorded_at` | `recruitment_route` | `consent_sensors` | `tier_consented` | `install_delay_days` | `trial_arm` | `arm_deviation` | `withdrawal_reason` |
|---|---|---|---|---|---|---|---|---|---|
| MPRN-00B4DDA0621CC6AC64 | invited | 2022-01-07 00:00:00+00:… | letter to the meter-poi… | — | — | — | — | — | — |
| MPRN-00B4DDA0621CC6AC64 | consented | 2022-03-13 00:00:00+00:… | letter to the meter-poi… | yes | T2 | 48 | feedback | none | — |
| MPRN-03FB1E262BB1CC50A9 | invited | 2022-01-04 00:00:00+00:… | letter to the meter-poi… | — | — | — | — | — | — |
| MPRN-03FB1E262BB1CC50A9 | consented | 2022-03-31 00:00:00+00:… | letter to the meter-poi… | yes | T3 | 25 | control | none | — |
| MPRN-07D5E0C1E09A59AB34 | invited | 2022-02-08 00:00:00+00:… | community group | — | — | — | — | — | — |

**Joins**

- `premises_id` → D18, D19, D27 to D30 (the meter-boundary identity of a home)

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
| Path | `v1/observable/D29_part*.parquet` (1 part) |
| Format | declared `parquet` ; on disk Parquet |
| Partitioning | none declared ; on disk 1 sequential parts |
| Rows | 100 |
| Size | 12.3 kB |
| Time span | — |
| Resolution | not a time series |
| Primary key | declared `keyed_by: premises` ; id columns on disk: `premises_id` |
| Present for | estate-year (100 rows, 12.3 kB); town14 (2,184 rows, 41.1 kB) |
| Status | **present** — built in observation/nonsensor.py and not yet written into a package by the runner; D31 carries weather only (I-072) |
| Leakage audit | passed: no GT-class or forbidden field names present |
| Part hash | `ec0abfff455716e4…` (part 0) |

**Schema** — types, null counts and ranges from the Parquet footers; descriptions and units from `schema/datasets.yaml`.

| Column | Type | Unit | Nulls | Min | Max | Declared |
|---|---|---|---|---|---|---|
| `premises_id` | string | — | no nulls | MPRN-00B4DDA0621CC6AC64 | MPRN-FECC1C4894CC3DF0C3 | required |
| `wave` | int64 | — | no nulls | 1 | 2 | required |
| `responded_at` | timestamp[ns, tz=UTC] | — | 25 null (25.0%) | 2022-03-02 00:00:00+00:00 | 2023-04-12 00:00:00+00:00 | optional |
| `q_household_size` | int64 | — | 25 null (25.0%) | 1 | 7 | optional |
| `q_children_under_18` | int64 | — | 30 null (30.0%) | 0 | 3 | optional |
| `q_occupied_weekday_hours` | double | — | 28 null (28.0%) | 14.0 | 24.0 | optional |
| `q_dwelling_type` | string | — | 27 null (27.0%) | apartment | terraced | optional |
| `q_heating_system` | string | — | 29 null (29.0%) | direct electric | gas boiler | optional |
| `q_has_pv` | string | — | 25 null (25.0%) | don't know | yes | optional |
| `q_has_ev` | string | — | 25 null (25.0%) | don't know | yes | optional |
| `q_appliances.list.element` | BYTE_ARRAY | — | 25 null (25.0%) | dishwasher | washing_machine | leaf of `q_appliances` |
| `q_env_behaviour_score` | int64 | — | 29 null (29.0%) | 3 | 5 | optional |
| `q_comfort_preference_c` | double | degC *(derived)* | 30 null (30.0%) | 18.5 | 21.9 | optional |
| `straightlined` | bool | — | no nulls | False | True | required |
| `item_nonresponse_count` | int64 | — | no nulls | 0 | 2 | required |

A dotted name is a leaf of a struct column: the Parquet footer flattens a struct, so the file physically carries the leaves while the dataset logically carries the parent.

<details><summary>Column descriptions, as declared</summary>

| Column | Declared description |
|---|---|
| `premises_id` | the premises the questionnaire was sent to |
| `wave` | the survey wave the study ran |
| `responded_at` | when the respondent submitted; null for unit non-response |
| `q_household_size` | the respondent's own count of people in the home |
| `q_children_under_18` | the respondent's answer |
| `q_occupied_weekday_hours` | optimistic occupancy is a calibrated bias (6.5 rule 3) |
| `q_dwelling_type` | the respondent's answer |
| `q_heating_system` | the respondent's answer, which may be out of date |
| `q_has_pv` | the respondent's recollection |
| `q_has_ev` | the respondent's recollection |
| `q_appliances` | the respondent ticking a list, with omissions |
| `q_env_behaviour_score` | over-reported by design (6.5 rule 3) |
| `q_comfort_preference_c` | the respondent's stated preferred temperature |
| `straightlined` | derived by the survey platform from answer variance, as a real platform would flag it |
| `item_nonresponse_count` | count of items the respondent left blank |

</details>

**Sample** — the first five rows of part 0, as written. Identity-bearing columns would be withheld; this dataset carries none.

| `premises_id` | `wave` | `responded_at` | `q_household_size` | `q_children_under_18` | `q_occupied_weekday_hours` | `q_dwelling_type` | `q_heating_system` | `q_has_pv` | `q_has_ev` | `q_appliances` | `q_env_behaviour_score` | `q_comfort_preference_c` | `straightlined` | `item_nonresponse_count` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| MPRN-00B4DDA0621CC6AC64 | 1 | 2022-03-13 00:00:00+00:… | 5 | 2 | 18.5 | detached | gas boiler | no | no | ['dishwasher', 'fridge_… | 3 | 21.0 | False | 0 |
| MPRN-00B4DDA0621CC6AC64 | 2 | 2023-03-05 00:00:00+00:… | 4 | 2 | 21.5 | detached | — | no | no | ['extractor_fan', 'frid… | 3 | 21.9 | False | 1 |
| MPRN-03FB1E262BB1CC50A9 | 1 | 2022-03-03 00:00:00+00:… | 4 | 2 | 24.0 | — | direct electric | no | don't know | ['dishwasher', 'electri… | 4 | 21.2 | False | 1 |
| MPRN-03FB1E262BB1CC50A9 | 2 | — | — | — | — | — | — | — | — | — | — | — | False | 0 |
| MPRN-07D5E0C1E09A59AB34 | 1 | — | — | — | — | — | — | — | — | — | — | — | False | 0 |

**Joins**

- `premises_id` → D18, D19, D27 to D30 (the meter-boundary identity of a home)
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
| Path | `v1/observable/D30_part*.parquet` (1 part) |
| Format | declared `parquet` ; on disk Parquet |
| Partitioning | none declared ; on disk 1 sequential parts |
| Rows | 50 |
| Size | 11.8 kB |
| Time span | — |
| Resolution | not a time series |
| Primary key | declared `keyed_by: premises` ; id columns on disk: `premises_id` |
| Present for | estate-year (50 rows, 11.8 kB); town14 (1,092 rows, 37.1 kB) |
| Status | **present** — built in observation/nonsensor.py and not yet written into a package by the runner; D31 carries weather only (I-072) |
| Leakage audit | passed: no GT-class or forbidden field names present |
| Part hash | `8e1247642e2094c4…` (part 0) |

**Schema** — types, null counts and ranges from the Parquet footers; descriptions and units from `schema/datasets.yaml`.

| Column | Type | Unit | Nulls | Min | Max | Declared |
|---|---|---|---|---|---|---|
| `premises_id` | string | — | no nulls | MPRN-00B4DDA0621CC6AC64 | MPRN-FECC1C4894CC3DF0C3 | required |
| `record_version` | int64 | — | no nulls | 1 | 1 | required |
| `recorded_at` | timestamp[ns, tz=UTC] | — | no nulls | 2015-06-01 00:00:00+00:00 | 2015-06-01 00:00:00+00:00 | required |
| `record_source` | string | — | no nulls | BER assessment | operator file | required |
| `rec_ber_band` | string | — | no nulls | A1 | C3 | optional |
| `rec_ber_kwh_m2_yr` | double | — | 3 null (6.0%) | 0.48 | 224.75 | optional |
| `rec_floor_area_m2` | double | — | no nulls | 52.71 | 952.2 | optional |
| `rec_dwelling_type` | string | — | no nulls | apartment | terraced | optional |
| `rec_build_year` | int64 | — | 4 null (8.0%) | 1983 | 2015 | optional |
| `rec_heating_system` | string | — | 3 null (6.0%) | gas boiler | gas boiler | optional |
| `rec_pv_kwp` | double | — | 45 null (90.0%) | 3.459720080089999 | 6.096606669673275 | optional |
| `rec_pv_install_date` | timestamp[ns] | — | 50 null (100.0%) | — | — | optional |
| `rec_pv_azimuth_deg` | double | — | 45 null (90.0%) | 135.0 | 180.0 | optional |
| `rec_shading` | string | — | 50 null (100.0%) | — | — | optional |
| `record_conflict` | string | — | 43 null (86.0%) | assessor vs installer on … | two floor areas on file | optional |
| `asset_since_removed` | bool | — | no nulls | False | True | required |

<details><summary>Column descriptions, as declared</summary>

| Column | Declared description |
|---|---|
| `premises_id` | the premises the record is filed against |
| `record_version` | the version of the administrative record |
| `recorded_at` | when the assessor or installer filed it |
| `record_source` | BER assessor \| installer \| operator \| self-declared |
| `rec_ber_band` | the band on the published BER certificate, which predates any later retrofit |
| `rec_ber_kwh_m2_yr` | the figure on the certificate |
| `rec_floor_area_m2` | subject to m2/ft2 unit errors (6.5 rule 3) |
| `rec_dwelling_type` | the assessor's classification |
| `rec_build_year` | the year on the record |
| `rec_heating_system` | the system recorded at assessment |
| `rec_pv_kwp` | subject to kW/kWp confusion |
| `rec_pv_install_date` | the date on the notification |
| `rec_pv_azimuth_deg` | the orientation the installer recorded, at release-level coarseness |
| `rec_shading` | the installer's shading note |
| `record_conflict` | a note where two sources disagree (assessor against installer) |
| `asset_since_removed` | true where the record still lists an asset that has since gone, because nobody told the register |

</details>

**Sample** — the first five rows of part 0, as written. Identity-bearing columns would be withheld; this dataset carries none.

| `premises_id` | `record_version` | `recorded_at` | `record_source` | `rec_ber_band` | `rec_ber_kwh_m2_yr` | `rec_floor_area_m2` | `rec_dwelling_type` | `rec_build_year` | `rec_heating_system` | `rec_pv_kwp` | `rec_pv_install_date` | `rec_pv_azimuth_deg` | `rec_shading` | `record_conflict` | `asset_since_removed` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| MPRN-00B4DDA0621CC6AC64 | 1 | 2015-06-01 00:00:00+00:… | BER assessment | A3 | 52.28 | 113.68 | detached | 2010 | gas boiler | — | — | — | — | — | False |
| MPRN-03FB1E262BB1CC50A9 | 1 | 2015-06-01 00:00:00+00:… | operator file | B3 | 147.4 | 68.09 | apartment | 2008 | — | — | — | — | — | — | False |
| MPRN-07D5E0C1E09A59AB34 | 1 | 2015-06-01 00:00:00+00:… | BER assessment | C2 | 186.48 | 115.94 | semi-detached | — | gas boiler | — | — | — | — | assessor vs installer o… | False |
| MPRN-125C76166B6EE7008F | 1 | 2015-06-01 00:00:00+00:… | BER assessment | B3 | 143.46 | 135.19 | detached | 2009 | gas boiler | — | — | — | — | — | False |
| MPRN-12648450D5BDED39DD | 1 | 2015-06-01 00:00:00+00:… | BER assessment | B3 | 131.98 | 111.22 | semi-detached | 2004 | gas boiler | — | — | — | — | — | False |

**Joins**

- `premises_id` → D18, D19, D27 to D30 (the meter-boundary identity of a home)
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
| Path | `v1/observable/D31_part*.parquet` (1 part) |
| Format | declared `parquet` ; on disk Parquet |
| Partitioning | none declared ; on disk 1 sequential parts |
| Rows | 70,080 |
| Size | 168.5 kB |
| Time span | `ts` 2022-01-01 00:00:00+00:00 → 2022-12-31 23:00:00+00:00 |
| Resolution | not derived |
| Primary key | grain `series-native` ; id columns on disk: `series_id`, `ts`, `realisation_id` |
| Present for | estate-year (70,080 rows, 168.5 kB); town14 (2,688 rows, 12.2 kB) |
| Status | **present** — built in observation/nonsensor.py and not yet written into a package by the runner; D31 carries weather only (I-072) |
| Leakage audit | passed: no GT-class or forbidden field names present |
| Part hash | `57f8fec156ef3916…` (part 0) |

**Schema** — types, null counts and ranges from the Parquet footers; descriptions and units from `schema/datasets.yaml`.

| Column | Type | Unit | Nulls | Min | Max | Declared |
|---|---|---|---|---|---|---|
| `series_id` | string | — | no nulls | station.cloud_oktas | station.wind_speed_ms | required |
| `ts` | timestamp[ns, tz=UTC] | — | no nulls | 2022-01-01 00:00:00+00:00 | 2022-12-31 23:00:00+00:00 | required |
| `value` | double | — | 18 null (0.0%) | -5.3 | 1043.4 | optional |
| `unit` | string | — | no nulls | degC | percent | required |
| `station_or_zone` | string | — | no nulls | ROCHES_POINT | ROCHES_POINT | required |
| `quality` | string | — | no nulls | estimated | ok | required |
| `provenance` | string | — | no nulls | interpolated | metered | required |
| `revision` | int64 | — | no nulls | 0 | 1 | required |
| `realisation_id` | string | — | no nulls | REAL-2022-20261008 | REAL-2022-20261008 | required |
| `segment` | string | — | no nulls | real_historical | real_historical | required |

<details><summary>Column descriptions, as declared</summary>

| Column | Declared description |
|---|---|
| `series_id` | the publisher's own series identifier |
| `ts` | the publisher's timestamp, on the publisher's interval convention |
| `value` | the published value; null during a station outage or publication gap |
| `unit` | as published |
| `station_or_zone` | 6.4 item 7: the nearest official station, not the true site microclimate |
| `quality` | the publisher's quality flag, including gap-filled values |
| `provenance` | measured, estimated or interpolated, as the publisher states |
| `revision` | the publication revision; prices and demand are revised after the fact |
| `realisation_id` | the weather realisation this series is consistent with (6.5 rule 2: one realisation drives everything) |
| `segment` | real historical \| generated projection (6.5 rule 2) |

</details>

**Sample** — the first five rows of part 0, as written. Identity-bearing columns would be withheld; this dataset carries none.

| `series_id` | `ts` | `value` | `unit` | `station_or_zone` | `quality` | `provenance` | `revision` | `realisation_id` | `segment` |
|---|---|---|---|---|---|---|---|---|---|
| station.cloud_oktas | 2022-01-01 00:00:00+00:… | 3.0 | oktas | ROCHES_POINT | ok | metered | 0 | REAL-2022-20261008 | real_historical |
| station.cloud_oktas | 2022-01-01 01:00:00+00:… | 7.0 | oktas | ROCHES_POINT | ok | metered | 0 | REAL-2022-20261008 | real_historical |
| station.cloud_oktas | 2022-01-01 02:00:00+00:… | 6.0 | oktas | ROCHES_POINT | ok | metered | 0 | REAL-2022-20261008 | real_historical |
| station.cloud_oktas | 2022-01-01 03:00:00+00:… | 7.0 | oktas | ROCHES_POINT | ok | metered | 0 | REAL-2022-20261008 | real_historical |
| station.cloud_oktas | 2022-01-01 04:00:00+00:… | 7.0 | oktas | ROCHES_POINT | ok | metered | 0 | REAL-2022-20261008 | real_historical |

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
v1/       789.9 MB   total
├── evidence/                  1.7 MB
│   ├── wp5_tenyear.json                 1 file(s)   395.5 kB
│   ├── assumption_sweep_u30.json        1 file(s)   268.5 kB
│   ├── e1_gate_report.json              1 file(s)   175.6 kB
│   ├── d24_calibration_targets.json     1 file(s)   113.5 kB
│   ├── junit.xml                        1 file(s)   101.4 kB
│   ├── w2_steps6to9.json                1 file(s)    47.3 kB
│   ├── data_dictionary.md               1 file(s)    46.1 kB
│   ├── delivery_packages.json           1 file(s)    42.5 kB
│   └── … 38 further name pattern(s)       38 file(s)   501.3 kB
├── ground_truth/            205.0 MB
│   ├── D16_part*.parquet               13 file(s)   122.8 MB
│   ├── D13_part*.parquet               13 file(s)    34.7 MB
│   ├── D15_part*.parquet                1 file(s)    23.5 MB
│   ├── D10_part*.parquet               13 file(s)    13.5 MB
│   ├── D26_part*.parquet                1 file(s)     1.9 MB
│   ├── D11_part*.parquet                1 file(s)   490.6 kB
│   ├── D05_part*.parquet                1 file(s)    58.1 kB
│   ├── D21_part*.parquet                1 file(s)    39.7 kB
│   └── … 24 further name pattern(s)       60 file(s)   181.0 kB
├── observable/              583.0 MB
│   ├── D18_part*.parquet               13 file(s)   506.4 MB
│   ├── D19_part*.parquet               13 file(s)    71.1 MB
│   ├── D25_part*.parquet                1 file(s)     2.6 MB
│   ├── D31_part*.parquet                1 file(s)   168.5 kB
│   ├── D27_part*.manifest.json          1 file(s)    37.2 kB
│   ├── D27_part*.parquet                1 file(s)    15.6 kB
│   ├── D29_part*.parquet                1 file(s)    12.3 kB
│   ├── D30_part*.parquet                1 file(s)    11.8 kB
│   └── … 10 further name pattern(s)       34 file(s)    54.2 kB
├── .DS_Store                  8.0 kB
├── SUPERSEDED.md              3.0 kB
└── run_diagnostics.json      95.5 kB
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

| Dataset | Title | Class | Status | Present for another run? | Rows found elsewhere | Reason recorded on disk |
|---|---|---|---|---|---|---|
| D12 | Origin, destination, mode, vehicle, distance | GT | missing | no | none | — |
| D24 | Every empirical target with source, version and tolerance | META | partial | no | v1/evidence/d24_calibration_targets.json (113… | — |

### D.2 Declared columns absent from the rows that exist

Covers present datasets, where the comparison is against the Parquet schema, and partial ones, where it is against the keys of the rows held in an evidence artefact.

| Dataset | Declared column | Required | Compared against |
|---|---|---|---|
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
| D01 | geoparquet | Parquet |
| D12 | parquet | absent |
| D16 | re-run on demand (U07 option b, decision D-009); hot slices cached | Parquet |
| D18 | rendered on demand; cached slices | Parquet |
| D21 | json | Parquet |
| D22 | parquet + npz | Parquet |
| D23 | json | Parquet |
| D24 | parquet + citation file | JSON inside an evidence artefact |
| D25 | MIMIC MySQL via the public API; Parquet copy | Parquet |
| D28 | parquet + protocol document | Parquet |

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

Generated by `scripts/baile_nua/report/datasets_md.py` at 2026-10-15T11:31:27 from git `0a56db5463af`. Read-only on `v1/`.

