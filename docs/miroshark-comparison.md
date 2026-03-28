# MiroShark vs MiroFish — Comparison Report

**Date:** 2026-03-28
**Source:** https://github.com/aaronjmars/MiroShark (created 2026-03-20, 319 stars, AGPL-3.0)

## What MiroShark Is

MiroShark is a very recent fork (created 2026-03-20) by `aaronjmars` with 319 stars already. It builds on MiroFish + MiroFish-Offline and adds several significant features. Same AGPL-3.0 license.

---

## Key Differences

| Area | Our MiroFish (vendor/) | MiroShark |
|------|----------------------|-----------|
| **Platforms** | Twitter + Reddit (dual) | Twitter + Reddit + **Polymarket** (triple) |
| **Graph Storage** | Zep Cloud (hosted API) | **Neo4j** (self-hosted) + Ollama embeddings |
| **Belief Tracking** | None — agents are stateless between rounds | **BeliefState system** — stance, confidence, trust per agent |
| **Memory** | Full context each round (prompt blowup risk) | **Sliding-window round memory** with LLM summarization |
| **Cross-platform data flow** | Independent platforms | **MarketMediaBridge** — sentiment feeds market, prices feed social |
| **Web Enrichment** | None | Auto-researches public figures via Perplexity/OpenRouter |
| **Report Generation** | ReACT agent with Zep tools | ReACT agent with **market state + belief trajectory** tools |
| **Model Routing** | Single model | **Smart dual-tier** — strong model for reasoning, cheap for bulk |
| **LLM Providers** | OpenAI-compatible API | Same + **Claude Code CLI** as provider (uses Pro/Max subscriptions) |
| **Performance** | Sequential graph writes | **Batched UNWIND Neo4j writes** (10x), parallel chunk processing (3x) |
| **Backend** | Flask | Flask (same) |
| **Frontend** | Vue 3 + D3.js | Vue 3 + D3.js (same base, "Hyperstitions" UI overhaul) |

---

## Features Worth Adopting (ranked by impact)

### 1. Belief State System — HIGH IMPACT

Each agent tracks stance (-1 to +1), confidence (0-1), and trust in other agents (0-1). Updates are **heuristic** (no LLM calls), so it's cheap. This gives simulations emergent opinion dynamics — agents genuinely change their minds based on who they trust and what arguments they encounter.

**Why it matters for FishCloud:** Our target users (marketers, strategists) care about *how* opinions shift, not just final state. Belief trajectories make reports dramatically more insightful — "Agent-47 shifted from -0.8 to +0.3 after round 5 exposure to Agent-12's argument" is a concrete, citable finding.

**Effort:** Medium. Heuristic math is simple; the work is integrating it into the OASIS agent loop and exposing trajectories in reports.

### 2. Sliding-Window Round Memory — HIGH IMPACT

Old rounds get LLM-summarized into compact paragraphs; recent rounds keep full detail. Prevents prompt blowup on long simulations.

**Why it matters for FishCloud:** We charge credits per simulation. Longer simulations = more value = more credit spend. Without memory compaction, quality degrades after ~15-20 rounds. MiroShark can run 50+ rounds without quality loss.

**Effort:** Low-Medium. Straightforward to implement as a pre-processing step before each round's prompt construction.

### 3. Prediction Market (Polymarket/Wonderwall) — HIGH IMPACT

A third simulated platform with AMM-based prediction market. Agents buy/sell shares based on beliefs. Market prices emerge from collective behavior.

**Why it matters for FishCloud:** This is a killer differentiator for our analyst/strategist users. "The market converged to 73% probability" is the kind of output they'd pay premium credits for. Also creates natural cross-platform dynamics via the MarketMediaBridge.

**Effort:** High. Requires the full Wonderwall module (AMM logic, agent trading actions, market state tracking). But it's AGPL — we can legally adapt it.

### 4. Smart Dual-Tier Model Routing — MEDIUM IMPACT

Strong model for intelligence-sensitive tasks (reports, ontology, graph reasoning), cheap model for bulk work (NER, profile gen, simulation rounds).

**Why it matters for FishCloud:** We already have `model_routing` in our DB. MiroShark's approach is more granular — routing by *task type* within a single simulation rather than just by tier. This could cut GPU costs 40-60% per job.

**Effort:** Low. We already have the infrastructure; just need to apply it more granularly in the adapter layer.

### 5. Web Enrichment for Public Figures — MEDIUM IMPACT

Auto-detects notable entities (politicians, CEOs) and enriches their graph nodes with real-world data via web search.

**Why it matters for FishCloud:** Users simulating reactions to real-world events (product launches, policy changes) get much richer agents when the system knows who these people actually are.

**Effort:** Low. A pre-simulation enrichment step with a web search API call per notable entity.

### 6. Batched Writes / Performance Optimizations — LOW-MEDIUM IMPACT

10x faster graph construction via batched writes, 3x faster parallel chunk processing.

**Why it matters for FishCloud:** Faster pipeline = shorter GPU time = lower cost per job. But we use Zep, not Neo4j, so the specific optimization doesn't directly apply. The parallel chunk processing pattern does.

**Effort:** Low for chunk parallelism. High if we wanted to switch from Zep to Neo4j (not recommended).

---

## Features NOT Worth Copying

- **Neo4j migration** — We're on Zep Cloud which is managed. Switching adds operational burden with marginal benefit.
- **Claude Code CLI as LLM provider** — Clever hack for local users, irrelevant for our cloud SaaS.
- **Ollama embeddings** — We use cloud GPU; local inference isn't our model.
- **"Hyperstitions" UI** — Our visual identity (ocean teal, bioluminescent) is intentionally different from their aesthetic.

---

## Recommended Priority

| Priority | Feature | Effort | Credit Impact |
|----------|---------|--------|---------------|
| **P0** | Sliding-window round memory | Low-Med | Enables longer sims = more credit spend |
| **P0** | Smart task-level model routing | Low | Cuts GPU cost 40-60% |
| **P1** | Belief state system | Medium | Makes reports dramatically better |
| **P1** | Web enrichment | Low | Better agent fidelity for real-world scenarios |
| **P2** | Prediction market platform | High | Premium tier feature, major differentiator |

---

## Licensing Note

MiroShark is AGPL-3.0, same as MiroFish. Since we already wrap MiroFish (also AGPL), incorporating MiroShark ideas doesn't change our licensing posture — but any code we directly copy must comply with AGPL (source availability for the SaaS). Implementing the *concepts* independently in our adapter layer is cleaner.
