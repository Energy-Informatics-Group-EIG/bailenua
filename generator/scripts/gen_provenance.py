#!/usr/bin/env python3
"""Generate ``docs/PROVENANCE.md``: one row per declared dataset, D01 to D31.

What the table claims, and on what evidence
-------------------------------------------
Nothing here is a mapping typed from memory.  Every cell is derived from
something already declared in the tree, and the derivation is named in the
page so a reader can check it:

``dataset``
    ``baile_nua.export.dispatch.ALL_DATASETS`` - 31 ids plus ``D17_aggregate``.

``what it is``
    ``schema/datasets.yaml``: title, access class, grain, subsystem.  The
    status line under it comes from ``export.dispatch`` (who writes it),
    ``export.absent`` (the recorded reason a dataset is not written) and
    ``scripts/replay_config.json`` (what the running replay omits).

``upstream sources``
    Derived, never declared: see :func:`builders_for`.  A citation is then
    resolved against the manifests actually on disk under ``sources/``.  One
    that does not resolve to a file WITH a ``*.manifest.json`` beside it is
    marked UNSOURCED in red, which is the whole point of the column.

``transform``
    ``export.dispatch.EXPORTERS`` for the datasets the export layer writes,
    and the ``StreamWriter`` method that buffers each engine-streamed dataset,
    found by reading which method names it.

``assumptions``
    The two declared registries of ``[A]`` flags:
    ``validation.assumption_sweep.ASSUMPTION_FLAGS`` (56) and
    ``export.tariffs.TARIFF_ASSUMPTIONS`` (8).  A flag reaches a dataset when
    its own ``where`` names one of that dataset's builder modules.

The honest limitation, stated here and in the page
--------------------------------------------------
**The repository declares no dataset-to-source mapping.**  ``datasets.yaml``
carries no ``sources`` key; ``sources_registry.py`` carries no ``datasets``
key.  So the attribution in this table is *inferred* by the three channels in
:func:`builders_for`, and it can be wrong in both directions: it can miss a
source that reaches a dataset through a module that never names it, and it can
over-claim when a module mentions a dataset for an unrelated reason.  Every
citation therefore carries the module it was attributed through, so a reader
can reject one.  Fixing this properly means declaring the mapping in
``datasets.yaml``; this generator is not that fix and does not pretend to be.
"""

from __future__ import annotations

import argparse
import ast
import dataclasses
import json
import pathlib
import re
import sys
from typing import Any, Iterable

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

UNSOURCED = '<span style="color:red">UNSOURCED</span>'

#: Design r4 section 4, the subsystem table (one row per S01..S13).  Mapping a
#: subsystem to the packages that implement it is the one piece of judgement in
#: this generator that is not read from a file, so it is kept small, explicit
#: and cited.  A subsystem in the schema with no entry here is an error, not a
#: silent empty set: see :func:`check_subsystem_map`.
SUBSYSTEM_PACKAGES: dict[str, tuple[str, ...]] = {
    # S01 Environment: weather, solar geometry, daylight
    "S01": ("weather",),
    # S02 Geography and infrastructure: parcels, streets, venues, LV network
    "S02": ("network",),
    # S03 Buildings: fabric, archetype, BER, systems, passport
    "S03": ("physics",),
    # S04 Population synthesis
    "S04": ("population",),
    # S05 Life-course engine
    "S05": ("lifecourse",),
    # S06 Calendar and exogenous events
    "S06": ("engine.calendar", "engine.calendar_events"),
    # S07 Activity and household engine
    "S07": ("activity",),
    # S08 Mobility - no package of its own; trips live in activity/engine.py
    "S08": ("activity",),
    # S09 Building physics and IEQ
    "S09": ("physics",),
    # S10 Appliance and electrical
    "S10": ("devices",),
    # S11 Network
    "S11": ("network",),
    # S12 Observation model
    "S12": ("observation",),
    # S13 Edge export boundary
    "S13": ("edge",),
}

#: Packages whose job is to SCORE the model rather than build it.  Named here
#: for the same reason ``tests/test_source_exposure_consistency.py`` names
#: them: a source a scoring module reads is a source the dataset is compared
#: AGAINST, not one it is built from, and listing it as upstream would be a
#: false provenance claim.
SCORING_PACKAGES = (
    "plausibility", "validation", "report", "calibration", "bench",
    "release", "rl", "privacy", "render", "mimic",
)

#: A module that names more than this many of the 32 dataset ids is a registry
#: or a dispatcher - ``export/dispatch.py`` names 27, ``release/packages.py``
#: 28, ``report/datasets_md.py`` all 32 - and naming a dataset there is not
#: evidence that it builds it.  The producer module is exempt: it is the
#: producer by declaration, not by mention.  The measured gap in this tree is
#: between 8 and 12, so the limit sits in it.
PLUMBING_LIMIT = 10

#: How a module actually LOADS a declared source, as opposed to mentioning its
#: key.  Taken from ``tests/test_source_exposure_consistency.py``, which
#: records why the distinction matters: ``physics/fabric_assessed.py`` names
#: the held-out gas tables in a constant that documents the independent
#: validation axis, and counting mentions flagged a held-out table as an input.
_LOAD_PATTERNS = (
    r"require\(\s*{k}\s*\)",
    r"REGISTRY\[\s*{k}\s*\]",
    r"_cube\(\s*{k}\s*\)",
    r"_read_jsonstat\(\s*{k}\s*\)",
    r"_table\(\s*{k}\s*\)",
    r"source_key\s*=\s*{k}",
    r"^\s*\w+\s*=\s*{k}\s*$",
    # An element of a *_SOURCE_KEYS tuple, which is how export/tariffs.py
    # holds the keys it reads.
    r"^\s*{k}\s*,\s*$",
    # A declaration that carries the key and is then loaded through it, which
    # is how `weather/station.py` reads Met Éireann: `StationSpec(key=...)`
    # followed by `require(spec.key)`.  Without this the weather sources
    # reached no dataset at all.
    r"\bkey\s*=\s*{k}",
    # The other branch of a conditional choice of key, which is how
    # `population/names.py` picks the boys' or the girls' table.  Without it
    # the boys' table was attributed and the girls' was reported as read by
    # nothing - a false finding, caught by checking the five before publishing.
    r"\belse\s+{k}",
)

#: How a module reads the WHOLE declared register rather than a named key.
#: ``export/run_manifest.py`` does exactly this to build D23's
#: ``input_sources``, so without it D23 - the provenance dataset - would cite
#: nothing.
_CORPUS_PATTERNS = (
    re.compile(r"\bfor\s+\w+\s+in\s+sorted\(\s*REGISTRY\s*\)"),
    re.compile(r"\bfor\s+\w+\s+in\s+REGISTRY\b"),
    re.compile(r"\ball_manifests\s*\("),
)

#: The whole declared register, cited as one line rather than as 69.
CORPUS_REF = "<the whole declared source register>"

#: Known defects that bear on a dataset's provenance and that the issue-log
#: scan below cannot find, because their headings name the symptom and not the
#: dataset.  Hand-declared, and that is why each one names its issue: a reader
#: checks it against ``docs/ISSUES.md`` rather than taking it on trust.
DECLARED_DEFECTS: dict[str, tuple[str, ...]] = {
    "D14": (
        "I-110 (FIXED in Phase 2): `CalendarDay.is_dst` and `dst_transition` "
        "were inverted — Irish winter GMT is a NEGATIVE DST adjustment in "
        "tzdata, so `bool(t.dst())` read true all winter — and the two "
        "transitions were labelled as each other. Summer time is now decided "
        "by the UTC offset at 12:00 UTC. Every artefact that reported a DST "
        "transition date before the fix reported the wrong one.",
    ),
    "D15": (
        "I-111 (FIXED on branch `fix-i111-d15-dst`; D15 to be re-exported for "
        "affected packages): D15's `is_dst` COLUMN carried the same inversion "
        "as I-110 — built from tzdata's `dst()`, truthy in an Irish winter — "
        "so the column read true in winter and false in summer. Measured in "
        "the shipped package: January mean 1.0, July mean 0.0 over 525,600 "
        "rows. The column is CORRECTED under I-111; the shipped value is not "
        "correct. This issue is not in THIS worktree's `docs/ISSUES.md`, "
        "which predates it — it is logged in the main checkout.",
    ),
}

#: A path literal under ``sources/`` - how ``engine/calendar.py`` reads the
#: derived holiday and school-break tables, bypassing the registry entirely.
_SOURCE_PATH = re.compile(r"[\"'](sources/[A-Za-z0-9_\-./]+)[\"']")


# --------------------------------------------------------------------------- #
# the source register as it is ON DISK
# --------------------------------------------------------------------------- #

@dataclasses.dataclass(frozen=True)
class Manifest:
    """One ``sources/**/*.manifest.json``, normalised."""

    relpath: str
    key: str
    title: str
    publisher: str
    licence: str
    sha256: str
    retrieved: str
    file_exists: bool
    #: Is the MANIFEST committed?  A manifest present on disk but untracked
    #: resolves - the bytes and the record are both there - but it is not yet
    #: part of the repository, and a reader of the committed tree would not
    #: find it.  Said, not hidden.
    manifest_tracked: bool = True

    @property
    def resolves(self) -> bool:
        """A citation resolves only if the bytes AND the manifest are there."""
        return self.file_exists and bool(self.sha256)


def _tracked_manifests(project_root: pathlib.Path) -> set[str] | None:
    """``git ls-files sources`` as a set of relpaths, or ``None`` if unknown."""
    import subprocess

    try:
        proc = subprocess.run(
            ["git", "ls-files", "--", "sources"],
            cwd=project_root, capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return {
        line[len("sources/"):]
        for line in proc.stdout.splitlines()
        if line.startswith("sources/")
    }


def load_manifests(sources_dir: pathlib.Path) -> dict[str, Manifest]:
    """``{relpath: Manifest}`` for every manifest under ``sources/``.

    Manifests in this tree carry two shapes: the one ``sources.fetch`` writes
    (``relpath``, ``retrieved_at``) and a hand-written one (no ``relpath``,
    ``fetched_utc``).  Both are read; neither is normalised on disk.
    """
    out: dict[str, Manifest] = {}
    if not sources_dir.is_dir():
        return out
    tracked = _tracked_manifests(sources_dir.parent)
    for path in sorted(sources_dir.rglob("*.manifest.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        data_path = path.with_name(path.name[: -len(".manifest.json")])
        rel = str(data_path.relative_to(sources_dir))
        out[rel] = Manifest(
            relpath=doc.get("relpath") or rel,
            key=str(doc.get("key") or ""),
            title=str(doc.get("title") or ""),
            publisher=str(doc.get("publisher") or ""),
            licence=str(doc.get("licence") or ""),
            sha256=str(doc.get("sha256") or ""),
            retrieved=str(
                doc.get("retrieved_at")
                or doc.get("retrieved_at_utc")
                or doc.get("fetched_utc")
                or ""
            ),
            file_exists=data_path.is_file(),
            manifest_tracked=(
                True if tracked is None
                else str(path.relative_to(sources_dir)) in tracked
            ),
        )
    return out


def manifests_by_key(manifests: dict[str, Manifest]) -> dict[str, Manifest]:
    return {m.key: m for m in manifests.values() if m.key}


# --------------------------------------------------------------------------- #
# citations
# --------------------------------------------------------------------------- #

@dataclasses.dataclass(frozen=True)
class Citation:
    """One upstream source a dataset is claimed to rest on."""

    #: ``"key"`` for a declared source key, ``"path"`` for a bare path literal.
    kind: str
    ref: str
    #: The module the claim was attributed through, so a reader can reject it.
    via: str
    manifest: Manifest | None = None
    #: Why it does not resolve, when it does not.
    unresolved_reason: str = ""

    @property
    def resolved(self) -> bool:
        if self.kind == "corpus":
            # The whole register: resolved when every key in it resolved, which
            # :meth:`Provenance._resolve` has already decided.
            return not self.unresolved_reason
        return self.manifest is not None and self.manifest.resolves


# --------------------------------------------------------------------------- #
# the model
# --------------------------------------------------------------------------- #

@dataclasses.dataclass
class DatasetRow:
    dataset_id: str
    name: str
    title: str
    access_class: str
    grain: str
    subsystem: str
    status: str
    transform: list[str]
    builders: list[str]
    citations: list[Citation]
    assumptions: list[str]
    notes: list[str]
    defects: list[str]


class Provenance:
    """Everything the page is built from, derived once."""

    def __init__(self, project_root: pathlib.Path = PROJECT_ROOT) -> None:
        import baile_nua
        import baile_nua.sources_registry  # noqa: F401  (populates REGISTRY)
        from baile_nua.sources import REGISTRY

        self.project_root = project_root
        self.pkg_root = pathlib.Path(baile_nua.__file__).resolve().parent
        self.registry = dict(REGISTRY)
        self.sources_dir = project_root / "sources"
        self.manifests = load_manifests(self.sources_dir)
        self.by_key = manifests_by_key(self.manifests)
        self.texts = {
            str(p.relative_to(self.pkg_root)): p.read_text(encoding="utf-8")
            for p in sorted(self.pkg_root.rglob("*.py"))
        }
        self.schema = self._load_schema()
        self.dataset_ids = self._dataset_ids()
        self._dataset_patterns = {
            d: re.compile(r"\b" + re.escape(d) + r"\b") for d in self.dataset_ids
        }
        self.names_count = {
            mod: sum(1 for p in self._dataset_patterns.values() if p.search(text))
            for mod, text in self.texts.items()
        }
        self._keys_cache: dict[str, list[str]] = {}
        self._readers_cache: dict[str, list[str]] | None = None
        self.flags = self._load_flags()
        self.omitted = self._replay_omissions()
        self.issues = self._load_issues()

    # -- inputs ---------------------------------------------------------- #

    def _load_schema(self) -> dict[str, Any]:
        import yaml

        path = self.pkg_root / "schema" / "datasets.yaml"
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    def _dataset_ids(self) -> tuple[str, ...]:
        from baile_nua.export.dispatch import ALL_DATASETS

        return tuple(ALL_DATASETS)

    def _load_flags(self) -> tuple[Any, ...]:
        from baile_nua.export.tariffs import TARIFF_ASSUMPTIONS
        from baile_nua.validation.assumption_sweep import ASSUMPTION_FLAGS

        return tuple(ASSUMPTION_FLAGS) + tuple(TARIFF_ASSUMPTIONS)

    def _load_issues(self) -> dict[str, list[str]]:
        """``{dataset_id: ["I-nnn (STATUS) — heading", ...]}`` from the log.

        Attribution is by the issue's own HEADING naming the dataset id, which
        is narrow on purpose: an issue that mentions a dataset in passing is
        not an issue about it.  The cost of that narrowness is real and is why
        :data:`DECLARED_DEFECTS` exists - I-110 and I-111 are both about a
        dataset column and neither heading names a dataset.
        """
        path = self.project_root / "docs" / "ISSUES.md"
        out: dict[str, list[str]] = {}
        if not path.is_file():
            return out
        text = path.read_text(encoding="utf-8")
        heads = list(re.finditer(
            r"^#{2,3}\s+(I-\d+)\s*[—\-]\s*(.+)$", text, re.M))
        for i, head in enumerate(heads):
            issue_id, title = head.group(1), head.group(2).strip()
            end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
            body = text[head.end():end]
            status = re.search(r"\*\*Status:\s*([^*\n]+)", body)
            label = f"{issue_id} ({(status.group(1) if status else '?').strip()})"
            for dataset_id in self.dataset_ids:
                if self._dataset_patterns[dataset_id].search(title):
                    out.setdefault(dataset_id, []).append(f"{label} — {title}")
        return out

    def _replay_omissions(self) -> tuple[str, ...]:
        path = self.project_root / "scripts" / "replay_config.json"
        if not path.is_file():
            return ()
        try:
            cfg = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return ()
        return tuple(cfg.get("omit_datasets") or ())

    # -- transform ------------------------------------------------------- #

    def transform_for(self, dataset_id: str) -> list[str]:
        """Who writes it, named as ``module.function``."""
        from baile_nua.export.dispatch import (
            EXPORTERS, RELOCATED_TO_RUN, WRITTEN_BY_THE_ENGINE,
        )

        out: list[str] = []
        fn = EXPORTERS.get(dataset_id)
        if fn is not None:
            out.append(f"{fn.__module__}.{fn.__name__}")
            if dataset_id in RELOCATED_TO_RUN:
                out.append(
                    f"written under <package>/{RELOCATED_TO_RUN[dataset_id]}/ "
                    f"(dispatch.RELOCATED_TO_RUN)"
                )
        if dataset_id in WRITTEN_BY_THE_ENGINE:
            for method in self.stream_writer_methods(dataset_id):
                out.append(
                    f"baile_nua.engine.stream_writer.StreamWriter.{method}"
                )
            if not self.stream_writer_methods(dataset_id):
                out.append("baile_nua.engine.stream_writer.StreamWriter")
        return out

    def stream_writer_methods(self, dataset_id: str) -> list[str]:
        """Which ``StreamWriter`` method buffers this dataset, read from its AST."""
        text = self.texts.get("engine/stream_writer.py")
        if text is None:
            return []
        tree = ast.parse(text)
        wanted = (
            re.compile(r'_add(?:_frame)?\(\s*"' + re.escape(dataset_id) + r'"'),
        )
        out: list[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name.startswith("__"):
                continue
            segment = ast.get_source_segment(text, node) or ""
            if any(p.search(segment) for p in wanted):
                out.append(node.name)
        return sorted(out)

    # -- status ---------------------------------------------------------- #

    def status_for(self, dataset_id: str) -> tuple[str, list[str]]:
        from baile_nua.export.absent import ABSENT, OWNED_ELSEWHERE
        from baile_nua.export.dispatch import EXPORTERS, WRITTEN_BY_THE_ENGINE

        notes: list[str] = []
        if dataset_id in self.omitted:
            notes.append(
                "OMITTED from the running 2015-2026 replay by "
                "`scripts/replay_config.json` `omit_datasets`"
            )
        if dataset_id in OWNED_ELSEWHERE:
            return "owned elsewhere", notes + [OWNED_ELSEWHERE[dataset_id]]
        if dataset_id in ABSENT:
            reason = ABSENT[dataset_id]
            missing = reason.get("missing_required") or []
            notes.append(str(reason.get("reason", "")).strip())
            if missing:
                notes.append("missing required fields: " + ", ".join(missing))
            return "not written", notes
        if dataset_id in WRITTEN_BY_THE_ENGINE:
            if dataset_id in self.omitted:
                return "streamed by the engine, omitted here", notes
            return "streamed by the engine", notes
        if dataset_id in EXPORTERS:
            return "written by the export layer", notes
        return "no exporter and no recorded reason", notes

    def defects_for(self, dataset_id: str) -> list[str]:
        """Known defects bearing on provenance: declared, then from the log."""
        return list(DECLARED_DEFECTS.get(dataset_id, ())) + \
            list(self.issues.get(dataset_id, ()))

    # -- attribution ----------------------------------------------------- #

    def producer_modules(self, dataset_id: str) -> list[str]:
        from baile_nua.export.dispatch import EXPORTERS, WRITTEN_BY_THE_ENGINE

        out: list[str] = []
        fn = EXPORTERS.get(dataset_id)
        if fn is not None:
            rel = fn.__module__[len("baile_nua."):].replace(".", "/") + ".py"
            if rel in self.texts:
                out.append(rel)
        if dataset_id in WRITTEN_BY_THE_ENGINE:
            out.append("engine/stream_writer.py")
        return out

    def subsystem_modules(self, dataset_id: str) -> list[str]:
        decl = self.schema["datasets"].get(dataset_id, {})
        subsystem = str(decl.get("subsystem") or "")
        prefixes = SUBSYSTEM_PACKAGES.get(subsystem, ())
        out = []
        for mod in self.texts:
            stem = mod[:-3].replace("/", ".")
            if any(stem == p or stem.startswith(p + ".") for p in prefixes):
                out.append(mod)
        return sorted(out)

    def naming_modules(self, dataset_id: str) -> list[str]:
        """Non-scoring, non-plumbing modules that name the dataset id."""
        pattern = self._dataset_patterns[dataset_id]
        out = []
        for mod, text in self.texts.items():
            if mod.split("/")[0] in SCORING_PACKAGES:
                continue
            if mod.startswith("sources"):
                continue
            if self.names_count.get(mod, 0) > PLUMBING_LIMIT:
                continue
            if pattern.search(text):
                out.append(mod)
        return sorted(out)

    def builders_for(self, dataset_id: str) -> list[str]:
        """The modules this dataset's provenance is read from.

        Three channels, none of them a mapping typed into this file:

        1. the **producer** - ``dispatch.EXPORTERS`` or the ``StreamWriter``;
        2. the dataset's **subsystem** package, per the schema's ``subsystem``
           field and the design r4 section 4 table (:data:`SUBSYSTEM_PACKAGES`);
        3. any other module that **names the dataset id**, excluding the
           scoring packages and the registries (:data:`PLUMBING_LIMIT`).
        """
        mods = set(self.producer_modules(dataset_id))
        mods |= set(self.subsystem_modules(dataset_id))
        mods |= set(self.naming_modules(dataset_id))
        return sorted(mods)

    # -- citations ------------------------------------------------------- #

    def _loads(self, text: str, key: str) -> bool:
        # The substring test first: 147 modules x 69 keys x 10 patterns is
        # 101,000 regex passes over whole files, and all but a handful can be
        # ruled out by one `in`.
        if key not in text:
            return False
        quoted = r"[\"']" + re.escape(key) + r"[\"']"
        return any(
            re.search(p.format(k=quoted), text, re.M) for p in _LOAD_PATTERNS
        )

    def keys_loaded_by(self, module: str) -> list[str]:
        """Cached: the scan is 69 keys x 9 patterns over a module's whole text,
        and the render pass asks for it once per dataset per section."""
        cached = self._keys_cache.get(module)
        if cached is None:
            text = self.texts.get(module, "")
            cached = sorted(k for k in self.registry if self._loads(text, k))
            self._keys_cache[module] = cached
        return cached

    def readers_of(self, key: str) -> list[str]:
        """Every module outside ``sources*`` that loads this key."""
        if self._readers_cache is None:
            readers: dict[str, list[str]] = {k: [] for k in self.registry}
            for module in sorted(self.texts):
                if module.startswith("sources"):
                    continue
                for loaded in self.keys_loaded_by(module):
                    readers[loaded].append(module)
            self._readers_cache = readers
        return self._readers_cache.get(key, [])

    def paths_cited_by(self, module: str) -> list[str]:
        text = self.texts.get(module, "")
        return sorted({m.group(1) for m in _SOURCE_PATH.finditer(text)})

    def reads_whole_register(self, module: str) -> bool:
        text = self.texts.get(module, "")
        return any(p.search(text) for p in _CORPUS_PATTERNS)

    def source_roles(self, rows: list["DatasetRow"]) -> dict[str, dict[str, Any]]:
        """Each declared key's role: upstream, scoring-only, or read by nothing.

        D23's ``input_sources`` records the whole DECLARED corpus - its own
        note says so: "the set it could have read and not the set it did" - so
        a source it records and this page does not cite upstream is not
        automatically a gap.  A source that only a SCORING module reads is one
        the model is compared against, and listing it as upstream would be a
        false provenance claim.  The distinction is published here so the
        validator can check it instead of guessing at it.
        """
        cited = {
            c.ref for row in rows for c in row.citations if c.kind == "key"
        }
        out: dict[str, dict[str, Any]] = {}
        for key in sorted(self.registry):
            readers = self.readers_of(key)
            scoring = [m for m in readers if m.split("/")[0] in SCORING_PACKAGES]
            if key in cited:
                role = "upstream"
            elif scoring:
                role = "scoring-only"
            elif readers:
                role = "read-but-unattributed"
            else:
                role = "read-by-nothing"
            out[key] = {"role": role, "readers": readers}
        return out

    def flags_for(self, builders: Iterable[str]) -> list[Any]:
        """Flags whose own ``where`` names one of these modules."""
        mods = set(builders)
        out = []
        for flag in self.flags:
            where = " ".join(str(w) for w in flag.where)
            if any(m in where for m in mods):
                out.append(flag)
        return out

    def citations_for(self, dataset_id: str, builders: list[str]) -> list[Citation]:
        found: dict[tuple[str, str], Citation] = {}

        def add(kind: str, ref: str, via: str) -> None:
            if (kind, ref) in found:
                return
            found[(kind, ref)] = self._resolve(kind, ref, via)

        for module in builders:
            for key in self.keys_loaded_by(module):
                add("key", key, module)
            for path in self.paths_cited_by(module):
                add("path", path, module)
            if self.reads_whole_register(module):
                add("corpus", CORPUS_REF, module)
        for flag in self.flags_for(builders):
            for key in flag.sources:
                add("key", key, f"assumption {flag.flag_id}")
        return [found[k] for k in sorted(found)]

    def _resolve(self, kind: str, ref: str, via: str) -> Citation:
        if kind == "corpus":
            unresolved = []
            for key, src in sorted(self.registry.items()):
                m = self.by_key.get(key) or self.manifests.get(src.relpath)
                if m is None or not m.resolves:
                    unresolved.append(key)
            if unresolved:
                return Citation(
                    kind, ref, via, None,
                    f"{len(unresolved)} of {len(self.registry)} declared keys "
                    f"do not resolve: {', '.join(unresolved[:5])}",
                )
            return Citation(kind, ref, via, None)

        if kind == "key":
            manifest = self.by_key.get(ref)
            if manifest is None:
                src = self.registry.get(ref)
                if src is not None:
                    manifest = self.manifests.get(src.relpath)
            if manifest is None:
                return Citation(
                    kind, ref, via, None,
                    "no sources/**/*.manifest.json declares this key",
                )
            if not manifest.file_exists:
                return Citation(
                    kind, ref, via, manifest,
                    f"manifest present, the bytes are not: sources/{manifest.relpath}",
                )
            return Citation(kind, ref, via, manifest)

        rel = ref[len("sources/"):] if ref.startswith("sources/") else ref
        manifest = self.manifests.get(rel)
        data = self.sources_dir / rel
        if manifest is None:
            return Citation(
                kind, ref, via, None,
                (
                    "the file is on disk with no manifest beside it"
                    if data.is_file()
                    else "neither the file nor a manifest is on disk"
                ),
            )
        if not manifest.file_exists:
            return Citation(
                kind, ref, via, manifest,
                "manifest present, the bytes are not",
            )
        return Citation(kind, ref, via, manifest)

    # -- rows ------------------------------------------------------------ #

    def rows(self) -> list[DatasetRow]:
        out = []
        for dataset_id in self.dataset_ids:
            decl = self.schema["datasets"].get(dataset_id, {})
            builders = self.builders_for(dataset_id)
            citations = self.citations_for(dataset_id, builders)
            status, notes = self.status_for(dataset_id)
            flags = self.flags_for(builders)
            out.append(DatasetRow(
                dataset_id=dataset_id,
                name=str(decl.get("name") or ""),
                title=str(decl.get("title") or ""),
                access_class=str(decl.get("access_class") or ""),
                grain=str(decl.get("grain") or ""),
                subsystem=str(decl.get("subsystem") or ""),
                status=status,
                transform=self.transform_for(dataset_id),
                builders=builders,
                citations=citations,
                assumptions=sorted({f.flag_id for f in flags}, key=_flag_sort),
                notes=[n for n in notes if n],
                defects=self.defects_for(dataset_id),
            ))
        return out


def _flag_sort(flag_id: str) -> tuple[int, str]:
    m = re.match(r"A-(\d+)([a-z]*)", flag_id)
    return (int(m.group(1)), m.group(2)) if m else (9999, flag_id)


def check_subsystem_map(prov: Provenance) -> list[str]:
    """Every subsystem the schema uses must be mapped.  Silence is a bug."""
    used = {
        str(d.get("subsystem"))
        for d in prov.schema["datasets"].values()
        if d.get("subsystem")
    }
    return sorted(used - set(SUBSYSTEM_PACKAGES))


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #

def _cell(parts: list[str]) -> str:
    return "<br>".join(p for p in parts if p) or "—"


def _esc(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").strip()


def render_source_cell(citations: list[Citation]) -> str:
    if not citations:
        return (
            "no module attributed to this dataset loads a declared source "
            "and no assumption flag names one"
        )
    parts = []
    for c in citations:
        ref = f"`{_esc(c.ref)}`"
        if c.kind == "corpus" and c.resolved:
            parts.append(
                f"`{_esc(CORPUS_REF)}` — **every source declared in "
                f"sources_registry.py**, each with its own publisher, licence "
                f"and SHA-256: the module iterates the register rather than "
                f"naming keys, so see the digest register below "
                f"<sub>via {_esc(c.via)}</sub>"
            )
        elif c.resolved and c.manifest is not None:
            untracked = (
                " <sub>(manifest on disk but **not committed**)</sub>"
                if not c.manifest.manifest_tracked else ""
            )
            parts.append(
                f"{ref} — {_esc(c.manifest.publisher)} — "
                f"{_esc(_short(c.manifest.licence))} "
                f"<sub>via {_esc(c.via)}</sub>{untracked}"
            )
        else:
            parts.append(
                f"{ref} — {UNSOURCED} — {_esc(c.unresolved_reason)} "
                f"<sub>via {_esc(c.via)}</sub>"
            )
    return _cell(parts)


def _short(licence: str, limit: int = 64) -> str:
    licence = " ".join(licence.split())
    return licence if len(licence) <= limit else licence[: limit - 1] + "…"


def render(prov: Provenance, rows: list[DatasetRow]) -> str:
    cited = _cited_register(rows)
    n_resolved = sum(
        1 for r in rows if r.citations and all(c.resolved for c in r.citations)
    )
    n_unsourced_cells = sum(
        1 for r in rows if any(not c.resolved for c in r.citations)
    )
    n_no_citation = sum(1 for r in rows if not r.citations)

    out: list[str] = []
    out.append("# Baile Nua / HRSD_Occupants — provenance\n")
    out.append(
        f"**{prov.schema.get('label', '')}**\n"
    )
    out.append(
        "One row per declared dataset: what it is, every upstream source that "
        "could be attributed to it with its publisher and licence, the module "
        "and function that produces it, and the `[A]` assumption numbers it "
        "depends on.\n"
    )
    out.append(
        "Generated by `scripts/gen_provenance.py`. Checked by "
        "`scripts/validate_provenance.py` against D23 (run manifests, for the "
        "source digests) and D24 (calibration targets, for the assumption and "
        "source register). **Do not edit by hand** — regenerate.\n"
    )

    out.append("## How to read this, and what it does not claim\n")
    out.append(
        "The repository declares **no dataset-to-source mapping**: "
        "`schema/datasets.yaml` has no `sources` key and `sources_registry.py` "
        "has no `datasets` key. Every citation below is therefore *inferred*, "
        "by three channels, and each one carries the module it was attributed "
        "through so a reader can reject it:\n"
    )
    out.append(
        "1. the **producer** — `export.dispatch.EXPORTERS`, or the "
        "`StreamWriter` method that buffers the dataset;\n"
        "2. the dataset's **subsystem** package, from the schema's `subsystem` "
        "field and the design r4 §4 subsystem table;\n"
        "3. any other module that **names the dataset id**, excluding the "
        "scoring packages (a source a scoring module reads is one the dataset "
        "is compared against, not built from) and the registries that name "
        f"more than {PLUMBING_LIMIT} datasets.\n"
    )
    out.append(
        "The inference can be wrong in both directions. It misses a source "
        "that reaches a dataset only through a module that never names it, and "
        "it over-claims when a module mentions a dataset for an unrelated "
        "reason. The fix is to declare the mapping in `datasets.yaml`; this "
        "page is not that fix.\n"
    )
    out.append(
        f"A citation resolves only when a file under `sources/` exists **and** "
        f"a `*.manifest.json` sits beside it carrying its SHA-256, publisher, "
        f"licence and retrieval date. One that does not is marked "
        f"{UNSOURCED}.\n"
    )
    out.append(
        f"**Today: {len(rows)} datasets. {n_resolved} resolve fully "
        f"(at least one citation, every citation resolved). "
        f"{n_unsourced_cells} carry at least one {UNSOURCED} citation. "
        f"{n_no_citation} have no citation at all.**\n"
    )
    untracked = sorted(
        rel for rel, m in prov.manifests.items() if not m.manifest_tracked
    )
    if untracked:
        out.append(
            f"{len(untracked)} of the {len(prov.manifests)} manifests under "
            f"`sources/` are **present on disk but not committed**, so a "
            f"reader of the committed tree would not find them. They resolve "
            f"here because the bytes and the record are both on this disk, "
            f"and the citation says so: "
            + ", ".join(f"`sources/{r}`" for r in untracked)
            + ".\n"
        )
    if prov.omitted:
        out.append(
            "The 2015-2026 replay now running omits "
            + ", ".join(f"**{d}**" for d in prov.omitted)
            + " (`scripts/replay_config.json`), so no part of it exists for "
            "those years however the table reads.\n"
        )

    out.append("## The table\n")
    out.append(
        "| Dataset | What it is | Upstream sources — publisher — licence | "
        "Transform | Assumptions |"
    )
    out.append("|---|---|---|---|---|")
    for row in rows:
        ident = _cell([
            f"**{row.dataset_id}**",
            f"`{row.name}`" if row.name else "",
            f"{row.access_class}{' · ' + row.subsystem if row.subsystem else ''}",
        ])
        what = _cell(
            [_esc(row.title), f"grain: {_esc(row.grain)}" if row.grain else "",
             f"*{_esc(row.status)}*"]
            + [f"<sub>{_esc(_short(n, 240))}</sub>" for n in row.notes]
            + [f"<sub>⚠ {_esc(_short(d, 560))}</sub>" for d in row.defects]
        )
        transform = _cell([f"`{_esc(t)}`" for t in row.transform]) \
            if row.transform else "— (nothing in this tree writes it)"
        assumptions = ", ".join(row.assumptions) if row.assumptions else "—"
        out.append(
            f"| {ident} | {what} | {render_source_cell(row.citations)} "
            f"| {transform} | {assumptions} |"
        )
    out.append("")

    out.append("## Source digest register\n")
    out.append(
        "Every source cited above, once, with the digest the validator "
        "compares against D23's `input_sources` and D24's `source_sha256`. "
        "The licence is reproduced in full here; the table abbreviates it.\n"
    )
    out.append(
        "| Source | Resolves | Publisher | Licence | SHA-256 | Retrieved |"
    )
    out.append("|---|---|---|---|---|---|")
    for ref, cit in cited:
        if cit.kind == "corpus":
            out.append(
                f"| `{_esc(ref)}` "
                f"| {'yes — every declared key resolves' if cit.resolved else UNSOURCED + ' — ' + _esc(cit.unresolved_reason)} "
                f"| (the register) | (per source) | (per source) | (per source) |"
            )
        elif cit.resolved and cit.manifest is not None:
            m = cit.manifest
            out.append(
                f"| `{_esc(ref)}` | yes — `sources/{_esc(m.relpath)}`"
                f"{'' if m.manifest_tracked else ' (manifest **not committed**)'} "
                f"| {_esc(m.publisher)} | {_esc(m.licence)} "
                f"| `{m.sha256}` | {_esc(m.retrieved)} |"
            )
        else:
            out.append(
                f"| `{_esc(ref)}` | {UNSOURCED} — {_esc(cit.unresolved_reason)} "
                f"| — | — | — | — |"
            )
    out.append("")

    out.append("## Assumption register\n")
    out.append(
        "The `[A]` flags reaching at least one dataset above, from "
        "`validation.assumption_sweep.ASSUMPTION_FLAGS` and "
        "`export.tariffs.TARIFF_ASSUMPTIONS`. `verdict` is the U30 sweep's: "
        "`RETIRED` a public source was found and the assumption is now scored "
        "against it; `SOURCE_FOUND` a source exists and wiring it in is a "
        "named step; `KEPT` searched, nothing published; `WRONG_INSTRUMENT` "
        "PxStat cannot carry this kind of evidence at all.\n"
    )
    out.append("| Flag | Verdict | Subject | Declared in | Datasets |")
    out.append("|---|---|---|---|---|")
    used = {}
    for row in rows:
        for flag_id in row.assumptions:
            used.setdefault(flag_id, []).append(row.dataset_id)
    by_id = {f.flag_id: f for f in prov.flags}
    for flag_id in sorted(used, key=_flag_sort):
        flag = by_id[flag_id]
        out.append(
            f"| {flag_id} | {_esc(flag.verdict)} | {_esc(flag.subject)} "
            f"| {_esc('; '.join(str(w) for w in flag.where))} "
            f"| {', '.join(used[flag_id])} |"
        )
    out.append("")

    unused = sorted(set(by_id) - set(used), key=_flag_sort)
    if unused:
        out.append(
            f"{len(unused)} declared flags reach no dataset by the attribution "
            f"above, which is a gap in the attribution and not a claim that "
            f"they are unused: {', '.join(unused)}.\n"
        )

    cited_relpaths = {
        c.manifest.relpath for _, c in cited if c.manifest is not None
    }
    if any(c.kind == "corpus" for _, c in cited):
        # A module that iterates the register cites every key in it.
        cited_relpaths |= {s.relpath for s in prov.registry.values()}
    uncited = sorted(
        rel for rel, m in prov.manifests.items()
        if m.relpath not in cited_relpaths and rel not in cited_relpaths
    )
    roles = prov.source_roles(rows)
    not_upstream = {
        key: info for key, info in roles.items() if info["role"] != "upstream"
    }
    out.append("## Declared sources that are not upstream of any dataset\n")
    out.append(
        "D23's `input_sources` records the whole **declared** corpus — its own "
        "note says so: \"the set it could have read and not the set it did\" — "
        "so a key D23 records and the table above does not cite is not "
        "automatically a gap. This section says which, and why, so the "
        "validator checks the claim rather than guessing at it.\n"
    )
    out.append(
        "- `scoring-only` — read only by a scoring module "
        f"({', '.join(SCORING_PACKAGES)}). The model is compared **against** "
        "it; calling it upstream would be a false provenance claim.\n"
        "- `read-but-unattributed` — a non-scoring module loads it and the "
        "attribution above could not reach a dataset from that module. A gap "
        "in the attribution.\n"
        "- `read-by-nothing` — declared and consumed by no module at all. A "
        "declared source that nothing consumes is an unverified claim "
        "(`tests/test_sources_provenance.py`), so this is a finding.\n"
    )
    out.append("| Source | Role | Read by |")
    out.append("|---|---|---|")
    for key, info in sorted(not_upstream.items()):
        readers = ", ".join(f"`{r}`" for r in info["readers"]) or "— nothing"
        out.append(f"| `{_esc(key)}` | `{info['role']}` | {readers} |")
    if not not_upstream:
        out.append("| — | — | every declared source is upstream of a dataset |")
    out.append("")

    out.append("## Manifested sources no dataset cites\n")
    if uncited:
        out.append(
            f"{len(uncited)} of the {len(prov.manifests)} manifested files "
            f"under `sources/` are cited by no dataset above. A declared "
            f"source that nothing consumes is an unverified claim "
            f"(`tests/test_sources_provenance.py`), so this list is a finding, "
            f"not a footnote.\n"
        )
        for rel in uncited:
            m = prov.manifests[rel]
            out.append(f"- `sources/{rel}` — `{m.key or 'no key'}` — {_esc(m.title)}")
    else:
        out.append("None.\n")
    out.append("")
    return "\n".join(out)


def _cited_register(rows: list[DatasetRow]) -> list[tuple[str, Citation]]:
    seen: dict[str, Citation] = {}
    for row in rows:
        for c in row.citations:
            seen.setdefault(c.ref, c)
    return sorted(seen.items())


# --------------------------------------------------------------------------- #

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--out", default=str(PROJECT_ROOT / "docs" / "PROVENANCE.md"),
        help="where to write the page (default: docs/PROVENANCE.md)",
    )
    ap.add_argument(
        "--project-root", default=str(PROJECT_ROOT),
        help="tree to read sources/, schema and replay config from",
    )
    ap.add_argument("--stdout", action="store_true", help="print, do not write")
    args = ap.parse_args(argv)

    prov = Provenance(pathlib.Path(args.project_root).resolve())
    unmapped = check_subsystem_map(prov)
    if unmapped:
        print(
            "SUBSYSTEM_PACKAGES does not map: " + ", ".join(unmapped),
            file=sys.stderr,
        )
        return 2
    rows = prov.rows()
    page = render(prov, rows)
    if args.stdout:
        print(page)
    else:
        out = pathlib.Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page, encoding="utf-8")
        print(f"wrote {out} ({len(page)} bytes, {len(rows)} datasets)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
