"""I-117: the per-epoch network dicts are reduced to what is actually read.

`e1_run` solved 96 power flows a day and kept every result dict for the whole
segment, to compute five aggregates and a length at the end. 83% of each dict
was `feeder_head_loading_pct` (one entry per feeder) and `trafo_loading_pct`
(one per substation), and `lv.loading_report` reads neither.

Measured: 10,809 B full against 832 B reduced, so 0.35 GB a year and 4.15 GB
over the 4,291-day replay — and because every segment runs in the SAME process,
`ru_maxrss` never resets at a year boundary and the cost accumulates across all
twelve years. That is the step-wise growth that took the gate to 88%.

The test that matters is the first one: the report must be IDENTICAL. A memory
saving that changes a reported number is not a saving, it is a defect.
"""
from __future__ import annotations

import inspect

import numpy as np

import baile_nua.sources_registry  # noqa: F401  - e1_run reads sources at import
from baile_nua.engine import e1_run
from baile_nua.network import lv

N_FEEDERS, N_SUBS = 64, 53


def _full(sim_day: int, epoch: int, converged: bool = True) -> dict:
    rng = np.random.default_rng(sim_day * 1000 + epoch)
    return {
        "converged": converged,
        "reading": "ok",
        "why": None,
        "feeder_head_loading_pct": {
            f"FDR-{i:04d}": float(rng.uniform(5, 95)) for i in range(N_FEEDERS)},
        "trafo_loading_pct": {
            f"SUB-{i:04d}": float(rng.uniform(5, 95)) for i in range(N_SUBS)},
        "max_feeder_loading_pct": float(rng.uniform(10, 99)),
        "max_line_loading_pct": float(rng.uniform(10, 99)),
        "max_trafo_loading_pct": float(rng.uniform(10, 99)),
        "vm_pu_min": float(rng.uniform(0.90, 1.0)),
        "vm_pu_max": float(rng.uniform(1.0, 1.1)),
        "n_buses_outside_en50160": 0,
        "n_connections_at_zero": 3,
        "n_connections_loaded": 1092,
        "power_factor": 0.97,
        "total_load_kw": float(rng.uniform(100, 2000)),
        "voltage_is_not_a_claim": True,
        "sim_day": sim_day,
        "epoch": epoch,
    }


def _reduce(r: dict) -> dict:
    """The reduction e1_run applies, mirrored so the report can be compared."""
    if not r.get("converged"):
        return r
    return {
        "converged": True,
        "max_trafo_loading_pct": r["max_trafo_loading_pct"],
        "max_feeder_loading_pct": r["max_feeder_loading_pct"],
        "max_line_loading_pct": r["max_line_loading_pct"],
        "vm_pu_min": r["vm_pu_min"],
        "sim_day": r["sim_day"],
        "epoch": r["epoch"],
    }


def test_the_loading_report_is_identical_after_the_reduction():
    """The whole point. Same numbers, 8% of the memory."""
    full = [_full(d, e) for d in range(3) for e in range(96)]
    full[17]["converged"] = False          # a non-convergence must still count
    full[200]["converged"] = False
    reduced = [_reduce(r) for r in full]
    assert lv.loading_report(full) == lv.loading_report(reduced)


def test_a_non_converged_epoch_keeps_its_full_dict():
    """Those are the only ones worth diagnosing, and they are rare."""
    bad = _full(1, 1, converged=False)
    assert _reduce(bad) is bad
    assert "feeder_head_loading_pct" in _reduce(bad)


def test_a_converged_epoch_drops_the_two_unread_dicts():
    kept = _reduce(_full(1, 1))
    assert "feeder_head_loading_pct" not in kept
    assert "trafo_loading_pct" not in kept
    assert kept["sim_day"] == 1 and kept["epoch"] == 1


def test_the_reduction_keeps_every_field_loading_report_reads():
    """Derived from the source, so adding a field there fails here first."""
    src = inspect.getsource(lv.loading_report)
    read = set(__import__("re").findall(r'r\["([a-z_0-9]+)"\]', src))
    read |= set(__import__("re").findall(r'r\.get\("([a-z_0-9]+)"\)', src))
    kept = set(_reduce(_full(1, 1)))
    missing = read - kept
    assert not missing, f"loading_report reads {missing}, which the reduction drops"


def test_e1_run_actually_applies_the_reduction():
    """Asserted on the source: nothing else would notice if it stopped."""
    src = inspect.getsource(e1_run)
    i = src.index("network_epochs.append(")
    window = src[i:i + 400]
    assert "if not r.get(\"converged\")" in window, (
        "the append must reduce converged epochs (I-117)")
    assert "max_trafo_loading_pct" in window


def test_the_saving_is_real_and_large():
    """If the shapes change this records what the claim was based on."""
    import sys

    def deep(o, seen=None):
        seen = seen if seen is not None else set()
        if id(o) in seen:
            return 0
        seen.add(id(o))
        n = sys.getsizeof(o)
        if isinstance(o, dict):
            n += sum(deep(k, seen) + deep(v, seen) for k, v in o.items())
        return n

    full, red = deep(_full(1, 1)), deep(_reduce(_full(1, 1)))
    assert red < full * 0.15, f"reduced {red} B is not much smaller than {full} B"
