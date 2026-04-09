"""Test cross-environment bridge: event collection and digest formatting."""
from __future__ import annotations

from simswarm.bridge import Bridge
from simswarm.types import Agent, AgentActivityConfig, BeliefState, Event


def _make_agent(agent_id: str, envs: list[str]) -> Agent:
    return Agent(
        id=agent_id, name=agent_id, persona="test",
        environments=envs, belief_state=BeliefState(),
        config=AgentActivityConfig(),
    )


class TestEventCollection:
    def test_collects_events_from_multiple_sources(self):
        bridge = Bridge()
        bridge.receive_events([
            Event(source="social", type="viral_post", data={"text": "Big news"}),
            Event(source="market", type="price_move", data={"delta": 0.15}),
        ])
        assert len(bridge.pending_events) == 2

    def test_clear_flushes_events(self):
        bridge = Bridge()
        bridge.receive_events([Event(source="social", type="test", data={})])
        bridge.clear()
        assert len(bridge.pending_events) == 0


class TestDigestFormatting:
    def test_agent_sees_only_cross_environment_events(self):
        bridge = Bridge()
        bridge.receive_events([
            Event(source="social", type="viral_post", data={"text": "Trending"}),
            Event(source="market", type="price_move", data={"question": "Will X?", "price_yes": 0.7}),
        ])
        social_agent = _make_agent("a1", ["social"])
        digest = bridge.get_digest(social_agent)
        assert "price" in digest.lower() or "market" in digest.lower()
        assert "viral" not in digest.lower()

    def test_multi_env_agent_sees_events_from_other_envs(self):
        bridge = Bridge()
        bridge.receive_events([
            Event(source="social", type="viral_post", data={"text": "News"}),
            Event(source="market", type="price_move", data={"question": "Q?", "price_yes": 0.6}),
            Event(source="economic", type="policy_change", data={"action": "stimulus"}),
        ])
        agent = _make_agent("a1", ["social", "market"])
        digest = bridge.get_digest(agent)
        assert "policy" in digest.lower() or "economic" in digest.lower()

    def test_empty_events_returns_empty_digest(self):
        bridge = Bridge()
        agent = _make_agent("a1", ["social"])
        digest = bridge.get_digest(agent)
        assert digest == ""


class TestScheduledEvents:
    def test_injects_scheduled_event_at_correct_round(self):
        bridge = Bridge()
        from simswarm.types import ScheduledEvent
        scheduled = [ScheduledEvent(round=5, type="policy_change", data={"action": "distribute"})]
        bridge.inject_scheduled(scheduled, current_round=5)
        assert len(bridge.pending_events) == 1
        assert bridge.pending_events[0].type == "policy_change"

    def test_skips_scheduled_event_at_wrong_round(self):
        bridge = Bridge()
        from simswarm.types import ScheduledEvent
        scheduled = [ScheduledEvent(round=5, type="policy_change", data={"action": "distribute"})]
        bridge.inject_scheduled(scheduled, current_round=3)
        assert len(bridge.pending_events) == 0
