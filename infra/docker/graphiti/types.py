"""Return types matching MiroFish's Zep service interfaces."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class NodeInfo:
    uuid: str
    name: str
    labels: list[str]
    summary: str
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class EdgeInfo:
    uuid: str
    name: str
    fact: str
    source_node_uuid: str
    target_node_uuid: str
    source_node_name: str | None = None
    target_node_name: str | None = None
    created_at: str | None = None
    valid_at: str | None = None
    invalid_at: str | None = None
    expired_at: str | None = None


@dataclass
class SearchResult:
    facts: list[str]
    edges: list[dict[str, Any]]
    nodes: list[dict[str, Any]]
    query: str
    total_count: int


@dataclass
class InsightForgeResult:
    query: str
    simulation_requirement: str
    sub_queries: list[str]
    semantic_facts: list[str] = field(default_factory=list)
    entity_insights: list[dict[str, Any]] = field(default_factory=list)
    relationship_chains: list[str] = field(default_factory=list)
    total_facts: int = 0
    total_entities: int = 0
    total_relationships: int = 0


@dataclass
class PanoramaResult:
    query: str
    all_nodes: list[NodeInfo] = field(default_factory=list)
    all_edges: list[EdgeInfo] = field(default_factory=list)
    active_facts: list[str] = field(default_factory=list)
    historical_facts: list[str] = field(default_factory=list)
    total_nodes: int = 0
    total_edges: int = 0
    active_count: int = 0
    historical_count: int = 0


@dataclass
class EntityNode:
    uuid: str
    name: str
    labels: list[str]
    summary: str
    attributes: dict[str, Any] = field(default_factory=dict)
    related_edges: list[dict[str, Any]] = field(default_factory=list)
    related_nodes: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class FilteredEntities:
    entities: list[EntityNode]
    entity_types: set[str]
    total_count: int
    filtered_count: int
