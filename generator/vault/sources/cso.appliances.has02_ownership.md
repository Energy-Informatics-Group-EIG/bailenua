---
type: "source"
id: "cso.appliances.has02_ownership"
status: "validation"
tags:
  - "exposure/none"
  - "source"
  - "use/validation"
publisher: "Central Statistics Office (Ireland), Survey on Income and Living Conditions"
licence_summary: "CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/)"
sha256_prefix: "a879f0945593"
bytes: 7177
retrieved: "2026-10-09"
intended_use: "validation"
model_development_exposure: "none"
in_register: true
generated_by: "scripts/build_vault.py"
---

# cso.appliances.has02_ownership

Households who possess a household appliance, by appliance type, possession status and year (HAS02)

| | |
|---|---|
| Publisher | Central Statistics Office (Ireland), Survey on Income and Living Conditions |
| Licence | CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/) |
| File | `cso_plausibility/HAS02_household_appliance_ownership.json` |
| Bytes | 7,177 |
| SHA-256 prefix | `a879f0945593…` |
| Retrieved | 2026-10-09 |
| Intended use | validation — Never used for calibration; splits fixed and hashed in D24 before comparison |
| Model-development exposure | none |
| In the register | yes |
| Manifest | `sources/cso_plausibility/HAS02_household_appliance_ownership.json.manifest.json` |

## Datasets that use it

—

## Used for

U27 plausibility: appliance OWNERSHIP, which `OWNERSHIP_PRIORS` has carried as declared assumptions [A] since Day 5 with the note that 'SAPS publishes no appliance ownership'. SAPS does not, but SILC does: HAS02 gives the share of households possessing a washing machine, clothes dryer, dishwasher, fridge, fridge with separate freezer, deep freeze and microwave. Seven of the nineteen priors stop being assumptions. Declared `validation` and exposure `none`: the priors were set before this table was found, so it can score them rather than merely agree with them. It must stay unexposed - if a prior is ever adjusted against it, its intended_use changes with it.

## Touched by

| | |
|---|---|
| Assumptions | [[A-04]] |
