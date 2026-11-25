"""Design 7.8's threat model, which the design requires **before** U20.

Verbatim from the design: "**Threat model first** (required before U20 is
decided)". So this module is the threat model, written as data rather than
prose so that the inference tests in :mod:`baile_nua.privacy.inference` can be
checked against it — an attack that does not correspond to a declared attacker,
target and access level is an attack nobody argued for, and a declared attacker
with no attack is a gap in the evidence. :func:`unattacked_targets` reports the
second, and a test fails on it.

**What R09 already guarantees, and what it does not.** R09 is implemented as
"no occupancy, presence or person-level field is ever transmitted", and
``edge/export.py`` enforces it at schema level: only D19's declared fields are
assembled. The design is explicit that this is not enough — "aggregate energy
profiles are known to reveal presence and routines" — and that Baile Nua can
measure the residual risk because it holds the ground truth. That measurement
is what this package is for.

**The claim boundary, stated here and repeated in every result.** Design 7.8:
"Passing these tests does not establish privacy or GDPR compliance; it informs
the DPIA." So no result from this package may be reported as a privacy
guarantee, and :data:`CLAIM_BOUNDARY` travels with every artefact.

**AUC ≤ 0.60 is a screening threshold and not a pass mark**, which is the
design's own word for it: "AUC ≤ 0.60 stays only as a **screening**
threshold." A configuration that clears it still has to report precision and
recall at operational thresholds, advantage over the prior-only and
time-of-day baselines, leakage across repeated releases, and the utility cost
of each mitigation. A screening threshold cleared is not a configuration
approved.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "ATTACKER_CLASSES",
    "TARGET_INFORMATION",
    "OBSERVATION_DURATIONS",
    "ACCESS_LEVELS",
    "CONSEQUENCES",
    "SCREENING_AUC",
    "CLAIM_BOUNDARY",
    "threat_model",
    "unattacked_targets",
]

#: Design 7.8's screening threshold: occupancy-inference AUC at or below this,
#: at the **upper** 95% confidence bound, measured against a prior-only
#: baseline. The upper bound rather than the point estimate, because a wide
#: interval whose centre clears the line has not cleared it.
SCREENING_AUC = 0.60

CLAIM_BOUNDARY = (
    "Design 7.8: passing these tests does not establish privacy or GDPR "
    "compliance; it informs the DPIA. No result in this package is a privacy "
    "guarantee. Differential privacy is claimed only with a defined protected "
    "unit, privacy budget, composition across releases and measured utility "
    "loss - none of which is declared here, so DP is not claimed at all."
)

#: Design 7.8's three attacker classes, verbatim in substance.
ATTACKER_CLASSES: dict[str, dict[str, Any]] = {
    "operator_or_aggregator": {
        "description": (
            "a network operator or aggregator with routine data access"
        ),
        "sees": "every export from every home, continuously, as of right",
        "knows_in_advance": (
            "nothing household-specific beyond what the export carries, but "
            "has the whole population to learn population-level structure from"
        ),
        "modelled_as": (
            "an attacker trained on a DISJOINT set of homes and tested on the "
            "target homes. That split is the whole realism of this class: an "
            "operator learns what a household at home looks like from other "
            "households, not from the one it is attacking."
        ),
    },
    "holder_of_repeated_releases": {
        "description": "a party holding repeated releases",
        "sees": "the same homes across several release periods",
        "knows_in_advance": "the previous releases",
        "modelled_as": (
            "the same attacks run per release period, with the advantage "
            "accumulated across periods reported separately - design 7.8's "
            "'leakage across multiple periods and repeated releases'. A "
            "single-release result understates this attacker."
        ),
    },
    "informed_neighbour": {
        "description": (
            "an informed neighbour who knows the household's routine"
        ),
        "sees": "one home's export",
        "knows_in_advance": (
            "that household's typical routine - when they usually leave, "
            "roughly how many live there"
        ),
        "modelled_as": (
            "the TIME-OF-DAY baseline. A neighbour who knows the routine can "
            "already guess occupancy from the clock, so the quantity that "
            "matters for this class is the attack's advantage OVER that "
            "baseline, not its raw accuracy. An attack that scores 0.75 AUC "
            "where the clock alone scores 0.74 tells this attacker nothing."
        ),
    },
}

#: Design 7.8's target information.
TARGET_INFORMATION: dict[str, dict[str, Any]] = {
    "occupancy_now": {
        "description": "is anyone at home in this interval",
        "attack": "occupancy_classifier",
        "screening_threshold": SCREENING_AUC,
        "why_it_matters": "the live question; R09 exists because of it",
    },
    "absence_period": {
        "description": "is the household away for a run of days (a holiday)",
        "attack": "holiday_detector",
        "screening_threshold": None,
        "why_it_matters": (
            "burglary timing. A single interval misread matters little; a "
            "correctly identified fortnight matters a great deal, so this is "
            "scored per EPISODE and not per interval."
        ),
    },
    "household_size": {
        "description": "how many people live here",
        "attack": "household_size_estimator",
        "screening_threshold": None,
        "why_it_matters": "profiling; also an attribute-inference target",
    },
    "routine_change": {
        "description": (
            "has this household's routine changed - someone moved in or out, "
            "a job changed, a person became ill"
        ),
        "attack": "routine_change_detector",
        "screening_threshold": None,
        "why_it_matters": (
            "inference about the people in the home, and the change-detection "
            "task the whole dataset exists to support - so a high score here "
            "is simultaneously the dataset working and a privacy risk, and "
            "the two readings must be reported together"
        ),
    },
}

OBSERVATION_DURATIONS: dict[str, str] = {
    "one_day": "a single day's export",
    "one_month": "a release period",
    "years": "the full ten-year span",
}

ACCESS_LEVELS: dict[str, str] = {
    "single_export": "one release, one configuration",
    "linked_releases": (
        "several releases of the same homes, linkable by the meter-point id - "
        "which 6.4's meter-point keying makes possible BY DESIGN, since the "
        "opaque id stays with the property across occupants"
    ),
}

CONSEQUENCES: tuple[str, ...] = (
    "burglary timing, from a correctly identified absence period",
    "profiling, from household size and routine",
    "inference about the people in the home, from routine change",
)


def threat_model() -> dict[str, Any]:
    """The whole model as one record, for the artefact."""
    return {
        "design_ref": "7.8",
        "required_before": "U20 (export granularity decision)",
        "attacker_classes": ATTACKER_CLASSES,
        "target_information": TARGET_INFORMATION,
        "observation_durations": OBSERVATION_DURATIONS,
        "access_levels": ACCESS_LEVELS,
        "consequences": CONSEQUENCES,
        "screening_auc": SCREENING_AUC,
        "screening_is_not_a_pass_mark": (
            "Design 7.8's own word: 'AUC <= 0.60 stays only as a SCREENING "
            "threshold'. Clearing it does not approve a configuration; the "
            "configuration must also report precision and recall at "
            "operational thresholds, advantage over the prior-only and "
            "time-of-day baselines, leakage across repeated releases, "
            "membership and attribute inference where relevant, and the "
            "utility cost of each mitigation."
        ),
        "what_r09_guarantees": (
            "No occupancy, presence or person-level field is transmitted, "
            "enforced at schema level by edge/export.py, which assembles only "
            "D19's declared fields. The design is explicit that this is not "
            "sufficient, because an aggregate energy profile reveals presence "
            "and routine anyway."
        ),
        "claim_boundary": CLAIM_BOUNDARY,
    }


def unattacked_targets(attacks_run: tuple[str, ...]) -> list[str]:
    """Declared targets that no attack addressed.

    A threat model is only evidence if every target it names was actually
    attacked. Without this, a target could be declared, never tested, and the
    threat model would read as though it had been covered.
    """
    return sorted(
        name for name, spec in TARGET_INFORMATION.items()
        if spec["attack"] not in attacks_run
    )
