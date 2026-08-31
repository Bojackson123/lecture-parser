from lecturenotes.model import SlideRange, topic_id


def test_with_slides_uses_slide_range() -> None:
    assert topic_id("lec01", SlideRange(start=3, end=5), 12.0) == "lec01:s3-5"


def test_without_slides_uses_truncated_start_seconds() -> None:
    assert topic_id("lec01", None, 754.9) == "lec01:t754"


def test_same_inputs_same_output() -> None:
    a = topic_id("lec01", SlideRange(start=3, end=5), 12.0)
    b = topic_id("lec01", SlideRange(start=3, end=5), 12.0)
    assert a == b


def test_different_slide_ranges_give_different_ids() -> None:
    assert topic_id("lec01", SlideRange(start=3, end=5), 0.0) != topic_id(
        "lec01", SlideRange(start=3, end=6), 0.0
    )


def test_start_time_ignored_when_slides_present() -> None:
    assert topic_id("lec01", SlideRange(start=3, end=5), 0.0) == topic_id(
        "lec01", SlideRange(start=3, end=5), 999.0
    )


def test_lecture_id_is_part_of_the_key() -> None:
    assert topic_id("lec01", SlideRange(start=1, end=1), 0.0) != topic_id(
        "lec02", SlideRange(start=1, end=1), 0.0
    )
