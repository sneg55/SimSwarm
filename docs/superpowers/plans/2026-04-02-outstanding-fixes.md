# Outstanding Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix 8 outstanding bugs and quality issues across recovery system, frontend, data extraction, and infrastructure.

**Architecture:** Independent fixes grouped by subsystem. Each task is self-contained and can be deployed independently.

**Tech Stack:** Python (FastAPI, Celery, SQLAlchemy), Vue 3, Caddy, MinIO

---

## Task 1: Prevent resume task from overwriting COMPLETED jobs

**Problem:** Recovery resume task runs after pod terminates, fails, and overwrites `status=COMPLETED` with `status=FAILED`. Job 53 hit this — data was saved successfully but status was overwritten.

**Files:**
- Modify: `saas/workers/recovery.py`

**Fix:** Before dispatching a resume task, check if the job is already COMPLETED. If so, skip it.

Find the section in `recover_stale_jobs` that dispatches `resume_simulation_task` and add a status check:

```python
# Before resuming, verify job isn't already completed
if job_status in ('COMPLETED', 'FAILED', 'REFUNDED'):
    logger.info("recover.skipping_finished job_id=%d status=%s", job_id, job_status)
    continue
```

Also in `resume_simulation_task` in `saas/workers/tasks.py`, add a guard at the start:

```python
# Don't overwrite a job that already completed via the original task
from saas.workers.persistence import _get_job_status
current_status = _get_job_status(job_id)
if current_status in ('COMPLETED', 'REFUNDED'):
    logger.info("resume.skipping_already_complete job_id=%d status=%s", job_id, current_status)
    return {"job_id": job_id, "status": "already_completed", "skipped": True}
```

Add `_get_job_status` helper to `saas/workers/persistence.py`:

```python
def _get_job_status(job_id: int) -> str | None:
    engine = _get_sync_engine()
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT status FROM simulation_jobs WHERE id = :job_id"),
                {"job_id": job_id},
            ).first()
            return row[0] if row else None
    finally:
        engine.dispose()
```

**Test:** `pytest tests/ -v`
**Commit:** `fix: prevent recovery resume from overwriting COMPLETED job status`

---

## Task 2: Fix tier selection click not registering before Run

**Problem:** Clicking Small tier on Step 3, then immediately clicking "Run Simulation" — the tier doesn't register. Medium (default) always gets submitted.

**Files:**
- Modify: `frontend/src/components/wizard/WizardLaunch.vue`

**Fix:** The issue is that `selectedTier` defaults to `'medium'` and the emit fires on mount (line 76). When the user clicks Small then quickly clicks Run, the click event on the tier card may not have propagated before the submit fires.

Change the default tier to `null` and require explicit selection. The "Run Simulation" button should be disabled until a tier is selected:

```javascript
const selectedTier = ref(null)
// Remove: emit('update:tier', 'medium')  — don't auto-select
```

In the template, the Run button already has `:disabled` based on `canSubmit` in NewSimulation.vue which checks `selectedTier.value`. With `null` default, the user must click a tier before running.

To preserve good UX, auto-highlight Medium visually but don't emit until clicked:

```javascript
onMounted(() => {
  // Don't auto-emit — wait for explicit click
})
```

Actually the simplest fix: keep Medium as default but ensure the emit is synchronous. The real bug is that `selectTier` calls `emit('update:tier', id)` and the parent's `handleSubmit` reads the ref before Vue processes the emit. Fix by using `nextTick`:

In `NewSimulation.vue`, update `handleSubmit`:
```javascript
async function handleSubmit() {
  await nextTick()  // ensure tier selection is processed
  // ... rest of submit
}
```

**Test:** `cd frontend && npx vitest run`
**Commit:** `fix: ensure tier selection registers before sim submission`

---

## Task 3: Fix pipeline_stage never updating (async InterfaceError)

**Problem:** Every sim shows `pipeline_stage=NULL` and PROVISIONING status throughout because the async update fails with `InterfaceError: cannot perform operation: another operation is in progress`. The Celery task runs async code that shares the asyncpg connection pool.

**Files:**
- Modify: `saas/workers/persistence.py`

**Fix:** The `_async_update_pipeline_stage` function uses the shared async pool from a Celery worker context. Replace it with a sync version using psycopg2 (same pattern as all other Celery persistence functions):

```python
def _update_pipeline_stage(job_id: int, stage: int) -> None:
    """Update pipeline_stage and set status to RUNNING (sync, for Celery)."""
    engine = _get_sync_engine()
    try:
        with engine.connect() as conn:
            conn.execute(
                text("UPDATE simulation_jobs SET pipeline_stage = :stage, status = 'RUNNING' WHERE id = :job_id"),
                {"stage": stage, "job_id": job_id},
            )
            conn.commit()
    finally:
        engine.dispose()
```

Update `saas/workers/tasks.py` to use the sync version in the stage callback:

```python
async def _stage_cb(j_id: int, stage: int) -> None:
    _update_pipeline_stage(j_id, stage)  # sync, no await
```

Do the same for `_async_update_heartbeat` → sync `_update_heartbeat`.

**Test:** `pytest tests/ -v`
**Commit:** `fix: use sync DB writes for pipeline_stage and heartbeat updates`

---

## Task 4: Fix agent_name null in extracted posts

**Problem:** `extract_posts` and `extract_top_posts` join `post.user_id = user.user_id` but `user_name` is NULL for Twitter platform (Twitter sim uses `agent_id` not `user_id` in the user table, or user_name field is empty).

**Files:**
- Modify: `infra/docker/sim_data_extractor.py`

**Fix:** Use `COALESCE(u.user_name, u.name, 'Agent ' || u.agent_id)` in the SQL to fall back through available name fields:

In `extract_posts`:
```sql
SELECT p.post_id, p.user_id, u.agent_id,
       COALESCE(u.user_name, u.name, 'Agent ' || u.agent_id) AS agent_name,
       ...
```

Same fix in `extract_top_posts`.

Also in `extract_agent_trajectories`, use the same COALESCE pattern when building agent names.

**Test:** Verify with: `python3 -c "import ast; ast.parse(open('infra/docker/sim_data_extractor.py').read()); print('OK')"`
**Commit:** `fix: fallback agent names in extraction (COALESCE user_name/name/agent_id)`

---

## Task 5: Investigate missing Polymarket data

**Problem:** Sims don't generate prediction market trades. The `market_curves.json` and `trades.json` are always empty (`[]`). The Polymarket platform may not be enabled in the simulation config.

**Files:**
- Investigate: `infra/docker/run_job.py` (prepare_simulation, run_and_wait)
- Investigate: `vendor/miroshark/backend/scripts/run_parallel_simulation.py`

**Investigation steps:**
1. Check if the simulation config enables Polymarket: `grep -r "polymarket\|prediction_market\|enable_polymarket" infra/docker/run_job.py vendor/miroshark/backend/`
2. Check the config generator: does it create prediction markets by default?
3. The celery logs showed `Generated 1 prediction markets` — so markets ARE generated in config, but the parallel sim runner may not launch the Polymarket platform.

**Fix:** In `run_job.py`'s `run_and_wait` or `prepare_simulation`, ensure the Polymarket platform is included in the parallel simulation launch. The config has prediction markets but the runner might only launch Twitter + Reddit.

Check `run_parallel_simulation.py` for which platforms are launched. If Polymarket is conditionally enabled, ensure the condition is met.

**Test:** Run a sim and check if `polymarket_simulation.db` exists in the sim directory.
**Commit:** `fix: enable Polymarket platform in parallel simulation runner`

---

## Task 6: Investigate sparse engagement data (0 likes/shares)

**Problem:** All posts have `num_likes=0, num_shares=0, num_comments=0`. Agents create posts but never engage with each other's content.

**Investigation steps:**
1. Check actions.jsonl from a completed sim — are there any LIKE_POST, REPOST, CREATE_COMMENT actions?
2. Check the agent behavior config — do agents have engagement enabled?
3. The sim may complete too quickly (72 rounds) for engagement to accumulate.

This is likely a MiroShark engine behavior issue rather than an extraction bug. The agents post but the simulation rounds may not include engagement phases. May need configuration changes in the sim config generator to enable agent engagement behavior.

**Fix:** This may require changes to the MiroShark config generator to set `enable_engagement: true` or increase the number of rounds where agents can interact. This is more of a product quality issue than a bug — document findings and create a follow-up task.

**Commit:** `docs: document engagement sparsity root cause and fix options`

---

## Task 7: Save pod_id immediately on creation (before ready-wait)

**Problem:** Orphan cleanup can't match pods to jobs during provisioning because `pod_id` is saved only after the pod is fully ready (which can take 5+ min). The 10-min grace period is a band-aid.

**Files:**
- Modify: `saas/gpu/runpod_provider.py`
- Modify: `saas/workers/job_runner.py`

**Fix:** The `RunPodProvider.provision()` method creates the pod at line 66, knows the `pod_id` at line 79, but doesn't return until the pod is ready at line 91. Split this into two steps:

Option A: Add an `on_pod_created` callback to `provision()`:
```python
async def provision(self, config, on_created=None):
    # ... pod creation ...
    pod_id = pod["id"]
    if on_created:
        await on_created(pod_id)
    # ... wait for ready loop ...
```

In `job_runner.py`'s `_run_inner`, pass the callback:
```python
async def _on_created(pid):
    if self._pod_id_callback:
        await self._pod_id_callback(config.job_id, pid)

instance = await self.gpu_provider.provision(gpu_config, on_created=_on_created)
```

Remove the existing `_pod_id_callback` call after `provision()` returns (it would be redundant).

**Test:** `pytest tests/ -v`
**Commit:** `fix: save pod_id to DB immediately on creation, before ready-wait loop`

---

## Task 8: Document MinIO HTTPS plan (Caddy proxy tech debt)

**Problem:** The Caddy reverse proxy for MinIO (`/minio/*` → `178.156.171.213:9000`) with Host header preservation is fragile. Proper fix is HTTPS directly on MinIO.

**Files:**
- Create: `docs/minio-https-plan.md`

**Content:** Document two options:
1. Install Caddy on simswarm-3 with Let's Encrypt for a subdomain (e.g. `minio.simswarm.xyz`)
2. Use the existing Caddy proxy but with a dedicated subdomain route

Recommend option 1 as a future task. The current proxy works and the Host header fix is correct — this is low priority tech debt, not urgent.

**Commit:** `docs: MinIO HTTPS migration plan`
