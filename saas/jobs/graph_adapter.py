"""Translate native-engine graph payloads into the Graphiti-compatible shape
the Vue frontend expects.

After the MiroShark cutover, ``simswarm/graph.py`` emits:
    nodes: {id, label, group, summary, total_actions, total_posts, rounds_active}
    edges: {source, target, type, weight}

The frontend (GraphCanvas.vue, GraphDetailPanel.vue, useSimulationData.js)
was built against the pre-cutover Graphiti shape:
    nodes: {uuid, name, labels[], summary, connection_count, sentiment}
    edges: {source_node_uuid, target_node_uuid, source_node_name,
            target_node_name, name, fact}

Rather than rewriting the native builder or the frontend, we adapt once
here. Already-Graphiti-shaped payloads (jobs created pre-cutover) pass
through untouched.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any


def adapt_graph_payload(raw: dict[str, Any]) -> dict[str, Any]:
    """Return *raw* enriched with frontend-compatible node/edge field aliases.

    Passes through unchanged if the payload is already in Graphiti shape
    (first node has a ``uuid`` key).
    """
    nodes = raw.get("nodes") or []
    edges = raw.get("edges") or []

    if nodes and "uuid" in nodes[0]:
        return raw  # already Graphiti-shaped

    conn_count: dict[str, int] = defaultdict(int)
    for e in edges:
        src = e.get("source")
        tgt = e.get("target")
        if src:
            conn_count[src] += 1
        if tgt:
            conn_count[tgt] += 1

    name_by_id = {n.get("id"): n.get("label") for n in nodes if n.get("id")}

    adapted_nodes = [_adapt_node(n, conn_count) for n in nodes]
    adapted_edges = [_adapt_edge(e, name_by_id) for e in edges]

    return {
        "nodes": adapted_nodes,
        "edges": adapted_edges,
        "metadata": raw.get("metadata", {}),
    }


def _adapt_node(n: dict[str, Any], conn_count: dict[str, int]) -> dict[str, Any]:
    nid = n.get("id", "")
    group = n.get("group") or "Entity"
    return {
        **n,
        "uuid": nid,
        "name": n.get("label") or n.get("name") or nid,
        "labels": [group] if isinstance(group, str) else list(group or ["Entity"]),
        "connection_count": conn_count.get(nid, 0),
        # Native engine does not currently surface per-entity sentiment; emit 0.0
        # so the frontend reads the field rather than crashing on undefined.
        "sentiment": n.get("sentiment", 0.0),
    }


def _adapt_edge(e: dict[str, Any], name_by_id: dict[str, str]) -> dict[str, Any]:
    src = e.get("source", "")
    tgt = e.get("target", "")
    etype = e.get("type", "")
    # LLM-extracted relation edges carry a real `fact`; interaction edges
    # (follow/like/mention) only have a type — fall back to the type label.
    fact = e.get("fact") or etype
    return {
        **e,
        "source_node_uuid": src,
        "target_node_uuid": tgt,
        "source_node_name": name_by_id.get(src, ""),
        "target_node_name": name_by_id.get(tgt, ""),
        "name": etype,
        "fact": fact,
    }
