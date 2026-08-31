"""P1-03: the Phase 1 done-gate (plan §6).

``ingest_captions()`` on the VTT fixture must equal the **hand-written**
``tests/fixtures/captions/lecture01.segments.json``, and the SRT twin must give the
identical list. The JSON transcribes the captions table in ``tests/fixtures/README.md``;
it is never regenerated from the code under test, or the snapshot would only prove
that the code agrees with itself.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lecturenotes.ingest.captions import Segment, ingest_captions

SEGMENT_COUNT = 22

HAND_WRITTEN = (
    "the segments fixture is hand-written; if the merge rule changed on purpose, edit "
    "tests/fixtures/captions/lecture01.segments.json deliberately - do not regenerate "
    "it from the code under test."
)


@pytest.fixture(scope="module")
def expected_segments(fixtures_dir: Path) -> list[Segment]:
    raw = (fixtures_dir / "captions" / "lecture01.segments.json").read_text(encoding="utf-8")
    return [Segment.model_validate(d) for d in json.loads(raw)]


def test_expected_fixture_has_22_segments(expected_segments: list[Segment]) -> None:
    assert len(expected_segments) == SEGMENT_COUNT


def test_vtt_ingests_to_the_hand_written_segments(
    fixtures_dir: Path, expected_segments: list[Segment]
) -> None:
    actual = ingest_captions(fixtures_dir / "captions" / "lecture01.vtt")
    assert actual == expected_segments, HAND_WRITTEN
    assert len(actual) == SEGMENT_COUNT


def test_srt_ingests_to_the_identical_segments(
    fixtures_dir: Path, expected_segments: list[Segment]
) -> None:
    captions = fixtures_dir / "captions"
    from_srt = ingest_captions(captions / "lecture01.srt")
    assert from_srt == expected_segments, HAND_WRITTEN
    assert from_srt == ingest_captions(captions / "lecture01.vtt")


def test_suffix_dispatch_is_case_insensitive(tmp_path: Path, fixtures_dir: Path) -> None:
    upper = tmp_path / "LECTURE01.VTT"
    upper.write_bytes((fixtures_dir / "captions" / "lecture01.vtt").read_bytes())
    assert len(ingest_captions(upper)) == SEGMENT_COUNT


def test_utf8_bom_is_tolerated(tmp_path: Path, fixtures_dir: Path) -> None:
    with_bom = tmp_path / "bom.srt"
    srt_bytes = (fixtures_dir / "captions" / "lecture01.srt").read_bytes()
    with_bom.write_bytes(b"\xef\xbb\xbf" + srt_bytes)
    assert len(ingest_captions(with_bom)) == SEGMENT_COUNT


def test_unsupported_suffix_raises_value_error_naming_it(tmp_path: Path) -> None:
    txt = tmp_path / "lecture01.txt"
    txt.write_text("not captions\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r"\.txt"):
        ingest_captions(txt)


def test_missing_file_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        ingest_captions(tmp_path / "nope.vtt")


def test_merge_knobs_are_forwarded(fixtures_dir: Path, expected_segments: list[Segment]) -> None:
    """``max_segment_s`` below the fixture's longest merged span (49 s) changes the output."""
    path = fixtures_dir / "captions" / "lecture01.vtt"
    assert ingest_captions(path, max_segment_s=60.0) == expected_segments
    assert ingest_captions(path, max_segment_s=40.0) != expected_segments


# --- the captions-table rows with no other named test (Phase 1 done-gate) ----------


def _spans(segments: list[Segment], start_s: float, end_s: float) -> list[Segment]:
    return [s for s in segments if s.start_s == start_s and s.end_s == end_s]


def test_cue_09_gap_cue_gives_two_segments_sharing_its_span(
    expected_segments: list[Segment],
) -> None:
    assert len(_spans(expected_segments, 210.0, 240.0)) == 2


def test_cue_10_last_gap_cue_gives_two_segments_sharing_its_span(
    expected_segments: list[Segment],
) -> None:
    assert len(_spans(expected_segments, 240.0, 268.0)) == 2


def test_cue_16_slide_3_start_is_one_segment_mentioning_equation(
    expected_segments: list[Segment],
) -> None:
    (segment,) = _spans(expected_segments, 421.0, 445.0)
    assert "equation" in segment.text
