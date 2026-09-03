"""Command-line entrypoint for lecturenotes.

Two inspection subcommands so far: ``captions`` (P1-04) prints the segments one
caption file ingests to, ``slides`` (P2-04) prints the deck one slide file ingests to,
so a bad transcript or a deck whose columns interleaved can be inspected in seconds
(plan §8). They print one file's stage output only — pairing, chunking, alignment and
generation belong to ``build`` (Phase 5).
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

from lecturenotes import __version__
from lecturenotes.ingest.captions import ingest_captions
from lecturenotes.ingest.slides import Deck, ingest_slides
from lecturenotes.render.base import format_clock


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lecturenotes",
        description="Turn a week of lecture material into structured study notes.",
    )
    parser.add_argument("--version", action="store_true", help="print the version and exit")
    commands = parser.add_subparsers(dest="command", metavar="COMMAND")

    captions = commands.add_parser(
        "captions",
        help="print the segments one caption file ingests to (a debugging aid)",
        description="Parse, dedupe and sentence-merge one .vtt/.srt file and print the "
        "resulting segments, one per line as '[m:ss–m:ss] text'.",
    )
    captions.add_argument("file", type=Path, help="a .vtt or .srt caption file")
    captions.add_argument("--json", action="store_true", help="print the segments as JSON")
    captions.add_argument(
        "--max-gap-s",
        type=float,
        default=5.0,
        metavar="N",
        help="flush an unfinished sentence across a silence longer than N seconds (default 5)",
    )
    captions.add_argument(
        "--max-segment-s",
        type=float,
        default=60.0,
        metavar="N",
        help="flush an unfinished sentence before it spans more than N seconds (default 60)",
    )

    slides = commands.add_parser(
        "slides",
        help="print the deck one slide file ingests to (a debugging aid)",
        description="Parse one .pptx/.pdf file and print each slide's title, text blocks "
        "in reading order and images, then any image set aside as recurring (a logo).",
    )
    slides.add_argument("file", type=Path, help="a .pptx or .pdf slide deck")
    slides.add_argument("--json", action="store_true", help="print the whole Deck as JSON")
    slides.add_argument("--notes", action="store_true", help="also print speaker notes")
    slides.add_argument(
        "--min-px",
        type=int,
        default=32,
        metavar="N",
        help="drop images narrower or shorter than N pixels as decoration (default 32)",
    )
    return parser


def _utf8_stdout() -> None:
    """Windows consoles default to a code page that mangles the en-dash in ``[0:01–0:26]``."""
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")


def cmd_captions(args: argparse.Namespace) -> int:
    try:
        segments = ingest_captions(
            args.file, max_gap_s=args.max_gap_s, max_segment_s=args.max_segment_s
        )
    except (OSError, ValueError) as exc:  # missing file, bad suffix, CaptionParseError
        print(f"lecturenotes captions: {exc}", file=sys.stderr)
        return 2
    _utf8_stdout()
    if args.json:
        print(json.dumps([s.model_dump() for s in segments], indent=2))
    else:
        for s in segments:
            print(f"[{format_clock(s.start_s)}–{format_clock(s.end_s)}] {s.text}")
    return 0


def _print_deck(deck: Deck, *, notes: bool) -> None:
    assets = {asset.id: asset for asset in deck.assets}
    for slide in deck.slides:
        if slide.number > 1:
            print()
        header = f"--- slide {slide.number}"
        if slide.title is not None:
            header += f": {slide.title}"
        if slide.hidden:
            header += " [hidden]"
        print(header)
        for i, block in enumerate(slide.blocks):
            if i:
                print()
            for line in block.lines:
                print(line)
        for image_id in slide.image_ids:
            a = assets[image_id]
            print(f"[image {a.id} {a.width}x{a.height} {a.media_type}]")
        if notes and slide.notes is not None:
            print(f"[notes] {slide.notes}")
    for image_id in deck.recurring_image_ids:
        a = assets[image_id]
        print(f"[recurring] {a.id} {a.width}x{a.height} {a.media_type}")


def cmd_slides(args: argparse.Namespace) -> int:
    try:
        deck = ingest_slides(args.file, min_px=args.min_px)
    except (OSError, ValueError) as exc:  # missing file, bad suffix, DeckParseError
        print(f"lecturenotes slides: {exc}", file=sys.stderr)
        return 2
    _utf8_stdout()
    if args.json:
        print(deck.model_dump_json(indent=2))
    else:
        _print_deck(deck, notes=args.notes)
    return 0


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = build_parser()
    if not argv:
        parser.print_help()
        return 0
    args = parser.parse_args(argv)
    if args.version:
        print(f"lecturenotes {__version__}")
        return 0
    if args.command == "captions":
        return cmd_captions(args)
    if args.command == "slides":
        return cmd_slides(args)
    parser.print_help()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
