"""Bad-host retry semantics for the simulation workflow.

Sim 125 landed on a RunPod host whose worker Flask never came up —
every /health poll returned 502 and /logs was also 502, so the
`_check_vllm_terminal_failure` marker path could never fire. The
workflow's bad-host retry only kicked in on the "vLLM failed to start"
marker, so silent hosts burned the full 15-min wait *twice* (activity
retry) and then failed without ever trying a fresh host.

These tests pin the contract: any failure from wait_for_worker_health
must be treated as a bad host and swap pods while the retry budget is
still available.
"""
from __future__ import annotations

import uuid

import pytest
from temporalio import activity
from temporalio.worker import Worker

from saas.workflows.client import SIM_TASK_QUEUE
from saas.workflows.types import SimParams, PodInfo


def _params(job_id: int = 500) -> SimParams:
    return SimParams(
        job_id=job_id, user_id="u1", seed_text="s", goal="g",
        tier="small", model_id="m", gpu_type="L40S", max_rounds=15,
        vllm_args="", llm_api_key="k",
    )


@pytest.mark.asyncio
async def test_silent_host_triggers_bad_host_retry(temporal_env):
    """First pod's /health never responds → workflow tears it down and
    provisions a fresh host before giving up."""
    from saas.workflows.sim_workflow import SimulationWorkflow

    call_log: list[str] = []
    provision_count = {"n": 0}

    @activity.defn(name="fishcloud.enrich_seed")
    async def _enrich(a, b, c):
        call_log.append("enrich")
        return a

    @activity.defn(name="fishcloud.derive_markets")
    async def _markets(a, b, c, d):
        call_log.append("markets")
        return []

    @activity.defn(name="fishcloud.provision_pod")
    async def _provision(a, b):
        provision_count["n"] += 1
        call_log.append(f"provision#{provision_count['n']}")
        return PodInfo(id=f"pod-{provision_count['n']}")

    @activity.defn(name="fishcloud.wait_for_worker_health")
    async def _health(pod_id: str):
        call_log.append(f"health({pod_id})")
        # First pod = silent host. Raise a plain RuntimeError with no
        # "vLLM failed to start" marker — exactly what sim 125 saw.
        if pod_id == "pod-1":
            raise RuntimeError("activity timed out")
        # Second pod comes up fine.

    @activity.defn(name="fishcloud.submit_and_poll")
    async def _submit(a, b, c):
        call_log.append("submit")
        return {
            "pod_id": a, "provision_seconds": 1, "pipeline_seconds": 1,
            "report": "", "chat_log": "[]", "graph_data": "{}",
            "structured": "{}", "sim_data_uploaded": True,
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
            id=f"sim-bad-{uuid.uuid4()}", task_queue=SIM_TASK_QUEUE,
        )
        await handle.result()

    assert provision_count["n"] == 2, (
        f"Expected two provision_pod calls (retry on fresh host); "
        f"got {provision_count['n']}. call_log={call_log}"
    )
    # Bad pod is torn down before the second provision
    assert call_log.index("terminate(pod-1)") < call_log.index("provision#2")
    # Workflow succeeded: upload fired, no mark_failed
    assert "upload" in call_log
    assert "mark_failed" not in call_log
