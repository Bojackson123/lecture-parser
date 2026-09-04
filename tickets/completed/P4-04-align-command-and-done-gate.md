# P4-04 — `lecturenotes align DECK CAPTIONS` inspection command + Phase 4 done-gate
Phase 4 · Depends on: P4-03 · Size: S

## Goal

Make Phase 4 runnable from the shell, as every phase before it: an `align` subcommand
that ingests one deck and one caption file, aligns them, and prints the chunks — the
tool for the failure mode plan §8 names ("bad notes are almost always bad chunks", and
this is the chunk viewer that `build --dry-run` will grow from). Then close the phase:
tick the done-gate in `tickets/README.md`, move the four P4 tickets to
`tickets/completed/`, and record the Phase 4 invariants later phases must respect in
`CLAUDE.md`.

## Scope

**In**
- `align DECK CAPTIONS [--json] [--min-gap-s N] [--min-silence-s N]` subcommand in
  `lecturenotes/cli.py`; the module docstring's "pairing, chunking, alignment and
  generation belong to `build`" sentence updated (alignment is now here; pairing and
  generation still are not).
- `tests/test_cli.py` additions.
- `CLAUDE.md` section "Alignment (Phase 4)" and the smoke command in "Checks".
- `tickets/README.md` done-gate, ticket moves.

**Out**
- `build`, `--dry-run`, file pairing (plan §7.4) — Phase 5. This command takes **two
  explicit paths**; it must never guess which caption file goes with which deck.
- Chunk merging / density knobs (§9), generation, caching — Phase 5.
- The caption-ingest knobs (`--max-gap-s`, `--max-segment-s`) are *not* duplicated
  here — see Decisions.

## Tasks

1. **`cli.py`**: add the `align` subparser next to the other three (help: "align a
   slide deck with a caption file and print the chunks (a debugging aid)"). Arguments:
   `deck` (`type=Path`, a `.pptx`/`.pdf`), `captions` (`type=Path`, a `.vtt`/`.srt`),
   `--json`, `--min-gap-s` (`type=float`, default 60.0, metavar `N`, help "flag an
   unmatched stretch as a gap only if it spans at least N seconds"), `--min-silence-s`
   (`type=float`, default 1.0, metavar `N`, help "a gap must be bracketed by silences
   of at least N seconds"). `cmd_align`:
   - `ingest_slides(args.deck)` and `ingest_captions(args.captions)` inside the
     established `try/except (OSError, ValueError)` → `lecturenotes align: {exc}` on
     stderr, return 2.
   - `chunks = align_lecture(deck, segments, min_gap_s=…, min_silence_s=…)`.
   - `_utf8_stdout()`, then per chunk a header line, then its segments indented two
     spaces, blank line between chunks (the `slides` command's rhythm):
     - slide chunk: `--- slide 2: The Bellman Equation [4:31–6:59]` — width-1 range
       prints `slide {n}`, the deck slide's title after a colon when it has one; a
       wider range (not produced in v1) prints `slides {start}–{end}` with no title;
     - gap chunk: `--- (no slide) [2:31–4:28]`;
     - segments: `  [0:01–0:26] welcome back everyone, …` — `format_clock`, same as
       `captions`.
   - `--json` prints the chunk list as a JSON array of `model_dump()` objects,
     `indent=2`, re-validatable through `Chunk`.
   - Wire `args.command == "align"` into `main()`.
2. **`tests/test_cli.py`** via `main([...])` and `capsys`:
   - `main(["align", "tests/fixtures/decks/lecture01.pdf",
     "tests/fixtures/captions/lecture01.vtt"])` returns 0; exactly four lines start
     with `--- `, in order `--- slide 1: Markov Decision Processes [0:01–2:29]`,
     `--- (no slide) [2:31–4:28]`, `--- slide 2: The Bellman Equation [4:31–6:59]`,
     `--- slide 3: Value Iteration [7:01–9:05]`; 22 indented segment lines; nothing
     on stderr.
   - The PPTX deck and the SRT captions produce identical stdout (cross-format,
     end to end).
   - `--min-gap-s 1000` → three `--- ` lines, none containing `(no slide)`.
   - `--json` output: each array element re-validates as a `Chunk`; four elements;
     the second has `"slides": null`.
   - A wrong file in either slot (`week01.json` as the deck; a missing path) →
     return 2, `lecturenotes align:` prefix on stderr, nothing on stdout.
   - `captions …`, `slides …`, `render …`, `--version`, and no-args behaviour
     unchanged.
3. **`CLAUDE.md`**: add **"Alignment (Phase 4)"** after "Rendering (Phase 3)" with the
   invariants later phases depend on:
   - `align_lecture(deck, segments)` is the only entrypoint; `tokenize`,
     `term_weights`, `slide_terms`, `score`, `span_units` and `solve_windows` are
     exported for debugging and tests, not for re-composition elsewhere;
   - chunks **partition the segments in order** and their slide ranges are
     non-decreasing; chunk spans are unions of member segment spans — they may
     overlap and leave holes, so sort by `start_s`, never assume a partition of time;
   - segments whose spans overlap (one cue's sentences) are never split across
     chunks;
   - speaker notes and image bytes never influence alignment — the PDF and PPTX of a
     deck align identically;
   - gap chunks (`slides=None`) are the §4.1 gap signal (board work): real content
     for generation, the frame-pull trigger for Phase 9, never dropped;
   - hidden slides are skipped, never renumbered — no chunk cites a slide the reader
     can't count to;
   - `lecturenotes align DECK CAPTIONS` takes two explicit paths — a debugging aid
     that must not grow pairing (§7.4), chunk merging (§9), or generation.
   Add
   `uv run lecturenotes align tests/fixtures/decks/lecture01.pdf tests/fixtures/captions/lecture01.vtt   # smoke: 4 chunks`
   to the "Checks" block.
4. **`tickets/README.md`**: tick the Phase 4 done-gate boxes with the date, relink the
   P4 rows to `completed/…`, and replace the closing line with "**Phase 4 is done.**
   Phase 5 (generation) can start; its tickets will be added to this index in a later
   session."
5. `git mv tickets/P4-0*.md tickets/completed/`. Run the full suite from a clean state
   (`uv sync --all-groups`) and commit.

## Acceptance criteria

- `uv run lecturenotes align tests/fixtures/decks/lecture01.pdf tests/fixtures/captions/lecture01.vtt | grep -c "^--- "`
  prints `4`.
- `uv run lecturenotes align tests/fixtures/decks/lecture01.pdf tests/fixtures/captions/lecture01.vtt | grep "no slide"`
  prints `--- (no slide) [2:31–4:28]`.
- Swapping in `lecture01.pptx` and `lecture01.srt` produces byte-identical stdout.
- `uv run lecturenotes align tests/fixtures/notes/week01.json tests/fixtures/captions/lecture01.vtt; echo $?`
  prints an error line then `2`.
- `uv run lecturenotes captions tests/fixtures/captions/lecture01.vtt | wc -l` still
  prints `22`; `slides …lecture01.pdf | grep -c "^--- slide"` still prints `3`;
  `render …week01.json | grep -c "^--- "` still prints `1`; `--version` still prints
  `lecturenotes 0.0.1`.
- From a clean checkout: `uv sync --all-groups && uv run pytest && uv run ruff check .
  && uv run mypy && uv run lint-imports` passes.
- `ls tickets/completed/ | grep -c P4-` prints `4`; `ls tickets/*.md` lists no P4
  files; `grep -c "Alignment (Phase 4)" CLAUDE.md` ≥ 1.

## Decisions & notes

- **Two positional files, no inference.** Plan §7.4 is emphatic that pairing is
  guess-and-confirm territory, and the confirm belongs to `build` (Phase 5). An
  inspection command that guessed would train users to trust exactly the failure §7.4
  calls the worst one (confident notes about the wrong lecture).
- **The gap knobs are flags; the caption knobs are not.** `--min-gap-s` and
  `--min-silence-s` are what you turn when *this* command's output looks wrong (a
  detour missed, an aside over-flagged) — the §8 debugging loop this command exists
  for. `--max-gap-s`/`--max-segment-s` tune sentence merging, which has its own
  command (`captions`) to watch them in; duplicating them here doubles surface for no
  new visibility. When `build` composes the pipeline it can own a shared config.
- **Chunk headers use the slide title from the deck**, not anything stored in the
  chunk — `Chunk` deliberately carries only numbers and segments; the deck is in hand
  here, and keeping presentation out of the type is the same one-way-door caution as
  the IR's.
- **`(no slide)` rather than `gap` in output** — the header states a fact about the
  material; "gap" is pipeline jargon that reads as an error. The JSON keeps
  `"slides": null` as the machine-readable form.
- **stdout first, `--json` for scripts** — the print-first stance of every
  inspection command; the chunk view is for eyes, and the JSON round-trips per the
  standing P1-04 rule.
