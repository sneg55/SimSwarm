# Zep Integration Tests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add test coverage for Zep graph extraction, graph API endpoint, and import correctness — prevent regressions like the ZepToolsService class name bug.

**Architecture:** Tests live in `tests/` with mocked Zep SDK objects. `extract_graph_data()` is tested by importing it from `infra/docker/run_job.py` with sys.path manipulation. Graph API endpoint tests use the standard httpx test client.

**Tech Stack:** pytest-asyncio, unittest.mock, httpx AsyncClient

**GitHub Issue:** #3

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `tests/test_zep_graph_extraction.py` | Create | Unit tests for `extract_graph_data()` |
| `tests/test_graph_api.py` | Create | Tests for GET `/api/jobs/{id}/graph` endpoint |

---

### Task 1: Import Correctness Tests

**Files:**
- Create: `tests/test_zep_graph_extraction.py`

These tests verify the imports used by `extract_graph_data()` actually resolve — catching bugs like the `ZepToolService` vs `ZepToolsService` typo.

- [ ] **Step 1: Write import verification tests**

```python
# tests/test_zep_graph_extraction.py
"""Tests for Zep graph extraction (infra/docker/run_job.py:extract_graph_data).

We import the function by adding infra/docker to sys.path and mocking the
MiroFish dependencies that aren't available in the test environment.
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# We need to make run_job importable. It normally runs inside the GPU worker
# container with MiroFish on the path. For tests, we mock those imports.
_INFRA_DOCKER = str(Path(__file__).parent.parent / "infra" / "docker")


def _import_extract_graph_data():
    """Import extract_graph_data from run_job.py with mocked MiroFish deps."""
    # Mock the MiroFish app.services.zep_tools module
    mock_zep_tools = MagicMock()
    mock_zep_tools.ZepToolsService = MagicMock

    with patch.dict(sys.modules, {"app": MagicMock(), "app.services": MagicMock(), "app.services.zep_tools": mock_zep_tools}):
        if _INFRA_DOCKER not in sys.path:
            sys.path.insert(0, _INFRA_DOCKER)
        # Force re-import
        if "run_job" in sys.modules:
            del sys.modules["run_job"]
        import run_job
        return run_job.extract_graph_data


def test_extract_graph_data_is_importable():
    """Regression test: extract_graph_data must be importable without errors."""
    fn = _import_extract_graph_data()
    assert callable(fn)


def test_extract_graph_data_references_zep_tools_service_not_zep_tool_service():
    """Regression for commit 63a8064: class was ZepToolService (singular), should be ZepToolsService."""
    source = (Path(__file__).parent.parent / "infra" / "docker" / "run_job.py").read_text()
    assert "ZepToolsService" in source
    assert "ZepToolService" not in source.replace("ZepToolsService", "")
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/test_zep_graph_extraction.py::test_extract_graph_data_is_importable tests/test_zep_graph_extraction.py::test_extract_graph_data_references_zep_tools_service_not_zep_tool_service -v`
Expected: 2 PASS (the class name was already fixed in commit 63a8064)

- [ ] **Step 3: Commit**

```bash
git add tests/test_zep_graph_extraction.py
git commit -m "test: add import correctness tests for Zep graph extraction"
```

---

### Task 2: Graph Extraction — Happy Path

**Files:**
- Modify: `tests/test_zep_graph_extraction.py`

- [ ] **Step 1: Write tests for successful graph extraction**

Append to `tests/test_zep_graph_extraction.py`:

```python
def _make_mock_node(uuid, name, labels, summary=""):
    """Create a mock Zep node object with attribute access."""
    node = MagicMock()
    node.uuid = uuid
    node.name = name
    node.labels = labels
    node.summary = summary
    return node


def _make_mock_edge(uuid, name, fact, src_uuid, tgt_uuid, src_name="", tgt_name=""):
    """Create a mock Zep edge object with attribute access."""
    edge = MagicMock()
    edge.uuid = uuid
    edge.name = name
    edge.fact = fact
    edge.source_node_uuid = src_uuid
    edge.target_node_uuid = tgt_uuid
    edge.source_node_name = src_name
    edge.target_node_name = tgt_name
    return edge


def test_extract_graph_returns_correct_structure():
    """extract_graph_data should return dict with nodes, edges, metadata."""
    mock_nodes = [
        _make_mock_node("n1", "Alice", ["Person", "Entity"], "A researcher"),
        _make_mock_node("n2", "MIT", ["University", "Entity"], "A university"),
    ]
    mock_edges = [
        _make_mock_edge("e1", "WORKS_AT", "Alice works at MIT", "n1", "n2", "Alice", "MIT"),
    ]

    mock_zep_service = MagicMock()
    mock_zep_service.get_all_nodes.return_value = mock_nodes
    mock_zep_service.get_all_edges.return_value = mock_edges

    # Patch the ZepToolsService constructor to return our mock
    mock_zep_module = MagicMock()
    mock_zep_module.ZepToolsService.return_value = mock_zep_service

    with patch.dict(sys.modules, {
        "app": MagicMock(),
        "app.services": MagicMock(),
        "app.services.zep_tools": mock_zep_module,
    }):
        with patch.dict("os.environ", {"ZEP_API_KEY": "test-key"}):
            if _INFRA_DOCKER not in sys.path:
                sys.path.insert(0, _INFRA_DOCKER)
            if "run_job" in sys.modules:
                del sys.modules["run_job"]
            import run_job
            result = run_job.extract_graph_data("graph-123")

    # Structure check
    assert "nodes" in result
    assert "edges" in result
    assert "metadata" in result

    # Nodes
    assert len(result["nodes"]) == 2
    alice = result["nodes"][0]
    assert alice["uuid"] == "n1"
    assert alice["name"] == "Alice"
    assert alice["labels"] == ["Person", "Entity"]
    assert alice["summary"] == "A researcher"
    assert alice["connection_count"] == 1  # 1 edge touching Alice

    # Edges
    assert len(result["edges"]) == 1
    edge = result["edges"][0]
    assert edge["uuid"] == "e1"
    assert edge["name"] == "WORKS_AT"
    assert edge["fact"] == "Alice works at MIT"
    assert edge["source_node_uuid"] == "n1"
    assert edge["target_node_uuid"] == "n2"

    # Metadata
    assert result["metadata"]["total_nodes"] == 2
    assert result["metadata"]["total_edges"] == 1
    assert "Person" in result["metadata"]["entity_types"]
    assert "University" in result["metadata"]["entity_types"]


def test_extract_graph_connection_count_is_correct():
    """Nodes connected by multiple edges have correct connection_count."""
    mock_nodes = [
        _make_mock_node("n1", "A", ["Person"]),
        _make_mock_node("n2", "B", ["Person"]),
        _make_mock_node("n3", "C", ["Person"]),
    ]
    mock_edges = [
        _make_mock_edge("e1", "KNOWS", "A knows B", "n1", "n2"),
        _make_mock_edge("e2", "KNOWS", "A knows C", "n1", "n3"),
        _make_mock_edge("e3", "KNOWS", "B knows C", "n2", "n3"),
    ]

    mock_zep_service = MagicMock()
    mock_zep_service.get_all_nodes.return_value = mock_nodes
    mock_zep_service.get_all_edges.return_value = mock_edges

    mock_zep_module = MagicMock()
    mock_zep_module.ZepToolsService.return_value = mock_zep_service

    with patch.dict(sys.modules, {
        "app": MagicMock(),
        "app.services": MagicMock(),
        "app.services.zep_tools": mock_zep_module,
    }):
        with patch.dict("os.environ", {"ZEP_API_KEY": "test-key"}):
            if "run_job" in sys.modules:
                del sys.modules["run_job"]
            import run_job
            result = run_job.extract_graph_data("graph-456")

    counts = {n["name"]: n["connection_count"] for n in result["nodes"]}
    assert counts["A"] == 2  # edges e1, e2
    assert counts["B"] == 2  # edges e1, e3
    assert counts["C"] == 2  # edges e2, e3


def test_extract_graph_entity_types_excludes_generic_labels():
    """Entity types should not include 'Entity' or 'Node' generic labels."""
    mock_nodes = [
        _make_mock_node("n1", "X", ["Entity", "Node", "Person"]),
    ]

    mock_zep_service = MagicMock()
    mock_zep_service.get_all_nodes.return_value = mock_nodes
    mock_zep_service.get_all_edges.return_value = []

    mock_zep_module = MagicMock()
    mock_zep_module.ZepToolsService.return_value = mock_zep_service

    with patch.dict(sys.modules, {
        "app": MagicMock(),
        "app.services": MagicMock(),
        "app.services.zep_tools": mock_zep_module,
    }):
        with patch.dict("os.environ", {"ZEP_API_KEY": "test-key"}):
            if "run_job" in sys.modules:
                del sys.modules["run_job"]
            import run_job
            result = run_job.extract_graph_data("graph-789")

    # "Person" should be in entity_types, but not "Entity" or "Node"
    assert "Person" in result["metadata"]["entity_types"]
    assert "Entity" not in result["metadata"]["entity_types"]
    assert "Node" not in result["metadata"]["entity_types"]
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/test_zep_graph_extraction.py -v -k "not import"`
Expected: 4 PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_zep_graph_extraction.py
git commit -m "test: add happy-path tests for Zep graph extraction"
```

---

### Task 3: Graph Extraction — Error Handling

**Files:**
- Modify: `tests/test_zep_graph_extraction.py`

- [ ] **Step 1: Write tests for failure scenarios**

Append to `tests/test_zep_graph_extraction.py`:

```python
def test_extract_graph_returns_empty_on_api_key_missing():
    """Missing ZEP_API_KEY should return empty graph, not crash."""
    mock_zep_module = MagicMock()
    mock_zep_module.ZepToolsService.side_effect = ValueError("ZEP_API_KEY未配置")

    with patch.dict(sys.modules, {
        "app": MagicMock(),
        "app.services": MagicMock(),
        "app.services.zep_tools": mock_zep_module,
    }):
        with patch.dict("os.environ", {"ZEP_API_KEY": ""}):
            if "run_job" in sys.modules:
                del sys.modules["run_job"]
            import run_job
            result = run_job.extract_graph_data("graph-err")

    assert result["nodes"] == []
    assert result["edges"] == []
    assert result["metadata"]["total_nodes"] == 0
    assert result["metadata"]["total_edges"] == 0


def test_extract_graph_returns_empty_on_connection_error():
    """Zep unreachable should return empty graph."""
    mock_zep_service = MagicMock()
    mock_zep_service.get_all_nodes.side_effect = ConnectionError("Zep unreachable")

    mock_zep_module = MagicMock()
    mock_zep_module.ZepToolsService.return_value = mock_zep_service

    with patch.dict(sys.modules, {
        "app": MagicMock(),
        "app.services": MagicMock(),
        "app.services.zep_tools": mock_zep_module,
    }):
        with patch.dict("os.environ", {"ZEP_API_KEY": "test-key"}):
            if "run_job" in sys.modules:
                del sys.modules["run_job"]
            import run_job
            result = run_job.extract_graph_data("graph-conn-err")

    assert result["nodes"] == []
    assert result["edges"] == []


def test_extract_graph_returns_empty_on_timeout():
    """Zep timeout should return empty graph."""
    mock_zep_service = MagicMock()
    mock_zep_service.get_all_nodes.side_effect = TimeoutError("request timed out")

    mock_zep_module = MagicMock()
    mock_zep_module.ZepToolsService.return_value = mock_zep_service

    with patch.dict(sys.modules, {
        "app": MagicMock(),
        "app.services": MagicMock(),
        "app.services.zep_tools": mock_zep_module,
    }):
        with patch.dict("os.environ", {"ZEP_API_KEY": "test-key"}):
            if "run_job" in sys.modules:
                del sys.modules["run_job"]
            import run_job
            result = run_job.extract_graph_data("graph-timeout")

    assert result["nodes"] == []
    assert result["edges"] == []


def test_extract_graph_empty_graph_returns_valid_structure():
    """Zep returns 0 nodes and 0 edges — still valid structure."""
    mock_zep_service = MagicMock()
    mock_zep_service.get_all_nodes.return_value = []
    mock_zep_service.get_all_edges.return_value = []

    mock_zep_module = MagicMock()
    mock_zep_module.ZepToolsService.return_value = mock_zep_service

    with patch.dict(sys.modules, {
        "app": MagicMock(),
        "app.services": MagicMock(),
        "app.services.zep_tools": mock_zep_module,
    }):
        with patch.dict("os.environ", {"ZEP_API_KEY": "test-key"}):
            if "run_job" in sys.modules:
                del sys.modules["run_job"]
            import run_job
            result = run_job.extract_graph_data("graph-empty")

    assert result["nodes"] == []
    assert result["edges"] == []
    assert result["metadata"]["total_nodes"] == 0
    assert result["metadata"]["total_edges"] == 0
    assert result["metadata"]["entity_types"] == []
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/test_zep_graph_extraction.py -v`
Expected: All pass (the function already has try/except returning empty graph)

- [ ] **Step 3: Commit**

```bash
git add tests/test_zep_graph_extraction.py
git commit -m "test: add error handling tests for Zep graph extraction"
```

---

### Task 4: Graph API Endpoint Tests

**Files:**
- Create: `tests/test_graph_api.py`

- [ ] **Step 1: Write tests for GET `/api/jobs/{id}/graph`**

```python
# tests/test_graph_api.py
"""Tests for the GET /api/jobs/{id}/graph endpoint."""
import json
import pytest
from unittest.mock import patch

from saas.models.job import SimulationJob, JobStatus


SAMPLE_GRAPH = json.dumps({
    "nodes": [
        {"uuid": "n1", "name": "Alice", "labels": ["Person"], "summary": "", "connection_count": 1},
    ],
    "edges": [
        {"uuid": "e1", "name": "KNOWS", "fact": "Alice knows Bob",
         "source_node_uuid": "n1", "target_node_uuid": "n2",
         "source_node_name": "Alice", "target_node_name": "Bob"},
    ],
    "metadata": {"entity_types": ["Person"], "total_nodes": 1, "total_edges": 1},
})


async def _create_job(db_session, user_id, graph_data=None, status=JobStatus.COMPLETED):
    """Helper to create a SimulationJob in the test DB."""
    job = SimulationJob(
        user_id=user_id,
        seed_text="test seed",
        goal="test goal",
        tier="small",
        credits_charged=30,
        status=status,
        result_graph=graph_data,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    return job


async def test_get_graph_returns_graph_data(client, auth_headers, db_session):
    user_id = auth_headers["_user_id"]
    job = await _create_job(db_session, user_id, graph_data=SAMPLE_GRAPH)

    resp = await client.get(f"/api/jobs/{job.id}/graph", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["nodes"]) == 1
    assert data["nodes"][0]["name"] == "Alice"
    assert len(data["edges"]) == 1
    assert data["metadata"]["total_nodes"] == 1


async def test_get_graph_returns_404_for_no_graph_data(client, auth_headers, db_session):
    user_id = auth_headers["_user_id"]
    job = await _create_job(db_session, user_id, graph_data=None)

    resp = await client.get(f"/api/jobs/{job.id}/graph", headers=auth_headers)
    assert resp.status_code == 404
    assert "not available" in resp.json()["detail"]


async def test_get_graph_returns_404_for_nonexistent_job(client, auth_headers):
    resp = await client.get("/api/jobs/99999/graph", headers=auth_headers)
    assert resp.status_code == 404


async def test_get_graph_returns_403_for_other_users_job(client, auth_headers, db_session):
    """User cannot access another user's graph data."""
    job = await _create_job(db_session, user_id="other-user", graph_data=SAMPLE_GRAPH)

    resp = await client.get(f"/api/jobs/{job.id}/graph", headers=auth_headers)
    assert resp.status_code == 403


async def test_get_graph_returns_401_without_auth(client, db_session):
    job = await _create_job(db_session, user_id="user-1", graph_data=SAMPLE_GRAPH)

    resp = await client.get(f"/api/jobs/{job.id}/graph")
    assert resp.status_code == 401


async def test_get_graph_handles_malformed_json(client, auth_headers, db_session):
    """If stored graph JSON is malformed, return 500."""
    user_id = auth_headers["_user_id"]
    job = await _create_job(db_session, user_id, graph_data="not valid json{{{")

    resp = await client.get(f"/api/jobs/{job.id}/graph", headers=auth_headers)
    assert resp.status_code == 500
    assert "Invalid graph data" in resp.json()["detail"]


async def test_get_graph_with_empty_graph_json(client, auth_headers, db_session):
    """Empty but valid graph structure."""
    user_id = auth_headers["_user_id"]
    empty_graph = json.dumps({
        "nodes": [], "edges": [],
        "metadata": {"entity_types": [], "total_nodes": 0, "total_edges": 0},
    })
    job = await _create_job(db_session, user_id, graph_data=empty_graph)

    resp = await client.get(f"/api/jobs/{job.id}/graph", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["nodes"] == []
    assert data["edges"] == []
    assert data["metadata"]["total_nodes"] == 0
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/test_graph_api.py -v`
Expected: All 7 PASS (the endpoint already exists in `saas/api/jobs.py:104-121`)

- [ ] **Step 3: Commit**

```bash
git add tests/test_graph_api.py
git commit -m "test: add comprehensive tests for graph API endpoint"
```

---

### Task 5: Graph Data Persistence Test

**Files:**
- Modify: `tests/test_graph_api.py`

- [ ] **Step 1: Write test verifying graph_data survives job completion**

Append to `tests/test_graph_api.py`:

```python
async def test_graph_data_persisted_after_job_save(db_session):
    """Simulate _save_job_results writing graph_data and verify it's readable."""
    from sqlalchemy import text

    # Create a pending job
    job = SimulationJob(
        user_id="user-persist",
        seed_text="test",
        goal="test",
        tier="small",
        credits_charged=30,
        status=JobStatus.PENDING,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    # Simulate what _save_job_results does (raw SQL update)
    await db_session.execute(
        text(
            "UPDATE simulation_jobs "
            "SET status = 'COMPLETED', result_graph = :graph_data "
            "WHERE id = :job_id"
        ),
        {"graph_data": SAMPLE_GRAPH, "job_id": job.id},
    )
    await db_session.commit()

    # Re-read and verify
    await db_session.refresh(job)
    assert job.status == JobStatus.COMPLETED
    assert job.result_graph is not None
    parsed = json.loads(job.result_graph)
    assert len(parsed["nodes"]) == 1
    assert parsed["nodes"][0]["name"] == "Alice"
```

- [ ] **Step 2: Run test**

Run: `pytest tests/test_graph_api.py::test_graph_data_persisted_after_job_save -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_graph_api.py
git commit -m "test: add graph data persistence verification test"
```

---

### Task 6: Final Regression Suite

- [ ] **Step 1: Run all tests**

Run: `pytest tests/ -v --timeout=30`
Expected: All pass

- [ ] **Step 2: Verify test count increased**

Run: `pytest tests/ --co -q | tail -5`
Expected: should show new test files `test_zep_graph_extraction.py` and `test_graph_api.py` with ~18 new tests total

- [ ] **Step 3: Commit any final fixups**

```bash
git add tests/
git commit -m "test: finalize Zep integration test suite"
```
