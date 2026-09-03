"""``MarkdownRenderer`` against the hand-written ``week01.md`` (P3-02).

The byte-equality test *is* the Phase 3 done-criterion (plan §6): the expected file is
the format spec, transcribed by hand from ``tests/fixtures/notes/week01.py``. The
ad-hoc weeks are the render-side analogue of P2-01's ad-hoc decks: small in-memory
``NoteWeek``s for cases the fixture cannot show.
"""

from __future__ import annotations

from pathlib import Path

from lecturenotes.model import (
    Equation,
    Figure,
    MediaAsset,
    Node,
    NoteLecture,
    NoteWeek,
    SlideRange,
    SourceAnchor,
    SourceRef,
    Table,
    Topic,
)
from lecturenotes.render.base import RenderOptions, RenderResult
from lecturenotes.render.markdown import MarkdownRenderer

EXPECTED_MD = Path(__file__).resolve().parents[1] / "fixtures" / "notes" / "week01.md"

HAND_WRITTEN = (
    "the expected markdown is hand-written; if the format changed on purpose, edit "
    "tests/fixtures/notes/week01.md deliberately — do not regenerate it from the code "
    "under test."
)


def _render(week: NoteWeek) -> RenderResult:
    return MarkdownRenderer().render(week, RenderOptions())


def _week(
    body: list[Node],
    *,
    slides: tuple[int, int] | None = (1, 1),
    assets: list[MediaAsset] | None = None,
) -> NoteWeek:
    """A single-lecture, single-topic week with no optional sections."""
    return NoteWeek(
        id="adhoc-w01",
        course="ADHOC",
        week_number=1,
        lectures=[
            NoteLecture(
                id="lec01",
                title="Ad-hoc lecture",
                overview="One topic, no optional sections.",
                objectives=[],
                source=SourceRef(),
                topics=[
                    Topic(
                        id="lec01:s01-01:t000",
                        heading="Only topic",
                        anchor=SourceAnchor(
                            start_s=0.0,
                            end_s=60.0,
                            slides=SlideRange(start=slides[0], end=slides[1])
                            if slides
                            else None,
                        ),
                        body=body,
                    )
                ],
                assets=assets or [],
            )
        ],
    )


def _text(week: NoteWeek) -> str:
    result = _render(week)
    assert len(result.documents) == 1
    return result.documents[0].text


# --- the done-gate ----------------------------------------------------------------------


def test_week01_renders_to_the_hand_written_markdown(week01: NoteWeek) -> None:
    result = _render(week01)
    assert len(result.documents) == 1
    document = result.documents[0]
    assert document.name == "cs-rl-101-w01.md"
    expected = EXPECTED_MD.read_bytes().decode("utf-8")
    assert document.text == expected, HAND_WRITTEN


def test_week01_manifest_is_exactly_the_referenced_asset(week01: NoteWeek) -> None:
    result = _render(week01)
    assert [asset.id for asset in result.assets] == ["fig-value-iteration-convergence"]


# --- ad-hoc weeks -----------------------------------------------------------------------


def test_pipe_in_table_cell_is_escaped() -> None:
    table = Table(header=["expr"], rows=[["a | b"]])
    assert r"| a \| b |" in _text(_week([table]))


def test_figure_with_no_alt_renders_empty_brackets() -> None:
    asset = MediaAsset(id="fig-x", media_type="image/png", source="x.png", alt=None)
    text = _text(_week([Figure(asset_id="fig-x")], assets=[asset]))
    assert "![](assets/fig-x.png)" in text


def test_figure_with_no_caption_has_no_italic_line() -> None:
    asset = MediaAsset(id="fig-x", media_type="image/png", source="x.png", alt="a plot")
    text = _text(_week([Figure(asset_id="fig-x", caption=None)], assets=[asset]))
    assert "![a plot](assets/fig-x.png)" in text
    assert "*" not in text.split("![a plot](assets/fig-x.png)", 1)[1].splitlines()[0]


def test_equation_label_is_not_rendered() -> None:
    unlabelled = _text(_week([Equation(latex=r"e = mc^2")]))
    labelled = _text(_week([Equation(latex=r"e = mc^2", label="mass-energy")]))
    assert labelled == unlabelled
    assert "mass-energy" not in labelled


def test_empty_optional_sections_are_omitted() -> None:
    text = _text(_week([Equation(latex="x")]))
    assert "**Objectives**" not in text
    assert "### Glossary" not in text
    assert "### Open questions" not in text


def test_slideless_topic_has_no_slide_in_anchor() -> None:
    text = _text(_week([Equation(latex="x")], slides=None))
    assert "[0:00–1:00]" in text
    assert "slide" not in text.split("[0:00–1:00]", 1)[1].splitlines()[0]


def test_output_ends_with_one_newline_and_has_no_carriage_returns() -> None:
    text = _text(_week([Equation(latex="x")]))
    assert text.endswith("\n")
    assert not text.endswith("\n\n")
    assert "\r" not in text
