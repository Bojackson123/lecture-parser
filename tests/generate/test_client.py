"""P5-01 client tests (plan §8: the LLM client sits behind an interface with a
recorded-response fake; no test touches the network).

``anthropic.Anthropic`` is monkeypatched in every test that goes near the real
client, so a missing API key can never fail the suite and a test that accidentally
reaches for the network dies on the stub instead.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import anthropic
import pytest
from pydantic import ValidationError

from lecturenotes.generate.client import (
    DEFAULT_MODEL,
    AnthropicClient,
    GenRequest,
    LLMClient,
    RecordedClient,
)


def use(client: LLMClient) -> None:
    """Typed helper: the call type-checks iff the argument satisfies the protocol."""
    assert isinstance(client.model, str)


# --- GenRequest -------------------------------------------------------------------


def test_gen_request_is_frozen() -> None:
    request = GenRequest(key="chunk:lec01:s2-2", prompt="p")
    with pytest.raises(ValidationError):
        request.key = "other"  # type: ignore[misc]


def test_gen_request_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        GenRequest(key="chunk:lec01:s2-2", prompt="p", temperature=0.0)  # type: ignore[call-arg]


# --- RecordedClient ---------------------------------------------------------------


def _recorded(tmp_path: Path) -> tuple[RecordedClient, Path]:
    path = tmp_path / "responses.json"
    path.write_text(json.dumps({"chunk:lec01:s2-2": '{"x": 1}'}), encoding="utf-8")
    return RecordedClient(path), path


def test_recorded_client_serves_the_response_for_its_key(tmp_path: Path) -> None:
    client, _ = _recorded(tmp_path)
    assert client.complete(GenRequest(key="chunk:lec01:s2-2", prompt="p")) == '{"x": 1}'


def test_recorded_client_miss_names_the_key_and_the_file(tmp_path: Path) -> None:
    client, path = _recorded(tmp_path)
    with pytest.raises(KeyError) as excinfo:
        client.complete(GenRequest(key="chunk:lec99:s1-1", prompt="p"))
    message = str(excinfo.value)
    assert "chunk:lec99:s1-1" in message
    assert str(path) in message


def test_recorded_client_model_is_recorded(tmp_path: Path) -> None:
    client, _ = _recorded(tmp_path)
    assert client.model == "recorded"


def test_both_clients_satisfy_the_protocol(tmp_path: Path) -> None:
    client, _ = _recorded(tmp_path)
    use(client)
    use(AnthropicClient())


# --- AnthropicClient --------------------------------------------------------------


class _TextBlock:
    type = "text"

    def __init__(self, text: str) -> None:
        self.text = text


class _Message:
    def __init__(self, blocks: list[_TextBlock], stop_reason: str) -> None:
        self.content = blocks
        self.stop_reason = stop_reason


class _StubSDK:
    """Stands in for ``anthropic.Anthropic``: records every ``messages.create`` call."""

    def __init__(self, message: _Message) -> None:
        self._message = message
        self.calls: list[dict[str, Any]] = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs: Any) -> _Message:
        self.calls.append(kwargs)
        return self._message


def _install(monkeypatch: pytest.MonkeyPatch, message: _Message) -> _StubSDK:
    stub = _StubSDK(message)
    monkeypatch.setattr(anthropic, "Anthropic", lambda *args, **kwargs: stub)
    return stub


def test_default_model() -> None:
    assert DEFAULT_MODEL == "claude-opus-5"
    assert AnthropicClient().model == DEFAULT_MODEL


def test_construction_needs_no_sdk_and_no_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    def explode(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("the SDK client must not be constructed before complete()")

    monkeypatch.setattr(anthropic, "Anthropic", explode)
    client = AnthropicClient()
    assert client.model == DEFAULT_MODEL


def test_complete_sends_one_user_message_and_returns_the_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub = _install(monkeypatch, _Message([_TextBlock('{"x": 1}')], stop_reason="end_turn"))
    client = AnthropicClient(model="claude-opus-5")
    request = GenRequest(key="chunk:lec01:s2-2", prompt="p")
    assert client.complete(request) == '{"x": 1}'
    assert stub.calls == [
        {
            "model": "claude-opus-5",
            "max_tokens": 16000,
            "messages": [{"role": "user", "content": "p"}],
        }
    ]


def test_text_blocks_are_concatenated(monkeypatch: pytest.MonkeyPatch) -> None:
    stub = _install(
        monkeypatch, _Message([_TextBlock('{"x": '), _TextBlock("1}")], stop_reason="end_turn")
    )
    assert AnthropicClient().complete(GenRequest(key="k", prompt="p")) == '{"x": 1}'
    assert len(stub.calls) == 1


def test_truncated_response_raises_naming_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, _Message([_TextBlock('{"x"')], stop_reason="max_tokens"))
    client = AnthropicClient()
    with pytest.raises(ValueError, match="chunk:lec01:s2-2"):
        client.complete(GenRequest(key="chunk:lec01:s2-2", prompt="p"))
