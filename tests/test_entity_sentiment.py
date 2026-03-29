"""Tests for score_entity_sentiment — keyword-based per-entity sentiment scoring."""
from __future__ import annotations

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Import the function under test from infra/docker/run_job.py without
# triggering MiroFish imports (they require a GPU environment).
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def run_job_module():
    """Import run_job.py constants + functions via exec (avoids MiroFish deps)."""
    spec_path = Path(__file__).resolve().parent.parent / "infra" / "docker" / "run_job.py"
    source = spec_path.read_text()
    ns = {"__builtins__": __builtins__}
    exec(compile(source, str(spec_path), "exec"), ns)
    return ns


@pytest.fixture()
def score_fn(run_job_module):
    return run_job_module["score_entity_sentiment"]


# ---------------------------------------------------------------------------
# Helper to build graph data + chat_log quickly
# ---------------------------------------------------------------------------

def _graph(*names: str) -> dict:
    """Build minimal graph_data with the given node names."""
    return {
        "nodes": [{"uuid": f"n{i}", "name": name} for i, name in enumerate(names)],
        "edges": [],
    }


def _entry(agent: str, content: str) -> dict:
    """Build a single chat_log entry."""
    return {
        "agent_name": agent,
        "action_type": "CREATE_POST",
        "action_args": {"content": content},
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPositiveSentiment:
    def test_positive_mentions_give_positive_score(self, score_fn):
        """Entity mentioned alongside positive words gets a positive sentiment."""
        graph = _graph("Alice")
        chat_log = [
            _entry("Bob", "Alice shows great support and progress in her work"),
            _entry("Carol", "Alice continues to achieve success and growth"),
        ]
        score_fn(graph, chat_log)
        assert graph["nodes"][0]["sentiment"] > 0


class TestNegativeSentiment:
    def test_negative_mentions_give_negative_score(self, score_fn):
        """Entity mentioned alongside negative words gets a negative sentiment."""
        graph = _graph("Bob")
        chat_log = [
            _entry("Alice", "Bob faces crisis and conflict with growing tension"),
            _entry("Carol", "Bob may fail and collapse under the risk"),
        ]
        score_fn(graph, chat_log)
        assert graph["nodes"][0]["sentiment"] < 0


class TestNoMentions:
    def test_no_mentions_give_zero(self, score_fn):
        """Entity never mentioned in chat_log gets 0.0 sentiment."""
        graph = _graph("Dave")
        chat_log = [
            _entry("Alice", "Bob shows great support and positive progress"),
        ]
        score_fn(graph, chat_log)
        assert graph["nodes"][0]["sentiment"] == 0.0


class TestMixedSentiment:
    def test_mixed_mentions_between_minus_one_and_one(self, score_fn):
        """Entity with both positive and negative mentions scores between -1 and 1."""
        graph = _graph("Eve")
        chat_log = [
            _entry("Alice", "Eve shows support and progress but faces risk and crisis"),
            _entry("Bob", "Eve may achieve success but also decline"),
        ]
        score_fn(graph, chat_log)
        sentiment = graph["nodes"][0]["sentiment"]
        assert -1.0 <= sentiment <= 1.0
        # Mixed mentions: should not be exactly +1 or -1
        assert sentiment != 1.0
        assert sentiment != -1.0


class TestAgentAsEntity:
    def test_agent_name_matches_entity(self, score_fn):
        """When agent_name matches an entity name, that entity gets scored."""
        graph = _graph("Alice")
        # Content does not mention "Alice" explicitly, but agent_name is "Alice"
        chat_log = [
            _entry("Alice", "This shows great support and positive progress"),
        ]
        score_fn(graph, chat_log)
        assert graph["nodes"][0]["sentiment"] > 0


class TestScoreClamped:
    def test_score_clamped_to_range(self, score_fn):
        """Sentiment score is always in [-1.0, 1.0] even with extreme inputs."""
        graph = _graph("Zara")
        # All positive words
        chat_log = [
            _entry("X", "Zara support approve praise welcome benefit success agree "
                   "positive progress growth improve achieve gain boost encourage"),
        ]
        score_fn(graph, chat_log)
        assert -1.0 <= graph["nodes"][0]["sentiment"] <= 1.0


class TestEmptyChatLog:
    def test_empty_chat_log_gives_zero(self, score_fn):
        """Empty chat_log results in 0.0 sentiment for all entities."""
        graph = _graph("Alice", "Bob")
        score_fn(graph, [])
        assert graph["nodes"][0]["sentiment"] == 0.0
        assert graph["nodes"][1]["sentiment"] == 0.0


class TestEmptyGraphNodes:
    def test_empty_nodes_no_crash(self, score_fn):
        """Calling with empty nodes list does not crash."""
        graph = {"nodes": [], "edges": []}
        chat_log = [_entry("Alice", "support and growth")]
        score_fn(graph, chat_log)  # should not raise
        assert graph["nodes"] == []


class TestGraphNodeSchemaHasSentiment:
    def test_graphnode_sentiment_defaults_to_zero(self):
        """GraphNode pydantic model has sentiment field defaulting to 0.0."""
        from saas.schemas.graph import GraphNode
        node = GraphNode(uuid="n1", name="Test")
        assert node.sentiment == 0.0

    def test_graphnode_accepts_sentiment_value(self):
        """GraphNode pydantic model accepts a custom sentiment value."""
        from saas.schemas.graph import GraphNode
        node = GraphNode(uuid="n1", name="Test", sentiment=-0.75)
        assert node.sentiment == -0.75
