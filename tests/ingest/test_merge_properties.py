"""P1-03 property tests (plan §10: property-based tests for the pure stages).

Cue text is restricted to letters, spaces and ``.?!`` so that the terminator rule is
the only thing the generator exercises. ``terminated_cue_lists`` builds cues whose
every line is a run of complete sentences over letters-only words, so the test can
recover the sentences with a rule that does not come from the code under test.
"""

from __future__ import annotations

import math
import re

from hypothesis import given
from hypothesis import strategies as st

from lecturenotes.ingest.captions import Cue, Segment, merge_sentences
from tests.ingest.strategies import cue_lists

SENTENCE_WORD = st.text(alphabet="abcdefghijklmnopqrstuvwxyz.?!", min_size=1, max_size=8)
SENTENCE_LINE = st.lists(SENTENCE_WORD, min_size=1, max_size=8).map(" ".join)
sentence_cue_lists = cue_lists(line=SENTENCE_LINE)

LETTER_WORD = st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=8)
TERMINATOR = st.sampled_from([".", "?", "!", "...", "?!"])
SENTENCE = st.tuples(st.lists(LETTER_WORD, min_size=1, max_size=5), TERMINATOR).map(
    lambda t: " ".join(t[0]) + t[1]
)
TERMINATED_LINE = st.lists(SENTENCE, min_size=1, max_size=3).map(" ".join)
terminated_cue_lists = cue_lists(line=TERMINATED_LINE)

_WS = re.compile(r"\s+")


def _words(text: str) -> str:
    return _WS.sub(" ", text).strip()


@given(sentence_cue_lists)
def test_no_words_are_lost_or_invented(cues: list[Cue]) -> None:
    out = merge_sentences(cues)
    assert _words(" ".join(s.text for s in out)) == _words(
        " ".join(line for c in cues for line in c.lines)
    )


@given(sentence_cue_lists)
def test_every_segment_has_clean_non_empty_text(cues: list[Cue]) -> None:
    for s in merge_sentences(cues):
        assert s.text.strip()
        assert s.text == s.text.strip()
        assert "  " not in s.text


@given(sentence_cue_lists)
def test_starts_are_non_decreasing_and_every_span_is_well_formed(cues: list[Cue]) -> None:
    out = merge_sentences(cues)
    assert all(p.start_s <= c.start_s for p, c in zip(out, out[1:], strict=False))
    assert all(s.start_s <= s.end_s for s in out)


@given(sentence_cue_lists)
def test_every_span_lies_within_the_input_span(cues: list[Cue]) -> None:
    lo, hi = cues[0].start_s, cues[-1].end_s
    for s in merge_sentences(cues):
        assert lo <= s.start_s and s.end_s <= hi


@given(sentence_cue_lists)
def test_every_segment_bound_is_some_cue_bound(cues: list[Cue]) -> None:
    """Spans are unions of cue spans: nothing is interpolated (ticket decision)."""
    starts = {c.start_s for c in cues}
    ends = {c.end_s for c in cues}
    for s in merge_sentences(cues):
        assert s.start_s in starts
        assert s.end_s in ends


@given(sentence_cue_lists)
def test_infinite_knobs_never_cut_mid_sentence(cues: list[Cue]) -> None:
    """With no gap or length cap, only the last segment may lack a terminator."""
    out = merge_sentences(cues, max_gap_s=math.inf, max_segment_s=math.inf)
    for s in out[:-1]:
        assert s.text[-1] in ".?!"


def _sentences_in(line: str) -> list[str]:
    """Words are letters-only here, so a word ending in ``.?!`` ends a sentence."""
    sentences: list[str] = []
    current: list[str] = []
    for word in line.split(" "):
        current.append(word)
        if word[-1] in ".?!":
            sentences.append(" ".join(current))
            current = []
    assert not current, line
    return sentences


@given(terminated_cue_lists)
def test_cues_that_end_in_terminators_give_one_segment_per_sentence_with_the_cue_span(
    cues: list[Cue],
) -> None:
    expected = [
        Segment(start_s=c.start_s, end_s=c.end_s, text=sentence)
        for c in cues
        for line in c.lines
        for sentence in _sentences_in(line)
    ]
    assert merge_sentences(cues, max_gap_s=math.inf, max_segment_s=math.inf) == expected
