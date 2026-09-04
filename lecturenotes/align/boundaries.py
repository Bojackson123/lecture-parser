"""Monotonic boundaries (plan §4.1): units of shared speech time, then the window DP.

Two pure functions — the constraint half of alignment; the scores they consume are
``align/scoring.py`` (P4-01), and gap carving / ``align_lecture`` arrive in P4-03:

    span_units(segments)                   → ((int, ...), ...)   index groups
    solve_windows(slides, units, weights)  → (int, ...)          per-unit window index

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
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from lecturenotes.align.scoring import score
from lecturenotes.ingest.captions import Segment

__all__ = ["solve_windows", "span_units"]


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
