# Graphiti + Kuzu Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Zep Cloud with Graphiti + Kuzu (embedded) running in-process on the GPU pod, using shadow modules that intercept MiroFish's Zep imports.

**Architecture:** Five shadow modules in `infra/docker/graphiti/` implement the same class interfaces as MiroFish's Zep services (`GraphBuilderService`, `ZepToolsService`, `ZepEntityReader`, paging utils) backed by Graphiti+Kuzu. On pod startup, `run_job.py` injects the shadow path into `sys.path` before MiroFish's path. Kuzu runs in-memory (`:memory:`), vLLM handles entity extraction, OpenAI handles embeddings.

**Tech Stack:** graphiti-core, kuzu, OpenAI embeddings API, Python dataclasses matching MiroFish's return types

---

## Task 1: Graphiti singleton + shared types

**Files:**
- Create: `infra/docker/graphiti/__init__.py`
- Create: `infra/docker/graphiti/types.py`

- [ ] **Step 1: Create shared return type dataclasses**

Create `infra/docker/graphiti/types.py` with all the dataclasses MiroFish expects:

```python
"""Return types matching MiroFish's Zep service interfaces."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


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
```

- [ ] **Step 2: Create Graphiti singleton factory**

Create `infra/docker/graphiti/__init__.py`:

```python
"""Graphiti + Kuzu singleton for MiroFish shadow modules."""
from __future__ import annotations

import asyncio
import logging
import os

logger = logging.getLogger(__name__)

_instance = None
_entity_types = None
_edge_types = None
_edge_type_map = None


def _run(coro):
    """Run async coroutine from sync context."""
    try:
        asyncio.get_running_loop()
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    except RuntimeError:
        return asyncio.run(coro)


async def get_graphiti_instance():
    """Lazy singleton — creates Graphiti with Kuzu in-memory + vLLM + OpenAI embedder."""
    global _instance
    if _instance is not None:
        return _instance

    from graphiti_core import Graphiti
    from graphiti_core.driver.kuzu_driver import KuzuDriver
    from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient
    from graphiti_core.llm_client.config import LLMConfig
    from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig

    driver = KuzuDriver(db=":memory:")

    llm_client = OpenAIGenericClient(
        config=LLMConfig(
            api_key=os.getenv("LLM_API_KEY", "not-needed"),
            model=os.getenv("LLM_MODEL_NAME", "Qwen/Qwen2.5-32B-Instruct-AWQ"),
            base_url=os.getenv("LLM_BASE_URL", "http://localhost:8000/v1"),
            temperature=0,
        ),
    )

    embedder = OpenAIEmbedder(
        config=OpenAIEmbedderConfig(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            embedding_model="text-embedding-3-small",
            embedding_dim=1536,
        )
    )

    _instance = Graphiti(
        graph_driver=driver,
        llm_client=llm_client,
        embedder=embedder,
    )
    logger.info("Graphiti + Kuzu initialized (in-memory)")
    return _instance


def get_stored_entity_types():
    return _entity_types


def get_stored_edge_types():
    return _edge_types


def get_stored_edge_type_map():
    return _edge_type_map


def store_ontology(entity_types, edge_types, edge_type_map):
    global _entity_types, _edge_types, _edge_type_map
    _entity_types = entity_types
    _edge_types = edge_types
    _edge_type_map = edge_type_map


def reset():
    """Reset singleton for next job (if pod reuses)."""
    global _instance, _entity_types, _edge_types, _edge_type_map
    _instance = None
    _entity_types = None
    _edge_types = None
    _edge_type_map = None
```

- [ ] **Step 3: Commit**

```bash
git add infra/docker/graphiti/__init__.py infra/docker/graphiti/types.py
git commit -m "feat: Graphiti singleton factory + shared MiroFish-compatible types"
```

---

## Task 2: Shadow GraphBuilderService

**Files:**
- Create: `infra/docker/graphiti/graph_builder.py`

- [ ] **Step 1: Create shadow GraphBuilderService**

Create `infra/docker/graphiti/graph_builder.py` implementing the same interface MiroFish expects:

```python
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
        from graphiti import get_graphiti_instance, get_stored_entity_types, get_stored_edge_types, get_stored_edge_type_map, _run

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
                from graphiti_core.nodes import EpisodeType
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
        from graphiti import get_graphiti_instance, reset, _run
        try:
            graphiti = _run(get_graphiti_instance())
            from graphiti_core.utils.maintenance.graph_data_operations import clear_data
            _run(clear_data(graphiti.driver, group_ids=[graph_id]))
        except Exception as exc:
            logger.warning("Failed to clear graph %s: %s", graph_id, exc)
        reset()

    def _get_graph_info(self, graph_id: str) -> Dict[str, Any]:
        """Get graph statistics."""
        from graphiti import get_graphiti_instance, _run
        graphiti = _run(get_graphiti_instance())
        from graphiti_core.nodes import EntityNode
        from graphiti_core.edges import EntityEdge
        nodes = _run(EntityNode.get_by_group_ids(graphiti.driver, [graph_id]))
        edges = _run(EntityEdge.get_by_group_ids(graphiti.driver, [graph_id]))
        return {"node_count": len(nodes), "edge_count": len(edges)}
```

- [ ] **Step 2: Commit**

```bash
git add infra/docker/graphiti/graph_builder.py
git commit -m "feat: shadow GraphBuilderService backed by Graphiti + Kuzu"
```

---

## Task 3: Shadow zep_paging

**Files:**
- Create: `infra/docker/graphiti/zep_paging.py`

- [ ] **Step 1: Create shadow zep_paging**

Create `infra/docker/graphiti/zep_paging.py` — replaces `app.utils.zep_paging`. Since Kuzu is local, no pagination or retries needed:

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add infra/docker/graphiti/zep_paging.py
git commit -m "feat: shadow zep_paging — local Kuzu queries, no pagination needed"
```

---

## Task 4: Shadow ZepEntityReader

**Files:**
- Create: `infra/docker/graphiti/zep_entity_reader.py`

- [ ] **Step 1: Create shadow ZepEntityReader**

Create `infra/docker/graphiti/zep_entity_reader.py`:

```python
"""Shadow ZepEntityReader backed by Graphiti + Kuzu.

Replaces app.services.zep_entity_reader.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set

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

        all_edges_data = []
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

        # Build edge lookup per node
        node_edges = {}
        for edge in all_edges_data:
            for uid in (edge["source_node_uuid"], edge["target_node_uuid"]):
                node_edges.setdefault(uid, []).append(edge)

        entities = []
        entity_types: set[str] = set()
        total_count = len(raw_nodes)

        for n in raw_nodes:
            labels = n.labels or []
            # Skip nodes with only generic labels
            specific_labels = [l for l in labels if l not in ("Entity", "Node")]
            if defined_entity_types:
                if not any(l in defined_entity_types for l in specific_labels):
                    continue
            elif not specific_labels:
                continue

            for l in specific_labels:
                entity_types.add(l)

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
        """Get a single entity with its related edges and nodes."""
        from graphiti import get_graphiti_instance, _run
        from graphiti_core.nodes import EntityNode as GEntityNode

        graphiti = _run(get_graphiti_instance())
        try:
            node = _run(GEntityNode.get_by_uuid(graphiti.driver, entity_uuid))
        except Exception:
            return None

        return EntityNode(
            uuid=node.uuid,
            name=node.name or "",
            labels=node.labels or [],
            summary=node.summary or "",
            attributes=node.attributes or {},
        )

    def get_all_edges(self, graph_id: str) -> List[Dict[str, Any]]:
        """Get all edges in the graph."""
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
```

- [ ] **Step 2: Commit**

```bash
git add infra/docker/graphiti/zep_entity_reader.py
git commit -m "feat: shadow ZepEntityReader backed by Graphiti + Kuzu"
```

---

## Task 5: Shadow ZepToolsService

**Files:**
- Create: `infra/docker/graphiti/zep_tools.py`

- [ ] **Step 1: Create shadow ZepToolsService**

Create `infra/docker/graphiti/zep_tools.py` — the largest shadow module, implements search and report agent tools:

```python
"""Shadow ZepToolsService backed by Graphiti + Kuzu.

Replaces app.services.zep_tools.ZepToolsService.
"""
from __future__ import annotations

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
                from app.utils.llm_client import LLMClient
                self._llm_client = LLMClient()
            except Exception:
                pass
        return self._llm_client

    def search_graph(
        self,
        graph_id: str,
        query: str,
        limit: int = 10,
        scope: str = "edges",
    ) -> SearchResult:
        """Hybrid search on the graph."""
        from graphiti import get_graphiti_instance, _run

        graphiti = _run(get_graphiti_instance())

        try:
            from graphiti_core.search.search_config_recipes import (
                COMBINED_HYBRID_SEARCH_CROSS_ENCODER,
                EDGE_HYBRID_SEARCH_RRF,
                NODE_HYBRID_SEARCH_RRF,
            )

            if scope == "nodes":
                config = NODE_HYBRID_SEARCH_RRF
            elif scope == "both":
                config = COMBINED_HYBRID_SEARCH_CROSS_ENCODER
            else:
                config = EDGE_HYBRID_SEARCH_RRF

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
            logger.warning("search_graph failed, falling back to local: %s", exc)
            return self._local_search(graph_id, query, limit)

    def _local_search(self, graph_id: str, query: str, limit: int) -> SearchResult:
        """Keyword-based fallback search."""
        all_edges = self.get_all_edges(graph_id)
        query_lower = query.lower()
        matching_facts = []
        matching_edges = []

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
        from graphiti import get_graphiti_instance, _run
        from graphiti_core.nodes import EntityNode as GEntityNode

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
        from graphiti import get_graphiti_instance, _run
        from graphiti_core.edges import EntityEdge as GEntityEdge

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
        """Deep search: generate sub-queries, search each, aggregate results."""
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
                lines = [l.strip() for l in response.split("\n") if l.strip() and len(l.strip()) > 10]
                if lines:
                    sub_queries = lines[:max_sub_queries]
            except Exception as exc:
                logger.warning("Failed to generate sub-queries: %s", exc)

        # Search for each sub-query
        all_facts = []
        all_entities = []
        all_chains = []

        for sq in sub_queries:
            result = self.search_graph(graph_id, sq, limit=10, scope="both")
            all_facts.extend(result.facts)
            for node in result.nodes:
                all_entities.append(node)

        # Deduplicate facts
        seen = set()
        unique_facts = []
        for f in all_facts:
            if f not in seen:
                seen.add(f)
                unique_facts.append(f)

        return InsightForgeResult(
            query=query,
            simulation_requirement=simulation_requirement,
            sub_queries=sub_queries,
            semantic_facts=unique_facts,
            entity_insights=all_entities,
            relationship_chains=all_chains,
            total_facts=len(unique_facts),
            total_entities=len(all_entities),
            total_relationships=len(all_chains),
        )

    def panorama_search(
        self,
        graph_id: str,
        query: str,
        include_expired: bool = True,
        limit: int = 50,
    ) -> PanoramaResult:
        """Broad search returning all nodes and edges."""
        all_nodes = self.get_all_nodes(graph_id)
        all_edges = self.get_all_edges(graph_id, include_temporal=True)

        active_facts = [e.fact for e in all_edges if e.fact and not e.expired_at]
        historical_facts = [e.fact for e in all_edges if e.fact and e.expired_at]

        return PanoramaResult(
            query=query,
            all_nodes=all_nodes,
            all_edges=all_edges,
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
        """Simple search — delegates to search_graph."""
        return self.search_graph(graph_id, query, limit=limit, scope="edges")
```

- [ ] **Step 2: Commit**

```bash
git add infra/docker/graphiti/zep_tools.py
git commit -m "feat: shadow ZepToolsService with search, insight_forge, panorama"
```

---

## Task 6: Wire shadow modules into run_job.py + update Dockerfile

**Files:**
- Modify: `infra/docker/run_job.py`
- Modify: `infra/docker/Dockerfile.worker`

- [ ] **Step 1: Inject shadow module path in run_job.py**

In `infra/docker/run_job.py`, find the section where `sys.path.insert(0, MIROFISH_BACKEND)` is called (in `_patch_mirofish_prompts_to_english` and in `main()`). Add the shadow path BEFORE the MiroFish path.

At the top of the file, after the existing constants:

```python
GRAPHITI_SHADOW = "/app/graphiti"
```

In `main()`, before `sys.path.insert(0, MIROFISH_BACKEND)`:

```python
    # 2b. Inject Graphiti shadow modules BEFORE MiroFish backend
    sys.path.insert(0, GRAPHITI_SHADOW)
```

Also in `_patch_mirofish_prompts_to_english()`, the line `sys.path.insert(0, MIROFISH_BACKEND)` should be preceded by the shadow path:

```python
    if GRAPHITI_SHADOW not in sys.path:
        sys.path.insert(0, GRAPHITI_SHADOW)
    sys.path.insert(1, MIROFISH_BACKEND)
```

- [ ] **Step 2: Update Dockerfile.worker**

In `infra/docker/Dockerfile.worker`:

Replace line 20:
```dockerfile
RUN pip install --no-cache-dir --ignore-installed flask flask-cors requests zep-cloud
```
With:
```dockerfile
RUN pip install --no-cache-dir --ignore-installed flask flask-cors requests graphiti-core kuzu
```

Replace line 30 (verification):
```dockerfile
RUN python3 -c "import vllm; print(f'vLLM {vllm.__version__}')" && \
    python3 -c "import flask; print(f'Flask {flask.__version__}')" && \
    python3 -c "import oasis; print('OASIS OK')" && \
    python3 -c "import zep_cloud; print('Zep OK')"
```
With:
```dockerfile
RUN python3 -c "import vllm; print(f'vLLM {vllm.__version__}')" && \
    python3 -c "import flask; print(f'Flask {flask.__version__}')" && \
    python3 -c "import oasis; print('OASIS OK')" && \
    python3 -c "import graphiti_core; print('Graphiti OK')" && \
    python3 -c "import kuzu; print('Kuzu OK')"
```

Add after line 38 (`COPY infra/docker/worker_api.py /app/worker_api.py`):
```dockerfile
COPY infra/docker/graphiti/ /app/graphiti/
```

- [ ] **Step 3: Commit**

```bash
git add infra/docker/run_job.py infra/docker/Dockerfile.worker
git commit -m "feat: wire shadow modules into run_job.py + swap zep-cloud for graphiti in Dockerfile"
```

---

## Task 7: Update SaaS layer — remove ZEP_API_KEY, add OPENAI_API_KEY

**Files:**
- Modify: `saas/workers/job_runner.py`
- Modify: `saas/workers/tasks.py`
- Modify: `saas/config.py`

- [ ] **Step 1: Update JobConfig.to_mirofish_env()**

In `saas/workers/job_runner.py`, update `to_mirofish_env()` to remove `ZEP_API_KEY` and add `OPENAI_API_KEY`:

```python
    def to_mirofish_env(self) -> dict[str, str]:
        return {
            "LLM_API_KEY": self.llm_api_key,
            "LLM_BASE_URL": "http://localhost:8000/v1",
            "LLM_MODEL_NAME": self.model_id,
            "OPENAI_API_KEY": self.openai_api_key,
            "OASIS_DEFAULT_MAX_ROUNDS": str(self.max_rounds),
            "MODEL_ID": self.model_id,
            "VLLM_ARGS": self.vllm_args or "--max-model-len 32768",
        }
```

Update the `JobConfig` dataclass to replace `zep_api_key` with `openai_api_key`.

- [ ] **Step 2: Update task dispatch**

In `saas/workers/tasks.py`, replace `zep_api_key` with `openai_api_key` in `run_simulation_task` parameters and the `JobConfig` constructor.

In `saas/api/jobs.py`, update the `run_simulation_task.delay()` call to pass `openai_api_key=os.getenv("OPENAI_API_KEY", "")` instead of `zep_api_key`.

- [ ] **Step 3: Update config**

In `saas/config.py`, add `OPENAI_API_KEY: str = ""` and remove the requirement for `ZEP_API_KEY` (make it optional or remove).

- [ ] **Step 4: Run backend tests**

Run: `cd /Users/sneg55/Documents/GitHub/.worktrees/kuzu-migration && python -m pytest tests/ -x -q`
Expected: All pass (tests mock at Celery level, don't touch Zep)

- [ ] **Step 5: Commit**

```bash
git add saas/workers/job_runner.py saas/workers/tasks.py saas/config.py saas/api/jobs.py
git commit -m "feat: replace ZEP_API_KEY with OPENAI_API_KEY in job pipeline"
```

---

## Task 8: Integration test with real Kuzu

**Files:**
- Create: `tests/test_graphiti_shadow.py`

- [ ] **Step 1: Create integration test**

```python
"""Tests for Graphiti shadow modules with real Kuzu in-memory."""
import sys
import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add shadow modules to path
SHADOW_PATH = str(Path(__file__).parent.parent / "infra" / "docker" / "graphiti")
if SHADOW_PATH not in sys.path:
    sys.path.insert(0, SHADOW_PATH)


@pytest.fixture(autouse=True)
def reset_graphiti():
    """Reset Graphiti singleton between tests."""
    import graphiti as g
    g.reset()
    yield
    g.reset()


def test_types_import():
    from graphiti.types import NodeInfo, EdgeInfo, SearchResult, FilteredEntities
    node = NodeInfo(uuid="1", name="Test", labels=["Person"], summary="A person")
    assert node.name == "Test"


def test_graph_builder_create():
    from graphiti.graph_builder import GraphBuilderService
    builder = GraphBuilderService()
    graph_id = builder.create_graph("test-graph")
    assert graph_id.startswith("fishcloud_")


def test_ontology_to_pydantic():
    from graphiti.graph_builder import _ontology_to_pydantic
    ontology = {
        "entity_types": [
            {"name": "Person", "description": "A person", "attributes": [
                {"name": "role", "description": "Their role"}
            ]},
            {"name": "Organization", "description": "An org", "attributes": []},
        ],
        "edge_types": [
            {"name": "WORKS_FOR", "description": "Employment", "attributes": [],
             "source_targets": [{"source": "Person", "target": "Organization"}]},
        ],
    }
    entity_types, edge_types, edge_type_map = _ontology_to_pydantic(ontology)
    assert "Person" in entity_types
    assert "Organization" in entity_types
    assert "WORKS_FOR" in edge_types
    assert ("Person", "Organization") in edge_type_map


@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set — skipping Graphiti integration test",
)
def test_full_graph_lifecycle():
    """End-to-end test: create graph, ingest text, query, extract."""
    from graphiti.graph_builder import GraphBuilderService
    from graphiti.zep_tools import ZepToolsService
    from graphiti.zep_entity_reader import ZepEntityReader

    builder = GraphBuilderService()
    graph_id = builder.create_graph("integration-test")

    ontology = {
        "entity_types": [
            {"name": "Person", "description": "A person", "attributes": []},
            {"name": "Organization", "description": "An org", "attributes": []},
        ],
        "edge_types": [
            {"name": "WORKS_FOR", "description": "Works at", "attributes": [],
             "source_targets": [{"source": "Person", "target": "Organization"}]},
        ],
    }
    builder.set_ontology(graph_id, ontology)

    chunks = [
        "John Smith is the CEO of Acme Corp, a leading technology company.",
        "Acme Corp recently acquired Widget Inc for $500 million.",
    ]
    uuids = builder.add_text_batches(graph_id, chunks)
    assert len(uuids) > 0

    # Wait is a no-op for Graphiti
    builder._wait_for_episodes(uuids)

    # Query the graph
    tools = ZepToolsService()
    nodes = tools.get_all_nodes(graph_id)
    edges = tools.get_all_edges(graph_id)
    assert len(nodes) > 0

    # Entity filtering
    reader = ZepEntityReader()
    filtered = reader.filter_defined_entities(graph_id)
    assert filtered.filtered_count > 0

    # Cleanup
    builder.delete_graph(graph_id)
```

- [ ] **Step 2: Run tests**

Run: `cd /Users/sneg55/Documents/GitHub/.worktrees/kuzu-migration && python -m pytest tests/test_graphiti_shadow.py -v`
Expected: Unit tests pass, integration test skipped without OPENAI_API_KEY

- [ ] **Step 3: Commit**

```bash
git add tests/test_graphiti_shadow.py
git commit -m "test: Graphiti shadow module unit + integration tests"
```
