---
type: "privacy tier"
id: "GT"
status: "enforced by the generated leakage test"
tags:
  - "class/GT"
  - "privacy-tier"
released_in: "ground_truth"
datasets:
  - "D01"
  - "D02"
  - "D03"
  - "D04"
  - "D05"
  - "D06"
  - "D07"
  - "D08"
  - "D09"
  - "D10"
  - "D11"
  - "D12"
  - "D13"
  - "D14"
  - "D15"
  - "D16"
  - "D17"
  - "D20"
  - "D21"
  - "D26"
generated_by: "scripts/build_vault.py"
---

# Privacy tier GT

| | |
|---|---|
| Description | Ground truth. Never given to a model under test. |
| Released in | ground_truth |
| Datasets | 20 |

## Datasets in this tier

[[D01]], [[D02]], [[D03]], [[D04]], [[D05]], [[D06]], [[D07]], [[D08]], [[D09]], [[D10]], [[D11]], [[D12]], [[D13]], [[D14]], [[D15]], [[D16]], [[D17]], [[D20]], [[D21]], [[D26]]

## Roles that may see it

[[role_Homeowner_occupant]], [[role_Modeller_researcher]]

The class is carried in the schema and the leakage test is generated from it, so the separation is mechanical ([[D-006]]).
