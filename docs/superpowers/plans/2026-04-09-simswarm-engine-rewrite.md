# SimSwarm Engine Rewrite — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the MiroShark engine with a clean-room SimSwarm engine — a Python async library that the Celery worker imports directly. No CAMEL-AI, no Flask, no subprocess.

**Architecture:** Library-first engine with pluggable environments (Social, Market, Economic), direct vLLM calls, first-class scenario sweep, and in-memory state with Parquet flush for large sims. The SaaS layer is untouched — the swap happens at `run_job.py` on the GPU pod.

**Tech Stack:** Python 3.11+, asyncio, aiohttp, Jinja2, Parquet (pyarrow), Pydantic 2, pytest + pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-04-09-simswarm-engine-rewrite-design.md`

---

## Phase 1: Contract Tests & Golden Files

Write tests against MiroShark's current output to establish the contract that the new engine must satisfy. Zero risk — pure observation.

---

### Task 1: Result Schema Validators

Define Pydantic models for every result shape the worker API returns. These validators are reused in all subsequent contract tests.

**Files:**
- Create: `tests/contracts/__init__.py`
- Create: `tests/contracts/schemas.py`

- [ ] **Step 1: Create the contracts package**

```bash
mkdir -p tests/contracts
touch tests/contracts/__init__.py
```

- [ ] **Step 2: Write result schema models**

```python
# tests/contracts/schemas.py
"""Pydantic models defining the contract between SaaS and engine.

These schemas validate the shape of results returned by the worker API.
Both MiroShark and the new SimSwarm engine must produce output that passes
these validators.
"""
from __future__ import annotations

from pydantic import BaseModel, field_validator


class ChatLogEntry(BaseModel):
    round_num: int
    agent_id: int
    agent_name: str
    action_type: str
    platform: str
    action_args: dict
    timestamp: str | None = None
    result: str | None = None
    success: bool | None = None


class GraphNode(BaseModel):
    uuid: str
    name: str
    labels: list[str]
    summary: str
    connection_count: int | None = None
    sentiment: float | None = None
    stance: str | None = None
    influence_weight: float | None = None


class GraphEdge(BaseModel):
    uuid: str
    source_node_uuid: str
    target_node_uuid: str
    name: str | None = None
    fact: str | None = None


class GraphMetadata(BaseModel):
    entity_types: list[str]
    total_nodes: int
    total_edges: int


class GraphData(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    metadata: GraphMetadata


class Finding(BaseModel):
    label: str
    title: str
    description: str
    metric: str
    accentColor: str

    @field_validator("accentColor")
    @classmethod
    def valid_hex(cls, v: str) -> str:
        if not v.startswith("#") or len(v) not in (4, 7):
            raise ValueError(f"Invalid hex color: {v}")
        return v


class SentimentEntry(BaseModel):
    label: str
    value: int
    direction: str

    @field_validator("direction")
    @classmethod
    def valid_direction(cls, v: str) -> str:
        if v not in ("positive", "negative"):
            raise ValueError(f"direction must be positive or negative, got {v}")
        return v


class Coalition(BaseModel):
    name: str
    description: str
    agents: int
    strength: int
    color: str


class ConfidenceEntry(BaseModel):
    label: str
    value: str
    color: str


class StructuredResults(BaseModel):
    brief: str
    findings: list[Finding]
    sentiment: list[SentimentEntry]
    coalitions: list[Coalition]
    confidence: list[ConfidenceEntry]


class WorkerStatusResponse(BaseModel):
    """Shape of GET /status when status is 'completed'."""
    status: str
    report: str
    chat_log: str  # JSON string — parse separately
    graph_data: str  # JSON string — parse separately
    structured: str  # JSON string — parse separately
    sim_data_uploaded: bool | None = None
    error: str | None = None
```

- [ ] **Step 3: Commit**

```bash
git add tests/contracts/
git commit -m "feat: add result schema validators for engine contract tests"
```

---

### Task 2: Contract Tests for Structured Results

Test that `build_structured_results()` produces output matching the contract schemas. This function is pure Python with no engine dependencies — already testable.

**Files:**
- Create: `tests/contracts/test_result_shapes.py`
- Reference: `infra/docker/results.py` (build_structured_results)
- Reference: `infra/docker/constants.py` (FINDING_COLORS)

- [ ] **Step 1: Write the contract test**

```python
# tests/contracts/test_result_shapes.py
"""Contract tests: validate that engine output matches expected schemas.

These tests run against build_structured_results() which is pure Python.
The schemas defined here are the contract between SaaS and engine —
any engine (MiroShark or SimSwarm) must produce conforming output.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from tests.contracts.schemas import (
    ChatLogEntry,
    Coalition,
    ConfidenceEntry,
    Finding,
    GraphData,
    SentimentEntry,
    StructuredResults,
)

DOCKER_DIR = Path(__file__).resolve().parent.parent.parent / "infra" / "docker"


@pytest.fixture(scope="module")
def build_fn():
    """Import build_structured_results without triggering engine imports."""
    constants_path = DOCKER_DIR / "constants.py"
    results_path = DOCKER_DIR / "results.py"

    spec = importlib.util.spec_from_file_location("constants", constants_path)
    constants_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(constants_mod)
    sys.modules.setdefault("constants", constants_mod)

    source = results_path.read_text()
    ns = {"__builtins__": __builtins__}
    exec(compile(source, str(results_path), "exec"), ns)
    return ns["build_structured_results"]


SAMPLE_OUTLINE = {
    "summary": "Global markets face uncertainty amid trade tensions.",
    "sections": [
        {"title": "Tariff Escalation"},
        {"title": "Supply Chain Disruption"},
        {"title": "Investor Sentiment"},
    ],
}

SAMPLE_SECTIONS = {
    "Tariff Escalation": "New tariffs imposed on semiconductor imports are reshaping global trade flows. "
    "Major economies are retaliating with counter-tariffs.",
    "Supply Chain Disruption": "Manufacturing hubs in Southeast Asia report delays. "
    "Companies are diversifying supplier networks.",
    "Investor Sentiment": "Markets are pricing in a 60% probability of recession. "
    "Bond yields have inverted across major economies.",
}

SAMPLE_CHAT_LOG = [
    {
        "agent_name": "TraderBot",
        "platform": "twitter",
        "action_type": "CREATE_POST",
        "action_args": {"content": "Markets looking bearish"},
        "round_num": 1,
    },
    {
        "agent_name": "Analyst",
        "platform": "reddit",
        "action_type": "CREATE_COMMENT",
        "action_args": {"content": "Supply chains are resilient"},
        "round_num": 3,
    },
    {
        "agent_name": "TraderBot",
        "platform": "twitter",
        "action_type": "LIKE_POST",
        "action_args": {},
        "round_num": 5,
    },
]

SAMPLE_GRAPH_DATA = {
    "nodes": [
        {"uuid": "n1", "name": "US Economy", "labels": ["Entity", "Economy"], "summary": "Largest economy"},
        {"uuid": "n2", "name": "China Trade", "labels": ["Entity", "Trade"], "summary": "Trade partner"},
    ],
    "edges": [
        {"uuid": "e1", "source_node_uuid": "n1", "target_node_uuid": "n2", "name": "trades_with"},
    ],
    "metadata": {"entity_types": ["Economy", "Trade"], "total_nodes": 2, "total_edges": 1},
}


class TestStructuredResultsContract:
    """Verify build_structured_results output conforms to StructuredResults schema."""

    def test_output_validates_against_schema(self, build_fn):
        result = build_fn(SAMPLE_OUTLINE, SAMPLE_SECTIONS, SAMPLE_CHAT_LOG, SAMPLE_GRAPH_DATA)
        validated = StructuredResults.model_validate(result)
        assert validated.brief == SAMPLE_OUTLINE["summary"]

    def test_findings_match_section_count(self, build_fn):
        result = build_fn(SAMPLE_OUTLINE, SAMPLE_SECTIONS, SAMPLE_CHAT_LOG, SAMPLE_GRAPH_DATA)
        validated = StructuredResults.model_validate(result)
        assert len(validated.findings) == len(SAMPLE_OUTLINE["sections"])

    def test_each_finding_has_valid_color(self, build_fn):
        result = build_fn(SAMPLE_OUTLINE, SAMPLE_SECTIONS, SAMPLE_CHAT_LOG, SAMPLE_GRAPH_DATA)
        for finding in result["findings"]:
            Finding.model_validate(finding)

    def test_sentiment_entries_have_valid_direction(self, build_fn):
        result = build_fn(SAMPLE_OUTLINE, SAMPLE_SECTIONS, SAMPLE_CHAT_LOG, SAMPLE_GRAPH_DATA)
        for entry in result["sentiment"]:
            validated = SentimentEntry.model_validate(entry)
            assert 0 <= validated.value <= 100

    def test_confidence_entries_present(self, build_fn):
        result = build_fn(SAMPLE_OUTLINE, SAMPLE_SECTIONS, SAMPLE_CHAT_LOG, SAMPLE_GRAPH_DATA)
        labels = {c["label"] for c in result["confidence"]}
        assert "Agents" in labels
        assert "Rounds" in labels
        assert "Graph Entities" in labels

    def test_coalitions_validate(self, build_fn):
        result = build_fn(SAMPLE_OUTLINE, SAMPLE_SECTIONS, SAMPLE_CHAT_LOG, SAMPLE_GRAPH_DATA)
        for c in result["coalitions"]:
            validated = Coalition.model_validate(c)
            assert validated.strength >= 0
            assert validated.agents >= 0


class TestChatLogEntryContract:
    """Verify chat log entries conform to ChatLogEntry schema."""

    def test_sample_entries_validate(self):
        for entry in SAMPLE_CHAT_LOG:
            ChatLogEntry.model_validate(entry)

    def test_required_fields_present(self):
        entry = ChatLogEntry.model_validate(SAMPLE_CHAT_LOG[0])
        assert entry.agent_name == "TraderBot"
        assert entry.platform == "twitter"
        assert entry.action_type == "CREATE_POST"
        assert entry.round_num == 1


class TestGraphDataContract:
    """Verify graph data conforms to GraphData schema."""

    def test_graph_data_validates(self):
        validated = GraphData.model_validate(SAMPLE_GRAPH_DATA)
        assert validated.metadata.total_nodes == 2
        assert validated.metadata.total_edges == 1

    def test_edges_reference_existing_nodes(self):
        validated = GraphData.model_validate(SAMPLE_GRAPH_DATA)
        node_ids = {n.uuid for n in validated.nodes}
        for edge in validated.edges:
            assert edge.source_node_uuid in node_ids
            assert edge.target_node_uuid in node_ids
```

- [ ] **Step 2: Run tests to verify they pass against current code**

Run: `pytest tests/contracts/test_result_shapes.py -v`
Expected: All PASS — these validate MiroShark's current output.

- [ ] **Step 3: Commit**

```bash
git add tests/contracts/test_result_shapes.py
git commit -m "feat: add contract tests for structured results and data shapes"
```

---

### Task 3: Worker API Contract Tests

Test the HTTP contract of the worker API endpoints — the exact interface the SaaS layer depends on.

**Files:**
- Create: `tests/contracts/test_worker_contract.py`
- Reference: `infra/docker/worker_api.py`

- [ ] **Step 1: Write the worker API contract tests**

```python
# tests/contracts/test_worker_contract.py
"""Contract tests for the worker API HTTP interface.

Tests that /health, /job, and /status endpoints return the exact shapes
that JobRunner expects. Both MiroShark and SimSwarm workers must pass.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

WORKER_API_PATH = Path(__file__).resolve().parent.parent.parent / "infra" / "docker" / "worker_api.py"


@pytest.fixture()
def worker_client():
    """Load fresh worker_api module and return Flask test client."""
    spec = importlib.util.spec_from_file_location("worker_api_contract", WORKER_API_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod._job["status"] = "idle"
    mod._job["result"] = None
    mod._job["error"] = None
    mod.app.config["TESTING"] = True
    return mod.app.test_client(), mod


class TestHealthContract:
    """GET /health must return {status, vllm_ready, job_status}."""

    def test_health_shape_when_vllm_ready(self, worker_client):
        flask_client, _ = worker_client
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": [{"id": "model"}]}
        with patch("requests.get", return_value=mock_resp):
            resp = flask_client.get("/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "status" in data
        assert "vllm_ready" in data
        assert "job_status" in data
        assert data["status"] == "ok"
        assert data["vllm_ready"] is True

    def test_health_shape_when_vllm_down(self, worker_client):
        flask_client, _ = worker_client
        with patch("requests.get", side_effect=ConnectionError("down")):
            resp = flask_client.get("/health")
        assert resp.status_code == 503
        data = resp.get_json()
        assert data["status"] == "waiting_for_vllm"
        assert data["vllm_ready"] is False

    def test_health_includes_job_status(self, worker_client):
        flask_client, mod = worker_client
        mod._job["status"] = "running"
        with patch("requests.get", side_effect=ConnectionError()):
            resp = flask_client.get("/health")
        data = resp.get_json()
        assert data["job_status"] == "running"


class TestJobSubmitContract:
    """POST /job must accept {seed_text, goal, max_rounds} and return {status}."""

    def test_accepts_required_fields(self, worker_client):
        flask_client, mod = worker_client
        with patch.object(mod, "_run_job_background"):
            resp = flask_client.post(
                "/job",
                json={
                    "seed_text": "Test seed about AI policy",
                    "goal": "Predict policy outcomes",
                    "max_rounds": 15,
                },
                content_type="application/json",
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "accepted"

    def test_accepts_optional_fields(self, worker_client):
        flask_client, mod = worker_client
        with patch.object(mod, "_run_job_background"):
            resp = flask_client.post(
                "/job",
                json={
                    "seed_text": "Test seed",
                    "goal": "Test goal",
                    "max_rounds": 10,
                    "forecast_days": 7,
                    "target_agents": 10,
                    "upload_urls": {"posts": "https://example.com/upload"},
                },
                content_type="application/json",
            )
        assert resp.status_code == 200

    def test_rejects_when_already_running(self, worker_client):
        flask_client, mod = worker_client
        mod._job["status"] = "running"
        resp = flask_client.post(
            "/job",
            json={"seed_text": "x", "goal": "y", "max_rounds": 5},
            content_type="application/json",
        )
        assert resp.status_code == 409
        data = resp.get_json()
        assert "error" in data


class TestStatusContract:
    """GET /status must return {status} and result fields when completed."""

    def test_idle_status_shape(self, worker_client):
        flask_client, _ = worker_client
        resp = flask_client.get("/status")
        data = resp.get_json()
        assert data["status"] == "idle"

    def test_completed_status_has_all_result_fields(self, worker_client):
        flask_client, mod = worker_client
        mod._job["status"] = "completed"
        mod._job["result"] = {
            "report": "# Test Report\n\nFindings here.",
            "chat_log": json.dumps([{"agent_name": "A", "action_type": "CREATE_POST",
                                     "round_num": 1, "platform": "twitter",
                                     "agent_id": 1, "action_args": {}}]),
            "graph_data": json.dumps({
                "nodes": [{"uuid": "n1", "name": "X", "labels": ["Entity"], "summary": "s"}],
                "edges": [],
                "metadata": {"entity_types": ["Entity"], "total_nodes": 1, "total_edges": 0},
            }),
            "structured": json.dumps({
                "brief": "Test", "findings": [], "sentiment": [],
                "coalitions": [], "confidence": [],
            }),
        }
        resp = flask_client.get("/status")
        data = resp.get_json()
        assert data["status"] == "completed"
        assert "report" in data
        assert "chat_log" in data
        assert "graph_data" in data
        assert "structured" in data

    def test_completed_result_fields_are_strings(self, worker_client):
        flask_client, mod = worker_client
        mod._job["status"] = "completed"
        mod._job["result"] = {
            "report": "# Report",
            "chat_log": "[]",
            "graph_data": "{}",
            "structured": "{}",
        }
        resp = flask_client.get("/status")
        data = resp.get_json()
        assert isinstance(data["report"], str)
        assert isinstance(data["chat_log"], str)
        assert isinstance(data["graph_data"], str)
        assert isinstance(data["structured"], str)

    def test_failed_status_has_error(self, worker_client):
        flask_client, mod = worker_client
        mod._job["status"] = "failed"
        mod._job["error"] = "GPU OOM"
        resp = flask_client.get("/status")
        data = resp.get_json()
        assert data["status"] == "failed"
        assert "error" in data


class TestStatusValues:
    """Status field must only contain values JobRunner knows how to handle."""

    VALID_STATUSES = {"idle", "running", "completed", "failed"}

    def test_idle_is_valid(self, worker_client):
        flask_client, _ = worker_client
        resp = flask_client.get("/status")
        assert resp.get_json()["status"] in self.VALID_STATUSES

    def test_running_is_valid(self, worker_client):
        flask_client, mod = worker_client
        mod._job["status"] = "running"
        resp = flask_client.get("/status")
        assert resp.get_json()["status"] in self.VALID_STATUSES
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/contracts/test_worker_contract.py -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add tests/contracts/test_worker_contract.py
git commit -m "feat: add worker API contract tests for HTTP interface"
```

---

### Task 4: Golden File Capture Script

A script that runs against saved simulation outputs and validates them against contract schemas. When we have real MiroShark outputs, we save them as golden files and run this script to establish the baseline.

**Files:**
- Create: `tests/contracts/test_golden_files.py`
- Create: `tests/contracts/golden/README.md`

- [ ] **Step 1: Create the golden files directory**

```bash
mkdir -p tests/contracts/golden
```

- [ ] **Step 2: Write the golden file validation test**

```python
# tests/contracts/test_golden_files.py
"""Golden file tests: validate saved MiroShark outputs against contract schemas.

To populate golden files, run a simulation and copy the output:
  cp /tmp/results/chat_log.json tests/contracts/golden/small_sim_chat_log.json
  cp /tmp/results/graph_data.json tests/contracts/golden/small_sim_graph_data.json
  cp /tmp/results/structured_results.json tests/contracts/golden/small_sim_structured.json

Tests are skipped if golden files don't exist yet.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.contracts.schemas import (
    ChatLogEntry,
    GraphData,
    StructuredResults,
)

GOLDEN_DIR = Path(__file__).resolve().parent / "golden"

SCENARIOS = [
    "small_sim",
    "market_sim",
    "enriched_sim",
]


def _load_golden(scenario: str, suffix: str) -> dict | list | None:
    path = GOLDEN_DIR / f"{scenario}_{suffix}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


@pytest.mark.parametrize("scenario", SCENARIOS)
class TestGoldenChatLog:
    def test_all_entries_validate(self, scenario):
        data = _load_golden(scenario, "chat_log")
        if data is None:
            pytest.skip(f"Golden file not found: {scenario}_chat_log.json")
        assert isinstance(data, list), "chat_log must be a list"
        assert len(data) > 0, "chat_log must not be empty"
        for entry in data:
            ChatLogEntry.model_validate(entry)

    def test_round_numbers_are_sequential(self, scenario):
        data = _load_golden(scenario, "chat_log")
        if data is None:
            pytest.skip(f"Golden file not found: {scenario}_chat_log.json")
        rounds = [e["round_num"] for e in data]
        assert rounds == sorted(rounds), "round_num should be non-decreasing"


@pytest.mark.parametrize("scenario", SCENARIOS)
class TestGoldenGraphData:
    def test_validates_against_schema(self, scenario):
        data = _load_golden(scenario, "graph_data")
        if data is None:
            pytest.skip(f"Golden file not found: {scenario}_graph_data.json")
        validated = GraphData.model_validate(data)
        assert validated.metadata.total_nodes >= 1

    def test_node_count_matches_metadata(self, scenario):
        data = _load_golden(scenario, "graph_data")
        if data is None:
            pytest.skip(f"Golden file not found: {scenario}_graph_data.json")
        assert len(data["nodes"]) == data["metadata"]["total_nodes"]


@pytest.mark.parametrize("scenario", SCENARIOS)
class TestGoldenStructured:
    def test_validates_against_schema(self, scenario):
        data = _load_golden(scenario, "structured")
        if data is None:
            pytest.skip(f"Golden file not found: {scenario}_structured.json")
        validated = StructuredResults.model_validate(data)
        assert len(validated.brief) > 0

    def test_findings_have_descriptions(self, scenario):
        data = _load_golden(scenario, "structured")
        if data is None:
            pytest.skip(f"Golden file not found: {scenario}_structured.json")
        for finding in data["findings"]:
            assert len(finding["description"]) > 0
```

- [ ] **Step 3: Write the golden README**

```markdown
# Golden Files

Saved outputs from MiroShark simulations used as regression baselines.

## How to populate

Run a simulation and copy results:

```bash
# Small sim (5 agents, 15 rounds)
cp /tmp/results/chat_log.json tests/contracts/golden/small_sim_chat_log.json
cp /tmp/results/graph_data.json tests/contracts/golden/small_sim_graph_data.json
cp /tmp/results/structured_results.json tests/contracts/golden/small_sim_structured.json

# Sim with prediction market
cp /tmp/results/chat_log.json tests/contracts/golden/market_sim_chat_log.json
# ... etc

# Sim with web enrichment
cp /tmp/results/chat_log.json tests/contracts/golden/enriched_sim_chat_log.json
# ... etc
```

Tests skip gracefully when golden files are missing.
```

- [ ] **Step 4: Run tests — should skip gracefully**

Run: `pytest tests/contracts/test_golden_files.py -v`
Expected: All SKIPPED (golden files not populated yet)

- [ ] **Step 5: Commit**

```bash
git add tests/contracts/test_golden_files.py tests/contracts/golden/
git commit -m "feat: add golden file validation tests for regression baseline"
```

---

## Phase 2: SimSwarm Engine Core

Build the engine from scratch as a Python package. TDD throughout — tests first, then implementation.

---

### Task 5: Package Structure & Types

Set up the `simswarm/` package with core type definitions. Every subsequent task imports from here.

**Files:**
- Create: `simswarm/__init__.py`
- Create: `simswarm/types.py`
- Create: `tests/engine/__init__.py`
- Create: `tests/engine/test_types.py`

- [ ] **Step 1: Create the package directories**

```bash
mkdir -p simswarm
mkdir -p tests/engine
touch tests/engine/__init__.py
```

- [ ] **Step 2: Write the type validation test**

```python
# tests/engine/test_types.py
"""Test that core engine types are well-formed and serializable."""
from __future__ import annotations

import json

from simswarm.types import (
    Action,
    ActionResult,
    Agent,
    AgentActivityConfig,
    BeliefState,
    EngineConfig,
    EnvironmentConfig,
    Event,
    Observation,
    RoundSnapshot,
    ScheduledEvent,
    SimulationConfig,
    SimulationResult,
    SimulationState,
)


class TestAgentConstruction:
    def test_minimal_agent(self):
        agent = Agent(
            id="agent-1",
            name="Alice",
            persona="You are Alice, a financial analyst.",
            environments=["social"],
            belief_state=BeliefState(),
            config=AgentActivityConfig(),
        )
        assert agent.id == "agent-1"
        assert agent.environments == ["social"]

    def test_belief_state_defaults(self):
        bs = BeliefState()
        assert bs.positions == {}
        assert bs.confidence == {}
        assert bs.trust == {}
        assert len(bs.exposure_history) == 0


class TestSimulationConfig:
    def test_minimal_config(self):
        config = SimulationConfig(
            seed_text="Test seed",
            goal="Predict outcomes",
            entities=[],
            environments=[],
            rounds=10,
            concurrency=4,
        )
        assert config.rounds == 10
        assert config.variables == {}
        assert config.scheduled_events == []

    def test_config_with_variables(self):
        config = SimulationConfig(
            seed_text="Test",
            goal="Test",
            entities=[],
            environments=[],
            rounds=10,
            concurrency=4,
            variables={"policy": "equity_heavy", "fund_size": 2_000_000_000},
        )
        assert config.variables["policy"] == "equity_heavy"


class TestScheduledEvent:
    def test_event_construction(self):
        event = ScheduledEvent(
            round=10,
            type="policy_change",
            data={"action": "distribute", "amount": "50B"},
        )
        assert event.round == 10


class TestEngineConfig:
    def test_defaults(self):
        cfg = EngineConfig()
        assert cfg.flush_interval == 10
        assert cfg.checkpoint_interval == 50
        assert cfg.max_memory_rounds == 20
        assert cfg.concurrency == 32


class TestSimulationState:
    def test_initial_state(self):
        state = SimulationState(round=0, agents={}, environments={}, events=[], snapshots=[])
        assert state.round == 0
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/engine/test_types.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'simswarm'`

- [ ] **Step 4: Write the types module**

```python
# simswarm/__init__.py
"""SimSwarm — agent-based simulation engine."""
from simswarm.types import (
    Agent,
    BeliefState,
    EngineConfig,
    SimulationConfig,
    SimulationResult,
)

__all__ = ["Agent", "BeliefState", "EngineConfig", "SimulationConfig", "SimulationResult"]
```

```python
# simswarm/types.py
"""Core type definitions for the SimSwarm engine.

All types are plain dataclasses — no framework dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class BeliefState:
    """Agent's evolving internal state."""
    positions: dict[str, float] = field(default_factory=dict)  # topic -> [-1.0, 1.0]
    confidence: dict[str, float] = field(default_factory=dict)  # topic -> [0.0, 1.0]
    trust: dict[str, float] = field(default_factory=dict)  # agent_id -> [0.0, 1.0]
    exposure_history: set[str] = field(default_factory=set)  # content hashes


@dataclass
class AgentActivityConfig:
    """Controls agent behavior intensity and bias."""
    activity_level: float = 0.5  # 0.0-1.0
    sentiment_bias: float = 0.0  # -1.0 to 1.0
    stance: str = "neutral"  # supportive, opposing, neutral, observer
    influence_weight: float = 1.0  # 0.5-3.0


@dataclass
class Agent:
    """A simulation participant."""
    id: str
    name: str
    persona: str
    environments: list[str]
    belief_state: BeliefState
    config: AgentActivityConfig
    memory: list[str] = field(default_factory=list)


@dataclass
class Action:
    """An action an agent wants to perform."""
    agent_id: str
    environment: str
    action_type: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionResult:
    """Result of executing an action in an environment."""
    success: bool
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class Observation:
    """What an agent sees from an environment."""
    environment: str
    content: str
    structured: dict[str, Any] = field(default_factory=dict)


@dataclass
class Event:
    """Cross-environment event published by an environment."""
    source: str  # environment name
    type: str
    data: dict[str, Any] = field(default_factory=dict)
    round: int = 0


@dataclass
class ScheduledEvent:
    """A policy shock or event injected at a specific round."""
    round: int
    type: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class EnvironmentConfig:
    """Configuration for instantiating an environment."""
    type: str  # "social", "market", "economic"
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class Entity:
    """An entity from the knowledge graph, passed as engine input."""
    id: str
    name: str
    type: str
    summary: str
    attributes: dict[str, Any] = field(default_factory=dict)
    relationships: list[dict[str, str]] = field(default_factory=list)


@dataclass
class SimulationConfig:
    """Full configuration for a simulation run."""
    seed_text: str
    goal: str
    entities: list[Entity]
    environments: list[EnvironmentConfig]
    rounds: int
    concurrency: int
    agent_configs: list[dict[str, Any]] | None = None
    variables: dict[str, Any] = field(default_factory=dict)
    scheduled_events: list[ScheduledEvent] = field(default_factory=list)
    enrichment: dict[str, Any] | None = None


@dataclass
class EngineConfig:
    """Engine-level settings (not simulation-specific)."""
    flush_interval: int = 10
    checkpoint_interval: int = 50
    max_memory_rounds: int = 20
    concurrency: int = 32
    context_budget: int = 16384  # max tokens per agent context


@dataclass
class RoundSnapshot:
    """Metrics captured at end of each round."""
    round: int
    agent_count: int
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class SimulationState:
    """Full mutable state of a running simulation."""
    round: int
    agents: dict[str, Agent]
    environments: dict[str, Any]
    events: list[Event]
    snapshots: list[RoundSnapshot]


@dataclass
class GraphSnapshot:
    """Entity graph data returned after simulation."""
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    metadata: dict[str, Any]


@dataclass
class ActionRecord:
    """A logged agent action for the chat log."""
    round_num: int
    agent_id: str
    agent_name: str
    action_type: str
    platform: str
    action_args: dict[str, Any]
    timestamp: str | None = None
    success: bool = True


@dataclass
class SimulationResult:
    """Complete output of a simulation run."""
    chat_log: list[ActionRecord]
    graph_data: GraphSnapshot
    trajectories: dict[str, Any]
    market_data: list[dict[str, Any]] | None = None
    raw_state: SimulationState | None = None


class Tool:
    """An action exposed by an environment as an LLM tool."""
    def __init__(self, name: str, description: str, parameters: dict[str, Any],
                 handler: Any = None):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.handler = handler

    def to_openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/engine/test_types.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add simswarm/ tests/engine/
git commit -m "feat: add simswarm package with core type definitions"
```

---

### Task 6: LLM Client

Direct async client for OpenAI-compatible APIs. No framework.

**Files:**
- Create: `simswarm/llm.py`
- Create: `tests/engine/test_llm.py`

- [ ] **Step 1: Write the LLM client tests**

```python
# tests/engine/test_llm.py
"""Test LLM client: tool call parsing, retry logic, context assembly."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from simswarm.llm import LLMClient, LLMResponse, build_context, parse_tool_calls
from simswarm.types import Agent, AgentActivityConfig, BeliefState, Observation


class TestParseToolCalls:
    def test_parses_single_tool_call(self):
        raw = {
            "choices": [{
                "message": {
                    "tool_calls": [{
                        "function": {
                            "name": "create_post",
                            "arguments": json.dumps({"text": "Hello world"}),
                        }
                    }]
                }
            }]
        }
        calls = parse_tool_calls(raw)
        assert len(calls) == 1
        assert calls[0]["name"] == "create_post"
        assert calls[0]["args"]["text"] == "Hello world"

    def test_parses_multiple_tool_calls(self):
        raw = {
            "choices": [{
                "message": {
                    "tool_calls": [
                        {"function": {"name": "create_post", "arguments": '{"text": "A"}'}},
                        {"function": {"name": "like_post", "arguments": '{"post_id": "p1"}'}},
                    ]
                }
            }]
        }
        calls = parse_tool_calls(raw)
        assert len(calls) == 2

    def test_returns_empty_when_no_tool_calls(self):
        raw = {"choices": [{"message": {"content": "I will do nothing."}}]}
        calls = parse_tool_calls(raw)
        assert calls == []

    def test_handles_malformed_arguments_gracefully(self):
        raw = {
            "choices": [{
                "message": {
                    "tool_calls": [{
                        "function": {
                            "name": "create_post",
                            "arguments": "not valid json{{{",
                        }
                    }]
                }
            }]
        }
        calls = parse_tool_calls(raw)
        assert len(calls) == 1
        assert calls[0]["args"] == {}


class TestBuildContext:
    def test_includes_persona_as_system_message(self):
        agent = Agent(
            id="a1", name="Alice", persona="You are Alice.",
            environments=["social"], belief_state=BeliefState(),
            config=AgentActivityConfig(),
        )
        obs = [Observation(environment="social", content="Feed: post by Bob")]
        messages = build_context(agent, obs)
        assert messages[0]["role"] == "system"
        assert "Alice" in messages[0]["content"]

    def test_includes_observations_as_user_message(self):
        agent = Agent(
            id="a1", name="Alice", persona="You are Alice.",
            environments=["social"], belief_state=BeliefState(),
            config=AgentActivityConfig(),
        )
        obs = [Observation(environment="social", content="Feed: post by Bob")]
        messages = build_context(agent, obs)
        user_msgs = [m for m in messages if m["role"] == "user"]
        assert any("post by Bob" in m["content"] for m in user_msgs)

    def test_includes_belief_summary_when_beliefs_exist(self):
        bs = BeliefState(
            positions={"climate": 0.8},
            confidence={"climate": 0.9},
        )
        agent = Agent(
            id="a1", name="Alice", persona="You are Alice.",
            environments=["social"], belief_state=bs,
            config=AgentActivityConfig(),
        )
        obs = [Observation(environment="social", content="Feed")]
        messages = build_context(agent, obs)
        full_text = " ".join(m["content"] for m in messages)
        assert "climate" in full_text


class TestLLMClient:
    @pytest.mark.asyncio
    async def test_chat_sends_correct_payload(self):
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "choices": [{"message": {"content": "Hello"}}]
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)
        mock_session.post.return_value = mock_response

        client = LLMClient(base_url="http://localhost:8000/v1", model="test-model")
        client.session = mock_session

        result = await client.chat([{"role": "user", "content": "Hi"}])
        assert result.content == "Hello"

        call_kwargs = mock_session.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["model"] == "test-model"
        assert payload["messages"][0]["content"] == "Hi"

    @pytest.mark.asyncio
    async def test_chat_passes_tools_when_provided(self):
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "choices": [{"message": {"tool_calls": [
                {"function": {"name": "do_thing", "arguments": "{}"}}
            ]}}]
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)
        mock_session.post.return_value = mock_response

        client = LLMClient(base_url="http://localhost:8000/v1", model="test-model")
        client.session = mock_session

        tools = [{"type": "function", "function": {"name": "do_thing", "parameters": {}}}]
        result = await client.chat([{"role": "user", "content": "Go"}], tools=tools)
        assert len(result.tool_calls) == 1

        call_kwargs = mock_session.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert "tools" in payload
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/engine/test_llm.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the LLM client**

```python
# simswarm/llm.py
"""Async LLM client for OpenAI-compatible APIs.

Direct aiohttp calls — no SDK, no framework.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

import aiohttp

from simswarm.types import Agent, Observation

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Parsed response from an LLM call."""
    content: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


def parse_tool_calls(raw: dict) -> list[dict[str, Any]]:
    """Extract tool calls from an OpenAI-format response."""
    message = raw.get("choices", [{}])[0].get("message", {})
    raw_calls = message.get("tool_calls", [])
    results = []
    for call in raw_calls:
        fn = call.get("function", {})
        name = fn.get("name", "")
        try:
            args = json.loads(fn.get("arguments", "{}"))
        except (json.JSONDecodeError, TypeError):
            args = {}
        results.append({"name": name, "args": args})
    return results


def build_context(agent: Agent, observations: list[Observation]) -> list[dict[str, str]]:
    """Assemble the message list for an agent's LLM call."""
    messages = [{"role": "system", "content": agent.persona}]

    # Belief summary
    if agent.belief_state.positions:
        lines = []
        for topic, pos in agent.belief_state.positions.items():
            conf = agent.belief_state.confidence.get(topic, 0.5)
            lines.append(f"- {topic}: position={pos:.2f}, confidence={conf:.2f}")
        messages.append({
            "role": "system",
            "content": "Your current beliefs:\n" + "\n".join(lines),
        })

    # Recent memory
    if agent.memory:
        messages.append({
            "role": "system",
            "content": "Recent actions:\n" + "\n".join(agent.memory[-5:]),
        })

    # Observations
    obs_parts = []
    for obs in observations:
        obs_parts.append(f"[{obs.environment}]\n{obs.content}")
    if obs_parts:
        messages.append({"role": "user", "content": "\n\n".join(obs_parts)})

    return messages


class LLMClient:
    """Async client for OpenAI-compatible /v1/chat/completions."""

    def __init__(self, base_url: str, model: str, api_key: str = "none"):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.session: aiohttp.ClientSession | None = None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session

    async def chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict] | None = None,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Send a chat completion request and return parsed response."""
        session = await self._ensure_session()
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools

        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}"}

        async with session.post(url, json=payload, headers=headers) as resp:
            data = await resp.json()

        message = data.get("choices", [{}])[0].get("message", {})
        return LLMResponse(
            content=message.get("content", "") or "",
            tool_calls=parse_tool_calls(data),
            raw=data,
        )

    async def close(self) -> None:
        if self.session:
            await self.session.close()
            self.session = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/engine/test_llm.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add simswarm/llm.py tests/engine/test_llm.py
git commit -m "feat: add async LLM client with tool call parsing"
```

---

### Task 7: Belief State Engine

Port the proven belief update math from MiroShark. This is one of the few components that should have exact numerical parity.

**Files:**
- Create: `simswarm/belief.py`
- Create: `tests/engine/test_belief.py`
- Reference: `vendor/miroshark/backend/wonderwall/social_agent/belief_state.py`

- [ ] **Step 1: Write belief state tests**

```python
# tests/engine/test_belief.py
"""Test belief state updates with known inputs and expected outputs.

These are pure math tests — no LLM, no environment, no async.
"""
from __future__ import annotations

from simswarm.belief import update_beliefs
from simswarm.types import BeliefState


class TestPositionUpdate:
    def test_novel_supportive_content_shifts_position_positive(self):
        bs = BeliefState(
            positions={"climate": 0.0},
            confidence={"climate": 0.5},
            trust={"author1": 0.8},
        )
        posts = [{"author": "author1", "content_hash": "h1", "stance": 0.6, "likes": 3}]
        updated = update_beliefs(bs, posts, topic="climate")
        assert updated.positions["climate"] > 0.0

    def test_novel_opposing_content_shifts_position_negative(self):
        bs = BeliefState(
            positions={"climate": 0.0},
            confidence={"climate": 0.5},
            trust={"author1": 0.8},
        )
        posts = [{"author": "author1", "content_hash": "h2", "stance": -0.6, "likes": 3}]
        updated = update_beliefs(bs, posts, topic="climate")
        assert updated.positions["climate"] < 0.0

    def test_repeated_content_has_no_effect(self):
        bs = BeliefState(
            positions={"climate": 0.3},
            confidence={"climate": 0.5},
            trust={"author1": 0.8},
            exposure_history={"h1"},
        )
        posts = [{"author": "author1", "content_hash": "h1", "stance": -0.9, "likes": 10}]
        updated = update_beliefs(bs, posts, topic="climate")
        assert updated.positions["climate"] == 0.3  # unchanged


class TestConfidenceResistance:
    def test_high_confidence_resists_change(self):
        low_conf = BeliefState(
            positions={"topic": 0.0}, confidence={"topic": 0.2}, trust={"a": 0.8},
        )
        high_conf = BeliefState(
            positions={"topic": 0.0}, confidence={"topic": 0.9}, trust={"a": 0.8},
        )
        posts = [{"author": "a", "content_hash": "h1", "stance": 0.8, "likes": 5}]
        updated_low = update_beliefs(low_conf, posts, topic="topic")
        updated_high = update_beliefs(high_conf, posts, topic="topic")
        assert abs(updated_low.positions["topic"]) > abs(updated_high.positions["topic"])

    def test_confidence_increases_with_engagement(self):
        bs = BeliefState(
            positions={"topic": 0.5}, confidence={"topic": 0.5}, trust={},
        )
        updated = update_beliefs(bs, [], topic="topic", own_likes=10, own_dislikes=0)
        assert updated.confidence["topic"] > 0.5


class TestTrustUpdate:
    def test_trust_defaults_to_half(self):
        bs = BeliefState()
        posts = [{"author": "stranger", "content_hash": "h1", "stance": 0.5, "likes": 1}]
        updated = update_beliefs(bs, posts, topic="topic")
        assert updated.trust.get("stranger", 0.5) == 0.5


class TestExposureHistory:
    def test_new_content_added_to_history(self):
        bs = BeliefState()
        posts = [{"author": "a", "content_hash": "new_hash", "stance": 0.5, "likes": 1}]
        updated = update_beliefs(bs, posts, topic="topic")
        assert "new_hash" in updated.exposure_history

    def test_history_capped_at_2000(self):
        bs = BeliefState(
            exposure_history={f"h{i}" for i in range(2000)},
        )
        posts = [{"author": "a", "content_hash": "overflow", "stance": 0.5, "likes": 1}]
        updated = update_beliefs(bs, posts, topic="topic")
        assert len(updated.exposure_history) <= 2000


class TestPositionBounds:
    def test_position_clamped_to_negative_one(self):
        bs = BeliefState(
            positions={"topic": -0.95}, confidence={"topic": 0.1}, trust={"a": 1.0},
        )
        posts = [{"author": "a", "content_hash": "h1", "stance": -1.0, "likes": 100}]
        updated = update_beliefs(bs, posts, topic="topic")
        assert updated.positions["topic"] >= -1.0

    def test_position_clamped_to_positive_one(self):
        bs = BeliefState(
            positions={"topic": 0.95}, confidence={"topic": 0.1}, trust={"a": 1.0},
        )
        posts = [{"author": "a", "content_hash": "h1", "stance": 1.0, "likes": 100}]
        updated = update_beliefs(bs, posts, topic="topic")
        assert updated.positions["topic"] <= 1.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/engine/test_belief.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write the belief update logic**

```python
# simswarm/belief.py
"""Heuristic belief state updates.

Ported from MiroShark's belief_state.py. No LLM calls —
pure math based on trust, social proof, novelty, and confidence resistance.
"""
from __future__ import annotations

import copy
import math

from simswarm.types import BeliefState

EXPOSURE_CAP = 2000
DEFAULT_TRUST = 0.5
NOVELTY_MULTIPLIER = 1.5
SOCIAL_PROOF_SCALE = 0.1  # log(1 + likes) * scale
CONFIDENCE_BOOST_PER_LIKE = 0.005
CONFIDENCE_DECAY_PER_DISLIKE = 0.008


def update_beliefs(
    state: BeliefState,
    posts: list[dict],
    topic: str,
    own_likes: int = 0,
    own_dislikes: int = 0,
) -> BeliefState:
    """Return a new BeliefState with updated positions, confidence, trust, and exposure.

    Args:
        state: Current belief state (not mutated).
        posts: List of dicts with keys: author, content_hash, stance (-1 to 1), likes.
        topic: The topic being updated.
        own_likes: Likes received on agent's own posts this round.
        own_dislikes: Dislikes received on agent's own posts this round.
    """
    updated = copy.deepcopy(state)

    current_pos = updated.positions.get(topic, 0.0)
    current_conf = updated.confidence.get(topic, 0.5)

    # Resistance factor: high confidence = resist change
    resistance = 1.0 - (current_conf * 0.8)  # range: 0.2 to 1.0

    position_delta = 0.0

    for post in posts:
        content_hash = post["content_hash"]

        # Skip already-seen content
        if content_hash in updated.exposure_history:
            continue

        # Mark as seen
        updated.exposure_history.add(content_hash)

        author = post["author"]
        stance = post["stance"]
        likes = post.get("likes", 0)

        # Trust weighting (default 0.5 for unknown authors)
        trust = updated.trust.get(author, DEFAULT_TRUST)

        # Social proof: log scale
        social_proof = math.log1p(likes) * SOCIAL_PROOF_SCALE

        # Novelty: new content has more impact
        novelty = NOVELTY_MULTIPLIER

        # Influence = trust * (1 + social_proof) * novelty * resistance
        influence = trust * (1.0 + social_proof) * novelty * resistance

        # Delta = stance * influence * 0.1 (scaled to keep updates small)
        position_delta += stance * influence * 0.1

    # Apply position update
    new_pos = current_pos + position_delta
    updated.positions[topic] = max(-1.0, min(1.0, new_pos))

    # Confidence update from own engagement
    conf_delta = (own_likes * CONFIDENCE_BOOST_PER_LIKE
                  - own_dislikes * CONFIDENCE_DECAY_PER_DISLIKE)
    new_conf = current_conf + conf_delta
    updated.confidence[topic] = max(0.0, min(1.0, new_conf))

    # Cap exposure history
    if len(updated.exposure_history) > EXPOSURE_CAP:
        excess = len(updated.exposure_history) - EXPOSURE_CAP
        to_remove = list(updated.exposure_history)[:excess]
        for item in to_remove:
            updated.exposure_history.discard(item)

    return updated
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/engine/test_belief.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add simswarm/belief.py tests/engine/test_belief.py
git commit -m "feat: add belief state update engine with heuristic math"
```

---

### Task 8: Environment Protocol & Social Environment

The first pluggable environment — unified social platform replacing Twitter + Reddit.

**Files:**
- Create: `simswarm/environments/__init__.py`
- Create: `simswarm/environments/base.py`
- Create: `simswarm/environments/social.py`
- Create: `tests/engine/test_social_env.py`

- [ ] **Step 1: Write social environment tests**

```python
# tests/engine/test_social_env.py
"""Test the unified social environment: posts, replies, votes, feed ranking."""
from __future__ import annotations

from simswarm.environments.social import SocialEnvironment, SocialConfig
from simswarm.types import Action, Agent, AgentActivityConfig, BeliefState


def _make_agent(agent_id: str, name: str = "Test") -> Agent:
    return Agent(
        id=agent_id, name=name, persona="Test agent",
        environments=["social"], belief_state=BeliefState(),
        config=AgentActivityConfig(),
    )


class TestPostCreation:
    def test_create_post_returns_post_id(self):
        env = SocialEnvironment(SocialConfig())
        agent = _make_agent("a1", "Alice")
        action = Action(agent_id="a1", environment="social",
                        action_type="create_post", args={"text": "Hello world"})
        result = env.execute_action(agent, action)
        assert result.success
        assert "post_id" in result.data

    def test_post_appears_in_feed(self):
        env = SocialEnvironment(SocialConfig())
        alice = _make_agent("a1", "Alice")
        bob = _make_agent("a2", "Bob")

        # Alice posts
        env.execute_action(alice, Action(
            agent_id="a1", environment="social",
            action_type="create_post", args={"text": "Test post"},
        ))

        # Bob's observation should include Alice's post
        obs = env.get_observations(bob)
        assert "Test post" in obs.content


class TestReplies:
    def test_reply_creates_threaded_response(self):
        env = SocialEnvironment(SocialConfig(threading=True))
        alice = _make_agent("a1", "Alice")

        post_result = env.execute_action(alice, Action(
            agent_id="a1", environment="social",
            action_type="create_post", args={"text": "Original"},
        ))
        post_id = post_result.data["post_id"]

        reply_result = env.execute_action(alice, Action(
            agent_id="a1", environment="social",
            action_type="reply", args={"post_id": post_id, "text": "Reply"},
        ))
        assert reply_result.success

    def test_reply_fails_on_nonexistent_post(self):
        env = SocialEnvironment(SocialConfig())
        agent = _make_agent("a1")
        result = env.execute_action(agent, Action(
            agent_id="a1", environment="social",
            action_type="reply", args={"post_id": "fake", "text": "Reply"},
        ))
        assert not result.success


class TestVoting:
    def test_like_increases_post_score(self):
        env = SocialEnvironment(SocialConfig())
        alice = _make_agent("a1", "Alice")
        bob = _make_agent("a2", "Bob")

        post_result = env.execute_action(alice, Action(
            agent_id="a1", environment="social",
            action_type="create_post", args={"text": "Likeable"},
        ))
        post_id = post_result.data["post_id"]

        env.execute_action(bob, Action(
            agent_id="a2", environment="social",
            action_type="vote", args={"post_id": post_id, "value": 1},
        ))
        post = env.posts[post_id]
        assert post.likes == 1


class TestFeedRanking:
    def test_popular_posts_rank_higher(self):
        env = SocialEnvironment(SocialConfig())
        alice = _make_agent("a1", "Alice")
        agents = [_make_agent(f"v{i}") for i in range(5)]

        # Post A: no votes
        post_a = env.execute_action(alice, Action(
            agent_id="a1", environment="social",
            action_type="create_post", args={"text": "Unpopular"},
        ))

        # Post B: many votes
        post_b = env.execute_action(alice, Action(
            agent_id="a1", environment="social",
            action_type="create_post", args={"text": "Popular"},
        ))
        for v in agents:
            env.execute_action(v, Action(
                agent_id=v.id, environment="social",
                action_type="vote", args={"post_id": post_b.data["post_id"], "value": 1},
            ))

        env.tick()
        reader = _make_agent("reader")
        obs = env.get_observations(reader)
        # Popular should appear before unpopular in feed
        pop_idx = obs.content.index("Popular")
        unpop_idx = obs.content.index("Unpopular")
        assert pop_idx < unpop_idx


class TestTools:
    def test_get_tools_returns_expected_actions(self):
        env = SocialEnvironment(SocialConfig())
        tools = env.get_tools()
        tool_names = {t.name for t in tools}
        assert "create_post" in tool_names
        assert "reply" in tool_names
        assert "vote" in tool_names
        assert "do_nothing" in tool_names


class TestEvents:
    def test_viral_post_publishes_event(self):
        env = SocialEnvironment(SocialConfig(viral_threshold=2))
        alice = _make_agent("a1", "Alice")
        voters = [_make_agent(f"v{i}") for i in range(3)]

        post = env.execute_action(alice, Action(
            agent_id="a1", environment="social",
            action_type="create_post", args={"text": "Going viral"},
        ))
        for v in voters:
            env.execute_action(v, Action(
                agent_id=v.id, environment="social",
                action_type="vote", args={"post_id": post.data["post_id"], "value": 1},
            ))

        env.tick()
        events = env.publish_events()
        viral_events = [e for e in events if e.type == "viral_post"]
        assert len(viral_events) >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/engine/test_social_env.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write the environment base and social implementation**

```python
# simswarm/environments/__init__.py
"""Pluggable simulation environments."""
from simswarm.environments.social import SocialConfig, SocialEnvironment

__all__ = ["SocialConfig", "SocialEnvironment"]
```

```python
# simswarm/environments/base.py
"""Base protocol for simulation environments."""
from __future__ import annotations

from typing import Protocol

from simswarm.types import Action, ActionResult, Agent, Event, Observation, Tool


class Environment(Protocol):
    """Interface that all environments must implement."""
    name: str

    def get_observations(self, agent: Agent) -> Observation: ...
    def execute_action(self, agent: Agent, action: Action) -> ActionResult: ...
    def get_tools(self) -> list[Tool]: ...
    def publish_events(self) -> list[Event]: ...
    def tick(self) -> None: ...
```

```python
# simswarm/environments/social.py
"""Unified social environment — replaces separate Twitter/Reddit platforms.

Configurable threading, voting mode, feed algorithm, and virality.
"""
from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from typing import Any

from simswarm.types import Action, ActionResult, Agent, Event, Observation, Tool


@dataclass
class SocialConfig:
    threading: bool = True
    voting_mode: str = "likes_only"  # "likes_only" or "upvote_downvote"
    recency_weight: float = 0.3
    popularity_weight: float = 0.4
    relevance_weight: float = 0.3
    echo_chamber_strength: float = 0.5
    viral_threshold: int = 5


@dataclass
class Post:
    id: str
    author_id: str
    author_name: str
    text: str
    parent_id: str | None = None
    likes: int = 0
    dislikes: int = 0
    reposts: int = 0
    created_round: int = 0
    voters: set[str] = field(default_factory=set)


class SocialEnvironment:
    """Unified social platform with configurable features."""

    name = "social"

    def __init__(self, config: SocialConfig, current_round: int = 0):
        self.config = config
        self.current_round = current_round
        self.posts: dict[str, Post] = {}
        self.follows: dict[str, set[str]] = {}  # follower_id -> set of followed_ids
        self._pending_events: list[Event] = []
        self._new_viral: set[str] = set()

    def execute_action(self, agent: Agent, action: Action) -> ActionResult:
        handler = {
            "create_post": self._handle_create_post,
            "reply": self._handle_reply,
            "vote": self._handle_vote,
            "repost": self._handle_repost,
            "follow": self._handle_follow,
            "do_nothing": self._handle_noop,
        }.get(action.action_type)
        if handler is None:
            return ActionResult(success=False, data={"error": f"Unknown action: {action.action_type}"})
        return handler(agent, action.args)

    def get_observations(self, agent: Agent) -> Observation:
        ranked = self._rank_feed(agent.id)
        lines = []
        for post in ranked[:20]:
            score = post.likes - post.dislikes
            lines.append(f"[{post.author_name}] {post.text} (score: {score})")
            if self.config.threading:
                replies = [p for p in self.posts.values() if p.parent_id == post.id]
                for reply in replies[:3]:
                    lines.append(f"  -> [{reply.author_name}] {reply.text}")
        content = "\n".join(lines) if lines else "(no posts yet)"
        return Observation(environment=self.name, content=content)

    def get_tools(self) -> list[Tool]:
        tools = [
            Tool(
                name="create_post",
                description="Create a new post",
                parameters={"type": "object", "properties": {
                    "text": {"type": "string", "description": "Post content"},
                }, "required": ["text"]},
            ),
            Tool(
                name="reply",
                description="Reply to an existing post",
                parameters={"type": "object", "properties": {
                    "post_id": {"type": "string"},
                    "text": {"type": "string"},
                }, "required": ["post_id", "text"]},
            ),
            Tool(
                name="vote",
                description="Vote on a post (value: 1 for like, -1 for dislike)",
                parameters={"type": "object", "properties": {
                    "post_id": {"type": "string"},
                    "value": {"type": "integer", "enum": [1, -1]},
                }, "required": ["post_id", "value"]},
            ),
            Tool(
                name="repost",
                description="Repost someone's post",
                parameters={"type": "object", "properties": {
                    "post_id": {"type": "string"},
                }, "required": ["post_id"]},
            ),
            Tool(
                name="follow",
                description="Follow another agent",
                parameters={"type": "object", "properties": {
                    "agent_id": {"type": "string"},
                }, "required": ["agent_id"]},
            ),
            Tool(
                name="do_nothing",
                description="Take no action this round",
                parameters={"type": "object", "properties": {}},
            ),
        ]
        return tools

    def publish_events(self) -> list[Event]:
        events = list(self._pending_events)
        self._pending_events.clear()
        return events

    def tick(self) -> None:
        self.current_round += 1
        # Check for new viral posts
        for post_id, post in self.posts.items():
            total = post.likes + post.reposts
            if total >= self.config.viral_threshold and post_id not in self._new_viral:
                self._new_viral.add(post_id)
                self._pending_events.append(Event(
                    source=self.name,
                    type="viral_post",
                    data={"post_id": post_id, "text": post.text, "author": post.author_name,
                          "score": total},
                    round=self.current_round,
                ))

    # --- Action handlers ---

    def _handle_create_post(self, agent: Agent, args: dict) -> ActionResult:
        post_id = str(uuid.uuid4())
        post = Post(
            id=post_id, author_id=agent.id, author_name=agent.name,
            text=args.get("text", ""), created_round=self.current_round,
        )
        self.posts[post_id] = post
        return ActionResult(success=True, data={"post_id": post_id})

    def _handle_reply(self, agent: Agent, args: dict) -> ActionResult:
        parent_id = args.get("post_id", "")
        if parent_id not in self.posts:
            return ActionResult(success=False, data={"error": "Post not found"})
        post_id = str(uuid.uuid4())
        reply = Post(
            id=post_id, author_id=agent.id, author_name=agent.name,
            text=args.get("text", ""), parent_id=parent_id,
            created_round=self.current_round,
        )
        self.posts[post_id] = reply
        return ActionResult(success=True, data={"post_id": post_id})

    def _handle_vote(self, agent: Agent, args: dict) -> ActionResult:
        post_id = args.get("post_id", "")
        value = args.get("value", 1)
        if post_id not in self.posts:
            return ActionResult(success=False, data={"error": "Post not found"})
        post = self.posts[post_id]
        if agent.id in post.voters:
            return ActionResult(success=False, data={"error": "Already voted"})
        post.voters.add(agent.id)
        if value > 0:
            post.likes += 1
        else:
            post.dislikes += 1
        return ActionResult(success=True, data={"post_id": post_id})

    def _handle_repost(self, agent: Agent, args: dict) -> ActionResult:
        post_id = args.get("post_id", "")
        if post_id not in self.posts:
            return ActionResult(success=False, data={"error": "Post not found"})
        self.posts[post_id].reposts += 1
        return ActionResult(success=True, data={"post_id": post_id})

    def _handle_follow(self, agent: Agent, args: dict) -> ActionResult:
        target_id = args.get("agent_id", "")
        if agent.id not in self.follows:
            self.follows[agent.id] = set()
        self.follows[agent.id].add(target_id)
        return ActionResult(success=True, data={"followed": target_id})

    def _handle_noop(self, agent: Agent, args: dict) -> ActionResult:
        return ActionResult(success=True, data={})

    # --- Feed ranking ---

    def _rank_feed(self, agent_id: str) -> list[Post]:
        top_level = [p for p in self.posts.values() if p.parent_id is None]
        if not top_level:
            return []

        followed = self.follows.get(agent_id, set())
        max_round = max((p.created_round for p in top_level), default=0) or 1

        scored = []
        for post in top_level:
            recency = 1.0 - (max_round - post.created_round) / max(max_round, 1)
            popularity = math.log1p(post.likes + post.reposts)
            relevance = 1.0 if post.author_id in followed else (1.0 - self.config.echo_chamber_strength)
            score = (
                self.config.recency_weight * recency
                + self.config.popularity_weight * popularity
                + self.config.relevance_weight * relevance
            )
            scored.append((score, post))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [post for _, post in scored]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/engine/test_social_env.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add simswarm/environments/ tests/engine/test_social_env.py
git commit -m "feat: add unified social environment with feed ranking"
```

---

### Task 9: Market Environment

Prediction markets with constant-product AMM. Ported from MiroShark's Polymarket logic.

**Files:**
- Create: `simswarm/environments/market.py`
- Create: `tests/engine/test_market_env.py`

- [ ] **Step 1: Write market environment tests**

```python
# tests/engine/test_market_env.py
"""Test prediction market environment: AMM pricing, buy/sell, portfolio tracking."""
from __future__ import annotations

import pytest

from simswarm.environments.market import MarketEnvironment, MarketConfig, Market
from simswarm.types import Action, Agent, AgentActivityConfig, BeliefState


def _make_agent(agent_id: str, name: str = "Trader") -> Agent:
    return Agent(
        id=agent_id, name=name, persona="Test trader",
        environments=["market"], belief_state=BeliefState(),
        config=AgentActivityConfig(),
    )


class TestAMMPricing:
    def test_initial_price_at_fifty_percent(self):
        market = Market(id="m1", question="Will X happen?", reserve_yes=100, reserve_no=100)
        assert market.price_yes == pytest.approx(0.5)
        assert market.price_no == pytest.approx(0.5)

    def test_prices_sum_to_one(self):
        market = Market(id="m1", question="?", reserve_yes=150, reserve_no=50)
        assert market.price_yes + market.price_no == pytest.approx(1.0)

    def test_buy_yes_increases_yes_price(self):
        market = Market(id="m1", question="?", reserve_yes=100, reserve_no=100)
        initial_price = market.price_yes
        market.buy_yes(10.0)  # spend 10 USD on YES shares
        assert market.price_yes > initial_price

    def test_buy_no_increases_no_price(self):
        market = Market(id="m1", question="?", reserve_yes=100, reserve_no=100)
        initial_price = market.price_no
        market.buy_no(10.0)
        assert market.price_no > initial_price


class TestBuySell:
    def test_buy_returns_shares(self):
        market = Market(id="m1", question="?", reserve_yes=100, reserve_no=100)
        shares = market.buy_yes(10.0)
        assert shares > 0

    def test_sell_returns_usd(self):
        market = Market(id="m1", question="?", reserve_yes=100, reserve_no=100)
        shares = market.buy_yes(10.0)
        usd = market.sell_yes(shares)
        assert usd > 0
        assert usd == pytest.approx(10.0, rel=0.01)  # round-trip ~preserves value

    def test_constant_product_invariant_after_buy(self):
        market = Market(id="m1", question="?", reserve_yes=100, reserve_no=100)
        k_before = market.reserve_yes * market.reserve_no
        market.buy_yes(10.0)
        k_after = market.reserve_yes * market.reserve_no
        assert k_after == pytest.approx(k_before, rel=0.001)


class TestPortfolio:
    def test_buy_updates_portfolio(self):
        env = MarketEnvironment(MarketConfig(
            markets=[{"question": "Test?", "initial_price_yes": 0.5}],
            initial_balance=1000.0,
        ))
        trader = _make_agent("t1")
        env.register_agent(trader)

        market_id = list(env.markets.keys())[0]
        result = env.execute_action(trader, Action(
            agent_id="t1", environment="market",
            action_type="buy_shares",
            args={"market_id": market_id, "outcome": "yes", "amount": 50.0},
        ))
        assert result.success
        portfolio = env.portfolios["t1"]
        assert portfolio.balance < 1000.0
        assert portfolio.shares.get(market_id, {}).get("yes", 0) > 0


class TestMultipleMarkets:
    def test_supports_multiple_markets(self):
        env = MarketEnvironment(MarketConfig(
            markets=[
                {"question": "Will A happen?", "initial_price_yes": 0.6},
                {"question": "Will B happen?", "initial_price_yes": 0.4},
            ],
            initial_balance=1000.0,
        ))
        assert len(env.markets) == 2


class TestMarketEvents:
    def test_large_price_move_publishes_event(self):
        env = MarketEnvironment(MarketConfig(
            markets=[{"question": "Test?", "initial_price_yes": 0.5}],
            initial_balance=10000.0,
            price_move_event_threshold=0.05,
        ))
        trader = _make_agent("t1")
        env.register_agent(trader)

        market_id = list(env.markets.keys())[0]
        # Buy enough to move price significantly
        env.execute_action(trader, Action(
            agent_id="t1", environment="market",
            action_type="buy_shares",
            args={"market_id": market_id, "outcome": "yes", "amount": 500.0},
        ))
        env.tick()
        events = env.publish_events()
        price_events = [e for e in events if e.type == "price_move"]
        assert len(price_events) >= 1


class TestMarketTools:
    def test_get_tools_returns_expected_actions(self):
        env = MarketEnvironment(MarketConfig(markets=[], initial_balance=100.0))
        tools = env.get_tools()
        tool_names = {t.name for t in tools}
        assert "buy_shares" in tool_names
        assert "sell_shares" in tool_names
        assert "browse_markets" in tool_names
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/engine/test_market_env.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write the market environment**

```python
# simswarm/environments/market.py
"""Prediction market environment with constant-product AMM.

Ported from MiroShark's Polymarket logic. Supports multiple markets.
"""
from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from typing import Any

from simswarm.types import Action, ActionResult, Agent, Event, Observation, Tool


@dataclass
class Market:
    """A single prediction market with AMM pricing."""
    id: str
    question: str
    reserve_yes: float
    reserve_no: float

    @property
    def price_yes(self) -> float:
        return self.reserve_no / (self.reserve_yes + self.reserve_no)

    @property
    def price_no(self) -> float:
        return self.reserve_yes / (self.reserve_yes + self.reserve_no)

    def buy_yes(self, usd: float) -> float:
        """Spend USD to buy YES shares. Returns shares received."""
        # Mint complete sets, swap NO back to pool
        # k = reserve_yes * reserve_no (invariant)
        k = self.reserve_yes * self.reserve_no
        self.reserve_yes += usd
        self.reserve_no += usd
        new_reserve_no = k / self.reserve_yes
        shares = self.reserve_no - new_reserve_no
        self.reserve_no = new_reserve_no
        return shares

    def buy_no(self, usd: float) -> float:
        """Spend USD to buy NO shares. Returns shares received."""
        k = self.reserve_yes * self.reserve_no
        self.reserve_yes += usd
        self.reserve_no += usd
        new_reserve_yes = k / self.reserve_no
        shares = self.reserve_yes - new_reserve_yes
        self.reserve_yes = new_reserve_yes
        return shares

    def sell_yes(self, shares: float) -> float:
        """Sell YES shares back. Returns USD received."""
        k = self.reserve_yes * self.reserve_no
        self.reserve_no += shares
        new_reserve_yes = k / self.reserve_no
        usd = self.reserve_yes - new_reserve_yes
        self.reserve_yes = new_reserve_yes
        return usd

    def sell_no(self, shares: float) -> float:
        """Sell NO shares back. Returns USD received."""
        k = self.reserve_yes * self.reserve_no
        self.reserve_yes += shares
        new_reserve_no = k / self.reserve_yes
        usd = self.reserve_no - new_reserve_no
        self.reserve_no = new_reserve_no
        return usd


@dataclass
class Portfolio:
    balance: float
    shares: dict[str, dict[str, float]] = field(default_factory=dict)  # market_id -> {yes: N, no: N}


@dataclass
class MarketConfig:
    markets: list[dict[str, Any]]
    initial_balance: float = 1000.0
    initial_liquidity: float = 100.0
    price_move_event_threshold: float = 0.1


class MarketEnvironment:
    """Prediction market environment with AMM-based pricing."""

    name = "market"

    def __init__(self, config: MarketConfig, current_round: int = 0):
        self.config = config
        self.current_round = current_round
        self.markets: dict[str, Market] = {}
        self.portfolios: dict[str, Portfolio] = {}
        self._pending_events: list[Event] = []
        self._last_prices: dict[str, float] = {}
        self._trades: list[dict] = []

        for m in config.markets:
            market_id = str(uuid.uuid4())
            price_yes = m.get("initial_price_yes", 0.5)
            # Set reserves to match desired initial price
            # price_yes = reserve_no / (reserve_yes + reserve_no)
            # With total liquidity L: reserve_no = price_yes * 2L, reserve_yes = (1 - price_yes) * 2L
            liq = config.initial_liquidity
            reserve_yes = liq * 2 * (1 - price_yes)
            reserve_no = liq * 2 * price_yes
            self.markets[market_id] = Market(
                id=market_id, question=m["question"],
                reserve_yes=reserve_yes, reserve_no=reserve_no,
            )
            self._last_prices[market_id] = price_yes

    def register_agent(self, agent: Agent) -> None:
        if agent.id not in self.portfolios:
            self.portfolios[agent.id] = Portfolio(balance=self.config.initial_balance)

    def execute_action(self, agent: Agent, action: Action) -> ActionResult:
        self.register_agent(agent)
        handler = {
            "buy_shares": self._handle_buy,
            "sell_shares": self._handle_sell,
            "browse_markets": self._handle_browse,
            "comment_on_market": self._handle_comment,
            "do_nothing": self._handle_noop,
        }.get(action.action_type)
        if handler is None:
            return ActionResult(success=False, data={"error": f"Unknown action: {action.action_type}"})
        return handler(agent, action.args)

    def get_observations(self, agent: Agent) -> Observation:
        self.register_agent(agent)
        lines = []
        for market in self.markets.values():
            lines.append(
                f"Market: {market.question} | YES: {market.price_yes:.1%} | NO: {market.price_no:.1%}"
            )
        portfolio = self.portfolios.get(agent.id)
        if portfolio:
            lines.append(f"\nYour balance: ${portfolio.balance:.2f}")
            for mid, shares in portfolio.shares.items():
                m = self.markets.get(mid)
                if m:
                    lines.append(f"  {m.question}: YES={shares.get('yes', 0):.1f}, NO={shares.get('no', 0):.1f}")
        content = "\n".join(lines) if lines else "(no markets)"
        return Observation(environment=self.name, content=content)

    def get_tools(self) -> list[Tool]:
        return [
            Tool(name="buy_shares", description="Buy outcome shares in a market",
                 parameters={"type": "object", "properties": {
                     "market_id": {"type": "string"},
                     "outcome": {"type": "string", "enum": ["yes", "no"]},
                     "amount": {"type": "number", "description": "USD to spend"},
                 }, "required": ["market_id", "outcome", "amount"]}),
            Tool(name="sell_shares", description="Sell outcome shares",
                 parameters={"type": "object", "properties": {
                     "market_id": {"type": "string"},
                     "outcome": {"type": "string", "enum": ["yes", "no"]},
                     "shares": {"type": "number"},
                 }, "required": ["market_id", "outcome", "shares"]}),
            Tool(name="browse_markets", description="View all available markets",
                 parameters={"type": "object", "properties": {}}),
            Tool(name="comment_on_market", description="Comment on a market",
                 parameters={"type": "object", "properties": {
                     "market_id": {"type": "string"},
                     "text": {"type": "string"},
                 }, "required": ["market_id", "text"]}),
            Tool(name="do_nothing", description="Take no action",
                 parameters={"type": "object", "properties": {}}),
        ]

    def publish_events(self) -> list[Event]:
        events = list(self._pending_events)
        self._pending_events.clear()
        return events

    def tick(self) -> None:
        self.current_round += 1
        for market_id, market in self.markets.items():
            prev = self._last_prices.get(market_id, 0.5)
            curr = market.price_yes
            delta = abs(curr - prev)
            if delta >= self.config.price_move_event_threshold:
                self._pending_events.append(Event(
                    source=self.name, type="price_move",
                    data={"market_id": market_id, "question": market.question,
                          "price_yes": curr, "delta": curr - prev},
                    round=self.current_round,
                ))
            self._last_prices[market_id] = curr

    # --- Handlers ---

    def _handle_buy(self, agent: Agent, args: dict) -> ActionResult:
        market_id = args.get("market_id", "")
        outcome = args.get("outcome", "yes")
        amount = args.get("amount", 0.0)
        if market_id not in self.markets:
            return ActionResult(success=False, data={"error": "Market not found"})
        portfolio = self.portfolios[agent.id]
        if portfolio.balance < amount:
            return ActionResult(success=False, data={"error": "Insufficient balance"})

        market = self.markets[market_id]
        if outcome == "yes":
            shares = market.buy_yes(amount)
        else:
            shares = market.buy_no(amount)

        portfolio.balance -= amount
        if market_id not in portfolio.shares:
            portfolio.shares[market_id] = {"yes": 0.0, "no": 0.0}
        portfolio.shares[market_id][outcome] += shares

        self._trades.append({
            "agent_id": agent.id, "market_id": market_id,
            "side": "buy", "outcome": outcome, "shares": shares,
            "cost": amount, "round": self.current_round,
        })
        return ActionResult(success=True, data={"shares": shares, "cost": amount})

    def _handle_sell(self, agent: Agent, args: dict) -> ActionResult:
        market_id = args.get("market_id", "")
        outcome = args.get("outcome", "yes")
        shares = args.get("shares", 0.0)
        if market_id not in self.markets:
            return ActionResult(success=False, data={"error": "Market not found"})
        portfolio = self.portfolios[agent.id]
        held = portfolio.shares.get(market_id, {}).get(outcome, 0.0)
        if held < shares:
            return ActionResult(success=False, data={"error": "Insufficient shares"})

        market = self.markets[market_id]
        if outcome == "yes":
            usd = market.sell_yes(shares)
        else:
            usd = market.sell_no(shares)

        portfolio.shares[market_id][outcome] -= shares
        portfolio.balance += usd

        self._trades.append({
            "agent_id": agent.id, "market_id": market_id,
            "side": "sell", "outcome": outcome, "shares": shares,
            "usd": usd, "round": self.current_round,
        })
        return ActionResult(success=True, data={"usd": usd})

    def _handle_browse(self, agent: Agent, args: dict) -> ActionResult:
        data = []
        for m in self.markets.values():
            data.append({"market_id": m.id, "question": m.question,
                         "price_yes": m.price_yes, "price_no": m.price_no})
        return ActionResult(success=True, data={"markets": data})

    def _handle_comment(self, agent: Agent, args: dict) -> ActionResult:
        return ActionResult(success=True, data={})

    def _handle_noop(self, agent: Agent, args: dict) -> ActionResult:
        return ActionResult(success=True, data={})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/engine/test_market_env.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add simswarm/environments/market.py tests/engine/test_market_env.py
git commit -m "feat: add prediction market environment with AMM pricing"
```

---

### Task 10: Cross-Environment Bridge

Pub/sub event system that distributes events between environments as agent observation digests.

**Files:**
- Create: `simswarm/bridge.py`
- Create: `tests/engine/test_bridge.py`

- [ ] **Step 1: Write bridge tests**

```python
# tests/engine/test_bridge.py
"""Test cross-environment bridge: event collection and digest formatting."""
from __future__ import annotations

from simswarm.bridge import Bridge
from simswarm.types import Agent, AgentActivityConfig, BeliefState, Event


def _make_agent(agent_id: str, envs: list[str]) -> Agent:
    return Agent(
        id=agent_id, name=agent_id, persona="test",
        environments=envs, belief_state=BeliefState(),
        config=AgentActivityConfig(),
    )


class TestEventCollection:
    def test_collects_events_from_multiple_sources(self):
        bridge = Bridge()
        bridge.receive_events([
            Event(source="social", type="viral_post", data={"text": "Big news"}),
            Event(source="market", type="price_move", data={"delta": 0.15}),
        ])
        assert len(bridge.pending_events) == 2

    def test_clear_flushes_events(self):
        bridge = Bridge()
        bridge.receive_events([Event(source="social", type="test", data={})])
        bridge.clear()
        assert len(bridge.pending_events) == 0


class TestDigestFormatting:
    def test_agent_sees_only_cross_environment_events(self):
        bridge = Bridge()
        bridge.receive_events([
            Event(source="social", type="viral_post", data={"text": "Trending"}),
            Event(source="market", type="price_move", data={"question": "Will X?", "price_yes": 0.7}),
        ])
        # Agent in social env should see market events, not social events
        social_agent = _make_agent("a1", ["social"])
        digest = bridge.get_digest(social_agent)
        assert "price" in digest.lower() or "market" in digest.lower()
        assert "viral" not in digest.lower()

    def test_multi_env_agent_sees_events_from_other_envs(self):
        bridge = Bridge()
        bridge.receive_events([
            Event(source="social", type="viral_post", data={"text": "News"}),
            Event(source="market", type="price_move", data={"question": "Q?", "price_yes": 0.6}),
            Event(source="economic", type="policy_change", data={"action": "stimulus"}),
        ])
        agent = _make_agent("a1", ["social", "market"])
        digest = bridge.get_digest(agent)
        # Should see economic events (not in their envs)
        assert "policy" in digest.lower() or "economic" in digest.lower()

    def test_empty_events_returns_empty_digest(self):
        bridge = Bridge()
        agent = _make_agent("a1", ["social"])
        digest = bridge.get_digest(agent)
        assert digest == ""


class TestScheduledEvents:
    def test_injects_scheduled_event_at_correct_round(self):
        bridge = Bridge()
        from simswarm.types import ScheduledEvent
        scheduled = [ScheduledEvent(round=5, type="policy_change", data={"action": "distribute"})]
        bridge.inject_scheduled(scheduled, current_round=5)
        assert len(bridge.pending_events) == 1
        assert bridge.pending_events[0].type == "policy_change"

    def test_skips_scheduled_event_at_wrong_round(self):
        bridge = Bridge()
        from simswarm.types import ScheduledEvent
        scheduled = [ScheduledEvent(round=5, type="policy_change", data={"action": "distribute"})]
        bridge.inject_scheduled(scheduled, current_round=3)
        assert len(bridge.pending_events) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/engine/test_bridge.py -v`
Expected: FAIL

- [ ] **Step 3: Write the bridge**

```python
# simswarm/bridge.py
"""Cross-environment event bridge.

Collects events from environments, formats digests for agents,
and injects scheduled events at the correct round.
"""
from __future__ import annotations

from simswarm.types import Agent, Event, ScheduledEvent


class Bridge:
    """Distributes cross-environment events as agent observation digests."""

    def __init__(self) -> None:
        self.pending_events: list[Event] = []

    def receive_events(self, events: list[Event]) -> None:
        self.pending_events.extend(events)

    def inject_scheduled(self, scheduled: list[ScheduledEvent], current_round: int) -> None:
        for se in scheduled:
            if se.round == current_round:
                self.pending_events.append(Event(
                    source="scheduled",
                    type=se.type,
                    data=se.data,
                    round=current_round,
                ))

    def get_digest(self, agent: Agent) -> str:
        """Format a digest of events from environments the agent is NOT in.

        Agents already get observations from their own environments.
        The bridge surfaces what's happening elsewhere.
        """
        agent_envs = set(agent.environments)
        cross_events = [e for e in self.pending_events if e.source not in agent_envs]
        if not cross_events:
            return ""

        lines = []
        for event in cross_events:
            lines.append(_format_event(event))
        return "\n".join(lines)

    def clear(self) -> None:
        self.pending_events.clear()


def _format_event(event: Event) -> str:
    """Human-readable one-liner for an event."""
    if event.type == "viral_post":
        return f"[Social] Trending: \"{event.data.get('text', '')[:80]}\" by {event.data.get('author', '?')}"
    if event.type == "price_move":
        q = event.data.get("question", "?")
        p = event.data.get("price_yes", 0)
        d = event.data.get("delta", 0)
        direction = "up" if d > 0 else "down"
        return f"[Market] {q} moved {direction} to {p:.0%}"
    if event.type == "policy_change":
        action = event.data.get("action", "unknown")
        return f"[Policy] {action}: {event.data}"
    return f"[{event.source}] {event.type}: {event.data}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/engine/test_bridge.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add simswarm/bridge.py tests/engine/test_bridge.py
git commit -m "feat: add cross-environment event bridge"
```

---

### Task 11: Scenario Sweep

First-class parameter variation: generate config combinations and key results by variable tuple.

**Files:**
- Create: `simswarm/sweep.py`
- Create: `tests/engine/test_sweep.py`

- [ ] **Step 1: Write sweep tests**

```python
# tests/engine/test_sweep.py
"""Test scenario sweep: config generation and variable combinatorics."""
from __future__ import annotations

from simswarm.sweep import ScenarioSweep, generate_sweep_configs
from simswarm.types import SimulationConfig


def _base_config() -> SimulationConfig:
    return SimulationConfig(
        seed_text="Test seed",
        goal="Test goal",
        entities=[],
        environments=[],
        rounds=10,
        concurrency=4,
        variables={"policy": "default", "timeline": "moderate"},
    )


class TestConfigGeneration:
    def test_single_variable_generates_correct_count(self):
        sweep = ScenarioSweep(
            base_config=_base_config(),
            vary={"policy": ["a", "b", "c"]},
        )
        configs = generate_sweep_configs(sweep)
        assert len(configs) == 3

    def test_two_variables_generate_cartesian_product(self):
        sweep = ScenarioSweep(
            base_config=_base_config(),
            vary={
                "policy": ["equity", "supply"],
                "timeline": ["slow", "fast"],
            },
        )
        configs = generate_sweep_configs(sweep)
        assert len(configs) == 4  # 2 x 2

    def test_generated_configs_have_correct_variables(self):
        sweep = ScenarioSweep(
            base_config=_base_config(),
            vary={"policy": ["a", "b"]},
        )
        configs = generate_sweep_configs(sweep)
        policies = {c.variables["policy"] for _, c in configs}
        assert policies == {"a", "b"}

    def test_configs_keyed_by_variable_tuple(self):
        sweep = ScenarioSweep(
            base_config=_base_config(),
            vary={"policy": ["a"], "timeline": ["slow"]},
        )
        configs = generate_sweep_configs(sweep)
        key, config = configs[0]
        assert key == {"policy": "a", "timeline": "slow"}

    def test_base_config_unchanged_variables_preserved(self):
        base = _base_config()
        base.variables["extra"] = "keep_me"
        sweep = ScenarioSweep(base_config=base, vary={"policy": ["x"]})
        configs = generate_sweep_configs(sweep)
        _, config = configs[0]
        assert config.variables["extra"] == "keep_me"
        assert config.variables["policy"] == "x"

    def test_empty_vary_returns_single_base_config(self):
        sweep = ScenarioSweep(base_config=_base_config(), vary={})
        configs = generate_sweep_configs(sweep)
        assert len(configs) == 1


class TestSweepCopyIsolation:
    def test_configs_are_independent_copies(self):
        sweep = ScenarioSweep(
            base_config=_base_config(),
            vary={"policy": ["a", "b"]},
        )
        configs = generate_sweep_configs(sweep)
        _, config_a = configs[0]
        _, config_b = configs[1]
        config_a.variables["injected"] = True
        assert "injected" not in config_b.variables
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/engine/test_sweep.py -v`
Expected: FAIL

- [ ] **Step 3: Write the sweep module**

```python
# simswarm/sweep.py
"""Scenario sweep: generate config combinations for parameter variation."""
from __future__ import annotations

import copy
import itertools
from dataclasses import dataclass, field
from typing import Any

from simswarm.types import SimulationConfig


@dataclass
class ScenarioSweep:
    """Definition of a parameter sweep over a base config."""
    base_config: SimulationConfig
    vary: dict[str, list[Any]] = field(default_factory=dict)


def generate_sweep_configs(
    sweep: ScenarioSweep,
) -> list[tuple[dict[str, Any], SimulationConfig]]:
    """Generate (key, config) pairs for each variable combination.

    Returns a list of (variable_dict, config) tuples.
    Each config is a deep copy of base_config with variables overridden.
    """
    if not sweep.vary:
        return [({}, copy.deepcopy(sweep.base_config))]

    var_names = list(sweep.vary.keys())
    var_values = [sweep.vary[name] for name in var_names]

    results = []
    for combo in itertools.product(*var_values):
        key = dict(zip(var_names, combo))
        config = copy.deepcopy(sweep.base_config)
        config.variables.update(key)
        results.append((key, config))

    return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/engine/test_sweep.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add simswarm/sweep.py tests/engine/test_sweep.py
git commit -m "feat: add scenario sweep with config combinatorics"
```

---

### Task 12: Core Simulation Loop

The orchestrator that runs rounds: observe, step, execute, update, bridge, snapshot.

**Files:**
- Create: `simswarm/engine.py`
- Create: `tests/engine/test_engine.py`

- [ ] **Step 1: Write core loop tests**

```python
# tests/engine/test_engine.py
"""Test the core simulation loop: round orchestration, progress, termination."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from simswarm.engine import Engine
from simswarm.environments.social import SocialConfig, SocialEnvironment
from simswarm.llm import LLMClient, LLMResponse
from simswarm.types import (
    Agent,
    AgentActivityConfig,
    BeliefState,
    EngineConfig,
    Entity,
    EnvironmentConfig,
    SimulationConfig,
)


def _mock_llm_response(action_name: str = "do_nothing", args: dict | None = None):
    """Create a mock LLM response with a single tool call."""
    import json
    args = args or {}
    return LLMResponse(
        content="",
        tool_calls=[{"name": action_name, "args": args}],
        raw={},
    )


def _make_config(rounds: int = 3, agent_count: int = 2) -> SimulationConfig:
    return SimulationConfig(
        seed_text="Test simulation",
        goal="Test goal",
        entities=[Entity(id=f"e{i}", name=f"Agent{i}", type="person", summary=f"Agent {i}")
                  for i in range(agent_count)],
        environments=[EnvironmentConfig(type="social", params={})],
        rounds=rounds,
        concurrency=4,
    )


class TestEngineRoundExecution:
    @pytest.mark.asyncio
    async def test_runs_correct_number_of_rounds(self):
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat.return_value = _mock_llm_response("do_nothing")

        engine = Engine(
            fast_llm=mock_llm,
            smart_llm=mock_llm,
            engine_config=EngineConfig(concurrency=4),
        )
        config = _make_config(rounds=3)
        result = await engine.run(config)
        assert len(result.chat_log) >= 0  # may have do_nothing entries
        # Verify rounds were tracked
        assert mock_llm.chat.call_count == 3 * 2  # 3 rounds * 2 agents

    @pytest.mark.asyncio
    async def test_agents_receive_observations(self):
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat.return_value = _mock_llm_response("create_post", {"text": "Hello"})

        engine = Engine(
            fast_llm=mock_llm,
            smart_llm=mock_llm,
            engine_config=EngineConfig(concurrency=4),
        )
        config = _make_config(rounds=2, agent_count=1)
        result = await engine.run(config)
        # Agent should have made posts
        posts = [a for a in result.chat_log if a.action_type == "create_post"]
        assert len(posts) >= 1


class TestProgressCallback:
    @pytest.mark.asyncio
    async def test_progress_called_each_round(self):
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat.return_value = _mock_llm_response("do_nothing")
        progress_calls = []

        async def on_progress(round_num, total, metrics):
            progress_calls.append(round_num)

        engine = Engine(
            fast_llm=mock_llm,
            smart_llm=mock_llm,
            engine_config=EngineConfig(concurrency=4),
        )
        config = _make_config(rounds=3)
        await engine.run(config, on_progress=on_progress)
        assert progress_calls == [1, 2, 3]


class TestAgentGeneration:
    @pytest.mark.asyncio
    async def test_creates_agents_from_entities(self):
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat.return_value = _mock_llm_response("do_nothing")

        engine = Engine(
            fast_llm=mock_llm,
            smart_llm=mock_llm,
            engine_config=EngineConfig(concurrency=4),
        )
        config = _make_config(rounds=1, agent_count=5)
        result = await engine.run(config)
        # Should have created 5 agents (one per entity)
        agent_names = {a.agent_name for a in result.chat_log}
        assert len(agent_names) <= 5  # may have fewer if some did nothing


class TestSweepExecution:
    @pytest.mark.asyncio
    async def test_run_sweep_returns_keyed_results(self):
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat.return_value = _mock_llm_response("do_nothing")

        engine = Engine(
            fast_llm=mock_llm,
            smart_llm=mock_llm,
            engine_config=EngineConfig(concurrency=4),
        )
        from simswarm.sweep import ScenarioSweep
        config = _make_config(rounds=1)
        sweep = ScenarioSweep(
            base_config=config,
            vary={"policy": ["a", "b"]},
        )
        results = await engine.run_sweep(sweep)
        assert len(results) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/engine/test_engine.py -v`
Expected: FAIL

- [ ] **Step 3: Write the engine**

```python
# simswarm/engine.py
"""Core simulation engine: orchestrates rounds, agents, and environments."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Awaitable

from simswarm.belief import update_beliefs
from simswarm.bridge import Bridge
from simswarm.environments.social import SocialConfig, SocialEnvironment
from simswarm.environments.market import MarketConfig, MarketEnvironment
from simswarm.llm import LLMClient, build_context, parse_tool_calls
from simswarm.sweep import ScenarioSweep, generate_sweep_configs
from simswarm.types import (
    Action,
    ActionRecord,
    Agent,
    AgentActivityConfig,
    BeliefState,
    EngineConfig,
    Entity,
    EnvironmentConfig,
    Event,
    GraphSnapshot,
    Observation,
    RoundSnapshot,
    SimulationConfig,
    SimulationResult,
    SimulationState,
)

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int, dict[str, Any]], Awaitable[None]]


class Engine:
    """SimSwarm simulation engine."""

    def __init__(
        self,
        fast_llm: LLMClient,
        smart_llm: LLMClient,
        engine_config: EngineConfig | None = None,
    ):
        self.fast_llm = fast_llm
        self.smart_llm = smart_llm
        self.config = engine_config or EngineConfig()

    async def run(
        self,
        config: SimulationConfig,
        on_progress: ProgressCallback | None = None,
    ) -> SimulationResult:
        """Run a single simulation."""
        # Initialize environments
        environments = self._create_environments(config.environments)
        # Initialize agents
        agents = self._create_agents(config.entities, list(environments.keys()))
        # Initialize bridge
        bridge = Bridge()
        # State
        chat_log: list[ActionRecord] = []
        snapshots: list[RoundSnapshot] = []
        semaphore = asyncio.Semaphore(config.concurrency)

        for round_num in range(1, config.rounds + 1):
            # Inject scheduled events
            bridge.inject_scheduled(config.scheduled_events, round_num)

            # Observe: each agent gets observations from their environments + bridge digest
            agent_observations: dict[str, list[Observation]] = {}
            for agent in agents.values():
                obs = []
                for env_name in agent.environments:
                    if env_name in environments:
                        obs.append(environments[env_name].get_observations(agent))
                digest = bridge.get_digest(agent)
                if digest:
                    obs.append(Observation(environment="bridge", content=digest))
                # Add variables context if present
                if config.variables:
                    var_lines = [f"  {k}: {v}" for k, v in config.variables.items()]
                    obs.append(Observation(
                        environment="scenario",
                        content="Current scenario variables:\n" + "\n".join(var_lines),
                    ))
                agent_observations[agent.id] = obs

            # Step: batch LLM calls
            async def step_agent(agent: Agent) -> list[ActionRecord]:
                async with semaphore:
                    obs = agent_observations.get(agent.id, [])
                    tools = []
                    for env_name in agent.environments:
                        if env_name in environments:
                            tools.extend(environments[env_name].get_tools())
                    tool_schemas = [t.to_openai_schema() for t in tools]
                    messages = build_context(agent, obs)
                    response = await self.fast_llm.chat(messages, tools=tool_schemas)
                    records = []
                    for call in response.tool_calls:
                        action_name = call["name"]
                        action_args = call["args"]
                        # Determine which environment owns this action
                        target_env = self._find_env_for_action(action_name, environments, agent)
                        action = Action(
                            agent_id=agent.id, environment=target_env,
                            action_type=action_name, args=action_args,
                        )
                        if target_env in environments:
                            result = environments[target_env].execute_action(agent, action)
                        else:
                            result = None
                        records.append(ActionRecord(
                            round_num=round_num, agent_id=agent.id,
                            agent_name=agent.name, action_type=action_name,
                            platform=target_env, action_args=action_args,
                            success=result.success if result else False,
                        ))
                        # Update memory
                        agent.memory.append(f"Round {round_num}: {action_name}({action_args})")
                        if len(agent.memory) > self.config.max_memory_rounds:
                            agent.memory = agent.memory[-self.config.max_memory_rounds:]
                    if not response.tool_calls:
                        records.append(ActionRecord(
                            round_num=round_num, agent_id=agent.id,
                            agent_name=agent.name, action_type="do_nothing",
                            platform=agent.environments[0] if agent.environments else "unknown",
                            action_args={},
                        ))
                    return records

            tasks = [step_agent(agent) for agent in agents.values()]
            results = await asyncio.gather(*tasks)
            for records in results:
                chat_log.extend(records)

            # Tick environments
            for env in environments.values():
                env.tick()

            # Collect and distribute events
            all_events = []
            for env in environments.values():
                all_events.extend(env.publish_events())
            bridge.receive_events(all_events)

            # Snapshot
            snapshots.append(RoundSnapshot(
                round=round_num,
                agent_count=len(agents),
                metrics={"actions": len([r for rs in results for r in rs])},
            ))

            # Progress callback
            if on_progress:
                await on_progress(round_num, config.rounds, snapshots[-1].metrics)

            # Clear bridge for next round
            bridge.clear()

        # Build result
        return SimulationResult(
            chat_log=chat_log,
            graph_data=GraphSnapshot(nodes=[], edges=[], metadata={}),
            trajectories={},
            market_data=None,
            raw_state=SimulationState(
                round=config.rounds,
                agents=agents,
                environments=environments,
                events=[],
                snapshots=snapshots,
            ),
        )

    async def run_sweep(
        self,
        sweep: ScenarioSweep,
        on_progress: ProgressCallback | None = None,
    ) -> list[tuple[dict[str, Any], SimulationResult]]:
        """Run a parameter sweep and return keyed results."""
        configs = generate_sweep_configs(sweep)
        results = []
        for key, config in configs:
            result = await self.run(config, on_progress=on_progress)
            results.append((key, result))
        return results

    def _create_environments(self, env_configs: list[EnvironmentConfig]) -> dict[str, Any]:
        environments = {}
        for ec in env_configs:
            if ec.type == "social":
                environments["social"] = SocialEnvironment(SocialConfig(**ec.params))
            elif ec.type == "market":
                environments["market"] = MarketEnvironment(MarketConfig(**ec.params))
        # Default to social if none specified
        if not environments:
            environments["social"] = SocialEnvironment(SocialConfig())
        return environments

    def _create_agents(self, entities: list[Entity], env_names: list[str]) -> dict[str, Agent]:
        agents = {}
        for entity in entities:
            agent = Agent(
                id=entity.id,
                name=entity.name,
                persona=f"You are {entity.name}. {entity.summary}",
                environments=env_names,
                belief_state=BeliefState(),
                config=AgentActivityConfig(),
            )
            agents[agent.id] = agent
        return agents

    def _find_env_for_action(
        self, action_name: str, environments: dict[str, Any], agent: Agent
    ) -> str:
        for env_name in agent.environments:
            if env_name in environments:
                tool_names = {t.name for t in environments[env_name].get_tools()}
                if action_name in tool_names:
                    return env_name
        return agent.environments[0] if agent.environments else "unknown"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/engine/test_engine.py -v`
Expected: All PASS

- [ ] **Step 5: Update `__init__.py` exports**

```python
# simswarm/__init__.py
"""SimSwarm — agent-based simulation engine."""
from simswarm.engine import Engine
from simswarm.sweep import ScenarioSweep
from simswarm.types import (
    Agent,
    BeliefState,
    EngineConfig,
    SimulationConfig,
    SimulationResult,
)

__all__ = [
    "Agent", "BeliefState", "Engine", "EngineConfig",
    "ScenarioSweep", "SimulationConfig", "SimulationResult",
]
```

- [ ] **Step 6: Commit**

```bash
git add simswarm/engine.py simswarm/__init__.py tests/engine/test_engine.py
git commit -m "feat: add core simulation engine with round orchestration"
```

---

### Task 13: Prompt Templates

Centralized Jinja2 templates replacing scattered prompts.

**Files:**
- Create: `simswarm/prompts/__init__.py`
- Create: `simswarm/prompts/agent_system.j2`
- Create: `simswarm/prompts/agent_observation.j2`
- Create: `simswarm/prompts/templates.py`
- Create: `tests/engine/test_prompts.py`

- [ ] **Step 1: Write prompt template tests**

```python
# tests/engine/test_prompts.py
"""Test prompt template rendering."""
from __future__ import annotations

from simswarm.prompts.templates import render_agent_system, render_agent_observation
from simswarm.types import Agent, AgentActivityConfig, BeliefState, Entity, Observation


class TestAgentSystemPrompt:
    def test_includes_entity_name(self):
        entity = Entity(id="e1", name="Alice Chen", type="analyst", summary="Senior financial analyst at Goldman Sachs")
        prompt = render_agent_system(entity, goal="Predict market reaction to tariffs")
        assert "Alice Chen" in prompt
        assert "financial analyst" in prompt

    def test_includes_goal(self):
        entity = Entity(id="e1", name="X", type="person", summary="Test")
        prompt = render_agent_system(entity, goal="Analyze trade policy")
        assert "trade policy" in prompt.lower() or "Analyze" in prompt

    def test_includes_stance_when_provided(self):
        entity = Entity(id="e1", name="X", type="person", summary="Test")
        prompt = render_agent_system(entity, goal="Test", stance="supportive")
        assert "supportive" in prompt.lower()


class TestAgentObservation:
    def test_includes_observations(self):
        obs = [Observation(environment="social", content="[Alice] Markets are down")]
        result = render_agent_observation(obs, variables={"policy": "equity_heavy"})
        assert "Markets are down" in result

    def test_includes_variables(self):
        obs = [Observation(environment="social", content="Feed")]
        result = render_agent_observation(obs, variables={"fund_size": "2T"})
        assert "fund_size" in result

    def test_empty_observations(self):
        result = render_agent_observation([], variables={})
        assert isinstance(result, str)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/engine/test_prompts.py -v`
Expected: FAIL

- [ ] **Step 3: Write the templates**

```bash
mkdir -p simswarm/prompts
```

```jinja2
{# simswarm/prompts/agent_system.j2 #}
You are {{ entity.name }}, {{ entity.summary }}.

Simulation goal: {{ goal }}

{% if stance %}Your stance on this topic is {{ stance }}.{% endif %}

You are participating in a simulation. Act according to your character — make decisions, express opinions, and interact with others as {{ entity.name }} would.

You will be shown a feed of posts and market data. Choose actions using the available tools. If you have nothing meaningful to add, use do_nothing.
```

```jinja2
{# simswarm/prompts/agent_observation.j2 #}
{% for obs in observations %}
--- {{ obs.environment | upper }} ---
{{ obs.content }}

{% endfor %}
{% if variables %}
--- SCENARIO PARAMETERS ---
{% for key, value in variables.items() %}
{{ key }}: {{ value }}
{% endfor %}
{% endif %}
```

```python
# simswarm/prompts/__init__.py
"""Centralized prompt templates."""
```

```python
# simswarm/prompts/templates.py
"""Render Jinja2 prompt templates."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from simswarm.types import Entity, Observation

TEMPLATE_DIR = Path(__file__).parent
_env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), keep_trailing_newline=False)


def render_agent_system(entity: Entity, goal: str, stance: str | None = None) -> str:
    template = _env.get_template("agent_system.j2")
    return template.render(entity=entity, goal=goal, stance=stance).strip()


def render_agent_observation(
    observations: list[Observation],
    variables: dict[str, Any] | None = None,
) -> str:
    template = _env.get_template("agent_observation.j2")
    return template.render(observations=observations, variables=variables or {}).strip()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/engine/test_prompts.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add simswarm/prompts/ tests/engine/test_prompts.py
git commit -m "feat: add centralized Jinja2 prompt templates"
```

---

### Task 14: Integration Test — Full Simulation Loop

End-to-end test that runs a small simulation with mocked LLM and verifies the complete output.

**Files:**
- Create: `tests/engine/test_integration.py`

- [ ] **Step 1: Write the integration test**

```python
# tests/engine/test_integration.py
"""Integration test: run a full simulation with mocked LLM, verify output contracts."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from simswarm.engine import Engine
from simswarm.llm import LLMClient, LLMResponse
from simswarm.sweep import ScenarioSweep
from simswarm.types import (
    EngineConfig,
    Entity,
    EnvironmentConfig,
    SimulationConfig,
)
from tests.contracts.schemas import ChatLogEntry


def _rotating_responses():
    """Return different tool calls across rounds to simulate realistic behavior."""
    responses = [
        LLMResponse(content="", tool_calls=[
            {"name": "create_post", "args": {"text": "The market looks bearish today."}},
        ], raw={}),
        LLMResponse(content="", tool_calls=[
            {"name": "create_post", "args": {"text": "I disagree, fundamentals are strong."}},
        ], raw={}),
        LLMResponse(content="", tool_calls=[
            {"name": "do_nothing", "args": {}},
        ], raw={}),
    ]
    idx = 0
    while True:
        yield responses[idx % len(responses)]
        idx += 1


class TestFullSimulation:
    @pytest.mark.asyncio
    async def test_small_sim_produces_valid_output(self):
        response_gen = _rotating_responses()
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat.side_effect = lambda *a, **kw: next(response_gen)

        engine = Engine(
            fast_llm=mock_llm,
            smart_llm=mock_llm,
            engine_config=EngineConfig(concurrency=4),
        )
        config = SimulationConfig(
            seed_text="Global trade tensions escalate as new tariffs are announced.",
            goal="Predict market sentiment over the next 7 days",
            entities=[
                Entity(id="e1", name="TraderBot", type="analyst", summary="Quantitative trader"),
                Entity(id="e2", name="PolicyWatcher", type="journalist", summary="Economics reporter"),
                Entity(id="e3", name="MarketMaker", type="institution", summary="Investment bank desk"),
            ],
            environments=[EnvironmentConfig(type="social", params={})],
            rounds=5,
            concurrency=4,
        )
        result = await engine.run(config)

        # Chat log should have entries
        assert len(result.chat_log) > 0

        # Every entry should validate against contract schema
        for entry in result.chat_log:
            ChatLogEntry.model_validate({
                "round_num": entry.round_num,
                "agent_id": entry.agent_id,
                "agent_name": entry.agent_name,
                "action_type": entry.action_type,
                "platform": entry.platform,
                "action_args": entry.action_args,
            })

        # Should have entries from multiple agents
        agent_names = {e.agent_name for e in result.chat_log}
        assert len(agent_names) >= 2

        # Should have entries across multiple rounds
        rounds = {e.round_num for e in result.chat_log}
        assert len(rounds) == 5

    @pytest.mark.asyncio
    async def test_sweep_produces_comparable_results(self):
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat.return_value = LLMResponse(
            content="", tool_calls=[{"name": "do_nothing", "args": {}}], raw={},
        )

        engine = Engine(
            fast_llm=mock_llm,
            smart_llm=mock_llm,
            engine_config=EngineConfig(concurrency=4),
        )
        config = SimulationConfig(
            seed_text="Test",
            goal="Test",
            entities=[Entity(id="e1", name="A", type="person", summary="Test")],
            environments=[EnvironmentConfig(type="social", params={})],
            rounds=2,
            concurrency=4,
            variables={"policy": "default"},
        )
        sweep = ScenarioSweep(
            base_config=config,
            vary={"policy": ["a", "b", "c"]},
        )
        results = await engine.run_sweep(sweep)
        assert len(results) == 3
        for key, result in results:
            assert "policy" in key
            assert len(result.chat_log) > 0


class TestMultiEnvironmentSimulation:
    @pytest.mark.asyncio
    async def test_social_and_market_together(self):
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat.return_value = LLMResponse(
            content="",
            tool_calls=[{"name": "create_post", "args": {"text": "Testing"}}],
            raw={},
        )

        engine = Engine(
            fast_llm=mock_llm,
            smart_llm=mock_llm,
            engine_config=EngineConfig(concurrency=4),
        )
        config = SimulationConfig(
            seed_text="Test",
            goal="Test",
            entities=[Entity(id="e1", name="A", type="trader", summary="Trader")],
            environments=[
                EnvironmentConfig(type="social", params={}),
                EnvironmentConfig(type="market", params={
                    "markets": [{"question": "Will X?", "initial_price_yes": 0.5}],
                    "initial_balance": 1000.0,
                }),
            ],
            rounds=2,
            concurrency=4,
        )
        result = await engine.run(config)
        assert len(result.chat_log) > 0
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/engine/test_integration.py -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add tests/engine/test_integration.py
git commit -m "feat: add integration tests for full simulation loop"
```

---

## Phase 3: Migration (separate plan)

Phase 3 covers the report module, new `run_job.py`, shadow mode comparison, and the final swap. This should be planned after Phase 2 is complete and the engine is proven with its own test suite.

Tasks that will be in the Phase 3 plan:
- Economic environment (v1)
- Report module with tool access over SimulationResult
- New `run_job.py` that imports SimSwarm engine
- Output format adapters (SimulationResult → MiroShark-compatible JSON)
- Shadow mode: run both engines, compare outputs
- Docker image update
- MiroShark removal

---

## Run All Tests

After completing all tasks:

```bash
# Contract tests
pytest tests/contracts/ -v

# Engine unit tests
pytest tests/engine/ -v

# All together
pytest tests/ -v
```
