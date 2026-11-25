"""Negative controls for Day 2 (design 9.3 row 2).

    Negative control that must fail:
      * A population with a 10-year-old parent
      * Marginals shifted 10%
"""

from __future__ import annotations

import pandas as pd

from baile_nua.population.households import (
    PlausibilityViolation,
    SynthHousehold,
    SynthPerson,
    check_plausibility,
)
from baile_nua.population.joint_metrics import marginal_acceptance, marginal_error
from baile_nua.population.saps import Marginal, MarginalSpec
from baile_nua.validation.negative_control import NegativeControl, register


# --------------------------------------------------------------------------- #
# NC-D2-01  A 10-year-old parent
# --------------------------------------------------------------------------- #

def _ten_year_old_parent() -> list[SynthHousehold]:
    """A household whose "mother" is ten years old.

    Design 5.2 step 3: "a parent's age at a child's birth falls between 16 and
    50 (mother) or 16 and 65 (father)".  This control makes that impossible by
    a wide margin - the parent would have been 6 at the child's birth - so a
    check that passes it is not checking anything.
    """
    hh = SynthHousehold(
        household_id="H-NC0001", small_area="047106011",
        saps_type="one parent (mother) with children", size=2,
    )
    hh.members = [
        SynthPerson("P-NC0001", "H-NC0001", "047106011", "head", "F", 10, 2012,
                    is_parent_of_children=True),
        SynthPerson("P-NC0002", "H-NC0001", "047106011", "child", "M", 4, 2018),
    ]
    return [hh]


def _plausible_household() -> list[SynthHousehold]:
    hh = SynthHousehold(
        household_id="H-OK0001", small_area="047106011",
        saps_type="one parent (mother) with children", size=2,
    )
    hh.members = [
        SynthPerson("P-OK0001", "H-OK0001", "047106011", "head", "F", 34, 1988,
                    is_parent_of_children=True),
        SynthPerson("P-OK0002", "H-OK0001", "047106011", "child", "M", 4, 2018),
    ]
    return [hh]


register(
    NegativeControl(
        control_id="NC-D2-01",
        title="A population with a 10-year-old parent",
        design_ref="9.3 day 2; 5.2 step 3 plausibility rules",
        intended_test="baile_nua.population.households.check_plausibility",
        expected_exception=PlausibilityViolation,
        expected_message="parent age at birth",
        build=_ten_year_old_parent,
        invoke=lambda hs: check_plausibility(hs, raise_on_violation=True),
        must_still_pass=(
            (
                "the same check on a plausible lone-parent household",
                lambda _: check_plausibility(_plausible_household(), raise_on_violation=True),
            ),
        ),
    )
)


# --------------------------------------------------------------------------- #
# NC-D2-02  Siblings born three months apart, not twins
# --------------------------------------------------------------------------- #

def _impossible_siblings() -> list[SynthHousehold]:
    """Two siblings whose ages differ by less than nine months and who are not
    twins - which is biologically impossible for one mother.

    Ages are integers in the synthesis, so "three months apart" has to be
    represented by the only thing the rule can see: a gap below the nine-month
    threshold that is not zero.  The check uses years, so a 0 gap means twins
    and is legal; this control therefore needs a fractional gap.
    """
    hh = SynthHousehold(
        household_id="H-NC0002", small_area="047106011",
        saps_type="married couple with children", size=4,
    )
    hh.members = [
        SynthPerson("P-NC0010", "H-NC0002", "047106011", "head", "M", 40, 1982, True),
        SynthPerson("P-NC0011", "H-NC0002", "047106011", "partner", "F", 38, 1984, True),
        SynthPerson("P-NC0012", "H-NC0002", "047106011", "child", "M", 6, 2016),
        SynthPerson("P-NC0013", "H-NC0002", "047106011", "child", "F", 6, 2016),
    ]
    # Make the second child 0.25 years older: not a twin, and far closer than
    # nine months.
    hh.members[3].age = 6.25  # type: ignore[assignment]
    return [hh]


register(
    NegativeControl(
        control_id="NC-D2-02",
        title="Siblings born three months apart who are not twins",
        design_ref="9.3 day 2; 5.2 step 3 ('siblings are at least 9 months apart unless twins')",
        intended_test="baile_nua.population.households.check_plausibility",
        expected_exception=PlausibilityViolation,
        expected_message="siblings",
        build=_impossible_siblings,
        invoke=lambda hs: check_plausibility(hs, raise_on_violation=True),
        must_still_pass=(
            (
                "twins (a zero gap) remain legal",
                lambda hs: check_plausibility(
                    [_twins()], raise_on_violation=True
                ),
            ),
        ),
    )
)


def _twins() -> SynthHousehold:
    hh = SynthHousehold(
        household_id="H-OK0002", small_area="047106011",
        saps_type="married couple with children", size=4,
    )
    hh.members = [
        SynthPerson("P-OK0010", "H-OK0002", "047106011", "head", "M", 40, 1982, True),
        SynthPerson("P-OK0011", "H-OK0002", "047106011", "partner", "F", 38, 1984, True),
        SynthPerson("P-OK0012", "H-OK0002", "047106011", "child", "M", 6, 2016),
        SynthPerson("P-OK0013", "H-OK0002", "047106011", "child", "F", 6, 2016),
    ]
    return hh


# --------------------------------------------------------------------------- #
# NC-D2-03  Marginals shifted 10%
# --------------------------------------------------------------------------- #

_REF_COUNTS = pd.Series(
    {"1": 1290, "2": 1509, "3": 920, "4": 921, "5": 435, "6": 137, "7": 30, "8+": 15}
)


def _shifted_marginal() -> dict[str, pd.Series]:
    """A household-size distribution with 10% of its mass moved.

    Taken from one-person households and given to four-person households, which
    is the kind of error a broken scale-down would make: a plausible-looking
    distribution with the wrong shape.  The totals still match, so a check that
    only verifies totals passes it.
    """
    shifted = _REF_COUNTS.astype(float).copy()
    move = shifted["1"] * 0.10
    shifted["1"] -= move
    shifted["4"] += move
    # Scale to the size of the Baile Nua town so the comparison is like for like.
    factor = 1092.0 / float(_REF_COUNTS.sum())
    return {"household_size": (shifted * factor).round().astype(int)}


def _reference_marginal() -> dict[str, Marginal]:
    spec = MarginalSpec(
        key="household_size", unit="household", saps_table="T5_2",
        categories={k: (k,) for k in _REF_COUNTS.index},
        total_column=None, design_ref="negative control",
    )
    frame = pd.DataFrame([_REF_COUNTS.to_dict()], index=["ALL"])
    return {
        "household_size": Marginal(
            spec=spec, by_small_area=frame, town_total=_REF_COUNTS,
            total_declared=int(_REF_COUNTS.sum()),
            total_from_categories=int(_REF_COUNTS.sum()),
        )
    }


class MarginalShiftDetected(AssertionError):
    """The shifted marginal was correctly rejected."""


def _check_marginal(scaled: dict[str, pd.Series]) -> None:
    """The intended test: R04's acceptance band, as marginal_acceptance applies it."""
    errors = marginal_error(_reference_marginal(), scaled)
    detail, summary = marginal_acceptance(errors)
    if summary["verdict"] != "PASS":
        raise MarginalShiftDetected(
            f"marginal rejected: observed max |z| {summary['observed_max_abs_z']} "
            f"exceeds the simultaneous band {summary['z_crit_simultaneous_bonferroni']} "
            f"over {summary['n_categories_total']} categories "
            f"(total variation distance {float(detail['total_variation_distance'].max()):.4f})"
        )


def _unshifted_marginal() -> dict[str, pd.Series]:
    factor = 1092.0 / float(_REF_COUNTS.sum())
    return {"household_size": (_REF_COUNTS.astype(float) * factor).round().astype(int)}


# NC-D2-03 is registered in `baile_nua.validation.ensemble_control`, not here.
#
# Its artefact and its fault are unchanged - 10% of the one-person mass moved
# to four-person households - and `marginal_acceptance` is unchanged. What
# changed is the control's INTENDED TEST, because a power analysis established
# that the single-realisation band cannot detect this fault and never could:
# its deterministic resolution is 12.82% and the fault is 10%, so max |z| comes
# out at 2.1332 against a critical 2.7344 (D-026).
#
# A negative control whose magnitude sits below its check's resolution cannot
# fail, and a control that cannot fail tests nothing. The fault is now pointed
# at a check with the power to see it: the ensemble generator-bias check, which
# judges the generator at its own measured run-to-run precision rather than at
# the sampling error of a 1,092-household draw.
#
# The single-realisation check keeps its own control immediately below:
# NC-D2-05's 40% shift is above the 12.82% resolution and the band detects it,
# which is what demonstrates that the band works where it is applicable. And
# `tests/test_marginal_power.py` pins the resolution itself, so the 10% fault
# cannot quietly be pointed back at a check that cannot see it.


# --------------------------------------------------------------------------- #
# NC-D2-04  A building whose derived fabric is physically impossible
# --------------------------------------------------------------------------- #

def _absurd_building() -> dict[str, object]:
    """A 30 m2 single-storey pre-1919 detached dwelling rated G.

    The first version of this control used a **400 m2** house, on the assumption
    that bigger and older meant worse. That was wrong and the harness caught it:
    specific heat loss is heat loss per square metre of floor, and large
    dwellings have a *better* surface-to-volume ratio, so the 400 m2 house came
    out at 3.7 W/K/m2 - comfortably inside the plausible range - and the control
    reported NOT_DETECTED.

    The genuinely extreme case is the opposite: a very **small**, old, detached
    dwelling with no party walls, where envelope area per square metre of floor
    is at its worst. This one derives above 7 W/K/m2 and must be refused.
    """
    return {
        "ber_band": "G", "era_median_band": "G", "floor_area_m2": 30.0,
        "dwelling_type": "detached", "year_built_band": "pre 1919",
        "storeys": 1, "n_bedrooms": 1,
    }


def _derive(kwargs: dict[str, object]) -> None:
    from baile_nua.physics.archetype import derive_rc

    derive_rc(**kwargs)  # type: ignore[arg-type]


register(
    NegativeControl(
        control_id="NC-D2-04",
        title="A building whose derived fabric is outside the plausible Irish range",
        design_ref="5.7 fidelity tiers; 7.2 physics bounds",
        intended_test="baile_nua.physics.archetype.derive_rc",
        expected_exception=Exception,  # ImplausibleFabricError
        expected_message="outside the published plausible range",
        build=_absurd_building,
        invoke=_derive,
        must_still_pass=(
            (
                "an ordinary semi-detached house is accepted",
                lambda _: _derive({
                    "ber_band": "D1", "era_median_band": "D1", "floor_area_m2": 105.0,
                    "dwelling_type": "semi-detached", "year_built_band": "1971-1980",
                    "storeys": 2, "n_bedrooms": 3,
                }),
            ),
        ),
    )
)


# --------------------------------------------------------------------------- #
# NC-D2-05  A marginal shift large enough for the band to detect
# --------------------------------------------------------------------------- #

def _resolution_of_marginal_band(
    categories: pd.Series, n: int, *, category: str = "1", to: str = "4"
) -> dict[str, float]:
    """The smallest detectable relative shift in one category, at sample size n.

    NC-D2-03 reports NOT_DETECTED, and that is a real result rather than a
    broken check: a 10% shift of one-person households into four-person
    households is *inside* the sampling-error band at a town of 1,092 homes.
    Rather than leave that as a bare failure, this measures the band's actual
    detection threshold, which is the number the E1 report needs and which U11
    needs in order to rule on the acceptance statistic.
    """
    shares = categories / categories.sum()
    lo, hi = 0.0, 1.0
    for _ in range(40):
        mid = (lo + hi) / 2.0
        shifted = categories.astype(float).copy()
        move = shifted[category] * mid
        shifted[category] -= move
        shifted[to] += move
        scaled = (shifted / shifted.sum() * n).round().astype(int)
        errors = marginal_error(_reference_marginal(), {"household_size": scaled})
        _detail, summary = marginal_acceptance(errors)
        if summary["verdict"] == "PASS":
            lo = mid
        else:
            hi = mid
    return {
        "n": n,
        "smallest_detectable_relative_shift": round(hi, 4),
        "shift_tested_by_NC_D2_03": 0.10,
        "detectable": hi <= 0.10,
    }


def _large_shift() -> dict[str, pd.Series]:
    """A 40% shift, well above the band's measured detection threshold."""
    shifted = _REF_COUNTS.astype(float).copy()
    move = shifted["1"] * 0.40
    shifted["1"] -= move
    shifted["4"] += move
    factor = 1092.0 / float(_REF_COUNTS.sum())
    return {"household_size": (shifted * factor).round().astype(int)}


register(
    NegativeControl(
        control_id="NC-D2-05",
        title="Household-size marginal with 40% of one category shifted",
        design_ref="9.3 day 2; 12 R04. Companion to NC-D2-03, which is below the band's resolution",
        intended_test="baile_nua.population.joint_metrics.marginal_acceptance",
        expected_exception=MarginalShiftDetected,
        expected_message="exceeds the simultaneous band",
        build=_large_shift,
        invoke=_check_marginal,
        must_still_pass=(
            (
                "the same band accepts the unshifted marginal",
                lambda _: _check_marginal(_unshifted_marginal()),
            ),
        ),
    )
)
