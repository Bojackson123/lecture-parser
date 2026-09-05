"""PW-03: ``/api/dry-run`` — the chunk preview that spends nothing.

The P5-04 ``no_client`` doctrine, ported: every test here arms a raising client
seam and deletes ``ANTHROPIC_API_KEY``, so the endpoint provably constructs no
client and consults no key. The chunking is the same ``merge_chunks`` call and
floor the real run uses.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import lecturenotes.web.app as web_app
from lecturenotes.align import align_lecture
from lecturenotes.generate.lecture import merge_chunks
from lecturenotes.ingest.captions import ingest_captions
from lecturenotes.ingest.slides import ingest_slides

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
PPTX = FIXTURES / "decks" / "lecture01.pptx"
VTT = FIXTURES / "captions" / "lecture01.vtt"


@pytest.fixture
def no_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """Any client construction is a test failure — and no key must ever be consulted."""

    def boom(model: str) -> object:
        raise AssertionError("a client was constructed")

    monkeypatch.setattr(web_app, "_make_client", boom)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def _stage(workspace: Path) -> list[str]:
    uploads = workspace / "uploads" / "w"
    uploads.mkdir(parents=True)
    shutil.copy(PPTX, uploads / "lecture01.pptx")
    shutil.copy(VTT, uploads / "lecture01.vtt")
    return ["uploads/w"]


def test_dry_run_4_chunks_one_gap_5_requests_with_no_client(
    client: TestClient, workspace: Path, no_client: None
) -> None:
    response = client.post("/api/dry-run", json={"paths": _stage(workspace)})
    assert response.status_code == 200
    body = response.json()
    assert body["total_requests"] == 5  # 4 merged chunks + 1 synthesis (§7.1 budget)
    (lecture,) = body["lectures"]
    assert lecture["lecture_id"] == "lec01"
    chunks = lecture["chunks"]
    assert len(chunks) == 4
    assert sum(chunk["gap"] for chunk in chunks) == 1
    for chunk in chunks:
        assert chunk["gap"] == (chunk["slides"] is None)
        if chunk["gap"]:
            assert chunk["title"] is None


def test_dry_run_matches_the_real_runs_chunking(
    client: TestClient, workspace: Path, no_client: None
) -> None:
    """Field-for-field against the library composition the real build prompts over."""
    response = client.post("/api/dry-run", json={"paths": _stage(workspace)})
    expected = merge_chunks(align_lecture(ingest_slides(PPTX), ingest_captions(VTT)), 100)
    (lecture,) = response.json()["lectures"]
    assert len(lecture["chunks"]) == len(expected)
    for got, chunk in zip(lecture["chunks"], expected, strict=True):
        assert got["start_s"] == chunk.start_s
        assert got["end_s"] == chunk.end_s
        assert got["words"] == sum(len(s.text.split()) for s in chunk.segments)
        if chunk.slides is None:
            assert got["slides"] is None
        else:
            assert got["slides"] == {"start": chunk.slides.start, "end": chunk.slides.end}


def test_dry_run_word_counts_are_the_merge_floor_counts(
    client: TestClient, workspace: Path, no_client: None
) -> None:
    """The P5-02 fixture weights: the numbers shown explain the merges you get."""
    response = client.post("/api/dry-run", json={"paths": _stage(workspace)})
    (lecture,) = response.json()["lectures"]
    assert sorted(chunk["words"] for chunk in lecture["chunks"]) == [81, 103, 103, 120]


def test_dry_run_min_words_merges_and_the_gap_fences(
    client: TestClient, workspace: Path, no_client: None
) -> None:
    response = client.post(
        "/api/dry-run", json={"paths": _stage(workspace), "min_words": 200}
    )
    (lecture,) = response.json()["lectures"]
    chunks = lecture["chunks"]
    assert len(chunks) < 4
    assert sum(chunk["gap"] for chunk in chunks) == 1  # never merged away
    assert response.json()["total_requests"] == len(chunks) + 1


def test_dry_run_pairing_error_is_422(
    client: TestClient, workspace: Path, no_client: None
) -> None:
    response = client.post("/api/dry-run", json={"paths": []})
    assert response.status_code == 422
    assert response.json()["error"] == "no decks or caption files found"


def test_dry_run_missing_file_is_422_with_the_message(
    client: TestClient, workspace: Path, no_client: None
) -> None:
    response = client.post(
        "/api/dry-run",
        json={"paths": ["uploads/missing.pptx", "uploads/missing.vtt"]},
    )
    assert response.status_code == 422
    assert response.json()["error"]
