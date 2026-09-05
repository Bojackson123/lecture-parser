"""Shared pytest fixtures: repo paths and the canonical ``NoteWeek``."""

import importlib.util
from pathlib import Path

import pytest

from lecturenotes.model import NoteWeek
from tests.fixtures.notes.week01 import week01 as build_week01

REPO_ROOT = Path(__file__).resolve().parent.parent

# The web GUI's stack is its own dependency group (PW-01): in an environment
# synced without it, the rest of the suite must still collect and pass, so the
# web tests are skipped wholesale.
if importlib.util.find_spec("fastapi") is None:
    collect_ignore = ["web"]


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def fixtures_dir(repo_root: Path) -> Path:
    return repo_root / "tests" / "fixtures"


@pytest.fixture
def week01() -> NoteWeek:
    """A fresh copy of the hand-written week-1 notes (``tests/fixtures/notes/week01.py``)."""
    return build_week01()
