"""Full coverage tests for saas.utils.sentiment."""
from saas.utils.sentiment import (
    score_entity_sentiment,
    needs_sentiment_backfill,
)


def _graph(*names):
    return {"nodes": [{"uuid": f"n{i}", "name": n} for i, n in enumerate(names)], "edges": []}


def _entry(agent, content):
    return {"agent_name": agent, "action_type": "CREATE_POST", "action_args": {"content": content}}


def test_empty_nodes_returns_early():
    g = {"nodes": [], "edges": []}
    score_entity_sentiment(g, [{"agent_name": "A", "action_args": {"content": "support"}}])
    assert g["nodes"] == []


def test_positive_mentions_yield_positive_score():
    g = _graph("Alice")
    log = [_entry("Bob", "Alice shows support and growth and progress")]
    score_entity_sentiment(g, log)
    assert g["nodes"][0]["sentiment"] > 0


def test_negative_mentions_yield_negative_score():
    g = _graph("Bob")
    log = [_entry("A", "Bob faces crisis, collapse, and risk")]
    score_entity_sentiment(g, log)
    assert g["nodes"][0]["sentiment"] < 0


def test_unmentioned_entity_gets_zero():
    g = _graph("Dave")
    log = [_entry("A", "Alice shows support")]
    score_entity_sentiment(g, log)
    assert g["nodes"][0]["sentiment"] == 0.0


def test_empty_content_skipped():
    g = _graph("Alice")
    log = [{"agent_name": "Alice", "action_args": {"content": ""}}]
    score_entity_sentiment(g, log)
    assert g["nodes"][0]["sentiment"] == 0.0


def test_missing_action_args_handled():
    g = _graph("Alice")
    log = [{"agent_name": "Alice"}]  # no action_args
    score_entity_sentiment(g, log)
    assert g["nodes"][0]["sentiment"] == 0.0


def test_node_without_name_ignored():
    g = {"nodes": [{"uuid": "n0", "name": ""}, {"uuid": "n1", "name": "Alice"}], "edges": []}
    log = [_entry("B", "Alice enjoys support and growth")]
    score_entity_sentiment(g, log)
    assert g["nodes"][0]["sentiment"] == 0.0
    assert g["nodes"][1]["sentiment"] > 0


def test_agent_name_match_alone_scores_entity():
    g = _graph("Alice")
    log = [_entry("Alice", "today is a day of support and growth")]
    score_entity_sentiment(g, log)
    assert g["nodes"][0]["sentiment"] > 0


def test_score_is_clamped_between_neg1_and_1():
    g = _graph("Zara")
    log = [_entry("X", "Zara is wonderful, excellent, fantastic, and a great success!")]
    score_entity_sentiment(g, log)
    s = g["nodes"][0]["sentiment"]
    assert -1.0 <= s <= 1.0


def test_mixed_sentiment_between_bounds():
    g = _graph("Eve")
    log = [_entry("X", "Eve shows support but faces crisis and risk")]
    score_entity_sentiment(g, log)
    s = g["nodes"][0]["sentiment"]
    assert -1.0 <= s <= 1.0


def test_needs_backfill_no_nodes():
    assert needs_sentiment_backfill({"nodes": []}) is False


def test_needs_backfill_missing_sentiment():
    assert needs_sentiment_backfill({"nodes": [{"name": "A"}]}) is True


def test_needs_backfill_has_sentiment():
    assert needs_sentiment_backfill({"nodes": [{"name": "A", "sentiment": 0.3}]}) is False


def test_multiple_entries_accumulate():
    g = _graph("Alice")
    log = [
        _entry("X", "Alice shows support"),
        _entry("X", "Alice shows growth"),
    ]
    score_entity_sentiment(g, log)
    assert g["nodes"][0]["sentiment"] > 0
