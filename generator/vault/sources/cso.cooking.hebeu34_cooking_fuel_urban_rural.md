---
type: "source"
id: "cso.cooking.hebeu34_cooking_fuel_urban_rural"
status: "calibration"
tags:
  - "exposure/tuning"
  - "source"
  - "use/calibration"
publisher: "Central Statistics Office (Ireland)"
licence_summary: "CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/)"
sha256_prefix: "d0a2064ee4f3"
bytes: 2758
retrieved: "2026-10-10"
intended_use: "calibration"
model_development_exposure: "tuning"
in_register: true
generated_by: "scripts/build_vault.py"
---

# cso.cooking.hebeu34_cooking_fuel_urban_rural

HEBEU34: main fuel used for cooking in households, by urban/rural location and type of fuel (2024)

| | |
|---|---|
| Publisher | Central Statistics Office (Ireland) |
| Licence | CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/) |
| File | `cso_plausibility/HEBEU34_main_cooking_fuel_urban_rural.json` |
| Bytes | 2,758 |
| SHA-256 prefix | `d0a2064ee4f3…` |
| Retrieved | 2026-10-10 |
| Intended use | calibration — Allowed to shape parameters (design 7.1 calibration sources) |
| Model-development exposure | tuning |
| In the register | yes |
| Manifest | `sources/cso_plausibility/HEBEU34_main_cooking_fuel_urban_rural.json.manifest.json` |

## Datasets that use it

—

## Used for

U25: the share of gas-connected dwellings that cook with gas, which was a declared assumption at 0.45 until this table was found. Replaces part of sweep flag A-33. TUNING-EXPOSED: the cooking-fuel split is derived from this table, so it cannot afterwards validate that split.

## Substitute flag

Published share is UNCONDITIONAL on having a gas connection; the model needs it conditional, so it is derived with one stated assumption rather than used directly

## Touched by

| | |
|---|---|
| Assumptions | [[A-33]] |
