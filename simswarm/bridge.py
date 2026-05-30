"""Cross-environment event bridge.

Collects events from environments, formats digests for agents,
and injects scheduled events at the correct round.
"""
from __future__ import annotations

from simswarm.types import Agent, Event, ScheduledEvent


class Bridge:
    def __init__(self) -> None:
        self.pending_events: list[Event] = []

    def receive_events(self, events: list[Event]) -> None:
        self.pending_events.extend(events)

    def inject_scheduled(self, scheduled: list[ScheduledEvent], current_round: int) -> None:
        for se in scheduled:
            if se.round == current_round:
                self.pending_events.append(Event(
                    source="scheduled", type=se.type, data=se.data, round=current_round,
                ))

    def get_digest(self, agent: Agent) -> str:
        agent_envs = set(agent.environments)
        cross_events = [e for e in self.pending_events if e.source not in agent_envs]
        if not cross_events:
            return ""
        lines = []
        for event in cross_events:
            lines.append(_format_event(event))
        return "\n".join(lines)

    def clear(self) -> None:
        self.pending_events.clear()


def _format_event(event: Event) -> str:
    if event.type == "viral_post":
        return f"[Social] Trending: \"{event.data.get('text', '')[:80]}\" by {event.data.get('author', '?')}"
    if event.type == "price_move":
        q = event.data.get("question", "?")
        p = event.data.get("price_yes", 0)
        d = event.data.get("delta", 0)
        direction = "up" if d > 0 else "down"
        return f"[Market] {q} moved {direction} to {p:.0%}"
    if event.type == "policy_change":
        action = event.data.get("action", "unknown")
        return f"[Policy] {action}: {event.data}"
    return f"[{event.source}] {event.type}: {event.data}"
