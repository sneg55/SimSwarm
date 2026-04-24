"""Tests for simswarm.graph.build_graph — GraphSnapshot construction."""
from __future__ import annotations

from simswarm.graph import build_graph
from simswarm.types import ActionRecord, Entity


def _entity(id: str, name: str) -> Entity:
    return Entity(id=id, name=name, type="person", summary=f"{name} summary")


def _action(round_num: int, agent_id: str, agent_name: str, action_type: str,
            args: dict | None = None, success: bool = True, platform: str = "social",
            result: dict | None = None) -> ActionRecord:
    return ActionRecord(
        round_num=round_num, agent_id=agent_id, agent_name=agent_name,
        action_type=action_type, platform=platform,
        action_args=args or {}, success=success, action_result=result,
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


def _ents():
    return [
        Entity(id="a1", name="Alice", type="Person", summary=""),
        Entity(id="o1", name="OpenAI", type="Organization", summary=""),
        Entity(id="a2", name="Bob", type="Person", summary=""),
    ]


def test_metadata_entity_types_is_unique_sorted():
    g = build_graph(_ents(), chat_log=[])
    assert g.metadata["entity_types"] == ["Organization", "Person"]


def test_metadata_entity_types_empty_for_no_entities():
    g = build_graph([], chat_log=[])
    assert g.metadata["entity_types"] == []


# ---------------------------------------------------------------------------
# Regression: sim #128 edge-resolution gaps
# ---------------------------------------------------------------------------


def test_reply_via_post_id_resolves_to_original_author():
    """The social env records replies with only `post_id` as the target
    reference. Without a post→author hop, every reply silently drops."""
    entities = [_entity("alice", "Alice"), _entity("bob", "Bob")]
    chat_log = [
        _action(1, "alice", "Alice", "create_post", {"text": "hi"},
                result={"post_id": "p1"}),
        _action(2, "bob", "Bob", "reply", {"post_id": "p1", "text": "hey"},
                result={"post_id": "p2"}),
    ]
    graph = build_graph(entities, chat_log)
    reply_edges = [e for e in graph.edges if e["type"] == "reply"]
    assert len(reply_edges) == 1
    assert reply_edges[0]["source"] == "bob"
    assert reply_edges[0]["target"] == "alice"


def test_repost_via_post_id_resolves_to_original_author():
    entities = [_entity("alice", "Alice"), _entity("bob", "Bob")]
    chat_log = [
        _action(1, "alice", "Alice", "create_post", {"text": "hi"},
                result={"post_id": "p1"}),
        _action(2, "bob", "Bob", "repost", {"post_id": "p1"}),
    ]
    graph = build_graph(entities, chat_log)
    repost_edges = [e for e in graph.edges if e["type"] == "repost"]
    assert len(repost_edges) == 1
    assert repost_edges[0]["target"] == "alice"


def test_vote_value_1_becomes_like_edge():
    entities = [_entity("alice", "Alice"), _entity("bob", "Bob")]
    chat_log = [
        _action(1, "alice", "Alice", "create_post", {"text": "hi"},
                result={"post_id": "p1"}),
        _action(2, "bob", "Bob", "vote", {"post_id": "p1", "value": 1}),
    ]
    graph = build_graph(entities, chat_log)
    assert len(graph.edges) == 1
    assert graph.edges[0]["type"] == "like"
    assert graph.edges[0]["source"] == "bob"
    assert graph.edges[0]["target"] == "alice"


def test_vote_value_negative_becomes_dislike_edge():
    entities = [_entity("alice", "Alice"), _entity("bob", "Bob")]
    chat_log = [
        _action(1, "alice", "Alice", "create_post", {"text": "hi"},
                result={"post_id": "p1"}),
        _action(2, "bob", "Bob", "vote", {"post_id": "p1", "value": -1}),
    ]
    graph = build_graph(entities, chat_log)
    assert len(graph.edges) == 1
    assert graph.edges[0]["type"] == "dislike"


def test_follow_via_agent_id_arg_resolves():
    """Social env emits follow with arg key `agent_id`, not `target_id`."""
    entities = [_entity("alice", "Alice"), _entity("bob", "Bob")]
    chat_log = [_action(1, "alice", "Alice", "follow", {"agent_id": "bob"})]
    graph = build_graph(entities, chat_log)
    assert len(graph.edges) == 1
    assert graph.edges[0]["target"] == "bob"
    assert graph.edges[0]["type"] == "follow"


def test_multi_word_entity_label_mention_in_post_text():
    """Entities with multi-word names (e.g. "US Navy") can't be @-mentioned,
    but full-label references in post prose should still produce edges."""
    entities = [_entity("donald_trump", "Donald Trump"),
                _entity("us_navy", "US Navy")]
    chat_log = [
        _action(1, "donald_trump", "Donald Trump", "create_post",
                {"text": "The US Navy is the strongest in the world."}),
    ]
    graph = build_graph(entities, chat_log)
    mention_edges = [e for e in graph.edges if e["type"] == "mention"]
    assert len(mention_edges) == 1
    assert mention_edges[0]["source"] == "donald_trump"
    assert mention_edges[0]["target"] == "us_navy"


def test_full_label_mention_respects_word_boundary():
    """"Alice" should not match inside "Alicent"."""
    entities = [_entity("alice", "Alice"), _entity("bob", "Bob")]
    chat_log = [
        _action(1, "bob", "Bob", "create_post",
                {"text": "Alicent is a different person entirely."}),
    ]
    graph = build_graph(entities, chat_log)
    assert graph.edges == []


def test_full_label_mention_is_case_insensitive():
    entities = [_entity("alice", "Alice"), _entity("bob", "Bob")]
    chat_log = [
        _action(1, "bob", "Bob", "create_post", {"text": "talking to ALICE now"}),
    ]
    graph = build_graph(entities, chat_log)
    mention_edges = [e for e in graph.edges if e["type"] == "mention"]
    assert len(mention_edges) == 1
    assert mention_edges[0]["target"] == "alice"


def test_post_author_index_skips_failed_posts():
    """A failed create_post must not populate the post→author index,
    otherwise a later reply to that post_id would resolve spuriously."""
    entities = [_entity("alice", "Alice"), _entity("bob", "Bob")]
    chat_log = [
        _action(1, "alice", "Alice", "create_post", {"text": "hi"},
                result={"post_id": "p1"}, success=False),
        _action(2, "bob", "Bob", "reply", {"post_id": "p1", "text": "hey"}),
    ]
    graph = build_graph(entities, chat_log)
    # Bob's reply can't resolve → no edge.
    assert graph.edges == []
