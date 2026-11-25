"""D23 must name the engine the year was run on, not a module constant.

The twelve-year replay is not one engine: 2015 ran on freeze-2.2, later years
on whatever the supervisor was restarted with, and the D18 era gating switches
on at the 2019 boundary. `export.run_manifest.FREEZE_TAG` is a constant, so
before this a D23 row asserted, for eleven of the twelve years, a version they
were not run on.

The fallback is tested as carefully as the happy path: a version that was
inferred must never be reported as one that was recorded.
"""
from __future__ import annotations

import json

from baile_nua.export.run_manifest import (
    ENGINE_SIDECAR,
    FREEZE_TAG,
    engine_identity,
)

SIDE = {
    "segment": "2019",
    "engine_tag": "v1-engine-freeze-2.3",
    "code_digest": "a" * 64,
    "conf_digest": "b" * 64,
    "d18_era_gating": True,
}


def test_reads_the_sidecar_beside_the_package(tmp_path):
    (tmp_path / ENGINE_SIDECAR).write_text(json.dumps(SIDE))
    got = engine_identity(tmp_path)
    assert got["engine_tag"] == "v1-engine-freeze-2.3"
    assert got["code_digest"] == "a" * 64
    assert got["d18_era_gating"] is True
    assert "recorded by the run" in got["source"]


def test_reads_the_sidecar_one_level_up(tmp_path):
    """`export_all` is handed the package dir; the supervisor writes the
    sidecar at the segment root, one level above it."""
    (tmp_path / ENGINE_SIDECAR).write_text(json.dumps(SIDE))
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    assert engine_identity(pkg)["engine_tag"] == "v1-engine-freeze-2.3"


def test_fallback_says_it_is_a_fallback(tmp_path):
    got = engine_identity(tmp_path)
    assert got["engine_tag"] == FREEZE_TAG
    assert got["code_digest"] is None
    assert "fallback" in got["source"]
    assert "not a statement about this run" in got["source"]


def test_unreadable_sidecar_falls_back_rather_than_raising(tmp_path):
    """A truncated sidecar must not take a ten-hour year's export down."""
    (tmp_path / ENGINE_SIDECAR).write_text("{not json")
    got = engine_identity(tmp_path)
    assert got["engine_tag"] == FREEZE_TAG
    assert "fallback" in got["source"]


def test_two_segments_can_report_different_engines(tmp_path):
    """The whole point: 2018 and 2019 must not report the same version."""
    a, b = tmp_path / "2018", tmp_path / "2019"
    for d, tag, gate in ((a, "v1-engine-freeze-2.2", False),
                         (b, "v1-engine-freeze-2.3", True)):
        d.mkdir()
        (d / ENGINE_SIDECAR).write_text(
            json.dumps({**SIDE, "engine_tag": tag, "d18_era_gating": gate}))
    assert engine_identity(a)["engine_tag"] != engine_identity(b)["engine_tag"]
    assert engine_identity(a)["d18_era_gating"] is False
    assert engine_identity(b)["d18_era_gating"] is True


def test_the_supervisor_writes_the_sidecar_before_the_export():
    """Ordering is the whole reason the sidecar exists rather than DONE.json.

    If an edit ever moves the write after `export_all`, D23 silently reverts to
    the constant and nothing else fails - so the order is asserted on the
    source itself.
    """
    import pathlib

    src = (pathlib.Path(__file__).resolve().parents[1]
           / "replay_supervisor.py").read_text()
    i_side = src.index('ENGINE.json')
    i_exp = src.index('from baile_nua.export import export_all')
    i_done = src.index('"DONE.json").write_text')
    assert i_side < i_exp, "the sidecar must be written BEFORE export_all"
    assert i_side < i_done, "and before the DONE sentinel"
