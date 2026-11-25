"""Leakage suite: GT/OBS/META separation (design 5.1, 6.3, 6.5, 7.7, R09).

    A leakage test in CI fails any benchmark dataset that contains a column from
    the first three layers.  (design 5.1)

    D19 contains no occupancy-level or GT field.  (traceability matrix R09)

The suite is generated from ``datasets.yaml`` (D-006): adding a GT field extends
the test automatically, and there is no hand-maintained deny-list to forget.
"""

from __future__ import annotations

import pandas as pd
import pytest

from baile_nua.io import PackageError, write_dataset
from baile_nua.schema import AccessClass
from baile_nua.schema.access import (
    LeakageError,
    SHARED_JOIN_KEYS,
    assert_no_forbidden_patterns,
    assert_no_gt_field_names,
    audit_frame,
    gt_field_names,
    hidden_layer_field_names,
    obs_field_names,
)

pytestmark = pytest.mark.leakage


# --------------------------------------------------------------------------- #
# Static properties of the schema itself
# --------------------------------------------------------------------------- #

def test_gt_and_obs_field_names_overlap_only_on_declared_join_keys(schema):
    """Any shared name is either a declared join key or a leak waiting to happen."""
    overlap = (gt_field_names(schema) & obs_field_names(schema)) - SHARED_JOIN_KEYS
    assert not overlap, (
        f"field names {sorted(overlap)} appear in both GT and OBS datasets but are "
        f"not in SHARED_JOIN_KEYS. Either add them there with a stated reason, or "
        f"rename one side."
    )


def test_no_hidden_layer_name_appears_in_any_obs_dataset(schema):
    bad = hidden_layer_field_names(schema) & obs_field_names(schema)
    assert not bad, sorted(bad)


def test_every_shared_join_key_is_actually_used(schema):
    """Keep SHARED_JOIN_KEYS honest: an unused exemption is an unexamined one."""
    everywhere = {f.name for ds in schema.datasets.values() for f in ds.fields}
    unused = SHARED_JOIN_KEYS - everywhere
    assert not unused, f"SHARED_JOIN_KEYS lists names nothing uses: {sorted(unused)}"


# --------------------------------------------------------------------------- #
# R09: no occupancy field is ever transmitted (E0-8)
# --------------------------------------------------------------------------- #

_CLEAN_D19 = {
    "premises_id": "MPRN-0123456789ABCDEF01",
    "interval_start": "2022-01-01T00:00:00Z",
    "interval_end": "2022-01-01T00:30:00Z",
    "import_wh": 250.0,
    "export_wh": 0.0,
    "interval_peak_w": 1200.0,
    "interval_min_w": 40.0,
    "export_config": "home_30min",
    "quality": "ok",
}


def test_a_clean_edge_export_passes():
    audit_frame(_CLEAN_D19.keys(), "D19")


@pytest.mark.parametrize(
    "field",
    [
        "occupancy",
        "occupancy_count",
        "occupants_living",
        "presence_flag",
        "person_id",
        "household_id",
        "n_adults",
        "n_children",
        "residents",
        "people_home",
        "activity_code",
        "asleep",
        "at_home",
        "away_flag",
        "trans",
        "willingness_score",
        "comfort_band_c",
    ],
)
def test_r09_refuses_every_occupancy_shaped_field(field):
    """R09 is name-based and content-blind on purpose: it is a statement about
    what is *transmitted*, not about what happens to be inferable.

    The assertion is against ``audit_frame``, the function the write path
    actually calls, so this tests the contract rather than one helper.  Some
    names are caught by the forbidden-pattern rule and some by the GT-name rule;
    which one fires is an implementation detail, that one of them does is not.
    """
    cols = {**_CLEAN_D19, field: 1}
    with pytest.raises(LeakageError):
        audit_frame(cols.keys(), "D19")


def test_r09_is_enforced_on_the_write_path(tmp_path):
    """Not just in a test helper: the writer itself must refuse."""
    frame = pd.DataFrame([{**_CLEAN_D19, "occupancy_count": 3}])
    with pytest.raises(LeakageError, match="R09"):
        write_dataset(frame, "D19", tmp_path / "v1" / "observable" / "edge_exports.parquet")


# --------------------------------------------------------------------------- #
# 5.14: forbidden profile fields are never exported to MIMIC
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "field",
    ["health_status", "fitness_level", "mobility_aid", "medical_device",
     "country_of_birth", "diagnosis", "disability"],
)
def test_mimic_export_refuses_the_forbidden_fields(field):
    with pytest.raises(LeakageError, match="forbidden field name"):
        assert_no_forbidden_patterns(["participant_id", field], "D25")


# --------------------------------------------------------------------------- #
# 6.3: whole datasets cannot be placed in the wrong package
# --------------------------------------------------------------------------- #

def test_gt_dataset_cannot_be_written_into_the_observable_package(tmp_path):
    frame = pd.DataFrame([{
        "presence_id": "PR-1", "person_id": "P-000001",
        "start": "2022-01-01T00:00:00Z", "end": "2022-01-01T07:00:00Z",
        "location_kind": "building", "location_id": "B-0001", "zone": "bedroom",
    }])
    with pytest.raises(PackageError, match="v1/ground_truth"):
        write_dataset(frame, "D11", tmp_path / "v1" / "observable" / "presence.parquet")


def test_obs_dataset_cannot_be_written_into_the_ground_truth_package(tmp_path):
    frame = pd.DataFrame([_CLEAN_D19])
    with pytest.raises(PackageError, match="v1/observable"):
        write_dataset(frame, "D19", tmp_path / "v1" / "ground_truth" / "edge_exports.parquet")


def test_every_dataset_resolves_to_exactly_one_package(schema):
    from baile_nua.schema.access import package_for

    for ds_id, ds in schema.datasets.items():
        pkg = package_for(ds_id, schema)
        assert pkg == {
            AccessClass.GT: "ground_truth",
            AccessClass.OBS: "observable",
            AccessClass.META: "evidence",
        }[ds.access_class]


# --------------------------------------------------------------------------- #
# 7.6: the RL information boundary
# --------------------------------------------------------------------------- #

def test_rl_observation_space_refuses_gt_and_reward_components():
    from baile_nua.rl import InterfaceAuditError, audit_observation_space

    audit_observation_space(["import_w", "export_w", "grid_signal"], "T1")
    for bad in (["import_w", "occupants_living"], ["import_w", "trans"],
                ["import_w", "lambda_self"], ["import_w", "discomfort_penalty"]):
        with pytest.raises(InterfaceAuditError):
            audit_observation_space(bad, "T1")


def test_rl_agent_cannot_see_a_channel_its_tier_lacks():
    from baile_nua.rl import InterfaceAuditError, audit_observation_space

    with pytest.raises(InterfaceAuditError, match="does not have"):
        audit_observation_space(["import_w", "ct_ev"], "T1")
    # the same channel is legal at T3
    audit_observation_space(["import_w", "ct_ev"], "T3")
