---
type: "index"
id: "MOC_Datasets"
status: "generated"
tags:
  - "index"
  - "moc"
count: 32
schema_version: "1.0.0"
design_revision: 3
generated_by: "scripts/build_vault.py"
---

# MOC — Datasets

32 datasets declared in `scripts/baile_nua/schema/datasets.yaml` at schema version 1.0.0, design revision 3.

## OBS — [[tier_OBS]]

| dataset | title | package | status | rows |
|---|---|---|---|---|
| [[D17_aggregate]] | D17's observable view: connection register, asset ratings, feeder-head and substation … | Observable | present | 158,340 |
| [[D18]] | Rendered device readings with noise and gaps | Observable | present | 66,097,553 |
| [[D19]] | What leaves each home: aggregates, energy profile, flexibility compliance | Observable | present | 3,521,520 |
| [[D25]] | HRSD participants, profiles, MCV, sessions and responses in MIMIC schema 1.1 | Observable | present | 294,695 |
| [[D27]] | Supplier tariff, ToU and export rates, switches, flexibility and P2P terms, connection … | Observable | present — the edge-export contract view is not written by E1's runner | 50 |
| [[D28]] | Recruitment, response rates, consent to sensors, dropouts, trial arms and periods | Observable | present — built in observation/nonsensor.py and not yet written into a package by the runner; D31 carries weather only (I-072) | 101 |
| [[D29]] | Questionnaire answers with calibrated reporting error and non-response | Observable | present — built in observation/nonsensor.py and not yet written into a package by the runner; D31 carries weather only (I-072) | 100 |
| [[D30]] | Recorded building and asset data, stale or wrong at realistic rates | Observable | present — built in observation/nonsensor.py and not yet written into a package by the runner; D31 carries weather only (I-072) | 50 |
| [[D31]] | Station weather, wholesale prices, carbon intensity, system demand, flex events | Observable | present — built in observation/nonsensor.py and not yet written into a package by the runner; D31 carries weather only (I-072) | 70,080 |

## GT — [[tier_GT]]

| dataset | title | package | status | rows |
|---|---|---|---|---|
| [[D01]] | Parcels, streets, venues, network topology | Ground truth | present | 96 |
| [[D02]] | HRSD_Buildings: fabric, archetype, BER, systems, physics parameters | Ground truth | present | 50 |
| [[D03]] | Dated building events (extension, retrofit, asset added or removed) | Ground truth (+ observable view) | present | 45 |
| [[D04]] | Appliances, heating, PV, BESS, chargers, vehicles, with owner and lifetime | Ground truth | missing | — |
| [[D05]] | HRSD_Occupants: persistent characteristics and trait vector | Ground truth | present | 147 |
| [[D06]] | Who lives where, from when to when | Ground truth | present | 147 |
| [[D07]] | Kin, partner, carer, friend, co-worker edges | Ground truth | present | 205 |
| [[D08]] | Evolving states, slowly changing (SCD-2) | Ground truth | present | 147 |
| [[D09]] | Births, deaths, moves, jobs, health states, decisions | Ground truth | present | 250 |
| [[D10]] | Person activity intervals with location and co-participants | Ground truth | present | 1,431,181 |
| [[D11]] | Person location intervals - the no-double-occupancy source | Ground truth | present | 54,301 |
| [[D12]] | Origin, destination, mode, vehicle, distance | Ground truth | missing | — |
| [[D13]] | Cycle start/end, programme, signature ID, energy | Ground truth | present | 1,449,871 |
| [[D14]] | Event instances, phases, footprint, attendance | Ground truth | present | 244 |
| [[D15]] | True site weather and solar geometry driving physics and behaviour | Ground truth | present | 525,600 |
| [[D16]] | Zone temps, RH, CO2, DHW, heat delivered | Ground truth | present | 1,752,000 |
| [[D17]] | Feeder and transformer loading, voltages, outages | Ground truth (+ observable view) | present | 157,248 |
| [[D20]] | Ground-truth labels for detector scoring (onset, type, persistence) | Ground truth | present | 253 |
| [[D21]] | Human-readable narratives generated from D05 to D09 | Ground truth | present | 294 |
| [[D26]] | Crosswalk to person_id, true traits, planted segments, propensity, gap, test settings | Ground truth | present | 23,456 |

## META — [[tier_META]]

| dataset | title | package | status | rows |
|---|---|---|---|---|
| [[D22]] | Appliance waveform templates and variation parameters | Evidence | present | 19 |
| [[D23]] | Code and data versions, parameters, seeds, checksums | Evidence | present | 1 |
| [[D24]] | Every empirical target with source, version and tolerance | Evidence | partial | 113 (in an evidence artefact) |

## Keys

Appendix B of `DATASETS.md` names these join keys: `building_id`, `household_id`, `person_id`, `premises_id`, `signature_id`, `small_area`, `timestamp`

Declaring dataset per key, derived from the schema's `id_prefix` and grain (and, for `premises_id`, from Appendix B's prose):

| key | declared by |
|---|---|
| `asset_id` | [[D04]] |
| `building_id` | [[D02]] |
| `device_id` | [[D18]] |
| `edge_id` | [[D07]] |
| `event_id` | [[D09]] |
| `feature_id` | [[D01]] |
| `household_id` | [[D06]] |
| `participant_id` | [[D25]] |
| `person_id` | [[D05]] |
| `premises_id` | [[D02]] |
| `run_id` | [[D23]] |
| `series_id` | [[D31]] |
| `signature_id` | [[D22]] |

## Writers

`export/dispatch.py` registers 19 exporters; 8 datasets are streamed by the engine itself.
