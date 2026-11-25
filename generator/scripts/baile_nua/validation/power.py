"""Power analysis for the marginal-acceptance checks.

Design 9.3 names a negative control as "marginals shifted 10%" and NC-D2-03
plants exactly that.  The single-realisation check does not detect it, and the
first response to that (I-020) was to record the resolution as a limitation.
That was the wrong response: a negative control whose magnitude sits below its
check's resolution is not a recognised limitation, it is a control that cannot
fail, and recording it as a limitation leaves the gate reporting a number
nobody can act on.

This module answers the question that should have been asked before the
magnitude was chosen: **what is the smallest shift the check can see?**

Three quantities, because they answer three different questions, and conflating
them is how the original "12.8%" figure came to be quoted without its
assumptions.

``deterministic_resolution``
    The smallest shift whose *signature* exceeds the acceptance band, with no
    noise at all.  This is the right question for Baile Nua's generator,
    because the generator reproduces its household-size and household-type
    control totals EXACTLY - measured across-seed standard deviation 0.000000
    over twelve independent seeds - so there is no sampling variability in the
    statistic to average away.

``random_sample_power``
    The power of the same check if the population *were* a random draw of
    ``n`` households from the reference distribution.  This is the question the
    check's own band is calibrated for, since it uses the multinomial standard
    error at the scaled sample size, and it is the one that says what sample
    size the question needs.

``ensemble_power``
    The power of the ensemble check over K independent generator runs, judged
    at the generator's own measured precision rather than at multinomial
    sampling error.

**Why the two differ so much.** The check's band is the multinomial sampling
error of a 1,092-household draw, about 0.013 in proportion for a category near
p = 0.25. The generator's own reproduction error on the same statistic is
**zero**. So the band is roughly 28 times wider than the precision the thing
being tested actually has, and a bias comfortably inside the band is still an
unambiguous defect in the generator. That is not a flaw in the band - it is the
right band for "could a town of this size look like this by chance" - it is a
mismatch between that question and "is the generator biased", which is the
question a negative control about a shifted marginal is asking.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Callable

import numpy as np
import pandas as pd
from scipy import stats

__all__ = [
    "ShiftSpec",
    "ResolutionResult",
    "bonferroni_z",
    "deterministic_resolution",
    "random_sample_power",
    "required_n_for_power",
    "shift_counts",
]


@dataclasses.dataclass(frozen=True)
class ShiftSpec:
    """A mass-moving shift: take ``fraction`` of ``source`` and give it to ``sink``.

    This is NC-D2-03's fault exactly: the totals still match, so a check that
    verifies only totals passes it, and the shape is the only thing that
    changed.
    """

    source: str
    sink: str
    fraction: float

    def describe(self) -> str:
        return (
            f"{self.fraction:.1%} of the '{self.source}' category moved to "
            f"'{self.sink}'"
        )


@dataclasses.dataclass
class ResolutionResult:
    """What a check can and cannot see."""

    statistic: str
    n: int
    alpha: float
    n_categories: int
    z_critical: float
    planted_fraction: float
    planted_max_abs_z: float
    planted_detected: bool
    deterministic_resolution_fraction: float
    power_at_planted: float | None = None
    fraction_for_95pc_power: float | None = None
    fraction_for_80pc_power: float | None = None
    n_for_95pc_power_at_planted: int | None = None
    notes: str = ""

    def as_row(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def bonferroni_z(n_categories: int, alpha: float = 0.05) -> float:
    """The simultaneous critical value the acceptance band uses (design 12 R04).

    Reproduced here rather than imported so the power analysis cannot silently
    drift from the check: if the band changes, these two disagree and the test
    that compares them fails.
    """
    return float(stats.norm.ppf(1.0 - alpha / (2.0 * max(int(n_categories), 1))))


def shift_counts(counts: pd.Series, spec: ShiftSpec) -> pd.Series:
    """Apply a mass-moving shift to a count vector, preserving the total."""
    out = counts.astype(float).copy()
    move = out[spec.source] * float(spec.fraction)
    out[spec.source] -= move
    out[spec.sink] += move
    return out


def _max_abs_z(
    reference: pd.Series, observed_p: np.ndarray, n: int
) -> float:
    """max |z| against the reference, using the multinomial SE at size ``n``.

    The same quantity ``marginal_error`` computes, written out here so the
    power analysis depends on the band's *definition* rather than on a call
    into the synthesis pipeline.
    """
    p0 = (reference / reference.sum()).to_numpy(dtype=float)
    se = np.sqrt(np.clip(p0 * (1.0 - p0), 1e-12, None) / max(n, 1))
    return float(np.max(np.abs((observed_p - p0) / se)))


def deterministic_resolution(
    reference: pd.Series,
    *,
    n: int,
    spec: ShiftSpec,
    alpha: float = 0.05,
    tol: float = 1e-6,
) -> ResolutionResult:
    """The smallest shift whose signature alone exceeds the band.

    Solved by bisection on the shift fraction rather than algebraically,
    because the band's critical value depends on the category count and the
    standard error on the reference proportions, and a closed form would have
    to be re-derived every time either changed. Bisection cannot drift.

    This is the resolution that applies to Baile Nua's generator, whose
    household-size marginal has an across-seed standard deviation of exactly
    zero: with no variability there is nothing to average, so detection is a
    sharp threshold on the shift rather than a probability.
    """
    cats = list(reference.index)
    z_crit = bonferroni_z(len(cats), alpha)

    def signature(fraction: float) -> float:
        shifted = shift_counts(reference, dataclasses.replace(spec, fraction=fraction))
        p = (shifted / shifted.sum()).to_numpy(dtype=float)
        return _max_abs_z(reference, p, n)

    planted_z = signature(spec.fraction)

    lo, hi = 0.0, 1.0
    if signature(hi) <= z_crit:
        resolution = float("nan")
    else:
        while hi - lo > tol:
            mid = 0.5 * (lo + hi)
            if signature(mid) > z_crit:
                hi = mid
            else:
                lo = mid
        resolution = 0.5 * (lo + hi)

    return ResolutionResult(
        statistic=f"{spec.source}->{spec.sink} mass shift",
        n=int(n), alpha=alpha, n_categories=len(cats), z_critical=z_crit,
        planted_fraction=float(spec.fraction),
        planted_max_abs_z=planted_z,
        planted_detected=bool(planted_z > z_crit),
        deterministic_resolution_fraction=resolution,
        notes=(
            "Deterministic: no sampling variability. Applies to a generator "
            "that reproduces its control totals exactly, which Baile Nua's "
            "does (measured across-seed SD 0.000000 on household_size and "
            "household type over 12 seeds)."
        ),
    )


def random_sample_power(
    reference: pd.Series,
    *,
    n: int,
    fractions: tuple[float, ...],
    alpha: float = 0.05,
    n_trials: int = 4000,
    spec: ShiftSpec,
    seed: int = 20261008,
) -> pd.DataFrame:
    """Power of the single-realisation check against a RANDOM draw of ``n``.

    Monte Carlo rather than a non-central chi-square approximation, because the
    check's statistic is a maximum over categories of per-category z scores and
    not a chi-square: the approximation would be close but it would be an
    approximation to a different test.

    The row at ``fraction = 0`` is the false-positive rate, and it is the
    calibration check on this whole analysis: the band is a simultaneous
    Bonferroni band at ``alpha``, so an unshifted draw must be rejected at
    about ``alpha`` or below. If it is not, the band and this analysis disagree
    and neither can be trusted.
    """
    rng = np.random.default_rng(seed)
    p0 = (reference / reference.sum()).to_numpy(dtype=float)
    z_crit = bonferroni_z(len(reference), alpha)
    rows = []
    for fraction in fractions:
        shifted = shift_counts(reference, dataclasses.replace(spec, fraction=fraction))
        p1 = (shifted / shifted.sum()).to_numpy(dtype=float)
        draws = rng.multinomial(n, p1, size=n_trials) / float(n)
        se = np.sqrt(np.clip(p0 * (1.0 - p0), 1e-12, None) / max(n, 1))
        z = np.abs((draws - p0) / se)
        rejected = (z.max(axis=1) > z_crit)
        rows.append({
            "fraction": float(fraction),
            "mean_max_abs_z": float(z.max(axis=1).mean()),
            "rejection_rate": float(rejected.mean()),
            "n_trials": int(n_trials),
            "is_false_positive_row": bool(fraction == 0.0),
        })
    return pd.DataFrame(rows)


def required_n_for_power(
    reference: pd.Series,
    *,
    spec: ShiftSpec,
    target_power: float = 0.95,
    alpha: float = 0.05,
    n_trials: int = 3000,
    seed: int = 20261008,
    n_hi: int = 200_000,
) -> int:
    """Smallest ``n`` at which a RANDOM draw detects the planted shift.

    Answers "how many households would this question need", which is the
    number that makes the 10% magnitude's difficulty concrete: Cobh itself has
    5,257 households and the scaled town has 1,092.
    """
    lo, hi = 50, int(n_hi)

    def power_at(n: int) -> float:
        tab = random_sample_power(
            reference, n=n, fractions=(spec.fraction,), alpha=alpha,
            n_trials=n_trials, spec=spec, seed=seed,
        )
        return float(tab.rejection_rate.iloc[0])

    if power_at(hi) < target_power:
        return -1
    while lo < hi:
        mid = (lo + hi) // 2
        if power_at(mid) >= target_power:
            hi = mid
        else:
            lo = mid + 1
    return int(lo)
