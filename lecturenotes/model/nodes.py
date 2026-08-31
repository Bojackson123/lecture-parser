"""Body node types for a ``Topic`` (plan §2.2).

Semantic, not presentational: the IR records *what* the lecturer said
(``Callout(kind=EXAM)``), and the renderer decides what that looks like.
Every node carries a ``type`` literal so the ``Node`` union can be
discriminated when validating JSON.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CalloutKind(StrEnum):
    """Why a passage was flagged. Presentation (colour, icon) is downstream."""

    EXAM = "EXAM"
    PITFALL = "PITFALL"
    UNCERTAIN = "UNCERTAIN"
    ASIDE = "ASIDE"


class _Node(BaseModel):
    """Shared config: immutable (hence hashable) and strict about unknown fields."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class Prose(_Node):
    type: Literal["prose"] = "prose"
    text: str


class BulletItem(_Node):
    """One bullet. Not a ``Node`` itself; only appears inside ``BulletList``.

    ``children`` exists so NESTING degradation (plan §2.3) has real input.
    """

    text: str
    children: list[BulletItem] = []


class BulletList(_Node):
    type: Literal["bullet_list"] = "bullet_list"
    items: list[BulletItem] = Field(min_length=1)


class Definition(_Node):
    type: Literal["definition"] = "definition"
    term: str
    definition: str


class Equation(_Node):
    """Always LaTeX (plan §2.2): every plausible target consumes it natively."""

    type: Literal["equation"] = "equation"
    latex: str
    label: str | None = None


class CodeBlock(_Node):
    type: Literal["code_block"] = "code_block"
    code: str
    language: str | None = None


class Callout(_Node):
    """``text`` is a plain string, not ``list[Node]``, to keep the union non-recursive."""

    type: Literal["callout"] = "callout"
    kind: CalloutKind
    text: str


class Figure(_Node):
    """References a ``MediaAsset`` by id, not a path; the emitter resolves it."""

    type: Literal["figure"] = "figure"
    asset_id: str
    caption: str | None = None


class Table(_Node):
    type: Literal["table"] = "table"
    header: list[str]
    rows: list[list[str]]

    @model_validator(mode="after")
    def _rows_match_header_width(self) -> Table:
        width = len(self.header)
        for i, row in enumerate(self.rows):
            if len(row) != width:
                raise ValueError(
                    f"row {i} has {len(row)} cell(s) but the header has {width} column(s)"
                )
        return self


class Quote(_Node):
    type: Literal["quote"] = "quote"
    text: str
    attribution: str | None = None


Node = Annotated[
    Prose | BulletList | Definition | Equation | CodeBlock | Callout | Figure | Table | Quote,
    Field(discriminator="type"),
]
"""Ordered, heterogeneous body content of a ``Topic``."""
