# GPU Orphan Hardening — Design Spec

**Date:** 2026-03-28
**Status:** Draft
**Trigger:** $33.82 RunPod bill on Mar 27 ($24.78 L40S alone) caused by orphaned GPU pods never being cleaned up.

## Root Cause

Both safety-net Celery tasks (`cleanup_orphaned_pods`, `recover_stale_jobs`) use `psycopg2` for sync DB queries, but the Celery container only has `asyncpg` installed. Both tasks have been **silently failing every 10 minutes since deployment**, returning `{'error': 'No module named psycopg2'}` which Celery marks as "succeeded".

Additionally, the normal teardown code path has architectural gaps where pods can escape termination (tier timeout during provisioning, pod_id not persisted until success).

## Scope

Seven changes, ordered by priority:

1. Immediate dependency fix (psycopg2)
2. Early pod ID persistence
3. Restructure tier timeout
4. Heartbeat column + staleness detection
5. Alerting on orphan termination
6. RunPod direct audit hardening
7. Testing

---

## 1. Immediate Dependency Fix

**Problem:** `psycopg2` is not installed in the Celery container. Both cleanup and recovery tasks fail silently.

**Fix:**
- Add `psycopg2-binary` to the Celery container's Python dependencies (in `pyproject.toml` or `requirements.txt`, and in the Docker image).
- Change both tasks to **raise** on critical failures (missing DB driver, missing `RUNPOD_API_KEY`) instead of returning error dicts. Celery should mark these as failed tasks, not quiet successes.

**Files:** `pyproject.toml` (or equivalent), `saas/workers/cleanup.py`, `saas/workers/recovery.py`

---

## 2. Early Pod ID Persistence

**Problem:** `pod_id` is only written to the job record after the entire pipeline succeeds (`tasks.py:88-93`). If anything fails between provisioning and result saving, the pod is invisible to DB-based cleanup.

**Fix:**
- Save `pod_id` to the job record immediately after `gpu_provider.provision()` returns, before the pipeline starts.
- Add a `pod_id_callback` to `JobRunner` (same pattern as existing `stage_callback`).
- Call it from `_run_inner()` right after provisioning (line ~132).
- In `tasks.py`, the callback does: `UPDATE simulation_jobs SET pod_id = :pod_id WHERE id = :job_id`.

**Result:** Job row goes from `pod_id=NULL, status=PROVISIONING` to `pod_id=xxx, status=PROVISIONING` as soon as the pod is created. Recovery and cleanup can always find the pod via the DB.

**Files:** `saas/workers/job_runner.py`, `saas/workers/tasks.py`

---

## 3. Restructure Tier Timeout

**Problem:** `asyncio.wait_for` in `job_runner.run()` (line 119-126) wraps the entire `_run_inner()`, including provisioning. If the timeout fires during provisioning, `asyncio.CancelledError` propagates and the `finally` teardown block may not execute — the pod is created but never terminated.

**Fix:** Split into two phases:

```python
async def _run_inner(self, gpu_config, config):
    # Phase 1: Provision (uses its own internal timeout via MAX_POLL_ATTEMPTS)
    instance = await self.gpu_provider.provision(gpu_config)
    pod_id = instance.instance_id
    await self._pod_id_callback(config.job_id, pod_id)  # persist immediately

    # Phase 2: Pipeline (wrapped with tier timeout)
    try:
        result = await asyncio.wait_for(
            self._execute_pipeline(pod_id, config),
            timeout=config.timeout_seconds,
        )
        result["pod_id"] = pod_id
        return result
    except asyncio.TimeoutError:
        raise TimeoutError(
            f"Job {config.job_id} exceeded {config.tier} tier timeout"
        )
    finally:
        await self.gpu_provider.terminate(pod_id)  # always runs
```

The outer `run()` method drops its `asyncio.wait_for` wrapper. Provisioning completes (or fails) naturally. The tier timeout applies only to pipeline execution, where we're guaranteed to have `pod_id` and the `finally` block.

**Files:** `saas/workers/job_runner.py`

---

## 4. Heartbeat Column + Staleness Detection

**Problem:** Recovery uses `created_at + tier_timeout + 10min` to decide if a job is stale. A job could be stuck with a live pod but no progress, and we wait the full timeout (~55 min) before acting.

**Fix:**

### Migration
Add `last_heartbeat TIMESTAMPTZ NULL` to `simulation_jobs`.

### Heartbeat Updates
In the pipeline polling loop (`_poll_until_complete`), update `last_heartbeat = now()` in the DB every 60 seconds (not on every poll, to avoid DB pressure). Use a callback (same pattern as `stage_callback` / `pod_id_callback`). Track last write time in-memory and skip if <60s since last update.

### Recovery Staleness Rules
A job is stale if any of:
- `last_heartbeat` is older than 5 minutes AND pod is dead in RunPod
- `last_heartbeat` is older than 15 minutes regardless of pod status (alive but no progress)
- `last_heartbeat IS NULL` AND `created_at` is older than `tier_timeout + 10min` (legacy fallback for pre-migration jobs)

**Result:** Zombie jobs with live pods burning money get caught in ~15 min instead of ~55 min.

**Files:** New Alembic migration, `saas/models/job.py`, `saas/workers/job_runner.py`, `saas/workers/recovery.py`

---

## 5. Alerting on Orphan Termination

**Problem:** Cleanup and recovery only log warnings. Nobody sees them unless they read celery logs manually.

**Fix:**
- When `cleanup_orphaned_pods` terminates a pod, or `recover_stale_jobs` fails a job, POST a notification to a configurable `ALERT_WEBHOOK_URL` env var.
- Works with Slack incoming webhooks, Discord, Telegram bots, or any HTTP endpoint.
- Payload: `pod_id`, GPU type, estimated cost (uptime hours x hourly rate), reason (orphan/stale/timeout).
- **Fire-and-forget:** Alert failure must never block cleanup. Wrap in `try/except`, log, continue.
- No new dependencies — use `httpx.post` (already in the project).

**Files:** New `saas/workers/alerts.py`, `saas/workers/cleanup.py`, `saas/workers/recovery.py`, `saas/config.py` (add `ALERT_WEBHOOK_URL`)

---

## 6. RunPod Direct Audit Hardening

**Problem:** The existing cleanup logic has fragilities around race conditions and DB failure behavior.

**Fixes:**

### Grace Period
Don't terminate a pod created less than 3 minutes ago. Prevents a race where cleanup runs between `provision()` returning and `pod_id` being persisted (even with early persistence from Section 2, there's a small window). Use the pod's `uptimeInSeconds` from the RunPod API to determine age.

### DB Failure Behavior
Currently `_get_active_job_pod_ids()` returns `{"__db_error__"}` sentinel on failure, which causes cleanup to proceed — potentially killing active pods it can't verify. Change to: if DB is unreachable, **skip cleanup entirely** and send an alert. Safer to let a pod run an extra 10 min than to accidentally kill an active job.

### Cost Tracking
When terminating an orphan, query the pod's `uptimeInSeconds` from the RunPod API and include estimated wasted cost in the log and alert payload.

**Files:** `saas/workers/cleanup.py`

---

## 7. Testing

### Unit Tests
Mock `runpod` API and DB calls. Cover:
- Cleanup skips pods younger than 3 min grace period
- Cleanup skips entirely when DB is unreachable (doesn't kill active pods)
- Recovery detects stale heartbeat and fails the job
- Recovery resumes job with fresh heartbeat and live pod
- Alerts fire on orphan termination
- Alert failures don't block cleanup

### Integration Test: Teardown Guarantee
Simulate `asyncio.CancelledError` during pipeline execution. Verify `gpu_provider.terminate()` is always called. This is the core architectural fix — must not regress.

### CI: Dependency Check
Verify `psycopg2` imports successfully inside the celery container image. Can be a simple `docker compose exec celery python -c "import psycopg2"` step in CI, or an import test in the test suite.

No E2E test against real RunPod — the cleanup task itself serves that role in prod.

**Files:** `tests/test_cleanup.py`, `tests/test_recovery.py`, `tests/test_job_runner_teardown.py`

---

## Files Changed (Summary)

| File | Change |
|------|--------|
| `pyproject.toml` | Add `psycopg2-binary` dependency |
| `saas/models/job.py` | Add `last_heartbeat` column |
| `saas/workers/job_runner.py` | Early pod_id callback, restructure timeout, heartbeat callback |
| `saas/workers/tasks.py` | Wire pod_id and heartbeat callbacks |
| `saas/workers/cleanup.py` | Grace period, DB failure skip, cost tracking, raise on critical error |
| `saas/workers/recovery.py` | Heartbeat-based staleness, raise on critical error |
| `saas/workers/alerts.py` | New — webhook alert helper |
| `saas/config.py` | Add `ALERT_WEBHOOK_URL` setting |
| New Alembic migration | `last_heartbeat` column |
| `tests/test_cleanup.py` | New — cleanup unit tests |
| `tests/test_recovery.py` | New — recovery unit tests |
| `tests/test_job_runner_teardown.py` | New — teardown guarantee integration test |
