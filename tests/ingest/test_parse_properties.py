"""P1-01 property tests (plan §10: property-based tests for the pure stages).

The VTT/SRT *renderers* live here, not in the package — the package never writes
captions; they exist only to state "render → parse is the identity".
"""

from __future__ import annotations

import itertools

from hypothesis import given, settings
from hypothesis import strategies as st

from lecturenotes.ingest.captions import Cue, format_timestamp, parse_srt, parse_vtt, strip_tags

BOM = "\ufeff"
MAX_MS = 99 * 3600 * 1000 + 59 * 60 * 1000 + 59 * 1000 + 999  # 99:59:59.999

# Non-whitespace, printable, no markup characters — and hence no "-->".
_WORD_CHARS = st.characters(blacklist_categories=("Z", "C"), blacklist_characters="<>&")
_WORD = st.text(alphabet=_WORD_CHARS, min_size=1, max_size=12)
# Already normalised: single spaces, no leading/trailing whitespace.
_LINE = st.lists(_WORD, min_size=1, max_size=8).map(" ".join)


@st.composite
def cue_lists(draw: st.DrawFn) -> list[Cue]:
    """1–30 cues with strictly increasing, non-overlapping spans and 1–3 clean lines each."""
    n = draw(st.integers(min_value=1, max_value=30))
    # Strictly positive gaps, accumulated: start_i < end_i < start_{i+1}, well under MAX_MS.
    gaps = draw(st.lists(st.integers(1, 60_000), min_size=2 * n, max_size=2 * n))
    bounds = list(itertools.accumulate(gaps, initial=draw(st.integers(0, 60_000))))[1:]
    return [
        Cue(
            start_s=bounds[2 * i] / 1000,
            end_s=bounds[2 * i + 1] / 1000,
            lines=tuple(draw(st.lists(_LINE, min_size=1, max_size=3))),
        )
        for i in range(n)
    ]


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
_CLASS_TAG = st.text(alphabet=_WORD_CHARS, min_size=1, max_size=10).map(lambda s: f"<c.{s}>")
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


@given(_LINE)
def test_strip_tags_is_identity_on_clean_text(line: str) -> None:
    assert strip_tags(line) == line
