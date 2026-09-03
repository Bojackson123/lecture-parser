"""Real ingest output shared by the ``tests/align`` modules.

Alignment tests consume the committed fixtures through the real entrypoints
(``ingest_captions``, ``ingest_slides``), not hand-built stand-ins (P4-01 decision):
what Phase 4 aligns is whatever Phases 1 and 2 actually produce.
"""

from pathlib import Path

import pytest

from lecturenotes.ingest.captions import Segment, ingest_captions
from lecturenotes.ingest.slides import Deck, ingest_slides


@pytest.fixture(scope="session")
def segments(fixtures_dir: Path) -> list[Segment]:
    """The 22 segments of ``captions/lecture01.vtt`` (1-based in the fixtures README)."""
    return ingest_captions(fixtures_dir / "captions" / "lecture01.vtt")


@pytest.fixture(scope="session")
def deck(fixtures_dir: Path) -> Deck:
    """The 3-slide ``decks/lecture01.pptx`` deck."""
    return ingest_slides(fixtures_dir / "decks" / "lecture01.pptx")
