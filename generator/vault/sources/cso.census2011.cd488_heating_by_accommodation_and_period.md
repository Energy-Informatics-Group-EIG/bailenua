---
type: "source"
id: "cso.census2011.cd488_heating_by_accommodation_and_period"
status: "validation"
tags:
  - "exposure/none"
  - "source"
  - "use/validation"
publisher: "Central Statistics Office (Ireland)"
licence_summary: "CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/)"
sha256_prefix: "b544bb57ae80"
bytes: 9879
retrieved: "2026-10-09"
intended_use: "validation"
model_development_exposure: "none"
in_register: true
generated_by: "scripts/build_vault.py"
---

# cso.census2011.cd488_heating_by_accommodation_and_period

Census 2011 CD488: private households by type of private accommodation, type of central heating and period built

| | |
|---|---|
| Publisher | Central Statistics Office (Ireland) |
| Licence | CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/) |
| File | `cso_housing/CD488_central_heating_by_accommodation_and_period_2011.json` |
| Bytes | 9,879 |
| SHA-256 prefix | `b544bb57ae80…` |
| Retrieved | 2026-10-09 |
| Intended use | validation — Never used for calibration; splits fixed and hashed in D24 before comparison |
| Model-development exposure | none |
| In the register | yes |
| Manifest | `sources/cso_housing/CD488_central_heating_by_accommodation_and_period_2011.json.manifest.json` |

## Datasets that use it

—

## Used for

U30: the public joint behind I-011's assumed dwelling-type x heating-fuel split. To be used in the week 3 fabric and heating work, not before.

## Substitute flag

[A] retained: the joint is 2011, eleven years before T0, so it constrains the STRUCTURE (which fuels go with which dwelling type and era) and not the 2022 levels, which come from SAPS 2022

## Touched by

| | |
|---|---|
| Assumptions | [[A-12]] |
| Issues | [[I-011]] |
