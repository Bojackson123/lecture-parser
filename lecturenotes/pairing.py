"""Sorted-filename pairing and the course slug — the §7.4 helpers both frontends share.

Moved verbatim from ``cli.py`` (PW-01) so the CLI and the web layer run the same
pairing code: whichever frontend shows the pairing, the user is confirming the output
of this one function. Pure and stdlib-only; the "nothing in the pipeline imports the
web layer" contract lists this module as a source, so it can never grow a web import.
"""

from __future__ import annotations

import re
from pathlib import Path

DECK_SUFFIXES = {".pdf", ".pptx"}
CAPTION_SUFFIXES = {".vtt", ".srt"}


def collect_pairs(paths: list[Path]) -> list[tuple[str, Path, Path]]:
    """Sorted-filename pairing (plan §7.4): ``[(lecture_id, deck, captions)]``.

    Directories are scanned non-recursively for known suffixes; explicit files are
    classified by suffix and anything else is an error. No stem matching, no duration
    comparison, no content sniffing — §7.4 rejects inference on purpose; the caller
    prints the result and the user confirms it.
    """
    decks: list[Path] = []
    captions: list[Path] = []
    for path in paths:
        if path.is_dir():
            for child in sorted(path.iterdir()):
                if child.suffix.lower() in DECK_SUFFIXES:
                    decks.append(child)
                elif child.suffix.lower() in CAPTION_SUFFIXES:
                    captions.append(child)
        elif path.suffix.lower() in DECK_SUFFIXES:
            decks.append(path)
        elif path.suffix.lower() in CAPTION_SUFFIXES:
            captions.append(path)
        else:
            raise ValueError(
                f"{path}: not a deck (.pdf/.pptx), a caption file (.vtt/.srt),"
                " or a directory"
            )
    decks.sort(key=lambda p: p.name)
    captions.sort(key=lambda p: p.name)
    if len(decks) != len(captions):
        deck_names = ", ".join(p.name for p in decks) or "(none)"
        caption_names = ", ".join(p.name for p in captions) or "(none)"
        raise ValueError(
            f"{len(decks)} deck(s) but {len(captions)} caption file(s);"
            f" every deck needs exactly one caption file."
            f" decks: {deck_names}. captions: {caption_names}"
        )
    if not decks:
        raise ValueError("no decks or caption files found")
    return [
        (f"lec{n:02d}", deck, caption)
        for n, (deck, caption) in enumerate(zip(decks, captions, strict=True), start=1)
    ]


def course_slug(course: str) -> str:
    """Course lowercased, non-alphanumeric runs collapsed to ``-`` (§7.2: the week id
    feeds the stable topic ids, so it must be derivable and boring)."""
    return re.sub(r"[^a-z0-9]+", "-", course.lower()).strip("-")
