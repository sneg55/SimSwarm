---
sidebar_label: Architecture
---

# Architecture

SimSwarm is a small set of long-lived services plus ephemeral GPU pods. The Docker Compose stack runs the application and orchestration tier. Neo4j and MinIO are external services reached over the network.

## Component overview

```
Browser
   │  (HTTPS, ports 80/443)
   ▼
Caddy ──serves──► frontend (Vue build, frontend_dist volume)
   │  reverse-proxies /api
   ▼
app (FastAPI, 127.0.0.1:8080)
   │
   ├── PostgreSQL (db)  ── application state: users, jobs, model_routing
   ├── Redis            ── Celery broker + cache
   ├── Temporal (7233)  ── starts SimulationWorkflow on job creation
   ├── Neo4j (bolt://)  ── optional entity-graph storage
   └── MinIO (S3)       ── presigned upload/download URLs for sim artifacts

celery (worker + beat)
   └── off-pod report task + maintenance beats

temporal-worker  ── runs SimulationWorkflow + activities
   └── provisions/tears down ephemeral GPU pods (RunPod)
            │
            ▼
   GPU pod (vLLM + simswarm engine)
            └── uploads artifacts to MinIO, then is torn down
```

## How the services connect

- **app (FastAPI)** is the API surface. The router (`saas/router.py`) mounts health, jobs, auth, progress, export, share, fetch, profile, and AI routes under `/api`. It reads and writes application state in PostgreSQL, and on job creation it generates presigned MinIO URLs and starts a Temporal workflow.
- **celery** runs the worker with `--beat`. It owns the off-pod report-generation task (enqueued by a Temporal activity) and periodic maintenance beats. Its broker is Redis.
- **temporal** and **temporal-db** hold authoritative workflow state. The app is a Temporal client; it does not store workflow progress itself.
- **temporal-worker** hosts `SimulationWorkflow` and its activities. The activities provision a GPU pod, wait for the worker to be healthy, submit and poll the run, upload results, and always tear the pod down.
- **GPU pods** are ephemeral. The engine in `simswarm/` runs on the pod behind a worker API. Results land in MinIO and the pod is terminated.
- **Neo4j** (optional) backs the entity-graph view. **MinIO** stores per-job simulation artifacts and model weights.

See [Docker Compose](./docker-compose.md) for the per-service breakdown, [Temporal](./temporal.md) for the workflow, and [GPU Runner](./gpu-runner.md) for pod provisioning.
