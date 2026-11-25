---
type: "source"
id: "cso.census.f1054_economic_status_by_age_group"
status: "validation"
tags:
  - "exposure/design"
  - "source"
  - "use/validation"
publisher: "Central Statistics Office (Ireland)"
licence_summary: "CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/)"
sha256_prefix: "29981f29a949"
bytes: 10781
retrieved: "2026-10-11"
intended_use: "validation"
model_development_exposure: "design"
in_register: true
generated_by: "scripts/build_vault.py"
---

# cso.census.f1054_economic_status_by_age_group

F1054: population aged 15 years and over, by principal economic status and age group

| | |
|---|---|
| Publisher | Central Statistics Office (Ireland) |
| Licence | CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/) |
| File | `cso_population/F1054_principal_economic_status_by_age_group.json` |
| Bytes | 10,781 |
| SHA-256 prefix | `29981f29a949…` |
| Retrieved | 2026-10-11 |
| Intended use | validation — Never used for calibration; splits fixed and hashed in D24 before comparison |
| Model-development exposure | design |
| In the register | yes |
| Manifest | `sources/cso_population/F1054_principal_economic_status_by_age_group.json.manifest.json` |

## Datasets that use it

—

## Used for

Design 5.2 joint population validation. The person-level joint of age and principal economic status, compared cell by cell against the synthesised town. It found I-069: the population matched every marginal and had the joint wrong by a third. NOT INDEPENDENT since I-069's fix. It shares underlying Census 2022 counts with FY047B, which the population is now fitted to - proven by the identical 4,136,852 national 15+ total and by each table partitioning the State. A pass against it is a CONSISTENCY CHECK and belongs in the calibration-exposed table, not the independent one.

## Touched by

| | |
|---|---|
| Issues | [[I-069]] |
