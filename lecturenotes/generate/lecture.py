"""Generation (plan §3 stage 5): the density merge, the chunk pass, the synthesis
pass, asset minting, and the phase's single entrypoint.

    merge_chunks(chunks, min_words=100)              pure §9.1 density merge
    generate_topic(chunk, deck, lecture_id, client)  one Chunk → one Topic
    generate_lecture(deck, chunks, ...)              the only entrypoint: merge →
                                                     chunk pass → synthesis → assets

Decisions (P5-03):

- **``generate_lecture(deck, chunks, ...)`` is the only entrypoint** — the phase
  convention. It takes chunks, not paths: stage 5's input is ``[Chunk]`` plus the deck
  for slide context, and composing ingest → align → generate is the caller's job
  (P5-04's ``build``).
- **Assets land in ``media/``, id-keyed, path-relative.** ``MediaAsset.source`` is a
  POSIX path relative to the week document's directory, so the expected fixture stays
  byte-stable, re-runs overwrite in place, and the P3-03 emitter needs no change.
- **Only referenced images are minted.** ``image_ids`` already excludes recurring
  logos (P2-03), and an image no ``Figure`` cites has no reader; the deck keeps the
  bytes, generation copies out only what the notes use.
- **Five requests per fixture lecture, exactly** (4 chunks + 1 synthesis), pinned so
  cost regressions are test failures, not invoice surprises.

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

from collections.abc import Mapping, Sequence
from pathlib import Path

from lecturenotes.align import Chunk
from lecturenotes.generate.client import LLMClient
from lecturenotes.generate.prompts import (
    ChunkNotes,
    LectureSynthesis,
    chunk_prompt,
    cited_slides,
    synthesis_prompt,
)
from lecturenotes.ingest.slides import Deck
from lecturenotes.model import (
    Figure,
    MediaAsset,
    NoteLecture,
    SlideRange,
    SourceAnchor,
    SourceRef,
    Topic,
    topic_id,
)

__all__ = ["generate_lecture", "generate_topic", "merge_chunks"]

# Minted-file extensions by MediaAsset.media_type — the types slide ingest can emit.
# Explicit and tiny on purpose: an unmapped type raises rather than guessing.
_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
}


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


def _chunk_topic(
    chunk: Chunk, deck: Deck, lecture_id: str, client: LLMClient
) -> tuple[Topic, dict[str, str]]:
    """The chunk pass proper: one ``complete``, validated, plus the response's alts.

    ``generate_topic`` and ``generate_lecture`` both go through here, so the request
    and validation path cannot drift between them.
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
    topic = Topic(
        id=topic_id(lecture_id, chunk.slides, chunk.start_s),
        heading=notes.heading,
        anchor=SourceAnchor(start_s=chunk.start_s, end_s=chunk.end_s, slides=chunk.slides),
        body=notes.body,
        cards=notes.cards,
    )
    return topic, notes.image_alts


def generate_topic(chunk: Chunk, deck: Deck, lecture_id: str, client: LLMClient) -> Topic:
    """One ``complete`` call: prompt the chunk, validate, verify figures, coordinate.

    The topic's id and anchor come from the chunk, never from the model: the §7.2
    stable id is ``topic_id(lecture_id, chunk.slides, chunk.start_s)`` and the anchor
    is the chunk span verbatim, so every claim stays checkable in seconds.
    """
    topic, _ = _chunk_topic(chunk, deck, lecture_id, client)
    return topic


def _mint_assets(
    deck: Deck, topics: Sequence[Topic], image_alts: Mapping[str, str], out_dir: Path
) -> list[MediaAsset]:
    """Write each referenced slide image under ``out_dir / "media"``, id-keyed.

    First-reference order across topics; an image reused by several figures is one
    file and one asset. The ids were verified against the cited slides in the chunk
    pass, so the deck lookup cannot miss.
    """
    images = {image.id: image for image in deck.assets}
    assets: list[MediaAsset] = []
    minted: set[str] = set()
    for topic in topics:
        for node in topic.body:
            if not isinstance(node, Figure) or node.asset_id in minted:
                continue
            image = images[node.asset_id]
            ext = _EXTENSIONS.get(image.media_type)
            if ext is None:
                raise ValueError(
                    f"no file extension mapped for media type {image.media_type!r}"
                    f" (asset {image.id!r})"
                )
            target = out_dir / "media" / f"{image.id}{ext}"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(image.data)
            minted.add(image.id)
            assets.append(
                MediaAsset(
                    id=image.id,
                    media_type=image.media_type,
                    source=f"media/{image.id}{ext}",
                    alt=image_alts.get(image.id),
                )
            )
    return assets


def generate_lecture(
    deck: Deck,
    chunks: Sequence[Chunk],
    *,
    lecture_id: str,
    source: SourceRef,
    client: LLMClient,
    out_dir: Path,
    min_words: int = 100,
) -> NoteLecture:
    """Plan §3 stage 5 end to end: merge → chunk pass → synthesis → asset minting.

    The only entrypoint of ``generate/``; everything else is exported for debugging
    and tests. One ``complete`` per merged chunk plus one for the synthesis, and the
    model's own validators (figure refs resolve, asset ids unique) are the final gate.
    """
    topics: list[Topic] = []
    image_alts: dict[str, str] = {}
    for chunk in merge_chunks(chunks, min_words):
        topic, alts = _chunk_topic(chunk, deck, lecture_id, client)
        topics.append(topic)
        image_alts.update(alts)
    synthesis = LectureSynthesis.model_validate_json(
        client.complete(synthesis_prompt(topics, lecture_id))
    )
    return NoteLecture(
        id=lecture_id,
        title=synthesis.title,
        overview=synthesis.overview,
        objectives=synthesis.objectives,
        source=source,
        topics=topics,
        glossary=synthesis.glossary,
        open_questions=synthesis.open_questions,
        assets=_mint_assets(deck, topics, image_alts, out_dir),
    )
