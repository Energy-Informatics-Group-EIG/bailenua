"""D10, D17 and D17's observable view: the three datasets the writer gained.

Two of them had producers in the frozen engine and no consumer.  ``run_day``
materialised every activity interval and kept only ``len()``; ``lv.d17_rows``
built a D17 row per element per coupling epoch and the run accumulated them to
report their own count.  Both are now buffered and written, and BN-1 adds
D17's declared observable view.

What these tests are for, in order of how much they would hurt if they were
absent:

* **the OBS/GT split.**  BN-1 gives a DSO the connection register, the asset
  ratings and the feeder-head and substation measurements, and *nothing else*.
  Per-element voltage and per-element loading stay ground truth: voltage
  because :func:`lv.assert_voltage_is_not_a_claim` always raises - the LV
  topology is ``[A]`` (A-49) and voltage drop is a line integral along exactly
  the declared span - and loading because it is the ratio the ground-truth
  dataset exists to carry.  A field-by-field check, not a spot check, because
  a leak is a name that got through rather than a value that looked wrong.
* **the view is a projection, not a recomputation.**  Every measured power in
  the view must equal the D17 row for the same element and epoch.  A view that
  recomputed its own numbers could disagree with the truth it is a view of,
  and nothing downstream would notice.
* **the mapping to D10's ten fields.**  Written against the schema rather than
  against the engine's convenience, with ``hetus_code`` read off the same
  ACTIVITY_CODES table the duration targets are drawn from.

The writer-level tests build a small real pandapower network and drive the
real :class:`StreamWriter`, so they exercise ``write_dataset`` - and therefore
schema validation, the leakage audit and the package rule - rather than
re-implementing it.  They need no ``sources/`` on disk.
"""

from __future__ import annotations

import dataclasses
import types

import numpy as np
import pandas as pd
import pytest

from baile_nua.engine.stream_writer import (
    StreamWriter,
    d10_frame,
    hetus_code_for,
)
from baile_nua.network import lv
from baile_nua.schema import AccessClass, load
from baile_nua.schema.access import (
    SHARED_JOIN_KEYS,
    LeakageError,
    audit_frame,
    gt_field_names,
    person_level_field_names,
)

pytestmark = pytest.mark.filterwarnings("ignore::FutureWarning")

EPOCH_STALENESS_S = 15 * 60


# --------------------------------------------------------------------------- #
# a small real network, and a slice stub that carries only what the writer uses
# --------------------------------------------------------------------------- #

@dataclasses.dataclass
class _Building:
    building_id: str
    estate_id: str
    premises_id: str


@pytest.fixture(scope="module")
def net_and_slice():
    """Two estates, 30 connections: enough for several feeders per substation.

    Built with :func:`lv.build_town_network` rather than with a hand-made
    pandapower net, so the ratings the view publishes are the catalogue values
    of the standard types the real network is built from.
    """
    blds = [
        _Building(
            building_id=f"B-{i:05d}",
            estate_id=("EST-A" if i < 18 else "EST-B"),
            premises_id=f"MPRN-{i:08X}",
        )
        for i in range(30)
    ]
    tn = lv.build_town_network(buildings={b.building_id: b for b in blds})
    sl = types.SimpleNamespace(
        buildings={f"H-{i:05d}": b for i, b in enumerate(blds)}
    )
    return tn, sl


@pytest.fixture(scope="module")
def written(tmp_path_factory, net_and_slice):
    """Two days of solved network state, written through the real writer."""
    tn, sl = net_and_slice
    out = tmp_path_factory.mktemp("d17")
    w = StreamWriter(out, master_seed=1)
    gt_rows: list[dict] = []
    for sim_day in (0, 1):
        day = types.SimpleNamespace(
            sim_day=sim_day,
            date=pd.Timestamp("2022-01-01") + pd.Timedelta(days=sim_day),
        )
        rows: list[dict] = []
        for epoch in range(2):
            # A spread of loads so the elements differ from one another; two
            # exporting homes so the sign convention is exercised.
            load_w = {
                bid: (-1200.0 if i % 13 == 0 else 400.0 + 25.0 * i)
                for i, bid in enumerate(sorted(tn.load_by_building))
            }
            lv.solve_epoch(tn, net_w_by_building=load_w)
            ts = pd.Timestamp(day.date).tz_localize("UTC") + pd.Timedelta(
                minutes=15 * epoch)
            rows.extend(lv.d17_rows(
                tn, ts=ts, coupling_mode="C2",
                epoch_staleness_s=EPOCH_STALENESS_S))
        w.add_network_day(day, rows, tn, sl)
        gt_rows.extend(rows)
    w.close()
    gt = pd.concat(
        [pd.read_parquet(p) for p in sorted((out / "ground_truth").glob("D17_part*.parquet"))],
        ignore_index=True)
    obs = pd.concat(
        [pd.read_parquet(p)
         for p in sorted((out / "observable").glob("D17_aggregate_part*.parquet"))],
        ignore_index=True)
    return types.SimpleNamespace(root=out, gt=gt, obs=obs, produced=gt_rows)


# --------------------------------------------------------------------------- #
# the schema declares the view, and it is an OBS dataset in its own right
# --------------------------------------------------------------------------- #

def test_d17_declares_the_obs_view_and_the_view_exists(schema):
    assert schema["D17"].obs_view == "D17_aggregate"
    view = schema[schema["D17"].obs_view]
    assert view.access_class == AccessClass.OBS
    assert schema["D17"].access_class == AccessClass.GT, (
        "the full network state is ground truth and stays ground truth; the "
        "view is in addition to it, not instead of it"
    )


def test_every_field_of_the_view_names_its_mechanism(schema):
    """Design 6.5 rule 1, on this dataset specifically.

    The global test covers every OBS dataset; this one fails with the field
    name when the dataset under change is this one.
    """
    missing = [f.name for f in schema["D17_aggregate"].fields if not f.mechanism]
    assert not missing, missing


def test_the_view_declares_no_gt_counterpart_and_says_why(schema):
    """6.5's too-good test needs a calibrated error model to bound agreement.

    E1 renders no instrument error for network metering, so there is no such
    model and no bound to apply.  Declaring a counterpart anyway would invite
    a test to bound agreement against nothing.  The dataset's notes say so,
    and this keeps the two consistent.
    """
    view = schema["D17_aggregate"]
    assert not [f.name for f in view.fields if f.gt_counterpart]
    assert "no gt_counterpart is declared" in (view.notes or "")


# --------------------------------------------------------------------------- #
# the OBS/GT split
# --------------------------------------------------------------------------- #

@pytest.mark.leakage
def test_the_view_carries_no_gt_or_person_level_field_name(schema, written):
    cols = list(written.obs.columns)
    gt = gt_field_names(schema)
    leaked = sorted(c for c in cols if c in gt and c not in SHARED_JOIN_KEYS)
    assert not leaked, (
        f"the observable view carries ground-truth column names {leaked}. "
        f"Declaring them in the view's own field map would let the leakage "
        f"audit through on the `own` exemption, which is why this test reads "
        f"the GT names directly."
    )
    person = sorted(set(cols) & person_level_field_names(schema))
    assert not person, person
    # And the real audit, on the frame as written.
    audit_frame(cols, "D17_aggregate", schema)


@pytest.mark.leakage
def test_per_element_voltage_and_loading_stay_in_ground_truth(written):
    """The two refusals BN-1 names, checked on the bytes rather than asserted."""
    assert "voltage_pu" in written.gt.columns
    assert "loading_pct" in written.gt.columns
    assert written.gt["voltage_pu"].notna().any(), (
        "D17 must still record the voltage it computes; the refusal is about "
        "making a CLAIM from it, not about hiding it from ground truth"
    )
    for col in written.obs.columns:
        low = col.lower()
        assert "volt" not in low and "_pu" not in low, (
            f"{col} looks like a voltage in the observable view. "
            f"lv.assert_voltage_is_not_a_claim() raises unconditionally: the "
            f"topology is [A] (A-49) and a per-unit voltage is a property of "
            f"the declared feeder span as much as of the town."
        )
        assert "loading" not in low, (
            f"{col} looks like per-element loading, which is GT. The ratings "
            f"and the measurements are both published because BN-1 names "
            f"them; their ratio is not."
        )


@pytest.mark.leakage
def test_the_view_publishes_no_per_connection_power(written):
    """A register row names a premises; a measurement row never does.

    A per-MPRN power in the view would be the connection-level series under a
    different name, and an aggregate view that carries per-customer power is
    not aggregate.
    """
    measured = written.obs[written.obs["record_kind"] != "connection_register"]
    assert measured["premises_id"].isna().all()
    register = written.obs[written.obs["record_kind"] == "connection_register"]
    assert register["p_kw_measured"].isna().all()
    assert register["q_kvar_measured"].isna().all()


def test_the_view_cannot_be_written_into_the_ground_truth_package(
        tmp_path, net_and_slice, written):
    from baile_nua.io import PackageError, write_dataset

    with pytest.raises(PackageError, match="v1/observable"):
        write_dataset(written.obs.head(5), "D17_aggregate",
                      tmp_path / "v1" / "ground_truth" / "x.parquet")


@pytest.mark.leakage
def test_a_voltage_column_added_to_the_view_is_refused(schema, written):
    """The guard, exercised: the audit must reject it, not accept and drop it."""
    bad = written.obs.head(3).assign(voltage_pu=1.0)
    with pytest.raises(LeakageError):
        audit_frame(bad.columns, "D17_aggregate", schema)


# --------------------------------------------------------------------------- #
# the view is a projection of D17, not a second computation
# --------------------------------------------------------------------------- #

def test_every_measured_power_equals_the_ground_truth_row_it_views(written):
    gt = written.gt.copy()
    gt["record_kind"] = gt["element_kind"].map(
        {"transformer": "substation", "feeder": "feeder_head"})
    obs = written.obs[written.obs["record_kind"] != "connection_register"]
    assert len(obs) == len(gt), (
        f"{len(obs)} measurement rows for {len(gt)} ground-truth rows: the "
        f"view must cover every element of every epoch exactly once"
    )
    # A feeder row is keyed by its circuit and a substation row by its
    # station, which is the same identifier D17 puts in `element_id`.
    gt["element_ref"] = gt["element_id"]
    obs = obs.assign(element_ref=obs["feeder_ref"].fillna(obs["substation_ref"]))
    merged = obs.merge(gt, on=["ts", "record_kind", "element_ref"],
                       suffixes=("", "_gt"))
    assert len(merged) == len(obs)
    assert np.allclose(merged["p_kw_measured"], merged["p_kw"], rtol=0, atol=0)
    assert np.allclose(merged["q_kvar_measured"], merged["q_kvar"], rtol=0, atol=0)


def test_the_sign_convention_survives_the_projection(written):
    """D17's p_kw is positive for import at every element kind.

    The view inherits that rather than restating it, and an exporting estate
    must show as negative on both sides.  This is the error ``lv.d17_rows``
    already made once, with the LV terminal's sign.
    """
    obs = written.obs[written.obs["record_kind"] == "substation"]
    gt = written.gt[written.gt["element_kind"] == "transformer"]
    assert np.sign(obs["p_kw_measured"].to_numpy()).tolist() == \
        np.sign(gt["p_kw"].to_numpy()).tolist()


# --------------------------------------------------------------------------- #
# the connection register and the asset ratings
# --------------------------------------------------------------------------- #

def test_the_register_names_every_premises_exactly_once(written, net_and_slice):
    tn, sl = net_and_slice
    register = written.obs[written.obs["record_kind"] == "connection_register"]
    expected = {b.premises_id for b in sl.buildings.values()}
    assert set(register["premises_id"]) == expected
    assert len(register) == len(expected), (
        "a premises recorded twice would be a register that disagrees with "
        "itself about which circuit a customer is on"
    )


def test_the_register_agrees_with_the_network_it_was_built_from(
        written, net_and_slice):
    tn, sl = net_and_slice
    premises_of = {b.building_id: b.premises_id for b in sl.buildings.values()}
    want = {
        premises_of[bid]: (sub, feeder)
        for bid, (sub, feeder) in tn.assignment.items()
    }
    register = written.obs[written.obs["record_kind"] == "connection_register"]
    got = {
        r.premises_id: (r.substation_ref, r.feeder_ref)
        for r in register.itertuples()
    }
    assert got == want


def test_the_register_is_written_once_however_many_days_are_added(written):
    """It is a register, not a series.

    The LV topology is built once per run and does not change within it, so
    repeating 1,092 membership rows on every epoch would publish the same
    register 35,040 times a year.  Two days were added in the fixture.
    """
    register = written.obs[written.obs["record_kind"] == "connection_register"]
    assert register["ts"].nunique() == 1


def test_the_ratings_are_the_catalogue_values_not_numbers_written_here(
        written, net_and_slice):
    tn, _sl = net_and_slice
    net = tn.net
    subs = written.obs[written.obs["record_kind"] == "substation"]
    for sub, ti in tn.trafo_by_substation.items():
        want = float(net.trafo.at[ti, "sn_mva"]) * 1000.0
        got = subs.loc[subs["substation_ref"] == sub, "transformer_rated_kva"]
        assert got.notna().all() and np.allclose(got, want)
        assert str(net.trafo.at[ti, "std_type"]) in [n for _c, n in lv.STD_TRAFO]
    heads = written.obs[written.obs["record_kind"] == "feeder_head"]
    for feeder, li in tn.head_line_by_feeder.items():
        want = float(net.line.at[li, "max_i_ka"]) * 1000.0
        got = heads.loc[heads["feeder_ref"] == feeder, "feeder_rated_a"]
        assert got.notna().all() and np.allclose(got, want)


def test_every_feeder_row_names_the_substation_it_hangs_off(
        written, net_and_slice):
    tn, _sl = net_and_slice
    sub_of = {f: s for _b, (s, f) in tn.assignment.items()}
    heads = written.obs[written.obs["record_kind"] == "feeder_head"]
    for r in heads.itertuples():
        assert r.substation_ref == sub_of[r.feeder_ref]


def test_a_substation_row_names_no_feeder(written):
    subs = written.obs[written.obs["record_kind"] == "substation"]
    assert subs["feeder_ref"].isna().all()
    assert subs["feeder_rated_a"].isna().all()
    heads = written.obs[written.obs["record_kind"] == "feeder_head"]
    assert heads["transformer_rated_kva"].isna().all()


def test_the_view_can_be_omitted_without_omitting_the_ground_truth(
        tmp_path, net_and_slice):
    """``omit_datasets`` must not be able to drop GT by dropping its view."""
    tn, sl = net_and_slice
    w = StreamWriter(tmp_path, master_seed=1,
                     omit_datasets=frozenset({"D17_aggregate"}))
    day = types.SimpleNamespace(sim_day=0, date=pd.Timestamp("2022-01-01"))
    lv.solve_epoch(tn, net_w_by_building={
        bid: 500.0 for bid in tn.load_by_building})
    rows = lv.d17_rows(tn, ts=pd.Timestamp("2022-01-01", tz="UTC"),
                       coupling_mode="C2", epoch_staleness_s=EPOCH_STALENESS_S)
    w.add_network_day(day, rows, tn, sl)
    w.close()
    assert list((tmp_path / "ground_truth").glob("D17_part*.parquet"))
    assert not list((tmp_path / "observable").glob("D17_aggregate*.parquet"))


# --------------------------------------------------------------------------- #
# D10
# --------------------------------------------------------------------------- #

def _d10_rows() -> list[dict]:
    """One person's day: at home, out at a venue, and in transit between.

    The in-transit interval is the case that matters: it is on the road
    network and has no place to name, which is why D10's ``location_id`` is
    nullable and why it is written null rather than given the dwelling.
    """
    return [
        {"person_id": "P-000001", "start_min": 0, "end_min": 480,
         "activity": "sleep", "zone": "bedroom", "joint_with": [],
         "trigger": "routine", "deliberated": False, "location_id": "B-00001"},
        {"person_id": "P-000001", "start_min": 480, "end_min": 510,
         "activity": "travel_commute", "zone": "in_transit", "joint_with": [],
         "trigger": "routine", "deliberated": False, "location_id": None},
        {"person_id": "P-000001", "start_min": 510, "end_min": 1000,
         "activity": "work_at_workplace", "zone": "outside",
         "joint_with": ["P-000002"], "trigger": "routine",
         "deliberated": True, "location_id": "V-WORKPLACE-001"},
        {"person_id": "P-000001", "start_min": 1000, "end_min": 1440,
         "activity": "laundry", "zone": "utility", "joint_with": [],
         "trigger": "lapse", "deliberated": True, "location_id": "B-00001"},
    ]


@pytest.fixture(scope="module")
def d10(tmp_path_factory):
    from baile_nua.io import write_dataset

    idx = pd.date_range("2022-03-04", periods=1440, freq="1min", tz="UTC")
    frame = d10_frame(_d10_rows(), sim_day=62, minute_index=idx)
    # Written through the real path, so the schema validator, the type
    # coercion and the leakage audit all run on it.
    path = tmp_path_factory.mktemp("d10") / "ground_truth" / "D10_part000.parquet"
    write_dataset(frame, "D10", path)
    return pd.read_parquet(path)


def test_d10_carries_exactly_the_schema_fields_in_schema_order(schema, d10):
    assert list(d10.columns) == [f.name for f in schema["D10"].fields]


def test_d10_activity_ids_are_unique_and_carry_the_day(d10):
    assert d10["activity_id"].is_unique
    assert set(d10["activity_id"].str[:9]) == {"AC-00062-"}


def test_d10_intervals_are_ordered_and_cover_the_day(d10):
    assert (d10["end"] >= d10["start"]).all()
    assert d10["start"].min() == pd.Timestamp("2022-03-04", tz="UTC")
    # The last interval ends at midnight, which the day's own minute index
    # cannot express; D11 and D13 stamp 23:59 for the same reason.
    assert d10["end"].max() == pd.Timestamp("2022-03-04 23:59", tz="UTC")


def test_d10_location_id_is_null_only_where_there_is_no_place(d10):
    null = d10[d10["location_id"].isna()]
    assert set(null["zone"]) <= {"in_transit", "out_of_model"}, (
        "a null location_id outside in_transit/out_of_model means a place was "
        "lost, not absent"
    )
    assert len(null) == 1


def test_d10_hetus_code_is_the_declared_acl00_mapping():
    """``hetus_code`` is read off the table the duration targets come from.

    Not a second mapping maintained beside it: six codes in the first version
    of ACTIVITY_CODES were wrong (I-029) and were only caught by reading the
    labels from a file, so a parallel table would be a second place for the
    same mistake.
    """
    from baile_nua.activity.hetus import ACTIVITY_CODES

    for activity, spec in ACTIVITY_CODES.items():
        want = "+".join(code for code, _w in spec["hetus"])
        assert hetus_code_for(activity) == want
    assert hetus_code_for("laundry") == "AC331+AC332"
    assert hetus_code_for("sleep") == "AC01"


def test_hetus_code_refuses_an_activity_the_engine_does_not_target():
    with pytest.raises(KeyError, match="ACTIVITY_CODES"):
        hetus_code_for("teleportation")


def test_every_d10_hetus_code_decomposes_into_registered_acl00_codes(d10):
    """Each component must be a code in the registered ACL00 codelist.

    Skipped rather than failed when the codelist file is not on disk: a
    checkout without ``sources/`` is a legitimate state.
    """
    from baile_nua.sources import SourceError

    try:
        from baile_nua.activity.hetus import acl00_labels

        labels = acl00_labels()
    except (SourceError, FileNotFoundError, KeyError) as exc:
        pytest.skip(f"ACL00 codelist unavailable: {exc}")
    for code in sorted({c for v in d10["hetus_code"] for c in v.split("+")}):
        assert code in labels, f"{code} is not in the registered ACL00 codelist"


def test_d10_is_ground_truth_and_cannot_be_written_into_the_observable_view(
        tmp_path, d10):
    from baile_nua.io import PackageError, write_dataset

    with pytest.raises(PackageError, match="v1/ground_truth"):
        write_dataset(d10, "D10", tmp_path / "v1" / "observable" / "x.parquet")


# --------------------------------------------------------------------------- #
# the engine actually carries them: D10's location_id must agree with D11's
# --------------------------------------------------------------------------- #

@pytest.mark.slow
def test_the_engine_resolves_one_location_for_both_d10_and_d11(tmp_path):
    """D10 and D11 are two views of one set of intervals.

    They are resolved by the same expression on the same objects, so for a
    person-minute where both record a place, the place must be the same.  If
    they ever disagree, one of the two is describing a day the model did not
    simulate.  Requires ``sources/``; slow, so it is out of the fast loop.
    """
    pytest.importorskip("pandapower")
    from baile_nua.sources import SourceError

    try:
        import baile_nua.sources_registry  # noqa: F401
        from baile_nua.engine.e1_run import run_year
    except (SourceError, FileNotFoundError) as exc:      # pragma: no cover
        pytest.skip(f"sources unavailable: {exc}")

    try:
        run_year(
            master_seed=20251010, out_root=tmp_path / "pkg",
            checkpoint_root=tmp_path / "ckpt", days=1,
            slice_kind="e1_estate", write_package=True,
            omit_datasets=frozenset({"D18"}),
            solve_network=False, with_venues=True,
        )
    except SourceError as exc:                           # pragma: no cover
        pytest.skip(f"sources unavailable: {exc}")

    gt = tmp_path / "pkg" / "ground_truth"
    a = pd.read_parquet(sorted(gt.glob("D10_part*.parquet"))[0])
    p = pd.read_parquet(sorted(gt.glob("D11_part*.parquet"))[0])
    assert len(a) == len(p), (
        "D10 and D11 are the same intervals; a different row count means one "
        "of them dropped some"
    )
    join = ["person_id", "start", "end"]
    m = a[join + ["location_id"]].merge(
        p[join + ["location_id"]], on=join, suffixes=("_d10", "_d11"))
    assert len(m) == len(a)
    both = m[m["location_id_d10"].notna() & m["location_id_d11"].notna()]
    assert (both["location_id_d10"] == both["location_id_d11"]).all()
