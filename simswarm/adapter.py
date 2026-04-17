"""Output adapter: converts SimulationResult types to SaaS worker API JSON.

This is the contract bridge — the SaaS layer consumes these exact shapes.
"""
from __future__ import annotations

from typing import Any

from simswarm.story_signals import build_story_signals
from simswarm.types import ActionRecord, GraphSnapshot

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FINDING_COLORS = ["#22D3EE", "#A78BFA", "#F97316", "#6EE7B7", "#FF6B6B", "#FBBF24"]


# ---------------------------------------------------------------------------
# Public adapter functions
# ---------------------------------------------------------------------------


def adapt_chat_log(chat_log: list[ActionRecord]) -> list[dict]:
    """Convert ActionRecords to dicts consumed by the SaaS frontend.

    agent_id is preserved as a string. (The old MiroShark-compat hashing was
    dropped after the engine cutover — extractors keep string agent_ids and
    the frontend never required int typing.)
    """
    result = []
    for record in chat_log:
        result.append({
            "round_num": record.round_num,
            "agent_id": record.agent_id,
            "agent_name": record.agent_name,
            "action_type": record.action_type,
            "platform": record.platform,
            "action_args": record.action_args,
            "action_result": record.action_result,
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
    forecast_days: int,
    verdict: str = "",
) -> dict:
    """Build the structured results dict consumed by the SaaS frontend.

    Args:
        brief: One-paragraph executive summary from the LLM.
        findings: List of {slot, title, body, citation, accent_color} from the LLM.
            (Legacy shape {title, content} is also accepted and re-shaped.)
        chat_log: Already-adapted chat log.
        graph_data: Already-adapted graph dict.
        forecast_days: Required timeline in days.
        verdict: One-sentence answer from the LLM.
    """
    adapted_findings: list[dict] = []
    for i, finding in enumerate(findings):
        if "slot" in finding:
            adapted_findings.append({
                "slot": finding["slot"],
                "title": finding.get("title", ""),
                "body": finding.get("body", ""),
                "citation": finding.get("citation", ""),
                "accent_color": finding.get("accent_color", FINDING_COLORS[i % len(FINDING_COLORS)]),
            })
        else:
            # Legacy path (during rollout): wrap the old {title, content} shape.
            slot = "industry" if i == 0 else ("regulator" if i == 1 else "intermediary")
            adapted_findings.append({
                "slot": slot,
                "title": finding.get("title", f"Finding {i + 1}"),
                "body": finding.get("content", "")[:500],
                "citation": "",
                "accent_color": FINDING_COLORS[i % len(FINDING_COLORS)],
            })

    signals = build_story_signals(chat_log, graph_data, forecast_days)

    return {
        "brief": brief,
        "verdict": verdict,
        "findings": adapted_findings,
        **signals,
    }
