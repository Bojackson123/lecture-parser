"""P4-03: gap carving and ``align_lecture`` on the committed fixtures.

The expected output is the hand-written ``tests/fixtures/align/lecture01.chunks.json``
— the slide → time map transcribed, whose spans are, by design, the ``week01`` notes
fixture's lecture-1 topic anchors. Segment numbers in test names are 1-based, matching
the map; slices below are 0-based.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from lecturenotes.align.boundaries import Chunk, align_lecture
from lecturenotes.ingest.captions import Segment, ingest_captions
from lecturenotes.ingest.slides import Deck, Slide, TextBlock, ingest_slides
from lecturenotes.model import NoteWeek
from lecturenotes.model.source import SlideRange


@pytest.fixture(scope="session")
def expected_chunks(fixtures_dir: Path) -> list[Chunk]:
    """The hand-written fixture, validated through ``Chunk`` (never regenerated)."""
    path = fixtures_dir / "align" / "lecture01.chunks.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [Chunk.model_validate(item) for item in raw]


@pytest.fixture(scope="session")
def chunks(deck: Deck, segments: list[Segment]) -> list[Chunk]:
    """The headline run: PPTX deck + VTT segments, default knobs."""
    return align_lecture(deck, segments)


def _slide_only(number: int, lines: tuple[str, ...], *, hidden: bool = False) -> Slide:
    return Slide(
        number=number,
        title=None,
        blocks=(TextBlock(lines=lines),),
        notes=None,
        image_ids=(),
        hidden=hidden,
    )


# --- the fixture, chunk for chunk ----------------------------------------------


def test_align_lecture_equals_the_hand_written_fixture(
    chunks: list[Chunk], expected_chunks: list[Chunk]
) -> None:
    assert chunks == expected_chunks


def test_pdf_and_srt_yield_the_same_chunks(fixtures_dir: Path, chunks: list[Chunk]) -> None:
    """Cross-format: speaker notes (PPTX-only) never score and image bytes (different
    ids per format, P2-03) never influence alignment, so the chunks are identical."""
    pdf = ingest_slides(fixtures_dir / "decks" / "lecture01.pdf")
    srt = ingest_captions(fixtures_dir / "captions" / "lecture01.srt")
    assert align_lecture(pdf, srt) == chunks


def test_slide_1_maps_to_segments_1_to_4(chunks: list[Chunk], segments: list[Segment]) -> None:
    assert chunks[0].slides == SlideRange(start=1, end=1)
    assert chunks[0].segments == tuple(segments[0:4])


def test_board_work_is_flagged_as_a_gap(chunks: list[Chunk], segments: list[Segment]) -> None:
    """The dice/reroll detour is the §4.1 gap signal: ``slides is None``."""
    assert chunks[1].slides is None
    assert chunks[1].segments == tuple(segments[4:12])
    assert (chunks[1].start_s, chunks[1].end_s) == (151.0, 268.0)


def test_slide_2_maps_to_segments_13_to_18(chunks: list[Chunk], segments: list[Segment]) -> None:
    assert chunks[2].slides == SlideRange(start=2, end=2)
    assert chunks[2].segments == tuple(segments[12:18])


def test_slide_3_maps_to_segments_19_to_22(chunks: list[Chunk], segments: list[Segment]) -> None:
    assert chunks[3].slides == SlideRange(start=3, end=3)
    assert chunks[3].segments == tuple(segments[18:22])


def test_chunk_spans_equal_the_week01_topic_anchors(
    chunks: list[Chunk], week01: NoteWeek
) -> None:
    """The input and output fixtures tell one story: the four chunk spans are exactly
    the ``week01`` notes fixture's lecture-1 topic anchors."""
    spans = [(chunk.start_s, chunk.end_s) for chunk in chunks]
    assert spans == [(1.0, 149.0), (151.0, 268.0), (271.0, 419.0), (421.0, 545.0)]
    anchors = [(t.anchor.start_s, t.anchor.end_s) for t in week01.lectures[0].topics]
    assert spans == anchors


# --- what is *not* a gap --------------------------------------------------------


def test_segment_4_is_not_board_work(chunks: list[Chunk], segments: list[Segment]) -> None:
    """Segment 4 shares no vocabulary with slide 1, but the lecturer was mid-flow —
    no leading silence, so the carve peels it off the run and it stays in chunk 1."""
    assert segments[3] in chunks[0].segments


def test_the_closing_recap_is_not_a_gap(chunks: list[Chunk], segments: list[Segment]) -> None:
    """Segment 22 (25 s, no leading silence) fails both gates and sits in chunk 4."""
    assert segments[21] in chunks[3].segments
    assert chunks[3].slides == SlideRange(start=3, end=3)


# --- the knobs, on the fixture ---------------------------------------------------


def test_infinite_min_gap_folds_the_detour_into_chunk_1(
    deck: Deck, segments: list[Segment]
) -> None:
    """§4.1 says "talked for *minutes*": with the duration gate unmeetable there are
    three chunks, none a gap, and the detour stays with slide 1."""
    chunks = align_lecture(deck, segments, min_gap_s=float("inf"))
    assert [chunk.slides for chunk in chunks] == [
        SlideRange(start=1, end=1),
        SlideRange(start=2, end=2),
        SlideRange(start=3, end=3),
    ]
    assert chunks[0].segments == tuple(segments[0:12])


def test_min_silence_10_leaves_no_qualifying_silence(
    deck: Deck, segments: list[Segment]
) -> None:
    """The fixture's silences are 2 s and 3 s: at ``min_silence_s=10.0`` nothing
    brackets the detour and the result is the same three chunks."""
    chunks = align_lecture(deck, segments, min_silence_s=10.0)
    assert chunks == align_lecture(deck, segments, min_gap_s=float("inf"))
    assert len(chunks) == 3
    assert all(chunk.slides is not None for chunk in chunks)


# --- ad-hoc decks (file-format/edge cases in tests, lecture cases in the fixture) --


def test_a_hidden_slide_never_receives_a_chunk() -> None:
    """Skip, never renumber: slide 2 is hidden, so even speech that matches its
    vocabulary exactly cannot produce a chunk citing it."""
    deck = Deck(
        source="adhoc.pptx",
        slides=(
            _slide_only(1, ("gradient descent converges",)),
            _slide_only(2, ("quarterback touchdown football",), hidden=True),
        ),
        assets=(),
    )
    segments = [
        Segment(start_s=0.0, end_s=10.0, text="the quarterback throws a touchdown football"),
        Segment(start_s=10.0, end_s=20.0, text="another quarterback touchdown football replay"),
    ]
    chunks = align_lecture(deck, segments)
    assert chunks == [Chunk(slides=SlideRange(start=1, end=1), segments=tuple(segments))]
    assert all(
        chunk.slides is None or chunk.slides == SlideRange(start=1, end=1) for chunk in chunks
    )


def test_a_deck_with_no_visible_slides_yields_one_ungated_gap_chunk() -> None:
    """Nothing to attach speech to and no boundary evidence to gate on: everything
    lands in a single gap chunk, duration and silence gates notwithstanding."""
    deck = Deck(
        source="adhoc.pptx",
        slides=(
            _slide_only(1, ("alpha bravo",), hidden=True),
            _slide_only(2, ("carol delta",), hidden=True),
        ),
        assets=(),
    )
    segments = [
        Segment(start_s=0.0, end_s=5.0, text="alpha bravo spoken"),
        Segment(start_s=5.0, end_s=9.0, text="carol delta spoken"),
    ]
    assert align_lecture(deck, segments) == [Chunk(slides=None, segments=tuple(segments))]


def test_no_segments_yields_no_chunks(deck: Deck) -> None:
    assert align_lecture(deck, []) == []


# --- Chunk validators -------------------------------------------------------------


def test_chunk_rejects_empty_segments() -> None:
    with pytest.raises(ValidationError, match="at least one segment"):
        Chunk(slides=None, segments=())


def test_chunk_span_is_min_start_and_max_end_not_first_and_last() -> None:
    """Spans are unions and may overlap (P1-03), so the span is min/max over the
    members: here the first segment ends last and the second starts first."""
    chunk = Chunk(
        slides=None,
        segments=(
            Segment(start_s=10.0, end_s=100.0, text="ends last"),
            Segment(start_s=5.0, end_s=30.0, text="starts first"),
        ),
    )
    assert chunk.start_s == 5.0
    assert chunk.end_s == 100.0
