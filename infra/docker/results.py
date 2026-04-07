"""
Result collection, report generation, graph extraction, and structured output.
"""
from __future__ import annotations

import json
import re
import traceback

from constants import POSITIVE_WORDS, NEGATIVE_WORDS, FINDING_COLORS


def generate_report(graph_id: str, simulation_id: str, goal: str, storage) -> str:
    """Run ReportAgent and return the full Markdown report string."""
    from app.services.report_agent import ReportAgent
    from app.services.graph_tools import GraphToolsService

    print("[run_job] Step 5: Generating report...", flush=True)

    graph_tools = GraphToolsService(storage=storage)
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


def collect_chat_log(simulation_id: str) -> list:
    """Return all agent actions as a list of dicts."""
    from app.services.simulation_runner import SimulationRunner

    actions = SimulationRunner.get_all_actions(simulation_id)
    return [a.to_dict() for a in actions]


def extract_graph_data(graph_id: str, storage) -> dict:
    """Extract all nodes and edges from Neo4j before cleanup."""
    try:
        data = storage.get_graph_data(graph_id)
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
        print(f"[run_job] WARNING: graph extraction failed: {exc}", flush=True)
        traceback.print_exc()
        return {"nodes": [], "edges": [], "metadata": {"entity_types": [], "total_nodes": 0, "total_edges": 0}}


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
    max_round = max((a.get("round_num", 0) for a in chat_log), default=0)
    trade_count = sum(
        1 for a in chat_log
        if a.get("platform") == "polymarket" and a.get("action_type") in ("BUY", "SELL")
    )
    confidence = [
        {"label": "Agents", "value": str(len(agent_names)), "color": "#22D3EE"},
        {"label": "Rounds", "value": str(max_round), "color": "#A78BFA"},
        {"label": "Graph Entities", "value": str(meta.get("total_nodes", 0)), "color": "#6EE7B7"},
        {"label": "Trades", "value": str(trade_count), "color": "#F97316"},
    ]

    return {"brief": brief, "findings": findings, "sentiment": sentiment, "coalitions": coalitions, "confidence": confidence}
