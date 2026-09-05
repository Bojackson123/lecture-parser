"""Sanity pins on the hand-written Notion payload spec (P7-01).

No renderer exists yet: these tests pin ``tests/fixtures/notes/week01.notion.json``,
the file P7-02 implements to byte-equality and P7-04 posts verbatim. Spec decisions
recorded with the fixture:

- One document per week, named ``{week.id}.notion.json`` → ``cs-rl-101-w01.notion.json``
  (the §7.2 stable-name pattern; the name lives in P7-02's renderer).
- Top level is exactly ``{"page": {"title": …}, "payloads": [[block, …], …]}`` — each
  payload one Notion append-request ``children`` array, each block a Notion API block
  object verbatim. The title comes from ``course`` + ``week_number``, never lecture
  titles, so P7-04 can key update-not-duplicate on it.
- The one deliberate non-Notion shape is the ``asset_placeholder`` image source:
  renderers are pure (P3-01), so the emitter resolves it after uploading (P7-04).
- Serialization is ``json.dumps(indent=2, ensure_ascii=False)`` + one trailing
  newline — what P7-02 must reproduce byte-for-byte.

The file is hand-written and never regenerated from the code under test; if the
format changes on purpose, edit it deliberately.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from lecturenotes.model import Figure, NoteWeek
from lecturenotes.render.base import format_clock

FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "notes" / "week01.notion.json"
)


@pytest.fixture(scope="module")
def raw() -> bytes:
    return FIXTURE.read_bytes()


@pytest.fixture(scope="module")
def document() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _blocks(node: Any) -> list[dict[str, Any]]:
    """Every block object in the document, nested children included."""
    found: list[dict[str, Any]] = []
    if isinstance(node, dict):
        if "type" in node:
            found.append(node)
        for value in node.values():
            found.extend(_blocks(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_blocks(item))
    return found


# --- shape ------------------------------------------------------------------------------


def test_top_level_is_exactly_page_and_payloads(document: dict[str, Any]) -> None:
    assert sorted(document) == ["page", "payloads"]
    assert document["page"] == {"title": "CS-RL-101 — Week 1"}


def test_week01_fits_in_one_payload(document: dict[str, Any]) -> None:
    assert len(document["payloads"]) == 1
    assert isinstance(document["payloads"][0], list)


# --- anchors ----------------------------------------------------------------------------


def test_every_topic_clock_appears_in_the_serialized_text(
    raw: bytes, week01: NoteWeek
) -> None:
    # Property 4's grep for format_clock output will hit this file too.
    text = raw.decode("utf-8")
    for lecture in week01.lectures:
        for topic in lecture.topics:
            assert format_clock(topic.anchor.start_s) in text, topic.id


def test_slide_range_citation_uses_en_dash(document: dict[str, Any]) -> None:
    # The P6-01 citation grammar: clock, then · slide N / · slides N–M / nothing.
    citations = [
        run["text"]["content"]
        for block in _blocks(document["payloads"][0])
        if block["type"] == "heading_2"
        for run in block["heading_2"]["rich_text"]
        if run.get("annotations", {}).get("color") == "gray"
    ]
    assert "  3:00 · slides 2–3" in citations
    assert "  2:31" in citations  # the gap topic cites no slide


# --- the asset placeholder --------------------------------------------------------------


def test_exactly_one_asset_placeholder_with_the_week01_figure_id(
    document: dict[str, Any], week01: NoteWeek
) -> None:
    figure_ids = [
        node.asset_id
        for lecture in week01.lectures
        for topic in lecture.topics
        for node in topic.body
        if isinstance(node, Figure)
    ]
    assert len(figure_ids) == 1
    images = [b for b in _blocks(document["payloads"][0]) if b["type"] == "image"]
    assert len(images) == 1
    image = images[0]["image"]
    assert image["type"] == "asset_placeholder"
    assert image["asset_placeholder"] == {"asset_id": figure_ids[0]}


# --- bytes ------------------------------------------------------------------------------


def test_file_is_utf8_lf_with_one_trailing_newline(raw: bytes) -> None:
    assert b"\r" not in raw
    assert raw.endswith(b"\n")
    assert not raw.endswith(b"\n\n")
    text = raw.decode("utf-8")  # strict: raises on mojibake
    assert "–" in text  # en-dashes intact
