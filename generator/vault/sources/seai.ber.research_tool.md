---
type: "source"
id: "seai.ber.research_tool"
status: "calibration"
tags:
  - "exposure/tuning"
  - "source"
  - "use/calibration"
publisher: "Sustainable Energy Authority of Ireland"
licence_summary: "CC-BY 4.0 (data.gov.ie; publisher Sustainable Energy Authority of Ireland)"
sha256_prefix: "1cf9b515c8b2"
bytes: 215763007
retrieved: "2026-10-10"
intended_use: "calibration"
model_development_exposure: "tuning"
in_register: true
generated_by: "scripts/build_vault.py"
---

# seai.ber.research_tool

National BER Research Tool: anonymised domestic BER dataset, with assessed element U-values, year of construction and BER band

| | |
|---|---|
| Publisher | Sustainable Energy Authority of Ireland |
| Licence | CC-BY 4.0 (data.gov.ie; publisher Sustainable Energy Authority of Ireland) |
| File | `seai/BERPublicSearch.zip` |
| Bytes | 215,763,007 |
| SHA-256 prefix | `1cf9b515c8b2…` |
| Retrieved | 2026-10-10 |
| Intended use | calibration — Allowed to shape parameters (design 7.1 calibration sources) |
| Model-development exposure | tuning |
| In the register | yes |
| Manifest | `sources/seai/BERPublicSearch.zip.manifest.json` |

## Datasets that use it

—

## Used for

Week 3 step 1 / I-048: DERIVING the era-and-band-to-U-value mapping that data/fabric_u_values.yaml declared [A] and never read back. Gives the assessed U-value distribution conditional on year of construction and BER band, which is what the retrofit hypothesis is about - so no retrofit penetration RATE has to be assumed. TUNING-EXPOSED FOR FABRIC: not available to validate fabric. The independent fabric validation is gas (DBERNG01 tuned, DBERNG02 held out).

## Touched by

| | |
|---|---|
| Assumptions | [[A-15]] |
| Issues | [[I-048]] |
