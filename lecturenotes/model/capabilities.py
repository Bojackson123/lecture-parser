"""Renderer capabilities (plan §2.3).

A renderer declares the set of ``Capability`` values it supports; anything the IR uses
that the renderer lacks is rewritten by a shared helper before rendering, so
degradation is declared, not improvised.

``degrade()`` (plan §2.3) will live here from Phase 3, once there is a first renderer
to degrade *for*.
"""

from enum import StrEnum


class Capability(StrEnum):
    NATIVE_MATH = "NATIVE_MATH"
    NESTING = "NESTING"
    CALLOUTS = "CALLOUTS"
    TABLES = "TABLES"
    IMAGES = "IMAGES"
    CODE = "CODE"
