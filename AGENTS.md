# AGENTS.md

## Project Overview

FishCloud — a fully managed SaaS wrapping the open-source MiroFish swarm intelligence engine. Users buy credits, upload a seed document, set a prediction goal, and get a report + chat replay + entity graph.

## Tech Stack

- **Backend:** Python 3.11+, FastAPI, async SQLAlchemy + asyncpg, Celery + Redis, Alembic migrations
- **Frontend:** Vue 3 (Composition API), Vite 6, Pinia, Tailwind CSS, Cytoscape.js
- **Database:** PostgreSQL 16
- **GPU:** RunPod spot instances (A100/H100), ephemeral per-job
- **Billing:** Stripe one-time credit packs
- **Proxy:** Caddy with automatic TLS
- **CI/CD:** GitHub Actions → SSH deploy to Hetzner

## Repository Layout

```
saas/                   # FastAPI backend
  api/                  #   auth.py, jobs.py, billing.py, export.py, progress.py, health.py
  auth/                 #   JWT auth, email verification
  billing/              #   credit_packs.py, ledger.py, stripe_service.py
  gpu/                  #   provider.py (abstract), runpod_provider.py, failover.py
  models/               #   user.py, job.py, credit_entry.py, model_routing.py
  workers/              #   celery_app.py, job_runner.py, tasks.py
  adapters/             #   MiroFish engine adapter
  config.py             #   Pydantic Settings (env vars)
  database.py           #   Async SQLAlchemy engine/session
  main.py               #   FastAPI app factory
frontend/src/
  views/                #   Landing, Login, Register, Dashboard, NewSimulation, SimulationStatus, SimulationResults, DemoResult, Account
  components/           #   graph/ (Cytoscape viz), CreditBadge, TierSelector, ChatReplay, etc.
  stores/               #   Pinia (auth)
  api/                  #   Axios clients (auth, billing, jobs, demos)
vendor/mirofish/        # MiroFish engine (git submodule, AGPL-3.0)
demos/                  # Static demo simulation JSON snapshots
tests/                  # pytest + pytest-asyncio
infra/scripts/          # benchmark.py, benchmark_report.py, refresh_demos.py
docs/superpowers/       # Specs and implementation plans
```

## Development Commands

```bash
# Backend
pip install -e ".[dev]"
uvicorn saas.main:create_app --factory --reload --port 8080
celery -A saas.workers.celery_app worker --loglevel=info

# Frontend
cd frontend && npm install && npm run dev    # Vite dev at :5173
cd frontend && npm run build                 # Prod build

# Tests
pytest                              # Backend (uses in-memory SQLite)
cd frontend && npm test             # Frontend (Vitest)

# Docker (full stack)
docker compose build
docker compose run --rm migrate
docker compose up -d
```

## Testing Conventions

- Backend tests use `pytest-asyncio` with `asyncio_mode = "auto"`
- Test database: in-memory SQLite via `aiosqlite` (no external DB needed)
- Fixtures in `tests/conftest.py`: `client` (async httpx), `db_session`, `auth_headers`, `funded_user`, `seeded_routing`
- Ruff for linting, line length 100

## Key Patterns

- **App factory:** `saas.main:create_app()` — accepts optional `Settings` for testing
- **Dependency injection:** `saas.database:get_session` is overridden in tests
- **Credit gating:** Job creation checks balance, returns 402 if insufficient
- **Job lifecycle:** API → Celery task → RunPod GPU provision → MiroFish pipeline → store results → teardown GPU
- **Rate limiting:** slowapi limiter, reset in test fixtures
- **Model routing:** Operator-configurable `model_routing` DB table maps tier → GPU/model/params

## Important Rules

- Never generate fake or mock data for demos or feature testing. Only use real data from actual simulation runs. Exception: unit/integration test mocks are fine.
- MiroFish engine code in `vendor/mirofish/` should not be modified directly — use the adapter layer in `saas/adapters/`.
- Credit pack prices are fixed; adjust credit consumption per tier if margins are off.
- GPU instances are ephemeral — always ensure teardown happens (even on failure).

## Deployment

- Push to `main` triggers GitHub Actions deploy (`.github/workflows/deploy.yml`)
- Deploys via SSH to Hetzner VPS at `/opt/fishcloud`
- Services: app, celery, db, redis, caddy, migrate (one-shot), frontend-init (one-shot)
- Environment variables configured in `.env` on server (not in repo)
