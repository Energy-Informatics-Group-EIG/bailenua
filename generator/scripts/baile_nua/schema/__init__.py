"""Schema subsystem: ``datasets.yaml`` is the single source of truth (D-005).

Everything downstream is generated from it, never written by hand:

* :func:`load` - the parsed, validated schema
* :mod:`baile_nua.schema.validate` - row and frame validators
* :mod:`baile_nua.schema.access` - GT/OBS/META allow-lists for the leakage test
* :mod:`baile_nua.schema.docgen` - the data dictionary in the evidence view
"""

from baile_nua.schema.model import (
    AccessClass,
    Dataset,
    Field,
    Schema,
    SchemaError,
    load,
)

__all__ = ["AccessClass", "Dataset", "Field", "Schema", "SchemaError", "load"]
