# PW-05 — Review panel: `/api/render`, `/ws/` media serving, previews
Side-track W · Depends on: PW-01 (parallel to PW-02..04) · Size: M

## Goal

The §7.1 tuning loop works in the browser without rebuilding: pick any week JSON in
the workspace, render it with any of the three renderers in-process (pure, free),
and see it — markdown as a formatted page with figures displaying, anki as a card
table, notion as a payload summary. `/ws/` serves workspace files read-only so
`media/` images resolve in the preview.

## Scope

**In**
- `GET /api/render?week=<id>&format=markdown|anki|notion` →
  `RenderResult.model_dump()`; `<id>` is the JSON's filename stem, no separators;
  unknown week → 404, invalid JSON → 422.
- `GET /ws/<relpath>` → file bytes; resolved path must stay under the workspace
  (403 otherwise); images/JSON/text only; no directory listings.
- Review panel: week dropdown (from `/api/state`), format tabs; `mdToHtml()` in
  `app.js` (~80 lines, exactly the closed construct set `MarkdownRenderer` emits —
  pinned by the hand-written `week01.md` spec; `$$…$$` stays literal in v1) with
  `media/` srcs rewritten to `/ws/…`; anki TSV parsed into a table (6 header lines
  skipped); notion as title + payload/block counts + collapsible raw JSON.

**Out**
- A fourth renderer, or any HTML renderer in `render/` — the preview is UI-local,
  like each target's math dialect.
- Writing anything — `/ws/` and `/api/render` are read-only.

## Tasks

1. Tests first: `/api/render` output equals the CLI `render --json` output per
   format for the week01 fixture placed in a tmp workspace; unknown week → 404;
   `/ws/` serves a placed PNG byte-equal; `..` traversal → 403.
2. Implement both endpoints (renderer table mirrors `cli._RENDERERS`' three
   entries — pinned equal by a test).
3. Review panel + `mdToHtml` in `static/`.

## Acceptance criteria

- `/api/render?week=week01&format=anki` equals `lecturenotes render
  tests/fixtures/notes/week01.json --format anki --json` — likewise markdown and
  notion.
- A `/ws/` request resolving outside the workspace returns 403 — pinned by a test.
- The fixture figure displays in the markdown preview (manual check, recorded in
  PW-06's gate).

## Decisions & notes

- **Weeks are addressed by filename stem**, not the `NoteWeek.id` field — file
  addressing can't be ambiguous and needs no index.
- **`mdToHtml` parses our own renderer's output only** — a closed subset with a
  committed spec, which is why a bespoke 80-line function is safe where a general
  markdown parser would not be.
