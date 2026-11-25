---
type: "phase"
id: "Phase 09"
status: "pending"
tags:
  - "phase"
  - "status/pending"
effort: "8 d"
gate: "G9"
blockers:
  - "I-103"
datasets:
  - "D01"
  - "D02"
  - "D17"
generated_by: "scripts/build_vault.py"
---

# Phase 9 — Town growth and amenities

| | |
|---|---|
| Effort | 8 d |
| Exit gate | [[G9]] |
| Status | pending |

## Work

Exercise D01/D02's never-used validity intervals (valid_to on 0 of 1,092; version = 1 on all).

## Exit criteria

no dwelling produces data before completion; +300 dwellings (+27.5%) adds ~15 transformers, ~18 feeders, ~615 buses; D17 rows scale as 96 epochs × (transformers + feeders), a rule reproducing the measured 157,248 rows exactly.

## Blockers and open items

[[I-103]]

## Issues the playbook tracks against this phase (§10)

- [[I-103]] — RELOCATED_TO_RUN points at wp5_decade, which ceases to exist. Revisit in Phase 9.

## Touches

| | |
|---|---|
| Datasets | [[D01]], [[D02]], [[D17]] |
| Decisions | [[D-112]], [[D-114]] |
| Gates named | [[G9]] |
| Events | [[Cluain Ard completion 2019]], [[Belgard completion 2024]], [[Abbeylands phased completion to 2027]] |
| Estates | [[Abbeylands]], [[Belgard]], [[Cluain Ard]] |

Source: `PLAYBOOK_v3.1.md` §2.
