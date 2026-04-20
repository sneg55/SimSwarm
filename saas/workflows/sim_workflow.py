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
        # Phase 1: pre-GPU. Both activities are fail-soft on LLM misses but
        # DB/network exceptions can still exhaust their 2-attempt retry. No
        # pod exists yet, so a failure here bypasses the Phase 2 saga — we
        # need an explicit refund path before the workflow raises.
        try:
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
        except Exception as e:
            await workflow.execute_activity(
                "fishcloud.refund_credits",
                args=[
                    params.job_id, params.user_id,
                    params.credits_charged,
                    f"pre_gpu_failed: {str(e)[:4000]}",
                ],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=5),
            )
            raise

        # Phase 2: GPU lifecycle
        # Keep provision_pod's start_to_close_timeout strictly greater than
        # the provider's internal poll budget (MAX_POLL_ATTEMPTS * 5s = 600s)
        # so Temporal doesn't cancel mid-poll and race the provider's own
        # terminate path. Heartbeat timeout catches true hangs faster.
        #
        # BAD_HOST_MAX_RETRIES=1 gives two total provision attempts. If the
        # first host's vLLM is terminally broken (bad NVIDIA driver — RunPod
        # marks the pod healthy but torch.cuda.init() fails), wait_for_health
        # raises a non_retryable ApplicationError with "vLLM failed to start",
        # we tear the bad pod down, and re-provision once on a fresh host.
        BAD_HOST_MAX_RETRIES = 1
        pod: PodInfo | None = None
        try:
            for bad_host_attempt in range(BAD_HOST_MAX_RETRIES + 1):
                pod = await workflow.execute_activity(
                    "fishcloud.provision_pod",
                    args=[params, markets],
                    result_type=PodInfo,
                    start_to_close_timeout=timedelta(minutes=13),
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
                        retry_policy=RetryPolicy(maximum_attempts=2),
                    )
                    break  # healthy — leave the bad-host retry loop
                except Exception as wait_err:
                    # ApplicationError("vLLM failed to start ...") surfaces
                    # here wrapped in ActivityError; check the whole chain.
                    err_chain = str(wait_err)
                    cause = getattr(wait_err, "cause", None)
                    if cause is not None:
                        err_chain += " | " + str(cause)
                    is_bad_host = "vLLM failed to start" in err_chain
                    if is_bad_host and bad_host_attempt < BAD_HOST_MAX_RETRIES:
                        workflow.logger.warning(
                            "workflow.bad_host.retrying pod_id=%s attempt=%d",
                            pod.id, bad_host_attempt + 1,
                        )
                        await workflow.execute_activity(
                            "fishcloud.terminate_pod",
                            args=[pod.id],
                            start_to_close_timeout=timedelta(minutes=2),
                            retry_policy=RetryPolicy(maximum_attempts=5),
                        )
                        pod = None  # already terminated; outer finally must not re-try
                        continue
                    raise

            assert pod is not None  # loop always assigns before break/raise

            result = await workflow.execute_activity(
                "fishcloud.submit_and_poll",
                args=[pod.id, params, markets],
                start_to_close_timeout=timedelta(
                    seconds=TIER_TIMEOUTS.get(params.tier, 2700),
                ),
                heartbeat_timeout=timedelta(seconds=180),
                retry_policy=RetryPolicy(maximum_attempts=1),
            )

            # Cap retries so a permanent PG/MinIO outage can't strand a job
            # in RUNNING forever. 3 attempts covers transient blips; beyond
            # that the saga (refund + terminate) fires and the stale-job
            # detector will pick up anything truly unreachable.
            await workflow.execute_activity(
                "fishcloud.upload_and_finalize",
                args=[params.job_id, params.user_id, result],
                start_to_close_timeout=timedelta(minutes=10),
                heartbeat_timeout=timedelta(seconds=60),
                retry_policy=RetryPolicy(maximum_attempts=3),
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
            # Terminate the currently-held pod, if any. Bad-host retries
            # clear `pod` after their in-loop terminate, so this runs at
            # most once per successful provision.
            if pod is not None:
                await workflow.execute_activity(
                    "fishcloud.terminate_pod",
                    args=[pod.id],
                    start_to_close_timeout=timedelta(minutes=2),
                    retry_policy=RetryPolicy(maximum_attempts=5),
                )
