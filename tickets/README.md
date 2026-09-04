# Tickets

Work items for `PROJECT_PLAN.md`, one file per ticket. Each ticket is sized for a
single Claude Code session and has command-based acceptance criteria so "done" can be
checked without judgment calls. Open tickets live in this directory; finished ones move
to `completed/`.

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

**Phase 0 is done.**

## Phase 1 — Caption ingest

Plan §6: *done when the rolling-caption fixture dedupes; tags stripped; segments merge
on sentence boundaries.* Plan §3 stage 1: `.vtt` / `.srt` → `[Segment]`, a pure
function. Plan §10: tests first — "the caption-dedupe edge cases are the whole
difficulty" — and property-based tests for the pure stages.

All of Phase 1 lives in one module, `lecturenotes/ingest/captions.py`, as three pure
functions plus a composing entrypoint; each ticket adds one stage and consumes the
previous ticket's output:

```
parse_vtt / parse_srt  → [Cue]        P1-01   (tags stripped here)
dedupe_rolling         → [Cue]        P1-02
merge_sentences        → [Segment]    P1-03
ingest_captions(path)  → [Segment]    P1-03   (parse → dedupe → merge, by suffix)
```

| ID | Title | Depends on | Done when |
|---|---|---|---|
| [P1-01](completed/P1-01-caption-parsing-and-tags.md) | `Cue`/`Segment` types, VTT + SRT parsing, tag stripping | P0-04 | Both fixtures parse to the *same* 20 clean cues; `strip_tags` handles the no-whitespace timing-tag case; hypothesis round-trip passes |
| [P1-02](completed/P1-02-rolling-caption-dedupe.md) | Rolling-caption dedupe | P1-01 | Fixture cues 1–6 collapse to seven lines with original timings; cues 7–20 untouched; dedupe is idempotent under hypothesis |
| [P1-03](completed/P1-03-sentence-merge-and-segments.md) | Sentence-boundary merge, `ingest_captions()`, expected-segments snapshot | P1-02 | Hand-written `lecture01.segments.json` (22 segments) equals `ingest_captions()` on both VTT and SRT |
| [P1-04](completed/P1-04-captions-command-and-done-gate.md) | `lecturenotes captions FILE` inspection command + Phase 1 done-gate | P1-03 | `lecturenotes captions <vtt>` prints 22 lines; done-gate ticked; tickets moved to `completed/` |

**Suggested order:** strictly P1-01 → P1-02 → P1-03 → P1-04; each function consumes
the previous one's output, so there is no parallelism here.

### Phase 1 done-gate

- [x] The plan §6 done-criterion is a passing test: `tests/ingest/test_ingest_captions.py`
      compares `ingest_captions()` against the hand-written `tests/fixtures/captions/lecture01.segments.json`.
- [x] Every row of the captions table in `tests/fixtures/README.md` has a test named after it under `tests/ingest/`
      (P1-04 added the last three, for cues 9, 10 and 16, which until then were covered only by the snapshot).
- [x] From a clean checkout (P1-04 closed Phase 1 on 2026-08-31):

```
uv sync --all-groups
uv run pytest && uv run ruff check . && uv run mypy && uv run lint-imports
```

passes, and `uv run lecturenotes captions tests/fixtures/captions/lecture01.vtt` prints
22 segments.

**Phase 1 is done.** Phase 2 tickets are below.

## Phase 2 — Slide ingest

Plan §6: *done when `.pptx` and `.pdf` both yield titles + bullets + speaker notes;
multi-column PDF reads in order.* Plan §3 stage 2: `.pptx` / `.pdf` → `Deck`, a pure
function ("text, speaker notes, rendered images"). Plan §10: tests first, property tests
for the pure layout step.

All of Phase 2 lives in one module, `lecturenotes/ingest/slides.py`, as two parsers, one
pure layout function and a composing entrypoint; each ticket adds one piece and reuses the
previous ticket's hand-written expected output:

```
Deck / Slide / TextBlock / SlideImage, clean_line   P2-01
parse_pptx(path)       → Deck                       P2-01   (text + notes + pictures)
ingest_slides(path)    → Deck                       P2-01   (dispatch by suffix)
layout_page(spans)     → PageLayout                 P2-02   (pure; columns, title, property-tested)
parse_pdf(path)        → Deck                       P2-02   (text; boilerplate dropped)
image rules (size, recurring) in ingest_slides      P2-03   (both formats; PDF images; groups)
lecturenotes slides FILE                            P2-04   (inspection command; done-gate)
```

| ID | Title | Depends on | Done when |
|---|---|---|---|
| [P2-01](completed/P2-01-deck-types-and-pptx.md) | `Deck`/`Slide` types, expected-deck fixture, PPTX parsing, `ingest_slides()` | P1-04 | Hand-written `lecture01.deck.json` equals `ingest_slides()` on the PPTX; ad-hoc python-pptx cases pass; python-pptx is a runtime dep |
| [P2-02](completed/P2-02-pdf-layout-and-reading-order.md) | PDF layout: columns in reading order, title, boilerplate; `parse_pdf` | P2-01 | PDF titles + blocks equal the PPTX deck's; slide 2 reads left column then right; footer gone; layout property tests pass |
| [P2-03](completed/P2-03-slide-images-and-assets.md) | Slide images and assets: PDF images, size filter, recurring-image rule, groups | P2-02 | Both formats yield one 240×150 `image/png` on slide 3; logo-on-every-slide and tiny-image ad-hoc cases pass; PDF full-deck test passes |
| [P2-04](completed/P2-04-slides-command-and-done-gate.md) | `lecturenotes slides FILE` inspection command + Phase 2 done-gate | P2-03 | `slides <pdf>` prints 3 slides; done-gate ticked; tickets moved to `completed/`; `CLAUDE.md` invariants added |

**Suggested order:** strictly P2-01 → P2-02 → P2-03 → P2-04; the PDF ticket compares
against the PPTX ticket's fixture, the image ticket needs both parsers, and the command
prints the finished `Deck`.

### Phase 2 done-gate

- [x] The plan §6 done-criterion is a passing test: `tests/ingest/test_ingest_slides.py`
      compares `ingest_slides()` on **both** `lecture01.pptx` and `lecture01.pdf` against the
      hand-written `tests/fixtures/decks/lecture01.deck.json` (PPTX half P2-01, PDF half P2-03).
- [x] Every row of the decks table in `tests/fixtures/README.md` has a test named after it
      under `tests/ingest/` (`test_slide_1_…`, `test_slide_2_…`, `test_slide_3_…` in
      `test_pptx.py` and `test_pdf.py`; `test_footer_is_dropped_as_boilerplate` in `test_pdf.py`).
- [x] From a clean checkout (P2-04 closed Phase 2 on 2026-09-01):

```
uv sync --all-groups
uv run pytest && uv run ruff check . && uv run mypy && uv run lint-imports
```

passes, and `uv run lecturenotes slides tests/fixtures/decks/lecture01.pdf` prints
3 slides.

**Phase 2 is done.** Phase 3 tickets are below.

## Phase 3 — Markdown renderer + filesystem emitter

Plan §6: *done when the hand-written `NoteWeek` fixture renders to a readable file.*
Plan §2.3: renderers declare capabilities; a shared `degrade()` rewrites the IR against
them before rendering; delivery is a separate emitter so rendering is testable with no
network. Plan §8: contract tests parametrised over every renderer; snapshot tests on
the markdown renderer.

Phase 3 fills `render/base.py`, `render/markdown.py` and `emit/filesystem.py`, plus the
`degrade()` slot reserved in `model/capabilities.py`; the contract-test stub in
`tests/contract/test_renderers.py` is retyped and its four properties go live:

```
Renderer / RenderOptions / RenderResult, asset_target, format_clock   P3-01
degrade(week, caps) / constructs_used(week)   (model/)                P3-01
MarkdownRenderer → one week page                                      P3-02
emit_filesystem(result, out_dir)  + emit boundary contracts           P3-03
lecturenotes render FILE [-o DIR]                                     P3-04
```

| ID | Title | Depends on | Done when |
|---|---|---|---|
| [P3-01](completed/P3-01-render-contract-and-degrade.md) | `render/base.py` contract types, `degrade()`, contract tests retyped | P2-04 | `degrade(week01, ALL - {X})` removes each construct `X` for all 64 capability subsets and the result validates; contract file typed `list[Renderer]` with the four properties implemented (still skipping); `format_clock` moved with CLI output unchanged |
| [P3-02](completed/P3-02-markdown-renderer.md) | Markdown renderer + hand-written expected markdown | P3-01 | Rendering `week01` yields one `cs-rl-101-w01.md` equal to the hand-written `week01.md` byte-for-byte; all four contract properties pass un-skipped for `MarkdownRenderer` |
| [P3-03](completed/P3-03-filesystem-emitter.md) | `emit/filesystem.py` + emit boundary contract | P3-01 | A hand-built `RenderResult` lands as UTF-8/LF files under `tmp_path` with the PNG copied byte-for-byte to `assets/`; re-emit overwrites in place; `lint-imports` reports 4 contracts, 0 broken |
| [P3-04](completed/P3-04-render-command-and-done-gate.md) | `lecturenotes render FILE [-o DIR]` + Phase 3 done-gate | P3-02, P3-03 | `render week01.json` prints 1 document matching the expected markdown; `-o` writes the page + 1 asset; done-gate ticked; tickets moved; `CLAUDE.md` invariants added |

**Suggested order:** P3-01 first; P3-02 and P3-03 are independent of each other and can
go in either order (both need only P3-01's types — the emitter's tests hand-build
`RenderResult` values and never import a renderer); P3-04 last.

### Phase 3 done-gate

- [x] The plan §6 done-criterion is a passing test: `tests/render/test_markdown.py`
      compares the rendered `week01` fixture byte-for-byte against the hand-written
      `tests/fixtures/notes/week01.md`.
- [x] The four renderer contract properties (plan §8) run un-skipped against
      `MarkdownRenderer` in `tests/contract/test_renderers.py`.
- [x] From a clean checkout (P3-04 closed Phase 3 on 2026-09-03):

```
uv sync --all-groups
uv run pytest && uv run ruff check . && uv run mypy && uv run lint-imports
```

passes, and `uv run lecturenotes render tests/fixtures/notes/week01.json` prints
1 document.

**Phase 3 is done.** Phase 4 tickets are below.

## Phase 4 — Alignment

Plan §6: *done when the fixture deck maps to correct spans in order; gaps flagged.*
Plan §3 stage 4: `Deck` + `[Segment]` → `[Chunk]`, a pure function, monotonic. Plan
§4.1: score slide vocabulary against transcript segments weighting rare terms, solve
for *monotonic* boundaries rather than matching slides independently, and surface the
**gap signal** (minutes of speech with no matching slide content — board work). Plan
§10: property tests — alignment output must be monotonic and must partition the
segments, for any input.

Phase 4 fills `lecturenotes/align/` with two modules — pure scoring, then the solve —
plus the entrypoint; each ticket consumes the previous ticket's output, and the
expected chunks are pinned by the slide → time map in `tests/fixtures/README.md`
(whose spans are, by design, the `week01` notes fixture's topic anchors):

```
tokenize / term_weights / slide_terms / score      align/scoring.py     P4-01
span_units, solve_windows (monotonic DP)           align/boundaries.py  P4-02
gap carving, Chunk, align_lecture(deck, segments)  align/boundaries.py  P4-03
lecturenotes align DECK CAPTIONS                   cli.py               P4-04
```

| ID | Title | Depends on | Done when |
|---|---|---|---|
| [P4-01](completed/P4-01-tokens-and-rare-term-scoring.md) | Tokens, rare-term weights, slide↔segment scoring | P3-04 | `w("bellman") > w("equation")` on the fixture; every board-work segment shares < 2 scoring terms with every slide; speaker notes never score |
| [P4-02](completed/P4-02-monotonic-window-dp.md) | Span units and the monotonic window DP | P4-01 | Fixture yields 16 units and windows opening at segments 1/13/19; DP equals brute force (optimum *and* tie-break) under hypothesis; the generic "equation" does not advance segment 4 |
| [P4-03](completed/P4-03-gap-carving-and-align-lecture.md) | Gap carving, `Chunk`, `align_lecture()`, expected-chunks fixture | P4-02 | Hand-written `lecture01.chunks.json` equals `align_lecture()` on PPTX+VTT **and** PDF+SRT; the dice detour is a `slides=None` gap chunk spanning 151–268; partition + monotonicity property tests pass |
| [P4-04](completed/P4-04-align-command-and-done-gate.md) | `lecturenotes align DECK CAPTIONS` inspection command + Phase 4 done-gate | P4-03 | `align <pdf> <vtt>` prints 4 chunks with one `(no slide)` header; done-gate ticked; tickets moved to `completed/`; `CLAUDE.md` invariants added |

**Suggested order:** strictly P4-01 → P4-02 → P4-03 → P4-04; the DP consumes the
scores, the entrypoint composes both, and the command prints the finished chunks — no
parallelism here.

### Phase 4 done-gate

- [x] The plan §6 done-criterion is a passing test: `tests/align/test_align_lecture.py`
      compares `align_lecture()` on **both** deck formats and **both** caption formats
      against the hand-written `tests/fixtures/align/lecture01.chunks.json`, with the
      board-work gap flagged as a `slides=None` chunk.
- [x] Every row of the slide → time map in `tests/fixtures/README.md` has a test named
      after it under `tests/align/`, and the plan §10 properties (monotonic; partitions
      the segments, for any input) run under hypothesis.
- [x] From a clean checkout (P4-04 closed Phase 4 on 2026-09-04):

```
uv sync --all-groups
uv run pytest && uv run ruff check . && uv run mypy && uv run lint-imports
```

passes, and `uv run lecturenotes align tests/fixtures/decks/lecture01.pdf
tests/fixtures/captions/lecture01.vtt` prints 4 chunks.

**Phase 4 is done.** Phase 5 tickets are below.

## Phase 5 — Generation (chunk + synthesis)

Plan §6: *done when `build --dry-run` shows chunking; real run produces valid
`NoteWeek`.* Plan §3 stage 5: `[Chunk]` → `NoteLecture` — the LLM stage, a per-chunk
pass plus a lecture-level synthesis pass (§4.2), with `Callout(EXAM)` and
`Callout(UNCERTAIN)` carrying the highest-value content. Plan §7.1: responses cached
by `hash(chunk_content + prompt_version + model)`. Plan §7.4: the file pairing is
printed and confirmed. Plan §8: the LLM client sits behind an interface with a
recorded-response fake — no test touches the network — and `--dry-run` stops before
generation and prints the chunking. The two §9 decisions flagged "worth settling
before phase 5" are settled: a word-count merge floor (default 100 — P5-02 records
why not the suggested 120) and prose summary + bullet key points per topic.

Phase 5 fills `lecturenotes/generate/` with three modules — the client seam and
cache, then prompts and assembly — plus the `build` command; each ticket consumes the
previous ticket's output, and the hand-written fixtures close the loop the P4-03
spans were designed for: with the recorded fake, ingest → align → generate reproduces
the `week01` lec01 notes that Phase 3 renders.

```
GenRequest / LLMClient / AnthropicClient / RecordedClient  generate/client.py   P5-01
response_key, CachedClient                                 generate/cache.py    P5-01
PROMPT_VERSION, ChunkNotes, chunk_prompt                   generate/prompts.py  P5-02
merge_chunks, generate_topic                               generate/lecture.py  P5-02
LectureSynthesis, synthesis_prompt                         generate/prompts.py  P5-03
asset minting, generate_lecture(deck, chunks)              generate/lecture.py  P5-03
lecturenotes build PATHS... (pairing, --dry-run)           cli.py               P5-04
```

| ID | Title | Depends on | Done when |
|---|---|---|---|
| [P5-01](completed/P5-01-llm-client-fake-and-cache.md) | LLM client seam, recorded-response fake, response cache | P4-04 | `RecordedClient` serves by request key and misses loudly; the cache key changes iff `prompt_version`/model/prompt does; `anthropic` is a runtime dep; nothing needs an API key at import time |
| [P5-02](completed/P5-02-chunk-prompts-and-topic-generation.md) | Chunk pass: `merge_chunks`, chunk prompt, `generate_topic()`, responses fixture | P5-01 | The fixture chunks (81/120/103/103 words) survive the 100-word floor; the 4 generated topics reproduce `week01` lec01's (PPTX image id on the figure); EXAM-verbatim and UNCERTAIN prompt instructions pinned by tests |
| [P5-03](completed/P5-03-synthesis-and-generate-lecture.md) | Synthesis pass, asset minting, `generate_lecture()`, expected-notes fixture | P5-02 | `generate_lecture()` on PPTX+VTT with the fake equals the hand-written `lecture01.notes.json` in exactly 5 requests; `media/img-….png` written byte-equal to the deck asset |
| [P5-04](completed/P5-04-build-command-and-done-gate.md) | `lecturenotes build` (pairing, `--dry-run`, real run) + Phase 5 done-gate | P5-03 | `build <pptx> <vtt> --course CS-RL-101 --week 1 --dry-run` prints 1 pairing + 4 chunks with no API key; the fake-driven real run writes `cs-rl-101-w01.json` that `render` accepts; done-gate ticked; tickets moved to `completed/`; `CLAUDE.md` invariants added |

**Suggested order:** strictly P5-01 → P5-02 → P5-03 → P5-04; the prompts need the
client seam, the entrypoint composes the chunk pass, and the command composes
everything — no parallelism here.

### Phase 5 done-gate

- [x] The plan §6 dry-run criterion is a passing test: `tests/test_cli.py` drives
      `build --dry-run` on the committed PPTX+VTT and gets the pairing plus the 4
      chunks with no client constructed and no `ANTHROPIC_API_KEY` set
      (`test_build_dry_run_prints_pairing_then_4_chunks_with_no_client`, P5-04).
- [x] The plan §6 real-run criterion — "real run produces valid `NoteWeek`" — is
      checked manually once with a real `ANTHROPIC_API_KEY` (no pytest test touches
      the network, plan §8): `build` on the fixture PPTX+VTT into a scratch dir,
      output validates and `lecturenotes render` accepts it. Run 2026-09-04 with
      `claude-opus-5` (the default model): `build` wrote
      `cs-rl-101-w01.json` (1 lecture, 4 topics, 1 asset) and `render` printed the
      full document — anchors, EXAM/UNCERTAIN callouts and the figure included.
- [x] From a clean checkout (checked 2026-09-04):

```
uv sync --all-groups
uv run pytest && uv run ruff check . && uv run mypy && uv run lint-imports
```

passes, and `uv run lecturenotes build tests/fixtures/decks/lecture01.pptx
tests/fixtures/captions/lecture01.vtt --course CS-RL-101 --week 1 --dry-run` prints
1 pairing and 4 chunks.

**Phase 5 is done.** Phase 6 tickets are not written yet.

## Ticket format

```
# P<phase>-NN — Title
Phase <phase> · Depends on: … · Size: S/M/L

## Goal            one paragraph: what exists after this ticket that didn't before
## Scope           In / Out bullet lists — Out names the ticket or phase that owns it
## Tasks           ordered checklist
## Acceptance criteria   commands or observable facts, checkable by the next session
## Decisions & notes     choices made here that later phases must respect, and why
```

## Stack (pinned)

Python 3.12 · uv · pydantic v2 · pytest · hypothesis (from P1-01) · ruff · mypy (strict) · import-linter.
Fixture generation uses `reportlab` and `python-pptx` in a separate `fixtures` dependency group;
`python-pptx` and `pypdf` become runtime dependencies in Phase 2 (P2-01, P2-02);
`anthropic>=1` becomes a runtime dependency in Phase 5 (P5-01), with `claude-opus-5`
as the default model.
