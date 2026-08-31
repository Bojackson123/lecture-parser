"""Stable topic ids (plan §7.2)."""

from lecturenotes.model.source import SlideRange


def topic_id(lecture_id: str, slides: SlideRange | None, start_s: float) -> str:
    """Derive a topic id from its source coordinates.

    Plan §7.2: "Topic ids must survive regeneration so that re-emitting **updates**
    rather than duplicates. Derive them from source coordinates — ``lecture_id +
    slide_range`` — not from position in the list or a slug of the heading, both of
    which move when you change a prompt."

    With slides: ``"lec01:s3-5"``. Without (board work, gaps between decks): the
    whole-second start time, ``"lec01:t754"``.

    Non-goal: ids never derive from list position or heading text.
    """
    if slides is not None:
        return f"{lecture_id}:s{slides.start}-{slides.end}"
    return f"{lecture_id}:t{int(start_s)}"
