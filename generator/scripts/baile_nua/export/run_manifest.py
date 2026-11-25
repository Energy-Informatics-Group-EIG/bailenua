"""D23 - run manifests, written for runs that recorded no manifest of their own.

A previous pass recorded D23 as unwritable, and its reason was right as far as
it went: ``run_diagnostics.json`` carries the master seed, the coupling mode
and the slice, and carries none of ``code_git_sha``, ``code_tree_hash``,
``input_sources`` or ``outputs``; and :class:`baile_nua.manifest.RunManifest`
would compute those four *for the tree as it stands now*, which describes the
exporter's commit and not the commit that produced the package.

That objection is answered here, and not by weakening it.  Every field in the
row carries its **provenance class**, and the classes are not decoration: they
are the difference between a fact the run wrote down and a fact this module
worked out afterwards.

====================================  =======================================
Class                                 What it means
====================================  =======================================
``captured_at_run_time``              the run itself wrote this value down
``derived_from_run_time_filesystem``  not written down, but the filesystem
                                      recorded it as the run happened (an
                                      mtime), which is weaker than a record
                                      and stronger than a guess
``reconstructed_and_verified``         reconstructed from git, AND the files
                                      it is derived from are byte-identical
                                      between the run-time commit and the
                                      freeze tag, so the reconstruction
                                      cannot be wrong about them
``reconstructed_from_git_history``     reconstructed from the nearest commit
                                      at or before the run's start.  NOT
                                      verified: the working tree's state at
                                      run time was never recorded
``computed_at_export_time``            computed now, over bytes on disk now
``assigned_by_exporter``               this module made it up, deterministically
``not_established``                    no honest value exists; the reason is
                                      recorded in its place
====================================  =======================================

**The finding that forced this design.**  The tag is not the runs' code.  The
estate-year ran from about 22:36 to 23:11 on 2026-10-11 and ``e4862f3``
("Fix I-081 (the restore threw away the hot water cylinder)") committed
``engine/run.py`` at 22:54 - eighteen minutes into it.  The 14-day town run
started within seconds of ``7f81f74``, which committed
``activity/engine.py``.  Between either run's nearest commit and
``v1-engine-freeze``, ``engine/e1_run.py`` and ``engine/run.py`` both changed.
So writing the tag's tree hash into ``code_tree_hash`` would state, as a
checksum, something demonstrably false.  What is written instead is the hash
at the nearest commit before the run, suffixed so it cannot be read as
captured, with the differing files named in the row.

**Three fields are visibly reconstructed without opening any JSON.**
``run_id`` begins ``D23-RECONSTRUCTED-``; ``code_git_sha`` ends
``-reconstructed``; ``code_tree_hash`` ends ``-reconstructed-at-<sha7>``.  The
suffix idiom is :func:`baile_nua.manifest.git_sha`'s own - it already returns
``<sha>-dirty``, ``uncommitted-no-head`` and ``git-unavailable`` - so a
decorated identity string is this project's existing convention and not a new
one invented here.  ``design_revision`` is an int and cannot be decorated,
which is exactly why ``parameters.field_provenance`` is the authority and the
suffixes are only the warning.

**What is not in ``outputs``.**  Only the parts the RUN streamed, plus its
diagnostics.  The exported parts under the same roof were written by this
package, not by the run, and their bytes change every time anything is
re-exported; including them would make the field stale on the next export and
would also claim the run produced files it never saw.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

from baile_nua.export.context import ExportError, RunContext
from baile_nua.export.writer import emit

__all__ = [
    "PROVENANCE_CLASSES",
    "MODEL_CODE_PREFIX",
    "FREEZE_TAG",
    "RunCodeState",
    "git_repo_for",
    "reconstruct_code_state",
    "build_d23_row",
    "export_d23",
]

#: Every class a field's provenance may take.  A field whose class is not one
#: of these is a bug, and :func:`build_d23_row` refuses to emit one.
PROVENANCE_CLASSES: tuple[str, ...] = (
    "captured_at_run_time",
    "derived_from_run_time_filesystem",
    "reconstructed_and_verified",
    "reconstructed_from_git_history",
    "computed_at_export_time",
    "assigned_by_exporter",
    "not_established",
)

#: The tree the code digest is taken over.  Same subtree
#: :func:`baile_nua.manifest.code_tree_hash` is pointed at by
#: ``RunManifest.start`` (``Path(manifest.__file__).parent``), named here as a
#: path so it can be checked out of an arbitrary commit.
MODEL_CODE_PREFIX = "scripts/baile_nua"

#: The freeze the runs are compared against, when a run does not say.
FREEZE_TAG = "v1-engine-freeze"

#: Written by `replay_supervisor.run_segment` into the segment directory
#: BEFORE the export post-pass, which is the only reason D23 can read it: the
#: segment's `DONE.json` is not written until after the export has finished.
ENGINE_SIDECAR = "ENGINE.json"


def engine_identity(run_root: Any) -> dict[str, Any]:
    """The engine that produced THIS run, not the constant in this module.

    A twelve-year chained replay does not run on one engine. 2015 ran on
    freeze-2.2; later years run on whatever the supervisor was restarted with,
    and the D18 era gating switches at the 2019 boundary. D23 reporting a
    hardcoded `FREEZE_TAG` for every year would state, of eleven years, a
    version they were not run on.

    Looks for the sidecar beside the package and one level up, because
    `export_all` is called with the package directory while the supervisor
    writes the sidecar at the segment root. Falls back to the module constant
    and SAYS it fell back - an inferred version must not be reported as a
    recorded one.
    """
    import json as _json
    from pathlib import Path as _Path

    root = _Path(run_root)
    for cand in (root / ENGINE_SIDECAR, root.parent / ENGINE_SIDECAR):
        if cand.is_file():
            try:
                d = _json.loads(cand.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            return {
                "engine_tag": d.get("engine_tag"),
                "code_digest": d.get("code_digest"),
                "conf_digest": d.get("conf_digest"),
                "d18_era_gating": d.get("d18_era_gating"),
                "source": f"recorded by the run ({cand.name})",
            }
    return {
        "engine_tag": FREEZE_TAG,
        "code_digest": None,
        "conf_digest": None,
        "d18_era_gating": None,
        "source": "fallback to export.run_manifest.FREEZE_TAG - the run "
                  "recorded no engine sidecar, so this is the module's "
                  "constant and not a statement about this run",
    }

#: Suffixes :func:`baile_nua.manifest.code_tree_hash` hashes.
_SOURCE_SUFFIXES = {".py", ".yaml", ".yml"}

#: Datasets the engine streams.  Their parts, and only their parts, are the
#: run's own outputs.
_STREAMED = ("D11", "D13", "D16", "D18", "D19")


# --------------------------------------------------------------------------- #
# git: the repository that contains the run's outputs
# --------------------------------------------------------------------------- #

def git_repo_for(path: Path) -> Path | None:
    """The git repository containing ``path``, or ``None``.

    Resolved first, so a staged root whose ``v1`` is a symlink into the real
    tree finds the real tree's repository rather than reporting none.  The
    repository is located from the RUN's own path and never from this module's,
    because the question is which repository produced the run.
    """
    here = Path(path).resolve()
    for candidate in (here, *here.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _git(repo: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, timeout=120, check=False,
    )
    if out.returncode != 0:
        raise ExportError(
            f"git {' '.join(args)} failed in {repo}: {out.stderr.strip()}")
    return out.stdout.strip()


class RunCodeState:
    """What can and cannot be established about a run's code, from git.

    Everything on this object is evidence, not a conclusion: the commit it
    found, whether the tag's model code differs from it, and which files
    differ.  :func:`build_d23_row` turns that into provenance classes.
    """

    def __init__(
        self, repo: Path, run_started_at: pd.Timestamp, run_ended_at: pd.Timestamp,
    ) -> None:
        self.repo = repo
        self.run_started_at = run_started_at
        self.run_ended_at = run_ended_at
        self.tag = FREEZE_TAG
        self.tag_sha = _git(repo, "rev-list", "-1", self.tag)
        # The nearest commit at or before the run STARTED, on the tag's own
        # ancestry.  `--before` on the tag rather than on HEAD: HEAD moves with
        # every agent's commit, and the question is which committed state of
        # the frozen line the run could have been built from.
        before = _git(
            repo, "rev-list", "-1",
            f"--before={run_started_at.isoformat()}", self.tag,
        )
        self.commit_before_run = before or ""
        self.commits_during_run = [
            line for line in _git(
                repo, "rev-list",
                f"--since={run_started_at.isoformat()}",
                f"--until={run_ended_at.isoformat()}",
                self.tag,
            ).splitlines() if line
        ]
        self.model_files_changed_during_run = (
            self._model_files_between(self.commit_before_run, self.commits_during_run[0])
            if self.commits_during_run and self.commit_before_run else []
        )
        self.model_files_changed_since = (
            self._model_files_between(self.commit_before_run, self.tag_sha)
            if self.commit_before_run else []
        )

    def _model_files_between(self, a: str, b: str) -> list[str]:
        """Model-code files differing between two commits.

        ``scripts/tests`` is excluded: a test is not the model, and including
        it would make every window look like a model change.
        """
        if not a or not b or a == b:
            return []
        names = _git(self.repo, "diff", "--name-only", a, b, "--", MODEL_CODE_PREFIX)
        return sorted(
            n for n in names.splitlines()
            if n and not n.startswith("scripts/tests")
            and Path(n).suffix in _SOURCE_SUFFIXES
        )

    def files_identical_between(self, relpath: str, a: str, b: str) -> bool:
        """Is one path byte-identical at two commits?

        The basis for ``reconstructed_and_verified``: a value derived only from
        files that did not change over the window cannot be wrong about them,
        however dirty the working tree was.
        """
        if not a or not b:
            return False
        names = _git(self.repo, "diff", "--name-only", a, b, "--", relpath)
        return not [n for n in names.splitlines() if n]

    def tree_hash_at(self, commit: str) -> str:
        """``manifest.code_tree_hash``, computed over a checkout of ``commit``.

        The same construction, over the same subtree and the same suffixes, so
        the value is comparable with one a future run captures for itself.
        """
        from baile_nua.manifest import code_tree_hash

        if not commit:
            raise ExportError("tree_hash_at was given no commit")
        with tempfile.TemporaryDirectory(prefix="agent_f_tree_") as tmp:
            archive = subprocess.run(
                ["git", "-C", str(self.repo), "archive", commit, MODEL_CODE_PREFIX],
                capture_output=True, timeout=300, check=False,
            )
            if archive.returncode != 0:
                raise ExportError(
                    f"git archive {commit} failed: "
                    f"{archive.stderr.decode('utf-8', 'replace').strip()}")
            tar = subprocess.run(
                ["tar", "-x", "-C", tmp], input=archive.stdout,
                capture_output=True, timeout=300, check=False,
            )
            if tar.returncode != 0:
                raise ExportError(
                    f"extracting {commit} failed: "
                    f"{tar.stderr.decode('utf-8', 'replace').strip()}")
            return code_tree_hash(Path(tmp) / MODEL_CODE_PREFIX)

    def as_evidence(self) -> dict[str, Any]:
        return {
            "repo": str(self.repo),
            "freeze_tag": self.tag,
            "freeze_tag_sha": self.tag_sha,
            "run_started_at_utc": self.run_started_at.isoformat(),
            "run_ended_at_utc": self.run_ended_at.isoformat(),
            "nearest_commit_at_or_before_run_start": self.commit_before_run,
            "commits_made_while_the_run_was_in_flight": self.commits_during_run,
            "model_code_files_committed_while_the_run_was_in_flight":
                self.model_files_changed_during_run,
            "model_code_files_changed_between_that_commit_and_the_tag":
                self.model_files_changed_since,
            "why_the_tag_is_not_the_runs_code": (
                "the files listed under "
                "model_code_files_changed_between_that_commit_and_the_tag "
                "differ, so the tag's tree hash would be a false checksum for "
                "this run"
            ),
            "what_is_still_unknown": (
                "whether the working tree was clean at run time. No run-time "
                "record exists, so even the nearest commit is an upper bound "
                "on what is established, not a statement that the run used it."
            ),
        }


def reconstruct_code_state(ctx: RunContext) -> RunCodeState | None:
    """The code state for ``ctx``'s run, or ``None`` if there is no repository."""
    repo = git_repo_for(ctx.run_root)
    if repo is None:
        return None
    ended, started = _run_window(ctx)
    return RunCodeState(repo, started, ended)


# --------------------------------------------------------------------------- #
# when the run happened
# --------------------------------------------------------------------------- #

def _run_window(ctx: RunContext) -> tuple[pd.Timestamp, pd.Timestamp]:
    """``(ended_at, started_at)``, from the filesystem and the run's own clock.

    ``run_diagnostics.json`` is the last thing a run writes, so its mtime is
    when the run finished; the run's own ``benchmark.timings.total_s`` is how
    long it took.  Neither is a recorded timestamp, which is why both are
    classed ``derived_from_run_time_filesystem`` and not ``captured``.
    """
    diag_path = Path(ctx.run_root) / "run_diagnostics.json"
    ended = pd.Timestamp(diag_path.stat().st_mtime, unit="s", tz="UTC")
    total_s = (
        ((ctx.diagnostics.get("benchmark") or {}).get("timings") or {})
        .get("total_s")
    )
    if total_s is None:
        return ended, ended
    return ended, ended - pd.Timedelta(seconds=float(total_s))


# --------------------------------------------------------------------------- #
# the row
# --------------------------------------------------------------------------- #

def _declared_input_sources() -> dict[str, Any]:
    """The declared corpus, from each source's own per-file manifest.

    The sha256 in a source manifest was written when the file was RETRIEVED,
    which is before any run read it, so it is a record made no later than run
    time - unlike a hash computed now.  What is NOT established is which of
    them this run read: nothing recorded that, and the registry is a
    declaration of the corpus rather than a log of reads.
    """
    import baile_nua.sources_registry  # noqa: F401  (declares the sources)
    from baile_nua.sources import REGISTRY, manifest_for

    out: dict[str, Any] = {}
    for key in sorted(REGISTRY):
        src = REGISTRY[key]
        try:
            man = manifest_for(src)
        except Exception:                      # absent file: recorded as such
            man = None
        out[key] = {
            "relpath": src.relpath,
            "url": src.url,
            "licence": src.licence,
            "intended_use": src.intended_use,
            "model_development_exposure": src.model_development_exposure,
            "sha256": (man or {}).get("sha256"),
            "retrieved_at_utc": (man or {}).get("retrieved_at_utc"),
            "sha256_recorded_when": (
                "at retrieval, by the source's own manifest"
                if man else "NOT ON DISK: no manifest for this declared source"
            ),
        }
    return {
        "_provenance": (
            "the DECLARED corpus with each file's retrieval-time SHA-256. "
            "Which of these the run actually read was NOT recorded by the run, "
            "so this is the set it could have read and not the set it did."
        ),
        "n_declared": len(out),
        "sources": out,
    }


def _run_outputs(ctx: RunContext, exclude_dataset: str) -> dict[str, Any]:
    """``path -> sha256`` for the parts the RUN streamed, plus its diagnostics."""
    from baile_nua.hashing import hash_file

    root = Path(ctx.run_root)
    files: list[Path] = []
    for pkg in ("ground_truth", "observable", "evidence"):
        for dataset_id in _STREAMED:
            if dataset_id == exclude_dataset:
                continue
            files += sorted((root / pkg).glob(f"{dataset_id}_part*.parquet"))
    diag = root / "run_diagnostics.json"
    if diag.is_file():
        files.append(diag)
    digests = {
        str(p.relative_to(root)): hash_file(p) for p in files
    }
    return {
        "_provenance": (
            "SHA-256 computed at export time over the parts the ENGINE "
            "streamed (D11, D13, D16, D18, D19) and the run's diagnostics. "
            "The run recorded no digest of its own outputs, so these hashes "
            "say what the bytes are now, not what the run wrote."
        ),
        "_excluded": (
            "parts written by baile_nua.export rather than by the run - they "
            "are not the run's outputs and their bytes change on every "
            f"re-export - and {exclude_dataset} itself, which cannot hash a "
            "file it is in the middle of writing"
        ),
        "n_files": len(digests),
        "total_bytes": int(sum(p.stat().st_size for p in files)),
        "files": digests,
    }


def build_d23_row(ctx: RunContext) -> tuple[dict[str, Any], dict[str, Any]]:
    """``(row, field_provenance)`` for one run.

    Separated from :func:`export_d23` so a test can inspect the provenance
    map without writing a Parquet part.
    """
    from baile_nua.manifest import RunManifest
    from baile_nua.schema import load

    diag = ctx.diagnostics
    schema = load()
    ended, started = _run_window(ctx)
    state = reconstruct_code_state(ctx)
    prov: dict[str, dict[str, Any]] = {}

    def record(field: str, cls: str, evidence: str, **extra: Any) -> None:
        if cls not in PROVENANCE_CLASSES:
            raise ExportError(
                f"D23.{field}: provenance class {cls!r} is not one of "
                f"{PROVENANCE_CLASSES}. A field with an undeclared provenance "
                f"class is exactly the ambiguity this module exists to remove."
            )
        prov[field] = {"provenance": cls, "evidence": evidence, **extra}

    # -- captured ----------------------------------------------------------- #
    label = str(diag["label"])
    record("label", "captured_at_run_time",
           "run_diagnostics.json['label'], written by the run")
    record("master_seed", "captured_at_run_time",
           "run_diagnostics.json['master_seed']")
    record("coupling_mode", "captured_at_run_time",
           "run_diagnostics.json['coupling_mode']")
    record("scope", "captured_at_run_time",
           "run_diagnostics.json['slice'] and ['benchmark'], plus the n_days "
           "the context reads off the run's own timestamped parts")
    chain_head = diag.get("checkpoint_chain_head")
    if chain_head:
        record("checkpoint_chain_head", "captured_at_run_time",
               "run_diagnostics.json['checkpoint_chain_head']")
    else:
        record("checkpoint_chain_head", "not_established",
               "the run recorded no checkpoint chain head")

    # -- filesystem --------------------------------------------------------- #
    record("created_at_utc", "derived_from_run_time_filesystem",
           "the mtime of run_diagnostics.json, which is the last file a run "
           "writes, so it is when the run FINISHED. The run recorded no "
           "creation timestamp of its own.",
           run_started_at_utc=started.isoformat(),
           derived_from="st_mtime of run_diagnostics.json")

    # -- environment: captured in part -------------------------------------- #
    machine = ((diag.get("benchmark") or {}).get("machine") or {})
    environment = {
        "_provenance": (
            "the subset the run's own benchmark recorded. The schema asks for "
            "'python, numpy, platform, core count'; python, platform and core "
            "count were captured and the library versions were not."
        ),
        "captured": {
            k: machine[k] for k in
            ("python", "platform", "machine", "cpu_brand", "cpu_count",
             "memory_gb")
            if k in machine
        },
        "not_captured": ["numpy", "pandas", "pyarrow", "duckdb", "numba"],
        "not_captured_note": (
            "RunManifest.start records all five; neither run built a "
            "RunManifest, so they are gone. They are NOT filled in from this "
            "process: this process is not the run's process."
        ),
    }
    record("environment", "captured_at_run_time",
           "benchmark.machine, captured by the run. The five library versions "
           "the schema also wants are listed under not_captured rather than "
           "filled in from the exporting process.")

    # -- reconstructed from git --------------------------------------------- #
    if state is None:
        git_sha_value = "no-git-repository-not-established"
        tree_hash_value = "no-git-repository-not-established"
        record("code_git_sha", "not_established",
               f"no git repository found at or above {ctx.run_root}")
        record("code_tree_hash", "not_established",
               f"no git repository found at or above {ctx.run_root}")
        code_state_evidence: dict[str, Any] = {"available": False}
    else:
        code_state_evidence = state.as_evidence()
        short = (state.commit_before_run or "unknown")[:7]
        git_sha_value = f"{state.commit_before_run}-reconstructed"
        tree_hash_value = (
            f"{state.tree_hash_at(state.commit_before_run)}"
            f"-reconstructed-at-{short}"
        )
        record(
            "code_git_sha", "reconstructed_from_git_history",
            "the nearest commit at or before the run's start on the "
            f"{FREEZE_TAG} ancestry. NOT captured: the run wrote no SHA. The "
            "value carries a '-reconstructed' suffix so it cannot be read as "
            "captured, in the idiom of manifest.git_sha's '-dirty'.",
            nearest_commit=state.commit_before_run,
            commits_in_flight_during_the_run=state.commits_during_run,
            model_code_committed_while_the_run_was_in_flight=(
                state.model_files_changed_during_run),
            working_tree_cleanliness_at_run_time="NOT RECORDED, so unknown",
        )
        record(
            "code_tree_hash", "reconstructed_from_git_history",
            "manifest.code_tree_hash's own construction over a checkout of "
            "the nearest commit before the run. The FREEZE TAG's hash is NOT "
            "used: the named model-code files differ between that commit and "
            "the tag, so the tag's hash would be a false checksum for this "
            "run.",
            computed_over=MODEL_CODE_PREFIX,
            model_code_files_changed_between_that_commit_and_the_tag=(
                state.model_files_changed_since),
            tree_hash_at_the_freeze_tag=state.tree_hash_at(state.tag_sha),
        )

    # -- version labels: reconstructed, and verifiable ---------------------- #
    code_version = RunManifest.__dataclass_fields__["code_version"].default
    record(
        "code_version", "reconstructed_from_git_history",
        "RunManifest.code_version's default as the freeze tag declares it. "
        "The run recorded no version string. Suffixed '-reconstructed'.",
    )
    schema_rel = f"{MODEL_CODE_PREFIX}/schema/datasets.yaml"
    schema_unchanged = (
        state is not None
        and state.files_identical_between(
            schema_rel, state.commit_before_run, state.tag_sha)
    )
    for field in ("schema_version", "design_revision"):
        if schema_unchanged:
            record(
                field, "reconstructed_and_verified",
                f"read from {schema_rel} at the freeze tag, AND that file is "
                f"byte-identical between the nearest commit before the run "
                f"and the tag, so the reconstruction cannot be wrong about it. "
                f"Still not CAPTURED: the run did not write it down.",
                verified_identical_between=[
                    state.commit_before_run, state.tag_sha],
            )
        else:
            record(
                field, "reconstructed_from_git_history",
                f"read from {schema_rel} at the freeze tag; that file is NOT "
                f"identical between the run-time commit and the tag, so this "
                f"may not be the schema the run validated against.",
            )

    # -- computed now, and said so ------------------------------------------ #
    outputs = _run_outputs(ctx, exclude_dataset="D23")
    record("outputs", "computed_at_export_time",
           "SHA-256 of the parts the engine streamed, hashed now. The run "
           "recorded no digest of its outputs, so this describes the bytes on "
           "disk at export time.")
    input_sources = _declared_input_sources()
    record("input_sources", "reconstructed_from_git_history",
           "the declared source corpus with each file's RETRIEVAL-time "
           "SHA-256 from its own manifest - a record made before the run. "
           "Which of them the run read was never recorded.")

    # -- assigned ----------------------------------------------------------- #
    run_id = (
        f"D23-RECONSTRUCTED-{ctx.run_name}-seed{ctx.master_seed}"
        f"-{str(chain_head or 'nochain')[:12]}"
    )
    record("run_id", "assigned_by_exporter",
           "deterministic from the run name, the captured master seed and the "
           "captured checkpoint chain head. The run minted no id, so one is "
           "assigned; it begins D23-RECONSTRUCTED- so no reader can mistake "
           "this row for a manifest the run wrote.")

    record("parameters", "assigned_by_exporter",
           "this module's own record: the per-field provenance map, the "
           "provenance summary, the git evidence, and the run parameters that "
           "WERE captured. Nothing in it is a run parameter reconstructed "
           "from a default.")

    classes = sorted({v["provenance"] for v in prov.values()})
    summary = {
        "classes_used": classes,
        "by_class": {
            c: sorted(f for f, v in prov.items() if v["provenance"] == c)
            for c in classes
        },
        "n_captured_at_run_time": sum(
            1 for v in prov.values()
            if v["provenance"] == "captured_at_run_time"),
        "n_fields": len(prov),
        "the_point": (
            "D23 declares sixteen fields and these runs recorded a handful of "
            "them. Which handful is the finding, and it is in this column "
            "rather than only in a commit message."
        ),
    }
    parameters = {
        "field_provenance": prov,
        "provenance_summary": summary,
        "code_state_evidence": code_state_evidence,
        "captured_run_parameters": {
            "slice_kind": ctx.slice_kind,
            "estate_selection": (diag.get("slice") or {}).get("estate_selection"),
            "e1_scope_enforced": (diag.get("slice") or {}).get("e1_scope_enforced"),
            "claim": diag.get("claim"),
            "network_claim": diag.get("network_claim"),
            "datasets_streamed": sorted(
                ((diag.get("benchmark") or {}).get("storage") or {})
                .get("by_dataset", {})),
        },
        "not_captured_run_parameters": (
            "the runner's own knobs - collect_presence_days, omit_datasets, "
            "checkpoint root, worker count - were passed on a command line "
            "that nothing recorded. They are named here as absent rather than "
            "reconstructed from a default that may not have been used."
        ),
    }

    scope = {
        **(diag.get("slice") or {}),
        "n_days": ctx.n_days,
        "n_days_evidence": ctx.t0_evidence,
        "t0_utc": ctx.t0.isoformat(),
        "coupling_mode": ctx.coupling_mode,
        "run_root": str(ctx.run_root),
    }

    row = {
        "run_id": run_id,
        "created_at_utc": ended,
        "label": label,
        "code_version": f"{code_version}-reconstructed",
        "code_git_sha": git_sha_value,
        "code_tree_hash": tree_hash_value,
        "schema_version": schema.schema_version,
        "design_revision": int(schema.design_revision),
        "master_seed": int(ctx.master_seed),
        "coupling_mode": ctx.coupling_mode,
        "scope": json.dumps(scope, sort_keys=True, default=str),
        "input_sources": json.dumps(input_sources, sort_keys=True, default=str),
        "parameters": json.dumps(parameters, sort_keys=True, default=str),
        "outputs": json.dumps(outputs, sort_keys=True, default=str),
        "checkpoint_chain_head": chain_head,
        "environment": json.dumps(environment, sort_keys=True, default=str),
    }
    declared = set(load()["D23"].field_map)
    missing = sorted(declared - set(row))
    unclassed = sorted(declared - set(prov))
    if missing or unclassed:
        raise ExportError(
            f"D23: declared field(s) {missing} have no value and {unclassed} "
            f"have no provenance class. Every declared field must be "
            f"populated AND classed, or omitted with a recorded reason; "
            f"silence is the one thing this module may not do."
        )
    return row, prov


def export_d23(ctx: RunContext) -> dict[str, Any]:
    """One row: this run's manifest, every field carrying its provenance."""
    row, prov = build_d23_row(ctx)
    # Resolved per run, so each year of the chained replay reports the engine
    # it was actually run on rather than this module's constant.
    _engine = engine_identity(ctx.run_root)
    frame = pd.DataFrame([row])
    classes = {f: v["provenance"] for f, v in prov.items()}
    return emit(
        frame, "D23", ctx,
        source=(
            "run_diagnostics.json, the run's own filesystem timestamps, and "
            "git history at and before the run; per-field provenance in "
            "parameters.field_provenance"
        ),
        conversions=[
            {"field": f, "provenance": c} for f, c in sorted(classes.items())
        ],
        limitations=[
            "Not a manifest the run wrote: the runs on disk built no "
            "RunManifest, so only the fields classed captured_at_run_time are "
            "the run's own record.",
            "code_git_sha and code_tree_hash are reconstructed from the "
            "nearest commit before the run and carry a '-reconstructed' "
            "suffix. The working tree's cleanliness at run time was never "
            "recorded, so even that commit is an upper bound on what is "
            "established.",
            "The freeze tag is NOT the runs' code: model-code files changed "
            "between each run's nearest commit and the tag, which is why the "
            "tag's tree hash is reported alongside rather than used.",
            "input_sources is the declared corpus, not a log of reads: which "
            "sources the run touched was never recorded.",
            "outputs covers the engine-streamed parts only, hashed at export "
            "time.",
        ],
        extra={
            "d23_provenance_classes": classes,
            "d23_n_captured_at_run_time": sum(
                1 for c in classes.values() if c == "captured_at_run_time"),
            "d23_freeze_tag": _engine["engine_tag"],
            "d23_engine_code_digest": _engine["code_digest"],
            "d23_engine_conf_digest": _engine["conf_digest"],
            "d23_d18_era_gating": _engine["d18_era_gating"],
            "d23_engine_version_source": _engine["source"],
        },
    )
