"""Shared fixtures for report module tests."""
from __future__ import annotations

from simswarm.types import ActionRecord, GraphSnapshot, SimulationResult

SAMPLE_MARKDOWN = """## Executive Summary

The simulation revealed significant polarization between pro-trade and anti-trade agents.

## Key Findings

### Finding 1: Coalition Formation
Alice and Bob formed opposing camps early in the simulation.

### Finding 2: Market Signals
Trading activity indicated bearish sentiment in round 2.

## Agent Coalitions

Coalition 1 includes Alice and Carol.

## Market Analysis

Polymarket data shows declining confidence.

## Conclusion

The simulation demonstrates clear narrative divergence.
"""


def make_chat_log() -> list[ActionRecord]:
    return [
        ActionRecord(
            round_num=1,
            agent_id="agent-alpha",
            agent_name="Alice",
            action_type="create_post",
            platform="twitter",
            action_args={"content": "Support the new initiative — great opportunity!"},
            timestamp="2026-04-08T10:00:00Z",
            success=True,
        ),
        ActionRecord(
            round_num=1,
            agent_id="agent-beta",
            agent_name="Bob",
            action_type="CREATE_POST",
            platform="reddit",
            action_args={"content": "I oppose this — danger ahead."},
            timestamp="2026-04-08T10:01:00Z",
            success=True,
        ),
        ActionRecord(
            round_num=2,
            agent_id="agent-alpha",
            agent_name="Alice",
            action_type="create_post",
            platform="twitter",
            action_args={"content": "Progress continues."},
            timestamp="2026-04-08T10:10:00Z",
            success=True,
        ),
        ActionRecord(
            round_num=2,
            agent_id="agent-beta",
            agent_name="Bob",
            action_type="do_nothing",
            platform="twitter",
            action_args={},
            timestamp="2026-04-08T10:11:00Z",
            success=True,
        ),
        ActionRecord(
            round_num=1,
            agent_id="agent-alpha",
            agent_name="Alice",
            action_type="FOLLOW",
            platform="twitter",
            action_args={"target": "Bob"},
            timestamp="2026-04-08T10:02:00Z",
            success=True,
        ),
        ActionRecord(
            round_num=1,
            agent_id="agent-beta",
            agent_name="Bob",
            action_type="FOLLOW",
            platform="twitter",
            action_args={"target": "Alice"},
            timestamp="2026-04-08T10:03:00Z",
            success=True,
        ),
    ]


def make_result() -> SimulationResult:
    chat_log = make_chat_log()
    graph = GraphSnapshot(
        nodes=[{"id": "n1", "label": "Alice"}],
        edges=[],
        metadata={"total_nodes": 1},
    )
    return SimulationResult(
        chat_log=chat_log,
        graph_data=graph,
        trajectories={},
    )
