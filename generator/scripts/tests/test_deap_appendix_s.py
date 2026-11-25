"""DEAP Appendix S, extracted from the manual rather than transcribed.

`data/fabric_u_values.yaml` carried every era U-value in the model as one `[A]`
flag — *"not read back from the Part L documents in this run; verify in WP1"* —
and I-048's retrofit hypothesis is a claim about exactly those numbers. The
source was already fetched: DEAP's Appendix S publishes fabric defaults for
*existing* dwellings, and that is the regulatory methodology every Irish BER is
computed with.

These tests do two jobs. They check the parse still matches the document, so a
value cannot drift from the source it claims; and they record what the
comparison against the model found, which was not what I-048 predicted.
"""

from __future__ import annotations

import pytest

import baile_nua.sources_registry  # noqa: F401
from baile_nua.physics import deap_appendix_s as S
from baile_nua.physics.archetype import _load_fabric


@pytest.fixture(scope="module")
def tables():
    return S.appendix_s()


def test_the_twelve_age_bands_parse(tables):
    s1 = tables["S1_age_bands"]
    assert list(S.BAND_ORDER) == list("ABCDEFGHIJKL")
    assert s1["A"].lower().startswith("before 1900")
    assert "2014" in s1["L"] and "onwards" in s1["L"].lower()
    for band in S.BAND_ORDER:
        assert s1[band], band


def test_the_band_lookup_covers_the_whole_range():
    """Every year the town can contain has to land in a band."""
    assert S.band_for_year(1850) == "A"
    assert S.band_for_year(1899) == "A"
    assert S.band_for_year(1900) == "B"
    assert S.band_for_year(1966) == "D"
    assert S.band_for_year(1967) == "E"
    assert S.band_for_year(2004) == "I"
    assert S.band_for_year(2014) == "L"
    assert S.band_for_year(2031) == "L"
    # And the gaps the manual's own ranges leave are closed rather than raising.
    for year in range(1800, 2032):
        assert S.band_for_year(year) in S.BAND_ORDER, year


def test_the_regulations_summary_parses_seven_rows(tables):
    regs = tables["S2_regulations"]
    assert len(regs) == 7, [r["year"] for r in regs]
    by_band = {r["band"]: r for r in regs}
    # Spot-checks against the document, each a different row.
    assert by_band["G"]["wall"] == 0.6
    assert by_band["H"]["wall"] == 0.55
    assert by_band["J"] == {"year": "2002", "band": "J", "roof": 0.25,
                            "wall": 0.37, "floor": 0.37}
    assert by_band["L"]["wall"] == 0.21
    # U-values must improve monotonically with the regulation year.
    walls = [by_band[b]["wall"] for b in "FGHIJKL"]
    assert walls == sorted(walls, reverse=True), walls


def test_table_s2_floor_for_h_and_i_is_the_ground_floor_value(tables):
    """The manual prints "0.45 / 0.6" with a footnote; the parse takes 0.45.

    Footnote 39: ".45 = ground floor, .6 = exposed / semi exposed floor". The
    model's floor element is the ground floor, so 0.45 is the right half — and
    this test exists because a parse that silently took the other one would
    change every old dwelling's floor loss by a third.
    """
    by_band = {r["band"]: r for r in tables["S2_regulations"]}
    assert by_band["H"]["floor"] == 0.45
    assert by_band["I"]["floor"] == 0.45


def test_the_wall_table_has_every_type_and_band(tables):
    walls = tables["S3_walls"]
    assert len(walls) >= 11, sorted(walls)
    for name, row in walls.items():
        assert sorted(row) == sorted(S.BAND_ORDER), name
        assert all(0.1 < v < 3.0 for v in row.values()), (name, row)
    assert walls["Unknown"]["A"] == 2.1
    assert walls["Stone"]["A"] == 2.1
    assert walls["concrete hollow block"]["A"] == 2.4


def test_the_filled_cavity_rows_are_the_published_retrofit(tables):
    """The number I-048's hypothesis needed, and it is in the regulation.

    A filled cavity is 0.6 for every band from A to G — so DEAP itself says a
    pre-1900 dwelling whose cavity has been insulated has a wall U-value of
    0.6, not the 2.1 its age band otherwise implies.
    """
    walls = tables["S3_walls"]
    assert tables["S3_filled_cavity_rows"] == [
        "300mm filled cavity", "425 mm filled cavity"
    ]
    for name in tables["S3_filled_cavity_rows"]:
        row = walls[name]
        for band in "ABCDEFG":
            assert row[band] == 0.6, (name, band, row[band])
        # From H onward the regulations are already at least as good, so the
        # filled-cavity row stops being a distinct case.
        assert row["H"] == walls["Unknown"]["H"]
        assert row["L"] == walls["Unknown"]["L"]


def test_the_roof_insulation_series_is_monotone(tables):
    s4 = tables["S4_roof_by_insulation_mm"]
    assert s4["None"] == 2.3
    order = ["None", "12", "25", "50", "75", "100", "150", "200", "250", ">=300"]
    assert list(s4) == order or set(s4) == set(order), sorted(s4)
    vals = [s4[k] for k in order]
    assert vals == sorted(vals, reverse=True), vals
    assert s4[">=300"] == 0.13


def test_the_unknown_thickness_roof_defaults(tables):
    s5 = tables["S5_roof_unknown_thickness"]
    for band in "ABCDE":
        assert s5[band] == 2.3, band
    assert s5["F"] == s5["G"] == 0.49
    assert s5["L"] == 0.20


# --------------------------------------------------------------------------- #
# what the comparison against the model found
# --------------------------------------------------------------------------- #

#: The model's era labels mapped onto DEAP's bands. Approximate by
#: construction — the model's eras and DEAP's bands do not share boundaries —
#: so this is only used for the comparisons below, never to derive a U-value.
_ERA_TO_BAND = {
    "pre 1919": "A", "1919-1945": "B", "1946-1960": "C", "1961-1970": "D",
    "1971-1980": "E", "1981-1990": "G", "1991-2000": "H", "2001-2010": "J",
    "2011-2015": "K", "2016 or later": "L",
}


def test_the_model_s_modern_walls_already_are_deap_s(tables):
    """So that part of the `[A]` flag is a match, not a correction.

    From band G onward the model's wall U-values are the regulation values to
    two decimals. Finding this mattered as much as finding the mismatch: it
    says the era table was not guessed, and it localises I-048's problem to the
    old bands rather than leaving it general.
    """
    eras = _load_fabric()["eras"]
    walls = tables["S3_walls"]["Unknown"]
    for era in ("1981-1990", "1991-2000", "2001-2010"):
        band = _ERA_TO_BAND[era]
        assert eras[era]["wall"] == pytest.approx(walls[band], abs=0.001), (
            era, band, eras[era]["wall"], walls[band]
        )


def test_the_model_s_old_walls_never_reach_the_filled_cavity_value(tables):
    """The gap I-048's hypothesis is about, measured.

    The best the band multiplier can do is `much_better` = 0.55, so a band-A
    wall bottoms out at 2.1 x 0.55 = 1.155 against DEAP's published 0.6 for a
    filled cavity in the same band — a factor of 1.9.
    """
    fabric = _load_fabric()
    eras = fabric["eras"]
    best_multiplier = min(fabric["ber_band_fabric_multiplier"].values())
    filled = tables["S3_walls"]["300mm filled cavity"]
    for era in ("pre 1919", "1919-1945", "1946-1960", "1961-1970", "1971-1980"):
        band = _ERA_TO_BAND[era]
        floor_value = eras[era]["wall"] * best_multiplier
        assert floor_value > filled[band], (
            f"{era}: the model can reach {floor_value:.3f} and DEAP publishes "
            f"{filled[band]} for a filled cavity, so there is nothing to fix"
        )
    # The size of it, at the oldest band.
    assert eras["pre 1919"]["wall"] * best_multiplier == pytest.approx(1.155)
    assert filled["A"] == 0.6


def test_the_model_s_old_roofs_are_already_far_better_than_deap_s_default(tables):
    """The finding that cuts the other way, and it is why this is measured.

    The model's own data file says its roofs are at "typical CURRENT
    (post-retrofit) condition", and against DEAP's unknown-thickness default
    of 2.3 for bands A to E they are four to five times better. So a generous
    roof retrofit was already assumed. Correcting walls alone therefore has an
    uncertain net effect, which is why I-048 cannot be settled by argument.
    """
    eras = _load_fabric()["eras"]
    s5 = tables["S5_roof_unknown_thickness"]
    s4 = tables["S4_roof_by_insulation_mm"]
    for era in ("pre 1919", "1946-1960", "1971-1980"):
        band = _ERA_TO_BAND[era]
        ratio = eras[era]["roof"] / s5[band]
        assert ratio < 0.30, (era, eras[era]["roof"], s5[band], ratio)
    # And the model's value corresponds to a real, nameable insulation depth:
    # DEAP S4 puts 75 mm at 0.5 and 50 mm at 0.68.
    assert s4["75"] == 0.5
    assert s4["50"] == 0.68
    assert s4["75"] <= eras["pre 1919"]["roof"] <= s4["50"], (
        "the model's pre-1919 roof no longer sits between DEAP's 50 mm and "
        "75 mm loft-insulation values, so the 'post-retrofit condition' claim "
        "in the data file needs restating"
    )


def test_the_extractor_fails_loudly_rather_than_returning_a_bad_parse():
    """A silent mis-parse would put wrong U-values into every dwelling."""
    assert issubclass(S.ExtractionError, RuntimeError)
    with pytest.raises(KeyError):
        S.wall_u_values("a wall type the manual does not have")
