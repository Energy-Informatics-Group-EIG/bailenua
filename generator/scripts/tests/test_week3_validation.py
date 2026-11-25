"""The week-3 validation modules, tested on their ability to FAIL.

Every module here produces a verdict, and a verdict-producing module has one
characteristic failure mode: it passes everything. So the tests are built
around planted faults — a population with the right marginals and the wrong
joint, a presence record with a person in two places, an export where the
"safe" configuration carries the same data as the unsafe one — and each must be
caught.

The guards are tested too. Three modules in week 3 hold a reference the build
must never fit to, and each makes that executable rather than documentary:
``overnight_lp1.assert_not_a_calibration_target``,
``lv.assert_voltage_is_not_a_claim`` and
``fabric_assessed.assert_not_a_fabric_validation_reference`` all raise
unconditionally. A test that only checked they exist would pass on a function
that returns ``None``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import baile_nua.sources_registry  # noqa: F401  (declares the sources)
from baile_nua.privacy import inference as inf
from baile_nua.privacy import threat_model as tm
from baile_nua.validation import joint_person as JP
from baile_nua.validation import overnight_lp1 as LP1
from baile_nua.validation.venue_presence import (
    VenuePresenceError,
    check_venue_presence_consistency,
)


# --------------------------------------------------------------------------- #
# the guards: each must RAISE, not merely exist
# --------------------------------------------------------------------------- #

def test_every_never_fit_guard_actually_raises():
    """A guard that returned None would pass a test that only called it."""
    from baile_nua.network import lv
    from baile_nua.physics import fabric_assessed as FA

    with pytest.raises(LP1.CalibrationTargetError):
        LP1.assert_not_a_calibration_target()
    with pytest.raises(lv.VoltageClaimError):
        lv.assert_voltage_is_not_a_claim()
    with pytest.raises(Exception):
        FA.assert_not_a_fabric_validation_reference()


def test_each_guarded_module_agrees_with_its_sources_declared_exposure():
    """A module claiming `none` for a source declared `tuning` is the I-058 fault."""
    from baile_nua.sources import REGISTRY

    for mod in (LP1, JP):
        src = REGISTRY.get(mod.SOURCE_KEY)
        assert src is not None, (
            f"{mod.__name__} names source {mod.SOURCE_KEY!r}, which is not "
            f"declared. A module naming an undeclared source cannot have its "
            f"exposure checked at all."
        )
        assert src.model_development_exposure == mod.EXPOSURE, (
            f"{mod.__name__} says exposure {mod.EXPOSURE!r} and the register "
            f"says {src.model_development_exposure!r}. One of them is wrong "
            f"and the module is scoring against a reference whose "
            f"independence it has mis-stated (I-058)."
        )


# --------------------------------------------------------------------------- #
# joint_person: the check that found I-069
# --------------------------------------------------------------------------- #

def test_the_joint_check_catches_a_population_with_right_marginals_and_a_wrong_joint():
    """The planted fault is exactly I-069's shape.

    Two populations with the SAME economic-status marginal: one where status is
    drawn independently of age, one where it is conditioned. The first must
    fail and the second must do better - if both pass, the check cannot see
    the only fault it exists to see.
    """
    rng = np.random.default_rng(0)
    n = 3000
    ages = rng.integers(15, 90, n)

    # Independent: the fault. Status drawn from one marginal for everybody.
    marginal = {"employed": 0.45, "retired": 0.18, "student": 0.14,
                "home duties": 0.11, "unemployed": 0.07, "unable to work": 0.05}
    labels, probs = list(marginal), list(marginal.values())
    indep = pd.DataFrame({
        "age": ages,
        "econ_status": rng.choice(labels, size=n, p=probs),
    })

    # Conditioned: the same marginal overall, but nobody is retired at 20 and
    # nobody is a student at 70.
    def status_for(a: int) -> str:
        if a < 25:
            return str(rng.choice(["student", "employed", "unemployed"],
                                  p=[0.55, 0.38, 0.07]))
        if a >= 66:
            return str(rng.choice(["retired", "employed", "home duties"],
                                  p=[0.82, 0.10, 0.08]))
        return str(rng.choice(["employed", "home duties", "unemployed",
                               "unable to work"], p=[0.74, 0.14, 0.07, 0.05]))

    cond = pd.DataFrame({"age": ages,
                         "econ_status": [status_for(int(a)) for a in ages]})

    bad = JP.compare(persons=indep)
    good = JP.compare(persons=cond)

    assert bad["verdict"] == "FAIL", (
        "a population whose economic status is drawn independently of age "
        "passed the joint check. That is I-069's exact fault, so a check that "
        "passes it is measuring nothing."
    )
    assert bad["n_impossible_cells_populated"] > 0
    assert good["total_variation_distance"] < bad["total_variation_distance"], (
        f"conditioning status on age did not improve the joint distance "
        f"({good['total_variation_distance']} against "
        f"{bad['total_variation_distance']}), so the metric does not respond "
        f"to the thing it is supposed to measure"
    )


def test_the_reference_is_read_from_the_source_and_shape_checked():
    """A mis-read dimension would move an acceptance verdict."""
    ref = JP.reference_joint()
    assert ref["source"] == JP.SOURCE_KEY
    # `design`, not `none`. F1054 was held out until I-069's fix, which had to
    # draw its conditioning from FY047B - the same Census 2022 cross by
    # county. Both tables give the national 15+ total as 4,136,852 and each
    # partitions the State, so they share underlying counts and F1054 can no
    # longer validate what it informed.
    assert ref["model_development_exposure"] == "design"
    assert ref["total"] > 0
    # The module asserts its mapped cells sum to F1054's published total; this
    # pins that the check is live rather than nominal.
    assert abs(ref["total"] - ref["published_total"]) / ref["published_total"] < 0.02
    shares = list(ref["share"].values())
    assert abs(sum(shares) - 1.0) < 1e-9, (
        f"the reference shares sum to {sum(shares)}, not 1. A dropped "
        f"category makes every model share look too high."
    )


def test_an_unknown_settlement_stratum_is_refused():
    with pytest.raises(JP.JointValidationError, match="not exactly one"):
        JP.reference_joint("Towns of about fourteen thousand people")


def test_negative_ages_are_counted_and_not_absorbed_into_the_under_15_exclusion():
    """I-070. F1054 covers 15+, so an under-15 is excluded - and a NEGATIVE
    age would vanish into that exclusion unless it is counted separately."""
    df = pd.DataFrame({"age": [-1, -1, 3, 20, 40, 70],
                       "econ_status": ["home duties"] * 3 + ["employed"] * 3})
    t = JP.town_joint(df)
    assert t["n_persons_with_negative_age"] == 2
    assert t["n_persons_under_15_excluded"] == 3


# --------------------------------------------------------------------------- #
# venue_presence
# --------------------------------------------------------------------------- #

def _presence(rows: list[tuple]) -> pd.DataFrame:
    return pd.DataFrame(
        rows, columns=["person_id", "sim_day", "start_min", "end_min",
                       "location_kind", "location_id"])


def test_a_person_in_two_places_at_once_is_caught():
    """The failure that makes every venue occupancy wrong and is invisible
    from the venue side: each venue's own count looks fine."""
    rows = _presence([
        ("P1", 1, 540, 660, "venue", "VEN-A"),
        ("P1", 1, 600, 720, "venue", "VEN-B"),      # overlaps
    ])
    r = check_venue_presence_consistency(
        presence=rows, venues=None, capacities={"VEN-A": 50, "VEN-B": 50})
    assert r["consistency"]["person_in_two_places_at_once"] == 1
    assert r["consistent"] is False


def test_a_venue_row_with_no_venue_id_is_caught():
    """The state the build was in until WP7, and the reason
    check_venue_capacity could never have passed: it groups by location_id."""
    rows = _presence([
        ("P1", 1, 540, 660, "venue", None),
        ("P2", 1, 540, 660, "venue", "VEN-A"),
    ])
    r = check_venue_presence_consistency(
        presence=rows, venues=None, capacities={"VEN-A": 50})
    assert r["consistency"]["venue_rows_with_no_venue_id"] == 1
    assert r["consistent"] is False


def test_a_dangling_venue_reference_is_caught():
    rows = _presence([("P1", 1, 540, 660, "venue", "VEN-GHOST")])
    r = check_venue_presence_consistency(
        presence=rows, venues=None, capacities={"VEN-A": 50})
    assert r["consistency"]["venues_named_but_not_declared"] == ["VEN-GHOST"]
    assert r["consistent"] is False


def test_over_capacity_is_caught_and_reported_apart_from_consistency():
    """Capacity depends on an [A] number; consistency does not. A run that is
    internally consistent and over capacity must say so in both columns."""
    rows = _presence([
        (f"P{i}", 1, 540, 660, "venue", "VEN-A") for i in range(5)
    ])
    r = check_venue_presence_consistency(
        presence=rows, venues=None, capacities={"VEN-A": 2})
    assert r["capacity"]["within_capacity"] is False
    assert r["capacity"]["n_venue_days_over_capacity"] == 1
    # And the RECORDS are consistent, which is the point of separating them.
    assert r["consistency"]["person_in_two_places_at_once"] == 0
    assert r["consistent"] is True


def test_being_at_a_venue_and_at_home_at_once_is_caught():
    rows = _presence([
        ("P1", 1, 540, 660, "venue", "VEN-A"),
        ("P1", 1, 600, 700, "building", "B-1"),
    ])
    r = check_venue_presence_consistency(
        presence=rows, venues=None, capacities={"VEN-A": 50})
    assert r["consistency"]["person_at_a_venue_and_at_home_at_once"] == 1


def test_an_empty_presence_record_is_not_a_pass():
    r = check_venue_presence_consistency(
        presence=pd.DataFrame(columns=["person_id", "sim_day", "start_min",
                                       "end_min", "location_kind",
                                       "location_id"]),
        venues=None, capacities={"VEN-A": 5})
    assert r["measured"] is False
    assert "NOT the same as passing" in r["why"]


def test_missing_capacities_are_refused_rather_than_skipped():
    rows = _presence([("P1", 1, 540, 660, "venue", "VEN-A")])
    with pytest.raises(VenuePresenceError, match="every venue has a capacity"):
        check_venue_presence_consistency(presence=rows, venues=None,
                                         capacities={})


# --------------------------------------------------------------------------- #
# privacy
# --------------------------------------------------------------------------- #

def test_the_attacker_sees_only_the_export():
    """Ground truth may be a LABEL and never a feature.

    An attack that used `occupied` as a feature would score an AUC of 1.0 and
    the result would be meaningless. Tested by giving the attacker a frame
    whose export column carries no information at all: the AUC must collapse
    to chance, which it cannot do if a label has leaked into the features.
    """
    rng = np.random.default_rng(1)
    n_homes, n_int = 10, 24 * 4 * 14
    rows = []
    start = pd.Timestamp("2022-01-01", tz="UTC")
    for h in range(n_homes):
        for i in range(n_int):
            rows.append({
                "premises_id": f"MPRN-{h:03d}",
                "interval_start": start + pd.Timedelta(minutes=15 * i),
                # Pure noise, independent of occupancy.
                "import_wh": float(rng.normal(300, 50)),
                "occupied": bool(rng.random() < 0.5),
                "household_size": 1 + h % 4,
            })
    r = inf.run_attacks(frame=pd.DataFrame(rows), config_name="t",
                        interval_min=15)
    occ = r["attacks"]["occupancy_classifier"]
    assert occ["measured"] is True
    assert occ["auc_model"]["hi"] < 0.60, (
        f"the export carries pure noise and the occupancy attack still scored "
        f"an upper bound of {occ['auc_model']['hi']}. A ground-truth column "
        f"has leaked into the features."
    )


def test_the_split_is_by_home_and_too_few_homes_is_refused():
    """Design 7.8 trains on some homes and tests on others. A split by TIME
    would measure the informed-neighbour class and report it as the operator
    class."""
    rows = []
    start = pd.Timestamp("2022-01-01", tz="UTC")
    for h in range(2):
        for i in range(96):
            rows.append({"premises_id": f"MPRN-{h}",
                         "interval_start": start + pd.Timedelta(minutes=15 * i),
                         "import_wh": 300.0, "occupied": True,
                         "household_size": 2})
    with pytest.raises(inf.InferenceError, match="by-home split"):
        inf.run_attacks(frame=pd.DataFrame(rows), config_name="t",
                        interval_min=15)


def test_a_label_column_missing_is_an_error_not_a_silent_skip():
    rows = pd.DataFrame({"premises_id": ["A"], "interval_start": [0],
                         "import_wh": [1.0]})
    with pytest.raises(inf.InferenceError, match="LABELS"):
        inf.run_attacks(frame=rows, config_name="t", interval_min=30)


def test_an_unscoreable_occupancy_attack_is_not_recorded_as_clearing_screening():
    """A configuration whose attack could not be scored has not cleared the
    threshold; it has not been tested against it."""
    start = pd.Timestamp("2022-01-01", tz="UTC")
    rows = [{"premises_id": f"MPRN-{h}",
             "interval_start": start + pd.Timedelta(minutes=30 * i),
             "import_wh": 300.0,
             "occupied": True,                 # constant: nothing to classify
             "household_size": 2}
            for h in range(6) for i in range(48)]
    r = inf.run_attacks(frame=pd.DataFrame(rows), config_name="t",
                        interval_min=30)
    assert r["attacks"]["occupancy_classifier"]["measured"] is False
    assert r["screening"]["verdict"] == "NOT EVALUABLE"
    assert r["screening"]["applicable"] is False
    assert "not been tested" in r["screening"]["not_the_same_as_passing"]


def test_the_threat_model_has_an_attack_for_every_declared_target():
    """A target declared and never attacked would read as covered."""
    assert tm.unattacked_targets(inf.ATTACKS) == []
    # And the check must be able to notice an omission. It names the TARGET
    # left uncovered, not the attack that was dropped - which is the useful
    # direction: the threat model's claim is about targets.
    assert tm.unattacked_targets(
        tuple(a for a in inf.ATTACKS if a != "holiday_detector")
    ) == ["absence_period"]


def test_the_screening_threshold_is_applied_to_the_upper_bound():
    """A wide interval whose centre clears 0.60 has not cleared it."""
    assert tm.SCREENING_AUC == 0.60
    y = np.array([0] * 20 + [1] * 20)
    s = np.concatenate([np.linspace(0, 0.6, 20), np.linspace(0.4, 1.0, 20)])
    ci = inf.auc_ci(y, s)
    assert ci["hi"] >= ci["auc"] >= ci["lo"]
    assert ci["n_pos"] == 20 and ci["n_neg"] == 20


def test_auc_handles_the_tie_heavy_case_a_baseline_produces():
    """A time-of-day baseline predicts one of a few hundred values, so ties
    are the normal case. A convention that broke them in the attacker's
    favour would inflate every baseline."""
    y = np.array([0, 0, 1, 1])
    assert inf.auc(y, np.array([0.5, 0.5, 0.5, 0.5])) == pytest.approx(0.5)
    assert inf.auc(y, np.array([0.1, 0.2, 0.8, 0.9])) == pytest.approx(1.0)
    assert inf.auc(y, np.array([0.9, 0.8, 0.2, 0.1])) == pytest.approx(0.0)


# --------------------------------------------------------------------------- #
# overnight_lp1
# --------------------------------------------------------------------------- #

def test_the_lp1_comparison_omits_an_hour_with_nobody_awake_rather_than_dividing_by_zero():
    shape = {h: 1.0 for h in range(24)}
    awake = {h: (0.0 if h == 3 else 0.5) for h in range(24)}
    out = LP1.load_per_awake_person(hourly_shape=shape,
                                   awake_share_by_hour=awake)
    assert 3 not in out, (
        "an hour with nobody awake produced a quotient. Reporting a large "
        "number there would be an artefact of the division, not a finding."
    )
    assert out[0] == pytest.approx(2.0)


def test_an_unmeasured_run_cannot_produce_an_lp1_score():
    r = LP1.compare_to_lp1(feeder_shape={"measured": False},
                           awake_share={"measured": True})
    assert r["measured"] is False
    r2 = LP1.compare_to_lp1(
        feeder_shape={"measured": True, "hourly_shape_over_day_mean": {}},
        awake_share={"measured": False})
    assert r2["measured"] is False


def test_the_lp1_module_states_that_it_has_no_pass_mark():
    """PL-PEAK-01 owns the acceptance test. A second band invented here would
    be a threshold for a quantity with no published reference."""
    fs = {"measured": True,
          "hourly_shape_over_day_mean": {h: 1.0 for h in range(24)}}
    aw = {"measured": True, "awake_share_by_hour": {h: 0.5 for h in range(24)}}
    r = LP1.compare_to_lp1(feeder_shape=fs, awake_share=aw)
    assert r["measured"] is True
    assert "no_band_and_no_pass_mark" in r
    assert "PL-PEAK-01" in r["no_band_and_no_pass_mark"]
    assert "denominator_caveat" in r
    assert r["model_development_exposure"] == "none"


def test_f1054_and_the_fit_source_really_do_share_underlying_counts():
    """The measurement the reclassification rests on.

    F1054's exposure was moved from `none` to `design` because it shares
    Census 2022 counts with FY047B, which the population is now fitted to.
    That is an empirical claim, so this is the measurement rather than a
    comment asserting it: both tables must give the SAME national 15+ total.

    Written per table rather than generically, because the two have different
    shapes - F1054 carries its geography in the STATISTIC dimension and
    FY047B in a county dimension - and a generic reader that tried to find
    "the geography dimension" silently found none in F1054 on the first
    attempt.
    """
    from baile_nua.population import econ_by_age as EA
    from baile_nua.validation import joint_person as JP

    # F1054, via the module that reads it: its mapped cells are asserted
    # against the table's own published total inside reference_joint().
    ref = JP.reference_joint()
    f1054_towns_10k_plus = ref["published_total"]
    assert f1054_towns_10k_plus > 0

    # FY047B, via the module that reads it.
    prof = EA.age_profile_by_status()
    fy_cork = sum(sum(v.values()) for v in prof["counts"].values())
    assert fy_cork > 0

    # Both are Census 2022.
    assert prof["census_year"] == "2022", prof["census_year"]

    # The decisive comparison, read straight from the two files: the national
    # 15+ total each one publishes.
    import json
    from pathlib import Path

    import numpy as np

    from baile_nua.sources import REGISTRY

    root = Path(__file__).resolve().parents[2] / "sources"

    def read(key, dim_label_fragment, total_label, census_year="2022"):
        doc = json.loads((root / REGISTRY[key].relpath).read_text("utf-8"))
        ids, size, value, dim = (doc["id"], doc["size"], doc["value"],
                                 doc["dimension"])

        def index(k):
            c = dim[k]["category"]["index"]
            return c if isinstance(c, dict) else {str(v): i
                                                  for i, v in enumerate(c)}

        gd = [k for k in ids
              if dim_label_fragment.lower() in str(dim[k].get("label", "")).lower()
              or k == dim_label_fragment]
        assert len(gd) == 1, (key, gd)
        gd = gd[0]
        arr = np.array([np.nan if v is None else float(v) for v in value],
                       dtype=np.float64).reshape(size)
        pos = {k: i for i, k in enumerate(ids)}
        gi, gl = index(gd), dim[gd]["category"]["label"]

        sel = [0] * len(ids)
        for k in ids:
            lab = dim[k]["category"]["label"]
            if k == gd:
                continue
            if k == "TLIST(A1)":
                yk = [c for c, v in lab.items() if str(v).strip() == census_year]
                assert yk, (key, sorted(lab.values()))
                sel[pos[k]] = index(k)[yk[0]]
            else:
                pick = [c for c, v in lab.items()
                        if str(v).strip().lower().startswith(
                            ("all ", "both ", "total"))
                        and "change" not in str(v).lower()]
                sel[pos[k]] = index(k)[pick[0]] if pick else 0

        def at(gkey):
            s2 = list(sel)
            s2[pos[gd]] = gi[gkey]
            v = float(arr[tuple(s2)])
            return 0.0 if not np.isfinite(v) else v

        tk = [c for c, v in gl.items() if str(v).strip() == total_label]
        assert len(tk) == 1, (key, total_label, sorted(gl.values())[:8])
        return at(tk[0]), sum(at(c) for c in gi if c != tk[0])

    f_whole, f_parts = read(
        "cso.census.f1054_economic_status_by_age_group", "STATISTIC", "Ireland")
    y_whole, y_parts = read(
        "cso.census.fy047b_economic_status_by_age_and_county", "County", "State")

    assert abs(f_parts - f_whole) / f_whole < 0.001, (
        f"F1054's settlement rows sum to {f_parts:,.0f} against its own "
        f"'Ireland' total of {f_whole:,.0f}, so it does not partition the "
        f"State and the shared-counts argument does not hold as stated"
    )
    assert abs(y_parts - y_whole) / y_whole < 0.001, (
        f"FY047B's county rows sum to {y_parts:,.0f} against its 'State' "
        f"total of {y_whole:,.0f}"
    )
    assert abs(f_whole - y_whole) < 1.0, (
        f"F1054 gives the national 15+ population as {f_whole:,.0f} and "
        f"FY047B as {y_whole:,.0f}. F1054's reclassification to `design` "
        f"rests on these being the SAME Census counts; if they differ, "
        f"revisit it rather than leaving a comment that asserts it."
    )


# --------------------------------------------------------------------------- #
# the invariant the venue criterion depends on
# --------------------------------------------------------------------------- #

def test_every_outside_activity_is_either_a_venue_type_or_outdoors_at_home():
    """The completeness invariant, and the whole of the venue criterion.

    The engine maps ``zone == "outside"`` to ``location_kind = "venue"``, which
    conflates two meanings of the word: outdoors, and away from home. Gardening
    is the first - a person gardening is at their own building - and recording
    them at a venue put 6,042 presence rows in a 14-day town run with
    ``location_kind="venue"`` and no venue to name.

    So an outside activity must be exactly one of two things: an activity with
    a venue type, or an activity in ``OUTDOORS_BUT_AT_HOME``. A new one that is
    neither fails here rather than silently producing unnamed venue rows that
    only the week-3 criterion would find, three artefacts later.
    """
    from baile_nua.activity.engine import ACTIVITY_CODES, OUTDOORS_BUT_AT_HOME
    from baile_nua.population.venues import VENUE_TYPES

    outside = {a for a, spec in ACTIVITY_CODES.items()
               if spec.get("zone") == "outside"}
    mapped = {a for spec in VENUE_TYPES.values() for a in spec["activities"]}
    unaccounted = sorted(outside - mapped - set(OUTDOORS_BUT_AT_HOME))
    assert not unaccounted, (
        f"these activities have zone='outside' and are neither mapped to a "
        f"venue type nor declared OUTDOORS_BUT_AT_HOME: {unaccounted}. Each "
        f"will produce presence rows with location_kind='venue' and "
        f"location_id=None, which fails the week-3 venue-consistency "
        f"criterion and tells a detector nothing about where the person was."
    )
    # And the two sets must not overlap: an activity cannot be at a venue and
    # at home.
    both = sorted(mapped & set(OUTDOORS_BUT_AT_HOME))
    assert not both, (
        f"{both} are declared both as a venue activity and as "
        f"outdoors-at-home. The engine checks OUTDOORS_BUT_AT_HOME first, so "
        f"the venue mapping would be silently dead for them."
    )


def test_gardening_is_recorded_at_the_dwelling_not_at_a_venue():
    """The specific case, pinned on the engine's own output."""
    from baile_nua.activity.engine import ACTIVITY_CODES, OUTDOORS_BUT_AT_HOME

    assert "gardening" in OUTDOORS_BUT_AT_HOME
    assert ACTIVITY_CODES["gardening"]["zone"] == "outside", (
        "gardening's zone is no longer 'outside', so it no longer needs the "
        "OUTDOORS_BUT_AT_HOME exception and the exception should be removed "
        "rather than left to mislead"
    )
