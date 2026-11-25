"""D21 - biographies, rendered from the written D05, D06, D08 and D09 parts.

Design 5.2 step 6 asks for a narrative "generated from structured records
only, never free-written", and declares ``source_record_ids`` so that "every
sentence traces to a record".  Both of those are properties of the GENERATOR,
not of the prose, so this module is built so that they can be checked:

**1. Every sentence is a template with a citation.**  A sentence is produced by
a :class:`Sentence`, which carries the record ids it was rendered from, and the
renderer appends those ids to the sentence in square brackets.  So the
Markdown is self-citing: a reader who doubts a clause can read the id off the
end of it and go to that row.  ``source_record_ids`` is the sorted union of
the ids the sentences cited, and
``test_d21_every_cited_record_id_resolves_to_a_row`` asserts that each one is a
primary key present in the written part it names, and that the column and the
narrative agree in both directions.

**2. Nothing is said that a record does not say.**  Each sentence restates
named fields of one or more rows.  There is no adjective that is not a value,
no comparison between people, no inference from one field to another, and no
summary judgement.  Where a field is null the sentence that would have used it
is not emitted, rather than being emitted with a hedge - an absent record
produces an absent sentence, which is itself information.

**3. A biography that reads oddly is the output, not a bug.**  The declared
purpose is that a reader can catch an implausible synthetic life that no
aggregate check would notice.  So the renderer never smooths: if the records
say a person is 3 years old and in full-time employment, the biography says
both, in two plain sentences, next to each other.  Smoothing that would delete
the finding.

**The ``as_of`` dates are the dates the record changes.**  One row per person
per date on which something in that person's structured record begins, ends or
happens, bounded to the run's span, plus the run's first and last day.  A fixed
calendar would mostly produce identical rows; the change dates are where a
biography can differ from the one before it.

``cluster_label`` is declared ``forbidden`` and is written as null, which
``baile_nua.schema.validate`` enforces: design 5.13 allows no person to be
labelled by cluster.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from baile_nua.export.context import ArtefactAbsent, ExportError, RunContext
from baile_nua.export.writer import emit

__all__ = [
    "SOURCE_DATASETS",
    "PRIMARY_KEY",
    "Sentence",
    "record_id",
    "load_source_frames",
    "as_of_dates_for",
    "render_person",
    "export_d21",
]

#: The datasets a biography is rendered from, and nothing else.
SOURCE_DATASETS: tuple[str, ...] = ("D05", "D06", "D08", "D09")

#: The one that cannot be missing.  Without a person row there is no person to
#: write about; the other three each contribute a section, and a section with
#: no rows says so in the narrative rather than being dropped.  The 14-day
#: town run is the case that forced this: it stepped no life course, so it has
#: no D09 at all, and refusing to write D21 for it would have turned "this run
#: records no life events" into "this dataset is missing".
REQUIRED_SOURCE = "D05"

#: The column that identifies a row of each, so a cited id can be resolved.
PRIMARY_KEY: dict[str, str] = {
    "D05": "person_id",
    "D06": "membership_id",
    "D08": "state_id",
    "D09": "event_id",
}


def record_id(dataset_id: str, key: Any) -> str:
    """``"D08:S-000123"`` - a dataset and the primary key of one of its rows."""
    if dataset_id not in PRIMARY_KEY:
        raise ExportError(
            f"{dataset_id} has no declared primary key, so a sentence cannot "
            f"cite it. A citation that cannot be resolved is worse than none."
        )
    return f"{dataset_id}:{key}"


@dataclasses.dataclass(frozen=True)
class Sentence:
    """One rendered sentence and the record ids it was rendered from.

    ``text`` must be a restatement of named fields.  The dataclass cannot
    enforce that, but keeping the ids on the sentence rather than on the
    biography means an uncited sentence is a visible omission rather than an
    invisible one: :func:`render_person` refuses a sentence with no ids.
    """

    text: str
    ids: tuple[str, ...]

    def markdown(self) -> str:
        return f"{self.text} [{'; '.join(self.ids)}]"


# --------------------------------------------------------------------------- #
# reading the written datasets
# --------------------------------------------------------------------------- #

def _package_dir(out_root: Path, subdir: str | None, package: str) -> Path:
    base = Path(out_root) / package
    return base / subdir if subdir else base


#: The columns each source contributes, used to stand an ABSENT source up as
#: an empty frame with the right shape.  Named rather than inferred, so an
#: absent source produces an empty section and never a KeyError halfway
#: through a narrative.
_COLUMNS: dict[str, tuple[str, ...]] = {
    "D06": ("membership_id", "person_id", "household_id", "building_id",
            "valid_from", "valid_to", "role", "reason_in", "reason_out"),
    "D08": ("state_id", "person_id", "valid_from", "valid_to", "household_id",
            "role", "econ_status", "occupation_soc", "occupation_isco08",
            "industry_nace", "workplace_venue_id", "work_pattern",
            "remote_share", "school_venue_id", "school_year", "health_state",
            "caring_load", "caring_hours_week", "decision_authority",
            "vehicle_access", "income_quintile"),
    "D09": ("event_id", "event_type", "effective_at", "decided_at", "persons",
            "household_id", "building_id", "cause", "observable_effects"),
}


def load_source_frames(
    ctx: RunContext, *, out_root: Path | None = None,
) -> tuple[dict[str, pd.DataFrame], list[str]]:
    """``(frames, absent)`` - the written parts, read back from disk.

    Read back rather than rebuilt on purpose.  A biography whose claims are
    traceable has to cite the rows a reader can open, and that is what is on
    disk; rebuilding the structural state here would produce a narrative
    citing ids that match the disk only as long as the two constructions
    agree.

    A source with no part on disk is returned EMPTY and named in ``absent``,
    except :data:`REQUIRED_SOURCE`, whose absence is an
    :class:`~baile_nua.export.context.ArtefactAbsent`.
    """
    import pyarrow.parquet as pq

    root = Path(out_root) if out_root is not None else ctx.out_root
    frames: dict[str, pd.DataFrame] = {}
    absent: list[str] = []
    for dataset_id in SOURCE_DATASETS:
        paths = sorted(
            _package_dir(root, ctx.subdir, "ground_truth")
            .glob(f"{dataset_id}_part*.parquet")
        )
        if not paths:
            if dataset_id == REQUIRED_SOURCE:
                raise ArtefactAbsent(
                    f"D21 needs the written {REQUIRED_SOURCE} part and none is "
                    f"under {_package_dir(root, ctx.subdir, 'ground_truth')}. "
                    f"Without a person row there is no person to write about, "
                    f"and a biography citing ids that are not on disk would be "
                    f"untraceable - the one thing design 5.2 step 6 forbids. "
                    f"Export {REQUIRED_SOURCE} first."
                )
            absent.append(dataset_id)
            frames[dataset_id] = pd.DataFrame(
                {c: pd.Series(dtype="object") for c in _COLUMNS[dataset_id]})
            continue
        frames[dataset_id] = pd.concat(
            [pq.read_table(p).to_pandas() for p in paths], ignore_index=True)
    return frames, absent


# --------------------------------------------------------------------------- #
# which dates
# --------------------------------------------------------------------------- #

def _as_date(value: Any) -> Any:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    ts = pd.to_datetime(value, utc=True, errors="coerce")
    if ts is pd.NaT or pd.isna(ts):
        return None
    return ts.date()


def as_of_dates_for(
    person_id: str, frames: dict[str, pd.DataFrame], ctx: RunContext,
) -> list[Any]:
    """The dates this person's record changes, within the run's span.

    The run's first and last day are always included, so every person has a
    biography at the start and at the end whether anything happened to them or
    not - an uneventful life is a result too.
    """
    first = ctx.t0.date()
    last = (ctx.t0 + pd.Timedelta(days=max(ctx.n_days - 1, 0))).date()
    dates = {first, last}
    for dataset_id in ("D06", "D08"):
        rows = frames[dataset_id]
        mine = rows[rows["person_id"] == person_id]
        for col in ("valid_from", "valid_to"):
            for value in mine[col].tolist():
                d = _as_date(value)
                if d is not None:
                    dates.add(d)
    events = frames["D09"]
    for _, row in events.iterrows():
        persons = row.get("persons")
        if persons is None or person_id not in list(persons):
            continue
        for col in ("effective_at", "decided_at"):
            d = _as_date(row.get(col))
            if d is not None:
                dates.add(d)
    return sorted(d for d in dates if first <= d <= last)


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #

def _fmt(value: Any) -> str:
    """A value as the record holds it, with no rounding that hides anything."""
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return str(value)


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, tuple)):
        return len(value) > 0
    try:
        return not pd.isna(value)
    except (TypeError, ValueError):
        return True


def _interval_covers(row: pd.Series, as_of: Any) -> bool:
    start = _as_date(row.get("valid_from"))
    end = _as_date(row.get("valid_to"))
    if start is not None and as_of < start:
        return False
    if end is not None and as_of > end:
        return False
    return True


def _person_sentences(person: pd.Series, as_of: Any) -> list[Sentence]:
    pid = record_id("D05", person["person_id"])
    out: list[Sentence] = []
    birth = _as_date(person.get("birth_date"))
    name = f"{person.get('given_name')} {person.get('family_name')}"
    if birth is not None:
        age = (as_of - birth).days // 365
        out.append(Sentence(
            f"{name} ({person['person_id']}) was born on {birth.isoformat()} "
            f"and is recorded as {age} years old on {as_of.isoformat()}.",
            (pid,)))
    else:
        out.append(Sentence(
            f"{name} ({person['person_id']}) has no birth date in the record.",
            (pid,)))
    out.append(Sentence(
        f"Sex recorded: {person.get('sex')}. Country of birth: "
        f"{person.get('country_of_birth')}. Nationality: "
        f"{person.get('nationality')}. Census ethnicity category: "
        f"{person.get('ethnicity_census')}.",
        (pid,)))
    langs = person.get("other_languages")
    lang_text = f"First language: {person.get('first_language')}."
    if _present(langs):
        lang_text += f" Other languages recorded: {', '.join(map(str, langs))}."
    if _present(person.get("years_in_ireland")):
        lang_text += (
            f" Years in Ireland recorded as "
            f"{_fmt(person['years_in_ireland'])}.")
    out.append(Sentence(lang_text, (pid,)))
    if _present(person.get("education_level")):
        out.append(Sentence(
            f"Education level recorded (ISCED): {person['education_level']}.",
            (pid,)))
    if _present(person.get("death_date")):
        out.append(Sentence(
            f"A death date is recorded: "
            f"{_as_date(person['death_date']).isoformat()}.",
            (pid,)))
    return out


def _trait_sentence(person: pd.Series) -> Sentence:
    """The trait vector as values, with no adjective attached to any of them.

    Included because an implausible trait value is exactly the kind of thing
    this dataset exists to let a reader notice, and omitted of any
    interpretation because design 5.13 forbids labelling a person and because
    'strongly environmentalist' would be this module's word, not the record's.
    """
    pid = record_id("D05", person["person_id"])
    names = (
        "trans", "community", "env", "autonomy", "comfort", "conditional",
        "privacy", "instTrust", "idvZ", "satisficer", "stated_gap",
        "lambda_self", "lambda_coop", "lambda_altru",
        "big5_o", "big5_c", "big5_e", "big5_a", "big5_n",
        "chronotype", "habit_strength", "lapse_rate", "attention",
        "response_propensity",
    )
    parts = [f"{n} {_fmt(person[n])}" for n in names if n in person.index]
    return Sentence(
        "Recorded trait values, in the record's own names and scales "
        "(z-scores except where the schema declares another unit; "
        "chronotype in hours): " + ", ".join(parts) + ".",
        (pid,))


def _membership_sentences(
    memberships: pd.DataFrame, as_of: Any,
) -> list[Sentence]:
    out: list[Sentence] = []
    for _, row in memberships.iterrows():
        rid = record_id("D06", row["membership_id"])
        if not _interval_covers(row, as_of):
            continue
        start = _as_date(row.get("valid_from"))
        end = _as_date(row.get("valid_to"))
        text = (
            f"Lives in household {row['household_id']} at building "
            f"{row['building_id']} as {row['role']}, from "
            f"{start.isoformat() if start else 'an unrecorded date'}")
        text += f" to {end.isoformat()}." if end else " with no recorded end."
        if _present(row.get("reason_in")):
            text += f" Reason recorded for joining: {row['reason_in']}."
        if _present(row.get("reason_out")):
            text += f" Reason recorded for leaving: {row['reason_out']}."
        out.append(Sentence(text, (rid,)))
    return out


def _state_sentences(states: pd.DataFrame, as_of: Any) -> list[Sentence]:
    out: list[Sentence] = []
    for _, row in states.iterrows():
        if not _interval_covers(row, as_of):
            continue
        rid = record_id("D08", row["state_id"])
        out.append(Sentence(
            f"Economic status recorded as {row['econ_status']}, work pattern "
            f"{row['work_pattern']}, remote share "
            f"{_fmt(row['remote_share'])} of working days.",
            (rid,)))
        job = []
        for col, label in (
            ("occupation_soc", "occupation (SOC 2010)"),
            ("occupation_isco08", "occupation (ISCO-08)"),
            ("industry_nace", "industry (NACE rev2)"),
            ("workplace_venue_id", "workplace venue"),
        ):
            if _present(row.get(col)):
                job.append(f"{label} {row[col]}")
        if job:
            out.append(Sentence(
                "Work record: " + ", ".join(job) + ".", (rid,)))
        school = []
        for col, label in (("school_venue_id", "school venue"),
                           ("school_year", "school year")):
            if _present(row.get(col)):
                school.append(f"{label} {_fmt(row[col])}")
        if school:
            out.append(Sentence(
                "Education record: " + ", ".join(school) + ".", (rid,)))
        out.append(Sentence(
            f"Functional health state recorded as {row['health_state']} "
            f"(design U09 records generic functional states only, never "
            f"diagnoses). Caring load {row['caring_load']}, "
            f"{_fmt(row['caring_hours_week'])} caring hours a week.",
            (rid,)))
        out.append(Sentence(
            f"Vehicle access recorded as {row['vehicle_access']}; household "
            f"income quintile {_fmt(row['income_quintile'])}; decision "
            f"authority within the household "
            f"{_fmt(row['decision_authority'])} on a 0-to-1 scale.",
            (rid,)))
    return out


def _event_sentences(
    events: pd.DataFrame, person_id: str, as_of: Any,
) -> tuple[list[Sentence], list[Sentence]]:
    """``(events up to as_of, events after it)``.

    The future ones are rendered too, under their own heading: a record that
    says a person will move in 143 days after the decision is a fact of the
    dataset, and hiding it would make the biography a worse instrument for
    spotting an implausible life course.
    """
    past: list[Sentence] = []
    future: list[Sentence] = []
    for _, row in events.iterrows():
        persons = row.get("persons")
        if persons is None or person_id not in list(persons):
            continue
        rid = record_id("D09", row["event_id"])
        eff = _as_date(row.get("effective_at"))
        dec = _as_date(row.get("decided_at"))
        text = (
            f"{row['event_type']}, effective "
            f"{eff.isoformat() if eff else 'on an unrecorded date'}")
        if dec is not None:
            text += f", decided {dec.isoformat()}"
        if _present(row.get("household_id")):
            text += f", household {row['household_id']}"
        if _present(row.get("building_id")):
            text += f", building {row['building_id']}"
        text += f". Cause recorded: {row['cause']}."
        others = [p for p in list(persons) if p != person_id]
        if others:
            text += f" Other persons on the event: {', '.join(others)}."
        sentence = Sentence(text, (rid,))
        (past if eff is not None and eff <= as_of else future).append(sentence)
    return past, future


def render_person(
    person_id: str, as_of: Any, frames: dict[str, pd.DataFrame], ctx: RunContext,
) -> dict[str, Any]:
    """One D21 row: the Markdown, and the ids every sentence in it cited."""
    people = frames["D05"]
    match = people[people["person_id"] == person_id]
    if match.empty:
        raise ExportError(
            f"{person_id} is not a row of the written D05, so there is no "
            f"record to render. A biography for a person the dataset does not "
            f"carry would cite an id that resolves to nothing."
        )
    person = match.iloc[0]
    memberships = frames["D06"][frames["D06"]["person_id"] == person_id]
    states = frames["D08"][frames["D08"]["person_id"] == person_id]
    past, future = _event_sentences(frames["D09"], person_id, as_of)

    sections: list[tuple[str, list[Sentence]]] = [
        ("Person", _person_sentences(person, as_of)),
        ("Household", _membership_sentences(memberships, as_of)),
        ("State on this date", _state_sentences(states, as_of)),
        ("Life events recorded on or before this date", past),
        ("Life events recorded after this date", future),
        ("Trait vector as recorded", [_trait_sentence(person)]),
    ]

    lines = [
        f"# {person.get('given_name')} {person.get('family_name')} "
        f"({person_id}) as of {as_of.isoformat()}",
        "",
        "*UNVALIDATED SIMULATION EVIDENCE. Generated from the written D05, "
        "D06, D08 and D09 rows cited in square brackets after each sentence; "
        "no sentence states anything those rows do not. A biography that "
        "reads oddly is evidence about the model and has not been smoothed.*",
        "",
    ]
    ids: set[str] = set()
    for heading, sentences in sections:
        if not sentences:
            lines += [f"## {heading}", "", "No record covers this date.", ""]
            continue
        lines.append(f"## {heading}")
        lines.append("")
        for sentence in sentences:
            if not sentence.ids:
                raise ExportError(
                    f"D21/{person_id}/{as_of}: a sentence was rendered with no "
                    f"record id. Every sentence traces to a record (design 5.2 "
                    f"step 6), so an uncited sentence is refused rather than "
                    f"written."
                )
            lines.append(f"- {sentence.markdown()}")
            ids.update(sentence.ids)
        lines.append("")

    return {
        "person_id": person_id,
        "as_of": as_of,
        "narrative_md": "\n".join(lines).rstrip() + "\n",
        "source_record_ids": sorted(ids),
        "cluster_label": None,
    }


def export_d21(ctx: RunContext) -> dict[str, Any]:
    """A biography per person per date on which that person's record changes."""
    frames, absent = load_source_frames(ctx)
    rows: list[dict[str, Any]] = []
    for person_id in sorted(frames["D05"]["person_id"].tolist()):
        for as_of in as_of_dates_for(person_id, frames, ctx):
            rows.append(render_person(person_id, as_of, frames, ctx))
    if not rows:
        raise ExportError(
            "D21: the written D05 carries no person, so no biography could be "
            "rendered."
        )
    frame = pd.DataFrame(rows)
    n_ids = int(frame["source_record_ids"].map(len).sum())

    # How many D09 rows can be cited at all.  Computed rather than assumed,
    # because on the estate-year it is ZERO: D09 as exported is the TOWN's
    # ten-year life course (2022-2031, households outside the estate) while
    # D05, D06 and D08 are the 50-home estate slice, so the two carry no
    # person in common and no biography can cite a life event. That is a
    # referential finding about the package, recorded here and in
    # docs/ISSUES.md, and it is left visible in the narratives as "No record
    # covers this date" rather than hidden by dropping the section.
    people = set(frame["person_id"])
    d09_persons: set[str] = set()
    for value in frames["D09"]["persons"].tolist():
        if value is not None:
            d09_persons.update(map(str, list(value)))
    citable = sorted(d09_persons & people)
    limitations = [
        "A sentence whose field is null is not emitted, so an absent "
        "record shows as an absent sentence rather than a hedge.",
        "Nothing is interpreted: no comparison between people, no "
        "inference across fields, no summary judgement. A trait value is "
        "reported as a number in the schema's own name and scale.",
        "cluster_label is declared forbidden and is written null (5.13).",
        "The narrative is not smoothed. An implausible life reads as an "
        "implausible life, which is the dataset's declared purpose.",
    ]
    if absent:
        limitations.append(
            f"Source dataset(s) {absent} have no part on disk for this "
            f"target, so the sections they feed read 'No record covers this "
            f"date' in every narrative. The 14-day town run stepped no life "
            f"course and therefore has no D09 at all: that is a property of "
            f"the run and it is reported, not filled in."
        )
    if "D09" not in absent and not citable:
        limitations.append(
            f"NO life event is citable on this target: the written D09 names "
            f"{len(d09_persons)} persons and the written D05 names "
            f"{len(people)}, and the two sets are DISJOINT. D09 as exported "
            f"is the town's ten-year life course and D05/D06/D08 are the "
            f"estate slice, so every biography's life-event sections read 'No "
            f"record covers this date'. That is a referential gap in the "
            f"package, not a gap in this generator, and it is left visible."
        )
    return emit(
        frame, "D21", ctx,
        source=(
            "the written D05, D06, D08 and D09 parts, read back from "
            f"{_package_dir(ctx.out_root, ctx.subdir, 'ground_truth')}"
        ),
        conversions=[
            {"field": "narrative_md",
             "from": "templated restatement of named fields of the cited rows",
             "note": "no sentence is free-written; every one is a template"},
            {"field": "source_record_ids",
             "from": "the ids the sentences cited, as <dataset>:<primary key>",
             "note": ("the same ids appear inline in narrative_md in square "
                      "brackets, so the Markdown is self-citing and the "
                      "column and the prose can be checked against each "
                      "other in both directions")},
            {"field": "as_of",
             "from": ("the dates this person's D06/D08 intervals begin or end "
                      "and their D09 events fire, bounded to the run's span, "
                      "plus the run's first and last day")},
        ],
        limitations=limitations,
        extra={
            "d21_source_datasets": list(SOURCE_DATASETS),
            "d21_primary_keys": PRIMARY_KEY,
            "d21_n_citations": n_ids,
            "d21_n_persons": int(frame["person_id"].nunique()),
            "d21_n_as_of_dates": int(frame["as_of"].nunique()),
            "d21_n_d05_persons": len(people),
            "d21_n_d09_persons": len(d09_persons),
            "d21_n_persons_with_a_citable_life_event": len(citable),
            "d21_absent_source_datasets": list(absent),
        },
    )
