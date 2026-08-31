"""Slide ingest (plan §3 stage 2): ``.pptx`` / ``.pdf`` → ``Deck``.

Two parsers, one pure layout function and a composing entrypoint, added one ticket at
a time:

    Deck / Slide / TextBlock / SlideImage, clean_line   P2-01
    parse_pptx(path)       → Deck                       P2-01  (text + notes + pictures)
    ingest_slides(path)    → Deck                       P2-01  (dispatch by suffix)
    layout_page(spans)     → PageLayout                 P2-02  (pure; columns, title)
    parse_pdf(path)        → Deck                       P2-02  (text; boilerplate dropped)
    image rules            in ingest_slides             P2-03  (size, recurring; groups)

The stage is pure: image bytes stay in ``SlideImage.data`` and nothing is written to
disk. Phase 5 mints ``MediaAsset``s from ``SlideImage``s and owns where the bytes go.
Both parsers push every title, body line and note through ``clean_line`` so the PDF's
``- States…`` equals the PPTX's ``States…`` (P2-02's cross-format invariant).
"""

from __future__ import annotations

import hashlib
import re
import zipfile
from collections import Counter
from collections.abc import Callable, Iterable
from pathlib import Path

from pptx import Presentation
from pptx.enum.shapes import PP_PLACEHOLDER
from pptx.exc import PackageNotFoundError
from pptx.shapes.base import BaseShape
from pptx.shapes.graphfrm import GraphicFrame
from pptx.shapes.picture import Picture
from pptx.shapes.shapetree import SlideShapes
from pptx.slide import Slide as PptxSlide
from pptx.util import Emu, Length
from pydantic import BaseModel, ConfigDict, model_validator

__all__ = [
    "Deck",
    "DeckParseError",
    "Slide",
    "SlideImage",
    "TextBlock",
    "clean_line",
    "image_id",
    "ingest_slides",
    "parse_pptx",
]


class _DeckModel(BaseModel):
    # Bytes travel as base64 in JSON, so a whole ``Deck`` is one plain JSON document:
    # the expected fixture is a file, and P2-04's ``--json`` output can be re-read.
    model_config = ConfigDict(
        frozen=True, extra="forbid", ser_json_bytes="base64", val_json_bytes="base64"
    )


def _duplicates(ids: Iterable[str]) -> list[str]:
    return sorted(value for value, n in Counter(ids).items() if n > 1)


def image_id(data: bytes) -> str:
    """``img-`` + the first 16 hex digits of ``sha256(data)``.

    Content-addressed, not ``slideN-imgM``: a figure reused on two slides is one asset
    with two references, and inserting a slide moves nothing (cf. plan §7.2).
    """
    return "img-" + hashlib.sha256(data).hexdigest()[:16]


class TextBlock(_DeckModel):
    """One shape's worth of text: one line per paragraph (or per table row)."""

    lines: tuple[str, ...]

    @model_validator(mode="after")
    def _valid(self) -> TextBlock:
        if not self.lines:
            raise ValueError("a text block needs at least one line")
        if any(not line for line in self.lines):
            raise ValueError("text block lines must not be empty")
        return self


class SlideImage(_DeckModel):
    """A picture's bytes, identified by their hash (``image_id``)."""

    id: str
    media_type: str
    width: int
    height: int
    data: bytes

    @model_validator(mode="after")
    def _valid(self) -> SlideImage:
        expected = image_id(self.data)
        if self.id != expected:
            raise ValueError(f"image id {self.id!r} does not match its content hash {expected!r}")
        if self.width < 1 or self.height < 1:
            raise ValueError(f"width and height must be >= 1, got {self.width}x{self.height}")
        return self


class Slide(_DeckModel):
    """One slide. ``number`` is the 1-based position in the file, hidden slides included.

    That is what a reader counts when they open the deck, so a ``SlideRange`` in an
    anchor stays honest; Phase 4 may skip ``hidden`` slides but must not renumber.
    """

    number: int
    title: str | None
    blocks: tuple[TextBlock, ...]
    notes: str | None
    image_ids: tuple[str, ...]
    hidden: bool = False

    @model_validator(mode="after")
    def _valid(self) -> Slide:
        if self.number < 1:
            raise ValueError(f"slide number must be >= 1, got {self.number}")
        dupes = _duplicates(self.image_ids)
        if dupes:
            raise ValueError(f"duplicate image id(s) on slide {self.number}: {', '.join(dupes)}")
        return self


class Deck(_DeckModel):
    """The output of stage 2.

    ``source`` is the path as given, in POSIX form (for ``SourceRef.deck_path``).
    """

    source: str
    slides: tuple[Slide, ...]
    assets: tuple[SlideImage, ...]
    recurring_image_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _valid(self) -> Deck:
        numbers = [slide.number for slide in self.slides]
        if numbers != list(range(1, len(numbers) + 1)):
            raise ValueError(
                f"slide numbers must be exactly 1..{len(numbers)} in order, got {numbers}"
            )
        dupes = _duplicates(asset.id for asset in self.assets)
        if dupes:
            raise ValueError(f"duplicate asset id(s): {', '.join(dupes)}")
        known = {asset.id for asset in self.assets}
        missing = sorted({i for slide in self.slides for i in slide.image_ids if i not in known})
        if missing:
            raise ValueError(f"slide(s) reference unknown image id(s): {', '.join(missing)}")
        missing = sorted({i for i in self.recurring_image_ids if i not in known})
        if missing:
            raise ValueError(
                f"recurring_image_ids reference unknown image id(s): {', '.join(missing)}"
            )
        return self


class DeckParseError(ValueError):
    """A deck file that could not be opened or read; names the file and the cause."""

    def __init__(self, path: Path, cause: BaseException) -> None:
        super().__init__(f"{path}: {cause}")
        self.path = path
        self.__cause__ = cause


# --- line cleaning -----------------------------------------------------------------

_WHITESPACE = re.compile(r"\s+")  # \s covers \v, \t and NBSP
_LEADING_BULLET = re.compile(r"^[-–—•·▪●○■‣*]\s")


def clean_line(text: str) -> str:
    """Collapse whitespace, then drop exactly one leading bullet glyph.

    A soft line break (``\\v``) and NBSP become a space; a bullet glyph is removed only
    when followed by whitespace, so ``-x`` and ``1. Initialise`` are content. One glyph,
    not many: ``-  -  twice`` is a line that starts with a dash. Idempotent on cleaned
    text and the identity on clean text.
    """
    text = _WHITESPACE.sub(" ", text).strip()
    return _LEADING_BULLET.sub("", text, count=1).strip()


def _clean_or_none(text: str | None) -> str | None:
    if text is None:
        return None
    cleaned = clean_line(text)
    return cleaned or None


# --- PPTX -----------------------------------------------------------------------------

_TITLE_TYPES = frozenset({PP_PLACEHOLDER.TITLE, PP_PLACEHOLDER.CENTER_TITLE})
_DEFAULT_SLIDE_HEIGHT = Emu(6858000)  # 7.5 in, python-pptx's default template
_ROW_BANDS = 20


def _is_title(shape: BaseShape) -> bool:
    return shape.is_placeholder and shape.placeholder_format.type in _TITLE_TYPES


def _reading_order(shapes: SlideShapes, slide_height: Length) -> list[BaseShape]:
    """Top-level shapes sorted by (row band, left) — position, not z-order.

    spTree order is authoring order, so a text box added last but placed at the top
    must still come first. Bands of ¹⁄₂₀ slide height keep two side-by-side
    placeholders (same top) in left-to-right order.
    """
    band = max(int(slide_height) // _ROW_BANDS, 1)

    def key(shape: BaseShape) -> tuple[int, int]:
        return (int(shape.top or 0) // band, int(shape.left or 0))

    return sorted(shapes, key=key)


def _shape_lines(shape: BaseShape) -> list[str]:
    """Cleaned, non-empty lines of a text-bearing or table shape; ``[]`` otherwise."""
    if isinstance(shape, GraphicFrame) and shape.has_table:
        raw = [" | ".join(cell.text for cell in row.cells) for row in shape.table.rows]
    elif shape.has_text_frame:
        # ``has_text_frame`` is only true on shapes that carry a ``text_frame``.
        raw = [paragraph.text for paragraph in shape.text_frame.paragraphs]  # type: ignore[attr-defined]
    else:
        return []
    return [line for line in (clean_line(r) for r in raw) if line]


def _notes(slide: PptxSlide) -> str | None:
    if not slide.has_notes_slide:
        return None
    frame = slide.notes_slide.notes_text_frame
    return _clean_or_none(frame.text if frame is not None else None)


def parse_pptx(path: Path) -> Deck:
    """Read a ``.pptx`` into a ``Deck``: titles, body blocks, notes, top-level pictures.

    Per slide, ``title`` is the ``TITLE``/``CENTER_TITLE`` placeholder; every other
    top-level shape with a text frame or a table becomes one ``TextBlock`` (a line per
    paragraph, or per table row with cells joined by ``" | "``), in reading order; each
    top-level picture becomes a ``SlideImage`` listed once per slide and once in
    ``assets``. Group shapes are P2-03. Raises ``DeckParseError`` for a file that is
    not a presentation; lets ``FileNotFoundError`` through.
    """
    if not path.is_file():
        raise FileNotFoundError(path)
    try:
        prs = Presentation(str(path))
    except (PackageNotFoundError, zipfile.BadZipFile, KeyError) as exc:
        raise DeckParseError(path, exc) from exc
    slide_height = prs.slide_height if prs.slide_height is not None else _DEFAULT_SLIDE_HEIGHT

    slides: list[Slide] = []
    assets: dict[str, SlideImage] = {}
    for number, pptx_slide in enumerate(prs.slides, start=1):
        title: str | None = None
        blocks: list[TextBlock] = []
        image_ids: list[str] = []
        for shape in _reading_order(pptx_slide.shapes, slide_height):
            if _is_title(shape):
                if title is None:
                    title = _clean_or_none(shape.text_frame.text)  # type: ignore[attr-defined]
                continue
            if isinstance(shape, Picture):
                image = shape.image
                width, height = image.size
                asset = SlideImage(
                    id=image_id(image.blob),
                    media_type=image.content_type,
                    width=width,
                    height=height,
                    data=image.blob,
                )
                assets.setdefault(asset.id, asset)
                if asset.id not in image_ids:
                    image_ids.append(asset.id)
                continue
            lines = _shape_lines(shape)
            if lines:
                blocks.append(TextBlock(lines=tuple(lines)))
        slides.append(
            Slide(
                number=number,
                title=title,
                blocks=tuple(blocks),
                notes=_notes(pptx_slide),
                image_ids=tuple(image_ids),
                hidden=pptx_slide._element.get("show") == "0",
            )
        )
    # ``as_posix``: the path as given, with forward slashes on every platform, so the
    # expected-deck fixture (and any ``--json`` output) is byte-identical across OSes.
    return Deck(source=path.as_posix(), slides=tuple(slides), assets=tuple(assets.values()))


# --- the composed stage ------------------------------------------------------------

_PARSERS: dict[str, Callable[[Path], Deck]] = {".pptx": parse_pptx}


def ingest_slides(path: Path) -> Deck:
    """Plan §3 stage 2 end to end: read ``path`` and parse by suffix.

    ``.pptx`` here; P2-02 registers ``.pdf`` and P2-03 adds keyword-only image knobs.
    Raises ``ValueError`` for any other suffix, ``FileNotFoundError`` for a missing
    file, ``DeckParseError`` for a file that is not a deck.
    """
    suffix = path.suffix.lower()
    parser = _PARSERS.get(suffix)
    if parser is None:
        raise ValueError(f"unsupported deck format: {suffix!r} (expected .pptx or .pdf)")
    return parser(path)
