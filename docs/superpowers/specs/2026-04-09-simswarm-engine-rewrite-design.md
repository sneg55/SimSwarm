# SimSwarm Engine — Clean-Room Rewrite Design Spec

**Date:** 2026-04-09
**Status:** Draft
**Scope:** Exploratory spec — no implementation timeline committed

## Motivation

The current simulation engine (MiroShark, forked from MiroFish) is ~37K LOC across 130 files. It works, but three problems motivate a rewrite:

1. **Technical debt:** Heavy CAMEL-AI dependency makes the LLM interaction loop opaque. Debugging agent behavior means tracing through framework internals we don't control.
2. **Unnecessary complexity:** Dual social platforms (Twitter + Reddit separately), 37 SQL schema files, scattered prompts across 15+ files, TwHIN-BERT embedding model for feed ranking. Much of this is inherited from upstream MiroFish and not load-bearing for SimSwarm's product.
3. **Architecture limits:** Flask + subprocess + per-sim SQLite doesn't scale. IPC overhead for progress updates, no shared state, subprocess spawning complexity. The architecture fights the product direction (scenario sweeps, economic simulation, structured policy inputs).

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Language | Python | Engine is a library imported by the Python Celery worker. LLM calls are I/O-bound; async Python handles this fine. One language for the full stack. |
| Runtime model | Library (no server, no subprocess) | `await engine.run(config)` inside the Celery worker. Simplest integration. GPU pods are ephemeral and run one sim — crash isolation is moot. |
| Approach | Clean-room rewrite, informed by MiroShark | ~90% new code. Reference MiroShark for proven logic (AMM math, belief heuristics, effective prompts) but don't copy structure. |
| Name | SimSwarm | Engine and product share identity. No MiroFish lineage. |

## Architecture Overview

Three layers:

```
┌─────────────────────────────────────────────┐
│                 SaaS Layer                  │
│  (FastAPI, Celery, Postgres, Neo4j, MinIO)  │
├─────────────────────────────────────────────┤
│              SimSwarm Engine                 │
│  ┌─────────┐  ┌──────────┐  ┌───────────┐  │
│  │  Core   │  │  Agent   │  │  Report   │  │
│  │  Loop   │  │ Runtime  │  │  Module   │  │
│  └────┬────┘  └─────┬────┘  └───────────┘  │
│       │             │                       │
│  ┌────┴─────────────┴────────────────────┐  │
│  │           Environments                │  │
│  │  Social │ Market │ Economic │ Custom  │  │
│  └──────────────────┬────────────────────┘  │
│                     │                       │
│  ┌──────────────────┴────────────────────┐  │
│  │      Cross-Environment Bridge         │  │
│  └───────────────────────────────────────┘  │
├─────────────────────────────────────────────┤
│              LLM Client                     │
│  (direct vLLM /v1/chat/completions calls)   │
└─────────────────────────────────────────────┘
```

### Entry Point

```python
from simswarm import Engine, SimulationConfig, ScenarioSweep

engine = Engine()

# Single run
result = await engine.run(config, on_progress=callback)

# Sweep across variable combinations
sweep = ScenarioSweep(base_config=config, vary={...})
results = await engine.run_sweep(sweep, on_progress=callback)
```

## Core Loop

Orchestrates simulation rounds. Each round:

1. **Observe** — each environment generates personalized observations per agent
2. **Step** — batch LLM calls for all agents (gated by concurrency semaphore)
3. **Execute** — dispatch agent actions to their target environments
4. **Update** — environments process actions, update internal state
5. **Bridge** — environments publish events, bridge distributes digests
6. **Snapshot** — capture round metrics for trajectory analysis
7. **Check termination** — max rounds reached, or convergence detected

The loop is pure async. Concurrency is controlled via semaphore (configurable, default 32 concurrent LLM calls).

## Agent Runtime

Each agent is a lightweight dataclass — no framework inheritance.

```python
@dataclass
class Agent:
    id: str
    name: str
    persona: str              # LLM system prompt (generated from entity)
    environments: list[str]   # which environments this agent participates in
    belief_state: BeliefState
    memory: RingBuffer        # sliding window of recent observations/actions
    config: AgentActivityConfig
```

### LLM Interaction

One function, no class hierarchy:

```python
async def agent_step(agent, observations, tools) -> list[Action]:
    messages = build_context(agent, observations)
    response = await llm_client.chat(messages, tools=tools)
    return parse_tool_calls(response)
```

Context is assembled per-step from: persona (static) + belief summary (updated per round) + cross-environment digest + current observations. Total context budget capped (configurable, default 16K tokens). Older memory evicted when budget exceeded.

### Belief State

Ported from MiroShark — proven math, heuristic updates, no LLM calls for belief evolution.

- **Positions:** topic -> float [-1.0, +1.0]
- **Confidence:** topic -> float [0.0, 1.0]
- **Trust:** agent_id -> float [0.0, 1.0]
- **Exposure history:** set of content hashes (dedup, capped at 2,000)

Update logic per round:
1. Read posts from feed, estimate stance via keyword matching
2. Weight by author trust * social proof * novelty multiplier
3. Resistance formula: high-confidence agents resist change more
4. Engagement feedback: likes increase confidence, dislikes decrease

### Tool Calling

Each environment registers its actions as OpenAI function-calling tools. Agents see only tools for their subscribed environments. vLLM with `--enable-auto-tool-choice --tool-call-parser hermes` handles structured tool responses natively.

### Concurrency

Agents step in parallel within a round, gated by semaphore. Round doesn't advance until all agents complete.

## Environments

Pluggable simulation spaces where agents act.

```python
class Environment(Protocol):
    name: str

    def get_observations(self, agent: Agent) -> Observation: ...
    def execute_action(self, agent: Agent, action: Action) -> ActionResult: ...
    def get_tools(self) -> list[Tool]: ...
    def publish_events(self) -> list[Event]: ...
    def tick(self) -> None: ...  # end-of-round state updates
```

### SocialEnvironment

Unified social platform — replaces separate Twitter + Reddit implementations. Configurable features:

| Feature | Options | Default |
|---------|---------|---------|
| Threading | on / off | on |
| Voting | likes-only / upvote-downvote | likes-only |
| Feed algorithm | recency, popularity, relevance weights | balanced |
| Echo chamber strength | 0.0 - 1.0 | 0.5 |
| Viral threshold | interaction count | 5 |

**Actions:** `create_post`, `reply`, `vote`, `repost`, `follow`, `do_nothing`

**Observation:** Personalized feed — ranked posts from followed agents + algorithmic recommendations. Feed ranking uses a weighted scorer (recency * w1 + popularity * w2 + relevance * w3). No TwHIN-BERT — embedding similarity was overkill and added a model dependency.

### MarketEnvironment

Prediction markets with constant-product AMM. Logic ported from MiroShark's Polymarket implementation (~1K LOC).

- Supports **multiple markets** per simulation (MiroShark only supported one)
- Price_YES = reserve_NO / (reserve_YES + reserve_NO)
- Buy: mint complete sets, swap unwanted outcome back
- Sell: split shares, swap to pool, burn complete sets

**Actions:** `buy_shares`, `sell_shares`, `comment_on_market`, `browse_markets`, `do_nothing`

**Observation:** Market prices, volume, recent trades, own portfolio.

### EconomicEnvironment (new)

Agents represent economic actors (firms, workers, investors, policymakers) in a simplified economy. This is the grant-enabling environment.

**Actions:** `set_price`, `hire`, `fire`, `invest`, `allocate`, `apply_policy`, `do_nothing`

**Observation:** Market conditions (prices, employment, demand), own balance sheet, active policies.

**State:** Tracks aggregate metrics (employment rate, price levels, output, inequality measures) updated each round via **rule-based formulas** — not LLM calls. Agent actions (hire, set_price, invest) feed into configurable economic update functions that compute next-round state deterministically. Example: total employment = sum of all firm hiring minus firing, price level = weighted average of firm prices. This keeps the economic tick fast and reproducible. The formulas are the part the grant work would flesh out — v1 ships with simple aggregation.

Policy variables injected via scenario config and visible to all agents as structured observation data.

### Cross-Environment Bridge

First-class pub/sub event system. Environments publish events after each round. The bridge collects and injects digests into agent observations:

- Market price moves -> social agents see price context
- Viral social posts -> market agents see sentiment context
- Policy changes -> all agents see policy context

Agents opt into environments at creation time. Multi-environment agents get observations and tools from all their environments.

## Scenario Configuration & Sweep

### SimulationConfig

Two layers of configuration:

```python
@dataclass
class SimulationConfig:
    # Seed layer — what to simulate
    seed_text: str
    goal: str
    entities: list[Entity]
    enrichment: dict | None

    # Scenario layer — how to simulate it
    environments: list[EnvironmentConfig]
    agent_configs: list[AgentConfig] | None  # None = auto-generate from entities
    rounds: int
    concurrency: int  # max parallel LLM calls

    # Policy/variables layer — what to vary
    variables: dict[str, Any]
    scheduled_events: list[ScheduledEvent]
```

### Variables

Named parameters injected into agent context as structured data:

```python
variables = {
    "wealth_fund_size": 2_000_000_000_000,
    "distribution_model": "cash",
    "portfolio_strategy": "equity_heavy",
    "displacement_timeline": "aggressive",
}
```

Agents see these as explicit parameters in their observations, not buried in prompt text.

### Scheduled Events

Policy shocks injected at specific rounds:

```python
ScheduledEvent(round=10, type="policy_change", data={"action": "fund_distributes", "amount": "50B"})
```

### Scenario Sweep

First-class concept for parameter variation:

```python
sweep = ScenarioSweep(
    base_config=config,
    vary={
        "portfolio_strategy": ["equity_heavy", "supply_side", "balanced"],
        "displacement_timeline": ["gradual", "aggressive", "moderate"],
    },
)
# Generates 3x3 = 9 simulation runs
results = await engine.run_sweep(sweep, on_progress=callback)
```

All runs in a sweep share seed, entities, and agent configurations. Only variables differ. This makes cross-run comparison meaningful.

## LLM Integration

No framework. One async client.

```python
class LLMClient:
    def __init__(self, base_url: str, model: str, api_key: str = "none"):
        self.session = aiohttp.ClientSession()
        self.base_url = base_url
        self.model = model

    async def chat(self, messages, tools=None, temperature=0.7) -> LLMResponse:
        # POST /v1/chat/completions — OpenAI-compatible
        # Retries on 429/503 with exponential backoff
```

**Two instances per simulation:**
- **Fast client** — agent steps (vLLM on GPU pod, high throughput, lower temperature)
- **Smart client** — config generation, report writing (external model like Grok or GPT-4)

**Prompt templates** centralized in `prompts/` directory using Jinja2:
- `agent_system.j2` — agent persona
- `agent_observation.j2` — per-round context
- `config_generation.j2` — auto-generate simulation parameters from seed
- `report.j2` — report agent instructions

## State & Storage

### During Simulation

**Small/medium sims (<=50 agents, <=200 rounds):** All state in-memory as Python dataclasses.

```python
@dataclass
class SimulationState:
    round: int
    agents: dict[str, Agent]
    environments: dict[str, Environment]
    events: list[Event]
    snapshots: list[RoundSnapshot]
```

**Large sims (1000+ agents or 1000+ rounds):** Active round state in memory, completed rounds flush to append-only Parquet files on disk. Trajectory aggregates computed incrementally.

```python
@dataclass
class EngineConfig:
    flush_interval: int = 10       # flush completed rounds to disk every N rounds
    checkpoint_interval: int = 50  # full state checkpoint every N rounds
    max_memory_rounds: int = 20    # keep only last N rounds in memory for agent context
```

Memory estimate for large sims: ~50MB active state + streaming disk writes. Parquet compression (~10:1) keeps disk manageable.

### Progress Reporting

Via callback — the SaaS passes `on_progress` callable. Engine invokes it each round with round number, agent count, and key metrics. Celery worker writes to DB via sync psycopg2.

### After Simulation

Engine returns a `SimulationResult`:

```python
@dataclass
class SimulationResult:
    report_input: ReportInput
    chat_log: list[ActionRecord]
    graph_data: GraphSnapshot
    trajectories: SimulationTrajectory
    market_data: list[MarketSnapshot] | None
    raw_state: SimulationState
```

The SaaS layer handles persistence (Postgres, MinIO, Neo4j). The engine doesn't know about those systems.

### Checkpointing

For long runs, engine serializes `SimulationState` to JSON at configurable intervals. If a spot instance is preempted, SaaS restarts with `start_from_state` to resume.

Mandatory for large sims — spot preemption over multi-day runs is near-certain.

## Knowledge Graph

Neo4j integration moves **outside the engine**.

**Before simulation (SaaS layer):**
1. Seed document -> entity extraction -> Neo4j storage
2. Query Neo4j for entities + relationships
3. Pass to engine as `list[Entity]` in config

**During simulation (engine):**
- Agents generated from entities (persona generation, multi-perspective allocation)
- No Neo4j reads or writes
- Engine tracks emergent relationships (influence, coalitions, trust networks)

**After simulation (SaaS layer):**
- Engine returns `GraphSnapshot` with original entities + emergent relationships + updated scores
- SaaS writes enriched graph back to Neo4j
- Frontend renders via Cytoscape.js

Entity extraction and graph building logic (ontology generation, NER, deduplication) stays in the SaaS layer. It's pre-processing, not simulation logic.

## Report Generation

Lean module (~500 LOC) replacing MiroShark's 3,200-line monolith.

```python
async def generate_report(result: SimulationResult, llm: LLMClient) -> Report:
```

The report agent receives `SimulationResult` and has tool access:

| Tool | Purpose |
|------|---------|
| `get_trajectory(topic)` | Belief/sentiment curves over time |
| `get_coalitions()` | Agent clusters by stance |
| `get_market_history(market_id)` | Price/volume over rounds |
| `get_top_posts(sort_by, limit)` | Most viral/influential content |
| `get_agent_summary(agent_id)` | One agent's journey |
| `compare_scenarios(variable)` | Diff outcomes across sweep runs (new) |

Multi-turn ReACT pattern: read data via tools, write sections, read more, refine.

**Output:**

```python
@dataclass
class Report:
    executive_brief: str
    findings: list[Finding]
    coalitions: list[Coalition]
    confidence_grid: dict[str, float]
    scenario_comparison: dict | None  # populated for sweep runs
    raw_markdown: str
```

`compare_scenarios()` is new — surfaces how outcomes differed across sweep variable combinations. This is the grant deliverable.

## What Gets Dropped

| Dropped | Reason |
|---------|--------|
| CAMEL-AI | Opaque LLM loop. Replaced by direct vLLM calls. |
| Flask | Engine is a library, not a server. |
| Subprocess spawning | Library runs in-process. |
| Dual social platforms | Merged into one configurable SocialEnvironment. |
| 37 SQL schema files | In-memory state + Parquet for large sims. |
| TwHIN-BERT embeddings | Weighted scorer is sufficient for feed ranking. |
| Scattered prompts | Centralized Jinja2 templates. |
| Zep Cloud remnants | Dead code from upstream MiroFish. |

## What Gets Ported (reference, not copy)

| Component | Source | Notes |
|-----------|--------|-------|
| Belief state math | `belief_state.py` | Heuristic update formulas, resistance curves |
| AMM pricing | `polymarket/` | Constant-product invariant, buy/sell mechanics |
| Multi-perspective agent generation | `simulation_config_agents.py` | LLM-driven entity -> multiple agent personas |
| Effective prompts | Various | Agent persona templates, report instructions |
| Cross-platform bridge concept | `cross_platform_digest.py`, `market_media_bridge.py` | Generalized into pub/sub event system |

## Estimated Scope

| Component | Estimated LOC |
|-----------|---------------|
| Core loop | ~500 |
| Agent runtime + belief state | ~800 |
| LLM client | ~200 |
| SocialEnvironment | ~1,000 |
| MarketEnvironment | ~600 |
| EconomicEnvironment (v1) | ~500 |
| Cross-environment bridge | ~300 |
| Scenario config + sweep | ~400 |
| Report module | ~500 |
| State management + checkpointing | ~400 |
| Prompt templates | ~300 |
| Tests | ~2,000 |
| **Total** | **~7,500** |

Down from MiroShark's ~37K LOC — 80% reduction.

## Testing & Migration Safety

The SaaS layer is cleanly decoupled from MiroShark at the HTTP boundary (worker API on the GPU pod). The tight coupling is only in `infra/docker/run_job.py`, which imports MiroShark service classes directly. This is the single seam where the engine swap happens.

### Layer 1: Contract Tests (write before any rewrite)

Define the exact contract between SaaS and engine as a test suite. These tests don't care which engine runs — they verify inputs and outputs.

**HTTP contract** (worker API):
- POST `/job` accepts `{seed_text, goal, max_rounds, forecast_days, target_agents, upload_urls}`
- GET `/status` returns `{status, report, chat_log, graph_data, structured}`
- Status values: `idle` → `running` → `completed` / `failed`

**Result shape contract** (schema validation):
- `report` is valid markdown string, non-empty
- `chat_log` is JSON list where each item has `agent_id`, `agent_name`, `action_type`, `round_num`
- `graph_data` is JSON with `nodes` (each has `id`, `label`, `type`), `edges` (each has `source`, `target`), `metadata`
- `structured` has `executive_brief`, `findings`, `coalitions`, `confidence_grid`

Run these against MiroShark output now, then against SimSwarm output later. Both must pass.

### Layer 2: Golden File Tests (capture before rewrite)

Run 3-5 representative simulations on MiroShark and save full outputs as golden files:
- A small sim (5 agents, 15 rounds)
- A medium sim with prediction market
- A sim with web enrichment
- A sim with high agent count

Save: chat_log, graph_data, structured results, trajectory data. These become regression baselines. The new engine doesn't need identical output, but:
- Same entity types should appear in the graph
- Belief trajectories should show similar dynamics (convergence, polarization)
- Market prices should respond to sentiment (not random walk)
- Report should contain findings, coalitions, confidence grid

These are behavioral smoke tests — reviewed by eye, not exact-match asserts.

### Layer 3: Engine Test Suite (write alongside the new engine)

The new SimSwarm engine gets its own test suite, structured by component:

| Component | What to test | How |
|-----------|-------------|-----|
| Core loop | Round sequencing, termination, concurrency | Unit test with mock environment + mock LLM |
| Agent runtime | Context assembly, memory eviction, tool parsing | Unit test with canned LLM responses |
| Belief state | Position updates, trust decay, confidence resistance | Pure math — unit test with known inputs/expected outputs |
| SocialEnvironment | Feed ranking, post creation, voting, threading | Unit test environment in isolation |
| MarketEnvironment | AMM pricing, buy/sell, portfolio tracking | Unit test with known trades → expected prices |
| Cross-env bridge | Event publishing, digest formatting | Integration test with two mock environments |
| Scenario sweep | Config generation, variable substitution, result keying | Unit test combinatorics |
| LLM client | Retry logic, tool call parsing, error handling | Unit test with httpx mock |
| Checkpointing | Serialize → deserialize → resume produces same state | Round-trip test |

**Key principle:** Belief math and AMM pricing are the only components that need exact numerical parity with MiroShark. Everything else is behavioral.

### Swap Strategy

Migration happens at one seam: `run_job.py`.

| Phase | What | Risk |
|-------|------|------|
| 1 | Write contract + golden file tests against MiroShark | None — observation only |
| 2 | Build SimSwarm engine with its own test suite | None — parallel development |
| 3 | Write new `run_job.py` that imports SimSwarm, outputs to same file paths in same formats | None — not deployed yet |
| 4 | Run both engines on same inputs, compare outputs (shadow mode) | None — comparison only |
| 5 | Swap — new Docker image with SimSwarm, MiroShark removed | Low — contract tests gate deployment |

The SaaS layer, frontend, Celery tasks, GPU provisioning — none of this changes. The worker API stays the same. Only the engine inside the pod swaps.
