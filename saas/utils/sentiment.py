"""Per-entity sentiment scoring via VADER.

For each chat-log entry we compute a VADER compound score in [-1, 1]
and attribute it to every graph entity mentioned in that entry. Each
node's final sentiment is the mean of scores from entries where it
was mentioned (or 0.0 if it was never mentioned).
"""
from __future__ import annotations

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_VADER = SentimentIntensityAnalyzer()


def score_entity_sentiment(graph_data: dict, chat_log: list[dict]) -> None:
    """Score each graph node's sentiment by analyzing chat_log mentions.

    Mutates graph_data["nodes"] in place, adding a "sentiment" float field
    (-1.0 to +1.0) to each node.
    """
    nodes = graph_data.get("nodes", [])
    if not nodes:
        return

    name_to_indices: dict[str, list[int]] = {}
    for i, node in enumerate(nodes):
        name = node.get("name", "").strip()
        if name:
            name_to_indices.setdefault(name.lower(), []).append(i)

    scores: dict[int, list[float]] = {}

    for entry in chat_log:
        args = entry.get("action_args") or {}
        content = args.get("text") or args.get("content") or ""
        if not content:
            continue
        content_lower = content.lower()
        agent_name = (entry.get("agent_name") or "").strip().lower()

        matched_indices: set[int] = set()
        for entity_name, indices in name_to_indices.items():
            if entity_name in content_lower:
                matched_indices.update(indices)
            if agent_name and agent_name == entity_name:
                matched_indices.update(indices)

        if not matched_indices:
            continue

        compound = _VADER.polarity_scores(content)["compound"]
        for idx in matched_indices:
            scores.setdefault(idx, []).append(compound)

    for i, node in enumerate(nodes):
        vals = scores.get(i)
        if not vals:
            node["sentiment"] = 0.0
        else:
            node["sentiment"] = round(sum(vals) / len(vals), 2)


def needs_sentiment_backfill(graph_data: dict) -> bool:
    """Return True if graph nodes exist but none have a sentiment field."""
    nodes = graph_data.get("nodes", [])
    if not nodes:
        return False
    return not any("sentiment" in n for n in nodes)
