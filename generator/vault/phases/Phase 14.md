---
type: "phase"
id: "Phase 14"
status: "pending"
tags:
  - "phase"
  - "status/pending"
effort: "5 d"
gate: "G14"
generated_by: "scripts/build_vault.py"
---

# Phase 14 — Emergent outcomes dataset

| | |
|---|---|
| Effort | 5 d |
| Exit gate | [[G14]] |
| Status | pending |

## Work

Work: a per-year outcome dataset carrying indoor temperature and comfort hours, bill burden, and energy poverty by tenure and Part V status on two measures: the ESRI expenditure measure (energy spend above 10% of disposable income) and the CSO SILC subjective measure ("unable to keep home adequately warm"). * Exit G14: every outcome derived from simulated physics and simulated finances, with no imposed rate;

## Exit criteria

every outcome derived from simulated physics and simulated finances, with no imposed rate; the two poverty measures reported separately and never averaged.

## Blockers and open items

No open issue in `docs/ISSUES.md` is named by this phase.

## Playbook open decisions on this phase

- **D19** — Which energy-poverty measure is primary (Phase 14). The ESRI expenditure measure and the SILC subjective measure disagree by construction — a well-insulated low-income home can pass one and fail the other. *Recommendation:* Report both, never averaged, and name neither primary. The disagreement is informative. Validation in Phase 16 scores against SILC because that is what SILC publishes.

## Touches

| | |
|---|---|
| Gates named | [[G14]] |

Source: `PLAYBOOK_v3.1.md` §2.
