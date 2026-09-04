# lecturenotes

Turns a week of lecture material (videos, slide decks, transcripts, captions) into
structured study notes with pluggable output formats. Design: `PROJECT_PLAN.md`.
Work items: `tickets/README.md`.

## The note IR

Plan §2.2, verbatim. This is the only contract between the two halves of the pipeline.

Semantic node types, not presentational ones. The renderer decides what a
`Callout(kind=EXAM)` looks like; the IR only records that the lecturer flagged it.

```python
NoteWeek
  id, course, week_number, lectures: [NoteLecture]

NoteLecture
  id, title, overview, objectives: [str]
  source: SourceRef            # video url, deck path, caption path
  topics: [Topic]
  glossary: [Definition]
  open_questions: [str]

Topic
  id                           # stable, see §7.2
  heading: str
  anchor: SourceAnchor         # timestamp + slide range — the citation
  body: [Node]                 # ordered, heterogeneous
  cards: [CardSeed]            # optional Q/A pairs for spaced-repetition targets

Node = Prose | BulletList | Definition | Equation | CodeBlock
     | Callout | Figure | Table | Quote
```

Notable choices:

- **`Equation` holds LaTeX, always.** Every plausible target consumes LaTeX natively
  or near-natively. Storing rendered math would be a one-way door.
- **`Callout` has a `kind` enum**, not a colour or emoji: `EXAM`, `PITFALL`,
  `UNCERTAIN`, `ASIDE`. Presentation is downstream.
- **`SourceAnchor` on every topic** is the feature that makes the notes trustworthy.
  Timestamp plus slide numbers, so any claim can be checked in seconds.
- **`CardSeed` is generated but ignored by document renderers.** Costs nothing to
  produce alongside the notes; makes the Anki target trivial later. Don't add a
  separate extraction pass for it.
- **`Figure` references a `MediaAsset` by id**, not a path. Assets are resolved by the
  emitter — inlined as base64, uploaded, or copied next to the output, as appropriate.

## Stable IDs

Plan §7.2, verbatim.

Topic ids must survive regeneration so that re-emitting **updates** rather than
duplicates. Derive them from source coordinates — `lecture_id + slide_range` — not from
position in the list or a slug of the heading, both of which move when you change a
prompt.

## Caption ingest (Phase 1)

Two invariants later phases depend on (P1-03/P1-04 decisions):

- **`Segment` spans are unions of cue spans.** A segment runs from the first cue that
  contributed to it to the last; two sentences from one cue share that cue's span.
  Spans may therefore overlap and **do not partition time** — sort by `start_s`, never
  assume a partition, never interpolate within a cue (the anchor must point where the
  words really are).
- **`ingest_captions(path)` is the only entrypoint.** `parse_vtt`/`parse_srt`,
  `dedupe_rolling` and `merge_sentences` are exported for debugging and tests, not for
  re-composition elsewhere; anything that needs segments calls `ingest_captions`.

`lecturenotes captions FILE [--json]` prints the segments for one file — a debugging
aid for bad chunks, not the product. It must not grow pairing or chunking logic.

## Slide ingest (Phase 2)

Invariants later phases depend on (P2-01..P2-04 decisions):

- **`ingest_slides(path)` is the only entrypoint.** `parse_pdf`, `parse_pptx`,
  `layout_page` and `clean_line` are exported for debugging and tests, not for
  re-composition elsewhere; the image rules (`min_px`, recurring) are applied inside
  `ingest_slides`, so anything that needs a `Deck` calls it.
- **`Slide.number` is the 1-based position in the file, hidden slides included**, so a
  `SlideRange` matches what a reader counts when they open the deck. Skip `hidden`
  slides if you must, never renumber.
- **Image ids are content hashes** of the extracted bytes (`img-` + 16 hex of sha256),
  and ingest never writes files: bytes stay in `SlideImage.data`. Phase 5 mints
  `MediaAsset` from `SlideImage` and owns where the bytes go. The same figure via PDF and
  PPTX has **different ids** (pypdf re-encodes the image stream) — never join decks on
  image id across formats.
- **`recurring_image_ids` are set aside on purpose** (a logo on more than half of ≥ 3
  slides): they stay in `assets` but leave every `image_ids`. Do not turn them into
  figures.

`lecturenotes slides FILE [--json] [--notes] [--min-px N]` prints one deck — titles,
blocks in reading order, images, recurring images — a debugging aid for interleaved
columns and logos-as-figures, not the product. It must not grow pairing or alignment
logic.

## Rendering (Phase 3)

Invariants later phases depend on (P3-01..P3-04 decisions):

- **`degrade(week, capabilities)` lives in `model/`** and takes a `set[Capability]`,
  never a renderer; renderers declare `capabilities` and never improvise degradation —
  the capability↔construct map is defined once, in `constructs_used`.
- **Every renderer surfaces anchors via `format_clock`** (from `render/base.py`) — the
  contract test greps every renderer's output for it, so timestamps built any other
  way fail the suite.
- **Renderers are pure** (`NoteWeek` in, `RenderResult` out, no IO); **emitters own IO
  and never read the IR.** Asset files are id-keyed via the shared `asset_target`, so
  links and paths cannot drift and re-emits update in place.
- **`tests/fixtures/notes/week01.md` is hand-written** and never regenerated from the
  code under test — it is the markdown format spec, not a snapshot.
- **`render/` and `emit/` never import `ingest/`, `align/` or `generate/`**
  (import-linter, 4 contracts).

`lecturenotes render FILE [-o DIR] [--json] [--format {anki,markdown}]` renders one
existing `NoteWeek` JSON with the chosen renderer (default `markdown`, so every
pre-P6-03 invocation is unchanged) — a debugging aid, and the §7.1 tuning loop: build
once, render cheaply many times, now across formats from the same cached JSON. It must
not grow pairing or generation logic; Phase 7 adds `notion` as one `_RENDERERS` entry
in `cli.py`.

## Alignment (Phase 4)

Invariants later phases depend on (P4-01..P4-04 decisions):

- **`align_lecture(deck, segments)` is the only entrypoint.** `tokenize`,
  `term_weights`, `slide_terms`, `score`, `span_units` and `solve_windows` are
  exported for debugging and tests, not for re-composition elsewhere.
- **Chunks partition the segments in order** and their slide ranges are
  non-decreasing; chunk spans are unions of member segment spans — they may overlap
  and leave holes, so sort by `start_s`, never assume a partition of time.
- **Segments whose spans overlap (one cue's sentences) are never split across
  chunks.**
- **Speaker notes and image bytes never influence alignment** — the PDF and PPTX of a
  deck align identically.
- **Gap chunks (`slides=None`) are the §4.1 gap signal** (board work): real content
  for generation, the frame-pull trigger for Phase 9, never dropped.
- **Hidden slides are skipped, never renumbered** — no chunk cites a slide the reader
  can't count to.

`lecturenotes align DECK CAPTIONS [--json] [--min-gap-s N] [--min-silence-s N]` takes
two explicit paths — a debugging aid that must not grow pairing (§7.4), chunk merging
(§9), or generation.

## Generation (Phase 5)

Invariants later phases depend on (P5-01..P5-04 decisions):

- **`generate_lecture(deck, chunks, ...)` is the only entrypoint.** `merge_chunks`,
  `generate_topic`, the prompt builders and the client/cache types are exported for
  debugging and tests, not for re-composition elsewhere; the merge, both passes,
  figure verification and asset minting all happen inside it.
- **The fake is keyed by `request.key`, the cache by `prompt_version + model +
  prompt`.** Request keys are `chunk:` + the §7.2 topic id (or `synthesis:<lecture>`),
  never a prompt hash — prompt tuning must not break recorded fixtures; a tuned
  prompt, model switch, or `PROMPT_VERSION` bump re-generates on purpose (§7.1).
  Nothing consults `ANTHROPIC_API_KEY` at import time, client construction, or during
  `--dry-run` — only a real `complete` does.
- **The merge floor is 100 words (`--min-words`), and gap chunks fence merging.** An
  under-floor slide chunk merges into an adjacent slide chunk, never across a gap and
  never into one — board work must not cite slides, and the §4.1 gap signal must
  survive for Phase 9. Dry-run chunking and real-run chunking go through the same
  `merge_chunks` call with the same floor, always.
- **Assets are minted id-keyed into `media/`**, only for images a `Figure` actually
  references; `MediaAsset.source` is a POSIX path relative to the week JSON's
  directory, so re-runs overwrite in place and the P3-03 emitter needs no change.
- **Pairing is sorted filename order, printed, and confirmed** — never inferred
  (§7.4). Non-TTY stdin without `--yes` is a hard error, never a hang or a silent
  proceed.

`lecturenotes build PATHS... --course TEXT --week N [-o DIR] [--dry-run] [--yes]
[--model ID] [--min-words N] [--cache-dir DIR]` writes `<out>/<week_id>.json` plus
`media/`; `render` presents it (§7.1's tuning loop, two commands). It must not grow
rendering, emitting, or a format flag before Phase 6, nor alignment knobs
(`--min-gap-s`/`--min-silence-s` stay on `align`, the debugging aid).

## Anki deck (Phase 6)

Invariants later phases depend on (P6-01..P6-03 decisions):

- **Every topic carries ≥ 1 card** — a generation guarantee, pinned in the chunk
  prompt (P6-01), never patched in a renderer: a renderer that padded missing cards
  would be inventing content.
- **Card guids are 16 hex of sha256 over `topic_id + "\n" + raw front`** (the IR
  front, before math translation) — renderer-local, in `render/anki.py`, never in
  `model/ids.py`. A reworded front is deliberately a *new* card; re-importing an
  unchanged deck updates in place (§7.2, observed against a real Anki).
- **The deck is `CardSeed`s only.** Glossary definitions stay out; a card-less topic
  contributes no rows.
- **Paired `$…$` → `\(…\)` in card fields** is the renderer-local math dialect for
  Anki's MathJax, applied nowhere outside `render/anki.py`; unpaired `$` passes
  through.
- **`--format` selects presentation only** — `render` grows no pairing, generation or
  alignment logic; both formats read the same cached week JSON.

## Boundary rules

- `model/` imports nothing else in the package.
- `render/` never imports `ingest/`.

import-linter enforces these: the contracts live in `pyproject.toml`
(`[tool.importlinter]`) and `tests/test_boundaries.py` runs `lint-imports` from inside
`pytest`, so a violation fails the ordinary test run, not only `uv run lint-imports`.

## Checks

```
uv sync --all-groups
uv run pytest
uv run ruff check .
uv run mypy
uv run lint-imports
uv run lecturenotes captions tests/fixtures/captions/lecture01.vtt   # smoke: 22 lines
uv run lecturenotes slides tests/fixtures/decks/lecture01.pdf         # smoke: 3 slides
uv run lecturenotes render tests/fixtures/notes/week01.json           # smoke: 1 document
uv run lecturenotes render tests/fixtures/notes/week01.json --format anki   # smoke: 8 cards
uv run lecturenotes align tests/fixtures/decks/lecture01.pdf tests/fixtures/captions/lecture01.vtt   # smoke: 4 chunks
uv run lecturenotes build tests/fixtures/decks/lecture01.pptx tests/fixtures/captions/lecture01.vtt --course CS-RL-101 --week 1 --dry-run   # smoke: 1 pairing, 4 chunks
```

## Working conventions

- One phase per session (plan §6). Each phase has explicit done-criteria.
- Tests first for done-criteria: write the tests that encode "done" before the code.
- When the IR must change, change `model/` and let mypy find the breakage rather than
  patching renderers individually (plan §10).
