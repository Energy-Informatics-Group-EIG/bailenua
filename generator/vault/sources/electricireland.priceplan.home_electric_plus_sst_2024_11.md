---
type: "source"
id: "electricireland.priceplan.home_electric_plus_sst_2024_11"
status: "reference"
tags:
  - "exposure/none"
  - "source"
  - "use/reference"
publisher: "Electric Ireland (ESB)"
licence_summary: "Electric Ireland published residential price schedule; re-use terms not stated on the document, to be confirmed in WP1 \u2026"
sha256_prefix: "4da1616fc352"
bytes: 239763
retrieved: "2026-10-12"
intended_use: "reference"
model_development_exposure: "none"
datasets:
  - "D27"
in_register: true
generated_by: "scripts/build_vault.py"
---

# electricireland.priceplan.home_electric_plus_sst_2024_11

Electric Ireland Home Electric+ Standard Smart Tariff Price Plan, price schedule valid as of 1 November 2024: day, night and peak unit rates, the published band hours, and urban and rural annual standing charges

| | |
|---|---|
| Publisher | Electric Ireland (ESB) |
| Licence | Electric Ireland published residential price schedule; re-use terms not stated on the document, to be confirmed in WP1 (as U05 for SEAI and RMDS) |
| File | `electric_ireland/1124_pp_he_plus_sst.pdf` |
| Bytes | 239,763 |
| SHA-256 prefix | `4da1616fc352…` |
| Retrieved | 2026-10-12 |
| Intended use | reference — Structural or documentary reference; shapes no parameter |
| Model-development exposure | none |
| In the register | yes |
| Manifest | `sources/electric_ireland/1124_pp_he_plus_sst.pdf.manifest.json` |

## Datasets that use it

[[D27]]

## Used for

D27's three-band time-of-use plan: the only part of the card that carries PUBLISHED band hours (Day 08:00-23:00 excluding peak, Night 23:00-08:00, Peak 17:00-19:00) and a published peak rate. The 2022 standard price schedule states no band hours at all, so this is also where the day/night plan's night window comes from - a CROSS-PLAN carry, flagged as such in export/tariffs. VINTAGE: this schedule is dated November 2024 and the simulated year is 2022. A three-band domestic smart tariff was not a published plan in May 2022, so there is no contemporaneous sheet to use; the mismatch is recorded on the dataset rather than hidden. Exposure `none`, as above.

## Substitute flag

[A] PDF, not machine-readable: the figures used are transcribed by hand into export/tariffs.TARIFF_RATES with their page and the exact published wording, per the brief's rule for a reference that is not machine-readable, and a test asserts each quoted figure is on that page of this file

## Touched by

| | |
|---|---|
| Assumptions | [[A-90]], [[A-93]] |
