"""Negative controls for the G-C generator modes and the T6 null control.

The ``NC-GC`` prefix, not ``NC-W2``: week 2 step 1's plausibility controls
already own NC-W2-01 to NC-W2-08, and the registry refused the collision -
which is the registry doing its job.

A null control that can only ever say "no effect" certifies nothing. These
three controls break each week-2 check on purpose and require it to notice:

NC-GC-01  a T6 null cohort with a causal effect secretly planted. The null
          control must detect predictive value - if it cannot, then its
          clean result on the real null cohort means only that it finds
          nothing anywhere.
NC-GC-02  a non-identifiable cohort with the correlation lowered to where the
          coefficients ARE recoverable. The mode must report that it is no
          longer generating the non-identifiability it claims - which is the
          failure that actually happened during the build, at r = 0.97.
NC-GC-03  a continuous-no-clusters cohort with real, well-separated classes
          planted. The validity gate must ACCEPT them. Without this the gate
          could reject clusters unconditionally and pass mode 3 forever.

NC-GC-02 and NC-GC-03 are the two halves of the same principle: a check has
to be able to fail *and* to succeed, or its verdict carries no information.
And NC-GC-02 is not hypothetical. The first version of the non-identifiable
mode used r = 0.97 and the assessment correctly reported that the
coefficients were estimable; this control is that episode turned into a
permanent test.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from baile_nua.validation.negative_control import NegativeControl, register

__all__ = ["CONTROL_IDS"]

CONTROL_IDS: tuple[str, ...] = ("NC-GC-01", "NC-GC-02", "NC-GC-03")


class NullControlDetectedAnEffect(AssertionError):
    """The T6 null control found predictive value, which is what it is for."""


class ModeIsNotAdversarial(AssertionError):
    """A G-C mode stopped generating the adversarial structure it claims."""


class ClusterGateDetectedPlantedClusters(AssertionError):
    """The validity gate found the three classes the cohort denied having.

    Raised on SUCCESS, like every negative control's intended check: the
    control's artefact is a cohort that claims no latent classes while
    containing three, and catching that lie is what the gate is for.
    """


# --------------------------------------------------------------------------- #
# NC-GC-01  the T6 null with an effect planted in it
# --------------------------------------------------------------------------- #

def _null_cohort_with_an_effect() -> Any:
    """The null cohort, with a real causal path added to the revealed outcome."""
    import dataclasses

    from baile_nua.mimic import gc_modes as gc

    c = gc.generate(gc.T6_NULL_MODE, n=2000, master_seed=4242)
    rng = np.random.default_rng(5)
    # A genuine causal effect of the stated score on revealed behaviour,
    # beyond anything the baseline covariates carry. This is exactly what the
    # null says is absent.
    revealed = c.revealed + 0.55 * c.stated + rng.normal(0.0, 0.05, c.n)
    return dataclasses.replace(c, revealed=revealed)


def _run_t6_null(cohort: Any) -> None:
    from baile_nua.mimic import gc_modes as gc

    a = gc.assess(cohort, seed=1)
    if a.observed_class != "PASS":
        raise NullControlDetectedAnEffect(
            f"the T6 null control reported {a.observed_class}: "
            f"{a.detail}"
        )


def _run_t6_null_on_the_real_null() -> None:
    """The same check on the untouched null cohort must come back clean."""
    from baile_nua.mimic import gc_modes as gc

    c = gc.generate(gc.T6_NULL_MODE, n=2000, master_seed=4242)
    a = gc.assess(c, seed=1)
    assert a.observed_class == "PASS", a.detail


register(NegativeControl(
    control_id="NC-GC-01",
    title="A T6 null cohort with a causal effect secretly planted in it",
    design_ref="5.14 T6 null causal-link control; K17; 9.3 week 2",
    intended_test="baile_nua.mimic.gc_modes.assess (causally_unrelated arm)",
    expected_exception=NullControlDetectedAnEffect,
    expected_message="SOFTWARE_DEFECT",
    build=_null_cohort_with_an_effect,
    invoke=_run_t6_null,
    must_still_pass=(
        ("the untouched null cohort still reports no predictive value",
         lambda _c: _run_t6_null_on_the_real_null()),
    ),
))


# --------------------------------------------------------------------------- #
# NC-GC-02  a non-identifiable mode that is no longer non-identifying
# --------------------------------------------------------------------------- #

def _identifiable_cohort() -> Any:
    """The same mode at r = 0.97, where the coefficients ARE recoverable.

    Not an invented number: this is the value the first version of the mode
    used, and the assessment reported a SOFTWARE_DEFECT against it because at
    r = 0.97 with n = 2000 the variance inflation is only about 17 and the
    standard errors come back near 0.054.
    """
    from baile_nua.mimic import gc_modes as gc

    return gc.build_non_identifiable(n=2000, master_seed=4242, rho=0.97)


def _run_non_identifiable(cohort: Any) -> None:
    from baile_nua.mimic import gc_modes as gc

    a = gc.assess(cohort, seed=1)
    if a.observed_class != "RECOGNISED_LIMITATION":
        raise ModeIsNotAdversarial(
            f"the non-identifiable mode reported {a.observed_class}: "
            f"{a.detail}"
        )


def _run_non_identifiable_at_full_collinearity(_cohort: Any) -> None:
    from baile_nua.mimic import gc_modes as gc

    c = gc.build_non_identifiable(n=2000, master_seed=4242)
    a = gc.assess(c, seed=1)
    assert a.observed_class == "RECOGNISED_LIMITATION", a.detail


register(NegativeControl(
    control_id="NC-GC-02",
    title="The non-identifiable G-C mode with the correlation lowered to r = 0.97",
    design_ref="5.14 G-C modes, non-identifiable; verify-vs-diagnose",
    intended_test="baile_nua.mimic.gc_modes.assess (non_identifiable arm)",
    expected_exception=ModeIsNotAdversarial,
    expected_message="recoverable",
    build=_identifiable_cohort,
    invoke=_run_non_identifiable,
    must_still_pass=(
        ("the mode at its real correlation is still a recognised limitation",
         _run_non_identifiable_at_full_collinearity),
    ),
))


# --------------------------------------------------------------------------- #
# NC-GC-03  a cohort that claims no clusters and has three
# --------------------------------------------------------------------------- #
#
# The first version of this control had the polarity inverted: it handed the
# gate three real clusters and required the gate to ACCEPT them, raising only
# if it rejected. That is a POSITIVE control - a sensitivity check - and the
# negative-control harness correctly reported NOT_DETECTED when the gate did
# the right thing, because nothing raised. The harness was right and the
# control was wrong.
#
# The same substance fits the pattern once the artefact is the broken thing:
# a continuous-no-clusters cohort whose latents have been replaced by three
# well-separated classes while the cohort still CLAIMS k_true = 1. The
# validity gate must notice the lie. That exercises the gate's sensitivity -
# which is what the original intent was - and it fails if the gate rejects
# clusters unconditionally, which is the failure worth guarding against.


def _cohort_claiming_no_clusters_but_having_three() -> Any:
    """A mode-3 cohort with real classes substituted into its latents."""
    import dataclasses

    from baile_nua.mimic import gc_modes as gc

    c = gc.generate("continuous_no_clusters", n=2100, master_seed=4242)
    rng = np.random.default_rng(99)
    centres = np.array([[-4.0, -4.0, 0.0], [4.0, -4.0, 0.0], [0.0, 4.0, 0.0]])
    planted = np.vstack([
        rng.multivariate_normal(ctr, np.eye(3) * 0.6, 700) for ctr in centres
    ])
    truth = dict(c.planted)
    truth["latents"] = planted          # k_true stays 1: that is the lie
    return dataclasses.replace(c, planted=truth)


def _run_cluster_gate(cohort: Any) -> None:
    from baile_nua.mimic import gc_modes as gc

    a = gc.assess(cohort, seed=1)
    if a.observed_class != "PASS":
        raise ClusterGateDetectedPlantedClusters(
            f"the validity gate found structure the cohort denied having: "
            f"{a.detail}"
        )
    # No raise means the gate reported no structure in three well-separated
    # classes, which the harness records as NOT_DETECTED - a gate that
    # rejects clusters unconditionally would pass the continuous-no-clusters
    # mode forever while detecting nothing.


def _gate_still_rejects_one_gaussian(_cohort: Any) -> None:
    """And the untouched mode-3 cohort is still called structureless."""
    from baile_nua.mimic import gc_modes as gc

    c = gc.generate("continuous_no_clusters", n=2100, master_seed=4242)
    a = gc.assess(c, seed=1)
    assert a.observed_class == "PASS", a.detail


register(NegativeControl(
    control_id="NC-GC-03",
    title="A cohort claiming no latent classes while containing three",
    design_ref="5.14 G-C modes, continuous-no-clusters; T3",
    intended_test="baile_nua.mimic.gc_modes.cluster_validity_gap",
    expected_exception=ClusterGateDetectedPlantedClusters,
    expected_message="found structure",
    build=_cohort_claiming_no_clusters_but_having_three,
    invoke=_run_cluster_gate,
    must_still_pass=(
        ("the untouched single-Gaussian cohort is still called structureless",
         _gate_still_rejects_one_gaussian),
    ),
))
