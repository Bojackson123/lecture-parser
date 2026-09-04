"""P4-03 property tests (plan §10): ``align_lecture`` output partitions and stays monotonic.

Plan §10 verbatim: alignment output must be monotonic and must partition the segments,
for any input. The knobs are drawn too — small ``min_gap_s`` values force the carving
paths that the fixture's single detour cannot reach on its own.
"""

from __future__ import annotations

from itertools import pairwise

from hypothesis import given
from hypothesis import strategies as st

from lecturenotes.align.boundaries import align_lecture
from lecturenotes.ingest.captions import Segment
from lecturenotes.ingest.slides import Deck
from tests.align.strategies import ordered_segments, small_decks

_MIN_GAPS = st.sampled_from([0.0, 1.0, 5.0, 60.0])
_MIN_SILENCES = st.sampled_from([0.5, 1.0, 2.0])


@given(small_decks(), ordered_segments(), _MIN_GAPS, _MIN_SILENCES)
def test_chunks_partition_the_segments_in_order(
    deck: Deck, segments: list[Segment], min_gap_s: float, min_silence_s: float
) -> None:
    """Plan §10 verbatim: concatenating ``chunk.segments`` gives back the input."""
    chunks = align_lecture(deck, segments, min_gap_s=min_gap_s, min_silence_s=min_silence_s)
    assert [s for chunk in chunks for s in chunk.segments] == segments


@given(small_decks(), ordered_segments(), _MIN_GAPS, _MIN_SILENCES)
def test_non_gap_chunks_are_monotonic(
    deck: Deck, segments: list[Segment], min_gap_s: float, min_silence_s: float
) -> None:
    """Non-decreasing, not strict: a carved middle may split one slide's window."""
    chunks = align_lecture(deck, segments, min_gap_s=min_gap_s, min_silence_s=min_silence_s)
    starts = [chunk.slides.start for chunk in chunks if chunk.slides is not None]
    assert all(a <= b for a, b in pairwise(starts))


@given(small_decks(), ordered_segments(), _MIN_GAPS, _MIN_SILENCES)
def test_overlapping_segments_are_never_in_different_chunks(
    deck: Deck, segments: list[Segment], min_gap_s: float, min_silence_s: float
) -> None:
    """The P1-03 span-union rule paying rent: cue-mates stay together, so a chunk
    boundary can never point an anchor at words that belong to the other side."""
    chunks = align_lecture(deck, segments, min_gap_s=min_gap_s, min_silence_s=min_silence_s)
    chunk_of: dict[int, int] = {}
    position = 0
    for index, chunk in enumerate(chunks):
        for _ in chunk.segments:
            chunk_of[position] = index
            position += 1
    for i in range(1, len(segments)):
        if segments[i].start_s < segments[i - 1].end_s:
            assert chunk_of[i] == chunk_of[i - 1]


@given(small_decks(), ordered_segments(), _MIN_GAPS, _MIN_SILENCES)
def test_chunks_are_non_empty_and_gaps_span_min_gap(
    deck: Deck, segments: list[Segment], min_gap_s: float, min_silence_s: float
) -> None:
    """With visible slides present, only a piece at least ``min_gap_s`` wide may be
    carved out as a gap (§4.1: "talked for *minutes*")."""
    chunks = align_lecture(deck, segments, min_gap_s=min_gap_s, min_silence_s=min_silence_s)
    for chunk in chunks:
        assert chunk.segments
        if chunk.slides is None:
            assert chunk.end_s - chunk.start_s >= min_gap_s


@given(small_decks(), ordered_segments(), _MIN_SILENCES)
def test_infinite_min_gap_yields_no_gap_chunks(
    deck: Deck, segments: list[Segment], min_silence_s: float
) -> None:
    chunks = align_lecture(deck, segments, min_gap_s=float("inf"), min_silence_s=min_silence_s)
    assert all(chunk.slides is not None for chunk in chunks)


@given(small_decks(), ordered_segments(), _MIN_GAPS, _MIN_SILENCES)
def test_align_lecture_is_deterministic(
    deck: Deck, segments: list[Segment], min_gap_s: float, min_silence_s: float
) -> None:
    first = align_lecture(deck, segments, min_gap_s=min_gap_s, min_silence_s=min_silence_s)
    second = align_lecture(deck, segments, min_gap_s=min_gap_s, min_silence_s=min_silence_s)
    assert first == second
