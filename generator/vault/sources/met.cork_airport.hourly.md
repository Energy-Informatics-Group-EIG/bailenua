---
type: "source"
id: "met.cork_airport.hourly"
status: "calibration"
tags:
  - "exposure/none"
  - "source"
  - "use/calibration"
publisher: "Met \u00c9ireann"
licence_summary: "CC-BY 4.0 (Met \u00c9ireann open data)"
sha256_prefix: "8d592587f0c8"
bytes: 10607064
retrieved: "2026-10-08"
intended_use: "calibration"
model_development_exposure: "none"
datasets:
  - "D31"
in_register: true
generated_by: "scripts/build_vault.py"
---

# met.cork_airport.hourly

Hourly climate data, Cork Airport (station 3904)

| | |
|---|---|
| Publisher | Met Éireann |
| Licence | CC-BY 4.0 (Met Éireann open data) |
| File | `met_eireann/hly3904_cork_airport.zip` |
| Bytes | 10,607,064 |
| SHA-256 prefix | `8d592587f0c8…` |
| Retrieved | 2026-10-08 |
| Intended use | calibration — Allowed to shape parameters (design 7.1 calibration sources) |
| Model-development exposure | none |
| In the register | yes |
| Manifest | `sources/met_eireann/hly3904_cork_airport.zip.manifest.json` |

## Datasets that use it

[[D31]]

## Used for

The observable station series D31. Design 6.4 item 7 requires the observable weather to come from the nearest official station rather than the true site microclimate; Cork Airport is inland and elevated, so the station-to-site gap is physically real rather than injected noise.

## Touched by

*Nothing recorded.*
