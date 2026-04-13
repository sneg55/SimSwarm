"""Output adapter: converts SimulationResult types to SaaS worker API JSON.

This is the contract bridge — the SaaS layer consumes these exact shapes.
"""
from __future__ import annotations

from typing import Any

from simswarm.stance import NEGATIVE_WORDS, POSITIVE_WORDS  # noqa: F401 — public re-export
from simswarm.types import ActionRecord, GraphSnapshot

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FINDING_COLORS = ["#22D3EE", "#A78BFA", "#F97316", "#6EE7B7", "#FF6B6B", "#FBBF24"]

_COALITION_COLORS = ["#22D3EE", "#A78BFA", "#F97316", "#6EE7B7", "#FF6B6B"]


# ---------------------------------------------------------------------------
# Public adapter functions
# ---------------------------------------------------------------------------


def adapt_chat_log(chat_log: list[ActionRecord]) -> list[dict]:
    """Convert ActionRecords to MiroShark-compatible dicts.

    agent_id is converted from string to int via abs(hash(agent_id)) % 10**9
    for backwards compatibility with the SaaS layer.
    """
    result = []
    for record in chat_log:
        result.append({
            "round_num": record.round_num,
            "agent_id": abs(hash(record.agent_id)) % 10**9,
            "agent_name": record.agent_name,
            "action_type": record.action_type,
            "platform": record.platform,
            "action_args": record.action_args,
            "timestamp": record.timestamp,
            "success": record.success,
        })
    return result


def adapt_graph_data(graph: GraphSnapshot) -> dict:
    """Convert GraphSnapshot to the {nodes, edges, metadata} contract dict."""
    return {
        "nodes": list(graph.nodes),
        "edges": list(graph.edges),
        "metadata": dict(graph.metadata),
    }


def adapt_structured(
    brief: str,
    findings: list[dict[str, Any]],
    chat_log: list[dict[str, Any]],
    graph_data: dict[str, Any],
) -> dict:
    """Build the structured results dict consumed by the SaaS frontend.

    Args:
        brief: One-sentence summary of the simulation goal/outcome.
        findings: List of dicts with keys 'title' and 'content'.
        chat_log: Already-adapted chat log (list of dicts with int agent_id).
        graph_data: Already-adapted graph dict with nodes/edges/metadata.
    """
    adapted_findings = []
    for i, finding in enumerate(findings):
        content = finding.get("content", "")
        adapted_findings.append({
            "label": "FINDING",
            "title": finding.get("title", f"Section {i + 1}"),
            "description": content[:500],
            "metric": "",
            "accentColor": FINDING_COLORS[i % len(FINDING_COLORS)],
        })

    sentiment = _compute_platform_sentiment(chat_log)
    coalitions = _detect_coalitions(chat_log)
    confidence = _build_confidence(chat_log, graph_data)

    return {
        "brief": brief,
        "findings": adapted_findings,
        "sentiment": sentiment,
        "coalitions": coalitions,
        "confidence": confidence,
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _compute_platform_sentiment(chat_log: list[dict[str, Any]]) -> list[dict]:
    """Keyword-based sentiment score per platform."""
    platform_stats: dict[str, dict[str, int]] = {}
    for action in chat_log:
        platform = action.get("platform", "unknown")
        action_type = action.get("action_type", "")
        stats = platform_stats.setdefault(platform, {"positive": 0, "total": 0})
        stats["total"] += 1
        if action_type in ("CREATE_POST", "LIKE_POST", "REPOST", "COMMENT", "CREATE_COMMENT"):
            stats["positive"] += 1

    result = []
    for platform, counts in platform_stats.items():
        total = counts["total"]
        positive = counts["positive"]
        value = int((positive / total) * 100) if total > 0 else 0
        result.append({
            "label": platform.capitalize(),
            "value": value,
            "direction": "positive" if value >= 50 else "negative",
        })
    return result


def _detect_coalitions(chat_log: list[dict[str, Any]]) -> list[dict]:
    """Detect mutual-follow coalitions from interaction patterns."""
    follow_graph: dict[str, set[str]] = {}
    for action in chat_log:
        name = action.get("agent_name", "")
        if action.get("action_type") == "FOLLOW":
            target = (action.get("action_args") or {}).get("target", "")
            if name and target:
                follow_graph.setdefault(name, set()).add(target)

    visited: set[str] = set()
    coalitions = []
    for agent in follow_graph:
        if agent in visited:
            continue
        group = {agent}
        for target in follow_graph.get(agent, set()):
            if agent in follow_graph.get(target, set()):
                group.add(target)
        if len(group) >= 2:
            visited.update(group)
            idx = len(coalitions)
            coalitions.append({
                "name": f"Coalition {idx + 1}",
                "description": f"Mutual followers: {', '.join(sorted(group))}",
                "agents": len(group),
                "strength": min(100, len(group) * 20),
                "color": _COALITION_COLORS[idx % len(_COALITION_COLORS)],
            })
    return coalitions


def _build_confidence(
    chat_log: list[dict[str, Any]],
    graph_data: dict[str, Any],
) -> list[dict]:
    """Build confidence grid from agent count, rounds, entities, and trades."""
    agent_names = {action.get("agent_name") for action in chat_log if action.get("agent_name")}
    max_round = max((a.get("round_num", 0) for a in chat_log), default=0)
    trade_count = sum(
        1 for a in chat_log
        if a.get("platform") == "polymarket" and a.get("action_type") in ("BUY", "SELL")
    )
    meta = graph_data.get("metadata", {})
    return [
        {"label": "Agents", "value": str(len(agent_names)), "color": "#22D3EE"},
        {"label": "Rounds", "value": str(max_round), "color": "#A78BFA"},
        {"label": "Graph Entities", "value": str(meta.get("total_nodes", 0)), "color": "#6EE7B7"},
        {"label": "Trades", "value": str(trade_count), "color": "#F97316"},
    ]
