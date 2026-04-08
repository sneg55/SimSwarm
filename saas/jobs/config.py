"""Job configuration: dataclass + worker image resolution."""
from __future__ import annotations

import os
from dataclasses import dataclass

from saas.constants.tiers import TIER_TIMEOUTS

WORKER_IMAGE_REPO = "ghcr.io/sneg55/simswarm-worker"
WORKER_IMAGE_DEFAULT_TAG = "v20260402201814"


def get_worker_image() -> str:
    """Return worker Docker image, preferring WORKER_IMAGE_TAG env var.

    Falls back to WORKER_IMAGE_DEFAULT_TAG (pinned for deploy stability).
    The canonical default for new/clean envs lives in saas.config.Settings.
    """
    tag = os.getenv("WORKER_IMAGE_TAG", WORKER_IMAGE_DEFAULT_TAG)
    return f"{WORKER_IMAGE_REPO}:{tag}"


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
    openai_api_key: str
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    forecast_days: int | None = None
    target_agents: int = 5
    upload_urls: dict | None = None

    @property
    def timeout_seconds(self) -> int:
        return TIER_TIMEOUTS[self.tier]

    def to_worker_env(self) -> dict[str, str]:
        return {
            "LLM_API_KEY": self.llm_api_key,
            "LLM_BASE_URL": "http://localhost:8000/v1",
            "LLM_MODEL_NAME": self.model_id,
            "OPENAI_API_KEY": self.openai_api_key,
            "NEO4J_URI": self.neo4j_uri,
            "NEO4J_USER": self.neo4j_user,
            "NEO4J_PASSWORD": self.neo4j_password,
            "EMBEDDING_PROVIDER": "openai",
            "EMBEDDING_MODEL": "text-embedding-3-small",
            "EMBEDDING_DIMENSIONS": "1536",
            "WONDERWALL_DEFAULT_MAX_ROUNDS": str(self.max_rounds),
            "MODEL_ID": self.model_id,
            "VLLM_ARGS": self.vllm_args or "--max-model-len 8192 --enable-auto-tool-choice --tool-call-parser hermes",
        }
