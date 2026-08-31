"""P1-02: rolling-caption dedupe (plan §3 stage 1, second function).

The fixture tests are named after rows of the captions table in
``tests/fixtures/README.md`` (cues 1–6, the rolling stretch); the inline-``Cue`` tests
pin down the edge cases the ticket lists. Plan §10: "the caption-dedupe edge cases are
the whole difficulty" of Phase 1.
"""

from __future__ import annotations

import pytest

from lecturenotes.ingest.captions import Cue, dedupe_rolling, parse_srt, parse_vtt

CUE_COUNT = 20

# The seven unique lines of the rolling stretch, verbatim from the fixture.
LINE_A = "welcome back everyone, today we start on sequential decision making."
LINE_B = "a markov decision process has four ingredients: states, actions, rewards,"
LINE_C = "and a transition function that says where you land after each action."
LINE_D = "the reward is a number you get for taking an action in a state,"
LINE_E = "and the discount factor gamma says how much you care about later rewards."
LINE_F = "keep this picture in your head because the famous equation coming up"
LINE_G = "is nothing more than these four ingredients written down recursively."
ROLLING_LINES = (LINE_A, LINE_B, LINE_C, LINE_D, LINE_E, LINE_F, LINE_G)


def cue(start_s: float, end_s: float, *lines: str) -> Cue:
    return Cue(start_s=start_s, end_s=end_s, lines=lines)


@pytest.fixture(scope="module", params=["vtt", "srt"])
def parsed(request: pytest.FixtureRequest) -> list[Cue]:
    """The 20 fixture cues as parsed by P1-01, for both caption formats."""
    if request.param == "vtt":
        return parse_vtt(request.getfixturevalue("vtt_text"))
    return parse_srt(request.getfixturevalue("srt_text"))


@pytest.fixture(scope="module")
def deduped(parsed: list[Cue]) -> list[Cue]:
    return dedupe_rolling(parsed)


# --- the fixture, row by row -------------------------------------------------------


def test_20_cues_in_20_cues_out(parsed: list[Cue], deduped: list[Cue]) -> None:
    """No fixture cue is a whole-cue repeat, so nothing is dropped."""
    assert len(parsed) == CUE_COUNT
    assert len(deduped) == CUE_COUNT


def test_cues_01_to_06_collapse_to_the_seven_lines_a_to_g(deduped: list[Cue]) -> None:
    lines = tuple(line for c in deduped[:6] for line in c.lines)
    assert lines == ROLLING_LINES


def test_cue_01_keeps_two_lines_cues_02_to_06_keep_one(deduped: list[Cue]) -> None:
    assert deduped[0].lines == (LINE_A, LINE_B)
    assert [c.lines for c in deduped[1:6]] == [(line,) for line in ROLLING_LINES[2:]]


def test_rolling_stretch_has_no_repeated_text(deduped: list[Cue]) -> None:
    lines = [line for c in deduped[:6] for line in c.lines]
    assert len(lines) == len(set(lines)) == 7


def test_every_cue_keeps_its_parsed_timing(parsed: list[Cue], deduped: list[Cue]) -> None:
    assert [(c.start_s, c.end_s) for c in deduped] == [(c.start_s, c.end_s) for c in parsed]


def test_cues_07_to_20_are_untouched(parsed: list[Cue], deduped: list[Cue]) -> None:
    assert deduped[6:] == parsed[6:]


def test_cue_17_multi_line_cue_that_is_not_a_rolling_repeat_is_kept(deduped: list[Cue]) -> None:
    assert len(deduped[16].lines) == 2


def test_vtt_and_srt_dedupe_to_the_same_cues(vtt_text: str, srt_text: str) -> None:
    assert dedupe_rolling(parse_vtt(vtt_text)) == dedupe_rolling(parse_srt(srt_text))


# --- ad-hoc edge cases -------------------------------------------------------------


def test_whole_cue_repeat_is_dropped_and_extends_the_survivor() -> None:
    assert dedupe_rolling([cue(0, 2, "foo bar"), cue(2, 5, "foo bar")]) == [cue(0, 5, "foo bar")]


def test_chain_of_whole_cue_repeats_collapses_to_one_spanning_all() -> None:
    cues = [cue(0, 2, "foo bar"), cue(2, 5, "foo bar"), cue(5, 9, "foo bar")]
    assert dedupe_rolling(cues) == [cue(0, 9, "foo bar")]


def test_two_line_overlap() -> None:
    cues = [cue(0, 2, "a", "b", "c"), cue(2, 4, "b", "c", "d")]
    assert dedupe_rolling(cues) == [cue(0, 2, "a", "b", "c"), cue(2, 4, "d")]


def test_one_line_overlap_in_a_multi_line_cue() -> None:
    cues = [cue(0, 2, "a", "b"), cue(2, 4, "b", "c", "d")]
    assert dedupe_rolling(cues) == [cue(0, 2, "a", "b"), cue(2, 4, "c", "d")]


def test_overlap_is_against_the_survivor_not_the_original_neighbour() -> None:
    """After a cue is emptied, the next cue is compared to whatever survived before it."""
    cues = [cue(0, 2, "a", "b"), cue(2, 4, "b"), cue(4, 6, "b", "c")]
    assert dedupe_rolling(cues) == [cue(0, 4, "a", "b"), cue(4, 6, "c")]


def test_partial_line_is_not_a_repeat() -> None:
    cues = [
        cue(0, 2, "so", "the reward is a number"),
        cue(2, 4, "the reward is a number you get", "for an action"),
    ]
    assert dedupe_rolling(cues) == cues


def test_comparison_is_exact_no_case_folding_or_punctuation_stripping() -> None:
    cues = [cue(0, 2, "Foo bar."), cue(2, 4, "foo bar"), cue(4, 6, "foo bar,")]
    assert dedupe_rolling(cues) == cues


def test_non_adjacent_repeat_is_kept() -> None:
    cues = [cue(0, 1, "x"), cue(1, 2, "y"), cue(2, 3, "x")]
    assert dedupe_rolling(cues) == cues


def test_repeat_of_a_non_final_line_is_not_an_overlap() -> None:
    """Only a *suffix* of prev matching a *prefix* of cur counts."""
    cues = [cue(0, 2, "a", "b"), cue(2, 4, "a", "c")]
    assert dedupe_rolling(cues) == cues


def test_single_cue_and_empty_list() -> None:
    assert dedupe_rolling([]) == []
    assert dedupe_rolling([cue(0, 1, "a", "a")]) == [cue(0, 1, "a", "a")]


def test_inputs_are_not_mutated_and_a_new_list_is_returned() -> None:
    cues = [cue(0, 2, "a"), cue(2, 4, "a"), cue(4, 6, "b")]
    before = list(cues)
    out = dedupe_rolling(cues)
    assert cues == before
    assert out is not cues
    assert out == [cue(0, 4, "a"), cue(4, 6, "b")]


def test_stripping_continues_until_nothing_overlaps() -> None:
    """Degenerate repeated text: the result must be a fixed point of the function.

    A single "largest overlap" strip would leave ``(a, b) | (a, b, c)``, which still
    overlaps; deduping again would then change the output. The shortest prefix of
    ``cur`` whose remainder has no overlap with ``prev`` is dropped instead.
    """
    cues = [cue(0, 2, "a", "b"), cue(2, 4, "b", "a", "b", "c")]
    out = dedupe_rolling(cues)
    assert out == [cue(0, 2, "a", "b"), cue(2, 4, "c")]
    assert dedupe_rolling(out) == out

    cues = [cue(0, 2, "a", "a"), cue(2, 4, "a", "a", "a")]
    assert dedupe_rolling(cues) == [cue(0, 4, "a", "a")]
