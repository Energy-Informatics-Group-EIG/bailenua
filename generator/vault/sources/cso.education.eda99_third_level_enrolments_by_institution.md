---
type: "source"
id: "cso.education.eda99_third_level_enrolments_by_institution"
status: "calibration"
tags:
  - "exposure/design"
  - "source"
  - "use/calibration"
publisher: "Central Statistics Office (Ireland)"
licence_summary: "CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/)"
sha256_prefix: "433ce54d0bd9"
bytes: 20000
retrieved: "2026-10-11"
intended_use: "calibration"
model_development_exposure: "design"
in_register: true
generated_by: "scripts/build_vault.py"
---

# cso.education.eda99_third_level_enrolments_by_institution

EDA99: students enrolled in and entrants to third level courses, by institution

| | |
|---|---|
| Publisher | Central Statistics Office (Ireland) |
| Licence | CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/) |
| File | `cso_venues/EDA99_third_level_enrolments_by_institution.json` |
| Bytes | 20,000 |
| SHA-256 prefix | `433ce54d0bd9…` |
| Retrieved | 2026-10-11 |
| Intended use | calibration — Allowed to shape parameters (design 7.1 calibration sources) |
| Model-development exposure | design |
| In the register | yes |
| Manifest | `sources/cso_venues/EDA99_third_level_enrolments_by_institution.json.manifest.json` |

## Datasets that use it

—

## Used for

WP7 venues. Full-time enrolment at National University of Ireland, Cork, which sizes the college venue the town's 19-and-over students attend. Exposure `design` and not `none`: the venue capacity is DERIVED from it, so it can never afterwards validate venue occupancy (7.1, I-058).

## Touched by

| | |
|---|---|
| Issues | [[I-058]] |
