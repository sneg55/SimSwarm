"""Circuit-breaker retry semantics for the simulation workflow.

When poll_until_complete trips the LLM error-rate circuit breaker mid-sim
(vLLM on this pod started returning timeouts on every chat call), the
workflow must terminate the bad pod, provision a fresh one, and retry
submit_and_poll exactly once. If the retry succeeds, the user gets a
real result instead of a failure.
"""
from __future__ import annotations

import uuid

import pytest
from temporalio import activity
from temporalio.exceptions import ApplicationError
from temporalio.worker import Worker

from saas.constants.tiers import LLM_CIRCUIT_BREAKER_MARKER
from saas.workflows.client import SIM_TASK_QUEUE
from saas.workflows.types import PodInfo, SimParams


def _params(job_id: int = 700) -> SimParams:
    return SimParams(
        job_id=job_id, user_id="u1", seed_text="s", goal="g",
        tier="small", model_id="m", gpu_type="L40S", max_rounds=15,
        vllm_args="", llm_api_key="k",
    )


@pytest.mark.asyncio
async def test_circuit_breaker_trip_swaps_pods_and_succeeds(temporal_env):
    """First pod trips the LLM circuit breaker; workflow tears it down,
    provisions a fresh pod, retries submit_and_poll, succeeds."""
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
            # First pod's vLLM degrades — pipeline trips the circuit breaker.
            # Pipeline raises RuntimeError; the activity rewraps as a Temporal
            # ApplicationError carrying the original message. The workflow
            # detects the marker via substring match on the exception chain.
            raise ApplicationError(
                f"{LLM_CIRCUIT_BREAKER_MARKER}: 18/20 LLM lines were errors over ~60s",
            )
        return {
            "pod_id": pod_id, "provision_seconds": 1, "pipeline_seconds": 1,
            "report": "ok", "chat_log": "[]", "graph_data": "{}",
            "structured": "{}", "sim_data_uploaded": True,
        }

    @activity.defn(name="fishcloud.upload_and_finalize")
    async def _upload(a, b, c):
        call_log.append("upload")

    @activity.defn(name="fishcloud.terminate_pod")
    async def _terminate(pod_id: str):
        call_log.append(f"terminate({pod_id})")

    @activity.defn(name="fishcloud.clear_pod_id")
    async def _clear_pod_id(job_id: int):
        call_log.append(f"clear_pod_id({job_id})")

    @activity.defn(name="fishcloud.mark_failed")
    async def _mark_failed(a, b):
        call_log.append("mark_failed")

    activities = [
        _enrich, _markets, _provision, _health, _submit,
        _upload, _terminate, _clear_pod_id, _mark_failed,
    ]

    async with Worker(
        temporal_env.client, task_queue=SIM_TASK_QUEUE,
        workflows=[SimulationWorkflow], activities=activities,
    ):
        handle = await temporal_env.client.start_workflow(
            SimulationWorkflow.run, _params(),
            id=f"sim-cb-{uuid.uuid4()}", task_queue=SIM_TASK_QUEUE,
        )
        await handle.result()

    assert provision_count["n"] == 2, (
        f"expected fresh pod after circuit breaker trip; got {provision_count['n']} "
        f"provisions. call_log={call_log}"
    )
    assert submit_count["n"] == 2, "expected submit_and_poll retried"
    # Bad pod torn down before second provision
    assert call_log.index("terminate(pod-1)") < call_log.index("provision#2")
    # Final state: success path
    assert "upload" in call_log
    assert "mark_failed" not in call_log


@pytest.mark.asyncio
async def test_circuit_breaker_exhausts_budget_then_marks_failed(temporal_env):
    """If both pods trip the circuit breaker, workflow gives up after one
    retry, marks the job failed, and propagates the failure."""
    from saas.workflows.sim_workflow import SimulationWorkflow

    call_log: list[str] = []
    provision_count = {"n": 0}

    @activity.defn(name="fishcloud.enrich_seed")
    async def _enrich(a, b, c):
        return a

    @activity.defn(name="fishcloud.derive_markets")
    async def _markets(a, b, c, d):
        return []

    @activity.defn(name="fishcloud.provision_pod")
    async def _provision(a, b):
        provision_count["n"] += 1
        return PodInfo(id=f"pod-{provision_count['n']}")

    @activity.defn(name="fishcloud.wait_for_worker_health")
    async def _health(pod_id: str):
        pass

    @activity.defn(name="fishcloud.submit_and_poll")
    async def _submit(pod_id, params_arg, markets_arg):
        call_log.append(f"submit({pod_id})")
        raise ApplicationError(
            f"{LLM_CIRCUIT_BREAKER_MARKER}: 15/15 LLM lines were errors",
        )

    @activity.defn(name="fishcloud.upload_and_finalize")
    async def _upload(a, b, c):
        call_log.append("upload")

    @activity.defn(name="fishcloud.terminate_pod")
    async def _terminate(pod_id: str):
        call_log.append(f"terminate({pod_id})")

    @activity.defn(name="fishcloud.clear_pod_id")
    async def _clear_pod_id(job_id: int):
        call_log.append(f"clear_pod_id({job_id})")

    @activity.defn(name="fishcloud.mark_failed")
    async def _mark_failed(a, b):
        call_log.append("mark_failed")

    activities = [
        _enrich, _markets, _provision, _health, _submit,
        _upload, _terminate, _clear_pod_id, _mark_failed,
    ]

    async with Worker(
        temporal_env.client, task_queue=SIM_TASK_QUEUE,
        workflows=[SimulationWorkflow], activities=activities,
    ):
        handle = await temporal_env.client.start_workflow(
            SimulationWorkflow.run, _params(),
            id=f"sim-cb-fail-{uuid.uuid4()}", task_queue=SIM_TASK_QUEUE,
        )
        with pytest.raises(Exception):
            await handle.result()

    assert provision_count["n"] == 2, "should swap once before giving up"
    assert call_log.count("submit(pod-1)") == 1
    assert call_log.count("submit(pod-2)") == 1
    assert "mark_failed" in call_log
    assert "upload" not in call_log
