"""The five MIMIC counters (design 5.14, E0-5 / U16).

    **Counters, reported separately and never merged:**
      * unique synthetic participants
      * completed sessions
      * completed responses
      * linked Baile Nua panel participants
      * unlinked extended-pool participants

    Repeated sessions never count as unique participants.  The E1 target of
    10,000 refers to unique participants.

The class refuses to add them up.  That is not pedantry: the obvious way to
report "10,000+" is to sum sessions and participants, which would let a few
hundred people taking many sessions each look like ten thousand people, and
design 5.14 forbids exactly that.
"""

from __future__ import annotations

import dataclasses
from typing import Any

__all__ = ["MimicCounters", "CounterMergeRefused"]


class CounterMergeRefused(TypeError):
    """Something tried to total the five counters (design 5.14)."""


@dataclasses.dataclass
class MimicCounters:
    unique_participants: int = 0
    completed_sessions: int = 0
    completed_responses: int = 0
    linked_panel_participants: int = 0
    unlinked_pool_participants: int = 0

    #: Not one of the five, but needed to show that the five are consistent.
    abandoned_sessions: int = 0
    rejected_forbidden_field_batches: int = 0

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        if self.linked_panel_participants + self.unlinked_pool_participants > self.unique_participants:
            raise ValueError(
                f"pool counts ({self.linked_panel_participants} linked + "
                f"{self.unlinked_pool_participants} unlinked) exceed unique "
                f"participants ({self.unique_participants}); the two pools "
                f"partition the participants and cannot overlap"
            )

    # -- the refusal ---------------------------------------------------------

    def __int__(self) -> int:
        raise CounterMergeRefused(
            "the five MIMIC counters are reported separately and never merged "
            "(design 5.14). Summing them would let repeated sessions inflate the "
            "participant count, which is the specific thing the design forbids. "
            "Use .as_dict() and report each."
        )

    def total(self) -> int:
        raise CounterMergeRefused(
            "there is no total. Design 5.14: 'Counters, reported separately and "
            "never merged'. The E1 target of 10,000 refers to unique "
            "participants only - use .unique_participants."
        )

    def __add__(self, other: Any) -> MimicCounters:
        """Adding two counter sets is legitimate (two batches); summing the
        five fields of one is not."""
        if not isinstance(other, MimicCounters):
            raise CounterMergeRefused(
                f"cannot add {type(other).__name__} to MimicCounters"
            )
        return MimicCounters(
            unique_participants=self.unique_participants + other.unique_participants,
            completed_sessions=self.completed_sessions + other.completed_sessions,
            completed_responses=self.completed_responses + other.completed_responses,
            linked_panel_participants=self.linked_panel_participants + other.linked_panel_participants,
            unlinked_pool_participants=self.unlinked_pool_participants + other.unlinked_pool_participants,
            abandoned_sessions=self.abandoned_sessions + other.abandoned_sessions,
            rejected_forbidden_field_batches=(
                self.rejected_forbidden_field_batches + other.rejected_forbidden_field_batches
            ),
        )

    def as_dict(self) -> dict[str, Any]:
        self._validate()
        return {
            "unique_synthetic_participants": self.unique_participants,
            "completed_sessions": self.completed_sessions,
            "completed_responses": self.completed_responses,
            "linked_baile_nua_panel_participants": self.linked_panel_participants,
            "unlinked_extended_pool_participants": self.unlinked_pool_participants,
            "_not_one_of_the_five": {
                "abandoned_sessions": self.abandoned_sessions,
                "rejected_forbidden_field_batches": self.rejected_forbidden_field_batches,
            },
            "_rule": (
                "Reported separately and never merged (design 5.14). The E1 "
                "target of 10,000 refers to unique participants. Repeated "
                "sessions never count as unique participants."
            ),
            "e1_target_unique_participants": 10000,
            "e1_target_met": self.unique_participants >= 10000,
        }

    def __str__(self) -> str:
        d = self.as_dict()
        lines = ["MIMIC counters (design 5.14, never merged):"]
        for key in (
            "unique_synthetic_participants", "completed_sessions",
            "completed_responses", "linked_baile_nua_panel_participants",
            "unlinked_extended_pool_participants",
        ):
            lines.append(f"  {key:<42} {d[key]:>8,}")
        lines.append(
            f"  E1 target (>= 10,000 unique participants):   "
            f"{'MET' if d['e1_target_met'] else 'NOT MET'}"
        )
        return "\n".join(lines)
