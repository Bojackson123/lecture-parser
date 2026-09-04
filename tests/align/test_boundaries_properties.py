"""P4-02 property tests (plan §10): units against spans, the DP against brute force.

``solve_windows`` is *specified* by exhaustive search: with ≤ 4 slides, ≤ 6 units and
integer weights the optimum and its tie-break are exact, so the DP must reproduce the
lexicographically largest optimal boundary tuple exactly — not merely its score.
Monotonic-partition optimisers rot at the edges (empty windows, ties, single slide);
the brute force gives the DP nowhere to hide.
"""

from __future__ import annotations

from itertools import combinations_with_replacement, pairwise

from hypothesis import given

from lecturenotes.align.boundaries import solve_windows, span_units
from lecturenotes.align.scoring import score
from lecturenotes.ingest.captions import Segment
from tests.align.strategies import WindowsInstance, ordered_segments, windows_instances

# --- span_units ---------------------------------------------------------------


@given(ordered_segments())
def test_units_partition_the_segments_into_consecutive_runs(segments: list[Segment]) -> None:
    units = span_units(segments)
    assert [i for unit in units for i in unit] == list(range(len(segments)))


@given(ordered_segments())
def test_neighbours_share_a_unit_iff_spans_strictly_overlap(segments: list[Segment]) -> None:
    units = span_units(segments)
    unit_of = {i: k for k, unit in enumerate(units) for i in unit}
    for i in range(1, len(segments)):
        together = unit_of[i - 1] == unit_of[i]
        assert together == (segments[i].start_s < segments[i - 1].end_s)


@given(ordered_segments(overlaps=False))
def test_non_overlapping_segments_yield_singleton_units(segments: list[Segment]) -> None:
    assert span_units(segments) == tuple((i,) for i in range(len(segments)))


@given(ordered_segments())
def test_span_units_is_deterministic(segments: list[Segment]) -> None:
    assert span_units(segments) == span_units(segments)


# --- solve_windows ------------------------------------------------------------


def _total(
    slides: list[frozenset[str]],
    units: list[frozenset[str]],
    cuts: tuple[int, ...],
    weights: dict[str, float],
) -> float:
    """Distinct-union window scoring: each shared term counts once per window."""
    return sum(
        score(slides[j], frozenset().union(*units[cuts[j] : cuts[j + 1]]), weights)
        for j in range(len(slides))
    )


def _brute_force(
    slides: list[frozenset[str]],
    units: list[frozenset[str]],
    weights: dict[str, float],
) -> tuple[float, tuple[int, ...]]:
    """Every non-decreasing boundary tuple; keep the max score, ties to the
    lexicographically largest boundaries. Returns (total, per-unit assignment)."""
    best: tuple[float, tuple[int, ...]] | None = None
    for bounds in combinations_with_replacement(range(len(units) + 1), len(slides) - 1):
        cuts = (0, *bounds, len(units))
        key = (_total(slides, units, cuts, weights), bounds)
        if best is None or key > best:
            best = key
    assert best is not None
    total, bounds = best
    cuts = (0, *bounds, len(units))
    assignment = tuple(j for j in range(len(slides)) for _ in range(cuts[j + 1] - cuts[j]))
    return total, assignment


@given(windows_instances())
def test_dp_equals_brute_force_optimum_and_tie_break(instance: WindowsInstance) -> None:
    slides, units, weights = instance
    expected_total, expected = _brute_force(slides, units, weights)
    assignment = solve_windows(slides, units, weights)
    assert assignment == expected
    # Recompute the DP result's total through the same distinct-union scoring the
    # brute force used: equal boundaries must also mean the equal optimum score.
    boundaries = tuple(
        sum(1 for a in assignment if a < j) for j in range(1, len(slides))
    )
    assert _total(slides, units, (0, *boundaries, len(units)), weights) == expected_total


@given(windows_instances())
def test_assignment_is_monotonic_in_range_and_covers_every_unit(
    instance: WindowsInstance,
) -> None:
    slides, units, weights = instance
    assignment = solve_windows(slides, units, weights)
    assert len(assignment) == len(units)
    assert all(0 <= j < len(slides) for j in assignment)
    assert all(a <= b for a, b in pairwise(assignment))


@given(windows_instances())
def test_solve_windows_is_deterministic(instance: WindowsInstance) -> None:
    slides, units, weights = instance
    assert solve_windows(slides, units, weights) == solve_windows(slides, units, weights)


@given(windows_instances())
def test_no_units_yields_the_empty_assignment(instance: WindowsInstance) -> None:
    slides, _, weights = instance
    assert solve_windows(slides, [], weights) == ()


@given(windows_instances())
def test_one_slide_takes_every_unit(instance: WindowsInstance) -> None:
    _, units, weights = instance
    assert solve_windows([frozenset({"alpha"})], units, weights) == (0,) * len(units)
