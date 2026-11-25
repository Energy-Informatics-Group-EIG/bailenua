"""Tests for the U27 plausibility suite.

U27's last sentence is "unit tests alone never pass a gate", so these tests
are about the suite's *contract* rather than about the model: that an unsourced
check is never counted as a sourced pass, that a partial-year run is refused
rather than failed, and that every check names its source and tolerance.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

import baile_nua.sources_registry  # noqa: F401  (declares the sources)
from baile_nua.plausibility import CHECKS, run_suite
from baile_nua.plausibility.suite import KNOWN_PLAUSIBILITY_FAILURES as KNOWN_FAILURES
from baile_nua.plausibility.checks import (
    MIN_DAYS_FOR_AN_ANNUAL_CHECK,
    T0_YEAR,
    _year_at_or_before_t0,
)
from baile_nua.sources import REGISTRY

ROOT = Path(__file__).resolve().parents[2]
E1 = ROOT / "v1"
E1_DIAG = ROOT / "v1" / "run_diagnostics.json"


def test_every_check_declares_a_source_or_a_declared_gap():
    """U27: source, tolerance, and for an unsourced check the issue."""
    for c in CHECKS:
        assert c.quantity and c.family, f"{c.check_id} is under-specified"
        assert c.tolerance, f"{c.check_id} has no tolerance"
        assert c.tolerance_basis, f"{c.check_id} does not say WHY its tolerance"
        if c.source_key is None:
            assert c.unsourced_issue, (
                f"{c.check_id} has no source and no issue recording the gap; "
                f"an unsourced check must be declared, not merely absent"
            )
        else:
            assert c.source_key in REGISTRY, (
                f"{c.check_id} cites {c.source_key}, which is not registered"
            )


def test_an_unsourced_pass_is_never_counted_as_a_sourced_one():
    """The distinction that stops the suite reading as coverage it lacks."""
    out = run_suite(package_root=E1, diagnostics_path=E1_DIAG)
    assert out["n_pass"] == out["n_pass_sourced"] + out["n_pass_unsourced_band"]
    assert out["n_sourced"] + out["n_unsourced"] == out["n_checks"]
    # The indoor-temperature check has a declared band and no source, so it
    # must appear as a pass that is NOT a sourced pass.
    temp = next(r for r in out["results"] if r["check_id"] == "PL-TEMP-01")
    assert temp["sourced"] is False
    assert temp["outcome"] in ("PASS", "FAIL"), (
        "a check with a declared band must still be evaluated; reporting it as "
        "unevaluable throws away a working verdict"
    )


def test_checks_with_neither_source_nor_band_are_not_evaluable():
    """Two remain, and PL-PEAK-01 is no longer one of them.

    I-039 listed three unsourced families. U30 confirmed two of them absent
    from the whole PxStat catalogue and found the third published by the
    network operator instead of the statistics office: ESB Networks' Standard
    Load Profile LP1. So PL-PEAK-01 is sourced and evaluable now, and this
    test's own list is the record of that change.
    """
    out = run_suite(package_root=E1, diagnostics_path=E1_DIAG)
    for cid in ("PL-APPLSHARE-01", "PL-EVHP-01"):
        r = next(x for x in out["results"] if x["check_id"] == cid)
        assert r["outcome"] == "NOT_EVALUABLE"
        assert r["sourced"] is False
        assert "I-039" in r["note"], (
            f"{cid} must name the issue that records its gap"
        )

    peak = next(x for x in out["results"] if x["check_id"] == "PL-PEAK-01")
    assert peak["sourced"] is True, (
        "PL-PEAK-01 lost its reference; I-039 is reopened if so"
    )
    assert peak["source_key"] == "esbn.rmds.slp_indexes_2022"
    assert peak["outcome"] in ("PASS", "FAIL"), (
        "a sourced check with a band must reach a verdict, not NOT_EVALUABLE"
    )


def test_the_e1_package_fails_only_what_is_known_to_fail():
    """The regression fixture (U23 keeps the E1 estate for exactly this).

    PL-PEAK-01 fails on the overnight taper: the simulated town's load is flat
    from midnight to 04:00 where ESB Networks' LP1 falls by a factor of 1.72,
    because people go to bed. The load factor and the evening peak hour both
    pass. I-044 tracks it and the behaviour work owns the fix.
    """
    out = run_suite(package_root=E1, diagnostics_path=E1_DIAG)
    failed = {r["check_id"] for r in out["results"] if r["outcome"] == "FAIL"}
    unexpected = failed - set(KNOWN_FAILURES)
    assert not unexpected, f"the E1 package now fails {sorted(unexpected)}"
    fixed = set(KNOWN_FAILURES) - failed
    assert not fixed, (
        f"{sorted(fixed)} is listed as a known failure but now passes. Good "
        f"news: close its issue ({[KNOWN_FAILURES[c] for c in sorted(fixed)]}) "
        f"and remove it from KNOWN_FAILURES, so the list never shelters a "
        f"defect that has already been fixed."
    )
    assert out["n_pass_sourced"] >= 7, (
        f"only {out['n_pass_sourced']} sourced checks pass; the suite is "
        f"losing coverage"
    )


def test_a_partial_year_run_is_refused_not_failed(tmp_path):
    """Found by the suite's own write hook on a three-day smoke run.

    Comparing three days of accumulated energy against a yearly CSO figure
    failed, as it had to. Extrapolating would be worse: three days of January
    is three days of peak heating, so the verdict would turn on the
    arithmetic of the extrapolation rather than on the model.
    """
    diag = json.loads(E1_DIAG.read_text())
    diag["benchmark"]["n_days"] = 3
    (tmp_path / "ground_truth").mkdir()
    (tmp_path / "observable").mkdir()
    dpath = tmp_path / "run_diagnostics.json"
    dpath.write_text(json.dumps(diag, default=str), encoding="utf-8")

    out = run_suite(package_root=tmp_path, diagnostics_path=dpath)
    for cid in ("PL-ELEC-01", "PL-GAS-01", "PL-MIX-01"):
        r = next(x for x in out["results"] if x["check_id"] == cid)
        assert r["outcome"] == "NO_DATA", (
            f"{cid} returned {r['outcome']} on a 3-day run; an annual check "
            f"must refuse a partial year rather than fail it"
        )
        assert str(MIN_DAYS_FOR_AN_ANNUAL_CHECK) in r["note"]


def test_a_reference_year_after_t0_is_never_used():
    """NDA08 runs to 2026 and the first version validated 2022 against it."""
    years = [str(y) for y in range(2011, 2027)]
    assert _year_at_or_before_t0(years) == T0_YEAR
    # A table that stops before t0 uses its latest and the gap is reported.
    assert _year_at_or_before_t0([str(y) for y in range(2004, 2020)]) == "2019"
    # And a table starting after t0 falls back to its earliest, not a crash.
    assert _year_at_or_before_t0(["2024", "2025"]) == "2024"


def test_the_suite_runs_on_a_package_write():
    """U27: "Run it on every package write"."""
    import inspect

    from baile_nua.engine import e1_run

    src = inspect.getsource(e1_run.run_year)
    assert "write_suite" in src, (
        "run_year does not run the plausibility suite, so a package can be "
        "written without being checked"
    )
    assert "PlausibilityFailure" in src
    # And the failure must be raised AFTER the package is written.
    assert src.index("run_diagnostics.json") < src.index("PlausibilityFailure"), (
        "the suite must raise after the package is on disk, so that what was "
        "rejected can be inspected"
    )


def test_every_sourced_check_records_the_hash_it_read():
    out = run_suite(package_root=E1, diagnostics_path=E1_DIAG)
    for r in out["results"]:
        if r["sourced"] and r["outcome"] in ("PASS", "FAIL"):
            assert r["source_sha256"] and len(r["source_sha256"]) == 64, (
                f"{r['check_id']} does not record the SHA-256 of the file it "
                f"compared against"
            )


# --------------------------------------------------------------------------- #
# the known-failure register
# --------------------------------------------------------------------------- #

def test_the_known_failure_register_is_the_only_one():
    """One register of the fact, read by the run hook and by this file.

    There was briefly a copy of this list here and another fact implied by the
    run hook refusing every failure, which is two registers of the same thing
    and a guarantee that they drift. The register lives in the plausibility
    package and both read it.
    """
    import inspect

    from baile_nua.engine import e1_run
    from baile_nua.plausibility import suite

    assert KNOWN_FAILURES is suite.KNOWN_PLAUSIBILITY_FAILURES
    hook = inspect.getsource(e1_run.run_year)
    assert "KNOWN_PLAUSIBILITY_FAILURES" in hook, (
        "the run hook no longer consults the register, so a declared known "
        "failure would either block every run or be waived silently"
    )


def test_every_known_failure_names_an_issue():
    """"Known" has to mean written down, not tolerated."""
    import re

    issues = (ROOT / "docs" / "ISSUES.md").read_text(encoding="utf-8")
    for check_id, issue in sorted(KNOWN_FAILURES.items()):
        assert re.match(r"^I-\d{3}$", issue), (check_id, issue)
        assert f"## {issue} " in issues, (
            f"{check_id} is declared a known failure tracked as {issue}, but "
            f"{issue} has no entry in docs/ISSUES.md"
        )
        assert check_id in {c.check_id for c in CHECKS}, (
            f"{check_id} is in the register but is not a declared check"
        )


def test_an_undeclared_failure_still_stops_a_package():
    """The register must not become a blanket waiver.

    Checked on the hook's own logic rather than by running a year: the
    distinction that matters is between a failure with an issue number and a
    failure nobody knew about, and only the second may pass silently.
    """
    import inspect

    from baile_nua.engine import e1_run

    hook = inspect.getsource(e1_run.run_year)
    assert "if unknown:" in hook
    assert "raise PlausibilityFailure" in hook
    # The raise must be reached from the unknown branch, not from `failed`.
    tail = hook[hook.index("if unknown:"):]
    assert "raise PlausibilityFailure" in tail[:800]


def test_the_suite_separates_independent_passes_from_calibration_inputs():
    """I-058: "n sourced" reads as independence the suite does not have.

    PL-ELEC-01 scores against DBEREL01 and PL-GAS-01 against DBERNG01, and
    both of those are declared at exposure `tuning` — the appliance trigger
    rates were adjusted against the first and the I-031 floor-area fixes were
    checked against the second. A check scored against a source the model was
    calibrated on is a consistency check: it can catch gross error, which is
    what these two were built for, but it cannot evidence generalisation.

    So the summary carries an independence count alongside the sourced count,
    and this test pins the gap between them rather than the absolute numbers,
    which move as sources are added.
    """
    import baile_nua.sources_registry  # noqa: F401
    from baile_nua.plausibility.checks import CHECKS
    from baile_nua.sources import REGISTRY

    tuned = {
        c.check_id for c in CHECKS
        if c.source_key
        and REGISTRY[c.source_key].model_development_exposure == "tuning"
    }
    assert tuned == {"PL-ELEC-01", "PL-GAS-01"}, (
        f"the set of checks scored against a calibration input has changed to "
        f"{sorted(tuned)}. If a check was added, I-058 needs updating; if one "
        f"was made independent, say so there."
    )
    # And every one of them states the consequence where its use is described.
    for check_id in tuned:
        key = next(c.source_key for c in CHECKS if c.check_id == check_id)
        used_for = REGISTRY[key].used_for
        assert "CONSISTENCY" in used_for, (
            f"{key} backs {check_id} and is tuning-exposed, but its used_for "
            f"does not say the check is a consistency check: {used_for!r}"
        )
        assert "I-058" in used_for, key


def test_the_held_out_energy_axes_are_still_independent():
    """What validates energy, now that two checks cannot."""
    import baile_nua.sources_registry  # noqa: F401
    from baile_nua.sources import REGISTRY

    for key in ("cso.electricity.dbere102_by_dwelling_construction",
                "cso.gas.dberng02_by_dwelling_construction"):
        if key not in REGISTRY:
            continue
        assert REGISTRY[key].model_development_exposure == "none", (
            f"{key} is the held-out axis and is declared "
            f"{REGISTRY[key].model_development_exposure!r}. With PL-ELEC-01 "
            f"and PL-GAS-01 scored against calibration inputs, this is the "
            f"only independent energy evidence left."
        )
