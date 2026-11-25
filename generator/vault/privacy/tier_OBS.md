---
type: "privacy tier"
id: "OBS"
status: "enforced by the generated leakage test"
tags:
  - "class/OBS"
  - "privacy-tier"
released_in: "observable"
datasets:
  - "D17_aggregate"
  - "D18"
  - "D19"
  - "D25"
  - "D27"
  - "D28"
  - "D29"
  - "D30"
  - "D31"
generated_by: "scripts/build_vault.py"
---

# Privacy tier OBS

| | |
|---|---|
| Description | Observable. What a device, respondent, assessor or operator would see. |
| Released in | observable |
| Datasets | 9 |

## Datasets in this tier

[[D17_aggregate]], [[D18]], [[D19]], [[D25]], [[D27]], [[D28]], [[D29]], [[D30]], [[D31]]

## Roles that may see it

[[role_Homeowner_occupant]], [[role_PARA_EL]], [[role_EdgeWare]], [[role_FLEXUS]], [[role_DSO_LEC]], [[role_Regulator_CRU]], [[role_Modeller_researcher]]

The class is carried in the schema and the leakage test is generated from it, so the separation is mechanical ([[D-006]]).
