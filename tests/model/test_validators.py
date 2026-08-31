import pytest
from pydantic import ValidationError

from lecturenotes.model import (
    Figure,
    MediaAsset,
    NoteLecture,
    NoteWeek,
    Prose,
    SlideRange,
    SourceAnchor,
    SourceRef,
    Topic,
)


def _lecture(lecture_id: str = "lec01", **overrides: object) -> NoteLecture:
    fields: dict[str, object] = {
        "id": lecture_id,
        "title": "T",
        "overview": "O",
        "objectives": [],
        "source": SourceRef(),
        "topics": [
            Topic(
                id=f"{lecture_id}:t0",
                heading="H",
                anchor=SourceAnchor(start_s=0, end_s=1),
                body=[Prose(text="p")],
            )
        ],
    }
    fields.update(overrides)
    return NoteLecture.model_validate(fields)


def test_slide_range_accepts_valid() -> None:
    assert SlideRange(start=1, end=1).end == 1
    assert SlideRange(start=3, end=5).start == 3


def test_slide_range_end_before_start_raises() -> None:
    with pytest.raises(ValidationError):
        SlideRange(start=3, end=2)


def test_slide_range_is_one_based() -> None:
    with pytest.raises(ValidationError):
        SlideRange(start=0, end=1)


def test_source_anchor_end_before_start_raises() -> None:
    with pytest.raises(ValidationError):
        SourceAnchor(start_s=10.0, end_s=5.0)


def test_source_anchor_negative_start_raises() -> None:
    with pytest.raises(ValidationError):
        SourceAnchor(start_s=-1.0, end_s=5.0)


def test_source_anchor_zero_length_is_fine() -> None:
    assert SourceAnchor(start_s=5.0, end_s=5.0).slides is None


def test_figure_with_known_asset_is_fine() -> None:
    topic = Topic(
        id="lec01:s1-1",
        heading="H",
        anchor=SourceAnchor(start_s=0, end_s=1, slides=SlideRange(start=1, end=1)),
        body=[Figure(asset_id="a1")],
    )
    lecture = _lecture(
        topics=[topic],
        assets=[MediaAsset(id="a1", media_type="image/png", source="a1.png")],
    )
    assert lecture.assets[0].id == "a1"


def test_figure_referencing_unknown_asset_raises() -> None:
    topic = Topic(
        id="lec01:s1-1",
        heading="H",
        anchor=SourceAnchor(start_s=0, end_s=1),
        body=[Figure(asset_id="missing")],
    )
    with pytest.raises(ValidationError, match="missing"):
        _lecture(topics=[topic])


def test_duplicate_asset_ids_raise() -> None:
    dup = MediaAsset(id="a1", media_type="image/png", source="a1.png")
    with pytest.raises(ValidationError, match="a1"):
        _lecture(assets=[dup, dup])


def test_duplicate_lecture_ids_in_week_raise() -> None:
    with pytest.raises(ValidationError, match="lec01"):
        NoteWeek(id="w01", course="C", week_number=1, lectures=[_lecture(), _lecture()])


def test_distinct_lecture_ids_in_week_are_fine() -> None:
    week = NoteWeek(
        id="w01", course="C", week_number=1, lectures=[_lecture("lec01"), _lecture("lec02")]
    )
    assert [lec.id for lec in week.lectures] == ["lec01", "lec02"]


def test_extra_field_on_notes_types_raises() -> None:
    with pytest.raises(ValidationError):
        _lecture(colour="red")


def test_notes_types_are_frozen() -> None:
    lecture = _lecture()
    with pytest.raises(ValidationError):
        lecture.title = "new"  # type: ignore[misc]
