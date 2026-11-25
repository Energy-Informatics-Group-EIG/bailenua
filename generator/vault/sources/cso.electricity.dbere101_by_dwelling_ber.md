---
type: "source"
id: "cso.electricity.dbere101_by_dwelling_ber"
status: "calibration"
tags:
  - "exposure/tuning"
  - "source"
  - "use/calibration"
publisher: "Central Statistics Office (Ireland), from matched BER and ESB Networks meter data"
licence_summary: "CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/)"
sha256_prefix: "d0082edfdcfd"
bytes: 4863
retrieved: "2026-10-10"
intended_use: "calibration"
model_development_exposure: "tuning"
datasets:
  - "D24"
in_register: true
generated_by: "scripts/build_vault.py"
---

# cso.electricity.dbere101_by_dwelling_ber

Household Electricity Consumption by type of dwelling, energy rating and year (DBEREL01)

| | |
|---|---|
| Publisher | Central Statistics Office (Ireland), from matched BER and ESB Networks meter data |
| Licence | CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/) |
| File | `cso_electricity/DBEREL01_household_electricity_by_dwelling_and_ber.json` |
| Bytes | 4,863 |
| SHA-256 prefix | `d0082edfdcfd…` |
| Retrieved | 2026-10-10 |
| Intended use | calibration — Allowed to shape parameters (design 7.1 calibration sources) |
| Model-development exposure | tuning |
| In the register | yes |
| Manifest | `sources/cso_electricity/DBEREL01_household_electricity_by_dwelling_and_ber.json.manifest.json` |

## Datasets that use it

[[D24]]

## Used for

D24 calibration target for the device and DER layer (design 5.6, 7.2). The dimensions are exactly the archetype library's own - dwelling type crossed with BER band - so the target applies per dwelling rather than only to the town mean, which is what distinguishes 'the average home uses about the right amount' from 'each KIND of home does'. 2022 is t0, so the comparison year is the simulated year. Exposure is declared as 'tuning' because the appliance trigger rates WERE adjusted against it: 7.1 requires that to be visible, not buried. So PL-ELEC-01, which scores against this table, is a CONSISTENCY check against a calibration input and NOT an independent validation - the held-out electricity …

## Touched by

| | |
|---|---|
| Assumptions | [[A-18]] |
| Issues | [[I-058]] |
