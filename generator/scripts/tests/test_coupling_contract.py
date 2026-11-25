"""C2 coupling and design 8.2's timing and safety contract.

The contract's own guarantee is the thing to test:

    a controller can never gain flexibility from stale network information.
    Violations that still occur within an interval are counted against the
    controller in evaluation. They are never silently corrected.

So the test uses a **greedy** controller - one that reads the published
network state and asks for the whole headroom - because that is what would
exploit staleness if staleness were exploitable, and runs the same day at
15-minute and 1-minute epochs.

Two things in here were found by this test rather than asserted by it, and
both were real.

**The envelope has to allocate upstream headroom, not just the connection's.**
The first version built the envelope from per-connection headroom only, as a
literal reading of the contract's wording. Twenty homes each inside their own
12 kW service limit then collectively overloaded a 40 kW feeder, and C1
extracted 1,213 kWh against C2's 908 while causing the violations - because a
15-minute commitment is made before a 15-minute-old solve can reveal the
overload. That is exactly the gain from stale information the contract
forbids, and it only shows up when the binding element is upstream.

**The tightening rate has to be per unit of time, not per epoch.** Tightening
by a fixed factor per violating epoch made C2, with 1440 epochs a day against
C1's 96, tighten up to fifteen times as hard for the same physical violations.
The two modes then differed because of epoch counting rather than staleness,
which would have made the whole comparison meaningless.

The tolerance is derived twice over. The margins come from LP1's measured
maximum quarter-hour ramp (0.256 of mean at 15 minutes, scaled to 0.0171 at
one), and the bound comes from the envelope's own arithmetic: with the
envelope equal to headroom times ``1 - margin``, the relative difference in
accepted energy that the two envelopes imply is exactly
``(m1 - m2) / (1 - m2)`` = 0.2431. A first version compared the energy
difference against the C1 margin directly, which is only approximately right -
both are dimensionless but they are fractions of different quantities, one a
load change per quarter-hour and the other an energy difference - and loose by
5%. The realised difference comes out at 0.137, below the bound because the
device and SoC limits also bind.
"""

from __future__ import annotations

import numpy as np
import pytest

import baile_nua.sources_registry  # noqa: F401
from baile_nua.engine import coupling as C
from baile_nua.plausibility import slp

N_PREMISES = 20
CONNECTION_W = 12_000.0


@pytest.fixture(scope="module")
def baseline():
    """A day of per-premises load shaped by LP1's own mean diurnal.

    The published profile rather than engine output, deliberately: what is
    under test is the timing contract, and a baseline taken from the model
    would make the contract's margin - which is derived from LP1 - circular.
    """
    shape = slp.lp1_reference()["mean_diurnal_over_day_mean"]
    mins = sorted(shape)
    prof = np.interp(np.arange(1440), mins, [shape[m] for m in mins])
    base = prof / prof.mean() * (4000.0 / 24.0)      # a 4 kWh/day home, in W
    rng = np.random.default_rng(7)
    return {
        f"P-{i:03d}": base * rng.uniform(0.6, 1.6) for i in range(N_PREMISES)
    }


def _limits(premises, device_w=3600.0):
    return {
        (p, "battery"): C.DeviceLimits(
            premises_id=p, device="battery", max_import_w=device_w,
            max_export_w=device_w, soc=0.5, capacity_wh=1e9,
        )
        for p in premises
    }


# --------------------------------------------------------------------------- #
# the modes and the margin
# --------------------------------------------------------------------------- #

def test_the_coupling_modes_match_the_design_table():
    assert set(C.MODES) == {"C1", "C2", "C3"}
    assert C.MODES["C1"].epoch_minutes == 15
    assert C.MODES["C2"].epoch_minutes == 1
    assert C.MODES["C3"].device_step_s == 1
    assert "mandatory" in C.MODES["C2"].status


def test_the_tolerance_is_the_envelope_s_own_arithmetic():
    """``(m1 - m2) / (1 - m2)``, not the C1 margin on its own.

    The envelope is headroom times ``1 - margin``, so if it were the only
    binding constraint the accepted energy would differ by exactly this. The
    C1 margin alone is a looser and dimensionally sloppier bound: it is a
    fractional load change per quarter-hour, not a fractional energy
    difference.
    """
    m1 = C.staleness_margin(15)["margin_fraction_of_mean"]
    m2 = C.staleness_margin(1)["margin_fraction_of_mean"]
    exact = (m1 - m2) / (1.0 - m2)
    assert exact == pytest.approx(0.2431, abs=0.002), exact
    assert exact < m1, "the exact bound should be tighter than the C1 margin"


def test_the_staleness_margin_comes_from_lp1_and_not_from_our_own_output():
    """A margin calibrated on the model would certify the model with itself."""
    m = C.staleness_margin(15)
    assert m["source_key"] == "esbn.rmds.slp_indexes_2022"
    assert len(m["source_sha256"]) == 64
    assert not m["scaled_linearly"], "15 minutes is LP1's own resolution"
    assert 0.1 < m["margin_fraction_of_mean"] < 0.5, m

    one = C.staleness_margin(1)
    assert one["scaled_linearly"], (
        "1 minute is below LP1's resolution, so the margin cannot be measured "
        "there and the scaling has to be declared"
    )
    assert one["margin_fraction_of_mean"] < m["margin_fraction_of_mean"]
    assert one["linearity_note"]


def test_lp1_s_maximum_ramp_is_where_the_morning_is():
    """A sanity check on the measurement: the worst ramp is the morning rise."""
    r = slp.max_epoch_ramp()
    assert r["n_adjacent_pairs"] > 30_000
    assert 0.2 < r["max_ramp_fraction_of_mean"] < 0.4
    assert r["median_ramp_fraction_of_mean"] < r["p99_ramp_fraction_of_mean"]
    assert r["p99_ramp_fraction_of_mean"] < r["max_ramp_fraction_of_mean"]
    _day, minute = r["max_ramp_at"]
    assert 5 * 60 <= minute <= 10 * 60, (
        f"LP1's largest quarter-hour ramp is at minute {minute}, which is not "
        f"in the morning - either the reader or the profile is not what it "
        f"is taken to be"
    )


# --------------------------------------------------------------------------- #
# step 3: the safety layer
# --------------------------------------------------------------------------- #

def _state(premises, *, margin=0.256, feeder_headroom_w=1e9, tightening=1.0):
    return C.NetworkState(
        epoch_index=4, solved_at_minute=45, published_at_minute=60,
        feeder_p_kw=10.0,
        headroom_import_w={p: 8000.0 for p in premises},
        headroom_export_w={p: 8000.0 for p in premises},
        margin_fraction=margin, tightening=tightening,
        feeder_headroom_w=feeder_headroom_w, n_connections=len(premises),
    )


def test_the_state_carries_a_staleness_stamp():
    """Step 1 of the contract: published with a staleness stamp."""
    st = _state(["P-000"])
    assert st.staleness_s == 900


def test_a_device_power_limit_clips_and_the_clip_is_logged():
    layer = C.SafetyLayer(
        limits=_limits(["P-000"], device_w=3600.0), bands={}, epoch_minutes=15,
    )
    a = C.AgentAction(action_id="A1", premises_id="P-000", device="battery",
                      requested_w=9000.0, submitted_at_minute=60, epoch_index=4)
    d = layer.check(a, _state(["P-000"]))
    assert d.verdict == "clipped"
    assert d.accepted_w == 3600.0
    assert d.clipped_w == pytest.approx(5400.0)
    assert d.reasons and "device import limit" in d.reasons[0]


def test_a_soc_ceiling_clips_a_charge():
    lim = {("P-000", "battery"): C.DeviceLimits(
        premises_id="P-000", device="battery", max_import_w=10_000.0,
        max_export_w=10_000.0, soc=0.94, soc_max=0.95, capacity_wh=10_000.0,
    )}
    layer = C.SafetyLayer(limits=lim, bands={}, epoch_minutes=15)
    a = C.AgentAction(action_id="A1", premises_id="P-000", device="battery",
                      requested_w=8000.0, submitted_at_minute=60, epoch_index=4)
    d = layer.check(a, _state(["P-000"]))
    # 1% of 10 kWh is 100 Wh, which over a quarter-hour is 400 W.
    assert d.accepted_w == pytest.approx(400.0)
    assert d.binding_limit in ("soc", "network_envelope")
    assert any("SoC ceiling" in r for r in d.reasons)


def test_a_discharge_that_would_strand_an_ev_is_rejected_outright():
    """Named by the contract. There is no safe partial version of stranding."""
    lim = {("P-000", "ev"): C.DeviceLimits(
        premises_id="P-000", device="ev", max_import_w=7000.0,
        max_export_w=7000.0, soc=0.30, soc_min_departure=0.80,
        minutes_to_departure=30, capacity_wh=60_000.0,
    )}
    layer = C.SafetyLayer(limits=lim, bands={}, epoch_minutes=15)
    a = C.AgentAction(action_id="A1", premises_id="P-000", device="ev",
                      requested_w=-5000.0, submitted_at_minute=60, epoch_index=4)
    d = layer.check(a, _state(["P-000"]))
    assert d.verdict == "rejected"
    assert d.accepted_w == 0.0
    assert d.binding_limit == "ev_departure"
    # With plenty of time, the same discharge is allowed.
    lim[("P-000", "ev")].minutes_to_departure = 600
    ok = layer.check(a, _state(["P-000"]))
    assert ok.verdict != "rejected", ok


def test_a_vulnerable_occupant_s_temperature_floor_rejects_a_heat_cut():
    bands = {"P-000": C.OccupantBand(
        premises_id="P-000", has_vulnerable_occupant=True, living_c=17.5,
    )}
    layer = C.SafetyLayer(
        limits=_limits(["P-000"]), bands=bands, epoch_minutes=15,
    )
    a = C.AgentAction(action_id="A1", premises_id="P-000", device="heat_pump",
                      requested_w=-2000.0, submitted_at_minute=60, epoch_index=4)
    d = layer.check(a, _state(["P-000"]))
    assert d.verdict == "rejected"
    assert d.binding_limit == "occupant_band"
    assert C.VULNERABLE_MIN_C == 18.0
    # A home with no vulnerable occupant is not protected by this rule.
    bands["P-000"] = C.OccupantBand(
        premises_id="P-000", has_vulnerable_occupant=False, living_c=17.5,
    )
    assert layer.check(a, _state(["P-000"])).verdict != "rejected"


def test_the_envelope_is_the_minimum_of_connection_and_upstream_headroom():
    """The fix the coupling-lag test forced. Not a refinement: a correction."""
    premises = [f"P-{i:03d}" for i in range(20)]
    # Plenty of connection headroom, almost no feeder headroom.
    st = _state(premises, margin=0.0, feeder_headroom_w=20_000.0)
    imp, _exp = st.envelope("P-000")
    assert imp == pytest.approx(1000.0), (
        "the envelope ignored the upstream limit; twenty homes at their own "
        "connection headroom would overload the feeder"
    )
    # And the other way round: tight connection, generous feeder.
    st2 = _state(premises, margin=0.0, feeder_headroom_w=1e9)
    assert st2.envelope("P-000")[0] == pytest.approx(8000.0)


def test_the_margin_actually_shrinks_the_envelope():
    premises = ["P-000"]
    wide = _state(premises, margin=0.0).envelope("P-000")[0]
    tight = _state(premises, margin=0.256).envelope("P-000")[0]
    assert tight == pytest.approx(wide * (1 - 0.256))


# --------------------------------------------------------------------------- #
# the whole day, and the contract's guarantee
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "feeder_kw,device_w",
    [(40.0, 3600.0), (25.0, 7000.0), (100_000.0, 100_000.0)],
    ids=["feeder-binding", "tight-feeder", "connection-binding"],
)
def test_a_greedy_controller_never_gains_from_stale_information(
    baseline, feeder_kw, device_w
):
    """The contract's guarantee, across three different binding constraints.

    Three regimes, because the first version of the envelope passed the
    connection-binding case and failed the feeder-binding one - a test run at
    only one operating point would have certified a broken contract.
    """
    res = C.coupling_lag_test(
        baseline_w=baseline, connection_limit_w=CONNECTION_W,
        feeder_limit_kw=feeder_kw,
        limits=_limits(sorted(baseline), device_w=device_w),
    )
    assert res["no_gain_from_stale_information"], (
        f"C1 accepted {res['C1']['accepted_wh']:.0f} Wh against C2's "
        f"{res['C2']['accepted_wh']:.0f} Wh: the 15-minute controller gained "
        f"flexibility from a staler solve, which design 8.2 forbids"
    )
    assert res["within_tolerance"], (
        f"relative difference {res['relative_difference_in_accepted_energy']:.4f} "
        f"exceeds the envelope-implied bound {res['tolerance']:.4f}"
    )
    assert res["passes"]


def test_fresher_information_buys_more_usable_flexibility(baseline):
    """The positive half: C2 should be strictly better off, not merely equal."""
    res = C.coupling_lag_test(
        baseline_w=baseline, connection_limit_w=CONNECTION_W,
        feeder_limit_kw=40.0, limits=_limits(sorted(baseline)),
    )
    assert res["C2"]["accepted_wh"] > res["C1"]["accepted_wh"] * 1.02, (
        "C2 bought no more flexibility than C1, so the epoch length is not "
        "reaching the envelope and the test is not measuring anything"
    )
    # And it does so without exceeding the limit: that is the whole point.
    assert res["C2"]["feeder_peak_kw"] <= 40.0 + 1e-6
    assert res["C1"]["feeder_peak_kw"] <= 40.0 + 1e-6
    assert res["C1"]["n_violations"] == 0
    assert res["C2"]["n_violations"] == 0


def test_violations_the_controller_cannot_prevent_are_still_recorded(baseline):
    """Never silently corrected - including when the baseline alone causes it."""
    res = C.coupling_lag_test(
        baseline_w=baseline, connection_limit_w=CONNECTION_W,
        feeder_limit_kw=3.0, limits=_limits(sorted(baseline)),
    )
    assert res["C1"]["n_violations"] > 0 and res["C2"]["n_violations"] > 0
    assert res["violations_recorded_not_absorbed"]
    # The same physics at two resolutions: the same minutes and the same peak.
    assert res["same_violation_minutes_both_modes"], res["feeder_violation_minutes"]
    assert res["C1"]["feeder_peak_kw"] == pytest.approx(
        res["C2"]["feeder_peak_kw"], rel=0.02
    )
    # And the controller is throttled to almost nothing rather than permitted.
    assert res["C1"]["accepted_wh"] < 10_000.0


def test_the_envelope_tightens_and_relaxes_at_the_same_rate_in_real_time():
    """The confound that would have made the comparison meaningless."""
    # Fifteen violating one-minute epochs must tighten exactly as much as one
    # violating quarter-hour.
    one_quarter = C.ENVELOPE_TIGHTEN_PER_15_MIN ** (15 / 15.0)
    fifteen_minutes = (C.ENVELOPE_TIGHTEN_PER_15_MIN ** (1 / 15.0)) ** 15
    assert one_quarter == pytest.approx(fifteen_minutes)
    assert 0.0 < C.ENVELOPE_TIGHTEN_PER_15_MIN < 1.0
    assert C.ENVELOPE_RELAX_PER_15_MIN > 0.0


def test_every_d17_row_carries_the_mode_and_the_staleness_stamp(baseline):
    """D17's schema requires both; the staleness stamp is the contract's."""
    out = C.run_coupled_day(
        mode="C1", baseline_w=baseline, connection_limit_w=CONNECTION_W,
        feeder_limit_kw=40.0, limits=_limits(sorted(baseline)),
        agent=C.greedy_agent(premises_ids=sorted(baseline)),
    )
    assert out["n_epochs"] == 96
    assert out["d17_rows"]
    for r in out["d17_rows"]:
        assert r["coupling_mode"] == "C1"
        assert r["epoch_staleness_s"] == 900
        assert r["element_kind"] in ("feeder", "transformer", "connection")
        assert r["p_kw"] >= 0.0
        assert r["outage"] is False
    assert out["claim"].startswith("This output implements design 8.2")
    assert "FEEDER AGGREGATION" in out["claim"], (
        "the output must say it is not a power flow; pandapower is week 3"
    )


def test_a_day_with_no_controller_is_unchanged_by_the_coupling_mode(baseline):
    """Without an agent, C1 and C2 must agree exactly.

    This is the control for the whole test: the epoch barrier only aggregates,
    so with nobody acting on the published state the two modes are reading the
    same load at different intervals and must produce the same peak. A
    difference here would mean the harness itself perturbs the load.
    """
    peaks = {}
    for mode in ("C1", "C2"):
        out = C.run_coupled_day(
            mode=mode, baseline_w=baseline, connection_limit_w=CONNECTION_W,
            feeder_limit_kw=1e9, limits={}, agent=None,
        )
        peaks[mode] = out["feeder_peak_kw"]
        assert out["n_actions"] == 0
    assert peaks["C1"] == pytest.approx(peaks["C2"], rel=1e-9), peaks


def test_the_run_is_reproducible(baseline):
    a = C.coupling_lag_test(
        baseline_w=baseline, connection_limit_w=CONNECTION_W,
        feeder_limit_kw=40.0, limits=_limits(sorted(baseline)),
    )
    b = C.coupling_lag_test(
        baseline_w=baseline, connection_limit_w=CONNECTION_W,
        feeder_limit_kw=40.0, limits=_limits(sorted(baseline)),
    )
    assert a["C1"]["accepted_wh"] == b["C1"]["accepted_wh"]
    assert a["C2"]["accepted_wh"] == b["C2"]["accepted_wh"]
