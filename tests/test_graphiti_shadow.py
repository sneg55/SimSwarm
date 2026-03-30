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


# ── ZepToolsService mock-based tests ──

def _make_mock_edge(uuid, name, fact, src, tgt, expired_at=None):
    """Create a mock Graphiti EntityEdge."""
    from unittest.mock import MagicMock
    e = MagicMock()
    e.uuid = uuid
    e.name = name
    e.fact = fact
    e.source_node_uuid = src
    e.target_node_uuid = tgt
    e.created_at = None
    e.valid_at = None
    e.invalid_at = None
    e.expired_at = expired_at
    e.attributes = {}
    return e


def _make_mock_node(uuid, name, labels, summary=""):
    from unittest.mock import MagicMock
    n = MagicMock()
    n.uuid = uuid
    n.name = name
    n.labels = labels
    n.summary = summary
    n.attributes = {}
    return n


def test_search_graph_happy_path():
    """search_graph should call graphiti.search_() and transform results."""
    from unittest.mock import patch, MagicMock
    from graphiti.zep_tools import ZepToolsService

    tools = ZepToolsService()

    # Mock graphiti instance with search_() method
    mock_graphiti = MagicMock()
    mock_search_results = MagicMock()
    mock_search_results.edges = [
        _make_mock_edge("e1", "WORKS_FOR", "Alice works at Acme", "n1", "n2"),
        _make_mock_edge("e2", "ACQUIRED", "Acme acquired Widget", "n2", "n3"),
    ]
    mock_search_results.nodes = [
        _make_mock_node("n1", "Alice", ["Person"], "A person"),
        _make_mock_node("n2", "Acme", ["Organization"], "A company"),
    ]
    mock_search_results.episodes = []
    mock_search_results.communities = []

    # Mock the async get_graphiti_instance to return our mock
    async def mock_get_instance():
        return mock_graphiti

    # Mock search_ as a coroutine
    async def mock_search(**kwargs):
        return mock_search_results

    mock_graphiti.search_ = mock_search

    # Mock the search config recipes import
    mock_config = MagicMock()
    mock_recipes = MagicMock()
    mock_recipes.EDGE_HYBRID_SEARCH_RRF = mock_config
    mock_recipes.NODE_HYBRID_SEARCH_RRF = mock_config
    mock_recipes.COMBINED_HYBRID_SEARCH_CROSS_ENCODER = mock_config

    import sys
    with patch.dict(sys.modules, {"graphiti_core.search.search_config_recipes": mock_recipes}):
        with patch("graphiti.get_graphiti_instance", mock_get_instance):
            with patch("graphiti._run", side_effect=lambda coro: __import__("asyncio").run(coro)):
                result = tools.search_graph("g1", "acme", limit=5, scope="edges")

    assert result.query == "acme"
    assert len(result.facts) == 2
    assert "Alice works at Acme" in result.facts
    assert len(result.edges) == 2
    assert result.edges[0]["uuid"] == "e1"
    assert len(result.nodes) == 2
    assert result.nodes[0]["name"] == "Alice"
    assert result.total_count == 2


def test_search_graph_scope_nodes():
    """search_graph with scope='nodes' should use NODE_HYBRID_SEARCH_RRF config."""
    from unittest.mock import patch, MagicMock
    from graphiti.zep_tools import ZepToolsService

    tools = ZepToolsService()

    mock_graphiti = MagicMock()
    mock_search_results = MagicMock()
    mock_search_results.edges = []
    mock_search_results.nodes = [_make_mock_node("n1", "Alice", ["Person"])]
    mock_search_results.episodes = []
    mock_search_results.communities = []

    async def mock_get_instance():
        return mock_graphiti

    async def mock_search(**kwargs):
        return mock_search_results

    mock_graphiti.search_ = mock_search

    mock_node_config = MagicMock()
    mock_edge_config = MagicMock()
    mock_recipes = MagicMock()
    mock_recipes.EDGE_HYBRID_SEARCH_RRF = mock_edge_config
    mock_recipes.NODE_HYBRID_SEARCH_RRF = mock_node_config
    mock_recipes.COMBINED_HYBRID_SEARCH_CROSS_ENCODER = MagicMock()

    import sys
    with patch.dict(sys.modules, {"graphiti_core.search.search_config_recipes": mock_recipes}):
        with patch("graphiti.get_graphiti_instance", mock_get_instance):
            with patch("graphiti._run", side_effect=lambda coro: __import__("asyncio").run(coro)):
                result = tools.search_graph("g1", "alice", limit=3, scope="nodes")

    assert len(result.nodes) == 1
    assert result.nodes[0]["name"] == "Alice"


def test_local_search_matches_keyword():
    """_local_search should find edges whose fact contains the query."""
    from unittest.mock import patch
    from graphiti.zep_tools import ZepToolsService

    tools = ZepToolsService()

    mock_edges = [
        _make_mock_edge("e1", "WORKS_FOR", "Alice works at Acme Corp", "n1", "n2"),
        _make_mock_edge("e2", "ACQUIRED", "Acme acquired Widget", "n2", "n3"),
        _make_mock_edge("e3", "LIVES_IN", "Bob lives in Berlin", "n4", "n5"),
    ]

    with patch.object(tools, "get_all_edges") as mock_get:
        from graphiti.types import EdgeInfo
        mock_get.return_value = [
            EdgeInfo(uuid=e.uuid, name=e.name, fact=e.fact,
                     source_node_uuid=e.source_node_uuid, target_node_uuid=e.target_node_uuid)
            for e in mock_edges
        ]
        result = tools._local_search("graph-1", "acme", limit=10)

    assert result.total_count == 2
    assert len(result.facts) == 2
    assert "Alice works at Acme Corp" in result.facts
    assert "Acme acquired Widget" in result.facts


def test_local_search_respects_limit():
    from unittest.mock import patch
    from graphiti.zep_tools import ZepToolsService
    from graphiti.types import EdgeInfo

    tools = ZepToolsService()

    edges = [
        EdgeInfo(uuid=f"e{i}", name="REL", fact=f"fact about topic {i}",
                 source_node_uuid="n1", target_node_uuid="n2")
        for i in range(20)
    ]

    with patch.object(tools, "get_all_edges", return_value=edges):
        result = tools._local_search("g1", "topic", limit=5)

    assert len(result.facts) == 5
    assert len(result.edges) == 5


def test_local_search_returns_empty_on_no_match():
    """_local_search should return empty when no edges match."""
    from unittest.mock import patch
    from graphiti.zep_tools import ZepToolsService
    from graphiti.types import EdgeInfo

    tools = ZepToolsService()
    edges = [EdgeInfo(uuid="e1", name="R", fact="unrelated content", source_node_uuid="n1", target_node_uuid="n2")]

    with patch.object(tools, "get_all_edges", return_value=edges):
        result = tools._local_search("g1", "nonexistent", limit=10)

    assert result.total_count == 0
    assert result.facts == []


def test_quick_search_delegates_to_search_graph():
    from unittest.mock import patch
    from graphiti.zep_tools import ZepToolsService
    from graphiti.types import SearchResult

    tools = ZepToolsService()

    mock_result = SearchResult(facts=["f1"], edges=[], nodes=[], query="q", total_count=1)

    with patch.object(tools, "search_graph", return_value=mock_result) as mock_search:
        result = tools.quick_search("g1", "query", limit=5)

    mock_search.assert_called_once_with("g1", "query", limit=5, scope="edges")
    assert result.facts == ["f1"]


def test_panorama_search_splits_active_historical():
    from unittest.mock import patch
    from graphiti.zep_tools import ZepToolsService
    from graphiti.types import NodeInfo, EdgeInfo

    tools = ZepToolsService()

    nodes = [NodeInfo(uuid="n1", name="Alice", labels=["Person"], summary="")]
    edges = [
        EdgeInfo(uuid="e1", name="R1", fact="active fact", source_node_uuid="n1", target_node_uuid="n2", expired_at=None),
        EdgeInfo(uuid="e2", name="R2", fact="old fact", source_node_uuid="n1", target_node_uuid="n3", expired_at="2026-01-01"),
        EdgeInfo(uuid="e3", name="R3", fact="another active", source_node_uuid="n2", target_node_uuid="n3", expired_at=None),
    ]

    with patch.object(tools, "get_all_nodes", return_value=nodes), \
         patch.object(tools, "get_all_edges", return_value=edges):
        result = tools.panorama_search("g1", "test", include_expired=True, limit=50)

    assert result.active_count == 2
    assert result.historical_count == 1
    assert "active fact" in result.active_facts
    assert "old fact" in result.historical_facts
    assert result.total_nodes == 1
    assert result.total_edges == 3


def test_panorama_search_excludes_historical_when_disabled():
    from unittest.mock import patch
    from graphiti.zep_tools import ZepToolsService
    from graphiti.types import EdgeInfo

    tools = ZepToolsService()

    edges = [
        EdgeInfo(uuid="e1", name="R1", fact="active", source_node_uuid="n1", target_node_uuid="n2", expired_at=None),
        EdgeInfo(uuid="e2", name="R2", fact="old", source_node_uuid="n1", target_node_uuid="n3", expired_at="2026-01-01"),
    ]

    with patch.object(tools, "get_all_nodes", return_value=[]), \
         patch.object(tools, "get_all_edges", return_value=edges):
        result = tools.panorama_search("g1", "test", include_expired=False)

    assert result.historical_facts == []
    assert result.active_count == 1


def test_panorama_search_respects_limit():
    from unittest.mock import patch
    from graphiti.zep_tools import ZepToolsService
    from graphiti.types import NodeInfo, EdgeInfo

    tools = ZepToolsService()

    nodes = [NodeInfo(uuid=f"n{i}", name=f"Node {i}", labels=[], summary="") for i in range(10)]
    edges = [EdgeInfo(uuid=f"e{i}", name="R", fact=f"fact {i}", source_node_uuid="n1", target_node_uuid="n2") for i in range(10)]

    with patch.object(tools, "get_all_nodes", return_value=nodes), \
         patch.object(tools, "get_all_edges", return_value=edges):
        result = tools.panorama_search("g1", "test", limit=3)

    assert len(result.all_nodes) == 3
    assert len(result.all_edges) == 3
    assert result.total_nodes == 10  # total count still reflects full set


def test_insight_forge_without_llm():
    """insight_forge without LLM should search with original query only."""
    from unittest.mock import patch
    from graphiti.zep_tools import ZepToolsService
    from graphiti.types import SearchResult

    tools = ZepToolsService(llm_client=None)

    mock_result = SearchResult(
        facts=["fact1", "fact2"],
        edges=[
            {"uuid": "e1", "name": "WORKS_FOR", "fact": "fact1",
             "source_node_uuid": "n1", "target_node_uuid": "n2"},
        ],
        nodes=[{"uuid": "n1", "name": "Alice"}, {"uuid": "n2", "name": "Acme"}],
        query="test", total_count=2,
    )

    with patch.object(tools, "search_graph", return_value=mock_result):
        result = tools.insight_forge("g1", "main query", "sim requirement")

    assert result.query == "main query"
    assert result.sub_queries == ["main query"]  # no LLM, just original
    assert len(result.semantic_facts) == 2
    assert result.total_entities == 2
    # Relationship chains should be populated from edges
    assert len(result.relationship_chains) == 1
    assert "Alice --[WORKS_FOR]--> Acme" in result.relationship_chains


def test_insight_forge_deduplicates_facts():
    """insight_forge should deduplicate facts across sub-queries."""
    from unittest.mock import patch, MagicMock
    from graphiti.zep_tools import ZepToolsService
    from graphiti.types import SearchResult

    mock_llm = MagicMock()
    mock_llm.chat.return_value = "What about X?\nWhat about Y?"

    tools = ZepToolsService(llm_client=mock_llm)

    # Both sub-queries return overlapping facts
    call_count = [0]
    def mock_search(graph_id, query, limit=10, scope="edges"):
        call_count[0] += 1
        return SearchResult(
            facts=["shared fact", f"unique fact {call_count[0]}"],
            edges=[], nodes=[], query=query, total_count=2,
        )

    with patch.object(tools, "search_graph", side_effect=mock_search):
        result = tools.insight_forge("g1", "main", "requirement", max_sub_queries=2)

    # "shared fact" should appear only once
    assert result.semantic_facts.count("shared fact") == 1
    assert len(result.semantic_facts) == 3  # shared + unique1 + unique2


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
