# P7-02 — Notion renderer
Phase 7 · Depends on: P7-01 · Size: L

## Goal

Create `lecturenotes/render/notion.py` (plan §5): a `NotionRenderer` that renders a
`NoteWeek` to the P7-01 payload document, matching the hand-written spec
`tests/fixtures/notes/week01.notion.json` byte-for-byte. Registering it in
`tests/contract/test_renderers.py` runs the four contract properties against a third
renderer — the first whose output is structure-as-text rather than a page or a deck —
which is half of the plan §6 done-criterion (*contract tests pass*). All format
decisions were made in P7-01; this ticket implements them. The §2.3 limits are
P7-03's.

## Scope

**In**
- `lecturenotes/render/notion.py`: `NotionRenderer` plus its local helpers
  (rich-text builder, inline-math translator, callout kind→icon/colour map,
  citation builder).
- `tests/render/test_notion.py`.
- `NotionRenderer()` registered in `tests/contract/test_renderers.py`.

**Out**
- The four Notion limits (2,000-char rich text, 100-element children, 2-level
  nesting, 1,000-block payloads) → P7-03. This renderer may produce over-limit
  output for over-limit input; `week01` is nowhere near.
- `emit/notion_api.py`, uploads, page identity → P7-04 (independent — its tests
  hand-build `RenderResult`s from the P7-01 spec and never import this module).
- The `--format notion` CLI entry and `push` → P7-05.
- Any change to fixtures or `model/` — P7-01 finished the spec; `degrade()` needs
  nothing (full capability set, see Decisions).

## Tasks

1. **`tests/render/test_notion.py` first** (red on `ImportError`):
   - The byte-equality pin: `NotionRenderer().render(week01, RenderOptions())`
     yields exactly one document named `cs-rl-101-w01.notion.json` whose `text`
     equals `tests/fixtures/notes/week01.notion.json` byte-for-byte. Assertion
     message as in P3-02/P6-02: *the expected payload is hand-written; if the
     format changed on purpose, edit the file deliberately — do not regenerate it
     from the code under test.*
   - The manifest is exactly the assets `Figure`s reference: `week01` → the one
     lec01 asset, and an ad-hoc week with no figures → `assets == ()` even when a
     lecture owns assets (the manifest contract from `render/base.py`).
   - **Ad-hoc weeks built in-memory** (the P3-02/P6-02 pattern):
     - math: `$x$` in prose becomes one inline `equation` rich-text run flanked by
       text runs; two pairs in one text both translate; an unpaired `$` (e.g.
       `costs $5`) passes through as text; translation applies in prose, bullet,
       cell and definition text — never in citations.
     - callouts: each of the four kinds maps to its pinned icon + colour; no other
       kind values exist (exhaustive over the enum, so a fifth kind fails here
       first).
     - citations: slide-less topic → clock only; single slide → ` · slide N`;
       range → ` · slides N–M` (en-dash).
     - a nested `BulletList` produces `children` on the parent item; a flat one
       produces none.
     - determinism the cheap way: two renders byte-equal (the contract suite
       re-checks this generically).
     - the rendered text contains no `\r` and ends with exactly one `\n`.
2. **`render/notion.py`**: `class NotionRenderer` with `name = "notion"`,
   `capabilities = set(Capability)` (see Decisions), and a pure `render()` —
   structure building plus one `json.dumps(payload, indent=2, ensure_ascii=False)
   + "\n"`, no IO, deterministic by construction:
   - document name `f"{week.id}.notion.json"`; page title from `course` +
     `week_number` (P7-01 spec);
   - blocks built lecture → topic → node in order, per the P7-01 mapping;
   - every timestamp built with `format_clock` from `render/base.py` and nothing
     else (CLAUDE.md invariant — the contract test greps for it);
   - `assets` manifest collected from rendered `Figure`s only;
   - helpers are module-local functions, exported for tests but not re-composed
     elsewhere (the ingest-entrypoint doctrine, applied to render, as in P6-02).
3. **Register** `NotionRenderer()` in `RENDERERS` in
   `tests/contract/test_renderers.py` — the four properties now run for
   `markdown`, `anki` and `notion`: 12 tests, no skips. Property 4 passes because
   the citation carries the clock string into the JSON text.
4. Run the full check suite and commit in two steps: tests first (red on
   `ImportError`), then the implementation.

## Acceptance criteria

- `uv run pytest` → all green, and `uv run pytest tests/contract/ -v` shows the
  four contract properties **passing for `markdown`, `anki` and `notion`** (12
  tests, no skips).
- `uv run ruff check .`, `uv run mypy`, `uv run lint-imports` clean (the 4 boundary
  contracts still hold — `render/` gained no new imports beyond `model`).
- `uv run python -c "from lecturenotes.render.notion import NotionRenderer; from lecturenotes.render.base import RenderOptions; from tests.fixtures.notes.week01 import week01; r = NotionRenderer().render(week01(), RenderOptions()); print(r.documents[0].name, len(r.documents), len(r.assets))"`
  prints `cs-rl-101-w01.notion.json 1 1`.
- `uv run python -c "from pathlib import Path; from lecturenotes.render.notion import NotionRenderer; from lecturenotes.render.base import RenderOptions; from tests.fixtures.notes.week01 import week01; print(NotionRenderer().render(week01(), RenderOptions()).documents[0].text == Path('tests/fixtures/notes/week01.notion.json').read_text(encoding='utf-8'))"`
  prints `True`.
- `git log` shows tests committed before (or with, never after) the
  implementation; `git status` clean.

## Decisions & notes

- **Capabilities are the full set, and this time it is literal.** Notion natively
  has all six constructs — equation blocks, nested list items, callouts, tables,
  images, code — so `degrade()` is a true no-op and the renderer handles the whole
  IR. (P6-02's full set was a different argument — cards-only output; recorded so
  the two aren't conflated.) The 2-level nesting cap is a renderer-local *limit*
  handled in P7-03, not a missing capability: `NESTING` describes whether the
  target nests at all, and Notion does.
- **Structure-as-text is deliberate.** `RenderedDocument.text` holding serialized
  JSON keeps `RenderResult` unchanged, keeps the contract suite's text grep
  working, makes `render --format notion -o DIR` a working debugging aid via the
  untouched filesystem emitter, and gives byte-for-byte fixture equality — the
  doctrine every renderer so far has profited from. A parallel structured result
  type would buy nothing and cost a second contract.
- **Fixed serialization is the determinism.** `indent=2`, `ensure_ascii=False`,
  insertion-ordered dicts built in one code path, trailing `\n` — no sorting, no
  canonicalization pass; the builder's order is the format, as pinned by the
  fixture.
- **The math translator is Notion-local**, like Anki's `\(…\)` translator before
  it: paired-`$` handling lives in this module and nowhere else. Inline `$…$` in
  the IR stays plain text (the degrade docstring's rule); each renderer that has a
  native inline-math form claims it locally.
