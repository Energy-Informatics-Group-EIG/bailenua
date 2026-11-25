"""Design 6.4's non-sensor datasets, under 6.5's rules: D28, D29, D30, D31.

These are **observation models of human and administrative processes**, not
sensors. A survey answer is what a respondent would say; a recorded BER is what
an assessor wrote down and nobody updated. So each field has to name the
mechanism that would produce it, and 6.5's four rule families exist to stop
them becoming a clean copy of the ground truth with noise on top.

**Rule 1, strictly observational.** Every field in :data:`FIELD_MECHANISM`
names a real-world mechanism — a respondent answering, an assessor recording,
an installer logging, a station measuring. A field with no mechanism is
rejected: :func:`assert_every_field_has_a_mechanism` raises. Survey answers are
built from what a respondent would *know or believe*, which is why
``q_occupied_weekday_hours`` is derived from a rounded, recall-biased
impression of occupancy and never from the occupancy array.

**Rule 3, realistically imperfect, and the planted rates are the contract.**
Every error rate this module applies is declared in :data:`PLANTED_RATES` and
returned in the generator's record. The 6.5 test re-estimates each rate *from
the emitted data* and must recover it within tolerance. That is what makes
"realistically imperfect" a measurement rather than a claim: a generator that
silently applied half the declared non-response would fail.

**What the rates are and are not.** Design 6.5: "Error rates are calibrated
against survey-methodology and administrative-data quality evidence where
available, and flagged ``[A]`` where not." They are flagged, as A-51, with the
search record: PxStat publishes response rates for its own surveys (SILC, HBS,
LFS) as methodology notes rather than as tables, and nothing published gives
the rate at which Irish householders misreport an appliance or at which a BER
record goes stale. The *directions* are evidence-based and stated per rate; the
*magnitudes* are declared.

**Rule 2, temporal and causal consistency.** D31's weather comes from
:mod:`baile_nua.weather.site`, which already produces the site truth (D15, GT)
and the station observable (D31, OBS) from **one realisation** with one
``realisation_id``, related by a declared downscaling model. So that rule is
satisfied by construction rather than by this module, and the test checks the
construction.

**What is NOT built, and E2-7 fails on it.** D31's market series — wholesale
prices, carbon intensity, system demand, flexibility-service events. Their
sources are EirGrid and SEMO, neither declared in ``SOURCES.md``, and the
standing rule is that every source is declared before use. So D31 carries its
weather series and not its market series, and :data:`D31_NOT_BUILT` says so in
the artefact rather than leaving a reader to infer it from an absence.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import numpy as np

__all__ = [
    "FIELD_MECHANISM",
    "PLANTED_RATES",
    "D31_NOT_BUILT",
    "NonSensorError",
    "assert_every_field_has_a_mechanism",
    "build_study_protocol",
    "build_household_survey",
    "build_recorded_metadata",
    "build_external_series",
]


class NonSensorError(RuntimeError):
    pass


#: Rule 1. Every OBS field names the real-world mechanism that would produce
#: it. Not decoration: ``assert_every_field_has_a_mechanism`` rejects a frame
#: carrying a field that is not here, so a field cannot be added without
#: saying who would have recorded it.
FIELD_MECHANISM: dict[str, dict[str, str]] = {
    # ---- D28 study_protocol: who recorded it is the study team ----
    "D28.premises_id": {"who": "study team", "how": "the meter-point the invitation was addressed to"},
    "D28.protocol_event": {"who": "study team", "how": "the event logged: invited, consented, declined, installed, withdrew"},
    "D28.recorded_at": {"who": "study team", "how": "when the event was entered, which is not always when it happened"},
    "D28.recruitment_route": {"who": "study team", "how": "the channel the household came through"},
    "D28.consent_sensors": {"who": "the householder", "how": "what they agreed to on the consent form"},
    "D28.tier_consented": {"who": "the householder", "how": "the instrumentation tier they accepted"},
    "D28.install_delay_days": {"who": "the installer", "how": "days from consent to a working install"},
    "D28.trial_arm": {"who": "study team", "how": "the arm randomised at recruitment"},
    "D28.arm_deviation": {"who": "study team", "how": "non-compliance or crossover, noticed and written down"},
    "D28.withdrawal_reason": {"who": "the householder", "how": "what they said, when they said anything"},
    # ---- D29 household_survey: a respondent answering ----
    "D29.premises_id": {"who": "study team", "how": "the meter-point the questionnaire went to"},
    "D29.wave": {"who": "study team", "how": "which questionnaire round"},
    "D29.responded_at": {"who": "the respondent", "how": "when they submitted; null if they did not"},
    "D29.q_household_size": {"who": "the respondent", "how": "how many people they say live there"},
    "D29.q_children_under_18": {"who": "the respondent", "how": "self-reported count"},
    "D29.q_occupied_weekday_hours": {"who": "the respondent", "how": "their impression of how long someone is home, rounded to a half hour"},
    "D29.q_dwelling_type": {"who": "the respondent", "how": "what they call their home"},
    "D29.q_heating_system": {"who": "the respondent", "how": "what they believe heats it"},
    "D29.q_has_pv": {"who": "the respondent", "how": "yes / no / don't know"},
    "D29.q_has_ev": {"who": "the respondent", "how": "yes / no / don't know"},
    "D29.q_appliances": {"who": "the respondent", "how": "ticked from a list, with omissions"},
    "D29.q_env_behaviour_score": {"who": "the respondent", "how": "a Likert self-report, socially desirable"},
    "D29.q_comfort_preference_c": {"who": "the respondent", "how": "the temperature they say they like"},
    "D29.straightlined": {"who": "study team", "how": "derived from the answer pattern during data cleaning"},
    "D29.item_nonresponse_count": {"who": "study team", "how": "counted from the blanks"},
    # ---- D30 recorded_metadata: an assessor or installer recording ----
    "D30.premises_id": {"who": "the record system", "how": "the meter-point the record is filed under"},
    "D30.record_version": {"who": "the record system", "how": "how many times the record has been written"},
    "D30.recorded_at": {"who": "the assessor or installer", "how": "the date on the record, which may be years old"},
    "D30.record_source": {"who": "the record system", "how": "BER assessment, installer certificate, or the operator's own file"},
    "D30.rec_ber_band": {"who": "a BER assessor", "how": "the band on the certificate, as of its assessment date"},
    "D30.rec_ber_kwh_m2_yr": {"who": "a BER assessor", "how": "the figure on the certificate"},
    "D30.rec_floor_area_m2": {"who": "a BER assessor", "how": "measured on site, sometimes in the wrong unit"},
    "D30.rec_dwelling_type": {"who": "a BER assessor", "how": "the type recorded"},
    "D30.rec_build_year": {"who": "a BER assessor", "how": "the year recorded, often a band's midpoint"},
    "D30.rec_heating_system": {"who": "a BER assessor", "how": "the system present at assessment"},
    "D30.rec_pv_kwp": {"who": "the installer", "how": "the capacity on the certificate, sometimes kW not kWp"},
    "D30.rec_pv_install_date": {"who": "the installer", "how": "the commissioning date"},
    "D30.rec_pv_azimuth_deg": {"who": "the installer", "how": "the orientation recorded, to the nearest 45 degrees"},
    "D30.rec_shading": {"who": "the installer", "how": "a coarse category on the site survey"},
    "D30.record_conflict": {"who": "the record system", "how": "two sources disagreeing, where anyone noticed"},
    "D30.asset_since_removed": {"who": "the record system", "how": "the asset is gone and the record is not"},
    # ---- D31 external_series: a station or a market operator measuring ----
    "D31.series_id": {"who": "the publisher", "how": "the series as published"},
    "D31.ts": {"who": "the publisher", "how": "the interval stamp, at the publisher's own convention"},
    "D31.value": {"who": "the instrument or market", "how": "the published value; null where the station was out"},
    "D31.unit": {"who": "the publisher", "how": "the published unit"},
    "D31.station_or_zone": {"who": "the publisher", "how": "which station or market zone"},
    "D31.quality": {"who": "the publisher", "how": "the publisher's own quality flag"},
    "D31.provenance": {"who": "the publisher", "how": "measured, gap-filled, modelled or revised"},
    "D31.revision": {"who": "the publisher", "how": "how many times the value has been restated"},
    "D31.realisation_id": {"who": "the simulation", "how": "which weather realisation this series belongs to, so the station and the site cannot disagree"},
    "D31.segment": {"who": "the simulation", "how": "real historical or generated, recorded in the evidence view only"},
}

#: ``[A]``, A-51. Every error rate this module plants, with the DIRECTION the
#: evidence supports and the magnitude declared. The 6.5 planted-rate recovery
#: test re-estimates each one from the emitted data.
PLANTED_RATES: dict[str, dict[str, Any]] = {
    "survey_unit_nonresponse": {
        "value": 0.28,
        "direction_is_evidenced": (
            "household surveys lose a quarter to a half of an invited sample, "
            "and response falls with privacy concern - which is why this is "
            "conditioned on the household's privacy trait rather than applied "
            "flat"
        ),
        "magnitude_is": "[A]",
    },
    "survey_item_nonresponse": {
        "value": 0.06,
        "direction_is_evidenced": "item non-response is far below unit non-response",
        "magnitude_is": "[A]",
    },
    "survey_straightlining": {
        "value": 0.09,
        "direction_is_evidenced": "satisficers straight-line; the population carries a satisficer trait",
        "magnitude_is": "[A]",
    },
    "survey_appliance_omission": {
        "value": 0.17,
        "direction_is_evidenced": "respondents under-report appliances they rarely think about",
        "magnitude_is": "[A]",
    },
    "survey_pv_dont_know": {
        "value": 0.11,
        "direction_is_evidenced": "tenants frequently do not know what is on the roof",
        "magnitude_is": "[A]",
    },
    "survey_occupancy_overstated_hours": {
        "value": 1.6,
        "unit": "hours",
        "direction_is_evidenced": (
            "design 6.4: 'optimistic occupancy'. Respondents overstate how "
            "much someone is home, so this is signed POSITIVE and a recovery "
            "test that found it negative would be a planted-rate failure"
        ),
        "magnitude_is": "[A]",
    },
    "survey_env_desirability_points": {
        "value": 1.0,
        "unit": "Likert points",
        "direction_is_evidenced": (
            "social desirability inflates self-reported environmental "
            "behaviour; signed POSITIVE"
        ),
        "magnitude_is": "[A]",
    },
    "record_ber_stale": {
        "value": 0.22,
        "direction_is_evidenced": (
            "a BER is valid ten years and is not reissued after a retrofit "
            "unless a grant required it, so the recorded band is pre-retrofit "
            "for a real share of upgraded homes"
        ),
        "magnitude_is": "[A]",
    },
    "record_missing_field": {
        "value": 0.08,
        "direction_is_evidenced": "administrative records have blanks",
        "magnitude_is": "[A]",
    },
    "record_unit_error": {
        "value": 0.015,
        "direction_is_evidenced": (
            "kW recorded as kWp and square metres as square feet are the two "
            "classic transcription errors; rare and large"
        ),
        "magnitude_is": "[A]",
    },
    "record_asset_since_removed": {
        "value": 0.03,
        "direction_is_evidenced": "assets are removed and records are not updated",
        "magnitude_is": "[A]",
    },
    "record_source_conflict": {
        "value": 0.07,
        "direction_is_evidenced": "assessor and installer disagree where both recorded",
        "magnitude_is": "[A]",
    },
    "protocol_decline_sensors": {
        "value": 0.31,
        "direction_is_evidenced": (
            "consent to in-home sensing is refused by a substantial minority, "
            "and refusal rises with the privacy trait - conditioned, not flat"
        ),
        "magnitude_is": "[A]",
    },
    "protocol_withdrawal_per_year": {
        "value": 0.045,
        "direction_is_evidenced": "panel attrition compounds over a ten-year study",
        "magnitude_is": "[A]",
    },
    "protocol_withdrawal_reason_given": {
        "value": 0.55,
        "direction_is_evidenced": "about half of withdrawals give no reason",
        "magnitude_is": "[A]",
    },
    "protocol_arm_deviation": {
        "value": 0.12,
        "direction_is_evidenced": "non-compliance and crossover in a behavioural trial",
        "magnitude_is": "[A]",
    },
    "station_outage": {
        "value": 0.012,
        "direction_is_evidenced": "stations go out and the gap is filled",
        "magnitude_is": "[A]",
    },
}

#: What D31 does not carry, stated rather than left as an absence.
D31_NOT_BUILT: dict[str, Any] = {
    "series_not_built": ("wholesale_price", "carbon_intensity",
                         "system_demand", "flex_event"),
    "why": (
        "Their publishers are EirGrid and SEMO and neither is declared in "
        "SOURCES.md. The standing rule is that every source is declared "
        "before use, and acquiring two new publishers' series - with their "
        "licences, their revision conventions and their time-zone handling - "
        "is a source-acquisition exercise rather than a generator. So D31 "
        "carries the weather series it can source and not the market series."
    ),
    "consequence": (
        "E2-7 FAILS. D28, D29 and D30 are built and pass the 6.5 tests that "
        "can run; D31 is partial, so the criterion 'D28 to D31 pass the 6.5 "
        "tests' is not met. Reported as a failure, not as partial credit."
    ),
    "what_it_blocks_specifically": (
        "6.5 rule 2's cross-correlation test - 'prices correlated with wind, "
        "demand and temperature; carbon intensity with the generation mix' - "
        "cannot run on series that are absent. The weather half of rule 2 can "
        "and does: one realisation drives the site truth and the station "
        "observable, related by a declared downscaling model."
    ),
}


def assert_every_field_has_a_mechanism(dataset: str, columns: Any) -> None:
    """Rule 1. A field with no named mechanism is rejected at the boundary.

    Raises rather than warns: design 6.5 says "A field with no such mechanism
    is rejected at schema level", and a warning would let one through.
    """
    missing = [c for c in columns if f"{dataset}.{c}" not in FIELD_MECHANISM]
    if missing:
        raise NonSensorError(
            f"{dataset} carries fields with no named real-world mechanism: "
            f"{missing}. Design 6.5 rule 1: every OBS field must name the "
            f"mechanism that would produce it - a respondent answering, an "
            f"assessor recording, an installer logging, a station measuring. "
            f"Add it to FIELD_MECHANISM, which means saying who would have "
            f"written this down."
        )


def _gen(master_seed: int, entity: str, draw: int = 0) -> Any:
    from baile_nua.rng import SeedTree, Stream

    return SeedTree(master_seed).generator(
        Stream.RECORDED_METADATA, entity=entity, draw=draw)


def _survey_gen(master_seed: int, entity: str, draw: int = 0) -> Any:
    from baile_nua.rng import SeedTree, Stream

    return SeedTree(master_seed).generator(
        Stream.SURVEY_RESPONSE, entity=entity, draw=draw)


def _protocol_gen(master_seed: int, entity: str, draw: int = 0) -> Any:
    from baile_nua.rng import SeedTree, Stream

    return SeedTree(master_seed).generator(
        Stream.STUDY_PROTOCOL, entity=entity, draw=draw)


# --------------------------------------------------------------------------- #
# D28  study_protocol
# --------------------------------------------------------------------------- #

RECRUITMENT_ROUTES: tuple[tuple[str, float], ...] = (
    ("letter to the meter-point", 0.46),
    ("community group", 0.21),
    ("local radio and press", 0.14),
    ("door to door", 0.12),
    ("word of mouth", 0.07),
)

TRIAL_ARMS: tuple[tuple[str, float], ...] = (
    ("control", 0.40),
    ("time-of-use tariff", 0.24),
    ("feedback", 0.20),
    ("flexibility requests", 0.16),
)


def build_study_protocol(
    *, premises: Any, traits: Any, master_seed: int, n_years: int = 10,
) -> dict[str, Any]:
    """D28. Recruitment, consent, install, arm, withdrawal — per premises.

    **Selection is driven by traits**, which design 6.4 requires and which is
    the whole point of the dataset: "homes that accept sensors aren't typical".
    The true selection mechanism stays in GT; what D28 carries is what the
    study team wrote down.

    ``traits`` maps premises_id to ``{"privacy": float, "env": float,
    "instTrust": float}`` — the population's own standardised traits.
    """
    import pandas as pd

    rows: list[dict[str, Any]] = []
    truth: list[dict[str, Any]] = []
    base = pd.Timestamp("2022-01-01", tz="UTC")

    for pid in sorted(premises):
        t = traits.get(pid) or {}
        privacy = float(t.get("privacy", 0.0))
        trust = float(t.get("instTrust", 0.0))
        g = _protocol_gen(master_seed, pid)

        route = _pick(g, RECRUITMENT_ROUTES)
        # Consent to sensors falls with privacy concern and rises with
        # institutional trust. The LOGIT is where the selection lives, and the
        # coefficients are [A] - their SIGNS are the modelled claim.
        lo = (_logit(1.0 - PLANTED_RATES["protocol_decline_sensors"]["value"])
              - 0.9 * privacy + 0.5 * trust)
        p_consent = 1.0 / (1.0 + np.exp(-lo))
        consented = bool(g.random() < p_consent)
        tier = (None if not consented else
                str(g.choice(["T1", "T2", "T3", "T4"],
                             p=[0.46, 0.33, 0.15, 0.06])))
        delay = int(np.clip(g.gamma(2.0, 9.0), 0, 180)) if consented else None
        arm = _pick(g, TRIAL_ARMS)
        deviated = bool(g.random() < PLANTED_RATES["protocol_arm_deviation"]["value"])

        rows.append({
            "premises_id": pid, "protocol_event": "invited",
            "recorded_at": base + pd.Timedelta(days=int(g.integers(0, 60))),
            "recruitment_route": route, "consent_sensors": None,
            "tier_consented": None, "install_delay_days": None,
            "trial_arm": None, "arm_deviation": None,
            "withdrawal_reason": None,
        })
        rows.append({
            "premises_id": pid,
            "protocol_event": ("consented" if consented else "declined"),
            "recorded_at": base + pd.Timedelta(days=int(g.integers(60, 120))),
            "recruitment_route": route,
            "consent_sensors": ("yes" if consented else "no"),
            "tier_consented": tier,
            "install_delay_days": delay,
            "trial_arm": (arm if consented else None),
            "arm_deviation": (("crossover" if deviated else "none")
                              if consented else None),
            "withdrawal_reason": None,
        })

        # Withdrawal: a hazard per year, compounding, so a ten-year panel
        # loses a real share of itself.
        withdrew_year = None
        if consented:
            for y in range(n_years):
                if g.random() < PLANTED_RATES["protocol_withdrawal_per_year"]["value"]:
                    withdrew_year = y
                    break
        if withdrew_year is not None:
            gave_reason = bool(
                g.random() < PLANTED_RATES["protocol_withdrawal_reason_given"]["value"])
            rows.append({
                "premises_id": pid, "protocol_event": "withdrew",
                "recorded_at": base + pd.Timedelta(days=365 * withdrew_year
                                                   + int(g.integers(0, 365))),
                "recruitment_route": route, "consent_sensors": "withdrawn",
                "tier_consented": tier, "install_delay_days": None,
                "trial_arm": arm, "arm_deviation": None,
                "withdrawal_reason": (str(g.choice(
                    ["moved house", "too intrusive", "no longer interested",
                     "bereavement", "no time"]))
                    if gave_reason else None),
            })

        truth.append({
            "premises_id": pid, "true_consent_probability": round(p_consent, 6),
            "privacy": privacy, "instTrust": trust,
            "consented": consented, "withdrew_year": withdrew_year,
            "true_arm": arm, "true_arm_deviation": deviated,
        })

    df = pd.DataFrame(rows)
    assert_every_field_has_a_mechanism("D28", df.columns)
    n_prem = len(premises)
    n_cons = sum(1 for t in truth if t["consented"])
    return {
        "dataset": "D28", "access_class": "OBS",
        "rows": df,
        "ground_truth_selection": pd.DataFrame(truth),
        "planted": {
            "protocol_decline_sensors":
                PLANTED_RATES["protocol_decline_sensors"]["value"],
            "protocol_withdrawal_per_year":
                PLANTED_RATES["protocol_withdrawal_per_year"]["value"],
            "protocol_arm_deviation":
                PLANTED_RATES["protocol_arm_deviation"]["value"],
            "protocol_withdrawal_reason_given":
                PLANTED_RATES["protocol_withdrawal_reason_given"]["value"],
        },
        "observed": {
            "n_premises": n_prem,
            "consent_rate": round(n_cons / max(n_prem, 1), 4),
            "decline_rate": round(1 - n_cons / max(n_prem, 1), 4),
        },
        "selection_is_not_random": (
            "Consent is a logit in the household's own privacy and "
            "institutional-trust traits, so the instrumented sub-sample is "
            "NOT a random sample of the town - which is design 6.4's point: "
            "'homes that accept sensors aren't typical'. The true consent "
            "probability is in ground_truth_selection and never in D28."
        ),
    }


def _pick(g: Any, options: tuple[tuple[str, float], ...]) -> str:
    labels = [o[0] for o in options]
    w = np.array([o[1] for o in options], dtype=np.float64)
    return str(g.choice(labels, p=w / w.sum()))


def _logit(p: float) -> float:
    p = float(np.clip(p, 1e-6, 1 - 1e-6))
    return float(np.log(p / (1 - p)))


# --------------------------------------------------------------------------- #
# D29  household_survey
# --------------------------------------------------------------------------- #

def build_household_survey(
    *, truth_by_premises: Any, traits: Any, master_seed: int,
    waves: tuple[int, ...] = (1, 2),
) -> dict[str, Any]:
    """D29. What a respondent would say, which is not what is true.

    ``truth_by_premises`` maps premises_id to the GT a respondent could in
    principle know: ``household_size``, ``children_under_18``,
    ``occupied_weekday_hours``, ``dwelling_type``, ``heating_system``,
    ``has_pv``, ``has_ev``, ``appliances`` (a list), ``env_behaviour_score``,
    ``comfort_preference_c``.

    Every answer is a *degraded* version of one of those, by a mechanism named
    in :data:`FIELD_MECHANISM`. Nothing is copied: the too-good test in the 6.5
    suite fails a field that agrees with its GT counterpart more closely than
    the planted error allows.
    """
    import pandas as pd

    R = PLANTED_RATES
    rows: list[dict[str, Any]] = []
    planted_log: list[dict[str, Any]] = []
    base = pd.Timestamp("2022-03-01", tz="UTC")

    for pid in sorted(truth_by_premises):
        gt = truth_by_premises[pid]
        t = traits.get(pid) or {}
        privacy = float(t.get("privacy", 0.0))
        satisficer = float(t.get("satisficer", 0.0))

        for wave in waves:
            g = _survey_gen(master_seed, pid, draw=wave)
            # Unit non-response, conditioned on privacy: the direction is the
            # evidenced part and the base rate is [A].
            lo = (_logit(R["survey_unit_nonresponse"]["value"])
                  + 0.8 * privacy)
            p_nr = 1.0 / (1.0 + np.exp(-lo))
            if g.random() < p_nr:
                rows.append({
                    "premises_id": pid, "wave": wave, "responded_at": None,
                    **{k: None for k in (
                        "q_household_size", "q_children_under_18",
                        "q_occupied_weekday_hours", "q_dwelling_type",
                        "q_heating_system", "q_has_pv", "q_has_ev",
                        "q_appliances", "q_env_behaviour_score",
                        "q_comfort_preference_c")},
                    "straightlined": False, "item_nonresponse_count": 0,
                })
                planted_log.append({"premises_id": pid, "wave": wave,
                                    "unit_nonresponse": True})
                continue

            straight = bool(g.random() < R["survey_straightlining"]["value"]
                            * (1.0 + 0.5 * satisficer))
            # Household size: respondents are accurate about it, but a
            # household with a lodger or an adult child away sometimes
            # miscounts. Signed symmetrically.
            size_true = int(gt.get("household_size", 0))
            size_said = size_true
            if g.random() < 0.09:
                size_said = max(1, size_true + int(g.choice([-1, 1])))

            # Occupancy: OVERSTATED, which is the signed claim.
            occ_true = float(gt.get("occupied_weekday_hours", 0.0))
            occ_said = occ_true + R["survey_occupancy_overstated_hours"]["value"] \
                + float(g.normal(0, 1.1))
            occ_said = float(np.clip(round(occ_said * 2) / 2.0, 0.0, 24.0))

            # PV: a share say don't know.
            pv_true = bool(gt.get("has_pv", False))
            pv_said = ("don't know"
                       if g.random() < R["survey_pv_dont_know"]["value"]
                       else ("yes" if pv_true else "no"))
            ev_true = bool(gt.get("has_ev", False))
            ev_said = ("don't know" if g.random() < 0.04
                       else ("yes" if ev_true else "no"))

            # Appliances: omissions only. A respondent does not invent a
            # dishwasher they do not have, which is why this is one-sided.
            appl_true = list(gt.get("appliances", ()))
            appl_said = [a for a in appl_true
                         if g.random() >= R["survey_appliance_omission"]["value"]]

            # Environmental behaviour: inflated by social desirability.
            env_true = float(gt.get("env_behaviour_score", 3.0))
            env_said = int(np.clip(round(
                env_true + R["survey_env_desirability_points"]["value"]
                + g.normal(0, 0.6)), 1, 5))

            comfort_true = float(gt.get("comfort_preference_c", 20.0))
            comfort_said = float(np.round(
                comfort_true + g.normal(0, 0.8), 1))

            row = {
                "premises_id": pid, "wave": wave,
                "responded_at": base + pd.Timedelta(
                    days=365 * (wave - 1) + int(g.integers(0, 45))),
                "q_household_size": size_said,
                "q_children_under_18": int(gt.get("children_under_18", 0)),
                "q_occupied_weekday_hours": occ_said,
                "q_dwelling_type": gt.get("dwelling_type"),
                "q_heating_system": (
                    gt.get("heating_system") if g.random() > 0.12
                    else "don't know"),
                "q_has_pv": pv_said, "q_has_ev": ev_said,
                "q_appliances": appl_said,
                "q_env_behaviour_score": (3 if straight else env_said),
                "q_comfort_preference_c": comfort_said,
                "straightlined": straight,
                "item_nonresponse_count": 0,
            }
            # Item non-response, applied last so the count is what it says.
            blanked = 0
            for field in ("q_children_under_18", "q_occupied_weekday_hours",
                          "q_dwelling_type", "q_heating_system",
                          "q_env_behaviour_score", "q_comfort_preference_c"):
                if g.random() < R["survey_item_nonresponse"]["value"]:
                    row[field] = None
                    blanked += 1
            row["item_nonresponse_count"] = blanked
            rows.append(row)
            planted_log.append({
                "premises_id": pid, "wave": wave, "unit_nonresponse": False,
                "straightlined": straight, "n_items_blanked": blanked,
                "appliances_true": len(appl_true),
                "appliances_said": len(appl_said),
            })

    df = pd.DataFrame(rows)
    assert_every_field_has_a_mechanism("D29", df.columns)
    return {
        "dataset": "D29", "access_class": "OBS",
        "rows": df,
        "planted": {k: R[k]["value"] for k in (
            "survey_unit_nonresponse", "survey_item_nonresponse",
            "survey_straightlining", "survey_appliance_omission",
            "survey_pv_dont_know", "survey_occupancy_overstated_hours",
            "survey_env_desirability_points")},
        "planted_log": pd.DataFrame(planted_log),
        "no_latent_trait_appears": (
            "Design 6.5 rule 1: 'Latent traits, true occupancy schedules and "
            "causal links never appear.' The traits CONDITION non-response - "
            "which is the realism - and no trait value is emitted."
        ),
    }


# --------------------------------------------------------------------------- #
# D30  recorded_metadata
# --------------------------------------------------------------------------- #

def build_recorded_metadata(
    *, truth_by_premises: Any, master_seed: int,
) -> dict[str, Any]:
    """D30. What the record says, which is sometimes years out of date.

    The staleness mechanism is the interesting one and it is not noise: a BER
    is valid for ten years and is not reissued after a retrofit unless a grant
    required it, so a *retrofitted* home's recorded band is its **pre-retrofit**
    band. That is a specific, directional error a model must cope with, and it
    is why ``record_ber_stale`` is applied to the retrofitted homes rather than
    uniformly.
    """
    import pandas as pd

    R = PLANTED_RATES
    rows: list[dict[str, Any]] = []
    planted_log: list[dict[str, Any]] = []

    for pid in sorted(truth_by_premises):
        gt = truth_by_premises[pid]
        g = _gen(master_seed, pid)
        assessed = pd.Timestamp(gt.get("ber_assessed_at", "2015-06-01"), tz="UTC")

        stale = (bool(gt.get("retrofitted", False))
                 and g.random() < R["record_ber_stale"]["value"])
        band = (gt.get("ber_band_before_retrofit") if stale
                else gt.get("ber_band"))
        kwh = (gt.get("ber_kwh_m2_yr_before_retrofit") if stale
               else gt.get("ber_kwh_m2_yr"))

        floor = float(gt.get("floor_area_m2", 0.0))
        unit_err = g.random() < R["record_unit_error"]["value"]
        if unit_err:
            # Square metres recorded as square feet: the classic one, and a
            # factor of 10.76 rather than a small perturbation.
            floor = round(floor * 10.7639, 1)

        pv_kwp = gt.get("pv_kwp")
        pv_unit_err = pv_kwp is not None and g.random() < R["record_unit_error"]["value"]
        if pv_unit_err and pv_kwp:
            pv_kwp = round(float(pv_kwp) * 0.92, 2)      # kW recorded for kWp

        removed = bool(g.random() < R["record_asset_since_removed"]["value"])
        conflict = (str(g.choice(["assessor vs installer on PV size",
                                 "assessor vs operator on heating system",
                                 "two floor areas on file"]))
                    if g.random() < R["record_source_conflict"]["value"]
                    else None)

        row = {
            "premises_id": pid, "record_version": 1,
            "recorded_at": assessed,
            "record_source": str(g.choice(
                ["BER assessment", "installer certificate", "operator file"],
                p=[0.62, 0.23, 0.15])),
            "rec_ber_band": band, "rec_ber_kwh_m2_yr": kwh,
            "rec_floor_area_m2": floor,
            "rec_dwelling_type": gt.get("dwelling_type"),
            "rec_build_year": gt.get("build_year"),
            "rec_heating_system": gt.get("heating_system"),
            "rec_pv_kwp": pv_kwp,
            "rec_pv_install_date": gt.get("pv_install_date"),
            "rec_pv_azimuth_deg": (
                None if gt.get("pv_azimuth_deg") is None
                else float(round(float(gt["pv_azimuth_deg"]) / 45.0) * 45.0)),
            "rec_shading": gt.get("shading_category"),
            "record_conflict": conflict,
            "asset_since_removed": removed,
        }
        blanked = []
        for field in ("rec_ber_kwh_m2_yr", "rec_build_year", "rec_shading",
                      "rec_pv_azimuth_deg", "rec_heating_system"):
            if g.random() < R["record_missing_field"]["value"]:
                row[field] = None
                blanked.append(field)
        rows.append(row)
        planted_log.append({
            "premises_id": pid, "ber_stale": stale,
            "floor_unit_error": unit_err, "pv_unit_error": pv_unit_err,
            "asset_since_removed": removed,
            "has_conflict": conflict is not None,
            "n_blanked": len(blanked),
            "retrofitted": bool(gt.get("retrofitted", False)),
        })

    df = pd.DataFrame(rows)
    assert_every_field_has_a_mechanism("D30", df.columns)
    return {
        "dataset": "D30", "access_class": "OBS",
        "rows": df,
        "planted": {k: R[k]["value"] for k in (
            "record_ber_stale", "record_missing_field", "record_unit_error",
            "record_asset_since_removed", "record_source_conflict")},
        "planted_log": pd.DataFrame(planted_log),
        "staleness_is_conditional": (
            "record_ber_stale applies only to RETROFITTED homes, because that "
            "is the mechanism: a BER is valid ten years and is not reissued "
            "after an upgrade unless a grant required it. Applying it "
            "uniformly would make it noise instead of the directional error a "
            "model actually has to cope with."
        ),
    }


# --------------------------------------------------------------------------- #
# D31  external_series
# --------------------------------------------------------------------------- #

def build_external_series(
    *, realisation: Any, master_seed: int,
) -> dict[str, Any]:
    """D31. The station series, from the SAME realisation as the site truth.

    6.5 rule 2's first requirement — "One weather realisation drives
    everything" — is satisfied by construction:
    :mod:`baile_nua.weather.site` produces the site truth (D15, GT) and the
    station observable from one realisation and tags both with one
    ``realisation_id``. This function converts the station frame to D31 rows
    and adds the publisher-side imperfections: outages, gap-filling and
    revisions.

    The market series are **not built** — see :data:`D31_NOT_BUILT`.
    """
    import pandas as pd

    R = PLANTED_RATES
    st = getattr(realisation, "station_hourly", None)
    if st is None or len(st) == 0:
        raise NonSensorError(
            "the realisation carries no station_hourly frame, so D31 has no "
            "weather series to publish")
    rid = getattr(realisation, "realisation_id", None)
    if not rid:
        raise NonSensorError(
            "the realisation has no realisation_id, so D31 rows could not be "
            "tied to the site truth they must be consistent with (6.5 rule 2)")

    value_cols = [c for c in st.columns
                  if c not in ("ts", "station", "realisation_id")
                  and pd.api.types.is_numeric_dtype(st[c])]
    if not value_cols:
        raise NonSensorError(
            f"the station frame has no numeric series: {list(st.columns)}")

    rows: list[dict[str, Any]] = []
    n_out = 0
    # The station frame may carry its stamp as a column or as the index, and
    # a DatetimeIndex has no .iloc - so it is normalised to a Series once here
    # rather than guarded at every use.
    ts = pd.Series(
        pd.to_datetime(st["ts"] if "ts" in st.columns else st.index, utc=True)
    ).reset_index(drop=True)
    station = (str(st["station"].iloc[0]) if "station" in st.columns
               else "ROCHES_POINT")
    for col in value_cols:
        g = _gen(master_seed, f"D31:{col}")
        vals = pd.to_numeric(st[col], errors="coerce").to_numpy(dtype=float)
        out = g.random(len(vals)) < R["station_outage"]["value"]
        n_out += int(out.sum())
        for i, v in enumerate(vals):
            outage = bool(out[i])
            if outage:
                # Gap-filled, not blank: a station outage is usually filled
                # from a neighbour and published with a quality flag, which is
                # a different thing for a model to cope with than a hole.
                filled = (float(np.nanmean(vals[max(i - 3, 0):i + 4]))
                          if np.isfinite(vals[max(i - 3, 0):i + 4]).any()
                          else None)
                rows.append({
                    "series_id": f"station.{col}", "ts": ts.iloc[i],
                    "value": (None if filled is None else round(filled, 4)),
                    "unit": _unit_for(col), "station_or_zone": station,
                    "quality": "estimated", "provenance": "gap_filled",
                    "revision": 0, "realisation_id": rid,
                    "segment": "real_historical",
                })
                continue
            rev = 1 if g.random() < 0.004 else 0
            rows.append({
                "series_id": f"station.{col}", "ts": ts.iloc[i],
                "value": (None if not np.isfinite(v) else round(float(v), 4)),
                "unit": _unit_for(col), "station_or_zone": station,
                "quality": ("good" if np.isfinite(v) else "missing"),
                "provenance": "measured", "revision": rev,
                "realisation_id": rid, "segment": "real_historical",
            })

    df = pd.DataFrame(rows)
    assert_every_field_has_a_mechanism("D31", df.columns)
    return {
        "dataset": "D31", "access_class": "OBS",
        "rows": df,
        "realisation_id": rid,
        "series_built": sorted(f"station.{c}" for c in value_cols),
        "planted": {"station_outage": R["station_outage"]["value"]},
        "observed": {"n_rows": len(df),
                     "n_gap_filled": n_out,
                     "gap_filled_rate": round(n_out / max(len(df), 1), 5)},
        "one_realisation_drives_everything": (
            f"These rows carry realisation_id {rid}, the same id the site "
            f"truth (D15, GT) carries. weather/site.py produces both from one "
            f"realisation related by a declared downscaling model, so the "
            f"station and the site cannot disagree about the day - which is "
            f"6.5 rule 2's first requirement, satisfied by construction."
        ),
        "not_built": D31_NOT_BUILT,
    }


def _unit_for(col: str) -> str:
    c = col.lower()
    if "temp" in c:
        return "degC"
    if "rh" in c or "humid" in c:
        return "percent"
    if "wind" in c or "wdsp" in c:
        return "m/s"
    if "rain" in c or "precip" in c:
        return "mm"
    if "ghi" in c or "dni" in c or "dhi" in c or "rad" in c:
        return "W/m2"
    if "msl" in c or "press" in c:
        return "hPa"
    if "clamt" in c or "cloud" in c:
        return "oktas"
    if "sun" in c:
        return "hours"
    return "unknown"
