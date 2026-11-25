"""The U27 plausibility suite: declared checks, measured outputs, verdicts.

**How a check is specified.** Each carries the quantity it measures, the
registered source it is held to, how the reference is read from that source,
the tolerance and why that tolerance, and a function that extracts the measured
value from a written package. A check with no registered source is **not
omitted** — it is declared ``UNSOURCED`` with the issue that records the gap,
and the suite reports it. A suite that silently skipped what it could not
source would read as coverage.

**Outcomes.**

``PASS``           measured value inside the tolerance band
``FAIL``           outside it
``NOT_EVALUABLE``  no reference AND no declared band: nothing to compare
``NO_DATA``        the package does not contain what the check needs

**``sourced`` is a separate field from the outcome**, and the distinction
matters. A check can have a usable tolerance without a published source - the
indoor-temperature band is declared ``[A]`` because no CSO or SEAI table
publishes measured Irish indoor temperatures, yet the band still refuses a
24.6 °C annual median. The first version of this runner returned
``UNSOURCED`` whenever a check had no source key and never ran the
measurement, which threw away a working check's verdict. Now the measurement
runs, the verdict stands, and ``sourced=False`` records that the tolerance is
declared rather than published.

So a gate reads **two** counts, never one: how many checks passed, and how
many of those were against a published reference. "5 of 5 passed" is not the
same claim as "5 of 9 are sourced at all", and a suite that reported only the
first would read as coverage it does not have.
"""

from __future__ import annotations

import dataclasses
import itertools
import json
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

__all__ = [
    "CHECKS",
    "PlausibilityCheck",
    "PlausibilityResult",
    "read_jsonstat",
    "run_suite",
    "write_suite",
    "KNOWN_PLAUSIBILITY_FAILURES",
]


# --------------------------------------------------------------------------- #
# reading references
# --------------------------------------------------------------------------- #

def read_jsonstat(source_key: str) -> tuple[dict[str, Any], dict[tuple, Any], str]:
    """A registered JSON-stat source, indexed by label tuple, with its SHA-256."""
    from baile_nua.sources import REGISTRY, require

    path = require(source_key)
    doc = json.loads(path.read_text(encoding="utf-8"))
    ids = doc["id"]
    labels = [list(doc["dimension"][i]["category"]["label"].values()) for i in ids]
    values = doc["value"]
    cells = {
        combo: (values[i] if isinstance(values, list) else values.get(str(i)))
        for i, combo in enumerate(itertools.product(*labels))
    }
    sha = json.loads(
        REGISTRY[source_key].manifest_path.read_text(encoding="utf-8")
    )["sha256"]
    return doc, cells, str(sha)


#: Checks a package is KNOWN to fail, each with the issue that tracks it.
#:
#: This is not a tolerance, not a skip, and not a waiver. The suite still
#: reports FAIL, the artefact still records it, and the run still says so
#: loudly. What the register does is separate two different events that look
#: identical to a write hook: a model defect somebody has written down and is
#: working on, and a model defect nobody knew about. The second must stop a
#: package being delivered. The first already has an issue number.
#:
#: There was briefly one of these in `tests/test_plausibility.py` and another
#: implied by the run hook refusing everything, which is two registers of the
#: same fact. One register, here, read by both.
#:
#: Two rules keep it from becoming a dumping ground:
#:
#: * a known failure that starts PASSING is an error, so an entry cannot
#:   outlive the defect it describes;
#: * every entry names an issue, so "known" means written down rather than
#:   tolerated.
KNOWN_PLAUSIBILITY_FAILURES: dict[str, str] = {
    # Empty, and it got here the way it was meant to.
    #
    # PL-PEAK-01 / I-044 was the only entry: the simulated town had no
    # overnight taper, flat from midnight to 04:00 where ESB Networks' LP1
    # falls by a factor of 1.72. Fixed on 10 Oct 2026 - the activity engine
    # was discarding every bedtime past midnight - and the taper now measures
    # 1.41 against a floor of 1.25.
    #
    # The removal was not voluntary. The second rule above fired:
    # `test_the_e1_package_fails_only_what_is_known_to_fail` failed with
    # "['PL-PEAK-01'] is listed as a known failure but now passes", which is
    # the register refusing to shelter a defect that no longer exists. An
    # entry here cannot outlive the thing it describes.
}


# --------------------------------------------------------------------------- #
# the check contract
# --------------------------------------------------------------------------- #

@dataclasses.dataclass
class PlausibilityCheck:
    """One declared check: what, against what, within what, and why."""

    check_id: str
    quantity: str
    #: Registered source key, or None when no published Irish reference exists.
    source_key: str | None
    reference_note: str
    tolerance: str
    tolerance_basis: str
    #: Returns ``(measured, reference, passed, detail)``; may raise LookupError
    #: when the package has nothing to measure.
    measure: Callable[[dict[str, Any]], tuple[Any, Any, bool, dict[str, Any]]]
    #: The issue that records the gap, for unsourced checks.
    unsourced_issue: str | None = None
    family: str = ""
    #: True when the check has a usable tolerance even without a source, so
    #: the measurement is still worth running.
    has_declared_band: bool = False


@dataclasses.dataclass
class PlausibilityResult:
    check_id: str
    quantity: str
    family: str
    outcome: str                   # PASS | FAIL | NOT_EVALUABLE | NO_DATA
    #: Whether the tolerance traces to a published reference in sources/.
    sourced: bool = True
    measured: Any = None
    reference: Any = None
    source_key: str | None = None
    source_sha256: str | None = None
    #: I-058. The source's declared model-development exposure. A check scored
    #: against a source at exposure "tuning" is a CONSISTENCY check against a
    #: calibration input, not an independent validation - it can still catch
    #: gross error, which is what PL-ELEC-01 and PL-GAS-01 were built for, but
    #: it cannot evidence generalisation. Carried on the result so that
    #: "9 sourced checks pass" cannot be read as nine independent ones.
    source_exposure: str | None = None
    tolerance: str = ""
    tolerance_basis: str = ""
    detail: dict[str, Any] = dataclasses.field(default_factory=dict)
    note: str = ""

    @property
    def passed(self) -> bool:
        return self.outcome == "PASS"

    def as_row(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


# --------------------------------------------------------------------------- #
# the package view a check is given
# --------------------------------------------------------------------------- #

def _package(root: Path, diagnostics_path: Path | None = None) -> dict[str, Any]:
    """Assemble what the checks need from a written package.

    Reads the delivered Parquet and the run diagnostics, never the simulation,
    so a check cannot accidentally test the model against itself.
    """
    root = Path(root)
    out: dict[str, Any] = {"root": root}

    def parts(sub: str, dataset_id: str) -> pd.DataFrame | None:
        files = sorted((root / sub).glob(f"{dataset_id}_part*.parquet"))
        if not files:
            single = root / sub / f"{dataset_id}.parquet"
            files = [single] if single.exists() else []
        if not files:
            return None
        return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)

    out["D16"] = parts("ground_truth", "D16")
    out["D13"] = parts("ground_truth", "D13")
    out["D18"] = parts("observable", "D18")
    out["D19"] = parts("observable", "D19")

    dpath = diagnostics_path or (root / "run_diagnostics.json")
    out["diagnostics"] = (
        json.loads(Path(dpath).read_text(encoding="utf-8"))
        if Path(dpath).exists() else None
    )
    return out


# --------------------------------------------------------------------------- #
# runner
# --------------------------------------------------------------------------- #

def run_suite(
    *, package_root: Path, diagnostics_path: Path | None = None,
    checks: tuple[PlausibilityCheck, ...] | None = None,
) -> dict[str, Any]:
    """Run every declared check against a written package."""
    from baile_nua import CLAIM, LABEL
    from baile_nua.sources import REGISTRY

    pkg = _package(package_root, diagnostics_path)
    results: list[PlausibilityResult] = []

    for check in (checks if checks is not None else CHECKS):
        sourced = check.source_key is not None
        if not sourced and not check.has_declared_band:
            # No reference and no band: there is genuinely nothing to compare.
            results.append(PlausibilityResult(
                check_id=check.check_id, quantity=check.quantity,
                family=check.family, outcome="NOT_EVALUABLE", sourced=False,
                source_exposure=exposure,
                tolerance=check.tolerance, tolerance_basis=check.tolerance_basis,
                note=(
                    f"No published Irish reference and no declared band. "
                    f"Declared gap: {check.unsourced_issue}. "
                    f"{check.reference_note}"
                ),
            ))
            continue

        # I-058: a check scored against a source the model was CALIBRATED on
        # is a consistency check, not an independent validation. Both
        # exposures were already declared; what was missing was carrying the
        # consequence into the result, so "9 sourced checks pass" could be
        # read as nine independent ones.
        exposure = (
            REGISTRY[check.source_key].model_development_exposure
            if check.source_key else None
        )
        sha = None
        if sourced:
            # From the MANIFEST, not by parsing: the manifest records the
            # SHA-256 of the bytes on disk, so this works for a source that is
            # not JSON-stat at all. PL-PEAK-01's reference is an ESB Networks
            # spreadsheet, and the earlier version of this - parse as
            # JSON-stat, swallow the exception, record None - would have
            # reported a sourced check with no hash and passed the test that
            # exists to prevent exactly that.
            try:
                sha = json.loads(
                    REGISTRY[check.source_key].manifest_path.read_text(
                        encoding="utf-8"
                    )
                )["sha256"]
            except Exception:                            # pragma: no cover
                sha = None

        try:
            measured, reference, passed, detail = check.measure(pkg)
        except LookupError as exc:
            results.append(PlausibilityResult(
                check_id=check.check_id, quantity=check.quantity,
                family=check.family, outcome="NO_DATA", sourced=sourced,
                source_key=check.source_key, source_sha256=sha,
                source_exposure=exposure,
                tolerance=check.tolerance, tolerance_basis=check.tolerance_basis,
                note=f"the package does not contain what this check needs: {exc}",
            ))
            continue

        results.append(PlausibilityResult(
            check_id=check.check_id, quantity=check.quantity,
            family=check.family, outcome=("PASS" if passed else "FAIL"),
            sourced=sourced, measured=measured, reference=reference,
            source_key=check.source_key, source_sha256=sha,
            source_exposure=exposure,
            tolerance=check.tolerance, tolerance_basis=check.tolerance_basis,
            detail=detail,
            note=check.reference_note,
        ))

    by_outcome: dict[str, int] = {}
    for r in results:
        by_outcome[r.outcome] = by_outcome.get(r.outcome, 0) + 1
    families = sorted({c.family for c in (checks if checks is not None else CHECKS)})

    return {
        "label": LABEL,
        "claim": CLAIM,
        "design_ref": "U27 (standing requirement, 9 October 2026); 7.1; D24",
        "package_root": str(package_root),
        "n_checks": len(results),
        "by_outcome": by_outcome,
        "families": families,
        "n_pass": by_outcome.get("PASS", 0),
        "n_fail": by_outcome.get("FAIL", 0),
        "n_not_evaluable": by_outcome.get("NOT_EVALUABLE", 0),
        "n_no_data": by_outcome.get("NO_DATA", 0),
        "n_sourced": sum(1 for r in results if r.sourced),
        "n_unsourced": sum(1 for r in results if not r.sourced),
        "n_pass_sourced": sum(
            1 for r in results if r.outcome == "PASS" and r.sourced
        ),
        "n_pass_unsourced_band": sum(
            1 for r in results if r.outcome == "PASS" and not r.sourced
        ),
        "all_evaluable_checks_pass": by_outcome.get("FAIL", 0) == 0,
        "unsourced_families": sorted(
            {r.family for r in results if not r.sourced}
        ),
        # I-058. Of the sourced checks, how many are against a source the
        # model was NOT calibrated on. That is the independence count, and it
        # is smaller than n_sourced.
        "n_pass_independent": sum(
            1 for r in results
            if r.outcome == "PASS" and r.sourced
            and r.source_exposure == "none"
        ),
        "n_pass_against_a_calibration_input": sum(
            1 for r in results
            if r.outcome == "PASS" and r.sourced
            and r.source_exposure == "tuning"
        ),
        "n_pass_against_a_design_exposed_reference": sum(
            1 for r in results
            if r.outcome == "PASS" and r.sourced
            and r.source_exposure == "design"
        ),
        "checks_against_calibration_inputs": sorted(
            r.check_id for r in results if r.source_exposure == "tuning"
        ),
        "rule": (
            "Three counts, never one. A pass against a DECLARED band is not a "
            "pass against a published reference; a pass against a source the "
            "model was CALIBRATED on is a consistency check and not an "
            "independent validation (I-058); and a check with neither a "
            "reference nor a band is reported as NOT_EVALUABLE with the issue "
            "that records the gap. A suite reporting only 'n passed' would "
            "read as coverage it does not have, and one reporting 'n sourced' "
            "would read as independence it does not have either."
        ),
        "results": [r.as_row() for r in results],
    }


def write_suite(
    *, package_root: Path, out_path: Path,
    diagnostics_path: Path | None = None,
) -> dict[str, Any]:
    out = run_suite(
        package_root=package_root, diagnostics_path=diagnostics_path
    )
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(
        json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8"
    )
    return out


# Checks are declared in `checks.py` and imported here so that this module
# holds only the contract and the runner.
from baile_nua.plausibility.checks import CHECKS  # noqa: E402
