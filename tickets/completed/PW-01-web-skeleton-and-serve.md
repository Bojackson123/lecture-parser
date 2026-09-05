# PW-01 — `pairing.py` extraction, `web/` skeleton, `serve` subcommand, 5th contract
Side-track W · Depends on: P7-05 · Size: M

## Goal

`lecturenotes serve --no-browser` starts a local FastAPI server on 127.0.0.1:8765
serving the static UI shell, with the web stack installed as an optional extra and
the boundary rules extended so nothing in the pipeline can ever import the web
layer. The sorted-filename pairing helpers move out of `cli.py` into a shared
`lecturenotes/pairing.py` so both frontends call the same library code.

## Scope

**In**
- `lecturenotes/pairing.py`: `collect_pairs()`, `course_slug()`, the suffix sets —
  moved verbatim from `cli.py`; `cli.py` re-imports them under their old private
  names so every call site and test is untouched.
- `pyproject.toml`: `[project.optional-dependencies] web = [fastapi, uvicorn,
  python-multipart]`; `httpx` in the dev group (TestClient transport, test-only);
  5th import-linter contract ("nothing in the pipeline imports the web layer").
- `lecturenotes/web/`: `__init__.py`, `app.py` (`create_app(workspace) -> FastAPI`
  serving `/` and `/static/*` from `web/static/` via `importlib.resources`, plus a
  Host-header guard), `server.py` (`serve(port, workspace, open_browser)` running
  uvicorn on 127.0.0.1), `static/index.html` + `app.js` + `style.css` (shell).
- `cli.py`: `serve [--port N] [-o DIR] [--no-browser]` subparser + `cmd_serve`,
  lazily importing `web.server`; `ModuleNotFoundError` → install hint, exit 2.
- `tests/web/`: static-shell and serve-wiring tests; one loopback smoke test.

**Out
- Every `/api/*` endpoint beyond the shell → PW-02..PW-06.
- Any pipeline logic in `web/` — it composes entrypoints only, forever.

## Tasks

1. Move `_collect_pairs`/`_course_slug`/suffix sets to `lecturenotes/pairing.py`
   (public names, docstrings intact); re-import in `cli.py` under the old names.
2. `pyproject.toml`: web extra, httpx in dev, 5th contract (source = the six
   pipeline packages + `pairing`; forbidden = `web`; `cli` deliberately excluded).
3. `web/app.py`: `create_app`, static serving via `importlib.resources` with a
   filename allowlist, `TrustedHostMiddleware` (localhost + testserver).
4. `web/server.py`: `serve()` — uvicorn on 127.0.0.1, `webbrowser.open` unless
   suppressed; `cli.py`: subparser + `cmd_serve`.
5. Tests first: shell served with the right content types; unknown static name →
   404; foreign Host header rejected; `serve` wiring (monkeypatched `serve`);
   loopback smoke test (uvicorn on port 0, GET `/`, clean shutdown).

## Acceptance criteria

- `uv run lecturenotes serve --no-browser` prints the URL and binds
  http://127.0.0.1:8765; Ctrl+C stops it.
- With the extra absent, `serve` prints `run \`uv sync --extra web\`` to stderr
  and exits 2 (manual check — tests always have the extra installed).
- `uv run lint-imports` reports 5 contracts, 0 broken.
- Whole existing suite passes unchanged; every CLAUDE.md smoke command's output is
  byte-identical.

## Decisions & notes

- **The web stack is an optional extra, not a runtime dep** — the P7-04 doctrine
  (pipeline needs no server). FastAPI over stdlib `http.server` was an explicit
  user decision (2026-09-04): nicer ergonomics and testability were judged worth
  the optional dependency footprint.
- **`pairing.py` is a move, not a copy** — one implementation of §7.4 for both
  frontends; `web` never imports `cli`, keeping "the web layer calls the library"
  honest.
- **`testserver` is in the allowed hosts** so the TestClient exercises the same
  middleware path production uses; it is unreachable from outside the process.
