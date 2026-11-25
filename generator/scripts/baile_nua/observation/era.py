"""Per-home observability eras: when a home starts to be observed, and how.

D18 is "rendered device readings with noise and gaps" at 1-minute resolution and
it is the single largest dataset in the package - 27.1 kB per home-day measured
on the estate-year, 69% of a year's bytes.  Written for every home for every day
of the 2015-2026 replay it is about 130 GB, which does not fit the disk; and it
would also be **false**, because Ireland had no smart meters before late 2019 and
no PARA//EL programme before 2021.  A home cannot be observed before anything was
fitted to observe it.

So D18 is gated per home, and the gate is the same fact that bounds the real
data: what was installed, and when.

Three eras, in order, and a home only ever moves forwards through them:

``Era.NONE``
    Nothing is fitted.  **No D18 rows at all.**  This is the whole of
    2015-2018 for every home, and it is the correct state rather than a gap:
    the ESB Networks National Smart Metering Programme commenced in late 2019.

``Era.METER_30MIN``
    From the home's smart-meter install date.  The meter's own import and
    export registers, at the **30-minute** interval the programme's data
    service publishes - two channels, 96 readings a day, and nothing else.
    No room sensor, no CT clamp, no inverter telemetry: none of that is
    fitted by a meter exchange.

``Era.FULL_1MIN``
    From the home's PARA//EL / EdgeWare enrolment date.  The edge device reads
    the meter's HAN port and whatever else the household consented to, at
    1-minute resolution - the full device mix of the home's sensor tier.  This
    is the only era that produces the D18 the published estate-year contains.

**What is sourced and what is assumed.**

The smart-meter *rollout curve* is sourced:
``sources/derived/smart_meter_rollout.csv``, 4,291 daily rows, built from three
figures ESB Networks published - commencement in late 2019, 1.5 million of a
2 million target at 2023-11-21 (0.75), and "over two million / more than four
out of five households" at 2025-09-04 (0.83).  The interpolation *between*
those anchors, and the allocation of *which* premises is metered when, are
**A-98**: no county- or area-level breakdown is published.

PARA//EL enrolment is **D-111** and **A-99** end to end.  There is no enrolment
series and there cannot be one, because the programme is the project's own
fiction: 1 January 2021 to 30% of dwellings by 30 September 2026, skewed toward
homes with PV, heat pumps or EVs and toward estates with an energy co-op.

That the pre-enrolment observable is 30-minute import and export, and only
that, is **A-100**.

**How the national share is reproduced, and why it is by construction.**

Each home is given a deterministic uniform key from the seed tree, the homes are
ranked by it, and the home at rank ``r`` of ``N`` is handed the quantile
``u = (r + 0.5) / N``.  Its install date is the first day on which the sourced
cumulative share reaches ``u``.  The count installed by any day is then exactly
``round(share(day) * N)`` - not in expectation, but identically, for any ``N``.
Drawing ``u`` independently per home would have reproduced the curve only on
average, and a 50-home slice would have missed it by several homes.

A home whose ``u`` exceeds the curve's final value (0.83) is **never** metered
inside the replay, which is the right answer: a sixth of Irish premises still
had no smart meter at the end of the span.

Enrolment uses the project's standing rule - calibrated totals, endogenous
selection.  The A-99 ramp decides *how many* homes are enrolled on a given day;
a propensity score built from the home's own PV, heat pump and EV, plus a
per-estate offset, decides *which*.  A home must already have a meter to be
enrolled, because the edge device's import and export channels are the meter's
registers read over its HAN port; eligibility therefore opens on the install
date, and the daily target is filled from the eligible homes in propensity
order.  If the pool is ever too small the shortfall is reported in
:func:`diagnostics` rather than hidden, and the realised share falls short of
the target instead of a home being enrolled before it had a meter.
"""

from __future__ import annotations

import csv
import dataclasses
import datetime as dt
import enum
import functools
import heapq
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from baile_nua.rng import SeedTree, Stream

__all__ = [
    "Era",
    "HomeFacts",
    "HomeEra",
    "EraMap",
    "ROLLOUT_CSV",
    "ENROLMENT_START",
    "ENROLMENT_END",
    "ENROLMENT_FINAL_SHARE",
    "METER_ERA_CHANNELS",
    "METER_ERA_INTERVAL_S",
    "PROPENSITY_WEIGHTS",
    "rollout_curve",
    "enrolment_share",
    "build_era_map",
    "home_facts_from_slice",
    "RolloutSourceMissing",
]


class RolloutSourceMissing(RuntimeError):
    """The sourced rollout curve is not on disk.

    Raised rather than defaulted.  A silent fallback here would publish an
    install-date distribution that no press release supports, and the whole
    point of the gate is that the dates trace to something.
    """


ROLLOUT_CSV = "sources/derived/smart_meter_rollout.csv"

#: D-111: enrolment opens on 1 January 2021 and reaches 30% of dwellings on
#: 30 September 2026, the last day of the replay.  A-99: the SHAPE between
#: those two points is assumed linear, exactly as A-98 assumes it for the
#: rollout - nothing published or publishable constrains it, because the
#: programme is this project's own.
ENROLMENT_START = dt.date(2021, 1, 1)
ENROLMENT_END = dt.date(2026, 9, 30)
ENROLMENT_FINAL_SHARE = 0.30

#: A-100.  What a smart meter exchange alone makes observable: the meter's
#: active-import and active-export registers, at the 30-minute interval the
#: programme's data service publishes.  A meter exchange fits no room sensor,
#: no CT clamp and no inverter telemetry, so a home in this era has none of
#: them however high its consented sensor tier is - the tier describes what
#: PARA//EL would install, and PARA//EL has not been yet.
METER_ERA_CHANNELS: tuple[str, ...] = ("import_w", "export_w")
METER_ERA_INTERVAL_S = 1800

#: A-99.  The enrolment propensity's named terms.  These decide only the ORDER
#: in which homes enrol; the COUNT comes from the ramp above, so changing a
#: weight re-sorts the queue and never changes how many homes are enrolled on
#: any day.  That is the project's standing rule (calibrated totals, endogenous
#: selection) and it is why these numbers can be stated without a source.
PROPENSITY_WEIGHTS: dict[str, float] = {
    "pv": 1.0,
    "heat_pump": 0.8,
    "ev": 0.8,
    #: The spread of the per-estate offset.  This is D-111's "estates with an
    #: energy co-op" term, and it is realised as a seeded per-estate offset
    #: rather than as a reading of a co-op attribute, because the population
    #: synthesis holds none: there is no co-op in the town model today. What it
    #: reproduces is the observable CONSEQUENCE - enrolment clusters by estate
    #: instead of being spread evenly - and if a co-op is ever synthesised this
    #: term should read it instead of drawing.
    "estate_sd": 0.6,
    #: Per-home idiosyncrasy, so that two homes with identical PV, heat pump
    #: and EV do not enrol in building-id order.
    "home_sd": 0.5,
}


class Era(enum.Enum):
    """What is fitted at a home on a given day, and therefore what D18 holds."""

    NONE = "none"
    METER_30MIN = "meter_30min"
    FULL_1MIN = "full_1min"


@dataclasses.dataclass(frozen=True)
class HomeFacts:
    """The home attributes the enrolment propensity reads.

    Deliberately narrow.  The era model is allowed to know what technology is
    fitted and which estate the dwelling is in; it is not allowed to know
    anything about the people, because enrolment under D-111 is a property of
    the premises offer and because R11 keeps person attributes out of anything
    that shapes an observable.
    """

    premises_id: str
    estate_id: str
    has_pv: bool = False
    has_heat_pump: bool = False
    has_ev: bool = False


@dataclasses.dataclass(frozen=True)
class HomeEra:
    """One home's two dates, and the era they imply for any day."""

    premises_id: str
    #: The day the smart meter was exchanged; ``None`` if never, inside the span.
    install_date: dt.date | None
    #: The day PARA//EL enrolment took effect; ``None`` if never.
    enrolment_date: dt.date | None

    def era_on(self, day: dt.date) -> Era:
        if self.enrolment_date is not None and day >= self.enrolment_date:
            return Era.FULL_1MIN
        if self.install_date is not None and day >= self.install_date:
            return Era.METER_30MIN
        return Era.NONE


def _project_root() -> Path:
    """Reuse ``sources.PROJECT_ROOT`` rather than recount parents.

    Same reason ``engine/calendar.py`` does: this module sits one level deeper
    than ``sources.py``, so a copied ``parents[2]`` would point at ``scripts/``.
    """
    from baile_nua.sources import PROJECT_ROOT

    return PROJECT_ROOT


@functools.lru_cache(maxsize=1)
def rollout_curve() -> tuple[tuple[dt.date, ...], tuple[float, ...]]:
    """The sourced daily cumulative share of premises with a smart meter.

    Returns ``(dates, shares)``, both ascending and the same length.  Read
    straight off the derived CSV; nothing is interpolated here, because the
    interpolation is already in the file and declared there as A-98.
    """
    path = _project_root() / ROLLOUT_CSV
    if not path.exists():
        raise RolloutSourceMissing(
            f"{ROLLOUT_CSV} is not on disk, so no home has an install date and "
            f"D18 cannot be gated. This is a sourced table (A-98, three ESB "
            f"Networks anchors) and there is no fallback: a default curve would "
            f"publish install dates with nothing behind them."
        )
    dates: list[dt.date] = []
    shares: list[float] = []
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            dates.append(dt.date.fromisoformat(row["date"]))
            shares.append(float(row["cumulative_share_of_premises"]))
    if not dates:
        raise RolloutSourceMissing(f"{ROLLOUT_CSV} is empty")
    if any(b < a for a, b in zip(dates, dates[1:])):
        raise ValueError(f"{ROLLOUT_CSV} dates are not ascending")
    if any(b < a - 1e-12 for a, b in zip(shares, shares[1:])):
        raise ValueError(
            f"{ROLLOUT_CSV} cumulative share decreases somewhere; a cumulative "
            f"rollout cannot un-install meters"
        )
    return tuple(dates), tuple(shares)


def enrolment_share(day: dt.date) -> float:
    """The A-99 PARA//EL enrolment target share for ``day``.

    Zero before :data:`ENROLMENT_START`, linear to
    :data:`ENROLMENT_FINAL_SHARE` at :data:`ENROLMENT_END`, and flat after -
    flat rather than extrapolated, because D-111 states a point and not a
    gradient, and continuing the ramp past the end of the replay would be
    inventing a programme decision nobody has taken.
    """
    if day < ENROLMENT_START:
        return 0.0
    if day >= ENROLMENT_END:
        return ENROLMENT_FINAL_SHARE
    span = (ENROLMENT_END - ENROLMENT_START).days
    return ENROLMENT_FINAL_SHARE * ((day - ENROLMENT_START).days / span)


def _install_dates(
    facts: Sequence[HomeFacts], *, seed_tree: SeedTree,
) -> dict[str, dt.date | None]:
    """Stratified install dates: the count by any day is ``round(share * N)``.

    The ranking key is drawn per premises from the seed tree, so it depends on
    the master seed and the premises id and on nothing else - not on position in
    the list, not on how many workers ran, not on the order homes were visited.
    """
    n = len(facts)
    keys = []
    for f in facts:
        gen = seed_tree.generator(
            Stream.SMART_METER_INSTALL, entity=f.premises_id, sim_day=0
        )
        keys.append((float(gen.random()), f.premises_id))
    # Sorted on (key, premises_id): the id breaks a tie so that two homes that
    # drew the same float still get a defined order.
    keys.sort()
    dates, shares = rollout_curve()
    share_arr = np.asarray(shares, dtype=np.float64)
    out: dict[str, dt.date | None] = {}
    for rank, (_key, pid) in enumerate(keys):
        u = (rank + 0.5) / n
        # First day whose cumulative share reaches u.
        i = int(np.searchsorted(share_arr, u, side="left"))
        out[pid] = dates[i] if i < len(dates) else None
    return out


def _propensity(f: HomeFacts, *, seed_tree: SeedTree) -> float:
    w = PROPENSITY_WEIGHTS
    gen = seed_tree.generator(
        Stream.PARAEL_ENROLMENT, entity=f.premises_id, sim_day=0
    )
    egen = seed_tree.generator(
        Stream.PARAEL_ENROLMENT, entity=f"estate:{f.estate_id}", sim_day=0
    )
    score = (
        w["pv"] * float(f.has_pv)
        + w["heat_pump"] * float(f.has_heat_pump)
        + w["ev"] * float(f.has_ev)
        + float(egen.normal(0.0, w["estate_sd"]))
        + float(gen.normal(0.0, w["home_sd"]))
    )
    return score


def _enrolment_dates(
    facts: Sequence[HomeFacts],
    install: Mapping[str, dt.date | None],
    *,
    seed_tree: SeedTree,
) -> tuple[dict[str, dt.date | None], dict[str, Any]]:
    """Fill the A-99 daily target from the metered homes in propensity order."""
    n = len(facts)
    # Rank: highest propensity first, premises id breaking any tie.
    scored = sorted(
        ((-_propensity(f, seed_tree=seed_tree), f.premises_id) for f in facts)
    )
    rank_of = {pid: r for r, (_s, pid) in enumerate(scored)}

    # When each home becomes ELIGIBLE: its install date.  Homes never metered
    # inside the span never become eligible.
    by_install: dict[dt.date, list[str]] = {}
    for f in facts:
        d = install.get(f.premises_id)
        if d is not None:
            by_install.setdefault(d, []).append(f.premises_id)

    out: dict[str, dt.date | None] = {f.premises_id: None for f in facts}
    pool: list[tuple[int, str]] = []        # a heap, best propensity first
    enrolled = 0
    shortfall_days = 0
    max_shortfall = 0
    day = ENROLMENT_START
    # The loop runs to the END of the rollout table, not to ENROLMENT_END: the
    # table is the replay's own span, and stopping early would leave the last
    # days ungated.
    dates, _shares = rollout_curve()
    last = dates[-1]
    # Homes metered BEFORE enrolment opened are already eligible on day one.
    for d, pids in by_install.items():
        if d <= day:
            for pid in pids:
                heapq.heappush(pool, (rank_of[pid], pid))
    one = dt.timedelta(days=1)
    while day <= last:
        if day > ENROLMENT_START:
            for pid in by_install.get(day, ()):
                heapq.heappush(pool, (rank_of[pid], pid))
        target = int(round(enrolment_share(day) * n))
        want = target - enrolled
        if want > 0:
            took = 0
            while took < want and pool:
                _r, pid = heapq.heappop(pool)
                out[pid] = day
                took += 1
                enrolled += 1
            if took < want:
                shortfall_days += 1
                max_shortfall = max(max_shortfall, want - took)
        day += one
    diag = {
        "n_homes": n,
        "n_enrolled": enrolled,
        "final_target": int(round(enrolment_share(last) * n)),
        "shortfall_days": shortfall_days,
        "max_shortfall_homes": max_shortfall,
    }
    return out, diag


@dataclasses.dataclass(frozen=True)
class EraMap:
    """Every home's era dates, keyed by premises id.

    Built once per run.  It holds no mutable state and no generator, so it is
    safe to share across workers exactly as :class:`~baile_nua.rng.SeedTree` is.
    """

    homes: Mapping[str, HomeEra]
    enrolment_diagnostics: Mapping[str, Any]

    def __len__(self) -> int:
        return len(self.homes)

    def era_on(self, premises_id: str, day: dt.date) -> Era:
        """The era for one home on one day.

        A premises the map does not hold is :attr:`Era.NONE` and not an error:
        the map is built from the run's own slice, so an unknown premises has no
        install date, and returning "nothing is fitted" is both the safe answer
        and the true one.
        """
        home = self.homes.get(premises_id)
        return Era.NONE if home is None else home.era_on(day)

    def realised_meter_share(self, day: dt.date) -> float:
        """The share of homes with a smart meter on ``day``, as built."""
        if not self.homes:
            return 0.0
        k = sum(
            1 for h in self.homes.values()
            if h.install_date is not None and day >= h.install_date
        )
        return k / len(self.homes)

    def realised_enrolment_share(self, day: dt.date) -> float:
        if not self.homes:
            return 0.0
        k = sum(
            1 for h in self.homes.values()
            if h.enrolment_date is not None and day >= h.enrolment_date
        )
        return k / len(self.homes)

    def diagnostics(self) -> dict[str, Any]:
        """What the run should record about its own gating."""
        installed = [
            h.install_date for h in self.homes.values() if h.install_date
        ]
        enrolled = [
            h.enrolment_date for h in self.homes.values() if h.enrolment_date
        ]
        dates, shares = rollout_curve()
        return {
            "n_homes": len(self.homes),
            "n_ever_metered": len(installed),
            "n_never_metered": len(self.homes) - len(installed),
            "n_ever_enrolled": len(enrolled),
            "first_install": min(installed).isoformat() if installed else None,
            "last_install": max(installed).isoformat() if installed else None,
            "first_enrolment": min(enrolled).isoformat() if enrolled else None,
            "rollout_source": ROLLOUT_CSV,
            "rollout_span": [dates[0].isoformat(), dates[-1].isoformat()],
            "rollout_final_share": shares[-1],
            "enrolment_assumption": "D-111 / A-99",
            "meter_era_channels": list(METER_ERA_CHANNELS),
            "meter_era_interval_s": METER_ERA_INTERVAL_S,
            "enrolment": dict(self.enrolment_diagnostics),
        }


def build_era_map(
    facts: Iterable[HomeFacts], *, master_seed: int,
) -> EraMap:
    """Assign every home its install and enrolment date.

    Deterministic in ``master_seed`` and the premises ids alone.  ``facts`` may
    arrive in any order; it is sorted here, so two callers that built the same
    set of homes get the same map.
    """
    items = sorted(facts, key=lambda f: f.premises_id)
    seen: set[str] = set()
    for f in items:
        if f.premises_id in seen:
            raise ValueError(
                f"premises {f.premises_id!r} appears twice; the era map is "
                f"keyed by premises and a duplicate would silently take one "
                f"home's install date and drop the other's"
            )
        seen.add(f.premises_id)
    if not items:
        return EraMap(homes={}, enrolment_diagnostics={"n_homes": 0})
    tree = SeedTree(master_seed)
    install = _install_dates(items, seed_tree=tree)
    enrol, diag = _enrolment_dates(items, install, seed_tree=tree)
    homes = {
        f.premises_id: HomeEra(
            premises_id=f.premises_id,
            install_date=install[f.premises_id],
            enrolment_date=enrol[f.premises_id],
        )
        for f in items
    }
    return EraMap(homes=homes, enrolment_diagnostics=diag)


def home_facts_from_slice(sl: Any) -> list[HomeFacts]:
    """Read the era model's narrow view off a built slice.

    PV is membership of ``sl.pv`` (the slice's PV systems are keyed by
    household); the heat pump is the building's own ``heating_system``; the EV
    is the ``has_ev`` flag the DER draw sets on the building.  Nothing else is
    read, and nothing is drawn here.
    """
    out: list[HomeFacts] = []
    for hh_id, b in sorted(sl.buildings.items()):
        out.append(HomeFacts(
            premises_id=b.premises_id,
            estate_id=str(b.estate_id),
            has_pv=hh_id in getattr(sl, "pv", {}),
            has_heat_pump=str(getattr(b, "heating_system", "")) == "heat pump",
            has_ev=bool(getattr(b, "has_ev", False)),
        ))
    return out
