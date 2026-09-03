"""P1-04 ``lecturenotes captions FILE``, P2-04 ``lecturenotes slides FILE`` and
P3-04 ``lecturenotes render FILE [-o DIR]``.

Debugging commands, not the product (plan §8: "bad notes are almost always bad
chunks"): ``captions`` prints one line per segment, ``[m:ss–m:ss] text``, or the
segments as JSON that ``Segment.model_validate`` accepts back; ``slides`` prints one
deck - titles, blocks in reading order, images found, notes on request - or the
``Deck`` as JSON that ``Deck.model_validate_json`` accepts back; ``render`` prints the
markdown one ``NoteWeek`` JSON renders to (or emits it to a directory with ``-o``), or
the ``RenderResult`` as JSON that ``RenderResult.model_validate_json`` accepts back.
Everything goes through ``main([...])`` and ``capsys`` so the tests exercise exactly
what the console script runs.
"""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

import pytest
from PIL import Image as PILImage
from pptx import Presentation
from pptx.util import Inches

import lecturenotes
from lecturenotes.cli import format_clock, main
from lecturenotes.ingest.slides import Deck, image_id
from lecturenotes.render.base import RenderResult

SEGMENT_COUNT = 22
SLIDE_COUNT = 3
# README decks table, transcribed - never read from the parser output.
PPTX_IMAGE_ID = "img-a63ae9b7dc5e9397"
PPTX_IMAGE_LINE = f"[image {PPTX_IMAGE_ID} 240x150 image/png]"


@pytest.fixture(scope="module")
def vtt_path(fixtures_dir: Path) -> str:
    return str(fixtures_dir / "captions" / "lecture01.vtt")


@pytest.fixture(scope="module")
def srt_path(fixtures_dir: Path) -> str:
    return str(fixtures_dir / "captions" / "lecture01.srt")


# --- existing behaviour is unchanged ----------------------------------------------


def test_version_flag_still_works(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == f"lecturenotes {lecturenotes.__version__}"


def test_no_arguments_prints_help_and_returns_0(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    out = capsys.readouterr().out
    assert out.startswith("usage: lecturenotes")
    assert "captions" in out
    assert "slides" in out
    assert "render" in out


# --- plain lines ------------------------------------------------------------------


def test_captions_prints_22_lines_first_and_last_anchored(
    vtt_path: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["captions", vtt_path]) == 0
    captured = capsys.readouterr()
    lines = captured.out.splitlines()
    assert len(lines) == SEGMENT_COUNT
    assert lines[0].startswith("[0:01–0:26] welcome back")
    assert lines[-1].startswith("[8:40–9:05] that's it")
    assert captured.err == ""


def test_every_line_has_the_bracketed_span_prefix(
    vtt_path: str, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["captions", vtt_path])
    for line in capsys.readouterr().out.splitlines():
        prefix, _, text = line.partition("] ")
        assert prefix.startswith("["), line
        start, sep, end = prefix[1:].partition("–")
        assert sep and start and end, line
        assert text and text == text.strip(), line


def test_srt_prints_the_same_lines_as_vtt(
    vtt_path: str, srt_path: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["captions", vtt_path]) == 0
    from_vtt = capsys.readouterr().out
    assert main(["captions", srt_path]) == 0
    assert capsys.readouterr().out == from_vtt


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0.0, "0:00"),
        (1.0, "0:01"),
        (26.0, "0:26"),
        (59.9, "0:59"),  # floored, never rounded up into the next second
        (60.0, "1:00"),
        (520.0, "8:40"),
        (599.0, "9:59"),
        (600.0, "10:00"),
        (3599.0, "59:59"),
        (3600.0, "1:00:00"),
        (3723.0, "1:02:03"),
        (36_000.0, "10:00:00"),
    ],
)
def test_format_clock(seconds: float, expected: str) -> None:
    assert format_clock(seconds) == expected


# --- --json -----------------------------------------------------------------------


def test_json_output_is_22_segment_dicts(srt_path: str, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["captions", "--json", srt_path]) == 0
    data = json.loads(capsys.readouterr().out)
    assert isinstance(data, list)
    assert len(data) == SEGMENT_COUNT
    assert all(set(d) == {"start_s", "end_s", "text"} for d in data)


def test_json_output_equals_the_hand_written_fixture(
    vtt_path: str, fixtures_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The JSON uses the ``Segment`` field names, so it round-trips with the snapshot."""
    main(["captions", "--json", vtt_path])
    printed = json.loads(capsys.readouterr().out)
    expected_raw = (fixtures_dir / "captions" / "lecture01.segments.json").read_text("utf-8")
    assert printed == json.loads(expected_raw)


# --- merge knobs ------------------------------------------------------------------


def test_max_segment_s_is_forwarded(vtt_path: str, capsys: pytest.CaptureFixture[str]) -> None:
    """40 s is below the fixture's longest merged span (49 s), so the output must change."""
    assert main(["captions", vtt_path]) == 0
    default = capsys.readouterr().out
    assert main(["captions", "--max-segment-s", "40", vtt_path]) == 0
    assert capsys.readouterr().out != default
    assert main(["captions", "--max-segment-s", "60", vtt_path]) == 0
    assert capsys.readouterr().out == default


def test_max_gap_s_is_forwarded(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Two unterminated cues 10 s apart: the default 5 s gap flushes them as two
    segments, ``--max-gap-s 20`` joins them into one. (The lecture fixture cannot show
    this — every sentence that carries across cues there crosses a zero-second gap.)"""
    vtt = tmp_path / "gap.vtt"
    vtt.write_text(
        dedent(
            """
            WEBVTT

            00:00:00.000 --> 00:00:05.000
            first half

            00:00:15.000 --> 00:00:20.000
            second half.
            """
        ).strip(),
        encoding="utf-8",
    )
    assert main(["captions", str(vtt)]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "[0:00–0:05] first half",
        "[0:15–0:20] second half.",
    ]
    assert main(["captions", "--max-gap-s", "20", str(vtt)]) == 0
    assert capsys.readouterr().out.splitlines() == ["[0:00–0:20] first half second half."]


# --- errors -----------------------------------------------------------------------


def test_unsupported_suffix_returns_2_with_stderr_only(
    fixtures_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pdf = str(fixtures_dir / "decks" / "lecture01.pdf")
    assert main(["captions", pdf]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert ".pdf" in captured.err
    assert "Traceback" not in captured.err


def test_missing_file_returns_2_with_stderr_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = str(tmp_path / "nope.vtt")
    assert main(["captions", missing]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "nope.vtt" in captured.err
    assert "Traceback" not in captured.err


def test_malformed_captions_return_2_with_the_line_number(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = tmp_path / "bad.vtt"
    bad.write_text("WEBVTT\n\nthis is not a timing line\nhello\n", encoding="utf-8")
    assert main(["captions", str(bad)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "line 3" in captured.err
    assert "Traceback" not in captured.err


# =====================================================================================
# P2-04: ``lecturenotes slides FILE``
# =====================================================================================


@pytest.fixture(scope="module")
def pptx_path(fixtures_dir: Path) -> str:
    return str(fixtures_dir / "decks" / "lecture01.pptx")


@pytest.fixture(scope="module")
def pdf_path(fixtures_dir: Path) -> str:
    return str(fixtures_dir / "decks" / "lecture01.pdf")


def _slide_headers(out: str) -> list[str]:
    return [line for line in out.splitlines() if line.startswith("--- slide")]


def _image_lines(out: str) -> list[str]:
    return [line for line in out.splitlines() if line.startswith("[image ")]


# --- plain lines ------------------------------------------------------------------


def test_slides_prints_3_slide_headers_with_titles(
    pptx_path: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["slides", pptx_path]) == 0
    captured = capsys.readouterr()
    assert _slide_headers(captured.out) == [
        "--- slide 1: Markov Decision Processes",
        "--- slide 2: The Bellman Equation",
        "--- slide 3: Value Iteration",
    ]
    assert captured.err == ""


def test_slides_prints_the_left_column_before_the_right(
    pptx_path: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Slide 2's reading order at a glance: the last left-column row precedes the
    right column's heading."""
    main(["slides", pptx_path])
    lines = capsys.readouterr().out.splitlines()
    assert lines.index("gamma: discount factor") < lines.index("Intuition")


def test_slides_separates_blocks_with_one_blank_line(
    pptx_path: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Slide 2 has two blocks: six left-column lines, a blank, six right-column lines."""
    main(["slides", pptx_path])
    lines = capsys.readouterr().out.splitlines()
    start = lines.index("--- slide 2: The Bellman Equation")
    end = lines.index("--- slide 3: Value Iteration")
    body = [line for line in lines[start + 1 : end] if not line.startswith("[")]
    while body and body[-1] == "":  # the slide separator, if the command prints one
        body.pop()
    assert body[0] == "Equation"
    assert body[6] == ""
    assert body[7] == "Intuition"
    assert body.count("") == 1
    assert len(body) == 13


def test_slides_lists_the_figure_as_an_image_line_after_slide_3s_text(
    pptx_path: str, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["slides", pptx_path])
    out = capsys.readouterr().out
    assert _image_lines(out) == [PPTX_IMAGE_LINE]
    lines = out.splitlines()
    last_step = "4. Read off the greedy policy pi(s) = argmax_a [ ... ]"
    assert lines.index("--- slide 3: Value Iteration") < lines.index(last_step)
    assert lines.index(last_step) < lines.index(PPTX_IMAGE_LINE)


def test_slides_prints_no_notes_by_default(
    pptx_path: str, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["slides", pptx_path])
    assert "[notes]" not in capsys.readouterr().out


def test_slides_notes_flag_adds_one_notes_line_per_slide(
    pptx_path: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["slides", "--notes", pptx_path]) == 0
    lines = capsys.readouterr().out.splitlines()
    notes = [line for line in lines if line.startswith("[notes] ")]
    assert len(notes) == SLIDE_COUNT
    assert "this will be on the exam" in notes[1]
    # Each notes line sits inside its own slide, after the text and images.
    headers = _slide_headers("\n".join(lines))
    for header, note in zip(headers, notes, strict=True):
        assert lines.index(header) < lines.index(note)
    assert lines.index(PPTX_IMAGE_LINE) < lines.index(notes[2])
    assert lines.index(notes[0]) < lines.index(headers[1])
    assert lines.index(notes[1]) < lines.index(headers[2])


def test_slides_pdf_prints_the_same_headers_and_never_notes(
    pptx_path: str, pdf_path: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["slides", pptx_path]) == 0
    from_pptx = _slide_headers(capsys.readouterr().out)
    assert main(["slides", "--notes", pdf_path]) == 0
    out = capsys.readouterr().out
    assert _slide_headers(out) == from_pptx
    assert "[notes]" not in out
    # The PDF figure is re-encoded (a different id) but is the same 240x150 PNG.
    image_lines = _image_lines(out)
    assert len(image_lines) == 1
    assert image_lines[0].startswith("[image img-")
    assert image_lines[0].endswith(" 240x150 image/png]")
    assert image_lines[0] != PPTX_IMAGE_LINE


def test_slides_pdf_and_pptx_print_the_same_text_lines(
    pptx_path: str, pdf_path: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """The cross-format assertion, seen from the shell: everything but the image line."""

    def text_only(out: str) -> list[str]:
        return [line for line in out.splitlines() if not line.startswith("[image ")]

    assert main(["slides", pptx_path]) == 0
    from_pptx = text_only(capsys.readouterr().out)
    assert main(["slides", pdf_path]) == 0
    assert text_only(capsys.readouterr().out) == from_pptx


# --- --json -----------------------------------------------------------------------


def test_slides_json_validates_back_to_a_3_slide_deck(
    pptx_path: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["slides", "--json", pptx_path]) == 0
    out = capsys.readouterr().out
    deck = Deck.model_validate_json(out)
    assert len(deck.slides) == SLIDE_COUNT
    assert [a.id for a in deck.assets] == [PPTX_IMAGE_ID]
    assert json.loads(out)["slides"][2]["notes"]  # --json is the complete view


def test_slides_json_equals_the_hand_written_fixture(
    pptx_path: str, fixtures_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["slides", "--json", pptx_path])
    printed = Deck.model_validate_json(capsys.readouterr().out)
    expected_raw = (fixtures_dir / "decks" / "lecture01.deck.json").read_text("utf-8")
    expected = Deck.model_validate_json(expected_raw)
    # source is the path as given (absolute here, repo-relative in the fixture).
    assert printed.source.endswith(expected.source)
    assert printed.model_copy(update={"source": expected.source}) == expected


# --- ad-hoc decks: [hidden], untitled, --min-px, [recurring] ----------------------------


def _png(tmp_path: Path, name: str, size: tuple[int, int], colour: str) -> Path:
    path = tmp_path / f"{name}.png"
    PILImage.new("RGB", size, colour).save(path)
    return path


def _pptx(tmp_path: Path, per_slide: list[list[Path]], hidden: tuple[int, ...] = ()) -> str:
    """One blank, untitled slide per entry with its pictures side by side."""
    blank = 6
    prs = Presentation()
    for number, pictures in enumerate(per_slide, start=1):
        slide = prs.slides.add_slide(prs.slide_layouts[blank])
        for i, picture in enumerate(pictures):
            slide.shapes.add_picture(str(picture), Inches(1 + 3 * i), Inches(1))
        if number in hidden:
            slide._element.set("show", "0")
    path = tmp_path / "adhoc.pptx"
    prs.save(str(path))
    return str(path)


def test_slides_untitled_and_hidden_headers(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    deck = _pptx(tmp_path, [[], [], []], hidden=(2,))
    assert main(["slides", deck]) == 0
    assert _slide_headers(capsys.readouterr().out) == [
        "--- slide 1",
        "--- slide 2 [hidden]",
        "--- slide 3",
    ]


def test_slides_min_px_is_forwarded(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    tiny = _png(tmp_path, "tiny", (8, 8), "red")
    deck = _pptx(tmp_path, [[tiny]])
    assert main(["slides", deck]) == 0
    assert _image_lines(capsys.readouterr().out) == []
    assert main(["slides", "--min-px", "4", deck]) == 0
    image_lines = _image_lines(capsys.readouterr().out)
    assert len(image_lines) == 1
    assert image_lines[0].endswith(" 8x8 image/png]")


def test_slides_recurring_logo_is_listed_once_after_the_last_slide(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    logo = _png(tmp_path, "logo", (64, 48), "navy")
    figure = _png(tmp_path, "figure", (64, 48), "olive")
    deck = _pptx(tmp_path, [[logo], [logo, figure], [logo], []])
    assert main(["slides", deck]) == 0
    out = capsys.readouterr().out
    lines = out.splitlines()
    recurring = [line for line in lines if line.startswith("[recurring] ")]
    assert len(recurring) == 1
    logo_id = image_id(logo.read_bytes())
    assert recurring[0].split() == ["[recurring]", logo_id, "64x48", "image/png"]
    assert lines.index("--- slide 4") < lines.index(recurring[0])
    # The logo is nowhere in an [image ...] line; the figure on slide 2 still is.
    image_lines = _image_lines(out)
    assert len(image_lines) == 1
    assert image_id(figure.read_bytes()) in image_lines[0]
    assert lines.index("--- slide 2") < lines.index(image_lines[0]) < lines.index("--- slide 3")


def test_slides_prints_no_recurring_line_when_nothing_recurs(
    pptx_path: str, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["slides", pptx_path])
    assert "[recurring]" not in capsys.readouterr().out


# --- errors -----------------------------------------------------------------------


def test_slides_unsupported_suffix_returns_2_with_stderr_only(
    vtt_path: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["slides", vtt_path]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("lecturenotes slides: ")
    assert ".vtt" in captured.err
    assert "Traceback" not in captured.err


def test_slides_missing_file_returns_2_with_stderr_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = str(tmp_path / "nope.pptx")
    assert main(["slides", missing]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "nope.pptx" in captured.err
    assert "Traceback" not in captured.err


def test_slides_garbage_deck_returns_2_naming_the_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"not a pdf\n")
    assert main(["slides", str(bad)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "bad.pdf" in captured.err
    assert "Traceback" not in captured.err


# =====================================================================================
# P3-04: ``lecturenotes render FILE [-o DIR]``
# =====================================================================================


@pytest.fixture(scope="module")
def week_json_path(fixtures_dir: Path) -> str:
    return str(fixtures_dir / "notes" / "week01.json")


@pytest.fixture(scope="module")
def expected_markdown(fixtures_dir: Path) -> str:
    """Hand-written (P3-02) — bytes, not read_text, so newline handling can't lie."""
    return (fixtures_dir / "notes" / "week01.md").read_bytes().decode("utf-8")


# --- stdout mode ------------------------------------------------------------------


def test_render_prints_one_document_under_its_name(
    week_json_path: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["render", week_json_path]) == 0
    captured = capsys.readouterr()
    headers = [line for line in captured.out.splitlines() if line.startswith("--- ")]
    assert headers == ["--- cs-rl-101-w01.md"]
    assert "$$" in captured.out
    assert "> **EXAM**" in captured.out
    assert "[2:31–4:28]" in captured.out  # the slide-less anchor
    assert captured.err == ""


def test_render_text_after_the_header_equals_the_expected_markdown(
    week_json_path: str, expected_markdown: str, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["render", week_json_path])
    header, _, body = capsys.readouterr().out.partition("\n")
    assert header == "--- cs-rl-101-w01.md"
    assert body == expected_markdown


# --- -o DIR -----------------------------------------------------------------------


def test_render_out_writes_page_and_asset_and_prints_nothing(
    week_json_path: str,
    expected_markdown: str,
    fixtures_dir: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["render", week_json_path, "-o", str(tmp_path)]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    page = tmp_path / "cs-rl-101-w01.md"
    assert page.read_bytes().decode("utf-8") == expected_markdown
    copied = tmp_path / "assets" / "fig-value-iteration-convergence.png"
    original = fixtures_dir / "decks" / "value_iteration.png"
    assert copied.read_bytes() == original.read_bytes()


# --- --json -----------------------------------------------------------------------


def test_render_json_revalidates_to_one_document_and_one_asset(
    week_json_path: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["render", "--json", week_json_path]) == 0
    result = RenderResult.model_validate_json(capsys.readouterr().out)
    assert [d.name for d in result.documents] == ["cs-rl-101-w01.md"]
    assert [a.id for a in result.assets] == ["fig-value-iteration-convergence"]


# --- errors -----------------------------------------------------------------------


def test_render_non_json_file_returns_2_with_stderr_only(
    vtt_path: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["render", vtt_path]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("lecturenotes render: ")
    assert "Traceback" not in captured.err


def test_render_wrong_shape_json_returns_2_with_stderr_only(
    fixtures_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Valid JSON that is a ``Deck``, not a ``NoteWeek`` — pydantic's ValidationError
    is a ValueError, so it gets the uniform error line, not a traceback."""
    deck_json = str(fixtures_dir / "decks" / "lecture01.deck.json")
    assert main(["render", deck_json]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("lecturenotes render: ")
    assert "Traceback" not in captured.err


def test_render_missing_file_returns_2_with_stderr_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = str(tmp_path / "nope.json")
    assert main(["render", missing]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "nope.json" in captured.err
    assert "Traceback" not in captured.err
