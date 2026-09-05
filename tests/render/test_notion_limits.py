"""The four §2.3 Notion limits, enforced inside ``render/notion.py`` (P7-03).

Hypothesis proves the caps for arbitrary weeks — the plan §10 treatment for pure
stages — and ad-hoc weeks pin each boundary exactly. The format itself is pinned
elsewhere: ``week01.notion.json`` byte-equality lives in ``test_notion.py`` and this
ticket changes no fixture, which is the point of the P7-01 format/limits split.

The limits, and how over-limit input degrades (P7-03 decisions):

- a text run longer than 2,000 characters splits at exactly 2,000 — dumb on purpose;
  Notion joins adjacent runs seamlessly — and never inside an inline ``equation`` run;
- bullet descendants below the second level flatten pre-order into their depth-2
  parent's array (nesting ≤ 2 levels);
- children arrays chunk at 100: items past the hundredth are promoted to the parent's
  level right after it, dedented but never dropped;
- payloads split at top-level block boundaries when the next block would push past
  1,000 nested-inclusive blocks or 100 top-level elements — a block and its children
  always travel together.

Caps the plan doesn't name (rows per table, equation-expression size) stay out of
scope, so the strategies keep tables and expressions small.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from hypothesis import given
from hypothesis import strategies as st

from lecturenotes.model import (
    BulletItem,
    BulletList,
    Callout,
    CalloutKind,
    CodeBlock,
    Definition,
    Equation,
    Figure,
    MediaAsset,
    Node,
    NoteLecture,
    NoteWeek,
    Prose,
    Quote,
    SlideRange,
    SourceAnchor,
    SourceRef,
    Table,
    Topic,
)
from lecturenotes.render.base import RenderOptions
from lecturenotes.render.notion import NotionRenderer

RICH_TEXT_CAP = 2000
CHILDREN_CAP = 100
PAYLOAD_CAP = 1000

_Block = dict[str, Any]

_ASSET = MediaAsset(id="img-aaaaaaaaaaaaaaaa", media_type="image/png", source="media/a.png")


# --- strategies -------------------------------------------------------------------------
# The IR has no hypothesis strategies before this file (the P3-01 degrade tests are
# fixture-based), so the week strategies live here. "$" is excluded from plain text so
# generated pairs can't merge into one long accidental equation expression.

_PLAIN = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="$"),
    max_size=40,
)
_LONG = st.integers(min_value=1, max_value=4500).map("x".__mul__)
_MATH = st.text(alphabet="abgxyz\\{}^_+= ", min_size=1, max_size=12).map(lambda e: f"${e}$")

CONTENT_TEXT = st.lists(st.one_of(_PLAIN, _LONG, _MATH), max_size=4).map("".join)
_TEXT = st.one_of(_PLAIN, _LONG)

_LEAF = st.builds(BulletItem, text=_PLAIN, children=st.just([]))
BULLET_ITEMS: st.SearchStrategy[BulletItem] = st.recursive(
    _LEAF,
    lambda inner: st.builds(
        BulletItem,
        text=_PLAIN,
        # The wide branch exists so the 100-children chunk fires under hypothesis too,
        # not only in the ad-hoc boundary cases.
        children=st.one_of(
            st.lists(inner, min_size=1, max_size=3),
            st.lists(_LEAF, min_size=1, max_size=120),
        ),
    ),
    max_leaves=8,
)


@st.composite
def _tables(draw: st.DrawFn) -> Table:
    width = draw(st.integers(min_value=1, max_value=3))
    row = st.lists(_PLAIN, min_size=width, max_size=width)
    return Table(header=draw(row), rows=draw(st.lists(row, max_size=3)))


_NODES: st.SearchStrategy[Node] = st.one_of(
    st.builds(Prose, text=CONTENT_TEXT),
    st.builds(BulletList, items=st.lists(BULLET_ITEMS, min_size=1, max_size=3)),
    st.builds(Definition, term=_TEXT, definition=CONTENT_TEXT),
    st.builds(Equation, latex=_PLAIN, label=st.none() | _PLAIN),
    st.builds(CodeBlock, code=_TEXT, language=st.none() | st.just("python")),
    st.builds(Callout, kind=st.sampled_from(CalloutKind), text=CONTENT_TEXT),
    st.builds(Figure, asset_id=st.just(_ASSET.id), caption=st.none() | _TEXT),
    _tables(),
    st.builds(Quote, text=CONTENT_TEXT, attribution=st.none() | _TEXT),
)


@st.composite
def _topics(draw: st.DrawFn) -> Topic:
    start = draw(st.integers(min_value=0, max_value=9000))
    end = start + draw(st.integers(min_value=0, max_value=600))
    span = draw(st.none() | st.tuples(st.integers(1, 30), st.integers(0, 5)))
    slides = None if span is None else SlideRange(start=span[0], end=span[0] + span[1])
    return Topic(
        id="lec01:s1-1",
        heading=draw(_TEXT),
        anchor=SourceAnchor(start_s=float(start), end_s=float(end), slides=slides),
        body=draw(st.lists(_NODES, max_size=4)),
    )


@st.composite
def _lectures(draw: st.DrawFn, index: int) -> NoteLecture:
    return NoteLecture(
        id=f"lec{index:02d}",
        title=draw(_TEXT),
        overview=draw(_TEXT),
        # Up to 120 objectives so the 100-element top-level chunk fires under hypothesis.
        objectives=draw(st.lists(_PLAIN, max_size=120)),
        source=SourceRef(),
        topics=draw(st.lists(_topics(), max_size=3)),
        glossary=draw(st.lists(st.builds(Definition, term=_PLAIN, definition=_PLAIN), max_size=2)),
        open_questions=draw(st.lists(_PLAIN, max_size=2)),
        assets=[_ASSET],
    )


@st.composite
def weeks(draw: st.DrawFn) -> NoteWeek:
    count = draw(st.integers(min_value=0, max_value=2))
    return NoteWeek(
        id="hyp-w01",
        course="HYP",
        week_number=1,
        lectures=[draw(_lectures(i)) for i in range(count)],
    )


# --- builders and walkers ---------------------------------------------------------------


def _payloads(week: NoteWeek) -> list[list[_Block]]:
    result = NotionRenderer().render(week, RenderOptions())
    document = json.loads(result.documents[0].text)
    payloads: list[list[_Block]] = document["payloads"]
    return payloads


def _children(block: _Block) -> list[_Block]:
    children: list[_Block] = block[block["type"]].get("children", [])
    return children


def _all_blocks(blocks: list[_Block]) -> Iterator[_Block]:
    for block in blocks:
        yield block
        yield from _all_blocks(_children(block))


def _rich_text_arrays(block: _Block) -> Iterator[list[dict[str, Any]]]:
    payload = block[block["type"]]
    if "rich_text" in payload:
        yield payload["rich_text"]
    if "caption" in payload:
        yield payload["caption"]
    if "cells" in payload:
        yield from payload["cells"]


def _nested_count(block: _Block) -> int:
    return 1 + sum(_nested_count(child) for child in _children(block))


def _flat_text(runs: list[dict[str, Any]]) -> str:
    """Reconstruct source text: text-run contents, equation runs back to ``$…$``.

    Reconstruction equalling the source proves both halves of the preservation
    property at once — split pieces concatenate back, and no split landed inside an
    inline equation (a severed pair would reconstruct with extra ``$``s).
    """
    return "".join(
        f"${run['equation']['expression']}$" if run["type"] == "equation"
        else run["text"]["content"]
        for run in runs
    )


def _week(topics: list[Topic], objectives: list[str] | None = None) -> NoteWeek:
    return NoteWeek(
        id="adhoc-w01",
        course="ADHOC",
        week_number=1,
        lectures=[
            NoteLecture(
                id="lec01",
                title="Ad-hoc lecture",
                overview="One topic.",
                objectives=objectives or [],
                source=SourceRef(),
                topics=topics,
            )
        ],
    )


def _topic(body: list[Node]) -> Topic:
    return Topic(
        id="lec01:s1-1",
        heading="Ad-hoc topic",
        anchor=SourceAnchor(start_s=0.0, end_s=60.0, slides=SlideRange(start=1, end=1)),
        body=body,
    )


def _body(week: NoteWeek) -> list[_Block]:
    """The one topic's blocks: after heading_1, overview and the topic heading_2."""
    payloads = _payloads(week)
    assert len(payloads) == 1
    return payloads[0][3:]


def _preorder(items: list[BulletItem]) -> list[str]:
    out: list[str] = []
    for item in items:
        out.append(item.text)
        out.extend(_preorder(item.children))
    return out


def _bullet_texts(payloads: list[list[_Block]]) -> list[str]:
    """Every bulleted_list_item's text in reading order: parent, children, then rest."""
    return [
        _flat_text(block["bulleted_list_item"]["rich_text"])
        for payload in payloads
        for block in _all_blocks(payload)
        if block["type"] == "bulleted_list_item"
    ]


# --- the four caps, for arbitrary weeks -------------------------------------------------


@given(weeks())
def test_every_rich_text_run_is_at_most_2000_characters(week: NoteWeek) -> None:
    for payload in _payloads(week):
        for block in _all_blocks(payload):
            for runs in _rich_text_arrays(block):
                for run in runs:
                    if run["type"] == "text":
                        assert len(run["text"]["content"]) <= RICH_TEXT_CAP


@given(weeks())
def test_every_children_array_and_payload_top_level_has_at_most_100_elements(
    week: NoteWeek,
) -> None:
    for payload in _payloads(week):
        assert len(payload) <= CHILDREN_CAP
        for block in _all_blocks(payload):
            assert len(_children(block)) <= CHILDREN_CAP


@given(weeks())
def test_every_payload_has_at_most_1000_blocks_counting_nested(week: NoteWeek) -> None:
    for payload in _payloads(week):
        assert sum(_nested_count(block) for block in payload) <= PAYLOAD_CAP


@given(weeks())
def test_no_block_nests_deeper_than_two_levels(week: NoteWeek) -> None:
    # Level 1 is a payload's top-level array, level 2 its children; nothing below.
    for payload in _payloads(week):
        for block in payload:
            for child in _children(block):
                assert "children" not in child[child["type"]]


# --- text is preserved, for arbitrary input ---------------------------------------------


@given(CONTENT_TEXT)
def test_split_runs_concatenate_back_to_the_source_text(text: str) -> None:
    week = _week([_topic([Prose(text=text)])])
    (block,) = _body(week)
    assert _flat_text(block["paragraph"]["rich_text"]) == text


@given(st.lists(BULLET_ITEMS, min_size=1, max_size=3))
def test_flattening_loses_no_bullet_text(items: list[BulletItem]) -> None:
    week = _week([_topic([BulletList(items=items)])])
    assert _bullet_texts(_payloads(week)) == _preorder(items)


# --- boundary cases: rich text ----------------------------------------------------------


def test_2000_char_prose_stays_one_run() -> None:
    week = _week([_topic([Prose(text="x" * RICH_TEXT_CAP)])])
    (block,) = _body(week)
    runs = block["paragraph"]["rich_text"]
    assert [len(run["text"]["content"]) for run in runs] == [RICH_TEXT_CAP]


def test_2001_char_prose_splits_into_two_runs() -> None:
    text = "x" * (RICH_TEXT_CAP + 1)
    week = _week([_topic([Prose(text=text)])])
    (block,) = _body(week)
    runs = block["paragraph"]["rich_text"]
    assert [len(run["text"]["content"]) for run in runs] == [RICH_TEXT_CAP, 1]
    assert _flat_text(runs) == text


def test_a_split_never_lands_inside_an_inline_equation_run() -> None:
    # 1,999 chars, then a pair that would straddle the 2,000 mark if runs were split
    # on the raw string: the equation run stays atomic, only text runs split.
    text = "a" * 1999 + "$xy$" + "b" * 2001
    week = _week([_topic([Prose(text=text)])])
    (block,) = _body(week)
    runs = block["paragraph"]["rich_text"]
    assert [run["type"] for run in runs] == ["text", "equation", "text", "text"]
    assert runs[1]["equation"]["expression"] == "xy"
    assert [len(r["text"]["content"]) for r in runs if r["type"] == "text"] == [1999, 2000, 1]
    assert _flat_text(runs) == text


def test_split_runs_keep_their_annotations() -> None:
    term = "t" * (RICH_TEXT_CAP + 500)
    week = _week([_topic([Definition(term=term, definition="d")])])
    (block,) = _body(week)
    runs = block["paragraph"]["rich_text"]
    assert [run.get("annotations") for run in runs[:2]] == [{"bold": True}, {"bold": True}]
    assert _flat_text(runs[:2]) == term


# --- boundary cases: children arrays and nesting ----------------------------------------


def test_100_children_stay_one_array() -> None:
    items = [BulletItem(text="p", children=[BulletItem(text=f"c{i}") for i in range(100)])]
    week = _week([_topic([BulletList(items=items)])])
    (block,) = _body(week)
    assert len(_children(block)) == 100


def test_a_101st_child_is_promoted_to_the_parent_level() -> None:
    items = [BulletItem(text="p", children=[BulletItem(text=f"c{i}") for i in range(101)])]
    week = _week([_topic([BulletList(items=items)])])
    parent, promoted = _body(week)
    assert len(_children(parent)) == 100
    assert _children(parent)[99]["bulleted_list_item"]["rich_text"][0]["text"]["content"] == "c99"
    assert promoted["bulleted_list_item"]["rich_text"][0]["text"]["content"] == "c100"
    assert "children" not in promoted["bulleted_list_item"]


def test_a_3_deep_list_flattens_its_third_level_into_its_depth_2_parent_pre_order() -> None:
    items = [
        BulletItem(
            text="A",
            children=[
                BulletItem(text="B", children=[BulletItem(text="C"), BulletItem(text="D")]),
                BulletItem(text="E"),
            ],
        )
    ]
    week = _week([_topic([BulletList(items=items)])])
    (block,) = _body(week)
    children = _children(block)
    assert [c["bulleted_list_item"]["rich_text"][0]["text"]["content"] for c in children] == [
        "B",
        "C",
        "D",
        "E",
    ]
    assert all("children" not in c["bulleted_list_item"] for c in children)


# --- boundary cases: payload chunking ---------------------------------------------------
# A lecture's chrome before its objectives is 3 top-level blocks (heading_1, overview,
# the bold "Objectives" label), so 97 objectives put the top level at exactly 100.


def test_100_top_level_blocks_stay_one_payload() -> None:
    week = _week([], objectives=[f"o{i}" for i in range(97)])
    payloads = _payloads(week)
    assert [len(payload) for payload in payloads] == [100]


def test_a_101st_top_level_block_starts_a_second_payload() -> None:
    week = _week([], objectives=[f"o{i}" for i in range(98)])
    payloads = _payloads(week)
    assert [len(payload) for payload in payloads] == [100, 1]
    last = payloads[1][0]["bulleted_list_item"]["rich_text"][0]["text"]["content"]
    assert last == "o97"


def test_a_body_past_1000_blocks_splits_into_a_second_payload_at_a_block_boundary() -> None:
    # 80 items of 12 children weigh 13 blocks each; with 3 blocks of chrome the 77th
    # item would hit 1,004, so the payload closes at 991 and 4 items carry over.
    items = [
        BulletItem(text=f"i{i}", children=[BulletItem(text=f"i{i}.{j}") for j in range(12)])
        for i in range(80)
    ]
    week = _week([_topic([BulletList(items=items)])])
    payloads = _payloads(week)
    assert [sum(_nested_count(block) for block in payload) for payload in payloads] == [991, 52]
    # Every tree crossed whole: each top item keeps its 12 children on both sides.
    tops = [b for payload in payloads for b in payload if b["type"] == "bulleted_list_item"]
    assert [len(_children(top)) for top in tops] == [12] * 80
    assert _bullet_texts(payloads) == _preorder(items)


# --- the fixture sits below every limit -------------------------------------------------


def test_week01_still_renders_to_a_single_payload(week01: NoteWeek) -> None:
    # Byte-equality with the hand-written fixture is pinned in test_notion.py; this
    # only documents why P7-03 could not change it: week01 is far below every cap.
    payloads = _payloads(week01)
    assert len(payloads) == 1
    assert len(payloads[0]) <= CHILDREN_CAP
    assert sum(_nested_count(block) for block in payloads[0]) <= PAYLOAD_CAP
