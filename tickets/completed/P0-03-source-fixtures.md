# P0-03 — Source fixtures (captions + deck)
Phase 0 · Depends on: P0-01 · Size: M

## Goal

Commit one small, coherent mock lecture as test input: a 20-cue WebVTT (and SRT twin)
with the caption edge cases from plan §8 built in, and a 3-slide deck as both PDF and
PPTX with one multi-column slide. Later phases (1, 2, 4, 5) test against these files,
so they are designed to exercise those phases' hard cases, not just to exist.
Kilobytes, not megabytes (plan §8).

## Scope

**In**
- `tests/fixtures/captions/lecture01.vtt` and `lecture01.srt`.
- `tests/fixtures/decks/make_deck.py` plus its generated `lecture01.pdf` and `lecture01.pptx`.
- `tests/fixtures/README.md` documenting which cue/slide exercises which edge case.
- `tests/fixtures/test_fixtures_sanity.py`.
- A `fixtures` dependency group for the generator.

**Out**
- Expected *outputs* (deduped segment list, extracted deck JSON) — those are the
  test-first deliverables of Phases 1 and 2 (plan §10).
- The hand-written `NoteWeek` fixture → P0-04.
- Any parser code. Sanity tests use only line counting and third-party readers.
- `.mp4` fixture → Phase 9.

## Tasks

1. **Pick the lecture content.** A short reinforcement-learning lecture, mirroring the
   plan's own "Bellman Equation" example:
   - Slide 1 — *Markov Decision Processes*: states, actions, rewards, transition function.
   - Slide 2 — *The Bellman Equation*: two columns — left: the equation and its terms;
     right: an intuition bullet list.
   - Slide 3 — *Value Iteration*: algorithm steps + a small figure (PNG).
   The transcript walks the slides in order with one off-slide detour (see 2).
2. **`tests/fixtures/captions/lecture01.vtt`** — exactly **20 cues**, hand-written. Must contain:
   - `WEBVTT` header line and one `NOTE` block before the first cue.
   - **Rolling-caption repetition** (YouTube auto-caption style) across at least 6
     consecutive cues: each cue's first line repeats the previous cue's last line.
   - **Inline timing tags** `<00:00:12.500><c>word</c>` in at least 3 cues.
   - One `<v Lecturer>` voice tag; one `<i>`/`<b>` styling tag.
   - One cue with two text lines (multi-line cue).
   - Sentences that span cue boundaries, and at least one cue that ends mid-sentence
     followed by one that ends with a full stop — Phase 1's "merge on sentence boundary" case.
   - The exact phrase **"this will be on the exam"** once (Phase 5 `Callout(EXAM)` test).
   - A stretch of roughly two minutes (≈4 cues) of board-work speech that shares no
     distinctive vocabulary with any slide — Phase 4's **gap signal**.
   - The rare term **"bellman"** appearing only during the slide-2 portion; the generic
     term "equation" appearing during slides 1, 2 and 3 — Phase 4's rare-term weighting.
   - Cue timestamps monotonic, total duration ~8–10 minutes.
3. **`tests/fixtures/captions/lecture01.srt`** — the same 20 cues in SRT form
   (numbered, comma-millisecond timestamps, no `NOTE`, no `<c>` tags — SRT has no
   timing tags; keep the `<i>` tag since SRT tolerates it).
4. **`tests/fixtures/decks/make_deck.py`** — a standalone script (no `lecturenotes`
   imports) that writes both deck files next to itself:
   - PDF via `reportlab`: 3 pages, landscape. Page 2 draws two text columns with
     rows at the *same y-coordinates* so naive top-to-bottom extraction interleaves
     them; page 1 and 3 single column. Slide numbers in the footer.
   - PPTX via `python-pptx`: same 3 slides using the title+content layout; **speaker
     notes on every slide** (2–3 sentences each — these become Phase 2 test data);
     slide 3 includes a small generated PNG (draw it in-script with `Pillow` or emit
     a hand-built minimal PNG; ≤ 2 KB).
   - Deterministic: fixed metadata (author/date) so regenerating yields a stable diff
     where the libraries allow it. Print the output paths.
5. `pyproject.toml`: add `[dependency-groups] fixtures = ["reportlab", "python-pptx", "pypdf", "Pillow"]`.
   Run `uv run --group fixtures python tests/fixtures/decks/make_deck.py` and commit
   the generated files.
6. **`tests/fixtures/README.md`** — two tables:
   - *Captions*: cue number → what it exercises (rolling repeat, timing tag, voice tag,
     multi-line, exam phrase, gap stretch, "bellman") → intended outcome after Phase 1
     dedupe/merge, in prose.
   - *Decks*: slide number → title → what it exercises (multi-column, notes, image) →
     intended extraction order for slide 2 (left column fully, then right column).
   Include the slide→time mapping the transcript was written to
   (e.g. slide 1: 0:00–2:30, board work 2:30–4:30, slide 2: 4:30–7:00, slide 3: 7:00–end)
   — Phase 4's alignment tests will assert against it.
7. **`tests/fixtures/test_fixtures_sanity.py`**:
   - VTT starts with `WEBVTT`; counting lines matching `-->` gives exactly 20.
   - SRT cue count is 20 and equals the VTT count.
   - PDF has 3 pages (`pypdf.PdfReader`).
   - PPTX opens (`pptx.Presentation`), has 3 slides, and every slide has non-empty notes text.
   - Every file under `tests/fixtures/` is < 100 KB.
   Mark the PDF/PPTX tests to skip if `pypdf`/`python-pptx` are not importable, so the
   core `dev` group alone still runs green.

## Acceptance criteria

- `uv run --group fixtures python tests/fixtures/decks/make_deck.py` regenerates
  `lecture01.pdf` and `lecture01.pptx` without error.
- `uv sync --all-groups && uv run pytest tests/fixtures` → all green, nothing skipped.
- `grep -c -- "-->" tests/fixtures/captions/lecture01.vtt` prints `20`.
- `grep -c "bellman" tests/fixtures/captions/lecture01.vtt` ≥ 1 and all occurrences
  fall inside the slide-2 time window recorded in `README.md`.
- `grep -c "this will be on the exam" tests/fixtures/captions/lecture01.vtt` prints `1`.
- `du -sh tests/fixtures` is well under 1 MB.
- `tests/fixtures/README.md` tables are filled in for every cue and slide.
- All fixture files committed; `git status` clean.

## Decisions & notes

- **Hand-write the VTT; generate the decks.** Caption edge cases need human control
  over every cue; PDF/PPTX are binary and only reproducible via a script.
- **Generator is committed and pinned in a separate `fixtures` group** so the core
  `dev` group stays minimal and the generated files can be rebuilt after a deliberate
  content change.
- **One mock lecture across all fixture types** (rather than unrelated samples) is
  what lets Phase 4 test alignment on committed data instead of real course material.
- Fixture design is the point of this ticket: each edge case in the README table is a
  future test's name. If a later phase needs a case that isn't here, add it *here* and
  update the README, rather than inventing a second fixture.
- **PPTX slide 2 uses the *Two Content* layout**, not title+content with a second text
  box: it is how a real two-column slide is authored, and it gives Phase 2 a
  placeholder-ordered case (left then right) to contrast with the PDF's interleaving.
- **`value_iteration.png` is committed alongside the decks** (1.4 KB) so Phase 2 can
  compare the extracted image against its source bytes; both decks embed the same PNG.
- **Board work is a dice/reroll detour**, thematically backward induction but lexically
  disjoint from the slides (no state/action/reward/value/equation/gamma), so the gap
  signal is unambiguous.
- Regeneration is byte-identical (reportlab `invariant=1`, fixed core properties, PPTX
  zip entries rewritten with a pinned timestamp). To verify the dev-only skip path use
  `uv run --exact --no-group fixtures pytest tests/fixtures`; plain `uv run` syncs
  inexactly and leaves the fixture packages installed.
