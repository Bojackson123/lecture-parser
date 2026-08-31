"""Sanity checks on the committed source fixtures (P0-03).

No parser code from ``lecturenotes`` is used here: line counting, a regex for cue
timestamps, and third-party readers only.
"""

import re
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent
VTT = FIXTURES / "captions" / "lecture01.vtt"
SRT = FIXTURES / "captions" / "lecture01.srt"
PDF = FIXTURES / "decks" / "lecture01.pdf"
PPTX = FIXTURES / "decks" / "lecture01.pptx"

CUE_COUNT = 20
# Slide -> time map the transcript was written to (see README.md).
SLIDE2_WINDOW_S = (4 * 60 + 30, 7 * 60)

_TIMING = re.compile(r"^(\d\d):(\d\d):(\d\d)[.,](\d{3}) --> (\d\d):(\d\d):(\d\d)[.,](\d{3})")


def _cues(text: str) -> list[tuple[float, float, str]]:
    """(start_s, end_s, body) per cue, by scanning for timing lines."""
    cues: list[tuple[float, float, str]] = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = _TIMING.match(line)
        if not m:
            continue
        h1, m1, s1, ms1, h2, m2, s2, ms2 = (int(g) for g in m.groups())
        start = h1 * 3600 + m1 * 60 + s1 + ms1 / 1000
        end = h2 * 3600 + m2 * 60 + s2 + ms2 / 1000
        body: list[str] = []
        for later in lines[i + 1 :]:
            if not later.strip():
                break
            body.append(later)
        cues.append((start, end, "\n".join(body)))
    return cues


def test_vtt_header_and_cue_count() -> None:
    text = VTT.read_text(encoding="utf-8")
    assert text.startswith("WEBVTT")
    assert sum(1 for line in text.splitlines() if "-->" in line) == CUE_COUNT


def test_srt_cue_count_matches_vtt() -> None:
    srt = [line for line in SRT.read_text(encoding="utf-8").splitlines() if "-->" in line]
    vtt = [line for line in VTT.read_text(encoding="utf-8").splitlines() if "-->" in line]
    assert len(srt) == CUE_COUNT == len(vtt)


def test_vtt_timestamps_monotonic_and_duration_in_range() -> None:
    cues = _cues(VTT.read_text(encoding="utf-8"))
    assert len(cues) == CUE_COUNT
    for start, end, _ in cues:
        assert start <= end
    for (_, prev_end, _), (start, _, _) in zip(cues, cues[1:], strict=False):
        assert prev_end <= start
    assert 8 * 60 <= cues[-1][1] <= 10 * 60


def test_exam_phrase_appears_exactly_once() -> None:
    assert VTT.read_text(encoding="utf-8").count("this will be on the exam") == 1


def test_bellman_only_inside_slide_2_window() -> None:
    text = VTT.read_text(encoding="utf-8")
    assert "bellman" in text
    lo, hi = SLIDE2_WINDOW_S
    for start, end, body in _cues(text):
        if "bellman" in body.lower():
            assert lo <= start and end <= hi, (start, end, body)
    # ...and the NOTE block (before the first cue) must not mention it either.
    assert "bellman" not in text.split("-->", 1)[0].lower()


def test_srt_has_no_vtt_only_syntax() -> None:
    text = SRT.read_text(encoding="utf-8")
    assert "WEBVTT" not in text
    assert "NOTE" not in text
    assert "<c>" not in text
    assert "<v " not in text
    assert "<i>" in text  # SRT tolerates simple styling tags; the fixture keeps one.


def test_pdf_has_three_pages() -> None:
    pypdf = pytest.importorskip("pypdf")
    assert len(pypdf.PdfReader(str(PDF)).pages) == 3


def test_pptx_has_three_slides_with_notes() -> None:
    pptx = pytest.importorskip("pptx")
    prs = pptx.Presentation(str(PPTX))
    slides = list(prs.slides)
    assert len(slides) == 3
    for slide in slides:
        assert slide.has_notes_slide
        assert slide.notes_slide.notes_text_frame.text.strip()


def test_every_fixture_file_is_small() -> None:
    files = [p for p in FIXTURES.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    assert files
    for path in files:
        assert path.stat().st_size < 100 * 1024, path
