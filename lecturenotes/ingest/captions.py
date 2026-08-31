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

from pydantic import BaseModel, ConfigDict, model_validator

__all__ = [
    "CaptionParseError",
    "Cue",
    "Segment",
    "dedupe_rolling",
    "format_timestamp",
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
