"""Build jobs: one at a time, progress ticked once per LLM ``complete()``.

The worker thread runs exactly the ``cmd_build`` real-run composition — ingest →
align → ``generate_lecture`` with a ``CachedClient`` — with one addition:
``ProgressClient`` wraps the cache **outermost**, so every request (cache hit or
miss) ticks ``done`` and a fully cached rebuild races through the bar instead of
looking stuck. Totals are known before generation starts: ``merge_chunks`` per
lecture (same floor as the real merge) plus one synthesis each, the §7.1 budget.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from lecturenotes.align.boundaries import align_lecture
from lecturenotes.generate.cache import CachedClient
from lecturenotes.generate.client import GenRequest, LLMClient
from lecturenotes.generate.lecture import generate_lecture, merge_chunks
from lecturenotes.generate.prompts import PROMPT_VERSION
from lecturenotes.ingest.captions import ingest_captions
from lecturenotes.ingest.slides import ingest_slides
from lecturenotes.model import NoteWeek, SourceRef
from lecturenotes.pairing import course_slug


class JobResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    week_id: str
    file: str
    lectures: int
    topics: int
    assets: int


class JobStatus(BaseModel):
    """A point-in-time snapshot; ``GET /api/job`` returns one per poll."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    state: Literal["running", "done", "failed"]
    course: str
    week: int
    phase: Literal["ingesting", "generating", "writing"]
    done: int
    total: int | None = None
    current: str | None = None
    error: str | None = None
    result: JobResult | None = None


class JobRunningError(RuntimeError):
    """Raised by ``start`` while a job is live — one build at a time, on purpose."""

    def __init__(self, job_id: str) -> None:
        super().__init__(f"a build is already running ({job_id})")
        self.job_id = job_id


class ProgressClient:
    """An ``LLMClient`` that reports around each ``complete``.

    ``on_start(key)`` fires before delegating (the UI's "current request"),
    ``on_finish(key)`` after (the tick). Wrap it around the ``CachedClient``, never
    inside it, so cache hits tick too.
    """

    def __init__(
        self,
        inner: LLMClient,
        *,
        on_start: Callable[[str], None],
        on_finish: Callable[[str], None],
    ) -> None:
        self._inner = inner
        self.model = inner.model
        self._on_start = on_start
        self._on_finish = on_finish

    def complete(self, request: GenRequest) -> str:
        self._on_start(request.key)
        text = self._inner.complete(request)
        self._on_finish(request.key)
        return text


@dataclass
class _JobFields:
    """The one mutable record behind the immutable snapshots, guarded by the lock."""

    id: str
    state: Literal["running", "done", "failed"]
    course: str
    week: int
    phase: Literal["ingesting", "generating", "writing"] = "ingesting"
    done: int = 0
    total: int | None = None
    current: str | None = None
    error: str | None = None
    result: JobResult | None = None


class JobManager:
    """At most one live job; the last finished one is kept so the UI can show the
    result across page reloads. All mutation happens under one lock; ``status()``
    returns immutable snapshots."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._counter = 0
        self._fields: _JobFields | None = None

    def status(self) -> JobStatus | None:
        with self._lock:
            if self._fields is None:
                return None
            fields = self._fields
            return JobStatus(
                id=fields.id,
                state=fields.state,
                course=fields.course,
                week=fields.week,
                phase=fields.phase,
                done=fields.done,
                total=fields.total,
                current=fields.current,
                error=fields.error,
                result=fields.result,
            )

    def wait(self, timeout: float | None = None) -> None:
        """Join the current worker thread — for tests and orderly shutdown."""
        thread = self._thread
        if thread is not None:
            thread.join(timeout)

    def start(
        self,
        *,
        workspace: Path,
        pairs: list[tuple[str, Path, Path]],
        course: str,
        week: int,
        min_words: int,
        model: str,
        make_client: Callable[[str], LLMClient],
    ) -> str:
        with self._lock:
            if self._fields is not None and self._fields.state == "running":
                raise JobRunningError(self._fields.id)
            self._counter += 1
            job_id = f"job-{self._counter}"
            self._fields = _JobFields(id=job_id, state="running", course=course, week=week)
            thread = threading.Thread(
                target=self._run,
                args=(job_id,),
                kwargs={
                    "workspace": workspace,
                    "pairs": pairs,
                    "course": course,
                    "week": week,
                    "min_words": min_words,
                    "model": model,
                    "make_client": make_client,
                },
                name=f"lecturenotes-{job_id}",
                daemon=True,
            )
            self._thread = thread
        thread.start()
        return job_id

    def _update(self, job_id: str, **changes: object) -> None:
        with self._lock:
            if self._fields is None or self._fields.id != job_id:
                return  # a stale thread never touches a newer job
            for key, value in changes.items():
                setattr(self._fields, key, value)

    def _advance(self, job_id: str) -> None:
        with self._lock:
            if self._fields is None or self._fields.id != job_id:
                return
            self._fields.done += 1

    def _run(
        self,
        job_id: str,
        *,
        workspace: Path,
        pairs: list[tuple[str, Path, Path]],
        course: str,
        week: int,
        min_words: int,
        model: str,
        make_client: Callable[[str], LLMClient],
    ) -> None:
        try:
            ingested = []
            total = 0
            for lecture_id, deck_path, caption_path in pairs:
                self._update(job_id, phase="ingesting", current=lecture_id)
                deck = ingest_slides(deck_path)
                segments = ingest_captions(caption_path)
                chunks = align_lecture(deck, segments)
                # Same floor as generate_lecture's internal merge — the total the
                # bar counts to is exactly the number of completes that will run.
                total += len(merge_chunks(chunks, min_words)) + 1
                ingested.append((lecture_id, deck_path, caption_path, deck, chunks))
            self._update(job_id, phase="generating", total=total, current=None)
            client = ProgressClient(
                CachedClient(make_client(model), workspace / ".cache", PROMPT_VERSION),
                on_start=lambda key: self._update(job_id, current=key),
                on_finish=lambda key: self._advance(job_id),
            )
            lectures = []
            for lecture_id, deck_path, caption_path, deck, chunks in ingested:
                lectures.append(
                    generate_lecture(
                        deck,
                        chunks,
                        lecture_id=lecture_id,
                        source=SourceRef(
                            deck_path=deck_path.as_posix(),
                            caption_path=caption_path.as_posix(),
                        ),
                        client=client,
                        out_dir=workspace,
                        min_words=min_words,
                    )
                )
            self._update(job_id, phase="writing", current=None)
            week_model = NoteWeek(
                id=f"{course_slug(course)}-w{week:02d}",
                course=course,
                week_number=week,
                lectures=lectures,
            )
            workspace.mkdir(parents=True, exist_ok=True)
            target = workspace / f"{week_model.id}.json"
            # Bytes, not write_text: the week01.json convention is UTF-8 + LF.
            target.write_bytes((week_model.model_dump_json(indent=2) + "\n").encode("utf-8"))
            result = JobResult(
                week_id=week_model.id,
                file=target.name,
                lectures=len(week_model.lectures),
                topics=sum(len(lecture.topics) for lecture in week_model.lectures),
                assets=sum(len(lecture.assets) for lecture in week_model.lectures),
            )
            self._update(job_id, state="done", result=result)
        except Exception as exc:  # noqa: BLE001 — a stuck "running" job is worse:
            # (OSError, ValueError) is the cmd_build surface; anything else is a bug
            # whose message must still reach the UI instead of killing the thread.
            self._update(job_id, state="failed", error=str(exc))
