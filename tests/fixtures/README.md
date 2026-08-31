# Test fixtures

One mock lecture — *Lecture 1: MDPs and the Bellman Equation* — as captions and as a
slide deck, designed so that every later phase has its hard cases on committed data
(plan §8). Each row below is a future test's name: if a phase needs a case that isn't
here, add it *here* and update these tables rather than inventing a second fixture.

```
captions/lecture01.vtt      20 cues, hand-written (the canonical caption fixture)
captions/lecture01.srt      the same 20 cues as SRT
decks/make_deck.py          generator for the three files below (uv run --group fixtures)
decks/lecture01.pdf         3 landscape pages, slide 2 two-column
decks/lecture01.pptx        3 slides, speaker notes on every slide, PNG on slide 3
decks/value_iteration.png   the figure embedded in both decks (1.4 KB)
test_fixtures_sanity.py     line counts, third-party readers, size caps
```

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

## Captions

| Cue | Time | Exercises | Intended outcome after Phase 1 dedupe / merge |
|---|---|---|---|
| — | before cue 1 | `WEBVTT` header, one `NOTE` block | Both skipped; neither is a segment. |
| 1 | 0:01–0:26 | `<v Lecturer>` voice tag; first cue of the **rolling stretch** (1–6): each cue's first line repeats the previous cue's last line | Voice tag stripped. Cues 1–6 collapse to seven unique lines (A…G) with no repeated text. |
| 2 | 0:26–0:50 | rolling repeat of cue 1 line 2; sentence continues across the cue boundary | Repeated line dropped; "…rewards, / and a transition function…" merged into one sentence. |
| 3 | 0:50–1:15 | rolling repeat | Repeated line dropped. |
| 4 | 1:15–1:40 | rolling repeat; sentence spans 4→5 | Repeated line dropped; merged with cue 5's new line. |
| 5 | 1:40–2:05 | rolling repeat; new line ends mid-sentence ("…the famous equation coming up"); first "equation" (slide-1 window) | Merged with cue 6's new line into one sentence. |
| 6 | 2:05–2:29 | last rolling cue; completes the sentence with a full stop | End of slide-1 segment; the rolling stretch yields exactly 7 lines. |
| 7 | 2:31–3:00 | start of the **board-work gap** (7–10); two sentences in one cue | Two segments (split at ". suppose"). No slide vocabulary anywhere in 7–10. |
| 8 | 3:00–3:30 | gap; a question mark as a sentence terminator | Split at "? on average". |
| 9 | 3:30–4:00 | gap | Two segments. |
| 10 | 4:00–4:28 | gap; last cue before the return to slides | Two segments; a ~3 s silence before cue 11. |
| 11 | 4:31–5:00 | **inline timing tags** `<00:04:32.000><c>back</c>…`; first "bellman" | Tags stripped to plain words: "back to the slides. this is the bellman equation, …". |
| 12 | 5:00–5:30 | `<i>expected</i>` styling tag (also kept in the SRT) | Tag stripped, word kept. |
| 13 | 5:30–6:00 | inline timing tags; "bellman" | Tags stripped. |
| 14 | 6:00–6:30 | inline timing tags; the exact phrase **"this will be on the exam"** (once in the file) | Tags stripped; Phase 5 must emit `Callout(kind=EXAM)` anchored here (≈6:00–6:30, slide 2). |
| 15 | 6:30–6:59 | "bellman" twice in one cue (name and equation); last slide-2 cue | One long sentence, one segment. |
| 16 | 7:01–7:25 | slide-3 start; "equation" in the slide-3 window | One segment. |
| 17 | 7:25–7:50 | **multi-line cue** that is *not* a rolling repeat; the line break falls mid-sentence | Lines joined with a space into one sentence. |
| 18 | 7:50–8:15 | **ends mid-sentence** with no terminal punctuation ("…tolerance epsilon") | Held open and merged with cue 19. |
| 19 | 8:15–8:40 | completes cue 18's sentence with a full stop | Merged segment spans 7:50–8:40. |
| 20 | 8:40–9:05 | closing cue; apostrophe ("that's"); total duration 9:05 | One segment; end of lecture. |

The SRT twin has identical cue text and timings (comma milliseconds, numbered), no
`NOTE`, no timing/`<c>`/`<v>` tags, and keeps the single `<i>` tag. Parsing both must
yield the same 20 cues after tag stripping.

## Decks

| Slide | Title | Exercises | Intended extraction |
|---|---|---|---|
| 1 | Markov Decision Processes | Single column, five bullets; PPTX speaker notes | Title, then the five bullets in order. |
| 2 | The Bellman Equation | **Two columns.** In the PDF, both columns are drawn row by row at the *same y-coordinates*, so naive top-to-bottom extraction (e.g. `pypdf` `extract_text()`) interleaves them: `Equation / Intuition / V(s) = … / Value = … / …`. In the PPTX the columns are the two body placeholders of the *Two Content* layout. Speaker notes. | **Left column fully** (`Equation`, the equation line, four term rows), **then the right column** (`Intuition` + five bullets). The PDF needs x-clustering; the PPTX gives the right order from placeholder order. |
| 3 | Value Iteration | Single column (four numbered steps; step 2 wraps onto two lines in the PDF) plus an **image** (`value_iteration.png`, 240×150 palette PNG) on the right; the PPTX body placeholder is narrowed to make room. Speaker notes. | Title, the steps in order, and one `MediaAsset` (`image/png`) for the figure; the figure contains no extractable text. |

Speaker notes (PPTX only) are 2–3 sentences per slide and are Phase 2 test data; slide
2's notes contain "this will be on the exam" as well, so a notes-aware Phase 5 has a
second, slide-side source for the same callout.

Slide text is ASCII only (`gamma`, `sum_s'`, `in`) because reportlab's built-in fonts are
Latin-1; the identical strings appear in the PDF and PPTX so cross-format tests can
compare directly.
