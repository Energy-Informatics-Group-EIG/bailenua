---
type: "phase"
id: "Phase 01"
status: "pending"
tags:
  - "phase"
  - "status/pending"
effort: "5 d"
gate: "G1"
blockers:
  - "I-069"
  - "I-106"
modules:
  - "baile_nua.population.venues"
generated_by: "scripts/build_vault.py"
---

# Phase 1 — Population defects

| | |
|---|---|
| Effort | 5 d |
| Exit gate | [[G1]] |
| Status | pending |

## Work

I-069: economic status drawn with no age conditioning — 241 "students" at a median age of 45; 8,426 venue-presence rows (7.3% of 114,951) carry no venue id.

## Exit criteria

economic status age-conditioned; age structure within declared tolerance of SAP2022 in every band including 85+; the 7.3% gap a declared residual.

## Blockers and open items

[[I-069]], [[I-106]]

## Issues the playbook tracks against this phase (§10)

- [[I-069]] — Closes in Phase 1; gates all population and venue work.
- [[I-106]] — Age-structure deficit vs SAP2022 (65+ −29%, 85+ −71%). Logged. Closes in Phase 1. Blocks D3's arithmetic.

## Touches

| | |
|---|---|
| Modules | [[baile_nua.population.venues]] |
| Issues | [[I-069]], [[I-106]] |
| Gates named | [[G1]] |

Source: `PLAYBOOK_v3.1.md` §2.
