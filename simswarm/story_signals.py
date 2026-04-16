"""Deterministic extraction of Story signals from chat_log + graph_data.

Pure functions only. No LLM calls, no I/O. The output feeds both the Story
view directly and the report.j2 prompt as grounding context.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
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


def _classify_stance(text: str) -> str:
    """Return 'opposed' | 'supports' | 'neutral' | 'split' based on keyword signals."""
    lowered = text.lower()
    has_opposed = any(kw in lowered for kw in OPPOSED_SIGNALS)
    has_support = any(kw in lowered for kw in SUPPORT_SIGNALS)
    if has_opposed and has_support:
        return "split"
    if has_opposed:
        return "opposed"
    if has_support:
        return "supports"
    return "neutral"


def _post_text(action: dict[str, Any]) -> str:
    args = action.get("action_args") or {}
    return args.get("text") or args.get("content") or ""


def _agent_dominant_stance(agent_posts: list[dict[str, Any]]) -> str:
    """A single agent's overall stance = majority stance across their posts."""
    if not agent_posts:
        return "neutral"
    counts = Counter(_classify_stance(_post_text(p)) for p in agent_posts)
    # Drop neutral when any directional stance exists — neutral shouldn't win by default.
    directional = {k: v for k, v in counts.items() if k != "neutral"}
    if directional:
        return max(directional.items(), key=lambda kv: kv[1])[0]
    return "neutral"


def _top_keywords(texts: list[str], limit: int = 3) -> list[str]:
    """Top non-stopword tokens across a bag of texts."""
    stopwords = {"the", "a", "an", "is", "are", "to", "of", "for", "and", "or",
                 "in", "on", "we", "our", "this", "that", "it", "be", "by",
                 "with", "as", "at", "from", "will", "not", "but"}
    tokens: Counter[str] = Counter()
    for t in texts:
        for word in re.findall(r"[a-z][a-z\-]{3,}", t.lower()):
            if word not in stopwords:
                tokens[word] += 1
    return [w for w, _ in tokens.most_common(limit)]


_STANCE_BLOC_NAME = {
    "opposed":  "Opposition bloc",
    "supports": "Support bloc",
    "neutral":  "Neutral bloc",
    "split":    "Split bloc",
}


def extract_stakeholder_positions(chat_log: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Cluster agents by dominant stance and return stakeholder position dicts."""
    posts_by_agent: dict[str, list[dict]] = defaultdict(list)
    for action in chat_log:
        if action.get("action_type") in ("CREATE_POST", "CREATE_COMMENT"):
            posts_by_agent[action.get("agent_name", "")].append(action)

    agent_stances: dict[str, str] = {
        name: _agent_dominant_stance(posts) for name, posts in posts_by_agent.items() if name
    }

    buckets: dict[str, list[str]] = defaultdict(list)
    for name, stance in agent_stances.items():
        buckets[stance].append(name)

    positions: list[dict[str, Any]] = []
    for stance, members in buckets.items():
        if not members:
            continue
        bucket_texts: list[str] = []
        for name in members:
            bucket_texts.extend(_post_text(p) for p in posts_by_agent[name])
        positions.append({
            "name": _STANCE_BLOC_NAME[stance],
            "stance": stance,
            "members": sorted(members),
            "member_count": len(members),
            "rationale_keywords": _top_keywords(bucket_texts, limit=3),
        })
    # Stable order: opposed, supports, split, neutral
    order = {"opposed": 0, "supports": 1, "split": 2, "neutral": 3}
    positions.sort(key=lambda p: order.get(p["stance"], 99))
    return positions


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
