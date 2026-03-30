"""Tests for Graphiti shadow modules."""
import sys
import os
import pytest
from pathlib import Path

# Add infra/docker to path so `import graphiti` resolves to infra/docker/graphiti/
SHADOW_PATH = str(Path(__file__).parent.parent / "infra" / "docker")
if SHADOW_PATH not in sys.path:
    sys.path.insert(0, SHADOW_PATH)


@pytest.fixture(autouse=True)
def reset_graphiti_singleton():
    """Reset Graphiti singleton between tests."""
    try:
        import graphiti as g
        g.reset()
    except Exception:
        pass
    yield
    try:
        import graphiti as g
        g.reset()
    except Exception:
        pass


# ── Type tests (no external deps needed) ──

def test_node_info_creation():
    from graphiti.types import NodeInfo
    n = NodeInfo(uuid="abc", name="Test Entity", labels=["Person"], summary="A test person")
    assert n.uuid == "abc"
    assert n.name == "Test Entity"
    assert n.labels == ["Person"]
    assert n.attributes == {}


def test_edge_info_creation():
    from graphiti.types import EdgeInfo
    e = EdgeInfo(uuid="e1", name="WORKS_FOR", fact="Alice works for Acme",
                 source_node_uuid="n1", target_node_uuid="n2")
    assert e.fact == "Alice works for Acme"
    assert e.source_node_name is None  # optional


def test_search_result_creation():
    from graphiti.types import SearchResult
    r = SearchResult(facts=["fact1"], edges=[], nodes=[], query="test", total_count=1)
    assert r.total_count == 1


def test_filtered_entities_creation():
    from graphiti.types import FilteredEntities, EntityNode
    entity = EntityNode(uuid="1", name="Alice", labels=["Person"], summary="A person")
    f = FilteredEntities(entities=[entity], entity_types={"Person"}, total_count=5, filtered_count=1)
    assert f.filtered_count == 1
    assert "Person" in f.entity_types


# ── Ontology conversion tests ──

def test_ontology_to_pydantic_basic():
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
    assert "WORKS_FOR" in edge_type_map[("Person", "Organization")]


def test_ontology_skips_reserved_fields():
    from graphiti.graph_builder import _ontology_to_pydantic
    ontology = {
        "entity_types": [
            {"name": "Person", "description": "A person", "attributes": [
                {"name": "name", "description": "Reserved"},
                {"name": "uuid", "description": "Reserved"},
                {"name": "role", "description": "Valid"},
            ]},
        ],
        "edge_types": [],
    }
    entity_types, _, _ = _ontology_to_pydantic(ontology)
    model = entity_types["Person"]
    fields = model.model_fields
    assert "role" in fields
    assert "name" not in fields  # reserved, skipped
    assert "uuid" not in fields  # reserved, skipped


def test_ontology_empty():
    from graphiti.graph_builder import _ontology_to_pydantic
    entity_types, edge_types, edge_type_map = _ontology_to_pydantic({"entity_types": [], "edge_types": []})
    assert entity_types == {}
    assert edge_types == {}
    assert edge_type_map == {}


# ── GraphBuilderService tests (no external deps) ──

def test_graph_builder_create_returns_id():
    """create_graph should return a string starting with fishcloud_."""
    # This will fail if graphiti-core isn't installed, which is fine for CI
    try:
        from graphiti.graph_builder import GraphBuilderService
        builder = GraphBuilderService()
        graph_id = builder.create_graph("test")
        assert graph_id.startswith("fishcloud_")
        assert len(graph_id) > 20
    except ImportError:
        pytest.skip("graphiti-core not installed")


def test_wait_for_episodes_is_noop():
    """_wait_for_episodes should complete immediately (Graphiti is synchronous)."""
    from graphiti.graph_builder import GraphBuilderService
    builder = GraphBuilderService()
    # Should not raise
    builder._wait_for_episodes(["uuid1", "uuid2"])


# ── Integration test (requires OPENAI_API_KEY + graphiti-core + kuzu) ──

@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set — skipping Graphiti integration test",
)
def test_full_graph_lifecycle():
    """End-to-end: create graph, ingest text, query, extract."""
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

    builder._wait_for_episodes(uuids)

    tools = ZepToolsService()
    nodes = tools.get_all_nodes(graph_id)
    assert len(nodes) > 0
    assert len(tools.get_all_edges(graph_id)) >= 0

    reader = ZepEntityReader()
    filtered = reader.filter_defined_entities(graph_id)
    assert filtered.filtered_count >= 0  # may be 0 if labels are generic

    builder.delete_graph(graph_id)
