"""The FastAPI app behind ``lecturenotes serve``.

Routes are thin: HTTP in, pydantic model out, all real work delegated to the same
library entrypoints ``cli.py`` composes. Error responses are ``{"error": message}``
with the status code carrying the category — the messages themselves are the
underlying exceptions verbatim, the CLI's no-traceback doctrine over HTTP.
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.trustedhost import TrustedHostMiddleware

# The shell is three committed files, served from the package so an installed wheel
# works too. An allowlist, not a directory walk: nothing else can ever be served.
_STATIC_TYPES = {
    "index.html": "text/html; charset=utf-8",
    "app.js": "text/javascript; charset=utf-8",
    "style.css": "text/css; charset=utf-8",
}


def _static_bytes(name: str) -> bytes:
    return (files("lecturenotes.web") / "static" / name).read_bytes()


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

    @app.get("/")
    async def index() -> Response:
        return Response(_static_bytes("index.html"), media_type=_STATIC_TYPES["index.html"])

    @app.get("/static/{name}")
    async def static_file(name: str) -> Response:
        if name not in _STATIC_TYPES or name == "index.html":
            raise HTTPException(404, f"no such static file: {name}")
        return Response(_static_bytes(name), media_type=_STATIC_TYPES[name])

    return app
