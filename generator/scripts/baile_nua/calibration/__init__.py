"""D24 calibration targets: every target number, read from a file in sources/.

The brief's rule, in full: "Do not hard-code statistics from memory. Every
calibration number traces to a file in sources/ (D24 calibration_targets)."

This package is how that rule is kept mechanically rather than by discipline.
Nothing here holds a literal statistic. Each target is a *reader* that opens a
registered source, pulls the cell it names, and returns the value together with
the source key and the SHA-256 of the bytes it came from, so a target can
always be traced back to the download that produced it - and so that a target
silently changing when a source is re-downloaded is visible rather than not.
"""

from __future__ import annotations

from baile_nua.calibration.targets import (
    CalibrationTarget,
    TargetError,
    build_d24,
    electricity_per_dwelling_targets,
    meter_distribution_target,
    per_meter_target,
    write_d24,
)

__all__ = [
    "CalibrationTarget",
    "TargetError",
    "build_d24",
    "electricity_per_dwelling_targets",
    "meter_distribution_target",
    "per_meter_target",
    "write_d24",
]
