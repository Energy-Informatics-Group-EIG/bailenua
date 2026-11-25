---
type: "source"
id: "cso.housing.nda08_new_dwelling_size_by_type"
status: "validation"
tags:
  - "exposure/none"
  - "source"
  - "use/validation"
publisher: "Central Statistics Office (Ireland)"
licence_summary: "CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/)"
sha256_prefix: "7b415941fa60"
bytes: 2996
retrieved: "2026-10-09"
intended_use: "validation"
model_development_exposure: "none"
in_register: true
generated_by: "scripts/build_vault.py"
---

# cso.housing.nda08_new_dwelling_size_by_type

Average New Dwelling Size by dwelling type and year, with weight in mix (NDA08)

| | |
|---|---|
| Publisher | Central Statistics Office (Ireland) |
| Licence | CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/) |
| File | `cso_plausibility/NDA08_average_new_dwelling_size_by_type.json` |
| Bytes | 2,996 |
| SHA-256 prefix | `7b415941fa60…` |
| Retrieved | 2026-10-09 |
| Intended use | validation — Never used for calibration; splits fixed and hashed in D24 before comparison |
| Model-development exposure | none |
| In the register | yes |
| Manifest | `sources/cso_plausibility/NDA08_average_new_dwelling_size_by_type.json.manifest.json` |

## Datasets that use it

—

## Used for

U27 plausibility: floor area BY DWELLING TYPE, which is what I-031 needed and TRS05 could not give - TRS05 is a rental median by local authority with no type split, and was used only as a lower bound. NDA08 gives square metres for single houses, scheme houses and apartments separately, plus each type's weight in the mix. New dwellings only, so it bounds the MODERN end of the stock and is the right comparator for the post-2005 cohort rather than for a pre-1980 terrace. Exposure `none` and it must stay so: the apartment area-per-room value was corrected against TRS05 and physical reasoning, not against this, so this can still score the correction.

## Touched by

| | |
|---|---|
| Issues | [[I-031]] |
