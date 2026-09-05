# P7-05 — `--format notion`, `lecturenotes push` + Phase 7 done-gate
Phase 7 · Depends on: P7-03, P7-04 · Size: M

## Goal

Wire Phase 7 into the CLI and close it. `render` gains `notion` as the one
`_RENDERERS` entry CLAUDE.md reserved in P6-03 — the whole render-side diff — and a
new `lecturenotes push FILE --parent PAGE_ID` command composes `NotionRenderer` with
`emit_notion` over the real transport, completing the plan §2 diagram's last arrow
(stage 8, emit, for a target that isn't a filesystem). Then the phase closes: done-
gate ticked, tickets moved, invariants recorded, plus the one manual gate item only
a real Notion can verify — pushing the fixture week twice and watching the second
push update the same page instead of creating a sibling.

## Scope

**In**
- `cli.py`: `_RENDERERS["notion"] = NotionRenderer`; the new `push` subcommand.
- CLI tests in `tests/test_cli.py`.
- `tickets/README.md` Phase 7 done-gate ticked; P7 tickets moved to `completed/`.
- `CLAUDE.md`: Phase 7 invariants section; new smoke lines; the render-section
  sentence that reserved the `notion` entry updated.
- One manual check: a real double push to a scratch Notion page.

**Out**
- A `--format` or push on `build` — build writes IR JSON; presentation and
  delivery stay downstream (the §7.1 two-command loop, unchanged since P6-03).
- Pairing, generation or alignment logic on `render` or `push` — standing
  CLAUDE.md rule.
- `--dry-run`, `--clean`, retry/backoff, multi-week push — knobs arrive when a
  real need does (the P6-03 discipline).
- Any change to `render/notion.py` or `emit/notion_api.py` beyond imports —
  P7-02..04 finished them.

## Tasks

1. **CLI tests first** in `tests/test_cli.py`:
   - `render tests/fixtures/notes/week01.json --format notion` exits 0 and prints
     `--- cs-rl-101-w01.notion.json` followed by the payload JSON, byte-identical
     to `tests/fixtures/notes/week01.notion.json`; the default stays markdown and
     the existing render tests pass untouched; `--format notion -o DIR` writes the
     document **and** copies the figure PNG to `DIR/assets/` (non-empty manifest —
     unlike anki's `-o`), making `-o` the offline debugging view of what `push`
     would upload.
   - `push` wiring: `push` without `--parent` → argparse error, exit 2; `push` on
     a missing/invalid week JSON → the standard render-path error contract, exit 2.
   - **No token → clean error**: with `NOTION_TOKEN` unset (monkeypatched away),
     `push tests/fixtures/notes/week01.json --parent x` prints
     `lecturenotes push: NOTION_TOKEN is not set` to stderr, exits 2, and
     constructs no transport (the P5-01 doctrine, asserted the same way).
   - **Fake-injection run**: with the transport factory monkeypatched to
     `FakeNotionTransport`, a push of `week01.json` performs the full P7-04 fresh-
     emit sequence and prints a one-line summary (page title, payload count,
     asset count); pushing again against the same fake performs the re-emit
     sequence — no second page.
   - `--asset-root` defaults to the week JSON's directory: pushing a copy of
     `week01.json` from a temp dir with `media/` beside it uploads those bytes
     (the P5-03 rule, now observable end-to-end).
2. **`cli.py`**:
   - add the `_RENDERERS` entry — `--format` choices grow to
     `{anki,markdown,notion}` with markdown still the default; the render path
     needs nothing else (print, `--json`, `-o` are format-agnostic since P6-03).
   - `cmd_push`: load + validate the week JSON (same error contract as
     `cmd_render`), render with `NotionRenderer`, read `NOTION_TOKEN` **here, at
     run time** (never at import, never before validation), build
     `UrllibTransport`, call `emit_notion(..., parent_page_id=args.parent,
     asset_root=<week JSON's directory, or --asset-root>)`, print the summary
     line. Transport construction behind a small factory hook so the tests inject
     the fake.
3. **Manual gate item** (record dated in the done-gate, like P5-04's real run and
   P6-03's double import): create a scratch Notion page, share it with a scratch
   integration, then
   `uv run lecturenotes push tests/fixtures/notes/week01.json --parent <id>`
   twice. First run: page "CS-RL-101 — Week 1" appears with both lectures, the
   figure rendered from the uploaded PNG, equation blocks and inline math
   rendering, callout icons per kind. Second run: **the same page** (same URL)
   updated in place — no duplicate sibling. §7.2 observed end-to-end against the
   real API.
4. **Close the phase** (mirror P6-03):
   - Tick the Phase 7 done-gate in `tickets/README.md`; append "**Phase 7 is
     done.** Phase 8 tickets are not written yet."; move the five P7 tickets to
     `tickets/completed/` and repoint the table links.
   - `CLAUDE.md` §Checks: add
     `uv run lecturenotes render tests/fixtures/notes/week01.json --format notion   # smoke: 1 page payload`.
   - `CLAUDE.md`: update the render-section sentence that reserved the `notion`
     entry, and add a **Notion (Phase 7)** invariants section: the four §2.3
     limits are renderer-local in `render/notion.py`, never in the IR or upstream;
     the payload JSON (`{"page", "payloads"}`, blocks verbatim, asset
     placeholders) is the renderer↔emitter contract, pinned by the hand-written
     `week01.notion.json`; the page title (course + week number) is the page
     identity — re-push updates in place, retitling forks deliberately; the
     emitter never reads the IR and archives-then-appends, never diffs;
     `NOTION_TOKEN` is read only by `push` at run time; the inline `$…$` →
     equation-run dialect never leaves `render/notion.py`; `push` grows no
     pairing, generation or alignment logic.
5. Full check suite; commit.

## Acceptance criteria

- `uv run pytest && uv run ruff check . && uv run mypy && uv run lint-imports`
  green from a clean checkout after `uv sync --all-groups`, with no `NOTION_TOKEN`
  in the environment.
- `uv run lecturenotes render tests/fixtures/notes/week01.json` still prints the
  markdown document (default unchanged — existing smoke lines intact).
- `uv run lecturenotes render tests/fixtures/notes/week01.json --format notion`
  prints 1 document whose body parses as JSON with keys `page` and `payloads`.
- `uv run lecturenotes push tests/fixtures/notes/week01.json --parent x` with no
  `NOTION_TOKEN` exits 2 with the token message on stderr.
- The manual double-push item is ticked in the done-gate with the date, the page
  URL observed stable, and "no duplicate sibling" recorded.
- `tickets/` contains only `README.md` and `completed/`; the Phase 7 table links
  resolve; `CLAUDE.md` shows the new invariants section; `git status` clean.

## Decisions & notes

- **`push` is its own subcommand, not a `render` flag.** `render` is the pure,
  offline §7.1 tuning loop and the debugging aid; `push` is stage 8 — credentials,
  network, side effects. Folding them would put an env-var read and a network
  failure mode inside the one command every invariant says stays pure-ish.
  The pipeline stays two visible halves at the CLI, as in the §2 diagram.
- **`push` renders internally rather than reading a rendered file** because the
  payload JSON is a contract between two modules, not a user-facing interchange
  format; the week JSON is the user-facing artifact (§7.1: build once, present
  many ways — `push` is one more way).
- **The token is env-only, no `--token` flag**: flags leak into shell history and
  process lists; `NOTION_TOKEN` matches the `ANTHROPIC_API_KEY` precedent,
  including the read-at-use-time doctrine.
- **The factory hook is the minimum injection point** — one module-level callable
  the tests monkeypatch, not a plugin system; the same restraint as the
  `_RENDERERS` dict (P6-03: resist generalising until a third party exists).
- **The manual item checks the one claim the suite cannot**: that Notion's real
  API accepts the payloads and that find-by-title means what we think. Everything
  mechanical is already pinned — byte-for-byte format (P7-01/02), limits under
  hypothesis (P7-03), call sequences against the fake (P7-04) — so one dated
  manual run is evidence, not a test suite escape hatch.
