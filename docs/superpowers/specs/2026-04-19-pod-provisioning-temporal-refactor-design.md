# Pod Provisioning: Temporal Refactor

Ground-up rewrite of the sim orchestration layer. Replaces the current Celery + beat-task recovery + heuristic-driven liveness inference with a Temporal workflow. Prompted by sim #120 on 2026-04-19: a deploy killed the main Celery task ~9 min after dispatch, leaving the pod healthy but idle for 3 h 40 m while `recover_stale_jobs` silently skipped it on the (wrong) heuristic that `PROVISIONING + no heartbeat = main task still in wait_for_worker_health`.

## Problem Statement

Today the sim lifecycle has three independent actors, each inferring the others' liveness from circumstantial evidence:

1. **Main Celery task** (`run_simulation_task`) — provisions, waits, polls, terminates. Owns the pod from `pod_id_callback` through the `finally` block.
2. **Recovery beat task** (`recover_stale_jobs`, every 10 min) — looks at `last_heartbeat`, `created_at`, pod reachability, and *guesses* whether the main task is still running. Decides to resume, fail, or stay out of the way.
3. **Cleanup beat task** (`cleanup_orphaned_pods`, every 10 min) — scans RunPod, terminates pods whose `pod_id` doesn't match a live job row.

Each actor has its own heuristic (`HEARTBEAT_FRESH_S = 180`, `HEARTBEAT_STALE_NO_PROGRESS_S = 900`, `HEARTBEAT_STALE_POD_DEAD_S = 300`, `GRACE_PERIOD_SECONDS = 600`). None of them can actually ask Celery "is this task alive right now?" — they infer it from DB rows and pod HTTP responses. The broker's `visibility_timeout = 86 400 s` (24 h) means a redelivery after a deploy-kill doesn't fire for 24 h.

The deploy-kill-before-first-heartbeat case falls through every guard and parks a live pod consuming GPU credit until the tier timeout fires hours later.

## Goals

- Move the sim lifecycle onto a workflow engine that owns task liveness authoritatively.
- Delete every heuristic in `recovery.py`, `recovery_utils.py`, `tasks_resume.py`.
- Keep Postgres as the app read-state (API reads from `simulation_jobs` as today); move authoritative workflow state to Temporal's own store.
- Self-hosted — no cloud services.
- Flag-day cutover; no feature flag; rollback = revert commit.

## Non-Goals

- Multi-tenant / multi-region. Same single-VPS deployment.
- Replacing Celery. Celery keeps running enrichment retries, maintenance, alerts, and `generate_report_task`.
- Priority queues per tier. Single workflow task queue; priority can be added later via Temporal's native priority field.

## Architecture

### New services in `docker-compose.yml` on Hetzner VPS

- **`temporal-server`** — `temporalio/auto-setup` image (dev-friendly) or `temporalio/server` + manual schema setup. Listens on `7233` (gRPC). Not exposed externally.
- **`temporal-db`** — dedicated `postgres:16` container, separate from the existing `db` service. Volume-backed, included in VPS backup scripts.
- **`simswarm-temporal-worker`** — new service running the Python SDK worker process. Hosts all activity implementations and the `SimulationWorkflow` class.

### Unchanged services

- `app` (FastAPI) — now dispatches workflows via the Temporal Python client instead of `run_simulation_task.delay(...)`.
- `simswarm-celery` — keeps running beat tasks (`cleanup_orphaned_pods`, `prune_error_events`) and non-sim Celery tasks (`enrich_retry_task`, `generate_report_task`, email alerts).
- `db`, `redis`, `caddy`, `migrate`, `frontend-init` — untouched.

### Process topology

```
FastAPI POST /jobs
   │
   └─ temporal_client.start_workflow(SimulationWorkflow.run, …, id="sim-{job_id}", task_queue="sim-queue")
            │
            ▼
   ┌──────────────────────┐
   │  temporal-server     │  (state in temporal-db)
   └──────────────────────┘
            │
            ▼
   simswarm-temporal-worker  ← picks up workflow task
       executes activities:
         enrich_seed          (Celery-side module, imported)
         derive_markets
         provision_pod        (calls RunPod provider)
         wait_for_worker_health
         submit_and_poll
         upload_and_finalize  (MinIO + enqueue generate_report_task)
         terminate_pod        (always)
         refund_credits       (saga compensation on failure)
```

### Sources of truth

| State | Owner | Read by |
|---|---|---|
| Workflow progress (which activity, retries, heartbeats) | Temporal | Operators (`temporal` CLI) |
| Sim user-visible state (`status`, `pipeline_stage`, `pod_id`, `result_*`, `completed_at`) | Postgres `simulation_jobs` | FastAPI → frontend |
| Credit ledger | Postgres `credit_entries` | API, billing |
| Pod lifecycle | RunPod API | Activities, `cleanup_orphaned_pods` safety net |

Activities write to `simulation_jobs` synchronously via `psycopg2` (respects existing sync-DB-writes-from-workers rule). Temporal does not replace Postgres for the app; it replaces Celery+recovery+resume for orchestration.

## Workflow

### `SimulationWorkflow`

```python
@workflow.defn
class SimulationWorkflow:
    @workflow.run
    async def run(self, params: SimParams) -> SimResult:
        # Phase 1: pre-GPU work (can fail-soft)
        enriched_seed = await workflow.execute_activity(
            enrich_seed, params.seed_text, params.goal,
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )  # returns the concatenated seed text; writes enrichment fields to DB as a side-effect
        markets = await workflow.execute_activity(
            derive_markets, params.goal, enriched_seed, params.tier,
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )

        # Phase 2: GPU lifecycle (pod teardown guaranteed)
        pod = await workflow.execute_activity(
            provision_pod, params, markets,
            start_to_close_timeout=timedelta(minutes=10),
            heartbeat_timeout=timedelta(seconds=60),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=30),
                maximum_attempts=3,
                non_retryable_error_types=["GPUQuotaExceeded", "InvalidConfig"],
            ),
        )
        try:
            await workflow.execute_activity(
                wait_for_worker_health, pod.id,
                start_to_close_timeout=timedelta(minutes=15),
                heartbeat_timeout=timedelta(seconds=30),
            )
            result = await workflow.execute_activity(
                submit_and_poll, pod.id, params, markets,
                start_to_close_timeout=timedelta(seconds=TIER_TIMEOUTS[params.tier]),
                heartbeat_timeout=timedelta(seconds=180),
            )
            await workflow.execute_activity(
                upload_and_finalize, params.job_id, result,
                start_to_close_timeout=timedelta(minutes=10),
                heartbeat_timeout=timedelta(seconds=60),
            )
            return result
        except Exception:
            await workflow.execute_activity(
                refund_credits, params.job_id, params.user_id, params.credits_charged,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=5),
            )
            raise
        finally:
            await workflow.execute_activity(
                terminate_pod, pod.id,
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(maximum_attempts=5),
            )
```

**Workflow ID:** `sim-{job_id}`. Uniqueness guaranteed by Temporal; a second `start_workflow` call with the same ID raises `WorkflowAlreadyStartedError`, which replaces the current `idempotency preamble` in `tasks.py:77-104`.

**Retries for the workflow itself:** handled by user retry UI (the existing `retry_of` column). Temporal workflow doesn't auto-restart on `refund_credits` success.

### Activities

| Activity | `start_to_close` | `heartbeat` | Grounding |
|---|---|---|---|
| `enrich_seed` | 60 s | — | `enrichment.py:49` per-call timeout=30 s; gives room for one retry |
| `derive_markets` | 60 s | — | `market_derivation.py:27` `_LLM_TIMEOUT_SECONDS = 20`; gives room for one retry |
| `provision_pod` | 10 min | 60 s | `runpod_provider.py:13` `MAX_POLL_ATTEMPTS = 120 × 5 s = 600 s` |
| `wait_for_worker_health` | 15 min | 30 s | `pipeline.py:47` `range(180) × 5 s = 900 s` |
| `submit_and_poll` | `TIER_TIMEOUTS[tier]` | 180 s | `tiers.py:4` (small 2700 s / medium 18 000 s / large 43 200 s); heartbeat = 3 × existing `HEARTBEAT_INTERVAL_S = 60 s` |
| `upload_and_finalize` | 10 min | 60 s | **Conservative, tune during rollout.** MinIO upload + `generate_report_task.apply_async` |
| `terminate_pod` | 2 min | — | **Conservative, tune during rollout.** Single RunPod API call with retry budget |
| `refund_credits` | 30 s | — | **Conservative, tune during rollout.** Single sync DB insert |

**Activity idempotency rules** (required because Temporal may retry any activity):

- `enrich_seed`, `derive_markets` — pure functions of inputs; safe to retry.
- `provision_pod` — before creating a new pod, check `simulation_jobs.pod_id` for this `job_id`. If already set and the pod is alive, return the existing pod info. Otherwise create, then write `pod_id` in the same DB call that returns.
- `wait_for_worker_health` — pure HTTP poll; safe to retry.
- `submit_and_poll` — check pod `/status` first. If `running` or `completed`, resume polling from current state instead of re-POSTing `/job`. This subsumes the current `runner.py:198-207` "idle pod, resubmit" logic.
- `upload_and_finalize` — MinIO uploads are idempotent (key-based overwrite). Double-enqueue of `generate_report_task` is tolerated because that task itself must guard terminal jobs (`status in {COMPLETED, FAILED, REFUNDED} → skip`); this refactor requires that guard to exist (currently absent — adding it is part of the implementation plan).
- `terminate_pod` — RunPod's `terminate_pod` is idempotent ("pod not found" = success); activity swallows that error.
- `refund_credits` — uses the existing `NOT EXISTS` guard pattern from `recovery.py:211-215`.

### Activity DB writes (status progression)

Each activity writes the `simulation_jobs` status and `pipeline_stage` via sync psycopg2 on entry/exit. No change to the API's read path.

| Activity | Writes on entry | Writes on success |
|---|---|---|
| `enrich_seed` | — | `enriched_seed`, `enrichment_citations` |
| `derive_markets` | — | `markets_config` |
| `provision_pod` | `status='PROVISIONING'`, `pipeline_stage=0` | `pod_id` |
| `wait_for_worker_health` | — | — |
| `submit_and_poll` | `status='RUNNING'` | `pipeline_stage=N` transitions, `result_*`, `pipeline_seconds` |
| `upload_and_finalize` | `status='REPORTING'` | `sim_data_available=true` |
| `terminate_pod` | — | — (no user-visible change) |
| `refund_credits` | `status='FAILED'`, `error_message` | `credit_entries` row |

## DB Schema Changes

Alembic migration `add_workflow_columns`:

```sql
ALTER TABLE simulation_jobs ADD COLUMN workflow_id VARCHAR(255);
ALTER TABLE simulation_jobs ADD COLUMN workflow_run_id VARCHAR(255);
CREATE INDEX ix_simulation_jobs_workflow_id ON simulation_jobs (workflow_id);
```

`workflow_id = sim-{job_id}`. `workflow_run_id` is Temporal's internal run identifier, updated on start and on each reset; enables `tctl workflow show` lookups from a DB row.

### Columns dropped after cutover stabilizes

Separate migration, post-rollout. Not in the cutover migration itself so we can rollback cleanly:

- `celery_task_id` — no Celery task owns the sim any more.
- `resume_task_id` — no resume path exists.
- `last_heartbeat` — Temporal owns liveness.
- `retry_count` — superseded by activity retry policies and workflow-level retries (kept as metric-only if useful).

### Columns kept

- `retry_of` — user-initiated retries still create a new sim row with `retry_of = old_id`. The API creates a new workflow for the new sim.
- `pod_id`, `pipeline_stage`, `status`, `result_*`, `sim_data_available`, `markets_config`, `enriched_seed`, `enrichment_citations`, `live_status` — all unchanged.

## Failure Modes

| Failure | Current handling | New handling |
|---|---|---|
| Deploy kills worker during `provision_pod` | Task redelivered after `visibility_timeout` (24 h); `recover_stale_jobs` skips for hours on `PROVISIONING + no_heartbeat` heuristic | Temporal replays workflow on next worker; `provision_pod` activity re-entry checks `simulation_jobs.pod_id` and hands back existing pod |
| Deploy kills worker during `submit_and_poll` | Recovery re-enqueues `resume_simulation_task`; race conditions with atomic-claim column | Temporal replays; `submit_and_poll` checks pod `/status` and resumes polling in place |
| Pod `/health` never comes up | `wait_for_worker_health` TimeoutError → `runner.py` finally → pod terminated | `wait_for_worker_health` activity exceeds `start_to_close`; workflow finally runs `terminate_pod`; `refund_credits` fires in except block |
| `submit_and_poll` hangs (no heartbeat) | `recover_stale_jobs` flags via `HEARTBEAT_STALE_NO_PROGRESS_S = 900 s` | Activity heartbeat stops → Temporal fails activity after `heartbeat_timeout = 180 s` → workflow except block refunds, finally terminates |
| RunPod transient error during provision | `classify_gpu_error` + `self.retry()` with 60 s fixed delay | Activity `RetryPolicy` with exponential backoff; `non_retryable_error_types` excludes permanent errors |
| Two workers pick up same sim | Idempotency preamble checks `retries == 0` + `pod_id` set | `WorkflowAlreadyStartedError` at dispatch site |
| Redis flush / Celery outage | Recovery stops; sims stall silently | Temporal Postgres backend survives Redis loss; workflows continue. Celery outage affects only `generate_report_task` enqueue — handled by `upload_and_finalize` retry policy |
| `temporal-server` restart | n/a | Workflow state persists in `temporal-db`; workers reconnect on server return; activities idempotent so mid-activity restarts resume safely |

## Cutover

Flag-day. Sequence:

1. **Pre-deploy on staging or a scratch VPS:**
   - Bring up `temporal-server`, `temporal-db`, `simswarm-temporal-worker` alongside existing services.
   - Run a handful of sims end-to-end through `SimulationWorkflow`.
   - Kill `simswarm-temporal-worker` mid-sim — verify workflow resumes on restart.
   - Kill `temporal-server` mid-sim — verify workflow resumes on restart.
   - Kill pod mid-sim — verify `submit_and_poll` fails, `refund_credits` fires, `terminate_pod` succeeds.

2. **Production drain:**
   - Stop accepting new sims (set `/jobs` to 503 or drop behind a maintenance flag).
   - Wait until all rows in `PROVISIONING`, `RUNNING`, `REPORTING` reach a terminal state.

3. **Production cutover (single PR):**
   - Alembic migration adds `workflow_id`, `workflow_run_id`.
   - `docker-compose.yml` adds `temporal-server`, `temporal-db`, `simswarm-temporal-worker`.
   - API `POST /jobs` swapped from `run_simulation_task.delay(...)` to `temporal_client.start_workflow(...)`.
   - `run_simulation_task`, `resume_simulation_task`, `recover_stale_jobs`, and their helpers deleted.
   - Push to `main`, CI deploys.

4. **Re-open `/jobs`** once the new stack is serving.

5. **Post-cutover cleanup PR (separate):** drop deprecated columns listed above.

**Rollback:** revert the cutover PR. In-flight workflows resume on the reverted-state pod terminations via the old `recover_stale_jobs` path… actually, no — rollback means losing the temporal-server, which means losing workflow state. Mitigation: don't merge the cutover until step 1 is green, and accept that a rollback after a live sim has started on Temporal means that sim must be manually refunded. Users warned via status page if rollback happens.

## What Gets Deleted

| File | Reason |
|---|---|
| `saas/jobs/recovery.py` | Temporal owns workflow liveness |
| `saas/jobs/recovery_utils.py` | `_is_stale`, `_check_pod_status`, `_heartbeat_is_fresh` no longer needed |
| `saas/jobs/recovery_reporting.py` | Report orphan recovery replaced by `upload_and_finalize` retry policy |
| `saas/jobs/tasks_resume.py` | No resume path — Temporal replays |
| `saas/jobs/runner.py` `resume()` method | Same |
| `saas/jobs/tasks.py` lines 74–104 (idempotency preamble) | Replaced by `WorkflowAlreadyStartedError` |
| `saas/jobs/tasks.py` `run_simulation_task` body | Moved into `SimulationWorkflow` + activities |
| `saas/workers/celery_app.py` beat schedule `recover-stale-jobs` | Task gone |
| `saas/jobs/models.py` columns `celery_task_id`, `resume_task_id`, `last_heartbeat`, `retry_count` | Second migration, post-stabilization |

`cleanup_orphaned_pods` **stays** as a safety net. It's the one layer that doesn't infer from worker state — it reconciles RunPod reality against DB pod_ids. If a workflow ever leaves a pod leaked (bug in `terminate_pod`), the beat task catches it. Lower value than before but cheap insurance.

## New Files

| File | Purpose |
|---|---|
| `saas/workflows/__init__.py` | Package marker |
| `saas/workflows/sim_workflow.py` | `SimulationWorkflow` + `SimParams` / `SimResult` dataclasses |
| `saas/workflows/activities/provisioning.py` | `provision_pod`, `wait_for_worker_health`, `terminate_pod` |
| `saas/workflows/activities/pipeline.py` | `submit_and_poll` |
| `saas/workflows/activities/pre_gpu.py` | `enrich_seed` activity wrapper, `derive_markets` activity wrapper |
| `saas/workflows/activities/finalization.py` | `upload_and_finalize`, `refund_credits` |
| `saas/workflows/client.py` | `get_temporal_client()` helper used by FastAPI dispatch path |
| `saas/workflows/worker.py` | Worker bootstrap — registers workflow + activities, starts SDK worker |
| `infra/temporal/docker-compose.yml` snippet | `temporal-server`, `temporal-db` service definitions |
| `Dockerfile.temporal-worker` | Image for `simswarm-temporal-worker` service |

Activity modules import the existing implementations from `saas/jobs/` rather than duplicating logic. For example, `provisioning.py:provision_pod` calls `saas.gpu.runpod_provider.RunPodProvider.provision()` directly; only the orchestration layer is new.

## Operational Concerns

- **Backups:** `temporal-db` added to the existing Postgres backup script on the VPS. State loss = in-flight workflows frozen; replay from DB artefacts needed. Treated with the same seriousness as the app DB.
- **Monitoring:** `temporal` CLI (`temporal workflow list`, `temporal workflow show -w sim-120`) available on the VPS via `docker compose exec temporal-server tctl …`. The existing `orphan_alert` path still fires from `cleanup_orphaned_pods` for any leaked pod.
- **Alerts:** one new alert — "workflow failed" hook via Temporal's `OnFailed` webhook (or polling `list` for `FAILED` state in a new short beat task). Emits to the same channel as current `send_orphan_alert`.
- **Local dev:** `docker-compose.yml` local variant brings up `temporal-server` and `temporal-db` alongside app services. Test suite uses `temporalio.testing.WorkflowEnvironment` — no external Temporal needed for `pytest`.
- **Dependency add:** `temporalio` Python SDK, pinned in `pyproject.toml` (respects existing pin-deps-exactly rule on the worker side).

## Open Questions (Follow-Up Work)

1. **Priority lanes per tier:** Temporal supports per-activity priority. If `large`-tier sims end up starving `small` ones on a shared worker pool, add priority; don't implement preemptively.
2. **Workflow-level retries:** should a whole-workflow failure retry once automatically (e.g. transient RunPod-wide outage)? Current code doesn't; keep that behavior. Revisit after the first month of production data.
3. **Report task inclusion:** if `generate_report_task` grows its own recovery pains, consider folding it into `SimulationWorkflow` as a final activity. Deliberately out of scope for this refactor.
4. **Temporal schema migrations:** on Temporal server version bumps, the `temporal-db` schema changes. Pin the server version in `docker-compose.yml` and treat upgrades as a separate, deliberate operation.
5. **`generate_report_task` terminal guard:** the refactor depends on `generate_report_task` being safe to re-enqueue (see idempotency rules above). The implementation plan must add a terminal-status check at the top of the report task before removing `run_simulation_task`.
