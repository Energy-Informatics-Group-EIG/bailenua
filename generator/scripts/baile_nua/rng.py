"""Counter-based RNG and seed tree (design 8.2, reproducibility contract).

The contract the design requires:

    A counter-based RNG (Philox) is keyed by master seed, stream, entity ID,
    simulated day and draw counter.  Results don't depend on execution order
    or worker count.

Implementation.  ``numpy.random.Philox`` is Philox-4x64-10: a 2x64-bit key and a
4x64-bit counter.  That maps onto the five required coordinates exactly:

===========================  ==============================================
Philox slot                  Baile Nua coordinate
===========================  ==============================================
``key[0]``, ``key[1]``       master seed, expanded to 128 bits by SplitMix64
``counter[0]``               stream id (a named, stable integer, never ad hoc)
``counter[1]``               entity id (person / building / household / asset)
``counter[2]``               simulated day (days since the run epoch)
``counter[3]``               draw counter (a sub-stream within the day)
===========================  ==============================================

Consequences, each of which is asserted in ``tests/test_determinism.py``:

* Every draw is addressable.  There is no "current state" to advance, so nothing
  depends on the order in which households, workers or days are visited.
* Two different entities, days or streams can never collide, because they occupy
  different counter words rather than different positions in one sequence.
* A stream is reproducible in isolation: ``substream()`` for one home-day can be
  rebuilt without replaying anything else, which is what ``replay()`` needs.

Streams are declared once in :class:`Stream`.  Passing a bare integer is refused,
because an ad-hoc stream number is the classic way two subsystems silently share a
sequence.
"""

from __future__ import annotations

import enum
from typing import Final

import numpy as np
from numpy.random import Generator, Philox

__all__ = ["Stream", "SeedTree", "splitmix64", "stable_entity_id"]

_MASK64: Final[int] = (1 << 64) - 1


def splitmix64(x: int) -> int:
    """SplitMix64 finaliser: expand a small seed into a well-mixed 64-bit word.

    Used only to turn a human-chosen master seed (for example 20261008) into key
    material with no structure.  It is not used for simulation draws.
    """
    x = (x + 0x9E3779B97F4A7C15) & _MASK64
    z = x
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & _MASK64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & _MASK64
    return (z ^ (z >> 31)) & _MASK64


class Stream(enum.IntEnum):
    """Named random streams.

    Every subsystem that draws randomness owns a stream here.  The integer values
    are part of the reproducibility contract: **changing one invalidates every
    checkpoint**, so values are appended, never renumbered or reused.
    """

    # -- static synthesis (S04, S03, S02) -------------------------------------
    POPULATION_SCALE_DOWN = 1
    POPULATION_IPF = 2
    HOUSEHOLD_ASSEMBLY = 3
    PERSON_DEMOGRAPHICS = 4
    PERSON_TRAITS = 5
    PERSON_NAMES = 6
    PERSON_BIG5 = 7
    BUILDING_FABRIC = 8
    BUILDING_SYSTEMS = 9
    APPLIANCE_STOCK = 10
    DER_STOCK = 11
    SENSOR_TIER = 12
    GEOGRAPHY = 13
    VEHICLE_STOCK = 14

    # -- slow loop (S05, S06) -------------------------------------------------
    LIFE_COURSE = 20
    HEALTH_STATE = 21
    DISRUPTION = 22
    CALENDAR_EVENT = 23
    EVENT_ATTENDANCE = 24

    # -- fast loop (S07, S08, S09, S10) ---------------------------------------
    ACTIVITY_SEQUENCE = 30
    ACTIVITY_DURATION = 31
    HOUSEHOLD_COUPLING = 32
    SHARED_RESOURCE_QUEUE = 33
    NEGOTIATION = 34
    LAPSE = 35
    WINDOW_OPENING = 36
    SETPOINT_CHOICE = 37
    MOBILITY = 38
    APPLIANCE_TRIGGER = 39
    APPLIANCE_SIGNATURE = 40
    HOT_WATER_DRAW = 41
    DER_DISPATCH = 42

    # -- environment (S01) ----------------------------------------------------
    WEATHER_SUBHOUR = 50
    WEATHER_DOWNSCALE = 51

    # -- observation and export (S12, S13) ------------------------------------
    SENSOR_NOISE = 60
    SENSOR_GAP = 61
    SENSOR_DRIFT = 62
    SENSOR_FAILURE = 63
    SURVEY_RESPONSE = 64
    RECORDED_METADATA = 65
    STUDY_PROTOCOL = 66
    OPERATOR_LOG = 67

    # -- MIMIC (5.14) ---------------------------------------------------------
    MIMIC_POOL_PERSON = 70
    MIMIC_RESPONSE_PROPENSITY = 71
    MIMIC_WILLINGNESS = 72
    MIMIC_LATENCY = 73
    MIMIC_ABANDONMENT = 74
    MIMIC_SESSION_COMPOSITION = 75
    MIMIC_PLANTED_EFFECT = 76

    # -- run assembly --------------------------------------------------------
    ESTATE_SELECTION = 77

    # -- WP7 venues (S02/S07) -------------------------------------------------
    #: Which venue a per-visit activity happens at (shopping, social, sport,
    #: civic). Persistent venues - a child's school, a worker's workplace -
    #: are assigned once in population/venues.py and draw nothing here.
    #:
    #: 78, not 9002: the 9000s are the test and negative-control streams, and
    #: a production subsystem that borrowed one would share a sequence with a
    #: harness. Appended rather than renumbered, which is what the contract
    #: above requires - changing an existing value invalidates every
    #: checkpoint.
    VENUE_CHOICE = 78

    # -- Phase 12 D18 era gating (S12) ----------------------------------------
    #: The home's ranking key against the sourced ESB Networks rollout curve,
    #: which becomes its smart-meter install date (A-98). Its own stream, not
    #: SENSOR_TIER's: the tier is what a household consented to and the install
    #: date is what the utility did, and sharing a sequence would correlate the
    #: two for no modelled reason.
    SMART_METER_INSTALL = 79
    #: The PARA//EL enrolment propensity's per-home and per-estate terms
    #: (D-111 / A-99).
    PARAEL_ENROLMENT = 80

    # -- test and negative-control streams -----------------------------------
    TEST_ONLY = 9000
    NEGATIVE_CONTROL = 9001


def stable_entity_id(entity: str) -> int:
    """Map a string entity key (``"P-000123"``, ``"B-0007"``) to a 64-bit word.

    Deterministic across processes and Python versions: it reads the ASCII bytes
    rather than calling ``hash()``, which is salted per interpreter.  FNV-1a is
    used because collision resistance is not a security property here, only
    stability.
    """
    h = 0xCBF29CE484222325
    for b in entity.encode("utf-8"):
        h = ((h ^ b) * 0x100000001B3) & _MASK64
    return h


class SeedTree:
    """The run's root of randomness.

    One instance per run, built from the manifest's master seed.  It hands out
    :class:`numpy.random.Generator` objects addressed by coordinate; it never
    holds mutable draw state of its own, so it is safe to share across workers.
    """

    __slots__ = ("_master_seed", "_key")

    def __init__(self, master_seed: int) -> None:
        if not isinstance(master_seed, (int, np.integer)) or isinstance(master_seed, bool):
            raise TypeError(f"master_seed must be an int, got {type(master_seed).__name__}")
        master_seed = int(master_seed)
        if not 0 <= master_seed <= _MASK64:
            raise ValueError(f"master_seed must fit in 64 bits, got {master_seed}")
        self._master_seed = master_seed
        # Two independent 64-bit words so the key has no exploitable structure.
        k0 = splitmix64(master_seed)
        self._key = (k0, splitmix64(k0 ^ 0xA0761D6478BD642F))

    # -- introspection --------------------------------------------------------

    @property
    def master_seed(self) -> int:
        return self._master_seed

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return f"SeedTree(master_seed={self._master_seed})"

    # -- the one way to get randomness ---------------------------------------

    def generator(
        self,
        stream: Stream,
        entity: int | str = 0,
        sim_day: int = 0,
        draw: int = 0,
    ) -> Generator:
        """Return the generator for exactly one coordinate.

        Parameters
        ----------
        stream:
            A :class:`Stream` member.  A bare ``int`` is refused: an undeclared
            stream number is how two subsystems end up sharing a sequence.
        entity:
            Entity id.  A string key is hashed with :func:`stable_entity_id`.
        sim_day:
            Days since the run epoch.  ``0`` for static synthesis.
        draw:
            Sub-stream within the day, for a caller that needs several
            independent sequences for the same entity-day (for example one per
            appliance).  It is *not* a counter the caller has to advance: drawing
            many values from the returned generator is the normal case.
        """
        if not isinstance(stream, Stream):
            raise TypeError(
                "stream must be a Stream member, not a bare int. "
                "Declare the stream in baile_nua.rng.Stream so it cannot collide."
            )
        ent = stable_entity_id(entity) if isinstance(entity, str) else int(entity)
        if ent < 0:
            raise ValueError(f"entity id must be non-negative, got {ent}")
        if sim_day < 0:
            raise ValueError(f"sim_day must be non-negative, got {sim_day}")
        if draw < 0:
            raise ValueError(f"draw must be non-negative, got {draw}")
        counter = (
            int(stream) & _MASK64,
            ent & _MASK64,
            int(sim_day) & _MASK64,
            int(draw) & _MASK64,
        )
        return Generator(Philox(key=list(self._key), counter=list(counter)))

    def spawn_key(
        self, stream: Stream, entity: int | str = 0, sim_day: int = 0, draw: int = 0
    ) -> tuple[int, int, int, int, int, int]:
        """The full coordinate, for recording in a checkpoint or manifest.

        Returns ``(key0, key1, stream, entity, sim_day, draw)``.  Writing this
        into a checkpoint is what lets ``replay()`` rebuild a home-day without
        replaying the run.
        """
        ent = stable_entity_id(entity) if isinstance(entity, str) else int(entity)
        return (*self._key, int(stream), ent, int(sim_day), int(draw))
