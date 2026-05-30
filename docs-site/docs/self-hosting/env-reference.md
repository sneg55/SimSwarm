---
sidebar_label: Environment Reference
---

# Environment Reference

Every variable below comes from `.env.example`, `saas/config.py` (`Settings`), or `docker-compose.yml`. No variable here is invented. Where `.env.example` ships a literal value it is quoted in the Default column; where a value is environment-specific (keys, passwords) it is marked **Required** or described.

## Core

| Variable | Purpose | Default / Required |
|----------|---------|--------------------|
| `DATABASE_URL` | PostgreSQL connection string (asyncpg driver). Compose overrides this to point at the `db` service. | Required (`.env.example`: `postgresql+asyncpg://fishcloud:fishcloud@localhost:5432/fishcloud`) |
| `SECRET_KEY` | JWT signing key. | Required (`.env.example`: `change-me-in-production`) |
| `POSTGRES_PASSWORD` | Password for the bundled Postgres container. Used by `docker-compose`. | Required (`.env.example`: `change-me`) |
| `DEMO_MODE` | `true` = read-only public demo (blocks register / create-job / launch-draft with 403). | `false` |

## On-pod LLM (vLLM)

| Variable | Purpose | Default / Required |
|----------|---------|--------------------|
| `LLM_API_KEY` | API key for the on-pod fast LLM. | Required (`.env.example`: `not-needed`) |
| `LLM_BASE_URL` | Base URL for the on-pod LLM. | `http://localhost:8000/v1` |
| `LLM_MODEL_NAME` | On-pod model name. | `Qwen/Qwen3-14B` |

## Neo4j graph database

| Variable | Purpose | Default / Required |
|----------|---------|--------------------|
| `NEO4J_URI` | Bolt connection URI. | `bolt://localhost:7687` |
| `NEO4J_USER` | Neo4j username. | `neo4j` |
| `NEO4J_PASSWORD` | Neo4j password. Required Settings field (no default). | Required (`.env.example`: `change-me`) |

## Report generation (Anthropic)

| Variable | Purpose | Default / Required |
|----------|---------|--------------------|
| `ANTHROPIC_API_KEY` | API key for off-pod report generation. | `""` (`.env.example`: `your_anthropic_key`) |
| `SMART_PROVIDER` | Provider for the report (smart) model. Settings only; not in `.env.example`. | `anthropic` |
| `SMART_MODEL` | Report model name. | `claude-opus-4-6` |

## GPU provider

| Variable | Purpose | Default / Required |
|----------|---------|--------------------|
| `RUNPOD_API_KEY` | RunPod provisioning key. Read via `os.getenv`, not `Settings`; needed by the worker. | Required (`.env.example`: `your_runpod_key`) |

## MinIO object storage

| Variable | Purpose | Default / Required |
|----------|---------|--------------------|
| `MINIO_ENDPOINT` | MinIO host:port. Empty disables the storage layer. | `""` (`.env.example`: `localhost:9000`) |
| `MINIO_ACCESS_KEY` | MinIO access key. | `""` (`.env.example`: `your_minio_key`) |
| `MINIO_SECRET_KEY` | MinIO secret key. | `""` (`.env.example`: `your_minio_secret`) |
| `MINIO_BUCKET` | Bucket for sim artifacts. | `simswarm` |
| `MINIO_SECURE` | Use TLS for MinIO connections. | `true` |
| `MINIO_PROXY_BASE` | Optional HTTPS proxy base to rewrite download URLs (e.g. `https://simswarm.xyz/minio`). | `""` |

## Temporal

| Variable | Purpose | Default / Required |
|----------|---------|--------------------|
| `TEMPORAL_ADDRESS` | Temporal frontend address. Read via `os.getenv`. | `temporal:7233` |
| `TEMPORAL_NAMESPACE` | Temporal namespace. Read via `os.getenv`. | `fishcloud` |
| `TEMPORAL_DB_PASSWORD` | Password for the bundled Temporal Postgres container. Used by `docker-compose`. | Required (`.env.example`: `change-me`) |

## Seed limits (Settings only)

| Variable | Purpose | Default / Required |
|----------|---------|--------------------|
| `MAX_SEED_CHARS` | Maximum seed-text length. Settings only; not in `.env.example`. | `50000` |
| `MAX_SIMULATION_ROUNDS` | Maximum simulation rounds. Settings only; not in `.env.example`. | `200` |

## Worker image

| Variable | Purpose | Default / Required |
|----------|---------|--------------------|
| `WORKER_IMAGE_REPO` | GPU worker image repository. | `ghcr.io/sneg55/simswarm-worker` |
| `WORKER_IMAGE_TAG` | GPU worker image tag. | `latest` |

## Optional

| Variable | Purpose | Default / Required |
|----------|---------|--------------------|
| `XAI_API_KEY` | xAI Grok key for seed enrichment (web + X search). | `""` |
| `OPENAI_API_KEY` | Embeddings fallback. | `""` |
| `ALERT_WEBHOOK_URL` | Webhook for orphan-pod / error alerts. | `""` |
| `LOG_FORMAT` | Log format: `json` or `text`. | `json` |
| `DOMAIN` | Caddy hostname for TLS. Used by `docker-compose` (`caddy` service). Not a `Settings` field. | `localhost` |

> `DATABASE_URL` and `REDIS_URL` are set inline by `docker-compose.yml` for the `app`, `celery`, and `temporal-worker` services, pointing at the `db` and `redis` containers. `REDIS_URL` is not a `Settings` field and has no `.env.example` entry.
