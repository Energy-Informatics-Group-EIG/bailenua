"""Determinism suite: the reproducibility contract (design 8.2, 7.2).

The contract, and what each test here holds it to:

* "A counter-based RNG (Philox) is keyed by master seed, stream, entity ID,
  simulated day and draw counter.  **Results don't depend on execution order or
  worker count.**"  ->  :func:`test_draws_are_order_independent`,
  :func:`test_identical_hashes_at_1_8_and_max_workers`
* "Floating-point sums run in fixed order."  ->  :func:`test_fixed_order_reduction`
* "Re-rendering any home-period from its seed gives a byte-identical hash."
  ->  :func:`test_parquet_write_is_byte_identical`
* "Checkpoints ... content-hashed and chained."  ->  see test_checkpoint.py
"""

from __future__ import annotations

import concurrent.futures as cf
import random

import numpy as np
import pytest

from baile_nua.hashing import hash_array, hash_frame
from baile_nua.rng import SeedTree, Stream, stable_entity_id

pytestmark = pytest.mark.determinism


def _draw(seed: int, person: str, day: int) -> np.ndarray:
    return SeedTree(seed).generator(Stream.PERSON_TRAITS, person, day).normal(size=8)


def test_same_coordinate_gives_the_same_draw(seed_tree):
    a = seed_tree.generator(Stream.ACTIVITY_DURATION, "P-000007", 42).random(16)
    b = seed_tree.generator(Stream.ACTIVITY_DURATION, "P-000007", 42).random(16)
    assert np.array_equal(a, b)


def test_coordinates_are_independent(seed_tree):
    base = seed_tree.generator(Stream.ACTIVITY_DURATION, "P-000007", 42).random(16)
    for label, other in [
        ("stream", seed_tree.generator(Stream.ACTIVITY_SEQUENCE, "P-000007", 42)),
        ("entity", seed_tree.generator(Stream.ACTIVITY_DURATION, "P-000008", 42)),
        ("day", seed_tree.generator(Stream.ACTIVITY_DURATION, "P-000007", 43)),
        ("draw", seed_tree.generator(Stream.ACTIVITY_DURATION, "P-000007", 42, draw=1)),
    ]:
        assert not np.allclose(base, other.random(16)), f"{label} coordinate collided"


def test_different_master_seed_gives_different_draws():
    assert not np.allclose(_draw(1, "P-1", 0), _draw(2, "P-1", 0))


def test_draws_are_order_independent(master_seed):
    """The central property: visiting entities in any order gives the same values.

    A stateful RNG would fail this, which is precisely why the design mandates a
    counter-based one.
    """
    people = [f"P-{i:06d}" for i in range(1, 41)]
    forward = {p: _draw(master_seed, p, 7) for p in people}

    shuffled = people[:]
    random.Random(99).shuffle(shuffled)
    backward = {p: _draw(master_seed, p, 7) for p in shuffled}

    for p in people:
        assert np.array_equal(forward[p], backward[p]), p


@pytest.mark.parametrize("workers", [1, 8, 12])
def test_identical_hashes_at_1_8_and_max_workers(master_seed, workers):
    """Design 8.2 CI test: "Identical hashes at 1, 8 and maximum workers."

    12 is the logical-core count of the E1 target machine (I-005), so this is
    literally 1 / 8 / max here.
    """
    people = [f"P-{i:06d}" for i in range(1, 121)]
    serial = hash_array(np.concatenate([_draw(master_seed, p, 3) for p in people]))

    with cf.ThreadPoolExecutor(max_workers=workers) as pool:
        # map preserves input order; the point is that the *values* do not
        # depend on which worker computed them or when.
        parallel = hash_array(
            np.concatenate(list(pool.map(lambda p: _draw(master_seed, p, 3), people)))
        )
    assert parallel == serial


def test_fixed_order_reduction_is_bit_stable(master_seed):
    """Reductions run in sorted id order, so the float sum is bit-stable.

    Design 8.2: "Floating-point sums run in fixed order; no fast-math."  Summing
    the same values in a different order is *not* associative in IEEE-754, so the
    contract is not "sum them" but "sum them in sorted id order".
    """
    ids = [f"B-{i:04d}" for i in range(200)]
    values = {
        i: float(SeedTree(master_seed).generator(Stream.APPLIANCE_TRIGGER, i).random())
        for i in ids
    }

    def reduce_sorted(order):
        return sum(values[i] for i in sorted(order))

    shuffled = ids[:]
    random.Random(7).shuffle(shuffled)
    assert reduce_sorted(ids) == reduce_sorted(shuffled)


def test_numpy_reductions_really_are_order_sensitive():
    """The reason the sorted-and-exact discipline exists, measured not assumed.

    ``np.sum`` and a manual accumulation loop - which is what ``numba.njit``
    compiles - both depend on summation order at the 1e-9 to 1e-7 level.  That
    is invisible in a plot and fatal to a byte-identical hash.  If this test
    ever stops failing, the discipline could be relaxed, which is worth
    discovering explicitly rather than assuming.
    """
    rng = np.random.default_rng(0)
    a = rng.normal(size=1440) * 1e6
    idx = rng.permutation(a.size)
    b = a[idx]

    assert float(a.sum()) != float(b.sum()), "np.sum became order-independent"

    def accumulate(x):
        t = 0.0
        for v in x:
            t += v
        return t

    assert accumulate(a) != accumulate(b), "manual accumulation became order-independent"


def test_canonical_reduction_is_order_independent_and_exact():
    """Design 8.2: reductions run in sorted id order.

    ``sorted_sum`` is both order-independent (keys are sorted) and exact
    (``math.fsum`` is correctly rounded), so a feeder total cannot change with
    how its homes were partitioned across workers.
    """
    from baile_nua.reduce import sorted_sum, sorted_sum_arrays

    rng = np.random.default_rng(1)
    ids = [f"B-{i:04d}" for i in range(200)]
    values = dict(zip(ids, (rng.normal(size=200) * 1e6).tolist()))

    shuffled = dict(random.Random(7).sample(list(values.items()), len(values)))
    assert sorted_sum(values) == sorted_sum(shuffled)

    # and it survives the catastrophic-cancellation case exactly
    hard = {"B-0000": 1.0, "B-0001": 1e16, "B-0002": -1e16}
    assert sorted_sum(hard) == 1.0

    series = {f"B-{i:04d}": rng.normal(size=16) * 1e5 for i in range(30)}
    shuffled_series = dict(random.Random(3).sample(list(series.items()), len(series)))
    assert np.array_equal(sorted_sum_arrays(series), sorted_sum_arrays(shuffled_series))


def test_bare_int_stream_is_refused(seed_tree):
    """An undeclared stream number is how two subsystems silently collide."""
    with pytest.raises(TypeError, match="Stream member"):
        seed_tree.generator(5, "P-1")  # type: ignore[arg-type]


def test_stream_values_are_unique():
    values = [int(s) for s in Stream]
    assert len(values) == len(set(values)), "two streams share a value"


def test_parquet_write_is_byte_identical(tmp_path):
    """Design 7.2: re-rendering gives a byte-identical hash."""
    import hashlib

    import pandas as pd

    from baile_nua.io import write_dataset

    rows = [
        {
            "premises_id": f"MPRN-{i:018X}",
            "interval_start": "2022-03-01T00:00:00Z",
            "interval_end": "2022-03-01T00:30:00Z",
            "import_wh": 100.0 + i,
            "export_wh": 0.0,
            "interval_peak_w": 800.0 + i,
            "interval_min_w": 10.0,
            "export_config": "home_30min",
            "quality": "ok",
        }
        for i in range(32)
    ]
    frame = pd.DataFrame(rows)
    a = write_dataset(frame, "D19", tmp_path / "work" / "a.parquet")
    b = write_dataset(frame, "D19", tmp_path / "work" / "b.parquet")
    assert hashlib.sha256(a.read_bytes()).hexdigest() == hashlib.sha256(b.read_bytes()).hexdigest()


def test_frame_hash_is_column_order_invariant_and_row_order_sensitive():
    """The manifest hash normalises column order and NOT row order (I-030).

    This reverses the Day-1 choice and the direction of the reversal matters:
    a row-order invariant hash calls two different byte streams "the same
    content", which could only ever HIDE a determinism failure. Design 9.2's
    criterion is byte-identical output, checked with SHA-256 over the files
    themselves, and every dataset is written in a deterministic order anyway,
    so there is no legitimate reordering for the hash to absorb.
    """
    import pandas as pd

    f = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    assert hash_frame(f) == hash_frame(f[["b", "a"]])
    assert hash_frame(f) != hash_frame(f.iloc[::-1].reset_index(drop=True))
    assert hash_frame(f) != hash_frame(f.assign(a=[1, 2, 4]))


def test_the_row_order_independent_hash_is_still_available_and_correct():
    """Kept for the cases that want it, and it must still have the property."""
    import pandas as pd

    from baile_nua.hashing import hash_frame_row_order_independent as h

    f = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    assert h(f) == h(f.iloc[::-1].reset_index(drop=True))
    assert h(f) != h(f.assign(a=[1, 2, 4]))


def test_frame_hash_distinguishes_a_null_from_a_zero():
    """A null and a zero must never collide, whatever dtype represents missing."""
    import numpy as np
    import pandas as pd

    a = pd.DataFrame({"x": pd.array([1.0, np.nan, 3.0], dtype="float64")})
    b = pd.DataFrame({"x": pd.array([1.0, 0.0, 3.0], dtype="float64")})
    assert hash_frame(a) != hash_frame(b)
    c = pd.DataFrame({"x": pd.array([1, None, 3], dtype="Int64")})
    d = pd.DataFrame({"x": pd.array([1, 0, 3], dtype="Int64")})
    assert hash_frame(c) != hash_frame(d)


def test_frame_hash_is_stable_across_equivalent_dtypes_for_the_same_values():
    """The hash must not change because a column arrived as a different dtype.

    Determinism depends on this: ``coerce_frame`` normalises dtypes before the
    write, and the hash must agree with that normalisation rather than fight it.
    """
    import pandas as pd

    a = pd.DataFrame({"x": pd.array([1, 2, 3], dtype="Int64")})
    b = pd.DataFrame({"x": pd.array([1, 2, 3], dtype="int64")})
    assert hash_frame(a) == hash_frame(b)
