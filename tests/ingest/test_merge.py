"""P1-03: sentence-boundary merge (plan §3 stage 1, third function).

The fixture tests are named after rows of the captions table in
``tests/fixtures/README.md`` and run on the deduped fixture cues; the inline-``Cue``
tests pin down the knobs (``max_gap_s``, ``max_segment_s``), the terminator rule and
its documented v1 limitation.
"""

from __future__ import annotations

import pytest

from lecturenotes.ingest.captions import (
    Cue,
    Segment,
    dedupe_rolling,
    merge_sentences,
    parse_vtt,
)

SEGMENT_COUNT = 22


def cue(start_s: float, end_s: float, *lines: str) -> Cue:
    return Cue(start_s=start_s, end_s=end_s, lines=lines)


def seg(start_s: float, end_s: float, text: str) -> Segment:
    return Segment(start_s=start_s, end_s=end_s, text=text)


@pytest.fixture(scope="module")
def segments(vtt_text: str) -> list[Segment]:
    """The fixture after parse -> dedupe -> merge with the default knobs."""
    return merge_sentences(dedupe_rolling(parse_vtt(vtt_text)))


def _within(segments: list[Segment], lo: float, hi: float) -> bool:
    return all(lo <= s.start_s and s.end_s <= hi for s in segments)


# --- the fixture, row by row -------------------------------------------------------


def test_fixture_merges_to_22_segments(segments: list[Segment]) -> None:
    assert len(segments) == SEGMENT_COUNT


def test_cue_07_two_sentences_in_one_cue_split_at_suppose_and_share_the_span(
    segments: list[Segment],
) -> None:
    first, second = segments[4], segments[5]
    assert first.text.endswith("and grab the chalk.")
    assert second.text.startswith("suppose you roll")
    assert (first.start_s, first.end_s) == (151.0, 180.0)
    assert (second.start_s, second.end_s) == (151.0, 180.0)


def test_cue_08_question_mark_terminator_splits_at_on_average(segments: list[Segment]) -> None:
    question, answer = segments[6], segments[7]
    assert question.text == "how much would you pay to play that game?"
    assert answer.text.startswith("on average you win")
    assert (question.start_s, question.end_s) == (answer.start_s, answer.end_s) == (180.0, 210.0)


def test_cues_18_and_19_mid_sentence_cue_is_held_open_and_merged(
    segments: list[Segment],
) -> None:
    merged = [s for s in segments if "tolerance epsilon" in s.text]
    assert len(merged) == 1
    assert "tolerance epsilon you stop and read off" in merged[0].text
    assert (merged[0].start_s, merged[0].end_s) == (470.0, 520.0)


def test_cue_17_multi_line_cue_lines_are_joined_with_exactly_one_space(
    segments: list[Segment],
) -> None:
    joined = [s for s in segments if "maximum change" in s.text]
    assert len(joined) == 1
    assert "the maximum change between sweeps shrinks" in joined[0].text
    assert (joined[0].start_s, joined[0].end_s) == (445.0, 470.0)


def test_cues_01_and_02_sentence_continues_across_the_rolling_boundary(
    segments: list[Segment],
) -> None:
    second = segments[1]
    assert second.text.startswith("a markov decision process has four ingredients")
    assert second.text.endswith("where you land after each action.")
    assert (second.start_s, second.end_s) == (1.0, 50.0)


def test_no_segment_text_has_newlines_tags_double_spaces_or_edge_whitespace(
    segments: list[Segment],
) -> None:
    for s in segments:
        assert "\n" not in s.text
        assert "<" not in s.text and ">" not in s.text
        assert "  " not in s.text
        assert s.text == s.text.strip()


def test_cue_14_exam_phrase_is_in_exactly_one_segment_inside_its_cue_span(
    segments: list[Segment],
) -> None:
    exam = [s for s in segments if "this will be on the exam" in s.text]
    assert len(exam) == 1
    assert _within(exam, 360.0, 390.0)


def test_bellman_is_in_exactly_three_segments_all_inside_the_slide_2_window(
    segments: list[Segment],
) -> None:
    bellman = [s for s in segments if "bellman" in s.text]
    assert len(bellman) == 3
    assert _within(bellman, 270.0, 420.0)


def test_every_segment_bound_is_the_bound_of_some_fixture_cue(
    vtt_text: str, segments: list[Segment]
) -> None:
    """Spans are unions of cue spans; nothing is interpolated (ticket decision)."""
    cues = parse_vtt(vtt_text)
    starts = {c.start_s for c in cues}
    ends = {c.end_s for c in cues}
    for s in segments:
        assert s.start_s in starts and s.end_s in ends, s


# --- ad-hoc edge cases -------------------------------------------------------------


def test_unpunctuated_captions_are_cut_when_the_buffer_would_exceed_max_segment_s() -> None:
    cues = [cue(10 * i, 10 * (i + 1), f"word{i}") for i in range(6)]
    out = merge_sentences(cues, max_segment_s=30.0)
    assert out == [
        seg(0.0, 30.0, "word0 word1 word2"),
        seg(30.0, 60.0, "word3 word4 word5"),
    ]


def test_silence_gap_flushes_an_open_buffer_before_the_next_cue() -> None:
    cues = [cue(0, 10, "the reward is"), cue(18, 25, "a number.")]
    assert merge_sentences(cues) == [seg(0, 10, "the reward is"), seg(18, 25, "a number.")]


def test_gap_under_max_gap_s_with_no_terminator_still_merges() -> None:
    cues = [cue(0, 10, "the reward is"), cue(14, 25, "a number.")]
    assert merge_sentences(cues) == [seg(0, 25, "the reward is a number.")]


def test_gap_threshold_is_configurable() -> None:
    cues = [cue(0, 10, "the reward is"), cue(14, 25, "a number.")]
    assert merge_sentences(cues, max_gap_s=3.0) == [
        seg(0, 10, "the reward is"),
        seg(14, 25, "a number."),
    ]


def test_eof_flush_keeps_a_final_cue_with_no_terminal_punctuation() -> None:
    cues = [cue(0, 10, "first sentence."), cue(10, 20, "and then it just stops")]
    assert merge_sentences(cues) == [
        seg(0, 10, "first sentence."),
        seg(10, 20, "and then it just stops"),
    ]


def test_ellipsis_and_interrobang_each_count_as_one_terminator() -> None:
    cues = [cue(0, 10, "wait for it... really?! yes.")]
    assert [s.text for s in merge_sentences(cues)] == ["wait for it...", "really?!", "yes."]


def test_closing_quote_or_bracket_after_the_terminator_stays_with_the_sentence() -> None:
    cues = [cue(0, 10, 'he said "stop." (really!) then left.')]
    assert [s.text for s in merge_sentences(cues)] == ['he said "stop."', "(really!)", "then left."]


def test_decimal_point_does_not_split() -> None:
    cues = [cue(0, 10, "on average you win 3.5 dollars.")]
    assert [s.text for s in merge_sentences(cues)] == ["on average you win 3.5 dollars."]


def test_dot_not_followed_by_whitespace_does_not_split_so_e_dot_g_dot_this_does_split() -> None:
    """Documents the v1 limitation: ``e.g.`` followed by a space is a false sentence end."""
    cues = [cue(0, 10, "use a solver, e.g. value iteration.")]
    assert [s.text for s in merge_sentences(cues)] == ["use a solver, e.g.", "value iteration."]


def test_terminator_at_end_of_text_splits() -> None:
    assert merge_sentences([cue(0, 10, "done.")]) == [seg(0, 10, "done.")]


def test_sentence_completed_in_a_later_cue_starts_where_the_buffer_started() -> None:
    cues = [cue(0, 10, "a"), cue(10, 20, "b"), cue(20, 30, "c. d")]
    assert merge_sentences(cues) == [seg(0, 30, "a b c."), seg(20, 30, "d")]


def test_max_segment_flush_ends_at_the_last_cue_seen() -> None:
    cues = [cue(0, 10, "a"), cue(20, 30, "b"), cue(55, 65, "c")]
    assert merge_sentences(cues, max_gap_s=100.0, max_segment_s=50.0) == [
        seg(0, 30, "a b"),
        seg(55, 65, "c"),
    ]


def test_empty_cue_list_gives_empty_segment_list() -> None:
    assert merge_sentences([]) == []


def test_inputs_are_not_mutated() -> None:
    cues = [cue(0, 10, "a"), cue(10, 20, "b.")]
    before = list(cues)
    merge_sentences(cues)
    assert cues == before
