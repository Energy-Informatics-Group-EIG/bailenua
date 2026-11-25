"""The memory gate must act on current RSS, not on a high-water mark (I-116).

`resource.getrusage().ru_maxrss` only ever rises. Gating on it means one
historical spike aborts the segment and every retry of it for the rest of the
run, while the process sits at a fraction of the budget — measured on the real
run: peak 11,938 MB against a current RSS of 0.47 GB. The peak is still
recorded, because it is the only evidence of what the run demanded and I-113
depends on it to catch a spike between two 30-day checks.
"""
from __future__ import annotations

import pathlib
import sys

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import replay_supervisor as rs  # noqa: E402

SRC = (SCRIPTS / "replay_supervisor.py").read_text(encoding="utf-8")


def test_the_helper_reports_a_real_current_rss():
    """If this returned 0 the gate would be silently disabled."""
    mb = rs._current_rss_mb()
    assert mb > 1.0, f"implausible current RSS {mb}"
    assert mb < 200_000.0


def test_the_gate_compares_current_rss_not_the_peak():
    """Asserted on the source: the comparison is the whole point.

    A behavioural test would need a process that really exceeds 18 GB, so the
    structure is pinned instead - and structure is what regressed here.
    """
    i_gate = SRC.index('> cfg["rss_gate_mb"]')
    window = SRC[i_gate - 400:i_gate]
    assert 'state["rss_mb"]' in window, (
        "the gate must test current RSS; testing ru_maxrss makes it a one-shot "
        "time bomb (I-116)")
    # And the thing it must NOT be compared against.
    assert "ru_maxrss" not in SRC[i_gate - 120:i_gate + 40], (
        "ru_maxrss appears adjacent to the gate comparison again")


def test_the_peak_is_still_recorded():
    """Dropping the peak would lose the evidence I-113 relies on."""
    assert "ru_maxrss" in SRC, "the peak must still be measured"
    assert 'state["peak_rss_mb"]' in SRC
    assert 'state["rss_mb"]' in SRC


def test_a_failing_ps_cannot_trip_the_gate(monkeypatch):
    """Losing the gate for one cycle is recoverable; aborting a ten-hour
    segment because `ps` hiccuped is not."""
    def boom(*a, **k):
        raise OSError("no ps")

    monkeypatch.setattr(rs.subprocess, "run", boom)
    assert rs._current_rss_mb() == 0.0


def test_the_gate_figure_is_the_configured_budget():
    import json

    cfg = json.loads((SCRIPTS / "replay_config.json").read_text())
    assert int(cfg["rss_gate_mb"]) == 18432, "the brief's 18 GB gate"
