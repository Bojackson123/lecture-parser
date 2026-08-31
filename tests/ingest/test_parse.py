"""P1-01: VTT/SRT parsing and tag stripping (plan §3 stage 1, first function).

Fixture-driven tests are named after rows of the captions table in
``tests/fixtures/README.md``; the rest pin down the structural rules the ticket states.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from lecturenotes.ingest.captions import (
    CaptionParseError,
    Cue,
    Segment,
    format_timestamp,
    parse_srt,
    parse_vtt,
    strip_tags,
)

CUE_COUNT = 20
BOM = "\ufeff"

CUE_11_RAW = (
    "<00:04:32.000><c>back</c><00:04:32.400><c>to</c><00:04:32.700><c>the</c>"
    "<00:04:33.200><c>slides.</c> this is the bellman equation, and it is the heart of "
    "the whole course."
)
CUE_11_CLEAN = (
    "back to the slides. this is the bellman equation, and it is the heart of the whole course."
)


@pytest.fixture(scope="module")
def vtt_cues(vtt_text: str) -> list[Cue]:
    return parse_vtt(vtt_text)


@pytest.fixture(scope="module")
def srt_cues(srt_text: str) -> list[Cue]:
    return parse_srt(srt_text)


# --- the fixture, row by row -------------------------------------------------------


def test_vtt_parses_exactly_20_cues(vtt_cues: list[Cue]) -> None:
    assert len(vtt_cues) == CUE_COUNT


def test_srt_parses_exactly_20_cues(srt_cues: list[Cue]) -> None:
    assert len(srt_cues) == CUE_COUNT


def test_vtt_and_srt_parse_to_the_same_cues(vtt_cues: list[Cue], srt_cues: list[Cue]) -> None:
    """The invariant ``tests/fixtures/README.md`` states — the headline test."""
    assert vtt_cues == srt_cues


def test_header_and_note_block_are_not_cues(vtt_cues: list[Cue]) -> None:
    assert vtt_cues[0].start_s == 1.0
    for cue in vtt_cues:
        for line in cue.lines:
            assert "WEBVTT" not in line
            assert "lecturenotes fixture" not in line


def test_cue_01_voice_tag_stripped_and_two_lines(vtt_cues: list[Cue]) -> None:
    cue = vtt_cues[0]
    assert (cue.start_s, cue.end_s) == (1.0, 26.0)
    assert len(cue.lines) == 2
    assert cue.lines[0].startswith("welcome back everyone")
    assert cue.lines[0].endswith("sequential decision making.")


def test_cue_11_inline_timing_tags_without_whitespace(vtt_cues: list[Cue]) -> None:
    assert vtt_cues[10].lines[0].startswith("back to the slides. this is the bellman equation")
    assert vtt_cues[10].lines == (CUE_11_CLEAN,)


def test_cue_12_italic_tag_stripped_word_kept(vtt_cues: list[Cue], srt_cues: list[Cue]) -> None:
    for cues in (vtt_cues, srt_cues):
        assert "the expected value" in cues[11].lines[0]
        assert "<i>" not in cues[11].lines[0]


def test_cue_13_and_14_inline_timing_tags(vtt_cues: list[Cue]) -> None:
    assert vtt_cues[12].lines[0].startswith("the bellman equation is recursive")
    assert vtt_cues[13].lines[0].startswith("write it down properly")
    assert "this will be on the exam" in vtt_cues[13].lines[0]


def test_cue_17_multi_line_cue_keeps_both_lines(vtt_cues: list[Cue]) -> None:
    assert len(vtt_cues[16].lines) == 2


def test_cue_20_timing_and_apostrophe(vtt_cues: list[Cue]) -> None:
    cue = vtt_cues[-1]
    assert (cue.start_s, cue.end_s) == (520.0, 545.0)
    assert cue.lines[0].startswith("that's it for today")


def test_no_parsed_line_contains_markup(vtt_cues: list[Cue]) -> None:
    for cue in vtt_cues:
        for line in cue.lines:
            assert "<" not in line and ">" not in line
            assert line == line.strip()
            assert "  " not in line


def test_rolling_repetition_is_left_in_place(vtt_cues: list[Cue]) -> None:
    """Dedupe is P1-02's job; this ticket must hand the repeats over intact."""
    for prev, cur in zip(vtt_cues[:6], vtt_cues[1:6], strict=False):
        assert prev.lines[-1] == cur.lines[0]


# --- strip_tags --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        pytest.param(CUE_11_RAW, CUE_11_CLEAN, id="cue-11 timing tags, no whitespace"),
        pytest.param("<c.colorE5E5E5> word</c>", "word", id="youtube: space inside <c>"),
        pytest.param(
            "<00:00:01.000><c>no</c><00:00:01.500><c>gap</c>", "no gap", id="timing tag -> space"
        ),
        pytest.param("<00:01.000>a<01:02:03.456>b", "a b", id="MM:SS and HH:MM:SS timing tags"),
        pytest.param("<b>bo</b>ld", "bold", id="styling tag mid-word -> nothing"),
        pytest.param("<v Lecturer>hi there</v>", "hi there", id="voice tag dropped"),
        pytest.param("<lang en><ruby>x<rt>y</rt></ruby></lang>", "xy", id="ruby/lang"),
        pytest.param("<i>a</i> <u>b</u> <c.x.y>c</c>", "a b c", id="i/u/c.class"),
        pytest.param("a &amp; b", "a & b", id="&amp;"),
        pytest.param("&lt;x&gt;&nbsp;it&#39;s", "<x> it's", id="&lt; &gt; &nbsp; &#39;"),
        pytest.param("a  b\tc\n d", "a b c d", id="whitespace run + tab"),
        pytest.param("  padded \t", "padded", id="ends stripped"),
        pytest.param("", "", id="empty"),
        pytest.param("<c></c>", "", id="only tags"),
    ],
)
def test_strip_tags_table(raw: str, clean: str) -> None:
    assert strip_tags(raw) == clean


def test_strip_tags_is_idempotent_on_fixture_cues(vtt_text: str) -> None:
    for line in vtt_text.splitlines():
        assert strip_tags(strip_tags(line)) == strip_tags(line)


def test_strip_tags_is_identity_on_plain_text() -> None:
    for text in ("", "plain", "already single-spaced text, with punctuation!", "a & b"):
        assert strip_tags(text) == text


# --- structure: what parses and what raises ------------------------------------------


def test_mm_ss_timestamps_parse() -> None:
    cues = parse_vtt("WEBVTT\n\n01:02.500 --> 01:03.000\nhi\n")
    assert cues == [Cue(start_s=62.5, end_s=63.0, lines=("hi",))]


def test_crlf_input_parses(vtt_text: str, srt_text: str, vtt_cues: list[Cue]) -> None:
    assert parse_vtt(vtt_text.replace("\n", "\r\n")) == vtt_cues
    assert parse_srt(srt_text.replace("\n", "\r\n")) == vtt_cues


def test_bom_prefixed_file_parses(vtt_text: str, srt_text: str, vtt_cues: list[Cue]) -> None:
    assert parse_vtt(BOM + vtt_text) == vtt_cues
    assert parse_srt(BOM + srt_text) == vtt_cues


def test_missing_webvtt_header_raises_line_1(srt_text: str) -> None:
    with pytest.raises(CaptionParseError) as excinfo:
        parse_vtt(srt_text)
    assert excinfo.value.line_no == 1
    assert str(excinfo.value).startswith("line 1: ")


def test_webvtt_header_may_carry_trailing_text_and_header_lines() -> None:
    text = "WEBVTT - lecture 1\nKind: captions\nLanguage: en\n\n00:00:00.000 --> 00:00:01.000\nhi\n"
    assert parse_vtt(text) == [Cue(start_s=0.0, end_s=1.0, lines=("hi",))]
    with pytest.raises(CaptionParseError):
        parse_vtt("WEBVTTX\n\n00:00:00.000 --> 00:00:01.000\nhi\n")


def test_malformed_timing_line_raises_with_line_no() -> None:
    with pytest.raises(CaptionParseError) as excinfo:
        parse_vtt("WEBVTT\n\n00:00:01.000 -> 00:00:02.000\nhi\n")
    assert excinfo.value.line_no == 3
    assert str(excinfo.value).startswith("line 3: expected a timing line, got '")

    with pytest.raises(CaptionParseError) as excinfo:
        parse_srt("1\n00:00:01,000 --> 00:00:02,000\nhi\n\n2\n00:00:03,000 --> oops\nbye\n")
    assert excinfo.value.line_no == 6


def test_srt_sequence_number_line_is_required_but_not_validated() -> None:
    cues = parse_srt("7\n00:00:01,000 --> 00:00:02,000\na\n\n3\n00:00:03,000 --> 00:00:04,000\nb\n")
    assert [c.lines for c in cues] == [("a",), ("b",)]
    with pytest.raises(CaptionParseError) as excinfo:
        parse_srt("00:00:01,000 --> 00:00:02,000\na\n")
    assert excinfo.value.line_no == 1


def test_srt_accepts_dot_milliseconds() -> None:
    assert parse_srt("1\n00:00:01.250 --> 00:00:02,000\na\n") == [
        Cue(start_s=1.25, end_s=2.0, lines=("a",))
    ]


def test_end_before_start_raises() -> None:
    with pytest.raises(CaptionParseError) as excinfo:
        parse_vtt("WEBVTT\n\n00:00:05.000 --> 00:00:04.000\nhi\n")
    assert excinfo.value.line_no == 3


def test_style_block_and_cue_identifier_are_skipped() -> None:
    text = (
        "WEBVTT\n\n"
        "STYLE\n::cue { color: red }\n\n"
        "REGION\nid:r1 width:40%\n\n"
        "NOTE a comment\nspanning two lines\n\n"
        "intro\n00:00:00.000 --> 00:00:01.000 align:start position:0%\nhello\n\n"
        "00:00:01.000 --> 00:00:02.000\nworld\n"
    )
    assert parse_vtt(text) == [
        Cue(start_s=0.0, end_s=1.0, lines=("hello",)),
        Cue(start_s=1.0, end_s=2.0, lines=("world",)),
    ]


def test_garbage_block_raises_at_its_first_line() -> None:
    with pytest.raises(CaptionParseError) as excinfo:
        parse_vtt("WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nhi\n\nnot a cue\nnor this\n")
    assert excinfo.value.line_no == 6


def test_cue_with_only_tags_is_dropped_and_empty_lines_removed() -> None:
    text = (
        "WEBVTT\n\n"
        "00:00:00.000 --> 00:00:01.000\n<c></c>\n<00:00:00.500>\n\n"
        "00:00:01.000 --> 00:00:02.000\n<c></c>\nkept\n \n"
    )
    assert parse_vtt(text) == [Cue(start_s=1.0, end_s=2.0, lines=("kept",))]


def test_no_cues_is_an_empty_list() -> None:
    assert parse_vtt("WEBVTT\n") == []
    assert parse_vtt("WEBVTT\n\nNOTE nothing here\n") == []
    assert parse_srt("") == []


# --- types and helpers -------------------------------------------------------------


def test_cue_validators() -> None:
    with pytest.raises(ValidationError):
        Cue(start_s=2.0, end_s=1.0, lines=("a",))
    with pytest.raises(ValidationError):
        Cue(start_s=-1.0, end_s=1.0, lines=("a",))
    with pytest.raises(ValidationError):
        Cue(start_s=0.0, end_s=1.0, lines=())
    assert Cue(start_s=1.0, end_s=1.0, lines=("a",)).lines == ("a",)


def test_segment_validators() -> None:
    with pytest.raises(ValidationError):
        Segment(start_s=2.0, end_s=1.0, text="a")
    with pytest.raises(ValidationError):
        Segment(start_s=0.0, end_s=1.0, text="")
    assert Segment(start_s=0.0, end_s=1.0, text="a").text == "a"


def test_cue_and_segment_are_frozen_and_forbid_extras() -> None:
    cue = Cue(start_s=0.0, end_s=1.0, lines=("a",))
    with pytest.raises(ValidationError):
        cue.start_s = 5.0  # type: ignore[misc]
    with pytest.raises(ValidationError):
        Cue.model_validate({"start_s": 0.0, "end_s": 1.0, "lines": ["a"], "speaker": "x"})
    with pytest.raises(ValidationError):
        Segment.model_validate({"start_s": 0.0, "end_s": 1.0, "text": "a", "extra": 1})


def test_caption_parse_error_is_a_value_error_with_line_no() -> None:
    err = CaptionParseError(12, "expected a timing line, got 'x'")
    assert isinstance(err, ValueError)
    assert err.line_no == 12
    assert str(err) == "line 12: expected a timing line, got 'x'"


@pytest.mark.parametrize(
    ("seconds", "sep", "expected"),
    [
        (0.0, ".", "00:00:00.000"),
        (1.0, ".", "00:00:01.000"),
        (62.5, ".", "00:01:02.500"),
        (3661.001, ".", "01:01:01.001"),
        (545.0, ",", "00:09:05,000"),
        (359999.999, ".", "99:59:59.999"),
    ],
)
def test_format_timestamp(seconds: float, sep: str, expected: str) -> None:
    assert format_timestamp(seconds, sep=sep) == expected
