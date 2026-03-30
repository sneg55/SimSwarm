"""Shadow ZepEntityReader backed by Graphiti + Kuzu.

Replaces app.services.zep_entity_reader.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from graphiti.types import EntityNode, FilteredEntities

logger = logging.getLogger(__name__)


class ZepEntityReader:
    """Shadow replacement for MiroFish's ZepEntityReader."""

    def __init__(self, api_key: Optional[str] = None):
        # api_key ignored
        logger.info("ZepEntityReader initialized (Graphiti shadow)")

    def filter_defined_entities(
        self,
        graph_id: str,
        defined_entity_types: Optional[List[str]] = None,
        enrich_with_edges: bool = True,
    ) -> FilteredEntities:
        """Filter graph nodes to those with specific entity type labels."""
        from graphiti import get_graphiti_instance, _run
        from graphiti_core.nodes import EntityNode as GEntityNode
        from graphiti_core.edges import EntityEdge as GEntityEdge

        graphiti = _run(get_graphiti_instance())
        raw_nodes = _run(GEntityNode.get_by_group_ids(graphiti.driver, [graph_id]))

        all_edges_data: List[Dict[str, Any]] = []
        if enrich_with_edges:
            raw_edges = _run(GEntityEdge.get_by_group_ids(graphiti.driver, [graph_id]))
            all_edges_data = [
                {
                    "uuid": e.uuid,
                    "name": e.name or "",
                    "fact": e.fact or "",
                    "source_node_uuid": e.source_node_uuid or "",
                    "target_node_uuid": e.target_node_uuid or "",
                    "attributes": e.attributes or {},
                }
                for e in raw_edges
            ]

        # Build edge lookup per node UUID
        node_edges: Dict[str, List[Dict[str, Any]]] = {}
        for edge in all_edges_data:
            for uid in (edge["source_node_uuid"], edge["target_node_uuid"]):
                node_edges.setdefault(uid, []).append(edge)

        entities: List[EntityNode] = []
        entity_types: set[str] = set()
        total_count = len(raw_nodes)

        for n in raw_nodes:
            labels = n.labels or []
            # Skip nodes with only generic labels
            specific_labels = [lbl for lbl in labels if lbl not in ("Entity", "Node")]
            if defined_entity_types:
                if not any(lbl in defined_entity_types for lbl in specific_labels):
                    continue
            elif not specific_labels:
                continue

            for lbl in specific_labels:
                entity_types.add(lbl)

            related = node_edges.get(n.uuid, [])
            entities.append(EntityNode(
                uuid=n.uuid,
                name=n.name or "",
                labels=labels,
                summary=n.summary or "",
                attributes=n.attributes or {},
                related_edges=related,
                related_nodes=[],
            ))

        logger.info(
            "Filtered entities: %d/%d (types: %s)",
            len(entities), total_count, entity_types,
        )
        return FilteredEntities(
            entities=entities,
            entity_types=entity_types,
            total_count=total_count,
            filtered_count=len(entities),
        )

    def get_entity_with_context(
        self,
        graph_id: str,
        entity_uuid: str,
    ) -> Optional[EntityNode]:
        """Get a single entity by UUID."""
        from graphiti import get_graphiti_instance, _run
        from graphiti_core.nodes import EntityNode as GEntityNode

        graphiti = _run(get_graphiti_instance())
        try:
            node = _run(GEntityNode.get_by_uuid(graphiti.driver, entity_uuid))
        except Exception:
            return None

        if node is None:
            return None

        return EntityNode(
            uuid=node.uuid,
            name=node.name or "",
            labels=node.labels or [],
            summary=node.summary or "",
            attributes=node.attributes or {},
        )

    def get_all_edges(self, graph_id: str) -> List[Dict[str, Any]]:
        """Get all edges in the graph as dicts."""
        from graphiti import get_graphiti_instance, _run
        from graphiti_core.edges import EntityEdge as GEntityEdge

        graphiti = _run(get_graphiti_instance())
        raw_edges = _run(GEntityEdge.get_by_group_ids(graphiti.driver, [graph_id]))

        return [
            {
                "uuid": e.uuid,
                "name": e.name or "",
                "fact": e.fact or "",
                "source_node_uuid": e.source_node_uuid or "",
                "target_node_uuid": e.target_node_uuid or "",
                "attributes": e.attributes or {},
            }
            for e in raw_edges
        ]
