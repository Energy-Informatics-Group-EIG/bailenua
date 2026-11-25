"""The reproducibility contract, measured rather than asserted.

Design 6.1 and the brief require byte-identical output at 1, 8 and the maximum
number of workers.  Two things make that claim testable here:

*The parallel region is a function.*  ``EstateRunner._run_household`` is a pure
function of one household's own state and read-only inputs, so the day is a MAP
over households rather than a loop that accumulates as it goes.

*The reduction is ordered.*  Results are collected in sorted household-id
order, never in completion order, and the feeder sum goes through
:func:`baile_nua.reduce.sorted_sum_arrays`.  That matters in the last bits:
``np.sum`` over the same 50 arrays in a different order differs by 1e-9 to
1e-7, which is invisible in a plot and fatal to a hash.

What "byte-identical" is taken to mean here is the **Parquet bytes**, not just
equal floats: the files are what a downstream consumer reads, and a dtype that
lands as ``float64`` in one run and ``Float64`` in another is a difference the
consumer sees even when every value matches.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

__all__ = ["worker_determinism", "replay_home_days", "file_digest"]


def file_digest(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def worker_determinism(
    *,
    master_seed: int,
    days: int,
    worker_counts: tuple[int, ...] = (1, 8, 0),
    scratch: Path = Path("/tmp/bn_determinism"),
) -> dict[str, Any]:
    """Run the same days at several worker counts and compare the bytes.

    ``0`` in ``worker_counts`` means "max", resolved to ``os.cpu_count()`` and
    reported as the number actually used, because "max" is not a number anyone
    can check later.
    """
    import baile_nua.sources_registry  # noqa: F401
    from baile_nua.engine.calendar import build_calendar
    from baile_nua.engine.e1_run import build_runner_for_slice, build_slice
    from baile_nua.engine.run import EstateRunner
    from baile_nua.engine.stream_writer import StreamWriter
    from baile_nua.population.synthesise import synthesise_t0
    from baile_nua.weather.site import build_realisation

    town = synthesise_t0(master_seed=master_seed)
    wx = build_realisation(2022, master_seed=master_seed, days=days + 1)
    calendar = build_calendar(2022, weather_hourly=wx.site_hourly)[:days]
    sl = build_slice(town, master_seed=master_seed, calendar=calendar)

    runs: dict[str, Any] = {}
    for requested in worker_counts:
        n = int(requested) if requested else (os.cpu_count() or 1)
        out = Path(scratch) / f"w{n}"
        shutil.rmtree(out, ignore_errors=True)
        out.mkdir(parents=True, exist_ok=True)

        runner = build_runner_for_slice(
            sl, wx, calendar, master_seed=master_seed,
            checkpoint_root=out / "checkpoints",
        )
        writer = StreamWriter(out, master_seed=master_seed)
        chain_head = None
        for day in calendar:
            exchange = runner.phase_a(day, sl.disruptions)
            result = runner.run_day(
                day, exchange, collect_presence=True, workers=n
            )
            chain_head = runner.checkpoint(day, exchange)
            writer.add_day(day, result, runner, sl)
        writer.close()

        digests = {
            str(p.relative_to(out)): file_digest(p)
            for p in sorted(out.rglob("*"))
            if p.is_file() and p.suffix in (".parquet", ".gz")
        }
        runs[str(n)] = {
            "requested": ("max" if not requested else requested),
            "workers_used": n,
            "checkpoint_chain_head": chain_head,
            "n_files": len(digests),
            "digests": digests,
        }

    # ---- compare ---------------------------------------------------------
    keys = sorted(runs, key=lambda k: int(k))
    base = runs[keys[0]]
    comparisons = []
    for k in keys[1:]:
        other = runs[k]
        shared = sorted(set(base["digests"]) & set(other["digests"]))
        only_base = sorted(set(base["digests"]) - set(other["digests"]))
        only_other = sorted(set(other["digests"]) - set(base["digests"]))
        differing = [f for f in shared if base["digests"][f] != other["digests"][f]]
        comparisons.append({
            "a_workers": int(keys[0]),
            "b_workers": int(k),
            "n_files_compared": len(shared),
            "files_only_in_a": only_base,
            "files_only_in_b": only_other,
            "differing_files": differing,
            "chain_head_matches":
                base["checkpoint_chain_head"] == other["checkpoint_chain_head"],
            "byte_identical": (
                not differing and not only_base and not only_other
                and base["checkpoint_chain_head"] == other["checkpoint_chain_head"]
            ),
        })
    return {
        "days": days,
        "n_homes": sl.diagnostics["n_homes"],
        "worker_counts_used": [int(k) for k in keys],
        "runs": {k: {x: y for x, y in v.items() if x != "digests"}
                 for k, v in runs.items()},
        "file_digests": {k: v["digests"] for k, v in runs.items()},
        "comparisons": comparisons,
        "all_byte_identical": all(c["byte_identical"] for c in comparisons),
    }


def replay_home_days(
    *,
    master_seed: int,
    checkpoint_root: Path,
    data_root: Path,
    n_samples: int = 100,
) -> dict[str, Any]:
    """Re-simulate 100 random home-days from their checkpoints and compare.

    Stronger than re-running the year in two ways.

    *It tests the checkpoint.*  The state the checkpoint recorded for the start
    of a day is restored, that one day is run, and the result must match. A
    piece of state the checkpoint forgot - a battery's charge, an appliance's
    failure countdown, an indoor temperature - shows up as a divergence naming
    the household and the quantity. A whole-year re-run never restores
    anything, so it cannot find such a gap.

    *It tests the delivered files.*  The comparison is against the Parquet in
    ``v1/``, not against a second copy kept inside the checkpoint. A replay
    that agreed with a private copy while the released data said something else
    would be worth nothing, and the released data is what anyone else reads.

    D19 at the 30-minute interval is compared because it is the observable
    deliverable, and D16's living-zone temperature because it is the quantity
    that carries across the day boundary and so is the one a bad restore
    breaks.
    """
    import baile_nua.sources_registry  # noqa: F401
    from baile_nua.checkpoint import CheckpointStore
    from baile_nua.edge.export import EXPORT_CONFIGS, build_export
    from baile_nua.engine.calendar import build_calendar
    from baile_nua.engine.e1_run import build_runner_for_slice, build_slice
    from baile_nua.engine.run import MINUTES_PER_DAY, EstateRunner
    from baile_nua.engine.stream_writer import D16_EPOCH_MINUTES
    from baile_nua.population.synthesise import synthesise_t0
    from baile_nua.rng import SeedTree, Stream
    from baile_nua.weather.site import build_realisation

    store = CheckpointStore(checkpoint_root)
    store.verify_chain()
    available = sorted(d for d in store.days() if d > 0)
    if not available:
        raise RuntimeError(f"no replayable checkpoints under {checkpoint_root}")

    town = synthesise_t0(master_seed=master_seed)
    wx = build_realisation(2022, master_seed=master_seed)
    calendar = build_calendar(2022, weather_hourly=wx.site_hourly)
    sl = build_slice(town, master_seed=master_seed, calendar=calendar)
    by_day = {d.sim_day: d for d in calendar}

    data_root = Path(data_root)
    d19 = _load_parts(data_root / "observable", "D19")
    d16 = _load_parts(data_root / "ground_truth", "D16")
    d19 = d19[d19.export_config == "home_30min"]
    d19["date"] = pd.to_datetime(d19.interval_start, utc=True).dt.date
    d16["date"] = pd.to_datetime(d16.ts, utc=True).dt.date

    # The sample is drawn from a declared stream, so "100 random home-days" is
    # the SAME hundred next time: a failure that cannot be re-examined cannot
    # be fixed.
    gen = SeedTree(master_seed).generator(Stream.TEST_ONLY, entity="replay", sim_day=0)
    homes = sorted(sl.households)
    pairs: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    cap = len(homes) * len(available)
    while len(pairs) < n_samples and len(seen) < cap:
        h = homes[int(gen.integers(0, len(homes)))]
        d = available[int(gen.integers(0, len(available)))]
        if (h, d) in seen:
            continue
        seen.add((h, d))
        pairs.append((h, d))

    wanted: dict[int, set[str]] = {}
    for h, d in pairs:
        wanted.setdefault(d, set()).add(h)

    bid_of = {hh: sl.buildings[hh].building_id for hh in sl.households}
    pid_of = {hh: sl.buildings[hh].premises_id for hh in sl.households}
    mismatches: list[dict[str, Any]] = []
    checked = 0
    worst_abs = 0.0

    for sim_day in sorted(wanted):
        cp = store.get(sim_day)
        day = by_day[sim_day]
        runner = build_runner_for_slice(
            sl, wx, calendar, master_seed=master_seed)
        runner.restore(cp)
        exchange = store.get_exchange_log(sim_day)
        result = runner.run_day(day, exchange)

        date = day.date.date()
        idx = pd.date_range(
            pd.Timestamp(date).tz_localize("UTC"), periods=MINUTES_PER_DAY,
            freq="1min", tz="UTC",
        )
        day19 = d19[d19.date == date]
        day16 = d16[d16.date == date]

        for hh in sorted(wanted[sim_day]):
            checked += 1
            bid, pid = bid_of[hh], pid_of[hh]
            ser = result.series.get(bid)
            if ser is None:
                mismatches.append({"sim_day": sim_day, "household_id": hh,
                                   "problem": "replay produced no series"})
                continue

            # --- D19, the observable deliverable --------------------------
            replayed = build_export(
                premises_id=pid, minute_index=idx,
                net_import_w=np.clip(ser["net_w"], 0.0, None),
                net_export_w=np.clip(-ser["net_w"], 0.0, None),
                config=EXPORT_CONFIGS["home_30min"],
            ).reset_index(drop=True)
            recorded = day19[day19.premises_id == pid].sort_values("interval_start")
            if len(recorded) != len(replayed):
                mismatches.append({
                    "sim_day": sim_day, "household_id": hh, "field": "D19 row count",
                    "replayed": len(replayed), "recorded": len(recorded),
                })
                continue
            for col in ("import_wh", "export_wh", "interval_peak_w", "interval_min_w"):
                a = np.asarray(replayed[col], dtype=np.float64)
                b = np.asarray(recorded[col], dtype=np.float64)
                diff = float(np.max(np.abs(a - b))) if len(a) else 0.0
                worst_abs = max(worst_abs, diff)
                if diff > 0.0:
                    k = int(np.argmax(np.abs(a - b)))
                    mismatches.append({
                        "sim_day": sim_day, "household_id": hh,
                        "dataset": "D19", "field": col, "interval": k,
                        "replayed": float(a[k]), "recorded": float(b[k]),
                        "abs_diff": diff,
                    })

            # --- D16, the state that carries across the day boundary -------
            n = MINUTES_PER_DAY // D16_EPOCH_MINUTES
            a = (
                np.asarray(ser["temp_living_c"], dtype=np.float64)
                .reshape(n, D16_EPOCH_MINUTES).mean(axis=1)
            )
            rec16 = day16[day16.building_id == bid].sort_values("ts")
            if len(rec16) != n:
                mismatches.append({
                    "sim_day": sim_day, "household_id": hh,
                    "field": "D16 row count", "replayed": n, "recorded": len(rec16),
                })
                continue
            b = np.asarray(rec16.temp_living_c, dtype=np.float64)
            diff = float(np.max(np.abs(a - b)))
            worst_abs = max(worst_abs, diff)
            if diff > 0.0:
                k = int(np.argmax(np.abs(a - b)))
                mismatches.append({
                    "sim_day": sim_day, "household_id": hh,
                    "dataset": "D16", "field": "temp_living_c", "epoch": k,
                    "replayed": float(a[k]), "recorded": float(b[k]),
                    "abs_diff": diff,
                })

            # I-081's quantity. The cylinder temperature carries across the
            # day boundary exactly as the fabric temperatures do, and D16
            # records it - but this comparison read only temp_living_c, so a
            # restore that threw the tank away was invisible here. Measured
            # afterwards: putting the tank back to its construction setpoint,
            # a median 4.4 C and up to 7.9 C from the recorded value, changes
            # neither temp_living_c nor any D19 field on 250 home-days,
            # because for a gas dwelling the reheat is gas and the living zone
            # does not feel it. So the one test able to find a missing restore
            # could not see the one that was missing. It can now.
            if "dhw_tank_c" in ser and "dhw_tank_c" in rec16.columns:
                at = (
                    np.asarray(ser["dhw_tank_c"], dtype=np.float64)
                    .reshape(n, D16_EPOCH_MINUTES).mean(axis=1)
                )
                bt = np.asarray(rec16.dhw_tank_c, dtype=np.float64)
                ok = np.isfinite(at) & np.isfinite(bt)
                if ok.any():
                    dt = np.abs(at[ok] - bt[ok])
                    difft = float(np.max(dt))
                    worst_abs = max(worst_abs, difft)
                    if difft > 0.0:
                        k = int(np.argmax(dt))
                        mismatches.append({
                            "sim_day": sim_day, "household_id": hh,
                            "dataset": "D16", "field": "dhw_tank_c",
                            "epoch": k, "replayed": float(at[ok][k]),
                            "recorded": float(bt[ok][k]), "abs_diff": difft,
                        })
        del runner

    return {
        "checkpoint_root": str(checkpoint_root),
        "data_root": str(data_root),
        "chain_verified": True,
        "chain_head": store.head(),
        "n_checkpoints": len(available) + 1,
        "n_home_days_requested": n_samples,
        "n_home_days_checked": checked,
        "n_days_replayed": len(wanted),
        "compared": [
            "D19 home_30min import_wh, export_wh, interval_peak_w, interval_min_w",
            "D16 temp_living_c at the 15-minute epoch",
            "D16 dhw_tank_c at the 15-minute epoch (I-081)",
        ],
        "tolerance": "exact: any non-zero absolute difference is a mismatch",
        "worst_absolute_difference": worst_abs,
        "n_mismatches": len(mismatches),
        "mismatches": mismatches[:40],
        "exact_replay": not mismatches,
    }


def _load_parts(root: Path, dataset_id: str) -> pd.DataFrame:
    parts = sorted(Path(root).glob(f"{dataset_id}_part*.parquet"))
    if not parts:
        raise FileNotFoundError(f"no {dataset_id} parts under {root}")
    return pd.concat([pd.read_parquet(p) for p in parts], ignore_index=True)
