"""Shared fixtures and loader for run_job_v2 tests.

Provides:
  - _load_run_job_v2()   — imports run_job_v2 with stub deps
  - make_simulation_result()
  - make_report()
"""
from __future__ import annotations

import importlib
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DOCKER_DIR = REPO_ROOT / "infra" / "docker"
RUN_JOB_V2 = DOCKER_DIR / "run_job_v2.py"


# ---------------------------------------------------------------------------
# Stub factory
# ---------------------------------------------------------------------------

def _make_stubs() -> dict[str, types.ModuleType]:
    stubs: dict[str, types.ModuleType] = {}

    graph_ops = types.ModuleType("graph_ops")
    graph_ops.build_graph = MagicMock(return_value=("proj-1", "graph-1"))
    stubs["graph_ops"] = graph_ops

    service_init = types.ModuleType("service_init")
    service_init.wait_for_neo4j = MagicMock()
    service_init.wait_for_vllm = MagicMock()
    stubs["service_init"] = service_init

    neo4j_mod = types.ModuleType("app.storage.neo4j_storage")
    neo4j_mod.Neo4jStorage = MagicMock()
    stubs["app"] = types.ModuleType("app")
    stubs["app.storage"] = types.ModuleType("app.storage")
    stubs["app.storage.neo4j_storage"] = neo4j_mod

    return stubs


def _load_run_job_v2() -> types.ModuleType:
    stubs = _make_stubs()
    pre = {k: sys.modules[k] for k in stubs if k in sys.modules}
    for name, mod in stubs.items():
        sys.modules[name] = mod
    try:
        spec = importlib.util.spec_from_file_location("run_job_v2", RUN_JOB_V2)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        for name in stubs:
            if name in pre:
                sys.modules[name] = pre[name]
            else:
                sys.modules.pop(name, None)


# ---------------------------------------------------------------------------
# Pytest fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def rjv2():
    return _load_run_job_v2()


# ---------------------------------------------------------------------------
# Data builders
# ---------------------------------------------------------------------------

def make_simulation_result():
    from simswarm.types import ActionRecord, GraphSnapshot, SimulationResult

    chat_log = [
        ActionRecord(
            round_num=1, agent_id="agent-alpha", agent_name="Alice",
            action_type="CREATE_POST", platform="twitter",
            action_args={"content": "Support this initiative!"},
            timestamp="2026-04-08T10:00:00Z", success=True,
        ),
        ActionRecord(
            round_num=1, agent_id="agent-beta", agent_name="Bob",
            action_type="FOLLOW", platform="twitter",
            action_args={"target_id": "agent-alpha", "target_name": "Alice"},
            timestamp="2026-04-08T10:01:00Z", success=True,
        ),
        ActionRecord(
            round_num=2, agent_id="agent-alpha", agent_name="Alice",
            action_type="buy_shares", platform="market",
            action_args={"market": "election", "amount": 50},
            timestamp="2026-04-08T10:02:00Z", success=True,
        ),
    ]
    graph = GraphSnapshot(
        nodes=[{
            "uuid": "n1", "name": "Alice", "labels": ["Entity", "Person"],
            "summary": "Key figure", "connection_count": 1,
        }],
        edges=[],
        metadata={"entity_types": ["Person"], "total_nodes": 1, "total_edges": 0},
    )
    return SimulationResult(chat_log=chat_log, graph_data=graph, trajectories={})


def make_report():
    from simswarm.report import Report

    return Report(
        executive_brief="The simulation shows clear polarization.",
        findings=[
            {"title": "Coalition Formation", "content": "Alice and Bob diverge."},
            {"title": "Market Signals", "content": "Bearish sentiment in round 2."},
        ],
        raw_markdown=(
            "## Executive Summary\n\nThe simulation shows clear polarization.\n\n"
            "## Key Findings\n\n### Coalition Formation\nAlice and Bob diverge.\n"
        ),
    )
