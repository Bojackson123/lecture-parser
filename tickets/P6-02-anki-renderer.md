# P6-02 — Anki renderer
Phase 6 · Depends on: P6-01 · Size: L

## Goal

Create `lecturenotes/render/anki.py` (plan §5): an `AnkiRenderer` that renders a
`NoteWeek`'s `CardSeed`s to **one Anki notes-in-plain-text file** matching the
hand-written spec `tests/fixtures/notes/week01.anki.txt` byte-for-byte. The plan §6
done-criterion (*same `NoteWeek` produces a deck*) becomes one byte-equality test,
and registering the renderer in `tests/contract/test_renderers.py` runs the four
contract properties against a second, structurally alien renderer for the first time
— the real point of Phase 6. All format decisions were made in P6-01; this ticket
implements them.

## Scope

**In**
- `lecturenotes/render/anki.py`: `AnkiRenderer` plus its local helpers
  (`card_guid`, math-delimiter translation, TSV field quoting).
- `tests/render/test_anki.py`.
- `AnkiRenderer()` registered in `tests/contract/test_renderers.py`.
- `tests/fixtures/README.md` pointer.

**Out
- The `--format` CLI flag and done-gate → P6-03. `emit_filesystem` needs no change
  (text documents; the deck's manifest is empty).
- Anki media (`collection.media`) — cards are text-only; a card can't reference a
  `Figure`, so there is nothing to ship. Revisit only if `CardSeed` ever grows an
  image field (a model change, taken deliberately).
- Any change to fixtures, prompts or `model/` — P6-01 finished those.
- Notion/HTML renderers → Phase 7.

## Tasks

1. **`tests/render/test_anki.py` first** (red on `ImportError`):
   - The done-gate: `AnkiRenderer().render(week01, RenderOptions())` yields exactly
     one document named `cs-rl-101-w01.txt` whose `text` equals
     `tests/fixtures/notes/week01.anki.txt` byte-for-byte. Assertion message as in
     P3-02: *the expected deck is hand-written; if the format changed on purpose,
     edit the file deliberately — do not regenerate it from the code under test.*
   - The manifest is empty (`assets == ()`) even though lec01 owns an asset — cards
     reference no figures, and the emitter must copy nothing.
   - **Ad-hoc weeks built in-memory** (the render-side analogue of P3-02's):
     - guid: two renders of the same week produce identical guids; two cards with
       the same front under different topics, and two cards with different fronts
       under one topic, produce four distinct guids.
     - quoting: a front containing a tab, a back containing `\n`, and a field
       containing `"` are CSV-quoted (wrapped in `"`, inner `"` doubled — Anki's
       quoting rules); a field needing no quoting is written bare.
     - a tag containing whitespace is sanitized with `_`
       (`exam topic` → `exam_topic`); a card with empty `tags` still has its
       (empty) fourth column — three tabs on the row, never two.
     - math: `$x$` becomes `\(x\)`; two pairs in one field both translate; an
       unpaired `$` (e.g. `costs $5`) passes through untouched; translation applies
       to fronts and backs only — never to the citation.
     - a card-less topic contributes no rows (the ≥ 1-card guarantee is
       generation's, pinned in P6-01 — the renderer never invents content), and a
       week whose every topic is card-less still renders: headers only, no rows.
     - the citation of a slide-less topic has no ` · slide`; a single-slide range
       renders ` · slide N`, a true range ` · slides N–M` (en-dash).
     - the rendered text ends with exactly one `\n` and contains no `\r`.
2. **`render/anki.py`**: `class AnkiRenderer` with `name = "anki"`,
   `capabilities = set(Capability)` (see Decisions), and a pure `render()` — string
   building only, no IO, deterministic by construction:
   - header block from `week.course` / `week.week_number` (P6-01 spec, six lines);
   - one row per card, iterating lectures → topics → cards in order;
   - `card_guid(topic_id, front)` = first 16 hex of `sha256` over
     `f"{topic_id}\n{front}".encode()` — raw IR front, before math translation;
   - timestamps built with `format_clock` from `render/base.py` and nothing else
     (CLAUDE.md invariant — the contract test greps for it);
   - the math translator and field-quoting helper are module-local functions,
     exported for tests but not re-composed elsewhere (the ingest-entrypoint
     doctrine, applied to render).
3. **Register** `AnkiRenderer()` in `RENDERERS` in
   `tests/contract/test_renderers.py` — the four properties now run for `anki`;
   property 4 passes only because P6-01 gave every topic a card, which is the
   checkpoint working as intended.
4. **`tests/fixtures/README.md`**: point `notes/week01.anki.txt` at its consumer —
   "byte-equality target of `tests/render/test_anki.py` (P6-02)".
5. Run the full check suite and commit in two steps: tests first (red on
   `ImportError`), then the implementation.

## Acceptance criteria

- `uv run pytest` → all green, and `uv run pytest tests/contract/ -v` shows the
  four contract properties **passing for both `markdown` and `anki`** (8 tests, no
  skips).
- `uv run ruff check .`, `uv run mypy`, `uv run lint-imports` clean (the 4
  boundary contracts still hold — `render/` gained no new imports).
- `uv run python -c "from lecturenotes.render.anki import AnkiRenderer; from lecturenotes.render.base import RenderOptions; from tests.fixtures.notes.week01 import week01; r = AnkiRenderer().render(week01(), RenderOptions()); print(r.documents[0].name, len(r.documents), len(r.assets))"`
  prints `cs-rl-101-w01.txt 1 0`.
- `uv run python -c "from pathlib import Path; from lecturenotes.render.anki import AnkiRenderer; from lecturenotes.render.base import RenderOptions; from tests.fixtures.notes.week01 import week01; print(AnkiRenderer().render(week01(), RenderOptions()).documents[0].text == Path('tests/fixtures/notes/week01.anki.txt').read_text(encoding='utf-8'))"`
  prints `True`.
- `git log` shows tests committed before (or with, never after) the
  implementation; `git status` clean.

## Decisions & notes

- **Capabilities are the full set, and that is honest, not a shortcut.** The deck
  renders only `topic.cards` — plain strings — so no body construct ever reaches
  the output and `degrade()` is a no-op that could not change the result. Declaring
  the empty set instead would make the contract's degrade step do maximal rewriting
  of bodies the renderer then ignores — pure waste dressed up as caution. Recorded
  so Phase 7 doesn't "fix" it: capability declarations describe what may appear in
  the week a renderer receives, and this renderer trivially tolerates everything.
- **`cs-rl-101-w01.txt`, named `{week.id}.txt`** — the §7.2 pattern: stable name,
  so re-emitting overwrites in place; the guid column makes re-*import* an update
  inside Anki itself.
- **The renderer emits nothing for a card-less topic.** The every-topic-≥ 1-card
  guarantee belongs to generation (P6-01's prompt pin) and the fixture sanity test
  — a renderer that padded missing cards would be inventing content, the exact
  failure the IR exists to prevent. A card-less topic in some future week means the
  contract suite flags it (property 4), which is the desired behaviour: the flaw
  surfaces, loudly, at test time.
- **Helpers stay module-local.** `card_guid` is not in `model/ids.py` even though
  it smells like an id: it exists only for Anki's import protocol, no other phase
  may reuse it, and putting it in `model/` would invite exactly the cross-target
  coupling the guid's renderer-format independence (raw-front hashing) is designed
  to avoid.
- **No new dependencies.** The TSV, the quoting and the sha256 are stdlib; the
  P6-01 decision against genanki keeps Phase 6 dependency-free.
