---
type: "phase"
id: "Phase 05"
status: "pending"
tags:
  - "phase"
  - "status/pending"
effort: "7 d"
gate: "G5"
blockers:
  - "I-094"
generated_by: "scripts/build_vault.py"
---

# Phase 5 — Vintaged rates and two price regimes

| | |
|---|---|
| Effort | 7 d |
| Exit gate | [[G5]] |
| Status | pending |

## Work

SourcedValue has no validity field and uses __slots__. Add validity intervals, a date-keyed resolver, the SEM SMP → I-SEM switch at Oct 2018.

## Exit criteria

no rate outside its interval; every vintage cites a document on disk — test_d27_every_sourced_rate_is_in_its_cited_document greps the cited document's bytes, which is this phase's real cost.

## Blockers and open items

[[I-094]]

## Issues the playbook tracks against this phase (§10)

- [[I-094]], [[A-97]] — Closes in Phase 5.

## Touches

| | |
|---|---|
| Gates named | [[G5]] |
| Events | [[SEM SMP to I-SEM switch]] |

Source: `PLAYBOOK_v3.1.md` §2.
