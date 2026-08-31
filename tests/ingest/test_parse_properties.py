"""P1-01 property tests (plan §10: property-based tests for the pure stages).

The VTT/SRT *renderers* live here, not in the package — the package never writes
captions; they exist only to state "render → parse is the identity".
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from lecturenotes.ingest.captions import Cue, format_timestamp, parse_srt, parse_vtt, strip_tags
from tests.ingest.strategies import LINE, MAX_MS, WORD_CHARS, cue_lists

BOM = "\ufeff"


def render_vtt(cues: list[Cue]) -> str:
    blocks = [
        f"{format_timestamp(c.start_s)} --> {format_timestamp(c.end_s)}\n" + "\n".join(c.lines)
        for c in cues
    ]
    return "WEBVTT\n\n" + "\n\n".join(blocks) + "\n"


def render_srt(cues: list[Cue]) -> str:
    blocks = [
        f"{i}\n{format_timestamp(c.start_s, sep=',')} --> {format_timestamp(c.end_s, sep=',')}\n"
        + "\n".join(c.lines)
        for i, c in enumerate(cues, start=1)
    ]
    return "\n\n".join(blocks) + "\n"


@given(cue_lists())
def test_vtt_render_parse_round_trip(cues: list[Cue]) -> None:
    assert parse_vtt(render_vtt(cues)) == cues


@given(cue_lists())
def test_srt_render_parse_round_trip(cues: list[Cue]) -> None:
    assert parse_srt(render_srt(cues)) == cues


@given(cue_lists())
@settings(max_examples=25)
def test_crlf_and_bom_do_not_change_the_round_trip(cues: list[Cue]) -> None:
    assert parse_vtt(BOM + render_vtt(cues).replace("\n", "\r\n")) == cues
    assert parse_srt(BOM + render_srt(cues).replace("\n", "\r\n")) == cues


# --- strip_tags --------------------------------------------------------------------


def _timing_tag(ms: int, short: bool) -> str:
    stamp = format_timestamp(ms / 1000)
    return f"<{stamp[3:] if short else stamp}>"


_TIMING_TAG = st.builds(_timing_tag, st.integers(0, MAX_MS), st.booleans())
_NAMED_TAG = st.sampled_from(
    [
        "<c>", "</c>", "<v Lecturer>", "<v Some Name>", "</v>", "<i>", "</i>", "<b>", "</b>",
        "<u>", "</u>", "<ruby>", "</ruby>", "<rt>", "</rt>", "<lang en>", "<lang en-GB>",
        "</lang>",
    ]
)  # fmt: skip
_CLASS_TAG = st.text(alphabet=WORD_CHARS, min_size=1, max_size=10).map(lambda s: f"<c.{s}>")
_TAG = st.one_of(_TIMING_TAG, _NAMED_TAG, _CLASS_TAG)
# Arbitrary text — any whitespace, any printable — but no bare markup characters.
_FREE_TEXT = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="<>&")
)
_TAGGY_TEXT = st.lists(st.one_of(_FREE_TEXT, _TAG), max_size=12).map("".join)


@given(_TAGGY_TEXT)
def test_strip_tags_is_idempotent(text: str) -> None:
    once = strip_tags(text)
    assert strip_tags(once) == once


@given(_TAGGY_TEXT)
def test_strip_tags_output_is_normalised_and_markup_free(text: str) -> None:
    out = strip_tags(text)
    assert out == out.strip()
    assert "  " not in out
    assert "<" not in out and ">" not in out


@given(LINE)
def test_strip_tags_is_identity_on_clean_text(line: str) -> None:
    assert strip_tags(line) == line
