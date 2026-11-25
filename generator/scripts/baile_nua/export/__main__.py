"""``python -m baile_nua.export <run_root> <out_root> [--subdir S] [--only D01,D02]``

Prints the export record as JSON on stdout.  Nothing is written anywhere but
the Parquet parts and their manifests: the record is returned, not filed, so
the caller decides where (and whether) it is kept.
"""

from __future__ import annotations

import argparse
import json
import sys

from baile_nua.export import export_all


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m baile_nua.export")
    ap.add_argument("run_root", help="the run to read (holds run_diagnostics.json)")
    ap.add_argument("out_root", help="where <package>/ directories are written")
    ap.add_argument("--subdir", default=None,
                    help="write under <out_root>/<package>/<subdir>/")
    ap.add_argument("--only", default=None,
                    help="comma-separated dataset ids, e.g. D02,D05")
    ap.add_argument("--name", default=None, help="a label for this run")
    args = ap.parse_args(argv)

    report = export_all(
        args.run_root, args.out_root,
        which=(args.only.split(",") if args.only else None),
        subdir=args.subdir, run_name=args.name,
    )
    json.dump(report, sys.stdout, indent=2, default=str, sort_keys=True)
    sys.stdout.write("\n")
    return 1 if report["n_failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
