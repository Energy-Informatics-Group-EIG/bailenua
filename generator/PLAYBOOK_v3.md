# PLAYBOOK v3 — the Baile Nua historical replay as a training set

**Status: DRAFT FOR APPROVAL. No code written or changed.**
**Supersedes v1 and v2. Phase 1 starts only when you say go.**

> **UNVALIDATED SIMULATION EVIDENCE.** Every quantity is measured on this
> machine and labelled so, read from a file in this repo and cited, or flagged
> unverified. Nothing is an estimate presented as a fact.

Scope: **1 Jan 2015 → 30 Sep 2026**, **4,291 days**, **3 leap days** (2016,
2020, 2024), run as a **single chained trajectory**, then nightly live forward
mode. Baseline: branch `hrsd-v1-freeze2-finish`, tag `v1-engine-freeze-2.1`,
digests `b8252f59…` / `e0ab1c83…`, suite 1,108 tests with 1 known failure
(I-101), **nothing pushed**.

### What changed from v2

* **All decisions settled.** D11–D17 answered; §8 holds only what is new.
* **The framing changed, and it is the biggest change in this document.**
  Baile Nua is now explicitly a **training set in which outcomes emerge**.
  That requires a household finance layer the model does not have, and it makes
  crisis response and upgrade adoption **endogenous**.
* **Phase 16 split:** 16a (PARA//EL observation, needs no LEC or FLEXUS build)
  and 16b (flexibility services, gated on both).
* **Role-scoped data views** added as a deliverable with its own tests.
* **Total ≈143 working days**, up from 111, plus 5.12 days of chained runtime.
  The increase is the finance and outcomes layer (13 d), the role views (6 d),
  and splitting 16 into two 10-day halves.

---

## 1. Goal, non-goals, boundary

**Goal.** One town simulated day by day from the real weather, prices, calendar
and demography of each day, as a **single chained trajectory**, so that any
pattern is attributable to something that happened — and so the 2022 census
becomes a **test** rather than an input.

**Non-goals.** Not a scenario engine. Not a detector (r4 §248). Not validated.
No transport model.

### 1.1 Outcomes emerge; they are not imposed

This is the governing principle of v3 and it changes what the model must
contain.

Occupants persist from 2015 through the chain, so a household has a **history**:
the same people, ageing, in the same dwelling, with upgrades arriving over time
per Phase 11. **Comfort, bills and energy poverty must then fall out of the
physics and the household's finances — never from a script.** A home with PV, a
heat pump and good fabric should feel the 2022 energy crisis less *because its
bill is smaller*, not because a rule says it suffers less.

**What this requires that does not exist today:**

| needed | status |
|---|---|
| Household income | **absent.** `saps.py:626` records why: "Used as the income-band proxy: **Census publishes no household income**." There is a *proxy*, not income. The `income_quintile` in `mimic/extended_pool.py:356` belongs to the synthetic MIMIC pool, not the town |
| A bill computed from simulated consumption | **absent.** The *rate structure* is sourced — CRU's decomposition into unit rate, standing charge per day and five components that "reconcile to the estimated annual bill it states" — but nothing multiplies simulated kWh by a tariff |
| Energy-poverty measures | **absent entirely** |
| Indoor temperature, comfort | **present.** `comfort` is a D05 z-score trait, `temp_living_c` is a D16 field, `behaviour/comfort_taking.py` and `ablation_u22.json` exist. Comfort *hours* as a metric does not |

**Endogenous adoption, with the national total preserved.** Which households
adopt PV, a heat pump or retrofit may depend on income, tenure, BER and
simulated bills — but the yearly totals must still match the sourced national
series. The way to have both is a **ranked allocation**: score every eligible
household's propensity from income, tenure, BER and its own bill burden, then
take the top *N* where *N* comes from the sourced series. The total stays exact
and the selection stays endogenous. No propensity model is permitted to change
the total.

**Your parallelism question — confirmed, with one consequence.** The chain is
serial, so making adoption depend on simulated bills costs **no** parallelism:
year *N+1* already cannot start before year *N* finishes. The v2 constraint
"keep adoption exogenous so years remain parallelisable" existed *only* to
protect year-level parallelism, which chaining had already removed. It is
withdrawn (§4 housekeeping).

The consequence, which v2's §6 got wrong and I am correcting: **the life course
can no longer be precomputed for the whole span in one pass.** Its
*demographic* part — births, deaths, moves, separations — stays
physics-independent and precomputable. Its *adoption* part becomes endogenous
and must be decided year by year inside the chain. §6's overlap table is
updated accordingly.

### 1.2 The boundary

R02: "Baile Nua is a base model… Scenarios and interventions run in BNIT."
U06: "(a) in the base town; BNIT can re-tier." U10: "(a) for existing retail
tariffs; dynamic and flex signals stay in BNIT."

Residential flexibility in Ireland was negligible before ~2023, so FLEXUS
activity is **not "what happened"** and cannot sit in a replay that claims to
be real.

| layer | where | content |
|---|---|---|
| **Base replay** | **Baile Nua** | GT at full resolution, all 4,291 days; observable layer **by era**; household finance and emergent outcomes |
| **16a observation** | **BNIT**, edge emulator per **FX-BN-04** | PARA//EL/EdgeWare sensing for enrolled homes from enrolment date. **Needs no LEC or FLEXUS build** |
| **16b flexibility** | **BNIT**, over the frozen replay | LEC programmes, signals, offers, delivery, settlement via BN-6/BN-7. **Gated on the LEC and FLEXUS builds** |
| **Role views** | **BNIT** | the seven role-scoped views, from the coupled run |

The replay is frozen before any coupled run reads it. No coupled run writes
into a base package.

| scope | Baile Nua | BNIT |
|---|---|---|
| A–C, E, G, H, I, J, K, P | **yes** | — |
| D COVID restrictions, WFH, mortality | **yes** | — |
| F estates, growth, amenities | **yes** (projection-labelled after today) | alternative trajectories |
| F Abbeylands construction loads, LEC/MV | **backlog, §11** | — |
| F/I transport, modes, CMATS, mode shift | — | **yes** |
| M uptake, endogenous selection, calibrated totals | **yes** | alternative uptake rates |
| N observable layer eras 1–2 | **yes** | **era 3: enrolment + D18 (16a)** |
| O crisis behaviour, bill-burden driven | **yes** | — |
| **Household finance, comfort, energy poverty** | **yes** | — |
| Flexibility services, any year | — | **yes (16b)** |
| Role-scoped views | — | **yes** |

---

## 2. Phases

Order: **population defects → engine generalisation → data → finance →
behaviour → outcomes → validation → chained run → observation → views →
flexibility.** No phase starts before its predecessor's gate. Every phase ends
with a freeze cycle (§4.4).

### ⭐ FAST PATH — Phases 0–4, 24 days, usable on its own
A real-weather, census-back-tested replay.

### Phase 0 — Baseline, decisions, issue logging (2 d)
Answer §8; record starting digests; confirm the decade retired and archived.
**I-105 (DST), I-106 (age structure) and I-107 (map/D01) are already logged.**
**Exit G0:** every §8 item answered; every §3 source acquired with licence and
manifest, or dropped with a written reason. **No source assumed obtainable.**

### Phase 1 — Population defects (5 d)
* **I-069:** economic status drawn with **no age conditioning** — 241
  "students" at a **median age of 45**; 8,426 venue-presence rows (**7.3% of
  114,951**) carry no venue id.
* **I-106:** measured at t0 against SAP2022 for the town's own small areas —
  65+ **9.4% against 13.2%** (273 of an expected 386, **−29%**), 75–84
  **−48%**, 85+ **−71%**, worsening monotonically with age: a draw truncated or
  under-dispersed at the top.
* **Exit G1:** economic status age-conditioned; age structure within declared
  tolerance of SAP2022 **in every band including 85+**; the 7.3% gap a declared
  residual.
* **Why first:** `venues.py` argues it itself. **No population or venue feature
  work until G1**, and **D3's COVID arithmetic is not computed until G1** —
  census-correct, 85+ goes from 10 to ~34 and the expectation rises ~2.5–3×.

### Phase 2 — Time axis (6 d)
`build_realisation(year)` → date range (**closes I-088**: the data is already
real observed Met Éireann, both stations on disk from 1962/1955, so this is an
interface change). `build_calendar` **raises `NotImplementedError` for any year
but 2022** — generalise; per-year holiday and school-term tables. Retire
`DAYS_PER_YEAR`.
**Exit G2:** 366-day 2016 balances; **29 Feb in 2016, 2020, 2024**; 12 holiday
tables verified independently; 2022 keeps the **18 Mar one-off** and still
excludes **St Brigid's, which begins 2023**.

### Phase 3 — DST and clocks (5 d)
UTC sim, **local-clock schedules**, local-time exports. `MINUTES_PER_DAY = 1440`
backs every per-minute array; `tariffs.py:344` declares `BAND_CLOCK` as local.
**Exit G3:** bands on the correct local hour across **all 23 transitions**; 23-
and 25-hour days balance. **I-105 is a live defect today**, independent of this
plan.

### Phase 4 — Population base and the census checkpoint (6 d)
t0 is **2022-01-01, Census 2022**; only `sap2022` is on disk. Acquire **Census
2016 SAPS**, parameterise the vintage, age forward to 1 Jan 2015.
**Belgard is not in today's t0** — `build_year` runs 1860–2021 with **zero
dwellings after 2021** — so the work is the **mapping**: how small areas
reconcile to SAP2022 dwelling counts once estates carry completion dates, with
Cluain Ard (2019) inside the aged base by 2022 and Belgard (2024) outside it.
**Exit G4 — the prize:** 2015 → 2022 compared against actual SAP2022 marginals
on **population and dwelling stock**, within declared tolerances. Today the
census *is* the base and can never be a test.

### Phase 5 — Vintaged rates and two price regimes (7 d)
`SourcedValue` has **no validity field** and uses `__slots__`. Add validity
intervals, a date-keyed resolver, the **SEM SMP → I-SEM switch at Oct 2018**.
**Exit G5:** no rate outside its interval; every vintage cites a document on
disk — `test_d27_every_sourced_rate_is_in_its_cited_document` greps the cited
document's **bytes**, which is this phase's real cost.

### Phase 6 — Market and system data (5 d)
SEM SMP, I-SEM DA/BM, EirGrid demand and carbon; build D31's market series.
**Exit G6: E2-7 passes for the first time** — today
`observation/nonsensor.py:40` records it as "**What is NOT built, and E2-7
fails on it**".

### Phase 7 — Life course and housing chain (8 d)
**Exists:** vacancy on last-occupant loss (`tenyear.py:893-905`);
`VACANT_FROST_SETPOINT_C = 7.0`; refill from **VAC04's 5–6% Cork rate and
VAC17's gross flows**; `separation`; births from `vsa36`/`vsa104` by mother's
age.
**Add:** sourced **probate/sale/letting durations** (vacancy is year-granular
today — a dwelling can empty and refill with no elapsed time);
**movers-based household composition** (today `integers(1,5)` size,
`integers(20,70)` age, all `"at work"` — **no child has ever moved into a Baile
Nua dwelling**, despite SAP2022 movers being on disk); **pre-occupancy
renovation**; **occupancy steps as dated passport events** (the map covers only
six building-change types, so **no occupancy step is a D03 event today**);
**tenancy/meter structural break** with tenure transition; **individual
emigration** (today folded into whole-household `move_out`, `[A] A-25b`).
**Exit G7:** chain complete and sourced. **Movers composition first.**

### Phase 8 — Institutional population and COVID behaviour (10 d)
A care-home population, then restriction levels by date, school closures,
time-varying WFH, age-banded excess mortality pre-vaccination, vaccine rollout
by age band, care-home deaths separated. **Together** because there is **no
institutional population** today — every "institution" hit is a third-level
education venue — so **every modelled death vacates a dwelling**.
**Exit G8:** D3's presentation rule implemented in the artefact; care-home
deaths vacate no dwelling; **every IFR, seroprevalence and national death
figure fetched and cited before it is written**.

### Phase 9 — Town growth and amenities (8 d)
Exercise D01/D02's **never-used** validity intervals (`valid_to` on **0 of
1,092**; `version` = 1 on all). **Cluain Ard 2019, Part V 10% social**
(**D13**). **Belgard 2024, nZEB A-rated, Part V 20% — 10% social + 10%
affordable/cost-rental, A-numbered on a land purchase after 1 Aug 2021**
(**D13**); 190 A-rated dwellings already exist so the archetype is available.
**Sizes and dwelling-type mix derived from CSO new dwelling completions (NDA)
for Cobh/Cork County in 2019 and 2024, scaled to the town** (**D15**), with any
residual A-numbered. Abbeylands phased to 2027. Part V tenure (D02 has
`rented social`, 116 present). First occupants from CSO new-dwelling data.
Amenities by statutory ratio, extending the venue layer's derived-count +
sourced-capacity pattern (DoE; Childcare Guidelines ~20 places/75 dwellings;
Compact Settlement Guidelines 2024; retail by catchment). Network growth
(`_trafo_type` already auto-sizes).
**Exit G9:** no dwelling produces data before completion; +300 dwellings
(**+27.5%**) adds ~15 transformers, ~18 feeders, ~615 buses; D17 rows scale as
**96 epochs × (transformers + feeders)**, a rule reproducing the measured
157,248 rows exactly.
**Excluded → §11:** construction-site loads, LEC/MV.

### Phase 10 — Household finance (8 d) — NEW
* **Work:** income per household from **sourced CSO SILC distributions by
  tenure and composition, updated by year**; bills computed from each home's
  **actual simulated consumption and export**, its resolved tariff, standing
  charges and credits. Both are new: income does not exist, and no bill is
  computed anywhere today.
* **Exit G10:** every household has a dated income with a sourced distribution
  behind it; every home has a bill reconciling to CRU's own component
  decomposition; **no bill uses anything but simulated consumption** — no
  scripted or assumed usage.
* **Depends on:** G5 (rates must resolve by date before a bill means anything).

### Phase 11 — M: technology uptake, endogenously selected (7 d)
* **Work:** yearly 2015–2026 uptake of rooftop PV, BESS, heat pumps,
  insulation/windows/deep retrofit, EVs and chargers from SEAI grant data, BER
  statistics, CSO/SIMI and ESB Networks microgeneration connections.
  **Selection by income, tenure, BER, dwelling type and simulated bill burden —
  never uniform — with yearly totals held exactly to the sourced series by
  ranked allocation (§1.1).** After today, one trajectory toward sourced
  Climate Action Plan targets, labelled projection.
* **Exists:** the mechanism — `retrofit_fabric`, `retrofit_heat_pump` and three
  DER events keyed to `HEBEU37` already emit dated passport events. Only the
  **rates and the selection** are missing.
* **Exit G11:** each install a dated BEP event changing load from that date;
  national totals matched per year **exactly**; selection demonstrably
  income/tenure/bill-dependent; **the demographic life course still
  precomputable, the adoption part moved into the chain** (§1.1).

### Phase 12 — N: observable layer by era (7 d)

| era | from | observable |
|---|---|---|
| 1 | 2015 | bi-monthly actual or estimated register reads only |
| 2 | smart-meter install (ESB rollout 2019–24, sourced by area and year) | 30-minute import/export interval, realistic gaps and estimates |
| 3 | 2021, **16a** | 15-minute and device-level for **enrolled homes from their enrolment date only** |

GT stays full resolution throughout; **only the observable layer changes.**
**Exit G12:** no home has interval data before its install date; era
transitions dated per home; effect on **D18, D19, D30, D31** reported with
measured bytes.

### Phase 13 — O: crisis behaviour, bill-burden driven (9 d)
* **Entry:** G6 (prices), G8 (restrictions), **G10 (bills)**.
* **COVID 2020–22:** higher daytime load, higher self-consumption and lower
  export, lower EV charging and mobility, shifted flexibility availability —
  **with the effect on tradeable flexibility in 2021 quantified**.
* **Energy crisis 2021–24, endogenous:** wholesale gas and electricity path;
  **each Irish retail price change by supplier and date**; heating oil price;
  electricity credits by date and amount. The behavioural response — lower
  setpoints, shorter hours, fewer rooms heated — **scales with each
  household's own bill burden**, with the **elasticity sourced** from
  SEAI/CSO/ESRI and stated explicitly. A PV, heat-pump or well-insulated home
  responds less **because its burden is lower**, which is an outcome, not a
  rule. Low-income and Part V households respond more for the same reason.
* **Recovery 2023–24**, with partial persistence **only if the evidence
  supports it** (**D14**) — if the studies are equivocal, no persistence, and
  say so.
* **Exit G13:** every date verified against its source; the elasticity sourced
  and cited; no household's response set by anything but its own burden.

### Phase 14 — Emergent outcomes dataset (5 d) — NEW
* **Work:** a per-year outcome dataset carrying **indoor temperature and
  comfort hours**, **bill burden**, and **energy poverty by tenure and Part V
  status** on two measures: the **ESRI expenditure measure** (energy spend
  above 10% of disposable income) and the **CSO SILC subjective measure**
  ("unable to keep home adequately warm").
* **Exit G14:** every outcome derived from simulated physics and simulated
  finances, with no imposed rate; the two poverty measures reported separately
  and never averaged.

### Phase 15 — Policy events, behaviour, data flaws (6 d)
Electricity credits 2022–24; MSS export payments from Dec 2022; smoky coal ban
Oct 2022; supplier switching (CRU); holidays abroad (empty homes), Christmas
returns, college terms, hybrid days by sector, 2022 temporary-protection
arrivals; observable-layer flaws — estimated reads, meter swaps, comms gaps,
DST glitches — **tied to real events**.
**Exit G15:** every dated event cites a source or carries an A-number.

### Phase 16 — Validation (7 d)
Named targets and tolerances against **ESB Networks SLPs per year 2015–2025**
(D9), EirGrid demand shape, CSO counts, **CSO SILC energy-deprivation rates by
year 2015–2025 — the 2022 rise must appear as an emergent result, not a fitted
one** — and **mean comfort improvement after retrofit from SEAI evaluation
studies**. **No CER/ISSDA** (D1).
**Exit G16:** every target passes, or fails and is reported as a failure. **No
tolerance widened to manufacture a pass.** The SILC comparison is the strongest
test in the plan: the 2022 deprivation rise either emerges from prices,
incomes and physics, or it does not.

### Phase 17 — P: chained production (6 d + 5.12 d runtime)
Three real engine changes, not packaging:
1. **Promote `restore()` to the production path.** It exists (`run.py:1129`),
   restores `rc` zone temperatures, `battery.soc`, `ev_soc`,
   `failed_appliances` and `dhw.temp_c`, and refuses partial restores — but its
   docstring says production never uses it: "a whole-year re-run … never
   restores anything — it recomputes from day zero." Today it is a
   **replay-test harness only**.
2. **Close the `person_state` gap.** `Checkpoint` carries `person_state`
   ("per-person evolving state"); `restore()` iterates **only
   `household_state`** — so activity, location, routines and habits are
   **written and ignored**. Exactly the **I-081** failure mode, where
   `dhw_tank_c` was carried and ignored so "every replayed day began with the
   cylinder at its construction temperature … and diverged on the morning
   reheat", invisible for weeks.
3. **`sim_day` continuous 0 → 4,290** (**D11 agreed**). The `SeedTree` is keyed
   on (seed, entity, `sim_day`), so a year restarting at 0 would **re-draw
   2015's random numbers**.
**Exit G17:** every year package complete with manifest, checksums, code digest,
catalogue entry **and its start and end checkpoint hashes**; `verify_chain`
clean across 4,291 days; **end hash of year *N* equals start hash of year
*N+1***; continuity test shows no step change at any 31 Dec → 1 Jan; the merged
multi-year view built **from the year packages, not a separate run**.
**Risk: high** — restore reaches production for the first time, and the project
has already paid once (I-081) for a carried-and-ignored field.

### Phase 18 — 16a: PARA//EL / EdgeWare observation (10 d)
* **Entry:** **G17 only.** Needs **no LEC and no FLEXUS build** — it is an edge
  emulator per **FX-BN-04**.
* **Work:** for enrolled homes from their enrolment date — environmental
  sensors (zone temperature, humidity, CO2, presence where consented); DER
  telemetry (PV, battery, heat pump, EV charger); 15-minute electricity; and
  **NILM appliance disaggregation produced as PARA//EL would infer it, with its
  errors**, scored against GT appliance truth **for the modeller view only**.
* **Enrolment (D12):** from **1 Jan 2021, ramping to 30% of dwellings by
  30 Sep 2026**, skewed toward homes with PV, heat pumps or EVs and toward
  estates with an energy co-op. **A-numbered programme assumption** — no
  sourced enrolment data exists, and the failed search is recorded with it.
* **Exit G18:** the "complete building" dataset exists for 2021–2026; NILM
  error characterised and scored; **flexibility event counts per home and per
  weather regime for 2021 → Sep 2026**, with an explicit statement on whether
  they suffice for RD estimation and forecasting. If they do not, that is a
  finding, not something to fix by widening a window.
* **Sizing:** at 30% enrolment, D18 is **~9.5 GB** (§6).

### Phase 19 — Role-scoped data views (6 d)
* **Entry:** G18.
* **Deliverable:** a **view specification** — who sees which columns, at what
  aggregation, from which date — plus **generated example extracts per role**,
  so the BNIT–FLEXUS map's role selector can read them.

| role | sees |
|---|---|
| Homeowner / occupant | full data, **their own home only** |
| PARA//EL | everything local; shares upward **only** at the home's consented level |
| EdgeWare | community-level detail needed to model the community — partition aggregates, consented member data |
| FLEXUS | **only what EdgeWare passes up**; never household-identifiable |
| DSO (LEC) | network data plus aggregates of **≥5 premises** (**LC-AMI-03**); **flexibility columns excluded from AMI** (**LC-AMI-01**) |
| Regulator (CRU) | compliance, settlement and programme aggregates |
| Modeller / researcher | observable data plus GT scoring, **labelled designer view, never used in a test run** |

* **Exit G19:** **no view exposes data above its tier**, and **no DSO aggregate
  ever covers fewer than 5 premises** — both as tests, not review. The
  modeller view carries the designer label in the artefact itself.

### Phase 20 — 16b: Flexibility services (10 d)
* **Entry:** G17, **plus the LEC build and the FLEXUS build** — neither is in
  this repo and neither is mine to assess (**D16**).
* **Work:** LEC programmes, signals, offers, delivery and settlement over the
  **frozen** replay via BN-6/BN-7. Labelled a BNIT run throughout.
* **Exit G20:** reads the frozen replay, writes only flexibility datasets, no
  base package modified.

**Total ≈143 working days** (0–17: 117 d; 18–20: 26 d), plus 5.12 days of
chained runtime.

---

## 3. Data acquisition

Storage `sources/<family>/<file>` + `*.manifest.json` (bytes, SHA-256),
registered with URL, licence, title, use and exposure. `sources.require`
**re-hashes on every use and refuses changed bytes** — the provenance record
already exists.

**A missing source makes the run REFUSE.** No fallback, no substitution, no
interpolation across an absence. `require` already raises
`SourceError: source 'x' is registered but missing from disk`.

### On disk
Met Éireann `hly3904` (1962→2026-10-01) and `hly1075` (1955→2026-10-01), hourly,
CC-BY — **the whole span, plus the Dec 2014 warm-up**; irradiance **derived**
(pvlib Ineichen + Erbs from observed cloud and sunshine; no `glorad` in the
files); ESB Networks SLPs **2022 only**; CSO `vsa08` deaths (annual),
`vsa36`/`vsa104` births and fertility, `ep006` migration, `pea01` estimates,
`HEBEU37` installations, `VAC04`/`VAC17`/`F2095` vacancy, `SAP2022` movers;
SEAI BER research tool and `EBA02`/`EBQ02`; CRU bill-component report;
`HEBEU88` billing tariff.

### To acquire
| input | for | cadence | licence |
|---|---|---|---|
| Census 2016 (or 2011) SAPS, Cobh | 4 | census | CC-BY |
| CSO **weekly** deaths | 8 | weekly | CC-BY |
| Holidays 2015–26, school terms | 2 | annual | python-holidays / DoE |
| SEM SMP → Sep 2018 | 6 | half-hourly | to confirm |
| I-SEM DA/BM from Oct 2018 | 6 | half-hourly | to confirm |
| EirGrid demand + carbon | 6 | 15-min | to confirm |
| Retail tariffs per year; **supplier price changes by date** | 5, 13 | per change | CRU / notices |
| COVID restriction levels, school closures | 8, 13 | event | gov.ie |
| Vaccination by age band | 8 | daily | HSE/HPSC |
| CSO WFH series | 8, 13 | quarterly | CC-BY |
| Google mobility | 8, 13 | daily, **Feb 2020–Oct 2022 only** | CC-BY |
| **CSO SILC income distributions by tenure and composition, by year** | **10** | annual | CC-BY |
| **CSO SILC energy deprivation by year 2015–2025** | **16** | annual | CC-BY |
| **CSO NDA new dwelling completions, Cobh / Cork County** | **9** | quarterly | CC-BY |
| **SEAI retrofit evaluation studies (comfort improvement)** | **16** | study | SEAI |
| **SEAI/CSO/ESRI setpoint-response elasticity studies** | **13** | study | varies |
| **ESRI expenditure-based energy-poverty definition** | **14** | reference | ESRI |
| SEAI grant statistics by year | 11 | annual | SEAI |
| ESB Networks microgeneration connections | 11 | annual | ESBN |
| EV registrations + chargers (CSO/SIMI) | 11 | monthly | CC-BY / SIMI |
| Climate Action Plan targets | 11 | periodic | gov.ie |
| CSO appliance ownership; oil and solid-fuel decline | 11 | periodic | CC-BY |
| ESB Networks smart-meter rollout by area and year | 12 | annual | ESBN |
| Heating oil price (CSO or SEAI) | 13 | monthly | CC-BY |
| ESB Networks SLPs per year 2015–2025 | 16 | annual | published |
| CSO/ESRI projections, Cork CDP targets | 9 | periodic | CC-BY / council |
| Storm warning register | 2 | event | Met Éireann |

**Two A-numbered gaps with their failed searches recorded**, per the project's
existing convention:

* **Enrolment (D12).** No published series exists for PARA//EL/EdgeWare
  enrolment — it is a programme fact, not a statistic. The A-record states the
  ramp (1 Jan 2021 → 30% by 30 Sep 2026), the skew (PV / heat pump / EV, energy
  co-op estates), and that no source was sought because none can exist.
* **GAA and televised fixtures.** `sport` already carries **A-43** — "'sport'
  matches 115 tables, none of them a fixture list or an attendance series — the
  matches are road freight TRANSPORT". Dates tabled as declared assumptions.

Storms need no acquisition to **appear** — derived from observed wind, and
**Ophelia (2017), Emma (2018) and Éowyn (Jan 2025) are all inside the station
data**. A register adds only the warning *status*.

---

## 4. Rules

1. Every value **sourced or A-numbered**, with the search that failed.
2. **No fabricated data** — no synthetic geometry presented as surveyed
   (`structural.py` refuses "a fabricated polygon that would read as surveyed
   geometry"); no interpolation across an absence; no national figure applied
   to the town without the scaling stated.
3. **Three labels on every row:** `observed` vs `projection` (cut-over = run
   date), and `provisional` vs `final`.
4. **Freeze cycle per phase:** new tag, digests recomputed, `_frozen_root`
   rebuilt from the tag, worker and aggregator reissued as **new files** (never
   editing a mode-500 original — I-080), digests verified. 0.5 d/phase,
   included.
5. **Nothing pushed.** Repo and `code/` stay local.
6. **Stop and ask** on anything not covered here.
7. **No gate passed by widening it.**
8. **Nothing deleted** — superseded artefacts renamed aside.
9. **Each day stamped with its code digest**, closing the I-090 class.
10. **Outcomes are never imposed.** No comfort level, bill, poverty rate or
    crisis response is written as a target. Every one is computed from physics
    and finances, and compared against a source only at a validation gate.
    **(Replaces v2's "adoption stays exogenous so years remain
    parallelisable", which the serial chain made unnecessary — §1.1.)**
11. **Calibrated totals, endogenous selection.** A propensity model may decide
    *who* adopts; only the sourced series decides *how many*.

---

## 5. Tests

**Assumptions to remove.** Measured: `365` appears in the suite **4 times
across 3 files**, plus an `or 365` default in `plausibility/checks.py:902` and
the `365 * n_years` sizing formulas in `release/policy.py`.
`tariffs.py:179` notes "2022 is not a leap year" and standing charges are
365-day figures. Small and bounded — under a day — with the risk in the sizing
formulas, not the tests.

**New tests by phase.** Age-conditioned economic status and SAP2022 structure in
every band (1); leap days, 12 holiday tables (2); 23 DST transitions with
correct local tariff hours, 23- and 25-hour balance (3); census-2022 population
**and dwelling-stock** checkpoint (4); no rate outside its validity interval,
Oct 2018 regime boundary (5); no NO_DATA in span (6); every occupancy step a
dated passport event, no refill without elapsed duration, a child in an
in-moving household (7); care-home deaths vacate no dwelling (8); no data
before completion date, Part V share, amenity ratios (9); **every bill
reconciles to CRU's components and uses only simulated consumption; every
household income traces to a dated SILC distribution** (10); **yearly uptake
totals match the sourced series exactly while selection correlates with income,
tenure and bill burden** (11); no interval data before install date, era
transitions dated (12); **crisis response scales with bill burden and with
nothing else; every crisis date verified; the elasticity cited** (13); **both
energy-poverty measures computed from simulated finances, reported separately,
never averaged** (14); policy-event dating (15); per-year SLP targets, **the
2022 SILC deprivation rise emerges**, retrofit comfort improvement (16);
**year-boundary continuity, end-hash == next start-hash, `verify_chain` clean
over 4,291 days, person-state restored (the I-081 guard extended), `sim_day`
continuous** (17); NILM error characterised and scored against GT (18); **no
view exposes data above its tier; no DSO aggregate covers fewer than 5
premises** (19); coupled run writes no base package (20).

**Regression.** The existing suite is the harness: **1,108 tests, 1 failed /
1,072 passed / 35 skipped**. The failure is **I-101** (27 min vs 30; it fails on
the freeze-1 tree too, so it predates recent merges) and **must not be closed
by widening the margin — the margin is the claim.** Any new failure blocks its
phase.

---

## 6. Runtime, storage, delivery

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

### Storage, at the agreed 30% enrolment

| | |
|---|---|
| Base, D18 omitted, 4,291 days | **66 GB** |
| D18 for enrolled homes, 30% by Sep 2026 | **~9.5 GB** |
| **Total** | **~76 GB against 110 GiB free** |

Linear ramp from zero over the 2,099-day enrolment window, 1-minute basis as an
**upper bound** (Phase 12 specifies 15-minute plus device-level, lighter for the
interval part). **No external volume and no split run.** D18 is never dropped —
it is scoped to enrolled homes from their enrolment date, a modelling decision,
not a storage one. If device-level telemetry proves heavier than the 1-minute
estate basis I will re-size and come back rather than overrun silently.

### Parallelism — the chain removes it

**P's chaining makes jobs=2 by year impossible, and that is the right trade.**
A chained run inherits the **simulated** end state of the previous year, so
year *N+1* cannot begin until year *N* finishes. Serial by construction. Cost:
**5.12 days wall instead of ~2.56**; bought with genuine continuity of thermal
mass, tanks, SOC, occupancy and life course across eleven boundaries, and a
verifiable hash chain end to end.

| candidate | overlap | note |
|---|---|---|
| Export for year *N* while *N+1* simulates | **yes, fully** | reads a finished package; 81 s and 130 s measured this session |
| Year packaging, checksums, catalogue | **yes, fully** | pure I/O over a finished year |
| Monthly provisional drops | **yes** | package month *M* while *M+1* simulates |
| Within-year write flushing | **measure first (D17 agreed)** | writes are ~49% of runtime (50.7 s against 52.3 s), so the ceiling is large — but the run was measured **I/O bound** on 12 Oct ("write time overtook sim time, 119.4 s against 104.4 s"), so a background flush may buy nothing |
| **Demographic life course for the whole span** | **yes, once** | physics-independent |
| **Adoption part of the life course** | **NO — changed in v3** | endogenous on simulated bills (§1.1), so it must be decided year by year inside the chain |
| Simulation of two years | **no** | the chain forbids it |

Memory is unchanged: one process at ~7.5 GB `ru_maxrss`, well inside 32 GB, and
the jobs≥2 RSS problem disappears with the option.

### Chained delivery

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

Plus the 2015 warm-up and ~0.5 h of packaging per year, which overlaps the next
year's simulation. **Monthly provisional drops ~52 min each**, shipped
`provisional` and superseded by the year package.

**The 2015 cold start: a 31-day warm-up on December 2014 weather**, already on
disk. The deepest carried state is building thermal mass, time constant of
order 1–5 days for heavy masonry (DHW tank and battery SOC ~1 day), so 31 days
is **more than six times the longest constant**. December also absorbs a cold
start better than January: the indoor–outdoor gradient is near its annual
maximum, so the initial-condition error is largest **and** fastest-decaying
there. The warm-up is **discarded burn-in** — never packaged, never published,
no `observed` label.

**Chain verifiability.** Each package records the checkpoint hash it started
from and the one it ended with. `CheckpointStore.verify_chain` already
"recomputes every link and reports the earliest day at which the recorded chain
diverges", and `checkpoint_chain_head` is already published in run diagnostics
— so the claim is checkable with machinery that exists.

**The merged multi-year view is built from the year packages, never a separate
run**, so it cannot disagree with them.

---

## 7. Live forward mode

**Nightly scheduled job. Never on page load.** No request path generates a day.

* **Scheduler:** one nightly job, last completed day → yesterday, in order,
  **continuing the chain** from the last checkpoint.
* **Idempotency:** a day is complete **iff** its sentinel exists — the decade's
  own rule, per day. Complete days skipped; partial days renamed aside and
  redone, never resumed in place, because the writer numbers parts from zero.
* **Provisional flags:** inputs arrive at different lags (weather next day,
  prices next day, CSO quarterly, SILC annual, census every six years). A day
  with incomplete inputs ships `provisional` with the lagging source **named**,
  and is later **superseded by a new version** rather than mutated — which is
  what D02's unused `version` field is for.
* **No silent fallback:** a day missing a required input is **not generated**;
  it is reported blocked, naming the source.
* **Hosting:** ~103 s and ~16 MB per day, so a night's work is minutes on the
  existing workstation; ~5.8 GB/year without D18. Needs a scheduler, a writable
  sources tree and a monitored failure path. r4 §772 already anticipates this.

---

## 8. Open decisions

v1's D1–D10 and v2's D11–D17 are settled and recorded. Renumbered in order,
only what is new:

| # | decision | recommendation |
|---|---|---|
| **D18** | **The behavioural elasticity of heating response to bill burden** (Phase 13) is the number the whole crisis layer turns on, and I do not know whether a usable Irish estimate exists. | Acquire the SEAI/CSO/ESRI studies in Phase 0 and **report the elasticity you can source before Phase 13 starts.** If no Irish estimate exists, the options are an A-numbered value with a sensitivity range, or no behavioural response at all — and I would rather tell you that at G0 than discover it in Phase 13. |
| **D19** | **Which energy-poverty measure is primary** (Phase 14). The ESRI expenditure measure and the SILC subjective measure disagree by construction — a well-insulated low-income home can pass one and fail the other. | **Report both, never averaged, and name neither primary.** The disagreement is informative. Validation in Phase 16 scores against SILC because that is what SILC publishes. |
| **D20** | **Income dynamics.** SILC gives distributions by year, not household trajectories. A household's income over 11.75 years can follow the distribution's drift, or be redrawn each year, or track employment events from the life course. | **Track the life course** — employment change is already an event type — with the distribution as the anchor. Redrawing annually would destroy the cohort continuity that §1.1 exists to create. |
| **D21** | **NILM error model** (Phase 18). Scoring PARA//EL's inferred appliances against GT needs a realistic error characterisation, and I have no source for PARA//EL's actual accuracy. | Supply measured PARA//EL accuracy if it exists; otherwise an A-numbered error model with the failed search recorded, and the scoring reported as indicative only. |
| **D22** | **Consent levels** (Phases 18–19). "Presence where consented" and "shares upward only by the home's consented level" imply a consent model per home that does not exist. | A **sourced or A-numbered consent distribution** set in Phase 18, with the tiers named in the view specification so Phase 19's tests can assert against them. |

---

## 9. Reporting

Per phase, one report: **a summary table** (entry gate, work, deliverables,
tests added/passing/failing, exit verdict, days spent vs estimate); **measured
numbers with their basis**, every runtime and RSS figure stated with the machine
state beside it — the standing lesson of I-089 and the four-arm probe, that **no
cost figure means anything without the machine state beside it**; **decisions
needed**, each with a recommendation and what is blocked; **new issues** from
**I-108**; **the freeze record** (tag, digests, root rebuild, drivers reissued).
I stop at every gate and wait.

---

## 10. Issues

| issue | consequence |
|---|---|
| **I-090** | **Closes.** One freeze, one chained replay; `wp5_decade` and its D03/D09/D20 residual disappear. The per-day digest stamp closes the **class**. |
| **I-100** | Already closed; the per-phase freeze cycle keeps it closed. |
| **I-088** | **Closes in Phase 2** — an interface limit, not missing data. |
| **I-069** | **Closes in Phase 1**; gates all population and venue work. |
| **I-105** | DST/tariff-band mismatch, **a live defect today**. Logged. Closes in Phase 3. |
| **I-106** | Age-structure deficit vs SAP2022 (65+ −29%, 85+ −71%). Logged. Closes in Phase 1. **Blocks D3's arithmetic.** |
| **I-107** | BNIT map holds positions, D01 is `POINT EMPTY`. Logged, not scheduled. |
| **I-103** | `RELOCATED_TO_RUN` points at `wp5_decade`, which **ceases to exist**. Revisit in Phase 9. |
| **I-104** | Already fixed. |
| **I-101** | Open, predates the freeze. **Not to be closed by widening the margin.** |
| **I-094 / A-97** | **Closes in Phase 5.** |
| **I-089** | Honoured, not closed: 103 s/day is the flush-inclusive figure. |
| **I-081** | Its lesson is Phase 17's main risk — a checkpoint field carried and ignored. The `person_state` gap is the same shape. |
| **E2-7** | **Closes in Phase 6.** |
| **FX-BN-05 / T-OBS** | FLEXUS obligations, not Baile Nua's. FX-BN-05 requires one town-year under 24 h wall — the replay measures **10.44 h/year**. T-OBS requires ten years of OBS — the replay supplies **11.75**. The FLEXUS spec is to be updated to "the 2015–2026 replay" separately, by you. |
| **FX-BN-04** | Phase 18's basis: the edge emulator, which is why 16a needs no LEC or FLEXUS build. |
| **LC-AMI-01 / LC-AMI-03** | Phase 19's tests: flexibility columns excluded from AMI; DSO aggregates never fewer than 5 premises. |

---

## 11. Backlog — needed before live mode reaches 2027

| item | effort | flag |
|---|---|---|
| **Abbeylands construction-site loads** — builder's supply, cabins, crane | 6–8 d | **needed before live mode reaches 2027.** Venues draw **no electrical load** today; a new non-domestic load class |
| **LEC connection application and MV reinforcement** | 8–10 d | **needed before live mode reaches 2027.** MV is a slack `ext_grid` by explicit design decision (`lv.py:254`) |
| **Map/geometry alignment (I-107)** | 10+ d | not scheduled; export map positions keyed to D01/D02 ids rather than fabricating polygons |
| **Transport, modes, CMATS, mode shift** | 15–20 d | **BNIT**, per R02 |

---

## Awaiting approval

No code written or changed. Phase 1 starts when you say go.
