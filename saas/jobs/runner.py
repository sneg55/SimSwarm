"""Job runner: bridges Celery tasks to GPU provider + MiroShark pipeline."""
from __future__ import annotations

import asyncio
import logging

import httpx

from saas.gpu.provider import GPUProvider, GPUProviderConfig
from saas.constants.tiers import TIER_TIMEOUTS, TIER_MAX_COST_USD  # noqa: F401 — re-export
from saas.jobs.config import JobConfig, get_worker_image  # noqa: F401 — re-export
from saas.jobs.status import _extract_live_status  # noqa: F401 — re-export
from saas.jobs.pipeline import poll_until_complete
from saas.jobs.worker_http import submit_job, wait_for_worker_health

logger = logging.getLogger(__name__)


class JobRunner:
    """Manages the full lifecycle of a simulation job on a GPU instance."""

    def __init__(self, gpu_provider: GPUProvider, stage_callback=None,
                 pod_id_callback=None, heartbeat_callback=None,
                 status_callback=None):
        self.gpu_provider = gpu_provider
        # Optional async callable(job_id, stage) invoked when pipeline_stage changes
        self._stage_callback = stage_callback
        # Optional async callable(job_id, pod_id) invoked right after GPU provisioning
        self._pod_id_callback = pod_id_callback
        # Optional async callable(job_id) invoked periodically during polling
        self._heartbeat_callback = heartbeat_callback
        # Optional async callable(job_id, status) invoked once on PROVISIONING→RUNNING
        self._status_callback = status_callback

    async def run(self, config: JobConfig) -> dict:
        """Provision a GPU, run the pipeline, then terminate the instance.

        Provisioning runs with its own internal timeout (MAX_POLL_ATTEMPTS).
        The tier timeout wraps only pipeline execution, ensuring the finally
        block always has a valid pod_id to terminate.
        """
        gpu_config = GPUProviderConfig(
            gpu_type=config.gpu_type,
            docker_image=get_worker_image(),
            max_cost_per_hour_usd=TIER_MAX_COST_USD.get(config.tier, 4.00),
            timeout_seconds=config.timeout_seconds,
            env_vars=config.to_worker_env(),
            job_id=config.job_id,
        )

        if self._stage_callback is not None:
            try:
                await self._stage_callback(config.job_id, 0)
            except Exception:
                pass

        timeout = getattr(config, "_timeout_override", None) or config.timeout_seconds
        logger.info(f"Job {config.job_id}: starting with {timeout}s tier timeout ({config.tier})")

        return await self._run_inner(gpu_config, config, timeout)

    async def _run_inner(self, gpu_config, config: JobConfig, timeout: int | float) -> dict:
        """Provision GPU, run pipeline with tier timeout, guarantee teardown."""
        import time

        # Phase 1: Provision (own internal timeout via MAX_POLL_ATTEMPTS)
        # on_created fires as soon as the pod is created (before the ready-wait
        # loop) so cleanup can match the pod to a job and won't kill it as orphaned.
        async def _on_pod_created(pid):
            if self._pod_id_callback is not None:
                try:
                    await self._pod_id_callback(config.job_id, pid)
                except Exception:
                    logger.warning("Early pod_id_callback failed for job %d", config.job_id)

        provision_start = time.monotonic()
        instance = await self.gpu_provider.provision(gpu_config, on_created=_on_pod_created)
        provision_seconds = int(time.monotonic() - provision_start)
        pod_id = instance.instance_id
        logger.info(
            "job.gpu_provisioned job_id=%d pod_id=%s provision_seconds=%d",
            config.job_id, pod_id, provision_seconds,
            extra={"event": "gpu_provisioned", "job_id": config.job_id,
                   "pod_id": pod_id, "elapsed_s": provision_seconds},
        )

        # Phase 2: Pipeline (wrapped with tier timeout, teardown guaranteed)
        try:
            pipeline_start = time.monotonic()
            result = await asyncio.wait_for(
                self._execute_pipeline(pod_id, config),
                timeout=timeout,
            )
            pipeline_seconds = int(time.monotonic() - pipeline_start)
            result["pod_id"] = pod_id
            result["provision_seconds"] = provision_seconds
            result["pipeline_seconds"] = pipeline_seconds
            return result
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"Job {config.job_id} exceeded {config.tier} tier timeout of {timeout}s"
            )
        except Exception as e:
            logger.error(f"Pipeline failed for pod {pod_id}: {e}")
            try:
                worker_url = f"https://{pod_id}-5000.proxy.runpod.net"
                async with httpx.AsyncClient(timeout=10) as client:
                    status_resp = await client.get(f"{worker_url}/status")
                    if status_resp.status_code == 200:
                        logger.error(f"Worker status at failure: {status_resp.json()}")
            except Exception:
                logger.warning("Could not retrieve worker status before termination")
            raise
        finally:
            # Guard terminate() so a teardown failure (e.g. "pod not found to
            # terminate" when the pod is already gone) doesn't overwrite the
            # original pipeline exception — users need the real error, not the
            # cleanup error.
            try:
                await self.gpu_provider.terminate(pod_id)
            except Exception as term_exc:
                logger.warning(
                    "job.terminate_failed job_id=%d pod_id=%s error=%s",
                    config.job_id, pod_id, term_exc,
                )

    async def _execute_pipeline(self, instance_id: str, config: JobConfig) -> dict:
        """Execute the MiroShark pipeline via the worker pod's HTTP API.

        Steps:
          1. Poll /health until the worker API (and vLLM) is ready
          2. POST /job with seed_text, goal, max_rounds -- blocks until complete
          3. Return report + chat_log to be saved in the DB

        A single httpx.AsyncClient is reused for all HTTP requests to avoid
        connection churn (TLS handshake per request).
        """
        worker_url = f"https://{instance_id}-5000.proxy.runpod.net"

        async with httpx.AsyncClient(timeout=15) as client:
            await wait_for_worker_health(worker_url, client)
            await submit_job(worker_url, config, client)
            return await poll_until_complete(
                worker_url, instance_id, config, client=client,
                stage_callback=self._stage_callback,
                heartbeat_callback=self._heartbeat_callback,
                status_callback=self._status_callback,
            )

