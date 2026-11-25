---
type: "source"
id: "electricireland.priceplan.standard_elec_2022_05"
status: "reference"
tags:
  - "exposure/none"
  - "source"
  - "use/reference"
publisher: "Electric Ireland (ESB)"
licence_summary: "Electric Ireland published residential price schedule; re-use terms not stated on the document, to be confirmed in WP1 \u2026"
sha256_prefix: "5a717ae9df27"
bytes: 42039
retrieved: "2026-10-12"
intended_use: "reference"
model_development_exposure: "none"
datasets:
  - "D27"
in_register: true
generated_by: "scripts/build_vault.py"
---

# electricireland.priceplan.standard_elec_2022_05

Electric Ireland Standard Electricity Price Plan incl. NightSaver, price schedule valid as of 1 May 2022: 24-hour and NightSaver day/night unit rates and urban and rural annual standing charges

| | |
|---|---|
| Publisher | Electric Ireland (ESB) |
| Licence | Electric Ireland published residential price schedule; re-use terms not stated on the document, to be confirmed in WP1 (as U05 for SEAI and RMDS) |
| File | `electric_ireland/0522_pp_standard_elec.pdf` |
| Bytes | 42,039 |
| SHA-256 prefix | `5a717ae9df27…` |
| Retrieved | 2026-10-12 |
| Intended use | reference — Structural or documentary reference; shapes no parameter |
| Model-development exposure | none |
| In the register | yes |
| Manifest | `sources/electric_ireland/0522_pp_standard_elec.pdf.manifest.json` |

## Datasets that use it

[[D27]]

## Used for

D27's flat and day/night rate magnitudes and their standing charges. The schedule is dated 1 May 2022 and the estate-year run simulates 2022, so the rates are contemporaneous with the simulated year, and Cobh is urban so the URBAN standing charge is the one used. EXPOSURE IS `none` AND CANNOT BECOME ANYTHING ELSE: D27 is a record-only dataset and the frozen engine is forbidden from importing the module that reads this file, so no parameter can be fitted to it even by accident.

## Substitute flag

[A] PDF, not machine-readable: the figures used are transcribed by hand into export/tariffs.TARIFF_RATES with their page and the exact published wording, per the brief's rule for a reference that is not machine-readable, and a test asserts each quoted figure is on that page of this file

## Touched by

| | |
|---|---|
| Assumptions | [[A-90]], [[A-93]] |
