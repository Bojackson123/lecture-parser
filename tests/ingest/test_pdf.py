"""P2-02: ``parse_pdf`` on the fixture deck and on ad-hoc PDFs.

Each row of the decks table in ``tests/fixtures/README.md`` is a test name here. The
ad-hoc PDFs are built with ``pypdf.PdfWriter`` under ``tmp_path`` - a blank page, an
encrypted page, and pages copied out of the fixture - because they exercise the file
format and the cross-page boilerplate rule, not the lecture.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter

from lecturenotes.ingest.slides import Deck, DeckParseError, Slide, ingest_slides, parse_pdf

# README decks table, transcribed - never read from the parser output.
TITLES = ("Markov Decision Processes", "The Bellman Equation", "Value Iteration")
FOOTERS = ("slide 1 / 3", "slide 2 / 3", "slide 3 / 3")


@pytest.fixture(scope="module")
def deck(decks_dir: Path) -> Deck:
    return parse_pdf(decks_dir / "lecture01.pdf")


def _texts(slide: Slide) -> list[str]:
    title = [slide.title] if slide.title is not None else []
    return title + [line for block in slide.blocks for line in block.lines]


# --- the decks table ---------------------------------------------------------------


def test_slide_1_single_column_gives_title_then_five_bullets(deck: Deck) -> None:
    slide = deck.slides[0]
    assert slide.title == TITLES[0]
    assert len(slide.blocks) == 1
    assert len(slide.blocks[0].lines) == 5
    assert slide.blocks[0].lines[0].startswith("States s in S")


def test_slide_1_bullet_glyphs_are_stripped(deck: Deck) -> None:
    assert not any(line.startswith("- ") for line in _texts(deck.slides[0]))


def test_slide_2_two_columns_read_left_block_then_right_block(deck: Deck) -> None:
    slide = deck.slides[1]
    assert len(slide.blocks) == 2
    left, right = slide.blocks
    assert len(left.lines) == 6
    assert (left.lines[0], left.lines[-1]) == ("Equation", "gamma: discount factor")
    assert len(right.lines) == 6
    assert (right.lines[0], right.lines[-1]) == (
        "Intuition",
        "Everything else in the course builds on this",
    )


def test_slide_3_steps_in_order_with_leading_spaces_gone(deck: Deck) -> None:
    slide = deck.slides[2]
    assert len(slide.blocks) == 1
    lines = slide.blocks[0].lines
    assert len(lines) == 5
    assert lines[2].startswith("gamma *")
    assert [line[:2] for line in lines] == ["1.", "2.", "ga", "3.", "4."]


def test_footer_is_dropped_as_boilerplate(deck: Deck) -> None:
    for slide in deck.slides:
        for text in _texts(slide):
            assert not any(footer in text for footer in FOOTERS), text
            assert "Lecture 1" not in text


def test_titles_are_the_28pt_strings(deck: Deck) -> None:
    assert tuple(slide.title for slide in deck.slides) == TITLES


def test_pdf_slides_have_no_notes(deck: Deck) -> None:
    assert [slide.notes for slide in deck.slides] == [None, None, None]


def test_slide_numbers_are_page_numbers_and_nothing_is_hidden(deck: Deck) -> None:
    assert [slide.number for slide in deck.slides] == [1, 2, 3]
    assert not any(slide.hidden for slide in deck.slides)


def test_source_is_the_path_as_given_in_posix_form(decks_dir: Path) -> None:
    path = decks_dir / "lecture01.pdf"
    assert parse_pdf(path).source == path.as_posix()


def test_upper_case_suffix_parses(tmp_path: Path, decks_dir: Path) -> None:
    upper = tmp_path / "LECTURE01.PDF"
    upper.write_bytes((decks_dir / "lecture01.pdf").read_bytes())
    assert len(ingest_slides(upper).slides) == 3


# --- ad-hoc PDFs -------------------------------------------------------------------


def _write(writer: PdfWriter, tmp_path: Path, name: str = "adhoc.pdf") -> Path:
    path = tmp_path / name
    writer.write(str(path))
    return path


def _pages_of(decks_dir: Path, *numbers: int) -> PdfWriter:
    reader = PdfReader(str(decks_dir / "lecture01.pdf"))
    writer = PdfWriter()
    for number in numbers:
        writer.add_page(reader.pages[number - 1])
    return writer


def test_garbage_bytes_raise_deck_parse_error_naming_the_file(tmp_path: Path) -> None:
    junk = tmp_path / "junk.pdf"
    junk.write_bytes(b"\x00not a pdf\xff" * 64)
    with pytest.raises(DeckParseError, match="junk.pdf"):
        parse_pdf(junk)


def test_missing_file_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        parse_pdf(tmp_path / "nope.pdf")


def test_one_blank_page_is_one_slide_with_no_title_and_no_blocks(tmp_path: Path) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=842, height=595)
    (only,) = parse_pdf(_write(writer, tmp_path)).slides
    assert only == Slide(number=1, title=None, blocks=(), notes=None, image_ids=())


def test_footer_rule_needs_two_pages_so_a_one_page_deck_keeps_its_footer(
    tmp_path: Path, decks_dir: Path
) -> None:
    """Page 1 of the fixture alone: ``slide 1 / 3`` is on every page of a one-page deck,
    but nothing can be *recurring* with one page, so the line survives (as its own
    right-hand column)."""
    (only,) = parse_pdf(_write(_pages_of(decks_dir, 1), tmp_path)).slides
    assert only.title == TITLES[0]
    assert any("slide 1 / 3" in line for line in _texts(only))


def test_footer_rule_fires_on_a_two_page_deck(tmp_path: Path, decks_dir: Path) -> None:
    slides = parse_pdf(_write(_pages_of(decks_dir, 1, 2), tmp_path)).slides
    assert [slide.title for slide in slides] == list(TITLES[:2])
    assert not any("slide" in text for slide in slides for text in _texts(slide))


def test_password_protected_pdf_raises_deck_parse_error(tmp_path: Path) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=842, height=595)
    writer.encrypt("secret")
    locked = _write(writer, tmp_path, "locked.pdf")
    with pytest.raises(DeckParseError, match="locked.pdf"):
        parse_pdf(locked)


def test_empty_user_password_is_tried_and_accepted(tmp_path: Path) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=842, height=595)
    writer.encrypt(user_password="", owner_password="owner")
    assert len(parse_pdf(_write(writer, tmp_path)).slides) == 1
