# P5-01 — `generate/client.py` + `generate/cache.py`: LLM client seam, recorded fake, response cache
Phase 5 · Depends on: P4-04 · Size: M

## Goal

Create the infrastructure everything else in Phase 5 stands on: the plan §8 client
interface ("The LLM client sits behind an interface with a recorded-response fake. No
test touches the network.") and the plan §7.1 response cache ("Cache LLM responses
keyed by `hash(chunk_content + prompt_version + model)` ... without this each
iteration costs a full week of tokens"). After this ticket, `lecturenotes/generate/`
has a `LLMClient` protocol with three implementations — the real Anthropic client, the
recorded fake tests use, and a caching wrapper that composes over either — and
`anthropic` is a runtime dependency. No prompts, no schemas, no `Topic`s yet: the
callers arrive in P5-02/P5-03.

## Scope

**In**
- `lecturenotes/generate/client.py`: `DEFAULT_MODEL`, `GenRequest`, `LLMClient`,
  `AnthropicClient`, `RecordedClient`.
- `lecturenotes/generate/cache.py`: `response_key`, `CachedClient`.
- `anthropic>=1` added to `[project] dependencies` in `pyproject.toml`; `uv sync`.
- `tests/generate/` package (`__init__.py`), `tests/generate/test_client.py`,
  `tests/generate/test_cache.py`, `tests/generate/test_cache_properties.py`.

**Out**
- Prompt construction, response schemas, `PROMPT_VERSION` → P5-02. Topic/lecture
  assembly → P5-02/P5-03. CLI wiring, cache-dir choice, `ANTHROPIC_API_KEY` UX → P5-04.
- Response *recording* tooling (a capture mode on `AnthropicClient`) — the fixture is
  hand-written like every other expected fixture (P0-03 standing rule), so nothing
  records.
- Streaming, retries beyond the SDK's built-in ones, token accounting — see Decisions.

## Tasks

1. **Tests first** (red on `ImportError`).
   - `tests/generate/test_client.py`:
     - `GenRequest(key="chunk:lec01:s2-2", prompt="p")` is frozen and rejects extra
       fields (the house pydantic config).
     - `RecordedClient` over a tmp JSON file `{"chunk:lec01:s2-2": "{\"x\": 1}"}`
       returns exactly that string for that key; an unknown key raises `KeyError`
       whose message contains both the key and the file path (a miss must name what
       to add to the fixture, not fail mysteriously downstream).
     - `RecordedClient.model == "recorded"` and the protocol is satisfied:
       `isinstance`-free structural check via a `def use(c: LLMClient) -> None` typed
       helper (mypy is the arbiter).
     - Importing `lecturenotes.generate.client` and constructing
       `AnthropicClient()` performs no SDK construction and needs no API key
       (monkeypatch `anthropic.Anthropic` to raise; only `complete` may touch it).
     - With `anthropic.Anthropic` monkeypatched to a stub returning a canned message
       (one text block), `AnthropicClient(model="claude-opus-5").complete(req)`
       returns the block's text, and the stub saw `model="claude-opus-5"`,
       `messages=[{"role": "user", "content": req.prompt}]`, and a `max_tokens` of
       16000. A canned response with `stop_reason == "max_tokens"` raises
       `ValueError` naming the key (truncated JSON must never reach a validator).
   - `tests/generate/test_cache.py`:
     - `CachedClient(inner, cache_dir=tmp_path / "c", prompt_version="1")` over a
       counting stub: first `complete` calls inner once and writes one file under the
       cache dir; a second identical call returns the same text with the inner count
       still 1; a different prompt calls inner again. The cache dir is created on
       demand.
     - `CachedClient.model == inner.model` (the wrapper is transparent to callers
       that stamp the model into keys or logs).
   - `tests/generate/test_cache_properties.py` (hypothesis, over text strategies):
     - `response_key` is deterministic, 64 lowercase hex chars, and changes when any
       one of `prompt_version`, `model`, `prompt` changes while the others are held
       (draw two distinct values for the varied component).
     - No collision by concatenation: `response_key("a", "bc", p)` differs from
       `response_key("ab", "c", p)` — pinned because the key must be a hash of the
       *triple*, not of a joined string.
     - Cache round-trip: for any response text the stub returns (including empty and
       non-ASCII), the second call returns it unchanged.
2. **`pyproject.toml`**: add `anthropic>=1` to `[project] dependencies` (the 1.x SDK;
   it rides on `httpx2`). `uv sync --all-groups`. No import-linter change: the four
   contracts already list `lecturenotes.generate` on the correct sides.
3. **`client.py`**:
   - `DEFAULT_MODEL = "claude-opus-5"` (the settled §9-adjacent decision; `--model`
     overrides in P5-04, and the model id is part of every cache key).
   - `GenRequest`: frozen pydantic model, `extra="forbid"` — `key: str` (a
     human-readable request id like `chunk:lec01:s2-2` / `synthesis:lec01`; P5-02
     defines the naming), `prompt: str`.
   - `LLMClient` Protocol: `model: str` and
     `def complete(self, request: GenRequest) -> str`. The return value is the raw
     response text (JSON the caller validates) — validation lives at the call site so
     the fake and the cache stay plain strings on disk.
   - `AnthropicClient(model: str = DEFAULT_MODEL)`: constructs the SDK client
     **lazily on first `complete`** (importing `generate/` or running `--dry-run`
     must never require a key); sends one user message with `max_tokens=16000`;
     returns the concatenated `text` blocks; raises `ValueError` (naming
     `request.key`) if `stop_reason == "max_tokens"`. Nothing else — the SDK already
     retries 429/5xx.
   - `RecordedClient(path: Path)`: loads a JSON object mapping request key →
     response text once; `complete` returns `mapping[request.key]`, `KeyError`
     naming key and path on a miss; `model = "recorded"`.
4. **`cache.py`**:
   - `response_key(prompt_version: str, model: str, prompt: str) -> str`: sha256 hex
     of the UTF-8 canonical JSON of the *list* `[prompt_version, model, prompt]` —
     §7.1's key, delimiter-collision-free (chunk content is in the prompt).
   - `CachedClient(inner: LLMClient, cache_dir: Path, prompt_version: str)`:
     `model = inner.model`; `complete` reads/writes
     `cache_dir / f"{response_key(...)}.txt"` (UTF-8), calling `inner.complete` only
     on a miss and creating the directory on demand.
5. Run the full check suite; commit tests first, then the implementation.

## Acceptance criteria

- `uv run pytest` → all green, hypothesis included; `uv run ruff check .`,
  `uv run mypy`, `uv run lint-imports` clean (still 4 contracts, 0 broken).
- `uv run python -c "from lecturenotes.generate.cache import response_key; ks = {response_key(*t) for t in [('1','m','p'),('2','m','p'),('1','n','p'),('1','m','q')]}; print(len(ks))"`
  prints `4`.
- `uv run python -c "import anthropic, lecturenotes.generate.client as c; print(c.DEFAULT_MODEL)"`
  prints `claude-opus-5` with no API key in the environment.
- `git log` shows the tests committed before (or together with, never after) the
  implementation; `git status` clean.

## Decisions & notes

- **The fake is keyed by `request.key`, never by prompt hash.** The recorded-response
  fixture (P5-02) is hand-written, and prompt text will be tuned constantly (§7.1
  exists because of that). Hash-keying would break every recorded fixture on every
  prompt edit; key-keying survives tuning, and a miss fails loudly with the missing
  key's name. The *cache*, by contrast, hashes the full triple on purpose — a tuned
  prompt must re-generate.
- **`complete` returns raw text; callers validate.** Response pydantic models live in
  `prompts.py` (P5-02) next to the prompts that promise them. The seam stays one
  string in, one string out, so the fake is a dict lookup and the cache is a file.
  Structured outputs (`output_config.format`) are a drop-in upgrade *inside*
  `AnthropicClient` if a real run ever returns unparseable JSON — the interface hides
  it.
- **`model` is on the protocol.** The cache key needs the model id (§7.1) and the
  wrapper must not guess it; reading `inner.model` keeps one source of truth and lets
  P5-04 print what a run will cost against which model.
- **Lazy SDK construction.** `--dry-run` (P5-04) and every test import this module;
  none of them may demand `ANTHROPIC_API_KEY`. Only a real `complete` does.
- **No streaming, no custom retries.** Chunk responses are a few KB of JSON —
  `max_tokens=16000` non-streaming is comfortable, and the SDK retries transient
  failures itself. The `max_tokens` truncation check turns silent JSON corruption
  into a named error; revisit streaming only if a real lecture chunk actually hits it.
- **`RecordedClient.model == "recorded"`.** It participates in cache keys harmlessly
  if someone composes fake+cache in a test, and it makes accidental use of the fake in
  a real run self-announcing.
