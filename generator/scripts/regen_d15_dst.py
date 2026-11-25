#!/usr/bin/env python3
"""Re-export D15 for packages written before the I-111 fix.

D15's `is_dst` was built from `tzdata`'s `dst()`, which is -1 h in an Irish
winter and therefore truthy, so the column was true in winter and false in
summer (I-111). The column is wrong; nothing downstream of it is, because
nothing in the engine reads `is_dst`.

**This costs no re-simulation.** `export/structural` opens with the reason:
D01, D02, D05-D08, D14, D15 and D22 are deterministic functions of the run's
master seed, so the export layer rebuilds the weather realisation from the seed
the run recorded rather than replaying a day. Re-exporting D15 alone is a few
seconds per package against ten hours for a simulated year.

**One constraint, checked rather than assumed.** `RunContext.weather` rebuilds
the realisation as `build_realisation(year, days=n_days)` - from 1 January,
with a length. It carries no start date. So this script refuses any package
whose recorded t0 is not 1 January: for such a package the rebuild would
silently return the wrong window. Every output segment of the replay starts on
1 January; the only segment that does not is the Dec-2014 warm-up, which is
configured `discard_output` and writes no package.

The old part is renamed aside with `.pre-i111`, never deleted - the convention
already used for `.pre-freeze2`.

    python regen_d15_dst.py --dry-run work/replay_2015_2026/2015/pkg
    python regen_d15_dst.py work/replay_2015_2026/*/pkg

Known limitation: the part scan looks at the package root and one level down,
which covers `ground_truth/` and `observable/`. A package with a nested RUN
subdirectory - `v1/ground_truth/town14/` - is not reached, because re-exporting
it needs `export_all(..., subdir="town14")` and a context opened for that run
rather than for the package. Those must be done explicitly; this script reports
them as "no D15 part" rather than pretending to have handled them.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

JAN_1 = (1, 1)


def _parts(pkg: Path) -> list[Path]:
    """D15's parts, wherever this package keeps them.

    A package puts its parts in `ground_truth/` and `observable/`, not at the
    root, so a flat glob finds nothing and reports "no D15 part" for a package
    that has one. That asymmetry - one scan that looks at the top level and
    another that looks a level down - is exactly what produced I-104, where
    the catalogue said "present" and "not on disk" two lines apart.
    """
    found: list[Path] = []
    for root in [pkg, *sorted(d for d in pkg.iterdir() if d.is_dir())]:
        found += [p for p in root.glob("D15_part*")
                  if p.suffix in {".parquet", ".json"}]
    return sorted(found)


def inspect(pkg: Path) -> dict:
    """What is in this package's D15 today, without changing anything."""
    import pandas as pd

    from baile_nua.export.context import RunContext

    out: dict = {"pkg": str(pkg), "parts": [p.name for p in _parts(pkg)]}
    ctx = RunContext.open(pkg, pkg)
    out["t0"] = str(ctx.t0)
    out["n_days"] = ctx.n_days
    out["starts_jan_1"] = (ctx.t0.month, ctx.t0.day) == JAN_1
    pq = [p for p in _parts(pkg) if p.suffix == ".parquet"]
    if pq:
        df = pd.read_parquet(pq[0], columns=["ts", "is_dst"])
        m = pd.to_datetime(df["ts"]).dt.month
        jan = df.loc[m == 1, "is_dst"]
        jul = df.loc[m == 7, "is_dst"]
        out["rows"] = len(df)
        out["jan_mean"] = None if jan.empty else round(float(jan.mean()), 3)
        out["jul_mean"] = None if jul.empty else round(float(jul.mean()), 3)
        # Inverted means winter true and summer false. Either month alone is
        # enough to tell, which matters for a package that has only one.
        out["inverted"] = bool(
            (out["jan_mean"] == 1.0) or (out["jul_mean"] == 0.0))
    return out


def regen(pkg: Path, *, dry_run: bool) -> dict:
    rep = inspect(pkg)
    if not rep["parts"]:
        rep["action"] = "skipped: no D15 part in this package"
        return rep
    if not rep["starts_jan_1"]:
        rep["action"] = (
            f"REFUSED: t0 is {rep['t0']}, not 1 January. RunContext rebuilds "
            f"the realisation from 1 January for n_days and carries no start "
            f"date, so re-exporting would write the wrong window.")
        return rep
    if not rep.get("inverted"):
        rep["action"] = "skipped: already correct"
        return rep
    if dry_run:
        rep["action"] = "would re-export D15"
        return rep

    stamp = int(time.time())
    moved = []
    for p in _parts(pkg):
        aside = p.with_suffix(p.suffix + f".pre-i111.{stamp}")
        p.rename(aside)
        moved.append(aside.name)
    rep["renamed_aside"] = moved

    from baile_nua.export import export_all
    record = export_all(pkg, pkg, which=["D15"], relocate={})
    rep["verdict"] = record.get("D15", {}).get("verdict")
    after = inspect(pkg)
    rep["jan_mean_after"] = after.get("jan_mean")
    rep["jul_mean_after"] = after.get("jul_mean")
    rep["rows_after"] = after.get("rows")
    if after.get("inverted"):
        rep["action"] = "FAILED: still inverted after re-export"
    elif after.get("rows") != rep.get("rows"):
        rep["action"] = (
            f"FAILED: row count changed {rep.get('rows')} -> "
            f"{after.get('rows')}; the rebuilt window does not match")
    else:
        rep["action"] = "re-exported"
    return rep


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pkg", nargs="+", type=Path)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    import baile_nua.sources_registry  # noqa: F401

    bad = 0
    for pkg in args.pkg:
        if not pkg.exists():
            print(f"{pkg}: does not exist")
            bad += 1
            continue
        rep = regen(pkg, dry_run=args.dry_run)
        print(f"\n{rep['pkg']}")
        print(f"  t0 {rep.get('t0')}  n_days {rep.get('n_days')}  "
              f"rows {rep.get('rows')}")
        print(f"  is_dst Jan {rep.get('jan_mean')} Jul {rep.get('jul_mean')}"
              f"  inverted={rep.get('inverted')}")
        if "jan_mean_after" in rep:
            print(f"  after: Jan {rep['jan_mean_after']} "
                  f"Jul {rep['jul_mean_after']} rows {rep['rows_after']}")
        print(f"  -> {rep['action']}")
        if rep["action"].startswith(("FAILED", "REFUSED")):
            bad += 1
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
