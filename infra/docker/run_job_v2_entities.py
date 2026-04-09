"""Entity extraction helpers for run_job_v2.

Provides:
  - _fallback_entities()   — capitalized-word extraction when Neo4j unavailable
  - build_entities_from_graph()  — convert Neo4j nodes → Entity list
  - get_entities()         — top-level: try graph_ops, fall back to text extraction
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure simswarm package is importable when this module is loaded standalone
_DOCKER_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _DOCKER_DIR.parent.parent
for _p in (str(_DOCKER_DIR), str(_REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from simswarm.types import Entity

# ---------------------------------------------------------------------------
# Optional MiroShark graph tooling
# ---------------------------------------------------------------------------

try:
    from graph_ops import build_graph as _build_graph  # type: ignore[import]
    _GRAPH_OPS_AVAILABLE = True
except ImportError:
    _GRAPH_OPS_AVAILABLE = False
    _build_graph = None

try:
    from app.storage.neo4j_storage import Neo4jStorage  # type: ignore[import]
    _NEO4J_STORAGE_AVAILABLE = True
except ImportError:
    _NEO4J_STORAGE_AVAILABLE = False
    Neo4jStorage = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _fallback_entities(seed_text: str, count: int) -> list[Entity]:
    """Extract entities from seed text when Neo4j is unavailable.

    Picks title-case words, deduplicates, returns at most *count* Entity objects.
    Returns at least 1 entity even when fewer capitalized words exist than *count*.
    """
    words = seed_text.split()
    seen: list[str] = []
    seen_lower: set[str] = set()
    for w in words:
        cleaned = w.strip(".,!?;:\"'()-[]")
        if not cleaned:
            continue
        if cleaned[0].isupper() and cleaned.lower() not in seen_lower:
            seen_lower.add(cleaned.lower())
            seen.append(cleaned)

    selected = seen[:count] if seen else ["Entity"]
    entities = []
    for name in selected:
        eid = name.lower().replace(" ", "_")
        entities.append(Entity(
            id=eid,
            name=name,
            type="person",
            summary=f"{name} is a key entity identified in the seed document.",
        ))
    return entities


def build_entities_from_graph(storage, graph_id: str) -> list[Entity]:
    """Convert Neo4j nodes (via storage) into Entity objects."""
    nodes = storage.get_all_nodes(graph_id) if hasattr(storage, "get_all_nodes") else []
    entities: list[Entity] = []
    for node in nodes:
        name = node.get("name", "")
        if not name:
            continue
        labels = node.get("labels", [])
        etype = next((l for l in labels if l not in ("Entity", "Node")), "Entity")
        entities.append(Entity(
            id=node.get("uuid", name.lower().replace(" ", "_")),
            name=name,
            type=etype,
            summary=node.get("summary", f"{name} — extracted from knowledge graph."),
        ))
    return entities


def get_entities(
    seed_text: str,
    goal: str,
    target_agents: int,
) -> list[Entity]:
    """Return entities for the simulation.

    Tries graph_ops first; falls back to capitalized-word extraction.
    """
    entities: list[Entity] = []

    if _GRAPH_OPS_AVAILABLE and _NEO4J_STORAGE_AVAILABLE:
        try:
            storage = Neo4jStorage()
            _project_id, graph_id = _build_graph(seed_text, goal, storage)
            print(f"[run_job_v2] Graph built: graph_id={graph_id}", flush=True)
            entities = build_entities_from_graph(storage, graph_id)
        except Exception as exc:
            print(
                f"[run_job_v2] WARNING: graph_ops failed ({exc}), using fallback",
                flush=True,
            )

    if not entities:
        entities = _fallback_entities(seed_text, count=max(target_agents, 10))
        print(f"[run_job_v2] Fallback entities: {[e.name for e in entities]}", flush=True)

    return entities
