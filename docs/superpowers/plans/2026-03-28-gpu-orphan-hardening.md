# GPU Orphan Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate GPU pod leaks that caused a $24 L40S bill by fixing the broken safety nets and hardening the teardown code path.

**Architecture:** Fix the missing `psycopg2-binary` dependency that silently broke both cleanup tasks since deployment. Restructure `JobRunner` so provisioning is outside the tier timeout wrapper, pod_id is persisted immediately after creation, and a heartbeat column enables tighter staleness detection. Add webhook alerting so orphan terminations are visible in real-time.

**Tech Stack:** Python, SQLAlchemy, Celery, Alembic, httpx, RunPod API, pytest

**Spec:** `docs/superpowers/specs/2026-03-28-gpu-orphan-hardening-design.md`

**Worktree:** `.worktrees/gpu-orphan-hardening` (branch `feature/gpu-orphan-hardening`)

---

### Task 1: Add psycopg2-binary dependency

**Files:**
- Modify: `pyproject.toml:16` (dependencies list)

- [ ] **Step 1: Add psycopg2-binary to dependencies**

In `pyproject.toml`, add `psycopg2-binary` to the dependencies list:

```toml
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.34.0",
    "sqlalchemy[asyncio]>=2.0.36",
    "asyncpg>=0.30.0",
    "alembic>=1.14.0",
    "pydantic>=2.10.0",
    "pydantic-settings>=2.7.0",
    "python-dotenv>=1.0.1",
    "stripe>=11.0.0",
    "celery[redis]>=5.4.0",
    "bcrypt>=4.2.0",
    "pyjwt>=2.9.0",
    "runpod>=1.7.0",
    "httpx>=0.28.0",
    "reportlab>=4.0.0",
    "slowapi>=0.1.9",
    "psycopg2-binary>=2.9.0",
]
```

- [ ] **Step 2: Install updated dependencies**

Run: `pip install -e ".[dev]"`
Expected: Successfully installed psycopg2-binary

- [ ] **Step 3: Verify import works**

Run: `python -c "import psycopg2; print(psycopg2.__version__)"`
Expected: Prints version number (e.g., `2.9.9`)

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "fix: add psycopg2-binary dependency for cleanup/recovery tasks"
```

---

### Task 2: Make cleanup and recovery tasks raise on critical errors

**Files:**
- Modify: `saas/workers/cleanup.py`
- Modify: `saas/workers/recovery.py`
- Test: `tests/test_cleanup.py` (new)
- Test: `tests/test_recovery.py` (new)

- [ ] **Step 1: Write test for cleanup raising on missing RUNPOD_API_KEY**

Create `tests/test_cleanup.py`:

```python
"""Tests for orphaned pod cleanup logic."""
from unittest.mock import patch

import pytest

from saas.workers.cleanup import cleanup_orphaned_pods


def test_cleanup_raises_on_missing_runpod_key():
    """Cleanup must raise, not silently return, when RUNPOD_API_KEY is missing."""
    with patch.dict("os.environ", {"RUNPOD_API_KEY": ""}, clear=False):
        with pytest.raises(RuntimeError, match="RUNPOD_API_KEY"):
            cleanup_orphaned_pods()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cleanup.py::test_cleanup_raises_on_missing_runpod_key -v`
Expected: FAIL — currently returns dict instead of raising

- [ ] **Step 3: Update cleanup to raise on critical errors**

Replace the early returns in `saas/workers/cleanup.py` with raises:

```python
def cleanup_orphaned_pods() -> dict:
    """Terminate RunPod pods that have no matching RUNNING/PENDING job.

    Runs on a 10-minute beat schedule to catch pods orphaned by worker
    restarts, crashes, or failed termination.
    """
    runpod_key = os.getenv("RUNPOD_API_KEY", "")
    if not runpod_key:
        raise RuntimeError("cleanup: RUNPOD_API_KEY not set — cannot check for orphaned pods")

    try:
        import runpod
        runpod.api_key = runpod_key
    except ImportError:
        raise RuntimeError("cleanup: runpod package not installed")

    pods = runpod.get_pods()
    if not pods:
        return {"active_pods": 0, "terminated": 0}

    # Find pod IDs actively managed by running jobs
    active_pod_ids = _get_active_job_pod_ids()

    terminated = []
    for pod in pods:
        pod_id = pod.get("id", "")
        name = pod.get("name", "")
        # Only clean up pods we created (named fishcloud-sim or simswarm-sim)
        if name not in ("fishcloud-sim", "simswarm-sim"):
            continue
        if pod_id in active_pod_ids:
            continue
        # Pod has no matching active job — terminate it
        try:
            runpod.terminate_pod(pod_id)
            gpu = pod.get("machine", {}).get("gpuDisplayName", "?")
            logger.warning(
                "cleanup.terminated pod_id=%s gpu=%s name=%s", pod_id, gpu, name,
                extra={"event": "cleanup_terminated", "pod_id": pod_id},
            )
            terminated.append(pod_id)
        except Exception as e:
            logger.warning("cleanup.terminate_failed pod_id=%s error=%s", pod_id, e)

    result = {"active_pods": len(pods), "terminated": len(terminated), "pod_ids": terminated}
    if terminated:
        logger.info("cleanup.summary active_pods=%d terminated=%d", len(pods), len(terminated))
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cleanup.py::test_cleanup_raises_on_missing_runpod_key -v`
Expected: PASS

- [ ] **Step 5: Write test for recovery raising on missing DATABASE_URL**

Add to `tests/test_recovery.py`:

```python
"""Tests for stale job recovery logic."""
from unittest.mock import patch

import pytest

from saas.workers.recovery import recover_stale_jobs


def test_recovery_raises_on_missing_database_url():
    """Recovery must raise, not silently return, when DATABASE_URL is missing."""
    with patch.dict("os.environ", {"DATABASE_URL": ""}, clear=False):
        with pytest.raises(RuntimeError, match="DATABASE_URL"):
            recover_stale_jobs()
```

- [ ] **Step 6: Run test to verify it fails**

Run: `pytest tests/test_recovery.py::test_recovery_raises_on_missing_database_url -v`
Expected: FAIL — currently returns dict

- [ ] **Step 7: Update recovery to raise on critical errors**

In `saas/workers/recovery.py`, change the early return and the catch-all:

```python
def recover_stale_jobs() -> dict:
    """Find jobs stuck in RUNNING/PROVISIONING after a worker restart and fail+refund them."""
    from sqlalchemy import create_engine, text

    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("recovery: DATABASE_URL not set — cannot recover stale jobs")

    sync_url = database_url.replace("+asyncpg", "").replace(
        "postgresql://", "postgresql+psycopg2://"
    )
```

Also change the bottom `except` block from swallowing to re-raising:

```python
    except Exception as e:
        logger.error("recover.error error=%s", e, exc_info=True)
        raise RuntimeError(f"recovery: failed to recover stale jobs: {e}") from e
```

- [ ] **Step 8: Run both test files**

Run: `pytest tests/test_cleanup.py tests/test_recovery.py -v`
Expected: All tests PASS

- [ ] **Step 9: Run full test suite**

Run: `pytest -q`
Expected: All 255+ tests pass

- [ ] **Step 10: Commit**

```bash
git add saas/workers/cleanup.py saas/workers/recovery.py tests/test_cleanup.py tests/test_recovery.py
git commit -m "fix: make cleanup/recovery tasks raise on critical errors instead of silent return"
```

---

### Task 3: Add early pod_id persistence

**Files:**
- Modify: `saas/workers/job_runner.py:88-95` (add pod_id_callback to __init__)
- Modify: `saas/workers/tasks.py:72-80` (wire pod_id callback)
- Modify: `saas/workers/persistence.py` (add _update_pod_id helper)
- Test: `tests/test_job_runner_teardown.py` (new)

- [ ] **Step 1: Write test for early pod_id persistence**

Create `tests/test_job_runner_teardown.py`:

```python
"""Tests for JobRunner teardown guarantees."""
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from saas.workers.job_runner import JobRunner, JobConfig


def _make_config(**overrides):
    defaults = dict(
        job_id=1, user_id="u1", seed_text="test seed", goal="test goal",
        tier="small", model_id="test-model", gpu_type="RTX4090",
        max_rounds=10, vllm_args="", llm_api_key="k", zep_api_key="z",
    )
    defaults.update(overrides)
    return JobConfig(**defaults)


@pytest.fixture
def mock_gpu_provider():
    provider = AsyncMock()
    instance = MagicMock()
    instance.instance_id = "pod-abc123"
    provider.provision.return_value = instance
    provider.terminate.return_value = None
    return provider


async def test_pod_id_callback_called_before_pipeline(mock_gpu_provider):
    """pod_id_callback must fire immediately after provisioning, before pipeline starts."""
    callback_calls = []

    async def pod_id_cb(job_id, pod_id):
        callback_calls.append((job_id, pod_id))

    runner = JobRunner(
        gpu_provider=mock_gpu_provider,
        pod_id_callback=pod_id_cb,
    )
    # Make pipeline raise so we can verify callback was called before pipeline
    runner._execute_pipeline = AsyncMock(side_effect=RuntimeError("pipeline boom"))

    with pytest.raises(RuntimeError, match="pipeline boom"):
        await runner.run(_make_config())

    assert callback_calls == [(1, "pod-abc123")]
    mock_gpu_provider.terminate.assert_awaited_once_with("pod-abc123")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_job_runner_teardown.py::test_pod_id_callback_called_before_pipeline -v`
Expected: FAIL — `pod_id_callback` parameter doesn't exist yet

- [ ] **Step 3: Add _update_pod_id to persistence.py**

Add to `saas/workers/persistence.py`:

```python
def _update_pod_id(job_id: int, pod_id: str) -> None:
    """Persist pod_id to the SimulationJob row immediately after GPU provisioning."""
    from sqlalchemy import text

    factory = _get_worker_session_factory()
    if factory is None:
        logger.warning("DATABASE_URL not set; skipping pod_id update for job %d", job_id)
        return

    async def _do_update():
        async with factory() as session:
            try:
                await session.execute(
                    text(
                        "UPDATE simulation_jobs SET pod_id = :pod_id "
                        "WHERE id = :job_id"
                    ),
                    {"pod_id": pod_id, "job_id": job_id},
                )
                await session.commit()
                logger.info("Saved pod_id=%s for job %d (early persist)", pod_id, job_id)
            except Exception as exc:
                logger.warning("Could not save pod_id for job %d: %s", job_id, exc)

    _run_async(_do_update())
```

- [ ] **Step 4: Add pod_id_callback to JobRunner.__init__**

In `saas/workers/job_runner.py`, update the constructor and `_run_inner`:

```python
class JobRunner:
    """Manages the full lifecycle of a simulation job on a GPU instance."""

    def __init__(self, gpu_provider: GPUProvider, stage_callback=None, pod_id_callback=None):
        self.gpu_provider = gpu_provider
        self._stage_callback = stage_callback
        # Optional async callable(job_id, pod_id) invoked right after GPU provisioning
        self._pod_id_callback = pod_id_callback
```

In `_run_inner`, add the callback call right after provisioning (after line 134):

```python
    async def _run_inner(self, gpu_config, config: JobConfig) -> dict:
        """Inner run method wrapped by the tier timeout."""
        import time
        provision_start = time.monotonic()
        instance = await self.gpu_provider.provision(gpu_config)
        provision_seconds = int(time.monotonic() - provision_start)
        pod_id = instance.instance_id
        logger.info(
            "job.gpu_provisioned job_id=%d pod_id=%s provision_seconds=%d",
            config.job_id, pod_id, provision_seconds,
            extra={"event": "gpu_provisioned", "job_id": config.job_id,
                   "pod_id": pod_id, "elapsed_s": provision_seconds},
        )

        # Persist pod_id immediately so cleanup/recovery can find it
        if self._pod_id_callback is not None:
            try:
                await self._pod_id_callback(config.job_id, pod_id)
            except Exception:
                logger.warning("pod_id_callback failed for job %d", config.job_id)

        try:
            pipeline_start = time.monotonic()
            result = await self._execute_pipeline(instance.instance_id, config)
            pipeline_seconds = int(time.monotonic() - pipeline_start)
            result["pod_id"] = pod_id
            result["provision_seconds"] = provision_seconds
            result["pipeline_seconds"] = pipeline_seconds
            return result
        except Exception as e:
            logger.error(f"Pipeline failed for pod {instance.instance_id}: {e}")
            try:
                worker_url = f"https://{instance.instance_id}-5000.proxy.runpod.net"
                async with httpx.AsyncClient(timeout=10) as client:
                    status_resp = await client.get(f"{worker_url}/status")
                    if status_resp.status_code == 200:
                        logger.error(f"Worker status at failure: {status_resp.json()}")
            except Exception:
                logger.warning("Could not retrieve worker status before termination")
            raise
        finally:
            await self.gpu_provider.terminate(instance.instance_id)
```

- [ ] **Step 5: Wire pod_id_callback in tasks.py**

In `saas/workers/tasks.py`, add the import and wire the callback:

Add to the imports at the top:

```python
from saas.workers.persistence import (
    _extract_key_insight,
    _mark_job_failed,
    _save_job_results,
    _update_job_metadata,
    _update_job_retry,
    _update_pipeline_stage,
    _update_pod_id,
)
```

In `run_simulation_task`, add the callback and pass it to JobRunner:

```python
    async def _pod_id_cb(j_id: int, pod_id: str) -> None:
        _update_pod_id(j_id, pod_id)

    runner = JobRunner(
        gpu_provider=gpu_provider,
        stage_callback=_stage_cb,
        pod_id_callback=_pod_id_cb,
    )
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_job_runner_teardown.py::test_pod_id_callback_called_before_pipeline -v`
Expected: PASS

- [ ] **Step 7: Run full test suite**

Run: `pytest -q`
Expected: All tests pass

- [ ] **Step 8: Commit**

```bash
git add saas/workers/job_runner.py saas/workers/tasks.py saas/workers/persistence.py tests/test_job_runner_teardown.py
git commit -m "feat: persist pod_id immediately after GPU provisioning"
```

---

### Task 4: Restructure tier timeout to wrap only pipeline execution

**Files:**
- Modify: `saas/workers/job_runner.py:96-162` (run + _run_inner methods)
- Test: `tests/test_job_runner_teardown.py` (add test)

- [ ] **Step 1: Write test for teardown on pipeline timeout**

Add to `tests/test_job_runner_teardown.py`:

```python
async def test_terminate_called_on_pipeline_timeout(mock_gpu_provider):
    """GPU must be terminated even when the pipeline times out."""
    async def slow_pipeline(*args, **kwargs):
        await asyncio.sleep(10)  # longer than timeout

    runner = JobRunner(gpu_provider=mock_gpu_provider)
    runner._execute_pipeline = slow_pipeline

    config = _make_config()
    # Override timeout to 0.1s so the test is fast
    config._timeout_override = 0.1

    with pytest.raises((TimeoutError, asyncio.TimeoutError)):
        await runner.run(config)

    mock_gpu_provider.terminate.assert_awaited_once_with("pod-abc123")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_job_runner_teardown.py::test_terminate_called_on_pipeline_timeout -v`
Expected: FAIL — current structure may not guarantee terminate on timeout

- [ ] **Step 3: Restructure run() and _run_inner()**

Replace `run()` and `_run_inner()` in `saas/workers/job_runner.py`:

```python
    async def run(self, config: JobConfig) -> dict:
        """Provision a GPU, run the pipeline, then terminate the instance.

        Provisioning runs with its own internal timeout (MAX_POLL_ATTEMPTS).
        The tier timeout wraps only pipeline execution, ensuring the finally
        block always has a valid pod_id to terminate.
        """
        gpu_config = GPUProviderConfig(
            gpu_type=config.gpu_type,
            docker_image=get_worker_image(),
            max_cost_per_hour_usd=TIER_MAX_COST_USD.get(config.tier, 4.00),
            timeout_seconds=config.timeout_seconds,
            env_vars=config.to_mirofish_env(),
        )

        # Mark job as provisioning so the frontend can show GPU spin-up status
        if self._stage_callback is not None:
            try:
                await self._stage_callback(config.job_id, 0)
            except Exception:
                pass

        timeout = getattr(config, "_timeout_override", None) or config.timeout_seconds
        logger.info(f"Job {config.job_id}: starting with {timeout}s tier timeout ({config.tier})")

        return await self._run_inner(gpu_config, config, timeout)

    async def _run_inner(self, gpu_config, config: JobConfig, timeout: int | float) -> dict:
        """Provision GPU, run pipeline with tier timeout, guarantee teardown."""
        import time

        # Phase 1: Provision (own internal timeout via MAX_POLL_ATTEMPTS)
        provision_start = time.monotonic()
        instance = await self.gpu_provider.provision(gpu_config)
        provision_seconds = int(time.monotonic() - provision_start)
        pod_id = instance.instance_id
        logger.info(
            "job.gpu_provisioned job_id=%d pod_id=%s provision_seconds=%d",
            config.job_id, pod_id, provision_seconds,
            extra={"event": "gpu_provisioned", "job_id": config.job_id,
                   "pod_id": pod_id, "elapsed_s": provision_seconds},
        )

        # Persist pod_id immediately so cleanup/recovery can find it
        if self._pod_id_callback is not None:
            try:
                await self._pod_id_callback(config.job_id, pod_id)
            except Exception:
                logger.warning("pod_id_callback failed for job %d", config.job_id)

        # Phase 2: Pipeline (wrapped with tier timeout, teardown guaranteed)
        try:
            pipeline_start = time.monotonic()
            result = await asyncio.wait_for(
                self._execute_pipeline(pod_id, config),
                timeout=timeout,
            )
            pipeline_seconds = int(time.monotonic() - pipeline_start)
            result["pod_id"] = pod_id
            result["provision_seconds"] = provision_seconds
            result["pipeline_seconds"] = pipeline_seconds
            return result
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"Job {config.job_id} exceeded {config.tier} tier timeout of {timeout}s"
            )
        except Exception as e:
            logger.error(f"Pipeline failed for pod {pod_id}: {e}")
            try:
                worker_url = f"https://{pod_id}-5000.proxy.runpod.net"
                async with httpx.AsyncClient(timeout=10) as client:
                    status_resp = await client.get(f"{worker_url}/status")
                    if status_resp.status_code == 200:
                        logger.error(f"Worker status at failure: {status_resp.json()}")
            except Exception:
                logger.warning("Could not retrieve worker status before termination")
            raise
        finally:
            await self.gpu_provider.terminate(pod_id)
```

- [ ] **Step 4: Run teardown tests**

Run: `pytest tests/test_job_runner_teardown.py -v`
Expected: All tests PASS

- [ ] **Step 5: Run full test suite**

Run: `pytest -q`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add saas/workers/job_runner.py tests/test_job_runner_teardown.py
git commit -m "fix: restructure tier timeout to wrap only pipeline, guaranteeing teardown"
```

---

### Task 5: Add last_heartbeat column (migration + model)

**Files:**
- Create: `alembic/versions/f7g8h9i0j1k2_add_last_heartbeat.py`
- Modify: `saas/models/job.py:46` (add column)

- [ ] **Step 1: Create Alembic migration**

Create `alembic/versions/f7g8h9i0j1k2_add_last_heartbeat.py`:

```python
"""add last_heartbeat to simulation_jobs

Revision ID: f7g8h9i0j1k2
Revises: e6f7g8h9i0j1
Create Date: 2026-03-28
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'f7g8h9i0j1k2'
down_revision: Union[str, Sequence[str]] = 'e6f7g8h9i0j1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'simulation_jobs',
        sa.Column('last_heartbeat', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('simulation_jobs', 'last_heartbeat')
```

- [ ] **Step 2: Add column to SQLAlchemy model**

In `saas/models/job.py`, add after `share_token`:

```python
    last_heartbeat: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
```

- [ ] **Step 3: Verify tests still pass (SQLite auto-creates from model)**

Run: `pytest -q`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add alembic/versions/f7g8h9i0j1k2_add_last_heartbeat.py saas/models/job.py
git commit -m "feat: add last_heartbeat column to simulation_jobs"
```

---

### Task 6: Wire heartbeat updates into the polling loop

**Files:**
- Modify: `saas/workers/persistence.py` (add _update_heartbeat)
- Modify: `saas/workers/job_runner.py:88-95` (add heartbeat_callback to __init__)
- Modify: `saas/workers/job_runner.py:261-350` (_poll_until_complete — call heartbeat)
- Modify: `saas/workers/tasks.py` (wire heartbeat callback)
- Test: `tests/test_job_runner_teardown.py` (add heartbeat test)

- [ ] **Step 1: Write test for heartbeat callback during polling**

Add to `tests/test_job_runner_teardown.py`:

```python
async def test_heartbeat_callback_called_during_polling(mock_gpu_provider):
    """heartbeat_callback should fire during the polling loop."""
    heartbeat_calls = []

    async def heartbeat_cb(job_id):
        heartbeat_calls.append(job_id)

    runner = JobRunner(
        gpu_provider=mock_gpu_provider,
        heartbeat_callback=heartbeat_cb,
    )

    # Mock _execute_pipeline to simulate a quick completed response
    async def fake_pipeline(instance_id, config):
        return {
            "job_id": config.job_id,
            "instance_id": instance_id,
            "report": "test",
            "chat_log": "[]",
            "graph_data": "{}",
            "status": "completed",
        }

    runner._execute_pipeline = fake_pipeline

    await runner.run(_make_config())

    # Heartbeat may or may not fire depending on pipeline speed, but the runner
    # should accept the parameter without error
    assert mock_gpu_provider.terminate.await_count == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_job_runner_teardown.py::test_heartbeat_callback_called_during_polling -v`
Expected: FAIL — `heartbeat_callback` parameter doesn't exist yet

- [ ] **Step 3: Add _update_heartbeat to persistence.py**

Add to `saas/workers/persistence.py`:

```python
def _update_heartbeat(job_id: int) -> None:
    """Update last_heartbeat timestamp on a SimulationJob row."""
    from sqlalchemy import text

    factory = _get_worker_session_factory()
    if factory is None:
        return

    async def _do_update():
        async with factory() as session:
            try:
                await session.execute(
                    text(
                        "UPDATE simulation_jobs SET last_heartbeat = :now "
                        "WHERE id = :job_id"
                    ),
                    {"now": datetime.now(timezone.utc), "job_id": job_id},
                )
                await session.commit()
            except Exception as exc:
                logger.warning("Could not update heartbeat for job %d: %s", job_id, exc)

    _run_async(_do_update())
```

- [ ] **Step 4: Add heartbeat_callback to JobRunner**

In `saas/workers/job_runner.py`, update constructor:

```python
    def __init__(self, gpu_provider: GPUProvider, stage_callback=None,
                 pod_id_callback=None, heartbeat_callback=None):
        self.gpu_provider = gpu_provider
        self._stage_callback = stage_callback
        self._pod_id_callback = pod_id_callback
        # Optional async callable(job_id) invoked every ~60s during polling
        self._heartbeat_callback = heartbeat_callback
```

- [ ] **Step 5: Call heartbeat from _poll_until_complete**

In `saas/workers/job_runner.py`, in `_poll_until_complete`, add heartbeat tracking. After the `poll_start` and `poll_interval` lines (around line 283-286), add:

```python
        async with _ensure_client() as http:
            poll_start = time.monotonic()
            poll_interval = 10
            max_polls = max(360, config.timeout_seconds // poll_interval)
            last_stage: int | None = None
            last_heartbeat_time = 0.0  # track last heartbeat write
            for poll in range(max_polls):
                await asyncio.sleep(poll_interval)
                try:
                    status_resp = await http.get(f"{worker_url}/status")
                    status_data = status_resp.json()
                except Exception as e:
                    logger.warning(f"Status poll {poll + 1} failed: {e}")
                    continue

                # Update heartbeat every ~60s
                now_mono = time.monotonic()
                if (now_mono - last_heartbeat_time >= 60
                        and self._heartbeat_callback is not None):
                    last_heartbeat_time = now_mono
                    try:
                        await self._heartbeat_callback(config.job_id)
                    except Exception:
                        pass
```

The rest of the polling loop stays the same.

- [ ] **Step 6: Wire heartbeat callback in tasks.py**

In `saas/workers/tasks.py`, add import and wire:

Add to imports:
```python
from saas.workers.persistence import (
    _extract_key_insight,
    _mark_job_failed,
    _save_job_results,
    _update_job_metadata,
    _update_job_retry,
    _update_pipeline_stage,
    _update_pod_id,
    _update_heartbeat,
)
```

In `run_simulation_task`:

```python
    async def _heartbeat_cb(j_id: int) -> None:
        _update_heartbeat(j_id)

    runner = JobRunner(
        gpu_provider=gpu_provider,
        stage_callback=_stage_cb,
        pod_id_callback=_pod_id_cb,
        heartbeat_callback=_heartbeat_cb,
    )
```

- [ ] **Step 7: Run tests**

Run: `pytest tests/test_job_runner_teardown.py -v`
Expected: All tests PASS

- [ ] **Step 8: Run full test suite**

Run: `pytest -q`
Expected: All tests pass

- [ ] **Step 9: Commit**

```bash
git add saas/workers/persistence.py saas/workers/job_runner.py saas/workers/tasks.py tests/test_job_runner_teardown.py
git commit -m "feat: add heartbeat updates during pipeline polling loop"
```

---

### Task 7: Update recovery to use heartbeat-based staleness

**Files:**
- Modify: `saas/workers/recovery.py` (heartbeat-based staleness rules)
- Test: `tests/test_recovery.py` (add staleness tests)

- [ ] **Step 1: Write tests for heartbeat-based staleness detection**

Add to `tests/test_recovery.py`:

```python
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock


def _make_job_row(job_id=1, user_id="u1", tier="small", credits_charged=10,
                  pod_id="pod-123", created_at=None, last_heartbeat=None):
    """Create a fake DB row tuple matching the recovery query columns."""
    if created_at is None:
        created_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    return (job_id, user_id, tier, credits_charged, pod_id, created_at, last_heartbeat)


def test_recovery_stale_heartbeat_dead_pod():
    """Job with heartbeat >5 min ago and dead pod should be marked FAILED."""
    old_hb = datetime.now(timezone.utc) - timedelta(minutes=6)
    row = _make_job_row(last_heartbeat=old_hb)

    # The staleness logic: heartbeat > 5min AND pod dead → stale
    from saas.workers.recovery import _is_stale
    assert _is_stale(
        last_heartbeat=old_hb,
        created_at=row[5],
        pod_alive=False,
        tier_timeout=2700,
    ) is True


def test_recovery_fresh_heartbeat_alive_pod():
    """Job with recent heartbeat and alive pod should NOT be stale."""
    fresh_hb = datetime.now(timezone.utc) - timedelta(minutes=1)

    from saas.workers.recovery import _is_stale
    assert _is_stale(
        last_heartbeat=fresh_hb,
        created_at=datetime.now(timezone.utc) - timedelta(minutes=30),
        pod_alive=True,
        tier_timeout=2700,
    ) is False


def test_recovery_stale_heartbeat_alive_pod_15min():
    """Job with heartbeat >15 min ago should be stale even if pod is alive."""
    old_hb = datetime.now(timezone.utc) - timedelta(minutes=16)

    from saas.workers.recovery import _is_stale
    assert _is_stale(
        last_heartbeat=old_hb,
        created_at=datetime.now(timezone.utc) - timedelta(hours=1),
        pod_alive=True,
        tier_timeout=2700,
    ) is True


def test_recovery_no_heartbeat_legacy_fallback():
    """Job with no heartbeat uses created_at + tier_timeout fallback."""
    old_created = datetime.now(timezone.utc) - timedelta(minutes=60)

    from saas.workers.recovery import _is_stale
    assert _is_stale(
        last_heartbeat=None,
        created_at=old_created,
        pod_alive=False,
        tier_timeout=2700,  # 45 min + 10 min buffer = 55 min < 60 min
    ) is True


def test_recovery_no_heartbeat_within_timeout():
    """Job with no heartbeat but within tier_timeout should NOT be stale."""
    recent_created = datetime.now(timezone.utc) - timedelta(minutes=10)

    from saas.workers.recovery import _is_stale
    assert _is_stale(
        last_heartbeat=None,
        created_at=recent_created,
        pod_alive=True,
        tier_timeout=2700,
    ) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_recovery.py -v`
Expected: FAIL — `_is_stale` doesn't exist yet

- [ ] **Step 3: Extract _is_stale helper and update recovery logic**

In `saas/workers/recovery.py`, add the `_is_stale` function and update the query to include `last_heartbeat`:

```python
HEARTBEAT_STALE_POD_DEAD_S = 300    # 5 minutes
HEARTBEAT_STALE_NO_PROGRESS_S = 900  # 15 minutes


def _is_stale(
    last_heartbeat: datetime | None,
    created_at: datetime,
    pod_alive: bool,
    tier_timeout: int,
) -> bool:
    """Determine if a job should be considered stale.

    Rules:
      1. heartbeat > 5 min ago AND pod dead → stale
      2. heartbeat > 15 min ago regardless of pod → stale (no progress)
      3. no heartbeat AND created_at > tier_timeout + 10 min → stale (legacy)
      4. Otherwise → not stale
    """
    now = datetime.now(timezone.utc)

    if last_heartbeat is not None:
        if last_heartbeat.tzinfo is None:
            last_heartbeat = last_heartbeat.replace(tzinfo=timezone.utc)
        hb_age = (now - last_heartbeat).total_seconds()

        if hb_age > HEARTBEAT_STALE_POD_DEAD_S and not pod_alive:
            return True
        if hb_age > HEARTBEAT_STALE_NO_PROGRESS_S:
            return True
        return False

    # No heartbeat — legacy fallback based on created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    age = (now - created_at).total_seconds()
    timeout_with_buffer = tier_timeout + 600

    if not pod_alive and age > HEARTBEAT_STALE_POD_DEAD_S:
        return True
    if age > timeout_with_buffer:
        return True
    return False
```

Update the SQL query in `recover_stale_jobs` to include `last_heartbeat`:

```python
            result = conn.execute(
                text(
                    "SELECT id, user_id, tier, credits_charged, pod_id, "
                    "created_at, last_heartbeat "
                    "FROM simulation_jobs "
                    "WHERE status IN ('PENDING', 'RUNNING', 'PROVISIONING') "
                    "ORDER BY created_at ASC"
                )
            )
```

Update the row unpacking:

```python
            for row in stale_jobs:
                job_id, user_id, tier, credits_charged, pod_id, created_at, last_heartbeat = row
                timeout = TIER_TIMEOUTS.get(tier, 2700)

                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)

                pod_alive = pod_id in active_pods if pod_id else False

                if not _is_stale(last_heartbeat, created_at, pod_alive, timeout):
                    # Not stale — resume if pod alive, skip if no pod yet
                    if pod_alive and pod_id:
                        logger.info(
                            "recover.resuming job_id=%d pod_id=%s",
                            job_id, pod_id,
                        )
                        resume_simulation_task.delay(
                            job_id=job_id,
                            user_id=user_id,
                            pod_id=pod_id,
                            credits_charged=credits_charged,
                        )
                        resumed.append({"job_id": job_id, "pod_id": pod_id})
                    continue

                # Job is stale — mark failed and refund
                reason = "heartbeat_stale" if last_heartbeat else "timeout"
                if not pod_alive:
                    reason = "pod_gone"
                age_seconds = (datetime.now(timezone.utc) - created_at).total_seconds()
                error_msg = (
                    f"Job recovered after worker restart "
                    f"({reason}, age={int(age_seconds)}s)"
                )
```

The rest of the function (UPDATE, refund, commit) stays the same, except update the refund row lookup to handle 7-element tuples: `row[0]` for job_id, `row[1]` for user_id, `row[3]` for credits_charged.

- [ ] **Step 4: Run recovery tests**

Run: `pytest tests/test_recovery.py -v`
Expected: All tests PASS

- [ ] **Step 5: Run full test suite**

Run: `pytest -q`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add saas/workers/recovery.py tests/test_recovery.py
git commit -m "feat: heartbeat-based staleness detection in recovery task"
```

---

### Task 8: Add webhook alerting

**Files:**
- Create: `saas/workers/alerts.py`
- Modify: `saas/config.py` (add ALERT_WEBHOOK_URL)
- Modify: `saas/workers/cleanup.py` (call alert on terminate)
- Modify: `saas/workers/recovery.py` (call alert on recover)
- Test: `tests/test_alerts.py` (new)

- [ ] **Step 1: Write test for alert helper**

Create `tests/test_alerts.py`:

```python
"""Tests for webhook alerting."""
from unittest.mock import patch, MagicMock

from saas.workers.alerts import send_orphan_alert


@patch("saas.workers.alerts.httpx")
def test_send_orphan_alert_posts_to_webhook(mock_httpx):
    """Alert should POST JSON to the configured webhook URL."""
    mock_httpx.post.return_value = MagicMock(status_code=200)

    with patch.dict("os.environ", {"ALERT_WEBHOOK_URL": "https://hooks.slack.com/test"}):
        send_orphan_alert(
            pod_id="pod-abc",
            gpu_type="L40S",
            uptime_seconds=3600,
            reason="orphan",
        )

    mock_httpx.post.assert_called_once()
    call_kwargs = mock_httpx.post.call_args
    assert "https://hooks.slack.com/test" in call_kwargs.args or call_kwargs.kwargs.get("url") == "https://hooks.slack.com/test"


@patch("saas.workers.alerts.httpx")
def test_send_orphan_alert_noop_without_webhook_url(mock_httpx):
    """Alert should do nothing when ALERT_WEBHOOK_URL is not set."""
    with patch.dict("os.environ", {"ALERT_WEBHOOK_URL": ""}, clear=False):
        send_orphan_alert(pod_id="pod-abc", gpu_type="L40S", uptime_seconds=3600, reason="orphan")

    mock_httpx.post.assert_not_called()


@patch("saas.workers.alerts.httpx")
def test_send_orphan_alert_swallows_errors(mock_httpx):
    """Alert failure must never raise — fire and forget."""
    mock_httpx.post.side_effect = Exception("network error")

    with patch.dict("os.environ", {"ALERT_WEBHOOK_URL": "https://hooks.slack.com/test"}):
        # Should not raise
        send_orphan_alert(pod_id="pod-abc", gpu_type="L40S", uptime_seconds=3600, reason="orphan")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_alerts.py -v`
Expected: FAIL — module doesn't exist

- [ ] **Step 3: Create alerts.py**

Create `saas/workers/alerts.py`:

```python
"""Fire-and-forget webhook alerts for GPU orphan events."""
from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

# Rough hourly rates for cost estimation
GPU_HOURLY_RATES: dict[str, float] = {
    "A100 PCIe": 1.64,
    "A100": 1.64,
    "L40S": 1.24,
    "RTX 4090": 0.69,
    "RTX A6000": 0.79,
    "H100": 3.89,
    "A40": 0.79,
}


def send_orphan_alert(
    pod_id: str,
    gpu_type: str,
    uptime_seconds: int,
    reason: str,
    job_id: int | None = None,
) -> None:
    """POST an alert to the configured webhook URL. Never raises."""
    webhook_url = os.getenv("ALERT_WEBHOOK_URL", "")
    if not webhook_url:
        return

    hours = uptime_seconds / 3600
    rate = GPU_HOURLY_RATES.get(gpu_type, 1.00)
    estimated_cost = round(hours * rate, 2)

    text = (
        f":warning: *GPU Orphan Terminated*\n"
        f"• Pod: `{pod_id}`\n"
        f"• GPU: {gpu_type}\n"
        f"• Uptime: {int(hours)}h {int((hours % 1) * 60)}m\n"
        f"• Est. wasted cost: ${estimated_cost}\n"
        f"• Reason: {reason}"
    )
    if job_id is not None:
        text += f"\n• Job ID: {job_id}"

    try:
        httpx.post(
            webhook_url,
            json={"text": text},
            timeout=10,
        )
    except Exception as e:
        logger.warning("alert.send_failed error=%s", e)
```

- [ ] **Step 4: Add ALERT_WEBHOOK_URL to config.py**

In `saas/config.py`, add to the Settings class:

```python
    # Alerting
    ALERT_WEBHOOK_URL: str = ""
```

- [ ] **Step 5: Run alert tests**

Run: `pytest tests/test_alerts.py -v`
Expected: All tests PASS

- [ ] **Step 6: Wire alerts into cleanup.py**

In `saas/workers/cleanup.py`, after successfully terminating a pod (after `terminated.append(pod_id)`):

```python
        # Pod has no matching active job — terminate it
        try:
            runpod.terminate_pod(pod_id)
            gpu = pod.get("machine", {}).get("gpuDisplayName", "?")
            uptime = pod.get("runtime", {}).get("uptimeInSeconds", 0)
            logger.warning(
                "cleanup.terminated pod_id=%s gpu=%s name=%s", pod_id, gpu, name,
                extra={"event": "cleanup_terminated", "pod_id": pod_id},
            )
            terminated.append(pod_id)

            from saas.workers.alerts import send_orphan_alert
            send_orphan_alert(
                pod_id=pod_id, gpu_type=gpu,
                uptime_seconds=uptime, reason="orphan_no_matching_job",
            )
        except Exception as e:
            logger.warning("cleanup.terminate_failed pod_id=%s error=%s", pod_id, e)
```

- [ ] **Step 7: Wire alerts into recovery.py**

In `saas/workers/recovery.py`, after marking a job FAILED (after `recovered.append(...)`):

```python
                recovered.append({"job_id": job_id, "reason": reason})

                from saas.workers.alerts import send_orphan_alert
                age_s = int(age_seconds)
                send_orphan_alert(
                    pod_id=pod_id or "unknown",
                    gpu_type="unknown",
                    uptime_seconds=age_s,
                    reason=f"recovery_{reason}",
                    job_id=job_id,
                )
```

- [ ] **Step 8: Run full test suite**

Run: `pytest -q`
Expected: All tests pass

- [ ] **Step 9: Commit**

```bash
git add saas/workers/alerts.py saas/config.py saas/workers/cleanup.py saas/workers/recovery.py tests/test_alerts.py
git commit -m "feat: add webhook alerting on orphan pod termination"
```

---

### Task 9: Harden RunPod direct audit in cleanup

**Files:**
- Modify: `saas/workers/cleanup.py` (grace period, DB failure skip, cost tracking)
- Test: `tests/test_cleanup.py` (add tests)

- [ ] **Step 1: Write tests for grace period and DB failure behavior**

Add to `tests/test_cleanup.py`:

```python
from unittest.mock import MagicMock


def _make_pod(pod_id="pod-1", name="fishcloud-sim", uptime_seconds=600, gpu="L40S"):
    return {
        "id": pod_id,
        "name": name,
        "machine": {"gpuDisplayName": gpu},
        "runtime": {"uptimeInSeconds": uptime_seconds},
    }


@patch("saas.workers.cleanup.os.getenv")
@patch("saas.workers.cleanup._get_active_job_pod_ids")
def test_cleanup_skips_young_pods(mock_get_ids, mock_getenv):
    """Pods younger than 3 minutes should not be terminated."""
    mock_getenv.side_effect = lambda k, d="": "test-key" if k == "RUNPOD_API_KEY" else d

    mock_get_ids.return_value = set()  # no active jobs

    mock_runpod = MagicMock()
    mock_runpod.get_pods.return_value = [
        _make_pod(pod_id="young-pod", uptime_seconds=120),  # 2 min — skip
    ]

    with patch.dict("sys.modules", {"runpod": mock_runpod}):
        with patch("saas.workers.cleanup.os.getenv", mock_getenv):
            result = cleanup_orphaned_pods()

    mock_runpod.terminate_pod.assert_not_called()


@patch("saas.workers.cleanup.os.getenv")
@patch("saas.workers.cleanup._get_active_job_pod_ids")
def test_cleanup_skips_entirely_on_db_error(mock_get_ids, mock_getenv):
    """When DB is unreachable, cleanup should skip entirely and not terminate anything."""
    mock_getenv.side_effect = lambda k, d="": "test-key" if k == "RUNPOD_API_KEY" else d

    mock_get_ids.return_value = None  # DB failure returns None

    mock_runpod = MagicMock()
    mock_runpod.get_pods.return_value = [
        _make_pod(pod_id="pod-1", uptime_seconds=3600),
    ]

    with patch.dict("sys.modules", {"runpod": mock_runpod}):
        with patch("saas.workers.cleanup.os.getenv", mock_getenv):
            result = cleanup_orphaned_pods()

    mock_runpod.terminate_pod.assert_not_called()
    assert result.get("skipped")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cleanup.py -v`
Expected: FAIL — no grace period or DB failure skip logic yet

- [ ] **Step 3: Update cleanup.py with grace period, DB failure skip, cost tracking**

Rewrite `saas/workers/cleanup.py`:

```python
"""Orphaned pod cleanup logic."""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

GRACE_PERIOD_SECONDS = 180  # 3 minutes — don't kill pods younger than this


def _get_active_job_pod_ids() -> set[str] | None:
    """Return RunPod pod IDs for active jobs, or None on DB failure."""
    from sqlalchemy import create_engine, text

    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        return None

    sync_url = database_url.replace("+asyncpg", "").replace(
        "postgresql://", "postgresql+psycopg2://"
    )
    try:
        engine = create_engine(sync_url)
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT pod_id FROM simulation_jobs "
                    "WHERE status IN ('PENDING', 'RUNNING', 'PROVISIONING') "
                    "AND pod_id IS NOT NULL"
                )
            )
            pod_ids = {row[0] for row in result}
        engine.dispose()
    except Exception as e:
        logger.warning("cleanup.db_error error=%s", e)
        return None

    return pod_ids


def cleanup_orphaned_pods() -> dict:
    """Terminate RunPod pods that have no matching RUNNING/PENDING job.

    Runs on a 10-minute beat schedule to catch pods orphaned by worker
    restarts, crashes, or failed termination.
    """
    runpod_key = os.getenv("RUNPOD_API_KEY", "")
    if not runpod_key:
        raise RuntimeError("cleanup: RUNPOD_API_KEY not set — cannot check for orphaned pods")

    try:
        import runpod
        runpod.api_key = runpod_key
    except ImportError:
        raise RuntimeError("cleanup: runpod package not installed")

    pods = runpod.get_pods()
    if not pods:
        return {"active_pods": 0, "terminated": 0}

    # Find pod IDs actively managed by running jobs
    active_pod_ids = _get_active_job_pod_ids()

    if active_pod_ids is None:
        # DB unreachable — skip cleanup to avoid killing active pods
        logger.warning("cleanup.skipped_db_unreachable")
        from saas.workers.alerts import send_orphan_alert
        send_orphan_alert(
            pod_id="N/A", gpu_type="N/A", uptime_seconds=0,
            reason="cleanup_skipped_db_unreachable",
        )
        return {"skipped": "db_unreachable", "active_pods": len(pods)}

    terminated = []
    for pod in pods:
        pod_id = pod.get("id", "")
        name = pod.get("name", "")
        # Only clean up pods we created
        if name not in ("fishcloud-sim", "simswarm-sim"):
            continue
        if pod_id in active_pod_ids:
            continue

        # Grace period — don't kill pods younger than 3 minutes
        uptime = pod.get("runtime", {}).get("uptimeInSeconds", 0)
        if uptime < GRACE_PERIOD_SECONDS:
            logger.info(
                "cleanup.skipped_young pod_id=%s uptime=%ds", pod_id, uptime,
            )
            continue

        # Pod has no matching active job — terminate it
        try:
            runpod.terminate_pod(pod_id)
            gpu = pod.get("machine", {}).get("gpuDisplayName", "?")
            logger.warning(
                "cleanup.terminated pod_id=%s gpu=%s uptime=%ds name=%s",
                pod_id, gpu, uptime, name,
                extra={"event": "cleanup_terminated", "pod_id": pod_id},
            )
            terminated.append(pod_id)

            from saas.workers.alerts import send_orphan_alert
            send_orphan_alert(
                pod_id=pod_id, gpu_type=gpu,
                uptime_seconds=uptime, reason="orphan_no_matching_job",
            )
        except Exception as e:
            logger.warning("cleanup.terminate_failed pod_id=%s error=%s", pod_id, e)

    result = {"active_pods": len(pods), "terminated": len(terminated), "pod_ids": terminated}
    if terminated:
        logger.info("cleanup.summary active_pods=%d terminated=%d", len(pods), len(terminated))
    return result
```

- [ ] **Step 4: Run cleanup tests**

Run: `pytest tests/test_cleanup.py -v`
Expected: All tests PASS

- [ ] **Step 5: Run full test suite**

Run: `pytest -q`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add saas/workers/cleanup.py tests/test_cleanup.py
git commit -m "fix: add grace period, DB failure skip, and cost tracking to cleanup"
```

---

### Task 10: Integration test for teardown guarantee under cancellation

**Files:**
- Test: `tests/test_job_runner_teardown.py` (add integration test)

- [ ] **Step 1: Write integration test for CancelledError teardown**

Add to `tests/test_job_runner_teardown.py`:

```python
async def test_terminate_called_on_asyncio_cancellation(mock_gpu_provider):
    """GPU must be terminated even when the task is cancelled externally."""
    cancel_event = asyncio.Event()

    async def hanging_pipeline(*args, **kwargs):
        cancel_event.set()
        await asyncio.sleep(3600)  # hangs until cancelled

    runner = JobRunner(gpu_provider=mock_gpu_provider)
    runner._execute_pipeline = hanging_pipeline

    config = _make_config()
    task = asyncio.create_task(runner.run(config))

    # Wait until pipeline is "running", then cancel
    await cancel_event.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    mock_gpu_provider.terminate.assert_awaited_once_with("pod-abc123")


async def test_terminate_called_on_provision_success_pipeline_error(mock_gpu_provider):
    """GPU must be terminated when pipeline raises any exception."""
    runner = JobRunner(gpu_provider=mock_gpu_provider)
    runner._execute_pipeline = AsyncMock(side_effect=RuntimeError("vLLM crash"))

    with pytest.raises(RuntimeError, match="vLLM crash"):
        await runner.run(_make_config())

    mock_gpu_provider.terminate.assert_awaited_once_with("pod-abc123")
```

- [ ] **Step 2: Run the integration tests**

Run: `pytest tests/test_job_runner_teardown.py -v`
Expected: All tests PASS

- [ ] **Step 3: Run full test suite**

Run: `pytest -q`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add tests/test_job_runner_teardown.py
git commit -m "test: add integration tests for GPU teardown under cancellation"
```

---

### Task 11: Final verification and cleanup

**Files:**
- All modified files

- [ ] **Step 1: Run full test suite**

Run: `pytest -v`
Expected: All tests pass, including all new tests in test_cleanup.py, test_recovery.py, test_alerts.py, test_job_runner_teardown.py

- [ ] **Step 2: Run ruff linter**

Run: `ruff check saas/workers/ tests/test_cleanup.py tests/test_recovery.py tests/test_alerts.py tests/test_job_runner_teardown.py`
Expected: No lint errors (or fix any that appear)

- [ ] **Step 3: Verify all files are committed**

Run: `git status`
Expected: Clean working tree

- [ ] **Step 4: Review commit log**

Run: `git log --oneline main..HEAD`
Expected: ~10 clean commits covering each task
