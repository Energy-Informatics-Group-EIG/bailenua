"""Command line entry points.

    baile-nua schema check            validate datasets.yaml and print a summary
    baile-nua schema dict  PATH       write the data dictionary
    baile-nua mimic diff              the day-1 schema diff against MIMIC 1.1
    baile-nua mimic verify            re-read the MIMIC tree and check for drift
    baile-nua mimic provision         create the LOCAL-ONLY MIMIC copy
    baile-nua controls run  PATH      run every negative control, write the artefact
    baile-nua scope show              print the approved E1 scope
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from baile_nua import CLAIM, LABEL, __version__

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MIMIC_ROOT = os.environ.get(
    "BAILE_NUA_MIMIC_ROOT", "/Users/brianoregan/Documents/GitHub/mimic"
)


def _banner() -> None:
    print(f"baile-nua {__version__}")
    print(LABEL)
    print(CLAIM)
    print()


# --------------------------------------------------------------------------- #

def cmd_schema_check(_args) -> int:
    from baile_nua.schema import load
    from baile_nua.schema.access import gt_field_names, obs_field_names

    s = load()
    print(f"schema {s.schema_version}, design revision {s.design_revision} (frozen {s.design_frozen})")
    print(f"datasets: {len(s.datasets)}  fields: {sum(len(d.fields) for d in s.datasets.values())}")
    for cls in ("GT", "OBS", "META"):
        ids = sorted(s.by_access(cls))
        print(f"  {cls:<4} {len(ids):>2}  {' '.join(ids)}")
    print(f"GT field names: {len(gt_field_names(s))}   OBS field names: {len(obs_field_names(s))}")
    print("schema OK")
    return 0


def cmd_schema_dict(args) -> int:
    from baile_nua import docgen

    p = docgen.write(args.path)
    print(f"wrote {p} ({p.stat().st_size:,} bytes)")
    return 0


def cmd_mimic_diff(_args) -> int:
    from baile_nua.mimic.crosswalk import schema_diff

    d = schema_diff()
    print(json.dumps(d, indent=2, ensure_ascii=False))
    clean = not d["unmapped_mimic_fields"] and not d["unknown_hrsd_fields"]
    print()
    print(f"day-1 acceptance (schema diff lists only the U18 gaps): {'PASS' if clean else 'FAIL'}")
    return 0 if clean else 1


def cmd_mimic_verify(args) -> int:
    from baile_nua.mimic.crosswalk import MimicDriftError, verify_against_mimic_source

    try:
        f = verify_against_mimic_source(args.mimic_root)
    except MimicDriftError as exc:
        print(f"DRIFT: {exc}", file=sys.stderr)
        return 1
    for k, v in f["checks"].items():
        print(f"  {'OK  ' if v else 'FAIL'} {k}")
    for d in f["defects"]:
        print(f"\nDEFECT {d['id']} in {d['file']}\n  {d['summary']}\n  action: {d['action']}")
    return 0


def cmd_mimic_provision(args) -> int:
    from baile_nua.mimic.provision import provision

    info = provision(Path(args.mimic_root), PROJECT_ROOT / "work" / "mimic_local")
    print(json.dumps(info, indent=2))
    return 0


def cmd_controls_run(args) -> int:
    import baile_nua.sources_registry  # noqa: F401
    from baile_nua.validation.negative_control import import_all_controls, run_all

    # Discovery, so the CLI and the test suite cannot disagree about which
    # controls exist.
    import_all_controls()

    results = run_all(write_to=Path(args.path) if args.path else None)
    for r in results:
        print(f"{r.control_id}  {r.outcome:<20} {r.title}")
        if not r.passed:
            print(f"    expected: {r.expected}")
            print(f"    observed: {r.observed}")
            print(f"    detail  : {r.detail}")
    n_pass = sum(r.passed for r in results)
    print(f"\n{n_pass}/{len(results)} negative controls failed for their declared reason")
    return 0 if n_pass == len(results) else 1


def cmd_sources_fetch(args) -> int:
    import baile_nua.sources_registry  # noqa: F401
    from baile_nua.sources import REGISTRY, fetch, write_register

    ok = fail = 0
    for key, src in REGISTRY.items():
        try:
            m = fetch(src, timeout=600)
            ok += 1
            print(f"OK   {key:<36} {m['bytes']:>12,} B  {m['sha256'][:12]}")
        except Exception as exc:  # noqa: BLE001
            fail += 1
            print(f"FAIL {key:<36} {type(exc).__name__}: {str(exc)[:80]}")
    print(f"\n{ok} retrieved, {fail} failed")
    print("register:", write_register())
    return 0 if fail == 0 else 1


def cmd_sources_register(_args) -> int:
    import baile_nua.sources_registry  # noqa: F401
    from baile_nua.sources import write_register

    print("register:", write_register())
    return 0


def cmd_population_t0(args) -> int:
    import json

    from baile_nua.population.synthesise import synthesise_t0, write_t0

    pop = synthesise_t0(master_seed=args.seed, method=args.method)
    d = {k: v for k, v in pop.diagnostics.items() if k != "trait_within_between"}
    print(json.dumps(d, indent=2, default=str))
    if args.write:
        for key, path in sorted(write_t0(pop, PROJECT_ROOT).items()):
            print(f"wrote {key}: {path}")
    return 0



def cmd_e1_run(args) -> int:
    """The E1 estate run: one year, every layer, streamed to v1/."""
    import baile_nua.sources_registry  # noqa: F401
    from baile_nua.engine.e1_run import run_year

    out_root = Path(args.out) if args.out else PROJECT_ROOT / "v1"
    if args.days is not None and out_root == PROJECT_ROOT / "v1":
        # A smoke run must not overwrite the delivered package. This cost
        # three separate debugging detours: `--days 3` left a three-day
        # package in v1/ and every check needing a full year then reported
        # NO_DATA, which looks like a regression and is not one.
        raise SystemExit(
            "refusing to write a --days run to v1/: that would replace the "
            "delivered year with a partial package, and every annual check "
            "would report NO_DATA. Pass --out work/smoke (or any other path) "
            "for a smoke run, or drop --days for the real one."
        )
    d = run_year(
        master_seed=args.seed,
        out_root=out_root,
        checkpoint_root=(
            PROJECT_ROOT / "work" / "checkpoints"
            / ("e1_year" if args.out is None else f"smoke_{Path(args.out).name}")
        ),
        days=args.days,
        collect_presence_days=args.presence_days,
        progress=lambda m: print(m, flush=True),
    )
    print(json.dumps(d["benchmark"]["full_town_projection"], indent=2))
    return 0


def cmd_e1_invariants(args) -> int:
    from baile_nua.validation.e1_invariants import run_v0_invariants

    out = run_v0_invariants(
        release_root=PROJECT_ROOT / "v1",
        diagnostics_path=PROJECT_ROOT / "v1" / "run_diagnostics.json",
        write_to=PROJECT_ROOT / "v1" / "evidence" / "v0_invariants.json",
    )
    for inv in out["invariants"]:
        print(f"{inv['status']:<8} {inv['invariant']}  "
              f"({inv['n_violations']} violations in {inv['n_checked']} checked)")
        if inv["skipped_reason"]:
            print(f"         reason: {inv['skipped_reason']}")
    print(f"\nzero_failures={out['zero_failures']}  "
          f"pass={out['n_pass']} fail={out['n_fail']} skipped={out['n_skipped']}")
    return 0 if out["zero_failures"] else 1


def cmd_e1_determinism(args) -> int:
    from baile_nua.bench.determinism import worker_determinism

    out = worker_determinism(master_seed=args.seed, days=args.days)
    path = PROJECT_ROOT / "v1" / "evidence" / "worker_determinism.json"
    path.write_text(json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8")
    for c in out["comparisons"]:
        print(f"{c['a_workers']} vs {c['b_workers']} workers: "
              f"{c['n_files_compared']} files, "
              f"{len(c['differing_files'])} differing, "
              f"chain {'match' if c['chain_head_matches'] else 'DIFFER'} -> "
              f"{'byte-identical' if c['byte_identical'] else 'NOT IDENTICAL'}")
    print(f"wrote {path}")
    return 0 if out["all_byte_identical"] else 1


def cmd_e1_replay(args) -> int:
    from baile_nua.bench.determinism import replay_home_days

    out = replay_home_days(
        master_seed=args.seed,
        checkpoint_root=PROJECT_ROOT / "work" / "checkpoints" / "e1_year",
        data_root=PROJECT_ROOT / "v1",
        n_samples=args.samples,
    )
    path = PROJECT_ROOT / "v1" / "evidence" / "checkpoint_replay.json"
    path.write_text(json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"{out['n_home_days_checked']} home-days over {out['n_days_replayed']} "
          f"days; {out['n_mismatches']} mismatches; worst absolute difference "
          f"{out['worst_absolute_difference']}")
    print(f"wrote {path}")
    return 0 if out["exact_replay"] else 1


def cmd_e1_artefacts(args) -> int:
    import baile_nua.sources_registry  # noqa: F401  (declares the sources)
    from baile_nua.calibration import write_d24
    from baile_nua.report.artefacts import (
        write_held_out_comparison,
        write_machine,
        write_saps_marginals,
        write_u03_comparison,
    )

    ev = PROJECT_ROOT / "v1" / "evidence"
    m = write_machine(out_path=ev / "machine.json")
    print(f"machine: {m['machine'].get('cpu_brand', '?')}, "
          f"{m['machine'].get('memory_gb', '?')} GB RAM, "
          f"{m['machine'].get('disk_free_gb', '?')} GB free disk")
    d24 = write_d24(ev / "d24_calibration_targets.json")
    print(f"D24: {d24['n_targets']} targets, exposures {d24['exposures_present']}")
    saps = write_saps_marginals(
        master_seed=args.seed, out_path=ev / "saps_marginals.json"
    )
    print(f"SAPS: {saps['n_within_simultaneous_band']}/{saps['n_marginals']} "
          f"within the simultaneous band; worst |z| {saps['worst_abs_z']:.2f} "
          f"against {saps['worst_critical_z']:.2f}")
    u03 = write_u03_comparison(
        master_seed=args.seed, out_path=ev / "u03_comparison.json",
        n_seeds=args.seeds,
    )
    print(f"U03: recommends {u03['recommendation']} "
          f"(decisive={u03['recommendation_decisive']}, "
          f"contradicts design={u03['contradicts_design']})")
    diag = PROJECT_ROOT / "v1" / "run_diagnostics.json"
    if diag.exists():
        ho = write_held_out_comparison(
            master_seed=args.seed, out_path=ev / "heldout_comparison.json",
            diagnostics_path=diag,
        )
        print(f"held out: gas ratio {ho['gas_space_heat']['mean_ratio']} "
              f"on the UNFITTED axis, electricity "
              f"{ho['electricity_fossil_heated']['mean_ratio']}")
    else:
        print("held out: skipped, no run_diagnostics.json yet")
    return 0


def cmd_e1_report(args) -> int:
    from baile_nua.report import write_report

    path = write_report(project_root=PROJECT_ROOT)
    print(f"wrote {path}")
    return 0


def cmd_scope_show(_args) -> int:
    from baile_nua.config import e1_scope

    print(json.dumps(e1_scope(), indent=2))
    return 0


# --------------------------------------------------------------------------- #

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="baile-nua", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="group", required=True)

    sc = sub.add_parser("schema").add_subparsers(dest="cmd", required=True)
    sc.add_parser("check").set_defaults(fn=cmd_schema_check)
    d = sc.add_parser("dict")
    d.add_argument("path", nargs="?",
                   default=str(PROJECT_ROOT / "v1" / "evidence" / "data_dictionary.md"))
    d.set_defaults(fn=cmd_schema_dict)

    mi = sub.add_parser("mimic").add_subparsers(dest="cmd", required=True)
    mi.add_parser("diff").set_defaults(fn=cmd_mimic_diff)
    for name, fn in (("verify", cmd_mimic_verify), ("provision", cmd_mimic_provision)):
        q = mi.add_parser(name)
        q.add_argument("--mimic-root", default=DEFAULT_MIMIC_ROOT)
        q.set_defaults(fn=fn)

    co = sub.add_parser("controls").add_subparsers(dest="cmd", required=True)
    c = co.add_parser("run")
    c.add_argument("path", nargs="?",
                   default=str(PROJECT_ROOT / "v1" / "evidence" / "negative_controls.json"))
    c.set_defaults(fn=cmd_controls_run)

    sr = sub.add_parser("sources").add_subparsers(dest="cmd", required=True)
    sr.add_parser("fetch").set_defaults(fn=cmd_sources_fetch)
    sr.add_parser("register").set_defaults(fn=cmd_sources_register)

    po = sub.add_parser("population").add_subparsers(dest="cmd", required=True)
    pt = po.add_parser("t0")
    pt.add_argument("--seed", type=int, default=20261008)
    pt.add_argument("--method", default="proportional",
                    choices=["proportional", "whole_area_stratified"])
    pt.add_argument("--write", action="store_true")
    pt.set_defaults(fn=cmd_population_t0)

    so = sub.add_parser("scope").add_subparsers(dest="cmd", required=True)
    so.add_parser("show").set_defaults(fn=cmd_scope_show)

    e1 = sub.add_parser("e1").add_subparsers(dest="cmd", required=True)
    er = e1.add_parser("run")
    er.add_argument("--seed", type=int, default=20261008)
    er.add_argument("--days", type=int, default=None,
                    help="limit the run to the first N days (for a smoke run)")
    er.add_argument(
        "--out", default=None,
        help="output root (default v1/). A --days run REFUSES to write to the "
             "delivered package unless --out is given: a smoke run that "
             "overwrites v1/ leaves a three-day package where the year should "
             "be, and every check that needs a full year then reports NO_DATA.",
    )
    er.add_argument("--presence-days", type=int, default=14)
    er.set_defaults(fn=cmd_e1_run)
    e1.add_parser("invariants").set_defaults(fn=cmd_e1_invariants)
    ed = e1.add_parser("determinism")
    ed.add_argument("--seed", type=int, default=20261008)
    ed.add_argument("--days", type=int, default=3)
    ed.set_defaults(fn=cmd_e1_determinism)
    ep = e1.add_parser("replay")
    ep.add_argument("--seed", type=int, default=20261008)
    ep.add_argument("--samples", type=int, default=100)
    ep.set_defaults(fn=cmd_e1_replay)
    ea = e1.add_parser("artefacts")
    ea.add_argument("--seed", type=int, default=20261008)
    ea.add_argument("--seeds", type=int, default=10)
    ea.set_defaults(fn=cmd_e1_artefacts)
    e1.add_parser("report").set_defaults(fn=cmd_e1_report)

    args = p.parse_args(argv)
    _banner()
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
