"""Base protocol for simulation environments."""
from __future__ import annotations

from typing import Protocol

from simswarm.types import Action, ActionResult, Agent, Event, Observation, Tool


class Environment(Protocol):
    """Interface that all environments must implement."""
    name: str

    def get_observations(self, agent: Agent) -> Observation: ...
    def execute_action(self, agent: Agent, action: Action) -> ActionResult: ...
    def get_tools(self) -> list[Tool]: ...
    def publish_events(self) -> list[Event]: ...
    def tick(self) -> None: ...
