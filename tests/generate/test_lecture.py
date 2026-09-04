"""P5-02 chunk-pass tests: ``merge_chunks`` on the fixture and ad-hoc cases, and
``generate_topic`` reproducing the week01 lec01 topics through the recorded fake.

The density floor is 100 words (P5-02 decision, not §9.1's suggested ~120): the
committed chunks weigh 81/120/103/103 words, so at 120 slides 2 and 3 would merge and
sever the chunk↔week01-topic correspondence the P4 fixtures were built around.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lecturenotes.align import Chunk
from lecturenotes.generate.client import RecordedClient
from lecturenotes.generate.lecture import generate_topic, merge_chunks
from lecturenotes.ingest.captions import Segment
from lecturenotes.ingest.slides import Deck
from lecturenotes.model import Figure, NoteWeek, SlideRange

PPTX_IMAGE_ID = "img-a63ae9b7dc5e9397"


def _words(chunk: Chunk) -> int:
    return sum(len(segment.text.split()) for segment in chunk.segments)


def _segment(word_count: int, start: float) -> Segment:
    return Segment(start_s=start, end_s=start + 1.0, text=" ".join(["w"] * word_count))


def _slide_chunk(number: int, word_count: int, start: float) -> Chunk:
    return Chunk(
        slides=SlideRange(start=number, end=number), segments=(_segment(word_count, start),)
    )


def _gap_chunk(word_count: int, start: float) -> Chunk:
    return Chunk(slides=None, segments=(_segment(word_count, start),))


# --- merge_chunks on the fixture ----------------------------------------------------


def test_fixture_chunk_word_counts(chunks: list[Chunk]) -> None:
    """The documented weights: 81 (fenced by the gap), 120, 103, 103."""
    assert [_words(chunk) for chunk in chunks] == [81, 120, 103, 103]


def test_fixture_chunks_survive_the_default_floor(chunks: list[Chunk]) -> None:
    """Chunks 2-4 clear 100; chunk 1 (81 words) is fenced by the gap, so it stays."""
    assert merge_chunks(chunks) == chunks


# --- merge_chunks, ad-hoc -----------------------------------------------------------


def test_under_floor_chunk_merges_into_its_predecessor() -> None:
    first, small, last = (
        _slide_chunk(1, 150, 0.0),
        _slide_chunk(2, 50, 10.0),
        _slide_chunk(3, 150, 20.0),
    )
    merged = merge_chunks([first, small, last])
    assert merged == [
        Chunk(slides=SlideRange(start=1, end=2), segments=first.segments + small.segments),
        last,
    ]


def test_under_floor_chunk_at_the_start_merges_forward() -> None:
    small, rest = _slide_chunk(1, 50, 0.0), _slide_chunk(2, 150, 10.0)
    assert merge_chunks([small, rest]) == [
        Chunk(slides=SlideRange(start=1, end=2), segments=small.segments + rest.segments)
    ]


def test_under_floor_chunk_fenced_by_gaps_survives() -> None:
    fenced = [_gap_chunk(120, 0.0), _slide_chunk(2, 10, 10.0), _gap_chunk(120, 20.0)]
    assert merge_chunks(fenced) == fenced


def test_gap_chunks_are_never_merged_into_and_never_absorbed() -> None:
    """Whatever its word count, a gap chunk neither joins a neighbour nor takes one."""
    chunks = [_slide_chunk(1, 150, 0.0), _gap_chunk(5, 10.0), _slide_chunk(2, 150, 20.0)]
    assert merge_chunks(chunks) == chunks


def test_merging_cascades_until_the_floor_is_met() -> None:
    chunks = [_slide_chunk(1, 40, 0.0), _slide_chunk(2, 40, 10.0), _slide_chunk(3, 40, 20.0)]
    assert merge_chunks(chunks) == [
        Chunk(
            slides=SlideRange(start=1, end=3),
            segments=tuple(segment for chunk in chunks for segment in chunk.segments),
        )
    ]


def test_the_floor_is_a_knob() -> None:
    chunks = [_slide_chunk(1, 60, 0.0), _slide_chunk(2, 60, 10.0)]
    assert merge_chunks(chunks, min_words=50) == chunks
    assert merge_chunks(chunks, min_words=80) == [
        Chunk(slides=SlideRange(start=1, end=2), segments=chunks[0].segments + chunks[1].segments)
    ]


# --- generate_topic against the recorded fake ---------------------------------------


@pytest.fixture(scope="module")
def client(responses_path: Path) -> RecordedClient:
    return RecordedClient(responses_path)


def test_slide_2_topic_equals_week01_bellman_topic(
    chunks: list[Chunk], deck: Deck, client: RecordedClient, week01: NoteWeek
) -> None:
    topic = generate_topic(chunks[2], deck, "lec01", client=client)
    expected = week01.lectures[0].topics[2]
    assert topic == expected
    assert topic.id == "lec01:s2-2"
    assert (topic.anchor.start_s, topic.anchor.end_s) == (271.0, 419.0)
    assert topic.anchor.slides == SlideRange(start=2, end=2)


def test_first_two_topics_equal_week01s(
    chunks: list[Chunk], deck: Deck, client: RecordedClient, week01: NoteWeek
) -> None:
    lec01 = week01.lectures[0]
    assert generate_topic(chunks[0], deck, "lec01", client=client) == lec01.topics[0]
    assert generate_topic(chunks[1], deck, "lec01", client=client) == lec01.topics[1]


def test_slide_3_topic_equals_week01s_up_to_the_figure_asset_id(
    chunks: list[Chunk], deck: Deck, client: RecordedClient, week01: NoteWeek
) -> None:
    """The recorded response cites the PPTX image id, not week01's semantic id."""
    topic = generate_topic(chunks[3], deck, "lec01", client=client)
    week01_topic = week01.lectures[0].topics[3]
    expected = week01_topic.model_copy(
        update={
            "body": [
                node.model_copy(update={"asset_id": PPTX_IMAGE_ID})
                if isinstance(node, Figure)
                else node
                for node in week01_topic.body
            ]
        }
    )
    assert topic != week01_topic
    assert topic == expected


def _client_answering(tmp_path: Path, key: str, body: list[dict[str, str]]) -> RecordedClient:
    path = tmp_path / "responses.json"
    response = json.dumps({"heading": "h", "body": body})
    path.write_text(json.dumps({key: response}), encoding="utf-8")
    return RecordedClient(path)


def test_figure_citing_an_image_not_on_the_slides_raises(
    chunks: list[Chunk], deck: Deck, tmp_path: Path
) -> None:
    bad = _client_answering(
        tmp_path,
        "chunk:lec01:s2-2",
        [{"type": "figure", "asset_id": "img-deadbeef00000000"}],
    )
    with pytest.raises(ValueError, match="img-deadbeef00000000"):
        generate_topic(chunks[2], deck, "lec01", client=bad)


def test_any_figure_on_a_gap_chunk_raises(
    chunks: list[Chunk], deck: Deck, tmp_path: Path
) -> None:
    """A gap chunk cites no slides, so even a real deck image id is out of bounds."""
    bad = _client_answering(
        tmp_path, "chunk:lec01:t151", [{"type": "figure", "asset_id": PPTX_IMAGE_ID}]
    )
    with pytest.raises(ValueError, match=PPTX_IMAGE_ID):
        generate_topic(chunks[1], deck, "lec01", client=bad)
