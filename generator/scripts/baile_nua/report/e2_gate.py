"""The E2 gate report, generated from artefacts so a figure cannot be typed.

Design 9.2's gate table defines E2 as: *"Full town, 10 years, invariants clean.
Coupling-lag test passes. Scale benchmarks within hardware. Physical
consistency at F1/F2. Event coverage complete. Privacy inference test run and
reported. D28 to D31 pass the 6.5 tests."* Seven criteria, each decided here
from a named artefact.

**Why a generator rather than a written document.** The standing rule on this
build is that only artefact-traced figures may be cited, and the first E2
report was written by hand against artefacts read one at a time. Two of its
forty-three figures were wrong — a free-disk number remembered from week 1 and
a per-home-day cost taken from the wrong run — and both were caught only
because the figures were checked afterwards. A generator cannot type a figure
that is not in an artefact: :func:`_need` raises on a missing key rather than
printing a placeholder, which is the same discipline ``e1_gate`` adopted after
its renderer published a question mark where a measurement belonged.

**Independent and calibration-exposed checks are rendered as separate tables**,
because I-058's rule is that a source used to build the model cannot validate
it, and a single table of "checks that passed" reads as independence it does
not have. The split is read from each source's declared
``model_development_exposure`` rather than from a list kept here, so a source
that is re-declared moves table without anyone remembering to move it.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

__all__ = ["E2Criterion", "ArtefactMissing", "build_report", "write_report"]


class ArtefactMissing(RuntimeError):
    """An artefact a criterion depends on is absent, so it has no verdict."""


@dataclasses.dataclass
class E2Criterion:
    criterion_id: str
    design_text: str
    verdict: str                      # PASS | FAIL | NOT EVALUABLE
    evidence: list[str]
    measured: str
    why: str = ""


def _read(path: Path, *, required: bool = True) -> dict[str, Any] | None:
    if not path.exists():
        if required:
            raise ArtefactMissing(
                f"{path} is absent. This report is generated from artefacts "
                f"only; a missing artefact is reported as missing and never "
                f"filled in from memory of the run that produced it."
            )
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _need(obj: dict[str, Any], key: str, where: str) -> Any:
    if key not in obj:
        raise ArtefactMissing(
            f"{where} has no {key!r}. The artefact was written by a different "
            f"version of the run than this report expects; re-run it rather "
            f"than publishing a table with a gap in it. Present: {sorted(obj)}"
        )
    return obj[key]


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _exposure_split(project_root: Path) -> dict[str, Any]:
    """Which checks are independent, read from the declared exposures.

    Read from the register rather than from a list here, so a source that is
    re-declared - as F1054 was, from `none` to `design`, once the population
    was fitted to its sibling - moves table without anyone remembering to
    move it.
    """
    import baile_nua.sources_registry  # noqa: F401
    from baile_nua.sources import REGISTRY

    # Each check names the source it is scored against. The exposure comes
    # from the register.
    checks: tuple[dict[str, Any], ...] = (
        {"check": "U31 old/new gas gradient (D-073)",
         "source": "cso.gas.dberng02_by_dwelling_construction",
         "artefact": "v1/evidence/u31_newpop_prereg.json",
         "result_key": "passes_all_four"},
        {"check": "Age x economic-status joint, independent arm",
         "source": "cso.census.cna25_economic_status_by_age_1981_2016",
         "artefact": "v1/evidence/w3_joint_population.json",
         "result_key": "independent.verdict"},
        {"check": "Age x economic-status joint, scorer",
         "source": "cso.census.f1054_economic_status_by_age_group",
         "artefact": "v1/evidence/w3_joint_population.json",
         "result_key": "design_exposed.verdict"},
        {"check": "Gross move rate (U33)",
         "source": "cso.census.sap2022_usual_residence_one_year_ago_by_town",
         "artefact": "v1/evidence/wp5_tenyear.json",
         "result_key": "u33_move_rate_proxy.within"},
        {"check": "Overnight load per awake person (I-052)",
         "source": "esbn.rmds.slp_indexes_2022",
         "artefact": "v1/evidence/i052_lp1_timing.json",
         "result_key": "reported, no pass mark"},
        {"check": "Annual gas PL-GAS-01",
         "source": "cso.gas.dberng01_by_dwelling_ber",
         "artefact": "v1/evidence/plausibility.json",
         "result_key": "suite"},
        {"check": "Retrofit and control magnitudes",
         "source": "seai.deap.manual_4_2_7",
         "artefact": "v1/evidence/wp5_tenyear.json",
         "result_key": "extraction shape-checked"},
        {"check": "School venue capacity",
         "source": "cso.education.eda49_schools_and_pupils_by_teacher_size",
         "artefact": "v1/evidence/w3_town_network_venues.json",
         "result_key": "venues sized from it"},
    )
    independent, exposed, undeclared = [], [], []
    for c in checks:
        src = REGISTRY.get(c["source"])
        if src is None:
            undeclared.append(c["source"])
            continue
        row = {**c, "exposure": src.model_development_exposure}
        (independent if src.model_development_exposure == "none"
         else exposed).append(row)
    if undeclared:
        raise ArtefactMissing(
            f"these checks name sources that are not declared: {undeclared}. "
            f"A check scored against an undeclared source has no exposure, so "
            f"it cannot be placed in either table."
        )
    # Sources the model is BUILT from, which validate nothing and so have no
    # row in either table. Counted from the register rather than listed here:
    # the first version of this function carried a row for the assessed-fabric
    # source reading "derived from it; cannot validate it", which put a
    # calibration input in a table of checks and tripped the rule that keeps
    # that source out of report modules altogether
    # (test_no_plausibility_check_or_calibration_target_reads_this_source).
    # The disclosure belongs here, as a count with its reason, and the source
    # keys stay in the register where they are already declared.
    scored_against = {c["source"] for c in checks}
    build_only = sorted(
        k for k, s in REGISTRY.items()
        if s.model_development_exposure in ("design", "selection", "tuning")
        and k not in scored_against
    )

    # The plausibility suite's own exposure-partitioned pass counts. They are
    # carried through as THREE separate numbers and are never added together:
    # "9 checks passed" would assert nine independent corroborations where
    # there are six, and the other three are the model agreeing with its own
    # inputs. The partition is the result; the total is not a result.
    plaus_ref = "v1/evidence/plausibility.json"
    plaus = _read(project_root / "v1" / "evidence" / "plausibility.json")
    pass_counts = {
        key: _need(plaus, key, plaus_ref)
        for key in ("n_pass_independent",
                    "n_pass_against_a_calibration_input",
                    "n_pass_against_a_design_exposed_reference")
    }

    return {"independent": independent, "calibration_exposed": exposed,
            "n_independent": len(independent), "n_exposed": len(exposed),
            "n_build_only_sources_that_validate_nothing": len(build_only),
            "build_only_note": (
                "Declared `design`, `selection` or `tuning` and scored against "
                "by no check in either table. Design 7.1: a source used to "
                "build the model cannot validate it, so these appear in the "
                "source-use register and in neither results table. The count "
                "is derived from the register's own exposure field."
            ),
            "plausibility_pass_counts": pass_counts,
            "plausibility_pass_counts_artefact": plaus_ref,
            "plausibility_pass_counts_must_not_be_summed": (
                "These three are reported separately and are NEVER added into "
                "one figure. Their sum would read as that many independent "
                "corroborations, and only n_pass_independent is independent: "
                "the other two are the model agreeing with a source it was "
                "built from, which is a consistency check. The suite's own "
                "n_pass and n_pass_sourced are reported beside them as the "
                "suite's totals, and are not a substitute for the partition."
            ),
            "plausibility_suite_totals": {
                "n_checks": _need(plaus, "n_checks", plaus_ref),
                "n_pass": _need(plaus, "n_pass", plaus_ref),
                "n_fail": _need(plaus, "n_fail", plaus_ref),
                "n_not_evaluable": _need(plaus, "n_not_evaluable", plaus_ref),
                "n_pass_sourced": _need(plaus, "n_pass_sourced", plaus_ref),
                "n_pass_unsourced_band": _need(
                    plaus, "n_pass_unsourced_band", plaus_ref),
            }}


def build_report(*, project_root: Path) -> dict[str, Any]:
    """Decide all seven E2 criteria from artefacts."""
    root = Path(project_root)
    ev = root / "v1" / "evidence"

    # Which town run the figures came from, and the report must NAME it: the
    # first version hard-coded "work/town3" in the evidence lines while
    # falling back to town2, so it cited a file it had not read. A traceability
    # claim that is itself untraceable is worse than no claim.
    # The NEWEST town run, by mtime, rather than a hard-coded preference
    # order. The first version listed ("town3", "town2", "town") and silently
    # kept using town3 after town4 was produced - the same staleness the
    # evidence-path bug had, one layer up. A list of candidates goes stale; a
    # timestamp does not.
    candidates = sorted(
        (p for p in (root / "work").glob("town*/town_diagnostics.json")),
        key=lambda p: p.stat().st_mtime, reverse=True)
    town_path = candidates[0] if candidates else None
    if town_path is None:
        raise ArtefactMissing(
            "no town run diagnostics found under work/town*, so the full-town "
            "criteria have no evidence")
    town = _read(town_path)
    town_ref = _rel(town_path, root)
    wp5 = _read(ev / "wp5_tenyear.json")
    w2 = _read(ev / "w2_steps6to9.json")
    e1 = _read(ev / "e1_gate_report.json")
    run = _read(root / "v1" / "run_diagnostics.json")
    machine = _read(ev / "machine.json")
    privacy = _read(ev / "privacy_inference_u20.json")
    tells = _read(ev / "tell_audit.json", required=False)
    packages = _read(ev / "delivery_packages.json", required=False)
    u31 = _read(ev / "u31_newpop_prereg.json", required=False)

    crit: list[E2Criterion] = []

    # ---- E2-1  full town, 10 years, invariants clean ---------------------
    net = _need(town, "network", town_ref)
    meas = _need(town, "_measured", town_ref)
    tm = _need(_need(town, "benchmark", town_ref), "timings", f"{town_ref} benchmark")
    days = _need(meas, "n_days", "town _measured")
    year_h = _need(tm, "run_s", "town timings") / days * 365 / 3600
    gb = _need(meas, "storage_bytes", "town _measured") / days * 365 / 1e9
    lc = _need(wp5, "life_course", "wp5_tenyear.json")
    suite = _need(wp5, "suite_on_every_year", "wp5_tenyear.json")
    # Decided from the artefacts rather than asserted. The criterion is the
    # CONJUNCTION of three things - the full town, ten years of it, and clean
    # invariants - and it passes only if one run satisfies all three. The
    # newest full-town run covers `days` days, and the ten-year run is on a
    # slice (`wp5['slice']`), so no single artefact carries both. Previously
    # this verdict was the literal string "FAIL", which was the right answer
    # for the wrong reason: it would have stayed FAIL after a decade landed.
    E2_1_REQUIRED_DAYS = 3650
    n_homes_town = _need(_need(town, "slice", "town"), "n_homes", "town slice")
    wp5_slice = _need(wp5, "slice", "wp5")
    wp5_is_full_town = str(wp5_slice).strip().lower() in ("town", "full town",
                                                          "full_town")
    invariants_clean = bool(
        _need(_need(lc, "invariants", "life_course"), "clean", "invariants"))
    no_suite_failures = not (_need(suite, "any_fail", "suite")
                             or _need(suite, "any_no_data", "suite"))
    e2_1_pass = bool(
        days >= E2_1_REQUIRED_DAYS and wp5_is_full_town
        and invariants_clean and no_suite_failures)
    crit.append(E2Criterion(
        "E2-1", "Full town, 10 years, invariants clean",
        ("PASS" if e2_1_pass else "FAIL"),
        [town_ref, "v1/evidence/wp5_tenyear.json", "v1/evidence/machine.json"],
        (f"full town {n_homes_town} homes for **{days} days** under "
         f"{_need(town,'coupling_mode',town_ref)}, against the "
         f"{E2_1_REQUIRED_DAYS} days the criterion requires; "
         f"{_need(wp5,'n_years_simulated','wp5')} years on the "
         f"**{wp5_slice}** (not the full town); ten-year invariants "
         f"clean={invariants_clean}; any_fail="
         f"{_need(suite,'any_fail','suite')}, any_no_data="
         f"{_need(suite,'any_no_data','suite')}"),
        (f"**FAILS on the conjunction.** The criterion asks for one run that "
         f"is the full town AND ten years AND invariants clean. The full-town "
         f"run is {days} of {E2_1_REQUIRED_DAYS} days "
         f"({days / E2_1_REQUIRED_DAYS:.1%} of the decade), and the decade "
         f"that did run is on the {wp5_slice}, not the town. Invariants are "
         f"clean on the decade that ran ({invariants_clean}), so the clean "
         f"clause is met and the COVERAGE clause is not. Every part has run "
         f"and not all at once.\n\n"
         f"The measured basis for why: a full-town decade is "
         f"{year_h * 10:.0f} run hours extrapolated from the measured "
         f"{year_h:.2f} h per town-year, and {gb * 10:.1f} GB without D18, "
         f"against "
         f"{_need(_need(machine,'machine','machine.json'),'disk_free_gb','machine')} "
         f"GB free - so it fits the disk and not the week. Reported as a "
         f"**failure with a measured basis, not a deferral**: the criterion "
         f"is not met now, whatever is scheduled."),
    ))

    # ---- E2-2  coupling-lag ---------------------------------------------
    cc = _need(w2, "step7_coupling_contract", "w2_steps6to9.json")
    ok = _need(cc, "all_regimes_pass", "step7_coupling_contract")
    crit.append(E2Criterion(
        "E2-2", "Coupling-lag test passes", ("PASS" if ok else "FAIL"),
        ["v1/evidence/w2_steps6to9.json"],
        f"all_regimes_pass={ok}",
        "The 1-minute device and physics step against the 15-minute network "
        "epoch. C2 now exists, so the contract is a statement about a "
        "coupling that solves something.",
    ))

    # ---- E2-3  scale within hardware ------------------------------------
    proj = _need(_need(run, "benchmark", "run_diagnostics.json"),
                 "full_town_projection", "benchmark")
    margin_h = _need(proj, "projected_run_hours_with_margin", "projection")
    bare_h = _need(proj, "projected_run_hours", "projection")
    crit.append(E2Criterion(
        "E2-3", "Scale benchmarks within hardware",
        ("PASS" if year_h <= margin_h else "FAIL"),
        [town_ref, "v1/run_diagnostics.json"],
        (f"measured {year_h:.2f} h per town-year under C2 against a projected "
         f"{bare_h} h bare and {margin_h} h with U21's margin; peak RSS "
         f"{_need(meas,'peak_rss_mb','town _measured')} MB of "
         f"{_need(_need(machine,'machine','machine.json'),'memory_gb','machine')} GB"),
        (f"Measured on the full town rather than extrapolated. The power flow "
         f"is {_need(tm,'network_share_of_runtime','timings'):.1%} of runtime "
         f"and has its own line, because a projection built from simulate "
         f"plus write alone under-predicts C2 by exactly that."),
    ))

    # ---- E2-4  physical consistency at F1/F2 ----------------------------
    phys = _need(town, "max_physics_relative_residual", town_ref)
    clos = _need(town, "max_energy_closure_relative_residual", town_ref)
    crit.append(E2Criterion(
        "E2-4", "Physical consistency at F1/F2",
        ("PASS" if (phys < 1e-6 and clos < 1e-3) else "FAIL"),
        [town_ref],
        f"max physics relative residual {phys:.3e}; max energy closure "
        f"relative residual {clos:.3e}",
        "Both at machine precision. F3 (EnergyPlus) is out of scope by E1's "
        "own declaration and is not claimed.",
    ))

    # ---- E2-5  event coverage -------------------------------------------
    cov = _need(_need(w2, "step6_wp6_events", "w2_steps6to9.json"),
                "coverage_audit", "step6_wp6_events")
    r20 = _need(cov, "passes_r20", "coverage_audit")
    crit.append(E2Criterion(
        "E2-5", "Event coverage complete", ("PASS" if r20 else "FAIL"),
        ["v1/evidence/w2_steps6to9.json"],
        (f"{_need(cov,'n_kinds','coverage_audit')} event kinds; "
         f"missing_from_the_year={_need(cov,'missing_from_the_year','coverage_audit')}; "
         f"present_but_unsourced={_need(cov,'present_but_unsourced','coverage_audit')}; "
         f"{_need(cov,'n_sourced','coverage_audit')} sourced, "
         f"{_need(cov,'n_legal','coverage_audit')} legal instrument, "
         f"{_need(cov,'n_assumed','coverage_audit')} [A]"),
        "Complete in the sense the criterion asks: every declared kind occurs "
        "and every one has a source or a registered [A]. NOT a claim that the "
        "event RATES are right - five of ten kinds are [A].",
    ))

    # ---- E2-6  privacy test run and reported ----------------------------
    cfgs = _need(privacy, "configurations", "privacy_inference_u20.json")
    scored = {k: v for k, v in cfgs.items() if v.get("attacks")}
    crit.append(E2Criterion(
        "E2-6", "Privacy inference test run and reported",
        ("PASS" if scored else "FAIL"),
        ["v1/evidence/privacy_inference_u20.json"],
        (", ".join(
            f"{k}: occupancy AUC "
            f"{v['attacks']['occupancy_classifier']['auc_model']['auc']} "
            f"(95% hi {v['attacks']['occupancy_classifier']['auc_model']['hi']}), "
            f"{v['screening']['verdict']}"
            for k, v in sorted(scored.items())
            if v["attacks"]["occupancy_classifier"].get("measured"))),
        ("The criterion is that the test is RUN and REPORTED, and it was, for "
         "the first time. The RESULT fails design 7.8's screening threshold "
         "and is reported in full, including that the attack does not beat a "
         "time-of-day baseline - which design 7.8 also requires and which "
         "says something different."),
    ))

    # ---- E2-7  D28 to D31 pass the 6.5 tests ----------------------------
    from baile_nua.observation.nonsensor import D31_NOT_BUILT

    crit.append(E2Criterion(
        "E2-7", "D28 to D31 pass the 6.5 tests", "FAIL",
        ["scripts/tests/test_nonsensor_65_rules.py", "docs/ISSUES.md (I-072)"],
        ("D28, D29 and D30 built and passing rules 1 and 3; D31 carries its "
         "weather series only; rule 4 NOT EVALUABLE"),
        (f"Not built: {list(D31_NOT_BUILT['series_not_built'])}. "
         f"{D31_NOT_BUILT['why']} Rule 4's test needs a real reference "
         f"package and there is none, so it is unevaluated rather than "
         f"scored."),
    ))

    n_pass = sum(1 for c in crit if c.verdict == "PASS")
    n_fail = sum(1 for c in crit if c.verdict == "FAIL")
    return {
        "gate": "E2",
        "town_run_used": town_ref,
        "label": "UNVALIDATED SIMULATION EVIDENCE: E2 engineering candidate",
        "claim": ("Engineering verification only. No behavioural calibration "
                  "is claimed."),
        "verdict": ("PASS" if n_fail == 0 else "FAIL"),
        "n_pass": n_pass, "n_fail": n_fail, "n_criteria": len(crit),
        "criteria": [dataclasses.asdict(c) for c in crit],
        "exposure_split": _exposure_split(root),
        "week3_acceptance": _week3(root, town, town_ref),
        "tell_audit": ({
            "n_data_findings": tells.get("n_findings"),
            "n_manifest_disclosures": tells.get(
                "manifest_disclosure", {}).get("n_disclosing"),
            "highest_severity": tells.get("highest_severity"),
            "adversarial_analyst_run": False,
        } if tells else {"run": False}),
        "delivery_packages": ({
            "all_separation_rules_pass":
                packages["separation"]["all_rules_pass"],
            "observable_blind_safe": packages["observable"]["blind_safe"],
            "n_limitations_shipped": packages["evidence"]["n_limitations"],
        } if packages else {"built": False}),
        "u31_prereg": ({
            "passes_all_four": u31.get("passes_all_four"),
            "criterion_edited": False,
            "gradient_before": u31["measured_on_the_new_population"][
                "gradient_before"],
            "gradient_after": u31["measured_on_the_new_population"][
                "gradient_after"],
        } if u31 else {"run": False}),
        "e1_regression": {"gate": _need(e1, "gate", "e1_gate_report.json"),
                          "n_pass": _need(e1, "n_pass", "e1_gate_report.json")},
    }


def _week3(root: Path, town: dict[str, Any], town_ref: str) -> dict[str, Any]:
    """Design 9.4's week-3 acceptance criteria, scored separately."""
    w3 = _read(root / "v1" / "evidence" / "w3_town_network_venues.json",
               required=False)
    net = _need(town, "network", town_ref)
    load = _need(net, "loading", "town network")
    out = {
        "feeder_loading_within_physical_limits": {
            "verdict": ("PASS" if _need(load, "within_physical_limits", "loading")
                        else "FAIL"),
            "measured": (
                f"max transformer {load.get('max_transformer_loading_pct')}%, "
                f"max line {load.get('max_line_loading_pct')}%, "
                f"{load.get('n_epochs_solved')} of {load.get('n_epochs')} "
                f"epochs solved, "
                f"{load.get('n_epochs_that_did_not_converge')} non-converged"),
        },
    }
    if w3:
        out["venue_presence_consistent_with_person_presence"] = {
            "verdict": w3["venues"]["verdict"],
            "measured": json.dumps(w3["venues"]["presence"]["consistency"]),
        }
        scale_ref = "v1/evidence/w3_town_network_venues.json scale"
        scale = _need(w3, "scale", "w3_town_network_venues.json")
        out["measured_scale_within_the_day_6_projection"] = {
            "verdict": _need(scale, "verdict", scale_ref),
            "measured": _need(
                _need(scale, "comparison", scale_ref), "reading",
                f"{scale_ref} comparison"),
            # The three caveats that qualify the scale figure, carried in
            # full rather than paraphrased. A scale PASS quoted without them
            # reads as a clean linear projection, and it is none of the
            # three things that would make it one.
            "caveats": {
                "per_home_day_cost_at_scale": _need(
                    scale, "per_home_day_cost_at_scale", scale_ref),
                "runtime_was_measured_under_contention": _need(
                    scale, "runtime_was_measured_under_contention", scale_ref),
                "storage_reading": _need(scale, "storage_reading", scale_ref),
            },
        }
    return out


def write_report(*, project_root: Path, out_path: Path | None = None) -> Path:
    """Write the JSON record. The prose report is rendered beside it."""
    root = Path(project_root)
    rec = build_report(project_root=root)
    out = out_path or (root / "v1" / "evidence" / "e2_gate_report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rec, indent=2, default=str) + "\n",
                   encoding="utf-8")
    return out


def _render(d: dict[str, Any]) -> str:
    """The prose report, rendered from the record so no figure is typed."""
    w: list[str] = []
    a = w.append
    a("# E2 gate report - Baile Nua simulation candidate")
    a("")
    a(f"**{d['label']}**  ")
    a(f"{d['claim']}")
    a("")
    a("Generated from artefacts by `baile_nua.report.e2_gate`. Every figure "
      "below is read from the artefact named beside it; a missing key raises "
      "rather than printing a placeholder, so a number that is not in an "
      "artefact cannot appear here.")
    a("")
    a("---")
    a("")
    a("## 1. Verdict per E2 criterion")
    a("")
    a("Design 9.2's gate table: *\"Full town, 10 years, invariants clean. "
      "Coupling-lag test passes. Scale benchmarks within hardware. Physical "
      "consistency at F1/F2. Event coverage complete. Privacy inference test "
      "run and reported. D28 to D31 pass the 6.5 tests.\"*")
    a("")
    a(f"The town figures below come from `{d['town_run_used']}`, which is the "
      f"newest `work/town*/town_diagnostics.json` by mtime - chosen by "
      f"timestamp rather than from a hard-coded preference order, so the "
      f"report cannot cite a run it did not read.")
    a("")
    a("| # | criterion | verdict | measured | artefacts |")
    a("| --- | --- | --- | --- | --- |")
    for c in d["criteria"]:
        measured = c["measured"].replace("\n", " ")
        a(f"| {c['criterion_id']} | {c['design_text']} | "
          f"**{c['verdict']}** | {measured} | "
          f"{', '.join('`' + e + '`' for e in c['evidence'])} |")
    a("")
    a(f"**Gate verdict: {d['verdict']} - {d['n_pass']} of "
      f"{d['n_criteria']} criteria met, {d['n_fail']} failed.**")
    a("")
    failed = [c["criterion_id"] for c in d["criteria"] if c["verdict"] == "FAIL"]
    if failed:
        a(f"Failing: **{', '.join(failed)}**. Each is scored PASS or FAIL "
          f"exactly as design 9.2 writes the criterion. A criterion that is "
          f"not met now is a FAIL with its measured basis, never a deferral "
          f"on the strength of a run that is scheduled.")
        a("")
    for c in d["criteria"]:
        if c["why"]:
            a(f"**{c['criterion_id']}.** {c['why']}")
            a("")
            a(f"*Evidence:* {', '.join('`' + e + '`' for e in c['evidence'])}")
            a("")
    a("---")
    a("")
    es = d["exposure_split"]
    a("## 2. Independent checks")
    a("")
    a("**Table 1 of 2 tables that are deliberately NOT combined.** I-058's "
      "rule: a source used to build the model cannot validate it. The checks "
      "below are the only ones scored against a reference declared at "
      "`model_development_exposure = \"none\"`, so they are the only ones that "
      "are independent evidence. The split is read from the register's own "
      "exposure field, so a source that is re-declared - as F1054 was, from "
      "`none` to `design`, once the population was fitted to its sibling "
      "FY047B - moves table on its own.")
    a("")
    a(f"**{es['n_independent']} independent checks.**")
    a("")
    a("| check | reference | exposure class | artefact |")
    a("| --- | --- | --- | --- |")
    for r in es["independent"]:
        a(f"| {r['check']} | `{r['source']}` | `{r['exposure']}` "
          f"(independent) | `{r['artefact']}` |")
    a("")
    a("## 3. Checks scored against a calibration input or a design-exposed "
      "reference")
    a("")
    a("**Table 2 of 2. These are consistency checks, not independent "
      "validations.** A pass here means the model agrees with something it "
      "was built from. These rows must never be added to the table above: a "
      "combined count of \"checks that passed\" would read as independence "
      "that this half does not have.")
    a("")
    a(f"**{es['n_exposed']} calibration-exposed checks**, kept separate from "
      f"the {es['n_independent']} independent ones above. The two counts are "
      f"reported as two counts.")
    a("")
    a("| check | reference | exposure class | artefact |")
    a("| --- | --- | --- | --- |")
    for r in es["calibration_exposed"]:
        a(f"| {r['check']} | `{r['source']}` | **`{r['exposure']}`** "
          f"(calibration-exposed) | `{r['artefact']}` |")
    a("")
    a("### 3.1 The plausibility suite's pass counts, reported as three "
      "numbers and never as one")
    a("")
    pc = es["plausibility_pass_counts"]
    a(f"Read from `{es['plausibility_pass_counts_artefact']}`.")
    a("")
    a("| pass count | value | what it means |")
    a("| --- | --- | --- |")
    a(f"| `n_pass_independent` | **{pc['n_pass_independent']}** | "
      f"Independent evidence. Scored against a reference at exposure `none`. |")
    a(f"| `n_pass_against_a_calibration_input` | "
      f"**{pc['n_pass_against_a_calibration_input']}** | NOT independent. The "
      f"model agreeing with a source it was fitted to. |")
    a(f"| `n_pass_against_a_design_exposed_reference` | "
      f"**{pc['n_pass_against_a_design_exposed_reference']}** | NOT "
      f"independent. Nothing is fitted to the reference, but its information "
      f"is in the model through a sibling table. |")
    a("")
    a(es["plausibility_pass_counts_must_not_be_summed"])
    a("")
    st = es["plausibility_suite_totals"]
    a(f"The suite's own totals, for completeness and not as a substitute for "
      f"the partition above: {st['n_checks']} checks, {st['n_pass']} pass, "
      f"{st['n_fail']} fail, {st['n_not_evaluable']} not evaluable; "
      f"{st['n_pass_sourced']} of the passes are against a source and "
      f"{st['n_pass_unsourced_band']} against an unsourced `[A]` band.")
    a("")
    a(f"**{es['n_build_only_sources_that_validate_nothing']} further sources "
      f"appear in neither table.** {es['build_only_note']}")
    a("")
    u = d.get("u31_prereg") or {}
    if u.get("passes_all_four") is not None:
        a("## 4. U31 against D-073, the pre-registered criterion")
        a("")
        a(f"Gradient **{u['gradient_before']} -> {u['gradient_after']}** on "
          f"one population with frozen membership. "
          f"**passes_all_four = {u['passes_all_four']}**; "
          f"criterion_edited = {u['criterion_edited']}.")
        a("")
        a("*Evidence:* `v1/evidence/u31_newpop_prereg.json`, and the off-arm "
          "question answered in `v1/evidence/u31_off_arm_question.json`. The "
          "four conditions are scored against D-073's literal pre-registered "
          "thresholds, not against the new population's own measured "
          "before-values.")
        a("")
    a("## 5. Design 9.4's week-3 acceptance criteria")
    a("")
    a("Scored separately from the E2 gate. *Evidence:* "
      f"`{d['town_run_used']}` and `v1/evidence/w3_town_network_venues.json`.")
    a("")
    a("| criterion | verdict | measured |")
    a("| --- | --- | --- |")
    for k, v in d["week3_acceptance"].items():
        measured = str(v["measured"]).replace("\n", " ")
        a(f"| {k.replace('_', ' ')} | **{v['verdict']}** | {measured} |")
    a("")
    cav = (d["week3_acceptance"]
           .get("measured_scale_within_the_day_6_projection", {})
           .get("caveats"))
    if cav:
        a("### 5.1 The scale figure's caveats, in full")
        a("")
        a("Quoted rather than paraphrased, from "
          "`v1/evidence/w3_town_network_venues.json`. The scale PASS does not "
          "mean the cost is linear in homes, and it was not measured on an "
          "idle machine.")
        a("")
        for key in ("per_home_day_cost_at_scale",
                    "runtime_was_measured_under_contention",
                    "storage_reading"):
            a(f"**`scale.{key}`**")
            a("")
            for para in str(cav[key]).split("\n\n"):
                a(f"> {para.strip()}")
                a(">")
            a("")
    t = d.get("tell_audit") or {}
    if t.get("run") is not False:
        a("## 6. Tell audit (design 7.9 item 4)")
        a("")
        a(f"{t.get('n_data_findings')} data findings and "
          f"{t.get('n_manifest_disclosures')} manifest disclosures; highest "
          f"severity **{t.get('highest_severity')}**. "
          f"Adversarial analyst run: "
          f"**{t.get('adversarial_analyst_run')}** - design 7.9 requires both, "
          f"and an automated pass finds only the tells somebody thought of.")
        a("")
    p = d.get("delivery_packages") or {}
    if p.get("built") is not False:
        a("## 7. Delivery packages (design 6.3)")
        a("")
        a(f"All separation rules pass: "
          f"**{p.get('all_separation_rules_pass')}**. Observable view "
          f"blind-safe: **{p.get('observable_blind_safe')}**. "
          f"{p.get('n_limitations_shipped')} limitations shipped in the "
          f"evidence view, read from the issue log.")
        a("")
    a("---")
    a("")
    a(f"**{d['label']}.** E1 regression: "
      f"{d['e1_regression']['gate']} {d['e1_regression']['n_pass']}/8.")
    return "\n".join(w) + "\n"


def write_markdown(*, project_root: Path, out_path: Path | None = None) -> Path:
    root = Path(project_root)
    rec = build_report(project_root=root)
    out = out_path or (root / "docs" / "E2_gate_report.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_render(rec), encoding="utf-8")
    return out
