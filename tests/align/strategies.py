"""Hypothesis strategies for the P4-02 boundary tests.

``ordered_segments`` builds transcript-shaped input for ``span_units``: segments in
non-decreasing ``start_s`` order whose neighbours strictly overlap, touch exactly, or
leave a gap — the three relations the unit rule must distinguish. Times are integers
so "touching" is exact, and the text is word salad because these tests never read it.

``windows_instances`` builds tiny exact instances for ``solve_windows``: 1-4 slides,
0-6 units, a 5-term alphabet and **integer** weights, so the brute-force optimum is
cheap and ties are real — the tie-break is part of the spec and must actually be
exercised (P4-02 decision).
"""

from __future__ import annotations

from hypothesis import strategies as st

from lecturenotes.ingest.captions import Segment

TERMS = ("alpha", "bravo", "carol", "delta", "echo")

_TEXT = st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", min_size=1, max_size=20)
_TERM_SET = st.frozensets(st.sampled_from(TERMS), max_size=len(TERMS))

WindowsInstance = tuple[list[frozenset[str]], list[frozenset[str]], dict[str, float]]


@st.composite
def ordered_segments(
    draw: st.DrawFn, *, overlaps: bool = True, max_size: int = 8
) -> list[Segment]:
    """Segments in transcript order; ``overlaps=False`` keeps every neighbour disjoint."""
    relations = ["overlap", "touch", "gap"] if overlaps else ["touch", "gap"]
    count = draw(st.integers(min_value=0, max_value=max_size))
    segments: list[Segment] = []
    start = draw(st.integers(min_value=0, max_value=10))
    for _ in range(count):
        if segments:
            previous = segments[-1]
            relation = draw(st.sampled_from(relations))
            if relation == "overlap":
                start = draw(
                    st.integers(min_value=int(previous.start_s), max_value=int(previous.end_s) - 1)
                )
            elif relation == "touch":
                start = int(previous.end_s)
            else:
                start = int(previous.end_s) + draw(st.integers(min_value=1, max_value=5))
        end = start + draw(st.integers(min_value=1, max_value=10))
        segments.append(Segment(start_s=float(start), end_s=float(end), text=draw(_TEXT)))
    return segments


@st.composite
def windows_instances(draw: st.DrawFn) -> WindowsInstance:
    """(slides, units, weights) small enough to brute-force, tie-rich by design."""
    slides = draw(st.lists(_TERM_SET, min_size=1, max_size=4))
    units = draw(st.lists(_TERM_SET, min_size=0, max_size=6))
    weights = {term: float(draw(st.integers(min_value=1, max_value=4))) for term in TERMS}
    return slides, units, weights
