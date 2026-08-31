"""P1-02 property tests (plan §10: property-based tests for the pure stages).

``corrupted_cue_lists`` takes a clean cue list and injects YouTube-style rolling
repeats — the previous cue's last line copied to the front of the next cue, and whole
cues re-shown as a second cue over the tail of their span. ``dedupe_rolling`` must undo
exactly that corruption.
"""

from __future__ import annotations

from hypothesis import assume, given
from hypothesis import strategies as st

from lecturenotes.ingest.captions import Cue, dedupe_rolling
from tests.ingest.strategies import cue_lists


def _no_adjacent_shared_lines(cues: list[Cue]) -> bool:
    return all(not set(p.lines) & set(c.lines) for p, c in zip(cues, cues[1:], strict=False))


clean_cue_lists = cue_lists().filter(_no_adjacent_shared_lines)


@st.composite
def corrupted_cue_lists(draw: st.DrawFn) -> tuple[list[Cue], list[Cue]]:
    """``(clean, corrupted)``: ``corrupted`` is ``clean`` with rolling repeats injected."""
    clean = draw(clean_cue_lists)
    corrupted: list[Cue] = []
    for i, c in enumerate(clean):
        lines = c.lines
        if i and draw(st.booleans()):
            lines = (clean[i - 1].lines[-1], *lines)
        if draw(st.booleans()):
            # Re-show the cue: split its span at a point in [start, end] into two cues.
            start_ms, end_ms = round(c.start_s * 1000), round(c.end_s * 1000)
            mid_s = draw(st.integers(start_ms, end_ms)) / 1000
            corrupted.append(Cue(start_s=c.start_s, end_s=mid_s, lines=lines))
            corrupted.append(Cue(start_s=mid_s, end_s=c.end_s, lines=c.lines))
        else:
            corrupted.append(Cue(start_s=c.start_s, end_s=c.end_s, lines=lines))
    return clean, corrupted


def _is_subsequence(needle: list[str], haystack: list[str]) -> bool:
    it = iter(haystack)
    return all(any(item == candidate for candidate in it) for item in needle)


@given(cue_lists())
def test_output_lines_are_a_subsequence_of_input_lines(cues: list[Cue]) -> None:
    out = dedupe_rolling(cues)
    in_lines = [line for c in cues for line in c.lines]
    out_lines = [line for c in out for line in c.lines]
    assert _is_subsequence(out_lines, in_lines)


@given(cue_lists())
def test_no_adjacent_output_pair_shares_its_boundary_line(cues: list[Cue]) -> None:
    out = dedupe_rolling(cues)
    for prev, cur in zip(out, out[1:], strict=False):
        assert prev.lines[-1] != cur.lines[0]


@given(cue_lists())
def test_dedupe_is_idempotent(cues: list[Cue]) -> None:
    once = dedupe_rolling(cues)
    assert dedupe_rolling(once) == once


@given(clean_cue_lists)
def test_dedupe_is_the_identity_on_inputs_without_adjacent_repeats(cues: list[Cue]) -> None:
    assert dedupe_rolling(cues) == cues


@given(cue_lists())
def test_output_is_ordered_non_empty_and_covers_the_input(cues: list[Cue]) -> None:
    out = dedupe_rolling(cues)
    assert out
    assert all(c.lines for c in out)
    assert all(p.start_s <= c.start_s for p, c in zip(out, out[1:], strict=False))
    assert out[0].start_s == cues[0].start_s
    assert out[-1].end_s == cues[-1].end_s
    # Covered time never shrinks: every input span lies inside some output span.
    for c in cues:
        assert any(o.start_s <= c.start_s and c.end_s <= o.end_s for o in out)


@given(cue_lists())
def test_surviving_cues_keep_their_start_and_only_grow_at_the_end(cues: list[Cue]) -> None:
    out = dedupe_rolling(cues)
    starts = {c.start_s: c for c in cues}
    for o in out:
        assert o.start_s in starts
        assert o.end_s >= starts[o.start_s].end_s


@given(corrupted_cue_lists())
def test_deduping_injected_repeats_restores_the_clean_list(
    pair: tuple[list[Cue], list[Cue]],
) -> None:
    clean, corrupted = pair
    assume(corrupted != clean)
    assert dedupe_rolling(corrupted) == clean
