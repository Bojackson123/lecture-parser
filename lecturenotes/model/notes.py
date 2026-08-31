"""The document-level IR: ``NoteWeek`` → ``NoteLecture`` → ``Topic`` (plan §2.2)."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, model_validator

from lecturenotes.model.nodes import Definition, Figure, Node
from lecturenotes.model.source import MediaAsset, SourceAnchor, SourceRef


class _NotesModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _duplicates(ids: Iterable[str]) -> list[str]:
    return sorted(value for value, n in Counter(ids).items() if n > 1)


class CardSeed(_NotesModel):
    """A Q/A pair for spaced-repetition targets.

    Generated alongside the notes and ignored by document renderers; makes the Anki
    target trivial later without a separate extraction pass.
    """

    front: str
    back: str
    tags: list[str] = []


class Topic(_NotesModel):
    """One section of a lecture's notes.

    ``id`` is stable across regeneration — see ``lecturenotes.model.ids.topic_id``.
    """

    id: str
    heading: str
    anchor: SourceAnchor
    body: list[Node]
    cards: list[CardSeed] = []


class NoteLecture(_NotesModel):
    """Notes for a single lecture.

    ``assets`` live here rather than on ``NoteWeek`` because slide ingest is per
    lecture (plan §7.3), which keeps the ``Figure.asset_id`` check local.
    """

    id: str
    title: str
    overview: str
    objectives: list[str]
    source: SourceRef
    topics: list[Topic]
    glossary: list[Definition] = []
    open_questions: list[str] = []
    assets: list[MediaAsset] = []

    @model_validator(mode="after")
    def _figures_resolve_to_unique_assets(self) -> NoteLecture:
        dupes = _duplicates(asset.id for asset in self.assets)
        if dupes:
            raise ValueError(f"duplicate asset id(s): {', '.join(dupes)}")
        known = {asset.id for asset in self.assets}
        missing = sorted(
            {
                node.asset_id
                for topic in self.topics
                for node in topic.body
                if isinstance(node, Figure) and node.asset_id not in known
            }
        )
        if missing:
            raise ValueError(f"figure(s) reference unknown asset id(s): {', '.join(missing)}")
        return self


class NoteWeek(_NotesModel):
    """A week of a course: the unit the pipeline produces and renderers consume."""

    id: str
    course: str
    week_number: int
    lectures: list[NoteLecture]

    @model_validator(mode="after")
    def _lecture_ids_unique(self) -> NoteWeek:
        dupes = _duplicates(lecture.id for lecture in self.lectures)
        if dupes:
            raise ValueError(f"duplicate lecture id(s): {', '.join(dupes)}")
        return self
