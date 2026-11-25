"""The generator-bias ensemble check, and the NC-D2-03 controls built on it.

Design 9.3 day 2 requires a negative control in which the marginals are
"shifted 10%".  NC-D2-03 plants exactly that and the single-realisation
acceptance band does not detect it.  The first response was to record the
resolution as a recognised limitation (I-020); that was wrong, because a
control whose magnitude sits below its check's resolution cannot fail and so
tests nothing.

**What the power analysis found** (`baile_nua.validation.power`, recorded in
DECISIONS.md as D-026):

* The single-realisation band's **deterministic resolution is 12.82%**. The
  planted 10% produces max |z| 2.1332 against a critical 2.7344, so it is
  below the resolution by construction and no amount of care in running the
  check would find it.
* If the population were a genuine random draw of 1,092 households, the same
  check would have **42.6% power** against a 10% shift, and would need
  **3,664 households** for 95% power - against Cobh's real 5,257 and the
  scaled town's 1,092.
* The generator is **deterministic** in this marginal: across-run standard
  deviation 1.7e-16 over 40 independent seeds, in both the correct and the
  shifted configuration. It reproduces its control totals exactly.

That last measurement is the one that matters. The acceptance band is the
multinomial sampling error of a 1,092-household draw - about 0.013 in
proportion near p = 0.25 - and the generator's own run-to-run error is zero.
The band is therefore roughly twenty-eight times wider than the precision of
the thing it is testing, and a bias comfortably inside it is still an
unambiguous defect in the generator.

So the fix is not a wider band or a bigger fault. It is a check that judges the
generator at the generator's own precision: the ensemble mean of K runs against
what the generator is contracted to reproduce.

Stated in households, which is the interpretable form:

===========================================  ====================
Single-realisation band fires at             about 34 households
Ensemble check (K=20) fires at               about 1.5 households
The planted 10% shift moves                  about 27 households
===========================================  ====================

which is why one check cannot see it and the other cannot miss it.
"""

from __future__ import annotations

import functools
from typing import Any

import numpy as np
import pandas as pd

from baile_nua.population.joint_metrics import (
    ENSEMBLE_TARGET_VS_SAPS_MAX_ABS_Z,
    contracted_reference,
    ensemble_marginal_acceptance,
)
from baile_nua.validation.negative_control import NegativeControl, register

__all__ = [
    "ENSEMBLE_K",
    "ENSEMBLE_K_MINIMUM",
    "EnsembleBiasDetected",
    "run_generator_ensemble",
    "check_generator_bias",
]

#: The smallest K the power analysis permits.
#:
#: Two independent derivations agree on it, which is why it is this number and
#: not a round one:
#:
#: * **Information.** A random draw needs 3,664 households for 95% power
#:   against a 10% shift; the scaled town has 1,092, so 3,664/1,092 = 3.36,
#:   and K = 4.
#: * **Measured.** Bootstrapped over a pool of 40 correct and 40 shifted runs,
#:   K = 4 is the smallest K with power >= 0.95 and false-positive rate
#:   <= 0.05. At K = 2 the check is useless, because one degree of freedom puts
#:   the t critical value at 101.9.
ENSEMBLE_K_MINIMUM: int = 4

#: The K actually used.
#:
#: 20 rather than the minimum 4, for a reason that is about the critical value
#: rather than about power. The standard deviation is estimated from the same K
#: runs, so the band is a t quantile on K-1 degrees of freedom: at K = 4 that
#: is 6.895, two and a half times its asymptotic value, and the check pays that
#: penalty on every marginal. At K = 20 it is 3.074, within 13%. Twenty runs
#: cost about 52 seconds and leave the check with teeth on the marginals that
#: genuinely do vary between seeds - age band (across-run SD up to 0.0032) and
#: sex (0.0074) - where the minimum K would not.
ENSEMBLE_K: int = 20


class EnsembleBiasDetected(AssertionError):
    """The ensemble check correctly rejected a biased generator."""


def _shift_control_totals(
    marginals: dict[str, pd.DataFrame], *, fraction: float,
    key: str = "household_size", source: str = "1", sink: str = "4",
) -> dict[str, pd.DataFrame]:
    """Inject the NC-D2-03 fault where NC-D2-03 injects it: the control totals.

    Per small area, so each area's household TOTAL is untouched and only the
    shape changes - which is the point of the fault: a check that verifies
    totals passes it. Re-integerised by largest remainder against each area's
    own total, so the result is a vector of whole households exactly as the
    real scale-down produces.
    """
    out = {k: v.copy() for k, v in marginals.items()}
    hs = out[key].astype(float)
    move = hs[source] * float(fraction)
    hs[source] = hs[source] - move
    hs[sink] = hs[sink] + move
    repaired = hs.copy()
    for area in repaired.index:
        row = repaired.loc[area].to_numpy(dtype=float)
        target = int(round(float(marginals[key].loc[area].sum())))
        floor = np.floor(row).astype(int)
        short = target - int(floor.sum())
        rem = row - floor
        if short > 0:
            floor[np.argsort(-rem)[:short]] += 1
        elif short < 0:
            floor[np.argsort(rem)[:-short]] -= 1
        repaired.loc[area] = floor
    out[key] = repaired.astype(int)
    return out


@functools.lru_cache(maxsize=4)
def _plan_and_reference(master_seed: int = 1) -> tuple[Any, pd.Series, pd.Series]:
    """The scale-down plan, SAPS town counts, and the scaled target.

    Cached: building the marginals takes a couple of seconds and the ensemble
    control calls this for both arms.
    """
    import baile_nua.sources_registry  # noqa: F401
    from baile_nua.population import saps, scale_down

    reference = saps.build_marginals()
    plan = scale_down.build_both(reference, master_seed=master_seed)["proportional"]
    return (
        plan,
        reference["household_size"].town_total,
        plan.marginals["household_size"].sum(axis=0),
    )


def run_generator_ensemble(
    *, k: int = ENSEMBLE_K, shift_fraction: float = 0.0, base_seed: int = 5000,
) -> dict[str, Any]:
    """Run the household synthesis K times and return the realised marginals.

    ``shift_fraction`` injects the NC-D2-03 fault into the control totals; zero
    is the correct generator, and is what the false-positive control runs.
    """
    from baile_nua.population import households as hh

    plan, saps_town, scaled_target = _plan_and_reference()
    marginals = (
        plan.marginals if shift_fraction == 0.0
        else _shift_control_totals(plan.marginals, fraction=shift_fraction)
    )
    cats = list(saps_town.index)
    reference_date = pd.Timestamp("2022-01-01").date()
    runs: list[pd.Series] = []
    for i in range(int(k)):
        result = hh.synthesise_households(
            marginals, master_seed=base_seed + i, reference_date=reference_date
        )
        sizes = pd.Series(
            ["8+" if h.size >= 8 else str(h.size) for h in result.households]
        )
        runs.append(sizes.value_counts().reindex(cats).fillna(0).astype(int))
    return {
        "k": int(k),
        "shift_fraction": float(shift_fraction),
        "runs": runs,
        "saps_town": saps_town,
        "scaled_target": scaled_target,
    }


def check_generator_bias(ensemble: dict[str, Any]) -> None:
    """The intended test: the ensemble mean against the contracted reference.

    Raises :class:`EnsembleBiasDetected` when the generator is biased. Also
    checks the other half - that the contracted reference has not itself
    drifted away from SAPS beyond the declared repair budget - because a check
    that only ever compares the generator against its own target could be
    satisfied by a pipeline whose target is wrong.
    """
    cr = contracted_reference(ensemble["saps_town"], ensemble["scaled_target"])

    # Half one: the declared transformation must stay inside its budget.
    if cr["target_vs_saps_max_abs_z"] > ENSEMBLE_TARGET_VS_SAPS_MAX_ABS_Z:
        raise EnsembleBiasDetected(
            f"the scaled control totals have drifted from SAPS beyond the "
            f"declared repair budget: max |z| {cr['target_vs_saps_max_abs_z']} "
            f"exceeds {ENSEMBLE_TARGET_VS_SAPS_MAX_ABS_Z} (worst category "
            f"'{cr['target_vs_saps_worst_category']}'). The person-total "
            f"repair may use the sampling-error budget and may not exceed it "
            f"(D-010)."
        )

    # Half two: the generator must reproduce those totals.
    detail, summary = ensemble_marginal_acceptance(
        cr["reference_proportions"], ensemble["runs"],
        label=f"shift_fraction={ensemble['shift_fraction']}",
    )
    if summary["verdict"] != "PASS":
        n = summary["mean_n_per_run"]
        worst = summary["worst_category"]
        bias_households = abs(
            float(detail.loc[worst, "ensemble_mean_proportion"])
            - float(detail.loc[worst, "reference_proportion"])
        ) * n
        raise EnsembleBiasDetected(
            f"generator bias detected: over K={summary['k_runs']} runs the "
            f"ensemble mean household-size marginal departs from the control "
            f"totals the generator was given by max |z| "
            f"{summary['observed_max_abs_z']}, against a Bonferroni t band of "
            f"{summary['t_crit_bonferroni']} on {summary['degrees_of_freedom']} "
            f"degrees of freedom. Worst category '{worst}': "
            f"{bias_households:.1f} households, total variation distance "
            f"{summary['total_variation_distance']}. The generator's own "
            f"run-to-run standard deviation on this marginal is "
            f"{summary['max_across_run_sd']:.2e}, so this is bias and not "
            f"variability."
        )


def _build_shifted_ensemble() -> dict[str, Any]:
    return run_generator_ensemble(k=ENSEMBLE_K, shift_fraction=0.10)


def _correct_population_passes(_artefact: Any) -> None:
    """The false-positive control, and the check that shaped the design.

    A correct generator must pass. This is not a formality: the *literal*
    reading of "test the ensemble mean against SAPS" fails here, and measurably
    so. Once the standard error shrinks to the generator's own precision, the
    deliberate person-total repair - which moves the two-person share by
    -0.0251 and the three-person share by +0.0228 to satisfy both of R03's
    ranges (I-012, D-010) - sits about 55 standard errors from raw SAPS, and a
    correct population is rejected at every K from 4 upwards. Measured, not
    argued.

    So the ensemble tests the generator against the target the declared
    procedure produces, and the deviation of that target from SAPS is bounded
    separately by ENSEMBLE_TARGET_VS_SAPS_MAX_ABS_Z. Two questions, two
    references, both checked.
    """
    check_generator_bias(run_generator_ensemble(k=ENSEMBLE_K, shift_fraction=0.0))


register(NegativeControl(
    control_id="NC-D2-03",
    title=(
        "Household-size marginal with 10% of its mass shifted "
        "(ensemble generator-bias check)"
    ),
    design_ref=(
        "9.3 day 2; 12 R04; I-020 and its amendment; D-026 power analysis"
    ),
    intended_test=(
        "baile_nua.validation.ensemble_control.check_generator_bias "
        f"(K={ENSEMBLE_K} runs)"
    ),
    expected_exception=EnsembleBiasDetected,
    expected_message="generator bias detected",
    build=_build_shifted_ensemble,
    invoke=check_generator_bias,
    must_still_pass=(
        (
            "a correct generator passes the ensemble check (false-positive control)",
            _correct_population_passes,
        ),
    ),
))
