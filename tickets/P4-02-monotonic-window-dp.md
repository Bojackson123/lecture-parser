# P4-02 — Span units and the monotonic window DP
Phase 4 · Depends on: P4-01 · Size: L

## Goal

Create `lecturenotes/align/boundaries.py` (plan §5) with the constraint half of plan
§4.1: "solve for *monotonic* boundaries rather than matching each slide independently;
slides advance in order, and using that constraint fixes the slides whose text is too
generic to place on their own." Two pure functions: `span_units`, which groups segments
that share speech time (a P1-03 consequence — two sentences from one cue have the same
span, and a boundary between them would lie about where the words are), and
`solve_windows`, a dynamic program that partitions the unit sequence into one
contiguous, possibly-empty window per slide, maximising the P4-01 score of each slide
against its window's *distinct* vocabulary. On the fixture this must put the window
boundaries exactly at segments 13 and 19 — leaving segment 4's lone generic "equation"
on slide 1 and the closing recap's slide-1 vocabulary on slide 3.

## Scope

**In**
- `span_units` and `solve_windows` in `lecturenotes/align/boundaries.py`.
- `tests/align/test_boundaries.py`, `tests/align/test_boundaries_properties.py`,
  strategies in `tests/align/strategies.py`.

**Out**
- Gap carving, `Chunk`, `align_lecture`, hidden-slide handling → P4-03 (this ticket's
  functions are slide-number-agnostic: they see term sets, not `Slide`s).
- Scene detection (§4.1 approach 3) → Phase 9.
- Slide grouping / chunk merging — §9 density decision, Phase 5.

## Tasks

1. **Tests first** (red on `ImportError`).
   - `tests/align/test_boundaries.py`, fixture half (segments via `ingest_captions` on
     the VTT, slides via `ingest_slides` on the PPTX, weights and term sets via P4-01):
     - `span_units` on the 22 fixture segments yields **16 units**: 0-based segment
       index groups `(0, 1)` (the rolling overlap — segment 1 spans 1–26 inside
       segment 2's 1–50), `(4, 5)`, `(6, 7)`, `(8, 9)`, `(10, 11)`, `(12, 13)` (the
       five two-sentence cues), all other segments singletons.
     - Touching is not overlapping: segments 2 and 3 meet at 50.0 exactly and are
       *separate* units.
     - `solve_windows` on the fixture (3 slides × 16 units) assigns units to windows
       `[7, 5, 4]` — windows open at segments 1, 13 and 19, exactly the fixtures
       README's slide → time map.
     - `test_generic_equation_does_not_advance_segment_4`: the unit for segment 4 is
       in window 0. Segment 4 shares "equation" with slide 2 (P4-01 pinned that), but
       window 2's vocabulary already contains "equation" from the bellman cues, so
       under distinct-union scoring moving it gains nothing and the tie-break keeps it
       — the fixtures README's "must not, on its own, pull a segment towards slide 2".
     - `test_window_2_opens_on_the_bellman_cue`: the unit `(12, 13)` — "back to the
       slides." plus the first "bellman" sentence, one cue — is in window 1, entire:
       the span rule drags the vocabulary-free "back to the slides." along with its
       cue-mate.
     - `test_monotonicity_keeps_the_closing_recap_on_slide_3`: segment 22 shares
       `{"transition", "function"}` with slide 1 and nothing with slide 3 (P4-01
       pinned that), yet its unit sits in window 2 — matched independently it would
       jump back to slide 1; the monotonic constraint is what §4.1 says it is.
     - `test_board_work_stays_in_window_1`: the four board-work units (segments 5–12)
       are all in window 0 — all-zero scores everywhere, settled by the
       advance-as-late-as-possible tie-break, so window 1 runs to segment 12. (Their
       *gap* status is P4-03's job; here they merely must not advance the slide.)
   - `tests/align/test_boundaries_properties.py` (hypothesis), with strategies in
     `tests/align/strategies.py`:
     - `ordered_segments()`: lists of `Segment` with non-decreasing `start_s` and a
       mix of strictly-overlapping, touching and gapped neighbours (word-salad text —
       these tests never read it).
     - `span_units` properties: the groups partition `range(len(segments))` into
       consecutive runs, in order; two consecutive segments share a unit **iff**
       `next.start_s < prev.end_s`; the identity on non-overlapping inputs (every unit
       a singleton); deterministic.
     - `windows_instances()`: 1–4 slide term sets and 0–6 unit term sets over a
       5-term alphabet, **integer** weights 1–4 (exact arithmetic, so ties are real
       and the tie-break is actually exercised).
     - `solve_windows` properties against **brute force** (enumerate every boundary
       tuple with `itertools.combinations_with_replacement`, score each window by
       distinct-union, keep the optima): equal total score, and *equal boundary
       tuple* — the lexicographically largest optimum, exactly.
     - Shape properties: result length equals the unit count; values non-decreasing,
       all in `range(len(slides))`; deterministic; no units → `()`; one slide →
       all zeros.
2. **`span_units(segments: Sequence[Segment]) -> tuple[tuple[int, ...], ...]`**:
   walk the segments in order; consecutive segments merge into the same unit while
   `next.start_s < prev.end_s` (strict overlap — spans are unions of cue spans, so
   cue-mates have identical spans and rolling-merge products overlap; segments that
   merely touch at a boundary are separate). Returns 0-based index groups, consecutive
   and exhaustive. Raise `ValueError` if `start_s` values ever decrease — the caller's
   job is to pass segments in transcript order, and `ingest_captions` already does.
3. **`solve_windows(slides: Sequence[frozenset[str]], units: Sequence[frozenset[str]],
   weights: Mapping[str, float]) -> tuple[int, ...]`**: choose cut positions
   `0 = b_0 ≤ b_1 ≤ … ≤ b_S = U` (window `j` gets `units[b_j : b_j+1]`) maximising

   `total = Σ_j score(slides[j], union of window j's term sets, weights)`

   with P4-01's `score` (distinct shared terms — a term counts once per window no
   matter how many units repeat it). Among optima return the assignment with the
   **lexicographically largest** `(b_1, …, b_{S-1})`: every window opens as late as
   the optimum allows (equivalently: the pointwise-smallest per-unit assignment).
   Return the per-unit window indices. `ValueError` when there are units but no
   slides — the no-deck case is `align_lecture`'s branch (P4-03), not a silent guess
   here. Implementation is free (right-to-left DP over `(unit, slide)` with running
   union sets is O(S·U²) in set operations and plenty for a 3-hour week); the
   brute-force property is the specification.
4. Run the full check suite; commit tests first, then the implementation.

## Acceptance criteria

- `uv run pytest` → all green, hypothesis included; `uv run ruff check .`,
  `uv run mypy`, `uv run lint-imports` clean.
- `uv run python -c "from pathlib import Path; from lecturenotes.ingest.captions import ingest_captions; from lecturenotes.align.boundaries import span_units; print(len(span_units(ingest_captions(Path('tests/fixtures/captions/lecture01.vtt')))))"`
  prints `16`.
- `uv run python -c "from pathlib import Path; from collections import Counter; from lecturenotes.ingest.captions import ingest_captions; from lecturenotes.ingest.slides import ingest_slides; from lecturenotes.align.scoring import slide_terms, term_weights, tokenize; from lecturenotes.align.boundaries import span_units, solve_windows; segs = ingest_captions(Path('tests/fixtures/captions/lecture01.vtt')); deck = ingest_slides(Path('tests/fixtures/decks/lecture01.pptx')); units = span_units(segs); terms = [frozenset().union(*(tokenize(segs[i].text) for i in u)) for u in units]; a = solve_windows([slide_terms(s) for s in deck.slides], terms, term_weights(segs)); print([Counter(a)[j] for j in range(3)])"`
  prints `[7, 5, 4]`.
- `git log` shows the tests committed before (or together with, never after) the
  implementation; `git status` clean.

## Decisions & notes

- **Units before windows, and never split afterwards.** The P1-03 span rule (a
  segment's span is the union of its cues' spans) means overlapping spans identify
  speech from the same moment; a chunk boundary between them would produce an anchor
  pointing at words that belong to the other side. This is also what places the
  vocabulary-free "back to the slides." — its cue-mate has "bellman", and the unit
  moves as one. Rolling-merge overlaps glue too, which is correct for the same reason:
  the words genuinely share time.
- **Distinct-union window scoring is load-bearing, not a nicety.** Summing per-unit
  scores would pay `w("equation")` again for segment 4 and pull it into slide 2's
  window — the exact failure the fixtures README forbids. Counting each shared term
  once per window makes a lone generic word worthless next to a window that already
  has it, while a *new* rare word ("course", df 1, from the bellman cue) still moves
  boundaries. This is why P4-01's `tokenize` returns sets.
- **Ties go to "advance as late as possible."** All-zero stretches (board work) must
  land somewhere deterministic; keeping them with the current slide matches how
  lectures work (a detour belongs to the slide on screen) and gives P4-03 maximal
  runs to carve gaps from. Lexicographically largest boundary tuple is that rule made
  precise enough to brute-force against.
- **Windows may be empty** — a slide the lecturer skipped gets no units and, in
  P4-03, no chunk. The DP must not force coverage; the empty-window score is 0 by
  construction (empty union shares nothing).
- **Brute-force equivalence is the spec.** Monotonic-partition optimisers rot at the
  edges (empty windows, ties, single slide); with ≤ 4 slides, ≤ 6 units and integer
  weights the exhaustive optimum is cheap and exact, so the DP has nowhere to hide.
  Floats appear only in production use, where ties are measure-zero and the tie-break
  is a don't-care.
- **`solve_windows` sees term sets, not `Slide`s or numbers.** Hidden-slide handling
  (skip, never renumber — the `Slide` docstring reserves this for Phase 4) is a
  candidate-selection question and lands in `align_lecture` (P4-03), keeping the DP
  testable on synthetic sets.
- **O(S·U²) is fine; do not pre-optimise.** A week is ~400 segments and ~100 slides;
  set unions dominate and stay small. If a real course is slow, profile then — the
  brute-force property makes refactoring safe.
