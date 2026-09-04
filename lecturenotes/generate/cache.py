"""Response cache (plan §7.1): without it every tuning iteration costs a full week
of tokens.

    response_key(prompt_version, model, prompt)  → sha256 hex, §7.1's cache key
    CachedClient(inner, cache_dir, prompt_version)  file-per-response wrapper

Decisions (P5-01):

- **The key hashes the canonical JSON of the *triple*** ``[prompt_version, model,
  prompt]`` — delimiter-collision-free (``("a", "bc")`` ≠ ``("ab", "c")``), and a
  tuned prompt or a model switch re-generates on purpose. Chunk content is in the
  prompt, so §7.1's ``hash(chunk_content + prompt_version + model)`` is covered.
- **Files hold the raw response bytes, UTF-8.** Read/written as bytes so Windows
  newline translation cannot alter a response on the round trip.
- **``model`` mirrors ``inner.model``** — the wrapper is transparent to callers
  that stamp the model into keys or logs; ``inner`` stays the one source of truth.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from lecturenotes.generate.client import GenRequest, LLMClient

__all__ = ["CachedClient", "response_key"]


def response_key(prompt_version: str, model: str, prompt: str) -> str:
    """Cache key for one response: sha256 hex of the UTF-8 JSON of the triple."""
    payload = json.dumps([prompt_version, model, prompt], ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class CachedClient:
    """Caches ``inner``'s responses under ``cache_dir``, one file per key."""

    def __init__(self, inner: LLMClient, cache_dir: Path, prompt_version: str) -> None:
        self._inner = inner
        self._cache_dir = cache_dir
        self._prompt_version = prompt_version
        self.model = inner.model

    def complete(self, request: GenRequest) -> str:
        key = response_key(self._prompt_version, self.model, request.prompt)
        path = self._cache_dir / f"{key}.txt"
        if path.exists():
            return path.read_bytes().decode("utf-8")
        text = self._inner.complete(request)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
        return text
