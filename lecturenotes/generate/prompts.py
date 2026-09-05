"""The generation prompts (plan §4.2): the per-chunk pass and the lecture-level
synthesis pass.

    PROMPT_VERSION                 the §7.1 cache-invalidation knob — bump deliberately
    ChunkNotes                     what the model must return: heading, body, cards,
                                   alt text per referenced image id
    chunk_prompt(chunk, deck, id)  one ``Chunk`` → one ``GenRequest``
    LectureSynthesis               the lecture-level return: title, overview,
                                   objectives, glossary, open questions
    synthesis_prompt(topics, id)   all of a lecture's topics → one ``GenRequest``

Decisions (P5-03):

- **Synthesis reads the generated topics, not the transcript.** Its job is coherence
  over what the notes *say*; the transcript was already distilled chunk by chunk where
  the model had room for detail (§4.2). Topic bodies ride along as compact JSON — the
  model reads the IR it just wrote.
- **The synthesis must add nothing the topics don't support** — the §4.2
  anti-hallucination stance at lecture level, pinned by exact substring in the tests.

Decisions (P5-02):

- **Request keys are ``"chunk:" + topic_id(...)``** — one id scheme end to end: the
  fake's fixture keys, the topic ids and log lines all name the same coordinates, and
  recorded fixtures survive prompt tuning because keys never hash content (P5-01).
- **The prompt embeds ``ChunkNotes.model_json_schema()``.** The pydantic model is the
  single source of truth: a schema edit changes the prompt automatically, so prompt
  and validator cannot drift apart (the pinned-fragment test guards the embedding).
- **``ChunkNotes`` reuses the IR's ``Node``/``CardSeed`` types wholesale.** The model
  writes IR, not a parallel dialect (plan §2.1); if Phase 6 forces an IR change, mypy
  finds this seam like every other (plan §10).
- **Plain seconds in the prompt** — ``format_clock`` is presentation-side and
  ``render/`` is unimportable here (import-linter contract 4).
- **Notes and image ids are context, not structure**: the PDF deck (``notes=None``,
  re-encoded image ids) and the PPTX deck produce different prompt *text* but the same
  prompt shape — format differences stay inside the prompt.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from lecturenotes.align import Chunk
from lecturenotes.generate.client import GenRequest
from lecturenotes.ingest.slides import Deck, Slide
from lecturenotes.model import CardSeed, Definition, Node, SlideRange, Topic, topic_id

__all__ = [
    "PROMPT_VERSION",
    "ChunkNotes",
    "LectureSynthesis",
    "chunk_prompt",
    "synthesis_prompt",
]

PROMPT_VERSION: str = "3"

# The exact sentence the gap-chunk prompt test pins: gap chunks are the §4.1 board-work
# signal, and the model must know there is no slide context rather than inventing one.
_GAP_FRAMING = (
    "The lecturer was away from the slides for this passage (board work or live"
    " demonstration); there is no slide context."
)

_INSTRUCTIONS = """\
## Instructions
- Write study notes for this topic from the transcript and slide context above.
- Start the body with a short prose summary, then a bullet list of key points.
- Write mathematics as LaTeX, only inside Equation nodes.
- Quote exam or emphasis remarks near-verbatim in a Callout of kind EXAM.
- Produce at least one card per topic: a question a student can answer from the body \
alone.
- Do not smooth over gaps: use a Callout of kind UNCERTAIN instead of guessing where \
the transcript is garbled or ambiguous.
- Reference only the listed image ids in Figure nodes, and give every referenced id \
alt text in image_alts. Never invent an image id: if a diagram or chart you want to \
show has no id listed under "Images on this slide", describe the visual in prose instead \
of emitting a Figure node."""


class ChunkNotes(BaseModel):
    """What the model returns for one chunk: a topic's content, minus its coordinates.

    ``image_alts`` carries alt text per referenced image id — ``Figure.caption`` is
    the visible caption, ``MediaAsset.alt`` the accessibility text; both exist in the
    IR and both need a source (P5-03 mints the assets).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    heading: str
    body: list[Node]
    cards: list[CardSeed] = []
    image_alts: dict[str, str] = {}


def cited_slides(deck: Deck, slides: SlideRange | None) -> list[Slide]:
    """The visible slides a chunk cites; hidden slides never provide context.

    A merged range can span a hidden slide (P5-02's ``merge_chunks`` unions ranges);
    its content was never shown, so it contributes neither prompt context nor
    permissible image ids.
    """
    if slides is None:
        return []
    return [
        slide
        for slide in deck.slides
        if slides.start <= slide.number <= slides.end and not slide.hidden
    ]


def _slide_context(deck: Deck, slides: SlideRange | None) -> list[str]:
    if slides is None:
        return [_GAP_FRAMING]
    assets = {asset.id: asset for asset in deck.assets}
    lines: list[str] = []
    for slide in cited_slides(deck, slides):
        title = f": {slide.title}" if slide.title is not None else ""
        lines.append(f"## Slide {slide.number}{title}")
        for block in slide.blocks:
            lines.extend(block.lines)
            lines.append("")
        if slide.notes is not None:
            lines.append("### Speaker notes")
            lines.append(slide.notes)
            lines.append("")
        if slide.image_ids:
            lines.append("### Images on this slide")
            for image_id in slide.image_ids:
                asset = assets[image_id]
                lines.append(f"{image_id} ({asset.width}x{asset.height})")
            lines.append("")
    return lines[:-1] if lines and lines[-1] == "" else lines


def chunk_prompt(chunk: Chunk, deck: Deck, lecture_id: str) -> GenRequest:
    """One ``Chunk`` → one ``GenRequest`` (the per-chunk half of plan §4.2)."""
    lines = [
        "You are turning one topic of a recorded lecture into structured study notes.",
        "",
        "## Transcript (seconds)",
        *(
            f"[{segment.start_s}-{segment.end_s}] {segment.text}"
            for segment in chunk.segments
        ),
        "",
        *_slide_context(deck, chunk.slides),
        "",
        _INSTRUCTIONS,
        "",
        "## Response schema",
        "Respond with a single JSON object matching this schema, and nothing else:",
        json.dumps(ChunkNotes.model_json_schema(), indent=2),
    ]
    return GenRequest(
        key="chunk:" + topic_id(lecture_id, chunk.slides, chunk.start_s),
        prompt="\n".join(lines) + "\n",
    )


_SYNTHESIS_INSTRUCTIONS = """\
## Instructions
- Write the lecture-level front matter for the study notes above.
- Give a title, an overview of a few sentences, and 2-4 objectives.
- Include glossary definitions only for terms the topics actually define or use.
- List open questions a student should follow up on.
- Add nothing the topics do not support: every claim in the overview, objectives, \
glossary and open questions must come from the topics above."""


class LectureSynthesis(BaseModel):
    """What the model returns for the lecture-level pass: front matter over the topics.

    Reuses the IR's ``Definition`` for the glossary, the same way ``ChunkNotes``
    reuses ``Node``/``CardSeed``: the model writes IR, not a parallel dialect.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str
    overview: str
    objectives: list[str]
    glossary: list[Definition] = []
    open_questions: list[str] = []


def synthesis_prompt(topics: Sequence[Topic], lecture_id: str) -> GenRequest:
    """All of a lecture's topics → one ``GenRequest`` (the synthesis half of §4.2)."""
    lines = [
        "You are writing the front matter for one lecture's structured study notes.",
        "The topics below are the finished notes; read them as given.",
        "",
    ]
    for topic in topics:
        body = json.dumps(
            [node.model_dump(mode="json") for node in topic.body], separators=(",", ":")
        )
        lines.extend([f"## {topic.heading}", body, ""])
    lines.extend(
        [
            _SYNTHESIS_INSTRUCTIONS,
            "",
            "## Response schema",
            "Respond with a single JSON object matching this schema, and nothing else:",
            json.dumps(LectureSynthesis.model_json_schema(), indent=2),
        ]
    )
    return GenRequest(key=f"synthesis:{lecture_id}", prompt="\n".join(lines) + "\n")
