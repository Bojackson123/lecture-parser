"""``MarkdownRenderer``: a ``NoteWeek`` as one markdown week page (plan §5, P3-02).

The format spec is the hand-written ``tests/fixtures/notes/week01.md``; every
formatting decision here is reviewable there. One page per week, named
``{week.id}.md`` — the week id is stable, so re-emitting updates one file in place
(plan §7.2). The heading ladder — ``#`` week, ``##`` lecture, ``###`` topic — is what
makes one page workable.

Markdown is native to all six capabilities, so ``degrade()`` is a no-op for this
renderer. ``CardSeed``s are invisible on purpose (plan §2.2): cards are the Anki
target's input. Equation labels are IR cross-reference handles, not content, and are
not rendered. Only ``|`` is escaped, and only inside table cells — the IR's text is
markdown-safe by construction, and a general escaping pass would mangle inline math.
"""

from __future__ import annotations

from lecturenotes.model import (
    BulletItem,
    BulletList,
    Callout,
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
    Table,
    Topic,
)
from lecturenotes.render.base import (
    RenderedDocument,
    RenderOptions,
    RenderResult,
    asset_target,
    format_clock,
)


class MarkdownRenderer:
    """Renders a week to one markdown page. Pure string building — no IO."""

    name = "markdown"
    capabilities = set(Capability)

    def render(self, week: NoteWeek, opts: RenderOptions) -> RenderResult:
        manifest = _Manifest()
        blocks = [f"# {week.course} — Week {week.week_number}"]
        for lecture in week.lectures:
            blocks.extend(_lecture_blocks(lecture, manifest))
        text = "\n\n".join(blocks) + "\n"
        document = RenderedDocument(name=f"{week.id}.md", text=text)
        return RenderResult(documents=(document,), assets=tuple(manifest.assets))


class _Manifest:
    """Assets in first-reference order, each once."""

    def __init__(self) -> None:
        self.assets: list[MediaAsset] = []
        self._seen: set[str] = set()

    def add(self, asset: MediaAsset) -> None:
        if asset.id not in self._seen:
            self._seen.add(asset.id)
            self.assets.append(asset)


def _lecture_blocks(lecture: NoteLecture, manifest: _Manifest) -> list[str]:
    assets = {asset.id: asset for asset in lecture.assets}
    blocks = [f"## {lecture.title}", lecture.overview]
    if lecture.objectives:
        blocks.append("**Objectives**")
        blocks.append("\n".join(f"- {objective}" for objective in lecture.objectives))
    for topic in lecture.topics:
        blocks.extend(_topic_blocks(topic, assets, manifest))
    if lecture.glossary:
        blocks.append("### Glossary")
        blocks.append(
            "\n".join(f"- **{d.term}** — {d.definition}" for d in lecture.glossary)
        )
    if lecture.open_questions:
        blocks.append("### Open questions")
        blocks.append("\n".join(f"- {question}" for question in lecture.open_questions))
    return blocks


def _topic_blocks(
    topic: Topic, assets: dict[str, MediaAsset], manifest: _Manifest
) -> list[str]:
    blocks = [f"### {topic.heading}", _anchor_line(topic)]
    blocks.extend(_node_block(node, assets, manifest) for node in topic.body)
    return blocks


def _anchor_line(topic: Topic) -> str:
    anchor = topic.anchor
    line = f"[{format_clock(anchor.start_s)}–{format_clock(anchor.end_s)}"
    if anchor.slides is not None:
        if anchor.slides.start == anchor.slides.end:
            line += f" · slide {anchor.slides.start}"
        else:
            line += f" · slides {anchor.slides.start}–{anchor.slides.end}"
    return line + "]"


def _node_block(node: Node, assets: dict[str, MediaAsset], manifest: _Manifest) -> str:
    match node:
        case Prose():
            return node.text
        case BulletList():
            return "\n".join(_bullet_lines(node.items, depth=0))
        case Definition():
            return f"**{node.term}** — {node.definition}"
        case Equation():
            return f"$$\n{node.latex}\n$$"
        case CodeBlock():
            fence = f"```{node.language}" if node.language else "```"
            code = node.code.removesuffix("\n")
            return f"{fence}\n{code}\n```"
        case Callout():
            return f"> **{node.kind.value}** — {node.text}"
        case Figure():
            asset = assets[node.asset_id]
            manifest.add(asset)
            image = f"![{asset.alt or ''}]({asset_target(asset)})"
            return image if node.caption is None else f"{image}\n*{node.caption}*"
        case Table():
            return _table_block(node)
        case Quote():
            lines = [f"> {node.text}"]
            if node.attribution is not None:
                lines.append(f"> — {node.attribution}")
            return "\n".join(lines)


def _bullet_lines(items: list[BulletItem], depth: int) -> list[str]:
    lines: list[str] = []
    for item in items:
        lines.append(f"{'  ' * depth}- {item.text}")
        lines.extend(_bullet_lines(item.children, depth + 1))
    return lines


def _table_block(table: Table) -> str:
    def row(cells: list[str]) -> str:
        return "| " + " | ".join(cell.replace("|", r"\|") for cell in cells) + " |"

    separator = "| " + " | ".join("---" for _ in table.header) + " |"
    return "\n".join([row(table.header), separator, *(row(r) for r in table.rows)])
