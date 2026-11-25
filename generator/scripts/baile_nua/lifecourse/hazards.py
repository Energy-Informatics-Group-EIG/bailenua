"""WP5 life-course hazards, every one either published or declared (D24, I-040).

Design 5.3 lists the ten-year life course - births, deaths, moves in and out,
partnering, separation, children leaving, employment change, health states,
retrofits and DER adoption - and gives **no numbers for any of them**. U30
flag A-25 owns that gap and names this step as the one that has to close it.

The rule from I-040 is that an ``[A]`` flag records *what was searched*, not
merely that it is an assumption. :data:`SEARCH_RECORD` is that record: every
term put to PxStat's 13,086-table catalogue, the number of tables it returned,
and what the hit was actually good for. Several of those searches returned
tables that look right and are not - a stock where a transition rate is
needed - and the record says so, because "no rate is published" and "I did not
find the words" are different claims (A-35's lesson).

What came back, and in what form:

===========================  ==========  ===================================
hazard                       form        source
===========================  ==========  ===================================
birth                        RATE        VSA104 age-specific fertility, by
                                         NUTS 3 region; VSA36 parity split
death                        RATE        VSA08 deaths / PEA01 population,
                                         same year and same age bands
partnering                   RATE        VSA49 marriages per 1,000 by
                                         single year of age and sex
employment change            RATE        JCA01 separations / employees by
                                         single year of age and sex
vacancy (equilibrium)        RATE        VAC04 Cork County vacancy rate
vacancy (gross flows)        RATE        VAC17 dwellings entering/leaving
net migration                NET RATE    EP006 Cork, per 1,000
DER / retrofit               PREVALENCE  HEBEU37 installations in place
health state 50+             PREVALENCE  HSPAE122 chronic conditions
---------------------------  ----------  -----------------------------------
gross household turnover     [A]         bounded by VAC17 / VAC04
union dissolution            [A]         bounded by CD565 stock
child leaves home            [A]         bounded by EA036 age-20 stock
health onset under 50        [A]         HSPAE122 starts at 50
annual retrofit adoption     [A]         bounded by HEBEU37 prevalence
===========================  ==========  ===================================

A PREVALENCE is not a hazard. Where the published quantity is a stock or a
prevalence, the annual rate is ``[A]`` and the published number constrains
what ten years of it is allowed to add up to - which is a weaker claim than a
sourced rate, and is labelled as such rather than dressed up as one.
"""

from __future__ import annotations

import dataclasses
import functools
import json
from typing import Any

from baile_nua.sources import REGISTRY, require

__all__ = [
    "SEARCH_RECORD",
    "HAZARD_SOURCES",
    "HazardSource",
    "AssumedHazard",
    "ASSUMED_HAZARDS",
    "fertility_rates_by_age",
    "parity_shares_by_age",
    "death_rates_by_age_sex",
    "marriage_rates_by_age_sex",
    "job_separation_rate_by_age_sex",
    "net_migration_per_1000",
    "vacancy_rate_cork_county",
    "vacancy_flow_rates",
    "der_prevalence",
    "chronic_condition_prevalence_50_plus",
    "divorced_separated_share",
    "age_20_living_with_parents",
    "EVIDENCE_TAG",
    "DONOR_NOTE",
]

EVIDENCE_TAG = "[A]"

DONOR_NOTE = (
    "No life-course hazard here is transferred from another country: every "
    "sourced rate is Irish, and every assumed one is bounded by an Irish "
    "published quantity. U04 does not apply to this module."
)


# --------------------------------------------------------------------------- #
# The search record (I-040). Written from the searches actually run, with the
# hit counts they actually returned.
# --------------------------------------------------------------------------- #

#: ``(search term, tables returned, what it was good for)``.
SEARCH_RECORD: tuple[tuple[str, int, str], ...] = (
    # --- found a usable RATE ---
    (r"[Ff]ertility [Rr]ate", 3,
     "VSA104 fertility rates by age group and NUTS 3 region - an age-specific "
     "RATE, and regional, so the South-West column needs no denominator of "
     "ours. ADOPTED for the birth hazard."),
    (r"age of mother", 9,
     "VSA36 births by age of mother and previous liveborn children - counts, "
     "so they give the PARITY SHARE inside an age group, which splits the "
     "VSA104 rate. ADOPTED for the parity dimension."),
    (r"[Dd]eath [Rr]ate", 10,
     "VSA09 'Deaths and Death Rates per 1,000 population' is State-level and "
     "ALL AGES - a crude rate, which cannot age a population. Searching "
     "'Deaths' for tables carrying both an Age and a Sex dimension found "
     "VSA08, which is counts by age group and sex. ADOPTED as the numerator."),
    (r"[Ll]ife [Tt]able", 1,
     "CEPHA05, the Decennial Life Table, is the only life table PxStat "
     "publishes and its last year is 1990. REJECTED: 1990 mortality cannot "
     "age a 2022 population, and the error is not small."),
    (r"Population Estimates by age and sex", 8,
     "PEA01 population estimates by age group and sex, on the SAME age-band "
     "code as VSA08 (C02076V02508). ADOPTED as the denominator, which makes "
     "the death rate a ratio of two published numbers."),
    (r"Marriage Rate", 1,
     "VSA49 marriages per 1,000 males and per 1,000 females by single year of "
     "age. ADOPTED for partnering; already declared under U30."),
    (r"job churn", 8,
     "JCA01 job churn components for employees by year, sex, single year of "
     "age and employee status, with Separations and Hirings as components. "
     "ADOPTED for employment change."),
    (r"[Vv]acan", 72,
     "VAC17 'Vacancy Flows' publishes dwellings BECOMING VACANT and MOVING "
     "OUT OF VACANCY quarterly - the only vacancy table that is a flow and "
     "not a stock. VAC04 gives the Cork County vacancy rate quarterly. Both "
     "ADOPTED. C0674 was fetched first and discarded: it is the 2006 census "
     "vintage, which the registry entry had mislabelled as 2022."),
    (r"energy effic", 6,
     "HEBEU37 energy efficiency installations IN PLACE in the home, by type "
     "(heat pump, PV, thermal solar, smart controls, battery). A PREVALENCE, "
     "not an adoption rate. ADOPTED as a ten-year cumulative bound only."),
    (r"chronic", 11,
     "HSPAE122 multiple chronic conditions among people aged 50 and over. A "
     "PREVALENCE, and it starts at 50. ADOPTED as a bound for 50+ only."),

    # --- found something that LOOKS right and is not ---
    (r"internal migration", 1,
     "PEB08 projected annual births, deaths, internal and international "
     "migration. A PROJECTION, and net. Not a hazard."),
    (r"\bmigration\b / EP006", 3,
     "EP006 annual estimated NET migration per 1,000 of average population by "
     "county. Net only: it constrains the DIFFERENCE between the two gross "
     "flows and neither of them. ADOPTED as a net constraint; the gross "
     "turnover rate stays [A] (A-25b)."),
    (r"\bseparat", 20,
     "CD565 divorced and separated population by age group and sex - a census "
     "STOCK. JCA03/JCA04 'Separations' are JOB separations, not relationship "
     "ones. No separation or divorce transition rate for Ireland. CD565 "
     "ADOPTED as a bound only (A-25c)."),
    (r"\bdivorce", 1,
     "MIP21 carries European divorce rates; the Irish entries are the same "
     "census stocks. Still no transition rate."),
    (r"living with parents", 4,
     "EA036 population aged 20 still living with parents, 2011 and 2016 - a "
     "COUNT at a single age, and PEA01's finest band is 20-24, so even the "
     "denominator is approximate. ADOPTED as a weak bound only (A-25d)."),
    (r"labour force", 262,
     "All census stocks - participation rates and employment status at a "
     "point in time. A stock gives no transition rate. JCA01 (above) is the "
     "one that does."),
    (r"\bunemploy", 133,
     "Same: stocks and rates at a point in time, not flows between states."),

    # --- found nothing ---
    (r"retrofit", 0,
     "ZERO tables across all 13,086. PxStat publishes no retrofit rate under "
     "that word. HEBEU37's prevalence is the nearest published quantity and "
     "it is not a rate, so annual retrofit adoption is [A] (A-25f)."),
    (r"household formation", 0, "ZERO tables."),
    (r"labour force transition", 0,
     "ZERO tables - but this is a PHRASE failure, not evidence of absence: "
     "'job churn' found the flows (I-046's lesson). Recorded so the next "
     "reader does not repeat the phrase and conclude nothing exists."),
    (r"transition", 1,
     "One unrelated table (IEWA23). Confirms the vocabulary is 'churn', "
     "'flows' and 'separations', not 'transition'."),
    (r"age.specific fertility", 0,
     "ZERO - another phrase failure. '[Ff]ertility [Rr]ate' returns VSA104, "
     "which IS age-specific."),
    (r"\bhires?\b", 0,
     "ZERO for the word; JCA01 spells the component 'Hirings'."),
    (r"[Ee]xpectation of [Ll]ife", 0, "ZERO for the phrase; CEPHA05 calls it "
     "'Life Expectation' inside the STATISTIC dimension."),
)


@dataclasses.dataclass(frozen=True)
class HazardSource:
    """One life-course hazard that has a published source."""

    hazard: str
    source_key: str
    #: ``rate`` | ``net_rate`` | ``prevalence`` | ``stock_bound``
    form: str
    note: str

    @property
    def is_a_rate(self) -> bool:
        return self.form == "rate"


HAZARD_SOURCES: tuple[HazardSource, ...] = (
    HazardSource("birth", "cso.vitalstats.vsa104_fertility_rates_by_age", "rate",
                 "age-specific fertility per 1,000 women, South-West region"),
    HazardSource("birth_parity", "cso.vitalstats.vsa36_births_by_age_and_parity",
                 "prevalence", "parity shares within an age group"),
    HazardSource("death", "cso.vitalstats.vsa08_deaths_by_age_and_sex", "rate",
                 "numerator; denominator is PEA01 on the same age bands"),
    HazardSource("death_denominator",
                 "cso.population.pea01_population_estimates_by_age_sex", "rate",
                 "population by age group and sex, same year"),
    HazardSource("partnering", "cso.vitalstats.vsa49_marriage_rates_by_age", "rate",
                 "marriages per 1,000 by single year of age and sex"),
    HazardSource("employment_change", "cso.labour.jca01_job_churn_by_age_sex", "rate",
                 "separations / employees by single year of age and sex"),
    HazardSource("move_net", "cso.migration.ep006_net_migration_per_1000", "net_rate",
                 "net migration per 1,000, Cork; constrains the difference only"),
    HazardSource("vacancy_equilibrium", "cso.housing.vac04_local_authority_vacancy_rates",
                 "rate", "Cork County percentage of dwellings vacant"),
    HazardSource("vacancy_flows", "cso.housing.vac17_vacancy_flows", "rate",
                 "gross quarterly flows into and out of vacancy, national"),
    HazardSource("vacancy_local", "cso.housing.f2095_housing_stock_vacancy_by_ed",
                 "rate", "vacancy rate at electoral-division geography"),
    HazardSource("der_adoption", "cso.energy.hebeu37_efficiency_installations",
                 "prevalence", "installations in place, 2024; a cumulative bound"),
    HazardSource("health_state", "cso.health.hspae122_multiple_chronic_conditions",
                 "prevalence", "chronic conditions at 50+; a stock to reproduce"),
    HazardSource("union_dissolution_bound",
                 "cso.census.cd565_divorced_and_separated_population", "stock_bound",
                 "divorced and separated stock by age group and sex"),
    HazardSource("child_leaves_home_bound",
                 "cso.census.ea036_age_20_living_with_parents", "stock_bound",
                 "count aged 20 living with parents; denominator approximate"),
)


@dataclasses.dataclass(frozen=True)
class AssumedHazard:
    """A hazard with no published rate: the value, why, and what bounds it."""

    flag: str
    hazard: str
    value: float
    units: str
    why_assumed: str
    bounded_by: str
    bound_check: str


#: The five hazards design 5.3 needs and PxStat does not publish as a rate.
#: Each value is a round number chosen for transparency, NOT fitted: nothing in
#: this module is tuned against model output.
ASSUMED_HAZARDS: tuple[AssumedHazard, ...] = (
    AssumedHazard(
        flag="A-25b",
        hazard="gross household move-out rate",
        value=0.065,
        units="per household per year",
        why_assumed=(
            "EP006 publishes NET migration only. A net rate of +0.6 per 1,000 "
            "(Cork, 2011-2016) is consistent with any pair of gross flows that "
            "differ by that much, including zero and zero."
        ),
        bounded_by="VAC17 gross vacancy flows against the national dwelling stock",
        bound_check="vacancy_flow_rates",
    ),
    AssumedHazard(
        flag="A-25c",
        hazard="union dissolution rate",
        value=0.009,
        units="per couple per year",
        why_assumed=(
            "No separation or divorce transition rate is published for Ireland; "
            "CD565 is a census stock and MIP21's Irish entries are the same."
        ),
        bounded_by="CD565 divorced-and-separated share of the 35-54 population",
        bound_check="divorced_separated_share",
    ),
    AssumedHazard(
        flag="A-25d",
        hazard="child leaves the parental home",
        value=0.115,
        units="per resident child aged 18-34 per year",
        why_assumed=(
            "EA036 publishes a count at a single age (20) for two census years "
            "and nothing else; there is no hazard over 18-34."
        ),
        bounded_by="EA036 share still living with parents at 20",
        bound_check="age_20_living_with_parents",
    ),
    AssumedHazard(
        flag="A-25e",
        hazard="chronic health-state onset under 50",
        value=0.012,
        units="per person per year",
        why_assumed=(
            "HSPAE122, the only chronic-condition prevalence found, starts at "
            "50. Nothing published covers onset below it."
        ),
        bounded_by="HSPAE122 1-or-more prevalence at 50+, which onset must build to",
        bound_check="chronic_condition_prevalence_50_plus",
    ),
    AssumedHazard(
        flag="A-25f",
        hazard="annual retrofit / DER adoption rate",
        value=0.025,
        units="per dwelling per year, per measure",
        why_assumed=(
            "Zero tables for 'retrofit'. HEBEU37 is a 2024 PREVALENCE of "
            "installations in place, which fixes the cumulative total and not "
            "the annual rate."
        ),
        bounded_by="HEBEU37 prevalence by measure",
        bound_check="der_prevalence",
    ),
)


# --------------------------------------------------------------------------- #
# Reading. Offset arithmetic rather than a label cross-product: JCA01 has
# 16.8 million cells and itertools.product over it is gigabytes.
# --------------------------------------------------------------------------- #

class HazardSourceError(RuntimeError):
    pass


class _Table:
    """A JSON-stat cube addressed by dimension LABEL, not by code."""

    def __init__(self, key: str) -> None:
        self.key = key
        doc = json.loads(require(key).read_text(encoding="utf-8"))
        self.ids: list[str] = doc["id"]
        self.size: list[int] = doc["size"]
        self.labels: dict[str, list[str]] = {
            i: list(doc["dimension"][i]["category"]["label"].values())
            for i in self.ids
        }
        self._value = doc["value"]
        self.sha256 = str(
            json.loads(REGISTRY[key].manifest_path.read_text(encoding="utf-8"))["sha256"]
        )

    def get(self, **sel: str) -> float | None:
        if set(sel) != set(self.ids):
            raise HazardSourceError(
                f"{self.key}: selector names {sorted(sel)} but the cube's "
                f"dimensions are {self.ids}. Address every dimension."
            )
        off = 0
        for i, n in zip(self.ids, self.size):
            labs = self.labels[i]
            want = sel[i]
            try:
                k = labs.index(want)
            except ValueError as exc:
                raise HazardSourceError(
                    f"{self.key}: dimension {i} has no label {want!r}. The CSO "
                    f"has re-labelled it; fix the reader rather than reaching "
                    f"for a nearby cell. First few: {labs[:4]}"
                ) from exc
            off = off * n + k
        v = self._value[off] if isinstance(self._value, list) else self._value.get(str(off))
        return None if v is None else float(v)

    def stat(self, n: int = 0) -> str:
        return self.labels["STATISTIC"][n]


@functools.lru_cache(maxsize=None)
def _table(key: str) -> _Table:
    return _Table(key)


#: The region the town sits in. Cobh is in Cork, which is NUTS 3 South-West.
NUTS3_REGION = "South-West"
COUNTY = "Cork"
LOCAL_AUTHORITY = "Cork County Council"

#: Years. Each is the latest the table actually carries, read at import rather
#: than hard-coded, except where a table's last year is unusable (noted).
FERTILITY_YEAR_POLICY = "latest year VSA104 carries for the region"
DEATH_YEAR_POLICY = (
    "latest year carried by BOTH VSA08 and PEA01. VSA08 ends in 2018, which is "
    "also the last pre-pandemic year, so the mortality schedule is not a "
    "COVID-era one."
)


def _latest_year(t: _Table, dim: str = "TLIST(A1)") -> str:
    return t.labels[dim][-1]


def fertility_rates_by_age(
    *, region: str = NUTS3_REGION, year: str | None = None
) -> dict[str, float]:
    """VSA104 age-specific fertility rates, per 1,000 women in the band."""
    t = _table("cso.vitalstats.vsa104_fertility_rates_by_age")
    y = year or _latest_year(t)
    out: dict[str, float] = {}
    for band in t.labels["C02076V03371"]:
        if band == "All ages":
            continue
        v = t.get(**{"STATISTIC": "Age specific fertility rates",
                     "TLIST(A1)": y, "C02076V03371": band,
                     "C03788V04538": region})
        if v is not None:
            out[band] = v
    if not out:
        raise HazardSourceError(
            f"VSA104 has no fertility rates for {region!r} in {y}."
        )
    return out


def parity_shares_by_age(*, year: str | None = None) -> dict[str, dict[int, float]]:
    """VSA36 parity composition inside each age band, as shares summing to 1."""
    t = _table("cso.vitalstats.vsa36_births_by_age_and_parity")
    y = year or _latest_year(t)
    parities = [p for p in t.labels["C01934V02366"] if p.isdigit()]
    out: dict[str, dict[int, float]] = {}
    for age in t.labels["C02076V02508"]:
        counts: dict[int, float] = {}
        for p in parities:
            v = t.get(**{"STATISTIC": "Total Births", "TLIST(A1)": y,
                         "C02076V02508": age, "C01934V02366": p})
            if v:
                counts[int(p)] = v
        tot = sum(counts.values())
        if tot > 0:
            out[age] = {k: v / tot for k, v in counts.items()}
    return out


def death_rates_by_age_sex(*, year: str | None = None) -> dict[tuple[str, str], float]:
    """Deaths per 1,000 by age band and sex: VSA08 numerator / PEA01 denominator.

    Both tables carry the same age-band dimension code (C02076V02508), so the
    bands are not mapped by hand - a mapping is where this kind of thing goes
    wrong (I-047).
    """
    dt = _table("cso.vitalstats.vsa08_deaths_by_age_and_sex")
    pt = _table("cso.population.pea01_population_estimates_by_age_sex")
    y = year or _latest_year(dt)
    if y not in pt.labels["TLIST(A1)"]:
        raise HazardSourceError(
            f"PEA01 does not carry {y}, so the death rate for that year would "
            f"mix two periods."
        )
    out: dict[tuple[str, str], float] = {}
    for sex in ("Male", "Female"):
        for band in dt.labels["C02076V02508"]:
            if band == "All ages":
                continue
            if band not in pt.labels["C02076V02508"]:
                raise HazardSourceError(
                    f"VSA08 band {band!r} is absent from PEA01; the bands have "
                    f"diverged and the ratio would be wrong."
                )
            d = dt.get(**{"STATISTIC": dt.stat(), "TLIST(A1)": y,
                          "C02199V02655": sex, "C02478V03568": "Total Deaths",
                          "C02076V02508": band})
            # PEA01 is published in THOUSANDS of persons.
            p = pt.get(**{"STATISTIC": pt.stat(), "TLIST(A1)": y,
                          "C02076V02508": band, "C02199V02655": sex})
            if d is None or not p:
                continue
            out[(sex, band)] = 1000.0 * d / (p * 1000.0)
    return out


def marriage_rates_by_age_sex(*, year: str | None = None) -> dict[tuple[str, str], float]:
    """VSA49 marriages per 1,000 by single year of age and sex."""
    t = _table("cso.vitalstats.vsa49_marriage_rates_by_age")
    y = year or _latest_year(t)
    out: dict[tuple[str, str], float] = {}
    for sex, stat in (("Male", "Marriages per 1000 Males"),
                      ("Female", "Marriages per 1000 Females")):
        for age in t.labels["C02076V02508"]:
            v = t.get(**{"C02076V02508": age, "TLIST(A1)": y, "STATISTIC": stat})
            if v is not None:
                out[(sex, age)] = v
    return out


def job_separation_rate_by_age_sex(
    *, year: str | None = None, sector: str = "All NACE economic sectors"
) -> dict[tuple[str, str], float]:
    """JCA01 separations divided by employees, by single year of age and sex."""
    t = _table("cso.labour.jca01_job_churn_by_age_sex")
    y = year or _latest_year(t)
    out: dict[tuple[str, str], float] = {}
    for sex in ("Male", "Female"):
        for age in t.labels["C02076V02508"]:
            base = {"STATISTIC": "Employment records", "TLIST(A1)": y,
                    "C02199V02655": sex, "C02687V03254": sector,
                    "C02076V02508": age}
            emp = t.get(**base, C02749V03318="Employees (Hirings + Job stayers)")
            sep = t.get(**base, C02749V03318="Separations")
            if emp and sep is not None:
                out[(sex, age)] = sep / emp
    return out


def net_migration_per_1000(*, county: str = COUNTY) -> dict[str, float]:
    """EP006 net migration per 1,000 of average population, by intercensal period."""
    t = _table("cso.migration.ep006_net_migration_per_1000")
    y = _latest_year(t)
    out: dict[str, float] = {}
    for period in t.labels["C02691V03258"]:
        v = t.get(**{"STATISTIC": t.stat(), "C02691V03258": period,
                     "C02779V03348": county, "TLIST(A1)": y})
        if v is not None:
            out[period] = v
    return out


def vacancy_rate_cork_county() -> dict[str, float]:
    """VAC04 percentage of dwellings vacant, Cork County Council, by quarter."""
    t = _table("cso.housing.vac04_local_authority_vacancy_rates")
    out: dict[str, float] = {}
    for q in t.labels["TLIST(Q1)"]:
        v = t.get(**{"STATISTIC": t.stat(), "TLIST(Q1)": q,
                     "C03789V04537": LOCAL_AUTHORITY})
        if v is not None:
            out[q] = v
    return out


def vacancy_flow_rates() -> dict[str, Any]:
    """VAC17 gross vacancy flows, and the turnover they imply.

    The flows are counts of dwellings; dividing by the national stock implied
    by VAC04's rate would mix two geographies, so what is returned is the
    flow itself plus the RATIO of the two directions, which is scale-free and
    is what the vacancy chain has to balance.
    """
    t = _table("cso.housing.vac17_vacancy_flows")
    qs = t.labels["TLIST(Q1)"]
    becoming, leaving = [], []
    for q in qs:
        a = t.get(**{"STATISTIC": "Dwellings becoming vacant", "TLIST(Q1)": q,
                     "C03788V04528": "Ireland"})
        b = t.get(**{"STATISTIC": "Dwellings moving out of vacancy",
                     "TLIST(Q1)": q, "C03788V04528": "Ireland"})
        if a is not None and b is not None:
            becoming.append(a)
            leaving.append(b)
    n = len(becoming)
    mb = sum(becoming) / n
    ml = sum(leaving) / n
    return {
        "quarters": n,
        "mean_becoming_vacant": mb,
        "mean_leaving_vacancy": ml,
        "balance_ratio": mb / ml,
        "annual_becoming_vacant": mb * 4.0,
        "note": (
            "A balance ratio near 1.0 is the equilibrium the chain has to hold: "
            "homes leave vacancy as fast as they enter it, so the vacancy stock "
            "is flat over ten years."
        ),
    }


def der_prevalence(*, year: str | None = None) -> dict[str, float]:
    """HEBEU37 share of homes with each installation in place, as fractions."""
    t = _table("cso.energy.hebeu37_efficiency_installations")
    y = year or _latest_year(t)
    out: dict[str, float] = {}
    for kind in t.labels["C04534V05318"]:
        v = t.get(**{"STATISTIC": t.stat(), "TLIST(A1)": y,
                     "C02199V02655": "Both sexes", "C04534V05318": kind})
        if v is not None:
            out[kind] = v / 100.0
    return out


def chronic_condition_prevalence_50_plus(*, year: str | None = None) -> dict[str, float]:
    """HSPAE122 prevalence of 1+, 2+, 3+ and 4+ chronic conditions at 50 and over."""
    t = _table("cso.health.hspae122_multiple_chronic_conditions")
    y = year or _latest_year(t)
    out: dict[str, float] = {}
    for stat in t.labels["STATISTIC"]:
        v = t.get(**{"STATISTIC": stat, "TLIST(A1)": y, "C03788V04528": "Ireland"})
        if v is not None:
            out[stat] = v / 100.0
    return out


def divorced_separated_share() -> dict[str, float]:
    """CD565 divorced-and-separated stock by age band, over PEA01 population.

    A bound, not a hazard: CD565 counts people who ARE separated, which ten
    years of an assumed dissolution rate has to be consistent with.
    """
    t = _table("cso.census.cd565_divorced_and_separated_population")
    pt = _table("cso.population.pea01_population_estimates_by_age_sex")
    y = _latest_year(t)
    if y not in pt.labels["TLIST(A1)"]:
        raise HazardSourceError(f"PEA01 does not carry CD565's year {y}.")
    # PEA01's bands are 5-year; CD565's are 10-year. Pair them explicitly.
    pairs = {
        "25 - 34 years": ("25 - 29 years", "30 - 34 years"),
        "35 - 44 years": ("35 - 39 years", "40 - 44 years"),
        "45 - 54 years": ("45 - 49 years", "50 - 54 years"),
        "55 - 64 years": ("55 - 59 years", "60 - 64 years"),
    }
    out: dict[str, float] = {}
    for band, sub in pairs.items():
        num = 0.0
        for stat in t.labels["STATISTIC"]:
            v = t.get(**{"C02076V03371": band, "C02199V02655": "Both sexes",
                         "TLIST(A1)": y, "STATISTIC": stat})
            if v:
                num += v
        den = 0.0
        for s in sub:
            p = pt.get(**{"STATISTIC": pt.stat(), "TLIST(A1)": y,
                          "C02076V02508": s, "C02199V02655": "Both sexes"})
            if p:
                den += p * 1000.0
        if den:
            out[band] = num / den
    out["_census_year"] = float(y)
    return out


def age_20_living_with_parents() -> dict[str, float]:
    """EA036 count at age 20 over an APPROXIMATE denominator.

    PEA01's finest band is 20-24, so the denominator is that band divided by
    five. The approximation is the reason A-25d is a weak bound and is
    labelled one.
    """
    t = _table("cso.census.ea036_age_20_living_with_parents")
    pt = _table("cso.population.pea01_population_estimates_by_age_sex")
    y = _latest_year(t)
    n = t.get(**{"STATISTIC": t.stat(), "C02704V03272": "All persons",
                 "C02728V03296": "All socio-economic groups", "TLIST(A1)": y})
    p = pt.get(**{"STATISTIC": pt.stat(), "TLIST(A1)": y,
                  "C02076V02508": "20 - 24 years", "C02199V02655": "Both sexes"})
    den = (p * 1000.0) / 5.0
    return {
        "year": float(y),
        "count_age_20": float(n),
        "approx_cohort": den,
        "share": float(n) / den,
        "denominator_note": (
            "PEA01's finest band is 20-24; the cohort is that band over five. "
            "A uniform split across five single years is itself an assumption, "
            "so this share is indicative, not exact."
        ),
    }


def source_shas() -> dict[str, str]:
    """Every source this module reads, with the sha256 of the file read (D24)."""
    return {h.source_key: _table(h.source_key).sha256 for h in HAZARD_SOURCES}
