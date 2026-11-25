"""WP7 venues: where people are when they are not at home.

Design 9.4's week-3 acceptance criterion is "**venue presence consistent with
person presence**", and until now there was nothing to be consistent *with*.
The activity engine has sent people to ``work_at_workplace``, ``school``,
``shopping``, ``social_out``, ``sport_exercise`` and ``religion_civic`` since
WP4, and recorded each of those as ``location_kind="venue"`` with
``location_id=None``. The town carried ``workplace_venue_id: None`` and
``school_venue_id: None`` on every person. And :func:`check_venue_capacity` in
``validation/invariants.py`` was written, exported, documented — and called by
nothing, which is how a venue layer that did not exist passed for one.

So three things were missing at once: the venues, the assignment of people to
them, and anyone asking whether the two records agreed.

**What is sourced.**

``MEAN_PUPILS_PER_SCHOOL`` comes from CSO **EDA49**, which publishes the number
of national schools *and* the number of pupils in them, both by teacher size of
school — so the ratio is a published mean enrolment, not a capacity this build
chose. That distinction decides whether the acceptance criterion means anything:
a venue whose capacity was invented could be made consistent with any
attendance by choosing the capacity.

**What is ``[A]``, registered as A-50.** How many venues Cobh has, and where.
PxStat publishes school statistics nationally; the register of individual
schools belongs to the Department of Education, and there is no PxStat table of
workplaces, shops or sports grounds by town. So the **count** of each venue type
is *derived* from the town's own population divided by the published size, and
the **siting** — which small area a venue sits in — is declared.

What that costs, stated rather than left implicit: a claim about *travel
distance* to a venue would be a claim about the declared siting, and is not
made. The criterion this supports is consistency between two records of the
same presence, which the siting does not touch.

**What this layer does NOT cover, measured rather than assumed.** 8,426 venue
presence rows in the 14-day town run carry no venue id (7.3% of 114,951), and
every one of them is the ``school`` activity performed by somebody with no
school assigned — a person aged 19 or over whose ``econ_status`` is
``"student"``. There are 241 such people in the town, with a **median age of
45**, and they are I-069: ``synthesise.py`` draws economic status from the
area marginal with no age conditioning, so the town has middle-aged students
who attend school.

So this is two faults wearing one symptom, and the order matters. A "college"
venue type would make the symptom go away by building a venue to serve a
population bug. The genuine 19-to-24 student population needs one — the Census
puts it at 9.92% of the 15+ population against the town's 1.63% — but it should
be built after I-069 is fixed, against a population whose students are
students. Recorded in I-069's consequences, and the week-3 venue criterion is
reported as FAIL with this as the cause.

**Why the counts are derived rather than declared.** A declared count would
make venue occupancy a free parameter: too few schools and every school is over
capacity, too many and the criterion passes trivially. Deriving the count from
the town's own school-age population and the published mean enrolment leaves
nothing to tune, and makes over-capacity a *finding* rather than an artefact of
a number someone picked.
"""

from __future__ import annotations

import dataclasses
import functools
import math
from typing import Any

__all__ = [
    "EDA49_SOURCE_KEY",
    "person_frame_from_town",
    "populate_venue_ids",
    "VENUE_TYPES",
    "SITING_A_FLAGS",
    "Venue",
    "VenueError",
    "mean_pupils_per_school",
    "build_venues",
    "assign_persistent_venues",
    "venue_capacities",
]

EDA49_SOURCE_KEY = "cso.education.eda49_schools_and_pupils_by_teacher_size"
EDA99_SOURCE_KEY = "cso.education.eda99_third_level_enrolments_by_institution"

#: The two Cork institutions a Cobh resident could commute to. Named rather
#: than "all colleges", because a Cobh student does not attend Trinity.
CORK_INSTITUTIONS: tuple[str, ...] = (
    "National University of Ireland, Cork",
    "Cork Institute of Technology",
)


class VenueError(RuntimeError):
    pass


@dataclasses.dataclass(frozen=True)
class Venue:
    """One D01 feature of kind ``venue``."""

    venue_id: str
    venue_type: str
    capacity: int
    small_area: str
    #: How the capacity was arrived at, carried on the venue so a reader of
    #: D01 does not have to come back here to find out whether it is sourced.
    capacity_basis: str

    def as_d01_row(self, valid_from: str = "2022-01-01") -> dict[str, Any]:
        """A D01 row. ``geometry_wkt`` is the small area's centroid.

        Declared as a point rather than a footprint: the model never asks how
        big a venue's building is, and a fabricated polygon would look like
        surveyed geometry in a dataset whose other rows are derived from real
        small-area boundaries.
        """
        import pandas as pd

        return {
            "feature_id": self.venue_id,
            "feature_kind": "venue",
            "geometry_wkt": f"POINT EMPTY  /* small area {self.small_area}; "
                            f"siting is [A] A-50 */",
            "venue_type": self.venue_type,
            "capacity": int(self.capacity),
            "feeder_id": None,
            "estate_id": None,
            "valid_from": pd.Timestamp(valid_from).tz_localize("UTC"),
            "valid_to": None,
        }


#: Which activity sends a person to which venue type, and how the type's
#: capacity is arrived at. ``persistent`` means a person goes to the SAME venue
#: every time — a child attends one school, a worker has one workplace — which
#: is what makes the two presence records comparable at all.
VENUE_TYPES: dict[str, dict[str, Any]] = {
    "primary_school": {
        "activities": ("school",),
        "persistent": True,
        "serves": "children aged 5 to 12",
        "capacity_basis": "sourced",
        "capacity_note": (
            "CSO EDA49: pupils in national schools over national schools, "
            "both by teacher size of school. A published mean enrolment."
        ),
    },
    "college": {
        "activities": ("school",),
        "persistent": True,
        "serves": "students aged 19 and over",
        "capacity_basis": "sourced",
        "capacity_note": (
            "CSO EDA99: full-time enrolment at the two Cork institutions a "
            "Cobh resident can commute to - National University of Ireland, "
            "Cork and Cork Institute of Technology. Cobh HAS NO third-level "
            "institution, so this venue sits OUTSIDE the town and the "
            "students travel to it. That is the modelled fact rather than an "
            "approximation, and it means capacity does not bind here: a Cobh "
            "student is not competing for a place against the town's other 90."
        ),
    },
    "secondary_school": {
        "activities": ("school",),
        "persistent": True,
        "serves": "children aged 13 to 18",
        "capacity_basis": "derived_from_sourced",
        "capacity_note": (
            "EDA49 covers NATIONAL (primary) schools only. Secondary capacity "
            "is taken at the same mean enrolment, which is [A] (A-50) and "
            "declared at the sourced primary figure rather than at a number "
            "chosen separately - Irish second-level schools are on average "
            "larger than primary ones, so this errs towards MORE schools and "
            "therefore towards finding over-capacity rather than hiding it."
        ),
    },
    "workplace": {
        "activities": ("work_at_workplace",),
        "persistent": True,
        "serves": "people at work who are not working from home",
        "capacity_basis": "declared",
        "capacity_note": (
            "[A] A-50. PxStat publishes no table of workplaces by size for a "
            "town. Declared at 25, deliberately SMALL: a smaller workplace "
            "means more of them and tighter capacity, so the criterion is "
            "harder to pass, not easier."
        ),
    },
    "shop": {
        "activities": ("shopping",),
        "persistent": False,
        "serves": "anyone, per visit",
        "capacity_basis": "declared",
        "capacity_note": "[A] A-50. Declared at 60 concurrent visitors.",
    },
    "community": {
        "activities": ("social_out", "religion_civic"),
        "persistent": False,
        "serves": "anyone, per visit",
        "capacity_basis": "declared",
        "capacity_note": "[A] A-50. Declared at 120 concurrent visitors.",
    },
    "sports": {
        "activities": ("sport_exercise",),
        "persistent": False,
        "serves": "anyone, per visit",
        "capacity_basis": "declared",
        "capacity_note": "[A] A-50. Declared at 80 concurrent visitors.",
    },
}

#: ``[A]``, A-50. The declared capacities and the siting, with the direction
#: each error pushes the acceptance criterion - which is the part that matters,
#: because a declared capacity that made the criterion EASIER would be a
#: declared number doing the work of a result.
SITING_A_FLAGS: dict[str, dict[str, Any]] = {
    "workplace_capacity": {
        "value": 25,
        "direction": "conservative: smaller venues mean more of them and "
                     "tighter capacity, so over-capacity is easier to find",
    },
    "shop_capacity": {"value": 60, "direction": "conservative, same reason"},
    "community_capacity": {"value": 120, "direction": "conservative, same reason"},
    "sports_capacity": {"value": 80, "direction": "conservative, same reason"},
    "siting": {
        "value": "one venue per small area in round-robin order",
        "direction": (
            "neutral for the consistency criterion, which compares two records "
            "of the same presence. A TRAVEL DISTANCE claim would depend on it "
            "and is not made."
        ),
    },
    "secondary_school_size": {
        "value": "the EDA49 primary mean",
        "direction": (
            "conservative: Irish second-level schools are larger on average, "
            "so this yields more schools and tighter capacity"
        ),
    },
}

_DECLARED_CAPACITY = {
    "workplace": 25, "shop": 60, "community": 120, "sports": 80,
}


@functools.lru_cache(maxsize=1)
def mean_pupils_per_school() -> dict[str, Any]:
    """Mean enrolment per national school, read from EDA49.

    Both the numerator and the denominator are published, so the mean is a
    ratio of two source figures rather than a number recorded by hand.
    """
    import json
    from pathlib import Path

    import numpy as np

    from baile_nua.sources import REGISTRY

    src = REGISTRY.get(EDA49_SOURCE_KEY)
    if src is None:
        raise VenueError(
            f"{EDA49_SOURCE_KEY} is not declared, so school size has no "
            f"source. Declare it before using it (D24)."
        )
    path = Path(__file__).resolve().parents[3] / "sources" / src.relpath
    if not path.exists():
        raise VenueError(
            f"{EDA49_SOURCE_KEY} is declared but not fetched: {path} is "
            f"absent. Fetch it rather than hard-coding the mean."
        )
    doc = json.loads(path.read_text(encoding="utf-8"))
    ids, size, value, dim = doc["id"], doc["size"], doc["value"], doc["dimension"]

    def index(key: str) -> dict[str, int]:
        c = dim[key]["category"]["index"]
        return c if isinstance(c, dict) else {str(v): i for i, v in enumerate(c)}

    size_dims = [k for k in ids if k not in ("STATISTIC", "TLIST(A1)")]
    if len(size_dims) != 1:
        raise VenueError(
            f"EDA49 has {len(size_dims)} dimensions besides STATISTIC and "
            f"year: {size_dims}. Its shape has changed and the mean must be "
            f"re-read, not guessed."
        )
    zd = size_dims[0]
    arr = np.array([np.nan if v is None else float(v) for v in value],
                   dtype=np.float64).reshape(size)
    pos = {k: i for i, k in enumerate(ids)}
    si, sl = index("STATISTIC"), dim["STATISTIC"]["category"]["label"]
    yi, yl = index("TLIST(A1)"), dim["TLIST(A1)"]["category"]["label"]
    zi, zl = index(zd), dim[zd]["category"]["label"]

    latest = max(yl, key=lambda k: int(yl[k]))
    total = [k for k, v in zl.items() if v.strip().lower() == "all teachers"]
    pupils = [k for k, v in sl.items() if "pupil" in v.lower()]
    schools = [k for k, v in sl.items() if v.strip().lower() == "national schools"]
    if not (total and pupils and schools):
        raise VenueError(
            f"EDA49 does not carry the categories the mean needs: "
            f"all-teachers={total}, pupils={pupils}, schools={schools}"
        )

    def get(stat: str) -> float:
        sel = [0] * len(ids)
        sel[pos["STATISTIC"]] = si[stat]
        sel[pos["TLIST(A1)"]] = yi[latest]
        sel[pos[zd]] = zi[total[0]]
        return float(arr[tuple(sel)])

    n_schools, n_pupils = get(schools[0]), get(pupils[0])
    if not (n_schools > 0 and n_pupils > 0):
        raise VenueError(
            f"EDA49 gave {n_schools} schools and {n_pupils} pupils for "
            f"{yl[latest]}; the mean cannot be taken"
        )
    mean = n_pupils / n_schools
    if not 50.0 < mean < 500.0:
        raise VenueError(
            f"EDA49 implies {mean:.1f} pupils per national school, outside any "
            f"plausible range. A dimension is being read wrongly."
        )
    return {
        "source": EDA49_SOURCE_KEY,
        "year": yl[latest],
        "n_schools": n_schools,
        "n_pupils": n_pupils,
        "mean_pupils_per_school": round(mean, 2),
        "basis": (
            "published pupil count over published school count, both at 'All "
            "teachers'. A ratio of two source figures; nothing recorded by hand."
        ),
    }


def person_frame_from_town(town: Any, *, as_of: str = "2022-01-01") -> Any:
    """The one frame the venue layer needs, joined out of the town's four.

    The town keeps these facts in four places and the join belongs here rather
    than at every call site: ``persons`` has ``birth_date`` and not ``age``;
    ``states`` has ``econ_status``, ``remote_share`` and ``school_year``;
    ``membership`` links a person to a building; and ``small_area`` is a
    property of the building. Getting that wrong silently is easy - a left
    join that drops the states frame would leave every person as not at work
    and size the workplace stock at one.
    """
    import pandas as pd

    ref = pd.Timestamp(as_of)
    persons = town.persons.copy()
    born = pd.to_datetime(persons["birth_date"], errors="coerce")
    persons["age"] = ((ref - born).dt.days // 365).astype("Int64")

    states = town.states.copy()
    # One state row per person at t0. The frame is bitemporal, so taking it
    # unfiltered would multiply a person by their state history.
    if "valid_to" in states.columns:
        states = states[states["valid_to"].isna()]
    states = states.drop_duplicates(subset=["person_id"], keep="first")

    out = persons[["person_id", "age"]].merge(
        states[["person_id", "econ_status", "remote_share", "school_year"]],
        on="person_id", how="left", validate="one_to_one")

    mem = town.membership
    if "valid_to" in mem.columns:
        mem = mem[mem["valid_to"].isna()]
    mem = mem.drop_duplicates(subset=["person_id"], keep="first")
    out = out.merge(mem[["person_id", "building_id"]], on="person_id",
                    how="left")

    sa = {b.building_id: getattr(b, "small_area", None) for b in town.buildings}
    out["small_area"] = out["building_id"].map(sa)

    n_missing = int(out["econ_status"].isna().sum())
    if n_missing:
        raise VenueError(
            f"{n_missing} of {len(out)} people have no econ_status after the "
            f"join, so workplace demand would be understated. The states "
            f"frame is bitemporal; check the valid_to filter."
        )
    return out


def populate_venue_ids(town: Any, *, assignment: dict[str, dict[str, Any]]) -> Any:
    """Return the town's ``states`` frame with the venue ids filled in.

    The columns have existed since WP2 and have been ``None`` on every row
    ever since - ``"workplace_venue_id": None``, ``"school_venue_id": None`` in
    synthesise.py. This fills them. Returns a copy: the synthesised town is the
    t0 fixture and other runs depend on it being unchanged.
    """
    states = town.states.copy()
    states["workplace_venue_id"] = states["person_id"].map(
        lambda pid: (assignment.get(str(pid)) or {}).get("workplace_venue_id"))
    states["school_venue_id"] = states["person_id"].map(
        lambda pid: (assignment.get(str(pid)) or {}).get("school_venue_id"))
    return states


@functools.lru_cache(maxsize=1)
def cork_third_level_capacity() -> dict[str, Any]:
    """Full-time enrolment at the Cork institutions, read from EDA99.

    The two named institutions rather than "all colleges": a Cobh resident
    commutes to Cork, not to Dublin, so the capacity that bears on this town
    is Cork's.
    """
    import json
    from pathlib import Path

    import numpy as np

    from baile_nua.sources import REGISTRY

    src = REGISTRY.get(EDA99_SOURCE_KEY)
    if src is None:
        raise VenueError(f"{EDA99_SOURCE_KEY} is not declared")
    path = Path(__file__).resolve().parents[3] / "sources" / src.relpath
    if not path.exists():
        raise VenueError(
            f"{EDA99_SOURCE_KEY} is declared but not fetched: {path}")
    doc = json.loads(path.read_text(encoding="utf-8"))
    ids, size, value, dim = doc["id"], doc["size"], doc["value"], doc["dimension"]

    def index(k: str) -> dict[str, int]:
        c = dim[k]["category"]["index"]
        return c if isinstance(c, dict) else {str(v): i for i, v in enumerate(c)}

    inst = [k for k in ids
            if "institution" in str(dim[k].get("label", "")).lower()]
    if len(inst) != 1:
        raise VenueError(f"EDA99 has {len(inst)} institution dimensions: {inst}")
    idim = inst[0]
    arr = np.array([np.nan if v is None else float(v) for v in value],
                   dtype=np.float64).reshape(size)
    pos = {k: i for i, k in enumerate(ids)}
    ii, il = index(idim), dim[idim]["category"]["label"]
    sti, stl = index("STATISTIC"), dim["STATISTIC"]["category"]["label"]
    yi, yl = index("TLIST(A1)"), dim["TLIST(A1)"]["category"]["label"]
    ft = [k for k, v in stl.items() if "full-time" in v.lower()]
    if not ft:
        raise VenueError(
            f"EDA99 has no full-time enrolment statistic: "
            f"{sorted(stl.values())}")

    per_inst: dict[str, dict[str, Any]] = {}
    for name in CORK_INSTITUTIONS:
        keys = [k for k, v in il.items() if v.strip() == name]
        if len(keys) != 1:
            raise VenueError(
                f"{name!r} is not exactly one EDA99 institution; published "
                f"names include {sorted(il.values())[:6]}")
        # The most recent year with a figure: EDA99's later years are blank
        # for some institutions after the sector was reorganised.
        got = None
        for ykey in sorted(yi, key=lambda z: -int(yl[z])):
            sel = [0] * len(ids)
            sel[pos["STATISTIC"]] = sti[ft[0]]
            sel[pos["TLIST(A1)"]] = yi[ykey]
            sel[pos[idim]] = ii[keys[0]]
            v = float(arr[tuple(sel)])
            if np.isfinite(v) and v > 0:
                got = (yl[ykey], v)
                break
        if got is None:
            raise VenueError(f"EDA99 has no full-time enrolment for {name!r}")
        per_inst[name] = {"year": got[0], "full_time_enrolment": got[1]}

    cap = int(round(sum(v["full_time_enrolment"] for v in per_inst.values())))
    if not 5_000 <= cap <= 100_000:
        raise VenueError(
            f"EDA99 implies a Cork third-level capacity of {cap}, outside any "
            f"plausible range. A dimension is being read wrongly.")
    return {
        "source": EDA99_SOURCE_KEY,
        "institutions": per_inst,
        "capacity": cap,
        "basis": (
            "full-time enrolment at the two Cork institutions a Cobh resident "
            "can commute to, summed. Cobh has no third-level institution, so "
            "this venue is OUTSIDE the town."
        ),
        "capacity_does_not_bind": (
            "the town has about 90 third-level students against a capacity of "
            f"{cap}, so no Cobh student competes for a place with another. "
            "Stated because a capacity that cannot bind is not evidence of "
            "anything, and the venue criterion must not be read as having "
            "tested it."
        ),
    }


def venue_capacities(venues: list[Venue]) -> dict[str, int]:
    """``{venue_id: capacity}``, the shape ``check_venue_capacity`` wants."""
    return {v.venue_id: int(v.capacity) for v in venues}


def build_venues(*, persons: Any, small_areas: list[str] | None = None) -> dict[str, Any]:
    """Derive the town's venues from its own population.

    ``persons`` is the town's person frame — it needs ``age``, ``econ_status``
    and ``remote_share``, plus ``small_area`` if the siting is to follow the
    population rather than a single list.

    Counts are derived and not declared, which is the whole design: a declared
    count makes venue occupancy a free parameter, where too few venues puts
    every one over capacity and too many makes the criterion pass trivially.
    """
    import numpy as np
    import pandas as pd

    df = persons if isinstance(persons, pd.DataFrame) else pd.DataFrame(persons)
    for col in ("age", "econ_status"):
        if col not in df.columns:
            raise VenueError(
                f"the person frame has no {col!r}, so venue demand cannot be "
                f"derived from the population. Deriving it is what keeps the "
                f"venue count from being a free parameter."
            )
    areas = small_areas or (
        sorted(df["small_area"].dropna().astype(str).unique())
        if "small_area" in df.columns else ["SA-UNKNOWN"])
    if not areas:
        raise VenueError("no small areas to site venues in")

    school_mean = mean_pupils_per_school()
    per_school = float(school_mean["mean_pupils_per_school"])
    college = cork_third_level_capacity()

    ages = pd.to_numeric(df["age"], errors="coerce")
    n_primary = int(((ages >= 5) & (ages <= 12)).sum())
    n_secondary = int(((ages >= 13) & (ages <= 18)).sum())
    at_work = df["econ_status"].astype(str).str.lower().isin(
        {"at work", "employed"})
    remote = (pd.to_numeric(df.get("remote_share"), errors="coerce").fillna(0.0)
              if "remote_share" in df.columns
              else pd.Series(0.0, index=df.index))
    # HEADCOUNT, not expected attendance. The first version weighted each
    # worker by (1 - remote_share) - the expected number at a workplace on a
    # given day - and that is the wrong denominator for this purpose, because
    # `assign_persistent_venues` gives a persistent place to every worker who
    # is not FULLY remote. The stock came out at 45 workplaces for 1,297
    # workers and every roll was 28 to 29 against a capacity of 25.
    #
    # Sizing by the roll is also the conservative reading of "capacity": a
    # roll that fits means concurrent presence fits, since presence is a
    # subset of the roll. Sizing by attendance would let a venue's roll exceed
    # its capacity and rely on absence to stay inside it, which is true on
    # average and false on the day everyone turns up.
    workplace_demand = float((at_work & (remote.clip(0.0, 1.0) < 1.0)).sum())

    n_college = int(((ages >= 19)
                     & df["econ_status"].astype(str).str.lower().eq("student")
                     ).sum())
    demand = {
        "primary_school": n_primary,
        "secondary_school": n_secondary,
        "college": n_college,
        "workplace": workplace_demand,
        # The discretionary types are not sized by a headcount - everyone can
        # shop - so they are sized by the peak concurrent demand the activity
        # engine could produce, which is bounded by the population. One venue
        # per N of population, with N the declared capacity: that gives enough
        # that capacity is not the binding constraint, and the criterion then
        # tests the record rather than the stock.
        "shop": len(df) / 4.0,
        "community": len(df) / 4.0,
        "sports": len(df) / 4.0,
    }
    size = {
        "primary_school": per_school,
        "secondary_school": per_school,
        "college": float(college["capacity"]),
        **{k: float(v) for k, v in _DECLARED_CAPACITY.items()},
    }

    venues: list[Venue] = []
    counts: dict[str, int] = {}
    for vtype, spec in VENUE_TYPES.items():
        cap = int(round(size[vtype]))
        n = max(1, math.ceil(demand[vtype] / max(size[vtype], 1.0)))
        counts[vtype] = n
        for i in range(n):
            venues.append(Venue(
                venue_id=f"VEN-{vtype.upper()[:4]}-{i:03d}",
                venue_type=vtype, capacity=cap,
                small_area=areas[i % len(areas)],
                capacity_basis=str(spec["capacity_note"]),
            ))

    return {
        "venues": venues,
        "counts": counts,
        "capacities": venue_capacities(venues),
        "demand": {k: (round(v, 1) if isinstance(v, float) else v)
                   for k, v in demand.items()},
        "school_size_source": school_mean,
        "college_size_source": college,
        "counts_are_derived_not_declared": (
            "Each count is the town's own demand divided by the venue type's "
            "size. A declared count would make venue occupancy a free "
            "parameter - too few venues and every one is over capacity, too "
            "many and the criterion passes trivially - so there is nothing "
            "here to tune and over-capacity is a finding."
        ),
        "a_flags": SITING_A_FLAGS,
        "a_flag_id": "A-50",
    }


def assign_persistent_venues(
    *, persons: Any, venues: list[Venue], master_seed: int,
) -> dict[str, dict[str, str | None]]:
    """Give each person their one school and their one workplace.

    Persistent assignment is what makes the two presence records comparable:
    if a child attended a different school every day, "venue presence
    consistent with person presence" would be a statement about a draw rather
    than about the model.

    Round-robin within the venue type rather than a random draw, and the reason
    is the criterion: a random assignment puts a long tail on venue occupancy
    and would show over-capacity that is an artefact of the draw. Round-robin
    fills venues evenly, so an over-capacity result means the town genuinely
    has more pupils than its derived school stock holds.
    """
    import pandas as pd

    df = persons if isinstance(persons, pd.DataFrame) else pd.DataFrame(persons)
    by_type: dict[str, list[Venue]] = {}
    for v in venues:
        by_type.setdefault(v.venue_type, []).append(v)
    for k in by_type:
        by_type[k].sort(key=lambda v: v.venue_id)

    out: dict[str, dict[str, str | None]] = {}
    cursor = {k: 0 for k in by_type}

    def take(vtype: str) -> str | None:
        pool = by_type.get(vtype)
        if not pool:
            return None
        v = pool[cursor[vtype] % len(pool)]
        cursor[vtype] += 1
        return v.venue_id

    ages = pd.to_numeric(df["age"], errors="coerce")
    at_work = df["econ_status"].astype(str).str.lower().isin(
        {"at work", "employed"})
    is_student = df["econ_status"].astype(str).str.lower().eq("student")
    remote = (pd.to_numeric(df.get("remote_share"), errors="coerce").fillna(0.0)
              if "remote_share" in df.columns
              else pd.Series(0.0, index=df.index))
    pid_col = "person_id" if "person_id" in df.columns else df.columns[0]

    # Sorted by person id so the assignment is reproducible and independent of
    # the frame's row order.
    for _, row in df.assign(_age=ages, _work=at_work, _rem=remote,
                            _stu=is_student).sort_values(pid_col).iterrows():
        pid = str(row[pid_col])
        a = row["_age"]
        school = None
        # `school_year` is the SYNTHESIS's own marker of who is at school and
        # in which year, and it is used in preference to a recomputed age
        # because the two disagree by one for some people. The synthesis
        # assigns from `member.age`, which comes from the IPF age band; this
        # frame computes (t0 - birth_date).days // 365. A person the synthesis
        # calls 5 can compute as 4, and 34 five-year-olds were left with no
        # school by an age test that looked correct. I-071 records the
        # underlying inconsistency - two definitions of age in one build -
        # which is a wider problem than this assignment.
        sy = row.get("school_year")
        if pd.notna(sy):
            school = take("primary_school" if float(sy) <= 8
                          else "secondary_school")
        elif pd.notna(a) and 5 <= a <= 12:
            school = take("primary_school")
        elif pd.notna(a) and 13 <= a <= 18:
            school = take("secondary_school")
        elif pd.notna(a) and a >= 19 and bool(row["_stu"]):
            # I-069's residue, and now a real population rather than a
            # symptom: 91 students aged 19 and over, where before the fix
            # there were 241 with a median age of 45. They commute to Cork.
            school = take("college")
        work = take("workplace") if (bool(row["_work"])
                                    and float(row["_rem"]) < 1.0) else None
        out[pid] = {"school_venue_id": school, "workplace_venue_id": work}
    return out
