"""MIMIC alignment suite (design 5.13, 5.14; day 1 and day 3 acceptance).

Day 1 acceptance criterion, design 9.3:

    schema diff against MIMIC 1.1 lists only the U18 gaps

Every constant the crosswalk relies on is also re-read from the MIMIC working
tree, so a change there fails here rather than silently exporting wrong coding.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from baile_nua.mimic.crosswalk import (
    MIMIC_FORBIDDEN_FIELDS,
    MIMIC_LATENTS,
    MIMIC_PRIMARY_FIELDS,
    MIMIC_SCHEMA_VERSION,
    MIMIC_VALUE_SETS,
    age_band_for,
    schema_diff,
    self_report_from_latent,
    u18_gaps,
    verify_against_mimic_source,
)

pytestmark = pytest.mark.mimic

MIMIC_ROOT = Path(
    os.environ.get("BAILE_NUA_MIMIC_ROOT", "/Users/brianoregan/Documents/GitHub/mimic")
)
_have_mimic = (MIMIC_ROOT / "database" / "schema.sql").is_file()
needs_mimic = pytest.mark.skipif(not _have_mimic, reason=f"MIMIC tree not at {MIMIC_ROOT}")


# --------------------------------------------------------------------------- #
# Day 1 acceptance
# --------------------------------------------------------------------------- #

def test_schema_diff_lists_only_the_u18_gaps(schema):
    """The Day 1 acceptance criterion, asserted directly."""
    diff = schema_diff(schema)
    assert diff["mimic_schema_version"] == MIMIC_SCHEMA_VERSION
    assert diff["unmapped_mimic_fields"] == [], (
        "every MIMIC primary field must be mapped (R29 acceptance: zero unmapped "
        "MIMIC fields except the gaps listed in U18)"
    )
    assert diff["unknown_hrsd_fields"] == []
    assert diff["n_mapped"] == len(MIMIC_PRIMARY_FIELDS) == 16
    gaps = {(g["mimic_field"], g["missing_value"]) for g in diff["value_set_gaps"]}
    assert gaps == {
        ("profiles.employment_status", "Home duties"),
        ("profiles.dwelling_type", "Terraced"),
    }


def test_optional_fields_are_mapped_as_a_group(schema):
    """Design 5.14 maps ``profile_optional.*`` (the 10 permitted fields)."""
    assert schema_diff(schema)["optional_fields_mapped_as_group"] is True


def test_every_u18_gap_states_what_information_is_lost():
    """A gap mapped to another value must say what the mapping costs, so the
    E1 report can carry it rather than hiding it behind "mapped to Other"."""
    for g in u18_gaps():
        assert g.information_lost and len(g.information_lost) > 40, g.mimic_field
        assert g.recommendation.endswith("(U18).")
        assert g.mapped_to in MIMIC_VALUE_SETS[g.mimic_field.split(".", 1)[1]]


# --------------------------------------------------------------------------- #
# Level 1: one trait model
# --------------------------------------------------------------------------- #

def test_hrsd_uses_mimics_own_latent_names(schema):
    """Design 5.14 level 1: same names and scales as mimic_sd_generator.php."""
    hrsd = {f.name for f in schema["D05"].fields if f.mimic_trait}
    assert hrsd == set(MIMIC_LATENTS)


def test_self_report_mapping_matches_mimics_php_rounding():
    """``clampi(round(3 + 1.05*latent), 1, 5)``.

    PHP's ``round()`` is half-away-from-zero; Python's is banker's rounding.
    The boundary cases are where they disagree, so they are the cases tested.
    """
    assert self_report_from_latent(0.0) == 3
    assert self_report_from_latent(10.0) == 5
    assert self_report_from_latent(-10.0) == 1
    # 3 + 1.05*(-1.42857...) = 1.5 exactly -> PHP gives 2, banker's gives 2 as well
    # 3 + 1.05*0.47619 = 3.5 -> PHP gives 4, Python's round() would give 4
    assert self_report_from_latent(0.476190476190476) == 4
    # 3 + 1.05*(-0.476190476) = 2.5 -> PHP gives 3; Python's round(2.5) gives 2
    assert self_report_from_latent(-0.476190476190476) == 3


def test_age_bands_use_mimics_en_dash():
    """I-003 exists because the separator matters. HRSD must emit the en-dash."""
    assert age_band_for(60) == "55–64"
    assert "–" in age_band_for(60), "must be U+2013 EN DASH, not a hyphen"
    assert age_band_for(18) == "18–24"
    assert age_band_for(90) == "65+"


def test_minors_are_refused_an_age_band():
    """Design 5.14: every synthetic ADULT can take part. Minors must not."""
    with pytest.raises(ValueError, match="under 18"):
        age_band_for(17)


# --------------------------------------------------------------------------- #
# Level 2: identical coding, and the forbidden fields
# --------------------------------------------------------------------------- #

def test_forbidden_fields_are_exactly_mimics_five(schema):
    """ProfileService::FORBIDDEN_FIELDS, by MIMIC's exact names."""
    import re

    pats = schema["D25"].forbidden_field_patterns
    for field in MIMIC_FORBIDDEN_FIELDS:
        assert any(re.search(p, field) for p in pats), field


def test_d25_never_declares_a_forbidden_field(schema):
    """The export schema itself must not contain one."""
    assert not (set(schema["D25"].field_map) & set(MIMIC_FORBIDDEN_FIELDS))


# --------------------------------------------------------------------------- #
# Drift guard against the real MIMIC tree
# --------------------------------------------------------------------------- #

@needs_mimic
def test_mimic_source_still_matches_the_recorded_constants():
    """No MIMIC value set is recalled; all are re-read and compared."""
    findings = verify_against_mimic_source(MIMIC_ROOT)
    assert findings["ok"], findings["drifted"]
    assert findings["checks"]["PRIMARY_FIELDS"]
    assert findings["checks"]["FORBIDDEN_FIELDS"]
    assert findings["checks"]["schema_version_1_1"]
    assert findings["checks"]["session_length_13"]


@needs_mimic
def test_i003_defect_is_still_present_and_reported():
    """I-003: the hyphen/en-dash defect.

    Asserted as *present* on purpose. The brief says to report it, not fix it,
    so this test is the record that it is still there. When the MIMIC team fixes
    it, this test fails and ISSUES.md I-003 is closed deliberately.
    """
    findings = verify_against_mimic_source(MIMIC_ROOT)
    assert findings["checks"]["I003_hyphen_vs_endash_defect_still_present"] is True
    ids = {d["id"] for d in findings["defects"]}
    assert "I-003" in ids


@needs_mimic
def test_u18_gaps_are_confirmed_in_mimic_source():
    findings = verify_against_mimic_source(MIMIC_ROOT)
    assert findings["checks"]["U18_no_home_duties_value"] is True
    assert findings["checks"]["U18_no_terraced_value"] is True
