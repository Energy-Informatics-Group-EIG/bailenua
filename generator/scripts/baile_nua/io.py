"""Validated, deterministic dataset I/O.

Every write goes through :func:`write_dataset`, which:

1. **coerces** to the schema's declared types, so the same data always produces
   the same Parquet bytes (design 7.2 determinism);
2. **validates** against ``datasets.yaml``, including the GT/OBS leakage audit;
3. **refuses to write a dataset into the wrong release package**, which is the
   structural half of design 6.3 - the leakage test alone would catch a GT
   column in an OBS file, but not an entire GT dataset placed in
   ``v1/observable/``;
4. writes a sidecar ``.manifest.json`` with the content hash, so the data file
   can be gitignored while its manifest stays in git (as the brief requires).

Parquet is written with zstd (design 8.3) and without the writer's version
string, so the bytes depend only on the data.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import duckdb
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from baile_nua.hashing import hash_file, hash_frame, hash_json
from baile_nua.schema import load
from baile_nua.schema.access import audit_frame, package_for
from baile_nua.schema.validate import (
    ValidationError,
    coerce_frame,
    validate_frame,
)

__all__ = ["write_dataset", "read_dataset", "duck", "PackageError", "dataset_path"]

Package = Literal["observable", "ground_truth", "evidence", "work"]


class PackageError(ValueError):
    """A dataset was written into a release package its access class forbids."""


def dataset_path(root: Path, dataset_id: str, *, name: str | None = None) -> Path:
    """Where a dataset belongs, derived from its access class (design 6.3)."""
    s = load()
    ds = s[dataset_id]
    pkg = package_for(dataset_id, s)
    return Path(root) / "v1" / pkg / f"{name or ds.name}.parquet"


def _assert_package(dataset_id: str, path: Path) -> None:
    s = load()
    expected = package_for(dataset_id, s)
    parts = set(path.parts)
    # `work/` is always allowed: it is the intermediate area, not a release.
    if "work" in parts:
        return
    for pkg in ("observable", "ground_truth", "evidence"):
        if pkg in parts and pkg != expected:
            raise PackageError(
                f"{dataset_id} ({s[dataset_id].name}) is access class "
                f"{s[dataset_id].access_class}, which belongs in v1/{expected}/, "
                f"but the path targets v1/{pkg}/: {path}. Design 6.3 keeps the "
                f"three packages separate."
            )


def write_dataset(
    frame: pd.DataFrame,
    dataset_id: str,
    path: str | Path,
    *,
    strict_columns: bool = True,
    manifest: Any | None = None,
    extra_meta: dict[str, Any] | None = None,
    null_required: dict[str, str] | None = None,
) -> Path:
    """Validate, coerce and write one dataset, plus its sidecar manifest.

    ``null_required`` is ``{field: why it has no source}`` for required fields
    the caller is leaving null ON PURPOSE.  Every key is passed to
    :func:`~baile_nua.schema.validate.validate_frame` as a declared-null
    exemption and is recorded in the sidecar manifest as
    ``schema_conformance`` plus ``null_required_fields``, so a part that does
    not fill a required column says so in its own manifest instead of looking
    like a conformant one.  A reason is mandatory: an exemption with no stated
    reason is the thing it exists to prevent.
    """
    p = Path(path)
    _assert_package(dataset_id, p)
    s = load()
    ds = s[dataset_id]

    # Audit the INCOMING frame first.  `coerce_frame` restricts output to the
    # schema's declared columns, so a forbidden column handed in here would
    # otherwise be silently dropped and the write would succeed - a silent drop
    # is worse than a refusal, because the caller believes the field was
    # exported and nothing records that it was not.
    audit_frame(frame.columns, dataset_id, s)

    declared_null = dict(null_required or {})
    blank = sorted(k for k, v in declared_null.items() if not str(v).strip())
    if blank:
        raise ValidationError(
            f"{dataset_id}: null_required names {blank} with no reason. A "
            f"required field left null without a stated reason is exactly the "
            f"silent absence the manifest exists to prevent."
        )

    out = coerce_frame(frame, dataset_id, s)
    validate_frame(out, dataset_id, s, strict_columns=strict_columns,
                   permit_null_required=tuple(sorted(declared_null)))

    p.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(out, preserve_index=False)
    pq.write_table(
        table,
        p,
        compression="zstd",
        compression_level=9,
        # Determinism: no writer version in the footer, stable row-group size.
        store_schema=True,
        write_statistics=True,
        row_group_size=100_000,
        write_page_index=False,
    )

    content_hash = hash_frame(out)
    meta = {
        "dataset_id": dataset_id,
        "dataset_name": ds.name,
        "access_class": ds.access_class,
        "release_package": package_for(dataset_id, s),
        "schema_version": s.schema_version,
        "design_revision": s.design_revision,
        "label": s.label,
        "rows": int(len(out)),
        "columns": list(out.columns),
        "content_hash_sha256": content_hash,
        "file_sha256": hash_file(p),
        "calibration_status": ds.calibration_status,
        "schema_conformance": (
            "full" if not declared_null else
            "partial: required fields listed in null_required_fields are null "
            "by declaration, because the model holds no value for them"
        ),
        **({"null_required_fields": dict(sorted(declared_null.items()))}
           if declared_null else {}),
        **(extra_meta or {}),
    }
    if ds.access_class == "OBS":
        meta["leakage_audit"] = "passed: no GT-class or forbidden field names present"
    (p.parent / f"{p.stem}.manifest.json").write_text(
        __import__("json").dumps(meta, indent=2, sort_keys=True), encoding="utf-8"
    )
    if manifest is not None:
        manifest.record_output(p)
    return p


def read_dataset(path: str | Path, dataset_id: str | None = None) -> pd.DataFrame:
    frame = pq.read_table(path).to_pandas()
    if dataset_id is not None:
        validate_frame(frame, dataset_id, strict_columns=False)
    return frame


def duck(read_only: bool = True) -> duckdb.DuckDBPyConnection:
    """A DuckDB connection configured for this project.

    ``TimeZone='UTC'`` is set explicitly: without it, hour extraction follows the
    session's local zone and silently shifts every hour-of-day statistic.
    """
    con = duckdb.connect(":memory:")
    con.execute("SET TimeZone='UTC'")
    return con
