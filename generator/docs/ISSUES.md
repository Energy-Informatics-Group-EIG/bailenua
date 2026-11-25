# Baile Nua / HRSD_Occupants — ISSUES

**UNVALIDATED SIMULATION EVIDENCE: E1 engineering candidate**

Register of blockers, design contradictions, unreachable sources, and required MIMIC
changes. Nothing here is silently reinterpreted or silently fixed in MIMIC.

Status values: `OPEN`, `MITIGATED`, `CLOSED`, `BLOCKED`, `REPORT-TO-MIMIC`.

| ID | Raised | Area | Severity | Status | Summary |
| --- | --- | --- | --- | --- | --- |
| I-001 | 2026-10-08 | MIMIC / safety | **Critical** | MITIGATED | `config/local.php` points at the production Blacknight DB and is preferred over env vars; a naive `docker compose up` would write synthetic participants to production. |
| I-002 | 2026-10-08 | MIMIC / security | High | REPORT-TO-MIMIC | Live production DB credentials and researcher token sit in plaintext on disk in the repo working tree. |
| I-003 | 2026-10-08 | MIMIC / defect | Medium | REPORT-TO-MIMIC | `mimic_sd_generator.php` age-band hyphen vs en-dash: the education adjustment never fires for 55–64. |
| I-004 | 2026-10-08 | Brief / design | Medium | CLOSED | Brief referenced `docs/Baile_Nua_Technical_Design_Review_r3.md` and `<MIMIC_PATH>`; neither existed as given. |
| I-005 | 2026-10-08 | Hardware / U21 | High | OPEN | The named execution machine is far below the U21 minimum. |
| I-006 | 2026-10-08 | MIMIC / API | High | OPEN | MIMIC rate limits + PHP-session-per-participant make 10,000 unique participants through the public API costly; U19 "test-mode allowance" does not exist in code. |
| I-007 | 2026-10-08 | Design / contradiction | Low | OPEN | E1 asks for "at least 10,000 unique participants" but Baile Nua has ~140 people in the E1 estate; the number can only come from the U16 extended pool. |
| I-008 | 2026-10-08 | Data / U04 | **High** | MITIGATED | Eurostat HETUS contains **no Irish data in any wave**, so U04's "Irish recalibration" of HETUS has no Irish anchor inside HETUS. |
| I-009 | 2026-10-08 | Data / source | Low | CLOSED | Met Éireann's historical-data host moved from `cli.fusio.net` to `clidata.met.ie`; the design's and the old documented URLs are dead. |
| I-010 | 2026-10-08 | Data / SAPS | Medium | CLOSED | The CSO SAPS small-area file carries no place names, so "the small areas of Cobh" cannot be selected from SAPS alone. |
| I-011 | 2026-10-08 | Data / SAPS | Medium | **CLOSED** | SAPS 2022 publishes no detached / semi-detached / terraced split and cannot distinguish a heat pump from direct electric heating. Closed with CSO EBA02/EBQ02 BER data for Co. Cork. |
| I-012 | 2026-10-08 | Design / R03 | Medium | MITIGATED | R03's "~3,000 people" and "1,000 to 1,100 homes" are jointly satisfiable at Cobh's real household size only over a narrow window; the obvious 3,000-person anchor falls outside it. |
| I-013 | 2026-10-08 | Design / U03 | Medium | OPEN | The measured U03 comparison recommends **proportional scaling**, contradicting the design's own recommendation of whole-area stratified sampling. |
| I-014 | 2026-10-08 | Data / names | Low | MITIGATED | No public Irish surname frequency table, and no national given-name lists for non-Irish origins, were found. |
| I-015 | 2026-10-08 | Data / R27 | Low | MITIGATED | No authoritative machine-readable public-figure register for Ireland was found; the committed list is partial. |
| I-016 | 2026-10-08 | Thresholds / U11 | **Medium** | OPEN | The Day-1 provisional threshold `saps_marginal_z_abs_max: 2.0` was mis-specified and has been replaced by a simultaneous band. **Brian's ruling needed.** |
| I-017 | 2026-10-08 | Data / weather | **High** | CLOSED | Met Éireann station 1575 is **Malin Head, Co. Donegal**, not Roches Point. Roches Point is station **1075**. |
| I-018 | 2026-10-08 | Data / CSO API | Low | CLOSED | The CSO PxStat API returns a bare `403 Forbidden` for a CSV request that exceeds its cell cap, with no indication of the real reason. |
| I-019 | 2026-10-08 | Physics / [A] | Medium | OPEN | Four physics input sets are declared assumptions not read back from their source documents in this run: BER band boundaries, Part L U-values, thermal mass parameters, and floor area per room. |
| I-020 | 2026-10-08 | Validation / U11 | **Medium** | OPEN | The design's Day-2 negative control ("marginals shifted 10%") is **below the detection resolution** of the R04 acceptance band at the Baile Nua town size. Reported as NOT_DETECTED, with the threshold measured. |
| I-021 | 2026-10-08 | MIMIC / defect | **High** | REPORT-TO-MIMIC | Both MIMIC migrations use **MariaDB-only syntax** and fail on MySQL 8.0, which MIMIC's own docker-compose pins. Migration 002 is the **ADR-004 GDPR Article 9 compliance** migration. |
| I-022 | 2026-10-08 | MIMIC / exposure | Medium | MITIGATED | MIMIC's `docker-compose.yml` publishes MySQL on `3306:3306` and the web app on `8080:80` — **all interfaces**, not loopback. |
| I-023 | 2026-10-08 | MIMIC / defect | **High** | REPORT-TO-MIMIC | `includes/Rng.php` overflows PHP's 64-bit integer into a float, so the "deterministic mulberry32" RNG silently loses precision — and the resulting PHP notice corrupts the JSON of `api/session.php`. |
| I-024 | 2026-10-08 | MIMIC / API gap | Low | MITIGATED | `api/session.php` does not return `context_key`, though ADR-006 persists it on `session_items`. An API-only consumer must parse it from the scenario id. |
| I-025 | 2026-10-08 | Design contradiction | **Critical** | MITIGATED | **U17 and U19 are incompatible with MIMIC as it stands.** The synthetic marker cannot be set through the public API, so the purge and the synthetic banner would both have missed all 10,000 participants. |
| I-026 | 2026-10-08 | MIMIC / sandbox | Medium | CLOSED | PHP OPcache delays a config change by up to 2 s, so a batch started immediately after switching the pool marker tagged its participants with the **previous** pool's code. |
| I-087 | 2026-10-12 | MIMIC / API gap | Medium | REPORT-TO-MIMIC | `JourneyService::state` returns `summary` once a participant has one completed session, and `api/session.php` refuses `action=create` unless the next step is `decide`, so **the public API permits exactly one session per participant** and a panel wave cannot reuse a participant id. |
| I-090 | 2026-10-12 | Provenance / D23 | **High** | OPEN | Model code was committed **while both finished runs were in flight**, so neither run's code state is recoverable even from the freeze tag; D23 records the reconstruction and the files that differ. |
| I-091 | 2026-10-12 | Export / referential | **High** | OPEN | The written D09 and the written D05 share **no person**: D09 is the town's ten-year life course, D05/D06/D08 are the estate slice. Every D21 biography's life-event section is therefore empty. |
| I-092 | 2026-10-12 | Export / defect | Medium | CLOSED | `export/context.py` imported the engine before the source registry, so any export that needed the slice FIRST died with "source is not declared" about a source that is declared. |
| I-093 | 2026-10-12 | Sweep / coverage | Low | OPEN | `export/structural.py` carries two assumption-flag references that no sweep entry names, so `test_every_a_flag_in_the_tree_is_accounted_for` FAILS. Pre-existing, from the merged export layer. |
| I-094 | 2026-10-12 | Data / D27 vintage | Medium | OPEN | D27's three-band plan is sourced from a **November 2024** schedule because no three-band domestic plan was published in May 2022, so one of three plans carries price levels four years out of step with the simulated year. |
| I-095 | 2026-10-12 | Model / D08 | Medium | OPEN | D21 surfaced two internal inconsistencies in D08 that no aggregate check would notice: `caring_load` = `child` with `caring_hours_week` = 0, and `vehicle_access` = `none` in income quintile 5. |
| I-096 | 2026-10-12 | MIMIC / scaling | **High** | REPORT-TO-MIMIC | `api/dashboard.php` returns **504 at 23,456 participant rows**. The cause is the LEGACY `DashboardAnalytics::bundle()`, which every request runs whatever `?fresh` is, and which is CPU-bound in PHP (web container 100%, MySQL 0.9%) for over 1,000 s against nginx's 600 s `fastcgi_read_timeout`. |

---

## I-001 — MIMIC local instance would write to PRODUCTION (Critical)

**Found:** 2026-10-08, before any MIMIC call was made.

**Evidence.** `/Users/brianoregan/Documents/GitHub/mimic/web/mimic/config/database.php`
returns `config/local.php` **in preference to** the `MIMIC_DB_*` environment variables:

```php
$localPath = __DIR__ . '/local.php';
if (is_readable($localPath)) { $local = require $localPath; return [ ... ]; }
return [ 'host' => getenv('MIMIC_DB_HOST') ?: '127.0.0.1', ... ];
```

`config/local.php` is present on disk and contains:

```
host  mysql4464int.cp.blacknight.com      (production, remote)
name  db1379071_mimic1x
```

`docker-compose.yml` bind-mounts the working tree read-write
(`- ./web:/var/www/html:rw`) and sets `MIMIC_DB_HOST: mysql`. Because `local.php`
wins, the `MIMIC_DB_HOST` env var is **ignored** and every API call from the
container would reach the production database over the network.

The brief states: *"Never call any remote or production MIMIC."* A `docker compose up`
in the MIMIC repo as it stands would have violated that on the first request.

**Mitigation taken (no edit to the MIMIC repo).** The local instance runs from an
isolated copy at `work/mimic_local/`, created by `scripts/baile_nua/mimic/provision.py`.
The copy's `config/local.php` is replaced with a loopback-only config, and the
compose project is renamed so it cannot share volumes with the original. A
pre-flight assertion (`mimic.provision.assert_local_only`) resolves the configured DB
host and refuses to run if it is not the local container or loopback; the MIMIC
runner calls it before every batch. The original repo is left untouched and is
never used as the compose context.

**Required MIMIC change (not made here).** `config/database.php` should prefer
explicit environment variables over `local.php`, or `local.php` should be keyed by
environment, so that a containerised run cannot silently reach production.

---

## I-002 — Production credentials in plaintext in the working tree (High)

`web/mimic/config/local.php` holds the production DB user, password and the
researcher API token in plaintext. The file is `.gitignore`d and is **not** tracked
(verified with `git ls-files --error-unmatch`), so the credentials are not in git
history, but they are readable by any process running as this user and are copied by
any backup of the repo. Reported, not altered.

**Recommendation for the MIMIC team:** move to environment injection or a secret
store, and rotate the credentials, since they have been exposed on a developer
workstation.

---

## I-003 — `mimic_sd_generator.php` age-band separator defect (Medium)

Known before this run and confirmed in code. The education adjustment compares the
age band against `'55-64'` (ASCII hyphen) while the bands are defined with
`'55–64'` (en-dash, U+2013), so the branch is dead for 55–64-year-olds. Not fixed
here: the brief requires it be reported to the MIMIC team, not patched. The HRSD
conformance test T1 includes a check of this class of error.

---

## I-004 — Brief paths did not resolve (Medium, closed)

The brief named two paths that did not exist as given:

1. `docs/Baile_Nua_Technical_Design_Review_r3.md` — the design document was at the
   project root as `Baile Nua Technical Design Review.md` (+ `.pdf`). It is
   revision 3, architecture frozen 8 October 2026, so it is the binding document.
   Resolved by copying it to the expected path; the originals are preserved
   unmodified under `docs/source_pdf/`.
2. `<MIMIC_PATH>` — an unsubstituted placeholder. Resolved by locating the MIMIC
   working tree at `/Users/brianoregan/Documents/GitHub/mimic` (confirmed by the
   presence of `web/mimic/mimic_sd_generator.php`, `database/schema.sql` at
   schema_version 1.1, and `api/{session,response,consent}.php`). Recorded in
   `docs/DECISIONS.md` as D-002.

---

## I-005 — Execution machine is below the U21 minimum (High)

U21 and the E0 approval table set a minimum of 32–64 cores, 128–256 GB RAM and
2–4 TB NVMe. The brief's E0 decision was "run on this Mac" and to report on Day 6
whether the full town fits. Measured target:

| Item | U21 minimum | This machine | Ratio |
| --- | --- | --- | --- |
| Logical cores | 32–64 | 12 | 0.19–0.38× |
| Physical cores | — | 6 | — |
| RAM | 128–256 GB | 32 GB | 0.13–0.25× |
| Free disk | 2–4 TB | ~89 GB free of 932 GB (91% full) | ~0.02–0.04× |
| Arch | — | x86_64, macOS 15.7.9 | — |

This does not block E1 (the 50-home slice). It is recorded now because the Day 6
benchmark decides E2, and because free disk is the binding constraint rather than
CPU: the design's own estimate for full-town ground truth is "tens of GB without
1-min physics state; a few hundred GB with it", against ~89 GB free. U07's
recommendation (b) (daily checkpoints plus re-run, no stored 1-min building state)
is therefore not merely preferred here but required. Quantified on Day 6.

---

## I-006 — No test-mode rate-limit allowance exists in MIMIC (High)

U19 chose "(a) real-time API calls with a test-mode allowance" for the HRSD runner.
No such allowance exists in the code. `mimic_rate_limit()` in `bootstrap.php` is
IP-keyed with fixed limits: consent 60/60 s, profile 60/60 s, session 120/60 s,
response 180/60 s. One unique participant requires at minimum 1 consent + 1 profile
+ 1 MCV + 1 session create + 13 responses. Consent at 60/min caps the run at
3,600 participants/hour, so 10,000 unique participants cannot be created in under
~2.8 hours of wall clock on the consent bucket alone, and the response bucket
(180/min against ~130,000 responses) is the harder limit at ~12 hours.

Additionally, `api/consent.php` stores the participant id in the **PHP session**
(`mimic_set_participant`), and `session.php`/`response.php` read the actor from that
session, so the runner must hold one cookie jar per participant and cannot batch.

**Mitigation taken.** The limiter is file-backed under `sys_get_temp_dir()/mimic_rate`
and keyed by bucket+IP. For the local instance only, the runner is given a
test-mode allowance by configuration of the *local copy* (not the MIMIC repo):
`MIMIC_TESTMODE_RATE=1` in the local container environment, with the allowance
implemented in the local copy's bootstrap and recorded here as a required MIMIC
change. This is what U19 asked for; it is applied to the sandbox copy only, and the
production path is untouched.

**Required MIMIC change (not made in the MIMIC repo):** an explicit, documented
test-mode allowance — for example a configured allow-list of loopback source
addresses, or a signed test token that raises the bucket limits — so that
conformance runs do not require editing the limiter.

---

## I-007 — 10,000 unique participants cannot come from the E1 estate (Low)

E1 scope is 50 homes / ~140 people, of whom roughly 100 are adults. The E1 criterion
"MIMIC T1, T9 and T10 pass with at least 10,000 unique participants (5.14 counters)"
is therefore satisfiable only through the U16 **extended pool** (unlinked), which
5.14 defines as "the same person generator, without the time simulation", drawing on
full-size Cobh, other Irish small areas and the EU-27. This is consistent with the
approved U16 decision (both pools, 10,000 counted as unique participants) and with
the requirement to keep the five counters separate: the E1 report states the linked
panel count (small, from the estate) and the unlinked pool count (the bulk)
separately and never merges them. Recorded so that the E1 report is not read as a
claim that 10,000 simulated townspeople exist.


---

## I-008 — Eurostat HETUS has no Irish data in any wave (High)

**Found:** 2026-10-08, by inspecting the retrieved data rather than the catalogue
description.

E0-2 approved U04 as: *"No Irish time-use microdata yet. Use public aggregates
(Eurostat HETUS tables) with Irish recalibration where possible."* That wording
presumes HETUS has an Irish row to recalibrate. It does not.

Measured country coverage, read from the downloaded files:

| HETUS wave | Dataset prefix | Countries | Ireland? | UK? |
| --- | --- | --- | --- | --- |
| 2020 | `tus_20*` | 11: AT BG DE EE FI HR HU NL NO PL RS | **No** | **No** |
| 2000 / 2010 | `tus_00*` | 22: AT BE BG DE EE EL ES FI FR HU IT LT LU LV NL NO PL RO RS SI TR UK | **No** | Yes |

So there is no Irish time-use aggregate in HETUS at all, and the 2020 wave has
lost the UK as well. This is stronger than risk K02 states ("No *recent* Irish
time-use diary microdata available"): there is no Irish HETUS figure of any
vintage.

**Mitigation taken.** Two parts, neither of which claims Irish calibration.

1. **Structural donor: HETUS 2000/2010, `geo='UK'`.** The design itself names
   the fallback as "HETUS/UK TUS with Irish recalibration" (U04 option b), and
   the UK is the nearest neighbour on language, working week, school calendar and
   climate. Five tables are used: `tus_00age` (age and sex), `tus_00week` (day
   type), `tus_00selfstat` (labour status), `tus_00hhstatus` (household
   composition) and `tus_00startime` (diurnal participation, which constrains
   *when* rather than only *how long*).
2. **Irish anchoring from real Irish data for this town.** Census 2022 SAPS for
   Cobh's own 53 small areas carries Theme 11: means of travel to work, school or
   college (T11_1), **time leaving home** (T11_2), **journey time** (T11_3) and
   **working from home** (T11_4). These anchor the departure and return times,
   the commute durations and the remote-work share — the parts of the daily
   schedule that most affect occupancy and load — against Irish, Cobh-specific,
   public data. The activity *durations* stay UK-donor.

**Consequence for claims.** The activity engine is flagged
**VERIFIED, NOT CALIBRATED** throughout, per E0-2, and the E1 report states that
the donor is UK and that no Irish time-use evidence exists. D24
`calibration_targets` records `geo='UK'` and the `[A]` flag on every activity
target, so no later analysis can mistake it for Irish calibration. Risk K02's
severity should be raised at the E1 review: its mitigation named "Irish
calibration on CER occupancy proxies", and CER is forbidden to this build.

---

## I-009 — Met Éireann historical-data host moved (Low, closed)

`cli.fusio.net`, the host in the design's S01 row and in Met Éireann's older
documentation, no longer resolves (connection failure, not a 404). The current
host is `clidata.met.ie`, confirmed by the iframe on
`https://www.met.ie/climate/available-data/historical-data`:

| Station | Working URL | Bytes |
| --- | --- | --- |
| Roches Point (1575) | `https://clidata.met.ie/cli/climate_data/webdata/hly1575.zip` | 11,019,991 |
| Cork Airport (3904) | `https://clidata.met.ie/cli/climate_data/webdata/hly3904.zip` | 10,607,064 |

Both are now in the source register. Roches Point drives the true site series
(D15, GT) because it is the coastal station at the harbour mouth and matches
Cobh's exposure; Cork Airport is the observable station series (D31, OBS)
because design 6.4 item 7 wants the observable weather to come from the nearest
*official* station rather than the true site microclimate, and the
inland-and-elevated airport makes that gap physically real rather than injected
noise.

---

## I-010 — CSO SAPS small-area file has no place names (Medium, closed)

The SAPS small-area CSV's `GEOGDESC` column repeats the numeric small-area code
(`017001001`), so the small areas belonging to Cobh cannot be selected from the
SAPS file. Three routes were tried:

1. The Built-Up Area SAPS file *does* name Cobh (`GEOGID` 18746) but gives only
   the town aggregate, not its small areas.
2. The Electoral Division SAPS file names `COBH URBAN` and `COBH RURAL`, but its
   `GEOGID` is a GUID that does not appear in the small-area file, so it cannot
   be joined.
3. **Used:** the OSi / Tailte Éireann *CSO Small Areas, National Statistical
   Boundaries 2022, ungeneralised* layer carries `SA_URBAN_AREA_NAME`, which
   names the built-up area each small area belongs to, alongside `SA_PUB2022`.
   `SA_PUB2022` joins exactly to SAPS `GEOGID`.

Result: **Cobh is 53 small areas**, split `COBH URBAN` 29 / `COBH RURAL` 24.
Selecting by electoral division instead would have dropped 24 of the 53 — nearly
half the town — with no error anywhere. `saps.verify_join_keys()` now asserts
that all 53 OSi codes resolve to SAPS rows and fails the run otherwise, and the
same query yields the real NUTS3 code the MIMIC crosswalk needs (**IE053,
South-West**) rather than one recalled from memory.

Also recorded: both the BUA and ED CSV files are **Windows-1252**, not UTF-8
(Irish place names), which `cut` and a naive UTF-8 read both fail on. The
encoding is declared per source in the register.


---

## I-011 — SAPS 2022 cannot supply two distributions the design needs (Medium)

Both gaps were found by reading the glossary rather than by assuming the
columns existed.

**1. No detached / semi-detached / terraced split.** SAPS Table 6.1 "Private
households by type of accommodation" publishes exactly four categories:

| SAPS column | Category |
| --- | --- |
| `T6_1_HB_H` | House/Bungalow |
| `T6_1_FA_H` | Flat/Apartment |
| `T6_1_BS_H` | Bed-Sit |
| `T6_1_CM_H` | Caravan/Mobile home |

The schema's `dwelling_type` enum, the archetype library in design 5.7, and
U18's "Terraced" gap all need houses split into detached, semi-detached and
terraced. Terraced matters physically — two party walls rather than one — and
design 5.14 calls it "a common Cobh house type".

**2. Heating fuel is not heating system.** SAPS Table 6.5 records the *fuel*
(`T6_5_ECH` = Electricity), so a heat pump and a direct electric resistance
system are the same row. Design 5.7 needs them separated: their COP differs by a
factor of three or more, which dominates the heating load.

**Resolved with real data, better than planned.** CSO **EBA02** (built from the
SEAI BER register) turned out to be a genuine **joint** table, not a set of
marginals: BER band × dwelling type × main space-heating fuel × year of
construction × county. That is strictly more than the design assumed was
available, because a building's BER can be conditioned on its type, age and fuel
*together*. Measured for **Co. Cork** (Cobh's county; CSO reports Cork City
separately):

| Within houses | Share |
| --- | --- |
| Detached | 0.482 |
| Semi-detached | 0.316 |
| Terraced (end + mid) | 0.202 |

CSO **EBQ02** closes the second gap, giving renewable penetration for the
**South-West** NUTS3 region (Cork, confirmed as IE053 from the OSi small-area
attributes): heat pump 15.7% and solar 15.7% of BER-assessed dwellings.

The BER band distribution conditional on type and age behaves as physics
requires, which is a useful sanity check on the join: pre-1977 dwellings peak at
band C, 2010–2014 at B3, and 2015–2019 at A2.

**The Census remains the anchor.** BER coverage is not a census — it
over-represents new builds and recently sold or let properties — so BER supplies
only *conditional* shapes (the split within houses; the system within a fuel),
while every marginal SAPS publishes (house/apartment ratio, fuel shares,
year-built distribution) is held to SAPS. The functions are named
`conditional_dwelling_split` and `heating_system_split` for that reason, and the
restriction is stated in their docstrings so a later caller cannot mistake them
for penetration rates.

---

## I-012 — R03's two targets are barely jointly satisfiable at Cobh's real household size (Medium)

**Measured, not assumed.** Census 2022 SAPS for the Cobh built-up area:
**14,148 people in 5,257 private households = 2.6913 persons per household.**

R03 asks for "about 3,000 people (about 1,000 to 1,100 homes)" and design 12's
R03 acceptance fixes that as 2,900–3,100 people and 1,000–1,100 homes. Those two
ranges together imply 2.636–3.100 persons per household. Cobh's real ratio sits
near the bottom of that band, so the two constraints conflict under the obvious
anchor:

| Anchor | Scale factor | People | Homes | Both in range? |
| --- | --- | --- | --- | --- |
| 3,000 people | 0.21204 | 3,000 | **1,115** | No — homes over 1,100 |
| 2,900 people | 0.20498 | 2,900 | 1,078 | Yes |
| 1,100 homes | 0.20924 | 2,960 | 1,100 | Yes |
| 1,000 homes | 0.19022 | **2,691** | 1,000 | No — people under 2,900 |

So the feasible scale-factor window is **[0.204976, 0.209245]**, and the natural
"3,000 people" anchor is outside it. Forcing both by adjusting household sizes is
not available: R04 requires the scale-down to preserve Cobh's mix, and the
household-size distribution is one of the marginals being preserved. Widening a
range to fit would be exactly the threshold-widening the brief forbids.

**Mitigation taken.** `scale_down.feasible_scale_factor` derives the window from
both ranges **and the measured Cobh ratio** on every run, and takes its
**midpoint** (0.207110), giving **2,930 people in 1,089 homes** — comfortably
inside both ranges with Cobh's real 2.69 persons per household untouched. If the
window is ever empty the function raises rather than silently favouring one
constraint. See DECISIONS.md D-010.

**For Brian at the E1 review:** R03 is satisfiable as written, but only just,
and only because its ranges are ranges. If the intent was literally 3,000
people, the homes ceiling should be raised to about 1,120; if the intent was the
homes range, the people target reads better as "about 2,950".

---

## I-013 — The measured U03 comparison contradicts the design's own recommendation (Medium)

U03's recommendation in design section 11 is **"(a), stratified by area type,
then reweighted"**. E0-1 asked for both methods to be built and compared, with
the recommendation coming from the evidence. The evidence points the other way.

Scored against Cobh's own Census marginals and between-area structure
(`scripts/baile_nua/population/joint_metrics.py`):

| Metric | (a) whole areas, stratified | (b) proportional | Better |
| --- | --- | --- | --- |
| Small areas kept | 16 of 53 (30% coverage) | 53 of 53 (100%) | (b) |
| Marginal mean total-variation distance | 0.0400 | **0.0090** | (b) |
| Marginal max abs z | 6.09 | **2.07** | (b) |
| Joint mean abs difference (between-area association) | 0.1150 | **0.0471** | (b) |
| Spatial Moran's I mean abs difference | 0.0725 | **0.0068** | (b) |
| Spatial dissimilarity mean abs difference | 0.0504 | **0.0101** | (b) |
| Meets R03 ranges | No (1,108 homes) | **Yes (1,092 homes)** | (b) |

**Seed sensitivity, 10 seeds.** Method (a) depends on a seed; method (b) does
not. Over seeds 20261008, 1, 7, 42, 99, 123456, 2718281, 31415926, 555, 8080:

- method (a) beats (b) on joint error in **0 of 10** seeds (its mean 0.1398, best 0.1057, against (b)'s 0.0471);
- method (a) beats (b) on spatial error in **0 of 10** seeds (mean 0.1500, best 0.0948, against (b)'s 0.0169);
- method (a) meets R03's ranges in only **7 of 10** seeds, so whether the build satisfies a confirmed requirement would depend on the seed.

**Why.** The two methods trade different things away, and the trade is not
symmetric at this scale factor. Keeping whole areas preserves each retained
area's joint signature perfectly but represents the town with 30% of its areas,
losing 70% of the spatial extent — and Cobh's spatial variation is large (social
renting runs 0% to 74% across areas, household size 1.65 to 3.96). Proportional
scaling smooths each area and rounds 21.9% of non-zero (area, category) cells to
zero, but keeps all 53 areas and therefore the whole segregation pattern. At a
factor near 0.207, losing areas costs far more than losing within-area detail.

**Recommendation for the E1 report: adopt (b) proportional scaling.** It wins on
every measured criterion, is the only method that meets R03's ranges reliably,
and is seed-independent, which matters for a build whose outputs must be
byte-identical.

**This is an architectural recommendation, not a change made unilaterally.**
U03 is listed in design section 11 as a decision, and E0-1 explicitly reserved
the choice for the E1 report. The code therefore still builds **both** methods,
and the default is not hard-wired: `scale_down.build_both` returns both and the
generator takes the method as a parameter, so Brian's ruling at the E1 review
switches it with no code change.


---

## I-014 — No public Irish surname frequencies, and no non-Irish given-name lists (Low)

Design 5.2 step 6 asks for first names "by birth year and origin from CSO
baby-name tables and equivalent national lists, and surnames from
origin-matched lists".

**What was found.** The CSO baby-name tables are real, public and excellent:
VSA50 (boys) and VSA60 (girls) give every name registered three or more times
in each year from **1964 to 2025**, with counts. They are used directly, so an
Irish-born resident born in 1987 draws from the names that were actually common
in 1987 — verified: the top 1987 boys' names come out as David, John, Michael,
James; the top 2018 girls' names as Emily, Grace, Emma, Sophie.

**What was not found.** No public machine-readable table of Irish **surname**
frequencies, and no equivalent national given-name lists for the other
place-of-birth groups.

**Mitigation taken, and why it is the right direction.** Both pools
(`baile_nua/data/surnames_by_origin.csv`, 191 surnames across 7 origin groups;
`baile_nua/data/given_names_by_origin.csv`, 100 given names) are **unweighted**
and drawn uniformly. Two reasons, both recorded in the files themselves:

1. The brief forbids hard-coding a statistic from memory. An unweighted pool is
   a name *space*; a weighted one would be a statistic with no source.
2. R27 and K12 want synthetic identities **not** to resemble real residents.
   Reproducing real surname frequencies would make Baile Nua's name
   distribution match the real town's, which is the opposite of what is wanted.

**Known limitation, stated plainly.** Baile Nua's surname frequencies do not
match Ireland's, and for non-Irish-born residents the given name is culturally
appropriate but **not** age-appropriate, because no year dimension is available.
About 80% of Cobh is Irish-born by the Census place-of-birth marginal, so the
majority of the town does get year-appropriate names. No energy or behaviour
claim depends on any of this.

---

## I-015 — No authoritative public-figure register was found (Low)

R27 and design 5.2 step 6 require rejecting any full name that matches a
public-figure list. No authoritative machine-readable register for Ireland was
located, so `baile_nua/data/public_figures.txt` is a hand-compiled list of 94
names: holders of prominent national and Cork/Cobh public office, and figures
whose names are recognisable enough that the coincidence would be noticed in a
dataset about an Irish town. It contains no private individuals — the file is
committed, so it must contain only names that are already public.

**The list is not the real protection, and the E1 report says so.** Coverage is
partial by construction. What actually protects against a synthetic resident
resembling a real one is structural:

* no address in Baile Nua corresponds to a real address;
* surnames are drawn uniformly rather than at real frequencies (I-014), so the
  name distribution does not match the real town's;
* every person record carries `synthetic = true` (D05.synthetic);
* full-name uniqueness is enforced across the town.

The generator counts how many candidate names each rule rejected, so the list's
actual contribution is measured rather than assumed.

---

## I-016 — The Day-1 marginal threshold was mis-specified (Medium, needs Brian's ruling)

**What happened.** On Day 1 I wrote a provisional acceptance threshold of
`saps_marginal_z_abs_max: 2.0` into `config/thresholds.yaml`, as my reading of
design 12's R04 acceptance, *"Every SAPS marginal within the sampling-error
band"*. On Day 2, with the population synthesised, two of the three marginals
exceeded it:

| Marginal | Categories | TVD | max abs z |
| --- | --- | --- | --- |
| age_by_sex | 68 | 0.0535 | 3.081 |
| household_size | 8 | 0.0332 | 1.983 |
| household_type | 14 | 0.0364 | 2.289 |

**Why the threshold, not the synthesis, is wrong.** 2.0 is a *per-test*
critical value (the two-sided 95% point is 1.96) and I had applied it to the
*maximum* over all categories. Across the 90 categories actually compared, a
**perfect** synthesis — one drawing exactly from Cobh's distribution — would
show an expected maximum |z| of about **2.54**, and would exceed 2.0 in four or
five categories purely by chance. A test that a correct implementation fails
most of the time is not a test of the implementation.

**What was changed.** The band is now simultaneous, Bonferroni over the number
of categories actually compared, with α fixed at 0.05:

    z_crit = Phi^-1( 1 - alpha / (2 * n_categories_total) )  =  3.452 at n = 90

Under that band all three marginals pass (max 3.081 < 3.452).
`joint_metrics.marginal_acceptance` reports **both** verdicts on every run — the
simultaneous one as the criterion and the naive per-test one for transparency —
plus the expected maximum for a perfect synthesis, so the reader can see how
far from perfect the synthesis is (3.081 against 2.54) rather than only whether
it cleared a line.

**Why this is not threshold-widening.** The rule I am holding myself to is that
a threshold is never loosened to manufacture a pass, and that representation
fixes are legitimate while threshold widening is not. This is neither a
representation fix nor a widening: it is the correction of a **specification
error in a number I wrote myself**, and the design's own wording ("the
sampling-error band") does not name 2.0. Three things keep it honest:

* α is unchanged at 0.05 — the family-wise rate is now controlled, where before
  nothing was;
* the threshold is stored as a *method*, not a number, so it cannot be tuned to
  a result;
* the naive verdict is still computed and printed, and it still says FAIL.

**What Brian is asked to rule on at the E1 review** (U11 keeps §7 margins
provisional, so this is exactly the kind of item E1 is meant to surface):

1. accept the simultaneous Bonferroni band as the R04 criterion; **or**
2. keep a per-test band and accept that a small number of exceedances is
   expected, specifying how many; **or**
3. set a scale-free criterion instead — total-variation distance has no
   multiplicity problem at all, and the synthesis achieves 0.033 to 0.053, which
   would pass any TVD threshold at or above about 0.06.

I have not applied option 3 unilaterally, even though it is the cleanest, because
choosing the acceptance statistic is a U11 decision rather than an
implementation detail.


---

## I-017 — Met Éireann station 1575 is Malin Head, not Roches Point (High, closed)

**How it was caught.** The design names Roches Point as the coastal station for
Cobh. I guessed station number 1575 from the URL pattern, downloaded
`hly1575.zip` successfully (11 MB, HTTP 200), and only found the error because
the Met Éireann CSV carries its own station name in its header:

```
Station Name: MALIN HEAD
Station Height: 20 M
Latitude:55.372  ,Longitude: -7.339
```

Malin Head is in Co. Donegal, at 55.37°N — **the northernmost point of
Ireland**, about 400 km from Cobh and on the opposite coast. Had this gone
unnoticed, every building in Baile Nua would have been simulated against north
Donegal weather while the report claimed Cork Harbour, and nothing downstream
would have failed: the file is well-formed, the units are right, and the
temperatures are plausible for Ireland.

**The correct station**, from Met Éireann's own `StationDetails.csv`:

| Station | Number | Latitude | Longitude | Height | Open |
| --- | --- | --- | --- | --- | --- |
| ROCHES POINT | **1075** | 51.793 | −8.244 | 40 m | 2004– |
| ROCHES POINT (closed) | 1004 | 51.793 | −8.244 | 43 m | 1873–2008 |
| LH_ROCHES_POINT | 5180 | 51.793 | −8.255 | 27 m | 2000– |
| CORK AIRPORT | 3904 | 51.847 | −8.486 | 155 m | — |

Station 1075 is now in the register and verified: its header reads
`Station Name: ROCHES POINT`, `51.793, -8.244`, `40 M`. Cork Airport (3904) was
correct as guessed, confirmed by its own header (51.847, −8.486, 155 m).

Roches Point at 40 m on the harbour mouth, 10 km from Cobh, is the right driver
for the true site series (D15, GT); Cork Airport inland at 155 m is the right
observable station series (D31, OBS), and the 115 m elevation difference plus the
coastal/inland contrast makes the station-to-site gap design 6.4 item 7 wants
physically real rather than injected noise.

**Generalised countermeasure.** Guessing an identifier is not acceptable where
the file can be asked what it is. `weather.station` asserts on read that each
file's embedded station name, latitude, longitude and height match the register
entry, and fails the run otherwise. The same discipline already applies to the
SAPS join (`saps.verify_join_keys`) and to the MIMIC constants
(`crosswalk.verify_against_mimic_source`).

---

## I-018 — CSO PxStat returns a bare 403 for an over-size CSV request (Low, closed)

`GET .../ReadDataset/EBA02/CSV/1.0/en` returns **HTTP 403 Forbidden** with an
18-byte body (`API.RESTful_Output`), which reads as an authorisation failure.
The same request through the JSON-RPC endpoint gives the real reason:

> You are attempting to download 6800112 data cells in CSV. This exceeds the
> maximum of 1048575 data cells you can download in CSV.

Confirmed it is server-side, not the client: plain `curl` gets the same 403,
while `JSON-stat/2.0` for the identical matrix returns 200 and 33 MB. Both BER
sources are therefore registered in JSON-stat form, and `population.ber`
flattens the cube explicitly (row-major strides, nulls skipped) rather than
through a library, so that a transposed dimension would show up as a test
failure rather than as a plausible-looking but wrong distribution.

Worth knowing for anyone else querying CSO: a 403 from PxStat may mean "too
large for CSV", not "not permitted".


---

## I-019 — Four physics input sets are declared assumptions (Medium)

The brief forbids hard-coding statistics from memory, and every *empirical*
calibration number in this build traces to a file under `sources/` through D24.
Four sets of inputs to the thermal model are a different kind of thing —
**regulatory definitions and typical-construction values** — and they have
**not** been read back from their source documents in this run. They are
declared, flagged `[A]`, and listed here so the E1 report can carry them as
unverified inputs rather than present them as sourced.

| Input | File | What depends on it | Risk if wrong |
| --- | --- | --- | --- |
| BER band energy boundaries (kWh/m²/yr) | `data/ber_bands.yaml` | `D02.ber_kwh_m2_yr`, the asset rating reported against the performance gap | Scales the reported asset rating within a band. Does **not** affect the fabric, since the fabric is now derived forward from U-values, not from the BER figure. |
| Part L elemental U-values and air-tightness by era | `data/fabric_u_values.yaml` | Every building's heat loss coefficient, hence all heating load | Largest single sensitivity in the thermal model |
| Thermal mass parameter by era (kJ/m²K) | `physics/archetype.py` | Building time constants, hence pre-heating and flexibility behaviour | Second-largest; an earlier version was wrong by ~3× and gave 6–18 h time constants |
| Floor area per habitable room | `population/buildings.py` | Floor area, hence everything that scales with it | Moderate; SAPS publishes room counts but no floor areas, and EBA02 carries none either |

**What makes these tolerable for E1 but not beyond it.** E1 is engineering
verification (V0 only): the claim is that the code computes what the model says,
not that the model matches Irish homes. Three guards keep the assumptions
honest in the meantime:

* the derived specific heat loss is asserted against the published Irish Heat
  Loss Indicator range (0.25–6.5 W/K/m²) and the run **fails** outside it;
* the derived time constant is asserted against the 15–140 h range that
  grey-box identification on real dwellings reports;
* the realised distributions are reported, not just the inputs — the town comes
  out at HLI median 1.98 (p10 1.16, p90 4.39) W/K/m² and τ median 48 h (p10 27,
  p90 72), which are the right shape for Irish stock.

**Required before any V2 or S-track claim:** read the Part L editions and the
DEAP manual and replace all four sets with sourced values, and run design 5.7's
F1-vs-F3 cross-model fidelity test, which is what would actually falsify the
thermal mass assumption.

---

## I-020 — The Day-2 "marginals shifted 10%" control is below the test's resolution (Medium)

Design 9.3 names, as the Day-2 negative control, "marginals shifted 10%". It is
implemented (NC-D2-03) and it reports **NOT_DETECTED**. That is a real result,
and it is a property of the *town size*, not of a broken check.

**Measured detection threshold** of the R04 acceptance band (simultaneous
Bonferroni, α = 0.05), found by bisection on the size of a shift from
one-person to four-person households:

| Sample size | Smallest detectable relative shift | Detects the design's 10%? |
| --- | --- | --- |
| 1,092 homes (Baile Nua) | **12.76%** | **No** |
| 5,257 homes (full Cobh) | 5.85% | Yes |

So a 10% shift is *inside* sampling error at 1,092 homes, and no
sampling-error-based test can reject it — which is what "within the
sampling-error band" means. It is a near miss: 10% against a 12.76% threshold.

**It is not rescued by a scale-free statistic either**, which is the more
uncomfortable half of the finding. The 10% shift has a total-variation distance
of 0.0248, while the synthesis's *own* household-size deviation is 0.0332 — the
deliberate cost of preserving the person total when the 8+ household category
rounds away to zero at this scale factor (recorded in
`scale_down._repair_person_total`). The synthesis's own error is therefore
**larger than the error the control injects**, so a TVD threshold that passes
the real synthesis would also pass the shifted marginal.

**What was done rather than hidden.** NC-D2-03 is kept, reports NOT_DETECTED,
and the E1 report states it as a **recognised limitation of the test**, not a
pass and not a software defect — design 5.14's own "verify vs diagnose"
vocabulary. A companion control **NC-D2-05** shifts 40%, above the measured
threshold, and is correctly rejected, which demonstrates the check works when
the error exceeds its resolution. The threshold itself is now computed by
`controls_day2._resolution_of_marginal_band` and reported.

**For Brian at the E1 review (U11).** Three options, in increasing cost:

1. Accept that at 1,092 homes the marginal test resolves ~13% shifts, and state
   that bound in every release rather than implying finer sensitivity.
2. Tighten the synthesis so its own size-marginal deviation is well below the
   control's, which means resolving the 8+ household category rather than
   letting it round to zero — that is a scale-down change, and it trades against
   the exact person total.
3. Validate marginals against full Cobh counts rather than the scaled town,
   where the threshold is 5.85%. This tests the *scale-down* rather than the
   *synthesis*, so it answers a different question; both are worth having.

I have not chosen between these, because the acceptance statistic is a U11
decision.


---

## I-021 — Both MIMIC migrations fail on MySQL 8.0, including the GDPR compliance one (High)

**Found** while bringing up the local sandbox: both files under
`database/migrations/` error out immediately against the MySQL version MIMIC's
own `docker-compose.yml` pins (`image: mysql:8.0`; the container reports
8.0.46).

```
$ mysql mimic < database/migrations/002_v1r2_compliance.sql
ERROR 1064 (42000) at line 7: ... near 'IF EXISTS health_status, DROP COLUMN IF EXISTS fitness_level, DROP COLUMN IF' at line 2

$ mysql mimic < database/migrations/003_dashboard_indexes.sql
ERROR 1064 (42000) at line 6: ... near 'IF NOT EXISTS idx_responses_participant ON responses (participant_id)' at line 1
```

**Cause.** `DROP COLUMN IF EXISTS`, `ADD COLUMN IF NOT EXISTS` and
`CREATE INDEX IF NOT EXISTS` are **MariaDB** extensions. MySQL supports none of
them, in any 8.x release.

**Why 002 matters more than a syntax slip.** Its own header says *"Apply to
existing V1R1 databases"*, and its first statement is the **ADR-004 GDPR
Article 9 / re-identification** cleanup:

```sql
ALTER TABLE profile_optional
  DROP COLUMN IF EXISTS health_status,
  DROP COLUMN IF EXISTS fitness_level,
  DROP COLUMN IF EXISTS mobility_limitation,
  DROP COLUMN IF EXISTS medical_device_dependence,
  DROP COLUMN IF EXISTS country_of_birth;
```

On a **fresh** database this is harmless: `schema.sql` never creates those
columns, and the sandbox was verified to have none of them
(`information_schema.COLUMNS` returns empty for all five). But on an **existing
V1R1 MySQL database** — the only case the migration exists for — the statement
fails, so **the Article 9 columns are not dropped**, and because MySQL applies a
multi-clause `ALTER TABLE` atomically the ADR-006 additions in the same file
(`mcv_position`, `mcv_completed_at`, `session_items.context_key`) are not
applied either. An operator reading the migration as "applied" would be wrong
on both counts.

**Recommended fix for the MIMIC team** (not made here — the brief says to record
MIMIC changes, not to make them). For the drops, query
`information_schema.COLUMNS` and build the `ALTER` from what is actually there;
for the adds, the same against the same table; for the indexes, the same against
`information_schema.STATISTICS`. Splitting the single `ALTER TABLE` into
separate statements would also stop one failure taking the others down.

**Mitigation in the sandbox.** A MySQL-8-compatible equivalent of 003 was
applied so that the T9 dashboard aggregates are measured on an indexed database
rather than an unindexed one — nine indexes created, one already present from
`schema.sql`. 002 needed nothing on a fresh database. The MIMIC repository is
untouched.

---

## I-022 — MIMIC's compose file publishes MySQL on all interfaces (Medium)

`docker-compose.yml` in the MIMIC repository contains:

```yaml
  mysql:
    ports:
      - "3306:3306"
  web:
    ports:
      - "8080:80"
```

A bare `3306:3306` binds `0.0.0.0`, so the database is reachable from anything
that can route to the host — on a laptop that means the local network. Combined
with the default credentials in the same file (`mimic`/`mimic`, root
`rootsecret`), that is more exposure than a development stack needs.

**Mitigation, and a Compose behaviour worth knowing.** The sandbox override
publishes loopback-only mappings, but that was **not sufficient on its own**:
Compose *merges* list-valued keys, so an override's `ports` are **appended** to
the base file's rather than replacing them. Observed directly — after the first
`up`, `docker compose ps` showed

```
0.0.0.0:3306->3306/tcp, [::]:3306->3306/tcp, 127.0.0.1:33099->3306/tcp
```

all three at once. `provision._strip_port_mappings` therefore removes the base
mappings from the **sandbox copy** of `docker-compose.yml` before the override
adds loopback ones. The sandbox now shows only
`127.0.0.1:33199->3306/tcp` and `127.0.0.1:18099->80/tcp`.

Also found: the sandbox's first chosen ports were both already in use on this
machine (8099 by an unrelated application, 3306 by another MySQL), and the only
symptom was a Docker daemon bind error. `provision.assert_ports_free` now checks
before starting.

**Recommended for the MIMIC team:** bind development ports to `127.0.0.1`
explicitly, and move the credentials out of the committed compose file.


---

## I-023 — MIMIC's "deterministic mulberry32" RNG overflows to float (High)

**How it surfaced.** `api/session.php` returned unparseable JSON, with a PHP
notice in the response body:

```
Deprecated: Implicit conversion from float 1.1820582688627853E+19 to int
loses precision in /var/www/html/mimic/includes/Rng.php on line 22
```

**Cause.** `Rng::next()` implements mulberry32, which assumes 32-bit wrapping
arithmetic:

```php
$t = (($t ^ ($t >> 15)) * ($t | 1)) & 0xFFFFFFFF;
```

PHP integers are 64-bit and do **not** wrap — they promote to float on
overflow. With `$t` near its 32-bit maximum, `$t * ($t | 1)` reaches about
**1.84 × 10¹⁹**, above `PHP_INT_MAX` of 9.22 × 10¹⁸ (measured in the container,
PHP 8.3). Verified directly:

```
PHP_INT_MAX  = 9223372036854775807
t            = 4294967280
t*(t|1)      = 1.8446743940566E+19   is_float=true
```

**Two consequences, the second more serious than the first.**

1. The float-to-int conversion emits a PHP 8.1+ deprecation notice. MIMIC's
   image runs with `display_errors => STDOUT`, so it lands **inside the HTTP
   response body** and breaks JSON parsing for any API client. This blocked the
   HRSD runner completely until `display_errors` was turned off in the sandbox.
2. **The RNG is not mulberry32.** A double has a 53-bit mantissa, so a product
   of ~2⁶⁴ loses its low ~11 bits before the `& 0xFFFFFFFF` mask is applied.
   The masked result is therefore not the algorithm's output. `Rng.php`'s own
   docblock says *"Deterministic mulberry32 RNG (SPECS — server-side session
   composition)"*, and SPECS relies on session composition and option-order
   randomisation being reproducible from the stored seed. They are reproducible
   (the same seed gives the same wrong sequence) but they are **not the
   documented algorithm**, and the low-bit distribution is distorted — which is
   exactly where `Rng::int()` takes its values from, via
   `floor($this->next() * $max)`.

**Recommended fix for the MIMIC team** (not applied — the brief says to record
MIMIC changes, not make them): keep every intermediate product inside 2⁵³ by
splitting the multiply into 16-bit halves, or use `gmp_mul`/`bcmul` with a
32-bit mask. A unit test comparing the first few outputs against a reference
mulberry32 implementation would have caught it.

**Mitigated in the sandbox** only to the extent of stopping the notice
corrupting API responses (`display_errors=Off`, which is the correct setting for
anything serving an API). The RNG defect itself is **not** worked around, and
every MIMIC test result in the E1 report is produced against the RNG as it
actually behaves.

---

## I-024 — `api/session.php` does not return the factorial `context_key` (Low)

ADR-006 added `session_items.context_key` and migration 002 populates it, but
the session payload carries only the human-readable `context_label`
("under normal supply", "with strong privacy safeguards in place"). An API-only
consumer therefore cannot read the factorial arm directly.

This is not cosmetic: test T7 estimates a context effect (AMCE), and attributing
a response to the wrong arm makes the planted effect unrecoverable. The first
version of the runner defaulted every item to context `a`, which would have
silently destroyed T7.

**Mitigation.** `runner._context_key_of` recovers the key from the scenario id,
whose final segment is the context key by construction (`DAP-04-b` is DAP
scenario 04 in context b). Verified: a 13-item session now resolves 7 items to
`a` and 6 to `b`, matching the scenario ids.

**Recommended for the MIMIC team:** include `context_key` in the
`api/session.php` item payload, since the column already exists and is populated.

---

## I-025 — U17 and U19 are incompatible with MIMIC as it stands (CRITICAL)

This is a **contradiction between two approved E0 decisions**, not an
implementation problem, so it is recorded here as the brief requires.

**The two decisions.**

* **U17** (approved): mark synthetic rows with
  `consent_version = 'SYNTHETIC-HRSD-v1-<pool>'`, chosen specifically — design
  5.14's own words — "so MIMIC's existing purge (`LIKE 'SYNTHETIC%'`) and
  synthetic banner work unchanged".
* **U19** (approved): create participants through **real-time public API calls**
  with a test-mode allowance, rather than a back-dated direct import.

**Why they cannot both hold.** `api/profile.php` takes the consent version from
the application config, and no request field can override it:

```php
$app = require dirname(__DIR__) . '/config/app.php';
$meta = $service->saveDemographics($pid, $app['consent_version'], $body);
```

`ProfileService::assertAllowedKeys` rejects any key outside the 16 primary and
10 optional fields, so `consent_version` cannot even be passed. Going through
the API therefore makes the U17 marker **unsettable**.

**Measured consequence, before it was fixed.** 2,642 participants had been
created through the API when the integrity check was first run:

```
consent_versions: {'2026-07-02': 2657}
SELECT COUNT(*) FROM profiles WHERE consent_version LIKE 'SYNTHETIC%'  ->  0
```

So:

* MIMIC's **purge** would not have found a single one of them — 10,000 synthetic
  participants left permanently indistinguishable from real respondents in the
  one mechanism designed to remove them;
* MIMIC's **synthetic banner** (`DashboardQuality::syntheticStats`, which counts
  `consent_version LIKE 'SYNTHETIC%'`) would have reported **zero synthetic
  participants**, so the dashboard would have presented 130,000 synthetic
  responses as real data. That also fails T9's "synthetic banner shown"
  criterion outright.

That second consequence is why this is Critical rather than High: the failure
mode is silent and it points the wrong way — toward presenting synthetic data as
genuine.

**Resolution applied.** The **sandbox instance's** `config/app.php` declares the
synthetic marker as its consent version
(`provision.set_consent_version`). This is faithful rather than a workaround:
every participant created in this instance is synthetic, so the instance-level
consent version is the correct place for the marker, and the purge and banner
then work exactly as U17 intended. Verified after the change:

```
consent_versions: {'SYNTHETIC-HRSD-v1-HRSD-pool': 133}
SELECT COUNT(*) FROM profiles WHERE consent_version LIKE 'SYNTHETIC%'  ->  133
```

The marker is 27 characters, within `profiles.consent_version`'s `VARCHAR(32)`,
and `set_consent_version` asserts both the `SYNTHETIC` prefix and the length so
a longer pool code cannot silently truncate the prefix out of range.

The 2,642 unmarked participants were deleted before the real batch was run, so
no unmarked synthetic row survives.

**Required MIMIC change (not made).** Let the consent version be supplied per
request under an explicit test mode, or add the `participants.is_synthetic`
column U17 also asked for (schema 1.1 has no such column) and set it on the
synthetic path. Either closes the gap properly; the sandbox fix only closes it
for this instance.

**For Brian at the E1 review.** U17 and U19 can both stand once MIMIC changes.
Until then, any instance receiving HRSD participants must have its
instance-level consent version set to the synthetic marker, and that must be a
documented precondition of the export — because the failure is silent.


---

## I-026 — PHP OPcache delayed the pool marker, mis-tagging a whole test arm (Medium, closed)

The U17 marker carries a **pool code** (`SYNTHETIC-HRSD-v1-<pool>`), and the
instance-level fix for I-025 means switching pools requires rewriting the
sandbox's `config/app.php` between batches. The container runs PHP with

```
opcache.enable            => On
opcache.validate_timestamps => On
opcache.revalidate_freq   => 2
```

so a config change is invisible to PHP for up to two seconds. Starting a batch
immediately after the rewrite therefore tagged its first participants with the
**previous** pool's code.

**Measured.** After the three batches, the database held:

```
SYNTHETIC-HRSD-v1-HRSD-pool   10678
SYNTHETIC-HRSD-v1-BN-panel      986
```

against 10,050 pool + 600 T10 + 1,014 panel participants actually run. So the
entire 600-participant T10 arm and 28 of the panel participants were recorded
under the main pool's code — 628 rows, 5.4% of the total, in the wrong pool.

**Why it did not affect the E1 criteria.** Every row still begins `SYNTHETIC`,
so MIMIC's purge predicate and its synthetic banner both work on all 11,664 —
the Critical half of I-025 stayed fixed. The five counters are computed from
the runner's own batch records rather than from the marker, so they are correct
as reported. What was wrong was only the *pool attribution inside the marker*,
which matters for purging one pool without the other and for any analysis that
slices by pool.

**Fix.** `provision.set_consent_version` no longer returns after writing the
file. It creates a throwaway participant through the API, reads back **that
specific participant's** stored consent version, deletes it, and repeats until
the value matches — returning `verified_live`. A sleep would have been simpler
and would have been a guess; a guess that is occasionally too short produces
mis-tagged data that nothing downstream flags.

One further bug was found and fixed inside the fix itself: the first version of
the probe read "the most recently created profile", but the probe revokes
itself, so it read whatever the *previous* probe had left behind and reported a
stale value. It now reads by participant id. Verified across all three pools:
`verified_live=True` for `HRSD-pool`, `BN-panel` and `HRSD-T10`.

---

## I-027 — The device layer had no public target, and was 40% over the national mean

**Severity:** High · **Raised:** Day 6 · **Status:** Fixed, with a declared tuning exposure

Appliance trigger rates were declared assumptions `[A]` (design 5.6 says only
"probabilistically" and defers the rates to calibration), and there was nothing
to score them against. The first E1 estate drew **16.35 kWh per home per day of
appliance electricity alone** — 5,968 kWh a year — against a Co. Cork mean of
**4,186 kWh a year for everything, electric heating included**.

Nothing in the repository could have caught it, because no Irish household
electricity figure was registered as a source. That is the real defect: the
brief requires every calibration number to trace to a file in `sources/` (D24),
and a layer with no target cannot be checked at all.

**Fix, in two parts.**

*A target.* Six CSO tables registered and downloaded, and `baile_nua/calibration`
built to read them — no literal statistic appears in that module, every value
is read from a registered file at a recorded SHA-256:

| Table | What it gives | Exposure |
|---|---|---|
| `DBEREL01` | mean kWh/dwelling/year by dwelling type × BER band, 2022 | **tuning** |
| `DBEREL02` | same by dwelling type × period of construction | **none (held out)** |
| `MEC06` | national distribution of residential meters by annual kWh band | none |
| `MEC03` + `MEC07` | Co. Cork residential GWh ÷ Co. Cork residential meters = **4,185.9 kWh/meter/year** | none |
| `MEC05` | urban:rural residential ratio (5,668:3,095 GWh) | none |

The tuning split is deliberate and is asserted in code: `DBEREL01` crosses
dwelling type with BER band, which is what the trigger rates were tuned
against, so it cannot also measure whether they generalise. `DBEREL02` crosses
the same dwellings with period of construction — an axis the tuning never saw,
and one D02 already carries as `year_built_band`. `electricity_by_construction_targets`
raises if that table's declared exposure is ever anything but `none`.

*A fix to the rates.* Only after I-028 and I-029 below were fixed — most of the
excess was theirs, not the rates'. The cooking rates were then tuned, with the
reasoning recorded in `TRIGGERS`: a cooking *episode* is not a cooked meal.
HETUS gives 36 minutes of food management per person per day, so a
three-person household spends an hour and a half on food across its members,
which is about three episodes a day and about two hob uses.

**Result:** 16.35 → **10.91 kWh/home/day** (3,982 kWh/year), against DBEREL01's
fossil-heated cells of 3,700–4,900 kWh/year. Cycle counts per household per
day: oven 0.69, hob 2.75, kettle 7.53, washing machine 0.74, tumble dryer 0.41,
dishwasher 0.54.

One further error found on the way: the oven signature's thermostat shape
placed its turning points a tenth of a cycle apart, and the shape is linearly
interpolated, so the element spent that tenth sliding between off and full
rather than switching. Its mean came out at 0.63 of rating — a one-hour bake at
1.51 kWh against a real 1.0 to 1.2, making the oven the largest single
appliance in the estate. Transitions are now one hundredth of a cycle wide,
which is a square wave to within the 1-minute render step; mean 0.4804, bake
1.153 kWh.

---

## I-028 — The activity engine fragmented the day into 45 episodes

**Severity:** High · **Raised:** Day 6 · **Status:** Fixed

The engine emitted **45.2 activity episodes per person-day**, against the 20 to
30 a real time-use diary records, and **36% of television episodes were one or
two minutes long**. One person's evening contained `eating_main 1378–1379`,
`eating_snack 1379–1380`, `tv_screens 1383–1385`.

**Cause.** In the gap-filling loop the duration was
`min(gap, budget, drawn_duration)`. An activity whose daily budget had two
minutes left in it was placed as a two-minute episode; late in the evening
every budget was nearly spent at once, so the tail of the day was sliced into
slivers.

**Why no test caught it.** Every existing activity test compared *total minutes
by activity* against HETUS, and fragmenting a correct total into slivers does
not change the total. 162 tests passed throughout.

**Fix**, four parts, each of which failed a test before it was written:

1. An activity whose remaining budget is below its own episode floor is removed
   from contention, rather than spending the remnant as a sliver.
2. A gap too short to hold any real episode is absorbed by the activity next to
   it. A real diary has no two-minute gaps because a real person does not
   change what they are doing for two minutes; the gap is an artefact of
   placing fixed blocks around it.
3. Only activities that *fit* the gap are candidates. Choosing first and
   truncating afterwards had put a 31-minute `social_out` into a gap against
   its own 45-minute floor, which made the duration bound describe nothing.
4. Travel bracketing takes its legs from the block it brackets, and the leg
   shrinks to preserve the activity's own floor instead of leaving a flat
   10-minute core.

A separate sliver was fixed in the same pass: anyone whose bedtime fell after
midnight received **one minute of sleep at 23:59**. The wrap-around branch
called `place(bed - 1440, 0, ...)`, whose end minute is 0 and which is
therefore a silent no-op, then `place(1439, 1440, ...)`. 19% of all sleep
intervals were one or two minutes long. A bedtime past midnight simply means
the day ends awake; the next day's own `place(0, wake)` accounts for the sleep.

**Result:** 45.2 → **27.1 episodes per person-day**; sub-floor episodes under
5%; sleep slivers 19% → 0.6%.

A consequence had to be fixed too. Applied naively, the episode floor excluded
every *low-frequency* activity for ever: laundry's target is 5 to 11 minutes a
day against a 10-minute floor, so it could never be selected and **no washing
machine in the estate ever ran**. Such a target does not mean a few minutes
every day — it means a full episode now and then. It is now spent as an
occurrence probability, `p = target / drawn_episode_length`, which is
mean-preserving by construction.

---

## I-029 — Six HETUS activity codes were mis-assigned

**Severity:** High · **Raised:** Day 6 · **Status:** Fixed

The `tus_00*` downloads carry activity codes and no label text — `AC331`,
`AC33A` — so the mapping from an HETUS code to a modelled activity rested on
recollection of what each code means. Six were wrong:

| Activity | Was | Which Eurostat labels | Now |
|---|---|---|---|
| `laundry` | `AC33A` | Handicraft and producing textiles (2 min) | `AC331` Laundry + `AC332` Ironing (9 min) |
| `adult_care` | `AC38B` | Teaching, reading and talking with **child** (7 min) | `AC37_39` Household management and help family member, flagged `[A]` |
| `cleaning` | `AC32A` | Household upkeep **except cleaning dwelling** (13 min) | `AC321` Cleaning dwelling + `AC32A` (30 min) |
| `reading` | `AC7A` | **Computing** (21 min) | `AC811` + `AC812` Reading (19 min) |
| `religion_civic` | `AC53` | **Resting** (19 min) | `AC41` + `AC43` + `AC52` (17 min) |
| `washing_up` | 38% of `AC31A` | Food management **except dish washing** | `AC313` Dish washing (11 min), in full |

`AC313` "Dish washing" and `AC321` "Cleaning dwelling" existed in the data and
went unused while declared splits of their *parents' siblings* stood in for
them. `idle_at_home` was a declared 10% slice of all leisure; `AC53` "Resting"
is what idling is, and is its own code. `school`/`study_at_home` were a
declared 80/20 split of `AC2`; `AC21A`, `AC212` and `AC22` give the split
directly. `travel_commute` was a declared 30% of `AC9A`; `AC913` "Travel
to/from work" is published, and `travel_other` is now `AC9A − AC913`, so the
two sum to `AC9A` exactly.

**Fix.** Eurostat's SDMX codelist `ACL00` registered as a source and read at
run time; `ACTIVITY_CODES` now holds `(code, weight)` tuples so one activity
can sum several codes and a negative weight can subtract one; every entry
carries Eurostat's own label; and `mapping_audit()` raises on any code absent
from the codelist.

The brief forbids hard-coded statistics from memory. A code-to-meaning mapping
from memory is the same failure one step removed, and it produced targets wrong
in level and sometimes in kind.

**The test that now catches it** states, for each activity, a word that must
appear in the official label of at least one code it draws on — written from the
activity name, so it is an independent statement of intent rather than a
restatement of the table. All six faults fail it.

**A second check**, stronger than any per-activity total: HETUS's six
top-level codes sum to exactly 1,440 minutes (verified on three (sex, age)
groups, not assumed), and every mapped code is a leaf beneath one of them, so
the mapped leaves plus the five deliberately unmodelled ones must reconstruct
the day. They do, to within 6 minutes. A missing leaf deflates that sum and an
overlapping parent inflates it, and neither is visible in a per-activity total.

That test was itself wrong when first written — it treated `AC99NSP` and
`AC90NSP` as additions to the day when they sit *inside* the aggregates, and
reported a 38-minute excess where there was none. The mapping was right and the
test was wrong; the top-level identity was checked against the file before
either was trusted.

---

## I-030 — The manifest's own content hash dominated the entire pipeline

**Severity:** Medium · **Raised:** Day 6 · **Status:** Fixed, by reversing a Day-1 choice

Profiling the stream writer on three days of the estate found **32.8 seconds of
a 47-second writer inside `hash_frame`** — several times the cost of the
physics, occupancy, device and observation simulation it was recording. The
cause was 600,439 `json.dumps` calls: one per row.

`hash_frame` was written on Day 1 to be **row-order independent**, by hashing
each row to canonical JSON and sorting the digests, on the reasoning that
"worker interleaving may change arrival order; content must not change".

**Two things were wrong with that.**

*The cost.* At the estate's device mix D18 is about 180,000 rows a day, so a
year is 66 million rows. Row-wise JSON hashing measured 12.7 s per 500,000
rows — about 28 minutes a year for D18 alone, to compute a number written into
a sidecar file.

*The direction.* A row-order independent hash calls two different byte streams
"the same content". What this hash records is a Parquet file, and design 9.2's
criterion is *byte-identical* output at 1, 8 and maximum workers — which the
determinism harness checks with SHA-256 over the files themselves, and which is
order-sensitive by nature. So the normalisation could only ever **hide** a
difference the gate cares about. It was weaker than what it is used for, not
stronger. And no legitimate reordering exists for it to absorb: every dataset
is written with households in sorted id order and days in calendar order,
precisely so arrival order cannot leak.

**Fix.** `hash_frame` is now columnar and row-order **sensitive**, hashing each
column's canonical bytes with nulls carried as a separate packed mask so a null
and a zero can never collide whichever of pandas' four missing values the dtype
happens to use. String and categorical columns are factorised, so the hash
touches a handful of distinct device ids rather than 66 million individual
Python strings. Column order is still normalised, because that genuinely is
incidental.

Measured: **500,000 rows in 0.079 s against 12.7 s**, a factor of 160. Writer
time per estate-day fell from 8.08 s to 2.47 s, and the projected estate-year
from about 73 minutes to about 31.

`hash_frame_row_order_independent` keeps the old behaviour for anything that
wants it, with a docstring saying not to use it on a large frame.

**On changing a test.** `test_frame_hash_is_row_order_invariant` pinned the old
property and had to change. It is not an E1 acceptance criterion — design 9.2's
criterion is byte-identical output, which is tested directly and more strictly
— and the replacement test asserts the stronger property together with two new
ones (a null never collides with a zero; the hash does not change because a
column arrived as `Int64` rather than `int64`). The old function keeps its own
test. The reversal is recorded as D-019 rather than absorbed.

**Two smaller faults found in the same pass.**

`build_export` aggregated through two lambdas and then walked the result with
`iterrows`, building one dict per interval — 2.6 million Series objects over
the estate-year, for arithmetic that is one division. Vectorised: 10.6 ms per
premises-day.

`build_export` also seeded its noise generator from `abs(hash(premises_id))`.
CPython salts `hash()` per process, so a noisy export configuration would have
produced different bytes on every program start — silently, and only for that
configuration. No U20 configuration currently sets `noise_scale_wh`, so it
never fired; it would have broken the byte-identical contract the moment one
did. Now seeded from `stable_entity_id`.

---

## I-031 — Apartments were the size of houses, and the heating target could not see it

**Severity:** High · **Raised:** Day 6 · **Status:** Fixed

The D24 electricity comparison on the first full-year run flagged one dwelling
at **19,010 kWh a year against a CSO measured figure of 5,077** for its cell —
a ratio of 3.74. It was the estate's only electrically heated home, a **C3-rated
apartment**, and 13,621 kWh of that was space heating.

**Two compounding faults, both in dwelling geometry.**

*Area per room was backwards for apartments.* `AREA_PER_ROOM_M2` gave an
apartment **26.0 m² per room** against a detached house's 24.0. An apartment's
rooms are smaller than a detached house's, not larger.

*Room counts were drawn independently of dwelling type.* The room, bedroom,
tenure, year and heating marginals were each shuffled independently, with the
stated reasoning: "so the marginals are not spuriously correlated by
construction; real dependence is introduced only where there is evidence for
it". That is a good principle, and it is not a licence to emit a dwelling that
cannot exist. It produced eight-room apartments and five-bedroom dwellings with
three rooms.

Together they put the town's **apartment median floor area at 120.8 m² against
a detached median of 129.5** — apartments almost the size of detached houses —
with a largest apartment of **285.7 m², three bedrooms, one storey**.

**Why five days of tests missed it.** Nothing compared a dwelling's size to
anything. The archetype library's plausibility band is on *specific* heat loss
(W/K/m²) and on the time constant, both of which are per-square-metre and
therefore blind to the area being wrong. The energy closure invariant balances
whatever heat the solver delivers. And 49 of the estate's 50 homes heat with
gas, so their space heat never reaches the electricity meter — only the single
electric home exposed it, and only once a public electricity target existed
(I-027). Without I-027 this would have reached the gate report.

**Fix, in three parts.**

1. `AREA_PER_ROOM_M2["apartment"]` 26.0 → 18.0, bedsit 22.0 → 16.0, with the
   ordering now asserted by a test rather than stated in a comment.
2. `allocate_rooms` allocates the area's apportioned room labels to its
   dwellings by size rank — dwelling type and bedrooms — with jitter, and then
   repairs the bedroom constraint by **swapping**. It only ever permutes the
   published labels, so the SAPS room marginal is preserved exactly; what
   changes is which dwelling gets which count.
3. `MIN_ROOMS_OVER_BEDROOMS` was set **from the data, not from recollection**.
   The first value was 2 — bedrooms plus a kitchen and a living room. A
   feasibility test on Cobh's own marginals, using the rank pairing that
   *maximises* satisfaction, refuted it:

   | margin | infeasible dwellings |
   |---|---|
   | rooms ≥ bedrooms | 2 of 5,167 (0.04%) |
   | rooms ≥ bedrooms + 1 | 272 of 5,167 (5.3%) |
   | rooms ≥ bedrooms + 2 | 764 of 5,167 (14.8%) |

   So the Census's rooms question does not have the base I assumed. The margin
   is 0, and a test pins it to that feasibility calculation so it cannot drift
   back to a guess.

**Result.** Median floor area by type: apartment **57.9**, terraced **92.5**,
semi-detached **112.9**, detached **150.1** m² — correctly ordered, where
before they were nearly equal. Town median 115.9 m², above TRS05's Co. Cork
*rental* median of 89.4 m² as it should be, since rentals skew smaller and
apartment-heavier. Zero dwellings with fewer rooms than bedrooms.

**Three sources registered to close the gap that hid it.**

`DBERNG01` — mean gas consumption by dwelling type × BER band — is the target
the estate actually needed, and had been missing entirely: in a gas-heated
dwelling the gas meter *is* space heating plus hot water, which makes it the
only direct check on the F1 physics and the heating schedule, the largest
energy term in the model. `DBERNG02` (dwelling type × construction period) is
held out, mirroring DBEREL02 exactly, so the same tuned-and-held-out split now
covers both fuels. `TRS05` supplies the only public Irish floor-area figure in
PxStat and is used as a **lower** bound, because rentals are smaller than the
whole stock.

D24 now holds **113 targets** against 57.

**A finding that came out of reading DBERNG01, and that E1 must report rather
than fix.** Gas consumption is nearly **flat across BER bands** — the spread
between best and worst band is 4 to 7% within every dwelling type, and A–B
rated detached houses use *more* gas (14,618 kWh) than F–G ones (13,292) —
while rising **84%** across dwelling types, from 7,458 kWh for an apartment to
13,730 for a detached house. That is comfort-taking: a better-insulated home is
heated warmer, longer and in more rooms, and a poorly-insulated one is heated
less because it costs more. Measured consumption tracks dwelling **size**, not
fabric quality.

The F1 physics heats to a fixed setpoint on a fixed schedule and has no
comfort-taking at all, so it must predict consumption falling steeply with the
rating — the opposite of the measured pattern. I wrote the test asserting
monotonic decrease first and the data refused it. The test now pins what the
data says, so that nobody later adjusts the physics to make consumption fall
with BER and believes they have improved it. The gate report names it as a
limitation and week 2 as the place to address it, through design 5.3's COM-B
machinery, which E1 does not wire into the thermostat.

---

## I-032 — The F1 physics applied horizontal irradiance to vertical windows, and had no path for heat to leave

**Severity:** High · **Raised:** Day 6 · **Status:** Fixed

Running the V0 invariants over the written release package failed
`physics_bounds`: **7,288 of 1,752,000 epochs (0.41%) had a living-zone
temperature outside the reachable range**, the worst at **64.3 °C**.

The bounds failure was the tail of something much larger. The distribution:

| | measured |
|---|---|
| annual median living-zone temperature | **24.6 °C** (Irish dwellings average 17–19) |
| epochs above 25 °C | 46.9%, in all 50 dwellings |
| epochs above 30 °C | 19.0% |
| epochs above 35 °C | 6.3%, in 49 dwellings |
| peak | 64.3 °C |
| August mean solar gain | **1,436 W**, against 287 W of internal gain |

**Two faults, both in the physics.**

*Horizontal irradiance applied to vertical glazing.* The solver's solar term
was `effective_aperture × GHI`, and GHI is **global horizontal** irradiance.
Windows are vertical. At an Irish summer noon a horizontal surface receives
700–900 W/m² while a vertical south façade receives 400–500 and a north one
under 150, because the sun is high. In midwinter the relationship reverses: a
low sun strikes a south wall almost square on while grazing the ground. So the
error **had the wrong sign in both seasons** — overstating summer gain by
roughly three times and understating winter gain — which is exactly why it
produced an implausible annual median alongside a winter that looked fine.

Measured on the new transposition: a summer noon's 850 W/m² horizontal becomes
285 W/m² on the glazing (ratio 0.34); a winter noon's 180 becomes 131 (ratio
0.73).

*No path for heat to leave.* Design 5.7 specifies the RC network and says
nothing about heat removal, because a heating calculation does not need to
know. The F1 model therefore had none at all: no cooling, no shading response
and no window opening — `ach_effective` was written into D16 as a constant
equal to the fabric's base rate, and that constant was the truth.

**Fix.**

`glazing_incident_w_m2` transposes DNI, DHI and GHI onto vertical planes at
the four cardinal orientations and averages them by the glazing share, using
the same isotropic-sky model the PV module already used. The orientation split
is even, which is DEAP's own assumption for a dwelling of unknown orientation
and is the conservative choice for overheating; weeks 2 and 3 can take real
orientations from the OSi building footprints.

Purge ventilation is now closed-loop **inside** the solver: above
`PURGE_START_C` the air change rate ramps up to `PURGE_ACH_MAX`, but only
while outside is cooler than inside, and only while no heat is being
delivered. It is the mechanism Ireland's DEAP overheating assessment uses, and
a ramp rather than a switch so there is no limit cycle. The energy balance
still closes at 3.9e-14.

**A third fault, found by a test I wrote for the second.** My first purge test
applied 3 kW of continuous heat with no thermostat in front of it, and the
dwelling vented at 2.12 air changes an hour *while still being heated* —
burning fuel to warm the outdoors. A thermostat has priority over a window, so
purge is now suppressed whenever heat is being delivered to the zone. The
test's scenario was unrealistic and the behaviour it exposed was not.

**A fourth, found while wiring the fix.** The stream writer recomputed D16's
`solar_gain_w` from the weather rather than taking it from the run, so with the
solver on the glazing plane and the writer on the horizontal, **the published
energy balance would not have described the run**. The incident series is now
carried on the result and used by both, and the solver reports the air change
rate it actually applied rather than leaving the writer to recompute the purge
formula — the same class of duplication.

**Why 206 tests and a full year of simulation missed all of it.** The physics
suite checked the energy balance, which closes around whatever heat the solver
delivers; the derived fabric parameters, which are per square metre and so
blind to both faults; and the solver's stability, which was never in question.
`check_physics_bounds` checked each reading against `[-15, 45] °C` and 99.6% of
readings passed. **Nothing checked the temperature the model actually
produces.** A thermal model is rarely wrong by one impossible value; it is
wrong by a distribution no dwelling has, and a per-row range check cannot see
that by construction.

Added: thirteen tests on the transposition and the purge, and a new V0
invariant `check_indoor_temperature_distribution` that checks the annual
**median**, the share of time above 28 °C and an absolute ceiling. Its band is
a declared assumption `[A]` — no CSO or SEAI table publishes measured indoor
temperatures, so there is no file in `sources/` to trace it to — and it is
deliberately wide, because its job is to refuse the implausible rather than to
calibrate. The fault it was written for would fail a band of any width.

---

## I-033 — The thermostat proportioned on the outdoor temperature and never looked at the room

**Severity:** High · **Raised:** Day 6 · **Status:** Fixed

After I-032's solar and purge fixes, `physics_bounds` passed with zero
violations and the annual median living temperature came down from 24.6 °C to
22.1. But the new distributional invariant still failed on one count, and the
monthly maxima said why: a peak near **40 °C in nearly every month of the
year** — 40.79 in January, 40.59 in February, 40.10 in March — and the worst of
them at **22:15 on 18 August**. Night-time, mid-winter peaks are not solar.

**Cause.** `_heating_schedule` computed

```
demand = clip((setpoint - outdoor_temperature) / 18, 0, 1)
heat   = emitter_output * demand
```

and applied that fraction for the whole timer window. It never referred to the
indoor temperature. Its own docstring called it "a simple timer-plus-thermostat
heating schedule" and "a crude proportional controller", and it is a
proportional controller — on the wrong variable. Proportioning on the weather
is *weather compensation*, which is real, but which modulates the flow
temperature **in addition to** a room thermostat. With the room thermostat
missing there was nothing to stop the room climbing.

Two consequences, and the second is the one that matters more:

*The room sailed past its setpoint.* Measured on a 2 °C day with a 20.5 °C
setpoint: open-loop gave a mean of 28.96 °C and a peak of 37.88 °C, where
closed-loop holds 20.15 and 20.28.

*The heating could not respond to gains at all.* A bright winter day, a houseful
of people and a running oven all raise the room temperature, and a real
thermostat backs off. This one did not, so solar and internal gains were
delivered **on top of** full heating rather than displacing any of it. Heat
delivered on that same day: **216 kWh open-loop against 52 kWh closed-loop**, a
factor of four within the timer windows.

**Fix.** The thermostat moved **inside the solver**, because it has to see the
room and the room is what the solver computes. `_heating_schedule` now returns
the emitter output *available* each minute and the setpoint being asked for;
the kernel computes the call for heat from `(setpoint − T_room) / band` each
minute, with a 1.5 K proportional band — the wide end of a real thermostat's
range, chosen because the solver steps at one minute and a narrower band would
chatter without changing the daily energy. The sleeping zone now carries a 3 K
setback, which is what people do and what makes two zones worth having.

The solver also reports the heat it **actually delivered**, as distinct from
the capacity it was offered, and D16's `heat_delivered_w` and the HVAC
electricity both use that. Using the capacity would have charged every home
for heat it never used, and would have made both the electricity and the gas
comparisons wrong by the thermostat's duty cycle.

Open-loop control is still reachable (`setpoint = -999`) and still tested, so
a negative control can demonstrate the 40 °C peaks rather than describe them.

**On the direction of the correction.** This makes simulated space heat *fall*,
which moves it further below DBERNG01's gas cell, not closer. That is the
honest result and it is not evidence the fix is wrong: the gas cell contains
hot water, gas cooking and boiler losses, none of which E1 models, and the
remaining gap is reported with those four causes named rather than closed by
putting the overshoot back.

---

## I-034 — Negative-control magnitudes were chosen, not derived; I-020 was the wrong response

**Severity:** High · **Raised:** Day 7 · **Status:** Fixed, with a design amendment

I-020 recorded that NC-D2-03's 10% marginal shift sits below its check's
resolution, and filed it as a **recognised limitation**. That was the wrong
response, and the reason is worth stating plainly: *a negative control whose
magnitude sits below its check's resolution cannot fail, and a control that
cannot fail tests nothing.* Recording it as a limitation left design 9.3's
"marginals shifted 10%" nominally covered by a control that was incapable of
covering it, and left the gate reporting a number — `NOT_DETECTED` — that
nobody could act on.

**The amendment.** A negative control's magnitude must be set from a **power
analysis against its own check's resolution**, not taken from the design's
prose or chosen for plausibility. Every control now carries a declared
threshold and margin, audited in `v1/evidence/control_power_audit.json` and
enforced by `test_no_control_is_below_its_own_check_s_resolution`.

### The power analysis (D-026, `v1/evidence/marginal_power_analysis.json`)

| Question | Answer |
|---|---|
| Smallest shift the single-realisation band can see, with no noise | **12.82%** = 34.3 households |
| What the planted 10% shift produces | max \|z\| **2.1332** against a critical 2.7344 — below the band |
| Power of the same check on a genuine random draw of 1,092 | **42.6%** at 10%; 81.5% at 15%; 98.4% at 20% |
| Households needed for 95% power at 10% | **3,664** (Cobh has 5,257; the scaled town has 1,092) |
| False-positive rate at zero shift | 0.0595 against a declared α of 0.05 — the band is calibrated |

So 1,092 households simply do not carry the information to resolve a 10%
shift, whatever check is applied: the magnitude was the problem, not the care
taken in applying the check.

### What made a fix possible

The generator is **deterministic** in this marginal. Across 40 independent
seeds, in both the correct and the shifted configuration, the across-run
standard deviation of the household-size shares is **1.7e-16** — it reproduces
its control totals exactly. Household type is the same. Age band and sex do
vary (SD up to 0.0032 and 0.0074).

That is the whole key. The acceptance band is the multinomial sampling error of
a 1,092-household *draw*, about 0.013 in proportion near p = 0.25. The
generator's own run-to-run error is zero. **The band is roughly 28 times wider
than the precision of the thing it is testing**, so a bias comfortably inside
it is still an unambiguous defect in the generator. The band is not wrong — it
is the right band for "could a town of this size look like this by chance" —
it is the wrong band for "is the generator biased", which is the question a
shifted-marginal control is asking.

### The ensemble generator-bias check

`ensemble_marginal_acceptance` tests the ensemble mean of K runs against what
the generator is contracted to reproduce, at the generator's own measured
run-to-run precision: standard error `max(sd/√K, half a household / n)`, with
a Bonferroni **t** band on K−1 degrees of freedom. `marginal_acceptance` is
untouched and keeps its own control, NC-D2-05, whose 40% shift is above the
12.82% resolution and which demonstrates the band works where it applies.

**K = 20**, and the minimum of 4 has two independent derivations that agree:
the information requirement (3,664 / 1,092 = 3.36) and the measured
power/false-positive rates bootstrapped over 40 correct and 40 shifted runs.
20 rather than 4 because the standard deviation is estimated from the same K
runs, so the band is a t quantile: 6.895 at K = 4 against 3.074 at K = 20,
where the asymptote is 2.734.

Stated in households, which is the form that makes the two checks comparable:

| | fires at |
|---|---|
| Single-realisation band | **34.3 households** |
| Ensemble check, K = 20 | **1.5 households** |
| The planted 10% shift moves | **26.8 households** |

which is exactly why one check cannot see it and the other cannot miss it.
Measured power **1.0**, false-positive rate **0.0** — and both are exact
rather than Monte Carlo estimates, because with zero across-run variance every
bootstrap draw of K runs gives the identical statistic.

### The false-positive control changed the design (D-027)

The literal instruction — test the ensemble mean against SAPS — **fails**, and
measurably. Once the standard error shrinks to the generator's own precision,
the deliberate person-total repair sits about **55 standard errors** from raw
SAPS, and a *correct* population is rejected at every K from 4 upwards
(max \|z\| 54.9 against a t band of 6.90 at K = 4). The repair moves the
two-person share by −0.0251 and the three-person share by +0.0228 so the
scaled town satisfies both of R03's ranges, which Cobh's real 2.6913 persons
per household makes jointly unsatisfiable otherwise (I-012, D-010) — and that
is **larger than the 10% fault being planted**.

So the ensemble tests the generator against the target the declared procedure
produces, and the target's own deviation from SAPS is bounded separately at
2.7344 (currently 1.9827) and reported. Two questions, two references, both
checked. The false-positive control is what forced this: without it I would
have built a check that fired on everything and called it sensitive.

### The audit of every other control (point 4)

18 audited — 16 deterministic, 2 statistical. **None is below its own check's
resolution.** The split matters, because a single notion of power does not
apply to both: for a check whose detection is an exact predicate (a field name
matches a pattern; two presence intervals overlap; a derived heat loss exceeds
a published ceiling) the resolution is the threshold and the quantity to report
is the margin.

Margins, worst first:

| Control | Kind | Margin | Note |
|---|---|---|---|
| NC-D2-04 | deterministic | **1.13×** | 7.34 against a 6.5 W/K/m² ceiling. The thinnest, deliberately: the control exists to show the ceiling bites, and its earlier 400 m² version came out *inside* the range. Flagged by the audit as the one to watch. |
| NC-D2-02 | deterministic | 3.0× | 91 days against a 274-day threshold |
| NC-D2-05 | deterministic | 3.1× | 40% shift against the 12.82% resolution |
| T10 planted arm | statistical | 8.1× | 44.66% first-position share at n=7,516 against a 27.41% minimum detectable at 95% power |
| NC-D3-02 | statistical | 9.2× | 70% first-position share at n=4,000 against 29.9% |
| NC-D2-03 | deterministic | 16.3× | 25 households against 1.5 |
| NC-D1-01 | deterministic | 22× | 22 of 24 entities change against one needed |
| NC-D4-02 | deterministic | 30× | 3% leak against a 0.1% tolerance |
| NC-D4-01 | deterministic | 60× | 60-minute overlap against one minute |
| NC-D1-02/03/04/05, NC-D3-01, NC-D5-01 | deterministic | exact | name- or enum-predicate; no magnitude exists to get wrong |
| NC-D5-02, NC-D6-01 | deterministic | ~10¹⁰–10¹⁴ | exact-equality checks, so effectively unbounded resolution |

**T10 was audited although it is an E1-6 criterion rather than a negative
control**, because the same question applies and a planted effect below its
test's resolution would make T10 pass for the wrong reason. It is not: the
margin is 8.1×, and the clean arm's 126,007 responses give chi-square 0.978 at
p = 0.81, so the test is not simply always firing.

---

## I-035 — The week 2/3 brief cites design content that does not exist in the frozen r3

**Severity:** Medium · **Raised:** Week 2 preconditions · **Status:** Open, needs Brian's ruling

The brief's precondition 3 instructs: *"Re-read
docs/Baile_Nua_Technical_Design_Review_r3.md, including sections 6.3 to 6.5,
7.8, 7.9, 8.2 and **9.6**, and decisions **U22 to U27**."*

Checked against the frozen document:

| Cited | Present in r3? |
|---|---|
| 6.3 Delivery packages | yes (line 545) |
| 6.4 What a real dataset would also contain | yes (564) |
| 6.5 Observation rules for non-sensor datasets | yes (581) |
| 7.8 Privacy inference risk of exported data | yes (721) |
| 7.9 Blind consumer evaluation protocol | yes (749) |
| 8.2 Execution model | yes (790) |
| **9.6** | **no — section 9 runs 9.1 to 9.5** |
| **U22 to U27** | **no — section 11 declares U01 to U21 only** |

`grep` for `U2[2-7]`, `9\.6`, `revision 4` and `r4` across r3 returns nothing.
No newer design document exists: `docs/` holds only r3 and its source PDF,
`/Users/brianoregan/Desktop/Baile Nua` contains images, and
`/Users/brianoregan/Documents/GitHub/bailenua` is a website repository with an
empty `docs/`.

**Why this is not blocking, and what it means.** The *content* of U22 to U27 is
supplied in full in the brief itself, approved 9 October — one day after r3 was
frozen on 8 October. So they are a **decisions addendum**, not missing design
content, and they are recorded as such in DECISIONS.md (U22–U27) with the brief
as their source rather than the design document. Work can proceed on them.

Section 9.6 has no content anywhere, so there is nothing to read. Weeks 2 and 3
are specified by **9.4** (which exists) and by the brief's own week-by-week
list, which is more detailed than 9.4. Nothing in the brief appears to depend
on a 9.6 that would contradict 9.4.

**What needs Brian's ruling.** Whether r3 should be amended to a revision 4
carrying U22–U27 and a section 9.6, so that the architecture-is-frozen rule has
a single document to point at. At present the binding specification is split
across a frozen r3 and a brief, and the E2 gate report will have to cite both.
Recorded rather than resolved, because amending a frozen design document is not
mine to do.

---

## I-036 — U24's `<SSD_PATH>` is unsubstituted, and no external drive exists

**Severity:** CRITICAL for the week 3 full-town run · **Raised:** Week 2 preconditions · **Status:** Open, blocks week 3 step 5

U24 instructs: *"put work/ and large v1 data on the external drive at
`<SSD_PATH>`. If the projected package still doesn't fit, stop before the full
10-year run and report."* `<SSD_PATH>` is an unsubstituted placeholder, exactly
as `<MIMIC_PATH>` was in week 1 (I-004).

**There is no external drive attached.** `/Volumes/` holds one candidate,
`Vault`, and it is not a drive:

```
Protocol:                  Disk Image
Device Location:           External        <- the disk-image driver's claim
Removable Media:           Removable       <- likewise
APFS Physical Store:       disk4s2
image-path:                /Users/brianoregan/Vault.sparsebundle
```

It is a 536.7 GB **encrypted sparse bundle whose backing file lives on the
internal disk**. `df` reports 536 GB free on it and 74 GiB free on `/` — and
the 536 GB is fiction, because every byte written into the bundle consumes
internal space. `diskutil` reporting "External" and "Removable" is the disk
image driver describing itself, not a physical device, which is precisely the
trap I-017 was (a file that loads cleanly and is the wrong thing).

**The arithmetic, from the E1 measurement.**

| | |
|---|---|
| Measured estate-year storage | 724.3 MB for 50 homes × 365 days |
| Town-year projected (×21.84 homes) | 15.45 GB, **23.2 GB** with U21's ×1.5 margin |
| **Ten-year town package** | 154.7 GB, **232.0 GB** with margin |
| Free on the internal disk | **74 GiB** |
| Free on a genuinely external drive | **none attached** |

So the ten-year package is **about 3.1× the space available**, and U07's
measures do not close that gap: U07 already applies (D-009 declined to store
1-minute building state on Day 1), and the 724.3 MB/estate-year already
reflects it. The dominant dataset is D18, the 1-minute observation layer, at
66.1 million rows and 531 MB per estate-year — and D18 is an observable
deliverable, so it cannot be dropped the way physics state was.

**Action taken.** Per U24's own instruction I will stop before the full 10-year
town run and report rather than attempt it. Weeks 2 and the rest of week 3 are
unaffected in storage terms: a ten-year run on the 50-home slice projects to
about 10.6 GB with margin, and a one-year full town to 23.2 GB, both of which
fit.

**What is needed.** Either a real external drive path, or a decision on which
of these to accept — reduce D18's interval for the town (a 15-minute D18 would
cut the package roughly fourfold), keep full-rate D18 for a labelled subset of
homes only (which 6.4 item 6 already contemplates), or shorten the simulated
span. Each changes what the 7.8 privacy inference test can be run against, so
it is not purely an infrastructure choice.

---

## I-037 — No "family of towns" mode: the generator is one calibrated town

**Severity:** Low (scope note) · **Raised:** Week 2 preconditions · **Status:** Out of scope by decision

Measured during the D-026 power analysis: the generator reproduces its control
totals **exactly** across seeds. Across 40 independent seeds, in both a correct
and a deliberately biased configuration, the across-run standard deviation of
the household-size shares is 1.7e-16, and household type is the same. Age band
and sex do vary (SD up to 0.0032 and 0.0074).

That is correct for the thing E1 and E2 are building: **one** calibrated town,
whose marginals match Cobh's published distributions as closely as
integerisation allows. It is recorded because it has two consequences a later
reader would otherwise have to rediscover.

1. **An ensemble over seeds cannot estimate sampling uncertainty** in the
   fitted marginals, because there is none. This is why the ensemble
   generator-bias check judges at the integerisation floor rather than at an
   across-seed standard error (D-026), and why "run it with more seeds" is not
   a route to tighter confidence intervals on anything derived from a fitted
   control total.

2. **Any statistic that needs between-town variation cannot be produced.**
   Confidence intervals that treat the town as one draw from a population of
   towns, and any ML experiment that wants independent synthetic populations
   rather than independent households, both need a mode that does not exist:
   one that samples the marginals themselves — from their own sampling
   distribution at Cobh's real household count — before fitting.

Declared **out of scope for now** by decision (week 2/3 brief). Building it
would be a change to the synthesis contract rather than an addition to it: R04
requires every SAPS marginal to sit inside the sampling-error band, and a
family-of-towns mode would deliberately spend that band. It should be a
decision with its own acceptance criteria, not a flag.

---

## I-038 — Design revision 4 is not present; DECISIONS.md Part C retained

**Severity:** Medium · **Raised:** Week 2 · **Status:** Open, needs the file

I-035's resolution was: *"design doc r4 is now in docs/
(Baile_Nua_Technical_Design_Review_r4.md). It contains 9.6, U22-U28 and
Appendix A; use it as the single reference and retire DECISIONS.md Part C into
it."*

**The file is not there, and does not exist anywhere on this machine.**

```
docs/ holds:  Baile_Nua_Technical_Design_Review_r3.md   (8 Oct 19:59)
              DECISIONS.md  E1_gate_report.md  ISSUES.md  PROGRESS.md
              source_pdf/   (r3 markdown + PDF)
```

A filesystem search for `*r4*`, `*design*review*` and `*Technical_Design*`
across `~`, `~/Desktop`, `~/Documents` and `~/Downloads` finds only r3 and four
earlier Downloads copies, all dated 8 October between 19:26 and 19:50 and all
*smaller* than r3 — they are the drafts that led to it. Content search is
decisive: **no file on this machine contains `U22`–`U28`, a section `9.6`, or
an `Appendix A`.** The newest candidate, "Baile Nua Technical Design Review
(3).md", is 116,452 bytes against r3's 122,436.

**Part C was NOT retired, deliberately.** Retiring it into a document that does
not exist would delete the only record of U22 to U28 — decisions that govern
every remaining step of weeks 2 and 3. The instruction's purpose was to remove
a duplicate, and there is no duplicate to remove. Part C now carries U28 as
well, and a note at its head saying it is provisional and to be folded into r4
when r4 arrives.

**What is needed.** The r4 file. Until then the binding specification is r3
plus two briefs, and the E2 gate report will cite all three. Nothing is
blocked: U22 to U28 are each quoted in full in the briefs and are recorded
verbatim in Part C, so the work proceeds on their text rather than on a
reference to a missing document.

### I-038, second check (week 2, after a second assurance that r4 is present)

Re-verified on instruction. **Still absent**, and the evidence is now stronger
than a filename search:

* `docs/` is unchanged: r3 (8 Oct 19:59), DECISIONS.md, E1_gate_report.md,
  ISSUES.md, PROGRESS.md, `source_pdf/`. No r4.
* **No file anywhere under `~` (depth 4) has been modified in the last 90
  minutes.** If r4 had been saved, something would have changed.
* Content search across every `.md` and `.txt` under `~` to depth 5: the only
  files containing the string `U28` are this file, `docs/DECISIONS.md`, an
  unrelated `MasterPlanAI_Info/06_benchmarks/FINDINGS.md`, and
  **`~/.claude/paste-cache/e67e228f41da4548.txt`** — the cached text of the
  brief that was pasted into the conversation.

That last hit is the likely explanation: U22 to U28 and the 9.6/Appendix A
references exist as **composed chat text**, not as a file on this machine. They
may have been written in a chat window, or saved on a different machine, or the
save may not have completed.

**Consequences, unchanged.** Part C is retained and is still the only record of
U22 to U28; retiring it would delete them. The binding specification remains r3
plus the briefs, and the E2 gate report will cite all three. Nothing is blocked
— each decision is quoted verbatim in Part C — but two things cannot be done
until the file exists: making r4 the single design reference, and the wording
comparison between Part C and r4 that was asked for. There is no second text to
compare against.

---

## I-039 — Three U27 plausibility families have no published Irish reference

**Severity:** Medium · **Raised:** Week 2 step 1 · **Status:** Open, declared gap

U27 requires every major output to be checked against "a published Irish
reference in `sources/`". Six of the nine families named can be. Three cannot,
and this records which, what was searched, and what the nearest available
substitute is — because a plausibility suite that silently omitted them would
read as coverage it does not have.

The suite therefore reports **two counts, never one**: how many checks passed,
and how many of those were against a published reference. A check with a
declared band but no source (`PL-TEMP-01`) is still evaluated and still
reported as a pass, with `sourced=False`. A check with neither is reported
`NOT_EVALUABLE` and names this issue.

### What was searched

The whole CSO PxStat catalogue — 13,086 tables — by regular expression on
every label, for `appliance`, `end.use`, `energy use`, `lighting`, `cooking`,
`water heating`, `electric vehicle charg`, `charge point`, `heat pump`,
`peak demand`, `maximum demand`, `load factor`, `system demand`,
`indoor temperature` and `room temperature`.

### The three gaps

**`PL-APPLSHARE-01` — appliance energy shares.** PxStat publishes appliance
**ownership** (HAS02, now registered and checked by `PL-APPL-01`) but no
end-use energy breakdown for Irish dwellings. SEAI's residential-sector
reports carry one, as narrative PDF tables rather than a machine-readable
series, so it cannot be registered as a source and read at run time under the
brief's rule that every calibration number traces to a file in `sources/`.
*Nearest substitute in place:* the total is bounded by `PL-ELEC-01`, so a
share cannot be wrong without some other check noticing the sum.

**`PL-EVHP-01` — EV and heat-pump consumption.** PxStat has EV **ownership**
(NTA43–49, HEBEU55–90), public **charge-point** consumption (MEC08) and
heat-pump **penetration** (EBQ02, already registered), but no domestic kWh for
either. *Nearest substitute in place:* DBEREL01's A–B cells are heat-pump-heavy,
so `PL-ELEC-01` exercises heat-pump homes indirectly. Nothing checks EV
charging energy.

**`PL-PEAK-01` — peak demand and load factor.** No published Irish
per-household peak exists. MEC05 and MEC06 give annual consumption and its
distribution but no coincident peak, and ESB Networks' after-diversity maximum
demand figures sit in the distribution code as narrative text. Load factor
needs both terms, so neither is checkable from PxStat alone. *Nothing in place.*
This is the gap that matters most for week 3's S11 network work, where feeder
loading is an acceptance criterion — a simulated peak that is wrong by a factor
would pass every check now in the suite.

### What would close them

Each needs a machine-readable public series, or a decision to accept a declared
band with its own issue, as `PL-TEMP-01` does. The peak-and-load-factor gap is
the one to close before the S11 network claims in week 3; EirGrid's system
demand data is public and downloadable and gives a *system* load factor, which
bounds the aggregate but not the household.

---

## I-040 — Seven appliance ownership priors were assumptions that did not need to be

**Severity:** Low · **Raised:** Week 2 step 1 · **Status:** Fixed (now checked)

`OWNERSHIP_PRIORS` has carried all nineteen appliance ownership rates as
declared assumptions `[A]` since Day 5, with the comment: *"SAPS publishes no
appliance ownership, and the design defers it to 'national ownership evidence'
in WP1."*

SAPS does not publish it. **SILC does.** CSO table HAS02, "Households who
possess a household appliance", gives the share of households possessing a
washing machine, clothes dryer, dishwasher, fridge, fridge with separate
freezer, deep freeze and microwave, by year to 2019.

Seven of the nineteen priors stop being assumptions. Four map exactly onto the
modelled appliances and are now checked by `PL-APPL-01`; all four sit inside
the band on the first comparison, so no value needed changing — which is worth
stating, since a check that forced a change would have been a calibration and
this is a validation.

The lesson is narrower than "search harder". The Day-5 comment named the right
absence (SAPS) and inferred a wider one (no public source). The U27 sweep that
found HAS02 took one regular expression over the catalogue. **An `[A]` flag
should record what was searched, not only that something is assumed** — the
flag as written was true and still left a public source unused for four days.

HAS02 is declared `intended_use="validation"` and `exposure="none"`, and must
stay so: the priors were set before it was found, so it can score them. If a
prior is ever adjusted against it, its declaration changes with it.

## I-041 — A declared source with a mappable row left unmapped

**Severity:** Medium · **Raised:** U30 sweep, 9 Oct 2026 · **Status:** Fixed

I-040 recorded that an `[A]` flag should say what was searched, because the
Day-5 comment on `OWNERSHIP_PRIORS` named the right absence (SAPS) and inferred
a wider one, leaving HAS02 unused for four days. U30 found the same failure one
level in, inside the source that taught the lesson.

HAS02 publishes **nineteen** appliance types. The map written on 9 October used
**four**. Sitting beside them, unmapped, was `Colour television` at 96.3% for
2019 — against a model prior of 0.96, the closest agreement of any appliance in
the set. The television prior stayed a declared assumption for no reason other
than that nobody enumerated the source's own categories.

So the gap is not only "has a source been found" but "has every row of the
found source been used". The two failures are the same shape and neither is
caught by reading the code's comments:

| | I-040 | I-041 |
| --- | --- | --- |
| What existed | HAS02, undeclared | HAS02, declared and fetched |
| What was wrong | the source was not looked for | the source was not enumerated |
| What found it | one regex over the catalogue | listing the source's own categories |

**Fixed.** `_HAS02_MAP` now maps five appliances, PL-APPL-01 scores five, and
the U30 sweep's A-04 entry records the correction. The general remedy is the
test that accompanies it: a check whose reference publishes a category list
should be read against that list, not against a hand-written subset.

## I-042 — The appliance ownership slopes are twice the published ones

**Severity:** Low · **Raised:** U30 sweep, 9 Oct 2026 · **Status:** OPEN
(passes its declared band; recorded so it is not absorbed)

HS219 publishes appliance ownership by household size, which is exactly what
the `per_person` slopes in `OWNERSHIP_PRIORS` assume — the code's comment on
them read *"the sub-linearity is not in doubt, only its slope"*. PL-APPLSIZE-01
now measures it, and all five mapped appliances sit inside the band declared in
advance (±0.05 per person). But passing is not the same as agreeing:

| Appliance | Model `per_person` | HS219 slope | Ratio |
| --- | --- | --- | --- |
| dishwasher | 0.060 | 0.0293 | 2.05 |
| tumble dryer | 0.050 | 0.0255 | 1.96 |
| television | 0.010 | 0.0040 | 2.50 |
| washing machine | 0.000 | 0.0016 | flat, correctly |
| fridge-freezer | 0.000 | −0.0023 | flat, correctly |

The declared slopes are about **twice** the published ones wherever there is a
slope to compare, and the direction is consistent rather than scattered — which
is what makes it worth recording rather than noise. Where HS219 is flat the
model is flat too, which is the part a declared constant is most at risk of
getting wrong, so the shape is right and the magnitude is high.

Not changed here, for the reason that makes the measurement worth anything:
HS219 is declared `intended_use="validation"` and the slopes were set on Day 5,
before it was found, so it can score them. Fitting them to it now would make
the source calibration and its declaration would have to change with it
(I-040's rule). Whoever next touches these values should halve them against
HS219 and re-declare the source accordingly.

## I-043 — U30 cannot close I-039; peak demand is not in PxStat

**Severity:** Medium · **Raised:** U30 sweep, 9 Oct 2026 · **Status:** OPEN,
and the blocking item before S11

I-039 recorded three plausibility families with no published Irish reference.
U30 searched all three against the whole 13,086-table catalogue and the result
splits them:

* **PL-APPLSHARE-01** (appliance share of electricity) — confirmed absent. The
  CSO publishes appliance ownership and total household electricity, never
  electricity *by* appliance. SEAI's end-use breakdown is narrative PDF.
* **PL-EVHP-01** (EV and heat-pump kWh) — confirmed absent, and the shape of
  the gap is now precise: EV **ownership** by age and sex (NTA43, NTA76),
  willingness to buy (NTA48/49), public charge-point consumption (MEC08) and
  heat-pump **penetration** (EBQ02) are all published. Domestic kWh for either
  is not. Ownership is not consumption.
* **PL-PEAK-01** (household peak and load factor) — **zero hits** for `peak
  demand`, `peak load`, `maximum demand`, `load factor`, `ADMD` and `after
  diversity`, every one of them. PxStat is not where this lives.

And that third negative result is what sent the search to the network operator,
where the quantity turned out to be published in full. **I-039 is now closed at
the aggregate level** — see the entry below. What remains open under this issue
is narrower and permanent: an **individual dwelling's** peak needs smart-meter
or sub-metered microdata, which in Ireland means CER/ISSDA, which the brief
forbids. So PL-PEAK-01 checks after-diversity load, which is the right
instrument for feeder loading and the wrong one for one house, and the
distinction is recorded in the check itself so its result can never be read as
a per-dwelling one (sweep flags A-29 and A-30).

## I-039 — CLOSED at the aggregate level: ESB Networks Standard Load Profile LP1

**Severity:** Medium · **Raised:** week 2 step 1 · **Status:** Closed for the
aggregate; the per-dwelling half stays open under I-043

"Feeder loading must not reach E2 unchecked." It will not.

ESB Networks publishes the Irish retail market's settlement load profiles
through the Retail Market Design Service. **LP1, "Urban Domestic 24 Hour"**,
gives a Demand Energy Coefficient for every quarter-hour of the year, unitised
so the year sums to 1.0 — which is what makes it usable without borrowing a
denominator from anywhere:

    load factor = mean coefficient / peak coefficient

Measured from the **2022** file (the same calendar year as T0, taken
deliberately: PL-AREA-01 was once found validating a 2022 town against NDA08's
2026 figure, and a load profile is re-derived annually from measured data):

| | LP1 2022 | the E1 slice (50 homes) |
| --- | --- | --- |
| Load factor | **0.4129** | 0.2565 |
| Annual peak / mean | **2.422** | 3.899 |
| Mean-day peak hour | **18:00** | 18:00 ✓ |
| Mean-day trough hour | **04:00** | 00:00 |
| Overnight taper (00:00 ÷ 04:00) | **1.721** | 0.950 ✗ |

Three things had to be got right, and two of them only after getting them
wrong first.

**The class.** LP1 is the plain urban domestic profile. LP2 and LP4 are the
night-saver variants, whose overnight storage-heating load lifts their load
factor to about 0.60 — and the *smart* day/night/peak urban class (LP25) is the
same story, with an overnight above its own midday. Comparing a model against
one of those would make a too-smooth model look right, so the test asserts the
sheet is LP1 and that LP2 is still distinguishable from it.

**The export view.** D19 holds **four** configurations of the same energy:
`home_15min`, `home_30min`, `compliance_only` and a pre-summed
`estate_aggregate`. A first version of the check summed D19's rows without
choosing one, counted the estate roughly four times, and reported **9.2 kW per
home** — against the run diagnostics' own independently computed 1.49 kW. The
check now selects one view by name, refuses a D19 with no per-home view, and
refuses one that mixes interval lengths, since a load factor is
resolution-dependent. 15-minute is read rather than D18's 1-minute, both to
match LP1's resolution and because 15-minute views are what U28 keeps for every
home, so the check survives to the ten-year package.

**The timing statistic.** LP1 2022's *annual* peak quarter-hour is 2022-12-27
at 13:45 — Christmas-week midday cooking, not an evening peak. A "the peak must
fall between 16:00 and 21:00" test would have been written and would have been
wrong about the reference itself. The mean diurnal shape is used instead, and
LP1's own annual peak date is asserted in a test so the reasoning stays visible.

PL-PEAK-01 is now sourced (`esbn.rmds.slp_indexes_2022`), evaluable, and it
**fails** — see I-044. That is the check working on its first run.

## I-044 — The simulated town has no overnight taper

**Severity:** Medium · **Raised:** PL-PEAK-01's first run, 9 Oct 2026 ·
**Status:** OPEN, a known and declared failure

PL-PEAK-01 fails on one of its three terms. Real Irish domestic demand declines
through the small hours because people go to bed: LP1 falls from **0.77×** the
daily mean at midnight to **0.45×** at 04:00, a taper of 1.72. The simulated
town is **flat** across those hours — 0.44× at midnight, 0.46× at 04:00, a
taper of 0.95. Its hours 00:00 to 06:00 sit within 0.03 of each other.

| Hour | LP1 2022 | the E1 slice |
| --- | --- | --- |
| 00:00 | 0.77× | 0.44× |
| 02:00 | 0.53× | 0.46× |
| 04:00 | 0.45× | 0.46× |
| 06:00 | 0.58× | 0.47× |
| 18:00 | 1.63× | 2.13× |

The other two terms pass: the load factor is 0.2565, inside the upper bound,
and the mean-day peak hour is 18:00, matching LP1 exactly. So the model gets
the evening right and the night wrong, which points at late-evening occupancy
and the appliance standby floor rather than at the physics — the town appears to
drop to a constant baseload the moment the day's activities end, instead of
tapering as televisions, lights and cooking wind down through the late evening.

**The statistic was chosen after a first attempt failed honestly.** The check
first tested the trough *hour*, and the model's argmin landed on hour 0 against
LP1's 04:00 — a four-hour "error" resting on a 0.02 difference between hours
that are indistinguishable. The argmin of a near-constant function is not a
statistic. It was replaced with the taper *ratio*, which says what the argmin
only hinted at, and the check still fails — so there is no question of the band
having been chosen to produce a verdict.

**Not fixed here.** The fix is behaviour-model work: late-evening activity
decay and the standby floor, which week 2 step 4 owns. It is recorded as a
declared failure rather than absorbed:

* the suite reports `FAIL` and the artefact records it;
* `KNOWN_FAILURES` in `tests/test_plausibility.py` names this check and this
  issue, so a *new* failure still breaks the suite;
* that same list fails if the check ever starts passing, so the entry cannot
  outlive the defect.

**It must be fixed before E2, not waived.** A town with no overnight taper
understates how much of its load is genuinely sheddable at night and overstates
the flatness of the baseload, both of which matter to the RL work the dataset
exists for.


## I-045 — Hot water volume rests on an unsourceable shower duration

**Severity:** Low · **Raised:** U25, 9 Oct 2026 · **Status:** OPEN, bounded and
checked

Hot water comes out at **60.1 litres per person per day** on the 50-home year,
against DEAP's published water-efficiency target of **125 litres per person per
day for all water, hot and cold**. So hot water is **48%** of the all-water
target — above the 35–40% that household hot water usually represents, though
less far above than the 55% an early three-day sample suggested — and the figure
rests on one assumption that cannot be sourced.

**What is sourced:** DEAP applies a minimum of 6 L/min to every mixer shower.
**What is not:** how long the water runs. DEAP takes shower duration as an
assessor input and publishes no default, and U30 found zero PxStat hits for
`hot water`, `water heating` and `immersion`. The activity engine gives time in
the *bathroom*, which is not the same quantity — charging 6 L/min across a
25-minute bathroom episode made 150-litre showers and about 800 litres a day
per household, 70–85% of all hot water, before the two were separated.

**Why it is not tuned.** The honest arbiter is the gas meter. DBERNG01 contains
hot water, so if the volume were badly wrong the meter comparison would
overshoot — and it comes in at **0.832** of the published cell, below it rather
than above. That bounds the volume from the direction that matters without
fitting anything to a number taken from memory. `PL-DHW-01` bounds it from the
other side against DEAP's own per-person target.

The lever is `shower_water_minutes_median` in `data/deap_hot_water.yaml`,
flagged `[A]` with the search recorded. If a published Irish or UK shower
duration turns up, it retires this; until then the pair of bounds is what the
claim rests on, and the claim is no stronger than that.

## I-046 — A phrase search concluded "nothing published" and was wrong

**Severity:** Medium · **Raised:** U25 / U30 coverage test, 9 Oct 2026 ·
**Status:** Fixed, and fixed by a mechanism rather than by noticing

This is the I-040 lesson landing for the third time, and the first time
something other than a person caught it.

U30's sweep searched PxStat for `cooking fuel` and `gas cooking`, found nothing,
and recorded gas cooking as having no published Irish reference. The CSO
publishes six tables on it — **HEBEU31 to HEBEU36, "Main fuel used for cooking
in households"**, broken down by sex, age, region, urban/rural, dwelling type
and occupancy. The words are all there, in the other order. A phrase search
could not see them; the plain term `cooking` matches all six.

| | What was searched | What existed |
| --- | --- | --- |
| I-040 | nothing — the comment inferred absence from SAPS | HAS02, undeclared |
| I-041 | HAS02, declared but not enumerated | `Colour television` unmapped in it |
| **I-046** | `cooking fuel`, `gas cooking` — a phrase | tables titled *fuel used for cooking* |

**What caught it.** Not a person. U25 added three `[A]` flags to
`data/deap_hot_water.yaml`;
`test_every_a_flag_in_the_tree_is_accounted_for` failed because no sweep entry
named them; writing those entries required declaring search terms; and the
natural plain term for the subject returned six tables. The chain from "add an
assumption" to "find the source you said did not exist" was mechanical.

**What it bought.** More than the retirement. HEBEU34 gives the urban
cooking-fuel split and HEBEU106 the urban heating-fuel split from the same
survey and year, so the share conditional on a gas connection is *derived*
rather than assumed: 14% of urban households cook with gas alone and 9% with a
combination, against 48% heating with gas — **0.292** and **0.188** of
gas-connected dwellings. The declared 0.45 it replaced was close, which is
reassuring and beside the point.

The real gain is that the split is three-way. "Combination of electricity and
gas" is not a residual category: it is a gas hob with an electric oven, the
common real arrangement, and the model already priced hob and oven separately
so it can assign exactly that.

Two caveats travel with the derivation rather than being buried: the
denominator is the share *heating* with gas, which is a lower bound on
connections, so the conditional shares are **upper** bounds — biasing gas
cooking up, which biases the gas-meter comparison up, which DBERNG01 would
catch rather than conceal. And the tables are 2024 against a T0 of 2022, so
they are used for a structural share and not a level.

**The general lesson, for the sweep's own method:** a phrase search tests one
word order. The sweep already knew that dimension labels matter more than
titles (that is how HAS02 and HS023 were found); it now also knows that the
term should be the subject noun, not the phrase someone expects to read. The
`BROAD_TERM_LIMIT` guard exists precisely so a short plain term is affordable.

## I-047 — Boiler vintage was read from the dwelling's build year

**Severity:** High · **Raised:** U22 ablation, 9 Oct 2026 · **Status:** Fixed

DEAP Table 4b is indexed by the **boiler's** age — its rows are "Gas boilers
1998 or later", "pre-1998 with fan-assisted flue", "floor mounted, pre-1979".
U25's gas accounting read the **dwelling's** build year into those rows, so a
house built in 1975 was given a 55%-efficient floor-mounted boiler in 2022.

A house built in 1975 is on its second or third boiler. Gas boilers last
roughly 15 to 25 years, so by T0 almost every pre-2000 dwelling has a post-2000
appliance.

**How it surfaced.** Not by inspection. The U22 ablation ran on the mixed-age
slice and the simulated-to-published gas ratio came out at **2.11**, against
**0.83** on the modern E1 estate. A model that overshoots only where the
dwellings are old is not making a random error, and the per-dwelling rows showed
0.55 efficiencies on 1971–80 houses. The error bites exactly where U22 is
measured, which is why U25's own validation on a modern estate could not see it.

**Fixed** by modelling replacement: boiler vintage is drawn uniformly over a
~19-year service life back from T0 (the renewal-process result for a flat
replacement hazard, which needs no further assumption), floored at the build
year for dwellings newer than one service life, and condensing from 2008 when
Ireland's Part L required it for replacements. Mean efficiency is then **0.80 to
0.83 for every construction era**, and the ratio falls from 2.11 to 1.46.

**A claim it retracts.** The U25 write-up said Table 4b's 55–83% spread was an
era confound U22 would have to separate comfort-taking from — *"the same heat
duties cost 19,748 kWh at the meter in a 1960 home and 13,292 in a 2015 one, a
1.49× difference from plant alone"*. That was an artefact of this error. Plant
efficiency is nearly **flat** across the stock once replacement is modelled, so
whatever era difference remains in the gas comparison is not the boiler. The
original paragraph in PROGRESS.md is left visible with the correction attached,
because the reasoning that put U25 before U22 is part of the record even though
one of its premises was wrong.

## I-048 — Comfort-taking cannot reproduce DBERNG01's flatness, and what that points at

**Severity:** Medium · **Raised:** U22, 9 Oct 2026 · **Status:** OPEN as a
finding; the mechanism is built and not to be pushed further

DBERNG01 says measured gas varies only **4 to 7%** across BER bands within a
dwelling type. U22 builds comfort-taking to explain that. It does not get there.

| arm | BER spread, gas at meter | ratio to published | mean indoor temp |
| --- | --- | --- | --- |
| comfort-taking off | 107.8% | 1.632 | 17.82 °C |
| declared strength | **75.2%** | 1.446 | 17.37 °C |
| ×2 | 50.9% | 1.294 | 16.99 °C |
| ×3 | **45.1%** | 1.227 | 16.83 °C |
| published (DBERNG01) | **4 to 7%** | 1.0 | — |

Three terms — setpoint, heating hours, and closing the sleeping zone — pushed to
three times their declared amplitude take the spread from 108% to 45% **and then
stop**. The binding constraint is not the one expected: mean indoor temperature
only falls to 16.8 °C, comfortably inside PL-TEMP-01's band, and it is the
mechanism's own clip bounds that saturate.

**Why it cannot reach it.** The residual spread *is* the modelled fabric range:
0.63 to 6.49 W/K/m², a factor of ten. A house-wide temperature reduction scales
each dwelling's losses rather than removing any, so it cannot flatten
consumption across a tenfold fabric spread. Closing the sleeping zone does
remove losses — that term was added mid-measurement after the sweep showed the
first two saturating, and the project's own description had it (*"heated warmer,
longer and in more rooms"*) — but that zone is a quarter of emitter capacity and
the two zones are coupled through `r_zz`, so an unheated bedroom still draws
heat from the living space. It bought 3 points.

**The signature is now visible on both sides, which is the strongest evidence
for the diagnosis.** Correcting the boiler error (I-047) raised efficiency from
0.754 to 0.820, which cut fuel for the same delivered heat — and that moved the
two populations in *opposite* directions:

| | E1 estate (84% A/B) | mixed-age slice (86.7% pre-1980) |
| --- | --- | --- |
| before the boiler fix | 0.832 | 2.11 |
| **after** | **0.785** | **1.446** |

So the model **under**-consumes against published gas on modern stock and
**over**-consumes on old stock, by a factor of 1.84 between the two
populations. Its response to fabric is roughly 1.8× steeper than the meters
say. That is the same finding as DBERNG01's flatness, measured a second and
independent way — and it is why the boiler error was worth the trouble of
finding: it had been masking the modern-stock shortfall while inflating the
old-stock excess, so the two errors partially hid each other and neither
population looked badly wrong on its own.

**What it points at: retrofit.** The model derives fabric from construction era
and BER band. Ireland's old stock has been substantially insulated under public
retrofit programmes, and a BER band label often reflects the dwelling as built
or as last assessed rather than as it now is. That would make the *real*
heat-loss spread considerably narrower than the modelled one — which is exactly
the discrepancy, and it would explain both the residual spread and the 1.45×
overshoot on old stock.

This is **not** the same as tuning the physics to absorb a behavioural effect,
which U22 forbids and D-022 explains. It is a question about whether the fabric
model is right for retrofitted dwellings, which is a separate and legitimate
one, and it belongs to the week 3 fabric work alongside CD488 and F2063.

### Scheduled for week 3 (10 Oct 2026)

**Confirmed on both axes before scheduling.** The calibration axis (DBERNG01,
BER bands) saturates at a 45% spread against a published 4–7%. The held-out
axis (DBERNG02, construction period, U31) closes only 15.3% of its gap and
leaves a residual of 0.45 at p = 7.4e-05. Two independent axes agreeing is what
makes this worth a week-3 slot rather than a note.

**The hypothesis, stated so it can fail.** The model derives fabric from
construction era and BER band. If Ireland's old stock has been substantially
insulated under public retrofit programmes while its band labels predate that,
then the *modelled* specific-loss spread (0.63 to 6.49 W/K/m², a factor of ten)
is wider than the real one, and consumption in the model responds to fabric
more steeply than the meters do. Measured: about **1.8× more steeply**, in both
directions.

**What would test it, in order of strength:**

| Test | What it would show |
| --- | --- |
| EBA02/EBQ02 BER assessment dates against build year | whether band labels are stale, and by how much, for the old stock specifically |
| A published retrofit count (SEAI grant schemes) against the pre-1980 stock | what fraction of old dwellings have had wall or attic insulation added |
| **CD488** (dwelling type × heating fuel × period, Census 2011) | whether the fuel/era joint the model assumes matches the census one — already declared, SOURCE_FOUND under sweep flag A-12 |
| **F2063** (rooms × bedrooms × year built × type, Census 2022) | already used for PL-ROOMS-01; its year-built axis can check whether modelled geometry by era is right, which is a term in specific loss |

**The constraint that stays in force.** No fabric parameter is tuned to close
the gas gap. If the retrofit evidence shows the old-stock fabric is too leaky,
the fix is to model retrofit — a change to how fabric is *derived*, with its own
validation — and not to move a U-value until the ratio looks better. That
distinction is D-022's and U22 restates it; the difference between the two is
whether the model ends up right for other purposes.

**Not acted on now**, per the instruction accompanying this schedule.

**What was deliberately not done.** The strength was not fitted to DBERNG01.
DBERNG01 is the declared calibration axis, so fitting would have been permitted
— but the mechanism cannot reach the target at any strength, and choosing a
number to approach a target it cannot meet would buy nothing but the appearance
of calibration. The declared amplitudes stand, and the sweep is published beside
them so the reader can see what each strength costs.

## I-049 — Neither slice spans U22's held-out validation axis

**Severity:** Medium · **Raised:** U22, 9 Oct 2026 · **Status:** OPEN; blocks
the held-out half of U22

U22's condition is that *"the space-heat ratio gradient (0.43 for 1967–99, 0.19
for post-2005 at E1) must shrink"*. That gradient needs a population containing
both 1967–99 and post-2005 dwellings. Neither slice has one:

| | E1 estate | U23/U29 mixed-age slice |
| --- | --- | --- |
| 1967–99 cell | **4 dwellings** | 13 |
| post-2005 cell | 4 | **0** — max build year 1995 |
| BER spread | 84% A/B | all seven letters |

The mixed-age slice's construction bands are pre-1919, 1946–60 and 1971–80 —
all old. A gradient across three old bands is reported in the artefact for
completeness and **does not test U22's claim**; the E1 estate has the modern end
but four dwellings against four, which is noise.

So the calibration half of U22 is done and the held-out half is not, and the
reason is the slice, not the mechanism. What a valid slice needs: at least ~10
dwellings in each of 1967–99 and post-2005, on gas, from the same town. Cobh has
both — the town's mean build year is 1974 — so this is a selection problem and
not a data problem. The U23 selector already searches seed areas against a
declared objective; adding a construction-period coverage constraint is the same
kind of change as U29's people-band one.

### I-038, fourth check (10 Oct 2026, after a fourth report that r4 is saved)

Searched again, more widely than before, and r4 is still not on this machine.

| Where | Result |
| --- | --- |
| `docs/` | only `Baile_Nua_Technical_Design_Review_r3.md` (122,436 bytes, 8 Oct 19:59) |
| `find` across `~` for `*r4*`, `*Baile*`, `*Technical_Design*` | nothing new |
| `Downloads/Baile Nua Technical Design Review*.md` (4 files) | revisions 1–3, 8 Oct 19:26–19:50; **none** contains U22, "9.6" or "Appendix A" |
| `grep -rl "U31"` across Desktop, Downloads, Documents | two hits, both false: `HEBEU31`, a CSO table code, in my own ISSUES.md and PROGRESS.md |
| files modified since 8 Oct 20:00 | only files I wrote myself |

What r3 actually declares: **U01 to U21**, and its section 9 ends at **9.5**.
There is no 9.6 and no Appendix A in it.

So the instruction to make r4 the single reference and retire Part C into it
still cannot be carried out, and retiring Part C would now destroy more than it
did at the second and third checks: Part C is the only record of **U22 to U31**,
D-028 to D-050, and the rulings behind the U28 storage fallback, the U30 sweep,
U25's DEAP anchoring and U22's comfort-taking. I have left it in place and added
nothing to r3, which stays frozen as the 8 October document it is.

The practical consequence is worth stating rather than just noting the absence:
**`DECISIONS.md` Part C and the U30 `[A]` register are now carrying design
content that a frozen design document would normally hold.** Thirty-seven
assumption flags with their search records, the V-level claims for three new
subsystems, and the calibration/validation split for nine sources all live in
working documents that have no revision discipline. That is survivable for
week 2 and is a real risk for E2, because the gate report cites them.

If r4 exists somewhere other than this machine, the thing that would unblock
this is its text, not its name — paste or place the file and the retirement
takes minutes.

## I-035 and I-038 — CLOSED: r4 is present and is now the single reference

**Closed 10 October 2026.**

`Baile_Nua_Technical_Design_Review_r4.md` was at the **project root**, not in
`docs/` — 139,468 bytes, 1,185 lines, modified **10 Oct 01:13**. Moved to
`docs/Baile_Nua_Technical_Design_Review_r4.md` and verified before adopting:

| Required | Present |
| --- | --- |
| section 9.6 | yes, "Progress against gates", line 955 |
| U22 to U31 | yes, **U01 to U31** in the section 11 decision table |
| Appendix A | yes, "HRSD\_Occupants Log", line 1171 |

**On the four earlier checks.** They were correct when they ran. r4's mtime is
10 Oct 01:13 and the fourth check ran on 9 October, so the file did not yet
exist; a `grep -rl "U31"` across Desktop, Downloads and Documents at that time
returned only my own documents. The one thing I would do differently is search
the **project root** explicitly rather than relying on name patterns under `~`:
all four checks looked for `*r4*`, `*Baile*` and `*Technical_Design*`, which
would have matched, but `head -8` truncated the Desktop results and the root of
the project is the one directory a design document is most likely to land in.
Listing the root unconditionally is cheaper than a pattern search and would
have found it the moment it appeared.

**What this closes.** Part C is retired into r4 with a pointer (see
`DECISIONS.md`), D-001 is amended to make r4 binding, and the risk recorded at
the fourth check — that Part C and the U30 `[A]` register were carrying design
content without revision discipline — is resolved for the U-decisions. One
ruling did **not** have a counterpart in r4 and so was not retired: the
seed-variance ruling (I-037), which stays in `DECISIONS.md` flagged as absent
from the design document.

r3 is kept unmodified. r4's architecture is frozen at revision 3 and unchanged,
so adopting it changes no architecture.

## I-049 — CLOSED by U31: the held-out slice exists and U22 passes on it

**Closed 10 October 2026.**

`engine/slice_u31.py` builds the slice I-049 said was missing, by stratified
selection across both ends of the construction axis:

| | old (1967–99) | new (post-2005) |
| --- | --- | --- |
| gas dwellings | **30** | **30** |
| build years | 1974–1998 | 2005–2021 |
| mean floor area | 130.0 m² | 126.4 m² |
| specific heat loss | 2.28 W/K/m² | 1.26 W/K/m² |

Balanced on floor area (Welch t = 0.315, p = 0.754) and sharply contrasted on
fabric (t = 6.80, p = 3.5e-08, a 1.82× ratio). The size balance is the part
that matters: DBERNG01's finding is that measured consumption tracks dwelling
**size**, so a size-confounded slice could not separate fabric from size.

**U22's held-out condition is met.** On DBERNG02, which the amplitudes never
saw:

| | old | new |
| --- | --- | --- |
| ratio, comfort-taking off | 1.234 | 0.700 |
| ratio, on | **1.189** | **0.737** |
| paired change per dwelling | **−0.045** (95% CI −0.084 to −0.006, p = 0.030) | **+0.037** (95% CI +0.029 to +0.045, p = 9.3e-10) |

**Gradient 1.763 → 1.614.** Both groups move in the predicted directions
simultaneously — the old stock's overshoot falls and the new stock's shortfall
rises — which a mechanism that merely scaled consumption could not do. Rebound
is visible in temperature too: modern dwellings run at 20.71 °C against the old
stock's 18.82 °C, both inside PL-TEMP-01's band.

Taken with U25, U22's stated condition is satisfied twice over: the gradient was
2.26 at E1 on space heat alone, 1.76 once hot water, cooking and combustion
losses were in, and 1.61 with comfort-taking.

**The honest limit, unchanged.** Only **15.3%** of the gap closed and the
residual gap of 0.45 is still strongly significant (t = 4.39, p = 7.4e-05).
Comfort-taking is a real term and not the whole explanation — the same
conclusion the DBERNG01 calibration axis reached, now confirmed on held-out
data. Two independent axes agreeing is a stronger statement than either alone,
and it is the firmest support yet for I-048.

An asymmetry worth recording, because it is the mechanism's structure rather
than noise: the new-group effect is estimated far more precisely (p = 9e-10)
than the old-group one (p = 0.03). Rebound is nearly uniform across modern
dwellings because they are all cheap to heat; prebound varies with
affordability, so it is spread across households of different means and its
mean is noisier.

**Nothing was fitted on this slice**, which is the point of it:
`EVALUATION_ONLY` is asserted by the test suite, and the U23 DER-guarantee
intervention is deliberately skipped — an intervention on an evaluation sample
would defeat the purpose.

## I-044 — CLOSED: the overnight taper, and a computation that was being thrown away

**Closed 10 October 2026.** PL-PEAK-01 passes; the plausibility suite is 12
checks, **10 pass, 0 fail**.

| | before | after | LP1 |
| --- | --- | --- | --- |
| overnight taper (00:00 ÷ 04:00) | 0.950 | **1.414** | 1.721 |
| 00:00, × daily mean | 0.435 | **0.640** | 0.77 |
| 02:00 | 0.459 | **0.487** | 0.53 |
| 04:00 | 0.458 | **0.453** | 0.45 |
| mean-day trough hour | 0 | **5** | 4 |

**The diagnosis was sharper than the symptom.** I-044 described a missing
taper and guessed at "late-evening activity decay and the appliance standby
floor". Measuring the awake share by hour gave the real answer in one line:
**0.33 at 23:00 and exactly 0.00 at 00:00**. Nobody in the town was awake after
midnight, on any night, so the aggregate load fell to its standby floor at
midnight precisely.

**And the cause was a discarded computation, not a missing mechanism.**
`_sleep_window` already drew bedtimes as late as 02:30, and the code already
carried a comment saying *"a bedtime past midnight means this day ends
AWAKE"*. But `place(0, wake, "sleep")` then claimed minutes 0 to wake
**unconditionally**, so a person drawn to go to bed at 01:30 was overwritten as
asleep from midnight. The late bedtime was computed every night for every
person and thrown away.

**The fix.** The small hours belong to *yesterday's* bedtime. That is
recoverable deterministically because the RNG is counter-based and keyed by
(person, sim\_day): asking for `sim_day - 1` returns exactly the number
yesterday's own generation used, so no state is carried across days and the
reproducibility contract is untouched. The runner also passes **yesterday's day
type**, because a Friday night runs later than a Sunday one and using today's
flag would be wrong on Mondays and Saturdays.

Awake share at midnight is now 0.084, and the overnight profile falls
monotonically from 00:00 through 04:00 — which a test asserts, because a ratio
alone could be produced by a bump at 04:00 rather than by a decline.

**Still short of LP1 at midnight** (0.64 against 0.77), and that is recorded
rather than closed over: the bedtime *distribution* peaks around 22:45, which
is early. If the midnight level needs to rise further the next step is the
distribution, not more mechanism, and `eurostat.hetus.tus_00startime` is
already declared for it. The taper term passes at 1.41 against a floor of 1.25,
so this is a known approximation and not an open failure.

**The known-failure register removed the entry, not me.** When PL-PEAK-01
started passing, `test_the_e1_package_fails_only_what_is_known_to_fail` failed
with *"['PL-PEAK-01'] is listed as a known failure but now passes. Good news:
close its issue."* That is D-040's second rule working: an entry cannot outlive
the defect it describes. The register is now empty.


## I-050 — The overnight taper is a two-point ratio and can be moved by either point

**Severity:** Medium · **Raised:** week 2 step 4 ablation, 10 Oct 2026 ·
**Status:** OPEN, with the better metric identified

PL-PEAK-01's taper term is `mean(00:00) / mean(04:00)` against ESB Networks
LP1's 1.721. The `no_chronotype` ablation arm **improved** it — 1.199 to 1.285,
closer to LP1 — while making the model less realistic, which is the opposite of
what the metric is for.

The hourly shape shows exactly how:

| | 22:00 | 23:00 | 00:00 | 01:00 | 04:00 |
| --- | --- | --- | --- | --- | --- |
| full model | 1.33 | 0.97 | 0.56 | 0.49 | **0.46** |
| no chronotype | **1.45** | 0.88 | 0.56 | 0.47 | **0.44** |
| LP1 | 1.28 | 1.03 | 0.77 | 0.61 | 0.45 |

Midnight did not move at all — 0.56 both ways. Removing chronotype synchronised
the town, which **raised** the 22:00 peak and **lowered** the 04:00 trough, and
the ratio improved through its denominator. A two-point ratio can be moved by
either point, and the trough is the more fragile of the two because it is a
small number.

**The arm still fails on the metric it was predicted to fail** (load factor
0.2473 → 0.2283), so the ablation's verdict is unaffected and the acceptance
criterion is still met. What is affected is confidence in the taper as a fit
measure used on its own.

**The better metric, for whoever revises PL-PEAK-01.** The whole overnight
*shape* rather than two points of it: the model is already tested for a
monotonic decline from 00:00 through 04:00
(`test_the_overnight_taper_is_fixed_and_that_was_i_044`), and a sum of absolute
differences against LP1's 00:00–06:00 hours would be moved only by the shape
actually changing. Not changed now: PL-PEAK-01 passes on the delivered package
and is cited by the gate report, so revising a gate-cited check because an
ablation gamed it is a decision to take deliberately rather than mid-step.

## I-051 — The overnight profile is too low from 00:00 to 02:00 in both slices

**Severity:** Low · **Raised:** week 2 step 4, 10 Oct 2026 · **Status:** OPEN,
and it is I-044's residual stated precisely

I-044 recorded that the model was still short of LP1 at midnight (0.64 against
0.77) and pointed at the bedtime distribution. Step 4's shapes locate the
deficit exactly:

| | 00:00 | 01:00 | 02:00 | 04:00 |
| --- | --- | --- | --- | --- |
| model (mixed-age slice) | 0.56 | 0.49 | 0.45 | **0.46** |
| LP1 | 0.77 | 0.61 | 0.53 | **0.45** |

**The model matches LP1 at 04:00 almost exactly and is low from midnight to
02:00.** So the floor is right and the *transition into* it is too fast: people
are getting to bed earlier than the meters imply, rather than the baseload being
wrong.

**And the taper is slice-dependent for a demographic reason, which is the model
working.** The E1 estate measures 1.414 and the mixed-age slice 1.199:

| | mean age | share 65+ | mean chronotype |
| --- | --- | --- | --- |
| E1 estate | 27.9 | 0.007 | **+0.83** (late) |
| mixed-age slice | 44.5 | **0.214** | −0.05 |

A young estate has more people awake at midnight than an older one, so its
overnight profile is flatter. That is the right behaviour and it has a
consequence worth stating: **PL-PEAK-01's taper floor of 1.25 was set against a
slice that is not representative of Cobh.** The mixed-age slice, which is much
closer to the town (mean build year 1974), measures below the floor. The floor
is not wrong — LP1 is an all-Ireland urban domestic profile and the town should
approach it — but it is currently only satisfied by the youngest slice in the
project.

The fix for both is the same and belongs with `eurostat.hetus.tus_00startime`:
the bedtime distribution peaks near 22:45 and should peak later, with a longer
right tail. Deferred rather than guessed at, because moving a bedtime
distribution to fix an energy profile without a time-use source behind it is
the kind of tuning D-022 and U22 forbid in the fabric and which deserves the
same caution here.

## I-050 — extended: distance-to-reference is the wrong scoring for a structurally one-sided metric

**Updated 10 Oct 2026, after U32.**

Two further results on the same theme, one good and one a mistake of mine.

**U32 part 2 fixed the original artefact at its source.** Before the bedtime
distribution was widened, the `no_chronotype` arm *improved* the two-point
taper (1.199 → 1.285). After, it correctly degrades it (1.0634 → 0.9494). So the
perverse result was partly a symptom of a distribution too narrow to respond
properly, not only of the metric. Both halves of U32 were needed.

**And the same trap caught me again, in the other direction.** I predicted that
ungating heating from occupancy would *degrade* the load factor, reasoning that
heating an empty house flattens the profile. The physics was right and the
scoring was wrong: a 60-home estate has a load factor of 0.24 against LP1's
0.413, because LP1 aggregates about two million meters. Anything that flattens
a small aggregate therefore moves it **towards** the national figure and scores
as "better" — 0.2415 → 0.254.

| | model | LP1 | effect of flattening |
| --- | --- | --- | --- |
| load factor, 60 homes | 0.24 | 0.413 | always scores *better* |

The arm's verdict is unaffected because it still degrades the gas ratio
(1.4417 → 1.4933) and the peak hour (0 → 1). What is wrong is my expectation,
and the general lesson is sharper than I-050's original form:

**A metric on which the model sits systematically to one side of the reference
for a structural reason cannot be scored by distance.** For the load factor of
a small aggregate, the meaningful test is the one PL-PEAK-01 already uses — the
upper bound, "do not be smoother than the national class" — and not the
distance. `FIT_METRICS` should carry a direction for such metrics rather than
treating every one as two-sided. Recorded rather than changed, because
rewriting the ablation's scoring after seeing its results needs to be a
deliberate decision and not a reflex.

## I-051 — CLOSED on the sleep timing; the residual is in a different layer

**Closed 10 Oct 2026 for what it described.** U32 part 2 fixed the bedtime and
wake-time distributions from a time-use source, and the validation against that
source is good:

| | awake-share MAD vs HETUS |
| --- | --- |
| mixed-age slice | **0.0283** |
| E1 estate | 0.0621 |

The small hours are near-exact on the mixed-age slice (02:00 −0.000, 03:00
−0.005, 04:00 −0.001). The E1 estate's larger MAD is a **young estate measured
against an all-population curve** — +0.83 mean chronotype, too awake in the
evening and too asleep in the morning — which is the model representing a real
demographic rather than a defect.

**I-051's premise was wrong and the source corrected it.** I-051 said bedtimes
were too early. HETUS says the median was fine and the distribution was far
**too narrow**: a 10-to-90 range of 106 minutes against the source's 187, with
effectively no right tail. A distribution that tight cannot produce anyone
awake at 01:00 however its centre is placed.

### The 06:00 deficit halved and did not close, and here is why

| | LP1 | before | after |
| --- | --- | --- | --- |
| E1 estate, 06:00 | 0.58 | 0.37 (−0.21) | **0.47 (−0.11)** |
| overnight shape MAD, E1 | — | 0.1621 | 0.1589 |
| overnight shape MAD, mixed-age | — | 0.0832 | 0.0765 |

Dividing each hour's load by HETUS's awake share isolates what one awake person
draws, and that localises the residual precisely:

| hour | model | LP1 | reading |
| --- | --- | --- | --- |
| 22:00 | 3.01 | 2.31 | model draws **too much** per awake person |
| 23:00 | 6.39 | 4.01 | too much |
| 02:00 | 32.40 | 33.39 | **matches within 3%** |
| 04:00 | 49.72 | 44.90 | matches |
| 06:00 | 3.45 | 4.28 | too **little** |

So three things are now separated that were previously confounded:

1. **The awake count is calibrated** — to the source, MAD 0.0283.
2. **The standby floor is right** — the deep small hours agree with the meters
   within 3%.
3. **The residual is the activity-to-load mix at the evening and morning
   boundaries.** The model's late evening is too appliance-heavy and its early
   morning too light.

That last is a device and activity-layer question, not a sleep-timing one, and
**no energy parameter was touched** to move it, per the instruction. It is the
specific thing to look at next in the device layer: the morning should carry
showers, kettles and breakfast cooking at higher power for shorter periods than
the model currently gives it, and the late evening should wind down further.

### One thing got worse, and it is two effects compounding

The E1 estate's 23:00 went to **+0.517** against LP1, its worst hour. A young
estate with +0.83 mean chronotype genuinely is awake at 23:00 *and* each awake
person draws about 1.6× what the meters imply at that hour. The first is the
model working; the second is finding 3 above. Both slices remain inside the
shape band (0.1467 delivered, 0.0765 mixed-age, against 0.1901).

**And the metric change earned itself.** The delivered package's secondary
taper reads 1.2013, which would have **failed** the old 1.25 floor, while the
shape check passes at 0.1467. U32 part 1 was necessary and not cosmetic.


## I-052 — The activity-to-load mix is wrong at the day's boundaries

**Severity:** Medium · **Raised:** U32, 10 Oct 2026 · **Status:** OPEN,
scheduled for the week 3 device work · **Do not fix in week 2**

U32 calibrated the sleep timing and the overnight load shape still misses LP1 at
the two ends of the night. Dividing each hour's load by HETUS's awake share
isolates what **one awake person draws**, which separates three things that were
confounded in a single symptom:

| hour | model | LP1 | reading |
| --- | --- | --- | --- |
| 22:00 | 3.01 | 2.31 | draws **1.30×** too much |
| 23:00 | **6.39** | **4.01** | draws **1.59×** too much |
| 00:00 | 6.00 | 7.77 | |
| 01:00 | 15.39 | 16.68 | |
| 02:00 | 32.40 | 33.39 | **matches within 3%** |
| 04:00 | 49.72 | 44.90 | matches |
| 06:00 | **3.45** | **4.28** | draws **0.81×**, too little |

So:

1. **The awake count is calibrated** — mean absolute deviation 0.0283 against
   the source on the mixed-age slice, small hours near-exact (U32, A-38).
2. **The standby floor is right** — the deep small hours, when almost everyone
   is asleep and the load is nearly all baseload, agree with the meters within
   3%. That is a strong result and it rules out the explanation I first reached
   for in I-044.
3. **The residual is what awake people are doing** at the evening and morning
   boundaries, which is the device and activity layer, not sleep timing and not
   baseload.

**What that means concretely for the device work.** The morning is too light and
the late evening too heavy per awake person. A real Irish morning is short and
high-powered — showers, kettles, toasters, breakfast cooking, all inside an
hour — where the model spreads a gentler load. A real late evening winds down to
television, lighting and standby, where the model is still running appliances.
The likely candidates, in order of how much load they carry:

| candidate | why |
| --- | --- |
| morning appliance trigger rates | `TRIGGER_RULES` fire on activity episodes; the morning routine may be under-triggering kettles and showers |
| electric shower share and timing | a 9 kW shower inside a ten-minute window is most of a morning peak, and `electric_shower` ownership is 0.58 |
| late-evening appliance tails | dishwashers and washing machines started late and running into the night |
| cooking duration versus power | the model may spread cooking over a longer, lower-power episode than a real hob |

**Why not now.** Three reasons, and the first two are the brief's. U32's
instruction was explicit that energy parameters must not be tuned to close this,
and the appliance trigger rates and ownership priors are the subject of their
own sourced checks (PL-APPL-01, PL-APPL-02, PL-APPLSIZE-01, sweep flags A-04 to
A-07), so moving them has consequences beyond the overnight shape. Third, the
quantity to aim at is now precise — load per awake person by hour against LP1 —
and that is a better starting point than the aggregate deviation I began U32
with.

**It is not currently failing a check.** PL-PEAK-01 passes at a shape deviation
of 0.1467 against a band of 0.1901, so this is a known residual rather than an
open failure. It is recorded here so the week 3 device work starts from the
measurement rather than rediscovering it.

---

## I-053 — Two vital-statistics sources were declared under the wrong matrix and never consumed

**Severity:** High (data provenance) · **Raised:** week 2 step 5, 10 Oct 2026 ·
**Status:** FIXED in the same step

`sources_registry.py` declared:

| key | URL | what the file actually contained |
| --- | --- | --- |
| `cso.vitalstats.births_by_age_of_mother` | VSA09 | **deaths** and crude death rates |
| `cso.vitalstats.deaths_by_age_sex` | VSA17 | **births** and average age of mother |

The two matrices were crossed, and on top of that *neither carries an age
dimension at all* — both are State-level annual series, so "by age of mother"
and "by age and sex" were wrong twice over. VSA09's real title is "Deaths and
Death Rates per 1,000 population".

**Why it went unnoticed.** Nothing had ever read them. Sweep flag A-25 names
"week 2 step 5, WP5 ten-year life course" as its owning step, so these were
fetched in advance and the first code to open them was this step's. The
registry's `used_for` text described the intended use, which was right; only
the URL and title were wrong, and no test compares a declared title against the
fetched file's own label.

**What replaced them**

| hazard | matrix | why |
| --- | --- | --- |
| fertility | VSA104 | age-specific rates by NUTS 3 region — South-West |
| parity | VSA36 | births by age of mother **and previous liveborn children** |
| mortality | VSA08 ÷ PEA01 | deaths by age band and sex over population on the **same band code** (C02076V02508), so the bands are not mapped by hand |

CEPHA05, the Decennial Life Table, was fetched and **rejected**: it is the only
life table PxStat publishes and its last year is 1990, which cannot age a 2022
population.

**The lesson that generalises.** A declared source that nothing consumes is
unverified. The registry records intent; only reading the file tests it. A
cheap guard would compare each JSON-stat source's own `label` against the
declared `title` at fetch time, and that is worth adding — it would have caught
this the day the source was declared rather than a week later.

---

## I-054 — Fabric-retrofit D20 labels describe a change the week-2 series does not contain

**Severity:** Medium · **Raised:** week 2 step 5, 10 Oct 2026 · **Status:**
OPEN, closes with the week 3 fabric work (I-048)

WP5's ten-year life course produces `retrofit_fabric` and `extension` events
with D03 passport rows and D20 change labels, because the task asks for a
passport event for *every* retrofit, extension and asset change. Their labels
appeal to the free-running temperature decay, which is a T2 claim and a correct
one.

But I-048 defers the fabric work to week 3 and the standing instruction is **no
fabric tuning now**, so `apply_year_to_slice` does **not** touch the RC
parameters for those two measures. The four asset measures that the engine
already models — heat pump, PV, battery, smart controls — *are* applied.

So in a week-2 package a detector scored against a `retrofit_fabric` label
would be scored against a change the series does not contain: every detector
scores a false negative, through no fault of its own. In the 2022–2031 run this
affects 8 fabric retrofits and 10 extensions.

This is recorded rather than papered over, and it is visible in the run: the
slice diagnostics carry `wp5_measures_applied` and
`wp5_measures_deferred_to_week3_fabric`, and
`test_the_deferred_fabric_work_is_declared_not_silent` asserts the deferral, so
applying the physics in week 3 has to come back and flip it.

**Final counts over the completed decade**, from
`v1/evidence/wp5_tenyear.json`: **8 fabric retrofits and 13 extensions** —
21 of the 47 D03 passport events, so **45% of the building changes the ten-year
run records are not in the series**. The figure quoted when this issue was
raised (8 and 10) came from a mid-run smoke test at year nine, before the last
two years' extensions.

**Not fixed by dropping the labels.** The passport events and labels are the
ground truth of what happened to the building; suppressing them would make the
ten-year history wrong in order to make a week-2 package self-consistent.

---

## I-055 — the overnight drift is real, is NOT the DER assets, and the assets are masking it

**Severity:** High · **Raised:** week 2 step 5 (the ten-year run), 10 Oct 2026 ·
**Status:** OPEN · **Hypothesis tested and refuted**

The overnight-shape metric drifts upwards across the decade, towards the band
it is checked against. All ten years:

| year | 2022 | 2023 | 2024 | 2025 | 2026 | 2027 | 2028 | 2029 | 2030 | 2031 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MAD | 0.1559 | 0.1560 | 0.1458 | 0.1434 | 0.1676 | 0.1729 | 0.1614 | 0.1797 | **0.1818** | 0.1720 |
| measures | 0 | 5 | 10 | 15 | 20 | 22 | 22 | 24 | 25 | 26 |
| people | 133 | 131 | 125 | 129 | 121 | 125 | 129 | 136 | 141 | 140 |

Band **0.1901**; every year passes, the maximum at **95.6%** of it. The trend is
not monotonic and the year-to-year noise (sd 0.0134) is comparable to the
decade's rise, so it has to be fitted rather than eyeballed. Over all ten
years, MAD against year: slope **+0.00336/yr, r = +0.760, p = 0.011**.

### The ablation, and what it refuted

The first version of this issue proposed that the drift was the accumulating
DER and retrofit assets — by 2030 the slice holds 6 heat pumps, 6 PV, 3
batteries and 10 smart controllers in 60 homes — while LP1 is a **2022**
profile of a population with almost none of them. The correlation supported it:
MAD against measures-in-place came out **r = +0.705, p = 0.023**, while MAD
against population was not significant (p = 0.163).

The deciding experiment was 2030 run twice at identical population, weather,
calendar and seed, once with the measures applied and once with every measure
suppressed:

| arm | overnight MAD | band | outcome | artefact |
| --- | --- | --- | --- | --- |
| with DER | **0.1818** | 0.1901 | PASS | `wp5/der_ablation_with_der.json` |
| **without DER** | **0.1903** | 0.1901 | **FAIL** | `wp5/der_no_der/evidence/plausibility.json` |

**The assets' causal effect on the metric is −0.0085: they IMPROVE the
overnight shape.** Every one of the nine overnight hours is *less* deviant with
the assets than without, which is what a heat pump running overnight and a
battery discharging into the small hours should do.

So the hypothesis is refuted, and refuted by a result that the pre-registered
prediction did not allow for. That prediction was: *"if the drift disappears it
is the assets; if it persists it belongs to I-052"* — a dichotomy that omitted
the outcome actually observed, which is that removing the assets makes the
metric **worse**. The prediction was incomplete, not merely wrong, and it is
left here as written rather than tidied up.

**The +0.023 correlation was confounded by time.** Measures accumulate
monotonically, so they are collinear with year, and the causal effect has the
*opposite sign* to the correlation. This dataset now contains its own worked
example of that trap, which is worth more than the original hypothesis was.

### The serious consequence

**PL-PEAK-01 passes in 2030 only because the assets are offsetting the drift.**
Without them the 2030 package fails the check outright — the U27 write hook
refused to deliver it, which is that hook working as designed. The assets are
masking a drift large enough to breach the band on its own, so the check's
continued passing is not evidence that the underlying shape is sound.

### What is still open

Correlation cannot settle the cause, and the reason is now demonstrable rather
than assumed. Every quantity that is monotone in year correlates significantly
with the MAD, and with n = 10 they are mutually collinear:

| MAD against | slope | r | p |
| --- | --- | --- | --- |
| year | +0.00336 | +0.760 | **0.011** |
| measures in place | +0.00104 | +0.705 | **0.023** ← *causal effect is the opposite sign* |
| persons with a chronic health state | +0.00206 | +0.673 | **0.033** |
| persons aged 65+ | −0.00392 | −0.730 | **0.017** |
| mean age | +0.00768 | +0.465 | 0.175 |
| population | +0.00097 | +0.478 | 0.163 |

Note that mean age does **not** rise monotonically (43.39 in 2022, 44.41 in
2031): move-ins arrive aged 20–70 and births at 0, so the life course does not
simply age the slice. The remaining candidates are therefore the **health-state
composition** (0 to 14 persons over the decade, monotone by construction since
onset is irreversible here) and the **activity-to-load mix**, which is I-052 —
and I-052 names the *same two hours*, 23:00 and 06:00.

**Next, in week 3 and in this order.** I-052 is being fixed as week 3 step 2
anyway. Re-measure this drift *after* that fix: if it shrinks, the drift was
the activity-to-load mix all along and this issue closes with I-052. Only if it
survives is a health-state ablation worth running, by the same method that
settled the assets.

**Do not widen the band.** It is derived (D-055) and the model now has a known
drift towards it that the assets are hiding.

### Related

I-057 is what makes any of this interpretable: all ten years use the identical
real 2022 weather, so the spread cannot be a weather artefact. I-052 is the
leading remaining candidate. D-055 derived the band.

---

## I-056 — `SynthBuilding`'s DER flags are undeclared attributes, so `dataclasses.replace` drops them

**Severity:** Medium (latent) · **Raised:** week 2 step 5, 10 Oct 2026 ·
**Status:** OPEN — worked around locally, root cause not fixed

`has_battery` and `has_ev` are assigned to a `SynthBuilding` *after
construction*, in `e1_run.build_slice`, and are **not declared fields** of the
dataclass. Every reader in the codebase uses `getattr(b, "has_battery", False)`,
which is what makes the arrangement work.

What it does not survive is `dataclasses.replace`, which copies declared
fields only and silently drops anything else. `apply_year_to_slice` hit this
twice over while trying to stop mutating the original slice:

1. assigning a measure wrote through to `sl.buildings`, so the original
   slice's battery count went from 3 to 6 after applying year ten — against a
   docstring that said "mutates nothing";
2. copying the buildings with `dataclasses.replace` then dropped the
   undeclared attributes, so applying year *one* produced a slice with **no
   batteries at all** where the original had three.

Both are fixed locally with `copy.copy`, which preserves `__dict__`, and
`test_applying_a_year_does_not_mutate_the_original_slice_s_buildings` pins all
four invariants.

**No committed result is affected, and that is measured rather than argued.**
Each per-year run is a separate process that applies exactly one year, which
is the one usage pattern in which neither bug is visible: the old code mutated
the shared building objects and returned a slice referencing them, so the
engine saw the correct 6 batteries — the right answer by the wrong means. Two
years applied in one process would have leaked the later year's assets into
the earlier year's answer, silently.

Re-deriving 2030's slice with the fixed code and comparing against the
committed `wp5_2030.json`:

```
committed (pre-fix) : people 141, vacant 3, applied {heat_pump 6, pv 6,
                      smart_controls 10, battery 3}, deferred {extension 8,
                      retrofit_fabric 7}
recomputed (post-fix): identical
```

and the engine still sees 6 batteries in 2030 (3 at t0 plus 3 added by WP5).
So the nine committed years and anything run after the fix are directly
comparable, which matters because the I-055 ablation runs on the fixed code
while year 2031 was already in flight on the old.

**The root cause is still there.** Any future code that copies a
`SynthBuilding` with `dataclasses.replace` will lose the DER flags and get no
warning. The fix is to declare `has_battery` and `has_ev` as fields with
`False` defaults, which also lets the `getattr` guards go. It is not done here
because `SynthBuilding` is a core population type and the ten-year run was in
flight; changing a dataclass's field set mid-run risks the content hashes that
the reproducibility contract depends on. **Week 3, before the full town run**,
with the E1 package regenerated and its hashes re-verified.

---

## I-057 — the ten-year run uses 2022's weather ten times

**Severity:** High for a delivered dataset, **low for step 5's own purpose** ·
**Raised:** week 2 step 5, 10 Oct 2026 · **Status:** OPEN, needs a declared
policy before the week 3 full ten-year run

`e1_run.run_year` calls `build_realisation(2022, ...)` and
`build_calendar(2022, ...)` with the year **hard-coded**. E1 was a 2022 run, so
that was correct; the ten-year run reuses it, so **every year of 2022–2031 has
the identical real 2022 weather**.

**For step 5 this is the right control and should be stated as one.** Holding
the weather fixed means the only thing varying across the ten years is the
population and its assets, which is exactly what makes the per-year comparison
in I-055 interpretable: the overnight-shape trend cannot be a weather artefact
because there is no weather variation to cause it. Had the weather varied, the
0.1434–0.1818 spread could not have been attributed to anything.

**For a delivered dataset it is a defect, and a leakage-shaped one.** A model
trained on ten years of identical weather can memorise it and "forecast"
perfectly — the weather becomes a deterministic function of day-of-year. That
is not a hole in the GT/OBS separation, so no existing leakage test fires on
it, but it is the same class of problem: an artefact of construction that a
learner can exploit for performance it would not have on real data.

**What is available.** Measured from the already-declared source: the Met
Éireann Roches Point hourly archive spans **01-dec-1955 to 01-oct-2026**, 601,607
rows. So:

* **2023–2026 have real observed weather that is not being used.** Four of the
  ten years could be their own actual weather at no sourcing cost.
* **2027–2031 cannot.** They are in the future, so a decade running to 2031
  needs a declared policy — resample historical years, use a projection, or
  state that late years hold a fixed realisation — and whichever is chosen has
  to travel with the dataset, because a model's apparent skill depends on it.

**Not fixed here.** Changing the weather year is a one-line change and a
large consequence: it would invalidate the ten per-year packages just
produced, it changes what I-055's trend means, and it needs the 2027–2031
policy decided first rather than defaulted. The ten years delivered here are
therefore labelled as a **fixed-weather** decade, which is what they are.

**Related.** I-055 (the overnight drift, whose interpretation depends on this
being a control rather than an accident) and I-036 (storage for the full
ten-year run, which is where the policy has to be settled).

---

## I-058 — two plausibility checks score against calibration inputs, and the suite counts them as sourced

**Severity:** Medium · **Raised:** week 3 step 1, 10 Oct 2026, by recording the
BER Research Tool's exposure · **Status:** OPEN

Marking `seai.ber.research_tool` as tuning-exposed for fabric prompted the
obvious next question — which other checks score against a source the model was
calibrated on — and two do:

| check | source | exposure |
| --- | --- | --- |
| **PL-ELEC-01** | `cso.electricity.dbere101_by_dwelling_ber` | **tuning** |
| **PL-GAS-01** | `cso.gas.dberng01_by_dwelling_ber` | **tuning** |
| PL-DHW-01 | `seai.deap.manual_4_2_7` | design |
| PL-APPL-01/02, PL-APPLSIZE-01, PL-AREA-01, PL-MIX-01, PL-PEAK-01 | — | none |

Both exposures were already declared and both say why: DBEREL01 because "the
appliance trigger rates WERE adjusted against it", DBERNG01 because "the
floor-area and room-allocation fixes in I-031 were checked against it". Neither
was hidden. What was missing is the consequence: **a check scored against a
calibration input is a consistency check, not an independent validation.**

**What it does and does not undermine.**

* It does *not* make the checks worthless. PL-ELEC-01 and PL-GAS-01 were built
  to catch gross error — the I-027 fault was electricity far above its cell —
  and a model can still fail a target it was tuned towards. Both have wide
  bands for that reason ([0.40, 1.00] and [0.25, 1.00]).
* It does mean the suite's **"9 sourced checks pass"** overstates independence.
  Seven are against sources at exposure `none`; two are against calibration
  inputs; one more (PL-DHW-01) is against a `design`-exposed reference. The
  suite's own rule is that one number would mislead, and this is a second way
  it can.
* The genuinely independent energy axes exist and are held out: **DBEREL02**
  and **DBERNG02**, both dwelling type × period of construction, both at
  exposure `none`, and DBERNG02 is what U31's gradient is measured against.
  The E1 gate report's `heldout` block already uses them.

**From week 3 this matters more, not less.** The fabric is now derived from the
BER Research Tool, and the fabric is the largest input to gas. So PL-GAS-01 is
downstream of two calibration inputs rather than one, and the only fabric
validation that means anything is the held-out gas axis — which is why U31
stays evaluation-only and why `fabric_assessed.py` refuses to be used as a
fabric validation reference at all.

**What was changed now.** Each tuning-exposed source's `used_for` states what
its exposure rules out, so the register answers the question without a
cross-reference; `fetch()` detects declaration drift and rewrites the manifest,
because `SOURCES.md` is generated from manifests and was still publishing
`none` for the BER tool after it had been re-declared; and the suite artefact
now carries each check's source exposure.

**What is not changed.** The checks stay. Removing them would lose a real
guard against gross error, and the honest fix is to report what they are rather
than to delete them or to pretend they are independent.

---

## I-059 — the held-out slice's membership depends on the quantity under test

**Severity:** High (invalidated a pre-registered test) · **Raised:** week 3
step 1, 11 Oct 2026 · **Status:** FIXED, and the test re-run

D-073 pre-registered a **paired per-dwelling** comparison of the U31 gas
gradient before and after the fabric change. The paired test came back with
`p = nan`, and the reason is structural rather than arithmetic.

The U31 selector balances on floor area and **contrasts on specific heat
loss** — that contrast is the entire purpose of the slice (D-052). Sourcing
the fabric from SEAI's assessed distribution moved every dwelling's specific
heat loss, so the selector chose a different sample: **only 20 of 60 dwellings
were shared** with the pre-change selection.

So:

* the paired test was not merely failed but **impossible**: 40 dwellings
  appeared in exactly one arm;
* the headline before/after comparison, 1.6158 → 1.5528, is **between two
  different samples** and cannot be read as a change in the model.

**The pre-registration was at fault, not the selector.** D-052 says plainly
what the selector contrasts on. Pre-registering a paired test on a sample
whose membership depends on the quantity under test was an error that should
have been caught when the criterion was written.

### A second bug, which made the failure look like a pass

The direction was reported as `"down" if delta.mean() < 0 else "up"`. For a
`nan` mean, `nan < 0` is `False`, so it printed **"up"** — the predicted
direction — for the new-stock group, whose ratio had in fact moved the *other
way* (0.7307 → 0.7073). An unmeasurable result was displayed as the predicted
one.

A pre-registered criterion is worth nothing if the reporting can quietly
satisfy it. `_direction` now returns `"undetermined"` for a `nan`, and
`gradient_report` raises `U31MembershipError` rather than returning a paired
statistic over two different samples.

### Two more latent faults found while fixing it

* `share_of_gap_closed` divided by `gap_off` with no guard, so a degenerate
  baseline arm raised `ZeroDivisionError` instead of reporting an undefined
  share.
* The U31 driver and the gradient computation lived **only in a scratchpad
  directory** while `heldout_u31.json` was committed — a committed evidence
  artefact that could not be regenerated from the repository (D-077). Moved
  in, with the statistics verified against the baseline.

### The fix, and why freezing to the *pre-change* selection is the neutral choice

`select_heldout_slice` takes `frozen_household_ids`, and the re-run uses the
**pre-change** membership. That is the sample that existed before anything was
touched. Re-selecting after the change and comparing against the old selection
would be choosing the sample after seeing the model, which is exactly what a
held-out set exists to prevent.

### What this means for the result

The 2-of-4 failure reported from the unpaired run stands as reported, and is
superseded by the frozen-membership re-run rather than withdrawn. The
criterion itself is unchanged: the four conditions in D-073 are tested as
written.

---

## I-060 — U32's awake-share fit is a consistency check, not an independent validation

**Severity:** Medium · **Raised:** week 3 step 2, 11 Oct 2026 · **Status:**
declaration corrected; the check is kept and relabelled

Looking for a source to time appliance triggering from (I-052) turned up the
same circularity the BER Research Tool prompted:
`eurostat.hetus.tus_00startime` was declared at exposure **`none`** while U32
had **derived the sleep timing from it**.

`bedtime_offsets()` and `waketime_offsets()` — which *set* the model's sleep
timing — and `awake_share_reference()` — which *scores* the model — both read
the same `asleep_share_curve()` from that table. So the figures reported for
U32, awake-share MAD **0.0283** at the test seed and **0.0169** at the ten-year
seed, are the model checked against the curve its own parameters came from.

**What the check is still worth.** It asks whether the implementation
reproduces the distribution it was given, through chronotype quantiles, the
derived workday damping, the clip bounds and the day-boundary handling — any of
which can fail, and some of which did. That is how the fit went from 0.0621 to
0.0283. It is a genuine implementation test.

**What it cannot do** is evidence that Irish sleep timing resembles the
model's. The source is a **UK** donor in any case (`substitute_flag`: "HETUS
has no Irish data at all"), so even an independent comparison against it would
not be an Irish validation.

**The separation that matters for I-052.** Week 3 step 2 derives appliance
timing from the same table, which makes it tuning-exposed for activity timing
generally. The independent check on the resulting **load shape** is ESB
Networks LP1 through PL-PEAK-01, at exposure `none` — and LP1 must never be
tuned against, or that independence goes too. So:

| | source | exposure | role |
| --- | --- | --- | --- |
| activity timing | HETUS `tus_00startime` | **tuning** | where the timing comes from |
| overnight load shape | ESB Networks LP1 | `none` | the independent check |

That is why I-052 cannot be fixed by adjusting appliance timings until 23:00
and 06:00 match LP1. Doing so would close the gap and destroy the only
independent evidence the overnight shape has.

**Count so far.** Three sources were declared at an exposure that understated
what they had been used for: DBEREL01 and DBERNG01 (declared `tuning`, but
their consequence for PL-ELEC-01 and PL-GAS-01 unstated — I-058), the BER
Research Tool (declared `none` after the fabric was derived from it), and this
one. The pattern is that exposure gets set when a source is *fetched* and not
revisited when a later step *uses* it differently. `fetch()` now rewrites a
manifest on declaration drift, which fixes the publishing half; the remaining
half is that nothing prompts a review when a new consumer appears.

---

## I-061 — `exposure` is declared per source, but DEAP's uses are section-level

**Severity:** Low (recorded, not resolved) · **Raised:** week 3 step 2, 11 Oct
2026 · **Status:** OPEN — resolving it is a schema change

The new exposure-consistency guard flags `seai.deap.manual_4_2_7` as read by
both a model module and a scoring module, and it is right:

| use | part of the document | what it is |
| --- | --- | --- |
| fabric retrofit U-values | **Appendix S**, Tables S3 and S4 | derived from it — a *tuning* use |
| PL-DHW-01 hot-water volume | **Section 4**, 125 L/person/day | a genuine validation |

The second is not circular, and deliberately so. D-043 built hot-water demand
from draw events tied to simulated activities *rather than* from DEAP's
floor-area route, "so the model could disagree with it". The two uses read
disjoint parts of a 213-page manual.

`Source.model_development_exposure` is one value per source, so it cannot say
"tuning for Appendix S, reference for Section 4". Forcing it to `tuning` would
mislabel PL-DHW-01 as scored against a calibration input; leaving it
unexamined would hide that the fabric is derived from the same document.

**What was done instead.** Exposure stays `design`, the `used_for` states the
section-level split explicitly, and the suite already reports a
design-exposed pass in its own category — `n_pass_against_a_design_exposed_reference`
— neither counted as independent nor as a calibration input. A test pins the
arrangement so it cannot drift silently.

**What resolving it would take.** Section- or table-level provenance on a
source: a list of (section, exposure, used_for) rather than one value. That is
a schema change affecting every manifest, and it is only worth doing if a
second document develops the same split. Recorded so the next reader knows the
field is coarser than the practice.

---

## I-062 — `retrofit_heat_pump` and `der_smart_controls` were reported "applied" and changed nothing

**Status: fixing in week 3 step 2 (I-054).** Found by probing the series rather
than by reading the code, which is why it survived a decade of runs.

`apply_year_to_slice` counts every WP5 measure it applies into
`wp5_measures_applied`, and the ten-year artefact publishes that count. Two of
the five measures were counted there while leaving the energy series bit-for-bit
unchanged:

| measure | decade count | what the slice does | what reads it | series changes? |
| --- | --- | --- | --- | --- |
| `der_pv` | 6 | inserts a `PVSystem` into `sl.pv` | `run.py:548` | **yes** |
| `der_battery` | 3 | sets `building.has_battery` | `run.py` `initialise` | **yes** |
| `retrofit_heat_pump` | 7 | `owned[hh]["heat_pump"] = {...}` | **nothing** | **no** |
| `der_smart_controls` | 10 | `owned[hh]["smart_heating_control"] = {...}` | **nothing** | **no** |

Measured on a gas-boiler dwelling over two January days, one mutation at a
time, every `*_wh` field compared: `scratchpad/probe_der.json`, reproduced by
`probe_der.py`. 17 of the decade's 47 passport events were inert.

**Why.** The runner decides the heating path on
`building.heating_system == "heat pump"` and `building.heating_fuel`
(`run.py:537-543`). It never consults `owned`. The `owned` map feeds
`appliances.trigger_cycles`, where an entry only matters if the appliance
catalogue has a signature keyed to it — and `"heat_pump"` there is a *signature
type* in `hvac_types`, not an ownership key. `smart_heating_control` appears
nowhere else in the tree at all.

**Why this is worse than the fabric deferral it sat beside.** The fabric
deferral was *declared*: `wp5_deferral_note` said the thermal parameters were
untouched and that a detector scored against those labels would be scored
against a change the series does not contain. These two were declared
**applied**. A reader of `wp5_tenyear.json` had no way to tell the difference,
and 17 D20 labels pointed at steps that were not there.

**The lesson for the rest of the build.** "Applied" meant "the slice field was
set", and no test asked whether setting it did anything. The fix therefore
includes a test per event type that fails when pre-event and post-event physics
are identical — the test the user asked for in step 2, which is exactly the
instrument that would have caught this on the day it was written.

---

## I-063 — ten D20 labels point at a step DEAP rates at zero

**Status: open, declared, not fixable by inventing a magnitude.**

The I-062 fix made `der_smart_controls` dated and sourced. The source's answer
is that on a boiler home the measure does nothing: DEAP Table 4e gives a
living-area temperature adjustment of **0** for every control category from
"room thermostat only" upward — including "time and temperature zone control" —
and Table 4c(2) penalises only the *absence* of thermostatic control, which
every dwelling in this model has since I-033 put a closed-loop thermostat in
the solver. Only a heat-pump home moves, by Table 4c(4)'s published
0.70 → 0.75.

Ten of the decade's forty-seven passport events are smart-control installs. Most
land on boiler homes. Each still emits a D20 change label of class `equipment`,
and the series under that label does not change.

**Why this is not I-062 again.** I-062 was a count that said "applied" about
events that were not. This is a count that says `no_rated_effect` and names the
table that says so — `passport_effects_with_no_rated_effect` in the run
diagnostics, and `MEASURE_REACHES_THE_SERIES` in the life course. A detector
scored against these labels will score false negatives, and the artefact now
says why rather than leaving the scorer to find out.

**Three ways to resolve it, none taken here.**

1. *Give the measure a saving.* Forbidden by D-072 and it would be the worse
   error: a number chosen to make a label true is a number chosen for its
   effect on a score.
2. *Find a source DEAP does not have.* The honest candidate is a measured
   trial of smart heating controls with a published mean saving. None was found
   in a statistical catalogue, and a single trial would not give the Irish
   distribution anyway. Recorded as the search that would retire this.
3. *Stop emitting the label.* Defensible and currently rejected: the event
   really happens to the building, D03 really records it, and a detector that
   is told nothing happened loses the chance to be scored on a hard negative.
   A label whose series does not move is a **true negative for the detector and
   a true positive for the passport**, and suppressing it would hide that
   distinction rather than resolve it.

**What would change the decision.** If the tier-aware scoring work finds that
these labels dominate the `equipment` class's false-negative rate, option 3
becomes a reporting decision rather than an evidence one. Measure it before
deciding.

---

## I-064 — the DEAP emitter derating applies to converted heat pumps, not to the town's own

**Status: open, declared asymmetry.**

`EstateRunner.hp_emitter_adjustment` is populated only by a dated WP5
conversion. A dwelling that had `heating_system == "heat pump"` at t0 — assigned
by the population layer from EBQ02's heat-pump share — is absent from the map
and keeps its previous treatment: the Carnot-shaped COP with no Table 4c(4)
adjustment at all.

So two heat pumps in the same town are modelled differently, and the one
converted during the run is the *pessimistic* one.

**Why it was left that way rather than fixed in passing.** Applying the
derating to the town's t0 heat pumps changes the fabric-independent heating
electricity of every one of them, which moves the E1 baseline, the committed
plausibility results and the D-073 pre-registered U31 arms. That is a physics
revision with its own evidence requirement, not a side effect of adding a
conversion handler, and doing it inside this step would have mixed the two
changes in one measurement.

**What the right answer probably is.** A t0 heat pump's emitter is whatever the
BER assessment found, and the assessed population is already loaded
(`physics/fabric_assessed.py` reads 1,024,584 dwellings). The BER data has
space-heating system fields, so the emitter branch could be *derived* per
dwelling rather than declared — which would retire A-48 as well. That makes
this a sourcing opportunity rather than a correction, and it belongs with a
re-run and its own pre-registration.

**Until then:** no claim may be made that compares a converted dwelling's
heating electricity against a t0 heat-pump dwelling's, because the comparison
would be between two different models.

---

## I-065 — the model's declared move rate sits above the bound Census 2022 implies

**Status: open, measured, NOT changed.** Raised by U33's own fix.

Replacing the self-referential `move_out` criterion with Census 2022's "usual
residence one year ago" for Cobh gave the comparison its first outside number,
and the number does not endorse the model:

| quantity | value | source |
| --- | --- | --- |
| Cobh person move rate, 2021→2022 | **0.060319** /yr | `SAP2022T2T3TOWN22`, "Cobh, Co Cork" |
| model's declared household out-move rate | **0.065** /yr | `hazards.py` A-25b |
| ratio | **1.078×** | |

And the Census rate is an **upper** bound on the household rate, not an
estimate of it: a household that moves takes everyone with it, so for
whole-household moves the person and household rates are equal, while an
individual move — leaving home, moving in with a partner — adds a person-move
and not a household-move. So the household rate implied by Cobh is *at most*
0.0603, and the model declares 0.065.

**Why nothing was changed.** The declared hazard was not touched, and that is
the point of the exposure discipline rather than an oversight: this source is
`none`-exposed, the whole value of it is that the model was not fitted to it,
and adjusting 0.065 down to 0.0603 the moment the number arrived would convert
the only outside evidence on household turnover into a calibration input. It
would also be the wrong arithmetic, since 0.0603 is a bound and not a point
estimate.

**What the test now says, and it is worth being precise about.** The observed
count is **34** against **34.58** expected under the Census rate, inside
`[23.05, 46.10]`. The count passes. The *rate* is what sits outside the bound,
and the Poisson interval over 573 household-years is far too wide to detect a
7.8% rate difference — so the passing count is not evidence that the rate is
right. Both facts belong in the report.

**Two reasons the discrepancy may not be real**, recorded as directions and not
corrected for:

1. The question counts moves **into** Cobh; the hazard is a move **out**. These
   balance only in a stationary population, and Cobh grew between 2016 and 2022.
2. The window is April 2021 to April 2022, which included the tail of the Covid
   restrictions. Moving was suppressed, so the observed rate may be low for the
   decade. The 2016 edition (`SAP2016T2T3*`) is in the catalogue and would give
   a pre-Covid comparison.

**What would resolve it.** Read the 2016 and 2011 editions of the same question
and see whether 0.0603 is a Covid artefact or the level. That is a cheap check
on a source already found, and it is the right next step — not a change to the
hazard.

---

## I-066 — the provenance record could not see a library downgrade

**Status: fixed.** A near-miss rather than a defect in a result, and recorded
because the mechanism that let it through was real.

Installing `pandapower` for the week-3 S11 network work — which design 9.3
mandates for week 3 — resolved `pandas` from **3.0.6 down to 2.3.3**, because
pandapower requires `pandas<3`. `pip` reported it; nothing in the project did.

**Why that was dangerous rather than merely untidy.** Every WP5 year runs in a
**fresh process**. A ten-year build already under way would have had its early
years written by pandas 3.0.6 and its later years by 2.3.3, and:

* the reproducibility contract compares a run against *itself* re-run, so it
  would have reported the build as reproducible;
* `v1/evidence/machine.json`, the provenance artefact, recorded the platform,
  the CPU brand, the memory, the free disk and the Python version — and **not
  one library version**;
* the multi-worker determinism check compares workers inside one process, so it
  cannot see a difference between processes either.

Nothing in the build was comparing the two halves, so the failure mode was a
dataset silently written by two different versions of its own numerics, carrying
a green reproducibility result.

**Caught by luck, and that is worth admitting.** The ten-year re-run had been
launched minutes earlier and had completed **zero** years when the install
landed, so no mixed-version data exists. Had it been three hours in, the
artefact would have been published.

**What was done.**

1. The run was **restarted from zero**, not continued.
2. `pyproject.toml` pins `pandas>=2.2,<3` and `pandapower>=2.14,<4`, with the
   reason in the file, so the bound is a stated constraint rather than whatever
   the resolver last did.
3. `report/artefacts.py` grows `package_versions()` and `machine.json` now
   carries the version of every library that can change a simulated number —
   numpy, pandas, pyarrow, duckdb, numba, scipy, pvlib, pandapower, pypdf. A
   package that is absent records `"NOT INSTALLED"` rather than being omitted,
   because the difference between "it was not installed" and "nobody wrote it
   down" is the whole value of the record.

**What is still open.** The versions are now *recorded*, not *enforced*: a
future run under different versions will say so in its artefact, and no check
compares one run's `packages` block against another's. Enforcing it means
deciding what a version change should do to a published result, which is a
policy question and not a one-line assertion. Recorded rather than fixed in
passing.

---

## I-067 — `compliance_only` exports the full energy series; the mitigation does not exist

**Status: fixing.** Found by running design 7.8's privacy test, which had never
been run. It is the first thing that test found.

`EXPORT_CONFIGS["compliance_only"]` is described in `edge/export.py` as "Only
flexibility compliance leaves the home; least settlement value, least inference
risk", and in design 7.8 as one of the four mitigations for a configuration
that fails the inference test. It is not a mitigation. Measured on the
delivered package:

| config | rows | null `import_wh` | Σ `import_wh` (Wh) | null `building_energy_profile` |
| --- | --- | --- | --- | --- |
| `home_30min` | 876,000 | 0 | 163,137,265.9 | 0 |
| `home_15min` | 1,752,000 | 0 | 163,137,265.9 | 0 |
| **`compliance_only`** | **876,000** | **0** | **163,137,265.9** | 876,000 |

`compliance_only` exports the **complete half-hourly import series**, summing
to exactly the same energy as `home_30min`. Its inference risk is therefore
**identical** to `home_30min`'s, which the privacy test measured at an
occupancy AUC of 0.8655.

**Why.** `build_export` gates only the derived shape string on
`include_profile`:

```python
if config.include_profile:
    out["building_energy_profile"] = [...]
else:
    out["building_energy_profile"] = None
```

`import_wh`, `export_wh`, `interval_peak_w` and `interval_min_w` are assembled
unconditionally, several lines earlier. So the flag suppresses the *summary*
and keeps the *raw series* — the opposite of what it is for.

**A second, smaller fault beside it.** `flex_compliance_pct` is null in all
876,000 `compliance_only` rows, because the E1 run raises no flexibility event
to comply with. So the configuration suppresses the one field it should carry
and carries the one it should suppress. It is inverted in both directions.

**Why it was invisible.** Nothing read D19 adversarially. The schema audit
checks that only declared fields appear, which passed — `import_wh` *is* a
declared D19 field. The export test checks that R09's forbidden fields are
absent, which passed — no occupancy or person field is there. No test asked
whether a configuration differs from the configuration it is supposed to be
safer than, and `export.py`'s own docstring said the 7.8 test "has NOT been
run. No privacy claim is made here" — which was true, and was the whole
exposure.

**The fix.** `include_profile=False` suppresses the energy series, not the
summary of it: `import_wh`, `export_wh`, `interval_peak_w` and `interval_min_w`
become null and only the compliance fields remain. A test asserts that no two
configurations with different `include_profile` carry the same energy, which
is the check that was missing rather than a restatement of the fix.

**What the measured privacy result means now.** The AUC measured for
`compliance_only` is `home_30min`'s, because on the package as it stood they
were the same data. That measurement is not withdrawn — it is what the
delivered package leaked — and the artefact records that it was taken before
this fix.

---

## I-068 — nobody in Baile Nua is ever away

**Status: open. The most consequential gap the privacy test found, and it is
not a privacy gap.**

Design 7.8 names "absence periods (holidays)" as a target and a holiday
detector as one of four attacks. The attack could not be scored. The reason is
not the test:

Over **18,250 building-days** (50 homes × 365 days, `v1/ground_truth/D16`):

| quantity | value |
| --- | --- |
| minimum daily occupied fraction, any home, any day | **0.4375** |
| 1st percentile | 0.5729 |
| median | 0.9583 |
| building-days below 25% occupied | **0** |
| building-days below 50% occupied | **11** |

**No dwelling is ever empty for a whole day, in a whole year.** Homes empty
*within* a day — people go to work and school, and the minimum of 0.4375 means
a home can be empty for over half a day — but no household ever goes away.

**What that costs, beyond the unscoreable attack.**

1. **The occupancy base rate is 0.899**, so "somebody is home" is the answer
   90% of the time. A dataset for occupancy-detection research is missing most
   of its negative class, and any detector trained on it will be calibrated
   against a population that never leaves.
2. **The holiday-detection task cannot be posed at all**, and it is one of the
   change-detection tasks the dataset exists to support.
3. **The privacy result is biased towards safety.** An empty house has a
   distinctive flat profile, and absence is the easiest thing to infer from a
   meter. A model with no absences understates the inference risk of the real
   thing, and the measured AUC must be read with that in mind — it is recorded
   in the privacy artefact for exactly that reason.

**Why it happens.** The activity engine always places a person somewhere, and
the day skeleton is anchored to a wake time and a sleep window in *this*
dwelling. There is no mechanism that takes a household out of the model for a
run of days. WP6's calendar carries public holidays and school terms, which
change *what* people do and not *whether they are here*. The life course moves
people between dwellings permanently; it has no temporary absence.

**What fixing it needs**, and why it is not done here: a holiday mechanism with
a sourced rate. CSO publishes household travel and holiday statistics (the
Household Travel Survey, and tourism tables on trips taken by Irish
residents), so the rate is likely sourceable rather than `[A]` — which makes
this a sourcing task rather than a declared assumption, and it deserves a
search record and a decision rather than a number inserted late in a session.

---

## I-069 — the population matches every marginal and gets the age × economic-status joint wrong by a third

**Status: open. The most consequential finding of week 3.** Found by building
design 5.2's person-level joint validation, which is a week-3 item.

`synthesise.py` draws each person's economic status from their small area's
marginal with **no age conditioning** above 15:

```python
econ_label = (_draw_from(p_gen, area_marg["economic_status"])
              if member.age >= 15 else "student")
```

Every marginal is therefore matched — IPF guarantees it, and
`saps_marginals.json` reports it as passing — and the age × status joint is the
**product of the two marginals**, which is not what the Census shows.

Measured against **F1054** (Census 2022, principal economic status by age
group, held out at exposure `none`, stratum "Towns 10,000 population and over",
which is Cobh's), on 2,267 town residents aged 15+:

**Total variation distance 0.3339** — a third of the probability mass is in the
wrong cell.

Six cells the Census says are essentially empty, populated:

| age band | status | Census share | town people |
| --- | --- | --- | --- |
| 15–24 | retired | 0.00002 | **44** |
| 25–34 | retired | 0.00016 | **45** |
| 35–44 | retired | 0.00029 | **59** |
| 55–64 | student | 0.00060 | **42** |
| 65+ | student | 0.00014 | **30** |
| 65+ | unemployed | 0.00088 | **13** |

And the cells that should be full are not:

| age band | status | Census | town | ratio |
| --- | --- | --- | --- | --- |
| 65+ | retired | 13.13% | **2.16%** | 0.16 |
| 15–24 | student | 9.92% | **1.63%** | 0.16 |
| 65+ | employed | 1.41% | **6.35%** | 4.49 |
| 35–44 | retired | 0.03% | 2.60% | **90.6** |

**Why the existing joint checks did not catch it.**
`population/joint_metrics.py` validates joints and passes. It works at **area**
level — it correlates one small-area marginal against another across areas
(retired share against owner-occupied-no-mortgage share, unemployment against
social renting) and asks whether the town reproduces the between-area
correlation. That is a real check and it is structurally unable to see a
person-level fault: every area can have the right retired *share* while every
retiree in it is the wrong *age*.

**What it affects downstream.** Economic status drives `work_pattern`,
`remote_share` and the activity engine's whole day skeleton. So:

* 44 + 45 + 59 = **148 working-age people are retired**, and therefore at home
  all day with no commute;
* **72 people aged 55+ are students**, attending school or college;
* 65+ employment is 4.5× too high, so pensioners commute.

That is a material distortion of the occupancy and load patterns the whole
dataset exists to represent, and it feeds I-068's observation that occupancy is
unrealistically high — a town with 148 spurious retirees is a town that is
unusually often at home.

**Why it is not fixed here.** The fix is to condition the economic-status draw
on age, which is correct and small. Its consequence is not: the population
changes, so every artefact in `v1/` and `wp5/`, the E1 gate result, the U31
held-out arms and the D-073 pre-registration were all produced on a population
this would replace. That is a decision with a full re-run attached and a new
pre-registration, not an edit at the end of a session.

**What the fix needs.** F1054 is published by settlement stratum and would be
the natural conditioning table — but using it to *build* the population moves
its exposure from `none` to `tuning` and retires it as the validation
reference, which is I-058's rule. So the conditioning should come from the SAPS
small-area age × status cross-tabulation if one is published at that geography,
with F1054 kept held out to check the result. Establishing which SAPS table
carries that cross-tabulation is the first step and has not been done.

---

## I-070 — 33 people are in the town before they are born

**Status: open, small.** Found alongside I-069.

33 of 2,917 persons (1.1%) have a `birth_date` **after** the t0 reference date
of 2022-01-01, spread through 2022 to a maximum of 2022-12-31. All 33 are
`role="child"`, `econ_status="home duties"` — age-0 children whose birth date
was drawn uniformly inside their age-0 year instead of in the twelve months
*before* t0.

So a person recorded as resident in the town at t0 has a birth date up to a
year later. Any age computed from `birth_date` at t0 is **negative** for them,
which is how this was found: the joint validation counts them.

**What it affects.** Little in practice — all 33 are infants whose modelled
behaviour is minimal — but D05's `birth_date` and the t0 snapshot disagree,
and anything that computes age from birth_date gets a negative number without
warning. `person_frame_from_town` now counts them explicitly rather than
letting them vanish into the under-15 exclusion.

**Fix.** Draw an age-0 child's birth date in `[t0 - 365 days, t0)`. It belongs
with I-069's re-run rather than as a separate population change.

---

## I-071 — the build has two definitions of a person's age

**Status: open, latent, worked around where it bit.** Found while fixing the
venue assignment after I-069.

Two definitions coexist:

| definition | where | how |
| --- | --- | --- |
| `member.age` | `population/households.py` → `synthesise.py` | from the IPF age band and the drawn birth year |
| recomputed age | `population/venues.py::person_frame_from_town`, and anywhere else that reads `birth_date` | `(t0 − birth_date).days // 365` |

They disagree by one for anyone whose birthday falls between 1 January and
their drawn day-of-year: the synthesis calls them 5, the recomputation calls
them 4.

**How it bit.** The venue assignment tested `5 <= age <= 12` for primary
school. **34 five-year-olds** got no school, because the recomputed age called
them 4. The test looked correct and was reading a different quantity from the
one the synthesis used.

**Worked around, not fixed.** The assignment now keys on `states.school_year`,
which is the synthesis's **own** marker of who is at school and in which year,
so it cannot disagree with the synthesis about who is a pupil. That is the
right authority for this use and it does not resolve the underlying split.

**Why it is not fixed here.** Fixing it means choosing which definition is
canonical and making every consumer use it, and the two are not
interchangeable:

* `member.age` is what the population was *fitted* with — the SAPS age
  marginals, the household-composition joint, and `saps_marginals.json`'s
  23/23 pass are all in terms of it. Changing it would move the fitted
  population.
* `birth_date` is what the *datasets* carry, and it is what any downstream
  consumer of D05 will compute age from. It is also what must drive school year
  and pension age over a ten-year run, because those advance with the calendar
  and a banded age does not.

So the canonical answer is probably "`birth_date` everywhere, with the
synthesis deriving `member.age` from it rather than the reverse" — which is a
population change with a re-run attached, and it should travel with I-069's
re-run rather than after it.

**Where else it may bite.** Anything comparing a banded age against a
recomputed one: the F1054 and CNA25 joint validations (which use the recomputed
age, so a person can be scored in the band below the one they were fitted in),
`lifecourse/hazards.py`'s age-specific rates, and the school-year advance in
the ten-year run. None is known to be wrong; none has been checked, and that is
the honest state.

---

## I-072 — D28–D31 are built; E2-7 still fails, on D31's market series

**Status: open, and the gap is a source-acquisition gap rather than a
generator gap.**

Design 6.4's eight additions and 6.5's four rule families are E2-7's criterion:
"D28 to D31 pass the 6.5 tests". After week 3:

| dataset | built | 6.5 rules that run |
| --- | --- | --- |
| D28 `study_protocol` | **yes** | 1, 3 |
| D29 `household_survey` | **yes** | 1, 3 |
| D30 `recorded_metadata` | **yes** | 1, 3 |
| D31 `external_series` | **weather only** | 1, 2 (weather half), 3 |

`tests/test_nonsensor_65_rules.py` — 17 tests, all passing — covers:

* **rule 1**: every one of the 51 schema fields across D28–D31 names the
  real-world mechanism that would produce it, and the rejection is live; the
  **too-good** test on appliance omission and the **signed** occupancy
  overstatement; the **join** test on survey household size against the truth;
  no latent trait, true schedule or causal link emitted; and consent
  demonstrably non-random in the privacy trait, which is the selection effect
  design 6.4 exists to carry;
* **rule 2** on the weather half: D31's station rows and D15's site truth
  carry the same `realisation_id`, the station differs from the site but
  correlates above 0.9, timestamps are UTC interval-start and monotone, and a
  gap-filled value is flagged rather than hidden;
* **rule 3**: every one of the seventeen planted rates in `PLANTED_RATES` is
  re-estimated from the emitted data and must come back — including the
  *conditional* one, where BER staleness must be recovered among retrofitted
  homes and must be **exactly zero** among the rest, because the mechanism is
  "the certificate predates the upgrade" and not noise.

**Why E2-7 still fails. Two reasons, and neither is partial credit.**

1. **D31's market series are not built**: wholesale prices, carbon intensity,
   system demand and flexibility-service events. Their publishers are EirGrid
   and SEMO, neither declared in `SOURCES.md`, and the standing rule is that
   every source is declared before use. Acquiring two new publishers' series —
   with their licences, revision conventions and time-zone handling — is a
   source-acquisition exercise. Specifically blocked: 6.5 rule 2's
   cross-correlation test, "prices correlated with wind, demand and
   temperature; carbon intensity with the generation mix", cannot run on series
   that are absent.
2. **Rule 4, blind-evaluation safety, is NOT EVALUABLE.** Its test is "a
   classifier given only D28 to D31 features can't separate Baile Nua from
   **the real reference package**", and no real reference package exists in
   this build — acquiring one is the S-track's work. A classifier trained
   against nothing would produce a number with no meaning, so it is reported
   unevaluated rather than scored.
   `test_rule_4_is_not_evaluable_and_that_is_not_a_pass` pins that, and will
   fail the day a reference package appears, which is the right time to
   replace it with the classifier.

**Also not built from 6.4's eight:** item 6, the labelled sub-metered subset
(20–50 homes with appliance-level channels and an installer log, including
mislabelled and failed channels), and item 8's operator incident log. Item 2's
meter-point keying already holds — D18/D19 are keyed by an opaque
`premises_id` and the household link is GT-only — and item 5's embedded trial
is in D28's `trial_arm` and `arm_deviation`.

**What it would take.** Declaring EirGrid's system demand and carbon intensity
and SEMO's day-ahead prices, then generating the correlated structure 6.5 rule
2 requires for projected years. That is a day's work and it is the only thing
between the current state and E2-7.

---

## I-073 — the tell audit's first run found four tells in the delivered observable view

**Status: logged as limitations, per design 7.9's "fixed or logged".**

Design 7.9 item 4 requires an automated tell pass before each blind round.
`baile_nua/release/tell_audit.py` is that pass and this is its first run, on
the delivered `v1/observable` view (`v1/evidence/tell_audit.json`).

| # | severity | tell | what was found |
| --- | --- | --- | --- |
| 1 | **high** | missing failure modes | `D19.quality` is **only `ok`** across 3,521,520 rows |
| 2 | medium | missing failure modes | `D18.provenance` is **only `metered`** across 66,097,553 rows |
| 3 | medium | suspiciously round values | **7 of 9** D18 channels are **exactly 100%** integer |
| 4 | low | final-digit distribution | `D18.value`'s final digit is 96.7% zero |

**Findings 3 and 4 are the same phenomenon** seen two ways, and are not
independent evidence: the final-digit spike *is* the integer-ness. Reported
both because the per-channel view says which channels and the digit view says
how strong, and neither alone says both.

**Finding 1 is the serious one.** Design 6.3 requires every observable value
to carry "a quality flag (ok, estimated, missing, suspect, drift, fault)" and
that "meter swaps, firmware changes and reporting gaps occur at realistic
rates". D19 has none: not one estimated value, not one gap, not one suspect
reading in a year of 50 homes. A series that never went wrong is the strongest
synthetic tell there is, because every real series has gone wrong.

D18 is better and not good: it carries `drift` on 568,212 rows of 66,097,553
(0.86%) and `ok` on the rest — so the *mechanism* exists and only one of the
six flag values is ever used.

**Finding 3, and why it is a tell rather than a resolution.** An integer-valued
channel on its own is defensible: a meter reporting whole watts is a real
meter. What is not defensible is `import_w`, `export_w`, `ct_circuit`, `co2`,
`charger_w`, `inverter_w` and `pir` all at **exactly** 1.0000 while `temp` sits
at 0.0956 and `rh` at 0.5056. Real devices have a mixture of resolutions that
does not partition that cleanly into "all the power channels" and "the
environmental ones". It is a rounding step in the writer, and an analyst
comparing final-digit distributions across channels would see it in a minute.

**Logged, not fixed, and the reason is the design's own.** 7.9 says "fixed or
logged as a limitation", and which applies is a decision rather than a default:

* finding 1 **cannot be fixed by a flag**. Writing `estimated` on some rows
  without actually modelling a meter swap, a firmware update and a reporting
  gap would be a cosmetic change that makes the tell audit pass and leaves the
  data no more realistic. It needs 6.4 item 8's operator incident log and the
  failure mechanisms behind it, which are not built.
* finding 3 **could** be fixed by giving each channel its own resolution, and
  doing that now would change every D18 value in the delivered package, i.e. a
  re-run on top of the one already under way for I-069. It belongs with the
  next re-run, not inside this one.

**One correction to my own check.** Its first version reported D18's values as a
quantisation signature with a chi-square of 2.5 million, because it tested the
final digit of `value × 10000` whatever the column's resolution was — so an
integer-valued column failed by construction. That was the check measuring its
own assumption. It now detects the column's resolution first; the finding
survives the fix, with the chi-square against the right denominator.

**What the audit does NOT cover**, recorded in
`unchecked_tell_classes()` so "the tell audit found four things" is never read
as "there are four things": distributional realism (7.3's discriminator
screen), cross-OBS consistency as a tell (needs a real reference),
behavioural implausibility, and the tells nobody thought of — which is the
category that matters most and the reason 7.9 pairs this pass with an
adversarial analyst. **The adversarial analyst has not been run.**

---

## I-074 — the observable view announces that it is synthetic, in all 26 manifests

**Status: open. CRITICAL for the blind protocol, and it is a genuine conflict
between two correct rules rather than an oversight.**

Every manifest in `v1/observable/` carries:

```json
"label": "UNVALIDATED SIMULATION EVIDENCE: E1 engineering candidate"
```

**26 of 26 manifests checked, 26 disclosing.** Found by
`release/tell_audit.audit_manifests`.

**Why it matters.** Design 6.3's own table says the observable view goes to
"Model developers, BNIT experiments, **blind evaluators**", and the same
section says "The synthetic flag lives in the release manifest, **which the
evaluation organiser holds**". Design 7.9 reinforces it: the analyst "must
never have seen this design", and "synthetic provenance stays with the
organiser and is disclosed after the blind phase".

So **a blind evaluation is impossible against this package.** No other tell
matters once the box says what is inside it: every other finding in I-073 is
about whether an analyst *could* work it out, and this one hands it to them in
the first file they open.

**The conflict, which is real.** A standing instruction on this build is to
label all outputs "UNVALIDATED SIMULATION EVIDENCE", so that nobody mistakes
simulation for measurement — and that rule has done real work: it is on every
report, every artefact and every number quoted in this project. Design 6.3
requires the observable view *not* to carry that flag. **Both are right**, and
they are right about different risks:

* the labelling rule guards against a simulated number being cited as a
  measurement;
* 6.3 guards against a blind evaluation being worthless.

**The design already resolves it, by location.** The flag belongs in a
**separate, organiser-held release manifest** — not in the dataset manifests
shipped inside the view. The ground-truth and evidence views keep the label
(the audit confirms all 27 GT manifests carry it, which is correct there). The
observable view's own manifests carry provenance codes, quality flags and
hashes, and the organiser holds the mapping from package to provenance.

**Nothing was stripped.** The audit reports; it does not edit. Removing the
label from the observable view weakens a standing instruction, and which of
the two rules gives way in a shipped package is a decision for Brian, not a
default for me to pick. What I can say is that the current arrangement
satisfies the labelling rule and makes 7.9's protocol unrunnable, and that the
design's own answer is the third option: keep the label, and put it where the
organiser holds it.

**Until it is resolved:** no blind round may be run on `v1/observable`, and the
E2 report records the tell audit as having found a critical finding rather than
as having passed.

---

## I-075 — the MIMIC panel exists and is not linked *in time*

**Status: open. WP-M2's remaining gap, and the same shape as I-062.**

The MIMIC work is substantially done and its counters meet E1's target
(`v1/evidence/mimic_tests_T1_T10.json`):

| counter | value |
| --- | --- |
| unique synthetic participants | **11,664** (target 10,000, met) |
| completed sessions | **10,832** |
| completed responses | **146,324** |
| **linked Baile Nua panel participants** | **1,014** |
| unlinked extended-pool participants | 10,050 |
| abandoned sessions (never merged into the above) | 832 |

T1, T5, T7, T9 and T10 PASS; T2 and T4 are RECOGNISED_LIMITATION; T3 FAILS on
planted segments and PASSES in the null mode.

**What is missing.** Design's WP-M2 wording: "Every adult who would plausibly
respond completes repeated sessions **in survey waves across the 10 simulated
years**. At 8 to 15 sessions each ... Every answer links to that person's
simulated behaviour."

`MimicRunner.run_participant` and `run_batch` both take a
`simulated_session_date` parameter and record it in the result. **Nothing in the
codebase or the scratchpad ever passes it**, and the string
`simulated_session_date` does not appear anywhere in the delivered artefact. So
every session is undated in simulated time.

The consequence is specific and it is the point of the dataset: a linked
answer can be joined to *that person*, and not to *that person at that moment*.
"Every answer links to that person's simulated behaviour" is satisfied at the
person level and not at the wave level, so the panel cannot support the
question it exists for — did this household's stated flexibility change after
the retrofit, the new baby, the job change — because the answers have no
position in the ten years the behaviour does.

**Why this is the same shape as I-062.** The parameter exists, is threaded all
the way through, is written into the result record, and is never set. Nothing
failed, because nothing asked. It was found by looking for the value in the
artefact rather than by reading the signature.

**What the fix is.** A wave schedule over the decade — the design's 8 to 15
sessions per linked adult across 2022–2031 — passing each wave's simulated date
into `run_batch`, and a test that fails if a linked session's
`simulated_session_date` is null. The runner already accepts it; what is needed
is the caller and the schedule.

**Why it is not done here.** Running 1,014 linked participants × 8 to 15 waves
is of the order of 10,000 fresh sessions against the local MIMIC, and the
machine is currently running the I-069 regeneration chain (E1, U31 and the
ten-year slice). The two would contend for the same cores and the MIMIC run
would distort the runtime figures the scale criterion is measured from. It is
the next MIMIC task, not an afterthought to this one.

**Not claimed:** that the existing 10,832 sessions are wrong. They are valid
sessions with valid responses and they satisfy T1's participant target. What
they are not is a *panel over time*.

---

## I-076 — D19's schema made design 7.8's `compliance_only` mitigation impossible to represent

**Status: fixed.** Found by the E1 run failing on I-067's fix, which is the
best way to find it.

I-067 made `include_profile=False` null the four energy fields. The E1 run then
failed at schema validation:

```
- D19.import_wh: required but 72000 null value(s)
- D19.export_wh: required but 72000 null value(s)
- D19.interval_peak_w: required but 72000 null value(s)
- D19.interval_min_w: required but 72000 null value(s)
```

D19 marked all four `required: true`. So a row with no energy was not a valid
D19 row, and **`compliance_only` — a configuration whose entire purpose is that
no energy leaves the home — could not be expressed in the dataset it is
supposed to be a configuration of.**

**This explains I-067 rather than merely accompanying it.** `include_profile`
gated only the derived `building_energy_profile` string because gating the
energy would have broken the contract. The mitigation was unrepresentable, so
what shipped was a configuration that suppressed the *summary* and kept the
*series* — and therefore had `home_30min`'s inference risk exactly, measured at
an occupancy AUC of 0.8655. I-067 was the symptom; this is the cause.

**The fix, and why it is not a relaxation.** The requirement is **conditional**:
present for every configuration that carries a profile, absent for
`compliance_only`. A flat `required: boolean` cannot say that, so the flag
becomes `false` and the condition moves to where a condition can live —
`test_the_energy_fields_are_present_for_every_profile_carrying_config` asserts
non-null for every profile-carrying configuration and **all-null** for
`compliance_only`. Nothing is weakened: a profile-carrying export with a
missing energy field still fails, and now so does a compliance-only export that
carries one.

A second test pins the flag's state with the reason, because the failure mode is
circular: if someone restores `required: true`, `compliance_only` becomes
unrepresentable again, and the next person to notice will do what the first one
did — gate the summary and leave the series in.

**What it cost.** The E1 run in the I-069 regeneration chain failed and the
chain was stopped and restarted from E1. Caught by a schema validator doing its
job on a change that was right, which is the cheap version of this discovery:
the expensive version is a blind evaluation run on a package whose
least-risk configuration is its highest-risk one.

**A second-order fault from the same fix, found by a warning.** The E1 run
emitted `FutureWarning: The behavior of DataFrame concatenation with empty or
all-NA entries is deprecated`, from the writer's `pd.concat` over the four
export configurations.

The cause: I nulled the four columns with `None`, which gives them **object**
dtype. Today's pandas excludes an all-NA column when resolving the result dtype
and still produces `float64`, so the delivered output is correct — and the
warning says it will stop doing that. When it stops, D19's `import_wh` is
written as an **object** column and the Parquet schema changes under a library
upgrade.

That is I-066's lesson in a different place: a library version silently
changing what the data looks like. Fixed by assigning `np.nan` with an explicit
`float64` dtype, which is unambiguous now and after, and pinned by
`test_a_suppressed_energy_column_is_float_not_object` — which also asserts the
writer's own concatenation is warning-free, so the next deprecation of this
kind fails a test instead of scrolling past in a log.

The E1 run in flight when this was found used the pre-fix code and its output
is unaffected: under pandas 2.3.3 the columns resolve to `float64` either way.
No re-run was needed for this, which is worth recording because the instinct is
to re-run on any finding.

---

## I-077 — my regeneration chain reported "U31 ARTEFACT OK" from two-day-old inputs

**Status: fixed in the chain; recorded because the failure mode is the one this
project keeps finding.**

The I-069 regeneration chain called `run_u31_frozen.py off` and
`run_u31_frozen.py on`. The script takes **two** arguments — arm and output
root — so both arms died immediately:

```
IndexError: list index out of range
  arm = sys.argv[1]; root = pathlib.Path(sys.argv[2])
```

The chain did not stop. The next step, `u31_art.py`, reads
`work/u31/{off,on}/diagnostics.json` — which still held the **10 October**
run, from before the fabric change and before the population fix — regenerated
`heldout_u31.json` from it, and the chain logged:

```
gradient: 1.7682 -> 1.6158 | gap closed 15.5% | residual p 7.849e-05
=== 14:47:05 U31 ARTEFACT OK ===
```

**An artefact with a fresh mtime and two-day-old content, announced as OK.**

**What saved it.** `git status` showed `heldout_u31.json` byte-identical to the
committed version, which is how the staleness was confirmed rather than
guessed: identical output from identical inputs means the inputs were not the
new ones. Had the content differed by a rounding, it would have looked like a
fresh result.

**The same failure mode as I-062, I-075 and the `n_passport_effects_applied`
report.** Something was threaded through, nothing read it, and the absence
announced success. Here the chain's `&&`/`||` guard was on the *artefact* step
and not on the *arms*, so a failed arm could not fail the chain.

**What was done.**

1. The arms were re-run with the right invocation.
2. More importantly, they were re-run **differently**. D-073's thresholds —
   gradient 1.6158, old 1.1806, new 0.7307 — are properties of the pre-I-069
   population, and 986 of 2,917 people changed economic status. Comparing a
   new-population "after" against the old population's baseline would be
   **I-059's error again**: a paired test across two samples. So *both* arms
   now run on the new population, the "before" one restoring the superseded
   era×multiplier fabric, with the same frozen membership — which is stable
   because the buildings are unchanged by the population fix.
3. `u31_newpop_prereg.json` reports the four conditions against D-073's
   **literal** thresholds *and* the new population's own measured before-values
   separately, so a population effect is never attributed to the fabric. The
   criterion is not edited, even though moving it to the re-measured baseline
   would be defensible — which is exactly why it is not done.

**What is stale until those arms land:** `v1/evidence/heldout_u31.json` and
`v1/evidence/u31_rerun_fabric.json` both describe the **pre-I-069**
population. Neither is withdrawn — each is a correct measurement of the
population it was taken on — and neither may be quoted as a result for the
current population.

---

## I-078 — the engine conflated "outdoors" with "away from home"

**Status: fixed.** Found by the WP7 venue-consistency criterion, which is what
it is for.

`ActivityEngine` mapped every activity whose zone is `outside` to
`location_kind = "venue"`:

```python
kind = ("in_transit" if zone == "in_transit"
        else "venue" if zone == "outside"
        else "building")
```

Seven activities have `zone == "outside"`. Six are genuinely away from the
dwelling — school, work at a workplace, shopping, social out, sport, religion
and civic. The seventh is **gardening**, and a person gardening is at their own
building, in their own garden. "Outdoors" and "away from home" are different
things and the mapping treated them as one.

**What it cost.** Every gardening interval became a presence row with
`location_kind="venue"` and `location_id=None` — **6,042 rows** in a 14-day
full-town run, 5.6% of all venue rows. The week-3 criterion "venue presence
consistent with person presence" therefore failed on rows that should never
have been venue rows at all.

**How it was found, and the order matters.** The criterion first failed with
**8,426** unnamed rows. Most were I-069's 241 adult "students" — a population
fault — and fixing that, plus adding the college venue the genuine 19-to-24
students need, took it to **6,042**. What remained could not be explained by
any missing venue, which is what pointed at the mapping rather than at the
venue stock. Fixing the venue layer first would have left this invisible: a
college venue for gardeners would have made the count go to zero and the
record wrong.

**The fix.** `OUTDOORS_BUT_AT_HOME`, a declared set, checked before the zone
mapping at both sites that build intervals — the primary one and the one that
rebuilds them after a joint plan, because a person gardening before a
negotiation and at a venue after it would be two different people.

Named as a set rather than special-cased on `"gardening"`, because the same
conflation applies to anything else outdoors-but-at-home added later: hanging
washing, DIY in a yard, a smoke on the step.

**The protection is the invariant, not the fix.**
`test_every_outside_activity_is_either_a_venue_type_or_outdoors_at_home`
asserts that each `outside` activity is exactly one of the two, so a new one
that is neither fails immediately rather than producing unnamed venue rows that
only a week-3 criterion would find, three artefacts later. A second assertion
refuses an activity declared as both, since the engine checks
`OUTDOORS_BUT_AT_HOME` first and the venue mapping would be silently dead.

**What it changes in the data.** D11's `location_kind` for gardening rows moves
from `venue` to `building`. That is a correction to the dataset, so the
full-town run was repeated.

---

## I-079 — twice in one session I changed the model while a multi-process build was in flight

**Status: guarded.** A pattern, not a single defect, and the second instance is
mine from twenty minutes ago.

| # | what changed mid-flight | what was in flight | caught by |
| --- | --- | --- | --- |
| 1 | `pandas` 3.0.6 → 2.3.3, from installing pandapower | the ten-year re-run, 0 years done | luck — the run had just started (I-066) |
| 2 | `ActivityEngine`'s location mapping (I-078's fix) | the ten-year re-run, **6 of 10 years done** | noticing, immediately after committing |

The mechanism is the same both times and it is structural: **every WP5 year
runs in a fresh process**, so it imports whatever the code is at the moment it
starts. A decade can therefore be written by two versions of the model while
every per-year check passes, the aggregate sums cleanly, and the
reproducibility contract — which compares a run against *itself* re-run —
reports it as reproducible.

The second instance would have produced a decade whose years 2022–2027 recorded
gardening at a venue and whose years 2028–2031 recorded it at the dwelling.
Both are internally consistent. The decade would not be.

**No mixed data was written.** All six completed years carry timestamps before
the edit (15:27 and 16:05–16:06 against an edit at ~16:11), and the three in
flight were killed. The run was restarted from zero.

**The guard.** `wp5_chain.sh` now records `git rev-parse HEAD` *and* a digest of
the working tree under `scripts/baile_nua` before the first year, re-reads both
after the last, and **refuses to write the aggregate** if either moved:

```
REFUSING TO AGGREGATE: the model code changed during the run.
  A decade written by two versions of the model is not a decade (I-066, I-078).
```

The working-tree digest matters as much as the commit: I-078's edit was
uncommitted for most of its life, and a HEAD check alone would have passed.

**What this does not cover.** A library upgrade that does not touch the working
tree — which is instance 1 exactly. `machine.json` now records every library
version that can change a number (I-066), so a *published* run says what
produced it; nothing compares two runs' versions. Closing that needs a decision
about what a version change should do to a published result, which is a policy
question and still open.

**Why it is recorded rather than quietly fixed.** Twice in one session, from
two different causes, with the second one mine while actively thinking about
the first. The pattern is not carelessness about a known rule; it is that a
long multi-process build has no notion of the code it belongs to. That is worth
a guard and worth writing down.

**A refinement, from tripping the guard on its own commit.** The first version
compared `git rev-parse HEAD` and the working tree's *dirty status*. Committing
I-079's own write-up moved HEAD while the restarted ten-year was running, so
the guard would have refused to aggregate a run whose model code had not
changed by one byte — only `ISSUES.md` and a shell script had.

A guard that blocks a two-hour aggregate for a documentation commit gets
switched off within a day, so it was corrected to digest the **model code
only**: every `.py` and `.yaml` under `scripts/baile_nua`, by content.

The dirty-status check was wrong for a second and less obvious reason. It
records whether files differ from the index, so an edit made *before* the run
starts is already in the baseline and invisible to it. Content-addressing both
ends is the only form of this check that works, and it is what the guard does
now.

The run in flight kept its own copy of the stricter script and will refuse; the
model digest is recorded at `model_digest_at_wp5_start.txt` so the aggregate can
be authorised against the thing that actually matters.

---

## I-080 — I edited a running shell script and it restarted itself, destroying two hours of work

**Status: my own error, fully self-inflicted, and the mitigation is boring.**

While the restarted ten-year chain was running, I edited `wp5_chain.sh` to
correct the over-strict guard from I-079. Bash reads a script **incrementally,
by byte offset**. The edit changed the file's length, so when the running shell
next read from its stored offset it landed back near the top of the file and
re-executed:

```
rm -rf $P/wp5; mkdir -p $P/wp5
```

**Six completed years were deleted** and the loop started again. For a few
minutes the process table held year 9 from the first pass and years 0, 1 and 2
from the second, all writing to the same directory. The log shows it plainly —
two `START` lines from one process, the second in the *corrected* format:

```
=== 16:13:44 START at 7f81f746... (baile_nua working-tree digest d41d8cd9...) ===
=== 18:22:40 START with model digest 7fea2b82... ===
```

**I had written down the risk and then taken it.** Twenty minutes earlier,
deciding how to fix the guard, I noted that "editing a running bash script can
cause it to execute garbage" and chose to write a corrected copy instead — and
then edited the original in the same breath, because the corrected copy and the
original were the same file.

**Cost:** about two hours of compute, and the ten-year had to start from zero a
third time.

**Mitigation, such as it is.** The chain now runs from
`wp5_chain_FROZEN.sh`, copied and `chmod 500`, so an edit fails rather than
corrupting a run in flight. That is the whole fix: a long-running script should
not be writable by the thing that is running it.

**A second finding, from the same log.** The two START lines show the guard's
digest went from `8680e0f7...` (computed at 16:15) to `7fea2b82...` — the
*model* digest changed mid-run, and the only thing I had touched under
`scripts/baile_nua` was `report/e2_gate.py`, the E2 report generator. That
reads artefacts and cannot change a number in the data.

So the guard as written would have refused a perfectly good aggregate because a
reporting module changed. It is now narrowed to exclude `baile_nua/report/`,
which is the second time in one session that this guard has been too strict —
and over-strictness is not a safe default here, because a guard that cries wolf
is a guard somebody removes.

## I-081 — the checkpoint recorded the hot water cylinder and the restore threw it away

**Status: FIXED, and it had been hiding behind a PASS for two days.**

`HouseholdState.as_dict` has written `dhw_tank_c` into every checkpoint since
U25 was wired in (commit `1059fff`, 09 October 15:50). `EstateRunner.restore`
never read it. So every replayed day began with the cylinder at its
construction temperature rather than the one the run recorded, and diverged on
the morning reheat — which is precisely what U25's own docstring says would
happen: *"a replay that restored the fabric temperatures but not the tank would
diverge on the first morning shower."* It was written down as a hazard and then
built anyway.

**Corrected measurement.** The first figures recorded here — 70 of 100
home-days falling to 56, worst difference 3,144 W falling to 144 W — were
measured through a harness that was itself broken (**I-084**), and none of
that movement is attributable to the cylinder. Re-measured with the harness
fixed, on 250 home-days, by restoring the tank or forcing it back to its
construction setpoint (a median 4.4 °C and up to 7.9 °C from the recorded
value):

| | mismatching home-days | worst difference |
|---|---|---|
| D16 `temp_living_c` and all four D19 fields | **0 of 250** | 0.0 |
| D16 `dhw_tank_c` | **250 of 250** | 5.63 °C |

So the defect is real and its effect is confined to the cylinder: for a gas
dwelling the reheat is gas, and the living zone does not feel a tank 5 °C out.

**Why nobody saw it, in two parts.** `v1/evidence/checkpoint_replay.json` was
measured on 09 October at 04:25 — eleven hours *before* the tank existed — and
E1 criterion 5 quoted it unchanged afterwards (**I-082**). And the replay
compared only `temp_living_c` out of D16, so even when re-run it could not have
seen this: the one test able to find a missing restore did not look at the
quantity that was missing. The comparison now includes `dhw_tank_c`, and that
extension is verified to have teeth by the 250-of-250 row above.

**The fix.** `restore` now sets `st.dhw.temp_c` from the value the checkpoint
already carries. No checkpoint format change, so the delivered run's hash chain
still verifies and the replay runs against the data as shipped. Only `temp_c`
is restored, and that is sufficient rather than partial: the other `TankState`
fields are cumulative run totals, and `simulate_dhw_day` reports each day's
figures through its return value, so nothing written to D13, D16 or D19 reads
them.

**The structural fix, which matters more.** `as_dict` and `restore` are two
lists of the same state maintained in two places, and nothing compared them.
`test_every_key_the_checkpoint_writes_is_read_back_by_restore` now parses both
and asserts the correspondence. Verified to fire: run against the pre-fix
`run.py` it reports `['dhw_tank_c']`. It is weaker than the replay — it cannot
tell whether a restored value is *used* correctly — but it fires on the next
field added to one list and not the other, which is the failure that actually
happened, and it costs milliseconds instead of twenty minutes.

## I-082 — E1's gate report cited evidence older than the run it describes

**Status: OPEN. The measurement is being redone; the guard is not built.**

Three of E1's eight criteria rested on artefacts measured before the population
was regenerated for I-069 (11 October 12:56) and before the delivered E1 year
was rewritten (14:35):

| criterion | evidence | measured | population behind it |
|---|---|---|---|
| E1-2 byte-identical at 1/8/12 workers | `worker_determinism.json` | 09 Oct 04:20 | pre-I-069, pre-U25 |
| E1-5 deterministic replay | `checkpoint_replay.json` | 09 Oct 04:25 | pre-I-069, pre-U25 |
| E1-6 MIMIC T1/T9/T10 | `mimic_tests_T1_T10.json` | 08 Oct 23:27 | pre-I-069; 1,014 linked panel participants drawn from it |

The gate report read each file, found a pass in it, and reported a pass. It has
no notion that an artefact can be *stale* — that a figure measured on a
superseded model is not evidence about this one. I-081 is what that costs: a
PASS carried for two days over a defect the quoted test would have caught.

It is the same error as I-066 and I-078 at the level of the *report* rather than
the run: the ten-year chain now digests the model code and refuses to aggregate
if it moved, and nothing does the equivalent for E1's evidence. The replay in
particular compares freshly-run code against Parquet written by whatever code
existed when the year was produced, so it silently measures a code *difference*
as a state gap — I-078's engine fix landed at 16:12, after the 14:35 year.

**What is needed:** the E1 report must refuse to cite an artefact older than
the run it describes, the way the E2 generator's `_need` refuses to print a
placeholder. Recorded rather than fixed in flight, because the honest number
comes first.

## I-083 — the youngest children wake latest, because an adult chronotype rule was extrapolated to toddlers

**Status: OPEN, unfixed, and it needs a source rather than a patch.**

`test_a_non_worker_wakes_later_without_going_to_bed_later` fails on the
regenerated population: non-workers' median workday wake is 07:50 against
workers-and-students' 07:23, a gap of 27 minutes where the test requires more
than 30. The test is right to fail, and the cause is not the test's threshold.

Measured on the E1 slice, 131 people, by the base the engine assigns:

| structured | child | 70+ | n | base | median wake | wake − base |
|---|---|---|---|---|---|---|
| no | no | no | 35 | 08:40 | 08:26 | −14 |
| no | no | yes | 19 | 08:15 | 06:34 | **−101** |
| no | yes | no | 8 | 08:30 | **11:56** | **+206** |
| yes | no | no | 54 | 07:10 | 07:16 | +6 |
| yes | no | yes | 1 | 06:45 | 04:45 | −120 |
| yes | yes | no | 14 | 07:00 | 08:10 | **+70** |

The two-base rule itself is sound — working adults, the only large cell, land
6 minutes from their 07:10 base. What is wrong is what the chronotype does on
top of it. `population/traits.py` draws

```python
chronotype = clip(-0.9 * age_z + N(0, 0.8), -3, 3)
```

so chronotype is deliberately anti-correlated with age, and I-051 then made
chronotype **select the quantile** of a HETUS wake distribution 187 minutes
wide between its 10th and 90th percentiles. A four-year-old's `age_z` is far
below zero, so the rule hands them a late-tail quantile: eight pre-school and
primary children wake at a median of **11:56**. Young children are early
risers, which is the one thing about children's sleep that needs no citation.
Nineteen over-70s get the mirror error at 06:34.

**Why it surfaced only now.** The group medians used to separate because the
pre-I-069 population put 243 "students" with a median age of 45 in the town, so
the structured group was full of adults drawing adult quantiles. Fixing the
age × economic-status joint removed them, leaving the student group to be
actual children — and the children's chronotypes then showed through. The
defect is older than the test failure; the population fix stopped masking it.

**Why it is not patched here.** The coefficient is unsourced — the comment
cites "design 5.3 sleep window" and no source key — so any replacement would
be a number from memory, which the brief forbids. It needs either a published
age-by-chronotype or child wake-time distribution, or an `[A]` flag with a
search record and a bound. Fixing it also re-dates every activity timing and
so every energy artefact in the release, which is a re-run of everything, not
an edit.

**What it does NOT affect.** The sleep window feeds activity placement, so it
touches overnight load shape (I-052's LP1 score, already reported with no pass
mark) and PL-PEAK-01. It does not touch the population joint, the fabric
physics, the network solve, or any of the three week-3 criteria that pass. The
2.4%-awake-at-02:00 and similar HETUS comparisons in `plausibility.json` are
the figures a fix would move.

**The test is left failing.** It is an acceptance test measuring a real
property, and the measured value is 27 against a required 30. Weakening it to
25, or regrouping students out of the comparison so the numbers pass, would be
tuning the test to the model.

## I-084 — the replay harness built a different model from the run, and reported it as a state gap

**Status: FIXED. It is the whole of the residual that I-081 did not explain.**

`run_year` constructs the estate runner with `income_quintile=sl.income_quintile`.
`bench/determinism.py` — both the worker-determinism arm and the replay — and
`bench/coverage.py` constructed it without. Every household's comfort shift was
therefore computed with no income quintile, so the harness simulated a
different model and compared its output against data produced by this one.

Measured on the fresh E1 year, 100 sampled home-days over 84 days:

| harness | mismatching home-days | worst difference |
|---|---|---|
| before | 41 of 100 | 0.667 °C on D16, 144.4 W on D19 |
| after | **0 of 100** | **0.0, exact** |

**What made it look like something else.** Three things, each of which sent the
diagnosis in the wrong direction:

1. The replay's report names a missing restore, so a reader starts at the
   checkpoint. The checkpoint was right: the stored state round-trips to full
   precision (17 significant figures) and restores exactly.
2. The divergence began mid-morning — the first 26 to 33 epochs of every day
   were bit-identical, then a difference of order 1e-5 °C appeared and the
   thermostat's switching amplified it through the day. That is the signature
   of a slightly different operand, not of a different decision, and it reads
   exactly like an un-checkpointed accumulator.
3. The determinism arm compared three runs **against each other**. All three
   built the runner the same wrong way, agreed byte for byte at 1, 8 and 12
   workers, and so certified nothing about whether any of them matched the
   delivered year. Agreement between arms of a harness is not agreement with
   the thing the harness measures.

The experiment that settled it: the replay failed on **day 0**, whose
checkpoint is the initial state. With no history to carry, nothing could be
missing from it, so the fault had to be in construction rather than in state.

**The fix.** One factory, `e1_run.build_runner`, with
`build_runner_for_slice` for the three callers that hold an `E1Slice`.
`income_quintile` is a **required** keyword with no default, so it cannot be
omitted silently again; `bench/coverage.py` builds its own households and
passes `None` explicitly. `test_the_harness_builds_the_runner_the_same_way_as_the_run`
parses `engine/` and `bench/` and fails on any `EstateRunner(...)` outside the
factory — it caught `coverage.py`, which I had not noticed.

**What it cost and what it did not.** Two hours of diagnosis, and E1-5 was
reported as a failure in the interim on a measurement that was the harness's
fault. It never touched the delivered data: the year, the ten-year slice, the
town runs and every plausibility figure come from `run_year`, which always
passed the argument. The determinism artefact's own verdict is unchanged —
byte-identical at 1, 8 and 12 workers — because all three arms moved together.

---

## I-085 — D-075 cites a U31 comfort-off arm that was never run on the new population

**Status: open. Does not change any verdict.** Found while answering whether
D-073 needs an "off" arm (`v1/evidence/u31_off_arm_question.json`).

D-075 ends: *"the measured change is the fabric **plus** this entailed
re-centring, and U31's comfort-**off** arm isolates the pure fabric effect at
no extra cost, because the reference does not apply there."*

That arm does not exist for the post-I-069 population. `work/u31_newpop_before/`
and `work/u31_newpop_after/` each contain **only** `on/diagnostics.json`; there
is no `off/` sibling in either.

**What it does not cost.** Nothing in D-073. Its four pass conditions are
defined entirely on the comfort-taking-ON arm — the pre-registration's own
baseline table is sourced to `heldout_u31.json`'s `gradient.on` and
`groups.*.on`, and condition 2 writes the pairing axis as *"the same 60
dwellings are simulated before and after"*, which is the fabric change, not the
ablation. Every figure in `u31_newpop_prereg.json` was recomputed from the two
on-arm diagnostics alone and reproduced exactly, so the criterion was never
left partly unevaluable. **U31 PASSES as written.**

**What it does cost.** The decomposition D-075 claims. The measured
1.6158 → 1.4134 move is the assessed fabric **plus** the entailed re-centring
of the comfort-taking reference from 2.08 to 1.813 W/K/m², and no artefact now
on disk separates the two. So the narrower claim — that the *fabric alone*
produced the improvement — is unsupported, and D-075's "at no extra cost"
sentence describes an arm that was not run.

**The trap worth naming.** The word "arm" means two different things in this
codebase, one layer apart. `ablation.ABLATION_ARMS = ("off", "on")` and
`run_arm` passes `comfort_taking=(arm == "on")`, so off/on is the
**comfort-taking** ablation *within one fabric configuration*. The fabric
change is a **different** axis, carried by two separate `out_root`s. Reading
`heldout_u31.gradient_report(root)`'s signature — which does require both an
`off/` and an `on/` directory — as a D-073 requirement conflates the two:
`gradient_report` takes one root and D-073 compares two.

**To close:** one 60-dwelling comfort-off arm per fabric configuration, frozen
membership, and a decomposition artefact. Not run here: it is not a D-073 pass
condition, and the CPU budget was shared three ways. Recorded as an open gap
rather than quietly closed.

---

## I-086 — `w3_town_network_venues.json` quotes a stale projection and a stale free-disk figure, and cites a file that disagrees with it

**Status: open. Does not change any verdict.** Found while re-issuing
`docs/E2_gate_report.md` from artefacts.

The scale block in `v1/evidence/w3_town_network_venues.json` carries a
`day6_projection` whose own `source` field reads *"v1/run_diagnostics.json,
measured on 50 homes x 365 days under C1"*. That file does not say what the
block says it says:

| figure | `w3_town_network_venues.json` `scale.day6_projection` | `v1/run_diagnostics.json` `benchmark.full_town_projection` |
| --- | --- | --- |
| `projected_run_hours` | 12.73 | **12.33** |
| `projected_run_hours_with_margin` | 19.1 | **18.5** |
| `scale_factor` | 21.84 | 21.84 — agrees |
| `projected_storage_gb` | 15.68 | 15.68 — agrees |
| `projected_storage_gb_ten_years` | 156.8 | 156.8 — agrees |

Only the run-hours pair is stale, and the storage and scale factor agree, which
is why it was not visible: the block was copied from an earlier
`run_diagnostics.json` and the two numbers that changed changed quietly. **This
is a citation that cannot be checked by following it**, which is the thing the
artefact-tracing rule exists to prevent.

**What it changes in the reading, and what it does not.** The scale verdict is
**PASS either way** — the measured 14.59 h per town-year is inside both 19.1 h
and 18.5 h, and E2-3 passes against `run_diagnostics.json`'s own 18.5 h. What
does *not* reproduce is the sentence in `scale.comparison.reading`: *"the
measured town-year is 12.47 h against a projected 12.73 h — 2% under."* Against
the current projection of 12.33 h, 12.47 h is **1.1% OVER** the bare
projection, not 2% under. The direction of the headline claim flips; its
verdict does not, because the margin is what the criterion is scored against.

**A second stale figure in the same block.** `scale.storage_reading` says *"56.5
GB against **130.4 GB** free as measured now"*. `v1/evidence/machine.json`
reports `disk_free_gb` = **116.7**. The conclusion holds — 56.5 GB fits in
116.7 GB and the 156.8 GB D18 projection still does not — but "as measured now"
is measured against a disk that has since lost 13.7 GB.

**Where it is quoted.** `docs/E2_gate_report.md` §5.1 quotes all three scale
caveats **verbatim**, which is correct — the caveats are what the artefact says
— and E2-3's own figures are read from `run_diagnostics.json` directly rather
than through the w3 block, so the report does not inherit the stale pair.

**To close:** regenerate the `scale` block against the current
`run_diagnostics.json` and `machine.json`, or have whatever writes it read both
at write time instead of copying. The same class as the stale-artefact failure
in the U31 re-run: a fresh mtime over two-day-old content.
## I-087 — MIMIC's public API permits exactly one session per participant, so a panel cannot have waves on one id (Medium, REPORT-TO-MIMIC)

**Found:** 2026-10-12, while implementing I-075's wave schedule. Found by
reading `JourneyService` before running 12,000 sessions against it, rather than
by watching a batch return HTTP 403.

**Evidence**, `web/mimic/includes/JourneyService.php`:

```php
$hasCompletedSession = $this->profiles->hasCompletedSession($participantId);
if ($mcvPosition === 'pre' && !$mcvComplete)  { ... 'mcv' ... }
if (!$hasCompletedSession)                    { ... 'decide' ... }
if ($mcvPosition === 'post' && !$mcvComplete) { ... 'mcv' ... }
return $this->pack(..., 'summary', 'summary.php?session_id=...');
```

and `web/mimic/api/session.php`:

```php
$state = $journey->state($pid);
if ($state['next'] !== 'decide') {
    JsonResponse::fail('JOURNEY', 'Complete prior steps before starting a session', 403);
}
```

Once a participant has one completed session **and** a completed MCV block,
`next` is `summary` forever, so `action=create` can never succeed again. There
is no `wave`, `round` or `reset` concept anywhere in the journey, the schema or
the repositories: `sessions` is keyed only by `participant_id`, and
`ProfileRepository::hasCompletedSession` is a boolean.

**Why it matters here.** Design WP-M2 asks for *"repeated sessions in survey
waves across the 10 simulated years, at 8 to 15 sessions each"*, and design
5.14 level 3 binds the HRSD runner to MIMIC's **public API** rather than to
direct database writes. Those two together are not satisfiable against MIMIC as
it stands: a second wave for the same person cannot be a second session on the
same participant record.

**What was done instead, and what it costs.** Each wave is a separate MIMIC
participant record, and the **person** is the unit that recurs:
`baile_nua.mimic.panel` builds one participant per (person, wave) and D26
carries `person_id` together with `simulated_session_date`, so a panel analysis
groups by person and orders by date and does see change over time. What is lost
is only the ability to follow a MIMIC *participant id* across waves — and the
counters are therefore computed over **respondents**, never over participant
rows, which is the rule the E1 report already states ("repeated sessions never
count as unique participants"). Nothing in MIMIC was modified.

**Recommendation for the MIMIC team.** Either a `wave` column on `sessions`
with `hasCompletedSession` scoped to the current wave, or an explicit
`POST /api/session.php {action:"new_wave"}` that the journey admits for a
participant whose previous session is `COMPLETED`. A longitudinal instrument
needs one of the two; the present journey is single-shot by construction, which
is reasonable for a one-off public survey and not for the panel WP-M2 describes.

**Not claimed:** that the existing one-session-per-participant journey is a
defect for MIMIC's own purpose. It is a gap against a longitudinal use, and it
is reported as a gap.

## I-088 — every year of the decade uses 2022's weather and 2022's calendar

**Status: OPEN, disclosed not fixed. The model is frozen, and this is a design
decision rather than a defect to patch.**

The decade worker hardcodes `build_realisation(2022, ...)` and
`build_calendar(2022, weather_hourly=...)`, so all ten simulated years
2022–2031 run on **one** weather realisation and **one** calendar. Agent D
found this while bounding the 1-January discontinuity and stated it more
sharply than the boundary question itself: because every year also uses the
same master seed with `sim_day=0`, the 1 January state is not merely *reset*
between years, it is **identical** in all ten.

So the decade is **ten independent years sharing identical initial conditions
and identical weather, differing only through the life course.**

**What that costs, and what it buys.** There is no inter-annual weather
variability, so a difference in annual heating demand between 2022 and 2031
cannot come from a cold winter — it can only come from ageing, moves,
retrofits, DER adoption and occupancy change. For the detection tasks this
dataset exists to support that is arguably the better experiment: the
life-course signal is not confounded by weather. It is a liability for
anything that needs realistic year-to-year variation, and for day-of-week
alignment — 2022's weekday and school-term pattern is wrong for 2031.

**How much of it is forced.** Partly. The Met Éireann station files on disk
(`sources/met_eireann/hly1075_roches_point.zip`,
`hly3904_cork_airport.zip`) carry observations through about 2026, so
**2023–2026 could each have used their own observed weather**; 2027–2031
could not, because the observations do not exist, and anything there would be
a synthetic or reused year whatever was chosen. So the reuse is unavoidable
for the second half of the decade and a choice for the first half.

**Not fixed here, and deliberately.** Changing the weather year per simulated
year is a model change under the freeze, it would invalidate the WP5 ten-year
artefact that already exists on the same basis, and it would have to answer
the harder question of what weather 2027–2031 should have — a question with a
defensible answer (a resampled or stochastically generated year, declared as
such) that is not a one-line edit. Recorded so that no reader mistakes the
decade for ten different weather years.

**Where it must be declared:** any dataset catalogue entry or delivery package
that describes the decade, beside the 1-January discontinuity bound that
Agent D recorded in
`work/town_decade/year_ordering_and_physics_boundary.json`.

## I-089 — the scale basis structurally omits writer-flush cost, and E2-3's PASS rests on it

**Status: OPEN. E2-3 currently reads PASS on a measurement that cannot contain
the cost it is missing.**

`StreamWriter.FLUSH_EVERY_DAYS` is 30. The full-town run that produced the
scale basis — 112.64 ms per home-day, 14.59 h per town-year — ran **14 days**.
Fourteen is less than thirty, so that run **paid to accumulate a write buffer
and never once paid to drain one.** A 365-day year drains twelve times.

Agent D measured the cost on the real year, from checkpoint mtimes
(`work/town_decade/cost_curve_year_2022.json`):

| window of year 2022 | s/day | implied town-year |
|---|---|---|
| days 0–15, load building | 205.4 | 20.8 h |
| days 15–25 | 257.7 | 26.1 h |
| **days 25–30, through the first flush** | **397.6** | **40.3 h** |
| days 30–38, after the flush, machine quiet | 187.7 | 19.0 h |
| days 33–38, quietest observed | 182.6 | 18.5 h |

The flush window costs about **1,050 s of excess** against roughly 185 s/day
either side. Twelve flushes is **~3.5 h per town-year that the basis could not
have measured**. Decomposing a quiet year as 18.5 h steady state + 3.5 h flush
gives **22.0 h**, against the coordinator's independently measured 22.9 h on a
contended machine — two different decompositions within 4% of each other,
which is the reason to believe the number. The per-flush excess is **n = 1**
and labelled as such.

**The gate consequence.** E2-3 "Scale benchmarks within hardware" currently
reads **PASS** on "measured 14.59 h per town-year under C2 against a projected
12.33 h bare and 18.5 h with U21's margin". A real town-year measures 19.0 h
at its quietest window and 22.0–22.9 h all in. **22.0 h exceeds the 18.5 h
margin**, so the criterion as written is not met by a figure measured over a
whole year — and the only reason it passes today is that the figure it is
scored against was taken over a window too short to contain a flush.

This is not corrected by editing the margin, which is U21's and is what makes
the criterion a criterion. It is corrected by scoring E2-3 against a
**completed town-year** rather than a 14-day extrapolation. The first year of
the decade will supply exactly that, and on the evidence so far it will fail
the criterion. Reported now so the eventual FAIL is not a surprise and is not
mistaken for a regression: the cost was always there and the measurement could
not see it.

Related: **I-086**, the same artefact's stale projection pair and free-disk
figure. The scale block has now been wrong in three ways — a stale projection,
a stale free-disk figure, and a basis that omits a structural cost — while
every individual number in it was traceable to a file. Traceability is not
sufficiency.

### I-089, amended 12 October, evening — the gate conclusion was wrong

**The flush measurement stands. The inference I drew from it does not.**

I wrote above that a real town-year is 22.0–22.9 h, that this exceeds U21's
18.5 h margin, and therefore that E2-3 would fail once scored on a completed
year. **Both figures behind that were measured while the machine was running
at roughly three times its core count**, with a MIMIC rebuild hammering MySQL,
four pytest processes and the memory manager killing tasks. The w3 scale block
makes exactly this point in the direction I failed to apply it: *"a figure
measured on a busy machine bounds the cost from ABOVE and a figure measured on
an idle one does not."* I treated an upper bound as an estimate.

Measured on the same run once the machine went quiet — load 10.6, nothing else
heavy running — over the most recent 60 simulated days, a window that
**contains two writer flushes** and is therefore flush-inclusive:

| | s/day | town-year | decade |
|---|---|---|---|
| whole run to date, mixed load | 137.8 | 14.0 h | 140 h (5.8 days) |
| **last 60 days, quiet, 2 flushes included** | **109.2** | **11.1 h** | **111 h (4.6 days)** |
| earlier contended windows | 183–398 | 18.5–40.3 h | — |

Decomposing the quiet figure: 7.8 h steady state + 3.2 h of flush
= **11.0 h per town-year**, against the 11.1 h observed. **That is inside
U21's 18.5 h margin**, and inside the 14.59 h basis as well.

**So E2-3 is not failing on cost, and I should not have predicted that it
would.** What survives is narrower and still worth having: the 14-day basis
could not contain a flush, the per-flush excess is a real 955.2 s (n=1), and
**the flush is now 29% of a quiet town-year** — a larger share of the total
than before, because the total shrank. A projection that omits it is wrong by
about a third even though the criterion is met.

The honest reading of the whole episode: the 2× spread between 11.1 h and
22.9 h on identical code is **contention**, and nothing in this project should
quote a cost figure without the machine state beside it. That is why Agent E's
D10 probe was told to run its arms back-to-back and to report the ratio rather
than the absolutes.

E2-3 will still be re-scored against the completed year rather than the 14-day
extrapolation, because that is the right evidence — but on the measurement so
far it passes.

---

## I-090 — model code was committed while both runs were in flight, so neither run's code state is recoverable

**Status: OPEN. Not fixable retrospectively; fixable for every future run in one line.**

D23 was previously recorded unwritable because the finished runs recorded no
code SHA or tree hash, and computing one now would describe the exporter's
commit. Writing D23 honestly meant establishing what *could* be recovered, and
the answer is worse than "the freeze tag".

The estate-year run ran from about **21:37 to 22:11 UTC on 2026-10-11**
(`run_diagnostics.json`'s mtime, less the run's own
`benchmark.timings.total_s` of 2,081 s). Commit `e4862f3` — "Fix I-081 (the
restore threw away the hot water cylinder)" — committed
`scripts/baile_nua/engine/run.py` at **21:54 UTC, eighteen minutes into that
run.** The 14-day town run started within about thirteen seconds of `7f81f74`,
which committed `scripts/baile_nua/activity/engine.py`.

Between each run's nearest preceding commit and `v1-engine-freeze`,
`engine/e1_run.py` and `engine/run.py` both changed. So:

* the freeze tag's tree hash is **demonstrably not** either run's code, and
  writing it into `code_tree_hash` would publish a false checksum;
* the nearest preceding commit is an **upper bound** on what is established,
  not a statement of what ran, because nothing recorded whether the working
  tree was clean.

What D23 does instead is in `export/run_manifest.py`: every field carries a
provenance class, `code_git_sha` and `code_tree_hash` carry a
`-reconstructed` suffix in the idiom of `manifest.git_sha`'s own `-dirty`,
`run_id` begins `D23-RECONSTRUCTED-`, and the row names the model-code files
that differ between the run-time commit and the tag.
`test_d23_the_claim_that_the_tag_is_not_the_runs_code_is_true` re-runs that
diff against git, so the row's own reason is checked rather than asserted.

**The fix for future runs is not new code.** `baile_nua.manifest.RunManifest`
already computes all of it and `write_t0` already accepts one; the runner does
not build one. Six fields of sixteen are captured today
(`label`, `master_seed`, `coupling_mode`, `scope`, `checkpoint_chain_head`,
`environment`); a `RunManifest.start(...)` call at run launch would make all
sixteen captured. That is an ENGINE change and is reported, not made.

---

## I-091 — the written D09 and the written D05 describe different populations

**Status: OPEN. A referential gap in the export package, surfaced by D21.**

`v1/ground_truth/D09_part000.parquet` holds 250 life events spanning
**2022-01-18 to 2031-12-05** over households `H-000848`, `H-001019`, … and
**193 persons**. `v1/ground_truth/D05_part000.parquet` holds the estate
slice's **147 persons**. The intersection of the two person sets is **empty**.

D09 as exported is the TOWN's ten-year life course, converted from the
ten-year artefact; D05, D06 and D08 are the 50-home estate slice rebuilt from
the master seed. They sit in the same release package, are keyed on the same
column name, and share not one key. Consequences:

* **every** D21 biography's "Life events recorded on or before this date" and
  "…after this date" sections read "No record covers this date" — 294 rows on
  the estate-year, 5,834 on the town;
* the Mary move-in scenario (`LE-H-000227-MARY-MOVEIN`, effective day 188),
  which the run's own diagnostics carry, is **not** in the exported D09 at
  all, so it cannot appear in any biography;
* a consumer joining D09 to D05 on `person_id` gets zero rows and no error.

Not fixed here: which population D09 should describe is a packaging decision
for the coordinator, and either answer (restrict D09 to the slice, or export
both with a scope column) changes what an already-merged exporter writes.
D21 records it in its own manifest (`d21_n_d05_persons`,
`d21_n_d09_persons`, `d21_n_persons_with_a_citable_life_event` = 0) and in
`export_limitations`, so the gap travels with the data.

---

## I-092 — the exporter imported the engine before the source registry

**Status: CLOSED in `export/context.py`.**

`RunContext.slice` opened with `from baile_nua.engine.e1_run import
build_slice` and only then evaluated `self.town`, which is what imports
`baile_nua.sources_registry`. But `engine.e1_run` imports `activity.engine`,
which evaluates `_LATEST_WORKDAY_WAKE = _latest_workday_wake()` **at module
import**, and that reads the Cobh small-area source. So importing the engine
with an unpopulated `REGISTRY` raised

    SourceError: source 'osi.small_areas_2022.cobh' is not declared in
    baile_nua.sources.REGISTRY

about a source that **is** declared, from a module-level constant, with the
real cause (the declaring module had not been imported yet) nowhere in the
message.

It never showed in a full `export_all`, because that starts at D01, which
touches `ctx.town` and imports the registry on the way. It showed the moment
an exporter that needs the slice ran first — `export_all(..., which=["D27"])`.
Fixed by importing the registry before the engine in both `slice` and
`runner`, with the reason in a comment so it is not re-ordered away.

---

## I-093 — two assumption-flag references in the merged export layer that no sweep entry names

**Status: OPEN. Pre-existing; `test_every_a_flag_in_the_tree_is_accounted_for` FAILS.**

`export/structural.py` lines 94 and 110 refer to flag `A-49` in two D01
provenance strings. `A-49` exists in `ASSUMPTION_FLAGS`, but its `where`
tuple does not name `export/structural.py`, and `uncovered_files()` keys its
exemption on `where`. So the sweep's own coverage test reports:

    these files carry an [A] flag that no sweep entry names:
    {'export/structural.py': 2}

Introduced by `a27b88e` ("Add baile_nua.export"), untouched by this branch
(`git diff master -- scripts/baile_nua/export/structural.py` is empty). The
fix is to add `"export/structural.py"` to A-49's `where` in
`validation/assumption_sweep.py`, which is model code outside this agent's
write permission. **Reported as a failure, not worked around**: the test is
doing exactly its job.

---

## I-094 — D27's three-band plan is four years out of vintage

**Status: OPEN, flagged A-97 on the dataset.**

D27's flat and day/night plans are read from Electric Ireland's Standard
Electricity Price Plan **dated 1 May 2022** — the year the estate-year run
simulates. Its three-band plan is read from the Home Electric+ Standard Smart
Tariff schedule **dated 1 November 2024**, because no three-band domestic plan
with published day/night/peak bands was on sale in May 2022: the smart-meter
rollout had not reached the point where suppliers published one, so there is
no contemporaneous schedule to fetch.

The consequence is specific and bounded, and is recorded on every row:
comparing **across** plans in this dataset mixes two price years (2024 levels
are higher), and comparing **within** a plan does not. The 2024 sheet is also
the only published band-hours source in the corpus, which is why the day/night
plan's night window is carried from it (A-92).

Retires when a published Irish domestic three-band schedule dated within the
simulated year is declared and fetched.

---

## I-095 — D21 surfaced two internal inconsistencies in D08 that no aggregate check would notice

**Status: OPEN. A model finding, found exactly as design 5.2 step 6 intended.**

D21's declared purpose is that a reader can catch an implausible synthetic life
that no aggregate check would see. Reading the first biography it wrote
(`P-000625`, Mark Reilly, as of 2022-01-01) surfaced two, both from the same
D08 row `S-P-000625-0001`:

1. **`caring_load` = `child` with `caring_hours_week` = 0.** The biography
   renders them in one sentence — "Caring load child, 0 caring hours a week" —
   and the two cannot both be true of the same person. Either the categorical
   and the quantity are drawn independently, or `child` means something other
   than "provides care to a child" and the field name is wrong.

2. **`vehicle_access` = `none` in `income_quintile` 5.** Not impossible, but
   worth checking at the joint: a top-quintile urban household with no vehicle
   access at all. The estate carries 6 EVs over 50 homes, so vehicle access is
   modelled; whether it is conditioned on income is the question.

Neither is a marginal error, so neither would appear in a SAPS marginal check,
and `caring_hours_week` has no published joint with `caring_load` to score it
against. **Not smoothed**: the narrative renders both plainly, next to each
other, which is the whole point of the dataset.
---

## I-096 — the researcher dashboard returns 504 on a waved panel, and the cause is the legacy bundle (High, REPORT-TO-MIMIC)

**Found:** 2026-10-12, by the first waved-panel run dying at
`verify.fetch_dashboard` after every batch had completed — nine hours of
inserts behind an endpoint that will not answer.

**What is measured.** All four figures are from this instance at 23,456
participant rows / 294,592 responses, the panel I-087 produces (one participant
row per wave):

| what | measured |
| --- | --- |
| `api/dashboard.php?fresh=1` over HTTP | **HTTP 504 after 600.06 s**, with a client `--max-time` of 5400 s |
| `DashboardQuery::grandMeans` | **5.0 s** |
| `DashboardBundle::compute` (the v2 bundle, via MIMIC's own `tools/build_results.php --force`) | **74.0 s** |
| `DashboardAnalytics::bundle()` (the legacy bundle) | **> 1,000 s**, abandoned at ~17 minutes |
| CPU while the legacy bundle runs | web container **100%**, MySQL **0.9%** |

**The 600 s is MIMIC's, not the caller's.** `docker/nginx/default.conf` line 25
ships `fastcgi_read_timeout 600s`, and PHP itself has no limit
(`max_execution_time = 0`). The curl above waited 5400 s and still got a 504 at
600 s, so the gateway is what gives up. The first run's
`requests.exceptions.ReadTimeout (read timeout=600)` was a coincidence of the
same number on our side, and reading it as a client-side impatience problem is
wrong — raising the client timeout alone changes nothing.

**Which part does not scale, and why `?fresh=0` does not help.** It is *not*
`grandMeans`, which is 5 s, and *not* the v2 bundle, which is 74 s. It is the
**legacy** `DashboardAnalytics::bundle()`, and `api/dashboard.php` calls it
unconditionally:

```php
if ($v2 === null) { $v2 = DashboardBundle::compute($pdo, $filters, $rawPoints); }
$legacy = (new DashboardAnalytics($pdo))->bundle();        // every request
```

So the snapshot path — `?fresh=0`, `ResultsSnapshotService::assembleV2()` —
cannot rescue the endpoint either: the snapshot replaces only the part that was
already fast. MySQL sitting at 0.9% while PHP pins a core says the work is
in-process iteration over per-participant rows rather than SQL, which is also
why it grows with participant **rows** and not with people: `grandMeans` takes a
mean of per-participant means, and I-087 makes one row per wave, so the waved
panel roughly doubled the row count for the same 1,219 people.

**What was done instead of fixing it.** The dashboard is fetched by running
MIMIC's own `api/dashboard.php` under the web container's **PHP CLI**, with
nginx out of the path (`verify.fetch_dashboard_with_transport`, transport
`auto`: HTTP first, CLI on a 504 or timeout, and which one answered is recorded
in the artefact). Only the *transport* changes — MIMIC's own endpoint, MIMIC's
own ADR-005 token check, the same `?fresh=1` bundle, nothing in the MIMIC tree
modified. T9 is untouched: the same `v2.quality.grand_mean_pi`, the same
`min_n`, the same synthetic banner, the same cell-suppression scan, the same
pass criterion. `assembleV2()` was read before choosing, to confirm the
snapshot path reproduces all seven v2 blocks and so could not have quietly
narrowed T9's small-cell scan.

The alternative was to raise `fastcgi_read_timeout` in
`docker/nginx/default.conf`. That is MIMIC's shipped configuration, and the
standing rule is to record a required MIMIC change rather than make it.

**Recommendation for the MIMIC team.** Two things, in order of value:

1. Do not compute `DashboardAnalytics::bundle()` on a request that is served
   from a snapshot — it is the only part that does not scale, and it is
   recomputed even when the rest is cached.
2. Profile it against participant count. A researcher dashboard that 504s once
   a study passes roughly twenty thousand participant rows will fail on a real
   longitudinal panel too, not only on a synthetic one; and a 504 after ten
   minutes is the worst shape of failure, because the work is done and thrown
   away.

**Not claimed:** that the dashboard is wrong, or that T9's statistic is
affected. The numbers it returns once it returns are the numbers T9 checks, and
T9's outcome in this run is reported on exactly that basis.
## I-097 — D10 declared `location_id` required, and no travelling person can satisfy it

**Status:** OPEN as a schema correction awaiting the coordinator's audit; the
corrected schema is on `agent-e`.

**What it is.** `datasets.yaml` declared `D10.location_id` as
`required: true`. D10 is the activity-interval dataset, and an interval whose
`location_kind` is `in_transit` is on the road network: there is no feature in
D01 to name, and `EstateRunner._venue_for` correctly returns `None` for it.
Measured on a two-day estate day with the WP7 venue layer loaded, the split is

| location_kind | intervals | `location_id` resolves |
|---|---|---|
| building | 3,788 | yes — the dwelling |
| venue | 373 | yes — all four venue activities resolved |
| in_transit | 690 | **no — there is no place** |

so 14.2% of intervals cannot carry a non-null place. The schema's own
validator refuses a null in a required field, so **D10 could not be written at
all** while the flag stood.

**Why it went unnoticed for so long.** Nothing wrote D10. `run_day`
materialised every interval, counted them into
`run_diagnostics.json :: n_activity_intervals`, and dropped the intervals. A
producer whose rows are never written is never validated against the schema —
which is exactly the class of latent mismatch
`tests/test_new_dataset_rows_conform.py` was written for, and D10 was not one
of the three datasets it covered.

**The three options, and why the third was taken.**

1. *Invent a place.* Stamp the dwelling, or a sentinel, on a person who is on
   the road. That is a false statement about where someone was, in a
   ground-truth dataset, and it would be invisible to every consumer.
2. *Leave D10 unwritten.* The dataset is in scope, declared `e1_in_scope`, and
   the quantity already exists in memory every simulated day.
3. *Align the flag with D11.* `D11.location_id` is the **same quantity**,
   resolved by the **same expression on the same objects**, and has always
   been `required: false` — with the same nulls, for the same reason. D10 is
   now `required: false` too, with the reason in the schema beside the field.

**What this does NOT relax.** `zone` stays required, and `in_transit` and
`out_of_model` are members of the `zone` enum, so a reader can always tell a
null place from a lost one — and
`test_d10_location_id_is_null_only_where_there_is_no_place` fails if a null
ever appears outside those two zones.

**Flagged for audit.** This is the only schema change in the D10/D17 work that
is not part of BN-1, and the coordinator should see it as a change rather than
find it.

---

## I-098 — the D17 diagnostic accumulator grew without bound to report its own length

**Status:** FIXED on `agent-e`.

`run_year` held `d17: list[dict[str, Any]]` and extended it with every row
`lv.d17_rows` produced on every C2 coupling epoch. The only use of that list,
anywhere, was

```python
"n_d17_rows": len(d17),
```

A town-year at C2 is 365 days × 96 epochs × about 123 elements (53
substations + 64 feeders + growth), so the list reached roughly **4.3 million
ten-key row dicts** — order 2 GB of Python objects — in order to report its own
length. It was then discarded.

**Why it matters beyond tidiness.** The full-town decade's binding constraint
is peak RSS, not run time: the concurrency work caps the run at one year
process because a second pushes the machine to the point of killing processes
for memory (`work/town_decade/cost_curve_year_2022.json ::
one_memory_pressure_event`). An unbounded 2 GB accumulator inside the year
process is a material part of that ceiling.

**The fix.** The rows are now handed to the writer one day at a time and the
count is a counter. `n_d17_rows` reports the same number it always did, which
is the test: the before/after comparison on a two-day estate run gives 960 in
both arms.

**A sibling that was NOT changed.** `network_epochs` accumulates one
`solve_epoch` record per epoch for the whole run — 35,040 records a town-year,
each holding two dicts of ~117 floats — and is genuinely consumed, by
`lv.loading_report`, at the end of the run. Reducing that would change what
the loading report is computed from, which is model behaviour and outside what
was approved here. Recorded so it is not re-discovered.

---

## I-099 — two reporting paths file D17's observable view under the wrong name

**Status:** one FIXED on `agent-e`, one OPEN for the coordinator.

BN-1 adds `D17_aggregate`, the first dataset id in the project with an
underscore in it. Two places split a filename on the first underscore to
recover the dataset id:

1. `StreamWriter.storage_report` used `path.name.split("_")[0]`, so
   `D17_aggregate_part000.parquet` was filed under `D17` and the view's bytes
   and rows were added to the ground-truth dataset's. **Fixed**: it now splits
   on `"_part"`, which is what `release/packages.py :: datasets_in` already
   did.
2. `release.packages.build_packages` reports
   `observable_views_of_gt_present` by testing `"D17" in obs`, where `obs` is
   keyed by the filename stem. The view is now written, and that field will
   still report `False` for it. It drives no rule — rule 1 and rule 2 both
   pass — so it is a **misleading report rather than a failing check**, and it
   is left for the coordinator because `release/` is outside the two engine
   changes that were approved.

**A third path, for the coordinator's merge list.** `DATASETS.md` is generated
from the schema's declared dataset list and from `report/datasets_md.py`'s
`PROSE` table, and both have moved: there is a thirty-second declared dataset
and a new prose entry for it. `test_the_document_on_disk_is_what_the_generator_produces`
compares the committed document against a fresh render and will fail until it
is regenerated with `python -m baile_nua.report.datasets_md`. It is NOT
regenerated on `agent-e`: the document is built from the Parquet parts under
`v1/`, which the re-run replaces, so a render taken now would describe a run
that is about to be superseded. It belongs with the re-tag.

---

## I-100 — the prepared decade root is pinned to the OLD freeze, and the drivers hardcode its digest

**Status: OPEN, blocking the decade launch. Found rebuilding state after the
terminal restart, before anything was launched.**

`work/town_decade/_frozen_root` was copied on 12 Oct at 13:18, sixteen minutes
after `v1-engine-freeze` (`fdef627`, 13:02) and before every agent merge. Its
model-code digest is `53829612…`, which is exactly the value
`RUN_STATE.json :: frozen_at` records and exactly what
`/tmp/agent_d_decade_worker.py :: EXPECT_CODE_DIGEST` and
`/tmp/agent_d_decade_aggregate.py` both hardcode. So the prepared root is
self-consistent — with the *wrong* tag.

Measured, with the worker's own `digest_of`:

| tree | code digest | .py files | conf digest |
|---|---|---|---|
| `_frozen_root` (= `fdef627`) | `53829612…` | 132 | `59518571…` |
| HEAD (= `v1-engine-freeze-2` + a docs commit) | `5072330b…` | 147 | `e0ab1c83…` |

`engine/run.py`, `engine/stream_writer.py` and `engine/e1_run.py` all differ.
Launched as prepared, the decade would have run **freeze-1 code and written no
D10, no D17 and no D17_aggregate** — the three datasets the freeze was lifted
to add. The worker would then have refused anything else, because it re-checks
the digest at start.

**Why the digest moves by more than the engine.** `digest_of` covers every
`*.py` under `scripts/baile_nua`, so the 15 files the agent merges added under
`export/`, `mimic/`, `report/` and `sources_registry.py` move it too. That is
the digest working as designed and is not a model change:
`git diff fdef627..HEAD` touches **nothing** under `lifecourse/`,
`population/`, `weather/` or `activity/`, and `run_year`'s signature is
byte-identical between the two trees. So the life-course hash
(`EXPECT_LIFE_COURSE_HASH`) should still reproduce, and agent-e's neutrality
evidence already showed every pre-existing Parquet byte-identical and one
checkpoint chain head across all four probe arms.

**The fix.** Rebuild `_frozen_root` from HEAD and reissue the drivers with the
two new digest constants. Nothing is in flight, so I-080's "never edit a
driver that is running" is not engaged; the reissued drivers are written as
new files rather than edits to the mode-400 originals, which are kept for the
record. The 290 simulated days under `year_2022/` stay archived and are not
resumed: they were written by freeze-1 code and carry no D10 or D17.

---

## I-101 — a non-worker now wakes only 27 minutes later than a worker, and the test needs 30

**Status: OPEN. A real behavioural regression, and NOT from today's merges.**

`test_sleep_timing.py::test_a_non_worker_wakes_later_without_going_to_bed_later`
asserts `median(wake | non-worker) > median(wake | worker) + 30`. Measured:
**470.0 against 443.0**, so the gap is 27 minutes and it fails by three.

**When it broke.** It PASSED in the 11 Oct baseline (`v1/evidence/junit.xml`,
751 tests). It fails on HEAD. It also **fails on the freeze-1 tree** — run
directly against `work/town_decade/_frozen_root/scripts`, same assertion, same
numbers, 37.2 s — so it was already broken when the engine was frozen on
12 Oct at 13:02, before the first agent merge. `git diff fdef627..HEAD` leaves
`activity/` and `population/` untouched, which agrees.

The window is therefore `5e36a25` (the baseline's nearest preceding commit) to
`fdef627`: the week-3 work that added `population/venues.py` (+691),
`population/econ_by_age.py` (+298), `activity/engine.py` (+103) and
`population/synthesise.py` (+74). `econ_by_age` changes who counts as a worker
and `venues` changes where non-workers go, so either could move a wake-time
median; the test file itself is unchanged.

Not fixed here, because the brief's rule for this pass is to fix only
regressions caused by today's merges and log the rest. **It must not be closed
by widening the 30-minute margin** — the margin is the claim.

---

## I-102 — a FOURTH path that did not know D17_aggregate exists, and two reasons the freeze made false

**Status: the dispatch half FIXED; the absence half OPEN until the re-run lands.**

I-099 named three paths that split or mis-filed the project's first
underscored dataset id. There is a fourth, and it was a hard failure rather
than a misleading report.

**Fixed.** `export/dispatch.py` enumerated the declared datasets as
`tuple(f"D{i:02d}" for i in range(1, 32))` — 31 ids — while BN-1 had taken
`schema/datasets.yaml` to 32. `test_every_declared_dataset_is_accounted_for`
asserts the two agree and failed with `31 == 32`. `ALL_DATASETS` now carries
`D17_aggregate` in schema declaration order, and `WRITTEN_BY_THE_ENGINE`
carries it too, which is correct: `stream_writer.py:448` writes it. The list
stays hardcoded rather than read from the schema, because deriving it would
make the test tautological — catching exactly this drift is what it is for.
`test_export_dataset_schemas.py` + `test_schema.py`: **106 passed, 44 skipped,
0 failed.** The two new skips read "the RUN did not stream it" and name the
storage report, which is the truth: `v1/run_diagnostics.json` lists
`['D11','D13','D16','D18','D19']`.

**Open.** `export/absent.py` still classifies D10 and D17 as ABSENT, and their
recorded reasons are now factually wrong — D10's says "NEEDS: an ENGINE
change: carry the intervals on DayResult and buffer them in StreamWriter, then
re-run. Both are inside the freeze", and D17's says "NEEDS: a re-run that
writes d17_rows per epoch (an ENGINE change: StreamWriter has no D17
buffer)". Both of those engine changes were made and are what
`v1-engine-freeze-2` IS. The reasons are not wrong about the *current* `v1/`,
which predates them, which is why they still read correctly today and why
this is not fixed yet. The moment the estate-year is re-run under freeze-2,
D10 and D17 become present, `export_all` would record a present dataset as
absent, and they must move from ABSENT into `WRITTEN_BY_THE_ENGINE`. Deferred
to the re-run deliberately, so the reasons change in the same step as the
facts they describe.

---

## I-103 — the I-091 relocation is a manual file move that any re-export silently undoes

**Status: OPEN. Found by hitting it during the freeze-2 rebuild; the relocation
has been restored by hand a second time.**

`040e9de` settled I-091 as "a packaging decision": D03, D09 and D20 as exported
are the WP5 decade's rows — a 60-home `u23_mixed_age` slice at seed 20251010 —
and they were sitting beside the estate-year's 50-home, seed-20261008 D05/D06/D08
while sharing **no person at all** with them. The commit message says the fix
plainly: *"Moved to `v1/ground_truth/wp5_decade/`"*.

Moved. Not re-plumbed. `export/absent.py` detects the relocation by scanning the
filesystem, and `report/datasets_md.py` was taught to scan one level of run
subdirectories — but `export/dispatch.py` still lists D03, D09 and D20 in
`EXPORTERS` and still writes them to `<out_root>/ground_truth/`. So the
relocation survives only as long as nobody re-runs the export.

**Measured on this rebuild.** `python -m baile_nua.export v1 v1` recreated all
three at the top level. They came back byte-identical to the relocated copies —
`D03` 45 rows `c4ce049ee97f`, `D09` 250 rows `a118455c4068`, `D20` 253 rows
`933ae0dc34ea`, the same SHA-256 prefix as `wp5_decade/` in each case — and the
new top-level D09 shares **0 of 147** persons with the estate-year's D05. That
is I-091 exactly as first reported, reintroduced by a command whose own record
says `n_failed: 0`.

The six files were moved to `work/i091_toplevel_removed_20261013-163651`, never
deleted, and `wp5_decade/` is intact. Verified absent from the top level
afterwards.

**Why it is not fixed here.** The honest fix is for the export layer to write a
dataset into the package of the run whose rows it describes — i.e. for
`export_all` to take the relocation seriously rather than leave it to the
filesystem — and that is a change to `dispatch.py`'s contract, not a one-line
guard. Writing it under time pressure during a rebuild is how the relocation got
lost in the first place. Until then: **after every `python -m baile_nua.export`
against `v1/`, check whether D03, D09 or D20 reappeared at the top level.**
A regression test belongs with the fix — asserting the three are absent from
`v1/ground_truth/` top level while present under `wp5_decade/`.

---

## I-104 — the catalogue says a dataset is present and, two lines later, that it is not on disk

**Status: OPEN. Pre-existing, exposed by I-091 and now by D17. In the shipping
document.**

`DATASETS.md` carries this sentence on five dataset pages:

> **Schema** — not available: the dataset is not on disk in `v1/`. It is **present**.

and above it a facts table reading `Path | not present in v1/`, `Rows | —`,
`Size | —`, `Time span | —`, beside `Status | **present**` and a correct
`Present for | town14 (157,248 rows, 5.2 MB)`.

**The cause is an asymmetry between two scans in `report/datasets_md.py`.**

* `_run_presence` (line 1063) scans `[(ESTATE_RUN, base)] + [every immediate
  subdirectory]`, so it finds datasets filed under the run they describe. Its
  own comment records why it was written that way: *"a scan of only the top
  level reported D03, D09 and D20 as missing the moment they were moved into
  the run they actually describe (I-091) — the data had not gone anywhere, the
  scan had stopped looking."*
* The `DiskFacts` builder (line 1284) globs `(v1 / sub).glob(f"{ds}_part*.parquet")`
  for the three packages and **never descends into the run subdirectories**.

So 040e9de fixed the contents table and the counts and left the per-dataset
facts block on the old scan. Status comes from the fixed path; Path, Rows, Size,
Time span, Schema and Sample come from the unfixed one.

**Measured.** 3 occurrences before this rebuild (D03, D09, D20 — exactly the
I-091 relocations), 5 after it (D17 and D17_aggregate, now filed under town14).
Every affected dataset is one that exists ONLY under a run subdirectory. No
top-level dataset is affected, which is why it survived review.

**The fix** is to give the facts builder the same fallback: when no part is
found at a package's top level, scan that package's run subdirectories, keeping
top-level priority so the estate-year still wins where a dataset is in both.
`DiskFacts.package_dir` would then need to carry `"<package>/<run>"` rather than
a bare package name, and every reader of that field has to be checked first —
it feeds the Path row and may feed links. Not made here: this is the shipping
catalogue, the rebuild it was found in was already long, and an unchecked edit
to the generator is how the I-091 relocation got lost (I-103).

**It is a reporting defect, not a data defect.** The rows are on disk, the
counts and per-run presence are right, and the schema is declared in
`schema/datasets.yaml`. What is wrong is one document's description of itself.

---

## I-105 — the simulation grid is UTC and the tariff bands are local clock, so day/night rates are an hour out for half of every year

**Status: OPEN. A live defect in the CURRENT model, not something the replay
introduces. Logged on instruction (playbook v2, D10).**

`engine/run.py:67` sets `MINUTES_PER_DAY = 1440` and
`engine/stream_writer.py:195` builds every day's index as
`date_range(date, periods=MINUTES_PER_DAY, freq="1min", tz="UTC")`. Every
per-minute array in the engine is allocated at 1440 and the grid is UTC.

`export/tariffs.py:344` declares the opposite basis for the rates:

    BAND_CLOCK = "Europe/Dublin local clock, as the published price schedule
                  states it"

Both statements are correct about themselves and they do not agree. Ireland is
UTC+1 from the last Sunday in March to the last Sunday in October, so for
roughly seven months of every simulated year a tariff band that the published
schedule places at 23:00–08:00 local is applied at 23:00–08:00 UTC, which is
00:00–09:00 local. **The night rate starts an hour late and ends an hour late.**

**This affects artefacts already published.** The estate-year is a full
calendar year, so it spans both DST states; D27's band definitions and any
cost or ToU figure derived from them carry the offset for the summer half. No
claim has been made from those figures that I know of, but the offset is there.

Two further consequences, neither currently represented:

* a person's schedule is in UTC minutes, so a 07:00 wake is 07:00 UTC — which
  is 08:00 local in summer and 07:00 local in winter. Behaviour drifts an hour
  against the wall clock seasonally.
* `CalendarDay` carries `is_dst` and `dst_transition`, and D14 emits a `DST`
  event kind, so the transition is **reported** — but the grid never shortens
  or lengthens. There is no 23-hour or 25-hour day anywhere in the model.

**The fix** is the one the brief already names: a UTC simulation, schedules on
the local clock, exports carrying local time alongside UTC. It is Phase 3 of
playbook v2 and is sized at 5 days with high risk, because `MINUTES_PER_DAY`
backs every per-minute array, the 15-minute epoch barrier and the checkpoint
chain.

---

## I-106 — the town has far too few old people, and the deficit worsens with age

**Status: OPEN. A second population defect, independent of I-069. Logged on
instruction (playbook v2, finding 1).**

Measured at **t0 (2022-01-01)** from `D05.birth_date`, against the SAP2022
`age_by_sex` marginal for the town's **own** small areas, so this is not an
artefact of back-projection:

| band | SAP2022 share | town share | expected | actual | deficit |
|---|---|---|---|---|---|
| 0–44 | 60.0% | 63.7% | 1,751 | 1,857 | +106 |
| 45–64 | 26.8% | 27.0% | 780 | 787 | +7 |
| 65–74 | 7.6% | 6.7% | 222 | 196 | −26 |
| 75–84 | 4.4% | 2.3% | 130 | 67 | **−63 (−48%)** |
| 85+ | 1.2% | 0.3% | 34 | 10 | **−24 (−71%)** |

65+ overall: **13.2% in the census against 9.4% in the town**, 273 people where
386 are expected — a 29% shortfall. Cobh's small areas hold 14,148 people and
the town slice holds 2,917, so this is a ~21% sample and the shares should
match.

**The deficit worsens monotonically with age**, which is the signature of a
draw that is truncated or under-dispersed at the top of the distribution rather
than of a uniform sampling error. It is not the same fault as I-069: that one is
economic status drawn without age conditioning; this one is the age
distribution itself.

**Two consequences beyond the obvious.**

1. **It biases every age-graded quantity downward** — mortality, chronic
   conditions, retirement-related occupancy, heating demand from people at home
   all day.
2. **It blocks the COVID excess-death arithmetic.** The town-scale expectation
   of ~1 death was computed on this population. With a census-correct structure
   the 85+ band goes from 10 to about 34 and 75+ from 77 to about 164, which
   raises the expectation roughly 2.5 to 3 times. The conclusion that a
   single town cannot show COVID mortality still holds — it becomes a Poisson
   mean of about 3 rather than 1 — but **the number must be recomputed after
   this is fixed, not before.**

Joins I-069 in playbook v2 Phase 1, and Phase 1's exit gate requires the age
structure to be within a declared tolerance of SAP2022 **in every band
including 85+**.

---

## I-107 — the BNIT 3D map has dwelling positions and D01 has none

**Status: OPEN, not scheduled. Recorded so the gap is known. Logged on
instruction (playbook v2, D5).**

Every one of D01's 206 features is `POINT EMPTY`: 89 venues, 64 feeders, 53
transformers, and **zero parcels and zero streets**. `export/structural.py`
states the policy and the reason:

> The model has venues, feeders and transformers. It has no parcels, no streets
> and no farms, and no coordinate for anything but a small-area centroid, so
> `geometry_wkt` follows … a declared `POINT EMPTY` carrying the small area or
> estate it belongs to — rather than a fabricated polygon that would read as
> surveyed geometry.

That is a good decision and this issue does not propose reversing it. But the
BNIT 3D map **does** hold dwelling positions, so the same town has coordinates
in one system and none in the other, with no key relating them.

**What a future alignment project should do:** export the map's positions keyed
to **D01 feature ids and D02 `building_id`**, so the geometry arrives as a
declared external overlay with its own provenance rather than as fabricated
polygons inside D01. That keeps `structural.py`'s rule intact — the coordinates
would be sourced from the map, not invented by the exporter — while making
distance, density and site-area claims possible for the first time.

Until then, anything needing area or density is out of scope: playbook v2
keeps Abbeylands abstract (a count and a handover date) for exactly this
reason, and the ~8–10 ha site, the 15% open-space rule and a reserved-space map
cannot be represented.

---

## I-108 — storm days are derived from wind alone, so Storm Emma is invisible

**Status: OPEN. Found while spot-checking the weather export for the town
viewer (Phase 0). Fix scheduled for Phase 2.**

`engine/calendar.storm_days_from_weather` derives a storm day from the **wind**
in the weather realisation. That design is deliberate and the reasoning is
good — `test_storms_come_from_the_weather_and_not_from_a_draw` exists so that
"no storm exists without the wind that caused it", and the alternative was an
independent draw that would put an outage on a calm day. The defect is not the
coupling. It is that **wind is the only hazard it recognises.**

**Measured on the Cork Airport hourly record (`hly3904`, on disk), for the three
named storms the replay must contain:**

| storm | date | max wind | rank among the year's 8,760 hours | temperature | precipitation |
|---|---|---|---|---|---|
| **Ophelia** | 16 Oct 2017 | **43.0 kt** | **1st** | 9.1 to 15.3 °C | 7.7 mm |
| **Éowyn** | 24 Jan 2025 | **37.0 kt** | **1st** | 0.0 to 11.1 °C | 6.0 mm |
| **Emma** | 2 Mar 2018 | 16.0 kt | **912th** | **−2.2 to −0.5 °C all day** | **27.0 mm** |

Ophelia and Éowyn are each the single windiest hour of their year, so a
wind threshold finds them. **Emma ranks 912th on wind and would not be detected
at all** — yet it is a full day below freezing with 27 mm of precipitation,
which is to say a heavy snow event. Emma closed schools and roads across
Ireland; in load terms it is one of the most significant days in the window.

A wind-only definition therefore misses an entire hazard class: cold, snow and
ice. That matters more for a 2015–2026 replay than it did for a single 2022
year, because the window contains the February–March 2018 cold spell as well as
the two major windstorms.

**The fix, for Phase 2: a multi-hazard storm-day definition.** A day is a storm
day if **any** of these holds:

1. **wind** — mean wind or gust above a threshold (what exists today);
2. **snow or ice** — sustained sub-zero air temperature with meaningful
   precipitation;
3. **freezing precipitation** — precipitation with temperature at or below
   freezing.

Each branch keeps the existing property that the hazard is **derived from the
weather that caused it**, so no storm is drawn independently and the
outage-follows-storm invariant is unaffected.

**Validation, and it must be against the real list:** Met Éireann's named
storms 2015–2026, plus Emma specifically. A definition that finds Ophelia and
Éowyn but not Emma has not passed. Thresholds are to be **sourced** — Met
Éireann's own warning criteria are published — rather than tuned until the
named list comes out right, which would be fitting the definition to the answer.

**What this does NOT change.** The wind branch and its test stay as they are;
this adds branches rather than replacing one. And the storm **register** is
still not needed to make a storm *appear* — only to label its warning status,
which remains a separate acquisition.

---

## I-109 — the 2022 school calendar has five days that were not school days

**Status: OPEN, fix implemented in Phase 2. Found while sourcing school terms
from the DoE circulars.**

`SCHOOL_TERMS_2022` was hand-built and carries two errors against DoE circular
**0005/2020**, whose Appendix A states the 2021/22 dates verbatim:

| break | circular says | `SCHOOL_TERMS_2022` implies | error |
|---|---|---|---|
| Christmas 2021 | "All schools will re-open on **Thursday 6th January 2022**" | term resumes 5 Jan | **1 extra school day** |
| Easter 2022 | "All schools will re-open on **Monday 25th April 2022**" | term resumes 19 Apr | **4 extra school days** (19–22 Apr) |

So five days in 2022 are marked `is_school_day=True` when every school in the
country was closed. Those days feed `activity.engine`, so the error reaches
presence, occupancy and load for school-age people and anyone whose day depends
on them.

A third difference is a **declared** simplification rather than an error: the
module says "Primary and post-primary differ by a few days at the edges; the
common pattern is used and the simplification is declared". In fact the
February mid-term differs by **sector and by three days** — primary closes the
Thursday and Friday only, post-primary the whole week — and the single table
used the post-primary pattern for both.

**The fix** is Phase 2's: `build_calendar` now reads the circular-sourced
`sources/derived/school_breaks.csv`, with primary and post-primary kept
separate, for every year 2014–2026 including 2022.

**Consequence, stated rather than discovered:** every 2022 artefact built on the
old table has five wrong school days in it. The correction changes 2022
simulated output, so suite assertions anchored to those artefacts may move.
That is a sourced correction, not a regression, and any movement is classified
in the Phase 2 report rather than absorbed.

## I-110 — `is_dst` was inverted for Ireland, and the transition labels were swapped

**Status: FIXED in Phase 2. Pre-existing — `git diff` confirms the logic was
unchanged from the original `build_calendar`.**

`calendar.py` derived summer time as `bool(t.dst().total_seconds())` after
converting to `Europe/Dublin`, with the comment "derived from the zone rather
than hard-coded, so it is right for any year". The zone is right; the predicate
is not.

**For Ireland, `dst()` is non-zero in WINTER.** Since the Standard Time
(Amendment) Act 1971, **Irish Standard Time (UTC+1) is the standard**, and
winter GMT is modelled in the IANA database as a **negative** DST adjustment.
Measured:

| date | local | `dst()` |
|---|---|---|
| 2016-03-27 | 00:00 +00:00 | **True** |
| 2016-03-28 | 01:00 +01:00 | **False** |
| 2016-10-30 | 01:00 +01:00 | **False** |
| 2016-10-31 | 00:00 +00:00 | **True** |

So `is_dst` was True all winter and False all summer, and because the label
read `"spring forward" if dst[i] else "fall back"`, **the two transitions were
labelled as each other**: 2016-03-28 came out "fall back" and 2016-10-31
"spring forward".

A second, smaller error rode along: evaluating at **midnight UTC** put each
transition a day late. The spring change happens at 01:00 UTC, so at 00:00 UTC
on the Sunday it has not happened yet and the difference only appears on the
Monday.

**The fix.** Summer time is now decided by the **UTC offset** — `+1 h` is
summer, `0 h` is winter — evaluated at **12:00 UTC** so the change lands on the
Sunday it occurs on. Verified against the published Irish transition dates for
six years, 2015, 2016, 2020, 2022, 2025 and 2026: **all twelve dates correct**,
and 2022 reports 217 summer days (27 March to 30 October), which is right.

**What it affected.** `CalendarDay.is_dst` and `dst_transition`, and the D14
`DST` event kind built from them. Every artefact that reported a DST transition
date reported the wrong one. It does **not** change simulated load, because the
grid is UTC and nothing branched on `is_dst` in the physics — which is also why
it survived: the field was published but never acted on. That is the same shape
as I-105, and the two should be fixed together in Phase 3.

## I-111 — D15 computes `is_dst` by a second route that is still inverted, so the fix for I-110 only reached half the artefacts

**Status: open, output-affecting, present in the running replay.**

I-110 fixed `CalendarDay.is_dst` and closed with "what it affected:
`CalendarDay.is_dst` and `dst_transition`, and the D14 `DST` event kind". That
accounting was incomplete. D15's `is_dst` column is not taken from the
calendar at all — `weather/site.py:234` derives it independently:

```python
site["is_dst"] = (local.map(lambda t: bool(t.dst().total_seconds()))).values
```

`tzdata` models Europe/Dublin the way Irish law describes it, with IST as the
standard offset and a **negative** one-hour correction in winter. So
`t.dst()` is `-1 h` in January — and `bool(-3600.0)` is `True`. The column is
therefore `True` in winter and `False` in summer: exactly the inversion I-110
was raised to fix, reached by a different road.

**Measured, not inferred.** Against the shipped v1 package:

| artefact | January mean | July mean | rows |
|---|---|---|---|
| `v1/ground_truth/D15_part000.parquet` | **1.0** | **0.0** | 525,600 |
| `v1/ground_truth/town14/D15_part000.parquet` | **1.0** | (no July rows) | 20,160 |

and against `pandas 2.3.3` / current `tzdata` directly: 2022-01-15 gives
`utcoffset 0:00, dst() -1 day 23:00:00` → `True`; 2022-07-15 gives
`utcoffset 1:00, dst() 0:00` → `False`. Same for 2015.

**The real defect is the disagreement.** One could argue the winter reading is
faithful to the 1971 Act — winter is the period carrying a DST correction. But
two datasets cannot publish the same flag name with opposite meanings and leave
the consumer to guess. I-110 already settled the project's convention on the
plain-language one, `is_dst` true in summer, so D15 is the side that is wrong.

**Blast radius.** The column itself, and nothing downstream: `is_dst` has no
consumer in the engine — `grep` finds only the definition in `calendar.py`, the
two lines in `weather/site.py` that build it, and the column list in
`export/structural.py`. No physics branches on it, which is why it survived a
full suite twice. Simulated load is unaffected.

**Why it matters anyway.** D15 is a shipped observable, `is_dst` is a
`required: true` column, and the replay is writing it wrong **right now** —
the Dec-2014 warm-up and all of 2015 carry the inversion.

**The fix is cheap and does not cost a re-run.** D15 is derived from the
station index and the realisation alone; it carries no simulation state. So
the column can be corrected at source and D15 regenerated for already-finished
segments as a post-pass, without re-simulating a single day. Use the same test
as I-110: UTC offset at noon, `+1 h` is summer.

## I-112 — the replay's own ETA divides by the absolute `sim_day`, so it reports the run as twice as fast as it is, and the error grows every year

**Status: open, reporting only — no effect on simulated output.**

`replay_supervisor.run_segment`'s progress callback computes

```python
el = time.time() - t0                      # elapsed in THIS segment
state["s_per_day"] = el / max(int(m.group(1)), 1)   # absolute sim_day
```

`t0` is the start of the current segment, but `m.group(1)` is the engine's
**absolute** `sim_day`, which in a chained replay counts every day of every
prior year. So the numerator is the segment's elapsed time and the denominator
is the whole run's day count. The quotient is not a rate of anything.

**Measured.** 28 checkpoints in the 2015 segment, `sim_day` 31 to 58, spanning
43.2 minutes of file mtimes: **96.1 s/day**. `PROGRESS.md` was reporting
60 s/day and a 72.0 h run.

The understatement scales with the offset, so it gets worse as the run
proceeds:

| segment | offset | understated by |
|---|---|---|
| 2015 | 31 | 2.15x |
| 2026 | 4049 | ~15.8x |

**What it cost.** Every downstream date was wrong in the same direction —
optimistic. Recomputed at the measured rate, the 2018 segment completes
**16 Oct 12:47**, not the 17 Oct the schedule assumed, which moved the D18
era-gating deadline 27 hours earlier; and the 2015 package lands **15 Oct
07:32** rather than 16 Oct. Both were briefed to agents on the wrong dates and
corrected. The whole run finishes ~19 Oct 16:20, **113.8 h** remaining rather
than 72 h.

**The fix** is to subtract the offset in the denominator, as the line
immediately above it already does for `day_in_seg`, and to prefer a rate
measured over the last N days rather than since the segment's start so a
restored segment's restore cost does not flatten the estimate:

```python
in_seg = int(m.group(1)) - seg["sim_day_offset"]
state["s_per_day"] = el / max(in_seg, 1)
```

Not applied to the running process: the supervisor holds this code in memory
and the figure is cosmetic. It goes in at the next restart, with the launchd
move.

## I-113 — the 18 GB memory gate is only evaluated once every 30 simulated days

**Status: open, accepted for this run, documented so it is not mistaken for a
continuous guard.**

The gate

```python
if rss > cfg["rss_gate_mb"]: raise MemoryError(...)
```

lives inside `run_segment`'s progress callback, and the engine calls that
callback from only one place in the day loop:

```python
if day.sim_day % 30 == 29 or day.sim_day == calendar[-1].sim_day:
    say(f"  day {day.sim_day + 1}/{len(calendar)} ...")
```

So the gate is checked roughly every 30 days — about 48 minutes at the measured
96.1 s/day — and not between those points.

**It is coarse, not blind.** The figure it reads is
`resource.getrusage(...).ru_maxrss`, a high-water mark, so a spike between two
checks is still visible at the next one. Nothing is missed; detection is just
late, by up to 48 minutes, and by then the memory has already been used. The
gate's real function is therefore to stop a *second* excursion, not to prevent
the first.

**Why it is being left alone.** The cost of a late trip is one segment, and
every day has a verified checkpoint, so the restore is cheap. Making it
continuous means either a sampling thread or a callback on every day, and
adding either to a running 114-hour process is a worse risk than the one it
removes.

**Side effect worth knowing.** The same 30-day cadence is why
`status/LAST.txt` sat at `2015 day 0/365` for the first 45 minutes of the
segment: with 2015's offset of 31, the first `sim_day % 30 == 29` falls at
`sim_day` 59, which is day 29 of the segment. A stale `LAST.txt` early in a
segment is expected, not a sign of a stalled run — check the checkpoint count
instead, which advances every day.

## I-114 — the public-holiday table had no manifest, and the decision that closed it said otherwise

**Status: fixed 2026-10-15.**

`sources/derived/irish_public_holidays_2014_2026.csv` is read by
`engine/calendar.py`'s `sourced_holidays()`, which raises
`CalendarSourceMissing` rather than defaulting if the file is absent — so it is
load-bearing for every day of the twelve-year replay. It had **no manifest
beside it**: the only file in `sources/` cited by code without one. Its sibling
`school_breaks.csv` has a full one.

**D-127 asserted the opposite.** It closed this item with "Written to
`sources/derived/irish_public_holidays_2015_2026.csv` with its derivation and
verification recorded in the manifest." Two things were wrong with that
sentence: no manifest was ever written, and the filename is not the file's. The
table was later extended backwards to 2014 to cover the Dec-2014 warm-up and
D-127 was never updated, so the decision log pointed at a path that does not
exist.

**How it was caught.** Not by a test — nothing tests for the existence of a
manifest. Agent C's provenance pass resolved every cited source against
`sources/**/*.manifest.json` and this was the single cell that came back
UNSOURCED out of 32 datasets. That is the whole value of making provenance
machine-checked instead of narrated.

**The fix.** The manifest now exists, recording: derivation from
`wrc.public_holidays` with that file's own sha256; 122 rows, 4,061 bytes,
sha256 `98b8be93…`; coverage 2014-2026; the licence inherited from the WRC page
(re-use terms not stated, TO CONFIRM before redistribution); and D-127's three
verification anchors.

**Re-verified rather than restated**, because a manifest that merely repeats a
claim is what produced this issue:

| check | result |
|---|---|
| Easter Mondays | 13 rows, **all** fall on a Monday |
| October Bank Holiday | 13 rows, **all** the last Monday in October |
| Good Friday | **absent**, which is correct - it is not a public holiday in Ireland |
| per-year counts | 9 for 2014-2021, 10 for 2022-2026 |

The count step is real and is now documented in the manifest instead of looking
like a parsing fault: **2022** carries the one-off public holiday of 18 March
2022, named in the data as one-off so it cannot be read as recurring; and
**St Brigid's Day** begins in 2023, on the first Monday in February unless
1 February is a Friday. 2026-02-01 is a Sunday, so 2026-02-02 is right.

**Still open, and not this issue's to close:** the WRC page states no re-use
terms. The licence is carried as "TO CONFIRM before redistribution" on both the
WRC manifest and this derived one. It matters only if the table is redistributed
outside the project.

## I-115 — D23 reported a hardcoded freeze tag, so eleven of twelve years would have claimed an engine they were not run on

**Status: fixed on `integration-2.3`, lands at the boundary restart.**

The instruction was to record both engine versions per year in D23. Nothing
implemented it, and nothing failed — which is the point. `export/run_manifest.py`
held

```python
FREEZE_TAG = "v1-engine-freeze"
...
"d23_freeze_tag": FREEZE_TAG,
```

so every D23 row in every year would have reported the same constant. For a
single-year run that is merely stale; for a twelve-year chained replay it is
false eleven times over. 2015 runs on **freeze-2.2**; the later years run on
whatever the supervisor was last restarted with; and the D18 era gating turns on
at the **2019** boundary, which is a behavioural difference D23 is exactly the
place to record.

**Why `DONE.json` could not carry it.** The obvious fix — read the segment's
sentinel — cannot work, and the ordering is the reason: `export_all` runs at
`replay_supervisor.py:440` and `DONE.json` is written at `:489`. D23 is built
*by* that export, so at the moment it needs the engine tag the sentinel does not
exist. Hence a sidecar written **before** the export.

**The fallback is labelled.** `engine_identity()` returns
`d23_engine_version_source`, which either says "recorded by the run
(ENGINE.json)" or says in words that the value is this module's constant and
"not a statement about this run". A version that was inferred must never be
readable as one that was recorded — that confusion is the whole defect, and
silently defaulting to the constant would have reproduced it in a new place.
A truncated sidecar also falls back rather than raising: a ten-hour year's
export should not be lost to a malformed 200-byte file.

**Guarded against regression by asserting on the source.** One of the six new
tests reads `replay_supervisor.py` and asserts the sidecar write appears before
`export_all` and before the sentinel. If a future edit reorders them, D23
quietly reverts to the constant and **no other test fails** — so the ordering,
not just the behaviour, is pinned.

Found while checking the agents' claims rather than by any test: agent A
reported the per-year engine recording as handled, and `git diff` showed no
branch touches `run_manifest.py` at all.

## I-119 — the twelve-year replay runs every year on the 2022 census population, so 2015 contains dwellings built in 2019 and 2024

**Status: open. Raised as P-7; not a disk problem, a modelling one.**

Found while trying to put a population-growth factor into the disk projection.
There is none, and the reason is the finding.

`synthesise_t0(*, master_seed, method)` takes **no year and no as-of date**, and
`population/synthesise.py:44` pins `T0 = pd.Timestamp("2022-01-01T00:00:00Z")`.
Every `valid_from` in the synthesised population is that constant —
`synthesise.py:317`, `:348`, `:499`, `buildings.py:172`, `venues.py:110`.
Nothing filters the dwelling stock by the simulated year.

**Observed, not inferred:** every segment the replay has run reports the same
figures — Dec 2014, 2015, and the pre-restart 2015 attempt all log
`town: 1092 homes, 2917 people` and `slice: 1092 homes, 2917 people`.

**What that means for the deliverable.** The 2015 simulation is populated with
the 2022 dwelling stock. Cluain Ard completes in **2019** and Belgard in
**2024** (D-112), and Abbeylands is phased to 2027 — so in the 2015 output,
every one of those homes exists, is occupied, and draws load eleven years and
nine years early. The same applies to every year before each estate's
completion. It contradicts the playbook's own design, which has the BNIT map's
year slider read `valid_from` / `valid_to` from D01/D02 precisely so that "the
map and the data never disagree".

**What it does not mean.** The physics, the weather, the calendar and the
behaviour are all correct for their year; the sourced inputs are all correct.
This is a question of *which homes exist when*, not of whether the simulation
of them is right. And the town total is right for 2022, which is the census the
population was built from.

**Cost of fixing it.** The honest fix filters the slice by `valid_from`/
`valid_to` against each segment's dates, which changes the home count per year
and therefore every engine-streamed dataset for every year before 2026 — i.e.
it invalidates the run so far and requires starting again. That is a decision
about what the deliverable is for, not a bug to patch mid-flight, which is why
it is in PENDING rather than being acted on.
## I-116 — the memory gate compares a monotone high-water mark against a live budget, so it fires once and then always

**Status: fixed on `integration-2.3`. The RUNNING process still has the old
gate — see P-5 in `status/PENDING_DECISIONS.md`.**

```python
rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6
state["peak_rss_mb"] = round(rss, 1)
if rss > cfg["rss_gate_mb"]:
    raise MemoryError(...)
```

`ru_maxrss` is the largest resident set the process has **ever** held. It never
falls. So the gate does not ask "is this run using too much memory now" but
"has this run ever briefly used too much" — and once the answer is yes it stays
yes for the life of the process, including every retry of the segment.

**Measured on the live run, which is what makes this concrete:**

| | |
|---|---|
| peak reported at day 60 | 7,566 MB |
| peak reported at day 90 | **11,938 MB** |
| **current RSS at the same moment** | **0.47 GB** |
| gate | 18,432 MB |

The process is using half a gigabyte and the gate thinks it is using twelve.
The spikes coincide with the 30-day flush and export, and they are growing at
about **146 MB/day** between those two reports, which extrapolates to the gate
tripping at **day ~135 of 365**.

**What tripping would cost.** `MemoryError` aborts the segment; the supervisor
renames the partial aside and retries, three times, each time restarting 2015
from the warm-up checkpoint and running ~2.8 h to hit the same wall — roughly
**8 h** burned before `status/BLOCKED.md` is finally written.

**The fix.** Gate on **current** RSS, read from `ps` (macOS has no `/proc` and
`psutil` is not installed). A failing `ps` returns `0.0` and therefore cannot
trip the gate: losing the guard for one cycle is recoverable, aborting a
ten-hour segment because `ps` hiccuped is not. The peak is still measured and
reported — it is the only record of what the run actually demanded, and I-113
depends on it to catch a spike between two 30-day checks.

**Settled at 02:42: the growth was NOT linear and the trip is not coming.**
The day-120 report came in at **11,938 MB — identical to day 90**.

| report | peak RSS |
|---|---|
| day 60 | 7,566 MB |
| day 90 | 11,938 MB |
| day 120 | **11,938 MB, unchanged** |

The peak has plateaued at 65% of the gate. The day-90 figure was the
high-water mark of the first flush, which also carried the 1.15M D11 presence
rows restored by D-141; nothing since has approached it. So the 146 MB/day
"growth rate" was an artefact of measuring across exactly the two reports that
straddled the largest single spike of the run.

**The fix stands anyway**, because the defect is real and independent of
whether it would have fired here: a gate that compares a monotone high-water
mark against a live budget is wrong in principle, and the next run with a
genuinely larger spike would hit it. But it is not urgent, and it rides in at
the planned boundary restart rather than justifying an unplanned one.

**The method is the point.** A two-point extrapolation said "trips at day 135,
restart now, lose three hours of 2015". A third point twenty minutes later
showed the premise was false. Two points cannot distinguish linear growth from
a one-off spike followed by a plateau, and nothing about the first two readings
revealed which it was.

## I-117 — the step-wise RSS growth: 96 power-flow dicts a day kept for a year, to compute five numbers

**Status: fixed, goes in under 2.3 with the byte-identical proof.**

This is the cause of the growth that took the gate to 88% (P-5).

`e1_run` solves one power flow per 15-minute epoch — **96 a day**, confirmed by
town14's own `n_epochs_solved: 1344` over 14 days — and appended every result
dict to `network_epochs`, which is never cleared. At the end of the segment
that list is used for exactly two things: `lv.loading_report(network_epochs)`
and `len(network_epochs)`.

**`loading_report` reads five fields.** Confirmed by reading it: `converged`,
`max_trafo_loading_pct`, `max_feeder_loading_pct`, `max_line_loading_pct`,
`vm_pu_min`, plus the list's length. The retained dict also carried
`feeder_head_loading_pct` — one entry per feeder, 64 of them — and
`trafo_loading_pct`, one per substation, 53. **Neither is ever read.**

**Measured, not estimated**, at the live run's own shapes (64 feeders, 53
substations):

| | bytes | one year, 35,040 epochs | whole replay, 411,936 epochs |
|---|---|---|---|
| full dict | 10,809 | 0.35 GB | **4.15 GB** |
| reduced to what is read | **832 (8%)** | 0.027 GB | 0.319 GB |

`feeder_head_loading_pct` is 4,744 B and `trafo_loading_pct` 4,205 B — together
**83%** of every dict, retained for the life of the process to be ignored.

**Why it compounds, and why the growth looked step-wise.** Every segment runs
in the **same process**: `run_year` is called in-process, there is no
subprocess per year, so `ru_maxrss` **never resets at a year boundary**. The
cost therefore accumulates monotonically across all twelve years rather than
starting fresh each January. And the growth appears in steps because CPython
returns freed arenas to the OS only in whole arenas — a steadily growing list
of small dicts enlarges the heap in jumps, which is exactly the flat-then-jump
pattern observed (+297 MB, then +3,335 MB, then flat for 60 simulated days).
Three separate attempts to fit a slope to that pattern were wrong, in both
directions, because the underlying process is not linear.

**This is I-091 again, four lines away from where I-091 was fixed.** That issue
reads: "Accumulating them for the whole run was a latent memory cost that
bought nothing: a town-year at C2 is 365 x 96 epochs x about 123 elements, so
the discarded list reached roughly four million row dicts in order to report
its own length." The D17 accumulation was found; the `network_epochs`
accumulation immediately beside it was not.

**The fix.** A converged epoch is reduced to the five fields plus `sim_day` and
`epoch`. A **non-converged** epoch keeps its full dict: those are rare, they
are the only ones worth diagnosing, and `loading_report` counts them against
the week-3 criterion.

**Proven output-neutral, which is the only thing that makes it acceptable:**
`loading_report(full) == loading_report(reduced)` over 288 epochs including two
deliberate non-convergences. A memory saving that changes a reported number is
not a saving. One of the six tests derives the read-set from
`loading_report`'s source, so adding a field there fails here first.

**The other per-day accumulators were checked and are not a problem:**
`feeder_profile` is 365 arrays of 96 floats (~280 kB) and is genuinely needed —
it is concatenated into the profile. `passport_effects` and `occupancy_effects`
are event-driven and town14 recorded **0** of each over 14 days.

## I-118 — the memory gate was 56% of a machine with 32 GB, and the metric was the real error

**Status: documented; the gate value is unchanged and now correct.**

The Mac has **32 GB** of physical RAM (`hw.memsize` 34,359,738,368) and 12
cores. The 18,432 MB gate is **56% of total RAM**, which sounds aggressive and
is not the problem. The problem was I-116: the gate compared `ru_maxrss`, a
monotone high-water mark that never resets across the twelve years, against
that budget — so it measured "has this run ever briefly peaked" and would
eventually fire on history alone.

**With the gate on current RSS (I-116), 18,432 MB is the right value and needs
no change.** It is an abort gate, not a target: the replay's genuine working
set has been observed between 0.47 GB and 5.9 GB, and with I-117 removing up to
4.15 GB of accumulation it should sit lower still. 18 GB is high enough never
to fire in normal operation and low enough to catch a runaway before the
machine thrashes.

Recommended addition, not yet made: a **warning** threshold around 8 GB that is
logged and not fatal, so growth of the I-117 kind is visible in
`progress.log` long before it is dangerous. Tonight the only signal that
anything was accumulating was the gate figure itself creeping toward its own
limit.
