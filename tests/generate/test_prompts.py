"""P5-02/P5-03 prompt tests: request keys, prompt contents, and the pinned
instructions.

The exact-substring pins are the arbiter for prompt regressions (the ticket's rule:
this file pins what the prompt *contains*, not how well it works). The prompts embed
``ChunkNotes.model_json_schema()`` / ``LectureSynthesis.model_json_schema()``, so a
schema edit that silently drops the embedding fails here.
"""

from __future__ import annotations

from lecturenotes.align import Chunk
from lecturenotes.generate.prompts import (
    PROMPT_VERSION,
    ChunkNotes,
    LectureSynthesis,
    chunk_prompt,
    synthesis_prompt,
)
from lecturenotes.ingest.slides import Deck
from lecturenotes.model import NoteWeek

PPTX_IMAGE_ID = "img-a63ae9b7dc5e9397"

# --- request keys -------------------------------------------------------------------


def test_prompt_version_is_pinned() -> None:
    # "2": P6-01 added the at-least-one-card instruction (a deliberate §7.1 bump).
    assert PROMPT_VERSION == "2"


def test_slide_chunk_key_is_chunk_plus_topic_id(chunks: list[Chunk], deck: Deck) -> None:
    assert chunk_prompt(chunks[2], deck, "lec01").key == "chunk:lec01:s2-2"


def test_gap_chunk_key_uses_the_start_time(chunks: list[Chunk], deck: Deck) -> None:
    assert chunk_prompt(chunks[1], deck, "lec01").key == "chunk:lec01:t151"


# --- the slide-2 prompt: transcript, slide context, speaker notes -------------------


def test_prompt_contains_every_segment_with_its_span(chunks: list[Chunk], deck: Deck) -> None:
    prompt = chunk_prompt(chunks[2], deck, "lec01").prompt
    for segment in chunks[2].segments:
        assert f"[{segment.start_s}-{segment.end_s}] {segment.text}" in prompt


def test_prompt_contains_the_slide_title_and_block_lines(chunks: list[Chunk], deck: Deck) -> None:
    prompt = chunk_prompt(chunks[2], deck, "lec01").prompt
    slide = deck.slides[1]
    assert slide.title is not None and slide.title in prompt
    for block in slide.blocks:
        for line in block.lines:
            assert line in prompt


def test_prompt_contains_the_speaker_notes(chunks: list[Chunk], deck: Deck) -> None:
    """"this will be on the exam" appears twice: cue 14 and the slide-2 note."""
    prompt = chunk_prompt(chunks[2], deck, "lec01").prompt
    notes = deck.slides[1].notes
    assert notes is not None and notes in prompt
    assert prompt.count("this will be on the exam") == 2


def test_pptx_prompt_lists_image_ids_with_pixel_sizes(chunks: list[Chunk], deck: Deck) -> None:
    prompt = chunk_prompt(chunks[3], deck, "lec01").prompt
    assert f"{PPTX_IMAGE_ID} (240x150)" in prompt


# --- the same calls on the PDF deck: format differences stay inside the prompt ------


def test_pdf_prompt_has_no_notes_section(chunks: list[Chunk], pdf_deck: Deck) -> None:
    prompt = chunk_prompt(chunks[2], pdf_deck, "lec01").prompt
    assert "Speaker notes" not in prompt
    assert prompt.count("this will be on the exam") == 1  # cue 14 only


def test_pdf_prompt_lists_the_pdf_deck_image_ids(chunks: list[Chunk], pdf_deck: Deck) -> None:
    prompt = chunk_prompt(chunks[3], pdf_deck, "lec01").prompt
    pdf_image_id = pdf_deck.slides[2].image_ids[0]
    assert pdf_image_id != PPTX_IMAGE_ID  # pypdf re-encodes (P2-03)
    assert f"{pdf_image_id} (240x150)" in prompt
    assert PPTX_IMAGE_ID not in prompt


# --- the gap-chunk prompt -----------------------------------------------------------


def test_gap_prompt_has_no_slide_context(chunks: list[Chunk], deck: Deck) -> None:
    prompt = chunk_prompt(chunks[1], deck, "lec01").prompt
    prompt_lines = set(prompt.splitlines())
    for slide in deck.slides:
        assert slide.title is not None and slide.title not in prompt
        assert slide.notes is not None and slide.notes not in prompt
        for block in slide.blocks:
            # Whole-line membership: a one-word line like "Equation" may legitimately
            # occur inside instruction text, but never as slide context of its own.
            assert not set(block.lines) & prompt_lines
    assert "Speaker notes" not in prompt
    assert "img-" not in prompt


def test_gap_prompt_contains_the_board_work_framing(chunks: list[Chunk], deck: Deck) -> None:
    prompt = chunk_prompt(chunks[1], deck, "lec01").prompt
    assert "The lecturer was away from the slides" in prompt


# --- instruction pins (exact substrings, the arbiter for prompt regressions) --------


def test_instruction_pins(chunks: list[Chunk], deck: Deck) -> None:
    for chunk in chunks:
        prompt = chunk_prompt(chunk, deck, "lec01").prompt
        assert "Start the body with a short prose summary, then a bullet list of key points" in (
            prompt
        )
        assert "Write mathematics as LaTeX, only inside Equation nodes" in prompt
        assert "Quote exam or emphasis remarks near-verbatim in a Callout of kind EXAM" in prompt
        assert "Produce at least one card per topic" in prompt
        assert "use a Callout of kind UNCERTAIN instead of guessing" in prompt
        assert "Reference only the listed image ids in Figure nodes" in prompt


# --- the embedded response schema ---------------------------------------------------


def test_prompt_embeds_the_chunk_notes_schema(chunks: list[Chunk], deck: Deck) -> None:
    prompt = chunk_prompt(chunks[2], deck, "lec01").prompt
    assert '"image_alts"' in prompt  # a distinctive ChunkNotes schema fragment


def test_chunk_notes_schema_declares_image_alts() -> None:
    schema = ChunkNotes.model_json_schema()
    assert "image_alts" in schema["properties"]


# --- the synthesis prompt (P5-03) ---------------------------------------------------


def test_synthesis_key_is_synthesis_plus_lecture_id(week01: NoteWeek) -> None:
    assert synthesis_prompt(week01.lectures[0].topics, "lec01").key == "synthesis:lec01"


def test_synthesis_prompt_contains_every_topic_heading(week01: NoteWeek) -> None:
    topics = week01.lectures[0].topics
    prompt = synthesis_prompt(topics, "lec01").prompt
    for topic in topics:
        assert topic.heading in prompt


def test_synthesis_prompt_contains_the_topic_bodies(week01: NoteWeek) -> None:
    """The model reads the IR it just wrote: bodies ride along as compact JSON."""
    prompt = synthesis_prompt(week01.lectures[0].topics, "lec01").prompt
    assert "Sequential decision making starts with a Markov decision process." in prompt
    assert "solve the last decision first" in prompt


def test_synthesis_instruction_pins(week01: NoteWeek) -> None:
    prompt = synthesis_prompt(week01.lectures[0].topics, "lec01").prompt
    assert "overview of a few sentences" in prompt
    assert "2-4 objectives" in prompt
    assert "only for terms the topics actually define or use" in prompt
    # The §4.2 anti-hallucination stance at lecture level (exact substring).
    assert "Add nothing the topics do not support" in prompt


def test_synthesis_prompt_embeds_the_lecture_synthesis_schema(week01: NoteWeek) -> None:
    prompt = synthesis_prompt(week01.lectures[0].topics, "lec01").prompt
    assert '"open_questions"' in prompt  # a distinctive LectureSynthesis schema fragment


def test_lecture_synthesis_schema_declares_open_questions() -> None:
    schema = LectureSynthesis.model_json_schema()
    assert "open_questions" in schema["properties"]
