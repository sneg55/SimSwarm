---
sidebar_label: Dev Setup
---

# Development Setup

SimSwarm is MIT-licensed and self-hostable. This page covers running the
backend and frontend locally for development. For a full deployment, see
[Self-Hosting](../self-hosting/architecture.md).

## Prerequisites

- Python 3.11+ (the project declares `requires-python = ">=3.11"` in
  `pyproject.toml`).
- Node.js + npm for the frontend.

You do **not** need Postgres, Redis, Temporal, Neo4j, or a GPU to run the test
suite — the backend tests use in-memory SQLite. You do need those services to
run real simulations end to end.

## Backend

Install the package in editable mode with the `dev` extra:

```bash
pip install -e ".[dev]"
```

Run the API with auto-reload (the app factory is `saas.main:create_app`):

```bash
uvicorn saas.main:create_app --factory --reload --port 8080
```

The API is mounted under `/api` (for example, `GET /api/health`).

Run the Celery worker (handles the off-pod report task and scheduled
maintenance):

```bash
celery -A saas.workers.celery_app worker --loglevel=info
```

In production the worker also runs the beat scheduler in the same process
(`--beat`, see `docker-compose.yml`); for local report-task development a plain
worker is usually enough.

## Frontend

The Vue 3 + Vite app lives in `frontend/`:

```bash
cd frontend && npm install && npm run dev
```

`npm run dev` runs Vite with `--host`. To produce a production build:

```bash
cd frontend && npm run build
```

## Configuration

Backend settings are read from environment variables / `.env` via Pydantic
Settings (`saas/config.py`). For tests, settings are constructed directly with
SQLite (see [Testing](testing.md)). For a real local run you will need the
relevant `DATABASE_URL`, `REDIS_URL`, Temporal, MinIO, and LLM variables — see
[Environment Reference](../self-hosting/env-reference.md).

## Before opening a PR

Per `CONTRIBUTING.md`: branch off `main`, keep PRs focused, never commit secrets
or infra hostnames/IPs, and run both backend and frontend tests. The engine
lives in `simswarm/`; the application wrapper lives in `saas/`.

## Related

- [Testing](testing.md) — running pytest and Vitest.
- [Repository Structure](repo-structure.md) — where code lives.
- [Code Style](code-style.md) — conventions to follow.
