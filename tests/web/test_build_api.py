"""PW-04: ``/api/build`` + ``/api/job`` — the §7.4 confirm-echo and the §7.1 budget.

The request carries the pairing the user confirmed; the server recomputes and
rejects on any difference, so the confirm click confirms exactly what runs. The
client seam is monkeypatched with the recorded fake, the cli tests' pattern.
"""

from __future__ import annotations

import shutil
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import lecturenotes.web.app as web_app
from lecturenotes.cli import main
from lecturenotes.generate.client import GenRequest, RecordedClient
from lecturenotes.web.jobs import JobManager

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
RESPONSES = FIXTURES / "generate" / "lecture01.responses.json"

_TIMEOUT = 60.0


@pytest.fixture
def recorded_seam(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """The counting recorded fake behind the web seam; yields the call counter."""
    counter = [0]

    class _Counting:
        def __init__(self) -> None:
            self._inner = RecordedClient(RESPONSES)
            self.model = self._inner.model

        def complete(self, request: GenRequest) -> str:
            counter[0] += 1
            return self._inner.complete(request)

    monkeypatch.setattr(web_app, "_make_client", lambda model: _Counting())
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    return counter


def _stage(workspace: Path) -> list[str]:
    uploads = workspace / "uploads" / "w"
    uploads.mkdir(parents=True)
    shutil.copy(FIXTURES / "decks" / "lecture01.pptx", uploads / "lecture01.pptx")
    shutil.copy(FIXTURES / "captions" / "lecture01.vtt", uploads / "lecture01.vtt")
    return ["uploads/w"]


def _build_body(client: TestClient, paths: list[str]) -> dict[str, object]:
    pairs = client.post("/api/pair", json={"paths": paths}).json()["pairs"]
    return {"paths": paths, "course": "CS-RL-101", "week": 1, "pairs": pairs}


def _manager(client: TestClient) -> JobManager:
    manager = client.app.state.jobs  # type: ignore[attr-defined]
    assert isinstance(manager, JobManager)
    return manager


def test_build_runs_to_done_and_render_accepts_the_output(
    client: TestClient,
    workspace: Path,
    recorded_seam: list[int],
    capsys: pytest.CaptureFixture[str],
) -> None:
    body = _build_body(client, _stage(workspace))
    response = client.post("/api/build", json=body)
    assert response.status_code == 202
    job_id = response.json()["job_id"]

    _manager(client).wait(timeout=_TIMEOUT)
    status = client.get("/api/job").json()
    assert status["id"] == job_id
    assert status["state"] == "done"
    assert status["done"] == 5 and status["total"] == 5
    assert recorded_seam[0] == 5  # the §7.1 budget, uncached first run
    assert status["result"]["week_id"] == "cs-rl-101-w01"
    assert status["result"] == {
        "week_id": "cs-rl-101-w01",
        "file": "cs-rl-101-w01.json",
        "lectures": 1,
        "topics": 4,
        "assets": 1,
    }

    target = workspace / "cs-rl-101-w01.json"
    assert target.is_file()
    assert list((workspace / "media").glob("img-*.png"))  # assets minted next to it
    assert main(["render", str(target)]) == 0
    capsys.readouterr()  # the rendered document is not this test's concern

    # The finished job also shows up in /api/state for page reloads.
    assert client.get("/api/state").json()["job"]["id"] == job_id


def test_build_without_a_matching_pairs_echo_is_400_and_starts_nothing(
    client: TestClient, workspace: Path, recorded_seam: list[int]
) -> None:
    body = _build_body(client, _stage(workspace))
    tampered = dict(body)
    (pair,) = list(body["pairs"])  # type: ignore[arg-type]
    tampered["pairs"] = [dict(pair, captions="uploads/w/other.vtt")]
    response = client.post("/api/build", json=tampered)
    assert response.status_code == 400
    assert "pairing" in response.json()["error"]
    assert client.get("/api/job").status_code == 404
    assert recorded_seam[0] == 0


def test_build_with_a_pairing_error_is_400(
    client: TestClient, workspace: Path, recorded_seam: list[int]
) -> None:
    (workspace / "empty").mkdir()
    response = client.post(
        "/api/build",
        json={"paths": ["empty"], "course": "C", "week": 1, "pairs": []},
    )
    assert response.status_code == 400
    assert response.json()["error"] == "no decks or caption files found"


def test_job_before_any_build_is_404(client: TestClient) -> None:
    response = client.get("/api/job")
    assert response.status_code == 404
    assert response.json()["error"]


def test_a_second_build_while_one_runs_is_409(
    client: TestClient, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    entered = threading.Event()
    release = threading.Event()

    class _GatedRecorded:
        def __init__(self) -> None:
            self._inner = RecordedClient(RESPONSES)
            self.model = self._inner.model

        def complete(self, request: GenRequest) -> str:
            entered.set()
            assert release.wait(timeout=_TIMEOUT)
            return self._inner.complete(request)

    monkeypatch.setattr(web_app, "_make_client", lambda model: _GatedRecorded())
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    body = _build_body(client, _stage(workspace))
    first = client.post("/api/build", json=body)
    assert first.status_code == 202
    assert entered.wait(timeout=_TIMEOUT)
    try:
        second = client.post("/api/build", json=body)
        assert second.status_code == 409
        assert first.json()["job_id"] in second.json()["error"]
    finally:
        release.set()
        _manager(client).wait(timeout=_TIMEOUT)
