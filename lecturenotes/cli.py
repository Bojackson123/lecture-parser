"""Command-line entrypoint for lecturenotes.

One subcommand so far, ``captions`` (P1-04): print the segments one caption file
ingests to, so a bad transcript can be inspected in seconds (plan §8). It prints
segments only — pairing, chunking and generation belong to ``build`` (Phase 5).
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

from lecturenotes import __version__
from lecturenotes.ingest.captions import ingest_captions


def format_clock(seconds: float) -> str:
    """``m:ss``, or ``h:mm:ss`` once past an hour; whole seconds, floored."""
    total = int(seconds)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


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
    parser.print_help()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
