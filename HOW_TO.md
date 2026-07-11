# HOW_TO — Rebuilding FinSightAI Yourself

> This is a **guide for you to reproduce this build by hand**, not a changelog. It
> walks through every phase in the order it actually happened, explains *why*
> each decision was made (with an analogy where one helps), names the files
> involved, and tells you how to check your own work at each step. The
> `claude-help` branch has the finished code if you get stuck — but the point
> is to type it yourself and understand *why* it's shaped this way, not to
> copy it.
>
> Read this alongside [ARCHITECTURE.md](ARCHITECTURE.md) (the system's ADRs —
> the "why we chose X over Y" record) and [DESIGN.md](DESIGN.md) (the UI/UX
> spec). This file is the narrative that connects them: the order things were
> built in, and the reasoning at each fork in the road.

## How to use this document

Each phase has the same shape:

- **Goal** — what this phase produces
- **Analogy** — a mental model for *why* it's shaped this way
- **What to build** — the actual files and the shape of their contents
- **Why this way, not another way** — the alternatives that were considered and rejected
- **Verify it** — a concrete command or check proving the phase actually works before moving to the next one

Work through the phases **in order**. Each one assumes the previous ones are
done and working — this mirrors how the system was actually built: backend
core → data grounding → orchestration → persistence → quality gates →
packaging → design → frontend → iteration. Skipping ahead (e.g., building the
frontend before the backend can stream real events) means building against a
guess instead of a real contract, which is exactly the mistake typed schemas
(Phase 3) and the design-doc-before-code rule (Phase 12) both exist to
prevent.

---

## Phase 0 — Read the starting point before changing anything

**Goal.** Understand what already existed before writing a single line.

**Analogy.** You don't renovate a house by knocking down walls on day one —
you walk through first and figure out which walls are load-bearing.

**What was there.** A partially-working FastAPI + OpenAI Agents SDK backend:
four agents (fundamentals, risk, sentiment, a synthesizer, a critic) wired
into a linear pipeline, a Postgres schema with one `research_reports` table
storing markdown blobs, and a Streamlit demo UI. It worked end-to-end but had
real gaps: specialist agents returned free-form markdown text (not
structured data), there was no grounding beyond `yfinance` ratios (nothing
from actual filings), no tests, no cost/latency tracking, and the "UI" was a
prototyping tool, not a product.

**What to do in your own rebuild.** Before writing code, spend 30–60 minutes
just reading: every Python file, the `pyproject.toml` dependencies, the one
existing Alembic migration, the Streamlit script. Write down (even just to
yourself) three lists: *what works*, *what's structurally wrong* (not just
"missing," but "will actively fight me if I build on top of it as-is"), and
*what's simply not started yet*. This is what became the source material for
Phase 1's architecture decisions.

**Verify it.** You should be able to explain, in one sentence each, what
every existing file does — before you add or change anything.

---

## Phase 1 — Write the architecture document first, code second

**Goal.** Produce [ARCHITECTURE.md](ARCHITECTURE.md): one file that states,
for every major decision, what was chosen, what alternatives were rejected,
and why — *before* those decisions get baked into code.

**Analogy.** A structural engineer's report for a building. Nobody pours
concrete before deciding steel vs. wood framing and writing down why — because
five years later, when someone asks "why is this wall load-bearing?", the
answer needs to exist somewhere other than "ask the person who left." An
Architecture Decision Record (ADR) is that written answer, made at the moment
of the decision, not reconstructed afterward.

**What to build.** A markdown file with one ADR per major decision. The
format that worked well:

```markdown
### ADR-N: <the decision, stated as a title>

**Decision.** One paragraph: what was chosen, concretely.

**Why.** The reasoning — what problem this solves, what property it gives you.

**Alternatives rejected.**
- **Option A** — what it is, and the *specific* reason it loses here (not
  "it's worse," but "it costs X for a benefit Y that doesn't apply because Z")
- **Option B** — same treatment

**Trade-off accepted.** What you're giving up by choosing this, stated
honestly, so a future reader (including future-you) knows it was a conscious
choice, not an oversight.
```

The ADRs this project needed, roughly in the order they had to be decided
(each is explained in depth in its own ADR — this is the map, not the
territory):

1. **Orchestration shape** — deterministic Python control flow vs. an agent
   framework like LangGraph/CrewAI (ADR-1). Decide this *first* — it determines
   the shape of every agent and every API response you write afterward.
2. **Agent runtime** — which SDK actually calls the LLM and manages tool use
   (ADR-2).
3. **Inter-agent contracts** — typed schemas vs. free text between agents
   (ADR-3). This one is foundational; get it wrong and everything downstream
   (evals, UI, database) inherits the mess.
4. **Model routing** — one model everywhere vs. cheap-for-extraction,
   strong-for-judgment (ADR-4).
5. **Grounding strategy** — RAG over filings, and specifically *why* pgvector
   over a dedicated vector database (ADR-5).
6. **The quality gate** — adversarial critic with a bounded revision loop
   (ADR-6).
7. **Transport** — SSE vs. WebSockets vs. polling for streaming the run to
   the browser (ADR-7).
8. **Observability** — first-party trace tables vs. a third-party LLM-ops
   product (ADR-8).
9. **Evaluation** — a two-tier harness, deterministic + LLM-judge, over
   *golden fixtures* rather than live data (ADR-9).
10. **Frontend stack** — Next.js, and specifically that the UI gets its own
    design document before any component code (ADR-10 — this is Phase 12).
11. **Packaging** — Docker Compose + GitHub Actions, and explicitly not
    Kubernetes (ADR-11).

**Why this way, not another way.** The tempting alternative is "figure it out
as you code" — decide the orchestration shape by writing the pipeline function
and seeing what feels right. That works for a toy script. It breaks down the
moment more than one subsystem depends on the decision: the database schema,
the API response shape, the frontend's SSE event types, and the eval harness
all had to agree on "what does one agent's output look like" (ADR-3) *before*
any of those four things could be built without guessing. Writing the ADR
first means you make that decision exactly once, deliberately, instead of
accidentally re-deciding it four different ways in four different files.

**Verify it.** Read your ADR file cold, a day later, and check: for each
decision, could a stranger understand *why*, not just *what*? If an ADR just
restates the decision without a real "alternatives rejected" section, it's
not done — go back and actually name what you didn't choose and why.

---

## Phase 2 — Environment: reproducible before anything else

**Goal.** A backend that any machine (yours tomorrow, a reviewer's laptop,
CI) can stand up identically.

**Analogy.** A recipe that says "some flour, a bit of sugar" is not
reproducible; a recipe that says "300g flour, 120g sugar" is. `uv.lock` and
`docker-compose.yml` are the exact-gram version of your dependencies and your
database.

**What to build.**

1. Python dependency management with **uv** (not raw `pip`/`venv`):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   uv sync                      # creates .venv, installs exactly what's locked
   ```
   `pyproject.toml` lists direct dependencies with version floors; `uv.lock`
   pins the *exact* resolved versions (including transitive ones). Commit
   `uv.lock` — this is the "300g flour," not the vague "some flour."

2. A local Postgres with the `pgvector` extension, via Docker, **not** a
   locally-installed Postgres — because you need the vector extension (ADR-5)
   and you want the exact same database image in dev, CI, and prod:
   ```yaml
   # docker-compose.yml (db service)
   services:
     db:
       image: pgvector/pgvector:pg17
       environment:
         POSTGRES_USER: finsight
         POSTGRES_PASSWORD: finsight
         POSTGRES_DB: finsight
       ports: ["5432:5432"]
   ```
   ```bash
   docker compose up -d db
   docker exec finsight-db psql -U finsight -d finsight -c "CREATE EXTENSION IF NOT EXISTS vector;"
   ```

3. `.env` (gitignored) with `OPENAI_API_KEY` and `DATABASE_URL`; `.env.example`
   (committed) as the template — so the *shape* of required config is in
   version control even though the secrets aren't.

**Why this way, not another way.** A locally-installed Postgres works too,
right up until you need the pgvector extension and discover your OS package
manager has an old Postgres version that doesn't support it cleanly, or your
teammate's local Postgres has a different collation, or CI needs a
from-scratch database and now you're maintaining install scripts for three
platforms. The `pgvector/pgvector:pg17` image *is* Postgres 17 with the
extension pre-built — zero platform-specific installation, identical
everywhere.

**Verify it.** `uv run python -c "import agents, pgvector, fastapi; print('ok')"`
succeeds, and `docker exec finsight-db psql -U finsight -d finsight -c "SELECT extname FROM pg_extension WHERE extname='vector';"`
returns one row.

---

## Phase 3 — Typed contracts between agents (the backbone)

**Goal.** `backend/schemas/agents.py` — one Pydantic model per agent output,
used as the *only* way agents communicate with each other, the database, and
eventually the UI.

**Analogy.** A shipping manifest. When a package moves between warehouses,
nobody opens the box and re-inspects the contents at every stop — there's a
manifest listing exactly what's inside, in a fixed format, and every handler
downstream trusts it. Free-text agent output (the old design: markdown ending
in `SCORE: 7`) is the opposite — every downstream consumer has to "open the
box" (regex-parse the text) and guess, and a shipment (an LLM response) that's
packed slightly differently breaks every handler downstream of it silently.

**What to build.** For each specialist, a Pydantic model with **required,
typed fields** — not optional free text with a hopeful comment:

```python
class SpecialistOutput(BaseModel):
    score: float = Field(ge=0, le=10)
    confidence: Literal["low", "medium", "high"]
    summary: str
    bullets: list[str]
    data_warnings: list[str]   # explicit gaps, not silently-invented numbers

class FundamentalsOutput(SpecialistOutput):
    citations: list[Citation]   # filing passages this agent actually used
```

Give this to the Agents SDK as `output_type=FundamentalsOutput` — the SDK
enforces the schema on the model's response, retrying if it doesn't validate.
You get a Python object, not a string to parse.

One more piece worth calling out: **compute arithmetic in code, not in the
prompt.** The overall score is a weighted average of four pillar scores —
don't ask an LLM to "compute the weighted average and put it in the
`overall_score` field." LLMs are unreliable at exact arithmetic and you'd have
to write a test to catch a wrong sum anyway. Instead:

```python
def compute_overall_score(fundamentals, risk, sentiment, technicals) -> float:
    return round(
        fundamentals.score * 0.35 + risk.score * 0.30 +
        sentiment.score * 0.20 + technicals.score * 0.15, 1
    )
```

...and overwrite whatever the synthesizer put in that field with this
computed value after the fact. Let the model do the parts only a model can do
(judgment, prose); let code do the parts code is exact at (arithmetic).

**Why this way, not another way.** The free-text alternative ("just have the
model write markdown, parse scores with a regex at the end") is genuinely
faster to build on day one. It is where the *old* codebase started, and it's
exactly what had to be undone: a regex looking for `SCORE: (\d+)` breaks the
moment a model writes `Score: 7/10` instead, and there's no way to validate
"did the agent actually include a confidence level" without... writing a
schema, at which point you should have just started with one. Typed contracts
cost more up front (defining every field) and pay for themselves at every
consumer: the eval harness (Phase 10) can assert `0 <= score <= 10`
mechanically; the frontend (Phase 13) binds a chart to `report.overall_score`
instead of regex-scraping a paragraph; the critic (Phase 6) can check "does
this number in the draft appear anywhere in the specialist JSON" instead of
trying to fact-check prose against prose.

**Verify it.** Write one throwaway script that constructs each schema with
made-up data and calls `.model_dump_json()` — if a schema is awkward to
construct by hand, it'll be awkward for an LLM to fill in too; simplify it
before wiring it to an agent.

---

## Phase 4 — Configuration and model routing

**Goal.** `backend/core/config.py` — one place that says which model plays
which role, and what each model costs.

**Analogy.** Hospital triage. You don't send every patient to the chief
surgeon — a resident (a small, cheap model) handles the straightforward cases
(extracting numbers from a tool call and writing three bullet points), and
only the cases where a wrong call is expensive (synthesizing the final report,
adversarially reviewing it for fabrication) go to the attending physician (a
larger, more expensive model).

**What to build.**

```python
class Settings(BaseSettings):
    specialist_model: str = "gpt-4o-mini"   # 4 parallel calls per run — cheap
    synthesizer_model: str = "gpt-4o"       # the actual product quality
    critic_model: str = "gpt-4o"            # weak critic = rubber stamp
    embedding_model: str = "text-embedding-3-small"
    max_revisions: int = 2
    max_cost_usd: float = 0.50              # circuit breaker, see Phase 6

MODEL_PRICING_PER_1M = {  # (input, output) USD per 1M tokens
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    ...
}

def estimate_cost_usd(model, input_tokens, output_tokens) -> float:
    in_price, out_price = MODEL_PRICING_PER_1M.get(model, (0, 0))
    return (input_tokens * in_price + output_tokens * out_price) / 1_000_000
```

Read model names from `Settings` in every agent definition, never hardcode a
model string inside an agent file — the whole point is that changing the
synthesizer's model tier later is a one-line env change, not a grep-and-replace.

**Why this way, not another way.** Uniform-model pipelines (all `gpt-4o-mini`,
or all `gpt-4o`) are simpler to reason about but wrong in both directions: all-cheap
under-delivers exactly where quality matters most (the critic missing a
subtle fabrication), all-expensive overpays 4x for specialist calls that don't
need it. Routing by *task difficulty*, decided once here, is what makes the
per-run cost land around $0.02 instead of $0.08+ at equivalent quality.

**Verify it.** Run one specialist agent standalone and print
`estimate_cost_usd(model, usage.input_tokens, usage.output_tokens)` — the
number should be a fraction of a cent. If it's not, you're pointed at the
wrong model tier.

---

## Phase 5 — Tools: giving agents hands

**Goal.** `backend/tools/market.py` — async functions decorated
`@function_tool` that fetch real data (price, fundamentals, risk metrics,
news) via `yfinance`, which agents call before writing anything.

**Analogy.** An agent without tools is a analyst locked in a room with no
phone, no terminal, no newspaper — asked to write a report from memory alone.
Tools are the phone line out: "call this function, get real numbers back, now
write about *those*."

**What to build.** Each tool: async (so four specialists calling tools
concurrently actually overlap instead of blocking each other — push the
blocking `yfinance` call into a thread), returns a plain dict, and **reports
gaps explicitly** instead of omitting them silently:

```python
@function_tool
async def get_fundamentals(ticker: str) -> dict:
    info = await asyncio.to_thread(lambda: yf.Ticker(ticker).info)
    data = {"pe_ratio": info.get("trailingPE"), ...}
    data["data_warnings"] = [k for k, v in data.items() if v is None]
    return data
```

Wire the agent's instructions to *require* the gap be surfaced: "if a metric
is null, list it in `data_warnings` and lower your confidence — never
estimate a missing number." This is the first of several places (the critic
in Phase 6 is another) where the system is designed to make fabrication
*visible* rather than merely *hoping* the model doesn't do it.

**Why this way, not another way.** Returning `None` silently and letting the
model's prose gloss over it ("the company shows solid margins" — no number,
no explanation why) is how hallucination sneaks in: the model fills the gap
from training-data memory rather than admitting it doesn't have live data. An
explicit `data_warnings` list turns a silent gap into a structured signal the
critic (and later, a human reader) can actually see.

**Verify it.** Call `get_fundamentals("NVDA")` directly (not through an agent)
and confirm you get a plain dict back with real numbers. Then call it with an
obviously-wrong ticker and confirm `data_warnings` is non-empty instead of the
function crashing.

---

## Phase 6 — Grounding: RAG over SEC filings

**Goal.** Given a ticker, fetch its latest 10-K/10-Q from SEC EDGAR, split it
into searchable chunks, embed them, store them in Postgres (via pgvector),
and give agents a `search_filings` tool to query them — with citations.

**Analogy.** A research librarian, not a photocopier. If you handed an
analyst a 300-page 10-K and said "read this whenever you need it," they'd
either not read it (too slow) or paste the whole thing into every question
(too expensive, and the important sentence gets lost in the noise — "lost in
the middle"). A good librarian instead *pre-reads* the document once, sticks
labeled tabs on the important sections (chunking), and keeps a card catalog
organized by topic (embeddings) — so when asked "what does this company say
about customer concentration risk," she pulls the *right three pages* in
seconds, with the page numbers attached (citations), instead of re-reading
the whole filing from page one.

**What to build**, in four files under `backend/rag/`:

1. **`edgar.py`** — SEC EDGAR is free and keyless; it only requires a
   descriptive `User-Agent` header. Two calls: ticker → CIK number (from
   SEC's `company_tickers.json`), then CIK → most recent 10-K/10-Q filing
   metadata (from `data.sec.gov/submissions/`). Fetch the filing HTML and
   strip it to plain text.

2. **`chunking.py`** — **split by Item boundaries first**
   (`Item 1A. Risk Factors`, `Item 7. MD&A`, …) using a regex over `Item \d+[A-C]?`,
   *then* token-window each section (~800 tokens, 100 overlap) using `tiktoken`.
   This two-step order is the whole trick: chunking blindly by token count
   alone gives you citations like "chunk 47" — meaningless to a reader.
   Section-first chunking gives you "10-K Item 1A — Risk Factors," which is
   what an actual citation looks like.

3. **`embeddings.py`** — batch-call `text-embedding-3-small` (1536
   dimensions), track token usage → cost, same pattern as Phase 4.

4. **`ingest.py`** + **`retrieval.py`** — `ensure_filing_ingested(ticker)` is
   **idempotent per accession number**: check if this exact filing is already
   in the `filings` table before re-fetching/re-embedding anything (first run
   for a ticker costs ~10–20s and a fraction of a cent; every subsequent
   research of the same ticker skips straight to retrieval). `search_chunks`
   does cosine-similarity nearest-neighbor search via pgvector's
   `<=>` operator (exposed in SQLAlchemy as `.cosine_distance()`).

Expose this as a tool (`backend/tools/filings.py`) the fundamentals and risk
agents call, same `@function_tool` pattern as Phase 5.

**Why pgvector, not a dedicated vector database.** This is ADR-5 in full, but
the short version: you already run Postgres for reports and traces. One
database means one connection pool, one backup story, one Docker service —
and it means you can `JOIN` a report to the exact filing chunks that were
retrieved while researching it. Corpus size here (~1–3k chunks *per ticker*)
is nowhere near where a dedicated vector database's extra infrastructure pays
for itself.

**Why this way, not another way (chunking specifically).** The tempting
shortcut is "just embed the whole filing as one giant chunk" or "split every
N characters with no regard for structure." Both produce retrieval that
*technically works* — you get chunks back — but with citations no reader can
use ("this claim is supported by page-fragment 12 of an unlabeled slice") and
worse relevance (a fixed-size window can start mid-sentence, split a table in
half, or straddle two unrelated sections).

**Verify it.** Run `ensure_filing_ingested(db, "NVDA")` directly, then
`search_chunks(db, "NVDA", "customer concentration risk")` — you should get
back 3–5 chunks, each with a `source` string that reads like
`"10-K 2026-02-25 Item 1A — Risk Factors"` and a `similarity` score. If the
top result isn't actually about customer concentration, your chunking is
probably too coarse or too fine — adjust `chunk_size_tokens` and re-test
before moving on.

---

## Phase 7 — Agents: the newsroom

**Goal.** `backend/agents/*.py` — one `Agent` per role, each with tools
(Phases 5–6), a typed `output_type` (Phase 3), and instructions that encode a
scoring rubric.

**Analogy.** A newsroom with a strict production process. Four **beat
reporters** (fundamentals, technicals, risk, sentiment specialists) each
research their own beat independently and file a story with sources attached.
An **editor** (the synthesizer) combines the four stories into one piece.
Before it goes to print, a **fact-checker with the temperament of an
adversarial lawyer** (the critic) reads the draft against the original
sources looking specifically for anything that isn't backed up — and can
send it back to the editor for a rewrite.

**What to build.** Per agent, instructions that are specific and checkable,
not vibes:

```python
fundamentals_agent = Agent(
    name="FundamentalsAgent",
    model=settings.specialist_model,
    instructions="""
    Always call get_fundamentals before writing anything.
    Always call search_filings at least once to ground your view in the
    company's own 10-K/10-Q.
    Every number MUST come from tool results — never estimate.
    Scoring rubric (0-10): 9-10 strong growth + expanding margins + reasonable
    valuation ... 0-2 fundamentally broken.
    """,
    tools=[get_fundamentals, search_filings],
    output_type=FundamentalsOutput,
)
```

Two details worth getting right the first time:

- **Give an explicit scoring rubric in the instructions**, band by band (9–10
  means *this*, 0–2 means *that*). Without it, scores drift — the same
  underlying data can get a 6 in one run and an 8 in another, and neither the
  critic nor a reader can tell if that's a meaningful signal or just noise.
- **The risk agent's score direction is inverted on purpose**: 10 = *safest*,
  0 = *riskiest* — so that every pillar score, across all four specialists,
  points the same direction ("higher is better for the investor"). State this
  explicitly in the instructions; it's the kind of thing that's obvious to
  you and invisible to the model unless you say it.

**Why this way, not another way.** A vague instruction ("assess the
company's risk") produces plausible-sounding but *incomparable* output run to
run. A rubric turns "assess risk" into something closer to a checklist,
which is both more consistent and — critically — something the eval harness
(Phase 10) can later grade against, because "the rubric said X, the report
said Y" is checkable in a way "did this feel about right" is not.

**Verify it.** Run each specialist standalone (`Runner.run(agent, "Analyze
NVDA")`) and inspect `result.final_output` — confirm the score, confidence,
and citations look reasonable *before* wiring four of them together in a
pipeline where a bug in one is harder to isolate.

---

## Phase 8 — Orchestration: the assembly line, not the committee

**Goal.** `backend/pipeline/research.py` — the function that actually runs
the four specialists in parallel, then synthesis, then the bounded
critic↔synthesizer loop, yielding events the whole way.

**Analogy.** An assembly line versus a committee meeting. An assembly line has
fixed stations in a fixed order — every car gets its doors attached at
station 4, always, and the line doesn't stop to vote on whether this
particular car needs doors. A committee meeting is flexible — anyone can raise
a motion to change the agenda — but it's slower, less predictable, and harder
to audit ("wait, why did we skip the risk assessment for *this* one?"). Equity
research on one ticker is always the same six steps in the same order; there's
no meaningful "flexibility" being paid for if you use a framework built for
open-ended, agent-decides-the-next-step workflows.

**What to build.** Plain `asyncio`, no agent-orchestration framework:

```python
# Phase 1: fan-out — four specialists genuinely run concurrently
fundamentals_result, risk_result, sentiment_result, technicals_result = \
    await asyncio.gather(
        Runner.run(fundamentals_agent, ...),
        Runner.run(risk_agent, ...),
        Runner.run(sentiment_agent, ...),
        Runner.run(technicals_agent, ...),
    )

overall_score = compute_overall_score(...)   # Phase 3 — code, not the model

# Phase 2: synthesis
draft = (await Runner.run(synthesizer_agent, combined_payload)).final_output
draft.overall_score = overall_score          # deterministic value wins

# Phase 3: bounded adversarial loop (the one place agency actually matters)
revision_count = 0
while True:
    critic_output = (await Runner.run(critic_agent, ...)).final_output
    if not critic_output.blocks_publication:
        break
    if revision_count >= settings.max_revisions:
        break                                 # publish anyway, flagged
    revision_count += 1
    draft = (await Runner.run(synthesizer_agent, revision_payload)).final_output
```

The **only** branch point in the entire pipeline is `blocks_publication` — a
typed boolean from the critic's schema (Phase 3), not a free-form decision an
LLM makes about *what to do next*. Everything else is a straight line.

Make the function an `async generator` (`yield` events instead of `return`ing
a final result) — this is what lets the API layer (Phase 11) stream progress
to the browser instead of making the user stare at a spinner for 35 seconds.

**Why this way, not another way.** LangGraph, CrewAI, and similar frameworks
are genuinely good tools — for graphs with dynamic routing, where the *next*
step depends on runtime decisions the graph itself needs to make. This
pipeline has exactly one such decision (does the critic block?), and
expressing that as `if critic_output.blocks_publication:` costs nothing extra
to write and nothing extra to debug. Adopting a framework here would mean
learning and carrying its abstractions (state channels, reducers,
checkpointers) to represent something that's actually a `gather()` and a
`while` loop — framework knowledge demonstrated, but not framework *judgment*
demonstrated, since the judgment call here is "this didn't need a framework."

**Why the loop has a hard bound.** An unbounded "keep revising until the
critic is happy" loop is a cost and latency hazard — a critic that's slightly
too strict (or a synthesizer that keeps making the same mistake) can loop
forever, and every iteration costs real money. `max_revisions` (default 2)
plus a `max_cost_usd` circuit breaker means the pipeline *always* terminates
and *always* publishes something — worst case, a report with unresolved
critic challenges attached and visible, which is still more useful to a
reader than no report at all.

**Verify it.** Run the pipeline against a real ticker end to end and print
each yielded event as it arrives — you should see the four specialist events
interleaved in whatever order they actually finish (not always the same
order — that's the proof they're genuinely parallel, not just concurrent-
looking), then synthesis, then at least one critic verdict.

---

## Phase 9 — Observability: the black box recorder

**Goal.** Every single agent call — specialist, synthesizer, critic, at every
revision — gets its own row in an `agent_runs` table: model, tokens in/out,
computed cost, latency, and the full structured output.

**Analogy.** An aircraft's flight data recorder. You hope you never need it —
but the difference between "the report cost $0.02" (a number you can state)
and "the critic call specifically cost $0.006 and took 1.9 seconds, and here
is exactly what it flagged" (a number you can *show*) is the difference
between claiming you operate a system and actually being able to prove it.

**What to build.** A thin wrapper around every agent call that captures
timing and usage in one place, so the pipeline (Phase 8) never has to repeat
this bookkeeping:

```python
@dataclass
class TracedRun:
    agent_name: str; phase: str; model: str; output: Any
    input_tokens: int; output_tokens: int; cost_usd: float; latency_ms: int
    ...

async def traced_run(agent, input_text, phase) -> TracedRun:
    t0 = time.perf_counter()
    result = await Runner.run(agent, input_text)
    usage = result.context_wrapper.usage
    return TracedRun(
        agent_name=agent.name, phase=phase, model=str(agent.model),
        output=result.final_output,
        input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
        cost_usd=estimate_cost_usd(str(agent.model), usage.input_tokens, usage.output_tokens),
        latency_ms=int((time.perf_counter() - t0) * 1000),
    )
```

Call `traced_run` (never `Runner.run` directly) everywhere in the pipeline,
and persist one `AgentRun` row per call. Sum the totals onto the parent
`ResearchReport` row so "what did this run cost" is a single indexed column,
not a query that has to aggregate every time.

**Why this way, not another way.** A managed LLM-ops product (Langfuse,
LangSmith) is a *better tool for iterating on prompts* — comparing prompt
versions across hundreds of runs — but it's an external dependency and an
external account for anyone standing up this project from scratch, and traces
living outside your own database means your own UI can't render them without
calling out to a third-party API. First-party tables cost about a day to
build and cover the actual product need (show the trace timeline in the
dossier) with zero new infrastructure. (This trade-off is explicit in
[ARCHITECTURE.md §9.6](ARCHITECTURE.md) — exporting to a dedicated tool later,
*in addition to* this, is a clearly-scoped future step, not a redo.)

**Verify it.** After one full pipeline run, query
`SELECT agent_name, phase, cost_usd, latency_ms FROM agent_runs WHERE report_id = ...`
— you should see exactly one row per agent call, including every revision
round, summing to the same total shown on the parent report.

---

## Phase 10 — Persistence: the filing cabinet

**Goal.** An Alembic migration that reshapes the database from "one table of
markdown blobs" to structured reports + traces + the RAG store (filings,
filing_chunks).

**Analogy.** Redesigning a filing cabinet from "one drawer, everything jammed
in as loose paper" to labeled folders — a `research_reports` folder, an
`agent_runs` folder cross-referenced to it, a `filings`/`filing_chunks`
folder for source material. You can *find* things now, and you can add a new
folder later (Phase 9's traces, added after reports already existed) without
reorganizing everything else.

**What to build.** A hand-written Alembic migration (not autogenerated,
because pgvector's `Vector` type and its HNSW index need explicit DDL
autogenerate doesn't know how to produce):

```python
def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    # ...structural changes to research_reports (JSONB report/critic columns)...
    op.create_table("agent_runs", ...)
    op.create_table("filings", ...)
    op.create_table(
        "filing_chunks",
        sa.Column("embedding", Vector(1536), nullable=True),
        ...
    )
    op.execute(
        "CREATE INDEX ix_filing_chunks_embedding_hnsw ON filing_chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )
```

Run it with `alembic -c backend/alembic.ini upgrade head`. Every SQLAlchemy
model in `backend/db/models.py` should match this migration exactly — the
models are what your Python code talks to; the migration is what actually
changes the database; they have to describe the same schema or you'll get
runtime errors that only show up when a specific column is touched.

**Why this way, not another way.** Autogenerating the migration
(`alembic revision --autogenerate`) is right for ordinary column changes but
blind to pgvector-specific DDL (the `Vector` column type, the HNSW index type,
the `vector_cosine_ops` operator class) — autogenerate would either skip them
silently or generate broken SQL. Writing this one migration by hand, once, is
cheaper than debugging a silently-wrong autogenerated one.

**Verify it.** `alembic -c backend/alembic.ini upgrade head`, then
`\d filing_chunks` in `psql` — confirm the `embedding` column is
`vector(1536)` and there's an `hnsw` index on it.

---

## Phase 11 — API layer: the waiter relaying the kitchen live

**Goal.** FastAPI routes: `POST /api/research/stream` (SSE), `GET /api/reports`
(history), `GET /api/reports/{id}` (detail with traces).

**Analogy.** A waiter who doesn't disappear into the kitchen and come back 35
seconds later with a finished plate — instead, walks over every few seconds:
"your appetizer's out," "the main course just started," "the chef sent it
back to be redone." Server-Sent Events is that waiter: one HTTP connection,
the server writes a new line whenever something happens, the browser reads
each line as it arrives.

**What to build.**

```python
@router.post("/research/stream")
async def research_stream(request: ResearchRequest):
    async def event_generator():
        async with AsyncSessionLocal() as db:
            async for event in run_research_pipeline_stream(request.ticker, db):
                yield f"data: {json.dumps(event)}\n\n"
            await db.commit()
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

Define every event's shape as you go (`{"type": "agent_completed", "agent":
"risk", "data": {...}, "usage": {...}}`, etc.) — this event protocol is a
contract the frontend (Phase 13) will implement a parser against, so write it
down (a table in DESIGN.md §6 is exactly this) before building the UI.

**Why SSE, not WebSockets or polling.** The data only flows one direction —
server tells browser what's happening; the browser never needs to push
anything mid-run. WebSockets buys bidirectional capability you don't use, at
the cost of connection-lifecycle complexity. Polling a status endpoint is
either laggy (long interval) or wasteful (short interval), and either way you
lose the fine-grained "this exact agent just finished" event — you'd only see
whatever the status was at the moment you happened to ask.

**A subtlety that will bite you if you skip it:** the pipeline (Phase 8) and
the RAG tool (Phase 6) use *different* database sessions (the tool opens its
own session per call, since specialist agents run concurrently and one
`AsyncSession` isn't safe to share across concurrent tasks). That means the
main pipeline's session must **commit** right after filing ingestion, before
the specialists start calling `search_filings` — otherwise the retrieval
tool's separate session can't see the just-inserted chunks, and you'll get
empty search results with no error message at all. This exact bug happened
during this build; the fix was two extra `await db.commit()` calls at
specific points in the pipeline, not a redesign.

**Verify it.** `curl -N -X POST localhost:8000/api/research/stream -d
'{"ticker":"NVDA"}'` and watch `data: {...}` lines arrive live in your
terminal, ending with the `complete` event.

---

## Phase 12 — Evaluation harness: two tiers of QA

**Goal.** `evals/` — deterministic checks that run free in CI on every push,
plus an opt-in LLM-as-judge tier over recorded fixtures.

**Analogy.** Spellcheck versus a second editor's read-through. Spellcheck is
instant, free, and catches a specific class of obvious error every time, with
zero judgment involved. A second editor reading the whole piece costs time
and is subjective, but catches things spellcheck structurally cannot — is the
argument actually well-supported, does the tone match the evidence. You want
both, and you don't want to pay for the second editor on every single
keystroke.

**What to build.**

*Tier 1 — deterministic, free, runs in CI:*
```python
def check_grounding(report_text: str, source_data: dict) -> GroundingResult:
    """Every number in the report must exist in the specialist data it came from."""
    report_numbers = extract_numbers(report_text)
    source_numbers = extract_numbers(json.dumps(source_data))
    violations = [n for n in report_numbers if not _matches(n, source_numbers)]
    return GroundingResult(checked=len(report_numbers), violations=violations)
```
Plus schema validation, verdict-consistent-with-score checks, and "a blocking
critic verdict must contain at least one high-severity challenge." All free,
all instant, all run on every `git push`.

*Tier 2 — LLM-as-judge, opt-in (costs real money):*
```python
async def judge_report(specialists: dict, report: dict) -> JudgeScores:
    """A separate model scores groundedness/completeness/actionability 1-5,
    against a rubric, over a GOLDEN FIXTURE — not live data."""
```

The critical design choice here is **golden fixtures**: record the actual
specialist output from one real pipeline run to a JSON file, check it into
the repo, and run the judge against *that*, forever, instead of against fresh
live data every time.

**Why golden fixtures, not live evals.** If you evaluate against live market
data, a score change between two CI runs could mean "the report got worse" or
could just mean "NVDA's price moved and the numbers are different now" — you
cannot tell which, so the eval is useless as a regression signal. A frozen
fixture means the input never changes, so if the judge's score changes, it's
because *your prompt or pipeline* changed — which is the only thing an eval
suite should be measuring.

**Verify it.** `uv run pytest evals -q` should pass in a few seconds with zero
API calls. `uv run pytest evals -m llm_eval -q -s` (explicit opt-in) should
cost about two cents and print a groundedness/completeness/actionability
score you can sanity-check by eye against the fixture's actual report text.

---

## Phase 13 — Tests: crash-test dummies, not the real car

**Goal.** `tests/` — pytest suite for the orchestrator and API that runs with
**zero LLM calls**, using scripted fake agent results.

**Analogy.** Crash-testing a car with dummies, not with actual passengers,
and not by driving the real car into a wall every time you change a bolt. You
build a rig that behaves *like* the real thing at the interface you care
about (a `TracedRun` with a made-up score) without paying for or depending on
the real thing (an actual OpenAI call) every time you run the suite.

**What to build.** A `ScriptedAgents` test double that returns canned
`TracedRun` objects instead of calling `Runner.run`, patched in via
`monkeypatch`:

```python
class ScriptedAgents:
    def __init__(self, critic_script: list[bool]):
        self.critic_script = list(critic_script)
    async def __call__(self, agent, input_text, phase):
        if agent.name == "CriticAgent":
            return make_traced_run(agent.name, phase, make_critic(blocks=self.critic_script.pop(0)))
        ...

async def test_revision_loop_is_bounded(db_session, monkeypatch):
    monkeypatch.setattr(
        "backend.pipeline.research.traced_run",
        ScriptedAgents(critic_script=[True] * 10),   # never approves
    )
    events = [e async for e in run_research_pipeline_stream("NVDA", db_session)]
    assert events[-1]["revision_count"] == settings.max_revisions  # loop actually stops
```

Run the whole suite against **SQLite in memory**, not real Postgres — with
one gotcha worth knowing in advance: use `StaticPool` (one shared connection)
because the pipeline does mid-run commits (Phase 11's subtlety), and SQLite's
default pooling would silently hand you a *different*, empty in-memory
database after a commit if you don't pin it to one connection.

**Why this way, not another way.** Testing against the real OpenAI API is
tempting because it's "the real thing," but it makes your test suite slow,
flaky (network + model non-determinism), and expensive to run on every push
— exactly the properties you don't want in the thing that's supposed to catch
regressions *before* they cost you anything. The scripted-agent approach
tests the part that's actually yours to get right (does the loop bound
correctly, does a failure mark the report `failed`, does the API return the
right shape) without re-testing "does OpenAI's API work," which is not your
code's job to verify.

**Verify it.** `uv run pytest tests -q` — should complete in a couple of
seconds, zero network calls (you can literally disconnect your network and
it'll still pass).

---

## Phase 14 — Packaging: the shipping container

**Goal.** `docker-compose.yml`, two `Dockerfile`s, and a GitHub Actions
workflow — so `docker compose up` reproduces the whole system anywhere, and
CI proves the tests aren't decorative.

**Analogy.** A shipping container. The contents (your app) don't change
based on which ship (developer laptop, CI runner, a cloud VM) carries them —
the container's job is to make the *outside* irrelevant.

**What to build.**

- `backend/Dockerfile`: multi-stage — a `uv sync --frozen` build stage, then
  a slim runtime stage that just copies the built `.venv` and source. Runs
  `alembic upgrade head` before starting `uvicorn`, so migrations are never a
  separate manual step in deploy.
- `frontend/web/Dockerfile`: Next.js `output: "standalone"` build — a
  `node_modules` install stage, a build stage, and a final stage that copies
  only the standalone server output (dramatically smaller image than shipping
  the full `node_modules`).
- `docker-compose.yml`: three services (`db`, `backend`, `frontend`), backend
  and frontend behind a `full` profile so `docker compose up -d db` alone is
  enough for local development against a locally-run backend/frontend.
- `.github/workflows/ci.yml`: on every push — `ruff check`, `pytest` (Tier-1
  evals + unit tests, no API key needed, using a dummy `OPENAI_API_KEY` env
  var since nothing in that suite actually calls out), `npm run lint`,
  `next build`.

**Why this way, not another way.** Kubernetes manifests are the "correct"
answer for running this at real multi-node scale — and true overkill for a
single-node demo whose whole point is that a reviewer can clone the repo and
run one command. Compose gets you 90% of "reproducible, one-command
environment" for a fraction of the operational surface area.

**Verify it.** `docker compose --profile full up --build` from a completely
clean checkout (no `.venv`, no `node_modules` — `git clean -xdf` if you want
to be sure) should give you a working app on `localhost:3000` with zero
manual steps beyond copying `.env.example` to `.env` and filling in an API
key.

---

## Phase 15 — Design the UI *before* building it

**Goal.** [DESIGN.md](DESIGN.md) — information architecture, a token system
(color/type/spacing), wireframes, and the streaming-state-machine table — all
written down before any React component exists.

**Analogy.** Architectural blueprints before construction. You don't lay
bricks and figure out where the doors go as you run out of wall — you decide
room layout, materials, and load-bearing walls on paper first, because
changing your mind after the foundation is poured is expensive in a way that
changing your mind on paper is not.

**What to build.** A design document with, at minimum:

1. **A design thesis** — one or two sentences that every subsequent choice
   has to serve. This project's: *the console is a machine room where agents
   work; the report is paper, an artifact you keep.* Every color, every
   animation choice traces back to reinforcing that split.
2. **A token system** — name every color, font, and spacing value *before*
   writing CSS, and justify the palette with more than taste: this project
   ran every candidate color through an automated validator (contrast, color-
   blindness-safe separation, lightness bands) rather than eyeballing it. See
   [DESIGN.md §2.1](DESIGN.md) for the actual method.
3. **Wireframes as ASCII art** — crude, fast, and just structured enough to
   argue about layout before writing a single `<div>`.
4. **An explicit event → UI-state table** — for a live, streaming interface
   specifically, write down every backend event (Phase 11) and exactly what
   changes on screen when it arrives, *before* writing the component that
   handles it. This becomes your state machine's spec.

**Why this way, not another way.** Skipping straight to component code is
faster for the first screen and slower for every screen after it — without a
written token system, the second component you write will quietly invent its
own spacing scale, and by the fifth component the UI has no consistent
rhythm, just five developers' (or five sessions') worth of individual
judgment calls that don't agree with each other. A design doc is where those
judgment calls get made *once*.

**Verify it.** Hand the design doc to someone who hasn't seen the app (or
re-read it yourself after a break) — they should be able to describe what the
running app looks like without having seen it, just from the doc.

---

## Phase 16 — Build the frontend from the design doc

**Goal.** The actual Next.js app: pages, components, the SSE-consuming state
machine — implementing DESIGN.md, not improvising past it.

**Analogy.** Now you lay the bricks — but you're building the exact rooms
from the blueprint, not making layout decisions on the fly.

**What to build, roughly in dependency order:**

1. **Scaffold + tokens.** `create-next-app` with TypeScript + Tailwind, then
   immediately translate DESIGN.md's token table into `globals.css` — CSS
   custom properties, mapped into Tailwind utilities via `@theme`/`@theme
   inline`, so every component references `bg-surface`/`text-text-muted`
   instead of a hardcoded hex.
2. **Types + event contracts.** `lib/types.ts` and `lib/events.ts` — hand-
   translate the Pydantic schemas (Phase 3) and the SSE event shapes (Phase
   11) into TypeScript interfaces. This is the frontend half of the same
   contract-first principle from Phase 3: define the shape before writing
   code that consumes it.
3. **The streaming state machine.** One `useReducer` hook
   (`useResearchStream.ts`) that owns all run state, fed by a single `fetch` +
   `ReadableStream` parser (SSE via `fetch`, not the native `EventSource` API
   — `EventSource` is GET-only and this is a POST with a body). Every SSE
   event type maps to exactly one reducer case, matching the table you wrote
   in DESIGN.md §5.
4. **Presentational components**, built bottom-up: `ScoreDial`, `VerdictChip`,
   `PillarBars` (pure, given props) before `Desk`/`Tape` (stateful, driven by
   the reducer) before the three pages (`/`, `/reports`, `/reports/[id]`) that
   assemble them.
5. **Pages.** The console (`page.tsx`) is a client component (it owns the
   live stream); the ledger and dossier are server components that `fetch`
   from the FastAPI backend at render time — no client-side data-fetching
   library needed for read-only history views.

**Why build bottom-up (tokens → types → state machine → leaf components →
pages), not top-down.** A page built before its components exist means either
placeholder code you'll delete, or premature decisions about a component's
API baked into the page that uses it before the component itself has been
thought through. Building the reducer before any component that reads from
it means the *state shape* gets decided once, deliberately, instead of
growing organically as an accumulation of whatever each component happened to
need.

**Verify it.** `npm run build` clean, then run a real research request
through the actual UI in a browser (not just curl against the API) — watch
the desk nodes go idle → working → done, the tape write events live, and the
paper report rise on completion. If you have Playwright or similar available,
screenshot every page — a build passing and a page rendering visually
correctly are different claims, and this project caught real bugs (see Phase
18) only by actually looking at screenshots, not just by a clean build.

---

## Phase 17 — First iteration: readability and brand

**Goal.** Respond to real feedback — "hard to read, very small," "use my
logo" — as a *design revision*, not a patch.

**Analogy.** A client walkthrough after the first coat of paint. You don't
repaint the whole house in a panic — you look at what's actually wrong (the
trim color reads muddy up close, one room's lighting is too dim), fix that
specifically, and note *why* in case someone asks later why the trim is a
different shade than the original plan.

**What changed, concretely:**

- **Type scale raised across the board**: 15px → 16px base, and every micro-
  label under 12px was bumped to a 13px floor. The fix was systematic (every
  component's text-size classes), not just "make the homepage bigger."
- **Secondary text brightened** for contrast, so de-emphasis comes from size
  and weight, not from dimming text below a comfortable reading contrast.
- **The provided logo integrated**: generated transparent web assets from the
  source PNG (strip the white matte with a soft alpha threshold, so there's
  no white halo on a dark background), placed in the nav inside a small
  neutral chip (so the logo's dark mark stays legible regardless of the
  surrounding background color — this detail mattered more once Phase 18
  added a light theme too).

**Why record this as a design-doc revision, not just a code diff.** DESIGN.md
got a "Rev 2" note at the top of its design-system section, explaining what
changed and *why* — future-you (or you, six months from now) looking at the
13px label floor should be able to find the reason ("user feedback: too
small") instead of wondering if it was arbitrary.

**Verify it.** Screenshot the same screen before and after, side by side —
"hard to read" is a claim you should be able to visually confirm you fixed,
not just assume.

---

## Phase 18 — Second iteration: a real theme system

**Goal.** Replace the color palette entirely and add a genuine light theme —
not just the report artifact (which was always light), the whole console
chrome too.

**Analogy.** A stage with colored lighting gels, not a different stage set for
day and night. The *set* — the component tree, the layout, the DOM structure
— never changes. Only the *lighting rig* (CSS custom properties) does, so
flipping a switch (the theme toggle) relights the whole scene without
rebuilding anything.

**What to build.**

1. **Design the palette twice, deliberately, not once and inverted.** A
   naive "invert the dark palette's lightness values for light mode" produces
   muddy, low-chroma colors. Instead: pick each mode's `bg`/`surface`/`text`
   values from scratch, from the *same brand hue family* (so the two modes
   read as one product, not two skins), and run **both** through the same
   automated color validator from Phase 15 — separately, against each mode's
   actual background, because a status color that passes contrast on a dark
   teal-charcoal background will not automatically pass on a light gray-green
   one.

2. **Decide what does *not* themed, and document why.** The report artifact
   ("the paper") stays the same warm color in both modes — like a PDF page
   staying white even in a dark-mode PDF reader. This wasn't an oversight;
   it's what keeps "the report rising off the desk" a *visible event* in both
   themes. (Considered and rejected: making light mode reuse the paper color
   for the whole chrome — it would have been free, but it collapses the
   desk/paper distinction that's the whole design thesis from Phase 15.)

3. **Semantic tokens, not a light/dark branch in every component.** Rewrite
   every hardcoded `bg-ink-900`/`text-ink-300` class to a semantic name
   (`bg-bg`, `text-text-muted`) whose *value* changes per theme, but whose
   *name* in the component code never does:

   ```css
   :root { --bg: #EDF1EE; --surface: #FFFFFF; /* light, default */ }
   @media (prefers-color-scheme: dark) {
     :root { --bg: #0B1615; --surface: #12211F; }
   }
   :root[data-theme="light"] { --bg: #EDF1EE; /* explicit override wins */ }
   :root[data-theme="dark"]  { --bg: #0B1615; }
   ```
   ```css
   @theme inline { --color-bg: var(--bg); --color-surface: var(--surface); }
   ```
   Now every component just writes `className="bg-bg"` — Tailwind resolves it
   through the CSS variable, which resolves through whichever selector
   currently matches. No component needs to know a theme system exists.

4. **A no-flash theme script, in the right place.** Reading `localStorage` to
   decide the theme has to happen *before* the page paints, or you get a
   flash of the wrong theme on every load. In Next.js's App Router, this
   means `next/script` with `strategy="beforeInteractive"`, written directly
   inside `app/layout.tsx` (not in a separate imported component — the
   framework's static analysis for this specific script strategy only
   recognizes it lexically inside the root layout file itself; a real
   mistake made and caught during this exact build).

**Why this way, not another way (a mistake worth learning from).** The first
attempt at the no-flash script placed it in a separate `ThemeScript.tsx`
component, rendered inside a manually-written `<head>` tag. It built cleanly,
lint passed, and it silently did nothing — Next's App Router doesn't reliably
render a hand-placed `<head>` element the way you'd expect from plain React,
so the script was dropped from the page entirely with no error. The bug was
invisible in the build output and only became obvious by *actually checking
the rendered HTML* (`curl localhost:3000 | grep theme-init`) and finding the
script simply wasn't there. The lesson generalizes past this one bug: a
successful build is not proof a specific runtime behavior works — check the
actual behavior, not just that compilation succeeded.

Also — and this one wasted real debugging time — **check what's actually
listening on the port before debugging your own code.** A leftover Docker
container from an earlier `docker compose up` was still bound to port 3000,
so every `npm start` afterward failed to bind and exited silently, while
`curl localhost:3000` kept returning 200 from the *stale* container the whole
time. The theme toggle looked broken for several iterations because the
"running" server wasn't the one being edited at all. `docker ps` /
`lsof -i :3000` first, always, before assuming the bug is in your code.

**Verify it.** Screenshot every page in both themes explicitly (don't trust
"it looks right in dev tools" — force `localStorage.setItem('finsight-theme',
'light')`, reload, screenshot; repeat for dark). Check that: text stays
readable in both, the report artifact looks identical regardless of desk
theme, and the theme choice survives a page reload.

---

## Phase 19 — Write it all down

**Goal.** ARCHITECTURE.md's Future Work section fully reasoned (not just a
bullet list), and this file — so the *next* person (or future-you) can trace
every decision back to a reason instead of reverse-engineering intent from
code.

**Analogy.** The building's as-built drawings, filed after construction — not
because anyone's required to read them, but because the day someone needs to
know why a wall is load-bearing, the alternative to having them is
demolition-by-guesswork.

**What to write, for each deferred feature:** not just *what* it is, but *why
it's not here yet* (a real constraint, not "ran out of time"), *what it would
take* concretely, and *what would have to be true* for it to become worth
building. "Multi-provider LLM failover" isn't skipped because it's hard —
it's skipped because it solves a reliability problem this single-operator
system doesn't have yet, at a real ongoing cost (every agent's behavior
becomes provider-specific until proven otherwise). Writing that down is what
turns "we didn't do X" into a decision someone can agree or disagree with,
instead of a mystery.

**Verify it.** Same test as Phase 1's ADRs: read it cold, a day later. If a
Future Work item just says what it is without saying why it's deferred, it's
not finished.

---

## What to do differently on your own pass

A few things, in hindsight, worth deciding *before* you hit them rather than
after:

1. **Decide the desk/paper (or your own surface metaphor) split before
   touching color values.** Adding a light theme after the fact meant
   retrofitting a distinction (what's *always* paper-colored vs. what
   *follows the theme*) that would have been a five-minute decision if made
   up front, instead of a design conversation after the first palette already
   shipped.
2. **When something silently doesn't work (a script that doesn't run, a tool
   returning empty results), check the actual runtime state before changing
   code.** Two real bugs in this build (the `<head>`-placed script being
   dropped, the stale Docker container squatting on port 3000) cost more time
   *looking in the wrong place* than they would have cost to fix, once found.
   `curl` the actual HTML. `docker ps` the actual containers. Don't assume the
   thing you just edited is the thing that's running.
3. **Write the rubric/schema/contract before the prompt that fills it.**
   Every time a schema got tightened *after* an agent's instructions were
   already written loosely (e.g., "cite filing passages" without "you MUST
   include at least 2 citations if search_filings returned results"), the
   fix was a second pass. Writing the strict version first is the same amount
   of work and skips the second pass.
