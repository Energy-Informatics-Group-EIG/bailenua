"""The linked Baile Nua panel, in survey waves across the decade (I-075).

Design WP-M2: *"Every adult who would plausibly respond completes repeated
sessions **in survey waves across the 10 simulated years**.  At 8 to 15 sessions
each ... Every answer links to that person's simulated behaviour."*

Before this module, :class:`baile_nua.mimic.runner.MimicRunner` accepted a
``simulated_session_date`` and nothing ever passed one, so the panel was a single
undated snapshot: an answer could be joined to *that person* and not to *that
person at that moment* (I-075).  This module is the caller and the schedule that
I-075 says is missing.

What it does **not** do, and why
--------------------------------

**It does not give a wave a stable MIMIC ``participant_id``.**  MIMIC's
``JourneyService::state`` returns ``next = 'summary'`` once a participant has one
completed session and a completed MCV block, and ``api/session.php`` refuses
``action=create`` unless ``next === 'decide'``:

    JsonResponse::fail('JOURNEY', 'Complete prior steps before starting a
                        session', 403);

So **the public API permits exactly one session per participant**, and a second
wave for the same person cannot be a second session on the same participant
record without a MIMIC change.  Recorded as I-087 (REPORT-TO-MIMIC) rather than
patched here, because design 5.14 level 3 binds the runner to MIMIC's public API
and the brief forbids editing MIMIC silently.

The consequence, and the mitigation: each wave is a separate MIMIC participant
record, and the **person** is the unit that recurs.  D26 carries
``person_id`` + ``simulated_session_date``, so a panel analysis groups by
``person_id`` and orders by date and does see change over time - which is the
question I-075 says the dataset exists for.  What it cannot do is follow a
MIMIC participant id across waves, and nothing in the artefact pretends it can:
the counters count **respondents**, never sessions, which is the rule the E1
report already states ("repeated sessions never count as unique participants").

**It does not evolve anything the frozen model does not publish.**  The frozen
t0 population (``synthesise_t0(master_seed=20261008)``) is a snapshot at
2022-01-01 and the ten-year life course on disk
(``v1/evidence/wp5_tenyear.json``) is a 60-home slice with aggregate counts, not
a per-person state series for all 2,917 people.  So what varies by wave here is
only what the frozen snapshot itself determines at a later date:

* ``age`` and therefore ``age_band``, from ``birth_date``;
* ``children_present``, as the household's own children age past 18;
* eligibility, as a 16-year-old at t0 becomes an adult mid-decade;
* and every **answer**, because the willingness generator is addressed by
  ``(person, wave)`` in the seed tree.

Economic status, dwelling, tenure and household size are carried from the t0
state because the frozen model publishes no per-person decade series for them.
That is a stated limitation of this panel, not a claim.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from typing import Any, Iterable

import numpy as np
import pandas as pd

from baile_nua.mimic import crosswalk
from baile_nua.mimic.extended_pool import PoolPerson
from baile_nua.population import traits as traits_mod
from baile_nua.rng import SeedTree, Stream

__all__ = [
    "PanelPerson",
    "WAVE_CALENDAR_START",
    "WAVE_CALENDAR_END",
    "N_WAVES",
    "MIN_SESSIONS",
    "MAX_SESSIONS",
    "PANEL_STRATUM",
    "wave_calendar",
    "build_panel",
    "panel_summary",
]

#: The decade the ten-year life course covers (``v1/evidence/wp5_tenyear.json``
#: reports ``span = "2022-2031"``), which is also the population's t0 year.
WAVE_CALENDAR_START = dt.date(2022, 1, 1)
WAVE_CALENDAR_END = dt.date(2031, 12, 31)

#: Fifteen waves, one every eight months, so that the design's "8 to 15
#: sessions each" is a *subset of a common wave calendar* rather than fifteen
#: private schedules.  A panel's waves are shared by construction: that is what
#: makes a wave comparison between people meaningful.
N_WAVES = 15
MIN_SESSIONS = 8
MAX_SESSIONS = 15

#: Not one of :mod:`baile_nua.mimic.extended_pool`'s three unlinked strata.
PANEL_STRATUM = "baile_nua_panel"

#: The fieldwork window of one wave, in days.  A real wave is not one evening.
FIELDWORK_WINDOW_DAYS = 28

#: MIMIC's ``work_pattern`` value set has no value for "not in employment", so
#: every person who is not working has to be mapped onto one of the four it
#: does have.  Recorded as a U18-class information loss per participant rather
#: than hidden in a dictionary literal (the same treatment as
#: ``HOME_DUTIES_MAPPED_TO`` and ``TERRACED_MAPPED_TO``).
NOT_WORKING_WORK_PATTERN_MAPPED_TO = "Irregular"

#: D02 (the frozen building frame) carries ``heating_system`` but no PV, battery
#: or EV column, so the panel's ``der_ownership`` can only report the heat pump
#: it does know about.  The unlinked pool draws PV/Battery/EV from marginals;
#: the panel does not invent them.
DER_FIELDS_NOT_IN_D02 = ("PV", "Battery", "EV")


@dataclasses.dataclass
class PanelPerson(PoolPerson):
    """One linked Baile Nua person at one wave.

    ``pool_person_id`` is ``"<person_id>-w<NN>"`` so that the seed tree
    addresses each wave separately and a person's answers differ between waves;
    ``linked_person_id`` is the population's own ``person_id``, which is what
    D26's crosswalk records and what a panel analysis groups by.
    """

    linked_person_id: str | None = None
    household_id: str | None = None
    building_id: str | None = None
    wave: int = 0
    n_waves: int = 0
    simulated_session_date: str | None = None
    #: Information MIMIC's value sets cannot carry for this participant, beyond
    #: the two gaps :class:`PoolPerson` already knows about.
    extra_information_lost: tuple[str, ...] = ()

    @property
    def u18_information_lost(self) -> list[str]:
        return list(super().u18_information_lost) + list(self.extra_information_lost)


def wave_calendar(
    *,
    n_waves: int = N_WAVES,
    start: dt.date = WAVE_CALENDAR_START,
    end: dt.date = WAVE_CALENDAR_END,
) -> list[dt.date]:
    """The shared wave calendar: ``n_waves`` nominal dates spanning the decade.

    Evenly spaced between ``start`` and ``end`` inclusive, so wave 1 opens the
    decade and wave ``n`` closes it.
    """
    if n_waves < 2:
        raise ValueError(f"a panel needs at least two waves; got {n_waves}")
    span = (end - start).days
    return [start + dt.timedelta(days=round(span * i / (n_waves - 1)))
            for i in range(n_waves)]


# --------------------------------------------------------------------------- #
# Mapping one frozen person onto MIMIC's value sets
# --------------------------------------------------------------------------- #

_TENURE_TO_MIMIC = {
    "owner-occupied with mortgage": "Owner",
    "owner-occupied no mortgage": "Owner",
    "rented private": "Renter",
    "rented social": "Social",
    "rent free": "Other",
    "not stated": "Other",
}

_WORK_PATTERN_TO_MIMIC = {
    "fixed day": "Office",
    "shift": "Shift",
    "irregular": "Irregular",
    "part-time": "Irregular",
}


def _traits_of(row: pd.Series) -> traits_mod.TraitVector:
    """Rebuild the person's frozen trait vector from the D05 row.

    The three self-reports MIMIC stores are *derived* rather than stored in
    D05, by MIMIC's own ``round(3 + 1.05 * latent)`` mapping
    (:func:`crosswalk.self_report_from_latent`), from the same latents
    :mod:`baile_nua.population.traits` used when it drew them.
    """
    mcv = row["mcv_latent"]
    return traits_mod.TraitVector(
        trans=float(row["trans"]),
        community=float(row["community"]),
        env=float(row["env"]),
        autonomy=float(row["autonomy"]),
        comfort=float(row["comfort"]),
        conditional=float(row["conditional"]),
        privacy=float(row["privacy"]),
        instTrust=float(row["instTrust"]),
        idvZ=float(row["idvZ"]),
        satisficer=int(row["satisficer"]),
        lambda_self=float(row["lambda_self"]),
        lambda_coop=float(row["lambda_coop"]),
        lambda_altru=float(row["lambda_altru"]),
        mcv_latent=[float(v) for v in (mcv if mcv is not None else [])],
        environmental_concern=crosswalk.self_report_from_latent(float(row["env"])),
        trust_in_automation=crosswalk.self_report_from_latent(float(row["autonomy"])),
        comfort_sensitivity=crosswalk.self_report_from_latent(float(row["comfort"])),
        stated_gap=float(row["stated_gap"]),
        response_propensity=float(row["response_propensity"]),
        big5_o=float(row["big5_o"]), big5_c=float(row["big5_c"]),
        big5_e=float(row["big5_e"]), big5_a=float(row["big5_a"]),
        big5_n=float(row["big5_n"]),
        chronotype=float(row["chronotype"]),
        habit_strength=float(row["habit_strength"]),
        lapse_rate=float(row["lapse_rate"]),
        attention=float(row["attention"]),
    )


def _age_on(birth_date: Any, on: dt.date) -> int:
    b = pd.Timestamp(birth_date).date()
    return on.year - b.year - ((on.month, on.day) < (b.month, b.day))


def _household_size_label(n: int) -> str:
    return "5+" if n >= 5 else str(max(n, 1))


# --------------------------------------------------------------------------- #
# Building the panel
# --------------------------------------------------------------------------- #

def build_panel(
    *,
    persons: pd.DataFrame,
    states: pd.DataFrame,
    membership: pd.DataFrame,
    buildings: pd.DataFrame,
    master_seed: int,
    n_waves: int = N_WAVES,
    min_sessions: int = MIN_SESSIONS,
    max_sessions: int = MAX_SESSIONS,
) -> tuple[list[PanelPerson], dict[str, Any]]:
    """Every adult who would plausibly respond, at each wave they answer.

    Returns the wave-level participants (sorted by person then wave, so the run
    order is a function of the input) and a diagnostics dictionary.

    Selection: *"every adult who would plausibly respond"* is read as a draw on
    the person's own ``response_propensity``, which is the field that exists for
    exactly this purpose and is what T5's self-selection test weights against.
    A person is in the panel if the draw succeeds **and** they are 18 or over at
    some wave: MIMIC has no age band below 18, so a minor cannot hold a profile.

    Number of sessions: ``min_sessions + Binomial(max-min, response_propensity)``,
    so a more willing person answers more waves and the panel has the
    differential non-response over time that a real one has.  The truth is
    recorded per participant in D26.
    """
    calendar = wave_calendar(n_waves=n_waves)
    tree = SeedTree(master_seed)

    persons = persons.set_index("person_id", drop=False)
    state_by_person = states.set_index("person_id", drop=False)
    # t0 membership: the frozen snapshot has one open row per person.
    memb = membership.sort_values("membership_id").drop_duplicates("person_id")
    memb_by_person = memb.set_index("person_id", drop=False)
    hh_size = memb.groupby("household_id")["person_id"].count().to_dict()
    hh_members = memb.groupby("household_id")["person_id"].apply(list).to_dict()
    bld = buildings.sort_values(["building_id", "version"]).drop_duplicates(
        "building_id", keep="last").set_index("building_id", drop=False)

    birth_of = {pid: pd.Timestamp(persons.at[pid, "birth_date"]).date()
                for pid in persons.index}

    people: list[PanelPerson] = []
    n_adults_ever = 0
    n_selected = 0
    sessions_by_person: dict[str, int] = {}
    waves_used: dict[int, int] = {}
    minor_waves_skipped = 0

    for person_id in sorted(persons.index):
        prow = persons.loc[person_id]
        if prow.get("death_date") is not None and not pd.isna(prow.get("death_date")):
            continue
        # 18+ at any wave in the calendar?
        if _age_on(birth_of[person_id], calendar[-1]) < 18:
            continue
        n_adults_ever += 1

        gen = tree.generator(Stream.MIMIC_POOL_PERSON, entity=person_id, sim_day=0)
        rp = float(prow["response_propensity"])
        if float(gen.random()) >= rp:
            continue              # would not plausibly respond
        n_selected += 1

        n_sessions = int(min_sessions + gen.binomial(max_sessions - min_sessions, rp))
        n_sessions = min(n_sessions, n_waves)
        # Wave 1 is recruitment; the rest are drawn without replacement so a
        # person's waves are a subset of the SHARED calendar.
        rest = sorted(
            int(i) for i in gen.choice(
                np.arange(1, n_waves), size=n_sessions - 1, replace=False
            )
        )
        wave_ixs = [0, *rest]

        try:
            srow = state_by_person.loc[person_id]
            mrow = memb_by_person.loc[person_id]
        except KeyError:                     # pragma: no cover - frozen pop has both
            continue
        household_id = str(mrow["household_id"])
        building_id = str(mrow["building_id"])
        brow = bld.loc[building_id] if building_id in bld.index else None

        econ = str(srow["econ_status"])
        wp_raw = str(srow["work_pattern"])
        remote_share = float(srow.get("remote_share") or 0.0)
        extra_lost: list[str] = []
        if remote_share >= 0.5:
            work_pattern = "Remote"
        elif wp_raw in _WORK_PATTERN_TO_MIMIC:
            work_pattern = _WORK_PATTERN_TO_MIMIC[wp_raw]
        else:
            work_pattern = NOT_WORKING_WORK_PATTERN_MAPPED_TO
            extra_lost.append(
                f"work_pattern: {wp_raw!r} (not in employment) -> "
                f"{NOT_WORKING_WORK_PATTERN_MAPPED_TO!r}; MIMIC's value set has "
                f"no value for a person who is not working"
            )

        dwelling = str(brow["dwelling_type"]) if brow is not None else "other"
        tenure = str(brow["tenure"]) if brow is not None else "not stated"
        heating = str(brow["heating_system"]) if brow is not None else ""
        der = ["HP"] if heating == "heat pump" else ["None"]
        extra_lost.append(
            "der_ownership: D02 carries no PV, battery or EV column, so only a "
            "heat pump can be reported for a linked participant"
        )

        tv = _traits_of(prow)
        size_label = _household_size_label(int(hh_size.get(household_id, 1)))
        members = hh_members.get(household_id, [person_id])

        for wave_ix in wave_ixs:
            nominal = calendar[wave_ix]
            jitter = int(gen.integers(0, FIELDWORK_WINDOW_DAYS))
            when = nominal + dt.timedelta(days=jitter)
            if when > WAVE_CALENDAR_END:
                when = WAVE_CALENDAR_END
            age = _age_on(birth_of[person_id], when)
            if age < 18:
                minor_waves_skipped += 1
                continue          # not yet an adult at this wave
            children = any(
                m != person_id and _age_on(birth_of[m], when) < 18 for m in members
            )
            wave_no = wave_ix + 1
            people.append(PanelPerson(
                pool_person_id=f"{person_id}-w{wave_no:02d}",
                stratum=PANEL_STRATUM,
                country="IE",
                nuts3="IE053",                       # Cobh
                urban_rural="Urban",
                sex=str(prow["sex"]),
                age=age,
                age_band=crosswalk.age_band_for(age),
                household_size=size_label,
                children_present="Yes" if children else "No",
                econ_status=econ,
                work_pattern=work_pattern,
                dwelling_type=dwelling,
                ownership_status=_TENURE_TO_MIMIC.get(tenure, "Other"),
                income_band=str(int(srow["income_quintile"])),
                education_level=str(prow["education_level"]),
                der_ownership=der,
                digital_access=("High" if tv.autonomy > 0.5
                                else "Medium" if tv.autonomy > -0.5 else "Low"),
                traits=tv,
                planted_segment=None,
                planted_null_mode=False,
                linked_person_id=person_id,
                household_id=household_id,
                building_id=building_id,
                wave=wave_no,
                n_waves=n_sessions,
                simulated_session_date=when.isoformat(),
                extra_information_lost=tuple(extra_lost),
            ))
            sessions_by_person[person_id] = sessions_by_person.get(person_id, 0) + 1
            waves_used[wave_no] = waves_used.get(wave_no, 0) + 1

    people.sort(key=lambda p: p.pool_person_id)
    counts = sorted(sessions_by_person.values())
    diagnostics = {
        "design_ref": "WP-M2; I-075",
        "n_persons_in_population": int(len(persons)),
        "n_adults_18_plus_at_some_wave": n_adults_ever,
        "n_selected_respondents": n_selected,
        "n_persons_with_at_least_one_wave": len(sessions_by_person),
        "n_wave_participants": len(people),
        "wave_calendar": [d.isoformat() for d in calendar],
        "n_waves_in_calendar": n_waves,
        "sessions_per_person": {
            "min": counts[0] if counts else 0,
            "median": counts[len(counts) // 2] if counts else 0,
            "max": counts[-1] if counts else 0,
            "mean": round(sum(counts) / len(counts), 2) if counts else 0.0,
        },
        "design_target_sessions_per_person": f"{min_sessions} to {max_sessions}",
        "participants_by_wave": dict(sorted(waves_used.items())),
        "waves_skipped_because_still_a_minor": minor_waves_skipped,
        "selection_rule": (
            "adults 18+ at some wave, selected by a draw on their own "
            "response_propensity; sessions = "
            f"{min_sessions} + Binomial({max_sessions - min_sessions}, "
            "response_propensity)"
        ),
        "simulated_session_date_span": (
            [people[0].simulated_session_date, people[-1].simulated_session_date]
            if people else []
        ),
        "mimic_limitation": (
            "MIMIC's public API allows one session per participant "
            "(JourneyService::state -> 'summary'), so each wave is a separate "
            "participant record and the recurring unit is person_id. I-087."
        ),
        "not_varying_by_wave": [
            "econ_status", "work_pattern", "dwelling_type", "ownership_status",
            "income_band", "household_size", "education_level",
        ],
        "varying_by_wave": ["age", "age_band", "children_present", "every answer"],
    }
    return people, diagnostics


def panel_summary(people: Iterable[PanelPerson]) -> dict[str, Any]:
    """Counts a test or a report can assert on without re-deriving them."""
    people = list(people)
    by_person: dict[str, list[str]] = {}
    for p in people:
        by_person.setdefault(str(p.linked_person_id), []).append(
            str(p.simulated_session_date)
        )
    years = sorted({d[:4] for ds in by_person.values() for d in ds})
    return {
        "n_wave_participants": len(people),
        "n_distinct_persons": len(by_person),
        "n_dated": sum(1 for p in people if p.simulated_session_date),
        "n_undated": sum(1 for p in people if not p.simulated_session_date),
        "years_covered": years,
        "min_sessions_per_person": min((len(v) for v in by_person.values()), default=0),
        "max_sessions_per_person": max((len(v) for v in by_person.values()), default=0),
    }
