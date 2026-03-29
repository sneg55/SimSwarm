"""Per-entity sentiment scoring (keyword lexicon, no LLM).

Extracted from infra/docker/run_job.py so it can be reused for
lazy backfilling of old jobs that predate the sentiment feature.
"""
from __future__ import annotations

import re

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
    """Score each graph node's sentiment by analyzing chat_log mentions.

    Mutates graph_data["nodes"] in place, adding a "sentiment" float field
    (-1.0 to +1.0) to each node.
    """
    nodes = graph_data.get("nodes", [])
    if not nodes:
        return

    # Build lookup: lowercase entity name -> node index(es)
    name_to_indices: dict[str, list[int]] = {}
    for i, node in enumerate(nodes):
        name = node.get("name", "").strip()
        if name:
            name_to_indices.setdefault(name.lower(), []).append(i)

    # Accumulate sentiment scores per node index
    pos_counts: dict[int, int] = {}
    neg_counts: dict[int, int] = {}

    for entry in chat_log:
        content = (entry.get("action_args") or {}).get("content", "")
        if not content:
            continue
        content_lower = content.lower()
        agent_name = (entry.get("agent_name") or "").strip().lower()

        # Count positive/negative words in this entry (strip punctuation)
        words = set(re.findall(r'\b[a-z]+\b', content_lower))
        pos = len(words & POSITIVE_WORDS)
        neg = len(words & NEGATIVE_WORDS)

        # Find which entities are mentioned in this content
        matched_indices: set[int] = set()
        for entity_name, indices in name_to_indices.items():
            if entity_name in content_lower:
                matched_indices.update(indices)
            if agent_name and agent_name == entity_name:
                matched_indices.update(indices)

        for idx in matched_indices:
            pos_counts[idx] = pos_counts.get(idx, 0) + pos
            neg_counts[idx] = neg_counts.get(idx, 0) + neg

    # Compute sentiment score per node
    for i, node in enumerate(nodes):
        p = pos_counts.get(i, 0)
        n = neg_counts.get(i, 0)
        total = p + n
        if total == 0:
            node["sentiment"] = 0.0
        else:
            node["sentiment"] = round(max(-1.0, min(1.0, (p - n) / total)), 2)


def needs_sentiment_backfill(graph_data: dict) -> bool:
    """Return True if graph nodes exist but none have a sentiment field."""
    nodes = graph_data.get("nodes", [])
    if not nodes:
        return False
    return not any("sentiment" in n for n in nodes)
