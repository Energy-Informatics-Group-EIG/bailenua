---
type: "source"
id: "cso.electricity.dbere102_by_dwelling_construction"
status: "calibration"
tags:
  - "exposure/none"
  - "source"
  - "use/calibration"
publisher: "Central Statistics Office (Ireland), from matched BER and ESB Networks meter data"
licence_summary: "CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/)"
sha256_prefix: "9b03f68ba15b"
bytes: 4547
retrieved: "2026-10-08"
intended_use: "calibration"
model_development_exposure: "none"
datasets:
  - "D02"
in_register: true
generated_by: "scripts/build_vault.py"
---

# cso.electricity.dbere102_by_dwelling_construction

Household Electricity Consumption by type of dwelling, period of construction and year (DBEREL02)

| | |
|---|---|
| Publisher | Central Statistics Office (Ireland), from matched BER and ESB Networks meter data |
| Licence | CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/) |
| File | `cso_electricity/DBEREL02_household_electricity_by_dwelling_and_construction.json` |
| Bytes | 4,547 |
| SHA-256 prefix | `9b03f68ba15b…` |
| Retrieved | 2026-10-08 |
| Intended use | calibration — Allowed to shape parameters (design 7.1 calibration sources) |
| Model-development exposure | none |
| In the register | yes |
| Manifest | `sources/cso_electricity/DBEREL02_household_electricity_by_dwelling_and_construction.json.manifest.json` |

## Datasets that use it

[[D02]]

## Used for

The held-out half of the device-layer check. DBEREL01 (dwelling x BER) is what the trigger rates were tuned against, so it cannot also measure whether they generalise. DBEREL02 crosses dwelling type with PERIOD OF CONSTRUCTION instead, a dimension the tuning never saw, and D02 already carries year_built_band, so it scores the same homes on an axis that was not fitted. Exposure stays 'none' and must stay 'none'.

## Touched by

| | |
|---|---|
| Assumptions | [[A-18]] |
