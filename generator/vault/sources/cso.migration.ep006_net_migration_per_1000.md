---
type: "source"
id: "cso.migration.ep006_net_migration_per_1000"
status: "calibration"
tags:
  - "exposure/none"
  - "source"
  - "use/calibration"
publisher: "Central Statistics Office (Ireland)"
licence_summary: "CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/)"
sha256_prefix: "f722628d7c63"
bytes: 5238
retrieved: "2026-10-10"
intended_use: "calibration"
model_development_exposure: "none"
in_register: true
generated_by: "scripts/build_vault.py"
---

# cso.migration.ep006_net_migration_per_1000

EP006: annual estimated net migration 1951-2016 per 1,000 of average population, by province, county or city

| | |
|---|---|
| Publisher | Central Statistics Office (Ireland) |
| Licence | CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/) |
| File | `cso_lifecourse/EP006_net_migration_per_1000_by_county.json` |
| Bytes | 5,238 |
| SHA-256 prefix | `f722628d7c63…` |
| Retrieved | 2026-10-10 |
| Intended use | calibration — Allowed to shape parameters (design 7.1 calibration sources) |
| Model-development exposure | none |
| In the register | yes |
| Manifest | `sources/cso_lifecourse/EP006_net_migration_per_1000_by_county.json.manifest.json` |

## Datasets that use it

—

## Used for

WP5 move-in / move-out. This is a NET rate, so it constrains the DIFFERENCE between the two gross flows and not either one; the gross turnover rate is the [A] part (hazards.py A-25b).

## Touched by

*Nothing recorded.*
