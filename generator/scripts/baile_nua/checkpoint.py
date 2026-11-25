"""Hash-chained daily checkpoints and the daily exchange log (design 8.2).

The contract:

    Full household and town state is saved at every day start, content-hashed
    and chained.  ``replay(home, day range)`` = checkpoint + recorded exchange
    log, giving byte-identical output.  Changing history invalidates every
    downstream checkpoint in the hash chain.

Two artefacts per simulated day:

:class:`Checkpoint`
    State at 00:00 of day *d*, plus the hash of day *d-1*'s checkpoint.  Holds
    only what the next day cannot derive: household and person state, building
    thermal state, asset state, and the RNG coordinate each household is at.
    It deliberately does **not** hold rendered output, which is reproducible.

:class:`ExchangeLog`
    The frozen output of Phase A (design 8.2): everything resolved town-wide in
    fixed id order before households run in parallel.  Because households may
    read this but never write it, and nothing else crosses households, a single
    household-day can be replayed in isolation from
    ``(checkpoint, exchange_log)`` alone.

The chain means an upstream edit is *detectable*, not merely discouraged:
:meth:`CheckpointStore.verify_chain` recomputes every link and reports the
earliest day at which the recorded chain diverges.
"""

from __future__ import annotations

import dataclasses
import gzip
import json
from pathlib import Path
from typing import Any

from baile_nua.hashing import canonical_json, chain, hash_bytes, hash_json

__all__ = ["Checkpoint", "ExchangeLog", "CheckpointStore", "ChainError"]

CHECKPOINT_FORMAT_VERSION = "1.0.0"


class ChainError(RuntimeError):
    """The recorded hash chain does not match the stored checkpoints."""


@dataclasses.dataclass
class ExchangeLog:
    """Phase A output: the only channel by which anything crosses households.

    Written once per simulated day, in fixed id order, before Phase B starts.
    Read-only thereafter - :meth:`freeze` makes that structural rather than a
    convention.
    """

    sim_day: int
    date_iso: str
    #: life events effective today, by household id
    life_events: dict[str, list[dict[str, Any]]] = dataclasses.field(default_factory=dict)
    #: illness transmission outcomes, by person id
    health_transitions: dict[str, str] = dataclasses.field(default_factory=dict)
    #: calendar event instances in force today
    calendar_events: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    #: event attendance draws, by person id
    event_attendance: dict[str, list[str]] = dataclasses.field(default_factory=dict)
    #: venue assignment with capacity already checked, by person id
    venue_assignments: dict[str, str] = dataclasses.field(default_factory=dict)
    #: pre-drawn cross-household contacts (visits, minding grandchildren)
    cross_household_contacts: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    #: shared vehicle allocation, by vehicle asset id
    shared_vehicles: dict[str, list[str]] = dataclasses.field(default_factory=dict)
    #: disruptions scheduled for today, by household id
    disruptions: dict[str, list[dict[str, Any]]] = dataclasses.field(default_factory=dict)
    #: network state published for epoch 0, from the previous day's last solve
    initial_network_state: dict[str, Any] = dataclasses.field(default_factory=dict)
    _frozen: bool = dataclasses.field(default=False, repr=False)

    def freeze(self) -> ExchangeLog:
        object.__setattr__(self, "_frozen", True)
        return self

    def __setattr__(self, name: str, value: Any) -> None:
        if getattr(self, "_frozen", False) and name != "_frozen":
            raise RuntimeError(
                "the daily exchange log is frozen at the end of Phase A "
                "(design 8.2); Phase B may read it but never write it"
            )
        object.__setattr__(self, name, value)

    def payload(self) -> dict[str, Any]:
        d = {k: v for k, v in dataclasses.asdict(self).items() if not k.startswith("_")}
        return d

    def content_hash(self) -> str:
        return hash_json(self.payload())


@dataclasses.dataclass
class Checkpoint:
    """State at the start of one simulated day, chained to the previous day."""

    sim_day: int
    date_iso: str
    run_id: str
    master_seed: int
    #: per-person evolving state, keyed by person id
    person_state: dict[str, dict[str, Any]] = dataclasses.field(default_factory=dict)
    #: per-household state, keyed by household id
    household_state: dict[str, dict[str, Any]] = dataclasses.field(default_factory=dict)
    #: per-building thermal and DHW state, keyed by building id
    building_state: dict[str, dict[str, Any]] = dataclasses.field(default_factory=dict)
    #: per-asset state (SoC, cycle count, failure state), keyed by asset id
    asset_state: dict[str, dict[str, Any]] = dataclasses.field(default_factory=dict)
    #: town-level counters and pending scheduled decisions
    town_state: dict[str, Any] = dataclasses.field(default_factory=dict)
    #: hash of the previous day's checkpoint; None on day 0
    previous_hash: str | None = None
    #: hash of the exchange log that will drive this day
    exchange_log_hash: str | None = None
    format_version: str = CHECKPOINT_FORMAT_VERSION

    def payload(self) -> dict[str, Any]:
        """The part that is hashed.  Excludes the chain link itself."""
        return {
            "format_version": self.format_version,
            "sim_day": self.sim_day,
            "date_iso": self.date_iso,
            "run_id": self.run_id,
            "master_seed": self.master_seed,
            "person_state": self.person_state,
            "household_state": self.household_state,
            "building_state": self.building_state,
            "asset_state": self.asset_state,
            "town_state": self.town_state,
            "exchange_log_hash": self.exchange_log_hash,
        }

    def content_hash(self) -> str:
        return hash_json(self.payload())

    def chain_hash(self) -> str:
        """This checkpoint's link: commits to its content and its predecessor."""
        return chain(self.previous_hash, self.content_hash())


class CheckpointStore:
    """Checkpoints and exchange logs on disk, one gzipped JSON file per day.

    JSON rather than pickle: a checkpoint has to be readable and diffable years
    later, and pickle would make the format depend on the class layout.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    # -- paths ---------------------------------------------------------------

    def _cp_path(self, sim_day: int) -> Path:
        return self.root / f"day_{sim_day:05d}.checkpoint.json.gz"

    def _xl_path(self, sim_day: int) -> Path:
        return self.root / f"day_{sim_day:05d}.exchange.json.gz"

    def _chain_path(self) -> Path:
        return self.root / "chain.json"

    # -- write ---------------------------------------------------------------

    def put(self, cp: Checkpoint, xl: ExchangeLog | None = None) -> str:
        if xl is not None:
            if xl.sim_day != cp.sim_day:
                raise ValueError(
                    f"exchange log is for day {xl.sim_day} but checkpoint is day {cp.sim_day}"
                )
            cp.exchange_log_hash = xl.content_hash()
            self._write_gz(self._xl_path(cp.sim_day), xl.payload())
        link = cp.chain_hash()
        self._write_gz(
            self._cp_path(cp.sim_day),
            {
                "payload": cp.payload(),
                "previous_hash": cp.previous_hash,
                "chain_hash": link,
            },
        )
        self._append_chain(cp.sim_day, cp.content_hash(), link)
        return link

    @staticmethod
    def _write_gz(path: Path, obj: Any) -> None:
        # mtime=0 so the gzip header does not change between runs: the file
        # bytes must be identical for the determinism test, not just the content.
        raw = canonical_json(obj)
        with gzip.GzipFile(filename="", mode="wb", fileobj=open(path, "wb"), mtime=0) as gz:
            gz.write(raw)

    def _append_chain(self, sim_day: int, content_hash: str, link: str) -> None:
        p = self._chain_path()
        chain_rec = json.loads(p.read_text()) if p.exists() else {"links": []}
        links = [l for l in chain_rec["links"] if l["sim_day"] != sim_day]
        links.append({"sim_day": sim_day, "content_hash": content_hash, "chain_hash": link})
        links.sort(key=lambda l: l["sim_day"])
        chain_rec["links"] = links
        chain_rec["head"] = links[-1]["chain_hash"] if links else None
        p.write_text(json.dumps(chain_rec, indent=2))

    # -- read ----------------------------------------------------------------

    @staticmethod
    def _read_gz(path: Path) -> Any:
        with gzip.open(path, "rb") as gz:
            return json.loads(gz.read().decode("utf-8"))

    def get(self, sim_day: int) -> Checkpoint:
        rec = self._read_gz(self._cp_path(sim_day))
        p = rec["payload"]
        return Checkpoint(
            sim_day=p["sim_day"],
            date_iso=p["date_iso"],
            run_id=p["run_id"],
            master_seed=p["master_seed"],
            person_state=p["person_state"],
            household_state=p["household_state"],
            building_state=p["building_state"],
            asset_state=p["asset_state"],
            town_state=p["town_state"],
            previous_hash=rec["previous_hash"],
            exchange_log_hash=p["exchange_log_hash"],
            format_version=p["format_version"],
        )

    def get_exchange_log(self, sim_day: int) -> ExchangeLog:
        p = self._read_gz(self._xl_path(sim_day))
        return ExchangeLog(**p).freeze()

    def days(self) -> list[int]:
        return sorted(
            int(p.name.split("_")[1].split(".")[0]) for p in self.root.glob("day_*.checkpoint.json.gz")
        )

    def head(self) -> str | None:
        p = self._chain_path()
        return json.loads(p.read_text()).get("head") if p.exists() else None

    # -- integrity -----------------------------------------------------------

    def verify_chain(self) -> None:
        """Recompute every link.  Raise :class:`ChainError` at the first break.

        This is what makes "changing history invalidates every downstream
        checkpoint" an enforced property rather than a hope.
        """
        p = self._chain_path()
        if not p.exists():
            raise ChainError(f"no chain record at {p}")
        recorded = json.loads(p.read_text())["links"]
        prev: str | None = None
        for rec in recorded:
            day = rec["sim_day"]
            cp = self.get(day)
            if cp.previous_hash != prev:
                raise ChainError(
                    f"day {day}: stored previous_hash {cp.previous_hash!r} does not "
                    f"match the previous link {prev!r}. An upstream day was edited."
                )
            content = cp.content_hash()
            if content != rec["content_hash"]:
                raise ChainError(
                    f"day {day}: content hash {content[:16]}... does not match the "
                    f"recorded {rec['content_hash'][:16]}.... The checkpoint was edited."
                )
            link = chain(prev, content)
            if link != rec["chain_hash"]:
                raise ChainError(
                    f"day {day}: chain hash mismatch (recomputed {link[:16]}..., "
                    f"recorded {rec['chain_hash'][:16]}...)"
                )
            # the exchange log must match what the checkpoint committed to
            if cp.exchange_log_hash is not None:
                xl_path = self._xl_path(day)
                if not xl_path.exists():
                    raise ChainError(f"day {day}: checkpoint commits to an exchange log that is missing")
                got = hash_json(self._read_gz(xl_path))
                if got != cp.exchange_log_hash:
                    raise ChainError(
                        f"day {day}: exchange log hash {got[:16]}... does not match the "
                        f"{cp.exchange_log_hash[:16]}... the checkpoint committed to"
                    )
            prev = link

    def invalidated_from(self, sim_day: int) -> list[int]:
        """Days whose checkpoints an edit at ``sim_day`` invalidates (design 8.2)."""
        return [d for d in self.days() if d >= sim_day]
