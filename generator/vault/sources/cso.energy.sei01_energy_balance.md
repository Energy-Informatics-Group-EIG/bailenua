---
type: "source"
id: "cso.energy.sei01_energy_balance"
status: "validation"
tags:
  - "exposure/none"
  - "source"
  - "use/validation"
publisher: "Central Statistics Office (Ireland), from the SEAI national energy balance"
licence_summary: "CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/)"
sha256_prefix: "1ea0736fe45f"
bytes: 494277
retrieved: "2026-10-09"
intended_use: "validation"
model_development_exposure: "none"
in_register: true
generated_by: "scripts/build_vault.py"
---

# cso.energy.sei01_energy_balance

Energy Balance by energy supply and consumption category, fuel type and year (SEI01)

| | |
|---|---|
| Publisher | Central Statistics Office (Ireland), from the SEAI national energy balance |
| Licence | CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/) |
| File | `cso_plausibility/SEI01_energy_balance.json` |
| Bytes | 494,277 |
| SHA-256 prefix | `1ea0736fe45f…` |
| Retrieved | 2026-10-09 |
| Intended use | validation — Never used for calibration; splits fixed and hashed in D24 before comparison |
| Model-development exposure | none |
| In the register | yes |
| Manifest | `sources/cso_plausibility/SEI01_energy_balance.json.manifest.json` |

## Datasets that use it

—

## Used for

U27 plausibility: the national residential energy balance by fuel, in ktoe. Gives the FUEL MIX of Irish household energy - how much is electricity against gas, oil, coal, peat and renewables - which is the one quantity that checks whether the simulated town's heating fuel shares and the relative size of its electricity and gas totals are jointly plausible. Every other reference checks one fuel at a time and so cannot see a town that gets both right separately and the balance between them wrong.

## Touched by

*Nothing recorded.*
