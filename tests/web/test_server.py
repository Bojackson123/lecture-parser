"""PW-01: ``lecturenotes serve`` wiring and one loopback smoke test.

The wiring test monkeypatches ``web.server.serve`` (``cmd_serve`` imports it at
call time, so the patched attribute is what runs); the smoke test is the one place
a real socket binds — port 0, loopback, clean shutdown, no external network.
"""

from __future__ import annotations

import threading
import time
import urllib.request
from pathlib import Path

import pytest
import uvicorn

import lecturenotes.web.server
from lecturenotes.cli import main
from lecturenotes.web.app import create_app


def test_serve_wires_port_workspace_and_browser_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    def fake_serve(*, port: int, workspace: Path, open_browser: bool) -> None:
        calls.append({"port": port, "workspace": workspace, "open_browser": open_browser})

    monkeypatch.setattr(lecturenotes.web.server, "serve", fake_serve)
    assert main(["serve", "--no-browser", "--port", "1234", "-o", "wk"]) == 0
    assert calls == [{"port": 1234, "workspace": Path("wk"), "open_browser": False}]


def test_serve_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_serve(*, port: int, workspace: Path, open_browser: bool) -> None:
        calls.append({"port": port, "workspace": workspace, "open_browser": open_browser})

    monkeypatch.setattr(lecturenotes.web.server, "serve", fake_serve)
    assert main(["serve"]) == 0
    assert calls == [{"port": 8765, "workspace": Path("notes"), "open_browser": True}]


def test_loopback_smoke(workspace: Path) -> None:
    """Bind port 0 on 127.0.0.1, GET the shell over a real socket, shut down."""
    app = create_app(workspace)
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not server.started:
        assert time.monotonic() < deadline, "server did not start"
        assert thread.is_alive(), "server thread died during startup"
        time.sleep(0.01)
    port = server.servers[0].sockets[0].getsockname()[1]
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as response:
            assert response.status == 200
            assert b"lecturenotes" in response.read()
    finally:
        server.should_exit = True
        thread.join(timeout=15)
    assert not thread.is_alive()
