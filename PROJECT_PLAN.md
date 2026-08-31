# Lecture Material → Structured Notes

A project plan. Intended to be worked through with Claude Code, phase by phase.

---

## 1. Goal

Take one week of course material — any mix of lecture videos, slide decks,
transcripts, and WebVTT subtitles, with multiple of each — and produce structured
study notes in whatever format is wanted, without the pipeline knowing or caring
which format that is.

**In scope:** ingestion, slide/speech alignment, note generation, pluggable output.

**Out of scope (v1):** speech-to-text (assume captions are provided), OCR of scanned
handouts, incremental live processing, a GUI.

**Success criterion:** for a week you attended, the notes are good enough that you
revise from them instead of rewatching. For a week you missed, they tell you what you
missed and where in the video to go.

---

## 2. Central design decision: the note IR

The pipeline is two halves joined by one data structure.

```
   sources ──► ingest ──► align ──► generate ──►  NoteDocument  ──► render ──► emit
                                                  ^^^^^^^^^^^^
                                              the only contract
```

Everything left of `NoteDocument` is about understanding the lecture. Everything right
of it is about presentation. Neither half imports the other.

### 2.1 Why not markdown as the IR

Markdown is the obvious choice and it's wrong here. Converting markdown to Notion
blocks, Anki cards, or LaTeX means re-parsing prose and guessing at intent: is this
indented block a quote, a callout, or a nested list? Is `$$...$$` display math or
literal text? You'd be throwing away structure the generator already knew and then
trying to recover it.

Generate structured data; render markdown from it as one output among several.

### 2.2 Model shape

Semantic node types, not presentational ones. The renderer decides what a
`Callout(kind=EXAM)` looks like; the IR only records that the lecturer flagged it.

```python
NoteWeek
  id, course, week_number, lectures: [NoteLecture]

NoteLecture
  id, title, overview, objectives: [str]
  source: SourceRef            # video url, deck path, caption path
  topics: [Topic]
  glossary: [Definition]
  open_questions: [str]

Topic
  id                           # stable, see §7.2
  heading: str
  anchor: SourceAnchor         # timestamp + slide range — the citation
  body: [Node]                 # ordered, heterogeneous
  cards: [CardSeed]            # optional Q/A pairs for spaced-repetition targets

Node = Prose | BulletList | Definition | Equation | CodeBlock
     | Callout | Figure | Table | Quote
```

Notable choices:

- **`Equation` holds LaTeX, always.** Every plausible target consumes LaTeX natively
  or near-natively. Storing rendered math would be a one-way door.
- **`Callout` has a `kind` enum**, not a colour or emoji: `EXAM`, `PITFALL`,
  `UNCERTAIN`, `ASIDE`. Presentation is downstream.
- **`SourceAnchor` on every topic** is the feature that makes the notes trustworthy.
  Timestamp plus slide numbers, so any claim can be checked in seconds.
- **`CardSeed` is generated but ignored by document renderers.** Costs nothing to
  produce alongside the notes; makes the Anki target trivial later. Don't add a
  separate extraction pass for it.
- **`Figure` references a `MediaAsset` by id**, not a path. Assets are resolved by the
  emitter — inlined as base64, uploaded, or copied next to the output, as appropriate.

### 2.3 Renderer contract

```python
class Renderer(Protocol):
    name: str
    capabilities: set[Capability]     # NATIVE_MATH, NESTING, CALLOUTS, TABLES, IMAGES...

    def render(self, week: NoteWeek, opts: RenderOptions) -> RenderResult
```

`RenderResult` is bytes-or-structure plus a manifest of assets needing resolution.
Delivery is a separate `Emitter` (write to disk, POST to an API), so rendering is
testable with no credentials and no network.

**Degradation is declared, not improvised.** A shared `degrade()` helper rewrites the
IR against a renderer's capability set before rendering: no `NATIVE_MATH` turns
`Equation` into a fenced code block; no `NESTING` flattens nested lists into a heading
plus a flat list. Each renderer therefore handles a guaranteed-supported subset, and
degradation behaviour is tested once rather than per renderer.

**Target limits live in the renderer.** Notion's 2,000-char rich-text cap, 100-element
children arrays, 2-level nesting, 1,000-block payloads; Anki's field escaping; LaTeX's
special characters. All renderer-local. None of it appears in the IR or upstream.

---

## 3. Pipeline stages

| # | Stage | In | Out | Pure? | Notes |
|---|---|---|---|---|---|
| 1 | Ingest captions | `.vtt` / `.srt` | `[Segment]` | yes | Rolling-caption dedupe lives here |
| 2 | Ingest slides | `.pptx` / `.pdf` | `Deck` | yes | Text, speaker notes, rendered images |
| 3 | Ingest video | `.mp4` | `[SceneChange]`, frames | no | Optional, per-lecture opt-in |
| 4 | Align | `Deck` + `[Segment]` | `[Chunk]` | yes | Monotonic; see §4 |
| 5 | Generate | `[Chunk]` | `NoteLecture` | no | LLM, chunk pass + synthesis pass |
| 6 | Verify | `NoteLecture` + sources | annotations | no | Optional; flags unsupported claims |
| 7 | Render | `NoteWeek` | `RenderResult` | yes | Pluggable |
| 8 | Emit | `RenderResult` | side effects | no | Pluggable |

Stages 1, 2, 4, 7 being pure functions is deliberate — they hold most of the fiddly
logic and all of it is unit-testable without network, credentials, or fixtures larger
than a few kilobytes.

---

## 4. The two stages that carry the project

Most of this pipeline is plumbing. Two stages decide whether the output is good.

### 4.1 Alignment (stage 4)

Mapping slides to the speech that accompanied them. Everything downstream improves if
this is right: chunk boundaries land on topic boundaries, timestamps are accurate, and
you can detect stretches where the lecturer went off-slide.

Approaches, in order of effort:

1. **Concatenate.** Slides and transcript passed together, no mapping. Works, but
   timestamps become per-lecture rather than per-topic.
2. **Text matching.** Score slide vocabulary against transcript segments, weighting
   rare terms — a slide titled "Bellman Equation" is pinned by "bellman", not
   "equation". Critically, solve for *monotonic* boundaries rather than matching each
   slide independently; slides advance in order, and using that constraint fixes the
   slides whose text is too generic to place on their own.
3. **Scene detection.** Frame-difference the video for slide transitions. Gives exact
   boundaries but doesn't know which slide is which — so combine: text matching for
   identity, scene changes for boundaries.

Build (2) first. Add (3) only for lectures where (1) or (2) visibly fails.

Alignment also produces the **gap signal**: spans where the lecturer talked for
minutes with no matching slide content. That's board work or live coding, and it's the
only reliable trigger for pulling video frames.

### 4.2 Generation (stage 5)

Per-chunk generation, then a lecture-level synthesis pass.

**Chunk for quality, not for context.** A week is roughly 45k tokens of speech and fits
in context comfortably. Chunking isn't a workaround — asked to summarise three hours at
once, the model produces uniformly shallow output; asked about one slide and its two
minutes of explanation, it produces notes with real detail because it has room to.

Two schema fields do disproportionate work:

- **`Callout(EXAM)` / emphasis.** Lecturers signal importance verbally — "this will be
  on the exam", "the classic mistake here". None of it is on the slides, and it's the
  highest-value content in the transcript. The prompt must protect it from being
  summarised away.
- **`Callout(UNCERTAIN)`.** Somewhere to put garbled audio other than a confident
  guess. Hallucinated smoothing over bad transcription is this pipeline's main failure
  mode, and giving the model a legitimate place to express doubt largely fixes it.

---

## 5. Repo layout

```
lecturenotes/
  model/          NoteWeek, Topic, Node types, capabilities, degrade()
  ingest/         captions.py  slides.py  video.py
  align/          scoring.py   boundaries.py
  generate/       prompts.py   client.py   cache.py
  render/         base.py  markdown.py  anki.py  notion.py  html.py
  emit/           filesystem.py  notion_api.py
  cli.py
tests/
  fixtures/       tiny .vtt, 3-page .pdf, expected outputs
  contract/       tests every renderer must pass
```

`model/` imports nothing else in the package. `render/` never imports `ingest/`.
Enforce it with an import-linter rule so the boundary doesn't erode.

---

## 6. Build phases

Each phase is a session's worth of work with a defined "done". Vertical slices, so
there's something runnable early.

| Phase | Deliverable | Done when |
|---|---|---|
| **0** | Repo skeleton, `model/` types, fixtures | Types instantiate; fixtures committed |
| **1** | Caption ingest | Rolling-caption fixture dedupes; tags stripped; segments merge on sentence boundaries |
| **2** | Slide ingest | `.pptx` and `.pdf` both yield titles + bullets + speaker notes; multi-column PDF reads in order |
| **3** | Markdown renderer + filesystem emitter | Hand-written `NoteWeek` fixture renders to a readable file |
| **4** | Alignment | Fixture deck maps to correct spans in order; gaps flagged |
| **5** | Generation (chunk + synthesis) | `build --dry-run` shows chunking; real run produces valid `NoteWeek` |
| **6** | **Anki renderer** | Same `NoteWeek` produces a deck. *Any IR flaw surfaces here.* |
| **7** | Notion renderer + emitter | Limits enforced; contract tests pass |
| **8** | Verification pass | Flags claims unsupported by the transcript |
| **9** | Video (scene detect, frame sampling) | Opt-in per lecture; sharpens boundaries |

Phase 3 before phase 5 is deliberate: a renderer and a hand-written fixture let you
see the shape of the output before spending a token, and you'll revise the IR when you
do.

Phase 6 is the real checkpoint. Anki is not a document — it's atomic cards with no
hierarchy — so it exercises the IR in a direction no document renderer will. Discover
the model's flaws there, before Notion, not after.

---

## 7. Cross-cutting concerns

### 7.1 Caching

Cache LLM responses keyed by `hash(chunk_content + prompt_version + model)`. You will
regenerate many times while tuning renderers and prompts, and without this each
iteration costs a full week of tokens. Bump `prompt_version` to invalidate
deliberately.

### 7.2 Stable IDs

Topic ids must survive regeneration so that re-emitting **updates** rather than
duplicates. Derive them from source coordinates — `lecture_id + slide_range` — not from
position in the list or a slug of the heading, both of which move when you change a
prompt.

### 7.3 Multiple lectures per week

The **lecture** is the unit of generation; the **week** is a container. Renderers
decide whether that becomes one page or several. Don't merge lectures before
generation — recap slides across lectures will produce duplicated notes, and
cross-lecture dedup belongs in the week-level synthesis.

### 7.4 File pairing

Multiple files of each type per week means captions must be matched to their deck and
video. Match by sorted filename, then **print the pairing and make the user confirm
it**. Course naming conventions vary too much for reliable inference, and a wrong
pairing yields confident notes about the wrong lecture — the worst failure mode
because the output looks fine.

---

## 8. Testing

- **Fixtures small and committed.** A 20-cue `.vtt` with deliberate rolling-caption
  repetition and inline timing tags; a 3-page PDF deck with one multi-column slide.
  Kilobytes, not megabytes.
- **Contract tests, parametrised over every renderer**: renders without raising;
  respects declared capabilities; output is deterministic; every `SourceAnchor`
  survives into the output in some form.
- **Snapshot tests** on the markdown renderer. Cheapest possible regression detection
  for IR changes.
- **The LLM client sits behind an interface** with a recorded-response fake. No test
  touches the network.
- **A `--dry-run` that stops before generation** and prints the chunking. This is the
  main debugging tool, since bad notes are almost always bad chunks.

---

## 9. Open decisions

Worth settling before phase 5, none blocking phase 0–4.

1. **Note density.** One topic per slide, or per group of related slides? Affects
   chunk merging. Suggest starting at ~120 words of speech minimum per chunk and
   tuning after seeing real output.
2. **Prose vs bullets.** Bullets are skimmable; prose retains reasoning. Suggest prose
   summary plus bullet key-points, and let the renderer drop one if desired.
3. **Verification.** Worth the extra pass, or is `UNCERTAIN` sufficient? Defer to
   phase 8 and decide with real output in hand.
4. **Multi-week features** — a running course glossary, cross-week links. Defer
   entirely; it changes the storage model and shouldn't influence v1.

---

## 10. Working with Claude Code

- Put §2.2 (the IR) and §7.2 (stable IDs) in `CLAUDE.md` verbatim. They're the
  invariants everything else depends on, and they're the things most likely to get
  quietly violated in a later phase.
- Also record the two boundary rules: `model/` imports nothing internal, `render/`
  never imports `ingest/`.
- Take one phase per session. The phase table gives explicit done-criteria; ask for
  those as tests first, particularly for phase 1, where the caption-dedupe edge cases
  are the whole difficulty.
- Phases 1, 2, 4 are pure functions — ask for property-based tests (alignment output
  must be monotonic and must partition the segments, for any input).
- When phase 6 forces an IR change, change `model/` and let the type checker find the
  breakage rather than patching renderers individually.
