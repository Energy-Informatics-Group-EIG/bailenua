# G0 source acquisition manifest

**Phase 0, PLAYBOOK v3.1. Status: IN PROGRESS — G0 NOT YET MET.**
Generated 2026-10-14. Statuses are measured, not assumed.

Gate G0 requires: *every source acquired with licence and manifest, or dropped
with a written reason. No source assumed obtainable.*

## Network reachability, tested

| host | result |
|---|---|
| CSO PxStat API | **200** — acquisition path verified end to end (PEA01, 40,608 B valid JSON-stat) |
| ESRI | **200** — WP824 acquired |
| SEAI | **403** to a default user agent; needs a browser-like fetch or a manual download |

## Acquired this phase

| source | key | status |
|---|---|---|
| ESRI WP824, price elasticity of residential gas demand | `esri.wp824.price_elasticity_residential_gas` | **ACQUIRED** — 1,649,355 B, sha256 `6e3b2627…`, manifest written, **answers D-117/D18** |

## Already on disk (verified this session)

| source | coverage | note |
|---|---|---|
| Met Éireann `hly3904` Cork Airport | 1962-01-01 → 2026-10-01, hourly | **covers the whole span plus the Dec 2014 warm-up** |
| Met Éireann `hly1075` Roches Point | 1955-12-01 → 2026-10-01, hourly | same |
| Solar irradiance | derived | pvlib Ineichen + Erbs from observed cloud and sunshine; no `glorad` in the files, so none is needed |
| ESB Networks Standard Load Profiles | **2022 only** | per-year 2015–2025 still to acquire (D-108) |
| CSO `vsa08` deaths by age/sex | annual | weekly series still needed |
| CSO `vsa36`, `vsa104` births, fertility | annual | |
| CSO `ep006` net migration | annual, county | |
| CSO `pea01` population estimates | annual | re-fetch verified today |
| CSO `HEBEU37` efficiency installations | annual | |
| CSO `VAC04`, `VAC17`, `F2095` vacancy | quarterly | acquired for the WP5 vacancy chain |
| CSO `SAP2022` movers | 2022 | the movers table Phase 7 needs |
| SEAI BER research tool, `EBA02`, `EBQ02` | year-stamped | |
| CRU bill-component report, `HEBEU88` | reference | the rate structure Phase 10 needs |

## Path proven, matrix code still to confirm

The PxStat `ReadDataset` pattern works; `ReadCollection` did not return JSON to a
plain GET, so the catalogue needs a different call before these can be fetched.

| source | for | phase |
|---|---|---|
| CSO SILC income distributions by tenure and composition, by year | household income | 10 |
| CSO SILC energy deprivation by year 2015–2025 | the 2022 rise must emerge | 16 |
| CSO NDA new dwelling completions, Cobh / Cork County | estate sizes and mix (D-114) | 9 |
| CSO weekly deaths | COVID excess mortality | 8 |
| CSO WFH series | time-varying WFH | 8, 13 |
| CSO appliance ownership; oil and solid-fuel decline | stock change | 11 |
| CSO/SIMI EV registrations and chargers | uptake | 11 |
| CSO heating oil price | crisis | 13 |

## To acquire, source identified, not yet fetched

| source | for | phase | note |
|---|---|---|---|
| Census 2016 (or 2011) SAPS, Cobh small areas | the 2015 base (D-106) | 4 | the fast path depends on this |
| Holidays 2015–2026 | calendar | 2 | `python-holidays` is a package, not a download; verify it carries the 18 Mar 2022 one-off and St Brigid's from 2023 before trusting it |
| School terms 2015–2026 | calendar | 2 | DoE circulars, per year |
| SEM SMP → Sep 2018 | price regime 1 | 6 | licence to confirm |
| I-SEM DA/BM from Oct 2018 | price regime 2 | 6 | licence to confirm |
| EirGrid demand and carbon | system data | 6 | licence to confirm |
| Retail tariffs per year; supplier price changes by date | bills, crisis | 5, 13 | CRU and supplier notices |
| COVID restriction levels; school closures | COVID | 8, 13 | gov.ie, event-dated |
| Vaccination by age band | COVID | 8 | HSE/HPSC |
| Google mobility | COVID | 8, 13 | **Feb 2020 → Oct 2022 only, then retired** — a partial source by nature |
| SEAI grant statistics by year | uptake | 11 | **SEAI 403s a default UA** |
| SEAI retrofit evaluation studies (comfort improvement) | validation | 16 | same |
| SEAI/CSO/ESRI setpoint-response studies | elasticity corroboration | 13 | WP824 found; more may exist |
| ESRI expenditure-based energy-poverty definition | outcomes | 14 | |
| ESB Networks microgeneration connections | uptake | 11 | |
| ESB Networks smart-meter rollout by area and year | observable eras | 12 | |
| ESB Networks SLPs per year 2015–2025 | validation | 16 | 2022 on disk only |
| Climate Action Plan targets | projection trajectory | 11 | |
| CSO/ESRI projections; Cork CDP targets | growth projection | 9 | |
| Met Éireann storm warning register | warning status | 2 | storms already derive from observed wind; this adds only the red-warning flag |
| Published NILM benchmarks (REDD, UK-DALE, REFIT) | NILM error model (D-120) | 18 | |

## Dropped, with reason

| source | reason |
|---|---|
| **CER Smart Metering trial (ISSDA)** | **Licensed and restricted; the brief forbids it** (`sources/SOURCES.md:25`, and it is listed as deliberately not used). D-100. Validation uses ESB SLPs, EirGrid and CSO instead. |
| **ERA5 reanalysis** | **Not needed.** Met Éireann covers 1955/1962 → 2026 at hourly resolution, and irradiance is derived from observed cloud and sunshine. |
| **GAA and televised fixture lists** | **No open-data source exists.** `sport` already carries **A-43**: "'sport' matches 115 tables, none of them a fixture list or an attendance series — the matches are road freight TRANSPORT". Tabled as A-numbered declared assumptions with the failed search recorded. |
| **PARA//EL enrolment series** | **Cannot exist** — a programme fact, not a statistic. A-numbered per D-111 (1 Jan 2021 → 30% by 30 Sep 2026), with the reason recorded rather than a failed search. |

---

# PxStat matrix codes resolved (2026-10-14)

Resolved via the **JSON-RPC** endpoint — `POST https://ws.cso.ie/public/api.jsonrpc`
with `method: PxStat.Data.Cube_API.ReadCollection` — which returns the full
catalogue (**13,111 tables**, 24.4 MB). The RESTful `ReadDataset` path the
registry already uses then fetches each table as JSON-stat. Both verified.

| need | code | label | years | verified |
|---|---|---|---|---|
| **New dwelling completions by LEA** (D-114) | **`NDA05`** | New Dwelling Completions by Local Electoral Area | **2012–2025** | **Yes — "Cobh, Cork County" is its own LEA**, one of 167. This is exactly the geography D-114 needs |
| same, quarterly | `NDQ09` | New Dwelling Completions by Local Electoral Area | quarterly | for finer phasing if annual proves too coarse |
| **SILC energy deprivation, current** (D-118, Phase 16) | **`SIH01`**, **`SIA131`** | Type of Deprivation Item Experienced | **2020–2025** | **Yes — both carry "Unable to afford to keep the home adequately warm"**, the exact measure D-118 names, plus "Without heating at some stage in the last year" |
| SILC energy deprivation, historical | `SIA26` | Persons Experiencing Deprivation | **2006–2019** | Yes — carries "Without heating at some stage in the last year" |
| SILC income distribution | `SIA43`, `SIA37`, `SIA38` | Net Disposable Equivalised Income Distribution | to confirm | candidates for Phase 10 |
| SILC income by composition | `SIA123`, `SIA124`, `SIA21` | Composition of Average Net Equivalised / Household Income | to confirm | candidates for Phase 10 |
| Deaths registered | `VSD51`, `VSD54` | Deaths Registered | to confirm | |
| Deaths registered, provisional | `VSAQ3`, `VSBQ1`, `VSBQ2` | Deaths Registered Provisional | to confirm | the nearest thing to a weekly series found |
| Working from home | `F7137`, `F7140`, `F7141` | Population Aged 15+ at Work by Days Working from Home | census-based | `SAP2022T11T4SA` gives it at small-area level |
| EV uptake | `TEA05`, `TEA16`, `TEA18` | Private Cars Licensed for the First Time | to confirm | need the fuel-type breakdown |
| Heating fuel type | `G0701`, `G0702` | SDG 7.1.2 Type of central heating fuel | | for the oil and solid-fuel decline in scope G |
| Additional heating used | `HEBEU07`–`HEBEU12` | Additional heating used to heat homes | | secondary heating, relevant to "fewer rooms heated" in Phase 13 |

## Three findings that change the plan

**1. The 2015–2025 SILC deprivation target needs a documented splice.** `SIH01`
and `SIA131` begin at **2020**; the historical indicator lives in the `SIA26`
family, which ends at **2019**. SILC was restructured between them, so the
series is **two generations, not one**. Phase 16 must report it as a spliced
series with the break at 2020 named, and **must not present it as continuous**.
The 2022 rise itself falls safely inside the current generation, so the headline
test is unaffected.

**2. `SIA46` is the wrong table and was my first guess.** "Summary of
Deprivation Indicators" stops at **2019** and carries only a count of
deprivation items, not the per-indicator breakdown. Recorded so nobody repeats
the mistake.

**3. Heating oil price is not in PxStat under any obvious name.** No hits for
"heating oil", "fuel price" or "consumer price index detailed". It is most
likely inside the CPI sub-indices under a code that does not say "oil", or it
sits with SEAI rather than CSO. **Unresolved — carried into the Phase 13
acquisition list rather than assumed available.**

---

# Census 2016 base — ACQUIRED (2026-10-14)

| file | bytes | sha256 | note |
|---|---|---|---|
| `sources/cso_census2016/SAPS2016_SA2017.csv` | 38,436,471 | `a951dfe8d5429346…` | **18,641 small areas, 802 columns** |
| `sources/cso_census2016/SAPS_2016_Glossary.xlsx` | 39,088 | `4764547e47ddcc04…` | column descriptions; the headers are not self-describing |
| `sources/osi_boundaries/Small_Areas_Generalised_20m_2015.geojson` | 45,844,868 | `0386592386c59cd6…` | **18,641 polygons**, WGS84, matching the SAPS row count exactly |

Licence: **CC BY 4.0** as you stated. The CSO page links its Copyright and
Re-use Policy rather than printing a licence inline, so each manifest records
this as **to confirm against that policy page** before any release
redistributes the bytes.

**Geography reconciles completely, and this is the fast path's main risk
retired.** 47 of the town's 53 small areas match `GEOGID` directly. The 6 that
do not are all **2022 split or merge codes** — `047106006/01`, `047106006/02`,
`047106028/01`, `047106028/02/047106004`, `047107021/01`, `047107021/02` — and
**every one of their 2017 parents is present** (`047106006`, `047106028`,
`047107021`, `047106004`). So Phase 4's boundary reconciliation is a named
mapping of 6 areas to 4 parents, not an open problem.

The boundary file confirms the geography independently: the matched areas sit in
electoral divisions **"Cobh Rural"** and **"Cobh Urban"**, Cork County.

**Two cautions on the boundary file.** `GEOGDESC` in the SAPS CSV is the literal
string `"Small Area"` for every row — there are **no place names in it at all**,
which is why a search for "Cobh" returns nothing and why the boundary file is
required to identify the town. And the `AREA` field is **0 for every feature**;
only `SHAPE_Area` is populated, in **square degrees**, so any real area or
density figure must be computed from the geometry in a projected CRS. That bears
directly on I-107 and D-104: small-area polygons are now on disk for the first
time, but dwelling-level positions still are not.

---

# A-43 partially reversed: GAA inter-county finals (2026-10-14)

`sources/gaa/all_ireland_finals_2015_2026.csv` — 24 rows (12 years × 2 codes),
22 with dates. **Club fixtures stay dropped**: no open-data fixture list exists,
which is what A-43 originally recorded.

**Status: PROVISIONAL, 0 of 24 rows verified.** The dates and scores come from
**aggregated web-search summaries, not per-final match reports**, so every row
carries `verified=no` and the manifest says so. They are an index to be checked,
not a source of record.

**Five rows need care before use**, and one is a caught error:

| row | problem |
|---|---|
| 2021 football | **scores come back identical to 2020** (2-14 to 0-15) — almost certainly a summary artefact. Caught before it entered the data |
| 2016 football | **replay**: drawn 18 Sep, replay 1 Oct. **Both are load events**; only the replay is in the row |
| 2019 football | **also a replay**; the drawn and replay dates were reported ambiguously |
| 2015, 2025 football | scores not captured |
| 2026, both codes | **NOT ACQUIRED.** The 2026 championship concluded before today, so both finals exist and must be sourced |

**Cork contested three finals in the window — hurling 2021, 2024 and 2025, all
lost.** The 2024 final went to **extra time**, so its broadcast ran longer than
a normal final: a distinct load signature for a Cork town. **These three rows
are the verification priority.**

---

# Heating oil — RESOLVED (2026-10-14)

Last report said heating oil was not in PxStat under any name I could find.
Both halves are now acquired.

**PRIMARY — EU Weekly Oil Bulletin.** `sources/eu_oil_bulletin/`,
`Weekly_Oil_Bulletin_Prices_History.xlsx` (4,487,743 B, sha256
`03a95c7a42ab4dfc…`), European Commission DG Energy, all member states from
2005. Ireland heating gas oil, consumer price **with** taxes, is column
`IE_price_with_tax_heating_oil` on the "Prices with taxes" sheet, **EUR per
1000 L, weekly**. Extracted to `ie_heating_gas_oil_weekly.csv`:

* **597 weekly observations, 2014-12 → 2026-09, ZERO nulls.**
* **Peak 2022-03-14 at €1,643.3/1000 L** — two weeks after the invasion of
  Ukraine.
* **Trough 2020-05-11 at €468.1** — the COVID price collapse.
* A **3.5× range** across the window. The energy crisis in one series.

**CROSS-CHECK — CSO `CPM18`.** The CPI item breakdown is a *dimension*, not a
label, which is why no label search found it. `CPM18` carries **"Liquid fuels
(home heating oil)"** at position 103 of 234 items, monthly **2003-01 → 2025-12**.

**Agreement over the 132 common months 2015–2025:**

| measure | value |
|---|---|
| Pearson r, levels | **0.9949** |
| Spearman ρ, levels | **0.9928** |
| Pearson r, month-over-month changes | **0.9313** |

**But the peak months differ by three, and this matters.** The bulletin peaks
**2022-03** (€1,456/1000 L monthly mean); CPM18 peaks **2022-06** (index 141.5).
A three-month difference in *when* the price shock bites is material to a
behavioural response, so the bulletin is primary — it is weekly, it is an actual
price rather than a basket index, and it needs no smoothing. CPM18's role is to
confirm the shape, which at r = 0.9949 it does.

**One coverage note:** CPM18 ends 2025-12, so the replay's final nine months
(2026-01 → 2026-09) rest on the bulletin alone, with no independent check.

Still wanted, and added to `docs/SEAI_MANUAL_DOWNLOADS.md` §5: the **SEAI
Domestic Fuel Cost Comparison**, for the conversion to a common energy basis
(c/kWh) and the *relative* cost of oil against gas and electricity. Neither the
bulletin nor the CPI converts, and inventing the factor would be an assumption
where SEAI publishes the answer.

---

# SILC: the 2020 break is a SPLICE, not a series

**Rule, binding on every output:** the 2015–2025 energy-deprivation series is
**two table generations joined at a definitional break** and must be published
with the break marked. It is never to be drawn, described or exported as a
continuous series.

| segment | table | years | indicator |
|---|---|---|---|
| historical | **`SIA26`** | **2006–2019** | "Without heating at some stage in the last year" |
| current | **`SIH01`**, **`SIA131`** | **2020–2025** | "Unable to afford to keep the home adequately warm" **and** "Without heating at some stage in the last year" |

**Why it is a break and not a join.** SILC was restructured between the two
generations, the table families are different, and the indicator wording the
current generation uses for the measure D-118 names — "Unable to afford to keep
the home adequately warm" — **is not available in the historical segment at
all**. So the series changes both its source and, for the primary measure, its
question.

**How it is reported:**

* a `series_segment` column on every row, valued `SIA26_2006_2019` or
  `SIH01_2020_2025`;
* **no interpolation, smoothing or rebasing across 2020** — if a chart spans the
  break, the break is drawn;
* any statement about change over the full window states that it crosses a
  definitional break;
* **the 2022 rise, which is Phase 16's actual validation target, falls entirely
  inside the current segment** — so the headline test never crosses the break
  and is unaffected.

`SIA46` remains recorded as the wrong table: 2019 cutoff, counts of items only,
no per-indicator breakdown.

---

# Small-area areas computed in ITM (EPSG:2157)

`v1/evidence/small_area_areas_itm2157.csv` — 53 rows, **47 with areas** (the 6
unmatched are the 2022 split/merge codes).

Implemented **directly**: no `pyproj`, `shapely` or `geopandas` is installed and
none was added. EPSG:2157 forward Transverse Mercator on GRS80 —
lat₀ 53.5°N, lon₀ 8°W, k₀ 0.999820, false origin 600000/750000 — then a
shoelace area per ring.

**Validated against an independent algorithm** rather than trusted: the same
polygons were also measured by spherical excess on the authalic sphere. The two
agree to **0.3476%**, which is within the authalic approximation's own error, so
the projection is sound.

| | |
|---|---|
| **Town footprint, 47 small areas** | **9.405 km²** |
| Cobh Urban | 2.082 km² |
| Cobh Rural | 7.323 km² |
| Median small area | **6.2 ha** |
| Largest | 516.7 ha (`047106026/047106029`, rural) |

**This is the first real geometry the project has had, and it sizes Abbeylands.**
An 8–10 ha site is **roughly one to one and a half median small areas**, and
about **1% of the town's total footprint**. Previously unobtainable: the
boundary file's own `AREA` field is **0 for every feature**, only `SHAPE_Area`
is populated and it is in square degrees, and nothing in D01 had a coordinate.
This does **not** change D-104 — there are still no dwelling-level positions, so
Abbeylands stays abstract — but it removes the excuse for guessing the town's
scale.

---

# GAA finals — verified 4 of 26 (2026-10-14)

26 rows (24 finals + 2 drawn games), **all 26 dated**, **4 verified against
match reports**. Club fixtures remain dropped.

**Verified, Cork first as instructed:**

| year | code | result | attendance | referee | source |
|---|---|---|---|---|---|
| 2021 | hurling | Limerick 3-32 **Cork** 1-22 | 40,000 | Fergal Horgan | RTÉ match report |
| 2024 | hurling | Clare 3-29 **Cork** 1-34 **AET** (normal time 3-21 to 1-27) | 82,300 | Johnny Murphy | RTÉ match report |
| 2025 | hurling | Tipperary 3-27 **Cork** 1-18 | 82,331 | Liam Gordon | **GAA.ie official report** |
| 2021 | football | Tyrone 2-14 Mayo 0-15 | 41,150 | Joe McQuillan | RTÉ match report |

**My 2021 football flag was wrong, and I am withdrawing it.** I flagged the
score as a probable search-summary artefact because it was identical to 2020's
2-14 to 0-15. Verification against three match reports shows **the score is
correct**: both the 2020 and 2021 finals genuinely finished 2-14 to 0-15, with
Mayo losing both on 0-15. A real coincidence, not an error. The process was
right — flag the anomaly, then check it — but the suspicion was unfounded.

**Replays are now separate rows**, because both dates are load events:

* 2016 football — drawn **18 Sep**, replay **1 Oct**
* 2019 football — drawn **1 Sep**, replay **14 Sep** (dates still unverified)

**2026 is now sourced**: hurling **19 Jul, Limerick 1-29 Galway 1-18**;
football **26 Jul, Mayo 1-20 Kerry 1-17 — Mayo's first title in 75 years**. A
GAA.ie report exists for the football and is cited, but was not fetched, so the
row stays `verified=no`.

**Remaining: 22 rows carry Wikipedia as an index only**, and 2015 football,
2025 football and the 2019 replay still lack scores.
