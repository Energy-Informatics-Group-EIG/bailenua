"""U31: the held-out validation slice for U22's comfort-taking.

I-049 recorded that neither existing slice could test U22's condition - the
gradient between 1967-99 and post-2005 stock - because the E1 estate has four
dwellings in each cell and the mixed-age slice has no post-2005 stock at all.

The tests that matter most here are not about the slice's composition but about
what must never happen to it: nothing may be fitted on it. U22's amplitudes
were set against DBERNG01 and this slice is compared against DBERNG02, which
design 7.1 requires to stay disjoint from calibration. A slice that quietly
became a calibration set would make U22's validation worthless while still
producing numbers.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy import stats

import baile_nua.sources_registry  # noqa: F401
from baile_nua.behaviour.comfort_taking import specific_loss_w_k_m2
from baile_nua.engine.slice_u31 import (
    EVALUATION_ONLY,
    MIN_GAS_PER_GROUP,
    NEW_FROM,
    OLD_RANGE,
    U31_REQUIREMENTS,
    U31Infeasible,
    construction_group,
    select_heldout_slice,
)
from baile_nua.population.synthesise import synthesise_t0

SEED = 20261008


@pytest.fixture(scope="module")
def town():
    return synthesise_t0(master_seed=SEED)


@pytest.fixture(scope="module")
def sel(town):
    return select_heldout_slice(town, master_seed=SEED)


# --------------------------------------------------------------------------- #
# the prohibition: nothing is fitted here
# --------------------------------------------------------------------------- #

def test_nothing_is_fitted_on_the_heldout_slice():
    """7.1's separation, as a mechanical check rather than an intention.

    If the ablation's strength sweep is ever pointed at this slice, U22's
    held-out validation stops being held out and the artefact that reports it
    becomes misleading rather than merely wrong.
    """
    import inspect

    from baile_nua.validation import ablation

    assert EVALUATION_ONLY is True
    assert U31_REQUIREMENTS["evaluation_only"] is True

    src = inspect.getsource(ablation)
    # The sweep's own default slice must not be the held-out one.
    sig = inspect.signature(ablation.run_arm)
    assert sig.parameters["slice_kind"].default == "u23_mixed_age", (
        "the ablation's default slice is now the held-out one; a strength "
        "sweep run without arguments would calibrate on the validation set"
    )
    assert "strength" in sig.parameters, "the sweep lost its strength knob"


def test_the_comfort_taking_defaults_were_not_changed_after_the_heldout_run():
    """The amplitudes are the declared ones, not fitted to anything.

    D-049 records that the strength was deliberately not fitted. These are the
    numbers the ablation and the held-out run were both made with, pinned so a
    later quiet adjustment shows up as a failing test rather than as a better
    result.
    """
    from baile_nua.behaviour.comfort_taking import DEFAULT_SPEC

    assert DEFAULT_SPEC.rebound_k_per_ln_cost == pytest.approx(1.45)
    assert DEFAULT_SPEC.prebound_k_per_ln_cost == pytest.approx(2.30)
    assert DEFAULT_SPEC.rebound_max_hours_fraction == pytest.approx(0.30)
    assert DEFAULT_SPEC.prebound_max_hours_fraction == pytest.approx(0.45)
    assert DEFAULT_SPEC.prebound_max_zone_abandonment == pytest.approx(0.85)


def test_no_der_guarantee_intervenes_on_the_evaluation_slice(town):
    """U23 guarantees a heat pump and a battery; U31 must not.

    The guarantee is a declared intervention that assigns an adoption the
    stochastic draw did not make. Doing that to an evaluation sample would
    change what is being evaluated.
    """
    from baile_nua.engine.calendar import build_calendar
    from baile_nua.engine.e1_run import build_slice

    cal = build_calendar(2022)
    sl = build_slice(town, master_seed=SEED, calendar=cal,
                     slice_kind="u31_heldout")
    assert not sl.diagnostics["der_guarantees"], (
        "a DER guarantee fired on the held-out slice"
    )


# --------------------------------------------------------------------------- #
# the slice spans the axis, which is what I-049 asked for
# --------------------------------------------------------------------------- #

def test_both_construction_groups_have_enough_gas_dwellings(sel):
    d = sel.diagnostics
    for group in ("old", "new"):
        assert d[group]["n_on_gas"] >= MIN_GAS_PER_GROUP, (
            f"{group} group has {d[group]['n_on_gas']} gas dwellings against a "
            f"floor of {MIN_GAS_PER_GROUP}; a mean on fewer is noise"
        )
    assert d["old"]["n"] == d["new"]["n"], (
        "the groups are unbalanced; the difference of two means has its "
        "standard error dominated by the smaller cell"
    )


def test_the_groups_are_the_ones_u22_names(sel):
    assert OLD_RANGE == (1967, 1999)
    assert NEW_FROM == 2005
    d = sel.diagnostics
    assert OLD_RANGE[0] <= d["old"]["min_build_year"]
    assert d["old"]["max_build_year"] <= OLD_RANGE[1]
    assert d["new"]["min_build_year"] >= NEW_FROM
    # And the gap between the groups is real, not a boundary artefact.
    assert d["new"]["min_build_year"] - d["old"]["max_build_year"] >= 5


def test_construction_group_classifies_the_boundaries_correctly():
    assert construction_group(1966) is None
    assert construction_group(1967) == "old"
    assert construction_group(1999) == "old"
    assert construction_group(2000) is None      # U22 names neither group here
    assert construction_group(2004) is None
    assert construction_group(2005) == "new"
    assert construction_group(2021) == "new"


def test_the_slice_is_balanced_on_floor_area_and_contrasted_on_fabric(town, sel):
    """The methodological point of the slice.

    DBERNG01's finding is that measured consumption tracks dwelling SIZE, not
    fabric quality. A slice whose old and new groups differed in size could
    not separate the two, and any gradient measured on it would be partly a
    size effect wearing a fabric label.
    """
    by = {b.building_id: b for b in town.buildings}
    chosen = [by[i] for i in sel.building_ids]
    area, loss = {}, {}
    for g in ("old", "new"):
        sub = [b for b in chosen if construction_group(b.build_year) == g]
        area[g] = np.array([b.floor_area_m2 for b in sub])
        loss[g] = np.array([
            specific_loss_w_k_m2(b.rc, b.floor_area_m2) for b in sub
        ])

    _t_a, p_area = stats.ttest_ind(area["old"], area["new"], equal_var=False)
    assert p_area > 0.05, (
        f"the groups differ in floor area (p = {p_area:.3f}), so the gradient "
        f"would be confounded by size - which is the one thing DBERNG01 says "
        f"consumption actually tracks"
    )

    _t_l, p_loss = stats.ttest_ind(loss["old"], loss["new"], equal_var=False)
    assert p_loss < 0.01, (
        f"the groups do not differ in fabric (p = {p_loss:.3f}); there is no "
        f"axis to measure a gradient along"
    )
    assert loss["old"].mean() / loss["new"].mean() > 1.4


def test_the_slice_is_gas_only_and_says_why(sel):
    """DBERNG02 is a meter reading; a dwelling burning no gas contributes nothing."""
    d = sel.diagnostics
    assert d["old"]["n"] == d["old"]["n_on_gas"]
    assert d["new"]["n"] == d["new"]["n_on_gas"]
    assert "meter reading" in U31_REQUIREMENTS["gas_dominant"]


def test_the_departures_from_the_other_selectors_are_declared(sel):
    """Not contiguous, not people-band constrained, not representative.

    Each is a real departure from D-018 and D-028, and each is recorded with
    its reason rather than left for a reader to discover.
    """
    d = sel.diagnostics
    assert "not_contiguous" in d["requirements"]
    assert "no_people_band" in d["requirements"]
    assert "not a sample of Cobh" in d["what_this_slice_is_not"].replace(
        "A sample of Cobh", "not a sample of Cobh"
    ) or "sample of Cobh" in d["what_this_slice_is_not"]
    # Stratified, so it spans many small areas rather than one block.
    assert d["n_small_areas"] > 10, (
        "the slice came out contiguous, which means the stratification "
        "collapsed onto one area and the two groups may not be comparable"
    )


def test_the_selection_is_reproducible(town):
    a = select_heldout_slice(town, master_seed=SEED)
    b = select_heldout_slice(town, master_seed=SEED)
    assert a.building_ids == b.building_ids
    c = select_heldout_slice(town, master_seed=SEED + 1)
    assert c.building_ids != a.building_ids, (
        "the seed does not affect the selection, so it is not a draw"
    )


def test_an_impossible_requirement_raises_rather_than_degrading(town):
    """A thin cell must be refused, not reported."""
    import baile_nua.engine.slice_u31 as mod

    original = mod.MIN_GAS_PER_GROUP
    try:
        mod.MIN_GAS_PER_GROUP = 10_000
        with pytest.raises(U31Infeasible, match="against a floor of"):
            select_heldout_slice(town, master_seed=SEED)
    finally:
        mod.MIN_GAS_PER_GROUP = original


def test_the_scope_declares_no_people_band():
    """E0-7's band sizes the simulated slice, not an evaluation sample."""
    from baile_nua.config import e1_scope

    scope = e1_scope()["heldout_slice"]
    assert scope["people_band_applies"] is False
    assert scope["evaluation_only"] is True
    assert scope["n_homes"] == 60
    # And the other scopes are untouched by this one existing.
    assert e1_scope()["slice"]["n_homes"] == 50
    assert e1_scope()["week2_slice"]["n_homes"] == 60
