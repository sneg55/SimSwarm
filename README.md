# FishCloud (MiroFish Hosted)

A fully managed SaaS wrapping the open-source [MiroFish](https://github.com/666ghj/MiroFish) swarm intelligence engine (AGPL-3.0). Users buy credits, upload a seed document, type a prediction goal, and receive a prediction report with interactive agent chat replay and entity graph visualization.

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
- **Billing** — Stripe one-time credit packs, double-entry credit ledger
- **Database** — PostgreSQL 16, Alembic migrations
- **Proxy** — Caddy with automatic TLS

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
# Backend tests
pytest

# Frontend tests
cd frontend && npm test
```

## Deployment (Hetzner)

Deployed via GitHub Actions on push to `main`. The workflow SSHs into the Hetzner VPS and runs the deploy script.

For manual / first-time deployment:

```bash
ssh root@your-server 'bash -s' < deploy.sh
```

The deploy script clones the repo to `/opt/fishcloud`, checks for `.env`, runs migrations, and starts all services via Docker Compose.

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `SECRET_KEY` | Yes | JWT signing key |
| `POSTGRES_PASSWORD` | Yes | Database password (used by docker-compose) |
| `STRIPE_SECRET_KEY` | Yes | Stripe API key |
| `STRIPE_WEBHOOK_SECRET` | Yes | Stripe webhook signing secret |
| `RUNPOD_API_KEY` | Yes | RunPod GPU provisioning |
| `DOMAIN` | No | Production domain (default: `localhost`) |
| `LLM_API_KEY` | Yes | LLM API key for MiroFish engine |
| `LLM_BASE_URL` | No | vLLM endpoint (default: `http://localhost:8000/v1`) |
| `LLM_MODEL_NAME` | No | Model ID (default: `Qwen2.5-32B-Instruct-AWQ`) |
| `ZEP_API_KEY` | Yes | Zep memory/graph service key |

## Project Structure

```
fishandcat/
├── saas/                  # FastAPI backend
│   ├── api/               #   Route handlers (auth, jobs, billing, export, progress)
│   ├── auth/              #   JWT auth, email verification
│   ├── billing/           #   Stripe integration, credit ledger, credit packs
│   ├── gpu/               #   RunPod provider, GPU provisioning
│   ├── models/            #   SQLAlchemy ORM models
│   ├── workers/           #   Celery app, job runner, tasks
│   └── adapters/          #   MiroFish engine adapter
├── frontend/              # Vue 3 SPA
│   └── src/
│       ├── views/         #   Pages (Landing, Dashboard, SimulationResults, etc.)
│       ├── components/    #   Reusable components (graph viz, credits, export)
│       ├── stores/        #   Pinia state management
│       └── api/           #   Axios API clients
├── vendor/mirofish/       # MiroFish engine (git submodule)
├── demos/                 # Static demo simulation snapshots (JSON)
├── infra/scripts/         # Benchmark, demo refresh scripts
├── alembic/               # Database migrations
├── docs/                  # Specs, plans, benchmarks
├── Dockerfile             # Multi-stage build (frontend + backend)
├── docker-compose.yml     # Full stack orchestration
├── Caddyfile              # Reverse proxy config
└── deploy.sh              # Hetzner deployment script
```

## Credit Packs & Pricing

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

## License

The SaaS layer (`saas/`, `frontend/` additions, `infra/`) is proprietary. The MiroFish engine in `vendor/mirofish/` is licensed under [AGPL-3.0](https://www.gnu.org/licenses/agpl-3.0.html).
