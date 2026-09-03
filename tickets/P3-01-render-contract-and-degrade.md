# P3-01 — `render/base.py` contract types, `degrade()`, contract tests retyped
Phase 3 · Depends on: P2-04 · Size: M

## Goal

Create `lecturenotes/render/base.py` (plan §5) with the render-side contract of plan
§2.3 — the `Renderer` protocol, `RenderOptions`, `RenderedDocument`, `RenderResult`,
the shared `asset_target()` path helper — and move `format_clock` there from `cli.py`,
because the anchor-survival contract test pins it as the one timestamp format every
renderer must surface. Fill the spot reserved in `model/capabilities.py` (its docstring
says so) with `degrade(week, capabilities)` and `constructs_used(week)`, so degradation
is declared once, not improvised per renderer. Retype `tests/contract/test_renderers.py`
(`RENDERERS: list[Renderer]`, still empty, still skipping) and implement its four
properties, so P3-02 only has to register a renderer and watch them go green. The
contract goes first because both P3-02 (renderer) and P3-03 (emitter) build against
these types and can then proceed in parallel.

## Scope

**In**
- `lecturenotes/render/base.py`: `Renderer` protocol, `RenderOptions`,
  `RenderedDocument`, `RenderResult`, `asset_target`, `format_clock`.
- `degrade` and `constructs_used` in `lecturenotes/model/capabilities.py`, exported
  from `model/__init__.py`.
- `tests/model/test_degrade.py`; the four properties in
  `tests/contract/test_renderers.py`.
- `cli.py`: `format_clock` becomes an import from `render.base` — no behaviour change,
  existing CLI tests stay green.

**Out**
- Any concrete renderer → P3-02. The emitter and all IO → P3-03. Import-linter
  additions → P3-03 (the ticket that creates emit code). CLI changes beyond the
  moved import → P3-04.
- New `Capability` members or IR node types — the six existing members cover the nine
  existing nodes; Phase 6 adds more only when Anki forces it (plan §10).

## Tasks

1. **`tests/model/test_degrade.py` first** (red on `ImportError`), against the `week01`
   fixture from `tests/conftest.py`:
   - For each single capability `X`: `constructs_used(degrade(week01, ALL - {X}))`
     does not contain `X`, where `ALL = set(Capability)`.
   - Parametrised over **all 64 subsets** `C` of `Capability` (`itertools` — cheap and
     deterministic, no hypothesis needed): `constructs_used(degrade(week01, C)) <= C`,
     and the result is a valid `NoteWeek` (pydantic re-validates on construction; assert
     `NoteWeek.model_validate_json(result.model_dump_json()) == result`).
   - Identity: `degrade(week01, ALL) == week01`.
   - Idempotence: `degrade(degrade(week01, C), C) == degrade(week01, C)` for a few
     representative `C` (empty set, `{NESTING}`, `ALL - {NATIVE_MATH, CODE}`).
   - Per-rewrite spot checks on `week01`: no `NATIVE_MATH` turns the `bellman` equation
     into `CodeBlock(language="latex", code=BELLMAN_LATEX)`; no `NESTING` flattens the
     discount-factor bullet's two children into siblings directly after their parent;
     no `CALLOUTS` yields `Prose(text="EXAM: Write the Bellman equation down …")`; no
     `TABLES` turns the term table into a `BulletList` whose first item is
     `Term | Meaning`; no `IMAGES` yields
     `Prose(text="[figure: Maximum change between successive sweeps …]")` and leaves
     `lecture.assets` untouched; no `CODE` turns the value-iteration block into `Prose`
     with the code verbatim.
   - Cards, glossary, open questions, anchors and topic ids are unchanged by any
     degradation.
2. **`constructs_used(week: NoteWeek) -> set[Capability]`** in `model/capabilities.py`:
   walk every topic body (and nested `BulletItem.children`); the capability↔construct
   map, defined once here and nowhere else:

   | Capability | Construct |
   |---|---|
   | `NATIVE_MATH` | any `Equation` |
   | `NESTING` | any `BulletItem` with non-empty `children` |
   | `CALLOUTS` | any `Callout` |
   | `TABLES` | any `Table` |
   | `IMAGES` | any `Figure` |
   | `CODE` | any `CodeBlock` |

   `Prose`, flat `BulletList`, `Definition` and `Quote` map to no capability — they are
   the floor every renderer must handle. Glossary entries are lecture metadata, not body
   nodes, and are not counted.
3. **`degrade(week: NoteWeek, capabilities: set[Capability]) -> NoteWeek`**: pure —
   returns a new week, never mutates (the nodes are frozen anyway). Rewrites applied in
   a fixed cascade so later steps catch earlier steps' output, which is what makes
   `constructs_used(result) <= capabilities` hold for every subset:
   1. no `NATIVE_MATH`: `Equation(latex, label)` → `CodeBlock(language="latex",
      code=latex)` (plan §2.3; the label is dropped — it is an IR cross-reference
      handle, not content).
   2. no `TABLES`: `Table` → `BulletList`, one item per row, cells joined with ` | `
      (the join P2-01 chose for slide tables), header as the first item.
   3. no `NESTING`: flatten `BulletItem.children` pre-order into siblings — parent,
      then its children, recursively; order preserved, no prefix decoration. Runs after
      the `TABLES` step so any list it created is already covered (table rows are flat,
      but the cascade must not depend on that).
   4. no `CALLOUTS`: `Callout(kind, text)` → `Prose(text=f"{kind.value}: {text}")` —
      the kind survives as text, the presentation is gone.
   5. no `IMAGES`: `Figure(asset_id, caption)` →
      `Prose(text=f"[figure: {caption or alt or asset_id}]")`, `alt` looked up in the
      owning lecture's `assets`. Assets stay on the lecture — an unreferenced asset is
      not an output construct, and stripping it would make degradation lossy for no
      reason.
   6. no `CODE`: `CodeBlock(code, language)` → `Prose(text=code)`, language dropped —
      catching the latex blocks step 1 produced.

   **Inline `$...$` in `Prose`, `BulletItem.text`, `Table` cells and `Definition` text
   is never rewritten.** It is plain text, readable anywhere; re-parsing prose for
   dollar signs is exactly the markdown-as-IR mistake plan §2.1 warns against.
4. **`render/base.py`** — imports `model` only (the `render never imports ingest`
   contract starts biting the moment this file exists):
   - `format_clock(seconds: float) -> str`, moved verbatim from `cli.py` (`m:ss`, or
     `h:mm:ss` past an hour; whole seconds, floored); `cli.py` imports it from here
     (cli → render is a legal direction; duplicating it would fork the one format the
     contract test greps for).
   - `class RenderOptions` — frozen pydantic model (`ConfigDict(frozen=True,
     extra="forbid")`), **no fields**. It exists so the §2.3 signature never churns;
     it grows knobs only when a renderer needs one.
   - `RenderedDocument(name: str, text: str)` — frozen; validator: `name` is a
     relative POSIX path (non-empty, no backslash, no leading `/`, no `..` segment).
   - `RenderResult(documents: tuple[RenderedDocument, ...],
     assets: tuple[MediaAsset, ...])` — frozen; validators: document names unique,
     asset ids unique. `assets` is the manifest of assets the output actually
     references — the emitter resolves exactly these (plan §2.3).
   - `asset_target(asset: MediaAsset) -> str`: `f"assets/{asset.id}{ext}"`, `ext` from
     an explicit `media_type` map (`image/png` → `.png`, `image/jpeg` → `.jpg`,
     `image/gif` → `.gif`, `image/svg+xml` → `.svg`); unknown `media_type` →
     `ValueError` naming the asset id and type — fail loudly rather than write an
     extension-less file. Renderers build links with it; the filesystem emitter writes
     to it (P3-03) — one helper, so the two can never drift.
   - `class Renderer(Protocol)`: `name: str`; `capabilities: set[Capability]`;
     `def render(self, week: NoteWeek, opts: RenderOptions) -> RenderResult`.
5. **`tests/contract/test_renderers.py`**: retype `RENDERERS: list[Renderer]` (still
   `[]`, the skip param stays) and replace the `NotImplementedError` body with the four
   properties, one test each, parametrised over `RENDERERS`:
   - *renders without raising*: `renderer.render(week01, RenderOptions())` succeeds on
     the full, undegraded fixture.
   - *respects declared capabilities*, IR-level:
     `degraded = degrade(week01, renderer.capabilities)`;
     `constructs_used(degraded) <= renderer.capabilities`; and the renderer renders
     `degraded` without raising. (Output-level checks cannot be generic across
     renderers; the IR-level check is, and it bites for real when Anki and Notion
     declare fewer than six.)
   - *deterministic*: rendering the same week twice yields equal `RenderResult`s.
   - *every `SourceAnchor` survives*: for every topic of every lecture,
     `format_clock(topic.anchor.start_s)` appears in the concatenation of all
     `document.text`s.
6. Run the full check suite and commit in two steps: the degrade and contract tests
   first (red on `ImportError`), then the implementation.

## Acceptance criteria

- `uv run pytest` → all green (the contract test still shows 4 skips — no renderer
  yet); `uv run ruff check .`, `uv run mypy`, `uv run lint-imports` clean.
- `uv run python -c "from lecturenotes.model import Capability, constructs_used, degrade; from tests.fixtures.notes.week01 import week01; print(sorted(constructs_used(degrade(week01(), set()))))"`
  prints `[]`.
- `uv run python -c "from lecturenotes.model import Capability, constructs_used; from tests.fixtures.notes.week01 import week01; print(len(constructs_used(week01())))"`
  prints `6`.
- `uv run python -c "from lecturenotes.render.base import asset_target; from lecturenotes.model import MediaAsset; print(asset_target(MediaAsset(id='fig-x', media_type='image/png', source='s')))"`
  prints `assets/fig-x.png`.
- `uv run lecturenotes captions tests/fixtures/captions/lecture01.vtt | head -1` still
  prints `[0:01–0:26] Welcome to CS-RL-101.` (format_clock moved, not changed).
- `grep -c "def format_clock" lecturenotes/cli.py` prints `0`.
- `git log` shows the tests committed before (or together with, but never after) the
  implementation; `git status` clean.

## Decisions & notes

- **`degrade()` takes a `set[Capability]`, never a `Renderer`.** It lives in `model/`
  (the reserved spot) and the import-linter contract forbids `model` → `render`, so the
  protocol cannot appear in its signature. This is the boundary working as designed,
  not a workaround.
- **The capability↔construct map is defined once**, in `constructs_used`, and the
  contract test's property 2 is expressed against it. Adding a node type without
  deciding its capability now fails a test instead of silently rendering wrong.
- **Prose, flat `BulletList`, `Definition` and `Quote` are the floor.** No capability
  guards them; every renderer must handle them. A renderer that cannot (Anki, perhaps,
  for `Quote`) is a Phase 6 discovery that adds a capability then — plan §10, let the
  breakage be found, don't pre-build for it.
- **The cascade order (math → tables → nesting → callouts → images → code) is load-
  bearing**: math-degradation emits code blocks and table-degradation emits lists, so
  code- and nesting-degradation must run later or the subset property fails. The
  all-64-subsets test exists to pin exactly this.
- **Inline `$...$` is never rewritten** — degradation operates on nodes, not on prose
  content. A target that cannot show a dollar-sign formula readably still shows it
  legibly as text; re-parsing prose is the §2.1 mistake.
- **Equation labels are dropped on degradation.** Nothing references them yet; when a
  cross-reference feature exists, it will need its own capability and can revisit.
- **Property 2 is IR-level, property 4 is output-level.** "No unsupported construct in
  the output" cannot be checked generically on arbitrary bytes; "the timestamp string
  appears" can, for any text-bearing format including a JSON-serialised Notion payload.
  Property 4 is why `format_clock` moved to `render/base.py`: **every renderer must
  surface anchors through it** — that is now a contract-level rule.
- **`RenderOptions` ships empty on purpose.** The §2.3 signature is honoured from day
  one and never churns; the alternative — inventing options nobody consumes — is how
  dead config is born. The one-page-or-several decision (plan §7.3) is a P3-02
  renderer decision, not an option.
- **`RenderResult.documents` is a tuple even though markdown emits one document.**
  The type is the contract for all renderers; Anki emits per-card structures and
  Notion may page. `text: str` covers v1; Phase 7 widens it to bytes-or-structure
  when a renderer actually produces one (plan §2.3) — mypy will find the callers.
