# P7-04 — Notion emitter: transport seam, fake, `emit_notion()`
Phase 7 · Depends on: P7-01 · Size: L

## Goal

Create `lecturenotes/emit/notion_api.py` (plan §5), the second emitter: take a
`RenderResult` holding a P7-01 payload document and deliver it to a real Notion
workspace — find or create the week's page, resolve asset placeholders by uploading,
append the payloads — with §7.2's update-not-duplicate holding at the page level: a
re-emit updates the same page at the same URL, never creates a sibling. All IO goes
through a `NotionTransport` seam with an in-package fake (the P5-01 client pattern),
so no test touches the network (plan §8) and the suite exercises every sequence the
emitter can produce. Independent of P7-02/P7-03: the tests hand-build `RenderResult`
values from the P7-01 spec and never import a renderer — the P3-03 doctrine, reused.

## Scope

**In**
- `lecturenotes/emit/notion_api.py`: `NotionTransport` (protocol),
  `FakeNotionTransport`, `UrllibTransport`, `emit_notion()`.
- `tests/emit/test_notion_api.py`.

**Out**
- Any import of `render.notion` or the IR — the emitter consumes `RenderResult`
  and the P7-01 JSON contract only. (No pyproject change: the P3-03 emit contract
  already fences `ingest`/`align`/`generate`.)
- CLI wiring, `NOTION_TOKEN` handling, `--parent` → P7-05. Nothing in this module
  reads the environment.
- Block-level diffing, preserving Notion comments across re-emits, rate-limit
  retry/backoff → not until someone needs them (see Decisions).
- A live-Notion test — the real transport is exercised once, manually, in P7-05's
  done-gate.

## Tasks

1. **`tests/emit/test_notion_api.py` first** (red on `ImportError`), hand-building
   `RenderResult`s whose single document is P7-01-shaped JSON, against
   `FakeNotionTransport`:
   - **Fresh emit**: with no existing page, the recorded call sequence is
     `find_child_page` (miss) → `create_page` → one `upload_file` per referenced
     asset → `append_children` once per payload, in payload order, against the new
     page id.
   - **Re-emit**: with the page existing under the parent, the sequence is
     `find_child_page` (hit) → `list_children` → `archive_block` per existing
     child → uploads → appends — and **no `create_page`**: same page id, nothing
     duplicated (§7.2 at the page level).
   - **Placeholder resolution**: the appended blocks are the document's blocks
     verbatim except each `asset_placeholder` became
     `{"type": "file_upload", "file_upload": {"id": …}}` with the id
     `upload_file` returned for that asset; the uploaded bytes are the file at
     `asset_root / asset.source`, read once per asset.
   - An empty manifest calls `upload_file` never; a manifest asset whose `source`
     doesn't exist raises `FileNotFoundError` naming the asset id, before any page
     mutation (fail before touching Notion, not mid-write).
   - A placeholder whose `asset_id` is in no manifest entry raises `ValueError`
     naming the id — a renderer bug surfacing loudly, per the manifest contract.
   - Two payloads append in order (the fake records ordering).
   - The test file imports only `emit.notion_api`, `render.base` and `model` —
     never a renderer; nothing reads env vars.
2. **`NotionTransport`** — a `Protocol` with the six calls the emitter needs and
   nothing more: `find_child_page(parent_id, title) -> str | None`,
   `create_page(parent_id, title) -> str`, `list_children(block_id) -> list[str]`,
   `archive_block(block_id) -> None`,
   `append_children(block_id, children) -> None`,
   `upload_file(name, media_type, data) -> str`.
3. **`FakeNotionTransport`** — in the package, like `RecordedClient` (P5-01):
   holds a dict of existing pages, records every call with its arguments, mints
   deterministic ids.
4. **`emit_notion(result: RenderResult, transport: NotionTransport, *,
   parent_page_id: str, asset_root: Path = Path(".")) -> None`**:
   - parse the one `.notion.json` document (`json.loads` — the P7-01 contract;
     zero or multiple `.notion.json` documents is a `ValueError`);
   - read + upload manifest assets first, building the id→file_upload map;
   - find-or-create the page by exact `page.title` under `parent_page_id`;
     on find: list and archive its children;
   - substitute placeholders, append payloads in order;
   - no return value — stage 8 is side effects (plan §3); tests inspect the fake.
5. **`UrllibTransport`** — the real thing on stdlib `urllib.request` (decided with
   the user, 2026-09-04: no new dependency): token and Notion-Version header set
   in the constructor (the token is a parameter — this module never reads the
   environment); JSON requests for the five block/page calls; the File Upload API
   (create upload, then multipart send — hand-rolled, ~15 lines) for
   `upload_file`; any non-2xx raises with status and response body in the message.
   Thin and dumb — every branch worth testing lives above the seam.
6. Run the full check suite and commit in two steps: tests first, then the
   implementation.

## Acceptance criteria

- `uv run pytest` → all green with no network access and no `NOTION_TOKEN` set
  anywhere in the environment.
- `uv run ruff check .`, `uv run mypy`, `uv run lint-imports` clean —
  `lint-imports` still reports **4 contracts, 0 broken** (no new contract needed;
  the emit fence already exists).
- `uv run python -c "from lecturenotes.emit.notion_api import FakeNotionTransport, emit_notion; print('ok')"`
  prints `ok` — importable with no key, no network (the P5-01 doctrine).
- `grep -c "os.environ" lecturenotes/emit/notion_api.py` prints `0`.
- `git log` shows tests committed before (or with, never after) the
  implementation; `git status` clean.

## Decisions & notes

- **Title is the page identity.** The title derives from `course` + `week_number`
  (P7-01), which prompt tuning, model switches and regeneration never change — the
  actual §7.2 requirement. Renaming the course is deliberately a new page, the
  same shape as P6-02's "a reworded front is a new card": identity comes from the
  stable coordinates, and changing those coordinates *should* fork. No local state
  file, no marker block — the page you can see is the whole truth.
- **Replace-children, not block-diff.** Archive-then-append keeps the page id and
  URL stable — the §7.2 property a user can observe — at the cost of losing
  block-level history and comments on re-emit. A diff would need stable block
  identities the payload format doesn't carry; building that before anyone has
  commented on a generated page is speculation. Recorded so the limitation is a
  decision, not an oversight.
- **Upload before mutate.** Assets are read and uploaded before the page is
  found-or-created, so a missing file on disk aborts with the page untouched. A
  half-written page is the emitter's worst failure mode; ordering is the cheap
  fix.
- **The fake is a stateful recorder, not a mock framework.** Sequence assertions
  read `transport.calls`; the create-vs-replace branch is driven by seeding pages.
  Same reasoning as `RecordedClient`: the seam is the test surface, and the suite
  must stay hermetic.
- **`asset_root` is a keyword with a cwd default**, exactly as in P3-03 and for
  the same reason: `MediaAsset.source` is relative and the emitter must not guess
  to what. P7-05's `push` passes the week JSON's directory (the P5-03 rule).
