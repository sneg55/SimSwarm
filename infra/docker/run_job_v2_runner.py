"""Simulation execution and file I/O for run_job_v2.

Provides:
  - run_simulation()   — async: builds Engine, runs SimulationConfig
  - generate_report()  — deprecated shim; raises NotImplementedError
  - write_results()    — sync: writes sim output files to disk (no report)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Ensure simswarm package is importable
_DOCKER_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _DOCKER_DIR.parent.parent
for _p in (str(_DOCKER_DIR), str(_REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from simswarm.adapter import adapt_chat_log, adapt_graph_data  # noqa: E402
from simswarm.engine import Engine  # noqa: E402
from simswarm.extractor import (  # noqa: E402
    agent_sentiment_from_trajectories,
    extract_agent_trajectories,
    extract_engagement_summary,
    extract_market_data,
    extract_posts,
    extract_profiles,
    extract_social_graph,
    extract_top_posts,
)
from simswarm.graph import build_graph  # noqa: E402
from simswarm.llm import LLMClient  # noqa: E402
from simswarm.relations import (  # noqa: E402
    RelationExtractionError,
    extract_relations,
)
from simswarm.types import (  # noqa: E402
    EngineConfig,
    Entity,
    EnvironmentConfig,
    SimulationConfig,
    SimulationResult,
)

# ---------------------------------------------------------------------------
# LLM endpoint config (read from env at import time)
# ---------------------------------------------------------------------------

_VLLM_URL = os.environ.get("VLLM_URL", "http://localhost:8000/v1")
_FAST_MODEL = os.environ.get("FAST_MODEL", os.environ.get("MODEL_ID", "Qwen/Qwen3-14B"))
_SMART_MODEL = os.environ.get("SMART_MODEL", _FAST_MODEL)
_LLM_API_KEY = os.environ.get("LLM_API_KEY", "none")


# ---------------------------------------------------------------------------
# run_simulation
# ---------------------------------------------------------------------------

async def run_simulation(
    seed_text: str,
    goal: str,
    max_rounds: int,
    entities: list[Entity],
    target_agents: int,
) -> SimulationResult:
    """Build Engine from env-var LLM config, run a full simulation."""
    fast_llm = LLMClient(base_url=_VLLM_URL, model=_FAST_MODEL, api_key=_LLM_API_KEY)
    smart_llm = LLMClient(base_url=_VLLM_URL, model=_SMART_MODEL, api_key=_LLM_API_KEY)

    config = SimulationConfig(
        seed_text=seed_text,
        goal=goal,
        entities=entities[:target_agents],
        environments=[
            EnvironmentConfig(type="social", params={}),
            EnvironmentConfig(type="market", params={}),
        ],
        rounds=max_rounds,
        concurrency=target_agents,
    )

    engine = Engine(
        fast_llm=fast_llm,
        smart_llm=smart_llm,
        engine_config=EngineConfig(concurrency=target_agents),
    )
    try:
        result = await engine.run(config)
        # Enrich the graph with LLM-extracted typed relations (DISAGREES_WITH,
        # SUPPORTS, RESPONDS_TO, …). This is the post-cutover replacement for
        # the Graphiti knowledge-graph edges. On failure we keep the
        # interaction-only graph rather than failing the whole job.
        relations: list[dict] = []
        try:
            relations = await extract_relations(
                list(config.entities), result.chat_log, smart_llm, goal=goal,
            )
            print(
                f"relations.extracted count={len(relations)} "
                f"types={sorted({r['type'] for r in relations})}",
                flush=True,
            )
            if relations:
                result.graph_data = build_graph(
                    list(config.entities), result.chat_log, relations=relations,
                )
        except RelationExtractionError as exc:
            print(f"relations.extraction_failed: {exc}", flush=True)
        # Stash for write_results so relations.json lands in MinIO for
        # post-mortem diagnostics.
        result.trajectories = {**(result.trajectories or {}), "relations": relations}
        return result
    finally:
        await fast_llm.close()
        await smart_llm.close()


# ---------------------------------------------------------------------------
# generate_report (deprecated shim)
# ---------------------------------------------------------------------------

async def generate_report(*_args, **_kwargs):
    raise NotImplementedError(
        "Report generation moved to saas/jobs/tasks_report.py; "
        "the pod should no longer invoke this path."
    )


# ---------------------------------------------------------------------------
# write_results
# ---------------------------------------------------------------------------

def write_results(result: SimulationResult, output_dir: str) -> None:
    """Write all sim-side output files to *output_dir*.

    Files: chat_log.json, graph_data.json, posts.json, engagement_summary.json,
           agent_trajectories.json, social_graph.json, trades.json, summary.json.

    Notably NOT written: report.md, structured_results.json — both are produced
    by the external-LLM report task in the Celery worker.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    def _w(name: str, data: object) -> None:
        (out / name).write_text(
            json.dumps(data, ensure_ascii=False, default=str), encoding="utf-8"
        )

    adapted_chat = adapt_chat_log(result.chat_log)
    _w("chat_log.json", adapted_chat)

    adapted_graph = adapt_graph_data(result.graph_data)

    trajectories = extract_agent_trajectories(result.chat_log)
    sentiment_by_agent = agent_sentiment_from_trajectories(trajectories)
    # Stamp mean-per-agent sentiment onto matching graph nodes so the
    # frontend GraphCanvas can color them. _adapt_node reads this field.
    for node in adapted_graph.get("nodes", []):
        nid = node.get("id")
        if nid in sentiment_by_agent:
            node["sentiment"] = sentiment_by_agent[nid]

    _w("graph_data.json", adapted_graph)

    _w("posts.json", extract_posts(result.chat_log))
    _w("top_posts.json", extract_top_posts(result.chat_log))
    _w("profiles.json", extract_profiles(result.chat_log))
    _w("engagement_summary.json", extract_engagement_summary(result.chat_log))
    _w("agent_trajectories.json", trajectories)
    _w("social_graph.json", extract_social_graph(result.chat_log))
    _w("trades.json", extract_market_data(result.chat_log))
    _w("relations.json", (result.trajectories or {}).get("relations", []))

    meta = adapted_graph.get("metadata", {})
    summary = {
        "status": "completed",
        "report_pending": True,
        "chat_log_entries": len(result.chat_log),
        "graph_nodes": meta.get("total_nodes", 0),
        "graph_edges": meta.get("total_edges", 0),
    }
    _w("summary.json", summary)
    print(json.dumps(summary), flush=True)
