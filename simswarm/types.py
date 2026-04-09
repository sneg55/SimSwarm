"""Core type definitions for the SimSwarm engine.

All types are plain dataclasses — no framework dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BeliefState:
    """Agent's evolving internal state."""
    positions: dict[str, float] = field(default_factory=dict)  # topic -> [-1.0, 1.0]
    confidence: dict[str, float] = field(default_factory=dict)  # topic -> [0.0, 1.0]
    trust: dict[str, float] = field(default_factory=dict)  # agent_id -> [0.0, 1.0]
    exposure_history: set[str] = field(default_factory=set)  # content hashes


@dataclass
class AgentActivityConfig:
    """Controls agent behavior intensity and bias."""
    activity_level: float = 0.5  # 0.0-1.0
    sentiment_bias: float = 0.0  # -1.0 to 1.0
    stance: str = "neutral"  # supportive, opposing, neutral, observer
    influence_weight: float = 1.0  # 0.5-3.0


@dataclass
class Agent:
    """A simulation participant."""
    id: str
    name: str
    persona: str
    environments: list[str]
    belief_state: BeliefState
    config: AgentActivityConfig
    memory: list[str] = field(default_factory=list)


@dataclass
class Action:
    """An action an agent wants to perform."""
    agent_id: str
    environment: str
    action_type: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionResult:
    """Result of executing an action in an environment."""
    success: bool
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class Observation:
    """What an agent sees from an environment."""
    environment: str
    content: str
    structured: dict[str, Any] = field(default_factory=dict)


@dataclass
class Event:
    """Cross-environment event published by an environment."""
    source: str  # environment name
    type: str
    data: dict[str, Any] = field(default_factory=dict)
    round: int = 0


@dataclass
class ScheduledEvent:
    """A policy shock or event injected at a specific round."""
    round: int
    type: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class EnvironmentConfig:
    """Configuration for instantiating an environment."""
    type: str  # "social", "market", "economic"
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class Entity:
    """An entity from the knowledge graph, passed as engine input."""
    id: str
    name: str
    type: str
    summary: str
    attributes: dict[str, Any] = field(default_factory=dict)
    relationships: list[dict[str, str]] = field(default_factory=list)


@dataclass
class SimulationConfig:
    """Full configuration for a simulation run."""
    seed_text: str
    goal: str
    entities: list[Entity]
    environments: list[EnvironmentConfig]
    rounds: int
    concurrency: int
    agent_configs: list[dict[str, Any]] | None = None
    variables: dict[str, Any] = field(default_factory=dict)
    scheduled_events: list[ScheduledEvent] = field(default_factory=list)
    enrichment: dict[str, Any] | None = None


@dataclass
class EngineConfig:
    """Engine-level settings (not simulation-specific)."""
    flush_interval: int = 10
    checkpoint_interval: int = 50
    max_memory_rounds: int = 20
    concurrency: int = 32
    context_budget: int = 16384  # max tokens per agent context


@dataclass
class RoundSnapshot:
    """Metrics captured at end of each round."""
    round: int
    agent_count: int
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class SimulationState:
    """Full mutable state of a running simulation."""
    round: int
    agents: dict[str, Agent]
    environments: dict[str, Any]
    events: list[Event]
    snapshots: list[RoundSnapshot]


@dataclass
class GraphSnapshot:
    """Entity graph data returned after simulation."""
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    metadata: dict[str, Any]


@dataclass
class ActionRecord:
    """A logged agent action for the chat log."""
    round_num: int
    agent_id: str
    agent_name: str
    action_type: str
    platform: str
    action_args: dict[str, Any]
    timestamp: str | None = None
    success: bool = True


@dataclass
class SimulationResult:
    """Complete output of a simulation run."""
    chat_log: list[ActionRecord]
    graph_data: GraphSnapshot
    trajectories: dict[str, Any]
    market_data: list[dict[str, Any]] | None = None
    raw_state: SimulationState | None = None


class Tool:
    """An action exposed by an environment as an LLM tool."""
    def __init__(self, name: str, description: str, parameters: dict[str, Any],
                 handler: Any = None):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.handler = handler

    def to_openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
