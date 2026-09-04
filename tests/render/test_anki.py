"""``AnkiRenderer`` against the hand-written ``week01.anki.txt`` (P6-02).

The byte-equality test *is* the Phase 6 done-criterion (plan §6): the expected deck is
the format spec, transcribed by hand from ``tests/fixtures/notes/week01.py`` in P6-01.
The ad-hoc weeks are the render-side analogue of P3-02's: small in-memory ``NoteWeek``s
for the guid, quoting, tag and math cases the fixture cannot show (no field in it needs
TSV quoting).
"""

from __future__ import annotations

from pathlib import Path

from lecturenotes.model import (
    CardSeed,
    NoteLecture,
    NoteWeek,
    SlideRange,
    SourceAnchor,
    SourceRef,
    Topic,
)
from lecturenotes.render.anki import AnkiRenderer, card_guid, quote_field, translate_math
from lecturenotes.render.base import RenderOptions, RenderResult

EXPECTED_TXT = (
    Path(__file__).resolve().parents[1] / "fixtures" / "notes" / "week01.anki.txt"
)

HAND_WRITTEN = (
    "the expected deck is hand-written; if the format changed on purpose, edit "
    "tests/fixtures/notes/week01.anki.txt deliberately — do not regenerate it from the "
    "code under test."
)


def _render(week: NoteWeek) -> RenderResult:
    return AnkiRenderer().render(week, RenderOptions())


def _topic(
    topic_id: str,
    cards: list[CardSeed],
    *,
    start_s: float = 0.0,
    slides: tuple[int, int] | None = (1, 1),
) -> Topic:
    return Topic(
        id=topic_id,
        heading="Ad-hoc topic",
        anchor=SourceAnchor(
            start_s=start_s,
            end_s=start_s + 60.0,
            slides=SlideRange(start=slides[0], end=slides[1]) if slides else None,
        ),
        body=[],
        cards=cards,
    )


def _week(topics: list[Topic]) -> NoteWeek:
    """A single-lecture week; the deck shows only its cards."""
    return NoteWeek(
        id="adhoc-w01",
        course="ADHOC",
        week_number=1,
        lectures=[
            NoteLecture(
                id="lec01",
                title="Ad-hoc lecture",
                overview="Cards only.",
                objectives=[],
                source=SourceRef(),
                topics=topics,
            )
        ],
    )


def _card(front: str = "Front?", back: str = "Back.", tags: list[str] | None = None) -> CardSeed:
    return CardSeed(front=front, back=back, tags=tags or [])


def _text(week: NoteWeek) -> str:
    result = _render(week)
    assert len(result.documents) == 1
    return result.documents[0].text


def _rows(week: NoteWeek) -> list[str]:
    """Data rows, for tests whose fields embed no newline."""
    return [line for line in _text(week).splitlines() if not line.startswith("#")]


# --- the done-gate ----------------------------------------------------------------------


def test_week01_renders_to_the_hand_written_deck(week01: NoteWeek) -> None:
    result = _render(week01)
    assert len(result.documents) == 1
    document = result.documents[0]
    assert document.name == "cs-rl-101-w01.txt"
    expected = EXPECTED_TXT.read_bytes().decode("utf-8")
    assert document.text == expected, HAND_WRITTEN


def test_week01_manifest_is_empty(week01: NoteWeek) -> None:
    # lec01 owns an asset, but cards reference no figures — the emitter copies nothing.
    assert _render(week01).assets == ()


# --- guids ------------------------------------------------------------------------------


def test_two_renders_produce_identical_guids() -> None:
    week = _week([_topic("lec01:s1-1", [_card("A?"), _card("B?")])])
    first = [row.split("\t")[0] for row in _rows(week)]
    second = [row.split("\t")[0] for row in _rows(week)]
    assert first == second


def test_guids_distinct_across_topics_and_fronts() -> None:
    # Same front under different topics, different fronts under one topic: 4 guids.
    week = _week(
        [
            _topic("lec01:s1-1", [_card("Same front?"), _card("Other front?")]),
            _topic("lec01:s2-2", [_card("Same front?"), _card("Other front?")], start_s=60.0),
        ]
    )
    guids = [row.split("\t")[0] for row in _rows(week)]
    assert len(guids) == 4
    assert len(set(guids)) == 4


def test_card_guid_hashes_the_raw_front_before_math_translation() -> None:
    assert card_guid("lec01:s1-1", "State $V(s)$.") != card_guid("lec01:s1-1", r"State \(V(s)\).")


# --- quoting ----------------------------------------------------------------------------


def test_front_containing_tab_is_quoted() -> None:
    week = _week([_topic("lec01:s1-1", [_card(front="a\tb")])])
    assert '\t"a\tb"\t' in _text(week)


def test_back_containing_newline_is_quoted() -> None:
    week = _week([_topic("lec01:s1-1", [_card(back="line one\nline two")])])
    assert '"line one\nline two [lec01 · 0:00 · slide 1]"' in _text(week)


def test_field_containing_double_quote_is_quoted_with_inner_quotes_doubled() -> None:
    week = _week([_topic("lec01:s1-1", [_card(front='say "hi"')])])
    assert '"say ""hi"""' in _text(week)


def test_field_needing_no_quoting_is_written_bare() -> None:
    week = _week([_topic("lec01:s1-1", [_card(front="plain front?")])])
    assert "\tplain front?\t" in _text(week)
    assert '"' not in _text(week)


# --- tags -------------------------------------------------------------------------------


def test_tag_containing_whitespace_is_sanitized_with_underscore() -> None:
    week = _week([_topic("lec01:s1-1", [_card(tags=["exam topic"])])])
    (row,) = _rows(week)
    assert row.split("\t")[3] == "exam_topic"


def test_card_with_empty_tags_still_has_its_fourth_column() -> None:
    week = _week([_topic("lec01:s1-1", [_card()])])
    (row,) = _rows(week)
    assert row.count("\t") == 3
    assert row.endswith("\t")


# --- math -------------------------------------------------------------------------------


def test_paired_dollars_become_parens() -> None:
    assert translate_math("$x$") == r"\(x\)"


def test_two_pairs_in_one_field_both_translate() -> None:
    week = _week([_topic("lec01:s1-1", [_card(back="$a$ and $b$")])])
    assert r"\(a\) and \(b\) [lec01 · 0:00 · slide 1]" in _text(week)


def test_unpaired_dollar_passes_through_untouched() -> None:
    week = _week([_topic("lec01:s1-1", [_card(back="costs $5")])])
    assert "costs $5 [lec01 · 0:00 · slide 1]" in _text(week)


def test_translation_applies_to_front_and_back_but_never_the_citation() -> None:
    week = _week([_topic("lec01:s1-1", [_card(front="State $V(s)$.", back="It is $x$.")])])
    (row,) = _rows(week)
    fields = row.split("\t")
    assert fields[1] == r"State \(V(s)\)."
    assert fields[2] == r"It is \(x\). [lec01 · 0:00 · slide 1]"


def test_quote_field_leaves_math_backslashes_alone() -> None:
    assert quote_field(r"\(x\)") == r"\(x\)"


# --- rows and citations -----------------------------------------------------------------


def test_cardless_topic_contributes_no_rows() -> None:
    # The ≥ 1-card guarantee is generation's (P6-01); the renderer never invents content.
    week = _week(
        [
            _topic("lec01:s1-1", [_card()]),
            _topic("lec01:s2-2", [], start_s=60.0),
        ]
    )
    assert len(_rows(week)) == 1


def test_week_of_cardless_topics_renders_headers_only() -> None:
    week = _week([_topic("lec01:s1-1", [])])
    assert _text(week) == (
        "#separator:tab\n"
        "#html:false\n"
        "#notetype:Basic\n"
        "#deck:ADHOC::Week 1\n"
        "#guid column:1\n"
        "#tags column:4\n"
    )


def test_slideless_topic_citation_has_no_slide() -> None:
    week = _week([_topic("lec01:t000", [_card()], slides=None)])
    (row,) = _rows(week)
    assert "[lec01 · 0:00]" in row
    assert "slide" not in row


def test_single_slide_citation() -> None:
    week = _week([_topic("lec01:s2-2", [_card()], slides=(2, 2))])
    assert "[lec01 · 0:00 · slide 2]" in _rows(week)[0]


def test_slide_range_citation_uses_en_dash() -> None:
    week = _week([_topic("lec01:s2-3", [_card()], slides=(2, 3))])
    assert "[lec01 · 0:00 · slides 2–3]" in _rows(week)[0]


# --- shape ------------------------------------------------------------------------------


def test_output_ends_with_one_newline_and_has_no_carriage_returns() -> None:
    text = _text(_week([_topic("lec01:s1-1", [_card()])]))
    assert text.endswith("\n")
    assert not text.endswith("\n\n")
    assert "\r" not in text
