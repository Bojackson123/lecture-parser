"""The note IR: NoteWeek, Topic, Node types, capabilities, degrade() (plan §2, §5).

Boundary rule: this package imports nothing else in ``lecturenotes``.
"""

from lecturenotes.model.capabilities import Capability
from lecturenotes.model.ids import topic_id
from lecturenotes.model.nodes import (
    BulletItem,
    BulletList,
    Callout,
    CalloutKind,
    CodeBlock,
    Definition,
    Equation,
    Figure,
    Node,
    Prose,
    Quote,
    Table,
)
from lecturenotes.model.notes import CardSeed, NoteLecture, NoteWeek, Topic
from lecturenotes.model.source import MediaAsset, SlideRange, SourceAnchor, SourceRef

__all__ = [
    "BulletItem",
    "BulletList",
    "Callout",
    "CalloutKind",
    "Capability",
    "CardSeed",
    "CodeBlock",
    "Definition",
    "Equation",
    "Figure",
    "MediaAsset",
    "Node",
    "NoteLecture",
    "NoteWeek",
    "Prose",
    "Quote",
    "SlideRange",
    "SourceAnchor",
    "SourceRef",
    "Table",
    "Topic",
    "topic_id",
]
