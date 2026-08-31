# P1-01 — `Cue`/`Segment` types, VTT + SRT parsing, tag stripping
Phase 1 · Depends on: P0-04 · Size: M

## Goal

Create `lecturenotes/ingest/captions.py` (plan §5) with the ingest-side types P0-02
deferred here — `Cue` and `Segment` — plus `parse_vtt`, `parse_srt` and `strip_tags`,
so that both caption fixtures read into the *same* 20 clean cues. This is the first of
three pure functions that make up plan §3 stage 1; P1-02 (dedupe) and P1-03 (sentence
merge) consume its output. Rolling-caption repetition is deliberately left in the cues
this ticket produces.

## Scope

**In**
- `lecturenotes/ingest/captions.py`: `Cue`, `Segment`, `CaptionParseError`, `parse_vtt`,
  `parse_srt`, `strip_tags`.
- `tests/ingest/__init__.py`, `tests/ingest/test_parse.py`, `tests/ingest/test_parse_properties.py`.
- `hypothesis` added to the `dev` dependency group.
- One new row in the `tests/fixtures/README.md` captions table (the tag-whitespace case).

**Out**
- `dedupe_rolling` → P1-02. `merge_sentences`, `ingest_captions(path)` → P1-03.
- A CLI entrypoint → P1-04.
- Speaker attribution from `<v>` tags — dropped, not stored (see Decisions).
- Speech-to-text, `.sbv`/`.ass`/`.ttml` formats — out of scope for v1 (plan §1).

## Tasks

1. **Types** in `captions.py`, pydantic v2 with `model_config = ConfigDict(frozen=True, extra="forbid")`
   exactly as `model/` does:
   - `Cue(start_s: float, end_s: float, lines: tuple[str, ...])` — text lines *after*
     tag stripping; validator `0 <= start_s <= end_s` and `len(lines) >= 1`.
   - `Segment(start_s: float, end_s: float, text: str)` — same timestamp validator;
     `text` non-empty. Defined here (not in P1-03) so the module's public surface is
     settled in one place and `align/` has a single import for it later.
   - `class CaptionParseError(ValueError)` with a `line_no: int` attribute and a message
     of the form `line 12: expected a timing line, got '...'`.
2. **`strip_tags(text: str) -> str`**, in this order:
   - Timing tags `<HH:MM:SS.mmm>` / `<MM:SS.mmm>` → **a single space**.
   - Every other tag → empty string: `<c>`, `<c.classname>`, `</c>`, `<v Name>`, `</v>`,
     `<i>`, `<b>`, `<u>`, `<ruby>`, `<rt>`, `<lang xx>` and their closers.
   - `html.unescape` (`&amp;`, `&lt;`, `&gt;`, `&nbsp;`, `&#39;`).
   - Collapse runs of whitespace to one space; strip both ends.
   Must be idempotent and must be the identity on tag-free, already-normalised text.
3. **`parse_vtt(text: str) -> list[Cue]`**:
   - Strip a UTF-8 BOM if present; split on CRLF or LF line endings.
   - First line must start with `WEBVTT` (optional trailing text after a space/tab);
     otherwise `CaptionParseError(line 1)`.
   - Skip blocks whose first line starts with `NOTE`, `STYLE` or `REGION` (up to the
     next blank line).
   - A cue block is: optional identifier line, a timing line
     `start --> end [settings…]`, then text lines until a blank line or EOF. Cue settings
     after the end timestamp (`align:start position:0%`) are ignored.
   - Timestamps accept `HH:MM:SS.mmm` and `MM:SS.mmm`; convert to float seconds.
   - Apply `strip_tags` to each text line; drop lines that become empty; a cue whose
     lines are all empty is dropped entirely (it carries no speech).
   - Any block that is neither skippable nor a well-formed cue → `CaptionParseError`
     with the offending line number.
4. **`parse_srt(text: str) -> list[Cue]`**: numbered blocks, `HH:MM:SS,mmm` (comma) —
   also accept a dot, since files in the wild mix them; same BOM/CRLF tolerance, same
   `strip_tags` per line, same empty-line handling, same error type. The sequence
   number line is required but its value is not validated (files in the wild skip numbers).
5. **Helpers.** `format_timestamp(seconds: float, *, sep: str = ".") -> str` giving
   `HH:MM:SS.mmm` lives in the package (P1-04 reuses it). The VTT/SRT *renderers* the
   property tests need (`render_vtt(cues)`, `render_srt(cues)`) live in the test module —
   the package never writes captions.
6. **`tests/ingest/test_parse.py`** — every test name is a README row:
   - VTT: exactly 20 cues; the `WEBVTT` header and the `NOTE` block are not cues;
     cue 1 has two lines; cue 1 is `1.0 → 26.0`, cue 20 is `520.0 → 545.0`.
   - SRT: exactly 20 cues.
   - **`parse_vtt(vtt_text) == parse_srt(srt_text)`** — the invariant
     `tests/fixtures/README.md` states. This is the headline test.
   - Cue 11 first line starts with `back to the slides. this is the bellman equation`
     (timing tags with no surrounding whitespace, see Decisions).
   - Cue 12 contains `the expected value` — `<i>` stripped, word kept.
   - Cue 1 line 1 starts with `welcome back everyone` — `<v Lecturer>` and `</v>` gone.
   - `strip_tags` table cases: the cue-11 string; `<c.colorE5E5E5> word</c>`;
     `a &amp; b`; a string with a run of spaces and a tab; idempotence on the fixture
     cues; identity on plain text.
   - `MM:SS.mmm` timestamps parse; CRLF input parses; a BOM-prefixed file parses; a
     file whose first line is not `WEBVTT` raises `CaptionParseError` with `line_no == 1`;
     a cue with a malformed timing line raises with the right `line_no`.
   - A `STYLE` block and a cue identifier line are both skipped (small inline strings).
7. **`tests/ingest/test_parse_properties.py`** (hypothesis):
   - Strategy: lists of 1–30 `Cue`s with strictly increasing, non-overlapping spans and
     1–3 lines each of printable non-empty text containing no `<`, `>`, `&`, or `-->`.
   - Render to VTT text and to SRT text (test-local renderers), parse, and assert the
     parsed list equals the input — for both formats.
   - `strip_tags(strip_tags(s)) == strip_tags(s)` for arbitrary text including random
     tags; `strip_tags(s) == s` for tag-free single-spaced text.
8. `pyproject.toml`: `dev = ["pytest", "ruff", "mypy", "import-linter", "hypothesis"]`;
   `uv sync --all-groups`; commit `uv.lock`.
9. `tests/fixtures/README.md`: extend the cue 11 row to say the timing tags carry **no
   whitespace between them**, so a naive strip glues `backtotheslides` — the rule in
   Task 2 is what makes it read correctly.

## Acceptance criteria

- `uv run pytest tests/ingest` → all green; `uv run pytest` still green overall.
- `uv run ruff check .`, `uv run mypy`, `uv run lint-imports` all clean.
- `uv run python -c "from pathlib import Path; from lecturenotes.ingest.captions import parse_vtt; print(len(parse_vtt(Path('tests/fixtures/captions/lecture01.vtt').read_text(encoding='utf-8'))))"`
  prints `20`.
- `uv run python -c "from pathlib import Path; from lecturenotes.ingest.captions import parse_vtt, parse_srt; r=lambda n: Path('tests/fixtures/captions/'+n).read_text(encoding='utf-8'); print(parse_vtt(r('lecture01.vtt')) == parse_srt(r('lecture01.srt')))"`
  prints `True`.
- `grep -c hypothesis pyproject.toml` ≥ 1 and `uv.lock` is committed with it.
- `git status` clean after commit.

## Decisions & notes

- **Timing tags become a space; all other tags become nothing.** Real YouTube VTT writes
  `<c> word</c>` with the space inside the tag, but the fixture (and some other
  producers) write `<c>word</c><00:00:01.000><c>next</c>` with none. A timing tag always
  sits on a word boundary, so replacing it with a space and collapsing whitespace is
  correct for both. `<i>`/`<b>` can legitimately sit mid-word, so those become nothing.
- **Tags are stripped at parse time.** No downstream stage wants them, so `Cue` holds
  clean text only; there is no raw-text variant to keep in sync.
- **Speaker (`<v Name>`) is dropped.** v1 assumes a single lecturer (plan §1). If a
  Q&A-heavy lecture ever needs it, add `speaker: str | None` to `Cue` then.
- **`Cue.lines` is a tuple**, not a list, because the model is frozen and P1-02 compares
  line sequences by value.
- **`Segment` is defined here, not in P1-03**, so the public surface of `captions.py`
  (`Cue`, `Segment`, three parsers/strippers, then two transforms) is decided once.
- **Both parsers share one block scanner**; only the header rule, the numbering line
  and the millisecond separator differ. Do not write two independent state machines.
- Parsing is strict about *structure* (a garbage block raises) but lenient about
  *content* (unknown tags, cue settings, extra header text are ignored): a course's
  captions come from one exporter, and a structural error means the whole file is
  suspect, while cosmetic variation is normal.
