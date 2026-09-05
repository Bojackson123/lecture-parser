"""The FastAPI app behind ``lecturenotes serve``.

Routes are thin: HTTP in, pydantic model out, all real work delegated to the same
library entrypoints ``cli.py`` composes. Error responses are ``{"error": message}``
with the status code carrying the category — the messages themselves are the
underlying exceptions verbatim, the CLI's no-traceback doctrine over HTTP.
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict
from starlette.middleware.trustedhost import TrustedHostMiddleware

from lecturenotes.model import NoteWeek
from lecturenotes.pairing import CAPTION_SUFFIXES, DECK_SUFFIXES, collect_pairs, course_slug

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


_KNOWN_SUFFIXES = DECK_SUFFIXES | CAPTION_SUFFIXES


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
    app = FastAPI(title="lecturenotes", docs_url=None, redoc_url=None, openapi_url=None)
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
        return StateResponse(workspace=str(workspace), weeks=_scan_weeks(workspace))

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

    return app
