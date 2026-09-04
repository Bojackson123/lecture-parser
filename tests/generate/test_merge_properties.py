"""Hypothesis properties for ``merge_chunks`` (P5-02).

``chunk_lists`` generates alignment-shaped input — non-decreasing slide ranges,
non-empty segments, word counts straddling the 100-word floor — and the properties
mirror the P4-03 invariants the merge must preserve: the output still partitions the
input segments in order, ranges stay monotonic, and gap chunks pass through untouched.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from lecturenotes.align import Chunk
from lecturenotes.generate.lecture import merge_chunks
from lecturenotes.ingest.captions import Segment
from lecturenotes.model import SlideRange

FLOOR = 100


@st.composite
def chunk_lists(draw: st.DrawFn) -> list[Chunk]:
    """0-6 chunks with non-decreasing slide ranges and 1-3 word-salad segments each."""
    count = draw(st.integers(min_value=0, max_value=6))
    chunks: list[Chunk] = []
    slide = 1
    time = 0.0
    for _ in range(count):
        segments: list[Segment] = []
        for _ in range(draw(st.integers(min_value=1, max_value=3))):
            word_count = draw(st.integers(min_value=1, max_value=120))
            duration = draw(st.integers(min_value=1, max_value=5))
            segments.append(
                Segment(start_s=time, end_s=time + duration, text=" ".join(["w"] * word_count))
            )
            time += duration
        if draw(st.booleans()):
            chunks.append(Chunk(slides=None, segments=tuple(segments)))
        else:
            slide += draw(st.integers(min_value=0, max_value=2))
            end = slide + draw(st.integers(min_value=0, max_value=1))
            chunks.append(
                Chunk(slides=SlideRange(start=slide, end=end), segments=tuple(segments))
            )
            slide = end
    return chunks


def _words(chunk: Chunk) -> int:
    return sum(len(segment.text.split()) for segment in chunk.segments)


@given(chunk_lists())
def test_output_concatenates_to_exactly_the_input_segments(chunks: list[Chunk]) -> None:
    merged = merge_chunks(chunks)
    assert [segment for chunk in merged for segment in chunk.segments] == [
        segment for chunk in chunks for segment in chunk.segments
    ]


@given(chunk_lists())
def test_slide_ranges_stay_non_decreasing(chunks: list[Chunk]) -> None:
    ranges = [chunk.slides for chunk in merge_chunks(chunks) if chunk.slides is not None]
    for previous, current in zip(ranges, ranges[1:], strict=False):
        assert previous.start <= current.start
        assert previous.end <= current.end


@given(chunk_lists())
def test_gap_chunks_pass_through_unchanged_and_unmerged(chunks: list[Chunk]) -> None:
    merged = merge_chunks(chunks)
    assert [chunk for chunk in merged if chunk.slides is None] == [
        chunk for chunk in chunks if chunk.slides is None
    ]


@given(chunk_lists())
def test_merge_is_a_fixpoint(chunks: list[Chunk]) -> None:
    merged = merge_chunks(chunks)
    assert merge_chunks(merged) == merged


@given(chunk_lists())
def test_every_output_slide_chunk_meets_the_floor_or_is_fenced(chunks: list[Chunk]) -> None:
    merged = merge_chunks(chunks)
    for index, chunk in enumerate(merged):
        if chunk.slides is None or _words(chunk) >= FLOOR:
            continue
        has_slide_neighbour = (index > 0 and merged[index - 1].slides is not None) or (
            index + 1 < len(merged) and merged[index + 1].slides is not None
        )
        assert not has_slide_neighbour
