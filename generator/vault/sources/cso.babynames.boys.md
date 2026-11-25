---
type: "source"
id: "cso.babynames.boys"
status: "calibration"
tags:
  - "exposure/none"
  - "source"
  - "use/calibration"
publisher: "Central Statistics Office (Ireland)"
licence_summary: "CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/)"
sha256_prefix: "5e8a40708dea"
bytes: 38007974
retrieved: "2026-10-08"
intended_use: "calibration"
model_development_exposure: "none"
datasets:
  - "D05"
in_register: true
generated_by: "scripts/build_vault.py"
---

# cso.babynames.boys

Boys' names in Ireland with 3 or more occurrences, by year (VSA50)

| | |
|---|---|
| Publisher | Central Statistics Office (Ireland) |
| Licence | CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/) |
| File | `cso/VSA50_boys_names.csv` |
| Bytes | 38,007,974 |
| SHA-256 prefix | `5e8a40708dea…` |
| Retrieved | 2026-10-08 |
| Intended use | calibration — Allowed to shape parameters (design 7.1 calibration sources) |
| Model-development exposure | none |
| In the register | yes |
| Manifest | `sources/cso/VSA50_boys_names.csv.manifest.json` |

## Datasets that use it

[[D05]]

## Used for

D05.given_name for males. Design 5.2 step 6: 'Draw first names by birth year and origin from CSO baby-name tables'. Covers registration years 1964 to 2025, so a person born in those years gets a name drawn from the frequencies that actually applied in their birth year.

## Touched by

*Nothing recorded.*
