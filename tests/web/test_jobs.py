"""PW-04: the job state machine, driven directly — no HTTP, no sleeps.

Synchronisation is by events inside a gated client, never by polling with sleeps:
``entered[i]`` fires at the start of the i-th ``complete``, which the pipeline only
reaches after the previous tick, so intermediate ``done`` counts are deterministic.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from lecturenotes.generate.client import GenRequest, RecordedClient
from lecturenotes.web.jobs import JobManager, JobRunningError, ProgressClient

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
PPTX = FIXTURES / "decks" / "lecture01.pptx"
VTT = FIXTURES / "captions" / "lecture01.vtt"
RESPONSES = FIXTURES / "generate" / "lecture01.responses.json"

_TIMEOUT = 60.0


class _Gated:
    """A recorded client whose calls block until the test releases them."""

    def __init__(self, path: Path, calls: int = 8) -> None:
        self._inner = RecordedClient(path)
        self.model = self._inner.model
        self.entered = [threading.Event() for _ in range(calls)]
        self.release = [threading.Event() for _ in range(calls)]
        self._index = 0

    def complete(self, request: GenRequest) -> str:
        index = self._index
        self._index += 1
        self.entered[index].set()
        assert self.release[index].wait(timeout=_TIMEOUT), "test never released the gate"
        return self._inner.complete(request)


def _start(manager: JobManager, workspace: Path, make_client: object) -> str:
    return manager.start(
        workspace=workspace,
        pairs=[("lec01", PPTX, VTT)],
        course="CS-RL-101",
        week=1,
        min_words=100,
        model="claude-opus-5",
        make_client=make_client,  # type: ignore[arg-type]
    )


def test_progress_ticks_once_per_complete(tmp_path: Path) -> None:
    manager = JobManager()
    gated = _Gated(RESPONSES)
    job_id = _start(manager, tmp_path / "notes", lambda model: gated)

    assert gated.entered[0].wait(timeout=_TIMEOUT)
    status = manager.status()
    assert status is not None
    assert status.id == job_id
    assert status.state == "running"
    assert status.phase == "generating"
    assert status.done == 0
    assert status.total == 5  # 4 merged chunks + 1 synthesis
    assert status.current is not None and status.current.startswith("chunk:")

    gated.release[0].set()
    assert gated.entered[1].wait(timeout=_TIMEOUT)
    status = manager.status()
    assert status is not None and status.done == 1

    for event in gated.release[1:]:
        event.set()
    manager.wait(timeout=_TIMEOUT)
    status = manager.status()
    assert status is not None
    assert status.state == "done"
    assert status.done == 5 and status.total == 5
    assert status.error is None
    assert status.result is not None
    assert status.result.week_id == "cs-rl-101-w01"


def test_a_second_start_raises_while_running(tmp_path: Path) -> None:
    manager = JobManager()
    gated = _Gated(RESPONSES)
    job_id = _start(manager, tmp_path / "notes", lambda model: gated)
    assert gated.entered[0].wait(timeout=_TIMEOUT)
    with pytest.raises(JobRunningError) as excinfo:
        _start(manager, tmp_path / "notes", lambda model: gated)
    assert excinfo.value.job_id == job_id
    assert job_id in str(excinfo.value)
    for event in gated.release:
        event.set()
    manager.wait(timeout=_TIMEOUT)


def test_a_finished_job_allows_the_next(tmp_path: Path) -> None:
    manager = JobManager()
    first = _start(manager, tmp_path / "notes", lambda model: RecordedClient(RESPONSES))
    manager.wait(timeout=_TIMEOUT)
    second = _start(manager, tmp_path / "notes", lambda model: RecordedClient(RESPONSES))
    manager.wait(timeout=_TIMEOUT)
    assert first != second
    status = manager.status()
    assert status is not None and status.id == second and status.state == "done"


def test_a_failed_ingest_records_the_message(tmp_path: Path) -> None:
    manager = JobManager()
    manager.start(
        workspace=tmp_path / "notes",
        pairs=[("lec01", tmp_path / "missing.pptx", VTT)],
        course="CS-RL-101",
        week=1,
        min_words=100,
        model="claude-opus-5",
        make_client=RecordedClient,  # type: ignore[arg-type]  # never reached
    )
    manager.wait(timeout=_TIMEOUT)
    status = manager.status()
    assert status is not None
    assert status.state == "failed"
    assert status.error and "missing.pptx" in status.error
    assert status.result is None


def test_cache_hits_tick_progress_without_the_inner_client(tmp_path: Path) -> None:
    """ProgressClient wraps the cache outermost: a fully cached rebuild still
    counts 0 → 5, and the inner client is never asked to complete anything."""
    workspace = tmp_path / "notes"
    manager = JobManager()
    _start(manager, workspace, lambda model: RecordedClient(RESPONSES))
    manager.wait(timeout=_TIMEOUT)

    class _Boom:
        model = "recorded"  # matches the first run so the cache keys line up

        def complete(self, request: GenRequest) -> str:
            raise AssertionError("cache hit expected — the inner client was consulted")

    _start(manager, workspace, lambda model: _Boom())
    manager.wait(timeout=_TIMEOUT)
    status = manager.status()
    assert status is not None
    assert status.state == "done"
    assert status.done == 5 and status.total == 5


def test_progress_client_reports_around_each_complete() -> None:
    events: list[str] = []
    inner = RecordedClient(RESPONSES)
    client = ProgressClient(
        inner,
        on_start=lambda key: events.append(f"start {key}"),
        on_finish=lambda key: events.append(f"finish {key}"),
    )
    assert client.model == inner.model
    key = "synthesis:lec01"  # always in the recorded fixture
    text = client.complete(GenRequest(key=key, prompt="ignored"))
    assert text == inner.complete(GenRequest(key=key, prompt="ignored"))
    assert events == [f"start {key}", f"finish {key}"]
