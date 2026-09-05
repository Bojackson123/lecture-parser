"""PW-02: ``/api/state``, ``/api/upload``, ``/api/pair``.

The pairing endpoint exposes ``pairing.collect_pairs`` as-is — same sorted-filename
doctrine, same error messages — so whichever frontend shows the pairing, the user is
confirming the same function's output (§7.4).
"""

from __future__ import annotations

import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from lecturenotes.model import NoteWeek

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


# --- /api/state --------------------------------------------------------------------


def test_state_on_an_empty_workspace(client: TestClient) -> None:
    response = client.get("/api/state")
    assert response.status_code == 200
    body = response.json()
    assert body["weeks"] == []
    assert body["workspace"]


def test_state_lists_a_week_json_with_counts(client: TestClient, workspace: Path) -> None:
    source = FIXTURES / "notes" / "week01.json"
    shutil.copy(source, workspace / "week01.json")
    week = NoteWeek.model_validate_json(source.read_text(encoding="utf-8"))
    (entry,) = client.get("/api/state").json()["weeks"]
    assert entry["id"] == "week01"  # the filename stem addresses the week, not week.id
    assert entry["file"] == "week01.json"
    assert entry["valid"] is True
    assert entry["error"] is None
    assert entry["lectures"] == len(week.lectures)
    assert entry["topics"] == sum(len(lecture.topics) for lecture in week.lectures)


def test_state_flags_an_invalid_json_instead_of_hiding_it(
    client: TestClient, workspace: Path
) -> None:
    (workspace / "broken.json").write_text("{not json", encoding="utf-8")
    (entry,) = client.get("/api/state").json()["weeks"]
    assert entry["id"] == "broken"
    assert entry["valid"] is False
    assert entry["error"]
    assert entry["lectures"] is None


# --- /api/upload -------------------------------------------------------------------


def test_upload_stores_the_bytes_under_uploads_week(
    client: TestClient, workspace: Path
) -> None:
    deck_bytes = (FIXTURES / "decks" / "lecture01.pptx").read_bytes()
    response = client.post(
        "/api/upload?week=week-03",
        files=[("files", ("lecture01.pptx", deck_bytes))],
    )
    assert response.status_code == 200
    assert response.json() == {"paths": ["uploads/week-03/lecture01.pptx"]}
    stored = workspace / "uploads" / "week-03" / "lecture01.pptx"
    assert stored.read_bytes() == deck_bytes


def test_upload_overwrites_in_place(client: TestClient, workspace: Path) -> None:
    for payload in (b"first", b"second"):
        response = client.post(
            "/api/upload?week=w", files=[("files", ("lecture01.vtt", payload))]
        )
        assert response.status_code == 200
    assert (workspace / "uploads" / "w" / "lecture01.vtt").read_bytes() == b"second"


def test_upload_rejects_traversal_names(client: TestClient, workspace: Path) -> None:
    response = client.post(
        "/api/upload?week=w", files=[("files", ("..\\..\\evil.vtt", b"x"))]
    )
    assert response.status_code == 400
    response = client.post(
        "/api/upload?week=w", files=[("files", ("../evil.vtt", b"x"))]
    )
    assert response.status_code == 400
    assert not (workspace / "evil.vtt").exists()
    assert list((workspace / "uploads").rglob("*")) == []


def test_upload_rejects_unknown_suffixes(client: TestClient) -> None:
    response = client.post(
        "/api/upload?week=w", files=[("files", ("lecture01.mp4", b"x"))]
    )
    assert response.status_code == 400
    assert ".mp4" in response.json()["error"] or "lecture01.mp4" in response.json()["error"]


def test_upload_rejects_a_non_slug_week(client: TestClient) -> None:
    response = client.post(
        "/api/upload?week=../escape", files=[("files", ("lecture01.vtt", b"x"))]
    )
    assert response.status_code == 400


# --- /api/pair ---------------------------------------------------------------------


def _stage_pair(workspace: Path) -> list[str]:
    uploads = workspace / "uploads" / "w"
    uploads.mkdir(parents=True)
    shutil.copy(FIXTURES / "decks" / "lecture01.pptx", uploads / "lecture01.pptx")
    shutil.copy(FIXTURES / "captions" / "lecture01.vtt", uploads / "lecture01.vtt")
    return ["uploads/w/lecture01.pptx", "uploads/w/lecture01.vtt"]


def test_pair_returns_lec01_for_the_fixture_pair(
    client: TestClient, workspace: Path
) -> None:
    paths = _stage_pair(workspace)
    response = client.post("/api/pair", json={"paths": paths})
    assert response.status_code == 200
    assert response.json() == {
        "pairs": [
            {
                "lecture_id": "lec01",
                "deck": "uploads/w/lecture01.pptx",
                "captions": "uploads/w/lecture01.vtt",
            }
        ]
    }


def test_pair_accepts_a_directory_path(client: TestClient, workspace: Path) -> None:
    _stage_pair(workspace)
    response = client.post("/api/pair", json={"paths": ["uploads/w"]})
    assert response.status_code == 200
    (pair,) = response.json()["pairs"]
    assert pair["lecture_id"] == "lec01"


def test_pair_mismatch_returns_the_collect_pairs_message_verbatim(
    client: TestClient, workspace: Path
) -> None:
    uploads = workspace / "uploads" / "w"
    uploads.mkdir(parents=True)
    shutil.copy(FIXTURES / "decks" / "lecture01.pptx", uploads / "lecture01.pptx")
    shutil.copy(FIXTURES / "decks" / "lecture01.pdf", uploads / "lecture02.pdf")
    shutil.copy(FIXTURES / "captions" / "lecture01.vtt", uploads / "lecture01.vtt")
    response = client.post("/api/pair", json={"paths": ["uploads/w"]})
    assert response.status_code == 422
    assert response.json()["error"] == (
        "2 deck(s) but 1 caption file(s); every deck needs exactly one caption file."
        " decks: lecture01.pptx, lecture02.pdf. captions: lecture01.vtt"
    )


def test_pair_empty_directory_is_422(client: TestClient, workspace: Path) -> None:
    (workspace / "empty").mkdir()
    response = client.post("/api/pair", json={"paths": ["empty"]})
    assert response.status_code == 422
    assert response.json()["error"] == "no decks or caption files found"
