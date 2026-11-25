---
type: "phase"
id: "Phase 17"
status: "pending"
tags:
  - "phase"
  - "status/pending"
effort: "6 d + 5.12 d runtime"
gate: "G17"
blockers:
  - "I-081"
datasets:
  - "D11"
modules:
  - "baile_nua.engine.run"
generated_by: "scripts/build_vault.py"
---

# Phase 17 — P: chained production

| | |
|---|---|
| Effort | 6 d + 5.12 d runtime |
| Exit gate | [[G17]] |
| Status | pending |

## Work

Three real engine changes, not packaging: 1. Promote restore() to the production path.

## Exit criteria

every year package complete with manifest, checksums, code digest, catalogue entry and its start and end checkpoint hashes; verify_chain clean across 4,291 days; end hash of year *N* equals start hash of year *N+1*; continuity test shows no step change at any 31 Dec → 1 Jan; the merged multi-year view built from the year packages, not a separate run.

## Blockers and open items

[[I-081]]

## Issues the playbook tracks against this phase (§10)

- [[I-081]] — Its lesson is Phase 17's main risk — a checkpoint field carried and ignored. The person_state gap is the same shape.

## Touches

| | |
|---|---|
| Datasets | [[D11]] |
| Modules | [[baile_nua.engine.run]] |
| Issues | [[I-081]] |
| Gates named | [[G17]] |

Source: `PLAYBOOK_v3.1.md` §2.
