# P6-01 — Card coverage, prompt pin, hand-written expected deck
Phase 6 · Depends on: P5-04 · Size: L

## Goal

The IR checkpoint itself (plan §6: *any IR flaw surfaces here*), taken before a line
of renderer code exists. Phase 6's deck is atomic cards, and two flaws surface
immediately: `week01`'s `value_iteration` (lec01) and `policy_iteration` (lec02)
topics have **no cards**, so a cards-only deck drops their anchors and fails contract
property 4 ("every `SourceAnchor` survives"); and `CardSeed` has **no stable
identity**, so Anki re-import would duplicate instead of update (§7.2). This ticket
resolves both at the fixture/prompt level — every topic gets ≥ 1 card, generation is
pinned to that guarantee, and the guid derivation is decided here (implemented in
P6-02) — then hand-writes the expected deck `tests/fixtures/notes/week01.anki.txt`,
the format spec and render-side twin of `week01.md`. The fixture docstring predicted
this ticket: "Phase 3 renders it, Phase 6 breaks it."

## Scope

**In**
- Cards for the two card-less topics in `tests/fixtures/notes/week01.py`;
  `week01.json` regenerated deliberately.
- The P5 fixture ripple: `tests/fixtures/generate/lecture01.notes.json` and
  `lecture01.responses.json` gain the same `value_iteration` card.
- Chunk-prompt instruction "at least one card per topic", pinned by a test;
  `PROMPT_VERSION` bump.
- `tests/fixtures/notes/week01.anki.txt`, hand-written.
- `tests/fixtures/README.md` and `tests/fixtures/notes/test_week01.py` updates.

**Out
- `render/anki.py` and every line of renderer code → P6-02 (this ticket's fixture is
  its spec; the guid/math/quoting *rules* are recorded here, implemented there).
- The `--format` flag and done-gate → P6-03.
- Glossary `Definition`s as cards — see Decisions.
- Regenerating with a real API key — the recorded fake stays the source of truth;
  the fixtures are edited by hand, consistently.

## Tasks

1. **Hand-write the two missing cards in `tests/fixtures/notes/week01.py`**,
   transcribed from the topic bodies (never invented). Exact content — the three
   fixtures below must agree with it verbatim:
   - `value_iteration` (lec01):
     - front: `When does value iteration stop, and what do you read off afterwards?`
     - back: `When the biggest per-sweep change falls below the tolerance epsilon;
       then pick the best action in every state to get the greedy policy.` (one
       line; transcribed from the topic's closing prose)
     - tags: `["value-iteration"]`
   - `policy_iteration` (lec02):
     - front: `What are the two alternating steps of policy iteration?`
     - back: `Evaluate the current policy exactly, then improve it greedily; stop
       when the policy stops changing.` (one line; transcribed from the topic's
       opening prose and table)
     - tags: `["policy-iteration"]`
   Regenerate the snapshot deliberately:
   `uv run python -m tests.fixtures.notes.week01 --write` — the diff touches only
   `cards` arrays.
2. **Ripple the P5 fixtures by hand** (lec02 is never generated, so only the lec01
   half moves):
   - `tests/fixtures/generate/lecture01.notes.json`: the `value_iteration` topic's
     `"cards": []` gains the card above.
   - `tests/fixtures/generate/lecture01.responses.json`: the `chunk:` response for
     the slide-3 topic gains the same card in its `ChunkNotes` JSON.
   - `tests/fixtures/notes/week01.md` is **not** touched — cards are invisible to
     the markdown renderer (P3-02 decision), and the untouched byte-equality test
     proves the doctrine held.
3. **Pin the guarantee in the prompt** (`lecturenotes/generate/prompts.py`): the
   chunk prompt instructs the model to produce **at least one card per topic**,
   pinned by a substring test in `tests/generate/test_prompts.py` exactly the way
   the EXAM-verbatim and UNCERTAIN instructions are (P5-02). Bump `PROMPT_VERSION`
   — a deliberate §7.1 cache invalidation; the recorded fake is keyed by
   `request.key`, not prompt hash, so no other generate test moves.
4. **Tighten the fixture sanity test**: `test_cards_glossary_open_questions` in
   `tests/fixtures/notes/test_week01.py` currently asserts ≥ 2 topics with cards;
   change it to assert **every** topic has ≥ 1 card — the new invariant, enforced
   where the fixture lives.
5. **Hand-write `tests/fixtures/notes/week01.anki.txt`** — before any renderer code,
   transcribed from `week01.py`, never generated. LF endings, single trailing
   newline. The full spec:
   - Six header lines, in order: `#separator:tab`, `#html:false`,
     `#notetype:Basic`, `#deck:CS-RL-101::Week 1` (`{course}::Week {week_number}` —
     `::` makes it a subdeck of the course), `#guid column:1`, `#tags column:4`.
   - One data row per `CardSeed`, lectures in week order, topics in lecture order,
     cards in topic order → **8 rows**. Four tab-separated columns:
     1. **guid**: 16 hex of `sha256(topic_id + "\n" + front)` over the UTF-8 of the
        **raw IR front** (before math translation) — mirrors the `img-` 16-hex
        convention; compute each with
        `python -c "import hashlib; print(hashlib.sha256('<id>\n<front>'.encode()).hexdigest()[:16])"`.
     2. **front**, math-translated.
     3. **back**, math-translated, with the citation appended after one space:
        `[{lecture.id} · {format_clock(anchor.start_s)}]`, extended with
        ` · slide N` / ` · slides N–M` when `anchor.slides` is set (en-dash, same
        style as the markdown anchor line). The eight citations:
        `[lec01 · 0:01 · slide 1]` ×2, `[lec01 · 2:31]` (the slide-less board-work
        topic), `[lec01 · 4:31 · slide 2]` ×2, `[lec01 · 7:01 · slide 3]`,
        `[lec02 · 0:00 · slide 1]`, `[lec02 · 3:00 · slides 2–3]`.
     4. **tags**, space-joined (`mdp discounting` for the two-tag card; never
        empty in this fixture).
   - **Math translation**: every paired `$…$` in a front or back becomes `\(…\)` —
     the Bellman card's back is one `\(V(s) = …\)` block plus its citation. No
     field in this fixture needs TSV quoting (no tabs, newlines or `"`), so the
     quoting rule is exercised only by P6-02's ad-hoc tests.
6. **`tests/fixtures/README.md`**: add `notes/week01.anki.txt` — "the week's cards
   as one Anki notes-in-plain-text file, hand-written (P6-01)" — with the standard
   "never regenerated from the code under test" sentence.
7. Run the full check suite; commit (fixture edits and prompt pin can land as one
   commit — nothing here has an implementation half to sequence against, but the
   `.anki.txt` must exist before P6-02 begins).

## Acceptance criteria

- `uv run pytest`, `uv run ruff check .`, `uv run mypy`, `uv run lint-imports` all
  green — including the untouched `tests/render/test_markdown.py` byte-equality
  test and the untouched P5 request-count tests.
- `git diff` for `week01.json`, `lecture01.notes.json` and
  `lecture01.responses.json` touches only card content (plus the
  `PROMPT_VERSION` line in `prompts.py`).
- `uv run python -c "from tests.fixtures.notes.week01 import week01; assert all(t.cards for lec in week01().lectures for t in lec.topics); print('ok')"`
  prints `ok`.
- `grep -c $'\t' tests/fixtures/notes/week01.anki.txt` prints `8`;
  `grep -c '^#' tests/fixtures/notes/week01.anki.txt` prints `6`.
- `grep -c '7:01' tests/fixtures/notes/week01.anki.txt` prints `1` and
  `grep -c '3:00' tests/fixtures/notes/week01.anki.txt` prints `1` — the two
  previously card-less topics' anchors now survive into the deck.
- `grep -c 'at least one card' tests/generate/test_prompts.py` prints ≥ 1 (the
  prompt-pin test), and that test passes.
- `git status` clean.

## Decisions & notes

- **Every topic carries ≥ 1 card — an IR-usage invariant, not a model change.** The
  alternatives were rejected deliberately: relaxing contract property 4 would
  permanently weaken the plan §8 contract for every future renderer, and letting
  the renderer synthesize fallback cards would have a renderer inventing content
  the generator never wrote. The guarantee lives in generation (the prompt pin) and
  in the fixture sanity test; the `model/` types still permit card-less topics, and
  the P6-02 renderer simply emits nothing for one.
- **The deck is `CardSeed`s only; glossary `Definition`s stay out.** Glossary
  entries are lecture metadata with no anchor — a term card could not cite its
  source, and §2.2 is explicit that cards are the Anki target's input. Revisit only
  if real decks feel thin.
- **One deck per week, named `{course}::Week {n}`**, lecture identity carried in
  each card's citation — this settles §7.3 for the Anki renderer the way "one week
  page" settled it for markdown. Anki's `::` gives the course a deck tree for free.
- **guid = 16 hex of sha256(topic_id + "\n" + front), raw IR front.** Derived from
  the §7.2 source coordinate (the topic id) plus content, never from list position.
  The honest trade-off, chosen with eyes open: a reworded front is a *new* card —
  the old one goes stale in Anki rather than a card with review history silently
  mutating under the student. Position-based guids were rejected as exactly the
  §7.2 anti-pattern ("position moves when you change a prompt"); an explicit id
  field on `CardSeed` was rejected because generation has no stabler coordinate to
  mint it from — it would move the same problem upstream and ripple every P5
  fixture for no gain. Hashing the raw front keeps guids independent of renderer
  formatting decisions.
- **Anki's notes-in-plain-text TSV, not genanki/.apkg.** Pure text fits
  `RenderedDocument.text: str`, the pure-renderer contract, byte-for-byte
  determinism and the hand-written-fixture doctrine exactly; a binary `.apkg`
  breaks all four and adds a runtime dependency. `#html:false` means `<` and `&`
  need no escaping and MathJax still processes `\(…\)` at review time.
- **Paired `$…$` → `\(…\)` is delimiter translation, not re-parsing** — the §2.3
  renderer-local exception to the "inline `$` is plain text" doctrine, confined to
  card fields, because Anki's MathJax does not recognise `$` delimiters and the
  flagship Bellman exam card would otherwise be unreadable at review time. §2.2's
  promise ("every plausible target consumes LaTeX natively or near-natively") is
  kept by speaking Anki's dialect. Unpaired `$` passes through untouched.
- **The expected deck is hand-written and never regenerated from the code under
  test** — same doctrine as `week01.md`, `segments.json`, `deck.json`,
  `chunks.json` and `notes.json`. It is the format spec; P6-02's renderer is
  written to it.
- **`PROMPT_VERSION` is bumped even though no recorded fixture breaks** — the P5-01
  key doctrine working as designed: fakes key on `request.key`, caches on
  `prompt_version + model + prompt`, so a real cached week regenerates on purpose
  and the committed fixtures don't move.
