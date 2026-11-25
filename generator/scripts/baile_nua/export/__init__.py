"""Dataset exporters: the declared datasets the frozen engine does not stream.

The engine writes five datasets as it runs (D11, D13, D16, D18, D19) through
:class:`~baile_nua.engine.stream_writer.StreamWriter`.  The other twenty-six
are declared in ``schema/datasets.yaml`` and have to be built from the state
the engine leaves behind: the t0 synthesis, the weather realisation, the
slice, the evidence artefacts and the non-sensor observation models.

That is what this package does, and the three rules it works under:

1. **It reads the frozen engine; it never changes it.**  Every value comes from
   a frozen constructor, a frozen generator, or a written part.
2. **It writes through** :func:`baile_nua.io.write_dataset`, so an exported
   part is validated, coerced, leakage-audited and manifested exactly as a
   streamed one is.
3. **It never invents a row.**  A dataset whose required fields have no model
   behind them stays absent, with its reason recorded in
   :mod:`baile_nua.export.absent` and returned by :func:`export_all`.

Parameterised by paths, so the same call serves any run::

    from baile_nua.export import export_all
    report = export_all("v1", "v1")
"""

from __future__ import annotations

from baile_nua.export.absent import ABSENT, OWNED_ELSEWHERE, reason_for
from baile_nua.export.context import ExportError, RunContext
from baile_nua.export.dispatch import (
    ALL_DATASETS,
    EXPORTERS,
    WRITTEN_BY_THE_ENGINE,
    export_all,
)

__all__ = [
    "ABSENT",
    "ALL_DATASETS",
    "EXPORTERS",
    "ExportError",
    "OWNED_ELSEWHERE",
    "RunContext",
    "WRITTEN_BY_THE_ENGINE",
    "export_all",
    "reason_for",
]
