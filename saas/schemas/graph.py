"""Pydantic models for the knowledge graph visualization API."""
from __future__ import annotations

from pydantic import BaseModel


class GraphNode(BaseModel):
    uuid: str
    name: str
    labels: list[str] = []
    summary: str = ""
    connection_count: int = 0


class GraphEdge(BaseModel):
    uuid: str
    name: str
    fact: str = ""
    source_node_uuid: str
    target_node_uuid: str
    source_node_name: str = ""
    target_node_name: str = ""


class GraphMetadata(BaseModel):
    entity_types: list[str] = []
    total_nodes: int = 0
    total_edges: int = 0


class GraphResponse(BaseModel):
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    metadata: GraphMetadata = GraphMetadata()
