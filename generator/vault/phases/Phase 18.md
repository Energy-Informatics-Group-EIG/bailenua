---
type: "phase"
id: "Phase 18"
status: "pending"
tags:
  - "phase"
  - "status/pending"
effort: "10 d"
gate: "G18"
datasets:
  - "D12"
  - "D18"
generated_by: "scripts/build_vault.py"
---

# Phase 18 — 16a: PARA//EL / EdgeWare observation

| | |
|---|---|
| Effort | 10 d |
| Entry | G17 only. Needs no LEC and no FLEXUS build — it is an edge emulator per FX-BN-04. |
| Exit gate | [[G18]] |
| Status | pending |

## Work

Entry: G17 only. Needs no LEC and no FLEXUS build — it is an edge emulator per FX-BN-04.

## Exit criteria

the "complete building" dataset exists for 2021–2026; NILM error characterised and scored; flexibility event counts per home and per weather regime for 2021 → Sep 2026, with an explicit statement on whether they suffice for RD estimation and forecasting. If they do not, that is a finding, not something to fix by widening a window.

## Blockers and open items

No open issue in `docs/ISSUES.md` is named by this phase.

## Issues the playbook tracks against this phase (§10)

- [[constraint_FX-BN-04]] — Phase 18's basis: the edge emulator, which is why 16a needs no LEC or FLEXUS build.

## Playbook open decisions on this phase

- **D21** — NILM error model (Phase 18). Scoring PARA//EL's inferred appliances against GT needs a realistic error characterisation, and I have no source for PARA//EL's actual accuracy. *Recommendation:* Supply measured PARA//EL accuracy if it exists; otherwise an A-numbered error model with the failed search recorded, and the scoring reported as indicative only.
- **D22** — Consent levels (Phases 18–19). "Presence where consented" and "shares upward only by the home's consented level" imply a consent model per home that does not exist. *Recommendation:* A sourced or A-numbered consent distribution set in Phase 18, with the tiers named in the view specification so Phase 19's tests can assert against them.

## Touches

| | |
|---|---|
| Datasets | [[D12]], [[D18]] |
| Gates named | [[G17]], [[G18]] |
| Events | [[PARA--EL enrolment ramp]] |

Source: `PLAYBOOK_v3.1.md` §2.
