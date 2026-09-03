"""Renderer capabilities and shared degradation (plan §2.3).

A renderer declares the set of ``Capability`` values it supports; ``degrade()``
rewrites anything the IR uses that the renderer lacks *before* rendering, so
degradation is declared once here, not improvised per renderer. ``constructs_used()``
is the capability↔construct map — defined once, here and nowhere else:

============== ==========================================
Capability     Construct
============== ==========================================
``NATIVE_MATH`` any ``Equation``
``NESTING``     any ``BulletItem`` with non-empty children
``CALLOUTS``    any ``Callout``
``TABLES``      any ``Table``
``IMAGES``      any ``Figure``
``CODE``        any ``CodeBlock``
============== ==========================================

``Prose``, flat ``BulletList``, ``Definition`` and ``Quote`` map to no capability —
they are the floor every renderer must handle.
"""

from __future__ import annotations

from enum import StrEnum

from lecturenotes.model.nodes import (
    BulletItem,
    BulletList,
    Callout,
    CodeBlock,
    Equation,
    Figure,
    Node,
    Prose,
    Table,
)
from lecturenotes.model.notes import NoteLecture, NoteWeek, Topic


class Capability(StrEnum):
    NATIVE_MATH = "NATIVE_MATH"
    NESTING = "NESTING"
    CALLOUTS = "CALLOUTS"
    TABLES = "TABLES"
    IMAGES = "IMAGES"
    CODE = "CODE"


def constructs_used(week: NoteWeek) -> set[Capability]:
    """The capabilities ``week``'s topic bodies require of a renderer.

    Glossary entries are lecture metadata, not body nodes, and are not counted.
    """
    used: set[Capability] = set()
    for lecture in week.lectures:
        for topic in lecture.topics:
            for node in topic.body:
                if isinstance(node, Equation):
                    used.add(Capability.NATIVE_MATH)
                elif isinstance(node, BulletList):
                    if any(item.children for item in node.items):
                        used.add(Capability.NESTING)
                elif isinstance(node, Callout):
                    used.add(Capability.CALLOUTS)
                elif isinstance(node, Table):
                    used.add(Capability.TABLES)
                elif isinstance(node, Figure):
                    used.add(Capability.IMAGES)
                elif isinstance(node, CodeBlock):
                    used.add(Capability.CODE)
    return used


def degrade(week: NoteWeek, capabilities: set[Capability]) -> NoteWeek:
    """Rewrite ``week`` so its bodies use only ``capabilities``. Pure — a new week.

    Rewrites cascade in a fixed order — math → tables → nesting → callouts → images →
    code — so later steps catch earlier steps' output (math-degradation emits code
    blocks, table-degradation emits lists); that order is what makes
    ``constructs_used(degrade(week, C)) <= C`` hold for every subset ``C``.

    Inline ``$...$`` in ``Prose``, bullet text, table cells and ``Definition`` text is
    never rewritten: it is plain text, readable anywhere, and re-parsing prose for
    dollar signs is the markdown-as-IR mistake plan §2.1 warns against.

    Cards, glossary, open questions, anchors, topic ids and lecture assets are
    untouched — an unreferenced asset is not an output construct.
    """
    return NoteWeek(
        id=week.id,
        course=week.course,
        week_number=week.week_number,
        lectures=[_degrade_lecture(lecture, capabilities) for lecture in week.lectures],
    )


def _degrade_lecture(lecture: NoteLecture, capabilities: set[Capability]) -> NoteLecture:
    alts = {asset.id: asset.alt for asset in lecture.assets}
    return NoteLecture(
        id=lecture.id,
        title=lecture.title,
        overview=lecture.overview,
        objectives=lecture.objectives,
        source=lecture.source,
        topics=[_degrade_topic(topic, capabilities, alts) for topic in lecture.topics],
        glossary=lecture.glossary,
        open_questions=lecture.open_questions,
        assets=lecture.assets,
    )


def _degrade_topic(
    topic: Topic, capabilities: set[Capability], alts: dict[str, str | None]
) -> Topic:
    body: list[Node] = list(topic.body)
    if Capability.NATIVE_MATH not in capabilities:
        body = [_equation_to_code(node) for node in body]
    if Capability.TABLES not in capabilities:
        body = [_table_to_bullets(node) for node in body]
    if Capability.NESTING not in capabilities:
        body = [_flatten_bullets(node) for node in body]
    if Capability.CALLOUTS not in capabilities:
        body = [_callout_to_prose(node) for node in body]
    if Capability.IMAGES not in capabilities:
        body = [_figure_to_prose(node, alts) for node in body]
    if Capability.CODE not in capabilities:
        body = [_code_to_prose(node) for node in body]
    return Topic(
        id=topic.id, heading=topic.heading, anchor=topic.anchor, body=body, cards=topic.cards
    )


def _equation_to_code(node: Node) -> Node:
    if isinstance(node, Equation):
        # The label is dropped: an IR cross-reference handle, not content.
        return CodeBlock(language="latex", code=node.latex)
    return node


def _table_to_bullets(node: Node) -> Node:
    if isinstance(node, Table):
        # One item per row, cells joined the way P2-01 joins slide-table cells;
        # the header is the first item.
        rows = [node.header, *node.rows]
        return BulletList(items=[BulletItem(text=" | ".join(row)) for row in rows])
    return node


def _flatten_bullets(node: Node) -> Node:
    if isinstance(node, BulletList):
        return BulletList(items=_flatten_items(node.items))
    return node


def _flatten_items(items: list[BulletItem]) -> list[BulletItem]:
    """Pre-order: parent, then its children, recursively; no prefix decoration."""
    flat: list[BulletItem] = []
    for item in items:
        flat.append(BulletItem(text=item.text))
        flat.extend(_flatten_items(item.children))
    return flat


def _callout_to_prose(node: Node) -> Node:
    if isinstance(node, Callout):
        return Prose(text=f"{node.kind.value}: {node.text}")
    return node


def _figure_to_prose(node: Node, alts: dict[str, str | None]) -> Node:
    if isinstance(node, Figure):
        text = node.caption or alts.get(node.asset_id) or node.asset_id
        return Prose(text=f"[figure: {text}]")
    return node


def _code_to_prose(node: Node) -> Node:
    if isinstance(node, CodeBlock):
        return Prose(text=node.code)
    return node
