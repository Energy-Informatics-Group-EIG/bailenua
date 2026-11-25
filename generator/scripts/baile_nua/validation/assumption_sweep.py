"""U30: sweep every remaining ``[A]`` assumption flag against PxStat.

I-040 is the reason this module exists. ``OWNERSHIP_PRIORS`` carried its
appliance rates as declared assumptions for four days behind a comment that
said SAPS publishes no appliance ownership - which was *true*, and still left
a public CSO source (HAS02) unused, because the comment recorded a conclusion
rather than a search. The lesson recorded there was:

    An ``[A]`` flag should record what was searched, not only that something
    is assumed.

So each flag below carries its **search terms**, and this module runs them
over the whole PxStat catalogue (``cso.pxstat.collection``: 13,086 tables with
their titles and the label of every dimension) and records the hits. The
verdict is declared; the evidence for it is computed. Two consequences:

* A flag saying "nothing public exists" is checked. ``KEPT`` flags that claim
  no hits are asserted to have none in the catalogue as fetched, so the claim
  cannot quietly go stale when the CSO publishes something.
* The search is reproducible. The catalogue is a declared source with a date
  and a SHA-256 like any other input, not a live query.

**Dimension labels matter more than titles.** HS023's title is the single word
"Households"; everything that makes it useful - that it breaks down by
household appliance, and by urban/rural - is in its dimension labels. A
title-only search would not find it. That is how HAS02 was missed and how the
HBS tables were found.

**A broad term finds nothing; it drowns.** ``BER\\b`` matches 932 tables
because "Number" and "Member" contain "ber". A term matching hundreds of
tables has not searched, so :func:`sweep` records each term's hit count and
:data:`BROAD_TERM_LIMIT` fails a term that must be anchored.

Verdicts
--------
``RETIRED``
    A public source was found, declared, fetched, and the assumption is now
    scored against it. The flag is gone.
``SOURCE_FOUND``
    A public source was found and declared, but wiring it in belongs to a
    named step. The flag stays, and now names a table instead of a void. This
    verdict is deliberately not ``RETIRED``: an unused source retires nothing.
``KEPT``
    Searched, nothing published. The flag stands with its search record.
``WRONG_INSTRUMENT``
    PxStat is a statistical-table service and cannot carry this kind of
    evidence at all (a regulatory U-value, a psychometric dispersion, a
    sub-metered appliance trace). Recorded as searched, with why the negative
    result is structural rather than a gap the CSO might one day fill.
"""

from __future__ import annotations

import dataclasses
import json
import re
from pathlib import Path
from typing import Any

from baile_nua.sources import REGISTRY, SourceError, require

__all__ = [
    "AssumptionFlag",
    "ASSUMPTION_FLAGS",
    "CatalogueEntry",
    "BROAD_TERM_LIMIT",
    "SWEEP_DATE",
    "load_catalogue",
    "search",
    "sweep",
    "write_sweep",
]

#: The date the sweep was run, as U30 requires it recorded. Fixed rather than
#: ``date.today()`` so the artefact is reproducible: the catalogue's own
#: manifest carries the retrieval date, and these must agree.
SWEEP_DATE = "2026-10-09"

#: A search term matching more tables than this has not narrowed anything and
#: is almost always an unanchored substring. 932 was the real one.
BROAD_TERM_LIMIT = 300

CATALOGUE_KEY = "cso.pxstat.collection"


@dataclasses.dataclass(frozen=True)
class CatalogueEntry:
    """One PxStat table, reduced to what a search needs."""

    matrix: str
    title: str
    dimensions: tuple[str, ...]

    @property
    def haystack(self) -> str:
        return f"{self.title} | {' | '.join(self.dimensions)}"


@dataclasses.dataclass(frozen=True)
class AssumptionFlag:
    """One remaining ``[A]`` flag, with the search that justifies its state."""

    flag_id: str
    subject: str
    #: Where the assumption lives. Module-qualified, so a reader can go to it.
    where: tuple[str, ...]
    #: What is assumed, in one line.
    assumed: str
    #: What evidence would retire it. Written before searching, not after.
    retires_if: str
    #: Regexes run over title + dimension labels.
    search_terms: tuple[str, ...]
    verdict: str
    verdict_note: str
    #: Declared source keys supporting a RETIRED or SOURCE_FOUND verdict.
    sources: tuple[str, ...] = ()
    #: The step that owns wiring a SOURCE_FOUND in.
    owning_step: str = ""
    issue: str = ""
    #: Tables the search found that are worth naming even under KEPT, because
    #: a near-miss is part of an honest record: it shows the search reached
    #: the right shelf and the book was not there.
    near_misses: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.verdict not in _VERDICTS:
            raise ValueError(f"{self.flag_id}: unknown verdict {self.verdict!r}")
        if self.verdict in ("RETIRED", "SOURCE_FOUND") and not self.sources:
            raise ValueError(
                f"{self.flag_id}: {self.verdict} must name the source(s) that "
                f"justify it, or it is just an assertion"
            )
        if self.verdict == "SOURCE_FOUND" and not self.owning_step:
            raise ValueError(
                f"{self.flag_id}: SOURCE_FOUND must name the step that will "
                f"use the source, or the find will sit unused as HAS02 did"
            )
        if not self.search_terms:
            raise ValueError(f"{self.flag_id}: a sweep entry needs search terms")


_VERDICTS = ("RETIRED", "SOURCE_FOUND", "KEPT", "WRONG_INSTRUMENT")


# --------------------------------------------------------------------------- #
# The flags. One entry per subject, not per string occurrence: `[A]` appears
# many more times than there are assumptions - one assumption is usually
# described in several places - so the entries are the authority on how
# many there are, and `uncovered_files` is the authority on whether any
# occurrence has been missed.
#
# `retires_if` was written before the search was run, so that the standard of
# evidence is not set by what happened to be found.
# --------------------------------------------------------------------------- #

ASSUMPTION_FLAGS: tuple[AssumptionFlag, ...] = (

    # ---------------- activity: the HETUS donor ---------------- #
    AssumptionFlag(
        flag_id="A-01", subject="HETUS UK donor for Irish time use",
        where=(
            "sources_registry.eurostat.hetus.* (substitute_flag)",
            "activity/hetus.py",
        ),
        assumed=(
            "UK diary data stands in for Irish time use; Irish anchoring comes "
            "from Cobh's own Census travel-to-work and time-leaving-home tables"
        ),
        retires_if="the CSO publishes an Irish time-use survey with activity durations",
        search_terms=(r"time use", r"time-use", r"\btime budget\b", r"\bdiary\b"),
        verdict="KEPT",
        verdict_note=(
            "No Irish time-use survey in the catalogue. The only matches are "
            "well-being tables on SATISFACTION with the amount of leisure time "
            "(WBA39, WBA40, WBB63-66), which measure contentment, not "
            "duration. Ireland is in neither HETUS wave (I-008), and the CSO "
            "has not run a time-use survey it publishes here, so the UK donor "
            "stands and the activity engine stays VERIFIED, NOT CALIBRATED."
        ),
        near_misses=(
            "WBA39/WBA40/WBB63-66 satisfaction with time use - a different "
            "quantity entirely",
        ),
        issue="I-008",
    ),
    AssumptionFlag(
        flag_id="A-02", subject="ACL00 code substitution for adult care",
        where=("activity/hetus.py:142 (AC38B -> AC37_39)",),
        assumed=(
            "HETUS's 'household management and help to family member' stands "
            "for adult care, the nearest available aggregate"
        ),
        retires_if="a published Irish adult-care duration by age and sex",
        search_terms=(r"\bcare\b.*\b(hour|time|duration)", r"carer"),
        verdict="WRONG_INSTRUMENT",
        verdict_note=(
            "This is a codelist mapping between two HETUS activity codes, not "
            "a statistic. PxStat publishes carer COUNTS (census tables on "
            "persons providing unpaid care) but no duration that could be "
            "substituted into a semi-Markov duration distribution. The census "
            "carer counts constrain WHO cares, which the population layer "
            "already takes from SAPS, not HOW LONG, which is the assumption."
        ),
        issue="I-008",
    ),
    AssumptionFlag(
        flag_id="A-03", subject="donor diary day weight of exactly 1.0",
        where=("activity/hetus.py:84",),
        assumed="a UK diary day counts as one Irish diary day, unweighted",
        retires_if=(
            "a published Irish-to-UK time-use adjustment factor, or an Irish "
            "survey to weight towards"
        ),
        search_terms=(r"time use", r"survey weight"),
        verdict="WRONG_INSTRUMENT",
        verdict_note=(
            "A weight of exactly 1.0 is a declared modelling choice, and the "
            "comment in the code says so: it is an assumption, where any other "
            "number would be a measurement. Nothing in a statistical catalogue "
            "can supply it while A-01 holds - with no Irish survey there is "
            "nothing to weight towards."
        ),
        issue="I-008",
    ),

    # ---------------- devices: appliance ownership ---------------- #
    AssumptionFlag(
        flag_id="A-04", subject="appliance ownership base rates that a source covers",
        where=("devices/appliances.py OWNERSHIP_PRIORS",
               "validation/controls_plausibility.py NC-W2-05 (guards them)"),
        assumed=(
            "base ownership probabilities for washing machine, tumble dryer, "
            "dishwasher, microwave, television and fridge-freezer"
        ),
        retires_if="a published Irish share of households possessing each appliance",
        search_terms=(r"appliance", r"washing machine", r"dishwasher",
                      r"tumble dryer", r"television"),
        verdict="RETIRED",
        verdict_note=(
            "Six of the fifteen priors are now scored, and getting there "
            "turned up a second instance of the I-040 mistake inside the "
            "source that taught it. HAS02 publishes NINETEEN appliance types, "
            "and the map built on 9 Oct used four - leaving 'Colour "
            "television' at 96.3% unmapped beside a model prior of 0.96. U30 "
            "mapped it, so PL-APPL-01 now scores five. The Household Budget "
            "Survey (HS023) adds the sixth, `fridge_freezer`, and PL-APPL-02 "
            "scores six. Both sources are declared validation-only: the "
            "priors were set before either was found, so they judge them. "
            "Recorded as I-041: a declared source with a mappable row left "
            "unmapped is the same failure as an undiscovered source, and only "
            "a check that enumerates the source's own categories finds it."
        ),
        sources=("cso.appliances.has02_ownership",
                 "cso.appliances.hs023_hbs_appliances_urban_rural"),
        issue="I-040",
    ),
    AssumptionFlag(
        flag_id="A-05", subject="appliance ownership base rates no source covers",
        where=("devices/appliances.py OWNERSHIP_PRIORS",),
        assumed=(
            "base ownership for kettle, toaster, hob, oven, extractor fan, "
            "lighting, standby, electric shower and immersion heater"
        ),
        retires_if="a published Irish ownership share for any of these",
        search_terms=(r"appliance", r"\bkettle\b", r"\btoaster\b",
                      r"\b(hob|cooker|oven)\b", r"extractor",
                      r"electric shower", r"immersion"),
        verdict="KEPT",
        verdict_note=(
            "Neither HAS02's seven nor the HBS's thirteen includes any of "
            "these. The HBS list is vacuum cleaner, tumble dryer, washing "
            "machine, dishwasher, refrigerator, refrigerator with freezer, "
            "separate deep freeze, microwave oven, TV, home computer and games "
            "console - so a kettle, a hob and an immersion heater are "
            "unmeasured in both, which is unsurprising for near-universal or "
            "fixed appliances. Nine of the fifteen priors stay declared "
            "assumptions, and are now assumptions with a search behind them."
        ),
        near_misses=(
            "HS023/HS219 cover vacuum cleaner, home computer and games "
            "console, which this model does not simulate",
        ),
        issue="I-040",
    ),
    AssumptionFlag(
        flag_id="A-06", subject="ownership slope per additional occupant",
        where=("devices/appliances.py OWNERSHIP_PRIORS[*]['per_person']",),
        assumed=(
            "ownership rises with household size at 0.05-0.06 per person for "
            "tumble dryer and dishwasher, 0.01 for television"
        ),
        retires_if="published ownership by household size",
        search_terms=(r"appliance",),
        verdict="RETIRED",
        verdict_note=(
            "The code's own comment was 'the sub-linearity is not in doubt, "
            "only its slope'. HS219 publishes the slope: the same thirteen "
            "appliances by household size, 1 person to 6+. Scored by the new "
            "PL-APPLSIZE-01, which passes 5 of 5 - and the measurement is "
            "worth stating precisely, because passing is not the same as "
            "agreeing. The declared slopes are about TWICE the published "
            "ones throughout: dishwasher 0.06 against 0.029, tumble dryer "
            "0.05 against 0.026. Both sit inside a band declared in advance "
            "at +/-0.05 per person, so the check passes honestly; the "
            "systematic factor of two is a finding for whoever next touches "
            "these values, and is recorded rather than quietly absorbed. "
            "Where HS219 is flat the model is flat too, which is the part a "
            "declared constant is most at risk of getting wrong."
        ),
        sources=("cso.appliances.hs219_hbs_appliances_by_household_size",),
        issue="I-040",
    ),
    AssumptionFlag(
        flag_id="A-07", subject="extra appliance cycles per extra occupant",
        where=("devices/appliances.py EXTRA_CYCLE_PER_EXTRA_PARTICIPANT",
               "calibration/targets.py (trigger rates had nothing to score them)",),
        assumed=(
            "cycle frequency scales sub-linearly with occupancy: kettle 0.30, "
            "toaster 0.45, microwave 0.35, hob 0.12 per extra participant"
        ),
        retires_if="published Irish appliance USE frequency by household size",
        search_terms=(r"appliance", r"\busage\b.*\bhousehold\b"),
        verdict="KEPT",
        verdict_note=(
            "HS219 publishes ownership by household size, not use. Owning a "
            "kettle and boiling it four times a day are different quantities, "
            "and only the first is published. Sub-metered use frequency is "
            "what would settle this, and the only Irish sub-metered trial is "
            "CER/ISSDA, which the brief forbids."
        ),
    ),
    AssumptionFlag(
        flag_id="A-08", subject="appliance power signature templates",
        where=("devices/signatures.py",),
        assumed=(
            "parameterised load-shape templates (nominal power, duration, "
            "ageing) tagged evidence_status='[A]' and "
            "provenance='synthetic-template' in D22"
        ),
        retires_if="a public Irish sub-metered appliance trace set",
        search_terms=(r"appliance", r"sub-?meter", r"load profile", r"half-?hourly"),
        verdict="WRONG_INSTRUMENT",
        verdict_note=(
            "A statistical-table service cannot publish a load trace. There is "
            "no public Irish sub-metered appliance dataset; CER/ISSDA is the "
            "only Irish one and the brief forbids it. The templates are "
            "declared synthetic in D22 precisely so that no consumer mistakes "
            "them for measurements, and 7.9's tell audit covers the risk that "
            "they are too clean."
        ),
    ),

    # ---------------- physics and fabric ---------------- #
    AssumptionFlag(
        flag_id="A-09", subject="indoor temperature plausibility band",
        where=("plausibility/checks.py PL-TEMP-01", "validation/invariants.py",
               "plausibility/suite.py (module docstring states the band)"),
        assumed=(
            "median 15-23 C, at most 5% of hours above 28 C, peak at most 40 C"
        ),
        retires_if="any published Irish measurement of indoor dwelling temperature",
        search_terms=(r"indoor temperat", r"dwelling temperat", r"room temperat",
                      r"thermal comfort"),
        verdict="KEPT",
        verdict_note=(
            "Zero hits across all 13,086 tables, for every phrasing. This is "
            "the sweep's most decisive negative: I-032 said 'no CSO or SEAI "
            "table publishes measured indoor temperature' and that claim has "
            "now been tested against the whole catalogue rather than asserted. "
            "The band stays declared, and PL-TEMP-01 keeps reporting PASS "
            "(declared band, unsourced) rather than PASS - which matters, "
            "because it was a 24.6 C median that this band caught."
        ),
        issue="I-032",
    ),
    AssumptionFlag(
        flag_id="A-10", subject="room count given dwelling type and bedrooms",
        where=("population/buildings.py", "population/saps.py rooms marginal"),
        assumed=(
            "room counts drawn from the SAPS rooms marginal, with a minimum "
            "rooms-over-bedrooms margin set by a feasibility test rather than "
            "from a joint distribution"
        ),
        retires_if=(
            "a published joint of rooms with dwelling type and bedrooms for "
            "the census year of T0"
        ),
        search_terms=(r"Number of Rooms", r"Rooms Occupied"),
        verdict="RETIRED",
        verdict_note=(
            "F2063 is the table whose absence caused I-031. Census 2022 "
            "publishes rooms x bedrooms x year built x dwelling type x county "
            "- the exact four-way joint that was drawn independently and "
            "produced a 285.7 m2 three-bedroom apartment burning 13.6 MWh. "
            "SAPS publishes these as separate marginals, which is why the "
            "assumption looked unavoidable; the county-level census table "
            "publishes the joint. Scored by the new PL-ROOMS-01 at Cork "
            "County, not used to recalibrate: the geometry was fixed before "
            "this was found, so the table judges it rather than fitting it."
        ),
        sources=("cso.census2022.f2063_rooms_bedrooms_year_type",),
        issue="I-019, I-031",
    ),
    AssumptionFlag(
        flag_id="A-11", subject="floor area per habitable room",
        where=("population/buildings.py AREA_PER_ROOM_M2",),
        assumed="m2 per habitable room by dwelling type (18.0 to 24.0)",
        retires_if="a published Irish floor area crossed with room count",
        search_terms=(r"floor area", r"\bsize of dwelling", r"square met"),
        verdict="KEPT",
        verdict_note=(
            "The census counts rooms and never measures them. The only floor "
            "areas the CSO publishes are TRS05 (total floor area of rental "
            "properties by local authority) and NDA08 (new dwelling size by "
            "type), both already declared and neither crossed with room count, "
            "so neither gives area PER ROOM. F2063 retires the room-count half "
            "of I-019 (A-10) and leaves this half assumed - which is now a "
            "precise statement of the gap rather than a general one."
        ),
        near_misses=("TRS05 rental floor area, NDA08 new dwelling size - both "
                     "declared, neither crossed with rooms",),
        issue="I-019, I-031",
    ),
    AssumptionFlag(
        flag_id="A-12", subject="heating fuel given dwelling type",
        where=("population/saps.py central_heating marginal notes (I-011)",),
        assumed=(
            "the dwelling-type x heating-fuel joint, since SAPS publishes the "
            "two marginals separately"
        ),
        retires_if="a published joint of dwelling type with central heating fuel",
        search_terms=(r"Central Heating",),
        verdict="SOURCE_FOUND",
        verdict_note=(
            "CD488 publishes dwelling type x central heating fuel x period "
            "built (Census 2011), and E1055 the same for 2011-2016. Eleven "
            "years before T0, so it constrains the STRUCTURE - which fuels go "
            "with which dwelling type and era - while the 2022 levels stay "
            "anchored to SAPS 2022. Not wired in: doing so changes the fabric "
            "and heating assignment, which is week 3 work, and changing it now "
            "would alter every E1 artefact. The flag stays and now names a "
            "table."
        ),
        sources=("cso.census2011.cd488_heating_by_accommodation_and_period",),
        owning_step="week 3, fabric and heating (S-series)",
        issue="I-011",
    ),
    AssumptionFlag(
        flag_id="A-13", subject="detached / semi-detached / terraced split",
        where=("population/saps.py dwelling_type marginal notes (I-011)",),
        assumed=(
            "SAPS 2022 publishes only four dwelling categories and does not "
            "split houses, so the split comes from SEAI BER public data"
        ),
        retires_if="a census dwelling-type split for Cobh's county in 2022",
        search_terms=(r"Type of Private Accommodation",),
        verdict="SOURCE_FOUND",
        verdict_note=(
            "The split IS published for 2022, at county rather than small-area "
            "level: F2063's dwelling-type dimension is the full eight "
            "categories including detached, semi-detached and terraced, for "
            "each of the 32 administrative counties. So the [A] note is "
            "accurate about SAPS and wrong about the census. Using it would "
            "replace a cross-dataset BER-derived split with a same-census one, "
            "which is a better anchor; it also moves a calibration input, so "
            "it belongs to the week 3 fabric work and not to a sweep. "
            "PL-ROOMS-01 scores the current split against it meanwhile."
        ),
        sources=("cso.census2022.f2063_rooms_bedrooms_year_type",),
        owning_step="week 3, fabric and heating (S-series)",
        issue="I-011",
    ),
    AssumptionFlag(
        flag_id="A-14", subject="electricity split: heat pump vs direct electric",
        where=("population/saps.py central_heating marginal notes (I-011)",),
        assumed=(
            "the share of 'Electricity' central heating that is a heat pump "
            "rather than resistance heating, taken from SEAI BER data"
        ),
        retires_if="a published split of electrically heated dwellings by system",
        search_terms=(r"heat pump", r"Central Heating"),
        verdict="KEPT",
        verdict_note=(
            "The census records the FUEL, not the system: a heat pump and an "
            "immersion-fed storage heater both report 'Electricity'. CD488's "
            "fuel dimension confirms it - twelve fuel categories, no system. "
            "EBQ02 (declared) gives heat-pump penetration among NEW BER "
            "assessments, which is the closest public figure and is already "
            "used. The within-electricity split stays assumed."
        ),
        near_misses=("EBQ02 renewables - already declared and used",),
        issue="I-011",
    ),
    AssumptionFlag(
        flag_id="A-15", subject="fabric U-values by construction era",
        where=(
            "data/fabric_u_values.yaml",
            "physics/deap_appendix_s.py",
            "physics/fabric_assessed.py",
            "physics/archetype.py (USE_ASSESSED_FABRIC)",
        ),
        assumed=(
            "wall, roof, floor and glazing U-values by era, not read back from "
            "the Part L documents in this run"
        ),
        retires_if="the Part L / TGD regulatory values, read from their documents",
        search_terms=(r"\bU[- ]?value", r"thermal transmittance", r"insulation"),
        verdict="RETIRED",
        sources=("seai.deap.manual_4_2_7", "seai.ber.research_tool"),
        verdict_note=(
            "Retired in week 3 against this flag's OWN pre-written criterion, "
            "which is the only reason it may be retired: 'the Part L / TGD "
            "regulatory values, read from their documents'. DEAP Appendix S "
            "Table S2 IS that table - DEAP is the regulatory methodology every "
            "Irish BER is computed with - and physics/deap_appendix_s.py "
            "machine-extracts it from the manual PDF rather than transcribing "
            "it, so a value that drifts from the document fails the suite. "
            "Tables S3 (wall by type x band), S4/S5 (roof) and S8 (floor) come "
            "the same way.\n\n"
            "The sweep's earlier verdict was not wrong about the catalogue: "
            "PxStat still returns zero, and ZERO_HIT_CLAIMS still asserts it. "
            "It was wrong about where to look - a regulatory document, not a "
            "statistical one - and about giving up on the quantity rather than "
            "the instrument.\n\n"
            "Two things this does NOT retire, and both are flagged "
            "separately: WHICH dwellings are in which retrofit state (the "
            "assessed conditional in physics/fabric_assessed.py answers it "
            "from 1,024,584 assessed dwellings, and that source is "
            "tuning-exposed for fabric per I-058, so it may never validate "
            "fabric); and what a retrofit MEASURE does, which is A-45 to A-47."
        ),
        issue="I-019, I-048",
    ),
    AssumptionFlag(
        flag_id="A-16", subject="BER band boundaries and DEAP primary-energy scope",
        where=("data/ber_bands.yaml",),
        assumed=(
            "kWh/m2/yr band boundaries and what DEAP's primary-energy figure "
            "includes, not read back from the SEAI document in this run"
        ),
        retires_if="the SEAI DEAP manual's band table, read from the document",
        search_terms=(r"energy rating", r"\bBER\b", r"Building Energy Rating"),
        verdict="WRONG_INSTRUMENT",
        verdict_note=(
            "PxStat publishes BER-derived STATISTICS in quantity - EBA02 and "
            "EBQ02 are declared and used, and the catalogue carries many more "
            "- but the band boundaries themselves are a definition in the DEAP "
            "methodology, not a statistic. Note for future sweeps: the term "
            "'BER' unanchored matches 932 tables, because 'Number' and "
            "'Member' contain it. A term that matches hundreds has not "
            "searched; BROAD_TERM_LIMIT fails it."
        ),
        issue="I-019",
    ),
    AssumptionFlag(
        flag_id="A-17", subject="archetype thermal parameters",
        where=("physics/archetype.py (thermal mass, glazed fraction, "
               "infiltration ACH, storey height, air/envelope split)",),
        assumed="4R3C parameter values by era and dwelling type",
        retires_if="published Irish measured values for any of them",
        search_terms=(r"air change", r"air tightness|airtight", r"thermal mass",
                      r"glazing|glazed"),
        verdict="WRONG_INSTRUMENT",
        verdict_note=(
            "Zero hits for every term. These are building-physics parameters, "
            "measured by blower-door and co-heating tests and published in "
            "research literature, not national statistics. The code already "
            "says the right thing - 'declared assumptions [A] in their exact "
            "values; the mechanism is not in doubt' - and the V-level scheme "
            "handles it: the physics is V2 grey-box, never claimed as "
            "calibrated."
        ),
        issue="I-019",
    ),
    AssumptionFlag(
        flag_id="A-18", subject="performance gap: rated vs actual energy",
        where=("physics/archetype.py performance gap factor (K14)",),
        assumed=(
            "efficient dwellings underperform their rating by a declared factor"
        ),
        retires_if=(
            "published Irish consumption crossed with energy rating, which "
            "would make the gap measurable rather than assumed"
        ),
        search_terms=(r"electricity consum", r"gas consum", r"energy consum"),
        verdict="SOURCE_FOUND",
        verdict_note=(
            "DBEREL01/02 and DBERNG01/02 are exactly this - metered household "
            "consumption crossed with BER band and with period of construction "
            "- and all four are already declared and used by PL-ELEC-01 and "
            "PL-GAS-01. They are what makes the performance gap a MEASURED "
            "quantity in this project: DBERNG01 shows gas varying only 4-7% "
            "across BER bands while varying 84% across dwelling types, and "
            "A-B detached burning more gas than F-G. The flag stays because "
            "the declared FACTOR has not yet been replaced by that evidence - "
            "which is precisely what U22 is for, and U22 is the next task."
        ),
        sources=("cso.electricity.dbere101_by_dwelling_ber",
                 "cso.electricity.dbere102_by_dwelling_construction",
                 "cso.gas.dberng01_by_dwelling_ber",
                 "cso.gas.dberng02_by_dwelling_construction"),
        owning_step="U22, comfort-taking (week 2 step 3)",
        issue="K14",
    ),
    AssumptionFlag(
        flag_id="A-19", subject="purge ventilation and thermostat parameters",
        where=("physics/rc.py PURGE_*, THERMOSTAT_BAND_C",),
        assumed=(
            "window-opening threshold 24 C over a 4 C span to 3.0 ACH, and a "
            "1.5 C proportional thermostat band"
        ),
        retires_if="published Irish window-opening or thermostat-setting behaviour",
        search_terms=(r"ventilation", r"window", r"thermostat", r"heating hours"),
        verdict="WRONG_INSTRUMENT",
        verdict_note=(
            "Occupant control behaviour is not in a statistical catalogue. "
            "These values exist because I-032 (median 24.6 C, peak 64.3 C) "
            "proved there was no heat-removal path at all; the mechanism was "
            "the finding, and the thresholds are DEAP-informed declared "
            "values. PL-TEMP-01's band is the check that keeps them honest, "
            "and A-09 records that the band itself is unsourced."
        ),
        issue="I-032",
    ),

    # ---------------- weather ---------------- #
    AssumptionFlag(
        flag_id="A-20", subject="urban heat bias and Linke turbidity",
        where=("weather/site.py urban_heat_c, linke_turbidity",),
        assumed=(
            "a small urban warm bias for a town of 14,000, and a maritime "
            "Irish turbidity value"
        ),
        retires_if=(
            "a published Irish urban heat island measurement, or a published "
            "turbidity climatology for the site"
        ),
        search_terms=(r"turbidity", r"urban heat", r"solar radiation",
                      r"sunshine", r"global radiation"),
        verdict="KEPT",
        verdict_note=(
            "Zero hits for turbidity and urban heat. The catalogue does carry "
            "Met Eireann SUNSHINE duration by station, including MTH07 at "
            "hourly resolution, which is a genuine near-miss: sunshine hours "
            "constrain the solar driver without giving either assumed value. "
            "The hourly station data already declared (Roches Point, Cork "
            "Airport) is the better instrument for the same purpose and is "
            "what the weather layer uses."
        ),
        near_misses=("MTM03/MTM07/MTD07/MTH07 sunshine by station, MTH07 hourly",),
    ),

    # ---------------- traits and willingness ---------------- #
    AssumptionFlag(
        flag_id="A-21", subject="MIMIC trait priors",
        where=("population/traits.py TRAIT_PRIORS (eight evidence_tag='[A]')",),
        assumed=(
            "population distributions for the psychometric traits MIMIC "
            "profiles, until FlexSense data exists (design 5.2 step 5, K04)"
        ),
        retires_if="a published Irish population distribution for any trait",
        search_terms=(r"personality", r"psychometric", r"attitude",
                      r"well-?being", r"trust"),
        verdict="KEPT",
        verdict_note=(
            "Zero hits for personality and psychometric measures. The CSO "
            "publishes well-being and satisfaction scales, which are survey "
            "responses on different constructs from the trait battery MIMIC "
            "profiles, and mapping one to the other would be an assumption "
            "wearing a citation. The design already names the resolution: "
            "FlexSense data under K04/K15, with the priors flagged until then."
        ),
        near_misses=("WBA/WBB well-being and life-satisfaction scales - "
                     "different constructs",),
        issue="K04",
    ),
    AssumptionFlag(
        flag_id="A-22", subject="within-country trait dispersion",
        where=("population/traits.py (Hofstede dispersion)",),
        assumed="a dispersion around the national Hofstede score",
        retires_if="a published within-Ireland dispersion for the dimensions",
        search_terms=(r"Hofstede", r"cultural dimension", r"values survey"),
        verdict="WRONG_INSTRUMENT",
        verdict_note=(
            "Hofstede publishes country means and no within-country "
            "dispersion, as the code comment says, and the CSO publishes "
            "neither. The quantity does not exist in published form anywhere, "
            "which is a different situation from a gap the CSO might fill."
        ),
        issue="K04",
    ),
    AssumptionFlag(
        flag_id="A-23", subject="G-B willingness priors",
        where=("mimic/willingness.py", "v1/evidence/gb_willingness_spec_frozen.json"),
        assumed=(
            "demand-response willingness coefficients from cited literature, "
            "unvalidated until FlexSense data (K04, K15)"
        ),
        retires_if="published Irish household demand-response willingness",
        search_terms=(r"willing", r"demand response", r"flexibilit",
                      r"smart meter"),
        verdict="KEPT",
        verdict_note=(
            "The nearest Irish willingness data in the catalogue is NTA48/49/"
            "78/79: willingness to buy an electric vehicle, with nine "
            "influencing factors. Real, Irish, and a different construct - "
            "buying a car is not shifting a load in response to a price "
            "signal, and treating one as a prior for the other would be the "
            "I-040 mistake in reverse: citing a source that does not measure "
            "the quantity. The priors stay [A] with that distinction recorded."
        ),
        near_misses=("NTA48/NTA49/NTA78/NTA79 willingness to buy an EV - a "
                     "different construct",),
        issue="K04, K15",
    ),
    AssumptionFlag(
        flag_id="A-24", subject="sensor tier uptake correlated with traits",
        where=("population/buildings.py (tier uptake)",),
        assumed=(
            "tier uptake correlates with traits 'as it would in reality' "
            "(design's words)"
        ),
        retires_if="published Irish smart-device or monitoring uptake by household type",
        search_terms=(r"smart meter", r"internet of things", r"broadband",
                      r"smart device"),
        verdict="KEPT",
        verdict_note=(
            "The catalogue has ICT-usage tables (broadband and device access "
            "by household type) but nothing on home-monitoring or sub-metering "
            "uptake, which did not exist as a consumer category when those "
            "surveys were designed. The assumption's role is also narrow: tier "
            "assignment decides which homes are OBSERVED, and 6.5's "
            "observation rules and the leakage tests are what protect against "
            "it being wrong."
        ),
    ),

    # ---------------- life course ---------------- #
    AssumptionFlag(
        flag_id="A-25", subject="life-course event rates",
        where=("lifecourse/hazards.py", "lifecourse/tenyear.py"),
        assumed=(
            "every hazard in the ten-year life course - birth, death, "
            "partnering, employment change and the vacancy chain - declared "
            "because design 5.3 gives none"
        ),
        retires_if="published Irish transition rates for any of these events",
        search_terms=(r"Marriage Rate", r"[Ff]ertility [Rr]ate", r"age of mother",
                      r"[Dd]eath [Rr]ate", r"job churn", r"[Vv]acan"),
        verdict="RETIRED",
        verdict_note=(
            "Week 2 step 5 wired all of these in, so the flag is gone for the "
            "hazards it covered. Births come from VSA104's age-specific "
            "fertility rates by NUTS 3 region (South-West), split by parity "
            "from VSA36. Deaths come from VSA08 over PEA01 on the SAME age-"
            "band dimension code, which makes the rate a ratio of two "
            "published numbers rather than a mapping of ours. Partnering comes "
            "from VSA49 by single year of age. Employment change comes from "
            "JCA01, which publishes job churn - hirings and separations - by "
            "single year of age and sex; the census labour-force tables are "
            "stocks and give no transition rate at all. The vacancy chain is "
            "held by VAC17's gross flows, which balance at 0.965, and VAC04's "
            "Cork County rate. Two tables were fetched and REJECTED rather "
            "than used: CEPHA05, the only life table PxStat publishes, stops "
            "at 1990 and cannot age a 2022 population; C0674 is the 2006 "
            "census vintage. What remains assumed is split out as A-25b to "
            "A-25f, each with its own search record and published bound. "
            "I-053: the two sources this flag originally named were declared "
            "under crossed matrices and had never been read."
        ),
        sources=("cso.vitalstats.vsa49_marriage_rates_by_age",
                 "cso.vitalstats.vsa104_fertility_rates_by_age",
                 "cso.vitalstats.vsa36_births_by_age_and_parity",
                 "cso.vitalstats.vsa08_deaths_by_age_and_sex",
                 "cso.population.pea01_population_estimates_by_age_sex",
                 "cso.labour.jca01_job_churn_by_age_sex",
                 "cso.housing.vac17_vacancy_flows",
                 "cso.housing.vac04_local_authority_vacancy_rates",
                 "cso.housing.f2095_housing_stock_vacancy_by_ed"),
        owning_step="week 2 step 5, WP5 ten-year life course",
        issue="I-053",
    ),

    AssumptionFlag(
        flag_id="A-25b", subject="gross household turnover",
        where=(
            "lifecourse/hazards.py ASSUMED_HAZARDS A-25b",
            "lifecourse/move_rate.py (the sourced proxy)",
        ),
        assumed="a gross household out-move rate of 0.065 per household per year",
        retires_if=(
            "a published Irish gross in-migration or out-migration rate, as "
            "opposed to the net figure"
        ),
        search_terms=(r"internal migration", r"household formation",
                      r"usual residence", r"residence one year",
                      r"year before Census"),
        verdict="SOURCE_FOUND",
        sources=("cso.census.sap2022_usual_residence_one_year_ago_by_town",),
        owning_step=(
            "week 3 step 4 (U33). Wired into "
            "tenyear.vital_statistics_intervals, which now tests the "
            "move_out count against the Census interval rather than against "
            "the model's own declared rate."
        ),
        verdict_note=(
            "The earlier verdict was right about migration ESTIMATES and "
            "wrong about where else to look. EP006 publishes NET migration "
            "per 1,000 by county and PEB08 projects it; neither gives a gross "
            "flow, and a net rate of +0.6 per 1,000 (Cork, 2011-2016) is "
            "consistent with any pair of gross flows differing by that much, "
            "including zero and zero. All of that still holds.\n\n"
            "What it missed is that the quantity is also a CENSUS QUESTION. "
            "Every resident is asked where they usually lived one year before "
            "Census Day, and SAP2022 publishes the answer at TOWN level - so "
            "for Cobh itself, not for Cork County and not for the South-West. "
            "Cobh 2022: 13,008 of 13,843 residents aged 1+ at the same "
            "address a year earlier, so 835 moved, a person move rate of "
            "0.060319 per year. An intra-Cobh move is counted, because the "
            "question is about the previous ADDRESS and a previous address in "
            "Co Cork falls under 'Elsewhere in county'.\n\n"
            "Why the flag is NOT retired. The Census counts PEOPLE and the "
            "hazard is per HOUSEHOLD. For whole-household moves the two rates "
            "are equal; an individual move - leaving home, moving in with a "
            "partner - adds a person-move and not a household-move. So the "
            "person rate bounds the household rate from ABOVE, and the split "
            "between the two kinds of move is what remains unsourced. The "
            "flag's subject has therefore narrowed from 'no source exists' to "
            "'the person-to-household conversion', which is a much smaller "
            "assumption than the one it replaces.\n\n"
            "Two caveats recorded rather than corrected for: the question "
            "counts moves INTO the town and the hazard is a move OUT, which "
            "balance only in a stationary population; and the window is April "
            "2021 to April 2022, which included the tail of the Covid "
            "restrictions and so may understate the decade. VAC17's gross "
            "vacancy flows still bound the rate as before, and that bound is "
            "what holds the vacancy stock flat over ten years.\n\n"
            "Measured, and reported because it is not flattering: the model's "
            "declared 0.065 is 1.078x the Census rate, so the declared hazard "
            "sits ABOVE the upper bound the Census implies. It was not "
            "changed - nothing is fitted to this - and the observed count "
            "lands at 34 against 34.58 expected under the Census rate, inside "
            "its interval."
        ),
        near_misses=("EP006 net migration per 1,000 by county",
                     "PEB08 projected internal and international migration"),
        issue="I-065",
    ),

    AssumptionFlag(
        flag_id="A-25c", subject="union dissolution rate",
        where=("lifecourse/hazards.py ASSUMED_HAZARDS A-25c",),
        assumed="a separation rate of 0.009 per couple per year",
        retires_if="a published Irish separation or divorce transition rate",
        search_terms=(r"\bseparat", r"\bdivorce"),
        verdict="KEPT",
        verdict_note=(
            "Searching separation returns 20 tables and none of them is a "
            "relationship transition rate: CD565-568 are census STOCKS of the "
            "divorced and separated population, MIP21 carries European divorce "
            "rates whose Irish entries are the same stocks, and JCA03/JCA04 "
            "'Separations' are JOB separations. A stock is not a hazard. CD565 "
            "was fetched anyway and is used as a BOUND: the assumed rate has "
            "to be consistent with a divorced-and-separated share of 11.9 per "
            "cent at 45-54, which is a weaker claim than a sourced rate and is "
            "labelled as one."
        ),
        near_misses=("CD565 divorced and separated population (a stock)",
                     "MIP21 European divorce rates",
                     "JCA03 Separations - job separations, not relationship"),
    ),

    AssumptionFlag(
        flag_id="A-25d", subject="children leaving the parental home",
        where=("lifecourse/hazards.py ASSUMED_HAZARDS A-25d",),
        assumed=(
            "a leaving rate of 0.115 per resident child aged 18 to 34 per year"
        ),
        retires_if=(
            "a published hazard or an age-by-age stock of young adults living "
            "with parents, from which a hazard could be differenced"
        ),
        search_terms=(r"living with parents", r"leaving home"),
        verdict="KEPT",
        verdict_note=(
            "EA036 publishes a COUNT of persons aged 20 still living with "
            "parents, for 2011 and 2016 only, at that single age - 37,995 in "
            "2016. One age in two years cannot be differenced into a hazard "
            "over 18 to 34. 'leaving home' returns 82 tables, all of which are "
            "the census TIME LEAVING HOME question - what time of the morning "
            "people leave for work - which is a different thing entirely and "
            "is a good example of why a hit count is not evidence. EA036 is "
            "used as a weak bound: even its denominator is approximate, "
            "because PEA01's finest band is 20-24."
        ),
        near_misses=("EA036 population aged 20 still living with parents",
                     "CD002/CD006 'Time Leaving Home' - the wrong sense"),
    ),

    AssumptionFlag(
        flag_id="A-25e", subject="chronic health-state onset under 50",
        where=("lifecourse/hazards.py ASSUMED_HAZARDS A-25e",),
        assumed="an onset rate of 0.012 per person per year below age 50",
        retires_if="a published Irish chronic-condition prevalence below age 50",
        search_terms=(r"chronic", r"[Ll]ong.standing illness",
                      r"activity limitation"),
        verdict="KEPT",
        verdict_note=(
            "HSPAE122, the one chronic-condition prevalence found, is 'among "
            "people aged 50 and over' and begins there; its 2021 figures are "
            "64.8 per cent with one or more conditions and 29.2 per cent with "
            "two or more. At 50 and over the onset rate is therefore NOT "
            "assumed: it is set so the cohort builds to that published stock. "
            "Below 50 nothing was found - the 335 disability tables are census "
            "stocks by type of disability, which is a different construct from "
            "a chronic condition and carries no onset rate. ('disabilit' is "
            "recorded here as a near-miss rather than as a search term: it "
            "matches 335 tables, which is drowning rather than searching, so "
            "the terms run are the narrower ones.) The under-50 "
            "rate is assumed and the published 50+ prevalence is what the "
            "whole schedule has to arrive at."
        ),
        near_misses=("HSPAE122 multiple chronic conditions, 50 and over",
                     "HSPAE25 COPD in a pulmonary rehabilitation programme"),
    ),

    AssumptionFlag(
        flag_id="A-25f", subject="annual retrofit and DER adoption rate",
        where=("lifecourse/hazards.py ASSUMED_HAZARDS A-25f",),
        assumed="an adoption rate of 0.025 per dwelling per year, per measure",
        retires_if="a published Irish retrofit or DER installation RATE",
        search_terms=(r"retrofit", r"energy effic", r"\bgrant\b"),
        verdict="KEPT",
        verdict_note=(
            "'retrofit' returns ZERO tables out of 13,086 - the CSO does not "
            "publish under that word at all. 'energy effic' returns HEBEU37, "
            "which is the right subject in the wrong form: installations IN "
            "PLACE in 2024, by type (heat pump 11 per cent, PV 10, thermal "
            "solar 8, smart controls 16, battery 4, one or more 34). That is a "
            "PREVALENCE, so it fixes the cumulative ten-year total and not the "
            "annual hazard, and it is used as a cap that the run cannot exceed "
            "rather than as a rate. 'grant' returns only student-grant "
            "expenditure, so the SEAI grant route is not in PxStat either."
        ),
        near_misses=("HEBEU37 energy efficiency installations in place",),
    ),

    AssumptionFlag(
        flag_id="A-39", subject="disruption rates and durations",
        where=("lifecourse/events.py DISRUPTION_KINDS",),
        assumed=(
            "illness 2.0 primary episodes per person per year, remote work "
            "18.0 per worker, appliance failure 0.45 per household, unplanned "
            "visitors 11.0 per household, with their duration ranges"
        ),
        retires_if=(
            "published Irish rates for acute illness episodes, remote-working "
            "days, appliance failures or household visitors"
        ),
        search_terms=(r"remote work", r"work from home", r"acute illness",
                      r"appliance failure"),
        verdict="KEPT",
        verdict_note=(
            "These were covered by A-25 until week 2 step 5 narrowed A-25 to "
            "the life-course hazards it had actually sourced, which left the "
            "disruption rates without an entry of their own - caught by "
            "uncovered_files(), which is what that check is for. They are a "
            "different kind of quantity from a life-course hazard: a "
            "disruption is a short perturbation to a day, and design 5.3's "
            "acceptance test (R17) is that rates fall within cited ranges "
            "rather than that they match a national statistic. The illness "
            "rate already carries its own correction: an earlier version "
            "added household contagion on top of a survey total that already "
            "included it, producing 32.5 illness days per person-year against "
            "a real 8 to 12."
        ),
    ),

    AssumptionFlag(
        flag_id="A-40", subject="the setpoint of a vacant dwelling",
        where=("engine/run.py VACANT_FROST_SETPOINT_C",),
        assumed="a vacant home is held at 7 C frost protection",
        retires_if=(
            "a regulatory or published figure for the heating setpoint of an "
            "unoccupied Irish dwelling"
        ),
        search_terms=(r"frost protection", r"unoccupied dwelling",
                      r"[Ss]etpoint"),
        verdict="KEPT",
        verdict_note=(
            "WP5's ten-year life course produces vacancies, and a vacant house "
            "is still connected to the feeder, so the runner needs a setpoint "
            "for a dwelling with nobody in it. DEAP has no vacancy case: its "
            "demand model assumes an occupied dwelling throughout, so the "
            "regulatory anchor is silent rather than contradicted. The "
            "assumption is deliberately narrow - at 7 C a vacant Irish home "
            "draws almost nothing for most of the year, and the quantity it "
            "moves is a standing baseline rather than a peak, so the slice's "
            "load factor and peak are nearly insensitive to it."
        ),
    ),

    # ---------------- WP6 calendar and events (week 2 step 6) ---------------- #
    AssumptionFlag(
        flag_id="A-41", subject="school term dates and daily school absence",
        where=("engine/calendar_events.py ASSUMED_EVENT_RATES",),
        assumed=(
            "the 2022 Irish term dates as transcribed intervals, and a daily "
            "school-day absence probability of 0.07"
        ),
        retires_if=(
            "a published term calendar as data, or a published Irish DAILY "
            "school absence rate"
        ),
        search_terms=(r"[Ss]chool [Yy]ear|[Tt]erm dates", r"[Aa]bsent"),
        verdict="SOURCE_FOUND",
        verdict_note=(
            "SCA42 and SCA31 publish chronic absence - the share of children "
            "absent TWENTY DAYS OR MORE in a school year - which is not a "
            "daily rate but does put a floor under one: 21.8 per cent of Cork "
            "primary children missing at least 20 of about 183 days gives "
            "0.0238 from chronic absence alone, before any short absence, and "
            "the assumed 0.07 sits above that floor. UA16 'Enrolments by "
            "week' was fetched and DISCARDED: its weekly series turned out to "
            "be 15 irregular snapshot dates across several years, not an "
            "attendance series, so it cannot be differenced into a term "
            "calendar. Term DATES remain a transcription from Department of "
            "Education circulars, which are documents rather than statistics."
        ),
        sources=("cso.education.sca42_primary_absence_by_county",),
        owning_step="week 2 step 6, WP6 calendar and events",
        near_misses=("UA16 enrolments by week - snapshots, not a series",
                     "SCA31 secondary chronic absence"),
    ),

    AssumptionFlag(
        flag_id="A-42", subject="electricity outage frequency and duration",
        where=("engine/calendar_events.py ASSUMED_EVENT_RATES",),
        assumed=(
            "a quarter of storm days produce a local outage, lasting 1 to 6 "
            "hours"
        ),
        retires_if=(
            "a published Irish supply-interruption statistic - customer "
            "minutes lost, customer interruptions, or an outage duration "
            "distribution"
        ),
        search_terms=(r"electricity.*interrupt|[Mm]inutes [Ll]ost",
                      r"[Oo]utage", r"supply interruption"),
        verdict="WRONG_INSTRUMENT",
        verdict_note=(
            "Zero tables. Supply reliability is published by the regulator "
            "and the network operator, not the statistics office - the same "
            "split that put the standard load profiles at ESB Networks rather "
            "than in PxStat (I-043). What makes this assumption narrow is "
            "that only the CONDITIONAL probability is assumed: outages are "
            "generated FROM storm days, and the storm days come from the "
            "weather realisation, so the outage RATE inherits a sourced "
            "frequency. An outage drawn independently would put the lights "
            "out on a calm day, and a model that had learned the real "
            "storm-outage correlation would be penalised for being right."
        ),
    ),

    AssumptionFlag(
        flag_id="A-43", subject="local event programme - festivals, markets, sport, roadworks",
        where=("engine/calendar_events.py ASSUMED_EVENT_RATES",),
        assumed=(
            "six festival days, a market on 45 per cent of cruise calls, 34 "
            "sport fixtures and three roadworks spells a year"
        ),
        retires_if=(
            "a published calendar of Irish local events, markets, fixtures or "
            "roadworks as open data"
        ),
        search_terms=(r"[Ff]estival", r"roadwork", r"[Ss]port"),
        verdict="KEPT",
        verdict_note=(
            "Zero tables for 'festival' and zero for 'roadwork'. 'sport' "
            "matches 115 tables and not one is a fixture list or an "
            "attendance series: the matches are road freight TRANSPORT "
            "activity and travel tables, where 'sport' is a substring of "
            "'transport'. That is the clearest case in the whole sweep that a "
            "hit count is not evidence. What is NOT assumed is the timing: "
            "markets and festivals are generated from the cruise-call driver, "
            "whose seasonality comes from TBA11, and roadworks from the "
            "institutional-year driver, so only the frequencies are declared. "
            "The one locally distinctive event class - a cruise call into a "
            "town of three thousand people - is the one with a real source."
        ),
        near_misses=("TBA10/TBA11 cruise visits, which ARE sourced",),
    ),

    AssumptionFlag(
        flag_id="A-44", subject="the safety layer's occupant floor and envelope dynamics",
        where=("engine/coupling.py VULNERABLE_MIN_C",
               "engine/coupling.py ENVELOPE_TIGHTEN_PER_15_MIN"),
        assumed=(
            "an 18 C living-zone floor for a home with a vulnerable occupant, "
            "and envelope tightening and relaxation rates for step 6 of the "
            "8.2 timing contract"
        ),
        retires_if=(
            "a published Irish minimum indoor temperature for vulnerable "
            "occupants, or a published network-envelope policy"
        ),
        search_terms=(r"indoor temperature", r"[Ss]etpoint",
                      r"frost protection"),
        verdict="KEPT",
        verdict_note=(
            "The temperature floor is the same gap I-032 and PL-TEMP-01 "
            "already record: no CSO or SEAI table publishes measured Irish "
            "indoor temperatures. 18 C is the WHO housing and health "
            "guideline minimum, which is a published GUIDELINE - a document, "
            "not a statistic - and its job here is to refuse the unsafe "
            "rather than to calibrate. The envelope dynamics are not "
            "published by anyone: design 8.2 says the envelope 'tightens "
            "automatically' and names no rate. What matters more than the "
            "values is that both are expressed per unit of TIME rather than "
            "per epoch: a per-epoch rate made C2, with 1440 epochs a day "
            "against C1's 96, tighten up to fifteen times as hard for the "
            "same physical violations, so the two coupling modes differed by "
            "epoch counting rather than by staleness and the coupling-lag "
            "test measured nothing. The staleness MARGIN itself is not "
            "assumed: it comes from LP1's measured maximum quarter-hour ramp."
        ),
        near_misses=("esbn.rmds.slp_indexes_2022 - sources the margin, "
                     "not the floor or the dynamics",),
    ),

    # ---------------- commuting ---------------- #
    AssumptionFlag(
        flag_id="A-26", subject="POWSCAR commuting microdata substitute",
        where=("sources.py (POWSCAR row in the substitutes table)",),
        assumed=(
            "the public SAPS travel-to-work marginals stand in for POWSCAR's "
            "origin-destination microdata (U04, 5.2 step 4)"
        ),
        retires_if="POWSCAR becoming public, which would end the substitution",
        search_terms=(r"travel to work", r"POWSCAR", r"place of work"),
        verdict="WRONG_INSTRUMENT",
        verdict_note=(
            "POWSCAR is restricted microdata by construction - its value is "
            "individual origin-destination records, which is exactly what "
            "cannot be published. The catalogue's travel-to-work tables are "
            "the aggregate form, and SAPS 2022's are already declared and "
            "used at small-area level for Cobh. The substitution is permanent "
            "and correctly flagged."
        ),
        issue="U04",
    ),

    # ---------------- the three unsourced plausibility families ---------------- #
    AssumptionFlag(
        flag_id="A-27", subject="appliance share of household electricity",
        where=("plausibility/checks.py PL-APPLSHARE-01",),
        assumed="no band declared; the check reports UNSOURCED",
        retires_if="a machine-readable Irish end-use electricity breakdown",
        search_terms=(r"end.?use", r"electricity consum", r"appliance"),
        verdict="KEPT",
        verdict_note=(
            "Confirms the check's own note against the full catalogue. PxStat "
            "publishes appliance ownership and total household electricity, "
            "never electricity BY appliance. SEAI's residential reports carry "
            "an end-use breakdown as narrative PDF tables, which cannot be "
            "registered as a source and read at run time under the brief's "
            "rules. The check stays declared-unsourced rather than being given "
            "a band from memory."
        ),
        issue="I-039",
    ),
    AssumptionFlag(
        flag_id="A-28", subject="EV charging and heat-pump kWh per dwelling",
        where=("plausibility/checks.py PL-EVHP-01",),
        assumed="no band declared; the check reports UNSOURCED",
        retires_if="published domestic kWh for EV charging or heat pumps",
        search_terms=(r"electric vehicle", r"heat pump", r"charge point|charging"),
        verdict="KEPT",
        verdict_note=(
            "The check's note already named NTA43-49, MEC08 and EBQ02, and the "
            "sweep confirms the shape of the gap: the CSO publishes EV "
            "OWNERSHIP by age and sex (NTA43, NTA76), willingness to buy "
            "(NTA48/49), public charge-point consumption (MEC08) and heat-pump "
            "penetration (EBQ02) - and no domestic kWh for either. Ownership "
            "is not consumption. DBEREL01's A-B cells remain the indirect "
            "check, which PL-ELEC-01 exercises."
        ),
        issue="I-039",
    ),
    AssumptionFlag(
        flag_id="A-29", subject="aggregate (after-diversity) load factor and shape",
        where=("plausibility/checks.py PL-PEAK-01", "plausibility/slp.py"),
        assumed="no band declared; the check reported UNSOURCED",
        retires_if=(
            "a published Irish domestic load profile or load factor, at any "
            "level of aggregation"
        ),
        search_terms=(r"peak demand", r"peak load", r"maximum demand",
                      r"load factor", r"\bADMD\b", r"after diversity"),
        verdict="RETIRED",
        verdict_note=(
            "Zero hits for every phrasing across 13,086 tables, so PxStat is "
            "not where this lives - and that negative result is what sent the "
            "search to the network operator, where it is published in full. "
            "ESB Networks' Standard Load Profile LP1, Urban Domestic 24 Hour, "
            "gives a Demand Energy Coefficient for every quarter-hour of the "
            "year, unitised to sum to 1.0, so the load factor falls out with "
            "no borrowed denominator: 0.4129 for 2022, with an annual peak "
            "2.422x the mean, a mean-day peak at 18:00 and a trough at 04:00. "
            "The 2022 vintage is taken because T0 is 2022 and a profile is "
            "re-derived annually from measured data. PL-PEAK-01 is now sourced "
            "and evaluable, and it FAILS on the overnight taper (I-044): the "
            "simulated town is flat from midnight to 04:00 where LP1 falls by "
            "a factor of 1.72. Its load factor and evening peak hour pass. "
            "That failure is the check working."
        ),
        sources=("esbn.rmds.slp_indexes_2022",),
        issue="I-039, I-043, I-044",
    ),
    # ---------------- U25: hot water, cooking ---------------- #
    AssumptionFlag(
        flag_id="A-31", subject="hot water draw volumes",
        where=("data/deap_hot_water.yaml assumptions",
               "physics/dhw.py draw_for_activity"),
        assumed=(
            "bath volume, hand-wash, washing-up and kitchen-tap draws, and "
            "the delivered and cold-feed temperatures"
        ),
        retires_if="published Irish per-event hot water volumes",
        search_terms=(r"hot water", r"water heating", r"\bimmersion\b",
                      r"water consumption|water usage"),
        verdict="KEPT",
        verdict_note=(
            "Zero hits for hot water, water heating and immersion across all "
            "13,086 tables. DEAP is the reference for everything else in this "
            "subsystem, and for these it asks the assessor for manufacturers' "
            "product data - bath capacity to overflow, tap flow rates - and "
            "publishes no default. So they are declared, and the one published "
            "bound that does exist is used as a check rather than ignored: "
            "DEAP's water-efficiency target of 125 litres per person per day "
            "for ALL water bounds hot water from above, because hot water is a "
            "subset of it. PL-DHW-01 measures 69 against that 125."
        ),
        issue="I-045",
    ),
    AssumptionFlag(
        flag_id="A-32", subject="minutes a shower's water runs",
        where=("data/deap_hot_water.yaml shower_water_minutes_median",
               "physics/dhw.py shower_water_minutes"),
        assumed=(
            "the water runs for a median 7.5 minutes, capped at 15 and by the "
            "length of the bathroom episode"
        ),
        retires_if="a published Irish or UK shower duration",
        search_terms=(r"\bshower\b", r"hot water"),
        verdict="KEPT",
        verdict_note=(
            "The single assumption the whole hot water volume turns on, and "
            "the one that went wrong first. DEAP publishes the FLOW RATE - a "
            "minimum of 6 L/min on every mixer shower - and takes the "
            "DURATION as an assessor input, so there is no default to use. "
            "The activity engine gives time in the bathroom, which is a "
            "different quantity: charging 6 L/min across a 25-minute bathroom "
            "episode made 150-litre showers and about 800 litres a day per "
            "household. Bounded from two sides rather than fitted - PL-DHW-01 "
            "against DEAP's per-person water target above, and the gas meter "
            "below, since DBERNG01 contains hot water and the meter "
            "comparison comes in at 0.841 of the published cell rather than "
            "over it. I-045 records that the claim is no stronger than that."
        ),
        issue="I-045",
    ),
    AssumptionFlag(
        flag_id="A-33", subject="share of dwellings that cook with gas",
        where=("physics/dhw.py cooking_fuel_shares",),
        assumed=(
            "was a declared 45% of gas-connected dwellings; now derived from "
            "published data"
        ),
        retires_if="a published Irish cooking-fuel split",
        search_terms=(r"cooking", r"\bcooker\b|\bhob\b|\boven\b"),
        verdict="RETIRED",
        verdict_note=(
            "The I-040 lesson landing a THIRD time, and the first time a "
            "mechanism caught it instead of a person. The earlier sweep "
            "searched `cooking fuel` and `gas cooking` and concluded nothing "
            "was published; the CSO's tables are titled 'Main fuel used for "
            "COOKING in households', so the words are there in the other "
            "order and a phrase search missed them. What found them was the "
            "coverage test: U25 added three [A] flags, the test demanded sweep "
            "entries, the entries demanded search terms, and the plain term "
            "`cooking` matched six tables. "
            "HEBEU34 gives the urban cooking-fuel split and HEBEU106 the "
            "urban heating-fuel split from the same survey, so the share "
            "conditional on a gas connection is derived rather than assumed: "
            "14% of urban households cook with gas alone and 9% with a "
            "combination, against 48% heating with gas, giving 0.292 and "
            "0.188 of gas-connected dwellings. The declared 0.45 it replaced "
            "was close, which is reassuring and not the point. The three-way "
            "split is the gain: 'combination' is a gas hob with an electric "
            "oven, which the model now assigns as such. Two caveats are "
            "recorded with the derivation - the denominator is gas HEATING, a "
            "lower bound on connections, so the shares are upper bounds; and "
            "the tables are 2024 against a T0 of 2022, so they are used for a "
            "structural share and not a level."
        ),
        sources=("cso.cooking.hebeu34_cooking_fuel_urban_rural",
                 "cso.cooking.hebeu106_heating_fuel_urban_rural"),
        issue="I-040, I-046",
    ),
    AssumptionFlag(
        flag_id="A-34", subject="gas versus electric cooking efficiency",
        where=("data/deap_hot_water.yaml gas_cooking",
               "physics/boiler.py gas_cooking_fuel_kwh"),
        assumed=(
            "pan-side efficiencies of 0.74 electric against 0.40 gas on the "
            "hob, and 0.80 against 0.50 in the oven"
        ),
        retires_if="published hob and oven efficiencies",
        search_terms=(r"\bcooker\b|\bhob\b|\boven\b",
                      r"appliance efficiency"),
        verdict="KEPT",
        verdict_note=(
            "The CSO publishes which fuel households cook WITH (A-33, now "
            "retired) and not how efficiently the appliance uses it, and DEAP "
            "is silent because cooking is outside its primary-energy boundary "
            "- which data/ber_bands.yaml already records. But the gas METER "
            "sees cooking, because DBERNG01 is a meter reading, so it cannot "
            "be left out. The assumption is kept as narrow as it can be: the "
            "model re-delivers the useful cooking energy the appliance layer "
            "has already sized, at a burner's efficiency, so what is declared "
            "is a single RATIO rather than a new annual energy invented from "
            "nothing. A flame loses heat around the pan and a gas oven vents "
            "its combustion products; the direction is not in doubt."
        ),
    ),
    # ---------------- U22: comfort-taking ---------------- #
    AssumptionFlag(
        flag_id="A-35", subject="heating affordability by income and tenure",
        where=("behaviour/comfort_taking.py AFFORDABILITY_BY_QUINTILE",
               "behaviour/comfort_taking.py TENURE_AFFORDABILITY_SHIFT"),
        assumed=(
            "headroom to pay for warmth, 0.20 to 0.90 across income "
            "quintiles, shifted by tenure and economic status"
        ),
        retires_if=(
            "a published mapping from Irish income or socio-economic group to "
            "heating affordability"
        ),
        search_terms=(r"fuel poverty", r"adequately warm",
                      r"deprivation", r"afford"),
        verdict="KEPT",
        verdict_note=(
            "Zero hits for `fuel poverty`, `adequately warm` and `warm`. The "
            "only `deprivation` tables in the catalogue are "
            "education-participation ones (AES16, AES21, AES24, AES29, AES34, "
            "by Levels of Deprivation), which are about something else "
            "entirely. "
            "An earlier draft of this note asserted that Ireland publishes "
            "fuel poverty through SILC - inability to afford to keep the home "
            "adequately warm - and that assertion was NOT supported by the "
            "search beside it. It may well be collected; it is not "
            "discoverable in PxStat under any of these terms, and after I-046 "
            "the difference between 'not published' and 'not found by the "
            "words I tried' is exactly what a sweep entry is for. So: not "
            "found, terms recorded, and the next searcher should try others. "
            "What is defensible is the "
            "ORDERING, which is why the values are spaced evenly rather than "
            "fitted: the claim is that prebound falls as means rise, and the "
            "ablation tests whether the claim earns its place rather than "
            "whether the numbers are right. Keyed on the income quintile the "
            "population layer already derives from SAPS, not on a second "
            "mapping - an earlier version carried its own socio-economic-group "
            "table which was both a duplicate and, because the SAPS labels "
            "are letter-prefixed, silently matched nothing."
        ),
        issue="I-048",
    ),
    AssumptionFlag(
        flag_id="A-36", subject="comfort-taking amplitudes",
        where=("behaviour/comfort_taking.py ComfortTakingSpec",),
        assumed=(
            "degrees of setpoint per log unit of cost advantage, the share of "
            "the heating window gained or given up, and how much of the "
            "sleeping zone a prebounding household abandons"
        ),
        retires_if=(
            "a published Irish rebound or prebound elasticity, or the "
            "mechanism reproducing DBERNG01's flatness at a fitted strength"
        ),
        search_terms=(r"rebound", r"prebound", r"indoor temperat"),
        verdict="KEPT",
        verdict_note=(
            "Declared and deliberately NOT fitted. DBERNG01 is the declared "
            "calibration axis so fitting would have been permitted, but the "
            "mechanism saturates at a 45% BER spread against a 4-7% target "
            "(I-048), so a fitted strength would buy the appearance of "
            "calibration and a kelvin of indoor temperature and nothing else. "
            "The sweep is published beside the declared values instead, in "
            "`v1/evidence/ablation_u22.json`, so a reader can see what each "
            "strength costs. Zero hits for indoor temperature confirms there "
            "is no Irish measurement to anchor the consequence against "
            "either (A-09)."
        ),
        issue="I-048",
    ),
    AssumptionFlag(
        flag_id="A-37", subject="boiler service life",
        where=("physics/boiler.py BOILER_MEAN_LIFE_YEARS",),
        assumed="a mean service life of 19 years before replacement",
        retires_if="a published Irish boiler age or replacement-rate distribution",
        search_terms=(r"\bboiler\b", r"heating system age"),
        verdict="KEPT",
        verdict_note=(
            "Twelve hits for `boiler`, and every one is about the FUEL burned "
            "in an open fire or stove with a back boiler (HEBEU13-24). The CSO "
            "publishes what households heat WITH - HEBEU06 and HEBEU103-108, "
            "main fuel or energy source used to heat the home, now declared "
            "for the cooking derivation - and nothing about how old the "
            "appliance is. DEAP takes the boiler from the assessment rather "
            "than modelling its replacement. The DIRECTION is not in doubt: "
            "boilers are replaced and dwellings are not, which is the whole "
            "of I-047. The consequence of the exact figure being wrong is "
            "bounded, because any service life under about 45 years puts a "
            "pre-1980 dwelling on a post-1998 boiler, which is the Table 4b "
            "row that matters."
        ),
        issue="I-047",
    ),
    AssumptionFlag(
        flag_id="A-38", subject="sleep-timing spread and tail",
        where=("activity/sleep_timing.py",
               "activity/engine.py _sleep_window"),
        assumed=(
            "the dispersion of bedtimes and wake times, transferred from the "
            "UK donor; the medians are Irish and not assumed"
        ),
        retires_if="an Irish time-use survey with sleep start times",
        search_terms=(r"time use", r"time-use", r"\bsleep\b"),
        verdict="KEPT",
        verdict_note=(
            "A-01's UK-donor flag, inherited by a specific parameter - but the "
            "parameter improved under it. Before U32 the bedtime spread was "
            "INVENTED: a standard deviation of 35 minutes on the sleep "
            "duration, giving a 10-to-90 range of 106 minutes and no right "
            "tail, which is why nobody in the town was ever awake at 01:00. "
            "It is now MEASURED from HETUS UK's share asleep by time of day "
            "(code AC0A): a 187-minute range with a tail past 02:50. So the "
            "flag stays because Ireland is in neither HETUS wave (I-008, "
            "A-01) and the donor is still the UK, not because the number is "
            "still a guess. "
            "What is transferred is a DISPERSION and not a level: the wake "
            "median stays anchored to Cobh's Census travel-to-work tables and "
            "the commute to its departure bands, and where the two sources "
            "meet the Irish one binds - the Census cap damps the UK spread by "
            "a derived 0.732 rather than the UK spread overruling the Census "
            "(D-056). Validated against the donor curve itself at a mean "
            "absolute deviation of 0.0283 on the mixed-age slice."
        ),
        issue="I-051, U32",
    ),
    AssumptionFlag(
        flag_id="A-30", subject="an individual dwelling's peak and load factor",
        where=("plausibility/slp.py (what_is_still_unsourced)",),
        assumed=(
            "no band declared for a single household's peak; only the "
            "after-diversity aggregate is checked"
        ),
        retires_if="a public Irish per-dwelling metered peak",
        search_terms=(r"peak demand", r"\bADMD\b", r"after diversity",
                      r"smart meter"),
        verdict="KEPT",
        verdict_note=(
            "The half of I-039 that LP1 does not close, and the distinction "
            "matters: LP1 is the aggregate of a whole customer class, which "
            "is the right instrument for feeder loading and the wrong one for "
            "one dwelling. A single household's peak is a kettle and a shower "
            "coinciding, and measuring it needs smart-meter or sub-metered "
            "microdata. In Ireland that means CER/ISSDA, which the brief "
            "forbids, so this is not a gap a search can close. Recorded so "
            "that PL-PEAK-01's after-diversity result is never read as a "
            "per-dwelling one."
        ),
        issue="I-043",
    ),

    # ---------------- week 3: what a retrofit MEASURE does ---------------- #
    # A-15 is retired, so the fabric's LEVEL is sourced. A-45 to A-47 are a
    # different question that the same source cannot answer: what changes when
    # a measure is installed. The user's constraint is recorded verbatim in
    # DECISIONS D-072 - retrofit-state shares "must come from a source ... or
    # be flagged [A] with a search record" and "never chosen to close the U31
    # gradient" - so each of these names the published quantity it DOES use and
    # isolates the one declared number that is left.
    AssumptionFlag(
        flag_id="A-45", subject="loft insulation depth a fabric retrofit installs",
        where=("physics/retrofit.py RETROFIT_LOFT_DEPTH_MM",),
        assumed=(
            "a cavity-and-attic retrofit tops the loft up to 300 mm, the depth "
            "the current Irish grant schemes specify"
        ),
        retires_if=(
            "a published distribution of installed loft-insulation depths "
            "under the Irish retrofit grant schemes"
        ),
        search_terms=(r"insulation", r"\battic\b", r"\bloft\b", r"retrofit",
                      r"energy efficiency.*grant"),
        verdict="KEPT",
        verdict_note=(
            "The U-VALUE is DEAP's, not assumed: Table S4 publishes the roof "
            "U-value for each observed insulation thickness, and at >=300 mm it "
            "is 0.13 W/m2K. Only the DEPTH is declared, and it is declared at "
            "the grant standard rather than chosen - the alternative depths "
            "DEAP publishes were not swept for the one that moved U31, which "
            "D-072 forbids. PxStat carries SEAI grant COUNTS by scheme and "
            "year, which say how many homes were insulated and not to what "
            "depth; the depth is an installation specification, not a "
            "statistic."
        ),
        near_misses=(
            "SEAI grant statistics - counts of homes upgraded by scheme, not "
            "the specification installed",
        ),
        issue="I-054",
    ),
    AssumptionFlag(
        flag_id="A-46", subject="floor area an extension adds",
        where=("physics/retrofit.py EXTENSION_FLOOR_AREA_SHARE",),
        assumed="an extension adds 0.18 of the original floor area",
        retires_if=(
            "a published distribution of Irish domestic extension sizes, or "
            "planning-permission floor areas for domestic extensions"
        ),
        search_terms=(r"extension", r"planning permission", r"floor area",
                      r"\bdwelling size\b"),
        verdict="KEPT",
        verdict_note=(
            "The added fabric's U-VALUES are DEAP Table S2's band L row - new "
            "work meets the current regulations, which is a regulatory fact "
            "rather than a choice. The AREA is declared. PxStat publishes "
            "planning permissions for extensions as COUNTS and new-dwelling "
            "floor areas (and TRS05, declared, for rental floor area), but "
            "nothing that gives the size of an extension to an existing home. "
            "Recorded with its direction of effect measured rather than "
            "argued: an extension both adds envelope and dilutes specific "
            "loss, and the decade's thirteen extensions came out at HLC "
            "ratios 1.051 to 1.080 in v1/evidence/wp5_tenyear.json."
        ),
        near_misses=(
            "planning permission tables - counts of extensions, no floor area",
            "TRS05 median floor area of rental properties - whole dwellings",
        ),
        issue="I-054",
    ),
    AssumptionFlag(
        flag_id="A-47", subject="which measures a fabric retrofit comprises",
        where=("physics/retrofit.py (module docstring, scope)",),
        assumed=(
            "a fabric retrofit means cavity fill plus attic insulation; "
            "windows and floors are left alone"
        ),
        retires_if=(
            "a published breakdown of measure COMBINATIONS per upgraded Irish "
            "home, rather than measure counts"
        ),
        search_terms=(r"retrofit", r"energy efficiency.*upgrade",
                      r"\bwall insulation\b", r"\bglazing\b"),
        verdict="KEPT",
        verdict_note=(
            "A scope choice, not a quantity, and the most consequential of the "
            "three: it decides how much of the envelope moves. Declared at the "
            "combination the Irish grant schemes mostly fund. SEAI publishes "
            "grant counts BY MEASURE, which gives marginal prevalence per "
            "measure and not the joint distribution a combination needs, so "
            "the catalogue cannot settle it. The honest consequence is stated "
            "rather than hidden: the eight decade retrofits moved HLC by "
            "ratios 0.754 to 0.958, and a retrofit that also replaced windows "
            "would move it further."
        ),
        near_misses=(
            "SEAI grant statistics by measure - marginals, not the joint "
            "distribution of measures per home",
        ),
        issue="I-054",
    ),
    AssumptionFlag(
        flag_id="A-48", subject="the emitter a converted heat pump is connected to",
        where=(
            "physics/deap_controls.py RETROFIT_KEEPS_STANDARD_RADIATORS",
            "physics/passport_assets.py apply_heat_pump_retrofit",
        ),
        assumed=(
            "a heat pump retrofitted into an existing dwelling keeps that "
            "dwelling's standard radiators, so DEAP Table 4c(4)'s "
            "standard-radiator branch applies rather than its underfloor or "
            "low-temperature branch"
        ),
        retires_if=(
            "a published breakdown of what emitters Irish heat-pump retrofits "
            "are installed onto - radiators kept, radiators resized, or "
            "underfloor added"
        ),
        search_terms=(r"heat pump", r"\bradiator", r"underfloor",
                      r"heating system", r"retrofit"),
        verdict="KEPT",
        verdict_note=(
            "The MAGNITUDE is DEAP's and the branch is the assumption, which "
            "is the opposite way round from most entries here and worth "
            "saying: Table 4c(4) publishes 1.0 for underfloor or warm air, "
            "0.85 for fan-coil or low-temperature radiators, 0.70 for "
            "standard radiators without compensation and 0.75 with. Nothing "
            "is invented; the question is which published row a converted "
            "dwelling belongs in.\n\n"
            "Declared at 0.70, which is DEAP's WORST branch, and deliberately "
            "so: of the four it is the only one that cannot flatter the "
            "measure, and it is the physically right answer for the measure "
            "WP5 actually models - a fabric retrofit does not resize "
            "radiators. The alternative choices all make a heat-pump "
            "conversion look better, so this is the branch that cannot be "
            "accused of having been chosen for its effect (D-072).\n\n"
            "PxStat publishes heat-pump COUNTS - HEBEU37 prevalence, already "
            "declared and used to bound WP5's adoption rate, and EBQ02's "
            "heat-pump share of new BER assessments - but no table reaches "
            "the emitter a heat pump is connected to. That is installation "
            "detail recorded on a BER assessment, not a published statistic."
        ),
        near_misses=(
            "HEBEU37 - heat-pump prevalence, declared and used; says how many "
            "homes have one, not what it is plumbed into",
            "EBQ02 - heat-pump share of new BER assessments, declared and used",
        ),
        issue="I-062",
    ),

    # ---------------- week 3: S11 network and WP7 venues ---------------- #
    AssumptionFlag(
        flag_id="A-49", subject="the town's LV network topology",
        where=(
            "network/lv.py TOPOLOGY_A_FLAGS",
            "config/e1_scope.yaml town_scaleup.what_is_not_claimed",
            # I-093. D01 exported provenance strings cite this flag on
            # the feeder and transformer rows, because the topology those
            # rows describe IS the assumption. The sweep walks the tree
            # for "[A]" and had no entry naming the file, so a correct
            # citation read as an unaccounted flag.
            "export/structural.py D01 feeder and transformer provenance",
        ),
        assumed=(
            "24 connections per LV feeder, a 300 m feeder span, a 15 m "
            "service drop and a power factor of 0.98"
        ),
        retires_if=(
            "ESB Networks publishes the LV circuit layout for Cobh, or any "
            "dataset giving connections per circuit and circuit lengths"
        ),
        search_terms=(r"\bnetwork\b.*\blow voltage\b", r"\bfeeder\b",
                      r"\bsubstation\b", r"distribution network",
                      r"\bcable\b"),
        verdict="KEPT",
        verdict_note=(
            "Every ELECTRICAL parameter is sourced and only the GEOMETRY is "
            "assumed, which is the opposite way round from most entries here "
            "and is what decides which network results may be reported. "
            "Cable resistance, reactance and thermal rating and transformer "
            "rating, vk, vkr, pfe and i0 are pandapower standard-type "
            "catalogue values - NAYY 4x150 SE, NAYY 4x50 SE, 0.4 and 0.63 MVA "
            "20/0.4 kV - and not one impedance is written in this build. The "
            "voltage limits are EN 50160 and the ESB Networks Distribution "
            "Code, 230 V +/-10%. The loading limit is 100% of a thermal "
            "rating, which is the definition of a rating.\n\n"
            "What the flag therefore restricts, and this is the load-bearing "
            "part: TRANSFORMER AND FEEDER LOADING may be claimed, because it "
            "is a ratio of powers and is insensitive to how connections are "
            "arranged on a circuit - a 400 kVA substation serving 40 homes "
            "sits at the same loading whether they are on one circuit or "
            "four. VOLTAGE may not, because voltage drop is a line integral "
            "along exactly the declared quantities. "
            "lv.assert_voltage_is_not_a_claim() raises unconditionally rather "
            "than leaving that to a docstring.\n\n"
            "PxStat carries no network asset data of any kind: it is an "
            "operator's own asset register, not a statistic, and no "
            "statistical catalogue would hold it. The remedy is ESB Networks "
            "directly, not a search."
        ),
        near_misses=(
            "nothing. PxStat publishes metered electricity by tariff group "
            "(MEC05, declared and used) and BER-linked consumption, which are "
            "demand statistics and say nothing about circuits",
        ),
        issue="I-039",
    ),
    AssumptionFlag(
        flag_id="A-50", subject="how many venues the town has, and where",
        where=(
            "population/venues.py SITING_A_FLAGS",
            "population/venues.py VENUE_TYPES (capacity_note)",
            "validation/venue_presence.py (capacity is [A]; consistency is not)",
        ),
        assumed=(
            "workplace capacity 25, shop 60, community 120, sports 80; one "
            "venue per small area in round-robin order; secondary-school size "
            "taken at the published PRIMARY mean"
        ),
        retires_if=(
            "a published register of Irish schools, workplaces or community "
            "facilities by town with capacities - the Department of "
            "Education's school list for schools, or a CSO table of "
            "workplaces by size for a town"
        ),
        search_terms=(r"\bschool", r"\bpupils?\b", r"\benrol",
                      r"place of work", r"workplace"),
        verdict="SOURCE_FOUND",
        sources=("cso.education.eda49_schools_and_pupils_by_teacher_size",),
        owning_step=(
            "week 3 WP7. EDA49 is wired into population/venues.py and sizes "
            "the school venues; the remaining declared quantities are the "
            "non-school capacities and the siting."
        ),
        verdict_note=(
            "School SIZE is sourced and that is the part that mattered. EDA49 "
            "publishes the number of national schools AND the number of "
            "pupils in them, both by teacher size of school, so the ratio is "
            "a published mean enrolment - 173.2 at the latest year. A venue "
            "whose capacity was invented could be made consistent with any "
            "attendance by choosing the capacity, so the week-3 criterion "
            "'venue presence consistent with person presence' would have been "
            "worthless without it.\n\n"
            "The venue COUNTS are DERIVED and not declared: the town's own "
            "demand divided by the venue type's size. That is deliberate - a "
            "declared count makes venue occupancy a free parameter, where too "
            "few venues puts every one over capacity and too many makes the "
            "criterion pass trivially - so there is nothing here to tune and "
            "over-capacity is a finding.\n\n"
            "What stays declared: the non-school capacities and the siting. "
            "Each is declared in the CONSERVATIVE direction and the direction "
            "is recorded beside the value, because a declared number that "
            "made the criterion EASIER would be a declared number doing the "
            "work of a result. A smaller workplace means more of them and "
            "tighter capacity; the secondary-school size is taken at the "
            "primary mean although Irish second-level schools are larger, "
            "which yields more schools and tighter capacity again.\n\n"
            "PxStat has no register of individual schools - that is the "
            "Department of Education's - and no table of workplaces by size "
            "for a town. The siting affects no claim that is made: a TRAVEL "
            "DISTANCE claim would depend on it and is not made, while the "
            "consistency criterion compares two records of the same presence."
        ),
        near_misses=(
            "EDA51 mainstream national schools and pupils in ordinary classes "
            "- the same quantity by a different cut, no extra information "
            "about capacity",
            "EDA03/EDA99 third-level enrolments - national totals; would bear "
            "on a college venue, which is not built (see I-069)",
        ),
        issue="I-069",
    ),

    # ---------------- week 3: 6.4's non-sensor observation models ------- #
    AssumptionFlag(
        flag_id="A-51", subject="reporting-error and non-response rates for D28 to D31",
        where=("observation/nonsensor.py PLANTED_RATES",),
        assumed=(
            "seventeen declared rates: survey unit and item non-response, "
            "straightlining, appliance omission, don't-know on PV, occupancy "
            "overstatement, social-desirability inflation, BER staleness, "
            "missing record fields, unit-transcription errors, assets since "
            "removed, source conflicts, sensor-consent refusal, panel "
            "attrition, reason-given-on-withdrawal, arm deviation and station "
            "outage"
        ),
        retires_if=(
            "published Irish survey-methodology and administrative-data "
            "quality evidence giving these rates - a response-rate table, a "
            "study of householder appliance misreporting, or a measured BER "
            "staleness rate"
        ),
        search_terms=(r"response rate", r"non-?response", r"survey method",
                      r"data quality", r"\bsurvey\b.*\bquality\b"),
        verdict="KEPT",
        verdict_note=(
            "Design 6.5 names this flag itself: 'Error rates are calibrated "
            "against survey-methodology and administrative-data quality "
            "evidence where available, and flagged [A] where not.' They are "
            "not available, so they are flagged.\n\n"
            "What the search found. The CSO publishes response rates for its "
            "OWN surveys - SILC, the Household Budget Survey, the LFS - in "
            "methodology notes attached to releases rather than as PxStat "
            "tables, so they are not machine-readable and they are rates for "
            "a statutory survey rather than for a voluntary in-home sensing "
            "study, which is a different instrument with a different refusal "
            "profile. Nothing published anywhere in the catalogue gives the "
            "rate at which Irish householders misreport an appliance, or the "
            "rate at which a BER record is stale.\n\n"
            "What is NOT assumed, and this is the part that matters for a "
            "reader deciding how much to trust the datasets: every rate's "
            "DIRECTION is evidence-based and stated beside it, and three are "
            "SIGNED claims rather than magnitudes - occupancy is overstated, "
            "environmental behaviour is inflated, appliances are omitted and "
            "never invented. A generator that applied symmetric noise instead "
            "would satisfy a magnitude test and fail the signed ones in "
            "tests/test_nonsensor_65_rules.py.\n\n"
            "And every rate is RECOVERABLE: 6.5 rule 3's test re-estimates "
            "each one from the emitted data and fails if it does not come "
            "back. So the magnitudes are declared, visible and checked, which "
            "is the most that can be said for a quantity nobody publishes."
        ),
        near_misses=(
            "CSO survey methodology notes - response rates for statutory "
            "surveys, in prose on release pages rather than in tables, and "
            "for a different instrument from a voluntary sensing study",
        ),
        issue="I-072",
    ),
)


# --------------------------------------------------------------------------- #
# Claims that are machine-checkable.
#
# A verdict note saying "zero hits" is prose, and prose does not fail when the
# CSO publishes something next year. These are the same claims as declarations:
# `test_zero_hit_claims_really_return_zero` runs them against the catalogue as
# fetched, so the day one of them starts matching, the suite says so.
# --------------------------------------------------------------------------- #

ZERO_HIT_CLAIMS: dict[str, tuple[str, ...]] = {
    "A-09": (r"indoor temperat", r"dwelling temperat", r"room temperat"),
    "A-11": (r"\bsize of dwelling",),
    "A-15": (r"\bU[- ]?value", r"thermal transmittance"),
    "A-17": (r"air change", r"air tightness|airtight", r"thermal mass"),
    "A-20": (r"turbidity", r"urban heat"),
    "A-22": (r"Hofstede", r"cultural dimension"),
    "A-25": (r"household formation",),
    "A-29": (r"peak demand", r"peak load", r"maximum demand", r"load factor",
             r"\bADMD\b", r"after diversity"),
    # U25's assumptions. These are the searches that make "DEAP is the only
    # reference" a tested statement rather than an assertion.
    "A-31": (r"hot water", r"water heating", r"\bimmersion\b"),
    "A-35": (r"fuel poverty", r"adequately warm", r"\bwarm\b"),
    "A-36": (r"rebound", r"prebound", r"indoor temperat"),
    # NOT "A-33": `cooking` matches six tables - HEBEU31 to HEBEU36, "Main
    # fuel used for cooking in households" - which is how that flag came to
    # be retired rather than kept.
}

#: Terms declared broad on purpose, exempt from :data:`BROAD_TERM_LIMIT`.
#:
#: Empty, and that is the measured result rather than an oversight. Every term
#: any flag uses matches at most 99 tables once anchored - the broadest are the
#: dimension-label searches "Number of Rooms" (99), "Type of Private
#: Accommodation" (90) and "Central Heating" (89), all well inside the limit.
#: The 932-table case that motivated the guard was the UNANCHORED r"BER\b",
#: which matches through "Number" and "Member"; anchoring it to r"\bBER\b"
#: brings it to 8. So the lesson is about anchoring, and the exemption list
#: earns no members.
#:
#: The mechanism stays because a future flag may legitimately need a broad
#: dimension term, and `test_the_limit_rejects_a_genuinely_unanchored_term`
#: exercises the guard directly so that an empty list cannot make it vacuous.
DELIBERATELY_BROAD: frozenset[str] = frozenset()


def load_catalogue() -> tuple[CatalogueEntry, ...]:
    """Read the declared PxStat catalogue.

    Uses :func:`require`, so an unfetched catalogue raises rather than
    silently sweeping nothing - a sweep over an empty catalogue would report
    "no source exists" for every flag, which is the most dangerous possible
    failure mode for this module.
    """
    path = require(CATALOGUE_KEY)
    raw = json.loads(path.read_text(encoding="utf-8"))
    items = raw.get("link", {}).get("item", [])
    if not items:
        raise SourceError(
            f"{CATALOGUE_KEY} parsed to zero tables; a sweep over an empty "
            f"catalogue would report 'nothing published' for every flag"
        )
    out = []
    for it in items:
        dims = tuple(
            str(v.get("label", k))
            for k, v in (it.get("dimension") or {}).items()
        )
        out.append(CatalogueEntry(
            matrix=str(it.get("extension", {}).get("matrix", "")),
            title=str(it.get("label", "")),
            dimensions=dims,
        ))
    return tuple(out)


def search(
    term: str, catalogue: tuple[CatalogueEntry, ...]
) -> tuple[CatalogueEntry, ...]:
    """Every table whose title or any dimension label matches ``term``.

    Dimension labels are searched as well as titles because the tables that
    matter are often titled uselessly: HS023 is called "Households", and
    everything that makes it the answer to A-04 and A-06 - that it breaks down
    by household appliance and by household size - is in its dimensions.
    """
    rx = re.compile(term, re.I)
    return tuple(e for e in catalogue if rx.search(e.haystack))


def sweep(catalogue: tuple[CatalogueEntry, ...] | None = None) -> dict[str, Any]:
    """Run every flag's search terms and assemble the U30 record."""
    cat = catalogue if catalogue is not None else load_catalogue()
    manifest_date = SWEEP_DATE
    flags: list[dict[str, Any]] = []
    for flag in ASSUMPTION_FLAGS:
        terms: list[dict[str, Any]] = []
        for term in flag.search_terms:
            hits = search(term, cat)
            terms.append({
                "term": term,
                "n_hits": len(hits),
                "deliberately_broad": term in DELIBERATELY_BROAD,
                "too_broad_to_be_a_search": (
                    len(hits) > BROAD_TERM_LIMIT and term not in DELIBERATELY_BROAD
                ),
                # Enough to identify what was looked at, not the whole result.
                "top_hits": [
                    {"matrix": h.matrix, "title": h.title,
                     "dimensions": list(h.dimensions)}
                    for h in hits[:8]
                ],
            })
        for key in flag.sources:
            if key not in REGISTRY:
                raise SourceError(
                    f"{flag.flag_id} names source {key!r}, which is not declared"
                )
        flags.append({
            "flag_id": flag.flag_id,
            "subject": flag.subject,
            "where": list(flag.where),
            "assumed": flag.assumed,
            "retires_if": flag.retires_if,
            "verdict": flag.verdict,
            "verdict_note": flag.verdict_note,
            "sources": list(flag.sources),
            "owning_step": flag.owning_step,
            "issue": flag.issue,
            "near_misses": list(flag.near_misses),
            "searched": terms,
            "total_hits_across_terms": sum(t["n_hits"] for t in terms),
        })
    counts: dict[str, int] = {}
    for f in flags:
        counts[f["verdict"]] = counts.get(f["verdict"], 0) + 1
    return {
        "label": "UNVALIDATED SIMULATION EVIDENCE",
        "decision": "U30",
        "question": (
            "Does a public CSO source exist for each remaining [A] assumption?"
        ),
        "swept_on": manifest_date,
        "catalogue": {
            "source_key": CATALOGUE_KEY,
            "n_tables": len(cat),
            "searched": "table title and the label of every dimension",
        },
        "method": (
            "Each flag declares its search terms and what evidence would "
            "retire it, both written before the search. The terms are run "
            "over the catalogue here, so the hits are computed and only the "
            "verdict is declared. I-040: an [A] flag should record what was "
            "searched, not only that something is assumed."
        ),
        "verdict_counts": counts,
        "n_flags": len(flags),
        "flags": flags,
    }


#: Files where "[A]" is the vocabulary being DEFINED rather than a flag being
#: raised: the dataset schema declares `evidence_tag` as one of [C]/[P]/[A]/[U]
#: and `evidence_status` as [C]/[A]/synthetic-placeholder. Excluded explicitly,
#: with the reason here, rather than by a silent pattern - a quiet exclusion is
#: how eight negative controls stayed out of pytest for four days.
VOCABULARY_FILES: frozenset[str] = frozenset({
    "schema/datasets.yaml",
    # The E2 report generator COUNTS assumptions: its "[A]" occurrences are
    # the register's own label being quoted in a column heading and in the
    # exposure split, not a new assumption being made. Same category as the
    # schema above, and listed for the same reason: so the exclusion is a
    # statement with a justification rather than a pattern nobody can audit.
    "report/e2_gate.py",
    # The D24 exporter records, per declared-but-unfillable field, WHY it is
    # null. One of those reasons quotes the schema's own `evidence_tag`
    # vocabulary - "Declared '[C] | [P] | [A] | [U]'" - to say that string
    # appears nowhere in the build. That is the register's label being named,
    # not an assumption being made, and it is the file's only occurrence.
    # Same category as the two above, listed for the same reason.
    "export/calibration_targets.py",
})


def uncovered_files(root: Path | None = None) -> dict[str, int]:
    """Files carrying an ``[A]`` flag that no sweep entry accounts for.

    The negative-control discovery lesson, applied here: eight of seventeen
    controls were never in pytest because the test imported a hand-written
    list. A hand-written list of assumptions would rot the same way, so the
    tree is the authority on where ``[A]`` appears and this reports anything
    the sweep has not claimed.
    """
    base = root or Path(__file__).resolve().parents[1]
    named = " ".join(w for f in ASSUMPTION_FLAGS for w in f.where)
    out: dict[str, int] = {}
    for path in sorted(base.rglob("*")):
        if path.suffix not in (".py", ".yaml") or not path.is_file():
            continue
        if path.name == "assumption_sweep.py":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        n = text.count("[A]")
        if not n:
            continue
        rel = path.relative_to(base).as_posix()
        if rel in VOCABULARY_FILES:
            continue
        stem = path.name
        if stem in named or rel in named or path.stem in named:
            continue
        out[rel] = n
    return out


def write_sweep(path: Path | None = None) -> Path:
    """Write the U30 artefact."""
    rec = sweep()
    out = path or (
        Path(__file__).resolve().parents[3] / "v1" / "evidence"
        / "assumption_sweep_u30.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    return out
