# Recover-Stale Skip Guard Tightening (Followup)

**Date:** 2026-04-19
**Status:** Deferred — surfaced during the 2026-04-19 task-redelivery soak test, not in scope for the parent spec.

## Context

Soak sim 119 (small tier, pod `hv3w6tyz2alp1t`) validated PR 1 of the task-redelivery hardening work. The `PROVISIONING → RUNNING` transition fired at `15:28:16`, and `pod_id` stayed stable across the whole run — both goals of the parent spec.

During the soak we also observed `recover_stale_jobs` at `15:30:53` enqueue a `resume_simulation_task` for a sim that was healthily polling, producing two parallel poll loops against the same pod:

```
15:28:16  job.transition_running job_id=119
15:30:53  recover.resuming job_id=119 pod_id=hv3w6tyz2alp1t pod_status=running
15:30:53  resume.claimed job_id=119 task_id=1ef670da-...
```

The main-task poller (Worker-2) and the resume-task poller (Worker-5) both continued polling the same pod until completion. It didn't break anything, but it's wasteful, and it's a latent risk should any future change make the two poll loops do non-idempotent DB writes.

## Why this is not a PR 1 regression

The same pattern fired for earlier sims (see job 118 triage logs on 2026-04-19). Recovery was *already* racing the main task whenever a heartbeat existed — PR 1 didn't create this behavior, it just surfaced it more clearly because the `recover.resuming` line now appears alongside the new `job.transition_running` line in the same 10-minute beat cycle.

It's harmless today because:
- `broker_transport_options.visibility_timeout=86400` (shipped `40d7f17`) prevents broker redelivery.
- The idempotency preamble (shipped `7ba4b82`) prevents a redelivered main task from re-provisioning.
- `_claim_resume` dedups concurrent resume tasks to one winner.
- Both poll loops hit the same pod, so DB writes converge.

## Root cause

`saas/jobs/recovery.py:112-118` skips recovery only when:

```python
if job_status == "PROVISIONING" and last_heartbeat is None:
    continue
```

Once `last_heartbeat` is written (every ~60s during polling) the guard is bypassed. With PR 1 transitioning to `RUNNING` early, the `job_status == "PROVISIONING"` arm is also false, so every 10-minute beat cycle spawns a resume task for every live sim.

## Goal

A sim that is healthily polling must not have a resume task enqueued on top of it. Recovery should continue to handle the genuine "worker restart mid-sim, main task is gone" case.

## Non-Goals

- No changes to `_claim_resume` semantics (already does its job).
- No new job states.
- No replacement of the beat-driven recovery loop; it still runs every 10 minutes.

## Design

Extend the skip guard to treat any live, recently-heart-beating sim as "main task is alive, don't race it":

```python
from datetime import datetime, timezone

HEARTBEAT_FRESH_S = 180  # 3× HEARTBEAT_INTERVAL_S (60s)

def _heartbeat_is_fresh(last_heartbeat) -> bool:
    if last_heartbeat is None:
        return False
    if last_heartbeat.tzinfo is None:
        last_heartbeat = last_heartbeat.replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - last_heartbeat).total_seconds()
    return age < HEARTBEAT_FRESH_S
```

Guard becomes:

```python
if job_status in ("PROVISIONING", "RUNNING") and (
    last_heartbeat is None or _heartbeat_is_fresh(last_heartbeat)
):
    logger.info(
        "recover.skipping_live job_id=%d status=%s pod_id=%s "
        "(main task is alive; heartbeat_fresh=%s)",
        job_id, job_status, pod_id, last_heartbeat is not None,
    )
    continue
```

Retain the existing `skipping_provisioning` branch for the "no heartbeat yet" case (it's strictly a subset of the new guard but preserving the distinct log helps operators read recovery history).

**Threshold choice.** 180s = 3× the existing `HEARTBEAT_INTERVAL_S`. A genuine worker death still shows up as stale within one recovery beat cycle (10 min > 180s), so recovery latency for real failures doesn't change.

## Testing

- **Unit:** `_heartbeat_is_fresh` — None → False; 10s old → True; 600s old → False; tz-naive datetime → treated as UTC.
- **Recovery integration:** extend `tests/test_recovery_resume.py` with:
  - RUNNING + fresh heartbeat → `resume_simulation_task.delay` NOT called, log line `recover.skipping_live` present.
  - RUNNING + 10-minute-old heartbeat → resume IS called (existing behavior preserved).
  - PROVISIONING + no heartbeat → still hits the `skipping_provisioning` branch.
- **Soak validation:** run one more small sim after the change lands, grep for `recover.skipping_live` and absence of `recover.resuming` for the same job id during the run.

## Rollout

- Single PR, no coupling to PR 2 of the parent spec.
- Low blast radius: the change is a narrower `continue` — strictly fewer resume tasks enqueued, never more.
- Rollback is a one-commit revert.

## Links

- Parent spec: `docs/superpowers/specs/2026-04-19-task-redelivery-hardening-design.md`
- Shipped fixes this builds on: `40d7f17` (broker visibility_timeout), `7ba4b82` (idempotency + RUNNING transition)
- Memory: "Resume ownership — resume_simulation_task only owns PROVISIONING/RUNNING"
