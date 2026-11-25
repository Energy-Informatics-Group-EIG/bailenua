"""D04 and D24: what they fill, what they leave null, and that the null is declared.

Both datasets are written with required columns still null, which is only
honest if three things hold, and this file checks each of them.

* **The declared-null mechanism is narrow.**  ``validate_frame``'s
  ``permit_null_required`` relaxes nothing but the required-null check, refuses
  a field that is not actually required, and still demands the column be
  PRESENT.  ``write_dataset`` refuses an exemption with no stated reason and
  records every one it accepts in the part's sidecar manifest.
* **The exemption lists are true of the schema.**  Every key in
  ``assets.NULL_REQUIRED`` and ``calibration_targets.NULL_REQUIRED`` is a field
  ``datasets.yaml`` declares required, and every key in
  ``assets.NULL_OPTIONAL`` names declared fields.
* **The engine constants D04 mirrors are still what the engine says.**  D04
  reads the battery, EV, charger and heat-pump parameters off named constants
  in this module because ``engine.run`` builds them inside a loop and retains
  nothing; the tests below assert against the engine's own source, the same way
  ``test_export_setpoint_constants_match_the_engine`` does for the setpoint.

The on-disk tests skip with a reason when no part is present and never pass
vacuously.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import pytest

import baile_nua
from baile_nua.export import assets, calibration_targets
from baile_nua.schema import load
from baile_nua.schema.validate import ValidationError, validate_frame

PROJECT_ROOT = Path(baile_nua.__file__).resolve().parents[2]
ENGINE_RUN = Path(baile_nua.__file__).resolve().parent / "engine" / "run.py"
DER = Path(baile_nua.__file__).resolve().parent / "devices" / "der.py"

#: The replay's per-year packages.  ``work/`` is not linked into an agent
#: worktree, so set ``BN_REPLAY_ROOT`` to the live tree to read them.
REPLAY_ROOT = Path(os.environ.get(
    "BN_REPLAY_ROOT", PROJECT_ROOT / "work" / "replay_2015_2026"))

#: Where a D04 part may be found.  The replay writes one per year; the estate
#: year and the 14-day town run write one when they are re-exported.
D04_SEARCH_ROOTS: tuple[Path, ...] = (
    PROJECT_ROOT / "v1" / "ground_truth",
    PROJECT_ROOT / "v1" / "ground_truth" / "town14",
    *sorted(REPLAY_ROOT.glob("*/pkg/ground_truth")),
)
D24_SEARCH_ROOTS: tuple[Path, ...] = (
    PROJECT_ROOT / "v1" / "evidence",
    *sorted(REPLAY_ROOT.glob("*/pkg/evidence")),
)


def _parts(roots, dataset_id: str) -> list[Path]:
    out: list[Path] = []
    for root in roots:
        out += sorted(Path(root).glob(f"{dataset_id}_part*.parquet"))
    return out


# --------------------------------------------------------------------------- #
# the declared-null mechanism
# --------------------------------------------------------------------------- #

def _d04_skeleton(n: int = 2) -> pd.DataFrame:
    """A minimal conformant D04 frame with every column present."""
    return pd.DataFrame([{
        "asset_id": f"A-{i:06d}-00", "version": 1,
        "valid_from": pd.Timestamp("2015-01-01", tz="UTC"), "valid_to": None,
        "building_id": f"B-{i:06d}", "owner_person_id": None,
        "asset_class": "appliance", "asset_type": "kettle",
        "make_model_synth": "m", "rated_power_w": None, "capacity": None,
        "efficiency": None, "install_date": pd.Timestamp("2010-01-01").date(),
        "age_years_at_t0": 5.0, "failure_hazard_scale": 1.0,
        "signature_id": None, "device_mode": "rendered",
        "pv_azimuth_deg": None, "pv_tilt_deg": None, "seed": 1,
    } for i in range(n)])


def test_a_null_in_a_required_column_is_refused_without_a_declaration():
    frame = _d04_skeleton()
    frame.loc[0, "make_model_synth"] = None
    with pytest.raises(ValidationError, match="required but 1 null"):
        validate_frame(frame, "D04")


def test_a_declared_null_in_a_required_column_passes():
    frame = _d04_skeleton()
    frame["make_model_synth"] = None
    validate_frame(frame, "D04", permit_null_required=["make_model_synth"])


def test_a_declared_null_does_not_excuse_a_missing_column():
    frame = _d04_skeleton().drop(columns=["make_model_synth"])
    with pytest.raises(ValidationError, match="missing required fields"):
        validate_frame(frame, "D04", permit_null_required=["make_model_synth"])


def test_a_declared_null_for_a_field_that_is_not_required_is_refused():
    # `signature_id` is declared optional, so exempting it claims something
    # about the schema that is not true.
    with pytest.raises(ValidationError, match="not declared\\s+required"):
        validate_frame(_d04_skeleton(), "D04",
                       permit_null_required=["signature_id"])


def test_a_declared_null_relaxes_nothing_else():
    frame = _d04_skeleton()
    frame["make_model_synth"] = None
    frame.loc[0, "device_mode"] = "not_an_enum_value"
    with pytest.raises(ValidationError, match="device_mode"):
        validate_frame(frame, "D04",
                       permit_null_required=["make_model_synth"])


def test_write_dataset_refuses_a_declared_null_with_no_reason(tmp_path):
    from baile_nua.io import write_dataset

    frame = _d04_skeleton()
    frame["make_model_synth"] = None
    with pytest.raises(ValidationError, match="with no reason"):
        write_dataset(frame, "D04", tmp_path / "ground_truth" / "x.parquet",
                      null_required={"make_model_synth": "   "})


def test_write_dataset_records_the_declaration_in_the_manifest(tmp_path):
    from baile_nua.io import write_dataset

    frame = _d04_skeleton()
    frame["make_model_synth"] = None
    path = write_dataset(
        frame, "D04", tmp_path / "ground_truth" / "D04_part000.parquet",
        null_required={"make_model_synth": "no per-asset model label exists"})
    meta = json.loads((path.parent / "D04_part000.manifest.json").read_text())
    assert meta["schema_conformance"].startswith("partial")
    assert meta["null_required_fields"] == {
        "make_model_synth": "no per-asset model label exists"}


def test_a_fully_conformant_part_says_so(tmp_path):
    from baile_nua.io import write_dataset

    path = write_dataset(
        _d04_skeleton(), "D04",
        tmp_path / "ground_truth" / "D04_part000.parquet")
    meta = json.loads((path.parent / "D04_part000.manifest.json").read_text())
    assert meta["schema_conformance"] == "full"
    assert "null_required_fields" not in meta


# --------------------------------------------------------------------------- #
# the exemption lists are true of the schema
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("dataset_id,module", [
    ("D04", assets), ("D24", calibration_targets),
])
def test_every_declared_null_names_a_required_field(dataset_id, module):
    required = set(load()[dataset_id].required_fields)
    named = set(module.NULL_REQUIRED)
    assert named and named <= required, sorted(named - required)


@pytest.mark.parametrize("dataset_id,module", [
    ("D04", assets), ("D24", calibration_targets),
])
def test_every_declared_null_carries_a_reason(dataset_id, module):
    for field, reason in module.NULL_REQUIRED.items():
        assert reason.strip(), field
        assert "NO SOURCE" in reason or "NULL for" in reason, field


def test_d04_null_optional_names_declared_fields():
    declared = set(load()["D04"].field_map)
    for key in assets.NULL_OPTIONAL:
        for name in (n.strip() for n in key.split(",")):
            assert name in declared, name


def test_d24_leaves_null_exactly_the_five_the_absent_reason_named():
    # The five the superseded reason listed, unchanged.
    assert set(calibration_targets.NULL_REQUIRED) == {
        "domain", "tolerance", "tolerance_kind", "evidence_tag", "provisional",
    }


def test_d04_and_d24_are_no_longer_recorded_as_absent():
    from baile_nua.export.absent import ABSENT, SUPERSEDED, SUPERSEDED_VERBATIM
    from baile_nua.export.dispatch import EXPORTERS

    for d in ("D04", "D24"):
        assert d not in ABSENT
        assert d in SUPERSEDED
        assert d in EXPORTERS
        # The objection is kept verbatim, not deleted.
        assert f'"{d}": {{' in SUPERSEDED_VERBATIM


# --------------------------------------------------------------------------- #
# the engine constants D04 mirrors
# --------------------------------------------------------------------------- #

def test_bess_constants_match_the_engine_source():
    src = ENGINE_RUN.read_text(encoding="utf-8")
    m = re.search(
        r"der_mod\.Battery\(\s*capacity_wh=([0-9_.]+),\s*"
        r"max_charge_w=([0-9_.]+),\s*max_discharge_w=([0-9_.]+)", src)
    assert m, "engine.run no longer builds der_mod.Battery(capacity_wh=...)"
    assert float(m.group(1).replace("_", "")) == assets.BESS_CAPACITY_WH
    assert float(m.group(2).replace("_", "")) == assets.BESS_MAX_CHARGE_W
    assert float(m.group(3).replace("_", "")) == assets.BESS_MAX_DISCHARGE_W


def test_ev_constants_match_the_engine_source():
    src = ENGINE_RUN.read_text(encoding="utf-8")
    m = re.search(
        r"der_mod\.ElectricVehicle\(\s*battery_wh=([0-9_.]+),\s*"
        r"charger_w=([0-9_.]+)", src)
    assert m, "engine.run no longer builds der_mod.ElectricVehicle(...)"
    assert float(m.group(1).replace("_", "")) == assets.EV_BATTERY_WH
    assert float(m.group(2).replace("_", "")) == assets.EV_CHARGER_W


def test_the_mirrored_defaults_are_still_the_dataclass_defaults():
    from baile_nua.devices.der import Battery, HeatPump

    assert (Battery(capacity_wh=1.0, max_charge_w=1.0, max_discharge_w=1.0)
            .round_trip_efficiency == assets.BESS_ROUND_TRIP_EFFICIENCY)
    assert HeatPump(rated_thermal_w=1.0).cop_at_7c == assets.HEAT_PUMP_COP_AT_7C


def test_the_engine_still_builds_the_heat_pump_on_the_dwellings_emitter():
    src = ENGINE_RUN.read_text(encoding="utf-8")
    assert "der_mod.HeatPump(rated_thermal_w=tp.heat_emitter_w)" in src
    # And still treats direct electric as COP 1, which is the only other
    # heating efficiency D04 fills.
    assert "direct electric: COP 1" in src


def test_the_appliance_rated_power_is_still_a_placeholder():
    """D04 leaves appliance ``rated_power_w`` null because the draw is 0.0."""
    e1 = (Path(baile_nua.__file__).resolve().parent / "engine" / "e1_run.py"
          ).read_text(encoding="utf-8")
    assert '"rated_power_w": 0.0,' in e1


def test_the_model_variation_is_still_drawn_per_cycle_not_per_asset():
    """The reason ``make_model_synth`` stays null."""
    sig = (Path(baile_nua.__file__).resolve().parent / "devices"
           / "signatures.py").read_text(encoding="utf-8")
    assert "one draw per cycle" in sig


def test_appliance_failure_is_still_a_fixed_outage_not_a_weibull():
    """The reason ``failure_hazard_scale`` stays null."""
    src = ENGINE_RUN.read_text(encoding="utf-8")
    assert "st.failed_appliances[d[\"appliance\"]] = day.sim_day + 7" in src
    assert "weibull" not in src.lower()


# --------------------------------------------------------------------------- #
# the parts, where they exist
# --------------------------------------------------------------------------- #

def test_every_d04_part_conforms_with_exactly_the_declared_nulls():
    paths = _parts(D04_SEARCH_ROOTS, "D04")
    if not paths:
        pytest.skip("no D04 part on disk under v1/ or work/replay_2015_2026/")
    for path in paths:
        frame = pq.read_table(path).to_pandas()
        validate_frame(frame, "D04",
                       permit_null_required=list(assets.NULL_REQUIRED))
        required = set(load()["D04"].required_fields)
        null_required = {c for c in required if frame[c].isna().any()}
        assert null_required <= set(assets.NULL_REQUIRED), (
            f"{path}: required columns {sorted(null_required - set(assets.NULL_REQUIRED))} "
            f"are null and NOT declared")
        meta = json.loads(
            (path.parent / f"{path.stem}.manifest.json").read_text())
        assert set(meta["null_required_fields"]) == set(assets.NULL_REQUIRED)


def test_every_d04_part_fills_what_it_claims_to_fill():
    paths = _parts(D04_SEARCH_ROOTS, "D04")
    if not paths:
        pytest.skip("no D04 part on disk")
    for path in paths:
        f = pq.read_table(path).to_pandas()
        appliance = f[f["asset_class"] == "appliance"]
        assert len(appliance), f"{path}: no appliance rows"
        # The two columns the appliance draw DOES carry are never null.
        assert appliance["age_years_at_t0"].notna().all()
        assert appliance["install_date"].notna().all()
        # And the ones only another class carries are never set on it.
        assert appliance["pv_azimuth_deg"].isna().all()
        pv = f[f["asset_class"] == "pv"]
        if len(pv):
            assert pv["capacity"].notna().all()
            assert pv["pv_azimuth_deg"].between(90.0, 270.0).all()
            assert pv["pv_tilt_deg"].between(12.0, 45.0).all()
        bess = f[f["asset_class"] == "bess"]
        if len(bess):
            assert (bess["capacity"] == assets.BESS_CAPACITY_WH).all()
            assert (bess["efficiency"] == assets.BESS_ROUND_TRIP_EFFICIENCY).all()
        assert set(f["asset_class"]) <= set(assets.ASSET_CLASSES)
        # One row per asset per version: the declared grain.
        assert not f.duplicated(["asset_id", "version"]).any()


def test_every_d24_part_conforms_with_exactly_the_declared_nulls():
    paths = _parts(D24_SEARCH_ROOTS, "D24")
    if not paths:
        pytest.skip("no D24 part on disk under v1/ or work/replay_2015_2026/")
    for path in paths:
        frame = pq.read_table(path).to_pandas()
        validate_frame(
            frame, "D24",
            permit_null_required=list(calibration_targets.NULL_REQUIRED))
        required = set(load()["D24"].required_fields)
        null_required = {c for c in required if frame[c].isna().any()}
        assert null_required <= set(calibration_targets.NULL_REQUIRED)
        # The eleven the field_mapping said were available are all present.
        for col in ("target_id", "statistic", "unit", "source_file",
                    "source_sha256", "source_url", "source_licence",
                    "retrieved_at", "intended_use",
                    "model_development_exposure", "value_json"):
            assert frame[col].notna().all(), f"{path}: {col} has nulls"
        assert not frame["target_id"].duplicated().any()
        # value_json is a JSON string and carries what the schema drops.
        payload = json.loads(frame["value_json"].iloc[0])
        assert "conditioned_on" in payload
        assert "scope_note" in payload["not_declared_by_the_schema"]


# --------------------------------------------------------------------------- #
# D24's target year, and the catch-up pass
# --------------------------------------------------------------------------- #

def test_the_d24_target_year_falls_back_and_records_the_substitution():
    """The sources behind D24 cover 2016-2023; the replay spans 2014-2026."""
    artefact, note = calibration_targets.targets_for_year(2020)
    assert note["substituted"] is False
    assert note["built_for_year"] == 2020
    assert artefact["n_targets"] > 0

    artefact, note = calibration_targets.targets_for_year(2015)
    assert note["substituted"] is True
    assert note["built_for_year"] == calibration_targets.FALLBACK_TARGET_YEAR
    # The substitution says what it cost, and names what refused.
    assert "2022 statistics" in note["note"]
    assert "TargetError" in note["build_d24_refused_because"]
    assert artefact["n_targets"] > 0


def test_which_replay_years_get_substituted_d24_targets():
    """Recorded as an assertion so it fires if the source coverage changes."""
    cfg = json.loads(
        (Path(baile_nua.__file__).resolve().parents[1]
         / "replay_config.json").read_text(encoding="utf-8"))
    years = [int(s["year"]) for s in cfg["segments"]
             if not s["discard_output"]]
    substituted = [y for y in years
                   if calibration_targets.targets_for_year(y)[1]["substituted"]]
    assert substituted == [2015, 2024, 2025, 2026], substituted


def test_the_catchup_pass_refuses_an_unfinished_segment(tmp_path):
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "export_catchup",
        Path(baile_nua.__file__).resolve().parents[1] / "export_catchup.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    pkg = tmp_path / "pkg"
    (pkg / "ground_truth").mkdir(parents=True)
    (pkg / "run_diagnostics.json").write_text('{"master_seed": 1}')
    # No DONE.json: the segment is either running or failed.
    with pytest.raises(SystemExit, match="still running"):
        mod.catchup(tmp_path, ["D24"])


def test_the_catchup_pass_moves_parts_aside_instead_of_deleting(tmp_path):
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "export_catchup",
        Path(baile_nua.__file__).resolve().parents[1] / "export_catchup.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    pkg = tmp_path / "pkg"
    (pkg / "evidence").mkdir(parents=True)
    part = pkg / "evidence" / "D24_part000.parquet"
    part.write_bytes(b"not really parquet")
    (pkg / "evidence" / "D24_part000.manifest.json").write_text("{}")

    moved = mod.move_aside(pkg, ["D24"], "stamp")
    assert len(moved) == 2
    assert not part.exists()
    kept = tmp_path / "superseded" / "stamp" / "evidence" / "D24_part000.parquet"
    assert kept.read_bytes() == b"not really parquet"
