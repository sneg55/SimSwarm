#!/usr/bin/env python3
"""
SimSwarm pipeline entry point (v2) — runs on GPU worker pods.

Pure-Python SimSwarm engine. No MiroShark dependencies.

Usage:
    python3 run_job_v2.py \\
        --seed-file /tmp/seed.txt \\
        --goal "Analyse climate-change opinion on social media" \\
        --max-rounds 200 \\
        --output-dir /tmp/results

Pipeline:
    1. Build entity graph via graph_ops.build_graph (or fallback)
    2. Run simulation via SimSwarm Engine
    3. Write sim output files (report generation moved to Celery worker)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Ensure helpers in this directory are importable
_DOCKER_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _DOCKER_DIR.parent.parent
for _p in (str(_DOCKER_DIR), str(_REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Re-export the public functions tests depend on
from run_job_v2_entities import _fallback_entities, get_entities  # noqa: E402,F401
from run_job_v2_runner import run_simulation, write_results  # noqa: E402

# Optional service_init for Neo4j/vLLM wait
try:
    from service_init import wait_for_neo4j  # type: ignore[import]
    _SERVICE_INIT_AVAILABLE = True
except ImportError:
    _SERVICE_INIT_AVAILABLE = False
    wait_for_neo4j = None


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------

def run_pipeline(
    seed_text: str,
    goal: str,
    max_rounds: int,
    output_dir: str,
    target_agents: int = 5,
) -> dict:
    """Sim-only pipeline: entities → simulation → write non-report artifacts.

    Report generation has moved to the SaaS-side Celery task
    (saas/jobs/tasks_report.py); the pod no longer writes report.md or
    structured_results.json.
    """
    entities = get_entities(seed_text, goal, target_agents)

    result = asyncio.run(
        run_simulation(seed_text, goal, max_rounds, entities, target_agents)
    )
    print(f"[run_job_v2] Simulation complete: {len(result.chat_log)} actions", flush=True)

    write_results(result, output_dir)

    out = Path(output_dir)
    return json.loads((out / "summary.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run SimSwarm pipeline on a GPU worker pod."
    )
    parser.add_argument("--seed-file", required=True)
    parser.add_argument("--goal", required=True)
    parser.add_argument("--max-rounds", type=int, default=200)
    parser.add_argument("--output-dir", default="/tmp/results")
    parser.add_argument("--target-agents", type=int, default=5)
    parser.add_argument("--skip-vllm-wait", action="store_true")
    args = parser.parse_args()

    seed_text = Path(args.seed_file).read_text(encoding="utf-8")

    if not args.skip_vllm_wait and _SERVICE_INIT_AVAILABLE:
        wait_for_neo4j()

    run_pipeline(seed_text, args.goal, args.max_rounds, args.output_dir, args.target_agents)


if __name__ == "__main__":
    main()
