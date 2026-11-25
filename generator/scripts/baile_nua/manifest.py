"""Run manifests (D23) — design 3.3 and 8.5.

    Each run is defined by a manifest naming code version, input data versions,
    parameter set and master seed, so any subsystem can be re-run for any home
    and period and give identical output.

Two things here that a naive manifest omits and that matter in practice:

* a **source tree hash** as well as the git SHA, so an uncommitted edit during a
  run cannot masquerade as the committed code;
* the **SHA-256 of every input file under ``sources/``** that was actually read,
  so a report can be traced to the bytes it was computed from.  The brief's rule
  "every calibration number traces to a file in sources/" is only enforceable if
  the manifest records which bytes those were.
"""

from __future__ import annotations

import dataclasses
import json
import os
import platform
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from baile_nua.hashing import hash_file, hash_json

__all__ = ["RunManifest", "LABEL", "code_tree_hash", "git_sha", "new_run_id"]

#: The label the brief requires on every output and report.
LABEL = "UNVALIDATED SIMULATION EVIDENCE: E1 engineering candidate"

_SOURCE_SUFFIXES = {".py", ".yaml", ".yml"}


def new_run_id(prefix: str = "E1") -> str:
    return f"{prefix}-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{uuid.uuid4().hex[:8]}"


def git_sha(repo: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=15, check=False,
        )
        sha = out.stdout.strip()
        if not sha:
            return "uncommitted-no-head"
        dirty = subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain"],
            capture_output=True, text=True, timeout=30, check=False,
        ).stdout.strip()
        return f"{sha}{'-dirty' if dirty else ''}"
    except (OSError, subprocess.SubprocessError):
        return "git-unavailable"


def code_tree_hash(package_root: Path) -> str:
    """Hash every ``.py`` / ``.yaml`` under the package, in sorted path order.

    Makes a run's code state self-describing even when the working tree is
    dirty, which during a week-long build it almost always is.
    """
    files = sorted(
        p for p in package_root.rglob("*")
        if p.is_file() and p.suffix in _SOURCE_SUFFIXES and "__pycache__" not in p.parts
    )
    return hash_json(
        {str(p.relative_to(package_root)): hash_file(p) for p in files}
    )


@dataclasses.dataclass
class RunManifest:
    """D23. Built at the start of a run, finalised when its outputs are written."""

    run_id: str
    master_seed: int
    coupling_mode: str
    scope: dict[str, Any]
    parameters: dict[str, Any] = dataclasses.field(default_factory=dict)
    code_version: str = "0.1.0a1+e1"
    label: str = LABEL
    design_revision: int = 3
    schema_version: str = "1.0.0"
    created_at_utc: str = dataclasses.field(
        default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    )
    code_git_sha: str = ""
    code_tree_hash: str = ""
    input_sources: dict[str, dict[str, Any]] = dataclasses.field(default_factory=dict)
    outputs: dict[str, str] = dataclasses.field(default_factory=dict)
    checkpoint_chain_head: str | None = None
    environment: dict[str, Any] = dataclasses.field(default_factory=dict)
    notes: list[str] = dataclasses.field(default_factory=list)

    # -- construction --------------------------------------------------------

    @classmethod
    def start(
        cls,
        *,
        master_seed: int,
        coupling_mode: str,
        scope: dict[str, Any],
        project_root: Path,
        parameters: dict[str, Any] | None = None,
        run_id: str | None = None,
    ) -> RunManifest:
        pkg = Path(__file__).parent
        m = cls(
            run_id=run_id or new_run_id(),
            master_seed=master_seed,
            coupling_mode=coupling_mode,
            scope=dict(scope),
            parameters=dict(parameters or {}),
        )
        m.code_git_sha = git_sha(project_root)
        m.code_tree_hash = code_tree_hash(pkg)
        m.environment = {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "logical_cores": os.cpu_count(),
            "numpy": __import__("numpy").__version__,
            "pandas": __import__("pandas").__version__,
            "pyarrow": __import__("pyarrow").__version__,
            "duckdb": __import__("duckdb").__version__,
        }
        try:
            m.environment["numba"] = __import__("numba").__version__
        except ImportError:  # pragma: no cover
            m.environment["numba"] = "not installed"
        return m

    # -- recording -----------------------------------------------------------

    def record_source(
        self, path: str | Path, *, url: str, licence: str, intended_use: str,
        retrieved_at: str, model_development_exposure: str = "none",
    ) -> str:
        """Record an input file under ``sources/`` with its SHA-256."""
        p = Path(path)
        sha = hash_file(p)
        self.input_sources[str(p)] = {
            "sha256": sha,
            "bytes": p.stat().st_size,
            "url": url,
            "licence": licence,
            "intended_use": intended_use,
            "retrieved_at": retrieved_at,
            "model_development_exposure": model_development_exposure,
        }
        return sha

    def record_output(self, path: str | Path) -> str:
        p = Path(path)
        sha = hash_file(p)
        self.outputs[str(p)] = sha
        return sha

    def note(self, text: str) -> None:
        self.notes.append(text)

    # -- persistence ---------------------------------------------------------

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    def manifest_hash(self) -> str:
        """Hash of everything except the hash field itself."""
        return hash_json(self.as_dict())

    def write(self, path: str | Path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        doc = self.as_dict()
        doc["manifest_hash"] = self.manifest_hash()
        p.write_text(json.dumps(doc, indent=2, sort_keys=True, default=str), encoding="utf-8")
        return p

    @classmethod
    def read(cls, path: str | Path) -> RunManifest:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        doc.pop("manifest_hash", None)
        return cls(**doc)
