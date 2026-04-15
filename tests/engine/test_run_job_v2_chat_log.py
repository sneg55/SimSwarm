"""Tests for run_job_v2: chat_log.json contract validation.

Verifies that write_results produces a chat_log.json whose entries
conform to the ChatLogEntry contract schema (string agent_id, required fields).
"""
from __future__ import annotations

import json


from tests.engine.run_job_v2_fixtures import (
    make_simulation_result,
    rjv2,  # noqa: F401
)


class TestChatLogJson:
    def test_parses_as_list(self, rjv2, tmp_path):  # noqa: F811
        result = make_simulation_result()
        rjv2.write_results(result, str(tmp_path))
        data = json.loads((tmp_path / "chat_log.json").read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert len(data) == len(result.chat_log)

    def test_agent_id_is_string(self, rjv2, tmp_path):  # noqa: F811
        """adapt_chat_log must preserve string agent_id from ActionRecord."""
        rjv2.write_results(make_simulation_result(), str(tmp_path))
        data = json.loads((tmp_path / "chat_log.json").read_text(encoding="utf-8"))
        for entry in data:
            assert isinstance(entry["agent_id"], str), (
                f"agent_id must be str, got {type(entry['agent_id'])!r}"
            )

    def test_entries_validate_against_contract_schema(self, rjv2, tmp_path):  # noqa: F811
        from tests.contracts.schemas import ChatLogEntry

        rjv2.write_results(make_simulation_result(), str(tmp_path))
        data = json.loads((tmp_path / "chat_log.json").read_text(encoding="utf-8"))
        for entry in data:
            validated = ChatLogEntry.model_validate(entry)
            assert isinstance(validated.agent_id, str)
            assert isinstance(validated.round_num, int)
            assert validated.platform != ""

    def test_action_types_preserved(self, rjv2, tmp_path):  # noqa: F811
        rjv2.write_results(make_simulation_result(), str(tmp_path))
        data = json.loads((tmp_path / "chat_log.json").read_text(encoding="utf-8"))
        action_types = {e["action_type"] for e in data}
        assert "CREATE_POST" in action_types

    def test_required_fields_present_in_every_entry(self, rjv2, tmp_path):  # noqa: F811
        rjv2.write_results(make_simulation_result(), str(tmp_path))
        data = json.loads((tmp_path / "chat_log.json").read_text(encoding="utf-8"))
        required = {"round_num", "agent_id", "agent_name", "action_type", "platform", "action_args"}
        for entry in data:
            missing = required - entry.keys()
            assert not missing, f"Entry missing fields: {missing}"


class TestGraphNodeAgentAttrs:
    def test_nodes_carry_stance_and_influence_weight(self, rjv2, tmp_path):  # noqa: F811
        """write_results must stamp AgentActivityConfig.stance and
        influence_weight onto graph nodes so the Graph detail panel can
        render them."""
        import json
        from simswarm.types import (
            Agent, AgentActivityConfig, BeliefState, GraphSnapshot,
            SimulationResult, SimulationState,
        )

        # Build a minimal SimulationResult whose graph nodes use "id" keys
        # that match the agent ids in raw_state.
        graph = GraphSnapshot(
            nodes=[
                {"id": "n1", "label": "Alice"},
                {"id": "n2", "label": "Bob"},
            ],
            edges=[],
            metadata={"entity_types": [], "total_nodes": 2, "total_edges": 0},
        )
        result = SimulationResult(chat_log=[], graph_data=graph, trajectories={})

        ag1 = Agent(
            id="n1", name="Alice", persona="", environments=[],
            belief_state=BeliefState(),
            config=AgentActivityConfig(stance="supportive", influence_weight=1.5),
        )
        ag2 = Agent(
            id="n2", name="Bob", persona="", environments=[],
            belief_state=BeliefState(),
            config=AgentActivityConfig(stance="opposing", influence_weight=0.8),
        )
        result.raw_state = SimulationState(
            round=1, agents={"n1": ag1, "n2": ag2},
            environments={}, events=[], snapshots=[],
        )
        rjv2.write_results(result, str(tmp_path))

        data = json.loads((tmp_path / "graph_data.json").read_text(encoding="utf-8"))
        by_id = {n["id"]: n for n in data["nodes"]}
        assert by_id["n1"]["stance"] == "supportive"
        assert by_id["n1"]["influence_weight"] == 1.5
        assert by_id["n2"]["stance"] == "opposing"
        assert by_id["n2"]["influence_weight"] == 0.8
