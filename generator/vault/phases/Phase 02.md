---
type: "phase"
id: "Phase 02"
status: "pending"
tags:
  - "phase"
  - "status/pending"
effort: "6 d"
gate: "G2"
blockers:
  - "I-088"
generated_by: "scripts/build_vault.py"
---

# Phase 2 — Time axis

| | |
|---|---|
| Effort | 6 d |
| Exit gate | [[G2]] |
| Status | pending |

## Work

build_realisation(year) → date range (closes I-088: the data is already real observed Met Éireann, both stations on disk from 1962/1955, so this is an interface change). build_calendar raises NotImplementedError for any year but 2022 — generalise;

## Exit criteria

366-day 2016 balances; 29 Feb in 2016, 2020, 2024; 12 holiday tables verified independently; 2022 keeps the 18 Mar one-off and still excludes St Brigid's, which begins 2023.

## Blockers and open items

[[I-088]]

## Issues the playbook tracks against this phase (§10)

- [[I-088]] — Closes in Phase 2 — an interface limit, not missing data.

## Touches

| | |
|---|---|
| Issues | [[I-088]] |
| Gates named | [[G2]] |
| Events | [[One-off public holiday 18 March 2022]], [[St Brigid's Day holiday begins]] |

Source: `PLAYBOOK_v3.1.md` §2.
