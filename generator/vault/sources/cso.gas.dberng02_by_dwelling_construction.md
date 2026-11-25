---
type: "source"
id: "cso.gas.dberng02_by_dwelling_construction"
status: "calibration"
tags:
  - "exposure/none"
  - "source"
  - "use/calibration"
publisher: "Central Statistics Office (Ireland), from matched BER and Gas Networks Ireland meter data"
licence_summary: "CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/)"
sha256_prefix: "39dd29fe62df"
bytes: 4641
retrieved: "2026-10-09"
intended_use: "calibration"
model_development_exposure: "none"
datasets:
  - "D02"
in_register: true
generated_by: "scripts/build_vault.py"
---

# cso.gas.dberng02_by_dwelling_construction

Mean Gas Consumption by type of dwelling, period of construction and year (DBERNG02)

| | |
|---|---|
| Publisher | Central Statistics Office (Ireland), from matched BER and Gas Networks Ireland meter data |
| Licence | CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/) |
| File | `cso_electricity/DBERNG02_mean_gas_by_dwelling_and_construction.json` |
| Bytes | 4,641 |
| SHA-256 prefix | `39dd29fe62df…` |
| Retrieved | 2026-10-09 |
| Intended use | calibration — Allowed to shape parameters (design 7.1 calibration sources) |
| Model-development exposure | none |
| In the register | yes |
| Manifest | `sources/cso_electricity/DBERNG02_mean_gas_by_dwelling_and_construction.json.manifest.json` |

## Datasets that use it

[[D02]]

## Used for

The held-out half of the heating check, mirroring DBEREL02 exactly: dwelling type crossed with period of construction, an axis no fix was fitted to, and one D02 already carries as year_built_band. Keeping the same tuned/held-out split on both the gas and the electricity side is what lets the E1 report say whether the device and physics layers generalise rather than only that they were fitted. Exposure stays 'none' and must stay 'none'.

## Touched by

| | |
|---|---|
| Assumptions | [[A-18]] |
