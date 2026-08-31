"""Where a note came from: source coordinates and media assets (plan §2.2).

``SourceAnchor`` on every topic is what makes the notes trustworthy — timestamp plus
slide numbers, so any claim can be checked in seconds.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator


class _SourceModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SlideRange(_SourceModel):
    """1-based, inclusive slide range: ``SlideRange(3, 5)`` covers slides 3, 4 and 5."""

    start: int
    end: int

    @model_validator(mode="after")
    def _ordered_and_one_based(self) -> SlideRange:
        if not 1 <= self.start <= self.end:
            raise ValueError(f"expected 1 <= start <= end, got start={self.start}, end={self.end}")
        return self


class SourceAnchor(_SourceModel):
    """The citation for a topic: a time span in the recording plus optional slides.

    Timestamps are float seconds — readable in hand-written JSON fixtures, trivially
    comparable, and what VTT/SRT parsing produces directly.
    """

    start_s: float
    end_s: float
    slides: SlideRange | None = None

    @model_validator(mode="after")
    def _non_negative_and_ordered(self) -> SourceAnchor:
        if not 0 <= self.start_s <= self.end_s:
            raise ValueError(
                f"expected 0 <= start_s <= end_s, got start_s={self.start_s}, end_s={self.end_s}"
            )
        return self


class SourceRef(_SourceModel):
    """The inputs a lecture was built from. Any subset may be present."""

    video_url: str | None = None
    deck_path: str | None = None
    caption_path: str | None = None


class MediaAsset(_SourceModel):
    """A figure's backing media.

    ``media_type`` is a MIME type (``image/png``). ``source`` is a path or URL that the
    emitter resolves — inlined as base64, uploaded, or copied next to the output.
    """

    id: str
    media_type: str
    source: str
    alt: str | None = None
