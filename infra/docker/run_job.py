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
# English language overrides for MiroFish prompts (default is Chinese)
# ---------------------------------------------------------------------------

ENGLISH_INSTRUCTION = (
    "CRITICAL REQUIREMENT: ALL output text MUST be written entirely in English. "
    "Do NOT output any Chinese, Japanese, Korean, or other non-Latin text. "
    "Translate any non-English context or references to English. "
    "This applies to ALL fields: names, descriptions, analysis, summaries, reports, "
    "dialogue, posts, comments, and any other generated text.\n\n"
)


def _patch_mirofish_prompts_to_english():
    """Monkey-patch MiroFish service prompts to output in English."""
    sys.path.insert(0, MIROFISH_BACKEND)

    modules_to_patch = [
        "app.services.ontology_generator",
        "app.services.report_agent",
        "app.services.oasis_profile_generator",
        "app.services.simulation_config_generator",
    ]

    for mod_name in modules_to_patch:
        try:
            mod = __import__(mod_name, fromlist=[""])
            for attr in dir(mod):
                val = getattr(mod, attr)
                if isinstance(val, str) and len(val) > 80 and not attr.startswith("_"):
                    setattr(mod, attr, ENGLISH_INSTRUCTION + val)
        except ImportError:
            pass

    # Patch ontology system prompt specifically
    try:
        import app.services.ontology_generator as ontology_mod
        if hasattr(ontology_mod, "ONTOLOGY_SYSTEM_PROMPT"):
            ontology_mod.ONTOLOGY_SYSTEM_PROMPT = (
                ENGLISH_INSTRUCTION + ontology_mod.ONTOLOGY_SYSTEM_PROMPT
            )
    except ImportError:
        pass

    print("[run_job] Patched MiroFish prompts to English output", flush=True)


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
    graph_id = builder.create_graph(name=f"SimSwarm-{int(time.time())}")
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
    # Extract markdown from Report object
    if hasattr(report, "markdown_content") and report.markdown_content:
        markdown = report.markdown_content
    elif hasattr(report, "outline") and hasattr(report.outline, "to_markdown"):
        markdown = report.outline.to_markdown()
    elif hasattr(report, "to_markdown"):
        markdown = report.to_markdown()
    else:
        markdown = str(report)
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
# Step 6 — Extract graph data from Zep before teardown
# ---------------------------------------------------------------------------

def extract_graph_data(graph_id: str) -> dict:
    """
    Extract all nodes and edges from the Zep knowledge graph before it is
    destroyed.  Returns a dict with ``nodes``, ``edges``, and ``metadata``.
    On any failure the function returns an empty graph structure so that the
    pipeline can still complete.
    """
    try:
        from app.services.zep_tools import ZepToolsService  # noqa: PLC0415
        import os

        api_key = os.environ.get("ZEP_API_KEY", "")
        print(f"[run_job] Extracting graph data for graph_id={graph_id}, ZEP_API_KEY={'set' if api_key else 'MISSING'}", flush=True)
        zep = ZepToolsService(api_key=api_key)
        raw_nodes = zep.get_all_nodes(graph_id)
        raw_edges = zep.get_all_edges(graph_id)
        print(f"[run_job] Zep returned {len(raw_nodes)} nodes, {len(raw_edges)} edges", flush=True)

        # Build connection_count per node by counting edges
        connection_count: dict[str, int] = {}
        for edge in raw_edges:
            src = getattr(edge, "source_node_uuid", None) or edge.get("source_node_uuid", "")
            tgt = getattr(edge, "target_node_uuid", None) or edge.get("target_node_uuid", "")
            connection_count[src] = connection_count.get(src, 0) + 1
            connection_count[tgt] = connection_count.get(tgt, 0) + 1

        entity_types: set[str] = set()

        nodes = []
        for n in raw_nodes:
            uuid = getattr(n, "uuid", None) or (n.get("uuid", "") if isinstance(n, dict) else "")
            name = getattr(n, "name", None) or (n.get("name", "") if isinstance(n, dict) else "")
            labels = getattr(n, "labels", None) or (n.get("labels", []) if isinstance(n, dict) else [])
            summary = getattr(n, "summary", None) or (n.get("summary", "") if isinstance(n, dict) else "")

            # Primary label = first label that is not "Entity" or "Node"
            primary_label = None
            for lbl in (labels or []):
                if lbl not in ("Entity", "Node"):
                    primary_label = lbl
                    break
            if primary_label:
                entity_types.add(primary_label)

            nodes.append({
                "uuid": str(uuid),
                "name": str(name),
                "labels": list(labels or []),
                "summary": str(summary or ""),
                "connection_count": connection_count.get(str(uuid), 0),
            })

        def _attr(obj, key):
            return getattr(obj, key, None) or (obj.get(key, "") if isinstance(obj, dict) else "")

        edges = []
        for e in raw_edges:
            edges.append({
                "uuid": str(_attr(e, "uuid")),
                "name": str(_attr(e, "name")),
                "fact": str(_attr(e, "fact") or ""),
                "source_node_uuid": str(_attr(e, "source_node_uuid")),
                "target_node_uuid": str(_attr(e, "target_node_uuid")),
                "source_node_name": str(_attr(e, "source_node_name")),
                "target_node_name": str(_attr(e, "target_node_name")),
            })

        graph_data = {
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "entity_types": sorted(entity_types),
                "total_nodes": len(nodes),
                "total_edges": len(edges),
            },
        }
        print(f"[run_job] Graph extracted: {len(nodes)} nodes, {len(edges)} edges", flush=True)
        return graph_data

    except Exception as exc:
        import traceback
        print(f"[run_job] WARNING: graph extraction failed: {exc}", flush=True)
        traceback.print_exc()
        return {"nodes": [], "edges": [], "metadata": {"entity_types": [], "total_nodes": 0, "total_edges": 0}}


# ---------------------------------------------------------------------------
# Structured results (no LLM calls — pure data transformation)
# ---------------------------------------------------------------------------

FINDING_COLORS = ["#22D3EE", "#A78BFA", "#F97316", "#6EE7B7", "#FF6B6B", "#FBBF24"]


def build_structured_results(outline, section_contents, chat_log, graph_data):
    """Build structured results from pipeline outputs. No LLM calls needed."""
    brief = ""
    if outline and outline.get("summary"):
        brief = outline["summary"]

    # Findings from outline sections + section content
    findings = []
    sections = (outline or {}).get("sections", [])
    sorted_files = sorted(section_contents.keys())
    for i, section in enumerate(sections):
        content = ""
        if i < len(sorted_files):
            raw = section_contents[sorted_files[i]]
            paragraphs = [p.strip() for p in raw.split("\n\n") if p.strip() and not p.strip().startswith("#")]
            content = paragraphs[0] if paragraphs else ""
        findings.append({
            "label": "FINDING",
            "title": section.get("title", f"Section {i + 1}"),
            "description": content[:500],
            "metric": "",
            "accentColor": FINDING_COLORS[i % len(FINDING_COLORS)],
        })

    # Sentiment from chat_log action types per platform
    sentiment = []
    platform_actions = {}
    for action in chat_log:
        platform = action.get("platform", "unknown")
        action_type = action.get("action_type", "")
        if platform not in platform_actions:
            platform_actions[platform] = {"positive": 0, "total": 0}
        platform_actions[platform]["total"] += 1
        if action_type in ("CREATE_POST", "LIKE_POST", "REPOST", "COMMENT"):
            platform_actions[platform]["positive"] += 1
    for platform, counts in platform_actions.items():
        total = counts["total"]
        positive = counts["positive"]
        value = int((positive / total) * 100) if total > 0 else 0
        sentiment.append({"label": platform.capitalize(), "value": value, "direction": "positive" if value >= 50 else "negative"})

    # Coalitions from FOLLOW patterns
    coalitions = []
    follow_graph = {}
    agent_names = set()
    for action in chat_log:
        name = action.get("agent_name", "")
        if name:
            agent_names.add(name)
        if action.get("action_type") == "FOLLOW":
            target = action.get("action_args", {}).get("target", "")
            if name and target:
                follow_graph.setdefault(name, set()).add(target)
    visited = set()
    coalition_colors = ["#22D3EE", "#A78BFA", "#F97316", "#6EE7B7", "#FF6B6B"]
    ci = 0
    for agent in follow_graph:
        if agent in visited:
            continue
        group = {agent}
        for target in follow_graph.get(agent, set()):
            if agent in follow_graph.get(target, set()):
                group.add(target)
        if len(group) >= 2:
            visited.update(group)
            coalitions.append({
                "name": f"Coalition {ci + 1}",
                "description": f"Mutual followers: {', '.join(sorted(group))}",
                "agents": len(group),
                "strength": min(100, len(group) * 20),
                "color": coalition_colors[ci % len(coalition_colors)],
            })
            ci += 1

    # Confidence from simulation metadata
    meta = graph_data.get("metadata", {})
    confidence = [
        {"label": "Agents", "value": str(len(agent_names)), "color": "#22D3EE"},
        {"label": "Rounds", "value": str(len(chat_log)), "color": "#A78BFA"},
        {"label": "Graph Entities", "value": str(meta.get("total_nodes", 0)), "color": "#6EE7B7"},
    ]

    return {"brief": brief, "findings": findings, "sentiment": sentiment, "coalitions": coalitions, "confidence": confidence}


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

    # Extract graph data from Zep before the ephemeral graph is destroyed
    graph_data = extract_graph_data(graph_id)

    # Build structured results from pipeline outputs
    structured = {}
    try:
        report_dirs = list(Path("/tmp/results").parent.glob("report_*"))
        if not report_dirs:
            report_dirs = list(Path("/tmp").glob("report_*"))
        outline = None
        section_contents = {}
        for rd in report_dirs:
            outline_file = rd / "outline.json"
            if outline_file.exists():
                outline = json.loads(outline_file.read_text(encoding="utf-8"))
            for sf in sorted(rd.glob("section_*.md")):
                section_contents[sf.name] = sf.read_text(encoding="utf-8")
        structured = build_structured_results(outline, section_contents, chat_log, graph_data)
        print(f"[run_job] Structured results: {len(structured.get('findings', []))} findings", flush=True)
    except Exception as exc:
        print(f"[run_job] WARNING: structured results failed: {exc}", flush=True)

    structured_str = json.dumps(structured, ensure_ascii=False, default=str)
    (out / "structured_results.json").write_text(structured_str, encoding="utf-8")

    (out / "report.md").write_text(report_md, encoding="utf-8")
    chat_log_str = json.dumps(chat_log, ensure_ascii=False, default=str)
    (out / "chat_log.json").write_text(chat_log_str, encoding="utf-8")
    graph_data_str = json.dumps(graph_data, ensure_ascii=False, default=str)
    (out / "graph_data.json").write_text(graph_data_str, encoding="utf-8")

    summary = {
        "status": "completed",
        "simulation_id": simulation_id,
        "graph_id": graph_id,
        "report_length": len(report_md),
        "chat_log_entries": len(chat_log),
        "graph_nodes": graph_data["metadata"]["total_nodes"],
        "graph_edges": graph_data["metadata"]["total_edges"],
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

    # 3b. Patch all prompts to English output
    _patch_mirofish_prompts_to_english()

    # 4. Optionally wait for local vLLM
    if not args.skip_vllm_wait:
        wait_for_vllm()

    # 5. Run the pipeline
    run_pipeline(seed_text, args.goal, args.max_rounds, args.output_dir)


if __name__ == "__main__":
    main()
