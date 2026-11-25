#!/usr/bin/env python3
"""Measure D18 bytes per home-day in each observability era, and size the replay.

Why this exists.  The decision to gate D18 rests on a number - "era-gated it
fits the disk" - and that number must be measured rather than asserted.  D-101
already records the full 1-minute figure, **27.1 kB per home-day**, measured on
the published estate-year (506.4 MB over 18,250 home-days).  What it does not
record is the 30-minute smart-meter era, which did not exist when it was
written, so this script measures that era the same way: render real
:func:`observe_channel` output through the real :func:`write_dataset`, and
divide the bytes on disk by the home-days that produced them.

**What is measured and what is assumed.**  The *byte counts* here are measured -
real Parquet, real zstd level 9, real schema coercion, real sidecar manifests.
The *load shape* fed in is synthetic: a baseline, an evening peak, appliance
spikes and PV export, with no physics behind it.  That is sufficient and it is
declared, because what is being measured is the storage cost of a row layout at
a row count, and the 1-minute arm is cross-checked against the 27.1 kB figure
the real estate-year produced.  If the arms disagree the cross-check says so.

Run:  scripts/.venv/bin/python scripts/measure_d18_era_bytes.py
"""

from __future__ import annotations

import datetime as dt
import json
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from baile_nua.engine.stream_writer import interval_mean_held  # noqa: E402
from baile_nua.io import write_dataset  # noqa: E402
from baile_nua.observation.era import (  # noqa: E402
    ENROLMENT_END,
    ENROLMENT_FINAL_SHARE,
    METER_ERA_CHANNELS,
    METER_ERA_INTERVAL_S,
    HomeFacts,
    build_era_map,
    rollout_curve,
)
from baile_nua.observation.sensors import (  # noqa: E402
    DEVICE_SPECS,
    TIER_DEVICES,
    observe_channel,
)
from baile_nua.population.buildings import SENSOR_TIER_UPTAKE  # noqa: E402
from baile_nua.rng import SeedTree  # noqa: E402

MINUTES_PER_DAY = 1440

#: D-101's measured figure for the full 1-minute era, kept here so the arm
#: below can be checked against it rather than silently replacing it.
MEASURED_FULL_1MIN_KB_PER_HOME_DAY = 27.1

#: WP7 town scope (config/e1_scope.yaml town_scaleup).
TOWN_HOMES = 1092

TRUTH_KEYS = {
    "import_w", "export_w", "ct_circuit", "temp", "rh", "co2", "pir",
    "inverter_w", "bess_soc", "charger_w",
}


def synthetic_truth(
    rng: np.random.Generator, *, has_pv: bool, has_bess: bool, has_ev: bool,
) -> dict[str, np.ndarray]:
    """A plausible 1-minute day for one home.  Shape is synthetic; see module doc."""
    m = np.arange(MINUTES_PER_DAY)
    hour = m / 60.0
    base = 120.0 + 60.0 * np.sin((hour - 4.0) / 24.0 * 2 * np.pi)
    evening = 600.0 * np.exp(-((hour - 18.5) ** 2) / 4.0)
    morning = 350.0 * np.exp(-((hour - 7.5) ** 2) / 1.5)
    load = base + evening + morning
    # A handful of appliance cycles, which is what makes the value column
    # incompressible and is therefore the part that matters for bytes.
    for _ in range(int(rng.integers(3, 9))):
        start = int(rng.integers(0, MINUTES_PER_DAY - 120))
        dur = int(rng.integers(20, 110))
        load[start:start + dur] += float(rng.uniform(400.0, 2200.0))
    load += rng.normal(0.0, 8.0, MINUTES_PER_DAY)
    pv = np.zeros(MINUTES_PER_DAY)
    if has_pv:
        pv = np.clip(3500.0 * np.sin((hour - 6.0) / 12.0 * np.pi), 0.0, None)
        pv *= np.clip(rng.normal(0.8, 0.25, MINUTES_PER_DAY), 0.0, 1.2)
    ev = np.zeros(MINUTES_PER_DAY)
    if has_ev and rng.random() < 0.4:
        start = int(rng.integers(0, 1200))
        ev[start:start + int(rng.integers(90, 260))] = 7200.0
    net = load + ev - pv
    nan = np.full(MINUTES_PER_DAY, np.nan)
    return {
        "import_w": np.clip(net, 0.0, None),
        "export_w": np.clip(-net, 0.0, None),
        "ct_circuit": load,
        "temp": 19.5 + 1.5 * np.sin((hour - 14.0) / 24.0 * 2 * np.pi)
                + rng.normal(0.0, 0.1, MINUTES_PER_DAY),
        "rh": np.full(MINUTES_PER_DAY, 55.0),
        "co2": 450.0 + 500.0 * np.exp(-((hour - 21.0) ** 2) / 9.0)
               + rng.normal(0.0, 15.0, MINUTES_PER_DAY),
        "pir": (rng.random(MINUTES_PER_DAY) < 0.25).astype(float),
        "inverter_w": pv if has_pv else nan,
        "bess_soc": (
            np.clip(50.0 + 30.0 * np.sin((hour - 10.0) / 24.0 * 2 * np.pi), 5, 95)
            if has_bess else nan
        ),
        "charger_w": ev if has_ev else nan,
    }


def render_day(
    truth: dict[str, np.ndarray], *, premises_id: str, tier: str, sim_day: int,
    date: pd.Timestamp, tree: SeedTree, era: str,
) -> dict[str, list]:
    """One home-day of D18 columns, exactly as ``StreamWriter`` builds them."""
    idx = pd.date_range(date, periods=MINUTES_PER_DAY, freq="1min", tz="UTC")
    if era == "meter_30min":
        channels = METER_ERA_CHANNELS
        interval_s, phase_min = METER_ERA_INTERVAL_S, 0
        truth = {
            c: interval_mean_held(truth[c], interval_s // 60) for c in channels
        }
    else:
        channels = TIER_DEVICES[tier]
        interval_s = phase_min = None
    cols: dict[str, list] = {
        "device_id": [], "premises_id": [], "channel": [], "ts": [],
        "value": [], "quality": [], "tier": [], "provenance": [], "unit": [],
    }
    for ch in channels:
        t = truth[ch]
        if not np.isfinite(t).any():
            continue
        device_id = f"DEV-{premises_id}-{ch}"
        r = observe_channel(
            t, channel_family=ch, device_id=device_id, seed_tree=tree,
            sim_day=sim_day, device_age_years=2.0,
            interval_s=interval_s, phase_min=phase_min,
        )
        keep = np.isfinite(r.value)
        n = int(keep.sum())
        if not n:
            continue
        cols["device_id"] += [device_id] * n
        cols["premises_id"] += [premises_id] * n
        cols["channel"] += [ch] * n
        cols["ts"].append(idx[keep] + pd.to_timedelta(r.ts_offset_s[keep], unit="s"))
        cols["value"].append(r.value[keep])
        cols["quality"] += list(np.asarray(r.quality, dtype=object)[keep])
        cols["tier"] += [tier] * n
        cols["provenance"] += list(np.asarray(r.provenance, dtype=object)[keep])
        cols["unit"] += [DEVICE_SPECS[ch].unit] * n
    return cols


def measure(era: str, *, n_homes: int, n_days: int, out: Path) -> dict:
    tree = SeedTree(20261008)
    rng = np.random.default_rng(7 if era == "meter_30min" else 11)
    tiers = sorted(SENSOR_TIER_UPTAKE)
    weights = np.array([SENSOR_TIER_UPTAKE[t] for t in tiers], dtype=float)
    weights /= weights.sum()
    homes = []
    for i in range(n_homes):
        tier = tiers[int(rng.choice(len(tiers), p=weights))]
        homes.append((
            f"MPRN-{i:06d}", tier,
            bool(rng.random() < 0.16), bool(rng.random() < 0.06),
            bool(rng.random() < 0.14),
        ))
    frames: list[pd.DataFrame] = []
    start = pd.Timestamp("2024-01-01", tz="UTC")
    rows = 0
    for d in range(n_days):
        date = start + pd.Timedelta(days=d)
        acc: dict[str, list] = {}
        for pid, tier, has_pv, has_bess, has_ev in homes:
            t = synthetic_truth(rng, has_pv=has_pv, has_bess=has_bess, has_ev=has_ev)
            cols = render_day(t, premises_id=pid, tier=tier, sim_day=d,
                              date=date, tree=tree, era=era)
            for k, v in cols.items():
                # `ts` and `value` are lists of arrays; the rest are lists of
                # scalars. Extending is right for both: the array list stays a
                # list of arrays, which is what the assembly below concatenates.
                acc.setdefault(k, []).extend(v)
        if not acc.get("ts"):
            continue
        frame = pd.DataFrame({
            "device_id": acc["device_id"],
            "premises_id": acc["premises_id"],
            "channel": acc["channel"],
            "ts": acc["ts"][0].append(acc["ts"][1:]) if len(acc["ts"]) > 1
                  else acc["ts"][0],
            "value": np.concatenate(acc["value"]),
            "quality": acc["quality"],
            "tier": acc["tier"],
            "provenance": acc["provenance"],
            "unit": acc["unit"],
        })
        frames.append(frame)
        rows += len(frame)
    big = pd.concat(frames, ignore_index=True)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "D18_part000.parquet"
    write_dataset(big, "D18", path, extra_meta={"part": 0, "rows": len(big)})
    man = path.with_suffix(path.suffix + ".manifest.json")
    sidecar = path.parent / f"{path.stem}.manifest.json"
    nbytes = path.stat().st_size
    for m in (man, sidecar):
        if m.exists():
            nbytes += m.stat().st_size
    home_days = n_homes * n_days
    return {
        "era": era,
        "n_homes": n_homes,
        "n_days": n_days,
        "home_days": home_days,
        "rows": int(rows),
        "rows_per_home_day": round(rows / home_days, 1),
        "bytes": int(nbytes),
        "bytes_per_row": round(nbytes / max(rows, 1), 3),
        "kb_per_home_day": round(nbytes / 1024 / home_days, 3),
    }


def project() -> dict:
    """Home-days in each era over the whole replay, at town scope."""
    facts = [
        HomeFacts(premises_id=f"MPRN-{i:06d}", estate_id=f"EST-{i % 12:02d}",
                  has_pv=(i % 7 == 0), has_heat_pump=(i % 11 == 0),
                  has_ev=(i % 9 == 0))
        for i in range(TOWN_HOMES)
    ]
    em = build_era_map(facts, master_seed=20261008)
    dates, _shares = rollout_curve()
    counts = {"none": 0, "meter_30min": 0, "full_1min": 0}
    for d in dates:
        for h in em.homes.values():
            counts[h.era_on(d).value] += 1
    return {
        "span": [dates[0].isoformat(), dates[-1].isoformat()],
        "n_days": len(dates),
        "n_homes": TOWN_HOMES,
        "home_days_total": len(dates) * TOWN_HOMES,
        "home_days_by_era": counts,
        "era_diagnostics": em.diagnostics(),
    }


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="d18_era_bytes_"))
    try:
        meter = measure("meter_30min", n_homes=120, n_days=60, out=tmp / "m")
        full = measure("full_1min", n_homes=25, n_days=14, out=tmp / "f")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    proj = project()
    kb = {"meter_30min": meter["kb_per_home_day"],
          "full_1min": full["kb_per_home_day"]}
    # The 1-minute arm is a check on this script, not the authority: D-101's
    # 27.1 kB came off a real estate-year. The projection below uses the
    # measured figure of record and reports the ratio so a drift is visible.
    ratio = full["kb_per_home_day"] / MEASURED_FULL_1MIN_KB_PER_HOME_DAY
    hd = proj["home_days_by_era"]
    gated_bytes = (
        hd["meter_30min"] * kb["meter_30min"]
        + hd["full_1min"] * MEASURED_FULL_1MIN_KB_PER_HOME_DAY
    ) * 1024
    ungated_bytes = (
        proj["home_days_total"] * MEASURED_FULL_1MIN_KB_PER_HOME_DAY * 1024
    )
    out = {
        "measured": {"meter_30min": meter, "full_1min": full},
        "cross_check_full_1min": {
            "measured_here_kb_per_home_day": full["kb_per_home_day"],
            "d101_measured_kb_per_home_day": MEASURED_FULL_1MIN_KB_PER_HOME_DAY,
            "ratio": round(ratio, 3),
            "used_for_projection": "D-101's 27.1 kB (a real estate-year)",
        },
        "projection": proj,
        "d18_gated_gb": round(gated_bytes / 1024 ** 3, 2),
        "d18_ungated_gb": round(ungated_bytes / 1024 ** 3, 2),
        "saving_gb": round((ungated_bytes - gated_bytes) / 1024 ** 3, 2),
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
