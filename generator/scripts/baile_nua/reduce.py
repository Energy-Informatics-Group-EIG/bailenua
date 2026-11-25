"""Canonical reductions (design 8.2: "Floating-point sums run in fixed order").

Measured on the E1 target machine, Python 3.12.6 / numpy 2.2.6:

=============================  =================
Reduction                      Order-sensitive?
=============================  =================
``np.sum`` (float64, n=1440)   **yes**, ~7e-9 absolute
``np.sum`` (float32)           **yes**
manual accumulation loop       **yes**, ~2e-7 absolute
  (what ``numba.njit`` compiles)
builtin ``sum`` (Neumaier,     no
  CPython >= 3.12)
``math.fsum`` (exact)          no
=============================  =================

So the two reductions the hot loops naturally reach for are exactly the two that
break byte-identical output across worker counts: a 7e-9 drift is invisible in a
plot and fatal to a hash.  Every reduction that crosses entities - summing homes
onto a feeder, summing appliances onto a house meter - therefore goes through
this module.

Two guarantees, not one:

* **fixed order** - keys are sorted before summing, so the result cannot depend
  on which worker finished first;
* **exactness** - ``math.fsum`` is correctly rounded, so the result does not
  depend on the order *within* the sorted sequence either, and re-grouping a
  feeder's homes cannot change its total.

Inside a single entity's own time series, order *is* the contract (minute 1 then
minute 2), and ordinary numpy is correct and fast there.  This module is for
reductions **across** entities, where order is an artefact of scheduling.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from typing import TypeVar

import numpy as np

__all__ = ["sorted_sum", "sorted_sum_arrays", "exact_sum", "sorted_mean"]

K = TypeVar("K")


def exact_sum(values: Iterable[float]) -> float:
    """Correctly-rounded sum of an already-ordered sequence."""
    return math.fsum(values)


def sorted_sum(contributions: Mapping[K, float]) -> float:
    """Sum a mapping of entity id to value, in sorted id order, exactly.

    This is the reduction design 8.2 means by "all reductions run in sorted ID
    order".
    """
    return math.fsum(contributions[k] for k in sorted(contributions))


def sorted_mean(contributions: Mapping[K, float]) -> float:
    if not contributions:
        raise ValueError("cannot take the mean of no contributions")
    return sorted_sum(contributions) / len(contributions)


def sorted_sum_arrays(contributions: Mapping[K, np.ndarray]) -> np.ndarray:
    """Element-wise sum of equal-length series, in sorted id order, exactly.

    Used for the epoch barrier: summing each home's 15-minute net-power series
    onto its feeder.  Done element-wise with :func:`math.fsum` so a feeder total
    is independent of how the homes were partitioned across workers.

    Cost is O(n_entities x n_steps) in Python, which is acceptable because it
    runs once per epoch over 50 homes, not inside the 1-minute loop.
    """
    if not contributions:
        raise ValueError("cannot sum no contributions")
    keys = sorted(contributions)
    lengths = {len(contributions[k]) for k in keys}
    if len(lengths) != 1:
        raise ValueError(f"contributions have differing lengths: {sorted(lengths)}")
    n = lengths.pop()
    stacked = [np.asarray(contributions[k], dtype=np.float64) for k in keys]
    out = np.empty(n, dtype=np.float64)
    for i in range(n):
        out[i] = math.fsum(col[i] for col in stacked)
    return out
