#!/usr/bin/env bash
# CI for Baile Nua / HRSD_Occupants (design 8.5: CI runs on every commit).
# Suites: schema, invariants, leakage, determinism, negative controls, MIMIC diff.
set -euo pipefail
cd "$(dirname "$0")"
PY=./.venv/bin/python
EV=../v1/evidence

echo "=== 1. schema (single source of truth) ==="
$PY -m baile_nua.cli schema check

echo; echo "=== 2. full test suite ==="
$PY -m pytest tests/ -q --junit-xml="$EV/junit.xml"

echo; echo "=== 2b. fast suite only (excludes the full-town synthesis) ==="
$PY -m pytest tests/ -q -m "not slow" 2>&1 | tail -1

echo; echo "=== 3. suites reported separately (design 9.2: pass/fail per criterion) ==="
for m in invariants leakage determinism negative_control mimic slow; do
  printf '  %-18s ' "$m"
  $PY -m pytest tests/ -q -m "$m" 2>&1 | tail -1
done

echo; echo "=== 4. negative controls, with expected vs observed failures ==="
$PY -m baile_nua.cli controls run "$EV/negative_controls.json" | tail -20

echo; echo "=== 5. MIMIC 1.1 schema diff (day-1 acceptance) ==="
$PY -m baile_nua.cli mimic diff | tail -3

echo; echo "=== 6. MIMIC source drift guard ==="
$PY -m baile_nua.cli mimic verify | tail -15

echo; echo "=== 7. data dictionary ==="
$PY -m baile_nua.cli schema dict "$EV/data_dictionary.md" | tail -1

echo; echo "CI GREEN"
