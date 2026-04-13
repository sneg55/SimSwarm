"""Graph construction from simulation output.

Replaces the old MiroShark Neo4j ingestion path. Pure-Python: takes the
post-sim ActionRecord list + the Entity list the sim ran on, returns a
GraphSnapshot the SaaS layer can render in Cytoscape.

Nodes = agents (one per Entity used). Edges = interactions extracted from
chat_log: follow, reply, mention, like. Repeated interactions between the
same pair collapse into one edge with `weight = count`.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from simswarm.types import ActionRecord, Entity, GraphSnapshot

# Action types that signal a directed interaction between two agents.
# Values are the edge `type` label.
_INTERACTION_ACTIONS = {
    "follow": "follow",
    "reply": "reply",
    "like": "like",
    "like_post": "like",
    "repost": "repost",
    "retweet": "repost",
    "quote": "quote",
    "mention": "mention",
}

# Which `action_args` key names carry the target agent. We check these in
# order and take the first match.
_TARGET_ARG_KEYS = ("target_id", "target_agent", "target_name", "target",
                    "to", "recipient", "post_author")

# Matches @-mentions in post text. Simswarm agent names can have spaces,
# so we only detect tight single-word mentions here (full-name mentions
# are resolved below via the name lookup).
_MENTION_RE = re.compile(r"@(\w+)")


def build_graph(entities: list[Entity], chat_log: list[ActionRecord]) -> GraphSnapshot:
    """Return a GraphSnapshot populated from the simulation's entities + chat log."""
    nodes = _build_nodes(entities, chat_log)
    id_by_name = {n["label"]: n["id"] for n in nodes}
    edges = _build_edges(chat_log, id_by_name)
    metadata = {
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "total_rounds": max((a.round_num for a in chat_log), default=0),
    }
    return GraphSnapshot(nodes=nodes, edges=edges, metadata=metadata)


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


def _build_nodes(
    entities: list[Entity],
    chat_log: list[ActionRecord],
) -> list[dict[str, Any]]:
    # Pre-compute per-agent activity stats from chat_log.
    stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"total_actions": 0, "total_posts": 0, "rounds": set()}
    )
    for action in chat_log:
        s = stats[action.agent_id]
        s["total_actions"] += 1
        s["rounds"].add(action.round_num)
        if action.action_type.lower() in ("create_post", "post", "comment"):
            s["total_posts"] += 1

    nodes: list[dict[str, Any]] = []
    for entity in entities:
        s = stats.get(entity.id, {"total_actions": 0, "total_posts": 0, "rounds": set()})
        nodes.append({
            "id": entity.id,
            "label": entity.name,
            "group": entity.type,
            "summary": entity.summary,
            "total_actions": s["total_actions"],
            "total_posts": s["total_posts"],
            "rounds_active": len(s["rounds"]),
        })
    return nodes


# ---------------------------------------------------------------------------
# Edges
# ---------------------------------------------------------------------------


def _build_edges(
    chat_log: list[ActionRecord],
    id_by_name: dict[str, str],
) -> list[dict[str, Any]]:
    # (source_id, target_id, type) -> weight
    tallies: dict[tuple[str, str, str], int] = defaultdict(int)

    for action in chat_log:
        if not action.success:
            continue
        edge_type = _INTERACTION_ACTIONS.get(action.action_type.lower())
        if edge_type:
            target_id = _resolve_target(action, id_by_name)
            if target_id and target_id != action.agent_id:
                tallies[(action.agent_id, target_id, edge_type)] += 1
            continue

        # Post content may contain @mentions even when the action itself isn't
        # tagged as a mention. Only scan post-ish actions.
        if action.action_type.lower() in ("create_post", "post", "comment", "reply"):
            text = (action.action_args or {}).get("text") or \
                (action.action_args or {}).get("content") or ""
            for handle in _MENTION_RE.findall(text or ""):
                target_id = id_by_name.get(handle)
                if target_id and target_id != action.agent_id:
                    tallies[(action.agent_id, target_id, "mention")] += 1

    return [
        {"source": src, "target": tgt, "type": kind, "weight": weight}
        for (src, tgt, kind), weight in tallies.items()
    ]


def _resolve_target(
    action: ActionRecord,
    id_by_name: dict[str, str],
) -> str | None:
    args = action.action_args or {}
    for key in _TARGET_ARG_KEYS:
        raw = args.get(key)
        if not raw:
            continue
        raw = str(raw).strip()
        if not raw:
            continue
        # Direct id match
        if raw in id_by_name.values():
            return raw
        # Name match (common case: target_name="Yann LeCun")
        if raw in id_by_name:
            return id_by_name[raw]
    return None
