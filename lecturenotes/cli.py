"""Command-line entrypoint for lecturenotes.

``build`` (P5-04) is the product: it composes ingest → align → generate for a week of
paired deck + caption files and writes the ``NoteWeek`` JSON (plus its ``media/``)
that ``render`` consumes — §7.1's regenerate-and-render tuning loop in two commands.
Pairing is sorted filename order, printed and confirmed, never inferred (§7.4);
``--dry-run`` prints the pairing and the exact chunking the real run would prompt
over and stops before any client exists (§8).

``push`` (P7-05) is stage 8 for a target that isn't a filesystem: it renders one
``NoteWeek`` JSON with the Notion renderer and delivers it under a parent page via
``emit_notion`` — credentials (``NOTION_TOKEN``, read at run time, never at import),
network and side effects, kept out of ``render`` so the §7.1 tuning loop stays pure.

Four inspection subcommands besides them: ``captions`` (P1-04) prints the segments one
caption file ingests to, ``slides`` (P2-04) prints the deck one slide file ingests to,
``render`` (P3-04; ``--format`` P6-03) prints what one ``NoteWeek`` JSON renders to in
the chosen format (or emits it with ``-o``), ``align`` (P4-04) prints the chunks one
deck and one caption file align
to, so a bad transcript, a deck whose columns interleaved, a renderer tweak, or a bad
chunk can be inspected in seconds (plan §8, §7.1). They run one stage on explicitly
named files only — pairing and generation belong to ``build``; in particular
``align`` takes two explicit paths and never guesses which caption file goes with
which deck (§7.4).
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
from collections.abc import Callable
from pathlib import Path

from lecturenotes import __version__
from lecturenotes.align.boundaries import Chunk, align_lecture
from lecturenotes.emit.filesystem import emit_filesystem
from lecturenotes.emit.notion_api import NotionTransport, UrllibTransport, emit_notion
from lecturenotes.generate.cache import CachedClient
from lecturenotes.generate.client import DEFAULT_MODEL, AnthropicClient, LLMClient
from lecturenotes.generate.lecture import generate_lecture, merge_chunks
from lecturenotes.generate.prompts import PROMPT_VERSION
from lecturenotes.ingest.captions import ingest_captions
from lecturenotes.ingest.slides import Deck, ingest_slides
from lecturenotes.model import NoteWeek, SourceRef
from lecturenotes.render.anki import AnkiRenderer
from lecturenotes.render.base import Renderer, RenderOptions, format_clock
from lecturenotes.render.markdown import MarkdownRenderer
from lecturenotes.render.notion import NotionRenderer

# The P6-03 format table, grown by the one entry Phase 7 reserved. A dict, not a
# plugin registry — three renderers still don't justify discovery.
_RENDERERS: dict[str, Callable[[], Renderer]] = {
    "markdown": MarkdownRenderer,
    "anki": AnkiRenderer,
    "notion": NotionRenderer,
}


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
        help="render a NoteWeek JSON to a chosen format (a debugging aid)",
        description="Load one NoteWeek JSON and render it with the chosen renderer: "
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
    render.add_argument(
        "--format",
        choices=sorted(_RENDERERS),
        default="markdown",
        help="output format (default: markdown)",
    )

    align = commands.add_parser(
        "align",
        help="align a slide deck with a caption file and print the chunks (a debugging aid)",
        description="Ingest one .pptx/.pdf deck and one .vtt/.srt caption file, align "
        "them, and print each chunk's header — 'slide N: Title' or '(no slide)' with "
        "its time span — followed by its segments.",
    )
    align.add_argument("deck", type=Path, help="a .pptx or .pdf slide deck")
    align.add_argument("captions", type=Path, help="a .vtt or .srt caption file")
    align.add_argument("--json", action="store_true", help="print the chunks as JSON")
    align.add_argument(
        "--min-gap-s",
        type=float,
        default=60.0,
        metavar="N",
        help="flag an unmatched stretch as a gap only if it spans at least N seconds "
        "(default 60)",
    )
    align.add_argument(
        "--min-silence-s",
        type=float,
        default=1.0,
        metavar="N",
        help="a gap must be bracketed by silences of at least N seconds (default 1)",
    )

    build = commands.add_parser(
        "build",
        help="build a week of study notes from paired decks and caption files",
        description="Pair decks (.pdf/.pptx) with caption files (.vtt/.srt) by sorted "
        "filename, print the pairing for confirmation, then ingest, align and generate "
        "one NoteWeek JSON plus its media/ directory — the input `lecturenotes render` "
        "consumes. --dry-run stops before generation and prints the chunking instead.",
    )
    build.add_argument(
        "paths",
        nargs="+",
        type=Path,
        metavar="PATH",
        help="deck/caption files, or directories scanned (non-recursively) for them",
    )
    build.add_argument(
        "--course", required=True, metavar="TEXT", help="course name, e.g. CS-RL-101"
    )
    build.add_argument("--week", type=int, required=True, metavar="N", help="week number")
    build.add_argument(
        "-o",
        "--out",
        type=Path,
        default=Path("notes"),
        metavar="DIR",
        help="output directory for the week JSON and media/ (default: notes)",
    )
    build.add_argument(
        "--dry-run",
        action="store_true",
        help="print the pairing and the chunking, then stop before generation",
    )
    build.add_argument(
        "--yes", action="store_true", help="accept the printed pairing without prompting"
    )
    build.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        metavar="ID",
        help=f"Anthropic model id (default: {DEFAULT_MODEL})",
    )
    build.add_argument(
        "--min-words",
        type=int,
        default=100,
        metavar="N",
        help="merge slide chunks below N transcript words into a neighbour (default 100)",
    )
    build.add_argument(
        "--cache-dir",
        type=Path,
        default=None,
        metavar="DIR",
        help="response cache directory (default: <out>/.cache)",
    )

    push = commands.add_parser(
        "push",
        help="push a NoteWeek JSON to a Notion page (reads NOTION_TOKEN)",
        description="Render one NoteWeek JSON with the Notion renderer and deliver it "
        "under a parent page: find or create the week's page by title, upload the "
        "figures, replace the content in place. The integration token is read from "
        "NOTION_TOKEN, never from a flag.",
    )
    push.add_argument(
        "file", type=Path, help="a NoteWeek JSON such as tests/fixtures/notes/week01.json"
    )
    push.add_argument(
        "--parent",
        required=True,
        metavar="PAGE_ID",
        help="the Notion page to create or update the week's page under",
    )
    push.add_argument(
        "--asset-root",
        type=Path,
        default=None,
        metavar="DIR",
        help="directory asset sources are relative to (default: the week JSON's directory)",
    )
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
    result = _RENDERERS[args.format]().render(week, RenderOptions())
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


def _print_chunks(chunks: list[Chunk], deck: Deck) -> None:
    """Chunk headers come from the deck's titles, not the chunk — ``Chunk``
    deliberately carries only numbers and segments (P4-04 decision)."""
    titles = {slide.number: slide.title for slide in deck.slides}
    for i, chunk in enumerate(chunks):
        if i:
            print()
        span = f"[{format_clock(chunk.start_s)}–{format_clock(chunk.end_s)}]"
        if chunk.slides is None:
            print(f"--- (no slide) {span}")
        elif chunk.slides.start == chunk.slides.end:
            title = titles.get(chunk.slides.start)
            name = f"slide {chunk.slides.start}"
            if title is not None:
                name += f": {title}"
            print(f"--- {name} {span}")
        else:  # not produced in v1 (width-1 ranges only), but never wrong
            print(f"--- slides {chunk.slides.start}–{chunk.slides.end} {span}")
        for s in chunk.segments:
            print(f"  [{format_clock(s.start_s)}–{format_clock(s.end_s)}] {s.text}")


def cmd_align(args: argparse.Namespace) -> int:
    try:
        deck = ingest_slides(args.deck)
        segments = ingest_captions(args.captions)
    except (OSError, ValueError) as exc:  # missing file, bad suffix, parse errors
        print(f"lecturenotes align: {exc}", file=sys.stderr)
        return 2
    chunks = align_lecture(
        deck, segments, min_gap_s=args.min_gap_s, min_silence_s=args.min_silence_s
    )
    _utf8_stdout()
    if args.json:
        print(json.dumps([chunk.model_dump() for chunk in chunks], indent=2))
    else:
        _print_chunks(chunks, deck)
    return 0


_DECK_SUFFIXES = {".pdf", ".pptx"}
_CAPTION_SUFFIXES = {".vtt", ".srt"}


def _make_client(model: str) -> LLMClient:
    """The one client seam (P5-04 decision): tests monkeypatch this, and
    ``ANTHROPIC_API_KEY`` handling stays inside ``AnthropicClient`` (consulted only on
    the first real ``complete``, never here)."""
    return AnthropicClient(model)


def _collect_pairs(paths: list[Path]) -> list[tuple[str, Path, Path]]:
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
                if child.suffix.lower() in _DECK_SUFFIXES:
                    decks.append(child)
                elif child.suffix.lower() in _CAPTION_SUFFIXES:
                    captions.append(child)
        elif path.suffix.lower() in _DECK_SUFFIXES:
            decks.append(path)
        elif path.suffix.lower() in _CAPTION_SUFFIXES:
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


def _course_slug(course: str) -> str:
    """Course lowercased, non-alphanumeric runs collapsed to ``-`` (§7.2: the week id
    feeds the stable topic ids, so it must be derivable and boring)."""
    return re.sub(r"[^a-z0-9]+", "-", course.lower()).strip("-")


def cmd_build(args: argparse.Namespace) -> int:
    try:
        pairs = _collect_pairs(args.paths)
    except ValueError as exc:
        print(f"lecturenotes build: {exc}", file=sys.stderr)
        return 2
    _utf8_stdout()
    print("pairing (sorted filename order — check it, a wrong pairing looks fine):")
    for lecture_id, deck_path, caption_path in pairs:
        print(f"  {lecture_id}: {deck_path} + {caption_path}")

    if args.dry_run:
        # Stops before any client exists: no key consulted, nothing spent (plan §8).
        # merge_chunks here and generate_lecture's internal merge share min_words, so
        # this is exactly the chunking the real run prompts over.
        for lecture_id, deck_path, caption_path in pairs:
            try:
                deck = ingest_slides(deck_path)
                segments = ingest_captions(caption_path)
            except (OSError, ValueError) as exc:
                print(f"lecturenotes build: {exc}", file=sys.stderr)
                return 2
            chunks = merge_chunks(align_lecture(deck, segments), args.min_words)
            print()
            if len(pairs) > 1:
                print(f"== {lecture_id}")
            _print_chunks(chunks, deck)
        return 0

    if not args.yes:
        if not sys.stdin.isatty():
            print(
                "lecturenotes build: stdin is not a terminal, so the pairing cannot be"
                " confirmed interactively; pass --yes to accept it",
                file=sys.stderr,
            )
            return 2
        answer = input("proceed with this pairing? [y/N] ")
        if answer.strip().lower() not in {"y", "yes"}:
            return 1

    cache_dir = args.cache_dir if args.cache_dir is not None else args.out / ".cache"
    client = CachedClient(_make_client(args.model), cache_dir, PROMPT_VERSION)
    lectures = []
    try:
        for lecture_id, deck_path, caption_path in pairs:
            deck = ingest_slides(deck_path)
            segments = ingest_captions(caption_path)
            lectures.append(
                generate_lecture(
                    deck,
                    align_lecture(deck, segments),
                    lecture_id=lecture_id,
                    source=SourceRef(
                        deck_path=deck_path.as_posix(), caption_path=caption_path.as_posix()
                    ),
                    client=client,
                    out_dir=args.out,
                    min_words=args.min_words,
                )
            )
    except (OSError, ValueError) as exc:  # bad file, bad response, hallucinated figure
        print(f"lecturenotes build: {exc}", file=sys.stderr)
        return 2
    week = NoteWeek(
        id=f"{_course_slug(args.course)}-w{args.week:02d}",
        course=args.course,
        week_number=args.week,
        lectures=lectures,
    )
    args.out.mkdir(parents=True, exist_ok=True)
    target = args.out / f"{week.id}.json"
    # Bytes, not write_text: the week01.json convention is UTF-8 + LF everywhere.
    target.write_bytes((week.model_dump_json(indent=2) + "\n").encode("utf-8"))
    topic_count = sum(len(lecture.topics) for lecture in week.lectures)
    asset_count = sum(len(lecture.assets) for lecture in week.lectures)
    print(
        f"wrote {target}: {len(week.lectures)} lecture(s),"
        f" {topic_count} topic(s), {asset_count} asset(s)"
    )
    return 0


def _load_dotenv(path: Path = Path(".env")) -> None:
    """Seed ``os.environ`` from a ``.env`` in the working directory, if one exists.

    ``KEY=VALUE`` lines only; ``#`` comments and blanks skipped; matching quotes
    around a value are unwrapped. ``setdefault``, so a real environment variable
    always wins. Stdlib on purpose (the P7-04 urllib reasoning: no new dependency),
    and read-at-use-time survives — this populates the environment in ``main()``,
    while the tokens are still consulted only where they always were
    (``cmd_push``; a real ``complete``).
    """
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


def _make_transport(token: str) -> NotionTransport:
    """The one transport seam (the P5-04 ``_make_client`` pattern): tests monkeypatch
    this and no test touches the network. ``NOTION_TOKEN`` is read by ``cmd_push`` at
    run time — never at import, never here."""
    return UrllibTransport(token)


def cmd_push(args: argparse.Namespace) -> int:
    try:
        week = NoteWeek.model_validate_json(args.file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:  # missing file, bad JSON, ValidationError
        print(f"lecturenotes push: {exc}", file=sys.stderr)
        return 2
    result = NotionRenderer().render(week, RenderOptions())
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        print("lecturenotes push: NOTION_TOKEN is not set", file=sys.stderr)
        return 2
    asset_root = args.asset_root if args.asset_root is not None else args.file.parent
    transport = _make_transport(token)
    try:
        emit_notion(result, transport, parent_page_id=args.parent, asset_root=asset_root)
    except (OSError, ValueError, RuntimeError) as exc:  # missing asset, API failure
        print(f"lecturenotes push: {exc}", file=sys.stderr)
        return 2
    payload_doc = json.loads(result.documents[0].text)
    title = payload_doc["page"]["title"]
    _utf8_stdout()  # the title carries the week separator em-dash
    print(
        f'pushed "{title}": {len(payload_doc["payloads"])} payload(s),'
        f" {len(result.assets)} asset(s)"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    _load_dotenv()
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
    if args.command == "align":
        return cmd_align(args)
    if args.command == "build":
        return cmd_build(args)
    if args.command == "push":
        return cmd_push(args)
    parser.print_help()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
