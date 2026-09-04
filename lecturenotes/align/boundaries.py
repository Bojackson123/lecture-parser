"""Monotonic boundaries (plan §4.1): units, the window DP, gap carving, ``Chunk``.

The constraint half of alignment; the scores it consumes are ``align/scoring.py``
(P4-01). ``align_lecture`` is the only entrypoint — mirroring ``ingest_captions`` and
``ingest_slides``, the two pure stages are exported for debugging and tests, not for
re-composition elsewhere:

    span_units(segments)                   → ((int, ...), ...)   index groups
    solve_windows(slides, units, weights)  → (int, ...)          per-unit window index
    align_lecture(deck, segments)          → [Chunk]             stage 4 (plan §3)

Decisions (P4-02):

- **Units before windows, never split afterwards.** A segment's span is the union of
  its cues' spans (P1-03), so overlapping spans identify speech from the same moment;
  a window boundary between them would produce an anchor pointing at words that belong
  to the other side. Cue-mates (identical spans) and rolling-merge products glue;
  touching at a boundary is not overlapping.
- **Distinct-union window scoring is load-bearing.** A shared term counts once per
  window no matter how many units repeat it: a lone generic word is worthless next to
  a window that already has it (the fixture's segment-4 "equation" must not advance
  the slide), while a *new* rare word still moves boundaries.
- **Ties advance as late as possible** — the lexicographically largest boundary tuple.
  All-zero stretches (board work) stay with the slide on screen, which matches how
  lectures work and gives P4-03 maximal runs to carve gaps from.
- **Windows may be empty**: a slide the lecturer skipped gets no units; the empty
  union shares nothing and scores 0 by construction, so the DP never forces coverage.
- **The brute-force property is the specification** (see
  ``tests/align/test_boundaries_properties.py``); this O(S·U²) DP is merely an
  implementation, safe to replace if a real course is slow — profile first (§10).

Decisions (P4-03):

- **Gaps need silence brackets *and* minutes, not just missing vocabulary.** Speech
  that merely lacks slide words is everywhere and belongs to the slide on screen; what
  distinguishes board work is the lecturer *leaving* — a pause at each end and a span
  measured in minutes (§4.1). The off-slide test is ``< 2`` shared terms, not
  ``score == 0``: one coincidental content word must not disqualify a gap.
- **Gap chunks are content, not noise.** ``slides=None`` is the §4.1 gap signal:
  Phase 5 generates notes from them like any other chunk and Phase 9 uses them as the
  trigger for frame pulls. Nothing may drop them.
- **Hidden slides are excluded before the DP**, not after: a hidden slide must not
  soak up units it can never own. Numbers stay untouched (P2 invariant), so a chunk
  can never cite a slide the reader can't find.
- **Chunk spans may overlap and do not partition time** (the P1-03 span-union rule);
  the chunks *partition the segments*, which is the plan §10 property.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict, model_validator

from lecturenotes.align.scoring import score, slide_terms, term_weights, tokenize
from lecturenotes.ingest.captions import Segment
from lecturenotes.ingest.slides import Deck
from lecturenotes.model.source import SlideRange

__all__ = ["Chunk", "align_lecture", "solve_windows", "span_units"]


class Chunk(BaseModel):
    """One slide's worth of speech, or one gap (the output of stage 4, plan §3).

    ``slides is None`` **is** the §4.1 gap signal — minutes of speech with no matching
    slide content (board work, live coding). v1 always emits width-1 ranges; the type
    is ``SlideRange`` now so the §9 grouping decision won't churn it. ``start_s`` and
    ``end_s`` are properties, not fields, so the JSON stays two-key and cannot
    disagree with the segments.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    slides: SlideRange | None
    segments: tuple[Segment, ...]

    @model_validator(mode="after")
    def _non_empty(self) -> Chunk:
        if not self.segments:
            raise ValueError("a chunk needs at least one segment")
        return self

    @property
    def start_s(self) -> float:
        """``min`` over members — spans are unions and may overlap (P1-03)."""
        return min(segment.start_s for segment in self.segments)

    @property
    def end_s(self) -> float:
        """``max`` over members, not the last one's end."""
        return max(segment.end_s for segment in self.segments)


def span_units(segments: Sequence[Segment]) -> tuple[tuple[int, ...], ...]:
    """Group consecutive segments whose spans strictly overlap.

    Walks the segments in order: consecutive segments merge into the same unit while
    ``next.start_s < prev.end_s``; segments that merely touch at a boundary stay
    separate. Returns 0-based index groups, consecutive and exhaustive. ``segments``
    must be in transcript order (non-decreasing ``start_s``) — ``ingest_captions``
    output already is — and a decrease raises ``ValueError``.
    """
    groups: list[tuple[int, ...]] = []
    current: list[int] = []
    for index, segment in enumerate(segments):
        if not current:
            current = [index]
            continue
        previous = segments[index - 1]
        if segment.start_s < previous.start_s:
            raise ValueError(
                f"segments out of transcript order: start_s drops from "
                f"{previous.start_s} to {segment.start_s} at index {index}"
            )
        if segment.start_s < previous.end_s:
            current.append(index)
        else:
            groups.append(tuple(current))
            current = [index]
    if current:
        groups.append(tuple(current))
    return tuple(groups)


def solve_windows(
    slides: Sequence[frozenset[str]],
    units: Sequence[frozenset[str]],
    weights: Mapping[str, float],
) -> tuple[int, ...]:
    """Partition ``units`` into one contiguous, possibly-empty window per slide.

    Chooses cut positions ``0 = b_0 ≤ b_1 ≤ … ≤ b_S = U`` (window ``j`` gets
    ``units[b_j : b_j+1]``) maximising the summed P4-01 ``score`` of each slide
    against its window's *distinct* term union; among optima, returns the assignment
    with the lexicographically largest ``(b_1, …, b_S-1)`` — every window opens as
    late as the optimum allows. Returns per-unit window indices. ``ValueError`` when
    there are units but no slides: the no-deck case is ``align_lecture``'s branch
    (P4-03), not a silent guess here.
    """
    if not slides:
        if units:
            raise ValueError("units but no slides: alignment needs a deck to align to")
        return ()
    slide_count, unit_count = len(slides), len(units)

    # best[j][u]: the best total for units[u:] over slides[j:]. Every window must
    # close by U (the cuts end at b_S = U), so the only finite base case is
    # best[S][U]; cut[j][u] records the b_{j+1} chosen at (j, u), ties to the
    # largest v — greedy reconstruction from (0, 0) then yields the
    # lexicographically largest boundary tuple, because suffix optima do not
    # depend on the prefix.
    unreachable = -math.inf
    best = [[unreachable] * (unit_count + 1) for _ in range(slide_count + 1)]
    best[slide_count][unit_count] = 0.0
    cut = [[0] * (unit_count + 1) for _ in range(slide_count)]
    for j in range(slide_count - 1, -1, -1):
        for u in range(unit_count, -1, -1):
            window: set[str] = set()
            for v in range(u, unit_count + 1):
                if v > u:
                    window |= units[v - 1]
                candidate = score(slides[j], frozenset(window), weights) + best[j + 1][v]
                if candidate >= best[j][u]:
                    best[j][u] = candidate
                    cut[j][u] = v

    assignment: list[int] = []
    u = 0
    for j in range(slide_count):
        v = cut[j][u]
        assignment.extend([j] * (v - u))
        u = v
    return tuple(assignment)


def _carve_gaps(
    unit_starts: Sequence[float],
    unit_ends: Sequence[float],
    unit_terms: Sequence[frozenset[str]],
    slides: Sequence[frozenset[str]],
    assignment: Sequence[int],
    *,
    min_gap_s: float,
    min_silence_s: float,
) -> set[int]:
    """Unit positions to carve out as gaps.

    Within each window a unit is *off-slide* iff it shares fewer than 2 distinct
    scoring terms with the window's slide. Each maximal off-slide run is split at
    silences — adjacent units whose spans are ``min_silence_s`` or more apart (spans
    may overlap, so the distance can be negative; that is never silence) — and a piece
    is carved only when it is silence-bracketed on both sides (the lecture's very
    start and end count as brackets) and spans at least ``min_gap_s``.
    """

    def bracketed_before(k: int) -> bool:
        return k == 0 or unit_starts[k] - unit_ends[k - 1] >= min_silence_s

    def bracketed_after(k: int) -> bool:
        return k == len(assignment) - 1 or unit_starts[k + 1] - unit_ends[k] >= min_silence_s

    off_slide = [
        len(unit_terms[k] & slides[assignment[k]]) < 2 for k in range(len(assignment))
    ]
    pieces: list[list[int]] = []
    for k, off in enumerate(off_slide):
        if not off:
            continue
        extends_piece = (
            pieces
            and pieces[-1][-1] == k - 1
            and assignment[k] == assignment[k - 1]
            and not bracketed_before(k)
        )
        if extends_piece:
            pieces[-1].append(k)
        else:
            pieces.append([k])

    gaps: set[int] = set()
    for piece in pieces:
        span = max(unit_ends[p] for p in piece) - min(unit_starts[p] for p in piece)
        if bracketed_before(piece[0]) and bracketed_after(piece[-1]) and span >= min_gap_s:
            gaps.update(piece)
    return gaps


def align_lecture(
    deck: Deck,
    segments: Sequence[Segment],
    *,
    min_gap_s: float = 60.0,
    min_silence_s: float = 1.0,
) -> list[Chunk]:
    """``Deck`` + ``[Segment]`` → ``[Chunk]`` — stage 4 (plan §3), pure and monotonic.

    Candidates are the non-hidden slides in order (skip ``hidden``, never renumber);
    with no segments the result is ``[]``, and with no candidates it is one ungated
    gap chunk holding every segment — a captions-only lecture is still alignable.
    Otherwise the P4-02 window DP assigns every span unit to a slide, gap carving
    marks the silence-bracketed, ``min_gap_s``-long off-slide pieces, and consecutive
    same-fate units within a window group into one chunk (``SlideRange(n, n)`` for the
    window's slide, ``None`` for a carved piece) — a carved middle splits a window
    into slide / gap / slide, so the same range may appear twice and monotonicity is
    non-decreasing, not strict. Empty windows produce no chunk. The chunks partition
    the segments in order (plan §10); their spans may overlap and have holes where the
    silences live.
    """
    if not segments:
        return []
    candidates = [slide for slide in deck.slides if not slide.hidden]
    if not candidates:
        return [Chunk(slides=None, segments=tuple(segments))]

    units = span_units(segments)
    unit_terms = [
        frozenset().union(*(tokenize(segments[i].text) for i in unit)) for unit in units
    ]
    slides = [slide_terms(slide) for slide in candidates]
    assignment = solve_windows(slides, unit_terms, term_weights(segments))
    gaps = _carve_gaps(
        [min(segments[i].start_s for i in unit) for unit in units],
        [max(segments[i].end_s for i in unit) for unit in units],
        unit_terms,
        slides,
        assignment,
        min_gap_s=min_gap_s,
        min_silence_s=min_silence_s,
    )

    chunks: list[Chunk] = []
    fates = [(assignment[k], k in gaps) for k in range(len(units))]
    start = 0
    for k in range(1, len(units) + 1):
        if k == len(units) or fates[k] != fates[start]:
            window, is_gap = fates[start]
            number = candidates[window].number
            chunks.append(
                Chunk(
                    slides=None if is_gap else SlideRange(start=number, end=number),
                    segments=tuple(
                        segments[i] for unit in units[start:k] for i in unit
                    ),
                )
            )
            start = k
    return chunks
