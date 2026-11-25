---
type: "phase"
id: "Phase 10"
status: "pending"
tags:
  - "phase"
  - "status/pending"
effort: "8 d"
gate: "G10"
generated_by: "scripts/build_vault.py"
---

# Phase 10 — Household finance

| | |
|---|---|
| Effort | 8 d |
| Exit gate | [[G10]] |
| Status | pending |

## Work

Work: income per household from sourced CSO SILC distributions by tenure and composition, updated by year; bills computed from each home's actual simulated consumption and export, its resolved tariff, standing charges and credits.

## Exit criteria

every household has a dated income with a sourced distribution behind it; every home has a bill reconciling to CRU's own component decomposition; no bill uses anything but simulated consumption — no scripted or assumed usage.

## Blockers and open items

No open issue in `docs/ISSUES.md` is named by this phase.

## Touches

| | |
|---|---|
| Gates named | [[G10]], [[G5]] |

Source: `PLAYBOOK_v3.1.md` §2.
