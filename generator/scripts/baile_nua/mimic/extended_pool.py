"""The HRSD extended pool (design 5.14, U16 pool 2).

    **HRSD extended pool (unlinked).**  The same person generator, without the
    time simulation, creates 10,000+ further participants from full-size Cobh,
    other Irish small areas and, with ``CountryAttributes`` priors, the EU-27.
    This tests MIMIC's country analytics at scale.

Why the pool exists, and why E1 needs it (ISSUES.md I-007): the E1 estate is 50
homes and about 140 people, of whom roughly 100 are adults.  The E1 criterion of
10,000 **unique participants** is therefore reachable only through this pool, and
U16 approved exactly that.  The five counters stay separate (design 5.14), so
the E1 report never implies that 10,000 simulated townspeople exist.

Three strata, each testing something different in MIMIC:

=========================  ====================================================
Stratum                    What it exercises
=========================  ====================================================
``cobh_full``              Full-size Cobh, from the same real SAPS marginals as
                           the simulated town but at 14,148-person scale, so
                           MIMIC sees the genuine Irish small-area structure.
``ireland_other``          Other Irish small areas, drawn from the national
                           SAPS file, so Irish within-country variation is
                           present rather than one town repeated.
``eu27``                   The EU-27, with individualism and social-trust
                           priors taken from MIMIC's own
                           ``CountryAttributes``, so its country analytics have
                           something to analyse.
=========================  ====================================================

The country priors are **read from MIMIC's source**, not recalled, by
:func:`country_attributes` - and a drift check fails if MIMIC's table changes.
"""

from __future__ import annotations

import dataclasses
import functools
import os
import re
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd

from baile_nua.mimic import crosswalk
from baile_nua.population import traits as traits_mod
from baile_nua.rng import SeedTree, Stream

__all__ = [
    "PoolPerson",
    "Stratum",
    "country_attributes",
    "generate_extended_pool",
    "DEFAULT_STRATUM_SHARES",
]

Stratum = Literal["cobh_full", "ireland_other", "eu27"]

#: How the pool is split.  Weighted toward Ireland because the primary purpose
#: is an Irish test population, with enough EU-27 mass for country analytics to
#: have a usable n per country (27 countries x ~110 = ~3,000).
DEFAULT_STRATUM_SHARES: dict[str, float] = {
    "cobh_full": 0.40, "ireland_other": 0.30, "eu27": 0.30,
}

MIMIC_ROOT = Path(
    os.environ.get("BAILE_NUA_MIMIC_ROOT", "/Users/brianoregan/Documents/GitHub/mimic")
)


@functools.lru_cache(maxsize=1)
def country_attributes() -> dict[str, dict[str, Any]]:
    """EU-27 individualism and social trust, parsed from MIMIC's own source.

    Design 5.13 lists ``CountryAttributes`` as the origin-country prior source.
    Parsed rather than copied so that a change in MIMIC's table shows up here as
    a changed distribution instead of being silently ignored.
    """
    path = MIMIC_ROOT / "web" / "mimic" / "includes" / "CountryAttributes.php"
    if not path.is_file():
        raise FileNotFoundError(
            f"MIMIC CountryAttributes.php not found at {path}; the EU-27 priors "
            f"are read from MIMIC's source rather than recalled"
        )
    text = path.read_text(encoding="utf-8")
    out: dict[str, dict[str, Any]] = {}
    pattern = re.compile(
        r"'([A-Z]{2})'\s*=>\s*\[\s*'individualism'\s*=>\s*([0-9.]+)\s*,\s*"
        r"'social_trust'\s*=>\s*([0-9.]+)\s*,\s*'region'\s*=>\s*'([^']+)'"
    )
    for code, idv, trust, region in pattern.findall(text):
        out[code] = {
            "individualism": float(idv),
            "social_trust": float(trust),
            "region": region,
        }
    if len(out) < 20:
        raise RuntimeError(
            f"parsed only {len(out)} countries from CountryAttributes.php; the "
            f"table layout may have changed"
        )
    return out


@dataclasses.dataclass
class PoolPerson:
    """One unlinked extended-pool participant.

    Deliberately *not* a Baile Nua person: it has no ``person_id``, no household
    and no simulated behaviour, because U16's pool 2 is unlinked by design.  D26
    records ``pool = 'HRSD-pool'`` so the counters never merge.
    """

    pool_person_id: str
    stratum: str
    country: str
    nuts3: str
    urban_rural: str
    sex: str
    age: int
    age_band: str
    household_size: str
    children_present: str
    econ_status: str
    work_pattern: str
    dwelling_type: str
    ownership_status: str
    income_band: str
    education_level: str
    der_ownership: list[str]
    digital_access: str
    traits: traits_mod.TraitVector
    #: T3: the segment planted for this participant, or None in null mode.
    planted_segment: str | None = None
    planted_null_mode: bool = False

    def mimic_profile(self) -> dict[str, Any]:
        """The 16 MIMIC primary fields plus the permitted optional ones.

        Values come from :mod:`baile_nua.mimic.crosswalk`, which read MIMIC's own
        value sets out of its source, so the coding is MIMIC's and not a
        plausible-looking approximation.
        """
        return {
            "age_band": self.age_band,
            "sex": self.sex_label,
            "household_size": self.household_size,
            "children_present": self.children_present,
            "employment_status": self.employment_label,
            "work_pattern": self.work_pattern,
            "dwelling_type": self.dwelling_label,
            "ownership_status": self.ownership_status,
            "region_country": self.country,
            "region_nuts3": self.nuts3,
            "urban_rural_island": self.urban_rural,
            "income_band": self.income_band,
            "der_ownership": self.der_ownership,
            "environmental_concern": self.traits.environmental_concern,
            "trust_in_automation": self.traits.trust_in_automation,
            "comfort_sensitivity": self.traits.comfort_sensitivity,
            # the ten permitted optional fields (ADR-004 exclusions applied)
            "education_level": self.education_level,
            "digital_access_level": self.digital_access,
            "home_automation_level": self.home_automation,
            "community_energy_member": "Yes" if self.traits.community > 0.8 else "No",
        }

    @property
    def sex_label(self) -> str:
        return "Female" if self.sex == "F" else "Male"

    @property
    def employment_label(self) -> str:
        """Maps onto MIMIC's value set, and shows the U18 gap where it bites."""
        if self.econ_status == "home duties":
            return crosswalk.HOME_DUTIES_MAPPED_TO
        return {
            "employed": "Full-time", "self-employed": "Full-time",
            "unemployed": "Unemployed", "student": "Student",
            "retired": "Retired", "unable to work": "Unemployed",
        }.get(self.econ_status, "Full-time")

    @property
    def dwelling_label(self) -> str:
        """Maps onto MIMIC's value set; "terraced" has nowhere to go (U18)."""
        return {
            "detached": "Detached", "semi-detached": "Semi-Detached",
            "terraced": crosswalk.TERRACED_MAPPED_TO,
            "apartment": "Apartment", "bedsit": "Other",
        }.get(self.dwelling_type, "Other")

    @property
    def home_automation(self) -> str:
        if self.traits.autonomy > 0.8:
            return "High"
        return "Medium" if self.traits.autonomy > -0.2 else "Low"

    @property
    def u18_information_lost(self) -> list[str]:
        """Which U18 gaps this participant's export actually loses."""
        lost = []
        if self.econ_status == "home duties":
            lost.append("employment_status: 'home duties' -> 'Unemployed'")
        if self.dwelling_type == "terraced":
            lost.append("dwelling_type: 'terraced' -> 'Semi-Detached'")
        return lost


def _irish_marginal_draws(gen: np.random.Generator, marginals: dict[str, pd.Series]) -> dict[str, Any]:
    """Draw demographics from real SAPS marginals."""
    def pick(key: str) -> str:
        counts = marginals[key]
        labels = sorted(counts.index)
        w = np.array([max(float(counts[l]), 0.0) for l in labels])
        return str(gen.choice(labels, p=w / w.sum()))

    return {
        "household_size": pick("household_size"),
        "econ_status": pick("economic_status"),
        "tenure": pick("tenure"),
        "accommodation": pick("accommodation_type"),
        "education": pick("education"),
        "seg": pick("socio_economic_group"),
    }


def generate_extended_pool(
    n: int,
    *,
    master_seed: int,
    shares: dict[str, float] | None = None,
    planted_segments: int = 0,
    null_mode: bool = False,
) -> list[PoolPerson]:
    """Generate ``n`` unlinked participants across the three strata.

    ``planted_segments`` plants k latent segments for test T3(a); ``null_mode``
    plants none, which is T3(b) - "null mode with no clusters", where MIMIC's
    validity gate must *reject* clusters.  The two are mutually exclusive and
    the truth is recorded per participant in D26.
    """
    if planted_segments and null_mode:
        raise ValueError(
            "T3(a) plants k segments and T3(b) plants none; a batch cannot be both"
        )
    shares = shares or DEFAULT_STRATUM_SHARES
    tree = SeedTree(master_seed)
    countries = country_attributes()

    # Irish marginals, from the real SAPS data for Cobh.
    from baile_nua.population.households import AGE_BAND_EDGES
    from baile_nua.population.saps import build_marginals

    ms = build_marginals()
    irish_marginals = {k: m.town_total for k, m in ms.items()}

    # Adult age distribution from the real SAPS age-by-sex marginal, restricted
    # to 18+ and expanded to single years.
    #
    # The first version drew age uniformly from 18 to 91, which put 37% of the
    # pool in the 65+ band against about 20% in reality - and MIMIC's own
    # generator weights that band at 0.20. A uniform draw would have given its
    # country and age analytics a population that does not exist anywhere.
    age_bands = AGE_BAND_EDGES(list(ms["age_by_sex"].by_small_area.columns))
    adult_ages: list[int] = []
    adult_sex: list[str] = []
    for label, (lo, hi, sx) in age_bands.items():
        count = int(ms["age_by_sex"].town_total.get(label, 0))
        if count <= 0 or hi < 18:
            continue
        lo_eff = max(lo, 18)
        span = hi - lo_eff + 1
        if span <= 0:
            continue
        base, extra = divmod(count, span)
        for k in range(span):
            n_k = base + (1 if k < extra else 0)
            adult_ages.extend([lo_eff + k] * n_k)
            adult_sex.extend([sx] * n_k)
    if not adult_ages:
        raise RuntimeError("could not build an adult age distribution from SAPS")
    adult_age_arr = np.array(adult_ages, dtype=np.int64)
    adult_sex_arr = np.array(adult_sex)

    # Largest-remainder split across strata so the counts sum to n exactly.
    keys = sorted(shares)
    w = np.array([shares[k] for k in keys], dtype=np.float64)
    exact = w / w.sum() * n
    counts = np.floor(exact).astype(np.int64)
    short = int(n - counts.sum())
    if short:
        order = np.argsort(-(exact - counts), kind="stable")
        counts[order[:short]] += 1

    eu_codes = sorted(countries)
    people: list[PoolPerson] = []
    index = 0

    for stratum, k in zip(keys, counts):
        for _ in range(int(k)):
            index += 1
            ppid = f"HP-{index:07d}"
            gen = tree.generator(Stream.MIMIC_POOL_PERSON, entity=ppid, sim_day=0)

            if stratum == "eu27":
                country = str(gen.choice(eu_codes))
                attrs = countries[country]
                nuts3 = f"{country}-{int(gen.integers(1, 10)):02d}"
                origin_group = "IE" if country == "IE" else (
                    "PL" if country == "PL" else "EU27_other"
                )
                urban = str(gen.choice(["Urban", "Rural", "Island"], p=[0.62, 0.30, 0.08]))
            else:
                country = "IE"
                attrs = countries["IE"]
                # Cobh's own NUTS3 for the Cobh stratum; other Irish regions for
                # the rest, so Irish within-country variation is present.
                nuts3 = (
                    "IE053" if stratum == "cobh_full"
                    else str(gen.choice(["IE041", "IE042", "IE051", "IE052", "IE061", "IE062", "IE063"]))
                )
                origin_group = "IE"
                urban = "Urban" if stratum == "cobh_full" else str(
                    gen.choice(["Urban", "Rural"], p=[0.55, 0.45])
                )

            demo = _irish_marginal_draws(gen, irish_marginals)

            # Adults only: MIMIC has no age band for minors (5.14). Age AND sex
            # are taken from the same draw on the real joint age-by-sex
            # distribution, so the two are consistent rather than independent.
            pick_ix = int(gen.integers(0, adult_age_arr.size))
            age = int(adult_age_arr[pick_ix])
            sex = str(adult_sex_arr[pick_ix])
            band = crosswalk.age_band_for(age)

            edu_isced = {
                "no formal education": "ISCED 0", "primary": "ISCED 1",
                "lower secondary": "ISCED 2", "upper secondary": "ISCED 3",
                "technical or vocational": "ISCED 4",
                "advanced cert or apprenticeship": "ISCED 4",
                "higher certificate": "ISCED 5",
                "ordinary degree or national diploma": "ISCED 6",
                "honours degree or professional qualification": "ISCED 6",
                "postgraduate diploma or degree": "ISCED 7",
                "doctorate": "ISCED 8", "not stated": "ISCED 3",
            }.get(demo["education"], "ISCED 3")
            edu_z = {
                "ISCED 0": -2.0, "ISCED 1": -1.4, "ISCED 2": -0.8, "ISCED 3": -0.2,
                "ISCED 4": 0.2, "ISCED 5": 0.6, "ISCED 6": 1.0, "ISCED 7": 1.5,
                "ISCED 8": 2.0,
            }[edu_isced]

            income = {
                "A employers and managers": "5", "B higher professional": "5",
                "C lower professional": "4", "D non-manual": "3",
                "E manual skilled": "3", "F semi-skilled": "2",
                "G unskilled": "1", "H own account workers": "3",
                "I farmers": "3", "J agricultural workers": "2",
                "Z all others and unknown": "2",
            }.get(demo["seg"], "3")

            tv = traits_mod.draw_traits(
                tree, person_id=ppid, sex=sex,
                age=age, origin_group=origin_group,
                years_in_ireland=None if country == "IE" else float(gen.integers(1, 30)),
                education_z=edu_z, income_quintile=int(income),
            )

            # T3: plant k latent segments by shifting the trait vector, or plant
            # none in null mode. The shift is recorded in D26 as the truth.
            segment: str | None = None
            if planted_segments:
                seg_ix = int(gen.integers(0, planted_segments))
                segment = f"SEG-{seg_ix + 1}"
                shift = (seg_ix - (planted_segments - 1) / 2.0) * 0.9
                tv = dataclasses.replace(
                    tv,
                    trans=tv.trans + shift,
                    community=tv.community + 0.6 * shift,
                    env=tv.env + 0.7 * shift,
                    environmental_concern=crosswalk.self_report_from_latent(tv.env + 0.7 * shift),
                )

            # Country prior on individualism, from MIMIC's own table, on MIMIC's
            # own scale: idvZ = (individualism - 55) / 20.
            tv = dataclasses.replace(
                tv, idvZ=(attrs["individualism"] - 55.0) / 20.0 + float(gen.normal(0, 0.5))
            )

            sz = demo["household_size"]
            der: list[str] = []
            if float(gen.random()) < 0.18:
                der.append("PV")
            if "PV" in der and float(gen.random()) < 0.40:
                der.append("Battery")
            if float(gen.random()) < 0.12:
                der.append("EV")
            if float(gen.random()) < 0.09:
                der.append("HP")
            if not der:
                der = ["None"]

            people.append(
                PoolPerson(
                    pool_person_id=ppid,
                    stratum=stratum,
                    country=country,
                    nuts3=nuts3,
                    urban_rural=urban,
                    sex=sex,
                    age=age,
                    age_band=band,
                    household_size="5+" if sz == "8+" or sz in ("5", "6", "7") else sz,
                    children_present=("Yes" if (25 <= age <= 54 and gen.random() < 0.45)
                                      else ("Yes" if gen.random() < 0.12 else "No")),
                    econ_status={
                        "at work": "employed",
                        "looking for first regular job": "unemployed",
                        "short-term unemployed": "unemployed",
                        "long-term unemployed": "unemployed",
                        "student": "student",
                        "looking after home/family": "home duties",
                        "retired": "retired",
                        "unable to work": "unable to work",
                        "other": "employed",
                    }.get(demo["econ_status"], "employed"),
                    work_pattern=str(gen.choice(
                        ["Office", "Remote", "Shift", "Irregular"], p=[0.42, 0.20, 0.20, 0.18]
                    )),
                    dwelling_type=(
                        "apartment" if demo["accommodation"] == "flat or apartment"
                        else str(gen.choice(["detached", "semi-detached", "terraced"],
                                            p=[0.48, 0.32, 0.20]))
                    ),
                    ownership_status={
                        "owner-occupied with mortgage": "Owner",
                        "owner-occupied no mortgage": "Owner",
                        "rented private": "Renter",
                        "rented social": "Social",
                        "rent free": "Other",
                        "not stated": "Other",
                    }.get(demo["tenure"], "Other"),
                    income_band=income,
                    education_level=edu_isced,
                    der_ownership=der,
                    digital_access=("High" if tv.autonomy > 0.5 else
                                    "Medium" if tv.autonomy > -0.5 else "Low"),
                    traits=tv,
                    planted_segment=segment,
                    planted_null_mode=null_mode,
                )
            )
    return people
