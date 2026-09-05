"""Shared web-test fixtures: one app per tmp workspace, driven in-process.

``TestClient`` is the web layer's ``main([...])`` + ``capsys``: requests exercise
exactly what the served app runs, and the seams (``web.app._make_client``,
``web.app._make_transport``) are monkeypatched the same way their cli twins are.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lecturenotes.web.app import create_app


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    return tmp_path / "notes"


@pytest.fixture
def client(workspace: Path) -> TestClient:
    return TestClient(create_app(workspace))
