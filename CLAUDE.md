# Project Instructions

## Memory System

You have a persistent, file-based memory system. Build it up over time so future conversations have a complete picture of who the user is, how they'd like to collaborate, what behaviors to avoid or repeat, and the context behind the work.

If the user explicitly asks you to remember something, save it immediately as whichever type fits best. If they ask you to forget something, find and remove the relevant entry.

## Types of Memory

There are four discrete types. Only save information that is NOT derivable from the current project state (code, git history, file structure).

### user
**What it stores:** Information about the user's role, goals, responsibilities, and knowledge.
**When to save:** When you learn any details about the user's role, preferences, responsibilities, or knowledge.
**How to use:** Tailor your behavior to the user's profile. Collaborate with a senior engineer differently than a first-time coder. Frame explanations relative to their domain knowledge.

### feedback
**What it stores:** Guidance the user has given about how to approach work — both what to avoid AND what to keep doing.
**When to save:** Any time the user corrects your approach OR confirms a non-obvious approach worked. Corrections are easy to notice; confirmations are quieter — watch for them.
**How to use:** Let these memories guide your behavior so the user doesn't need to offer the same guidance twice.
**Structure:** Lead with the rule, then a **Why:** line and a **How to apply:** line.

### project
**What it stores:** Information about ongoing work, goals, initiatives, bugs, or incidents NOT derivable from code or git history.
**When to save:** When you learn who is doing what, why, or by when. Always convert relative dates to absolute.
**How to use:** Understand broader context behind the user's requests, anticipate coordination issues, make better suggestions.
**Structure:** Lead with the fact/decision, then **Why:** and **How to apply:** lines.

### reference
**What it stores:** Pointers to where information lives in external systems.
**When to save:** When you learn about resources in external systems and their purpose.
**How to use:** When the user references an external system or you need external info.

## What NOT to Save

- Code patterns, conventions, architecture, file paths, or project structure — derivable by reading the project
- Git history, recent changes, who-changed-what — `git log` / `git blame` are authoritative
- Debugging solutions or fix recipes — the fix is in the code, commit message has context
- Anything already documented in CLAUDE.md files
- Ephemeral task details: in-progress work, temporary state, current conversation context

## Memory File Format

Each memory is its own `.md` file with YAML frontmatter:

```markdown
---
name: {{memory name}}
description: {{one-line description — be specific}}
type: {{user, feedback, project, reference}}
---

{{memory content}}
```

### Saving Process
1. Write the memory to its own file
2. Add a one-line pointer in `MEMORY.md`: `- [Title](file.md) — one-line hook`
3. Keep `MEMORY.md` under 200 lines

### Before Recommending from Memory

A memory that names a specific function, file, or flag may be outdated. Before recommending:
- If it names a file path: check the file exists
- If it names a function or flag: grep for it
- If the user is about to act on your recommendation: verify first

---

## Git Safety

- Never force push
- Never skip hooks
- Never commit secrets
- Use heredoc syntax for multi-line commit messages

---

## Project-Specific Instructions

### Overview

SimSwarm — a fully managed SaaS wrapping the open-source MiroShark swarm intelligence engine. Users buy credits, upload a seed document, set a prediction goal, and get a report + chat replay + entity graph.

### Tech Stack

- **Backend:** Python 3.11+, FastAPI, async SQLAlchemy + asyncpg, Celery + Redis, Alembic migrations
- **Frontend:** Vue 3 (Composition API), Vite 6, Pinia, Tailwind CSS, Cytoscape.js
- **Database:** PostgreSQL 16
- **Graph:** Neo4j 5.15 Community on dedicated VPS (simswarm-2)
- **GPU:** RunPod spot instances (A100/H100/L40S), ephemeral per-job
- **Enrichment:** xAI Grok (web_search + x_search) for seed research
- **Billing:** Stripe one-time credit packs (DB-configurable)
- **Proxy:** Caddy with automatic TLS
- **CI/CD:** GitHub Actions → SSH deploy to Hetzner

### Repository Layout

```
saas/                   # FastAPI backend
  api/                  #   auth.py, jobs.py, billing.py, export.py, progress.py, health.py
  auth/                 #   JWT auth, email verification
  billing/              #   credit_packs.py, ledger.py, stripe_service.py
  gpu/                  #   provider.py (abstract), runpod_provider.py, failover.py
  models/               #   user.py, job.py, credit_entry.py, model_routing.py
  workers/              #   celery_app.py, job_runner.py, tasks.py
  adapters/             #   MiroShark engine adapter
  config.py             #   Pydantic Settings (env vars)
  database.py           #   Async SQLAlchemy engine/session
  main.py               #   FastAPI app factory
frontend/src/
  views/                #   Landing, Login, Register, Dashboard, NewSimulation, SimulationStatus, SimulationResults, DemoResult, Account
  components/           #   graph/ (Cytoscape viz), CreditBadge, ChatReplay, etc.
  composables/          #   Shared logic (useSimulationData)
  stores/               #   Pinia (auth, credits)
  api/                  #   Axios clients (auth, billing, jobs, demos)
vendor/miroshark/       # MiroShark engine (git submodule, AGPL-3.0)
infra/docker/           # GPU worker image (Dockerfile, run_job.py, worker_api.py)
infra/neo4j/            # Neo4j VPS docker-compose
infra/scripts/          # benchmark.py, refresh_demos.py, run_demos.py
tests/                  # pytest + pytest-asyncio
docs/superpowers/       # Specs and implementation plans
```

### Development Commands

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

### Testing Conventions

- Backend tests use `pytest-asyncio` with `asyncio_mode = "auto"`
- Test database: in-memory SQLite via `aiosqlite` (no external DB needed)
- Fixtures in `tests/conftest.py`: `client` (async httpx), `db_session`, `auth_headers`, `funded_user`, `seeded_routing`
- Ruff for linting, line length 100

### Key Patterns

- **App factory:** `saas.main:create_app()` — accepts optional `Settings` for testing
- **Dependency injection:** `saas.database:get_session` is overridden in tests
- **Credit gating:** Job creation checks balance, returns 402 if insufficient
- **Job lifecycle:** API → Celery task → RunPod GPU provision → MiroShark pipeline → store results → teardown GPU
- **Rate limiting:** slowapi limiter, reset in test fixtures
- **Model routing:** Operator-configurable `model_routing` DB table maps tier → GPU/model/params
- **DB writes from Celery:** Always use sync psycopg2, never the shared async pool (prevents InterfaceError)

### Important Rules

- Never generate fake or mock data for demos or feature testing. Only use real data from actual simulation runs. Exception: unit/integration test mocks are fine.
- MiroShark engine code in `vendor/miroshark/` should not be modified directly — use the adapter layer in `saas/adapters/`.
- Credit pack prices are fixed; adjust credit consumption per tier if margins are off.
- GPU instances are ephemeral — always ensure teardown happens (even on failure).

### Deployment

- Push to `main` triggers GitHub Actions deploy (`.github/workflows/deploy.yml`)
- Deploys via SSH to Hetzner VPS at `/opt/fishcloud`
- Neo4j runs on separate VPS (simswarm-2) at `bolt://87.99.143.119:7687`
- Services: app, celery, db, redis, caddy, migrate (one-shot), frontend-init (one-shot)
- Environment variables configured in `.env` on server (not in repo)
