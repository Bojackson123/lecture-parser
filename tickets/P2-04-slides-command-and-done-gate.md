# P2-04 — `lecturenotes slides FILE` inspection command + Phase 2 done-gate
Phase 2 · Depends on: P2-03 · Size: S

## Goal

Make Phase 2 runnable from the shell, as P1-04 did for captions: a `slides` subcommand
that prints what one deck ingests to — titles, blocks in reading order, images found,
optionally notes — so a deck whose columns came out interleaved or whose logo became a
figure can be inspected in seconds. Then close the phase: tick the done-gate in
`tickets/README.md`, move the four P2 tickets to `tickets/completed/`, and record the
Phase 2 invariants later phases must respect in `CLAUDE.md`.

## Scope

**In**
- `slides FILE [--json] [--notes] [--min-px N]` subcommand in `lecturenotes/cli.py`.
- `tests/test_cli.py` additions.
- `CLAUDE.md` section "Slide ingest (Phase 2)" and the smoke command in "Checks".
- `tickets/README.md` done-gate, ticket moves.

**Out**
- `build`, `--dry-run`, file pairing (plan §7.4), alignment — Phases 4–5. This command
  prints one deck and must not grow pairing or alignment logic.
- Any output *format* beyond plain lines and JSON — rendering is Phase 3's job.
- Writing image files to disk — Phase 5 / emit owns that.

## Tasks

1. **`cli.py`**: add the `slides` subparser next to `captions` (the argparse layout P1-04
   settled). `cmd_slides` calls `ingest_slides(Path(FILE), min_px=args.min_px)` and prints,
   per slide:
   - `--- slide N: Title` — or `--- slide N` when untitled — with ` [hidden]` appended for
     hidden slides;
   - each block's lines, one per line, with a blank line between blocks;
   - `[image img-… 240x150 image/png]` per entry in `image_ids`;
   - `[notes] …` only with `--notes`;
   - after the last slide, `[recurring] img-… (on N slides)` lines when
     `recurring_image_ids` is non-empty.
   `--json` prints `deck.model_dump_json(indent=2)` instead (base64 image data — the
   output re-validates with `Deck.model_validate_json`). Errors (`OSError`, `ValueError`
   including `DeckParseError`) go to stderr with the `lecturenotes slides:` prefix and
   return 2, no traceback. Reuse `_utf8_stdout()`.
2. **`tests/test_cli.py`** via `main([...])` and `capsys`:
   - `main(["slides", "tests/fixtures/decks/lecture01.pptx"])` returns 0; exactly three
     lines start with `--- slide`; the first is `--- slide 1: Markov Decision Processes`;
     `Intuition` appears after `gamma: discount factor` (left column first);
     one line starts with `[image img-a63ae9b7dc5e9397 240x150 image/png]`; no `[notes]` line.
   - `--notes` adds exactly three `[notes]` lines.
   - The PDF prints the same three `--- slide` lines and no `[notes]` line even with `--notes`.
   - `--json` output validates with `Deck.model_validate_json` to three slides.
   - `tests/fixtures/captions/lecture01.vtt` → return 2, stderr message, nothing on stdout.
   - `captions …`, `--version`, and no-args behaviour unchanged.
3. **`CLAUDE.md`**: add **"Slide ingest (Phase 2)"** after "Caption ingest (Phase 1)" with
   the invariants later phases depend on:
   - `ingest_slides(path)` is the only entrypoint; `parse_pdf`, `parse_pptx`, `layout_page`
     and `clean_line` are exported for debugging and tests, not for re-composition;
   - `Slide.number` is the 1-based position in the file, hidden slides included, so a
     `SlideRange` matches what a reader counts in the deck — never renumber;
   - image ids are content hashes of the extracted bytes; ingest never writes files; Phase 5
     mints `MediaAsset` from `SlideImage` and owns where the bytes go; the same figure via
     PDF and PPTX has different ids;
   - `recurring_image_ids` are set aside on purpose (logos); do not turn them into figures;
   - `lecturenotes slides FILE` is a debugging aid and must not grow pairing or alignment logic.
   Add `uv run lecturenotes slides tests/fixtures/decks/lecture01.pdf   # smoke: 3 slides`
   to the "Checks" block.
4. **`tickets/README.md`**: tick the Phase 2 done-gate boxes with the date, relink the P2
   rows to `completed/…`, and replace the closing line with "**Phase 2 is done.** Phase 3
   (markdown renderer + filesystem emitter) can start; its tickets will be added to this
   index in a later session."
5. `git mv tickets/P2-0*.md tickets/completed/`. Run the full suite from a clean state
   (`git stash -u` anything unrelated, `uv sync --all-groups`) and commit.

## Acceptance criteria

- `uv run lecturenotes slides tests/fixtures/decks/lecture01.pdf | grep -c "^--- slide"` prints `3`.
- `uv run lecturenotes slides --json tests/fixtures/decks/lecture01.pptx | python -c "import json,sys; print(len(json.load(sys.stdin)['slides']))"` prints `3`.
- `uv run lecturenotes slides tests/fixtures/captions/lecture01.vtt; echo $?` prints an
  error line then `2`.
- `uv run lecturenotes captions tests/fixtures/captions/lecture01.vtt | wc -l` still prints
  `22`; `uv run lecturenotes --version` still prints `lecturenotes 0.0.1`.
- From a clean checkout: `uv sync --all-groups && uv run pytest && uv run ruff check . && uv run mypy && uv run lint-imports` passes.
- `ls tickets/completed/ | grep -c P2-` prints `4`; `ls tickets/*.md` lists no P2 files.
- `grep -c "Slide ingest" CLAUDE.md` ≥ 1.

## Decisions & notes

- **A debugging aid, not the product** — the same stance as P1-04. Bad notes are almost
  always bad chunks (plan §8), and bad chunks from slides are almost always a wrong
  reading order or a logo mistaken for a figure; this command shows both at a glance.
- **`--notes` is opt-in** because notes are long and the usual question is "did the
  columns come out in order"; `--json` is the complete view.
- **JSON is the model's own dump**, so a real deck's output can be committed — after
  hand-editing, per the P1-03 rule — as a Phase 4 alignment fixture, exactly as P1-04
  intended for segments.
- **Image bytes are printed only in `--json`** (as base64); the line format shows id, size
  and type, which is what a human needs to recognise a logo.
