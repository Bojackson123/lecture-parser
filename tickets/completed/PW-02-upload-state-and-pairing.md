# PW-02 — Workspace state, upload, pairing preview + Files/Pairing panels
Side-track W · Depends on: PW-01 · Size: M

## Goal

The browser can get files to the server and see exactly the pairing `build` would
run: `/api/state` lists the workspace's week JSONs and the current job, `/api/upload`
stores a week's decks and captions under a managed uploads directory, and
`/api/pair` returns the §7.4 sorted-filename pairing (or the `collect_pairs` error
verbatim). The Files and Pairing panels land in the UI, with the explicit
confirmation checkbox that later gates the Build button.

## Scope

**In**
- `GET /api/state` → `{workspace, weeks, job}`; weeks are top-level `*.json` files
  validated as `NoteWeek` (id/lectures/topics counts), invalid ones flagged with
  their error, never hidden.
- `POST /api/upload?week=<slug>` (multipart) → files stored at
  `<workspace>/uploads/<slug>/<name>`; bare filenames with a known suffix
  (.pdf/.pptx/.vtt/.srt) only, else 400; overwrite in place (real names matter —
  sorted-filename pairing).
- `POST /api/pair` `{paths}` → `{pairs}` via `pairing.collect_pairs`; `ValueError`
  → 422 `{"error": <message verbatim>}`. Relative paths resolve against the
  workspace.
- UI: drag-drop upload zone + server-folder-path field feeding one `paths` list;
  pairing table with the §7.4 warning line and the confirm checkbox.

**Out**
- Chunk preview → PW-03. Build → PW-04. Rendering existing weeks → PW-05.

## Tasks

1. Tests first (`tests/web/`): state on an empty workspace; state listing the
   week01 fixture with counts; an invalid JSON flagged; upload stores bytes
   byte-equal; traversal / bad-suffix names → 400; pair returns `lec01` for the
   fixture pair; mismatch → 422 with the exact `collect_pairs` message.
2. Implement the three endpoints in `web/app.py` (pydantic request/response
   models; `{"error": msg}` error shape).
3. Files + Pairing panels in `static/`.

## Acceptance criteria

- Uploading `lecture01.pptx` + `lecture01.vtt` then pairing their paths returns
  one pair `lec01`; the stored bytes equal the originals.
- Pairing one deck and zero captions returns 422 whose message is exactly what
  `lecturenotes build` prints for the same inputs.
- `..`-carrying or unknown-suffix upload names are rejected with 400 and nothing
  is written.

## Decisions & notes

- **Paths are strings resolved against the workspace when relative** — uploads
  return workspace-relative POSIX paths, the folder field may be absolute; both
  feed the same `collect_pairs`.
- **No stem matching, ever** — the endpoint exposes `collect_pairs` as-is; a wrong
  pairing must be visible, not papered over (§7.4).
