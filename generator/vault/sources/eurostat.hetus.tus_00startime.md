---
type: "source"
id: "eurostat.hetus.tus_00startime"
status: "calibration"
tags:
  - "exposure/tuning"
  - "source"
  - "use/calibration"
publisher: "Eurostat"
licence_summary: "CC-BY 4.0 (Eurostat re-use policy)"
sha256_prefix: "b681d632fd0f"
bytes: 10644931
retrieved: "2026-10-11"
intended_use: "calibration"
model_development_exposure: "tuning"
in_register: true
generated_by: "scripts/build_vault.py"
---

# eurostat.hetus.tus_00startime

HETUS 2000/2010: participation rate in the main activity by sex and time of the day (tus_00startime)

| | |
|---|---|
| Publisher | Eurostat |
| Licence | CC-BY 4.0 (Eurostat re-use policy) |
| File | `eurostat/tus_00startime.csv` |
| Bytes | 10,644,931 |
| SHA-256 prefix | `b681d632fd0f…` |
| Retrieved | 2026-10-11 |
| Intended use | calibration — Allowed to shape parameters (design 7.1 calibration sources) |
| Model-development exposure | tuning |
| In the register | yes |
| Manifest | `sources/eurostat/tus_00startime.csv.manifest.json` |

## Datasets that use it

—

## Used for

The diurnal participation profile. This is the single most important HETUS table for a semi-Markov engine, because it constrains WHEN each activity happens rather than only how long it lasts. TUNING-EXPOSED for activity timing: U32's sleep offsets and week 3's appliance timing are derived from it, so the awake-share fit and the V0 activity-share check are CONSISTENCY checks against a calibration input and NOT independent validations. The independent check on the resulting load shape is LP1 via PL-PEAK-01, exposure 'none'. See I-060.

## Substitute flag

[A] UK donor; HETUS has no Irish data at all (I-008, U04, K02)

## Touched by

| | |
|---|---|
| Issues | [[I-060]] |
