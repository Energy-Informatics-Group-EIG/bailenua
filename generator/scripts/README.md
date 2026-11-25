# baile_nua

Generator for **Baile Nua / HRSD_Occupants** — a synthetic Irish harbour town
calibrated to Cobh. Implements design revision 3 (architecture frozen 8 Oct 2026).

> **UNVALIDATED SIMULATION EVIDENCE: E1 engineering candidate.**
> Engineering verification only. No behavioural calibration is claimed.

Scope of this tree: gate **E1** (the Week 1 engineering proof of concept).

    python -m venv .venv && ./.venv/bin/pip install -e '.[dev]'
    ./.venv/bin/pytest -q                # CI suites
    ./.venv/bin/baile-nua --help         # CLI
