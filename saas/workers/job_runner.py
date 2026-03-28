"""Job runner: bridges Celery tasks to GPU provider + MiroFish pipeline."""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass

import httpx

from saas.gpu.provider import GPUProvider, GPUProviderConfig

logger = logging.getLogger(__name__)

TIER_TIMEOUTS: dict[str, int] = {
    "small": 2700,
    "medium": 18000,
    "large": 43200,
}

WORKER_IMAGE_REPO = "ghcr.io/sneg55/simswarm-worker"
WORKER_IMAGE_DEFAULT_TAG = "v20260327155910"


def get_worker_image() -> str:
    """Return worker Docker image, preferring WORKER_IMAGE_TAG env var."""
    tag = os.getenv("WORKER_IMAGE_TAG", WORKER_IMAGE_DEFAULT_TAG)
    return f"{WORKER_IMAGE_REPO}:{tag}"

TIER_MAX_COST_USD: dict[str, float] = {
    "small": 1.50,
    "medium": 4.00,
    "large": 8.00,
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
            "LLM_BASE_URL": "http://localhost:8000/v1",
            "LLM_MODEL_NAME": self.model_id,
            "ZEP_API_KEY": self.zep_api_key,
            "OASIS_DEFAULT_MAX_ROUNDS": str(self.max_rounds),
            # Used by start.sh to configure vLLM server
            "MODEL_ID": self.model_id,
            "VLLM_ARGS": self.vllm_args or "--max-model-len 32768",
        }


def _infer_pipeline_stage(log_lines: list[str]) -> int | None:
    """Map worker log lines to a pipeline stage number (1-5)."""
    log_text = " ".join(log_lines)
    if "report" in log_text.lower():
        return 5
    if "Running simulation" in log_text or "round=" in log_text:
        return 4
    if "preparing" in log_text:
        return 3
    if "Building" in log_text:
        return 2
    if "Generating ontology" in log_text:
        return 1
    return None


class JobRunner:
    """Manages the full lifecycle of a simulation job on a GPU instance."""

    def __init__(self, gpu_provider: GPUProvider, stage_callback=None):
        self.gpu_provider = gpu_provider
        # Optional async callable(job_id, stage) invoked when pipeline_stage changes
        self._stage_callback = stage_callback

    async def run(self, config: JobConfig) -> dict:
        """Provision a GPU, run the pipeline, then terminate the instance.

        Enforces the tier timeout as a hard upper bound on the entire job.
        """
        gpu_config = GPUProviderConfig(
            gpu_type=config.gpu_type,
            docker_image=get_worker_image(),
            max_cost_per_hour_usd=TIER_MAX_COST_USD.get(config.tier, 4.00),
            timeout_seconds=config.timeout_seconds,
            env_vars=config.to_mirofish_env(),
        )

        # Mark job as provisioning so the frontend can show GPU spin-up status
        if self._stage_callback is not None:
            try:
                await self._stage_callback(config.job_id, 0)
            except Exception:
                pass

        timeout = config.timeout_seconds
        logger.info(f"Job {config.job_id}: starting with {timeout}s tier timeout ({config.tier})")

        try:
            return await asyncio.wait_for(
                self._run_inner(gpu_config, config), timeout=timeout
            )
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"Job {config.job_id} exceeded {config.tier} tier timeout of {timeout}s"
            )

    async def _run_inner(self, gpu_config, config: JobConfig) -> dict:
        """Inner run method wrapped by the tier timeout."""
        import time
        provision_start = time.monotonic()
        instance = await self.gpu_provider.provision(gpu_config)
        provision_seconds = int(time.monotonic() - provision_start)
        pod_id = instance.instance_id
        logger.info(
            "job.gpu_provisioned job_id=%d pod_id=%s provision_seconds=%d",
            config.job_id, pod_id, provision_seconds,
            extra={"event": "gpu_provisioned", "job_id": config.job_id,
                   "pod_id": pod_id, "elapsed_s": provision_seconds},
        )

        try:
            pipeline_start = time.monotonic()
            result = await self._execute_pipeline(instance.instance_id, config)
            pipeline_seconds = int(time.monotonic() - pipeline_start)
            result["pod_id"] = pod_id
            result["provision_seconds"] = provision_seconds
            result["pipeline_seconds"] = pipeline_seconds
            return result
        except Exception as e:
            logger.error(f"Pipeline failed for pod {instance.instance_id}: {e}")
            try:
                worker_url = f"https://{instance.instance_id}-5000.proxy.runpod.net"
                async with httpx.AsyncClient(timeout=10) as client:
                    status_resp = await client.get(f"{worker_url}/status")
                    if status_resp.status_code == 200:
                        logger.error(f"Worker status at failure: {status_resp.json()}")
            except Exception:
                logger.warning("Could not retrieve worker status before termination")
            raise
        finally:
            await self.gpu_provider.terminate(instance.instance_id)

    async def _log_worker_output(self, worker_url: str, source: str = "all", tail: int = 20) -> None:
        """Pull recent logs from the worker pod and emit them."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{worker_url}/logs?tail={tail}&source={source}")
                if resp.status_code == 200:
                    data = resp.json()
                    for line in data.get("lines", []):
                        logger.info(f"  [{source}] {line}")
        except Exception:
            pass

    async def _execute_pipeline(self, instance_id: str, config: JobConfig) -> dict:
        """Execute the MiroFish pipeline via the worker pod's HTTP API.

        Steps:
          1. Poll /health until the worker API (and vLLM) is ready
          2. POST /job with seed_text, goal, max_rounds — blocks until complete
          3. Return report + chat_log to be saved in the DB
        """
        worker_url = f"https://{instance_id}-5000.proxy.runpod.net"

        # ------------------------------------------------------------------
        # 1. Wait for worker API to be ready (vLLM model load takes ~2-5 min)
        # ------------------------------------------------------------------
        import time
        health_start = time.monotonic()
        logger.info(f"Waiting for worker API at {worker_url}/health ...")
        for attempt in range(180):  # 15 min max (180 * 5s)
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get(f"{worker_url}/health")
                    if resp.status_code == 200:
                        elapsed = int(time.monotonic() - health_start)
                        health_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                        vllm_ready = health_data.get("vllm_ready", "?")
                        logger.info(
                            f"Worker API ready in {elapsed}s (vllm_ready={vllm_ready})",
                            extra={"event": "health_ready", "elapsed_s": elapsed},
                        )
                        break
                    elif attempt % 6 == 0:  # every 30s
                        elapsed = int(time.monotonic() - health_start)
                        try:
                            health_data = resp.json()
                            logger.info(f"Worker health: {health_data} ({elapsed}s elapsed)")
                        except Exception:
                            logger.info(f"Worker health: HTTP {resp.status_code} ({elapsed}s elapsed)")
                        # Pull vLLM logs while waiting — this is the key debugging info
                        await self._log_worker_output(worker_url, source="vllm", tail=20)
            except httpx.ConnectError:
                if attempt % 12 == 0:  # every 60s
                    elapsed = int(time.monotonic() - health_start)
                    logger.info(f"Worker not reachable yet ({elapsed}s elapsed, attempt {attempt + 1}/180)")
            except Exception as e:
                if attempt % 12 == 0:
                    elapsed = int(time.monotonic() - health_start)
                    logger.info(f"Worker health check: {type(e).__name__} ({elapsed}s elapsed)")
            await asyncio.sleep(5)
        else:
            elapsed = int(time.monotonic() - health_start)
            # Dump full logs before raising — critical for debugging vLLM failures
            logger.error(f"Worker health timeout after {elapsed}s — dumping vLLM and pipeline logs:")
            await self._log_worker_output(worker_url, source="vllm", tail=50)
            await self._log_worker_output(worker_url, source="pipeline", tail=20)
            raise TimeoutError(f"Worker API at {worker_url} did not become ready after {elapsed}s")

        # ------------------------------------------------------------------
        # 2. Submit job — returns immediately, pipeline runs in background
        # ------------------------------------------------------------------
        logger.info(f"Submitting job to {worker_url}/job (max_rounds={config.max_rounds})")
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{worker_url}/job", json={
                "seed_text": config.seed_text,
                "goal": config.goal,
                "max_rounds": config.max_rounds,
            })
            if resp.status_code != 200:
                try:
                    error_body = resp.json()
                    error_msg = error_body.get("error", resp.text[:2000])
                except Exception:
                    error_msg = resp.text[:2000]
                raise RuntimeError(f"Worker rejected job: {error_msg}")

        logger.info("Job accepted by worker, polling /status...")

        return await self._poll_until_complete(worker_url, instance_id, config)

    async def _poll_until_complete(
        self, worker_url: str, instance_id: str, config: JobConfig,
    ) -> dict:
        """Poll /status until completed or failed (up to tier timeout).

        Shared by _execute_pipeline (normal flow) and resume (reconnect flow).
        """
        import time
        poll_start = time.monotonic()
        poll_interval = 10
        max_polls = max(360, config.timeout_seconds // poll_interval)
        last_stage: int | None = None
        for poll in range(max_polls):
            await asyncio.sleep(poll_interval)
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    status_resp = await client.get(f"{worker_url}/status")
                    status_data = status_resp.json()
            except Exception as e:
                logger.warning(f"Status poll {poll + 1} failed: {e}")
                continue

            job_status = status_data.get("status", "unknown")
            log_lines: list[str] = []

            if poll % 6 == 0:  # Log every 60s
                elapsed = int(time.monotonic() - poll_start)
                logger.info(f"Pipeline status: {job_status} ({elapsed}s elapsed, poll {poll + 1}/{max_polls})")
                # Pull recent logs from the worker
                try:
                    async with httpx.AsyncClient(timeout=10) as log_client:
                        log_resp = await log_client.get(f"{worker_url}/logs?tail=10")
                        if log_resp.status_code == 200:
                            log_data = log_resp.json()
                            log_lines = log_data.get("lines", [])
                            for line in log_lines:
                                logger.info(f"  [worker] {line}")
                except Exception:
                    pass

            # Infer pipeline stage from logs and notify callback if changed
            stage = _infer_pipeline_stage(log_lines)
            if stage is not None and stage != last_stage:
                last_stage = stage
                logger.info(f"Pipeline stage updated to {stage}")
                if self._stage_callback is not None:
                    try:
                        await self._stage_callback(config.job_id, stage)
                    except Exception as cb_exc:
                        logger.warning(f"Stage callback failed: {cb_exc}")

            if job_status == "completed":
                result = status_data
                elapsed = int(time.monotonic() - poll_start)
                logger.info(
                    f"Pipeline completed in {elapsed}s!",
                    extra={"event": "pipeline_completed", "job_id": config.job_id,
                           "elapsed_s": elapsed},
                )
                break
            elif job_status == "failed":
                error_msg = status_data.get("error", "Unknown error")
                stdout = status_data.get("stdout", "")
                logger.error(f"Pipeline failed: {error_msg}")
                if stdout:
                    logger.error(f"Pipeline stdout: {stdout[:2000]}")
                raise RuntimeError(f"Worker pipeline failed: {error_msg}")
        else:
            raise TimeoutError(f"Pipeline did not complete within {max_polls * poll_interval}s")

        return {
            "job_id": config.job_id,
            "instance_id": instance_id,
            "report": result.get("report", ""),
            "chat_log": result.get("chat_log", "[]"),
            "graph_data": result.get("graph_data", "{}"),
            "status": "completed",
        }

    async def resume(self, pod_id: str, job_id: int) -> dict:
        """Reconnect to an existing pod and poll until complete.

        Used after worker restart to pick up jobs that were running on pods
        that are still alive.
        """
        worker_url = f"https://{pod_id}-5000.proxy.runpod.net"
        logger.info(
            "job.resuming job_id=%d pod_id=%s url=%s",
            job_id, pod_id, worker_url,
        )

        # Quick health check — is the pod actually responding?
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{worker_url}/status")
                status_data = resp.json()
                job_status = status_data.get("status", "unknown")
                logger.info("job.resume_status job_id=%d pod_status=%s", job_id, job_status)
        except Exception as e:
            raise RuntimeError(f"Cannot reach pod {pod_id} for resume: {e}")

        # If already completed, return result immediately
        if job_status == "completed":
            logger.info("job.resume_already_complete job_id=%d", job_id)
            return {
                "job_id": job_id,
                "instance_id": pod_id,
                "report": status_data.get("report", ""),
                "chat_log": status_data.get("chat_log", "[]"),
                "graph_data": status_data.get("graph_data", "{}"),
                "status": "completed",
            }

        if job_status == "failed":
            error_msg = status_data.get("error", "Unknown error")
            raise RuntimeError(f"Pod pipeline already failed: {error_msg}")

        if job_status == "idle":
            raise RuntimeError(f"Pod {pod_id} is idle — pipeline was never started or already reset")

        # Still running — create a minimal config for the polling loop
        minimal_config = type("MinimalConfig", (), {
            "job_id": job_id,
            "timeout_seconds": TIER_TIMEOUTS.get("medium", 18000),
        })()

        try:
            result = await self._poll_until_complete(worker_url, pod_id, minimal_config)
            return result
        finally:
            # Terminate pod after resume completes (success or failure)
            logger.info("job.resume_terminating pod_id=%s", pod_id)
            await self.gpu_provider.terminate(pod_id)
