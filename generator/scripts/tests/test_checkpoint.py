"""Checkpoint suite: hash-chained daily state and the exchange log (design 8.2)."""

from __future__ import annotations

import gzip
import json

import pytest

from baile_nua.checkpoint import ChainError, Checkpoint, CheckpointStore, ExchangeLog

pytestmark = pytest.mark.determinism


def _build(store: CheckpointStore, n_days: int = 5) -> str:
    prev = None
    for d in range(n_days):
        xl = ExchangeLog(
            sim_day=d,
            date_iso=f"2022-01-{d + 1:02d}",
            calendar_events=[{"kind": "school term", "phase": "main"}],
            venue_assignments={"P-000001": "V-0001"},
        ).freeze()
        cp = Checkpoint(
            sim_day=d, date_iso=f"2022-01-{d + 1:02d}", run_id="E1-test",
            master_seed=20261008,
            person_state={"P-000001": {"health_state": "well", "household_id": "H-0001"}},
            building_state={"B-0001": {"temp_living_c": 19.5 + d * 0.1}},
            previous_hash=prev,
        )
        prev = store.put(cp, xl)
    return prev


def test_chain_verifies_after_a_clean_run(tmp_path):
    store = CheckpointStore(tmp_path)
    head = _build(store)
    store.verify_chain()
    assert store.head() == head
    assert store.days() == [0, 1, 2, 3, 4]


def test_checkpoint_round_trips(tmp_path):
    store = CheckpointStore(tmp_path)
    _build(store, 2)
    cp = store.get(1)
    assert cp.sim_day == 1
    assert cp.person_state["P-000001"]["health_state"] == "well"
    assert cp.exchange_log_hash is not None


def test_exchange_log_is_frozen_after_phase_a(tmp_path):
    """Design 8.2: Phase B may read the exchange log but never write it.

    Enforced structurally, because "nothing crosses households except through
    the exchange log" is only true if the log cannot be mutated mid-day.
    """
    store = CheckpointStore(tmp_path)
    _build(store, 1)
    xl = store.get_exchange_log(0)
    with pytest.raises(RuntimeError, match="frozen"):
        xl.venue_assignments = {}
    with pytest.raises(RuntimeError, match="frozen"):
        xl.disruptions = {"H-0001": [{"kind": "illness"}]}


def test_editing_history_invalidates_the_chain(tmp_path):
    """Design 8.2: "Changing history invalidates every downstream checkpoint in
    the hash chain." Detectable, not merely discouraged."""
    store = CheckpointStore(tmp_path)
    _build(store, 5)
    store.verify_chain()

    target = tmp_path / "day_00002.checkpoint.json.gz"
    rec = json.loads(gzip.open(target, "rb").read())
    rec["payload"]["person_state"]["P-000001"]["health_state"] = "short illness"
    with gzip.GzipFile(filename="", mode="wb", fileobj=open(target, "wb"), mtime=0) as gz:
        gz.write(json.dumps(rec, sort_keys=True, separators=(",", ":")).encode())

    with pytest.raises(ChainError, match="day 2"):
        store.verify_chain()


def test_tampering_with_an_exchange_log_is_detected(tmp_path):
    store = CheckpointStore(tmp_path)
    _build(store, 3)
    target = tmp_path / "day_00001.exchange.json.gz"
    rec = json.loads(gzip.open(target, "rb").read())
    rec["venue_assignments"]["P-000001"] = "V-9999"
    with gzip.GzipFile(filename="", mode="wb", fileobj=open(target, "wb"), mtime=0) as gz:
        gz.write(json.dumps(rec, sort_keys=True, separators=(",", ":")).encode())
    with pytest.raises(ChainError, match="exchange log hash"):
        store.verify_chain()


def test_invalidated_from_lists_downstream_days(tmp_path):
    store = CheckpointStore(tmp_path)
    _build(store, 6)
    assert store.invalidated_from(3) == [3, 4, 5]


def test_checkpoint_files_are_byte_identical_across_runs(tmp_path):
    """Design 7.2: byte-identical. gzip's mtime field is zeroed for this reason."""
    a, b = CheckpointStore(tmp_path / "a"), CheckpointStore(tmp_path / "b")
    _build(a, 3)
    _build(b, 3)
    for d in (0, 1, 2):
        assert (a.root / f"day_{d:05d}.checkpoint.json.gz").read_bytes() == (
            b.root / f"day_{d:05d}.checkpoint.json.gz"
        ).read_bytes()


def test_mismatched_exchange_log_day_is_refused(tmp_path):
    store = CheckpointStore(tmp_path)
    cp = Checkpoint(sim_day=0, date_iso="2022-01-01", run_id="r", master_seed=1)
    xl = ExchangeLog(sim_day=1, date_iso="2022-01-02").freeze()
    with pytest.raises(ValueError, match="day 1 but checkpoint is day 0"):
        store.put(cp, xl)


# --------------------------------------------------------------------------- #
# I-081: what the checkpoint WRITES and what the restore READS must agree
# --------------------------------------------------------------------------- #

def test_every_key_the_checkpoint_writes_is_read_back_by_restore():
    """The structural half of I-081, which a measurement alone would not fix.

    ``HouseholdState.as_dict`` and ``EstateRunner.restore`` are two lists of
    the same state written in two places, and they drifted: U25 added the hot
    water cylinder to ``as_dict`` and not to ``restore``, so the cylinder was
    recorded faithfully in every checkpoint and thrown away on every replay.
    Each replayed day therefore began with the tank at its construction
    temperature and diverged on the morning reheat - 70 of 100 sampled
    home-days, worst absolute difference 3,144 W.

    What let it survive is that nothing compared the two lists. The replay
    test would have caught it, but the replay artefact had been measured
    eleven hours before the tank existed and was quoted unchanged afterwards,
    so the gap sat behind a PASS for two days.

    So this reads the source of both and asserts the correspondence directly.
    It is a weaker check than the replay - it cannot tell whether a restored
    value is USED correctly - but it fires on the next field added to one list
    and not the other, which is the failure that actually happened, and it
    costs milliseconds rather than the replay's twenty minutes.
    """
    import ast
    import inspect
    from pathlib import Path

    import baile_nua.sources_registry  # noqa: F401  (declares the sources)
    from baile_nua.engine import run as run_mod

    src = Path(inspect.getfile(run_mod)).read_text(encoding="utf-8")
    tree = ast.parse(src)

    def find(node_name: str, cls_name: str | None = None):
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and cls_name and node.name == cls_name:
                for sub in node.body:
                    if isinstance(sub, ast.FunctionDef) and sub.name == node_name:
                        return sub
            elif (isinstance(node, ast.FunctionDef) and node.name == node_name
                  and cls_name is None):
                return node
        raise AssertionError(f"{cls_name}.{node_name} not found in run.py")

    as_dict = find("as_dict", "HouseholdState")
    restore = find("restore", "EstateRunner")

    # The keys the checkpoint records for one household.
    written = set()
    for node in ast.walk(as_dict):
        if isinstance(node, ast.Dict):
            for k in node.keys:
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    written.add(k.value)

    # Every string literal used as a subscript or a .get() argument inside
    # restore. Deliberately generous about HOW the key is read, because the
    # point is whether it is read at all.
    read = set()
    for node in ast.walk(restore):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            read.add(node.value)

    # `household_id` and `building_id` identify the household rather than
    # carrying state: restore looks the household up by its key and would
    # refuse a checkpoint whose ids disagreed, so they are not restored INTO
    # anything and their absence from `restore` is correct.
    identifiers = {"household_id", "building_id"}
    missing = sorted(written - read - identifiers)
    assert not missing, (
        f"the checkpoint records {missing} for every household and "
        f"EstateRunner.restore never reads them back, so a replayed day "
        f"starts from the wrong state in exactly those quantities. That is "
        f"I-081, which cost 70 of 100 sampled home-days. Add the restore, or "
        f"stop writing the key."
    )


def test_the_harness_builds_the_runner_the_same_way_as_the_run():
    """I-084: a harness that constructs the model differently measures nothing.

    ``run_year`` passed ``income_quintile=sl.income_quintile`` and both bench
    harnesses did not, so every household's comfort shift was computed without
    its income quintile and the replay compared that model against data
    produced by this one. It read as a state gap - 41 of 100 sampled home-days,
    divergence starting the moment morning heating first mattered and growing
    to 0.67 C - and no amount of looking at the checkpoint would have found it,
    because the checkpoint was right.

    Two things hid it. The replay's own report named a missing restore, which
    is where a reader looks. And the determinism arm compared three runs
    against EACH OTHER: all three built the runner the same wrong way, agreed
    byte for byte, and said nothing about whether any of them matched the
    delivered year.

    So construction lives in one factory and this asserts there is no second
    way to do it. Checked against the source rather than by calling anything,
    because the failure is a call site that exists, not a behaviour.
    """
    import ast
    import inspect
    from pathlib import Path

    import baile_nua.sources_registry  # noqa: F401  (declares the sources)
    from baile_nua import bench, engine

    allowed = {"baile_nua/engine/e1_run.py"}
    offenders: list[str] = []
    for pkg in (engine, bench):
        root = Path(inspect.getfile(pkg)).parent
        for path in sorted(root.rglob("*.py")):
            rel = path.relative_to(root.parents[1]).as_posix()
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Name)
                        and node.func.id == "EstateRunner"
                        and rel not in allowed):
                    offenders.append(f"{rel}:{node.lineno}")
    assert not offenders, (
        f"these construct an EstateRunner directly instead of calling "
        f"e1_run.build_runner: {offenders}. Every argument the delivered run "
        f"passes has to be passed here too, and the last time one was missed "
        f"it cost a two-hour diagnosis of a reproducibility failure that did "
        f"not exist (I-084). Add the argument to build_runner, not to the "
        f"call site."
    )
