"""Do week 2's new dataset rows actually conform to `datasets.yaml`?

Three datasets gained a producer this week — D14 calendar events, D03 building
passport events and D17 network state — and none of them is written to a
package, because all three are ground truth and D20's sibling rule applies:
the per-year packages carry D11/D13/D16/D19 exactly as E1's does.

That is precisely why this test exists. A producer whose rows are never
written is never validated against the schema, so a mismatch sits latent until
something writes it. Both mismatches found here were of that kind:

* **D03** requires ``effective_at`` and ``decided_at``, timestamps. The engine
  works in sim-day integers, which is right for the engine and wrong for the
  dataset.
* **D17** requires ``ts`` and names exactly ten fields. The run's per-epoch
  record carries ``epoch_index``, ``minute``, ``envelope_tightening`` and
  ``n_violations`` instead — useful diagnostics, and not D17 columns.

Neither would have surfaced until week 3 writes D17 and D03 for the network
work. The fix keeps the diagnostic record and the schema row apart rather than
widening the schema, because adding the implementation's internals to a GT
dataset is how a schema stops being a contract.

D14 conformed exactly from the start, which is the control: the test can tell
a conforming producer from a non-conforming one.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest
import yaml

import baile_nua.sources_registry  # noqa: F401
from baile_nua.engine import calendar_events as EV
from baile_nua.engine import coupling as C
from baile_nua.lifecourse.tenyear import PassportEvent
from baile_nua.plausibility import slp

SCHEMA_PATH = "baile_nua/schema/datasets.yaml"


@pytest.fixture(scope="module")
def datasets():
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        return yaml.safe_load(fh)["datasets"]


def _fields(ds: dict, key: str) -> tuple[set[str], set[str]]:
    all_names = {f["name"] for f in ds[key]["fields"]}
    required = {f["name"] for f in ds[key]["fields"] if f.get("required")}
    return all_names, required


def _assert_conforms(ds: dict, key: str, row: dict) -> None:
    all_names, required = _fields(ds, key)
    missing = sorted(required - set(row))
    extra = sorted(set(row) - all_names)
    assert not missing, f"{key}: required fields absent from the row: {missing}"
    assert not extra, (
        f"{key}: the row carries fields the schema does not name: {extra}. "
        f"Widening the schema to accept them would put the implementation's "
        f"internals into a ground-truth contract."
    )


# --------------------------------------------------------------------------- #

def test_d14_event_rows_conform(datasets):
    """The control: a producer that conformed from the start."""
    ev = EV.build_events(
        year=2022, master_seed=1,
        storm_days=[__import__("pandas").Timestamp("2022-02-18")],
    )
    assert ev
    for e in ev[:50]:
        _assert_conforms(datasets, "D14", e.as_row())


def test_d14_enums_match_the_schema(datasets):
    """The enum values, not just the field names."""
    enums = yaml.safe_load(open(SCHEMA_PATH, encoding="utf-8"))["enums"]
    assert set(EV.EVENT_CLASSES) == set(enums["event_class"])
    assert set(EV.EVENT_PHASES) == set(enums["event_phase"])
    assert set(EV.EVENT_FOOTPRINTS) == set(enums["event_footprint"])


def test_d03_passport_rows_conform(datasets):
    """D03 requires timestamps; the engine works in sim-days."""
    pe = PassportEvent(
        passport_event_id="BP-TEST", building_id="B-001",
        # I-062. `measure` is required rather than defaulted, so no passport
        # event can be constructed that the engine cannot dispatch on: D03's
        # `event_type` is too coarse, since all four asset measures are
        # "asset added". It is NOT in `as_d03_row`, so the dataset schema is
        # unchanged - asserted below.
        event_type="retrofit", measure="retrofit_fabric",
        effective_day=100, decided_day=10,
        from_version=1, to_version=2,
        parameters_changed={"rc_r_ie": "changed"},
        driver="WP5 ten-year life course", life_event_id="LE-1",
    )
    _assert_conforms(datasets, "D03", pe.as_d03_row())
    row = pe.as_d03_row(start_date="2022-01-01")
    assert str(row["effective_at"].date()) == "2022-04-11", row["effective_at"]
    assert str(row["decided_at"].date()) == "2022-01-11", row["decided_at"]
    # And the internal record is still sim-days, because that is what the
    # engine and the invariants use.
    assert pe.as_row()["effective_day"] == 100


def test_a_passport_event_with_no_decision_date_still_conforms(datasets):
    pe = PassportEvent(
        passport_event_id="BP-2", building_id="B-002", event_type="extension",
        measure="extension", effective_day=5, decided_day=None, from_version=3, to_version=4,
        parameters_changed={"floor_area_m2": "changed"}, driver="WP5",
        life_event_id=None,
    )
    row = pe.as_d03_row()
    _assert_conforms(datasets, "D03", row)
    assert row["decided_at"] is None


@pytest.fixture(scope="module")
def coupled_day():
    shape = slp.lp1_reference()["mean_diurnal_over_day_mean"]
    mins = sorted(shape)
    prof = np.interp(np.arange(1440), mins, [shape[m] for m in mins])
    baseline = {f"P-{i:03d}": prof / prof.mean() * 160.0 for i in range(4)}
    return C.run_coupled_day(
        mode="C1", baseline_w=baseline, connection_limit_w=12_000.0,
        feeder_limit_kw=1e9, limits={}, agent=None,
    )


def test_d17_schema_rows_conform(datasets, coupled_day):
    rows = C.d17_schema_rows(coupled_day)
    assert len(rows) == 96
    for r in rows[:20]:
        _assert_conforms(datasets, "D17", r)


def test_the_diagnostic_record_is_deliberately_not_a_d17_row(datasets, coupled_day):
    """The two are kept apart on purpose, and the test says which is which."""
    all_names, _ = _fields(datasets, "D17")
    diag = coupled_day["d17_rows"][0]
    extra = set(diag) - all_names
    assert extra == {
        "epoch_index", "minute", "envelope_tightening", "n_violations"
    }, extra
    # Those four are what a reader of the timing contract needs, so they are
    # not dropped - they just do not go into the dataset.
    assert diag["envelope_tightening"] > 0.0
    assert diag["epoch_staleness_s"] == 900


def test_every_d17_row_carries_its_coupling_mode_and_staleness(datasets, coupled_day):
    """Both are schema fields and both are the 8.2 contract's own record."""
    for r in C.d17_schema_rows(coupled_day):
        assert r["coupling_mode"] in ("C1", "C2", "C3")
        assert r["epoch_staleness_s"] == 900
        assert r["outage"] is False


def test_the_conformance_helper_actually_fails_on_a_bad_row(datasets):
    """Otherwise the tests above prove nothing."""
    with pytest.raises(AssertionError, match="required fields absent"):
        _assert_conforms(datasets, "D17", {"element_id": "F-1"})
    with pytest.raises(AssertionError, match="does not name"):
        _assert_conforms(datasets, "D14", {
            **EV.build_events(
                year=2022, master_seed=1, storm_days=[],
            )[0].as_row(),
            "epoch_index": 3,
        })
