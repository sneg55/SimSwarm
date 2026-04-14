"""Tests for extract_top_posts and extract_profiles.

These are the two rich-data extractors the native runner was missing after
the MiroShark cutover; without them the frontend Data tab renders "No posts
available" and "No profiles available" for every post-cutover job.
"""
from __future__ import annotations

from simswarm.extractor import extract_profiles, extract_top_posts
from simswarm.types import ActionRecord
from tests.engine.extractor_fixtures import SAMPLE_LOG


# ---------------------------------------------------------------------------
# extract_top_posts
# ---------------------------------------------------------------------------


class TestExtractTopPosts:
    def test_returns_list_of_dicts(self):
        result = extract_top_posts(SAMPLE_LOG)
        assert isinstance(result, list)
        assert all(isinstance(p, dict) for p in result)

    def test_includes_frontend_required_fields(self):
        """TopPostsFeed.vue reads: post_id, platform, agent_name, content,
        num_likes, num_shares, num_dislikes."""
        post = extract_top_posts(SAMPLE_LOG)[0]
        for field in (
            "post_id", "platform", "agent_name", "content",
            "num_likes", "num_shares", "num_dislikes",
        ):
            assert field in post, f"missing {field} in {post}"

    def test_ranked_descending_by_engagement(self):
        # A log where one post is explicitly liked by others.
        log = [
            ActionRecord(
                round_num=1, agent_id="a", agent_name="Alice",
                action_type="create_post", platform="twitter",
                action_args={"content": "hot take", "post_id": "p1"},
                timestamp="t", success=True,
            ),
            ActionRecord(
                round_num=1, agent_id="b", agent_name="Bob",
                action_type="create_post", platform="twitter",
                action_args={"content": "cold take", "post_id": "p2"},
                timestamp="t", success=True,
            ),
            ActionRecord(
                round_num=2, agent_id="b", agent_name="Bob",
                action_type="like_post", platform="twitter",
                action_args={"target_id": "p1"},
                timestamp="t", success=True,
            ),
            ActionRecord(
                round_num=2, agent_id="c", agent_name="Carol",
                action_type="like_post", platform="twitter",
                action_args={"post_id": "p1"},
                timestamp="t", success=True,
            ),
        ]
        result = extract_top_posts(log)
        assert result[0]["content"] == "hot take"
        assert result[0]["num_likes"] == 2
        assert result[1]["num_likes"] == 0

    def test_respects_limit(self):
        # Build a log with 30 posts
        log = [
            ActionRecord(
                round_num=1, agent_id=f"a{i}", agent_name=f"Agent{i}",
                action_type="create_post", platform="twitter",
                action_args={"content": f"post {i}", "post_id": f"p{i}"},
                timestamp="t", success=True,
            )
            for i in range(30)
        ]
        result = extract_top_posts(log, limit=5)
        assert len(result) == 5

    def test_empty_log(self):
        assert extract_top_posts([]) == []

    def test_synthetic_post_id_when_missing(self):
        """Frontend uses post_id as a Vue :key; we must always emit one."""
        log = [ActionRecord(
            round_num=1, agent_id="a", agent_name="Alice",
            action_type="create_post", platform="twitter",
            action_args={"content": "no id here"},
            timestamp="t", success=True,
        )]
        result = extract_top_posts(log)
        assert result[0]["post_id"]  # non-empty

    def test_top_posts_tallies_dislikes(self):
        """Vote actions with value=-1 increment num_dislikes on the target post."""
        post = ActionRecord(
            round_num=1, agent_id="alice", agent_name="Alice",
            action_type="create_post", platform="twitter",
            action_args={"post_id": "p1", "text": "claim"},
            timestamp="t", success=True,
        )
        dislike = ActionRecord(
            round_num=1, agent_id="bob", agent_name="Bob",
            action_type="vote", platform="twitter",
            action_args={"post_id": "p1", "value": -1},
            timestamp="t", success=True,
        )
        like = ActionRecord(
            round_num=1, agent_id="carol", agent_name="Carol",
            action_type="vote", platform="twitter",
            action_args={"post_id": "p1", "value": 1},
            timestamp="t", success=True,
        )
        top = extract_top_posts([post, dislike, like])
        assert len(top) == 1
        assert top[0]["num_dislikes"] == 1
        assert top[0]["num_likes"] == 1


# ---------------------------------------------------------------------------
# extract_profiles
# ---------------------------------------------------------------------------


class TestExtractProfiles:
    def test_returns_one_profile_per_unique_agent(self):
        # SAMPLE_LOG mentions Alice, Bob, Carol, Dave = 4 agents
        result = extract_profiles(SAMPLE_LOG)
        names = {p["name"] for p in result}
        assert names == {"Alice", "Bob", "Carol", "Dave"}

    def test_includes_frontend_required_fields(self):
        """AgentProfileCards.vue reads: name, persona OR bio."""
        result = extract_profiles(SAMPLE_LOG)
        for p in result:
            assert "name" in p
            assert "persona" in p or "bio" in p

    def test_activity_counts_populated(self):
        by_name = {p["name"]: p for p in extract_profiles(SAMPLE_LOG)}
        # Alice: r1 create_post, r1 like_post, r1 follow, r2 create_comment,
        # r3 sell_shares = 5 actions, 1 post, active in r1/r2/r3 (3 rounds)
        alice = by_name["Alice"]
        assert alice["total_posts"] == 1
        assert alice["total_actions"] == 5
        assert alice["rounds_active"] == 3

    def test_empty_log(self):
        assert extract_profiles([]) == []
