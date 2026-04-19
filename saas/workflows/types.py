"""Shared dataclasses for the Simulation workflow.

Zero Temporal imports — this module is safe to import from both the workflow
(sandboxed) and activity (unrestricted) sides without sandbox violations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SimParams:
    """Arguments passed to SimulationWorkflow.run."""
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
    openai_api_key: str = ""
    credits_charged: int = 0
    enrich_web: bool = True
    forecast_days: int | None = None
    target_agents: int = 5
    upload_urls: dict[str, Any] | None = None


@dataclass
class PodInfo:
    """Returned by provision_pod; consumed by downstream activities."""
    id: str

# Note: submit_and_poll and upload_and_finalize communicate via plain dict;
# no SimResult dataclass is defined because SimulationWorkflow.run returns
# None (the API's POST /jobs path does not await workflow.result()).
