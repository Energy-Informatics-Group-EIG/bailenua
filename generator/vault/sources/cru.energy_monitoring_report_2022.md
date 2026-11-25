---
type: "source"
id: "cru.energy_monitoring_report_2022"
status: "reference"
tags:
  - "exposure/none"
  - "source"
  - "use/reference"
publisher: "Commission for Regulation of Utilities (Ireland)"
licence_summary: "Commission for Regulation of Utilities published decision and information papers; re-use terms not stated on the \u2026"
sha256_prefix: "418b4bc8b3c5"
bytes: 1679795
retrieved: "2026-10-12"
intended_use: "reference"
model_development_exposure: "none"
datasets:
  - "D27"
in_register: true
generated_by: "scripts/build_vault.py"
---

# cru.energy_monitoring_report_2022

CRU202389: Energy Monitoring Report for 2022, information paper published 13 July 2023, including the worked decomposition of a domestic electricity bill into unit rate, standing charge per day, PSO levy and VAT

| | |
|---|---|
| Publisher | Commission for Regulation of Utilities (Ireland) |
| Licence | Commission for Regulation of Utilities published decision and information papers; re-use terms not stated on the publication, to be confirmed in WP1 |
| File | `cru/CRU202389_energy_monitoring_report_2022.pdf` |
| Bytes | 1,679,795 |
| SHA-256 prefix | `418b4bc8b3c5…` |
| Retrieved | 2026-10-12 |
| Intended use | reference — Structural or documentary reference; shapes no parameter |
| Model-development exposure | none |
| In the register | yes |
| Manifest | `sources/cru/CRU202389_energy_monitoring_report_2022.pdf.manifest.json` |

## Datasets that use it

[[D27]]

## Used for

The INDEPENDENT regulator check that D27's card is decomposed the way an Irish domestic bill actually is. The report's own worked example gives a unit rate, an annual consumption of 4,200 kWh, a standing charge of EUR 0.80 per day, the PSO levy and the VAT, and those five reconcile to the estimated annual bill it states - so the transcription can be arithmetically verified rather than trusted. Published by the regulator and not by a supplier, which is why it is the cross-check and not the rate source. Exposure `none`.

## Substitute flag

[A] PDF, not machine-readable: the figures used are transcribed by hand into export/tariffs.TARIFF_RATES with their page and the exact published wording, per the brief's rule for a reference that is not machine-readable, and a test asserts each quoted figure is on that page of this file

## Touched by

| | |
|---|---|
| Assumptions | [[A-93]] |
