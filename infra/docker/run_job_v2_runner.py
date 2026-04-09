"""Simulation execution and report generation for run_job_v2.

Provides:
  - run_simulation()   — async: builds Engine, runs SimulationConfig
  - generate_report()  — async: runs ReportGenerator over a SimulationResult
  - write_results()    — sync: writes all output files to disk
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

from simswarm.adapter import adapt_chat_log, adapt_graph_data, adapt_structured
from simswarm.engine import Engine
from simswarm.extractor import (
    extract_agent_trajectories,
    extract_engagement_summary,
    extract_market_data,
    extract_posts,
    extract_social_graph,
)
from simswarm.llm import LLMClient
from simswarm.report import Report, ReportGenerator
from simswarm.types import (
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
        return await engine.run(config)
    finally:
        await fast_llm.close()
        await smart_llm.close()


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------

async def generate_report(result: SimulationResult, goal: str) -> Report:
    """Run ReportGenerator over a SimulationResult, return a Report."""
    smart_llm = LLMClient(base_url=_VLLM_URL, model=_SMART_MODEL, api_key=_LLM_API_KEY)
    try:
        return await ReportGenerator(smart_llm).generate(result, goal)
    finally:
        await smart_llm.close()


# ---------------------------------------------------------------------------
# write_results
# ---------------------------------------------------------------------------

def write_results(result: SimulationResult, report: Report, output_dir: str) -> None:
    """Write all pipeline output files to *output_dir*.

    Files: report.md, chat_log.json, graph_data.json, structured_results.json,
           posts.json, engagement_summary.json, agent_trajectories.json,
           social_graph.json, trades.json, summary.json
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    def _w(name: str, data: object) -> None:
        (out / name).write_text(
            json.dumps(data, ensure_ascii=False, default=str), encoding="utf-8"
        )

    (out / "report.md").write_text(report.raw_markdown, encoding="utf-8")

    adapted_chat = adapt_chat_log(result.chat_log)
    _w("chat_log.json", adapted_chat)

    adapted_graph = adapt_graph_data(result.graph_data)
    _w("graph_data.json", adapted_graph)

    _w("structured_results.json", adapt_structured(
        brief=report.executive_brief,
        findings=report.findings,
        chat_log=adapted_chat,
        graph_data=adapted_graph,
    ))

    _w("posts.json", extract_posts(result.chat_log))
    _w("engagement_summary.json", extract_engagement_summary(result.chat_log))
    _w("agent_trajectories.json", extract_agent_trajectories(result.chat_log))
    _w("social_graph.json", extract_social_graph(result.chat_log))
    _w("trades.json", extract_market_data(result.chat_log))

    meta = adapted_graph.get("metadata", {})
    summary = {
        "status": "completed",
        "report_length": len(report.raw_markdown),
        "chat_log_entries": len(result.chat_log),
        "graph_nodes": meta.get("total_nodes", 0),
        "graph_edges": meta.get("total_edges", 0),
    }
    _w("summary.json", summary)
    print(json.dumps(summary), flush=True)
