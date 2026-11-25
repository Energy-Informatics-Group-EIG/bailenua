"""Negative-control harness with expected-failure assertions.

Design 9.3, the negative-control rule, verbatim:

    Each broken dataset declares its intended test and an **expected failure
    assertion** (the specific check and message).  It passes only if that test
    fails for that reason.  A generic non-zero exit, or a failure in another
    test, counts as a harness defect.

So a control passes only when **all four** hold:

1. the intended check raised at all;
2. the exception is of the declared type (or a subclass);
3. its message contains the declared fragment - a different failure of the same
   type is not the failure we asked for;
4. every check listed in ``must_still_pass`` still passes on the broken
   artefact.  Without this, a control that broke three things at once would pass
   while telling us nothing about which check works.

Outcome vocabulary, which the gate report uses directly:

``PASS``                   the intended check failed for the intended reason
``NOT_DETECTED``           the broken artefact was accepted - the check is useless
``WRONG_EXCEPTION``        it failed, but with a different exception type
``WRONG_REASON``           right type, but the message is not the declared one
``COLLATERAL_FAILURE``     a check that should have been unaffected also failed
``HARNESS_DEFECT``         the control could not even be built
"""

from __future__ import annotations

import dataclasses
import re
import json
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

__all__ = ["NegativeControl", "ControlResult", "REGISTRY", "register", "run_all", "run_one"]


@dataclasses.dataclass(frozen=True)
class NegativeControl:
    """One deliberately broken artefact and the check that must reject it."""

    control_id: str
    title: str
    design_ref: str
    #: Human-readable name of the check that must fail, e.g.
    #: "baile_nua.schema.access.assert_no_forbidden_patterns".
    intended_test: str
    expected_exception: type[BaseException]
    #: Fragment that must appear in the exception message.  Chosen to be the
    #: part that identifies *why* it failed, not incidental wording.
    expected_message: str
    #: Builds the broken artefact.  Raising here is a HARNESS_DEFECT, not a pass.
    build: Callable[[], Any]
    #: Runs the intended check on the artefact.  Must raise.
    invoke: Callable[[Any], None]
    #: Checks that must still pass on the broken artefact, as
    #: ``(name, callable)`` pairs.  Keeps a control honest about its blast radius.
    must_still_pass: tuple[tuple[str, Callable[[Any], None]], ...] = ()


@dataclasses.dataclass
class ControlResult:
    control_id: str
    title: str
    design_ref: str
    intended_test: str
    expected: str
    observed: str
    outcome: str
    detail: str = ""

    @property
    def passed(self) -> bool:
        return self.outcome == "PASS"

    def as_dict(self) -> dict[str, Any]:
        return {**dataclasses.asdict(self), "passed": self.passed}


REGISTRY: dict[str, NegativeControl] = {}


def register(control: NegativeControl) -> NegativeControl:
    if control.control_id in REGISTRY:
        raise ValueError(f"duplicate negative control id {control.control_id!r}")
    REGISTRY[control.control_id] = control
    return control


def run_one(control: NegativeControl) -> ControlResult:
    expected = (
        f"{control.intended_test} raises {control.expected_exception.__name__} "
        f"containing {control.expected_message!r}"
    )

    def result(outcome: str, observed: str, detail: str = "") -> ControlResult:
        return ControlResult(
            control_id=control.control_id,
            title=control.title,
            design_ref=control.design_ref,
            intended_test=control.intended_test,
            expected=expected,
            observed=observed,
            outcome=outcome,
            detail=detail,
        )

    try:
        artefact = control.build()
    except Exception:  # noqa: BLE001 - a build failure is a harness defect
        return result(
            "HARNESS_DEFECT",
            "the broken artefact could not be built",
            traceback.format_exc(limit=4),
        )

    try:
        control.invoke(artefact)
    except control.expected_exception as exc:
        msg = str(exc)
        if control.expected_message not in msg:
            return result(
                "WRONG_REASON",
                f"{type(exc).__name__}: {msg[:300]}",
                f"expected message fragment {control.expected_message!r} absent",
            )
        observed = f"{type(exc).__name__}: {msg[:300]}"
    except Exception as exc:  # noqa: BLE001
        return result(
            "WRONG_EXCEPTION",
            f"{type(exc).__name__}: {str(exc)[:300]}",
            f"expected {control.expected_exception.__name__}",
        )
    else:
        return result(
            "NOT_DETECTED",
            "the intended check accepted the broken artefact",
            "This is a real finding: the check does not test what it claims to.",
        )

    # The blast-radius check: nothing else may have broken.
    for name, check in control.must_still_pass:
        try:
            check(artefact)
        except Exception as exc:  # noqa: BLE001
            return result(
                "COLLATERAL_FAILURE",
                observed,
                f"check {name!r} also failed on this control "
                f"({type(exc).__name__}: {str(exc)[:200]}). Design 9.3: a failure "
                f"in another test counts as a harness defect.",
            )

    return result("PASS", observed)


def run_all(write_to: Path | None = None) -> list[ControlResult]:
    results = [run_one(c) for c in REGISTRY.values()]
    if write_to is not None:
        write_to.parent.mkdir(parents=True, exist_ok=True)
        write_to.write_text(
            json.dumps(
                {
                    "label": "UNVALIDATED SIMULATION EVIDENCE: E1 engineering candidate",
                    "n_controls": len(results),
                    "n_passed": sum(r.passed for r in results),
                    "results": [r.as_dict() for r in results],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    return results


#: Modules under ``baile_nua.validation`` that register negative controls.
#:
#: Discovered rather than listed, because a list is a thing that falls behind.
#: It did: ``tests/test_negative_controls.py`` imported ``controls_day1`` and
#: ``controls_day2`` and nothing else, so for a whole day the suite covered
#: nine of seventeen controls and the Day 3 to 6 ones existed only behind
#: ``baile-nua controls run``. Nothing failed, because an unregistered control
#: is simply absent - which is the quietest way for a check to stop being
#: checked.
#: Matched on the CLASS being constructed and the registration call, not on
#: their exact call formatting. The first version looked for the literal
#: "register(NegativeControl(" and missed controls_day1 and controls_day2,
#: which put the two on separate lines - so the discovery that was written to
#: fix a stale import list started out with a stale pattern instead, and found
#: two modules of four. Formatting is not a contract.
_CONTROL_MODULE_PATTERN = re.compile(
    r"register\s*\(\s*NegativeControl\s*\(", re.S
)


def discover_control_modules() -> list[str]:
    """Names of every module in this package that registers a control.

    By source inspection rather than by importing everything and seeing what
    happens, so that a module which fails to import is reported as a module
    that failed to import rather than as a control that does not exist.
    """
    import pathlib

    here = pathlib.Path(__file__).parent
    out = []
    for path in sorted(here.glob("*.py")):
        if path.name.startswith("_") or path.name == "negative_control.py":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:                              # pragma: no cover
            continue
        if _CONTROL_MODULE_PATTERN.search(text):
            out.append(f"baile_nua.validation.{path.stem}")
    return out


def import_all_controls() -> dict[str, NegativeControl]:
    """Import every control module and return the full registry.

    The single entry point for "all the controls", used by the CLI and by the
    test suite so the two cannot disagree about what exists.
    """
    import importlib

    for name in discover_control_modules():
        importlib.import_module(name)
    return REGISTRY
