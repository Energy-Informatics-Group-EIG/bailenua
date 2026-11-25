---
type: "source"
id: "cso.electricity.tmegb03_residential_electricity_prices"
status: "reference"
tags:
  - "exposure/none"
  - "source"
  - "use/reference"
publisher: "Central Statistics Office (Ireland)"
licence_summary: "CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/)"
sha256_prefix: "33a5bda1bec2"
bytes: 5219
retrieved: "2026-10-12"
intended_use: "reference"
model_development_exposure: "none"
datasets:
  - "D27"
in_register: true
generated_by: "scripts/build_vault.py"
---

# cso.electricity.tmegb03_residential_electricity_prices

TMEGB03: residential electricity prices in euro per kWh, by year, semester, pricing basis and Eurostat household electricity consumption band (DA to DE)

| | |
|---|---|
| Publisher | Central Statistics Office (Ireland) |
| Licence | CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/) |
| File | `cso_electricity/TMEGB03_residential_electricity_prices.json` |
| Bytes | 5,219 |
| SHA-256 prefix | `33a5bda1bec2…` |
| Retrieved | 2026-10-12 |
| Intended use | reference — Structural or documentary reference; shapes no parameter |
| Model-development exposure | none |
| In the register | yes |
| Manifest | `sources/cso_electricity/TMEGB03_residential_electricity_prices.json.manifest.json` |

## Datasets that use it

[[D27]]

## Used for

The INDEPENDENT level check on D27's unit rates. Band DC is 2,500 to 5,000 kWh a year, which is where an Irish domestic meter sits, and the series is published per semester, so the 2022 half-year prices bracket the supplier's own 1 May 2022 schedule. Published by the CSO and not by the supplier whose rates are on the card, which is what makes it a check rather than a restatement. Exposure `none`.

## Touched by

| | |
|---|---|
| Assumptions | [[A-90]] |
