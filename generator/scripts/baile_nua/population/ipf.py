"""Iterative proportional fitting (design 5.2 step 3, design 8.1).

    Combine iterative proportional fitting with combinatorial optimisation, so
    households are built whole (a couple with two children aged 6 and 9) and
    match person-level and household-level marginals together.

IPF does the first half: it finds a joint distribution over household (type,
size) consistent with both marginals.  :mod:`baile_nua.population.households`
does the second half, turning that joint into whole households with plausible
members.

Written out rather than taken from ``ipfn`` for one reason that matters here:
determinism.  The iteration order, the zero-cell handling and the convergence
test all affect the last bits of the result, and the reproducibility contract
(design 8.2) needs them pinned and visible rather than inherited from a
dependency's defaults.
"""

from __future__ import annotations

import dataclasses

import numpy as np

__all__ = ["IPFResult", "ipf_2d", "IPFError"]


class IPFError(RuntimeError):
    """IPF could not converge, or the marginals are inconsistent."""


@dataclasses.dataclass
class IPFResult:
    table: np.ndarray
    iterations: int
    max_abs_marginal_error: float
    converged: bool
    structural_zeros: int

    def as_dict(self) -> dict[str, float | int | bool]:
        return {
            "iterations": self.iterations,
            "max_abs_marginal_error": float(self.max_abs_marginal_error),
            "converged": bool(self.converged),
            "structural_zeros": int(self.structural_zeros),
        }


def ipf_2d(
    seed_table: np.ndarray,
    row_marginal: np.ndarray,
    col_marginal: np.ndarray,
    *,
    max_iter: int = 2000,
    tol: float = 1e-9,
) -> IPFResult:
    """Fit ``seed_table`` to both marginals by alternating proportional scaling.

    ``seed_table`` carries the *structure*: a zero means the combination is
    impossible (a "one person household" of size 3), and IPF preserves zeros, so
    the structure survives the fit.  That is why a seed table is used rather
    than starting from ones.

    The marginals must sum to the same total; they are rescaled to their mean if
    they disagree slightly, and a disagreement beyond 1% raises, because at that
    point the two marginals are describing different populations and silently
    splitting the difference would hide it.
    """
    t = np.array(seed_table, dtype=np.float64)
    r = np.array(row_marginal, dtype=np.float64)
    c = np.array(col_marginal, dtype=np.float64)

    if t.ndim != 2:
        raise IPFError(f"seed table must be 2-D, got shape {t.shape}")
    if t.shape != (len(r), len(c)):
        raise IPFError(f"seed table {t.shape} does not match marginals ({len(r)}, {len(c)})")
    if (t < 0).any() or (r < 0).any() or (c < 0).any():
        raise IPFError("IPF inputs must be non-negative")

    rs, cs = r.sum(), c.sum()
    if rs <= 0 or cs <= 0:
        return IPFResult(np.zeros_like(t), 0, 0.0, True, int((t == 0).sum()))
    rel = abs(rs - cs) / max(rs, cs)
    if rel > 0.01:
        raise IPFError(
            f"row marginal sums to {rs:.1f} and column marginal to {cs:.1f}, a "
            f"{rel:.1%} disagreement. Two marginals that differ by more than 1% "
            f"describe different populations; splitting the difference would hide that."
        )
    target = (rs + cs) / 2.0
    r = r * (target / rs)
    c = c * (target / cs)

    structural_zeros = int((t == 0).sum())

    # Rows or columns whose marginal is positive but whose every seed cell is
    # zero cannot be fitted. That is a structural contradiction, not slow
    # convergence, so it is reported immediately.
    dead_rows = np.flatnonzero((t.sum(axis=1) == 0) & (r > 0))
    dead_cols = np.flatnonzero((t.sum(axis=0) == 0) & (c > 0))
    if dead_rows.size or dead_cols.size:
        raise IPFError(
            f"marginals require mass in rows {dead_rows.tolist()} / columns "
            f"{dead_cols.tolist()} where the seed table is entirely zero, so no "
            f"fit exists. Check the household type-size structure."
        )

    err = np.inf
    it = 0
    for it in range(1, max_iter + 1):
        # rows then columns, always in that order
        rsum = t.sum(axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            factor = np.where(rsum > 0, r / rsum, 0.0)
        t *= factor[:, None]

        csum = t.sum(axis=0)
        with np.errstate(divide="ignore", invalid="ignore"):
            factor = np.where(csum > 0, c / csum, 0.0)
        t *= factor[None, :]

        err = max(
            float(np.abs(t.sum(axis=1) - r).max()),
            float(np.abs(t.sum(axis=0) - c).max()),
        )
        if err <= tol:
            break

    return IPFResult(t, it, err, err <= tol, structural_zeros)
