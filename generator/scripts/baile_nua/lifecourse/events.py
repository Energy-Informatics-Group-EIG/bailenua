"""Life events and disruptions, S05 (design 5.9, 5.3, R08, R17; D09, D20).

E1 needs "at least one life event and one disruption" (E0-7), and the design
names the one that matters:

    **Mary's case** is a built-in test scenario.  Mary works 9 to 5 on weekdays
    and her EV unplugs about 08:00 and plugs back in about 17:00.  On a dated
    event, her daughter's family of four moves in.  Ground truth records the
    move, the new routines and the changed load; the edge detector must find it
    (section 5.12).

So this module provides the hooks and the Mary scenario, and - importantly -
the **D20 change labels** that make the event scoreable.  Design 5.12 is
explicit that Baile Nua detects nothing itself: its job is "to provide the
observable inputs and the labelled ground truth so that BNIT can score
detectors".

**What a D20 label must and must not say** (R25):

    The detector reports what changed in observable behaviour ("occupied-hours
    pattern consistent with 3 to 5 occupants"), never a cause ("a family moved
    in").

So every label carries an ``observable_change_text`` written in those terms, and
:func:`check_label_text` refuses a label whose text names a cause - because a
benchmark that rewards guessing causes is risk K13, and the cheapest way to
create it is to write the answer into the label.
"""

from __future__ import annotations

import dataclasses
import re
from typing import Any

import numpy as np

from baile_nua.rng import SeedTree, Stream

__all__ = [
    "LifeEvent",
    "Disruption",
    "ChangeLabel",
    "DISRUPTION_KINDS",
    "mary_scenario",
    "draw_disruptions",
    "check_label_text",
    "CAUSAL_WORDS",
    "CausalLabelRefused",
]


@dataclasses.dataclass
class LifeEvent:
    """A D09 row."""

    event_id: str
    event_type: str
    effective_day: int
    decided_day: int | None
    persons: list[str]
    household_id: str | None
    building_id: str | None
    cause: str
    observable_effects: dict[str, Any]


@dataclasses.dataclass
class Disruption:
    """A short perturbation to a household's day (design 5.3, R17)."""

    disruption_id: str
    kind: str
    person_id: str | None
    household_id: str
    start_day: int
    end_day: int
    detail: dict[str, Any] = dataclasses.field(default_factory=dict)

    def active_on(self, sim_day: int) -> bool:
        return self.start_day <= sim_day <= self.end_day


@dataclasses.dataclass
class ChangeLabel:
    """A D20 row: ground truth for detector scoring, never shown to a model."""

    label_id: str
    building_id: str
    change_class: str            # safety | equipment | routine deviation | structural
    true_onset_day: int
    true_end_day: int | None
    persistence: str             # transient | persistent | permanent
    source_event_ids: list[str]
    detectable_from_tier: str
    observable_change_text: str


#: The disruption kinds R17 names, with their hazards and durations.
#: Rates are declared assumptions [A]: design 5.3 gives no numbers and the
#: acceptance test (design 12 R17) is that "rates [are] within cited ranges",
#: which WP1 supplies.
DISRUPTION_KINDS: dict[str, dict[str, Any]] = {
    "illness": {
        # PRIMARY episodes only. Survey figures for acute illness already count
        # illnesses caught from a household member, so adding contagion on top
        # of a 2.6 total double-counts: the first version did exactly that and
        # produced 32.5 illness days per person per year against a real 8 to 12.
        # The primary rate plus the transmission below lands back near 2.6
        # episodes per person per year in total.
        "per_person_per_year": 2.0,
        "duration_days": (2, 7),
        # Chance that ONE other household member catches it, not an independent
        # draw per member - which compounded in a four-person household.
        "contagious_within_household": 0.30,
        "seasonal_peak_month": 1,
        "seasonal_amplitude": 0.7,
        "effect": "home-bound, more sleep, higher setpoint",
    },
    "remote_work": {
        "per_worker_per_year": 18.0,
        "duration_days": (1, 2),
        "effect": "at home on a weekday; the morning peak flattens",
    },
    "appliance_failure": {
        "per_household_per_year": 0.45,
        "duration_days": (3, 21),
        "effect": "the appliance stops; a workaround load may appear elsewhere",
    },
    "unplanned_visitors": {
        "per_household_per_year": 11.0,
        "duration_days": (1, 1),
        "effect": "extra occupants for part of a day; cooking and hot water rise",
    },
}

#: Words that must not appear in a D20 label's observable text (R25, K13).
CAUSAL_WORDS: tuple[str, ...] = (
    "moved in", "moved out", "move-in", "family", "daughter", "son", "baby",
    "born", "birth", "died", "death", "divorce", "separated", "retired",
    "lost her job", "lost his job", "new job", "ill", "illness", "sick",
    "holiday", "away on", "bought", "installed a", "pregnan",
)


class CausalLabelRefused(ValueError):
    """A D20 label names a cause instead of an observable change (R25)."""


def check_label_text(text: str) -> str:
    """Refuse a label that names a cause rather than an observable change.

    R25: "Detection infers behaviour, not causes."  A label that says "a family
    moved in" turns the benchmark into a cause-guessing game, which risk K13
    names directly.  Checked mechanically, because the temptation to write the
    obvious thing is strongest exactly when the cause is obvious.

    Matching is on **whole words**, not substrings. The first version matched
    substrings and refused a perfectly good label because "person" contains
    "son" - a check that cries wolf gets switched off, which would be worse than
    not having it.
    """
    low = text.lower()
    hits = [
        w for w in CAUSAL_WORDS
        if re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", low)
    ]
    if hits:
        raise CausalLabelRefused(
            f"D20 label text names a cause ({hits}): {text!r}. R25 requires the "
            f"label to describe what changed in OBSERVABLE behaviour - for "
            f"example 'occupied-hours pattern consistent with 3 to 5 occupants' "
            f"- and never why."
        )
    return text


def mary_scenario(
    *,
    household_id: str,
    building_id: str,
    mary_person_id: str,
    incoming_person_ids: list[str],
    move_in_day: int,
    decided_day: int | None = None,
) -> tuple[LifeEvent, list[ChangeLabel]]:
    """The design's built-in test scenario (5.9), with its D20 labels.

    One life event and **four** labels, because one event produces several
    separately detectable changes at different tiers and latencies - which is
    the point of design 5.12's tier table and what a detector benchmark needs.

    The labels describe observable change only; the event itself records the
    cause, in D09, which is ground truth and goes to the scoring API alone.
    """
    if len(incoming_person_ids) != 4:
        raise ValueError(
            f"the Mary scenario is 'her daughter's family of four'; got "
            f"{len(incoming_person_ids)} incoming persons"
        )
    event = LifeEvent(
        event_id=f"LE-{household_id}-MARY-MOVEIN",
        event_type="move in",
        effective_day=move_in_day,
        decided_day=decided_day if decided_day is not None else max(move_in_day - 45, 0),
        persons=list(incoming_person_ids),
        household_id=household_id,
        building_id=building_id,
        cause=(
            "design 5.9 built-in test scenario: Mary's daughter's family of four "
            "moves in on a dated event"
        ),
        observable_effects={
            "occupancy": "1 occupant becomes 5",
            "hot_water": "shower and hot-water draws rise sharply",
            "laundry": "washer and dryer cycles rise several-fold",
            "evening_load": "cooking and screen load rise and shift later",
            "weekday_daytime": "the house is no longer empty 09:00 to 17:00",
            "ev": "Mary's EV pattern (unplug ~08:00, plug ~17:00) is unchanged, "
                  "so the EV signature persists while everything around it changes",
        },
    )

    labels = [
        ChangeLabel(
            label_id=f"CL-{household_id}-STRUCT-01",
            building_id=building_id,
            change_class="structural",
            true_onset_day=move_in_day,
            true_end_day=None,
            persistence="permanent",
            source_event_ids=[event.event_id],
            detectable_from_tier="T1",
            observable_change_text=check_label_text(
                "Occupied-hours pattern consistent with 3 to 5 occupants where it "
                "was previously consistent with 1; weekday daytime load no longer "
                "falls to a near-constant baseline"
            ),
        ),
        ChangeLabel(
            label_id=f"CL-{household_id}-EQUIP-01",
            building_id=building_id,
            change_class="equipment",
            true_onset_day=move_in_day,
            true_end_day=None,
            persistence="persistent",
            source_event_ids=[event.event_id],
            detectable_from_tier="T2",
            observable_change_text=check_label_text(
                "Wet-appliance cycle count per week rises by a factor of three or "
                "more, with no new appliance signature appearing"
            ),
        ),
        ChangeLabel(
            label_id=f"CL-{household_id}-ROUTINE-01",
            building_id=building_id,
            change_class="routine deviation",
            true_onset_day=move_in_day,
            true_end_day=move_in_day + 20,
            persistence="transient",
            source_event_ids=[event.event_id],
            detectable_from_tier="T1",
            observable_change_text=check_label_text(
                "Evening peak shifts later by 30 to 60 minutes and broadens during "
                "the first three weeks, then stabilises"
            ),
        ),
        ChangeLabel(
            label_id=f"CL-{household_id}-STRUCT-02",
            building_id=building_id,
            change_class="structural",
            true_onset_day=move_in_day,
            true_end_day=None,
            persistence="permanent",
            source_event_ids=[event.event_id],
            detectable_from_tier="T3",
            observable_change_text=check_label_text(
                "Hot-water draw events per day rise from one to four or more, and "
                "bedroom CO2 overnight rises to a level consistent with more than "
                "one person sleeping there"
            ),
        ),
    ]
    return event, labels


def draw_disruptions(
    *,
    household_id: str,
    person_ids: list[str],
    worker_ids: list[str],
    seed_tree: SeedTree,
    year_days: int,
    month_of_day: list[int],
) -> list[Disruption]:
    """Draw a year of disruptions for one household (design 5.3, R17).

    Illness is **seasonal and contagious within the household**, which is what
    design 5.3 asks for and what makes it more than independent noise: one
    person's illness raises the household's load for a week and may be followed
    by another's, which is a correlated multi-day signature rather than a blip.
    """
    gen = seed_tree.generator(Stream.DISRUPTION, entity=household_id, sim_day=0)
    hgen = seed_tree.generator(Stream.HEALTH_STATE, entity=household_id, sim_day=0)
    out: list[Disruption] = []
    counter = 0

    def add(kind: str, person: str | None, start: int, length: int, detail: dict) -> None:
        nonlocal counter
        counter += 1
        out.append(
            Disruption(
                disruption_id=f"DIS-{household_id}-{counter:03d}",
                kind=kind, person_id=person, household_id=household_id,
                start_day=start, end_day=min(start + length - 1, year_days - 1),
                detail=detail,
            )
        )

    # ---- illness, seasonal, with household transmission ------------------
    spec = DISRUPTION_KINDS["illness"]
    for pid in sorted(person_ids):
        n = int(gen.poisson(spec["per_person_per_year"]))
        for _ in range(n):
            # Seasonal: a cosine peaking in the named month.
            for _try in range(40):
                day = int(gen.integers(0, year_days))
                month = month_of_day[day]
                phase = 2.0 * np.pi * (month - spec["seasonal_peak_month"]) / 12.0
                accept = (1.0 + spec["seasonal_amplitude"] * np.cos(phase)) / (
                    1.0 + spec["seasonal_amplitude"]
                )
                if float(gen.random()) < accept:
                    break
            lo, hi = spec["duration_days"]
            length = int(gen.integers(lo, hi + 1))
            add("illness", pid, day, length, {"effect": spec["effect"]})
            # Contagion: ONE other household member may follow a few days
            # later. Design 5.3 asks for illness to be "contagious within
            # households", which is about CLUSTERING in time - a correlated
            # multi-day signature the detector can see - rather than about
            # multiplying the household's total illness burden.
            others = sorted(p for p in person_ids if p != pid)
            if others and float(hgen.random()) < spec["contagious_within_household"]:
                other = others[int(hgen.integers(0, len(others)))]
                delay = int(hgen.integers(1, 5))
                add(
                    "illness", other, min(day + delay, year_days - 1),
                    int(hgen.integers(lo, hi + 1)),
                    {"effect": spec["effect"], "contagion_from": pid},
                )

    # ---- remote-work days ------------------------------------------------
    spec = DISRUPTION_KINDS["remote_work"]
    for pid in sorted(worker_ids):
        n = int(gen.poisson(spec["per_worker_per_year"]))
        for _ in range(n):
            day = int(gen.integers(0, year_days))
            add("remote_work", pid, day, 1, {"effect": spec["effect"]})

    # ---- appliance failure ------------------------------------------------
    spec = DISRUPTION_KINDS["appliance_failure"]
    for _ in range(int(gen.poisson(spec["per_household_per_year"]))):
        day = int(gen.integers(0, year_days))
        lo, hi = spec["duration_days"]
        appliance = str(
            gen.choice(["washing_machine", "tumble_dryer", "dishwasher",
                        "fridge_freezer", "immersion_heater"])
        )
        add(
            "appliance_failure", None, day, int(gen.integers(lo, hi + 1)),
            {"appliance": appliance, "effect": spec["effect"],
             "workaround": "laundrette run" if appliance in
                           ("washing_machine", "tumble_dryer") else "manual alternative"},
        )

    # ---- unplanned visitors ----------------------------------------------
    spec = DISRUPTION_KINDS["unplanned_visitors"]
    for _ in range(int(gen.poisson(spec["per_household_per_year"]))):
        day = int(gen.integers(0, year_days))
        add(
            "unplanned_visitors", None, day, 1,
            {"n_visitors": int(gen.integers(1, 5)), "effect": spec["effect"]},
        )

    out.sort(key=lambda d: (d.start_day, d.disruption_id))
    return out
