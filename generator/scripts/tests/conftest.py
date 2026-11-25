"""Shared fixtures.

The package is imported from the source tree rather than installed, so the
suite runs before `pip install -e .` has happened.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture(scope="session")
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def schema():
    from baile_nua.schema import load

    return load()


@pytest.fixture(scope="session")
def master_seed() -> int:
    return 20261008


@pytest.fixture
def seed_tree(master_seed):
    from baile_nua.rng import SeedTree

    return SeedTree(master_seed)
