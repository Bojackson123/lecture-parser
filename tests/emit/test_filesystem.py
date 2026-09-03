"""``emit_filesystem`` against hand-built ``RenderResult`` values (P3-03).

The results are built by hand and no renderer is imported: the emitter consumes
``RenderResult`` and nothing else, the mirror of the contract tests proving renderers
never touch an emitter. Only ``emit.filesystem``, ``render.base`` and ``model`` may be
imported here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lecturenotes.emit.filesystem import emit_filesystem
from lecturenotes.model import MediaAsset
from lecturenotes.render.base import RenderedDocument, RenderResult, asset_target

# The week01 figure asset, byte-identical to the fixture's (paths repo-root-relative).
FIGURE = MediaAsset(
    id="fig-value-iteration-convergence",
    media_type="image/png",
    source="tests/fixtures/decks/value_iteration.png",
)

# En-dash and LaTeX: the bytes that catch a wrong encoding or newline translation.
NOTES_TEXT = "# Week 1\n\nDiscounting — the factor $\\gamma$ weights future reward.\n"
APPENDIX_TEXT = "# Appendix\n\nProofs live here.\n"


def _result(
    documents: tuple[RenderedDocument, ...],
    assets: tuple[MediaAsset, ...] = (),
) -> RenderResult:
    return RenderResult(documents=documents, assets=assets)


def _two_documents() -> RenderResult:
    return _result(
        (
            RenderedDocument(name="notes.md", text=NOTES_TEXT),
            RenderedDocument(name="extra/appendix.md", text=APPENDIX_TEXT),
        )
    )


def test_documents_land_at_their_names_with_exact_utf8_lf_bytes(tmp_path: Path) -> None:
    emit_filesystem(_two_documents(), tmp_path)

    notes = (tmp_path / "notes.md").read_bytes()
    appendix = (tmp_path / "extra" / "appendix.md").read_bytes()
    assert notes == NOTES_TEXT.encode("utf-8")
    assert appendix == APPENDIX_TEXT.encode("utf-8")
    assert not notes.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in notes
    assert b"\r" not in appendix


def test_manifest_asset_is_copied_byte_for_byte_to_asset_target(
    tmp_path: Path, repo_root: Path
) -> None:
    result = _result(
        (RenderedDocument(name="notes.md", text=NOTES_TEXT),),
        assets=(FIGURE,),
    )

    emit_filesystem(result, tmp_path, asset_root=repo_root)

    written = tmp_path / asset_target(FIGURE)
    assert written == tmp_path / "assets" / "fig-value-iteration-convergence.png"
    assert written.read_bytes() == (repo_root / FIGURE.source).read_bytes()


def test_reemit_overwrites_in_place_and_leaves_no_extra_files(tmp_path: Path) -> None:
    emit_filesystem(_two_documents(), tmp_path)
    changed = _result(
        (
            RenderedDocument(name="notes.md", text="# Week 1, revised\n"),
            RenderedDocument(name="extra/appendix.md", text=APPENDIX_TEXT),
        )
    )

    emit_filesystem(changed, tmp_path)

    assert (tmp_path / "notes.md").read_text(encoding="utf-8") == "# Week 1, revised\n"
    files = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file())
    assert files == ["extra/appendix.md", "notes.md"]


def test_empty_manifest_creates_no_assets_directory(tmp_path: Path) -> None:
    emit_filesystem(_result((RenderedDocument(name="notes.md", text=NOTES_TEXT),)), tmp_path)

    assert not (tmp_path / "assets").exists()


def test_missing_asset_source_raises_naming_the_asset_id(tmp_path: Path) -> None:
    missing = MediaAsset(id="fig-gone", media_type="image/png", source="no/such/file.png")
    result = _result(
        (RenderedDocument(name="notes.md", text=NOTES_TEXT),),
        assets=(missing,),
    )

    with pytest.raises(FileNotFoundError, match="fig-gone"):
        emit_filesystem(result, tmp_path, asset_root=tmp_path)

    assert not (tmp_path / asset_target(missing)).exists()
