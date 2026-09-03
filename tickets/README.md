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
| [P3-01](P3-01-render-contract-and-degrade.md) | `render/base.py` contract types, `degrade()`, contract tests retyped | P2-04 | `degrade(week01, ALL - {X})` removes each construct `X` for all 64 capability subsets and the result validates; contract file typed `list[Renderer]` with the four properties implemented (still skipping); `format_clock` moved with CLI output unchanged |
| [P3-02](P3-02-markdown-renderer.md) | Markdown renderer + hand-written expected markdown | P3-01 | Rendering `week01` yields one `cs-rl-101-w01.md` equal to the hand-written `week01.md` byte-for-byte; all four contract properties pass un-skipped for `MarkdownRenderer` |
| [P3-03](P3-03-filesystem-emitter.md) | `emit/filesystem.py` + emit boundary contract | P3-01 | A hand-built `RenderResult` lands as UTF-8/LF files under `tmp_path` with the PNG copied byte-for-byte to `assets/`; re-emit overwrites in place; `lint-imports` reports 4 contracts, 0 broken |
| [P3-04](P3-04-render-command-and-done-gate.md) | `lecturenotes render FILE [-o DIR]` + Phase 3 done-gate | P3-02, P3-03 | `render week01.json` prints 1 document matching the expected markdown; `-o` writes the page + 1 asset; done-gate ticked; tickets moved; `CLAUDE.md` invariants added |

**Suggested order:** P3-01 first; P3-02 and P3-03 are independent of each other and can
go in either order (both need only P3-01's types — the emitter's tests hand-build
`RenderResult` values and never import a renderer); P3-04 last.

### Phase 3 done-gate

- [ ] The plan §6 done-criterion is a passing test: `tests/render/test_markdown.py`
      compares the rendered `week01` fixture byte-for-byte against the hand-written
      `tests/fixtures/notes/week01.md`.
- [ ] The four renderer contract properties (plan §8) run un-skipped against
      `MarkdownRenderer` in `tests/contract/test_renderers.py`.
- [ ] From a clean checkout:

```
uv sync --all-groups
uv run pytest && uv run ruff check . && uv run mypy && uv run lint-imports
```

passes, and `uv run lecturenotes render tests/fixtures/notes/week01.json` prints
1 document.

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
`python-pptx` and `pypdf` become runtime dependencies in Phase 2 (P2-01, P2-02).
