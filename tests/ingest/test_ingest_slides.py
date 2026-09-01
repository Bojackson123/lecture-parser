"""The Phase 2 done-gate (plan §6): PPTX half (P2-01) and PDF half (P2-02, P2-03).

``ingest_slides()`` on the PPTX fixture must equal the **hand-written**
``tests/fixtures/decks/lecture01.deck.json``, and on the PDF fixture must equal it up
to two substitutions a PDF cannot avoid: notes are ``None`` (PDFs carry none) and the
figure's bytes - hence its id - differ (pypdf re-encodes the image stream, P2-03
decision). The JSON transcribes the constants in
``tests/fixtures/decks/make_deck.py`` and the decks table in ``tests/fixtures/README.md``;
it is never regenerated from the code under test, or the snapshot would only prove that
the code agrees with itself.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lecturenotes.ingest.slides import (
    Deck,
    Slide,
    SlideImage,
    TextBlock,
    image_id,
    ingest_slides,
)

SLIDE_COUNT = 3

HAND_WRITTEN = (
    "the deck fixture is hand-written; if the extraction rule changed on purpose, edit "
    "tests/fixtures/decks/lecture01.deck.json deliberately - do not regenerate it from "
    "the code under test."
)


@pytest.fixture(scope="module")
def expected_deck(expected_deck_json: str) -> Deck:
    return Deck.model_validate_json(expected_deck_json)


def test_expected_fixture_has_3_slides(expected_deck: Deck) -> None:
    assert len(expected_deck.slides) == SLIDE_COUNT


def test_pptx_ingests_to_the_hand_written_deck(
    repo_root: Path, expected_deck: Deck, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Open the path the fixture itself names (repo-relative, POSIX), from the repo root,
    # so ``Deck.source`` is compared too and the test is cwd- and OS-independent.
    monkeypatch.chdir(repo_root)
    actual = ingest_slides(Path(expected_deck.source))
    assert actual == expected_deck, HAND_WRITTEN
    assert len(actual.slides) == SLIDE_COUNT


def test_pdf_ingests_to_the_hand_written_titles_and_blocks(
    decks_dir: Path, expected_deck: Deck
) -> None:
    pdf = ingest_slides(decks_dir / "lecture01.pdf")
    assert [(s.number, s.title, s.blocks) for s in pdf.slides] == [
        (s.number, s.title, s.blocks) for s in expected_deck.slides
    ], HAND_WRITTEN
    assert all(slide.notes is None for slide in pdf.slides)


def _without_images(deck: Deck) -> Deck:
    return deck.model_copy(
        update={
            "assets": (),
            "slides": tuple(s.model_copy(update={"image_ids": ()}) for s in deck.slides),
        }
    )


def test_pdf_ingests_to_the_hand_written_deck_up_to_notes_and_the_reencoded_figure(
    repo_root: Path, expected_deck: Deck, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The PDF half of the done-gate. Two deliberate substitutions on the expected side:
    every ``notes`` becomes ``None``, and the single asset is compared by
    ``(media_type, width, height)`` with slide 3's ``image_ids`` compared by length -
    the PDF figure is re-encoded by pypdf, so its bytes and id differ."""
    monkeypatch.chdir(repo_root)
    pdf_path = Path(expected_deck.source).with_suffix(".pdf")
    actual = ingest_slides(pdf_path)
    expected = expected_deck.model_copy(
        update={
            "source": pdf_path.as_posix(),
            "slides": tuple(s.model_copy(update={"notes": None}) for s in expected_deck.slides),
        }
    )
    assert _without_images(actual) == _without_images(expected), HAND_WRITTEN
    assert [(a.media_type, a.width, a.height) for a in actual.assets] == [
        (a.media_type, a.width, a.height) for a in expected.assets
    ], HAND_WRITTEN
    assert [len(s.image_ids) for s in actual.slides] == [
        len(s.image_ids) for s in expected.slides
    ], HAND_WRITTEN
    assert actual.slides[2].image_ids == (actual.assets[0].id,)
    assert actual.recurring_image_ids == expected.recurring_image_ids == ()


def test_pdf_and_pptx_agree_on_titles_and_blocks(decks_dir: Path) -> None:
    """The SRT-style cross-format assertion: one lecture, two files, one extraction."""
    pdf = ingest_slides(decks_dir / "lecture01.pdf")
    pptx = ingest_slides(decks_dir / "lecture01.pptx")
    assert [(s.title, s.blocks) for s in pdf.slides] == [(s.title, s.blocks) for s in pptx.slides]


def test_deck_survives_a_json_round_trip(decks_dir: Path) -> None:
    """Image bytes travel as base64, so the whole ``Deck`` is one plain JSON document."""
    deck = ingest_slides(decks_dir / "lecture01.pptx")
    assert Deck.model_validate_json(deck.model_dump_json()) == deck


def test_suffix_dispatch_is_case_insensitive(tmp_path: Path, decks_dir: Path) -> None:
    upper = tmp_path / "LECTURE01.PPTX"
    upper.write_bytes((decks_dir / "lecture01.pptx").read_bytes())
    assert len(ingest_slides(upper).slides) == SLIDE_COUNT


def test_unsupported_suffix_raises_value_error_naming_it(tmp_path: Path) -> None:
    # ``.key``, not ``.pdf``: this test must stay true once P2-02 registers ``.pdf``.
    key = tmp_path / "lecture01.key"
    key.write_bytes(b"not a deck\n")
    with pytest.raises(ValueError, match=r"\.key"):
        ingest_slides(key)


def test_missing_file_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        ingest_slides(tmp_path / "nope.pptx")


# --- the types ---------------------------------------------------------------------


def test_text_block_rejects_empty_or_blank_lines() -> None:
    with pytest.raises(ValueError, match="at least one line"):
        TextBlock(lines=())
    with pytest.raises(ValueError, match="empty"):
        TextBlock(lines=("ok", ""))


def test_slide_image_id_must_be_the_content_hash() -> None:
    data = b"\x89PNG not really"
    good = SlideImage(id=image_id(data), media_type="image/png", width=1, height=1, data=data)
    assert good.id.startswith("img-") and len(good.id) == 20
    with pytest.raises(ValueError, match="img-0000000000000000"):
        SlideImage(id="img-0000000000000000", media_type="image/png", width=1, height=1, data=data)
    with pytest.raises(ValueError, match="width"):
        SlideImage(id=image_id(data), media_type="image/png", width=0, height=1, data=data)


def test_slide_rejects_bad_number_and_duplicate_image_ids() -> None:
    with pytest.raises(ValueError, match="number"):
        Slide(number=0, title=None, blocks=(), notes=None, image_ids=())
    with pytest.raises(ValueError, match="img-aaaaaaaaaaaaaaaa"):
        Slide(
            number=1,
            title=None,
            blocks=(),
            notes=None,
            image_ids=("img-aaaaaaaaaaaaaaaa", "img-aaaaaaaaaaaaaaaa"),
        )


def _slide(number: int, image_ids: tuple[str, ...] = ()) -> Slide:
    return Slide(number=number, title=None, blocks=(), notes=None, image_ids=image_ids)


def test_deck_requires_slide_numbers_1_to_n_in_order() -> None:
    Deck(source="x.pptx", slides=(_slide(1), _slide(2)), assets=())
    with pytest.raises(ValueError, match=r"1\.\.2"):
        Deck(source="x.pptx", slides=(_slide(2), _slide(1)), assets=())
    with pytest.raises(ValueError, match=r"1\.\.2"):
        Deck(source="x.pptx", slides=(_slide(1), _slide(3)), assets=())


def test_deck_image_references_must_resolve_to_unique_assets() -> None:
    data = b"bytes"
    asset = SlideImage(id=image_id(data), media_type="image/png", width=2, height=2, data=data)
    Deck(source="x.pptx", slides=(_slide(1, (asset.id,)),), assets=(asset,))
    with pytest.raises(ValueError, match="img-ffffffffffffffff"):
        Deck(source="x.pptx", slides=(_slide(1, ("img-ffffffffffffffff",)),), assets=(asset,))
    with pytest.raises(ValueError, match="img-ffffffffffffffff"):
        Deck(
            source="x.pptx",
            slides=(_slide(1),),
            assets=(asset,),
            recurring_image_ids=("img-ffffffffffffffff",),
        )
    with pytest.raises(ValueError, match=asset.id):
        Deck(source="x.pptx", slides=(_slide(1),), assets=(asset, asset))
