"""Hypothesis strategies shared by the ``tests/ingest`` property modules.

Introduced in P1-01 (parse round trips); P1-02 builds its rolling-repeat corruption on
top of ``cue_lists``, and P1-03 is expected to do the same for sentence merging.
"""

from __future__ import annotations

import itertools

from hypothesis import strategies as st

from lecturenotes.ingest.captions import Cue

MAX_MS = 99 * 3600 * 1000 + 59 * 60 * 1000 + 59 * 1000 + 999  # 99:59:59.999

# Non-whitespace, printable, no markup characters — and hence no "-->".
WORD_CHARS = st.characters(blacklist_categories=("Z", "C"), blacklist_characters="<>&")
WORD = st.text(alphabet=WORD_CHARS, min_size=1, max_size=12)
# Already normalised: single spaces, no leading/trailing whitespace.
LINE = st.lists(WORD, min_size=1, max_size=8).map(" ".join)


@st.composite
def cue_lists(draw: st.DrawFn) -> list[Cue]:
    """1–30 cues with strictly increasing, non-overlapping spans and 1–3 clean lines each."""
    n = draw(st.integers(min_value=1, max_value=30))
    # Strictly positive gaps, accumulated: start_i < end_i < start_{i+1}, well under MAX_MS.
    gaps = draw(st.lists(st.integers(1, 60_000), min_size=2 * n, max_size=2 * n))
    bounds = list(itertools.accumulate(gaps, initial=draw(st.integers(0, 60_000))))[1:]
    return [
        Cue(
            start_s=bounds[2 * i] / 1000,
            end_s=bounds[2 * i + 1] / 1000,
            lines=tuple(draw(st.lists(LINE, min_size=1, max_size=3))),
        )
        for i in range(n)
    ]
