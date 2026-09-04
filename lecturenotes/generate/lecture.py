"""The chunk pass (plan §4.2): the density merge and one-chunk topic generation.

    merge_chunks(chunks, min_words=100)              pure §9.1 density merge
    generate_topic(chunk, deck, lecture_id, client)  one Chunk → one Topic

Decisions (P5-02):

- **The density floor is 100 words, not §9.1's suggested ~120.** The committed
  fixture chunks weigh 81/120/103/103 words: at 120, slides 2 and 3 would merge into
  one topic and sever the chunk↔week01-topic correspondence the P4 fixtures were
  built around. P5-04's ``--min-words`` is the tuning knob for real lectures.
- **Gap chunks fence merging.** Board work merged into a slide chunk would cite
  slides the lecturer wasn't on (the anchor-honesty rule), and a slide chunk merged
  into a gap would erase the §4.1 gap signal Phase 9 triggers on. A fenced
  under-floor chunk stays: a thin topic is honest, a mis-cited one is not.
- **Merge before spend.** ``merge_chunks`` is pure and runs before any request, so
  no tokens are paid for topics that would be thrown away, no §7.2 ids are orphaned,
  and ``--dry-run`` (P5-04) shows exactly what will be prompted.
- **Figures are verified against the chunk's cited slides.** A ``Figure.asset_id``
  the chunk's slides don't carry (or any figure on a gap chunk) is a hallucinated
  citation and raises ``ValueError`` naming the id — the anchor-honesty rule again.
"""

from __future__ import annotations

from collections.abc import Sequence

from lecturenotes.align import Chunk
from lecturenotes.generate.client import LLMClient
from lecturenotes.generate.prompts import ChunkNotes, chunk_prompt, cited_slides
from lecturenotes.ingest.slides import Deck
from lecturenotes.model import Figure, SlideRange, SourceAnchor, Topic, topic_id

__all__ = ["generate_topic", "merge_chunks"]


def _word_count(chunk: Chunk) -> int:
    return sum(len(segment.text.split()) for segment in chunk.segments)


def _merge(first: Chunk, second: Chunk) -> Chunk:
    assert first.slides is not None and second.slides is not None
    return Chunk(
        slides=SlideRange(
            start=min(first.slides.start, second.slides.start),
            end=max(first.slides.end, second.slides.end),
        ),
        segments=first.segments + second.segments,
    )


def merge_chunks(chunks: Sequence[Chunk], min_words: int = 100) -> list[Chunk]:
    """Merge under-floor slide chunks into adjacent slide chunks (plan §9.1).

    Repeatedly (leftmost first) merges a below-``min_words`` slide chunk into the
    adjacent slide chunk — predecessor preferred, else successor — unioning slide
    ranges and concatenating segments, until every slide chunk clears the floor or is
    fenced. Gap chunks and the list ends fence: a gap chunk is never a merge
    candidate on either side, whatever its word count. Pure and deterministic; the
    output still partitions the input segments in order (the P4-03 invariant).
    """
    merged = list(chunks)
    while True:
        for index, chunk in enumerate(merged):
            if chunk.slides is None or _word_count(chunk) >= min_words:
                continue
            if index > 0 and merged[index - 1].slides is not None:
                merged[index - 1 : index + 1] = [_merge(merged[index - 1], chunk)]
                break
            if index + 1 < len(merged) and merged[index + 1].slides is not None:
                merged[index : index + 2] = [_merge(chunk, merged[index + 1])]
                break
        else:
            return merged


def generate_topic(chunk: Chunk, deck: Deck, lecture_id: str, client: LLMClient) -> Topic:
    """One ``complete`` call: prompt the chunk, validate, verify figures, coordinate.

    The topic's id and anchor come from the chunk, never from the model: the §7.2
    stable id is ``topic_id(lecture_id, chunk.slides, chunk.start_s)`` and the anchor
    is the chunk span verbatim, so every claim stays checkable in seconds.
    """
    notes = ChunkNotes.model_validate_json(client.complete(chunk_prompt(chunk, deck, lecture_id)))
    allowed = {
        image_id for slide in cited_slides(deck, chunk.slides) for image_id in slide.image_ids
    }
    for node in notes.body:
        if isinstance(node, Figure) and node.asset_id not in allowed:
            raise ValueError(
                f"figure references image id {node.asset_id!r},"
                f" which is not on the slides cited by chunk {chunk.slides}"
            )
    return Topic(
        id=topic_id(lecture_id, chunk.slides, chunk.start_s),
        heading=notes.heading,
        anchor=SourceAnchor(start_s=chunk.start_s, end_s=chunk.end_s, slides=chunk.slides),
        body=notes.body,
        cards=notes.cards,
    )
