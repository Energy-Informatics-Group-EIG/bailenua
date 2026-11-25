"""Week-3 negative controls: deliberately broken artefacts the checks must reject.

A check that has never failed has not been tested. Every check built in week 3
is new, so every one of them needs a broken artefact it rejects — otherwise
"the joint validation passes" and "the joint validation cannot see anything"
are the same observation.

**NC-JOINT-01 is the one that matters most**, because it is I-069 itself turned
into a permanent test. The fix conditions the economic-status draw on age, and
the population now passes `validation/joint_person`. That pass is worth nothing
unless the *unconditioned* population still fails, so this control rebuilds the
defect exactly — status drawn from the area marginal with no age conditioning —
and requires the check to reject it.

It is **power-analysed**, which for a distributional check means: how large a
sample does the check need before the defect is reliably detectable? The answer
decides whether a future pass is evidence. See
:func:`joint_control_power_analysis`.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from baile_nua.validation.negative_control import NegativeControl, register

__all__ = [
    "JointValidationRejectedTheBrokenPopulation",
    "VenueCheckRejectedTheBrokenRecord",
    "ExportCheckFoundTheEnergySeries",
    "joint_control_power_analysis",
]


# The exceptions name what the CHECK FOUND, not what it missed, which is the
# convention the week-2 controls set (`NullControlDetectedAnEffect`). The
# harness counts a RAISE as detection: `invoke` runs the intended check on the
# broken artefact and raises when the check notices.
#
# The first version of this file had all three inverted - it raised when the
# check MISSED - and the harness reported NOT_DETECTED for two of them, which
# is exactly what it is for. Recorded here because getting it backwards is
# easy and silent: an inverted control reports the same NOT_DETECTED as a
# genuinely broken check.
class JointValidationRejectedTheBrokenPopulation(AssertionError):
    """joint_person rejected a population with I-069's defect. Detection."""


class VenueCheckRejectedTheBrokenRecord(AssertionError):
    """The venue check rejected a self-contradicting presence record."""


class ExportCheckFoundTheEnergySeries(AssertionError):
    """A compliance-only export was found carrying the interval energy."""


# --------------------------------------------------------------------------- #
# NC-JOINT-01  I-069's defect, rebuilt
# --------------------------------------------------------------------------- #

#: The sample size the control builds at. Not a round number: it is the size
#: :func:`joint_control_power_analysis` establishes the check needs, and the
#: town's own 15+ population (2,267) is comfortably above it.
JOINT_CONTROL_N = 1200

#: Cobh's own economic-status marginal, near enough. Taken at the shape SAPS
#: gives rather than a uniform one, because a uniform marginal would make the
#: defect trivially visible: the whole difficulty of I-069 is that the
#: marginal was RIGHT.
JOINT_CONTROL_MARGINAL: dict[str, float] = {
    "employed": 0.45, "retired": 0.18, "student": 0.14,
    "home duties": 0.11, "unemployed": 0.07, "unable to work": 0.05,
}


def _unconditioned_population(n: int = JOINT_CONTROL_N, seed: int = 20251011) -> Any:
    """I-069 exactly: the right marginal and the wrong joint.

    Status is drawn from the marginal independently of age, which is what
    `synthesise.py` did before the fix. The marginal therefore comes out right
    - which is the point, and the reason the fault survived every marginal
    check the build had.
    """
    import pandas as pd

    rng = np.random.default_rng(seed)
    labels = sorted(JOINT_CONTROL_MARGINAL)
    probs = np.array([JOINT_CONTROL_MARGINAL[k] for k in labels])
    probs = probs / probs.sum()
    return pd.DataFrame({
        "age": rng.integers(15, 90, n),
        "econ_status": rng.choice(labels, size=n, p=probs),
    })


def _run_joint_validation(population: Any) -> None:
    """The intended check. Must raise on the broken population."""
    from baile_nua.validation import joint_person as JP

    r = JP.compare(persons=population)
    if r["verdict"] != "PASS":
        raise JointValidationRejectedTheBrokenPopulation(
            f"joint_person returned {r['verdict']!r} with "
            f"{r['n_impossible_cells_populated']} impossible cells populated "
            f"and a total variation distance of "
            f"{r['total_variation_distance']} - it rejected a population "
            f"whose economic status was drawn independently of age, which is "
            f"I-069's exact fault."
        )


def _the_marginal_is_still_right(population: Any) -> None:
    """The broken population's MARGINAL must be correct.

    This is what keeps the control honest. If the generator produced a
    population with a wrong marginal too, the joint check might be rejecting
    it for the marginal rather than for the joint, and the control would prove
    nothing about the joint.
    """
    import pandas as pd

    got = population["econ_status"].value_counts(normalize=True)
    for status, want in JOINT_CONTROL_MARGINAL.items():
        have = float(got.get(status, 0.0))
        # Three standard errors of a binomial at this n.
        tol = 3.0 * float(np.sqrt(want * (1 - want) / len(population)))
        if abs(have - want) > max(tol, 0.01):
            raise AssertionError(
                f"HARNESS_DEFECT: the broken population's {status!r} share is "
                f"{have:.4f} against a target of {want:.4f} (tolerance "
                f"{max(tol, 0.01):.4f}). The control must break the JOINT "
                f"only; a wrong marginal would let joint_person reject it for "
                f"the wrong reason."
            )


def _the_conditioned_population_passes(_c: Any) -> None:
    """And the real population, after the fix, must PASS the same check.

    Without this the control would be satisfied by a check that rejects
    everything.
    """
    import baile_nua.sources_registry  # noqa: F401
    from baile_nua.population import venues as V
    from baile_nua.population.synthesise import synthesise_t0
    from baile_nua.validation import joint_person as JP

    town = synthesise_t0(master_seed=20251010)
    r = JP.compare(persons=V.person_frame_from_town(town))
    if r["verdict"] != "PASS":
        raise AssertionError(
            f"the SYNTHESISED population fails joint_person with verdict "
            f"{r['verdict']!r}, TVD {r['total_variation_distance']}, "
            f"{r['n_impossible_cells_populated']} impossible cells. The "
            f"control's broken arm is not the only thing failing, so the "
            f"check is not discriminating - it is rejecting everything."
        )


def joint_control_power_analysis(
    *, sizes: tuple[int, ...] = (100, 200, 400, 800, 1200, 2400),
    n_repeats: int = 12,
) -> dict[str, Any]:
    """How large a population the joint check needs to see I-069's defect.

    A distributional check's power is not optional detail here: the criterion
    is "a cell the reference puts below 0.001 holds five or more people", and
    five people is a smaller fraction of 2,400 than of 100. So a small
    population could pass by being small, and a future pass would be evidence
    of nothing.

    Returns the detection rate at each size. The control is built at
    :data:`JOINT_CONTROL_N`, which must be at or above the smallest size with
    a detection rate of 1.0.
    """
    from baile_nua.validation import joint_person as JP

    rows = []
    for n in sizes:
        detected = 0
        for rep in range(n_repeats):
            pop = _unconditioned_population(n=n, seed=90000 + 1000 * rep + n)
            if JP.compare(persons=pop)["verdict"] == "FAIL":
                detected += 1
        rows.append({"n": n, "n_repeats": n_repeats,
                     "n_detected": detected,
                     "detection_rate": round(detected / n_repeats, 4)})
    full = [r["n"] for r in rows if r["detection_rate"] >= 1.0]
    return {
        "control_id": "NC-JOINT-01",
        "question": (
            "how large a population does joint_person need before I-069's "
            "defect is reliably detected?"
        ),
        "rows": rows,
        "smallest_n_with_full_detection": (min(full) if full else None),
        "control_built_at_n": JOINT_CONTROL_N,
        "town_15_plus_n": 2267,
        "why_it_matters": (
            "The impossible-cell criterion counts PEOPLE - five or more in a "
            "cell the reference puts below 0.001 - so a small population can "
            "pass by being small. If the smallest fully-detecting n were "
            "above the town's own 15+ population, a pass on the town would be "
            "evidence of nothing."
        ),
    }


register(NegativeControl(
    control_id="NC-JOINT-01",
    title="A population with the right economic-status marginal and I-069's wrong joint",
    design_ref="5.2 joint and spatial population validation; I-069",
    intended_test="baile_nua.validation.joint_person.compare",
    expected_exception=JointValidationRejectedTheBrokenPopulation,
    expected_message="impossible cells populated",
    build=_unconditioned_population,
    invoke=_run_joint_validation,
    must_still_pass=(
        ("the broken population's economic-status MARGINAL is still right",
         _the_marginal_is_still_right),
        ("the synthesised population, after the fix, PASSES the same check",
         _the_conditioned_population_passes),
    ),
))


# --------------------------------------------------------------------------- #
# NC-VENUE-01  a presence record that contradicts itself
# --------------------------------------------------------------------------- #

def _self_contradicting_presence() -> Any:
    """One person at a venue and at home in the same minute.

    The failure that is invisible from the venue side: the venue's own
    occupancy count looks perfectly ordinary.
    """
    import pandas as pd

    rows = [
        # Ordinary, so the record is not broken everywhere.
        ("P1", 1, 540, 900, "venue", "VEN-A"),
        ("P2", 1, 540, 900, "venue", "VEN-A"),
        ("P3", 1, 0, 1440, "building", "B-3"),
        # The defect: P4 is in two places at once.
        ("P4", 1, 540, 900, "venue", "VEN-A"),
        ("P4", 1, 600, 1000, "building", "B-4"),
    ]
    return pd.DataFrame(rows, columns=[
        "person_id", "sim_day", "start_min", "end_min", "location_kind",
        "location_id"])


def _run_venue_consistency(presence: Any) -> None:
    from baile_nua.validation.venue_presence import (
        check_venue_presence_consistency,
    )

    r = check_venue_presence_consistency(
        presence=presence, venues=None, capacities={"VEN-A": 50})
    if not r["consistent"]:
        raise VenueCheckRejectedTheBrokenRecord(
            f"the venue check rejected the record: "
            f"person_at_a_venue_and_at_home_at_once="
            f"{r['consistency']['person_at_a_venue_and_at_home_at_once']}, "
            f"person_in_two_places_at_once="
            f"{r['consistency']['person_in_two_places_at_once']}"
        )


def _venue_capacity_is_untouched(presence: Any) -> None:
    """The broken record must still be within capacity.

    Otherwise the check might be rejecting it for the capacity rather than for
    the contradiction, and the control would prove nothing about consistency.
    """
    from baile_nua.validation.venue_presence import (
        check_venue_presence_consistency,
    )

    r = check_venue_presence_consistency(
        presence=presence, venues=None, capacities={"VEN-A": 50})
    if not r["capacity"]["within_capacity"]:
        raise AssertionError(
            "HARNESS_DEFECT: the broken presence record is also over "
            "capacity, so the consistency verdict cannot be attributed to the "
            "contradiction this control plants."
        )


register(NegativeControl(
    control_id="NC-VENUE-01",
    title="A presence record placing one person at a venue and at home at once",
    design_ref="9.4 week 3 venue presence consistent with person presence",
    intended_test="baile_nua.validation.venue_presence.check_venue_presence_consistency",
    expected_exception=VenueCheckRejectedTheBrokenRecord,
    expected_message="person_at_a_venue_and_at_home_at_once",
    build=_self_contradicting_presence,
    invoke=_run_venue_consistency,
    must_still_pass=(
        ("the broken record is still within every venue capacity",
         _venue_capacity_is_untouched),
    ),
))


# --------------------------------------------------------------------------- #
# NC-EXPORT-01  I-067's defect, rebuilt
# --------------------------------------------------------------------------- #

def _compliance_config_that_leaks() -> Any:
    """I-067: `compliance_only` carrying the full energy series.

    Rebuilt by constructing the configuration as it behaved before the fix -
    `include_profile=False` suppressing only the summary - so the control
    fails if the fix is ever reverted.
    """
    import pandas as pd

    from baile_nua.edge.export import EXPORT_CONFIGS, build_export

    idx = pd.date_range("2022-01-15", periods=24 * 60, freq="1min", tz="UTC")
    t = np.arange(len(idx)) / 60.0
    imp = 200.0 + 900.0 * np.exp(-((t - 19.0) ** 2) / 4.0)
    df = build_export(
        premises_id="MPRN-NC", minute_index=idx, net_import_w=imp,
        net_export_w=np.zeros(len(idx)),
        config=EXPORT_CONFIGS["compliance_only"],
        flex_event_id="FLEX-NC", flex_compliance_pct=90.0,
        estate_id="EST-NC",
    )
    # Put the energy series back, which is what the pre-fix code left in.
    thirty = pd.Series(imp).groupby(np.arange(len(imp)) // 30).sum() / 60.0
    df = df.copy()
    df["import_wh"] = thirty.to_numpy()[:len(df)]
    return df


def _run_export_differs(df: Any) -> None:
    import pandas as pd

    v = pd.to_numeric(df.get("import_wh"), errors="coerce")
    carries = bool(v is not None and v.notna().any()
                   and float(v.abs().sum()) > 0.0)
    if carries:
        raise ExportCheckFoundTheEnergySeries(
            "the compliance_only export carries the interval energy series, "
            "so its inference risk is home_30min's - measured at an occupancy "
            "AUC of 0.8655. This is I-067, and the configuration is offered "
            "in design 7.8 as a MITIGATION for a configuration that fails the "
            "inference test."
        )


def _the_real_compliance_config_does_not_leak(_c: Any) -> None:
    """And the shipped configuration must not carry the series.

    This is the half that would catch a revert: the control's broken arm is
    hand-built, so on its own it would keep passing even if `build_export`
    regressed.
    """
    import pandas as pd

    from baile_nua.edge.export import EXPORT_CONFIGS, build_export

    idx = pd.date_range("2022-01-15", periods=24 * 60, freq="1min", tz="UTC")
    imp = np.full(len(idx), 400.0)
    df = build_export(
        premises_id="MPRN-NC2", minute_index=idx, net_import_w=imp,
        net_export_w=np.zeros(len(idx)),
        config=EXPORT_CONFIGS["compliance_only"],
        flex_event_id="FLEX-NC", flex_compliance_pct=90.0,
        estate_id="EST-NC",
    )
    v = pd.to_numeric(df.get("import_wh"), errors="coerce")
    if v is not None and v.notna().any() and float(v.abs().sum()) > 0.0:
        raise AssertionError(
            "the SHIPPED compliance_only configuration carries the interval "
            "energy series. I-067 has been reverted."
        )


register(NegativeControl(
    control_id="NC-EXPORT-01",
    title="A compliance-only export that still carries the interval energy series",
    design_ref="7.8 export configurations; R09; I-067",
    intended_test="tests/test_export_configurations_differ.py (energy-presence check)",
    expected_exception=ExportCheckFoundTheEnergySeries,
    expected_message="carries the interval energy series",
    build=_compliance_config_that_leaks,
    invoke=_run_export_differs,
    must_still_pass=(
        ("the shipped compliance_only configuration does NOT carry the series",
         _the_real_compliance_config_does_not_leak),
    ),
))
