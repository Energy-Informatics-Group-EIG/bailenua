"""Validators generated from ``datasets.yaml``.

Checks a frame against its dataset definition: required fields present, enum
values legal, types coercible, ``forbidden`` fields actually null, and the
access-class audit from :mod:`baile_nua.schema.access`.

These run on every write (:mod:`baile_nua.io`), so a dataset cannot reach disk
in a shape the schema does not describe.
"""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

from baile_nua.schema import access
from baile_nua.schema.model import Dataset, Field, Schema, load

__all__ = ["ValidationError", "validate_frame", "validate_rows", "coerce_frame"]


class ValidationError(ValueError):
    """A frame does not match its dataset definition."""


def _check_enum(ds: Dataset, f: Field, series: pd.Series, s: Schema) -> list[str]:
    if f.enum is not None:
        allowed = set(s.enums[f.enum])
    elif f.enum_values is not None:
        allowed = set(f.enum_values)
    else:
        return []
    present = series.dropna()
    if present.empty:
        return []
    bad = sorted({v for v in present.unique().tolist() if v not in allowed})
    if not bad:
        return []
    return [
        f"{ds.id}.{f.name}: values {bad[:8]} are not in enum "
        f"{f.enum or 'enum_values'} = {sorted(allowed)[:12]}"
    ]


def _check_type(ds: Dataset, f: Field, series: pd.Series) -> list[str]:
    present = series.dropna()
    if present.empty:
        return []
    t = f.type
    try:
        if t == "int":
            pd.to_numeric(present, downcast=None)
            nonint = present[present.map(lambda v: float(v) != int(float(v)))]
            if len(nonint):
                return [f"{ds.id}.{f.name}: declared int but holds non-integral values"]
        elif t == "float":
            pd.to_numeric(present)
        elif t == "bool":
            bad = {v for v in present.unique().tolist() if not isinstance(v, (bool, int))}
            if bad:
                return [f"{ds.id}.{f.name}: declared bool but holds {sorted(map(str, bad))[:5]}"]
        elif t in ("timestamp", "date"):
            pd.to_datetime(present, utc=(t == "timestamp"))
        elif t.startswith("list["):
            bad = [v for v in present.head(200) if not isinstance(v, (list, tuple))]
            if bad:
                return [f"{ds.id}.{f.name}: declared {t} but holds non-sequence values"]
    except (ValueError, TypeError) as exc:
        return [f"{ds.id}.{f.name}: declared {t} but not coercible ({exc})"]
    return []


def validate_frame(
    frame: pd.DataFrame,
    dataset_id: str,
    schema: Schema | None = None,
    *,
    strict_columns: bool = True,
    permit_null_required: Sequence[str] = (),
) -> None:
    """Raise :class:`ValidationError` or :class:`access.LeakageError` on any breach.

    Leakage is raised as its own type and never downgraded into a validation
    error, so CI can report the two separately.

    ``permit_null_required`` names required fields whose nulls are DECLARED:
    the writer is saying "this column has no source in the model and I am
    leaving it null on purpose".  It is the one escape from the required-null
    check and it is deliberately narrow:

    * the column must still be PRESENT, so a reader sees the field and its
      nulls rather than a frame that quietly lacks it;
    * the field must actually be declared required, so a stale entry is an
      error rather than a silently ignored string;
    * nothing else is relaxed - type, enum and ``forbidden`` checks all still
      run, and the leakage audit runs first as always.

    It exists because the alternative for a partially derivable dataset is one
    of the two things this project forbids: filling a required field with a
    plausible number, or lowering the schema so the gap stops showing.  A
    declared null does neither, and :func:`baile_nua.io.write_dataset` records
    it in the part's manifest so the deviation travels with the data.
    """
    s = schema if schema is not None else load()
    ds = s[dataset_id]

    permitted = tuple(dict.fromkeys(str(n) for n in permit_null_required))
    not_required = [n for n in permitted if n not in ds.required_fields]
    if not_required:
        raise ValidationError(
            f"{dataset_id}: permit_null_required names {not_required}, which "
            f"{'is' if len(not_required) == 1 else 'are'} not declared "
            f"required. A declared-null exemption that exempts nothing is a "
            f"stale claim about the schema, so it is refused rather than "
            f"ignored."
        )
    permitted_set = set(permitted)

    # Leakage first: it is the check with consequences outside this process.
    access.audit_frame(frame.columns, dataset_id, s)

    problems: list[str] = []

    missing = [n for n in ds.required_fields if n not in frame.columns]
    if missing:
        problems.append(f"{ds.id} ({ds.name}): missing required fields {missing}")

    if strict_columns:
        extra = sorted(set(frame.columns) - set(ds.field_map))
        if extra:
            problems.append(f"{ds.id}: undeclared columns {extra}")

    for name in frame.columns:
        f = ds.field_map.get(name)
        if f is None:
            continue
        col = frame[name]
        if f.required and name not in permitted_set and col.isna().any():
            n = int(col.isna().sum())
            problems.append(f"{ds.id}.{name}: required but {n} null value(s)")
        if f.forbidden and not col.isna().all():
            problems.append(
                f"{ds.id}.{name}: declared forbidden and must always be null "
                f"(design 5.13: no person is ever labelled by cluster)"
            )
        if f.type == "enum":
            problems.extend(_check_enum(ds, f, col, s))
        else:
            problems.extend(_check_type(ds, f, col))

    if problems:
        raise ValidationError(
            f"{len(problems)} schema violation(s) in {dataset_id}:\n  - "
            + "\n  - ".join(problems)
        )


def validate_rows(
    rows: Sequence[dict], dataset_id: str, schema: Schema | None = None, **kw
) -> pd.DataFrame:
    """Validate a list of row dicts and return the frame."""
    frame = pd.DataFrame(list(rows))
    validate_frame(frame, dataset_id, schema, **kw)
    return frame


def coerce_frame(
    frame: pd.DataFrame, dataset_id: str, schema: Schema | None = None
) -> pd.DataFrame:
    """Cast declared columns to their schema types, for stable Parquet output.

    Determinism depends on this: an ``int64`` column that arrives as ``float64``
    in one run and ``int64`` in another produces different bytes for the same
    data.
    """
    s = schema if schema is not None else load()
    ds = s[dataset_id]
    out = frame.copy()
    for name in out.columns:
        f = ds.field_map.get(name)
        if f is None:
            continue
        col = out[name]
        try:
            if f.type == "int":
                out[name] = col.astype("Int64")
            elif f.type == "float":
                out[name] = col.astype("float64")
            elif f.type == "bool":
                out[name] = col.astype("boolean")
            elif f.type == "timestamp":
                out[name] = pd.to_datetime(col, utc=True)
            elif f.type == "date":
                out[name] = pd.to_datetime(col).dt.date
            elif f.type in ("string", "enum"):
                out[name] = col.astype("string")
        except (ValueError, TypeError) as exc:
            raise ValidationError(f"{dataset_id}.{name}: cannot coerce to {f.type}: {exc}") from exc
    # Column order from the schema, so two runs write the same byte layout.
    ordered = [n for n in ds.field_map if n in out.columns]
    return out[ordered]
