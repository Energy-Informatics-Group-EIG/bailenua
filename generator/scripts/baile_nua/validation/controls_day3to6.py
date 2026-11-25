"""Negative controls for days 3 to 6, as design 9.3 names them.

Day 3  a forbidden-field batch; a planted position bias
Day 4  a person in two places at once; a heat-balance leak
Day 5  an export carrying an occupancy field; a non-deterministic render
Day 6  injected shared mutable state

Each control declares what it is testing and asserts the *reason* for the
failure, not merely that something failed.  That distinction is the whole
value: a control that passes because the harness crashed has told you nothing,
and :func:`baile_nua.validation.negative_control.run_one` classifies that as
``HARNESS_DEFECT`` rather than as a pass.

The day-5 occupancy-field control is deliberately *not* a duplicate of
NC-D1-02.  That one hands a forbidden column to the schema audit directly.
This one goes through ``build_export``, the function a real exporter would
call, and plants the field after the export is built - which is the way the
field would actually arrive in practice, from a later edit downstream of the
function that was designed to make it impossible.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import numpy as np
import pandas as pd

from baile_nua.validation.negative_control import NegativeControl, register

__all__ = ["CONTROL_IDS"]

CONTROL_IDS: tuple[str, ...] = (
    "NC-D3-01", "NC-D3-02",
    "NC-D4-01", "NC-D4-02",
    "NC-D5-01", "NC-D5-02",
    "NC-D6-01",
)

_MINUTES = 1440


# --------------------------------------------------------------------------- #
# Day 3 — MIMIC
# --------------------------------------------------------------------------- #

def _d25_with_forbidden_field() -> pd.DataFrame:
    """A D25 participant frame carrying an ADR-004 forbidden field.

    D25 is the MIMIC-derived OBS dataset, and it declares
    ``forbidden_field_patterns`` precisely so that health, fitness, mobility,
    medical, country-of-birth, diagnosis and disability field names are refused
    by name rather than by review.

    Note what this control does NOT test: MIMIC's own ``ProfileService``
    rejecting such a field at submission. That is T1, which runs against the
    live local instance and is reported separately with its five HTTP 422
    responses. Re-testing it here against a local re-implementation would prove
    only that two of my own functions agree.
    """
    return pd.DataFrame([
        {
            "participant_id": "11111111-1111-4111-8111-111111111111",
            "consent_version": "SYNTHETIC-HRSD-v1-BN-panel",
            "age_band": "35-44",
            "reported_sex": "F",
            "household_size": 3,
            "region_nuts3": "IE053",
            # Forbidden outright by ADR-004 (GDPR Article 9 special category).
            "medical_device_dependence": "oxygen concentrator",
        }
    ])


def _audit_d25(frame: pd.DataFrame) -> None:
    from baile_nua.schema.access import assert_no_forbidden_patterns

    assert_no_forbidden_patterns(frame.columns, "D25")
    raise AssertionError(
        "assert_no_forbidden_patterns accepted a D25 frame naming "
        "medical_device_dependence, which ADR-004 forbids"
    )


def _audit_clean_d25(frame: pd.DataFrame) -> None:
    from baile_nua.schema.access import assert_no_forbidden_patterns

    assert_no_forbidden_patterns(
        [c for c in frame.columns if c != "medical_device_dependence"], "D25"
    )


register(NegativeControl(
    control_id="NC-D3-01",
    title="A D25 participant frame carrying an ADR-004 forbidden field",
    design_ref="9.3 day 3; 5.14; MIMIC ADR-004; R09",
    intended_test="baile_nua.schema.access.assert_no_forbidden_patterns",
    expected_exception=__import__(
        "baile_nua.schema.access", fromlist=["LeakageError"]
    ).LeakageError,
    expected_message="medical_device_dependence",
    build=_d25_with_forbidden_field,
    invoke=_audit_d25,
    must_still_pass=(
        ("the same frame without the forbidden column is accepted",
         _audit_clean_d25),
    ),
))


class PositionBiasDetected(AssertionError):
    """The position-bias check found a bias, which is what T10 is for."""


def _planted_position_bias() -> pd.DataFrame:
    """Responses in which display position drives the choice.

    The planted effect is strong and simple on purpose: a control's job is to
    prove the detector fires, so the signal must be unambiguous. T10's real
    arm, with a 1.6 odds multiplier, is the graded version.
    """
    rng = np.random.default_rng(20261008)
    n = 4000
    rows = []
    for i in range(n):
        order = list(rng.permutation(["SO", "RC", "CP", "AL"]))
        # Position 1 is chosen 70% of the time regardless of what is in it.
        pos = 1 if rng.random() < 0.70 else int(rng.integers(2, 5))
        rows.append({
            "response_id": f"R-{i:05d}",
            "chosen_signal": order[pos - 1],
            "chosen_display_position": pos,
        })
    return pd.DataFrame(rows)


def _check_position_bias(frame: pd.DataFrame) -> None:
    from scipy import stats

    counts = frame.chosen_display_position.value_counts().reindex(
        [1, 2, 3, 4], fill_value=0
    )
    # Under no bias, each position is chosen equally often, because the display
    # order is randomised per response.
    chi2, p = stats.chisquare(counts.to_numpy())
    share_1 = float(counts[1]) / float(counts.sum())
    if p < 1e-6:
        raise PositionBiasDetected(
            f"display position predicts the choice: position 1 chosen "
            f"{share_1:.1%} of the time against an expected 25.0%, "
            f"chi2={chi2:.1f}, p={p:.2e}. Design 5.14's T10 requires position "
            f"to carry no information once the order is randomised."
        )
    raise AssertionError(
        f"the position-bias check did not fire on a planted 70% "
        f"first-position bias (chi2={chi2:.1f}, p={p:.3g})"
    )


def _check_unbiased_is_quiet(frame: pd.DataFrame) -> None:
    """The same check on unbiased responses must NOT fire.

    Without this, a control passes just as well when the check always fires.
    """
    from scipy import stats

    rng = np.random.default_rng(99)
    pos = rng.integers(1, 5, size=len(frame))
    counts = pd.Series(pos).value_counts().reindex([1, 2, 3, 4], fill_value=0)
    _chi2, p = stats.chisquare(counts.to_numpy())
    if p < 1e-6:
        raise AssertionError(
            f"the position-bias check fires on UNBIASED responses (p={p:.2e}); "
            f"it would report a bias in any dataset"
        )


register(NegativeControl(
    control_id="NC-D3-02",
    title="Responses in which display position drives the choice",
    design_ref="9.3 day 3; 5.14 T10",
    intended_test="chi-square on chosen_display_position (T10)",
    expected_exception=PositionBiasDetected,
    expected_message="display position predicts the choice",
    build=_planted_position_bias,
    invoke=_check_position_bias,
    must_still_pass=(
        ("the same check is quiet on unbiased responses", _check_unbiased_is_quiet),
    ),
))


# --------------------------------------------------------------------------- #
# Day 4 — presence and physics
# --------------------------------------------------------------------------- #

def _person_in_two_places() -> pd.DataFrame:
    """A D11 presence frame in which one person is in two buildings at once."""
    base = pd.Timestamp("2022-03-01T08:00:00Z")
    return pd.DataFrame([
        {"presence_id": "PR-1", "person_id": "P-000001",
         "start": base, "end": base + pd.Timedelta(minutes=120),
         "location_kind": "building", "location_id": "B-000001", "zone": "living"},
        # Overlaps the first by an hour, in a different building.
        {"presence_id": "PR-2", "person_id": "P-000001",
         "start": base + pd.Timedelta(minutes=60),
         "end": base + pd.Timedelta(minutes=180),
         "location_kind": "building", "location_id": "B-000002", "zone": "kitchen"},
        {"presence_id": "PR-3", "person_id": "P-000002",
         "start": base, "end": base + pd.Timedelta(minutes=60),
         "location_kind": "building", "location_id": "B-000001", "zone": "living"},
    ])


def _check_double_occupancy(frame: pd.DataFrame) -> None:
    from baile_nua.validation.invariants import check_no_double_occupancy

    from baile_nua.validation.invariants import assert_all

    assert_all([check_no_double_occupancy(frame)])
    raise AssertionError(
        "check_no_double_occupancy accepted a person who is in two buildings "
        "at the same time"
    )


def _check_single_occupancy_is_quiet(frame: pd.DataFrame) -> None:
    from baile_nua.validation.invariants import check_no_double_occupancy

    from baile_nua.validation.invariants import assert_all

    ok = frame[frame.presence_id != "PR-2"]
    assert_all([check_no_double_occupancy(ok)])


register(NegativeControl(
    control_id="NC-D4-01",
    title="A person present in two buildings at the same time",
    design_ref="9.3 day 4; 7.2 presence invariant; R15",
    intended_test="baile_nua.validation.invariants.check_no_double_occupancy",
    expected_exception=__import__(
        "baile_nua.validation.invariants", fromlist=["InvariantViolation"]
    ).InvariantViolation,
    expected_message="P-000001",
    build=_person_in_two_places,
    invoke=_check_double_occupancy,
    must_still_pass=(
        ("the same frame without the overlap passes",
         _check_single_occupancy_is_quiet),
    ),
))


def _leaky_heat_balance() -> pd.DataFrame:
    """A daily energy frame in which the terms do not close.

    The leak is 3%: large enough to be a real error and small enough that it
    would pass a plot. A 50% leak would prove nothing about the threshold.
    """
    rows = []
    for i in range(20):
        appliance = 9_000.0 + 100.0 * i
        hvac = 12_000.0
        # Design 7.2's sign convention: pv_wh is POSITIVE generation and is
        # SUBTRACTED. Getting that backwards is exactly the kind of error this
        # invariant exists to catch, and the first version of this control got
        # it backwards - which the control's own "must still pass" check found.
        pv = 1_500.0
        net = appliance + hvac - pv
        rows.append({
            "building_id": f"B-{i:06d}",
            "date": "2022-01-15",
            "appliance_wh": appliance, "hvac_wh": hvac, "ev_wh": 0.0,
            "bess_charge_wh": 0.0, "bess_discharge_wh": 0.0,
            "pv_wh": pv,
            # 3% short: the terms no longer sum to the meter.
            "net_meter_wh": net * 0.97,
            "import_wh": net * 0.97, "export_wh": 0.0,
        })
    return pd.DataFrame(rows)


def _check_closure(frame: pd.DataFrame) -> None:
    from baile_nua.validation.invariants import check_energy_closure

    from baile_nua.validation.invariants import assert_all

    assert_all([check_energy_closure(frame)])
    raise AssertionError(
        "check_energy_closure accepted a daily balance that is 3% short"
    )


def _check_closed_balance_is_quiet(frame: pd.DataFrame) -> None:
    from baile_nua.validation.invariants import check_energy_closure

    ok = frame.copy()
    ok["net_meter_wh"] = (
        ok.appliance_wh + ok.hvac_wh + ok.ev_wh + ok.bess_charge_wh
        - ok.pv_wh - ok.bess_discharge_wh
    )
    ok["import_wh"] = ok.net_meter_wh.clip(lower=0.0)
    from baile_nua.validation.invariants import assert_all

    assert_all([check_energy_closure(ok)])


register(NegativeControl(
    control_id="NC-D4-02",
    title="A daily energy balance with a 3% heat-balance leak",
    design_ref="9.3 day 4; 7.2 energy closure",
    intended_test="baile_nua.validation.invariants.check_energy_closure",
    expected_exception=__import__(
        "baile_nua.validation.invariants", fromlist=["InvariantViolation"]
    ).InvariantViolation,
    expected_message="closure",
    build=_leaky_heat_balance,
    invoke=_check_closure,
    must_still_pass=(
        ("the same frame with the terms summed correctly passes",
         _check_closed_balance_is_quiet),
    ),
))


# --------------------------------------------------------------------------- #
# Day 5 — export and render
# --------------------------------------------------------------------------- #

def _export_with_occupancy_column() -> pd.DataFrame:
    """A real D19 export, with an occupancy column added afterwards.

    This is how the field would actually arrive. ``build_export`` is written so
    that it *cannot* emit occupancy - it never receives it - so the realistic
    failure is a later edit joining something on downstream, after the function
    designed to make it impossible has already returned.
    """
    from baile_nua.edge.export import EXPORT_CONFIGS, build_export

    idx = pd.date_range("2022-03-01", periods=_MINUTES, freq="1min", tz="UTC")
    rng = np.random.default_rng(7)
    net = rng.uniform(100.0, 3_000.0, size=_MINUTES)
    frame = build_export(
        premises_id="PRM-OPAQUE-0001", minute_index=idx,
        net_import_w=net, net_export_w=np.zeros(_MINUTES),
        config=EXPORT_CONFIGS["home_30min"],
    ).reset_index(drop=True)
    frame["occupancy_count"] = rng.integers(0, 5, size=len(frame))
    return frame


def _write_export(frame: pd.DataFrame) -> None:
    import tempfile
    from pathlib import Path

    from baile_nua.io import write_dataset

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "observable" / "D19_nc.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        write_dataset(frame, "D19", path)
    raise AssertionError(
        "write_dataset wrote a D19 export carrying occupancy_count. R09 and "
        "E0-8 require that no occupancy field is ever transmitted."
    )


def _write_clean_export(frame: pd.DataFrame) -> None:
    import tempfile
    from pathlib import Path

    from baile_nua.io import write_dataset

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "observable" / "D19_ok.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        write_dataset(frame.drop(columns=["occupancy_count"]), "D19", path)


register(NegativeControl(
    control_id="NC-D5-01",
    title="An edge export with an occupancy column added after build_export",
    design_ref="9.3 day 5; 5.1 leakage test; R09 / E0-8; 7.8",
    intended_test="baile_nua.io.write_dataset (schema access audit)",
    expected_exception=__import__(
        "baile_nua.schema.access", fromlist=["LeakageError"]
    ).LeakageError,
    expected_message="occupancy",
    build=_export_with_occupancy_column,
    invoke=_write_export,
    must_still_pass=(
        ("the same export without the column writes cleanly", _write_clean_export),
    ),
))


class RenderNotDeterministic(AssertionError):
    """The same cycle rendered twice gave different power."""


@dataclasses.dataclass
class _WobblyRender:
    """A render that draws fresh entropy instead of using the cycle's seed.

    This is the realistic version of the fault: not a deliberately random
    render, but one that reaches for ``np.random`` because the seed was
    inconvenient to thread through. The result looks perfectly plausible - the
    right magnitude, the right shape - and is different every time.
    """

    signature_seed: int

    def render(self, n: int) -> np.ndarray:
        from baile_nua.devices.signatures import signature_for

        sig = signature_for("washing_machine")
        x = np.array([a for a, _ in sig.shape])
        y = np.array([b for _, b in sig.shape])
        base = np.interp(np.linspace(0, 1, n, endpoint=False), x, y) * sig.peak_w
        return base * (1.0 + 0.02 * np.random.default_rng().normal(size=n))


def _build_wobbly_render() -> _WobblyRender:
    return _WobblyRender(signature_seed=12345)


def _check_render_determinism(r: _WobblyRender) -> None:
    a = r.render(160)
    b = r.render(160)
    if not np.array_equal(a, b):
        worst = float(np.max(np.abs(a - b)))
        raise RenderNotDeterministic(
            f"the same cycle rendered twice from the same signature_seed "
            f"differs by up to {worst:.1f} W. Design 8.2 requires every draw "
            f"to come from the counter-based stream keyed by the entity and "
            f"the draw counter, so a render is a function of its seed alone."
        )
    raise AssertionError("the planted non-deterministic render did not differ")


def _real_render_is_deterministic(_r: _WobblyRender) -> None:
    """The real renderer must be byte-identical across calls."""
    from baile_nua.devices.signatures import render_cycle, signature_for

    sig = signature_for("washing_machine")
    kw = dict(duration_s=sig.nominal_duration_s,
              energy_wh=sig.nominal_energy_wh, seed=4242)
    a = render_cycle(sig, **kw)
    b = render_cycle(sig, **kw)
    if not np.array_equal(a, b):
        raise AssertionError(
            "the REAL renderer is not deterministic for a fixed seed, which "
            "is a defect in the system rather than in this control"
        )


register(NegativeControl(
    control_id="NC-D5-02",
    title="A non-deterministic appliance render",
    design_ref="9.3 day 5; 8.2 reproducibility contract; 5.6",
    intended_test="byte equality of two renders from one signature_seed",
    expected_exception=RenderNotDeterministic,
    expected_message="differs by up to",
    build=_build_wobbly_render,
    invoke=_check_render_determinism,
    must_still_pass=(
        ("the real renderer is byte-identical for a fixed seed",
         _real_render_is_deterministic),
    ),
))


# --------------------------------------------------------------------------- #
# Day 6 — shared mutable state
# --------------------------------------------------------------------------- #

class SharedStateDetected(AssertionError):
    """Two households' results depend on the order they were run in."""


class _LeakyRunner:
    """A runner with one piece of state shared between households.

    The planted fault is a single accumulator - a running total of the day's
    energy that the per-household step both reads and writes. It is exactly the
    kind of thing that gets added for a progress bar, and under threads it
    makes every household's result depend on which others have already run.

    The accumulator is added to the result rather than merely recorded, because
    a shared counter that nothing reads is not a correctness problem and a
    control must plant the problem it claims to plant.
    """

    def __init__(self) -> None:
        self.running_total_wh = 0.0

    def household(self, hh_id: str, base_wh: float) -> dict[str, float]:
        # Read-modify-write on state no other household should see.
        self.running_total_wh += base_wh
        return {
            "household_id": hh_id,
            "energy_wh": base_wh + 1e-6 * self.running_total_wh,
        }

    def run(self, order: list[tuple[str, float]], workers: int) -> list[dict[str, float]]:
        from concurrent.futures import ThreadPoolExecutor

        self.running_total_wh = 0.0
        if workers > 1:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {
                    hh: pool.submit(self.household, hh, wh) for hh, wh in order
                }
                return [futures[hh].result() for hh, _ in sorted(order)]
        return [self.household(hh, wh) for hh, wh in order]


def _build_leaky_runner() -> _LeakyRunner:
    return _LeakyRunner()


def _check_no_shared_state(runner: _LeakyRunner) -> None:
    rng = np.random.default_rng(11)
    order = [
        (f"H-{i:06d}", float(rng.uniform(5_000, 25_000))) for i in range(50)
    ]
    serial = runner.run(sorted(order), workers=1)
    reversed_order = runner.run(sorted(order, reverse=True), workers=1)
    by_id_a = {r["household_id"]: r["energy_wh"] for r in serial}
    by_id_b = {r["household_id"]: r["energy_wh"] for r in reversed_order}
    changed = [k for k in by_id_a if by_id_a[k] != by_id_b[k]]
    if changed:
        k = sorted(changed)[0]
        raise SharedStateDetected(
            f"{len(changed)} of {len(by_id_a)} households changed their result "
            f"when the estate was run in a different order (first: {k}, "
            f"{by_id_a[k]:.6f} against {by_id_b[k]:.6f} Wh). Design 8.2 "
            f"forbids shared mutable state: a household's day must be a "
            f"function of its own state alone."
        )
    raise AssertionError(
        "the planted shared accumulator did not change any household's result"
    )


def _real_runner_has_no_order_dependence(_r: _LeakyRunner) -> None:
    """The real per-household step must be order-independent.

    Checked on the real engine, not on a stand-in: the control is only worth
    having if the thing it protects is actually protected.
    """
    import baile_nua.sources_registry  # noqa: F401
    from baile_nua.engine.calendar import build_calendar
    from baile_nua.engine.e1_run import build_slice
    from baile_nua.engine.run import EstateRunner
    from baile_nua.population.synthesise import synthesise_t0
    from baile_nua.weather.site import build_realisation

    seed = 20261008
    town = synthesise_t0(master_seed=seed)
    wx = build_realisation(2022, master_seed=seed, days=2)
    cal = build_calendar(2022, weather_hourly=wx.site_hourly)[:1]
    sl = build_slice(town, master_seed=seed, calendar=cal)

    def run(workers: int) -> dict[str, dict[str, Any]]:
        r = EstateRunner(
            master_seed=seed, households=sl.households, buildings=sl.buildings,
            thermal=sl.thermal, owned=sl.owned, pv=sl.pv,
            weather_minute=wx.site_minute, calendar=cal,
        )
        r.initialise()
        day = cal[0]
        res = r.run_day(day, r.phase_a(day, sl.disruptions), workers=workers)
        return {row["building_id"]: row for row in res.energy_rows}

    a, b = run(1), run(8)
    assert set(a) == set(b)
    for bid in sorted(a):
        if a[bid] != b[bid]:
            raise AssertionError(
                f"the REAL engine gave {bid} a different day at 8 workers than "
                f"at 1. That is a defect in the engine, not in this control."
            )


register(NegativeControl(
    control_id="NC-D6-01",
    title="Shared mutable state between households in the day loop",
    design_ref="9.3 day 6; 8.2 reproducibility contract; no shared mutable state",
    intended_test="order-independence of per-household results",
    expected_exception=SharedStateDetected,
    expected_message="changed their result",
    build=_build_leaky_runner,
    invoke=_check_no_shared_state,
    must_still_pass=(
        ("the real engine gives identical rows at 1 and 8 workers",
         _real_runner_has_no_order_dependence),
    ),
))
