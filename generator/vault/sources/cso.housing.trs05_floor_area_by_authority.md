---
type: "source"
id: "cso.housing.trs05_floor_area_by_authority"
status: "calibration"
tags:
  - "exposure/tuning"
  - "source"
  - "use/calibration"
publisher: "Central Statistics Office (Ireland), from RTB tenancy registrations matched to BER"
licence_summary: "CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/)"
sha256_prefix: "69b76b7a1ecf"
bytes: 7065
retrieved: "2026-10-10"
intended_use: "calibration"
model_development_exposure: "tuning"
in_register: true
generated_by: "scripts/build_vault.py"
---

# cso.housing.trs05_floor_area_by_authority

Total Floor Area of Rental Properties by local authority and year (TRS05)

| | |
|---|---|
| Publisher | Central Statistics Office (Ireland), from RTB tenancy registrations matched to BER |
| Licence | CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/) |
| File | `cso_housing/TRS05_median_floor_area_of_rental_properties.json` |
| Bytes | 7,065 |
| SHA-256 prefix | `69b76b7a1ecf…` |
| Retrieved | 2026-10-10 |
| Intended use | calibration — Allowed to shape parameters (design 7.1 calibration sources) |
| Model-development exposure | tuning |
| In the register | yes |
| Manifest | `sources/cso_housing/TRS05_median_floor_area_of_rental_properties.json.manifest.json` |

## Datasets that use it

—

## Used for

The only public Irish floor-area figure in PxStat, and the anchor for I-031. SAPS publishes room COUNTS and no areas, and neither EBA02 nor EBQ02 carries floor area, so the metres-squared-per-room relationship had to be assumed - and the assumption was wrong in a way that mattered: apartments were given MORE area per room than detached houses, which put the town's apartment median at 120.8 m2 against a detached median of 129.5. TRS05 gives 89.4 m2 as the median for Co. Cork rental properties in 2021. It bounds from BELOW rather than fixing the level, because rentals skew smaller and apartment-heavier than the whole stock, and that direction is stated wherever it is used. Cork County Council …

## Touched by

| | |
|---|---|
| Issues | [[I-031]] |
