# P3-02 — Markdown renderer + hand-written expected markdown
Phase 3 · Depends on: P3-01 · Size: L

## Goal

Create `lecturenotes/render/markdown.py` (plan §5): a `MarkdownRenderer` that declares
all six capabilities and renders a `NoteWeek` to **one week page**. The expected output
`tests/fixtures/notes/week01.md` — the render-side twin of `decks/lecture01.deck.json`
— is hand-written **first**, transcribed from `tests/fixtures/notes/week01.py`; it is
the format spec, every formatting decision is reviewable in it, and the Phase 3
done-criterion (plan §6: *the hand-written `NoteWeek` fixture renders to a readable
file*) becomes one byte-equality test against it. Registering the renderer in
`tests/contract/test_renderers.py` turns the four contract properties live — the
skips from P3-01 vanish.

## Scope

**In**
- `tests/fixtures/notes/week01.md` (hand-written, before any renderer code).
- `lecturenotes/render/markdown.py`: `MarkdownRenderer`.
- `tests/render/__init__.py`, `tests/render/test_markdown.py`.
- `MarkdownRenderer` registered in `tests/contract/test_renderers.py`.
- `tests/fixtures/README.md`: pointer to `week01.md`.

**Out**
- Writing anything to disk → P3-03. CLI → P3-04.
- Degradation behaviour for markdown — it declares all six capabilities, so
  `degrade()` is a no-op for it; degradation itself is tested in P3-01.
- Rendering `CardSeed`s — document renderers ignore cards (plan §2.2); Phase 6
  consumes them.
- A week index page, per-lecture splitting, or any `RenderOptions` knob — the
  one-week-page decision is recorded below, not made configurable.
- Anki, Notion, HTML renderers → Phases 6–7.

## Tasks

1. **Hand-write `tests/fixtures/notes/week01.md` first**, transcribed from the
   constants and node values in `tests/fixtures/notes/week01.py` — never from the code
   under test. LF line endings, single trailing newline, one blank line between
   blocks. The full skeleton, in order:
   - `# CS-RL-101 — Week 1` (`# {course} — Week {week_number}`).
   - Per lecture, in order: `## {title}`, the overview as a paragraph,
     `**Objectives**` followed by one `- ` bullet per objective, then the topics,
     then `### Glossary` (one `- **{term}** — {definition}` bullet per entry), then
     `### Open questions` (one `- ` bullet per question). Objectives, glossary and
     open-questions sections are omitted entirely when their list is empty.
   - Per topic: `### {heading}`, then the anchor line on its own paragraph:
     `[0:01–2:29 · slide 1]` for `lec01`'s MDP topic, `[3:00–7:00 · slides 2–3]` for
     a range, `[2:31–4:28]` for the slide-less board-work topic — i.e.
     `[{format_clock(start_s)}–{format_clock(end_s)}]` plus ` · slide N` /
     ` · slides N–M` when `anchor.slides` is set (en-dashes throughout, matching the
     `captions` output style). Then the body nodes.
   - Node mappings:
     - `Prose` → the text as one paragraph, verbatim — inline `$…$` passes through.
     - `BulletList` → `- {text}` per item, children indented by two spaces per level.
     - `Definition` (in a body) → `**{term}** — {definition}` as its own paragraph.
     - `Equation` → `$$` / the LaTeX on its own line(s) / `$$`. The `label` is not
       rendered.
     - `CodeBlock` → fenced with the language: ` ```python ` … ` ``` ` (bare ` ``` `
       when `language is None`).
     - `Callout` → `> **{kind.value}** — {text}` (one blockquote line; the kind enum
       value, so `EXAM`, `PITFALL`, `UNCERTAIN`, `ASIDE`).
     - `Figure` → `![{alt}]({asset_target(asset)})` — `alt` from the owning lecture's
       asset (empty string when `None`) — then `*{caption}*` on the next line (no
       caption line when `None`). For the fixture:
       `![Line plot of maximum value change per sweep, decaying geometrically](assets/fig-value-iteration-convergence.png)`.
     - `Table` → pipe table: header row, `| --- |` separator row, one row per
       `rows` entry; `|` inside a cell escaped as `\|`.
     - `Quote` → `> {text}`, then `> — {attribution}` when present.
2. **`tests/render/test_markdown.py`** (red on `ImportError`; commit with the
   fixture):
   - The done-gate: `MarkdownRenderer().render(week01, RenderOptions())` yields one
     document named `cs-rl-101-w01.md` whose `text` equals
     `tests/fixtures/notes/week01.md` byte-for-byte. The assertion message says: *the
     expected markdown is hand-written; if the format changed on purpose, edit the
     file deliberately — do not regenerate it from the code under test.*
   - The manifest is exactly the one referenced asset
     (`fig-value-iteration-convergence`), even though `lec02` contributes none.
   - **Ad-hoc weeks built in-memory** — the render-side analogue of P2-01's ad-hoc
     decks; small single-topic `NoteWeek`s constructed in the test:
     - a `Table` cell containing `a | b` renders with `a \| b`;
     - a `Figure` whose asset has `alt=None` renders `![](assets/…)`; a figure with
       `caption=None` has no italic line after the image;
     - an unlabelled `Equation` renders identically to a labelled one;
     - a lecture with empty `objectives`, `glossary` and `open_questions` contains
       none of those headings;
     - a topic with `slides=None` has no ` · slide` in its anchor line;
     - the rendered text ends with exactly one `\n` and contains no `\r`.
3. **`render/markdown.py`**: `class MarkdownRenderer` with `name = "markdown"`,
   `capabilities = set(Capability)` (fenced code, pipe tables, `$$` math, blockquote
   callouts, image links and nested lists are all native to markdown), and a pure
   `render()` building the document by string concatenation — no IO, no dict
   iteration order to worry about, deterministic by construction. Links built with
   `asset_target()` from `render.base`, never by hand. The manifest lists assets in
   first-reference order, each once.
4. **Register** `MarkdownRenderer()` in `RENDERERS` in
   `tests/contract/test_renderers.py` — the four properties now run un-skipped.
5. **`tests/fixtures/README.md`**: add `notes/week01.md` to the file listing — "the
   week rendered as one markdown page, hand-written (P3-02)" — with the "never
   regenerated from the code under test" sentence, as for the segments and deck files.
6. Run the full check suite and commit in two steps: the fixture and tests first (red
   on `ImportError`), then the implementation.

## Acceptance criteria

- `uv run pytest` → all green, and `uv run pytest tests/contract/ -v` shows the four
  contract tests **passing, not skipping**, for `markdown`.
- `uv run ruff check .`, `uv run mypy`, `uv run lint-imports` clean.
- `uv run python -c "from lecturenotes.render.markdown import MarkdownRenderer; from lecturenotes.render.base import RenderOptions; from tests.fixtures.notes.week01 import week01; r = MarkdownRenderer().render(week01(), RenderOptions()); print(r.documents[0].name, len(r.documents), len(r.assets))"`
  prints `cs-rl-101-w01.md 1 1`.
- `uv run python -c "from pathlib import Path; from lecturenotes.render.markdown import MarkdownRenderer; from lecturenotes.render.base import RenderOptions; from tests.fixtures.notes.week01 import week01; print(MarkdownRenderer().render(week01(), RenderOptions()).documents[0].text == Path('tests/fixtures/notes/week01.md').read_text(encoding='utf-8'))"`
  prints `True`.
- `grep -c "^## " tests/fixtures/notes/week01.md` prints `2` (two lectures, one page);
  `grep -c "^# " tests/fixtures/notes/week01.md` prints `1`.
- `grep -c "will be on the exam" tests/fixtures/notes/week01.md` prints `1` — the
  highest-value content survives rendering (plan §4.2).
- `git log` shows the fixture and tests committed before (or together with, but never
  after) the implementation; `git status` clean.

## Decisions & notes

- **One week page, named `{week.id}.md`** (`cs-rl-101-w01.md`) — chosen by the user
  over per-lecture files, settling the plan §7.3 question for this renderer. The week
  id is stable, so re-emitting updates one file in place (§7.2 reasoning). The
  heading ladder — `#` week, `##` lecture, `###` topic — is what makes one page
  workable; lecture identity is a section, not a file. Anki and Notion decide §7.3
  for themselves; nothing here binds them.
- **The expected markdown is hand-written and never regenerated from the code under
  test** — the same doctrine as `segments.json` and `deck.json`, chosen by the user
  over a `--write`-blessed snapshot. The honest trade-off: when Phase 6 changes the
  IR, this file is edited by hand, deliberately. That friction is the point (plan
  §10) — a bless mechanism would let a formatting regression walk into the repo
  inside an unrelated diff.
- **Math is `$…$` inline and `$$…$$` display** — chosen by the user; targets
  Obsidian, Typora, Pandoc, VS Code preview and modern GitHub rendering, and matches
  the inline `$…$` already baked into the fixture's prose.
- **The anchor line is a plain bracketed paragraph, not a heading suffix.** Keeping
  `### {heading}` clean means outline views and tables of contents show headings, not
  timestamps; the anchor is the first thing under the heading, where a reader's eye
  lands when checking a claim (plan §2.2: the citation is the feature).
- **`Callout` renders as a single blockquote line with the kind in bold.** Plain
  markdown has no admonition syntax; `> **EXAM** — …` survives every viewer,
  round-trips as text, and keeps the kind machine-greppable. Obsidian-style
  `> [!warning]` callouts are a flavour commitment this renderer refuses; an HTML or
  Obsidian renderer can make one later.
- **CardSeeds are invisible in the output on purpose** (plan §2.2). The temptation to
  append a "review questions" section is real and resisted: cards are the Anki
  target's input, and duplicating them here would make the week page and the deck
  drift.
- **Equation labels are not rendered.** They are IR cross-reference handles; markdown
  has no stable equation-numbering story, and a wrong number is worse than none.
- **Only `|` is escaped, and only inside table cells.** The fixture's prose is
  already markdown-safe by construction (it was hand-written as notes); a general
  markdown-escaping pass would mangle the inline math (`\gamma` → `\\gamma`) and
  solve a problem the generator (Phase 5) is better placed to avoid. Revisit only if
  real generated output breaks a viewer.
