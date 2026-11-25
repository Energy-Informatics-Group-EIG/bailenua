"""One way out of this package: :func:`emit`.

Everything goes through :func:`baile_nua.io.write_dataset`, which is what the
engine's own :class:`~baile_nua.engine.stream_writer.StreamWriter` uses.  That
is not a convenience - it is what makes an exported part indistinguishable
from a streamed one: the same coercion, the same schema validation, the same
leakage audit, the same refusal to write a dataset into the wrong release
package, and the same sidecar manifest with ``rows``, ``columns``,
``access_class``, ``release_package``, ``content_hash_sha256``, ``file_sha256``
and, for OBS datasets, ``leakage_audit``.

What this module adds to the manifest is provenance that a streamed part does
not need and an exported one does: which run root it was read from, what was
renamed or derived on the way, and what is known to be missing from it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from baile_nua.export.context import ExportError, RunContext

__all__ = ["emit", "cleanup_stale_parts", "ROWS_PER_PART"]

#: One part per this many rows, matching the engine's practice of writing
#: numbered parts rather than one file per dataset.
ROWS_PER_PART = 1_000_000


def emit(
    frame: pd.DataFrame,
    dataset_id: str,
    ctx: RunContext,
    *,
    source: str,
    conversions: list[dict[str, Any]] | None = None,
    limitations: list[str] | None = None,
    extra: dict[str, Any] | None = None,
    null_required: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Write one dataset as numbered parts and return its export record.

    ``null_required`` is ``{required field: why the model holds no value for
    it}``.  It is forwarded to :func:`baile_nua.io.write_dataset`, which
    records it in each part's manifest, and it is echoed in the returned
    record so the export report names the gap as well as the part.
    """
    from baile_nua.io import write_dataset
    from baile_nua.schema import load
    from baile_nua.schema.access import package_for

    if frame is None or len(frame) == 0:
        raise ExportError(
            f"{dataset_id}: the exporter produced no rows. An empty part is "
            f"not an honest absence - it reads as 'the model produced nothing' "
            f"where the truth is 'the exporter produced nothing'. Record the "
            f"dataset in baile_nua.export.absent instead."
        )
    schema = load()
    package = package_for(dataset_id, schema)
    # Before writing: drop any part left by a previous, longer export of this
    # same dataset. Without it, a re-export that produces fewer parts leaves
    # the old tail behind and a reader globbing Dnn_part*.parquet silently
    # reads the new head and the stale tail as one dataset.
    removed = cleanup_stale_parts(dataset_id, ctx)
    n = len(frame)
    n_parts = max(1, -(-n // ROWS_PER_PART))
    written: list[dict[str, Any]] = []
    for part in range(n_parts):
        chunk = frame.iloc[part * ROWS_PER_PART:(part + 1) * ROWS_PER_PART]
        path = ctx.path_for(dataset_id, package, part=part)
        write_dataset(
            chunk.reset_index(drop=True), dataset_id, path,
            extra_meta={
                "part": part,
                "rows": int(len(chunk)),
                "streamed": False,
                "exported_by": f"baile_nua.export ({source})",
                "export_source": source,
                "export_conversions": list(conversions or []),
                "export_limitations": list(limitations or []),
                **ctx.provenance(),
                **(extra or {}),
            },
            null_required=null_required,
        )
        written.append({
            "path": str(path),
            "rows": int(len(chunk)),
            "bytes": int(path.stat().st_size),
            "manifest_bytes": int(
                (path.parent / f"{path.stem}.manifest.json").stat().st_size),
        })
    return {
        "verdict": "written",
        "dataset_id": dataset_id,
        "access_class": schema[dataset_id].access_class,
        "release_package": package,
        "rows": int(n),
        "columns": list(frame.columns),
        "parts": written,
        "bytes": int(sum(p["bytes"] + p["manifest_bytes"] for p in written)),
        "source": source,
        "conversions": list(conversions or []),
        "limitations": list(limitations or []),
        "replaced_parts": removed,
        **({"null_required_fields": dict(sorted((null_required or {}).items())),
            "schema_conformance": (
                "partial: the required fields in null_required_fields are "
                "null by declaration")}
           if null_required else {"schema_conformance": "full"}),
    }


def cleanup_stale_parts(dataset_id: str, ctx: RunContext) -> list[str]:
    """Remove parts of ``dataset_id`` left by a previous, longer export.

    A re-export that produces fewer parts than the last one would otherwise
    leave the tail behind, and a reader globbing ``Dnn_part*.parquet`` would
    read the new head and the old tail as one dataset.
    """
    from baile_nua.schema import load
    from baile_nua.schema.access import package_for

    package = package_for(dataset_id, load())
    base = ctx.out_root / package / (ctx.subdir or "")
    removed: list[str] = []
    for path in sorted(Path(base).glob(f"{dataset_id}_part*")):
        path.unlink()
        removed.append(str(path))
    return removed
