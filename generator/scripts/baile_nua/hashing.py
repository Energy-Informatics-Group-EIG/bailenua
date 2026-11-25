"""Canonical hashing.

Determinism is a *byte-level* claim (design 7.2: "re-rendering any home-period
from its seed gives a byte-identical hash"), so every hash in the system goes
through one canonicaliser.  Two places where a naive hash silently differs
between runs, both handled here:

* **dict ordering.** JSON is serialised with sorted keys and no insignificant
  whitespace.
* **float formatting.** ``repr(0.1+0.2)`` is stable in CPython, but ``float32``
  vs ``float64`` and NaN sign bits are not.  Numeric arrays are hashed from
  their little-endian IEEE-754 bytes after normalising NaN.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

__all__ = [
    "canonical_json",
    "hash_json",
    "hash_bytes",
    "hash_file",
    "hash_frame",
    "hash_frame_row_order_independent",
    "hash_array",
    "chain",
]

_ALGO = "sha256"


def _default(o: Any) -> Any:
    # Every flavour of missing collapses to one canonical null. pandas has
    # several (``pd.NA`` for nullable dtypes, ``NaT`` for datetimes, ``None``,
    # ``nan``), and which one appears depends on the column's dtype rather than
    # on the data - so hashing them differently would make the same content
    # hash differently depending on how the frame happened to be built.
    if o is pd.NA or o is pd.NaT:
        return None
    try:
        if o is not None and not isinstance(o, (str, bytes, list, tuple, dict)) and pd.isna(o):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (set, frozenset)):
        return sorted(o, key=repr)
    if isinstance(o, Path):
        return str(o)
    if isinstance(o, (pd.Timestamp,)):
        return o.isoformat()
    if hasattr(o, "isoformat"):
        return o.isoformat()
    raise TypeError(f"cannot canonicalise {type(o).__name__} for hashing")


def canonical_json(obj: Any) -> bytes:
    """Deterministic JSON bytes: sorted keys, tight separators, UTF-8."""
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=_default
    ).encode("utf-8")


def hash_bytes(data: bytes) -> str:
    return hashlib.new(_ALGO, data).hexdigest()


def hash_json(obj: Any) -> str:
    return hash_bytes(canonical_json(obj))


def hash_file(path: str | Path, chunk: int = 1 << 20) -> str:
    h = hashlib.new(_ALGO)
    with open(path, "rb") as fh:
        while block := fh.read(chunk):
            h.update(block)
    return h.hexdigest()


def hash_array(a: np.ndarray) -> str:
    """Hash a numeric array from normalised little-endian bytes."""
    arr = np.ascontiguousarray(a)
    if arr.dtype.kind == "f":
        arr = arr.astype("<f8", copy=True)
        # One canonical NaN, so a sign bit or payload difference never shows up
        # as a determinism failure.
        arr[np.isnan(arr)] = np.nan
    elif arr.dtype.kind in "iu":
        arr = arr.astype("<i8", copy=False)
    elif arr.dtype.kind == "b":
        arr = arr.astype("<i8", copy=False)
    else:
        return hash_json(arr.tolist())
    h = hashlib.new(_ALGO)
    h.update(str(arr.shape).encode())
    h.update(arr.tobytes(order="C"))
    return h.hexdigest()


def _column_digest(col: pd.Series) -> str:
    """Canonical digest of one column, from bytes rather than from repr.

    Nulls are hashed as a separate mask, so a null and a zero can never collide
    however the column's dtype chooses to represent "missing" - pandas has
    ``pd.NA``, ``NaT``, ``None`` and ``nan``, and which one appears depends on
    the dtype rather than on the data.
    """
    h = hashlib.new(_ALGO)
    null = col.isna().to_numpy(dtype=bool)
    h.update(b"null:")
    h.update(np.packbits(null).tobytes())

    kind = getattr(col.dtype, "kind", None)
    if isinstance(col.dtype, pd.DatetimeTZDtype) or kind == "M":
        v = col.dt.tz_convert("UTC") if isinstance(col.dtype, pd.DatetimeTZDtype) else col
        a = v.astype("int64", errors="ignore").to_numpy(dtype="int64", na_value=0)
        h.update(b"ts:")
        h.update(np.ascontiguousarray(a, dtype="<i8").tobytes())
        return h.hexdigest()

    try:
        if pd.api.types.is_bool_dtype(col):
            a = col.to_numpy(dtype="int8", na_value=0)
            h.update(b"bool:")
            h.update(np.ascontiguousarray(a, dtype="<i1").tobytes())
            return h.hexdigest()
        if pd.api.types.is_integer_dtype(col):
            a = col.to_numpy(dtype="int64", na_value=0)
            h.update(b"int:")
            h.update(np.ascontiguousarray(a, dtype="<i8").tobytes())
            return h.hexdigest()
        if pd.api.types.is_float_dtype(col):
            a = col.to_numpy(dtype="float64", na_value=np.nan).astype("<f8", copy=True)
            # One canonical NaN, so a sign bit or payload never shows up as a
            # determinism failure.
            a[np.isnan(a)] = np.nan
            h.update(b"float:")
            h.update(np.ascontiguousarray(a).tobytes())
            return h.hexdigest()
    except (TypeError, ValueError):
        pass

    # Strings and categories: factorise, then hash the (few) distinct values
    # and the (many) integer codes. Encoding 66 million strings individually in
    # Python is what made this function the single most expensive thing in the
    # whole pipeline; there are only ever a handful of distinct device ids.
    if pd.api.types.is_string_dtype(col) or isinstance(col.dtype, pd.CategoricalDtype):
        codes, uniques = pd.factorize(col, use_na_sentinel=True)
        h.update(b"str:")
        for u in list(uniques):
            b = str(u).encode("utf-8")
            h.update(len(b).to_bytes(8, "little"))
            h.update(b)
        h.update(np.ascontiguousarray(codes, dtype="<i8").tobytes())
        return h.hexdigest()

    # Anything else - a column of dicts, say, as D19's building_energy_profile
    # is - falls back to canonical JSON per element. Correct, and slow, and the
    # columns it applies to are small.
    h.update(b"json:")
    for v in col.tolist():
        h.update(canonical_json(v))
        h.update(b"\x00")
    return h.hexdigest()


def hash_frame(frame: pd.DataFrame) -> str:
    """Content hash of a dataframe: column-order independent, ROW-ORDER SENSITIVE.

    **This reverses a Day-1 choice, deliberately, and the reasoning matters
    (I-030).**  The first version normalised row order too, by hashing each row
    to canonical JSON and sorting the digests.  Two things were wrong with it.

    *It was the single most expensive operation in the entire system.*  Measured
    on three days of the E1 estate: 32.8 seconds of a 47-second writer, from
    600,000 ``json.dumps`` calls - several times the cost of the physics,
    occupancy, device and observation simulation it was recording.  Over a
    year of 66 million D18 rows it would have dominated everything.

    *It was weaker than what it is used for, not stronger.*  A row-order
    independent hash calls two different byte streams "the same content".  But
    the thing this hash records in a manifest is a Parquet file, and design
    9.2's criterion is "byte-identical outputs at 1, 8 and maximum workers" -
    which the determinism harness checks with SHA-256 over the files
    themselves, and which is order-sensitive by nature.  So the normalisation
    could only ever hide a difference the gate cares about.  Every dataset this
    writes is emitted in a deterministic order anyway (households in sorted id
    order, days in calendar order), so there is no legitimate reordering for it
    to absorb.

    Column order is still normalised, because that genuinely is incidental.

    :func:`hash_frame_row_order_independent` keeps the old behaviour for
    anything that needs it.
    """
    cols = sorted(map(str, frame.columns))
    norm = frame.reindex(columns=cols)
    h = hashlib.new(_ALGO)
    h.update(canonical_json(cols))
    h.update(str(len(norm)).encode())
    for c in cols:
        h.update(c.encode("utf-8"))
        h.update(b"\x00")
        h.update(_column_digest(norm[c]).encode())
    return h.hexdigest()


def hash_frame_row_order_independent(frame: pd.DataFrame) -> str:
    """Content hash that ignores row order, by sorting per-row digests.

    Kept because the property is occasionally the one wanted - comparing two
    unordered sets of records - but it is O(rows) in Python and must not be
    used on a large frame. :func:`hash_frame` is what the write path uses.
    """
    cols = sorted(map(str, frame.columns))
    row_digests: list[str] = []
    norm = frame.reindex(columns=cols)
    for row in norm.itertuples(index=False, name=None):
        row_digests.append(hash_json(list(row)))
    row_digests.sort()
    h = hashlib.new(_ALGO)
    h.update(canonical_json(cols))
    for d in row_digests:
        h.update(d.encode())
    return h.hexdigest()


def chain(previous: str | None, payload_hash: str) -> str:
    """One link of a hash chain.

    ``chain(None, h)`` starts a chain.  Each link commits to its predecessor, so
    editing any earlier checkpoint invalidates every later one - which is what
    design 8.2 requires of "upstream edits".
    """
    prev = previous or ("0" * 64)
    return hash_bytes(f"{prev}:{payload_hash}".encode("ascii"))
