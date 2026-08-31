# P0-02 — `model/` types + stable-ID helper
Phase 0 · Depends on: P0-01 · Size: M

## Goal

Implement the note IR from plan §2.2 as pydantic v2 models in `lecturenotes/model/`,
plus the `Capability` enum (§2.3) and the `topic_id()` helper (§7.2), with tests proving
every type instantiates, round-trips through JSON, and rejects malformed input. This
is the contract both halves of the pipeline will be written against, so shape matters
more than speed here.

## Scope

**In**
- `model/nodes.py`, `model/source.py`, `model/notes.py`, `model/capabilities.py`,
  `model/ids.py`, `model/__init__.py` re-exports.
- Unit tests under `tests/model/`.

**Out**
- `degrade()` → Phase 3 (needs a first renderer to degrade *for*). Leave a docstring
  note in `capabilities.py`.
- `Renderer` protocol, `RenderOptions`, `RenderResult`, `Emitter` → `render/base.py`
  and `emit/`, Phase 3.
- Ingest-side types (`Segment`, `Deck`, `SceneChange`, `Chunk`) → Phases 1, 2, 4.
- The hand-written full `NoteWeek` fixture → P0-04 (tests here build small ad-hoc
  instances only).

## Tasks

1. **`model/nodes.py`**
   - `class CalloutKind(StrEnum)`: `EXAM`, `PITFALL`, `UNCERTAIN`, `ASIDE`.
   - A private base `_Node(BaseModel)` with `model_config = ConfigDict(frozen=True, extra="forbid")`.
   - Node classes, each with a `type: Literal["<name>"] = "<name>"` discriminator field:

     | Class | Fields |
     |---|---|
     | `Prose` | `text: str` |
     | `BulletItem` (not a Node) | `text: str`, `children: list[BulletItem] = []` |
     | `BulletList` | `items: list[BulletItem]` (min length 1) |
     | `Definition` | `term: str`, `definition: str` |
     | `Equation` | `latex: str`, `label: str \| None = None` |
     | `CodeBlock` | `code: str`, `language: str \| None = None` |
     | `Callout` | `kind: CalloutKind`, `text: str` |
     | `Figure` | `asset_id: str`, `caption: str \| None = None` |
     | `Table` | `header: list[str]`, `rows: list[list[str]]` — validator: every row has `len(header)` cells |
     | `Quote` | `text: str`, `attribution: str \| None = None` |

   - `Node = Annotated[Prose | BulletList | Definition | Equation | CodeBlock | Callout | Figure | Table | Quote, Field(discriminator="type")]`.
2. **`model/source.py`**
   - `SlideRange(start: int, end: int)` — 1-based, inclusive; validator `1 <= start <= end`.
   - `SourceAnchor(start_s: float, end_s: float, slides: SlideRange | None = None)` —
     validator `0 <= start_s <= end_s`.
   - `SourceRef(video_url: str | None = None, deck_path: str | None = None, caption_path: str | None = None)`.
   - `MediaAsset(id: str, media_type: str, source: str, alt: str | None = None)` —
     `media_type` is a MIME type (`image/png`); `source` is a path or URL the emitter resolves (plan §2.2).
3. **`model/notes.py`**
   - `CardSeed(front: str, back: str, tags: list[str] = [])`.
   - `Topic(id: str, heading: str, anchor: SourceAnchor, body: list[Node], cards: list[CardSeed] = [])`.
   - `NoteLecture(id: str, title: str, overview: str, objectives: list[str], source: SourceRef, topics: list[Topic], glossary: list[Definition] = [], open_questions: list[str] = [], assets: list[MediaAsset] = [])`
     with a `model_validator(mode="after")` that every `Figure.asset_id` in any topic body
     matches an `assets[*].id`, and that asset ids are unique.
   - `NoteWeek(id: str, course: str, week_number: int, lectures: list[NoteLecture])` —
     validator: lecture ids unique within the week.
   - Same `frozen=True, extra="forbid"` config on all of them.
4. **`model/capabilities.py`** — `class Capability(StrEnum)`: `NATIVE_MATH`, `NESTING`,
   `CALLOUTS`, `TABLES`, `IMAGES`, `CODE`. Module docstring: "`degrade()` (plan §2.3)
   will live here from Phase 3."
5. **`model/ids.py`** — `def topic_id(lecture_id: str, slides: SlideRange | None, start_s: float) -> str`:
   returns `f"{lecture_id}:s{slides.start}-{slides.end}"` when `slides` is given, else
   `f"{lecture_id}:t{int(start_s)}"` for slide-less (board-work / gap) topics. Docstring
   quotes plan §7.2 and states the non-goal: ids never derive from list position or heading text.
6. **`model/__init__.py`** — re-export every public name above; `__all__` defined.
7. **Tests, `tests/model/`** (create `tests/model/__init__.py`):
   - `test_nodes.py` — each of the nine node types instantiates with minimal args;
     `Table` with a ragged row raises `ValidationError`; unknown `CalloutKind` raises;
     an extra field raises; nodes are hashable (frozen).
   - `test_roundtrip.py` — build a `NoteLecture` whose topics use **every** node type
     (including a nested `BulletItem`); `NoteLecture.model_validate_json(x.model_dump_json()) == x`;
     the dumped JSON contains all nine `type` discriminator values.
   - `test_validators.py` — `SlideRange(3, 2)` raises; `SlideRange(0, 1)` raises;
     `SourceAnchor(end_s < start_s)` raises; `Figure` referencing an unknown asset id
     inside a `NoteLecture` raises; duplicate lecture ids in a `NoteWeek` raise.
   - `test_ids.py` — with slides → `lec01:s3-5`; without → `lec01:t754`; same inputs
     give same output; different slide ranges give different ids.

## Acceptance criteria

- `uv run pytest tests/model` → all green.
- `uv run mypy` → strict, no issues (pydantic mypy plugin enabled in P0-01).
- `uv run ruff check .` clean.
- `grep -rn "from lecturenotes\|import lecturenotes" lecturenotes/model/` shows only
  `lecturenotes.model.*` imports (the boundary rule, checked by hand until P0-04 automates it).
- `python -c "from lecturenotes.model import *; print(len(__all__))"` succeeds.

## Decisions & notes

- **`Callout.text` is a plain string, not `list[Node]`.** Keeps the union non-recursive
  and `degrade()` simple. Revisit only if Phase 6 (Anki) needs an equation inside a
  callout; that is exactly the kind of flaw plan §6 says to discover there.
- **Timestamps are `float` seconds**, not `timedelta` or ms ints: readable in hand-written
  JSON fixtures, trivially comparable, and VTT/SRT parsing produces them directly.
- **`BulletItem.children` exists deliberately** so `NESTING` degradation (plan §2.3)
  has real input in Phase 3.
- **`assets` live on `NoteLecture`, not `NoteWeek`**, because slide ingest is per
  lecture (plan §7.3) and the validator for `Figure.asset_id` can then be local.
- `frozen=True` everywhere: the pure stages (plan §3) get hashability and safety for
  free; `degrade()` will use `model_copy(update=...)`.
- `extra="forbid"` so a typo in a fixture or an LLM response fails loudly rather than
  silently dropping a field.
