"""Entity extraction for run_job_v2.

Uses the simswarm-native LLM-backed extractor. Falls back to a filtered
capitalized-word heuristic only when the LLM call fails.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Ensure simswarm package is importable when this module is loaded standalone
_DOCKER_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _DOCKER_DIR.parent.parent
for _p in (str(_DOCKER_DIR), str(_REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from simswarm.entities import (  # noqa: E402
    EntityExtractionError,
    extract_entities,
    fallback_entities,
)
from simswarm.llm import LLMClient  # noqa: E402
from simswarm.types import Entity  # noqa: E402

# Public helper exported for tests that historically imported it from here.
_fallback_entities = fallback_entities


def get_entities(
    seed_text: str,
    goal: str,
    target_agents: int,
) -> list[Entity]:
    """Return entities for the simulation via simswarm-native extraction."""
    count = max(target_agents, 5)

    vllm_url = os.environ.get("VLLM_URL", "http://localhost:8000/v1")
    # Use the smart model when available — it's better at structured extraction
    # than the fast model. Both default to the same local vLLM weights today.
    model = os.environ.get("SMART_MODEL", os.environ.get("FAST_MODEL",
             os.environ.get("MODEL_ID", "Qwen/Qwen3-14B")))
    api_key = os.environ.get("LLM_API_KEY", "none")

    async def _run() -> list[Entity]:
        llm = LLMClient(base_url=vllm_url, model=model, api_key=api_key)
        try:
            return await extract_entities(seed_text, goal, count, llm)
        finally:
            await llm.close()

    try:
        entities = asyncio.run(_run())
        print(
            f"[run_job_v2] Extracted {len(entities)} entities: "
            f"{[e.name for e in entities]}",
            flush=True,
        )
        return entities
    except EntityExtractionError as exc:
        print(
            f"[run_job_v2] WARNING: LLM entity extraction failed ({exc}), using fallback",
            flush=True,
        )
    except Exception as exc:  # noqa: BLE001 — defensive; fall back on any runtime error
        print(
            f"[run_job_v2] WARNING: entity extraction raised {type(exc).__name__}: {exc}, "
            f"using fallback",
            flush=True,
        )

    entities = fallback_entities(seed_text, count=count)
    print(
        f"[run_job_v2] Fallback entities: {[e.name for e in entities]}",
        flush=True,
    )
    return entities
