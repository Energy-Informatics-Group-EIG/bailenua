"""Per-home D18 era gating: the dates, the eras, and what the writer writes.

What these tests are for, in order of how much their absence would hurt.

* **No D18 row before a home's install date.**  This is the whole claim.  A row
  stamped before the meter existed is not noise, it is a fabricated
  measurement, and nothing downstream could tell it from a real one.
* **2015-2018 is empty.**  Ireland's National Smart Metering Programme
  commenced in late 2019, so four of the replay's twelve years must contain no
  observations at all.  A test that only checked "fewer rows" would pass on a
  gate that leaked a handful.
* **The realised share reproduces the sourced curve.**  The install dates are
  drawn, but the *count* is not: the stratified assignment makes the number
  installed by any day exactly ``round(share * N)``, so the tolerance here is
  ``0.5 / N`` and not a loose band.  If this drifts, the gate has stopped
  tracking the only sourced thing about it.
* **Determinism.**  Install dates that moved between runs would make every
  checkpoint in the chain unreproducible.
* **The 30-minute era is 30-minute, and two channels.**  A gate that let the
  full device mix through at a lower rate would publish sensors nobody fitted.
* **The comparison logic of ``prove_2_3_switch.py``.**  That script cannot run
  until the 2018 checkpoint exists (about 16 October 2026), so its comparison -
  the part that decides pass or fail - is tested here on real written packages
  instead of being taken on trust.

The writer-level tests drive the **real** :class:`StreamWriter` with a stub
slice and a stub day result, so they exercise ``write_dataset`` and therefore
schema validation, the leakage audit and the package rule.  They need
``sources/derived/smart_meter_rollout.csv`` on disk, which is what the gate is
built from; the test is skipped rather than silently passing if it is absent.
"""

from __future__ import annotations

import datetime as dt
import types

import numpy as np
import pandas as pd
import pytest

from baile_nua.engine.stream_writer import StreamWriter, interval_mean_held
from baile_nua.observation.era import (
    ENROLMENT_END,
    ENROLMENT_FINAL_SHARE,
    ENROLMENT_START,
    METER_ERA_CHANNELS,
    METER_ERA_INTERVAL_S,
    Era,
    HomeFacts,
    RolloutSourceMissing,
    build_era_map,
    enrolment_share,
    rollout_curve,
)
from baile_nua.observation.sensors import TIER_DEVICES, observe_channel
from baile_nua.rng import SeedTree, Stream

pytestmark = pytest.mark.filterwarnings("ignore::FutureWarning")

MINUTES_PER_DAY = 1440
MASTER_SEED = 20251010          # the replay's own seed (scripts/replay_config.json)
TOWN_HOMES = 1092               # config/e1_scope.yaml town_scaleup


def _rollout_or_skip():
    try:
        return rollout_curve()
    except RolloutSourceMissing as exc:          # pragma: no cover - env guard
        pytest.skip(str(exc))


def _facts(n: int, *, prefix: str = "MPRN") -> list[HomeFacts]:
    """``n`` homes with a spread of PV, heat pumps and EVs across 12 estates."""
    return [
        HomeFacts(
            premises_id=f"{prefix}-{i:06d}",
            estate_id=f"EST-{i % 12:02d}",
            has_pv=(i % 7 == 0),
            has_heat_pump=(i % 11 == 0),
            has_ev=(i % 9 == 0),
        )
        for i in range(n)
    ]


# --------------------------------------------------------------------------- #
# the sourced curve and the dates drawn against it
# --------------------------------------------------------------------------- #

def test_the_sourced_curve_has_its_three_anchors_and_no_rollout_before_2019():
    dates, shares = _rollout_or_skip()
    by = dict(zip(dates, shares))
    assert by[dt.date(2023, 11, 21)] == pytest.approx(0.75, abs=1e-9)
    assert by[dt.date(2025, 9, 4)] == pytest.approx(0.83, abs=1e-9)
    # The programme commenced in LATE 2019, so every day of 2015-2018 and the
    # first nine months of 2019 are zero. If this ever becomes non-zero the
    # gate is tracking a curve that contradicts the press releases it cites.
    pre = [s for d, s in by.items() if d < dt.date(2019, 10, 1)]
    assert pre and max(pre) == 0.0


@pytest.mark.parametrize("n", [50, 1092])
def test_the_realised_meter_share_reproduces_the_sourced_curve(n):
    """Within 0.5/N, which is what the stratified assignment guarantees.

    Not a loose tolerance picked to make the test pass: the home at rank ``r``
    of ``N`` is handed the quantile ``(r + 0.5) / N``, so the count installed
    by any day is exactly ``round(share * N)`` and the realised share can
    differ from the sourced one by at most half a home.
    """
    dates, shares = _rollout_or_skip()
    by = dict(zip(dates, shares))
    em = build_era_map(_facts(n), master_seed=MASTER_SEED)
    tol = 0.5 / n + 1e-9
    checked = [
        "2015-01-01", "2017-06-15", "2018-12-31", "2019-10-01", "2019-12-31",
        "2020-07-01", "2021-01-01", "2022-06-30", "2023-11-21", "2024-05-01",
        "2025-09-04", "2026-09-30",
    ]
    for iso in checked:
        d = dt.date.fromisoformat(iso)
        assert abs(em.realised_meter_share(d) - by[d]) <= tol, (
            f"{iso}: realised {em.realised_meter_share(d)} against sourced "
            f"{by[d]}, tolerance {tol}"
        )
    # And over the WHOLE span, not only the sampled dates.
    worst = max(abs(em.realised_meter_share(d) - s) for d, s in by.items())
    assert worst <= tol, f"worst deviation over the span is {worst}"


def test_the_share_that_never_gets_a_meter_is_the_curves_own_remainder():
    dates, shares = _rollout_or_skip()
    em = build_era_map(_facts(TOWN_HOMES), master_seed=MASTER_SEED)
    diag = em.diagnostics()
    # 0.83 at the end of the span: about a sixth of premises still had no smart
    # meter, and inventing one for them would overstate the programme.
    assert diag["n_never_metered"] > 0
    expected = round((1.0 - shares[-1]) * TOWN_HOMES)
    assert abs(diag["n_never_metered"] - expected) <= 1
    assert dt.date.fromisoformat(diag["first_install"]) >= dt.date(2019, 10, 1)


def test_install_dates_are_deterministic_in_the_seed():
    a = build_era_map(_facts(200), master_seed=MASTER_SEED)
    b = build_era_map(_facts(200), master_seed=MASTER_SEED)
    assert {k: v.install_date for k, v in a.homes.items()} == \
           {k: v.install_date for k, v in b.homes.items()}
    assert {k: v.enrolment_date for k, v in a.homes.items()} == \
           {k: v.enrolment_date for k, v in b.homes.items()}
    # Order of the input must not matter either: a run that visited homes in a
    # different order would otherwise get different dates.
    shuffled = list(reversed(_facts(200)))
    c = build_era_map(shuffled, master_seed=MASTER_SEED)
    assert {k: v.install_date for k, v in a.homes.items()} == \
           {k: v.install_date for k, v in c.homes.items()}


def test_a_different_seed_gives_different_install_dates():
    a = build_era_map(_facts(200), master_seed=MASTER_SEED)
    b = build_era_map(_facts(200), master_seed=MASTER_SEED + 1)
    moved = sum(
        1 for k in a.homes
        if a.homes[k].install_date != b.homes[k].install_date
    )
    # The COUNT installed by any day is identical by construction; WHICH homes
    # they are must not be. A gate whose allocation ignored the seed would
    # publish the same install date for the same premises id in every run.
    assert moved > 100, f"only {moved} of 200 homes moved"
    dates, shares = _rollout_or_skip()
    tol = 0.5 / 200 + 1e-9
    d = dt.date(2023, 11, 21)
    assert abs(b.realised_meter_share(d) - dict(zip(dates, shares))[d]) <= tol


def test_a_duplicate_premises_is_refused():
    f = _facts(3)
    with pytest.raises(ValueError, match="appears twice"):
        build_era_map(f + [f[0]], master_seed=MASTER_SEED)


# --------------------------------------------------------------------------- #
# enrolment: D-111 / A-99
# --------------------------------------------------------------------------- #

def test_the_enrolment_ramp_is_zero_before_2021_and_30pc_at_the_end():
    assert enrolment_share(dt.date(2020, 12, 31)) == 0.0
    assert enrolment_share(ENROLMENT_START) == 0.0
    assert enrolment_share(ENROLMENT_END) == pytest.approx(ENROLMENT_FINAL_SHARE)
    mid = ENROLMENT_START + (ENROLMENT_END - ENROLMENT_START) / 2
    assert enrolment_share(mid) == pytest.approx(ENROLMENT_FINAL_SHARE / 2, abs=1e-3)
    # Flat after the span, not extrapolated: D-111 states a point, not a
    # gradient.
    assert enrolment_share(dt.date(2030, 1, 1)) == pytest.approx(
        ENROLMENT_FINAL_SHARE)


def test_enrolment_hits_its_target_and_never_precedes_the_meter():
    _rollout_or_skip()
    em = build_era_map(_facts(TOWN_HOMES), master_seed=MASTER_SEED)
    diag = em.diagnostics()
    assert diag["enrolment"]["shortfall_days"] == 0
    assert diag["enrolment"]["n_enrolled"] == diag["enrolment"]["final_target"]
    assert abs(
        em.realised_enrolment_share(ENROLMENT_END) - ENROLMENT_FINAL_SHARE
    ) <= 1.0 / TOWN_HOMES + 1e-9
    for h in em.homes.values():
        if h.enrolment_date is None:
            continue
        assert h.install_date is not None, (
            f"{h.premises_id} is enrolled with no smart meter; the edge "
            f"device's import and export channels are the meter's registers"
        )
        assert h.enrolment_date >= h.install_date
        assert h.enrolment_date >= ENROLMENT_START


def test_enrolment_is_skewed_toward_pv_heat_pump_and_ev_homes():
    _rollout_or_skip()
    facts = _facts(TOWN_HOMES)
    em = build_era_map(facts, master_seed=MASTER_SEED)
    by_id = {f.premises_id: f for f in facts}
    enrolled = {k for k, h in em.homes.items() if h.enrolment_date}
    def rate(pred):
        pool = [f for f in facts if pred(f)]
        return sum(1 for f in pool if f.premises_id in enrolled) / len(pool)
    plain = rate(lambda f: not (f.has_pv or f.has_heat_pump or f.has_ev))
    for name, pred in (("pv", lambda f: f.has_pv),
                       ("heat pump", lambda f: f.has_heat_pump),
                       ("ev", lambda f: f.has_ev)):
        assert rate(pred) > plain, (
            f"{name} homes enrol at {rate(pred):.3f} against {plain:.3f} for "
            f"homes with none of the three; D-111 says the skew is toward them"
        )


def test_the_era_only_ever_moves_forwards():
    _rollout_or_skip()
    em = build_era_map(_facts(60), master_seed=MASTER_SEED)
    order = {Era.NONE: 0, Era.METER_30MIN: 1, Era.FULL_1MIN: 2}
    dates, _ = rollout_curve()
    for h in em.homes.values():
        seen = 0
        for d in dates[::29]:          # every 29th day: a full sweep is slow
            rank = order[h.era_on(d)]
            assert rank >= seen, f"{h.premises_id} went backwards on {d}"
            seen = rank


# --------------------------------------------------------------------------- #
# the writer: what actually lands in D18
# --------------------------------------------------------------------------- #

def _stub_slice(facts, tier_of):
    """A slice carrying only what ``StreamWriter.add_day`` reads.

    It holds EVERY home of the scope, because the writer builds its era map
    from the slice and the realised share is a property of the scope N. Only a
    handful of them are rendered: ``add_day`` iterates the day's series, not
    the slice, so a stub result for one building renders one home against a
    1,092-home era map. That is the same relationship the real run has - the
    town slice is the scope - and it is what lets these tests use the town's
    own install dates without simulating 1,092 homes.

    The PV, heat pump, EV and estate of each stub building are taken from the
    :class:`HomeFacts` the test built, so that ``home_facts_from_slice`` reads
    back exactly those facts and the writer's own era map is the one the test
    reasoned about. Stubbing them to constants instead gave every home the same
    enrolment propensity, and the enrolment dates then quietly disagreed with
    the test's own map - which is the failure this docstring exists to stop
    recurring.
    """
    buildings, thermal, pv = {}, {}, {}
    for i, f in enumerate(facts):
        hh = f"H-{i:05d}"
        buildings[hh] = types.SimpleNamespace(
            building_id=f"B-{i:05d}", premises_id=f.premises_id,
            estate_id=f.estate_id, sensor_tier=tier_of(f.premises_id),
            heating_system=("heat pump" if f.has_heat_pump else "gas boiler"),
            has_ev=f.has_ev,
            tenure="owner occupied", dwelling_type="semi-detached",
        )
        thermal[hh] = types.SimpleNamespace(solar_aperture_m2=6.0)
        if f.has_pv:
            pv[hh] = types.SimpleNamespace(capacity_kwp=4.0)
    return types.SimpleNamespace(buildings=buildings, thermal=thermal, pv=pv)


def _stub_result(sl, *, render):
    """One day of series for the buildings in ``render``, with every key read."""
    n = MINUTES_PER_DAY
    m = np.arange(n)
    hour = m / 60.0
    series = {}
    for j, bid in enumerate(sorted(render)):
        phase = 0.3 * j
        load = (150.0 + 500.0 * np.exp(-((hour - 18.5 + phase) ** 2) / 4.0)
                + 20.0 * np.sin(hour + phase))
        pv = np.clip(2500.0 * np.sin((hour - 6.0) / 12.0 * np.pi), 0.0, None)
        series[bid] = {
            "net_w": load - pv,
            "appliance_w": load,
            "temp_living_c": 19.0 + 1.5 * np.sin(hour / 24.0 * 2 * np.pi),
            "temp_sleep_c": 18.0 + np.sin(hour / 24.0 * 2 * np.pi),
            "temp_env_c": np.full(n, 10.0),
            "co2_living_ppm": 500.0 + 300.0 * np.sin(hour / 24.0 * 2 * np.pi),
            "co2_sleep_ppm": np.full(n, 600.0),
            "dhw_tank_c": np.full(n, 55.0),
            "heat_delivered_w": np.full(n, 1200.0),
            "internal_gain_w": np.full(n, 300.0),
            "solar_incident_w_m2": np.clip(
                400.0 * np.sin((hour - 6.0) / 12.0 * np.pi), 0.0, None),
            "ach_effective": np.full(n, 0.5),
            "occupants_living": np.full(n, 1.0),
            "occupants_sleep": np.full(n, 1.0),
            "occupied": np.ones(n),
            "pv_w": pv,
            "bess_soc_pct": np.full(n, 50.0),
            "ev_w": np.zeros(n),
        }
    return types.SimpleNamespace(
        series=series, cycles=[], activity_rows=[], presence_rows=[],
    )


#: Everything but D18, for the tests that only read D18. The other datasets
#: are not under test and writing them would make the test slow for no gain;
#: the gating branch runs identically either way. The proof-logic tests pass
#: ``omit=frozenset()`` instead, because they need non-D18 files to compare.
OMIT_ALL_BUT_D18 = frozenset({
    "D10", "D11", "D13", "D16", "D17", "D17_aggregate", "D19",
})


def _write_days(tmp_path, sl, *, dates, render, gated, sim_day0=0,
                omit=OMIT_ALL_BUT_D18):
    """Drive the real writer over ``dates`` and return the D18 frame."""
    w = StreamWriter(
        tmp_path, master_seed=MASTER_SEED,
        omit_datasets=omit,
        d18_era_gating=gated,
    )
    for k, iso in enumerate(dates):
        day = types.SimpleNamespace(
            sim_day=sim_day0 + k, date=pd.Timestamp(iso),
        )
        w.add_day(day, _stub_result(sl, render=render), None, sl)
    w.close()
    parts = sorted((tmp_path / "observable").glob("D18_part*.parquet"))
    if not parts:
        return pd.DataFrame(columns=["device_id", "premises_id", "channel",
                                     "ts", "value", "quality", "tier",
                                     "provenance", "unit"]), w
    return pd.concat([pd.read_parquet(p) for p in parts], ignore_index=True), w


@pytest.fixture(scope="module")
def town(tmp_path_factory):
    """The 1,092-home scope: its era map, a stub slice, and four named homes.

    ``early`` is the first home metered that also goes on to enrol, so both era
    boundaries are reachable; ``metered_only`` gets a meter and never enrols,
    which is the majority case; ``never`` gets no meter at all, which is the
    sixth of premises the curve leaves unmetered; ``enrolled_t3`` is a second
    enrolled home on a lower sensor tier, so the full era's channel set is
    checked against something other than T4.
    """
    _rollout_or_skip()
    facts = _facts(TOWN_HOMES)
    em = build_era_map(facts, master_seed=MASTER_SEED)
    early = min(
        (h for h in em.homes.values() if h.install_date and h.enrolment_date),
        key=lambda h: (h.install_date, h.premises_id),
    )
    metered_only = next(
        h for h in sorted(em.homes.values(), key=lambda x: x.premises_id)
        if h.install_date and h.enrolment_date is None
    )
    never = next(
        h for h in sorted(em.homes.values(), key=lambda x: x.premises_id)
        if h.install_date is None
    )
    enrolled_t3 = next(
        h for h in sorted(em.homes.values(), key=lambda x: x.premises_id)
        if h.enrolment_date and h.premises_id != early.premises_id
    )
    tier = {
        early.premises_id: "T4",
        metered_only.premises_id: "T4",
        never.premises_id: "T4",
        enrolled_t3.premises_id: "T3",
    }
    sl = _stub_slice(facts, lambda pid: tier.get(pid, "T1"))
    bid = {b.premises_id: b.building_id for b in sl.buildings.values()}
    return types.SimpleNamespace(
        em=em, sl=sl, bid=bid, early=early, metered_only=metered_only,
        never=never, enrolled_t3=enrolled_t3,
        sl_tmp=tmp_path_factory.mktemp("era_map_check"),
    )


def test_the_writers_own_era_map_is_the_one_the_scope_implies(town):
    """The writer builds its map from the slice; it must read the same facts.

    This is the one seam where the gate could be right in isolation and wrong
    in the engine: ``home_facts_from_slice`` reads PV from ``sl.pv``, the heat
    pump from ``heating_system`` and the EV from ``has_ev``, and if any of
    those is read differently from how it was written then the writer's
    enrolment dates are not the scope's.
    """
    from baile_nua.observation.era import home_facts_from_slice

    assert home_facts_from_slice(town.sl) == _facts(TOWN_HOMES)
    w = StreamWriter(
        town.sl_tmp, master_seed=MASTER_SEED, d18_era_gating=True,
    )
    built = w._era_map(town.sl)
    assert {k: (v.install_date, v.enrolment_date)
            for k, v in built.homes.items()} == \
           {k: (v.install_date, v.enrolment_date)
            for k, v in town.em.homes.items()}


def test_no_d18_row_before_a_homes_install_date(tmp_path, town):
    early, metered_only = town.early, town.metered_only
    render = {town.bid[early.premises_id], town.bid[metered_only.premises_id]}
    # The day before each home's install date, and the day of it.
    dates = sorted({
        (early.install_date - dt.timedelta(days=1)).isoformat(),
        early.install_date.isoformat(),
        (metered_only.install_date - dt.timedelta(days=1)).isoformat(),
        metered_only.install_date.isoformat(),
    })
    frame, _w = _write_days(tmp_path, town.sl, dates=dates, render=render,
                            gated=True)
    assert len(frame), "the gate wrote nothing at all on days it should write"
    frame["day"] = frame["ts"].dt.tz_convert("UTC").dt.date
    for home in (early, metered_only):
        own = frame[frame["premises_id"] == home.premises_id]
        assert len(own), f"{home.premises_id} has no rows on its install date"
        assert own["day"].min() >= home.install_date, (
            f"{home.premises_id} has a reading stamped "
            f"{own['day'].min()} but its meter was installed "
            f"{home.install_date}"
        )


def test_a_home_that_never_gets_a_meter_never_gets_a_row(tmp_path, town):
    render = {town.bid[town.never.premises_id]}
    frame, w = _write_days(
        tmp_path, town.sl, render=render,
        dates=["2019-12-31", "2021-06-30", "2024-01-01", "2026-09-30"],
        gated=True,
    )
    assert len(frame) == 0
    assert w.era_report()["home_days_by_era"]["none"] == 4


def test_2015_to_2018_yields_zero_d18_rows(tmp_path, town):
    """Four of the replay's twelve years are empty, and that is correct."""
    render = {town.bid[town.early.premises_id],
              town.bid[town.metered_only.premises_id]}
    dates = [
        "2015-01-01", "2015-06-30", "2016-02-29", "2016-12-31",
        "2017-03-15", "2017-10-01", "2018-01-01", "2018-07-04", "2018-12-31",
    ]
    frame, w = _write_days(tmp_path, town.sl, dates=dates, render=render,
                           gated=True)
    assert len(frame) == 0, (
        f"{len(frame)} D18 rows in 2015-2018; the National Smart Metering "
        f"Programme commenced in late 2019, so there was nothing fitted to "
        f"produce them"
    )
    assert not list((tmp_path / "observable").glob("D18_part*.parquet"))
    report = w.era_report()
    assert report["d18_era_gating"] is True
    assert report["home_days_by_era"]["none"] == len(dates) * 2
    assert report["home_days_by_era"]["meter_30min"] == 0
    assert report["home_days_by_era"]["full_1min"] == 0


def test_the_same_days_ungated_do_produce_rows(tmp_path, town):
    """The control: 2015-2018 is empty because of the GATE, not the stub.

    Without this, a stub that produced no observations for some unrelated
    reason would make the test above pass while proving nothing.
    """
    render = {town.bid[town.early.premises_id],
              town.bid[town.metered_only.premises_id]}
    frame, w = _write_days(
        tmp_path, town.sl, dates=["2015-01-01", "2018-12-31"], render=render,
        gated=False)
    assert len(frame) > 1000
    assert w.era_report() == {"d18_era_gating": False}


def test_the_meter_era_is_two_channels_at_thirty_minutes(tmp_path, town):
    home = town.metered_only
    # A T4 home: the tier would give ten channels if the era did not override
    # it, which is exactly the leak this test exists to catch.
    assert town.sl.buildings[
        next(hh for hh, b in town.sl.buildings.items()
             if b.premises_id == home.premises_id)].sensor_tier == "T4"
    day = home.install_date + dt.timedelta(days=40)
    frame, _w = _write_days(
        tmp_path, town.sl, dates=[day.isoformat()],
        render={town.bid[home.premises_id]}, gated=True)
    assert set(frame["channel"]) == set(METER_ERA_CHANNELS), (
        "a meter exchange fits no room sensor, no CT clamp and no inverter "
        "telemetry, whatever tier the household consented to"
    )
    # 48 half hours per channel, less whatever the gap model dropped.
    per_channel = frame.groupby("channel").size()
    assert (per_channel <= MINUTES_PER_DAY // (METER_ERA_INTERVAL_S // 60)).all()
    assert (per_channel >= 40).all()
    # Clock-aligned to the half hour. The drift is seconds a day with a weekly
    # or monthly resync, so rounding to the nearest minute recovers the slot.
    minute = frame["ts"].dt.tz_convert("UTC").dt.round("1min")
    slot = minute.dt.hour * 60 + minute.dt.minute
    assert set((slot % 30).unique()) == {0}, (
        "a half-hourly interval reading is stamped on the half hour; a phase "
        "of its own would be a device schedule, not a data service"
    )


def test_the_full_era_restores_the_whole_tier_at_one_minute(tmp_path, town):
    home = town.enrolled_t3
    day = home.enrolment_date + dt.timedelta(days=10)
    frame, w = _write_days(
        tmp_path, town.sl, dates=[day.isoformat()],
        render={town.bid[home.premises_id]}, gated=True)
    assert set(frame["channel"]) == set(TIER_DEVICES["T3"])
    # import_w is a 1-minute channel: close to 1,440 rows, not 48.
    n_import = int((frame["channel"] == "import_w").sum())
    assert n_import > 1200, n_import
    assert w.era_report()["home_days_by_era"]["full_1min"] == 1


def test_the_meter_era_publishes_the_interval_mean_not_a_spot_reading():
    """The half-hour value must be the mean of its thirty minutes.

    An instantaneous 1-minute sample stamped at the half hour would not close
    an energy balance against D16 or D19, and it is the kind of tell the 7.9
    audit looks for.
    """
    rng = np.random.default_rng(3)
    truth = rng.normal(600.0, 250.0, MINUTES_PER_DAY)
    held = interval_mean_held(truth, 30)
    assert held.shape == truth.shape
    for k in range(MINUTES_PER_DAY // 30):
        block = truth[k * 30:(k + 1) * 30]
        assert held[k * 30:(k + 1) * 30] == pytest.approx(block.mean())
    # And the whole-day energy is preserved, which is the property that makes
    # it safe to publish as interval consumption.
    assert held.mean() == pytest.approx(truth.mean())
    with pytest.raises(ValueError, match="does not divide"):
        interval_mean_held(np.zeros(100), 30)


def test_the_interval_override_leaves_every_existing_call_unchanged():
    """``observe_channel`` without the new arguments renders what it always did."""
    tree = SeedTree(MASTER_SEED)
    truth = np.linspace(0.0, 3000.0, MINUTES_PER_DAY)
    kw = dict(channel_family="import_w", device_id="DEV-X-import_w",
              seed_tree=tree, sim_day=11, device_age_years=2.0)
    a = observe_channel(truth, **kw)
    b = observe_channel(truth, interval_s=None, phase_min=None, **kw)
    np.testing.assert_array_equal(
        np.nan_to_num(a.value, nan=-1.0), np.nan_to_num(b.value, nan=-1.0))
    np.testing.assert_array_equal(a.ts_offset_s, b.ts_offset_s)
    assert a.quality == b.quality and a.provenance == b.provenance
    # And the override does change the reporting rate.
    c = observe_channel(truth, interval_s=1800, phase_min=0, **kw)
    assert np.isfinite(c.value).sum() <= 48
    assert c.diagnostics["interval_s"] == 1800
    assert c.diagnostics["interval_s_declared"] == 1


def test_gating_off_is_byte_for_byte_the_old_behaviour(tmp_path, town):
    """The flag's default must not change a single byte of an existing package.

    Not a row count: the ungated arm of ``prove_2_3_switch.py`` is the
    reference the 2019 switch is proved against, so "unchanged" has to mean
    the bytes.
    """
    from prove_2_3_switch import compare_packages

    render = {town.bid[town.early.premises_id]}
    a, b = tmp_path / "a", tmp_path / "b"
    _write_days(a, town.sl, dates=["2022-03-01", "2022-03-02"], render=render,
                gated=False)
    _write_days(b, town.sl, dates=["2022-03-01", "2022-03-02"], render=render,
                gated=False)
    assert compare_packages(a, b, ignore=frozenset()) == []


# --------------------------------------------------------------------------- #
# the proof script's comparison logic
# --------------------------------------------------------------------------- #

def test_the_new_streams_do_not_collide_with_an_existing_one():
    """Appended, never renumbered: a reused value shares a sequence."""
    values = [int(s) for s in Stream]
    assert len(values) == len(set(values))
    assert int(Stream.SMART_METER_INSTALL) == 79
    assert int(Stream.PARAEL_ENROLMENT) == 80


@pytest.fixture
def two_packages(tmp_path, town):
    """Two real written packages: one gated, one not, for the same two days.

    Two days inside the home's FULL era, so both arms write a full 1-minute
    D18 and the only thing that can differ is what the gate did to it. The
    datasets this writer is told to omit are omitted in both arms, so what is
    compared is D18 against D18.
    """
    early = town.early
    render = {town.bid[early.premises_id]}
    dates = [
        early.enrolment_date.isoformat(),
        (early.enrolment_date + dt.timedelta(days=1)).isoformat(),
    ]
    g, u = tmp_path / "gated", tmp_path / "ungated"
    # Nothing omitted: the proof's whole job is to compare the NON-D18
    # datasets, so there have to be some.
    _write_days(g, town.sl, dates=dates, render=render, gated=True,
                omit=frozenset())
    _write_days(u, town.sl, dates=dates, render=render, gated=False,
                omit=frozenset())
    return g, u


def test_the_proof_compares_bytes_and_names_the_dataset(two_packages):
    from prove_2_3_switch import DEFAULT_IGNORE, compare_packages, dataset_of

    g, u = two_packages
    assert dataset_of("observable/D17_aggregate_part003.parquet") == "D17_aggregate"
    assert dataset_of("observable/D18_part000.manifest.json") == "D18"
    assert dataset_of("run_diagnostics.json") is None

    # Ignoring nothing, the two differ - D18 is written differently by design.
    all_diffs = compare_packages(g, u, ignore=frozenset())
    assert any(d.dataset == "D18" for d in all_diffs), (
        "the gated and ungated arms wrote identical D18; the gate did nothing "
        "and any proof built on this would be vacuous"
    )
    # Ignoring D18, they are identical, which is the claim the 2019 switch rests
    # on.
    assert compare_packages(g, u, ignore=DEFAULT_IGNORE) == []


def test_the_proof_exits_nonzero_on_a_single_altered_byte(two_packages):
    from prove_2_3_switch import compare_packages, package_files

    g, u = two_packages
    target = next(
        p for rel, p in sorted(package_files(u).items())
        if rel.endswith(".parquet") and "D18" not in rel
    )
    raw = bytearray(target.read_bytes())
    # The LAST byte, not the first: a Parquet footer is where the magic and the
    # metadata live, so flipping a byte there is the realistic shape of a
    # difference and a size-only check would miss it.
    raw[-1] ^= 0x01
    target.write_bytes(bytes(raw))
    diffs = compare_packages(g, u)
    assert len(diffs) == 1
    assert diffs[0].kind == "bytes"
    assert diffs[0].dataset is not None


def test_the_proof_reports_a_missing_and_an_extra_file(two_packages, tmp_path):
    from prove_2_3_switch import compare_packages, package_files

    g, u = two_packages
    # Removed from the CANDIDATE, so it is absent from the candidate and the
    # kind is `only_in_b`. Removing it from the reference instead would also
    # report `only_in_a`, and the test would then not distinguish the two
    # directions at all.
    victim = next(
        rel for rel in sorted(package_files(g)) if "D18" not in rel
    )
    (g / victim).unlink()
    (g / "observable" / "D19_part099.parquet").write_bytes(b"not a parquet")
    diffs = compare_packages(g, u)
    assert {d.kind for d in diffs} == {"only_in_a", "only_in_b"}
    assert {d.relpath for d in diffs} == {
        victim, "observable/D19_part099.parquet"}


def test_a_truncated_file_is_a_size_difference(two_packages):
    from prove_2_3_switch import compare_packages, package_files

    g, u = two_packages
    target = next(
        p for rel, p in sorted(package_files(u).items())
        if rel.endswith(".parquet") and "D18" not in rel
    )
    raw = target.read_bytes()
    target.write_bytes(raw[:-16])
    diffs = compare_packages(g, u)
    assert [d.kind for d in diffs] == ["size"]
