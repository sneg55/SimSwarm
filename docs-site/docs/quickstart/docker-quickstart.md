---
sidebar_label: Docker Quickstart
---

# Docker Quickstart

Bring up a full SimSwarm instance with Docker Compose. Every service in `docker-compose.yml` is started by a single `docker compose up`.

## 1. Clone the repository

```bash
git clone https://github.com/sneg55/SimSwarm.git
cd SimSwarm
```

## 2. Create your environment file

```bash
cp .env.example .env
```

Edit `.env` and fill in the values for your deployment. The variables that must be set for a working instance:

- `POSTGRES_PASSWORD`: password for the bundled Postgres container.
- `TEMPORAL_DB_PASSWORD`: password for the bundled Temporal Postgres container.
- `SECRET_KEY`: JWT signing key.
- `NEO4J_PASSWORD`: Neo4j password (the setting is required; no default).
- `RUNPOD_API_KEY`: needed by the worker to provision GPU pods.
- `ANTHROPIC_API_KEY`: used by the off-pod report-generation task.
- `MINIO_ENDPOINT` / `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY`: object storage for simulation artifacts.

`DOMAIN` defaults to `localhost`; set it to your hostname for automatic TLS via Caddy. See the [Environment Reference](../self-hosting/env-reference.md) for the complete list.

## 3. Build and start

```bash
docker compose build
docker compose up -d
```

The `migrate` service runs `alembic upgrade head` once on startup, and `frontend-init` copies the built frontend into the shared volume Caddy serves. After the stack is healthy, the app is reachable through Caddy on ports 80/443 (or directly on `127.0.0.1:8080` for the API).

## Services that start

| Service | Container | Role |
|---------|-----------|------|
| `app` | simswarm-api | FastAPI backend; exposed on `127.0.0.1:8080`, health at `/api/health`. |
| `celery` | simswarm-celery | Celery worker + beat scheduler; runs the off-pod report task and maintenance beats. |
| `db` | simswarm-db | PostgreSQL 16; application database (`fishcloud`). |
| `redis` | simswarm-redis | Redis 7; Celery broker and cache. |
| `temporal-db` | simswarm-temporal-db | Dedicated PostgreSQL 16 for Temporal's own state store. |
| `temporal` | simswarm-temporal | Temporal server (auto-setup) on `127.0.0.1:7233`; orchestrates the sim lifecycle. |
| `temporal-worker` | simswarm-temporal-worker | Runs `saas.workflows.worker`; hosts the `SimulationWorkflow` and its activities. |
| `caddy` | simswarm-caddy | Reverse proxy + automatic TLS on ports 80/443; serves the frontend. |
| `frontend-init` | simswarm-frontend-init | One-shot: copies `frontend/dist` into the shared `frontend_dist` volume. |
| `migrate` | simswarm-migrate | One-shot: runs `alembic upgrade head` against the app database. |

> Neo4j and MinIO are not part of `docker-compose.yml`. They are external services configured via `NEO4J_*` and `MINIO_*` environment variables. See [Neo4j](../self-hosting/neo4j.md) and [MinIO](../self-hosting/minio.md).

## Verify

```bash
docker compose ps
curl http://127.0.0.1:8080/api/health
```

A healthy API returns `{"status":"ok","version":"0.1.0","database":"connected"}`.
