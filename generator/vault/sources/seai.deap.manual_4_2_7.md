---
type: "source"
id: "seai.deap.manual_4_2_7"
status: "reference"
tags:
  - "exposure/design"
  - "source"
  - "use/reference"
publisher: "Sustainable Energy Authority of Ireland"
licence_summary: "SEAI open data; terms to be confirmed in WP1 (U05)"
sha256_prefix: "e2aee5b29399"
bytes: 5540335
retrieved: "2026-10-11"
intended_use: "reference"
model_development_exposure: "design"
in_register: true
generated_by: "scripts/build_vault.py"
---

# seai.deap.manual_4_2_7

Dwelling Energy Assessment Procedure (DEAP) Manual version 4.2.7: Section 4 domestic hot water, Table 2 cylinder loss factors, Table 3 primary circuit losses, Table 3a combi boiler losses

| | |
|---|---|
| Publisher | Sustainable Energy Authority of Ireland |
| Licence | SEAI open data; terms to be confirmed in WP1 (U05) |
| File | `seai/DEAP_Manual_4_2_7.pdf` |
| Bytes | 5,540,335 |
| SHA-256 prefix | `e2aee5b29399…` |
| Retrieved | 2026-10-11 |
| Intended use | reference — Structural or documentary reference; shapes no parameter |
| Model-development exposure | design |
| In the register | yes |
| Manifest | `sources/seai/DEAP_Manual_4_2_7.pdf.manifest.json` |

## Datasets that use it

—

## Used for

U25: domestic hot water demand, cylinder and primary-circuit losses, combi boiler losses, and the instantaneous-versus-stored distinction. Also the document I-019's BER band boundaries and DEAP primary-energy scope are to be read back from (sweep flag A-16). Week 3 step 1 additionally reads APPENDIX S from it for the fabric: Table S3's filled-cavity wall and Table S4's roof set what a retrofit achieves, and Tables S1/S2/S5 were used to check the era U-value table. EXPOSURE IS SECTION-LEVEL AND THE FIELD CANNOT SAY SO (I-061). The fabric retrofit U-values are DERIVED from Appendix S, which is a tuning use. PL-DHW-01 scores hot-water volume against Section 4's 125 L/person/day, and that is …

## Substitute flag

[A] PDF, not machine-readable: values are transcribed by hand into data/deap_hot_water.yaml with their table and section, per the brief's rule for a reference that is not machine-readable

## Touched by

| | |
|---|---|
| Assumptions | [[A-15]] |
| Issues | [[I-019]], [[I-061]] |
| Decisions | [[D-043]] |
