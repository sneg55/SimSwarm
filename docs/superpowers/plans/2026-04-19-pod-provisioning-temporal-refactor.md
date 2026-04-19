# Pod Provisioning Temporal Refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Celery + `recover_stale_jobs` + `cleanup_orphaned_pods` three-actor orchestration with a single Temporal workflow owning the sim lifecycle. Delete all heuristic-driven liveness inference code.

**Architecture:** Add self-hosted `temporal-server` + dedicated `temporal-db` to `docker-compose.yml`. Build `SimulationWorkflow` with 7 activities in `saas/workflows/`. Flag-day cutover — API dispatches workflows via Temporal client; `run_simulation_task`, `resume_simulation_task`, `recover_stale_jobs`, and helper modules are deleted. Celery retained for `generate_report_task`, enrichment retries, maintenance, alerts.

**Tech Stack:** Temporal (self-hosted, `temporalio/auto-setup:1.22.7`), `temporalio` Python SDK (`>=1.8,<2.0`), existing FastAPI + SQLAlchemy + RunPod SDK + MinIO + Celery (for non-sim tasks).

**Reference spec:** `docs/superpowers/specs/2026-04-19-pod-provisioning-temporal-refactor-design.md`

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `pyproject.toml` | Modify | Add `temporalio` dependency |
| `saas/alembic/versions/YYYYMMDD_add_workflow_columns.py` | Create | Migration: add `workflow_id`, `workflow_run_id` |
| `saas/jobs/models.py` | Modify | New columns on `SimulationJob` |
| `saas/workflows/__init__.py` | Create | Package marker |
| `saas/workflows/types.py` | Create | `SimParams`, `SimResult`, `PodInfo` dataclasses (no Temporal imports — shared between workflow and activities) |
| `saas/workflows/client.py` | Create | `get_temporal_client()` helper |
| `saas/workflows/sim_workflow.py` | Create | `SimulationWorkflow` class |
| `saas/workflows/activities/__init__.py` | Create | Package marker |
| `saas/workflows/activities/pre_gpu.py` | Create | `enrich_seed`, `derive_markets` |
| `saas/workflows/activities/provisioning.py` | Create | `provision_pod`, `wait_for_worker_health`, `terminate_pod` |
| `saas/workflows/activities/pipeline.py` | Create | `submit_and_poll` |
| `saas/workflows/activities/finalization.py` | Create | `upload_and_finalize`, `refund_credits` |
| `saas/workflows/worker.py` | Create | Worker bootstrap — registers workflow + activities |
| `docker-compose.yml` | Modify | Add `temporal`, `temporal-db`, `temporal-worker` services (reuses `fishcloud-app` image) |
| `saas/jobs/api.py` | Modify | Swap `POST /jobs` dispatch from Celery to Temporal |
| `saas/jobs/tasks_report.py` | Modify | Add terminal-status guard to `generate_report_task` |
| `saas/workers/celery_app.py` | Modify | Drop `recover-stale-jobs` beat schedule + `worker_ready` hook |
| `saas/jobs/recovery.py` | Delete | Replaced by Temporal |
| `saas/jobs/recovery_utils.py` | Delete | Replaced by Temporal |
| `saas/jobs/recovery_reporting.py` | Delete | Replaced by Temporal |
| `saas/jobs/tasks_resume.py` | Delete | Replaced by Temporal |
| `saas/jobs/tasks.py` | Modify | Delete `run_simulation_task` body and idempotency preamble |
| `saas/jobs/runner.py` | Modify | Delete `resume()` method |
| `tests/workflows/conftest.py` | Create | `WorkflowEnvironment` fixture |
| `tests/workflows/test_activities_pre_gpu.py` | Create | Tests for `enrich_seed`, `derive_markets` activities |
| `tests/workflows/test_activities_provisioning.py` | Create | Tests for provisioning activities |
| `tests/workflows/test_activities_pipeline.py` | Create | Tests for `submit_and_poll` |
| `tests/workflows/test_activities_finalization.py` | Create | Tests for finalization activities |
| `tests/workflows/test_sim_workflow.py` | Create | End-to-end workflow tests including worker-kill replay |

---

### Task 1: Add `temporalio` dependency

**Files:**
- Modify: `pyproject.toml:6-27`

- [ ] **Step 1: Add the dependency**

Edit `pyproject.toml`. Insert `"temporalio>=1.8,<2.0",` in the `dependencies` list (alphabetical placement after `stripe`):

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
    "temporalio>=1.8,<2.0",
    "celery[redis]>=5.4.0",
    # ... rest unchanged
]
```

- [ ] **Step 2: Install locally**

Run: `pip install -e ".[dev]"`

Expected: installs `temporalio` and its transitive deps (`protobuf`, `grpcio`).

- [ ] **Step 3: Verify import**

Run: `python -c "import temporalio; print(temporalio.__version__)"`

Expected: prints a version ≥ 1.8.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "deps: add temporalio SDK for workflow refactor"
```

---

### Task 2: Alembic migration — workflow_id columns

**Files:**
- Create: `saas/alembic/versions/<timestamp>_add_workflow_columns.py`
- Modify: `saas/jobs/models.py`

- [ ] **Step 1: Write the model change**

Open `saas/jobs/models.py`. Find the `SimulationJob` class. Add these two columns near `celery_task_id` (keep the old columns — they're removed in a later cleanup migration, not here):

```python
workflow_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
workflow_run_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
```

- [ ] **Step 2: Generate the migration**

Run: `alembic -c saas/alembic.ini revision --autogenerate -m "add workflow_id columns"`

Expected: creates a file under `saas/alembic/versions/` that adds two columns and an index on `workflow_id`.

- [ ] **Step 3: Review + simplify the generated migration**

Open the generated file. Verify the `upgrade()` body is exactly:

```python
def upgrade() -> None:
    op.add_column('simulation_jobs', sa.Column('workflow_id', sa.String(length=255), nullable=True))
    op.add_column('simulation_jobs', sa.Column('workflow_run_id', sa.String(length=255), nullable=True))
    op.create_index('ix_simulation_jobs_workflow_id', 'simulation_jobs', ['workflow_id'])


def downgrade() -> None:
    op.drop_index('ix_simulation_jobs_workflow_id', table_name='simulation_jobs')
    op.drop_column('simulation_jobs', 'workflow_run_id')
    op.drop_column('simulation_jobs', 'workflow_id')
```

Remove anything else autogen added.

- [ ] **Step 4: Apply + verify**

Run: `alembic -c saas/alembic.ini upgrade head`

Then in a sqlite shell (or postgres): `\d simulation_jobs` — expect `workflow_id`, `workflow_run_id` columns present.

Run the existing test suite: `pytest tests/ -x -q`

Expected: all tests pass (new columns are nullable, don't break anything).

- [ ] **Step 5: Commit**

```bash
git add saas/jobs/models.py saas/alembic/versions/
git commit -m "feat(jobs): add workflow_id/workflow_run_id columns for temporal"
```

---

### Task 3: Scaffold `saas/workflows/` package + types

**Files:**
- Create: `saas/workflows/__init__.py`
- Create: `saas/workflows/types.py`
- Create: `saas/workflows/activities/__init__.py`

- [ ] **Step 1: Create package markers**

Create `saas/workflows/__init__.py` — empty file.

Create `saas/workflows/activities/__init__.py` — empty file.

- [ ] **Step 2: Create `types.py`**

Write `saas/workflows/types.py`:

```python
"""Shared dataclasses for the Simulation workflow.

Zero Temporal imports — this module is safe to import from both the workflow
(sandboxed) and activity (unrestricted) sides without sandbox violations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SimParams:
    """Arguments passed to SimulationWorkflow.run."""
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
    openai_api_key: str = ""
    credits_charged: int = 0
    enrich_web: bool = True
    forecast_days: int | None = None
    target_agents: int = 5
    upload_urls: dict[str, Any] | None = None


@dataclass
class PodInfo:
    """Returned by provision_pod; consumed by downstream activities."""
    id: str


# Note: submit_and_poll and upload_and_finalize communicate via plain dict;
# no SimResult dataclass is defined because SimulationWorkflow.run returns
# None (the API's POST /jobs path does not await workflow.result()).
```

- [ ] **Step 3: Smoke test import**

Run: `python -c "from saas.workflows.types import SimParams, PodInfo; print(SimParams.__dataclass_fields__.keys())"`

Expected: prints field names.

- [ ] **Step 4: Commit**

```bash
git add saas/workflows/
git commit -m "feat(workflows): scaffold workflows package with shared types"
```

---

### Task 4: Temporal client helper

**Files:**
- Create: `saas/workflows/client.py`

- [ ] **Step 1: Write the client helper**

Write `saas/workflows/client.py`:

```python
"""Temporal client factory. Reads TEMPORAL_ADDRESS + TEMPORAL_NAMESPACE from env."""
from __future__ import annotations

import os

from temporalio.client import Client


TEMPORAL_NAMESPACE_DEFAULT = "fishcloud"
SIM_TASK_QUEUE = "sim-queue"


async def get_temporal_client() -> Client:
    """Connect to Temporal using env config.

    Env:
      TEMPORAL_ADDRESS   — host:port, default 'temporal:7233' (docker network hostname)
      TEMPORAL_NAMESPACE — default 'fishcloud'
    """
    address = os.getenv("TEMPORAL_ADDRESS", "temporal:7233")
    namespace = os.getenv("TEMPORAL_NAMESPACE", TEMPORAL_NAMESPACE_DEFAULT)
    return await Client.connect(address, namespace=namespace)
```

- [ ] **Step 2: Smoke test import**

Run: `python -c "from saas.workflows.client import get_temporal_client, SIM_TASK_QUEUE; print(SIM_TASK_QUEUE)"`

Expected: prints `sim-queue`.

- [ ] **Step 3: Commit**

```bash
git add saas/workflows/client.py
git commit -m "feat(workflows): add temporal client factory"
```

---

### Task 5: `enrich_seed` activity (TDD)

**Files:**
- Create: `saas/workflows/activities/pre_gpu.py`
- Create: `tests/workflows/__init__.py`
- Create: `tests/workflows/test_activities_pre_gpu.py`

- [ ] **Step 1: Write failing test**

Create `tests/workflows/__init__.py` — empty file.

Create `tests/workflows/test_activities_pre_gpu.py`:

```python
"""Tests for pre-GPU activities (enrichment, market derivation).

Activities are plain async functions; tests call them directly without
a Temporal runtime. The Temporal @activity.defn decorator is a no-op when
called outside a worker context.
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest


@pytest.mark.asyncio
async def test_enrich_seed_returns_concatenated_text_on_success():
    from saas.workflows.activities.pre_gpu import enrich_seed

    fake_result = MagicMock(summary="Background research body", citations=[{"url": "x"}])

    with patch("saas.jobs.enrichment.enrich_seed", return_value=fake_result) as mock_enrich, \
         patch("saas.jobs.persistence._update_enrichment") as mock_update:
        result = await enrich_seed("seed text", "goal text", job_id=42)

    mock_enrich.assert_called_once_with("seed text", "goal text")
    mock_update.assert_called_once()
    assert "Background research body" in result
    assert "seed text" in result


@pytest.mark.asyncio
async def test_enrich_seed_returns_original_on_miss():
    from saas.workflows.activities.pre_gpu import enrich_seed

    with patch("saas.jobs.enrichment.enrich_seed", return_value=None), \
         patch("saas.jobs.persistence._update_enrichment") as mock_update:
        result = await enrich_seed("seed text", "goal text", job_id=42)

    mock_update.assert_not_called()
    assert result == "seed text"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/workflows/test_activities_pre_gpu.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'saas.workflows.activities.pre_gpu'`.

- [ ] **Step 3: Implement the activity**

Create `saas/workflows/activities/pre_gpu.py`:

```python
"""Pre-GPU activities: seed enrichment and market derivation.

Both activities are thin wrappers around existing saas.jobs.* implementations.
They exist as activities so the workflow can apply Temporal retry policies
and persist progress across worker restarts.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from temporalio import activity

logger = logging.getLogger(__name__)


@activity.defn(name="fishcloud.enrich_seed")
async def enrich_seed(seed_text: str, goal: str, job_id: int) -> str:
    """Enrich seed with xAI search; return concatenated text.

    On enrichment miss, returns the original seed_text unchanged (fail-soft).
    Side-effect: writes enrichment summary + citations to simulation_jobs row.
    """
    from saas.jobs.enrichment import enrich_seed as _enrich
    from saas.jobs.persistence import _update_enrichment

    result = _enrich(seed_text, goal)
    if result is None:
        logger.warning("activity.enrich_seed.miss job_id=%d", job_id)
        return seed_text

    _update_enrichment(job_id, result.summary, json.dumps(result.citations))
    return seed_text + "\n\n--- Background Research ---\n" + result.summary


@activity.defn(name="fishcloud.derive_markets")
async def derive_markets(
    goal: str, enriched_seed: str, tier: str, job_id: int,
) -> list[dict[str, Any]]:
    """Derive 3–5 prediction markets from seed + goal.

    Side-effect: writes markets_config JSON to simulation_jobs row.
    Fails soft: the underlying _derive always returns at least one market.
    """
    from saas.jobs.market_derivation import derive_markets as _derive
    from saas.jobs.persistence import _update_markets_config

    derivation = _derive(goal=goal, enriched_seed=enriched_seed, tier=tier)
    markets = derivation["markets"]
    _update_markets_config(job_id, markets)
    logger.info(
        "activity.derive_markets.ok job_id=%d source=%s count=%d",
        job_id, derivation["source"], len(markets),
    )
    return markets
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/workflows/test_activities_pre_gpu.py -v`

Expected: PASS both tests.

- [ ] **Step 5: Commit**

```bash
git add saas/workflows/activities/pre_gpu.py tests/workflows/
git commit -m "feat(workflows): enrich_seed activity"
```

---

### Task 6: `derive_markets` activity test coverage

**Files:**
- Modify: `tests/workflows/test_activities_pre_gpu.py`

- [ ] **Step 1: Add failing tests for derive_markets**

Append to `tests/workflows/test_activities_pre_gpu.py`:

```python
@pytest.mark.asyncio
async def test_derive_markets_persists_and_returns_list():
    from saas.workflows.activities.pre_gpu import derive_markets

    fake_derivation = {
        "source": "llm",
        "markets": [
            {"name": "M1", "stance": "yes", "question": "q1"},
            {"name": "M2", "stance": "no", "question": "q2"},
        ],
    }

    with patch("saas.jobs.market_derivation.derive_markets", return_value=fake_derivation) as mock_derive, \
         patch("saas.jobs.persistence._update_markets_config") as mock_update:
        result = await derive_markets(goal="g", enriched_seed="s", tier="medium", job_id=77)

    mock_derive.assert_called_once_with(goal="g", enriched_seed="s", tier="medium")
    mock_update.assert_called_once_with(77, fake_derivation["markets"])
    assert len(result) == 2
    assert result[0]["name"] == "M1"
```

- [ ] **Step 2: Run test**

Run: `pytest tests/workflows/test_activities_pre_gpu.py::test_derive_markets_persists_and_returns_list -v`

Expected: PASS (activity already implemented in Task 5; this is coverage).

- [ ] **Step 3: Commit**

```bash
git add tests/workflows/test_activities_pre_gpu.py
git commit -m "test(workflows): derive_markets activity coverage"
```

---

### Task 7: `provision_pod` activity with heartbeat + idempotent re-entry

**Files:**
- Create: `saas/workflows/activities/provisioning.py`
- Create: `tests/workflows/test_activities_provisioning.py`

- [ ] **Step 1: Write failing tests**

Create `tests/workflows/test_activities_provisioning.py`:

```python
"""Tests for provisioning activities (provision_pod, wait_for_worker_health, terminate_pod)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from saas.workflows.types import SimParams


def _params(job_id: int = 1) -> SimParams:
    return SimParams(
        job_id=job_id, user_id="u", seed_text="s", goal="g",
        tier="small", model_id="m", gpu_type="L40S", max_rounds=15,
        vllm_args="", llm_api_key="k",
    )


@pytest.mark.asyncio
async def test_provision_pod_reuses_existing_healthy_pod():
    from saas.workflows.activities.provisioning import provision_pod

    fake_resp = MagicMock(status_code=200)
    fake_client = AsyncMock()
    fake_client.get = AsyncMock(return_value=fake_resp)
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=None)

    with patch("saas.jobs.persistence._load_job_snapshot", return_value=("PROVISIONING", "pod-abc", 0)), \
         patch("httpx.AsyncClient", return_value=fake_client), \
         patch("saas.workers.utils._get_gpu_provider") as mock_provider:
        pod = await provision_pod(_params(), markets=[])

    assert pod.id == "pod-abc"
    mock_provider.assert_not_called()  # did not provision a new pod


@pytest.mark.asyncio
async def test_provision_pod_creates_new_when_no_existing():
    from saas.workflows.activities.provisioning import provision_pod

    fake_instance = MagicMock(instance_id="pod-new")
    fake_provider = MagicMock()
    fake_provider.provision = AsyncMock(return_value=fake_instance)

    with patch("saas.jobs.persistence._load_job_snapshot", return_value=("PENDING", None, 0)), \
         patch("saas.workers.utils._get_gpu_provider", return_value=fake_provider), \
         patch("saas.jobs.persistence._update_pod_id") as mock_update_pod, \
         patch("saas.jobs.persistence._update_pipeline_stage_sync") as mock_update_stage:
        pod = await provision_pod(_params(job_id=5), markets=[])

    assert pod.id == "pod-new"
    mock_update_stage.assert_called_once_with(5, 0)
    # on_created callback wires _update_pod_id; verify provider received it
    call_kwargs = fake_provider.provision.call_args.kwargs
    assert "on_created" in call_kwargs
    # trigger the on_created callback manually to verify it writes to DB
    import asyncio
    asyncio.get_event_loop().run_until_complete(call_kwargs["on_created"]("pod-new"))
    mock_update_pod.assert_called_with(5, "pod-new")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/workflows/test_activities_provisioning.py -v`

Expected: FAIL — `saas.workflows.activities.provisioning` does not exist.

- [ ] **Step 3: Implement the activity**

Create `saas/workflows/activities/provisioning.py`:

```python
"""Provisioning-phase activities: pod creation, health wait, teardown."""
from __future__ import annotations

import asyncio
import logging

import httpx
from temporalio import activity

from saas.workflows.types import PodInfo, SimParams

logger = logging.getLogger(__name__)


async def _heartbeat_every(interval_s: float) -> None:
    """Background task that pings Temporal heartbeat on a fixed interval."""
    while True:
        activity.heartbeat()
        await asyncio.sleep(interval_s)


@activity.defn(name="fishcloud.provision_pod")
async def provision_pod(params: SimParams, markets: list[dict]) -> PodInfo:
    """Provision a RunPod instance. Idempotent on re-entry: if an existing pod
    for this job_id is healthy, reuse it instead of creating a new one.
    """
    from saas.jobs.persistence import (
        _load_job_snapshot, _update_pipeline_stage_sync, _update_pod_id,
    )
    from saas.workers.utils import _get_gpu_provider

    # Idempotent re-entry check: if a pod already exists and is healthy, reuse
    snapshot = _load_job_snapshot(params.job_id)
    if snapshot is not None:
        _status, existing_pod_id, _retry = snapshot
        if existing_pod_id:
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    url = f"https://{existing_pod_id}-5000.proxy.runpod.net/health"
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        logger.info(
                            "activity.provision_pod.reuse job_id=%d pod_id=%s",
                            params.job_id, existing_pod_id,
                        )
                        return PodInfo(id=existing_pod_id)
            except Exception as e:
                logger.info(
                    "activity.provision_pod.existing_unhealthy "
                    "job_id=%d pod_id=%s error=%s — creating fresh",
                    params.job_id, existing_pod_id, e,
                )

    _update_pipeline_stage_sync(params.job_id, 0)

    # Build gpu config from JobConfig shape
    from saas.constants.tiers import TIER_MAX_COST_USD, TIER_TIMEOUTS
    from saas.gpu.provider import GPUProviderConfig
    from saas.jobs.config import JobConfig, get_worker_image
    import os

    job_config = JobConfig(
        job_id=params.job_id, user_id=params.user_id,
        seed_text=params.seed_text, goal=params.goal, tier=params.tier,
        model_id=params.model_id, gpu_type=params.gpu_type,
        max_rounds=params.max_rounds, vllm_args=params.vllm_args,
        llm_api_key=params.llm_api_key, openai_api_key=params.openai_api_key,
        neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_user=os.getenv("NEO4J_USER", "neo4j"),
        neo4j_password=os.getenv("NEO4J_PASSWORD", ""),
        forecast_days=params.forecast_days,
        target_agents=params.target_agents,
        upload_urls=params.upload_urls,
        markets_config=markets,
    )

    gpu_config = GPUProviderConfig(
        gpu_type=params.gpu_type,
        docker_image=get_worker_image(),
        max_cost_per_hour_usd=TIER_MAX_COST_USD.get(params.tier, 4.00),
        timeout_seconds=TIER_TIMEOUTS.get(params.tier, 2700),
        env_vars=job_config.to_worker_env(),
        job_id=params.job_id,
    )

    async def _on_created(pid: str) -> None:
        _update_pod_id(params.job_id, pid)
        activity.heartbeat()

    # Heartbeat from a side task so the RunPod ready-wait loop stays untouched
    heartbeat_task = asyncio.create_task(_heartbeat_every(30))
    try:
        gpu_provider = _get_gpu_provider()
        instance = await gpu_provider.provision(gpu_config, on_created=_on_created)
        return PodInfo(id=instance.instance_id)
    finally:
        heartbeat_task.cancel()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/workflows/test_activities_provisioning.py -v`

Expected: PASS both tests.

- [ ] **Step 5: Commit**

```bash
git add saas/workflows/activities/provisioning.py tests/workflows/test_activities_provisioning.py
git commit -m "feat(workflows): provision_pod activity with idempotent reuse"
```

---

### Task 8: `wait_for_worker_health` activity

**Files:**
- Modify: `saas/workflows/activities/provisioning.py`
- Modify: `tests/workflows/test_activities_provisioning.py`

- [ ] **Step 1: Write failing test**

Append to `tests/workflows/test_activities_provisioning.py`:

```python
@pytest.mark.asyncio
async def test_wait_for_worker_health_returns_on_200():
    from saas.workflows.activities.provisioning import wait_for_worker_health

    ok_resp = MagicMock(
        status_code=200,
        headers={"content-type": "application/json"},
    )
    ok_resp.json = MagicMock(return_value={"vllm_ready": True, "status": "ok"})

    fake_client = AsyncMock()
    fake_client.get = AsyncMock(return_value=ok_resp)
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=fake_client):
        # Should return without raising
        await wait_for_worker_health("pod-xyz")

    fake_client.get.assert_called()
    # Verify it hit /health not /status
    call_url = fake_client.get.call_args[0][0]
    assert call_url.endswith("/health")
```

- [ ] **Step 2: Run test to verify fails**

Run: `pytest tests/workflows/test_activities_provisioning.py::test_wait_for_worker_health_returns_on_200 -v`

Expected: FAIL — `wait_for_worker_health` not defined.

- [ ] **Step 3: Implement the activity**

Append to `saas/workflows/activities/provisioning.py`:

```python
@activity.defn(name="fishcloud.wait_for_worker_health")
async def wait_for_worker_health(pod_id: str) -> None:
    """Poll /health until 200 OK. Heartbeats on each attempt.

    The activity's start_to_close timeout (15 min) bounds the total wait.
    Heartbeats let Temporal kill hung activities faster than that.
    """
    worker_url = f"https://{pod_id}-5000.proxy.runpod.net"
    async with httpx.AsyncClient(timeout=15) as client:
        while True:
            activity.heartbeat()
            try:
                resp = await client.get(f"{worker_url}/health", timeout=10)
                if resp.status_code == 200:
                    body = resp.json() if resp.headers.get(
                        "content-type", "").startswith("application/json") else {}
                    logger.info(
                        "activity.wait_for_worker_health.ready pod_id=%s vllm_ready=%s",
                        pod_id, body.get("vllm_ready", "?"),
                    )
                    return
            except httpx.ConnectError:
                pass
            except Exception as e:
                logger.info(
                    "activity.wait_for_worker_health.retry pod_id=%s error=%s",
                    pod_id, type(e).__name__,
                )
            await asyncio.sleep(5)
```

- [ ] **Step 4: Run test to verify passes**

Run: `pytest tests/workflows/test_activities_provisioning.py::test_wait_for_worker_health_returns_on_200 -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add saas/workflows/activities/provisioning.py tests/workflows/test_activities_provisioning.py
git commit -m "feat(workflows): wait_for_worker_health activity"
```

---

### Task 9: `terminate_pod` activity (idempotent)

**Files:**
- Modify: `saas/workflows/activities/provisioning.py`
- Modify: `tests/workflows/test_activities_provisioning.py`

- [ ] **Step 1: Write failing test**

Append to `tests/workflows/test_activities_provisioning.py`:

```python
@pytest.mark.asyncio
async def test_terminate_pod_swallows_not_found():
    from saas.workflows.activities.provisioning import terminate_pod

    fake_provider = MagicMock()
    fake_provider.terminate = AsyncMock(side_effect=Exception("pod not found to terminate"))

    with patch("saas.workers.utils._get_gpu_provider", return_value=fake_provider):
        # Must not raise
        await terminate_pod("pod-gone")

    fake_provider.terminate.assert_called_once_with("pod-gone")


@pytest.mark.asyncio
async def test_terminate_pod_calls_provider():
    from saas.workflows.activities.provisioning import terminate_pod

    fake_provider = MagicMock()
    fake_provider.terminate = AsyncMock(return_value=None)

    with patch("saas.workers.utils._get_gpu_provider", return_value=fake_provider):
        await terminate_pod("pod-alive")

    fake_provider.terminate.assert_called_once_with("pod-alive")
```

- [ ] **Step 2: Run test to verify fails**

Run: `pytest tests/workflows/test_activities_provisioning.py -v -k terminate`

Expected: FAIL — `terminate_pod` not defined.

- [ ] **Step 3: Implement**

Append to `saas/workflows/activities/provisioning.py`:

```python
@activity.defn(name="fishcloud.terminate_pod")
async def terminate_pod(pod_id: str) -> None:
    """Terminate the pod. Idempotent — swallows 'not found' errors."""
    from saas.workers.utils import _get_gpu_provider

    gpu_provider = _get_gpu_provider()
    try:
        await gpu_provider.terminate(pod_id)
        logger.info("activity.terminate_pod.ok pod_id=%s", pod_id)
    except Exception as e:
        msg = str(e).lower()
        if "not found" in msg or "does not exist" in msg:
            logger.info("activity.terminate_pod.already_gone pod_id=%s", pod_id)
            return
        # Other errors (auth, network) — re-raise so Temporal retry policy triggers
        logger.warning("activity.terminate_pod.error pod_id=%s error=%s", pod_id, e)
        raise
```

- [ ] **Step 4: Run test to verify passes**

Run: `pytest tests/workflows/test_activities_provisioning.py -v -k terminate`

Expected: PASS both terminate tests.

- [ ] **Step 5: Commit**

```bash
git add saas/workflows/activities/provisioning.py tests/workflows/test_activities_provisioning.py
git commit -m "feat(workflows): terminate_pod activity, idempotent on missing"
```

---

### Task 10: `submit_and_poll` activity with resume-in-place

**Files:**
- Create: `saas/workflows/activities/pipeline.py`
- Create: `tests/workflows/test_activities_pipeline.py`

- [ ] **Step 1: Write failing test**

Create `tests/workflows/test_activities_pipeline.py`:

```python
"""Tests for the submit_and_poll activity."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from saas.workflows.types import SimParams


def _params(job_id: int = 1) -> SimParams:
    return SimParams(
        job_id=job_id, user_id="u", seed_text="s", goal="g",
        tier="small", model_id="m", gpu_type="L40S", max_rounds=15,
        vllm_args="", llm_api_key="k",
    )


@pytest.mark.asyncio
async def test_submit_and_poll_resumes_when_pod_already_running():
    """If /status shows running, don't re-POST /job — hand off to polling."""
    from saas.workflows.activities.pipeline import submit_and_poll

    status_resp = MagicMock(status_code=200)
    status_resp.json = MagicMock(return_value={"status": "running"})

    fake_client = AsyncMock()
    fake_client.get = AsyncMock(return_value=status_resp)
    fake_client.post = AsyncMock()  # should NOT be called
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=None)

    async def fake_poll(*args, **kwargs):
        return {
            "report": "", "chat_log": "[]", "graph_data": "{}", "structured": "{}",
            "sim_data_uploaded": True, "pod_id": "pod-1",
        }

    with patch("httpx.AsyncClient", return_value=fake_client), \
         patch("saas.jobs.pipeline.poll_until_complete", side_effect=fake_poll), \
         patch("saas.jobs.persistence._transition_to_running"):
        result = await submit_and_poll("pod-1", _params(), markets=[])

    fake_client.post.assert_not_called()
    assert result["sim_data_uploaded"] is True


@pytest.mark.asyncio
async def test_submit_and_poll_submits_when_pod_idle():
    from saas.workflows.activities.pipeline import submit_and_poll

    status_resp = MagicMock(status_code=200)
    status_resp.json = MagicMock(return_value={"status": "idle"})
    submit_resp = MagicMock(status_code=200)

    fake_client = AsyncMock()
    fake_client.get = AsyncMock(return_value=status_resp)
    fake_client.post = AsyncMock(return_value=submit_resp)
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=None)

    async def fake_poll(*args, **kwargs):
        return {
            "report": "", "chat_log": "[]", "graph_data": "{}", "structured": "{}",
            "sim_data_uploaded": True, "pod_id": "pod-2",
        }

    with patch("httpx.AsyncClient", return_value=fake_client), \
         patch("saas.jobs.pipeline.poll_until_complete", side_effect=fake_poll), \
         patch("saas.jobs.persistence._transition_to_running"):
        await submit_and_poll("pod-2", _params(job_id=7), markets=[{"name": "M"}])

    fake_client.post.assert_called_once()
    post_url = fake_client.post.call_args[0][0]
    assert post_url.endswith("/job")
```

- [ ] **Step 2: Run tests to verify fail**

Run: `pytest tests/workflows/test_activities_pipeline.py -v`

Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

Create `saas/workflows/activities/pipeline.py`:

```python
"""Pipeline-phase activity: submit /job and poll /status until complete."""
from __future__ import annotations

import asyncio
import logging

import httpx
from temporalio import activity

from saas.workflows.types import SimParams

logger = logging.getLogger(__name__)


async def _heartbeat_every(interval_s: float) -> None:
    while True:
        activity.heartbeat()
        await asyncio.sleep(interval_s)


@activity.defn(name="fishcloud.submit_and_poll")
async def submit_and_poll(
    pod_id: str, params: SimParams, markets: list[dict],
) -> dict:
    """POST /job (if pod idle) and poll /status until completion.

    Idempotent: if the pod reports 'running' or 'completed', skip POST and
    go straight to polling. This mirrors the current runner.resume() logic
    and makes the activity safe to retry after a worker restart.
    """
    from saas.jobs.persistence import (
        _transition_to_running, _update_heartbeat_sync,
        _update_pipeline_stage_sync,
    )
    from saas.jobs.pipeline import poll_until_complete, submit_job
    from saas.jobs.config import JobConfig
    import os

    worker_url = f"https://{pod_id}-5000.proxy.runpod.net"

    # Build the same config submit_job expects
    job_config = JobConfig(
        job_id=params.job_id, user_id=params.user_id,
        seed_text=params.seed_text, goal=params.goal, tier=params.tier,
        model_id=params.model_id, gpu_type=params.gpu_type,
        max_rounds=params.max_rounds, vllm_args=params.vllm_args,
        llm_api_key=params.llm_api_key, openai_api_key=params.openai_api_key,
        neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_user=os.getenv("NEO4J_USER", "neo4j"),
        neo4j_password=os.getenv("NEO4J_PASSWORD", ""),
        forecast_days=params.forecast_days,
        target_agents=params.target_agents,
        upload_urls=params.upload_urls,
        markets_config=markets,
    )

    # Callbacks for the polling loop — write progress to DB
    async def _stage_cb(j_id: int, stage: int) -> None:
        _update_pipeline_stage_sync(j_id, stage)
        activity.heartbeat()

    async def _heartbeat_cb(j_id: int) -> None:
        _update_heartbeat_sync(j_id)
        activity.heartbeat()

    async def _status_cb(j_id: int, _status: str) -> None:
        _transition_to_running(j_id)

    heartbeat_task = asyncio.create_task(_heartbeat_every(30))
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # Check pod state — if running/completed, skip POST (idempotent reentry)
            try:
                status_resp = await client.get(f"{worker_url}/status", timeout=10)
                status = status_resp.json().get("status", "unknown") if status_resp.status_code == 200 else "unknown"
            except Exception:
                status = "unknown"

            if status in ("running", "completed"):
                logger.info(
                    "activity.submit_and_poll.resume pod_id=%s status=%s",
                    pod_id, status,
                )
            else:
                logger.info("activity.submit_and_poll.submitting pod_id=%s", pod_id)
                await submit_job(worker_url, job_config, client)

            result = await poll_until_complete(
                worker_url, pod_id, job_config, client=client,
                stage_callback=_stage_cb,
                heartbeat_callback=_heartbeat_cb,
                status_callback=_status_cb,
            )
            result["pod_id"] = pod_id
            return result
    finally:
        heartbeat_task.cancel()
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/workflows/test_activities_pipeline.py -v`

Expected: PASS both tests.

- [ ] **Step 5: Commit**

```bash
git add saas/workflows/activities/pipeline.py tests/workflows/test_activities_pipeline.py
git commit -m "feat(workflows): submit_and_poll activity with resume-in-place"
```

---

### Task 11: `upload_and_finalize` activity

**Files:**
- Create: `saas/workflows/activities/finalization.py`
- Create: `tests/workflows/test_activities_finalization.py`

- [ ] **Step 1: Write failing test**

Create `tests/workflows/test_activities_finalization.py`:

```python
"""Tests for finalization activities (upload_and_finalize, refund_credits)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_upload_and_finalize_persists_results_and_enqueues_report():
    from saas.workflows.activities.finalization import upload_and_finalize

    result = {
        "pod_id": "pod-1",
        "provision_seconds": 100, "pipeline_seconds": 700,
        "report": "", "chat_log": "[]",
        "graph_data": "{}", "structured": "{}",
        "sim_data_uploaded": True,
    }

    with patch("saas.jobs.persistence._update_job_metadata") as mock_meta, \
         patch("saas.jobs.persistence._save_job_results") as mock_save, \
         patch("saas.jobs.persistence._update_sim_data_available") as mock_sim_avail, \
         patch("saas.jobs.persistence._transition_to_reporting") as mock_reporting, \
         patch("saas.jobs.tasks_report.generate_report_task.apply_async") as mock_enqueue:
        await upload_and_finalize(job_id=55, user_id="u1", result=result)

    mock_meta.assert_called_once()
    mock_save.assert_called_once()
    mock_sim_avail.assert_called_once_with(55, True)
    mock_reporting.assert_called_once_with(55)
    mock_enqueue.assert_called_once()


@pytest.mark.asyncio
async def test_upload_and_finalize_raises_when_upload_missing():
    from saas.workflows.activities.finalization import upload_and_finalize

    result = {
        "pod_id": "pod-1",
        "provision_seconds": 100, "pipeline_seconds": 700,
        "sim_data_uploaded": False,
    }

    with patch("saas.jobs.persistence._update_job_metadata"), \
         patch("saas.jobs.persistence._save_job_results"), \
         patch("saas.jobs.tasks_report.generate_report_task.apply_async") as mock_enqueue:
        with pytest.raises(RuntimeError, match="sim_data_upload_failed"):
            await upload_and_finalize(job_id=55, user_id="u1", result=result)

    mock_enqueue.assert_not_called()
```

- [ ] **Step 2: Run test to verify fails**

Run: `pytest tests/workflows/test_activities_finalization.py -v`

Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

Create `saas/workflows/activities/finalization.py`:

```python
"""Finalization activities: result upload/handoff, credit refund on failure."""
from __future__ import annotations

import logging

from temporalio import activity

logger = logging.getLogger(__name__)


@activity.defn(name="fishcloud.upload_and_finalize")
async def upload_and_finalize(job_id: int, user_id: str, result: dict) -> None:
    """Persist sim results, transition to REPORTING, enqueue report task.

    Raises RuntimeError if sim_data was not uploaded to MinIO — that's
    fatal under the external-report flow.
    """
    from saas.jobs.persistence import (
        _save_job_results, _transition_to_reporting,
        _update_job_metadata, _update_sim_data_available,
    )

    pod_id = result.get("pod_id", "")
    provision_seconds = result.get("provision_seconds")
    pipeline_seconds = result.get("pipeline_seconds")

    if pod_id:
        _update_job_metadata(
            job_id=job_id, pod_id=pod_id,
            provision_seconds=provision_seconds,
            pipeline_seconds=pipeline_seconds,
        )

    _save_job_results(
        job_id=job_id,
        report=result.get("report", ""),
        chat_log=result.get("chat_log", ""),
        graph_data=result.get("graph_data", "{}"),
        key_insight=None,
        structured=result.get("structured", "{}"),
    )

    if not result.get("sim_data_uploaded", False):
        raise RuntimeError(
            "sim_data_upload_failed: artifacts missing from MinIO"
        )

    _update_sim_data_available(job_id, True)
    _transition_to_reporting(job_id)

    import saas.jobs.tasks_report as _tasks_report
    _tasks_report.generate_report_task.apply_async((job_id, user_id))

    logger.info(
        "activity.upload_and_finalize.ok job_id=%d pod_id=%s",
        job_id, pod_id,
    )
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/workflows/test_activities_finalization.py -v`

Expected: PASS both tests.

- [ ] **Step 5: Commit**

```bash
git add saas/workflows/activities/finalization.py tests/workflows/test_activities_finalization.py
git commit -m "feat(workflows): upload_and_finalize activity"
```

---

### Task 12: `refund_credits` activity (idempotent)

**Files:**
- Modify: `saas/workflows/activities/finalization.py`
- Modify: `tests/workflows/test_activities_finalization.py`

- [ ] **Step 1: Write failing test**

Append to `tests/workflows/test_activities_finalization.py`:

```python
@pytest.mark.asyncio
async def test_refund_credits_invokes_refund_helper():
    from saas.workflows.activities.finalization import refund_credits

    with patch("saas.jobs.refund._refund_credits") as mock_refund, \
         patch("saas.jobs.persistence._mark_job_failed_sync") as mock_mark:
        await refund_credits(
            job_id=10, user_id="u", credits=90,
            error_message="activity_timed_out",
        )

    mock_mark.assert_called_once_with(10, "activity_timed_out")
    mock_refund.assert_called_once_with(job_id=10, user_id="u", credits=90)


@pytest.mark.asyncio
async def test_refund_credits_skips_refund_for_zero_credits():
    from saas.workflows.activities.finalization import refund_credits

    with patch("saas.jobs.refund._refund_credits") as mock_refund, \
         patch("saas.jobs.persistence._mark_job_failed_sync") as mock_mark:
        await refund_credits(
            job_id=11, user_id="u", credits=0, error_message="err",
        )

    mock_mark.assert_called_once()
    mock_refund.assert_not_called()
```

- [ ] **Step 2: Run test to verify fails**

Run: `pytest tests/workflows/test_activities_finalization.py -v -k refund`

Expected: FAIL — `refund_credits` not defined.

- [ ] **Step 3: Implement**

Append to `saas/workflows/activities/finalization.py`:

```python
@activity.defn(name="fishcloud.refund_credits")
async def refund_credits(
    job_id: int, user_id: str, credits: int, error_message: str,
) -> None:
    """Mark the job FAILED and refund credits. Idempotent via the existing
    NOT EXISTS guard in _refund_credits.
    """
    from saas.jobs.persistence import _mark_job_failed_sync
    from saas.jobs.refund import _refund_credits

    _mark_job_failed_sync(job_id, error_message)
    if credits > 0:
        _refund_credits(job_id=job_id, user_id=user_id, credits=credits)
    logger.info(
        "activity.refund_credits.ok job_id=%d credits=%d",
        job_id, credits,
    )
```

- [ ] **Step 4: Run test to verify passes**

Run: `pytest tests/workflows/test_activities_finalization.py -v -k refund`

Expected: PASS both tests.

- [ ] **Step 5: Verify `_mark_job_failed_sync` exists**

Run: `grep -n "_mark_job_failed_sync" saas/jobs/persistence*.py`

If it doesn't exist, find the actual name (`_mark_job_failed` in async context or similar). Update the activity and test to call the correct function — the persistence layer has both sync and async variants. Re-run test.

- [ ] **Step 6: Commit**

```bash
git add saas/workflows/activities/finalization.py tests/workflows/test_activities_finalization.py
git commit -m "feat(workflows): refund_credits activity"
```

---

### Task 13: `SimulationWorkflow` wiring all activities

**Files:**
- Create: `saas/workflows/sim_workflow.py`
- Create: `tests/workflows/conftest.py`
- Create: `tests/workflows/test_sim_workflow.py`

- [ ] **Step 1: Create Temporal test fixture**

Create `tests/workflows/conftest.py`:

```python
"""Shared fixtures for workflow tests: time-skipping Temporal environment."""
from __future__ import annotations

import pytest
import pytest_asyncio
from temporalio.testing import WorkflowEnvironment


@pytest_asyncio.fixture
async def temporal_env():
    """Time-skipping Temporal environment — no external server needed."""
    env = await WorkflowEnvironment.start_time_skipping()
    try:
        yield env
    finally:
        await env.shutdown()
```

- [ ] **Step 2: Write failing end-to-end workflow test**

Create `tests/workflows/test_sim_workflow.py`:

```python
"""End-to-end tests for SimulationWorkflow using time-skipping Temporal env."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from temporalio.worker import Worker

from saas.workflows.client import SIM_TASK_QUEUE
from saas.workflows.types import SimParams, PodInfo


def _params(job_id: int = 1) -> SimParams:
    return SimParams(
        job_id=job_id, user_id="u1", seed_text="s", goal="g",
        tier="small", model_id="m", gpu_type="L40S", max_rounds=15,
        vllm_args="", llm_api_key="k", credits_charged=30,
    )


@pytest.mark.asyncio
async def test_workflow_happy_path(temporal_env):
    """Run a full workflow with all activities mocked to succeed.

    Validates: activities are called in order; refund_credits is NOT called
    on success; terminate_pod IS called (finally block).
    """
    from saas.workflows.sim_workflow import SimulationWorkflow

    call_log: list[str] = []

    async def fake_enrich(seed, goal, job_id):
        call_log.append("enrich_seed"); return seed

    async def fake_markets(goal, seed, tier, job_id):
        call_log.append("derive_markets"); return [{"name": "M1"}]

    async def fake_provision(params, markets):
        call_log.append("provision_pod"); return PodInfo(id="pod-test")

    async def fake_health(pod_id):
        call_log.append("wait_for_worker_health")

    async def fake_submit(pod_id, params, markets):
        call_log.append("submit_and_poll")
        return {
            "pod_id": pod_id, "provision_seconds": 100, "pipeline_seconds": 700,
            "report": "", "chat_log": "[]",
            "graph_data": "{}", "structured": "{}",
            "sim_data_uploaded": True,
        }

    async def fake_upload(job_id, user_id, result):
        call_log.append("upload_and_finalize")

    async def fake_terminate(pod_id):
        call_log.append("terminate_pod")

    async def fake_refund(job_id, user_id, credits, error_message):
        call_log.append("refund_credits")

    # Register fakes as activities for the test worker
    from temporalio import activity

    @activity.defn(name="fishcloud.enrich_seed")
    async def _enrich(a, b, c): return await fake_enrich(a, b, c)

    @activity.defn(name="fishcloud.derive_markets")
    async def _markets(a, b, c, d): return await fake_markets(a, b, c, d)

    @activity.defn(name="fishcloud.provision_pod")
    async def _provision(a, b): return await fake_provision(a, b)

    @activity.defn(name="fishcloud.wait_for_worker_health")
    async def _health(a): return await fake_health(a)

    @activity.defn(name="fishcloud.submit_and_poll")
    async def _submit(a, b, c): return await fake_submit(a, b, c)

    @activity.defn(name="fishcloud.upload_and_finalize")
    async def _upload(a, b, c): return await fake_upload(a, b, c)

    @activity.defn(name="fishcloud.terminate_pod")
    async def _terminate(a): return await fake_terminate(a)

    @activity.defn(name="fishcloud.refund_credits")
    async def _refund(a, b, c, d): return await fake_refund(a, b, c, d)

    activities = [_enrich, _markets, _provision, _health, _submit, _upload, _terminate, _refund]

    async with Worker(
        temporal_env.client,
        task_queue=SIM_TASK_QUEUE,
        workflows=[SimulationWorkflow],
        activities=activities,
    ):
        handle = await temporal_env.client.start_workflow(
            SimulationWorkflow.run,
            _params(),
            id=f"sim-test-{uuid.uuid4()}",
            task_queue=SIM_TASK_QUEUE,
        )
        await handle.result()

    # Happy path: refund NOT called, terminate IS called
    assert "refund_credits" not in call_log
    assert "terminate_pod" in call_log
    # Order check — provision before pipeline
    assert call_log.index("provision_pod") < call_log.index("submit_and_poll")
    assert call_log.index("wait_for_worker_health") < call_log.index("submit_and_poll")
    assert call_log.index("submit_and_poll") < call_log.index("upload_and_finalize")


@pytest.mark.asyncio
async def test_workflow_refunds_when_pipeline_fails(temporal_env):
    """Pipeline activity raises — refund + terminate must run."""
    from saas.workflows.sim_workflow import SimulationWorkflow
    from temporalio import activity

    call_log: list[str] = []

    @activity.defn(name="fishcloud.enrich_seed")
    async def _e(a, b, c): call_log.append("enrich"); return a
    @activity.defn(name="fishcloud.derive_markets")
    async def _m(a, b, c, d): call_log.append("markets"); return []
    @activity.defn(name="fishcloud.provision_pod")
    async def _p(a, b): call_log.append("provision"); return PodInfo(id="pod-x")
    @activity.defn(name="fishcloud.wait_for_worker_health")
    async def _h(a): call_log.append("health")
    @activity.defn(name="fishcloud.submit_and_poll")
    async def _s(a, b, c): call_log.append("submit"); raise RuntimeError("pipeline boom")
    @activity.defn(name="fishcloud.upload_and_finalize")
    async def _u(a, b, c): call_log.append("upload")
    @activity.defn(name="fishcloud.terminate_pod")
    async def _t(a): call_log.append("terminate")
    @activity.defn(name="fishcloud.refund_credits")
    async def _r(a, b, c, d): call_log.append("refund")

    async with Worker(
        temporal_env.client, task_queue=SIM_TASK_QUEUE,
        workflows=[SimulationWorkflow],
        activities=[_e, _m, _p, _h, _s, _u, _t, _r],
    ):
        handle = await temporal_env.client.start_workflow(
            SimulationWorkflow.run, _params(),
            id=f"sim-fail-{uuid.uuid4()}", task_queue=SIM_TASK_QUEUE,
        )
        with pytest.raises(Exception):
            await handle.result()

    assert "upload" not in call_log  # never reached
    assert "refund" in call_log      # saga compensation fired
    assert "terminate" in call_log   # finally still runs
```

- [ ] **Step 3: Run test to verify fails**

Run: `pytest tests/workflows/test_sim_workflow.py -v`

Expected: FAIL — `saas.workflows.sim_workflow` not defined.

- [ ] **Step 4: Implement the workflow**

Create `saas/workflows/sim_workflow.py`:

```python
"""SimulationWorkflow — owns the full sim lifecycle.

The workflow is pure orchestration: it calls activities with timeouts and
retry policies, wires them together, and runs a saga compensation block
(refund_credits) on any failure inside the GPU-phase try block.
"""
from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from saas.constants.tiers import TIER_TIMEOUTS
    from saas.workflows.types import PodInfo, SimParams


@workflow.defn(name="fishcloud.SimulationWorkflow")
class SimulationWorkflow:
    @workflow.run
    async def run(self, params: SimParams) -> None:
        # Phase 1: pre-GPU, fail-soft
        enriched_seed = params.seed_text
        if params.enrich_web:
            enriched_seed = await workflow.execute_activity(
                "fishcloud.enrich_seed",
                args=[params.seed_text, params.goal, params.job_id],
                start_to_close_timeout=timedelta(seconds=60),
                retry_policy=RetryPolicy(maximum_attempts=2),
            )

        markets = await workflow.execute_activity(
            "fishcloud.derive_markets",
            args=[params.goal, enriched_seed, params.tier, params.job_id],
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )

        # Phase 2: GPU lifecycle
        pod: PodInfo = await workflow.execute_activity(
            "fishcloud.provision_pod",
            args=[params, markets],
            start_to_close_timeout=timedelta(minutes=10),
            heartbeat_timeout=timedelta(seconds=60),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=30),
                maximum_attempts=3,
            ),
        )

        try:
            await workflow.execute_activity(
                "fishcloud.wait_for_worker_health",
                args=[pod.id],
                start_to_close_timeout=timedelta(minutes=15),
                heartbeat_timeout=timedelta(seconds=30),
            )

            result = await workflow.execute_activity(
                "fishcloud.submit_and_poll",
                args=[pod.id, params, markets],
                start_to_close_timeout=timedelta(
                    seconds=TIER_TIMEOUTS.get(params.tier, 2700),
                ),
                heartbeat_timeout=timedelta(seconds=180),
            )

            await workflow.execute_activity(
                "fishcloud.upload_and_finalize",
                args=[params.job_id, params.user_id, result],
                start_to_close_timeout=timedelta(minutes=10),
                heartbeat_timeout=timedelta(seconds=60),
            )
        except Exception as e:
            # Saga compensation: refund the user before propagating failure
            await workflow.execute_activity(
                "fishcloud.refund_credits",
                args=[
                    params.job_id, params.user_id,
                    params.credits_charged, str(e)[:4096],
                ],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=5),
            )
            raise
        finally:
            # Always terminate the pod, success or failure
            await workflow.execute_activity(
                "fishcloud.terminate_pod",
                args=[pod.id],
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(maximum_attempts=5),
            )
```

- [ ] **Step 5: Run test to verify passes**

Run: `pytest tests/workflows/test_sim_workflow.py -v`

Expected: PASS both tests.

- [ ] **Step 6: Commit**

```bash
git add saas/workflows/sim_workflow.py tests/workflows/
git commit -m "feat(workflows): SimulationWorkflow with saga refund compensation"
```

---

### Task 14: Worker bootstrap

**Files:**
- Create: `saas/workflows/worker.py`

- [ ] **Step 1: Write the worker module**

Create `saas/workflows/worker.py`:

```python
"""Temporal worker bootstrap. Run as: python -m saas.workflows.worker"""
from __future__ import annotations

import asyncio
import logging

from temporalio.worker import Worker

from saas.workflows.activities.finalization import (
    refund_credits, upload_and_finalize,
)
from saas.workflows.activities.pipeline import submit_and_poll
from saas.workflows.activities.pre_gpu import derive_markets, enrich_seed
from saas.workflows.activities.provisioning import (
    provision_pod, terminate_pod, wait_for_worker_health,
)
from saas.workflows.client import SIM_TASK_QUEUE, get_temporal_client
from saas.workflows.sim_workflow import SimulationWorkflow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("saas.workflows.worker")


async def main() -> None:
    client = await get_temporal_client()
    logger.info("temporal.worker.connected task_queue=%s", SIM_TASK_QUEUE)

    worker = Worker(
        client,
        task_queue=SIM_TASK_QUEUE,
        workflows=[SimulationWorkflow],
        activities=[
            enrich_seed, derive_markets,
            provision_pod, wait_for_worker_health, terminate_pod,
            submit_and_poll,
            upload_and_finalize, refund_credits,
        ],
    )
    logger.info("temporal.worker.starting")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Smoke test import**

Run: `python -c "from saas.workflows import worker; print(worker.main)"`

Expected: prints the coroutine function without error.

- [ ] **Step 3: Commit**

```bash
git add saas/workflows/worker.py
git commit -m "feat(workflows): temporal worker bootstrap"
```

---

### Task 15: docker-compose entries for Temporal

**Files:**
- Modify: `docker-compose.yml`

No new Dockerfile needed — `simswarm-temporal-worker` reuses the existing `fishcloud-app` image (same pattern as the `celery` service). Only the `command:` differs.

- [ ] **Step 1: Add the three new services to docker-compose.yml**

Edit `docker-compose.yml`. Add these service entries (placement: alongside `db`, `redis`, `celery`):

```yaml
  temporal-db:
    image: postgres:16-alpine
    container_name: simswarm-temporal-db
    restart: unless-stopped
    environment:
      POSTGRES_USER: temporal
      POSTGRES_PASSWORD: ${TEMPORAL_DB_PASSWORD}
      POSTGRES_DB: temporal
    volumes:
      - temporaldata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U temporal"]
      interval: 5s
      timeout: 5s
      retries: 5

  temporal:
    image: temporalio/auto-setup:1.22.7
    container_name: simswarm-temporal
    restart: unless-stopped
    environment:
      - DB=postgres12
      - DB_PORT=5432
      - POSTGRES_USER=temporal
      - POSTGRES_PWD=${TEMPORAL_DB_PASSWORD}
      - POSTGRES_SEEDS=temporal-db
      - DEFAULT_NAMESPACE=fishcloud
    depends_on:
      temporal-db:
        condition: service_healthy
    ports:
      - "127.0.0.1:7233:7233"
    healthcheck:
      test: ["CMD-SHELL", "tctl cluster health | grep SERVING"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s

  temporal-worker:
    image: fishcloud-app
    container_name: simswarm-temporal-worker
    restart: unless-stopped
    env_file: .env
    environment:
      - DATABASE_URL=postgresql+asyncpg://fishcloud:${POSTGRES_PASSWORD}@db:5432/fishcloud
      - REDIS_URL=redis://redis:6379/0
      - TEMPORAL_ADDRESS=temporal:7233
      - TEMPORAL_NAMESPACE=fishcloud
    depends_on:
      db:
        condition: service_healthy
      temporal:
        condition: service_healthy
    command: python -m saas.workflows.worker
    security_opt:
      - no-new-privileges:true
```

Find the `volumes:` block at the bottom of the file and add `temporaldata:` alongside `pgdata`:

```yaml
volumes:
  pgdata:
  temporaldata:
```

- [ ] **Step 2: Add `TEMPORAL_DB_PASSWORD` to `.env.example`**

If `.env.example` exists, add a line:

```
TEMPORAL_DB_PASSWORD=replace-with-a-strong-value
```

If it doesn't exist, skip — operator will configure via deploy scripts.

- [ ] **Step 3: Validate compose file syntax**

Run: `docker compose config > /dev/null`

Expected: exits 0 (no output means the file parses correctly).

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml
[ -f .env.example ] && git add .env.example
git commit -m "infra(temporal): add temporal-server, temporal-db, temporal-worker services"
```

---

### Task 16: `generate_report_task` terminal-status guard

**Files:**
- Modify: `saas/jobs/tasks_report.py`

- [ ] **Step 1: Locate and read the current task**

Run: `grep -n "def generate_report_task\|def _generate_report\|@celery_app.task" saas/jobs/tasks_report.py`

Note the function signature line number.

- [ ] **Step 2: Write failing test**

Append to `tests/test_jobs_tasks_report.py` (create the file if it doesn't exist):

```python
from unittest.mock import patch

import pytest


def test_generate_report_task_skips_terminal_job():
    from saas.jobs.tasks_report import generate_report_task

    with patch("saas.jobs.persistence._get_job_status", return_value="COMPLETED") as mock_status:
        result = generate_report_task(job_id=99, user_id="u1")

    mock_status.assert_called_once_with(99)
    assert result == {"job_id": 99, "status": "skipped_terminal"}


def test_generate_report_task_proceeds_for_reporting_job():
    from saas.jobs.tasks_report import generate_report_task

    with patch("saas.jobs.persistence._get_job_status", return_value="REPORTING"), \
         patch("saas.jobs.tasks_report._run_report_generation") as mock_run:
        mock_run.return_value = {"job_id": 99, "status": "completed"}
        result = generate_report_task(job_id=99, user_id="u1")

    mock_run.assert_called_once()
    assert result["status"] == "completed"
```

Note: the second test assumes the task body can be wrapped behind a helper like `_run_report_generation`. If the existing task body is inline, refactor the body into `_run_report_generation(job_id, user_id)` as part of step 3.

- [ ] **Step 3: Run test to verify fails**

Run: `pytest tests/test_jobs_tasks_report.py -v`

Expected: FAIL on first test (guard doesn't exist).

- [ ] **Step 4: Add the guard + refactor**

Edit `saas/jobs/tasks_report.py`. Rename the existing task body to a helper function `_run_report_generation(job_id, user_id)` and restructure the task entrypoint:

```python
@celery_app.task(name="fishcloud.generate_report")
def generate_report_task(job_id: int, user_id: str) -> dict:
    """Generate the external report for a completed sim.

    Idempotency guard: if the job is already in a terminal state, skip —
    this prevents double-generation when upload_and_finalize is retried
    after a transient failure mid-way through its work.
    """
    from saas.jobs.persistence import _get_job_status

    current_status = _get_job_status(job_id)
    if current_status in ("COMPLETED", "FAILED", "REFUNDED"):
        logger.info(
            "report.skipping_terminal job_id=%d status=%s",
            job_id, current_status,
        )
        return {"job_id": job_id, "status": "skipped_terminal"}

    return _run_report_generation(job_id, user_id)


def _run_report_generation(job_id: int, user_id: str) -> dict:
    """Verbatim relocation of the previous `generate_report_task` body.
    Copy every line of the original function body into this helper
    without modification. Do not change imports, log lines, or return
    values — this refactor must preserve current behavior exactly.
    """
    # Original body goes here verbatim.
```

- [ ] **Step 5: Run tests to verify pass**

Run: `pytest tests/test_jobs_tasks_report.py -v`

Expected: PASS both tests.

Also run full suite: `pytest -x -q`. Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add saas/jobs/tasks_report.py tests/test_jobs_tasks_report.py
git commit -m "fix(jobs): guard generate_report_task against double-generation"
```

---

### Task 17: Swap API dispatch from Celery to Temporal

**Files:**
- Modify: `saas/jobs/api.py:98-125`

- [ ] **Step 1: Write failing test**

Append to `tests/test_jobs_api.py` (or wherever `POST /jobs` is tested):

```python
@pytest.mark.asyncio
async def test_create_job_starts_temporal_workflow(
    client, auth_headers, funded_user, seeded_routing,
):
    """POST /jobs must start a Temporal workflow (not a Celery task)."""
    from unittest.mock import AsyncMock, patch

    fake_handle = AsyncMock()
    fake_handle.id = "sim-42"
    fake_handle.result_run_id = "run-abc"
    fake_client = AsyncMock()
    fake_client.start_workflow = AsyncMock(return_value=fake_handle)

    with patch(
        "saas.workflows.client.get_temporal_client",
        return_value=fake_client,
    ):
        resp = await client.post(
            "/jobs",
            json={
                "seed_text": "x", "goal": "y",
                "tier": "small", "enrich_web": False,
            },
            headers=auth_headers,
        )
    assert resp.status_code == 201
    fake_client.start_workflow.assert_called_once()
    kwargs = fake_client.start_workflow.call_args.kwargs
    assert kwargs["id"].startswith("sim-")
    assert kwargs["task_queue"] == "sim-queue"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_jobs_api.py -v -k test_create_job_starts_temporal_workflow`

Expected: FAIL — still dispatching to Celery.

- [ ] **Step 3: Swap the dispatch path in api.py**

Edit `saas/jobs/api.py`. Replace the block from `# 4. Dispatch to Celery` through `job.celery_task_id = task_result.id` (lines 98–123) with:

```python
    # 4. Dispatch to Temporal
    from saas.workflows.client import get_temporal_client, SIM_TASK_QUEUE
    from saas.workflows.sim_workflow import SimulationWorkflow
    from saas.workflows.types import SimParams

    sim_params = SimParams(
        job_id=job.id, user_id=user_id,
        seed_text=body.seed_text, goal=body.goal, tier=body.tier.value,
        model_id=routing.model_id, gpu_type=routing.gpu_type,
        max_rounds=routing.max_rounds, vllm_args=routing.vllm_args or "",
        llm_api_key=os.getenv("LLM_API_KEY", "not-needed"),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        credits_charged=credits,
        enrich_web=body.enrich_web,
        forecast_days=body.forecast_days,
        target_agents=routing.target_agents,
        upload_urls=upload_urls,
    )

    try:
        temporal_client = await get_temporal_client()
        handle = await temporal_client.start_workflow(
            SimulationWorkflow.run,
            sim_params,
            id=f"sim-{job.id}",
            task_queue=SIM_TASK_QUEUE,
        )
    except Exception:
        await session.rollback()
        raise HTTPException(status_code=500, detail="Failed to queue simulation job")

    # 5. Store workflow identity and commit
    job.workflow_id = handle.id
    job.workflow_run_id = handle.result_run_id
    await session.commit()
    await session.refresh(job)

    return job
```

Remove the now-unused `run_simulation_task` import at the top of `api.py` (search for it; remove only that import).

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_jobs_api.py -v`

Expected: the new test passes. Existing `/jobs` tests that mocked `run_simulation_task.delay` will now fail — update them to mock `get_temporal_client` (mirror the fake in step 1).

- [ ] **Step 5: Run full suite**

Run: `pytest -x -q`

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add saas/jobs/api.py tests/test_jobs_api.py
git commit -m "feat(api): dispatch sim jobs via temporal SimulationWorkflow"
```

---

### Task 18: Delete `recover_stale_jobs` beat + worker_ready hook

**Files:**
- Modify: `saas/workers/celery_app.py:34-65`

- [ ] **Step 1: Remove the beat schedule entry**

Edit `saas/workers/celery_app.py`. In the `beat_schedule` dict, delete the `"recover-stale-jobs"` key:

```python
beat_schedule={
    "cleanup-orphaned-pods": {
        "task": "fishcloud.cleanup_orphaned_pods",
        "schedule": 600.0,
    },
    # "recover-stale-jobs" entry removed — Temporal owns workflow liveness
    "prune-error-events": {
        "task": "fishcloud.prune_error_events",
        "schedule": 86400.0,
    },
},
```

- [ ] **Step 2: Remove the worker_ready recovery call**

In the same file, remove the line `celery_app.send_task("fishcloud.recover_stale_jobs")` from `on_worker_ready`. Keep the dep-check portion of the handler.

- [ ] **Step 3: Run tests**

Run: `pytest -x -q`

Expected: all pass (the beat change is config, not covered by tests; the dep-check portion remains).

- [ ] **Step 4: Commit**

```bash
git add saas/workers/celery_app.py
git commit -m "refactor(workers): remove recover_stale_jobs beat + worker_ready hook"
```

---

### Task 19: Delete recovery/resume modules

**Files:**
- Delete: `saas/jobs/recovery.py`
- Delete: `saas/jobs/recovery_utils.py`
- Delete: `saas/jobs/recovery_reporting.py`
- Delete: `saas/jobs/tasks_resume.py`
- Modify: `saas/jobs/tasks.py` (remove `run_simulation_task` + idempotency preamble + the re-export of `resume_simulation_task`)
- Modify: `saas/jobs/runner.py` (remove `resume()` method)
- Modify: `saas/jobs/persistence.py` + variants (remove `_claim_resume`, `_release_resume` if present; keep everything else)

- [ ] **Step 1: Delete the files**

```bash
rm saas/jobs/recovery.py saas/jobs/recovery_utils.py saas/jobs/recovery_reporting.py saas/jobs/tasks_resume.py
```

- [ ] **Step 2: Prune `saas/jobs/tasks.py`**

Edit `saas/jobs/tasks.py`:

- Remove `from saas.jobs.tasks_resume import resume_simulation_task  # noqa: F401 — re-export`
- Remove `from saas.jobs.recovery import recover_stale_jobs as _recover_stale_jobs_impl`
- Delete the entire `run_simulation_task` function (the `@celery_app.task(name="fishcloud.run_simulation", ...)` decorated function and its body — lines 37–260).
- Delete the `@celery_app.task(name="fishcloud.recover_stale_jobs")` wrapper if present.

The `cleanup_orphaned_pods` task wrapper stays.

- [ ] **Step 3: Prune `saas/jobs/runner.py`**

Remove the `resume()` method (lines 153–229) from the `JobRunner` class. The class still has `run()` which is now unused by the deleted Celery path — since nothing calls it anymore, it can also be deleted. Verify with:

```bash
grep -rn "JobRunner\b" saas/ tests/
```

If the only references are the class definition + its own methods + the deleted `run_simulation_task` (which is gone), delete the entire file `saas/jobs/runner.py`.

Otherwise keep only the methods still referenced.

- [ ] **Step 4: Prune persistence re-exports**

If `_claim_resume` / `_release_resume` existed (from the earlier resume-dedup refactor), they're no longer used. Remove them from `saas/jobs/persistence.py` and any sibling module that defined them.

Run: `grep -rn "_claim_resume\|_release_resume" saas/ tests/`

Expected: no references outside the file defining them. Delete the definitions.

- [ ] **Step 5: Fix any lingering imports**

Run the import check:

```bash
python -c "import saas.main"
python -c "from saas.workers.celery_app import celery_app; import saas.jobs.tasks"
```

Fix any `ImportError`s by removing the offending import line.

- [ ] **Step 6: Run full suite**

Run: `pytest -x -q`

Expected: all pass. Tests that exercised `run_simulation_task`, `resume_simulation_task`, `recover_stale_jobs` should be deleted, not fixed — those code paths no longer exist. Delete those test files:

```bash
# Identify them first:
grep -lrn "run_simulation_task\|resume_simulation_task\|recover_stale_jobs" tests/
# Then delete any test file whose only purpose was testing the deleted code.
```

- [ ] **Step 7: Commit**

```bash
git add -u
git commit -m "refactor(jobs): delete recovery, resume, run_simulation_task — replaced by temporal"
```

---

### Task 20: Local smoke test — full workflow end-to-end

**Files:** none (operational verification)

- [ ] **Step 1: Bring up the full stack locally**

```bash
docker compose build
docker compose up -d db redis temporal-db temporal temporal-worker celery app
```

Wait for health: `docker compose ps` — all services `healthy` or `running`.

- [ ] **Step 2: Run Alembic migration**

```bash
docker compose exec app alembic -c saas/alembic.ini upgrade head
```

Expected: migration `add_workflow_columns` applied.

- [ ] **Step 3: Inspect Temporal**

```bash
docker compose exec temporal tctl namespace list
docker compose exec temporal tctl --ns fishcloud workflow list
```

Expected: `fishcloud` namespace exists, workflow list empty.

- [ ] **Step 4: Dispatch a sim via the API**

Use the test account (from memory reference) or via curl with a bearer token. Submit a `small` tier sim with `enrich_web=false` and a short seed.

- [ ] **Step 5: Watch the workflow**

```bash
docker compose exec temporal tctl --ns fishcloud workflow show --workflow_id sim-<job_id>
```

Expected: activities fire in order — `provision_pod` → `wait_for_worker_health` → `submit_and_poll` → `upload_and_finalize` → `terminate_pod`.

- [ ] **Step 6: Verify DB state**

```bash
docker compose exec db psql -U fishcloud -d fishcloud -c \
  "SELECT id, status, pod_id, workflow_id, workflow_run_id FROM simulation_jobs ORDER BY id DESC LIMIT 1;"
```

Expected: `workflow_id = sim-<job_id>`, `workflow_run_id` populated, `status` transitioning PROVISIONING → RUNNING → REPORTING → COMPLETED.

- [ ] **Step 7: Kill the temporal-worker mid-sim and verify replay**

```bash
docker compose restart temporal-worker
```

Expected: the workflow continues after the worker comes back. Temporal replays from the last-persisted event. Check `tctl workflow show` again — history entries resume after the restart.

- [ ] **Step 8: No commit — this is verification only**

If anything fails, return to the specific task. If all pass, proceed to Task 21.

---

### Task 21: Deploy to production

**Files:** none (operational)

- [ ] **Step 1: Push to main**

```bash
git push origin main
```

Triggers GitHub Actions deploy (`.github/workflows/deploy.yml`) to the Hetzner VPS.

- [ ] **Step 2: Watch the deploy**

```bash
gh run watch
```

Expected: build + deploy both green. Alembic migration runs as part of deploy.

- [ ] **Step 3: Post-deploy verification on server**

```bash
ssh -i ~/.ssh/simswarm_deploy root@178.156.236.185 \
  "cd /opt/fishcloud && docker compose ps"
```

Expected: `simswarm-temporal`, `simswarm-temporal-db`, `simswarm-temporal-worker` all running.

```bash
ssh -i ~/.ssh/simswarm_deploy root@178.156.236.185 \
  "cd /opt/fishcloud && docker compose exec -T temporal tctl cluster health"
```

Expected: `SERVING`.

- [ ] **Step 4: Dispatch a smoke sim on production**

Via the test account (from the `reference_test_account` memory), submit a `small` tier sim. Watch logs:

```bash
ssh -i ~/.ssh/simswarm_deploy root@178.156.236.185 \
  "cd /opt/fishcloud && docker compose logs -f temporal-worker" | head -200
```

Expected: activity-ordering log lines, workflow completes, sim row transitions to COMPLETED.

- [ ] **Step 5: Verify no stuck sims**

```bash
ssh -i ~/.ssh/simswarm_deploy root@178.156.236.185 \
  "cd /opt/fishcloud && docker compose exec -T db psql -U fishcloud -d fishcloud -c \\
   \"SELECT id, status, created_at, workflow_id FROM simulation_jobs WHERE status IN ('PENDING', 'PROVISIONING', 'RUNNING', 'REPORTING');\""
```

Expected: either empty, or a live sim with a valid `workflow_id`. No sims with `workflow_id IS NULL` in a non-terminal status.

- [ ] **Step 6: No commit — deploy is via CI**

---

### Follow-Up (Separate Plan)

Deliberately out of scope for this plan so the current work has a clear "done" bar:

1. **Drop deprecated columns** (`celery_task_id`, `resume_task_id`, `last_heartbeat`, `retry_count`) via a second Alembic migration after enough production data confirms the new path is healthy.
2. **Tune the three conservative timeouts** (`upload_and_finalize=10min`, `terminate_pod=2min`, `refund_credits=30s`) based on observed p99 from real workflow data.
3. **Workflow-failure alert.** Wire a listener that emits to the existing `send_orphan_alert` channel on any `SimulationWorkflow` execution that ends in `FAILED` state. Options: periodic short beat task running `tctl --ns fishcloud workflow list --query "ExecutionStatus='Failed'"`, or a Temporal Update handler pushing events out.
4. **Decide whether to fold `generate_report_task` into the workflow** (spec open question #3).
