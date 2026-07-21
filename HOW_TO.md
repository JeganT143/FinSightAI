# HOW_TO — Rebuilding FinSightAI Yourself

> This is a **build log you can execute from**: the exact order files were
> created, and for every function or class in them — what it takes in, what
> it returns, and what it wires into. Not full implementations (read the real
> file for that — the `claude-help` branch has it), and not abstract theory
> either (that's [ARCHITECTURE.md](ARCHITECTURE.md), read separately). This
> is the sequence and the interfaces, so you can type it yourself in the same
> order and know exactly how each piece is supposed to connect to the last
> one before you write it.
>
> Work through the phases **in order** — each one assumes the previous ones
> exist and compile/run. Every phase ends with a **Verify it** step: run that
> before moving on. If it doesn't pass, don't proceed — the next phase
> imports or calls things this one is supposed to produce.

---

## Phase 0 — Read the starting point before changing anything

No files created this phase. Read every existing file in the repo (agents,
tools, pipeline, the one Alembic migration, the Streamlit demo) and write
down three lists: what works, what's structurally wrong, what's not started.
This is the input to Phase 1's decisions — you can't write an ADR about what
to change without first knowing exactly what's there.

**Verify it.** You can describe what every existing file does, in one
sentence each, without re-opening it.

---

## Phase 1 — Write ARCHITECTURE.md before touching code

**File:** `ARCHITECTURE.md` (created, not code — this phase produces the
decision record everything downstream implements).

For each major decision, one ADR: **Decision** (one paragraph, concrete) →
**Why** → **Alternatives rejected** (named, with the specific reason each
loses) → **Trade-off accepted**. The decisions that had to be made before any
code, in the order they gate later phases:

1. Orchestration shape (deterministic graph, not a framework) — gates Phase 8.
2. Agent runtime (OpenAI Agents SDK) — gates Phase 7.
3. Inter-agent contracts (typed schemas, not free text) — gates Phase 3,
   which everything else depends on.
4. Model routing (cheap specialists / strong synthesis) — gates Phase 4.
5. Grounding strategy (RAG, pgvector specifically) — gates Phase 6.
6. The quality gate (bounded critic loop) — gates Phase 8.
7. Transport (SSE) — gates Phase 10.
8. Observability (first-party trace tables) — gates Phase 9.
9. Evaluation (two-tier, golden fixtures) — gates Phase 11.
10. Frontend stack (Next.js, design-doc-first) — gates Phase 14–15.
11. Packaging (Docker Compose + GitHub Actions, not K8s) — gates Phase 13.

**Verify it.** Every ADR's "alternatives rejected" names a *specific* reason
the alternative loses for *this* project — not a generic "it's worse."

---

## Phase 2 — Environment

No application code. Three artifacts:

1. `pyproject.toml` + `uv.lock` — direct dependencies in the former, exact
   resolved versions in the latter (commit both).
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   uv sync
   ```
2. `docker-compose.yml` — a `db` service on `pgvector/pgvector:pg17`.
   ```bash
   docker compose up -d db
   docker exec finsight-db psql -U finsight -d finsight -c "CREATE EXTENSION IF NOT EXISTS vector;"
   ```
3. `.env` (gitignored, real secrets) + `.env.example` (committed template) —
   `OPENAI_API_KEY`, `DATABASE_URL`.

**Verify it.** `uv run python -c "import agents, pgvector, fastapi"` succeeds.
`SELECT extname FROM pg_extension WHERE extname='vector';` returns one row.

---

## Phase 3 — Typed contracts

**File:** `backend/schemas/agents.py` — write these in this exact order,
since each later one references an earlier one:

1. `Citation(BaseModel)`
   - Fields: `source: str`, `quote: str`
   - `strip_control_chars(cls, v: str) -> str` (field validator on both fields)
     — **in:** the raw field value as the SDK parsed it — **out:** the same
     string with control characters stripped — **why it exists:** models
     occasionally garble em-dashes into control bytes; without this, citation
     chips render broken glyphs in the UI.
   - **Connects to:** used as the type of the `citations` field on
     `FundamentalsOutput`, `RiskOutput`, and `ReportDraft` (below).

2. `SpecialistOutput(BaseModel)` — the shared base every specialist extends.
   - Fields: `score: float` (`ge=0, le=10`), `confidence: Literal["low","medium","high"]`,
     `summary: str`, `bullets: list[str]`, `data_warnings: list[str]`.
   - No behavior — a pure data contract.

3. `FundamentalsOutput(SpecialistOutput)` — adds `citations: list[Citation]`.
   **Connects to:** passed as `output_type=` to `fundamentals_agent` (Phase 7).

4. `RiskOutput(SpecialistOutput)` — adds `citations: list[Citation]`.
   **Connects to:** `output_type=` for `risk_agent` (Phase 7). Score
   direction is inverted by convention (10 = safest) — enforced in the
   agent's *instructions* (Phase 7), not in this schema; the schema just
   carries the number.

5. `TechnicalsOutput(SpecialistOutput)` / `SentimentOutput(SpecialistOutput)`
   — no extra fields. **Connects to:** `output_type=` for `technicals_agent`
   / `sentiment_agent`.

6. `PillarSummary(BaseModel)` — fields: `pillar: Pillar`, `score: float`,
   `summary: str`. **Connects to:** used as the type of `ReportDraft.pillars`.

7. `ReportDraft(BaseModel)`
   - Fields: `ticker: str`, `verdict: Verdict`, `overall_score: float`,
     `pillars: list[PillarSummary]`, `thesis: str`, `key_risks: list[str]`,
     `catalysts: list[str]`, `citations: list[Citation]`,
     `narrative_markdown: str`.
   - **Connects to:** `output_type=` for `synthesizer_agent` (Phase 7). The
     model *fills* `overall_score`, but the pipeline (Phase 8) **overwrites
     it** with `compute_overall_score()`'s return value before persisting —
     write that override explicitly; don't trust the model's arithmetic.

8. `Challenge(BaseModel)` — fields: `claim: str`, `reason: str`,
   `severity: Literal["low","medium","high"]`, `pillar: Pillar | None`.
   **Connects to:** type of `CriticOutput.challenges`.

9. `CriticOutput(BaseModel)` — fields: `challenges: list[Challenge]`,
   `blocks_publication: bool`, `overall_assessment: str`.
   **Connects to:** `output_type=` for `critic_agent` (Phase 7).
   `blocks_publication` is read directly by the `while` loop's `if` in
   `pipeline/research.py` (Phase 8) — this one field is the entire branch
   point of the orchestrator.

10. `compute_overall_score(fundamentals: SpecialistOutput, risk: SpecialistOutput, sentiment: SpecialistOutput, technicals: SpecialistOutput) -> float`
    — **in:** the four already-parsed specialist outputs — **out:** `round(
    fundamentals.score*0.35 + risk.score*0.30 + sentiment.score*0.20 +
    technicals.score*0.15, 1)` — **connects to:** called exactly once per
    pipeline run, in `pipeline/research.py`, immediately after the
    `asyncio.gather()` fan-out returns (Phase 8).

11. `verdict_band(overall_score: float) -> list[str]` — **in:** a score —
    **out:** the list of verdict strings consistent with that score (e.g.
    `>=8.0` → `["STRONG_BUY","BUY"]`) — **connects to:** *not* called at
    runtime by the pipeline; called by `evals/test_deterministic.py` (Phase
    11) to assert the synthesizer's verdict matches its own score.

**Verify it.** Construct each schema by hand with made-up data and call
`.model_dump_json()` on it — if that's awkward, the schema is awkward for an
LLM to fill in too; fix it now, before any agent depends on it.

---

## Phase 4 — Config & model routing

**File:** `backend/core/config.py`

1. `Settings(BaseSettings)` — fields, with defaults where the value is a
   policy choice rather than a secret: `openai_api_key: str` (required, no
   default), `database_url: str` (required), `specialist_model: str =
   "gpt-4o-mini"`, `synthesizer_model: str = "gpt-4o"`, `critic_model: str =
   "gpt-4o"`, `embedding_model: str = "text-embedding-3-small"`,
   `embedding_dimensions: int = 1536`, `max_revisions: int = 2`,
   `max_cost_usd: float = 0.50`, `sec_user_agent: str`, `rag_top_k: int = 5`,
   `chunk_size_tokens: int = 800`, `chunk_overlap_tokens: int = 100`,
   `cors_origins: list[str]`.
   - **Connects to:** instantiated once as module-level `settings = Settings()`
     at the bottom of the file; every other module that needs a model name or
     a limit does `from backend.core.config import settings` and reads a
     field — never hardcode a model string anywhere else.

2. `MODEL_PRICING_PER_1M: dict[str, tuple[float, float]]` — a plain lookup
   table, `{model_name: (input_price_per_1M, output_price_per_1M)}`. Not a
   function; just data `estimate_cost_usd` reads.

3. `estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float`
   — **in:** a model name string + token counts — **out:** USD, computed
   from the table above (unknown models return `0.0` rather than raising) —
   **connects to:** called from `traced_run()` in `pipeline/tracing.py`
   (Phase 8) for every agent call, and from `embed_texts()` in
   `rag/embeddings.py` (Phase 6) for embedding cost.

**Verify it.** `estimate_cost_usd("gpt-4o-mini", 1000, 200)` returns a
plausible fraction-of-a-cent number by hand-checking against the table.

---

## Phase 5 — Market data tools

**File:** `backend/tools/market.py` — private helpers first, public
`@function_tool`s after, since each public tool calls the private ones:

1. `_fetch_info(ticker: str) -> dict[str, Any]` (private, **sync**) — **in:**
   ticker — **out:** the raw `yfinance.Ticker(ticker).info` dict —
   **connects to:** called via `asyncio.to_thread(_fetch_info, ticker)`
   inside every public tool below, so the blocking yfinance call doesn't
   block the event loop while four specialists run concurrently.

2. `_null_warnings(data: dict, skip=("ticker",)) -> list[str]` (private) —
   **in:** a dict of already-fetched fields — **out:** the list of keys whose
   value is `None` (excluding `skip`) — **connects to:** called at the end
   of every public tool to populate its `data_warnings` key.

3. `get_fundamentals(ticker: str) -> dict` (`@function_tool`, async) —
   **in:** ticker (supplied by the calling agent) — **out:** dict with
   `current_price`, `pe_ratio`, `revenue_growth`, `profit_margins`, … plus
   `data_warnings` — **connects to:** registered in `fundamentals_agent.tools`
   (Phase 7).

4. `get_risk_metrics(ticker: str) -> dict` — same shape, different fields
   (`beta`, `debt_to_equity`, `52_week_high/low`, `short_ratio`, …).
   **Connects to:** `risk_agent.tools`.

5. `get_analyst_sentiment(ticker: str) -> dict` — fields: recommendation,
   target prices, ownership. **Connects to:** `sentiment_agent.tools`.

6. `_fetch_news(ticker: str, limit: int) -> list[dict]` (private, sync) +
   `get_recent_news(ticker: str) -> dict` (public tool, wraps the private one
   in `asyncio.to_thread`) — **connects to:** `sentiment_agent.tools`.

7. `_compute_technicals(ticker: str) -> dict[str, Any]` (private, sync — does
   the pandas rolling-mean/RSI/volatility math over 1y of price history) +
   `get_technicals(ticker: str) -> dict` (public tool) — **connects to:**
   `technicals_agent.tools`.

**Verify it.** Call `get_fundamentals("NVDA")` directly (not through an
agent) — real numbers back. Call it with a garbage ticker — `data_warnings`
non-empty, no crash.

---

## Phase 6 — RAG: EDGAR ingestion, chunking, embeddings, retrieval

Five files under `backend/rag/`, built in this order because each imports
the previous:

1. **`edgar.py`**
   - `lookup_cik(client: httpx.AsyncClient, ticker: str) -> str` — **in:** a
     shared httpx client + ticker — **out:** the SEC CIK number — **connects
     to:** called first inside `latest_filing`, below.
   - `latest_filing(client, ticker, forms=("10-K","10-Q")) -> FilingMeta` —
     **out:** a `FilingMeta` dataclass (`ticker, cik, form_type,
     accession_no, filing_date, primary_document`, plus a computed `.url`
     property) — **connects to:** called by `ensure_filing_ingested` in
     `ingest.py`.
   - `fetch_filing_text(client, meta: FilingMeta) -> str` — **in:** the
     `FilingMeta` from the call above — **out:** the filing's plain text,
     HTML stripped — **connects to:** its output is fed straight into
     `chunk_filing` (next file).
   - `EdgarError(Exception)` — raised by the two network calls above, caught
     in `ensure_filing_ingested` so a down EDGAR degrades the run instead of
     crashing it.

2. **`chunking.py`**
   - `split_sections(text: str) -> list[tuple[str, str, str]]` — **in:** full
     filing text — **out:** `[(item_number, section_title, section_text), ...]`
     for the high-signal Items only (1, 1A, 3, 5, 7, 7A, 8) — **connects to:**
     called first inside `chunk_filing`.
   - `chunk_section(item, title, text, chunk_tokens=None, overlap_tokens=None) -> list[Chunk]`
     — **in:** one section's text (defaults for window size come from
     `settings.chunk_size_tokens`/`chunk_overlap_tokens`, Phase 4) —
     **out:** `Chunk` dataclasses (`item, section_title, chunk_index,
     content`) — **connects to:** called once per section inside
     `chunk_filing`.
   - `chunk_filing(text: str, max_chunks=400) -> list[Chunk]` — **out:** the
     capped, flattened list across all sections — **connects to:** called by
     `ensure_filing_ingested`; its output list is what gets embedded next.
   - `count_tokens(text: str) -> int` — a `tiktoken` wrapper used internally
     by the windowing logic above.

3. **`embeddings.py`**
   - `_get_client() -> AsyncOpenAI` (private, memoized module-level client).
   - `embed_texts(texts: list[str]) -> EmbeddingResult` — **in:** the chunk
     content strings, batched — **out:** `EmbeddingResult(vectors:
     list[list[float]], total_tokens: int, cost_usd: float)` (cost via
     `estimate_cost_usd`, Phase 4) — **connects to:** called once per filing
     by `ensure_filing_ingested`, with every chunk's text at once.
   - `embed_query(text: str) -> list[float]` — **in:** one search string —
     **out:** one vector (calls `embed_texts([text])` and unwraps it) —
     **connects to:** called by `search_chunks` in `retrieval.py`.

4. **`ingest.py`**
   - `IngestStatus` dataclass — `status: Literal["ingested","cached","unavailable"]`,
     `detail, form_type, filing_date, chunk_count, embedding_cost_usd`.
   - `ensure_filing_ingested(db: AsyncSession, ticker: str) -> IngestStatus`
     — **in:** a db session + ticker — **out:** `IngestStatus` — **body
     order:** check `Filing` table for an existing row by `accession_no`
     (from `latest_filing`) → if found, return `status="cached"` immediately
     → else fetch text, `chunk_filing`, `embed_texts`, insert one `Filing`
     row + one `FilingChunk` row per chunk (Phase 9's models), return
     `status="ingested"` — **connects to:** called once per pipeline run, as
     the very first step, in `pipeline/research.py` (Phase 8) — **and** its
     `EdgarError`/generic-exception handling means it *never raises*; a
     failed ingest just returns `status="unavailable"` and the run continues
     ungrounded.

5. **`retrieval.py`**
   - `RetrievedChunk` dataclass — `content, item, section_title, form_type,
     filing_date, similarity`, plus a computed `.source` property (e.g.
     `"10-K 2026-02-25 Item 1A — Risk Factors"`).
   - `search_chunks(db, ticker, query, k=None) -> list[RetrievedChunk]` —
     **in:** db session, ticker, free-text query — **out:** top-`k` (default
     `settings.rag_top_k`) chunks by pgvector cosine distance — **connects
     to:** called by the `search_filings` tool, next file.

6. **`backend/tools/filings.py`**
   - `search_filings(ticker: str, query: str) -> dict` (`@function_tool`) —
     **in:** ticker + query, from the calling agent — **out:** `{results:
     [{source, similarity, passage}, ...]}` or a "no results" note —
     **connects to:** registered in `fundamentals_agent.tools` and
     `risk_agent.tools` (Phase 7). **Important detail for Phase 10:** this
     function opens its **own** `AsyncSessionLocal()` internally — it does
     not receive the pipeline's session — because specialist agents run
     concurrently and one `AsyncSession` isn't safe to share across
     concurrent tasks. This is *why* the pipeline needs an explicit
     `db.commit()` right after `ensure_filing_ingested` returns: this
     function's separate session can't see uncommitted rows from the
     pipeline's session.

**Verify it.** `await ensure_filing_ingested(db, "NVDA")`, then
`await search_chunks(db, "NVDA", "customer concentration risk")` — 3–5
chunks back, each `.source` reading like `"10-K 2026-02-25 Item 1A — Risk
Factors"`, top result actually about customer concentration.

---

## Phase 7 — Agent definitions

Six files under `backend/agents/`, each one module-level `Agent(...)`
instance — not a function you call directly; the Agents SDK's `Runner.run()`
(Phase 8) is what invokes it.

1. `fundamentals.py` → `fundamentals_agent = Agent(name="FundamentalsAgent",
   model=settings.specialist_model, instructions="<rubric — see below>",
   tools=[get_fundamentals, search_filings], output_type=FundamentalsOutput)`
   — **in, at call time:** a plain string prompt, `f"Analyze {ticker}"` —
   **out:** a `FundamentalsOutput` instance, reached via
   `Runner.run(fundamentals_agent, prompt).final_output` — **connects to:**
   referenced in the `SPECIALISTS` dict in `pipeline/research.py` (Phase 8).
   Instructions must state the scoring rubric explicitly band-by-band (9–10
   / 7–8 / 5–6 / 3–4 / 0–2) and require citations when `search_filings`
   returns results — vague instructions produce scores that drift between
   runs with no way to tell if that's signal or noise.

2. `risk.py` → `risk_agent`, `output_type=RiskOutput`, tools =
   `[get_risk_metrics, search_filings]`. Instructions must state the score is
   **inverted** (10 = safest) — this is invisible to the model unless you
   say it explicitly, since every other pillar is "higher = better" in the
   usual sense too, just for a different underlying reason.

3. `technicals.py` → `technicals_agent`, `output_type=TechnicalsOutput`,
   tools = `[get_technicals]`.

4. `sentiment.py` → `sentiment_agent`, `output_type=SentimentOutput`,
   tools = `[get_analyst_sentiment, get_recent_news]`.

5. `synthesizer.py` → `synthesizer_agent`, `model=settings.synthesizer_model`,
   `output_type=ReportDraft`, **no tools** (it only ever sees the JSON
   payload the pipeline hands it — Phase 8's `_specialists_payload`). Its
   instructions must state the verdict-to-score bands explicitly (mirroring
   `verdict_band` from Phase 3) so the model's own verdict choice is
   *usually* already consistent, even though the pipeline never trusts this
   for the score itself.

6. `critic.py` → `critic_agent`, `model=settings.critic_model`,
   `output_type=CriticOutput`, no tools. Instructions must give a concrete
   severity rubric (what makes something `high` vs `low`) and state plainly
   that `blocks_publication` should only be `true` for at least one `high`
   challenge — otherwise the loop in Phase 8 either never triggers a
   revision or triggers one too often.

**Verify it.** `await Runner.run(fundamentals_agent, "Analyze NVDA")` →
inspect `.final_output` — real score, real citations, before wiring four of
these together where a bug in one is harder to isolate.

---

## Phase 8 — Tracing wrapper + the orchestrator

**File 1: `backend/pipeline/tracing.py`**

1. `TracedRun` dataclass — `agent_name, phase, model, output, input_tokens,
   output_tokens, requests, cost_usd, latency_ms, started_at, finished_at`,
   plus two computed properties: `.output_dict` (the output's
   `.model_dump()` if it's a `BaseModel`, else `{"text": str(output)}`) and
   `.usage_event` (the small dict shape the SSE `usage` field needs).

2. `traced_run(agent: Agent, input_text: str, phase: str) -> TracedRun` —
   **in:** an `Agent` instance (any of Phase 7's), a prompt string, a phase
   label (`"research"|"synthesis"|"critique"|"revision"`) — **body:** times
   `await Runner.run(agent, input_text)`, reads `result.context_wrapper.usage`,
   calls `estimate_cost_usd` (Phase 4) — **out:** one `TracedRun` — **connects
   to:** called *instead of* `Runner.run` directly, everywhere in
   `pipeline/research.py`, below — this is the one function that must wrap
   every single agent call, or that call's cost/latency simply isn't
   recorded anywhere.

**File 2: `backend/pipeline/research.py`**

3. `_specialists_payload(outputs: dict[str, SpecialistOutput], overall_score: float) -> str`
   — **in:** the four specialist outputs keyed by pillar name + the computed
   score — **out:** one JSON string — **connects to:** this exact string is
   the prompt handed to `synthesizer_agent` and (alongside the draft) to
   `critic_agent`.

4. `run_research_pipeline_stream(ticker: str, db: AsyncSession) -> AsyncGenerator[dict]`
   — **in:** ticker, db session — **out:** yields event dicts — **body, in
   order:**
   1. `crud.create_report(db, ticker)` (Phase 9) → `await db.commit()`
      (**must** happen here — see Phase 6's note on `search_filings`'
      separate session) → `yield {"type": "start", ...}`
   2. `ensure_filing_ingested(db, ticker)` (Phase 6) → `await db.commit()`
      (**must** happen here too, same reason) → `yield {"type": "grounding", ...}`
   3. `asyncio.gather` over `traced_run(agent, f"Analyze {ticker}", "research")`
      for all four Phase-7 specialists → as each resolves, `crud.add_agent_run`
      (Phase 9) + `yield {"type": "agent_completed", ...}`
   4. `compute_overall_score(...)` (Phase 3) on the four results
   5. `traced_run(synthesizer_agent, _specialists_payload(...), "synthesis")`
      → overwrite `draft.overall_score` with step 4's value → `yield`
   6. `while True:` — `traced_run(critic_agent, ..., "critique")` → `yield
      {"type": "critic_verdict", ...}` → `if not blocks_publication: break`
      → `if revision_count >= settings.max_revisions or total_cost >=
      settings.max_cost_usd: break` → else `traced_run(synthesizer_agent,
      <draft + challenges>, "revision")`, increment `revision_count`, loop
   7. `crud.complete_report(...)` (Phase 9) → `yield {"type": "complete", ...}`
   - **Exception handling:** the whole body after step 1 is inside a `try`;
     `except Exception: crud.fail_report(db, report, str(e)); yield
     {"type": "error", ...}; raise`.
   - **Connects to:** called by the SSE route in `api/routes_research.py`
     (Phase 10).

5. `run_research_pipeline(ticker: str, db: AsyncSession) -> dict` — **in:**
   same — **out:** just the `"complete"` event's payload — **body:**
   `async for event in run_research_pipeline_stream(...): if event["type"]
   == "complete": final = event` — **connects to:** called by the
   non-streaming `POST /api/research` route (Phase 10).

**Verify it.** Run the pipeline against a real ticker, print every yielded
event as it arrives — the four `agent_completed` events should arrive in
whatever order the specialists actually finish (proof they're really
concurrent), then synthesis, then at least one `critic_verdict`.

---

## Phase 9 — Persistence: models, session, CRUD, migration

**File 1: `backend/db/session.py`**
- `Base(DeclarativeBase)` — every model in the next file inherits this.
- `get_db()` (async generator) — **out:** yields one `AsyncSession`, commits
  on clean exit, rolls back on exception — **connects to:** used as a
  FastAPI `Depends(get_db)` in every route that touches the database
  (Phase 10).

**File 2: `backend/db/models.py`** — five `Base` subclasses, in dependency
order: `User` → `ResearchReport` (FK to `User`) → `AgentRun` (FK to
`ResearchReport`) → `Filing` → `FilingChunk` (FK to `Filing`, has the
`Vector(1536)` embedding column + HNSW index). Plus `utcnow() -> datetime`,
a small helper every model's `created_at` default calls.

**File 3: the Alembic migration** (`backend/migrations/versions/..._schema_v2...py`)
— hand-written, not autogenerated (autogenerate doesn't know pgvector's
`Vector` type or HNSW index DDL): `CREATE EXTENSION IF NOT EXISTS vector`,
restructure `research_reports` (drop the old free-text columns, add
`report`/`critic` JSONB), `CREATE TABLE agent_runs/filings/filing_chunks`,
`CREATE INDEX ... USING hnsw (embedding vector_cosine_ops)`.

**File 4: `backend/db/crud.py`** — every function takes the `db: AsyncSession`
first, matching `get_db`'s yield:
- `create_report(db, ticker: str) -> ResearchReport` — **out:** a new row,
  `status="running"` — **connects to:** step 1 of Phase 8's pipeline.
- `add_agent_run(db, report_id: uuid.UUID, run: TracedRun) -> AgentRun` —
  **in:** a `TracedRun` from Phase 8's `traced_run` — **out:** the inserted
  row — **connects to:** called once per agent call inside the pipeline.
- `complete_report(db, report, draft: ReportDraft, critic: CriticOutput | None, revision_count: int, prompt_tokens: int, completion_tokens: int, cost_usd: float, latency_ms: int) -> ResearchReport`
  — writes the final structured report + totals onto the row —
  **connects to:** step 7 of Phase 8's pipeline.
- `fail_report(db, report, error: str) -> ResearchReport` — **connects to:**
  the pipeline's `except` block.
- `get_report(db, report_id: uuid.UUID) -> ResearchReport | None` — eager-loads
  `agent_runs` — **connects to:** the `GET /api/reports/{id}` route (Phase 10).
- `list_reports(db, ticker: str | None, limit: int, offset: int) -> tuple[list[ResearchReport], int]`
  — **connects to:** the `GET /api/reports` route.

**Verify it.** `alembic -c backend/alembic.ini upgrade head`, then in
`psql`: `\d filing_chunks` shows `embedding vector(1536)` with an `hnsw`
index.

---

## Phase 10 — API layer

**File 1: `backend/api/routes_research.py`**
- `research(request: ResearchRequest, db: AsyncSession = Depends(get_db)) -> dict`
  — `POST /api/research` — **body:** `return await run_research_pipeline(request.ticker, db)`.
- `research_stream(request: ResearchRequest)` — `POST /api/research/stream`
  — **body:** an inner `event_generator()` that opens its own
  `AsyncSessionLocal()` (not `Depends`, since this outlives one request/response
  cycle) and does `async for event in run_research_pipeline_stream(ticker, db):
  yield f"data: {json.dumps(event)}\n\n"`, then commits — **out:**
  `StreamingResponse(event_generator(), media_type="text/event-stream")`.
- `_summary(report: ResearchReport) -> ReportSummary` (private) — the row →
  API-shape mapping used by `list_reports`, next.
- `list_reports(ticker, limit, offset, db) -> ReportListResponse` — `GET
  /api/reports` — calls `crud.list_reports`, maps each row through `_summary`.
- `get_report(report_id: uuid.UUID, db) -> ReportDetailResponse` — `GET
  /api/reports/{id}` — calls `crud.get_report`, 404s if `None`, otherwise
  maps the row (including its `agent_runs`) to the response schema.

**File 2: `backend/main.py`** — `app = FastAPI(...)`, `app.add_middleware(CORSMiddleware,
allow_origins=settings.cors_origins, ...)`, `app.include_router(router)`,
`health() -> dict` at `GET /health`.

**Verify it.** `curl -N -X POST localhost:8000/api/research/stream -d
'{"ticker":"NVDA"}'` — `data: {...}` lines arrive live, ending in a
`"complete"` event.

---

## Phase 11 — Evaluation harness

**File 1: `evals/grounding.py`**
- `extract_numbers(text: str) -> list[float]` — regex-pulls every number out
  of a string.
- `check_grounding(report_text: str, source_data: dict) -> GroundingResult`
  — **in:** a report's prose + the specialist JSON it came from — **out:**
  `GroundingResult(checked: int, violations: list[float])` — every number in
  `report_text` (after skipping small integers/years) must appear in
  `source_data`, literally or as a `x100`/`/100` percent conversion —
  **connects to:** called by `evals/test_deterministic.py`.

**File 2: `evals/test_deterministic.py`** — Tier 1, free, CI-gated. Loads
`evals/fixtures/nvda_specialists.json` + `nvda_report.json` (a real recorded
pipeline run) via `evals/conftest.py` fixtures, then asserts: every schema
validates, `overall_score` equals a fresh call to `compute_overall_score`
(Phase 3) on the fixture's own specialist data, `verdict in
verdict_band(overall_score)`, `check_grounding(...)` has zero violations, a
blocking critic verdict has at least one `high`-severity challenge.

**File 3: `evals/judges.py`** — `JudgeScores(BaseModel)` (groundedness/
completeness/actionability, 1–5 each) + `judge_report(specialists: dict,
report: dict) -> JudgeScores` — calls a separate `gpt-4o` chat completion
with `response_format=JudgeScores` over the same fixtures. **File 4:
`evals/test_llm_judge.py`** — Tier 2, opt-in (`pytest -m llm_eval`), asserts
each score clears a floor.

**Verify it.** `uv run pytest evals -q` passes in seconds, zero API calls.
`uv run pytest evals -m llm_eval -q -s` costs about two cents and prints
real scores.

---

## Phase 12 — Tests

**File: `tests/factories.py`** — plain builder functions (`make_specialist`,
`make_draft`, `make_critic`, `make_traced_run`) that construct Phase 3/8
objects with made-up data — no LLM involved.

**File: `tests/conftest.py`** — `db_engine` fixture (SQLite in memory, **`poolclass=StaticPool`**
— required because Phase 8's pipeline does mid-run commits, and SQLite's
default pooling would silently hand a *different*, empty in-memory database
back after a commit without this), `session_factory`, `db_session`, `client`
(httpx `ASGITransport` against the real FastAPI `app`, with `get_db`
overridden to yield the test session).

**File: `tests/test_pipeline.py`** — a `ScriptedAgents` callable that
replaces `pipeline.research.traced_run` via `monkeypatch`, returning canned
`TracedRun`s instead of calling the real SDK. Key assertions: a critic
script of `[True]*10` (never approves) still stops at exactly
`settings.max_revisions` (Phase 8's bound actually bounds); a specialist
`traced_run` that raises leaves the report `status="failed"` with the error
message stored.

**File: `tests/test_api.py`** — hits the real routes (Phase 10) through the
`client` fixture, asserting response shapes and a 404 on an unknown report
ID.

**Verify it.** `uv run pytest tests -q` — a couple of seconds, works with
your network disconnected.

---

## Phase 13 — Docker + CI

**Files:** `backend/Dockerfile` (multi-stage: `uv sync --frozen` in a build
stage, copy the built `.venv` into a slim runtime stage, `CMD` runs `alembic
upgrade head` then `uvicorn`), `frontend/web/Dockerfile` (Next.js `output:
"standalone"` build), `docker-compose.yml` (`db`, `backend`, `frontend`
services, the latter two behind a `full` profile), `.github/workflows/ci.yml`
(`ruff check` → `pytest tests evals` → frontend `npm run lint` + `next build`,
on every push).

**Verify it.** `docker compose --profile full up --build` from a clean
checkout (`git clean -xdf` first if you want to be sure) works with zero
manual steps beyond `.env`.

---

## Phase 14 — Design the UI before building it

**File:** `DESIGN.md` — no code. A token table (color/type/spacing, values
decided and machine-validated *before* any CSS exists), ASCII wireframes per
screen, and — specifically for a streaming interface — an explicit table
mapping every SSE event type (Phase 8's `yield` shapes) to the exact UI
change it causes. That table is Phase 15's `useResearchStream.ts` spec,
written down before the reducer exists.

---

## Phase 15 — Frontend build

Bottom-up: tokens → types → the state machine → leaf components → pages —
each step only depends on the ones before it.

1. **`frontend/web/src/app/globals.css`** — CSS custom properties translated
   directly from `DESIGN.md`'s token table, mapped into Tailwind via
   `@theme`/`@theme inline`.

2. **`frontend/web/src/lib/types.ts`** — hand-translated from Phase 3's
   Pydantic schemas: `interface Report`, `SpecialistOutput`, `Citation`,
   `CriticOutput`, etc. — field-for-field the same shape the backend emits.

3. **`frontend/web/src/lib/events.ts`** — hand-translated from Phase 8's
   `yield` shapes: `StartEvent, PhaseEvent, GroundingEvent,
   AgentStartedEvent, AgentCompletedEvent, CriticVerdictEvent, CompleteEvent,
   ErrorEvent`, unioned into `PipelineEvent`.

4. **`frontend/web/src/lib/score.ts`** — pure functions with no framework
   dependency, built before anything that uses them: `scoreTone(score:
   number): ScoreTone`, `verdictTone(verdict: Verdict): ScoreTone`,
   `formatMoney/formatDuration/formatTokens(...)`.

5. **`frontend/web/src/lib/useResearchStream.ts`** — the state machine:
   - `RunState` interface — the single source of truth every component reads.
   - `reduceEvent(state: RunState, event: PipelineEvent): RunState` — one
     `switch` case per `PipelineEvent` variant, each case doing exactly what
     Phase 14's event table specified.
   - `reducer(state, action): RunState` — wraps `reduceEvent` plus
     `run_requested`/`reset`/`disconnected` actions.
   - `useResearchStream()` — **out:** `{ state, start, reset }` — `start(ticker)`
     does `fetch(POST /api/research/stream)`, reads `res.body.getReader()`,
     splits on `\n\n`, parses each `data: ` line as JSON, dispatches it —
     **connects to:** every page component below calls this one hook; no
     component talks to `fetch` or SSE directly.

6. **Leaf components** (each pure, given props, built and sanity-checked
   before anything stateful uses them): `ScoreDial`, `VerdictChip`,
   `PillarBars`, `SpecialistCard`, `CriticCard`+`Stamp`.

7. **Stateful components** (read from `RunState`): `Desk` (renders
   `run.agents[*]`), `Tape` (renders `run.tape`), `RunStatusStrip`.

8. **`ReportPaper`** — the shared artifact component, takes a `Report` +
   optional `CriticOutput`/`revisionCount`/`publishedAt` — used identically
   by the console (post-publication) and the dossier page.

9. **Pages** — `app/page.tsx` (client component, owns `useResearchStream`),
   `app/reports/page.tsx` + `app/reports/[id]/page.tsx` (server components,
   `fetch` the FastAPI backend directly at render time via `lib/api.ts`'s
   `fetchReports`/`fetchReport`).

**Verify it.** `npm run build` clean, then a real research request through
the actual browser UI — watch nodes go idle → working → done, the tape write
live, the paper rise on completion.

---

## Phase 16 — Iteration 1: readability + branding

No new files — systematic edits across existing components: every
`text-[Npx]` under a 13px floor raised, secondary-text color brightened,
`resources/logo.png` processed (Pillow: strip near-white pixels to alpha,
soft threshold at the edge to avoid a halo) into `frontend/web/public/logo.png`
+ `src/app/icon.png`, placed in the nav.

**Verify it.** Screenshot the same screen before/after — the size/contrast
difference should be visible at a glance, not just measurable.

---

## Phase 17 — Iteration 2: the day/night theme system

1. **`globals.css` rewrite** — every color token becomes a CSS custom
   property with three definitions: a `:root` default (light), a `@media
   (prefers-color-scheme: dark)` override, and a `:root[data-theme="light"/"dark"]`
   override that wins over both. `@theme inline` maps each one
   (`--color-bg: var(--bg)`, etc.) into a Tailwind utility. The report
   artifact's `paper`/`paper-ink`/`paper-line` tokens are declared *once*,
   outside all three theme selectors — they don't change with the toggle.

2. **`app/layout.tsx`** — a `next/script` with `strategy="beforeInteractive"`,
   written **inline in this file** (not imported from a separate component —
   Next's static analysis for this strategy only recognizes it lexically
   inside the root layout), reads `localStorage.getItem("finsight-theme")`
   (falling back to `matchMedia("(prefers-color-scheme: dark)")`) and sets
   `document.documentElement.dataset.theme` before first paint.

3. **`components/ThemeToggle.tsx`** — `getStoredOrSystemTheme(): Theme`
   (mirrors step 2's logic for client-side reads) + `ThemeToggle()` — a
   button that flips `data-theme` and writes `localStorage`, rendered in the
   nav next to the existing links.

4. **Every component** that referenced the old `ink-*` token names gets
   renamed to the new semantic ones (`bg-bg`, `text-text-muted`,
   `border-border`, …) — a mechanical find/replace, not a logic change.

**Verify it.** Force `localStorage.setItem('finsight-theme','light')` +
reload, screenshot; repeat for `'dark'`. Confirm `curl localhost:3000 | grep
theme-init` actually contains the script (this is the exact check that
caught the App-Router `<head>`-stripping bug during this build — a clean
`next build` does **not** prove the script is in the shipped HTML).

---

## Phase 18 — Write it down

No application code. `ARCHITECTURE.md`'s Future Work section and this file
get written/updated last, after the system exists — because you can only
accurately say "here's why X is deferred" once you know exactly what
building X would require, which you now do, having just built everything
around it.

**Verify it.** Same test as Phase 1: read it cold, a day later. If a
decision or a deferred item doesn't say *why*, it's not finished.

---

## What to do differently on your own pass

1. **Decide the desk/paper (or your own surface-metaphor) split before
   touching color values.** Retrofitting "what's always paper-colored vs.
   what follows the theme" after Phase 16 shipped a single palette cost more
   than deciding it in Phase 14 would have.
2. **When something silently doesn't work, check the actual runtime state
   before changing code.** Phase 17's script-in-`<head>` bug and a stale
   Docker container squatting on port 3000 both cost more time *looking in
   the wrong place* than they would have cost to find. `curl` the actual
   HTML. `docker ps` the actual containers.
3. **Write the schema (Phase 3) and the rubric (Phase 7) before the code that
   fills them.** Every time a schema got tightened after an agent's
   instructions were already written loosely, the fix was a second pass —
   writing the strict version first is the same amount of work and skips it.
