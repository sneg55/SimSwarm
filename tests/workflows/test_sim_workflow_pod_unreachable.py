"""Pod-unreachable retry semantics for the simulation workflow.

When poll_until_complete raises the pod_unreachable marker (proxy or
network blip between temporal-worker and the RunPod pod, beyond
MAX_CONSECUTIVE_POLL_FAILURES = 30 polls × 10s = 5min), the workflow
must:

1. NOT terminate the pod — the pod itself is almost always fine;
   the issue is on the path between us and it.
2. Sleep briefly, then re-run submit_and_poll against the same pod.
   The activity is idempotent: on re-entry it checks /status and
   resumes polling if the pod is still running/completed, so no
   sim rounds are lost.
3. Cap retries at POD_UNREACHABLE_MAX_RETRIES so a permanent network
   partition can't loop forever — the saga eventually fires.

Sim 149 (bitcoin, 2026-05-15) lost a near-completed run to a ~50s proxy
blip on the old 5-failure threshold; this PR raises in-activity tolerance
to ~5min AND adds workflow-level retry so a longer blip still survives.
"""
from __future__ import annotations

import uuid

import pytest
from temporalio import activity
from temporalio.exceptions import ApplicationError
from temporalio.worker import Worker

from saas.constants.tiers import POD_UNREACHABLE_MARKER
from saas.workflows.client import SIM_TASK_QUEUE
from saas.workflows.types import PodInfo, SimParams


def _params(job_id: int = 800) -> SimParams:
    return SimParams(
        job_id=job_id, user_id="u1", seed_text="s", goal="g",
        tier="small", model_id="m", gpu_type="L40S", max_rounds=15,
        vllm_args="", llm_api_key="k",
    )


@pytest.mark.asyncio
async def test_pod_unreachable_retries_same_pod(temporal_env):
    """First submit_and_poll raises pod_unreachable; workflow retries
    against the SAME pod (no terminate, no re-provision), succeeds."""
    from saas.workflows.sim_workflow import SimulationWorkflow

    call_log: list[str] = []
    provision_count = {"n": 0}
    submit_count = {"n": 0}

    @activity.defn(name="fishcloud.enrich_seed")
    async def _enrich(a, b, c):
        return a

    @activity.defn(name="fishcloud.derive_markets")
    async def _markets(a, b, c, d):
        return []

    @activity.defn(name="fishcloud.provision_pod")
    async def _provision(a, b):
        provision_count["n"] += 1
        call_log.append(f"provision#{provision_count['n']}")
        return PodInfo(id=f"pod-{provision_count['n']}")

    @activity.defn(name="fishcloud.wait_for_worker_health")
    async def _health(pod_id: str):
        call_log.append(f"health({pod_id})")

    @activity.defn(name="fishcloud.submit_and_poll")
    async def _submit(pod_id, params_arg, markets_arg):
        submit_count["n"] += 1
        call_log.append(f"submit#{submit_count['n']}({pod_id})")
        if submit_count["n"] == 1:
            raise ApplicationError(
                f"{POD_UNREACHABLE_MARKER}: 30 consecutive /status poll failures",
            )
        return {
            "pod_id": pod_id, "provision_seconds": 1, "pipeline_seconds": 1,
            "sim_data_uploaded": True, "status": "completed",
        }

    @activity.defn(name="fishcloud.upload_and_finalize")
    async def _upload(a, b, c):
        call_log.append("upload")

    @activity.defn(name="fishcloud.terminate_pod")
    async def _terminate(pod_id: str):
        call_log.append(f"terminate({pod_id})")

    @activity.defn(name="fishcloud.mark_failed")
    async def _mark_failed(a, b):
        call_log.append("mark_failed")

    activities = [
        _enrich, _markets, _provision, _health, _submit,
        _upload, _terminate, _mark_failed,
    ]

    async with Worker(
        temporal_env.client, task_queue=SIM_TASK_QUEUE,
        workflows=[SimulationWorkflow], activities=activities,
    ):
        handle = await temporal_env.client.start_workflow(
            SimulationWorkflow.run, _params(),
            id=f"sim-pu-{uuid.uuid4()}", task_queue=SIM_TASK_QUEUE,
        )
        await handle.result()

    # SAME pod across both submit attempts — no swap
    assert provision_count["n"] == 1, (
        f"expected one provision (no pod swap); got {provision_count['n']}. "
        f"call_log={call_log}"
    )
    assert submit_count["n"] == 2, "expected submit_and_poll retried once"
    assert call_log.count("submit#1(pod-1)") == 1
    assert call_log.count("submit#2(pod-1)") == 1
    # No mid-loop terminate before retry
    assert "terminate(pod-1)" not in call_log[:call_log.index("submit#2(pod-1)")]
    # Final state: success path
    assert "upload" in call_log
    assert "mark_failed" not in call_log


@pytest.mark.asyncio
async def test_pod_unreachable_exhausts_budget_then_marks_failed(temporal_env):
    """Every submit_and_poll attempt trips pod_unreachable — workflow
    gives up after POD_UNREACHABLE_MAX_RETRIES, marks failed, raises."""
    from saas.workflows.sim_workflow import SimulationWorkflow

    call_log: list[str] = []

    @activity.defn(name="fishcloud.enrich_seed")
    async def _enrich(a, b, c):
        return a

    @activity.defn(name="fishcloud.derive_markets")
    async def _markets(a, b, c, d):
        return []

    @activity.defn(name="fishcloud.provision_pod")
    async def _provision(a, b):
        return PodInfo(id="pod-1")

    @activity.defn(name="fishcloud.wait_for_worker_health")
    async def _health(pod_id: str):
        pass

    @activity.defn(name="fishcloud.submit_and_poll")
    async def _submit(pod_id, params_arg, markets_arg):
        call_log.append("submit")
        raise ApplicationError(f"{POD_UNREACHABLE_MARKER}: 30 poll failures")

    @activity.defn(name="fishcloud.upload_and_finalize")
    async def _upload(a, b, c):
        call_log.append("upload")

    @activity.defn(name="fishcloud.terminate_pod")
    async def _terminate(pod_id: str):
        call_log.append("terminate")

    @activity.defn(name="fishcloud.mark_failed")
    async def _mark_failed(a, b):
        call_log.append("mark_failed")

    activities = [
        _enrich, _markets, _provision, _health, _submit,
        _upload, _terminate, _mark_failed,
    ]

    async with Worker(
        temporal_env.client, task_queue=SIM_TASK_QUEUE,
        workflows=[SimulationWorkflow], activities=activities,
    ):
        handle = await temporal_env.client.start_workflow(
            SimulationWorkflow.run, _params(),
            id=f"sim-pu-fail-{uuid.uuid4()}", task_queue=SIM_TASK_QUEUE,
        )
        with pytest.raises(Exception):
            await handle.result()

    # POD_UNREACHABLE_MAX_RETRIES = 2 → 3 total attempts before giving up
    assert call_log.count("submit") == 3
    assert "mark_failed" in call_log
    assert "upload" not in call_log
