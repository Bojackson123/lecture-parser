"""Caption ingest (plan §3 stage 1): ``.vtt`` / ``.srt`` → ``[Cue]`` → ``[Segment]``.

Three pure functions plus a composing entrypoint, added one ticket at a time:

    parse_vtt / parse_srt  → [Cue]        P1-01  (tags stripped here)
    dedupe_rolling         → [Cue]        P1-02
    merge_sentences        → [Segment]    P1-03
    ingest_captions(path)  → [Segment]    P1-03

Parsing is strict about *structure* (a garbage block raises ``CaptionParseError``) but
lenient about *content* (unknown tags, cue settings and extra header text are ignored):
a course's captions come from one exporter, so a structural error means the whole file
is suspect while cosmetic variation is normal.
"""

from __future__ import annotations

import html
import re
from collections.abc import Iterator
from pathlib import Path

from pydantic import BaseModel, ConfigDict, model_validator

__all__ = [
    "CaptionParseError",
    "Cue",
    "Segment",
    "dedupe_rolling",
    "format_timestamp",
    "ingest_captions",
    "merge_sentences",
    "parse_srt",
    "parse_vtt",
    "strip_tags",
]


class _CaptionModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Cue(_CaptionModel):
    """One caption block: a time span and its text lines *after* tag stripping.

    ``lines`` is a tuple (the model is frozen and P1-02 compares line sequences by
    value). Rolling-caption repetition is still present at this stage.
    """

    start_s: float
    end_s: float
    lines: tuple[str, ...]

    @model_validator(mode="after")
    def _valid(self) -> Cue:
        _check_span(self.start_s, self.end_s)
        if not self.lines:
            raise ValueError("a cue needs at least one line")
        return self


class Segment(_CaptionModel):
    """A sentence-sized run of speech with its time span (the output of stage 1)."""

    start_s: float
    end_s: float
    text: str

    @model_validator(mode="after")
    def _valid(self) -> Segment:
        _check_span(self.start_s, self.end_s)
        if not self.text:
            raise ValueError("a segment needs non-empty text")
        return self


def _check_span(start_s: float, end_s: float) -> None:
    if not 0 <= start_s <= end_s:
        raise ValueError(f"expected 0 <= start_s <= end_s, got start_s={start_s}, end_s={end_s}")


class CaptionParseError(ValueError):
    """A structurally malformed caption file. ``line_no`` is 1-based."""

    def __init__(self, line_no: int, message: str) -> None:
        super().__init__(f"line {line_no}: {message}")
        self.line_no = line_no


# --- tag stripping -----------------------------------------------------------------

_TIMING_TAG = re.compile(r"<(?:\d+:)?\d{2}:\d{2}\.\d{3}>")
_OTHER_TAG = re.compile(r"</?[A-Za-z][^<>]*>")
_WHITESPACE = re.compile(r"\s+")


def strip_tags(text: str) -> str:
    """Reduce a caption line to plain, single-spaced text.

    Timing tags (``<00:04:32.000>``) become a space — they always sit on a word
    boundary, and some exporters write ``<c>back</c><00:04:32.400><c>to</c>`` with no
    whitespace of their own. Every other tag (``<c>``, ``<v Name>``, ``<i>`` …) becomes
    nothing, because styling tags can legitimately sit mid-word. Entities are then
    unescaped and whitespace collapsed. Idempotent, and the identity on clean text.
    """
    text = _TIMING_TAG.sub(" ", text)
    text = _OTHER_TAG.sub("", text)
    text = html.unescape(text)
    return _WHITESPACE.sub(" ", text).strip()


# --- timestamps --------------------------------------------------------------------

_TIMESTAMP = r"(?:(\d+):)?(\d{2}):(\d{2})[.,](\d{3})"
_TIMING_LINE = re.compile(rf"^{_TIMESTAMP}[ \t]+-->[ \t]+{_TIMESTAMP}(?:[ \t].*)?$")


def _to_seconds(hours: str | None, minutes: str, seconds: str, millis: str) -> float:
    total_ms = ((int(hours or 0) * 60 + int(minutes)) * 60 + int(seconds)) * 1000 + int(millis)
    return total_ms / 1000


def format_timestamp(seconds: float, *, sep: str = ".") -> str:
    """``HH:MM:SS.mmm`` (``sep=","`` for SRT). Inverse of what the parsers accept."""
    total_ms = round(seconds * 1000)
    hours, rest = divmod(total_ms, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    secs, millis = divmod(rest, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{sep}{millis:03d}"


# --- the shared block scanner ------------------------------------------------------

_NEWLINE = re.compile(r"\r\n|\n")
_VTT_HEADER = re.compile(r"^WEBVTT(?:[ \t].*)?$")
_VTT_SKIPPABLE = re.compile(r"^(?:NOTE|STYLE|REGION)(?:[ \t]|$)")

_Block = list[tuple[int, str]]  # (1-based line number, line) for each non-blank line


def _blocks(text: str) -> Iterator[_Block]:
    """Split caption text into blank-line-separated blocks, tolerating a BOM and CRLF."""
    lines = _NEWLINE.split(text.removeprefix("\ufeff"))
    block: _Block = []
    for line_no, line in enumerate(lines, start=1):
        if line.strip():
            block.append((line_no, line))
        elif block:
            yield block
            block = []
    if block:
        yield block


def _cue_from_block(block: _Block, timing_index: int) -> Cue | None:
    """Build a cue whose timing line is ``block[timing_index]``; ``None`` if no speech."""
    line_no, timing = block[timing_index]
    match = _TIMING_LINE.match(timing)
    if match is None:
        raise CaptionParseError(line_no, f"expected a timing line, got {timing.strip()!r}")
    groups = match.groups()
    start_s = _to_seconds(*groups[:4])
    end_s = _to_seconds(*groups[4:])
    if start_s > end_s:
        raise CaptionParseError(line_no, f"cue ends before it starts: {timing.strip()!r}")
    lines = tuple(clean for _, raw in block[timing_index + 1 :] if (clean := strip_tags(raw)))
    if not lines:
        return None
    return Cue(start_s=start_s, end_s=end_s, lines=lines)


def parse_vtt(text: str) -> list[Cue]:
    """Parse WebVTT text into cues, tags stripped, rolling repetition left in place.

    The header block (``WEBVTT`` plus any header lines up to the first blank line) and
    ``NOTE`` / ``STYLE`` / ``REGION`` blocks are skipped. A cue block is an optional
    identifier line, a timing line (settings after the end timestamp are ignored), then
    text lines. Anything else raises ``CaptionParseError`` with the offending line.
    """
    blocks = _blocks(text)
    header = next(blocks, None)
    if header is None or header[0][0] != 1 or not _VTT_HEADER.match(header[0][1]):
        got = header[0][1] if header else ""
        raise CaptionParseError(1, f"expected a 'WEBVTT' header, got {got.strip()!r}")
    cues: list[Cue] = []
    for block in blocks:
        if _VTT_SKIPPABLE.match(block[0][1]):
            continue
        # An identifier line is optional: only treat the first line as one when the
        # second line is the one carrying the arrow, so a malformed timing line is
        # reported at its own line number rather than at the text after it.
        has_identifier = "-->" not in block[0][1] and len(block) > 1 and "-->" in block[1][1]
        timing_index = 1 if has_identifier else 0
        cue = _cue_from_block(block, timing_index)
        if cue is not None:
            cues.append(cue)
    return cues


def parse_srt(text: str) -> list[Cue]:
    """Parse SubRip text into cues; same tolerance and stripping as ``parse_vtt``.

    Every block is a sequence-number line (required, value not validated — files in
    the wild skip numbers), a timing line with comma *or* dot milliseconds, then text.
    """
    cues: list[Cue] = []
    for block in _blocks(text):
        line_no, first = block[0]
        if "-->" in first:
            raise CaptionParseError(line_no, f"expected a sequence number, got {first.strip()!r}")
        cue = _cue_from_block(block, timing_index=1)
        if cue is not None:
            cues.append(cue)
    return cues


# --- rolling-caption dedupe --------------------------------------------------------


def _overlap(prev: tuple[str, ...], cur: tuple[str, ...]) -> int:
    """Largest ``k`` such that the last ``k`` lines of ``prev`` are the first ``k`` of ``cur``."""
    for k in range(min(len(prev), len(cur)), 0, -1):
        if prev[-k:] == cur[:k]:
            return k
    return 0


def dedupe_rolling(cues: list[Cue]) -> list[Cue]:
    """Collapse YouTube-style rolling captions to one copy of every line.

    Rolling exporters make each cue re-show the previous cue's last line(s) before its
    new text. For each cue, the lines that overlap the *surviving* cue before it are
    dropped, and every surviving line keeps the span of the cue it first appeared in.
    A cue with nothing left is dropped and its predecessor's ``end_s`` extended over
    it — the words were on screen that long, so the anchor should say so.

    Lines are compared by exact equality (no case folding, no punctuation stripping)
    and only against the immediate neighbour; a line that recurs ten cues later is the
    lecturer repeating themselves, which later phases should see. Stripping repeats
    until the remainder no longer overlaps its predecessor — on real rolling captions
    that is one step; on degenerate repeated text it is what makes the function a fixed
    point of itself (``dedupe_rolling(dedupe_rolling(x)) == dedupe_rolling(x)``).
    """
    out: list[Cue] = []
    for cur in cues:
        if not out:
            out.append(cur)
            continue
        prev = out[-1]
        lines = cur.lines
        while lines and (k := _overlap(prev.lines, lines)):
            lines = lines[k:]
        if not lines:
            out[-1] = prev.model_copy(update={"end_s": cur.end_s})
        elif lines == cur.lines:
            out.append(cur)
        else:
            out.append(Cue(start_s=cur.start_s, end_s=cur.end_s, lines=lines))
    return out


# --- sentence merge ----------------------------------------------------------------

# One or more of . ? ! (so "..." and "?!" are one terminator), optional closing quote or
# bracket, then whitespace or end of text. "3.5" and "e.g." mid-sentence do not match;
# "e.g. this" does — accepted for v1, see the P1-03 ticket.
_SENTENCE_END = re.compile(r"""[.?!]+["')\]]*(?=\s|$)""")


def _split_sentences(text: str) -> tuple[list[str], str]:
    """Complete sentences (stripped, non-empty) and the unterminated remainder."""
    sentences: list[str] = []
    pos = 0
    for match in _SENTENCE_END.finditer(text):
        if sentence := text[pos : match.end()].strip():
            sentences.append(sentence)
        pos = match.end()
    return sentences, text[pos:].strip()


def merge_sentences(
    cues: list[Cue], *, max_gap_s: float = 5.0, max_segment_s: float = 60.0
) -> list[Segment]:
    """Join deduped cues into sentence-bounded segments.

    Cue lines are space-joined into an open buffer and every complete sentence
    (terminated by ``.``, ``?`` or ``!`` followed by whitespace or end of text) is
    emitted as a segment. A segment's span is the **union of the cues that contributed
    to it**: two sentences from one cue share that cue's span, and a sentence that
    spans cues runs from the first cue's start to the last cue's end. Nothing is
    interpolated within a cue — the anchor must point where the words really are —
    so spans may overlap and later phases must not assume segments partition time.

    Two knobs keep unpunctuated captions from swallowing the lecture: an open buffer
    is flushed as-is when the next cue starts more than ``max_gap_s`` after the
    previous one ended (a pause is a topic break, not a continuing sentence), or when
    taking the next cue would make the buffer span more than ``max_segment_s``. The
    remainder after the last cue is flushed with the last cue's end. Pure; the input
    list is not modified.
    """
    out: list[Segment] = []
    buffer = ""  # text without a terminator yet
    buffer_start_s = 0.0  # start of the first cue in ``buffer``
    last_end_s = 0.0  # end of the most recent cue

    def flush() -> None:
        nonlocal buffer
        out.append(Segment(start_s=buffer_start_s, end_s=last_end_s, text=buffer))
        buffer = ""

    for cue in cues:
        if buffer and cue.start_s - last_end_s > max_gap_s:
            flush()
        if buffer and cue.end_s - buffer_start_s > max_segment_s:
            flush()
        if buffer:
            buffer = f"{buffer} {' '.join(cue.lines)}"
        else:
            buffer = " ".join(cue.lines)
            buffer_start_s = cue.start_s
        sentences, buffer = _split_sentences(buffer)
        out.extend(Segment(start_s=buffer_start_s, end_s=cue.end_s, text=s) for s in sentences)
        if sentences:
            # Whatever is left over began in this cue; an untouched buffer keeps its start.
            buffer_start_s = cue.start_s
        last_end_s = cue.end_s
    if buffer:
        flush()
    return out


# --- the composed stage ------------------------------------------------------------

_PARSERS = {".vtt": parse_vtt, ".srt": parse_srt}


def ingest_captions(path: Path, **merge_kwargs: float) -> list[Segment]:
    """Plan §3 stage 1 end to end: read ``path``, parse by suffix, dedupe, merge.

    ``merge_kwargs`` (``max_gap_s``, ``max_segment_s``) are forwarded to
    ``merge_sentences`` so callers can tune the knobs without re-composing the
    pipeline. Raises ``ValueError`` for a suffix other than ``.vtt`` / ``.srt``,
    ``FileNotFoundError`` for a missing file, ``CaptionParseError`` for bad structure.
    """
    suffix = path.suffix.lower()
    parser = _PARSERS.get(suffix)
    if parser is None:
        raise ValueError(f"unsupported caption format: {suffix!r} (expected .vtt or .srt)")
    cues = parser(path.read_text(encoding="utf-8-sig"))
    return merge_sentences(dedupe_rolling(cues), **merge_kwargs)
