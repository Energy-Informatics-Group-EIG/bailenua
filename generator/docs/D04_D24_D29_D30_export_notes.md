# D04, D24 and the D29/D30 D11 dependency — export notes

**UNVALIDATED SIMULATION EVIDENCE: E1 engineering candidate**

Agent D, Phase 2, 14 October 2026. Branch `agent-D-phase2`.

Three things are recorded here: exactly which D04 columns are populated and
which are left null and why; the same for D24; and the answer to the D29/D30
D11 question, with the code that establishes it.

---

## 1. D04 `assets` — a per-year post-pass, not engine work

D04 was in `baile_nua.export.absent.ABSENT`. Its recorded reason was right
about the two fields it named and silent about the eighteen it did not. It is
now written by `baile_nua.export.assets.export_d04`, registered in
`export.dispatch.EXPORTERS`, so the per-year export post-pass produces it from
each finished year's package. No engine change, no re-simulation: the asset
state is a deterministic function of the master seed and is rebuilt through
`RunContext.slice`, exactly as D01, D02, D05–D08, D14 and D15 already are.

The old reason is kept verbatim in `absent.SUPERSEDED_VERBATIM` so the answer
can be checked against the objection.

### Rows written

One row per asset per version, `version = 1` throughout. Measured on the
14-day town run (1,092 dwellings): **16,894 rows**.

| asset_class | asset_type | rows | source |
|---|---|---|---|
| appliance | the ownership-prior keys | 13,245 | `build_slice`'s `owned` (`_draw_stock`) |
| heating | D02 `heating_system` | 1,092 | the dwelling's space heating |
| heating | the `DHWSystem` kind | 1,092 | `physics.dhw.dhw_system_for` |
| heating | `immersion` | 1,092 | the same DHW system |
| pv | `roof_pv` | 119 | `build_slice`'s `der.PVSystem` |
| bess | `home_battery` | 44 | `has_battery` + the engine's constants |
| vehicle | `battery_electric` | 105 | `has_ev` + the engine's constants |
| charger | `ev_charger` | 105 | the same |

### Columns POPULATED

| column | from | note |
|---|---|---|
| `asset_id` | the engine's own for appliances; MINTED for the rest | `A-<building id tail>-{HEAT,DHW,IMM,PV,BESS,EV,CHG}`. An identifier is a key, not a measurement |
| `version`, `valid_from` | `1`, and the run's own `t0` | |
| `building_id` | the slice | every asset the model holds belongs to a dwelling |
| `asset_class`, `asset_type` | the model's own labels | |
| `install_date` | **appliance only** — `t0 − age_years × 365.25`, floored to the day | recorded as a derivation, not a record |
| `age_years_at_t0` | **appliance only** — the draw's `age_years` | |
| `rated_power_w` | space heating: `ThermalParams.heat_emitter_w`; DHW store: `coil_rated_w` where coil-fed; immersion: `immersion_rated_w`; pv: `inverter_kw × 1000`; bess: `max_charge_w`; charger: `charger_w` | |
| `capacity` | pv: kWp; bess: Wh; vehicle: Wh; DHW store: litres | the three units D04's own note declares |
| `efficiency` | heat pump: `cop_at_7c`; direct electric: 1.0; immersion: 1.0; bess: round-trip | each read off the engine, not assumed |
| `pv_azimuth_deg`, `pv_tilt_deg` | the PV draw | pv rows only |
| `device_mode` | `rendered` | every asset in this run is rendered by the signature library during the day loop |
| `signature_id` | the run's **own D13 rows**, `asset_id → signature_id` | the one column read from a written part rather than rebuilt |
| `seed` | the run's master seed | the seed tree derives per-asset generators from it; no per-asset seed exists to record |

### Columns left NULL, and why

Four are **required** and are declared nulls: they are present in the frame,
null, and listed with their reasons in `assets.NULL_REQUIRED`, which
`write_dataset` records in the part's own manifest as `schema_conformance:
partial` plus `null_required_fields`.

| required column | why null |
|---|---|
| `make_model_synth` | **NO SOURCE.** The field's note says it "drives signature variation", and the model-to-model spread is drawn **once per cycle** in `devices.signatures`, not once per asset. A label here would imply a per-asset variation the renderer never applies. |
| `failure_hazard_scale` | **NO SOURCE as a Weibull scale.** Appliance failure is a `lifecourse.events` disruption with a fixed seven-day outage (`failed_appliances[k] = sim_day + 7`). There is no hazard parameter to read; `weibull` appears nowhere in `engine/run.py`. |
| `install_date` | **Populated for appliance rows; null for every other row.** Nothing else in the structural state carries a date: the DER draw returns a capacity, an azimuth and a tilt; `dhw_system_for` returns a volume and a rating. A dated install would have to come from a D03 passport event, and this run applies none to an asset. D30's own provenance already records `pv_install_date` as NOT SUPPLIED for the same reason. |
| `age_years_at_t0` | the same: `age_years` exists only in the appliance stock draw. |

Optional columns left null are listed with reasons in `assets.NULL_OPTIONAL`
and travel in the part's manifest too. The ones worth naming here:

- **`rated_power_w` is null for appliances.** `_draw_stock` sets it to `0.0` as
  an explicit placeholder — its own comment says the power comes from the
  signature library at render time. Writing the `0.0` through would claim a
  zero-power device.
- **`owner_person_id` is null everywhere.** The model attaches the vehicle and
  the charger to the **building**, not to a person. D05 carries a per-person
  `vehicle_access`, but reading an owner off it would be an inference the model
  never makes.
- **`efficiency` is null for pv** and for oil, gas, LPG, solid-fuel and
  district-heating dwellings. The PV model has a shading factor, a temperature
  coefficient and an inverter rating, and none of the three is a module
  efficiency; for a non-electric fuel the engine computes no electrical
  conversion at all ("oil or gas: not electric") and so holds no efficiency.
- **`signature_id` is null for an appliance that ran no D13 cycle** (39 of
  13,245 on the town run) and for every non-appliance class.
- **`valid_to` is null everywhere**: every row is version 1 and open-ended.

### The mechanism that lets a declared null reach disk

The alternative to a declared null is one of the two things this project
forbids: filling a required field with a plausible number, or lowering the
schema so the gap stops showing. So `schema.validate.validate_frame` gained one
narrow argument, `permit_null_required`, and `io.write_dataset` gained
`null_required={field: reason}`:

- it relaxes **only** the required-null check — type, enum, `forbidden` and the
  leakage audit all still run;
- the column must still be **present**, so a reader sees the field and its
  nulls rather than a frame that quietly lacks it;
- naming a field that is **not** declared required is an error, so a stale
  exemption cannot sit unnoticed;
- a reason is **mandatory**, and every accepted exemption is written into the
  part's sidecar manifest.

Defaults are empty, so no existing caller changes behaviour: a part with no
declared nulls records `schema_conformance: "full"` and carries no
`null_required_fields` key.

---

## 2. D24 `calibration_targets` in the per-year post-pass

D24's `absent` entry gave two reasons. **One is gone and one stands.**

*Gone:* "its release package is `v1/evidence/` — outside the paths this export
was permitted to write". The per-year post-pass already creates
`<year>/pkg/evidence/` before calling `export_all` — it has to, because D22 and
D23 are META too. That half of the objection was about one caller's
permissions, not about the data. The post-pass now **proves** the directory is
usable with a probe write (`replay_supervisor.prepare_evidence_package`) and
records the proof in the year's export report, so a read-only or full volume is
reported as itself instead of as three mysterious dataset failures.

*Stands, and is now written into the data:* five required fields have no
source. `baile_nua.export.calibration_targets.export_d24` fills the eleven
columns the old entry's own `field_mapping` said could be filled and declares
the five it said could not.

| column | status | from / why |
|---|---|---|
| `target_id`, `unit`, `source_sha256` | populated | the artefact's own, unchanged |
| `statistic` | populated | the artefact's `quantity`, RENAMED |
| `model_development_exposure` | populated | the artefact's `exposure`, RENAMED |
| `value` | populated | the artefact's scalar value; null for the one table-valued target, whose table travels in `value_json` |
| `value_json` | populated | a JSON string carrying `conditioned_on`, the artefact keys the schema declares no column for (`source_key`, `source_title`, `year`, `scope_note`), and the table value where there is one |
| `source_file`, `source_url`, `source_licence`, `intended_use` | populated | `sources.REGISTRY[source_key]`; one target names two sources and its register fields are joined with `" + "` rather than one being picked |
| `retrieved_at` | populated | the source's own per-file manifest; the **earliest** of the two for the composite target |
| `domain` | **NULL, required** | declared "population \| activity \| appliance \| physics \| weather \| mimic". The 113 targets are household electricity, household gas and median rental floor area — none of the six. Any value would be a misclassification. A **schema** question for Appendix D. |
| `tolerance` | **NULL, required** | the tolerances that exist are prose and are stated per plausibility **check**, not per target ("ratio in [0.40, 1.00]"), so there is no number for a declared float column. |
| `tolerance_kind` | **NULL, required** | nothing emits "absolute \| relative \| sampling-error-band"; it would have to be inferred from a tolerance that does not exist. |
| `evidence_tag` | **NULL, required** | "[C] \| [P] \| [A] \| [U]" appears nowhere in the build. |
| `provisional` | **NULL, required** | nothing records which target the design's provisional-margins statement applies to; a blanket value would be a claim about all 113. |

### The target year, and a substitution that is recorded

`build_d24(year)` reads published CSO tables and raises `TargetError` on the
first missing cell rather than guessing. **The tables cover 2016–2023; the
replay spans 2014–2026.** So `export_d24` asks for the run's own year first and
falls back to 2022 — `build_d24`'s own default, and the year of the committed
`v1/evidence/d24_calibration_targets.json` — when the sources do not reach it,
recording the substitution in the part's manifest, in its limitations and in
`targets_for_year`'s returned note. The years that get substituted targets are
**2015, 2024, 2025 and 2026**, asserted in
`test_which_replay_years_get_substituted_d24_targets` so a change in source
coverage fires the test.

A D24 row is a published reference statistic rather than an output of the
simulated year, and every row records the year it was actually built for inside
`value_json` — so the substitution costs a reader nothing as long as it is
stated, which is the whole point of stating it.

---

## 3. D29 / D30 — what they need from D11, and whether the replay supplies it

### The dependency, in the code

`export.nonsensor_datasets.export_d29` and `export_d30` both call
`build_truth_by_premises`, which calls `occupied_weekday_hours(ctx)`
(`scripts/baile_nua/export/nonsensor_datasets.py:118`). That function:

1. globs `<run_root>/ground_truth/D11_part*.parquet` and **raises
   `ExportError`** if there is none — "Defaulting it would hand the survey
   generator a flat truth and make its occupancy answers meaningless";
2. reads `start`, `end`, `location_kind`, `location_id`, keeps
   `location_kind == "building"`, and raises if none survive;
3. raises if the recorded span contains no weekday.

So the required D11 input is precisely: **at least one `D11_part*.parquet`
under the run root's `ground_truth/`, carrying at least one
building-located presence row, spanning at least one weekday.** Nothing else in
D29 or D30 touches D11.

### Does the real replay config supply it? **No.** The expectation was wrong.

The brief for this work said the expectation was yes, because the town14 run
wrote 1,130,467 D11 rows. The town14 run does satisfy it (the part's own
manifest says 1,130,**417** rows — a transposition in the brief, not a
discrepancy that matters). **The replay does not**, and the chain is:

- `engine/e1_run.py:939` — `collect_presence=(day.sim_day < collect_presence_days)`
- `engine/e1_run.py:593` — `collect_presence_days: int = 14`, a default
- `engine/calendar.py:364` — `sim_day=sim_day_offset + i`, so `sim_day` is
  **global** across the whole replay (D-110: the seed tree is keyed on
  `sim_day`, and restarting it at zero would re-draw an earlier year)
- `scripts/replay_supervisor.py` — `run_segment` calls `run_year(...)` and does
  **not** pass `collect_presence_days`

Every segment the replay keeps starts at `sim_day_offset` 31 or later (2015 at
31, 2016 at 396, … 2026 at 4049), so no day of any delivered year has
`sim_day < 14`. **No presence row is collected, no D11 part is written, and
D29 and D30 fail in every delivered year.** The only segment under the gate is
`warmup_2014` (offset 0), whose output is discarded.

`scripts/tests/test_d29_d30_need_d11.py::test_which_replay_segments_can_carry_d11`
asserts exactly this, so it fires if the config gains a
`collect_presence_days` or the engine's default moves.

### The fix is one argument, and it is safe — but it is not mine to make

Passing `collect_presence_days=seg["sim_day_offset"] + 14` in the supervisor's
`run_year` call would give every year fourteen days of D11 and unblock D29/D30.
It perturbs nothing: `collect_presence` is a **retention flag**. The venue
resolution inside the guarded block goes through the counter-based seed tree on
its own `(person, day, activity)` key, which the D10 path already resolves on
every day — `engine/run.py:509` says so in terms: "resolving it on every day
rather than only the first `collect_presence_days` advances no other stream and
changes no other draw". `test_collect_presence_is_a_retention_flag_and_draws_nothing`
asserts that statement is still in the engine.

It is still a change to a **running** replay's per-day behaviour and to the
volume of a ground-truth dataset, so it is reported, not made.

### Testing against the 2015 package

`test_each_finished_replay_year_against_the_d11_dependency` runs the real
predicate against every finished year's own package and skips with a reason
until one exists. The 2015 package is expected about **07:32 on 15 October**
(the coordinator's measured rate; the supervisor's own seconds-per-day
understates by ~2.15× because it divides elapsed segment time by the absolute
`sim_day`). When it lands, the test asserts the predicted outcome on the real
package: no D11 part, `occupied_weekday_hours` raising, and the year's export
report recording D29 and D30 as failed or not-written rather than carrying a
silently empty survey.

---

## 4. The 2015 D24 catch-up

The replay running now is the **main checkout**, not this branch, so the
per-year post-pass that executes for 2015 will not contain the D24 exporter.
**2015 will land without D24 and needs a catch-up pass.**

`scripts/export_catchup.py` is that pass. It re-runs the export post-pass over
a finished year for named datasets, and it is safe against an
already-exported package:

- it **refuses** a segment with no `DONE.json`, because that segment is either
  still running or failed and its package may be half-written;
- it **moves** existing parts into `<segment>/superseded/<timestamp>/` rather
  than letting `cleanup_stale_parts` unlink them, so a re-export that fails has
  not destroyed the part it was replacing;
- it leaves the run's own `export_report.json` **untouched** and writes
  `export_report_catchup_<timestamp>.json` beside it, appending to
  `export_catchup_log.json`;
- `--dry-run` says what would move and what would run, and writes nothing.

```
scripts/.venv/bin/python scripts/export_catchup.py --dry-run work/replay_2015_2026/2015 D24
scripts/.venv/bin/python scripts/export_catchup.py           work/replay_2015_2026/2015 D04 D24
```

Writing it found a real bug: a **D24-only** export raised `SourceError` saying
`cso.electricity.dbere101_by_dwelling_ber` "is not declared", because
`build_d24` resolves every target through `sources.REGISTRY` and nothing had
imported `sources_registry` yet. A full `export_all` starts at D01 and imports
the registry on the way, so the trap only shows when D24 runs first — which is
exactly what a catch-up pass does. `targets_for_year` now imports the registry
before it reads a source, the same way `RunContext.slice` documents.
