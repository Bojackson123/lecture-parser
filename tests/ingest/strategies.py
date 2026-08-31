"""Hypothesis strategies shared by the ``tests/ingest`` property modules.

Introduced in P1-01 (parse round trips); P1-02 builds its rolling-repeat corruption on
top of ``cue_lists``, and P1-03 swaps in a terminator-only alphabet for sentence merging.
P2-02 adds positioned text spans for the pure PDF layout step.
"""

from __future__ import annotations

import itertools
from typing import NamedTuple

from hypothesis import assume
from hypothesis import strategies as st

from lecturenotes.ingest.captions import Cue
from lecturenotes.ingest.slides import Span

MAX_MS = 99 * 3600 * 1000 + 59 * 60 * 1000 + 59 * 1000 + 999  # 99:59:59.999

# Non-whitespace, printable, no markup characters — and hence no "-->".
WORD_CHARS = st.characters(blacklist_categories=("Z", "C"), blacklist_characters="<>&")
WORD = st.text(alphabet=WORD_CHARS, min_size=1, max_size=12)
# Already normalised: single spaces, no leading/trailing whitespace.
LINE = st.lists(WORD, min_size=1, max_size=8).map(" ".join)


@st.composite
def cue_lists(draw: st.DrawFn, line: st.SearchStrategy[str] = LINE) -> list[Cue]:
    """1–30 cues with strictly increasing, non-overlapping spans and 1–3 clean lines each.

    ``line`` swaps the text strategy; P1-03 restricts it to letters and terminators.
    """
    n = draw(st.integers(min_value=1, max_value=30))
    # Strictly positive gaps, accumulated: start_i < end_i < start_{i+1}, well under MAX_MS.
    gaps = draw(st.lists(st.integers(1, 60_000), min_size=2 * n, max_size=2 * n))
    bounds = list(itertools.accumulate(gaps, initial=draw(st.integers(0, 60_000))))[1:]
    return [
        Cue(
            start_s=bounds[2 * i] / 1000,
            end_s=bounds[2 * i + 1] / 1000,
            lines=tuple(draw(st.lists(line, min_size=1, max_size=3))),
        )
        for i in range(n)
    ]


# --- P2-02: positioned text spans for layout_page ------------------------------------
#
# Pages are in PDF user space like ``Span`` itself: ``y`` grows upward, "top to bottom"
# is descending ``y``. Text is letters and single spaces, so ``clean_line`` is the
# identity on it and every expected value below can be spelled from the strategy's own
# output without calling the code under test. Where a strategy promises an exact
# layout, its rows are spaced so that no two of them can share a row (the row rule is
# ``0.5 × size``) and, for ``lined_spans``, so that no two can join as a two-line
# title (``1.5 × size``).

PAGE_WIDTH, PAGE_HEIGHT = 842.0, 595.0  # A4 landscape, like the fixture deck
MARGIN = 40.0

SPAN_WORD = st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=8)
SPAN_TEXT = st.lists(SPAN_WORD, min_size=1, max_size=6).map(" ".join)
BLANK_TEXT = st.sampled_from(["", " ", "  \t "])
BODY_SIZE = st.integers(min_value=10, max_value=20).map(float)
X = st.floats(min_value=MARGIN, max_value=PAGE_WIDTH - MARGIN)
INDENT = st.floats(min_value=0.0, max_value=60.0)  # a sub-bullet, never a new column


class OneColumn(NamedTuple):
    spans: list[Span]
    lines: list[str]


class TwoColumns(NamedTuple):
    spans: list[Span]
    left: list[str]
    right: list[str]


class TitledPage(NamedTuple):
    spans: list[Span]
    title: str


@st.composite
def spans(
    draw: st.DrawFn,
    *,
    min_spans: int = 1,
    max_spans: int = 20,
    size: st.SearchStrategy[float] = BODY_SIZE,
) -> list[Span]:
    """The general case: anywhere on the page, any sizes, some blank texts, any order."""
    n = draw(st.integers(min_value=min_spans, max_value=max_spans))
    y = st.floats(min_value=MARGIN, max_value=PAGE_HEIGHT - MARGIN)
    text = st.one_of(SPAN_TEXT, SPAN_TEXT, SPAN_TEXT, BLANK_TEXT)
    return [Span(x=draw(X), y=draw(y), size=draw(size), text=draw(text)) for _ in range(n)]


@st.composite
def row_ys(draw: st.DrawFn, n: int, *, min_gap: float, max_gap: float = 70.0) -> list[float]:
    """``n`` baselines top to bottom, consecutive ones ``min_gap``..``max_gap`` apart.

    ``n`` ≤ 8 keeps the whole stack inside the page for any ``max_gap`` ≤ 70.
    """
    gap = st.floats(min_value=min_gap, max_value=max_gap)
    gaps = draw(st.lists(gap, min_size=n - 1, max_size=n - 1))
    top = draw(st.floats(min_value=MARGIN + sum(gaps), max_value=PAGE_HEIGHT - MARGIN))
    return list(itertools.accumulate((-g for g in gaps), initial=top))


@st.composite
def lined_spans(
    draw: st.DrawFn,
    *,
    min_rows: int = 1,
    max_rows: int = 7,
    size: st.SearchStrategy[float] = BODY_SIZE,
    min_gap: float = 31.0,
) -> list[Span]:
    """One span per row, shuffled; rows > 1.5 × the largest body size (20) apart.

    So every span is exactly one output line: none can share a row or join a title.
    """
    n = draw(st.integers(min_value=min_rows, max_value=max_rows))
    ys = draw(row_ys(n, min_gap=min_gap))
    out = [Span(x=draw(X), y=y, size=draw(size), text=draw(SPAN_TEXT)) for y in ys]
    return draw(st.permutations(out))


@st.composite
def uniform_spans(draw: st.DrawFn) -> list[Span]:
    """Two or more rows, all at one size: nothing stands out, so nothing is a title."""
    return draw(lined_spans(min_rows=2, size=st.just(draw(BODY_SIZE))))


@st.composite
def one_column_spans(draw: st.DrawFn) -> OneColumn:
    """2–8 lines at one size, each indented ≤ 60 pt from the column's left edge."""
    size = draw(BODY_SIZE)
    n = draw(st.integers(min_value=2, max_value=8))  # one row alone would be a title
    lines = draw(st.lists(SPAN_TEXT, min_size=n, max_size=n))
    ys = draw(row_ys(n, min_gap=size + 1))
    left = draw(st.floats(min_value=MARGIN, max_value=400.0))
    out = [
        Span(x=left + draw(INDENT), y=y, size=size, text=line)
        for y, line in zip(ys, lines, strict=True)
    ]
    return OneColumn(draw(st.permutations(out)), lines)


@st.composite
def two_column_spans(draw: st.DrawFn) -> TwoColumns:
    """Left and right columns of 1–8 lines at one size, 250–500 pt apart, shuffled.

    Rows sit at shared baselines (the fixture's adversarial case: naive extraction
    interleaves the columns) or at independent ones.
    """
    size = draw(BODY_SIZE)
    n_left = draw(st.integers(min_value=1, max_value=8))
    n_right = draw(st.integers(min_value=1, max_value=8))
    left = draw(st.lists(SPAN_TEXT, min_size=n_left, max_size=n_left))
    right = draw(st.lists(SPAN_TEXT, min_size=n_right, max_size=n_right))
    x_left = draw(st.floats(min_value=40.0, max_value=120.0))
    x_right = x_left + draw(st.floats(min_value=250.0, max_value=500.0))
    ys_left = draw(row_ys(n_left, min_gap=size + 1))
    if n_left == n_right and draw(st.booleans()):
        ys_right = ys_left
    else:
        ys_right = draw(row_ys(n_right, min_gap=size + 1))
    # A page whose every span sits on one row is a title, by rule; that is not a
    # column layout, so only the one-line-each case has to keep its rows apart.
    assume(n_left + n_right > 2 or abs(ys_left[0] - ys_right[0]) > size)
    out = [
        Span(x=x_left + draw(INDENT), y=y, size=size, text=line)
        for y, line in zip(ys_left, left, strict=True)
    ] + [
        Span(x=x_right + draw(INDENT), y=y, size=size, text=line)
        for y, line in zip(ys_right, right, strict=True)
    ]
    return TwoColumns(draw(st.permutations(out)), left, right)


def _title_size(draw: st.DrawFn, body: list[Span]) -> float:
    """At least 1.2 × the largest body size — clear of the 1.15 threshold."""
    return max(s.size for s in body) * draw(st.floats(min_value=1.2, max_value=2.0))


@st.composite
def titled_spans(draw: st.DrawFn) -> TitledPage:
    """A body of 1–7 lines plus one larger span above it: that span is the title."""
    body = draw(lined_spans(max_rows=7))
    size = _title_size(draw, body)
    title = draw(SPAN_TEXT)
    y = max(s.y for s in body) + draw(st.floats(min_value=11.0, max_value=60.0))
    out = [*body, Span(x=draw(X), y=y, size=size, text=title)]
    return TitledPage(draw(st.permutations(out)), title)


@st.composite
def two_line_titled_spans(draw: st.DrawFn) -> TitledPage:
    """Two rows at the largest size, 0.6–1.4 × that size apart, above a body: one title."""
    body = draw(lined_spans(max_rows=6))
    size = _title_size(draw, body)
    first, second = draw(SPAN_TEXT), draw(SPAN_TEXT)
    y_second = max(s.y for s in body) + draw(st.floats(min_value=11.0, max_value=60.0))
    y_first = y_second + draw(st.floats(min_value=0.6 * size, max_value=1.4 * size))
    out = [
        *body,
        Span(x=draw(X), y=y_first, size=size, text=first),
        Span(x=draw(X), y=y_second, size=size, text=second),
    ]
    return TitledPage(draw(st.permutations(out)), f"{first} {second}")
