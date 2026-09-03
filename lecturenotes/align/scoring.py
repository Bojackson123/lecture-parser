"""Slide↔speech scoring (plan §4.1, approach 2): rare terms pin slides to speech.

Three pure functions with no notion of order or boundaries — the monotonic solve
that consumes them is ``align/boundaries.py`` (P4-02/P4-03):

    tokenize(text)          → frozenset[str]      what counts as a term
    term_weights(segments)  → dict[str, float]    transcript rarity, ln(N/df)
    slide_terms(slide)      → frozenset[str]      title + block lines, never notes
    score(slide, speech, w) → float               weight of the distinct shared terms

Decisions (P4-01):

- **Rarity over the transcript, not the deck.** Slides are terse, so deck-side IDF
  separates nothing; it is transcript ubiquity that makes "equation" generic and
  "bellman" pinning. ``ln(N/df)`` needs no smoothing: a shared term has df ≥ 1 by
  construction, and a term in every segment weighs exactly 0.
- **A stopword list *and* IDF, not either alone.** IDF alone leaves "the" a small
  positive weight, which would break "board work scores zero against every slide" —
  the property P4-03's gap detection rests on.
- **No stemming** ("rewards" ≠ "reward"): the fixture scores stay strong without it,
  and a stemmer would add a dependency and surprising matches.
- **Speaker notes never score.** Notes are PPTX-only, so scoring them would make
  alignment differ between two exports of the same deck.
- **Sets, not counts.** Term *presence* is the signal; counts would double-pay a term
  the lecturer repeats, and P4-02's distinct-union window scoring continues the shape.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence

from lecturenotes.ingest.captions import Segment
from lecturenotes.ingest.slides import Slide

__all__ = [
    "STOPWORDS",
    "score",
    "slide_terms",
    "term_weights",
    "tokenize",
]

# Common English function words that survive the length-3 cut. The fixture tests are
# the arbiter of membership: "how much would you pay" (segment 7) must share nothing
# with slide 1's "how much later rewards count", the recap (segment 22) must share
# exactly {transition, function} with slide 1 (hence "know"), and the board-work gap
# must have one stray slide hit, not two (hence "about", segment 10 vs slide 1).
STOPWORDS: frozenset[str] = frozenset(
    """
    the and for you that this with from how much would when where what which will
    can all any one out get into over than then they them there here also just very
    some such not but was has have had are its his her she him who now
    about know
    """.split()
)

_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> frozenset[str]:
    """Lower-cased alphanumeric runs, minus short tokens and stopwords.

    ``max_a`` → ``max``/``a`` and ``V(s')`` → ``v``/``s``, then everything shorter
    than 3 characters and every stopword is dropped. A set, because everything
    downstream (weights, distinct shared terms) is set-shaped.
    """
    return frozenset(
        token
        for token in _TOKEN.findall(text.lower())
        if len(token) >= 3 and token not in STOPWORDS
    )


def term_weights(segments: Sequence[Segment]) -> dict[str, float]:
    """Transcript-rarity weights: ``ln(N / df(t))`` over the segments.

    ``df(t)`` is the number of segments whose ``tokenize`` contains ``t``, so a term
    in every segment weighs exactly 0 and the rarest terms weigh the most.
    """
    df: Counter[str] = Counter()
    for segment in segments:
        df.update(tokenize(segment.text))
    return {term: math.log(len(segments) / count) for term, count in df.items()}


def slide_terms(slide: Slide) -> frozenset[str]:
    """The slide's visible vocabulary: title (if any) plus every block line.

    Never the speaker notes and never image data — notes are PPTX-only, and scoring
    them would make alignment differ between two exports of the same deck.
    """
    lines = [line for block in slide.blocks for line in block.lines]
    if slide.title is not None:
        lines.insert(0, slide.title)
    return tokenize(" ".join(lines))


def score(slide: frozenset[str], speech: frozenset[str], weights: Mapping[str, float]) -> float:
    """Sum of ``weights`` over the distinct shared terms ``slide & speech``.

    Terms missing from ``weights`` count 0: a slide-only term was never spoken and
    cannot be shared, but a caller's synthetic sets must not crash. Summed in sorted
    order so the float is reproducible across processes (set order is not).
    """
    return sum((weights.get(term, 0.0) for term in sorted(slide & speech)), 0.0)
