"""Pydantic models defining the contract between SaaS and engine.

These schemas validate the shape of results returned by the worker API.
Both MiroShark and the new SimSwarm engine must produce output that passes
these validators.
"""
from __future__ import annotations

from pydantic import BaseModel


class ChatLogEntry(BaseModel):
    round_num: int
    agent_id: str
    agent_name: str
    action_type: str
    platform: str
    action_args: dict
    timestamp: str | None = None
    result: str | None = None
    success: bool | None = None


class GraphNode(BaseModel):
    uuid: str
    name: str
    labels: list[str]
    summary: str
    connection_count: int | None = None
    sentiment: float | None = None
    stance: str | None = None
    influence_weight: float | None = None


class GraphEdge(BaseModel):
    uuid: str
    source_node_uuid: str
    target_node_uuid: str
    name: str | None = None
    fact: str | None = None


class GraphMetadata(BaseModel):
    entity_types: list[str]
    total_nodes: int
    total_edges: int


class GraphData(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    metadata: GraphMetadata


class StakeholderPosition(BaseModel):
    name: str
    stance: str  # opposed | supports | neutral | split
    members: list[str]
    member_count: int
    rationale_keywords: list[str]


class NamedCoalition(BaseModel):
    name: str
    members: list[str]
    size: int
    stance: str


class PhaseBoundary(BaseModel):
    phase: str
    rounds: list[int]  # [start, end] inclusive
    week_range: str
    dominant_topic: str


class QuotablePost(BaseModel):
    agent_name: str
    agent_role: str
    phase: str
    text: str
    engagement: int


class SimScale(BaseModel):
    participants: int
    horizon_days: int
    bloc_count: int
    market_stress: str  # "present" | "none_observed"


class FindingSlot(BaseModel):
    slot: str  # "industry" | "regulator" | "intermediary" | "market" | "turning_point"
    title: str
    body: str
    citation: str
    accent_color: str


class StructuredResults(BaseModel):
    # LLM-authored
    brief: str
    verdict: str
    findings: list[FindingSlot]
    # Deterministic (Path 3)
    stakeholder_positions: list[StakeholderPosition]
    named_coalitions: list[NamedCoalition]
    phase_boundaries: list[PhaseBoundary]
    quotable_posts: list[QuotablePost]
    disagreement_axis: str
    sim_scale: SimScale


class WorkerStatusResponse(BaseModel):
    """Shape of GET /status when status is 'completed'."""
    status: str
    report: str
    chat_log: str  # JSON string — parse separately
    graph_data: str  # JSON string — parse separately
    structured: str  # JSON string — parse separately
    sim_data_uploaded: bool | None = None
    error: str | None = None
