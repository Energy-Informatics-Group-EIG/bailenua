"""The t0 population pipeline (design 5.2; datasets D02, D05, D06, D07, D08).

Ties the stages together and writes the ground-truth datasets for Census day,
1 January 2022 (E0-3 / U08: Census 2022 is t0).

Order matters and is fixed:

1. **SAPS** for Cobh's 53 small areas, all 23 marginals, each closing against
   its own table total.
2. **Scale-down** (U03), both methods built; the caller chooses.
3. **Households and persons**, whole households with plausible members.
4. **Traits**, the MIMIC latent layer, per person.
5. **Names**, from the real CSO tables by birth year and origin.
6. **Buildings**, one per household, from the Census marginals plus the BER
   joint table.
7. **Write**, through the validated writers, so nothing reaches disk in a shape
   the schema does not describe.

Everything is addressed by entity id rather than by position, so the whole
pipeline is reproducible from the master seed alone and does not depend on
iteration order (design 8.2).
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd

from baile_nua.io import write_dataset
from baile_nua.manifest import RunManifest
from baile_nua.population import econ_by_age
from baile_nua.population import buildings as bld
from baile_nua.population import households as hh
from baile_nua.population import names as nm
from baile_nua.population import saps, scale_down, traits
from baile_nua.rng import SeedTree, Stream

__all__ = ["T0Population", "synthesise_t0", "write_t0"]

T0 = pd.Timestamp("2022-01-01T00:00:00Z")

#: SAPS place-of-birth categories -> the origin groups the name and trait pools
#: use.  The names are identical, which is deliberate: the SAPS marginal is the
#: only source for the mix, so the pools are keyed to its categories rather than
#: to a scheme of our own.
ORIGIN_GROUPS = ("IE", "UK", "PL", "IN", "EU27_other", "rest_of_world")

#: ISCED level per SAPS education category, for D05.education_level.
EDUCATION_TO_ISCED: dict[str, str] = {
    "no formal education": "ISCED 0",
    "primary": "ISCED 1",
    "lower secondary": "ISCED 2",
    "upper secondary": "ISCED 3",
    "technical or vocational": "ISCED 4",
    "advanced cert or apprenticeship": "ISCED 4",
    "higher certificate": "ISCED 5",
    "ordinary degree or national diploma": "ISCED 6",
    "honours degree or professional qualification": "ISCED 6",
    "postgraduate diploma or degree": "ISCED 7",
    "doctorate": "ISCED 8",
    "not stated": "ISCED 3",
}
#: z-scores for the education ladder, used as the ``education_z`` trait
#: predictor.  Monotone by construction; the spacing is a declared assumption.
EDUCATION_Z: dict[str, float] = {
    "ISCED 0": -2.0, "ISCED 1": -1.4, "ISCED 2": -0.8, "ISCED 3": -0.2,
    "ISCED 4": 0.2, "ISCED 5": 0.6, "ISCED 6": 1.0, "ISCED 7": 1.5, "ISCED 8": 2.0,
}

#: SAPS economic status -> the schema's ``econ_status`` enum.  The U18 gap is
#: visible here: "looking after home/family" is a real Census category and maps
#: to "home duties", which MIMIC has no value for.
ECON_MAP: dict[str, str] = {
    "at work": "employed",
    "looking for first regular job": "unemployed",
    "short-term unemployed": "unemployed",
    "long-term unemployed": "unemployed",
    "student": "student",
    "looking after home/family": "home duties",
    "retired": "retired",
    "unable to work": "unable to work",
    "other": "employed",
}


@dataclasses.dataclass
class T0Population:
    method: scale_down.Method
    plan: scale_down.ScaleDownPlan
    synthesis: hh.SynthesisResult
    buildings: list[bld.SynthBuilding]
    persons: pd.DataFrame          # D05
    membership: pd.DataFrame       # D06
    relationships: pd.DataFrame    # D07
    states: pd.DataFrame           # D08
    buildings_frame: pd.DataFrame  # D02
    crosswalk: pd.DataFrame        # GT premises crosswalk
    diagnostics: dict[str, Any]


def _as_weights(counts: Any) -> dict[str, float]:
    """A SAPS marginal as ``{label: weight}``, for the conditional draw."""
    return {str(k): max(float(v), 0.0) for k, v in dict(counts).items()}


def _draw_weighted(gen: np.random.Generator, weights: dict[str, float]) -> str:
    """Draw one label from explicit weights, in sorted label order.

    Sorted so the draw does not depend on dict insertion order, which is the
    same reason :func:`_draw_from` sorts: a reproducibility contract that held
    only while a dict happened to keep its order would not be one.
    """
    labels = sorted(weights)
    w = np.array([max(float(weights[l]), 0.0) for l in labels])
    if w.sum() <= 0:
        return labels[0]
    return str(gen.choice(labels, p=w / w.sum()))


def _draw_from(gen: np.random.Generator, counts: pd.Series) -> str:
    labels = sorted(counts.index)
    w = np.array([max(float(counts[l]), 0.0) for l in labels])
    if w.sum() <= 0:
        return labels[0]
    return str(gen.choice(labels, p=w / w.sum()))


def synthesise_t0(
    *,
    master_seed: int,
    method: scale_down.Method = "proportional",
) -> T0Population:
    """Build the whole town at t0 and return every ground-truth frame."""
    tree = SeedTree(master_seed)
    marginals = saps.build_marginals()
    plans = scale_down.build_both(marginals, master_seed=master_seed)
    plan = plans[method]

    synth = hh.synthesise_households(
        plan.marginals, master_seed=master_seed, reference_date=T0
    )

    name_gen = nm.NameGenerator(tree)

    person_rows: list[dict[str, Any]] = []
    state_rows: list[dict[str, Any]] = []
    membership_rows: list[dict[str, Any]] = []
    rel_rows: list[dict[str, Any]] = []
    privacy_by_household: dict[str, float] = {}

    # Households in sorted id order, and members in their declared role order,
    # so ids and draws are a function of the input alone.
    for household in sorted(synth.households, key=lambda h: h.household_id):
        sa = household.small_area
        area_marg = {k: plan.marginals[k].loc[sa] for k in plan.marginals}
        hh_gen = tree.generator(Stream.PERSON_DEMOGRAPHICS, entity=household.household_id)

        # Household-level attributes drawn once, then shared: birthplace and
        # socio-economic group are household properties in Census terms, and
        # drawing them per person would break the household's coherence.
        origin_group = _draw_from(hh_gen, area_marg["place_of_birth"])
        if origin_group not in ORIGIN_GROUPS:
            origin_group = "IE"
        seg = _draw_from(hh_gen, area_marg["socio_economic_group"])
        income_quintile = _SEG_TO_QUINTILE.get(seg, 3)
        decision_authority_pool = sorted(
            (m for m in household.members if m.age >= 18), key=lambda m: -m.age
        )

        privacies: list[float] = []
        for member in household.members:
            pid = member.person_id
            p_gen = tree.generator(Stream.PERSON_DEMOGRAPHICS, entity=pid)

            # Children born in Ireland to migrant parents: the second generation
            # is Irish-born. Modelled explicitly because treating every member
            # as the household's origin would overstate the non-Irish-born share
            # among children, which the Census contradicts.
            member_origin = origin_group
            years_in_ireland: float | None = None
            if origin_group != "IE":
                if member.age < 18 and float(p_gen.random()) < 0.75:
                    member_origin = "IE"
                else:
                    years_in_ireland = float(
                        min(member.age, p_gen.integers(1, max(member.age, 2)))
                    )

            if member.age >= 15:
                edu_label = _draw_from(p_gen, area_marg["education"])
            else:
                edu_label = "primary" if member.age >= 5 else "no formal education"
            isced = EDUCATION_TO_ISCED.get(edu_label, "ISCED 3")
            edu_z = EDUCATION_Z.get(isced, 0.0)

            tv = traits.draw_traits(
                tree, person_id=pid, sex=member.sex, age=member.age,
                origin_group=member_origin, years_in_ireland=years_in_ireland,
                education_z=edu_z, income_quintile=income_quintile,
            )
            privacies.append(tv.privacy)

            draw = name_gen.draw(
                pid, sex=member.sex, birth_year=member.birth_year,
                origin_group=member_origin,
            )

            # Birth date: a deterministic day within the birth year. A town where
            # everyone shares 1 January would be an obvious synthetic tell
            # (design 6.3), and birth dates drive school year and pension age.
            #
            # I-070. The day was drawn anywhere in the birth year, so a person
            # born in T0's own year could get a date AFTER t0: 33 of 2,917 had
            # a birth_date up to 2022-12-31 while being recorded as resident on
            # 2022-01-01. They were in the town before they were born, and any
            # age computed from birth_date was NEGATIVE for them without
            # warning - which is how the joint validation found it.
            #
            # Clamped to the day before t0 for the t0 cohort only. Not shifted
            # into the previous year: a person the Census counts as age 0 was
            # born within the twelve months before Census day, and moving them
            # back a whole year would make them age 1.
            doy = int(p_gen.integers(0, 365))
            birth_date = (
                pd.Timestamp(year=member.birth_year, month=1, day=1)
                + pd.Timedelta(days=doy)
            )
            # T0 is tz-aware and the birth date is a naive calendar day, so
            # the comparison is made on the DATE: a birth date is a calendar
            # fact and has no time zone.
            if birth_date.date() >= T0.date():
                birth_date = pd.Timestamp(T0.date()) - pd.Timedelta(
                    days=1 + doy % 365)
            birth_date = birth_date.date()

            row = {
                "person_id": pid,
                "given_name": draw.given_name,
                "family_name": draw.family_name,
                "birth_date": birth_date,
                "death_date": None,
                "sex": member.sex,
                "country_of_birth": member_origin if member_origin in ("IE", "UK", "PL", "IN") else ("XX" if member_origin == "rest_of_world" else "EU"),
                "nationality": _nationality_for(p_gen, member_origin, years_in_ireland),
                "ethnicity_census": _draw_from(p_gen, area_marg["ethnicity"]),
                "first_language": _language_for(member_origin),
                "other_languages": ["en"] if member_origin != "IE" else None,
                "years_in_ireland": years_in_ireland,
                "education_level": isced,
                **{k: getattr(tv, k) for k in traits.MIMIC_LATENTS},
                "stated_gap": tv.stated_gap,
                "lambda_self": tv.lambda_self,
                "lambda_coop": tv.lambda_coop,
                "lambda_altru": tv.lambda_altru,
                "big5_o": tv.big5_o, "big5_c": tv.big5_c, "big5_e": tv.big5_e,
                "big5_a": tv.big5_a, "big5_n": tv.big5_n,
                "chronotype": tv.chronotype,
                "habit_strength": tv.habit_strength,
                "lapse_rate": tv.lapse_rate,
                "attention": tv.attention,
                "response_propensity": tv.response_propensity,
                "mcv_latent": [float(v) for v in tv.mcv_latent],
                "synthetic": True,
                "seed": int(p_gen.integers(0, 2**62)),
                "pool": "BN-panel",
            }
            person_rows.append(row)

            # D08 person state at t0
            #
            # I-069's fix. This drew from the area's economic-status marginal
            # with NO age conditioning, so every marginal matched - IPF
            # guarantees it - and the age x status joint came out as the
            # product of the two marginals: a 14-year-old retiree, 243
            # "students" with a median age of 45, 65+ retirement at 2.2%
            # against the Census's 13.1%, and a total variation distance of
            # 0.3339 against F1054.
            #
            # It was a faithful use of the only small-area source there is.
            # EVERY SAPS table crossing economic status is `Sex x Principal
            # Economic Status` with no age dimension at all, so the marginals
            # this population is fitted to cannot condition status on age.
            # The fault was not reaching for a coarser geography that has the
            # joint: FY047B publishes it for Cork City and Cork County.
            #
            # The area marginal is preserved. econ_by_age applies Bayes -
            # P(status | age, area) proportional to P(age | status, county) x
            # P(status | area) - so SAPS still decides HOW MANY of each status
            # an area has and FY047B decides WHICH AGES get them. Imposing the
            # county joint directly would overwrite the small-area variation
            # the whole synthesis exists to reproduce: Cobh's older core areas
            # really do have more retired residents than its newer ones, and
            # SAPS is the only thing that knows it.
            econ_label = (
                _draw_weighted(
                    p_gen,
                    econ_by_age.status_weights_for_age(
                        member.age, _as_weights(area_marg["economic_status"])),
                )
                if member.age >= 15 else "student"
            )
            econ = ECON_MAP.get(econ_label, "student") if member.age >= 15 else "student"
            if member.age < 5:
                econ = "home duties"
            authority = (
                1.0 / max(len(decision_authority_pool), 1)
                if member in decision_authority_pool else 0.0
            )
            state_rows.append(
                {
                    "state_id": f"S-{pid}-0001",
                    "person_id": pid,
                    "valid_from": T0,
                    "valid_to": None,
                    "household_id": household.household_id,
                    "role": member.role,
                    "econ_status": econ,
                    "occupation_soc": (
                        _draw_from(p_gen, area_marg["occupation"]) if econ == "employed" else None
                    ),
                    "occupation_isco08": None,
                    "industry_nace": (
                        _draw_from(p_gen, area_marg["industry"]) if econ == "employed" else None
                    ),
                    "workplace_venue_id": None,
                    "work_pattern": _work_pattern(p_gen, econ),
                    "remote_share": _remote_share(p_gen, area_marg, econ),
                    "school_venue_id": None,
                    "school_year": (member.age - 4) if 5 <= member.age <= 18 else None,
                    "health_state": "well",
                    "caring_load": _caring_load(member, household),
                    "caring_hours_week": 0.0,
                    "decision_authority": authority,
                    "vehicle_access": _vehicle_access(p_gen, area_marg, member),
                    "income_quintile": income_quintile,
                }
            )
            membership_rows.append(
                {
                    "membership_id": f"M-{pid}-0001",
                    "person_id": pid,
                    "household_id": household.household_id,
                    "building_id": "",            # filled once buildings exist
                    "valid_from": T0,
                    "valid_to": None,
                    "role": member.role,
                    "reason_in": "t0",
                    "reason_out": None,
                }
            )

        privacy_by_household[household.household_id] = (
            float(np.mean(privacies)) if privacies else 0.0
        )
        rel_rows.extend(_relationships(household))

    # Buildings, which never see a person record (R11).
    buildings, bdiag = bld.generate_buildings(
        plan.marginals, synth.households, master_seed=master_seed,
        privacy_by_household=privacy_by_household,
    )
    by_household = {b.household_id: b for b in buildings}
    for row in membership_rows:
        b = by_household.get(row["household_id"])
        row["building_id"] = b.building_id if b else ""

    persons = pd.DataFrame(person_rows)
    states = pd.DataFrame(state_rows)
    membership = pd.DataFrame(membership_rows)
    relationships = pd.DataFrame(rel_rows)
    buildings_frame = pd.DataFrame([b.d02_row() for b in buildings])
    crosswalk = pd.DataFrame(
        [{"premises_id": b.premises_id, "gt_premises_key": b.gt_premises_key,
          "building_id": b.building_id} for b in buildings]
    )

    diagnostics = {
        "method": method,
        "scale_down": plan.summary(),
        "households": {k: v for k, v in synth.diagnostics.items() if k != "per_small_area"},
        "buildings": {k: v for k, v in bdiag.items() if k != "per_small_area"},
        "names": name_gen.report(),
        "n_persons": len(persons),
        "n_households": len(synth.households),
        "n_buildings": len(buildings),
        "trait_within_between": [
            traits.within_vs_between_variance(
                [traits.TraitVector(**_tv_kwargs(r)) for r in person_rows[:1500]],
                [r["country_of_birth"] for r in person_rows[:1500]],
                lat,
            )
            for lat in ("trans", "community", "env", "privacy")
        ],
    }
    return T0Population(
        method=method, plan=plan, synthesis=synth, buildings=buildings,
        persons=persons, membership=membership, relationships=relationships,
        states=states, buildings_frame=buildings_frame, crosswalk=crosswalk,
        diagnostics=diagnostics,
    )


_SEG_TO_QUINTILE: dict[str, int] = {
    "A employers and managers": 5, "B higher professional": 5,
    "C lower professional": 4, "D non-manual": 3, "E manual skilled": 3,
    "F semi-skilled": 2, "G unskilled": 1, "H own account workers": 3,
    "I farmers": 3, "J agricultural workers": 2, "Z all others and unknown": 2,
}


def _tv_kwargs(row: dict[str, Any]) -> dict[str, Any]:
    fields = {f.name for f in dataclasses.fields(traits.TraitVector)}
    out = {k: v for k, v in row.items() if k in fields}
    for missing in fields - set(out):
        out[missing] = 0 if missing in ("satisficer",) else (
            [] if missing == "mcv_latent" else 0.0
        )
    return out


def _nationality_for(gen, origin: str, years: float | None) -> str:
    """Nationality, which is not the same as country of birth (SAPS Table 2.1
    publishes both, and D05 keeps them separate)."""
    if origin == "IE":
        return "IE"
    # Naturalisation becomes likely after long residence.
    if years is not None and years >= 8 and float(gen.random()) < 0.35:
        return "IE"
    return {"UK": "GB", "PL": "PL", "IN": "IN", "EU27_other": "EU",
            "rest_of_world": "XX"}.get(origin, "XX")


def _language_for(origin: str) -> str:
    return {"IE": "en", "UK": "en", "PL": "pl", "IN": "en",
            "EU27_other": "en", "rest_of_world": "en"}.get(origin, "en")


def _work_pattern(gen, econ: str) -> str:
    if econ in ("employed", "self-employed"):
        return str(gen.choice(["fixed day", "shift", "part-time", "irregular"],
                              p=[0.62, 0.16, 0.14, 0.08]))
    return "none"


def _remote_share(gen, area_marg, econ: str) -> float:
    if econ not in ("employed", "self-employed"):
        return 0.0
    wfh = area_marg["working_from_home"]
    tot = float(wfh.sum())
    p = float(wfh.get("works from home", 0.0)) / tot if tot else 0.0
    if float(gen.random()) >= p:
        return 0.0
    return float(np.clip(gen.beta(2.0, 2.0), 0.05, 1.0))


def _caring_load(member, household) -> str:
    kids = [m for m in household.members if m.age < 12]
    elders = [m for m in household.members if m.age >= 80]
    if member.age < 18:
        return "none"
    if kids and elders:
        return "both"
    if kids:
        return "child"
    if elders and member.age < 75:
        return "elderly"
    return "none"


def _vehicle_access(gen, area_marg, member) -> str:
    if member.age < 17:
        return "none"
    cars = area_marg["car_availability"]
    tot = float(cars.sum())
    p_none = float(cars.get("0", 0.0)) / tot if tot else 0.2
    r = float(gen.random())
    if r < p_none:
        return "none"
    return "own" if r < p_none + 0.55 else "shared"


def _relationships(household) -> list[dict[str, Any]]:
    """D07 edges within a household: partner, parent_of, sibling, carer_of."""
    rows: list[dict[str, Any]] = []
    core = [m for m in household.members if m.role in ("head", "partner")]
    kids = [m for m in household.members if m.role == "child"]
    n = 0

    def add(a, b, kind, strength):
        nonlocal n
        n += 1
        rows.append({
            "edge_id": f"E-{household.household_id}-{n:03d}",
            "person_a": a.person_id, "person_b": b.person_id,
            "edge_type": kind, "valid_from": T0, "valid_to": None,
            "strength": strength,
        })

    if len(core) == 2:
        add(core[0], core[1], "partner", 0.9)
    for parent in household.parents:
        for kid in kids:
            add(parent, kid, "parent_of", 0.95)
            if kid.age < 12:
                add(parent, kid, "carer_of", 0.9)
    for i in range(len(kids)):
        for j in range(i + 1, len(kids)):
            add(kids[i], kids[j], "sibling", 0.7)
    return rows


def write_t0(pop: T0Population, root: Path, manifest: RunManifest | None = None) -> dict[str, Path]:
    """Write the t0 ground-truth datasets through the validated writers."""
    gt = Path(root) / "v1" / "ground_truth"
    out: dict[str, Path] = {}
    out["D05"] = write_dataset(pop.persons, "D05", gt / "persons.parquet", manifest=manifest)
    out["D06"] = write_dataset(pop.membership, "D06", gt / "household_membership.parquet", manifest=manifest)
    out["D07"] = write_dataset(pop.relationships, "D07", gt / "relationships.parquet", manifest=manifest)
    out["D08"] = write_dataset(pop.states, "D08", gt / "person_states.parquet", manifest=manifest)
    out["D02"] = write_dataset(pop.buildings_frame, "D02", gt / "buildings.parquet", manifest=manifest)
    # The premises crosswalk is GT-only: it is what makes the observable ids
    # reversible, so it must never travel with the observable package.
    cw = gt / "premises_crosswalk.parquet"
    cw.parent.mkdir(parents=True, exist_ok=True)
    pop.crosswalk.to_parquet(cw, compression="zstd", index=False)
    out["crosswalk"] = cw
    if manifest is not None:
        manifest.record_output(cw)
    return out
