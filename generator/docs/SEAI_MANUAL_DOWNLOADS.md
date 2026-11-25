# SEAI files needed — manual download list

**Why manual:** `seai.ie` returns **403** to a programmatic fetch, and the
instruction is **not to spoof a user agent**. So these are for you to download
in a browser and drop into `sources/seai/`. I will then hash each one, write its
manifest and add it to `docs/G0_SOURCE_MANIFEST.md`.

**Provenance of each URL is marked.** `[found]` means the URL appeared in a
search result and I have not been able to verify it resolves (403 blocks me).
`[page]` means I have the landing page but not the file URL, so the exact file
name is for you to read off the page. **No URL below is guessed silently.**

**Licence:** to be confirmed per file on download — SEAI publications do not
carry a uniform licence, and several of the project's existing SEAI entries
record "re-use terms not stated on the publication page". Please note what each
page says.

---

## 1. Grant and upgrade counts by year — for Phase 11 (scope M)

Needed: yearly counts 2015–2026 of **insulation, windows, heat pumps, solar PV**
and **deep retrofit**, by scheme, so uptake can be calibrated to the national
series (Rule 11: the sourced series decides *how many*).

| # | file | URL | provenance | for |
|---|---|---|---|---|
| 1.1 | National Retrofit Plan **Full Year Report 2024** | `https://www.seai.ie/sites/default/files/publications/SEAI-Retrofit-Full-Year-Report-2024.pdf` | **[found]** | per-scheme counts; the 2024 report is stated to break out 2019–2024 |
| 1.2 | National Retrofit Plan **Full Year Report 2023** | `https://www.seai.ie/sites/default/files/publications/SEAI-Retrofit-Full-Year-Report-2023.pdf` | **[found]** | cross-check against 1.1 |
| 1.3 | National Retrofit Plan **Full Year Report 2025** | — | **[page]** — look under news/publications; I could not confirm it is published | extends the series to 2025 |
| 1.4 | Retrofit **Quarterly** Progress Reports (Q1 2023, Q3 2023 at least) | `https://www.seai.ie/sites/default/files/publications/SEAI-Retrofit-Quarterly-Report-Q1-2023.pdf` and `…-Q3-2023.pdf` | **[found]** | quarterly granularity if the annual reports prove too coarse |

**The important gap: 2015–2018.** The Full Year Reports begin at 2019. A search
result states SEAI publishes "full datasets and analysis for all schemes from
2015 onwards", which would cover it, but **I have not found that download page**.
Two places to look, and this is the one item I most need from you:

| # | what | where | for |
|---|---|---|---|
| 1.5 | Scheme datasets **2015 onwards** (Better Energy Homes, Warmer Homes, Solar PV, Community Energy Grants) | SEAI **Data and Insights → SEAI Statistics** section | the 2015–2018 half of the uptake series |
| 1.6 | SEAI **Annual Reports 2015–2018** if 1.5 does not exist | e.g. `https://www.seai.ie/sites/default/files/publications/SEAI-Annual-Report-2013.pdf` shows the pattern **[found]** — substitute 2015…2018 | fallback for pre-2019 counts |

---

## 2. Residential energy statistics — Phases 11 and 16

| # | file | URL | provenance | for |
|---|---|---|---|---|
| 2.1 | **Energy in the Residential Sector** (latest, plus any earlier editions) | page: `https://www.seai.ie/data-and-insights/seai-statistics/key-publications/energy-in-residential-sector` | **[page, found]** | national residential energy by fuel and year — the oil and solid-fuel decline in scope G, and a cross-check on bills |

---

## 3. Behaviour and comfort — Phases 13 and 16

| # | file | URL | provenance | for |
|---|---|---|---|---|
| 3.1 | **Promoting retrofitting among homeowners in Ireland through a behavioural lens** | `https://www.seai.ie/sites/default/files/publications/Promoting-retrofitting-among-homeowners-in-Ireland-through-a-behavioural-lens.pdf` | **[found]** | adoption propensity (Phase 11) and the behavioural response (Phase 13) |
| 3.2 | Anything SEAI publishes on **comfort taking** / post-retrofit indoor temperature | page: SEAI blog + publications; a blog item exists at `https://www.seai.ie/blog/most-powerful-reason-upgrade-your-home-it-will-be-warmer-and-more-comfortable` **[found]** | **Phase 16's retrofit comfort-improvement validation target.** This matters more than it looks: the model already has a `comfort_taking` module and an `ablation_u22.json` artefact, so a sourced magnitude would replace an assumption that is already load-bearing |
| 3.3 | **Domestic Technical Standards and Specifications v4.0 (2026)** | `https://www.seai.ie/sites/default/files/publications/Domestic-Technical-Standards-and-Specifications.pdf` | **[found]** | what a grant-funded measure actually comprises — the measure mix for pre-occupancy renovation (Phase 7) and retrofit (Phase 11) |

---

## 4. Heating-response elasticity — Phase 13 corroboration only

**Not blocking.** D-117/D18 is already answered from a non-SEAI source: ESRI
Working Paper 824 (Wade, Carthy & Farrell, 19 March 2026), short-run elasticity
**−0.19 to −0.33** from population microdata covering all Irish residential gas
consumers 2018–2023. Acquired, hashed and manifested.

What SEAI could still add, and why it is worth a look:

| # | what | for |
|---|---|---|
| 4.1 | Any SEAI/CSO study of **setpoint, heating-hours or rooms-heated** change during 2022–23 | WP824 gives a **consumption** elasticity, not a setpoint response. Phase 13 needs the setpoint→consumption translation, and WP824 does not supply it. A sourced setpoint change would close the one remaining gap in the crisis layer |
| 4.2 | Anything on **persistence** after the crisis eased | WP824 estimates **no** long-run elasticity — "our analysis sits squarely within the short-run elasticity literature" — so on present evidence D-113 resolves to **no persistence**. A SEAI longitudinal study would change that |

---

## What I will do when the files land

1. `shasum -a 256` each file; record bytes.
2. Write a `*.manifest.json` beside it in the project's existing idiom — key,
   title, publisher, URL, fetched date, bytes, sha256, licence as the page
   states it, intended use, and model-development exposure.
3. Register it so `baile_nua.sources.require` re-hashes it on every use and
   refuses it if the bytes change.
4. Add it to `docs/G0_SOURCE_MANIFEST.md` and move it out of "to acquire".
5. For anything whose licence forbids redistribution, record it as
   **cited, not redistributed**, and exclude it from any B2 upload under R.

---

## 5. Domestic Fuel Cost Comparison — Phase 13 (added 2026-10-14)

| # | what | where | for |
|---|---|---|---|
| 5.1 | **SEAI Domestic Fuel Cost Comparison** (the archive of editions, not just the current one) | page: SEAI **Data and Insights → SEAI Statistics**; published periodically | A per-fuel cost comparison on a common energy basis (c/kWh), which is what Phase 13 needs to put **heating oil, gas, electricity and solid fuel on one axis**. The EU Oil Bulletin gives oil in EUR/1000 L and the CSO gives an index; neither converts to c/kWh, and inventing the conversion would be an assumption where SEAI publishes the answer |

**Why this is wanted even though heating oil is now sourced.** D18's oil price is
settled — the EU Weekly Oil Bulletin is acquired (597 weekly observations,
2014-12 to 2026-09, zero nulls) and cross-checks against CSO CPM18 at
**r = 0.9949**. What is still missing is the **conversion to a common energy
basis** and the **relative** cost of oil against gas and electricity, which is
what drives a household's fuel-switching and heating decisions. The
Domestic Fuel Cost Comparison is SEAI's own published answer to that, and using
it avoids an A-numbered conversion factor.

---

## Fallback if 1.5 does not exist (D-123, recorded 2026-10-14)

If there is no scheme-level dataset for **2015–2018**, the fallback is **SEAI
annual report totals by scheme and year**, with that segment **flagged on the
dataset as coarser** than 2019–2026 — a declared granularity break at 2019.

What this costs: Phase 11 needs a **count per scheme per year** to hold the
national total exactly under Rule 11, and an annual report total still gives
that, so the ranked allocation is unaffected. What is lost is the **measure mix
within each scheme** for those four years, which becomes an A-numbered split
carried back from the earliest year where the mix is published.

**G0 is held until these downloads land.**
