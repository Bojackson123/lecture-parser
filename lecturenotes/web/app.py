"""The FastAPI app behind ``lecturenotes serve``.

Routes are thin: HTTP in, pydantic model out, all real work delegated to the same
library entrypoints ``cli.py`` composes. Error responses are ``{"error": message}``
with the status code carrying the category — the messages themselves are the
underlying exceptions verbatim, the CLI's no-traceback doctrine over HTTP.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from importlib.resources import files
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict
from starlette.middleware.trustedhost import TrustedHostMiddleware

from lecturenotes.align.boundaries import Chunk, align_lecture
from lecturenotes.generate.client import DEFAULT_MODEL, AnthropicClient, LLMClient
from lecturenotes.generate.lecture import merge_chunks
from lecturenotes.ingest.captions import ingest_captions
from lecturenotes.ingest.slides import Deck, ingest_slides
from lecturenotes.model import NoteWeek
from lecturenotes.pairing import CAPTION_SUFFIXES, DECK_SUFFIXES, collect_pairs, course_slug
from lecturenotes.render.anki import AnkiRenderer
from lecturenotes.render.base import Renderer, RenderOptions, RenderResult
from lecturenotes.render.markdown import MarkdownRenderer
from lecturenotes.render.notion import NotionRenderer
from lecturenotes.web.jobs import JobManager, JobRunningError, JobStatus

# The same three entries as cli._RENDERERS — pinned equal by a test, so a fourth
# renderer registered there cannot be forgotten here.
_RENDERERS: dict[str, Callable[[], Renderer]] = {
    "markdown": MarkdownRenderer,
    "anki": AnkiRenderer,
    "notion": NotionRenderer,
}

# /ws/ serves exactly what previews need: figure images, week JSON, text output.
_WS_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".json": "application/json",
    ".md": "text/markdown; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
}

_WEEK_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")

# The shell is three committed files, served from the package so an installed wheel
# works too. An allowlist, not a directory walk: nothing else can ever be served.
_STATIC_TYPES = {
    "index.html": "text/html; charset=utf-8",
    "app.js": "text/javascript; charset=utf-8",
    "style.css": "text/css; charset=utf-8",
}


def _static_bytes(name: str) -> bytes:
    return (files("lecturenotes.web") / "static" / name).read_bytes()


class _ApiModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class WeekInfo(_ApiModel):
    """One workspace ``*.json``: ``id`` is the filename stem — the addressing key for
    the render/push endpoints — never the ``NoteWeek.id`` field (files can't be
    ambiguous and need no index). Invalid files are flagged, not hidden."""

    id: str
    file: str
    mtime: float
    valid: bool
    lectures: int | None = None
    topics: int | None = None
    error: str | None = None


class StateResponse(_ApiModel):
    workspace: str
    weeks: list[WeekInfo]
    job: JobStatus | None = None


class UploadResponse(_ApiModel):
    paths: list[str]


class PairRequest(_ApiModel):
    paths: list[str]


class PairEntry(_ApiModel):
    lecture_id: str
    deck: str
    captions: str


class PairResponse(_ApiModel):
    pairs: list[PairEntry]


class SlideRangeInfo(_ApiModel):
    start: int
    end: int


class ChunkInfo(_ApiModel):
    """One row of the dry-run table. ``words`` uses the same count as the merge
    floor (whitespace split per segment), so the numbers the user sees explain the
    merges they get; ``gap`` is the §4.1 board-work signal (``slides is None``)."""

    slides: SlideRangeInfo | None
    start_s: float
    end_s: float
    words: int
    title: str | None
    gap: bool


class LectureChunks(_ApiModel):
    lecture_id: str
    deck: str
    captions: str
    chunks: list[ChunkInfo]


class DryRunRequest(_ApiModel):
    paths: list[str]
    min_words: int = 100


class DryRunResponse(_ApiModel):
    lectures: list[LectureChunks]
    total_requests: int


class BuildRequest(_ApiModel):
    """``pairs`` is the pairing the UI displayed and the user confirmed — the §7.4
    ritual in HTTP form. The server recomputes and rejects on any difference, so
    the confirm click confirms exactly what will run; there is no ``--yes``."""

    paths: list[str]
    course: str
    week: int
    min_words: int = 100
    model: str = DEFAULT_MODEL
    pairs: list[PairEntry]


class BuildAccepted(_ApiModel):
    job_id: str


_KNOWN_SUFFIXES = DECK_SUFFIXES | CAPTION_SUFFIXES


def _make_client(model: str) -> LLMClient:
    """The web layer's client seam — the cli twin (P5-04 pattern): tests monkeypatch
    this, and ``ANTHROPIC_API_KEY`` handling stays inside ``AnthropicClient``
    (consulted only on the first real ``complete``, never here, never in dry-run)."""
    return AnthropicClient(model)


def _chunk_infos(deck: Deck, chunks: list[Chunk]) -> list[ChunkInfo]:
    titles = {slide.number: slide.title for slide in deck.slides}
    infos: list[ChunkInfo] = []
    for chunk in chunks:
        slides = (
            None
            if chunk.slides is None
            else SlideRangeInfo(start=chunk.slides.start, end=chunk.slides.end)
        )
        infos.append(
            ChunkInfo(
                slides=slides,
                start_s=chunk.start_s,
                end_s=chunk.end_s,
                words=sum(len(segment.text.split()) for segment in chunk.segments),
                title=None if chunk.slides is None else titles.get(chunk.slides.start),
                gap=chunk.slides is None,
            )
        )
    return infos


def _bare_filename(name: str) -> bool:
    return bool(name) and "/" not in name and "\\" not in name and Path(name).name == name


def _resolve(workspace: Path, raw: str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else workspace / path


def _display(workspace: Path, path: Path) -> str:
    """Workspace-relative POSIX when under the workspace, else the path as-is —
    the strings shown in the pairing table and echoed back by the build request."""
    try:
        return path.relative_to(workspace).as_posix()
    except ValueError:
        return str(path)


def _pair_entries(workspace: Path, raw_paths: list[str]) -> list[PairEntry]:
    """The §7.4 pairing over request paths — ``collect_pairs`` as-is, no inference.

    Both ``/api/pair`` (what the user sees and confirms) and ``/api/build`` (what
    actually runs) go through here, so the confirm click confirms exactly the
    pairing the server would execute. Raises the ``collect_pairs`` ``ValueError``.
    """
    pairs = collect_pairs([_resolve(workspace, raw) for raw in raw_paths])
    return [
        PairEntry(
            lecture_id=lecture_id,
            deck=_display(workspace, deck),
            captions=_display(workspace, captions),
        )
        for lecture_id, deck, captions in pairs
    ]


def _scan_weeks(workspace: Path) -> list[WeekInfo]:
    weeks: list[WeekInfo] = []
    for path in sorted(workspace.glob("*.json")):
        if not path.is_file():
            continue
        mtime = path.stat().st_mtime
        try:
            week = NoteWeek.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            weeks.append(
                WeekInfo(id=path.stem, file=path.name, mtime=mtime, valid=False, error=str(exc))
            )
            continue
        weeks.append(
            WeekInfo(
                id=path.stem,
                file=path.name,
                mtime=mtime,
                valid=True,
                lectures=len(week.lectures),
                topics=sum(len(lecture.topics) for lecture in week.lectures),
            )
        )
    return weeks


def create_app(workspace: Path) -> FastAPI:
    """Build the app for one workspace directory (created if missing).

    The workspace is ``build``'s ``--out``: week JSONs, ``media/`` and ``.cache/``
    live there, plus ``uploads/`` for files that arrive through the browser.
    """
    workspace.mkdir(parents=True, exist_ok=True)
    jobs = JobManager()
    app = FastAPI(title="lecturenotes", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.jobs = jobs
    # Loopback single-user tool; the host check is the cheap DNS-rebinding guard.
    # "testserver" is fastapi.testclient's default and unreachable from outside.
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"]
    )

    @app.exception_handler(HTTPException)
    async def _error_shape(request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse({"error": str(exc.detail)}, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation_shape(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse({"error": str(exc)}, status_code=422)

    @app.get("/")
    async def index() -> Response:
        return Response(_static_bytes("index.html"), media_type=_STATIC_TYPES["index.html"])

    @app.get("/static/{name}")
    async def static_file(name: str) -> Response:
        if name not in _STATIC_TYPES or name == "index.html":
            raise HTTPException(404, f"no such static file: {name}")
        return Response(_static_bytes(name), media_type=_STATIC_TYPES[name])

    @app.get("/api/state")
    def state() -> StateResponse:
        return StateResponse(
            workspace=str(workspace), weeks=_scan_weeks(workspace), job=jobs.status()
        )

    @app.post("/api/upload")
    def upload(week: str, files: list[UploadFile]) -> UploadResponse:
        if not week or course_slug(week) != week:
            raise HTTPException(400, f"week must be a lowercase slug, got {week!r}")
        # Validate every name before writing anything — a bad batch writes nothing.
        names: list[str] = []
        for item in files:
            name = item.filename or ""
            if not _bare_filename(name):
                raise HTTPException(400, f"{name!r}: upload names must be bare filenames")
            if Path(name).suffix.lower() not in _KNOWN_SUFFIXES:
                raise HTTPException(
                    400,
                    f"{name}: not a deck (.pdf/.pptx) or a caption file (.vtt/.srt)",
                )
            names.append(name)
        target_dir = workspace / "uploads" / week
        target_dir.mkdir(parents=True, exist_ok=True)
        paths: list[str] = []
        for item, name in zip(files, names, strict=True):
            # Overwrite in place: the *real* filename drives the sorted pairing,
            # so a re-upload must replace, never rename.
            (target_dir / name).write_bytes(item.file.read())
            paths.append(f"uploads/{week}/{name}")
        return UploadResponse(paths=paths)

    @app.post("/api/pair")
    def pair(request: PairRequest) -> PairResponse:
        try:
            return PairResponse(pairs=_pair_entries(workspace, request.paths))
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/dry-run")
    def dry_run(request: DryRunRequest) -> DryRunResponse:
        # Stops before any client exists (the P5-04 doctrine over HTTP): no
        # _make_client, no CachedClient, no key consulted — pinned by tests.
        # merge_chunks here and generate_lecture's internal merge share min_words,
        # so this is exactly the chunking the real run prompts over.
        try:
            pairs = collect_pairs([_resolve(workspace, raw) for raw in request.paths])
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        lectures: list[LectureChunks] = []
        total_requests = 0
        for lecture_id, deck_path, caption_path in pairs:
            try:
                deck = ingest_slides(deck_path)
                segments = ingest_captions(caption_path)
            except (OSError, ValueError) as exc:
                raise HTTPException(422, str(exc)) from exc
            chunks = merge_chunks(align_lecture(deck, segments), request.min_words)
            total_requests += len(chunks) + 1  # + the lecture's synthesis pass
            lectures.append(
                LectureChunks(
                    lecture_id=lecture_id,
                    deck=_display(workspace, deck_path),
                    captions=_display(workspace, caption_path),
                    chunks=_chunk_infos(deck, chunks),
                )
            )
        return DryRunResponse(lectures=lectures, total_requests=total_requests)

    @app.post("/api/build", status_code=202)
    def build(request: BuildRequest) -> BuildAccepted:
        try:
            entries = _pair_entries(workspace, request.paths)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        if request.pairs != entries:
            raise HTTPException(
                400,
                "the confirmed pairing does not match what would run;"
                " re-check the pairing and confirm it again",
            )
        resolved = collect_pairs([_resolve(workspace, raw) for raw in request.paths])
        try:
            job_id = jobs.start(
                workspace=workspace,
                pairs=resolved,
                course=request.course,
                week=request.week,
                min_words=request.min_words,
                model=request.model,
                # Resolved at request time so a monkeypatched seam is what runs.
                make_client=_make_client,
            )
        except JobRunningError as exc:
            raise HTTPException(409, str(exc)) from exc
        return BuildAccepted(job_id=job_id)

    @app.get("/api/job")
    def job() -> JobStatus:
        status = jobs.status()
        if status is None:
            raise HTTPException(404, "no build has run yet")
        return status

    def _load_week(week: str) -> NoteWeek:
        if not _WEEK_ID.fullmatch(week):
            raise HTTPException(404, f"no such week: {week}")
        path = workspace / f"{week}.json"
        if not path.is_file():
            raise HTTPException(404, f"no such week: {week}")
        try:
            return NoteWeek.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/render")
    def render(week: str, format: str = "markdown") -> RenderResult:
        # Pure and free (§7.1): the same renderers the CLI selects, in-process.
        if format not in _RENDERERS:
            raise HTTPException(
                422, f"unknown format {format!r}; expected one of {sorted(_RENDERERS)}"
            )
        return _RENDERERS[format]().render(_load_week(week), RenderOptions())

    @app.get("/ws/{relpath:path}")
    def workspace_file(relpath: str) -> Response:
        target = (workspace / relpath).resolve()
        if not target.is_relative_to(workspace.resolve()):
            raise HTTPException(403, "outside the workspace")
        media_type = _WS_TYPES.get(target.suffix.lower())
        if media_type is None:
            raise HTTPException(403, f"{target.suffix or target.name}: type not served")
        if not target.is_file():
            raise HTTPException(404, f"no such file: {relpath}")
        return Response(target.read_bytes(), media_type=media_type)

    return app
