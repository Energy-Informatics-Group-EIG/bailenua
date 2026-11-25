---
type: "source"
id: "cso.housing.vac17_vacancy_flows"
status: "calibration"
tags:
  - "exposure/none"
  - "source"
  - "use/calibration"
publisher: "Central Statistics Office (Ireland)"
licence_summary: "CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/)"
sha256_prefix: "addd23677d7f"
bytes: 3552
retrieved: "2026-10-10"
intended_use: "calibration"
model_development_exposure: "none"
in_register: true
generated_by: "scripts/build_vault.py"
---

# cso.housing.vac17_vacancy_flows

VAC17: vacancy flows, quarterly (dwellings entering and leaving vacancy)

| | |
|---|---|
| Publisher | Central Statistics Office (Ireland) |
| Licence | CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/) |
| File | `cso_lifecourse/VAC17_vacancy_flows.json` |
| Bytes | 3,552 |
| SHA-256 prefix | `addd23677d7f…` |
| Retrieved | 2026-10-10 |
| Intended use | calibration — Allowed to shape parameters (design 7.1 calibration sources) |
| Model-development exposure | none |
| In the register | yes |
| Manifest | `sources/cso_lifecourse/VAC17_vacancy_flows.json.manifest.json` |

## Datasets that use it

—

## Used for

WP5 vacancy chain. This is the one table that publishes vacancy as a FLOW rather than a stock, so it constrains the rate at which homes enter and leave vacancy - which is what a move-out/move-in chain actually generates.

## Touched by

| | |
|---|---|
| Assumptions | [[A-25]] |
