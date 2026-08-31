# lecturenotes

Turns a week of lecture material (videos, slide decks, transcripts, captions) into
structured study notes with pluggable output formats. Design: `PROJECT_PLAN.md`.
Work items: `tickets/README.md`.

## The note IR

Plan §2.2, verbatim. This is the only contract between the two halves of the pipeline.

Semantic node types, not presentational ones. The renderer decides what a
`Callout(kind=EXAM)` looks like; the IR only records that the lecturer flagged it.

```python
NoteWeek
  id, course, week_number, lectures: [NoteLecture]

NoteLecture
  id, title, overview, objectives: [str]
  source: SourceRef            # video url, deck path, caption path
  topics: [Topic]
  glossary: [Definition]
  open_questions: [str]

Topic
  id                           # stable, see §7.2
  heading: str
  anchor: SourceAnchor         # timestamp + slide range — the citation
  body: [Node]                 # ordered, heterogeneous
  cards: [CardSeed]            # optional Q/A pairs for spaced-repetition targets

Node = Prose | BulletList | Definition | Equation | CodeBlock
     | Callout | Figure | Table | Quote
```

Notable choices:

- **`Equation` holds LaTeX, always.** Every plausible target consumes LaTeX natively
  or near-natively. Storing rendered math would be a one-way door.
- **`Callout` has a `kind` enum**, not a colour or emoji: `EXAM`, `PITFALL`,
  `UNCERTAIN`, `ASIDE`. Presentation is downstream.
- **`SourceAnchor` on every topic** is the feature that makes the notes trustworthy.
  Timestamp plus slide numbers, so any claim can be checked in seconds.
- **`CardSeed` is generated but ignored by document renderers.** Costs nothing to
  produce alongside the notes; makes the Anki target trivial later. Don't add a
  separate extraction pass for it.
- **`Figure` references a `MediaAsset` by id**, not a path. Assets are resolved by the
  emitter — inlined as base64, uploaded, or copied next to the output, as appropriate.

## Stable IDs

Plan §7.2, verbatim.

Topic ids must survive regeneration so that re-emitting **updates** rather than
duplicates. Derive them from source coordinates — `lecture_id + slide_range` — not from
position in the list or a slug of the heading, both of which move when you change a
prompt.

## Boundary rules

- `model/` imports nothing else in the package.
- `render/` never imports `ingest/`.

import-linter enforces these: the contracts live in `pyproject.toml`
(`[tool.importlinter]`) and `tests/test_boundaries.py` runs `lint-imports` from inside
`pytest`, so a violation fails the ordinary test run, not only `uv run lint-imports`.

## Checks

```
uv sync --all-groups
uv run pytest
uv run ruff check .
uv run mypy
uv run lint-imports
```

## Working conventions

- One phase per session (plan §6). Each phase has explicit done-criteria.
- Tests first for done-criteria: write the tests that encode "done" before the code.
- When the IR must change, change `model/` and let mypy find the breakage rather than
  patching renderers individually (plan §10).
