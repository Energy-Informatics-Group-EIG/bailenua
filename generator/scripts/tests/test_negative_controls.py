"""Negative-control suite (design 7 preamble, 9.3 negative-control rule).

    This follows the HRSD principle that a check which has never failed has not
    been tested: every check below ships with a deliberately broken "negative
    control" dataset that it must reject.  (design 7)

    Each broken dataset declares its intended test and an expected failure
    assertion (the specific check and message).  It passes only if that test
    fails for that reason.  A generic non-zero exit, or a failure in another
    test, counts as a harness defect.  (design 9.3)

This module runs the registry and writes the artefact the E1 gate report is
generated from.  It never summarises; every control's expected and observed
failure is recorded individually.
"""

from __future__ import annotations

import pytest

from baile_nua.validation import negative_control as nc

# Discovery rather than a list of imports. The list fell behind: this file
# imported controls_day1 and controls_day2 and nothing else, so the suite
# covered nine of seventeen controls and the Day 3 to 6 ones were exercised
# only by `baile-nua controls run`. An unregistered control is simply absent,
# which is the quietest way for a check to stop being checked.
nc.import_all_controls()

pytestmark = pytest.mark.negative_control


def _ids() -> list[str]:
    return sorted(nc.REGISTRY)


def test_registry_is_not_empty():
    assert nc.REGISTRY, "no negative controls registered: every check needs one"


def test_every_controls_module_is_discovered_and_registered():
    """No controls module may be left out of the suite (the gap above).

    Asserted against the modules found on disk, so adding a controls module
    and forgetting to wire it in fails here instead of silently shrinking the
    gate.
    """
    modules = nc.discover_control_modules()
    assert len(modules) >= 4, (
        f"only {len(modules)} controls modules discovered: {modules}"
    )
    import sys

    for name in modules:
        assert name in sys.modules, f"{name} registers controls but was not imported"
    # Every day of design 9.3 that declares controls must have some.
    prefixes = {cid.split("-")[1] for cid in nc.REGISTRY}
    assert {"D1", "D2", "D3", "D4", "D5", "D6"} <= prefixes, (
        f"controls are missing for some days: found {sorted(prefixes)}"
    )


#: Controls that are KNOWN not to be detected, with the reason and the issue
#: that records it.  Listing one here is not a way to make a failure disappear:
#: the expected outcome is asserted exactly, so a control that starts passing
#: also fails this test and has to be moved out deliberately.
#:
#: **It is empty, and that is the point.**  NC-D2-03 was the only entry, on the
#: reasoning recorded in I-020: a 10% marginal shift sits inside the
#: sampling-error band at the Baile Nua town size, so the failure was a
#: sample-size limitation of the test rather than a software defect.
#:
#: That reasoning was correct about the arithmetic and wrong about what to do.
#: A negative control whose magnitude sits below its check's resolution cannot
#: fail, and a control that cannot fail tests nothing - so filing it as a
#: recognised limitation left design 9.3's "marginals shifted 10%" nominally
#: covered by a control incapable of covering it. I-034 amends the rule:
#: magnitudes come from a power analysis against the check's own resolution,
#: and the 10% fault is now pointed at a check with the power to see it (D-026,
#: D-027). The fault itself is unchanged and `marginal_acceptance` is
#: unchanged.
#:
#: This test fired when that happened, which is exactly what it is for.
KNOWN_NOT_DETECTED: dict[str, str] = {}


@pytest.mark.parametrize("control_id", sorted(KNOWN_NOT_DETECTED))
def test_known_limitation_controls_have_the_recorded_outcome(control_id: str):
    """A recognised limitation stays recognised, and stays visible.

    If one of these starts being detected, this test fails and the entry must be
    removed on purpose - the list cannot silently absorb a fixed check.
    """
    result = nc.run_one(nc.REGISTRY[control_id])
    assert result.outcome == "NOT_DETECTED", (
        f"{control_id} now reports {result.outcome}; if the check has improved, "
        f"remove it from KNOWN_NOT_DETECTED and update ISSUES.md. Reason on "
        f"record: {KNOWN_NOT_DETECTED[control_id]}"
    )


def test_no_control_is_a_recognised_limitation():
    """Every control must be able to fail (I-034).

    The stronger statement, asserted so that the empty dictionary above cannot
    quietly acquire a new entry: a control that cannot fire its own check is a
    gap in the gate, not a limitation of it, and admitting one needs a power
    analysis showing why no check with the power exists.
    """
    assert KNOWN_NOT_DETECTED == {}, (
        f"these controls are recorded as undetectable: "
        f"{sorted(KNOWN_NOT_DETECTED)}. Each needs either a check with the "
        f"power to see it or a power analysis showing that none can exist at "
        f"this sample size - see I-034 and D-026 for the one case that arose."
    )


@pytest.mark.parametrize("control_id", [c for c in _ids() if c not in KNOWN_NOT_DETECTED])
def test_control_fails_for_its_declared_reason(control_id: str):
    """One test per control, so a failure names the control that is wrong."""
    result = nc.run_one(nc.REGISTRY[control_id])
    assert result.outcome == "PASS", (
        f"\n  control : {result.control_id} — {result.title}"
        f"\n  design  : {result.design_ref}"
        f"\n  check   : {result.intended_test}"
        f"\n  expected: {result.expected}"
        f"\n  observed: {result.observed}"
        f"\n  outcome : {result.outcome}"
        f"\n  detail  : {result.detail}"
    )


def test_every_control_declares_an_expected_failure_assertion():
    """The rule requires "the specific check and message", not a bare exception."""
    for cid, c in nc.REGISTRY.items():
        assert c.intended_test, cid
        assert c.expected_message, cid
        assert c.expected_exception is not None, cid
        assert c.design_ref, cid


def test_duplicate_control_ids_are_refused():
    existing = next(iter(nc.REGISTRY.values()))
    with pytest.raises(ValueError, match="duplicate negative control id"):
        nc.register(existing)


def test_harness_detects_a_control_that_is_not_detected():
    """The harness must report a useless check, not silently pass it.

    Without this, a control whose "broken" artefact is actually valid would look
    like a passing check.
    """
    useless = nc.NegativeControl(
        control_id="NC-SELFTEST-not-detected",
        title="self-test: an artefact that nothing rejects",
        design_ref="self-test of the harness",
        intended_test="a check that does nothing",
        expected_exception=AssertionError,
        expected_message="never appears",
        build=lambda: object(),
        invoke=lambda _: None,
    )
    assert nc.run_one(useless).outcome == "NOT_DETECTED"


def test_harness_detects_the_wrong_exception_type():
    control = nc.NegativeControl(
        control_id="NC-SELFTEST-wrong-type",
        title="self-test: wrong exception type",
        design_ref="self-test of the harness",
        intended_test="a check that raises the wrong type",
        expected_exception=KeyError,
        expected_message="anything",
        build=lambda: object(),
        invoke=lambda _: (_ for _ in ()).throw(ValueError("not a KeyError")),
    )
    assert nc.run_one(control).outcome == "WRONG_EXCEPTION"


def test_harness_detects_the_wrong_reason():
    control = nc.NegativeControl(
        control_id="NC-SELFTEST-wrong-reason",
        title="self-test: right type, wrong reason",
        design_ref="self-test of the harness",
        intended_test="a check that fails for a different reason",
        expected_exception=ValueError,
        expected_message="the declared reason",
        build=lambda: object(),
        invoke=lambda _: (_ for _ in ()).throw(ValueError("some unrelated failure")),
    )
    assert nc.run_one(control).outcome == "WRONG_REASON"


def test_harness_detects_collateral_failure():
    """Design 9.3: "a failure in another test counts as a harness defect"."""
    control = nc.NegativeControl(
        control_id="NC-SELFTEST-collateral",
        title="self-test: the control broke more than it claimed",
        design_ref="self-test of the harness",
        intended_test="the intended check",
        expected_exception=ValueError,
        expected_message="intended",
        build=lambda: object(),
        invoke=lambda _: (_ for _ in ()).throw(ValueError("intended failure")),
        must_still_pass=(
            ("an unrelated check", lambda _: (_ for _ in ()).throw(RuntimeError("also broke"))),
        ),
    )
    assert nc.run_one(control).outcome == "COLLATERAL_FAILURE"


def test_harness_detects_a_control_that_cannot_be_built():
    control = nc.NegativeControl(
        control_id="NC-SELFTEST-harness-defect",
        title="self-test: the broken artefact cannot be built",
        design_ref="self-test of the harness",
        intended_test="never reached",
        expected_exception=ValueError,
        expected_message="never reached",
        build=lambda: (_ for _ in ()).throw(OSError("cannot build")),
        invoke=lambda _: None,
    )
    assert nc.run_one(control).outcome == "HARNESS_DEFECT"


def test_writes_the_gate_artefact(tmp_path):
    """The E1 gate report is generated from artefacts, never from prose."""
    import json

    out = tmp_path / "negative_controls.json"
    results = nc.run_all(write_to=out)
    doc = json.loads(out.read_text())
    assert doc["n_controls"] == len(results)
    assert doc["label"].startswith("UNVALIDATED SIMULATION EVIDENCE")
    for r in doc["results"]:
        assert {"control_id", "expected", "observed", "outcome", "design_ref"} <= set(r)
