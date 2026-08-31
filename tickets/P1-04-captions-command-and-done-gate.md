# P1-04 — `lecturenotes captions FILE` inspection command + Phase 1 done-gate
Phase 1 · Depends on: P1-03 · Size: S

## Goal

Make Phase 1 runnable from the shell — plan §6 wants "something runnable early" — with a
`captions` subcommand that prints the timestamped segments for one caption file, then
close the phase: tick the done-gate in `tickets/README.md`, move the four P1 tickets to
`tickets/completed/`, and record the one Phase 1 invariant later phases must respect in
`CLAUDE.md`. Optional: if the CLI should stay `--version`-only until Phase 5's `build`,
do only the done-gate part and note the decision here.

## Scope

**In**
- `captions FILE [--json] [--max-gap-s N] [--max-segment-s N]` subcommand in `lecturenotes/cli.py`.
- `tests/test_cli.py`.
- `tickets/README.md` done-gate, ticket moves, `CLAUDE.md` addition.

**Out**
- `build` and `--dry-run` → Phase 5. This command prints segments only; it must not grow
  chunking or pairing logic (plan §7.4).
- Any output *format* beyond plain lines and JSON — rendering is Phase 3's job.

## Tasks

1. **`cli.py`**: convert to `argparse` subparsers while keeping current behaviour —
   `--version` still works at the top level, and no arguments still prints help and
   returns 0 (`tests/test_smoke.py` must keep passing unchanged).
   - `captions FILE`: calls `ingest_captions(Path(FILE), max_gap_s=…, max_segment_s=…)`
     and prints one line per segment: `[m:ss–m:ss] text` — e.g. `[0:01–0:26] welcome back …`.
     Minutes are not zero-padded; hours appear only when ≥ 1 h (`1:02:03`). Write via
     `sys.stdout` as UTF-8 (the same Windows code-page issue P0-04 hit with em-dashes;
     the en-dash here is the same trap — reconfigure stdout or write bytes).
   - `--json`: print `[s.model_dump() for s in segments]` with `json.dumps(indent=2)`.
   - Missing file or unsupported suffix: print the error to stderr and return 2; do not
     print a traceback.
2. **`tests/test_cli.py`** using `main([...])` and `capsys`:
   - `main(["captions", "tests/fixtures/captions/lecture01.vtt"])` returns 0 and prints
     exactly 22 lines; the first starts with `[0:01–0:26] welcome back`; the last starts
     with `[8:40–9:05] that's it`.
   - `--json` output parses with `json.loads` into 22 objects with keys `start_s`, `end_s`, `text`.
   - An unsupported suffix returns 2 with a message on stderr and nothing on stdout.
   - `main(["--version"])` and `main([])` still return 0.
3. **`CLAUDE.md`**: add a short section **"Caption ingest (Phase 1)"** after "Stable IDs"
   with the two invariants later phases depend on: (a) `Segment` spans are unions of cue
   spans — they may overlap and do not partition time; sort by `start_s`, never assume a
   partition; (b) `ingest_captions` is the only entrypoint; parse/dedupe/merge are exposed
   for debugging, not for re-composition elsewhere. Add `uv run lecturenotes captions
   tests/fixtures/captions/lecture01.vtt` to the "Checks" block as the smoke command.
4. **`tickets/README.md`**: tick the Phase 1 done-gate boxes (record the date), update
   the P1 links to `completed/…`, and replace the closing line with "Phase 2 (slide
   ingest) can start; its tickets will be added to this index in a later session."
5. `git mv tickets/P1-0*.md tickets/completed/`. Run the full suite from a clean state
   (`git stash -u` anything unrelated, `uv sync --all-groups`) and commit.

## Acceptance criteria

- `uv run lecturenotes captions tests/fixtures/captions/lecture01.vtt | wc -l` prints `22`.
- `uv run lecturenotes captions --json tests/fixtures/captions/lecture01.srt | python -c "import json,sys; print(len(json.load(sys.stdin)))"` prints `22`.
- `uv run lecturenotes captions tests/fixtures/decks/lecture01.pdf; echo $?` prints an
  error line then `2`.
- `uv run lecturenotes --version` still prints `lecturenotes 0.0.1`.
- From a clean checkout: `uv sync --all-groups && uv run pytest && uv run ruff check . && uv run mypy && uv run lint-imports` passes.
- `ls tickets/completed/ | grep -c P1-` prints `4`; `ls tickets/*.md` lists no P1 files.
- `grep -c "Caption ingest" CLAUDE.md` ≥ 1.

## Decisions & notes

- **This is a debugging command, not the product.** The `build` command (Phase 5) will
  own pairing, chunking and generation; `captions` exists so a bad transcript can be
  inspected in seconds, which plan §8 says is the main debugging need ("bad notes are
  almost always bad chunks"). Keep it to one screen of code.
- **Subparsers now, not in Phase 5**, so the argparse layout is settled while the CLI has
  one command and adding `build` later is a five-line diff.
- **JSON output uses the `Segment` model's own field names** so a file produced here can
  be `model_validate`d back — handy for hand-building Phase 4 alignment fixtures from
  real captions.
- **UTF-8 stdout is enforced in the command**, not assumed from the console, for the same
  reason P0-04 wrote its snapshot via `sys.stdout.buffer`: Windows code pages mangle
  non-ASCII, and the en-dash in `[0:01–0:26]` is non-ASCII.
