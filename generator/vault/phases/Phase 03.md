---
type: "phase"
id: "Phase 03"
status: "pending"
tags:
  - "phase"
  - "status/pending"
effort: "5 d"
gate: "G3"
blockers:
  - "I-105"
modules:
  - "baile_nua.export.tariffs"
generated_by: "scripts/build_vault.py"
---

# Phase 3 — DST and clocks

| | |
|---|---|
| Effort | 5 d |
| Exit gate | [[G3]] |
| Status | pending |

## Work

UTC sim, local-clock schedules, local-time exports. MINUTES_PER_DAY = 1440 backs every per-minute array;

## Exit criteria

bands on the correct local hour across all 23 transitions; 23- and 25-hour days balance. I-105 is a live defect today, independent of this plan.

## Blockers and open items

[[I-105]]

## Issues the playbook tracks against this phase (§10)

- [[I-105]] — DST/tariff-band mismatch, a live defect today. Logged. Closes in Phase 3.

## Touches

| | |
|---|---|
| Modules | [[baile_nua.export.tariffs]] |
| Issues | [[I-105]] |
| Gates named | [[G3]] |
| Events | [[DST transitions across the span]] |

Source: `PLAYBOOK_v3.1.md` §2.
