---
type: "source"
id: "cso.gas.dberng01_by_dwelling_ber"
status: "calibration"
tags:
  - "exposure/tuning"
  - "source"
  - "use/calibration"
publisher: "Central Statistics Office (Ireland), from matched BER and Gas Networks Ireland meter data"
licence_summary: "CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/)"
sha256_prefix: "1014220a5660"
bytes: 5024
retrieved: "2026-10-10"
intended_use: "calibration"
model_development_exposure: "tuning"
datasets:
  - "D24"
in_register: true
generated_by: "scripts/build_vault.py"
---

# cso.gas.dberng01_by_dwelling_ber

Mean Gas Consumption by type of dwelling, energy rating and year (DBERNG01)

| | |
|---|---|
| Publisher | Central Statistics Office (Ireland), from matched BER and Gas Networks Ireland meter data |
| Licence | CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/) |
| File | `cso_electricity/DBERNG01_mean_gas_by_dwelling_and_ber.json` |
| Bytes | 5,024 |
| SHA-256 prefix | `1014220a5660…` |
| Retrieved | 2026-10-10 |
| Intended use | calibration — Allowed to shape parameters (design 7.1 calibration sources) |
| Model-development exposure | tuning |
| In the register | yes |
| Manifest | `sources/cso_electricity/DBERNG01_mean_gas_by_dwelling_and_ber.json.manifest.json` |

## Datasets that use it

[[D24]]

## Used for

The heating-side D24 target, and the one the estate actually needs: 49 of its 50 homes heat with gas, so their space heat never appears in the electricity meter and DBEREL01 cannot see it. In a gas-heated dwelling, gas consumption IS space heating plus hot water, which makes this the direct check on the F1 physics and the heating schedule - the largest energy term in the model and, until now, the one with no public target at all. Same axes as DBEREL01 (dwelling type x BER band), so the two can be read together per dwelling. Exposure is 'tuning' because the floor-area and room-allocation fixes in I-031 were checked against it, and from week 3 the fabric is derived from the BER Research Tool …

## Touched by

| | |
|---|---|
| Assumptions | [[A-18]] |
| Issues | [[I-031]], [[I-058]] |
