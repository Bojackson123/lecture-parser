# P6-03 — `render --format` flag + Phase 6 done-gate
Phase 6 · Depends on: P6-02 · Size: M

## Goal

Give `lecturenotes render` the format flag CLAUDE.md has reserved since Phase 3 —
"a format flag before Phase 6 (which adds the flag when Anki gives it a second
value)" — so one command presents a cached week as either the markdown page or the
Anki deck, then close Phase 6: tick the done-gate, move the tickets, and record the
new invariants in `CLAUDE.md`. Includes the one manual gate item the suite cannot
check: a real Anki import, imported twice, proving §7.2's update-not-duplicate for
real.

## Scope

**In**
- `--format {markdown,anki}` (default `markdown`) on `cmd_render` in
  `lecturenotes/cli.py`, via a name→renderer table.
- CLI tests in `tests/test_cli.py`.
- `tickets/README.md` Phase 6 done-gate ticked; P6 tickets moved to `completed/`.
- `CLAUDE.md`: Phase 6 invariants section; the render-section sentence updated now
  that the flag exists.
- One manual check: double-import into a real Anki.

**Out**
- A `--format` on `build` — build writes IR JSON; presentation stays `render`'s job
  (the §7.1 two-command tuning loop is unchanged).
- Emitter changes — `emit_filesystem` already handles text documents and an empty
  manifest (it creates `assets/` only when the manifest is non-empty).
- New `RenderOptions` fields, per-lecture deck splitting, deck-name knobs — the
  P6-01 decisions stand; knobs arrive only when a real need does.
- Notion renderer/emitter → Phase 7.

## Tasks

1. **CLI tests first** in `tests/test_cli.py`, alongside the existing render tests:
   - `render tests/fixtures/notes/week01.json --format anki` exits 0 and prints
     `--- cs-rl-101-w01.txt` followed by the deck — 6 header lines and 8 data rows,
     byte-identical to `tests/fixtures/notes/week01.anki.txt`.
   - The default is unchanged: the existing markdown render tests pass untouched,
     and `--format markdown` prints exactly what no flag prints.
   - `render … --format anki -o DIR` writes `DIR/cs-rl-101-w01.txt` and creates
     **no** `assets/` directory (empty manifest); the markdown `-o` behaviour is
     untouched.
   - `--format notion` fails with an argparse `choices` error, exit code 2.
   - `--json` with `--format anki` prints the `RenderResult` JSON (the generic
     path — no per-format casing).
2. **`cli.py`**: a module-level table
   `_RENDERERS = {"markdown": MarkdownRenderer, "anki": AnkiRenderer}`,
   `--format` with `choices=sorted(_RENDERERS)` and `default="markdown"`;
   `cmd_render` constructs the chosen renderer, everything downstream (print,
   `--json`, `-o` via `emit_filesystem`) unchanged. Phase 7 adds Notion by adding
   one table entry.
3. **Manual gate item** (record the result in the done-gate, dated, like P5-04's
   real-run item): `uv run lecturenotes render tests/fixtures/notes/week01.json
   --format anki -o /tmp/deck`, then in a real Anki: File → Import on
   `cs-rl-101-w01.txt` → **8 notes added**, the Bellman card shows rendered MathJax;
   import the same file again → **0 added, 8 updated/unchanged** — guids working,
   §7.2 observed end-to-end.
4. **Close the phase** (mirror P1–P5):
   - Tick the Phase 6 done-gate in `tickets/README.md`; append "**Phase 6 is
     done.** Phase 7 tickets are not written yet."; move the three P6 tickets to
     `tickets/completed/` and repoint the table links.
   - Add the render smoke line to `CLAUDE.md` §Checks:
     `uv run lecturenotes render tests/fixtures/notes/week01.json --format anki   # smoke: 8 cards`.
   - Update the CLAUDE.md render-section sentence that reserved the flag, and add
     a **Anki deck (Phase 6)** invariants section: every topic carries ≥ 1 card —
     a generation guarantee (prompt-pinned), never patched in a renderer; card
     guids are 16-hex sha256 of `topic_id + "\n" + raw front`, renderer-local, a
     reworded front is a new card; the deck is CardSeeds only (glossary stays
     out); paired `$…$` → `\(…\)` in card fields is the renderer-local math
     dialect, never applied outside `render/anki.py`; `--format` selects
     presentation only — no pairing, generation or alignment logic on `render`.
5. Full check suite; commit.

## Acceptance criteria

- `uv run pytest && uv run ruff check . && uv run mypy && uv run lint-imports`
  green from a clean checkout after `uv sync --all-groups`.
- `uv run lecturenotes render tests/fixtures/notes/week01.json` still prints the
  markdown document (default unchanged — existing smoke line intact).
- `uv run lecturenotes render tests/fixtures/notes/week01.json --format anki`
  prints 1 document whose body has 8 tab-containing lines.
- `uv run lecturenotes render tests/fixtures/notes/week01.json --format anki -o <tmp>`
  writes `cs-rl-101-w01.txt` and no `assets/` directory.
- The manual double-import item is ticked in the done-gate with the date and the
  observed counts (8 added, then 0 added).
- `tickets/` contains only `README.md` and `completed/`; the Phase 6 table links
  resolve; `CLAUDE.md` shows the new invariants section; `git status` clean.

## Decisions & notes

- **The flag is `--format`, on `render` only, defaulting to `markdown`.** The
  default preserves every existing invocation, script and smoke line; `build`
  stays presentation-free so the §7.1 loop remains "build once, render cheaply
  many times" — now across formats from the same cached JSON, which is the §7.1
  payoff this phase was waiting to collect.
- **A dict, not a plugin registry.** Two renderers don't justify entry points or
  discovery; Phase 7 is a one-line diff. Resist generalising until a third-party
  renderer actually exists.
- **The double-import is a manual gate item, not a test**, for the same reason
  P5-04's real run was: it exercises software we don't ship (Anki itself), and the
  suite must stay hermetic. Everything mechanical about the format is already
  pinned byte-for-byte; the manual item checks the one claim only Anki can verify
  — that our guid column means what we think it means.
- **`--json` stays format-agnostic** — it dumps `RenderResult`, whatever produced
  it, because it's the debugging view of the contract type, not of any renderer.
