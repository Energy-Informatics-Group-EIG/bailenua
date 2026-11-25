"""Negative controls for Day 1 (design 9.3 row 1).

    Negative control that must fail:
      * Order-dependent RNG mutation
      * GT column in an OBS file

Each control declares its intended test and an expected failure assertion, and
passes only if that test fails for that reason (design 9.3 negative-control
rule).
"""

from __future__ import annotations

import random
from typing import Any

import numpy as np
import pandas as pd

from baile_nua.rng import SeedTree, Stream
from baile_nua.schema.access import LeakageError, audit_frame
from baile_nua.schema.validate import ValidationError, validate_frame
from baile_nua.validation.negative_control import NegativeControl, register

# --------------------------------------------------------------------------- #
# NC-D1-01  Order-dependent RNG
# --------------------------------------------------------------------------- #


class _OrderDependentSeedTree:
    """A deliberately broken seed tree: one shared, stateful generator.

    This is the mutation design 9.3 asks for.  It is what a plausible
    implementation looks like if the author reaches for ``np.random.default_rng``
    once and reuses it, and it produces entity values that depend on the order
    the entities were visited in.
    """

    def __init__(self, master_seed: int) -> None:
        self._shared = np.random.default_rng(master_seed)  # the defect

    def generator(self, stream, entity="", sim_day=0, draw=0):  # noqa: ANN001
        return self._shared


def _order_dependence_check(tree: Any) -> None:
    """The intended test: draws must not depend on visit order (design 8.2).

    This mirrors ``tests/test_determinism.py::test_draws_are_order_independent``.
    """
    people = [f"P-{i:06d}" for i in range(1, 25)]

    def draw_all(order):
        t = tree() if callable(tree) else tree
        return {p: t.generator(Stream.PERSON_TRAITS, p, 7).normal(size=4) for p in order}

    forward = draw_all(people)
    shuffled = people[:]
    random.Random(99).shuffle(shuffled)
    backward = draw_all(shuffled)

    mismatched = [p for p in people if not np.array_equal(forward[p], backward[p])]
    if mismatched:
        raise AssertionError(
            f"RNG draws depend on execution order: {len(mismatched)} of {len(people)} "
            f"entities changed value when visited in a different order "
            f"(first: {mismatched[0]}). Design 8.2 requires a counter-based RNG whose "
            f"results do not depend on execution order or worker count."
        )


register(
    NegativeControl(
        control_id="NC-D1-01",
        title="Order-dependent RNG mutation",
        design_ref="9.3 day 1; 8.2 reproducibility contract",
        intended_test="tests.test_determinism.test_draws_are_order_independent",
        expected_exception=AssertionError,
        expected_message="depend on execution order",
        # A fresh broken tree per call, so the defect shows as order dependence
        # rather than simple stream exhaustion.
        build=lambda: (lambda: _OrderDependentSeedTree(20261008)),
        invoke=_order_dependence_check,
        must_still_pass=(
            # The correct implementation must pass the same check, otherwise the
            # check itself is broken rather than the control.
            ("same check on the real SeedTree", lambda _: _order_dependence_check(
                lambda: SeedTree(20261008)
            )),
        ),
    )
)


# --------------------------------------------------------------------------- #
# NC-D1-02  GT column in an OBS file
# --------------------------------------------------------------------------- #

_CLEAN_EDGE_EXPORT = {
    "premises_id": "MPRN-0123456789ABCDEF01",
    "interval_start": "2022-01-01T00:00:00Z",
    "interval_end": "2022-01-01T00:30:00Z",
    "import_wh": 250.0,
    "export_wh": 0.0,
    "interval_peak_w": 1200.0,
    "interval_min_w": 40.0,
    "export_config": "home_30min",
    "quality": "ok",
}


def _broken_obs_with_gt_column() -> pd.DataFrame:
    """An edge export carrying an occupancy count — exactly what R09 forbids."""
    return pd.DataFrame([{**_CLEAN_EDGE_EXPORT, "occupancy_count": 3}])


register(
    NegativeControl(
        control_id="NC-D1-02",
        title="GT column in an OBS file (occupancy count in an edge export)",
        design_ref="9.3 day 1; 5.1 leakage test; R09 / E0-8",
        intended_test="baile_nua.schema.access.audit_frame (tests.test_leakage)",
        expected_exception=LeakageError,
        expected_message="R09",
        build=_broken_obs_with_gt_column,
        invoke=lambda frame: audit_frame(frame.columns, "D19"),
        must_still_pass=(
            (
                "the same audit on a clean edge export",
                lambda _: audit_frame(pd.DataFrame([_CLEAN_EDGE_EXPORT]).columns, "D19"),
            ),
        ),
    )
)


# --------------------------------------------------------------------------- #
# NC-D1-03  A hidden-layer trait reaching an observable export
# --------------------------------------------------------------------------- #

register(
    NegativeControl(
        control_id="NC-D1-03",
        title="MIMIC latent trait column in an observable export",
        design_ref="5.1 four-layer model; 7.7 leakage test; R06",
        intended_test="baile_nua.schema.access.assert_no_forbidden_patterns",
        expected_exception=LeakageError,
        expected_message="person-level field",
        build=lambda: pd.DataFrame([{**_CLEAN_EDGE_EXPORT, "privacy": -0.4}]),
        invoke=lambda frame: audit_frame(frame.columns, "D19"),
        must_still_pass=(
            (
                "the same audit on a clean edge export",
                lambda _: audit_frame(pd.DataFrame([_CLEAN_EDGE_EXPORT]).columns, "D19"),
            ),
        ),
    )
)


# --------------------------------------------------------------------------- #
# NC-D1-04  An OBS schema field with no real-world mechanism
# --------------------------------------------------------------------------- #

_BROKEN_SCHEMA = """
schema_version: "0.0.1"
design_revision: 3
design_frozen: "2026-10-08"
label: "negative control"
enums: {}
datasets:
  D99:
    name: nc_obs_no_mechanism
    title: An observable dataset with a field nothing could have measured
    access_class: OBS
    grain: premises
    storage: parquet
    fields:
      - {name: premises_id, type: string, required: true,
         mechanism: "the meter point on the supply contract"}
      - {name: true_flexibility_potential_w, type: float, required: true}
"""


def _write_broken_schema() -> Any:
    import tempfile
    from pathlib import Path

    d = Path(tempfile.mkdtemp(prefix="bn-nc-"))
    p = d / "nc_no_mechanism.yaml"
    p.write_text(_BROKEN_SCHEMA, encoding="utf-8")
    return p


def _load_broken_schema(path: Any) -> None:
    from baile_nua.schema import load

    load(path)


register(
    NegativeControl(
        control_id="NC-D1-04",
        title="OBS field with no declared real-world mechanism",
        design_ref="6.5 rule 1 (strictly observational)",
        intended_test="baile_nua.schema.model.load (tests.test_schema)",
        expected_exception=Exception,  # SchemaError, imported lazily below
        expected_message="must name the real-world mechanism",
        build=_write_broken_schema,
        invoke=_load_broken_schema,
        must_still_pass=(
            ("loading the real schema", lambda _: __import__(
                "baile_nua.schema", fromlist=["load"]
            ).load()),
        ),
    )
)


# --------------------------------------------------------------------------- #
# NC-D1-05  Marginals shifted 10% (design 9.3 day 2 names this; the harness
#           piece is registered here because it is a schema/validator control)
# --------------------------------------------------------------------------- #

register(
    NegativeControl(
        control_id="NC-D1-05",
        title="Enum violation in a ground-truth dataset",
        design_ref="7.2 referential integrity; 8.5 schema-generated validators",
        intended_test="baile_nua.schema.validate.validate_frame",
        expected_exception=ValidationError,
        expected_message="not in enum",
        build=lambda: pd.DataFrame([{
            "presence_id": "PR-1", "person_id": "P-000001",
            "start": "2022-01-01T00:00:00Z", "end": "2022-01-01T07:00:00Z",
            "location_kind": "building", "location_id": "B-0001",
            "zone": "spaceship",
        }]),
        invoke=lambda frame: validate_frame(frame, "D11"),
        must_still_pass=(
            ("the same validator on a legal zone", lambda frame: validate_frame(
                frame.assign(zone="bedroom"), "D11"
            )),
        ),
    )
)
