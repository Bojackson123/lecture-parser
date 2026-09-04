"""``AnkiRenderer``: a ``NoteWeek``'s cards as one Anki notes-in-plain-text file
(plan §5, P6-02).

The format spec is the hand-written ``tests/fixtures/notes/week01.anki.txt``; every
formatting decision here is reviewable there, and the rules were decided in P6-01.
One deck per week, named ``{week.id}.txt`` — stable, so re-emitting overwrites in
place (plan §7.2); the guid column makes re-*import* an update inside Anki itself.

The deck renders ``topic.cards`` only — plain strings — so no body construct ever
reaches the output: ``capabilities`` is the full set because this renderer trivially
tolerates everything, not as a shortcut. A card-less topic contributes no rows — the
every-topic-≥ 1-card guarantee belongs to generation (P6-01's prompt pin); a renderer
that padded missing cards would be inventing content.

Guids hash the **raw IR front**, before math translation, keeping them independent of
renderer formatting decisions; a reworded front is deliberately a *new* card (P6-01).
Paired ``$…$`` becomes ``\\(…\\)`` in fronts and backs only — delimiter translation
for Anki's MathJax, not re-parsing; unpaired ``$`` passes through. ``#html:false``
means ``<`` and ``&`` need no escaping.

``card_guid``, ``translate_math`` and ``quote_field`` are exported for debugging and
tests, not for re-composition elsewhere — ``card_guid`` in particular stays out of
``model/ids.py`` because it exists only for Anki's import protocol.
"""

from __future__ import annotations

import hashlib
import re

from lecturenotes.model import Capability, CardSeed, NoteWeek, SourceAnchor
from lecturenotes.render.base import (
    RenderedDocument,
    RenderOptions,
    RenderResult,
    format_clock,
)

_HEADER = ("#separator:tab", "#html:false", "#notetype:Basic")
_MATH_PAIR = re.compile(r"\$([^$]+)\$")
_QUOTE_TRIGGERS = ("\t", "\n", '"')


class AnkiRenderer:
    """Renders a week's cards to one Anki TSV deck. Pure string building — no IO."""

    name = "anki"
    capabilities = set(Capability)

    def render(self, week: NoteWeek, opts: RenderOptions) -> RenderResult:
        lines = [
            *_HEADER,
            f"#deck:{week.course}::Week {week.week_number}",
            "#guid column:1",
            "#tags column:4",
        ]
        for lecture in week.lectures:
            for topic in lecture.topics:
                citation = _citation(lecture.id, topic.anchor)
                lines.extend(_row(topic.id, card, citation) for card in topic.cards)
        text = "\n".join(lines) + "\n"
        document = RenderedDocument(name=f"{week.id}.txt", text=text)
        return RenderResult(documents=(document,), assets=())


def card_guid(topic_id: str, front: str) -> str:
    """16 hex of sha256 over the topic id and the raw IR front (P6-01)."""
    return hashlib.sha256(f"{topic_id}\n{front}".encode()).hexdigest()[:16]


def translate_math(text: str) -> str:
    r"""Every paired ``$…$`` → ``\(…\)``; an unpaired ``$`` passes through."""
    return _MATH_PAIR.sub(r"\\(\1\\)", text)


def quote_field(field: str) -> str:
    """Anki's CSV quoting: wrap iff the field holds a tab, newline or ``"``."""
    if any(trigger in field for trigger in _QUOTE_TRIGGERS):
        return '"' + field.replace('"', '""') + '"'
    return field


def _row(topic_id: str, card: CardSeed, citation: str) -> str:
    fields = (
        card_guid(topic_id, card.front),
        translate_math(card.front),
        f"{translate_math(card.back)} {citation}",
        " ".join(_sanitize_tag(tag) for tag in card.tags),
    )
    return "\t".join(quote_field(field) for field in fields)


def _citation(lecture_id: str, anchor: SourceAnchor) -> str:
    citation = f"[{lecture_id} · {format_clock(anchor.start_s)}"
    if anchor.slides is not None:
        if anchor.slides.start == anchor.slides.end:
            citation += f" · slide {anchor.slides.start}"
        else:
            citation += f" · slides {anchor.slides.start}–{anchor.slides.end}"
    return citation + "]"


def _sanitize_tag(tag: str) -> str:
    return re.sub(r"\s+", "_", tag)
