---
type: "source"
id: "esbn.connections.basis_of_charges"
status: "reference"
tags:
  - "exposure/none"
  - "source"
  - "use/reference"
publisher: "ESB Networks Ltd, approved by the CER (now the CRU)"
licence_summary: "ESB Networks / Retail Market Design Service published market data; re-use terms not stated on the publication page, to \u2026"
sha256_prefix: "e7d1fc8ed317"
bytes: 182864
retrieved: "2026-10-12"
intended_use: "reference"
model_development_exposure: "none"
datasets:
  - "D27"
in_register: true
generated_by: "scripts/build_vault.py"
---

# esbn.connections.basis_of_charges

ESB Networks Ltd, Basis of Charges for Connection to the Distribution System, revision 1, effective 8 February 2010: the standard domestic connection capacities and the definition of Maximum Import Capacity

| | |
|---|---|
| Publisher | ESB Networks Ltd, approved by the CER (now the CRU) |
| Licence | ESB Networks / Retail Market Design Service published market data; re-use terms not stated on the publication page, to be confirmed in WP1 |
| File | `esbn_connections/basis_of_charges_for_connection_to_the_distribution_system.pdf` |
| Bytes | 182,864 |
| SHA-256 prefix | `e7d1fc8ed317…` |
| Retrieved | 2026-10-12 |
| Intended use | reference — Structural or documentary reference; shapes no parameter |
| Model-development exposure | none |
| In the register | yes |
| Manifest | `sources/esbn_connections/basis_of_charges_for_connection_to_the_distribution_system.pdf.manifest.json` |

## Datasets that use it

[[D27]]

## Used for

D27's max_import_kw. The document states that 'Domestic connections are only available for the standard capacities of 3kVA, 12kVA, 16kVA, 20kVA and 29kVA' and treats 12kVA as the standard domestic connection, so the connection capacity on the card is a published figure rather than a round guess. It is published in kVA and the schema declares the field in kW; the conversion at unity power factor is stated on the dataset rather than left implicit. Exposure `none`.

## Substitute flag

[A] PDF, not machine-readable: the figures used are transcribed by hand into export/tariffs.TARIFF_RATES with their page and the exact published wording, per the brief's rule for a reference that is not machine-readable, and a test asserts each quoted figure is on that page of this file

## Touched by

| | |
|---|---|
| Assumptions | [[A-95]] |
