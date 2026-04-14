"""Tests for agent_sentiment_from_trajectories — average sentiment per agent."""
from __future__ import annotations

from simswarm.extractor_activity import agent_sentiment_from_trajectories


def test_returns_mean_sentiment_per_agent():
    trajectories = [
        {
            "agent_id": "alice",
            "name": "Alice",
            "rounds": [
                {"round": 1, "posts": 1, "actions": 2, "sentiment": 0.4},
                {"round": 2, "posts": 1, "actions": 3, "sentiment": 0.8},
            ],
        },
        {
            "agent_id": "bob",
            "name": "Bob",
            "rounds": [
                {"round": 1, "posts": 1, "actions": 1, "sentiment": -0.2},
            ],
        },
    ]
    result = agent_sentiment_from_trajectories(trajectories)
    assert result == {"alice": 0.6, "bob": -0.2}


def test_empty_trajectories_returns_empty_dict():
    assert agent_sentiment_from_trajectories([]) == {}


def test_agent_with_no_rounds_is_skipped():
    trajectories = [{"agent_id": "alice", "name": "Alice", "rounds": []}]
    assert agent_sentiment_from_trajectories(trajectories) == {}


def test_missing_sentiment_key_treated_as_zero():
    trajectories = [
        {
            "agent_id": "alice",
            "name": "Alice",
            "rounds": [
                {"round": 1, "posts": 1, "actions": 1},  # no sentiment key
                {"round": 2, "posts": 1, "actions": 1, "sentiment": 0.6},
            ],
        },
    ]
    result = agent_sentiment_from_trajectories(trajectories)
    assert result == {"alice": 0.3}
