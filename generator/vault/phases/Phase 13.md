---
type: "phase"
id: "Phase 13"
status: "pending"
tags:
  - "phase"
  - "status/pending"
effort: "9 d"
gate: "G13"
generated_by: "scripts/build_vault.py"
---

# Phase 13 — O: crisis behaviour, bill-burden driven

| | |
|---|---|
| Effort | 9 d |
| Entry | G6 (prices), G8 (restrictions), G10 (bills). |
| Exit gate | [[G13]] |
| Status | pending |

## Work

Entry: G6 (prices), G8 (restrictions), G10 (bills). * COVID 2020–22: higher daytime load, higher self-consumption and lower export, lower EV charging and mobility, shifted flexibility availability — with the effect on tradeable flexibility in 2021 quantified.

## Exit criteria

every date verified against its source; the elasticity sourced and cited; no household's response set by anything but its own burden.

## Blockers and open items

No open issue in `docs/ISSUES.md` is named by this phase.

## Playbook open decisions on this phase

- **D18** — The behavioural elasticity of heating response to bill burden (Phase 13) is the number the whole crisis layer turns on, and I do not know whether a usable Irish estimate exists. *Recommendation:* Acquire the SEAI/CSO/ESRI studies in Phase 0 and report the elasticity you can source before Phase 13 starts. If no Irish estimate exists, the options are an A-numbered value with a sensitivity range, or no behavioural response at all — and I would rather tell you that at G0 than discover it in …

## Touches

| | |
|---|---|
| Decisions | [[D-113]] |
| Gates named | [[G10]], [[G13]], [[G6]], [[G8]] |
| Events | [[Energy crisis]], [[Recovery with conditional persistence]] |

Source: `PLAYBOOK_v3.1.md` §2.
