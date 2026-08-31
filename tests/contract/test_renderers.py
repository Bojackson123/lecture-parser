"""Renderer contract tests (plan §8) — scaffold only until Phase 3.

Every renderer registered in ``RENDERERS`` must satisfy four properties against the
``week01`` fixture:

1. **Renders without raising** on the full IR.
2. **Respects declared capabilities**: after ``degrade()`` to the renderer's declared
   ``Capability`` set, the output contains no construct the renderer said it lacks.
3. **Deterministic**: rendering the same ``NoteWeek`` twice yields identical output.
4. **Every ``SourceAnchor`` survives** into the output in some form (timestamp and/or
   slide range), so any claim remains checkable.

The registry is typed ``list[object]`` on purpose: the ``Renderer`` protocol lives in
``render/base.py`` from Phase 3, and this file must import nothing that does not exist.
"""

import pytest

from lecturenotes.model import NoteWeek

RENDERERS: list[object] = []  # Phase 3 registers renderers here; typed properly then.


@pytest.mark.parametrize(
    "renderer",
    RENDERERS or [pytest.param(None, marks=pytest.mark.skip(reason="no renderers yet"))],
)
def test_contract(renderer: object, week01: NoteWeek) -> None:
    raise NotImplementedError("Phase 3 implements the four contract properties above")
