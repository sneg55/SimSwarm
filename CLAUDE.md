# SimSwarm

SimSwarm is an open-source, self-hostable platform for swarm-intelligence simulations. Users upload a seed document, set a prediction goal, and get a report + chat replay + entity graph. The simulation engine is native Python (`simswarm/`).

## Tech Stack

- **Backend:** Python 3.11+, FastAPI, async SQLAlchemy + asyncpg, Celery + Redis, Alembic
- **Frontend:** Vue 3 (Composition API), Vite 6, Pinia, Tailwind CSS, Cytoscape.js
- **Database:** PostgreSQL 16 · **Graph:** Neo4j 5.15 Community
- **GPU:** RunPod spot instances (A100/H100/L40S), ephemeral per-job
- **Enrichment:** xAI Grok (web_search + x_search)
- **Orchestration:** Temporal (sim lifecycle + GPU provisioning) · **Object storage:** MinIO (S3-compatible)
- **CI/CD:** GitHub Actions → tests + Cloudflare Pages (static demo + docs)

## Repository Layout

```
saas/
  auth/               # Auth feature: api, models (User), schemas, service, email, profile
  jobs/               # Jobs feature: api, models (SimulationJob, ModelRouting, ErrorEvent), schemas,
                      #   runner, tasks, pipeline, persistence, market_derivation, enrichment,
                      #   progress, export, share, fetch, ai, cleanup, alerts, stale_detector
  gpu/                # GPU provider: abstract base, RunPod, errors
  adapters/           # Engine adapter layer
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
  stores/             # Pinia (auth, config)
  api/                # Axios clients
simswarm/             # Native swarm engine (entities, belief, graph, report, environments)
infra/                # Docker GPU worker, Neo4j, operational scripts
tests/                # pytest + pytest-asyncio
.claude/rules/        # Modular rules (testing, architecture, git, gpu-safety, deployment)
```

## Development Commands

```bash
# Backend
pip install -e ".[dev]"
uvicorn saas.main:create_app --factory --reload --port 8080
celery -A saas.workers.celery_app worker --loglevel=info

# Frontend
cd frontend && npm install && npm run dev
cd frontend && npm run build

# Tests
pytest                              # Backend (in-memory SQLite)
cd frontend && npm test             # Frontend (Vitest)
```
