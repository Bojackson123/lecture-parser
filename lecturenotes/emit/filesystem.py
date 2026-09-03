"""The filesystem emitter (plan §5, stage 8): write a ``RenderResult`` to a directory.

The side-effect half of the §2.3 split — rendering stays pure, delivery lives here.
``RenderResult`` in, files out: this module never reads the IR, which is what keeps it
renderer-independent. Assets are copied only; inlining and uploading are other
emitters' strategies.
"""

from __future__ import annotations

from pathlib import Path

from lecturenotes.render.base import RenderResult, asset_target


def emit_filesystem(result: RenderResult, out_dir: Path, *, asset_root: Path = Path(".")) -> None:
    """Write every document and manifest asset under ``out_dir``, overwriting in place.

    ``asset_root`` is what ``MediaAsset.source`` paths are relative to (a P0-04
    decision: the emitter must not guess). Existing files are overwritten, never
    cleaned up: stable ids (§7.2) make re-emitting an update, not a duplicate.
    """
    for document in result.documents:
        target = out_dir / document.name
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8", newline="\n") as f:
            f.write(document.text)

    for asset in result.assets:
        source = asset_root / asset.source
        if not source.is_file():
            raise FileNotFoundError(f"asset {asset.id!r}: source not found: {source}")
        target = out_dir / asset_target(asset)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
