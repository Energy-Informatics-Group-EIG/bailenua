---
type: "source"
id: "cso.electricity.mec05_by_tariff_group"
status: "reference"
tags:
  - "exposure/none"
  - "source"
  - "use/reference"
publisher: "Central Statistics Office (Ireland), from ESB Networks"
licence_summary: "CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/)"
sha256_prefix: "d91a0397387e"
bytes: 2985
retrieved: "2026-10-10"
intended_use: "reference"
model_development_exposure: "none"
in_register: true
generated_by: "scripts/build_vault.py"
---

# cso.electricity.mec05_by_tariff_group

Metered Electricity Consumption by tariff group and year (MEC05)

| | |
|---|---|
| Publisher | Central Statistics Office (Ireland), from ESB Networks |
| Licence | CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/) |
| File | `cso_electricity/MEC05_metered_electricity_by_tariff_group.json` |
| Bytes | 2,985 |
| SHA-256 prefix | `d91a0397387e…` |
| Retrieved | 2026-10-10 |
| Intended use | reference — Structural or documentary reference; shapes no parameter |
| Model-development exposure | none |
| In the register | yes |
| Manifest | `sources/cso_electricity/MEC05_metered_electricity_by_tariff_group.json.manifest.json` |

## Datasets that use it

—

## Used for

The aggregate cross-check, and the one that matches Cobh's own tariff group: 'Urban Residential' rather than a national all-dwellings mean. Cobh is a town, and urban residential consumption differs from rural (no oil-fired rural pattern, smaller dwellings). Reference and not calibration, because it cannot be made per-dwelling: the CSO publishes no meter COUNT by tariff group, so the 5,668 GWh has no denominator. It fixes the urban-to-rural RATIO (5,668 to 3,095 GWh) and nothing more.

## Touched by

*Nothing recorded.*
