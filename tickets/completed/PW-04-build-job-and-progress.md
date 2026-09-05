# PW-04 — Build job: `jobs.py`, `ProgressClient`, `/api/build` + `/api/job`
Side-track W · Depends on: PW-03 · Size: L

## Goal

The real build runs from the browser with visible progress: `POST /api/build`
starts one background job (a daemon thread running the exact `cmd_build` real-run
composition), `GET /api/job` reports `done/total` ticks — one per LLM `complete()`,
totals known after `merge_chunks` — and the §7.4 confirmation survives as an echo
check: the request carries the pairing the user confirmed and the server rejects it
if it differs from what it would actually run.

## Scope

**In**
- `web/jobs.py`: `JobStatus`, `JobManager` (one live job behind a lock; last
  finished job kept), `ProgressClient` (an `LLMClient` wrapper: proxies `model`,
  records `request.key`, ticks `done` after each `complete`).
- `POST /api/build` `{paths, course, week, min_words, model, pairs}` → 202
  `{job_id}`; pairing mismatch/absent → 400; job already running → 409 naming it.
- `GET /api/job` → `JobStatus` (404 before any job). UI: progress bar + result.
- Worker: per pair ingest → align (chunks computed once, reused for the total) →
  `generate_lecture(..., client=ProgressClient(CachedClient(_make_client(model),
  workspace/".cache", PROMPT_VERSION), ...), out_dir=workspace)`; writes
  `<workspace>/<week_id>.json` with the `cmd_build` UTF-8+LF bytes convention.

**Out**
- Cancellation — threads can't kill a blocking SDK call; documented as "wait or
  restart the server". A cooperative between-completes cancel is a follow-up.
- Rendering/push of the result → PW-05/PW-06.

## Tasks

1. Tests first (`tests/web/`): recorded-fake job (seam returns
   `RecordedClient(lecture01.responses.json)`) reaches `done` with progress 0→5
   and writes `cs-rl-101-w01.json` that `lecturenotes render` accepts; `pairs`
   mismatch → 400 and no job; second build while one runs → 409; a gated client
   (threading.Event) pins the running state and mid-progress counts with **no
   sleeps**; a counting client pins exactly 5 requests (§7.1 budget).
2. Implement `jobs.py` + the two endpoints; `ProgressClient` wraps the cache
   **outermost** so cache hits tick instantly.
3. Build panel in `static/` (500 ms polling while running).

## Acceptance criteria

- The fake-driven job writes a week JSON `render` accepts, with `total == 5` and
  `done == 5` at the end — no sleep in any test.
- `/api/build` without a matching `pairs` echo returns 400 and starts nothing.
- A second build during a running one returns 409 with the live job's id.

## Decisions & notes

- **The confirm click confirms exactly what will run**: the server recomputes
  `collect_pairs(paths)` and compares with the echoed pairing — §7.4 in HTTP form;
  no `--yes` analogue exists in the API.
- **`ProgressClient` sits outside `CachedClient`** so a fully cached rebuild
  races through the bar instead of looking stuck.
- **One job at a time** — the tool is single-user; queueing would add state for no
  workflow.
