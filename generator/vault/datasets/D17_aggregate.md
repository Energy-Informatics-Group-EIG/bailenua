---
type: "dataset"
id: "D17_aggregate"
status: "present"
tags:
  - "class/OBS"
  - "dataset"
dataset: "D17_aggregate"
name: "network_state_aggregate"
class: "OBS"
package: "Observable"
grain: "one row per premises in the register; one row per (epoch, element) for a measurement"
storage: "parquet"
subsystem: "S11"
e1_in_scope: true
rows: "158,340"
keys:
  - "premises_id"
upstream:
  - "D02"
generated_by: "scripts/build_vault.py"
---

# D17_aggregate · D17's observable view: connection register, asset ratings, feeder-head and substation measurements

D17's observable view: what a distribution operator would actually hold about its low-voltage network. The connection register — which MPRN sits on which feeder and which substation — the asset register's transformer and feeder ratings, and the feeder-head and substation power measurements.

## Facts

| | |
|---|---|
| Class | OBS — Observable. What a device, respondent, assessor or operator would see. |
| Privacy tier | [[tier_OBS|OBS]] |
| Package | Observable |
| Grain | one row per premises in the register; one row per (epoch, element) for a measurement |
| Storage, declared | parquet |
| Subsystem | S11 |
| E1 in scope | yes |
| Path | v1/observable/town14/D17_aggregate_part*.parquet (1 part) |
| Rows | 158,340 |
| Size | 2.5 MB |
| Time span | ts 2022-01-01 00:00:00+00:00 → 2022-01-14 23:45:00+00:00 |
| Resolution | not derived |
| Primary key | declared keyed_by: premises ; id columns on disk: ts, premises_id |
| Present for | town14 (158,340 rows, 2.5 MB) |
| Status | present |
| Part hash | bd71d19346af6a9c… (part 0) |
| Fields declared | 9 |

> A measurement here is the solved epoch power at the operator's metering point. E1 renders no instrument error for network metering - D18 is the only dataset with a device error model - so a value equals the quantity D17 records for the same element and epoch. That is stated rather than hidden, and it is why no gt_counterpart is declared: there is no calibrated error model for this instrument for the 6.5 too-good test to bound agreement against.

## Keys and joins

| key | declared by | required |
|---|---|---|
| `premises_id` | [[D02]] | no |

| | |
|---|---|
| Upstream (declares a key this dataset carries) | [[D02]] |

**Joins observed on disk** (DATASETS.md):

- `premises_id` → [[D18]], [[D19]], [[D27]], [[D30]]

## Produced by

- [[baile_nua.engine.stream_writer]] — streamed during the run itself

## Sources that name it

No source manifest names this dataset in its `used_for`.

## Touched by

| | |
|---|---|
| Decisions | [[D-081]] |
| Issues | [[I-099]], [[I-100]], [[I-102]], [[I-104]] |

## Key points, as the catalogue states them

- Three kinds of row in one table, told apart by record_kind: a connection-register entry, a feeder-head measurement, or a substation measurement. The register is written once per run, because the topology is built once and does not change within it.
- Both ratings are catalogue values of the pandapower standard types the network is built from, so neither is a number written in this build.
- No voltage, anywhere. The topology is a declared assumption and voltage drop is a line integral along exactly the declared feeder span, so publishing a per-unit voltage to a model developer would present an assumption as a measurement.
- No per-element loading: that ratio is ground truth. The ratings and the measurements are both here because the change request names them; their ratio is not published.
- No per-connection power. A register row names a premises and carries no measurement; a measurement row names an element and never a premises.

Schema: `scripts/baile_nua/schema/datasets.yaml`; catalogue: `DATASETS.md`.
