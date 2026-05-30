---
sidebar_label: Prerequisites
---

# Prerequisites

What you need to run a self-hosted SimSwarm instance.

## Required

- **Docker and Docker Compose.** The whole application and orchestration stack runs from `docker-compose.yml`.
- **PostgreSQL 16.** The Compose stack ships two Postgres containers: `db` (application state) and `temporal-db` (Temporal's state store). Both use `postgres:16-alpine`.
- **Redis.** Shipped as the `redis:7-alpine` container; Celery broker and cache.
- **A RunPod account.** GPU pods are provisioned through the provider layer in `saas/gpu/`; **RunPod is the only GPU provider** — set `RUNPOD_API_KEY`. The abstract `GPUProvider` base class defines the interface if you want to add another (see [GPU Runner](./gpu-runner.md)).
- **An LLM for report generation.** Report generation uses the Anthropic Messages API; set `ANTHROPIC_API_KEY` (model defaults to `SMART_MODEL=claude-opus-4-6`).
- **MinIO (or any S3-compatible store).** Simulation artifacts and model weights are read/written via presigned URLs. Set `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, and `MINIO_SECRET_KEY`. If `MINIO_ENDPOINT` is empty, the storage layer is disabled and artifact URLs are not generated. See [MinIO](./minio.md).
- **Neo4j.** The `NEO4J_PASSWORD` setting is required (no default), with `NEO4J_URI` defaulting to `bolt://localhost:7687`. Neo4j backs the entity-graph view; see [Neo4j](./neo4j.md).

## On-pod LLM

The simulation engine runs a fast LLM (vLLM) on the GPU pod. The relevant settings are `LLM_API_KEY`, `LLM_BASE_URL` (default `http://localhost:8000/v1`), and `LLM_MODEL_NAME` (default `Qwen/Qwen3-14B`). The worker image does **not** bake the model weights — at pod start, `start.sh` pulls them from MinIO (`s3://$MINIO_BUCKET/models/hf-cache/*`), so no network/persistent volume is required.

No helper script ships for this upload yet. Before the first run you must upload the model's HuggingFace cache to the `models/hf-cache/` prefix in your MinIO bucket — the exact layout `start.sh` pulls from. Any S3-compatible client works; for example, with `s5cmd` (which the worker also uses):

```bash
AWS_ACCESS_KEY_ID="$MINIO_ACCESS_KEY" \
AWS_SECRET_ACCESS_KEY="$MINIO_SECRET_KEY" \
s5cmd --endpoint-url "https://$MINIO_ENDPOINT" \
      cp '/path/to/hf-cache/*' "s3://$MINIO_BUCKET/models/hf-cache/"
```

`/path/to/hf-cache/` must contain the standard `models--<org>--<model>/snapshots/{hash}/` tree with the `*.safetensors` shards (use `http://` instead of `https://` if `MINIO_SECURE` is `false`). If the MinIO env vars are missing or the pull fails, the pod falls back to a (much slower) HuggingFace download. See [MinIO → Model weights](./minio.md#model-weights).

## Optional

- **xAI Grok** (`XAI_API_KEY`) — enables seed enrichment with web and X search. Without it, enrichment is unavailable.
- **OpenAI** (`OPENAI_API_KEY`) — embeddings fallback.
- **Alert webhook** (`ALERT_WEBHOOK_URL`) — receives orphan-pod / error alerts.

## For local development

- **Node.js 20+** — frontend dev server and build.
- **Python 3.11+** — backend dev server, Celery, and tests.

See the [Environment Reference](./env-reference.md) for the full variable list.
