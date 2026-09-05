"""``emit_notion`` against ``FakeNotionTransport`` on hand-built ``RenderResult``s (P7-04).

The results are built by hand from the P7-01 payload contract and no renderer is
imported — the P3-03 doctrine, reused: the emitter consumes ``RenderResult`` and the
JSON contract only. Only ``emit.notion_api``, ``render.base`` and ``model`` may be
imported here; nothing reads environment variables and nothing touches the network.

Sequence assertions read ``transport.calls`` (the P5-01 stateful-recorder pattern);
the create-vs-replace branch is driven by seeding pages on the fake, whose ids are
minted deterministically (``page-1``, ``upload-1``, …).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from lecturenotes.emit.notion_api import FakeNotionTransport, emit_notion
from lecturenotes.model import MediaAsset
from lecturenotes.render.base import RenderedDocument, RenderResult

# The week01 figure asset, byte-identical to the fixture's (paths repo-root-relative).
FIGURE = MediaAsset(
    id="fig-value-iteration-convergence",
    media_type="image/png",
    source="tests/fixtures/decks/value_iteration.png",
)

TITLE = "CS-RL-101 — Week 1"
PARENT = "parent-page"


def _paragraph(content: str) -> dict[str, Any]:
    return {
        "type": "paragraph",
        "paragraph": {"rich_text": [{"type": "text", "text": {"content": content}}]},
    }


def _image(asset_id: str) -> dict[str, Any]:
    """An image block holding the P7-01 asset placeholder, caption included."""
    return {
        "type": "image",
        "image": {
            "type": "asset_placeholder",
            "asset_placeholder": {"asset_id": asset_id},
            "caption": [{"type": "text", "text": {"content": "Convergence per sweep."}}],
        },
    }


def _document(payloads: list[list[dict[str, Any]]], title: str = TITLE) -> RenderedDocument:
    text = json.dumps({"page": {"title": title}, "payloads": payloads}, indent=2) + "\n"
    return RenderedDocument(name="cs-rl-101-w01.notion.json", text=text)


def _result(
    payloads: list[list[dict[str, Any]]],
    assets: tuple[MediaAsset, ...] = (),
) -> RenderResult:
    return RenderResult(documents=(_document(payloads),), assets=assets)


def test_fresh_emit_creates_page_uploads_then_appends_against_the_new_page(
    repo_root: Path,
) -> None:
    fake = FakeNotionTransport()
    payload = [_paragraph("Hello"), _image(FIGURE.id)]

    emit_notion(_result([payload], assets=(FIGURE,)), fake, parent_page_id=PARENT,
                asset_root=repo_root)

    assert [call[0] for call in fake.calls] == [
        "find_child_page",
        "create_page",
        "upload_file",
        "append_children",
    ]
    assert fake.calls[0][1:] == (PARENT, TITLE)
    assert fake.calls[1][1:] == (PARENT, TITLE)
    (page_id, _appended), = fake.appended
    assert page_id == "page-1"


def test_reemit_archives_children_and_appends_to_the_same_page_with_no_create(
    repo_root: Path,
) -> None:
    fake = FakeNotionTransport()
    page_id = fake.seed_page(PARENT, TITLE, children=["block-a", "block-b"])
    payload = [_paragraph("Revised"), _image(FIGURE.id)]

    emit_notion(_result([payload], assets=(FIGURE,)), fake, parent_page_id=PARENT,
                asset_root=repo_root)

    names = [call[0] for call in fake.calls]
    assert names == [
        "find_child_page",
        "list_children",
        "archive_block",
        "archive_block",
        "upload_file",
        "append_children",
    ]
    assert "create_page" not in names
    assert fake.calls[2][1] == "block-a"
    assert fake.calls[3][1] == "block-b"
    assert fake.appended[0][0] == page_id


def test_placeholders_become_file_upload_ids_and_blocks_are_otherwise_verbatim(
    repo_root: Path,
) -> None:
    fake = FakeNotionTransport()
    payload = [_paragraph("Before"), _image(FIGURE.id), _paragraph("After")]

    emit_notion(_result([payload], assets=(FIGURE,)), fake, parent_page_id=PARENT,
                asset_root=repo_root)

    (_page_id, appended), = fake.appended
    assert appended[0] == _paragraph("Before")
    assert appended[2] == _paragraph("After")
    image = appended[1]["image"]
    assert image["type"] == "file_upload"
    assert image["file_upload"] == {"id": "upload-1"}
    assert "asset_placeholder" not in image
    assert image["caption"] == _image(FIGURE.id)["image"]["caption"]
    name, media_type, data = fake.uploaded["upload-1"]
    assert name == "fig-value-iteration-convergence.png"
    assert media_type == "image/png"
    assert data == (repo_root / FIGURE.source).read_bytes()


def test_an_asset_referenced_by_two_placeholders_uploads_once(repo_root: Path) -> None:
    fake = FakeNotionTransport()
    payload = [_image(FIGURE.id), _image(FIGURE.id)]

    emit_notion(_result([payload], assets=(FIGURE,)), fake, parent_page_id=PARENT,
                asset_root=repo_root)

    assert [call[0] for call in fake.calls].count("upload_file") == 1
    (_page_id, appended), = fake.appended
    assert appended[0]["image"]["file_upload"] == {"id": "upload-1"}
    assert appended[1]["image"]["file_upload"] == {"id": "upload-1"}


def test_empty_manifest_never_calls_upload_file() -> None:
    fake = FakeNotionTransport()

    emit_notion(_result([[_paragraph("No figures")]]), fake, parent_page_id=PARENT)

    assert "upload_file" not in [call[0] for call in fake.calls]


def test_missing_asset_source_raises_naming_the_id_before_any_transport_call(
    tmp_path: Path,
) -> None:
    fake = FakeNotionTransport()
    missing = MediaAsset(id="fig-gone", media_type="image/png", source="no/such/file.png")
    result = _result([[_image("fig-gone")]], assets=(missing,))

    with pytest.raises(FileNotFoundError, match="fig-gone"):
        emit_notion(result, fake, parent_page_id=PARENT, asset_root=tmp_path)

    assert fake.calls == []


def test_placeholder_with_no_manifest_entry_raises_naming_the_id() -> None:
    fake = FakeNotionTransport()

    with pytest.raises(ValueError, match="fig-unmapped"):
        emit_notion(_result([[_image("fig-unmapped")]]), fake, parent_page_id=PARENT)

    assert fake.calls == []


def test_two_payloads_append_in_order_against_the_same_page() -> None:
    fake = FakeNotionTransport()
    first = [_paragraph("first")]
    second = [_paragraph("second")]

    emit_notion(_result([first, second]), fake, parent_page_id=PARENT)

    assert fake.appended == [("page-1", first), ("page-1", second)]


def test_zero_notion_json_documents_is_a_value_error() -> None:
    fake = FakeNotionTransport()
    result = RenderResult(
        documents=(RenderedDocument(name="notes.md", text="# Week 1\n"),), assets=()
    )

    with pytest.raises(ValueError, match=r"\.notion\.json"):
        emit_notion(result, fake, parent_page_id=PARENT)

    assert fake.calls == []


def test_multiple_notion_json_documents_is_a_value_error() -> None:
    fake = FakeNotionTransport()
    result = RenderResult(
        documents=(
            _document([[_paragraph("one")]]),
            RenderedDocument(name="cs-rl-101-w02.notion.json", text='{"page": {}}\n'),
        ),
        assets=(),
    )

    with pytest.raises(ValueError, match=r"\.notion\.json"):
        emit_notion(result, fake, parent_page_id=PARENT)

    assert fake.calls == []
