#!/usr/bin/env python3
"""Regenerate the Obsidian vault at ``vault/`` from the repository.

One note per entity, each with YAML frontmatter and ``[[wikilinks]]`` to the
entities it touches, so Obsidian's graph view is the project's own dependency
graph rather than a drawing of it.

Rules this script holds to, because the vault is published to a human and read
by one:

* **Read-only everywhere but ``vault/``.**  Every input is opened for reading.
  The only writes are inside ``vault/``, and the only deletions are of files
  ``vault/`` already holds that carry this script's own ``generated_by`` stamp.
* **No secrets.**  Every string taken from a repository file passes through
  :func:`scrub`, whose patterns are the ones the release gate already uses
  (``scripts/replay_supervisor.py:139``) plus e-mail addresses and long opaque
  tokens.  The finished vault is re-scanned before this script exits, and a hit
  is a failure rather than a warning.
* **No code bodies.**  A module note carries its path and the first line of its
  docstring.  Nothing else from a ``.py`` file reaches the vault: the docstring
  is read with :mod:`ast`, so no module is imported or executed.
* **Nothing invented.**  Where an input does not exist, or does not say what
  the vault wants to say, the note records the absence.  Phrases lifted from
  the playbook are verified to be present in it before they are used, and a
  phrase that is not found is marked rather than written as fact.
* **Idempotent.**  Iteration is sorted and every value is derived, so a re-run
  over unchanged inputs produces byte-identical files.  Re-run it after each
  completed year: the year notes pick up ``DONE.json`` as it appears.

Usage::

    ./scripts/.venv/bin/python scripts/build_vault.py [--vault DIR] [--quiet]

B-D-001, B-D-002, B-D-003.
"""

from __future__ import annotations

import argparse
import ast
import dataclasses
import datetime as dt
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import yaml

# --------------------------------------------------------------------------- #
# Where things are.
# --------------------------------------------------------------------------- #

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
DOCS = ROOT / "docs"

#: ``PLAYBOOK_v3.1.md`` is not tracked in git, so a worktree does not carry it.
#: It is searched for, in order, and the vault records which copy was read.  The
#: last candidate is the live tree, read-only and at the repository root only -
#: never ``work/replay_2015_2026/``, which belongs to a running process.
PLAYBOOK_CANDIDATES = (
    ROOT / "PLAYBOOK_v3.1.md",
    DOCS / "PLAYBOOK_v3.1.md",
    Path("/Users/brianoregan/Desktop/HRSD_Occupants/PLAYBOOK_v3.1.md"),
)

DATASETS_YAML = SCRIPTS / "baile_nua" / "schema" / "datasets.yaml"
DATASETS_MD = ROOT / "DATASETS.md"
DECISIONS_MD = DOCS / "DECISIONS.md"
ISSUES_MD = DOCS / "ISSUES.md"
SOURCES_DIR = ROOT / "sources"
SOURCES_MD = SOURCES_DIR / "SOURCES.md"
DISPATCH_PY = SCRIPTS / "baile_nua" / "export" / "dispatch.py"
REPLAY_CONFIG = SCRIPTS / "replay_config.json"
REPLAY_ROOT = ROOT / "work" / "replay_2015_2026"

GENERATED_BY = "scripts/build_vault.py"

YEARS = tuple(range(2015, 2027))

# --------------------------------------------------------------------------- #
# Scrubbing.  Patterns 1-3 are the release gate's own (replay_supervisor.py:139)
# so that the vault cannot pass a check the packages would fail; 4-6 are added
# because a note is prose and carries things a parquet part never would.
# --------------------------------------------------------------------------- #

SECRET_PATTERNS = (
    re.compile(r"(?i)\b(api[_-]?key|apikey|secret|password|passwd|token|"
               r"access[_-]?key|auth[_-]?token)\b\s*[=:]\s*\S{6,}"),
    re.compile(r"\b(AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{20,}|"
               r"sk-[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{10,})"),
    re.compile(r"://[^/\s:]+:[^/\s@]+@"),
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    # An opaque run of 40+ base64/hex characters: a key, a full digest or a
    # blob.  `_`, `-` and `/` are excluded from the run so that a long file
    # path or snake_case identifier is not a false positive; the digest
    # PREFIXES this script emits are 12 characters, well under the bar anyway.
    re.compile(r"(?<![A-Za-z0-9+/=])[A-Za-z0-9+=]{40,}"),
    # Host shapes that only appear in this repo inside credential discussions.
    re.compile(r"(?i)\b[a-z0-9.-]*\b(?:blacknight|cp\.blacknight)\b[a-z0-9.-]*"),
)

_SCRUB_HITS: list[str] = []


def scrub(text: str | None) -> str:
    """Return *text* with anything secret-shaped replaced, collapsed to a line."""
    if not text:
        return ""
    out = " ".join(str(text).split())
    for rx in SECRET_PATTERNS:
        out, n = rx.subn("[redacted]", out)
        if n:
            _SCRUB_HITS.append(rx.pattern[:40])
    return out


def clip(text: str, limit: int) -> str:
    """Scrub, then cut on a word boundary with an ellipsis if it was cut."""
    s = scrub(text)
    if len(s) <= limit:
        return s
    cut = s[:limit].rsplit(" ", 1)[0]
    return cut + " …"


def unmd(text: str) -> str:
    """Strip the markdown that would not survive being re-embedded in a note."""
    # HTML only: a <PLACEHOLDER> in the prose is content, not markup.
    s = re.sub(r"</?[a-z][^>]*>", "", text or "")
    s = s.replace("**", "").replace("`", "")
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    return " ".join(s.split())


# --------------------------------------------------------------------------- #
# Notes.
# --------------------------------------------------------------------------- #


@dataclasses.dataclass
class Note:
    """One vault note.  ``name`` is what a ``[[wikilink]]`` resolves to."""

    name: str
    folder: str
    kind: str
    note_id: str
    status: str
    tags: list[str]
    extra: dict[str, Any] = dataclasses.field(default_factory=dict)
    body: list[str] = dataclasses.field(default_factory=list)
    heading: str = ""

    @property
    def path(self) -> Path:
        return Path(self.folder) / f"{safe_filename(self.name)}.md"


_ILLEGAL = re.compile(r'[\\/:*?"<>|#^\[\]]')


def safe_filename(name: str) -> str:
    """A note name that every filesystem and Obsidian itself will accept."""
    return _ILLEGAL.sub("-", name).strip() or "untitled"


class Vault:
    """Collects notes, resolves links, writes the tree."""

    def __init__(self) -> None:
        self.notes: dict[str, Note] = {}
        self.unresolved: list[tuple[str, str]] = []
        self.link_count = 0

    # -- building -------------------------------------------------------- #

    def add(self, note: Note) -> Note:
        if note.name in self.notes:
            raise ValueError(f"duplicate note name {note.name!r}")
        self.notes[note.name] = note
        return note

    def has(self, name: str) -> bool:
        return name in self.notes

    def link(self, name: str, label: str | None = None, *, origin: str = "") -> str:
        """``[[name|label]]`` if *name* is a real note, else a plain mention."""
        if name in self.notes:
            self.link_count += 1
            return f"[[{safe_filename(name)}|{label}]]" if label else f"[[{safe_filename(name)}]]"
        self.unresolved.append((origin, name))
        return label or name

    def links(self, names: Iterable[str], *, origin: str = "") -> str:
        got = [self.link(n, origin=origin) for n in dict.fromkeys(n for n in names if n)]
        return ", ".join(got) if got else "—"

    # -- writing --------------------------------------------------------- #

    def render(self, note: Note) -> str:
        fm: dict[str, Any] = {
            "type": note.kind,
            "id": note.note_id,
            "status": note.status,
            "tags": sorted(set(note.tags)),
        }
        for key, value in note.extra.items():
            if value not in (None, "", [], {}):
                fm[key] = value
        fm["generated_by"] = GENERATED_BY
        lines = ["---", *yaml_block(fm), "---", ""]
        lines.append(f"# {note.heading or note.name}")
        lines.append("")
        lines.extend(note.body)
        text = "\n".join(lines).rstrip() + "\n"
        return text

    def write(self, root: Path) -> tuple[int, int, list[str]]:
        """Write every note under *root*.  Returns (written, removed, kept)."""
        root.mkdir(parents=True, exist_ok=True)
        wanted = {note.path: self.render(note) for note in self.notes.values()}
        removed, kept = 0, []
        for existing in sorted(root.rglob("*.md")):
            rel = existing.relative_to(root)
            if rel in wanted:
                continue
            head = existing.read_text(encoding="utf-8", errors="replace")[:2000]
            if GENERATED_BY in head:
                existing.unlink()
                removed += 1
            else:
                kept.append(str(rel))
        for rel, text in sorted(wanted.items()):
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists() or target.read_text(encoding="utf-8") != text:
                target.write_text(text, encoding="utf-8")
        for folder in sorted(root.rglob("*"), reverse=True):
            if folder.is_dir() and not any(folder.iterdir()):
                folder.rmdir()
        return len(wanted), removed, kept


def yaml_block(data: dict[str, Any]) -> list[str]:
    """A tiny, deterministic YAML emitter.  Scalars are JSON, so always valid."""
    out: list[str] = []
    for key, value in data.items():
        if isinstance(value, list):
            if not value:
                out.append(f"{key}: []")
            else:
                out.append(f"{key}:")
                out.extend(f"  - {json.dumps(scrub(str(v)))}" for v in value)
        elif isinstance(value, bool):
            out.append(f"{key}: {str(value).lower()}")
        elif isinstance(value, (int, float)):
            out.append(f"{key}: {value}")
        else:
            out.append(f"{key}: {json.dumps(scrub(str(value)))}")
    return out


# --------------------------------------------------------------------------- #
# Identifier harvesting.  IDs are all that crosses from a document body into a
# note, which is what keeps bodies - and anything a body might quote - out.
# --------------------------------------------------------------------------- #

RX_DATASET = re.compile(r"\bD(?:0[1-9]|1[0-9]|2[0-9]|3[01])(_aggregate)?\b")
RX_DECISION = re.compile(r"\bD-\d{3}[a-z]?\b")
RX_ISSUE = re.compile(r"\bI-\d{3}\b")
RX_ASSUMPTION = re.compile(r"\bA-\d{2}[a-f]?\b")
RX_GATE = re.compile(r"\bG(?:[0-9]|1[0-9]|20)\b")
RX_PYPATH = re.compile(r"\b((?:[a-z_][a-z0-9_]*/)*[a-z_][a-z0-9_]*\.py)\b")
RX_E0 = re.compile(r"\bE0-\d\b")


def ids_in(text: str) -> dict[str, list[str]]:
    """Every entity identifier a block of text names, de-duplicated and sorted."""
    t = text or ""
    return {
        "datasets": sorted({m.group(0) for m in RX_DATASET.finditer(t)}),
        "decisions": sorted({m.group(0) for m in RX_DECISION.finditer(t)}),
        "issues": sorted({m.group(0) for m in RX_ISSUE.finditer(t)}),
        "assumptions": sorted({m.group(0) for m in RX_ASSUMPTION.finditer(t)}),
        "gates": sorted({m.group(0) for m in RX_GATE.finditer(t)}),
        "e0": sorted({m.group(0) for m in RX_E0.finditer(t)}),
        "modules": sorted({m.group(1) for m in RX_PYPATH.finditer(t)}),
    }


# --------------------------------------------------------------------------- #
# Inputs: the schema.
# --------------------------------------------------------------------------- #


def load_schema() -> dict[str, Any]:
    return yaml.safe_load(DATASETS_YAML.read_text(encoding="utf-8"))


def key_owners(datasets: dict[str, Any]) -> dict[str, str]:
    """``key -> the dataset that declares the entity``, derived, not listed.

    Two derivations, in order:

    1. a field carrying an ``id_prefix`` declares that entity (the schema's own
       ``id_prefixes`` block is what the prefixes mean);
    2. otherwise, a dataset whose FIRST declared field is the key and whose
       ``grain`` names the same entity declares it - which is how ``feature_id``,
       ``signature_id``, ``participant_id`` and ``device_id`` are rooted.

    One key resists both: ``premises_id``.  Its owner is taken from DATASETS.md
    Appendix B, which states it in prose - "a ``household_id``, which occupies a
    ``building_id``, which is metered as a ``premises_id``" - so D02 is the last
    ground-truth dataset on the chain before the meter boundary.
    """
    owners: dict[str, str] = {}
    for ds_id in sorted(datasets):
        for field in datasets[ds_id].get("fields") or []:
            if field.get("id_prefix"):
                owners.setdefault(field["name"], ds_id)
    owners.setdefault("premises_id", "D02")  # Appendix B, in prose.
    for ds_id in sorted(datasets):
        fields = datasets[ds_id].get("fields") or []
        if not fields:
            continue
        first = fields[0]["name"]
        if not first.endswith("_id") or first in owners:
            continue
        entity = first[: -len("_id")]
        grain = str(datasets[ds_id].get("grain") or "").lower()
        if entity in grain or entity.replace("_", " ") in grain:
            owners.setdefault(first, ds_id)
    return owners


# --------------------------------------------------------------------------- #
# Inputs: DATASETS.md.
# --------------------------------------------------------------------------- #

RX_DS_HEADING = re.compile(r"^## (D\d{2}(?:_aggregate)?) · (.+)$")
RX_FACT_ROW = re.compile(r"^\|\s*([^|]+?)\s*\|\s*(.*?)\s*\|$")
RX_JOIN_BULLET = re.compile(r"^- `([a-z_0-9]+)`\s*→\s*(.+)$")


def parse_datasets_md() -> dict[str, dict[str, Any]]:
    """Per-dataset facts, key points, on-disk joins and named modules."""
    if not DATASETS_MD.exists():
        return {}
    lines = DATASETS_MD.read_text(encoding="utf-8").splitlines()
    starts: list[tuple[int, str, str]] = []
    for i, line in enumerate(lines):
        m = RX_DS_HEADING.match(line)
        if m:
            starts.append((i, m.group(1), m.group(2)))
    out: dict[str, dict[str, Any]] = {}
    for idx, (start, ds_id, title) in enumerate(starts):
        end = starts[idx + 1][0] if idx + 1 < len(starts) else len(lines)
        block = lines[start + 1: end]
        rec: dict[str, Any] = {"title": unmd(title), "facts": {}, "key_points": [],
                               "joins": [], "modules": [], "lead": ""}
        section = "lead"
        for raw in block:
            line = raw.rstrip()
            label = line.strip().strip("*")
            if line.startswith("**") and label in (
                    "Key points", "Facts", "Joins", "Validation"):
                section = label.lower().replace(" ", "_")
                continue
            if line.startswith("**Schema**") or line.startswith("**Sample**"):
                section = "ignore"
                continue
            if section == "lead" and line.strip() and not line.startswith("<"):
                if not rec["lead"]:
                    rec["lead"] = unmd(line)
            elif section == "key_points" and line.startswith("- "):
                rec["key_points"].append(unmd(line[2:]))
            elif section == "facts":
                m = RX_FACT_ROW.match(line)
                if m and m.group(1) and not set(m.group(1)) <= set("- "):
                    rec["facts"][unmd(m.group(1))] = unmd(m.group(2))
            elif section == "joins" and line.startswith("- "):
                m = RX_JOIN_BULLET.match(line)
                if m:
                    rec["joins"].append((m.group(1), unmd(m.group(2))))
                else:
                    rec["joins"].append(("", unmd(line[2:])))
            elif section == "validation":
                rec["modules"].extend(
                    m.group(1) for m in RX_PYPATH.finditer(line))
        rec["modules"] = sorted(set(rec["modules"]))
        out[ds_id] = rec
    return out


def parse_appendix_b() -> dict[str, Any]:
    """The keys Appendix B's diagram names, and the appendix's own prose note."""
    if not DATASETS_MD.exists():
        return {"keys": [], "present": False}
    text = DATASETS_MD.read_text(encoding="utf-8")
    m = re.search(r"## Appendix B · Keys and joins(.*?)(?=\n## )", text, re.S)
    if not m:
        return {"keys": [], "present": False}
    block = m.group(1)
    keys = sorted({k for k in re.findall(r"\b([a-z_]+_id|small_area|timestamp)\b", block)})
    return {"keys": keys, "present": True}


# --------------------------------------------------------------------------- #
# Inputs: sources.
# --------------------------------------------------------------------------- #


def parse_sources() -> list[dict[str, Any]]:
    """Every ``sources/**/*.manifest.json``, reduced to what a note shows."""
    out: list[dict[str, Any]] = []
    if not SOURCES_DIR.exists():
        return out
    for path in sorted(SOURCES_DIR.rglob("*.manifest.json")):
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            out.append({"key": f"unreadable.{path.name}", "error": str(exc)[:120]})
            continue
        sha = str(rec.get("sha256") or "")
        used_for = str(rec.get("used_for") or "")
        out.append({
            "key": str(rec.get("key") or path.stem),
            "title": clip(rec.get("title"), 300),
            "publisher": clip(rec.get("publisher"), 160),
            "licence": clip(rec.get("licence"), 220),
            "sha256_prefix": sha[:12],
            "bytes": rec.get("bytes"),
            "relpath": str(rec.get("relpath") or ""),
            "retrieved_at": str(rec.get("retrieved_at") or ""),
            "intended_use": str(rec.get("intended_use") or ""),
            "exposure": str(rec.get("model_development_exposure") or ""),
            "substitute": clip(rec.get("substitute_flag"), 400),
            "used_for": clip(used_for, 700),
            "ids": ids_in(used_for + " " + str(rec.get("title") or "")),
            "manifest": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT)
                         else str(path),
        })
    return out


def parse_sources_md() -> dict[str, Any]:
    """The register's rules and which keys it actually lists."""
    if not SOURCES_MD.exists():
        return {"present": False, "keys": [], "rules": [], "use_values": {}}
    text = SOURCES_MD.read_text(encoding="utf-8")
    keys = sorted(set(re.findall(r"^\| `([^`]+)` \|", text, re.M)))
    rules = [unmd(m) for m in re.findall(r"^\d+\. \*\*(.+?)\*\*", text, re.M)]
    use = {m[0]: unmd(m[1]) for m in re.findall(r"^\| `(\w+)` \| (.+?) \|$", text, re.M)}
    return {"present": True, "keys": keys, "rules": rules, "use_values": use}


# --------------------------------------------------------------------------- #
# Inputs: DECISIONS.md.
# --------------------------------------------------------------------------- #


def parse_decisions() -> list[dict[str, Any]]:
    """E0 decisions, table-row decisions and bold-lead decisions, in one list."""
    if not DECISIONS_MD.exists():
        return []
    text = DECISIONS_MD.read_text(encoding="utf-8")
    lines = text.splitlines()
    out: dict[str, dict[str, Any]] = {}

    # Part A: | E0-n | item | decision as approved | where it binds |
    for row in re.findall(r"^\|\s*(E0-\d)\s*\|(.+)$", text, re.M):
        cells = [unmd(c) for c in row[1].split("|")]
        out[row[0]] = {
            "id": row[0], "kind": "E0 decision", "date": "2026-10-08",
            "title": clip(cells[0] if cells else "", 160),
            "decision": clip(cells[1] if len(cells) > 1 else "", 700),
            "reason": "", "binds": clip(cells[2] if len(cells) > 2 else "", 400),
            "reversible": "binding input",
            "source": "docs/DECISIONS.md Part A",
        }

    # Part B and friends: | D-nnn | date | decision | reason | reversible? |
    for row in re.findall(r"^\|\s*(D-\d{3}[a-z]?)\s*\|(.+)$", text, re.M):
        cells = [unmd(c) for c in row[1].split("|")]
        rec = {
            "id": row[0], "kind": "implementation decision",
            "date": cells[0] if cells else "",
            "title": clip(first_sentence(cells[1] if len(cells) > 1 else ""), 160),
            "decision": clip(cells[1] if len(cells) > 1 else "", 700),
            "reason": clip(cells[2] if len(cells) > 2 else "", 700),
            "binds": "",
            "reversible": unmd(cells[3]) if len(cells) > 3 else "",
            "source": "docs/DECISIONS.md table",
        }
        out.setdefault(row[0], rec)

    # ``## D-nnn — title`` / ``### D-nnn title`` sections.
    for m in re.finditer(r"^#{2,4} (D-\d{3}[a-z]?)\s*(?:—\s*)?(.+)$", text, re.M):
        start = text.index(m.group(0))
        nxt = re.search(r"\n#{1,4} ", text[start + 1:])
        body = text[start + len(m.group(0)):
                    start + 1 + nxt.start() if nxt else len(text)]
        rec = out.setdefault(m.group(1), {
            "id": m.group(1), "kind": "implementation decision", "date": "",
            "title": "", "decision": "", "reason": "", "binds": "",
            "reversible": "", "source": "docs/DECISIONS.md section",
        })
        rec["title"] = clip(unmd(m.group(2)), 160)
        if not rec["decision"]:
            rec["decision"] = clip(first_sentences(unmd(body), 2), 700)
        rec["body_ids"] = ids_in(body)

    # Bold-lead decisions: ``**D-nnn (was Dn) — title.** body``
    for m in re.finditer(r"^\*\*(D-\d{3}[a-z]?)(\s*\([^)]*\))?\s*[—-]\s*(.{0,400}?)\*\*",
                         text, re.M | re.S):
        start = text.index(m.group(0))
        nxt = re.search(r"\n\n\*\*D-\d{3}|\n#{1,2} ", text[start + 1:])
        body = text[start + len(m.group(0)): start + 1 + nxt.start()] if nxt \
            else text[start + len(m.group(0)):]
        rec = out.setdefault(m.group(1), {
            "id": m.group(1), "kind": "implementation decision", "date": "",
            "title": "", "decision": "", "reason": "", "binds": "",
            "reversible": "", "source": "docs/DECISIONS.md replay section",
        })
        rec["title"] = rec["title"] or clip(unmd(m.group(3)), 160)
        rec["alias"] = unmd(m.group(2) or "").strip("() ")
        if not rec["decision"]:
            rec["decision"] = clip(first_sentences(unmd(body), 2), 700)
        rec["body_ids"] = ids_in(body)

    for rec in out.values():
        blob = " ".join(str(rec.get(k, "")) for k in
                        ("title", "decision", "reason", "binds"))
        got = ids_in(blob)
        prev = rec.get("body_ids") or {}
        rec["ids"] = {k: sorted(set(got.get(k, [])) | set(prev.get(k, [])))
                      for k in got}
        rec.pop("body_ids", None)
    return [out[k] for k in sorted(out, key=decision_sort_key)]


def decision_sort_key(ident: str) -> tuple[int, int, str]:
    if ident.startswith("E0-"):
        return (0, int(ident.split("-")[1]), "")
    m = re.match(r"D-(\d{3})([a-z]?)", ident)
    return (1, int(m.group(1)), m.group(2)) if m else (2, 0, ident)


def first_sentence(text: str) -> str:
    return first_sentences(text, 1)


def first_sentences(text: str, n: int) -> str:
    parts = re.split(r"(?<=[.;])\s+", (text or "").strip())
    return " ".join(parts[:n]).strip()


# --------------------------------------------------------------------------- #
# Inputs: ISSUES.md.  Only identifiers, the summary-table cells and the status
# token leave the file - never a body, because a body here quotes credentials
# (I-002) and the vault must not carry them even redacted.
# --------------------------------------------------------------------------- #

STATUS_WORDS = ("OPEN", "MITIGATED", "CLOSED", "BLOCKED", "REPORT-TO-MIMIC")


def parse_issues() -> list[dict[str, Any]]:
    if not ISSUES_MD.exists():
        return []
    text = ISSUES_MD.read_text(encoding="utf-8")
    out: dict[str, dict[str, Any]] = {}

    for row in re.findall(r"^\|\s*(I-\d{3})\s*\|(.+)$", text, re.M):
        cells = [unmd(c) for c in row[1].split("|")]
        while len(cells) < 5:
            cells.append("")
        out[row[0]] = {
            "id": row[0], "raised": cells[0], "area": cells[1],
            "severity": cells[2], "status": cells[3].upper() or "UNSTATED",
            "summary": clip(cells[4], 400), "title": "",
            "source": "docs/ISSUES.md register table",
        }

    for m in re.finditer(r"^## (I-\d{3}) — (.+)$", text, re.M):
        ident, title = m.group(1), m.group(2)
        start = text.index(m.group(0))
        nxt = text.find("\n## ", start + 1)
        body = text[start: nxt if nxt != -1 else len(text)]
        status = ""
        sm = re.search(r"\*\*Status:\s*([A-Z\-]+)", body)
        if sm and sm.group(1) in STATUS_WORDS:
            status = sm.group(1)
        if not status:
            for word in STATUS_WORDS:
                if re.search(rf"\b{word}\b", title.upper()) or \
                        re.search(rf"\b{word.lower()}\b", title.lower()):
                    status = word
                    break
        sev = ""
        svm = re.search(r"\((Critical|High|Medium|Low)[^)]*\)\s*$", title)
        if svm:
            sev = svm.group(1)
        rec = out.setdefault(ident, {
            "id": ident, "raised": "", "area": "", "severity": "",
            "status": "", "summary": "", "title": "",
            "source": "docs/ISSUES.md detail section",
        })
        rec["title"] = clip(re.sub(r"\s*\([^)]*\)\s*$", "", unmd(title)), 220)
        rec["severity"] = rec["severity"] or sev
        rec["status"] = rec["status"] or status or "UNSTATED"
        rec["ids"] = ids_in(body)
        if not rec["summary"]:
            rec["summary"] = rec["title"]

    for rec in out.values():
        rec.setdefault("ids", ids_in(rec.get("summary", "")))
        rec["status"] = (rec["status"] or "UNSTATED").upper()
        if not rec["title"]:
            rec["title"] = rec["summary"]
    return [out[k] for k in sorted(out)]


# --------------------------------------------------------------------------- #
# Inputs: the assumption registers.  ``ASSUMPTION_FLAGS`` is the authority on
# how many assumptions there are ("one entry per subject, not per string
# occurrence"), so they are read instead of counting ``[A]`` in the documents.
# There are two registers: the sweep's (A-01 to A-51) and the tariff module's
# (A-90 to A-97).  ``docs/DECISIONS.md`` cites both, so the vault loads both.
# --------------------------------------------------------------------------- #


def load_assumptions() -> list[dict[str, Any]]:
    sys.path.insert(0, str(SCRIPTS))
    flags: list[Any] = []
    for mod, attr in (("baile_nua.validation.assumption_sweep", "ASSUMPTION_FLAGS"),
                      ("baile_nua.export.tariffs", "TARIFF_ASSUMPTIONS")):
        try:
            flags.extend(getattr(__import__(mod, fromlist=[attr]), attr))
        except Exception as exc:                                # pragma: no cover
            print(f"  ! {mod}.{attr} unreadable: {exc}", file=sys.stderr)
    out = []
    for flag in flags:
        blob = " ".join([flag.subject, flag.assumed, flag.retires_if,
                         flag.verdict_note, *flag.where])
        out.append({
            "id": flag.flag_id,
            "subject": clip(flag.subject, 220),
            "assumed": clip(flag.assumed, 700),
            "retires_if": clip(flag.retires_if, 400),
            "verdict": flag.verdict,
            "verdict_note": clip(flag.verdict_note, 700),
            "where": [scrub(w) for w in flag.where],
            "sources": list(flag.sources),
            "owning_step": scrub(flag.owning_step),
            "issue": scrub(flag.issue),
            "near_misses": [clip(n, 160) for n in flag.near_misses],
            "ids": ids_in(blob + " " + flag.issue),
        })
    return sorted(out, key=lambda r: r["id"])


# --------------------------------------------------------------------------- #
# Inputs: modules.  Path plus the first line of the docstring, read with ast so
# nothing is imported and no code body is ever opened as text for the vault.
# --------------------------------------------------------------------------- #


def parse_modules() -> list[dict[str, Any]]:
    out = []
    roots = [SCRIPTS / "baile_nua"]
    files = sorted(p for r in roots if r.exists() for p in r.rglob("*.py"))
    files += sorted(p for p in SCRIPTS.glob("*.py"))
    for path in files:
        rel = path.relative_to(ROOT)
        parts = rel.parts
        if ".venv" in parts or "tests" in parts:
            continue
        dotted = ".".join(parts[1:]).removesuffix(".py")
        if dotted.endswith(".__init__"):
            dotted = dotted.removesuffix(".__init__")
        if not dotted:
            continue
        purpose = ""
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
            doc = ast.get_docstring(tree) or ""
            purpose = clip(first_sentence(" ".join(doc.split())), 240)
        except (OSError, SyntaxError) as exc:
            purpose = f"[docstring unreadable: {type(exc).__name__}]"
        out.append({
            "id": dotted,
            "path": str(rel),
            "purpose": purpose or "[no module docstring]",
            "lines": sum(1 for _ in path.open("rb")),
        })
    return out


def parse_exporters() -> dict[str, Any]:
    """``dataset -> the module that writes it``, from ``export/dispatch.py``.

    Parsed rather than imported: the vault must not pull pandas and pyarrow into
    memory beside a running replay, and the tables are literal.
    """
    res: dict[str, Any] = {"writers": {}, "engine": [], "relocated": {},
                           "present": DISPATCH_PY.exists()}
    if not DISPATCH_PY.exists():
        return res
    text = DISPATCH_PY.read_text(encoding="utf-8")
    block = re.search(r"EXPORTERS[^=]*=\s*\{(.*?)\n\}", text, re.S)
    if block:
        for ds, mod, fn in re.findall(r'"(D\w+)":\s*(\w+)\.(\w+)', block.group(1)):
            res["writers"][ds] = {"module": f"baile_nua.export.{mod}", "fn": fn}
    eng = re.search(r"WRITTEN_BY_THE_ENGINE[^=]*=\s*\((.*?)\)", text, re.S)
    if eng:
        res["engine"] = re.findall(r'"(D\w+)"', eng.group(1))
    rel = re.search(r"RELOCATED_TO_RUN[^=]*=\s*\{(.*?)\n\}", text, re.S)
    if rel:
        res["relocated"] = dict(re.findall(r'"(D\w+)":\s*"([^"]+)"', rel.group(1)))
    return res


# --------------------------------------------------------------------------- #
# Inputs: the playbook.
# --------------------------------------------------------------------------- #


def find_playbook() -> tuple[Path | None, str]:
    for cand in PLAYBOOK_CANDIDATES:
        try:
            if cand.is_file():
                return cand, str(cand)
        except OSError:
            continue
    return None, "not found on any candidate path"


#: The playbook numbers its own decisions D1-D22 (v1 D1-D10, v2 D11-D17, v3
#: D18-D22) and writes them bold, usually parenthesised: "(**D13**)".  Those
#: collide head-on with dataset ids D11-D22, so a bare bold ``Dnn`` inside the
#: playbook is resolved through DECISIONS.md's own "(was D1)" aliases to the
#: D-1nn it became, and removed from the text before dataset ids are harvested.
RX_PB_DECISION = re.compile(r"\*\*\(?D(\d{1,2})\)?\*\*")


def playbook_refs(body: str, alias_map: dict[str, str]) -> tuple[str, list[str]]:
    """Return (*body* with its own decision refs removed, those refs mapped)."""
    found: list[str] = []

    def sub(m: re.Match[str]) -> str:
        key = f"D{int(m.group(1))}"
        if key in alias_map:
            found.append(alias_map[key])
            return " "
        return m.group(0)

    return RX_PB_DECISION.sub(sub, body or ""), sorted(set(found))


def parse_playbook(path: Path | None,
                   alias_map: dict[str, str] | None = None) -> dict[str, Any]:
    pb: dict[str, Any] = {
        "present": path is not None, "path": str(path) if path else "",
        "phases": [], "gates": {}, "estates": [], "roles": [],
        "boundary": [], "status": "", "open_decisions": [], "delivery": {},
        "text": "",
    }
    if path is None:
        return pb
    alias_map = alias_map or {}
    text = path.read_text(encoding="utf-8")
    pb["text"] = text
    lines = text.splitlines()

    # Phases and their exit gates.
    heads = [(i, m) for i, line in enumerate(lines)
             if (m := re.match(r"^### Phase (\d+) — (.+?)\s*$", line))]
    for idx, (i, m) in enumerate(heads):
        end = heads[idx + 1][0] if idx + 1 < len(heads) else next(
            (j for j in range(i + 1, len(lines)) if lines[j].startswith("## ")),
            len(lines))
        body = "\n".join(lines[i + 1: end])
        num = int(m.group(1))
        clean, own_refs = playbook_refs(body, alias_map)
        # Stop at the next LABEL line ("**Excluded → §11:**", "**Risk: high**")
        # rather than at the next "**" of any kind: the criteria themselves
        # carry bold spans, and stopping at those truncated them mid-clause.
        exit_m = re.search(
            r"\*\*Exit (G\d+)[^:]*:\s*(.+?)"
            r"(?=\n\s*[*-] |\n\*\*[A-Z][\w ,→§/-]{0,40}:|\n#{2,4} |\Z)",
            body, re.S)
        entry_m = re.search(r"\*\*Entry:\*\*\s*(.+?)(?=\n\*|\n\n|\Z)", body, re.S)
        # "Household finance (8 d) — NEW": the effort is parenthesised but not
        # always last, so it is lifted out of the title rather than anchored.
        raw_title = unmd(m.group(2))
        eff = re.search(r"\(([^)]*\d[^)]*\bd\b[^)]*)\)", raw_title)
        title = raw_title.replace(eff.group(0), "") if eff else raw_title
        title = re.sub(r"\s*[—-]\s*NEW\s*$", "", title).strip(" —-")
        phase = {
            "num": num,
            "title": " ".join(title.split()),
            "effort": unmd(eff.group(1)) if eff else "",
            "new_in_v3": bool(re.search(r"NEW\s*$", raw_title)),
            "gate": exit_m.group(1) if exit_m else "",
            "exit": clip(unmd(exit_m.group(2)), 800) if exit_m else "",
            "entry": clip(unmd(entry_m.group(1)), 300) if entry_m else "",
            "work": clip(re.sub(r"^[*-]\s+", "",
                                 first_sentences(unmd(body), 2)), 500),
            "ids": ids_in(clean),
        }
        phase["ids"]["decisions"] = sorted(set(phase["ids"]["decisions"]) | set(own_refs))
        pb["phases"].append(phase)
        if phase["gate"]:
            pb["gates"][phase["gate"]] = {
                "id": phase["gate"], "phase": num,
                "criteria": phase["exit"], "ids": dict(phase["ids"]),
            }

    # §13 estate table.
    est = re.search(r"## 13\. S — estate timeline export.*?(?=\n## |\Z)", text, re.S)
    if est:
        blk = est.group(0)
        for row in re.findall(r"^\|\s*\*\*([A-Za-z ]+)\*\*\s*\|(.+)$", blk, re.M):
            cells = [unmd(c) for c in row[1].split("|") if c.strip() != ""]
            _, est_refs = playbook_refs(row[1], alias_map)
            pb["estates"].append({
                "decision_refs": est_refs,
                "name": unmd(row[0]).strip(),
                "fields": cells[0] if cells else "",
                "site": cells[1] if len(cells) > 1 else "",
                "complete": cells[2] if len(cells) > 2 else "",
                "ids": ids_in(row[1]),
            })
        pb["estate_note"] = clip(unmd(first_sentences(
            blk.split("\n\n")[1] if "\n\n" in blk else blk, 2)), 500)
        pb["estate_fields"] = clip(unmd(
            (re.search(r"Fields per estate per date: (.+?)\.", blk, re.S)
             or re.search(r"(Fields per estate.+)", blk)).group(1)), 400) \
            if "Fields per estate" in blk else ""

    # §19 role table.
    rol = re.search(r"### Phase 19 — Role-scoped data views.*?(?=\n### |\n## |\Z)",
                    text, re.S)
    if rol:
        blk = rol.group(0)
        for row in re.findall(r"^\|\s*([^|]+?)\s*\|\s*(.+?)\s*\|$", blk, re.M):
            name, sees = unmd(row[0]), unmd(row[1])
            if not name or name.lower() in ("role", "") or set(name) <= set("- "):
                continue
            pb["roles"].append({"name": name, "sees": clip(sees, 400),
                                "ids": ids_in(row[1])})
        pb["role_exit"] = clip(unmd(
            re.search(r"\*\*Exit G19:\*\*\s*(.+?)(?=\n\n|\Z)", blk, re.S).group(1)
            if re.search(r"\*\*Exit G19:\*\*", blk) else ""), 500)

    # §1.2 boundary layers.
    bnd = re.search(r"### 1\.2 The boundary(.*?)(?=\n## )", text, re.S)
    if bnd:
        blk = bnd.group(1)
        # §1.2 carries TWO tables - the layer table and the scope table - and
        # they are kept apart rather than merged, because a scope row's cells
        # mean "yes/no", not "where/what".
        tables = [tb for tb in re.findall(r"((?:^\|.*\n)+)", blk, re.M)]
        if tables:
            for row in re.findall(r"^\|\s*\*\*([^|*]+)\*\*\s*\|\s*([^|]+?)\s*\|\s*(.+?)\s*\|$",
                                  tables[0], re.M):
                pb["boundary"].append({"layer": unmd(row[0]), "where": unmd(row[1]),
                                       "content": clip(unmd(row[2]), 400)})
        pb["scope"] = []
        if len(tables) > 1:
            for row in re.findall(r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|$",
                                  tables[1], re.M):
                scope = unmd(row[0])
                if not scope or scope.lower() == "scope" or set(scope) <= set("- "):
                    continue
                pb["scope"].append({"scope": clip(scope, 160),
                                    "baile_nua": unmd(row[1]) or "—",
                                    "bnit": unmd(row[2]) or "—"})
        pb["boundary_rule"] = clip(unmd(
            re.search(r"(The replay is frozen.+?package\.)", blk, re.S).group(1)
            if "The replay is frozen" in blk else ""), 300)

    # §8 open decisions (the playbook's own D18-D22, distinct from D-nnn).
    od = re.search(r"## 8\. Open decisions(.*?)(?=\n## )", text, re.S)
    if od:
        for row in re.findall(r"^\|\s*\*\*(D\d+)\*\*\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|$",
                              od.group(1), re.M):
            pb["open_decisions"].append({
                "ref": row[0], "decision": alias_map.get(row[0], ""),
                "question": clip(unmd(row[1]), 300),
                "recommendation": clip(unmd(row[2]), 300)})

    # §6 chained delivery table.
    for row in re.findall(r"^\|\s*(20\d\d)\s*\|\s*(\d+)\s*\|\s*([\d.]+)\s*\|\s*\**([^|*]+)\**\s*\|$",
                          text, re.M):
        pb["delivery"][int(row[0])] = {"days": int(row[1]), "hours": float(row[2]),
                                       "release_at": unmd(row[3])}

    # §10 issues table: "| **I-106** | ... Closes in Phase 1. ... |".  The
    # phase a playbook issue is tracked against is only stated here, so the
    # phase notes would otherwise miss it.
    sec10 = re.search(r"## 10\. Issues(.*?)(?=\n## )", text, re.S)
    pb["issue_phase"] = []
    if sec10:
        for row in re.findall(r"^\|\s*\*\*([^|*]+)\*\*\s*\|\s*(.+?)\s*\|$",
                              sec10.group(1), re.M):
            ref, note_text = unmd(row[0]).strip(), unmd(row[1])
            pb["issue_phase"].append({
                "ref": ref,
                # A §10 row can name more than one thing ("I-094 / A-97") and
                # can name an obligation rather than an issue ("LC-AMI-01").
                "refs": [x.strip() for x in ref.split("/") if x.strip()],
                "consequence": clip(note_text, 400),
                "phases": sorted({int(n) for n in
                                  re.findall(r"Phase (\d+)", note_text)}),
            })

    st = re.search(r"\n## Status\n+(.+?)(?=\n\n|\Z)", text, re.S)
    pb["status"] = clip(unmd(st.group(1)), 300) if st else ""
    return pb


def verify_phrase(pb: dict[str, Any], phrase: str) -> bool:
    """True if the playbook really contains *phrase*, ignoring markdown noise."""
    if not pb.get("text"):
        return False
    hay = " ".join(unmd(pb["text"]).split()).lower()
    return " ".join(unmd(phrase).split()).lower() in hay


#: Dated events the vault carries.  Each one names the phrase it came from and
#: the phase that owns it; the phrase is checked against the playbook before the
#: note is written, and a phrase that is not found is flagged on the note rather
#: than asserted.  Nothing here is invented: the names are the playbook's own.
EVENT_SPECS: tuple[dict[str, Any], ...] = (
    {"name": "Cluain Ard completion 2019", "when": "2019",
     "phrase": "Cluain Ard 2019, Part V 10% social", "phase": 9,
     "section": "§2 Phase 9, §13", "estate": "Cluain Ard"},
    {"name": "Belgard completion 2024", "when": "2024",
     "phrase": "Belgard 2024, nZEB A-rated, Part V 20%", "phase": 9,
     "section": "§2 Phase 9, §13", "estate": "Belgard"},
    {"name": "Abbeylands phased completion to 2027", "when": "2025-2027",
     "phrase": "Abbeylands phased to 2027", "phase": 9,
     "section": "§2 Phase 9, §13", "estate": "Abbeylands"},
    {"name": "SEM SMP to I-SEM switch", "when": "2018-10",
     "phrase": "SEM SMP → I-SEM switch at Oct 2018", "phase": 5,
     "section": "§2 Phase 5"},
    {"name": "COVID restrictions", "when": "2020-2022",
     "phrase": "restriction levels by date, school closures", "phase": 8,
     "section": "§2 Phase 8, Phase 13"},
    {"name": "Vaccine rollout by age band", "when": "2021",
     "phrase": "vaccine rollout", "phase": 8, "section": "§2 Phase 8"},
    {"name": "Smart-meter rollout", "when": "2019-2024",
     "phrase": "smart-meter install (ESB rollout 2019–24", "phase": 12,
     "section": "§2 Phase 12"},
    {"name": "PARA//EL enrolment ramp", "when": "2021-01-01 to 2026-09-30",
     "phrase": "from 1 Jan 2021, ramping to 30% of dwellings by", "phase": 18,
     "section": "§2 Phase 18"},
    {"name": "Energy crisis", "when": "2021-2024",
     "phrase": "Energy crisis 2021–24, endogenous", "phase": 13,
     "section": "§2 Phase 13"},
    {"name": "Electricity credits", "when": "2022-2024",
     "phrase": "Electricity credits 2022–24", "phase": 15,
     "section": "§2 Phase 15"},
    {"name": "MSS export payments", "when": "from 2022-12",
     "phrase": "MSS export payments from Dec 2022", "phase": 15,
     "section": "§2 Phase 15"},
    {"name": "Smoky coal ban", "when": "2022-10",
     "phrase": "smoky coal ban Oct 2022", "phase": 15, "section": "§2 Phase 15"},
    {"name": "Temporary-protection arrivals", "when": "2022",
     "phrase": "2022 temporary-protection arrivals", "phase": 15,
     "section": "§2 Phase 15"},
    {"name": "Recovery with conditional persistence", "when": "2023-2024",
     "phrase": "Recovery 2023–24", "phase": 13, "section": "§2 Phase 13"},
    {"name": "One-off public holiday 18 March 2022", "when": "2022-03-18",
     "phrase": "2022 keeps the", "phase": 2, "section": "§2 Phase 2"},
    {"name": "St Brigid's Day holiday begins", "when": "2023",
     "phrase": "which begins 2023", "phase": 2, "section": "§2 Phase 2"},
    {"name": "DST transitions across the span", "when": "23 transitions",
     "phrase": "bands on the correct local hour across", "phase": 3,
     "section": "§2 Phase 3"},
    {"name": "Census 2022 as t0 and as a test", "when": "2022-04-03",
     "phrase": "t0 is", "phase": 4, "section": "§1 Goal, §2 Phase 4"},
)


#: Privacy tiers.  The playbook publishes no enumerated tier list, so the tiers
#: in this vault are the schema's own access classes - the mechanical ones,
#: enforced by the generated leakage test - and beside them the named
#: role-view obligations the playbook does state, as constraint notes.
CONSTRAINT_SPECS: tuple[dict[str, str], ...] = (
    {"id": "LC-AMI-01", "about": "flexibility columns excluded from AMI"},
    {"id": "LC-AMI-03", "about": "DSO aggregates never fewer than 5 premises"},
    {"id": "FX-BN-04", "about": "edge emulator basis for 16a observation"},
    {"id": "FX-BN-05", "about": "one town-year under 24 h wall time"},
    {"id": "T-OBS", "about": "ten years of observable data"},
)


# --------------------------------------------------------------------------- #
# Inputs: the run.
# --------------------------------------------------------------------------- #


def parse_run(replay_root: Path = REPLAY_ROOT) -> dict[str, Any]:
    cfg: dict[str, Any] = {}
    if REPLAY_CONFIG.exists():
        try:
            cfg = json.loads(REPLAY_CONFIG.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            cfg = {}
    segments = {str(s.get("name")): s for s in cfg.get("segments", [])}
    done: dict[str, dict[str, Any]] = {}
    present = replay_root.exists()
    if present:
        for path in sorted(replay_root.glob("*/DONE.json")):
            try:
                done[path.parent.name] = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                done[path.parent.name] = {}
    try:
        shown = str(replay_root.relative_to(ROOT))
    except ValueError:
        shown = str(replay_root)
    return {"config": cfg, "segments": segments, "done": done,
            "replay_root_present": present, "replay_root": shown}


# --------------------------------------------------------------------------- #
# Note building.
# --------------------------------------------------------------------------- #


def kv_table(rows: Iterable[tuple[str, str]]) -> list[str]:
    body = [f"| {k} | {v} |" for k, v in rows if v not in (None, "", "—")]
    if not body:
        return ["*Nothing recorded.*", ""]
    return ["| | |", "|---|---|", *body, ""]


def bullets(items: Iterable[str]) -> list[str]:
    got = [f"- {i}" for i in items if i]
    return [*got, ""] if got else []


def build(vault: Vault, quiet: bool = False,
          replay_root: Path = REPLAY_ROOT) -> dict[str, Any]:
    note = lambda *a, **k: vault.add(Note(*a, **k))  # noqa: E731
    stats: dict[str, Any] = {"missing_inputs": [], "notes_by_kind": {}}

    def log(msg: str) -> None:
        if not quiet:
            print(msg)

    # ---------------------------------------------------------------- inputs
    schema = load_schema()
    datasets = schema["datasets"]
    owners = key_owners(datasets)
    md = parse_datasets_md()
    appendix_b = parse_appendix_b()
    sources = parse_sources()
    sources_md = parse_sources_md()
    decisions = parse_decisions()
    issues = parse_issues()
    assumptions = load_assumptions()
    modules = parse_modules()
    exporters = parse_exporters()
    pb_path, pb_where = find_playbook()
    # DECISIONS.md records what each playbook decision number became, as
    # "(was D1)" / "(D19)" beside the D-1nn that superseded it.
    alias_map: dict[str, str] = {}
    for d in decisions:
        for num in re.findall(r"D(\d+)", d.get("alias", "") or ""):
            alias_map.setdefault(f"D{int(num)}", d["id"])
    pb = parse_playbook(pb_path, alias_map)
    run = parse_run(replay_root)

    for label, ok in (("DATASETS.md", bool(md)), ("docs/DECISIONS.md", bool(decisions)),
                      ("docs/ISSUES.md", bool(issues)), ("sources/", bool(sources)),
                      ("sources/SOURCES.md", sources_md["present"]),
                      ("PLAYBOOK_v3.1.md", pb["present"]),
                      ("export/dispatch.py", exporters["present"]),
                      ("work/replay_2015_2026/", run["replay_root_present"]),
                      ("assumption register", bool(assumptions))):
        if not ok:
            stats["missing_inputs"].append(label)
    log(f"  playbook: {pb_where}")

    # ------------------------------------------------------- registration pass
    # Every note is registered before any body is rendered, so a link can be
    # resolved against the finished registry and a dangling link is reported
    # rather than written.

    ds_ids = sorted(datasets, key=lambda d: (d != "D17_aggregate", d))
    ds_order = list(datasets.keys())

    dataset_notes = {d: note(d, "datasets", "dataset", d,
                             md.get(d, {}).get("facts", {}).get("Status", "undeclared")
                             .replace("*", "") or "undeclared",
                             ["dataset", f"class/{datasets[d].get('access_class','?')}"])
                     for d in ds_order}
    source_notes = {s["key"]: note(s["key"], "sources", "source", s["key"],
                                   s.get("intended_use") or "unstated",
                                   ["source",
                                    f"use/{s.get('intended_use') or 'unstated'}",
                                    f"exposure/{s.get('exposure') or 'unstated'}"])
                    for s in sources if "error" not in s}
    assumption_notes = {a["id"]: note(a["id"], "assumptions", "assumption", a["id"],
                                      a["verdict"],
                                      ["assumption", f"verdict/{a['verdict']}"])
                        for a in assumptions}
    decision_notes = {d["id"]: note(d["id"], "decisions", "decision", d["id"],
                                    d.get("reversible") or "recorded",
                                    ["decision", f"decision/{d['kind'].split()[0]}"])
                      for d in decisions}
    issue_notes = {i["id"]: note(i["id"], "issues", "issue", i["id"], i["status"],
                                 ["issue", f"status/{i['status'].lower()}",
                                  f"severity/{(i['severity'] or 'unstated').lower()}"])
                   for i in issues}
    module_notes = {m["id"]: note(m["id"], "modules", "module", m["id"], "present",
                                  ["module", "package/" + m["id"].split(".")[1]
                                   if m["id"].startswith("baile_nua.") and
                                   len(m["id"].split(".")) > 2 else "package/top"])
                    for m in modules}
    index_modules(module_notes)

    phase_names = {p["num"]: f"Phase {p['num']:02d}" for p in pb["phases"]}
    phase_notes = {}
    for p in pb["phases"]:
        status = "in progress" if (f"Phase {p['num']} in progress" in pb["status"]) \
            else "pending"
        phase_notes[p["num"]] = note(phase_names[p["num"]], "phases", "phase",
                                     phase_names[p["num"]], status,
                                     ["phase", f"status/{status.replace(' ', '-')}"])
    gate_notes = {g: note(g, "gates", "gate", g, "not reached",
                          ["gate", "status/not-reached"])
                  for g in sorted(pb["gates"], key=lambda x: int(x[1:]))}
    estate_notes = {e["name"]: note(e["name"], "estates", "estate", e["name"],
                                    "planned", ["estate"]) for e in pb["estates"]}
    event_notes = {}
    for spec in EVENT_SPECS:
        found = verify_phrase(pb, spec["phrase"])
        event_notes[spec["name"]] = note(
            spec["name"], "events", "event", spec["name"],
            "verified in playbook" if found else "phrase not found in playbook",
            ["event", "verified" if found else "unverified"])
    role_notes = {}
    for r in pb["roles"]:
        slug = f"role_{re.sub(r'[^A-Za-z0-9]+', '_', r['name']).strip('_')}"
        role_notes[r["name"]] = note(slug, "roles", "role", r["name"], "specified",
                                     ["role", "flexus-family"])
        role_notes[r["name"]].heading = f"{r['name']} (role)"
    tier_notes = {}
    for cls, meta in sorted(schema.get("access_classes", {}).items()):
        tier_notes[cls] = note(f"tier_{cls}", "privacy", "privacy tier", cls,
                               "enforced by the generated leakage test",
                               ["privacy-tier", f"class/{cls}"])
        tier_notes[cls].heading = f"Privacy tier {cls}"
    constraint_notes = {}
    for c in CONSTRAINT_SPECS:
        constraint_notes[c["id"]] = note(f"constraint_{c['id']}", "privacy",
                                         "constraint", c["id"],
                                         "named in PLAYBOOK_v3.1" if pb["present"]
                                         else "playbook not read",
                                         ["constraint", "privacy-tier"])
        constraint_notes[c["id"]].heading = f"{c['id']} — {c['about']}"
    year_notes = {}
    for y in YEARS:
        rec = run["done"].get(str(y))
        status = "complete" if rec else "pending"
        year_notes[y] = note(f"Year {y}", "years", "year", str(y), status,
                             ["year", f"status/{status}"])
    for name in ("MOC_Datasets", "MOC_Sources", "MOC_Decisions", "MOC_Run"):
        note(name, ".", "index", name, "generated", ["moc", "index"])

    # -------------------------------------------------------- dataset bodies
    carries: dict[str, list[str]] = defaultdict(list)
    for ds_id in ds_order:
        for field in datasets[ds_id].get("fields") or []:
            if field["name"].endswith("_id"):
                carries[field["name"]].append(ds_id)

    writer_of = exporters["writers"]
    engine_written = set(exporters["engine"])

    for ds_id in ds_order:
        spec = datasets[ds_id]
        rec = md.get(ds_id, {})
        facts = rec.get("facts", {})
        n = dataset_notes[ds_id]
        cls = spec.get("access_class", "?")
        n.heading = f"{ds_id} · {spec.get('title') or rec.get('title') or spec.get('name')}"
        upstream, downstream, keys = [], [], []
        for field in spec.get("fields") or []:
            name = field["name"]
            if not name.endswith("_id"):
                continue
            owner = owners.get(name)
            keys.append((name, owner or "—", bool(field.get("required"))))
            if owner == ds_id:
                downstream.extend(d for d in carries[name] if d != ds_id)
            elif owner:
                upstream.append(owner)
        n.extra.update({
            "dataset": ds_id,
            "name": spec.get("name"),
            "class": cls,
            "package": facts.get("Package") or
                       schema["access_classes"].get(cls, {}).get("released_in", ""),
            "grain": str(spec.get("grain") or ""),
            "storage": str(spec.get("storage") or ""),
            "subsystem": str(spec.get("subsystem") or ""),
            "e1_in_scope": bool(spec.get("e1_in_scope")),
            "rows": facts.get("Rows", ""),
            "keys": sorted({k for k, _, _ in keys}),
            "upstream": sorted(set(upstream)),
            "downstream": sorted(set(downstream)),
        })
        body = n.body
        if rec.get("lead"):
            body += [clip(rec["lead"], 600), ""]
        body += ["## Facts", ""]
        body += kv_table([
            ("Class", f"{cls} — {schema['access_classes'].get(cls, {}).get('description','')}"),
            ("Privacy tier", vault.link(f"tier_{cls}", cls, origin=ds_id)),
            ("Package", facts.get("Package", "")),
            ("Grain", str(spec.get("grain") or "")),
            ("Storage, declared", str(spec.get("storage") or "")),
            ("Subsystem", str(spec.get("subsystem") or "")),
            ("E1 in scope", "yes" if spec.get("e1_in_scope") else "no"),
            ("Path", facts.get("Path", "")),
            ("Rows", facts.get("Rows", "")),
            ("Size", facts.get("Size", "")),
            ("Time span", facts.get("Time span", "")),
            ("Resolution", facts.get("Resolution", "")),
            ("Primary key", facts.get("Primary key", "")),
            ("Present for", facts.get("Present for", "")),
            ("Status", facts.get("Status", "undeclared")),
            ("Part hash", facts.get("Part hash", "")),
            ("Fields declared", str(len(spec.get("fields") or []))),
        ])
        if spec.get("notes"):
            body += ["> " + clip(str(spec["notes"]), 600), ""]
        body += ["## Keys and joins", ""]
        if keys:
            body += ["| key | declared by | required |", "|---|---|---|"]
            for name, owner, required in sorted(set(keys)):
                link = vault.link(owner, origin=ds_id) if owner in dataset_notes \
                    else owner
                body.append(f"| `{name}` | {link} | {'yes' if required else 'no'} |")
            body.append("")
        else:
            body += ["No id column is declared for this dataset.", ""]
        body += kv_table([
            ("Upstream (declares a key this dataset carries)",
             vault.links(sorted(set(upstream)), origin=ds_id)),
            ("Downstream (carries a key this dataset declares)",
             vault.links(sorted(set(downstream)), origin=ds_id)),
        ])
        if rec.get("joins"):
            body += ["**Joins observed on disk** (DATASETS.md):", ""]
            for key, targets in rec["joins"]:
                names = sorted({m.group(0) for m in RX_DATASET.finditer(targets)})
                shown = vault.links(names, origin=ds_id) if names else clip(targets, 200)
                body.append(f"- `{key}` → {shown}" if key else f"- {clip(targets, 200)}")
            body.append("")
        body += ["## Produced by", ""]
        written_by = []
        if ds_id in writer_of:
            mod = writer_of[ds_id]["module"]
            written_by.append(f"{vault.link(mod, origin=ds_id)} "
                              f"(`{writer_of[ds_id]['fn']}`)")
        if ds_id in engine_written:
            written_by.append(f"{vault.link('baile_nua.engine.stream_writer', origin=ds_id)}"
                              " — streamed during the run itself")
        if exporters["relocated"].get(ds_id):
            written_by.append(f"relocated to the `{exporters['relocated'][ds_id]}` "
                              "run package (RELOCATED_TO_RUN)")
        body += bullets(written_by) or ["No writer is registered for this dataset "
                                        "in `export/dispatch.py`.", ""]
        if rec.get("modules"):
            body += ["**Named in the validation artefacts:** " +
                     vault.links([dotted_for(m) for m in rec["modules"]], origin=ds_id),
                     ""]
        srcs = sorted(s["key"] for s in sources
                      if "error" not in s and ds_id in s["ids"]["datasets"])
        body += ["## Sources that name it", "",
                 vault.links(srcs, origin=ds_id) if srcs
                 else "No source manifest names this dataset in its `used_for`.", ""]
        rel = {
            "Decisions": [d["id"] for d in decisions
                          if ds_id in d.get("ids", {}).get("datasets", [])],
            "Issues": [i["id"] for i in issues
                       if ds_id in i.get("ids", {}).get("datasets", [])],
            "Assumptions": [a["id"] for a in assumptions
                            if ds_id in a["ids"]["datasets"]],
            "Phases": [phase_names[p["num"]] for p in pb["phases"]
                       if ds_id in p["ids"]["datasets"]],
        }
        body += ["## Touched by", ""]
        body += kv_table([(k, vault.links(v, origin=ds_id)) for k, v in rel.items()])
        if rec.get("key_points"):
            body += ["## Key points, as the catalogue states them", ""]
            body += bullets(clip(k, 400) for k in rec["key_points"][:5])
        body += [f"Schema: `{DATASETS_YAML.relative_to(ROOT)}`; "
                 f"catalogue: `{DATASETS_MD.name}`.", ""]

    # --------------------------------------------------------- source bodies
    for s in sources:
        if "error" in s:
            continue
        n = source_notes[s["key"]]
        n.heading = f"{s['key']}"
        n.extra.update({
            "publisher": s["publisher"], "licence_summary": clip(s["licence"], 120),
            "sha256_prefix": s["sha256_prefix"], "bytes": s["bytes"],
            "retrieved": s["retrieved_at"], "intended_use": s["intended_use"],
            "model_development_exposure": s["exposure"],
            "datasets": s["ids"]["datasets"],
            "in_register": s["key"] in sources_md.get("keys", []),
        })
        body = n.body
        body += [clip(s["title"], 400), ""]
        body += kv_table([
            ("Publisher", s["publisher"]),
            ("Licence", s["licence"]),
            ("File", f"`{s['relpath']}`"),
            ("Bytes", f"{s['bytes']:,}" if isinstance(s["bytes"], int) else ""),
            ("SHA-256 prefix", f"`{s['sha256_prefix']}…`"),
            ("Retrieved", s["retrieved_at"]),
            ("Intended use", f"{s['intended_use']} — "
                             f"{sources_md.get('use_values', {}).get(s['intended_use'], '')}"),
            ("Model-development exposure", s["exposure"]),
            ("In the register", "yes" if s["key"] in sources_md.get("keys", [])
             else "not listed in sources/SOURCES.md"),
            ("Manifest", f"`{s['manifest']}`"),
        ])
        body += ["## Datasets that use it", "",
                 vault.links(s["ids"]["datasets"], origin=s["key"]) or "—", ""]
        if s["used_for"]:
            body += ["## Used for", "", s["used_for"], ""]
        if s["substitute"]:
            body += ["## Substitute flag", "", s["substitute"], ""]
        touch = kv_table([
            ("Assumptions", vault.links(
                [a["id"] for a in assumptions if s["key"] in a["sources"]],
                origin=s["key"])),
            ("Issues", vault.links(s["ids"]["issues"], origin=s["key"])),
            ("Decisions", vault.links(s["ids"]["decisions"], origin=s["key"])),
        ])
        if touch:
            body += ["## Touched by", "", *touch]

    # ----------------------------------------------------- assumption bodies
    for a in assumptions:
        n = assumption_notes[a["id"]]
        n.heading = f"{a['id']} — {a['subject']}"
        mods = sorted({dotted_for(w) for w in a["where"]
                       if dotted_for(w) in module_notes})
        n.extra.update({"verdict": a["verdict"], "datasets": a["ids"]["datasets"],
                        "modules": mods, "sources": a["sources"],
                        "issue": a["issue"][:80]})
        body = n.body
        body += kv_table([
            ("Verdict", a["verdict"]),
            ("Assumed", a["assumed"]),
            ("Retires if", a["retires_if"]),
            ("Owning step", a["owning_step"]),
        ])
        if a["verdict_note"]:
            body += ["## Verdict note", "", a["verdict_note"], ""]
        body += ["## Where it lives", ""]
        body += bullets(f"`{w}`" + (f" → {vault.link(dotted_for(w), origin=a['id'])}"
                                    if dotted_for(w) in module_notes else "")
                        for w in a["where"])
        body += ["## Affects", ""]
        body += kv_table([
            ("Datasets", vault.links(a["ids"]["datasets"], origin=a["id"])),
            ("Modules", vault.links(mods, origin=a["id"])),
            ("Sources", vault.links(a["sources"], origin=a["id"])),
            ("Issues", vault.links(a["ids"]["issues"], origin=a["id"])),
            ("Decisions", vault.links(a["ids"]["decisions"], origin=a["id"])),
            ("Phases", vault.links([phase_names[p["num"]] for p in pb["phases"]
                                    if a["id"] in p["ids"]["assumptions"]],
                                   origin=a["id"])),
        ])
        if a["near_misses"]:
            body += ["## Near misses the search found", ""]
            body += bullets(a["near_misses"])
        reg = ("scripts/baile_nua/export/tariffs.py` (`TARIFF_ASSUMPTIONS`)"
               if a["id"] >= "A-90" else
               "scripts/baile_nua/validation/assumption_sweep.py` "
               "(`ASSUMPTION_FLAGS`)")
        body += [f"Register: `{reg}.", ""]

    # ------------------------------------------------------- decision bodies
    for d in decisions:
        n = decision_notes[d["id"]]
        n.heading = f"{d['id']} — {d['title']}" if d["title"] else d["id"]
        ids = d.get("ids", {})
        mods = sorted({dotted_for(m) for m in ids.get("modules", [])
                       if dotted_for(m) in module_notes})
        n.extra.update({"date": d.get("date", ""), "kind": d["kind"],
                        "reversible": d.get("reversible", ""),
                        "alias": d.get("alias", ""),
                        "datasets": ids.get("datasets", []), "modules": mods,
                        "source": d.get("source", "")})
        body = n.body
        body += kv_table([
            ("Date", d.get("date", "")),
            ("Kind", d["kind"]),
            ("Reversible", d.get("reversible", "")),
            ("Also known as", d.get("alias", "")),
            ("Recorded in", f"`{d.get('source','')}`"),
        ])
        if d.get("decision"):
            body += ["## Decision", "", d["decision"], ""]
        if d.get("reason"):
            body += ["## Reason", "", d["reason"], ""]
        if d.get("binds"):
            body += ["## Where it binds the code", "", d["binds"], ""]
        body += ["## Affects", ""]
        body += kv_table([
            ("Datasets", vault.links(ids.get("datasets", []), origin=d["id"])),
            ("Modules", vault.links(mods, origin=d["id"])),
            ("Issues", vault.links(ids.get("issues", []), origin=d["id"])),
            ("Assumptions", vault.links(ids.get("assumptions", []), origin=d["id"])),
            ("Other decisions", vault.links(
                [x for x in ids.get("decisions", []) + ids.get("e0", [])
                 if x != d["id"]], origin=d["id"])),
            ("Gates", vault.links(ids.get("gates", []), origin=d["id"])),
            ("Phases", vault.links([phase_names[p["num"]] for p in pb["phases"]
                                    if d["id"] in p["ids"]["decisions"]],
                                   origin=d["id"])),
        ])

    # ---------------------------------------------------------- issue bodies
    for i in issues:
        n = issue_notes[i["id"]]
        n.heading = f"{i['id']} — {i['title']}" if i["title"] else i["id"]
        ids = i.get("ids", {})
        mods = sorted({dotted_for(m) for m in ids.get("modules", [])
                       if dotted_for(m) in module_notes})
        n.extra.update({"raised": i.get("raised", ""), "area": i.get("area", ""),
                        "severity": i.get("severity", ""),
                        "datasets": ids.get("datasets", []), "modules": mods,
                        "source": i.get("source", "")})
        body = n.body
        body += kv_table([
            ("Raised", i.get("raised", "")),
            ("Area", i.get("area", "")),
            ("Severity", i.get("severity", "")),
            ("Status", i["status"]),
            ("Recorded in", f"`{i.get('source','')}`"),
        ])
        if i.get("summary"):
            body += ["## Summary", "", i["summary"], "",
                     "*Summary only. The issue's evidence stays in "
                     "`docs/ISSUES.md`, which is where it belongs: some of those "
                     "bodies quote credentials, so no body is copied here.*", ""]
        body += ["## Affects", ""]
        body += kv_table([
            ("Datasets", vault.links(ids.get("datasets", []), origin=i["id"])),
            ("Modules", vault.links(mods, origin=i["id"])),
            ("Assumptions", vault.links(ids.get("assumptions", []), origin=i["id"])),
            ("Decisions", vault.links(ids.get("decisions", []), origin=i["id"])),
            ("Other issues", vault.links(
                [x for x in ids.get("issues", []) if x != i["id"]], origin=i["id"])),
            ("Gates", vault.links(ids.get("gates", []), origin=i["id"])),
            ("Phases", vault.links([phase_names[p["num"]] for p in pb["phases"]
                                    if i["id"] in p["ids"]["issues"]],
                                   origin=i["id"])),
        ])

    # --------------------------------------------------------- module bodies
    writes_by_module: dict[str, list[str]] = defaultdict(list)
    for ds_id, w in writer_of.items():
        writes_by_module[w["module"]].append(ds_id)
    for ds_id in engine_written:
        writes_by_module["baile_nua.engine.stream_writer"].append(ds_id)

    for m in modules:
        n = module_notes[m["id"]]
        n.heading = m["id"]
        writes = sorted(writes_by_module.get(m["id"], []))
        n.extra.update({"path": m["path"], "writes": writes, "lines": m["lines"]})
        body = n.body
        body += kv_table([
            ("Path", f"`{m['path']}`"),
            ("Purpose", m["purpose"]),
            ("Writes", vault.links(writes, origin=m["id"]) if writes else ""),
        ])
        body += ["*Path and purpose only — no code is reproduced in this vault.*", ""]
        rel = kv_table([
            ("Assumptions declared here", vault.links(
                [a["id"] for a in assumptions
                 if any(dotted_for(w) == m["id"] for w in a["where"])],
                origin=m["id"])),
            ("Decisions naming it", vault.links(
                [d["id"] for d in decisions
                 if m["id"] in {dotted_for(x) for x in d.get("ids", {}).get("modules", [])}],
                origin=m["id"])),
            ("Issues naming it", vault.links(
                [i["id"] for i in issues
                 if m["id"] in {dotted_for(x) for x in i.get("ids", {}).get("modules", [])}],
                origin=m["id"])),
            ("Phases naming it", vault.links(
                [phase_names[p["num"]] for p in pb["phases"]
                 if m["id"] in {dotted_for(x) for x in p["ids"]["modules"]}],
                origin=m["id"])),
        ])
        if rel:
            body += ["## Referenced by", "", *rel]

    # ---------------------------------------------------- phase, gate bodies
    for p in pb["phases"]:
        n = phase_notes[p["num"]]
        n.heading = f"Phase {p['num']} — {p['title']}"
        ids = p["ids"]
        mods = sorted({dotted_for(x) for x in ids["modules"]
                       if dotted_for(x) in module_notes})
        tracked_ids = {x for r in pb.get("issue_phase", [])
                       if p["num"] in r["phases"] for x in r["refs"]}
        blockers = [i["id"] for i in issues
                    if (i["id"] in ids["issues"] or i["id"] in tracked_ids)
                    and i["status"] in
                    ("OPEN", "BLOCKED", "REPORT-TO-MIMIC", "UNSTATED")]
        n.extra.update({"effort": p["effort"], "gate": p["gate"],
                        "blockers": blockers, "datasets": ids["datasets"],
                        "modules": mods})
        body = n.body
        body += kv_table([
            ("Effort", p["effort"]),
            ("Entry", p["entry"]),
            ("Exit gate", vault.link(p["gate"], origin=n.name) if p["gate"] else ""),
            ("Status", n.status),
        ])
        if p["work"]:
            body += ["## Work", "", p["work"], ""]
        if p["exit"]:
            body += ["## Exit criteria", "", p["exit"], ""]
        body += ["## Blockers and open items", "",
                 vault.links(blockers, origin=n.name) if blockers
                 else "No open issue in `docs/ISSUES.md` is named by this phase.", ""]
        tracked = [r for r in pb.get("issue_phase", []) if p["num"] in r["phases"]]
        if tracked:
            body += ["## Issues the playbook tracks against this phase (§10)", ""]
            body += bullets(
                f"{vault.links([constraint_name(x) for x in r['refs']], origin=n.name)}"
                f" — {r['consequence']}" for r in tracked)
        pb_open = [od for od in pb["open_decisions"]
                   if p["num"] in phases_mentioned(od["question"])]
        if pb_open:
            body += ["## Playbook open decisions on this phase", ""]
            body += bullets(f"**{od['ref']}** — {od['question']} "
                            f"*Recommendation:* {od['recommendation']}"
                            for od in pb_open)
        body += ["## Touches", ""]
        body += kv_table([
            ("Datasets", vault.links(ids["datasets"], origin=n.name)),
            ("Modules", vault.links(mods, origin=n.name)),
            ("Issues", vault.links(ids["issues"], origin=n.name)),
            ("Assumptions", vault.links(ids["assumptions"], origin=n.name)),
            ("Decisions", vault.links(ids["decisions"] + ids["e0"], origin=n.name)),
            ("Gates named", vault.links(ids["gates"], origin=n.name)),
            ("Events", vault.links([s["name"] for s in EVENT_SPECS
                                    if s["phase"] == p["num"]], origin=n.name)),
            ("Estates", vault.links(sorted({s["estate"] for s in EVENT_SPECS
                                            if s["phase"] == p["num"]
                                            and s.get("estate")}), origin=n.name)),
        ])
        body += [f"Source: `PLAYBOOK_v3.1.md` §2.", ""]

    for g_id, g in sorted(pb["gates"].items(), key=lambda kv: int(kv[0][1:])):
        n = gate_notes[g_id]
        phase_num = g["phase"]
        n.heading = f"{g_id} — exit gate of Phase {phase_num}"
        blockers = [i["id"] for i in issues
                    if i["id"] in g["ids"]["issues"] and i["status"] in
                    ("OPEN", "BLOCKED", "REPORT-TO-MIMIC", "UNSTATED")]
        n.extra.update({"phase": f"Phase {phase_num}", "blockers": blockers})
        body = n.body
        body += kv_table([
            ("Phase", vault.link(phase_names.get(phase_num, ""), origin=g_id)),
            ("Status", "not reached — the playbook records Phase 0 in progress"
             if pb["status"] else "not reached"),
        ])
        body += ["## Criteria", "", g["criteria"] or "—", ""]
        body += ["## Blockers", "",
                 vault.links(blockers, origin=g_id) if blockers
                 else "No open issue is named in this gate's phase text.", ""]
        body += ["## Touches", ""]
        body += kv_table([
            ("Datasets", vault.links(g["ids"]["datasets"], origin=g_id)),
            ("Issues", vault.links(g["ids"]["issues"], origin=g_id)),
            ("Decisions", vault.links(g["ids"]["decisions"], origin=g_id)),
        ])

    # -------------------------------------------------------- estate bodies
    for e in pb["estates"]:
        n = estate_notes[e["name"]]
        n.heading = e["name"]
        est_decisions = sorted(set(e["ids"]["decisions"]) |
                               set(e.get("decision_refs", [])))
        n.extra.update({"fields_until": e["fields"], "site": e["site"],
                        "complete": e["complete"], "decisions": est_decisions})
        body = n.body
        body += kv_table([
            ("Fields until", e["fields"]),
            ("Site works", e["site"]),
            ("Complete", e["complete"]),
        ])
        if pb.get("estate_fields"):
            body += ["## Timeline export", "",
                     f"The §13 export carries, per estate per date: "
                     f"{pb['estate_fields']}", ""]
        if pb.get("estate_note"):
            body += [pb["estate_note"], ""]
        body += ["## Linked", ""]
        body += kv_table([
            ("Built in", vault.link(phase_names.get(9, ""), origin=e["name"])),
            ("Events", vault.links([s["name"] for s in EVENT_SPECS
                                    if s.get("estate") == e["name"]],
                                   origin=e["name"])),
            ("Derived from", vault.links(["D01", "D02"], origin=e["name"])),
            ("Decisions", vault.links(est_decisions, origin=e["name"])),
        ])
        body += ["Source: `PLAYBOOK_v3.1.md` §13 (estate timeline export).", ""]

    # --------------------------------------------------------- event bodies
    for spec in EVENT_SPECS:
        n = event_notes[spec["name"]]
        n.heading = spec["name"]
        found = n.status.startswith("verified")
        n.extra.update({"when": spec["when"], "phase": f"Phase {spec['phase']}",
                        "playbook_section": spec["section"],
                        "phrase_verified": found})
        body = n.body
        body += kv_table([
            ("When", spec["when"]),
            ("Owning phase", vault.link(phase_names.get(spec["phase"], ""),
                                        origin=spec["name"])),
            ("Playbook section", spec["section"]),
            ("Estate", vault.link(spec["estate"], origin=spec["name"])
             if spec.get("estate") else ""),
        ])
        body += ["## Provenance", "",
                 f"Taken from `PLAYBOOK_v3.1.md` on the phrase "
                 f"*“{clip(spec['phrase'], 160)}”*, "
                 + ("which is present in the file as read."
                    if found else
                    "**which was NOT found in the file as read — treat this note "
                    "as unverified.**"), ""]
        phase = next((p for p in pb["phases"] if p["num"] == spec["phase"]), None)
        if phase:
            body += ["## Phase context", ""]
            body += kv_table([
                ("Datasets", vault.links(phase["ids"]["datasets"], origin=spec["name"])),
                ("Decisions", vault.links(phase["ids"]["decisions"], origin=spec["name"])),
                ("Issues", vault.links(phase["ids"]["issues"], origin=spec["name"])),
            ])
        years_touched = sorted({int(y) for y in re.findall(r"\b(20\d\d)\b", spec["when"])
                                if 2015 <= int(y) <= 2026})
        if years_touched:
            body += ["## Years", "",
                     vault.links([f"Year {y}" for y in years_touched],
                                 origin=spec["name"]), ""]

    # ---------------------------------------------------------- role bodies
    for r in pb["roles"]:
        n = role_notes[r["name"]]
        tiers = [c["id"] for c in CONSTRAINT_SPECS if c["id"] in r["sees"]]
        n.extra.update({"sees": r["sees"], "constraints": tiers})
        body = n.body
        body += kv_table([
            ("Role", r["name"]),
            ("Sees", r["sees"]),
            ("Named constraints", vault.links([f"constraint_{t}" for t in tiers],
                                              origin=n.name)),
            ("Specified in", "PLAYBOOK_v3.1 §2 Phase 19 (role-scoped data views)"),
        ])
        if pb.get("role_exit"):
            body += ["## Gate", "",
                     f"{vault.link('G19', origin=n.name)}: {pb['role_exit']}", ""]
        body += ["## Privacy tiers it may read", "",
                 vault.links([f"tier_{c}" for c in ("OBS", "GT", "META")
                              if (c == "OBS")
                              or ("GT" in r["sees"]) or ("full data" in r["sees"])],
                             origin=n.name), ""]
        body += ["*A role's tier is read from its own row in the playbook's table; "
                 "the playbook publishes no separate numbered tier list.*", ""]

    # ---------------------------------------------------------- tier bodies
    for cls, meta in sorted(schema.get("access_classes", {}).items()):
        n = tier_notes[cls]
        in_tier = [d for d in ds_order if datasets[d].get("access_class") == cls]
        n.extra.update({"released_in": meta.get("released_in", ""),
                        "datasets": in_tier})
        body = n.body
        body += kv_table([
            ("Description", clip(meta.get("description", ""), 300)),
            ("Released in", meta.get("released_in", "")),
            ("Datasets", str(len(in_tier))),
        ])
        body += ["## Datasets in this tier", "",
                 vault.links(in_tier, origin=n.name), ""]
        body += ["## Roles that may see it", "",
                 vault.links([role_notes[r["name"]].name for r in pb["roles"]
                              if (cls == "OBS") or ("full data" in r["sees"])
                              or ("GT" in r["sees"])], origin=n.name) or "—", ""]
        body += ["The class is carried in the schema and the leakage test is "
                 "generated from it, so the separation is mechanical "
                 f"({vault.link('D-006', origin=n.name)}).", ""]

    for c in CONSTRAINT_SPECS:
        n = constraint_notes[c["id"]]
        roles_named = [role_notes[r["name"]].name for r in pb["roles"]
                       if c["id"] in r["sees"]]
        phases_named = [phase_names[p["num"]] for p in pb["phases"]
                        if c["id"] in " ".join((p["exit"], p["entry"], p["work"]))]
        n.extra.update({"about": c["about"], "roles": roles_named,
                        "phases": phases_named})
        body = n.body
        body += kv_table([
            ("Obligation", c["about"]),
            ("Named in", "PLAYBOOK_v3.1 §2 and §10"),
        ])
        body += ["## Roles it binds", "",
                 vault.links(roles_named, origin=n.name) or "—", ""]
        body += ["## Phases that test it", "",
                 vault.links(phases_named, origin=n.name) or "—", ""]

    # ----------------------------------------------------------- year bodies
    delivery = pb.get("delivery", {})
    for y in YEARS:
        n = year_notes[y]
        seg = run["segments"].get(str(y), {})
        rec = run["done"].get(str(y))
        n.heading = f"Year {y}"
        counts = (rec or {}).get("row_counts") or {}
        n.extra.update({
            "days_planned": delivery.get(y, {}).get("days", seg.get("days", "")),
            "sim_day_offset": seg.get("sim_day_offset", ""),
            "run_status": n.status,
            "rows_total": sum(v for v in counts.values() if isinstance(v, int))
                          if counts else 0,
            "packages": sorted({str(k) for k in counts}) if counts else [],
        })
        body = n.body
        body += kv_table([
            ("Window", f"{seg.get('start','')} → {seg.get('end','')}"
             if seg else "not in `scripts/replay_config.json`"),
            ("Days, planned", str(delivery.get(y, {}).get("days", ""))),
            ("Hours, estimated", str(delivery.get(y, {}).get("hours", ""))),
            ("Release at", str(delivery.get(y, {}).get("release_at", ""))),
            ("sim_day offset", str(seg.get("sim_day_offset", ""))),
            ("Run status", n.status),
        ])
        if rec:
            body += ["## Run record", ""]
            body += kv_table([
                ("Days run", str(rec.get("days", ""))),
                ("sim_day range", " → ".join(str(x) for x in rec.get("sim_day", []))),
                ("Wall hours", str(rec.get("wall_h", ""))),
                ("Seconds per day", str(rec.get("s_per_day", ""))),
                ("Peak RSS, MB", str(rec.get("peak_rss_mb", ""))),
                ("Chain verify", clip(str(rec.get("chain_verify", "")), 200)),
                ("Datasets exported", str(rec.get("export_written", ""))),
                ("Export failures", str(rec.get("export_failed", ""))),
                ("Secret / personal scan",
                 "clean" if (rec.get("scan") or {}).get("clean") else "SEE DONE.json"),
                ("Provisional", str(rec.get("provisional", ""))),
                ("Finished", str(rec.get("finished", ""))),
                ("Code digest", f"`{str(rec.get('code_digest',''))[:12]}…`"),
                ("B2 upload", clip(str(rec.get("b2_upload", "")), 200)),
            ])
            if counts:
                body += ["## Row counts", "", "| dataset | rows |", "|---|---|"]
                for ds in sorted(counts):
                    link = vault.link(ds, origin=n.name) if ds in dataset_notes else ds
                    body.append(f"| {link} | {counts[ds]:,} |"
                                if isinstance(counts[ds], int)
                                else f"| {link} | {counts[ds]} |")
                body += ["", f"**Total rows:** "
                             f"{sum(v for v in counts.values() if isinstance(v, int)):,}",
                         ""]
        else:
            body += ["## Run record", "",
                     f"No `{run['replay_root']}/{y}/DONE.json` in this worktree, so "
                     f"the year is **pending**: no packages, no row counts. "
                     + ("The replay root is not present here at all."
                        if not run["replay_root_present"] else
                        "The replay root exists but this year has no sentinel."),
                     "",
                     "Re-run `scripts/build_vault.py` after the year completes and "
                     "this section fills itself in.", ""]
        evs = [s["name"] for s in EVENT_SPECS if covers_year(s["when"], y)]
        body += ["## Events in this year", "",
                 vault.links(evs, origin=n.name) or "—", ""]
        body += ["## Run configuration", ""]
        cfg = run["config"]
        body += kv_table([
            ("Label", str(cfg.get("label", ""))),
            ("Slice kind", str(cfg.get("slice_kind", ""))),
            ("Network solved", str(cfg.get("solve_network", ""))),
            ("Datasets omitted",
             vault.links(cfg.get("omit_datasets", []) or [], origin=n.name)
             if cfg.get("omit_datasets") else "none"),
            ("RSS gate, MB", str(cfg.get("rss_gate_mb", ""))),
        ])

    # ------------------------------------------------------------------ MOCs
    moc = vault.notes["MOC_Datasets"]
    moc.heading = "MOC — Datasets"
    moc.extra.update({"count": len(ds_order),
                      "schema_version": schema.get("schema_version", ""),
                      "design_revision": schema.get("design_revision", "")})
    b = moc.body
    b += [f"{len(ds_order)} datasets declared in "
          f"`{DATASETS_YAML.relative_to(ROOT)}` at schema version "
          f"{schema.get('schema_version')}, design revision "
          f"{schema.get('design_revision')}.", ""]
    for cls in ("OBS", "GT", "META"):
        rows = [d for d in ds_order if datasets[d].get("access_class") == cls]
        if not rows:
            continue
        b += [f"## {cls} — {vault.link(f'tier_{cls}', origin=moc.name)}", "",
              "| dataset | title | package | status | rows |", "|---|---|---|---|---|"]
        for d in rows:
            facts = md.get(d, {}).get("facts", {})
            b.append(f"| {vault.link(d, origin=moc.name)} "
                     f"| {clip(datasets[d].get('title',''), 90)} "
                     f"| {facts.get('Package','—')} "
                     f"| {facts.get('Status','undeclared')} "
                     f"| {facts.get('Rows','—')} |")
        b.append("")
    b += ["## Keys", "",
          "Appendix B of `DATASETS.md` names these join keys: "
          + (", ".join(f"`{k}`" for k in appendix_b["keys"])
             if appendix_b["present"] else "*Appendix B not found.*"), "",
          "Declaring dataset per key, derived from the schema's `id_prefix` and "
          "grain (and, for `premises_id`, from Appendix B's prose):", ""]
    b += ["| key | declared by |", "|---|---|"]
    for k in sorted(owners):
        b.append(f"| `{k}` | {vault.link(owners[k], origin=moc.name)} |")
    b += ["", "## Writers", "",
          f"`export/dispatch.py` registers {len(writer_of)} exporters; "
          f"{len(engine_written)} datasets are streamed by the engine itself.", ""]

    moc = vault.notes["MOC_Sources"]
    moc.heading = "MOC — Sources"
    manifest_count = sum(1 for s in sources if "error" not in s)
    moc.extra.update({"manifests": manifest_count,
                      "register_rows": len(sources_md.get("keys", []))})
    b = moc.body
    b += [f"{manifest_count} source manifests under `sources/`; "
          f"{len(sources_md.get('keys', []))} rows in the register "
          f"`sources/SOURCES.md`.", ""]
    if sources_md.get("rules"):
        b += ["## Rules the register applies", ""]
        b += bullets(sources_md["rules"])
    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for s in sources:
        if "error" in s:
            continue
        by_family[(s["relpath"].split("/")[0] if s["relpath"] else "unfiled")].append(s)
    for family in sorted(by_family):
        b += [f"## {family}", "",
              "| source | publisher | use | exposure | sha256 | datasets |",
              "|---|---|---|---|---|---|"]
        for s in sorted(by_family[family], key=lambda r: r["key"]):
            b.append(f"| {vault.link(s['key'], origin=moc.name)} "
                     f"| {clip(s['publisher'], 60)} | {s['intended_use']} "
                     f"| {s['exposure']} | `{s['sha256_prefix']}…` "
                     f"| {vault.links(s['ids']['datasets'], origin=moc.name)} |")
        b.append("")
    unregistered = sorted(s["key"] for s in sources if "error" not in s
                          and s["key"] not in sources_md.get("keys", []))
    if unregistered:
        b += ["## Manifests with no row in `sources/SOURCES.md`", "",
              vault.links(unregistered, origin=moc.name), ""]
    orphan = sorted(set(sources_md.get("keys", [])) -
                    {s["key"] for s in sources if "error" not in s})
    if orphan:
        b += ["## Register rows with no manifest on disk", "",
              ", ".join(f"`{o}`" for o in orphan), ""]

    moc = vault.notes["MOC_Decisions"]
    moc.heading = "MOC — Decisions, assumptions and issues"
    open_issues = [i for i in issues if i["status"] in ("OPEN", "BLOCKED")]
    moc.extra.update({"decisions": len(decisions), "assumptions": len(assumptions),
                      "issues": len(issues), "open_issues": len(open_issues)})
    b = moc.body
    b += [f"{len(decisions)} decisions, {len(assumptions)} assumptions and "
          f"{len(issues)} issues.", ""]
    b += ["## Decisions", "", "| id | date | title | reversible |", "|---|---|---|---|"]
    for d in decisions:
        b.append(f"| {vault.link(d['id'], origin=moc.name)} | {d.get('date','')} "
                 f"| {clip(d.get('title',''), 90)} | {clip(d.get('reversible',''), 40)} |")
    b += ["", "## Assumptions", "", "| id | subject | verdict |", "|---|---|---|"]
    for a in assumptions:
        b.append(f"| {vault.link(a['id'], origin=moc.name)} "
                 f"| {clip(a['subject'], 90)} | {a['verdict']} |")
    b += ["", "## Issues by status", ""]
    by_status: dict[str, list[str]] = defaultdict(list)
    for i in issues:
        by_status[i["status"]].append(i["id"])
    for status in sorted(by_status):
        b += [f"### {status} ({len(by_status[status])})", "",
              vault.links(sorted(by_status[status]), origin=moc.name), ""]

    moc = vault.notes["MOC_Run"]
    moc.heading = "MOC — The 2015–2026 replay"
    done_years = [y for y in YEARS if str(y) in run["done"]]
    moc.extra.update({"playbook": pb_where, "years_complete": len(done_years),
                      "phases": len(pb["phases"]), "gates": len(pb["gates"]),
                      "modules": len(modules)})
    b = moc.body
    b += [f"Playbook read from `{pb_where}`." if pb["present"]
          else "**`PLAYBOOK_v3.1.md` was not found**, so phases, gates, estates, "
               "roles and events are absent from this vault.", ""]
    if pb["status"]:
        b += [f"**Playbook status:** {pb['status']}", ""]
    if pb.get("boundary"):
        b += ["## The boundary (§1.2)", "", "| layer | where | content |",
              "|---|---|---|"]
        for row in pb["boundary"]:
            b.append(f"| {row['layer']} | {row['where']} | {row['content']} |")
        b.append("")
        if pb.get("boundary_rule"):
            b += [f"> {pb['boundary_rule']}", ""]
    if pb.get("scope"):
        b += ["## What sits in Baile Nua and what sits in BNIT (§1.2)", "",
              "| scope | Baile Nua | BNIT |", "|---|---|---|"]
        for row in pb["scope"]:
            b.append(f"| {row['scope']} | {row['baile_nua']} | {row['bnit']} |")
        b.append("")
    if pb["phases"]:
        b += ["## Phases and gates", "",
              "| phase | title | effort | gate | status |", "|---|---|---|---|---|"]
        for p in pb["phases"]:
            b.append(f"| {vault.link(phase_names[p['num']], origin=moc.name)} "
                     f"| {clip(p['title'], 60)} | {p['effort']} "
                     f"| {vault.link(p['gate'], origin=moc.name) if p['gate'] else '—'} "
                     f"| {phase_notes[p['num']].status} |")
        b.append("")
    b += ["## Years", "", "| year | days | status | rows | packages |",
          "|---|---|---|---|---|"]
    for y in YEARS:
        n = year_notes[y]
        b.append(f"| {vault.link(f'Year {y}', origin=moc.name)} "
                 f"| {delivery.get(y, {}).get('days', '—')} | {n.status} "
                 f"| {n.extra.get('rows_total') or '—'} "
                 f"| {len(n.extra.get('packages') or []) or '—'} |")
    b += ["", f"Run sentinels are read from `{run['replay_root']}/<year>/DONE.json` "
              f"inside this worktree only"
              + ("" if run["replay_root_present"]
                 else " — the directory does not exist here, so every year is pending")
              + ". The live run's own directory is never opened.", ""]
    if pb["estates"]:
        b += ["## Estates", "", vault.links([e["name"] for e in pb["estates"]],
                                            origin=moc.name), ""]
    if EVENT_SPECS and pb["present"]:
        b += ["## Events", "", vault.links([s["name"] for s in EVENT_SPECS],
                                           origin=moc.name), ""]
    if pb["roles"]:
        b += ["## FLEXUS-family roles and privacy tiers", "",
              vault.links([role_notes[r["name"]].name for r in pb["roles"]],
                          origin=moc.name), "",
              vault.links([f"tier_{c}" for c in sorted(schema.get("access_classes", {}))]
                          + [f"constraint_{c['id']}" for c in CONSTRAINT_SPECS],
                          origin=moc.name), ""]
    if pb["open_decisions"]:
        b += ["## Playbook open decisions (§8)", "",
              "| ref | became | question | recommendation |", "|---|---|---|---|"]
        for od in pb["open_decisions"]:
            became = vault.link(od["decision"], origin=moc.name) \
                if od.get("decision") else "—"
            b.append(f"| {od['ref']} | {became} | {od['question']} "
                     f"| {od['recommendation']} |")
        b += ["", "*These are the playbook's own D18–D22, not the `D-nnn` of "
                  "`docs/DECISIONS.md`; they are left as text so the two "
                  "numbering schemes cannot be confused.*", ""]
    b += ["## Modules by package", ""]
    by_pkg: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for m in modules:
        parts = m["id"].split(".")
        by_pkg[".".join(parts[:2]) if len(parts) > 2 else parts[0]].append(m)
    for pkg in sorted(by_pkg):
        b += [f"### {pkg} ({len(by_pkg[pkg])})", "", "| module | purpose | writes |",
              "|---|---|---|"]
        for m in sorted(by_pkg[pkg], key=lambda r: r["id"]):
            writes = sorted(writes_by_module.get(m["id"], []))
            b.append(f"| {vault.link(m['id'], origin=moc.name)} "
                     f"| {clip(m['purpose'], 110)} "
                     f"| {vault.links(writes, origin=moc.name) if writes else '—'} |")
        b.append("")
    b += ["## Index", "",
          vault.links(["MOC_Datasets", "MOC_Sources", "MOC_Decisions"],
                      origin=moc.name), ""]

    for n in vault.notes.values():
        stats["notes_by_kind"][n.kind] = stats["notes_by_kind"].get(n.kind, 0) + 1
    stats["inputs"] = {
        "datasets": len(ds_order), "sources": manifest_count,
        "assumptions": len(assumptions), "decisions": len(decisions),
        "issues": len(issues), "modules": len(modules),
        "phases": len(pb["phases"]), "gates": len(pb["gates"]),
        "estates": len(pb["estates"]), "events": len(EVENT_SPECS),
        "roles": len(pb["roles"]), "years_done": len(done_years),
    }
    stats["playbook"] = pb_where
    stats["unverified_events"] = [s["name"] for s in EVENT_SPECS
                                  if not verify_phrase(pb, s["phrase"])]
    return stats


#: Filled by :func:`build` so that a reference to something INSIDE a module -
#: ``export/tariffs.TARIFF_RATES`` - still resolves to the module note, and a
#: bare file name - ``venues.py`` - resolves when exactly one module has that
#: last segment.  The bare top-level package is never a resolution target: a
#: path that trims all the way down to ``baile_nua`` is a miss, not a hit.
_MODULE_REGISTRY: set[str] = set()
_MODULE_BY_STEM: dict[str, list[str]] = {}


def index_modules(names: Iterable[str]) -> None:
    _MODULE_REGISTRY.clear()
    _MODULE_BY_STEM.clear()
    for name in names:
        _MODULE_REGISTRY.add(name)
        _MODULE_BY_STEM.setdefault(name.rsplit(".", 1)[-1], []).append(name)


def phases_mentioned(text: str) -> set[int]:
    """The phase numbers a sentence names, "Phases 18-19" expanded to both."""
    out: set[int] = set()
    for lo, hi in re.findall(r"Phases?\s*(\d+)\s*(?:[–-]\s*(\d+))?", text or ""):
        a = int(lo)
        b = int(hi) if hi else a
        out.update(range(min(a, b), max(a, b) + 1))
    return out


def constraint_name(ref: str) -> str:
    """A §10 reference as a note name: an obligation becomes its constraint note."""
    if any(ref == c["id"] for c in CONSTRAINT_SPECS):
        return f"constraint_{ref}"
    return ref


def covers_year(when: str, year: int) -> bool:
    """Does a playbook event's ``when`` field cover *year*?

    ``when`` is written the way the playbook writes dates: a year, a range
    ("2021-2024", with an en dash or a hyphen), a month ("from 2022-12"), a
    pair of full dates, or a count ("23 transitions").  Two or more years in it
    are read as a span; one year is that year; none matches nothing.
    """
    years = [int(y) for y in re.findall(r"\b(20\d\d)\b", when or "")]
    if not years:
        return False
    return min(years) <= year <= max(years)


def dotted_for(path_or_dotted: str) -> str:
    """``activity/hetus.py`` or ``activity/hetus.py:12`` → ``baile_nua.activity.hetus``."""
    s = (path_or_dotted or "").strip().strip("`")
    s = s.split(":")[0].split(" ")[0]
    if s.endswith(".py"):
        s = s[:-3]
    s = s.replace("/", ".")
    s = re.sub(r"^(scripts\.)?", "", s)
    if not s:
        return ""
    cand = s if s.startswith("baile_nua.") else f"baile_nua.{s}"
    if not _MODULE_REGISTRY:
        return cand
    probe = cand
    while "." in probe:
        if probe in _MODULE_REGISTRY:
            return probe
        probe = probe.rsplit(".", 1)[0]
    stem = cand.rsplit(".", 1)[-1]
    hits = _MODULE_BY_STEM.get(stem, [])
    return hits[0] if len(hits) == 1 else cand


# --------------------------------------------------------------------------- #
# Entry point.
# --------------------------------------------------------------------------- #


def final_scan(root: Path) -> list[str]:
    """Re-scan the finished vault with the release gate's own patterns."""
    hits = []
    for path in sorted(root.rglob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for rx in SECRET_PATTERNS:
            m = rx.search(text)
            if m and "[redacted]" not in m.group(0):
                hits.append(f"{path.relative_to(root)}: /{rx.pattern[:36]}/")
                break
    return hits


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--vault", default=str(ROOT / "vault"),
                    help="output directory (default: <repo>/vault)")
    ap.add_argument("--replay-root", default=str(REPLAY_ROOT),
                    help="where to look for <year>/DONE.json (default: this "
                         "worktree's work/replay_2015_2026; read-only, and never "
                         "point it at a run that is in flight)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    out = Path(args.vault).resolve()
    if not str(out).startswith(str(ROOT)):
        print(f"refusing to write outside the repository: {out}", file=sys.stderr)
        return 2

    vault = Vault()
    stats = build(vault, quiet=args.quiet,
                  replay_root=Path(args.replay_root))
    written, removed, kept = vault.write(out)

    hits = final_scan(out)
    links = sum(len(re.findall(r"\[\[", (out / n.path).read_text(encoding="utf-8")))
                for n in vault.notes.values())

    if not args.quiet:
        print(f"\nvault: {out}")
        print(f"  notes written   {written}  (replaced {removed} stale, "
              f"left {len(kept)} foreign file(s) alone)")
        print(f"  wikilinks       {links}")
        print(f"  notes by type   " + ", ".join(
            f"{k}={v}" for k, v in sorted(stats['notes_by_kind'].items())))
        print(f"  inputs          " + ", ".join(
            f"{k}={v}" for k, v in sorted(stats["inputs"].items())))
        if stats["missing_inputs"]:
            print(f"  ! inputs absent  {', '.join(stats['missing_inputs'])}")
        if stats["unverified_events"]:
            print(f"  ! unverified events {', '.join(stats['unverified_events'])}")
        if vault.unresolved:
            counted = defaultdict(int)
            for origin, name in vault.unresolved:
                counted[name] += 1
            top = sorted(counted.items(), key=lambda kv: -kv[1])[:12]
            print(f"  ! unresolved link targets ({len(counted)} distinct, "
                  f"rendered as plain text): "
                  + ", ".join(f"{n}×{c}" for n, c in top))
        if _SCRUB_HITS:
            print(f"  ! scrubber fired {len(_SCRUB_HITS)} time(s)")
    if hits:
        print("SECRET SCAN FAILED on the generated vault:", file=sys.stderr)
        for h in hits:
            print(f"  {h}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
