---
type: "source"
id: "cso.population.pea01_population_estimates_by_age_sex"
status: "calibration"
tags:
  - "exposure/none"
  - "source"
  - "use/calibration"
publisher: "Central Statistics Office (Ireland)"
licence_summary: "CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/)"
sha256_prefix: "1a45b0d605dc"
bytes: 40608
retrieved: "2026-10-10"
intended_use: "calibration"
model_development_exposure: "none"
in_register: true
generated_by: "scripts/build_vault.py"
---

# cso.population.pea01_population_estimates_by_age_sex

PEA01: population estimates (persons in April) by year, age group and sex

| | |
|---|---|
| Publisher | Central Statistics Office (Ireland) |
| Licence | CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/) |
| File | `cso_vitalstats/PEA01_population_estimates_by_age_group_and_sex.json` |
| Bytes | 40,608 |
| SHA-256 prefix | `1a45b0d605dc…` |
| Retrieved | 2026-10-10 |
| Intended use | calibration — Allowed to shape parameters (design 7.1 calibration sources) |
| Model-development exposure | none |
| In the register | yes |
| Manifest | `sources/cso_vitalstats/PEA01_population_estimates_by_age_group_and_sex.json.manifest.json` |

## Datasets that use it

—

## Used for

WP5 mortality hazard, denominator. Paired with VSA08 on the same year and the same age groups this makes the age- and sex-specific death rate a RATIO OF TWO PUBLISHED NUMBERS, with no population estimate of our own in it.

## Touched by

| | |
|---|---|
| Assumptions | [[A-25]] |
