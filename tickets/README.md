# Tickets

Work items for `PROJECT_PLAN.md`, one file per ticket. Each ticket is sized for a
single Claude Code session and has command-based acceptance criteria so "done" can be
checked without judgment calls.

## Phase 0 — Repo skeleton, `model/` types, fixtures

Plan §6: *done when types instantiate; fixtures committed.*

| ID | Title | Depends on | Done when |
|---|---|---|---|
| [P0-01](completed/P0-01-repo-and-toolchain.md) | Repo, toolchain, package skeleton, CLAUDE.md | — | `uv sync` + pytest/ruff/mypy pass; `lecturenotes --version` works; initial commit exists |
| [P0-02](completed/P0-02-model-types.md) | `model/` types + stable-ID helper | P0-01 | Every IR type instantiates and JSON round-trips; validators reject bad input; mypy strict clean |
| [P0-03](completed/P0-03-source-fixtures.md) | Source fixtures (captions + deck) | P0-01 | 20-cue `.vtt`/`.srt` and 3-page `.pdf`/`.pptx` committed with a generator script and sanity tests |
| [P0-04](completed/P0-04-notes-fixture-tests-boundaries.md) | Hand-written `NoteWeek` fixture, test scaffolding, boundary enforcement | P0-02, P0-03 | `week01.json` snapshot committed; import-linter contracts enforced from `pytest` |

**Suggested order:** P0-01 → (P0-02 and P0-03 in parallel, they are independent) → P0-04.

### Phase 0 done-gate

- [x] All four tickets' acceptance criteria met (P0-04 closed Phase 0 on 2026-08-31).
- [x] From a clean checkout:

```
uv sync --all-groups
uv run pytest && uv run ruff check . && uv run mypy && uv run lint-imports
```

passes with the fixtures committed.

**Phase 0 is done.** Phase 1 (caption ingest) can start; its tickets will be added to
this index in a later session.

## Ticket format

```
# P0-NN — Title
Phase 0 · Depends on: … · Size: S/M/L

## Goal            one paragraph: what exists after this ticket that didn't before
## Scope           In / Out bullet lists — Out names the ticket or phase that owns it
## Tasks           ordered checklist
## Acceptance criteria   commands or observable facts, checkable by the next session
## Decisions & notes     choices made here that later phases must respect, and why
```

## Stack (pinned)

Python 3.12 · uv · pydantic v2 · pytest · ruff · mypy (strict) · import-linter.
Fixture generation uses `reportlab` and `python-pptx` in a separate `fixtures` dependency group.
