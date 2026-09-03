"""Command-line entrypoint for lecturenotes.

Three inspection subcommands so far: ``captions`` (P1-04) prints the segments one
caption file ingests to, ``slides`` (P2-04) prints the deck one slide file ingests to,
``render`` (P3-04) prints the markdown one ``NoteWeek`` JSON renders to (or emits it
with ``-o``), so a bad transcript, a deck whose columns interleaved, or a renderer
tweak can be inspected in seconds (plan §8, §7.1). They run one stage on one file only
— pairing, chunking, alignment and generation belong to ``build`` (Phase 5).
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

from lecturenotes import __version__
from lecturenotes.emit.filesystem import emit_filesystem
from lecturenotes.ingest.captions import ingest_captions
from lecturenotes.ingest.slides import Deck, ingest_slides
from lecturenotes.model import NoteWeek
from lecturenotes.render.base import RenderOptions, format_clock
from lecturenotes.render.markdown import MarkdownRenderer


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

    render = commands.add_parser(
        "render",
        help="render a NoteWeek JSON to markdown (a debugging aid)",
        description="Load one NoteWeek JSON and render it with the markdown renderer: "
        "print each document after a '--- name' line, or emit the documents and their "
        "assets under a directory with -o.",
    )
    render.add_argument(
        "file", type=Path, help="a NoteWeek JSON such as tests/fixtures/notes/week01.json"
    )
    render.add_argument(
        "-o",
        "--out",
        type=Path,
        default=None,
        metavar="DIR",
        help="emit the documents and assets under DIR instead of printing",
    )
    render.add_argument("--json", action="store_true", help="print the RenderResult as JSON")
    return parser


def _utf8_stdout() -> None:
    """Windows consoles default to a code page that mangles the en-dash in ``[0:01–0:26]``,
    and Windows pipes translate ``\\n`` to ``\\r\\n``, which would break ``render``'s
    byte-for-byte diff against the expected markdown. UTF-8 and LF, everywhere."""
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")


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


def cmd_render(args: argparse.Namespace) -> int:
    try:
        week = NoteWeek.model_validate_json(args.file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:  # missing file, bad JSON, ValidationError
        print(f"lecturenotes render: {exc}", file=sys.stderr)
        return 2
    result = MarkdownRenderer().render(week, RenderOptions())
    if args.out is not None:
        try:
            # asset_root stays at its cwd default: the fixture's sources are
            # repo-root-relative (P3-04 decision).
            emit_filesystem(result, args.out)
        except (OSError, ValueError) as exc:  # unwritable target, missing asset source
            print(f"lecturenotes render: {exc}", file=sys.stderr)
            return 2
        return 0  # quiet on success: the output paths are deterministic
    _utf8_stdout()
    if args.json:
        print(result.model_dump_json(indent=2))
    else:
        for document in result.documents:
            print(f"--- {document.name}")
            print(document.text, end="")  # already newline-terminated
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
    if args.command == "render":
        return cmd_render(args)
    parser.print_help()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
