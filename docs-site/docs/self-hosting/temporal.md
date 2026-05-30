---
sidebar_label: Temporal
---

# Temporal

Temporal owns the simulation lifecycle. The FastAPI app is a Temporal client; the actual orchestration runs in the `temporal-worker` service.

## Why Temporal

Before Temporal, the lifecycle had three independent actors (the main Celery task, a recovery beat task, and an orphan-cleanup beat task), each inferring the others' liveness from DB rows and pod HTTP responses. A deploy that killed the Celery task before the first heartbeat could leave a live GPU pod idle for hours. Temporal makes workflow liveness authoritative: the workflow state lives in Temporal's own store, not in heuristics.


## Where it runs

- **`temporal`**: the server (`temporalio/auto-setup`) on `127.0.0.1:7233`, namespace `fishcloud`, backed by the dedicated `temporal-db` Postgres container.
- **`temporal-worker`**: runs `python -m saas.workflows.worker`. It hosts `SimulationWorkflow` (`saas/workflows/sim_workflow.py`) and its activities (`saas/workflows/activities/`). Configured via `TEMPORAL_ADDRESS=temporal:7233` and `TEMPORAL_NAMESPACE=fishcloud`.

On job creation, `POST /api/jobs` starts the workflow with `id=sim-{job_id}` on the sim task queue.

## The workflow

`SimulationWorkflow.run` is pure orchestration over activities:

1. **Phase 1 (pre-GPU):** optional `enrich_seed` (when `enrich_web` is set) and `derive_markets`. A failure here marks the job FAILED explicitly, since no pod exists yet.
2. **Phase 2 (GPU lifecycle):** `provision_pod` → `wait_for_worker_health` → `submit_and_poll` → `upload_and_finalize`. The activities write user-visible state to Postgres synchronously.

The workflow has built-in resilience: a one-shot bad-host pod swap (vLLM never starts / silent host), pod-unreachable retries against the same pod (idempotent re-entry), and a one-shot pod swap when the LLM circuit breaker or slow-pod detector trips. Markers for these are defined in `saas/constants/tiers.py`.

## Cancel, not terminate

GPU teardown runs in the workflow's `finally` block. That `finally` only executes when the workflow is cancelled, not when it is terminated. `terminate` skips the cleanup path and would leave the pod billing. Always cancel a workflow:

```bash
temporal workflow cancel --workflow-id sim-<job_id>
```

Use `terminate` only as a last resort, knowing it will not run teardown and you must reap the pod manually.

## Inspecting a workflow

```bash
temporal workflow describe --workflow-id sim-<job_id>
```

The user-visible job status still lives in Postgres `simulation_jobs` (read by the API → frontend); Temporal owns workflow progress, retries, and heartbeats.
