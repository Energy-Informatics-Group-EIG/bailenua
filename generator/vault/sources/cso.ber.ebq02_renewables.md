---
type: "source"
id: "cso.ber.ebq02_renewables"
status: "calibration"
tags:
  - "exposure/none"
  - "source"
  - "use/calibration"
publisher: "Central Statistics Office (Ireland), from the SEAI BER register"
licence_summary: "CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/)"
sha256_prefix: "4ab2045e6714"
bytes: 23710635
retrieved: "2026-10-08"
intended_use: "calibration"
model_development_exposure: "none"
datasets:
  - "D04"
in_register: true
generated_by: "scripts/build_vault.py"
---

# cso.ber.ebq02_renewables

Domestic Building Energy Ratings by dwelling type, renewable energy source, year of construction, heating fuel and NUTS3 region (EBQ02)

| | |
|---|---|
| Publisher | Central Statistics Office (Ireland), from the SEAI BER register |
| Licence | CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/) |
| File | `seai/EBQ02_domestic_ber_renewables_by_region.json` |
| Bytes | 23,710,635 |
| SHA-256 prefix | `4ab2045e6714…` |
| Retrieved | 2026-10-08 |
| Intended use | calibration — Allowed to shape parameters (design 7.1 calibration sources) |
| Model-development exposure | none |
| In the register | yes |
| Manifest | `sources/seai/EBQ02_domestic_ber_renewables_by_region.json.manifest.json` |

## Datasets that use it

[[D04]]

## Used for

Also closes I-011. Census records heating FUEL, so a heat pump and direct electric resistance heating are the same row ('Electricity') - yet their COP differs by a factor of three or more and dominates the heating load (design 5.7). EBQ02 reports heat-pump and solar-panel penetration for the South-West NUTS3 region, which is Cork (IE053, confirmed from the OSi small-area attributes), so the split within electrically-heated homes comes from real regional data. Also supplies the PV and heat-pump adoption base rates for D04 at t0 (5.9 DER row).

## Touched by

| | |
|---|---|
| Issues | [[I-011]] |
