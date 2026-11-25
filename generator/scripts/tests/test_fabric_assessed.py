"""I-048 tested against SEAI's assessed U-values, not against an assumption.

The retrofit-state shares this work needed — what fraction of old dwellings
have filled cavities, how deep the loft insulation is — are exactly the kind of
number that could be quietly chosen to close the U31 gradient. They are not
chosen here and there is nothing to choose: SEAI's National BER Research Tool
publishes the **assessed** U-value of every element of every rated dwelling
with its year of construction and BER band, so the model is compared against
the real conditional distribution. The BER band already encodes the retrofit
state; the source says what U-value that state corresponds to.

PxStat has nothing: eighteen search terms, all empty, recorded in
``SEARCH_RECORD`` — and the fourteen hits for `wall` are every one of them
"wallet/purse", a substring collision like `sport` inside `transport`.
"""

from __future__ import annotations

import pytest

import baile_nua.sources_registry  # noqa: F401
from baile_nua.physics import fabric_assessed as FA


@pytest.fixture(scope="module")
def assessed():
    return FA.assessed_u_values()


def test_the_cache_is_built_from_the_registered_source(assessed):
    """A cache whose hash does not match the source is refused, not trusted."""
    import json

    from baile_nua.sources import REGISTRY

    manifest = json.loads(
        REGISTRY[FA.SOURCE_KEY].manifest_path.read_text(encoding="utf-8")
    )
    assert assessed["source_sha256"] == manifest["sha256"]
    assert assessed["rating_type"] == "Existing", (
        "new-build ratings would contaminate a question about retrofit"
    )
    assert assessed["n_assessed_dwellings"] > 500_000, assessed["n_cells"]


def test_every_cell_has_a_usable_count(assessed):
    """A median over 50 dwellings is not a population value."""
    assert assessed["n_cells"] >= 30
    for key, cell in assessed["cells"].items():
        assert cell["n"] >= FA.MIN_CELL_N, (key, cell["n"])
        for element in ("wall", "roof", "floor", "window"):
            v = cell[f"{element}_p50"]
            assert 0.05 < v < 8.0, (key, element, v)


def test_the_band_predicts_old_fabric_perfectly_and_new_fabric_weakly(assessed):
    """The structure that justifies the whole approach — and it is not uniform.

    Measured over about a million assessed existing dwellings:

    ===========  ==========  =================
    era          Spearman    wall spread A->G
    ===========  ==========  =================
    pre1919      **1.000**   0.25 -> 2.03 (x8.1)
    1919-1960    **1.000**   0.25 -> 2.03 (x8.1)
    1961-1980    **1.000**   0.27 -> 1.78 (x6.6)
    1981-2000    0.964       0.32 -> 0.59 (x1.8)
    2001+        0.657       0.27 -> 0.55 (x2.0)
    ===========  ==========  =================

    For old stock the BER band is a *perfect rank predictor* of the wall
    U-value across a factor of eight — the band carries the retrofit state
    exactly, which is why reading the conditional from the source needs no
    penetration share at all.

    For modern stock it barely predicts anything: a 2005 dwelling's wall meets
    the regulations whatever its band, so a poor band there comes from the
    heating system or the absence of renewables, not the fabric. The first
    version of this test asserted monotonicity everywhere and failed on 2001+
    at rho = 0.657 — correctly, because the premise was wrong rather than the
    data.

    This is also the shape of the model's error. A single band multiplier
    applies the same fabric response to every era, when the truth is a factor
    of eight on old stock and a factor of two on new.
    """
    from scipy import stats

    cells = assessed["cells"]
    rho_by_era: dict[str, float] = {}
    spread_by_era: dict[str, float] = {}
    for era in FA.ERA_CELLS:
        series = [
            (b, cells[f"{era}|{b}"]["wall_p50"])
            for b in FA.BAND_LETTERS if f"{era}|{b}" in cells
        ]
        assert len(series) >= 5, (era, series)
        values = [v for _b, v in series]
        rho_by_era[era], _p = stats.spearmanr(range(len(values)), values)
        spread_by_era[era] = values[-1] / values[0]

    for era in ("pre1919", "1919-1960", "1961-1980"):
        assert rho_by_era[era] > 0.95, (era, rho_by_era[era])
        assert spread_by_era[era] > 5.0, (era, spread_by_era[era])

    # And modern stock's fabric spread is small, whatever its bands say.
    assert spread_by_era["2001+"] < 3.0, spread_by_era
    assert spread_by_era["1981-2000"] < 3.0, spread_by_era
    assert rho_by_era["2001+"] < rho_by_era["pre1919"], rho_by_era


def test_an_old_retrofitted_dwelling_really_is_well_insulated(assessed):
    """The fact I-048's hypothesis rests on, read from the source.

    A pre-1919 dwelling rated A has an assessed wall U-value around 0.25 —
    better than the 2011 building regulations require of a new build. So Irish
    old stock genuinely does contain deeply retrofitted dwellings, and the
    model's era-derived fabric cannot represent them.
    """
    a = assessed["cells"]["pre1919|A"]
    g = assessed["cells"]["pre1919|G"]
    assert a["wall_p50"] < 0.35, a
    assert g["wall_p50"] > 1.8, g
    # A factor of eight within one construction era.
    assert g["wall_p50"] / a["wall_p50"] > 5.0


def test_the_model_is_too_lossy_on_old_stock_and_too_good_on_new():
    """I-048, quantified. Read from the evidence artefact, not recomputed.

    Measuring it twice from the same code would prove only that the code is
    deterministic; the artefact is what the finding is reported from, so the
    test asserts against that.
    """
    import json
    import pathlib

    p = (pathlib.Path(__file__).resolve().parents[2]
         / "v1" / "evidence" / "i048_fabric_assessed.json")
    if not p.exists():
        pytest.skip("i048_fabric_assessed.json not generated in this tree")
    doc = json.loads(p.read_text(encoding="utf-8"))
    wall = doc["result_wall"]
    assert wall["old_stock_pre1919_to_1980"]["model_over_assessed_median"] > 1.5
    assert wall["new_stock_1981_onwards"]["model_over_assessed_median"] < 0.9
    assert wall["old_over_new"] > 2.0, wall
    # And the direction holds on roofs too, conditional on band.
    roof = doc["result_roof"]
    assert roof["old_stock_pre1919_to_1980"]["model_over_assessed_median"] > 1.2
    assert roof["new_stock_1981_onwards"]["model_over_assessed_median"] < 1.0
    assert doc["nothing_was_fitted"]


def test_the_search_record_is_honest_about_px_stat():
    """Eighteen terms, and the one with hits is a substring collision."""
    from baile_nua.validation.assumption_sweep import load_catalogue, search

    cat = load_catalogue()
    zero_claims = [(t, v) for t, n, v in FA.SEARCH_RECORD if n == 0]
    assert len(zero_claims) >= 15, len(zero_claims)
    for term, verdict in zero_claims:
        hits = search(term, cat)
        assert not hits, (
            f"{term!r} is recorded as ZERO ({verdict}) but now returns "
            f"{len(hits)}: {[h.matrix for h in hits][:5]}"
        )
    # The 'wall' entry claims a collision; check it still is one.
    wall = [n for t, n, _v in FA.SEARCH_RECORD if t == r"[Ww]all"]
    assert wall and wall[0] == 14
    titles = [h.title for h in search(r"[Ww]all", cat)]
    assert titles and all("wallet" in t.lower() for t in titles), titles[:3]


def test_the_band_fallback_stays_within_the_era():
    """A thin cell falls back to the nearest BAND, never to an era average.

    An era average mixes retrofitted and unretrofitted stock, which is the
    very distinction the whole exercise is about.
    """
    # Every era/band combination must resolve without raising.
    for year in (1850, 1900, 1930, 1955, 1965, 1975, 1985, 1995, 2005, 2015, 2025):
        for band in ("A1", "B2", "C3", "D1", "E2", "F", "G"):
            v = FA.u_for(year, band, "wall")
            assert 0.05 < v < 5.0, (year, band, v)


def test_a_missing_or_stale_cache_is_an_error_not_a_default():
    assert issubclass(FA.AssessedFabricError, RuntimeError)
    with pytest.raises(FA.AssessedFabricError):
        FA.u_for(1900, "Z9", "wall")


def test_era_cells_cover_every_year():
    for year in range(1700, 2032):
        assert FA.era_cell(year) in FA.ERA_CELLS, year


# --------------------------------------------------------------------------- #
# exposure: this source calibrates fabric, so it may never validate fabric
# --------------------------------------------------------------------------- #

def test_the_source_is_declared_tuning_exposed():
    """Design 7.1. Once fabric is derived from it, it is the calibration side."""
    from baile_nua.sources import REGISTRY

    src = REGISTRY[FA.SOURCE_KEY]
    assert src.model_development_exposure == "tuning", (
        f"{FA.SOURCE_KEY} is declared {src.model_development_exposure!r}. The "
        f"model's element U-values are derived from it, so it is tuning-"
        f"exposed for fabric and must say so - otherwise a later reader could "
        f"use it to validate the thing it built."
    )
    assert src.intended_use == "calibration"
    assert "TUNING-EXPOSED FOR FABRIC" in src.used_for
    assert FA.FABRIC_EXPOSURE == "tuning"
    assert FA.VALIDATES_FABRIC is False


def test_using_it_as_a_fabric_validation_reference_always_raises():
    """No flag, no override: the attempt is the thing to catch.

    Modelled against assessed U-values would come out at 1.0 by construction,
    which is the most convincing-looking way for this project to fool itself.
    """
    with pytest.raises(FA.AssessedFabricError, match="TUNING-EXPOSED"):
        FA.assert_not_a_fabric_validation_reference("a plausibility check")
    with pytest.raises(FA.AssessedFabricError, match="1.0 by construction"):
        FA.assert_not_a_fabric_validation_reference()


def test_no_plausibility_check_or_calibration_target_reads_this_source():
    """The enforcement that survives someone forgetting the rule.

    Scanned by source inspection rather than by a registry of intentions,
    because a check added next month will not consult this test first.
    """
    import pathlib

    root = pathlib.Path(FA.__file__).resolve().parents[1]
    offenders = []
    for rel in ("plausibility", "calibration", "report"):
        for path in (root / rel).rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if FA.SOURCE_KEY in text or "fabric_assessed" in text:
                offenders.append(str(path.relative_to(root)))
    assert not offenders, (
        f"these modules reference the fabric calibration source: {offenders}. "
        f"Plausibility checks, calibration targets and report artefacts are "
        f"where a validation claim gets made, and this source cannot support "
        f"one about fabric. The independent axis is gas "
        f"({', '.join(FA.FABRIC_VALIDATION_SOURCES)})."
    )


def test_the_i048_finding_is_marked_as_pre_exposure():
    """What makes 1.913/0.750 a finding rather than a description of a fit."""
    import json
    import pathlib

    assert FA.I048_MEASURED_BEFORE_EXPOSURE is True
    # parents[3]: physics -> baile_nua -> scripts -> repo root.
    p = (pathlib.Path(FA.__file__).resolve().parents[3]
         / "v1" / "evidence" / "i048_fabric_assessed.json")
    if not p.exists():
        pytest.skip("i048_fabric_assessed.json not generated in this tree")
    doc = json.loads(p.read_text(encoding="utf-8"))
    assert "measured_before_exposure" in doc, (
        "the artefact must record that the comparison predates the "
        "derivation, or a later reader cannot tell a finding from a fit"
    )
    assert doc["measured_before_exposure"]["pre_exposure"] is True


def test_the_gas_axis_that_validates_fabric_is_still_held_out():
    """DBERNG02 must stay at exposure "none" for U31 to mean anything."""
    from baile_nua.sources import REGISTRY

    for key in FA.FABRIC_VALIDATION_SOURCES:
        if key not in REGISTRY:
            continue
        src = REGISTRY[key]
        if "dberng02" in key or "construction" in key:
            assert src.model_development_exposure == "none", (
                f"{key} is the held-out gas table and is declared "
                f"{src.model_development_exposure!r}. If it has been used for "
                f"tuning, U31's gradient is not a generalisation check."
            )
