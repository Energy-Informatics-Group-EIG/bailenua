"""D27 - tariffs and contracts, as a RECORD ONLY.

What this is
------------
Three synthetic rate cards - a flat 24-hour plan, a day/night plan and a
three-band time-of-use plan - with one plan assigned per household, written as
an OBS dataset because it is what a supplier or an aggregator would hold.

What this is NOT
----------------
An input.  **The engine does not read it, and ``control_mode`` is unchanged.**
Nothing under ``engine/``, ``physics/``, ``devices/`` or ``behaviour/`` imports
or names this module, and
``test_export_d21_d23_d27.test_d27_the_engine_cannot_read_the_tariff``
asserts that over the source tree rather than trusting this sentence.  The rate
card influences no setpoint, no appliance trigger and no dispatch decision; it
is a column a future RL or pricing experiment can read, and in this release it
is inert.  That is also why every source below is declared
``model_development_exposure="none"``: not as a claim about intent, but
because the layers that could be exposed are structurally unable to see the
data.

Where the numbers come from
---------------------------
Every magnitude on the card traces to a declared public source, fetched into
``sources/`` with its SHA-256 and retrieval date.  Seven sources, declared in
``sources_registry.py`` before use:

================================================  ============================
Source                                            What it establishes
================================================  ============================
``electricireland.priceplan.standard_elec_2022_05``  the flat and day/night
                                                  unit rates and their urban
                                                  standing charges, on a
                                                  schedule dated 1 May 2022 -
                                                  the year the estate-year run
                                                  simulates
``electricireland.priceplan.home_electric_plus_sst_2024_11``
                                                  the three-band plan: day,
                                                  night and peak rates, its
                                                  standing charge, and the
                                                  only PUBLISHED band hours
                                                  in the corpus
``cru.ceg.enduring_arrangements_cru202454``       that an export payment
                                                  exists, its published range
                                                  (16c/kWh to 25c/kWh) and its
                                                  regulated floor of zero
``esbn.connections.basis_of_charges``             the standard domestic
                                                  connection capacity
``cru.energy_monitoring_report_2022``             the regulator's own
                                                  decomposition of a domestic
                                                  bill, which the card's shape
                                                  is checked against
``cso.electricity.hebeu88_tariff_type_by_urban_rural``
                                                  the share of urban
                                                  households on each published
                                                  tariff type - the plan mix
``cso.electricity.tmegb03_residential_electricity_prices``
                                                  an independent check on the
                                                  LEVEL of the unit rates
================================================  ============================

Three older declared sources corroborate the **structure** and are kept
because they are what established it before any rate was found: ESB Networks'
Standard Load Profiles name the market's own domestic classes
(*24 Hour* and *Night Saver*), the DEAP manual distinguishes an on-peak from
an off-peak rate and records that the Irish night-rate tariff provides one
off-peak period each night, and CSO MEC05 publishes 'Tariff Group' as a real
classification of Irish metered consumption.

Five of the seven are PDFs, and the project's rule for a reference that is not
machine-readable - the DEAP manual's own ``substitute_flag`` - is that figures
are transcribed by hand WITH their page and a test asserts the quoted wording
is on that page.  That is what :data:`TARIFF_RATES` is: one entry per number,
each carrying its source key, page, and the published wording it was read
from.  ``test_d27_every_sourced_rate_is_in_its_cited_document`` checks all of
them against the fetched bytes, so a transcription error is a test failure
rather than a false citation in a published dataset.  The two CSO tables are
JSON-stat and are read at export time.

What is still assumed
---------------------
Three things, each with a flag and a search record in
:data:`TARIFF_ASSUMPTIONS`, in
:class:`baile_nua.validation.assumption_sweep.AssumptionFlag`'s own form:

* **A-92** the day/night plan's band hours.  The May 2022 schedule publishes
  rates and no hours at all; the window is carried from the smart tariff's
  published ``Night Hours: 23:00 - 08:00``.  A cross-plan carry, not a
  reading.
* **A-97** the three-band plan's vintage.  Its rates and hours are from a
  November 2024 schedule because no three-band domestic plan was published in
  May 2022, so that one plan's magnitudes are four years out of step with the
  simulated year.
* **A-96** ``flex_contract_terms`` and ``trial_arm``, which are written null
  because no aggregator contract and no recruitment randomisation exist in
  this run.

Five flags that stood before these sources were fetched are kept with verdict
``RETIRED`` and the source that retired each, so the record shows what was
assumed and what closed it rather than only the present state.

Reproducibility
---------------
Plan assignment is counter-based, as design 8.2 requires, keyed by the run's
master seed and the premises id, so the same premises gets the same plan on
every re-run and the plan does not depend on iteration order.  The stream id
is declared **here**, in the export layer, and not appended to
``baile_nua.rng.Stream``: the engine is frozen, and a new member of that enum
would invalidate every checkpoint.  :data:`EXPORT_TARIFF_PLAN_STREAM` is in a
range no declared ``Stream`` occupies and
``test_d27_the_export_stream_cannot_collide_with_a_declared_one`` asserts it.
"""

from __future__ import annotations

import json
import re
from typing import Any

import pandas as pd
from numpy.random import Generator, Philox

from baile_nua.export.context import ExportError, RunContext
from baile_nua.export.writer import emit
from baile_nua.rng import Stream, splitmix64, stable_entity_id

__all__ = [
    "EXPORT_TARIFF_PLAN_STREAM",
    "STRUCTURE_SOURCE_KEYS",
    "RATE_SOURCE_KEYS",
    "DEAP_STRUCTURE_QUOTES",
    "TARIFF_RATES",
    "PLANS",
    "TARIFF_ASSUMPTIONS",
    "SUPPLIER",
    "DAYS_PER_YEAR",
    "SourcedValue",
    "assumption_tag",
    "export_generator",
    "structure_evidence",
    "plan_mix",
    "plan_for_premises",
    "price_cross_check",
    "build_d27_frame",
    "export_d27",
]

#: Counter-based stream for plan assignment, declared in the export layer.
#:
#: 20001, not a value near the declared ones: ``rng.Stream`` runs to 78 for
#: production subsystems and 9000-9001 for the test and negative-control
#: streams, and its own contract is that values are appended and never reused.
#: The engine is frozen, so this module cannot append to that enum; a value
#: well outside its occupied ranges cannot collide with one appended later
#: either, and a test asserts the disjointness rather than assuming it.
EXPORT_TARIFF_PLAN_STREAM = 20001

#: The declared sources the card's STRUCTURE is read from.
STRUCTURE_SOURCE_KEYS: tuple[str, ...] = (
    "esbn.rmds.slp_indexes_2022",
    "seai.deap.manual_4_2_7",
    "cso.electricity.mec05_by_tariff_group",
)

#: The declared sources the card's MAGNITUDES are read from.
RATE_SOURCE_KEYS: tuple[str, ...] = (
    "electricireland.priceplan.standard_elec_2022_05",
    "electricireland.priceplan.home_electric_plus_sst_2024_11",
    "cru.ceg.enduring_arrangements_cru202454",
    "esbn.connections.basis_of_charges",
    "cru.energy_monitoring_report_2022",
    "cso.electricity.hebeu88_tariff_type_by_urban_rural",
    "cso.electricity.tmegb03_residential_electricity_prices",
)

#: Divisor turning a published ANNUAL standing charge into the per-day field
#: the schema declares.  365 and not 365.25: a supplier's annual standing
#: charge is a 365-day figure, 2022 is not a leap year, and the simulated year
#: is 365 days long.
DAYS_PER_YEAR = 365

#: The supplier of record.  A synthetic name, even though the rates are a real
#: published schedule: the plan MIX, the per-premises assignment and the
#: connection capacities are not Electric Ireland's, so presenting the rows as
#: that company's customer records would be a claim about the company. The
#: rate SOURCE is cited field by field instead.
SUPPLIER = "Baile Nua Synthetic Supply (SYNTHETIC: no real supplier)"


class SourcedValue:
    """One number, and the published wording it was read from.

    Exists so that no magnitude in this module can be written without a source
    key, a page and the exact text it came from.  The quote is not decoration:
    ``test_d27_every_sourced_rate_is_in_its_cited_document`` searches for it in
    the declared file's own bytes.
    """

    __slots__ = ("value", "unit", "source_key", "page", "quote", "note")

    def __init__(
        self, value: float, unit: str, source_key: str, page: int | None,
        quote: str, note: str = "",
    ) -> None:
        self.value = float(value)
        self.unit = unit
        self.source_key = source_key
        self.page = page
        self.quote = quote
        self.note = note

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "value": self.value, "unit": self.unit,
            "source_key": self.source_key, "quoted": self.quote,
        }
        if self.page is not None:
            out["page"] = self.page
        if self.note:
            out["note"] = self.note
        return out


_EI22 = "electricireland.priceplan.standard_elec_2022_05"
_EI24 = "electricireland.priceplan.home_electric_plus_sst_2024_11"
_CEG = "cru.ceg.enduring_arrangements_cru202454"
_BOC = "esbn.connections.basis_of_charges"
_EMR = "cru.energy_monitoring_report_2022"

#: Every magnitude on the card, transcribed from a declared PDF with its page.
#:
#: Rates are the **VAT-inclusive** column throughout, because that is what a
#: household is charged and what the schema's ``eur_kwh`` fields describe.  The
#: smart tariff sheet publishes a VAT-inclusive standard rate and four lower
#: "effective rates" that bundle payment-method discounts; the STANDARD rate is
#: the one taken, because a discount is a property of how a particular customer
#: pays and not of the tariff.
TARIFF_RATES: dict[str, SourcedValue] = {
    "flat_24h_eur_kwh": SourcedValue(
        0.2812, "EUR/kWh incl. VAT", _EI22, 1,
        "24-Hr Price per unit (kWh) 25.80 28.12",
        "the two columns are excl. and incl. VAT; the incl. figure is taken",
    ),
    "flat_24h_standing_eur_year": SourcedValue(
        272.05, "EUR/year incl. VAT", _EI22, 1,
        "Urban €249.59 €272.05",
        "the URBAN annual 24-hour standing charge; Cobh is an urban town",
    ),
    "nightsaver_day_eur_kwh": SourcedValue(
        0.3004, "EUR/kWh incl. VAT", _EI22, 1,
        "Day Price per unit (kWh) 27.56 30.04", "",
    ),
    "nightsaver_night_eur_kwh": SourcedValue(
        0.1482, "EUR/kWh incl. VAT", _EI22, 1,
        "Night Price per unit (kWh) 13.60 14.82", "",
    ),
    "nightsaver_standing_eur_year": SourcedValue(
        356.47, "EUR/year incl. VAT", _EI22, 1,
        "Urban €327 .04 €356.47",
        "the URBAN annual NightSaver standing charge. The published PDF's own "
        "text carries a stray space inside '€327 .04', which is why the test "
        "compares with whitespace removed",
    ),
    "smart_day_eur_kwh": SourcedValue(
        0.3703, "EUR/kWh incl. VAT", _EI24, 1,
        "Day Price per unit (kWh)^ 33.97 37.03",
        "the STANDARD incl.-VAT rate, not one of the four discounted "
        "'effective rates' that follow it on the same row",
    ),
    "smart_night_eur_kwh": SourcedValue(
        0.1946, "EUR/kWh incl. VAT", _EI24, 1,
        "Night Price per unit (kWh)^ 17.85 19.46", "",
    ),
    "smart_peak_eur_kwh": SourcedValue(
        0.3950, "EUR/kWh incl. VAT", _EI24, 1,
        "Peak Price per unit (kWh)^ 36.24 39.50", "",
    ),
    "smart_standing_eur_year": SourcedValue(
        250.77, "EUR/year incl. VAT", _EI24, 1,
        "Urban 230.06 250.77",
        "the URBAN annual standing charge for the smart tariff",
    ),
    "export_range_low_eur_kwh": SourcedValue(
        0.16, "EUR/kWh", _CEG, 13,
        "have generally ranged from circa 16c/kWh to 25c/kWh",
        "the low end of the range the CRU records suppliers offering",
    ),
    "export_range_high_eur_kwh": SourcedValue(
        0.25, "EUR/kWh", _CEG, 13,
        "have generally ranged from circa 16c/kWh to 25c/kWh",
        "the high end of the same published range",
    ),
    "export_floor_eur_kwh": SourcedValue(
        0.0, "EUR/kWh", _CEG, 34,
        "The current floor price for flat-rate export tariffs of zero is retained.",
        "the regulated floor, retained by the 2024 decision",
    ),
    "standard_domestic_connection_kva": SourcedValue(
        12.0, "kVA", _BOC, 10,
        "Domestic connections are only available for the standard capacities "
        "of 3kVA, 12kVA, 16kVA, 20kVA and 29kVA",
        "12 kVA is the standard domestic connection; the document also lists "
        "3, 16, 20 and 29 kVA, and treats 30 kVA or more as a business "
        "connection",
    ),
    "regulator_bill_example_standing_eur_day": SourcedValue(
        0.80, "EUR/day", _EMR, 37,
        "€0.80 *365 €51.60 €174.98 €2,119",
        "the regulator's own worked domestic bill: a standing charge of EUR "
        "0.80 a day, the PSO levy, the VAT and the estimated annual bill. Used "
        "as a CHECK on the card's shape, not as a rate",
    ),
}

#: The export rate written on every card: the midpoint of the published range.
#:
#: A stated rule rather than a choice: the CRU publishes a range and no single
#: number, so the card takes the midpoint and says so.  The floor is recorded
#: beside it, because a floor of zero is what makes the range the whole of the
#: published evidence rather than a central estimate.
EXPORT_RATE_EUR_KWH = round(
    (TARIFF_RATES["export_range_low_eur_kwh"].value
     + TARIFF_RATES["export_range_high_eur_kwh"].value) / 2.0, 6)

#: Published band hours.  The ONLY band hours in the declared corpus.
BAND_HOURS: dict[str, SourcedValue] = {
    "day": SourcedValue(
        0.0, "clock band", _EI24, 3,
        "Day Hours: 08:00 – 23:00 (excluding Peak)", "",
    ),
    "night": SourcedValue(
        0.0, "clock band", _EI24, 3,
        "Night Hours: 23:00 – 08:00", "",
    ),
    "peak": SourcedValue(
        0.0, "clock band", _EI24, 3,
        "Peak Hours: 17:00 – 19:00", "",
    ),
}

#: Band clock.  A published tariff states its bands in local clock time, so
#: the card does too, and the field is named rather than left to be guessed.
BAND_CLOCK = "Europe/Dublin local clock, as the published price schedule states it"

#: The clauses in DEAP 4.2.7 that establish the STRUCTURE, with their pages.
#: Kept after the rates were sourced, because they are the independent
#: corroboration that the bands and the export payment are features of the
#: Irish market and not of one supplier's product sheet.
DEAP_STRUCTURE_QUOTES: tuple[dict[str, Any], ...] = (
    {
        "page": 67,
        "quote": "The standard tariff is the on-peak rate unless the heating "
                 "and/or hot water uses an off-peak tariff",
        "establishes": "an on-peak rate and an off-peak rate both exist, and "
                       "the standard (flat) tariff is the on-peak one",
    },
    {
        "page": 104,
        "quote": "For the night-rate tariff available in Ireland, providing "
                 "one off-peak period each night",
        "establishes": "the Irish night-rate tariff is a SINGLE contiguous "
                       "nightly off-peak period, not several",
    },
    {
        "page": 139,
        "quote": "Electricity exported is valued at the price for electricity "
                 "sold to the grid",
        "establishes": "an export price exists and is distinct from the "
                       "purchase price",
    },
    {
        "page": 139,
        "quote": "(currently 0c)",
        "establishes": "DEAP's own export price, SUPERSEDED: it predates the "
                       "Clean Export Guarantee, and CRU202454 is the source "
                       "the card uses instead. Kept so the supersession is on "
                       "the record",
    },
    {
        "page": 140,
        "quote": "All normal fuel costs are available from the SEAI Domestic "
                 "Fuel Cost Comparison on the SEAI Website",
        "establishes": "DEAP carries no rates and names a publication that is "
                       "not in sources/. This is why the rates come from a "
                       "supplier's published schedule and the regulator's "
                       "papers instead",
    },
    {
        "page": 140,
        "quote": "exported to the grid via an ESB Networks provided "
                 "import/export meter",
        "establishes": "export is a metered, operator-provisioned "
                       "arrangement, which is what max_export_kw and "
                       "der_notification_ref describe",
    },
)


def assumption_tag() -> str:
    """The project's assumption marker, read from the schema that declares it.

    Not written as a literal here.  ``datasets.yaml`` is where the vocabulary
    of evidence tags is DEFINED - which is why
    ``validation.assumption_sweep.VOCABULARY_FILES`` exempts it from the
    uncovered-flag scan - so reading the marker from the schema keeps that
    scan meaning what it says: this module raises flags by id and does not
    re-declare the vocabulary.
    """
    from baile_nua.schema import load

    notes = load()["D24"].field_map["evidence_tag"].notes or ""
    tag = next((t for t in re.findall(r"\[([A-Z])\]", notes) if t == "A"), None)
    if tag is None:
        raise ExportError(
            "D24.evidence_tag no longer declares an assumption marker, so "
            "this module cannot label an assumption in the project's own "
            "vocabulary. Fix the schema or the reader, do not invent a marker."
        )
    return f"[{tag}]"


# --------------------------------------------------------------------------- #
# the assumption flags, in the sweep's own form
# --------------------------------------------------------------------------- #

def _flags() -> tuple[Any, ...]:
    from baile_nua.validation.assumption_sweep import AssumptionFlag

    where = ("export/tariffs.py",)
    return (
        AssumptionFlag(
            flag_id="A-90", subject="D27 retail rate magnitudes",
            where=where,
            assumed="nothing any more: the unit rates are a published schedule",
            retires_if=(
                "a published Irish residential electricity unit rate, "
                "declared in sources_registry.py with a file and manifest "
                "under sources/, from which day and night rates can be read"
            ),
            search_terms=(r"electricity price", r"unit rate", r"energy price",
                          r"cent per kilowatt"),
            verdict="RETIRED",
            verdict_note=(
                "RETIRED. Electric Ireland's Standard Electricity Price Plan "
                "dated 1 May 2022 publishes the 24-hour rate (28.12 c/kWh "
                "incl. VAT), the NightSaver day and night rates (30.04 and "
                "14.82) and the urban standing charges, and the Home "
                "Electric+ Standard Smart Tariff schedule publishes the "
                "three-band rates. Both are fetched, hashed and declared. "
                "CSO TMEGB03's published band-DC price for 2022 brackets the "
                "supplier's figure independently (0.2324 in the first half of "
                "the year, 0.3225 in the second, against the schedule's "
                "0.2812), which is what makes the level a measurement rather "
                "than a transcription. The retail market is price-"
                "deregulated, so no regulator publishes the rates themselves "
                "- which is why the primary source is a dated supplier "
                "schedule and the CSO series is the check."
            ),
            sources=(
                "electricireland.priceplan.standard_elec_2022_05",
                "electricireland.priceplan.home_electric_plus_sst_2024_11",
                "cso.electricity.tmegb03_residential_electricity_prices",
            ),
            owning_step="retired in this export; nothing further owed",
            near_misses=(
                "MEC05 metered consumption BY tariff group - the right shelf, "
                "no rate on it",
                "DEAP 4.2.7 p.140, which names the SEAI Domestic Fuel Cost "
                "Comparison instead of carrying a rate",
            ),
        ),
        AssumptionFlag(
            flag_id="A-91", subject="D27 plan mix across the town",
            where=where,
            assumed=(
                "nothing any more: the mix is the published share of urban "
                "households on each tariff type"
            ),
            retires_if=(
                "a published share of Irish households by electricity tariff "
                "type, declared and fetched"
            ),
            search_terms=(r"tariff", r"night rate", r"time of use"),
            verdict="RETIRED",
            verdict_note=(
                "RETIRED. CSO HEBEU88 publishes 'Electricity tariff used by "
                "households for billing' by urban or rural location, with "
                "categories Standard tariff, Day/Night (or "
                "Day/Night/Weekend), Smart tariff, Other NEC and unknown. "
                "Cobh is urban, so the urban row is used and the three known "
                "shares are renormalised, with the suppressed 'Other' and the "
                "unknown share reported on the dataset rather than "
                "reassigned. This is the HAS02 lesson (I-040) paying off: a "
                "search over the declared PxStat catalogue found a published "
                "table where an earlier note had recorded a conclusion."
            ),
            sources=("cso.electricity.hebeu88_tariff_type_by_urban_rural",),
            owning_step="retired in this export; nothing further owed",
            near_misses=(
                "MEC06 residential meter counts by consumption band - counts, "
                "but not by tariff type",
            ),
        ),
        AssumptionFlag(
            flag_id="A-92",
            subject="D27 band boundaries for the day/night plan",
            where=where,
            assumed=(
                "the day/night plan's night window is the smart tariff's "
                "published 'Night Hours: 23:00 - 08:00'. The May 2022 "
                "NightSaver schedule publishes rates and NO hours, so this is "
                "a carry from one published plan to another, not a reading"
            ),
            retires_if=(
                "a published Electric Ireland NightSaver meter band window, or "
                "the ESB Networks night-rate meter switching times, declared "
                "and fetched"
            ),
            search_terms=(r"night rate", r"night saver", r"day/night",
                          r"time-of-use"),
            verdict="KEPT",
            verdict_note=(
                "KEPT, and narrowed to one thing. The three-band plan's hours "
                "ARE published and are used as published (day 08:00-23:00 "
                "excluding peak, night 23:00-08:00, peak 17:00-19:00, "
                "CRU-regulated supplier schedule, page 3). What is not "
                "published anywhere in the declared corpus is the NightSaver "
                "meter's own window: the 2022 price schedule states the rates "
                "and not the hours, and PxStat returns zero hits for all four "
                "search terms over 13,086 tables because a meter switching "
                "time is a term of a connection and not a statistic. DEAP "
                "Appendix F (p.104) does establish the SHAPE - one off-peak "
                "period each night - so a single contiguous night band is "
                "sourced even where its boundaries are carried."
            ),
            near_misses=(
                "esbn.rmds.slp_indexes_2022, which publishes the quarter-hour "
                "demand shape of the Night Saver class but not the band that "
                "produced it",
            ),
        ),
        AssumptionFlag(
            flag_id="A-93", subject="D27 standing charge",
            where=where,
            assumed=(
                "nothing any more: the standing charge is the published urban "
                "annual charge for each plan, divided by 365"
            ),
            retires_if=(
                "a published Irish domestic standing charge, declared and "
                "fetched"
            ),
            search_terms=(r"standing charge", r"\bbill\b"),
            verdict="RETIRED",
            verdict_note=(
                "RETIRED. Each plan's published schedule carries its own "
                "urban annual standing charge: EUR 272.05 incl. VAT for the "
                "24-hour plan, EUR 356.47 for NightSaver (1 May 2022) and EUR "
                "250.77 for the smart tariff (1 November 2024). The CRU's "
                "Energy Monitoring Report for 2022 independently states a "
                "standing charge of EUR 0.80 a day in its worked domestic "
                "bill, which brackets all three. 'standing charge' returns "
                "ZERO hits over the whole PxStat catalogue, so the statistical "
                "service was indeed the wrong instrument - the published "
                "schedule was the right one."
            ),
            sources=(
                "electricireland.priceplan.standard_elec_2022_05",
                "electricireland.priceplan.home_electric_plus_sst_2024_11",
                "cru.energy_monitoring_report_2022",
            ),
            owning_step="retired in this export; nothing further owed",
        ),
        AssumptionFlag(
            flag_id="A-94",
            subject="D27 export rate under the Clean Export Guarantee",
            where=where,
            assumed=(
                "the midpoint of the CRU's published range, by a stated rule. "
                "The range, the floor and the existence of the payment are "
                "all published; the single number is not"
            ),
            retires_if=(
                "a published Clean Export Guarantee rate or a CRU decision "
                "setting one, declared and fetched"
            ),
            search_terms=(r"clean export", r"export (rate|payment|price)",
                          r"feed-in", r"microgeneration"),
            verdict="RETIRED",
            verdict_note=(
                "RETIRED as to the evidence, with the arithmetic stated. "
                "CRU202454 (18 June 2024) records that export tariffs "
                "'have generally ranged from circa 16c/kWh to 25c/kWh' and "
                "that the floor price of zero for flat-rate export tariffs is "
                "retained. The card carries the midpoint of that range, "
                "0.205 EUR/kWh, and both ends and the floor are on the "
                "dataset so a reader can take a different point from the same "
                "evidence. This supersedes DEAP p.139's 'currently 0c', which "
                "predates the guarantee: writing 0 would have stated that "
                "Irish microgenerators are unpaid. PxStat returns zero hits "
                "for all four terms, because a supplier obligation is not a "
                "statistical table."
            ),
            sources=("cru.ceg.enduring_arrangements_cru202454",),
            owning_step="retired in this export; nothing further owed",
            near_misses=(
                "seai.deap.manual_4_2_7 p.139, the only export price in the "
                "corpus before this fetch, and superseded by it",
            ),
        ),
        AssumptionFlag(
            flag_id="A-95", subject="D27 maximum import capacity",
            where=where,
            assumed=(
                "nothing any more: the standard domestic connection capacity "
                "is published. What is stated rather than published is the "
                "kVA-to-kW conversion, taken at unity power factor"
            ),
            retires_if=(
                "ESB Networks' published domestic connection capacity, or a "
                "connection-policy document, declared and fetched"
            ),
            search_terms=(r"connection capacity", r"maximum import", r"\bMIC\b"),
            verdict="RETIRED",
            verdict_note=(
                "RETIRED. ESB Networks' Basis of Charges for Connection to "
                "the Distribution System states that 'Domestic connections "
                "are only available for the standard capacities of 3kVA, "
                "12kVA, 16kVA, 20kVA and 29kVA' and treats 12 kVA as the "
                "standard domestic connection, with 30 kVA or more a business "
                "connection. The schema declares the field in kW and the "
                "document publishes kVA; the card carries 12.0 and states the "
                "unity-power-factor conversion rather than leaving it "
                "implicit. PxStat returns zero hits for all three terms, "
                "which was correct - the connection agreement was the right "
                "instrument."
            ),
            sources=("esbn.connections.basis_of_charges",),
            owning_step="retired in this export; nothing further owed",
        ),
        AssumptionFlag(
            flag_id="A-96",
            subject="D27 flexibility contract terms and trial arm",
            where=where,
            assumed=(
                "nothing: flex_contract_terms and trial_arm are written null, "
                "because no aggregator contract and no recruitment "
                "randomisation exist in this run"
            ),
            retires_if=(
                "a flexibility or aggregator contract model in the engine, "
                "and a recruitment protocol that randomises premises to arms"
            ),
            search_terms=(r"aggregator", r"demand response", r"flexibilit"),
            verdict="KEPT",
            verdict_note=(
                "Both fields are declared optional, and both are absent from "
                "the model rather than unsourced: there is no aggregator "
                "contract anywhere in the package, and D28 owns study "
                "selection. Written null rather than filled, so the absence "
                "is in the data."
            ),
        ),
        AssumptionFlag(
            flag_id="A-97",
            subject="D27 three-band plan is four years out of vintage",
            where=where,
            assumed=(
                "that a November 2024 smart-tariff schedule may stand for a "
                "2022 three-band plan. Its rates and its band hours are both "
                "2024"
            ),
            retires_if=(
                "a published Irish domestic three-band or smart tariff "
                "schedule dated within the simulated year, declared and "
                "fetched"
            ),
            search_terms=(r"smart meter", r"time of use", r"tariff"),
            verdict="KEPT",
            verdict_note=(
                "KEPT, and it is a vintage problem rather than an unsourced "
                "one. A three-band domestic plan with published day, night "
                "and peak bands was not on sale in May 2022 - the national "
                "smart meter rollout had not reached the point where "
                "suppliers published one - so there is no contemporaneous "
                "schedule to fetch. The flat and day/night plans ARE "
                "contemporaneous (1 May 2022, the simulated year). The "
                "consequence is specific and bounded: one of three plans "
                "carries 2024 price levels, which are higher, so a comparison "
                "ACROSS plans in this dataset mixes two years and a "
                "comparison WITHIN a plan does not. Recorded on every row."
            ),
        ),
    )


#: Built at import time, so ``AssumptionFlag.__post_init__`` validates every
#: flag the moment this module loads: a RETIRED or SOURCE_FOUND verdict with no
#: named source, or a flag with no search terms, is an import error and not a
#: surprise at export time.
TARIFF_ASSUMPTIONS: tuple[Any, ...] = _flags()


def _assumptions() -> tuple[Any, ...]:
    return TARIFF_ASSUMPTIONS


# --------------------------------------------------------------------------- #
# the plans
# --------------------------------------------------------------------------- #

def _band(name: str, start: str, end: str, rate_key: str) -> dict[str, Any]:
    rate = TARIFF_RATES[rate_key]
    return {
        "band": name, "from": start, "to": end,
        "rate_eur_kwh": rate.value,
        "rate_source": rate.as_dict(),
    }


def _standing_per_day(rate_key: str) -> float:
    return round(TARIFF_RATES[rate_key].value / DAYS_PER_YEAR, 6)


#: ``tariff_code -> plan``.  Three plans, matching the three ``tariff_kind``
#: values ``datasets.yaml`` declares (``flat | day-night | ToU``) and the three
#: published HEBEU88 categories the mix is drawn from.
#:
#: The codes name the schedule each plan is read from, so a reader of the
#: ``tariff_code`` column alone can see which published sheet and which year a
#: row's rates come from.
PLANS: dict[str, dict[str, Any]] = {
    "BN-SYNTH-24H-EI20220501": {
        "tariff_kind": "flat",
        "hebeu88_category": "Standard tariff",
        "rate_schedule_vintage": "2022-05-01",
        "contemporaneous_with_the_simulated_year": True,
        "standing_charge_key": "flat_24h_standing_eur_year",
        "structure_basis": (
            "ESB Networks Standard Load Profiles 2022 name a 'Domestic 24 "
            "Hour' class; DEAP 4.2.7 p.67 says the standard tariff is the "
            "on-peak rate; the rate and standing charge are the published "
            "1 May 2022 schedule"
        ),
        "bands": [_band("day", "00:00", "24:00", "flat_24h_eur_kwh")],
    },
    "BN-SYNTH-NIGHTSAVER-EI20220501": {
        "tariff_kind": "day-night",
        "hebeu88_category": "Day/Night tariff or Day/Night/Weekend tariff",
        "rate_schedule_vintage": "2022-05-01",
        "contemporaneous_with_the_simulated_year": True,
        "standing_charge_key": "nightsaver_standing_eur_year",
        "structure_basis": (
            "ESB Networks Standard Load Profiles 2022 name a 'Domestic Night "
            "Saver' class; DEAP 4.2.7 p.104 records one off-peak period each "
            "night; the rates and standing charge are the published 1 May "
            "2022 schedule. The HOURS are carried from the smart tariff's "
            "published night window (A-92): this schedule publishes none"
        ),
        "bands": [
            _band("night", "23:00", "08:00", "nightsaver_night_eur_kwh"),
            _band("day", "08:00", "23:00", "nightsaver_day_eur_kwh"),
        ],
    },
    "BN-SYNTH-TOU3-EI20241101": {
        "tariff_kind": "ToU",
        "hebeu88_category": "Smart tariff",
        "rate_schedule_vintage": "2024-11-01",
        "contemporaneous_with_the_simulated_year": False,
        "standing_charge_key": "smart_standing_eur_year",
        "structure_basis": (
            "the published Home Electric+ Standard Smart Tariff schedule: its "
            "own rates and its own band hours, the only published band hours "
            "in the declared corpus. FOUR YEARS OUT OF VINTAGE from the "
            "simulated year (A-97): no three-band domestic plan was published "
            "in May 2022"
        ),
        "bands": [
            _band("night", "23:00", "08:00", "smart_night_eur_kwh"),
            _band("day", "08:00", "17:00", "smart_day_eur_kwh"),
            _band("peak", "17:00", "19:00", "smart_peak_eur_kwh"),
            _band("day", "19:00", "23:00", "smart_day_eur_kwh"),
        ],
    },
}

#: Maximum import capacity, in the kW the schema declares, from the published
#: standard domestic connection capacity in kVA.
MAX_IMPORT_KW = TARIFF_RATES["standard_domestic_connection_kva"].value


# --------------------------------------------------------------------------- #
# reproducible assignment
# --------------------------------------------------------------------------- #

def export_generator(
    master_seed: int, stream_id: int, entity: int | str,
    sim_day: int = 0, draw: int = 0,
) -> Generator:
    """``SeedTree.generator``'s construction, for a stream declared in export/.

    Identical arithmetic to :meth:`baile_nua.rng.SeedTree.generator` - the same
    SplitMix64 key expansion, the same four counter words in the same order -
    reusing that module's own :func:`splitmix64` and
    :func:`stable_entity_id` so this is the same RNG and not a second one.
    What differs is only that the stream id comes from this package, because
    :class:`baile_nua.rng.Stream` is inside the freeze and appending a member
    to it would invalidate every checkpoint.
    """
    if stream_id in {int(s) for s in Stream}:
        raise ExportError(
            f"stream id {stream_id} is already declared in rng.Stream "
            f"({Stream(stream_id).name}). Two subsystems sharing a sequence "
            f"is the exact failure the Stream enum exists to prevent."
        )
    k0 = splitmix64(int(master_seed))
    key = [k0, splitmix64(k0 ^ 0xA0761D6478BD642F)]
    ent = stable_entity_id(entity) if isinstance(entity, str) else int(entity)
    mask = (1 << 64) - 1
    counter = [
        int(stream_id) & mask, ent & mask,
        int(sim_day) & mask, int(draw) & mask,
    ]
    return Generator(Philox(key=key, counter=counter))


def plan_mix() -> dict[str, Any]:
    """The share of URBAN households on each plan, read from CSO HEBEU88.

    Cobh is an urban town, so the urban row is the one used.  HEBEU88's two
    remaining categories - 'Other tariff NEC', which is suppressed, and
    'Tariff type unknown' - are reported rather than reassigned: a household
    whose tariff type the survey did not establish is not evidence for any
    particular plan, so the three known shares are renormalised and the
    unassigned share is recorded on the dataset.
    """
    import baile_nua.sources_registry  # noqa: F401  (declares the sources)
    from baile_nua.sources import require

    key = "cso.electricity.hebeu88_tariff_type_by_urban_rural"
    doc = json.loads(require(key).read_text("utf-8"))
    ids = list(doc["id"])
    size = [int(s) for s in doc["size"]]
    values = doc["value"]
    dims = [doc["dimension"][i] for i in ids]
    labels = [list(d["category"]["label"].values()) for d in dims]

    location_axis = next(
        i for i, d in enumerate(dims)
        if "Urban" in str(d.get("label")) or "Rural" in str(d.get("label")))
    tariff_axis = next(
        i for i, d in enumerate(dims) if "Tariff" in str(d.get("label")))

    published: dict[str, float | None] = {}
    strides = [1] * len(size)
    for i in range(len(size) - 2, -1, -1):
        strides[i] = strides[i + 1] * size[i + 1]
    for combo_index in range(strides[0] * size[0]):
        combo = [
            (combo_index // strides[i]) % size[i] for i in range(len(size))]
        location = labels[location_axis][combo[location_axis]]
        if not str(location).startswith("Urban"):
            continue
        tariff = labels[tariff_axis][combo[tariff_axis]]
        raw = (values[combo_index] if isinstance(values, list)
               else values.get(str(combo_index)))
        published[str(tariff)] = (None if raw is None else float(raw))

    wanted = {p["hebeu88_category"]: code for code, p in PLANS.items()}
    known = {
        wanted[cat]: share for cat, share in published.items()
        if cat in wanted and share is not None
    }
    missing = sorted(set(wanted) - {c for c in published if published[c] is not None})
    if missing:
        raise ExportError(
            f"HEBEU88 publishes no urban share for {missing}, so the plan mix "
            f"cannot be drawn from it. The categories present are "
            f"{sorted(published)}. Refusing rather than substituting a share."
        )
    total = sum(known.values())
    if total <= 0:
        raise ExportError("HEBEU88's urban shares sum to zero")
    weights = {code: share / total for code, share in sorted(known.items())}
    return {
        "source_key": key,
        "published_urban_shares_pct": published,
        "assigned_categories": {v: k for k, v in wanted.items()},
        "weights": weights,
        "renormalised_over_pct": round(total, 4),
        "unassigned_pct": {
            cat: share for cat, share in published.items()
            if cat not in wanted
        },
        "unassigned_note": (
            "'Other tariff NEC' is suppressed in the published table and "
            "'Tariff type unknown' is a non-answer; neither is evidence for a "
            "particular plan, so both are reported and not reassigned"
        ),
        "location_note": "the URBAN row: Cobh is an urban town",
    }


def plan_for_premises(
    premises_id: str, master_seed: int, weights: dict[str, float] | None = None,
) -> str:
    """The tariff code this premises is on.

    A function of the premises id, the master seed and the published mix, and
    nothing else, so it does not depend on how many premises were exported, in
    what order, or on how many workers ran.
    """
    w = dict(weights) if weights else plan_mix()["weights"]
    codes = sorted(w)
    rng = export_generator(master_seed, EXPORT_TARIFF_PLAN_STREAM, premises_id)
    u = float(rng.random())
    cumulative = 0.0
    for code in codes:
        cumulative += w[code]
        if u < cumulative:
            return code
    return codes[-1]


# --------------------------------------------------------------------------- #
# the structure and the independent level check
# --------------------------------------------------------------------------- #

def _declaration(key: str) -> dict[str, Any]:
    import baile_nua.sources_registry  # noqa: F401  (declares the sources)
    from baile_nua.sources import REGISTRY, manifest_for

    if key not in REGISTRY:
        raise ExportError(
            f"{key} is not declared in sources_registry.py. The project rule "
            f"is that a source is declared before use; an undeclared source "
            f"cannot support a number on a published dataset."
        )
    src = REGISTRY[key]
    man = manifest_for(src) or {}
    return {
        "title": src.title, "url": src.url, "licence": src.licence,
        "publisher": src.publisher, "intended_use": src.intended_use,
        "model_development_exposure": src.model_development_exposure,
        "substitute_flag": src.substitute_flag,
        "sha256": man.get("sha256"),
        "bytes": man.get("bytes"),
        "retrieved_at": man.get("retrieved_at"),
        "retrieved_at_utc": man.get("retrieved_at_utc"),
    }


def price_cross_check() -> dict[str, Any]:
    """CSO TMEGB03 against the supplier schedule, for the simulated year.

    An independent check and not a restatement: the CSO publishes the price
    series and Electric Ireland publishes the schedule, so if the two agreed
    only because they were the same document the check would be worthless.
    Reported, never used to adjust the card: the card carries the published
    schedule, and this says whether that schedule's level is consistent with
    the national series.
    """
    import baile_nua.sources_registry  # noqa: F401  (declares the sources)
    from baile_nua.sources import require

    key = "cso.electricity.tmegb03_residential_electricity_prices"
    doc = json.loads(require(key).read_text("utf-8"))
    ids = list(doc["id"])
    size = [int(s) for s in doc["size"]]
    values = doc["value"]
    dims = [doc["dimension"][i] for i in ids]
    labels = [list(d["category"]["label"].values()) for d in dims]
    strides = [1] * len(size)
    for i in range(len(size) - 2, -1, -1):
        strides[i] = strides[i + 1] * size[i + 1]

    band_dc: dict[str, float] = {}
    for combo_index in range(strides[0] * size[0]):
        combo = [
            (combo_index // strides[i]) % size[i] for i in range(len(size))]
        names = [labels[i][combo[i]] for i in range(len(size))]
        flat = " | ".join(str(n) for n in names)
        if "band DC" not in flat or "2022" not in flat:
            continue
        if "including all taxes" not in flat:
            continue
        semester = next(n for n in names if "January" in str(n) or "July" in str(n))
        raw = (values[combo_index] if isinstance(values, list)
               else values.get(str(combo_index)))
        if raw is not None:
            band_dc[str(semester)] = float(raw)
    if not band_dc:
        raise ExportError(
            "TMEGB03 carries no 2022 band-DC price including all taxes, so "
            "the level check cannot be made. Refusing rather than skipping it "
            "silently."
        )
    schedule = TARIFF_RATES["flat_24h_eur_kwh"].value
    low, high = min(band_dc.values()), max(band_dc.values())
    return {
        "source_key": key,
        "band": "DC, household electricity consumption 2,500 kWh < 5,000 kWh",
        "pricing_basis": "including all taxes and levies",
        "published_2022_eur_kwh_by_semester": band_dc,
        "card_flat_rate_eur_kwh": schedule,
        "within_the_published_semesters": bool(low <= schedule <= high),
        "verdict": (
            "CONSISTENT: the schedule's 1 May 2022 flat rate lies between the "
            "CSO's published first-half and second-half 2022 prices for the "
            "band an Irish domestic meter sits in"
            if low <= schedule <= high else
            "OUTSIDE the published semester range - reported as a finding, "
            "not corrected: the card carries what the schedule published"
        ),
        "not_used_to_adjust_anything": (
            "the card's rate is the published schedule. This is a check on "
            "its level and nothing is fitted to it, which is why the source "
            "is declared exposure 'none'."
        ),
    }


def structure_evidence() -> dict[str, Any]:
    """The structural claims, read out of the declared source files.

    Read and not recalled.  ``sources.require`` re-hashes each file against
    the SHA-256 its manifest recorded at retrieval and refuses it if the bytes
    have moved, so the evidence below is tied to specific bytes.
    """
    import baile_nua.sources_registry  # noqa: F401  (declares the sources)
    from baile_nua.sources import require

    out: dict[str, Any] = {
        key: _declaration(key)
        for key in (*STRUCTURE_SOURCE_KEYS, *RATE_SOURCE_KEYS)
    }

    # ESB Networks: the market's own domestic class names, from the sheet
    # titles of the published workbook.
    import openpyxl

    path = require("esbn.rmds.slp_indexes_2022")
    book = openpyxl.load_workbook(path, read_only=True)
    try:
        profiles = {
            sheet: book[sheet].cell(row=1, column=1).value
            for sheet in book.sheetnames
        }
    finally:
        book.close()
    # "Non Domestic" contains "Domestic", so the filter excludes it
    # explicitly rather than by substring luck: LP6 is "Non MD Non Domestic
    # Night Saver" and would otherwise be counted as a domestic class.
    domestic = sorted(
        str(v) for v in profiles.values()
        if v and "Domestic" in str(v) and "Non Domestic" not in str(v))
    duplicated = sorted(
        title for title in {
            str(v).split(":", 1)[-1].strip() for v in profiles.values() if v
        }
        if sum(
            1 for v in profiles.values()
            if v and str(v).split(":", 1)[-1].strip() == title
        ) > 1
    )
    out["esbn.rmds.slp_indexes_2022"]["read"] = {
        "sheet_titles": profiles,
        "domestic_classes": domestic,
        "establishes": (
            "the Irish retail market publishes distinct DOMESTIC 24 Hour and "
            "DOMESTIC Night Saver load classes, so a flat class and a "
            "day/night class both exist"
        ),
        "duplicated_class_names_in_the_publication": duplicated,
        "duplicated_class_names_note": (
            "computed, not asserted. In the 2022 workbook LP3 is titled "
            "'Rural Domestic 24 Hour' and LP4 is titled 'Urban Domestic Night "
            "Saver', which duplicates LP2's title and leaves the rural "
            "night-saver class unnamed. That is a label in the PUBLISHER's "
            "file; it does not weaken the structural claim, and it is recorded "
            "here so a reader who counts four distinct domestic names and "
            "finds three is not left guessing."
        ),
    }

    # CSO: 'Tariff Group' is a published dimension, and its residential
    # categories are urban and rural.
    mec05 = json.loads(
        require("cso.electricity.mec05_by_tariff_group").read_text("utf-8"))
    groups: list[str] = []
    for dim in (mec05.get("dimension") or {}).values():
        if str(dim.get("label")) == "Tariff Group":
            groups = list((dim.get("category") or {}).get("label", {}).values())
    out["cso.electricity.mec05_by_tariff_group"]["read"] = {
        "tariff_groups": groups,
        "residential_groups": [g for g in groups if "Residential" in g],
        "establishes": (
            "'Tariff Group' is a published classification of Irish metered "
            "electricity, with Urban Residential and Rural Residential as its "
            "domestic categories. It carries NO rate, which is why the rates "
            "come from a published supplier schedule."
        ),
    }

    # DEAP: the clauses, and the fact that it carries no rates.
    require("seai.deap.manual_4_2_7")
    out["seai.deap.manual_4_2_7"]["read"] = {
        "quotes": list(DEAP_STRUCTURE_QUOTES),
        "establishes": (
            "an on-peak and an off-peak rate, a single nightly off-peak "
            "period, an export price distinct from the purchase price, and a "
            "metered operator-provided import/export arrangement"
        ),
        "carries_no_rates": (
            "DEAP names the SEAI Domestic Fuel Cost Comparison for every "
            "magnitude (p.65, p.70, p.81, p.140), and that publication is not "
            "in sources/. Its own export price, 'currently 0c', predates the "
            "Clean Export Guarantee and is superseded by CRU202454."
        ),
    }

    # The transcribed magnitudes, each with the wording it came from.
    out["_transcribed_magnitudes"] = {
        name: value.as_dict() for name, value in sorted(TARIFF_RATES.items())
    }
    out["_published_band_hours"] = {
        name: value.as_dict() for name, value in sorted(BAND_HOURS.items())
    }
    out["_transcription_rule"] = (
        "five of the seven rate sources are PDFs and are not machine-readable, "
        "so each figure is transcribed with its page and the published wording "
        "and a test asserts that wording is on that page of the declared file "
        "(whitespace removed, because the published PDFs' own text layer "
        "carries stray spaces inside numbers). The same rule the DEAP manual's "
        "substitute_flag states."
    )
    return out


# --------------------------------------------------------------------------- #
# the frame
# --------------------------------------------------------------------------- #

def _rate_schedule(
    code: str, tag: str, mix: dict[str, Any], flags: tuple[Any, ...],
) -> dict[str, Any]:
    plan = PLANS[code]
    standing = TARIFF_RATES[plan["standing_charge_key"]]
    return {
        "label": (
            "UNVALIDATED SIMULATION EVIDENCE. SYNTHETIC rate card: the unit "
            "rates, standing charges, export range and connection capacity "
            "are published figures, cited field by field; the supplier name, "
            "the plan assignment and the premises are synthetic."
        ),
        "tariff_code": code,
        "tariff_kind": plan["tariff_kind"],
        "currency": "EUR, VAT-inclusive, as the published schedule states it",
        "band_clock": BAND_CLOCK,
        "bands": plan["bands"],
        "band_hours_source": {
            name: value.as_dict() for name, value in sorted(BAND_HOURS.items())
        },
        "standing_charge_eur_day": _standing_per_day(
            plan["standing_charge_key"]),
        "standing_charge_source": standing.as_dict(),
        "standing_charge_derivation": (
            f"the published annual charge divided by {DAYS_PER_YEAR}"),
        "export_rate_eur_kwh": EXPORT_RATE_EUR_KWH,
        "export_rate_source": {
            "rule": "the midpoint of the CRU's published range",
            "range_low": TARIFF_RATES["export_range_low_eur_kwh"].as_dict(),
            "range_high": TARIFF_RATES["export_range_high_eur_kwh"].as_dict(),
            "regulated_floor": TARIFF_RATES["export_floor_eur_kwh"].as_dict(),
        },
        "max_import_kw_source": {
            **TARIFF_RATES["standard_domestic_connection_kva"].as_dict(),
            "conversion": (
                "published in kVA; the schema declares kW, and the card takes "
                "unity power factor. Stated rather than left implicit."
            ),
        },
        "rate_schedule_vintage": plan["rate_schedule_vintage"],
        "contemporaneous_with_the_simulated_year": plan[
            "contemporaneous_with_the_simulated_year"],
        "structure_basis": plan["structure_basis"],
        "structure_source_keys": list(STRUCTURE_SOURCE_KEYS),
        "rate_source_keys": list(RATE_SOURCE_KEYS),
        "plan_mix": mix,
        "assumption_flags": {
            tag: [
                {"flag_id": f.flag_id, "subject": f.subject,
                 "assumed": f.assumed, "retires_if": f.retires_if,
                 "verdict": f.verdict, "verdict_note": f.verdict_note,
                 "search_terms": list(f.search_terms),
                 "sources": list(f.sources),
                 "owning_step": f.owning_step,
                 "near_misses": list(f.near_misses)}
                for f in flags
            ],
            "still_open": sorted(
                f.flag_id for f in flags if f.verdict != "RETIRED"),
            "retired_by_a_fetched_source": sorted(
                f.flag_id for f in flags if f.verdict == "RETIRED"),
        },
        "the_engine_does_not_read_this": (
            "D27 is a record only. No module under engine/, physics/, "
            "devices/ or behaviour/ imports or names baile_nua.export.tariffs, "
            "and control_mode is unchanged. Asserted by "
            "test_d27_the_engine_cannot_read_the_tariff over the source tree, "
            "which is also why every source above is declared "
            "model_development_exposure='none'."
        ),
    }


def build_d27_frame(ctx: RunContext) -> pd.DataFrame:
    """One contract row per premises: a static card, open-ended from t0."""
    tag = assumption_tag()
    mix = plan_mix()
    flags = _assumptions()
    cards = {
        code: json.dumps(_rate_schedule(code, tag, mix, flags), sort_keys=True)
        for code in PLANS
    }
    rows: list[dict[str, Any]] = []
    for household_id, building in sorted(ctx.slice.buildings.items()):
        premises_id = building.premises_id
        code = plan_for_premises(premises_id, ctx.master_seed, mix["weights"])
        pv = ctx.slice.pv.get(household_id)
        # The export capacity is the installed inverter rating from the run's
        # OWN DER stock. The notification PROCESS is not modelled, so the
        # notified capacity is taken to equal what is installed, and a
        # premises with no PV has none - that is read off the run, not assumed.
        max_export_kw = float(getattr(pv, "inverter_kw", 0.0) or 0.0)
        rows.append({
            "premises_id": premises_id,
            "valid_from": ctx.t0,
            "valid_to": None,
            "supplier": SUPPLIER,
            "tariff_code": code,
            "tariff_kind": PLANS[code]["tariff_kind"],
            "rate_schedule": cards[code],
            "standing_charge_eur_day": _standing_per_day(
                PLANS[code]["standing_charge_key"]),
            "export_rate_eur_kwh": EXPORT_RATE_EUR_KWH,
            "max_import_kw": MAX_IMPORT_KW,
            "max_export_kw": max_export_kw,
            "der_notification_ref": (
                f"SYNTH-DER-{premises_id}" if max_export_kw > 0 else None),
            "flex_contract_terms": None,
            "trial_arm": None,
        })
    if not rows:
        raise ExportError(
            "D27: the run's slice carries no building, so there is no premises "
            "to put a contract on."
        )
    frame = pd.DataFrame(rows)
    # Two optional fields are empty for every premises, and an all-None object
    # column reaches Parquet as Arrow `null`, which matches no declared type.
    # They are cast to `string`, the representation every other json field in
    # this dataset uses (serialised JSON), so an empty optional column is
    # typed the same way a populated one would be. Typed, not filled: the
    # values stay null, which is the finding.
    for column in ("flex_contract_terms", "trial_arm", "der_notification_ref"):
        frame[column] = frame[column].astype("string")
    return frame


def export_d27(ctx: RunContext) -> dict[str, Any]:
    """D27, as a record only: a sourced rate card the engine cannot read."""
    tag = assumption_tag()
    frame = build_d27_frame(ctx)
    evidence = structure_evidence()
    check = price_cross_check()
    mix = plan_mix()
    flags = _assumptions()
    open_flags = [f for f in flags if f.verdict != "RETIRED"]
    return emit(
        frame, "D27", ctx,
        source=(
            "three synthetic rate cards whose every magnitude is a published "
            "figure from a declared source - Electric Ireland's 1 May 2022 "
            "and 1 November 2024 price schedules, CRU202454 for the export "
            "range and floor, ESB Networks' Basis of Charges for the "
            "connection capacity, CSO HEBEU88 for the plan mix - with the "
            "structure corroborated by the ESB Networks load profiles, the "
            "DEAP manual and CSO MEC05, and the level checked against CSO "
            "TMEGB03"
        ),
        conversions=[
            {"field": "tariff_code",
             "from": "counter-based draw over the three plans, keyed by the "
                     "master seed and the premises id, weighted by HEBEU88's "
                     "published urban tariff-type shares",
             "stream_id": EXPORT_TARIFF_PLAN_STREAM,
             "note": "declared in export/, not appended to rng.Stream, which "
                     "is inside the freeze"},
            {"field": "standing_charge_eur_day",
             "from": "the plan's published ANNUAL urban standing charge "
                     f"divided by {DAYS_PER_YEAR}"},
            {"field": "export_rate_eur_kwh",
             "from": "the midpoint of the CRU's published 16-25 c/kWh range; "
                     "both ends and the regulated floor of zero are carried "
                     "in rate_schedule so a reader can take a different point"},
            {"field": "max_import_kw",
             "from": "ESB Networks' published standard domestic connection "
                     "capacity of 12 kVA, at unity power factor"},
            {"field": "max_export_kw",
             "from": "the installed PV inverter rating on the run's own DER "
                     "stock; 0.0 where the premises has no PV",
             "note": "the notification PROCESS is not modelled, so the "
                     "notified capacity is taken to equal what is installed"},
            {"field": "valid_from",
             "from": "the run's t0, read from its own timestamped parts"},
        ],
        limitations=[
            "RECORD ONLY: the engine does not read this dataset and "
            "control_mode is unchanged. No module under engine/, physics/, "
            "devices/ or behaviour/ may import this module, which is why all "
            "seven rate sources are declared exposure 'none'.",
            f"Three assumptions remain, each flagged {tag} with a search "
            f"record: {', '.join(f.flag_id for f in open_flags)}. "
            f"A-92: the day/night plan's band hours are carried from the "
            f"smart tariff's published night window, because the 2022 "
            f"NightSaver schedule publishes rates and no hours. "
            f"A-97: the three-band plan's rates and hours are from a November "
            f"2024 schedule - no three-band domestic plan was published in "
            f"May 2022 - so comparing ACROSS plans in this dataset mixes two "
            f"price years. A-96: flex_contract_terms and trial_arm are null.",
            "Five earlier assumptions are RETIRED by fetched sources (A-90 "
            "rates, A-91 mix, A-93 standing charge, A-94 export rate, A-95 "
            "connection capacity) and kept in the record with the source that "
            "closed each.",
            "The supplier name is synthetic even though the rates are a real "
            "published schedule: the plan mix and the per-premises assignment "
            "are not that supplier's, so presenting the rows as its customer "
            "records would be a claim about the company. The rate source is "
            "cited field by field instead.",
            "Five of the seven rate sources are PDFs. Their figures are "
            "transcribed by hand with page and published wording, per the "
            "project's rule for a reference that is not machine-readable, and "
            "a test asserts each wording against the fetched bytes.",
        ],
        extra={
            "d27_record_only": True,
            "d27_control_mode_unchanged": True,
            "d27_assumption_tag": tag,
            "d27_assumption_flags": [
                {"flag_id": f.flag_id, "subject": f.subject,
                 "verdict": f.verdict, "retires_if": f.retires_if,
                 "search_terms": list(f.search_terms),
                 "sources": list(f.sources),
                 "verdict_note": f.verdict_note,
                 "owning_step": f.owning_step}
                for f in flags
            ],
            "d27_open_assumption_flags": [f.flag_id for f in open_flags],
            "d27_retired_assumption_flags": [
                f.flag_id for f in flags if f.verdict == "RETIRED"],
            "d27_structure_evidence": evidence,
            "d27_price_cross_check": check,
            "d27_plan_mix": mix,
            "d27_plan_counts": (
                frame["tariff_code"].value_counts().sort_index().to_dict()),
            "d27_stream_id": EXPORT_TARIFF_PLAN_STREAM,
        },
    )
