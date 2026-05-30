---
sidebar_label: Docker Compose
---

# Docker Compose

A walk-through of every service block in `docker-compose.yml`. All long-lived services use `restart: unless-stopped`; the two one-shot services use `restart: "no"`.

## `app`

FastAPI backend. Built from the repo `Dockerfile` as image `fishcloud-app` (container `simswarm-api`). Reads `.env` via `env_file`, plus a `DATABASE_URL` pointing at the `db` service and `REDIS_URL` at `redis`. Published on `127.0.0.1:8080`. Depends on `db` and `redis` being healthy. Health check hits `http://localhost:8080/api/health`. Runs with `no-new-privileges`.

## `celery`

Reuses the `fishcloud-app` image (container `simswarm-celery`). Command:

```
celery -A saas.workers.celery_app worker --beat --loglevel=info --concurrency=4
```

The health check verifies both that the worker responds to `inspect ping` and that the beat scheduler is running (it greps `/proc/1/cmdline` for `beat`, catching a missing `--beat` flag). Depends on `db` and `redis`.

## `db`

`postgres:16-alpine` (container `simswarm-db`). User/DB `fishcloud`, password from `POSTGRES_PASSWORD`. Data persisted in the `pgdata` volume. Health check: `pg_isready -U fishcloud`.

## `redis`

`redis:7-alpine` (container `simswarm-redis`). Health check: `redis-cli ping`.

## `temporal-db`

`postgres:16-alpine` (container `simswarm-temporal-db`), dedicated to Temporal. User/DB `temporal`, password from `TEMPORAL_DB_PASSWORD`. Data in the `temporaldata` volume. Health check: `pg_isready -U temporal`.

## `temporal`

`temporalio/auto-setup:1.22.7` (container `simswarm-temporal`). Configured to use `temporal-db` (`DB=postgres12`, `POSTGRES_SEEDS=temporal-db`) and a default namespace of `fishcloud`. Published on `127.0.0.1:7233`. Depends on `temporal-db` healthy. Health check runs `tctl --address $HOSTNAME:7233 cluster health` (the frontend binds to the container IP, not `127.0.0.1`).

## `temporal-worker`

Reuses `fishcloud-app` (container `simswarm-temporal-worker`). Command:

```
python -m saas.workflows.worker
```

Environment adds `TEMPORAL_ADDRESS=temporal:7233` and `TEMPORAL_NAMESPACE=fishcloud`. Depends on `db` healthy and `temporal` healthy. Runs with `no-new-privileges`. This is where `SimulationWorkflow` and its activities execute.

## `caddy`

`caddy:2-alpine` (container `simswarm-caddy`). Publishes ports `80` and `443`. Mounts the repo `Caddyfile`, the shared `frontend_dist` volume (to serve the built frontend), and `caddy_data` / `caddy_config` volumes. `DOMAIN` defaults to `localhost`. Depends on `app`.

## `frontend-init` (one-shot)

Reuses `fishcloud-app` (container `simswarm-frontend-init`). Command:

```
cp -r /app/frontend/dist/. /srv/frontend/
```

Copies the built frontend into the shared `frontend_dist` volume that Caddy serves, then exits. `restart: "no"`.

## `migrate` (one-shot)

Reuses `fishcloud-app` (container `simswarm-migrate`). Command:

```
alembic upgrade head
```

Depends on `db` healthy, then applies migrations and exits. `restart: "no"`. See [Migrations](./migrations.md).

## Volumes

`pgdata`, `temporaldata`, `caddy_data`, `caddy_config`, `frontend_dist`.
