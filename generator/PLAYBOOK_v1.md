# PLAYBOOK v1 — the Baile Nua historical replay

**Status: DRAFT FOR APPROVAL. No code has been written or changed for this plan.**
**Nothing starts until the user approves this document and says go.**

> **UNVALIDATED SIMULATION EVIDENCE.** This is a process document. Every
> quantity in it is either measured on this machine during the 2026-10-13/14
> session and labelled as such, read from a file in this repository and cited,
> or flagged as unverified. Nothing here is an estimate presented as a fact.

Replaces: the 2022–2031 synthetic decade.
With: a real-data historical replay of **1 Jan 2015 → 30 Sep 2026** (**4,291
days**, containing **3 leap days**: 2016, 2020, 2024), then a nightly live
forward mode.

Baseline at the time of writing: branch `hrsd-v1-freeze2-finish`, 8 commits,
**nothing pushed**; tag `v1-engine-freeze-2.1`; code digest `b8252f59…`, conf
digest `e0ab1c83…`; suite 1,108 tests, 1 known failure (I-101); snapshot
`snapshots/v1-freeze2-2026-10-13` (1.4 GB).

---

## 1. Goal and non-goals

### Goal

One town, Baile Nua in Co. Cork, simulated day by day across 2015–2026 from the
real weather, real prices, real calendar and real demography of each of those
days — so that any pattern in the output is attributable to something that
actually happened, and so the 2022 census becomes a **test** of the model
rather than its input.

### Non-goals

* **Not a scenario engine.** One trajectory, the official one.
* **Not a detector.** Design r4 §248: "Baile Nua does not detect anything
  itself."
* **Not validated.** Every artefact keeps the UNVALIDATED label until a
  validation gate says otherwise, and §12 of this playbook does not claim one.
* **No transport model.** See the boundary below.

### The Baile Nua / BNIT boundary, applied

The project has already decided this pattern twice and I am applying it rather
than inventing one. **R02**: "Baile Nua is a base model… Scenarios and
interventions run in BNIT." **U06** (sensor mix): "(a) in the base town; BNIT
can re-tier." **U10** (tariffs): "(a) for existing retail tariffs; dynamic and
flex signals stay in BNIT", with the note that putting them all in BNIT
"leaves base behaviour unrealistic".

The principle: **what happened, or is officially committed, is Baile Nua; what
is counterfactual is BNIT.**

| scope item | Baile Nua | BNIT | why |
|---|---|---|---|
| A replay 2015–2026 | **yes** | — | it happened |
| A live forward mode | **yes** | — | it is happening |
| B I-069 fix | **yes** | — | a defect |
| C real inputs vintaged | **yes** | — | they happened |
| D COVID restrictions, WFH, mortality | **yes** | — | it happened; see §8 for the mortality caveat |
| E life course and housing chain | **yes** | — | base demography |
| F Cluain Ard 2019, Belgard 2024 | **yes** | — | completed; a replay omitting them is wrong |
| F Abbeylands to 2027 | **yes, labelled projection after today** | — | committed development |
| F one official growth trajectory | **yes, labelled projection** | — | CSO/ESRI + Cork CDP are official |
| F amenities by statutory ratio | **yes** | — | rules, not choices; the venue layer already works this way |
| F alternative trajectories | — | **BNIT** | scenarios, per R02 |
| **F/I transport, modes, CMATS, mode shift** | — | **BNIT** | mode shift is an intervention; 15–20 d and larger than the whole growth pipeline |
| G upgrades by national uptake | **yes** | — | it happened |
| H policy and market events | **yes** | — | they happened |
| I behaviour: holidays, Christmas, hybrid days, migration | **yes** | — | base behaviour |
| J observable-layer data flaws | **yes** | — | design r4 §551 already requires provenance and quality flags |
| K engine generalisation | **yes** | — | infrastructure |
| L validation targets | **yes** | — | but see the CER/ISSDA blocker, §8 |

---

## 2. Phases

Dependency order: **I-069 first → engine generalisation → data → behaviour →
validation gates → the long run.** No phase starts before its predecessor's
exit gate passes. Every phase ends with a freeze cycle (§4).

Effort is working days for one person. Totals exclude runtime.

### Phase 0 — Baseline and decisions (2 d)

* **Entry:** this playbook approved.
* **Work:** resolve the §8 open decisions; confirm the source list; record the
  starting digests; confirm the 2022–2031 decade is retired and its artefacts
  archived, not deleted.
* **Deliverables:** `DECISIONS.md` entries for each §8 item; a source
  acquisition manifest.
* **Tests:** none (no code).
* **Exit gate G0:** every §8 decision answered; every source in §3 either
  acquired with a licence and a manifest, or explicitly dropped with a written
  reason. **No source is assumed to be obtainable.**

### Phase 1 — I-069 (3 d)

* **Entry:** G0.
* **Work:** `population/synthesise.py` draws economic status from the area
  marginal **with no age conditioning**, which gives the town 241 "students"
  with a **median age of 45**. Condition the draw on age.
* **Deliverables:** an age-conditioned economic-status draw; I-069 closed.
* **Tests:** a new test asserting no person under the school-leaving age or
  over ~24 holds `econ_status="student"` without a conditioning reason; the
  existing week-3 venue criterion re-run.
* **Exit gate G1:** the **8,426 venue-presence rows with no venue id (7.3% of
  114,951)** fall to a declared residual, and the week-3 venue criterion stops
  failing for this cause. The Census puts 19–24 students at **9.92% of the 15+
  population against the town's 1.63%**, so expect that gap to move too.
* **Why first:** `population/venues.py` argues it in its own docstring — a
  college venue type "would make the symptom go away by building a venue to
  serve a population bug". **No feature work on population or venues until
  G1 passes.**

### Phase 2 — Time axis (6 d)

* **Entry:** G1.
* **Work:**
  * `build_realisation(year)` → a date range. **I-088 closed.** The data is
    already real observed Met Éireann for whatever year is asked, and both
    station files are on disk covering **1962-01-01 / 1955-12-01 → 2026-10-01**
    — so this is an interface change, not an acquisition.
  * `build_calendar` currently **raises `NotImplementedError` for any year but
    2022**. Generalise to a date range; add per-year holiday and school-term
    tables (§3).
  * Arbitrary start date; 4,291-day span; `DAYS_PER_YEAR` retired as a
    concept; checkpoint chain, writer part numbering and `FLUSH_EVERY_DAYS`
    reviewed for year assumptions.
* **Deliverables:** a run that starts on any date and spans any length.
* **Tests:** a 2015 full year completes; **29 Feb present in 2016, 2020, 2024**;
  each year's holiday table verified against an independent source; the 2022
  table still reproduces its 10 entries including the **18 Mar 2022 one-off**
  and still excludes **St Brigid's Day, which begins in 2023**.
* **Exit gate G2:** a 2016 run of 366 days closes its energy balance; holidays
  match for all 12 years.

### Phase 3 — DST and clocks (5 d)

* **Entry:** G2.
* **Work:** UTC simulation, **local-clock schedules**, local-time exports.
  `MINUTES_PER_DAY = 1440` backs every per-minute array and
  `stream_writer.py:195` builds a UTC 1440-minute index, while
  `export/tariffs.py:344` declares `BAND_CLOCK = "Europe/Dublin local clock, as
  the published price schedule states it"`.
* **Deliverables:** schedules that hold their local wall-clock meaning across
  a transition; exports carrying local time alongside UTC.
* **Tests:** tariff bands land on the correct local hour across **all 23
  transitions in span**; a 23-hour and a 25-hour day both close energy balance.
* **Exit gate G3:** both transition days balance; no schedule drifts by an hour
  seasonally.
* **Note:** this is **a live defect today**, not one the replay creates — day
  and night tariff bands are already an hour out for half of every simulated
  year, including the 2022 estate-year. It is **not yet in ISSUES.md** and I
  will log it in Phase 0 regardless of whether this plan proceeds.

### Phase 4 — Population base and the census checkpoint (5 d)

* **Entry:** G3.
* **Work:** t0 is currently **1 Jan 2022, Census 2022** (`synthesise.py:44`),
  and the only small-area source on disk is `sap2022`. Acquire **Census 2016
  SAPS** (or 2011) for the Cobh small areas; parameterise the census vintage;
  age the base forward to 1 Jan 2015.
* **Deliverables:** a 2015 starting state derived from a pre-2022 census.
* **Tests:** the aged base reproduces its own census marginals at the census
  date.
* **Exit gate G4 — the prize:** **the Census 2022 checkpoint.** Run 2015 → 2022
  and compare the simulated 2022 state against the actual SAP2022 marginals
  within declared tolerances. Today the census **is** the base, so it can never
  be a test; after this phase it is a seven-year out-of-sample demographic
  back-test the project has never been able to perform.
* **Risk:** every downstream marginal — ethnicity, economic status, household
  composition — is keyed to 2022 table shapes.

### Phase 5 — Vintaged rates and two price regimes (7 d)

* **Entry:** G4.
* **Work:** `SourcedValue` (`export/tariffs.py:191`) has **no validity field**
  and uses `__slots__`; vintage exists only as a free-text
  `rate_schedule_vintage` string. Add a validity interval and a date-keyed
  resolver. Add the **SEM SMP → I-SEM** regime switch at Oct 2018.
* **Deliverables:** every rate resolved by simulated date; two price regimes.
* **Tests:** the existing `test_d27_every_sourced_rate_is_in_its_cited_document`
  must keep passing — it greps the cited document's **bytes** for the exact
  quote, so **every vintage needs its own citable document on disk**. That, not
  the code, is the cost of this phase.
* **Exit gate G5:** no rate resolves outside its validity interval; every
  vintage cites a document present in `sources/`.

### Phase 6 — Market and system data (5 d)

* **Entry:** G5. **Blocked on acquisition (G0).**
* **Work:** SEM SMP, I-SEM DA/BM, EirGrid demand and carbon; build D31's
  market series.
* **Deliverables:** D31 wholesale price and carbon intensity.
* **Tests:** regime boundary continuity; no NO_DATA in span.
* **Exit gate G6:** **E2-7 passes for the first time.** Today
  `observation/nonsensor.py:40` records D31's market series as "**What is NOT
  built, and E2-7 fails on it**", with
  `series_not_built = ("wholesale_price", "carbon_intensity", …)`.

### Phase 7 — Life course and housing chain (8 d)

* **Entry:** G4 (independent of 5–6).
* **Work:** what exists and what is added:
  * **Exists:** vacancy creation on last-occupant loss
    (`tenyear.py:893-905`, emits `household_dissolved`); the vacant-load
    profile `VACANT_FROST_SETPOINT_C = 7.0` (`run.py:151`, frost protection,
    standing load retained, declared `[A]` because DEAP has no vacancy case);
    refill governed by **VAC04's Cork County 5–6% rate and VAC17's gross
    flows**, which are registered and on disk for exactly this purpose;
    `separation`; births with `vsa36`/`vsa104` by mother's age.
  * **Add:** sourced **probate/sale/letting duration** — today vacancy is
    year-granular (`vacant_since_year` is an integer year index) and a dwelling
    can empty and refill with no elapsed time at all; **movers-based household
    composition** — today it is `size = integers(1,5)`, `age = integers(20,70)`,
    50/50 sex, every member `role="adult"`, `econ_status="at work"`, so **no
    child has ever moved into a Baile Nua dwelling**, despite the SAP2022
    movers table being on disk; **optional pre-occupancy renovation** with a
    SEAI grant measure mix; **occupancy steps as dated passport events** — the
    passport map (`tenyear.py:305-337`) covers only six building-change types,
    so **no step of the occupancy chain is a D03 event today**;
    **tenancy/meter change as a structural break** with a tenure transition;
    **individual emigration** (today folded into whole-household `move_out`
    under `[A] A-25b`, "EP006 publishes NET migration only").
* **Deliverables:** the full death→reoccupation chain, dated and passported.
* **Tests:** every chain step emits a dated passport event; no dwelling refills
  without an elapsed duration; movers composition matches SAP2022 within
  tolerance; a child appears in at least one in-moving household.
* **Exit gate G7:** chain complete and sourced; **movers composition first**,
  as the cheapest fix with data already present.

### Phase 8 — Institutional population and COVID (10 d)

* **Entry:** G7.
* **Work:** an institutional (care-home) population, then the COVID layer:
  restriction levels by date, school closures, time-varying WFH, age-banded
  excess mortality before vaccination, vaccine rollout by age band, care-home
  deaths handled separately.
* **Why together:** they are the same gap from two directions. There is **no
  institutional population anywhere** today — every "institution" hit in the
  package is a third-level education venue — so **every modelled death vacates
  a dwelling**, and care-home deaths cannot be separated because there are no
  care homes. §8 of this playbook carries the honesty requirement.
* **Tests:** the national rate reproduces CSO weekly excess deaths; care-home
  deaths vacate no dwelling; the town count is reported as a draw with its
  interval.
* **Exit gate G8:** the presentation rule in §8 is implemented in the artefact,
  not just in prose.

### Phase 9 — Town growth and amenities (8 d)

* **Entry:** G1 **and** G7.
* **Work:** exercise D01/D02's **existing but never-used** validity intervals
  (`valid_to` is populated on **0 of 1,092** dwellings; `version` is 1 on all
  of them); Cluain Ard 2019; Belgard 2024 nZEB A-rated (190 A-rated dwellings
  already exist, so the archetype is available); Abbeylands phased to 2027;
  Part V tenure (D02 already has `rented social`, 116 present); first occupants
  from CSO new-dwelling data; amenity rules by statutory ratio, extending the
  venue layer's existing derived-count-plus-sourced-capacity pattern; network
  growth (`_trafo_type` already auto-sizes).
* **Deliverables:** a dated growth pipeline; amenities triggered by sourced
  ratios.
* **Tests:** no dwelling produces data before its completion date; Part V share
  matches the sourced rule; amenity counts follow the cited ratio.
* **Exit gate G9:** +300 dwellings (**+27.5%**) lands with ~15 transformers,
  ~18 feeders and ~615 buses added at the town's current ratios, and D17 rows
  scale as **96 epochs × (transformers + feeders)** — a rule that reproduces
  the measured 157,248 rows exactly.
* **Excluded here:** Abbeylands' **construction-site loads** (builder's supply,
  cabins, crane) and **LEC/MV reinforcement**. Venues draw **no electrical
  load** — they are activity destinations only — and the MV side is a slack
  `ext_grid` by explicit design decision (`lv.py:254`: "this models the LV
  network, not the MV one, and pretending to know the MV source impedance
  would be a declared assumption"). Both are **new subsystems, 14–18 d
  combined**, and are a separate proposal (§8).

### Phase 10 — Upgrades, policy events, behaviour, data flaws (9 d)

* **Entry:** G5, G9.
* **Work:** year-varying retrofit/heat-pump/PV/EV uptake as dated passport
  events (the mechanism exists — `retrofit_fabric`, `retrofit_heat_pump` and
  three DER events keyed to HEBEU37 — only the **rates** are time-invariant);
  smart-meter rollout 2019–24 with interval data only after install date;
  electricity credits 2022–24; MSS export payments from Dec 2022; smoky coal
  ban Oct 2022; supplier switching; holidays abroad, Christmas returns, hybrid
  days by sector, 2022 temporary-protection arrivals; observable-layer flaws
  tied to real events.
* **Tests:** no home has interval data before its install date; each policy
  event has a dated effect and a cited source.
* **Exit gate G10:** every dated event cites a source or carries an A-number.

### Phase 11 — Validation (5 d)

* **Entry:** G6, G8, G10.
* **Work:** named targets and tolerances against **ESB Networks Standard Load
  Profiles** (on disk: `esbn_rmds/load-profiles-indexes-2022.xlsx`, published
  without registration), EirGrid demand shape, CSO counts.
* **Exit gate G11:** every target either passes, or fails and is reported as a
  failure. **No tolerance is widened to manufacture a pass.**
* **Blocked:** CER/ISSDA — see §8.

### Phase 12 — Production run (2 d + runtime)

* **Entry:** G11.
* **Exit gate G12:** 4,291 days complete, invariants clean, storage resolved.

**Total: 75 working days** plus runtime (§6). Phases 1–4 alone (19 d) deliver a
real-weather, census-back-tested replay; everything after is fidelity.

---

## 3. Data acquisition plan

Storage: `sources/<family>/<file>`, with a sidecar `*.manifest.json` carrying
bytes and SHA-256, registered in `sources_registry.py` with URL, licence,
title, intended use and model-development exposure. `baile_nua.sources.require`
**re-hashes a file on every use and refuses it if the bytes have changed** —
that mechanism already exists and is the provenance record.

**When a source is missing: the run REFUSES.** No silent fallback, no
substitution, no interpolation across an absent source. The failure names the
key and the expected path. Precedent: `require` already raises
`SourceError: source 'x' is registered but missing from disk`, and
`RunContext.open` refuses a run whose diagnostics are absent rather than
guessing a seed.

| input | on disk | coverage | cadence | licence |
|---|---|---|---|---|
| Met Éireann `hly3904` Cork Airport | **yes** | 1962-01-01 → 2026-10-01 | hourly | CC-BY |
| Met Éireann `hly1075` Roches Point | **yes** | 1955-12-01 → 2026-10-01 | hourly | CC-BY |
| Solar irradiance | **derived, no source needed** | — | — | n/a |
| ESB Networks Standard Load Profiles | **yes** | 2022 | quarter-hourly | published, no registration |
| CSO `vsa08` deaths by age/sex | **yes** | annual | annual | CC-BY |
| CSO `vsa36`/`vsa104` births, fertility | **yes** | annual | annual | CC-BY |
| CSO `ep006` net migration | **yes** | annual, county | annual | CC-BY |
| CSO `pea01` population estimates | **yes** | annual | annual | CC-BY |
| CSO `HEBEU37` installations | **yes** | annual | annual | CC-BY |
| CSO `VAC04`/`VAC17`/`F2095` vacancy | **yes** | quarterly | quarterly | CC-BY |
| SEAI BER research tool | **yes** | year-stamped | rolling | SEAI terms |
| CSO `SAP2022` movers | **yes** | 2022 | census | CC-BY |
| **CSO weekly deaths** | **no** | — | weekly | CC-BY |
| **Census 2016/2011 SAPS** | **no** | — | census | CC-BY |
| **SEM SMP → Sep 2018** | **no** | — | half-hourly | to confirm |
| **I-SEM DA/BM from Oct 2018** | **no** | — | half-hourly | to confirm |
| **EirGrid demand + carbon** | **no** | — | 15-min | to confirm |
| **COVID restriction levels** | **no** | — | event | gov.ie |
| **School closures** | **no** | — | event | gov.ie |
| **Vaccination by age band** | **no** | — | daily | HSE/HPSC |
| **CSO WFH series** | **no** (static marginal only) | — | quarterly | CC-BY |
| **Google mobility** | **no** | **Feb 2020 → Oct 2022 only, then retired** | daily | CC-BY |
| **SEAI grant statistics by year** | **no** | — | annual | SEAI |
| **EV registrations (CSO/SIMI)** | **no** | — | monthly | CC-BY / SIMI terms |
| **Retail tariffs by year** | **partial** — 2022 and 2024 points | — | per change | CRU |
| **Holidays 2015–2026** | **no** — 2022 only | — | annual | python-holidays or tables |
| **School terms 2015–2026** | **no** — 2022 only | — | annual | DoE circulars |
| **CSO/ESRI projections, Cork CDP targets** | **no** | — | periodic | CC-BY / council |
| **Storm warnings register** | **no** (storms derived from wind) | — | event | Met Éireann |

Storms need no acquisition to **appear**: they are derived from the observed
wind (`storm_days_from_weather`, guarded by
`test_storms_come_from_the_weather_and_not_from_a_draw`), and **Ophelia (Oct
2017), Emma (Mar 2018) and Éowyn (Jan 2025) are all inside the station data**.
What a register would add is the red-warning *status*, not the event.

GAA finals and televised fixtures: **no open-data source exists.** The `sport`
event kind already carries `source_key=None` and assumption flag **A-43** —
"'sport' matches 115 tables, none of them a fixture list or an attendance
series — the matches are road freight TRANSPORT". Dates will be tabled as
**declared A-numbered assumptions** with the search that failed recorded, which
is the project's existing convention.

---

## 4. Rules

1. **Every value is sourced or declared.** A number with no source gets an
   A-number, the search that failed to find one, and what it would take to
   source it. This is the existing convention and it does not relax.
2. **No fabricated data.** Specifically: no synthetic geometry presented as
   surveyed (`export/structural.py` already refuses "a fabricated polygon that
   would read as surveyed geometry"); no interpolation across a missing source;
   no national figure applied to the town without the scaling stated.
3. **Observed vs projection labelled on every row.** A new temporal axis:
   every row carries whether its inputs were observed or projected. Today the
   package has a blanket UNVALIDATED label and strong `[A]` flags, but **no
   observed/projected distinction**. Cut-over is the run date; everything after
   is projection.
4. **Freeze cycle per phase.** Each phase ends: new tag, digests recomputed,
   `_frozen_root` rebuilt from the tag, worker and aggregator reissued as **new
   files** (never editing a mode-500 original — I-080), drivers' digests
   verified against the tag. Budget 0.5 d per phase, included above.
5. **Nothing pushed. `code/` and the repo stay local.** No tag or release
   reaches a remote.
6. **Stop and ask on anything not covered here.** Including: any threshold
   change, any tolerance, any source substitution, any decision in §8.
7. **No gate is passed by widening it.** Standing project rule; restated
   because a replay has many tolerances.
8. **Nothing is deleted.** Superseded artefacts are renamed aside, as the
   decade's own drivers do.

---

## 5. Test strategy

**Assumptions to remove.** Measured, not guessed: `365` appears in the test
suite exactly **4 times across 3 files** (`test_release_policy.py`,
`test_export_d21_d23_d27.py`, `test_e1_report.py`), plus an `or 365` default in
`plausibility/checks.py:902` and the `365 * n_years` sizing formulas in
`release/policy.py`. `DAYS_PER_YEAR` is a driver constant.
`tariffs.py:179` explicitly notes "2022 is not a leap year" and standing
charges are 365-day figures. **This is a small, well-bounded job — under a
day — and the risk is in the sizing formulas, not the tests.**

**New tests per phase** are listed in §2. Across phases:

* leap day present and balanced, 2016/2020/2024;
* all 23 DST transitions, tariff bands on the correct local hour;
* holiday tables for all 12 years, including the 2022 one-off and St Brigid's
  from 2023;
* price-regime boundary at Oct 2018;
* the Census 2022 checkpoint;
* smart-meter install date gating interval data;
* every occupancy-chain step emitting a dated passport event;
* care-home deaths vacating no dwelling;
* observed/projected label present on every row.

**Regression on existing datasets.** The existing suite is the regression
harness: 1,108 tests, currently **1 failed / 1,072 passed / 35 skipped**. The
single failure is **I-101** (a non-worker wakes 27 minutes later than a worker
where the test needs 30; it fails on the freeze-1 tree too, so it predates
every recent merge) and **must not be closed by widening the margin — the
margin is the claim.** Any new failure is a regression and blocks its phase.

---

## 6. Runtime plan

**Measured on this machine, 2026-10-13/14:**

| measurement | value | basis |
|---|---|---|
| Probe, full town C2 with D10/D17 | **101.2 s/day** overall, 96.3 s/day over the last 5 | 26 days, **sim only — no flush occurred** |
| town14, full town C2 | **103 s/day** (52.3 sim + 50.7 write) | 14 days, **includes writes** |
| Probe peak RSS at stop | 8,041 MB | `ps` basis |
| town14 peak RSS | 7,493 MB | engine `ru_maxrss` |
| Bytes, D18 omitted | 15.76 MB/day | town14 measured |

**The honest planning figure is town14's ~103 s/day, not the probe's 101.2.**
`FLUSH_EVERY_DAYS = 30` and the probe stopped at day 26 with `pkg/` holding
**0 files** — so its rate excludes every write. That is precisely **I-089**:
"the scale basis structurally omits writer-flush cost".

| | at 103 s/day |
|---|---|
| 4,291 days, serial | **123 h ≈ 5.1 days** |
| If loaded as on 12 Oct (254 s/day) | 303 h ≈ 12.6 days |
| Checkpoint files at 2/day | **8,582** |
| Disk, D18 omitted | **66 GB** |
| Disk, D18 included | **~213 GB against 110 GiB free** |

**D18 must be omitted, or the run split. This is a decision, not a detail.**

**Parallelism: yes, and the mechanism already exists.** `run_life_course` takes
only t0 persons, dwellings and households — **no simulation feedback** — so each
year's starting state is a deterministic function of (seed, year index), which
is exactly how the decade parallelises. Population carry-over is therefore not
an obstacle: it is *recomputed*, not inherited.

Two limits: the scheduler **refuses more than 3 jobs**, and 3 × ~7.5 GB exceeds
32 GB, so **jobs=2 (~2.6 days wall)** is the realistic ceiling. The 12 Oct
decision to run jobs=1 was taken on measurement — "write time overtook sim time
(119.4 s against 104.4 s per day), so the run is I/O bound" and "the OOM killer
had already taken a process at concurrency 1".

**The one thing that would break parallelism:** making upgrade adoption depend
on simulated bills or energy. **Keep adoption exogenous**, driven by national
uptake, and the run stays parallelisable.

Checkpoint cadence: 2 files/day as today, with a chain head per day and each
day **stamped with the code digest** it ran under (scope K) — which also closes
the I-090 class of problem permanently.

---

## 7. Live forward mode

**Trigger: a nightly scheduled job. Never on page load.** Explicitly: no
request path generates a day.

* **Scheduler:** one nightly job, generating every day from the last completed
  day to yesterday. A missed night is caught up by the next run, in order, one
  day at a time.
* **Idempotency:** a day is complete **iff** its completion sentinel exists —
  the decade's own rule ("a year is complete if and only if
  `_COMPLETE.json` exists"), applied per day. A day already complete is
  skipped. A partial day is renamed aside and redone, never resumed in place,
  because the writer numbers parts from zero.
* **Provisional flags for lagging inputs:** real inputs arrive late at
  different cadences — weather next day, prices next day, CSO quarterly,
  census every six years. A day whose inputs are incomplete is written with
  its rows flagged **provisional** and the specific lagging source named; a
  later run **supersedes** it with a new version rather than mutating it. This
  is what D02's unused `version` field is for.
* **No silent fallback:** a day whose required input is absent is **not
  generated**. It is reported as blocked, naming the source.
* **Hosting:** the measured per-day cost is ~103 s and ~16 MB, so one night's
  work is minutes on the existing workstation. No cluster. Growth is ~5.8
  GB/year with D18 omitted. Needs: a scheduler, a writable sources tree, and a
  monitored failure path. Design r4 §772 already anticipates this shape —
  "one multi-core workstation or edge server; no cluster is needed for v1".

---

## 8. Risks and open decisions

Each has my recommendation. **I will not proceed on any of these without an
answer.**

| # | decision | recommendation |
|---|---|---|
| D1 | **CER/ISSDA for validation (scope L) conflicts with a standing rule.** `sources/SOURCES.md:25`: "CER/ISSDA and any licensed or restricted source is NOT used", and it is listed as deliberately not used because "**The brief forbids it**". | **Do not use it.** Validate against ESB Networks Standard Load Profiles (on disk), EirGrid demand shape and CSO counts. If CER is genuinely wanted, the brief must change first, in writing, and the licence obtained — that is your call, not a technical one. |
| D2 | **D18 at town scale over 4,291 days needs ~213 GB against 110 GiB free.** | **Omit D18**, as the decade did (69% of bytes), and record the omission. Alternatively split the run by period. |
| D3 | **COVID mortality is unobservable at this scale.** Town age structure at 2020-04-01: 65+ = 241, 75+ = 60, **85+ = 7**. Two independent methods both give **≈1 expected death** (Poisson 95% interval 0–3). | Model the restriction **behaviour** (activity, WFH, closures) and **decline to model the deaths as a town-level result**. Report the calibrated national age-specific rate as the sourced input, person-years of exposure, the town count as an explicitly labelled Poisson draw with its interval, and state that care-home mortality — the majority of Irish first-wave deaths — is excluded. **My IFR, seroprevalence and national-death figures are from my own knowledge and are not verified against anything on disk; they must be fetched and cited before being written down.** |
| D4 | **Abbeylands' construction-site loads and LEC/MV reinforcement are new subsystems (14–18 d).** Venues draw no electrical load; MV is a slack bus by explicit design decision. | **Separate proposal.** Deliver Abbeylands as dated handovers first (Phase 9); treat the live construction site as its own project. |
| D5 | **The town has no geometry at all** — all 206 D01 features are `POINT EMPTY`, zero parcels, zero streets. So "~8–10 ha", "15% open space" and a reserved-space map cannot be represented. | **Keep the site abstract** — a count and a handover date, which the validity intervals already support. Real geometry is 10+ d and reverses a deliberate policy. |
| D6 | **Transport (scope I/F) is 15–20 d and larger than the whole growth pipeline.** Zero hits for CMATS, mode share, bus, rail, cycle or traffic; D12 trips are discarded same-day. | **BNIT**, per R02 — mode shift is an intervention. |
| D7 | **Census base for 1 Jan 2015.** No 2011/2016 SAPS on disk. | **Acquire Census 2016 SAPS** and age forward. Back-projecting the 2022 base is demographically backwards. If 2016 is unobtainable, start the replay at the 2016 census and lose one year. |
| D8 | **`FX-BN-05` and `T-OBS` are nowhere in this repository** — exhaustive search returns nothing; FLEXUS appears only as the R02 boundary. | **Supply the external spec**, or confirm no obligation exists. At 11.75 years the span *exceeds* ten, so a ten-year-window requirement is satisfied rather than broken. |
| D9 | **Per-year ESB Standard Load Profiles.** Only 2022 is on disk, but the replay spans 12 years. | Acquire per-year SLPs for validation, or validate only against 2022 and declare the limitation. |
| D10 | **The DST/tariff-band mismatch is a live defect today.** | **Log it in Phase 0** regardless of this plan's fate, and fix it in Phase 3. |

---

## 9. Progress reporting

Per phase, one report containing:

1. **A summary table:** entry gate, work done, deliverables, tests
   added/passing/failing, exit gate verdict, days spent vs estimate.
2. **Measured numbers with their basis** — every runtime, byte count and RSS
   figure stated with how it was measured and under what machine load. The
   standing lesson from I-089 and the four-arm probe: **no cost figure means
   anything without the machine state beside it.**
3. **Decisions needed from you**, each with a recommendation and what is blocked
   until it is answered.
4. **New issues** logged with I-numbers, continuing from **I-105**.
5. **The freeze record:** new tag, code and conf digests, frozen-root rebuild
   confirmed, drivers reissued.

I stop at every exit gate and wait, rather than rolling into the next phase.

---

## 10. Consequences for open issues

| issue | consequence |
|---|---|
| **I-090** (neither run's code state recoverable) | **Closes completely.** One freeze, one replay, every dataset regenerated; the `wp5_decade` run disappears and D03/D09/D20 — its last residual — come back under the new tag. Scope K's **per-day code-digest stamp** closes the class permanently, not just the instance. |
| **I-100** (frozen root pinned to the old freeze) | **Already closed** in this session: root rebuilt from `v1-engine-freeze-2.1`, digests verified, worker and aggregator reissued. The playbook's per-phase freeze cycle keeps it closed. |
| **I-088** (decade reuses 2022 weather and calendar) | **Closes in Phase 2.** Per-period real weather; it was an interface limit, not missing data. |
| **I-069** (economic status unconditioned on age) | **Closes in Phase 1**, and gates everything touching population or venues. |
| **I-103** (I-091 relocation is a manual move) | The `RELOCATED_TO_RUN` entries point at `wp5_decade`, which **ceases to exist**. Must be revisited in Phase 9, not left dangling. |
| **I-104** (catalogue's two scans disagree) | **Already fixed** in this session; the per-run scan is now used for facts as well as status. |
| **I-101** (sleep timing, 27 min vs 30) | Unaffected and still open. Predates the freeze. **Not to be closed by widening the margin.** |
| **I-094 / A-97** (D27 four years out of vintage) | **Closes in Phase 5** — vintaging is exactly the fix. |
| **I-097** (D10 `location_id`) | Unaffected; the schema correction stands. |
| **I-096** (dashboard 504) | Unaffected; MIMIC-side. |
| **E2-7** (D31 market series not built) | **Closes in Phase 6.** |
| **Spec references to "10 years"** | The span is **11.75 years**, so any ten-year-window requirement is exceeded. `FX-BN-05` and `T-OBS` are not in this repo — see **D8**. |

---

## Awaiting approval

**I have written no code and changed no behaviour for this plan.** The only
actions taken were stopping the probe on instruction and recording its metrics.

Phase 1 starts when you say go.
