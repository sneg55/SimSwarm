"""Slow-pod marker triggers workflow-level pod swap (same shape as
LLM circuit breaker). Sim 148 (hormuz, SECURE L40S, 2026-05-15) was
the motivating case — would have been auto-killed at ~20 min instead
of needing manual cancel after 1h30m + ~$15 wasted GPU.
"""
from __future__ import annotations

import uuid

import pytest
from temporalio import activity
from temporalio.exceptions import ApplicationError
from temporalio.worker import Worker

from saas.constants.tiers import SLOW_POD_MARKER
from saas.workflows.client import SIM_TASK_QUEUE
from saas.workflows.types import PodInfo, SimParams


def _params(job_id: int = 900) -> SimParams:
    return SimParams(
        job_id=job_id, user_id="u1", seed_text="s", goal="g",
        tier="small", model_id="m", gpu_type="L40S", max_rounds=15,
        vllm_args="", llm_api_key="k", credits_charged=30,
    )


@pytest.mark.asyncio
async def test_slow_pod_marker_swaps_pods_and_succeeds(temporal_env):
    """First submit_and_poll raises slow_pod; workflow tears down the
    bad pod, provisions a fresh one, retries — succeeds. Same pattern
    as the LLM circuit breaker but a different signal (low rounds/min
    vs high error rate)."""
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
                f"{SLOW_POD_MARKER}: 0.22 rounds/min over ~1200s",
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

    @activity.defn(name="fishcloud.refund_credits")
    async def _refund(a, b, c, d):
        call_log.append("refund")

    activities = [
        _enrich, _markets, _provision, _health, _submit,
        _upload, _terminate, _refund,
    ]

    async with Worker(
        temporal_env.client, task_queue=SIM_TASK_QUEUE,
        workflows=[SimulationWorkflow], activities=activities,
    ):
        handle = await temporal_env.client.start_workflow(
            SimulationWorkflow.run, _params(),
            id=f"sim-sp-{uuid.uuid4()}", task_queue=SIM_TASK_QUEUE,
        )
        await handle.result()

    assert provision_count["n"] == 2, (
        f"expected fresh pod after slow_pod trip; got {provision_count['n']}. "
        f"call_log={call_log}"
    )
    assert submit_count["n"] == 2, "expected submit_and_poll retried on new pod"
    # Bad pod torn down before second provision (the slow_pod swap)
    assert call_log.index("terminate(pod-1)") < call_log.index("provision#2")
    assert "upload" in call_log
    assert "refund" not in call_log
