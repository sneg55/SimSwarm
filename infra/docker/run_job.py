#!/usr/bin/env python3
"""
Job runner script that executes on GPU worker instances.
Called by the SaaS Celery worker via SSH/exec after provisioning.

Uses MiroShark engine with Neo4j graph database.

Usage:
    python3 run_job.py \
        --seed-file /tmp/seed.txt \
        --goal "Analyze climate change opinions on social media" \
        --max-rounds 200 \
        --output-dir /tmp/results

Pipeline (5 steps):
    1. Build Neo4j knowledge graph from seed text
       (ontology generation → NER extraction → graph ingestion)
    2. Create + prepare simulation
       (entity filtering → profile generation → config generation)
    3. Run Wonderwall simulation (parallel twitter+reddit)
    4. Generate report via ReportAgent
    5. Export report.md + chat_log.json + graph_data.json
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

from constants import MIROSHARK_BACKEND
from service_init import (
    wait_for_neo4j,
    wait_for_vllm,
    setup_miroshark_config,
    _apply_config_overrides,
)
from graph_ops import build_graph
from simulation import prepare_simulation, run_and_wait
from results import (
    generate_report,
    collect_chat_log,
    extract_graph_data,
    inject_agent_stance,
    score_entity_sentiment,
    build_structured_results,
)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

MIN_GRAPH_ENTITIES = 5


def run_pipeline(seed_text: str, goal: str, max_rounds: int, output_dir: str) -> dict:
    """Run the complete MiroShark pipeline and write results to output_dir."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Create storage once, pass it through the pipeline
    from app.storage.neo4j_storage import Neo4jStorage
    storage = Neo4jStorage()

    project_id, graph_id = build_graph(seed_text, goal, storage)
    try:
        # Guard: fail early if graph is too small for a meaningful simulation
        info = storage.get_graph_info(graph_id)
        node_count = info.get("node_count", 0)
        if node_count < MIN_GRAPH_ENTITIES:
            raise RuntimeError(
                f"GRAPH_TOO_SMALL: only {node_count} entities extracted "
                f"(minimum {MIN_GRAPH_ENTITIES})"
            )

        simulation_id = prepare_simulation(project_id, graph_id, seed_text, goal, storage)

        run_and_wait(simulation_id, max_rounds)
        report_md = generate_report(graph_id, simulation_id, goal, storage)
        chat_log = collect_chat_log(simulation_id)

        # Extract graph data from Neo4j
        graph_data = extract_graph_data(graph_id, storage)

        # Inject per-agent stance
        try:
            inject_agent_stance(simulation_id, graph_data)
        except Exception as exc:
            print(f"[run_job] WARNING: stance injection failed: {exc}", flush=True)

        # Score per-entity sentiment
        try:
            score_entity_sentiment(graph_data, chat_log)
            scored = sum(1 for n in graph_data.get("nodes", []) if n.get("sentiment", 0) != 0)
            print(f"[run_job] Sentiment scored: {scored}/{len(graph_data.get('nodes', []))} entities with non-zero sentiment", flush=True)
        except Exception as exc:
            print(f"[run_job] WARNING: sentiment scoring failed: {exc}", flush=True)

        # Build structured results
        structured = {}
        try:
            report_dirs = list(out.glob("report_*"))
            if not report_dirs:
                report_dirs = list(out.parent.glob("report_*"))
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

        # Extract rich simulation data from SQLite DBs
        try:
            _spec = importlib.util.spec_from_file_location("sim_data_extractor", "/app/sim_data_extractor.py")
            _mod = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(_mod)
            extract_all = _mod.extract_all
            from app.services.simulation_runner import SimulationRunner as _SRE
            sim_dir = os.path.join(_SRE.RUN_STATE_DIR, simulation_id)
            if os.path.isdir(sim_dir):
                print(f"[run_job] Extracting rich simulation data from {sim_dir}", flush=True)
                all_data = extract_all(sim_dir, chat_log)
                for filename, data in all_data.items():
                    fpath = out / filename
                    fpath.write_text(json.dumps(data, ensure_ascii=False, default=str), encoding="utf-8")
                    print(f"[run_job] Wrote {filename} ({fpath.stat().st_size} bytes)", flush=True)
            else:
                print(f"[run_job] WARNING: sim_dir not found for extraction: {sim_dir}", flush=True)
        except Exception as exc:
            print(f"[run_job] WARNING: rich data extraction failed: {exc}", flush=True)

    finally:
        # Always clean up Neo4j graph, even on failure
        try:
            storage.delete_graph(graph_id)
            storage.close()
            print(f"[run_job] Neo4j graph {graph_id} cleaned up", flush=True)
        except Exception as exc:
            print(f"[run_job] WARNING: graph cleanup failed: {exc}", flush=True)

    from app.services.simulation_runner import SimulationRunner as _SR
    summary = {
        "status": "completed",
        "simulation_id": simulation_id,
        "sim_dir": os.path.join(_SR.RUN_STATE_DIR, simulation_id),
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
        description="Execute MiroShark pipeline on a GPU worker instance."
    )
    parser.add_argument("--seed-file", required=True)
    parser.add_argument("--goal", required=True)
    parser.add_argument("--max-rounds", type=int, default=200)
    parser.add_argument("--output-dir", default="/tmp/results")
    parser.add_argument("--skip-vllm-wait", action="store_true")
    args = parser.parse_args()

    seed_text = Path(args.seed_file).read_text(encoding="utf-8")

    # 1. Write MiroShark .env
    setup_miroshark_config(args.max_rounds)

    # 2. Make MiroShark backend importable
    sys.path.insert(0, MIROSHARK_BACKEND)

    # 3. Override Config after import
    _apply_config_overrides(args.max_rounds)

    # 4. Check Neo4j connectivity
    wait_for_neo4j()

    # 5. Wait for vLLM
    if not args.skip_vllm_wait:
        wait_for_vllm()

    # 6. Run the pipeline
    run_pipeline(seed_text, args.goal, args.max_rounds, args.output_dir)


if __name__ == "__main__":
    main()
