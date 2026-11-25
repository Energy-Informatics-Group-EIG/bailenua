"""Identifier policy.

Two id spaces, deliberately kept apart (design 6.3, 6.4 item 2, decision D-007):

**Ground-truth ids** are sequential and readable: ``P-000001``, ``H-0007``,
``B-0042``, ``A-000310``, ``V-0003``.  They exist only in ``v1/ground_truth/``.
Sequential ids are a synthetic "tell", which is exactly why they must not
travel.

**Observable ids** are opaque strings keyed to the **premises** - the meter
point, which stays with the property - and never to the household.  When
occupants change, the premises id does not, and nothing announces the change.
That is the real ambiguity a change detector faces (design 6.4 item 2, Mary's
case in 5.9).

The mapping is an HMAC-SHA256 over the premises' ground-truth key under a
per-run id key.  Three properties follow:

* **Opaque.** Without the key, the observable id reveals nothing about ordering,
  estate, or how many homes exist.
* **Deterministic.** The same run always produces the same observable id, so
  replays and re-renders are byte-identical.
* **Not reversible by the recipient.** The key lives in the ground-truth
  crosswalk (``premises_crosswalk``), never in the observable package.

The id key is derived from the master seed, so a run is self-describing from its
manifest, and two runs with different seeds do not share observable ids.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Final

__all__ = [
    "gt_id",
    "IdMinter",
    "PREFIXES",
    "OBSERVABLE_ID_LEN",
]

PREFIXES: Final[dict[str, str]] = {
    "person": "P-",
    "household": "H-",
    "building": "B-",
    "asset": "A-",
    "venue": "V-",
    "premises": "MPRN-",
}

#: Length of the hex body of an observable id.  18 hex characters is 72 bits:
#: collision probability over 1,100 premises is ~2e-19, and it is long enough
#: that it does not look like a short sequential code.
OBSERVABLE_ID_LEN: Final[int] = 18


def gt_id(kind: str, n: int, width: int = 6) -> str:
    """A sequential ground-truth id.  ``gt_id("person", 1) -> 'P-000001'``."""
    try:
        prefix = PREFIXES[kind]
    except KeyError:
        raise KeyError(f"unknown id kind {kind!r}; known: {sorted(PREFIXES)}") from None
    if n < 0:
        raise ValueError(f"id number must be non-negative, got {n}")
    return f"{prefix}{n:0{width}d}"


class IdMinter:
    """Mints and crosswalks observable premises ids for one run.

    The key is derived from the master seed rather than randomly generated, so
    no extra secret has to be carried in the manifest for a replay to reproduce
    the same observable ids.
    """

    __slots__ = ("_key", "_forward", "_reverse")

    _KEY_CONTEXT: Final[bytes] = b"baile-nua/observable-premises-id/v1"

    def __init__(self, master_seed: int) -> None:
        self._key = hashlib.blake2b(
            master_seed.to_bytes(8, "big", signed=False),
            key=self._KEY_CONTEXT[:64],
            digest_size=32,
        ).digest()
        self._forward: dict[str, str] = {}
        self._reverse: dict[str, str] = {}

    def observable_premises_id(self, gt_premises_key: str) -> str:
        """Opaque observable id for a ground-truth premises key."""
        cached = self._forward.get(gt_premises_key)
        if cached is not None:
            return cached
        digest = hmac.new(
            self._key, gt_premises_key.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        obs = f"{PREFIXES['premises']}{digest[:OBSERVABLE_ID_LEN].upper()}"
        if obs in self._reverse and self._reverse[obs] != gt_premises_key:
            # 72-bit collision. Astronomically unlikely, but a silent collision
            # would merge two homes' observable data, so it must be loud.
            raise RuntimeError(
                f"observable premises id collision: {obs} already maps to "
                f"{self._reverse[obs]!r}, cannot also map {gt_premises_key!r}"
            )
        self._forward[gt_premises_key] = obs
        self._reverse[obs] = gt_premises_key
        return obs

    def to_gt(self, observable_id: str) -> str:
        """Reverse lookup.  Ground-truth side only; never shipped as OBS."""
        try:
            return self._reverse[observable_id]
        except KeyError:
            raise KeyError(
                f"{observable_id!r} was not minted by this run. The crosswalk is "
                f"run-scoped; observable ids from another master seed differ."
            ) from None

    def crosswalk_rows(self) -> list[dict[str, str]]:
        """The GT-class crosswalk, for ``v1/ground_truth/premises_crosswalk``."""
        return [
            {"premises_id": obs, "gt_premises_key": gt}
            for obs, gt in sorted(self._reverse.items())
        ]

    def __len__(self) -> int:
        return len(self._forward)
