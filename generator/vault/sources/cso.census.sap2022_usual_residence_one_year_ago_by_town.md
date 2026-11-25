---
type: "source"
id: "cso.census.sap2022_usual_residence_one_year_ago_by_town"
status: "calibration"
tags:
  - "exposure/none"
  - "source"
  - "use/calibration"
publisher: "Central Statistics Office (Ireland)"
licence_summary: "CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/)"
sha256_prefix: "bb6f439d3e75"
bytes: 114460
retrieved: "2026-10-11"
intended_use: "calibration"
model_development_exposure: "none"
in_register: true
generated_by: "scripts/build_vault.py"
---

# cso.census.sap2022_usual_residence_one_year_ago_by_town

SAP2022T2T3TOWN22: usually resident population aged 1 year and over by usual residence 1 year before Census Day, by Towns 2022

| | |
|---|---|
| Publisher | Central Statistics Office (Ireland) |
| Licence | CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/) |
| File | `cso_lifecourse/SAP2022T2T3TOWN22_usual_residence_one_year_ago_by_town.json` |
| Bytes | 114,460 |
| SHA-256 prefix | `bb6f439d3e75…` |
| Retrieved | 2026-10-11 |
| Intended use | calibration — Allowed to shape parameters (design 7.1 calibration sources) |
| Model-development exposure | none |
| In the register | yes |
| Manifest | `sources/cso_lifecourse/SAP2022T2T3TOWN22_usual_residence_one_year_ago_by_town.json.manifest.json` |

## Datasets that use it

—

## Used for

U33. A sourced PROXY for the gross household move rate, replacing the unmet internal-consistency criterion on `move_out` in lifecourse/tenyear.py's vital-statistics check. Cobh's own share of residents who were at a different address one year earlier. The person-to-household conversion stays [A] (A-25b): this bounds the hazard, it does not set it. Exposure stays `none` because nothing is fitted to it - the hazard keeps its declared value and this says whether that value is consistent with what the Census observed.

## Touched by

| | |
|---|---|
| Assumptions | [[A-25b]] |
