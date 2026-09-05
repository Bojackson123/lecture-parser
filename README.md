# lecturenotes

Turns one week of lecture material — slide decks, transcripts and captions — into
structured study notes, with the output format kept pluggable behind a single note IR.
One `build` produces a week JSON; cheap `render`/`push` steps turn that same JSON into
Markdown, an Anki deck, or a Notion page, so you can tune presentation without paying
for regeneration.

The design, pipeline stages and build phases are in
[`PROJECT_PLAN.md`](PROJECT_PLAN.md); work items are in [`tickets/`](tickets/README.md);
contributor invariants are in [`CLAUDE.md`](CLAUDE.md).

## How it works

```
captions (.vtt/.srt) ─┐
                      ├─ align ─ chunks ─ generate (Claude) ─ NoteWeek JSON ─ render ─ markdown / anki / notion
slides (.pdf/.pptx) ──┘                                            │
                                                                media/ assets
```

- **Ingest** parses captions into sentence segments and decks into titled, ordered
  slides (hidden slides skipped, logos filtered out).
- **Align** matches caption segments to slide ranges by term overlap, keeping gaps
  (board work) as explicit signals rather than dropping them.
- **Generate** calls the Claude API once per chunk plus a synthesis pass, producing a
  `NoteWeek` — topics with prose, definitions, equations (LaTeX), callouts, figures,
  and spaced-repetition card seeds. Every topic carries a `SourceAnchor` (timestamp +
  slide range), so any claim can be checked against the lecture in seconds.
- **Render/emit** turns the cached JSON into the target format. Topic and card IDs are
  stable across regeneration, so re-emitting updates in place instead of duplicating.

## Install

Requires Python ≥ 3.12 and [uv](https://docs.astral.sh/uv/).

```
uv sync
```

Copy `.env.example` to `.env` and fill in what you need:

- `ANTHROPIC_API_KEY` — used only by a real `build` generation call (never at import
  time, never during `--dry-run`).
- `NOTION_TOKEN` — used only by `push`, at run time. Create an internal integration at
  https://www.notion.so/my-integrations and share the target page with it.

A variable already set in the environment always wins over `.env`.

## Usage

Build a week from decks and captions (files are paired by sorted filename; the pairing
is printed and confirmed before anything runs):

```
uv run lecturenotes build lecture01.pdf lecture01.vtt --course CS-RL-101 --week 1 -o out/
```

This writes `out/<week_id>.json` plus `out/media/` for figure assets. Add `--dry-run`
to see the pairing and chunking without spending any API calls, `--cache-dir` to reuse
generations across runs.

Render the cached JSON into any target — the §7.1 tuning loop: build once, render
cheaply many times:

```
uv run lecturenotes render out/cs-rl-101-w01.json                    # Markdown (default)
uv run lecturenotes render out/cs-rl-101-w01.json --format anki      # Anki-importable text deck
uv run lecturenotes render out/cs-rl-101-w01.json --format notion    # Notion payload JSON
```

Push a week to Notion (the page title — course + week — is the page identity, so
re-pushing updates the same page in place):

```
uv run lecturenotes push out/cs-rl-101-w01.json --parent <PAGE_ID>
```

### Web GUI

```
uv run lecturenotes serve
```

Opens a single-page GUI on http://127.0.0.1:8765 (loopback only) covering the whole
pipeline: upload, pairing confirmation, dry-run, build with live progress, preview,
and push. The web stack lives in the `web` dependency group, which a plain `uv sync`
installs by default; every other command works without it.

### Debugging aids

Each pipeline stage has a CLI command that prints its output for one input — useful
for inspecting bad chunks, interleaved slide columns, or alignment problems:

```
uv run lecturenotes captions FILE [--json]                 # caption segments
uv run lecturenotes slides FILE [--json] [--notes]         # one deck's structure
uv run lecturenotes align DECK CAPTIONS [--json]           # slide↔caption chunks
```

## Development

```
uv sync --all-groups
uv run pytest
uv run ruff check .
uv run mypy
uv run lint-imports
```

The package splits into two halves that share only the note IR in `model/`:
`ingest/` → `align/` → `generate/` build the `NoteWeek`; `render/` → `emit/` present
it. Neither half imports the other — import-linter enforces the boundaries (contracts
in `pyproject.toml`, run as part of the normal test suite). `cli.py` and `web/` are
composers on top.

See [`CLAUDE.md`](CLAUDE.md) for the per-phase invariants and
[`PROJECT_PLAN.md`](PROJECT_PLAN.md) for the full design.
