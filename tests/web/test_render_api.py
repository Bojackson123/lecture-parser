"""PW-05: ``/api/render`` + ``/ws/`` — the §7.1 tuning loop over HTTP.

``/api/render`` must equal the CLI's ``render --json`` per format: both compose the
same pure renderers over the same week JSON, so any drift is a bug in one of them.
``/ws/`` serves workspace files read-only so ``media/`` figures display; the
resolved path must stay inside the workspace.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lecturenotes import cli
from lecturenotes.cli import main
from lecturenotes.web import app as web_app

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
WEEK01 = FIXTURES / "notes" / "week01.json"


@pytest.fixture
def staged(workspace: Path) -> Path:
    workspace.mkdir(parents=True, exist_ok=True)
    return Path(shutil.copy(WEEK01, workspace / "week01.json"))


def test_render_table_matches_the_cli_registry() -> None:
    assert web_app._RENDERERS == cli._RENDERERS


@pytest.mark.parametrize("fmt", ["markdown", "anki", "notion"])
def test_render_equals_the_cli_render_json(
    client: TestClient,
    staged: Path,
    fmt: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["render", str(staged), "--json", "--format", fmt]) == 0
    expected = json.loads(capsys.readouterr().out)
    response = client.get(f"/api/render?week=week01&format={fmt}")
    assert response.status_code == 200
    assert response.json() == expected


def test_render_defaults_to_markdown(client: TestClient, staged: Path) -> None:
    default = client.get("/api/render?week=week01")
    markdown = client.get("/api/render?week=week01&format=markdown")
    assert default.json() == markdown.json()


def test_render_unknown_week_is_404(client: TestClient) -> None:
    response = client.get("/api/render?week=nope")
    assert response.status_code == 404
    assert "nope" in response.json()["error"]


def test_render_traversal_week_id_is_404_not_a_file_read(
    client: TestClient, workspace: Path
) -> None:
    (workspace.parent / "outside.json").write_text("{}", encoding="utf-8")
    response = client.get("/api/render?week=..%2Foutside")
    assert response.status_code == 404


def test_render_unknown_format_is_422(client: TestClient, staged: Path) -> None:
    response = client.get("/api/render?week=week01&format=pdf")
    assert response.status_code == 422
    assert "pdf" in response.json()["error"]


def test_render_invalid_week_json_is_422(client: TestClient, workspace: Path) -> None:
    (workspace / "broken.json").write_text("{not json", encoding="utf-8")
    response = client.get("/api/render?week=broken")
    assert response.status_code == 422


# --- /ws/ --------------------------------------------------------------------------


def test_ws_serves_a_media_file_byte_equal(client: TestClient, workspace: Path) -> None:
    source = FIXTURES / "decks" / "value_iteration.png"
    (workspace / "media").mkdir(parents=True)
    shutil.copy(source, workspace / "media" / "figure.png")
    response = client.get("/ws/media/figure.png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content == source.read_bytes()


def test_ws_traversal_is_403(client: TestClient, workspace: Path) -> None:
    secret = workspace.parent / "secret.txt"
    secret.write_text("s", encoding="utf-8")
    response = client.get("/ws/..%2Fsecret.txt")
    assert response.status_code == 403


def test_ws_absolute_path_is_403(client: TestClient, tmp_path: Path) -> None:
    outside = tmp_path / "outside.txt"
    outside.write_text("s", encoding="utf-8")
    response = client.get("/ws/" + str(outside).replace("\\", "%5C").replace("/", "%2F"))
    assert response.status_code == 403


def test_ws_missing_file_is_404(client: TestClient) -> None:
    assert client.get("/ws/media/none.png").status_code == 404


def test_ws_disallowed_type_is_403(client: TestClient, workspace: Path) -> None:
    (workspace / "notes.py").write_text("x = 1", encoding="utf-8")
    response = client.get("/ws/notes.py")
    assert response.status_code == 403
