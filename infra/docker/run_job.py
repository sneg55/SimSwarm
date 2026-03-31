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
import json
import os
import re
import sys
import time
import requests
from pathlib import Path

VLLM_URL = "http://localhost:8000/v1"
MIROSHARK_BACKEND = "/app/miroshark/backend"

# Module-level storage reference (set in main, used by all pipeline steps)
_storage = None


# ---------------------------------------------------------------------------
# English ontology prompt (replaces MiroShark's default Chinese prompt)
# ---------------------------------------------------------------------------

ENGLISH_ONTOLOGY_PROMPT = """You are a knowledge graph ontology designer. Your task is to analyze the given text and simulation goal, then design entity types and relationship types for a social media opinion simulation.

**Output valid JSON only. No other text.**

## Context

We are building a social media simulation system where:
- Each entity is an account/actor that posts, comments, follows, and interacts on social media
- Entities influence each other through information sharing and discourse
- We need to model how different actors react to events and how information spreads

Entities MUST be real-world actors that can speak and interact on social media:
- Specific individuals (public figures, experts, journalists, politicians)
- Companies and their official accounts
- Organizations (NGOs, unions, industry groups, universities)
- Government agencies and regulators
- Media outlets (newspapers, TV, podcasts, influencers)
- Representative community groups (advocacy groups, fan communities, professional associations)

Entities MUST NOT be abstract concepts, topics, opinions, or attitudes.

## Output Format

```json
{
    "entity_types": [
        {
            "name": "TypeName (PascalCase)",
            "description": "Brief description (under 100 chars)",
            "attributes": [
                {"name": "attribute_name (snake_case)", "type": "text", "description": "What this captures"}
            ],
            "examples": ["Example Entity 1", "Example Entity 2"]
        }
    ],
    "edge_types": [
        {
            "name": "RELATIONSHIP_NAME (UPPER_SNAKE_CASE)",
            "description": "Brief description (under 100 chars)",
            "source_targets": [{"source": "SourceType", "target": "TargetType"}],
            "attributes": []
        }
    ],
    "analysis_summary": "Brief analysis of the text and key actors identified"
}
```

## Design Rules

### Entity Types (6-10 types)
- Design types that match the ACTUAL actors in the text — not generic academic templates
- Include 2 fallback types at the end: `Person` (any individual) and `Organization` (any org)
- The remaining 4-8 types should be SPECIFIC to the domain in the text
- Each type needs clear boundaries — no overlapping types
- 1-3 attributes per type (do NOT use reserved names: name, uuid, group_id, created_at, summary)

### Relationship Types (6-10 types)
- Reflect real social media and institutional relationships
- Cover: institutional ties (WORKS_FOR, REGULATES), social dynamics (SUPPORTS, OPPOSES), information flow (REPORTS_ON, RESPONDS_TO)
- Ensure source_targets reference your defined entity types

### Quality Checklist
- Every type must have 2+ concrete examples from the text
- Types should cover ALL major actors mentioned, not just the first few
- Relationship types should enable modeling the core dynamics described in the simulation goal
- ALL output must be in English
"""

ENGLISH_INSTRUCTION = (
    "CRITICAL REQUIREMENT: ALL output text MUST be written entirely in English. "
    "Do NOT output any Chinese, Japanese, Korean, or other non-Latin text. "
    "Translate any non-English context or references to English. "
    "This applies to ALL fields: names, descriptions, analysis, summaries, reports, "
    "dialogue, posts, comments, and any other generated text.\n\n"
)


# ---------------------------------------------------------------------------
# Platform-specific profile style instructions
# ---------------------------------------------------------------------------

TWITTER_STYLE = (
    "\n\nPLATFORM BEHAVIOR (Twitter): You are posting on Twitter. "
    "Keep posts under 280 characters. Be punchy and direct. "
    "Use hashtags sparingly. React to trending topics. "
    "Your tone should be conversational, opinionated, and concise. "
    "Do NOT write long paragraphs — tweets are short takes."
)

REDDIT_STYLE = (
    "\n\nPLATFORM BEHAVIOR (Reddit): You are posting on Reddit. "
    "Write detailed, substantive posts and comments. "
    "Provide reasoning, evidence, or personal experience. "
    "Use paragraph form. Reddit rewards depth over brevity. "
    "Your tone should be analytical and discussion-oriented. "
    "Do NOT write short one-liners — Reddit expects thoughtful contributions."
)


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


def setup_miroshark_config(max_rounds: int) -> None:
    """Write .env for MiroShark and override Config class."""
    env_values = {
        "LLM_API_KEY": os.getenv("LLM_API_KEY", "not-needed"),
        "LLM_BASE_URL": VLLM_URL,
        "LLM_MODEL_NAME": os.getenv("LLM_MODEL_NAME", "Qwen2.5-32B-Instruct-AWQ"),
        "NEO4J_URI": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        "NEO4J_USER": os.getenv("NEO4J_USER", "neo4j"),
        "NEO4J_PASSWORD": os.getenv("NEO4J_PASSWORD", ""),
        "EMBEDDING_PROVIDER": os.getenv("EMBEDDING_PROVIDER", "openai"),
        "EMBEDDING_MODEL": os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        "EMBEDDING_BASE_URL": "https://api.openai.com/v1",
        "EMBEDDING_API_KEY": os.getenv("OPENAI_API_KEY", ""),
        "EMBEDDING_DIMENSIONS": os.getenv("EMBEDDING_DIMENSIONS", "1536"),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
        "OPENAI_API_BASE_URL": VLLM_URL,
        "WONDERWALL_DEFAULT_MAX_ROUNDS": str(max_rounds),
    }

    env_path = Path(MIROSHARK_BACKEND) / ".env"
    env_path.write_text(
        "\n".join(f"{k}={v}" for k, v in env_values.items()) + "\n",
        encoding="utf-8",
    )
    print(f"[run_job] Wrote config to {env_path}", flush=True)


def _apply_config_overrides(max_rounds: int) -> None:
    """Patch Config class after import."""
    from app.config import Config

    Config.LLM_API_KEY = os.getenv("LLM_API_KEY", "not-needed")
    Config.LLM_BASE_URL = VLLM_URL
    Config.LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "Qwen2.5-32B-Instruct-AWQ")
    Config.NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    Config.NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    Config.NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
    Config.EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "openai")
    Config.EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    Config.EMBEDDING_BASE_URL = "https://api.openai.com/v1"
    Config.EMBEDDING_API_KEY = os.getenv("OPENAI_API_KEY", "")
    Config.EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))
    Config.WONDERWALL_DEFAULT_MAX_ROUNDS = max_rounds


def _patch_prompts_to_english():
    """Monkey-patch MiroShark prompts to output in English."""
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

    # Replace ontology prompt entirely
    try:
        import app.services.ontology_generator as ontology_mod
        if hasattr(ontology_mod, "ONTOLOGY_SYSTEM_PROMPT"):
            ontology_mod.ONTOLOGY_SYSTEM_PROMPT = ENGLISH_ONTOLOGY_PROMPT
    except ImportError:
        pass

    print("[run_job] Patched MiroShark prompts to English output", flush=True)


def _extract_enrichment_hints(seed_text: str) -> str | None:
    """Extract entity hints from the enrichment section of the seed text."""
    marker = "--- Background Research ---"
    if marker not in seed_text:
        return None
    research = seed_text.split(marker, 1)[1].strip()
    if not research:
        return None
    return (
        "The following background research was gathered from web and social media search. "
        "Use it to identify key entities, their roles, and relationships that should be "
        "represented in the ontology:\n\n" + research[:3000]
    )


# ---------------------------------------------------------------------------
# Step 1 — Build Neo4j knowledge graph from seed text
# ---------------------------------------------------------------------------

def build_graph(seed_text: str, goal: str) -> tuple[str, str]:
    """
    Steps 1-2: Generate ontology, build Neo4j graph via MiroShark's storage.
    Returns (project_id, graph_id).
    """
    global _storage

    from app.services.ontology_generator import OntologyGenerator
    from app.storage.neo4j_storage import Neo4jStorage
    from app.services.text_processor import TextProcessor

    # Initialize Neo4j storage (connects to remote Neo4j VPS)
    _storage = Neo4jStorage()

    # Extract enrichment hints for ontology
    enrichment_hints = _extract_enrichment_hints(seed_text)
    if enrichment_hints:
        print("[run_job] Using enrichment research as ontology context", flush=True)

    print("[run_job] Step 1: Generating ontology...", flush=True)
    ontology_gen = OntologyGenerator()
    ontology = ontology_gen.generate(
        document_texts=[seed_text],
        simulation_requirement=goal,
        additional_context=enrichment_hints,
    )

    print("[run_job] Step 2: Building Neo4j knowledge graph...", flush=True)
    graph_id = _storage.create_graph(name=f"SimSwarm-{int(time.time())}")
    _storage.set_ontology(graph_id, ontology)

    # Split text, ingest in batches
    chunks = TextProcessor.split_text(seed_text, chunk_size=500, overlap=50)
    _storage.add_text_batch(graph_id, chunks, batch_size=3)

    info = _storage.get_graph_info(graph_id)
    print(f"[run_job] Graph ready: graph_id={graph_id}, nodes={info.get('node_count', 0)}, edges={info.get('edge_count', 0)}", flush=True)

    project_id = graph_id
    return project_id, graph_id


# ---------------------------------------------------------------------------
# Step 2 — Prepare simulation
# ---------------------------------------------------------------------------

def prepare_simulation(project_id: str, graph_id: str, seed_text: str, goal: str) -> str:
    """
    Step 3: Create simulation state and prepare (entities → profiles → config).
    Returns simulation_id.
    """
    from app.services.simulation_manager import SimulationManager

    print("[run_job] Step 3: Creating and preparing simulation...", flush=True)
    sm = SimulationManager()
    state = sm.create_simulation(
        project_id=project_id,
        graph_id=graph_id,
        enable_twitter=True,
        enable_reddit=True,
        enable_polymarket=False,
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
        storage=_storage,
    )

    print(f"[run_job] Simulation prepared: {simulation_id}", flush=True)
    return simulation_id


# ---------------------------------------------------------------------------
# Step 2b — Patch platform-specific profiles
# ---------------------------------------------------------------------------

def _patch_platform_profiles(simulation_id: str) -> None:
    """Inject platform-specific writing style into agent profiles."""
    from app.services.simulation_runner import SimulationRunner

    sim_dir = os.path.join(SimulationRunner.RUN_STATE_DIR, simulation_id)

    # Patch Twitter profiles (CSV: user_char column)
    twitter_path = os.path.join(sim_dir, "twitter_profiles.csv")
    if os.path.exists(twitter_path):
        import csv
        rows = []
        with open(twitter_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
            rows.append(header)
            char_idx = header.index('user_char') if 'user_char' in header else 3
            for row in reader:
                if len(row) > char_idx:
                    row[char_idx] = row[char_idx] + TWITTER_STYLE
                rows.append(row)
        with open(twitter_path, 'w', newline='', encoding='utf-8') as f:
            csv.writer(f).writerows(rows)
        print(f"[run_job] Patched {len(rows) - 1} Twitter profiles with platform style", flush=True)

    # Patch Reddit profiles (JSON: persona field)
    reddit_path = os.path.join(sim_dir, "reddit_profiles.json")
    if os.path.exists(reddit_path):
        with open(reddit_path, 'r', encoding='utf-8') as f:
            profiles = json.load(f)
        for p in profiles:
            if 'persona' in p:
                p['persona'] = p['persona'] + REDDIT_STYLE
        with open(reddit_path, 'w', encoding='utf-8') as f:
            json.dump(profiles, f, ensure_ascii=False, indent=2)
        print(f"[run_job] Patched {len(profiles)} Reddit profiles with platform style", flush=True)


# ---------------------------------------------------------------------------
# Step 3 — Run simulation and wait for completion
# ---------------------------------------------------------------------------

def run_and_wait(simulation_id: str, max_rounds: int, poll_interval: int = 10) -> None:
    """Start the simulation subprocess and block until it finishes."""
    from app.services.simulation_runner import SimulationRunner, RunnerStatus

    print(f"[run_job] Step 4: Starting simulation (max_rounds={max_rounds})...", flush=True)
    SimulationRunner.start_simulation(
        simulation_id=simulation_id,
        platform="parallel",
        max_rounds=max_rounds,
        enable_cross_platform=True,
    )

    terminal_statuses = {RunnerStatus.COMPLETED, RunnerStatus.STOPPED, RunnerStatus.FAILED}
    timeout = int(os.getenv("JOB_TIMEOUT_SECONDS", "43200"))
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
    """Run ReportAgent and return the full Markdown report string."""
    from app.services.report_agent import ReportAgent
    from app.services.graph_tools import GraphToolsService

    print("[run_job] Step 5: Generating report...", flush=True)

    graph_tools = GraphToolsService(storage=_storage)
    agent = ReportAgent(
        graph_id=graph_id,
        simulation_id=simulation_id,
        simulation_requirement=goal,
        graph_tools=graph_tools,
    )

    def _progress(stage: str, pct: int, msg: str) -> None:
        print(f"[run_job]   [report:{stage}] {pct}% — {msg}", flush=True)

    report = agent.generate_report(progress_callback=_progress)
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
# Step 5 — Collect chat log
# ---------------------------------------------------------------------------

def collect_chat_log(simulation_id: str) -> list:
    """Return all agent actions as a list of dicts."""
    from app.services.simulation_runner import SimulationRunner

    actions = SimulationRunner.get_all_actions(simulation_id)
    return [a.to_dict() for a in actions]


# ---------------------------------------------------------------------------
# Step 6 — Extract graph data from Neo4j
# ---------------------------------------------------------------------------

def extract_graph_data(graph_id: str) -> dict:
    """Extract all nodes and edges from Neo4j before cleanup."""
    try:
        data = _storage.get_graph_data(graph_id)
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])

        # Filter orphan nodes (zero connections)
        connected_uuids = set()
        for e in edges:
            connected_uuids.add(e.get("source_node_uuid", ""))
            connected_uuids.add(e.get("target_node_uuid", ""))

        filtered_nodes = [n for n in nodes if n.get("uuid", "") in connected_uuids]

        entity_types = set()
        for n in filtered_nodes:
            for lbl in n.get("labels", []):
                if lbl not in ("Entity", "Node"):
                    entity_types.add(lbl)

        graph_data = {
            "nodes": filtered_nodes,
            "edges": edges,
            "metadata": {
                "entity_types": sorted(entity_types),
                "total_nodes": len(filtered_nodes),
                "total_edges": len(edges),
            },
        }
        print(f"[run_job] Graph extracted: {len(filtered_nodes)} nodes, {len(edges)} edges", flush=True)
        return graph_data

    except Exception as exc:
        import traceback
        print(f"[run_job] WARNING: graph extraction failed: {exc}", flush=True)
        traceback.print_exc()
        return {"nodes": [], "edges": [], "metadata": {"entity_types": [], "total_nodes": 0, "total_edges": 0}}


# ---------------------------------------------------------------------------
# Per-agent stance injection from simulation config
# ---------------------------------------------------------------------------

def inject_agent_stance(simulation_id: str, graph_data: dict) -> None:
    """Read agent_configs and inject stance + influence_weight into graph nodes."""
    from app.services.simulation_manager import SimulationManager

    sm = SimulationManager()
    config = sm.get_simulation_config(simulation_id)
    if not config:
        return

    agent_configs = config.get("agent_configs", [])
    if not agent_configs:
        return

    name_to_agent = {}
    for ac in agent_configs:
        name = (ac.get("entity_name") or "").strip().lower()
        if name:
            name_to_agent[name] = ac

    matched = 0
    for node in graph_data.get("nodes", []):
        node_name = (node.get("name") or "").strip().lower()
        ac = name_to_agent.get(node_name)
        if ac:
            node["stance"] = ac.get("stance", "neutral")
            node["influence_weight"] = ac.get("influence_weight", 1.0)
            matched += 1

    print(f"[run_job] Stance injected: {matched}/{len(graph_data.get('nodes', []))} nodes matched", flush=True)


# ---------------------------------------------------------------------------
# Per-entity sentiment scoring
# ---------------------------------------------------------------------------

POSITIVE_WORDS = {
    "support", "approve", "praise", "welcome", "benefit", "success", "agree",
    "positive", "progress", "growth", "improve", "achieve", "gain", "boost",
    "encourage", "optimistic", "favorable", "advance", "strengthen", "celebrate",
    "endorse", "commend", "constructive", "prosper", "thrive", "cooperate",
    "alliance", "partnership", "diplomatic", "peaceful", "stable", "recovery",
    "innovation", "opportunity", "confident", "resolve", "protect", "invest",
    "expand", "lead", "unite", "embrace", "recommend", "affirm", "uphold",
    "champion", "reform", "empower", "sustain", "reliable",
}

NEGATIVE_WORDS = {
    "oppose", "condemn", "reject", "threaten", "crisis", "fail", "warn",
    "attack", "ban", "sanction", "conflict", "damage", "destroy", "collapse",
    "risk", "danger", "decline", "loss", "struggle", "tension", "hostile",
    "aggressive", "escalate", "violate", "disrupt", "undermine", "restrict",
    "protest", "controversy", "criticism", "backlash", "concern", "fear",
    "instability", "vulnerable", "deficit", "recession", "inflation", "corrupt",
    "exploit", "abuse", "negligence", "incompetent", "reckless", "toxic",
    "polarize", "divide", "obstruct", "retaliate", "assassinate",
}


def score_entity_sentiment(graph_data: dict, chat_log: list[dict]) -> None:
    """Score each graph node's sentiment by analyzing chat_log mentions."""
    nodes = graph_data.get("nodes", [])
    if not nodes:
        return

    name_to_indices: dict[str, list[int]] = {}
    for i, node in enumerate(nodes):
        name = node.get("name", "").strip()
        if name:
            name_to_indices.setdefault(name.lower(), []).append(i)

    pos_counts: dict[int, int] = {}
    neg_counts: dict[int, int] = {}

    for entry in chat_log:
        content = (entry.get("action_args") or {}).get("content", "")
        if not content:
            continue
        content_lower = content.lower()
        agent_name = (entry.get("agent_name") or "").strip().lower()

        words = set(re.findall(r'\b[a-z]+\b', content_lower))
        pos = len(words & POSITIVE_WORDS)
        neg = len(words & NEGATIVE_WORDS)

        matched_indices: set[int] = set()
        for entity_name, indices in name_to_indices.items():
            if entity_name in content_lower:
                matched_indices.update(indices)
            if agent_name and agent_name == entity_name:
                matched_indices.update(indices)

        for idx in matched_indices:
            pos_counts[idx] = pos_counts.get(idx, 0) + pos
            neg_counts[idx] = neg_counts.get(idx, 0) + neg

    for i, node in enumerate(nodes):
        p = pos_counts.get(i, 0)
        n = neg_counts.get(i, 0)
        total = p + n
        if total == 0:
            node["sentiment"] = 0.0
        else:
            node["sentiment"] = round(max(-1.0, min(1.0, (p - n) / total)), 2)


# ---------------------------------------------------------------------------
# Structured results
# ---------------------------------------------------------------------------

FINDING_COLORS = ["#22D3EE", "#A78BFA", "#F97316", "#6EE7B7", "#FF6B6B", "#FBBF24"]


def build_structured_results(outline, section_contents, chat_log, graph_data):
    """Build structured results from pipeline outputs. No LLM calls needed."""
    brief = ""
    if outline and outline.get("summary"):
        brief = outline["summary"]

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
    """Run the complete MiroShark pipeline and write results to output_dir."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    project_id, graph_id = build_graph(seed_text, goal)
    simulation_id = prepare_simulation(project_id, graph_id, seed_text, goal)

    # Patch profiles with platform-specific style
    try:
        _patch_platform_profiles(simulation_id)
    except Exception as exc:
        print(f"[run_job] WARNING: platform profile patching failed: {exc}", flush=True)

    run_and_wait(simulation_id, max_rounds)
    report_md = generate_report(graph_id, simulation_id, goal)
    chat_log = collect_chat_log(simulation_id)

    # Extract graph data from Neo4j
    graph_data = extract_graph_data(graph_id)

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

    # Cleanup Neo4j graph
    try:
        _storage.delete_graph(graph_id)
        _storage.close()
        print(f"[run_job] Neo4j graph {graph_id} cleaned up", flush=True)
    except Exception as exc:
        print(f"[run_job] WARNING: graph cleanup failed: {exc}", flush=True)

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

    # 4. Patch prompts to English
    _patch_prompts_to_english()

    # 5. Wait for vLLM
    if not args.skip_vllm_wait:
        wait_for_vllm()

    # 6. Run the pipeline
    run_pipeline(seed_text, args.goal, args.max_rounds, args.output_dir)


if __name__ == "__main__":
    main()
