# D18 era gating — per-home observability

**Status:** built and tested on `agent-A-phase2`; **off by default**. The
supervisor turns it on at the 2019 segment boundary, after the proof in
§5 passes.

D18 ("rendered device readings with noise and gaps", 1-minute resolution) is
the largest dataset in the package. The replay currently runs with
`omit_datasets=["D18"]`, so it is absent altogether. Writing it for every home
for every day of 2015–2026 would be **121 GB**, which does not fit the disk —
and it would also be **false**, because Ireland had no smart meters before late
2019 and the PARA//EL programme does not start until 2021. A home cannot be
observed before something was fitted to observe it.

So D18 is gated per home, on the same fact that bounds the real data: what was
installed, and when.

---

## 1. The three eras

| era | from | what D18 holds | rows / home-day |
|---|---|---|---|
| `NONE` | the start of the replay | **nothing at all** | 0 |
| `METER_30MIN` | the home's smart-meter install date | the meter's import and export registers only, at **30 minutes**, clock-aligned, carrying the **interval mean** | ~96 |
| `FULL_1MIN` | the home's PARA//EL / EdgeWare enrolment date | the home's full sensor-tier device mix at **1 minute** | ~3,500 (tier-weighted) |

A home only ever moves forwards. `NONE` is the whole of 2015–2018 for every
home, and it is the **correct state**, not a gap: there is no device, so there
is no row to be missing and no quality flag to raise.

The meter era publishes the **interval mean** of each half hour, not a
1-minute spot reading stamped at the half hour. A spot reading would not close
an energy balance against D16 or D19 and is the kind of artefact the 7.9 tell
audit looks for.

Implementation: `scripts/baile_nua/observation/era.py`; the writer branch is in
`StreamWriter.add_day` (`scripts/baile_nua/engine/stream_writer.py`).

---

## 2. What is sourced and what is A-numbered

### Sourced — the rollout curve

`sources/derived/smart_meter_rollout.csv`, 4,291 daily rows
(2015-01-01 … 2026-09-30), columns `date`, `cumulative_share_of_premises`.
Its manifest records three figures ESB Networks published:

| date | share | basis |
|---|---|---|
| 2019-10-01 | 0.00 | NSMP "commenced in late 2019" |
| 2023-11-21 | 0.75 | 1.5 M installed of the "over 2 million" target |
| 2025-09-04 | 0.83 | "over two million", "more than four out of five households" |

**A-98** covers the two things the press releases do not say: the *shape*
between the anchors (assumed linear) and the *allocation* of which premises is
metered when (no county- or area-level breakdown is published).

The curve ends at 0.83, so **about a sixth of homes never get a meter inside
the replay**. That is deliberate. Giving them one would overstate a programme
that had not finished.

### A-numbered — PARA//EL enrolment (D-111, **A-99**)

No enrolment series exists or can exist: the programme is this project's own.
D-111 states it, and A-99 covers the whole of it:

* opens **1 January 2021**, reaching **30 % of dwellings on 30 September 2026**;
* the ramp between those two points is assumed **linear**, and **flat after**
  the end of the span — D-111 states a point, not a gradient, and extrapolating
  would invent a programme decision nobody has taken;
* enrolment is skewed toward homes with **PV, heat pumps or EVs** and toward
  **estates with an energy co-op**.

The propensity weights are in `PROPENSITY_WEIGHTS`. They decide only the
**order** in which homes enrol; the **count** comes from the ramp. That is the
project's standing rule — calibrated totals, endogenous selection — and it is
why those numbers can be stated without a source: changing a weight re-sorts
the queue and cannot change how many homes are enrolled on any day.

**The co-op term is stated plainly rather than implemented as D-111 words it.**
The population synthesis holds **no co-op attribute** — there is no energy
co-op in the town model today. The term is realised as a **seeded per-estate
offset** (`estate_sd`), which reproduces the observable consequence D-111 cares
about (enrolment clusters by estate instead of spreading evenly) without
pretending to read a co-op that does not exist. If a co-op is ever synthesised,
this term should read it instead of drawing.

### A-numbered — the pre-enrolment channel set (**A-100**)

That a smart-meter exchange alone makes **import and export, at 30 minutes, and
nothing else** observable. A meter exchange fits no room sensor, no CT clamp and
no inverter telemetry, so a home in the meter era has none of them however high
its consented sensor tier is: the tier describes what PARA//EL *would* install,
and PARA//EL has not been yet.

### One modelling consequence that is not in D-111

**A home must have a meter to be enrolled.** The edge device's import and export
channels are the meter's own registers read over its HAN port, so eligibility
opens on the install date and the daily enrolment target is filled from the
eligible homes in propensity order. At town scope this costs nothing — the
realised enrolment hits its target on every day of the span, with
`shortfall_days = 0` — and any shortfall is reported in the run's diagnostics
rather than hidden.

---

## 3. How the national share is reproduced — by construction

Each home gets a deterministic uniform key from the seed tree
(`Stream.SMART_METER_INSTALL`), homes are ranked by it, and the home at rank
`r` of `N` is handed the quantile `u = (r + 0.5) / N`. Its install date is the
first day on which the sourced cumulative share reaches `u`.

The count installed by any day is then **exactly `round(share(day) · N)`** — not
in expectation, identically, for any `N`. So the realised share differs from the
sourced curve by at most `0.5 / N`, and that is the tolerance the tests assert
rather than a band chosen to make them pass.

Measured at town scope (N = 1,092, seed 20251010), worst deviation over the
whole 4,291-day span: **0.00046 = 0.5/N**.

| date | sourced | realised |
|---|---|---|
| 2018-12-31 | 0.0000 | 0.0000 |
| 2019-12-31 | 0.0451 | 0.0449 |
| 2021-01-01 | 0.2272 | 0.2271 |
| 2023-11-21 | 0.7500 | 0.7500 |
| 2026-09-30 | 0.8300 | 0.8297 |

Drawing `u` independently per home would have matched the curve only on
average, and a 50-home slice would have missed it by several homes.

The map is built over **the run's own scope**: the writer builds it from the
slice it is handed, so the realised share tracks the curve at whatever N the run
is. For the replay the slice is the town, so scope N = 1,092.

**Verified against the real town slice**, not only against test fixtures —
`synthesise_t0(master_seed=20251010)` + `build_slice(slice_kind="town")`, which
is exactly what the replay builds: 1,092 homes across 53 real estates, 119 with
PV, 17 with a heat pump, 105 with an EV. `home_facts_from_slice` reads them all;
the era map builds in 0.1 s; worst share deviation over the whole span
**0.000458, equal to 0.5/N to six places**; 906 ever metered, 186 never, 328
ever enrolled against a final target of 328 with `shortfall_days = 0`; first
install **2019-10-02**, first enrolment **2021-01-05**.

---

## 4. The size estimate

Measured by `scripts/measure_d18_era_bytes.py`, which renders real
`observe_channel` output through real `write_dataset` (real Parquet, real zstd-9,
real sidecar manifests) and divides the bytes on disk by the home-days that
produced them. The *load shape* fed in is synthetic and that is declared in the
script; the *byte counts* are measured.

| era | measured | rows / home-day | bytes / row |
|---|---|---|---|
| `METER_30MIN` | **0.785 kB / home-day** | 95.6 | 8.41 |
| `FULL_1MIN` | 28.3 kB / home-day (this script) | 3,529 | 8.23 |

The 1-minute arm is a **cross-check**, not the authority: D-101's **27.1 kB /
home-day** came off the real published estate-year (506.4 MB over 18,250
home-days). The two agree to **4.6 %**, which is what validates the method; the
projection below uses 27.1 kB.

Home-days in each era over the replay at town scope (4,291 days × 1,092 homes =
4,685,772 home-days):

| era | home-days | share | D18 bytes |
|---|---|---|---|
| `NONE` | 3,148,579 | 67.2 % | 0 |
| `METER_30MIN` | 1,193,379 | 25.5 % | 0.89 GB |
| `FULL_1MIN` | 343,814 | 7.3 % | 8.88 GB |
| **total** | 4,685,772 | | **9.78 GB** |

Ungated, the same span is **121.1 GB**. Era gating saves **111 GB** and the
remainder fits.

> The brief quoted ~130 GB ungated and ~10.9 GB gated. My computed figures are
> **121.1 GB** and **9.78 GB**. The difference is which per-home-day figure is
> used and whether the December-2014 warm-up is counted: substituting this
> script's own 28.3 kB for D-101's 27.1 kB gives **10.2 GB**, which brackets the
> briefed 10.9 GB. Nothing here contradicts the decision to gate; the headroom
> is slightly larger than briefed, not smaller.

The warm-up (December 2014) is excluded because its output is discarded.

---

## 5. How the supervisor switches engines at the 2019 boundary

### 5.0 The claim that has to hold first

The 2015–2018 segments are already on disk. Turning the gate on at the 2019
boundary is only safe if it touches **D18 alone**. If it also perturbed D10,
D11, D13, D16, D17, D17_aggregate or D19, the 2019 package would not be a
continuation of the 2018 one and the chain's whole point — one town, one seed,
one continuous history — would be quietly broken.

By construction it cannot: the two new RNG streams are **appended** values
(`SMART_METER_INSTALL = 79`, `PARAEL_ENROLMENT = 80`) and the seed tree is
counter-based, so no other subsystem's sequence moves. But "cannot" is not a
proof, so there is one.

### 5.1 Run the proof

**One command, unattended, exits non-zero on any difference.** It needs the
final 2018 checkpoint, which exists as soon as the 2018 segment writes `DONE`.

```
scripts/.venv/bin/python scripts/prove_2_3_switch.py
```

Defaults are already the replay's: checkpoint root
`work/replay_2015_2026/2018/ckpt`, day `2019-01-01`, `sim_day_offset 1492`,
master seed and slice kind read from `scripts/replay_config.json`.

What it does: verifies the checkpoint chain, restores the final 2018
checkpoint, runs **2019-01-01** from it with the gate **on**, runs the **same
day from the same checkpoint** with the gate **off**, and compares every file of
both packages **byte for byte**, ignoring D18.

Exit codes:

| code | meaning | what to do |
|---|---|---|
| **0** | every non-D18 dataset is byte-identical **and** D18 differs | switch on |
| **1** | a non-D18 difference | **do not switch**; both packages are kept under `work/prove_2_3_switch_<day>/` for inspection |
| **2** | non-D18 matches but D18 is identical too — the gate did not engage, so the run proves nothing | **do not switch**; investigate the flag |
| **3** | the proof could not run: no 2018 checkpoint, or its chain does not verify | **do not switch**; this is the absence of a proof, not a failure of the gate |

Both arms run with `omit_datasets=frozenset()`, not the replay's `["D18"]`: a
dataset that is not written cannot be compared.

**Operational note.** The two arms run **sequentially**, so peak memory is one
town-day at a time — about what one replay segment uses. Run it with the
supervisor between segments (which is where the boundary is), or expect that
much again on top of the replay's resident set. It is not safe to assume
headroom for both at once on an 18 GB ceiling.

### 5.2 Switch

Two changes to `scripts/replay_config.json`, and nothing else:

```jsonc
{
  "omit_datasets": [],          // was ["D18"] — D18 is now written
  "d18_era_gating": true        // new
}
```

**That is the whole switch — a config edit, no code edit.**
`run_segment` already passes `d18_era_gating=bool(cfg.get("d18_era_gating",
False))` through to `run_year`, which defaults it to `False`. So the supervisor
behaves exactly as it does today until the config says otherwise, and nobody
has to edit Python at the boundary under time pressure.

Note that `omit_datasets` must be emptied as well as the gate turned on: a
gated D18 that is still omitted is no D18 at all.

**Do not retro-fit 2015–2018.** They are correct as they stand: those years
have no D18 because nothing was fitted, which is precisely what the gate would
have produced. Re-running them to write an empty dataset would cost about 43
hours and change nothing. If a reader needs the absence to be explicit, it is
in each year's diagnostics.

### 5.3 Verify after the first gated segment

The 2019 year's `run_diagnostics.json` carries `benchmark.d18_era`:

```jsonc
{
  "d18_era_gating": true,
  "home_days_by_era": {"none": ..., "meter_30min": ..., "full_1min": ...},
  "n_ever_metered": 906, "n_never_metered": 186, "n_ever_enrolled": 328,
  "first_install": "2019-10-02", "first_enrolment": "2021-01-05",
  "enrolment": {"shortfall_days": 0, ...}
}
```

Three things to read off it for 2019:

* `full_1min` must be **0** — enrolment does not open until 2021;
* `meter_30min` must be **small** — the curve reaches only 0.045 by 2019-12-31,
  so about 3,700 home-days of 398,580;
* `first_install` must be **on or after 2019-10-01**.

An ungated run reports `{"d18_era_gating": false}` explicitly, so a gated and an
ungated package are distinguishable from their diagnostics alone.

---

## 6. Files

| file | what |
|---|---|
| `scripts/baile_nua/observation/era.py` | the era model: curve, dates, enrolment allocation, `EraMap` |
| `scripts/baile_nua/rng.py` | two appended streams, 79 and 80 |
| `scripts/baile_nua/observation/sensors.py` | `observe_channel` gains `interval_s` / `phase_min` overrides, both defaulting to the device class's own behaviour |
| `scripts/baile_nua/engine/stream_writer.py` | the gate, `interval_mean_held`, `era_report()` |
| `scripts/baile_nua/engine/e1_run.py` | `run_year(d18_era_gating=...)`, `benchmark.d18_era` |
| `scripts/prove_2_3_switch.py` | the byte-for-byte proof |
| `scripts/measure_d18_era_bytes.py` | the size measurement |
| `scripts/tests/test_d18_era_gating.py` | 26 tests |
