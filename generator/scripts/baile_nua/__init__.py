"""Baile Nua / HRSD_Occupants — synthetic Irish town generator.

Implements design revision 3 (architecture frozen 8 October 2026).  Scope of
this tree is gate **E1**, the Week 1 engineering proof of concept.

Every output and report carries the label below.  It is not decoration: E1
reaches validation level V0 only (design 7), which proves correct
implementation and *nothing* about realism.
"""

from __future__ import annotations

__version__ = "0.1.0a1+e1"
LABEL = "UNVALIDATED SIMULATION EVIDENCE: E1 engineering candidate"
CLAIM = "Engineering verification only. No behavioural calibration is claimed."
DESIGN_REVISION = 3

__all__ = ["__version__", "LABEL", "CLAIM", "DESIGN_REVISION"]
