# lecturenotes

Turns one week of course material — lecture videos, slide decks, transcripts and
WebVTT captions — into structured study notes, with output format kept pluggable behind
a single note IR. The design, pipeline stages and build phases are in
[`PROJECT_PLAN.md`](PROJECT_PLAN.md); work items are in [`tickets/`](tickets/README.md).

## Checks

```
uv sync --all-groups
uv run pytest
uv run ruff check .
uv run mypy
uv run lint-imports
```
