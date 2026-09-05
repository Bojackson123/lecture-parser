# P7-01 — Notion payload spec + hand-written expected fixture
Phase 7 · Depends on: P6-03 · Size: M

## Goal

Make every Notion format decision before any renderer code exists — the P6-01 move,
repeated: commit `tests/fixtures/notes/week01.notion.json`, a hand-written rendering
of the `week01` fixture as one Notion page payload, and it becomes the format spec
P7-02 implements to byte-equality. The JSON shape decided here is also the
renderer↔emitter contract: P7-04's emitter posts these payloads verbatim, so the two
tickets that follow this one can proceed in parallel against the same file. Nothing
in `lecturenotes/` changes.

## Scope

**In**
- `tests/fixtures/notes/week01.notion.json`, hand-written.
- Sanity tests in `tests/render/test_notion_fixture.py` (fixture-level only — no
  renderer exists yet).
- `tests/fixtures/README.md` row pointing the fixture at its consumers.

**Out**
- `render/notion.py` → P7-02. The four Notion limits → P7-03 (the fixture sits far
  below all of them by design; nothing here encodes a limit).
- `emit/notion_api.py`, page identity, uploads → P7-04. The fixture carries an
  asset *placeholder*; resolving it is the emitter's job (plan §2.2).
- Any change to `week01.json`, `week01.md`, `week01.anki.txt`, `model/` or prompts —
  Phase 6 established the IR is sound; this ticket only maps it.

## Tasks

1. **Decide and write the payload shape** at the top of the fixture:
   - One document, named `{week.id}.notion.json` → `cs-rl-101-w01.notion.json`
     (the §7.2 stable-name pattern; the name lives in P7-02's renderer, but record
     it here with the spec).
   - Top level: `{"page": {"title": "CS-RL-101 — Week 1"}, "payloads": [[block,
     …], …]}` — each payload is one `children` array for one Notion append request,
     each block a Notion API block object verbatim. `week01` is small: exactly one
     payload.
   - Title is built from `course` + `week_number`, never from lecture titles —
     stable under regeneration, which is what P7-04 keys update-not-duplicate on.
2. **Map every construct** (the fixture's 2 lectures / 6 topics cover all 9 node
   types, so every rule below is exercised at least once):
   - Lecture → `heading_1` (title), overview `paragraph`, objectives as
     `bulleted_list_item`s; glossary and open questions as trailing `heading_2`
     sections, mirroring `week01.md`'s structure.
   - Topic → `heading_2` whose rich text is the heading plus a separate
     gray-annotated run carrying the citation — the exact `format_clock` string,
     then ` · slide N` / ` · slides N–M` (en-dash) / nothing for a slide-less
     topic, the P6-01 citation grammar.
   - `Prose` → `paragraph`. `BulletList` → `bulleted_list_item`s, `children` for
     nesting. `Definition` → `paragraph` with a bold term run, then `: ` + text.
     `Equation` → `equation` block, LaTeX as the KaTeX `expression`. `Callout` →
     `callout` with a kind→icon/colour map — pick and pin one emoji + colour per
     kind (EXAM, PITFALL, UNCERTAIN, ASIDE); presentation is decided here,
     downstream of the IR (plan §2.2). `CodeBlock` → `code` with `language`.
     `Quote` → `quote`. `Table` → `table` + `table_row`s, header row flagged.
   - `Figure` → `image` block holding `{"type": "asset_placeholder",
     "asset_placeholder": {"asset_id": …}}` — no URL, no path; the emitter resolves
     it (plan §2.2: *assets are resolved by the emitter*). Caption in the image
     caption rich text.
   - `CardSeed`s ignored — document renderers ignore cards (plan §2.2).
   - **Math dialect** (the renderer-local P6 parallel): paired `$…$` inside prose,
     bullet, cell and definition text becomes an inline `equation` rich-text run;
     unpaired `$` passes through as text; citations are never translated. The
     fixture must contain at least one inline translation.
3. **`tests/render/test_notion_fixture.py`** — sanity pins on the file itself:
   - parses as JSON; top level is exactly `page` + `payloads`; one payload.
   - every topic's `format_clock(topic.anchor.start_s)` appears in the serialized
     text (property 4's grep will hit this file).
   - exactly one `asset_placeholder`, and its `asset_id` is the `week01` figure's.
   - no `\r` anywhere; file ends with exactly one `\n`; UTF-8, en-dashes intact.
4. **`tests/fixtures/README.md`**: add the row — "`notes/week01.notion.json` —
   hand-written Notion payload spec; byte-equality target of
   `tests/render/test_notion.py` (P7-02), payload contract for
   `emit/notion_api.py` (P7-04). Never regenerated from the code under test."
5. Run the full check suite and commit.

## Acceptance criteria

- `uv run pytest` → all green, including the new fixture sanity tests; `uv run ruff
  check .`, `uv run mypy`, `uv run lint-imports` clean.
- `uv run python -c "import json; d = json.load(open('tests/fixtures/notes/week01.notion.json', encoding='utf-8')); print(sorted(d), len(d['payloads']))"`
  prints `['page', 'payloads'] 1`.
- `git diff --stat HEAD~1 -- tests/fixtures/notes/week01.md tests/fixtures/notes/week01.anki.txt tests/fixtures/notes/week01.json`
  is empty — the existing fixtures are untouched.
- `git status` clean.

## Decisions & notes

- **One page per week, H1 per lecture** (decided with the user, 2026-09-04). §7.3
  leaves page granularity to the renderer; one page mirrors the markdown renderer
  and leaves P7-04 exactly one page identity to manage. A child-page-per-lecture
  layout would double the fixture and the emitter's find/replace surface for
  navigation polish nobody has asked for.
- **Blocks are Notion API shapes verbatim, one payload = one append request.** The
  emitter must be able to POST without transforming (bar the asset placeholder),
  because every transformation it made would be format knowledge leaking out of the
  renderer — the drift `asset_target` exists to prevent, applied to Notion.
- **The placeholder is the one deliberate non-Notion shape in the file.** A real
  URL or upload id cannot be known at render time without IO, and renderers are
  pure (P3-01). The emitter swaps it for a `file_upload` reference after uploading
  (P7-04); the placeholder type name is chosen so a payload accidentally posted
  unresolved fails loudly at Notion's validator, not silently as a broken link.
- **This file is hand-written and never regenerated** — the same doctrine as
  `week01.md` and `week01.anki.txt`: it is the format spec, not a snapshot. If the
  format changes on purpose, edit the file deliberately.
- **The fixture stays far below every §2.3 limit on purpose.** Limits are P7-03's
  job, pinned by ad-hoc and property tests; encoding them into this fixture would
  couple the spec of the *format* to the spec of the *caps* and make both harder to
  read. P7-03 asserts this file is byte-unchanged by the limits work.
