# AGENTS.md

## Project Overview

SimSwarm — fully managed SaaS for swarm intelligence simulations. Users buy credits, upload a seed document, set a prediction goal, and get a deep analysis report + entity knowledge graph + prediction market data + chat replay.

Live at simswarm.xyz.

## Tech Stack

- **Backend:** Python 3.11+, FastAPI, async SQLAlchemy + asyncpg, Celery + Redis, Alembic
- **Frontend:** Vue 3 (Composition API), Vite 6, Pinia, Tailwind CSS, Cytoscape.js
- **Database:** PostgreSQL 16
- **Engine:** `simswarm/` — native async Python swarm engine (entity extraction → sim → graph construction → belief updates)
- **GPU:** RunPod spot instances (H100/L40S/A100), ephemeral per-job
- **Fast LLM (per-round agent turns):** Qwen3-14B via vLLM on the pod with tool calling (hermes parser)
- **Smart LLM (report generation):** Claude Opus 4.6 via Anthropic Messages API (off-pod, in Celery)
- **Enrichment:** xAI Grok (web_search + x_search) for seed research
- **Object storage:** MinIO (S3-compatible) for simulation artifacts
- **Billing:** Stripe one-time credit packs
- **Proxy:** Caddy with automatic TLS
- **CI/CD:** GitHub Actions → SSH deploy to Hetzner

## Repository Layout

```
saas/
  adapters/           # External LLM adapter (Anthropic)
  auth/               # Auth feature: api, models (User), schemas, service, email, profile
  billing/            # Billing feature: api, models (CreditEntry, CreditPack), ledger, stripe
  jobs/               # Jobs feature: api, models (SimulationJob, ModelRouting, ErrorEvent),
                      #   runner, tasks, tasks_report, persistence, recovery, cleanup, alerts,
                      #   enrichment, refund, progress, export, share, report, report_tools_minio
  gpu/                # GPU provider: abstract base, RunPod, Vast.ai, errors
  storage/            # MinIO S3-compatible storage
  constants/          # Named constants (tiers, etc.)
  workers/            # Celery app config + shared async utils
  middleware/         # Error tracking
  models/             # Base model class + re-exports for alembic discovery
  config.py           # Pydantic Settings
  database.py         # Async SQLAlchemy engine/session
  router.py           # API router assembly
  health.py           # Health check endpoint
  main.py             # FastAPI app factory
simswarm/             # Native swarm engine (no external engine dep)
  entities.py         # LLM-backed entity extraction
  engine.py           # Core simulation loop + belief update integration
  belief.py           # Heuristic belief-state math (no LLM)
  stance.py           # Keyword-based post sentiment scoring
  graph.py            # GraphSnapshot builder (nodes from entities, edges from chat_log)
  report.py           # Reference report generator (SaaS-side variant lives in saas/jobs/)
  adapter.py          # Output shape conversion for the SaaS API contract
  environments/       # Social / market / economic environments
  prompts/            # Jinja2 templates (agent_system, report, extract_entities)
frontend/src/
  views/              # Page components
  components/         # Reusable components (graph/, wizard/, results/, data/)
  composables/        # Shared Composition API logic
  stores/             # Pinia (auth, credits)
  api/                # Axios clients
infra/docker/         # GPU worker image: run_job_v2 + run_job_v2_runner + worker_api + start.sh
tests/                # pytest + pytest-asyncio
```

## Development Commands

```bash
pip install -e ".[dev]"
uvicorn saas.main:create_app --factory --reload --port 8080
celery -A saas.workers.celery_app worker --loglevel=info

cd frontend && npm install && npm run dev
cd frontend && npm run build

pytest                              # Backend (in-memory SQLite)
cd frontend && npm test             # Frontend (Vitest)
```

## Key Patterns

- **Feature-based organization:** Each feature (auth/, billing/, jobs/, gpu/) owns its models, schemas, and API routes.
- **App factory:** `saas.main:create_app()` — accepts optional `Settings` for testing.
- **Dependency injection:** `saas.database:get_session` is overridden in tests.
- **Credit gating:** Job creation checks balance, returns 402 if insufficient.
- **Draft workflow:** Users can save partial jobs (DRAFT status) and resume from any wizard step.
- **Job lifecycle:** API → Celery task (`run_simulation_task`) → enrich seed → RunPod GPU provision → vLLM + `simswarm` engine on pod → upload artifacts to MinIO → teardown GPU → `generate_report_task` on Celery calls Claude Opus with MinIO artifacts → persist report → `status=COMPLETED`. Any pre-COMPLETED failure refunds 100%.
- **Model routing:** Operator-configurable `model_routing` DB table maps tier → GPU/model/params.
- **DB writes from Celery:** Always use sync psycopg2, never the shared async pool (prevents InterfaceError).
- **Recovery:** If a deploy kills the Celery worker mid-simulation, recovery auto-resumes jobs on existing pods. Handles idle (resubmits /job), running (polls /status), and completed (saves results) states.
- **Simulation data:** Rich data (posts, trades, markets) extracted from GPU SQLite DBs, uploaded to MinIO, exposed via Data tab when `sim_data_available=true`.

## Important Rules

- Never generate fake or mock data for demos. Only use real data from actual simulation runs. Exception: unit/integration test mocks are fine.
- Simulation logic lives in `simswarm/` — no external engine dependencies. The legacy vendored engine has been fully removed.
- GPU instances are ephemeral — always ensure teardown happens (even on failure).
- Tier configuration lives in `saas/constants/tiers.py` — single source of truth.
- PostgreSQL enum changes need `COMMIT`/`BEGIN` wrapping in Alembic (`ALTER TYPE ADD VALUE` can't run inside a transaction).
- Files should stay under 300 lines. Split by concern if exceeded.
- Ruff for linting, line length 100.

## Simulation Tiers

| Tier | Agents | Credits | Timeout |
|------|--------|---------|---------|
| small | 1–500 | 30 | 45 min |
| medium | 501–2,000 | 90 | 5 hours |
| large | 2,001–10,000 | 300 | 12 hours |
