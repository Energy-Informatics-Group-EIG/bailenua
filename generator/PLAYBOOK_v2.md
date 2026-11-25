# PLAYBOOK v2 — the Baile Nua historical replay

**Status: DRAFT FOR APPROVAL. No code written or changed.**
**Supersedes PLAYBOOK_v1.md. Phase 1 starts only when you say go.**

> **UNVALIDATED SIMULATION EVIDENCE.** Every quantity here is measured on this
> machine and labelled as such, read from a file in this repo and cited, or
> flagged unverified. Nothing is an estimate presented as a fact.

Scope: **1 Jan 2015 → 30 Sep 2026**, **4,291 days**, **3 leap days** (2016,
2020, 2024), then nightly live forward mode. Baseline: branch
`hrsd-v1-freeze2-finish`, tag `v1-engine-freeze-2.1`, digests `b8252f59…` /
`e0ab1c83…`, suite 1,108 tests with 1 known failure (I-101), **nothing pushed**.

### What changed from v1

* All ten §8 decisions settled; §8 now holds only new ones.
* **Two corrections I owe you up front.** The fast path is **24 days, not 19**
  — Phase 1 grew because a second population defect is confirmed (below), and
  Phase 4 grew to carry the built-date mapping. And my v1 D18 sizing was wrong
  by a factor of 1,024 (a bytes/kB slip); corrected in §6, and the conclusion
  reverses — **D18 for enrolled homes fits on the internal disk**.
* New scope **M** (technology uptake), **N** (observable layer by era), **O**
  (crisis behaviour), **P** (year-on-year delivery), and a **coupled BNIT run**
  for flexibility.
* Total **≈111 working days**, up from 75. P is now a **chained** serial run:
  years inherit state rather than restarting, which costs the jobs=2 option
  (5.12 days wall instead of ~2.56) and makes Phase 15 real engine work rather
  than packaging.

---

## 1. Goal, non-goals, boundary

**Goal.** One town simulated day by day from the real weather, prices, calendar
and demography of each day, so any pattern is attributable to something that
happened — and so the 2022 census becomes a **test** rather than an input.

**Non-goals.** Not a scenario engine. Not a detector (r4 §248). Not validated.
No transport model.

### The boundary, with finding 3 resolved

R02: "Baile Nua is a base model… Scenarios and interventions run in BNIT."
U06: "(a) in the base town; BNIT can re-tier." U10: "(a) for existing retail
tariffs; dynamic and flex signals stay in BNIT."

**Finding 3 accepted, and it is the right call.** Residential flexibility
services in Ireland were negligible before ~2023, so FLEXUS activity is **not
"what happened"** and cannot sit in a replay that claims to be real.

| layer | where | content |
|---|---|---|
| **Base replay** | **Baile Nua** | GT at full resolution for all 4,291 days; observable layer **by era** (register reads → smart-meter interval) |
| **Coupled run** | **BNIT**, over the frozen replay | PARA//EL / EdgeWare enrolment from 2021; all flexibility services — LEC programmes, signals, offers, delivery, settlement — via the BN-6 / BN-7 intervention interface; writes the flexibility datasets and D18 for enrolled homes |

The replay is frozen before the coupled run reads it. The coupled run never
writes into the base packages.

| scope | Baile Nua | BNIT |
|---|---|---|
| A, B, C, E, G, H, I, J, K, P | **yes** | — |
| D COVID restrictions, WFH, mortality | **yes** | — |
| F estates, growth, amenities | **yes** (projection-labelled after today) | alternative trajectories |
| F Abbeylands construction loads, LEC/MV | **backlog, §11** | — |
| F/I transport, modes, CMATS, mode shift | — | **yes** |
| M uptake 2015–26 and one official trajectory | **yes** | alternative uptake rates |
| N observable layer by era | **yes** (eras 1–2) | **enrolment + D18** (era 3) |
| O crisis behaviour | **yes** | — |
| Flexibility services, any year | — | **yes** |

---

## 2. Phases

Order: **population defects → engine generalisation → data → behaviour →
validation → run → coupled run.** No phase starts before its predecessor's
gate. Every phase ends with a freeze cycle (§4.4).

### ⭐ FAST PATH — Phases 0–4, 24 days, usable on its own
A real-weather, census-back-tested replay. Deliverable in its own right.

### Phase 0 — Baseline, decisions, issue logging (2 d)
* **Entry:** v2 approved.
* **Work:** answer §8; record starting digests; confirm the decade retired and
  archived. **I-105 (DST), I-106 (age structure) and I-107 (map/D01 alignment)
  are already logged** — written on instruction while v2 was drafted.
* **Exit G0:** every §8 item answered; every §3 source acquired with licence and
  manifest, or dropped with a written reason. **No source assumed obtainable.**

### Phase 1 — Population defects (5 d, was 3)
* **Entry:** G0.
* **Work — two defects, not one:**
  * **I-069.** `synthesise.py` draws economic status with **no age
    conditioning**: 241 "students" with a **median age of 45**, and 8,426
    venue-presence rows (**7.3% of 114,951**) carry no venue id.
  * **I-106, new and confirmed.** Measured at t0 (2022-01-01) against SAP2022
    for the town's own small areas, so it is **not** a back-projection
    artefact:

    | band | SAP2022 | town | expected | actual | deficit |
    |---|---|---|---|---|---|
    | 65+ | 13.2% | 9.4% | 386 | 273 | **−113 (−29%)** |
    | 75–84 | 4.4% | 2.3% | 130 | 67 | **−63 (−48%)** |
    | 85+ | 1.2% | 0.3% | 34 | 10 | **−24 (−71%)** |
    | 0–44 | 60.0% | 63.7% | 1,751 | 1,857 | +106 |

    The deficit worsens monotonically with age — the signature of a truncated
    or under-dispersed draw at the top of the distribution. The town is a
    2,917-person slice of Cobh's 14,148, so shares should match and do not.
* **Exit G1:** economic status age-conditioned; the age structure within
  declared tolerance of SAP2022 **in every band including 85+**; the 7.3%
  venue-id gap falls to a declared residual.
* **Why first:** `venues.py` argues it itself — a college venue type "would
  make the symptom go away by building a venue to serve a population bug".
  **No feature work on population or venues until G1.** And **D3's COVID
  arithmetic must not be computed until G1 passes**: with a census-correct
  structure, 85+ goes from 10 to ~34 and the expected death count rises
  roughly 2.5–3×.

### Phase 2 — Time axis (6 d)
* **Work:** `build_realisation(year)` → date range (**closes I-088**; the data
  is already real observed Met Éireann and both stations are on disk from
  1962/1955, so this is an interface change, not acquisition).
  `build_calendar` currently **raises `NotImplementedError` for any year but
  2022** — generalise, add per-year holiday and school-term tables. Retire
  `DAYS_PER_YEAR`.
* **Exit G2:** a 366-day 2016 run closes energy balance; **29 Feb present in
  2016, 2020, 2024**; all 12 holiday tables verified independently; the 2022
  table still carries the **18 Mar 2022 one-off** and still excludes **St
  Brigid's Day, which begins 2023**.

### Phase 3 — DST and clocks (5 d)
* **Work:** UTC sim, **local-clock schedules**, local-time exports.
  `MINUTES_PER_DAY = 1440` backs every per-minute array;
  `stream_writer.py:195` builds a UTC 1440-minute index; `tariffs.py:344`
  declares `BAND_CLOCK = "Europe/Dublin local clock"`.
* **Exit G3:** tariff bands on the correct local hour across **all 23
  transitions**; a 23-hour and a 25-hour day both balance.
* **Note:** a **live defect today** (I-105), independent of this plan.

### Phase 4 — Population base and the census checkpoint (6 d, was 5)
* **Work:** t0 is **2022-01-01, Census 2022**; only `sap2022` is on disk.
  Acquire **Census 2016 SAPS**, parameterise the vintage, age forward to
  1 Jan 2015.
* **Finding 2, with a correction.** You expected Belgard (2024) to be in
  today's t0. It is not: **`build_year` runs 1860–2021 and there are zero
  dwellings after 2021**, so the 2022 stock already excludes everything built
  later — and neither Belgard nor Cluain Ard exists in the model under any
  name. The real work is therefore the **mapping**: once estates carry
  completion dates, G4 must state how the town's small areas reconcile to
  SAP2022 dwelling counts at the census date, with Cluain Ard (2019) **inside**
  the 2016-aged base by 2022 and Belgard (2024) **outside** it.
* **Exit G4 — the prize:** run 2015 → 2022 and compare the simulated 2022
  state against actual SAP2022 marginals within declared tolerances, on both
  **population** and **dwelling stock**. Today the census *is* the base, so it
  can never be a test; after this it is a seven-year out-of-sample back-test.

### Phase 5 — Vintaged rates and two price regimes (7 d)
`SourcedValue` has **no validity field** and uses `__slots__`; vintage is a
free-text string today. Add validity intervals, a date-keyed resolver, and the
**SEM SMP → I-SEM switch at Oct 2018**.
**Exit G5:** no rate resolves outside its interval; every vintage cites a
document on disk — `test_d27_every_sourced_rate_is_in_its_cited_document` greps
the cited document's **bytes**, which is this phase's real cost.

### Phase 6 — Market and system data (5 d)
SEM SMP, I-SEM DA/BM, EirGrid demand and carbon; build D31's market series.
**Exit G6: E2-7 passes for the first time** — today
`observation/nonsensor.py:40` records it as "**What is NOT built, and E2-7
fails on it**".

### Phase 7 — Life course and housing chain (8 d)
**Exists:** vacancy on last-occupant loss (`tenyear.py:893-905`); the vacant
load `VACANT_FROST_SETPOINT_C = 7.0`; refill from **VAC04's 5–6% Cork rate and
VAC17's gross flows**; `separation`; births from `vsa36`/`vsa104` by mother's
age.
**Add:** sourced **probate/sale/letting durations** (today vacancy is
year-granular — a dwelling can empty and refill with no elapsed time);
**movers-based household composition** (today `integers(1,5)` size,
`integers(20,70)` age, all `role="adult"`, all `"at work"` — **no child has
ever moved into a Baile Nua dwelling**, despite SAP2022 movers being on disk);
**pre-occupancy renovation**; **occupancy steps as dated passport events** (the
map covers only six building-change types, so **no occupancy step is a D03
event today**); **tenancy/meter structural break** with tenure transition;
**individual emigration** (today folded into whole-household `move_out`,
`[A] A-25b`).
**Exit G7:** chain complete and sourced. **Movers composition first** —
cheapest fix, data already present.

### Phase 8 — Institutional population and COVID behaviour (10 d)
A care-home population, then restriction levels by date, school closures,
time-varying WFH, age-banded excess mortality pre-vaccination, vaccine rollout
by age band, care-home deaths separated.
**Why together:** the same gap from two directions. There is **no institutional
population** today — every "institution" hit is a third-level education venue —
so **every modelled death vacates a dwelling**.
**Exit G8:** the D3 presentation rule is implemented in the artefact, not just
in prose; care-home deaths vacate no dwelling; **every IFR, seroprevalence and
national death figure fetched and cited before being written**.

### Phase 9 — Town growth and amenities (8 d)
Exercise D01/D02's **existing but never-used** validity intervals (`valid_to`
populated on **0 of 1,092** dwellings; `version` = 1 on all). Cluain Ard 2019
(Part V 10%); Belgard 2024 nZEB A-rated (190 A-rated dwellings already exist,
so the archetype is available) with Part V 10% or 20% by land-purchase date,
sourced; Abbeylands phased to 2027; Part V tenure (D02 has `rented social`, 116
present); first occupants from CSO new-dwelling data; amenities by statutory
ratio, extending the venue layer's derived-count + sourced-capacity pattern
(DoE; Childcare Guidelines ~20 places/75 dwellings; Compact Settlement
Guidelines 2024; retail by catchment); network growth (`_trafo_type` already
auto-sizes).
**Exit G9:** no dwelling produces data before completion; +300 dwellings
(**+27.5%**) adds ~15 transformers, ~18 feeders, ~615 buses at current ratios,
and D17 rows scale as **96 epochs × (transformers + feeders)** — a rule that
reproduces the measured 157,248 rows exactly.
**Excluded → §11 backlog:** construction-site loads and LEC/MV.

### Phase 10 — M: technology uptake (6 d)
* **Work:** yearly 2015–2026 uptake of rooftop PV, BESS, heat pumps,
  insulation/windows/deep retrofit, EVs and chargers from SEAI grant data, BER
  statistics, CSO/SIMI and ESB Networks microgeneration connections.
  **Assigned by tenure, income, BER and dwelling type — not uniformly.**
  After today, one trajectory toward sourced Climate Action Plan targets,
  labelled projection.
* **Exists:** the mechanism — `retrofit_fabric`, `retrofit_heat_pump` and three
  DER events, keyed to `HEBEU37`, already emit dated passport events. Only the
  **rates** are time-invariant.
* **Exit G10:** every install a dated BEP event changing load from that date;
  uptake matches national series within tolerance per year; **adoption stays
  exogenous** so years remain parallelisable (§6).

### Phase 11 — N: observable layer by era (7 d)
GT stays full-resolution throughout; **only the observable layer changes.**

| era | from | observable |
|---|---|---|
| 1 | 2015 | bi-monthly actual or estimated register reads only |
| 2 | smart-meter install (ESB rollout 2019–24, sourced by area and year) | 30-minute import/export interval data, with realistic gaps and estimates |
| 3 | 2021, **coupled run** | PARA//EL/EdgeWare enrolment **ramping home by home, not a switch-on** → 15-minute and device-level D18 **for enrolled homes from their enrolment date only** |

* **Exit G11:** no home has interval data before its install date; era
  transitions dated per home; the effect on **D18, D19, D30, D31** reported
  with measured byte counts; **flexibility event counts per home and per
  weather regime for 2021 → Sep 2026**, with an explicit statement on whether
  they suffice for RD estimation and forecasting. If they do not, say so — that
  is a finding, not a failure to fix by widening a window.

### Phase 12 — O: crisis behaviour (8 d)
* **Entry:** G5, G6 (prices), G8 (COVID restrictions).
* **COVID 2020–22:** higher daytime load, higher self-consumption and lower
  export, lower EV charging and mobility, shifted flexibility availability —
  with the **effect on tradeable flexibility in 2021 quantified**.
* **Energy crisis 2021–24:** wholesale gas and electricity path; **each Irish
  retail price change by supplier and date** (CRU or supplier notices); heating
  oil price; electricity credits by date and amount; behavioural response —
  lower setpoints, shorter hours, fewer rooms heated — sourced from
  SEAI/CSO/ESRI, **stronger for low-income and Part V households**; result:
  lower indoor temperatures visible in comfort and health-risk indicators.
* **Recovery 2023–24** as prices ease, **with partial persistence only if the
  evidence supports it** — if it does not, no persistence.
* **Exit G12:** every date verified against its source; every behavioural
  magnitude sourced or A-numbered.

### Phase 13 — Policy events, behaviour, data flaws (6 d)
Electricity credits 2022–24; MSS export payments from Dec 2022; smoky coal ban
Oct 2022; supplier switching (CRU); holidays abroad (empty homes), Christmas
returns, college terms, hybrid days by sector, 2022 temporary-protection
arrivals; observable-layer flaws — estimated reads, meter swaps, comms gaps,
DST glitches — **tied to real events**.
**Exit G13:** every dated event cites a source or carries an A-number.

### Phase 14 — Validation (6 d, was 5)
Named targets and tolerances against **ESB Networks SLPs per year 2015–2025**
(D9), EirGrid demand shape, CSO counts. **No CER/ISSDA** (D1).
**Exit G14:** every target passes, or fails and is reported as a failure. **No
tolerance widened to manufacture a pass.**

### Phase 15 — P: chained year-on-year production (6 d + runtime)
* **Work — three real changes, not packaging alone:**
  1. **Promote `restore()` to the production path.** It exists
     (`run.py:1129`), restores `rc` zone temperatures, `battery.soc`,
     `ev_soc`, `failed_appliances` and `dhw.temp_c`, and refuses a partial
     restore. But its own docstring says production never uses it: "a whole-year
     re-run … never restores anything — it recomputes from day zero." Today it
     is a **replay-test harness only**.
  2. **Close the `person_state` gap.** The `Checkpoint` dataclass carries
     `person_state` ("per-person evolving state"), and `restore()` iterates
     **only `household_state`** — so each person's current activity, location,
     routines and habits are **written and then ignored**. This is exactly the
     I-081 failure mode: `dhw_tank_c` was carried but ignored, so "every
     replayed day began with the cylinder at its construction temperature …
     and diverged on the morning reheat", invisible for weeks.
  3. **Make `sim_day` continuous 0 → 4,290.** The `SeedTree` is keyed on
     (seed, entity, `sim_day`), so a year restarting at `sim_day = 0` would
     **re-draw year 2015's random numbers**. Either `sim_day` runs continuously
     across the whole span, or the seed entity gains the year — and the first is
     the honest one for a chain.
* **Exit G15:** every year package complete with manifest, checksums, code
  digest, catalogue entry, **and the start and end checkpoint hashes**;
  `verify_chain` clean across all 4,291 days; **end hash of year *N* equals
  start hash of year *N+1*** at every boundary; continuity test shows no step
  change at any 31 Dec → 1 Jan; the merged multi-year view builds **from the
  year packages, not a separate run**.
* **Risk: high.** This puts restore on the production path for the first time,
  and the project has already paid once (I-081) for a checkpoint field that was
  carried and ignored. The replay test is the guard and must be extended to
  person state before the chain is trusted.

### Phase 16 — Coupled BNIT run: enrolment and flexibility (10 d)
* **Entry:** G15 (replay frozen), **plus entry gates on the LEC build and the
  FLEXUS build** — neither is in this repo and neither is mine to assess.
* **Work:** PARA//EL/EdgeWare enrolment curve from 2021; flexibility services
  over the frozen replay via BN-6/BN-7; writes the flexibility datasets and era-3
  D18. Labelled a **BNIT run** throughout.
* **Exit G16:** the coupled run reads the frozen replay and writes only
  flexibility datasets; no base package is modified.

**Total ≈111 working days** (0–15: 101 d; Phase 16: 10 d), plus 5.12 days of
chained runtime.

---

## 3. Data acquisition

Storage `sources/<family>/<file>` + `*.manifest.json` (bytes, SHA-256),
registered with URL, licence, title, use and exposure. `sources.require`
**re-hashes on every use and refuses changed bytes** — that is the provenance
record, and it already exists.

**A missing source makes the run REFUSE.** No fallback, no substitution, no
interpolation across an absence. Precedent: `require` already raises
`SourceError: source 'x' is registered but missing from disk`.

### On disk
Met Éireann `hly3904` (1962→2026-10-01) and `hly1075` (1955→2026-10-01), hourly,
CC-BY — **the whole span**; solar irradiance **derived** (pvlib Ineichen + Erbs
from observed cloud and sunshine, no `glorad` in the files); ESB Networks SLPs
**2022 only**; CSO `vsa08` deaths (annual), `vsa36`/`vsa104` births and
fertility, `ep006` migration, `pea01` estimates, `HEBEU37` installations,
`VAC04`/`VAC17`/`F2095` vacancy, `SAP2022` movers; SEAI BER research tool
(year-stamped) and `EBA02`/`EBQ02`.

### To acquire
| input | for | cadence | licence |
|---|---|---|---|
| Census 2016 (or 2011) SAPS, Cobh | Phase 4 | census | CC-BY |
| CSO **weekly** deaths | Phase 8 | weekly | CC-BY |
| Holidays 2015–26, school terms | Phase 2 | annual | python-holidays / DoE |
| SEM SMP → Sep 2018 | Phase 6 | half-hourly | to confirm |
| I-SEM DA/BM from Oct 2018 | Phase 6 | half-hourly | to confirm |
| EirGrid demand + carbon | Phase 6 | 15-min | to confirm |
| Retail tariffs per year + **supplier price changes by date** | 5, 12 | per change | CRU / notices |
| COVID restriction levels, school closures | 8, 12 | event | gov.ie |
| Vaccination by age band | Phase 8 | daily | HSE/HPSC |
| CSO WFH series | 8, 12 | quarterly | CC-BY |
| Google mobility | 8, 12 | daily, **Feb 2020–Oct 2022 only** | CC-BY |
| **SEAI grant statistics by year** | **M** | annual | SEAI |
| **ESB Networks microgeneration connections** | **M** | annual | ESBN |
| **EV registrations + chargers (CSO/SIMI)** | **M** | monthly | CC-BY / SIMI |
| **Climate Action Plan targets** (heat pump, EV, rooftop solar) | **M** | periodic | gov.ie |
| **CSO appliance ownership**; oil and solid-fuel decline | **G** | periodic | CC-BY |
| **ESB Networks smart-meter rollout by area and year** | **N** | annual | ESBN |
| **Heating oil price** (CSO or SEAI) | **O** | monthly | CC-BY |
| **SEAI/CSO/ESRI setpoint-response studies** | **O** | study | varies |
| **ESB Networks SLPs per year 2015–2025** | Phase 14 | annual | published |
| CSO/ESRI projections, Cork CDP targets | Phase 9 | periodic | CC-BY / council |
| Storm warning register | Phase 2 | event | Met Éireann |

Storms need no acquisition to **appear** — derived from observed wind
(`storm_days_from_weather`), and **Ophelia (2017), Emma (2018) and Éowyn (Jan
2025) are all inside the station data**. A register adds only the warning
*status*. GAA and televised fixtures have **no open-data source**: `sport`
already carries **A-43** ("'sport' matches 115 tables, none of them a fixture
list"), so dates are tabled as declared A-numbered assumptions with the failed
search recorded.

---

## 4. Rules

1. Every value **sourced or A-numbered**, with the search that failed.
2. **No fabricated data** — no synthetic geometry presented as surveyed
   (`structural.py` already refuses "a fabricated polygon that would read as
   surveyed geometry"); no interpolation across an absence; no national figure
   applied to the town without the scaling stated.
3. **Three labels on every row:** `observed` vs `projection` (cut-over = run
   date), and `provisional` vs `final` for monthly drops and lagging inputs.
4. **Freeze cycle per phase:** new tag, digests recomputed, `_frozen_root`
   rebuilt from the tag, worker and aggregator reissued as **new files** (never
   editing a mode-500 original — I-080), digests verified. 0.5 d/phase,
   included.
5. **Nothing pushed.** Repo and `code/` stay local.
6. **Stop and ask** on anything not covered here.
7. **No gate passed by widening it.**
8. **Nothing deleted** — superseded artefacts renamed aside.
9. **Each day stamped with its code digest** (scope K), which closes the I-090
   class permanently.

---

## 5. Tests

**Assumptions to remove.** Measured: `365` appears in the suite **4 times
across 3 files**, plus an `or 365` default in `plausibility/checks.py:902` and
the `365 * n_years` sizing formulas in `release/policy.py`.
`tariffs.py:179` notes "2022 is not a leap year" and standing charges are
365-day figures. Small and bounded — under a day — with the risk in the sizing
formulas, not the tests.

**New tests by phase:** age-conditioned economic status and SAP2022 age
structure in every band (1); leap days, 12 holiday tables (2); 23 DST
transitions with correct local tariff hours, 23- and 25-hour balance (3);
census-2022 population **and dwelling-stock** checkpoint (4); no rate outside
its validity interval, Oct 2018 regime boundary (5); no NO_DATA in span (6);
every occupancy step a dated passport event, no refill without elapsed
duration, a child in an in-moving household (7); care-home deaths vacate no
dwelling (8); no data before completion date, Part V share, amenity ratios (9);
uptake matches national series per year, adoption exogenous (10); no interval
data before install date, era transitions dated, flexibility event counts (11);
every crisis date verified (12); policy-event dating (13); per-year SLP targets
(14); **year-boundary continuity, end-hash == next start-hash, `verify_chain` clean over 4,291 days, person-state restored (the I-081 guard extended), `sim_day` continuous** (15); coupled run writes no base package (16).

**Regression.** The existing suite is the harness: **1,108 tests, 1 failed /
1,072 passed / 35 skipped**. The failure is **I-101** (27 min vs 30; it fails on
the freeze-1 tree too, so it predates recent merges) and **must not be closed
by widening the margin — the margin is the claim.** Any new failure blocks its
phase.

---

## 6. Runtime, storage, and P's delivery model

### Measured, this machine, 2026-10-13/14

| | value | basis |
|---|---|---|
| town14, full town C2 | **103 s/day** (52.3 sim + 50.7 write) | 14 days, **includes writes** |
| probe, full town C2 | 101.2 s/day | 26 days, **sim only — no flush occurred** |
| probe peak RSS | 8,041 MB | `ps` |
| town14 peak RSS | 7,493 MB | engine `ru_maxrss` |
| bytes, D18 omitted | 15.76 MB/day | town14 |
| D18 | **27.1 kB per home-day** at 1-minute | estate-year, 506.4 MB / 18,250 home-days |

**Use 103 s/day.** `FLUSH_EVERY_DAYS = 30` and the probe stopped at day 26 with
`pkg/` holding **0 files**, so its rate excludes every write — exactly I-089's
critique.

### D2 answered: D18 fits

| enrolled by Sep 2026 | mean homes | D18 | total with 66 GB base | fits 110 GiB |
|---|---|---|---|---|
| 10% (109) | 55 | 3.2 GB | 69.2 GB | yes |
| 20% (218) | 109 | 6.4 GB | 72.4 GB | yes |
| 40% (437) | 218 | 12.7 GB | 78.7 GB | yes |
| 50% (546) | 273 | 15.9 GB | 81.9 GB | yes |
| 100% (1,092) | 546 | 31.8 GB | 97.8 GB | yes |

Linear ramp from zero over the 2,099-day window, 1-minute basis as an **upper
bound** — N specifies 15-minute interval plus device-level, which will be less
for the interval part. **No external volume and no split run needed**, at any
enrolment level. If enrolment exceeds 50% *and* device-level telemetry proves
heavier than the 1-minute estate basis, I will re-size and come back rather
than silently overrun. **D18 is never dropped** — it is scoped to enrolled homes
from their enrolment date, which is a modelling decision, not a storage one.

### Parallelism — the chain removes it

**P's chaining makes jobs=2 by year impossible, and that is the right trade.**

v1 and the earlier v2 draft relied on each year's start being a deterministic
function of (seed, year index), because `run_life_course` takes only t0 state
with **no simulation feedback** — the state was *recomputed*, not inherited.
A chained run inherits the **simulated** end state of the previous year, so
year *N+1* cannot begin until year *N* finishes. Serial by construction.

Cost of the decision: **5.12 days wall instead of ~2.56.** Bought with it:
genuine continuity of thermal mass, tanks, SOC, occupancy and life course
across eleven boundaries, and a verifiable hash chain end to end. For a replay
that claims to be real, I think that is worth 2.5 days.

**What can still overlap, in order of value:**

| candidate | overlap | note |
|---|---|---|
| **Export layer for year *N* while *N+1* simulates** | **yes, fully** | it reads year *N*'s finished package; measured 81 s and 130 s for the two export runs this session |
| **Year packaging, checksums, catalogue entry** | **yes, fully** | pure I/O over a finished year |
| **Monthly provisional drops** | **yes** | package month *M* while *M+1* simulates |
| **Within-year write flushing** | **maybe — must be measured, not assumed** | writes are ~49% of runtime (town14: 50.7 s write against 52.3 s sim), so the ceiling is large. But the 12 Oct finding was that the run is **I/O bound** — "write time overtook sim time, 119.4 s against 104.4 s per day" — so if the disk is already saturated, moving the flush to a background worker buys nothing. Measure before building |
| **Life course for the whole span** | **yes, once** | physics-independent, so precompute 2015–2026 in one pass |
| **Simulation of two years** | **no** | the chain forbids it |

Memory is unchanged by chaining: one process at ~7.5 GB `ru_maxrss`, well
inside 32 GB, and the jobs≥2 RSS problem disappears with the option.

### P: chained delivery

**Run order 2015 → 2026, serial. Only 2015 starts cold.**

| year | days | hours | release at |
|---|---|---|---|
| 2015 | 365 | 10.44 | 0.44 d |
| 2016 | 366 | 10.47 | 0.87 d |
| 2017 | 365 | 10.44 | 1.31 d |
| 2018 | 365 | 10.44 | 1.74 d |
| 2019 | 365 | 10.44 | 2.18 d |
| 2020 | 366 | 10.47 | 2.61 d |
| 2021 | 365 | 10.44 | 3.05 d |
| 2022 | 365 | 10.44 | 3.48 d |
| 2023 | 365 | 10.44 | 3.92 d |
| 2024 | 366 | 10.47 | 4.35 d |
| 2025 | 365 | 10.44 | 4.79 d |
| 2026 | 273 | 7.81 | **5.12 d** |

Plus the 2015 warm-up (below) and ~0.5 h of packaging per year, which overlaps
the next year's simulation. **Monthly provisional drops ~52 min each**, shipped
`provisional` and superseded by the year package.

**The 2015 cold start: a 31-day warm-up on December 2014 weather.** Both station
files reach back to 1962 and 1955, so the data is on disk — no acquisition.
Justification: the deepest carried state is building thermal mass, with a time
constant of order 1–5 days for heavy masonry (DHW tank and battery SOC are
~1 day), so 31 days is **more than six times the longest constant**. December
is also the right month to absorb a cold start rather than 1 January: the
indoor-outdoor gradient is near its annual maximum, so the initial-condition
error is both largest and fastest-decaying there. The warm-up is **discarded
burn-in** — its days are never packaged, never published, and carry no
`observed` label.

**Chain verifiability.** Each package records the checkpoint hash it started
from and the one it ended with. `CheckpointStore.verify_chain` already
"recomputes every link and reports the earliest day at which the recorded chain
diverges", and `checkpoint_chain_head` is already published in run diagnostics
— so the chain claim is checkable with machinery that exists.

**The merged multi-year view is built from the year packages, never a separate
run**, so it cannot disagree with them.

---

## 7. Live forward mode

**Nightly scheduled job. Never on page load.** No request path generates a day.

* **Scheduler:** one nightly job, last completed day → yesterday, in order.
* **Idempotency:** a day is complete **iff** its sentinel exists — the decade's
  own rule, per day. Complete days skipped; partial days renamed aside and
  redone, never resumed in place, because the writer numbers parts from zero.
* **Provisional flags:** inputs arrive at different lags (weather next day,
  prices next day, CSO quarterly, census every six years). A day with
  incomplete inputs ships `provisional` with the lagging source **named**, and
  is later **superseded by a new version** rather than mutated — which is what
  D02's unused `version` field is for.
* **No silent fallback:** a day missing a required input is **not generated**;
  it is reported blocked, naming the source.
* **Hosting:** ~103 s and ~16 MB per day, so a night's work is minutes on the
  existing workstation; ~5.8 GB/year without D18. Needs a scheduler, a writable
  sources tree and a monitored failure path. r4 §772 already anticipates this —
  "one multi-core workstation or edge server; no cluster is needed for v1".

---

## 8. Open decisions

v1's D1–D10 are settled and recorded. New:

| # | decision | recommendation |
|---|---|---|
| **D11** | **`sim_day` continuity across the chain** (Phase 15). The `SeedTree` is keyed on (seed, entity, `sim_day`); a year restarting at 0 would re-draw 2015's numbers. | **Run `sim_day` continuously 0 → 4,290.** The alternative — adding the year to the seed entity — would make every year's draws differ from the equivalent day in a single-pass run, which defeats the point of a chain. This needs confirming before Phase 15, because it touches every stream. |
| **D17** | **Whether to overlap within-year write flushing** (§6). Writes are ~49% of runtime, but the run was measured **I/O bound** on 12 Oct, so the gain may be zero. | **Measure first, build second.** One instrumented month with the flush on a background worker, compared against the same month inline. Do not build it on the strength of the 49% figure alone. |
| **D12** | **Enrolment curve for PARA//EL/EdgeWare** (N era 3). Shape and end point drive both D18 volume and flexibility event counts. | A **sourced ramp** if any enrolment data exists; otherwise an A-numbered curve reaching a stated share by Sep 2026. I need the target share from you — it is a programme fact, not a modelling choice. |
| **D13** | **Part V for Belgard: 10% or 20%?** It turns on the land-purchase date under the Affordable Housing Act 2021, which I cannot source from anything on disk. | Supply the land-purchase date, or authorise an A-numbered assumption with the search recorded. |
| **D14** | **Setpoint persistence after the energy crisis** (O, 2023–24). | **Model persistence only if the evidence supports it.** If the SEAI/CSO/ESRI studies are equivocal, no persistence, and say so. |
| **D15** | **Cluain Ard and Belgard dwelling counts and mix** are unknown to me — only "Part V 10%" and "nZEB A-rated" are given. | Supply counts, dwelling-type mix and Part V unit counts, or authorise A-numbered assumptions. |
| **D16** | **Phase 16 depends on the LEC and FLEXUS builds**, neither in this repo. | Confirm their readiness dates, or Phase 16 stays unscheduled. |

---

## 9. Reporting

Per phase, one report: **a summary table** (entry gate, work, deliverables,
tests added/passing/failing, exit verdict, days spent vs estimate); **measured
numbers with their basis**, every runtime and RSS figure stated with the machine
state beside it — the standing lesson of I-089 and the four-arm probe, that **no
cost figure means anything without the machine state beside it**; **decisions
needed**, each with a recommendation and what is blocked; **new issues** from
**I-108** onward; **the freeze record** (tag, digests, root rebuild, drivers
reissued). I stop at every gate and wait.

---

## 10. Issues

| issue | consequence |
|---|---|
| **I-090** | **Closes.** One freeze, one replay; `wp5_decade` and its D03/D09/D20 residual disappear. Scope K's per-day digest stamp closes the **class**. |
| **I-100** | Already closed this session; the per-phase freeze cycle keeps it closed. |
| **I-088** | **Closes in Phase 2** — an interface limit, not missing data. |
| **I-069** | **Closes in Phase 1**; gates all population and venue work. |
| **I-105** *(new, logged Phase 0)* | DST/tariff-band mismatch: UTC 1440-minute grid vs `BAND_CLOCK` local clock. **A live defect today.** Closes in Phase 3. |
| **I-106** *(new, logged Phase 0)* | Age-structure deficit vs SAP2022: 65+ −29%, 75–84 −48%, 85+ −71%, worsening with age. Closes in Phase 1. **Blocks D3's arithmetic.** |
| **I-107** *(new, logged Phase 0)* | The BNIT 3D map holds dwelling positions while D01 is `POINT EMPTY`. A future alignment project should export map positions keyed to D01 IDs. Not scheduled. |
| **I-103** | `RELOCATED_TO_RUN` points at `wp5_decade`, which **ceases to exist**. Revisit in Phase 9. |
| **I-104** | Already fixed this session. |
| **I-101** | Unaffected, open, predates the freeze. **Not to be closed by widening the margin.** |
| **I-094 / A-97** | **Closes in Phase 5** — vintaging is the fix. |
| **I-089** | Honoured rather than closed: 103 s/day is the flush-inclusive figure. |
| **E2-7** | **Closes in Phase 6.** |
| **FX-BN-05 / T-OBS** | **FLEXUS obligations, not Baile Nua's**, per your quotes. FX-BN-05 requires one town-year in under 24 h wall — the replay measures **10.44 h/year**, inside it. T-OBS requires ingesting 10 years of OBS faster than real time — the replay **supplies 11.75 years**. The FLEXUS spec is to be updated to "the 2015–2026 replay" separately, by you. |

---

## 11. Backlog — needed before live mode reaches 2027

| item | effort | flag |
|---|---|---|
| **Abbeylands construction-site loads** — builder's supply, site cabins, crane | 6–8 d | **needed before live mode reaches 2027.** Venues draw **no electrical load** today; this is a new non-domestic load class |
| **LEC connection application and MV reinforcement** | 8–10 d | **needed before live mode reaches 2027.** MV is a slack `ext_grid` by explicit design decision (`lv.py:254`) — there is no MV network to reinforce |
| **Map/geometry alignment (I-107)** | 10+ d | not scheduled; reverses a deliberate policy |
| **Transport, modes, CMATS, mode shift** | 15–20 d | **BNIT**, per R02 |

---

## Awaiting approval

No code written or changed. Phase 1 starts when you say go.
