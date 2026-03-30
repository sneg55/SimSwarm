"""Shadow ZepToolsService backed by Graphiti + Kuzu.

Replaces app.services.zep_tools.ZepToolsService.
"""
from __future__ import annotations

import copy
import logging
from typing import Any, Dict, List, Optional

from graphiti.types import (
    NodeInfo, EdgeInfo, SearchResult, InsightForgeResult, PanoramaResult,
)

logger = logging.getLogger(__name__)


class ZepToolsService:
    """Shadow replacement for MiroFish's ZepToolsService."""

    def __init__(self, api_key: Optional[str] = None, llm_client=None):
        # api_key ignored
        self._llm_client = llm_client
        logger.info("ZepToolsService initialized (Graphiti shadow)")

    def _get_llm_client(self):
        if self._llm_client is None:
            try:
                from app.utils.llm_client import LLMClient  # noqa: PLC0415
                self._llm_client = LLMClient()
            except Exception:
                pass
        return self._llm_client

    # NOTE: search_graph / quick_search return SearchResult with dicts for edges/nodes,
    # while panorama_search returns PanoramaResult with NodeInfo/EdgeInfo objects.
    # This intentionally matches the original Zep interface contract that MiroFish expects.
    def search_graph(
        self,
        graph_id: str,
        query: str,
        limit: int = 10,
        scope: str = "edges",
    ) -> SearchResult:
        """Hybrid search on the graph. Falls back to local keyword search on failure."""
        from graphiti import get_graphiti_instance, _run  # noqa: PLC0415

        graphiti = _run(get_graphiti_instance())

        try:
            from graphiti_core.search.search_config_recipes import (  # noqa: PLC0415
                COMBINED_HYBRID_SEARCH_CROSS_ENCODER,
                EDGE_HYBRID_SEARCH_RRF,
                NODE_HYBRID_SEARCH_RRF,
            )

            # Copy the module-level singleton configs before mutating to avoid
            # corrupting shared state across concurrent calls.
            if scope == "nodes":
                config = copy.copy(NODE_HYBRID_SEARCH_RRF)
            elif scope == "both":
                config = copy.copy(COMBINED_HYBRID_SEARCH_CROSS_ENCODER)
            else:
                config = copy.copy(EDGE_HYBRID_SEARCH_RRF)

            config.limit = limit
            results = _run(graphiti.search_(
                query=query,
                config=config,
                group_ids=[graph_id],
            ))

            facts = [e.fact for e in results.edges if e.fact]
            edges = [
                {
                    "uuid": e.uuid,
                    "name": e.name or "",
                    "fact": e.fact or "",
                    "source_node_uuid": e.source_node_uuid or "",
                    "target_node_uuid": e.target_node_uuid or "",
                }
                for e in results.edges
            ]
            nodes = [
                {
                    "uuid": n.uuid,
                    "name": n.name or "",
                    "labels": n.labels or [],
                    "summary": n.summary or "",
                }
                for n in results.nodes
            ]

            return SearchResult(
                facts=facts,
                edges=edges,
                nodes=nodes,
                query=query,
                total_count=len(facts),
            )
        except Exception as exc:
            logger.warning("search_graph failed, falling back to local search: %s", exc)
            return self._local_search(graph_id, query, limit)

    def _local_search(self, graph_id: str, query: str, limit: int) -> SearchResult:
        """Keyword-based fallback search over all edges."""
        all_edges = self.get_all_edges(graph_id)
        query_lower = query.lower()
        matching_facts: List[str] = []
        matching_edges: List[Dict[str, Any]] = []

        for e in all_edges:
            fact = e.fact or e.name or ""
            if query_lower in fact.lower():
                matching_facts.append(fact)
                matching_edges.append({
                    "uuid": e.uuid,
                    "name": e.name,
                    "fact": e.fact,
                    "source_node_uuid": e.source_node_uuid,
                    "target_node_uuid": e.target_node_uuid,
                })

        return SearchResult(
            facts=matching_facts[:limit],
            edges=matching_edges[:limit],
            nodes=[],
            query=query,
            total_count=len(matching_facts),
        )

    def get_all_nodes(self, graph_id: str) -> List[NodeInfo]:
        """Get all entity nodes in the graph."""
        from graphiti import get_graphiti_instance, _run  # noqa: PLC0415
        from graphiti_core.nodes import EntityNode as GEntityNode  # noqa: PLC0415

        graphiti = _run(get_graphiti_instance())
        raw_nodes = _run(GEntityNode.get_by_group_ids(graphiti.driver, [graph_id]))

        return [
            NodeInfo(
                uuid=n.uuid,
                name=n.name or "",
                labels=n.labels or [],
                summary=n.summary or "",
                attributes=n.attributes or {},
            )
            for n in raw_nodes
        ]

    def get_all_edges(self, graph_id: str, include_temporal: bool = True) -> List[EdgeInfo]:
        """Get all entity edges in the graph."""
        from graphiti import get_graphiti_instance, _run  # noqa: PLC0415
        from graphiti_core.edges import EntityEdge as GEntityEdge  # noqa: PLC0415

        graphiti = _run(get_graphiti_instance())
        raw_edges = _run(GEntityEdge.get_by_group_ids(graphiti.driver, [graph_id]))

        result = []
        for e in raw_edges:
            ei = EdgeInfo(
                uuid=e.uuid,
                name=e.name or "",
                fact=e.fact or "",
                source_node_uuid=e.source_node_uuid or "",
                target_node_uuid=e.target_node_uuid or "",
            )
            if include_temporal:
                ei.created_at = str(e.created_at) if e.created_at else None
                ei.valid_at = str(e.valid_at) if e.valid_at else None
                ei.invalid_at = str(e.invalid_at) if e.invalid_at else None
                ei.expired_at = str(e.expired_at) if e.expired_at else None
            result.append(ei)
        return result

    def insight_forge(
        self,
        graph_id: str,
        query: str,
        simulation_requirement: str,
        report_context: str = "",
        max_sub_queries: int = 5,
    ) -> InsightForgeResult:
        """Deep search: generate sub-queries via LLM, search each, aggregate results."""
        llm = self._get_llm_client()
        sub_queries = [query]

        # Generate sub-queries via LLM if available
        if llm:
            try:
                prompt = (
                    f"Given the research question: \"{query}\"\n"
                    f"And the simulation requirement: \"{simulation_requirement}\"\n"
                    f"Generate {max_sub_queries} specific sub-questions to research. "
                    f"Return only the questions, one per line."
                )
                response = llm.chat(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                )
                lines = [
                    ln.strip() for ln in response.split("\n")
                    if ln.strip() and len(ln.strip()) > 10
                ]
                if lines:
                    sub_queries = lines[:max_sub_queries]
            except Exception as exc:
                logger.warning("Failed to generate sub-queries: %s", exc)

        # Search for each sub-query and aggregate
        all_facts: List[str] = []
        all_entities: List[Dict[str, Any]] = []
        all_edges: List[Dict[str, Any]] = []

        for sq in sub_queries:
            result = self.search_graph(graph_id, sq, limit=10, scope="both")
            all_facts.extend(result.facts)
            all_edges.extend(result.edges)
            for node in result.nodes:
                all_entities.append(node)

        # Deduplicate facts
        seen_facts: set[str] = set()
        unique_facts: List[str] = []
        for f in all_facts:
            if f not in seen_facts:
                seen_facts.add(f)
                unique_facts.append(f)

        # Build relationship chains: "SourceName --[RELATION]--> TargetName"
        # Build node name lookup from search result nodes
        node_names: Dict[str, str] = {}
        for n in all_entities:
            uid = n.get("uuid", "")
            name = n.get("name", "")
            if uid and name:
                node_names[uid] = name

        relationship_chains: List[str] = []
        seen_chains: set[str] = set()
        for edge in all_edges:
            src_uuid = edge.get("source_node_uuid", "")
            tgt_uuid = edge.get("target_node_uuid", "")
            rel_name = edge.get("name", "")
            src_name = node_names.get(src_uuid, src_uuid[:8])
            tgt_name = node_names.get(tgt_uuid, tgt_uuid[:8])
            chain = f"{src_name} --[{rel_name}]--> {tgt_name}"
            if chain not in seen_chains:
                seen_chains.add(chain)
                relationship_chains.append(chain)

        return InsightForgeResult(
            query=query,
            simulation_requirement=simulation_requirement,
            sub_queries=sub_queries,
            semantic_facts=unique_facts,
            entity_insights=all_entities,
            relationship_chains=relationship_chains,
            total_facts=len(unique_facts),
            total_entities=len(all_entities),
            total_relationships=len(relationship_chains),
        )

    def panorama_search(
        self,
        graph_id: str,
        query: str,
        include_expired: bool = True,
        limit: int = 50,
    ) -> PanoramaResult:
        """Broad search returning all nodes and edges, split by active/historical."""
        all_nodes = self.get_all_nodes(graph_id)
        all_edges = self.get_all_edges(graph_id, include_temporal=True)

        active_facts = [e.fact for e in all_edges if e.fact and not e.expired_at]
        historical_facts = [e.fact for e in all_edges if e.fact and e.expired_at]

        return PanoramaResult(
            query=query,
            all_nodes=all_nodes[:limit],
            all_edges=all_edges[:limit],
            active_facts=active_facts,
            historical_facts=historical_facts if include_expired else [],
            total_nodes=len(all_nodes),
            total_edges=len(all_edges),
            active_count=len(active_facts),
            historical_count=len(historical_facts),
        )

    def quick_search(
        self,
        graph_id: str,
        query: str,
        limit: int = 10,
    ) -> SearchResult:
        """Simple search — delegates to search_graph with edge scope."""
        return self.search_graph(graph_id, query, limit=limit, scope="edges")
