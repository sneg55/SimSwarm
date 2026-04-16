"""Deterministic extraction of Story signals from chat_log + graph_data.

Pure functions only. No LLM calls, no I/O. The output feeds both the Story
view directly and the report.j2 prompt as grounding context.
"""
from __future__ import annotations

from typing import Any

# Curated stance-signal keyword sets. Extracted from a corpus of prod goals
# (policy/markets/crisis/competitive/public-opinion verticals). These are
# intentionally conservative — a post that triggers neither set is neutral.
OPPOSED_SIGNALS: frozenset[str] = frozenset({
    "oppose", "against", "reject", "block", "resist", "pushback",
    "overreach", "mandate", "prescriptive", "burden", "compliance cost",
    "unworkable", "chilling", "harmful",
})

SUPPORT_SIGNALS: frozenset[str] = frozenset({
    "support", "endorse", "align with", "back the", "welcome", "approve",
    "transparency", "accountability", "standardized", "enforce",
    "strengthen", "clarity",
})

# Phase accent colors — aligned with tailwind.config.js tokens. Public so
# saas/jobs/report.py can tag LLM-produced findings with the correct hex
# without duplicating the mapping.
SLOT_COLORS: dict[str, str] = {
    "industry":      "#F97316",  # coral-amber
    "regulator":     "#22D3EE",  # ocean-glow
    "intermediary":  "#A78BFA",  # organic-violet
    "market":        "#6EE7B7",  # organic-seafoam
    "turning_point": "#FF6B6B",  # coral
}


def build_story_signals(
    chat_log: list[dict[str, Any]],
    graph_data: dict[str, Any],
    forecast_days: int,
) -> dict[str, Any]:
    """Top-level entry. Returns the deterministic signals dict.

    Args:
        chat_log: List of dicts matching the ActionRecord schema serialized
            to MinIO (i.e., already-parsed JSON). Each row has keys
            round_num, agent_id, agent_name, action_type, platform,
            action_args, timestamp, success. Post body lives at
            action_args["text"] (or action_args["content"] for legacy rows).
        graph_data: {"nodes": [...], "edges": [...], "metadata": {...}} dict.
        forecast_days: User-chosen horizon from JobCreate; required.

    Shape (see spec for full schema):
        {
            "stakeholder_positions": [...],
            "disagreement_axis": str,
            "quotable_posts": [...],
            "named_coalitions": [...],
            "phase_boundaries": [...],
            "sim_scale": {...},
        }
    """
    raise NotImplementedError
