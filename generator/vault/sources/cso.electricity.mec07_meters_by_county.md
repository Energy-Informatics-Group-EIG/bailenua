---
type: "source"
id: "cso.electricity.mec07_meters_by_county"
status: "calibration"
tags:
  - "exposure/none"
  - "source"
  - "use/calibration"
publisher: "Central Statistics Office (Ireland), from ESB Networks"
licence_summary: "CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/)"
sha256_prefix: "416f7db8540b"
bytes: 10849
retrieved: "2026-10-08"
intended_use: "calibration"
model_development_exposure: "none"
in_register: true
generated_by: "scripts/build_vault.py"
---

# cso.electricity.mec07_meters_by_county

Residential and Non-Residential Electricity Meters by county and year (MEC07)

| | |
|---|---|
| Publisher | Central Statistics Office (Ireland), from ESB Networks |
| Licence | CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/) |
| File | `cso_electricity/MEC07_residential_and_nonresidential_meters_by_county.json` |
| Bytes | 10,849 |
| SHA-256 prefix | `416f7db8540b…` |
| Retrieved | 2026-10-08 |
| Intended use | calibration — Allowed to shape parameters (design 7.1 calibration sources) |
| Model-development exposure | none |
| In the register | yes |
| Manifest | `sources/cso_electricity/MEC07_residential_and_nonresidential_meters_by_county.json.manifest.json` |

## Datasets that use it

—

## Used for

The denominator that makes MEC03 usable, and the geographically matched aggregate target: MEC03's Co. Cork residential GWh divided by MEC07's Co. Cork residential meter count is mean annual kWh per residential meter in Cobh's own county for 2022. Design 6.4 keys the observable layer to the PREMISES (meter point), so a per-meter figure is the one that compares to what the model emits - a per-household figure would not, because a vacant dwelling still has a meter.

## Touched by

*Nothing recorded.*
