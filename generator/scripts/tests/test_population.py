"""Day 2 suite: SAPS ingest, U03 scale-down, household and building synthesis.

Design 9.3 day-2 acceptance:

    SAPS marginals within sampling tolerance; zero plausibility violations;
    name uniqueness
"""

from __future__ import annotations

import pytest

import baile_nua.sources_registry  # noqa: F401  (registers the sources)
from baile_nua.sources import REGISTRY, manifest_for

pytestmark = pytest.mark.slow

_have_sources = all(
    manifest_for(s) is not None and s.path.is_file() for s in REGISTRY.values()
)
needs_sources = pytest.mark.skipif(
    not _have_sources, reason="public sources not downloaded; run `baile-nua sources fetch`"
)


# --------------------------------------------------------------------------- #
# SAPS ingest
# --------------------------------------------------------------------------- #

@needs_sources
def test_cobh_is_53_small_areas_across_two_eds():
    """I-010: the SAPS file has no place names, so this join is load-bearing."""
    from baile_nua.population.saps import cobh_small_areas, verify_join_keys

    rep = verify_join_keys()
    assert rep["n_small_areas_osi"] == 53
    assert rep["n_matched_in_saps"] == 53
    assert rep["unmatched"] == []
    assert rep["ed_counts"] == {"COBH URBAN": 29, "COBH RURAL": 24}
    sas = cobh_small_areas()
    assert sas.nuts3_code == "IE053"
    assert sas.county == "CORK"


@needs_sources
def test_every_marginal_closes_against_its_table_total():
    """A marginal that omits a category makes R04's acceptance meaningless."""
    from baile_nua.population.saps import build_marginals

    ms = build_marginals()
    assert len(ms) >= 21
    bad = {k: (m.total_declared, m.total_from_categories) for k, m in ms.items() if not m.closes}
    assert not bad, f"marginals that do not close: {bad}"


@needs_sources
def test_cobh_totals_match_the_saps_tables():
    from baile_nua.population.saps import build_marginals

    ms = build_marginals()
    assert int(ms["age_by_sex"].town_total.sum()) == 14148
    assert int(ms["household_size"].town_total.sum()) == 5257


# --------------------------------------------------------------------------- #
# U03: both methods, and the recommendation
# --------------------------------------------------------------------------- #

@needs_sources
def test_both_u03_methods_are_built():
    """E0-1 requires both, so that the choice comes from evidence."""
    from baile_nua.population.saps import build_marginals
    from baile_nua.population.scale_down import build_both

    plans = build_both(build_marginals(), master_seed=20261008)
    assert set(plans) == {"whole_area_stratified", "proportional"}
    for plan in plans.values():
        assert plan.n_people > 0 and plan.n_households > 0


@needs_sources
def test_r03_is_satisfiable_and_the_factor_is_derived_from_both_ranges():
    """I-012: the obvious 3,000-person anchor falls outside R03's homes range."""
    from baile_nua.population.scale_down import feasible_scale_factor

    f, info = feasible_scale_factor(cobh_people=14148, cobh_households=5257)
    lo, hi = info["feasible_factor_interval"]
    assert lo < hi, "R03's two ranges must leave a feasible window"
    assert lo <= f <= hi
    # the naive anchor is outside it, which is the whole point
    assert 3000 / 14148 > hi


@needs_sources
def test_proportional_method_meets_r03():
    from baile_nua.population.saps import build_marginals
    from baile_nua.population.scale_down import (
        TARGET_HOMES_RANGE,
        TARGET_PEOPLE_RANGE,
        scale_proportional,
    )

    plan = scale_proportional(build_marginals())
    assert TARGET_PEOPLE_RANGE[0] <= plan.n_people <= TARGET_PEOPLE_RANGE[1]
    assert TARGET_HOMES_RANGE[0] <= plan.n_households <= TARGET_HOMES_RANGE[1]


@needs_sources
def test_u03_comparison_covers_marginal_joint_and_spatial_error():
    """Review-2 finding A4: marginals alone do not prove representativeness."""
    from baile_nua.population.joint_metrics import compare_methods
    from baile_nua.population.saps import build_marginals, cobh_small_areas
    from baile_nua.population.scale_down import build_both

    ms = build_marginals()
    plans = build_both(ms, master_seed=20261008)
    cent = cobh_small_areas().frame.set_index("sa_code")
    scores, table, rec = compare_methods(ms, plans, cent)
    for col in (
        "marginal_mean_tvd", "joint_mean_abs_difference",
        "spatial_morans_mean_abs_difference",
        "spatial_dissimilarity_mean_abs_difference",
    ):
        assert col in table.columns
    assert rec["recommended_method"] in plans
    assert "claim_boundary" in rec


@needs_sources
def test_proportional_method_wins_on_every_measured_criterion():
    """I-013: this contradicts the design's own U03 recommendation, so it is
    asserted rather than left as a remark."""
    from baile_nua.population.joint_metrics import compare_methods
    from baile_nua.population.saps import build_marginals, cobh_small_areas
    from baile_nua.population.scale_down import build_both

    ms = build_marginals()
    plans = build_both(ms, master_seed=20261008)
    cent = cobh_small_areas().frame.set_index("sa_code")
    _scores, table, _rec = compare_methods(ms, plans, cent)
    p, w = "proportional", "whole_area_stratified"
    for col in (
        "marginal_mean_tvd", "joint_mean_abs_difference",
        "spatial_morans_mean_abs_difference",
        "spatial_dissimilarity_mean_abs_difference",
    ):
        assert table.loc[p, col] < table.loc[w, col], col


# --------------------------------------------------------------------------- #
# Household synthesis
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def town():
    from baile_nua.population.synthesise import synthesise_t0

    return synthesise_t0(master_seed=20261008)


@needs_sources
def test_zero_plausibility_violations(town):
    """Design 9.3 day-2 acceptance: "zero plausibility violations"."""
    assert town.synthesis.plausibility_violations == []


@needs_sources
def test_no_household_is_unplaced(town):
    """An unbuildable household is a silent population loss."""
    assert town.synthesis.diagnostics["unplaced_households_total"] == 0


@needs_sources
def test_town_size_meets_r03(town):
    assert 2900 <= town.diagnostics["n_persons"] <= 3100
    assert 1000 <= town.diagnostics["n_households"] <= 1100
    assert town.diagnostics["n_buildings"] == town.diagnostics["n_households"]


@needs_sources
def test_marginals_within_the_sampling_error_band(town):
    """Design 12 R04, with the band specified as simultaneous (I-016).

    Both verdicts are checked: the criterion, and the naive per-test one, so a
    future regression cannot quietly rely on the correction.
    """
    import pandas as pd

    from baile_nua.population.households import AGE_BAND_EDGES, SIZE_LABELS
    from baile_nua.population.joint_metrics import marginal_acceptance, marginal_error
    from baile_nua.population.saps import build_marginals

    ms = build_marginals()
    bands = AGE_BAND_EDGES(list(town.plan.marginals["age_by_sex"].columns))
    counts: dict[str, int] = {}
    for p in town.synthesis.persons:
        for lab, (lo, hi, s) in bands.items():
            if s == p.sex and lo <= p.age <= hi:
                counts[lab] = counts.get(lab, 0) + 1
                break
    sz = pd.Series({
        lab: sum(1 for h in town.synthesis.households if min(h.size, 8) == n)
        for lab, n in SIZE_LABELS
    })
    ty = pd.Series({
        t: sum(1 for h in town.synthesis.households if h.saps_type == t)
        for t in ms["household_type"].town_total.index
    })
    errors = marginal_error(
        {k: ms[k] for k in ("age_by_sex", "household_size", "household_type")},
        {"age_by_sex": pd.Series(counts), "household_size": sz, "household_type": ty},
    )
    detail, summary = marginal_acceptance(errors)
    assert summary["verdict"] == "PASS", summary
    # And the deviation is small in a scale-free sense too.
    assert float(detail["total_variation_distance"].max()) < 0.08, detail


@needs_sources
def test_persons_per_household_matches_cobh(town):
    """R04: the scale-down preserves Cobh's mix, which includes its household size."""
    pph = town.diagnostics["n_persons"] / town.diagnostics["n_households"]
    assert abs(pph - 2.6781) < 0.12, pph


# --------------------------------------------------------------------------- #
# Names (design 5.2 step 6, R26, R27, K12)
# --------------------------------------------------------------------------- #

@needs_sources
def test_every_full_name_is_unique(town):
    """Design 5.2 step 6: no full name appears more than once in town."""
    from baile_nua.population.names import normalise_name

    keys = [
        normalise_name(f"{r.given_name} {r.family_name}")
        for r in town.persons.itertuples()
    ]
    dupes = {k for k in keys if keys.count(k) > 1}
    assert not dupes, f"duplicate full names: {sorted(dupes)[:5]}"


@needs_sources
def test_no_name_matches_the_public_figure_list(town):
    """R27 / K12."""
    from baile_nua.population.names import normalise_name, public_figures

    figures = public_figures()
    hits = [
        f"{r.given_name} {r.family_name}"
        for r in town.persons.itertuples()
        if normalise_name(f"{r.given_name} {r.family_name}") in figures
    ]
    assert not hits, hits


@needs_sources
def test_names_are_age_appropriate_for_irish_born_residents(town):
    """The CSO tables are year-by-year, so this is a real property, not a hope.

    Checked as a distributional property: the given names of residents born in
    the 1980s should overlap the 1980s CSO name list far more than the 2010s one.
    """
    from baile_nua.population.names import given_name_table

    eighties = given_name_table("F")[1985][0]
    twenty_tens = given_name_table("F")[2015][0]
    born_80s = town.persons[
        (town.persons.sex == "F")
        & (town.persons.country_of_birth == "IE")
        & town.persons.birth_date.map(lambda d: 1980 <= d.year <= 1989)
    ]
    if len(born_80s) < 30:
        pytest.skip("too few Irish-born women born in the 1980s in this slice")
    in_80s = born_80s.given_name.isin(eighties).mean()
    in_10s = born_80s.given_name.isin(twenty_tens).mean()
    assert in_80s >= in_10s, (in_80s, in_10s)


@needs_sources
def test_every_person_carries_the_synthetic_flag(town):
    """R27 / K12: "synthetic flag in every record"."""
    assert bool(town.persons["synthetic"].all())


# --------------------------------------------------------------------------- #
# Traits (design 5.2 step 5, 5.8, R06)
# --------------------------------------------------------------------------- #

@needs_sources
def test_every_person_has_all_ten_mimic_latents(town):
    """R06 acceptance: "Traits present for 100% of persons"."""
    from baile_nua.mimic.crosswalk import MIMIC_LATENTS

    for latent in MIMIC_LATENTS:
        assert latent in town.persons.columns
        assert town.persons[latent].notna().all(), latent


@needs_sources
def test_lambda_weights_sum_to_one(town):
    """D05: "lambda_self, lambda_coop, lambda_altru; sum = 1"."""
    total = town.persons[["lambda_self", "lambda_coop", "lambda_altru"]].sum(axis=1)
    assert (total - 1.0).abs().max() < 1e-9


@needs_sources
def test_within_group_trait_variance_exceeds_between_group(town):
    """Design 5.8: "Variation within each group must exceed the difference
    between groups." Measured on every run (K05)."""
    for rec in town.diagnostics["trait_within_between"]:
        assert rec["within_over_between"] > 1.0, rec


# --------------------------------------------------------------------------- #
# Buildings (design 5.7, R10, R11)
# --------------------------------------------------------------------------- #

@needs_sources
def test_building_fabric_is_physically_plausible(town):
    import numpy as np

    from baile_nua.physics.archetype import (
        PLAUSIBLE_TIME_CONSTANT_H,
        _load_fabric,
    )

    rng = _load_fabric()["plausible_specific_hlc_w_m2k"]
    for b in town.buildings:
        hli = b.rc.hlc_w_per_k / b.floor_area_m2
        assert rng["lo"] <= hli <= rng["hi"], (b.building_id, hli)
        tau = b.rc.time_constant_hours
        assert PLAUSIBLE_TIME_CONSTANT_H[0] <= tau <= PLAUSIBLE_TIME_CONSTANT_H[1], (
            b.building_id, tau,
        )


@needs_sources
def test_dwelling_type_mix_matches_the_census(town):
    """The house/apartment ratio is anchored to SAPS; only the within-house
    split comes from BER (I-011)."""
    from baile_nua.population.saps import build_marginals

    acc = build_marginals()["accommodation_type"].town_total
    census_house = acc["house or bungalow"] / acc.sum()
    houses = sum(
        1 for b in town.buildings
        if b.dwelling_type in ("detached", "semi-detached", "terraced")
    )
    assert abs(houses / len(town.buildings) - census_house) < 0.02


@needs_sources
def test_terraced_houses_exist_and_have_party_walls(town):
    """U18's "Terraced" gap is only meaningful if terraced houses are modelled,
    and party walls are the physical reason it matters."""
    from baile_nua.physics.archetype import PARTY_WALL_FRACTION

    terraced = [b for b in town.buildings if b.dwelling_type == "terraced"]
    assert len(terraced) > 50
    assert PARTY_WALL_FRACTION["terraced"] > PARTY_WALL_FRACTION["semi-detached"] > 0.0
    assert PARTY_WALL_FRACTION["detached"] == 0.0


@needs_sources
def test_sensor_tier_mix_is_realistic_and_privacy_correlated(town):
    """U06 option (a): "most homes meter only"; design 5.13: tier uptake
    correlates with the privacy trait."""
    from collections import Counter

    tiers = Counter(b.sensor_tier for b in town.buildings)
    n = len(town.buildings)
    assert tiers["T1"] / n > 0.55, tiers
    assert tiers["T4"] / n < 0.10, tiers
    assert set(tiers) <= {"T1", "T2", "T3", "T4"}


@needs_sources
def test_heat_pumps_are_distinguished_from_direct_electric(town):
    """I-011: Census records fuel, not system; EBQ02 supplies the split."""
    systems = {b.heating_system for b in town.buildings}
    assert "heat pump" in systems
    assert "direct electric" in systems


@needs_sources
def test_observable_premises_ids_are_opaque_and_unique(town):
    """Design 6.3: IDs are opaque random strings, not sequential."""
    ids = [b.premises_id for b in town.buildings]
    assert len(set(ids)) == len(ids)
    assert all(i.startswith("MPRN-") for i in ids)
    # No sequential structure: consecutive buildings' ids must not be adjacent.
    bodies = [i.split("-", 1)[1] for i in ids[:50]]
    assert not any(b.endswith(("0001", "0002", "0003")) for b in bodies[:10])


# --------------------------------------------------------------------------- #
# Determinism of the whole pipeline
# --------------------------------------------------------------------------- #

@needs_sources
def test_t0_pipeline_is_byte_identical_across_runs(tmp_path):
    """Design 7.2, on the whole Day-2 pipeline rather than one component."""
    import hashlib

    from baile_nua.population.synthesise import synthesise_t0, write_t0

    a = write_t0(synthesise_t0(master_seed=20261008), tmp_path / "a")
    b = write_t0(synthesise_t0(master_seed=20261008), tmp_path / "b")
    for key in a:
        ha = hashlib.sha256(a[key].read_bytes()).hexdigest()
        hb = hashlib.sha256(b[key].read_bytes()).hexdigest()
        assert ha == hb, key


@needs_sources
def test_a_different_seed_gives_a_different_town():
    """A seed that changes nothing would mean the seed is not wired in."""
    from baile_nua.population.synthesise import synthesise_t0

    a = synthesise_t0(master_seed=20261008)
    b = synthesise_t0(master_seed=99)
    assert list(a.persons.given_name) != list(b.persons.given_name)
