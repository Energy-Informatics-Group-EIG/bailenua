"""Parse and validate ``datasets.yaml`` into typed objects.

The loader enforces the schema-level rules the design states, so that a
malformed or unsafe dataset definition cannot reach the rest of the system:

* design 6.5 rule 1 - **every field of an OBS dataset must declare a
  ``mechanism``**: the real-world process that would produce the value.  A field
  with no such mechanism is rejected here, at load time, not at review time.
* design 5.1 - any field whose ``layer`` is ``persistent``, ``evolving`` or
  ``stochastic`` belongs to the hidden layers and may not sit in an OBS dataset.
* every ``enum`` reference must name a declared enumeration.
* ``gt_counterpart`` is only meaningful on an OBS field.
"""

from __future__ import annotations

import dataclasses
import functools
import re
from pathlib import Path
from typing import Any, Final

import yaml

__all__ = ["AccessClass", "Field", "Dataset", "Schema", "SchemaError", "load", "SCHEMA_PATH"]

SCHEMA_PATH: Final[Path] = Path(__file__).with_name("datasets.yaml")

#: Layers of the four-layer person state model that ML/RL must never see (5.1).
HIDDEN_LAYERS: Final[frozenset[str]] = frozenset({"persistent", "evolving", "stochastic"})

_VALID_TYPES: Final[frozenset[str]] = frozenset(
    {
        "string", "int", "float", "bool", "date", "timestamp", "json", "enum",
        "list[string]", "list[int]", "list[float]",
    }
)


class SchemaError(ValueError):
    """Raised when ``datasets.yaml`` breaks one of the design's schema rules."""


class AccessClass(str):
    """GT / OBS / META.  A ``str`` subclass so it round-trips through YAML."""

    GT: Final[str] = "GT"
    OBS: Final[str] = "OBS"
    META: Final[str] = "META"
    ALL: Final[tuple[str, ...]] = ("GT", "OBS", "META")


@dataclasses.dataclass(frozen=True, slots=True)
class Field:
    name: str
    type: str
    required: bool = False
    enum: str | None = None
    enum_values: tuple[Any, ...] | None = None
    unit: str | None = None
    layer: str | None = None
    notes: str | None = None
    id_prefix: str | None = None
    # OBS-only
    mechanism: str | None = None
    gt_counterpart: str | None = None
    # MIMIC crosswalk
    mimic_field: str | None = None
    mimic_trait: bool = False
    # a field that must always be null, kept so a test can assert it (D21)
    forbidden: bool = False

    @property
    def is_hidden_layer(self) -> bool:
        return self.layer in HIDDEN_LAYERS


@dataclasses.dataclass(frozen=True)  # no slots: cached_property needs __dict__
class Dataset:
    id: str
    name: str
    title: str
    access_class: str
    grain: str
    storage: str
    fields: tuple[Field, ...]
    subsystem: str | None = None
    partition_by: tuple[str, ...] = ()
    obs_view: str | None = None
    access_note: str | None = None
    keyed_by: str | None = None
    e1_in_scope: bool = False
    notes: str | None = None
    calibration_status: str | None = None
    forbidden_field_patterns: tuple[str, ...] = ()
    mimic_schema_version: str | None = None

    @functools.cached_property
    def field_map(self) -> dict[str, Field]:
        return {f.name: f for f in self.fields}

    @functools.cached_property
    def required_fields(self) -> tuple[str, ...]:
        return tuple(f.name for f in self.fields if f.required)

    @functools.cached_property
    def forbidden_regexes(self) -> tuple[re.Pattern[str], ...]:
        return tuple(re.compile(p) for p in self.forbidden_field_patterns)

    def __repr__(self) -> str:  # pragma: no cover
        return f"Dataset({self.id} {self.name} {self.access_class} nfields={len(self.fields)})"


@dataclasses.dataclass(frozen=True)
class Schema:
    schema_version: str
    design_revision: int
    design_frozen: str
    label: str
    units: dict[str, str]
    id_prefixes: dict[str, str]
    enums: dict[str, tuple[Any, ...]]
    datasets: dict[str, Dataset]

    # -- lookups --------------------------------------------------------------

    def by_access(self, access_class: str) -> dict[str, Dataset]:
        return {k: v for k, v in self.datasets.items() if v.access_class == access_class}

    def by_name(self, name: str) -> Dataset:
        for d in self.datasets.values():
            if d.name == name:
                return d
        raise KeyError(f"no dataset named {name!r}")

    def e1_datasets(self) -> dict[str, Dataset]:
        return {k: v for k, v in self.datasets.items() if v.e1_in_scope}

    def __getitem__(self, key: str) -> Dataset:
        """``schema["D05"]`` or ``schema["persons"]``."""
        if key in self.datasets:
            return self.datasets[key]
        return self.by_name(key)


def _field_from_yaml(ds_id: str, raw: dict[str, Any], enums: dict[str, Any]) -> Field:
    unknown = set(raw) - {f.name for f in dataclasses.fields(Field)}
    if unknown:
        raise SchemaError(f"{ds_id}.{raw.get('name')}: unknown field keys {sorted(unknown)}")
    if "name" not in raw or "type" not in raw:
        raise SchemaError(f"{ds_id}: a field is missing 'name' or 'type': {raw!r}")
    ftype = raw["type"]
    if ftype not in _VALID_TYPES:
        raise SchemaError(f"{ds_id}.{raw['name']}: unknown type {ftype!r}")
    if ftype == "enum" and not (raw.get("enum") or raw.get("enum_values")):
        raise SchemaError(f"{ds_id}.{raw['name']}: type 'enum' needs 'enum' or 'enum_values'")
    if raw.get("enum") and raw["enum"] not in enums:
        raise SchemaError(f"{ds_id}.{raw['name']}: enum {raw['enum']!r} is not declared")
    ev = raw.get("enum_values")
    return Field(
        name=raw["name"],
        type=ftype,
        required=bool(raw.get("required", False)),
        enum=raw.get("enum"),
        enum_values=tuple(ev) if ev is not None else None,
        unit=raw.get("unit"),
        layer=raw.get("layer"),
        notes=raw.get("notes"),
        id_prefix=raw.get("id_prefix"),
        mechanism=raw.get("mechanism"),
        gt_counterpart=raw.get("gt_counterpart"),
        mimic_field=raw.get("mimic_field"),
        mimic_trait=bool(raw.get("mimic_trait", False)),
        forbidden=bool(raw.get("forbidden", False)),
    )


def _dataset_from_yaml(ds_id: str, raw: dict[str, Any], enums: dict[str, Any]) -> Dataset:
    for key in ("name", "title", "access_class", "grain", "storage", "fields"):
        if key not in raw:
            raise SchemaError(f"{ds_id}: missing required dataset key {key!r}")
    access = raw["access_class"]
    if access not in AccessClass.ALL:
        raise SchemaError(f"{ds_id}: access_class must be one of {AccessClass.ALL}, got {access!r}")

    fields = tuple(_field_from_yaml(ds_id, f, enums) for f in raw["fields"])
    names = [f.name for f in fields]
    dupes = {n for n in names if names.count(n) > 1}
    if dupes:
        raise SchemaError(f"{ds_id}: duplicate field names {sorted(dupes)}")

    # ---- design 6.5 rule 1: OBS fields must name their mechanism -----------
    if access == AccessClass.OBS:
        no_mechanism = [f.name for f in fields if not f.mechanism]
        if no_mechanism:
            raise SchemaError(
                f"{ds_id} ({raw['name']}) is OBS, so design 6.5 rule 1 applies: every field "
                f"must name the real-world mechanism that would produce it. "
                f"Fields with no mechanism: {no_mechanism}"
            )
        # ---- design 5.1: hidden layers may not appear in an OBS dataset ----
        hidden = [f.name for f in fields if f.is_hidden_layer]
        if hidden:
            raise SchemaError(
                f"{ds_id} is OBS but declares hidden-layer fields {hidden} "
                f"(design 5.1: only the 'observation' layer is visible to ML/RL)"
            )

    # ---- gt_counterpart only makes sense on OBS ----------------------------
    if access != AccessClass.OBS:
        stray = [f.name for f in fields if f.gt_counterpart]
        if stray:
            raise SchemaError(f"{ds_id} is {access} but fields {stray} declare a gt_counterpart")

    return Dataset(
        id=ds_id,
        name=raw["name"],
        title=raw["title"],
        access_class=access,
        grain=raw["grain"],
        storage=raw["storage"],
        fields=fields,
        subsystem=raw.get("subsystem"),
        partition_by=tuple(raw.get("partition_by", ())),
        obs_view=raw.get("obs_view"),
        access_note=raw.get("access_note"),
        keyed_by=raw.get("keyed_by"),
        e1_in_scope=bool(raw.get("e1_in_scope", False)),
        notes=raw.get("notes"),
        calibration_status=raw.get("calibration_status"),
        forbidden_field_patterns=tuple(raw.get("forbidden_field_patterns", ())),
        mimic_schema_version=raw.get("mimic_schema_version"),
    )


@functools.lru_cache(maxsize=4)
def load(path: str | Path | None = None) -> Schema:
    """Load, validate and cache the schema.

    Cached because it is consulted on every write; the cache is keyed by path so
    a test can load a deliberately broken copy without poisoning it.
    """
    p = Path(path) if path is not None else SCHEMA_PATH
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise SchemaError(f"{p}: top level must be a mapping")

    enums = {k: tuple(v) for k, v in (raw.get("enums") or {}).items()}
    datasets_raw = raw.get("datasets") or {}
    if not datasets_raw:
        raise SchemaError(f"{p}: no datasets declared")

    datasets = {k: _dataset_from_yaml(k, v, enums) for k, v in datasets_raw.items()}

    # dataset names must be unique too, since code looks them up by name
    names = [d.name for d in datasets.values()]
    dupes = {n for n in names if names.count(n) > 1}
    if dupes:
        raise SchemaError(f"{p}: duplicate dataset names {sorted(dupes)}")

    return Schema(
        schema_version=str(raw["schema_version"]),
        design_revision=int(raw["design_revision"]),
        design_frozen=str(raw["design_frozen"]),
        label=str(raw["label"]),
        units=dict(raw.get("units") or {}),
        id_prefixes=dict(raw.get("id_prefixes") or {}),
        enums=enums,
        datasets=datasets,
    )
