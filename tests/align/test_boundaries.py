"""P4-02: span units and the monotonic window DP, on the committed fixtures.

Segment numbers in test names and helpers are 1-based, matching the slide → time map
in ``tests/fixtures/README.md``; unit indices and window indices in assertions are
0-based (window 0 = slide 1).
"""

from __future__ import annotations

import pytest

from lecturenotes.align.boundaries import solve_windows, span_units
from lecturenotes.align.scoring import slide_terms, term_weights, tokenize
from lecturenotes.ingest.captions import Segment
from lecturenotes.ingest.slides import Deck

# The 22 segments as 16 units (0-based segment indices): the rolling overlap glues
# segments 1-2 (spans 1-26 and 1-50), each two-sentence cue glues its pair, and
# everything else is a singleton.
EXPECTED_UNITS = (
    (0, 1),  # rolling overlap: segment 1 spans 1-26 inside segment 2's 1-50
    (2,),
    (3,),
    (4, 5),  # cue 7, two sentences sharing its span
    (6, 7),  # cue 8
    (8, 9),  # cue 9
    (10, 11),  # cue 10
    (12, 13),  # cue 11: "back to the slides." + the first bellman sentence
    (14,),
    (15,),
    (16,),
    (17,),
    (18,),
    (19,),
    (20,),
    (21,),
)

Units = tuple[tuple[int, ...], ...]


@pytest.fixture(scope="session")
def units(segments: list[Segment]) -> Units:
    return span_units(segments)


@pytest.fixture(scope="session")
def assignment(segments: list[Segment], deck: Deck, units: Units) -> tuple[int, ...]:
    """The fixture solve: 3 slide term sets against the 16 units' distinct unions."""
    unit_terms = [
        frozenset().union(*(tokenize(segments[i].text) for i in unit)) for unit in units
    ]
    slides = [slide_terms(slide) for slide in deck.slides]
    return solve_windows(slides, unit_terms, term_weights(segments))


def _window_of(units: Units, assignment: tuple[int, ...], segment_number: int) -> int:
    """The window holding 1-based ``segment_number``'s unit."""
    index = segment_number - 1
    (position,) = (k for k, unit in enumerate(units) if index in unit)
    return assignment[position]


def test_span_units_yields_16_units_grouping_overlapping_spans(units: Units) -> None:
    assert units == EXPECTED_UNITS


def test_touching_segments_2_and_3_are_separate_units(
    segments: list[Segment], units: Units
) -> None:
    """Touching is not overlapping: the spans meet at 50.0 exactly."""
    assert segments[1].end_s == 50.0
    assert segments[2].start_s == 50.0
    assert units[0] == (0, 1)
    assert units[1] == (2,)


def test_span_units_rejects_segments_out_of_transcript_order() -> None:
    later = Segment(start_s=10.0, end_s=20.0, text="later")
    earlier = Segment(start_s=5.0, end_s=15.0, text="earlier")
    with pytest.raises(ValueError, match="order"):
        span_units([later, earlier])


def test_windows_are_7_5_4_units_opening_at_segments_1_13_and_19(
    units: Units, assignment: tuple[int, ...]
) -> None:
    """The fixtures README's slide → time map, as per-unit window indices."""
    assert assignment == (0,) * 7 + (1,) * 5 + (2,) * 4
    opening_segments = [units[assignment.index(j)][0] + 1 for j in range(3)]
    assert opening_segments == [1, 13, 19]


def test_generic_equation_does_not_advance_segment_4(
    units: Units, assignment: tuple[int, ...]
) -> None:
    """Segment 4 shares "equation" with slide 2 (P4-01 pinned that), but window 2's
    vocabulary already has "equation" from the bellman cues: under distinct-union
    scoring the move gains nothing, and the tie-break keeps the segment on slide 1."""
    assert _window_of(units, assignment, 4) == 0


def test_window_2_opens_on_the_bellman_cue(units: Units, assignment: tuple[int, ...]) -> None:
    """The unit (12, 13) — "back to the slides." plus the first bellman sentence, one
    cue — is in window 1 entire: the span rule drags the vocabulary-free sentence
    along with its cue-mate."""
    assert assignment[units.index((12, 13))] == 1
    assert _window_of(units, assignment, 13) == 1
    assert _window_of(units, assignment, 14) == 1


def test_monotonicity_keeps_the_closing_recap_on_slide_3(
    units: Units, assignment: tuple[int, ...]
) -> None:
    """Segment 22 shares {transition, function} with slide 1 and nothing with slide 3
    (P4-01 pinned that); matched independently it would jump back to slide 1, and the
    monotonic constraint is what keeps it in window 2 (plan §4.1)."""
    assert _window_of(units, assignment, 22) == 2


def test_board_work_stays_in_window_1(units: Units, assignment: tuple[int, ...]) -> None:
    """The four board-work units (segments 5-12) score zero against every slide, so
    the advance-as-late-as-possible tie-break keeps them all in window 0 — their gap
    status is P4-03's job; here they merely must not advance the slide."""
    assert [_window_of(units, assignment, n) for n in range(5, 13)] == [0] * 8


def test_solve_windows_rejects_units_without_slides() -> None:
    """The no-deck case is ``align_lecture``'s branch (P4-03), not a silent guess."""
    with pytest.raises(ValueError, match="slides"):
        solve_windows([], [frozenset({"bellman"})], {"bellman": 1.0})
