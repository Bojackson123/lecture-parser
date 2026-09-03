"""Renderer contract tests (plan §8).

Every renderer registered in ``RENDERERS`` must satisfy four properties against the
``week01`` fixture:

1. **Renders without raising** on the full IR.
2. **Respects declared capabilities**: after ``degrade()`` to the renderer's declared
   ``Capability`` set, the IR contains no construct the renderer said it lacks, and the
   renderer renders that degraded week without raising. (IR-level on purpose —
   output-level checks cannot be generic across renderers.)
3. **Deterministic**: rendering the same ``NoteWeek`` twice yields equal results.
4. **Every ``SourceAnchor`` survives**: ``format_clock(topic.anchor.start_s)`` appears
   somewhere in the output text, so any claim remains checkable. This is why
   ``format_clock`` lives in ``render/base.py``: every renderer must surface anchors
   through it.

P3-02 and later phases register renderers here; the properties then run against each.
"""

from __future__ import annotations

import pytest

from lecturenotes.model import NoteWeek, constructs_used, degrade
from lecturenotes.render.base import Renderer, RenderOptions, format_clock

RENDERERS: list[Renderer] = []  # P3-02 registers MarkdownRenderer here.

_PARAMS = RENDERERS or [pytest.param(None, marks=pytest.mark.skip(reason="no renderers yet"))]


@pytest.mark.parametrize("renderer", _PARAMS)
def test_renders_without_raising(renderer: Renderer, week01: NoteWeek) -> None:
    renderer.render(week01, RenderOptions())


@pytest.mark.parametrize("renderer", _PARAMS)
def test_respects_declared_capabilities(renderer: Renderer, week01: NoteWeek) -> None:
    degraded = degrade(week01, renderer.capabilities)
    assert constructs_used(degraded) <= renderer.capabilities
    renderer.render(degraded, RenderOptions())


@pytest.mark.parametrize("renderer", _PARAMS)
def test_deterministic(renderer: Renderer, week01: NoteWeek) -> None:
    assert renderer.render(week01, RenderOptions()) == renderer.render(week01, RenderOptions())


@pytest.mark.parametrize("renderer", _PARAMS)
def test_every_source_anchor_survives(renderer: Renderer, week01: NoteWeek) -> None:
    result = renderer.render(week01, RenderOptions())
    text = "\n".join(document.text for document in result.documents)
    for lecture in week01.lectures:
        for topic in lecture.topics:
            assert format_clock(topic.anchor.start_s) in text, topic.id
