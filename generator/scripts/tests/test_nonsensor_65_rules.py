"""Design 6.5's four rule families, as tests. E2-7's criterion.

Each rule gets the test the design names for it, and each test is built to be
able to fail on a generator that looked right:

**Rule 1, strictly observational.** The *too-good* test is the important one
and it is counter-intuitive: a survey field that agrees with ground truth
*more* closely than its calibrated error allows **fails**. A generator that
quietly copied the truth would pass every ordinary check and fail this. The
*join* test is its companion: two OBS datasets must not reconcile perfectly
where real ones would not.

**Rule 2, temporally and causally consistent external data.** One weather
realisation drives everything, so D31's station rows and D15's site truth must
carry the same ``realisation_id`` and must not disagree about the day.

**Rule 3, realistically imperfect.** Every planted rate is re-estimated *from
the emitted data* and must come back. This is what turns "realistically
imperfect" into a measurement: a generator applying half its declared
non-response fails here and nowhere else.

**Rule 4, blind-evaluation safe.** Reported NOT EVALUABLE, and the reason is
not a shortcut: the test is that "a classifier given only D28 to D31 features
can't separate Baile Nua from **the real reference package**", and there is no
real reference package in this build. A classifier trained against nothing
would be a number with no meaning. Stated in
``test_rule_4_is_not_evaluable_and_that_is_not_a_pass``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import baile_nua.sources_registry  # noqa: F401  (declares the sources)
from baile_nua.observation import nonsensor as NS

SEED = 20251011
N = 400


# --------------------------------------------------------------------------- #
# fixtures: a synthetic truth to observe
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def truth() -> dict:
    """Ground truth for N premises, with the fields a respondent could know."""
    rng = np.random.default_rng(7)
    appliance_pool = ["washing_machine", "dishwasher", "tumble_dryer",
                      "electric_shower", "oven", "kettle", "microwave"]
    out = {}
    for i in range(N):
        pid = f"MPRN-{i:05d}"
        retro = bool(rng.random() < 0.35)
        out[pid] = {
            "household_size": int(rng.integers(1, 6)),
            "children_under_18": int(rng.integers(0, 3)),
            "occupied_weekday_hours": float(np.round(rng.uniform(6, 20), 1)),
            "dwelling_type": str(rng.choice(["detached", "semi-detached",
                                             "terraced", "apartment"])),
            "heating_system": str(rng.choice(["gas boiler", "oil boiler",
                                              "heat pump"])),
            "has_pv": bool(rng.random() < 0.18),
            "has_ev": bool(rng.random() < 0.09),
            "appliances": [a for a in appliance_pool if rng.random() < 0.7],
            "env_behaviour_score": float(rng.integers(1, 5)),
            "comfort_preference_c": float(np.round(rng.normal(20.5, 1.4), 1)),
            # D30's fields
            "retrofitted": retro,
            "ber_band": ("C2" if retro else "E1"),
            "ber_band_before_retrofit": "E1",
            "ber_kwh_m2_yr": (190.0 if retro else 310.0),
            "ber_kwh_m2_yr_before_retrofit": 310.0,
            "floor_area_m2": float(np.round(rng.uniform(70, 170), 1)),
            "build_year": int(rng.integers(1940, 2015)),
            "pv_kwp": (float(np.round(rng.uniform(2, 6), 2))
                       if rng.random() < 0.18 else None),
            "pv_install_date": None,
            "pv_azimuth_deg": float(rng.uniform(90, 270)),
            "shading_category": str(rng.choice(["none", "light", "heavy"])),
            "ber_assessed_at": "2015-06-01",
        }
    return out


@pytest.fixture(scope="module")
def traits(truth) -> dict:
    rng = np.random.default_rng(11)
    return {pid: {"privacy": float(rng.normal(0, 1)),
                  "env": float(rng.normal(0, 1)),
                  "instTrust": float(rng.normal(0, 1)),
                  "satisficer": float(rng.normal(0, 1))}
            for pid in truth}


@pytest.fixture(scope="module")
def d29(truth, traits) -> dict:
    return NS.build_household_survey(
        truth_by_premises=truth, traits=traits, master_seed=SEED, waves=(1, 2))


@pytest.fixture(scope="module")
def d30(truth) -> dict:
    return NS.build_recorded_metadata(
        truth_by_premises=truth, master_seed=SEED)


@pytest.fixture(scope="module")
def d28(truth, traits) -> dict:
    return NS.build_study_protocol(
        premises=list(truth), traits=traits, master_seed=SEED, n_years=10)


# --------------------------------------------------------------------------- #
# Rule 1: strictly observational
# --------------------------------------------------------------------------- #

def test_rule_1_every_obs_field_names_its_mechanism(d28, d29, d30):
    """Design 6.5: "A field with no such mechanism is rejected at schema level"."""
    for rec, name in ((d28, "D28"), (d29, "D29"), (d30, "D30")):
        NS.assert_every_field_has_a_mechanism(name, rec["rows"].columns)
    # And the rejection must be live, not nominal.
    with pytest.raises(NS.NonSensorError, match="no named real-world mechanism"):
        NS.assert_every_field_has_a_mechanism("D29", ["q_true_occupancy_array"])


def test_rule_1_too_good_appliances_do_not_match_the_truth(d29, truth):
    """The too-good test. A survey that matches the truth too well FAILS.

    Appliance omission is planted at 0.17, so the reported count must be about
    83% of the true count. If a generator copied the list, agreement would be
    1.0 and this is the only test that would notice.
    """
    log = d29["planted_log"]
    answered = log[~log["unit_nonresponse"].astype(bool)]
    ratio = (answered["appliances_said"].sum()
             / max(answered["appliances_true"].sum(), 1))
    planted = NS.PLANTED_RATES["survey_appliance_omission"]["value"]
    expected = 1.0 - planted
    assert ratio < 0.97, (
        f"reported appliances are {ratio:.4f} of the true count. A survey "
        f"that agrees with ground truth this closely has copied it: design "
        f"6.5's too-good test fails a field whose agreement exceeds its "
        f"calibrated error's upper bound."
    )
    assert abs(ratio - expected) < 0.04, (
        f"appliance agreement is {ratio:.4f} against the {expected:.4f} the "
        f"planted omission rate of {planted} implies"
    )


def test_rule_1_too_good_occupancy_is_overstated_not_accurate(d29, truth):
    """Design 6.4 says "optimistic occupancy", so the error is SIGNED.

    A generator that added symmetric noise would pass a magnitude test and
    fail this: the mean error must be positive and near the planted value.
    """
    df = d29["rows"]
    got = df[df["q_occupied_weekday_hours"].notna()]
    err = np.array([
        float(r.q_occupied_weekday_hours)
        - float(truth[r.premises_id]["occupied_weekday_hours"])
        for r in got.itertuples()])
    planted = NS.PLANTED_RATES["survey_occupancy_overstated_hours"]["value"]
    assert err.mean() > 0.5, (
        f"mean occupancy error is {err.mean():+.3f} h. Design 6.4 requires "
        f"optimistic occupancy, so the error is signed POSITIVE; a symmetric "
        f"error would be noise and not the reporting bias."
    )
    assert abs(err.mean() - planted) < 0.35, (
        f"mean overstatement {err.mean():.3f} h against a planted "
        f"{planted} h")
    # And it must not be exact: a respondent's impression is rounded.
    assert (np.abs(err) < 1e-9).mean() < 0.15, (
        "more than 15% of occupancy answers are exactly right, which a "
        "rounded recall-biased impression would not be")


def test_rule_1_the_join_does_not_reconcile_perfectly(d29, truth):
    """Design 6.5: OBS datasets must not reconcile perfectly where real ones
    wouldn't.

    Survey household size against the true household size: real surveys
    disagree with the meter-point record for a real minority, and a perfect
    join would be the tell.
    """
    df = d29["rows"]
    got = df[df["q_household_size"].notna()]
    agree = np.array([
        int(r.q_household_size) == int(truth[r.premises_id]["household_size"])
        for r in got.itertuples()])
    rate = float(agree.mean())
    assert rate < 0.99, (
        f"survey household size matches the truth in {rate:.4f} of responses. "
        f"A perfect join between an OBS survey and the ground truth is design "
        f"6.5's join-test failure."
    )
    assert rate > 0.80, (
        f"survey household size matches in only {rate:.4f} of responses, "
        f"which is implausibly bad - respondents know how many people live "
        f"in their house"
    )


def test_rule_1_no_latent_trait_or_true_schedule_is_emitted(d28, d29, d30):
    """6.5 rule 1: "Latent traits, true occupancy schedules and causal links
    never appear."

    The traits CONDITION non-response and consent, which is the realism. No
    trait value may be in an OBS frame. Checked on the column names as a
    property, so a new leaky field is caught rather than a fixed list.
    """
    forbidden = ("privacy", "insttrust", "env_score", "satisficer", "big5",
                 "latent", "mcv", "true_", "lambda_", "occupancy_array",
                 "schedule", "propensity")
    for rec, name in ((d28, "D28"), (d29, "D29"), (d30, "D30")):
        bad = [c for c in rec["rows"].columns
               if any(f in c.lower() for f in forbidden)]
        assert not bad, f"{name} emits {bad}, which 6.5 rule 1 forbids"
    # The GT selection frame is allowed to carry them - it is GT - and must
    # not be the same object as the OBS rows.
    assert "true_consent_probability" in d28["ground_truth_selection"].columns
    assert "true_consent_probability" not in d28["rows"].columns


def test_rule_1_consent_is_not_random_so_the_sample_is_selected(d28):
    """Design 6.4: "homes that accept sensors aren't typical".

    The consenting sub-sample must differ in privacy from the declining one,
    or the dataset carries no selection effect and analysts have nothing to
    correct for.
    """
    gt = d28["ground_truth_selection"]
    yes = gt[gt["consented"].astype(bool)]["privacy"]
    no = gt[~gt["consented"].astype(bool)]["privacy"]
    assert len(yes) > 20 and len(no) > 20, (len(yes), len(no))
    assert yes.mean() < no.mean() - 0.2, (
        f"consenting households have mean privacy {yes.mean():.3f} and "
        f"declining {no.mean():.3f}. Consent must fall with privacy concern "
        f"or the selection effect the dataset exists to carry is absent."
    )


# --------------------------------------------------------------------------- #
# Rule 2: temporally and causally consistent external data
# --------------------------------------------------------------------------- #

def test_rule_2_one_realisation_drives_the_site_and_the_station():
    """6.5 rule 2: "One weather realisation drives everything."

    D31's station rows and D15's site truth must carry the SAME
    realisation_id. If they could differ, the station and the site could
    disagree about the day, and every price-weather and demand-weather
    relationship downstream would be built on two different weeks.
    """
    from baile_nua.weather.site import build_realisation

    r = build_realisation(2022, master_seed=SEED, days=3)
    d31 = NS.build_external_series(realisation=r, master_seed=SEED)

    assert d31["realisation_id"] == r.realisation_id
    assert set(d31["rows"]["realisation_id"]) == {r.realisation_id}, (
        "D31 rows carry a realisation_id that is not the site truth's, so the "
        "station and the site are not the same realisation"
    )
    site_id = (r.site_hourly["realisation_id"].iloc[0]
               if "realisation_id" in r.site_hourly.columns
               else r.realisation_id)
    assert site_id == r.realisation_id


def test_rule_2_the_station_differs_from_the_site_but_tracks_it():
    """The station is not the site, and is not unrelated to it either.

    Design 6.4 item 7: "The gap between station and site weather is itself
    realistic." So the two must differ - a station reading identical to the
    site would be the site - and must correlate, because they are the same
    weather an hour's drive apart.
    """
    from baile_nua.weather.site import build_realisation

    r = build_realisation(2022, master_seed=SEED, days=7)
    site, st = r.site_hourly, r.station_hourly
    common = [c for c in site.columns if c in st.columns
              and pd.api.types.is_numeric_dtype(site[c])
              and pd.api.types.is_numeric_dtype(st[c])]
    tcols = [c for c in common if "temp" in c.lower()]
    assert tcols, f"no temperature column common to site and station: {common}"
    c = tcols[0]
    a = pd.to_numeric(site[c], errors="coerce").to_numpy(dtype=float)
    b = pd.to_numeric(st[c], errors="coerce").to_numpy(dtype=float)
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    ok = np.isfinite(a) & np.isfinite(b)
    assert ok.sum() > 48
    assert not np.allclose(a[ok], b[ok]), (
        "the station temperature is identical to the site temperature, so the "
        "downscaling model is not doing anything and D31 is a copy of D15"
    )
    rho = float(np.corrcoef(a[ok], b[ok])[0, 1])
    assert rho > 0.9, (
        f"site and station temperature correlate at only {rho:.3f}. They are "
        f"the same weather an hour apart; a low correlation means they are "
        f"not the same realisation."
    )


def test_rule_2_timestamps_are_utc_interval_start_and_monotone(d31_weather):
    """6.5 rule 2's third test: "No series is misaligned in time (DST, time
    zone, interval-end vs interval-start conventions)."."""
    df = d31_weather["rows"]
    ts = pd.to_datetime(df["ts"], utc=True)
    assert str(ts.dt.tz) == "UTC", ts.dt.tz
    for sid, grp in df.groupby("series_id"):
        t = pd.to_datetime(grp["ts"], utc=True)
        assert t.is_monotonic_increasing, f"{sid} is not time-ordered"
        assert not t.duplicated().any(), f"{sid} has duplicate timestamps"


@pytest.fixture(scope="module")
def d31_weather() -> dict:
    from baile_nua.weather.site import build_realisation

    r = build_realisation(2022, master_seed=SEED, days=5)
    return NS.build_external_series(realisation=r, master_seed=SEED)


def test_rule_2_a_gap_filled_value_is_flagged_not_hidden(d31_weather):
    """A station outage is published with a quality flag, which is a different
    thing for a model to cope with than a silent hole."""
    df = d31_weather["rows"]
    filled = df[df["provenance"] == "gap_filled"]
    assert len(filled) > 0, (
        "no gap-filled rows at all, so the station-outage mechanism is not "
        "firing and the planted rate cannot be recovered")
    assert set(filled["quality"]) <= {"estimated"}, (
        "a gap-filled value is flagged 'good', which hides the imperfection "
        "the dataset exists to carry")


# --------------------------------------------------------------------------- #
# Rule 3: realistically imperfect — the planted rates must be recoverable
# --------------------------------------------------------------------------- #

def test_rule_3_survey_planted_rates_are_recovered(d29):
    """Design 6.5: "each planted rate is recovered from the data within
    tolerance". The test that turns the claim into a measurement."""
    df, log = d29["rows"], d29["planted_log"]
    P = NS.PLANTED_RATES

    # Unit non-response. Conditioned on privacy, so the recovered rate is the
    # population average of a logit and sits NEAR rather than AT the base
    # rate: the tolerance says so rather than the test pretending otherwise.
    nr = float(df["responded_at"].isna().mean())
    want = P["survey_unit_nonresponse"]["value"]
    assert abs(nr - want) < 0.06, (
        f"unit non-response recovered at {nr:.4f} against a planted {want}. "
        f"It is conditioned on the privacy trait, so it is an average of a "
        f"logit, but a gap this large means the rate is not being applied."
    )

    answered = df[df["responded_at"].notna()]
    # Item non-response: per answered row, per eligible field (6 of them).
    items = float(answered["item_nonresponse_count"].mean() / 6.0)
    want_i = P["survey_item_nonresponse"]["value"]
    assert abs(items - want_i) < 0.02, (
        f"item non-response recovered at {items:.4f} against {want_i}")

    # Straightlining.
    sl = float(answered["straightlined"].mean())
    want_s = P["survey_straightlining"]["value"]
    assert abs(sl - want_s) < 0.06, (
        f"straightlining recovered at {sl:.4f} against {want_s}")

    # Don't-know on PV.
    dk = float((answered["q_has_pv"] == "don't know").mean())
    want_dk = P["survey_pv_dont_know"]["value"]
    assert abs(dk - want_dk) < 0.04, (
        f"PV don't-know recovered at {dk:.4f} against {want_dk}")


def test_rule_3_record_planted_rates_are_recovered(d30, truth):
    """D30's rates, including the conditional one.

    BER staleness applies only to RETROFITTED homes, so it is recovered
    against that denominator and not against all homes - which is the same
    distinction the generator makes.
    """
    log = d30["planted_log"]
    P = NS.PLANTED_RATES

    retro = log[log["retrofitted"].astype(bool)]
    stale = float(retro["ber_stale"].mean())
    want = P["record_ber_stale"]["value"]
    assert abs(stale - want) < 0.07, (
        f"BER staleness recovered at {stale:.4f} among retrofitted homes "
        f"against a planted {want}")
    # And it must be ZERO among the un-retrofitted, because the mechanism is
    # "the certificate predates the upgrade".
    not_retro = log[~log["retrofitted"].astype(bool)]
    assert float(not_retro["ber_stale"].mean()) == 0.0, (
        "an un-retrofitted home has a stale BER, which the mechanism cannot "
        "produce: staleness here means the certificate predates an upgrade")

    removed = float(log["asset_since_removed"].mean())
    assert abs(removed - P["record_asset_since_removed"]["value"]) < 0.025

    conflict = float(log["has_conflict"].mean())
    assert abs(conflict - P["record_source_conflict"]["value"]) < 0.035

    blanked = float(log["n_blanked"].mean() / 5.0)
    assert abs(blanked - P["record_missing_field"]["value"]) < 0.025


def test_rule_3_a_unit_error_is_large_not_a_perturbation(d30, truth):
    """kW for kWp and square feet for square metres are TRANSCRIPTION errors.

    A model has to cope with a floor area ten times too big, which is a
    different problem from one 5% too big. A generator that applied a small
    perturbation would pass a rate test and fail this.
    """
    df, log = d30["rows"], d30["planted_log"]
    bad = log[log["floor_unit_error"].astype(bool)]["premises_id"].tolist()
    if not bad:
        pytest.skip("no floor unit error in this sample")
    rows = df[df["premises_id"].isin(bad)]
    for r in rows.itertuples():
        ratio = float(r.rec_floor_area_m2) / float(
            truth[r.premises_id]["floor_area_m2"])
        assert ratio > 5.0, (
            f"a 'unit error' changed the floor area by {ratio:.2f}x. Square "
            f"feet for square metres is a factor of 10.76; a small "
            f"perturbation is noise, not a transcription error."
        )


def test_rule_3_protocol_planted_rates_are_recovered(d28):
    """Consent and attrition, recovered from the emitted events."""
    gt = d28["ground_truth_selection"]
    P = NS.PLANTED_RATES
    decline = float((~gt["consented"].astype(bool)).mean())
    want = P["protocol_decline_sensors"]["value"]
    assert abs(decline - want) < 0.08, (
        f"sensor decline recovered at {decline:.4f} against a planted {want}; "
        f"it is conditioned on privacy and trust, so it is an average of a "
        f"logit")
    # Attrition over ten years, from a per-year hazard.
    consented = gt[gt["consented"].astype(bool)]
    withdrew = float(consented["withdrew_year"].notna().mean())
    h = P["protocol_withdrawal_per_year"]["value"]
    expected = 1.0 - (1.0 - h) ** 10
    assert abs(withdrew - expected) < 0.08, (
        f"ten-year attrition recovered at {withdrew:.4f} against the "
        f"{expected:.4f} a per-year hazard of {h} implies")


def test_rule_3_station_outage_rate_is_recovered(d31_weather):
    got = d31_weather["observed"]["gap_filled_rate"]
    want = NS.PLANTED_RATES["station_outage"]["value"]
    assert abs(got - want) < 0.006, (
        f"station outage recovered at {got} against a planted {want}")


# --------------------------------------------------------------------------- #
# Rule 4: blind-evaluation safe
# --------------------------------------------------------------------------- #

def test_rule_4_is_not_evaluable_and_that_is_not_a_pass():
    """6.5 rule 4's test needs a real reference package, and there is none.

    The design's wording is "a classifier given only D28 to D31 features can't
    separate Baile Nua from **the real reference package**". No real reference
    package exists in this build - acquiring one is the S-track's work - so a
    classifier would have nothing to be trained against and its score would
    have no meaning.

    Asserted as NOT EVALUABLE rather than skipped, so the E2 report cannot
    quietly count rule 4 among the rules that pass.
    """
    from baile_nua.observation.nonsensor import D31_NOT_BUILT

    assert "E2-7 FAILS" in D31_NOT_BUILT["consequence"], (
        "the module must state that E2-7 fails, so a reader of the artefact "
        "is not left to infer it from an absence")
    # The claim this test exists to pin: rule 4 is unevaluated, and the reason
    # is the absence of a reference and not the absence of effort.
    reference_packages: tuple[str, ...] = ()
    assert reference_packages == (), (
        "a real reference package now exists, so 6.5 rule 4 CAN be evaluated "
        "and this test must be replaced by the classifier it describes"
    )


# --------------------------------------------------------------------------- #
# the criterion itself
# --------------------------------------------------------------------------- #

def test_e2_7_is_reported_as_failing_because_d31_is_partial():
    """E2-7: "D28 to D31 pass the 6.5 tests".

    D28, D29 and D30 are built and pass the rules that can run. D31 carries
    its weather series and not its market series, because EirGrid and SEMO are
    not declared sources and the standing rule is that every source is
    declared before use. So the criterion is not met, and this test pins that
    the module says so rather than leaving the gap to be discovered.
    """
    nb = NS.D31_NOT_BUILT
    assert set(nb["series_not_built"]) == {
        "wholesale_price", "carbon_intensity", "system_demand", "flex_event"}
    assert "EirGrid" in nb["why"] and "SEMO" in nb["why"]
    assert "not as partial credit" in nb["consequence"]
    assert "cross-correlation" in nb["what_it_blocks_specifically"], (
        "the artefact must name the specific 6.5 test the absence blocks, not "
        "just say a dataset is missing")
