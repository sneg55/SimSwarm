"""Job runner: bridges Celery tasks to GPU provider + MiroFish pipeline."""
from __future__ import annotations

from dataclasses import dataclass

from saas.gpu.provider import GPUProvider, GPUProviderConfig

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
        """Execute the MiroFish 5-step pipeline on the GPU instance.

        Steps:
          1. Upload seed text to the instance as /tmp/seed.txt
          2. Execute run_job.py on the instance (blocks until completion)
          3. Download report.md and chat_log.json
          4. Return report + chat_log to be saved in the DB
        """
        # ------------------------------------------------------------------
        # 1. Upload seed text
        # ------------------------------------------------------------------
        # Use a heredoc so arbitrary text (quotes, newlines) is transmitted
        # safely without shell escaping issues.
        await self.gpu_provider.execute_command(
            instance_id,
            f"cat > /tmp/seed.txt << 'SEEDEOF'\n{config.seed_text}\nSEEDEOF",
        )

        # ------------------------------------------------------------------
        # 2. Run the pipeline
        # ------------------------------------------------------------------
        # Single-quote the goal after replacing any embedded single quotes.
        goal_safe = config.goal.replace("'", "'\\''")
        await self.gpu_provider.execute_command(
            instance_id,
            (
                "cd /app && python3 run_job.py"
                " --seed-file /tmp/seed.txt"
                f" --goal '{goal_safe}'"
                f" --max-rounds {config.max_rounds}"
                " --output-dir /tmp/results"
            ),
        )

        # ------------------------------------------------------------------
        # 3. Download results
        # ------------------------------------------------------------------
        report = await self.gpu_provider.execute_command(
            instance_id, "cat /tmp/results/report.md"
        )
        chat_log = await self.gpu_provider.execute_command(
            instance_id, "cat /tmp/results/chat_log.json"
        )

        # ------------------------------------------------------------------
        # 4. Return structured result for the Celery task to persist
        # ------------------------------------------------------------------
        return {
            "job_id": config.job_id,
            "instance_id": instance_id,
            "report": report,
            "chat_log": chat_log,
            "status": "completed",
        }
