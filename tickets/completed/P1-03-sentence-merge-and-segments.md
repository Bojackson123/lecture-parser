# P1-03 — Sentence-boundary merge, `ingest_captions()`, expected-segments snapshot
Phase 1 · Depends on: P1-02 · Size: M

## Goal

Finish plan §3 stage 1. Add `merge_sentences(cues) -> list[Segment]`, which joins
deduped cues into sentence-bounded segments, and `ingest_captions(path) -> list[Segment]`,
which composes parse → dedupe → merge by file suffix. The Phase 1 done-criterion
(plan §6) becomes one snapshot test: `ingest_captions()` on the VTT fixture equals a
committed, **hand-written** `tests/fixtures/captions/lecture01.segments.json` — the
"expected output" P0-03 deferred to this phase — and equals the same call on the SRT.

## Scope

**In**
- `merge_sentences`, `ingest_captions` in `lecturenotes/ingest/captions.py`.
- `tests/fixtures/captions/lecture01.segments.json` (22 segments, written by hand first).
- `tests/ingest/test_merge.py`, `tests/ingest/test_merge_properties.py`, `tests/ingest/test_ingest_captions.py`.
- `tests/fixtures/README.md`: pointer to the segments file and a segment-number column.

**Out**
- CLI → P1-04.
- Abbreviation-aware sentence splitting (`e.g.`, `3.5`, `Dr.`) — known limitation, see Decisions.
- Chunking segments into topics — that is alignment (Phase 4) and generation (Phase 5).
  Segments are sentences with timestamps, nothing more.

## Tasks

1. **Hand-write `tests/fixtures/captions/lecture01.segments.json` first**, as a JSON
   list of `{"start_s": …, "end_s": …, "text": …}` objects, derived from the README
   captions table and the dedupe result of P1-02. Expected 22 segments (spans in seconds):

   | # | start–end | Text (from cue) | Why |
   |---|---|---|---|
   | 1 | 1–26 | `welcome back everyone, … decision making.` (1) | first sentence of cue 1 |
   | 2 | 1–50 | `a markov decision process … each action.` (1+2) | sentence spans cues 1→2 |
   | 3 | 50–100 | `the reward is a number … later rewards.` (3+4) | spans 3→4 |
   | 4 | 100–149 | `keep this picture … written down recursively.` (5+6) | the rolling stretch ends |
   | 5 | 151–180 | `let me step away … grab the chalk.` (7) | split at `. suppose` |
   | 6 | 151–180 | `suppose you roll … in dollars.` (7) | same cue, same span |
   | 7 | 180–210 | `how much would you pay to play that game?` (8) | `?` terminator |
   | 8 | 180–210 | `on average you win … a bargain.` (8) | |
   | 9 | 210–240 | `now suppose i let you reroll … first roll.` (9) | |
   | 10 | 210–240 | `the trick is … already known.` (9) | |
   | 11 | 240–268 | `you keep the first roll … a five or a six.` (10) | |
   | 12 | 240–268 | `work it out at home, … four and a quarter.` (10) | |
   | 13 | 271–300 | `back to the slides.` (11) | timing tags stripped |
   | 14 | 271–300 | `this is the bellman equation, … whole course.` (11) | |
   | 15 | 300–330 | `the value of a state … the expected value … land next.` (12) | `<i>` stripped |
   | 16 | 330–360 | `the bellman equation is recursive: … right hand side.` (13) | |
   | 17 | 360–390 | `write it down properly … this will be on the exam.` (14) | the EXAM phrase |
   | 18 | 390–419 | `richard bellman called this … follows.` (15) | one long sentence |
   | 19 | 421–445 | `value iteration turns … all the states.` (16) | |
   | 20 | 445–470 | `each sweep applies … maximum change between sweeps … every time.` (17) | two lines joined with one space |
   | 21 | 470–520 | `the plot on the slide … tolerance epsilon you stop … in every state.` (18+19) | mid-sentence cue held open |
   | 22 | 520–545 | `that's it for today, … from samples.` (20) | EOF |

   Use the exact fixture strings; timestamps as floats (`1.0`, not `1`). Two-space
   indent, LF line endings, trailing newline, so `git diff` stays readable.
2. **`tests/ingest/test_ingest_captions.py`** — the done-gate:
   - `ingest_captions(fixtures_dir / "captions/lecture01.vtt")` equals
     `[Segment.model_validate(d) for d in json.loads(segments_json)]`. On failure the
     assertion message says: *the segments fixture is hand-written; if the merge rule
     changed on purpose, edit the JSON deliberately — do not regenerate it from the code
     under test.*
   - The SRT path gives an identical list.
   - `len(...) == 22`.
   - A `.txt` path raises `ValueError` naming the unsupported suffix; a missing file
     raises `FileNotFoundError` (let `Path.read_text` do it).
3. **`tests/ingest/test_merge.py`** — README rows as test names, run on the deduped fixture cues:
   - Cue 7 splits at `. suppose` into two segments with the same span `151–180`.
   - Cue 8 splits at `? on`.
   - Cues 18 + 19 merge into one segment spanning `470.0–520.0`.
   - Cue 17's two lines are joined with exactly one space (`maximum change between sweeps`).
   - Cues 1 + 2 merge across the rolling boundary into segment 2 with span `1.0–50.0`.
   - No segment text contains a newline, `<`, `>`, two consecutive spaces, or
     leading/trailing whitespace.
   - Exactly one segment contains `this will be on the exam`, and its span lies within `360–390`.
   - Exactly three segments contain `bellman` and all lie within `270–420`.
   - Ad-hoc inline cases:
     - **Unpunctuated captions** (six 10 s cues with no terminators) are cut when the
       open buffer would exceed `max_segment_s` (call with `max_segment_s=30.0` and
       assert 2 segments of 30 s each).
     - **Silence gap**: a cue ending mid-sentence followed by a cue starting 8 s later is
       flushed before the second cue (`max_gap_s=5.0` default) → two segments.
     - A gap under `max_gap_s` with no terminator still merges.
     - **EOF flush**: a final cue with no terminal punctuation still becomes a segment.
     - `...` and `?!` count as one terminator; a terminator not followed by whitespace
       or end-of-text (`3.5`, `e.g.`) does **not** split (documents the v1 limitation:
       `e.g. this` *does* split, and the test says so in its name).
     - Empty cue list → empty segment list.
4. **Implement `merge_sentences(cues, *, max_gap_s: float = 5.0, max_segment_s: float = 60.0)`**:
   - Maintain an open buffer `(text, start_s)`; `last_end_s` of the most recent cue.
   - For each cue: if the buffer is non-empty and `cue.start_s - last_end_s > max_gap_s`,
     flush the buffer as a segment ending at `last_end_s`. Then, if the buffer is
     non-empty and `cue.end_s - buffer.start_s > max_segment_s`, flush it the same way.
     Append `" ".join(cue.lines)` to the buffer (space-joined; buffer `start_s` =
     `cue.start_s` if the buffer was empty).
   - Split the buffer with the terminator regex `[.?!]+["')\]]*(?=\s|$)`. Each complete
     sentence becomes `Segment(start_s=buffer.start_s, end_s=cue.end_s, text=sentence.strip())`.
     The remainder (if any) becomes the new buffer with `start_s = cue.start_s`.
   - After the last cue, flush any remainder with `end_s = last_end_s`.
   - Skip any sentence that is empty after stripping.
5. **Implement `ingest_captions(path: Path) -> list[Segment]`**: read as `utf-8-sig`,
   dispatch on `path.suffix.lower()` (`.vtt` → `parse_vtt`, `.srt` → `parse_srt`,
   otherwise `ValueError(f"unsupported caption format: {suffix}")`), then
   `merge_sentences(dedupe_rolling(cues))`. Accept `**merge_kwargs` and pass them through
   so Phase 4/5 callers can tune the knobs without re-composing the pipeline.
6. **`tests/ingest/test_merge_properties.py`** (hypothesis, reuse the P1-01 cue strategy;
   text alphabet limited to letters, spaces and `.?!`):
   - Concatenating all segment texts with spaces and collapsing whitespace equals the same
     over all cue lines — no words lost or invented.
   - Every segment has non-empty stripped text with no doubled spaces.
   - `start_s` is non-decreasing across segments; every `end_s >= start_s`.
   - Every segment span lies within `[cues[0].start_s, cues[-1].end_s]`.
   - `merge_sentences` with `max_segment_s=inf, max_gap_s=inf` on cues that each end in
     a terminator yields exactly one segment per sentence-in-cue, and each segment's span
     equals its cue's span.
7. `tests/fixtures/README.md`: add `captions/lecture01.segments.json` to the file
   listing, and a *Segments* column (or a sentence per row) to the captions table
   mapping cue → segment numbers, so the three artefacts cross-reference.
8. Run the full check suite and commit.

## Acceptance criteria

- `uv run pytest` → all green; the only skip is still the renderer-contract scaffold.
- `uv run ruff check .`, `uv run mypy`, `uv run lint-imports` clean.
- `uv run python -c "from pathlib import Path; from lecturenotes.ingest.captions import ingest_captions; print(len(ingest_captions(Path('tests/fixtures/captions/lecture01.vtt'))))"`
  prints `22`.
- `uv run python -c "from pathlib import Path; from lecturenotes.ingest.captions import ingest_captions as f; print(f(Path('tests/fixtures/captions/lecture01.vtt')) == f(Path('tests/fixtures/captions/lecture01.srt')))"`
  prints `True`.
- `grep -c '"start_s"' tests/fixtures/captions/lecture01.segments.json` prints `22`.
- `grep -c "this will be on the exam" tests/fixtures/captions/lecture01.segments.json` prints `1`.
- `git status` clean after commit; the segments JSON was committed **before** the
  implementation commit (or in the same commit with the tests) — the log should show
  tests-first.

## Decisions & notes

- **A segment's span is the union of the cues that contributed to it.** Two sentences
  from one cue therefore share a span, and spans may overlap. The alternative —
  interpolating sub-cue timestamps by character count — invents precision the source
  does not have, and `SourceAnchor` (plan §2.2) is the trust feature; a citation must
  point where the words really are. **Phase 4 must sort by `start_s` and must not
  assume segments partition time.** Record this in `CLAUDE.md` at P1-04.
- **`max_segment_s` (default 60 s)** exists because real YouTube auto-captions are
  frequently unpunctuated end to end; without a cap the whole lecture becomes one
  segment and chunking (plan §4.2) has nothing to work with. 60 s is above the longest
  merged span in the fixture (50 s) and roughly "a slide's worth" of speech.
- **`max_gap_s` (default 5 s)** because a cue that ends mid-sentence followed by a
  silence is a topic break (the lecturer paused, or the captions have a hole), not a
  continuing sentence. The fixture's 2–3 s gaps all follow terminators, so the default
  is inert on committed data; the ad-hoc test covers it.
- **Knobs are keyword-only with defaults**, and `ingest_captions` forwards them, so
  callers in Phases 4/5 read as `ingest_captions(path, max_segment_s=45)` and nothing
  else has to know the pipeline's internals.
- **Sentence terminators are `.`, `?`, `!` followed by whitespace or end of text.**
  Abbreviations and decimals inside a sentence do not split (no whitespace follows the
  dot), but `e.g. this` will. Accepted for v1: the lecture register rarely contains
  them and the cost of a false split is one extra segment, not lost text. Fix with a
  real file in hand and add that case to the fixture first (P0-03 rule).
- **The expected JSON is hand-written and never regenerated from the code under test.**
  If it were generated, the snapshot would only prove the code agrees with itself. The
  README table is the source of truth; the JSON transcribes it.
- **`ingest_captions` takes a `Path`, not text**, because the format is chosen by
  suffix; the text-level functions stay available for callers that already have a string.
- **A buffer that gains no sentence keeps its start.** The task text says the
  remainder after splitting takes `start_s = cue.start_s`; read literally, that would
  move the start of an unpunctuated buffer forward on every cue and the 60 s cap would
  never trigger (`cue.end_s - buffer.start_s` would only ever measure one cue). The
  implementation resets the buffer's start to the current cue only when at least one
  sentence was completed in it — then the remainder really did begin in that cue.
  `test_unpunctuated_captions_are_cut_when_the_buffer_would_exceed_max_segment_s` and
  `test_sentence_completed_in_a_later_cue_starts_where_the_buffer_started` pin both
  halves of the rule.
- **Suffix dispatch is case-insensitive** (`LECTURE01.VTT` works) and reads
  `utf-8-sig`, so a BOM from a Windows exporter is invisible; both are tested.
- Closed 2026-08-31 in two commits: the hand-written JSON, README cross-references and
  all three test modules first (red, `ImportError` on `merge_sentences`), then the
  implementation. `uv run pytest` → 186 passed, 1 skipped (the renderer-contract
  scaffold); ruff, mypy and lint-imports clean. All four acceptance one-liners print
  the expected values. `ruff format --check` flags `tests/fixtures/notes/test_week01.py`
  and one other pre-existing file — unchanged by this ticket and not part of the
  project's check list.
