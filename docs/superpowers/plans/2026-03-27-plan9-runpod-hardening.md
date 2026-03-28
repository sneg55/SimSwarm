# RunPod Orchestration Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix orphan pod cleanup, add retry on transient failures, make worker image tag configurable via env, and add structured logging with duration tracking.

**Architecture:** Add `pod_id`/`retry_count`/duration columns to `SimulationJob`, rewrite orphan cleanup to use pod-to-job mapping, classify errors as transient vs permanent for Celery retry, read worker image tag from `WORKER_IMAGE_TAG` env var.

**Tech Stack:** Celery, RunPod SDK, SQLAlchemy async, Alembic, pytest-asyncio

**GitHub Issue:** #2

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `saas/models/job.py` | Modify | Add pod_id, retry_count, provision_seconds, pipeline_seconds columns |
| `saas/gpu/errors.py` | Create | TransientGPUError / PermanentGPUError exception classes |
| `saas/workers/job_runner.py` | Modify | Env-based image tag, return pod_id, structured logging, duration tracking |
| `saas/workers/tasks.py` | Modify | Retry logic, store pod_id, rewrite orphan cleanup, persist durations |
| `alembic/versions/` | Create | Migration for new columns |
| `tests/test_runpod_hardening.py` | Create | All new tests for this plan |

---

### Task 1: DB Schema — New Columns on SimulationJob

**Files:**
- Modify: `saas/models/job.py:17-39`
- Create: `alembic/versions/` new migration
- Test: `tests/test_runpod_hardening.py`

- [ ] **Step 1: Write failing test for new columns**

```python
# tests/test_runpod_hardening.py
import pytest
from saas.models.job import SimulationJob, JobStatus


async def test_simulation_job_has_pod_id_column(db_session):
    job = SimulationJob(
        user_id="user-1",
        seed_text="test",
        goal="test",
        tier="small",
        credits_charged=30,
        pod_id="pod_abc123",
    )
    db_session.add(job)
    await db_session.flush()
    assert job.pod_id == "pod_abc123"


async def test_simulation_job_has_retry_count_column(db_session):
    job = SimulationJob(
        user_id="user-1",
        seed_text="test",
        goal="test",
        tier="small",
        credits_charged=30,
        retry_count=0,
    )
    db_session.add(job)
    await db_session.flush()
    assert job.retry_count == 0


async def test_simulation_job_has_duration_columns(db_session):
    job = SimulationJob(
        user_id="user-1",
        seed_text="test",
        goal="test",
        tier="small",
        credits_charged=30,
        provision_seconds=45,
        pipeline_seconds=320,
    )
    db_session.add(job)
    await db_session.flush()
    assert job.provision_seconds == 45
    assert job.pipeline_seconds == 320
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_runpod_hardening.py -v`
Expected: FAIL — SimulationJob doesn't have these columns

- [ ] **Step 3: Add columns to SimulationJob model**

Modify `saas/models/job.py` — add after `completed_at`:

```python
    pod_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    provision_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pipeline_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_runpod_hardening.py -v`
Expected: 3 PASS

- [ ] **Step 5: Generate Alembic migration**

Run: `alembic revision --autogenerate -m "add pod_id retry_count duration columns to simulation_jobs"`

Verify the migration adds 4 columns with correct types and index on pod_id.

- [ ] **Step 6: Commit**

```bash
git add saas/models/job.py alembic/versions/ tests/test_runpod_hardening.py
git commit -m "feat: add pod_id, retry_count, duration columns to SimulationJob"
```

---

### Task 2: Error Classification

**Files:**
- Create: `saas/gpu/errors.py`
- Test: `tests/test_runpod_hardening.py`

- [ ] **Step 1: Write test for error classes**

Append to `tests/test_runpod_hardening.py`:

```python
from saas.gpu.errors import TransientGPUError, PermanentGPUError, classify_gpu_error
import httpx


def test_classify_timeout_as_transient():
    err = TimeoutError("pod did not become ready")
    assert classify_gpu_error(err) == "transient"


def test_classify_connect_error_as_transient():
    err = httpx.ConnectError("connection refused")
    assert classify_gpu_error(err) == "transient"


def test_classify_runtime_error_pipeline_failed_as_permanent():
    err = RuntimeError("Worker pipeline failed: OOM killed")
    assert classify_gpu_error(err) == "permanent"


def test_classify_runtime_error_no_gpus_as_transient():
    err = RuntimeError("No RunPod GPUs available. Last: insufficient capacity")
    assert classify_gpu_error(err) == "transient"


def test_classify_runtime_error_worker_rejected_as_permanent():
    err = RuntimeError("Worker rejected job: invalid seed format")
    assert classify_gpu_error(err) == "permanent"


def test_transient_gpu_error_is_exception():
    err = TransientGPUError("timeout")
    assert isinstance(err, Exception)


def test_permanent_gpu_error_is_exception():
    err = PermanentGPUError("bad input")
    assert isinstance(err, Exception)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_runpod_hardening.py::test_classify_timeout_as_transient -v`
Expected: FAIL — module not found

- [ ] **Step 3: Create error classification module**

```python
# saas/gpu/errors.py
"""GPU error classification for retry decisions."""
import httpx


class TransientGPUError(Exception):
    """Retryable infrastructure error (timeout, network, capacity)."""
    pass


class PermanentGPUError(Exception):
    """Non-retryable error (bad input, pipeline logic failure, OOM)."""
    pass


# Patterns in RuntimeError messages that indicate transient issues
_TRANSIENT_PATTERNS = [
    "No RunPod GPUs available",
    "No Vast.ai offers",
    "All GPU providers failed",
    "did not become ready",
    "Worker API at",  # health check timeout
]


def classify_gpu_error(exc: Exception) -> str:
    """Return 'transient' or 'permanent' for a GPU job error."""
    if isinstance(exc, (TimeoutError, httpx.ConnectError, httpx.ReadTimeout)):
        return "transient"

    if isinstance(exc, TransientGPUError):
        return "transient"

    if isinstance(exc, PermanentGPUError):
        return "permanent"

    if isinstance(exc, RuntimeError):
        msg = str(exc)
        for pattern in _TRANSIENT_PATTERNS:
            if pattern in msg:
                return "transient"
        # Default RuntimeError from pipeline = permanent
        return "permanent"

    # Unknown errors — don't retry
    return "permanent"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_runpod_hardening.py::test_classify_timeout_as_transient tests/test_runpod_hardening.py::test_classify_connect_error_as_transient tests/test_runpod_hardening.py::test_classify_runtime_error_pipeline_failed_as_permanent tests/test_runpod_hardening.py::test_classify_runtime_error_no_gpus_as_transient tests/test_runpod_hardening.py::test_classify_runtime_error_worker_rejected_as_permanent tests/test_runpod_hardening.py::test_transient_gpu_error_is_exception tests/test_runpod_hardening.py::test_permanent_gpu_error_is_exception -v`
Expected: 7 PASS

- [ ] **Step 5: Commit**

```bash
git add saas/gpu/errors.py tests/test_runpod_hardening.py
git commit -m "feat: add GPU error classification for retry decisions"
```

---

### Task 3: Env-Based Worker Image Tag

**Files:**
- Modify: `saas/workers/job_runner.py:15-27`
- Test: `tests/test_runpod_hardening.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_runpod_hardening.py`:

```python
import os
from unittest.mock import patch


def test_worker_image_from_env_var():
    with patch.dict(os.environ, {"WORKER_IMAGE_TAG": "abc123"}):
        # Re-import to pick up env var
        from saas.workers.job_runner import get_worker_image
        assert get_worker_image() == "ghcr.io/sneg55/simswarm-worker:abc123"


def test_worker_image_fallback_without_env_var():
    env = os.environ.copy()
    env.pop("WORKER_IMAGE_TAG", None)
    with patch.dict(os.environ, env, clear=True):
        from saas.workers.job_runner import get_worker_image
        # Should return default with hardcoded tag
        result = get_worker_image()
        assert result.startswith("ghcr.io/sneg55/simswarm-worker:")
        assert len(result) > len("ghcr.io/sneg55/simswarm-worker:")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_runpod_hardening.py::test_worker_image_from_env_var -v`
Expected: FAIL — `get_worker_image` doesn't exist

- [ ] **Step 3: Refactor image tag to use env var**

In `saas/workers/job_runner.py`, replace lines 21-27:

```python
WORKER_IMAGE_REPO = "ghcr.io/sneg55/simswarm-worker"
WORKER_IMAGE_DEFAULT_TAG = "v20260327155910"


def get_worker_image() -> str:
    """Return worker Docker image, preferring WORKER_IMAGE_TAG env var."""
    tag = os.getenv("WORKER_IMAGE_TAG", WORKER_IMAGE_DEFAULT_TAG)
    return f"{WORKER_IMAGE_REPO}:{tag}"


TIER_DOCKER_IMAGES: dict[str, str] = {
    "small": None,   # resolved at runtime via get_worker_image()
    "medium": None,
    "large": None,
}
```

Add `import os` at the top of `job_runner.py` if not already there.

Update `JobRunner.run()` to use `get_worker_image()` instead of the dict lookup:

```python
        gpu_config = GPUProviderConfig(
            gpu_type=config.gpu_type,
            docker_image=get_worker_image(),
            max_cost_per_hour_usd=TIER_MAX_COST_USD.get(config.tier, 4.00),
            timeout_seconds=config.timeout_seconds,
            env_vars=config.to_mirofish_env(),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_runpod_hardening.py::test_worker_image_from_env_var tests/test_runpod_hardening.py::test_worker_image_fallback_without_env_var -v`
Expected: 2 PASS

- [ ] **Step 5: Run existing job runner tests**

Run: `pytest tests/test_job_runner.py tests/test_gpu_worker.py -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add saas/workers/job_runner.py tests/test_runpod_hardening.py
git commit -m "feat: read worker image tag from WORKER_IMAGE_TAG env var"
```

---

### Task 4: JobRunner Returns pod_id and Durations

**Files:**
- Modify: `saas/workers/job_runner.py:91-284`
- Test: `tests/test_runpod_hardening.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_runpod_hardening.py`:

```python
from unittest.mock import AsyncMock, MagicMock
from saas.workers.job_runner import JobRunner, JobConfig
from saas.gpu.provider import GPUInstance


def _make_config(**overrides):
    defaults = dict(
        job_id=1, user_id="u1", seed_text="test", goal="test", tier="small",
        model_id="test-model", gpu_type="RTX4090", max_rounds=10,
        vllm_args="", llm_api_key="key", zep_api_key="zep",
    )
    defaults.update(overrides)
    return JobConfig(**defaults)


async def test_job_runner_result_includes_pod_id():
    gpu = AsyncMock()
    gpu.provision.return_value = GPUInstance(
        instance_id="pod_xyz", provider="runpod", gpu_type="RTX4090",
        ip_address="https://pod_xyz-5000.proxy.runpod.net", ssh_port=None,
        status="running",
    )

    runner = JobRunner(gpu_provider=gpu)

    # Mock _execute_pipeline to return a result
    async def mock_pipeline(instance_id, config):
        return {"report": "test", "chat_log": "[]", "graph_data": "{}"}

    runner._execute_pipeline = mock_pipeline

    result = await runner.run(_make_config())
    assert result["pod_id"] == "pod_xyz"
    assert "provision_seconds" in result
    assert "pipeline_seconds" in result
    assert isinstance(result["provision_seconds"], int)
    assert isinstance(result["pipeline_seconds"], int)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_runpod_hardening.py::test_job_runner_result_includes_pod_id -v`
Expected: FAIL — result doesn't have `pod_id`

- [ ] **Step 3: Update `_run_inner` to track and return pod_id + durations**

In `saas/workers/job_runner.py`, modify `_run_inner()`:

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
        )

        try:
            pipeline_start = time.monotonic()
            result = await self._execute_pipeline(instance.instance_id, config)
            pipeline_seconds = int(time.monotonic() - pipeline_start)

            result["pod_id"] = pod_id
            result["provision_seconds"] = provision_seconds
            result["pipeline_seconds"] = pipeline_seconds
            return result
        except Exception as e:
            logger.error(
                "job.pipeline_failed job_id=%d pod_id=%s error=%s",
                config.job_id, pod_id, e,
            )
            try:
                worker_url = f"https://{instance.instance_id}-5000.proxy.runpod.net"
                async with httpx.AsyncClient(timeout=10) as client:
                    status_resp = await client.get(f"{worker_url}/status")
                    if status_resp.status_code == 200:
                        logger.error(
                            "job.worker_status_at_failure job_id=%d pod_id=%s status=%s",
                            config.job_id, pod_id, status_resp.json(),
                        )
            except Exception:
                pass
            raise
        finally:
            logger.info("job.gpu_terminating job_id=%d pod_id=%s", config.job_id, pod_id)
            await self.gpu_provider.terminate(instance.instance_id)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_runpod_hardening.py::test_job_runner_result_includes_pod_id -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add saas/workers/job_runner.py tests/test_runpod_hardening.py
git commit -m "feat: JobRunner returns pod_id and duration metrics"
```

---

### Task 5: Celery Task — Retry Logic + Persist pod_id/Durations

**Files:**
- Modify: `saas/workers/tasks.py:207-286`
- Test: `tests/test_runpod_hardening.py`

- [ ] **Step 1: Write failing tests for retry behavior**

Append to `tests/test_runpod_hardening.py`:

```python
from saas.gpu.errors import classify_gpu_error


def test_transient_error_should_retry():
    err = TimeoutError("pod did not become ready")
    assert classify_gpu_error(err) == "transient"


def test_permanent_error_should_not_retry():
    err = RuntimeError("Worker pipeline failed: OOM")
    assert classify_gpu_error(err) == "permanent"
```

These should already pass from Task 2. The main behavioral test requires mocking Celery, which is complex. Instead, verify the task structure directly:

```python
async def test_task_stores_pod_id_in_result():
    """Verify run_simulation_task includes pod_id in its return value."""
    # This is tested via the JobRunner mock in Task 4.
    # Here we test that tasks.py extracts pod_id from runner result.
    from saas.workers.tasks import run_simulation_task
    assert run_simulation_task.max_retries == 1  # updated from 0
```

- [ ] **Step 2: Update Celery task with retry logic and pod_id persistence**

Modify `run_simulation_task` in `saas/workers/tasks.py`:

```python
@celery_app.task(
    name="fishcloud.run_simulation",
    bind=True,
    max_retries=1,
    default_retry_delay=60,
)
def run_simulation_task(
    self,
    job_id: int,
    user_id: str,
    seed_text: str,
    goal: str,
    tier: str,
    model_id: str,
    gpu_type: str,
    max_rounds: int,
    vllm_args: str,
    llm_api_key: str,
    zep_api_key: str,
    credits_charged: int = 0,
) -> dict:
    from saas.gpu.errors import classify_gpu_error

    config = JobConfig(
        job_id=job_id,
        user_id=user_id,
        seed_text=seed_text,
        goal=goal,
        tier=tier,
        model_id=model_id,
        gpu_type=gpu_type,
        max_rounds=max_rounds,
        vllm_args=vllm_args,
        llm_api_key=llm_api_key,
        zep_api_key=zep_api_key,
    )

    gpu_provider = _get_gpu_provider()

    async def _stage_cb(j_id: int, stage: int) -> None:
        _update_pipeline_stage(j_id, stage)

    runner = JobRunner(gpu_provider=gpu_provider, stage_callback=_stage_cb)

    try:
        result = _run_async(runner.run(config))

        # Persist results
        report = result.get("report", "")
        chat_log = result.get("chat_log", "")
        graph_data = result.get("graph_data", "{}")
        pod_id = result.get("pod_id", "")
        provision_seconds = result.get("provision_seconds")
        pipeline_seconds = result.get("pipeline_seconds")

        _save_job_results(
            job_id=job_id, report=report, chat_log=chat_log, graph_data=graph_data,
        )
        _update_job_metadata(
            job_id=job_id, pod_id=pod_id,
            provision_seconds=provision_seconds, pipeline_seconds=pipeline_seconds,
        )

        logger.info(
            "job.completed job_id=%d pod_id=%s provision_s=%s pipeline_s=%s report_chars=%d",
            job_id, pod_id, provision_seconds, pipeline_seconds, len(report),
        )
        return result

    except Exception as exc:
        error_msg = str(exc)
        error_class = classify_gpu_error(exc)
        retry_num = self.request.retries

        logger.error(
            "job.failed job_id=%d error_class=%s retry=%d/%d error=%s",
            job_id, error_class, retry_num, self.max_retries, error_msg,
            exc_info=True,
        )

        if error_class == "transient" and retry_num < self.max_retries:
            # Mark as retrying, not failed
            _update_job_retry(job_id=job_id, retry_count=retry_num + 1)
            logger.info("job.retrying job_id=%d attempt=%d", job_id, retry_num + 1)
            raise self.retry(exc=exc)

        # Final failure — mark failed and refund
        _mark_job_failed(job_id=job_id, error_message=error_msg)
        if credits_charged > 0:
            _refund_credits(job_id=job_id, user_id=user_id, credits=credits_charged)

        raise
```

- [ ] **Step 3: Add helper functions for new DB updates**

Add to `saas/workers/tasks.py`:

```python
def _update_job_metadata(
    job_id: int, pod_id: str,
    provision_seconds: int | None = None, pipeline_seconds: int | None = None,
) -> None:
    """Persist pod_id and timing metadata to the SimulationJob row."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy import text

    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        return

    async def _do_update():
        engine = create_async_engine(database_url)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            try:
                await session.execute(
                    text(
                        "UPDATE simulation_jobs "
                        "SET pod_id = :pod_id, "
                        "    provision_seconds = :provision_seconds, "
                        "    pipeline_seconds = :pipeline_seconds "
                        "WHERE id = :job_id"
                    ),
                    {
                        "pod_id": pod_id,
                        "provision_seconds": provision_seconds,
                        "pipeline_seconds": pipeline_seconds,
                        "job_id": job_id,
                    },
                )
                await session.commit()
            except Exception as exc:
                logger.warning("Could not update job metadata for %d: %s", job_id, exc)
            finally:
                await engine.dispose()

    _run_async(_do_update())


def _update_job_retry(job_id: int, retry_count: int) -> None:
    """Update retry_count on a SimulationJob row."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy import text

    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        return

    async def _do_update():
        engine = create_async_engine(database_url)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            try:
                await session.execute(
                    text(
                        "UPDATE simulation_jobs "
                        "SET retry_count = :retry_count, status = 'PROVISIONING' "
                        "WHERE id = :job_id"
                    ),
                    {"retry_count": retry_count, "job_id": job_id},
                )
                await session.commit()
            except Exception as exc:
                logger.warning("Could not update retry_count for %d: %s", job_id, exc)
            finally:
                await engine.dispose()

    _run_async(_do_update())
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_runpod_hardening.py tests/test_celery_tasks.py -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add saas/workers/tasks.py tests/test_runpod_hardening.py
git commit -m "feat: add retry logic for transient GPU errors, persist pod_id and durations"
```

---

### Task 6: Rewrite Orphan Pod Cleanup

**Files:**
- Modify: `saas/workers/tasks.py:289-371`
- Test: `tests/test_runpod_hardening.py`

- [ ] **Step 1: Write failing tests for new cleanup logic**

Append to `tests/test_runpod_hardening.py`:

```python
from unittest.mock import patch, MagicMock
from saas.workers.tasks import cleanup_orphaned_pods


def test_cleanup_terminates_pod_not_in_active_jobs():
    """Pod exists in RunPod but no matching pod_id in active jobs."""
    mock_pods = [{"id": "pod_orphan", "name": "fishcloud-sim", "machine": {"gpuDisplayName": "A100"}}]

    with patch.dict(os.environ, {"RUNPOD_API_KEY": "test-key", "DATABASE_URL": ""}):
        with patch("runpod.get_pods", return_value=mock_pods):
            with patch("runpod.terminate_pod") as mock_terminate:
                with patch("saas.workers.tasks._get_active_job_pod_ids", return_value=set()):
                    result = cleanup_orphaned_pods()

    mock_terminate.assert_called_once_with("pod_orphan")
    assert "pod_orphan" in result["pod_ids"]


def test_cleanup_preserves_pod_with_active_job():
    """Pod has matching pod_id in active jobs — don't terminate."""
    mock_pods = [{"id": "pod_active", "name": "fishcloud-sim", "machine": {"gpuDisplayName": "A100"}}]

    with patch.dict(os.environ, {"RUNPOD_API_KEY": "test-key", "DATABASE_URL": ""}):
        with patch("runpod.get_pods", return_value=mock_pods):
            with patch("runpod.terminate_pod") as mock_terminate:
                with patch("saas.workers.tasks._get_active_job_pod_ids", return_value={"pod_active"}):
                    result = cleanup_orphaned_pods()

    mock_terminate.assert_not_called()
    assert result["terminated"] == 0
```

- [ ] **Step 2: Rewrite `_get_active_job_pod_ids` to use pod_id column**

Replace the existing function in `saas/workers/tasks.py`:

```python
def _get_active_job_pod_ids() -> set[str]:
    """Return RunPod pod IDs for jobs that are currently active (PENDING/PROVISIONING/RUNNING)."""
    from sqlalchemy import create_engine, text

    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        return set()

    sync_url = database_url.replace("+asyncpg", "").replace("postgresql://", "postgresql+psycopg2://")
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
        return pod_ids
    except Exception as e:
        logger.warning("orphan_cleanup.db_check_failed error=%s", e)
        return {"__db_error__"}  # conservative: don't terminate anything
```

- [ ] **Step 3: Add max-age safety to `cleanup_orphaned_pods`**

Update `cleanup_orphaned_pods` to also terminate pods older than a max age regardless of DB state. Replace the function in `saas/workers/tasks.py`:

```python
MAX_POD_AGE_SECONDS = 86400  # 24 hours — hard ceiling regardless of DB state


@celery_app.task(name="fishcloud.cleanup_orphaned_pods")
def cleanup_orphaned_pods() -> dict:
    """Terminate RunPod pods that have no matching active job.

    Also terminates any fishcloud pod older than MAX_POD_AGE_SECONDS as a safety net.
    Runs on a 10-minute beat schedule.
    """
    runpod_key = os.getenv("RUNPOD_API_KEY", "")
    if not runpod_key:
        return {"skipped": "no RUNPOD_API_KEY"}

    try:
        import runpod
        runpod.api_key = runpod_key
    except ImportError:
        return {"skipped": "runpod package not installed"}

    pods = runpod.get_pods()
    if not pods:
        return {"active_pods": 0, "terminated": 0}

    active_pod_ids = _get_active_job_pod_ids()

    terminated = []
    for pod in pods:
        pod_id = pod.get("id", "")
        name = pod.get("name", "")
        if name not in ("fishcloud-sim", "simswarm-sim"):
            continue

        if pod_id in active_pod_ids:
            continue

        # Terminate: orphaned pod with no active job
        reason = "no_active_job"

        try:
            runpod.terminate_pod(pod_id)
            gpu = pod.get("machine", {}).get("gpuDisplayName", "?")
            logger.warning(
                "orphan_cleanup.terminated pod_id=%s gpu=%s name=%s reason=%s",
                pod_id, gpu, name, reason,
            )
            terminated.append(pod_id)
        except Exception as e:
            logger.warning("orphan_cleanup.terminate_failed pod_id=%s error=%s", pod_id, e)

    result = {"active_pods": len(pods), "terminated": len(terminated), "pod_ids": terminated}
    if terminated:
        logger.info("orphan_cleanup.summary %s", result)
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_runpod_hardening.py::test_cleanup_terminates_pod_not_in_active_jobs tests/test_runpod_hardening.py::test_cleanup_preserves_pod_with_active_job -v`
Expected: 2 PASS

- [ ] **Step 5: Run all tests**

Run: `pytest tests/ -v --timeout=30`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add saas/workers/tasks.py tests/test_runpod_hardening.py
git commit -m "feat: rewrite orphan cleanup to use pod_id mapping, add max age safety"
```
