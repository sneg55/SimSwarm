"""Test the unified social environment: posts, replies, votes, feed ranking."""
from __future__ import annotations

from simswarm.environments.social import SocialEnvironment, SocialConfig
from simswarm.types import Action, Agent, AgentActivityConfig, BeliefState


def _make_agent(agent_id: str, name: str = "Test") -> Agent:
    return Agent(
        id=agent_id, name=name, persona="Test agent",
        environments=["social"], belief_state=BeliefState(),
        config=AgentActivityConfig(),
    )


class TestPostCreation:
    def test_create_post_returns_post_id(self):
        env = SocialEnvironment(SocialConfig())
        agent = _make_agent("a1", "Alice")
        action = Action(agent_id="a1", environment="social",
                        action_type="create_post", args={"text": "Hello world"})
        result = env.execute_action(agent, action)
        assert result.success
        assert "post_id" in result.data

    def test_post_appears_in_feed(self):
        env = SocialEnvironment(SocialConfig())
        alice = _make_agent("a1", "Alice")
        bob = _make_agent("a2", "Bob")
        env.execute_action(alice, Action(
            agent_id="a1", environment="social",
            action_type="create_post", args={"text": "Test post"},
        ))
        obs = env.get_observations(bob)
        assert "Test post" in obs.content


class TestReplies:
    def test_reply_creates_threaded_response(self):
        env = SocialEnvironment(SocialConfig(threading=True))
        alice = _make_agent("a1", "Alice")
        post_result = env.execute_action(alice, Action(
            agent_id="a1", environment="social",
            action_type="create_post", args={"text": "Original"},
        ))
        post_id = post_result.data["post_id"]
        reply_result = env.execute_action(alice, Action(
            agent_id="a1", environment="social",
            action_type="reply", args={"post_id": post_id, "text": "Reply"},
        ))
        assert reply_result.success

    def test_reply_fails_on_nonexistent_post(self):
        env = SocialEnvironment(SocialConfig())
        agent = _make_agent("a1")
        result = env.execute_action(agent, Action(
            agent_id="a1", environment="social",
            action_type="reply", args={"post_id": "fake", "text": "Reply"},
        ))
        assert not result.success


class TestVoting:
    def test_like_increases_post_score(self):
        env = SocialEnvironment(SocialConfig())
        alice = _make_agent("a1", "Alice")
        bob = _make_agent("a2", "Bob")
        post_result = env.execute_action(alice, Action(
            agent_id="a1", environment="social",
            action_type="create_post", args={"text": "Likeable"},
        ))
        post_id = post_result.data["post_id"]
        env.execute_action(bob, Action(
            agent_id="a2", environment="social",
            action_type="vote", args={"post_id": post_id, "value": 1},
        ))
        post = env.posts[post_id]
        assert post.likes == 1


class TestFeedRanking:
    def test_popular_posts_rank_higher(self):
        env = SocialEnvironment(SocialConfig())
        alice = _make_agent("a1", "Alice")
        agents = [_make_agent(f"v{i}") for i in range(5)]
        env.execute_action(alice, Action(
            agent_id="a1", environment="social",
            action_type="create_post", args={"text": "Unpopular"},
        ))
        post_b = env.execute_action(alice, Action(
            agent_id="a1", environment="social",
            action_type="create_post", args={"text": "Popular"},
        ))
        for v in agents:
            env.execute_action(v, Action(
                agent_id=v.id, environment="social",
                action_type="vote", args={"post_id": post_b.data["post_id"], "value": 1},
            ))
        env.tick()
        reader = _make_agent("reader")
        obs = env.get_observations(reader)
        pop_idx = obs.content.index("Popular")
        unpop_idx = obs.content.index("Unpopular")
        assert pop_idx < unpop_idx


class TestTools:
    def test_get_tools_returns_expected_actions(self):
        env = SocialEnvironment(SocialConfig())
        tools = env.get_tools()
        tool_names = {t.name for t in tools}
        assert "create_post" in tool_names
        assert "reply" in tool_names
        assert "vote" in tool_names
        assert "do_nothing" in tool_names


class TestEvents:
    def test_viral_post_publishes_event(self):
        env = SocialEnvironment(SocialConfig(viral_threshold=2))
        alice = _make_agent("a1", "Alice")
        voters = [_make_agent(f"v{i}") for i in range(3)]
        post = env.execute_action(alice, Action(
            agent_id="a1", environment="social",
            action_type="create_post", args={"text": "Going viral"},
        ))
        for v in voters:
            env.execute_action(v, Action(
                agent_id=v.id, environment="social",
                action_type="vote", args={"post_id": post.data["post_id"], "value": 1},
            ))
        env.tick()
        events = env.publish_events()
        viral_events = [e for e in events if e.type == "viral_post"]
        assert len(viral_events) >= 1
