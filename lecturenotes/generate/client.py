"""LLM client seam (plan §8): one protocol, the real client, the recorded fake.

    GenRequest(key, prompt)      one generation request; ``key`` is a human-readable
                                 request id (``chunk:lec01:s2-2`` — P5-02 names them)
    LLMClient                    protocol: ``model`` + ``complete(request) -> str``
    AnthropicClient(model)       the real thing; SDK constructed lazily on first use
    RecordedClient(path)         the fake tests use: JSON file of key → response text

Decisions (P5-01):

- **``complete`` returns raw text; callers validate.** Response models live next to
  the prompts that promise them (P5-02), so the fake stays a dict lookup and the
  cache (``cache.py``) stays a file of plain strings.
- **The fake is keyed by ``request.key``, never by prompt hash** — prompt text is
  tuned constantly (§7.1) and hash-keying would break every recorded fixture on
  every edit. A miss raises ``KeyError`` naming the key and the file, so it says
  what to add to the fixture instead of failing mysteriously downstream.
- **Lazy SDK construction.** Importing this module, constructing the client, and
  ``--dry-run`` (P5-04) must never demand ``ANTHROPIC_API_KEY``; only a real
  ``complete`` does.
- **No streaming, no custom retries.** Responses are a few KB of JSON; the SDK
  already retries 429/5xx. A ``stop_reason == "max_tokens"`` response raises
  ``ValueError`` naming the key — truncated JSON must never reach a validator.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

import anthropic
from pydantic import BaseModel, ConfigDict

__all__ = [
    "DEFAULT_MODEL",
    "AnthropicClient",
    "GenRequest",
    "LLMClient",
    "RecordedClient",
]

DEFAULT_MODEL = "claude-opus-5"

# Comfortable headroom over a few-KB chunk response; the truncation check below is
# what turns an overrun into a named error instead of corrupt JSON.
_MAX_TOKENS = 16000


class GenRequest(BaseModel):
    """One generation request: a stable human-readable id plus the full prompt."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str
    prompt: str


class LLMClient(Protocol):
    """The seam everything in ``generate/`` talks through (plan §8)."""

    model: str

    def complete(self, request: GenRequest) -> str: ...


class AnthropicClient:
    """The real client. Constructs the SDK client lazily on first ``complete``."""

    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        self.model = model
        self._sdk: anthropic.Anthropic | None = None

    def complete(self, request: GenRequest) -> str:
        if self._sdk is None:
            self._sdk = anthropic.Anthropic()
        message = self._sdk.messages.create(
            model=self.model,
            max_tokens=_MAX_TOKENS,
            messages=[{"role": "user", "content": request.prompt}],
        )
        if message.stop_reason == "max_tokens":
            raise ValueError(
                f"response for {request.key!r} was truncated at {_MAX_TOKENS} tokens"
            )
        return "".join(block.text for block in message.content if block.type == "text")


class _MissingResponse(KeyError):
    """A ``KeyError`` whose message prints verbatim.

    Plain ``KeyError`` reprs its argument, escaping Windows path backslashes; the
    miss message must name the fixture file exactly as the shell would take it.
    """

    def __str__(self) -> str:
        return str(self.args[0])


class RecordedClient:
    """The recorded-response fake: a JSON object mapping request key → response text."""

    model = "recorded"

    def __init__(self, path: Path) -> None:
        self._path = path
        self._responses: dict[str, str] = json.loads(path.read_text(encoding="utf-8"))

    def complete(self, request: GenRequest) -> str:
        try:
            return self._responses[request.key]
        except KeyError:
            raise _MissingResponse(
                f"no recorded response for key {request.key!r} in {self._path}"
            ) from None
