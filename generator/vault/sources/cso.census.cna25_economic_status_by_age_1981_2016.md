---
type: "source"
id: "cso.census.cna25_economic_status_by_age_1981_2016"
status: "validation"
tags:
  - "exposure/none"
  - "source"
  - "use/validation"
publisher: "Central Statistics Office (Ireland)"
licence_summary: "CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/)"
sha256_prefix: "15ba6302037b"
bytes: 58853
retrieved: "2026-10-11"
intended_use: "validation"
model_development_exposure: "none"
in_register: true
generated_by: "scripts/build_vault.py"
---

# cso.census.cna25_economic_status_by_age_1981_2016

CNA25: population aged 15 years and over by age group, principal economic status, sex and marital status, 1981 to 2016

| | |
|---|---|
| Publisher | Central Statistics Office (Ireland) |
| Licence | CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/) |
| File | `cso_population/CNA25_economic_status_by_age_group_1981_2016.json` |
| Bytes | 58,853 |
| SHA-256 prefix | `15ba6302037b…` |
| Retrieved | 2026-10-11 |
| Intended use | validation — Never used for calibration; splits fixed and hashed in D24 before comparison |
| Model-development exposure | none |
| In the register | yes |
| Manifest | `sources/cso_population/CNA25_economic_status_by_age_group_1981_2016.json.manifest.json` |

## Datasets that use it

—

## Used for

Design 5.2. The nearest available INDEPENDENT check on the age x economic-status joint after F1054 was reclassified. A DIFFERENT ENUMERATION - Census 2016 - so it cannot share counts with the Census 2022 table the population is fitted to. It shares the INSTRUMENT (self-assessed principal economic status), and the six-year gap means it checks the STRUCTURE of the joint and not its LEVEL: a 2016-to-2022 difference confounds real change with model error. Exposure `none` and nothing is fitted to it.

## Touched by

*Nothing recorded.*
