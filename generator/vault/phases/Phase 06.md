---
type: "phase"
id: "Phase 06"
status: "pending"
tags:
  - "phase"
  - "status/pending"
effort: "5 d"
gate: "G6"
datasets:
  - "D31"
modules:
  - "baile_nua.observation.nonsensor"
generated_by: "scripts/build_vault.py"
---

# Phase 6 — Market and system data

| | |
|---|---|
| Effort | 5 d |
| Exit gate | [[G6]] |
| Status | pending |

## Work

SEM SMP, I-SEM DA/BM, EirGrid demand and carbon; build D31's market series.

## Exit criteria

E2-7 passes for the first time — today observation/nonsensor.py:40 records it as "What is NOT built, and E2-7 fails on it".

## Blockers and open items

No open issue in `docs/ISSUES.md` is named by this phase.

## Issues the playbook tracks against this phase (§10)

- E2-7 — Closes in Phase 6.

## Touches

| | |
|---|---|
| Datasets | [[D31]] |
| Modules | [[baile_nua.observation.nonsensor]] |
| Gates named | [[G6]] |

Source: `PLAYBOOK_v3.1.md` §2.
