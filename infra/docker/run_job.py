#!/usr/bin/env python3
"""
Job runner script that executes on GPU worker instances.
Called by the SaaS Celery worker via SSH/exec after provisioning.

Usage:
    python3 run_job.py \
        --seed-file /tmp/seed.txt \
        --goal "Analyze climate change opinions on social media" \
        --max-rounds 200 \
        --output-dir /tmp/results

Pipeline (5 steps matching the MiroFish UI workflow):
    1. Wait for vLLM to be ready (health check)
    2. Build Zep knowledge graph from seed text
       (text split → ontology generation → graph ingestion)
    3. Create + prepare simulation
       (entity filtering → profile generation → config generation)
    4. Run OASIS simulation (parallel twitter+reddit)
    5. Generate report via ReportAgent
    6. Export report.md + chat_log.json to output_dir
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import requests
from pathlib import Path

VLLM_URL = "http://localhost:8000/v1"
MIROFISH_BACKEND = "/app/mirofish/backend"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def wait_for_vllm(timeout: int = 600) -> None:
    """Block until vLLM OpenAI-compatible server responds on /v1/models."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = requests.get(f"{VLLM_URL}/models", timeout=5)
            if resp.status_code == 200:
                print("[run_job] vLLM server ready", flush=True)
                return
        except requests.ConnectionError:
            pass
        time.sleep(5)
    raise TimeoutError(f"vLLM server did not start within {timeout}s")


def setup_mirofish_config() -> None:
    """
    Write a .env file at the MiroFish backend root and override the Config
    class attributes so that both dotenv-based and direct-attribute access
    paths pick up the correct values.
    """
    env_values = {
        "LLM_API_KEY": os.getenv("LLM_API_KEY", "not-needed"),
        "LLM_BASE_URL": VLLM_URL,
        "LLM_MODEL_NAME": os.getenv("LLM_MODEL_NAME", "Qwen2.5-32B-Instruct-AWQ"),
        "ZEP_API_KEY": os.getenv("ZEP_API_KEY", ""),
        "OASIS_DEFAULT_MAX_ROUNDS": os.getenv("OASIS_DEFAULT_MAX_ROUNDS", "200"),
    }

    # Write .env so MiroFish's own dotenv-based Config loader picks it up
    env_path = Path(MIROFISH_BACKEND) / ".env"
    env_path.write_text(
        "\n".join(f"{k}={v}" for k, v in env_values.items()) + "\n",
        encoding="utf-8",
    )
    print(f"[run_job] Wrote config to {env_path}", flush=True)


def _apply_config_overrides(max_rounds: int) -> None:
    """
    Patch Config class attributes after import so any already-imported
    reference uses the updated values.
    """
    from app.config import Config  # noqa: PLC0415

    Config.LLM_API_KEY = os.getenv("LLM_API_KEY", "not-needed")
    Config.LLM_BASE_URL = VLLM_URL
    Config.LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "Qwen2.5-32B-Instruct-AWQ")
    Config.ZEP_API_KEY = os.getenv("ZEP_API_KEY", "")
    Config.OASIS_DEFAULT_MAX_ROUNDS = max_rounds


# ---------------------------------------------------------------------------
# Step 1 — Build Zep knowledge graph from seed text
# ---------------------------------------------------------------------------

def build_graph(seed_text: str, goal: str) -> tuple[str, str]:
    """
    Steps 1-2 of the MiroFish pipeline:
      • Generate ontology from seed text
      • Build a Zep graph using GraphBuilderService

    Returns (project_id, graph_id).
    """
    from app.services.ontology_generator import OntologyGenerator  # noqa: PLC0415
    from app.services.graph_builder import GraphBuilderService  # noqa: PLC0415

    print("[run_job] Step 1: Generating ontology...", flush=True)
    ontology_gen = OntologyGenerator()
    ontology = ontology_gen.generate(
        document_texts=[seed_text],
        simulation_requirement=goal,
    )

    print("[run_job] Step 2: Building Zep knowledge graph...", flush=True)
    builder = GraphBuilderService()
    graph_id = builder.create_graph(name=f"FishCloud-{int(time.time())}")
    builder.set_ontology(graph_id, ontology)

    # Split text, ingest in batches, wait for Zep processing
    from app.services.text_processor import TextProcessor  # noqa: PLC0415

    chunks = TextProcessor.split_text(seed_text, chunk_size=500, overlap=50)
    episode_uuids = builder.add_text_batches(graph_id, chunks, batch_size=3)
    builder._wait_for_episodes(episode_uuids, timeout=600)

    # Use graph_id as project_id (one graph per job)
    project_id = graph_id
    print(f"[run_job] Graph ready: graph_id={graph_id}", flush=True)
    return project_id, graph_id


# ---------------------------------------------------------------------------
# Step 2 — Prepare simulation
# ---------------------------------------------------------------------------

def prepare_simulation(project_id: str, graph_id: str, seed_text: str, goal: str) -> str:
    """
    Step 3 of the MiroFish pipeline.
    Creates a SimulationState and runs prepare_simulation() synchronously.

    Returns simulation_id.
    """
    from app.services.simulation_manager import SimulationManager  # noqa: PLC0415

    print("[run_job] Step 3: Creating and preparing simulation...", flush=True)
    sm = SimulationManager()
    state = sm.create_simulation(
        project_id=project_id,
        graph_id=graph_id,
        enable_twitter=True,
        enable_reddit=True,
    )
    simulation_id = state.simulation_id

    def _progress(stage: str, pct: int, msg: str, **_kw: object) -> None:
        print(f"[run_job]   [{stage}] {pct}% — {msg}", flush=True)

    sm.prepare_simulation(
        simulation_id=simulation_id,
        simulation_requirement=goal,
        document_text=seed_text,
        use_llm_for_profiles=True,
        progress_callback=_progress,
    )

    print(f"[run_job] Simulation prepared: {simulation_id}", flush=True)
    return simulation_id


# ---------------------------------------------------------------------------
# Step 3 — Run simulation and wait for completion
# ---------------------------------------------------------------------------

def run_and_wait(simulation_id: str, max_rounds: int, poll_interval: int = 10) -> None:
    """
    Step 4: Start the OASIS simulation subprocess and block until it finishes.
    Polls SimulationRunner.get_run_state() every *poll_interval* seconds.
    """
    from app.services.simulation_runner import SimulationRunner, RunnerStatus  # noqa: PLC0415

    print(f"[run_job] Step 4: Starting simulation (max_rounds={max_rounds})...", flush=True)
    run_state = SimulationRunner.start_simulation(
        simulation_id=simulation_id,
        platform="parallel",
        max_rounds=max_rounds,
    )

    terminal_statuses = {RunnerStatus.COMPLETED, RunnerStatus.STOPPED, RunnerStatus.FAILED}
    timeout = int(os.getenv("JOB_TIMEOUT_SECONDS", "43200"))  # 12h default
    start = time.time()

    while True:
        elapsed = int(time.time() - start)
        if elapsed > timeout:
            SimulationRunner.stop_simulation(simulation_id)
            raise TimeoutError(f"Simulation timed out after {timeout}s")

        run_state = SimulationRunner.get_run_state(simulation_id)
        if run_state is None:
            raise RuntimeError("SimulationRunner lost state for simulation_id=" + simulation_id)

        status = run_state.runner_status
        print(
            f"[run_job]   status={status.value}  "
            f"round={run_state.current_round}/{run_state.total_rounds}  "
            f"elapsed={elapsed}s",
            flush=True,
        )

        if status in terminal_statuses:
            break

        time.sleep(poll_interval)

    if run_state.runner_status == RunnerStatus.FAILED:
        raise RuntimeError(f"Simulation failed: {run_state.error}")

    print(f"[run_job] Simulation completed: {run_state.current_round} rounds", flush=True)


# ---------------------------------------------------------------------------
# Step 4 — Generate report
# ---------------------------------------------------------------------------

def generate_report(graph_id: str, simulation_id: str, goal: str) -> str:
    """
    Step 5: Run ReportAgent and return the full Markdown report string.
    """
    from app.services.report_agent import ReportAgent  # noqa: PLC0415

    print("[run_job] Step 5: Generating report...", flush=True)

    agent = ReportAgent(
        graph_id=graph_id,
        simulation_id=simulation_id,
        simulation_requirement=goal,
    )

    def _progress(stage: str, pct: int, msg: str) -> None:
        print(f"[run_job]   [report:{stage}] {pct}% — {msg}", flush=True)

    report = agent.generate_report(progress_callback=_progress)
    markdown = report.to_markdown() if hasattr(report, "to_markdown") else str(report)
    print(f"[run_job] Report generated ({len(markdown)} chars)", flush=True)
    return markdown


# ---------------------------------------------------------------------------
# Step 5 — Collect chat log (agent actions)
# ---------------------------------------------------------------------------

def collect_chat_log(simulation_id: str) -> list:
    """Return all agent actions as a list of dicts."""
    from app.services.simulation_runner import SimulationRunner  # noqa: PLC0415

    actions = SimulationRunner.get_all_actions(simulation_id)
    return [a.to_dict() for a in actions]


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_pipeline(seed_text: str, goal: str, max_rounds: int, output_dir: str) -> dict:
    """Run the complete 5-step MiroFish pipeline and write results to output_dir."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    project_id, graph_id = build_graph(seed_text, goal)
    simulation_id = prepare_simulation(project_id, graph_id, seed_text, goal)
    run_and_wait(simulation_id, max_rounds)
    report_md = generate_report(graph_id, simulation_id, goal)
    chat_log = collect_chat_log(simulation_id)

    (out / "report.md").write_text(report_md, encoding="utf-8")
    chat_log_str = json.dumps(chat_log, ensure_ascii=False, default=str)
    (out / "chat_log.json").write_text(chat_log_str, encoding="utf-8")

    summary = {
        "status": "completed",
        "simulation_id": simulation_id,
        "graph_id": graph_id,
        "report_length": len(report_md),
        "chat_log_entries": len(chat_log),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary), flush=True)
    return summary


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Execute MiroFish 5-step pipeline on a GPU worker instance."
    )
    parser.add_argument(
        "--seed-file",
        required=True,
        help="Path to a text file containing the seed material.",
    )
    parser.add_argument(
        "--goal",
        required=True,
        help="Simulation requirement / research goal.",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=200,
        help="Maximum OASIS simulation rounds (default: 200).",
    )
    parser.add_argument(
        "--output-dir",
        default="/tmp/results",
        help="Directory where report.md, chat_log.json and summary.json are written.",
    )
    parser.add_argument(
        "--skip-vllm-wait",
        action="store_true",
        help="Skip the vLLM health-check (useful for tests or when vLLM isn't used).",
    )
    args = parser.parse_args()

    seed_text = Path(args.seed_file).read_text(encoding="utf-8")

    # 1. Write MiroFish .env so dotenv picks it up on first import
    setup_mirofish_config()

    # 2. Make sure MiroFish backend is importable
    sys.path.insert(0, MIROFISH_BACKEND)

    # 3. Override Config after import
    _apply_config_overrides(args.max_rounds)

    # 4. Optionally wait for local vLLM
    if not args.skip_vllm_wait:
        wait_for_vllm()

    # 5. Run the pipeline
    run_pipeline(seed_text, args.goal, args.max_rounds, args.output_dir)


if __name__ == "__main__":
    main()
