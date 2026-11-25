"""Tests for the E1 gate report generator.

The property under test is the one design 9.3 day 7 asks for: the report is
generated from artefacts only. So the tests feed it artefacts - including
artefacts that say things FAILED - and check that it says so. A report
generator that can only render a pass is not a report generator.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from baile_nua.report import ArtefactMissing, build_report, write_report
from baile_nua.report.e1_gate import _issues_summary, _junit_summary


def _fixture(root: Path, *, failing: bool = False) -> Path:
    """A complete, minimal set of artefacts."""
    ev = root / "v1" / "evidence"
    ev.mkdir(parents=True, exist_ok=True)
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "sources").mkdir(parents=True, exist_ok=True)

    (root / "v1" / "run_diagnostics.json").write_text(json.dumps({
        "label": "UNVALIDATED SIMULATION EVIDENCE: E1 engineering candidate",
        "claim": "Engineering verification only. No behavioural calibration is claimed.",
        "coupling_mode": "C1",
        "network_claim": "E1 makes no network claim.",
        "master_seed": 1,
        "checkpoint_chain_head": "abc",
        "max_physics_relative_residual": 1e-13,
        "max_energy_closure_relative_residual": 1e-16,
        "slice": {
            "n_homes": 50, "n_people": 147, "n_life_events": 1,
            "n_disruptions_total": 2400,
        },
        "benchmark": {
            "machine": {"cpu_brand": "test", "memory_gb": 32, "cpu_count": 12,
                        "python": "3.12.0", "machine": "x86_64"},
            "n_days": 365, "home_days": 18250, "home_minutes": 26_280_000,
            "mean_s_per_day": 2.5, "median_s_per_day": 2.4, "p95_s_per_day": 3.1,
            "mean_write_s_per_day": 3.0, "mean_total_s_per_day": 5.5,
            "ms_per_home_day": 110.0, "ms_per_home_day_simulation_only": 50.0,
            "write_share_of_runtime": 0.545,
            "peak_rss_mb": 3000.0,
            "timings": {"town_s": 30.0, "weather_s": 12.0, "slice_s": 0.2,
                        "simulate_s": 912.5, "write_s": 1095.0,
                        "run_s": 2007.5, "total_s": 2050.0},
            "storage": {
                "total_bytes": 700_000_000, "total_mb": 667.6,
                "by_dataset": {
                    "D13": {"rows": 1_500_000, "bytes": 40_000_000, "bytes_per_row": 26.7},
                    "D16": {"rows": 1_752_000, "bytes": 110_000_000, "bytes_per_row": 62.8},
                    "D18": {"rows": 66_000_000, "bytes": 520_000_000, "bytes_per_row": 7.9},
                    "D19": {"rows": 3_500_000, "bytes": 30_000_000, "bytes_per_row": 8.6},
                },
            },
            "full_town_projection": {
                "n_town_homes": 1092, "scale_factor": 21.84,
                "projected_run_hours": 12.2, "projected_run_hours_with_margin": 18.3,
                "projected_simulate_hours": 5.5, "projected_write_hours": 6.6,
                "runtime_note": "Split reported because the two are not the same size.",
                "projected_storage_gb": 14.3, "projected_storage_gb_with_margin": 21.5,
                "projected_storage_gb_ten_years": 143.0,
                "projected_storage_gb_ten_years_with_margin": 214.5,
                "projected_peak_rss_gb_if_naive": 64.0, "machine_memory_gb": 32.0,
                "memory_note": "Streamed, so memory is bounded not scaled.",
                "margin": 1.5, "margin_basis": "U21.",
            },
        },
        "annual_electricity": {
            "summary": {
                "mean_simulated_kwh_yr": 4100.0,
                "fossil_heated": {
                    "n": 49, "mean_simulated_kwh_yr": 3381.4,
                    "mean_d24_target_kwh_yr": 5405.1,
                    "mean_ratio_simulated_over_target": 0.694,
                    "share_within_plus_minus_30pct": 0.388,
                },
                "electrically_heated": {
                    "n": 1, "mean_simulated_kwh_yr": 5795.4,
                    "mean_d24_target_kwh_yr": 2999.0,
                    "mean_ratio_simulated_over_target": 1.932,
                },
                "gas_heated_space_heat": {
                    "n": 49, "mean_space_heat_kwh_yr": 3506.7,
                    "mean_space_heat_kwh_m2_yr": 29.8,
                    "mean_d24_gas_target_kwh_yr": 10587.1,
                    "mean_ratio_space_heat_over_gas_target": 0.308,
                },
            },
            "per_dwelling": [],
        },
    }), encoding="utf-8")

    (ev / "v0_invariants.json").write_text(json.dumps({
        "n_invariants": 7, "n_pass": 6, "n_fail": 1 if failing else 0,
        "n_skipped": 1 if not failing else 0,
        "zero_failures": not failing,
        "invariants": [
            {"invariant": "energy_closure", "status": "FAIL" if failing else "PASS",
             "n_violations": 3 if failing else 0, "n_checked": 18250,
             "skipped_reason": None},
            {"invariant": "no_child_alone", "status": "PASS" if failing else "SKIPPED",
             "n_violations": 0, "n_checked": 0,
             "skipped_reason": None if failing else "presence collected for 14 days only"},
        ],
    }), encoding="utf-8")

    (ev / "worker_determinism.json").write_text(json.dumps({
        "days": 3, "n_homes": 50, "worker_counts_used": [1, 8, 12],
        "all_byte_identical": not failing,
        "comparisons": [
            {"a_workers": 1, "b_workers": 8, "n_files_compared": 12,
             "differing_files": ["D18_part000.parquet"] if failing else [],
             "files_only_in_a": [], "files_only_in_b": [],
             "chain_head_matches": True, "byte_identical": not failing},
        ],
    }), encoding="utf-8")

    (ev / "checkpoint_replay.json").write_text(json.dumps({
        "n_checkpoints": 365, "n_home_days_requested": 100,
        "n_home_days_checked": 100, "n_days_replayed": 71,
        "n_mismatches": 2 if failing else 0,
        "worst_absolute_difference": 1.5 if failing else 0.0,
        "exact_replay": not failing, "mismatches": [],
    }), encoding="utf-8")

    (ev / "negative_controls.json").write_text(json.dumps({
        "n_controls": 2, "n_passed": 1 if failing else 2,
        "results": [
            {"control_id": "NC-X-01", "title": "a thing", "design_ref": "9.3",
             "intended_test": "check_it", "expected": "raises X containing 'y'",
             "observed": "X: y", "outcome": "PASS", "detail": "", "passed": True},
            {"control_id": "NC-X-02", "title": "another", "design_ref": "9.3",
             "intended_test": "check_that", "expected": "raises X containing 'z'",
             "observed": "nothing was raised", "detail": "below resolution",
             "outcome": "NOT_DETECTED" if failing else "PASS",
             "passed": not failing},
        ],
    }), encoding="utf-8")

    (ev / "mimic_tests_T1_T10.json").write_text(json.dumps({
        "counters": {
            "unique_synthetic_participants": 9000 if failing else 11664,
            "completed_sessions": 10832, "completed_responses": 146324,
            "linked_baile_nua_panel_participants": 1014,
            "unlinked_extended_pool_participants": 10050,
        },
        "tests": [
            {"test_id": t, "title": f"test {t}", "pass_criterion": "c",
             "outcome": "PASS", "detail": "d", "e1_required": t in ("T1", "T9", "T10")}
            for t in ("T1", "T9", "T10")
        ],
    }), encoding="utf-8")

    (ev / "saps_marginals.json").write_text(json.dumps({
        "n_marginals": 23, "alpha": 0.05, "n_within_simultaneous_band": 23,
        "all_within_simultaneous_band": not failing,
        "worst_abs_z": 2.1, "worst_critical_z": 3.6,
    }), encoding="utf-8")

    (ev / "u03_comparison.json").write_text(json.dumps({
        "metric_names": ["joint_mean_abs_difference"],
        "rows": [{"method": "proportional",
                  "metrics": {"joint_mean_abs_difference": "0.01 ± 0.001"},
                  "means": {"joint_mean_abs_difference": 0.01}}],
        "recommendation": "proportional",
        "recommendation_reason": "smaller joint error",
        "summary_text": "both built",
        "contradicts_design": True,
        "contradiction_note": "coverage explains it",
    }), encoding="utf-8")

    (ev / "d24_calibration_targets.json").write_text(
        json.dumps({"n_targets": 57, "targets": []}), encoding="utf-8")

    (ev / "archetype_coverage.json").write_text(json.dumps({
        "purpose": "Archetype coverage, not an estate.",
        "n_homes": 26, "n_days": 7, "n_home_days": 182,
        "max_physics_relative_residual": 7.4e-13,
        "max_energy_closure_relative_residual": 2.8e-16,
        "all_dimensions_complete": True,
        "coverage": {
            "heating_system": {"in_the_town": ["a", "b"], "exercised": ["a", "b"],
                               "missing": [], "complete": True,
                               "why_it_matters": "different code", "per_value": {}},
            "ber_letter": {"in_the_town": ["A", "G"], "exercised": ["A", "G"],
                           "missing": [], "complete": True,
                           "why_it_matters": "stiffness varies",
                           "per_value": {
                               "A": {"n_home_days": 21, "mean_heat_kwh_day": 13.72,
                                     "mean_living_temp_c": 18.3, "min_living_temp_c": 13.8},
                               "G": {"n_home_days": 14, "mean_heat_kwh_day": 74.35,
                                     "mean_living_temp_c": 16.3, "min_living_temp_c": 10.3}}},
        },
    }), encoding="utf-8")

    (ev / "heldout_comparison.json").write_text(json.dumps({
        "electricity_fossil_heated": {"n": 49, "mean_ratio": 0.591},
        "gas_space_heat": {"n": 49, "mean_ratio": 0.323},
        "gas_space_heat_by_period": {
            "1967-1999": {"n": 4, "mean_simulated_kwh_yr": 3964.0,
                          "mean_target_kwh_yr": 8799.0, "mean_ratio": 0.429},
            "2005-2023": {"n": 4, "mean_simulated_kwh_yr": 2395.8,
                          "mean_target_kwh_yr": 11851.2, "mean_ratio": 0.185},
        },
        "what_this_can_and_cannot_say": "It can say whether the fit generalises.",
    }), encoding="utf-8")

    (ev / "marginal_power_analysis.json").write_text(json.dumps({
        "statistic": "household-size marginal, 8 categories",
        "n_town_households": 1092, "n_cobh_households": 5257, "alpha": 0.05,
        "z_critical_simultaneous": 2.7344,
        "planted_shift_fraction": 0.10,
        "planted_shift_description": "10% of '1' moved to '4'",
        "planted_shift_households": 26.8,
        "deterministic_resolution": {
            "question": "q", "resolution_fraction": 0.128183,
            "resolution_households": 34.3, "planted_max_abs_z": 2.1332,
            "planted_detected": False, "verdict": "below the resolution",
        },
        "random_sample_power": {
            "question": "q", "curve": [],
            "false_positive_rate_at_zero_shift": 0.0595,
            "power_at_planted_10pc": 0.426,
            "fraction_for_80pc_power": 0.15, "fraction_for_95pc_power": 0.20,
            "n_households_for_95pc_power_at_10pc": 3664,
            "calibration_note": "n",
        },
        "generator_precision": {
            "question": "q", "across_run_sd_max": 1.687e-16,
            "n_seeds_measured": 40, "measured_in_both_arms": True,
            "multinomial_se_near_p_0p25": 0.013018,
            "ratio_band_to_generator_precision": "about 28x",
            "verdict": "deterministic",
        },
        "ensemble_check": {
            "k_minimum": 4, "k_used": 20,
            "k_minimum_derivation": "two routes agree",
            "k_used_reason": "the t band is 6.895 at K=4 against 3.074 at K=20",
            "measured_power_at_10pc_shift": 1.0,
            "measured_false_positive_rate": 0.0,
            "both_exact_not_estimated": "exact, not Monte Carlo",
            "fires_at_households": 1.5, "planted_households": 26.8,
            "margin": "about 16x",
        },
        "why_the_reference_had_to_change": {
            "literal_reading": "rejects a correct population at K>=4",
            "cause": "the declared person-total repair",
            "resolution": "two questions, two references",
            "target_vs_saps_max_abs_z": 1.9827,
            "target_vs_saps_budget": 2.7344,
            "target_vs_saps_within_budget": True,
            "target_vs_saps_delta": {},
        },
    }), encoding="utf-8")

    (ev / "control_power_audit.json").write_text(json.dumps({
        "rule": "magnitudes from a power analysis, not chosen",
        "n_controls_audited": 18, "n_deterministic": 16, "n_statistical": 2,
        "controls_below_their_resolution": [],
        "controls_with_a_margin_under_2x": ["NC-D2-04"],
        "all_adequate": True,
        "audits": [
            {"control_id": "NC-D2-04", "kind": "deterministic",
             "detected_quantity": "specific heat loss", "planted_magnitude": "7.34",
             "check_fires_at": "above 6.5 W/K/m2", "margin": "13% above",
             "margin_ratio": 1.129, "adequate": True,
             "note": "The thinnest margin, deliberately."},
            {"control_id": "NC-D2-03", "kind": "deterministic",
             "detected_quantity": "ensemble mean", "planted_magnitude": "25 households",
             "check_fires_at": "1.5 households", "margin": "16x",
             "margin_ratio": 16.3, "adequate": True, "note": ""},
            {"control_id": "T10-planted-arm", "kind": "statistical",
             "detected_quantity": "chi-square on position",
             "planted_magnitude": "44.66% share", "check_fires_at": "27.41%",
             "margin": "8.1x", "margin_ratio": 8.1, "adequate": True,
             "note": "Audited although it is a criterion."},
        ],
    }), encoding="utf-8")

    (ev / "machine.json").write_text(json.dumps({
        "machine": {"cpu_brand": "test", "memory_gb": 32, "cpu_count": 12,
                    "python": "3.12.0", "machine": "x86_64",
                    "disk_free_gb": 78.7, "disk_total_gb": 931.5},
    }), encoding="utf-8")

    (ev / "junit.xml").write_text(
        '<testsuites><testsuite tests="182" failures="0" errors="0" '
        'skipped="0" time="95.0"/></testsuites>', encoding="utf-8")

    (root / "docs" / "ISSUES.md").write_text(
        "## I-001 — A thing went wrong\n\n"
        "**Severity:** High · **Raised:** Day 1 · **Status:** Fixed\n\nbody\n",
        encoding="utf-8",
    )
    (root / "sources" / "SOURCES.md").write_text(
        "### one\nsha256: abc\n\nCER/ISSDA are deliberately absent.\n",
        encoding="utf-8",
    )
    return root


def test_report_renders_a_pass_from_passing_artefacts(tmp_path):
    root = _fixture(tmp_path)
    d = build_report(project_root=root)
    assert d["gate"] == "PASS"
    assert d["n_fail"] == 0
    assert len(d["criteria"]) == 8


def test_report_renders_failures_from_failing_artefacts(tmp_path):
    """The generator must be able to report a failure, not only a pass."""
    root = _fixture(tmp_path, failing=True)
    d = build_report(project_root=root)
    assert d["gate"] == "FAIL"
    failed = {c["criterion_id"] for c in d["criteria"] if c["verdict"] == "FAIL"}
    # Invariants, determinism, controls, the run/replay, MIMIC, SAPS.
    assert {"E1-1", "E1-2", "E1-3", "E1-5", "E1-6", "E1-4"} <= failed


def test_a_missing_artefact_is_an_error_not_a_pass(tmp_path):
    root = _fixture(tmp_path)
    (root / "v1" / "evidence" / "worker_determinism.json").unlink()
    with pytest.raises(ArtefactMissing, match="worker_determinism"):
        build_report(project_root=root)


def test_a_not_detected_control_fails_criterion_three(tmp_path):
    """Design 9.2 says EVERY negative control. Not "most"."""
    root = _fixture(tmp_path)
    ev = root / "v1" / "evidence" / "negative_controls.json"
    d = json.loads(ev.read_text())
    d["results"][1]["outcome"] = "NOT_DETECTED"
    d["results"][1]["passed"] = False
    d["n_passed"] = 1
    ev.write_text(json.dumps(d), encoding="utf-8")
    report = build_report(project_root=root)
    c3 = next(c for c in report["criteria"] if c["criterion_id"] == "E1-3")
    assert c3["verdict"] == "FAIL"
    assert "NC-X-02" in c3["measured"]
    assert report["gate"] == "FAIL"


def test_a_skipped_invariant_is_not_counted_as_a_pass(tmp_path):
    root = _fixture(tmp_path)
    report = build_report(project_root=root)
    text = (root / "docs" / "E1_gate_report.md")
    write_report(project_root=root)
    body = text.read_text(encoding="utf-8")
    assert "was not evaluated" in body
    assert "presence collected for 14 days only" in body


def test_rendered_report_carries_the_label_and_the_claim(tmp_path):
    root = _fixture(tmp_path)
    path = write_report(project_root=root)
    body = path.read_text(encoding="utf-8")
    assert body.count("UNVALIDATED SIMULATION EVIDENCE") >= 2
    assert "No behavioural calibration is claimed" in body
    # The five MIMIC counters, each named.
    for key in ("unique_synthetic_participants", "completed_sessions",
                "completed_responses", "linked_baile_nua_panel_participants",
                "unlinked_extended_pool_participants"):
        assert key in body
    # The U03 contradiction must be visible, not buried.
    assert "contradicts the design" in body.lower()
    # Every required section.
    for heading in ("Pass or fail per E1 criterion", "five MIMIC counters",
                    "scale-down methods compared", "whether the full town fits",
                    "Energy against the CSO", "held-out axis",
                    "Archetype coverage",
                    "Can each control actually fail",
                    "Negative controls", "Known failures",
                    "ISSUES.md summary", "Decisions needed for weeks 2 and 3"):
        assert heading in body, f"missing section: {heading}"


def test_issues_summary_parses_severity_and_status(tmp_path):
    root = _fixture(tmp_path)
    out = _issues_summary(root / "docs" / "ISSUES.md")
    assert out["n"] == 1
    assert out["by_severity"]["High"] == 1
    assert out["issues"][0]["status"] == "Fixed"


def test_junit_summary_reads_both_shapes(tmp_path):
    a = tmp_path / "a.xml"
    a.write_text('<testsuites><testsuite tests="3" failures="1" errors="0" '
                 'skipped="0" time="1.0"/></testsuites>', encoding="utf-8")
    assert _junit_summary(a) == {
        "tests": 3, "failures": 1, "errors": 0, "skipped": 0,
        "time_s": 1.0, "green": False,
    }
    b = tmp_path / "b.xml"
    b.write_text('<testsuite tests="2" failures="0" errors="0" skipped="1" '
                 'time="0.5"/>', encoding="utf-8")
    assert _junit_summary(b)["green"] is True


def test_no_table_row_has_an_unescaped_pipe_in_a_cell(tmp_path):
    """A bare pipe inside a cell silently breaks the markdown table.

    The SAPS criterion measured "worst |z| 2.10", which rendered as two extra
    columns and pushed the evidence link out of the table.
    """
    root = _fixture(tmp_path)
    body = write_report(project_root=root).read_text(encoding="utf-8")
    header = None
    for line in body.splitlines():
        if not line.startswith("|"):
            header = None
            continue
        n = line.count("|") - line.count("\\|")
        if header is None:
            header = n
            continue
        if set(line.replace("|", "").replace("-", "").strip()) == set():
            continue
        assert n == header, (
            f"row has {n} cell separators against the header's {header}: {line[:160]}"
        )


def test_a_missing_benchmark_key_refuses_to_render(tmp_path):
    """A gap in the benchmark must raise, not print a placeholder.

    A table cell reading "?" is indistinguishable from a measurement that is
    genuinely unknown, and the real cause - an artefact written by an older
    version of the run - is fixable by re-running it.
    """
    root = _fixture(tmp_path)
    path = root / "v1" / "run_diagnostics.json"
    d = json.loads(path.read_text())
    del d["benchmark"]["mean_write_s_per_day"]
    path.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(ArtefactMissing, match="mean_write_s_per_day"):
        write_report(project_root=root)
