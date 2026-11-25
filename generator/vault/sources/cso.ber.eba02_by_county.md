---
type: "source"
id: "cso.ber.eba02_by_county"
status: "calibration"
tags:
  - "exposure/none"
  - "source"
  - "use/calibration"
publisher: "Central Statistics Office (Ireland), from the SEAI BER register"
licence_summary: "CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/)"
sha256_prefix: "031f0fcf64cd"
bytes: 33493066
retrieved: "2026-10-08"
intended_use: "calibration"
model_development_exposure: "none"
datasets:
  - "D02"
in_register: true
generated_by: "scripts/build_vault.py"
---

# cso.ber.eba02_by_county

Domestic Building Energy Rating by BER band, dwelling type, heating fuel, year of construction and county (EBA02)

| | |
|---|---|
| Publisher | Central Statistics Office (Ireland), from the SEAI BER register |
| Licence | CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/) |
| File | `seai/EBA02_domestic_ber_by_county.json` |
| Bytes | 33,493,066 |
| SHA-256 prefix | `031f0fcf64cd…` |
| Retrieved | 2026-10-08 |
| Intended use | calibration — Allowed to shape parameters (design 7.1 calibration sources) |
| Model-development exposure | none |
| In the register | yes |
| Manifest | `sources/seai/EBA02_domestic_ber_by_county.json.manifest.json` |

## Datasets that use it

[[D02]]

## Used for

Closes I-011. SAPS Table 6.1 publishes only House/Bungalow vs Flat/Apartment, but the schema's dwelling_type enum, the archetype library (5.7) and U18's 'Terraced' gap all need houses split into detached, semi-detached and terraced. EBA02 gives that split for Co. Cork, crossed with BER band and year of construction, so D02's BER and fabric parameters are conditioned on real Irish data rather than on an assumption. The house/apartment RATIO stays anchored to the Census marginal; BER supplies only the within-house split.

## Touched by

| | |
|---|---|
| Issues | [[I-011]] |
