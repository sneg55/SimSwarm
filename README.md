# SimSwarm (FishCloud)

A fully managed SaaS wrapping the open-source [MiroFish](https://github.com/666ghj/MiroFish) swarm intelligence engine (AGPL-3.0). Users buy credits, upload a seed document, set a prediction goal, and receive a prediction report with interactive agent chat replay, entity graph visualization, and web-sourced research context.

## Architecture

```
Frontend (Vue 3 + Vite + Tailwind)
        |
SaaS API (FastAPI)
        |
   +---------+----------+
   |                     |
Celery + Redis      PostgreSQL
   |
GPU Workers (RunPod spot instances)
   |
MiroFish Engine (git submodule)
+ vLLM + Zep
```

- **Frontend** — Vue 3, Pinia, Cytoscape.js for graph visualization, Tailwind CSS
- **Backend** — FastAPI, async SQLAlchemy, Celery task queue, Redis
- **GPU** — Ephemeral RunPod spot instances (A100/H100), auto spin-up/teardown per job
- **Enrichment** — xAI Grok (web_search + x_search) for seed text research
- **Billing** — Stripe one-time credit packs (DB-configurable), double-entry credit ledger
- **Database** — PostgreSQL 16, Alembic migrations
- **Monitoring** — Error event capture (API middleware + Celery failure handler), auto-prune
- **Proxy** — Caddy with automatic TLS, security headers, SSRF protection

## Prerequisites

- Docker & Docker Compose
- Node.js 20+ (for local frontend dev)
- Python 3.11+ (for local backend dev)

## Quick Start (Docker)

```bash
# 1. Clone with submodules
git clone --recurse-submodules https://github.com/sneg55/SimSwarm.git
cd SimSwarm

# 2. Configure environment
cp .env.example .env
# Edit .env with your values:
#   POSTGRES_PASSWORD, SECRET_KEY, STRIPE_SECRET_KEY,
#   STRIPE_WEBHOOK_SECRET, RUNPOD_API_KEY, DOMAIN

# 3. Build and run
docker compose build
docker compose run --rm migrate    # run database migrations
docker compose up -d               # start all services
```

The app will be available at `http://localhost` (or your configured `DOMAIN`).

### Services

| Service | Container | Port | Description |
|---------|-----------|------|-------------|
| API | simswarm-api | 8080 | FastAPI backend |
| Celery | simswarm-celery | — | Async job worker |
| PostgreSQL | simswarm-db | 5432 | Database |
| Redis | simswarm-redis | 6379 | Message queue & cache |
| Caddy | simswarm-caddy | 80, 443 | Reverse proxy + TLS |

## Local Development

### Backend

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run API server
uvicorn saas.main:create_app --factory --reload --port 8080

# Run Celery worker
celery -A saas.workers.celery_app worker --loglevel=info
```

### Frontend

```bash
cd frontend
npm install
npm run dev        # Vite dev server at http://localhost:5173
npm run build      # Production build to frontend/dist/
```

### Tests

```bash
# Backend tests (316 tests, in-memory SQLite — no external DB needed)
pytest

# Frontend tests (Vitest)
cd frontend && npm test
```

## Deployment (Hetzner)

Deployed via GitHub Actions on push to `main`. The workflow SSHs into the Hetzner VPS and runs the deploy script.

For manual / first-time deployment:

```bash
ssh root@your-server 'bash -s' < deploy.sh
```

The deploy script pulls latest code, validates migrations (single Alembic head check), gracefully stops Celery, runs migrations, rebuilds frontend assets, and health-checks the API before completing.

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `SECRET_KEY` | Yes | JWT signing key |
| `POSTGRES_PASSWORD` | Yes | Database password (used by docker-compose) |
| `STRIPE_SECRET_KEY` | Yes | Stripe API key |
| `STRIPE_WEBHOOK_SECRET` | Yes | Stripe webhook signing secret |
| `RUNPOD_API_KEY` | Yes | RunPod GPU provisioning |
| `XAI_API_KEY` | No | xAI API key for seed enrichment (web + X search) |
| `DOMAIN` | No | Production domain (default: `localhost`) |
| `LLM_API_KEY` | Yes | LLM API key for MiroFish engine |
| `LLM_BASE_URL` | No | vLLM endpoint (default: `http://localhost:8000/v1`) |
| `LLM_MODEL_NAME` | No | Model ID (default: `Qwen2.5-32B-Instruct-AWQ`) |
| `ZEP_API_KEY` | Yes | Zep memory/graph service key |
| `ALERT_WEBHOOK_URL` | No | Webhook URL for orphan pod / error alerts |

## Project Structure

```
fishandcat/
├── saas/                  # FastAPI backend
│   ├── api/               #   Route handlers (auth, jobs, billing, profile, share)
│   ├── auth/              #   JWT auth, email verification, password hashing
│   ├── billing/           #   Stripe integration, credit ledger, credit packs
│   ├── gpu/               #   RunPod/Vast.ai provider, failover, error classification
│   ├── middleware/        #   Error tracking middleware
│   ├── models/            #   SQLAlchemy ORM models (job, user, credit_entry, credit_pack, error_event)
│   ├── workers/           #   Celery app, job runner, enrichment, cleanup, recovery
│   └── adapters/          #   MiroFish engine adapter
├── frontend/              # Vue 3 SPA
│   └── src/
│       ├── views/         #   Pages (Landing, Dashboard, SimulationResults, Account, etc.)
│       ├── components/    #   Reusable components (graph viz, skeleton, pipeline progress)
│       ├── composables/   #   Shared logic (useSimulationData, useScrollReveal)
│       ├── stores/        #   Pinia state management
│       └── api/           #   Axios API clients
├── vendor/miroshark/       # MiroFish engine (git submodule)
├── infra/docker/          # GPU worker image (Dockerfile, run_job.py, worker_api.py)
├── infra/scripts/         # Benchmark, demo refresh scripts
├── alembic/               # Database migrations
├── docs/                  # Specs, plans, benchmarks
├── Dockerfile             # Multi-stage build (frontend + backend)
├── docker-compose.yml     # Full stack orchestration
├── Caddyfile              # Reverse proxy config (TLS, security headers, OG routing)
└── deploy.sh              # Hetzner deployment script
```

## Credit Packs & Pricing

Credit packs are configurable from the database (`credit_packs` table). Defaults:

| Pack | Credits | Price |
|------|---------|-------|
| Starter | 100 | $19 |
| Pro | 500 | $79 |
| Heavy | 2,000 | $249 |

| Simulation Tier | Agents | Credits |
|-----------------|--------|---------|
| Small | 1-500 | 30 |
| Medium | 501-2,000 | 90 |
| Large | 2,001-10,000 | 300 |

## Key Features

- **Seed Enrichment** — Optionally enriches user seed text with live web + X/Twitter research via xAI Grok before simulation runs. Toggle per-simulation, retry on failure.
- **Entity Graph** — Interactive knowledge graph with sentiment scoring, agent stance, influence weights, and per-agent activity timeline on click.
- **Job Retry** — Failed simulations can be retried with one click (same seed/goal/tier, new job).
- **Error Monitoring** — Unhandled API exceptions and Celery task failures captured to `error_events` table with auto-pruning.
- **Account Management** — Password change and account deletion (soft-delete).
- **Share Links** — Public share URLs with OpenGraph meta tags for rich previews on Slack/Twitter/LinkedIn.
- **Orphan Protection** — Celery beat runs cleanup every 10 min; healthcheck verifies beat is active; recovery terminates stale pods.

## License

The SaaS layer (`saas/`, `frontend/` additions, `infra/`) is proprietary. The MiroFish engine in `vendor/miroshark/` is licensed under [AGPL-3.0](https://www.gnu.org/licenses/agpl-3.0.html).
