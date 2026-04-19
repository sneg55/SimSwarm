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
            result_type=PodInfo,
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
                retry_policy=RetryPolicy(maximum_attempts=1),
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
