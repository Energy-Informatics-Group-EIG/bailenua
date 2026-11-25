"""Synthetic names (design 5.2 step 6, R26, R27, risk K12).

Design 5.2 step 6:

    Draw first names by birth year and origin from CSO baby-name tables and
    equivalent national lists, and surnames from origin-matched lists.  Reject
    any full-name combination that matches a public-figure list or appears more
    than once in town.

R27: identities are explicitly synthetic, do not reproduce real people, preserve
diversity and avoid deterministic stereotyping.  K12 (likelihood Low, impact
High): synthetic names resembling real Cobh residents.

**Given names** come from the real CSO tables VSA50 (boys) and VSA60 (girls),
which give every name registered three or more times in each year from 1964 to
2025, with counts.  A person born in 1987 therefore draws from the names that
were actually common in 1987, which is what makes a name age-appropriate without
anyone writing down a rule about it.

**Surnames are drawn uniformly, on purpose.**  No public Irish surname frequency
table was found (I-014), so there is no source for surname frequencies, and the
brief forbids inventing one from memory.  A uniform draw is also the *safer*
direction for R27 and K12: matching real surname frequencies would make the
synthetic population's name distribution resemble the real town's, and the
requirement is the opposite.  The consequence - Baile Nua's surname frequencies
do not match Ireland's - is recorded as a known limitation rather than hidden,
and is irrelevant to every energy or behaviour claim.

**Two rejection rules**, both hard:

* no full name may occur twice in the town;
* no full name may match the public-figure list.

The public-figure list is handled by *construction* as well as by filtering: a
name is rejected if its ``given + family`` pair matches the list, and the list
itself is kept in the repository with its provenance.
"""

from __future__ import annotations

import csv
import dataclasses
import functools
import unicodedata
from pathlib import Path
from typing import Any

import numpy as np

from baile_nua.rng import SeedTree, Stream
from baile_nua.sources import require

__all__ = [
    "NameDraw",
    "NameGenerator",
    "given_name_table",
    "normalise_name",
    "PUBLIC_FIGURE_PATH",
    "SURNAME_POOL_PATH",
    "GIVEN_NAME_POOL_PATH",
    "given_names_by_origin",
    "NameExhaustedError",
]

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
PUBLIC_FIGURE_PATH = DATA_DIR / "public_figures.txt"
SURNAME_POOL_PATH = DATA_DIR / "surnames_by_origin.csv"
GIVEN_NAME_POOL_PATH = DATA_DIR / "given_names_by_origin.csv"

#: The CSO tables start in 1964.  A person born before that draws from the
#: earliest available year rather than from nothing; the substitution is
#: recorded on the draw so it appears in the evidence view.
CSO_FIRST_YEAR = 1964


class NameExhaustedError(RuntimeError):
    """The name space ran out before every person could get a unique full name."""


def normalise_name(s: str) -> str:
    """Case- and accent-insensitive key for uniqueness and public-figure checks.

    Without accent folding, "Síle Ní Bhriain" and "Sile Ni Bhriain" would count
    as different names, which would defeat both checks on exactly the Irish names
    most likely to be affected.
    """
    s = unicodedata.normalize("NFKD", s.strip().lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.split())


# --------------------------------------------------------------------------- #
# Given names from the CSO tables
# --------------------------------------------------------------------------- #

@functools.lru_cache(maxsize=2)
def given_name_table(sex: str) -> dict[int, tuple[tuple[str, ...], np.ndarray]]:
    """``{birth_year: (names, probabilities)}`` from the real CSO table.

    The CSO file is long-format with one row per (year, name, statistic); only
    the *count* statistic is used, and the rank statistic is skipped, because
    both appear in the same file under different ``STATISTIC`` codes.
    """
    if sex not in ("M", "F"):
        raise ValueError(f"sex must be 'M' or 'F', got {sex!r}")
    key = "cso.babynames.boys" if sex == "M" else "cso.babynames.girls"
    path = require(key)
    name_col = "Boys Names" if sex == "M" else "Girls Names"
    # Counts live under the '...C01' statistic; ranks under '...C02'.
    count_stat_suffix = "C01"

    per_year: dict[int, dict[str, float]] = {}
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            stat = (row.get("STATISTIC") or "").strip()
            if not stat.endswith(count_stat_suffix):
                continue
            raw = (row.get("VALUE") or "").strip()
            if not raw:
                continue
            try:
                count = float(raw)
                year = int(row["Year"])
            except (TypeError, ValueError):
                continue
            if count <= 0:
                continue
            name = (row.get(name_col) or "").strip()
            # Reject initials and punctuation-only entries such as "A J", "A.J."
            if len(name) < 2 or any(ch in name for ch in ".") or " " in name:
                continue
            per_year.setdefault(year, {})[name] = per_year.setdefault(year, {}).get(name, 0.0) + count

    out: dict[int, tuple[tuple[str, ...], np.ndarray]] = {}
    for year, counts in per_year.items():
        # Sorted for determinism: dict order must never reach a probability vector.
        names = tuple(sorted(counts))
        weights = np.array([counts[n] for n in names], dtype=np.float64)
        out[year] = (names, weights / weights.sum())
    if not out:
        raise RuntimeError(
            f"no usable rows parsed from {path}; the CSO column layout may have changed"
        )
    return out


# --------------------------------------------------------------------------- #
# Surnames and the public-figure list
# --------------------------------------------------------------------------- #

@functools.lru_cache(maxsize=1)
def surname_pool() -> dict[str, tuple[str, ...]]:
    """``{origin_group: surnames}`` from the repository data file."""
    if not SURNAME_POOL_PATH.is_file():
        raise FileNotFoundError(
            f"surname pool missing at {SURNAME_POOL_PATH}; see I-014"
        )
    pool: dict[str, list[str]] = {}
    with open(SURNAME_POOL_PATH, newline="", encoding="utf-8") as fh:
        # The file leads with a provenance header (I-014); comments are stripped
        # before the CSV reader sees them so the header row is the real one.
        lines = [ln for ln in fh if not ln.lstrip().startswith("#") and ln.strip()]
    for row in csv.DictReader(lines):
        group = (row.get("origin_group") or "").strip()
        surname = (row.get("surname") or "").strip()
        if group and surname:
            pool.setdefault(group, []).append(surname)
    if not pool:
        raise RuntimeError(f"no surnames parsed from {SURNAME_POOL_PATH}")
    return {k: tuple(sorted(set(v))) for k, v in sorted(pool.items())}


@functools.lru_cache(maxsize=1)
def given_names_by_origin() -> dict[tuple[str, str], tuple[str, ...]]:
    """``{(origin_group, sex): given_names}`` for NON-Irish origins.

    Origin IE is served by the real CSO year-by-year tables instead, so it is
    absent here by design.  See I-014 for why these are unweighted.
    """
    if not GIVEN_NAME_POOL_PATH.is_file():
        raise FileNotFoundError(
            f"origin given-name pool missing at {GIVEN_NAME_POOL_PATH}; see I-014"
        )
    with open(GIVEN_NAME_POOL_PATH, newline="", encoding="utf-8") as fh:
        lines = [ln for ln in fh if not ln.lstrip().startswith("#") and ln.strip()]
    pool: dict[tuple[str, str], list[str]] = {}
    for row in csv.DictReader(lines):
        g = (row.get("origin_group") or "").strip()
        sx = (row.get("sex") or "").strip()
        nm = (row.get("given_name") or "").strip()
        if g and sx and nm:
            pool.setdefault((g, sx), []).append(nm)
    if not pool:
        raise RuntimeError(f"no given names parsed from {GIVEN_NAME_POOL_PATH}")
    return {k: tuple(sorted(set(v))) for k, v in sorted(pool.items())}


@functools.lru_cache(maxsize=1)
def public_figures() -> frozenset[str]:
    """Normalised full names that must never be generated."""
    if not PUBLIC_FIGURE_PATH.is_file():
        raise FileNotFoundError(
            f"public-figure list missing at {PUBLIC_FIGURE_PATH}; R27 and K12 "
            f"require the check, so its absence must fail rather than pass silently"
        )
    names = set()
    for line in PUBLIC_FIGURE_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        names.add(normalise_name(line))
    return frozenset(names)


# --------------------------------------------------------------------------- #
# Generation
# --------------------------------------------------------------------------- #

@dataclasses.dataclass(frozen=True)
class NameDraw:
    given_name: str
    family_name: str
    #: Which CSO year the given name was drawn from (may differ from birth year
    #: when the person was born before the table starts).
    name_year_used: int
    birth_year: int
    origin_group: str
    attempts: int
    #: True where the birth year predates the CSO table and the earliest year
    #: was substituted.  Surfaced so the evidence view can report how many.
    year_substituted: bool

    @property
    def full_name(self) -> str:
        return f"{self.given_name} {self.family_name}"


class NameGenerator:
    """Draws unique, culturally and age-appropriate synthetic names.

    Stateful only in the set of names already used, which is what uniqueness
    requires.  The *draws* are not stateful: each person's candidate sequence is
    a function of their person id alone, so a name does not depend on how many
    people were generated before them, and a re-run in a different order gives
    each person the same first-choice candidate.  Collisions are then resolved by
    advancing that person's own candidate index, so the only order dependence is
    which of two colliding people keeps the name - and that is resolved by
    generating in sorted person-id order.
    """

    #: Candidates tried per person before giving up.  Generous: with ~2,900
    #: people against hundreds of given names times hundreds of surnames, a
    #: collision beyond a handful of attempts means something is wrong.
    MAX_ATTEMPTS = 200

    def __init__(self, seed_tree: SeedTree) -> None:
        self._tree = seed_tree
        self._used: set[str] = set()
        self._figures = public_figures()
        self._surnames = surname_pool()
        self._given_by_origin = given_names_by_origin()
        self._rejections: dict[str, int] = {
            "duplicate_in_town": 0,
            "public_figure_match": 0,
        }

    @property
    def rejections(self) -> dict[str, int]:
        return dict(self._rejections)

    def _origin_key(self, origin_group: str) -> str:
        if origin_group in self._surnames:
            return origin_group
        if "other" in self._surnames:
            return "other"
        raise KeyError(
            f"no surname pool for origin group {origin_group!r} and no 'other' "
            f"fallback; pools: {sorted(self._surnames)}"
        )

    def draw(
        self, person_id: str, *, sex: str, birth_year: int, origin_group: str
    ) -> NameDraw:
        """Draw a name appropriate to this person's sex, birth year and origin.

        Origin matters as much as birth year: a Polish-born resident with an
        Irish given name drawn from the CSO table would be a visible synthetic
        tell and would misrepresent Cobh's actual mix. So origin IE uses the real
        CSO year-by-year frequencies, and every other origin group uses its own
        pool (unweighted and year-independent - see I-014).
        """
        okey = self._origin_key(origin_group)
        surnames = self._surnames[okey]

        year_used = birth_year
        substituted = False
        probs: np.ndarray | None = None
        if okey == "IE" or (okey, sex) not in self._given_by_origin:
            table = given_name_table(sex)
            if birth_year not in table:
                # Nearest available year, so a 1950-born person gets 1964's names
                # rather than none. Recorded on the draw.
                year_used = min(sorted(table), key=lambda y: abs(y - birth_year))
                substituted = True
            names, probs = table[year_used]
        else:
            names = self._given_by_origin[(okey, sex)]

        gen = self._tree.generator(Stream.PERSON_NAMES, entity=person_id, sim_day=0)
        for attempt in range(self.MAX_ATTEMPTS):
            given = (
                str(gen.choice(names, p=probs))
                if probs is not None
                else str(names[int(gen.integers(0, len(names)))])
            )
            family = str(surnames[int(gen.integers(0, len(surnames)))])
            key = normalise_name(f"{given} {family}")
            if key in self._figures:
                self._rejections["public_figure_match"] += 1
                continue
            if key in self._used:
                self._rejections["duplicate_in_town"] += 1
                continue
            self._used.add(key)
            return NameDraw(
                given_name=given,
                family_name=family,
                name_year_used=year_used,
                birth_year=birth_year,
                origin_group=okey,
                attempts=attempt + 1,
                year_substituted=substituted,
            )
        raise NameExhaustedError(
            f"could not find a unique, non-public-figure name for {person_id} in "
            f"{self.MAX_ATTEMPTS} attempts (sex={sex}, birth_year={birth_year}, "
            f"origin={origin_group}). Pool sizes: {len(names)} given x "
            f"{len(surnames)} surnames."
        )

    def report(self) -> dict[str, Any]:
        return {
            "n_names_issued": len(self._used),
            "rejections": self.rejections,
            "n_public_figures_on_list": len(self._figures),
            "surname_pool_sizes": {k: len(v) for k, v in self._surnames.items()},
            "surname_draw": "uniform within origin group (see I-014)",
            "given_name_source": {
                "IE": "CSO VSA50/VSA60, real frequencies, by birth year",
                "other origins": "unweighted origin pool, year-independent (I-014)",
            },
            "origin_given_name_pool_sizes": {
                f"{g}/{s_}": len(v) for (g, s_), v in self._given_by_origin.items()
            },
        }
