"""D25 (OBS) and D26 (GT): schema conformance, and the crosswalk in D26 only.

Design 5.14 level 2 puts the crosswalk to ``person_id``, the true traits, the
planted segments, the response propensity and the stated-preference gap in the
**answer key** and nowhere else: D26 is GT, "scoring only. Never written into
MIMIC".  D25 is what MIMIC legitimately holds.

The important property is enforced structurally rather than by inspection:
``person_id`` is not a declared D25 field, so the schema's own
``assert_fields_declared`` refuses it and ``write_dataset``'s
``strict_columns`` refuses it again.  Both refusals are tested here, because a
property guaranteed by a check nobody exercises is a property nobody has.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from baile_nua.mimic.datasets import D25_FIELDS, D26_FIELDS, d26_frame
from baile_nua.schema import load
from baile_nua.schema.access import LeakageError

pytestmark = pytest.mark.mimic

MAIN_TREE = Path("/Users/brianoregan/Desktop/HRSD_Occupants")
D25_PART = MAIN_TREE / "v1" / "observable" / "D25_part000.parquet"
D26_PART = MAIN_TREE / "v1" / "ground_truth" / "D26_part000.parquet"

#: The manifest keys the engine's own writer emits
#: (``baile_nua.io.write_dataset``, used by ``engine/stream_writer.py``).
REQUIRED_MANIFEST_KEYS = (
    "rows", "columns", "access_class", "release_package",
    "content_hash_sha256", "file_sha256",
)

#: Every field name that would carry the crosswalk or the hidden layer into an
#: OBS export.  None of these may appear in D25.
CROSSWALK_AND_TRUTH = (
    "person_id", "true_traits", "planted_segment", "response_propensity",
    "stated_gap", "satisficer", "planted_position_bias", "household_id",
    "building_id", "premises_id", "wave_person_key",
)


# --------------------------------------------------------------------------- #
# The schema is the source of truth, and this module must not drift from it
# --------------------------------------------------------------------------- #

def test_d25_module_fields_are_exactly_the_schemas(schema):
    declared = list(schema["D25"].field_map)
    assert list(D25_FIELDS) == declared, (
        "datasets.py's D25 field list has drifted from datasets.yaml, which is "
        "the single source of truth"
    )


def test_d26_module_fields_are_exactly_the_schemas(schema):
    declared = list(schema["D26"].field_map)
    assert list(D26_FIELDS) == declared


def test_d25_is_obs_and_d26_is_gt(schema):
    assert str(schema["D25"].access_class).endswith("OBS")
    assert str(schema["D26"].access_class).endswith("GT")
    assert "scoring only" in schema["D26"].access_note.lower()


def test_the_crosswalk_is_not_a_declared_d25_field(schema):
    for name in CROSSWALK_AND_TRUTH:
        assert name not in schema["D25"].field_map, (
            f"D25 declares {name!r}; the crosswalk and the hidden layer belong "
            f"in D26 (design 5.14 level 2)"
        )


def test_the_crosswalk_and_the_truth_are_declared_d26_fields(schema):
    for name in ("person_id", "true_traits", "planted_segment",
                 "response_propensity", "stated_gap",
                 "planted_position_bias", "simulated_session_date"):
        assert name in schema["D26"].field_map


# --------------------------------------------------------------------------- #
# The refusals
# --------------------------------------------------------------------------- #

def test_a_d25_frame_carrying_person_id_is_refused():
    from baile_nua.schema.access import audit_frame

    with pytest.raises(LeakageError):
        audit_frame([*D25_FIELDS, "person_id"], "D25")


def test_a_d25_frame_carrying_true_traits_is_refused():
    from baile_nua.schema.access import audit_frame

    with pytest.raises(LeakageError):
        audit_frame([*D25_FIELDS, "true_traits"], "D25")


def test_the_declared_d25_columns_are_accepted():
    from baile_nua.schema.access import audit_frame

    audit_frame(list(D25_FIELDS), "D25")      # must not raise


# --------------------------------------------------------------------------- #
# D26 from answer keys
# --------------------------------------------------------------------------- #

def _answer_keys() -> list[dict]:
    keys = []
    # A linked panel person across three waves, and two unlinked pool people.
    for wave, date in enumerate(("2022-01-14", "2026-05-02", "2031-11-20"), start=1):
        keys.append({
            "participant_id": f"0000000{wave}-0000-4000-8000-000000000000",
            "person_id": "P-000123", "wave_person_key": f"P-000123-w{wave:02d}",
            "wave": wave, "n_waves": 3, "pool": "BN-panel", "stratum": "panel",
            "true_traits": {"trans": 0.2, "community": -0.1},
            "planted_segment": None, "planted_null_mode": False,
            "response_propensity": 0.61, "stated_gap": 0.21, "satisficer": False,
            "planted_position_bias": 0.0, "generator": "G-B",
            "gb_spec_hash": "deadbeef", "simulated_session_date": date,
            "test_mode_settings": {"local_only": True},
            "u18_information_lost": [],
        })
    for i in (1, 2):
        keys.append({
            "participant_id": f"1000000{i}-0000-4000-8000-000000000000",
            "person_id": f"HP-000000{i}", "wave_person_key": f"HP-000000{i}",
            "wave": None, "n_waves": None, "pool": "HRSD-pool",
            "stratum": "cobh_full",
            "true_traits": {"trans": 0.0, "community": 0.0},
            "planted_segment": "SEG-1", "planted_null_mode": False,
            "response_propensity": 0.4, "stated_gap": 0.1, "satisficer": True,
            "planted_position_bias": 1.6, "generator": "G-B",
            "gb_spec_hash": "deadbeef", "simulated_session_date": None,
            "test_mode_settings": {"local_only": True},
            "u18_information_lost": ["employment_status: 'home duties' -> 'Unemployed'"],
        })
    # Consent never granted: no participant row, so no D26 row.
    keys.append({**keys[0], "participant_id": None})
    return keys


@pytest.fixture(scope="module")
def d26():
    frame, diag = d26_frame(_answer_keys(),
                            planted_context_effect={"grid_stress": {"gain": 0.45}})
    return frame, diag


def test_d26_validates_against_the_schema(d26):
    from baile_nua.schema.validate import coerce_frame, validate_frame

    frame, _ = d26
    out = coerce_frame(frame, "D26")
    validate_frame(out, "D26", strict_columns=True)


def test_d26_drops_a_participant_that_was_never_created(d26):
    frame, _ = d26
    assert len(frame) == 5, "a row with no participant_id cannot be in D26"
    assert frame["participant_id"].notna().all()


def test_d26_carries_the_crosswalk_and_the_truth(d26):
    frame, diag = d26
    assert diag["crosswalk_present"] is True
    assert frame["person_id"].notna().all()
    assert frame["true_traits"].notna().all()
    assert frame["response_propensity"].notna().all()
    assert frame["stated_gap"].notna().all()
    assert frame["planted_context_effect"].notna().all()
    assert (frame.loc[frame["pool"] == "HRSD-pool", "planted_segment"]
            == "SEG-1").all()


def test_d26_makes_the_panel_a_panel(d26):
    """One person, several rows, ordered in simulated time (I-075)."""
    frame, diag = d26
    panel = frame[frame["pool"] == "BN-panel"]
    assert panel["person_id"].nunique() == 1
    assert len(panel) == 3
    dates = list(panel["simulated_session_date"])
    assert dates == sorted(dates), "D26 must be ordered within a person"
    assert len(set(dates)) == 3
    assert diag["linked_panel_rows_undated"] == 0
    assert diag["max_rows_per_person"] == 3


def test_d26_keeps_the_wave_in_the_test_mode_settings(d26):
    frame, _ = d26
    panel = frame[frame["pool"] == "BN-panel"]
    waves = [json.loads(s)["wave"] for s in panel["test_mode_settings"]]
    assert sorted(waves) == [1, 2, 3]


def test_an_unlinked_pool_row_has_no_simulated_date(d26):
    """The pool is unlinked by design and has no position in simulated time."""
    frame, _ = d26
    pool = frame[frame["pool"] == "HRSD-pool"]
    assert pool["simulated_session_date"].isna().all()


def test_d26_round_trips_through_the_writer(tmp_path, d26):
    from baile_nua.mimic.datasets import write_d26

    frame, _ = d26
    path = write_d26(frame, tmp_path)
    assert path.name == "D26_part000.parquet"
    man = json.loads((path.parent / f"{path.stem}.manifest.json").read_text())
    for key in REQUIRED_MANIFEST_KEYS:
        assert key in man, f"the manifest has no {key!r}"
    assert man["rows"] == len(frame)
    assert man["access_class"] == "GT"
    assert man["release_package"] == "ground_truth"
    back = pd.read_parquet(path)
    assert list(back.columns) == list(D26_FIELDS)
    assert "person_id" in back.columns


def test_d26_cannot_be_written_into_the_observable_package(tmp_path, d26):
    from baile_nua.io import PackageError, write_dataset

    frame, _ = d26
    with pytest.raises(PackageError):
        write_dataset(frame, "D26", tmp_path / "v1" / "observable" / "D26.parquet")


# --------------------------------------------------------------------------- #
# The parts the run actually wrote
# --------------------------------------------------------------------------- #

def _read_back(path: Path) -> pd.DataFrame:
    """Read a written part, normalising Parquet list columns back to lists.

    ``schema.validate._check_type`` accepts a ``list[...]`` column only when
    its values are ``list`` or ``tuple``, and pandas hands back a
    ``numpy.ndarray`` for an Arrow ``list<element: int64>`` column. So a frame
    that validated at write time does **not** validate when read back, through
    no fault of the data: the Parquet type is right (verified
    ``list<element: int64>``) and only the in-memory representation differs.

    Normalised here rather than fixed in the validator, because
    ``baile_nua/schema/`` is not this agent's to change. Reported to the
    coordinator as a project-side finding: any consumer who reads a part back
    and re-validates it will hit this on every ``list[...]`` field, and D25 is
    simply the first dataset to have one with data in it.
    """
    frame = pd.read_parquet(path)
    for col in frame.columns:
        if frame[col].map(lambda v: isinstance(v, np.ndarray)).any():
            frame[col] = frame[col].map(
                lambda v: list(v) if isinstance(v, np.ndarray) else v
            )
    return frame


@pytest.mark.skipif(not D25_PART.is_file(), reason=f"no {D25_PART}")
def test_written_d25_conforms_and_holds_no_crosswalk():
    from baile_nua.schema.validate import validate_frame

    frame = _read_back(D25_PART)
    validate_frame(frame, "D25", strict_columns=True)
    for name in CROSSWALK_AND_TRUTH:
        assert name not in frame.columns
    man = json.loads(
        (D25_PART.parent / f"{D25_PART.stem}.manifest.json").read_text()
    )
    for key in REQUIRED_MANIFEST_KEYS:
        assert key in man
    assert man["rows"] == len(frame)
    assert man["access_class"] == "OBS"
    assert man["release_package"] == "observable"
    assert man["leakage_audit"].startswith("passed")
    assert list(man["columns"]) == list(frame.columns)
    assert frame["consent_version"].str.startswith("SYNTHETIC").all(), (
        "every exported row must be purgeable by MIMIC's own predicate"
    )


@pytest.mark.skipif(not D26_PART.is_file(), reason=f"no {D26_PART}")
def test_written_d26_conforms_and_carries_the_panel_in_time():
    from baile_nua.schema.validate import validate_frame

    frame = _read_back(D26_PART)
    validate_frame(frame, "D26", strict_columns=True)
    assert "person_id" in frame.columns
    man = json.loads(
        (D26_PART.parent / f"{D26_PART.stem}.manifest.json").read_text()
    )
    for key in REQUIRED_MANIFEST_KEYS:
        assert key in man
    assert man["access_class"] == "GT"
    assert man["release_package"] == "ground_truth"

    panel = frame[frame["pool"] == "BN-panel"]
    assert len(panel) > 0, "D26 holds no linked panel row"
    assert panel["simulated_session_date"].notna().all(), (
        "a linked panel row with no simulated_session_date is I-075 unfixed"
    )
    per_person = panel.groupby("person_id")["participant_id"].count()
    assert per_person.max() >= 8, (
        f"the busiest linked person has {per_person.max()} sessions; the design "
        f"asks for 8 to 15 across the decade"
    )
    years = {str(d)[:4] for d in panel["simulated_session_date"]}
    assert len(years) >= 8, f"the panel covers only {sorted(years)}"


@pytest.mark.skipif(not (D25_PART.is_file() and D26_PART.is_file()),
                    reason="both parts are needed")
def test_d25_and_d26_join_only_through_the_answer_key():
    """D25 alone cannot be resolved to a person; with D26 it can."""
    d25 = pd.read_parquet(D25_PART, columns=["participant_id"])
    d26 = pd.read_parquet(D26_PART, columns=["participant_id", "person_id"])
    assert set(d25["participant_id"]) <= set(d26["participant_id"]), (
        "every exported participant must have an answer-key row"
    )
    assert d26["participant_id"].is_unique, "D26's grain is one row per participant"
