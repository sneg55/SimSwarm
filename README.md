# SimSwarm

Fully managed SaaS for swarm intelligence simulations. Upload a document, set a prediction goal, and watch AI agents debate, trade, and publish across a simulated ecosystem. Get a deep analysis report, entity knowledge graph, prediction market data, and full chat replay.

**Live at [simswarm.xyz](https://simswarm.xyz)**

## Architecture

```
Frontend (Vue 3 + Vite + Tailwind)
        |
SaaS API (FastAPI)
        |
   +----------+-----------+
   |                      |
Celery + Redis      PostgreSQL
   |
   +-- GPU Workers (RunPod spot) -- simswarm engine + vLLM (Qwen3-14B)
   |        |
   |        +-- artifacts → MinIO (chat_log, posts, trades, graph)
   |
   +-- generate_report_task -- Claude Opus 4.6 (Anthropic Messages API)
```

| Layer | Technology |
|-------|-----------|
| Frontend | Vue 3 (Composition API), Vite 6, Pinia, Tailwind CSS, Cytoscape.js |
| Backend | Python 3.11+, FastAPI, async SQLAlchemy + asyncpg, Celery + Redis, Alembic |
| Database | PostgreSQL 16 |
| Engine | `simswarm/` — native async Python swarm engine |
| GPU | RunPod spot instances (H100/L40S/A100), ephemeral per-job |
| Fast LLM | Qwen3-14B via vLLM on-pod with tool calling (hermes parser) |
| Smart LLM | Claude Opus 4.6 via Anthropic Messages API (off-pod, report gen) |
| Enrichment | xAI Grok (web_search + x_search) |
| Object storage | MinIO (S3-compatible) for simulation artifacts |
| Billing | Stripe one-time credit packs, double-entry credit ledger |
| Proxy | Caddy with automatic TLS, security headers, SSRF protection |
| CI/CD | GitHub Actions -- tests, worker image build, SSH deploy to Hetzner |

## Prerequisites

- Docker & Docker Compose
- Node.js 20+ (for local frontend dev)
- Python 3.11+ (for local backend dev)

## Quick Start (Docker)

```bash
# 1. Clone
git clone https://github.com/sneg55/SimSwarm.git
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
# Backend tests (600+ tests, in-memory SQLite — no external DB needed)
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
| `ANTHROPIC_API_KEY` | Yes | Claude Opus 4.6 for report generation (Celery-side) |
| `SMART_MODEL` | No | Report model override (default: `claude-opus-4-6`) |
| `XAI_API_KEY` | No | xAI API key for seed enrichment (web + X search) |
| `DOMAIN` | No | Production domain (default: `localhost`) |
| `MINIO_ENDPOINT` | Yes | MinIO for simulation artifact storage |
| `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | Yes | MinIO credentials |
| `OPENAI_API_KEY` | No | Optional embeddings fallback |
| `ALERT_WEBHOOK_URL` | No | Webhook URL for orphan pod / error alerts |

## Project Structure

```
saas/
  adapters/         # External LLM adapter (Anthropic Messages API)
  auth/             # Authentication: API, models, JWT, email verification
  billing/          # Credits: API, Stripe integration, ledger, credit packs
  jobs/             # Simulation lifecycle: API, runner, tasks, tasks_report (off-pod
                    #   report gen), recovery, persistence, enrichment, cleanup, alerts,
                    #   refund, export, share, report + report_tools_minio
  gpu/              # GPU providers: abstract base + RunPod implementation
  storage/          # MinIO client for simulation artifact upload/download
  constants/        # Tier config (credits, timeouts, costs)
  workers/          # Celery app + async utilities
  middleware/       # Error tracking middleware
  models/           # Base model class + re-exports for Alembic discovery
  config.py         # Pydantic Settings
  main.py           # FastAPI app factory
simswarm/           # Native swarm engine — entities, engine, belief, graph, report, envs
frontend/src/
  views/            # Pages (Landing, Dashboard, Wizard, Results, Account)
  components/       # Reusable components (graph/, wizard/, results/, data/)
  composables/      # Shared Composition API logic
  stores/           # Pinia (auth, credits)
  api/              # Axios clients
infra/docker/       # GPU worker image (Dockerfile.worker, run_job_v2.py, worker_api.py)
alembic/            # Database migrations
tests/              # pytest + pytest-asyncio (950+ tests)
```

## Simulation Tiers

| Tier | Agents | Credits | Timeout |
|------|--------|---------|---------|
| Small | 1--500 | 30 | 45 min |
| Medium | 501--2,000 | 90 | 5 hours |
| Large | 2,001--10,000 | 300 | 12 hours |

### Credit Packs

| Pack | Credits | Price |
|------|---------|-------|
| Starter | 100 | $19 |
| Pro | 500 | $79 |
| Heavy | 2,000 | $249 |

## Key Features

- **Four result views** — Story (narrative overview), Graph (interactive entity graph), Data (prediction market charts), Report (deep analysis with citations).
- **Off-pod report generation** — GPU pod uploads sim artifacts to MinIO and tears down; a Celery task then drives Claude Opus 4.6 through a tool-calling loop over the artifacts. Any failure before `COMPLETED` triggers a 100% credit refund.
- **Draft workflow** — Save partial simulations and resume later from any wizard step.
- **Seed enrichment** — Optionally enriches seed text with live web + X/Twitter research via xAI Grok. Toggle per-simulation, retry on failure.
- **Entity graph** — Interactive Cytoscape viz with per-agent activity stats and interaction edges (follow / reply / like / mention) extracted by `simswarm.graph`.
- **Belief dynamics** — Agent positions and confidence mutate per round via `simswarm.belief.update_beliefs` using trust-weighted exposure math.
- **Simulation data** — Market predictions, social posts, and trading data extracted from the GPU simulation's SQLite databases and uploaded to MinIO.
- **Deploy-safe recovery** — If a deploy kills the Celery worker mid-simulation, recovery auto-resumes jobs on their existing GPU pods, and re-enqueues orphaned `REPORTING`-state jobs.
- **Share links** — Public share URLs with OpenGraph meta tags for rich previews on Slack/Twitter/LinkedIn.
- **Error monitoring** — API exceptions and Celery failures captured to `error_events` table with auto-pruning.

## License

Proprietary.
