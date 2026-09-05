"""``NotionRenderer``: a ``NoteWeek`` as one Notion page payload document (plan §5, P7-02).

The format spec is the hand-written ``tests/fixtures/notes/week01.notion.json``; every
formatting decision here is reviewable there, and the rules were decided in P7-01. One
document per week, named ``{week.id}.notion.json`` — stable, so re-emitting overwrites
in place (plan §7.2); the page *title* comes from ``course`` + ``week_number``, which
is what the emitter keys update-not-duplicate on (P7-04).

Structure-as-text is deliberate: ``RenderedDocument.text`` holds
``{"page", "payloads"}`` serialized with ``json.dumps(indent=2, ensure_ascii=False)``
plus one trailing newline — blocks in Notion API shape verbatim, built in one code
path in insertion order, so the builder's order *is* the format and two renders are
byte-equal by construction. The one non-Notion shape is the ``asset_placeholder``
image source: renderers are pure, so the emitter resolves it after uploading.

Notion natively has all six capabilities, so ``degrade()`` is a true no-op here — and
that stays true with the §2.3 limits, which are renderer-local target limits, not
missing capabilities (the P7-03 decision: ``NESTING`` stays declared). All four are
enforced at block-build time, so any valid ``NoteWeek`` renders to payloads Notion
will accept:

- text runs split at exactly 2,000 characters — dumb on purpose; Notion joins
  adjacent runs seamlessly — and never inside an inline ``equation`` run;
- bullet descendants below the second level flatten pre-order into their depth-2
  parent's children array (2-level nesting);
- children arrays chunk at 100: items past the hundredth are promoted to the
  parent's level right after it, dedented but never dropped;
- payloads split only at top-level block boundaries, whenever the next block would
  push past 1,000 nested-inclusive blocks or 100 top-level elements — a block and
  its children always travel together.

The math dialect is Notion-local, like Anki's ``\\(…\\)`` translator before it: paired
``$…$`` in prose, bullet, table-cell and definition text becomes an inline
``equation`` rich-text run; an unpaired ``$`` passes through; headings, citations and
the remaining metadata text (overview, objectives, callouts, quotes, captions, open
questions) stay plain text runs, the P7-01 enumeration taken literally.

``rich_text``, ``citation`` and ``CALLOUT_STYLE`` are exported for debugging and
tests, not for re-composition elsewhere (the ingest-entrypoint doctrine, applied to
render, as in P6-02).
"""

from __future__ import annotations

import json
import re
from typing import Any

from lecturenotes.model import (
    BulletItem,
    BulletList,
    Callout,
    CalloutKind,
    Capability,
    CodeBlock,
    Definition,
    Equation,
    Figure,
    MediaAsset,
    Node,
    NoteLecture,
    NoteWeek,
    Prose,
    Quote,
    SourceAnchor,
    Table,
    Topic,
)
from lecturenotes.render.base import (
    RenderedDocument,
    RenderOptions,
    RenderResult,
    format_clock,
)

_MATH_PAIR = re.compile(r"\$([^$]+)\$")

CALLOUT_STYLE: dict[CalloutKind, tuple[str, str]] = {
    CalloutKind.EXAM: ("📝", "red_background"),
    CalloutKind.PITFALL: ("⚠️", "yellow_background"),
    CalloutKind.UNCERTAIN: ("❓", "gray_background"),
    CalloutKind.ASIDE: ("💡", "blue_background"),
}
"""Kind → (emoji, colour), pinned in P7-01. Presentation is decided here, downstream
of the IR (plan §2.2)."""

_Block = dict[str, Any]
_Run = dict[str, Any]

# The §2.3 Notion API limits, renderer-local on purpose: none of them appears in the
# IR or upstream (plan §2.3, P7-03).
_RICH_TEXT_CAP = 2000
_CHILDREN_CAP = 100
_PAYLOAD_CAP = 1000


class NotionRenderer:
    """Renders a week to one Notion payload document. Pure dict building — no IO."""

    name = "notion"
    capabilities = set(Capability)

    def render(self, week: NoteWeek, opts: RenderOptions) -> RenderResult:
        manifest = _Manifest()
        blocks: list[_Block] = []
        for lecture in week.lectures:
            blocks.extend(_lecture_blocks(lecture, manifest))
        payload = {
            "page": {"title": f"{week.course} — Week {week.week_number}"},
            "payloads": _payloads(blocks),
        }
        text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
        document = RenderedDocument(name=f"{week.id}.notion.json", text=text)
        return RenderResult(documents=(document,), assets=tuple(manifest.assets))


def rich_text(text: str) -> list[_Run]:
    """Content text → rich-text runs, paired ``$…$`` becoming inline equation runs."""
    runs: list[_Run] = []
    pos = 0
    for match in _MATH_PAIR.finditer(text):
        if match.start() > pos:
            runs.extend(_text_runs(text[pos : match.start()]))
        runs.append({"type": "equation", "equation": {"expression": match.group(1)}})
        pos = match.end()
    if pos < len(text):
        runs.extend(_text_runs(text[pos:]))
    return runs


def citation(anchor: SourceAnchor) -> str:
    """The gray heading run: two spaces, the clock, then the P6-01 slide grammar."""
    text = f"  {format_clock(anchor.start_s)}"
    if anchor.slides is not None:
        if anchor.slides.start == anchor.slides.end:
            text += f" · slide {anchor.slides.start}"
        else:
            text += f" · slides {anchor.slides.start}–{anchor.slides.end}"
    return text


class _Manifest:
    """Assets in first-reference order, each once."""

    def __init__(self) -> None:
        self.assets: list[MediaAsset] = []
        self._seen: set[str] = set()

    def add(self, asset: MediaAsset) -> None:
        if asset.id not in self._seen:
            self._seen.add(asset.id)
            self.assets.append(asset)


def _text_run(content: str, **annotations: Any) -> _Run:
    run: _Run = {"type": "text", "text": {"content": content}}
    if annotations:
        run["annotations"] = annotations
    return run


def _text_runs(content: str, **annotations: Any) -> list[_Run]:
    """One text run, or consecutive ≤ 2,000-char runs when the content is longer.

    Splits at exactly the cap, not at word boundaries: Notion joins adjacent runs
    seamlessly, so the reader never sees the seam (P7-03 decision). Each piece keeps
    the annotations.
    """
    if len(content) <= _RICH_TEXT_CAP:
        return [_text_run(content, **annotations)]
    starts = range(0, len(content), _RICH_TEXT_CAP)
    return [_text_run(content[i : i + _RICH_TEXT_CAP], **annotations) for i in starts]


def _payloads(blocks: list[_Block]) -> list[list[_Block]]:
    """Chunk top-level blocks into ≤ 1,000-block, ≤ 100-element payloads.

    Splits happen only at top-level block boundaries — a block and its children
    travel together, so no payload ever holds a partial tree. A single tree cannot
    exceed the cap: after the children chunk it is at most 1 + 100 blocks.
    """
    payloads: list[list[_Block]] = [[]]
    size = 0
    for block in blocks:
        weight = _nested_count(block)
        if payloads[-1] and (len(payloads[-1]) == _CHILDREN_CAP or size + weight > _PAYLOAD_CAP):
            payloads.append([])
            size = 0
        payloads[-1].append(block)
        size += weight
    return payloads


def _nested_count(block: _Block) -> int:
    children: list[_Block] = block[block["type"]].get("children", [])
    return 1 + sum(_nested_count(child) for child in children)


def _block(block_type: str, payload: dict[str, Any]) -> _Block:
    return {"type": block_type, block_type: payload}


def _bullet(runs: list[_Run]) -> _Block:
    return _block("bulleted_list_item", {"rich_text": runs})


def _lecture_blocks(lecture: NoteLecture, manifest: _Manifest) -> list[_Block]:
    assets = {asset.id: asset for asset in lecture.assets}
    blocks: list[_Block] = [
        _block("heading_1", {"rich_text": _text_runs(lecture.title)}),
        _block("paragraph", {"rich_text": _text_runs(lecture.overview)}),
    ]
    if lecture.objectives:
        blocks.append(_block("paragraph", {"rich_text": [_text_run("Objectives", bold=True)]}))
        blocks.extend(_bullet(_text_runs(objective)) for objective in lecture.objectives)
    for topic in lecture.topics:
        blocks.extend(_topic_blocks(topic, assets, manifest))
    if lecture.glossary:
        blocks.append(_block("heading_2", {"rich_text": [_text_run("Glossary")]}))
        blocks.extend(_bullet(_definition_runs(entry)) for entry in lecture.glossary)
    if lecture.open_questions:
        blocks.append(_block("heading_2", {"rich_text": [_text_run("Open questions")]}))
        blocks.extend(_bullet(_text_runs(question)) for question in lecture.open_questions)
    return blocks


def _topic_blocks(
    topic: Topic, assets: dict[str, MediaAsset], manifest: _Manifest
) -> list[_Block]:
    heading_runs = [
        *_text_runs(topic.heading),
        *_text_runs(citation(topic.anchor), color="gray"),
    ]
    blocks = [_block("heading_2", {"rich_text": heading_runs})]
    for node in topic.body:
        blocks.extend(_node_blocks(node, assets, manifest))
    return blocks


def _node_blocks(
    node: Node, assets: dict[str, MediaAsset], manifest: _Manifest
) -> list[_Block]:
    match node:
        case Prose():
            return [_block("paragraph", {"rich_text": rich_text(node.text)})]
        case BulletList():
            return _bullet_list_blocks(node)
        case Definition():
            return [_block("paragraph", {"rich_text": _definition_runs(node)})]
        case Equation():
            # The label is an IR cross-reference handle, not content (P3-02's rule).
            return [_block("equation", {"expression": node.latex})]
        case CodeBlock():
            code = node.code.removesuffix("\n")
            language = node.language if node.language is not None else "plain text"
            return [_block("code", {"rich_text": _text_runs(code), "language": language})]
        case Callout():
            # The markdown renderer's ``> **EXAM** — text``, in runs: the icon alone
            # doesn't say what a kind means, so a bold label leads the text.
            emoji, color = CALLOUT_STYLE[node.kind]
            runs = [
                _text_run(node.kind.value, bold=True),
                _text_run(" — "),
                *_text_runs(node.text),
            ]
            payload = {
                "rich_text": runs,
                "icon": {"type": "emoji", "emoji": emoji},
                "color": color,
            }
            return [_block("callout", payload)]
        case Figure():
            asset = assets[node.asset_id]
            manifest.add(asset)
            image: dict[str, Any] = {
                "type": "asset_placeholder",
                "asset_placeholder": {"asset_id": asset.id},
            }
            if node.caption is not None:
                image["caption"] = _text_runs(node.caption)
            return [_block("image", image)]
        case Table():
            return [_table_block(node)]
        case Quote():
            runs = _text_runs(node.text)
            if node.attribution is not None:
                runs.extend(_text_runs(f"\n— {node.attribution}", color="gray"))
            return [_block("quote", {"rich_text": runs})]


def _bullet_list_blocks(node: BulletList) -> list[_Block]:
    """Each top item plus its flattened descendants, depth- and width-capped (P7-03).

    Descendants below the second level flatten pre-order into the depth-2 children
    array (the ``_flatten_items`` shape, local on purpose — ``model``'s helper is
    degradation's); children past the hundredth are promoted to the top level right
    after their parent, dedented but never dropped.
    """
    blocks: list[_Block] = []
    for item in node.items:
        children = [_bullet(rich_text(found.text)) for found in _descendants(item)]
        payload: dict[str, Any] = {"rich_text": rich_text(item.text)}
        if children:
            payload["children"] = children[:_CHILDREN_CAP]
        blocks.append(_block("bulleted_list_item", payload))
        blocks.extend(children[_CHILDREN_CAP:])
    return blocks


def _descendants(item: BulletItem) -> list[BulletItem]:
    found: list[BulletItem] = []
    for child in item.children:
        found.append(child)
        found.extend(_descendants(child))
    return found


def _definition_runs(definition: Definition) -> list[_Run]:
    return [*_text_runs(definition.term, bold=True), *rich_text(f": {definition.definition}")]


def _table_block(table: Table) -> _Block:
    children = [
        _block("table_row", {"cells": [rich_text(cell) for cell in row]})
        for row in [table.header, *table.rows]
    ]
    payload = {
        "table_width": len(table.header),
        "has_column_header": True,
        "has_row_header": False,
        "children": children,
    }
    return _block("table", payload)
