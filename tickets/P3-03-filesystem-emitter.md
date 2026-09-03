# P3-03 — `emit/filesystem.py` + emit boundary contract
Phase 3 · Depends on: P3-01 · Size: S

## Goal

Create `lecturenotes/emit/filesystem.py` (plan §5), the first emitter: a function that
takes a `RenderResult` and a directory and writes the documents and their assets to
disk — the side-effect half plan §2.3 split off so that rendering stays pure and
testable. Its tests build `RenderResult` values by hand and never import a renderer,
proving the emitter is renderer-independent the same way P3-01's contract tests prove
renderers are emitter-independent. While the packages are still small, also add the
import-linter contracts that fence the right half of the pipeline: `emit` (and
`render`) never import `ingest`, `align` or `generate`. Independent of P3-02 — the two
can land in either order.

## Scope

**In**
- `lecturenotes/emit/filesystem.py`: `emit_filesystem`.
- `tests/emit/__init__.py`, `tests/emit/test_filesystem.py`.
- `pyproject.toml`: a new forbidden contract for `emit`; the existing `render`
  contract's forbidden list widened to `ingest`, `align`, `generate`.

**Out**
- Any renderer dependency — the tests must not import `render.markdown`; wiring
  renderer to emitter is the CLI's job → P3-04.
- The Notion API emitter → Phase 7. Base64 inlining, uploads, any asset resolution
  other than copying a local file — this emitter only copies (plan §2.2: *as
  appropriate* means per-emitter).
- Minting `MediaAsset`s or deciding `source` values — Phase 5 owns producing
  well-defined sources from `SlideImage`s.

## Tasks

1. **`tests/emit/test_filesystem.py` first** (red on `ImportError`), with hand-built
   `RenderResult` values and `tmp_path`:
   - Two documents (`notes.md`, `extra/appendix.md`) land at
     `tmp_path / "notes.md"` and `tmp_path / "extra/appendix.md"` — parent
     directories created — with byte-exact content, UTF-8, LF (write a text
     containing an en-dash and a `$\gamma$` and read the bytes back; no BOM, no
     `\r`).
   - A manifest with the `week01` figure asset (`id="fig-value-iteration-convergence"`,
     `media_type="image/png"`, `source="tests/fixtures/decks/value_iteration.png"`),
     emitted with `asset_root=repo_root`, copies the PNG byte-for-byte to
     `tmp_path / "assets/fig-value-iteration-convergence.png"` — the path
     `asset_target()` returns, asserted via the helper, not a hardcoded string.
   - **Re-emit overwrites in place**: emit, change a document's text, emit again to
     the same directory → the file has the new content and the directory contains no
     extra files (the §7.2 update-not-duplicate property, at the file level).
   - An empty manifest creates no `assets/` directory.
   - A manifest asset whose `source` does not exist raises `FileNotFoundError` whose
     message contains the asset id, and the missing asset's file is not created.
   - `emit_filesystem` never touches the network and never reads a `NoteWeek` — the
     test file imports only `emit.filesystem`, `render.base` and `model`.
2. **`emit_filesystem(result: RenderResult, out_dir: Path, *,
   asset_root: Path = Path(".")) -> None`**:
   - Per document: `out_dir / document.name`, parents created
     (`mkdir(parents=True, exist_ok=True)`), written with
     `open(…, "w", encoding="utf-8", newline="\n")` — the same LF-everywhere rule as
     the fixture files.
   - Per manifest asset: read `asset_root / asset.source` as bytes, write to
     `out_dir / asset_target(asset)`, parents created. A missing source raises
     `FileNotFoundError` naming the asset id and the resolved path (an `OSError`, so
     the CLI's existing error contract covers it in P3-04).
   - No return value: stage 8 is side effects (plan §3); the tests inspect the
     directory.
3. **`pyproject.toml`**: add
   `emit never imports the left half` — `source_modules = ["lecturenotes.emit"]`,
   `forbidden_modules = ["lecturenotes.ingest", "lecturenotes.align",
   "lecturenotes.generate"]` — and widen the existing `render never imports ingest`
   contract's forbidden list to the same three modules (renaming it to match).
   `tests/test_boundaries.py` already runs `lint-imports` from pytest, so the new
   contracts are enforced by the ordinary test run with no new wiring.
4. Run the full check suite and commit in two steps: the tests first (red on
   `ImportError`), then the implementation and the pyproject contracts.

## Acceptance criteria

- `uv run pytest` → all green; `uv run ruff check .`, `uv run mypy`,
  `uv run lint-imports` clean.
- `uv run lint-imports` reports **4 contracts, 0 broken** (was 2).
- `uv run python -c "import tempfile; from pathlib import Path; from lecturenotes.emit.filesystem import emit_filesystem; from lecturenotes.render.base import RenderedDocument, RenderResult; d = Path(tempfile.mkdtemp()); emit_filesystem(RenderResult(documents=(RenderedDocument(name='n.md', text='hi\n'),), assets=()), d); print((d / 'n.md').read_text(encoding='utf-8'), end='')"`
  prints `hi`.
- `grep -c "lecturenotes.emit" pyproject.toml` ≥ 1.
- `git log` shows the tests committed before (or together with, but never after) the
  implementation; `git status` clean.

## Decisions & notes

- **`emit` may import `render`** — it consumes `RenderResult` and `asset_target`, and
  the plan's diagram (§2) has emit downstream of render. The forbidden contracts
  codify the real rule: *everything right of `NoteDocument` never imports the left
  half*. `align` and `generate` are added to both contracts while the packages are
  still empty because the contracts are free now and expensive to retrofit once
  something quietly depends on the hole.
- **Asset filenames are id-keyed via the shared `asset_target`**, so the link the
  renderer wrote and the path the emitter writes cannot drift — one helper, two
  callers — and re-emitting is byte-stable: same id, same path, file overwritten in
  place, never duplicated (§7.2 at the file level).
- **`asset_root` is a keyword because `MediaAsset.source` is relative.** The `week01`
  fixture's sources are repo-root-relative (a P0-04 decision: *assets are resolved by
  the emitter*, plan §2.2); the emitter must not guess what they are relative to.
  P3-04's CLI passes the current directory; Phase 5 owns producing sources that are
  well-defined for real runs.
- **This emitter only copies.** Inlining as base64 or uploading are other emitters'
  strategies (plan §2.2 lists all three); building a strategy switch here would be
  speculation. When the Notion emitter needs uploads, it is a new module behind the
  same `RenderResult`.
- **The emitter never reads the IR** — `RenderResult` in, side effects out. That is
  what keeps it renderer-independent, and it is why the tests build results by hand:
  any emitter that needs to know what a `Topic` is has taken a wrong turn.
- **Overwrite, don't clean.** The emitter does not delete files it did not write this
  run; a stale document from a renamed lecture id is the regeneration workflow's
  problem (plan §7.2 makes ids stable precisely so this stays rare). A `--clean`
  belongs on the CLI when someone actually needs it.
