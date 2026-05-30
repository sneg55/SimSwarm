"""Graph construction from simulation output.

Pure-Python graph builder: takes the
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
# Values are the edge `type` label. `vote` is special-cased in _build_edges
# to branch on args.value (1=like, -1=dislike).
_INTERACTION_ACTIONS = {
    "follow": "follow",
    "reply": "reply",
    "like": "like",
    "like_post": "like",
    "repost": "repost",
    "retweet": "repost",
    "quote": "quote",
    "mention": "mention",
    "vote": "like",
}

# Which `action_args` key names carry the target agent. Checked in order,
# first non-empty match wins. `post_id` routes through the post→author
# index (built from prior create_post/reply actions in the chat log).
_TARGET_ARG_KEYS = ("target_id", "target_agent", "target_name", "target",
                    "to", "recipient", "post_author", "agent_id", "post_id")

# Matches @-mentions in post text (single-token handles like @alice).
_MENTION_RE = re.compile(r"@(\w+)")


def build_graph(
    entities: list[Entity],
    chat_log: list[ActionRecord],
    relations: list[dict] | None = None,
) -> GraphSnapshot:
    """Return a GraphSnapshot populated from the simulation's entities + chat log.

    *relations*, when provided, is a list of dicts with keys ``source``,
    ``target`` (entity names), ``type`` (edge label), and optional ``fact``.
    These typed semantic edges are merged alongside the follow/like/mention
    interaction edges derived from the chat log. This is how the post-cutover
    pipeline restores the Graphiti-era knowledge-graph relations the frontend
    renders on the Graph tab.
    """
    nodes = _build_nodes(entities, chat_log)
    id_by_name = {n["label"]: n["id"] for n in nodes}
    post_author = _build_post_author_index(chat_log)
    edges = _build_edges(chat_log, id_by_name, post_author)
    if relations:
        edges.extend(_relations_to_edges(relations, id_by_name))
    metadata = {
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "total_rounds": max((a.round_num for a in chat_log), default=0),
        "entity_types": sorted({e.type for e in entities}),
    }
    return GraphSnapshot(nodes=nodes, edges=edges, metadata=metadata)


def _relations_to_edges(
    relations: list[dict],
    id_by_name: dict[str, str],
) -> list[dict[str, Any]]:
    """Map LLM-extracted relations (keyed by entity *name*) to graph edges
    keyed by entity *id*. Drops rows whose endpoints don't map."""
    out: list[dict[str, Any]] = []
    for r in relations:
        src_id = id_by_name.get(r.get("source", ""))
        tgt_id = id_by_name.get(r.get("target", ""))
        rtype = str(r.get("type", "")).strip()
        if not src_id or not tgt_id or not rtype or src_id == tgt_id:
            continue
        edge = {
            "source": src_id,
            "target": tgt_id,
            "type": rtype,
            "weight": 1,
        }
        fact = r.get("fact")
        if fact:
            edge["fact"] = str(fact)
        out.append(edge)
    return out


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


def _build_post_author_index(chat_log: list[ActionRecord]) -> dict[str, str]:
    """Map post_id → agent_id of the post's author.

    Built from prior create_post/reply actions so downstream reply/
    repost/vote actions (whose only target reference is a post UUID)
    can resolve back to the authoring agent.
    """
    index: dict[str, str] = {}
    for action in chat_log:
        if not action.success:
            continue
        if action.action_type.lower() not in ("create_post", "post", "reply", "comment"):
            continue
        result = action.action_result or {}
        post_id = result.get("post_id") if isinstance(result, dict) else None
        if post_id:
            index[str(post_id)] = action.agent_id
    return index


def _build_edges(
    chat_log: list[ActionRecord],
    id_by_name: dict[str, str],
    post_author: dict[str, str],
) -> list[dict[str, Any]]:
    # (source_id, target_id, type) -> weight
    tallies: dict[tuple[str, str, str], int] = defaultdict(int)
    agent_ids = set(id_by_name.values())

    for action in chat_log:
        if not action.success:
            continue
        action_type = action.action_type.lower()
        edge_type = _INTERACTION_ACTIONS.get(action_type)
        if edge_type:
            # Votes carry a polarity in args.value — negative votes are dislikes.
            if action_type == "vote":
                try:
                    value = int((action.action_args or {}).get("value", 1))
                except (TypeError, ValueError):
                    value = 1
                edge_type = "like" if value >= 0 else "dislike"
            target_id = _resolve_target(action, id_by_name, post_author, agent_ids)
            if target_id and target_id != action.agent_id:
                tallies[(action.agent_id, target_id, edge_type)] += 1
            continue

        # Post content: @handles and full-name entity mentions.
        if action_type in ("create_post", "post", "comment", "reply"):
            text = (action.action_args or {}).get("text") or \
                (action.action_args or {}).get("content") or ""
            for target_id in _scan_mentions(text, id_by_name):
                if target_id != action.agent_id:
                    tallies[(action.agent_id, target_id, "mention")] += 1

    return [
        {"source": src, "target": tgt, "type": kind, "weight": weight}
        for (src, tgt, kind), weight in tallies.items()
    ]


def _scan_mentions(
    text: str,
    id_by_name: dict[str, str],
) -> list[str]:
    """Return agent ids referenced in *text* by @handle or by full entity label.

    @handle match uses the per-token regex. Full-label match is case-
    insensitive with word boundaries, so multi-word names ("US Navy",
    "Donald Trump") that the @handle regex misses are still picked up.
    Each distinct target appears at most once per scan (dedup)."""
    if not text:
        return []
    found: list[str] = []
    seen: set[str] = set()
    for handle in _MENTION_RE.findall(text):
        tid = id_by_name.get(handle)
        if tid and tid not in seen:
            seen.add(tid)
            found.append(tid)
    lowered = text.lower()
    for name, tid in id_by_name.items():
        if tid in seen:
            continue
        needle = name.lower()
        if not needle or needle not in lowered:
            continue
        # word-boundary check around each occurrence
        pattern = r"\b" + re.escape(needle) + r"\b"
        if re.search(pattern, lowered):
            seen.add(tid)
            found.append(tid)
    return found


def _resolve_target(
    action: ActionRecord,
    id_by_name: dict[str, str],
    post_author: dict[str, str] | None = None,
    agent_ids: set[str] | None = None,
) -> str | None:
    args = action.action_args or {}
    agent_ids = agent_ids if agent_ids is not None else set(id_by_name.values())
    post_author = post_author or {}
    for key in _TARGET_ARG_KEYS:
        raw = args.get(key)
        if not raw:
            continue
        raw = str(raw).strip()
        if not raw:
            continue
        # post_id → author hop
        if key == "post_id":
            author = post_author.get(raw)
            if author and author in agent_ids:
                return author
            continue
        # Direct id match
        if raw in agent_ids:
            return raw
        # Name match (common case: target_name="Yann LeCun")
        if raw in id_by_name:
            return id_by_name[raw]
    return None
