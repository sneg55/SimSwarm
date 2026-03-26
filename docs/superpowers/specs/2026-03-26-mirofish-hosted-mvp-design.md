# MiroFish Hosted — MVP Product Specification

**Codename:** FishCloud
**Version:** 2.0
**Date:** March 26, 2026
**Goal:** Launch the fastest, cheapest, and easiest way for non-technical users to run large-scale MiroFish simulations on rented GPUs — pure credits-based usage from day one, with public "live demo result" pages as the no-login hook.

---

## 1. Product Overview

A fully managed SaaS wrapping the open-source MiroFish (AGPL-3.0) swarm intelligence engine (github.com/666ghj/MiroFish, 43k+ stars).

Users buy credits, upload a seed document, type a natural-language prediction goal, and receive a prediction report plus interactive agent chat replay.

### Value Proposition

- Zero infra, zero API keys, zero Docker hassle
- Pure pay-as-you-go credits (no free sims)
- Public demo pages give instant "wow" without any account
- Ride the March 2026 MiroFish hype wave

### Target Users (MVP)

- Traders / finance hobbyists
- PR / marketing teams
- Policy analysts & researchers
- Indie creators & writers
- Existing MiroFish GitHub users who want hosted scale

### Out of Scope (MVP)

- Free tier or free simulations
- Team / collaboration features
- 1M-agent mode
- Persistent saved simulations
- Enterprise features (SSO, white-label, dedicated GPUs)
- Mobile app
- Multi-language UI (English-first only)

---

## 2. Architecture Overview

### Thin Wrapper Model

MiroFish engine stays as close to upstream as possible (git submodule). The SaaS layer wraps it with multi-tenancy, billing, and GPU orchestration.

```
+--------------------------------------------------+
|                   Frontend                        |
|   Existing MiroFish Vue.js UI (forked)            |
|   + Auth pages + Billing/Credits UI + Demo pages  |
|   + Tailwind restyling                            |
+-------------------------+------------------------+
                          |
+-------------------------v------------------------+
|                SaaS API Layer                     |
|   Python/FastAPI                                  |
|   - Auth (email+password, JWT)                    |
|   - Credit ledger (deduct/check/purchase)         |
|   - Job manager (create/status/cancel)            |
|   - Stripe webhooks                               |
+-----------+--------------------------+-----------+
            |                          |
+-----------v-----------+  +-----------v-----------+
|      Job Queue        |  |      PostgreSQL       |
|   Celery + Redis      |  |  users, credits, jobs |
+-----------+-----------+  +-----------------------+
            |
+-----------v--------------------------------------+
|            GPU Worker Layer                       |
|   Spot H100/A100 on RunPod/Vast.ai               |
|   +--------------------------------------+       |
|   |  MiroFish Engine (git submodule)     |       |
|   |  + vLLM (operator-configured model)  |       |
|   |  + Neo4j/Zep (per-simulation)        |       |
|   +--------------------------------------+       |
|   Auto spin-up / tear-down per job               |
+--------------------------------------------------+
```

### Key Architectural Decisions

1. **MiroFish as submodule** — Engine code lives in `vendor/mirofish/`, updated from upstream periodically. Minimal patches (config injection, progress callbacks, result extraction).
2. **Self-hosted LLM** — vLLM on spot GPUs for COGS optimization. No external LLM API dependency.
3. **Ephemeral GPU workers** — Each job spins up a worker, runs the 5-step pipeline, stores results, tears down. Zero idle GPU cost.
4. **Per-simulation Neo4j/Zep** — Each sim gets isolated graph/memory state. Destroyed after results are extracted (kept 7 days for demo agent chat replay).
5. **Operator-configurable model routing** — Admin config table maps sim tier to model/GPU/parameters. Users never see model choices.

### Component Interfaces

| Interface | Protocol | Notes |
|-----------|----------|-------|
| Frontend <-> SaaS API | REST JSON (OpenAPI) | Standard CRUD + SSE for progress |
| SaaS API <-> Job Queue | Celery task dispatch | Redis pub/sub for progress |
| Job Queue <-> GPU Worker | RunPod/Vast.ai SDK | Provisioning + SSH/API for execution |
| GPU Worker <-> MiroFish Engine | Python function calls | Thin adapter wrapping MiroFish API |

---

## 3. User Flows

### Flow 1: Visitor (No Account)

1. Lands on marketing page
2. Browses 4-5 public demo result pages (e.g. `/demo/iran-war-us-china`)
3. Each demo shows: prediction report + scrollable agent chat replay (read-only)
4. CTA: "Run your own simulation" -> sign-up

### Flow 2: Sign-Up & Credit Purchase

1. Email + password registration -> email verification
2. Lands on dashboard with 0 credits
3. Prompted to buy a credit pack (Starter/Pro/Heavy) via Stripe checkout
4. Credits appear in balance immediately after payment

### Flow 3: Run a Simulation

1. Click "New Simulation"
2. Drag & drop seed file (PDF/TXT, max 50k chars) or paste text
3. Type prediction goal in natural language
4. Select tier: Small / Medium / Large
   - Shows exact credit cost + estimated runtime before confirmation
5. Click "Run" -> credits deducted immediately
6. Live progress page: pipeline stage indicator (steps 1-5) + estimated time remaining
7. On completion -> redirected to results dashboard

**Constraint:** "Run" button is disabled with "Buy credits" prompt if balance is insufficient.

### Flow 4: Results Dashboard

1. Prediction report (rendered markdown)
2. Agent chat replay (scrollable conversation log, read-only)
3. Export: PDF, JSON, CSV buttons
4. "Run another" CTA

### Flow 5: Account Management

- Credit balance (always visible in nav bar)
- Purchase more credits (one-click)
- Job history (list of past sims with status, cost, date)
- Low-credit warning banner when balance < 30 credits

---

## 4. Non-Functional Requirements

### Performance

| Tier | Target Wall-Clock Time |
|------|----------------------|
| Small (1-500 agents) | < 30 minutes |
| Medium (501-2,000 agents) | < 4 hours |
| Large (2,001-10,000 agents) | < 12 hours |

- First job starts executing within 60 seconds of click (GPU spin-up)

### Reliability

- 99% job success rate
- Multi-provider failover: RunPod primary, Vast.ai fallback
- Graceful failure: if a job dies mid-run, credits are refunded automatically

### Security

- User seeds deleted after 7 days
- Passwords hashed (bcrypt)
- JWT tokens with short expiry + refresh tokens
- Per-user job isolation (no cross-tenant data leakage)

### Cost Controls

- Auto-truncate seed > 50k chars with warning
- Max 200 simulation rounds for MVP
- Real-time credit cost preview before run
- GPU auto-teardown after job completion

### Analytics

- PostHog for conversion tracking (landing -> signup -> purchase -> first sim)
- Internal dashboard: job cost, runtime, GPU utilization, margin per sim

---

## 5. Success Metrics

### Launch KPIs (First 30 Days)

- 300 sign-ups
- 80 credit purchases
- >= 60% gross margin
- NPS >= 40

### Revenue Target

- $5k-12k by end of month 2 (credits only)

### Critical Pre-Launch Gate

Benchmarking must validate that credit pricing yields >= 60% gross margin. If it doesn't, adjust credit consumption per tier (not pack prices) before launch.

---

## Appendix A: Billing & Credits

### Credit Packs (Stripe One-Time Purchase)

| Pack | Credits | Price | Target Use |
|------|---------|-------|------------|
| Starter | 100 | $19 | 3-4 small sims |
| Pro | 500 | $79 | 15-20 medium sims |
| Heavy | 2,000 | $249 | Large-scale or frequent use |

### Credit Consumption Per Tier

| Tier | Agents | Credits |
|------|--------|---------|
| Small | 1-500 | 30 |
| Medium | 501-2,000 | 90 |
| Large | 2,001-10,000 | 300 |

**These numbers are placeholders.** Must be validated by benchmarking before launch.

### Billing Logic

- Credits deducted atomically at job start (not completion)
- No partial refunds for completed jobs
- Full credit refund if job fails due to system error
- No expiration on purchased credits
- Balance stored in PostgreSQL credit ledger (double-entry: purchases are credits, job runs are debits)

### Stripe Integration

- Checkout Sessions API for one-time pack purchases
- Webhook listener for `checkout.session.completed` -> credit ledger entry
- No subscriptions for MVP
- Customer portal for receipt/invoice access

### Benchmarking Plan (Pre-Launch, Blocking)

1. Run 3 simulations per tier (Small/Medium/Large) on target GPU config
2. Measure: total GPU-hours, vLLM tokens generated, Neo4j/Zep resource usage, total wall-clock time
3. Calculate actual COGS per sim tier
4. Validate that credit price / COGS >= 2.5x (60% gross margin)
5. If margin is below target: adjust credit consumption per tier (keep pack prices fixed)
6. Document results in `docs/benchmarks/` before launch

---

## Appendix B: GPU Orchestration

### Provider Strategy

- **Primary:** RunPod (serverless or on-demand spot)
- **Fallback:** Vast.ai (if RunPod capacity unavailable)
- Spot instances only for MVP (no on-demand)

### GPU Targets

| Tier | GPU | Notes |
|------|-----|-------|
| Small | A100 40GB | Or equivalent |
| Medium / Large | H100 80GB | A100 80GB as fallback |

### Operator Model Routing Table

A configuration table in PostgreSQL that maps simulation tiers to infrastructure:

```
sim_tier  | model_id                      | gpu_type   | max_rounds | vllm_args
----------+-------------------------------+------------+------------+----------
small     | Qwen2.5-32B-Instruct-AWQ      | a100-40gb  | 200        | ...
medium    | Qwen2.5-32B-Instruct-AWQ      | h100-80gb  | 200        | ...
large     | Qwen2.5-32B-Instruct-AWQ      | h100-80gb  | 200        | ...
```

- Operator can change model, GPU type, and parameters per tier without a deploy
- Enables A/B testing models, swapping in newer/cheaper models as they release
- Users never see this — they only see Small / Medium / Large

### vLLM Setup

- Default model: Qwen2.5-32B-Instruct (AWQ quantized)
- Fallback model: Llama-3.3-70B-Instruct
- Served via vLLM with OpenAI-compatible API endpoint
- MiroFish engine connects to vLLM as if it were any OpenAI-compatible API

### Job Lifecycle

1. SaaS API creates Celery task with job config (seed, goal, tier, user_id)
2. Celery worker calls RunPod SDK -> provisions GPU instance with pre-built Docker image (vLLM + MiroFish engine + Neo4j + Zep)
3. Worker connects to instance -> starts MiroFish pipeline with injected config
4. Progress callbacks sent via Redis pub/sub -> forwarded to frontend via SSE/polling
5. On completion: results (report JSON, agent chat logs) uploaded to PostgreSQL + S3
6. GPU instance terminated
7. On failure: retry once on same provider, then failover to Vast.ai, then mark failed + refund credits

### Pre-Built Docker Image

- Based on MiroFish's existing Dockerfile
- Adds: vLLM server, model weights (baked in or pulled from S3 cache), job runner script
- Rebuilt weekly or on upstream MiroFish updates

### Hard Timeouts

| Tier | Timeout | Action on Exceed |
|------|---------|-----------------|
| Small | 45 min | Kill + refund |
| Medium | 5 hrs | Kill + refund |
| Large | 12 hrs | Kill + refund |

---

## Appendix C: Demo Pages

### Purpose

4-5 pre-run simulation results as the no-login marketing hook. Instant "wow" without any account.

### Demo Topics (Suggested, Final List TBD)

1. `/demo/iran-war-us-china` — Predict US vs China public opinion on Iran escalation over 30 days (seed: CNN breaking news article)
2. `/demo/tesla-earnings` — Predict market sentiment after Tesla Q1 earnings (seed: SEC 10-K filing excerpt)
3. `/demo/dream-red-chamber` — Predict the lost ending of "Dream of the Red Chamber" (seed: Gutenberg novel excerpt)
4. `/demo/eu-ai-act` — Predict industry reaction to EU AI Act enforcement (seed: policy document)
5. `/demo/bitcoin-halving` — Predict crypto community sentiment post-halving (seed: recent crypto news roundup)

### Page Content

Each demo page contains:
- Hero section: seed summary + prediction goal
- Prediction report (rendered markdown, full)
- Agent chat replay (scrollable conversation log, read-only)
- CTA banner: "Run your own simulation — buy credits to get started"

### Technical Implementation

- Demos are static JSON snapshots stored in the repo (or S3)
- Weekly cron job re-runs each demo sim on our backend, exports results, replaces the snapshot
- Frontend renders demo pages from the same Vue components as the real results dashboard (code reuse)
- No auth required — public routes
- No persistent GPU/memory cost — just the weekly re-run

### Content Guidelines

- Seeds must be from public domain or openly licensed sources
- Demo topics should span different use cases (finance, geopolitics, culture, policy, crypto) to show breadth
- Reports should be impressive enough to convert visitors

---

## Appendix D: MiroFish Integration

### Repository Structure

```
fishandcat/
├── vendor/mirofish/          # git submodule -> fork of 666ghj/MiroFish
├── saas/
│   ├── api/                  # FastAPI SaaS layer
│   ├── workers/              # Celery job workers
│   ├── billing/              # Stripe + credit ledger
│   └── config/               # Operator config (model routing table, etc.)
├── frontend/                 # Forked MiroFish Vue UI + auth/billing pages
├── infra/
│   ├── docker/               # GPU worker Docker image
│   └── scripts/              # Deploy, benchmark, demo re-run scripts
├── docs/
│   └── superpowers/specs/    # This spec + appendices
└── demos/                    # Static demo snapshots (JSON)
```

### What We Patch in the MiroFish Fork (Minimal)

1. **Config injection** — Replace `.env` file loading with runtime config passed from our job runner (LLM endpoint, Neo4j/Zep connection strings, simulation parameters)
2. **Progress callbacks** — Add webhook/callback hooks at each pipeline stage (steps 1-5) so our worker can report progress back to the SaaS layer
3. **Result extraction** — Add an export function that dumps the final report + agent chat logs to JSON (if not already available)

### What We Do NOT Patch

- Core simulation logic
- Agent behavior / personality system
- Knowledge graph construction
- Report generation

### Upstream Sync Process

1. Track upstream `main` branch in our fork
2. Monthly (or as needed): merge upstream into fork, resolve conflicts in our 3 patch areas
3. Run test suite against merged code before deploying
4. If upstream makes breaking changes to our patch points: adapt patches or pin to last compatible version

### License Compliance (AGPL-3.0)

- Our MiroFish fork is public on GitHub (required by AGPL)
- The SaaS layer (`saas/`, `frontend/` additions, `infra/`) is private — separate work communicating with MiroFish over internal APIs, not a derivative of the AGPL code
- Credit to upstream project in footer and docs
