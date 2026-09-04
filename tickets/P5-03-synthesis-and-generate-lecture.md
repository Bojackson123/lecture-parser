# P5-03 — Synthesis pass, asset minting, `generate_lecture()`, expected-notes fixture
Phase 5 · Depends on: P5-02 · Size: M

## Goal

The lecture-level half of plan §4.2 ("Per-chunk generation, then a lecture-level
synthesis pass") and the phase's single entrypoint: `generate_lecture(deck, chunks,
...)` runs merge → chunk pass → synthesis → asset minting and returns a validated
`NoteLecture`. Asset minting discharges the Phase 2 handoff ("Phase 5 mints
`MediaAsset` from `SlideImage` and owns where the bytes go"): referenced slide images
are written to a `media/` directory and become id-keyed `MediaAsset`s. The
hand-written `lecture01.notes.json` fixture pins the full output: with the recorded
fake, the committed sources generate a `NoteLecture` whose content is the `week01`
lec01 that Phase 3 renders — the two halves of the pipeline now meet in the middle.

## Scope

**In**
- `lecturenotes/generate/prompts.py`: `LectureSynthesis`, `synthesis_prompt`.
- `lecturenotes/generate/lecture.py`: `generate_lecture` (the only entrypoint;
  everything else in `generate/` is exported for debugging and tests).
- `tests/fixtures/generate/lecture01.notes.json` (hand-written) and the
  `synthesis:lec01` entry added to `lecture01.responses.json`; README rows.
- `tests/generate/test_generate_lecture.py`; synthesis-prompt tests in
  `tests/generate/test_prompts.py`.

**Out**
- `NoteWeek` assembly, pairing, cache wiring, output paths → P5-04 (the week is a
  container, §7.3 — one `NoteWeek(...)` construction in the caller, no function
  needed here).
- A week-level LLM pass / cross-lecture dedup (§7.3) — deferred until a
  multi-lecture source fixture exists; recap-slide dedup cannot be tested against
  one lecture.
- The verification pass (unsupported-claim flagging) → Phase 8.

## Tasks

1. **Fixtures first**, hand-transcribed (standing rule):
   - Add `synthesis:lec01` to `tests/fixtures/generate/lecture01.responses.json`:
     the JSON text of a `LectureSynthesis` carrying `week01` lec01's `title`,
     `overview`, `objectives`, `glossary` and `open_questions` verbatim.
   - `tests/fixtures/generate/lecture01.notes.json`: a full `NoteLecture`, equal to
     `week01` lec01 with exactly three deliberate differences, each forced by
     generation-truth:
     - `source` is `SourceRef(deck_path="tests/fixtures/decks/lecture01.pptx",
       caption_path="tests/fixtures/captions/lecture01.vtt")` — the files the fake
       pipeline actually consumes; no video URL.
     - the value-iteration topic's `Figure.asset_id` is `img-a63ae9b7dc5e9397`
       (the P5-02 responses fixture).
     - `assets` is one `MediaAsset(id="img-a63ae9b7dc5e9397",
       media_type="image/png", source="media/img-a63ae9b7dc5e9397.png",
       alt=<week01's alt text>)`.
   - README rows for both under the generate table, naming the three differences.
2. **Tests next** (red on `ImportError`/missing fixture).
   - `test_prompts.py` additions: `synthesis_prompt(topics, "lec01").key ==
     "synthesis:lec01"`; the prompt contains every topic heading, embeds
     `LectureSynthesis.model_json_schema()` (assert a distinctive fragment, e.g.
     `"open_questions"`), and pins the instruction that the synthesis must not
     introduce claims absent from the topics (exact substring — the §4.2
     anti-hallucination stance at lecture level).
   - `tests/generate/test_generate_lecture.py`, on the real entrypoints
     (`ingest_slides` on the PPTX, `ingest_captions` on the VTT, `align_lecture`,
     `RecordedClient` on the responses fixture, `out_dir=tmp_path`):
     - The result equals
       `NoteLecture.model_validate_json(lecture01.notes.json.read_text())` — full
       structural equality, glossary and open questions included.
     - `tmp_path / "media" / "img-a63ae9b7dc5e9397.png"` exists and its bytes equal
       the deck asset's `SlideImage.data`; nothing else is written under `media/`
       (unreferenced and recurring images are not minted).
     - Exactly **5** `complete` calls (4 chunks + 1 synthesis) — a counting wrapper
       around the fake; the budget that makes §7.1's cost math legible.
     - A second run into a fresh `out_dir` returns an equal `NoteLecture`
       (deterministic given the client) and rewrites the media file (id-keyed, so
       re-runs update in place — the emitter's `asset_target` convention upstream).
     - A response set whose figure references an image no topic's slides carry
       still fails with the P5-02 `ValueError`; a `LectureSynthesis` response with
       an extra field fails validation (`extra="forbid"` end to end).
3. **`prompts.py`**: `LectureSynthesis` (frozen, `extra="forbid"`): `title: str`,
   `overview: str`, `objectives: list[str]`, `glossary: list[Definition] = []`,
   `open_questions: list[str] = []`. `synthesis_prompt(topics: Sequence[Topic],
   lecture_id: str) -> GenRequest`: key `synthesis:{lecture_id}`; prompt = each
   topic's heading plus its body as compact JSON (the model reads the IR it just
   wrote), instructions (overview of a few sentences; 2–4 objectives; glossary only
   for terms the topics actually define or use; open questions; add nothing the
   topics don't support), and the embedded schema.
4. **`lecture.py`**: `generate_lecture(deck: Deck, chunks: Sequence[Chunk], *,
   lecture_id: str, source: SourceRef, client: LLMClient, out_dir: Path,
   min_words: int = 100) -> NoteLecture`:
   - `merge_chunks(chunks, min_words)` → one validated `ChunkNotes` per chunk (one
     `complete` each, reusing the P5-02 request/validation path so `generate_topic`
     and the entrypoint cannot drift) → topics.
   - One synthesis `complete` → validated `LectureSynthesis`.
   - Mint assets: for each `Figure.asset_id` across topics, in first-reference
     order, look up the `SlideImage` in `deck.assets`, write its bytes to
     `out_dir / "media" / f"{id}{ext}"` (`ext` from `media_type` — `.png` for
     `image/png`; a tiny explicit map, `ValueError` on an unmapped type), and build
     `MediaAsset(id=..., media_type=..., source=f"media/{id}{ext}",
     alt=image_alts.get(id))` with `image_alts` merged across the chunk responses.
   - Return `NoteLecture(id=lecture_id, title=..., overview=..., objectives=...,
     source=source, topics=..., glossary=..., open_questions=..., assets=...)` —
     the model's own validators (figure refs resolve, asset ids unique) are the
     final gate.
5. Run the full check suite; commit fixtures + tests first, then the implementation.

## Acceptance criteria

- `uv run pytest` → all green; `uv run ruff check .`, `uv run mypy`,
  `uv run lint-imports` clean.
- `uv run python -c "import tempfile; from pathlib import Path; from lecturenotes.ingest.captions import ingest_captions; from lecturenotes.ingest.slides import ingest_slides; from lecturenotes.align import align_lecture; from lecturenotes.generate.client import RecordedClient; from lecturenotes.generate.lecture import generate_lecture; from lecturenotes.model import SourceRef; deck = ingest_slides(Path('tests/fixtures/decks/lecture01.pptx')); chunks = align_lecture(deck, ingest_captions(Path('tests/fixtures/captions/lecture01.vtt'))); lec = generate_lecture(deck, chunks, lecture_id='lec01', source=SourceRef(), client=RecordedClient(Path('tests/fixtures/generate/lecture01.responses.json')), out_dir=Path(tempfile.mkdtemp())); print(len(lec.topics), lec.assets[0].source)"`
  prints `4 media/img-a63ae9b7dc5e9397.png`.
- `git log` shows fixtures and tests committed before (or together with, never
  after) the implementation; `git status` clean.

## Decisions & notes

- **`generate_lecture(deck, chunks, ...)` is the only entrypoint** — the phase
  convention (`ingest_captions`, `ingest_slides`, `align_lecture`). It takes chunks,
  not paths: stage 5's input is `[Chunk]` (plan §3) plus the deck for slide context,
  and composing ingest → align → generate is the caller's job (P5-04's `build`).
- **Assets land in `media/`, id-keyed, path-relative.** `MediaAsset.source` is "a
  path or URL that the emitter resolves"; a POSIX path relative to the week
  document's directory keeps the expected fixture byte-stable (no tmp paths in
  JSON), re-runs overwrite in place, and the P3-03 emitter needs no change. The
  content-hash id means a figure reused across topics is one file, one asset, two
  references.
- **Only referenced images are minted.** `image_ids` already excludes recurring
  logos (P2-03), and an image no `Figure` cites has no reader; minting everything
  would bloat `media/` with decoration. The deck keeps the bytes; generation copies
  out only what the notes use.
- **Synthesis reads the generated topics, not the transcript.** Its job is
  coherence — overview, objectives, glossary, open questions over what the notes
  *say* — and the transcript was already distilled chunk by chunk where the model
  had room for detail (§4.2). Re-feeding 45k tokens of speech would reintroduce the
  uniformly-shallow failure mode the chunking exists to avoid.
- **Five requests per fixture lecture, exactly.** Pinned so cost regressions are
  test failures: a refactor that silently doubles calls (e.g. re-validating via a
  second `complete`) breaks the counting test, not the invoice.
- **`lecture01.notes.json` is generation's spec; `week01.json` stays render's.**
  Both hand-written, differing only in the three documented generation-truth fields.
  Neither is ever regenerated from code under test; if generation's shape must
  change, edit the fixture deliberately, README first (P0-03 rule).
- **No week-level LLM pass.** §7.3 puts cross-lecture dedup in week synthesis, but
  with a single-lecture fixture there is nothing to dedup and no way to test it;
  `build` assembles `NoteWeek` structurally. When a second lecture's sources exist,
  the pass gets its own ticket and fixture.
