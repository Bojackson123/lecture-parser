"""The local web GUI (Side-track W): ``lecturenotes serve``.

A composer like ``cli`` — it imports both halves of the pipeline and wires them to
HTTP, and grows no pipeline logic of its own. Nothing in the pipeline may import
this package back (the 5th import-linter contract). The stack lives in the ``web``
dependency group, part of ``default-groups`` so a plain ``uv sync`` installs it.
"""
