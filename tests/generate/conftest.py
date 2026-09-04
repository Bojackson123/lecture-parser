"""Real pipeline output shared by the ``tests/generate`` modules.

Generation tests consume the committed fixtures through the real entrypoints
(``ingest_captions``, ``ingest_slides``, ``align_lecture``), not hand-built stand-ins
(the P4-01 rule): what Phase 5 prompts over is whatever the earlier stages actually
produce. The deck is the PPTX — the recorded-response fixture is PPTX-bound (its
``s3-3`` response embeds the PPTX image id; P5-02 decision) — and the PDF deck exists
only for the cross-format prompt assertions.
"""

from pathlib import Path

import pytest

from lecturenotes.align import Chunk, align_lecture
from lecturenotes.ingest.captions import Segment, ingest_captions
from lecturenotes.ingest.slides import Deck, ingest_slides


@pytest.fixture(scope="session")
def segments(fixtures_dir: Path) -> list[Segment]:
    """The 22 segments of ``captions/lecture01.vtt``."""
    return ingest_captions(fixtures_dir / "captions" / "lecture01.vtt")


@pytest.fixture(scope="session")
def deck(fixtures_dir: Path) -> Deck:
    """The 3-slide ``decks/lecture01.pptx`` deck (speaker notes, PPTX image id)."""
    return ingest_slides(fixtures_dir / "decks" / "lecture01.pptx")


@pytest.fixture(scope="session")
def pdf_deck(fixtures_dir: Path) -> Deck:
    """The same deck via PDF: ``notes=None`` everywhere, re-encoded image id (P2-03)."""
    return ingest_slides(fixtures_dir / "decks" / "lecture01.pdf")


@pytest.fixture(scope="session")
def chunks(deck: Deck, segments: list[Segment]) -> list[Chunk]:
    """The four aligned chunks: slide 1, the board-work gap, slide 2, slide 3."""
    return align_lecture(deck, segments)


@pytest.fixture(scope="session")
def responses_path(fixtures_dir: Path) -> Path:
    """The hand-written recorded-response fixture (P5-02)."""
    return fixtures_dir / "generate" / "lecture01.responses.json"
