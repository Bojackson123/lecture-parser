"""Slide/speech alignment: scoring and monotonic boundaries (plan §3 stage 4, §4.1).

``align_lecture`` is the only entrypoint — anything that needs chunks calls it. The
scoring and boundary functions are exported for debugging and tests, not for
re-composition elsewhere (the ``ingest_captions``/``ingest_slides`` rule).
"""

from lecturenotes.align.boundaries import Chunk, align_lecture, solve_windows, span_units
from lecturenotes.align.scoring import STOPWORDS, score, slide_terms, term_weights, tokenize

__all__ = [
    "STOPWORDS",
    "Chunk",
    "align_lecture",
    "score",
    "slide_terms",
    "solve_windows",
    "span_units",
    "term_weights",
    "tokenize",
]
