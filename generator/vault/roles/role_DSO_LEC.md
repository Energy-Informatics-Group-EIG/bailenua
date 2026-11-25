---
type: "role"
id: "DSO (LEC)"
status: "specified"
tags:
  - "flexus-family"
  - "role"
sees: "network data plus aggregates of \u22655 premises (LC-AMI-03); flexibility columns excluded from AMI (LC-AMI-01)"
constraints:
  - "LC-AMI-01"
  - "LC-AMI-03"
generated_by: "scripts/build_vault.py"
---

# DSO (LEC) (role)

| | |
|---|---|
| Role | DSO (LEC) |
| Sees | network data plus aggregates of ≥5 premises (LC-AMI-03); flexibility columns excluded from AMI (LC-AMI-01) |
| Named constraints | [[constraint_LC-AMI-01]], [[constraint_LC-AMI-03]] |
| Specified in | PLAYBOOK_v3.1 §2 Phase 19 (role-scoped data views) |

## Gate

[[G19]]: no view exposes data above its tier, and no DSO aggregate ever covers fewer than 5 premises — both as tests, not review. The modeller view carries the designer label in the artefact itself.

## Privacy tiers it may read

[[tier_OBS]]

*A role's tier is read from its own row in the playbook's table; the playbook publishes no separate numbered tier list.*
