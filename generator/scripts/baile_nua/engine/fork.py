"""Intervention replay by forking, with common random numbers (design 8.2).

Design 8.2 names three kinds of replay and gives each a different guarantee:

    ================================  ====================================
    Observation replay                byte-identical
    Intervention replay               deterministic given the fork point
                                      and the intervention log
    Counterfactual comparison         paired differences with reported
                                      variance, using common random numbers
                                      for draws the intervention can't affect
    ================================  ====================================

and then one rule that is easy to read past:

    The replay API refuses to present an isolated single-household replay as a
    town-wide counterfactual. **Any intervention forces a town fork.**

That refusal is the substance of this module. A single-household fork is
cheap - one home, one day, no coupling - and it is exactly what a tired
researcher would reach for to estimate a town-wide effect. It would be wrong
for a reason that does not announce itself: the home's own load would respond
correctly while every coupled quantity around it - the feeder, the venue
occupancy, the later events, the neighbours' prices - stayed at its baseline
value, so the estimate would miss precisely the general-equilibrium part the
intervention was interesting for. So :func:`counterfactual` raises
:class:`ReplayRefused` rather than returning a number with a caveat attached.

**What common random numbers actually buy, and where they stop.** The
counter-based tree keys every draw on (master seed, stream, entity, sim_day,
draw), and holds no mutable state. So the same coordinate yields the same
number in any fork, for free - there is nothing to synchronise. The useful
question is therefore not whether the numbers are common but whether the same
COORDINATES are visited. An intervention that changes how many draws a
household takes shifts that household's later draw indices, and from there its
stream is decoupled from the baseline's even though every individual number
still matches. Other households are untouched, because the entity is part of
the key.

:func:`crn_audit` measures that instead of assuming it: it records the
coordinates each fork visits and reports which entities are paired and which
decoupled. :func:`counterfactual` then computes the paired statistic over the
paired entities only, and reports the decoupled ones separately rather than
averaging the two together - which would quietly mix a low-variance paired
estimate with a high-variance unpaired one and report the small variance.
"""

from __future__ import annotations

import dataclasses
import math
from typing import Any, Callable, Iterable, Sequence

import numpy as np

from baile_nua.checkpoint import Checkpoint, CheckpointStore
from baile_nua.hashing import hash_json
from baile_nua.rng import SeedTree, Stream

__all__ = [
    "Intervention",
    "Fork",
    "ReplayRefused",
    "DrawRecorder",
    "RecordingSeedTree",
    "fork_town",
    "fork_household",
    "counterfactual",
    "crn_audit",
    "observation_replay_is_byte_identical",
    "TOWN_SCOPE",
    "HOUSEHOLD_SCOPE",
]

TOWN_SCOPE = "town"
HOUSEHOLD_SCOPE = "household"


class ReplayRefused(RuntimeError):
    """The API refused to present a replay as something it cannot support."""


@dataclasses.dataclass(frozen=True)
class Intervention:
    """One entry of the intervention log."""

    intervention_id: str
    kind: str                       # tariff | setpoint | asset | control | event
    from_sim_day: int
    parameters: dict[str, Any]
    #: Entities the intervention acts on. Everything NOT named here keeps its
    #: baseline draw coordinates, which is what makes CRN worth having.
    touches_entities: tuple[str, ...] = ()
    #: Streams whose draw COUNT the intervention may change. A stream listed
    #: here is expected to decouple for the entities above; one not listed
    #: that decouples anyway is a finding, not noise.
    may_change_draw_count_in: tuple[str, ...] = ()

    def content_hash(self) -> str:
        return hash_json({
            "intervention_id": self.intervention_id,
            "kind": self.kind,
            "from_sim_day": self.from_sim_day,
            "parameters": self.parameters,
            "touches_entities": list(self.touches_entities),
            "may_change_draw_count_in": list(self.may_change_draw_count_in),
        })


@dataclasses.dataclass
class Fork:
    """A re-simulation branched from a checkpoint."""

    fork_id: str
    parent_run_id: str
    fork_at_sim_day: int
    #: The chain hash of the checkpoint forked from. This is what makes the
    #: fork reproducible: it commits to the exact state, not to a day number.
    parent_chain_hash: str
    scope: str
    intervention: Intervention | None
    entities: tuple[str, ...]

    @property
    def is_town_wide(self) -> bool:
        return self.scope == TOWN_SCOPE

    def content_hash(self) -> str:
        return hash_json({
            "parent_run_id": self.parent_run_id,
            "fork_at_sim_day": self.fork_at_sim_day,
            "parent_chain_hash": self.parent_chain_hash,
            "scope": self.scope,
            "intervention": (
                None if self.intervention is None
                else self.intervention.content_hash()
            ),
            "entities": sorted(self.entities),
        })


# --------------------------------------------------------------------------- #
# recording which draw coordinates a run visits
# --------------------------------------------------------------------------- #

@dataclasses.dataclass
class DrawRecorder:
    """The set of (stream, entity, sim_day, draw) coordinates a run visited."""

    coordinates: set[tuple[str, str, int, int]] = dataclasses.field(
        default_factory=set
    )

    def record(self, stream: Stream, entity: Any, sim_day: int, draw: int) -> None:
        self.coordinates.add((stream.name, str(entity), int(sim_day), int(draw)))

    def by_entity(self) -> dict[str, set[tuple[str, int, int]]]:
        out: dict[str, set[tuple[str, int, int]]] = {}
        for stream, entity, day, draw in self.coordinates:
            out.setdefault(entity, set()).add((stream, day, draw))
        return out

    def streams(self) -> set[str]:
        return {c[0] for c in self.coordinates}


class RecordingSeedTree:
    """A :class:`SeedTree` that logs every coordinate it is asked for.

    Wrapping rather than subclassing: ``SeedTree`` uses ``__slots__`` and holds
    no mutable state on purpose, and adding a mutable recorder to it would
    make the thing that is safe to share across workers no longer safe. The
    wrapper is used only in replay and audit, never in a production run.
    """

    def __init__(self, master_seed: int, recorder: DrawRecorder) -> None:
        self._tree = SeedTree(master_seed)
        self.recorder = recorder
        self.master_seed = master_seed

    def generator(
        self, stream: Stream, entity: int | str = 0, sim_day: int = 0,
        draw: int = 0,
    ) -> Any:
        self.recorder.record(stream, entity, sim_day, draw)
        return self._tree.generator(stream, entity=entity, sim_day=sim_day,
                                    draw=draw)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._tree, name)


# --------------------------------------------------------------------------- #
# forking
# --------------------------------------------------------------------------- #

def _checkpoint_at(store: CheckpointStore, sim_day: int) -> Checkpoint:
    # ``get`` raises rather than returning None when the day is absent, so the
    # missing-day case is translated into the module's own refusal: a caller
    # that asked to fork a day that was never simulated should be told that,
    # not handed an OSError from two layers down.
    try:
        return store.get(sim_day)
    except (FileNotFoundError, OSError, KeyError) as exc:
        raise ReplayRefused(
            f"there is no checkpoint for day {sim_day}, so nothing can be "
            f"forked from it. A fork commits to a state, not to a date. "
            f"({type(exc).__name__})"
        ) from exc


def fork_town(
    *,
    store: CheckpointStore,
    sim_day: int,
    intervention: Intervention | None,
    fork_id: str,
    entities: Sequence[str] | None = None,
) -> Fork:
    """Fork the whole coupled town at a checkpoint (design 8.2).

    The whole town, because every coupled state downstream has to be
    re-simulated: households, venues, network and later events.
    """
    cp = _checkpoint_at(store, sim_day)
    if intervention is not None and intervention.from_sim_day < sim_day:
        raise ReplayRefused(
            f"the intervention starts on day {intervention.from_sim_day} but "
            f"the fork is at day {sim_day}: forking after an intervention has "
            f"already taken effect would put the intervention in the "
            f"BASELINE, and the comparison would measure nothing."
        )
    ids = tuple(entities) if entities is not None else tuple(
        sorted(set(cp.household_state) | set(cp.building_state))
    )
    return Fork(
        fork_id=fork_id, parent_run_id=cp.run_id, fork_at_sim_day=sim_day,
        parent_chain_hash=cp.chain_hash(), scope=TOWN_SCOPE,
        intervention=intervention, entities=ids,
    )


def fork_household(
    *, store: CheckpointStore, sim_day: int, household_id: str, fork_id: str,
    intervention: Intervention | None = None,
) -> Fork:
    """Fork one household. Legitimate for inspection; refused for inference.

    This exists because a single-household replay is genuinely useful - to see
    what one home did, to debug one day. What it may not do is stand in for a
    town-wide counterfactual, and :func:`counterfactual` enforces that.
    """
    cp = _checkpoint_at(store, sim_day)
    if household_id not in cp.household_state:
        raise ReplayRefused(
            f"day {sim_day}'s checkpoint has no household {household_id!r}"
        )
    return Fork(
        fork_id=fork_id, parent_run_id=cp.run_id, fork_at_sim_day=sim_day,
        parent_chain_hash=cp.chain_hash(), scope=HOUSEHOLD_SCOPE,
        intervention=intervention, entities=(household_id,),
    )


# --------------------------------------------------------------------------- #
# the CRN audit
# --------------------------------------------------------------------------- #

def crn_audit(
    *, baseline: DrawRecorder, treated: DrawRecorder,
    intervention: Intervention,
) -> dict[str, Any]:
    """Which entities share their draw coordinates, and which decoupled.

    An entity is **paired** when both forks visited exactly the same
    coordinates for it: every draw it made is then literally the same number,
    and a difference between the forks is the intervention and nothing else.
    It is **decoupled** when the coordinate sets differ - the intervention
    changed how many draws it took - and a paired statistic over it would be
    comparing two different random sequences.
    """
    b, t = baseline.by_entity(), treated.by_entity()
    paired, decoupled, baseline_only, treated_only = [], [], [], []
    for e in sorted(set(b) | set(t)):
        if e not in t:
            baseline_only.append(e)
        elif e not in b:
            treated_only.append(e)
        elif b[e] == t[e]:
            paired.append(e)
        else:
            decoupled.append(e)

    touched = set(intervention.touches_entities)
    unexpected = [e for e in decoupled if e not in touched]
    declared_streams = set(intervention.may_change_draw_count_in)
    unexpected_streams = sorted(
        s for e in decoupled for s in
        {c[0] for c in (b.get(e, set()) ^ t.get(e, set()))}
        if s not in declared_streams
    )
    n_common = len(baseline.coordinates & treated.coordinates)
    n_total = len(baseline.coordinates | treated.coordinates)
    return {
        "n_entities": len(set(b) | set(t)),
        "paired": paired,
        "decoupled": decoupled,
        "baseline_only": baseline_only,
        "treated_only": treated_only,
        "n_paired": len(paired),
        "n_decoupled": len(decoupled),
        "common_coordinates": n_common,
        "total_coordinates": n_total,
        "crn_share": (n_common / n_total) if n_total else None,
        "decoupled_but_not_touched_by_the_intervention": unexpected,
        "undeclared_streams_that_changed_draw_count": unexpected_streams,
        "clean": not unexpected and not unexpected_streams,
        "note": (
            "An entity the intervention does not touch must stay paired. One "
            "that decouples anyway means a draw count changed somewhere the "
            "intervention log did not declare, and every paired statistic "
            "over it is then comparing two different random sequences while "
            "reporting the variance of one."
        ),
    }


# --------------------------------------------------------------------------- #
# the counterfactual
# --------------------------------------------------------------------------- #

def counterfactual(
    *,
    baseline: Fork,
    treated: Fork,
    outcome_baseline: dict[str, float],
    outcome_treated: dict[str, float],
    audit: dict[str, Any] | None = None,
    outcome_name: str = "annual_kwh",
) -> dict[str, Any]:
    """Paired differences with reported variance (design 8.2).

    Refuses, loudly, three ways a comparison can be meaningless:

    * either fork is not town-wide - the design's explicit rule;
    * the two forks are not from the same parent state, so they are not two
      branches of one history at all;
    * the baseline fork carries an intervention, which would make the
      "counterfactual" a comparison of two treatments.
    """
    for f, name in ((baseline, "baseline"), (treated, "treated")):
        if not f.is_town_wide:
            raise ReplayRefused(
                f"the {name} fork has scope {f.scope!r}. Design 8.2: the "
                f"replay API refuses to present an isolated single-household "
                f"replay as a town-wide counterfactual, because every coupled "
                f"quantity around that household - the feeder, the venues, "
                f"the later events - would stay at its baseline value, and "
                f"the estimate would miss exactly the coupled effect the "
                f"intervention was interesting for. Any intervention forces a "
                f"town fork."
            )
    if baseline.parent_chain_hash != treated.parent_chain_hash:
        raise ReplayRefused(
            f"the forks branch from different states "
            f"({baseline.parent_chain_hash[:12]} and "
            f"{treated.parent_chain_hash[:12]}), so their difference is not "
            f"the intervention: it also contains whatever made the states "
            f"differ."
        )
    if baseline.intervention is not None:
        raise ReplayRefused(
            f"the baseline fork carries intervention "
            f"{baseline.intervention.intervention_id!r}, so this compares two "
            f"treatments rather than a treatment against a counterfactual. "
            f"Say which it is and name both."
        )
    if treated.intervention is None:
        raise ReplayRefused(
            "the treated fork carries no intervention, so there is nothing to "
            "estimate the effect of."
        )

    paired_ids = (
        sorted(set(audit["paired"]) & set(outcome_baseline) & set(outcome_treated))
        if audit is not None
        else sorted(set(outcome_baseline) & set(outcome_treated))
    )
    diffs = np.array(
        [outcome_treated[e] - outcome_baseline[e] for e in paired_ids],
        dtype=float,
    )
    n = len(diffs)
    mean = float(diffs.mean()) if n else float("nan")
    sd = float(diffs.std(ddof=1)) if n > 1 else float("nan")
    se = sd / math.sqrt(n) if n > 1 else float("nan")

    unpaired_ids = (
        sorted(set(audit["decoupled"]) & set(outcome_baseline) & set(outcome_treated))
        if audit is not None else []
    )
    un = np.array(
        [outcome_treated[e] - outcome_baseline[e] for e in unpaired_ids],
        dtype=float,
    )

    return {
        "outcome": outcome_name,
        "baseline_fork": baseline.fork_id,
        "treated_fork": treated.fork_id,
        "intervention": treated.intervention.intervention_id,
        "intervention_hash": treated.intervention.content_hash(),
        "fork_at_sim_day": treated.fork_at_sim_day,
        "parent_chain_hash": treated.parent_chain_hash,
        "n_paired": n,
        "paired_mean_difference": mean,
        "paired_sd": sd,
        "paired_se": se,
        "paired_ci95": (
            [mean - 1.96 * se, mean + 1.96 * se] if n > 1 else None
        ),
        # Reported SEPARATELY, never pooled: averaging a low-variance paired
        # estimate with a high-variance unpaired one and quoting the paired
        # variance is how a counterfactual comes to overstate its precision.
        "n_unpaired": len(un),
        "unpaired_mean_difference": float(un.mean()) if len(un) else None,
        "unpaired_sd": float(un.std(ddof=1)) if len(un) > 1 else None,
        "pooling_note": (
            "Paired and unpaired entities are reported separately. The paired "
            "variance is small because common random numbers removed the "
            "shared noise; applying it to the unpaired entities would claim a "
            "precision that was never there."
        ),
        "crn": audit,
    }


def observation_replay_is_byte_identical(
    *, store: CheckpointStore, sim_day: int, digest_a: str, digest_b: str
) -> dict[str, Any]:
    """Observation replay's guarantee is byte-identical, not merely close.

    Thin on purpose: the measurement belongs to
    :mod:`baile_nua.bench.determinism`, which already replays home-days from
    checkpoint plus exchange log. What is added here is the statement of WHICH
    guarantee applies, so the three kinds of replay cannot be confused for one
    another at the call site.
    """
    cp = _checkpoint_at(store, sim_day)
    return {
        "kind": "observation replay",
        "guarantee": "byte-identical",
        "sim_day": sim_day,
        "chain_hash": cp.chain_hash(),
        "identical": digest_a == digest_b,
        "digest_a": digest_a,
        "digest_b": digest_b,
    }
