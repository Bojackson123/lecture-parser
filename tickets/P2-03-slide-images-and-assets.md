# P2-03 — Slide images and assets: PDF images, size filter, recurring-image rule, groups
Phase 2 · Depends on: P2-02 · Size: M

## Goal

Finish plan §3 stage 2's "rendered images" for both formats so that the whole-deck
equality tests hold on the PDF too. PDF page images become `SlideImage`s; decorative
images (bullet glyphs, rules) and recurring images (the logo on every slide) are kept out
of `Slide.image_ids` so Phase 5 never emits a `Figure` per logo; pictures inside PPTX group
shapes are found. The filtering rules live once, in the composed entrypoint, and are tested
once.

## Scope

**In**
- PDF image extraction in `parse_pdf`; group-shape recursion (pictures *and* text) in
  `parse_pptx`; a shared media-type allow-list.
- Format-agnostic post-processing in `ingest_slides`: `min_px` filter and the
  recurring-image rule; keyword-only knobs forwarded like `ingest_captions`'s.
- `tests/ingest/test_images.py`; the full-deck PDF assertion in
  `tests/ingest/test_ingest_slides.py`.
- `tests/fixtures/README.md`: slide 3 row and file listing.

**Out**
- Vector images (EMF/WMF/SVG) — skipped, not converted. Charts, SmartArt — ignored.
- Cross-format image identity (the same figure via PDF and PPTX has different ids — see Decisions).
- Writing image files anywhere → Phase 5 / emit. Rendering whole slides to PNG → Phase 9.

## Tasks

1. **Tests first.**
   - `tests/ingest/test_ingest_slides.py`: **PDF full deck** — `ingest_slides(pdf)` equals
     the JSON fixture after two deliberate substitutions written in the test: every
     `notes` becomes `None`, and the single asset is compared by
     `(media_type, width, height)` and slide 3's `image_ids` by length (the PDF figure is
     re-encoded by pypdf, so its bytes and id differ — the test name says so).
   - `tests/ingest/test_images.py`, on the fixture:
     - PDF slide 3 yields exactly one asset: `image/png`, 240 × 150; slides 1–2 yield none;
     - the PDF asset's id is **not** `img-a63ae9b7dc5e9397` — named
       `test_pdf_figure_is_reencoded_so_its_id_differs_from_the_pptx_one`;
     - PPTX slide 3's asset id is `img-a63ae9b7dc5e9397` (unchanged from P2-01).
   - Ad-hoc PPTX decks (python-pptx, `tmp_path`, pictures generated in-test with Pillow or
     read from `value_iteration.png`):
     - an 8 × 8 picture is dropped from `image_ids` and from `assets` (`min_px=32` default);
       with `min_px=4` it is kept;
     - the same picture on 3 of 4 slides → its id is in `deck.recurring_image_ids`, in
       `assets` exactly once, and in no slide's `image_ids`; a different picture on one of
       those slides is unaffected;
     - the same picture on 2 of 4 slides is **not** recurring (rule is "more than half");
     - a deck of 2 slides with the same picture on both is not recurring (rule needs ≥ 3 slides);
     - a picture inside a group shape is found; a text box inside a group is read as a block;
     - two different pictures on one slide are listed left-to-right;
     - the same picture twice on one slide → one asset, and it appears **once** in that
       slide's `image_ids` (ids are unique per slide, P2-01 validator).
   - `_media_type_ok` table: `image/png`, `image/jpeg`, `image/gif`, `image/bmp`,
     `image/tiff`, `image/webp` → kept; `image/x-emf`, `image/x-wmf`, `image/svg+xml` → skipped.
2. **`parse_pdf`**: for each `img in page.images` → `SlideImage(data=img.data,
   media_type=_MIME_BY_EXT[Path(img.name).suffix.lower()], width, height = img.image.size)`;
   an unknown extension or a `media_type` outside the allow-list is skipped; a decode
   failure (pypdf raises on some filters, Pillow on some streams) skips **that image** with
   no error — a broken image must never lose a slide's text. Order within a page as pypdf
   yields them.
3. **`parse_pptx`**: replace the top-level shape walk with a recursive one — a
   `GroupShape` contributes its children in the group's positional slot (sorted by the
   group's `top`/`left`; children in their own order); pictures whose `content_type` fails
   `_media_type_ok` are skipped; `PlaceholderPicture` (a picture dropped into a content
   placeholder) counts as a picture.
4. **Shared post-processing** in `ingest_slides(path, *, min_px: int = 32)`, pure and
   format-agnostic, applied to the parser's `Deck`:
   - drop every asset with `width < min_px or height < min_px` from `assets` and from every
     `image_ids`;
   - **recurring rule**: for a deck with ≥ 3 slides, an id present in the `image_ids` of
     more than half of the slides is removed from every slide's `image_ids`, stays in
     `assets`, and is listed in `Deck.recurring_image_ids` (first-seen order).
   Implement as two small functions on `Deck` values (`model_copy(update=…)`, the models
   are frozen) so P2-04's CLI and Phase 4 tests can call them on hand-built decks.
5. **`tests/fixtures/README.md`**: slide 3 row — "the PPTX picture is the committed PNG
   byte-for-byte (`img-a63ae9b7dc5e9397`); the PDF figure comes back from pypdf
   re-encoded (RGB, ~1.2 KB) with a different id, 240 × 150 either way"; the file listing
   line for `value_iteration.png` gains "(PPTX embeds it verbatim; the PDF re-encodes it)".
6. Full check suite; commit tests-first, then the implementation.

## Acceptance criteria

- `uv run pytest` → all green; ruff, mypy, lint-imports clean.
- `uv run python -c "from pathlib import Path; from lecturenotes.ingest.slides import ingest_slides; d=ingest_slides(Path('tests/fixtures/decks/lecture01.pdf')); print(len(d.assets), d.assets[0].media_type, d.assets[0].width, d.assets[0].height, d.slides[2].image_ids == (d.assets[0].id,))"`
  prints `1 image/png 240 150 True`.
- `uv run python -c "from pathlib import Path; from lecturenotes.ingest.slides import ingest_slides; print(ingest_slides(Path('tests/fixtures/decks/lecture01.pptx')).assets[0].id)"`
  prints `img-a63ae9b7dc5e9397`.
- `uv run pytest tests/ingest/test_ingest_slides.py -q` shows the PDF full-deck test passing.
- `git status` clean; tests-first visible in the log.

## Decisions & notes

- **Ids hash the bytes *as extracted*.** The same figure reaches us as the original PNG
  from a PPTX and as a Flate stream that pypdf re-encodes from a PDF; normalising (decode
  and hash pixels) would buy cross-format identity that nothing needs — a lecture has one
  deck. Phase 4/5 see one format at a time.
- **The size and recurring rules live in `ingest_slides`, not in the parsers**, so they are
  written and tested once and behave identically for both formats; the parsers stay
  faithful extractors. Same structure as `merge_sentences` sitting behind `ingest_captions`.
- **Recurring assets stay in `assets` but leave `image_ids`.** A debugger (P2-04's `slides`
  command) can see what was set aside and why; Phase 5 iterates `image_ids` and never
  sees the logo. "More than half of ≥ 3 slides" because a two-slide deck cannot
  distinguish a logo from a figure shown twice.
- **`min_px` is a knob** (default 32) because bullet glyphs and rules are 8–20 px and real
  figures are hundreds; a course whose decks use tiny icons meaningfully can lower it.
- **Decode failures skip the image silently.** Losing one picture is recoverable; raising
  would lose the slide's text and, with `ingest_slides` as the only entrypoint, the whole
  deck. Log nothing — the package has no logging yet; P2-04's command shows what was found.
- **No fixture mutation.** The recurrence and size cases are ad-hoc decks, like Phase 1's
  inline silence-gap cues; the canonical deck stays byte-stable and the README table keeps
  describing the lecture, not file-format corner cases.
- **Vector images are skipped, not converted.** Rasterising EMF/WMF needs a system
  renderer; nothing downstream can inline them; and they are almost always decorations.
  If a real deck keeps its figures as EMF, that is a Phase 9 concern (render the slide).
