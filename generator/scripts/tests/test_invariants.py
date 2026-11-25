"""V0 invariants suite (design 7.2, zero tolerance).

Each invariant is tested twice: on data that satisfies it, and on data that
violates it in exactly one way.  Design 7: "a check which has never failed has
not been tested."
"""

from __future__ import annotations

import pandas as pd
import pytest

from baile_nua.validation.invariants import (
    InvariantViolation,
    assert_all,
    check_energy_closure,
    check_no_child_alone,
    check_no_double_occupancy,
    check_physics_bounds,
    check_presence_within_lifespan,
    check_referential_integrity,
    check_venue_capacity,
)

pytestmark = pytest.mark.invariants

T = "2022-01-03T{}:00:00Z".format


def _presence(rows):
    return pd.DataFrame(
        rows,
        columns=["presence_id", "person_id", "start", "end", "location_kind", "location_id", "zone"],
    )


# --------------------------------------------------------------------------- #
# Nobody is in two places at once (R23)
# --------------------------------------------------------------------------- #

def test_clean_presence_has_no_double_occupancy():
    p = _presence([
        ("1", "P-000001", T("00"), T("08"), "building", "B-0001", "bedroom"),
        ("2", "P-000001", T("08"), T("09"), "in_transit", None, "in_transit"),
        ("3", "P-000001", T("09"), T("17"), "venue", "V-0001", "outside"),
        ("4", "P-000002", T("00"), T("09"), "building", "B-0001", "bedroom"),
    ])
    rep = check_no_double_occupancy(p)
    assert rep.status == "PASS", rep.violations


def test_overlapping_presence_is_a_violation():
    p = _presence([
        ("1", "P-000001", T("09"), T("17"), "building", "B-0001", "living"),
        ("2", "P-000001", T("12"), T("13"), "venue", "V-0001", "outside"),
    ])
    rep = check_no_double_occupancy(p)
    assert rep.status == "FAIL"
    assert rep.violations[0]["kind"] == "overlapping_presence"
    assert rep.violations[0]["overlap_seconds"] == 5 * 3600


def test_touching_intervals_are_legal():
    """Half-open [start, end): leaving at 09:00 and arriving at 09:00 is fine."""
    p = _presence([
        ("1", "P-000001", T("00"), T("09"), "building", "B-0001", "bedroom"),
        ("2", "P-000001", T("09"), T("17"), "venue", "V-0001", "outside"),
    ])
    assert check_no_double_occupancy(p).status == "PASS"


def test_inverted_interval_is_caught():
    p = _presence([("1", "P-000001", T("17"), T("09"), "building", "B-0001", "living")])
    rep = check_no_double_occupancy(p)
    assert rep.status == "FAIL"
    assert rep.violations[0]["kind"] == "end_before_start"


# --------------------------------------------------------------------------- #
# Lifespan
# --------------------------------------------------------------------------- #

_PERSONS = pd.DataFrame([
    {"person_id": "P-000001", "birth_date": "1980-05-01", "death_date": None},
    {"person_id": "P-000002", "birth_date": "2015-02-01", "death_date": None},
    {"person_id": "P-000003", "birth_date": "1935-01-01", "death_date": "2022-01-02"},
])


def test_presence_within_lifespan_passes():
    p = _presence([("1", "P-000001", T("00"), T("08"), "building", "B-0001", "bedroom")])
    assert check_presence_within_lifespan(p, _PERSONS).status == "PASS"


def test_presence_before_birth_is_a_violation():
    p = _presence([("1", "P-000002", "2010-01-01T00:00:00Z", "2010-01-01T08:00:00Z",
                    "building", "B-0001", "bedroom")])
    rep = check_presence_within_lifespan(p, _PERSONS)
    assert rep.status == "FAIL"
    assert rep.violations[0]["kind"] == "present_before_birth"


def test_presence_after_death_is_a_violation():
    p = _presence([("1", "P-000003", T("00"), T("08"), "building", "B-0001", "bedroom")])
    rep = check_presence_within_lifespan(p, _PERSONS)
    assert rep.status == "FAIL"
    assert rep.violations[0]["kind"] == "present_after_death"


def test_presence_for_an_unknown_person_is_a_violation():
    p = _presence([("1", "P-999999", T("00"), T("08"), "building", "B-0001", "bedroom")])
    rep = check_presence_within_lifespan(p, _PERSONS)
    assert rep.status == "FAIL"
    assert rep.violations[0]["kind"] == "presence_for_unknown_person"


# --------------------------------------------------------------------------- #
# Children under 12 are never alone at home (5.3)
# --------------------------------------------------------------------------- #

def test_supervised_child_passes():
    p = _presence([
        ("1", "P-000002", T("00"), T("20"), "building", "B-0001", "living"),   # child
        ("2", "P-000001", T("00"), T("20"), "building", "B-0001", "living"),   # adult
    ])
    rep = check_no_child_alone(p, _PERSONS, as_of=pd.Timestamp("2022-01-03", tz="UTC"))
    assert rep.status == "PASS", rep.violations


def test_child_alone_is_a_violation():
    p = _presence([
        ("1", "P-000002", T("00"), T("20"), "building", "B-0001", "living"),
        ("2", "P-000001", T("00"), T("09"), "building", "B-0001", "living"),
    ])
    rep = check_no_child_alone(p, _PERSONS, as_of=pd.Timestamp("2022-01-03", tz="UTC"))
    assert rep.status == "FAIL"
    v = rep.violations[0]
    assert v["kind"] == "child_under_12_alone"
    assert v["children"] == ["P-000002"]


def test_supervision_gap_mid_interval_is_caught():
    """The adult leaves at noon and returns at 13:00; that hour is a violation.

    This is why the check sweeps event boundaries rather than comparing whole
    intervals: a naive overlap test would see an adult present "during" the
    child's interval and pass.
    """
    p = _presence([
        ("1", "P-000002", T("08"), T("20"), "building", "B-0001", "living"),
        ("2", "P-000001", T("08"), T("12"), "building", "B-0001", "living"),
        ("3", "P-000001", T("13"), T("20"), "building", "B-0001", "living"),
    ])
    rep = check_no_child_alone(p, _PERSONS, as_of=pd.Timestamp("2022-01-03", tz="UTC"))
    assert rep.status == "FAIL"
    assert rep.violations[0]["from"].startswith("2022-01-03 12:00")


def test_a_child_in_a_different_building_does_not_supervise():
    p = _presence([
        ("1", "P-000002", T("08"), T("20"), "building", "B-0001", "living"),
        ("2", "P-000001", T("08"), T("20"), "building", "B-0002", "living"),
    ])
    rep = check_no_child_alone(p, _PERSONS, as_of=pd.Timestamp("2022-01-03", tz="UTC"))
    assert rep.status == "FAIL"


# --------------------------------------------------------------------------- #
# Venue capacity (5.4)
# --------------------------------------------------------------------------- #

def test_venue_within_capacity_passes():
    p = _presence([
        ("1", "P-000001", T("09"), T("17"), "venue", "V-0001", "outside"),
        ("2", "P-000002", T("09"), T("17"), "venue", "V-0001", "outside"),
    ])
    assert check_venue_capacity(p, {"V-0001": 10}).status == "PASS"


def test_venue_over_capacity_is_a_violation():
    p = _presence([
        (str(i), f"P-{i:06d}", T("09"), T("17"), "venue", "V-0001", "outside")
        for i in range(1, 6)
    ])
    rep = check_venue_capacity(p, {"V-0001": 3})
    assert rep.status == "FAIL"
    assert rep.violations[0]["occupants"] == 5
    assert rep.violations[0]["capacity"] == 3


def test_venue_without_declared_capacity_is_a_violation():
    """Design 5.4: "every venue has a capacity". An undeclared one is a defect."""
    p = _presence([("1", "P-000001", T("09"), T("17"), "venue", "V-0099", "outside")])
    rep = check_venue_capacity(p, {"V-0001": 10})
    assert rep.status == "FAIL"
    assert rep.violations[0]["kind"] == "venue_without_declared_capacity"


# --------------------------------------------------------------------------- #
# Energy closure (7.2)
# --------------------------------------------------------------------------- #

def _daily(**over):
    row = {
        "building_id": "B-0001", "date": "2022-01-03",
        "appliance_wh": 8000.0, "hvac_wh": 12000.0, "ev_wh": 9000.0,
        "bess_charge_wh": 2000.0, "pv_wh": 3000.0, "bess_discharge_wh": 1800.0,
    }
    row["net_meter_wh"] = (
        row["appliance_wh"] + row["hvac_wh"] + row["ev_wh"] + row["bess_charge_wh"]
        - row["pv_wh"] - row["bess_discharge_wh"]
    )
    row.update(over)
    return pd.DataFrame([row])


def test_energy_closes_exactly():
    assert check_energy_closure(_daily()).status == "PASS"


def test_energy_closure_tolerates_a_rounding_error():
    """0.1% of ~36 kWh gross is ~36 Wh; a 5 Wh residual must pass."""
    d = _daily()
    d.loc[0, "net_meter_wh"] += 5.0
    assert check_energy_closure(d).status == "PASS"


def test_energy_leak_is_a_violation():
    d = _daily()
    d.loc[0, "net_meter_wh"] += 500.0
    rep = check_energy_closure(d)
    assert rep.status == "FAIL"
    assert rep.violations[0]["kind"] == "energy_does_not_close"
    assert rep.violations[0]["residual_wh"] == pytest.approx(500.0)


# --------------------------------------------------------------------------- #
# Physics bounds (7.2)
# --------------------------------------------------------------------------- #

def test_physics_bounds_pass():
    s = pd.DataFrame([{
        "building_id": "B-0001", "ts": T("12"), "temp_living_c": 20.5,
        "temp_sleep_c": 18.0, "rh_living_pct": 55.0, "co2_living_ppm": 700.0,
        "co2_outdoor_ppm": 420.0, "bess_soc": 0.62,
    }])
    assert check_physics_bounds(s).status == "PASS"


@pytest.mark.parametrize(
    "col,value,kind",
    [
        ("temp_living_c", 95.0, "temperature_out_of_reachable_range"),
        ("rh_living_pct", 140.0, "rh_out_of_bounds"),
        ("co2_living_ppm", 50.0, "co2_out_of_bounds"),
        ("bess_soc", 1.4, "soc_out_of_bounds"),
    ],
)
def test_each_physics_bound_is_enforced(col, value, kind):
    s = pd.DataFrame([{
        "building_id": "B-0001", "ts": T("12"), "temp_living_c": 20.0,
        "rh_living_pct": 50.0, "co2_living_ppm": 700.0, "co2_outdoor_ppm": 420.0,
        "bess_soc": 0.5,
    }])
    s.loc[0, col] = value
    rep = check_physics_bounds(s)
    assert rep.status == "FAIL"
    assert any(v["kind"] == kind for v in rep.violations), rep.violations


def test_indoor_co2_below_outdoor_is_a_violation():
    """Design 7.2: "CO2 >= outdoor". Ventilation cannot scrub a room."""
    s = pd.DataFrame([{
        "building_id": "B-0001", "ts": T("12"), "co2_living_ppm": 400.0,
        "co2_outdoor_ppm": 450.0,
    }])
    rep = check_physics_bounds(s)
    assert rep.status == "FAIL"
    assert rep.violations[0]["kind"] == "indoor_co2_below_outdoor"


# --------------------------------------------------------------------------- #
# Referential integrity (7.2)
# --------------------------------------------------------------------------- #

def test_referential_integrity_passes():
    frames = {
        "D05": pd.DataFrame([{"person_id": "P-000001"}]),
        "D11": pd.DataFrame([{"person_id": "P-000001"}]),
    }
    rep = check_referential_integrity(frames, [("D11", "person_id", "D05", "person_id")])
    assert rep.status == "PASS"


def test_dangling_foreign_key_is_a_violation():
    frames = {
        "D05": pd.DataFrame([{"person_id": "P-000001"}]),
        "D11": pd.DataFrame([{"person_id": "P-000002"}]),
    }
    rep = check_referential_integrity(frames, [("D11", "person_id", "D05", "person_id")])
    assert rep.status == "FAIL"
    assert rep.violations[0]["kind"] == "dangling_foreign_key"


def test_null_foreign_key_is_not_dangling():
    """An optional reference left null is not a broken one."""
    frames = {
        "D05": pd.DataFrame([{"person_id": "P-000001"}]),
        "D11": pd.DataFrame([{"person_id": None}, {"person_id": "P-000001"}]),
    }
    rep = check_referential_integrity(frames, [("D11", "person_id", "D05", "person_id")])
    assert rep.status == "PASS"


# --------------------------------------------------------------------------- #
# assert_all
# --------------------------------------------------------------------------- #

def test_assert_all_reports_every_failure_not_just_the_first():
    p_bad = _presence([
        ("1", "P-000001", T("09"), T("17"), "building", "B-0001", "living"),
        ("2", "P-000001", T("12"), T("13"), "venue", "V-0001", "outside"),
    ])
    reports = [
        check_no_double_occupancy(p_bad),
        check_venue_capacity(p_bad, {}),
    ]
    with pytest.raises(InvariantViolation) as exc:
        assert_all(reports)
    msg = str(exc.value)
    assert "2 V0 invariant(s) violated" in msg
    assert "no_double_occupancy" in msg
    assert "venue_capacity" in msg


def test_assert_all_passes_on_clean_reports():
    p = _presence([("1", "P-000001", T("00"), T("08"), "building", "B-0001", "bedroom")])
    assert_all([check_no_double_occupancy(p)])
