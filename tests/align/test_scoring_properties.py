"""P4-01 property tests (plan §10: property-based tests for the pure stages).

Text is drawn from letters, digits and punctuation so the tokeniser faces case,
short runs and separators; token sets and weights for the ``score`` properties are
built directly, with integer-valued weights so floating-point summation cannot blur
the exact monotonicity claim.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from lecturenotes.align.scoring import STOPWORDS, score, term_weights, tokenize
from lecturenotes.ingest.captions import Segment

ALPHABET = (
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    " .,;:!?'\"()[]{}<>-_+*/\\&%$#@=~^|"
)
TEXT = st.text(alphabet=ALPHABET, max_size=80)
TOKEN = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=3, max_size=8)
TOKENS = st.frozensets(TOKEN, max_size=8)
WEIGHTS = st.dictionaries(TOKEN, st.integers(min_value=0, max_value=1000).map(float), max_size=8)


@given(TEXT)
def test_tokens_are_lowercase_long_enough_and_never_stopwords(text: str) -> None:
    for token in tokenize(text):
        assert len(token) >= 3
        assert token not in STOPWORDS
        assert token == token.lower()


@given(TEXT)
def test_tokenize_is_a_pure_function_of_its_input(text: str) -> None:
    assert tokenize(text) == tokenize(text)


@given(st.lists(st.text(alphabet=ALPHABET, min_size=1, max_size=80), max_size=10))
def test_weights_are_non_negative(texts: list[str]) -> None:
    segments = [Segment(start_s=0.0, end_s=1.0, text=text) for text in texts]
    assert all(weight >= 0.0 for weight in term_weights(segments).values())


@given(TOKENS, TOKENS, WEIGHTS)
def test_disjoint_terms_score_zero(
    slide: frozenset[str], speech: frozenset[str], weights: dict[str, float]
) -> None:
    assert score(slide, speech - slide, weights) == 0.0


@given(TOKENS, TOKENS, WEIGHTS, TOKEN)
def test_adding_a_shared_term_never_lowers_the_score(
    slide: frozenset[str], speech: frozenset[str], weights: dict[str, float], extra: str
) -> None:
    base = score(slide, speech, weights)
    assert score(slide | {extra}, speech | {extra}, weights) >= base
