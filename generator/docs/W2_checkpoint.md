# Week 2 checkpoint — Baile Nua / HRSD_Occupants

**Date:** 10 October 2026 · **Design reference:** r4 (adopted 10 Oct 2026;
architecture frozen at r3) · **Next gate:** E2, end of week 3

> **UNVALIDATED SIMULATION EVIDENCE.** Everything in this document is
> engineering verification and plausibility checking against published
> references. No behavioural validity is claimed anywhere. Where a number is
> compared against a source, the source is named and hashed; where there is no
> source, the assumption is flagged `[A]` with the search that failed to find
> one.

---

## 1. What week 2 was for

r4 §9.3 row 2 sets the week's scope and §9.4 its acceptance:

| Step | Work |
| --- | --- |
| 1 | U27 plausibility suite |
| 2 | U23 mixed-age slice |
| 3 | U25 hot water, gas cooking, boiler losses · U22 comfort-taking |
| 4 | WP4 behaviour depth with ablations · S08 mobility/EV |
| 5 | WP5 ten-year life course, Mary scenario, D20 labels |
| 6 | WP6 calendar and events |
| 7 | C2 coupling and the 8.2 timing contract |
| 8 | Intervention replay by forking |
| 9 | G-C generator modes and the T6 null control (5.14) |

**Acceptance (r4 §9.4):** *"Ablations degrade fit as expected; 10-year
invariants clean; every D20 label observable at its tier; coupling-lag test
(1-min vs 15-min epochs) within tolerance."*

| Criterion | Result |
| --- | --- |
| Ablations degrade fit as expected | **4 of 4 arms** degrade as predicted |
| 10-year invariants clean | **10 checks, 0 failures** |
| Every D20 label observable at its tier | **Yes, and the tier is derived rather than declared** |
| Coupling-lag test within tolerance | **Passes at all three binding regimes**, after the test found two real defects |

All four met. Each is expanded below, with what was found rather than only
what passed.

**Test suite at the end of the week: 635 passed, 1 skipped, 0 failed**
(18 min). That includes the E1 release self-check and the E1 report tests, so
the week's work has not disturbed the gate E1 passed — the E1 estate is kept
unchanged as a regression fixture precisely so that this is checkable rather
than assumed.

Steps 5 to 9 added **seven test files carrying 193 tests**, and the suite went
from 439 to 635 over the same period. The files are named for what they guard
rather than for the module they cover: `test_lifecourse_tenyear`,
`test_sources_provenance`, `test_calendar_events`, `test_coupling_contract`,
`test_fork_replay`, `test_gc_modes_and_t6`, `test_new_dataset_rows_conform`.

Step 5 carried two further acceptance items beyond r4's four — that births,
deaths and moves fall inside the vital-statistics CIs, and that the
plausibility suite runs on every year. The suite ran on all ten years. Births
and deaths are inside their published intervals and so is partnering. **Moves
cannot meet that criterion as stated**, because no vital-statistics source
publishes a gross move rate — EP006 publishes net migration only. §3 sets out
what is reported instead and why it is a weaker claim.

---

## 2. The week's sourcing work

The declared source registry went from **28 entries at the start of week 2 to
55**, so **27 were added**, and three more were fetched and then **rejected**.
Every calibration number traces to a file in `sources/` with a SHA-256 (D24),
and every remaining assumption carries the search that failed to find a source
(I-040).

### Sources adopted

| Subsystem | Source | What it anchors |
| --- | --- | --- |
| WP5 births | VSA104 | age-specific fertility by NUTS 3 region (South-West) |
| WP5 births | VSA36 | parity shares within an age band |
| WP5 deaths | VSA08 ÷ PEA01 | deaths over population on the **same** age-band dimension code |
| WP5 partnering | VSA49 | marriages per 1,000 by single year of age |
| WP5 employment | JCA01 | job churn by single year of age and sex |
| WP5 vacancy | VAC17, VAC04, F2095 | gross vacancy flows, Cork County rate, ED-level rate |
| WP5 migration | EP006 | net migration per 1,000, Cork |
| WP5 DER | HEBEU37 | installations in place, by type |
| WP5 health | HSPAE122 | chronic-condition prevalence at 50+ |
| WP5 bounds | CD565, EA036 | the stocks two `[A]` hazards must stay consistent with |
| WP6 cruise days | TBA10, TBA11 | Port of Cork calls and passengers; month-of-arrival seasonality |
| WP6 school terms | SCA42 | the chronic-absence floor under a daily absence rate |
| C2 margin | ESB Networks LP1 | the maximum quarter-hour ramp, 0.256 of mean |

### Sources fetched and rejected

Rejecting a fetched source is a finding, so each is recorded rather than
quietly dropped:

| Source | Why rejected |
| --- | --- |
| **CEPHA05** | the only life table PxStat publishes, and its last year is **1990** — it cannot age a 2022 population, and the error is not small |
| **C0674** | the **2006** census vintage; VAC04 and F2095 supersede it. The registry entry had mislabelled it as 2022 |
| **UA16** | "enrolments by week" turned out to be **15 irregular snapshot dates** across several years, not an attendance series, so it cannot be differenced into a term calendar |

---

## 3. Step 5 — WP5 ten-year life course, 2022–2031

Design 5.3 lists the ten-year life course and gives **no hazard for any of
it**. Sweep flag A-25 owned that gap and named this step.

### Hazards: nine sourced quantities, five `[A]`

Six are rates, one is a net rate and two are prevalences. A prevalence is not
a hazard: where the published quantity is a stock or a prevalence, the annual
rate is `[A]` and the published number constrains what ten years of it may add
up to — a weaker claim than a sourced rate, and labelled as one.

| Hazard | Form | Source |
| --- | --- | --- |
| birth | rate | VSA104 age-specific fertility, South-West; VSA36 parity split |
| death | rate | VSA08 ÷ PEA01, same year and same age-band code |
| partnering | rate | VSA49, single year of age and sex |
| employment change | rate | JCA01 separations ÷ employees, single year of age and sex |
| vacancy equilibrium | rate | VAC04 Cork County |
| vacancy flows | rate | VAC17 — the only vacancy table that is a **flow** |
| net migration | net rate | EP006 Cork |
| DER / retrofit | prevalence | HEBEU37 (a cumulative bound, not a rate) |
| health state 50+ | prevalence | HSPAE122 (a stock the onset builds to) |

`[A]`, each with a search record and a published bound: **A-25b** gross
household turnover (EP006 publishes net only; bounded by VAC17's flows, which
balance at 0.965), **A-25c** union dissolution (CD565 is a stock; 11.9% at
45–54), **A-25d** children leaving home (EA036 is one age in two years),
**A-25e** health onset under 50 (HSPAE122 starts at 50), **A-25f** annual
retrofit adoption (**zero** PxStat tables for "retrofit").

The searches that returned nothing are recorded as carefully as the ones that
found something, because "not published" and "I did not try the right words"
are different claims. The sharpest example: **`sport` matches 115 tables and
not one is a fixture list** — they are road freight *transport* tables, where
"sport" is a substring. A hit count is not evidence.

### D20 labels: the tier is derived, not declared

The schema defines `detectable_from_tier` as "the lowest tier at which it is
theoretically observable". That is a claim about sensor channels, and
`TIER_DEVICES` says which channels each tier has — so the tier is **computed**
from the channels a label's text appeals to, and the acceptance test
re-derives it. A label claiming something its tier cannot see fails; so does
one pitched higher than it needs to be, because "lowest" is part of the
contract.

The evidence that this is the rule the design meant, rather than one invented
to make the module pass, is that it reproduces **all four** of design 5.9's
hand-written Mary tiers — T1, T2, T1, T3 — which were written before any of
this existed.

All four tiers are exercised: T1 (occupancy changes, PV export, a heat pump's
cold-day load), T2 (fabric decay, smart controls, a health state's held
setpoint), T3 (a sleeping zone falling out of use), T4 (a battery's state of
charge).

### Acceptance

| Criterion | Result |
| --- | --- |
| 10-year invariants clean | **10 checks, 0 failures** |
| Every D20 label observable at its stated tier | yes, re-derived over every label in the run |
| Births and deaths within the vital-statistics CIs | **yes** — and partnering too, which is also published |
| Moves within the vital-statistics CIs | **cannot be met as stated.** See below |
| Plausibility suite run on every year | **yes** — all ten, 0 FAIL, 0 NO_DATA. §9 |

Births, deaths and partnerings are compared against the **published** rate at
the exposure this run actually had, with a two-sided 95% interval — a model
producing too *few* births fails exactly as one producing too many does.

Across **eight seeds**: **23 of the 24 sourced event-seed cells** fall inside
(deaths 8/8, births 8/8, partnering 7/8), and the assumed move rate 8/8. One
cell outside 24 at a 95% interval is what those intervals should give, so the
single partnering miss is the expected tail rather than a finding — and it is
reported rather than dropped, because a run in which *nothing* ever fell
outside a 95% interval would mean the intervals were not 95% ones.

**Moves are the exception, and it is a sourcing limit rather than a result.**
The acceptance criterion asks for moves inside the vital-statistics CIs, and
**no vital-statistics source publishes a gross move rate.** EP006 publishes
*net* migration per 1,000, which constrains the difference between the two
gross flows and neither of them: a net rate of +0.6 per 1,000 (Cork,
2011–2016) is consistent with any pair of gross flows differing by that much,
including zero and zero. Searching `internal migration` returns one table, a
projection; `household formation` returns none.

So the move rate is `[A]` (A-25b), and what is reported for it is an interval
around the **assumed** rate at this run's own exposure — observed 34 against an
expected 37.3, interval [25.3, 49.2]. That tests internal consistency, not
agreement with a source, and the row is labelled `sourced: false` in the
artefact so it cannot be read as the former. What *does* constrain the assumed
rate externally is VAC17's gross vacancy flows, whose two directions balance at
0.965 — which is why the vacancy stock stays flat across the ten years rather
than drifting with the assumption.

Stating this plainly rather than reporting "moves within CI": the number is
inside its interval, but the interval is not a vital-statistics one, and
presenting it as though it were would be the more comfortable of the two
available errors.

### What step 5 found

Four real defects, fixed rather than absorbed:

1. **I-053 — two vital-statistics sources declared under crossed matrices.**
   `births_by_age_of_mother` pointed at VSA09, which publishes **deaths**;
   `deaths_by_age_sex` pointed at VSA17, which publishes **births**. Neither
   carried an age dimension at all. It survived a week because *nothing had
   ever opened the files* — A-25 scheduled their first use for this step. A
   declared source that nothing consumes is an unverified claim. There is now
   a guard comparing every JSON-stat source's own label against the declared
   title, with a threshold measured from the corpus (real minimum 0.40; the
   I-053 cases 0.00) and a test asserting it still fails on the historical
   error.

2. **A parity reweighting that silently lost 12% of the births.** Multiplying
   each woman's rate by a VSA36 parity share rescaled every rate downwards:
   10.15 integrated against an exposure expectation of 11.52. From outside
   that is indistinguishable from a model missing its target, and no
   vital-statistics interval would have caught it — 10.15 sat comfortably
   inside the CI. Caught by recording the hazard integrated **at draw time**
   and comparing it against the exposure expectation, which is now a permanent
   check because the bug class is invisible without it.

3. **A passport version chain assigned in iteration order and checked in date
   order**, so two measures landing on one building in one year made it jump
   backwards. A passport whose versions do not follow its dates cannot
   reconstruct the building.

4. **Households kept occupying a dwelling after their last member died.** A
   vacant home is a real state, so the runner now holds it at frost protection
   rather than failing on `people[0]`.

### What step 5 deferred, and said so

**I-054.** Fabric retrofit and extension produce their D03 passport events and
D20 labels, but I-048 defers the fabric work to week 3 and the standing
instruction is no fabric tuning now — so the RC parameters are not touched.
In a week-2 package a detector scored against a `retrofit_fabric` label would
score a false negative through no fault of its own, for **8 fabric retrofits
and 10 extensions**. Suppressing the labels instead would make the ten-year
building history wrong in order to make a week-2 package self-consistent. The
deferral is in the run diagnostics and asserted by a test, so week 3 has to
come back and flip it.

---

## 4. Step 6 — WP6 calendar and events

E1 implemented four event classes and named the rest in
`OUT_OF_SCOPE_AT_E1`. WP6 closes that list: **all ten D14 event kinds** are
now generated.

R20's acceptance test is an event coverage audit — *every listed class present
with a source*. That is two claims, and the audit keeps them apart, because a
class can look covered because rows exist for it while nothing backs the rate
they were drawn from:

| | kinds |
| --- | --- |
| **Sourced** (3) | cruise day (TBA10/TBA11), school-term attendance (SCA42), storm (the weather realisation itself) |
| **Legal instrument** (2) | public holidays (Organisation of Working Time Act 1997), DST (Directive 2000/84/EC, **computed** from the rule rather than transcribed) |
| **`[A]` with a search record** (6) | outage (A-42), festival, market, sport, roadworks (A-43), school-term *dates* (A-41) |

Eleven entries for ten kinds, because **school term appears twice**: its
attendance is bounded by SCA42 and its *dates* are not published as data at
all. That is the split the audit is for — a class is not "covered" or
"uncovered" but covered in some respects and assumed in others, and reporting
one number would hide which. 274 D14 rows in the 2022 calendar.

Cobh is a cruise port, so the event class that most distinguishes this town
from a generic Irish one is the one with a real source: **81 Port of Cork
calls in 2022 landing 115,062 passengers** — about 1,420 per call into a town
of 3,000 — with TBA11's month-of-arrival seasonality (nothing November to
February, 24% in August).

### Shared drivers, enforced rather than asserted

Design 5.10 says compound correlation comes from shared drivers, and K09 says
a pairwise matrix over ten kinds is not validatable — so validation is by
class and by driver, which only works if the driver is in the data. Every
event names its driver and `driver_audit` refuses one claiming a driver that
does not generate it.

| Driver | Generates | Enforced by |
| --- | --- | --- |
| `winter_storm` | storm, outage, sport | outages occur **only** on storm days; storms cancel fixtures |
| `cruise_call` | cruise day, market, festival | markets and festivals occur **only** on cruise calls, inheriting TBA11's seasonality |
| `institutional_year` | school term, holiday, roadworks | roadworks are scheduled into the term gaps |
| `clock_change` | DST | computed from the directive |

An outage drawn independently of the weather would put the lights out on a
calm day, and a model that had learned the real storm–outage correlation would
then be penalised for being right.

**86% of multi-kind days are driver-explained** and 5 are genuine chance
overlaps. State kinds (school term, roadworks) are excluded from the
coincidence count — a six-week term overlapping a fixture is a Saturday, not a
coincidence, and counting it buried the five that meant something.

---

## 5. Step 7 — C2 coupling and the 8.2 timing contract

All six steps of design 8.2's interval order are implemented: a
staleness-stamped state from solve k−1, logged actions, a local safety layer
checking device power, SoC, the occupant temperature band and the minimum EV
departure charge against a conservative envelope, devices stepping on accepted
actions only, a solve on realised net load, and violations recorded as events
with the envelope tightening.

The **staleness margin is derived from a published source**: LP1's largest
change between adjacent quarter-hours, **0.256 of its mean**, at 07:15 on 7
March — the morning rise. A margin measured from our own output would have the
model certifying itself, and the contract's guarantee would be circular. It is
an after-diversity ramp, so it is a *lower* bound on what one dwelling needs,
and the test is written knowing that.

### The coupling-lag test found two real defects

**The envelope was not a network envelope.** Built from per-connection
headroom only — a literal reading of the contract's wording — twenty homes
each inside their own 12 kW service limit collectively overloaded a 40 kW
feeder. C1 then extracted **1,213 kWh against C2's 908 while causing the
violations**, because a 15-minute commitment is made before a 15-minute-old
solve can reveal the overload. That is precisely the gain from stale
information 8.2 says is impossible, and it appears *only* when the binding
element is upstream — a test at a single operating point would have certified
a broken contract. The envelope now takes the minimum of the connection's
headroom and its share of the upstream element's.

**The tightening rate was per epoch.** C2's 1440 epochs a day tightened up to
fifteen times as hard as C1's 96 for the same physical violations, so the two
modes differed by epoch counting rather than by staleness — the confound that
makes a coupling-lag test meaningless. Both rates are now per unit of time.

### After the fixes

| Regime | C1 accepted | C2 accepted | rel. diff | violations | C1 peak | C2 peak |
| --- | --- | --- | --- | --- | --- | --- |
| connection-binding | 2,428 kWh | 2,810 kWh | 0.1358 | 0 | 179.4 kW | 236.0 kW |
| feeder-binding (40 kW) | 370 kWh | 429 kWh | 0.1370 | 0 | **30.6 kW** | **39.4 kW** |
| tight feeder (25 kW) | 216 kWh | 251 kWh | 0.1378 | 0 | 19.5 kW | 24.6 kW |
| baseline exceeds the limit (3 kW) | 2.4 kWh | 2.9 kWh | 0.1778 | 70 / 1036 rows | 6.47 kW | 6.47 kW |

All four pass. The connection-binding regime's feeder limit is set effectively
unbounded (10⁵ kW) so that the *connection* envelope is what binds, which is
why its peaks exceed the others' — they are not against a constraint.

Relative difference **0.136 to 0.178** against a bound of **0.2431**, and the
bound is
derived twice: the two staleness margins come from LP1's measured ramp, and
the bound itself is the envelope's own arithmetic — with the envelope equal to
headroom × (1 − margin), the implied relative difference in accepted energy is
exactly (m₁ − m₂)/(1 − m₂). A first version compared the energy difference
against the C1 margin (0.256) directly; both are dimensionless but they are
fractions of different quantities, so that was loose by 5%. The realised
difference sits below the bound because the device and SoC limits also bind.

C2 always accepts **more** than C1 — no gain from staleness — and the mechanism
is visible in the peaks: C1's larger margin holds the feeder to 30.6 kW where
C2 reaches 39.4 kW under the same 40 kW limit. Fresher information buys more
usable flexibility, safely, which is the contract's whole point.

**Violations are counted, never corrected.** The last row of the table is a
feeder limit the baseline *alone* exceeds, so the controller cannot prevent the
overload. Both modes record it — 1050 and 1036 violation-**minutes**, agreeing
to within one epoch — at an identical **6.47 kW** peak, and throttle the
controller to 2.4 and 2.9 kWh, near zero. Minutes rather than rows, because the
same quarter-hour overload is one row at C1 and fifteen at C2: comparing row
counts would compare epoch granularity, not severity.

**What is not claimed.** The step-5 solve is still the feeder aggregation E1
used. Design 9.3 moves `pandapower` and the full network to week 3, and 8.2
marks C2 mandatory for network-sensitive research — so this step delivers the
*timing contract* and makes no voltage, loading or constraint claim.
`TIMING_CONTRACT_CLAIM` travels with the output saying so.

---

## 6. Step 8 — intervention replay by forking

Design 8.2's three replays have three different guarantees, and the rule that
matters most is the easiest to read past: *the replay API refuses to present an
isolated single-household replay as a town-wide counterfactual. Any
intervention forces a town fork.*

That refusal is the substance. A single-household fork is cheap and tempting
and would be wrong in a way that does not announce itself: the home's own load
would respond correctly while the feeder, the venue occupancy, the later
events and the neighbours' prices stayed at baseline — so the estimate would
miss exactly the coupled effect the intervention was interesting for.
`counterfactual()` raises rather than returning a number with a caveat. It
also refuses forks from different parent states, a baseline that carries an
intervention, and a treated fork that carries none.

**Common random numbers.** The counter-based tree keys every draw on (seed,
stream, entity, day, draw) and holds no state, so the same coordinate yields
the same number in any fork *for free*. The useful question is therefore not
whether the numbers are common but whether the same **coordinates** are
visited. `crn_audit` measures that: an entity the intervention does not touch
must stay paired, and one that decouples anyway is a finding, because every
paired statistic over it compares two different random sequences while
reporting the variance of one.

In the recorded run, a tariff intervention declared as touching two of twenty
households: **18 paired, 2 decoupled**, the decoupled pair exactly the two
named, and 40 of 42 draw coordinates shared (CRN share 0.952). No entity
decoupled that the intervention log had not declared, and no undeclared stream
changed its draw count — so the audit comes back clean.

Paired and unpaired entities are reported separately, never pooled: pooling a
low-variance paired estimate with a high-variance unpaired one and quoting the
paired variance is how a counterfactual comes to overstate its precision.

**The counterfactual figures in the artefact are a mechanism demonstration,
not an estimated effect.** The outcomes fed to it are synthetic (a flat −200
per household), which is why the paired standard deviation is exactly zero.
What is being shown is that the paired statistic uses only the paired
entities, that the two decoupled households are reported apart from them, and
that the refusals fire — not what a tariff does to a town. No intervention has
been run through the engine end to end yet, and the design's own guarantee for
this replay is *deterministic given the fork point and the intervention log*,
which is what is tested, rather than any claim about effect size.

---

## 7. Step 9 — G-C generator modes and the T6 null control

K17 is the risk this answers: *"Circularity: MIMIC is tested on data generated
with its own assumptions, so passing proves little."*

All five design 5.14 G-C modes are implemented, each declaring **in advance**
which assumption it breaks and what the right answer is — and the right answer
is often not "pass". Design 5.14 separates a **software defect** (wrong result
where the method should work) from a **recognised limitation** (correct
implementation failing where the method can't work). A mode coming out PASS
where a limitation was declared is itself a finding: an estimator that recovers
non-identifiable parameters is recovering its own prior.

| Mode | Breaks | Expected | Observed |
| --- | --- | --- | --- |
| wrong assumptions | MIMIC's weighted additive utility | limitation | limitation |
| non-identifiable | separately estimable trait effects | limitation | limitation |
| continuous, no clusters | a segmentation reflecting latent classes | pass | pass |
| causally unrelated | predictive association ⇒ causal value | pass | pass |
| differential non-response | responders representing the population | limitation | limitation |
| *(T6 linked arm)* | — | pass | pass |

### T6 and its null control

At the recorded master seed (20251010), with n = 2000:

| Arm | CV R² baseline | CV R² full | Incremental | Min. detectable | Verdict |
| --- | --- | --- | --- | --- | --- |
| linked (effect planted) | 0.4412 | 0.5539 | **+0.1127** | 0.0039 | effect found, 29× the floor |
| **null** (effect exactly zero) | 0.6346 | 0.6336 | **−0.0011** | 0.0039 | no predictive value, as required |

The null's increment is *negative*: out of sample a column with no causal
effect makes the fit slightly worse, which is what makes the null falsifiable
rather than true by construction.

The statistic is **cross-validated** because in sample, adding any column can
only raise R² — an in-sample test would find predictive value in pure noise
and the null would pass by construction. A test demonstrates exactly that on
the null cohort.

The null's confounder is deliberately **observed**, sitting inside the
demographics and opportunity the baseline model gets. With a hidden confounder
stated willingness would legitimately carry information about revealed
behaviour, and a correct method using it would be marked defective — so a null
built on a hidden confounder would be a trap rather than a test. Stated and
revealed still correlate at r > 0.4 in the null cohort: the association is
real and the causal effect is zero, which is the difficulty being tested.

Design 5.14's own caveat travels with the result: *T6 is internal consistency
only. Linked-panel predictive validity shows that MIMIC can recover the link
HRSD planted, not that the link exists in people.*

### Three criteria that were wrong before they were right

Each was corrected by the data, not by argument, and each is now a test:

1. The non-identifiable mode used **r = 0.97** while claiming the coefficients
   were unrecoverable "at any sample size". False: variance inflation there is
   only ≈17, so with n = 2000 the standard errors come back near **0.054** and
   the coefficients are perfectly estimable. Correlation is not collinearity
   sufficient to destroy identification. r is now 0.9995, inflation ≈1000.
2. That mode's acceptance criterion then went through a fixed standard-error
   threshold and half the coefficient gap before arriving at the textbook
   statement: under collinearity **prediction is identified and coefficient
   inference is not**. At the recorded seed: error correlation **−0.9995**;
   SE **0.014** on the sum against **0.901** on the difference, a ratio of
   **64**; and cross-validated R² of 0.4371 with both latents against the true
   predictor's 0.4373 — prediction is untouched while the contrast is
   unrecoverable.
3. The cluster mode compared a silhouette against a declared **0.25**. The
   data refused it: k-means on one correlated Gaussian scores around **0.33**,
   because splitting any blob in two gives a respectable silhouette. A raw
   silhouette is not calibrated against a null. It now compares against the
   same statistic on Gaussian data with the data's own covariance — observed
   **0.336** against a reference of **0.327 ± 0.010**, a gap of **+0.88 SD**,
   far below the 3.0 acceptance threshold. The observed value sits *above* the
   reference mean and is still correctly rejected, which is exactly what a
   declared cut-off at 0.25 could never have done.

Three negative controls (NC-GC-01 to 03), power-analysed and auto-discovered
by pytest. **NC-GC-02 is the r = 0.97 episode turned into a permanent test.**
NC-GC-03's polarity was inverted twice and the harness reported
`NOT_DETECTED` both times, correctly — a positive control does not fit a
negative-control harness, and the harness was right where the control was
wrong.

---

## 8. Steps 1–4, in brief

Completed earlier in the week and recorded in `PROGRESS.md` and `DECISIONS.md`
at the time; summarised here because the week's acceptance rests partly on
them.

**Step 1 — U27 plausibility suite.** Twelve checks against published Irish
references where they exist. `KNOWN_PLAUSIBILITY_FAILURES` is now **empty**,
and the register is two-sided: a new failure breaks the suite, and a listed
failure that starts *passing* also breaks it, so an entry cannot outlive the
defect it describes.

**Step 2 — U23 mixed-age slice** (and U29's resize to 60 homes). Measured at
the ten-year run's seed:

| Slice | Homes | Mean build year | Pre-1980 | BER range |
| --- | --- | --- | --- | --- |
| E1 estate | 50 | 2004.3 | 2.0% | A1–G |
| U23 mixed-age | 60 | **1953.0** | **90.0%** | A1–G |

(An earlier draft said 1962 and 84%; those were the slice at 50 homes, before
U29's resize. The resize was to *add headroom above E0-7's people band*, and
it also moved the age composition, which is worth noting because every
fabric-sensitive number in step 3 is measured on this slice.)

The E1 estate is kept unchanged as a regression fixture, so every E1 artefact
reproduces byte-identically — the suite confirms that.

**Step 3 — U25 and U22.** Hot water from draw events tied to simulated
activities rather than DEAP's floor-area route, so the model *can* disagree
with the reference; gas cooking split three ways from HEBEU34/HEBEU106; boiler
losses from DEAP Table 4b indexed by **boiler** age, not dwelling age
(I-047).

There are **two different gas ratios** in this project and an earlier draft of
this checkpoint ran them together. Both are given, with what each measures:

**PL-GAS-01 — mean simulated *space heat* over its DBERNG01 cell.** Below 1 by
construction, because space heat is 60–80% of an Irish gas bill; the check's
band is [0.25, 1.00] and U25's acceptance test was that the ratio *rises*.

| Package | PL-GAS-01 | PL-ELEC-01 | artefact |
| --- | --- | --- | --- |
| E1 estate before step 3 | 0.308 | 0.694 | `plausibility_e1.json` |
| E1 estate now | 0.331 | 0.693 | `plausibility.json` |
| 60-home mixed-age slice, 2022 | **0.983** | 0.629 | `wp5_2022.json` |

**Gas at the meter over published gas** — space heat *plus* hot water, gas
cooking and boiler losses, against a reference of **1.0**. This is the complete
bill against a published complete bill, and it is the metric I-048's diagnosis
rests on:

| Arm | at-meter ratio | artefact |
| --- | --- | --- |
| comfort-taking off | 1.632 | `ablation_u22.json` `strength_sweep[0]` |
| **declared strength** | **1.446** | `strength_sweep[1]` |
| ×2 | 1.294 | `strength_sweep[2]` |
| ×3 | 1.227 | `strength_sweep[3]` |
| 60-home slice, step 4 baseline | **1.4417** | `behaviour_ablation_w2s4.json` `fits.full` |

So on the mixed-age slice the model **over-consumes at the meter by 44%**
against DBERNG01, and three terms at three times their amplitude take that only
to 1.227.

**One figure in I-048 has no artefact behind it.** The issue reports the E1
estate's at-meter ratio as 0.785 — under-consuming on modern stock — and that
is the other half of the 1.84× divergence its retrofit hypothesis rests on.
`0.785` appears nowhere in `v1/evidence/`. The corresponding at-meter
measurement on the E1 estate is therefore **re-measured as the first act of the
week 3 fabric work**, because a hypothesis should not rest on a number that
cannot be traced.
Comfort-taking is three COM-B terms with different drivers, not one amplitude,
and its falsifiable consequence is that the *same fabric* produces different
behaviour by means — and that the sign flips with the fabric. Computed from
the model at a specific heat loss of 6.0 W/K/m² (a leaky dwelling; the town
spans 0.63 to 6.49, median 2.08) and at 0.8 W/K/m² (an efficient one):

| Household | Leaky dwelling | Efficient dwelling |
| --- | --- | --- |
| quintile 1, local-authority rented | **−1.95 K**, 64% of heating hours, 32% of the sleeping zone | **+0.28 K** |
| quintile 5, owner-occupied | **−0.24 K**, 96% of hours, 92% of the zone | **+1.25 K** |

Prebound is a *cost* response, so the poor household in the leaky home retreats
and the well-off one barely does; rebound is an *opportunity* response, so in
the efficient home the well-off household takes four times as much of the
saving as warmth. **No fabric correction can produce that pattern**, which is
what makes the mechanism falsifiable rather than a knob.

The strength is **not fitted** to DBERNG01. The artefact records the spread at
107.8% without the mechanism, 75.2% at the declared strength and 45.1% at three
times it, against a published 4 to 7% — so the mechanism saturates far short of
the target and a fitted strength would buy only the appearance of calibration
while costing a kelvin of indoor temperature.

**Step 4 — behaviour depth with ablations.** Four arms, each with its expected
direction declared **before** the run: **4 of 4 degrade as predicted**, none
improved, none without effect.

One *metric within* a passing arm moved the wrong way, and it was recorded
rather than rewritten. Ungating heating on occupancy was declared to degrade
both the gas ratio and the load factor. It degraded the gas ratio as predicted
(1.4417 → 1.4933, away from the reference 1.0) but **improved** the load
factor (0.2415 → 0.254, towards LP1's 0.413) — because a 60-home estate sits
at 0.24 against a national class profile's 0.413, so anything that spreads
load looks better on that metric regardless of whether it is more realistic.
The arm's verdict stands on the gas ratio; the load-factor expectation was
wrong, and that is I-050. The scoring was not changed after seeing the
result.

**U31 / U32.** A held-out slice spanning 1967–99 and post-2005 homes, with
nothing fitted on it and the prohibition enforced rather than intended. U32
replaced PL-PEAK-01's two-point taper with a whole-overnight-shape check whose
band is **derived** from LP1 (half what a shapeless profile would show,
0.1901), and widened the sleep-timing distributions from HETUS UK AC0A while
keeping the Irish medians.

The awake-share fit against HETUS is **0.0283** at the U32 test's seed
(20261008) and **0.0169** at the ten-year run's seed (20251010), against a
band of 0.05 — so the fit is stable across seeds, which matters because the
metric is a population marginal and a seed-sensitive one would not be
evidence of calibration. It was 0.0621 before the fixes.

---

## 9. Step 5's storage and runtime, measured

Ten full years simulated on the 60-home slice, the plausibility suite run on
each one.

| year | people | vacant | measures | run (min) | storage (MB) | peak RSS (MB) | suite PASS / NOT_EVAL |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2022 | 133 | 0 | 0 | 38.8 | 288 | 4231 | 10 / 2 |
| 2023 | 131 | 2 | 5 | 38.7 | 286 | 4132 | 10 / 2 |
| 2024 | 125 | 3 | 10 | 38.5 | 284 | 3897 | 10 / 2 |
| 2025 | 129 | 3 | 15 | 42.5 | 284 | 4322 | 10 / 2 |
| 2026 | 121 | 3 | 20 | 41.9 | 284 | 4105 | 10 / 2 |
| 2027 | 125 | 3 | 22 | 42.1 | 284 | 4246 | 10 / 2 |
| 2028 | 129 | 3 | 22 | 36.5 | 284 | 4264 | 10 / 2 |
| 2029 | 136 | 3 | 24 | 37.4 | 286 | 4378 | 10 / 2 |
| 2030 | 141 | 3 | 25 | 38.1 | 286 | 4378 | 10 / 2 |
| 2031 | 140 | 3 | 26 | 35.8 | 286 | 4421 | 10 / 2 |

| | |
| --- | --- |
| **Total storage** | **2.85 GB** (285 MB per year) |
| **Total runtime** | **6.5 CPU-hours** (39.0 min per year) |
| **Wall clock** | about 2.2 h, three years in parallel on 6 physical cores |
| **Peak RSS** | 4421 MB per process |
| **Suite** | 10 years run; **0 FAIL, 0 NO_DATA** |
| **Life course** | 241 D09 events, 244 D20 labels, 47 D03 passport events |

### The suite result, with the split that matters

Each year returns **10 PASS and 2 NOT_EVALUABLE** of 12 checks, and the suite's
own rule is that one number would mislead. **Three** counts, after I-058:

* **6 pass against an independent published reference** — a source at exposure
  `none` (appliance ownership and size slopes, floor area, fuel mix, peak and
  load factor);
* **2 pass against a *calibration input*** — PL-ELEC-01 against DBEREL01 and
  PL-GAS-01 against DBERNG01, both at exposure `tuning`. Those are consistency
  checks, not independent validations: the model was tuned towards those
  tables, so passing cannot evidence generalisation. They can still catch
  gross error, which is what they were built for;
* **1 passes against a `design`-exposed reference** (PL-DHW-01 against the
  DEAP manual);
* **1 passes against a declared band** (indoor temperature — I-032: no CSO or
  SEAI table publishes measured Irish indoor temperatures);
* **2 are NOT_EVALUABLE** with a named issue (appliance energy shares and
  EV/heat-pump consumption — I-039: PxStat publishes ownership but no end-use
  energy, and charge-point consumption is not per-dwelling).

An earlier draft of this section said "9 pass against a published reference".
That is true and it reads as nine independent checks, which it is not. The
independent count is **6**, and the genuinely independent energy axes —
DBEREL02 and DBERNG02, dwelling type × period of construction, both at
exposure `none` — are held out and used by the gate report's `heldout` block
and by U31.

**Zero `NO_DATA` on all ten years is the load-bearing result here**, not an
incidental one. The per-year packages deliberately omit D18, the 1-minute
observation series, which is 69% of a year's bytes — and the justification is
that no plausibility check reads it. That is enforced rather than asserted: a
check starved of its input returns `NO_DATA`, so the acceptance test is that
none does. Writing D18 would have taken the decade from 2.85 GB to about
9.2 GB and roughly doubled the runtime, for no check.

### Reading these figures across to the full town

The projection in §11 should be rebuilt from these, with three corrections to
any naive scaling:

* **Per-home, not per-year.** 285 MB for 60 homes is 4.75 MB per home-year
  without D18. The full town is 1,092 homes, so a ten-year town package on the
  same views is about **52 GB** — against the 232 GB that was projected with
  D18 included, which is the measurement that matters for I-036.
* **Runtime does not parallelise past the cores.** 39 min per year is wall
  clock for one process; the decade took about 2.2 h with three in parallel and
  the load average sat at 11 on 6 physical cores, so more processes would not
  have helped. A full town is 18× the homes, so about 12 h per year of
  simulation at this rate, which is the number E2 planning needs.
* **Peak RSS is per process, and it is the binding constraint on parallelism.**
  About 4421 MB for 60 homes; the engine streams rather
  than accumulating, so the town should not scale this linearly, but it has not
  been measured at town size and should not be assumed.

### Two limits on what this decade is

**The weather does not vary (I-057).** All ten years use the identical real
2022 weather, because `run_year` hard-codes the year. For step 5 that is the
right control — it is what makes the per-year comparison in I-055
interpretable, since the overnight trend cannot be a weather artefact. For a
*delivered* dataset it is a defect of a leakage-like kind: a model can
memorise ten identical years and forecast the weather perfectly. 2023–2026 have
real observed weather in the already-declared Met Éireann archive (which spans
1955–2026) and are not using it; 2027–2031 cannot, and need a declared policy.

**The fabric measures are recorded but not applied (I-054).** Over the
decade, **8 fabric retrofits and 13 extensions** produce their D03 passport
events and D20 labels and do *not* change the RC parameters, because I-048
defers fabric to week 3. That is 21 of the 47 passport events — **45% of the
building changes this run records are not in the series**, so a detector scored
against those labels in a week-2 package scores a false negative through no
fault of its own. The proportion is larger than it looked mid-run and is the
single biggest caveat on using this decade for detector scoring.

---

## 10. Open issues carried into week 3

| Issue | Severity | What it is | Disposition |
| --- | --- | --- | --- |
| **I-048** | Medium | the retrofit hypothesis for the fabric work | **week 3 fabric work**, alongside CD488 and F2063 |
| **I-054** | Medium | fabric-retrofit D20 labels describe a change the week-2 series does not contain | closes with I-048 |
| **I-052** | Medium | the activity-to-load mix is wrong at the day's boundaries (23:00 draws 6.39 against LP1's 4.01; 06:00 3.45 against 4.28) | **week 3 device work.** The awake count is calibrated and the standby floor is right; the residual is the mix, and the quantity to aim at is now precise |
| **I-050** | Low | distance-to-reference is the wrong scoring for a structurally one-sided metric | recorded; affects how an ablation is read, not what it measures |
| **I-043** | — | per-dwelling peak needs forbidden microdata | structural: PxStat has nothing, and ESB Networks publishes the class profile instead |
| **I-045** | — | shower duration is unsourceable | DEAP publishes the flow rate, not the duration; PL-DHW-01 bounds the consequence |
| **I-042** | — | ownership slopes ≈2× published | recorded against HS219 |
| **I-055** | Medium | PL-PEAK-01's reference is fixed at 2022 while the population is not; the overnight MAD rises 0.1434→0.1818 against a 0.1901 band, tracking the **assets** (p=0.023) not the population (p=0.163) | **found by the ten-year run.** A DER ablation is the deciding experiment; the band is not to be widened |
| **I-056** | Medium | `SynthBuilding`'s DER flags are undeclared attributes, so `dataclasses.replace` silently drops them | worked around with `copy.copy`; root cause is week 3, before the full town run, because declaring the fields changes a dataclass's hashes |
| **I-057** | High for a delivered dataset | the ten-year run uses 2022's weather ten times | the right **control** for step 5, a leakage-shaped defect for a dataset. Needs a declared 2027–2031 policy before the week 3 run |

Closed this week: **I-039** (peak/load-factor reference, at aggregate level,
against LP1), **I-044** (the overnight taper — nobody in the town was awake
after midnight), **I-046** (cooking split derived), **I-049** (held-out
slice), **I-051** (closed for what it described; the residual became I-052),
**I-053** (crossed vital-statistics matrices, fixed and guarded).

---

## 11. What week 3 needs

r4 §9.3 row 3: full town and network; joint and spatial validation; the 6.4
observable additions with 6.5 tests; privacy threat model and attacks; the
full ten-year run; the linked MIMIC panel; three delivery packages and a tell
audit; the E2 gate report.

Two things gate it.

**I-036 — storage.** The ten-year full-town package was projected at 232 GB
against 74 GiB free when the week began; the current disk has **120.9 GB
free**. `<SSD_PATH>` is still unset and no external drive is attached;
`/Volumes/Vault` is an encrypted sparse bundle on the internal disk, not extra
space.

§9 replaces the projection with measurements. Without D18, a decade of the
60-home slice is **2.85 GB** — 4.75 MB per home-year — which scales to about
**52 GB** for a ten-year full-town package on the same views, against the
232 GB projected with D18 included. D18 is 69% of a year's bytes and no
plausibility check reads it, so how the three delivery packages are scoped
changes the storage requirement by a factor of four, and that is a decision to
make deliberately rather than discover.

**A release path for D09, D20 and D03.** The ten-year run produces the life
events, change labels and passport events, and none of them belongs in a
released package — D20's schema says *"Scoring API only. Never released"*. So
the per-year packages carry D11/D13/D16/D19 exactly as E1's does, and the
ground truth lives in `v1/evidence/wp5_tenyear.json`. That is adequate for a
checkpoint and not adequate for scoring: a detector is scored against the
label *rows*, and the scoring API (r4 §8.3, R30) is week 3. Whoever builds it
should read those rows from the evidence artefact rather than regenerating
them, so that what a detector is scored against is the same ground truth this
checkpoint reports.

**C2's network claim.** The timing contract is implemented and tested, but the
step-5 solve is still a feeder aggregation. `pandapower` and the real power
flow are week 3, and until they exist no voltage, loading or
network-constraint claim can be made from any output — including the coupling
figures in §5, which are about *timing*, not about the network.

---

## 12. Method notes from the week

Seven things that generalise, each earned rather than asserted.

**Running the thing for its full duration finds what no unit test does.** The
life course had 26 tests passing before a single full year was simulated, and
all three of the decade's findings came from running it anyway: the metric
drifting towards its own band as the population diverged from the reference
(I-055), the slice mutation that only two years in one process could expose
(I-056), and ten years of identical weather (I-057). None is the kind of thing
a unit test is shaped to catch — the first needs ten years of output to see,
the second needs a usage pattern production does not have, and the third is
*correct behaviour* of a function doing exactly what it was told. A suite
passing is evidence that the parts work, not that the whole is what was
intended.

**A figure quoted from a summary is not a figure.** Writing this checkpoint
meant re-deriving every number in it from an artefact or from the code, and
**six did not survive**: the week's source count (24 → 27), PL-GAS-01's ratio
(a quoted 0.785 that appears in no artefact; the measured values are 0.308,
0.331 and 0.983 on three different packages), comfort-taking's prebound shifts
(−1.50/−0.00 → −1.95/−0.24 at a stated fabric), the slice's age composition
(1962/84% → 1953.0/90.0%, because the quoted pair was the slice before U29's
resize), T6 and the G-C statistics (quoted at an exploratory seed, not the
recorded one), and the multi-seed result (31/32 pooled sourced events with an
assumed rate). None was a modelling error; every one was a reporting error,
and the two are not easier to tell apart afterwards. The rule that would have
prevented all six: a checkpoint cites the artefact, and if there is no
artefact there is no number.

**A declared source that nothing consumes is an unverified claim.** I-053 sat
for a week because the registry recorded *intent* and only reading the file
tests it. The guard that now exists compares each cube's own label against the
declared title, with a threshold measured from the corpus rather than chosen.

**A threshold should be derived from the published reference, or from a
reference distribution the data itself generates — never declared and then
defended.** Three of this week's criteria were declared first and the data
refused all three: a 0.25 silhouette cut-off (k-means on one Gaussian scores
about 0.33), a fixed standard-error threshold for non-identifiability (r = 0.97
leaves coefficients estimable), and a vacancy range asserted from year one (a
fully-occupied slice can only approach it from below).

**Test a contract at more than one operating point.** The coupling envelope
passed the connection-binding regime and failed the feeder-binding one. A
single operating point would have certified a broken guarantee.

**Record the quantity integrated at decision time, not only the outcome.** The
parity bug produced a count comfortably inside its confidence interval while
being 12% wrong. Comparing the hazard integrated at draw time against the
exposure expectation is the only thing that would have caught it.

**When a check's verdict is inverted, the harness is usually right.**
NC-GC-03 reported `NOT_DETECTED` twice. Both times the control was wrong — a
positive control does not fit a negative-control harness — and both times the
temptation was to adjust the harness.

---

*Produced by the week 2 run. Every figure above is reproducible from the
master seed recorded in the evidence artefacts under `v1/evidence/`.*
