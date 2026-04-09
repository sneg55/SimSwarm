"""Tests for extract_engagement_summary and extract_agent_trajectories."""
from __future__ import annotations

from simswarm.extractor import extract_agent_trajectories, extract_engagement_summary
from tests.engine.extractor_fixtures import SAMPLE_LOG


class TestExtractEngagementSummary:
    def test_returns_list_of_dicts(self):
        result = extract_engagement_summary(SAMPLE_LOG)
        assert isinstance(result, list)
        assert all(isinstance(r, dict) for r in result)

    def test_one_entry_per_round(self):
        result = extract_engagement_summary(SAMPLE_LOG)
        rounds = [r["round"] for r in result]
        assert sorted(rounds) == [1, 2, 3]

    def test_required_fields_present(self):
        for entry in extract_engagement_summary(SAMPLE_LOG):
            for field in ("round", "total_posts", "total_likes", "total_comments", "active_agents"):
                assert field in entry

    def test_post_counts_correct(self):
        by_round = {r["round"]: r for r in extract_engagement_summary(SAMPLE_LOG)}
        assert by_round[1]["total_posts"] == 2   # Alice + Bob
        assert by_round[2]["total_posts"] == 1   # Bob only
        assert by_round[3]["total_posts"] == 1   # Dave (failed still counts)

    def test_like_counts_correct(self):
        by_round = {r["round"]: r for r in extract_engagement_summary(SAMPLE_LOG)}
        assert by_round[1]["total_likes"] == 1
        assert by_round[2]["total_likes"] == 0
        assert by_round[3]["total_likes"] == 0

    def test_comment_counts_correct(self):
        by_round = {r["round"]: r for r in extract_engagement_summary(SAMPLE_LOG)}
        assert by_round[2]["total_comments"] == 1

    def test_active_agents_round_1(self):
        by_round = {r["round"]: r for r in extract_engagement_summary(SAMPLE_LOG)}
        # Alice (post + like + follow), Bob (post), Carol (follow) = 3 unique agents
        assert by_round[1]["active_agents"] == 3

    def test_active_agents_round_2(self):
        by_round = {r["round"]: r for r in extract_engagement_summary(SAMPLE_LOG)}
        # Bob (post + buy), Alice (comment), Dave (nothing) = 3 unique agents
        assert by_round[2]["active_agents"] == 3

    def test_empty_log_returns_empty_list(self):
        assert extract_engagement_summary([]) == []


class TestExtractAgentTrajectories:
    def test_returns_list_of_dicts(self):
        result = extract_agent_trajectories(SAMPLE_LOG)
        assert isinstance(result, list)
        assert all(isinstance(t, dict) for t in result)

    def test_one_entry_per_agent(self):
        result = extract_agent_trajectories(SAMPLE_LOG)
        agent_ids = [t["agent_id"] for t in result]
        assert len(agent_ids) == len(set(agent_ids))
        assert set(agent_ids) == {"agent-alpha", "agent-beta", "agent-gamma", "agent-delta"}

    def test_required_top_level_fields(self):
        for traj in extract_agent_trajectories(SAMPLE_LOG):
            assert "agent_id" in traj
            assert "name" in traj
            assert "rounds" in traj
            assert isinstance(traj["rounds"], list)

    def test_round_entries_have_required_fields(self):
        for traj in extract_agent_trajectories(SAMPLE_LOG):
            for r in traj["rounds"]:
                for field in ("round", "posts", "actions", "sentiment"):
                    assert field in r

    def test_post_count_per_agent_round(self):
        trajs = {t["agent_id"]: t for t in extract_agent_trajectories(SAMPLE_LOG)}
        alice_rounds = {r["round"]: r for r in trajs["agent-alpha"]["rounds"]}
        assert alice_rounds[1]["posts"] == 1
        assert alice_rounds.get(2, {}).get("posts", 0) == 0

    def test_action_count_per_round(self):
        trajs = {t["agent_id"]: t for t in extract_agent_trajectories(SAMPLE_LOG)}
        alice_rounds = {r["round"]: r for r in trajs["agent-alpha"]["rounds"]}
        # Alice round 1: create_post + like_post + follow = 3 actions
        assert alice_rounds[1]["actions"] == 3

    def test_sentiment_is_float(self):
        for traj in extract_agent_trajectories(SAMPLE_LOG):
            for r in traj["rounds"]:
                assert isinstance(r["sentiment"], float)

    def test_sentiment_in_valid_range(self):
        for traj in extract_agent_trajectories(SAMPLE_LOG):
            for r in traj["rounds"]:
                assert -1.0 <= r["sentiment"] <= 1.0

    def test_empty_log_returns_empty_list(self):
        assert extract_agent_trajectories([]) == []
