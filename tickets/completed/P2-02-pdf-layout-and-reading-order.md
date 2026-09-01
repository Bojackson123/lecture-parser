# P2-02 — PDF layout: columns in reading order, title, boilerplate; `parse_pdf`
Phase 2 · Depends on: P2-01 · Size: L

## Goal

The hard half of the plan §6 criterion — *multi-column PDF reads in order*. A PDF has no
placeholders, only positioned strings, so this ticket adds a **pure, property-tested layout
function** `layout_page(spans, …)` that turns `(x, y, font size, text)` spans into a title
plus column blocks, and `parse_pdf(path)`, which feeds it `pypdf` spans, drops running
footers, and is registered in `ingest_slides`. The headline test is cross-format: the PDF
deck's titles and blocks equal the PPTX deck's (P2-01's hand-written JSON), so the fixture
deck — built so that naive extraction interleaves slide 2's two columns — reads left column
fully, then right.

## Scope

**In**
- `Span`, `PageLayout`, `layout_page`, `parse_pdf` in `lecturenotes/ingest/slides.py`;
  `.pdf` registered in `ingest_slides`.
- `tests/ingest/test_pdf.py`, `tests/ingest/test_layout_properties.py`, span strategies in
  `tests/ingest/strategies.py`, the PDF half of `tests/ingest/test_ingest_slides.py`.
- `pypdf` moves from the `fixtures` group to `[project] dependencies`.
- `tests/fixtures/README.md`: decks table rows for the column rule and the footer.

**Out**
- PDF images → P2-03 (in this ticket the PDF deck's `image_ids` and `assets` are empty).
- Speaker notes from PDF — PDFs have none; `notes` is `None`.
- OCR of image-only pages, password-protected PDFs, Beamer overlay collapse (the same frame
  repeated with incremental reveals), right-to-left scripts — see Decisions.

## Tasks

1. **Tests first.**
   - `tests/ingest/test_ingest_slides.py`, PDF half: for every slide of
     `ingest_slides(fixtures_dir / "decks/lecture01.pdf")`, `(number, title, blocks)` equals
     the JSON fixture's, and `notes is None`. Whole-deck equality waits for P2-03 (images).
     The SRT-style "both formats agree" assertion:
     `[(s.title, s.blocks) for s in pdf.slides] == [(s.title, s.blocks) for s in pptx.slides]`.
   - `tests/ingest/test_pdf.py`, README rows as names, on the fixture:
     - slide 2 has exactly two blocks: the six left-column lines (`Equation` …
       `gamma: discount factor`), then the six right-column lines (`Intuition` …
       `Everything else in the course builds on this`) — the multi-column row;
     - no line on slide 1 starts with `- ` (bullet glyphs stripped by `clean_line`);
     - slide 3's third line starts with `gamma *` (leading spaces gone) and slide 3 has five lines;
     - no slide's title or lines contain `slide 1 / 3`, `slide 2 / 3` or `slide 3 / 3` — the
       footer is boilerplate;
     - titles are the 28-pt strings `Markov Decision Processes`, `The Bellman Equation`,
       `Value Iteration`;
     - `LECTURE01.PDF` (upper-case suffix, via a copy under `tmp_path`) parses;
     - a `.pdf` path whose content is garbage bytes → `DeckParseError`;
     - a one-page PDF (write it in the test with `pypdf.PdfWriter().add_blank_page()`) →
       one slide, `title is None`, no blocks — the footer rule needs ≥ 2 pages and must
       not fire on 1.
   - `tests/ingest/test_layout_properties.py` (hypothesis) on `layout_page` with synthetic
     spans from a new `spans(...)` strategy family in `strategies.py` (page 842 × 595, text
     alphabet letters + spaces, sizes 10–20 body):
     - **two columns**: L and R line lists (1–8 each), `x_L ∈ [40, 120]`,
       `x_R − x_L ∈ [250, 500]`, rows at shared or independent y's, spans **shuffled** →
       `blocks == [L top-to-bottom, R top-to-bottom]`;
     - **one column with indents**: x offsets ≤ 60 pt from the block's left edge → exactly
       one block, lines in descending-y order;
     - **no text lost**: the multiset of input texts (after `clean_line`) equals title +
       every block line;
     - **order-invariance**: any permutation of the spans gives an equal `PageLayout`;
     - **uniform size** → `title is None`; one span 1.15× larger and topmost → it is the title;
     - **two-line title**: two rows at the largest size within 1.5 × size of each other →
       joined with a space.
2. **`Span(x: float, y: float, size: float, text: str)`** (frozen; `y` grows upward as in
   PDF user space) and **`PageLayout(title: str | None, blocks: tuple[TextBlock, ...])`**.
3. **`layout_page(spans, *, page_width: float, page_height: float) -> PageLayout`**:
   - Drop spans whose `clean_line(text)` is empty.
   - **Rows**: sort by `y` descending; spans whose `y` differ by ≤ 0.5 × min(size) share a row.
   - **Title**: let `top = max(size)`; the title is the topmost row whose spans are all at
     `top`, *provided* `top ≥ 1.15 × (largest other size)` or the page has a single row; a
     row at the same size directly beneath (gap ≤ 1.5 × size) joins it with a space; the
     result goes through `clean_line`. Otherwise `None`. Title spans are removed before
     column detection.
   - **Columns**: take the distinct x-starts of the remaining spans in ascending order and
     cluster by single linkage — a gap between consecutive x-starts greater than
     `column_gap = 0.15 × page_width` starts a new column. Sub-bullet indents (20–60 pt)
     chain into their parent column; the fixture's 390-pt gap splits.
   - **Order**: columns left → right; within a column, rows top → bottom; spans sharing a
     row are joined in `x` order with one space; each row through `clean_line`; empty
     rows and empty columns dropped. One `TextBlock` per column.
4. **`parse_pdf(path: Path) -> Deck`**:
   - `pypdf.PdfReader(path)`; if `is_encrypted`, try `decrypt("")` and raise
     `DeckParseError` if that fails; wrap `pypdf.errors.PdfReadError` (and the `PdfStreamError`
     family) as `DeckParseError`; let `FileNotFoundError` through.
   - Per page, collect spans with `page.extract_text(visitor_text=…)` — `x = tm[4]`,
     `y = tm[5]`, `font_size`, text with the trailing newline pypdf appends removed; skip
     whitespace-only text. `page_width/height` from `page.mediabox`.
   - **Boilerplate**: normalise every span's text with `re.sub(r"\d+", "#", clean_line(text))`;
     a normalised string that occurs on **more than half** of the pages, in a deck of at
     least two pages, is dropped from every page before layout. (The fixture footer
     `Lecture 1 - slide # / #` is on 3 of 3.)
   - Each page → `Slide(number=index + 1, title, blocks, notes=None, image_ids=())`;
     `Deck(source=str(path), slides, assets=())`.
5. Register `".pdf": parse_pdf` in `_PARSERS`; the unsupported-suffix message already says
   `.pptx or .pdf`.
6. **`pyproject.toml`**: `dependencies = ["pydantic>=2", "python-pptx>=1.0", "pypdf>=6"]`;
   drop `pypdf` from `fixtures` (which keeps `reportlab` and `Pillow` for the generator).
   pypdf's image decoding in P2-03 needs Pillow; it arrives at runtime as a dependency of
   python-pptx — say so in a comment next to the dependency list. pypdf ships `py.typed`;
   mypy strict stays clean without overrides.
7. **`tests/fixtures/README.md`**: in the decks table, slide 2's *Intended extraction* cell
   gains "(P2-02: x-clustering with a 0.15 × page-width gap threshold)"; add a row `— |
   footer | Lecture 1 - slide N / 3 on every page | dropped as boilerplate: a
   digit-normalised line on more than half the pages`.
8. Full check suite; commit tests-first, then the implementation.

## Acceptance criteria

- `uv run pytest` → all green, hypothesis included; ruff, mypy, lint-imports clean.
- `uv run python -c "from pathlib import Path; from lecturenotes.ingest.slides import ingest_slides; d=ingest_slides(Path('tests/fixtures/decks/lecture01.pdf')); print([b.lines[0] for b in d.slides[1].blocks])"`
  prints `['Equation', 'Intuition']`.
- `uv run python -c "from pathlib import Path; from lecturenotes.ingest.slides import ingest_slides as f; p=f(Path('tests/fixtures/decks/lecture01.pdf')); q=f(Path('tests/fixtures/decks/lecture01.pptx')); print([(s.title, s.blocks) for s in p.slides] == [(s.title, s.blocks) for s in q.slides])"`
  prints `True`.
- `uv run python -c "from pathlib import Path; from lecturenotes.ingest.slides import ingest_slides; print(ingest_slides(Path('tests/fixtures/decks/lecture01.pdf')).model_dump_json().count('slide 2 / 3'))"`
  prints `0`.
- `grep -n "pypdf" pyproject.toml` shows it under `dependencies` only.
- `git status` clean; tests-first visible in the log.

## Decisions & notes

- **pypdf, not pdfplumber or PyMuPDF.** It is already pinned, pure Python, typed, and a
  probe of the fixture showed `extract_text(visitor_text=…)` yields one span per drawn
  string with usable coordinates — enough for columns, title and footer. Revisit only with
  a real deck pypdf mangles, and then add that page to the fixture first (P0-03 rule).
- **Columns only when text is far apart** (0.15 × page width ≈ 126 pt on A4 landscape), so
  indentation never fragments a single column into several. The cost: a full-width
  paragraph sitting above two columns is read with the left column, slightly early.
  Accepted for v1; the alternative (row-aware segmentation) needs a real deck to tune.
- **Title by font size, not by position.** Beamer and PowerPoint exports set titles in the
  largest face but not always at the top edge, and section slides have nothing else. A
  page with a single font size has no title rather than a wrong one — Phase 5 can still
  name the topic from the speech.
- **Boilerplate by cross-page repetition, not by margin position**, so course names,
  lecturer names and page counters vanish wherever they sit, and a genuine bottom-of-slide
  bullet survives. Digit normalisation is what makes `slide 1 / 3` and `slide 2 / 3` the
  same line. The rule needs ≥ 2 pages and "more than half" so a two-page deck whose pages
  legitimately share one line is the only false positive.
- **Spans on one row are joined with a space.** A kerned word split into two text operators
  would gain a spurious space — known limitation, fix with a real file in hand (and add it
  to the fixture).
- **Order-invariance is a property test** because the PDF content-stream order is
  precisely what must *not* leak into the output; the fixture's row-by-row drawing is one
  adversarial order, hypothesis supplies the rest.
- **Beamer overlays** (frames repeated with incremental reveals) would produce near-duplicate
  consecutive slides. Not collapsed in v1: the fixture has no such case and slide numbers
  must stay the file's page numbers. If real decks need it, add a page to the fixture and a
  post-step in `ingest_slides` that marks (not removes) overlay pages.
- **`y` grows upward** (PDF user space) in `Span`; "top → bottom" means descending `y`.
  Keep the synthetic strategies in the same convention so property failures are readable.
- **Span coordinates are `tm × cm`, not raw `tm[4]`/`tm[5]`** (implementation note).
  pypdf hands the visitor the text matrix and the current transformation separately, and
  exporters that draw inside a scaled `cm` (PowerPoint's own export, Cairo) keep the real
  size in the matrices rather than in `Tf`; so `x, y` are the composed origin and `size` is
  `font_size ×` the composed unit height. Identical to the raw values on the fixture
  (identity `cm`, unit `Tm`), and it keeps the 0.15 × page-width threshold in the same
  units as `mediabox`.
- **A page that is a single row is a title** (a section slide with nothing else), even
  at one size; "uniform size → no title" holds from two rows up. The synthetic two-column
  strategy therefore keeps its rows apart in the one-line-each case.
- **The footer rule is tested on pages copied out of the fixture** with
  `pypdf.PdfWriter.add_page`: page 1 alone keeps `slide 1 / 3` (one page can't recur),
  pages 1–2 drop it. Same P2-01 rule as ad-hoc PPTX decks: cases about the *file format*
  are built in the test; cases about the *lecture* go into the fixture.
