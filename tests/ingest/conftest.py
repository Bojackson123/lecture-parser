"""Caption and deck fixture data shared by the ``tests/ingest`` modules."""

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def vtt_text(fixtures_dir: Path) -> str:
    return (fixtures_dir / "captions" / "lecture01.vtt").read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def srt_text(fixtures_dir: Path) -> str:
    return (fixtures_dir / "captions" / "lecture01.srt").read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def decks_dir(fixtures_dir: Path) -> Path:
    return fixtures_dir / "decks"


@pytest.fixture(scope="session")
def expected_deck_json(decks_dir: Path) -> str:
    """The hand-written expected ``Deck`` for the PPTX (``lecture01.deck.json``)."""
    return (decks_dir / "lecture01.deck.json").read_text(encoding="utf-8")
