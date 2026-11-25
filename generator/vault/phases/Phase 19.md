---
type: "phase"
id: "Phase 19"
status: "pending"
tags:
  - "phase"
  - "status/pending"
effort: "6 d"
gate: "G19"
generated_by: "scripts/build_vault.py"
---

# Phase 19 — Role-scoped data views

| | |
|---|---|
| Effort | 6 d |
| Entry | G18. |
| Exit gate | [[G19]] |
| Status | pending |

## Work

Entry: G18. * Deliverable: a view specification — who sees which columns, at what aggregation, from which date — plus generated example extracts per role, so the BNIT–FLEXUS map's role selector can read them.

## Exit criteria

no view exposes data above its tier, and no DSO aggregate ever covers fewer than 5 premises — both as tests, not review. The modeller view carries the designer label in the artefact itself.

## Blockers and open items

No open issue in `docs/ISSUES.md` is named by this phase.

## Issues the playbook tracks against this phase (§10)

- [[constraint_LC-AMI-01]], [[constraint_LC-AMI-03]] — Phase 19's tests: flexibility columns excluded from AMI; DSO aggregates never fewer than 5 premises.

## Playbook open decisions on this phase

- **D22** — Consent levels (Phases 18–19). "Presence where consented" and "shares upward only by the home's consented level" imply a consent model per home that does not exist. *Recommendation:* A sourced or A-numbered consent distribution set in Phase 18, with the tiers named in the view specification so Phase 19's tests can assert against them.

## Touches

| | |
|---|---|
| Gates named | [[G18]], [[G19]] |

Source: `PLAYBOOK_v3.1.md` §2.
