"""P1-04: the ``lecturenotes captions FILE`` inspection command.

A debugging command, not the product (plan §8: "bad notes are almost always bad
chunks"): one line per segment, ``[m:ss–m:ss] text``, or the segments as JSON that
``Segment.model_validate`` accepts back. Everything goes through ``main([...])`` and
``capsys`` so the tests exercise exactly what the console script runs.
"""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

import pytest

import lecturenotes
from lecturenotes.cli import format_clock, main

SEGMENT_COUNT = 22


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
