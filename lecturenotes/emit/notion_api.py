"""The Notion emitter (plan §5, stage 8): deliver a ``RenderResult`` to a workspace.

The side-effect half of the §2.3 split, aimed at an API instead of a directory: find
or create the week's page under a parent, resolve the P7-01 asset placeholders by
uploading, append the payloads verbatim. §7.2's update-not-duplicate holds at the
page level — a re-emit updates the same page at the same URL, never a sibling.

All IO goes through the ``NotionTransport`` seam; ``FakeNotionTransport`` is the
in-package stateful recorder tests drive (the P5-01 client pattern), so no test
touches the network. This module never reads the environment — the token is a
``UrllibTransport`` constructor parameter and P7-05 owns ``NOTION_TOKEN``.

Decisions (P7-04):

- **Title is the page identity.** The title derives from ``course`` + ``week_number``
  (P7-01), which prompt tuning, model switches and regeneration never change.
  Renaming the course is deliberately a new page — identity comes from the stable
  coordinates, and changing those coordinates *should* fork. No local state file, no
  marker block: the page you can see is the whole truth.
- **Replace-children, not block-diff.** Archive-then-append keeps the page id and
  URL stable — the §7.2 property a user can observe — at the cost of block-level
  history and comments on re-emit. A diff would need stable block identities the
  payload format doesn't carry.
- **Fail before touching Notion.** Placeholders are checked against the manifest and
  every asset is read from disk (once per asset) before the first transport call, so
  a renderer bug or a missing file aborts with the workspace untouched — a
  half-written page is this emitter's worst failure mode.
- **Upload names are id-keyed via ``asset_target``** (the P3-01 helper), so the name
  a file carries in Notion cannot drift from the name the filesystem emitter writes.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol, cast

from lecturenotes.render.base import RenderResult, asset_target

__all__ = [
    "FakeNotionTransport",
    "NotionTransport",
    "UrllibTransport",
    "emit_notion",
]

_Block = dict[str, Any]


class NotionTransport(Protocol):
    """The six calls the emitter needs and nothing more (plan §8)."""

    def find_child_page(self, parent_id: str, title: str) -> str | None: ...

    def create_page(self, parent_id: str, title: str) -> str: ...

    def list_children(self, block_id: str) -> list[str]: ...

    def archive_block(self, block_id: str) -> None: ...

    def append_children(self, block_id: str, children: list[_Block]) -> None: ...

    def upload_file(self, name: str, media_type: str, data: bytes) -> str: ...


def emit_notion(
    result: RenderResult,
    transport: NotionTransport,
    *,
    parent_page_id: str,
    asset_root: Path = Path("."),
) -> None:
    """Deliver ``result``'s one ``.notion.json`` document under ``parent_page_id``.

    ``asset_root`` is what ``MediaAsset.source`` paths are relative to (the P3-03
    rule: the emitter must not guess; P7-05's ``push`` passes the week JSON's
    directory). No return value — stage 8 is side effects (plan §3).
    """
    documents = [d for d in result.documents if d.name.endswith(".notion.json")]
    if len(documents) != 1:
        raise ValueError(
            f"expected exactly one .notion.json document, found {len(documents)}"
        )
    payload_doc = json.loads(documents[0].text)
    title: str = payload_doc["page"]["title"]
    payloads: list[list[_Block]] = payload_doc["payloads"]

    manifest = {asset.id: asset for asset in result.assets}
    for asset_id in _placeholder_ids(payloads):
        if asset_id not in manifest:
            raise ValueError(f"asset placeholder {asset_id!r} matches no manifest asset")

    contents: dict[str, bytes] = {}
    for asset in result.assets:
        source = asset_root / asset.source
        if not source.is_file():
            raise FileNotFoundError(f"asset {asset.id!r}: source not found: {source}")
        contents[asset.id] = source.read_bytes()

    page_id = transport.find_child_page(parent_page_id, title)
    if page_id is None:
        page_id = transport.create_page(parent_page_id, title)
    else:
        for child_id in transport.list_children(page_id):
            transport.archive_block(child_id)

    uploads = {
        asset.id: transport.upload_file(
            asset_target(asset).rpartition("/")[2], asset.media_type, contents[asset.id]
        )
        for asset in result.assets
    }

    for payload in payloads:
        transport.append_children(page_id, [_resolve(block, uploads) for block in payload])


def _placeholder_ids(node: object) -> Iterator[str]:
    if isinstance(node, dict):
        if node.get("type") == "asset_placeholder":
            yield str(node["asset_placeholder"]["asset_id"])
        for value in node.values():
            yield from _placeholder_ids(value)
    elif isinstance(node, list):
        for item in node:
            yield from _placeholder_ids(item)


def _resolve(node: object, uploads: Mapping[str, str]) -> Any:
    """The node with every placeholder swapped for its ``file_upload`` reference.

    The placeholder is the ``type``/``asset_placeholder`` key pair; sibling keys
    (the image caption) and everything else pass through verbatim, in order.
    """
    if isinstance(node, dict):
        if node.get("type") == "asset_placeholder":
            upload_id = uploads[str(node["asset_placeholder"]["asset_id"])]
            resolved: _Block = {}
            for key, value in node.items():
                if key == "type":
                    resolved["type"] = "file_upload"
                elif key == "asset_placeholder":
                    resolved["file_upload"] = {"id": upload_id}
                else:
                    resolved[key] = _resolve(value, uploads)
            return resolved
        return {key: _resolve(value, uploads) for key, value in node.items()}
    if isinstance(node, list):
        return [_resolve(item, uploads) for item in node]
    return node


class FakeNotionTransport:
    """The stateful recorder tests drive (the P5-01 ``RecordedClient`` reasoning:
    the seam is the test surface, and the suite must stay hermetic).

    Every call lands in ``calls`` as ``(name, *args)``; ids are minted
    deterministically (``page-1``, ``page-2``, …, ``upload-1``, …). Seed the
    create-vs-replace branch with ``seed_page`` — seeding records no call.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []
        self.appended: list[tuple[str, list[_Block]]] = []
        self.archived: list[str] = []
        self.uploaded: dict[str, tuple[str, str, bytes]] = {}
        self._pages: dict[tuple[str, str], str] = {}
        self._children: dict[str, list[str]] = {}
        self._next_page = 1
        self._next_upload = 1

    def seed_page(self, parent_id: str, title: str, *, children: Sequence[str] = ()) -> str:
        """Pre-existing page under ``parent_id``; returns its minted id."""
        page_id = self._mint_page()
        self._pages[(parent_id, title)] = page_id
        self._children[page_id] = list(children)
        return page_id

    def find_child_page(self, parent_id: str, title: str) -> str | None:
        self.calls.append(("find_child_page", parent_id, title))
        return self._pages.get((parent_id, title))

    def create_page(self, parent_id: str, title: str) -> str:
        self.calls.append(("create_page", parent_id, title))
        page_id = self._mint_page()
        self._pages[(parent_id, title)] = page_id
        self._children[page_id] = []
        return page_id

    def list_children(self, block_id: str) -> list[str]:
        self.calls.append(("list_children", block_id))
        return list(self._children.get(block_id, []))

    def archive_block(self, block_id: str) -> None:
        self.calls.append(("archive_block", block_id))
        self.archived.append(block_id)
        for children in self._children.values():
            if block_id in children:
                children.remove(block_id)

    def append_children(self, block_id: str, children: list[_Block]) -> None:
        self.calls.append(("append_children", block_id, children))
        self.appended.append((block_id, children))

    def upload_file(self, name: str, media_type: str, data: bytes) -> str:
        self.calls.append(("upload_file", name, media_type, data))
        upload_id = f"upload-{self._next_upload}"
        self._next_upload += 1
        self.uploaded[upload_id] = (name, media_type, data)
        return upload_id

    def _mint_page(self) -> str:
        page_id = f"page-{self._next_page}"
        self._next_page += 1
        return page_id


_API_ROOT = "https://api.notion.com/v1"
_NOTION_VERSION = "2022-06-28"


class UrllibTransport:
    """The real transport, on stdlib ``urllib`` (decided 2026-09-04: no new
    dependency). Thin and dumb — every branch worth testing lives above the seam;
    the real thing is exercised once, manually, in P7-05's done-gate.

    The token is a parameter: this module never reads the environment. Any non-2xx
    response raises with the status and response body in the message.
    """

    def __init__(self, token: str) -> None:
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": _NOTION_VERSION,
        }

    def find_child_page(self, parent_id: str, title: str) -> str | None:
        for block in self._child_blocks(parent_id):
            if block.get("type") == "child_page" and block["child_page"]["title"] == title:
                return str(block["id"])
        return None

    def create_page(self, parent_id: str, title: str) -> str:
        page = self._json(
            "POST",
            "/pages",
            {
                "parent": {"page_id": parent_id},
                "properties": {"title": [{"type": "text", "text": {"content": title}}]},
            },
        )
        return str(page["id"])

    def list_children(self, block_id: str) -> list[str]:
        return [str(block["id"]) for block in self._child_blocks(block_id)]

    def archive_block(self, block_id: str) -> None:
        self._json("PATCH", f"/blocks/{block_id}", {"archived": True})

    def append_children(self, block_id: str, children: list[_Block]) -> None:
        self._json("PATCH", f"/blocks/{block_id}/children", {"children": children})

    def upload_file(self, name: str, media_type: str, data: bytes) -> str:
        # The File Upload API: create the upload, then send the bytes as the one
        # "file" part of a hand-rolled multipart body.
        upload = self._json(
            "POST", "/file_uploads", {"filename": name, "content_type": media_type}
        )
        upload_id = str(upload["id"])
        boundary = uuid.uuid4().hex
        head = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{name}"\r\n'
            f"Content-Type: {media_type}\r\n\r\n"
        ).encode()
        tail = f"\r\n--{boundary}--\r\n".encode()
        self._send(
            "POST",
            f"/file_uploads/{upload_id}/send",
            head + data + tail,
            f"multipart/form-data; boundary={boundary}",
        )
        return upload_id

    def _child_blocks(self, block_id: str) -> Iterator[_Block]:
        cursor: str | None = None
        while True:
            query = "?page_size=100" + (f"&start_cursor={cursor}" if cursor else "")
            page = self._json("GET", f"/blocks/{block_id}/children{query}", None)
            results: list[_Block] = page["results"]
            yield from results
            if not page.get("has_more"):
                return
            cursor = str(page["next_cursor"])

    def _json(self, method: str, path: str, payload: _Block | None) -> _Block:
        body = None if payload is None else json.dumps(payload).encode()
        content_type = None if payload is None else "application/json"
        return cast(_Block, json.loads(self._send(method, path, body, content_type)))

    def _send(
        self, method: str, path: str, body: bytes | None, content_type: str | None
    ) -> bytes:
        request = urllib.request.Request(_API_ROOT + path, data=body, method=method)
        for header, value in self._headers.items():
            request.add_header(header, value)
        if content_type is not None:
            request.add_header("Content-Type", content_type)
        try:
            with urllib.request.urlopen(request) as response:
                return cast(bytes, response.read())
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Notion API {method} {path} failed: {error.code} {detail}"
            ) from None
