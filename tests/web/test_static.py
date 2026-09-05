"""PW-01: the static shell — served from the package, allowlisted, host-checked.

The files come through ``importlib.resources``, never a cwd-relative path, so these
tests also pin that an installed wheel (hatchling packages ``static/`` as package
data) can serve the shell.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from lecturenotes.web.app import create_app


def test_index_is_the_html_shell(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "lecturenotes" in response.text
    assert "/static/app.js" in response.text


def test_js_and_css_served_with_their_content_types(client: TestClient) -> None:
    js = client.get("/static/app.js")
    css = client.get("/static/style.css")
    assert js.status_code == 200
    assert js.headers["content-type"].startswith("text/javascript")
    assert css.status_code == 200
    assert css.headers["content-type"].startswith("text/css")


def test_unknown_static_name_is_404_with_error_shape(client: TestClient) -> None:
    response = client.get("/static/secrets.txt")
    assert response.status_code == 404
    assert "secrets.txt" in response.json()["error"]


def test_traversal_is_not_served(client: TestClient) -> None:
    # The allowlist admits exactly three names; index.html is reachable only at /.
    assert client.get("/static/index.html").status_code == 404
    assert client.get("/static/..%2Fapp.py").status_code == 404


def test_foreign_host_header_is_rejected(client: TestClient) -> None:
    # The DNS-rebinding guard: a page on an attacker's domain resolving to
    # 127.0.0.1 sends its own Host header and must not reach the API.
    response = client.get("/", headers={"host": "evil.example"})
    assert response.status_code == 400


def test_create_app_creates_the_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "deep" / "notes"
    create_app(workspace)
    assert workspace.is_dir()
