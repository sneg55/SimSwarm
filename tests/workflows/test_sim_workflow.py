"""End-to-end tests for SimulationWorkflow using time-skipping Temporal env."""
from __future__ import annotations

import uuid

import pytest
from temporalio.worker import Worker

from saas.workflows.client import SIM_TASK_QUEUE
from saas.workflows.types import SimParams, PodInfo


def _params(job_id: int = 1) -> SimParams:
    return SimParams(
        job_id=job_id, user_id="u1", seed_text="s", goal="g",
        tier="small", model_id="m", gpu_type="L40S", max_rounds=15,
        vllm_args="", llm_api_key="k",
    )


@pytest.mark.asyncio
async def test_workflow_happy_path(temporal_env):
    """Run a full workflow with all activities mocked to succeed.

    Validates: activities are called in order; mark_failed is NOT called
    on success; terminate_pod IS called (finally block).
    """
    from saas.workflows.sim_workflow import SimulationWorkflow

    call_log: list[str] = []

    from temporalio import activity

    @activity.defn(name="fishcloud.enrich_seed")
    async def _enrich(a, b, c):
        call_log.append("enrich_seed")
        return a

    @activity.defn(name="fishcloud.derive_markets")
    async def _markets(a, b, c, d):
        call_log.append("derive_markets")
        return [{"name": "M1"}]

    @activity.defn(name="fishcloud.provision_pod")
    async def _provision(a, b):
        call_log.append("provision_pod")
        return PodInfo(id="pod-test")

    @activity.defn(name="fishcloud.wait_for_worker_health")
    async def _health(a):
        call_log.append("wait_for_worker_health")

    @activity.defn(name="fishcloud.submit_and_poll")
    async def _submit(a, b, c):
        call_log.append("submit_and_poll")
        return {
            "pod_id": a, "provision_seconds": 100, "pipeline_seconds": 700,
            "report": "", "chat_log": "[]",
            "graph_data": "{}", "structured": "{}",
            "sim_data_uploaded": True,
        }

    @activity.defn(name="fishcloud.upload_and_finalize")
    async def _upload(a, b, c):
        call_log.append("upload_and_finalize")

    @activity.defn(name="fishcloud.terminate_pod")
    async def _terminate(a):
        call_log.append("terminate_pod")

    @activity.defn(name="fishcloud.mark_failed")
    async def _mark_failed(a, b):
        call_log.append("mark_failed")

    activities = [_enrich, _markets, _provision, _health, _submit, _upload, _terminate, _mark_failed]

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

    # Happy path: mark_failed NOT called, terminate IS called
    assert "mark_failed" not in call_log
    assert "terminate_pod" in call_log
    # Order check — provision before pipeline
    assert call_log.index("provision_pod") < call_log.index("submit_and_poll")
    assert call_log.index("wait_for_worker_health") < call_log.index("submit_and_poll")
    assert call_log.index("submit_and_poll") < call_log.index("upload_and_finalize")


@pytest.mark.asyncio
async def test_workflow_marks_failed_when_pipeline_fails(temporal_env):
    """Pipeline activity raises — mark_failed + terminate must run."""
    from saas.workflows.sim_workflow import SimulationWorkflow
    from temporalio import activity

    call_log: list[str] = []

    @activity.defn(name="fishcloud.enrich_seed")
    async def _e(a, b, c):
        call_log.append("enrich")
        return a

    @activity.defn(name="fishcloud.derive_markets")
    async def _m(a, b, c, d):
        call_log.append("markets")
        return []

    @activity.defn(name="fishcloud.provision_pod")
    async def _p(a, b):
        call_log.append("provision")
        return PodInfo(id="pod-x")

    @activity.defn(name="fishcloud.wait_for_worker_health")
    async def _h(a):
        call_log.append("health")

    @activity.defn(name="fishcloud.submit_and_poll")
    async def _s(a, b, c):
        call_log.append("submit")
        raise RuntimeError("pipeline boom")

    @activity.defn(name="fishcloud.upload_and_finalize")
    async def _u(a, b, c):
        call_log.append("upload")

    @activity.defn(name="fishcloud.terminate_pod")
    async def _t(a):
        call_log.append("terminate")

    @activity.defn(name="fishcloud.mark_failed")
    async def _mf(a, b):
        call_log.append("mark_failed")

    async with Worker(
        temporal_env.client, task_queue=SIM_TASK_QUEUE,
        workflows=[SimulationWorkflow],
        activities=[_e, _m, _p, _h, _s, _u, _t, _mf],
    ):
        handle = await temporal_env.client.start_workflow(
            SimulationWorkflow.run, _params(),
            id=f"sim-fail-{uuid.uuid4()}", task_queue=SIM_TASK_QUEUE,
        )
        with pytest.raises(Exception):
            await handle.result()

    assert "upload" not in call_log     # never reached
    assert "mark_failed" in call_log    # failure marking fired
    assert "terminate" in call_log      # finally still runs
