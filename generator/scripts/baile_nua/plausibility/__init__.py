"""U27: output plausibility against published Irish references.

Standing requirement, approved 9 October 2026. Every major output is checked
against a published reference in ``sources/``, each check carrying its source,
its tolerance and an expected-failure negative control, and the suite runs on
every package write.

The reason it exists is the week 1 record. Four defects — I-027, I-031, I-032,
I-033 — were each found by comparing an output against a public figure, and
each had survived a green test suite:

* appliance electricity 40% above the national mean for *everything*, found
  only once a CSO table existed to compare against;
* a 285.7 m² three-bedroom apartment, found by that same table and only
  because the estate happened to contain one electrically heated home;
* an annual median indoor temperature of 24.6 °C, found by running the V0
  invariants over the written package;
* a 40 °C peak in nearly every month, found by the distributional invariant
  added for the previous one.

The pattern is the point: **a unit test asks whether the code does what it was
told; a plausibility check asks whether what it was told is true.** U27's last
sentence — "unit tests alone never pass a gate" — is that observation made
binding.
"""

from baile_nua.plausibility.suite import (
    CHECKS,
    PlausibilityCheck,
    PlausibilityResult,
    run_suite,
    write_suite,
)

__all__ = [
    "CHECKS",
    "PlausibilityCheck",
    "PlausibilityResult",
    "run_suite",
    "write_suite",
]
