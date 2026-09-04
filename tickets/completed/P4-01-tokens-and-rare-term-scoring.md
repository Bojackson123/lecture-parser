# P4-01 — `align/scoring.py`: tokens, rare-term weights, slide↔segment scoring
Phase 4 · Depends on: P3-04 · Size: M

## Goal

Create `lecturenotes/align/scoring.py` (plan §5) with the text-matching half of plan
§4.1: a tokeniser, transcript-rarity term weights, and a score between one slide's text
and one stretch of speech. This is approach (2) of §4.1 — "score slide vocabulary
against transcript segments, weighting rare terms" — as three pure functions with no
notion of order or boundaries; the monotonic solve that consumes them is P4-02. The
fixtures were written for exactly this ticket (`tests/fixtures/README.md`, "Rare-term
weighting"): "bellman" must be the term that pins slide 2, and the generic "equation"
must not, on its own, be able to pull a segment there.

## Scope

**In**
- `lecturenotes/align/scoring.py`: `STOPWORDS`, `tokenize`, `term_weights`,
  `slide_terms`, `score`.
- `tests/align/` package (`__init__.py`), `tests/align/test_scoring.py`,
  `tests/align/test_scoring_properties.py`.

**Out**
- Units, windows, monotonicity, the DP → P4-02. Gaps, `Chunk`, the entrypoint → P4-03.
  CLI → P4-04.
- Stemming, lemmatisation, n-grams, embeddings — see Decisions.
- Speaker notes as scoring input — excluded on purpose, see Decisions.

## Tasks

1. **Tests first** (red on `ImportError`).
   - `tests/align/test_scoring.py`, on the committed fixtures (`ingest_captions` on
     `captions/lecture01.vtt` for the 22 segments, `ingest_slides` on
     `decks/lecture01.pptx` for the 3 slides — alignment tests consume the real
     entrypoints, not hand-built stand-ins):
     - `tokenize("V(s) = max_a [ R(s, a) + gamma * sum_s' T(s, a, s') V(s') ]")` is
       exactly `{"max", "gamma", "sum"}` — alphanumeric runs, everything shorter than
       3 characters gone.
     - `tokenize("How much would YOU pay?")` is `{"pay"}` — case folded, stopwords gone.
     - `w = term_weights(segments)`: `w["bellman"] > w["equation"] > 0` (df 3 vs 4 of
       22) — the rare-term ordering the fixtures README promises.
     - A term in every segment weighs 0: `term_weights` on 22 copies of one segment
       maps every surviving token to 0.0.
     - Segment 14 ("this is the bellman equation, and it is the heart of the whole
       course.") scores slide 2 strictly above slides 1 and 3, both of which score 0.
     - Segment 4 ("keep this picture in your head …") shares exactly `{"equation"}`
       with slide 2's terms and nothing with slide 1's — the generic-term trap P4-02's
       DP must survive, pinned here at the vocabulary level.
     - **The gap has no slide vocabulary** (fixtures README, board-work row): for every
       gap segment (5–12) and every slide,
       `len(tokenize(seg.text) & slide_terms(slide)) < 2`. The one stray hit —
       "number" in segment 6 against slide 1's "a number received…" — is why the bound
       is 2, not 1; assert that pair is exactly `{"number"}` so the coincidence stays
       documented.
     - Segment 22 (the closing recap) shares `{"transition", "function"}` with slide 1
       and nothing with slide 3 — the vocabulary that P4-02's monotonicity must
       overrule, pinned here.
     - `slide_terms` reads title + block lines only: an ad-hoc
       `Slide(number=1, title=None, blocks=(), notes="the bellman equation",
       image_ids=())` has `slide_terms == frozenset()` and scores 0 against segment 14.
   - `tests/align/test_scoring_properties.py` (hypothesis; text alphabet letters,
     digits and punctuation):
     - `tokenize` output never contains a stopword, a token shorter than 3 characters,
       or an upper-case letter; `tokenize` is a pure function of its input.
     - Weights are non-negative for any segment list.
     - `score(s, t, w) == 0` whenever `s & t == frozenset()`; `score` is monotone in
       the shared set (adding a shared term never lowers it).
2. **`tokenize(text: str) -> frozenset[str]`**: lower-case, take `[a-z0-9]+` runs (so
   `max_a` → `max`/`a`, `V(s')` → `v`/`s`), drop tokens shorter than 3 characters,
   drop `STOPWORDS`. Returns a set because everything downstream (weights, distinct
   shared terms) is set-shaped; nothing in Phase 4 needs token order or counts.
3. **`STOPWORDS: frozenset[str]`**, defined once at module top: common English function
   words that survive the length-3 cut. Must contain at least `the and for you that
   this with from how much would when where what which will can all any one out get
   into over than then they them there here also just very some such not but was has
   have had are its his her she him who now`; the fixture tests are the arbiter —
   "how much would you pay" (segment 7) must share nothing with slide 1's "how much
   later rewards count".
4. **`term_weights(segments: Sequence[Segment]) -> dict[str, float]`**: document
   frequency over segments (`df(t)` = number of segments whose `tokenize` contains
   `t`), weight `ln(N / df(t))`. Rarity is measured against the *transcript* — §4.1's
   example is a slide pinned by "bellman", not "equation", and it is transcript
   ubiquity that makes "equation" generic here.
5. **`slide_terms(slide: Slide) -> frozenset[str]`**: `tokenize` of the title (if any)
   plus every block line. **Never the speaker notes** and never image data.
6. **`score(slide: frozenset[str], speech: frozenset[str], weights) -> float`**: sum of
   `weights[t]` over the *distinct* shared terms `slide & speech` (terms missing from
   `weights` count 0 — a slide-only term was never spoken and cannot be shared, but
   don't crash on a caller's synthetic sets).
7. Run the full check suite; commit tests first, then the implementation.

## Acceptance criteria

- `uv run pytest` → all green, hypothesis included; `uv run ruff check .`,
  `uv run mypy`, `uv run lint-imports` clean (the 4 boundary contracts already cover
  `align/` — no new contract needed).
- `uv run python -c "from pathlib import Path; from lecturenotes.ingest.captions import ingest_captions; from lecturenotes.align.scoring import term_weights; w = term_weights(ingest_captions(Path('tests/fixtures/captions/lecture01.vtt'))); print(w['bellman'] > w['equation'] > 0)"`
  prints `True`.
- `uv run python -c "from lecturenotes.align.scoring import tokenize; print(sorted(tokenize(\"V(s) = max_a [ R(s, a) + gamma * sum_s' T(s, a, s') V(s') ]\")))"`
  prints `['gamma', 'max', 'sum']`.
- `git log` shows the tests committed before (or together with, never after) the
  implementation; `git status` clean.

## Decisions & notes

- **Rarity over the transcript, not the deck.** In the deck almost every content word
  is rare (slides are terse), so deck-side IDF separates nothing; it is the 22-segment
  transcript that makes "equation" (df 4) generic and "bellman" (df 3) — and
  "iteration" (df 1) — pinning. `ln(N/df)` needs no smoothing: a shared term has
  `df ≥ 1` by construction, and a term in every segment weighs exactly 0.
- **A stopword list *and* IDF, not either alone.** IDF alone leaves "the" with a small
  positive weight, which would make "scores zero against every slide" — the property
  the gap detection of P4-03 rests on — false for every gap segment. The list handles
  function words; IDF grades the content words the list can't know about.
- **No stemming.** "rewards"/"reward" and "recursive"/"recursively" do not match, and
  the fixture scores stay strong anyway (segment 3 shares eight distinct terms with
  slide 1). A stemmer would add a dependency and a class of surprising matches for a
  marginal gain; revisit only with a real lecture that visibly misaligns, and add its
  hard case to the fixtures first (P0-03 rule).
- **Speaker notes never score.** Notes are PPTX-only (P2-02: PDF decks have
  `notes=None`), so scoring them would make alignment differ between two exports of
  the same deck; P4-03 turns that into the cross-format test (PDF chunks == PPTX
  chunks). Notes remain generation context for Phase 5.
- **`tokenize` returns a set.** Term *presence* is the signal; counts would double-pay
  a term the lecturer repeats and add nothing the weights don't already express. This
  also makes P4-02's distinct-union window scoring the natural continuation rather
  than a special case.
- **The `< 2` shared-terms bound is vocabulary-level fixture documentation here** —
  P4-03 adopts it as the off-slide rule. Asserting the exact stray pair
  (`{"number"}`) keeps the fixture honest: if a future fixture edit adds a second
  coincidental hit, this test names the collision instead of a distant alignment test
  failing mysteriously.
