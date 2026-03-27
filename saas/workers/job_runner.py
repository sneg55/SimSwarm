"""Job runner: bridges Celery tasks to GPU provider + MiroFish pipeline."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import httpx

from saas.gpu.provider import GPUProvider, GPUProviderConfig

logger = logging.getLogger(__name__)

TIER_TIMEOUTS: dict[str, int] = {
    "small": 2700,
    "medium": 18000,
    "large": 43200,
}

WORKER_IMAGE = "ghcr.io/sneg55/fishcloud-worker:latest"

TIER_DOCKER_IMAGES: dict[str, str] = {
    "small": WORKER_IMAGE,
    "medium": WORKER_IMAGE,
    "large": WORKER_IMAGE,
}

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
        }


class JobRunner:
    """Manages the full lifecycle of a simulation job on a GPU instance."""

    def __init__(self, gpu_provider: GPUProvider):
        self.gpu_provider = gpu_provider

    async def run(self, config: JobConfig) -> dict:
        """Provision a GPU, run the pipeline, then terminate the instance."""
        gpu_config = GPUProviderConfig(
            gpu_type=config.gpu_type,
            docker_image=TIER_DOCKER_IMAGES.get(config.tier, "mirofish:latest"),
            max_cost_per_hour_usd=TIER_MAX_COST_USD.get(config.tier, 4.00),
            timeout_seconds=config.timeout_seconds,
            env_vars=config.to_mirofish_env(),
        )

        instance = await self.gpu_provider.provision(gpu_config)
        try:
            result = await self._execute_pipeline(instance.instance_id, config)
            return result
        finally:
            await self.gpu_provider.terminate(instance.instance_id)

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
        logger.info(f"Waiting for worker API at {worker_url}/health ...")
        for attempt in range(60):  # 5 min max (60 * 5s)
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get(f"{worker_url}/health")
                    if resp.status_code == 200:
                        logger.info(f"Worker API ready after {attempt * 5}s")
                        break
            except Exception:
                pass
            await asyncio.sleep(5)
        else:
            raise TimeoutError(f"Worker API at {worker_url} did not become ready within 300s")

        # ------------------------------------------------------------------
        # 2. Submit job — blocks until the pipeline completes (up to 1 hour)
        # ------------------------------------------------------------------
        logger.info(f"Submitting job to {worker_url}/job (max_rounds={config.max_rounds})")
        async with httpx.AsyncClient(timeout=3600) as client:  # 1 hour timeout
            resp = await client.post(f"{worker_url}/job", json={
                "seed_text": config.seed_text,
                "goal": config.goal,
                "max_rounds": config.max_rounds,
            })
            resp.raise_for_status()
            result = resp.json()

        # ------------------------------------------------------------------
        # 3. Return structured result for the Celery task to persist
        # ------------------------------------------------------------------
        return {
            "job_id": config.job_id,
            "instance_id": instance_id,
            "report": result.get("report", ""),
            "chat_log": result.get("chat_log", "[]"),
            "status": "completed",
        }
