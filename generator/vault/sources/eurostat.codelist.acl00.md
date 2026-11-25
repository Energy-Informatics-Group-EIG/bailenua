---
type: "source"
id: "eurostat.codelist.acl00"
status: "reference"
tags:
  - "exposure/none"
  - "source"
  - "use/reference"
publisher: "Eurostat"
licence_summary: "CC-BY 4.0 (Eurostat re-use policy)"
sha256_prefix: "a380e29dae9d"
bytes: 166842
retrieved: "2026-10-08"
intended_use: "reference"
model_development_exposure: "none"
in_register: true
generated_by: "scripts/build_vault.py"
---

# eurostat.codelist.acl00

SDMX codelist ACL00: HETUS activity coding list, with English labels

| | |
|---|---|
| Publisher | Eurostat |
| Licence | CC-BY 4.0 (Eurostat re-use policy) |
| File | `eurostat/ACL00_activity_codelist.xml` |
| Bytes | 166,842 |
| SHA-256 prefix | `a380e29dae9d…` |
| Retrieved | 2026-10-08 |
| Intended use | reference — Structural or documentary reference; shapes no parameter |
| Model-development exposure | none |
| In the register | yes |
| Manifest | `sources/eurostat/ACL00_activity_codelist.xml.manifest.json` |

## Datasets that use it

—

## Used for

The labels for the activity codes the HETUS tables are keyed by. The tus_00* downloads carry codes only - 'AC331', 'AC33A' - with no text, so until this was registered the mapping from an HETUS code to a modelled activity rested on recollection of what each code means. One of them was wrong: laundry was mapped to AC33A, which this codelist gives as 'Handicraft and producing textiles and other care for textiles' (2 minutes a day), when laundry is AC331 (5 minutes) and ironing AC332 (4). The brief forbids hard-coded statistics from memory; a code-to-meaning mapping from memory is the same failure one step removed, and this closes it.

## Touched by

*Nothing recorded.*
