"""U31's paired test needs the same sample in both arms, and once it did not.

Week 3 step 1 sourced the fabric from SEAI's assessed distribution, which
moved every dwelling's specific heat loss. The U31 selector **contrasts on
specific heat loss** — that contrast is the point of the slice (D-052) — so
the membership moved with it: only **20 of 60** dwellings survived into the
new selection.

Two things went wrong and only one of them was the selector.

The paired `ttest_rel` returned NaN, because 40 dwellings were present in a
single arm. That is the correct arithmetic for an impossible test. But the
direction was then reported as ``"down" if delta.mean() < 0 else "up"``, and
``nan < 0`` is ``False`` — so an unmeasurable result was printed as the
*predicted* direction for a group whose ratio had in fact moved the other way.
A pre-registered criterion is worth nothing if the reporting can quietly
satisfy it.
"""

from __future__ import annotations

import math

import pytest

import baile_nua.sources_registry  # noqa: F401
from baile_nua.validation.heldout_u31 import (
    U31MembershipError,
    _direction,
    gradient_report,
)


def test_a_nan_change_is_never_reported_as_a_direction():
    """The bug that flattered a failing result."""
    assert _direction(float("nan")) == "undetermined"
    assert _direction(-0.5) == "down"
    assert _direction(0.5) == "up"
    assert _direction(0.0) == "up"          # a tie is not a fall
    # And the old expression's behaviour, for the record: it would have said
    # "up" for a NaN, which is what happened.
    nan = float("nan")
    assert ("down" if nan < 0 else "up") == "up"


def test_an_unpaired_comparison_raises_instead_of_returning_nan(tmp_path):
    """A gradient report over two different samples must refuse, not report."""
    import json

    import numpy as np

    def write(arm: str, building_ids: list[str]) -> None:
        rows = []
        for i, bid in enumerate(building_ids):
            rows.append({
                "building_id": bid,
                "build_year": 1975 if i % 2 == 0 else 2010,
                "ber_band": "C2", "floor_area_m2": 100.0,
                "heating_fuel": "natural gas",
                "space_heat_kwh_yr": 5000.0, "meter_gas_kwh_yr": 9000.0,
                "d24_gas_target_kwh_yr": 10000.0,
                "temp_living_mean_c": 19.5,
            })
        d = {"annual_electricity": {"per_dwelling": rows},
             "slice": {"estate_selection": {}}}
        (tmp_path / arm).mkdir(parents=True, exist_ok=True)
        (tmp_path / arm / "diagnostics.json").write_text(json.dumps(d))

    # Overlapping but not identical membership: exactly the week 3 situation.
    write("off", [f"B-{i:03d}" for i in range(20)])
    write("on", [f"B-{i:03d}" for i in range(10, 30)])
    with pytest.raises(U31MembershipError, match="only one arm"):
        gradient_report(tmp_path)


def test_identical_membership_is_accepted(tmp_path):
    """The control: the same sample in both arms must work."""
    import json

    def write(arm: str, offset: float) -> None:
        rows = []
        for i in range(24):
            rows.append({
                "building_id": f"B-{i:03d}",
                "build_year": 1975 if i % 2 == 0 else 2010,
                "ber_band": "C2", "floor_area_m2": 100.0,
                "heating_fuel": "natural gas",
                "space_heat_kwh_yr": 5000.0,
                # A real gap between the groups, because that is what the
                # slice is selected for: old stock over-consumes, new under.
                "meter_gas_kwh_yr": (
                    (12000.0 if i % 2 == 0 else 7000.0)
                    + offset * (1 + i % 3)
                ),
                "d24_gas_target_kwh_yr": 10000.0,
                "temp_living_mean_c": 19.5,
            })
        d = {"annual_electricity": {"per_dwelling": rows},
             "slice": {"estate_selection": {}}}
        (tmp_path / arm).mkdir(parents=True, exist_ok=True)
        (tmp_path / arm / "diagnostics.json").write_text(json.dumps(d))

    write("off", 0.0)
    write("on", -200.0)
    rep = gradient_report(tmp_path)
    for group in ("old", "new"):
        block = rep["paired_by_dwelling"][group]
        assert block["direction_observed"] in ("down", "up")
        assert not math.isnan(block["p"])
        assert block["direction_observed"] == "down"


def test_the_selector_can_freeze_its_membership():
    """What makes a before/after comparison paired at all.

    Freezing to the PRE-change selection is the neutral choice: it is the
    sample that existed before anything was touched. Re-selecting after a
    change and comparing against the old selection would be choosing the
    sample after seeing the model, which is what a held-out set exists to
    prevent.
    """
    from baile_nua.engine.slice_u31 import select_heldout_slice
    from baile_nua.population.synthesise import synthesise_t0

    town = synthesise_t0(master_seed=20261008)
    fresh = select_heldout_slice(town, n_homes=60, master_seed=20261008)
    frozen = select_heldout_slice(
        town, n_homes=60, master_seed=20261008,
        frozen_household_ids=tuple(fresh.household_ids),
    )
    assert list(frozen.household_ids) == list(fresh.household_ids)
    assert frozen.diagnostics["frozen"] is True
    assert frozen.diagnostics["n_homes"] == 60
    assert sum(frozen.diagnostics["groups"].values()) == 60
    # A frozen id that is not in the town is refused rather than dropped.
    from baile_nua.engine.slice_u31 import U31Infeasible

    with pytest.raises(U31Infeasible, match="not in the town"):
        select_heldout_slice(
            town, n_homes=60, master_seed=20261008,
            frozen_household_ids=("H-DOES-NOT-EXIST",),
        )
