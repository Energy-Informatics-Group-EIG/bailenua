---
type: "source"
id: "cso.census.fy047b_economic_status_by_age_and_county"
status: "calibration"
tags:
  - "exposure/tuning"
  - "source"
  - "use/calibration"
publisher: "Central Statistics Office (Ireland)"
licence_summary: "CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/)"
sha256_prefix: "6364fd592824"
bytes: 421032
retrieved: "2026-10-11"
intended_use: "calibration"
model_development_exposure: "tuning"
in_register: true
generated_by: "scripts/build_vault.py"
---

# cso.census.fy047b_economic_status_by_age_and_county

FY047B: population aged 15 years and over, by county and city, sex, principal economic status and age group

| | |
|---|---|
| Publisher | Central Statistics Office (Ireland) |
| Licence | CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/) |
| File | `cso_population/FY047B_principal_economic_status_by_age_group_and_county.json` |
| Bytes | 421,032 |
| SHA-256 prefix | `6364fd592824…` |
| Retrieved | 2026-10-11 |
| Intended use | calibration — Allowed to shape parameters (design 7.1 calibration sources) |
| Model-development exposure | tuning |
| In the register | yes |
| Manifest | `sources/cso_population/FY047B_principal_economic_status_by_age_group_and_county.json.manifest.json` |

## Datasets that use it

—

## Used for

I-069's fix. The age profile WITHIN each principal economic status for Cork City and Cork County, used to condition the economic-status draw on age in population/synthesise.py. SAPS publishes economic status by sex and small area and NEVER by age, so this is the only way the joint can be fitted at all. Exposure is `tuning` because the population is built from it, so it can never validate the population (7.1, I-058) - F1054 does that, held out.

## Touched by

| | |
|---|---|
| Issues | [[I-058]], [[I-069]] |
