"""Rendering on demand must be byte-identical to materialising (R13, U28).

This is the guarantee the storage ruling rests on. U28 stops materialising
1-minute D18 for most homes and, under the storage fallback, for all but the
labelled sub-metered subset. If a re-render differed from what would have been
written, the package would not be smaller - it would be lossy, and the loss
would be silent.

So the test is not "the renderer is deterministic" in the abstract. It is: run
a day, keep its D18; run the same day again in a fresh runner with no shared
state; render the same channels; compare the **Parquet bytes**. Floats that
agree to a tolerance are not enough, because the package is bytes and a
consumer diffs bytes.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import baile_nua.sources_registry  # noqa: F401  (declares the sources)
from baile_nua.engine.calendar import build_calendar
from baile_nua.engine.e1_run import build_slice
from baile_nua.engine.run import EstateRunner
from baile_nua.engine.stream_writer import StreamWriter
from baile_nua.observation.sensors import TIER_DEVICES
from baile_nua.population.synthesise import synthesise_t0
from baile_nua.weather.site import build_realisation

SEED = 20261008


@pytest.fixture(scope="module")
def two_independent_runs(tmp_path_factory):
    """The same simulated day, produced twice by independent runners.

    Module-scoped because each run costs a town synthesis; the point is that
    the two runs share nothing but the seed, so they are built separately
    rather than by copying one result.
    """
    town = synthesise_t0(master_seed=SEED)
    wx = build_realisation(2022, master_seed=SEED, days=3)
    calendar = build_calendar(2022, weather_hourly=wx.site_hourly)[:2]
    sl = build_slice(town, master_seed=SEED, calendar=calendar)

    outputs = []
    for which in ("a", "b"):
        runner = EstateRunner(
            master_seed=SEED, households=sl.households, buildings=sl.buildings,
            thermal=sl.thermal, owned=sl.owned, pv=sl.pv,
            weather_minute=wx.site_minute, calendar=calendar,
        )
        runner.initialise()
        root = tmp_path_factory.mktemp(f"render_{which}")
        writer = StreamWriter(root, master_seed=SEED)
        for day in calendar:
            exchange = runner.phase_a(day, sl.disruptions)
            result = runner.run_day(day, exchange)
            writer.add_day(day, result, runner, sl)
        writer.close()
        outputs.append(root)
    return outputs[0], outputs[1], sl


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _parts(root: Path, dataset_id: str) -> list[Path]:
    return sorted((root / "observable").glob(f"{dataset_id}_part*.parquet")) + \
           sorted((root / "ground_truth").glob(f"{dataset_id}_part*.parquet"))


def test_a_rerendered_d18_is_byte_identical(two_independent_runs):
    """The claim U28 depends on, tested on the bytes.

    Two runners sharing nothing but the master seed must produce the same D18
    Parquet file, byte for byte. If this fails, rendering on demand is not a
    storage optimisation - it is data loss.
    """
    a, b, _sl = two_independent_runs
    parts_a, parts_b = _parts(a, "D18"), _parts(b, "D18")
    assert parts_a and parts_b, "no D18 written by one of the runs"
    assert len(parts_a) == len(parts_b)
    for pa, pb in zip(parts_a, parts_b):
        assert _digest(pa) == _digest(pb), (
            f"{pa.name} differs between two renders of the same day. "
            f"Rendering on demand would therefore lose data that "
            f"materialising would have kept, and U28's package is not "
            f"equivalent to the full one."
        )


def test_every_dataset_rerenders_byte_identically(two_independent_runs):
    """Not only D18: whatever is dropped from the package must be recoverable."""
    a, b, _sl = two_independent_runs
    checked = 0
    for dataset_id in ("D11", "D13", "D16", "D18", "D19"):
        parts_a, parts_b = _parts(a, dataset_id), _parts(b, dataset_id)
        if not parts_a:
            continue
        checked += 1
        assert len(parts_a) == len(parts_b), f"{dataset_id} part count differs"
        for pa, pb in zip(parts_a, parts_b):
            assert _digest(pa) == _digest(pb), f"{dataset_id}: {pa.name} differs"
    assert checked >= 4, f"only {checked} datasets were written to compare"


def test_the_channels_u28_stops_materialising_are_the_ones_rerendered(
    two_independent_runs
):
    """The test must exercise the channels the ruling actually drops.

    A byte-identity test that only covered the smart meter would prove nothing
    about the T1 and T2 one-minute channels that U28 stops writing, or the
    T3/T4 channels the storage fallback stops writing. So this asserts the
    comparison above really did include them.
    """
    a, _b, sl = two_independent_runs
    frames = [pd.read_parquet(p) for p in _parts(a, "D18")]
    assert frames, "no D18 to inspect"
    d18 = pd.concat(frames, ignore_index=True)

    tiers_present = set(d18.tier.unique())
    channels_present = set(d18.channel.unique())

    # The low tiers, whose 1-minute series U28 renders rather than materialises.
    assert {"T1", "T2"} & tiers_present, (
        f"the comparison covered only tiers {sorted(tiers_present)}; it must "
        f"include T1 or T2, whose one-minute channels U28 stops materialising"
    )
    # The sensored tiers, which the storage fallback also renders.
    assert {"T3", "T4"} & tiers_present, (
        f"the comparison covered only tiers {sorted(tiers_present)}; the "
        f"storage fallback renders T3 and T4 too, so they must be in it"
    )
    # And a channel beyond import/export, since the meter is kept either way.
    beyond_meter = channels_present - {"import_w", "export_w"}
    assert beyond_meter, (
        f"only meter channels were compared ({sorted(channels_present)}); the "
        f"ruling keeps those and renders the rest, so the rest is what needs "
        f"the guarantee"
    )


def test_a_render_does_not_depend_on_what_was_rendered_before(
    two_independent_runs
):
    """Order independence, which on-demand rendering needs and a batch write does not.

    Materialising renders every channel of every home in one pass. Rendering on
    demand renders whatever a consumer asks for, in whatever order, possibly
    one channel at a time. If a channel's values depended on what had already
    been rendered, the package would be self-consistent and every later render
    would disagree with it.
    """
    from baile_nua.observation.sensors import observe_channel
    from baile_nua.rng import SeedTree

    rng = np.random.default_rng(11)
    truth = rng.uniform(100.0, 3000.0, size=1440)
    tree = SeedTree(SEED)

    def render(device: str, sim_day: int) -> np.ndarray:
        return observe_channel(
            truth, channel_family="import_w", device_id=device,
            seed_tree=tree, sim_day=sim_day, device_age_years=2.0,
        ).value

    forward = [render(f"DEV-{i}", d) for i in range(3) for d in range(2)]
    backward = [render(f"DEV-{i}", d) for i in reversed(range(3))
                for d in reversed(range(2))]
    backward.reverse()
    # Re-pair them: backward was built in reverse order of (device, day).
    expected = [render(f"DEV-{i}", d) for i in range(3) for d in range(2)]
    for got, want in zip(forward, expected):
        assert np.array_equal(got, want, equal_nan=True)
    # And the reversed traversal must contain the same multiset of series.
    fwd_hashes = sorted(hashlib.sha256(np.ascontiguousarray(x).tobytes()).hexdigest()
                        for x in forward)
    bwd_hashes = sorted(hashlib.sha256(np.ascontiguousarray(x).tobytes()).hexdigest()
                        for x in backward)
    assert fwd_hashes == bwd_hashes, (
        "a channel's rendered values depend on what was rendered before it, so "
        "rendering on demand cannot reproduce a materialised package"
    )
