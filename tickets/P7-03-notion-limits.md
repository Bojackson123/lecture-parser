# P7-03 — Notion limits
Phase 7 · Depends on: P7-02 · Size: M

## Goal

Enforce Notion's four API limits inside `render/notion.py` — the named half of the
plan §6 done-criterion (*limits enforced*), and the reason plan §2.3 exists: "Target
limits live in the renderer. Notion's 2,000-char rich-text cap, 100-element children
arrays, 2-level nesting, 1,000-block payloads … All renderer-local. None of it
appears in the IR or upstream." After this ticket, any valid `NoteWeek` — however
long its prose or deep its lists — renders to payloads Notion will accept, and
hypothesis proves it for arbitrary input, the plan §10 treatment for pure stages.

## Scope

**In**
- Limit enforcement in `lecturenotes/render/notion.py`, applied at block-build
  time.
- Property + ad-hoc tests in `tests/render/test_notion_limits.py`.

**Out**
- Any new module, IR field, `RenderOptions` knob or `model/` change — the quoted
  §2.3 rule is the whole point; a limit that needs the IR's help is a design bug.
- Emitter-side splitting or retrying → nothing; P7-04 posts payloads as given,
  which is exactly why the limits must be right here.
- Notion caps the plan doesn't name (URL lengths, equation-expression size, rows
  per table). Out until one is hit in the wild; inventing caps is speculation.

## Tasks

1. **`tests/render/test_notion_limits.py` first**:
   - **Hypothesis properties** over generated weeks (reuse the IR strategies the
     P3-01 degrade tests built), asserting on the parsed rendered payload:
     - every rich-text run's content is ≤ 2,000 characters;
     - every `children` array — each payload's top level and every nested level —
       has ≤ 100 elements;
     - every payload contains ≤ 1,000 blocks, counting nested blocks;
     - no block nests deeper than 2 levels;
     - text is preserved: concatenating a split run's pieces yields the original,
       and flattening loses no bullet text.
   - **Ad-hoc boundary cases**: a 2,000-char prose stays one run and 2,001 splits
     into two; 100 objectives stay one array and 101 split; a 3-deep bullet list
     flattens its third level into its depth-2 parent in pre-order; a topic body
     long enough to exceed 1,000 blocks splits into a second payload at a
     top-level block boundary.
   - A split never lands inside an inline `equation` run — a translated `$…$` is
     atomic; only text runs split.
   - **The fixture is untouched**: `week01.notion.json` still byte-equals the
     render (it sits far below every limit — the P7-01 decision, now proven).
2. **Implementation**, renderer-local:
   - rich-text builder splits long text into consecutive ≤ 2,000-char runs;
   - children arrays chunk at 100 — sibling list items past the hundredth start a
     new parent-level continuation, and payloads' top level chunks the same way;
   - payload batching: top-level blocks accumulate into the current payload until
     the next block would push the nested-inclusive count past 1,000, then a new
     payload starts;
   - depth cap: bullet children below depth 2 are flattened into their depth-2
     ancestor pre-order (the `_flatten_items` shape, re-implemented locally —
     `model`'s helper is degradation's, and render must not reach into it).
3. Run the full check suite — including `tests/contract/` for all three renderers —
   and commit in two steps: tests first, then the implementation.

## Acceptance criteria

- `uv run pytest` → all green, including the new property tests under hypothesis
  and the untouched `week01.notion.json` byte-equality pin from P7-02.
- `uv run pytest tests/contract/ -v` → 12 tests, no skips (limits changed no
  fixture-visible output).
- `uv run ruff check .`, `uv run mypy`, `uv run lint-imports` clean.
- `git diff HEAD~2 -- tests/fixtures/` is empty — no fixture changed.
- `git log` shows tests committed before (or with, never after) the
  implementation; `git status` clean.

## Decisions & notes

- **The depth cap is a limit, not degradation, and `NESTING` stays declared.** The
  plan files "2-level nesting" under renderer-local target limits (§2.3), alongside
  the character caps — same list, same treatment. `degrade()` answers "can this
  target nest at all"; the cap answers "how deep does this target's API accept",
  which no other renderer shares and the capability↔construct map must not learn.
  Recorded so nobody later "fixes" the renderer by stripping `NESTING` and letting
  degrade flatten everything to depth 0 — that would visibly worsen output Notion
  can represent.
- **Split points are dumb on purpose.** Runs split at exactly 2,000 characters,
  not at word boundaries: Notion joins adjacent runs seamlessly, so the reader
  never sees the seam, and clever splitting is untestable prose aesthetics. The
  one real constraint — never inside an inline equation — is structural, and
  pinned.
- **Payloads split only at top-level block boundaries.** A block and its children
  travel together; a topic whose single block tree exceeds 1,000 nested blocks is
  out of scope until the IR can produce one (it can't today — bullet text is flat
  strings), and a validator error then is better than a speculative sub-block
  protocol now.
- **The fixture proving nothing changed is the point of the P7-01 split.** Format
  and limits are separate specs: the fixture pins the mapping, hypothesis pins the
  caps, and this ticket touching zero fixtures is the evidence the split worked.
