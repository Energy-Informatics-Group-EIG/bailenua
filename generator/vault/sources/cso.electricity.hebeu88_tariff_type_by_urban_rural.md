---
type: "source"
id: "cso.electricity.hebeu88_tariff_type_by_urban_rural"
status: "reference"
tags:
  - "exposure/none"
  - "source"
  - "use/reference"
publisher: "Central Statistics Office (Ireland)"
licence_summary: "CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/)"
sha256_prefix: "1ce1d554a4d4"
bytes: 2669
retrieved: "2026-10-12"
intended_use: "reference"
model_development_exposure: "none"
datasets:
  - "D27"
in_register: true
generated_by: "scripts/build_vault.py"
---

# cso.electricity.hebeu88_tariff_type_by_urban_rural

HEBEU88: electricity tariff used by households for billing, by urban or rural location and type of electricity tariff (2024)

| | |
|---|---|
| Publisher | Central Statistics Office (Ireland) |
| Licence | CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/) |
| File | `cso_electricity/HEBEU88_electricity_tariff_type_by_urban_rural.json` |
| Bytes | 2,669 |
| SHA-256 prefix | `1ce1d554a4d4…` |
| Retrieved | 2026-10-12 |
| Intended use | reference — Structural or documentary reference; shapes no parameter |
| Model-development exposure | none |
| In the register | yes |
| Manifest | `sources/cso_electricity/HEBEU88_electricity_tariff_type_by_urban_rural.json.manifest.json` |

## Datasets that use it

[[D27]]

## Used for

D27's PLAN MIX. The published categories are 'Standard tariff', 'Day/Night tariff or Day/Night/Weekend tariff', 'Smart tariff', 'Other tariff NEC' and 'Tariff type unknown', which map onto the three tariff_kind values datasets.yaml declares (flat, day-night, ToU). Cobh is urban, so the URBAN row is the one used, and the shares are renormalised over the three known categories with the suppressed and unknown shares reported rather than reassigned. Closes the assumption that the mix was an equal three-way split: this is the HAS02 lesson (I-040) again - the search over the declared PxStat catalogue found a published table where a comment had recorded a conclusion. Exposure `none`.

## Touched by

| | |
|---|---|
| Assumptions | [[A-91]] |
| Issues | [[I-040]] |
