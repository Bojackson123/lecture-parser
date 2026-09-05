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

**Phase 5 is done.** Phase 6 tickets are below.

## Phase 6 — Anki renderer

Plan §6: *done when the same `NoteWeek` produces a deck — any IR flaw surfaces here.*
The plan calls this "the real checkpoint": Anki is not a document — atomic cards, no
hierarchy — so it exercises the IR in a direction no document renderer will (§2.2:
`CardSeed` is the Anki target's input; §7.2: re-emitting must update, not duplicate;
§8: the contract properties now face a second, structurally alien renderer). Two IR
flaws are known going in, and P6-01 resolves both before any renderer code: two
`week01` topics have no cards (so their anchors would vanish from a cards-only deck,
failing contract property 4), and `CardSeed` has no stable identity (so Anki
re-import would duplicate). The deck format is Anki's notes-in-plain-text TSV — pure
text, so the pure-renderer contract, determinism and the hand-written byte-for-byte
fixture doctrine all survive contact with Anki.

```
cards on every topic, prompt pin, week01.anki.txt (spec)   fixtures + generate/prompts.py   P6-01
AnkiRenderer (guid, quoting, $…$→\(…\)), contract reg.     render/anki.py                   P6-02
lecturenotes render FILE --format {markdown,anki}          cli.py                           P6-03
```

| ID | Title | Depends on | Done when |
|---|---|---|---|
| [P6-01](completed/P6-01-card-coverage-and-expected-deck.md) | Card coverage, prompt pin, hand-written expected deck | P5-04 | Every `week01` topic has ≥ 1 card and the P5 fixtures agree; "at least one card per topic" pinned in the chunk prompt; `week01.anki.txt` committed with 6 header lines + 8 rows; `week01.md` untouched |
| [P6-02](completed/P6-02-anki-renderer.md) | Anki renderer | P6-01 | `AnkiRenderer` output equals `week01.anki.txt` byte-for-byte with an empty asset manifest; guid/quoting/math ad-hoc cases pass; all four contract properties pass for both renderers |
| [P6-03](completed/P6-03-render-format-flag-and-done-gate.md) | `render --format` flag + Phase 6 done-gate | P6-02 | `render week01.json --format anki` prints the 8-card deck and the default stays markdown; real-Anki double-import shows 8 added then 0; done-gate ticked; tickets moved; `CLAUDE.md` invariants added |

**Suggested order:** strictly P6-01 → P6-02 → P6-03; the expected deck is the
renderer's spec, and the flag needs a second renderer to select — no parallelism
here.

### Phase 6 done-gate

- [x] The plan §6 done-criterion is a passing test: `tests/render/test_anki.py`
      compares `AnkiRenderer` on the `week01` fixture byte-for-byte against the
      hand-written `tests/fixtures/notes/week01.anki.txt` (P6-02).
- [x] The four renderer contract properties (plan §8) pass un-skipped for **both**
      `markdown` and `anki` in `tests/contract/test_renderers.py` (P6-02).
- [x] The §7.2 criterion is observed for real, once, manually: the emitted `.txt`
      imported into a real Anki adds 8 notes; importing it again adds 0 (guids
      update in place). Run 2026-09-04: first import added the 8 notes; importing
      the identical file again added 0 — 7 reported unchanged and 1 (the Bellman
      formula card) reported updated in place, an Anki field-normalization artifact,
      not a duplicate. Update-not-duplicate observed end-to-end.
- [x] From a clean checkout (checked 2026-09-04):

```
uv sync --all-groups
uv run pytest && uv run ruff check . && uv run mypy && uv run lint-imports
```

passes, and `uv run lecturenotes render tests/fixtures/notes/week01.json --format
anki` prints 1 document with 8 card rows.

**Phase 6 is done.** Phase 7 tickets are below.

## Phase 7 — Notion renderer + emitter

Plan §6: *done when limits enforced; contract tests pass.* Plan §2.3 names the
limits and rules where they live: "Notion's 2,000-char rich-text cap, 100-element
children arrays, 2-level nesting, 1,000-block payloads … All renderer-local. None of
it appears in the IR or upstream." Plan §5: `render/notion.py` and
`emit/notion_api.py`; delivery is a separate emitter so rendering stays testable
with no credentials and no network (§2.3, §8), and §7.2's update-not-duplicate must
hold at the page level — a re-emit updates the same Notion page, never creates a
sibling. Two decisions taken with the user (2026-09-04): **one page per week** (H1
section per lecture, mirroring markdown) and **stdlib urllib** for the real
transport (no new runtime dependency; every test runs against an in-package fake,
the P5-01 seam pattern).

The renderer emits the page as one JSON document — `{"page", "payloads"}`, blocks
in Notion API shape verbatim, figures as asset placeholders the emitter resolves by
uploading — so the hand-written fixture doctrine, byte-equality and the four
contract properties all survive contact with an API target:

```
week01.notion.json (hand-written payload spec)      fixtures               P7-01
NotionRenderer (blocks, rich text, math, anchors)   render/notion.py       P7-02
the four §2.3 limits, under hypothesis              render/notion.py       P7-03
NotionTransport seam + fake, emit_notion()          emit/notion_api.py     P7-04
render --format notion; lecturenotes push           cli.py                 P7-05
```

| ID | Title | Depends on | Done when |
|---|---|---|---|
| [P7-01](completed/P7-01-notion-payload-spec-and-fixture.md) | Notion payload spec + hand-written expected fixture | P6-03 | `week01.notion.json` committed — 1 page, all 9 node types mapped, every anchor via the `format_clock` string, 1 asset placeholder; sanity tests pass; existing fixtures untouched |
| [P7-02](completed/P7-02-notion-renderer.md) | Notion renderer | P7-01 | `NotionRenderer` output equals `week01.notion.json` byte-for-byte with a 1-asset manifest; math/callout/citation ad-hoc cases pass; all four contract properties pass for all three renderers (12 tests, no skips) |
| [P7-03](completed/P7-03-notion-limits.md) | Notion limits | P7-02 | Rich text ≤ 2,000 chars, children arrays ≤ 100, payloads ≤ 1,000 blocks, nesting ≤ 2 — under hypothesis for arbitrary weeks; boundary cases pass; `week01.notion.json` byte-unchanged |
| [P7-04](completed/P7-04-notion-emitter.md) | Notion emitter: transport seam, fake, `emit_notion()` | P7-01 | Fake-transport sequences pass: fresh emit creates page + uploads + appends in order; re-emit finds by title, archives children, appends — same page id, no `create_page`; placeholders swapped; no test touches network or env |
| [P7-05](completed/P7-05-push-command-and-done-gate.md) | `--format notion`, `lecturenotes push` + Phase 7 done-gate | P7-03, P7-04 | `render --format notion` prints the payload (default stays markdown); `push` errors cleanly without `NOTION_TOKEN` and runs the full sequence against an injected fake; manual double push updates one real page in place; done-gate ticked; tickets moved; `CLAUDE.md` invariants added |

**Suggested order:** P7-01 first — it is the spec both halves implement. Then
P7-02 → P7-03 on the render side, with **P7-04 in parallel** to either: the
emitter's tests hand-build `RenderResult` values from the P7-01 spec and never
import a renderer (the P3-03 independence, reused). P7-05 last.

### Phase 7 done-gate

- [x] The plan §6 *contract tests pass* criterion: the four renderer contract
      properties (plan §8) pass un-skipped for **`markdown`, `anki` and `notion`**
      in `tests/contract/test_renderers.py` (12 tests) (P7-02).
- [x] The plan §6 *limits enforced* criterion: each of the four §2.3 limits is
      pinned by a named test in `tests/render/test_notion_limits.py`, and the
      hypothesis properties (caps hold, text preserved, for any week) pass (P7-03).
- [x] The §7.2 criterion is observed for real, once, manually: `push` of the
      fixture week to a scratch Notion page, run twice — the first creates the
      page (figure and math rendering), the second updates the **same page at the
      same URL** with no duplicate sibling. Run 2026-09-04 against a real
      workspace (`--asset-root .` from the repo root — the fixture's sources are
      repo-root-relative, the P3-04 quirk): the first push created
      "CS-RL-101 — Week 1" under the scratch page with all 57 top-level blocks
      (2 lecture H1s, the figure image from the uploaded PNG, 3 equation blocks,
      5 callouts — verified over the API); the second push updated the **same
      page id** (`…81bc-b514-c869ce96114f`) in place, the parent still holding
      exactly one child page. No duplicate sibling. §7.2 end-to-end.
- [x] From a clean checkout, with no `NOTION_TOKEN` set (checked 2026-09-04):

```
uv sync --all-groups
uv run pytest && uv run ruff check . && uv run mypy && uv run lint-imports
```

passes, and `uv run lecturenotes render tests/fixtures/notes/week01.json --format
notion` prints 1 document whose body parses as JSON with keys `page` and
`payloads`.

**Phase 7 is done.** Phase 8 tickets are not written yet.

## Side-track W — local web GUI (`lecturenotes serve`)

Plan §1 lists a GUI as out of v1 scope, so this is a deliberate side-track, outside
the §6 phase ladder: Phase 8 (verification) and Phase 9 (video) keep their numbers
and depend on no PW ticket. The deliverable is `lecturenotes serve` — a local
FastAPI server (the **`web` dependency group**, in `default-groups` so a plain
`uv sync` installs it; runtime deps unchanged — originally shipped as an extra,
reworked when a plain `uv sync` uninstalled it) with a plain HTML/JS single page
(no Node, no CDN) that walks the full
pipeline: upload/select a week's files, see and **confirm** the §7.4 pairing,
preview the dry-run chunking (spending nothing), run the real build with progress,
review all three formats from the cached week JSON (§7.1's tuning loop), and push
to Notion. The web layer is a composer like `cli.py`: it calls the same library
entrypoints, grows no pipeline logic, and nothing in the pipeline may import it
back (5th import-linter contract).

```
pairing.py (moved from cli), web/ skeleton, serve      PW-01
/api/state, /api/upload, /api/pair + UI panels         PW-02
/api/dry-run + chunk-table panel                       PW-03
jobs.py, ProgressClient, /api/build + /api/job         PW-04
/api/render, /ws/ media, review panel                  PW-05
/api/push + done-gate                                  PW-06
```

| ID | Title | Depends on | Done when |
|---|---|---|---|
| [PW-01](completed/PW-01-web-skeleton-and-serve.md) | `pairing.py` extraction, `web/` skeleton, `serve` subcommand, 5th contract | P7-05 | `serve --no-browser` binds 127.0.0.1:8765 and serves the shell; missing-extra path prints the install hint (exit 2); `lint-imports` reports 5 contracts, 0 broken; existing suite and smoke commands unchanged |
| [PW-02](completed/PW-02-upload-state-and-pairing.md) | Workspace state, upload, pairing preview + Files/Pairing panels | PW-01 | Uploaded fixture pptx+vtt pair as `lec01`; a count mismatch returns the `collect_pairs` message verbatim (422); traversal filenames rejected |
| [PW-03](completed/PW-03-dry-run-preview.md) | Dry-run chunk preview + chunk-table panel | PW-02 | Fixture pair yields 4 chunks (one gap-flagged) and `total_requests == 5` with a raising client seam armed and no `ANTHROPIC_API_KEY` |
| [PW-04](completed/PW-04-build-job-and-progress.md) | Build job, `ProgressClient`, `/api/build` + `/api/job` | PW-03 | Recorded-fake job reaches `done` with progress 0→5 and writes a week JSON `render` accepts; pairing mismatch → 400; concurrent build → 409; no `sleep` in any job test |
| [PW-05](completed/PW-05-review-panel-and-render-api.md) | Review panel: `/api/render`, `/ws/` media serving, previews | PW-01 | `/api/render` equals CLI `render --json` per format for the week01 fixture; `/ws/` traversal → 403; figure displays in the markdown preview |
| [PW-06](PW-06-push-and-done-gate.md) | `/api/push` + Side-track W done-gate | PW-04, PW-05 | Fake-transport push runs the P7-04 sequence; missing-token error names `NOTION_TOKEN` and `.env`; manual browser build+push recorded; done-gate ticked; tickets moved |

**Suggested order:** PW-01 → PW-02 → PW-03 → PW-04, with **PW-05 in parallel** to
any of PW-02..04 (it reads existing week JSONs and needs no build); PW-06 last.

### Side-track W done-gate

- [ ] All six tickets' acceptance criteria met — everything automated is green;
      PW-06 stays open until its manual browser run (below) is recorded.
- [x] The §7.4 ritual survives the GUI: pairing is displayed and explicitly
      confirmed, and `/api/build` rejects a confirmation that does not match what
      the server would run — pinned by
      `tests/web/test_build_api.py::test_build_without_a_matching_pairs_echo_is_400_and_starts_nothing`.
- [x] `/api/dry-run` constructs no client and consults no key — pinned by every
      test in `tests/web/test_dry_run.py` (the P5-04 `no_client` doctrine, ported
      to the `web.app._make_client` seam).
- [ ] One manual end-to-end run through the browser recorded: upload the fixture
      pptx+vtt, confirm the pairing, 4 chunks / 5 requests in dry-run, real build,
      all three format previews (figure rendering), push twice to a scratch Notion
      page updating the same page in place.
- [x] Checked 2026-09-04 (the suite, ruff, mypy and lint-imports, plus every
      CLAUDE.md smoke command byte-unchanged):

```
uv sync --all-groups
uv run pytest && uv run ruff check . && uv run mypy && uv run lint-imports
```

passes (5 contracts, 0 broken), and `uv run lecturenotes serve --no-browser` binds
http://127.0.0.1:8765.

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
