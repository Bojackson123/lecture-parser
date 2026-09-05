# PW-06 — `/api/push` + Side-track W done-gate
Side-track W · Depends on: PW-04, PW-05 · Size: S

## Goal

The last pipeline stage reaches the browser: `POST /api/push` renders a workspace
week with the Notion renderer and delivers it via `emit_notion` — token from the
environment at request time, transport behind the web layer's own seam — then the
side-track closes: done-gate ticked, tickets moved, CLAUDE.md gains its web
invariants section.

## Scope

**In**
- `POST /api/push` `{week_id, parent_page_id}` → `{title, payloads, assets}`;
  `NOTION_TOKEN` unset → 409 with a message naming `NOTION_TOKEN` and `.env`;
  emit failures (missing asset, API error) → 502 `{"error"}`. `asset_root` is the
  workspace (the P5-03 layout — real builds need no override).
- `web/app.py` `_make_transport` seam (the cli twin); Push panel in `static/`.
- CLAUDE.md: "Web GUI (Side-track W)" section; done-gate; ticket moves.

**Out**
- Async push, retries, multi-workspace — out of scope for a loopback tool.

## Tasks

1. Tests first: missing token → 409 naming both `NOTION_TOKEN` and `.env`, no
   transport constructed (a raising seam proves it); with a token in the env and a
   `FakeNotionTransport` via the seam → the P7-04 call sequence (find/create,
   upload, append) and the response counts; a second push reuses the same page id.
2. Implement the endpoint + panel.
3. CLAUDE.md section; tick the done-gate (record the manual browser run); move
   PW-01..06 to `completed/`.

## Acceptance criteria

- Fake-transport push of the week01 fixture (assets staged in the workspace)
  returns `{title: "CS-RL-101 — Week 1", payloads: 1, assets: 1}` and the fake
  records the P7-04 sequence.
- Without `NOTION_TOKEN`: 409, message names `NOTION_TOKEN` and `.env`, seam
  untouched.
- One manual end-to-end browser run recorded in the done-gate: upload → confirm →
  dry-run → build → three previews → push twice, same Notion page updated.
- From a clean checkout: `uv sync --all-groups --all-extras && uv run pytest &&
  uv run ruff check . && uv run mypy && uv run lint-imports` green (5 contracts).

## Decisions & notes

- **Token doctrine is unchanged**: read only in the push handler at request time,
  never a form field, never persisted, never at import — CLAUDE.md's "never a
  `--token` flag" applied to HTTP.
- **Push is synchronous** — seconds of work; a spinner beats job machinery.
- **Automated browser pass run 2026-09-04** (Claude-driven Chrome against a live
  `serve` on a scratch workspace): folder-path pairing showed `lec01`
  pptx+vtt, confirm checkbox gates Build, dry-run table showed 4 chunks (gap
  badge, spans, 81/120/103/103 words) and "5 API request(s)", markdown preview
  rendered every construct with the figure loading via `/ws/` at 240×150, anki
  tab showed the 8-card table, notion tab the payload histogram — zero console
  errors. **Still owed for the done-gate**: the human run with a real
  `ANTHROPIC_API_KEY` build and the double push to a real Notion page.
