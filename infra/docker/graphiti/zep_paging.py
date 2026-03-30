"""Shadow zep_paging backed by Graphiti + Kuzu.

Replaces app.utils.zep_paging. No pagination needed — all data is local.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def fetch_all_nodes(client: Any, graph_id: str, **kwargs) -> list[Any]:
    """Fetch all nodes from the Kuzu graph. Client param ignored."""
    from graphiti import get_graphiti_instance, _run
    from graphiti_core.nodes import EntityNode as GraphitiEntityNode

    graphiti = _run(get_graphiti_instance())
    nodes = _run(GraphitiEntityNode.get_by_group_ids(graphiti.driver, [graph_id]))
    return nodes


def fetch_all_edges(client: Any, graph_id: str, **kwargs) -> list[Any]:
    """Fetch all edges from the Kuzu graph. Client param ignored."""
    from graphiti import get_graphiti_instance, _run
    from graphiti_core.edges import EntityEdge as GraphitiEntityEdge

    graphiti = _run(get_graphiti_instance())
    edges = _run(GraphitiEntityEdge.get_by_group_ids(graphiti.driver, [graph_id]))
    return edges
