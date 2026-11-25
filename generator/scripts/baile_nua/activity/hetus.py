"""HETUS activity targets, and the Irish anchoring (design 5.3; E0-2 / U04; I-008).

**The honest position, stated once and carried everywhere.**  Eurostat HETUS
contains **no Irish data in any wave** (ISSUES.md I-008): the 2020 wave covers
11 countries and the 2000/2010 wave 22, and Ireland is in neither.  U04's
approved fallback is "HETUS/UK TUS with Irish recalibration", so:

* **activity durations and the diurnal profile** come from HETUS 2000/2010 with
  ``geo='UK'`` - the nearest neighbour on language, working week, school
  calendar and climate;
* **the timing that matters most for load** is anchored to real Irish,
  Cobh-specific Census data: SAPS Theme 11 gives means of travel to work
  (T11_1), **time leaving home** (T11_2), **journey time** (T11_3) and
  **working from home** (T11_4), for Cobh's own 53 small areas.

The activity engine is therefore flagged **VERIFIED, NOT CALIBRATED**
throughout, per E0-2, and D10 carries that flag in the schema.

HETUS codes, as they appear in ``acl00``, with the UK 2010 all-persons figures
read from the file (not recalled):

====================  ========  =======================================
Code                  UK 2010   Meaning
====================  ========  =======================================
``AC0``                 10:43   Personal care (total)
``AC01``                 8:22   Sleep
``AC02``                 1:25   Eating
``AC03``                 0:56   Other personal care
``AC1_TR``               2:37   Employment (total, = AC1A + AC1B)
``AC2``                  0:22   Study
``AC3``                  2:55   Household and family care (total)
``AC31A``                0:36   Food management
``AC32A``                0:13   Household upkeep
``AC33A``/``AC331``      0:07   Textiles and laundry
``AC36``                 0:31   Shopping and services
``AC38A``/``AC38B``      0:21   Childcare and adult care
``AC4-8``                5:15   Leisure (total)
``AC82``                 2:22   TV, video and media
``AC9A``                 2:09   Travel
====================  ========  =======================================

They sum to 24:00, which is the check that the top-level codes have been read
correctly rather than double-counted.
"""

from __future__ import annotations

import functools
from typing import Any

import numpy as np
import pandas as pd

from baile_nua.sources import require

__all__ = [
    "HETUS_DONOR_GEO",
    "HETUS_WAVE",
    "ACTIVITY_CODES",
    "hetus_time_spent",
    "hetus_time_spent_by_status",
    "ECON_TO_WSTATUS",
    "hetus_diurnal",
    "irish_departure_profile",
    "irish_journey_time_profile",
    "irish_remote_share",
    "CALIBRATION_FLAG",
]

#: There is no Irish row in HETUS, so the donor is explicit and travels with
#: every target derived from it.
HETUS_DONOR_GEO = "UK"
HETUS_WAVE = 2010
CALIBRATION_FLAG = "VERIFIED, NOT CALIBRATED (E0-2 / U04; HETUS has no Irish data, I-008)"

#: The ~30 activity states design 5.3 asks for, each mapped to the HETUS
#: code(s) whose duration target it draws from.
#:
#: ``hetus`` is a tuple of ``(code, weight)`` pairs, so one modelled activity
#: can draw on several HETUS codes (laundry is AC331 "Laundry" plus AC332
#: "Ironing") and several modelled activities can share one code with declared
#: weights (eating_main and eating_snack split AC02 "Eating" 55/45, because
#: HETUS does not distinguish them).  A weight below 1.0 is always a DECLARED
#: ASSUMPTION [A]; a weight of exactly 1.0 is a measurement.
#:
#: ``label`` repeats Eurostat's own English label for the code, and
#: :func:`mapping_audit` checks every one of them against the registered ACL00
#: codelist.  That check is not decoration.  The first version of this table
#: assigned codes from recollection and six of them were wrong (I-029):
#:
#:   * ``laundry`` -> AC33A, which is "Handicraft and producing textiles"
#:   * ``adult_care`` -> AC38B, which is "Teaching, reading and talking with
#:     CHILD" - a childcare code standing in for adult care
#:   * ``cleaning`` -> AC32A, "Household upkeep EXCEPT cleaning dwelling",
#:     while AC321 "Cleaning dwelling" went unused
#:   * ``reading`` -> AC7A, which is "Computing"
#:   * ``religion_civic`` -> AC53, which is "Resting"
#:   * ``washing_up`` -> a declared 38% split of AC31A, which is "Food
#:     management EXCEPT dish washing", while AC313 "Dish washing" went unused
#:
#: Each of those produced a target that was wrong in level and sometimes in
#: kind, and every one was invisible until the labels were read from a file.
ACTIVITY_CODES: dict[str, dict[str, Any]] = {
    "sleep":              {"hetus": (("AC01", 1.00),),  "zone": "bedroom",
                           "label": "Sleep"},
    # A nap is sleep outside the main sleep block; HETUS has no separate code,
    # so the 3% share is declared.
    "nap":                {"hetus": (("AC01", 0.03),),  "zone": "bedroom",
                           "label": "Sleep (daytime share, declared)"},
    "personal_care":      {"hetus": (("AC03", 0.55),),  "zone": "bathroom",
                           "label": "Other and/or unspecified personal care"},
    "shower_bath":        {"hetus": (("AC03", 0.30),),  "zone": "bathroom",
                           "label": "Other and/or unspecified personal care"},
    "dressing":           {"hetus": (("AC03", 0.15),),  "zone": "bedroom",
                           "label": "Other and/or unspecified personal care"},
    # AC31A already EXCLUDES dish washing, so cooking takes all of it and
    # washing_up takes AC313 in full. No split is needed or honest here.
    "cooking":            {"hetus": (("AC31A", 1.00),), "zone": "kitchen",
                           "label": "Food management except dish washing"},
    "washing_up":         {"hetus": (("AC313", 1.00),), "zone": "kitchen",
                           "label": "Dish washing"},
    "eating_main":        {"hetus": (("AC02", 0.55),),  "zone": "kitchen",
                           "label": "Eating"},
    "eating_snack":       {"hetus": (("AC02", 0.45),),  "zone": "living",
                           "label": "Eating"},
    # The modelled "laundry" activity is the whole wash-dry-iron cycle, so it
    # draws both codes in full.
    "laundry":            {"hetus": (("AC331", 1.00), ("AC332", 1.00)),
                           "zone": "utility", "label": "Laundry; Ironing"},
    "cleaning":           {"hetus": (("AC321", 1.00), ("AC32A", 1.00)),
                           "zone": "living",
                           "label": "Cleaning dwelling; Household upkeep except cleaning dwelling"},
    "diy_repairs":        {"hetus": (("AC35", 1.00),),  "zone": "utility",
                           "label": "Construction and repairs"},
    "gardening":          {"hetus": (("AC34A", 1.00),), "zone": "outside",
                           "label": "Gardening; other pet care"},
    # Both AC38 codes are child codes and both are childcare here.
    "childcare":          {"hetus": (("AC38A", 1.00), ("AC38B", 1.00)),
                           "zone": "living",
                           "label": "Childcare, except teaching, reading and talking; Teaching, reading and talking with child"},
    # HETUS has no adult-care code. AC37_39 "Household management and help
    # family member" is the nearest, and the substitution is flagged [A]: it
    # includes household management, so it over-states care and under-states
    # nothing. Design 5.3's caring_load is what actually drives the hours.
    "adult_care":         {"hetus": (("AC37_39", 1.00),), "zone": "living",
                           "label": "Household management and help family member [A: nearest code; HETUS has no adult-care code]"},
    # HETUS cannot separate work at the workplace from work at home: AC1_TR is
    # one code for both. The 85/15 split is declared, and design 5.3's
    # remote_share is what actually moves it per person.
    "work_at_workplace":  {"hetus": (("AC1_TR", 0.85),), "zone": "outside",
                           "label": "Employment, related activities and travel as part of/during main and second job"},
    "work_at_home":       {"hetus": (("AC1_TR", 0.15),), "zone": "living",
                           "label": "Employment, related activities and travel as part of/during main and second job"},
    # AC2 splits into its own components, so no declared split is needed.
    "school":             {"hetus": (("AC21A", 1.00),), "zone": "outside",
                           "label": "School and university except homework"},
    "study_at_home":      {"hetus": (("AC212", 1.00), ("AC22", 1.00)),
                           "zone": "bedroom",
                           "label": "Homework; Free time study"},
    "tv_screens":         {"hetus": (("AC82", 1.00),),  "zone": "living",
                           "label": "Television and video"},
    "reading":            {"hetus": (("AC811", 1.00), ("AC812", 1.00)),
                           "zone": "living",
                           "label": "Reading, except books; Reading books"},
    # Non-television indoor leisure: computing, games and listening.
    "hobbies":            {"hetus": (("AC7A", 1.00), ("AC7B", 1.00),
                                     ("AC733", 1.00), ("AC83", 1.00)),
                           "zone": "living",
                           "label": "Computing; Hobbies and games except computing and computer games; Computer games; Radio and music"},
    "social_at_home":     {"hetus": (("AC51A", 1.00),), "zone": "living",
                           "label": "Visiting and feasts"},
    "social_out":         {"hetus": (("AC51B", 1.00),), "zone": "outside",
                           "label": "Other social life"},
    "sport_exercise":     {"hetus": (("AC6A", 1.00), ("AC611", 1.00)),
                           "zone": "outside",
                           "label": "Sports and outdoor activities except walking and hiking; Walking and hiking"},
    "shopping":           {"hetus": (("AC36", 1.00),), "zone": "outside",
                           "label": "Shopping and services"},
    "religion_civic":     {"hetus": (("AC41", 1.00), ("AC43", 1.00),
                                     ("AC52", 1.00)),
                           "zone": "outside",
                           "label": "Organisational work; Participatory activities; Entertainment and culture"},
    # AC913 "Travel to/from work" sits inside AC9A, so the commute is taken out
    # of AC9A rather than being a declared share of it. The two then sum to
    # AC9A exactly, which is the check that the subtraction is right.
    "travel_commute":     {"hetus": (("AC913", 1.00),), "zone": "in_transit",
                           "label": "Travel to/from work"},
    "travel_other":       {"hetus": (("AC9A", 1.00), ("AC913", -1.00)),
                           "zone": "in_transit",
                           "label": "Travel except travel related to jobs, less travel to/from work"},
    # "Resting" is what idling is, and it is its own code - so the modelled
    # residual no longer has to be a 10% slice of all leisure.
    "idle_at_home":       {"hetus": (("AC53", 1.00),),  "zone": "living",
                           "label": "Resting"},
}


def _hhmm_to_minutes(value: Any) -> float:
    """Parse HETUS's ``hh:mm`` duration format into minutes.

    HETUS reports ``TIME_SP`` as ``"8:22"``, not as a decimal, and reading it as
    a float would silently give 8.22 minutes instead of 502.  Values marked
    with a flag or missing come back as NaN rather than zero, so a missing
    target is visible instead of looking like "no time spent".
    """
    if value is None:
        return float("nan")
    s = str(value).strip()
    if not s or s in (":", "-", ".", "NaN"):
        return float("nan")
    if ":" in s:
        parts = s.split(":")
        try:
            return float(int(parts[0]) * 60 + int(parts[1]))
        except (ValueError, IndexError):
            return float("nan")
    try:
        return float(s) * 60.0
    except ValueError:
        return float("nan")


@functools.lru_cache(maxsize=4)
def hetus_time_spent(
    *, geo: str = HETUS_DONOR_GEO, wave: int = HETUS_WAVE
) -> pd.DataFrame:
    """Daily minutes per HETUS activity code, by sex and age group.

    Long format: ``sex``, ``age``, ``acl00``, ``minutes``.  ``unit='TIME_SP'``
    is "time spent per day by all persons", which is the quantity a duration
    target needs - as distinct from ``PTP_TIME``, which is time spent *by
    participants only* and would overstate every minority activity.
    """
    d = pd.read_csv(require("eurostat.hetus.tus_00age"), low_memory=False)
    d = d[(d.geo == geo) & (d.TIME_PERIOD == wave) & (d.unit == "TIME_SP")]
    if d.empty:
        raise RuntimeError(
            f"no HETUS TIME_SP rows for geo={geo!r} wave={wave}. Ireland is "
            f"absent from every HETUS wave (I-008); the donor must be one of the "
            f"countries actually present."
        )
    out = d[["sex", "age", "acl00", "OBS_VALUE"]].copy()
    out["minutes"] = out["OBS_VALUE"].map(_hhmm_to_minutes)
    out = out.drop(columns=["OBS_VALUE"]).dropna(subset=["minutes"])
    out.attrs["geo"] = geo
    out.attrs["wave"] = wave
    out.attrs["calibration_flag"] = CALIBRATION_FLAG
    return out.reset_index(drop=True)


@functools.lru_cache(maxsize=4)
def hetus_diurnal(
    *, geo: str = HETUS_DONOR_GEO, wave: int = HETUS_WAVE
) -> pd.DataFrame:
    """Participation rate by time of day, for HETUS's nine broad groups.

    This is the table that constrains **when** things happen rather than only
    how long they last, which is what a semi-Markov engine needs and what
    design 7.3's occupancy row is compared against.  145 ten-minute slots cover
    the 24 hours (HETUS's day starts at 04:00, which is also when design 8.2's
    slow loop runs - a convenient coincidence, not a design dependency).

    Returned indexed by ``minute_of_day`` so the engine can look up a slot
    directly.
    """
    d = pd.read_csv(require("eurostat.hetus.tus_00startime"), low_memory=False)
    d = d[(d.geo == geo) & (d.TIME_PERIOD == wave) & (d.unit == "PTP_RT")]
    if d.empty:
        raise RuntimeError(f"no HETUS diurnal rows for geo={geo!r} wave={wave}")

    def slot_to_minute(s: str) -> float:
        # "H0730-0739" -> 7*60 + 30
        t = str(s)
        if not t.startswith("H") or "-" not in t:
            return float("nan")
        hhmm = t[1:].split("-")[0]
        try:
            return float(int(hhmm[:2]) * 60 + int(hhmm[2:4]))
        except (ValueError, IndexError):
            return float("nan")

    out = d[["sex", "startime", "acl00", "OBS_VALUE"]].copy()
    out["minute_of_day"] = out["startime"].map(slot_to_minute)
    out["participation_pct"] = pd.to_numeric(out["OBS_VALUE"], errors="coerce")
    out = out.dropna(subset=["minute_of_day", "participation_pct"])
    out["minute_of_day"] = out["minute_of_day"].astype(int)
    out.attrs["geo"] = geo
    out.attrs["wave"] = wave
    out.attrs["calibration_flag"] = CALIBRATION_FLAG
    return out.drop(columns=["OBS_VALUE", "startime"]).reset_index(drop=True)


@functools.lru_cache(maxsize=4)
def hetus_time_spent_by_status(
    *, geo: str = HETUS_DONOR_GEO, wave: int = HETUS_WAVE
) -> pd.DataFrame:
    """Daily minutes per activity, by **labour status** and sex.

    This is the conditioning design 5.3 asks for - "conditioned on person type"
    - and it matters a great deal more than the all-persons average. Measured,
    UK 2010, employment time (``AC1_TR``):

    =========================  =========
    Population                 Per day
    =========================  =========
    All persons                   2:37
    Full-time employed            5:07
    =========================  =========

    Comparing a full-time worker's simulated day against the 2:37 all-persons
    figure made the engine look 60% over on work and 50% under on everything
    else, when in fact it was the comparison that was wrong. ``wstatus`` values
    present: EMP_FT, EMP_PT, EDUC, HOME, RET, UNE, LEAV, OTH, POP.
    """
    d = pd.read_csv(require("eurostat.hetus.tus_00selfstat"), low_memory=False)
    d = d[(d.geo == geo) & (d.TIME_PERIOD == wave) & (d.unit == "TIME_SP")]
    if d.empty:
        raise RuntimeError(f"no HETUS labour-status rows for geo={geo!r} wave={wave}")
    out = d[["sex", "wstatus", "acl00", "OBS_VALUE"]].copy()
    out["minutes"] = out["OBS_VALUE"].map(_hhmm_to_minutes)
    out = out.drop(columns=["OBS_VALUE"]).dropna(subset=["minutes"])
    out.attrs["geo"] = geo
    out.attrs["wave"] = wave
    out.attrs["calibration_flag"] = CALIBRATION_FLAG
    return out.reset_index(drop=True)


#: Map the schema's ``econ_status`` and the engine's person types onto HETUS
#: ``wstatus`` values.  The mapping is explicit so a mismatch is visible rather
#: than falling through to the population average.
ECON_TO_WSTATUS: dict[str, str] = {
    "employed": "EMP_FT",
    "self-employed": "EMP_FT",
    "unemployed": "UNE",
    "student": "EDUC",
    "retired": "RET",
    "home duties": "HOME",
    "unable to work": "OTH",
}


# --------------------------------------------------------------------------- #
# The Irish anchoring: real Cobh Census data for the timing that matters
# --------------------------------------------------------------------------- #

#: SAPS Table 11.2 band -> (earliest, latest) minute of day for departure.
#: The bands are the Census's own; only the open ends need a choice, and both
#: are declared here rather than buried.
_DEPARTURE_BANDS: dict[str, tuple[int, int]] = {
    "before 06:30": (5 * 60, 6 * 60 + 29),      # open end: 05:00 assumed earliest
    "06:30-07:00": (6 * 60 + 30, 7 * 60),
    "07:01-07:30": (7 * 60 + 1, 7 * 60 + 30),
    "07:31-08:00": (7 * 60 + 31, 8 * 60),
    "08:01-08:30": (8 * 60 + 1, 8 * 60 + 30),
    "08:31-09:00": (8 * 60 + 31, 9 * 60),
    "09:01-09:30": (9 * 60 + 1, 9 * 60 + 30),
    "after 09:30": (9 * 60 + 31, 11 * 60),      # open end: 11:00 assumed latest
}

#: SAPS Table 11.3 band -> (lower, upper) journey minutes.
_JOURNEY_BANDS: dict[str, tuple[int, int]] = {
    "under 15 min": (3, 14),
    "15-30 min": (15, 29),
    "30-45 min": (30, 44),
    "45-60 min": (45, 59),
    "60-90 min": (60, 89),
    "90 min or more": (90, 150),
}


def irish_departure_profile(marginals: dict[str, Any] | None = None) -> dict[str, Any]:
    """Departure-time distribution for Cobh, from the real Census (T11_2).

    **This is the single most important Irish anchor in the activity engine.**
    HETUS has no Irish row, so departure timing - which sets the morning
    occupancy fall and therefore the morning load peak - would otherwise be
    purely UK-donor. SAPS T11_2 gives it for Cobh's own small areas.
    """
    if marginals is None:
        from baile_nua.population.saps import build_marginals

        marginals = {k: m.town_total for k, m in build_marginals().items()}
    counts = marginals["time_leaving_home"]
    stated = {k: float(counts[k]) for k in _DEPARTURE_BANDS if k in counts.index}
    total = sum(stated.values())
    if total <= 0:
        raise RuntimeError("Cobh departure-time marginal is empty")
    return {
        "source": "CSO Census 2022 SAPS Table 11.2, Cobh's 53 small areas",
        "bands": {k: _DEPARTURE_BANDS[k] for k in stated},
        "shares": {k: v / total for k, v in stated.items()},
        "n_persons": int(total),
        "not_stated_excluded": int(counts.get("not stated", 0)),
        "open_end_assumptions": {
            "before 06:30": "earliest assumed 05:00",
            "after 09:30": "latest assumed 11:00",
        },
        "evidence_tag": "[C] real Irish Census data for this town",
    }


def irish_journey_time_profile(marginals: dict[str, Any] | None = None) -> dict[str, Any]:
    """Journey-time distribution for Cobh, from the real Census (T11_3).

    Gives U02's return-time distribution directly: U02 models out-of-town work
    as an "outside" state "with travel time and return-time distributions", and
    this is that distribution, for Cobh rather than for Ireland as a whole.
    """
    if marginals is None:
        from baile_nua.population.saps import build_marginals

        marginals = {k: m.town_total for k, m in build_marginals().items()}
    counts = marginals["journey_time"]
    stated = {k: float(counts[k]) for k in _JOURNEY_BANDS if k in counts.index}
    total = sum(stated.values())
    if total <= 0:
        raise RuntimeError("Cobh journey-time marginal is empty")
    return {
        "source": "CSO Census 2022 SAPS Table 11.3, Cobh's 53 small areas",
        "bands": {k: _JOURNEY_BANDS[k] for k in stated},
        "shares": {k: v / total for k, v in stated.items()},
        "n_persons": int(total),
        "evidence_tag": "[C] real Irish Census data for this town",
    }


def irish_remote_share(marginals: dict[str, Any] | None = None) -> dict[str, Any]:
    """Share working from home, from the real Census (T11_4).

    Census 2022 was taken in April 2022, inside the E1 simulated year, so this
    is contemporaneous with the slice rather than projected - which matters,
    because the remote-work share moved a great deal either side of 2022.
    """
    if marginals is None:
        from baile_nua.population.saps import build_marginals

        marginals = {k: m.town_total for k, m in build_marginals().items()}
    counts = marginals["working_from_home"]
    wfh = float(counts.get("works from home", 0.0))
    never = float(counts.get("never works from home", 0.0))
    total = wfh + never
    return {
        "source": "CSO Census 2022 SAPS Table 11.4, Cobh's 53 small areas",
        "share_works_from_home": wfh / total if total else 0.0,
        "n_stated": int(total),
        "not_stated_excluded": int(counts.get("not stated", 0)),
        "census_date": "2022-04-03",
        "note": "contemporaneous with the E1 simulated year (E0-3)",
        "evidence_tag": "[C] real Irish Census data for this town",
    }


# --------------------------------------------------------------------------- #
# The codelist (I-029)
# --------------------------------------------------------------------------- #

@functools.lru_cache(maxsize=1)
def acl00_labels() -> dict[str, str]:
    """English labels for the HETUS activity codes, from Eurostat's codelist.

    The tus_00* tables carry codes and no text, so without this the mapping
    from an HETUS code to a modelled activity is only as good as someone's
    recollection of what the code means.  Mine was wrong once: ``AC33A`` is
    handicraft, not laundry.
    """
    import re

    path = require("eurostat.codelist.acl00")
    xml = path.read_text(encoding="utf-8", errors="replace")
    out: dict[str, str] = {}
    for cid, body in re.findall(r'<\w+:Code id="([^"]+)"[^>]*>(.*?)</\w+:Code>', xml, re.S):
        names = re.findall(r'<\w+:Name xml:lang="en">([^<]+)<', body)
        if names:
            out[cid] = names[0]
    if not out:
        raise RuntimeError(
            f"{path} parsed to no codes. The codelist's element names have "
            f"changed; fix the parser rather than falling back to literals."
        )
    return out


def mapping_audit() -> list[dict[str, Any]]:
    """Every modelled activity beside the official label of the code it uses.

    Returned rather than printed so a test can assert on it.  An unknown code
    is a hard error: a code that is not in the codelist cannot be in the data
    either, so the target it produces would be silently absent.
    """
    labels = acl00_labels()
    rows: list[dict[str, Any]] = []
    unknown: list[str] = []
    for name, spec in sorted(ACTIVITY_CODES.items()):
        for code, weight in spec["hetus"]:
            label = labels.get(code)
            if label is None:
                unknown.append(f"{name} -> {code}")
            rows.append(
                {
                    "activity": name,
                    "hetus_code": code,
                    "weight": float(weight),
                    "official_label": label,
                    "declared_label": str(spec["label"]),
                    "is_declared_assumption": float(weight) not in (1.0, -1.0),
                    "zone": str(spec["zone"]),
                }
            )
    if unknown:
        raise RuntimeError(
            "these modelled activities use HETUS codes that are not in "
            f"Eurostat's ACL00 codelist: {unknown}. A code that does not exist "
            f"yields no target and the activity silently never happens."
        )
    return rows
