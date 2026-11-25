---
type: "source"
id: "cso.education.eda49_schools_and_pupils_by_teacher_size"
status: "calibration"
tags:
  - "exposure/design"
  - "source"
  - "use/calibration"
publisher: "Central Statistics Office (Ireland)"
licence_summary: "CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/)"
sha256_prefix: "1a6d0f366364"
bytes: 11990
retrieved: "2026-10-11"
intended_use: "calibration"
model_development_exposure: "design"
in_register: true
generated_by: "scripts/build_vault.py"
---

# cso.education.eda49_schools_and_pupils_by_teacher_size

EDA49: national schools and pupils in national schools, by teacher size of school

| | |
|---|---|
| Publisher | Central Statistics Office (Ireland) |
| Licence | CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/) |
| File | `cso_venues/EDA49_national_schools_and_pupils_by_teacher_size.json` |
| Bytes | 11,990 |
| SHA-256 prefix | `1a6d0f366364…` |
| Retrieved | 2026-10-11 |
| Intended use | calibration — Allowed to shape parameters (design 7.1 calibration sources) |
| Model-development exposure | design |
| In the register | yes |
| Manifest | `sources/cso_venues/EDA49_national_schools_and_pupils_by_teacher_size.json.manifest.json` |

## Datasets that use it

—

## Used for

WP7 venues. Mean pupils per national school, from the published pupil count over the published school count, which sizes the town's school venues. Exposure is `design` and not `none`: the venue capacities are DERIVED from it, so it can never afterwards be used to validate them (7.1, I-058). The number of schools in Cobh and their siting stay [A] (A-50).

## Touched by

| | |
|---|---|
| Assumptions | [[A-50]] |
| Issues | [[I-058]] |
