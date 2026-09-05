# PW-03 — Dry-run chunk preview (`/api/dry-run`) + chunk-table panel
Side-track W · Depends on: PW-02 · Size: S

## Goal

The browser shows exactly the chunking the real run would prompt over, before any
money is spent: `POST /api/dry-run` ingests, aligns and merges each pair with the
same `merge_chunks` call and floor as `cmd_build`, returning a chunk table (slide
range or gap, time span, word count, slide title) plus `total_requests` — the §7.1
budget (merged chunks + 1 synthesis per lecture) — so cost is visible up front.

## Scope

**In**
- `POST /api/dry-run` `{paths, min_words=100}` → `{lectures: [{lecture_id,
  chunks: [{slides|null, start_s, end_s, words, title, gap}]}], total_requests}`;
  ingest/align errors → 422 `{"error"}`.
- Chunk-preview panel: table with a gap badge for `slides=None` chunks, clock
  spans, word counts, and the total request count.

**Out**
- Starting a job → PW-04. Alignment knobs (`--min-gap-s`/`--min-silence-s`) stay
  on the `align` CLI command — the GUI exposes only `min_words`, like `build`.

## Tasks

1. Tests first: fixture pptx+vtt → 4 chunks, exactly one `gap: true` with
   `slides: null`, `total_requests == 5`, word counts matching the P5-02 fixture
   weights (81/120/103/103) — all with a raising `_make_client` seam armed and
   `ANTHROPIC_API_KEY` deleted (the `no_client` doctrine, ported to `web.app`);
   `min_words=200` merges the slide chunks and the gap fences.
2. Implement the endpoint; reuse the ingest→align→merge composition verbatim.
3. Chunk panel in `static/`.

## Acceptance criteria

- The fixture pair returns 4 chunks and `total_requests == 5` while any client
  construction raises — pinned by a test.
- A missing file returns 422 with the underlying message, no traceback.

## Decisions & notes

- **Dry-run spends nothing** is a hard invariant, not a hope: the endpoint never
  touches `_make_client`, `CachedClient` or the environment — same guarantee as
  `cmd_build --dry-run` (P5-04), enforced by the same style of test.
- **`words` uses the same count as the merge floor** (whitespace split per
  segment), so the numbers the user sees explain the merges they get.
