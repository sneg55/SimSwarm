# Job Recovery Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the resume race condition that overwrites successful jobs as FAILED, add a circuit breaker to the status poller so it stops when a pod dies, and upgrade Neo4j to 5.18+ so relationship vector indexes work.

**Architecture:** Atomic DB claim column (`resume_task_id`) prevents duplicate resume tasks from racing. Consecutive poll failure counter in `poll_until_complete` short-circuits when the pod becomes unreachable. Neo4j upgrade is an infra-only change — no code modifications needed.

**Tech Stack:** Python 3.11, SQLAlchemy (sync psycopg2 for Celery), Alembic, PostgreSQL, Neo4j 5.18+

---

### Task 1: Add `resume_task_id` Column (Model + Migration)

**Files:**
- Modify: `saas/jobs/models.py:57` (after `live_status` column)
- Create: `alembic/versions/o6p7q8r9s0t1_add_resume_task_id.py`

- [ ] **Step 1: Add column to SimulationJob model**

In `saas/jobs/models.py`, add after line 57 (`live_status`):

```python
    resume_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
```

- [ ] **Step 2: Create Alembic migration**

Create `alembic/versions/o6p7q8r9s0t1_add_resume_task_id.py`:

```python
"""add resume_task_id column to simulation_jobs

Revision ID: o6p7q8r9s0t1
Revises: n5o6p7q8r9s0
Create Date: 2026-04-06
"""
from alembic import op
import sqlalchemy as sa

revision = "o6p7q8r9s0t1"
down_revision = "n5o6p7q8r9s0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("simulation_jobs", sa.Column("resume_task_id", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("simulation_jobs", "resume_task_id")
```

- [ ] **Step 3: Verify model loads**

Run: `python -c "from saas.jobs.models import SimulationJob; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add saas/jobs/models.py alembic/versions/o6p7q8r9s0t1_add_resume_task_id.py
git commit -m "feat: add resume_task_id column for resume deduplication"
```

---

### Task 2: Add Claim/Release Persistence Helpers

**Files:**
- Modify: `saas/jobs/persistence.py` (add two new functions at end of file)
- Create: `tests/test_resume_claim.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_resume_claim.py`:

```python
"""Tests for resume claim/release helpers."""
from unittest.mock import patch, MagicMock

from saas.jobs.persistence import _claim_resume, _release_resume


class TestClaimResume:
    """Verify atomic resume claiming via DB."""

    def test_claim_succeeds_when_unclaimed(self):
        """First claim on an unclaimed RUNNING job should return True."""
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.first.return_value = (42,)
        mock_conn.execute.return_value = mock_result

        mock_engine = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        with patch("saas.jobs.persistence._get_sync_engine", return_value=mock_engine):
            result = _claim_resume(job_id=42, task_id="celery-task-abc")

        assert result is True
        mock_conn.commit.assert_called_once()

    def test_claim_fails_when_already_claimed(self):
        """Second claim on an already-claimed job should return False."""
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.first.return_value = None  # no row returned
        mock_conn.execute.return_value = mock_result

        mock_engine = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        with patch("saas.jobs.persistence._get_sync_engine", return_value=mock_engine):
            result = _claim_resume(job_id=42, task_id="celery-task-def")

        assert result is False

    def test_claim_fails_when_no_engine(self):
        """Claim returns False when DATABASE_URL is unset."""
        with patch("saas.jobs.persistence._get_sync_engine", return_value=None):
            result = _claim_resume(job_id=42, task_id="celery-task-ghi")

        assert result is False

    def test_release_clears_resume_task_id(self):
        """Release should NULL out resume_task_id."""
        mock_conn = MagicMock()
        mock_engine = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        with patch("saas.jobs.persistence._get_sync_engine", return_value=mock_engine):
            _release_resume(job_id=42)

        mock_conn.execute.assert_called_once()
        mock_conn.commit.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_resume_claim.py -v`
Expected: FAIL — `_claim_resume` and `_release_resume` not defined

- [ ] **Step 3: Implement `_claim_resume` and `_release_resume`**

Add at the end of `saas/jobs/persistence.py`:

```python
def _claim_resume(job_id: int, task_id: str) -> bool:
    """Atomically claim a job for resume. Returns True if claimed, False if already taken."""
    from sqlalchemy import text

    engine = _get_sync_engine()
    if engine is None:
        return False
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "UPDATE simulation_jobs "
                    "SET resume_task_id = :task_id "
                    "WHERE id = :job_id "
                    "  AND status NOT IN ('COMPLETED', 'FAILED', 'REFUNDED') "
                    "  AND resume_task_id IS NULL "
                    "RETURNING id"
                ),
                {"task_id": task_id, "job_id": job_id},
            ).first()
            conn.commit()
            if row:
                logger.info("resume.claimed job_id=%d task_id=%s", job_id, task_id)
                return True
            logger.info("resume.claim_rejected job_id=%d task_id=%s", job_id, task_id)
            return False
    except Exception as exc:
        logger.warning("resume.claim_error job_id=%d: %s", job_id, exc)
        return False
    finally:
        engine.dispose()


def _release_resume(job_id: int) -> None:
    """Clear resume_task_id after resume completes (success or failure)."""
    from sqlalchemy import text

    engine = _get_sync_engine()
    if engine is None:
        return
    try:
        with engine.connect() as conn:
            conn.execute(
                text("UPDATE simulation_jobs SET resume_task_id = NULL WHERE id = :job_id"),
                {"job_id": job_id},
            )
            conn.commit()
    except Exception as exc:
        logger.warning("resume.release_error job_id=%d: %s", job_id, exc)
    finally:
        engine.dispose()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_resume_claim.py -v`
Expected: all 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add saas/jobs/persistence.py tests/test_resume_claim.py
git commit -m "feat: add atomic resume claim/release helpers"
```

---

### Task 3: Wire Claim Into `resume_simulation_task`

**Files:**
- Modify: `saas/jobs/tasks.py:179-246` (the `resume_simulation_task` function)
- Create: `tests/test_resume_dedup.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_resume_dedup.py`:

```python
"""Tests for resume_simulation_task deduplication."""
from unittest.mock import patch, MagicMock

import pytest


class TestResumeDedup:
    """Verify that duplicate resume tasks are rejected."""

    def test_resume_skips_when_claim_fails(self):
        """When _claim_resume returns False, task exits without running."""
        from saas.jobs.tasks import resume_simulation_task

        mock_self = MagicMock()
        mock_self.request = MagicMock()
        mock_self.request.id = "task-dup"

        with patch("saas.jobs.tasks._get_job_status", return_value="RUNNING"), \
             patch("saas.jobs.tasks._claim_resume", return_value=False) as mock_claim:
            result = resume_simulation_task(
                mock_self,
                job_id=42,
                user_id="user-1",
                pod_id="pod-abc",
                credits_charged=100,
            )

        assert result["skipped"] is True
        mock_claim.assert_called_once_with(42, "task-dup")

    def test_resume_releases_claim_on_success(self):
        """On successful resume, claim is released."""
        from saas.jobs.tasks import resume_simulation_task

        mock_self = MagicMock()
        mock_self.request = MagicMock()
        mock_self.request.id = "task-ok"

        mock_result = {
            "report": "# Report",
            "chat_log": "[]",
            "graph_data": "{}",
            "structured": "{}",
        }

        with patch("saas.jobs.tasks._get_job_status", return_value="RUNNING"), \
             patch("saas.jobs.tasks._claim_resume", return_value=True), \
             patch("saas.jobs.tasks._release_resume") as mock_release, \
             patch("saas.jobs.tasks._get_gpu_provider"), \
             patch("saas.jobs.tasks._run_async", return_value=mock_result), \
             patch("saas.jobs.tasks._save_job_results"):
            result = resume_simulation_task(
                mock_self,
                job_id=42,
                user_id="user-1",
                pod_id="pod-abc",
                credits_charged=100,
            )

        mock_release.assert_called_once_with(42)
        assert result["report"] == "# Report"

    def test_resume_releases_claim_on_failure(self):
        """On failed resume, claim is still released."""
        from saas.jobs.tasks import resume_simulation_task

        mock_self = MagicMock()
        mock_self.request = MagicMock()
        mock_self.request.id = "task-fail"

        with patch("saas.jobs.tasks._get_job_status", return_value="RUNNING"), \
             patch("saas.jobs.tasks._claim_resume", return_value=True), \
             patch("saas.jobs.tasks._release_resume") as mock_release, \
             patch("saas.jobs.tasks._get_gpu_provider"), \
             patch("saas.jobs.tasks._run_async", side_effect=RuntimeError("pod gone")), \
             patch("saas.jobs.tasks._mark_job_failed"), \
             patch("saas.jobs.tasks._refund_credits"):
            with pytest.raises(RuntimeError, match="pod gone"):
                resume_simulation_task(
                    mock_self,
                    job_id=42,
                    user_id="user-1",
                    pod_id="pod-abc",
                    credits_charged=100,
                )

        mock_release.assert_called_once_with(42)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_resume_dedup.py -v`
Expected: FAIL — `_claim_resume` not imported in tasks.py, logic not wired

- [ ] **Step 3: Wire claim/release into `resume_simulation_task`**

In `saas/jobs/tasks.py`, add to the imports (line 10-22 block):

```python
from saas.jobs.persistence import (
    _update_pipeline_stage_sync,
    _update_heartbeat_sync,
    _update_pod_id,
    _extract_key_insight,
    _get_job_status,
    _mark_job_failed,
    _save_job_results,
    _update_enrichment,
    _update_job_metadata,
    _update_job_retry,
    _update_sim_data_available,
    _claim_resume,
    _release_resume,
)
```

Then replace the `resume_simulation_task` function body (lines 196-246) with:

```python
    # Don't overwrite a job that already completed via the original task
    current_status = _get_job_status(job_id)
    if current_status in ('COMPLETED', 'REFUNDED'):
        logger.info("resume.skipping_already_complete job_id=%d status=%s", job_id, current_status)
        return {"job_id": job_id, "status": "already_completed", "skipped": True}

    # Atomic claim — prevents duplicate resume tasks from racing
    task_id = self.request.id or "unknown"
    if not _claim_resume(job_id, task_id):
        logger.info("resume.skipping_already_claimed job_id=%d task_id=%s", job_id, task_id)
        return {"job_id": job_id, "status": "already_claimed", "skipped": True}

    gpu_provider = _get_gpu_provider()

    async def _stage_cb(j_id: int, stage: int) -> None:
        _update_pipeline_stage_sync(j_id, stage)

    async def _heartbeat_cb(j_id: int) -> None:
        _update_heartbeat_sync(j_id)

    runner = JobRunner(
        gpu_provider=gpu_provider,
        stage_callback=_stage_cb,
        heartbeat_callback=_heartbeat_cb,
    )

    try:
        result = _run_async(runner.resume(pod_id=pod_id, job_id=job_id))

        report = result.get("report", "")
        chat_log = result.get("chat_log", "")
        graph_data = result.get("graph_data", "{}")
        structured = result.get("structured", "{}")

        _save_job_results(job_id=job_id, report=report, chat_log=chat_log, graph_data=graph_data, structured=structured)

        logger.info(
            "job.resumed_completed job_id=%d pod_id=%s report_chars=%d",
            job_id, pod_id, len(report),
        )
        return result

    except Exception as exc:
        error_msg = f"Resume failed: {exc}"
        logger.error("job.resume_failed job_id=%d pod_id=%s error=%s", job_id, pod_id, error_msg)

        _mark_job_failed(job_id=job_id, error_message=error_msg)
        if credits_charged > 0:
            _refund_credits(job_id=job_id, user_id=user_id, credits=credits_charged)

        # Terminate the pod — it's no use to us anymore
        try:
            _run_async(gpu_provider.terminate(pod_id))
        except Exception:
            pass

        raise

    finally:
        _release_resume(job_id)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_resume_dedup.py -v`
Expected: all 3 tests PASS

- [ ] **Step 5: Run existing recovery/task tests to check for regressions**

Run: `pytest tests/test_recovery.py tests/test_celery_tasks.py tests/test_dispatch_recovery.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add saas/jobs/tasks.py tests/test_resume_dedup.py
git commit -m "feat: wire atomic resume claim to prevent duplicate resume race"
```

---

### Task 4: Add Poll Failure Circuit Breaker

**Files:**
- Modify: `saas/jobs/pipeline.py:108-250` (the `poll_until_complete` function)
- Create: `tests/test_poll_circuit_breaker.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_poll_circuit_breaker.py`:

```python
"""Tests for poll_until_complete circuit breaker on consecutive failures."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from saas.jobs.pipeline import poll_until_complete


def _make_config(job_id=1, timeout_seconds=3600):
    return type("Cfg", (), {"job_id": job_id, "timeout_seconds": timeout_seconds})()


class TestPollCircuitBreaker:
    """Verify poller exits after consecutive failures."""

    @pytest.fixture(autouse=True)
    def _mock_sleep(self):
        with patch("saas.jobs.pipeline.asyncio.sleep", new_callable=AsyncMock):
            yield

    @pytest.mark.asyncio
    async def test_raises_after_consecutive_failures(self):
        """5 consecutive poll failures should raise RuntimeError."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("connection refused")

        config = _make_config()
        with pytest.raises(RuntimeError, match="consecutive poll failures"):
            await poll_until_complete(
                worker_url="https://pod-dead-5000.proxy.runpod.net",
                instance_id="pod-dead",
                config=config,
                client=mock_client,
            )

        # Should have tried exactly 5 times before giving up
        assert mock_client.get.call_count == 5

    @pytest.mark.asyncio
    async def test_resets_counter_on_success(self):
        """A successful poll resets the consecutive failure counter."""
        call_count = 0

        async def get_side_effect(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                raise Exception("temporary failure")
            resp = MagicMock()
            resp.json.return_value = {"status": "completed", "report": "ok", "chat_log": "[]"}
            return resp

        mock_client = AsyncMock()
        mock_client.get.side_effect = get_side_effect

        config = _make_config()
        result = await poll_until_complete(
            worker_url="https://pod-ok-5000.proxy.runpod.net",
            instance_id="pod-ok",
            config=config,
            client=mock_client,
        )

        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_does_not_trip_on_intermittent_failures(self):
        """Alternating success/failure should not trip the breaker."""
        call_count = 0

        async def get_side_effect(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if "/logs" in url or "/partial_chat" in url:
                resp = MagicMock()
                resp.status_code = 200
                resp.json.return_value = {"lines": [], "total_lines": 0}
                return resp
            # Alternate: fail, succeed, fail, succeed, ... then complete
            if call_count % 2 == 1 and call_count < 8:
                raise Exception("intermittent")
            resp = MagicMock()
            if call_count >= 8:
                resp.json.return_value = {
                    "status": "completed", "report": "done", "chat_log": "[]",
                }
            else:
                resp.json.return_value = {"status": "running"}
            return resp

        mock_client = AsyncMock()
        mock_client.get.side_effect = get_side_effect

        config = _make_config()
        result = await poll_until_complete(
            worker_url="https://pod-flaky-5000.proxy.runpod.net",
            instance_id="pod-flaky",
            config=config,
            client=mock_client,
        )

        assert result["status"] == "completed"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_poll_circuit_breaker.py -v`
Expected: FAIL — no circuit breaker logic exists yet

- [ ] **Step 3: Add circuit breaker to `poll_until_complete`**

In `saas/jobs/pipeline.py`, modify `poll_until_complete` — replace lines 128-144 with:

```python
    MAX_CONSECUTIVE_FAILURES = 5

    async with _ensure_client() as http:
        poll_start = time.monotonic()
        poll_interval = 10
        max_polls = max(360, config.timeout_seconds // poll_interval)
        last_stage: int | None = None
        last_heartbeat_time = 0.0
        _last_round: int | None = None
        _last_log_lines: list[str] = []
        _last_chat_count: int = 0
        consecutive_failures = 0
        for poll in range(max_polls):
            await asyncio.sleep(poll_interval)
            try:
                status_resp = await http.get(f"{worker_url}/status")
                status_data = status_resp.json()
                consecutive_failures = 0
            except Exception as e:
                consecutive_failures += 1
                logger.warning(f"Status poll {poll + 1} failed: {e}")
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    raise RuntimeError(
                        f"Pod unreachable: {MAX_CONSECUTIVE_FAILURES} consecutive poll failures"
                    )
                continue
```

The rest of the function (lines 146-250) stays exactly the same.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_poll_circuit_breaker.py -v`
Expected: all 3 tests PASS

- [ ] **Step 5: Run existing pipeline tests for regressions**

Run: `pytest tests/test_pipeline_lifecycle.py tests/test_pipeline_http.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add saas/jobs/pipeline.py tests/test_poll_circuit_breaker.py
git commit -m "feat: circuit breaker in status poller after 5 consecutive failures"
```

---

### Task 5: Upgrade Neo4j on simswarm-2

**Files:**
- No code changes — infrastructure only

- [ ] **Step 1: Check current Neo4j version**

```bash
ssh -i ~/.ssh/simswarm_deploy root@87.99.143.119 "neo4j --version"
```

Expected: `neo4j 5.15.x`

- [ ] **Step 2: Stop Neo4j service**

```bash
ssh -i ~/.ssh/simswarm_deploy root@87.99.143.119 "systemctl stop neo4j"
```

- [ ] **Step 3: Backup Neo4j data**

```bash
ssh -i ~/.ssh/simswarm_deploy root@87.99.143.119 "neo4j-admin database dump neo4j --to-path=/root/neo4j-backup-$(date +%Y%m%d)"
```

- [ ] **Step 4: Upgrade Neo4j to latest 5.x**

```bash
ssh -i ~/.ssh/simswarm_deploy root@87.99.143.119 "apt-get update && apt-get install -y neo4j"
```

If using a different package manager or Docker, adjust accordingly. The key is upgrading to >= 5.18.

- [ ] **Step 5: Start Neo4j and verify version**

```bash
ssh -i ~/.ssh/simswarm_deploy root@87.99.143.119 "systemctl start neo4j && sleep 5 && neo4j --version"
```

Expected: `neo4j 5.18.x` or higher

- [ ] **Step 6: Verify connectivity from simswarm app**

```bash
ssh -i ~/.ssh/simswarm_deploy root@178.156.236.185 "cd /opt/fishcloud && docker compose exec -T app python -c \"
import os
from neo4j import GraphDatabase
uri = os.environ.get('NEO4J_URI', 'bolt://87.99.143.119:7687')
user = os.environ.get('NEO4J_USER', 'neo4j')
password = os.environ.get('NEO4J_PASSWORD', '')
driver = GraphDatabase.driver(uri, auth=(user, password))
with driver.session() as s:
    result = s.run('CALL dbms.components() YIELD versions RETURN versions[0] AS version')
    print('Neo4j version:', result.single()['version'])
driver.close()
\""
```

Expected: version >= 5.18

- [ ] **Step 7: Run a test simulation to verify vector relationship indexes**

Trigger a small-tier sim via the test account or API. After it completes, check Celery logs:

```bash
ssh -i ~/.ssh/simswarm_deploy root@178.156.236.185 "cd /opt/fishcloud && docker compose logs celery --since 30m 2>&1" | grep -i "vector.*relationship\|queryRelationships"
```

Expected: no warnings about unsupported vector relationship indexes

---

### Task 6: Deploy Code Changes & Run Migration

**Files:**
- No new files — deployment of Tasks 1-4

- [ ] **Step 1: Run full test suite locally**

Run: `pytest tests/ -v --timeout=30`
Expected: all tests PASS

- [ ] **Step 2: Lint check**

Run: `ruff check saas/ tests/`
Expected: no errors

- [ ] **Step 3: Commit any remaining changes and push**

```bash
git push origin main
```

This triggers the GitHub Actions deploy to Hetzner.

- [ ] **Step 4: Run Alembic migration on production**

```bash
ssh -i ~/.ssh/simswarm_deploy root@178.156.236.185 "cd /opt/fishcloud && docker compose exec -T app alembic upgrade head"
```

Expected: `Running upgrade n5o6p7q8r9s0 -> o6p7q8r9s0t1, add resume_task_id column`

- [ ] **Step 5: Verify deployment**

```bash
ssh -i ~/.ssh/simswarm_deploy root@178.156.236.185 "cd /opt/fishcloud && docker compose exec -T db psql -U fishcloud -d fishcloud -c \"SELECT column_name FROM information_schema.columns WHERE table_name = 'simulation_jobs' AND column_name = 'resume_task_id';\""
```

Expected: one row showing `resume_task_id`

- [ ] **Step 6: Fix Job #59 status (it actually succeeded)**

```bash
ssh -i ~/.ssh/simswarm_deploy root@178.156.236.185 "cd /opt/fishcloud && docker compose exec -T db psql -U fishcloud -d fishcloud -c \"UPDATE simulation_jobs SET status = 'COMPLETED', error_message = NULL WHERE id = 59 AND result_report IS NOT NULL AND status = 'FAILED';\""
```

Expected: `UPDATE 1` — restores Job #59 to its correct COMPLETED status since it has a valid report
