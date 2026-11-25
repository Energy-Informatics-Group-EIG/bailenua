"""Schema suite: datasets.yaml is the single source of truth (D-005, design 8.5).

These tests assert the *structural* rules the design states about the schema
itself, before any data exists.
"""

from __future__ import annotations

import re

import pytest

from baile_nua.schema import AccessClass, SchemaError, load
from baile_nua.schema.model import HIDDEN_LAYERS


def test_all_31_datasets_declared(schema):
    """Design 6.1 inventories 31 datasets. All must be present.

    Anything else in the schema must be the DECLARED observable view of one of
    them - BN-1 added ``D17_aggregate``, which D17 has named in ``obs_view``
    since the schema was written. A key that is neither one of the 31 nor a
    declared view is still a failure, so this is the exact-set assertion it
    replaces plus an account of what may legitimately join it.
    """
    expected = {f"D{i:02d}" for i in range(1, 32)}
    missing = sorted(expected - set(schema.datasets))
    assert not missing, f"design 6.1 datasets absent from the schema: {missing}"
    views = {d.obs_view for d in schema.datasets.values() if d.obs_view}
    stray = sorted(set(schema.datasets) - expected - views)
    assert not stray, (
        f"datasets {stray} are in the schema and are neither one of design "
        f"6.1's 31 nor any dataset's declared obs_view"
    )


def test_every_declared_obs_view_that_exists_is_an_obs_dataset(schema):
    """A view of a GT dataset is observable, or it is not a view."""
    for ds in schema.datasets.values():
        if ds.obs_view and ds.obs_view in schema.datasets:
            view = schema[ds.obs_view]
            assert view.access_class == AccessClass.OBS, (
                f"{ds.id} declares {ds.obs_view} as its observable view, but "
                f"{ds.obs_view} is access class {view.access_class}"
            )


def test_design_revision_is_frozen_at_3(schema):
    assert schema.design_revision == 3
    assert schema.design_frozen == "2026-10-08"


def test_every_output_carries_the_required_label(schema):
    assert schema.label == "UNVALIDATED SIMULATION EVIDENCE: E1 engineering candidate"


def test_access_class_is_one_of_three(schema):
    for ds in schema.datasets.values():
        assert ds.access_class in AccessClass.ALL, ds.id


@pytest.mark.leakage
def test_obs_fields_declare_a_mechanism(schema):
    """Design 6.5 rule 1.

    "Every OBS field must name the real-world mechanism that would produce it:
    a respondent answering, an assessor recording, an installer logging, a
    station measuring.  A field with no such mechanism is rejected at schema
    level."
    """
    offenders = {
        f"{ds.id}.{f.name}"
        for ds in schema.by_access(AccessClass.OBS).values()
        for f in ds.fields
        if not f.mechanism
    }
    assert not offenders, f"OBS fields with no declared mechanism: {sorted(offenders)}"


@pytest.mark.leakage
def test_obs_datasets_carry_no_hidden_layer_fields(schema):
    """Design 5.1: the first three layers are never visible to ML/RL."""
    offenders = {
        f"{ds.id}.{f.name} (layer={f.layer})"
        for ds in schema.by_access(AccessClass.OBS).values()
        for f in ds.fields
        if f.layer in HIDDEN_LAYERS
    }
    assert not offenders, sorted(offenders)


def test_the_ten_mimic_latents_are_present_with_mimic_names(schema):
    """Design 5.14 level 1: MIMIC's own names and scales."""
    expected = {
        "trans", "community", "env", "autonomy", "comfort",
        "conditional", "privacy", "instTrust", "idvZ", "satisficer",
    }
    got = {f.name for f in schema["D05"].fields if f.mimic_trait}
    assert got == expected


def test_lambda_weights_present(schema):
    """Design 5.13 / D05: lambda_1 to lambda_3, summing to 1."""
    names = set(schema["D05"].field_map)
    assert {"lambda_self", "lambda_coop", "lambda_altru"} <= names


def test_d19_forbids_occupancy_by_name(schema):
    """R09 / E0-8: no occupancy field is ever transmitted."""
    pats = schema["D19"].forbidden_field_patterns
    assert any(re.search(p, "occupancy_count") for p in pats)
    assert any(re.search(p, "n_adults") for p in pats)
    assert any(re.search(p, "household_id") for p in pats)


def test_d25_forbids_the_five_forbidden_profile_fields(schema):
    """Design 5.14 level 2 forbidden fields: health, fitness, mobility,
    medical device, country of birth."""
    pats = schema["D25"].forbidden_field_patterns
    for probe in ("health_condition", "fitness_tracker", "mobility_aid",
                  "medical_device", "country_of_birth"):
        assert any(re.search(p, probe) for p in pats), probe


def test_d15_is_gt_and_d31_is_obs(schema):
    """Design review log 23: D15 reclassified to GT, D31 is the station series."""
    assert schema["D15"].access_class == AccessClass.GT
    assert schema["D31"].access_class == AccessClass.OBS


def test_d20_and_d26_are_scoring_only(schema):
    """Design 6.1 / 5.14: change labels and the answer key go to the scoring
    API only, never to a model under test."""
    for ds_id in ("D20", "D26"):
        ds = schema[ds_id]
        assert ds.access_class == AccessClass.GT
        assert ds.access_note and "scoring" in ds.access_note.lower()


def test_d21_cluster_label_is_declared_forbidden(schema):
    """Design 5.13: no person is labelled by cluster, in GT or biographies."""
    f = schema["D21"].field_map["cluster_label"]
    assert f.forbidden is True


def test_d10_is_flagged_verified_not_calibrated(schema):
    """E0-2 / U04: no Irish time-use microdata, so the activity engine is
    verified, not calibrated."""
    status = schema["D10"].calibration_status or ""
    assert "NOT CALIBRATED" in status


def test_observable_datasets_are_keyed_by_premises(schema):
    """Design 6.4 item 2: observable data is keyed by premises, not household."""
    for ds_id in ("D18", "D19", "D27", "D28", "D29", "D30"):
        ds = schema[ds_id]
        assert ds.keyed_by == "premises", ds_id
        assert "premises_id" in ds.field_map, ds_id
        assert "household_id" not in ds.field_map, ds_id


def test_no_person_attribute_sits_on_a_building_table(schema):
    """R11: HRSD_Occupants is about occupants; buildings are a separate layer.
    Traceability matrix R11 acceptance: "No person attribute stored on building
    tables"."""
    person_only = {f.name for f in schema["D05"].fields} - {"seed", "synthetic", "pool"}
    for ds_id in ("D02", "D03"):
        overlap = person_only & set(schema[ds_id].field_map)
        assert not overlap, f"{ds_id} carries person attributes {sorted(overlap)}"


def test_loader_rejects_an_obs_field_with_no_mechanism(tmp_path):
    """The rule is enforced at load time, not at review time."""
    broken = tmp_path / "broken.yaml"
    broken.write_text(
        """
schema_version: "0.0.1"
design_revision: 3
design_frozen: "2026-10-08"
label: "test"
enums: {}
datasets:
  D99:
    name: broken_obs
    title: t
    access_class: OBS
    grain: g
    storage: parquet
    fields:
      - {name: a_value, type: float, required: true}
""",
        encoding="utf-8",
    )
    with pytest.raises(SchemaError, match="must name the real-world mechanism"):
        load(broken)


def test_loader_rejects_a_hidden_layer_field_in_an_obs_dataset(tmp_path):
    broken = tmp_path / "broken2.yaml"
    broken.write_text(
        """
schema_version: "0.0.1"
design_revision: 3
design_frozen: "2026-10-08"
label: "test"
enums: {}
datasets:
  D99:
    name: broken_obs2
    title: t
    access_class: OBS
    grain: g
    storage: parquet
    fields:
      - {name: trait_x, type: float, required: true, layer: persistent,
         mechanism: "pretends to be observable"}
""",
        encoding="utf-8",
    )
    with pytest.raises(SchemaError, match="hidden-layer"):
        load(broken)
