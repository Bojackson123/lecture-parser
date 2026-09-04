"""The week-1 ``NoteWeek`` fixture: snapshot, round-trip, IR coverage, paths on disk."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from lecturenotes.model import CalloutKind, NoteWeek
from tests.fixtures.notes.week01 import JSON_PATH
from tests.fixtures.notes.week01 import week01 as build_week01

NODE_TYPES = {
    "prose",
    "bullet_list",
    "definition",
    "equation",
    "code_block",
    "callout",
    "figure",
    "table",
    "quote",
}

REGENERATE = (
    "tests/fixtures/notes/week01.json does not match week01(). If the IR change was "
    "intentional, rerun `uv run python -m tests.fixtures.notes.week01 --write` and commit."
)


def _walk(obj: Any) -> Iterator[dict[str, Any]]:
    """Every dict anywhere inside a parsed JSON document."""
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from _walk(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk(item)


def _snapshot() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    return data


def test_snapshot_matches_committed_json() -> None:
    expected = JSON_PATH.read_text(encoding="utf-8")
    actual = build_week01().model_dump_json(indent=2) + "\n"
    assert actual == expected, REGENERATE


def test_round_trip_from_json(week01: NoteWeek) -> None:
    assert NoteWeek.model_validate_json(JSON_PATH.read_text(encoding="utf-8")) == week01


def test_two_lectures() -> None:
    assert len(build_week01().lectures) == 2


def test_every_node_type_appears() -> None:
    found = {d["type"] for d in _walk(_snapshot()) if "type" in d}
    assert found == NODE_TYPES


def test_every_callout_kind_appears() -> None:
    found = {d["kind"] for d in _walk(_snapshot()) if d.get("type") == "callout"}
    assert found == {kind.value for kind in CalloutKind}


def test_both_topic_id_branches_appear(week01: NoteWeek) -> None:
    ids = [topic.id for lecture in week01.lectures for topic in lecture.topics]
    assert any(":t" in i for i in ids), ids
    assert any(":s" in i for i in ids), ids


def test_nested_bullets_table_rows_equation_label_python_code(week01: NoteWeek) -> None:
    nodes = [node for lec in week01.lectures for topic in lec.topics for node in topic.body]
    assert any(
        n.type == "bullet_list" and any(item.children for item in n.items) for n in nodes
    )
    assert any(n.type == "table" and len(n.rows) >= 2 for n in nodes)
    assert any(n.type == "equation" and n.label for n in nodes)
    assert any(n.type == "code_block" and n.language == "python" for n in nodes)


def test_cards_glossary_open_questions(week01: NoteWeek) -> None:
    # Every topic carries >= 1 card (P6-01): a cards-only deck must keep every anchor.
    assert all(topic.cards for lec in week01.lectures for topic in lec.topics)
    assert any(len(lec.glossary) >= 2 and lec.open_questions for lec in week01.lectures)


def test_referenced_source_files_exist(repo_root: Path, week01: NoteWeek) -> None:
    paths: list[str] = []
    for lecture in week01.lectures:
        paths.extend(p for p in (lecture.source.deck_path, lecture.source.caption_path) if p)
        paths.extend(asset.source for asset in lecture.assets)
    assert paths
    for rel in paths:
        assert (repo_root / rel).is_file(), rel
