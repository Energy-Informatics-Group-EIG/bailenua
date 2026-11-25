---
type: "source"
id: "cso.vitalstats.vsa36_births_by_age_and_parity"
status: "calibration"
tags:
  - "exposure/none"
  - "source"
  - "use/calibration"
publisher: "Central Statistics Office (Ireland)"
licence_summary: "CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/)"
sha256_prefix: "bce58378ddc9"
bytes: 87331
retrieved: "2026-10-10"
intended_use: "calibration"
model_development_exposure: "none"
in_register: true
generated_by: "scripts/build_vault.py"
---

# cso.vitalstats.vsa36_births_by_age_and_parity

VSA36: births by year, age of mother at maternity and previous liveborn children

| | |
|---|---|
| Publisher | Central Statistics Office (Ireland) |
| Licence | CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/) |
| File | `cso_vitalstats/VSA36_births_by_age_of_mother_and_parity.json` |
| Bytes | 87,331 |
| SHA-256 prefix | `bce58378ddc9…` |
| Retrieved | 2026-10-10 |
| Intended use | calibration — Allowed to shape parameters (design 7.1 calibration sources) |
| Model-development exposure | none |
| In the register | yes |
| Manifest | `sources/cso_vitalstats/VSA36_births_by_age_of_mother_and_parity.json.manifest.json` |

## Datasets that use it

—

## Used for

WP5 birth hazard, parity dimension: design 5.9 asks for age- AND parity-specific fertility, and VSA104 carries age only. These are counts, so they give the parity SHARE within an age group, which then splits the VSA104 rate.

## Touched by

| | |
|---|---|
| Assumptions | [[A-25]] |
