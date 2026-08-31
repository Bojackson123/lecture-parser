# P2-01 — `Deck`/`Slide` types, expected-deck fixture, PPTX parsing, `ingest_slides()`
Phase 2 · Depends on: P1-04 · Size: M

## Goal

Create `lecturenotes/ingest/slides.py` (plan §5) with the ingest-side deck types P0-02
deferred to this phase — `Deck`, `Slide`, `TextBlock`, `SlideImage` — plus `clean_line`,
`parse_pptx` and the composing entrypoint `ingest_slides(path)` (PPTX only until P2-02
registers `.pdf`). The hand-written expected output
`tests/fixtures/decks/lecture01.deck.json` — the slide-side twin of
`captions/lecture01.segments.json` — is committed **first**, and the PPTX half of the
Phase 2 done-criterion (plan §6: titles + bullets + speaker notes) becomes one snapshot
test against it. PPTX goes first because python-pptx hands over the structure the PDF has
to reconstruct: title placeholder, body placeholders in order, paragraphs, notes, pictures.

## Scope

**In**
- `lecturenotes/ingest/slides.py`: `Deck`, `Slide`, `TextBlock`, `SlideImage`,
  `DeckParseError`, `clean_line`, `image_id`, `parse_pptx`, `ingest_slides`.
- `tests/fixtures/decks/lecture01.deck.json` (hand-written, before any parser code).
- `tests/ingest/test_pptx.py`, `tests/ingest/test_ingest_slides.py` (PPTX half),
  `tests/ingest/conftest.py` additions (`decks_dir`, `expected_deck_json`).
- `python-pptx` moves from the `fixtures` group to `[project] dependencies`.
- `tests/fixtures/README.md`: pointer to the deck JSON.

**Out**
- PDF parsing → P2-02. PDF images, the min-size and recurring-image rules, pictures inside
  group shapes → P2-03. CLI → P2-04.
- Bullet nesting levels — not stored (see Decisions). Charts, SmartArt, vector images
  (EMF/WMF/SVG), embedded video — ignored in v1.
- Keynote, ODP, Google Slides exports other than `.pptx`/`.pdf` — out of scope (plan §1).

## Tasks

1. **Hand-write `tests/fixtures/decks/lecture01.deck.json` first**, as
   `Deck.model_dump(mode="json")` of the **PPTX** deck, transcribed from the constants in
   `tests/fixtures/decks/make_deck.py` and the README decks table — never from the code
   under test:

   | Slide | `title` | `blocks` | `notes` | `image_ids` |
   |---|---|---|---|---|
   | 1 | `Markov Decision Processes` | one block: the five `SLIDE1_BULLETS` | `NOTES[0]` | `[]` |
   | 2 | `The Bellman Equation` | two blocks: `SLIDE2_LEFT` (6 lines), then `SLIDE2_RIGHT` (6 lines) | `NOTES[1]` | `[]` |
   | 3 | `Value Iteration` | one block: the five `SLIDE3_STEPS`, the third with its leading spaces stripped (`gamma * sum_s' …`) | `NOTES[2]` | `["img-a63ae9b7dc5e9397"]` |

   `source` is `"tests/fixtures/decks/lecture01.pptx"`; `hidden` is `false` on every slide;
   `recurring_image_ids` is `[]`; `assets` holds one entry: `id` `img-a63ae9b7dc5e9397`
   (the first 16 hex digits of `sha256(value_iteration.png)`), `media_type` `image/png`,
   `width` 240, `height` 150, `data` = base64 of the committed `value_iteration.png`
   (`python -c "import base64;print(base64.b64encode(open('tests/fixtures/decks/value_iteration.png','rb').read()).decode())"`
   — derived from the source file, not from a parser). Two-space indent, LF line endings,
   trailing newline.
2. **`tests/ingest/test_ingest_slides.py`** — the done-gate, PPTX half (P2-02 adds the PDF half):
   - `ingest_slides(fixtures_dir / "decks/lecture01.pptx")` equals
     `Deck.model_validate_json(deck_json)`. The assertion message says: *the deck fixture is
     hand-written; if the extraction rule changed on purpose, edit the JSON deliberately —
     do not regenerate it from the code under test.*
   - `len(deck.slides) == 3`.
   - `Deck.model_validate_json(deck.model_dump_json()) == deck` — image bytes survive the
     JSON round trip as base64.
   - A `.key` path raises `ValueError` naming the unsupported suffix; a missing `.pptx`
     raises `FileNotFoundError`. (`.key`, not `.pdf`, so the test stays true after P2-02.)
3. **`tests/ingest/test_pptx.py`** — every README decks-table row is a test name, run on the fixture:
   - Slide 2 has exactly two blocks, the left placeholder's six lines then the right's.
   - Every slide has non-`None` notes; slide 2's notes contain `this will be on the exam`.
   - Slide 3 has one image whose `data` equals `value_iteration.png` byte-for-byte, whose
     id is `img-a63ae9b7dc5e9397`, and whose size is 240×150.
   - Titles come from the title placeholder and equal `SLIDE*_TITLE`.
   - **Ad-hoc decks built in-memory with python-pptx and saved under `tmp_path`** — the
     slide-side analogue of Phase 1's inline VTT strings:
     - an empty body placeholder yields no `TextBlock`;
     - a slide on the *Blank* layout with one text box → `title is None`, one block;
     - a paragraph containing a soft line break (`add_line_break()`, which python-pptx
       reads back as `\v`) becomes **one** line;
     - a table shape becomes one line per row, cells joined with ` | `;
     - a slide marked hidden (`slide._element.set("show", "0")`) keeps its number and has
       `hidden=True`;
     - blank notes text → `notes is None`; no notes slide → `None`;
     - a text box positioned above the body placeholder but added last is read **first**
       (position order, not z-order);
     - a `.pptx` path whose content is garbage bytes → `DeckParseError`.
   - `clean_line` table: `- States s in S` → `States s in S`; `• x`, `– x`, `* x` → `x`;
     `1. Initialise` unchanged (numbered markers are content); `-x` unchanged (glyph must be
     followed by whitespace); `a\vb` → `a b`; NBSP and tabs → one space; idempotent on
     every fixture line; identity on clean text.
4. **Types** in `slides.py`, pydantic v2, shared base
   `model_config = ConfigDict(frozen=True, extra="forbid", ser_json_bytes="base64", val_json_bytes="base64")`:
   - `TextBlock(lines: tuple[str, ...])` — validator: at least one line, none empty.
   - `SlideImage(id: str, media_type: str, width: int, height: int, data: bytes)` — validator:
     `id == image_id(data)` where `image_id(data) = "img-" + sha256(data).hexdigest()[:16]`
     (export `image_id`; P2-03 tests use it); `width`, `height` ≥ 1.
   - `Slide(number: int, title: str | None, blocks: tuple[TextBlock, ...], notes: str | None,
     image_ids: tuple[str, ...], hidden: bool = False)` — validator: `number >= 1`,
     `image_ids` unique.
   - `Deck(source: str, slides: tuple[Slide, ...], assets: tuple[SlideImage, ...],
     recurring_image_ids: tuple[str, ...] = ())` — validators: slide numbers are exactly
     `1..n` in order; asset ids unique; every `image_ids` entry (and every
     `recurring_image_ids` entry) resolves to an asset. Error messages name the offending
     ids, as `model/` does.
   - `class DeckParseError(ValueError)` — message names the file and the underlying error.
5. **`clean_line(text: str) -> str`**: collapse all whitespace (including `\v` and NBSP) to
   one space and strip; then remove exactly one leading bullet glyph from
   `- – — • · ▪ ● ○ ■ ‣ *` **when followed by whitespace**; strip again. Idempotent;
   identity on clean text. Applied to titles, body lines and notes by both parsers — it is
   what makes the PDF's `- States…` equal the PPTX's `States…` in P2-02.
6. **`parse_pptx(path: Path) -> Deck`**, per slide in file order (`number` = position, 1-based):
   - `title`: the placeholder of type `TITLE` or `CENTER_TITLE`, through `clean_line`;
     `None` if absent or empty.
   - Body: every other shape with a text frame or a table, **sorted by
     (top band, left)** where the band is `top // (slide_height / 20)` — reading order,
     not z-order. One `TextBlock` per shape: one line per paragraph (a table: one line per
     row, cells joined with ` | `), each through `clean_line`, empty lines dropped, empty
     blocks dropped. Top-level shapes only; groups are P2-03.
   - Pictures (`shape_type == MSO_SHAPE_TYPE.PICTURE`, top level) in the same positional
     order → `SlideImage(data=image.blob, media_type=image.content_type, size from
     image.size)`; a slide lists each id once; `Deck.assets` is deduplicated by id in
     first-seen order.
   - `notes`: `notes_slide.notes_text_frame.text` through `clean_line` when
     `has_notes_slide`; `None` when absent or blank.
   - `hidden`: the slide element's `show` attribute equals `"0"`.
   - Wrap `pptx.exc.PackageNotFoundError`, `zipfile.BadZipFile`, `KeyError` from a corrupt
     package in `DeckParseError`; let `FileNotFoundError` through.
7. **`ingest_slides(path: Path) -> Deck`**: dispatch on `path.suffix.lower()` through a
   `_PARSERS` dict exactly like `captions.py` (`.pptx` only here; P2-02 adds `.pdf`);
   otherwise `ValueError(f"unsupported deck format: {suffix!r} (expected .pptx or .pdf)")`.
   P2-03 will add keyword-only knobs; leave the signature ready for them.
8. **`pyproject.toml`**: `dependencies = ["pydantic>=2", "python-pptx>=1.0"]`; remove
   `python-pptx` from the `fixtures` group (it keeps `reportlab`, `pypdf`, `Pillow`);
   `uv sync --all-groups`; commit `uv.lock`. python-pptx 1.0 ships `py.typed`, so mypy
   strict must stay clean with **no** `ignore_missing_imports` override.
9. **`tests/fixtures/README.md`**: add `decks/lecture01.deck.json` to the file listing —
   "the PPTX deck as `Deck` JSON, hand-written (P2-01); the PDF yields the same titles and
   blocks with `notes: null` (P2-02)" — and the "never regenerated from the code under
   test" sentence, as for the segments file.
10. Run the full check suite and commit in two steps: the JSON and tests first (red on
    `ImportError`), then the implementation.

## Acceptance criteria

- `uv run pytest` → all green; `uv run ruff check .`, `uv run mypy`, `uv run lint-imports` clean.
- `uv run python -c "from pathlib import Path; from lecturenotes.ingest.slides import ingest_slides; print(len(ingest_slides(Path('tests/fixtures/decks/lecture01.pptx')).slides))"`
  prints `3`.
- `uv run python -c "from pathlib import Path; from lecturenotes.ingest.slides import Deck, ingest_slides; print(ingest_slides(Path('tests/fixtures/decks/lecture01.pptx')) == Deck.model_validate_json(Path('tests/fixtures/decks/lecture01.deck.json').read_text(encoding='utf-8')))"`
  prints `True`.
- `grep -c '"number"' tests/fixtures/decks/lecture01.deck.json` prints `3`.
- `grep -c "img-a63ae9b7dc5e9397" tests/fixtures/decks/lecture01.deck.json` prints `2`
  (the slide-3 reference and the asset).
- `grep -n "python-pptx" pyproject.toml` shows it under `dependencies` only.
- `git log` shows the JSON and tests committed before (or together with, but never after)
  the implementation; `git status` clean.

## Decisions & notes

- **Image ids are content hashes** (`img-` + 16 hex of sha256), not `slideN-imgM`. A figure
  reused on two slides is one asset with two references, and nothing in the id moves when a
  slide is inserted — the same reasoning as plan §7.2 for topic ids.
- **Bytes stay in `SlideImage.data`; ingest never writes files.** Stage 2 is pure (plan §3).
  Phase 5 mints `MediaAsset(id, media_type, source)` from a `SlideImage` and owns where the
  bytes go (`source` is a path or URL the emitter resolves, plan §2.2). `ser_json_bytes` /
  `val_json_bytes = "base64"` make the whole `Deck` JSON round-trippable, which is what lets
  the expected fixture be one plain JSON file and lets P2-04's `--json` output be re-read.
- **The JSON fixture describes the PPTX deck.** The PDF has no notes and re-encodes the
  figure (P2-03), so P2-02 compares the PDF against the same file for titles and blocks
  only. One fixture, two views — not two fixtures that drift.
- **Reading order is positional, not z-order.** spTree order is authoring order; a text box
  added last but placed at the top must still be read first. Row bands of ¹⁄₂₀ slide height
  keep two side-by-side placeholders (same top) in left-to-right order.
- **A soft line break (`\v`) becomes a space; a paragraph becomes a line.** In a slide, a
  soft break is a wrapped bullet, a new paragraph is a new bullet.
- **Bullet levels are not stored** in v1. python-pptx offers `paragraph.level` for free but
  the PDF cannot produce it reliably, and the cross-format equality test is the headline
  invariant. When Phase 5 wants nesting, add `Line(text, level)` in `model/`-style and let
  mypy find the breakage (plan §10) — do not bolt a parallel `levels` tuple on.
- **`Slide.number` is the 1-based position in the file, hidden slides included**, so a
  `SlideRange` in an anchor matches what a reader counts when they open the deck. Phase 4
  can skip `hidden` slides when aligning; it must not renumber.
- **`Deck.source` is the path as given** so Phase 5 can fill `SourceRef.deck_path` without
  re-deriving it.
- **Ad-hoc decks are built with python-pptx inside the tests** rather than committed as
  files: they are small, exact, and readable in the test that uses them — the P0-03 rule
  ("add the case to the fixture") applies to cases that need the *lecture*, not to
  structural edge cases of the file format.
