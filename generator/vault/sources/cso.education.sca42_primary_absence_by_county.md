---
type: "source"
id: "cso.education.sca42_primary_absence_by_county"
status: "calibration"
tags:
  - "exposure/none"
  - "source"
  - "use/calibration"
publisher: "Central Statistics Office (Ireland)"
licence_summary: "CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/)"
sha256_prefix: "1942e3fbbb7f"
bytes: 45030
retrieved: "2026-10-10"
intended_use: "calibration"
model_development_exposure: "none"
in_register: true
generated_by: "scripts/build_vault.py"
---

# cso.education.sca42_primary_absence_by_county

SCA42: average percentage of primary school children absent, by year, county, DEIS status and school location

| | |
|---|---|
| Publisher | Central Statistics Office (Ireland) |
| Licence | CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/) |
| File | `cso_events/SCA42_primary_school_absence_by_county.json` |
| Bytes | 45,030 |
| SHA-256 prefix | `1942e3fbbb7f…` |
| Retrieved | 2026-10-10 |
| Intended use | calibration — Allowed to shape parameters (design 7.1 calibration sources) |
| Model-development exposure | none |
| In the register | yes |
| Manifest | `sources/cso_events/SCA42_primary_school_absence_by_county.json.manifest.json` |

## Datasets that use it

—

## Used for

WP6 school-term attendance BOUND. Read carefully: SCA42 is the share of children absent for TWENTY DAYS OR MORE in the school year, which is chronic absence and not a daily absence rate. It therefore bounds the daily school-day attendance probability from below rather than setting it; the daily rate is [A] (calendar_events.py A-41).

## Touched by

| | |
|---|---|
| Assumptions | [[A-41]] |
