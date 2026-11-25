---
type: "phase"
id: "Phase 12"
status: "pending"
tags:
  - "phase"
  - "status/pending"
effort: "7 d"
gate: "G12"
datasets:
  - "D18"
  - "D19"
  - "D30"
  - "D31"
generated_by: "scripts/build_vault.py"
---

# Phase 12 — N: observable layer by era

| | |
|---|---|
| Effort | 7 d |
| Exit gate | [[G12]] |
| Status | pending |

## Work

| era | from | observable | |---|---|---| | 1 | 2015 | bi-monthly actual or estimated register reads only | | 2 | smart-meter install (ESB rollout 2019–24, sourced by area and year) | 30-minute import/export interval, realistic gaps and estimates | | 3 | 2021, 16a | 15-minute and device-level for enrolled homes from their enrolment date only | GT stays full resolution throughout; only the observable layer changes.

## Exit criteria

no home has interval data before its install date; era transitions dated per home; effect on D18, D19, D30, D31 reported with measured bytes.

## Blockers and open items

No open issue in `docs/ISSUES.md` is named by this phase.

## Touches

| | |
|---|---|
| Datasets | [[D18]], [[D19]], [[D30]], [[D31]] |
| Gates named | [[G12]] |
| Events | [[Smart-meter rollout]] |

Source: `PLAYBOOK_v3.1.md` §2.
