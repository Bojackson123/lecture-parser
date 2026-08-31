# P0-01 — Repo, toolchain, package skeleton, CLAUDE.md
Phase 0 · Depends on: — · Size: M

## Goal

Turn the bare `PROJECT_PLAN.md` directory into a git repo with a working Python 3.12 /
uv toolchain, the exact package layout from plan §5 (all packages empty), a minimal CLI
entrypoint, one smoke test, and a `CLAUDE.md` carrying the invariants from plan §10.
After this ticket every other ticket has a place to put code and a green baseline to
keep green.

## Scope

**In**
- `git init` and an initial commit.
- `pyproject.toml`, `uv.lock`, ruff/mypy/pytest configuration.
- Package skeleton per plan §5 with empty `__init__.py` files.
- `lecturenotes/cli.py` with `--version` only.
- `README.md` stub.
- `CLAUDE.md` with plan §2.2 and §7.2 verbatim plus the boundary rules and check commands.
- `tests/test_smoke.py`.

**Out**
- Any model types → P0-02.
- Fixtures → P0-03, P0-04.
- import-linter *contracts* (the dependency is installed here; contracts and the test
  wrapper are P0-04).
- CI workflow (no remote exists yet), pre-commit hooks.

## Tasks

1. `git init`. Add `.gitignore` covering Python bytecode, `.venv/`, `.pytest_cache/`,
   `.mypy_cache/`, `.ruff_cache/`, `dist/`, `*.egg-info/`. Do **not** ignore `uv.lock`.
2. Write `pyproject.toml`:
   - `[project]` name `lecturenotes`, version `0.0.1`, `requires-python = ">=3.12"`,
     `dependencies = ["pydantic>=2"]`.
   - `[project.scripts] lecturenotes = "lecturenotes.cli:main"`.
   - `[dependency-groups] dev = ["pytest", "ruff", "mypy", "import-linter"]`.
   - Build backend: hatchling (or uv's default), packages = `["lecturenotes"]`.
   - `[tool.ruff]` line-length 100; `[tool.ruff.lint] select = ["E", "F", "I", "UP", "B"]`.
   - `[tool.mypy] strict = true`, `files = ["lecturenotes"]`, `plugins = ["pydantic.mypy"]`.
   - `[tool.pytest.ini_options] testpaths = ["tests"]`.
3. `uv sync` and commit `uv.lock`.
4. Create the skeleton exactly as plan §5 lays it out:
   ```
   lecturenotes/__init__.py          # defines __version__
   lecturenotes/model/__init__.py
   lecturenotes/ingest/__init__.py
   lecturenotes/align/__init__.py
   lecturenotes/generate/__init__.py
   lecturenotes/render/__init__.py
   lecturenotes/emit/__init__.py
   lecturenotes/cli.py
   tests/__init__.py
   tests/fixtures/.gitkeep
   tests/contract/__init__.py
   ```
   Each subpackage `__init__.py` gets a one-line module docstring naming what plan §5
   says will live there (e.g. `"""Caption, slide and video ingestion (plan §3, stages 1–3)."""`).
5. `lecturenotes/cli.py`: `main(argv: list[str] | None = None) -> int` using `argparse`,
   supporting only `--version` (prints `lecturenotes <__version__>`). Running with no
   arguments prints help and returns 0. No subcommands yet — `build --dry-run` is Phase 5.
6. `README.md`: one paragraph pointing at `PROJECT_PLAN.md`, then the check commands.
7. `CLAUDE.md`, in this order:
   - One-line project description and a pointer to `PROJECT_PLAN.md` and `tickets/README.md`.
   - **"The note IR"** — plan §2.2 copied verbatim (the code block *and* the "Notable choices" bullets).
   - **"Stable IDs"** — plan §7.2 copied verbatim.
   - **"Boundary rules"** — `model/` imports nothing else in the package; `render/` never
     imports `ingest/`. Note that import-linter enforces these (from P0-04 on).
   - **"Checks"** — `uv run pytest`, `uv run ruff check .`, `uv run mypy`, `uv run lint-imports`.
   - **"Working conventions"** — one phase per session; tests first for done-criteria;
     when the IR must change, change `model/` and let mypy find the breakage (plan §10).
8. `tests/test_smoke.py`: imports `lecturenotes`, asserts `__version__` is a non-empty
   string, and asserts `cli.main(["--version"])` returns 0.
9. Run all checks, then commit.

## Acceptance criteria

- `uv sync` completes with no errors on a clean clone.
- `uv run pytest` → 1 passed.
- `uv run ruff check .` → no findings. `uv run mypy` → `Success: no issues found`.
- `uv run lecturenotes --version` prints `lecturenotes 0.0.1`.
- `git log --oneline` shows at least one commit; `git status` is clean.
- `tree lecturenotes tests` matches the layout in Task 4 (plus `cli.py`).
- `CLAUDE.md` contains the §2.2 code block and the §7.2 paragraph byte-for-byte
  (verify with a diff against the corresponding lines of `PROJECT_PLAN.md`).

## Decisions & notes

- **pydantic v2 for the IR** (chosen over dataclasses): free JSON round-trip for the
  LLM cache (plan §7.1), fixtures, and snapshot tests, at the cost of one runtime
  dependency in `model/`. The boundary rule is about *internal* imports; third-party
  deps in `model/` are fine.
- **mypy strict from day one.** Plan §10 relies on the type checker to surface IR
  breakage in Phase 6; a strict baseline has to exist before there is code to break.
- Version lives in `lecturenotes/__init__.py` as a plain string; no dynamic versioning.
- No `src/` layout — plan §5 shows `lecturenotes/` at the repo root and later tickets
  and CLAUDE.md quote those paths.
