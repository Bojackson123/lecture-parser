# P5-04 — `lecturenotes build`: pairing, dry-run, the real run + Phase 5 done-gate
Phase 5 · Depends on: P5-03 · Size: L

## Goal

The command the project exists for, and the close of Phase 5. `lecturenotes build`
composes the whole left half — ingest → align → generate — behind the plan §7.4
pairing ritual ("match by sorted filename, then **print the pairing and make the user
confirm it**"; a wrong pairing is the worst failure mode because the output looks
fine) and the plan §8 `--dry-run` ("stops before generation and prints the chunking.
This is the main debugging tool"). A real run wraps the Anthropic client in the §7.1
cache and writes a `NoteWeek` JSON plus its `media/` directory — the artifact
`lecturenotes render` already consumes, which turns §7.1's regenerate-and-render
tuning loop into two commands. The done-gate ticks both halves of the plan §6
criterion: "`build --dry-run` shows chunking; real run produces valid `NoteWeek`".

## Scope

**In**
- `cmd_build` in `lecturenotes/cli.py` (+ the `build` subparser; the align command's
  chunk printing extracted into a shared helper, its output unchanged).
- CLI tests in `tests/test_cli.py`; the Phase 5 done-gate, ticket moves, README and
  CLAUDE.md updates.

**Out**
- Rendering or emitting inside `build` — `render FILE [-o DIR]` is the next step of
  the loop and already exists (P3-04); a format flag arrives with Phase 6.
- Smarter pairing (stem matching, duration comparison, content sniffing) — §7.4
  rejects inference on purpose; sorted-order plus confirmation is the design.
- Alignment knobs on `build` (`--min-gap-s`, `--min-silence-s` stay on `align`,
  the debugging aid); a `--json` flag (the product *is* JSON files).
- Video ingest, frame pulling for gap chunks → Phase 9. Verification → Phase 8.

## Tasks

1. **Tests first** (red on unknown command), in `tests/test_cli.py`, all through
   `main([...])` + `capsys` as established there. Let `PPTX`/`VTT` be the committed
   fixture paths and `RESP` the P5-02 responses fixture:
   - **Dry run**: `main(["build", PPTX, VTT, "--course", "CS-RL-101", "--week",
     "1", "--dry-run"])` returns 0 and prints the pairing line (`lec01`, both
     filenames) followed by the 4 chunks in the align command's format (one
     `(no slide)` header). With `cli._make_client` monkeypatched to raise, the dry
     run still succeeds — no client is constructed, no key consulted.
   - **Pairing**: a directory containing two decks and two captions pairs them in
     sorted filename order as `lec01`, `lec02`; two decks + one caption exits 2
     with a message listing both sides; a path with an unknown suffix exits 2.
   - **Confirmation**: with stdin a fake TTY and `input` monkeypatched to `"n"`,
     the real run exits 1 having printed the pairing and made no client; `"y"`
     proceeds; with stdin not a TTY and no `--yes`, exit 2 with a message naming
     `--yes` (scripts must never hang on a hidden prompt).
   - **Real run** (monkeypatch `cli._make_client` to return
     `RecordedClient(RESP)`): `main(["build", PPTX, VTT, "--course", "CS-RL-101",
     "--week", "1", "--yes", "-o", str(tmp)])` returns 0 and writes
     `tmp/cs-rl-101-w01.json` and `tmp/media/img-a63ae9b7dc5e9397.png`. The JSON
     parses as a `NoteWeek` with id `cs-rl-101-w01`, course `CS-RL-101`, week 1,
     one lecture equal to the P5-03 `lecture01.notes.json` fixture with `source`
     replaced by the paths the command was given (POSIX form, the `Deck.source`
     convention).
   - **The loop closes**: `main(["render", str(tmp / "cs-rl-101-w01.json")])`
     returns 0 and prints 1 document (§7.1's tuning loop, end to end).
   - **The cache works through the CLI**: wrap the recorded client in a counting
     shim; a second identical `build` into the same `-o` makes zero `complete`
     calls (the default cache dir `<out>/.cache` persisted the five responses) and
     leaves equal output files.
2. **The subparser**: `build PATHS... --course TEXT --week N [-o DIR] [--dry-run]
   [--yes] [--model ID] [--min-words N] [--cache-dir DIR]`. `--course` and
   `--week` required (naming conventions vary too much to infer, §7.4 — and the
   week id must be stable, §7.2); `-o` defaults to `notes`; `--model` defaults to
   `DEFAULT_MODEL`; `--min-words` defaults to 100 (P5-02); `--cache-dir` defaults
   to `<out>/.cache`.
3. **`cmd_build`**:
   - Collect sources: each directory argument scanned non-recursively (sorted);
     `.pdf`/`.pptx` are decks, `.vtt`/`.srt` captions; explicit files taken as-is;
     anything else exits 2. Sort both lists by filename, zip into pairs
     (`lec01`, `lec02`, … in order); unequal counts exit 2 listing both sides.
   - Print the pairing table; confirm via `input()` unless `--yes` or `--dry-run`
     (decline → exit 1; non-TTY stdin without `--yes` → exit 2).
   - Per pair: `ingest_slides` + `ingest_captions` + `align_lecture`. `--dry-run`:
     print each lecture's `merge_chunks(chunks, args.min_words)` via the shared
     helper and stop — before any client exists.
   - Real run: `client = CachedClient(_make_client(args.model), cache_dir,
     PROMPT_VERSION)` where `_make_client(model)` is a module-level factory
     returning `AnthropicClient(model)` — the one seam tests monkeypatch;
     `generate_lecture(deck, chunks, lecture_id=..., source=SourceRef(deck_path=...,
     caption_path=...), client=client, out_dir=out, min_words=args.min_words)` per
     pair — the raw chunks plus the same `min_words` the dry run printed with, so
     the entrypoint's internal merge yields exactly the chunking `--dry-run` showed.
   - Assemble `NoteWeek(id=f"{slug}-w{args.week:02d}", course=args.course,
     week_number=args.week, lectures=...)` — `slug` = course lowercased,
     non-alphanumeric runs collapsed to `-` (so `CS-RL-101`, week 1 →
     `cs-rl-101-w01`, the fixture's own id). Write `<out>/<week_id>.json` as
     `model_dump_json(indent=2) + "\n"`, UTF-8, LF (the `week01.json` snapshot
     convention); print a one-line summary (week id, lectures, topics, assets).
4. **Docs**: extend the `cli.py` module docstring; add the build smoke line to
   `CLAUDE.md`'s Checks block and a "Generation (Phase 5)" invariants section
   (P5-01..P5-04 decisions later phases must respect: `generate_lecture` is the
   only entrypoint; the fake is keyed by request key, the cache by
   `prompt_version + model + prompt`; merge floor 100 with gap fencing; assets
   minted id-keyed into `media/`; `build` must not grow rendering or format flags
   before Phase 6).
5. **Phase 5 done-gate** (in `tickets/README.md`):
   - The plan §6 dry-run criterion is a passing test (task 1) and the smoke below.
   - The "real run produces valid `NoteWeek`" criterion is checked **manually
     once**, with `ANTHROPIC_API_KEY` set: run `build` on the fixture PPTX+VTT
     into a scratch dir without the fake, confirm the JSON validates and
     `lecturenotes render` accepts it, and note the run (date + model) in the gate.
     It is not a pytest test — no test touches the network (§8) — and at five
     small requests it costs cents.
   - From a clean checkout the full check suite passes and the smoke prints one
     pairing and 4 chunks.
   - Move P5-01..P5-04 to `tickets/completed/`, tick the gate, close the phase in
     the index ("Phase 6 tickets are below" line per convention).
6. Run the full check suite; commit tests first, then the implementation.

## Acceptance criteria

- `uv run pytest` → all green; `uv run ruff check .`, `uv run mypy`,
  `uv run lint-imports` clean.
- `uv run lecturenotes build tests/fixtures/decks/lecture01.pptx
  tests/fixtures/captions/lecture01.vtt --course CS-RL-101 --week 1 --dry-run`
  prints the `lec01` pairing and 4 chunks (one `(no slide)`), exit 0, with no
  `ANTHROPIC_API_KEY` in the environment.
- The existing `align` smoke output is byte-identical to before the helper
  extraction (`uv run lecturenotes align tests/fixtures/decks/lecture01.pdf
  tests/fixtures/captions/lecture01.vtt` still prints 4 chunks unchanged).
- Done-gate ticked in `tickets/README.md`, including the noted manual real run;
  tickets moved to `completed/`; `CLAUDE.md` carries the Phase 5 invariants and the
  build smoke line.
- `git log` shows tests committed before (or together with, never after) the
  implementation; `git status` clean.

## Decisions & notes

- **`--course`/`--week` are required, not inferred.** §7.4's argument against
  inferring pairings applies doubly to identity: the week id feeds §7.2's stable
  topic ids, and a guessed course slug that changes later would orphan every
  re-emit. Two explicit flags cost less than one silent duplicate week.
- **Confirmation is interactive-only; scripts say `--yes`.** A pairing prompt that
  reads EOF from a pipe would either hang or silently proceed — the exact §7.4
  failure. Non-TTY without `--yes` is a hard error naming the fix.
- **The client seam is `cli._make_client`.** One module-level factory keeps
  `ANTHROPIC_API_KEY` handling and model choice in one place and gives tests a
  single monkeypatch point — the CLI tests exercise the real `cmd_build` code path
  with the recorded fake, per the §8 rule.
- **Cache defaults to `<out>/.cache`.** The cache's whole purpose (§7.1) is the
  regenerate-render tuning loop on one output directory; co-locating it means
  deleting the output tree deletes its cache, and two courses never share keys by
  accident. `--cache-dir` exists for a shared cache if wanted.
- **Dry-run chunking must equal real-run chunking.** Both go through the same
  `merge_chunks` call with the same `--min-words`; §8 calls the dry run the main
  debugging tool, and a debugging tool that shows different chunks than the run it
  debugs is worse than none.
- **`build` writes the week JSON; `render` presents it.** The §6 deliverable is a
  valid `NoteWeek`, and keeping presentation out of `build` preserves the §2
  boundary the whole repo is shaped around — Phase 6's format flag lands on
  `render`, not here.
