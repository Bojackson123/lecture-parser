# Test fixtures

One mock lecture — *Lecture 1: MDPs and the Bellman Equation* — as captions and as a
slide deck, designed so that every later phase has its hard cases on committed data
(plan §8). Each row below is a future test's name: if a phase needs a case that isn't
here, add it *here* and update these tables rather than inventing a second fixture.

```
captions/lecture01.vtt      20 cues, hand-written (the canonical caption fixture)
captions/lecture01.srt      the same 20 cues as SRT
captions/lecture01.segments.json  the 22 segments both files ingest to, hand-written (P1-03)
decks/make_deck.py          generator for the three files below (uv run --group fixtures)
decks/lecture01.pdf         3 landscape pages, slide 2 two-column
decks/lecture01.pptx        3 slides, speaker notes on every slide, PNG on slide 3
decks/lecture01.deck.json   the PPTX deck as `Deck` JSON, hand-written (P2-01); the PDF yields
                            the same titles and blocks with `notes: null` (P2-02) and the same
                            figure re-encoded, so with a different id (P2-03)
decks/value_iteration.png   the figure embedded in both decks (1.4 KB; PPTX embeds it verbatim,
                            the PDF re-encodes it)
align/lecture01.chunks.json the four chunks alignment must produce, hand-written (P4-03)
generate/lecture01.responses.json  recorded LLM responses, one per chunk request key
                            plus the synthesis key, hand-transcribed from notes/week01.py
                            (P5-02, synthesis entry P5-03)
generate/lecture01.notes.json  the NoteLecture the fake pipeline must produce,
                            hand-written (P5-03): week01 lec01 with three deliberate
                            differences (source paths, figure asset id, minted asset)
notes/week01.py             hand-written NoteWeek builder covering the whole IR (P0-04)
notes/week01.json           its committed snapshot; regenerate with `--write`, never by hand
notes/week01.md             the week rendered as one markdown page, hand-written (P3-02);
                            transcribed from week01.py and never regenerated from the code
                            under test — if the format changes on purpose, edit it deliberately
test_fixtures_sanity.py     line counts, third-party readers, size caps
```

The notes fixture is the *output* side of the same lecture: `notes/week01.py` builds a
`NoteWeek` whose lecture 1 follows the slide → time map below, plus a second shorter
lecture so renderers face the one-page-or-several decision (plan §7.3). Regenerate with
`uv run python -m tests.fixtures.notes.week01 --write`; `notes/test_week01.py` fails
until the snapshot matches the builder.

Regenerate the decks with `uv run --group fixtures python tests/fixtures/decks/make_deck.py`.
Output is byte-for-byte reproducible (fixed metadata, reportlab `invariant`, pinned zip
timestamps), so an unintended change shows up as a git diff.

## Slide → time map

The transcript was written to this schedule. Phase 4 alignment tests assert against it.

| Segment | Time | Cues | Notes |
|---|---|---|---|
| Slide 1 — Markov Decision Processes | 0:00 – 2:30 | 1–6 | rolling-caption stretch |
| Board work (no slide) | 2:30 – 4:30 | 7–10 | the **gap signal**: dice/reroll detour, shares no distinctive vocabulary with any slide |
| Slide 2 — The Bellman Equation | 4:30 – 7:00 | 11–15 | only place "bellman" occurs; the exam callout |
| Slide 3 — Value Iteration | 7:00 – 9:05 | 16–20 | the explicit mid-sentence merge case |

Rare-term weighting (Phase 4): **"bellman"** appears in cues 11, 13, 15 only (all inside
4:30–7:00). The generic **"equation"** appears in all three slide segments (cues 5–6, 11,
13, 15, 16) and so must not, on its own, pull a segment towards slide 2.

`align/lecture01.chunks.json` is this map transcribed as the *expected output* of Phase
4: four chunks (slide 1, a `slides: null` gap, slide 2, slide 3) whose segment objects
are copied verbatim from `captions/lecture01.segments.json`. `align_lecture()` must
equal it exactly on both deck formats and both caption formats; it is never regenerated
from the code under test — if an alignment rule changes on purpose, edit the table,
then the JSON. The gap's silence brackets are the 2 s at 149→151 and the 3 s at
268→271 — the only ≥ 1 s gaps between consecutive cues.

The four chunks weigh **81 / 120 / 103 / 103 words** (whitespace-split over their
segment texts). Phase 5's density merge (`merge_chunks`, default floor 100 words)
returns them unchanged: chunks 2–4 clear the floor and the 81-word chunk 1 is fenced
by the gap, so the chunk ↔ `week01` lec01 topic correspondence above survives the
merge. This is why the P5-02 floor is 100 and not §9.1's suggested ~120 — at 120,
slides 2 and 3 would merge into one topic.

## Generate

`generate/lecture01.responses.json` is the recorded-response fixture for the Phase 5
fake (`RecordedClient`): a JSON object keyed by request key (`chunk:` + topic id —
`chunk:lec01:s1-1`, `chunk:lec01:t151`, `chunk:lec01:s2-2`, `chunk:lec01:s3-3`), each
value the JSON text of a `ChunkNotes`. It was hand-transcribed from
`notes/week01.py`'s lec01 topics so that the fake pipeline — `ingest → align →
generate(RecordedClient)` — reproduces the week01 lec01 topics that Phase 3 renders;
it is never regenerated from the code under test. Two deliberate differences on
`chunk:lec01:s3-3`: its `Figure.asset_id` is the PPTX deck's slide-3 image id
`img-a63ae9b7dc5e9397` (not week01's semantic `fig-value-iteration-convergence` —
P5-03 mints the asset), and `image_alts` maps that id to week01's `MediaAsset.alt`
text. The fixture is therefore **PPTX-bound**: the PDF deck's re-encoded figure has a
different id by design (P2-03), so the fake pipeline runs on PPTX+VTT and
cross-format behaviour is pinned in the `chunk_prompt` tests instead.

P5-03 adds the `synthesis:lec01` entry: the JSON text of a `LectureSynthesis` carrying
week01 lec01's `title`, `overview`, `objectives`, `glossary` and `open_questions`
verbatim, so the lecture-level pass reproduces the same front matter the chunk
responses reproduce topic by topic.

`generate/lecture01.notes.json` is the *expected output* of Phase 5's entrypoint: the
`NoteLecture` that `generate_lecture()` on PPTX+VTT with the recorded fake must equal,
in exactly 5 requests (4 chunks + 1 synthesis). It is `notes/week01.py`'s lec01 with
exactly three deliberate differences, each forced by generation-truth, and is never
regenerated from the code under test:

1. `source` is `deck_path: tests/fixtures/decks/lecture01.pptx`,
   `caption_path: tests/fixtures/captions/lecture01.vtt` — the files the fake pipeline
   actually consumes; no video URL.
2. the value-iteration topic's `Figure.asset_id` is `img-a63ae9b7dc5e9397` (the
   PPTX image id the responses fixture cites, not week01's semantic id).
3. `assets` is the one minted `MediaAsset`: id `img-a63ae9b7dc5e9397`, `image/png`,
   `source: media/img-a63ae9b7dc5e9397.png` (POSIX, relative to the week document's
   directory), with week01's alt text.

## Captions

| Cue | Time | Segments | Exercises | Intended outcome after Phase 1 dedupe / merge |
|---|---|---|---|---|
| — | before cue 1 | — | `WEBVTT` header, one `NOTE` block | Both skipped; neither is a segment. |
| 1 | 0:01–0:26 | 1, 2 | `<v Lecturer>` voice tag; first cue of the **rolling stretch** (1–6): each cue's first line repeats the previous cue's last line | Voice tag stripped. Cues 1–6 collapse to seven unique lines (A…G) with no repeated text. |
| 2 | 0:26–0:50 | 2 | rolling repeat of cue 1 line 2; sentence continues across the cue boundary | Repeated line dropped; "…rewards, / and a transition function…" merged into one sentence. |
| 3 | 0:50–1:15 | 3 | rolling repeat | Repeated line dropped. |
| 4 | 1:15–1:40 | 3 | rolling repeat; sentence spans 4→5 | Repeated line dropped; merged with cue 5's new line. |
| 5 | 1:40–2:05 | 4 | rolling repeat; new line ends mid-sentence ("…the famous equation coming up"); first "equation" (slide-1 window) | Merged with cue 6's new line into one sentence. |
| 6 | 2:05–2:29 | 4 | last rolling cue; completes the sentence with a full stop | End of slide-1 segment; the rolling stretch yields exactly 7 lines. |
| 7 | 2:31–3:00 | 5, 6 | start of the **board-work gap** (7–10); two sentences in one cue | Two segments (split at ". suppose"). No slide vocabulary anywhere in 7–10. |
| 8 | 3:00–3:30 | 7, 8 | gap; a question mark as a sentence terminator | Split at "? on average". |
| 9 | 3:30–4:00 | 9, 10 | gap | Two segments. |
| 10 | 4:00–4:28 | 11, 12 | gap; last cue before the return to slides | Two segments; a ~3 s silence before cue 11. |
| 11 | 4:31–5:00 | 13, 14 | **inline timing tags** `<00:04:32.000><c>back</c><00:04:32.400><c>to</c>…` with **no whitespace between them**, so a naive strip glues `backtotheslides`; first "bellman" | Timing tags become a space, `<c>`/`</c>` become nothing, whitespace is collapsed: "back to the slides. this is the bellman equation, …". |
| 12 | 5:00–5:30 | 15 | `<i>expected</i>` styling tag (also kept in the SRT) | Tag stripped, word kept. |
| 13 | 5:30–6:00 | 16 | inline timing tags; "bellman" | Tags stripped. |
| 14 | 6:00–6:30 | 17 | inline timing tags; the exact phrase **"this will be on the exam"** (once in the file) | Tags stripped; Phase 5 must emit `Callout(kind=EXAM)` anchored here (≈6:00–6:30, slide 2). |
| 15 | 6:30–6:59 | 18 | "bellman" twice in one cue (name and equation); last slide-2 cue | One long sentence, one segment. |
| 16 | 7:01–7:25 | 19 | slide-3 start; "equation" in the slide-3 window | One segment. |
| 17 | 7:25–7:50 | 20 | **multi-line cue** that is *not* a rolling repeat; the line break falls mid-sentence | Lines joined with a space into one sentence. |
| 18 | 7:50–8:15 | 21 | **ends mid-sentence** with no terminal punctuation ("…tolerance epsilon") | Held open and merged with cue 19. |
| 19 | 8:15–8:40 | 21 | completes cue 18's sentence with a full stop | Merged segment spans 7:50–8:40. |
| 20 | 8:40–9:05 | 22 | closing cue; apostrophe ("that's"); total duration 9:05 | One segment; end of lecture. |
| — | inline strings | — | **tag whitespace**: YouTube writes `<c.colorE5E5E5> word</c>` with the space *inside* the tag, while cue 11 has none between tags; also `&amp;`, `<i>` mid-word, runs of spaces/tabs | `strip_tags` gives single-spaced words either way ("word"; "a & b"); idempotent; the identity on clean text. |

`captions/lecture01.segments.json` is the *expected output* of Phase 1 for both
files: `ingest_captions()` (parse → dedupe → merge) must equal it exactly. It was
transcribed by hand from the *Segments* column above and is never regenerated from the
code under test; if the merge rule changes on purpose, edit the table, then the JSON.
A segment's span is the union of the cues that contributed to it, so two sentences
from one cue share a span and spans may overlap (P1-03 decision).

The SRT twin has identical cue text and timings (comma milliseconds, numbered), no
`NOTE`, no timing/`<c>`/`<v>` tags, and keeps the single `<i>` tag. Parsing both must
yield the same 20 cues after tag stripping.

## Decks

| Slide | Title | Exercises | Intended extraction |
|---|---|---|---|
| 1 | Markov Decision Processes | Single column, five bullets; PPTX speaker notes | Title, then the five bullets in order. |
| 2 | The Bellman Equation | **Two columns.** In the PDF, both columns are drawn row by row at the *same y-coordinates*, so naive top-to-bottom extraction (e.g. `pypdf` `extract_text()`) interleaves them: `Equation / Intuition / V(s) = … / Value = … / …`. In the PPTX the columns are the two body placeholders of the *Two Content* layout. Speaker notes. | **Left column fully** (`Equation`, the equation line, four term rows), **then the right column** (`Intuition` + five bullets). The PDF needs x-clustering (P2-02: single-linkage on x-starts with a 0.15 × page-width gap threshold, so indents chain into their column and the 390-pt gap splits); the PPTX gives the right order from placeholder order. |
| 3 | Value Iteration | Single column (four numbered steps; step 2 wraps onto two lines in the PDF) plus an **image** (`value_iteration.png`, 240×150 palette PNG) on the right; the PPTX body placeholder is narrowed to make room. Speaker notes. | Title, the steps in order, and one `MediaAsset` (`image/png`) for the figure; the figure contains no extractable text. The PPTX picture is the committed PNG byte-for-byte (`img-a63ae9b7dc5e9397`); the PDF figure comes back from pypdf re-encoded (RGB, ~1.2 KB) with a different id, 240 × 150 either way (P2-03). |
| — | footer | `Lecture 1 - slide N / 3` at the bottom right of every PDF page, 10 pt | Dropped as boilerplate: a digit-normalised line (`Lecture # - slide # / #`) that occurs on more than half the pages of a deck with at least two pages. A one-page deck keeps it. |

Speaker notes (PPTX only) are 2–3 sentences per slide and are Phase 2 test data; slide
2's notes contain "this will be on the exam" as well, so a notes-aware Phase 5 has a
second, slide-side source for the same callout.

`decks/lecture01.deck.json` is the *expected output* of Phase 2 for the PPTX:
`ingest_slides()` must equal it exactly, and the PDF must yield the same titles and blocks
(P2-02) and, up to `notes: null` and the re-encoded figure's bytes, the same deck (P2-03).
Decorative images (under 32 px on either side) and a picture recurring on more than half
of ≥ 3 slides never reach `image_ids`; the fixture has neither, so those rules are tested
on ad-hoc decks in `tests/ingest/test_images.py`. It was transcribed by hand from the constants in `make_deck.py` and the decks
table above and is never regenerated from the code under test; if an extraction rule
changes on purpose, edit the table, then the JSON. Image ids are content hashes
(`img-` + 16 hex of sha256) and image bytes are stored as base64 (P2-01 decision).

Slide text is ASCII only (`gamma`, `sum_s'`, `in`) because reportlab's built-in fonts are
Latin-1; the identical strings appear in the PDF and PPTX so cross-format tests can
compare directly.
