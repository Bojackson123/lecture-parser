"""P4-01: tokens, rare-term weights, slide↔segment scoring, on the committed fixtures.

Segment numbers are 1-based, matching the slide → time map and captions table in
``tests/fixtures/README.md``; slides are addressed by their 1-based ``number``.
"""

from __future__ import annotations

import math

import pytest

from lecturenotes.align.scoring import score, slide_terms, term_weights, tokenize
from lecturenotes.ingest.captions import Segment
from lecturenotes.ingest.slides import Deck, Slide


def _seg(segments: list[Segment], n: int) -> Segment:
    """1-based, matching the segment numbers in ``tests/fixtures/README.md``."""
    return segments[n - 1]


def _slide(deck: Deck, n: int) -> Slide:
    return deck.slides[n - 1]


@pytest.fixture(scope="session")
def weights(segments: list[Segment]) -> dict[str, float]:
    return term_weights(segments)


def test_tokenize_takes_alphanumeric_runs_and_drops_short_tokens() -> None:
    """Slide 2's equation line: ``max_a`` → ``max``/``a``, ``V(s')`` → ``v``/``s``,
    and everything shorter than 3 characters is gone."""
    line = "V(s) = max_a [ R(s, a) + gamma * sum_s' T(s, a, s') V(s') ]"
    assert tokenize(line) == frozenset({"max", "gamma", "sum"})


def test_tokenize_folds_case_and_drops_stopwords() -> None:
    """Segment 7's question must share nothing with slide 1's "how much later
    rewards count" — the stopword list is graded by exactly this kind of collision."""
    assert tokenize("How much would YOU pay?") == frozenset({"pay"})


def test_bellman_outweighs_the_generic_equation(weights: dict[str, float]) -> None:
    """The rare-term ordering the fixtures README promises: "bellman" occurs in
    segments 14/16/18 only (df 3), "equation" in all three slide windows
    (segments 4/14/16/18/19, df 5)."""
    assert weights["bellman"] > weights["equation"] > 0
    assert weights["bellman"] == pytest.approx(math.log(22 / 3))
    assert weights["equation"] == pytest.approx(math.log(22 / 5))


def test_a_term_in_every_segment_weighs_zero() -> None:
    one = Segment(start_s=0.0, end_s=1.0, text="the bellman equation")
    assert term_weights([one] * 22) == {"bellman": 0.0, "equation": 0.0}


def test_segment_14_scores_slide_2_only(
    segments: list[Segment], deck: Deck, weights: dict[str, float]
) -> None:
    """"this is the bellman equation, and it is the heart of the whole course."
    pins slide 2; slides 1 and 3 share no vocabulary with it at all."""
    speech = tokenize(_seg(segments, 14).text)
    assert score(slide_terms(_slide(deck, 2)), speech, weights) > 0
    assert score(slide_terms(_slide(deck, 1)), speech, weights) == 0.0
    assert score(slide_terms(_slide(deck, 3)), speech, weights) == 0.0


def test_segment_4_shares_only_equation_with_slide_2(
    segments: list[Segment], deck: Deck
) -> None:
    """The generic-term trap, pinned at the vocabulary level: "the famous equation
    coming up" touches slide 2 through "equation" alone (and slide 1 not at all), so
    only the DP's monotonicity (P4-02) keeps segment 4 with slide 1."""
    speech = tokenize(_seg(segments, 4).text)
    assert speech & slide_terms(_slide(deck, 2)) == frozenset({"equation"})
    assert speech & slide_terms(_slide(deck, 1)) == frozenset()


def test_board_work_segments_share_no_slide_vocabulary(
    segments: list[Segment], deck: Deck
) -> None:
    """The gap signal (fixtures README, board-work row): every gap segment (5-12)
    shares < 2 scoring terms with every slide. The one stray hit — "number" in
    segment 6 against slide 1's "a number received…" — is why the bound is 2, not 1;
    asserting the exact pair keeps the coincidence documented."""
    stray_hits = {
        (n, slide.number): shared
        for n in range(5, 13)
        for slide in deck.slides
        if (shared := tokenize(_seg(segments, n).text) & slide_terms(slide))
    }
    assert all(len(shared) < 2 for shared in stray_hits.values())
    assert stray_hits == {(6, 1): frozenset({"number"})}


def test_segment_22_shares_transition_function_with_slide_1_not_slide_3(
    segments: list[Segment], deck: Deck
) -> None:
    """The closing recap's vocabulary points back at slide 1 and not at slide 3 —
    exactly what P4-02's monotonicity must overrule, pinned here."""
    speech = tokenize(_seg(segments, 22).text)
    assert speech & slide_terms(_slide(deck, 1)) == frozenset({"transition", "function"})
    assert speech & slide_terms(_slide(deck, 3)) == frozenset()


def test_speaker_notes_never_score(
    segments: list[Segment], weights: dict[str, float]
) -> None:
    """``slide_terms`` reads title + block lines only: notes are PPTX-only, so
    scoring them would make alignment differ between two exports of one deck."""
    notes_only = Slide(
        number=1, title=None, blocks=(), notes="the bellman equation", image_ids=()
    )
    assert slide_terms(notes_only) == frozenset()
    assert score(slide_terms(notes_only), tokenize(_seg(segments, 14).text), weights) == 0.0
