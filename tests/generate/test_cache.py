"""P5-01 cache tests (plan §7.1: cache LLM responses so tuning doesn't re-spend tokens).

The inner client is a counting stub — the cache's contract is "inner is called once
per distinct (prompt_version, model, prompt), everything else is a file read".
"""

from __future__ import annotations

from pathlib import Path

from lecturenotes.generate.cache import CachedClient
from lecturenotes.generate.client import GenRequest


class CountingClient:
    """``LLMClient`` stub: counts completions, returns a fixed response."""

    model = "stub-model"

    def __init__(self, response: str = "generated") -> None:
        self.response = response
        self.calls = 0

    def complete(self, request: GenRequest) -> str:
        self.calls += 1
        return self.response


def test_second_identical_call_is_served_from_disk(tmp_path: Path) -> None:
    inner = CountingClient()
    client = CachedClient(inner, cache_dir=tmp_path / "c", prompt_version="1")
    request = GenRequest(key="chunk:lec01:s2-2", prompt="p")

    assert client.complete(request) == "generated"
    assert inner.calls == 1
    assert len(list((tmp_path / "c").iterdir())) == 1

    assert client.complete(request) == "generated"
    assert inner.calls == 1
    assert len(list((tmp_path / "c").iterdir())) == 1


def test_a_different_prompt_misses(tmp_path: Path) -> None:
    inner = CountingClient()
    client = CachedClient(inner, cache_dir=tmp_path / "c", prompt_version="1")

    client.complete(GenRequest(key="chunk:lec01:s2-2", prompt="p"))
    client.complete(GenRequest(key="chunk:lec01:s2-2", prompt="q"))
    assert inner.calls == 2
    assert len(list((tmp_path / "c").iterdir())) == 2


def test_cache_dir_is_created_on_demand(tmp_path: Path) -> None:
    cache_dir = tmp_path / "nested" / "c"
    client = CachedClient(CountingClient(), cache_dir=cache_dir, prompt_version="1")
    assert not cache_dir.exists()
    client.complete(GenRequest(key="k", prompt="p"))
    assert cache_dir.is_dir()


def test_model_is_the_inner_model(tmp_path: Path) -> None:
    client = CachedClient(CountingClient(), cache_dir=tmp_path / "c", prompt_version="1")
    assert client.model == "stub-model"
