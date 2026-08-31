# P0-04 — Hand-written `NoteWeek` fixture, test scaffolding, boundary enforcement
Phase 0 · Depends on: P0-02, P0-03 · Size: M

## Goal

Close Phase 0: commit a hand-written `NoteWeek` that exercises the entire IR (the
fixture Phase 3 will render and Phase 6 will break against), snapshot it as JSON so IR
drift is caught, set up the shared pytest scaffolding and the renderer contract-test
harness (empty for now), and make the two package-boundary rules from plan §5
machine-enforced via import-linter running inside `pytest`.

## Scope

**In**
- `tests/fixtures/notes/week01.py` builder and committed `week01.json` snapshot.
- `tests/conftest.py`.
- `tests/contract/test_renderers.py` scaffold.
- import-linter contracts in `pyproject.toml` and `tests/test_boundaries.py`.
- `CLAUDE.md` and `tickets/README.md` updates.

**Out**
- Any renderer, `degrade()`, or contract-test *implementation* → Phase 3.
- `Renderer` protocol itself → Phase 3 (`render/base.py`); the scaffold here types the
  registry loosely (`list[object]`) so it has nothing to import yet.
- Property-based tests (hypothesis) → Phases 1, 2, 4 where the pure functions are.

## Tasks

1. **`tests/fixtures/notes/week01.py`** — `def week01() -> NoteWeek`, built from
   `lecturenotes.model` types only. Requirements:
   - One `NoteWeek` (`course="CS-RL-101"`, `week_number=1`) with **two** `NoteLecture`s
     (plan §7.3: lecture is the unit of generation; week is a container).
   - Across the two lectures, **every one of the nine `Node` types appears at least
     once**; all four `CalloutKind`s appear; at least one `BulletList` has a nested
     `BulletItem.children`; a `Table` with ≥ 2 rows; an `Equation` (the Bellman
     equation in LaTeX) with a `label`; a `CodeBlock` with `language="python"`.
   - Lecture 1 has a `Figure` whose `asset_id` resolves to a `MediaAsset` pointing at
     the PNG embedded in P0-03's deck (reference by relative path string).
   - `SourceRef`s point at the P0-03 fixture paths (`tests/fixtures/captions/lecture01.vtt`,
     `tests/fixtures/decks/lecture01.pdf`); lecture 2 may reuse them with a different id.
   - Every `Topic.id` is produced by `topic_id()`; include **one slide-less gap topic**
     (`slides=None`, e.g. "Board work: deriving the update rule") so the `t<seconds>`
     branch is in the fixture.
   - At least two topics carry `CardSeed`s; one lecture has ≥ 2 glossary `Definition`s
     and ≥ 1 open question.
   - `SourceAnchor`s follow the slide→time mapping in `tests/fixtures/README.md` (P0-03).
   - `if __name__ == "__main__":` with a `--write` flag that dumps
     `week01().model_dump_json(indent=2)` to `week01.json` beside the module; without
     the flag it prints the JSON to stdout.
2. **`tests/fixtures/notes/week01.json`** — generate with
   `uv run python -m tests.fixtures.notes.week01 --write` and commit.
   (`tests/fixtures/notes/__init__.py` needed for `-m` to resolve.)
3. **`tests/fixtures/notes/test_week01.py`**:
   - Snapshot: `week01().model_dump_json(indent=2)` equals the committed file text
     (with a failure message telling the reader to rerun `--write` if the IR change was intentional).
   - Round-trip: `NoteWeek.model_validate_json(path.read_text()) == week01()`.
   - Coverage: the set of `type` discriminator values found anywhere in the JSON equals
     the full set of nine node type names; all four `CalloutKind` values appear;
     at least one topic id contains `:t` and at least one contains `:s`.
   - Every `SourceRef.deck_path`/`caption_path` and every `MediaAsset.source` in the
     fixture exists on disk relative to the repo root.
4. **`tests/conftest.py`** — fixtures `repo_root: Path`, `fixtures_dir: Path`, and
   `week01: NoteWeek` (calls the builder). Move any duplicated path logic from P0-03's
   sanity tests onto these.
5. **`tests/contract/test_renderers.py`** — scaffold only:
   ```python
   RENDERERS: list[object] = []   # Phase 3 registers renderers here; typed properly then.

   @pytest.mark.parametrize("renderer", RENDERERS or [pytest.param(None, marks=pytest.mark.skip(reason="no renderers yet"))])
   def test_contract(renderer, week01): ...
   ```
   with a docstring listing the four plan §8 contract properties to implement in Phase 3:
   renders without raising; respects declared capabilities; output is deterministic;
   every `SourceAnchor` survives into the output in some form.
6. **import-linter contracts** in `pyproject.toml`:
   ```toml
   [tool.importlinter]
   root_package = "lecturenotes"

   [[tool.importlinter.contracts]]
   name = "model imports nothing internal"
   type = "forbidden"
   source_modules = ["lecturenotes.model"]
   forbidden_modules = ["lecturenotes.ingest", "lecturenotes.align", "lecturenotes.generate",
                        "lecturenotes.render", "lecturenotes.emit", "lecturenotes.cli"]

   [[tool.importlinter.contracts]]
   name = "render never imports ingest"
   type = "forbidden"
   source_modules = ["lecturenotes.render"]
   forbidden_modules = ["lecturenotes.ingest"]
   ```
7. **`tests/test_boundaries.py`** — runs `lint-imports` via `subprocess.run` from
   `repo_root`, asserts returncode 0, and includes stdout in the failure message. This
   makes plain `uv run pytest` catch a boundary violation.
8. **Negative check** (manual, record the result in the commit message): add
   `from lecturenotes.ingest import __doc__ as _x` to `lecturenotes/model/notes.py`;
   confirm `uv run lint-imports` fails and `uv run pytest tests/test_boundaries.py` fails;
   revert.
9. Update `CLAUDE.md`: under "Boundary rules" note the contracts are enforced by
   `tests/test_boundaries.py`; under "Checks" add `uv sync --all-groups` as the setup
   line. Update `tickets/README.md`: tick the Phase 0 done-gate.
10. Commit.

## Acceptance criteria

- `uv sync --all-groups && uv run pytest` → all green; the only skip is the contract
  scaffold's "no renderers yet".
- `uv run lint-imports` → `Contracts: 2 kept, 0 broken.`
- Negative check in Task 8 was performed and both commands failed while the bad
  import was present.
- `tests/fixtures/notes/week01.json` is committed, and
  `uv run python -m tests.fixtures.notes.week01 | diff - tests/fixtures/notes/week01.json`
  is empty.
- `grep -o '"type": "[a-z_]*"' tests/fixtures/notes/week01.json | sort -u | wc -l` prints `9`.
- `uv run pytest && uv run ruff check . && uv run mypy && uv run lint-imports` passes
  from a clean checkout — the Phase 0 done-gate in `tickets/README.md`.

## Decisions & notes

- **Builder in Python + committed JSON snapshot, not JSON alone.** The Python builder
  is type-checked (mypy catches IR changes at edit time); the JSON snapshot catches
  *serialisation* changes and gives Phase 3's markdown snapshot tests a stable input.
  Regeneration is deliberate (`--write`), never automatic.
- **Two lectures, not one**, so Phase 3 renderers immediately face the
  one-page-or-several decision (plan §7.3) rather than discovering it in Phase 7.
- **Boundary enforcement runs inside pytest** rather than only as a separate CLI
  step, because there is no CI yet and `pytest` is the one command every session runs.
- Contract scaffold is intentionally untyped (`list[object]`) to avoid importing a
  `Renderer` protocol that does not exist yet; Phase 3 replaces it.
- Fixture content should read like real notes (the plan's success criterion is
  "good enough to revise from"); it doubles as the target quality bar for Phase 5 prompts.
- **Done 2026-08-31.** Negative check (Task 8) performed: with the bad import in
  `model/notes.py`, `uv run lint-imports` exited 1 (`1 kept, 1 broken`) and
  `uv run pytest tests/test_boundaries.py` failed; reverted cleanly.
- The builder writes the snapshot with `newline="\n"` and prints via `sys.stdout.buffer`
  as UTF-8 bytes, so the file and the `| diff` acceptance check are byte-identical on
  Windows too (the console code page would otherwise mangle the em-dashes).
