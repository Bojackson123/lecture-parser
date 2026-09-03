"""The render-side contract (plan §2.3, §5): what every renderer declares and produces.

``Renderer`` is a protocol, not a base class: anything with a name, a declared
``Capability`` set and a ``render()`` method qualifies. ``degrade()`` (in ``model``)
rewrites a week against the declared set before rendering, so a renderer only ever
sees constructs it supports.

Boundary rule: ``render`` imports ``model`` only — never ``ingest``.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from typing import Protocol

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from lecturenotes.model import Capability, MediaAsset, NoteWeek


def format_clock(seconds: float) -> str:
    """``m:ss``, or ``h:mm:ss`` once past an hour; whole seconds, floored.

    The one timestamp format anchors are surfaced in: the contract test greps every
    renderer's output for it (plan §8), so renderers must build timestamps with this
    and nothing else.
    """
    total = int(seconds)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


class RenderOptions(BaseModel):
    """Rendering knobs. Empty on purpose (plan §2.3): the signature never churns, and
    fields arrive only when a renderer actually needs one."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class RenderedDocument(BaseModel):
    """One output document: a relative POSIX path and its text."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    text: str

    @field_validator("name")
    @classmethod
    def _relative_posix_path(cls, name: str) -> str:
        if not name:
            raise ValueError("document name must be non-empty")
        if "\\" in name:
            raise ValueError(f"document name must be a POSIX path, no backslash: {name!r}")
        if name.startswith("/"):
            raise ValueError(f"document name must be relative: {name!r}")
        if ".." in name.split("/"):
            raise ValueError(f"document name must not contain a '..' segment: {name!r}")
        return name


def _duplicates(values: Iterable[str]) -> list[str]:
    return sorted(value for value, n in Counter(values).items() if n > 1)


class RenderResult(BaseModel):
    """What one render produces: documents plus the assets the output references.

    ``assets`` is a manifest, not a copy of the lecture's asset lists: the emitter
    resolves exactly these (plan §2.3), so a renderer lists an asset here iff its
    output links to it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    documents: tuple[RenderedDocument, ...]
    assets: tuple[MediaAsset, ...]

    @model_validator(mode="after")
    def _names_and_asset_ids_unique(self) -> RenderResult:
        dupes = _duplicates(document.name for document in self.documents)
        if dupes:
            raise ValueError(f"duplicate document name(s): {', '.join(dupes)}")
        dupes = _duplicates(asset.id for asset in self.assets)
        if dupes:
            raise ValueError(f"duplicate asset id(s): {', '.join(dupes)}")
        return self


_ASSET_EXTENSION = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/svg+xml": ".svg",
}


def asset_target(asset: MediaAsset) -> str:
    """The output-relative path an asset lands at, e.g. ``assets/fig-x.png``.

    Renderers build links with it; the filesystem emitter writes to it (P3-03) — one
    helper, so the two can never drift.
    """
    ext = _ASSET_EXTENSION.get(asset.media_type)
    if ext is None:
        raise ValueError(
            f"asset {asset.id!r} has media type {asset.media_type!r}, which maps to no "
            "file extension"
        )
    return f"assets/{asset.id}{ext}"


class Renderer(Protocol):
    """The contract every renderer satisfies (plan §2.3), pinned by the four
    properties in ``tests/contract/test_renderers.py``."""

    name: str
    capabilities: set[Capability]

    def render(self, week: NoteWeek, opts: RenderOptions) -> RenderResult: ...
