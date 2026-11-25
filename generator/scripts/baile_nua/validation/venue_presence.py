"""Design 9.4 week 3: "venue presence consistent with person presence".

The criterion compares two records of the same fact. A presence row says *this
person was at this venue from this minute to that one*; a venue's occupancy is
*how many people were there at each minute*. One is derived from the other, so
they cannot disagree by arithmetic — which is exactly why the check has to test
the things that **can** disagree:

1. **Nobody is in two places at once.** Two overlapping intervals for one
   person in the same day is the failure that makes every venue occupancy
   wrong at once, and it is invisible from the venue side: each venue's own
   count looks fine.
2. **Every venue a person is recorded at exists and has a capacity.** Design
   5.4 says every venue has a capacity. A presence row naming a venue the town
   does not have is a dangling reference, and a ``location_id`` of ``None`` on
   a venue row is the state this build was in until WP7 — which is why
   :func:`check_venue_capacity` could never have passed: it groups by
   ``location_id``.
3. **No venue is over its capacity**, at any minute.
4. **The two records agree on the headcount.** Summing person-minutes at
   venues and summing venue-minutes of occupancy must give the same total. A
   mismatch means one side is dropping rows — and it is **not an independent
   check on (2)**: venue-minutes are summed only over rows that name a venue,
   so a venue row with no id fails both, and the gap between the two totals is
   that row's minutes. Reported because the size of the gap says how much
   presence is unaccounted for, which the count of rows alone does not.
5. **A person at a venue is not simultaneously recorded at home.** The
   building-side presence and the venue-side presence are written by the same
   loop from the same intervals, so a disagreement here means the interval
   classification is inconsistent with itself.

**What this criterion is not.** It is an *internal consistency* criterion, not
a calibration one, and the distinction matters because the venue capacities are
partly ``[A]`` (A-50). Consistency between two records of the same presence
does not depend on whether the capacity is the right number — but **(3)** does.
So (3) is reported separately from the rest, and a capacity violation is
reported as what it is: either the town genuinely has more demand than its
derived venue stock holds, or the declared capacity is wrong. The venue counts
are *derived* from the town's own population precisely so that this is
informative rather than an artefact of a chosen number.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "VenuePresenceError",
    "check_venue_presence_consistency",
]


class VenuePresenceError(RuntimeError):
    pass


def _overlaps(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Pairs of overlapping (start, end) in a sorted list."""
    out = []
    s = sorted(intervals)
    for (a0, a1), (b0, b1) in zip(s, s[1:]):
        if b0 < a1:
            out.append(((a0, a1), (b0, b1)))
    return out


def check_venue_presence_consistency(
    *, presence: Any, venues: Any, capacities: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Score the week-3 criterion on a run's presence rows.

    ``presence`` is the rows the engine wrote: ``person_id``, ``sim_day``,
    ``start_min``, ``end_min``, ``location_kind``, ``location_id``.
    ``venues`` is the WP7 venue list (or anything with ``venue_id`` and
    ``capacity``); ``capacities`` overrides it if given.
    """
    import pandas as pd

    df = presence if isinstance(presence, pd.DataFrame) else pd.DataFrame(presence)
    if df.empty:
        return {
            "measured": False,
            "why": (
                "the run wrote no presence rows. E1 collects presence for the "
                "first `collect_presence_days` days only, so a run with that "
                "at zero cannot answer this criterion - which is NOT the same "
                "as passing it."
            ),
        }

    caps = dict(capacities or {})
    if not caps:
        for v in (venues or []):
            vid = getattr(v, "venue_id", None) or (
                v.get("venue_id") if isinstance(v, dict) else None)
            cap = getattr(v, "capacity", None) or (
                v.get("capacity") if isinstance(v, dict) else None)
            if vid is not None and cap is not None:
                caps[str(vid)] = int(cap)
    if not caps:
        raise VenuePresenceError(
            "no venue capacities were supplied, so 'no venue over capacity' "
            "cannot be checked. Design 5.4: every venue has a capacity."
        )

    at_venue = df[df["location_kind"] == "venue"].copy()
    at_home = df[df["location_kind"] == "building"].copy()

    findings: list[dict[str, Any]] = []

    # -- 1. nobody in two places at once ------------------------------------
    n_double = 0
    for (pid, day), grp in df.groupby(["person_id", "sim_day"], sort=True):
        ov = _overlaps(list(zip(grp["start_min"].astype(int),
                                grp["end_min"].astype(int))))
        if ov:
            n_double += len(ov)
            if len(findings) < 20:
                findings.append({
                    "kind": "person_in_two_places_at_once",
                    "person_id": str(pid), "sim_day": int(day),
                    "overlapping": ov[:2],
                })

    # -- 2. every named venue exists and has a capacity ---------------------
    named = at_venue["location_id"]
    n_unnamed = int(named.isna().sum())
    dangling = sorted(set(named.dropna().astype(str)) - set(caps))

    # -- 3. no venue over capacity, at any minute ---------------------------
    over: list[dict[str, Any]] = []
    occupancy_minutes = 0
    for (vid, day), grp in at_venue.dropna(subset=["location_id"]).groupby(
            ["location_id", "sim_day"], sort=True):
        cap = caps.get(str(vid))
        starts = grp["start_min"].astype(int).to_numpy()
        ends = grp["end_min"].astype(int).to_numpy()
        occupancy_minutes += int((ends - starts).sum())
        if cap is None:
            continue
        # Occupancy changes only at an interval boundary, so the maximum is
        # attained at one of them; checking every minute would be 1440x the
        # work for the same answer.
        for t in sorted(set(starts.tolist())):
            n = int(((starts <= t) & (ends > t)).sum())
            if n > cap:
                over.append({"venue_id": str(vid), "sim_day": int(day),
                             "minute": int(t), "occupants": n,
                             "capacity": cap})
                break        # one report per venue-day is enough to fail it

    # -- 4. the two records agree on person-minutes -------------------------
    person_minutes = int(
        (at_venue["end_min"].astype(int) - at_venue["start_min"].astype(int)).sum())

    # -- 5. a person at a venue is not also at home at that minute ----------
    n_home_and_away = 0
    if not at_home.empty:
        home_by = {
            (str(r.person_id), int(r.sim_day)): []
            for r in at_home.itertuples()
        }
        for r in at_home.itertuples():
            home_by[(str(r.person_id), int(r.sim_day))].append(
                (int(r.start_min), int(r.end_min)))
        for r in at_venue.itertuples():
            for (h0, h1) in home_by.get((str(r.person_id), int(r.sim_day)), ()):
                if int(r.start_min) < h1 and h0 < int(r.end_min):
                    n_home_and_away += 1
                    break

    consistent = (
        n_double == 0 and n_unnamed == 0 and not dangling
        and n_home_and_away == 0
        and person_minutes == occupancy_minutes
    )
    return {
        "measured": True,
        "criterion": 'design 9.4 week 3: "venue presence consistent with person presence"',
        "n_presence_rows": int(len(df)),
        "n_venue_rows": int(len(at_venue)),
        "n_building_rows": int(len(at_home)),
        "n_distinct_venues_visited": int(
            at_venue["location_id"].dropna().nunique()),
        "n_venues_declared": len(caps),
        "consistency": {
            "person_in_two_places_at_once": n_double,
            "venue_rows_with_no_venue_id": n_unnamed,
            "venues_named_but_not_declared": dangling,
            "person_at_a_venue_and_at_home_at_once": n_home_and_away,
            "person_minutes_at_venues": person_minutes,
            "venue_occupancy_minutes": occupancy_minutes,
            "the_two_records_agree": person_minutes == occupancy_minutes,
        },
        "consistent": bool(consistent),
        "capacity": {
            "n_venue_days_over_capacity": len(over),
            "examples": over[:10],
            "within_capacity": not over,
            "reported_separately_because": (
                "consistency between two records of the same presence does "
                "not depend on whether a capacity is the right number, and "
                "the capacities are partly [A] (A-50). A capacity violation "
                "means either the town has more demand than its derived venue "
                "stock holds or the declared capacity is wrong - and the "
                "counts are DERIVED from the town's own population so that "
                "the answer is informative rather than an artefact of a "
                "chosen number."
            ),
        },
        "findings": findings,
        "what_this_is_not": (
            "A calibration check. No published figure says how many people "
            "are in a Cobh shop at 11:00, so nothing here is scored against "
            "an outside reference. It asks whether the model's two records of "
            "the same presence agree, and whether the venue stock holds the "
            "town the model built."
        ),
    }
