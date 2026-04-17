# LLM-Derived Prediction Markets — Design

## Problem

Every production sim hits `MarketConfig(markets=[])` because `infra/docker/run_job_v2_runner.py:80` passes `params={}` to the market env. The `buy_shares` / `sell_shares` tools are still exposed to the LLM, so agents hallucinate market_ids, the env rejects them with `"Market not found"`, and the UI renders `NaN% / $NaN` in the Trades panel. Fix: derive a small list of prediction markets from the user's goal *before* the sim starts, and seed the env with them.

## Non-goals

- No changes to the AMM math (constant-product is fine).
- No changes to `extract_market_data` or `TradeFeed.vue` — the 2026-04-17 trade-schema work already handles display.
- No resolution/settlement logic. Markets stay open for the duration of the sim; no "winner" is declared.
- No market curves redesign. `market_curves.json` already plots price movement per market.

## Where it fits in the job lifecycle

New step **between job creation and GPU provisioning**, running in Celery on CPU:

```
create_job (API, credits debited)
  └─ enqueue run_simulation_task
      ├─ [existing] enrich_seed_with_web (if enrich_web=True)
      ├─ [NEW]      derive_markets_from_goal      ← this spec
      ├─ [existing] provision GPU pod
      └─ [existing] pod runs sim, uploads artifacts
```

Derivation always runs. It assumes enrichment has run (the user-facing `enrich_web` toggle is being deprecated — see [Decisions](#decisions) below — so every sim has an enriched seed). Derivation produces a list of market dicts that the pod receives via the existing job-params channel.

## LLM contract

**Model:** Grok (xAI) via the same client used for enrichment, or Claude via `smart_llm`. Either is fine; pick whichever is already wired into the Celery worker with credentials — don't introduce a new provider. Leaning Grok since enrichment is already Grok-heavy and the prompt is web-flavored.

**Prompt structure:**

```
System: You are a prediction market designer for an agent-based
simulation. Given a user goal, derive 3–5 binary (YES/NO) markets
that collectively capture the resolution space of that goal.
Markets should be mutually informative (not trivially redundant),
have clear resolution criteria, and be phrased in <=120 chars.

User goal: {goal}
Seed context: {enriched_seed or seed}
Tier: {tier}  # small=3 markets max, medium=4, large=5

Return JSON:
{
  "markets": [
    {"question": "...", "initial_price_yes": 0.50, "rationale": "..."},
    ...
  ]
}
```

**Output validation:**
- Must be a JSON object with key `markets` as a non-empty list.
- Each market: `question` (str, 1–120 chars, non-empty), `initial_price_yes` (float in [0.05, 0.95] — no 0/1 edges, those break the AMM), optional `rationale` (str, persisted for UI).
- Reject duplicates (case-insensitive question hash).
- If fewer than 1 valid market parses → **fallback**: a single market with `question=goal, initial_price_yes=0.5`.

**Timeout:** 20s per call. Retry once on transient failure; fall back to single-market on persistent failure. No job failure — derivation is best-effort.

## Storage

Add to `SimulationJob` model a nullable JSON column:

```python
markets_config: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
```

Migration: `alembic revision --autogenerate -m "add markets_config to simulation_jobs"`.

Persist the derived list (validated form, not raw LLM output). Include `derivation_source`: `"llm"` | `"fallback_goal"` | `"fallback_single"` so we can QA.

## Pod wiring

`infra/docker/run_job_v2.py` currently pulls the job row. Extend the worker → pod handoff (the job env / args passed when enqueuing the GPU task) to include `markets_config`. In `run_job_v2_runner.py:run_simulation`, replace:

```python
EnvironmentConfig(type="market", params={})
```

with:

```python
EnvironmentConfig(type="market", params={
    "markets": [
        {"question": m["question"],
         "initial_price_yes": m.get("initial_price_yes", 0.5)}
        for m in (markets_config or [])
    ] or [{"question": goal, "initial_price_yes": 0.5}],
}),
```

The `or [...]` tail is a belt-and-suspenders fallback in case the upstream derivation somehow emitted an empty list past validation.

## API / UI surface

**In v1:** show the derived market list on the job detail page, including the `rationale` per market so users understand why agents were trading on those specific questions. Compact card/list in the data tab, near the Trades panel. Shape (from the `GET /jobs/{id}` response, added):

```json
"markets_config": [
  {"question": "...", "initial_price_yes": 0.50, "rationale": "..."}
]
```

Minimal Vue component (`MarketsList.vue` or similar) in `frontend/src/components/data/`, rendered alongside `TradeFeed.vue`. Same dark ocean styling as the other data panels.

**Wizard-time preview (out of scope):** letting users see/edit markets *before* confirming the sim would need derivation to run at draft-save time with its own endpoint. Separate feature, not addressed here.

## Tier-specific caps

From `saas/constants/tiers.py`:
- `small` → max 3 markets
- `medium` → max 4 markets
- `large` → max 5 markets

Cap enforced by the prompt and a post-validation slice (`markets[:cap]`). Rationale: more markets = more diffuse trading, and small sims only have 15 rounds × ~4 agents = 60 agent-turns total. Three markets gives enough choice without starving any one of them.

## Cost

- One extra LLM call at derivation. Grok `grok-2` ~\$2/M input, ~\$10/M output. Prompt is ~500 tokens in, ~400 tokens out per market × 5 = ~2.5K out for the worst case. Round-trip: **<\$0.03 per sim**, typically <\$0.01.
- No additional GPU time (derivation is CPU-only on the Celery worker).

## Failure modes + mitigations

| Failure | Mitigation |
|---|---|
| LLM returns malformed JSON | Retry once; fall back to single-market (`question=goal`) |
| LLM emits unresolvable / opinion markets ("Is X good?") | Accept them — resolution isn't enforced anyway, and agent trading still produces signal |
| `initial_price_yes` = 0 or 1 | Clamp to [0.05, 0.95] during validation |
| Duplicate market questions | Dedupe case-insensitively during validation |
| Tier cap exceeded | Slice to cap after dedupe |
| Grok rate-limited / down | One retry with exponential backoff; fall back to single-market |
| Derivation timeout >20s | Kill and fall back |

In every failure case, the sim **still runs** with at least one market. A noisy log line (`markets.derivation_failed: <reason>`) goes to the existing Celery logging so operators can spot systematic issues.

## Test plan

- Unit: given a fixture goal + seed, `derive_markets_from_goal` returns a validated list of 3 markets (using a stubbed LLM client).
- Unit: malformed LLM output → returns fallback single-market.
- Unit: LLM returns 7 markets → result sliced to tier cap.
- Unit: LLM returns a market with `initial_price_yes=1.0` → clamped to 0.95.
- Integration: end-to-end through `create_job → run_simulation_task → run_job_v2_runner.run_simulation` — assert `MarketConfig.markets` has the derived list.
- Prod smoke: one small sim with a Fed-rate-cut seed → trades.json non-empty, all entries have `success=True`, Trades panel renders real `$NN` and `NN%` (no NaN).

## Decisions

These started as open questions and were resolved before plan-writing.

1. **Enrichment is mandatory.** The user-facing `enrich_web` toggle is being deprecated — every sim runs enrichment. Market derivation assumes the enriched seed is always available. Deprecating the toggle itself (API field, wizard UI, DB column) is a **separate piece of work**, not in this spec's scope, but derivation is designed against the post-deprecation world. Until that lands, derivation falls back to the raw seed if `enrich_web=False`.
2. **Show `rationale` in UI from v1.** Persist it and render it next to each market question in a new `MarketsList.vue` component on the job detail page. No separate v2.
3. **Cross-sim market continuity — deferred to "fork sim."** Markets get fresh UUIDs per sim, so there's no stable identity across runs. This is fine for now; the use case (comparing the same market across runs with tweaked inputs) lives under a larger future feature called **fork sim**. No action in this spec beyond leaving the UUID-per-run design as-is.
4. **Agent ↔ market coupling:** emergent only. Agents see markets via `browse_markets` and trade based on the LLM reading their persona alongside the market question. No explicit persona-to-market bias wiring.
5. **Resolution / winner determination:** deferred. Markets stay open for the duration of the sim; no YES/NO is declared at the end. The report describes price trajectories without requiring resolution. Revisit once derivation has been in prod for a while.

## Estimated effort

- 1 new module: `saas/jobs/market_derivation.py` (~150 LoC including prompt + validation).
- 1 small Alembic migration.
- 1 `SimulationJob` model change.
- 2 edits: `run_simulation_task` to call the deriver; `run_job_v2_runner.run_simulation` to read and pass to env.
- 1 new Vue component: `frontend/src/components/data/MarketsList.vue` + wiring into the data tab.
- `GET /jobs/{id}` response extended to include `markets_config`.
- ~6 unit tests + 1 integration test + 1 frontend vitest + 1 prod smoke.
- Total: ~day with review.

---

*Related:* [2026-04-17 trade-execution-results plan](/docs/superpowers/plans/2026-04-17-trade-execution-results.md) — that work fixed the rendering schema but can't show real data while markets stay empty. This spec closes that loop.
