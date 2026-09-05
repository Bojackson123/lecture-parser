"""PW-06: ``/api/push`` — the Notion delivery behind the web transport seam.

Token doctrine unchanged: ``NOTION_TOKEN`` is read in the handler at request time,
never a form field, never persisted; a missing token constructs no transport.
Every transport is a ``FakeNotionTransport`` injected through ``_make_transport``.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import lecturenotes.web.app as web_app
from lecturenotes.emit.notion_api import FakeNotionTransport

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
WEEK01 = FIXTURES / "notes" / "week01.json"
ASSET = FIXTURES / "decks" / "value_iteration.png"
# The committed fixture's asset sources are repo-root-relative (P3-04), so a
# workspace acting as asset root must mirror that layout.
ASSET_RELATIVE = Path("tests/fixtures/decks/value_iteration.png")


@pytest.fixture
def staged_week(workspace: Path) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    shutil.copy(WEEK01, workspace / "week01.json")
    target = workspace / ASSET_RELATIVE
    target.parent.mkdir(parents=True)
    shutil.copy(ASSET, target)


@pytest.fixture
def transport_seam(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[FakeNotionTransport, list[str]]:
    fake = FakeNotionTransport()
    tokens: list[str] = []

    def seam(token: str) -> FakeNotionTransport:
        tokens.append(token)
        return fake

    monkeypatch.setattr(web_app, "_make_transport", seam)
    monkeypatch.setenv("NOTION_TOKEN", "secret-token")
    return fake, tokens


def _push(client: TestClient) -> object:
    return client.post(
        "/api/push", json={"week_id": "week01", "parent_page_id": "parent-1"}
    )


def test_push_without_a_token_is_409_naming_env_and_dotenv(
    client: TestClient, staged_week: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("NOTION_TOKEN", raising=False)

    def boom(token: str) -> FakeNotionTransport:
        raise AssertionError("a transport was constructed with no token")

    monkeypatch.setattr(web_app, "_make_transport", boom)
    response = _push(client)
    assert response.status_code == 409
    error = response.json()["error"]
    assert "NOTION_TOKEN" in error
    assert ".env" in error


def test_push_runs_the_emit_sequence_with_the_env_token(
    client: TestClient,
    staged_week: None,
    transport_seam: tuple[FakeNotionTransport, list[str]],
) -> None:
    fake, tokens = transport_seam
    response = _push(client)
    assert response.status_code == 200
    assert response.json() == {"title": "CS-RL-101 — Week 1", "payloads": 1, "assets": 1}
    assert tokens == ["secret-token"]
    names = [call[0] for call in fake.calls]
    assert names[0] == "find_child_page"
    assert "create_page" in names
    assert names.count("upload_file") == 1
    assert "append_children" in names


def test_push_twice_updates_the_same_page(
    client: TestClient,
    staged_week: None,
    transport_seam: tuple[FakeNotionTransport, list[str]],
) -> None:
    fake, _ = transport_seam
    assert _push(client).status_code == 200
    assert _push(client).status_code == 200
    names = [call[0] for call in fake.calls]
    assert names.count("create_page") == 1  # the second push found and updated it
    assert "list_children" in names  # the archive-then-append update branch ran


def test_push_archives_seeded_children_before_appending(
    client: TestClient,
    staged_week: None,
    transport_seam: tuple[FakeNotionTransport, list[str]],
) -> None:
    fake, _ = transport_seam
    fake.seed_page("parent-1", "CS-RL-101 — Week 1", children=("old-1", "old-2"))
    assert _push(client).status_code == 200
    names = [call[0] for call in fake.calls]
    assert "create_page" not in names
    assert names.count("archive_block") == 2


def test_push_with_a_missing_asset_is_502_before_any_transport_call(
    client: TestClient,
    workspace: Path,
    transport_seam: tuple[FakeNotionTransport, list[str]],
) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    shutil.copy(WEEK01, workspace / "week01.json")  # week staged, asset not
    fake, _ = transport_seam
    response = _push(client)
    assert response.status_code == 502
    assert "source not found" in response.json()["error"]
    assert fake.calls == []  # a bad render or missing file leaves Notion untouched


def test_push_unknown_week_is_404(
    client: TestClient, transport_seam: tuple[FakeNotionTransport, list[str]]
) -> None:
    response = client.post(
        "/api/push", json={"week_id": "nope", "parent_page_id": "parent-1"}
    )
    assert response.status_code == 404
