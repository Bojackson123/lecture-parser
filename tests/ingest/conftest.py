"""Caption fixture text shared by the ``tests/ingest`` modules."""

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def vtt_text(fixtures_dir: Path) -> str:
    return (fixtures_dir / "captions" / "lecture01.vtt").read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def srt_text(fixtures_dir: Path) -> str:
    return (fixtures_dir / "captions" / "lecture01.srt").read_text(encoding="utf-8")
