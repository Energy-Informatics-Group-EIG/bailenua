"""Access-class enforcement: GT / OBS / META separation.

Design 5.1: *"A leakage test in CI fails any benchmark dataset that contains a
column from the first three layers."*  Design 6.3: the observable package
contains OBS datasets only.  Design 6.5 rule 1 extends the test to D28-D31.
R09/E0-8: no occupancy, presence or person-level field is ever transmitted.

Everything here is derived from ``datasets.yaml`` (D-006), so adding a GT field
automatically extends the test.  There is no hand-maintained deny-list to forget
to update.

The three checks, in increasing strictness:

``assert_fields_declared``
    Every column appears in the dataset's own schema.  Catches a stray column
    before it is ever classified.

``assert_no_gt_field_names``
    No column shares a name with a field that is GT-class **anywhere** in the
    schema, with a small allow-list of join keys that legitimately appear on
    both sides.  This is the design 5.1 test.

``assert_no_forbidden_patterns``
    No column name matches the dataset's own ``forbidden_field_patterns``.  This
    is the R09 test for D19 and the 5.14 forbidden-field test for D25: it is
    name-based and content-blind on purpose, because R09 is a statement about
    what is *transmitted*, not about what happens to be inferable.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Final

from baile_nua.schema.model import AccessClass, Schema, load

__all__ = [
    "LeakageError",
    "gt_field_names",
    "obs_field_names",
    "hidden_layer_field_names",
    "person_level_field_names",
    "SHARED_JOIN_KEYS",
    "assert_fields_declared",
    "assert_no_gt_field_names",
    "assert_no_forbidden_patterns",
    "audit_frame",
    "package_for",
]

#: Keys that legitimately appear in both GT and OBS datasets.  Each one is here
#: for a stated reason, and the list is deliberately short.
SHARED_JOIN_KEYS: Final[frozenset[str]] = frozenset(
    {
        # The observable key.  Opaque, keyed to the property not the household
        # (6.4 item 2).  Its GT side is D02.premises_id, which is why the name
        # appears in both classes.
        "premises_id",
        # Interval and series mechanics, identical on both sides by nature.
        "ts",
        "interval_start",
        "interval_end",
        "valid_from",
        "valid_to",
        "unit",
        "quality",
        "provenance",
        "revision",
        "version",
        # The weather realisation id: 6.5 rule 2 requires D15 (GT site) and D31
        # (OBS station) to be tied to the same realisation, so the id must be in
        # both.  It carries no occupancy or person information.
        "realisation_id",
        # Trial arm appears in D27/D28 (OBS, what the operator holds) and is not
        # a GT-only concept.
        "trial_arm",
        "tier_consented",
        # MIMIC's own participant UUID.  It is the join between D25 (OBS, what
        # MIMIC holds) and D26 (GT, the answer key), which is the whole point of
        # an answer key.  The UUID itself carries no person information, and the
        # crosswalk to person_id lives only in D26.
        "participant_id",
    }
)


class LeakageError(AssertionError):
    """A GT-class or forbidden field reached an observable output.

    Subclasses ``AssertionError`` so that a leak fails a test run even if a
    caller swallows ``Exception``.
    """


def _schema(schema: Schema | None) -> Schema:
    return schema if schema is not None else load()


def gt_field_names(schema: Schema | None = None) -> frozenset[str]:
    """Every field name that appears in a GT-class dataset."""
    s = _schema(schema)
    return frozenset(
        f.name
        for d in s.datasets.values()
        if d.access_class == AccessClass.GT
        for f in d.fields
    )


def obs_field_names(schema: Schema | None = None) -> frozenset[str]:
    s = _schema(schema)
    return frozenset(
        f.name
        for d in s.datasets.values()
        if d.access_class == AccessClass.OBS
        for f in d.fields
    )


def hidden_layer_field_names(schema: Schema | None = None) -> frozenset[str]:
    """Fields in the persistent / evolving / stochastic layers (design 5.1)."""
    s = _schema(schema)
    return frozenset(
        f.name for d in s.datasets.values() for f in d.fields if f.is_hidden_layer
    )


def person_level_field_names(schema: Schema | None = None) -> frozenset[str]:
    """Every field R09 means by "person-level", derived from the schema.

    R09 as interpreted at E0-8: *"no occupancy, presence or person-level field is
    ever transmitted"*.  "Person-level" is not a hand-written list - it is
    exactly the union of

    * every field in a hidden layer of the four-layer model (design 5.1), and
    * every MIMIC latent trait (design 5.14 level 1, R06),

    both read from ``datasets.yaml``.  Adding a trait or a hidden-layer field
    therefore extends the R09 refusal automatically (decision D-006); nobody has
    to remember to update a deny-list.
    """
    s = _schema(schema)
    traits = frozenset(
        f.name for d in s.datasets.values() for f in d.fields if f.mimic_trait
    )
    return hidden_layer_field_names(s) | traits


def package_for(dataset_id: str, schema: Schema | None = None) -> str:
    """Which release package a dataset belongs in (design 6.3)."""
    s = _schema(schema)
    return {
        AccessClass.GT: "ground_truth",
        AccessClass.OBS: "observable",
        AccessClass.META: "evidence",
    }[s[dataset_id].access_class]


def assert_fields_declared(
    columns: Iterable[str], dataset_id: str, schema: Schema | None = None
) -> None:
    s = _schema(schema)
    ds = s[dataset_id]
    undeclared = sorted(set(columns) - set(ds.field_map))
    if undeclared:
        raise LeakageError(
            f"{dataset_id} ({ds.name}): columns {undeclared} are not declared in "
            f"datasets.yaml. Add them to the schema, with a mechanism if the "
            f"dataset is OBS (design 6.5 rule 1), or remove them."
        )


def assert_no_gt_field_names(
    columns: Iterable[str], dataset_id: str, schema: Schema | None = None
) -> None:
    """Design 5.1: an OBS output may not carry a GT-class column name."""
    s = _schema(schema)
    ds = s[dataset_id]
    if ds.access_class != AccessClass.OBS:
        return
    own = set(ds.field_map)
    gt = gt_field_names(s)
    leaked = sorted(
        c for c in columns if c in gt and c not in SHARED_JOIN_KEYS and c not in own
    )
    if leaked:
        raise LeakageError(
            f"{dataset_id} ({ds.name}) is OBS but carries ground-truth columns "
            f"{leaked}. Design 5.1: the first three layers of the person state "
            f"model are never visible to models under test."
        )
    # A hidden-layer name is a leak even if it is in the dataset's own field map,
    # which would itself be a schema error; checked here as defence in depth.
    hidden = sorted(c for c in columns if c in hidden_layer_field_names(s))
    if hidden:
        raise LeakageError(
            f"{dataset_id} ({ds.name}) is OBS but carries hidden-layer columns {hidden}."
        )


def assert_no_forbidden_patterns(
    columns: Iterable[str], dataset_id: str, schema: Schema | None = None
) -> None:
    """R09 / 5.14: name-based refusal of occupancy and forbidden profile fields.

    A dataset that declares ``forbidden_field_patterns`` is marked
    transmission-restricted.  For such a dataset two refusals apply: the
    declared patterns, and every person-level field name derived from the schema
    by :func:`person_level_field_names`.
    """
    s = _schema(schema)
    ds = s[dataset_id]
    if not ds.forbidden_regexes:
        return
    bad: list[tuple[str, str]] = []
    person_level = person_level_field_names(s)
    own = set(ds.field_map)
    for c in columns:
        matched = False
        for rx in ds.forbidden_regexes:
            if rx.search(c):
                bad.append((c, rx.pattern))
                matched = True
                break
        if matched:
            continue
        if c in person_level and c not in own and c not in SHARED_JOIN_KEYS:
            bad.append((c, "person-level field (design 5.1 hidden layer or 5.14 MIMIC latent)"))
    if bad:
        detail = ", ".join(f"{c!r} matches {p!r}" for c, p in sorted(bad))
        raise LeakageError(
            f"{dataset_id} ({ds.name}): forbidden field name(s) present - {detail}. "
            f"R09 / E0-8: no occupancy, presence or person-level field is ever "
            f"transmitted; design 5.14: forbidden profile fields are never exported."
        )


def audit_frame(
    columns: Iterable[str], dataset_id: str, schema: Schema | None = None
) -> None:
    """Run all three checks.  Called by every writer in :mod:`baile_nua.io`."""
    cols = list(columns)
    # Forbidden patterns first.  An occupancy column is also an undeclared
    # column, and the R09 message is the one the operator needs to see.
    assert_no_forbidden_patterns(cols, dataset_id, schema)
    assert_fields_declared(cols, dataset_id, schema)
    assert_no_gt_field_names(cols, dataset_id, schema)


def audit_mapping(row: Mapping[str, object], dataset_id: str, schema: Schema | None = None) -> None:
    audit_frame(row.keys(), dataset_id, schema)
