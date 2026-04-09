"""Pydantic models defining the contract between SaaS and engine.

These schemas validate the shape of results returned by the worker API.
Both MiroShark and the new SimSwarm engine must produce output that passes
these validators.
"""
from __future__ import annotations

from pydantic import BaseModel, field_validator


class ChatLogEntry(BaseModel):
    round_num: int
    agent_id: int
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


class Finding(BaseModel):
    label: str
    title: str
    description: str
    metric: str
    accentColor: str

    @field_validator("accentColor")
    @classmethod
    def valid_hex(cls, v: str) -> str:
        if not v.startswith("#") or len(v) not in (4, 7):
            raise ValueError(f"Invalid hex color: {v}")
        return v


class SentimentEntry(BaseModel):
    label: str
    value: int
    direction: str

    @field_validator("direction")
    @classmethod
    def valid_direction(cls, v: str) -> str:
        if v not in ("positive", "negative"):
            raise ValueError(f"direction must be positive or negative, got {v}")
        return v


class Coalition(BaseModel):
    name: str
    description: str
    agents: int
    strength: int
    color: str


class ConfidenceEntry(BaseModel):
    label: str
    value: str
    color: str


class StructuredResults(BaseModel):
    brief: str
    findings: list[Finding]
    sentiment: list[SentimentEntry]
    coalitions: list[Coalition]
    confidence: list[ConfidenceEntry]


class WorkerStatusResponse(BaseModel):
    """Shape of GET /status when status is 'completed'."""
    status: str
    report: str
    chat_log: str  # JSON string — parse separately
    graph_data: str  # JSON string — parse separately
    structured: str  # JSON string — parse separately
    sim_data_uploaded: bool | None = None
    error: str | None = None
