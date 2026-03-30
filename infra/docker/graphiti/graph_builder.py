"""Shadow GraphBuilderService backed by Graphiti + Kuzu.

Replaces app.services.graph_builder.GraphBuilderService.
MiroFish imports this via sys.path ordering.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, create_model

logger = logging.getLogger(__name__)

# Re-export TaskManager from the real MiroFish module (not Zep-dependent)
try:
    import sys
    import importlib
    # The real task_manager doesn't depend on Zep
    _mirofish_backend = next((p for p in sys.path if "mirofish/backend" in p), None)
    if _mirofish_backend:
        spec = importlib.util.spec_from_file_location(
            "app.services.task_manager",
            f"{_mirofish_backend}/app/services/task_manager.py"
        )
        if spec and spec.loader:
            _tm_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(_tm_mod)
            TaskManager = _tm_mod.TaskManager
        else:
            TaskManager = None
    else:
        TaskManager = None
except Exception:
    TaskManager = None


def _ontology_to_pydantic(ontology: Dict[str, Any]) -> tuple[dict, dict, dict]:
    """Convert MiroFish ontology dict to Graphiti's Pydantic entity/edge type dicts."""
    entity_types = {}
    for et in ontology.get("entity_types", []):
        name = et["name"]
        fields = {}
        for attr in et.get("attributes", []):
            attr_name = attr["name"]
            # Skip reserved field names
            if attr_name in ("name", "uuid", "group_id", "created_at", "summary",
                             "name_embedding", "labels", "attributes"):
                continue
            fields[attr_name] = (Optional[str], None)
        if fields:
            entity_types[name] = create_model(name, **fields)
        else:
            entity_types[name] = create_model(name, description=(Optional[str], None))

    edge_types = {}
    edge_type_map = {}
    for et in ontology.get("edge_types", []):
        name = et["name"]
        fields = {}
        for attr in et.get("attributes", []):
            attr_name = attr["name"]
            if attr_name in ("uuid", "group_id", "created_at", "name", "fact",
                             "fact_embedding", "episodes", "expired_at",
                             "valid_at", "invalid_at", "attributes"):
                continue
            fields[attr_name] = (Optional[str], None)
        if fields:
            edge_types[name] = create_model(name, **fields)
        else:
            edge_types[name] = create_model(name, detail=(Optional[str], None))

        for st in et.get("source_targets", []):
            key = (st["source"], st["target"])
            edge_type_map.setdefault(key, []).append(name)

    return entity_types, edge_types, edge_type_map


class GraphBuilderService:
    """Shadow replacement for MiroFish's GraphBuilderService.

    Uses Graphiti + Kuzu instead of Zep Cloud.
    """

    def __init__(self, api_key: Optional[str] = None):
        # api_key ignored — we use Graphiti, not Zep
        self.task_manager = TaskManager() if TaskManager else None
        self._group_id = None
        logger.info("GraphBuilderService initialized (Graphiti shadow)")

    def create_graph(self, name: str) -> str:
        """Create a new graph. Returns graph_id."""
        from graphiti import get_graphiti_instance, _run
        _run(get_graphiti_instance())  # ensure singleton is initialized
        self._group_id = f"fishcloud_{uuid.uuid4().hex[:16]}"
        logger.info("Graph created: group_id=%s name=%s", self._group_id, name)
        return self._group_id

    def set_ontology(self, graph_id: str, ontology: Dict[str, Any]) -> None:
        """Store ontology for use in subsequent add_episode calls."""
        from graphiti import store_ontology
        entity_types, edge_types, edge_type_map = _ontology_to_pydantic(ontology)
        store_ontology(entity_types, edge_types, edge_type_map)
        logger.info(
            "Ontology set: %d entity types, %d edge types",
            len(entity_types), len(edge_types),
        )

    def add_text_batches(
        self,
        graph_id: str,
        chunks: List[str],
        batch_size: int = 3,
        progress_callback: Optional[Callable] = None,
    ) -> List[str]:
        """Ingest text chunks into the graph. Returns list of episode UUIDs."""
        from graphiti import (  # noqa: PLC0415
            get_graphiti_instance, get_stored_entity_types,
            get_stored_edge_types, get_stored_edge_type_map, _run,
        )

        graphiti = _run(get_graphiti_instance())
        entity_types = get_stored_entity_types()
        edge_types = get_stored_edge_types()
        edge_type_map = get_stored_edge_type_map()

        episode_uuids = []
        total = len(chunks)

        for i, chunk in enumerate(chunks):
            if not chunk.strip():
                continue
            try:
                ep_uuid = uuid.uuid4().hex
                from graphiti_core.nodes import EpisodeType  # noqa: PLC0415
                result = _run(graphiti.add_episode(
                    name=f"chunk_{i}",
                    episode_body=chunk,
                    source_description="seed_text",
                    reference_time=datetime.now(timezone.utc),
                    source=EpisodeType.text,
                    group_id=graph_id,
                    uuid=ep_uuid,
                    entity_types=entity_types,
                    edge_types=edge_types,
                    edge_type_map=edge_type_map,
                ))
                episode_uuids.append(ep_uuid)
            except Exception as exc:
                logger.warning("Failed to add chunk %d/%d: %s", i + 1, total, exc)
                # Skip failed chunks — one missing chunk is acceptable

            if progress_callback:
                progress = (i + 1) / total
                progress_callback(f"Ingested chunk {i + 1}/{total}", progress)

        logger.info("Ingested %d/%d chunks into graph %s", len(episode_uuids), total, graph_id)
        return episode_uuids

    def _wait_for_episodes(
        self,
        episode_uuids: List[str],
        progress_callback: Optional[Callable] = None,
        timeout: int = 600,
    ) -> None:
        """No-op — Graphiti processes episodes synchronously."""
        if progress_callback:
            progress_callback("Episodes processed (synchronous)", 1.0)

    def delete_graph(self, graph_id: str) -> None:
        """Delete all data for this graph."""
        from graphiti import get_graphiti_instance, reset, _run  # noqa: PLC0415
        try:
            graphiti = _run(get_graphiti_instance())
            from graphiti_core.utils.maintenance.graph_data_operations import clear_data  # noqa: PLC0415
            _run(clear_data(graphiti.driver, group_ids=[graph_id]))
        except Exception as exc:
            logger.warning("Failed to clear graph %s: %s", graph_id, exc)
        reset()

    def _get_graph_info(self, graph_id: str) -> Dict[str, Any]:
        """Get graph statistics."""
        from graphiti import get_graphiti_instance, _run  # noqa: PLC0415
        graphiti = _run(get_graphiti_instance())
        from graphiti_core.nodes import EntityNode  # noqa: PLC0415
        from graphiti_core.edges import EntityEdge  # noqa: PLC0415
        nodes = _run(EntityNode.get_by_group_ids(graphiti.driver, [graph_id]))
        edges = _run(EntityEdge.get_by_group_ids(graphiti.driver, [graph_id]))
        return {"node_count": len(nodes), "edge_count": len(edges)}
