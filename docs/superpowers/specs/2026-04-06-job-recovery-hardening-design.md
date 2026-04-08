# Job Recovery Hardening & Neo4j Upgrade

Three production issues discovered from Job #59 logs on 2026-04-06.

## Problem Statement

1. **Resume race condition:** `recover_stale_jobs` (10-min beat) can dispatch multiple `resume_simulation_task` calls for the same job across consecutive cycles. When two resume tasks run concurrently, the second fails on pod termination and overwrites the job status to FAILED — even though the first already extracted results successfully. Job #59 had a valid 19,786-char report but ended up FAILED with credits refunded.

2. **Zombie status poller:** After one resume task terminates the pod, any other `poll_until_complete` loop targeting that pod keeps polling indefinitely (getting empty HTTP responses), wasting a Celery worker slot until it eventually crashes or times out.

3. **Neo4j vector relationship warnings:** MiroFish calls `db.index.vector.queryRelationships()` and creates vector indexes on relationships — both require Neo4j 5.18+. Production runs 5.15. The engine falls back gracefully but spams ~40 identical warnings per job.

## Fix 1: Resume Deduplication via Atomic Claim

**Approach:** Use an atomic DB update as a distributed lock. The first `resume_simulation_task` to run claims the job; any subsequent task for the same job exits immediately.

**Mechanism:**

Add a new column `resume_task_id` (nullable text) to `simulation_jobs`. When `resume_simulation_task` starts:

```sql
UPDATE simulation_jobs
SET resume_task_id = :task_id
WHERE id = :job_id
  AND status NOT IN ('COMPLETED', 'FAILED', 'REFUNDED')
  AND resume_task_id IS NULL
RETURNING id
```

If 0 rows returned, another task already claimed it — exit early. On completion (success or failure), clear `resume_task_id`.

**Changes:**
- `saas/jobs/tasks.py` — add atomic claim at top of `resume_simulation_task`, clear on exit
- `saas/jobs/persistence.py` — add `_claim_resume(job_id, task_id)` and `_release_resume(job_id)` helpers
- `saas/jobs/models.py` — add `resume_task_id` column (nullable String)
- Alembic migration for the new column

**Why not lock in recovery.py instead:** The recovery function runs in a single Celery task, but the race happens across consecutive beat cycles (10 min apart). Locking at the dispatch site would require tracking which tasks were dispatched and whether they completed — more complex than a simple atomic claim at the resume entry point.

## Fix 2: Consecutive Poll Failure Circuit Breaker

**Approach:** Track consecutive poll failures in `poll_until_complete`. After 5 consecutive failures (50 seconds of no valid response), break with a descriptive error.

**Changes in `saas/jobs/pipeline.py`:**

```python
consecutive_failures = 0
MAX_CONSECUTIVE_FAILURES = 5

for poll in range(max_polls):
    await asyncio.sleep(poll_interval)
    try:
        status_resp = await http.get(f"{worker_url}/status")
        status_data = status_resp.json()
        consecutive_failures = 0  # reset on success
    except Exception as e:
        consecutive_failures += 1
        logger.warning("Status poll %d failed: %s", poll + 1, e)
        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            raise RuntimeError(
                f"Pod unreachable: {MAX_CONSECUTIVE_FAILURES} consecutive poll failures"
            )
        continue
```

This also protects against RunPod spot instance preemption, where the pod disappears mid-simulation.

## Fix 3: Neo4j Upgrade from 5.15 to 5.18+

**Approach:** Upgrade Neo4j on simswarm-2 (87.99.143.119) from 5.15 Community to 5.18+ Community. Neo4j 5.x minor upgrades are in-place compatible.

**Steps:**
1. SSH to simswarm-2
2. Stop Neo4j service
3. Backup data directory
4. Update Neo4j package to 5.18+ (or latest 5.x)
5. Start Neo4j, verify connection from simswarm app
6. Run a test simulation to confirm relationship vector indexes now work

**No code changes required** — MiroFish already has the correct Cypher for relationship vector indexes; it just needs a Neo4j version that supports them.

## Scope Boundary

- No changes to `vendor/mirofish/` — the engine code is correct, the infrastructure was behind
- No changes to `recovery.py` — the deduplication is handled at the resume task level
- No new retry logic — the circuit breaker is a fail-fast mechanism, not a retry

## Testing

- **Fix 1:** Unit test that calls `_claim_resume` twice for the same job — second call returns False
- **Fix 2:** Unit test that mocks httpx to return 5 consecutive errors — verify RuntimeError raised
- **Fix 3:** Manual verification after Neo4j upgrade — run a sim and confirm no vector relationship warnings in logs
