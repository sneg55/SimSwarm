"""Tests for simswarm.graph.build_graph — GraphSnapshot construction."""
from __future__ import annotations

import pytest

from simswarm.graph import build_graph
from simswarm.types import ActionRecord, Entity


def _entity(id: str, name: str) -> Entity:
    return Entity(id=id, name=name, type="person", summary=f"{name} summary")


def _action(round_num: int, agent_id: str, agent_name: str, action_type: str,
            args: dict | None = None, success: bool = True, platform: str = "social") -> ActionRecord:
    return ActionRecord(
        round_num=round_num, agent_id=agent_id, agent_name=agent_name,
        action_type=action_type, platform=platform,
        action_args=args or {}, success=success,
    )


def test_empty_chat_log_returns_entity_nodes_with_zero_stats():
    entities = [_entity("alice", "Alice"), _entity("bob", "Bob")]
    graph = build_graph(entities, [])

    assert len(graph.nodes) == 2
    alice = next(n for n in graph.nodes if n["id"] == "alice")
    assert alice["label"] == "Alice"
    assert alice["group"] == "person"
    assert alice["total_actions"] == 0
    assert alice["total_posts"] == 0
    assert alice["rounds_active"] == 0
    assert graph.edges == []
    assert graph.metadata["total_nodes"] == 2
    assert graph.metadata["total_edges"] == 0
    assert graph.metadata["total_rounds"] == 0


def test_node_stats_from_chat_log():
    entities = [_entity("a", "Alice")]
    chat_log = [
        _action(1, "a", "Alice", "create_post", {"text": "hi"}),
        _action(2, "a", "Alice", "create_post", {"text": "again"}),
        _action(3, "a", "Alice", "browse_markets"),
    ]
    graph = build_graph(entities, chat_log)
    alice = graph.nodes[0]
    assert alice["total_actions"] == 3
    assert alice["total_posts"] == 2
    assert alice["rounds_active"] == 3
    assert graph.metadata["total_rounds"] == 3


def test_follow_edges_resolved_by_target_id():
    entities = [_entity("alice", "Alice"), _entity("bob", "Bob")]
    chat_log = [
        _action(1, "alice", "Alice", "follow", {"target_id": "bob"}),
    ]
    graph = build_graph(entities, chat_log)
    assert len(graph.edges) == 1
    edge = graph.edges[0]
    assert edge["source"] == "alice"
    assert edge["target"] == "bob"
    assert edge["type"] == "follow"
    assert edge["weight"] == 1


def test_follow_edges_resolved_by_target_name():
    entities = [_entity("alice", "Alice"), _entity("bob", "Bob")]
    chat_log = [
        _action(1, "alice", "Alice", "follow", {"target_name": "Bob"}),
    ]
    graph = build_graph(entities, chat_log)
    assert len(graph.edges) == 1
    assert graph.edges[0]["target"] == "bob"


def test_repeated_interactions_collapse_into_single_edge_with_weight():
    entities = [_entity("alice", "Alice"), _entity("bob", "Bob")]
    chat_log = [
        _action(1, "alice", "Alice", "follow", {"target_id": "bob"}),
        _action(2, "alice", "Alice", "follow", {"target_id": "bob"}),
        _action(3, "alice", "Alice", "like", {"target_id": "bob"}),
    ]
    graph = build_graph(entities, chat_log)
    # follow x2 and like x1 are separate edge types
    assert len(graph.edges) == 2
    by_type = {e["type"]: e for e in graph.edges}
    assert by_type["follow"]["weight"] == 2
    assert by_type["like"]["weight"] == 1


def test_failed_actions_dont_create_edges():
    entities = [_entity("alice", "Alice"), _entity("bob", "Bob")]
    chat_log = [
        _action(1, "alice", "Alice", "follow", {"target_id": "bob"}, success=False),
    ]
    graph = build_graph(entities, chat_log)
    assert graph.edges == []


def test_self_loop_edges_are_filtered():
    entities = [_entity("alice", "Alice")]
    chat_log = [
        _action(1, "alice", "Alice", "follow", {"target_id": "alice"}),
    ]
    graph = build_graph(entities, chat_log)
    assert graph.edges == []


def test_at_mentions_in_post_text_create_mention_edges():
    entities = [_entity("alice", "Alice"), _entity("Bob", "Bob")]
    chat_log = [
        _action(1, "alice", "Alice", "create_post", {"text": "hey @Bob nice take"}),
    ]
    graph = build_graph(entities, chat_log)
    mention_edges = [e for e in graph.edges if e["type"] == "mention"]
    assert len(mention_edges) == 1
    assert mention_edges[0]["source"] == "alice"
    assert mention_edges[0]["target"] == "Bob"


def test_unresolved_target_does_not_crash():
    entities = [_entity("alice", "Alice")]
    chat_log = [
        _action(1, "alice", "Alice", "follow", {"target_id": "ghost"}),
    ]
    graph = build_graph(entities, chat_log)
    assert graph.edges == []
