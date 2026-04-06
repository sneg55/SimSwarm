# AGENTS.md

## Project Overview

SimSwarm — a fully managed SaaS wrapping the open-source MiroFish swarm intelligence engine. Users buy credits, upload a seed document, set a prediction goal, and get a report + chat replay + entity graph.

## Tech Stack

- **Backend:** Python 3.11+, FastAPI, async SQLAlchemy + asyncpg, Celery + Redis, Alembic migrations
- **Frontend:** Vue 3 (Composition API), Vite 6, Pinia, Tailwind CSS, Cytoscape.js
- **Database:** PostgreSQL 16
- **GPU:** RunPod spot instances (A100/H100/L40S), ephemeral per-job
- **Billing:** Stripe one-time credit packs
- **Proxy:** Caddy with automatic TLS
- **CI/CD:** GitHub Actions → SSH deploy to Hetzner

## Repository Layout

```
saas/
  auth/               # Auth feature: api, models (User), schemas, service, email, profile
  billing/            # Billing feature: api, models (CreditEntry, CreditPack), schemas, ledger, stripe, credit_packs
  jobs/               # Jobs feature: api, models (SimulationJob, ModelRouting, ErrorEvent), schemas,
                      #   runner, tasks, persistence, recovery, cleanup, alerts, enrichment, refund,
                      #   progress, export, share, fetch, ai
  gpu/                # GPU provider: abstract base, RunPod, Vast.ai, errors
  adapters/           # MiroFish engine adapter
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
frontend/src/
  views/              # Page components
  components/         # Reusable components (graph/, wizard/, results/, data/)
  composables/        # Shared Composition API logic
  stores/             # Pinia (auth, credits)
  api/                # Axios clients
vendor/mirofish/      # MiroFish engine (git submodule, AGPL-3.0)
infra/                # Docker GPU worker, Neo4j, operational scripts
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
- **App factory:** `saas.main:create_app()` — accepts optional `Settings` for testing
- **Dependency injection:** `saas.database:get_session` is overridden in tests
- **Credit gating:** Job creation checks balance, returns 402 if insufficient
- **Job lifecycle:** API → Celery task → RunPod GPU provision → MiroFish pipeline → store results → teardown GPU
- **Model routing:** Operator-configurable `model_routing` DB table maps tier → GPU/model/params
- **DB writes from Celery:** Always use sync psycopg2, never the shared async pool

## Important Rules

- Never generate fake or mock data for demos. Only use real data from actual simulation runs.
- MiroFish engine code in `vendor/mirofish/` should not be modified directly — use `saas/adapters/`.
- GPU instances are ephemeral — always ensure teardown happens (even on failure).
- Tier configuration lives in `saas/constants/tiers.py` — single source of truth.
