# P1-02 — Rolling-caption dedupe
Phase 1 · Depends on: P1-01 · Size: M

## Goal

Add `dedupe_rolling(cues: list[Cue]) -> list[Cue]` to `lecturenotes/ingest/captions.py`
so that YouTube-style rolling captions — where each cue's first line repeats the
previous cue's last line — collapse to one copy of every line, each keeping the timing
of the cue it first appeared in. On the fixture, cues 1–6 (14 lines) must yield exactly
the seven unique lines A…G the fixture README promises, and cues 7–20 must be untouched.
Plan §10 calls the caption-dedupe edge cases "the whole difficulty" of Phase 1; this
ticket is where they live, and it is tests-first.

## Scope

**In**
- `dedupe_rolling` in `captions.py`.
- `tests/ingest/test_dedupe.py` (example-based) and `tests/ingest/test_dedupe_properties.py` (hypothesis).

**Out**
- Sentence merging and segment construction → P1-03. This ticket outputs `Cue`s, not `Segment`s.
- Fuzzy / near-duplicate detection (see Decisions).
- Deduping across non-adjacent cues (see Decisions).

## Tasks

1. **Write the fixture tests first** (`tests/ingest/test_dedupe.py`), against
   `parse_vtt` output of `tests/fixtures/captions/lecture01.vtt`:
   - 20 cues in → 20 cues out (no cue in the fixture empties completely).
   - Cues 1–6 after dedupe carry, in order, the seven lines:
     A `welcome back everyone, …`, B `a markov decision process …`,
     C `and a transition function …`, D `the reward is a number …`,
     E `and the discount factor gamma …`, F `keep this picture …`,
     G `is nothing more than …` — assert on the full strings from the fixture.
   - Cue 1 keeps two lines (A, B); cues 2–6 keep one line each (C…G).
   - Every cue's `start_s`/`end_s` is unchanged from the parsed input.
   - Cues 7–20 are identical to their parsed input (`==` on the `Cue` objects).
   - The same assertions hold for the SRT fixture (parametrise over both files).
2. **Ad-hoc example tests**, built from small inline `Cue` lists:
   - **Whole-cue repeat**: `[Cue(0, 2, ("foo bar",)), Cue(2, 5, ("foo bar",))]` →
     one cue `Cue(0, 5, ("foo bar",))` — the repeated cue is dropped and the survivor's
     `end_s` is extended to cover it.
   - **Two-line overlap** (`k = 2`): prev lines `(a, b, c)`, cur lines `(b, c, d)` → cur
     becomes `(d,)`.
   - **Partial line is not a repeat**: prev `(…, "the reward is a number")`, cur
     `("the reward is a number you get", …)` → nothing dropped. Exact line equality only.
   - **Non-adjacent repeat is kept**: `(x,) (y,) (x,)` → unchanged. Only neighbours are compared.
   - **Single cue** and **empty list** return unchanged / empty.
   - **Chain of whole-cue repeats**: three identical cues collapse to one spanning all three.
3. **Implement `dedupe_rolling`**:
   - Walk the list once. For each `cur` with a surviving `prev`, find the largest `k`
     (bounded by `min(len(prev.lines), len(cur.lines))`) such that
     `prev.lines[-k:] == cur.lines[:k]`; keep `cur.lines[k:]`.
   - If nothing survives, replace `prev` with `prev.model_copy(update={"end_s": cur.end_s})`
     and do not append `cur`.
   - Never mutate inputs (they are frozen anyway); return a new list.
   - Comparison is exact string equality on the already-normalised lines from P1-01 —
     no lower-casing, no punctuation stripping.
4. **Property tests** (`tests/ingest/test_dedupe_properties.py`), reusing the P1-01 cue
   strategy plus a second strategy that *injects* rolling repeats (copy the previous
   cue's last line to the front of the next cue with probability ½, and occasionally
   duplicate a whole cue):
   - Output lines, concatenated in order, are a subsequence of the input lines.
   - No adjacent output pair has `prev.lines[-1] == cur.lines[0]`.
   - `dedupe_rolling(dedupe_rolling(x)) == dedupe_rolling(x)` (idempotent).
   - On inputs with no adjacent repeats, output `== input` (identity).
   - `start_s` is non-decreasing in the output; every output cue has ≥ 1 line.
   - `sum(end_s - start_s)` over the output is ≥ the same sum over the input minus the
     spans of dropped cues, i.e. covered time never shrinks: the last cue's `end_s` is
     unchanged and the first cue's `start_s` is unchanged.
   - For the injected-repeats strategy: deduping the injected list gives back the
     original clean list (round-trip through corruption).
5. Run the full check suite and commit.

## Acceptance criteria

- `uv run pytest tests/ingest` → all green, including the hypothesis modules.
- `uv run ruff check .`, `uv run mypy`, `uv run lint-imports` clean.
- `uv run python -c "from pathlib import Path; from lecturenotes.ingest.captions import parse_vtt, dedupe_rolling; c=dedupe_rolling(parse_vtt(Path('tests/fixtures/captions/lecture01.vtt').read_text(encoding='utf-8'))); print(len(c), sum(len(x.lines) for x in c[:6]))"`
  prints `20 7`.
- `git status` clean after commit.

## Decisions & notes

- **Exact match, not fuzzy.** Auto-caption exporters repeat lines verbatim; a genuine
  verbal repetition ("no, no, no") is rarely a whole *line* and is worth keeping.
  Fuzzy matching would silently eat real speech, which is the failure mode plan §4.2
  warns about (confident output that is subtly wrong). Revisit only with a real file
  that defeats exact matching, and add that file's pattern to the fixture first.
- **Adjacent cues only.** Rolling captions are a sliding window over consecutive cues;
  a line reappearing ten cues later is the lecturer repeating themselves, which Phase 5
  should see.
- **A fully-repeated cue extends its predecessor's `end_s`** rather than vanishing,
  because the words were on screen for that long and the `SourceAnchor` derived from
  them (plan §2.2) should cover the whole interval.
- **Timings are otherwise never altered.** Every surviving line keeps the span of the
  cue it first appeared in. P1-03 decides how spans combine into segments.
- `dedupe_rolling` is a separate public function rather than a flag on the parser so
  the `--dry-run` tooling in Phase 5 can show before/after when a lecture's captions
  look wrong.
