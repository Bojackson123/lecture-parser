# P3-04 — `lecturenotes render FILE [-o DIR]` inspection command + Phase 3 done-gate
Phase 3 · Depends on: P3-02, P3-03 · Size: S

## Goal

Make Phase 3 runnable from the shell, as P1-04 and P2-04 did for their phases: a
`render` subcommand that reads a `NoteWeek` JSON, renders it with the markdown
renderer, and either prints the documents or emits them to a directory. This is also
the plan §7.1 tuning loop in miniature — once Phase 5 caches generated weeks,
re-rendering a cached `NoteWeek` while tweaking a renderer costs zero tokens, and this
command is how. Then close the phase: tick the done-gate in `tickets/README.md`, move
the four P3 tickets to `tickets/completed/`, and record the Phase 3 invariants later
phases must respect in `CLAUDE.md`.

## Scope

**In**
- `render FILE [-o DIR] [--json]` subcommand in `lecturenotes/cli.py`.
- `tests/test_cli.py` additions.
- `CLAUDE.md` section "Rendering (Phase 3)" and the smoke command in "Checks".
- `tickets/README.md` done-gate, ticket moves.

**Out**
- `build`, `--dry-run`, file pairing (plan §7.4), chunking, generation — Phases 4–5.
  This command renders one existing `NoteWeek` JSON and must not grow a pipeline.
- A format/renderer selection flag — markdown is the only renderer until Phase 6,
  which adds the flag when there is a second choice.
- Asset strategies beyond the filesystem copy → Phase 7.

## Tasks

1. **`cli.py`**: add the `render` subparser next to `captions` and `slides`
   (help: "render a NoteWeek JSON to markdown (a debugging aid)"). Arguments:
   `file` (`type=Path`, a `NoteWeek` JSON such as `tests/fixtures/notes/week01.json`),
   `-o`/`--out` (`type=Path`, `metavar="DIR"`, default `None`), `--json` (print the
   `RenderResult` as JSON instead of the documents). `cmd_render`:
   - Load with `NoteWeek.model_validate_json(args.file.read_text(encoding="utf-8"))`
     inside the established `try/except (OSError, ValueError)` — pydantic's
     `ValidationError` is a `ValueError`, so a malformed or wrong-shaped JSON gets the
     uniform stderr line `lecturenotes render: {exc}` and return code 2, no traceback.
   - Render with `MarkdownRenderer().render(week, RenderOptions())`.
   - Without `-o`: `_utf8_stdout()`, then per document print `--- {name}` followed by
     the document text (already newline-terminated; no extra blank line).
   - With `-o DIR`: `emit_filesystem(result, args.out)` — `asset_root` stays at its
     `Path(".")` default, matching the fixture's repo-root-relative sources — wrapped
     in the same except (the emitter's `FileNotFoundError` is an `OSError`). Quiet on
     success, like every well-behaved writing command.
   - `--json` prints `result.model_dump_json(indent=2)` so the output re-validates
     with `RenderResult.model_validate_json`.
   - Wire `args.command == "render"` into `main()`.
2. **`tests/test_cli.py`** via `main([...])` and `capsys`:
   - `main(["render", "tests/fixtures/notes/week01.json"])` returns 0; exactly one
     line starts with `--- ` and it is `--- cs-rl-101-w01.md`; the output contains
     `$$`, `> **EXAM**` and `[2:31–4:28]` (the slide-less anchor); nothing on stderr.
   - The printed text after the `--- ` line equals
     `tests/fixtures/notes/week01.md` byte-for-byte.
   - `main(["render", "tests/fixtures/notes/week01.json", "-o", str(tmp_path)])`
     returns 0 and prints nothing; `tmp_path / "cs-rl-101-w01.md"` equals the
     expected markdown; `tmp_path / "assets/fig-value-iteration-convergence.png"`
     equals `tests/fixtures/decks/value_iteration.png` byte-for-byte.
   - `--json` output re-validates: `RenderResult.model_validate_json(out)` has one
     document and one asset.
   - `tests/fixtures/captions/lecture01.vtt` (valid file, not a `NoteWeek`) → return
     2, stderr message with the `lecturenotes render:` prefix, nothing on stdout; a
     missing path → likewise.
   - `captions …`, `slides …`, `--version`, and no-args behaviour unchanged.
3. **`CLAUDE.md`**: add **"Rendering (Phase 3)"** after "Slide ingest (Phase 2)" with
   the invariants later phases depend on:
   - `degrade(week, capabilities)` lives in `model/` and takes a `set[Capability]`,
     never a renderer; renderers declare capabilities and never improvise degradation
     — the capability↔construct map is defined once, in `constructs_used`;
   - every renderer surfaces anchors via `format_clock` (from `render/base.py`) — the
     contract test greps for it;
   - renderers are pure (`NoteWeek` in, `RenderResult` out, no IO); emitters own IO
     and never read the IR; asset files are id-keyed via the shared `asset_target`,
     so links and paths cannot drift and re-emits update in place;
   - the expected markdown `tests/fixtures/notes/week01.md` is hand-written and never
     regenerated from the code under test;
   - `render/` and `emit/` never import `ingest/`, `align/` or `generate/`
     (import-linter, 4 contracts);
   - `lecturenotes render FILE` is a debugging aid and must not grow pairing,
     generation, or a format flag before Phase 6.
   Add `uv run lecturenotes render tests/fixtures/notes/week01.json   # smoke: 1 document`
   to the "Checks" block.
4. **`tickets/README.md`**: tick the Phase 3 done-gate boxes with the date, relink the
   P3 rows to `completed/…`, and replace the closing line with "**Phase 3 is done.**
   Phase 4 (alignment) can start; its tickets will be added to this index in a later
   session."
5. `git mv tickets/P3-0*.md tickets/completed/`. Run the full suite from a clean state
   (`git stash -u` anything unrelated, `uv sync --all-groups`) and commit.

## Acceptance criteria

- `uv run lecturenotes render tests/fixtures/notes/week01.json | grep -c "^--- "`
  prints `1`.
- `uv run lecturenotes render tests/fixtures/notes/week01.json | tail -n +2 | diff - tests/fixtures/notes/week01.md`
  prints nothing.
- `uv run lecturenotes render tests/fixtures/decks/lecture01.deck.json; echo $?`
  prints an error line then `2` (a valid JSON of the wrong shape).
- After `uv run lecturenotes render tests/fixtures/notes/week01.json -o /tmp/w01`:
  `ls /tmp/w01` shows `assets` and `cs-rl-101-w01.md`, and
  `cmp /tmp/w01/assets/fig-value-iteration-convergence.png tests/fixtures/decks/value_iteration.png`
  prints nothing.
- `uv run lecturenotes captions tests/fixtures/captions/lecture01.vtt | wc -l` still
  prints `22`; `uv run lecturenotes slides tests/fixtures/decks/lecture01.pdf | grep -c "^--- slide"`
  still prints `3`; `uv run lecturenotes --version` still prints `lecturenotes 0.0.1`.
- From a clean checkout: `uv sync --all-groups && uv run pytest && uv run ruff check . && uv run mypy && uv run lint-imports` passes.
- `ls tickets/completed/ | grep -c P3-` prints `4`; `ls tickets/*.md` lists no P3
  files.
- `grep -c "Rendering (Phase 3)" CLAUDE.md` ≥ 1.

## Decisions & notes

- **A debugging-and-tuning aid, not the product** — the same stance as `captions` and
  `slides`, with one difference: this command outlives its debugging role. Plan §7.1's
  cache makes regeneration cheap only if re-rendering is free, and `render` on a
  cached `NoteWeek` JSON is that free step. It still must not grow a pipeline;
  `build` (Phase 5) composes the stages.
- **stdout is the default, `-o` is opt-in** — mirrors the print-first stance of the
  other commands; piping one week page through `less` or into `head` is the common
  inspection move, and emitting is the deliberate act.
- **Quiet on success in `-o` mode.** The paths are deterministic (`{week.id}.md`,
  id-keyed assets); printing them adds noise to the loop the command exists for.
- **No format flag yet.** With one renderer a `--format markdown` is dead weight and
  a name to bikeshed; Phase 6 adds the flag when Anki gives it a second value. The
  fence is recorded in `CLAUDE.md`.
- **`--json` dumps the `RenderResult`, not the `NoteWeek`** — the input is already a
  `NoteWeek` JSON; the render result (document names, text, manifest) is the thing a
  scripted check wants, and it re-validates, per the P1-04/P2-04 rule that `--json`
  output round-trips.
- **`asset_root` stays at the cwd default.** The fixture's sources are
  repo-root-relative, so the smoke command works from the repo root; when Phase 5
  produces weeks whose sources live elsewhere, the flag to override it can be added
  alongside the code that needs it — not before.
