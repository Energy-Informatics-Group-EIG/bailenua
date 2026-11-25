"""Configuration, loaded from YAML rather than written into call sites.

``e1_scope.yaml``   the E1 slice (E0-7).  The runner refuses to exceed it.
``thresholds.yaml`` acceptance thresholds, all provisional (E0-4 / U11).
"""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Any

import yaml

__all__ = [
    "e1_scope",
    "week2_slice",
    "thresholds",
    "CONFIG_DIR",
    "ScopeError",
]

CONFIG_DIR = Path(__file__).parent


class ScopeError(ValueError):
    """A run asked for more than the E1 scope allows (K11: scope creep)."""


@functools.lru_cache(maxsize=1)
def e1_scope() -> dict[str, Any]:
    return yaml.safe_load((CONFIG_DIR / "e1_scope.yaml").read_text(encoding="utf-8"))


@functools.lru_cache(maxsize=1)
def thresholds() -> dict[str, Any]:
    return yaml.safe_load((CONFIG_DIR / "thresholds.yaml").read_text(encoding="utf-8"))


def week2_slice() -> dict[str, Any]:
    """The week 2 mixed-age slice (U23, resized by U29)."""
    return e1_scope()["week2_slice"]


def assert_within_e1_scope(
    *, n_homes: int, coupling_mode: str, year: int, scope_name: str = "slice",
) -> None:
    """Refuse a run that exceeds the approved slice.

    ``scope_name`` selects which approved slice applies: ``"slice"`` is E0-7's
    E1 estate, ``"week2_slice"`` is U23 as resized by U29, and
    ``"heldout_slice"`` is U31's evaluation sample. Named scopes rather than
    one editable number, so growing one slice cannot silently raise the
    ceiling on another whose artefacts were produced under a different one.
    """
    cfg = e1_scope()
    if scope_name not in cfg:
        raise ScopeError(
            f"unknown scope {scope_name!r}; declared scopes are "
            f"{sorted(k for k in cfg if isinstance(cfg[k], dict))}"
        )
    sl = cfg[scope_name]
    if n_homes > sl["n_homes"]:
        raise ScopeError(
            f"{n_homes} homes exceeds the approved {scope_name} of "
            f"{sl['n_homes']}. Scale-up is gated by a decision, not decided "
            f"at a call site."
        )
    if coupling_mode != sl["coupling_mode"]:
        raise ScopeError(
            f"coupling mode {coupling_mode} is not the E1 mode {sl['coupling_mode']}; "
            f"C2 and C3 are weeks 2 and 3 (design 9.3, revision-3 effect table)."
        )
    if year != sl["calendar_year"]:
        raise ScopeError(
            f"year {year} is not the E1 year {sl['calendar_year']} (E0-3 / U08)."
        )
