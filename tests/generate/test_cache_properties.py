"""P5-01 property tests for the cache key and the round-trip (plan §10, §7.1).

Key text is full unicode (hypothesis excludes surrogates) so the UTF-8 hashing and
the on-disk round-trip face non-ASCII, empty strings and control characters. The
round-trip test builds its own temporary directory per example — a function-scoped
``tmp_path`` inside ``@given`` would be reused across examples.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from lecturenotes.generate.cache import CachedClient, response_key
from lecturenotes.generate.client import GenRequest

TEXT = st.text(max_size=100)
DISTINCT = st.tuples(TEXT, TEXT).filter(lambda pair: pair[0] != pair[1])
HEX_DIGITS = set("0123456789abcdef")


@given(TEXT, TEXT, TEXT)
def test_key_is_deterministic_lowercase_hex(prompt_version: str, model: str, prompt: str) -> None:
    key = response_key(prompt_version, model, prompt)
    assert key == response_key(prompt_version, model, prompt)
    assert len(key) == 64
    assert set(key) <= HEX_DIGITS


@given(DISTINCT, TEXT, TEXT)
def test_key_changes_with_prompt_version(pair: tuple[str, str], model: str, prompt: str) -> None:
    first, second = pair
    assert response_key(first, model, prompt) != response_key(second, model, prompt)


@given(TEXT, DISTINCT, TEXT)
def test_key_changes_with_model(prompt_version: str, pair: tuple[str, str], prompt: str) -> None:
    first, second = pair
    assert response_key(prompt_version, first, prompt) != response_key(
        prompt_version, second, prompt
    )


@given(TEXT, TEXT, DISTINCT)
def test_key_changes_with_prompt(prompt_version: str, model: str, pair: tuple[str, str]) -> None:
    first, second = pair
    assert response_key(prompt_version, model, first) != response_key(prompt_version, model, second)


@given(TEXT)
def test_no_collision_by_concatenation(prompt: str) -> None:
    # The key must hash the triple, not a joined string: ("a", "bc") vs ("ab", "c").
    assert response_key("a", "bc", prompt) != response_key("ab", "c", prompt)


class _FixedClient:
    model = "stub-model"

    def __init__(self, response: str) -> None:
        self._response = response

    def complete(self, request: GenRequest) -> str:
        return self._response


@given(st.text(max_size=200))
def test_cache_round_trips_any_response_text(response: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        client = CachedClient(
            _FixedClient(response), cache_dir=Path(tmp) / "c", prompt_version="1"
        )
        request = GenRequest(key="k", prompt="p")
        assert client.complete(request) == response
        assert client.complete(request) == response
