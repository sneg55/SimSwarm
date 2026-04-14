"""Verifies write_results stamps per-agent sentiment onto graph nodes."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from simswarm.types import ActionRecord, GraphSnapshot


def _post(agent_id: str, agent_name: str, content: str, round_num: int) -> ActionRecord:
    return ActionRecord(
        round_num=round_num, agent_id=agent_id, agent_name=agent_name,
        action_type="create_post", platform="twitter",
        action_args={"text": content}, timestamp="t", success=True,
    )


def test_write_results_stamps_sentiment_onto_agent_nodes(tmp_path: Path):
    from infra.docker.run_job_v2_runner import write_results

    # Alice's posts include words that appear in simswarm.stance.POSITIVE_WORDS
    # (e.g. "success", "support", "progress"); Bob's hit NEGATIVE_WORDS. The test asserts
    # directional sentiment, not exact scores — robust to scorer tuning.
    chat_log = [
        _post("alice", "Alice", "great wonderful excellent success support", 1),
        _post("alice", "Alice", "happy love fantastic win progress", 2),
        _post("bob", "Bob", "oppose condemn reject threaten crisis", 1),
    ]

    # Minimal graph_data with nodes keyed by agent_id, matching the native
    # engine's post-adapter shape (id=agent_id, label=agent_name).
    graph_data = GraphSnapshot(
        nodes=[
            {"id": "alice", "label": "Alice", "group": "person"},
            {"id": "bob", "label": "Bob", "group": "person"},
            {"id": "topic-x", "label": "TopicX", "group": "topic"},
        ],
        edges=[],
        metadata={"total_nodes": 3, "total_edges": 0},
    )

    result = SimpleNamespace(chat_log=chat_log, graph_data=graph_data, trajectories={})

    write_results(result, str(tmp_path))

    graph = json.loads((tmp_path / "graph_data.json").read_text())
    nodes_by_id = {n["id"]: n for n in graph["nodes"]}
    assert nodes_by_id["alice"]["sentiment"] > 0.0
    assert nodes_by_id["bob"]["sentiment"] < 0.0
    # Non-agent nodes keep whatever they had (no sentiment key, or unchanged).
    assert nodes_by_id["topic-x"].get("sentiment", 0.0) == 0.0
