"""Shared fixtures and sample data for adapter tests."""
from __future__ import annotations

from simswarm.types import ActionRecord, GraphSnapshot


def make_records() -> list[ActionRecord]:
    return [
        ActionRecord(
            round_num=1,
            agent_id="agent-abc",
            agent_name="TraderBot",
            action_type="CREATE_POST",
            platform="twitter",
            action_args={"content": "Markets looking bearish"},
            timestamp="2026-04-08T10:00:00Z",
            success=True,
        ),
        ActionRecord(
            round_num=2,
            agent_id="agent-xyz",
            agent_name="Analyst",
            action_type="CREATE_COMMENT",
            platform="reddit",
            action_args={"content": "Supply chains are resilient"},
            timestamp=None,
            success=True,
        ),
        ActionRecord(
            round_num=3,
            agent_id="agent-abc",
            agent_name="TraderBot",
            action_type="FOLLOW",
            platform="twitter",
            action_args={"target": "Analyst"},
            timestamp=None,
            success=False,
        ),
        ActionRecord(
            round_num=4,
            agent_id="agent-abc",
            agent_name="TraderBot",
            action_type="BUY",
            platform="polymarket",
            action_args={"market": "will_gdp_rise", "amount": 100},
            timestamp=None,
            success=True,
        ),
    ]


def make_graph() -> GraphSnapshot:
    return GraphSnapshot(
        nodes=[
            {
                "uuid": "n1",
                "name": "US Economy",
                "labels": ["Entity", "Economy"],
                "summary": "Largest economy",
                "connection_count": 2,
                "sentiment": 0.5,
                "stance": "supportive",
                "influence_weight": 1.5,
            },
            {
                "uuid": "n2",
                "name": "China Trade",
                "labels": ["Entity", "Trade"],
                "summary": "Key trade partner",
                "sentiment": -0.3,
            },
        ],
        edges=[
            {
                "uuid": "e1",
                "source_node_uuid": "n1",
                "target_node_uuid": "n2",
                "name": "trades_with",
                "fact": "bilateral trade 600B",
            }
        ],
        metadata={
            "entity_types": ["Economy", "Trade"],
            "total_nodes": 2,
            "total_edges": 1,
        },
    )


def make_findings() -> list[dict]:
    return [
        {"title": "Tariff Escalation", "content": "New tariffs on semiconductors."},
        {"title": "Supply Chain Risk", "content": "Southeast Asia delays reported."},
        {"title": "Investor Mood", "content": "Recession probability at 60%."},
    ]


BRIEF = "Global markets face uncertainty amid trade tensions."
