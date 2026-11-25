---
type: "source"
id: "cso.vitalstats.vsa08_deaths_by_age_and_sex"
status: "calibration"
tags:
  - "exposure/none"
  - "source"
  - "use/calibration"
publisher: "Central Statistics Office (Ireland)"
licence_summary: "CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/)"
sha256_prefix: "a54a0f9f29bf"
bytes: 5851305
retrieved: "2026-10-10"
intended_use: "calibration"
model_development_exposure: "none"
in_register: true
generated_by: "scripts/build_vault.py"
---

# cso.vitalstats.vsa08_deaths_by_age_and_sex

VSA08: deaths occurring by year, sex, cause of death and age group at death

| | |
|---|---|
| Publisher | Central Statistics Office (Ireland) |
| Licence | CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/) |
| File | `cso_vitalstats/VSA08_deaths_occurring_by_age_group_and_sex.json` |
| Bytes | 5,851,305 |
| SHA-256 prefix | `a54a0f9f29bf…` |
| Retrieved | 2026-10-10 |
| Intended use | calibration — Allowed to shape parameters (design 7.1 calibration sources) |
| Model-development exposure | none |
| In the register | yes |
| Manifest | `sources/cso_vitalstats/VSA08_deaths_occurring_by_age_group_and_sex.json.manifest.json` |

## Datasets that use it

—

## Used for

WP5 mortality hazard, numerator: deaths by age group and sex for a recent year (all causes). CEPHA05, the decennial life table, is the only table PxStat publishes as a life table and it stops at 1990, which cannot age a 2022 population.

## Touched by

| | |
|---|---|
| Assumptions | [[A-25]] |
