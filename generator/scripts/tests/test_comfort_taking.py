"""U22: comfort-taking - rebound in efficient homes, prebound in poor ones.

DBERNG01 says measured gas varies only 4 to 7% across BER bands within a
dwelling type, and that A-B detached houses burn MORE gas than F-G ones, while
varying 84% across dwelling types. A thermostat at a fixed setpoint cannot
produce that, and E1 did not: its space-heat ratio against the published cell
was 0.43 for 1967-99 stock and 0.19 for post-2005, so the better the fabric,
the further below the real meter the model fell.

These tests pin the mechanism's SHAPE - what it does and to what - and the
prohibition it operates under. Whether it reproduces the flatness is an
ablation, not a unit test, and lives in the artefact it writes.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest

import baile_nua.sources_registry  # noqa: F401
from baile_nua.behaviour.comfort_taking import (
    AFFORDABILITY_BY_QUINTILE,
    DEFAULT_SPEC,
    TENURE_AFFORDABILITY_SHIFT,
    ComfortTakingSpec,
    affordability,
    comfort_shift,
    specific_loss_w_k_m2,
)
from baile_nua.population.synthesise import synthesise_t0

SEED = 20261008


@pytest.fixture(scope="module")
def town():
    return synthesise_t0(master_seed=SEED)


# --------------------------------------------------------------------------- #
# the prohibition
# --------------------------------------------------------------------------- #

def test_the_mechanism_never_touches_thermal_parameters():
    """U22's condition, and D-022's reason.

    "Fitting the physics to reproduce a behavioural effect would hide the gap
    instead of measuring it, and would make the fabric parameters wrong for
    every other purpose." What the mechanism returns is a temperature asked
    for and a window length - both decisions.
    """
    import inspect

    from baile_nua.behaviour import comfort_taking

    src = inspect.getsource(comfort_taking)
    for forbidden in ("ThermalParams", "RCParameters", "r_ie =", "ach_base ="):
        assert f"{forbidden}(" not in src and f"{forbidden} =" not in src, (
            f"the comfort-taking module constructs or assigns {forbidden}, "
            f"which is building physics. U22: never tune the physics to "
            f"absorb comfort-taking."
        )
    out = comfort_shift(specific_loss_w_k_m2=1.0, income_quintile=5)
    assert set(out) >= {"setpoint_shift_c", "hours_multiplier"}
    assert "ThermalParams" in out["never_touches"]


def test_the_driving_quantity_is_the_whole_dwelling_conductance(town):
    """Specific heat loss, defined once, and checked per dwelling.

    The mechanism's driver has to be the same conductance the physics uses:
    the two fabric paths in series plus the infiltration path in parallel,
    over floor area. If this function computed something else, comfort-taking
    would be centred on a quantity nobody else in the project recognises.

    **This test used to assert a mean of 2.45 W/K/m2** on the grounds that
    "the E1 gate report states" it. That number appears nowhere in
    `v1/evidence/e1_gate_report.json`, and it was stale the moment the fabric
    changed. An identity checked per dwelling is both stronger and traceable:
    it tests the definition rather than a population statistic that moves
    whenever the population does.
    """
    for b in list(town.buildings)[:200]:
        expected = (
            1.0 / (b.rc.r_ie + b.rc.r_ea) + 1.0 / b.rc.r_inf
        ) / b.floor_area_m2
        assert specific_loss_w_k_m2(b.rc, b.floor_area_m2) == pytest.approx(
            expected, rel=1e-9
        ), b.building_id

    losses = np.array([
        specific_loss_w_k_m2(b.rc, b.floor_area_m2) for b in town.buildings
    ])
    assert losses.min() > 0.0
    # And the spread is what makes the mechanism worth having at all. It
    # narrowed from a factor of 10.3 to 6.6 when the fabric was sourced from
    # SEAI's assessed distribution, which is what I-048 predicted; the
    # mechanism still needs a real spread to redistribute across.
    assert losses.max() / losses.min() > 4.0, losses.max() / losses.min()


def test_the_reference_is_the_towns_median_not_its_mean(town):
    """Centring, and why the median.

    The distribution is right-skewed, so centring on the mean would put more
    than half the dwellings on the rebound side and give the mechanism a net
    warming effect on the town instead of a redistribution across the fabric
    range. Comfort-taking redistributes.
    """
    losses = np.array([
        specific_loss_w_k_m2(b.rc, b.floor_area_m2) for b in town.buildings
    ])
    median = float(np.median(losses))
    assert median < losses.mean(), "the distribution is no longer right-skewed"
    assert DEFAULT_SPEC.reference_specific_loss_w_k_m2 == pytest.approx(
        median, abs=0.05
    ), (
        f"the reference is {DEFAULT_SPEC.reference_specific_loss_w_k_m2} but "
        f"the town's median specific loss is {median:.3f}; the mechanism is "
        f"no longer centred on the population being simulated"
    )
    # A dwelling at the reference takes no shift, which is what "centred" means.
    at_median = comfort_shift(
        specific_loss_w_k_m2=DEFAULT_SPEC.reference_specific_loss_w_k_m2,
        income_quintile=3,
    )
    assert at_median["setpoint_shift_c"] == pytest.approx(0.0, abs=1e-9)
    assert at_median["hours_multiplier"] == pytest.approx(1.0, abs=1e-9)


# --------------------------------------------------------------------------- #
# the shape: rebound and prebound
# --------------------------------------------------------------------------- #

def test_an_efficient_home_takes_comfort_and_a_leaky_one_gives_it_up():
    efficient = comfort_shift(specific_loss_w_k_m2=0.8, income_quintile=4)
    leaky = comfort_shift(specific_loss_w_k_m2=5.0, income_quintile=2)
    assert efficient["mode"] == "rebound"
    assert efficient["setpoint_shift_c"] > 0.5
    assert efficient["hours_multiplier"] > 1.0
    assert leaky["mode"] == "prebound"
    assert leaky["setpoint_shift_c"] < -0.5
    assert leaky["hours_multiplier"] < 1.0


def test_prebound_is_a_cost_response_not_a_fabric_response():
    """The falsifiable content, and what a single fitted knob cannot do.

    The same leaky dwelling, two households. A well-off one barely prebounds
    at all; a poor one gives up more than a kelvin and a fifth of its heating
    hours. If prebound were a property of the fabric these would be equal,
    and the mechanism would just be a fabric correction wearing a behavioural
    name.
    """
    poor = comfort_shift(
        specific_loss_w_k_m2=4.0, income_quintile=1,
        tenure="rented from local authority",
    )
    rich = comfort_shift(
        specific_loss_w_k_m2=4.0, income_quintile=5,
        tenure="owner-occupied no mortgage",
    )
    assert poor["setpoint_shift_c"] < -1.0
    assert rich["setpoint_shift_c"] == pytest.approx(0.0, abs=0.05)
    assert poor["hours_multiplier"] < 0.85
    assert rich["hours_multiplier"] == pytest.approx(1.0, abs=0.01)


def test_rebound_also_needs_means():
    """A household with no slack banks the saving rather than spending it."""
    rich = comfort_shift(specific_loss_w_k_m2=0.8, income_quintile=5)
    middling = comfort_shift(specific_loss_w_k_m2=0.8, income_quintile=3)
    assert rich["setpoint_shift_c"] > middling["setpoint_shift_c"] > 0.0


def test_a_household_with_no_headroom_takes_no_rebound_at_all():
    """The fuel-poverty corner, and it is the intended prediction.

    The lowest income quintile in local-authority housing comes out at zero
    affordability headroom (0.20 - 0.25, floored), so an efficient dwelling
    buys it no extra warmth: it banks the whole saving. That is the right
    behavioural claim for a household in fuel poverty, and it is the same
    term that makes it prebound hardest in a leaky dwelling - the two are one
    mechanism, not two.

    Written as a test because a reader could easily take the zero for a bug.
    """
    aff = affordability(
        income_quintile=1, tenure="rented from local authority",
    )
    assert aff["affordability"] == pytest.approx(0.0)

    efficient = comfort_shift(
        specific_loss_w_k_m2=0.8, income_quintile=1,
        tenure="rented from local authority",
    )
    assert efficient["mode"] == "rebound"
    assert efficient["setpoint_shift_c"] == pytest.approx(0.0)
    assert efficient["hours_multiplier"] == pytest.approx(1.0)

    leaky = comfort_shift(
        specific_loss_w_k_m2=5.0, income_quintile=1,
        tenure="rented from local authority",
    )
    # The same zero headroom, now at full strength in the other direction.
    assert leaky["setpoint_shift_c"] < -1.5
    assert leaky["hours_multiplier"] < 0.75


def test_the_response_is_logarithmic_in_cost_not_linear():
    """A second halving buys less than the first.

    A linear response would hand implausible setpoints to the best dwellings
    and then have to be clipped, which is a way of discovering a model is
    wrong by watching it hit a limit.
    """
    ref = DEFAULT_SPEC.reference_specific_loss_w_k_m2
    first = comfort_shift(
        specific_loss_w_k_m2=ref / 2.0, income_quintile=5
    )["setpoint_shift_c"]
    second = comfort_shift(
        specific_loss_w_k_m2=ref / 4.0, income_quintile=5
    )["setpoint_shift_c"]
    # Twice the halving, not twice the shift.
    assert second > first
    assert second == pytest.approx(2.0 * first, rel=0.02), (
        "log in the cost RATIO means equal halvings give equal increments; "
        "that is the intended shape"
    )
    # But in the cost itself the response is decelerating, which is the claim.
    quarter_gain = second - first
    assert quarter_gain == pytest.approx(first, rel=0.02)


def test_the_shift_is_bounded_and_says_when_it_clipped():
    """A guard, not a tuning parameter.

    A mis-specified cost ratio should show up as a clipped shift in the
    diagnostics rather than as a 30 degC living room - PL-TEMP-01 would catch
    that, and this makes it visible earlier.
    """
    extreme = comfort_shift(specific_loss_w_k_m2=0.01, income_quintile=5)
    assert extreme["clipped"] is True
    assert extreme["setpoint_shift_c"] == DEFAULT_SPEC.max_setpoint_shift_c
    assert extreme["setpoint_shift_before_clipping_c"] > \
        DEFAULT_SPEC.max_setpoint_shift_c
    ordinary = comfort_shift(specific_loss_w_k_m2=1.5, income_quintile=3)
    assert ordinary["clipped"] is False


def test_prebound_is_stronger_than_rebound_per_unit_of_cost():
    """Not symmetric, and the asymmetry is the claim.

    Giving up warmth you cannot afford is forced; taking warmth you can
    afford is optional.
    """
    assert DEFAULT_SPEC.prebound_k_per_ln_cost > \
        DEFAULT_SPEC.rebound_k_per_ln_cost
    assert DEFAULT_SPEC.prebound_max_hours_fraction > \
        DEFAULT_SPEC.rebound_max_hours_fraction


# --------------------------------------------------------------------------- #
# affordability
# --------------------------------------------------------------------------- #

def test_affordability_uses_the_models_own_quintile_mapping():
    """One mapping, not two.

    An earlier version carried its own socio-economic-group table. It was a
    duplicate of `_SEG_TO_QUINTILE` in the population layer AND wrong: the
    SAPS labels are letter-prefixed ("A employers and managers"), so none of
    its keys would have matched and every household would have taken the
    unknown midpoint - a silent failure that would have switched the entire
    affordability term off.
    """
    from baile_nua.population import synthesise

    quintiles = set(synthesise._SEG_TO_QUINTILE.values())
    assert quintiles <= set(AFFORDABILITY_BY_QUINTILE), (
        "the population layer produces a quintile this module cannot price"
    )
    import inspect

    from baile_nua.behaviour import comfort_taking

    src = inspect.getsource(comfort_taking)
    assert "AFFORDABILITY_BY_SEG" not in src, (
        "the duplicate socio-economic-group table is back"
    )


def test_affordability_rises_with_income_and_falls_with_insecure_tenure():
    ordered = [
        affordability(income_quintile=q, tenure="owner-occupied with mortgage")
        ["affordability"] for q in (1, 2, 3, 4, 5)
    ]
    assert ordered == sorted(ordered)
    assert ordered[0] < ordered[-1]

    la = affordability(income_quintile=3, tenure="rented from local authority")
    owned = affordability(income_quintile=3, tenure="owner-occupied no mortgage")
    assert la["affordability"] < owned["affordability"]
    assert la["tenure_shift"] < 0 < owned["tenure_shift"]


def test_being_out_of_work_bites_regardless_of_the_recorded_occupation():
    """SEG classifies the job somebody had."""
    working = affordability(
        income_quintile=4, tenure="owner-occupied with mortgage",
        econ_status="employed",
    )
    unemployed = affordability(
        income_quintile=4, tenure="owner-occupied with mortgage",
        econ_status="unemployed",
    )
    assert unemployed["affordability"] < working["affordability"]
    assert unemployed["econ_status_shift"] < 0


def test_an_unknown_quintile_takes_the_midpoint_and_says_so():
    out = affordability(income_quintile=None, tenure=None)
    assert 0.4 < out["affordability"] < 0.7
    assert "unknown" in out["base_from"]


def test_affordability_is_bounded():
    for q in (1, 5):
        for tenure in TENURE_AFFORDABILITY_SHIFT:
            for status in ("employed", "unemployed", "retired"):
                v = affordability(
                    income_quintile=q, tenure=tenure, econ_status=status
                )["affordability"]
                assert 0.0 <= v <= 1.0


# --------------------------------------------------------------------------- #
# the town, as the mechanism sees it
# --------------------------------------------------------------------------- #

def test_the_town_splits_both_ways_with_neither_side_trivial(town):
    """A mechanism that only ever fired one way would be a bias, not a response."""
    import pandas as pd

    quintile = (
        town.states.groupby("household_id").income_quintile.first().to_dict()
    )
    modes: dict[str, int] = {}
    shifts = []
    for b in town.buildings:
        hh = b.household_id
        if hh is None:
            continue
        out = comfort_shift(
            specific_loss_w_k_m2=specific_loss_w_k_m2(b.rc, b.floor_area_m2),
            income_quintile=quintile.get(hh),
            tenure=b.tenure,
        )
        modes[out["mode"]] = modes.get(out["mode"], 0) + 1
        shifts.append(out["setpoint_shift_c"])
    assert modes.get("rebound", 0) > 100
    assert modes.get("prebound", 0) > 100
    arr = np.array(shifts)
    # Redistribution, not a net shift: the town mean should be small against
    # the spread it creates.
    assert abs(arr.mean()) < 0.5 * arr.std(), (
        f"mean shift {arr.mean():+.3f} K against a spread of {arr.std():.3f} "
        f"K - the mechanism is warming or cooling the whole town rather than "
        f"redistributing across the fabric range"
    )


def test_a_custom_spec_is_honoured():
    """The ablation needs the strengths to be changeable, not hard-coded."""
    weak = ComfortTakingSpec(
        rebound_k_per_ln_cost=0.0, prebound_k_per_ln_cost=0.0,
        rebound_max_hours_fraction=0.0, prebound_max_hours_fraction=0.0,
    )
    out = comfort_shift(
        specific_loss_w_k_m2=0.8, income_quintile=5, spec=weak
    )
    assert out["setpoint_shift_c"] == pytest.approx(0.0)
    assert out["hours_multiplier"] == pytest.approx(1.0)
    assert dataclasses.is_dataclass(weak)


# --------------------------------------------------------------------------- #
# the ablation's comparison logic
#
# The U22 conclusion rests on these functions, so they are tested on
# synthetic frames where the right answer is known by construction. An
# ablation that measured the wrong thing would be worse than none: it would
# produce a number nobody could check.
# --------------------------------------------------------------------------- #

def _row(**kw):
    base = {
        "ber_group": "C", "dwelling_type": "semi-detached",
        "year_built_band": "1971-1980", "heating_fuel": "natural gas",
        "space_heat_kwh_yr": 5000.0, "space_heat_kwh_m2_yr": 50.0,
        "meter_gas_kwh_yr": 9000.0, "d24_gas_target_kwh_yr": 10000.0,
        "temp_living_mean_c": 19.5,
    }
    base.update(kw)
    return base


def test_the_spread_is_measured_between_levels_not_within_them():
    """Between-band spread is the quantity; within-band is dwelling size.

    DBERNG01's own figure is a spread BETWEEN bands - 4 to 7% - while
    consumption varies 84% across dwelling types, which is size. A pooled
    standard deviation would mix the two and the 84% would swamp the 4%.
    """
    import pandas as pd

    from baile_nua.validation.ablation import _spread_across

    # Two bands whose MEANS are equal, but with huge within-band spread.
    frame = pd.DataFrame([
        _row(ber_group="A", space_heat_kwh_m2_yr=10.0),
        _row(ber_group="A", space_heat_kwh_m2_yr=90.0),
        _row(ber_group="F", space_heat_kwh_m2_yr=40.0),
        _row(ber_group="F", space_heat_kwh_m2_yr=60.0),
    ])
    out = _spread_across(frame, "ber_group", "space_heat_kwh_m2_yr")
    assert out["evaluable"] is True
    assert out["spread_pct"] == pytest.approx(0.0, abs=1e-6), (
        "equal band means must read as zero spread however wide the "
        "within-band variation"
    )


def test_a_level_with_one_dwelling_is_not_a_level():
    """One dwelling is one dwelling, and averaging it is not a band mean."""
    import pandas as pd

    from baile_nua.validation.ablation import _spread_across

    frame = pd.DataFrame([
        _row(ber_group="C", space_heat_kwh_m2_yr=50.0),
        _row(ber_group="C", space_heat_kwh_m2_yr=52.0),
        _row(ber_group="F", space_heat_kwh_m2_yr=60.0),
        _row(ber_group="F", space_heat_kwh_m2_yr=64.0),
        _row(ber_group="A", space_heat_kwh_m2_yr=5.0),      # alone
    ])
    out = _spread_across(frame, "ber_group", "space_heat_kwh_m2_yr")
    assert "A" not in out["levels"], (
        "a single-dwelling band was averaged into a band mean, which is how a "
        "four-against-four gradient gets reported as a finding"
    )
    assert set(out["levels"]) == {"C", "F"}
    # 62 against 51, and the lone A at 5.0 would have made it 1140%.
    assert out["spread_pct"] == pytest.approx(21.6, abs=0.1)


def test_a_thin_axis_reports_not_evaluable_rather_than_a_number():
    """The E1 estate's problem, refused rather than reported."""
    import pandas as pd

    from baile_nua.validation.ablation import _gradient, _spread_across

    frame = pd.DataFrame([_row(), _row()])      # one band only
    out = _spread_across(frame, "ber_group", "space_heat_kwh_m2_yr")
    assert out["evaluable"] is False
    assert "fewer than two levels" in out["reason"]

    g = _gradient(frame)
    assert g["evaluable"] is False


def test_the_heldout_gradient_is_oldest_over_newest():
    """The direction U22 names: 0.43 for old stock against 0.19 for new."""
    import pandas as pd

    from baile_nua.validation.ablation import _gradient

    frame = pd.DataFrame([
        _row(year_built_band="1971-1980", meter_gas_kwh_yr=4300.0),
        _row(year_built_band="1971-1980", meter_gas_kwh_yr=4300.0),
        _row(year_built_band="2011-2015", meter_gas_kwh_yr=1900.0),
        _row(year_built_band="2011-2015", meter_gas_kwh_yr=1900.0),
    ])
    g = _gradient(frame)
    assert g["evaluable"] is True
    assert g["oldest_ratio"] == pytest.approx(0.43)
    assert g["newest_ratio"] == pytest.approx(0.19)
    # Reported to four decimals, so compared at that precision.
    assert g["gradient_oldest_over_newest"] == pytest.approx(
        0.43 / 0.19, abs=1e-4
    )


def test_the_comparison_reports_direction_for_both_axes():
    import pandas as pd

    from baile_nua.validation.ablation import compare

    def diag(spread_hi, grad_old):
        rows = [
            _row(ber_group="A", space_heat_kwh_m2_yr=10.0,
                 year_built_band="2011-2015", meter_gas_kwh_yr=1900.0),
            _row(ber_group="A", space_heat_kwh_m2_yr=10.0,
                 year_built_band="2011-2015", meter_gas_kwh_yr=1900.0),
            _row(ber_group="F", space_heat_kwh_m2_yr=spread_hi,
                 year_built_band="1971-1980", meter_gas_kwh_yr=grad_old),
            _row(ber_group="F", space_heat_kwh_m2_yr=spread_hi,
                 year_built_band="1971-1980", meter_gas_kwh_yr=grad_old),
        ]
        return {
            "slice": {"n_homes": 4, "n_people": 10},
            "annual_electricity": {"per_dwelling": rows},
        }

    # "on" has a narrower BER spread and a flatter gradient, which is the
    # direction the mechanism claims.
    out = compare(diag(60.0, 4300.0), diag(20.0, 2400.0))
    assert out["moved"]["ber_spread_pct_space_heat_per_m2"]["change"] < 0
    assert out["moved"]["heldout_gradient"]["change"] < 0
    assert out["decision"] == "U22"
    assert "4 to 7" in out["reference"]["dberng01_ber_spread_pct"]
    assert "held out" in out["reference"]["sources"][1]


# --------------------------------------------------------------------------- #
# I-047: boiler vintage is not dwelling vintage
# --------------------------------------------------------------------------- #

def test_a_boiler_is_younger_than_the_house_it_heats():
    """The error the ablation caught, as a test.

    DEAP Table 4b is indexed by the BOILER's age. U25 read the dwelling's
    build year into its rows, so a house built in 1975 got a 55%-efficient
    floor-mounted boiler in 2022. It is on its second or third boiler.

    The error only bit where the dwelling was old, which is exactly where U22
    is measured - so U25's own validation on a modern estate could not see it,
    and the ablation's 2.11 gas ratio against the estate's 0.83 is what
    exposed it.
    """
    from baile_nua.physics.boiler import boiler_efficiency, boiler_vintage

    old = boiler_vintage(build_year=1975, t0_year=2022)
    assert old["still_original"] is False
    assert old["vintage"] > 2000, (
        f"a 1975 dwelling was given a {old['vintage']} boiler"
    )
    assert old["condensing"] is True

    # A dwelling younger than one service life is still on its original.
    new = boiler_vintage(build_year=2018, t0_year=2022)
    assert new["still_original"] is True
    assert new["vintage"] == 2018


def test_plant_efficiency_is_flat_across_eras_once_replacement_is_modelled():
    """The claim this retracts.

    The U25 write-up said Table 4b's 55-83% spread was an era confound U22
    would have to separate comfort-taking from. It is not: once boilers are
    replaced rather than inherited, efficiency is nearly flat across the
    stock, and whatever era difference remains in the gas comparison is not
    the boiler.
    """
    from baile_nua.physics.boiler import boiler_efficiency, boiler_spec_for

    gen = np.random.default_rng(11)
    means = {}
    for year in (1890, 1955, 1975, 1995, 2005):
        class _B:
            build_year = year
            heating_fuel = "natural gas"
        effs = [
            boiler_efficiency(boiler_spec_for(_B, gen=gen))["efficiency"]
            for _ in range(300)
        ]
        means[year] = float(np.mean(effs))
    spread = max(means.values()) - min(means.values())
    assert spread < 0.03, (
        f"boiler efficiency still varies by {spread:.3f} across construction "
        f"eras ({means}); if that is real it is an era confound and I-047's "
        f"retraction is wrong"
    )
    assert min(means.values()) > 0.75


def test_the_oldest_table_4b_rows_are_reachable_but_rare():
    """A 55% floor-mounted boiler should exist and be unusual.

    Making them unreachable would be the opposite error: some Irish homes do
    still have very old boilers, and a model in which none does cannot
    represent the worst case the distribution network plans for.
    """
    from baile_nua.physics.boiler import BoilerSpec, boiler_efficiency

    ancient = BoilerSpec(
        fuel="natural gas", build_year=1970, floor_mounted=True,
        fan_assisted_flue=False,
    )
    assert boiler_efficiency(ancient)["gross_seasonal_efficiency"] == \
        pytest.approx(0.55)
    assert boiler_efficiency(ancient)["row"] == "floor_mounted_pre_1979"


# --------------------------------------------------------------------------- #
# I-048: closing rooms, and the saturation that demanded it
# --------------------------------------------------------------------------- #

def test_prebound_closes_rooms_and_rebound_does_not():
    """The third term, added because the first two saturated.

    "Heated warmer, longer and IN MORE ROOMS" - the project's own description
    of the mechanism, which the first version under-built. A house-wide
    temperature reduction scales each dwelling's losses; abandoning a zone
    removes them, which is the only thing that can flatten consumption across
    a tenfold fabric spread.
    """
    severe = comfort_shift(
        specific_loss_w_k_m2=6.5, income_quintile=1,
        tenure="rented from local authority",
    )
    mild = comfort_shift(
        specific_loss_w_k_m2=3.0, income_quintile=3,
        tenure="owner-occupied with mortgage",
    )
    rebounding = comfort_shift(specific_loss_w_k_m2=0.8, income_quintile=5)

    assert severe["sleep_zone_heated_fraction"] < 0.25, (
        "a severely prebounding household should have effectively closed its "
        "bedrooms"
    )
    assert mild["sleep_zone_heated_fraction"] > severe["sleep_zone_heated_fraction"]
    assert rebounding["sleep_zone_heated_fraction"] == pytest.approx(1.0), (
        "rebound must not abandon a zone; there is no third zone to open"
    )
    assert rebounding["zone_abandonment"] == 0.0


def test_a_well_off_household_in_a_leaky_house_keeps_its_bedrooms():
    """The cost-response claim, on the zonal term too."""
    poor = comfort_shift(
        specific_loss_w_k_m2=5.0, income_quintile=1,
        tenure="rented from local authority",
    )
    rich = comfort_shift(
        specific_loss_w_k_m2=5.0, income_quintile=5,
        tenure="owner-occupied no mortgage",
    )
    assert poor["sleep_zone_heated_fraction"] < 0.4
    assert rich["sleep_zone_heated_fraction"] == pytest.approx(1.0)


def test_all_three_terms_are_bounded():
    """Guards, so a mis-specified cost ratio is visible rather than absurd."""
    for loss in (0.01, 0.5, 2.08, 5.0, 50.0):
        for q in (1, 3, 5):
            out = comfort_shift(specific_loss_w_k_m2=loss, income_quintile=q)
            assert DEFAULT_SPEC.min_setpoint_shift_c <= \
                out["setpoint_shift_c"] <= DEFAULT_SPEC.max_setpoint_shift_c
            assert 0.0 < out["hours_multiplier"] <= 2.0
            assert 0.0 <= out["sleep_zone_heated_fraction"] <= 1.0
