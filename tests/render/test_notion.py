"""``NotionRenderer`` against the hand-written ``week01.notion.json`` (P7-02).

The byte-equality test is half the Phase 7 done-criterion (plan §6): the expected
payload is the format spec, hand-written in P7-01. The ad-hoc weeks are the
render-side analogue of P3-02's and P6-02's: small in-memory ``NoteWeek``s for the
math-dialect, callout, citation and nesting cases the fixture pins only once each.
The four §2.3 limits are P7-03's; nothing here renders an over-limit week.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from lecturenotes.model import (
    BulletItem,
    BulletList,
    Callout,
    CalloutKind,
    Definition,
    Figure,
    MediaAsset,
    Node,
    NoteLecture,
    NoteWeek,
    Prose,
    SlideRange,
    SourceAnchor,
    SourceRef,
    Table,
    Topic,
)
from lecturenotes.render.base import RenderOptions, RenderResult
from lecturenotes.render.notion import CALLOUT_STYLE, NotionRenderer, citation, rich_text

EXPECTED_JSON = (
    Path(__file__).resolve().parents[1] / "fixtures" / "notes" / "week01.notion.json"
)

HAND_WRITTEN = (
    "the expected payload is hand-written; if the format changed on purpose, edit "
    "tests/fixtures/notes/week01.notion.json deliberately — do not regenerate it from "
    "the code under test."
)


def _render(week: NoteWeek) -> RenderResult:
    return NotionRenderer().render(week, RenderOptions())


def _topic(
    body: list[Node],
    *,
    heading: str = "Ad-hoc topic",
    topic_id: str = "lec01:s1-1",
    start_s: float = 0.0,
    slides: tuple[int, int] | None = (1, 1),
) -> Topic:
    return Topic(
        id=topic_id,
        heading=heading,
        anchor=SourceAnchor(
            start_s=start_s,
            end_s=start_s + 60.0,
            slides=SlideRange(start=slides[0], end=slides[1]) if slides else None,
        ),
        body=body,
    )


def _week(topics: list[Topic], assets: list[MediaAsset] | None = None) -> NoteWeek:
    """A single-lecture week with no objectives, glossary or open questions."""
    return NoteWeek(
        id="adhoc-w01",
        course="ADHOC",
        week_number=1,
        lectures=[
            NoteLecture(
                id="lec01",
                title="Ad-hoc lecture",
                overview="One topic.",
                objectives=[],
                source=SourceRef(),
                topics=topics,
                assets=assets or [],
            )
        ],
    )


def _payload(week: NoteWeek) -> list[dict[str, Any]]:
    result = _render(week)
    assert len(result.documents) == 1
    document = json.loads(result.documents[0].text)
    assert sorted(document) == ["page", "payloads"]
    assert len(document["payloads"]) == 1
    blocks: list[dict[str, Any]] = document["payloads"][0]
    return blocks


def _body(week: NoteWeek) -> list[dict[str, Any]]:
    """The blocks of an ad-hoc week's one topic: after heading_1, overview, heading_2."""
    return _payload(week)[3:]


def _text_run(content: str) -> dict[str, Any]:
    return {"type": "text", "text": {"content": content}}


def _equation_run(expression: str) -> dict[str, Any]:
    return {"type": "equation", "equation": {"expression": expression}}


# --- the done-gate ----------------------------------------------------------------------


def test_week01_renders_to_the_hand_written_payload(week01: NoteWeek) -> None:
    result = _render(week01)
    assert len(result.documents) == 1
    document = result.documents[0]
    assert document.name == "cs-rl-101-w01.notion.json"
    expected = EXPECTED_JSON.read_bytes().decode("utf-8")
    assert document.text == expected, HAND_WRITTEN


def test_week01_manifest_is_the_one_referenced_asset(week01: NoteWeek) -> None:
    result = _render(week01)
    assert [asset.id for asset in result.assets] == ["fig-value-iteration-convergence"]


def test_week_with_no_figures_has_empty_manifest_even_when_a_lecture_owns_assets() -> None:
    asset = MediaAsset(id="img-unused", media_type="image/png", source="media/unused.png")
    week = _week([_topic([Prose(text="no figures here")])], assets=[asset])
    assert _render(week).assets == ()


# --- math -------------------------------------------------------------------------------


def test_paired_dollars_become_one_inline_equation_run_flanked_by_text() -> None:
    week = _week([_topic([Prose(text="before $x$ after")])])
    (block,) = _body(week)
    assert block["paragraph"]["rich_text"] == [
        _text_run("before "),
        _equation_run("x"),
        _text_run(" after"),
    ]


def test_two_pairs_in_one_text_both_translate() -> None:
    week = _week([_topic([Prose(text="$a$ and $b$")])])
    (block,) = _body(week)
    assert block["paragraph"]["rich_text"] == [
        _equation_run("a"),
        _text_run(" and "),
        _equation_run("b"),
    ]


def test_unpaired_dollar_passes_through_as_text() -> None:
    week = _week([_topic([Prose(text="costs $5")])])
    (block,) = _body(week)
    assert block["paragraph"]["rich_text"] == [_text_run("costs $5")]


def test_translation_applies_in_bullet_text() -> None:
    week = _week([_topic([BulletList(items=[BulletItem(text="value $V(s)$")])])])
    (block,) = _body(week)
    assert block["bulleted_list_item"]["rich_text"] == [
        _text_run("value "),
        _equation_run("V(s)"),
    ]


def test_translation_applies_in_table_cells() -> None:
    week = _week([_topic([Table(header=["Term"], rows=[[r"$\gamma$"]])])])
    (block,) = _body(week)
    header_row, data_row = block["table"]["children"]
    assert header_row["table_row"]["cells"] == [[_text_run("Term")]]
    assert data_row["table_row"]["cells"] == [[_equation_run(r"\gamma")]]


def test_translation_applies_in_definition_text_after_the_bold_term() -> None:
    week = _week([_topic([Definition(term="Gamma", definition="$\\gamma$ discounts")])])
    (block,) = _body(week)
    runs = block["paragraph"]["rich_text"]
    assert runs == [
        {"type": "text", "text": {"content": "Gamma"}, "annotations": {"bold": True}},
        _text_run(": "),
        _equation_run("\\gamma"),
        _text_run(" discounts"),
    ]


def test_heading_and_citation_are_never_translated() -> None:
    week = _week([_topic([], heading="Value of $x$")])
    heading = _payload(week)[2]["heading_2"]["rich_text"]
    assert heading[0] == _text_run("Value of $x$")
    assert heading[1]["type"] == "text"


# --- callouts ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kind", "emoji", "color"),
    [
        (CalloutKind.EXAM, "📝", "red_background"),
        (CalloutKind.PITFALL, "⚠️", "yellow_background"),
        (CalloutKind.UNCERTAIN, "❓", "gray_background"),
        (CalloutKind.ASIDE, "💡", "blue_background"),
    ],
)
def test_each_callout_kind_maps_to_its_pinned_icon_and_colour(
    kind: CalloutKind, emoji: str, color: str
) -> None:
    week = _week([_topic([Callout(kind=kind, text="flagged")])])
    label = {
        "type": "text",
        "text": {"content": kind.value},
        "annotations": {"bold": True},
    }
    (block,) = _body(week)
    assert block["callout"]["icon"] == {"type": "emoji", "emoji": emoji}
    assert block["callout"]["color"] == color
    # The markdown renderer's ``> **EXAM** — text``, in Notion runs: the icon alone
    # doesn't say what a kind means, so a bold label leads the text.
    assert block["callout"]["rich_text"] == [label, _text_run(" — "), _text_run("flagged")]


def test_callout_style_covers_exactly_the_kind_enum() -> None:
    # Exhaustive over the enum on purpose: a fifth kind fails here first.
    assert set(CALLOUT_STYLE) == set(CalloutKind)


# --- citations --------------------------------------------------------------------------


def test_slideless_topic_citation_is_clock_only() -> None:
    week = _week([_topic([], topic_id="lec01:t000", slides=None)])
    run = _payload(week)[2]["heading_2"]["rich_text"][1]
    assert run["text"]["content"] == "  0:00"
    assert run["annotations"] == {"color": "gray"}


def test_single_slide_citation() -> None:
    week = _week([_topic([], topic_id="lec01:s2-2", slides=(2, 2))])
    run = _payload(week)[2]["heading_2"]["rich_text"][1]
    assert run["text"]["content"] == "  0:00 · slide 2"


def test_slide_range_citation_uses_en_dash() -> None:
    week = _week([_topic([], topic_id="lec01:s2-3", slides=(2, 3))])
    run = _payload(week)[2]["heading_2"]["rich_text"][1]
    assert run["text"]["content"] == "  0:00 · slides 2–3"


def test_citation_builder_matches_the_rendered_run() -> None:
    anchor = SourceAnchor(start_s=181.0, end_s=240.0, slides=SlideRange(start=2, end=3))
    assert citation(anchor) == "  3:01 · slides 2–3"


# --- nesting ----------------------------------------------------------------------------


def test_nested_bullet_list_produces_children_on_the_parent_item() -> None:
    week = _week(
        [
            _topic(
                [
                    BulletList(
                        items=[
                            BulletItem(text="parent", children=[BulletItem(text="child")])
                        ]
                    )
                ]
            )
        ]
    )
    (block,) = _body(week)
    assert block["bulleted_list_item"]["children"] == [
        {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [_text_run("child")]}}
    ]


def test_flat_bullet_list_item_has_no_children_key() -> None:
    week = _week([_topic([BulletList(items=[BulletItem(text="flat")])])])
    (block,) = _body(week)
    assert "children" not in block["bulleted_list_item"]


# --- figures ----------------------------------------------------------------------------


def test_captionless_figure_omits_the_caption_key_and_joins_the_manifest() -> None:
    asset = MediaAsset(id="img-x", media_type="image/png", source="media/img-x.png")
    week = _week([_topic([Figure(asset_id="img-x")])], assets=[asset])
    (block,) = _body(week)
    assert block["image"] == {
        "type": "asset_placeholder",
        "asset_placeholder": {"asset_id": "img-x"},
    }
    assert [a.id for a in _render(week).assets] == ["img-x"]


# --- helpers ----------------------------------------------------------------------------


def test_rich_text_of_empty_string_is_no_runs() -> None:
    assert rich_text("") == []


# --- shape ------------------------------------------------------------------------------


def test_two_renders_are_equal(week01: NoteWeek) -> None:
    assert _render(week01) == _render(week01)


def test_output_has_no_carriage_returns_and_one_trailing_newline(week01: NoteWeek) -> None:
    text = _render(week01).documents[0].text
    assert "\r" not in text
    assert text.endswith("\n")
    assert not text.endswith("\n\n")
