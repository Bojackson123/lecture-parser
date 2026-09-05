"""P5-03 entrypoint tests: ``generate_lecture()`` on the real pipeline output with the
recorded fake equals the hand-written ``lecture01.notes.json`` — the two halves of the
pipeline meet in the middle — in exactly 5 requests, minting exactly the referenced
asset.

Everything runs through the real entrypoints (the conftest fixtures: ``ingest_slides``
on the PPTX, ``ingest_captions`` on the VTT, ``align_lecture``); the expected
``NoteLecture`` is never regenerated from the code under test.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import ValidationError

from lecturenotes.align import Chunk
from lecturenotes.generate.client import GenRequest, LLMClient, RecordedClient
from lecturenotes.generate.lecture import generate_lecture
from lecturenotes.ingest.slides import Deck
from lecturenotes.model import NoteLecture, SourceRef

PPTX_IMAGE_ID = "img-a63ae9b7dc5e9397"
MEDIA_NAME = f"{PPTX_IMAGE_ID}.png"

# The fixture's pinned source: the files the fake pipeline actually consumes.
SOURCE = SourceRef(
    deck_path="tests/fixtures/decks/lecture01.pptx",
    caption_path="tests/fixtures/captions/lecture01.vtt",
)


class CountingClient:
    """Wraps a client and counts ``complete`` calls — the §7.1 request budget."""

    def __init__(self, inner: LLMClient) -> None:
        self.model = inner.model
        self.calls = 0
        self._inner = inner

    def complete(self, request: GenRequest) -> str:
        self.calls += 1
        return self._inner.complete(request)


def _generate(
    deck: Deck, chunks: list[Chunk], client: LLMClient, out_dir: Path
) -> NoteLecture:
    return generate_lecture(
        deck, chunks, lecture_id="lec01", source=SOURCE, client=client, out_dir=out_dir
    )


@pytest.fixture(scope="module")
def client(responses_path: Path) -> RecordedClient:
    return RecordedClient(responses_path)


@pytest.fixture
def expected(fixtures_dir: Path) -> NoteLecture:
    path = fixtures_dir / "generate" / "lecture01.notes.json"
    return NoteLecture.model_validate_json(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def image_bytes(deck: Deck) -> bytes:
    return next(image.data for image in deck.assets if image.id == PPTX_IMAGE_ID)


# --- the fixture run ----------------------------------------------------------------


def test_generate_lecture_equals_the_notes_fixture(
    deck: Deck,
    chunks: list[Chunk],
    client: RecordedClient,
    expected: NoteLecture,
    tmp_path: Path,
) -> None:
    """Full structural equality, glossary and open questions included."""
    lecture = _generate(deck, chunks, client, tmp_path)
    assert lecture == expected
    assert lecture.glossary == expected.glossary
    assert lecture.open_questions == expected.open_questions


def test_only_the_referenced_image_is_minted(
    deck: Deck,
    chunks: list[Chunk],
    client: RecordedClient,
    image_bytes: bytes,
    tmp_path: Path,
) -> None:
    """The media file's bytes equal the deck asset's; nothing else lands in media/."""
    _generate(deck, chunks, client, tmp_path)
    target = tmp_path / "media" / MEDIA_NAME
    assert target.read_bytes() == image_bytes
    assert [path.name for path in (tmp_path / "media").iterdir()] == [MEDIA_NAME]


def test_exactly_five_requests(
    deck: Deck, chunks: list[Chunk], client: RecordedClient, tmp_path: Path
) -> None:
    """4 chunks + 1 synthesis, pinned so a cost regression is a test failure."""
    counting = CountingClient(client)
    _generate(deck, chunks, counting, tmp_path)
    assert counting.calls == 5


def test_reruns_are_deterministic_and_rewrite_media_in_place(
    deck: Deck,
    chunks: list[Chunk],
    client: RecordedClient,
    image_bytes: bytes,
    tmp_path: Path,
) -> None:
    first_dir, second_dir = tmp_path / "a", tmp_path / "b"
    first = _generate(deck, chunks, client, first_dir)
    assert _generate(deck, chunks, client, second_dir) == first
    # Id-keyed target: a rerun into the same out_dir updates the file in place.
    (first_dir / "media" / MEDIA_NAME).write_bytes(b"stale")
    assert _generate(deck, chunks, client, first_dir) == first
    assert (first_dir / "media" / MEDIA_NAME).read_bytes() == image_bytes


# --- bad responses still fail loudly ------------------------------------------------


def _modified_client(
    responses_path: Path, tmp_path: Path, key: str, mutate: Callable[[str], str]
) -> RecordedClient:
    responses = json.loads(responses_path.read_text(encoding="utf-8"))
    responses[key] = mutate(responses[key])
    path = tmp_path / "responses.json"
    path.write_text(json.dumps(responses), encoding="utf-8")
    return RecordedClient(path)


def test_figure_citing_an_image_not_on_the_slides_still_raises(
    deck: Deck, chunks: list[Chunk], responses_path: Path, tmp_path: Path
) -> None:
    """The entrypoint reuses the P5-02 validation path; the ValueError survives."""
    bad = _modified_client(
        responses_path,
        tmp_path,
        "chunk:lec01:s3-3",
        lambda text: text.replace(PPTX_IMAGE_ID, "img-deadbeef00000000"),
    )
    with pytest.raises(ValueError, match="img-deadbeef00000000"):
        _generate(deck, chunks, bad, tmp_path / "out")


def test_null_valued_extra_keys_are_stripped_before_validation(
    deck: Deck, chunks: list[Chunk], responses_path: Path, tmp_path: Path, client: RecordedClient
) -> None:
    """LLM noise like ``"note": null`` is dropped at the boundary (seen in a real
    build); the result is identical to the clean response's."""

    def add_null_noise(text: str) -> str:
        response = json.loads(text)
        response["body"][0]["note"] = None
        response["comment"] = None
        return json.dumps(response)

    noisy = _modified_client(responses_path, tmp_path, "chunk:lec01:s1-1", add_null_noise)
    assert _generate(deck, chunks, noisy, tmp_path / "a") == _generate(
        deck, chunks, client, tmp_path / "b"
    )


def test_trailing_commas_are_repaired_before_parsing(
    deck: Deck, chunks: list[Chunk], responses_path: Path, tmp_path: Path, client: RecordedClient
) -> None:
    """A trailing comma before a closer (seen in a real build) parses; the result is
    identical to the clean response's."""

    def add_trailing_comma(text: str) -> str:
        pretty = json.dumps(json.loads(text), indent=2)
        assert pretty.endswith("}")
        return pretty[:-1] + ",\n}"

    sloppy = _modified_client(responses_path, tmp_path, "chunk:lec01:s1-1", add_trailing_comma)
    assert _generate(deck, chunks, sloppy, tmp_path / "a") == _generate(
        deck, chunks, client, tmp_path / "b"
    )


def test_comma_repair_never_touches_string_content(
    deck: Deck, chunks: list[Chunk], responses_path: Path, tmp_path: Path
) -> None:
    """The repair is string-aware: a literal ",}" inside a field survives while the
    real trailing comma is stripped."""
    heading = 'Braces ,} and ,] "quoted \\" too" in prose'

    def mutate(text: str) -> str:
        response = json.loads(text)
        response["heading"] = heading
        pretty = json.dumps(response, indent=2)
        return pretty[:-1] + ",\n}"

    sloppy = _modified_client(responses_path, tmp_path, "chunk:lec01:s1-1", mutate)
    lecture = _generate(deck, chunks, sloppy, tmp_path / "out")
    assert lecture.topics[0].heading == heading


def test_synthesis_with_an_extra_field_fails_validation(
    deck: Deck, chunks: list[Chunk], responses_path: Path, tmp_path: Path
) -> None:
    """``extra="forbid"`` end to end: a chatty synthesis response is rejected."""

    def add_field(text: str) -> str:
        response = json.loads(text)
        response["model_note"] = "hope this helps!"
        return json.dumps(response)

    bad = _modified_client(responses_path, tmp_path, "synthesis:lec01", add_field)
    with pytest.raises(ValidationError, match="model_note"):
        _generate(deck, chunks, bad, tmp_path / "out")
