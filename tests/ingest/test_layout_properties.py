"""P2-02 property tests for ``layout_page`` (plan §10: the pure layout step).

Synthetic pages come from ``tests/ingest/strategies.py`` in PDF user space (``y`` grows
upward; "top to bottom" is descending ``y``). Every strategy shuffles its spans before
handing them over: the content-stream order is precisely what must *not* leak into the
result — the fixture's row-by-row drawing is one adversarial order, hypothesis supplies
the rest.
"""

from __future__ import annotations

from collections import Counter

from hypothesis import given
from hypothesis import strategies as st

from lecturenotes.ingest.slides import PageLayout, Span, TextBlock, clean_line, layout_page
from tests.ingest.strategies import (
    PAGE_HEIGHT,
    PAGE_WIDTH,
    OneColumn,
    TitledPage,
    TwoColumns,
    lined_spans,
    one_column_spans,
    spans,
    titled_spans,
    two_column_spans,
    two_line_titled_spans,
    uniform_spans,
)


def _layout(page: list[Span]) -> PageLayout:
    return layout_page(page, page_width=PAGE_WIDTH, page_height=PAGE_HEIGHT)


def _lines(layout: PageLayout) -> list[str]:
    return [line for block in layout.blocks for line in block.lines]


# --- columns -----------------------------------------------------------------------


@given(two_column_spans())
def test_two_columns_read_left_top_to_bottom_then_right(page: TwoColumns) -> None:
    layout = _layout(page.spans)
    assert layout.title is None
    assert layout.blocks == (TextBlock(lines=tuple(page.left)), TextBlock(lines=tuple(page.right)))


@given(one_column_spans())
def test_indents_up_to_60pt_stay_one_block_in_descending_y_order(page: OneColumn) -> None:
    layout = _layout(page.spans)
    assert layout.title is None
    assert layout.blocks == (TextBlock(lines=tuple(page.lines)),)


def test_the_fixture_shape_interleaved_rows_split_into_two_columns() -> None:
    """Slide 2 of the deck in miniature: rows drawn L1 R1 L2 R2 at shared baselines."""
    page = [
        Span(x=60, y=515, size=28, text="The Bellman Equation"),
        Span(x=60, y=445, size=13, text="Equation"),
        Span(x=450, y=445, size=13, text="Intuition"),
        Span(x=60, y=405, size=13, text="V(s) = ..."),
        Span(x=450, y=405, size=13, text="Value = ..."),
    ]
    assert _layout(page) == PageLayout(
        title="The Bellman Equation",
        blocks=(
            TextBlock(lines=("Equation", "V(s) = ...")),
            TextBlock(lines=("Intuition", "Value = ...")),
        ),
    )


# --- nothing lost, nothing invented, nothing order-dependent -----------------------


@given(lined_spans())
def test_no_text_lost_when_every_span_is_its_own_row(page: list[Span]) -> None:
    expected = Counter(clean_line(s.text) for s in page)
    layout = _layout(page)
    title = [layout.title] if layout.title is not None else []
    assert Counter(title + _lines(layout)) == expected


@given(spans())
def test_no_words_lost_or_invented_on_any_page(page: list[Span]) -> None:
    """Rows may join spans and titles may join rows, but the words are the words."""
    expected = Counter(word for s in page for word in s.text.split())
    layout = _layout(page)
    produced = [layout.title or "", *_lines(layout)]
    assert Counter(word for line in produced for word in line.split()) == expected


@given(spans())
def test_every_line_is_clean_and_non_empty(page: list[Span]) -> None:
    layout = _layout(page)
    for line in ([layout.title] if layout.title is not None else []) + _lines(layout):
        assert line and clean_line(line) == line


@given(spans(), st.data())
def test_any_permutation_of_the_spans_gives_an_equal_layout(
    page: list[Span], data: st.DataObject
) -> None:
    shuffled = data.draw(st.permutations(page))
    assert _layout(shuffled) == _layout(page)


# --- the title ---------------------------------------------------------------------


@given(uniform_spans())
def test_uniform_size_gives_no_title(page: list[Span]) -> None:
    assert _layout(page).title is None


@given(titled_spans())
def test_a_larger_topmost_span_is_the_title(page: TitledPage) -> None:
    layout = _layout(page.spans)
    assert layout.title == page.title
    assert len(_lines(layout)) == len(page.spans) - 1


@given(two_line_titled_spans())
def test_two_rows_at_the_largest_size_join_as_one_title(page: TitledPage) -> None:
    layout = _layout(page.spans)
    assert layout.title == page.title
    assert len(_lines(layout)) == len(page.spans) - 2


def test_an_empty_page_has_no_title_and_no_blocks() -> None:
    assert _layout([]) == PageLayout(title=None, blocks=())
    assert _layout([Span(x=10, y=10, size=12, text="  ")]) == PageLayout(title=None, blocks=())


def test_a_page_with_a_single_row_is_a_title() -> None:
    """A section slide: nothing but one line, so that line names the slide."""
    assert _layout([Span(x=200, y=300, size=32, text="Part II")]) == PageLayout(
        title="Part II", blocks=()
    )
