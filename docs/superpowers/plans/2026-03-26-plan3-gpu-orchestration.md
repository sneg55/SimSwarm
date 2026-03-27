# Plan 3: GPU Orchestration & Job Queue

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Celery job queue, GPU provider abstraction (RunPod-only for MVP), job lifecycle management with progress tracking, and automatic refund on failure.

**Architecture:** Celery workers pick up jobs from Redis, provision ephemeral GPU instances via RunPod SDK, launch MiroFish pipeline, monitor progress via file-system IPC, extract results on completion, and tear down GPU resources. Operator model routing table controls which model/GPU combo is used per tier.

**Tech Stack:** Celery, Redis, RunPod SDK, Docker, pytest, pytest-celery

> **Note (2026-03-27):** Vast.ai fallback removed from MVP scope. Vast.ai was never tested successfully (API format issues, no working sim), Network Volume is RunPod-specific, and maintaining two providers doubles debugging surface. The abstract `GPUProvider` interface is kept so Vast.ai can be re-added later if RunPod capacity becomes an issue.

**Depends on:** Plan 1 (adapter, models), Plan 2 (credit ledger for refunds)

**Spec reference:** `docs/superpowers/specs/2026-03-26-mirofish-hosted-mvp-design.md` — Appendix B

---

## File Structure

```
saas/
├── workers/
│   ├── __init__.py
│   ├── celery_app.py          # Celery app configuration
│   ├── tasks.py               # Celery task definitions
│   └── job_runner.py          # Job lifecycle orchestration
├── gpu/
│   ├── __init__.py
│   ├── provider.py            # Abstract GPU provider interface
│   └── runpod_provider.py     # RunPod implementation (Vast.ai + failover removed for MVP)
├── api/
│   └── jobs.py                # Modified: dispatch to Celery on create
tests/
├── test_gpu_provider.py       # GPU provider unit tests
├── test_job_runner.py         # Job lifecycle tests
├── test_celery_tasks.py       # Celery task tests (mocked)
├── test_model_routing.py      # Routing table query tests
```

---

### Task 1: GPU Provider Abstraction

**Files:**
- Create: `saas/gpu/__init__.py`
- Create: `saas/gpu/provider.py`
- Create: `tests/test_gpu_provider.py`

- [ ] **Step 1: Write provider interface tests**

```python
# tests/test_gpu_provider.py
import pytest
from saas.gpu.provider import GPUInstance, GPUProviderConfig


def test_gpu_instance_creation():
    instance = GPUInstance(
        instance_id="pod-abc123",
        provider="runpod",
        gpu_type="a100-40gb",
        ip_address="203.0.113.10",
        ssh_port=22,
        status="running",
    )
    assert instance.instance_id == "pod-abc123"
    assert instance.provider == "runpod"
    assert instance.is_ready


def test_gpu_instance_not_ready_when_provisioning():
    instance = GPUInstance(
        instance_id="pod-abc123",
        provider="runpod",
        gpu_type="a100-40gb",
        ip_address=None,
        ssh_port=None,
        status="provisioning",
    )
    assert not instance.is_ready


def test_provider_config():
    config = GPUProviderConfig(
        gpu_type="h100-80gb",
        docker_image="fishcloud/worker:latest",
        max_cost_per_hour_usd=3.50,
        timeout_seconds=2700,  # 45 min
    )
    assert config.gpu_type == "h100-80gb"
    assert config.timeout_seconds == 2700
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_gpu_provider.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement provider abstraction**

```python
# saas/gpu/__init__.py
```

```python
# saas/gpu/provider.py
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class GPUProviderConfig:
    gpu_type: str
    docker_image: str
    max_cost_per_hour_usd: float
    timeout_seconds: int
    env_vars: dict[str, str] | None = None


@dataclass
class GPUInstance:
    instance_id: str
    provider: str
    gpu_type: str
    ip_address: str | None
    ssh_port: int | None
    status: str  # provisioning, running, stopped, error

    @property
    def is_ready(self) -> bool:
        return self.status == "running" and self.ip_address is not None


class GPUProvider(ABC):
    """Abstract interface for GPU cloud providers."""

    @abstractmethod
    async def provision(self, config: GPUProviderConfig) -> GPUInstance:
        """Spin up a GPU instance. Returns when instance is ready."""
        ...

    @abstractmethod
    async def get_status(self, instance_id: str) -> GPUInstance:
        """Get current status of an instance."""
        ...

    @abstractmethod
    async def terminate(self, instance_id: str) -> None:
        """Tear down a GPU instance."""
        ...

    @abstractmethod
    async def execute_command(self, instance_id: str, command: str) -> str:
        """Run a shell command on the GPU instance. Returns stdout."""
        ...
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_gpu_provider.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add saas/gpu/ tests/test_gpu_provider.py
git commit -m "feat: add GPU provider abstraction with instance model"
```

---

### Task 2: RunPod Implementation

**Files:**
- Create: `saas/gpu/runpod_provider.py`

- [ ] **Step 1: Implement RunPod provider**

```python
# saas/gpu/runpod_provider.py
"""RunPod GPU provider implementation.

Uses RunPod's Python SDK to provision spot GPU instances.
Requires RUNPOD_API_KEY env var.
"""
from __future__ import annotations

import asyncio
import runpod

from saas.gpu.provider import GPUProvider, GPUProviderConfig, GPUInstance

# RunPod GPU type mapping
GPU_TYPE_MAP = {
    "a100-40gb": "NVIDIA A100 40GB",
    "a100-80gb": "NVIDIA A100 80GB",
    "h100-80gb": "NVIDIA H100 80GB HBM3",
}

MAX_POLL_ATTEMPTS = 60  # 60 * 5s = 5 min max wait for provisioning


class RunPodProvider(GPUProvider):
    def __init__(self, api_key: str):
        runpod.api_key = api_key

    async def provision(self, config: GPUProviderConfig) -> GPUInstance:
        gpu_name = GPU_TYPE_MAP.get(config.gpu_type, config.gpu_type)

        pod = runpod.create_pod(
            name="fishcloud-worker",
            image_name=config.docker_image,
            gpu_type_id=gpu_name,
            cloud_type="SPOT",
            gpu_count=1,
            volume_in_gb=50,
            container_disk_in_gb=50,
            env=config.env_vars or {},
            docker_args=f"--timeout {config.timeout_seconds}",
        )

        pod_id = pod["id"]

        # Poll until ready
        for _ in range(MAX_POLL_ATTEMPTS):
            status = runpod.get_pod(pod_id)
            if status.get("desiredStatus") == "RUNNING" and status.get("runtime"):
                runtime = status["runtime"]
                return GPUInstance(
                    instance_id=pod_id,
                    provider="runpod",
                    gpu_type=config.gpu_type,
                    ip_address=runtime.get("ip"),
                    ssh_port=runtime.get("ports", [{}])[0].get("publicPort"),
                    status="running",
                )
            await asyncio.sleep(5)

        raise TimeoutError(f"RunPod instance {pod_id} did not become ready in time")

    async def get_status(self, instance_id: str) -> GPUInstance:
        pod = runpod.get_pod(instance_id)
        runtime = pod.get("runtime", {})
        status = "running" if pod.get("desiredStatus") == "RUNNING" and runtime else "provisioning"
        return GPUInstance(
            instance_id=instance_id,
            provider="runpod",
            gpu_type=pod.get("gpuType", "unknown"),
            ip_address=runtime.get("ip") if runtime else None,
            ssh_port=runtime.get("ports", [{}])[0].get("publicPort") if runtime else None,
            status=status,
        )

    async def terminate(self, instance_id: str) -> None:
        runpod.terminate_pod(instance_id)

    async def execute_command(self, instance_id: str, command: str) -> str:
        result = runpod.run_pod_command(instance_id, command)
        return result.get("output", "")
```

- [ ] **Step 2: Commit**

```bash
git add saas/gpu/runpod_provider.py
git commit -m "feat: add RunPod GPU provider implementation"
```

---

### Task 3: Model Routing Table Service

**Files:**
- Create: `tests/test_model_routing.py`

- [ ] **Step 1: Write routing table tests**

```python
# tests/test_model_routing.py
import pytest
from sqlalchemy import select
from saas.models.model_routing import ModelRouting
from saas.gpu.provider import GPUProviderConfig


async def test_seed_default_routing(db_session):
    """Seed the 3 default tier configs."""
    defaults = [
        ModelRouting(
            sim_tier="small",
            model_id="Qwen2.5-32B-Instruct-AWQ",
            gpu_type="a100-40gb",
            max_rounds=200,
            vllm_args="--quantization awq --max-model-len 32768",
        ),
        ModelRouting(
            sim_tier="medium",
            model_id="Qwen2.5-32B-Instruct-AWQ",
            gpu_type="h100-80gb",
            max_rounds=200,
            vllm_args="--quantization awq --max-model-len 32768",
        ),
        ModelRouting(
            sim_tier="large",
            model_id="Qwen2.5-32B-Instruct-AWQ",
            gpu_type="h100-80gb",
            max_rounds=200,
            vllm_args="--quantization awq --max-model-len 32768",
        ),
    ]
    db_session.add_all(defaults)
    await db_session.commit()

    result = await db_session.execute(select(ModelRouting))
    routes = result.scalars().all()
    assert len(routes) == 3


async def test_get_routing_for_tier(db_session):
    route = ModelRouting(
        sim_tier="small",
        model_id="Qwen2.5-32B-Instruct-AWQ",
        gpu_type="a100-40gb",
        max_rounds=200,
    )
    db_session.add(route)
    await db_session.commit()

    result = await db_session.execute(
        select(ModelRouting).where(ModelRouting.sim_tier == "small")
    )
    fetched = result.scalar_one()
    assert fetched.model_id == "Qwen2.5-32B-Instruct-AWQ"
    assert fetched.gpu_type == "a100-40gb"


async def test_routing_to_gpu_config(db_session):
    route = ModelRouting(
        sim_tier="medium",
        model_id="Qwen2.5-32B-Instruct-AWQ",
        gpu_type="h100-80gb",
        max_rounds=200,
        vllm_args="--quantization awq",
    )
    db_session.add(route)
    await db_session.commit()

    # Convert to GPUProviderConfig
    config = GPUProviderConfig(
        gpu_type=route.gpu_type,
        docker_image="fishcloud/worker:latest",
        max_cost_per_hour_usd=3.50,
        timeout_seconds=5 * 3600,  # 5 hrs for medium
    )
    assert config.gpu_type == "h100-80gb"
```

- [ ] **Step 2: Run tests to verify they pass**

```bash
pytest tests/test_model_routing.py -v
```

Expected: 3 passed (models already exist from Plan 1).

- [ ] **Step 3: Commit**

```bash
git add tests/test_model_routing.py
git commit -m "test: add model routing table query tests"
```

---

### Task 4: Job Runner (Lifecycle Orchestration)

**Files:**
- Create: `saas/workers/__init__.py`
- Create: `saas/workers/job_runner.py`
- Create: `tests/test_job_runner.py`

- [ ] **Step 1: Write job runner tests**

```python
# tests/test_job_runner.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from saas.workers.job_runner import JobRunner, JobConfig
from saas.gpu.provider import GPUInstance


@pytest.fixture
def job_config():
    return JobConfig(
        job_id=1,
        user_id="user-123",
        seed_text="Breaking news about AI regulation",
        goal="Predict industry response over 14 days",
        tier="small",
        model_id="Qwen2.5-32B-Instruct-AWQ",
        gpu_type="a100-40gb",
        max_rounds=200,
        vllm_args="--quantization awq",
        llm_api_key="test-key",
        zep_api_key="test-zep",
    )


@pytest.fixture
def gpu_instance():
    return GPUInstance(
        instance_id="pod-123",
        provider="runpod",
        gpu_type="a100-40gb",
        ip_address="10.0.0.1",
        ssh_port=22,
        status="running",
    )


def test_job_config_timeout_by_tier():
    small = JobConfig(
        job_id=1, user_id="u", seed_text="s", goal="g", tier="small",
        model_id="m", gpu_type="g", max_rounds=200, vllm_args="",
        llm_api_key="k", zep_api_key="z",
    )
    assert small.timeout_seconds == 2700  # 45 min

    medium = JobConfig(
        job_id=2, user_id="u", seed_text="s", goal="g", tier="medium",
        model_id="m", gpu_type="g", max_rounds=200, vllm_args="",
        llm_api_key="k", zep_api_key="z",
    )
    assert medium.timeout_seconds == 18000  # 5 hrs

    large = JobConfig(
        job_id=3, user_id="u", seed_text="s", goal="g", tier="large",
        model_id="m", gpu_type="g", max_rounds=200, vllm_args="",
        llm_api_key="k", zep_api_key="z",
    )
    assert large.timeout_seconds == 43200  # 12 hrs


def test_job_config_to_env_vars(job_config):
    env = job_config.to_mirofish_env()
    assert env["LLM_API_KEY"] == "test-key"
    assert env["LLM_BASE_URL"] == "http://localhost:8000/v1"
    assert env["LLM_MODEL_NAME"] == "Qwen2.5-32B-Instruct-AWQ"
    assert env["ZEP_API_KEY"] == "test-zep"
    assert env["OASIS_DEFAULT_MAX_ROUNDS"] == "200"


async def test_runner_provisions_gpu(job_config, gpu_instance):
    mock_gpu = AsyncMock()
    mock_gpu.provision = AsyncMock(return_value=gpu_instance)
    mock_gpu.terminate = AsyncMock()
    mock_gpu.execute_command = AsyncMock(return_value="")

    runner = JobRunner(gpu_provider=mock_gpu)

    # Mock the internal pipeline execution
    with patch.object(runner, "_execute_pipeline", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = {"report": "# Results", "chat_log": []}
        await runner.run(job_config)

    mock_gpu.provision.assert_awaited_once()
    mock_gpu.terminate.assert_awaited_once_with("pod-123")


async def test_runner_terminates_gpu_on_failure(job_config, gpu_instance):
    mock_gpu = AsyncMock()
    mock_gpu.provision = AsyncMock(return_value=gpu_instance)
    mock_gpu.terminate = AsyncMock()

    runner = JobRunner(gpu_provider=mock_gpu)

    with patch.object(runner, "_execute_pipeline", new_callable=AsyncMock) as mock_exec:
        mock_exec.side_effect = RuntimeError("Pipeline crashed")
        with pytest.raises(RuntimeError):
            await runner.run(job_config)

    # GPU must be terminated even on failure
    mock_gpu.terminate.assert_awaited_once_with("pod-123")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_job_runner.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement job runner**

```python
# saas/workers/__init__.py
```

```python
# saas/workers/job_runner.py
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from saas.gpu.provider import GPUProvider, GPUProviderConfig

logger = logging.getLogger(__name__)

TIER_TIMEOUTS = {
    "small": 2700,    # 45 min
    "medium": 18000,  # 5 hrs
    "large": 43200,   # 12 hrs
}


@dataclass
class JobConfig:
    job_id: int
    user_id: str
    seed_text: str
    goal: str
    tier: str
    model_id: str
    gpu_type: str
    max_rounds: int
    vllm_args: str
    llm_api_key: str
    zep_api_key: str

    @property
    def timeout_seconds(self) -> int:
        return TIER_TIMEOUTS[self.tier]

    def to_mirofish_env(self) -> dict[str, str]:
        return {
            "LLM_API_KEY": self.llm_api_key,
            "LLM_BASE_URL": "http://localhost:8000/v1",  # vLLM runs locally on GPU
            "LLM_MODEL_NAME": self.model_id,
            "ZEP_API_KEY": self.zep_api_key,
            "OASIS_DEFAULT_MAX_ROUNDS": str(self.max_rounds),
        }


class JobRunner:
    """Orchestrates the full lifecycle of a simulation job."""

    def __init__(self, gpu_provider: GPUProvider):
        self.gpu_provider = gpu_provider

    async def run(self, config: JobConfig) -> dict[str, Any]:
        gpu_config = GPUProviderConfig(
            gpu_type=config.gpu_type,
            docker_image="fishcloud/worker:latest",
            max_cost_per_hour_usd=5.0,
            timeout_seconds=config.timeout_seconds,
            env_vars=config.to_mirofish_env(),
        )

        instance = await self.gpu_provider.provision(gpu_config)
        logger.info(f"Job {config.job_id}: GPU provisioned ({instance.instance_id})")

        try:
            result = await self._execute_pipeline(instance.instance_id, config)
            logger.info(f"Job {config.job_id}: Pipeline completed")
            return result
        finally:
            await self.gpu_provider.terminate(instance.instance_id)
            logger.info(f"Job {config.job_id}: GPU terminated ({instance.instance_id})")

    async def _execute_pipeline(
        self, instance_id: str, config: JobConfig
    ) -> dict[str, Any]:
        """Execute the MiroFish 5-step pipeline on the GPU instance."""
        # Step 1: Upload seed
        await self.gpu_provider.execute_command(
            instance_id,
            f"echo '{config.seed_text[:1000]}' > /app/seed.txt",
        )

        # Step 2-5: Run the MiroFish pipeline
        # The Docker image has a runner script that executes all steps
        output = await self.gpu_provider.execute_command(
            instance_id,
            f"python /app/run_simulation.py --seed /app/seed.txt "
            f"--goal '{config.goal}' --max-rounds {config.max_rounds}",
        )

        # Step 6: Extract results
        report = await self.gpu_provider.execute_command(
            instance_id, "cat /app/results/report.md"
        )
        chat_log = await self.gpu_provider.execute_command(
            instance_id, "cat /app/results/chat_log.json"
        )

        return {"report": report, "chat_log": chat_log}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_job_runner.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add saas/workers/ tests/test_job_runner.py
git commit -m "feat: add job runner with GPU lifecycle and timeout management"
```

---

### Task 5: Celery Task Definitions

**Files:**
- Create: `saas/workers/celery_app.py`
- Create: `saas/workers/tasks.py`
- Create: `tests/test_celery_tasks.py`

- [ ] **Step 1: Write Celery task tests**

```python
# tests/test_celery_tasks.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from saas.workers.tasks import run_simulation_task


def test_task_is_registered():
    """Verify the Celery task is registered."""
    assert run_simulation_task.name == "saas.workers.tasks.run_simulation_task"


@patch("saas.workers.tasks._run_simulation")
def test_task_calls_runner(mock_run):
    """Task dispatches to the async runner with correct args."""
    mock_run.return_value = {"report": "# Test", "chat_log": "[]"}

    result = run_simulation_task(
        job_id=1,
        user_id="user-1",
        seed_text="test seed",
        goal="test goal",
        tier="small",
    )

    mock_run.assert_called_once()
    call_args = mock_run.call_args[0]
    assert call_args[0] == 1  # job_id
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_celery_tasks.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement Celery app and tasks**

Add `celery[redis]>=5.4.0` to `pyproject.toml` dependencies.

```python
# saas/workers/celery_app.py
import os
from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery("fishcloud", broker=REDIS_URL, backend=REDIS_URL)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,  # One job at a time per worker
)
```

```python
# saas/workers/tasks.py
import asyncio
import logging
import os

from saas.workers.celery_app import celery_app
from saas.workers.job_runner import JobConfig

logger = logging.getLogger(__name__)


def _run_simulation(
    job_id: int,
    user_id: str,
    seed_text: str,
    goal: str,
    tier: str,
) -> dict:
    """Synchronous wrapper for the async job runner.

    Celery tasks are sync by default — this bridges to the async runner.
    In production, this reads model routing from the DB and initializes
    GPU providers from env vars.
    """
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session
    from saas.models.model_routing import ModelRouting
    from saas.models.job import SimulationJob, JobStatus
    from saas.billing.ledger import CreditLedger

    database_url = os.getenv("DATABASE_URL", "").replace("+asyncpg", "+psycopg2")
    engine = create_engine(database_url)

    with Session(engine) as session:
        # Get model routing for this tier
        route = session.execute(
            select(ModelRouting).where(ModelRouting.sim_tier == tier)
        ).scalar_one()

        # Update job status
        job = session.get(SimulationJob, job_id)
        job.status = JobStatus.RUNNING
        session.commit()

        config = JobConfig(
            job_id=job_id,
            user_id=user_id,
            seed_text=seed_text,
            goal=goal,
            tier=tier,
            model_id=route.model_id,
            gpu_type=route.gpu_type,
            max_rounds=route.max_rounds,
            vllm_args=route.vllm_args or "",
            llm_api_key=os.getenv("LLM_API_KEY", ""),
            zep_api_key=os.getenv("ZEP_API_KEY", ""),
        )

        try:
            # Run the async job runner (RunPod only for MVP)
            from saas.gpu.runpod_provider import RunPodProvider
            from saas.workers.job_runner import JobRunner

            gpu = RunPodProvider(api_key=os.getenv("RUNPOD_API_KEY", ""))
            runner = JobRunner(gpu_provider=gpu)

            result = asyncio.run(runner.run(config))

            # Save results
            job.status = JobStatus.COMPLETED
            job.result_report = result.get("report", "")
            job.result_chat_log = result.get("chat_log", "")
            session.commit()

            return result

        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}")
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            session.commit()

            # Refund credits
            # Note: using sync session here — in production, wrap properly
            from saas.models.credit_entry import CreditEntry
            refund = CreditEntry(
                user_id=user_id,
                amount=job.credits_charged,
                description=f"Refund: job {job_id} failed",
                job_id=job_id,
            )
            session.add(refund)
            session.commit()

            raise


@celery_app.task(name="saas.workers.tasks.run_simulation_task", bind=True)
def run_simulation_task(
    self,
    job_id: int,
    user_id: str,
    seed_text: str,
    goal: str,
    tier: str,
) -> dict:
    return _run_simulation(job_id, user_id, seed_text, goal, tier)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_celery_tasks.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Run full test suite**

```bash
pytest -v
```

Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add saas/workers/ tests/test_celery_tasks.py pyproject.toml
git commit -m "feat: add Celery task definitions with GPU provisioning and auto-refund"
```

---

## Test Suite Summary (After Plan 3)

| File | Tests | What it covers |
|------|-------|----------------|
| `test_gpu_provider.py` | 3 | Instance model, readiness, config |
| `test_model_routing.py` | 3 | Seed defaults, tier lookup, config conversion |
| `test_job_runner.py` | 5 | Timeout by tier, env vars, GPU provision, terminate on failure |
| `test_celery_tasks.py` | 2 | Task registration, dispatch |
| *(Plan 1+2 tests)* | 49 | |
| **Total** | **62** | |

> **Note:** Failover tests (4) removed — Vast.ai fallback dropped from MVP scope.
