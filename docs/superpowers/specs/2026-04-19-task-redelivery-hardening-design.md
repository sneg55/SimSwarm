# Task Redelivery Hardening

**Date:** 2026-04-19
**Status:** Design approved, ready for implementation plan

## Context

Job 118 (medium tier, 2026-04-19) failed with `Pod unreachable: 5 consecutive poll failures` after its own running pod was terminated by `cleanup_orphaned_pods`. Triage (see incident note below) walked back the failure through three layers:

1. **Broker visibility timeout.** Celery's Redis default (`3600s`) redelivered the still-running `run_simulation_task` after ~60 min. Fixed in `40d7f17` by setting `broker_transport_options.visibility_timeout=86400`.
2. **Non-idempotent task body.** On redelivery the task started from scratch — re-enriched, re-derived markets, provisioned a second pod, and **overwrote `pod_id`** in `simulation_jobs`.
3. **Cleanup orphan detection.** `cleanup_orphaned_pods` compares live RunPod pods against `pod_id` values on active jobs. Once the DB row pointed at the new pod, the original pod was classified orphan and terminated mid-pipeline.

The visibility-timeout fix closes the specific redelivery window that triggered this incident. This spec hardens the two layers behind it so future redeliveries (broker crash, explicit `apply_async`, operator-initiated retry, deploy-time restart during a long sim) can't produce the same cascade.

Related observation: `simulation_jobs.status` never transitions `PROVISIONING → RUNNING`. Every active sim sits in `PROVISIONING` for its full duration, which (a) weakens `recover_stale_jobs`' `skipping_provisioning` guard once `last_heartbeat` is written, and (b) makes the status page semantically wrong.

**Incident reference:** ad-hoc investigation 2026-04-19, job 118. Not yet written up as a postmortem.

## Goals

1. A second delivery of `run_simulation_task` for a job that already has a live pod must **not** re-enrich, re-derive markets, or provision a second pod. It must either hand off to the resume path or no-op.
2. `simulation_jobs.status` must transition to `RUNNING` once the worker pod reports pipeline activity, on both the initial-run and resume code paths.
3. `cleanup_orphaned_pods` must not be able to terminate a pod that is actively progressing a pipeline, even if the DB `pod_id` is momentarily out of sync.

## Non-Goals

- No redesign of the job state machine. Existing `jobstatus` enum values stay.
- No new recovery task. The existing `resume_simulation_task` is the intended handoff target.
- No changes to the broker (we keep Redis; we're not migrating to RabbitMQ to get native ack semantics).
- No retroactive repair for historical jobs stuck in inconsistent states (one-off DB updates only, done case-by-case).

## Design

Two-PR delivery; each PR is independently shippable and each narrows the blast radius of the other.

- **PR 1 — Idempotent task entry + status transition.** Touches `saas/jobs/tasks.py`, `saas/jobs/pipeline.py`, `saas/jobs/persistence.py`. Where the real correctness work lives.
- **PR 2 — Cleanup grace via pod tag.** Touches `saas/jobs/cleanup.py` and the pod-provision path in `saas/gpu/runpod.py`. A defense-in-depth layer so cleanup can never kill a pod that is tagged with a non-terminal `job_id`, regardless of DB state.

### 1. Idempotent `run_simulation_task` entry

**Current state**
`saas/jobs/tasks.py:run_simulation_task` immediately enters enrichment + market derivation + provisioning without inspecting the DB row. Any redelivery therefore produces a second pod and clobbers `pod_id`.

**Change**
Add an idempotency preamble before any side-effectful step:

```
status, pod_id, retry_count, last_heartbeat = _load_job_snapshot(job_id)

# Terminal states — redelivery must not clobber them
if status in ('COMPLETED', 'FAILED', 'REFUNDED'):
    logger.info("run.skipping_terminal job_id=%d status=%s", job_id, status)
    return {"skipped": True, "status": status}

# Active pod already exists — hand off to the resume path instead of
# starting fresh. Resume owns the PROVISIONING/RUNNING handoff via
# _claim_resume; a redelivery that loses the claim race exits cleanly.
if pod_id and status in ('PROVISIONING', 'RUNNING'):
    from saas.jobs.tasks_resume import resume_simulation_task
    logger.info(
        "run.redelivery_detected job_id=%d pod_id=%s status=%s — handing to resume",
        job_id, pod_id, status,
    )
    resume_simulation_task.delay(
        job_id=job_id, user_id=user_id,
        pod_id=pod_id, credits_charged=credits_charged,
    )
    return {"handed_off": True, "pod_id": pod_id}
```

`_load_job_snapshot` is a new sync helper in `saas/jobs/persistence.py` that reads the four fields with psycopg2 (per the existing rule in `.claude/rules/architecture.md`). One round-trip, no ORM session.

**Edge cases**
- **`pod_id` set but pod is gone from RunPod.** The resume task will fail its poll loop and mark the job failed — same outcome as today, but via the single resume code path instead of both run + resume racing.
- **Redelivery arrives during enrichment (no `pod_id` yet).** Status is still `PENDING`; the preamble falls through to a fresh enrichment run. The cost is a duplicated Grok call, not a duplicated pod. Acceptable — the visibility-timeout fix already makes this window ≥24h and enrichment takes <30s.
- **Celery retry (`self.retry(exc=...)`).** The task is re-entered with `self.request.retries > 0`. `_update_job_retry` already bumps `retry_count` in the DB before retry is raised, so the preamble sees `retry_count>=1` and can still detect the existing pod. No special-case code needed.

### 2. `PROVISIONING → RUNNING` status transition

**Current state**
`saas/jobs/pipeline.py:poll_until_complete` updates `last_heartbeat` periodically but never writes `status`. `simulation_jobs.status` stays `PROVISIONING` for the full pipeline duration.

**Change**
In `poll_until_complete`, when `status_data.get("status") == "running"` is seen for the first time, invoke a new `status_callback(job_id, "RUNNING")`. Both call sites (`runner.run` in `tasks.py` and `runner.resume` in `tasks_resume.py`) wire it to a new sync persistence helper:

```python
def _transition_to_running(job_id: int) -> None:
    """Idempotent PROVISIONING→RUNNING. No-op for any other state."""
    # sync psycopg2, single UPDATE ... WHERE status='PROVISIONING'
```

Guarded by `WHERE status = 'PROVISIONING'` so concurrent writers (resume + main) can't race the row into RUNNING twice, and can't drag a COMPLETED/FAILED row back to RUNNING.

**Side effect on recovery logic**
`recover_stale_jobs` keeps its existing guard (`status == 'PROVISIONING' and last_heartbeat is None`). Once RUNNING is reached, recovery falls back to the heartbeat-age check, which is what we want — a job that's been RUNNING for 20 min with a fresh heartbeat should not be re-resumed.

### 3. Cleanup pod-tag grace (defense in depth)

**Current state**
`cleanup_orphaned_pods` (saas/jobs/cleanup.py:73) terminates any pod whose `id` is not in `_get_active_job_pod_ids()`. The DB is the sole source of truth — any moment the DB `pod_id` drifts from the pod that's actually running, cleanup will kill the running pod.

**Change**
At provision time, tag each pod with `job_id=<id>` via RunPod's pod name/tag fields (already set to `fishcloud-sim`/`simswarm-sim`; extend the name pattern or add to the existing tag block). Cleanup then gains a second check:

```python
if pod_id in active_pod_ids:
    continue
# Defense-in-depth: don't terminate a pod whose tag points at a
# non-terminal job, even if the DB row points elsewhere.
tag_job_id = _extract_job_tag(pod)
if tag_job_id is not None:
    status = _get_job_status(tag_job_id)
    if status in ('PENDING', 'PROVISIONING', 'RUNNING', 'REPORTING'):
        logger.warning(
            "cleanup.skipped_tagged pod_id=%s tag_job_id=%d status=%s "
            "(DB pod_id drift — investigate)",
            pod_id, tag_job_id, status,
        )
        continue
```

The log line at `WARNING` is intentional: this branch is a drift detector. If it ever fires, it's because something upstream (idempotency preamble missed a case, a race, a bug in resume) pointed the DB at a different pod. Alert on it.

**Why tags and not `pod.name`**: RunPod's name field already carries `fishcloud-sim`/`simswarm-sim` to filter *which* pods we own. The tag extension carries the job binding. Keeping them separate means a future rename of the name prefix doesn't break orphan detection.

## Testing

### PR 1 (idempotency + status transition)

- **Idempotency — terminal skip:** unit test that constructs a `SimulationJob` with `status=COMPLETED` and calls `run_simulation_task`; assert no GPU provider calls, no DB writes beyond the read.
- **Idempotency — active handoff:** unit test with `status=PROVISIONING, pod_id='x'`; patch `resume_simulation_task.delay` and assert it was called with the matching `job_id/pod_id/credits_charged`. Assert `provision` was NOT called.
- **Idempotency — clean redelivery:** status=PENDING, pod_id NULL → full path runs. Uses the existing happy-path integration test with a mocked provider; assert no regression.
- **Status transition:** extend the existing `tests/test_poll_circuit_breaker.py` fixture. Drive `poll_until_complete` with status sequence `['provisioning', 'running', 'running', 'completed']`; assert `status_callback` was called exactly once with `RUNNING` on the first `'running'` response.
- **Status transition — idempotent UPDATE:** direct DB test. Preset row to `COMPLETED`; call `_transition_to_running`; assert the row is unchanged.
- **Manual:** run a small sim in prod; confirm the status page shows `RUNNING` before the pipeline finishes (currently shows `PROVISIONING` for the whole run).

### PR 2 (cleanup tag grace)

- **Tag extraction:** unit test that `_extract_job_tag` parses the tag for pods provisioned by the new code path and returns `None` for legacy untagged pods.
- **Skip on tag hit:** mock `runpod.get_pods()` returning a pod whose tag references a job with `status=RUNNING`; assert cleanup does NOT terminate it. Flip the job status to `COMPLETED` and assert cleanup DOES terminate it (now orphaned).
- **No regression for legacy pods:** untagged pods still follow the existing name + active-jobs check. Assert cleanup behavior for untagged pods is unchanged.
- **Manual:** run a small sim after PR 2; grep pod metadata on RunPod to confirm the tag landed.

## Rollout

1. **PR 1 first.** Ship and soak for one medium sim. The idempotency preamble eliminates the cause of pod_id drift. Status transition is observable on the status page and in `simulation_jobs.status`.
2. **PR 2 second.** Purely defensive — catches any residual drift. Alerts (via the `cleanup.skipped_tagged` WARNING) let us know if the preamble missed a case; absence of alerts over two weeks retires the defense as "cold but kept".
3. **No rollback coupling.** PR 1 and PR 2 are independent. Either can revert without impacting the other.

## Out of Scope (tracked separately)

- Broker visibility timeout — already shipped in `40d7f17`.
- Rewriting the recover_stale_jobs decision tree — currently correct given the two fixes above.
- Historical DB cleanup for jobs in inconsistent states (e.g., 118) — handled by ad-hoc operator actions, not by this spec.
- Migrating off Redis as the broker — out of scope; the visibility-timeout + idempotency pairing is sufficient.

## Links

- Fix already shipped: `40d7f17` fix(workers): raise broker visibility_timeout above max tier timeout
- Prior related spec: `docs/superpowers/specs/2026-04-06-job-recovery-hardening-design.md` (the circuit-breaker that surfaced this error message)
- Architecture rule: `.claude/rules/architecture.md` — "DB writes from Celery: Always use sync psycopg2"
- Memory reference: "Resume ownership — resume_simulation_task only owns PROVISIONING/RUNNING"
- Memory reference: "Deploy vs sims — recovery resumes idle/running/completed pods automatically"
