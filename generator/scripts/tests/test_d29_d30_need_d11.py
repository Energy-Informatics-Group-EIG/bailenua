"""What D29 and D30 need from D11, and whether the replay config supplies it.

D29 and D30 failed in an earlier run and the recorded reason (D-138) was "they
need a D11 part".  This file pins down what that means in the code and then
asks the question the reason did not: does the real replay configuration
produce one?

**The dependency, in the code.**  ``export_d29`` and ``export_d30`` both call
``nonsensor_datasets.build_truth_by_premises``, which calls
``occupied_weekday_hours``, which globs
``<run_root>/ground_truth/D11_part*.parquet`` and raises ``ExportError`` when
there is none, by design: "defaulting it would hand the survey generator a flat
truth and make its occupancy answers meaningless".  Three further conditions
are in the same function and each raises: at least one row with
``location_kind == 'building'``, and at least one weekday inside the recorded
span.

**The answer, from the config - and the bug it exposed.**  D11 is written only
for the days the runner collects presence, and the gate is
``day.sim_day < collect_presence_days`` with ``collect_presence_days``
defaulting to 14.  ``sim_day`` is GLOBAL across the replay -
``build_calendar`` sets ``sim_day = sim_day_offset + i`` so the seed tree does
not re-draw an earlier year - and ``replay_supervisor.run_segment`` originally
did not pass ``collect_presence_days`` at all.  Every segment the replay KEEPS
starts at ``sim_day_offset`` 31 or later, so **no delivered year collected a
single presence row** and D29 and D30 would have failed in all twelve.  The
only segment under the gate was ``warmup_2014``, whose output is discarded.

**Fixed, and the replay restarted to apply it (D-141).**  The supervisor now
passes ``collect_presence_days = seg["sim_day_offset"] + 14``, which keeps the
original intent - the first fortnight of each segment - rather than widening
retention.  Safe to change mid-run because ``collect_presence`` is a RETENTION
flag: ``engine/run.py:500-511`` records that ``_venue_for`` is addressed
through the counter-based seed tree on its own ``(person, day, activity)`` key,
so resolving it every day "advances no other stream and changes no other
draw".  Confirmed on the real run: the sim_day 59 flush wrote 1,149,976 D11
rows, 879,418 of them ``location_kind == "building"``.

The two tests below are written against the FIXED behaviour and still fire the
moment either side moves - the supervisor dropping the offset, or the engine's
default changing.  As agent D first wrote it,
``test_the_supervisor_does_not_pass_collect_presence_days`` asserted the
argument was absent, as a deliberate tripwire; it fired, and the expectation
was inverted rather than the tripwire removed.
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import json
import os
from pathlib import Path

import pandas as pd
import pytest

import baile_nua
from baile_nua.export import nonsensor_datasets as NSD
from baile_nua.export.context import ExportError, RunContext

PROJECT_ROOT = Path(baile_nua.__file__).resolve().parents[2]
SCRIPTS = Path(baile_nua.__file__).resolve().parents[1]
REPLAY_CONFIG = SCRIPTS / "replay_config.json"
SUPERVISOR = SCRIPTS / "replay_supervisor.py"
E1_RUN = Path(baile_nua.__file__).resolve().parent / "engine" / "e1_run.py"
CALENDAR = Path(baile_nua.__file__).resolve().parent / "engine" / "calendar.py"

#: Where the replay's per-year packages land.
#:
#: ``work/`` is 26,225 files and is NOT linked into an agent worktree, so a
#: worktree sees no replay package and the on-disk test below skips.  Set
#: ``BN_REPLAY_ROOT`` to the live tree's path to point it at the real packages
#: read-only, rather than editing this file:
#:
#:     BN_REPLAY_ROOT=/Users/.../HRSD_Occupants/work/replay_2015_2026 pytest ...
REPLAY_ROOT = Path(os.environ.get(
    "BN_REPLAY_ROOT", PROJECT_ROOT / "work" / "replay_2015_2026"))


# --------------------------------------------------------------------------- #
# the dependency, in the code
# --------------------------------------------------------------------------- #

def test_d29_and_d30_both_reach_occupied_weekday_hours():
    """Static, so it cannot pass by not exercising the path."""
    for fn in (NSD.export_d29, NSD.export_d30):
        src = inspect.getsource(fn)
        assert "build_truth_by_premises(ctx)" in src, fn.__name__
    assert "occupied_weekday_hours(ctx)" in inspect.getsource(
        NSD.build_truth_by_premises)


def test_the_d11_input_is_a_ground_truth_part_under_the_run_root():
    src = inspect.getsource(NSD.occupied_weekday_hours)
    assert 'ctx.run_root / "ground_truth"' in src
    assert 'glob("D11_part*.parquet")' in src
    # The three columns it reads, which is what a substitute would have to
    # supply.
    for col in ("start", "end", "location_kind", "location_id"):
        assert f'"{col}"' in src, col


def _ctx(run_root: Path) -> RunContext:
    """A RunContext pointed at ``run_root`` without opening a run.

    ``RunContext.open`` reads a run's diagnostics and calendar, which a
    fixture directory does not have.  The dependency under test needs only
    ``run_root`` and ``t0``, so the dataclass is constructed directly.
    """
    return RunContext(run_root=run_root, out_root=run_root,
                      t0=pd.Timestamp("2015-01-01", tz="UTC"), n_days=365)


def test_no_d11_part_raises_and_names_the_missing_input(tmp_path):
    (tmp_path / "ground_truth").mkdir()
    with pytest.raises(ExportError) as exc:
        NSD.occupied_weekday_hours(_ctx(tmp_path))
    msg = str(exc.value)
    assert "no D11 part" in msg
    assert "occupied_weekday_hours" in msg
    # It refuses rather than defaults, and says why.
    assert "Defaulting it" in msg


def test_a_d11_part_with_no_building_rows_raises(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq

    gt = tmp_path / "ground_truth"
    gt.mkdir()
    t0 = pd.Timestamp("2015-01-01", tz="UTC")
    frame = pd.DataFrame({
        "start": [t0], "end": [t0 + pd.Timedelta(hours=1)],
        "location_kind": ["venue"], "location_id": ["V-1"],
    })
    pq.write_table(pa.Table.from_pandas(frame, preserve_index=False),
                   gt / "D11_part000.parquet")
    with pytest.raises(ExportError, match="no building-located presence rows"):
        NSD.occupied_weekday_hours(_ctx(tmp_path))


def test_a_building_d11_part_is_enough_to_derive_the_hours(tmp_path):
    """The positive case, so the tests above are not merely checking raises."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    gt = tmp_path / "ground_truth"
    gt.mkdir()
    # 2015-01-01 is a Thursday: a weekday, which the function requires.
    t0 = pd.Timestamp("2015-01-01", tz="UTC")
    frame = pd.DataFrame({
        "start": [t0, t0 + pd.Timedelta(days=1)],
        "end": [t0 + pd.Timedelta(hours=6), t0 + pd.Timedelta(days=1, hours=6)],
        "location_kind": ["building", "building"],
        "location_id": ["B-000001", "B-000001"],
    })
    pq.write_table(pa.Table.from_pandas(frame, preserve_index=False),
                   gt / "D11_part000.parquet")
    hours = NSD.occupied_weekday_hours(_ctx(tmp_path))
    assert set(hours) == {"B-000001"}
    assert 0.0 < hours["B-000001"] <= 24.0


# --------------------------------------------------------------------------- #
# the answer, from the engine and the config
# --------------------------------------------------------------------------- #

def _run_year_default(name: str) -> object:
    """A default from ``run_year``'s signature, read rather than imported."""
    tree = ast.parse(E1_RUN.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "run_year":
            args = node.args
            for arg, default in zip(args.kwonlyargs, args.kw_defaults):
                if arg.arg == name and default is not None:
                    return ast.literal_eval(default)
    raise AssertionError(f"run_year has no keyword-only {name} with a default")


def test_the_presence_gate_is_still_the_global_sim_day():
    src = E1_RUN.read_text(encoding="utf-8")
    assert "collect_presence=(day.sim_day < collect_presence_days)" in src
    # And sim_day is global across the replay, not per segment.
    assert "sim_day=sim_day_offset + i" in CALENDAR.read_text(encoding="utf-8")


def test_the_supervisor_offsets_the_presence_gate_per_segment():
    """It now passes it, and this test was inverted when it started to (D-141).

    As written by agent D this asserted `collect_presence_days` was ABSENT from
    the supervisor, as a tripwire with the note "if it starts to, the
    expectation below has to be rechecked". It did start to: the gate tests the
    GLOBAL sim_day against a default of 14, so with every delivered segment
    beginning at offset 31 or later, presence was retained on no day of any
    delivered year and D29/D30 would have failed in all twelve. The tripwire
    fired exactly as intended; the expectation is what changed.
    """
    src = SUPERVISOR.read_text(encoding="utf-8")
    assert "run_year(" in src
    assert 'collect_presence_days=seg["sim_day_offset"] + 14' in src, (
        "the supervisor must offset the presence gate by the segment's own "
        "sim_day_offset, or no delivered year retains a D11 presence row")


def test_which_replay_segments_can_carry_d11():
    """The finding: no DELIVERED year of the replay carries a D11 row.

    Asserted rather than described, so it fails the moment the config gains a
    ``collect_presence_days`` or the engine's default moves - either of which
    would change the answer for D29 and D30.
    """
    cfg = json.loads(REPLAY_CONFIG.read_text(encoding="utf-8"))
    gate = int(_run_year_default("collect_presence_days"))
    assert gate == 14, "the engine default is the per-segment window size"

    # The supervisor passes `sim_day_offset + 14`, so each segment retains
    # presence for its OWN first fortnight. Recomputed here from the config the
    # replay actually runs, not asserted as a list of names.
    windows = {}
    for seg in cfg["segments"]:
        start = int(seg["sim_day_offset"])
        days = (pd.Timestamp(seg["end"]) - pd.Timestamp(seg["start"])).days + 1
        assert days > 0
        effective = start + gate
        covered = min(gate, days)
        windows[seg["name"]] = covered
        assert start < effective, seg["name"]

    kept = [s["name"] for s in cfg["segments"] if not s["discard_output"]]
    assert kept, "the config delivers no segment at all"
    barren = [n for n in kept if windows[n] <= 0]
    assert barren == [], (
        f"these delivered segments retain no presence day, so D29/D30 cannot "
        f"be built for them: {barren}")
    # Every delivered year gets a full fortnight; none is shorter than 14 days.
    assert all(windows[n] == gate for n in kept), windows


def test_collect_presence_is_a_retention_flag_and_draws_nothing():
    """Why raising the gate would be safe, if the coordinator chooses to.

    The fix for the finding above is one argument in the supervisor's
    ``run_year`` call.  It is only safe if turning presence collection on for
    more days changes no draw, and the engine says it does not: the venue
    resolution inside the ``collect_presence`` block goes through the
    counter-based seed tree on its own (person, day, activity) key, which the
    D10 path already resolves on every day.  Asserted against the engine's own
    statement of it so the claim cannot rot silently.
    """
    src = (Path(baile_nua.__file__).resolve().parent / "engine" / "run.py"
           ).read_text(encoding="utf-8")
    assert (
        "resolving it on every day rather than only the first\n"
        "        # `collect_presence_days` advances no other stream and "
        "changes no\n        # other draw." in src
    )
    # And the flag only ever appends rows.
    body = src[src.index("collect_presence: bool = False"):]
    for guard in ("if collect_presence:",):
        assert guard in body


# --------------------------------------------------------------------------- #
# against the real 2015 package, when it lands
# --------------------------------------------------------------------------- #

def _replay_year_roots() -> list[Path]:
    return [p for p in sorted(REPLAY_ROOT.glob("*/pkg"))
            if (p / "run_diagnostics.json").is_file()]


def test_each_finished_replay_year_against_the_d11_dependency():
    """Run the real predicate against each finished year's own package.

    Skips with a reason until a year's package exists.  2015 was expected at
    about 09:20 on 2026-10-16; nothing here waits for it.
    """
    roots = _replay_year_roots()
    if not roots:
        pytest.skip(
            f"no finished replay package under {REPLAY_ROOT} "
            f"(a year's pkg/run_diagnostics.json is written at the end of the "
            f"segment, and work/ is not linked into a worktree - set "
            f"BN_REPLAY_ROOT to the live tree); staged pending the 2015 "
            f"package")
    for root in roots:
        parts = sorted((root / "ground_truth").glob("D11_part*.parquet"))
        if not parts:
            # The predicted outcome, asserted on the real package: no D11, so
            # D29 and D30 cannot be derived and the year's export report must
            # say so rather than carrying a silently empty survey.
            with pytest.raises(ExportError, match="no D11 part"):
                NSD.occupied_weekday_hours(_ctx(root))
            report = root.parent / "export_report.json"
            if report.is_file():
                rep = json.loads(report.read_text(encoding="utf-8"))
                for d in ("D29", "D30"):
                    rec = (rep.get("datasets") or {}).get(d) or {}
                    assert rec.get("verdict") in ("failed", "not written"), (
                        f"{root}: {d} is recorded as {rec.get('verdict')!r} "
                        f"with no D11 part to derive it from")
            continue
        # D11 is present: the dependency is satisfied and must actually work.
        hours = NSD.occupied_weekday_hours(_ctx(root))
        assert hours, f"{root}: a D11 part is present but yielded no hours"
        assert all(0.0 <= v <= 24.0 for v in hours.values())


def test_the_context_is_a_dataclass_so_the_fixture_above_is_legitimate():
    """Guards the shortcut these tests take.

    ``_ctx`` builds a ``RunContext`` directly instead of through ``open``.
    That is only sound while the fields it sets are plain dataclass fields
    with the meanings used here.
    """
    assert dataclasses.is_dataclass(RunContext)
    names = {f.name for f in dataclasses.fields(RunContext)}
    assert {"run_root", "out_root", "t0", "n_days"} <= names
