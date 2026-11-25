---
type: "phase"
id: "Phase 20"
status: "pending"
tags:
  - "phase"
  - "status/pending"
effort: "10 d"
gate: "G20"
generated_by: "scripts/build_vault.py"
---

# Phase 20 — 16b: Flexibility services

| | |
|---|---|
| Effort | 10 d |
| Entry | G17, plus the LEC build and the FLEXUS build — neither is in this repo and neither is mine to assess (D16). |
| Exit gate | [[G20]] |
| Status | pending |

## Work

Entry: G17, plus the LEC build and the FLEXUS build — neither is in this repo and neither is mine to assess (D16). * Work: LEC programmes, signals, offers, delivery and settlement over the frozen replay via BN-6/BN-7.

## Exit criteria

reads the frozen replay, writes only flexibility datasets, no base package modified. Total ≈143 working days (0–17: 117 d; 18–20: 26 d), plus 5.12 days of chained runtime. ---

## Blockers and open items

No open issue in `docs/ISSUES.md` is named by this phase.

## Touches

| | |
|---|---|
| Decisions | [[D-115]] |
| Gates named | [[G17]], [[G20]] |

Source: `PLAYBOOK_v3.1.md` §2.
