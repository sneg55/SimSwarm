# SimSwarm

Swarm intelligence simulations. Upload a document, set a prediction goal, and watch AI agents debate, trade, and publish across a simulated ecosystem. Get a deep analysis report, entity knowledge graph, prediction market data, and full chat replay.

SimSwarm is open source and self-hostable. A read-only public demo (a static snapshot) runs at [simswarm.xyz](https://simswarm.xyz). Self-host with `DEMO_MODE=true` to run your own instance in the same read-only mode.

**Live demo: [simswarm.xyz](https://simswarm.xyz)  ·  Documentation: [docs.simswarm.xyz](https://docs.simswarm.xyz)**

## Architecture

```
Frontend (Vue 3 + Vite + Tailwind)
        |
SaaS API (FastAPI)
        |
   +----------+-----------+-----------+
   |                      |           |
Temporal Worker     PostgreSQL    Redis
   |
   +-- sim_workflow (Temporal) — owns full sim lifecycle + GPU provisioning
   |        |
   |        +-- GPU Workers (RunPod spot) -- simswarm engine + vLLM (Qwen3-14B)
   |                 |
   |                 +-- artifacts → MinIO (chat_log, posts, trades, graph)
   |
   +-- generate_report_task (Celery task, Redis broker; enqueued by a Temporal activity) -- Claude Opus 4.6 (Anthropic Messages API)
```

| Layer | Technology |
|-------|-----------|
| Frontend | Vue 3 (Composition API), Vite 6, Pinia, Tailwind CSS, Cytoscape.js |
| Backend | Python 3.11+, FastAPI, async SQLAlchemy + asyncpg, Celery + Redis (report task), Alembic |
| Orchestration | Temporal — owns sim lifecycle, GPU provisioning, and activity retries |
| Database | PostgreSQL 16 |
| Engine | `simswarm/` — native async Python swarm engine |
| GPU | RunPod spot instances (H100/L40S/A100), ephemeral per-job |
| Fast LLM | Qwen3-14B via vLLM on-pod with tool calling (hermes parser) |
| Smart LLM | Claude Opus 4.6 via Anthropic Messages API (off-pod, report gen) |
| Enrichment | xAI Grok (web_search + x_search) |
| Object storage | MinIO (S3-compatible) for simulation artifacts |
| Proxy | Caddy with automatic TLS, security headers, SSRF protection |
| CI/CD | GitHub Actions — on push: tests + Cloudflare Pages deploys (static demo + docs). Worker-image build and single-VPS deploy are manual (`workflow_dispatch`). |

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
#   POSTGRES_PASSWORD, SECRET_KEY, RUNPOD_API_KEY, NEO4J_PASSWORD, DOMAIN

# 3. Build and run
docker compose build
docker compose run --rm migrate    # run database migrations
docker compose up -d               # start all services
```

The app will be available at `http://localhost` (or your configured `DOMAIN`).

> Neo4j and MinIO are **not** in the Compose stack — they're external services. You also need a RunPod key for GPU pods, and the model weights must be uploaded to MinIO before the first run. See the full **[self-hosting guide](https://docs.simswarm.xyz/self-hosting/architecture)** for the complete walkthrough.

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
# Backend tests (1000+ tests, in-memory SQLite — no external DB needed)
pytest

# Frontend tests (Vitest)
cd frontend && npm test
```

## Deployment

**Self-hosting** is the Docker Compose stack above — see the [Quick Start](#quick-start-docker) and the [self-hosting docs](https://docs.simswarm.xyz/self-hosting/architecture). It brings up the API, Celery, Temporal worker, Postgres, Redis, and Caddy; you supply a RunPod key for GPU pods and an S3-compatible store (MinIO) for artifacts.

**This repo's hosted surfaces** deploy automatically on push to `main` via GitHub Actions, both to Cloudflare Pages:

- `simswarm.xyz` — a static, read-only demo snapshot (`deploy-pages.yml`)
- `docs.simswarm.xyz` — this documentation (`deploy-docs.yml`)

A single-VPS deploy script (`deploy.sh`) and the GPU worker-image build remain available as manual (`workflow_dispatch`) workflows. `deploy.sh` validates a single Alembic head, gracefully stops Celery, runs migrations, rebuilds frontend assets, and health-checks the API.

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `SECRET_KEY` | Yes | JWT signing key |
| `POSTGRES_PASSWORD` | Yes | Database password (used by docker-compose) |
| `NEO4J_PASSWORD` | Yes | Neo4j graph database password |
| `RUNPOD_API_KEY` | Yes | RunPod GPU provisioning |
| `ANTHROPIC_API_KEY` | Yes | Claude Opus 4.6 for report generation |
| `SMART_MODEL` | No | Report model override (default: `claude-opus-4-6`) |
| `DEMO_MODE` | No | Set `true` for read-only demo (disables signup + job submission) |
| `XAI_API_KEY` | No | xAI API key for seed enrichment (web + X search) |
| `DOMAIN` | No | Production domain (default: `localhost`) |
| `MINIO_ENDPOINT` | Yes | MinIO for simulation artifact storage |
| `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | Yes | MinIO credentials |
| `OPENAI_API_KEY` | No | Optional embeddings fallback |
| `ALERT_WEBHOOK_URL` | No | Webhook URL for orphan pod / error alerts |

Full variable reference: **[docs.simswarm.xyz/self-hosting/env-reference](https://docs.simswarm.xyz/self-hosting/env-reference)**.

## Project Structure

```
saas/
  adapters/         # External LLM adapter (Anthropic Messages API)
  auth/             # Authentication: API, models, JWT, email verification
  jobs/             # Simulation lifecycle: API, runner, tasks, tasks_report (off-pod
                    #   report gen), recovery, persistence, enrichment, cleanup, alerts,
                    #   export, share, report + report_tools_minio
  gpu/              # GPU providers: abstract base + RunPod implementation
  storage/          # MinIO client for simulation artifact upload/download
  constants/        # Tier config (timeouts, etc.)
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
  stores/           # Pinia (auth, config)
  api/              # Axios clients
infra/docker/       # GPU worker image (Dockerfile.worker, run_job_v2.py, worker_api.py)
alembic/            # Database migrations
tests/              # pytest + pytest-asyncio (1000+ tests)
```

## Simulation Tiers

Three tiers (`small` / `medium` / `large`) set the GPU class and timeout. Agent count, model, GPU type, and round count are operator-configurable **per tier** via the `model_routing` table — they are not fixed by the tier itself.

| Tier | Timeout | Default GPU cloud |
|------|---------|-------------------|
| Small | 45 min | ALL |
| Medium | 5 hours | ALL |
| Large | 12 hours | SECURE |

See [GPU Runner](https://docs.simswarm.xyz/self-hosting/gpu-runner) for tier configuration and routing.

## Key Features

- **Four result views** — Story (narrative overview), Graph (interactive entity graph), Data (prediction market charts), Report (deep analysis with citations).
- **Off-pod report generation** — GPU pod uploads sim artifacts to MinIO and tears down; a Celery task then drives Claude Opus 4.6 through a tool-calling loop over the artifacts. Any failure before `COMPLETED` marks the job FAILED.
- **Draft workflow** — Save partial simulations and resume later from any wizard step.
- **Seed enrichment** — Optionally enriches seed text with live web + X/Twitter research via xAI Grok. Toggle per-simulation, retry on failure.
- **Entity graph** — Interactive Cytoscape viz with per-agent activity stats and interaction edges (follow / reply / like / mention) extracted by `simswarm.graph`.
- **Belief dynamics** — Agent positions and confidence mutate per round via `simswarm.belief.update_beliefs` using trust-weighted exposure math.
- **Simulation data** — Market predictions, social posts, and trading data extracted from the GPU simulation's SQLite databases and uploaded to MinIO.
- **Deploy-safe recovery** — If a deploy kills the Celery worker mid-simulation, recovery auto-resumes jobs on their existing GPU pods, and re-enqueues orphaned `REPORTING`-state jobs.
- **Share links** — Public share URLs with OpenGraph meta tags for rich previews on Slack/Twitter/LinkedIn.
- **Error monitoring** — API exceptions and Celery failures captured to `error_events` table with auto-pruning.

## Documentation

Full documentation — concepts, self-hosting, engine internals, and API reference — lives at **[docs.simswarm.xyz](https://docs.simswarm.xyz)**:

- [What is SimSwarm](https://docs.simswarm.xyz/introduction/what-is-simswarm) · [Lineage vs MiroFish/MiroShark](https://docs.simswarm.xyz/introduction/lineage-and-differences)
- [Quickstart](https://docs.simswarm.xyz/quickstart/docker-quickstart) · [Self-Hosting](https://docs.simswarm.xyz/self-hosting/architecture)
- [Engine Internals](https://docs.simswarm.xyz/engine/architecture) (belief dynamics, environments, story signals, graph build)
- [API Reference](https://docs.simswarm.xyz/api/simswarm)

## License

MIT — see [LICENSE](LICENSE).
