"""Tests for Zep graph extraction logic in infra/docker/run_job.py."""
from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock, patch



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _setup_run_job_imports():
    """
    Prepare sys.path and sys.modules so that ``import run_job`` resolves
    without pulling in the real MiroFish backend.
    """
    docker_dir = str(__import__("pathlib").Path(__file__).resolve().parents[1] / "infra" / "docker")
    if docker_dir not in sys.path:
        sys.path.insert(0, docker_dir)

    # Stub out the MiroFish dependency tree that run_job imports lazily
    app_mod = types.ModuleType("app")
    app_services = types.ModuleType("app.services")
    app_services_zep = types.ModuleType("app.services.zep_tools")
    app_services_zep.ZepToolsService = MagicMock()

    sys.modules.setdefault("app", app_mod)
    sys.modules.setdefault("app.services", app_services)
    sys.modules["app.services.zep_tools"] = app_services_zep

    # Force a fresh import of run_job so patches take effect
    sys.modules.pop("run_job", None)


def _make_mock_node(uuid: str, name: str, labels: list[str], summary: str) -> MagicMock:
    node = MagicMock()
    node.uuid = uuid
    node.name = name
    node.labels = labels
    node.summary = summary
    return node


def _make_mock_edge(
    uuid: str,
    name: str,
    fact: str,
    src_uuid: str,
    tgt_uuid: str,
    src_name: str,
    tgt_name: str,
) -> MagicMock:
    edge = MagicMock()
    edge.uuid = uuid
    edge.name = name
    edge.fact = fact
    edge.source_node_uuid = src_uuid
    edge.target_node_uuid = tgt_uuid
    edge.source_node_name = src_name
    edge.target_node_name = tgt_name
    return edge


def _import_run_job(mock_zep_cls: MagicMock | None = None):
    """Set up mocks, force re-import, and return the run_job module."""
    _setup_run_job_imports()
    if mock_zep_cls is not None:
        sys.modules["app.services.zep_tools"].ZepToolsService = mock_zep_cls
    import run_job  # noqa: PLC0415
    return run_job


# ---------------------------------------------------------------------------
# Task 1 — Import correctness
# ---------------------------------------------------------------------------

class TestImportCorrectness:
    def test_extract_graph_data_is_importable(self):
        run_job = _import_run_job()
        assert hasattr(run_job, "extract_graph_data")
        assert callable(run_job.extract_graph_data)

    def test_extract_graph_data_references_zep_tools_service_not_zep_tool_service(self):
        """Regression: the class name must be ZepToolsService (plural), not
        the old ZepToolService (singular)."""
        source_path = (
            __import__("pathlib").Path(__file__).resolve().parents[1]
            / "infra"
            / "docker"
            / "run_job.py"
        )
        source = source_path.read_text()
        assert "ZepToolsService" in source
        # The singular form should NOT appear (unless as part of the plural)
        import re
        singular_hits = re.findall(r"ZepToolService(?!s)", source)
        assert singular_hits == [], (
            f"Found old singular class name ZepToolService in run_job.py: {singular_hits}"
        )


# ---------------------------------------------------------------------------
# Task 2 — Happy-path extraction
# ---------------------------------------------------------------------------

class TestGraphExtractionHappyPath:
    @patch.dict("os.environ", {"ZEP_API_KEY": "test-key"})
    def test_extract_graph_returns_correct_structure(self):
        nodes = [
            _make_mock_node("n1", "Alice", ["Entity", "Person"], "A person"),
            _make_mock_node("n2", "Bob", ["Entity", "Person"], "Another person"),
        ]
        edge = _make_mock_edge("e1", "knows", "Alice knows Bob", "n1", "n2", "Alice", "Bob")

        mock_cls = MagicMock()
        mock_cls.return_value.get_all_nodes.return_value = nodes
        mock_cls.return_value.get_all_edges.return_value = [edge]

        run_job = _import_run_job(mock_cls)
        result = run_job.extract_graph_data("graph-id")

        assert isinstance(result, dict)
        assert len(result["nodes"]) == 2
        assert len(result["edges"]) == 1
        assert result["metadata"]["total_nodes"] == 2
        assert result["metadata"]["total_edges"] == 1
        assert "Person" in result["metadata"]["entity_types"]

        # Verify node structure
        node_names = {n["name"] for n in result["nodes"]}
        assert node_names == {"Alice", "Bob"}

        # Verify edge structure
        e = result["edges"][0]
        assert e["uuid"] == "e1"
        assert e["source_node_uuid"] == "n1"
        assert e["target_node_uuid"] == "n2"

    @patch.dict("os.environ", {"ZEP_API_KEY": "test-key"})
    def test_extract_graph_connection_count_is_correct(self):
        nodes = [
            _make_mock_node("n1", "Alice", ["Person"], ""),
            _make_mock_node("n2", "Bob", ["Person"], ""),
            _make_mock_node("n3", "Carol", ["Person"], ""),
        ]
        edges = [
            _make_mock_edge("e1", "knows", "", "n1", "n2", "Alice", "Bob"),
            _make_mock_edge("e2", "knows", "", "n2", "n3", "Bob", "Carol"),
            _make_mock_edge("e3", "knows", "", "n1", "n3", "Alice", "Carol"),
        ]

        mock_cls = MagicMock()
        mock_cls.return_value.get_all_nodes.return_value = nodes
        mock_cls.return_value.get_all_edges.return_value = edges

        run_job = _import_run_job(mock_cls)
        result = run_job.extract_graph_data("graph-id")

        counts = {n["name"]: n["connection_count"] for n in result["nodes"]}
        # n1 (Alice): e1 src + e3 src = 2
        assert counts["Alice"] == 2
        # n2 (Bob): e1 tgt + e2 src = 2
        assert counts["Bob"] == 2
        # n3 (Carol): e2 tgt + e3 tgt = 2
        assert counts["Carol"] == 2

    @patch.dict("os.environ", {"ZEP_API_KEY": "test-key"})
    def test_extract_graph_entity_types_excludes_generic_labels(self):
        nodes = [
            _make_mock_node("n1", "Alice", ["Entity", "Node", "Person"], ""),
        ]

        mock_cls = MagicMock()
        mock_cls.return_value.get_all_nodes.return_value = nodes
        mock_cls.return_value.get_all_edges.return_value = []

        run_job = _import_run_job(mock_cls)
        result = run_job.extract_graph_data("graph-id")

        entity_types = result["metadata"]["entity_types"]
        assert "Person" in entity_types
        assert "Entity" not in entity_types
        assert "Node" not in entity_types


# ---------------------------------------------------------------------------
# Task 3 — Error handling
# ---------------------------------------------------------------------------

class TestGraphExtractionErrors:
    @patch.dict("os.environ", {"ZEP_API_KEY": "test-key"})
    def test_extract_graph_returns_empty_on_api_key_missing(self):
        mock_cls = MagicMock()
        mock_cls.side_effect = ValueError("API key is invalid")

        run_job = _import_run_job(mock_cls)
        result = run_job.extract_graph_data("graph-id")

        assert result["nodes"] == []
        assert result["edges"] == []
        assert result["metadata"]["total_nodes"] == 0
        assert result["metadata"]["total_edges"] == 0

    @patch.dict("os.environ", {"ZEP_API_KEY": "test-key"})
    def test_extract_graph_returns_empty_on_connection_error(self):
        mock_cls = MagicMock()
        mock_cls.return_value.get_all_nodes.side_effect = ConnectionError("unreachable")

        run_job = _import_run_job(mock_cls)
        result = run_job.extract_graph_data("graph-id")

        assert result["nodes"] == []
        assert result["edges"] == []
        assert result["metadata"]["total_nodes"] == 0
        assert result["metadata"]["total_edges"] == 0

    @patch.dict("os.environ", {"ZEP_API_KEY": "test-key"})
    def test_extract_graph_returns_empty_on_timeout(self):
        mock_cls = MagicMock()
        mock_cls.return_value.get_all_nodes.side_effect = TimeoutError("timed out")

        run_job = _import_run_job(mock_cls)
        result = run_job.extract_graph_data("graph-id")

        assert result["nodes"] == []
        assert result["edges"] == []
        assert result["metadata"]["total_nodes"] == 0
        assert result["metadata"]["total_edges"] == 0

    @patch.dict("os.environ", {"ZEP_API_KEY": "test-key"})
    def test_extract_graph_empty_graph_returns_valid_structure(self):
        mock_cls = MagicMock()
        mock_cls.return_value.get_all_nodes.return_value = []
        mock_cls.return_value.get_all_edges.return_value = []

        run_job = _import_run_job(mock_cls)
        result = run_job.extract_graph_data("graph-id")

        assert result["nodes"] == []
        assert result["edges"] == []
        assert result["metadata"]["total_nodes"] == 0
        assert result["metadata"]["total_edges"] == 0
        assert result["metadata"]["entity_types"] == []
