---
type: "role"
id: "PARA//EL"
status: "specified"
tags:
  - "flexus-family"
  - "role"
sees: "everything local; shares upward only at the home's consented level"
generated_by: "scripts/build_vault.py"
---

# PARA//EL (role)

| | |
|---|---|
| Role | PARA//EL |
| Sees | everything local; shares upward only at the home's consented level |
| Specified in | PLAYBOOK_v3.1 §2 Phase 19 (role-scoped data views) |

## Gate

[[G19]]: no view exposes data above its tier, and no DSO aggregate ever covers fewer than 5 premises — both as tests, not review. The modeller view carries the designer label in the artefact itself.

## Privacy tiers it may read

[[tier_OBS]]

*A role's tier is read from its own row in the playbook's table; the playbook publishes no separate numbered tier list.*
