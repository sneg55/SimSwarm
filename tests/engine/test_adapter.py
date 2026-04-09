"""Tests for adapt_chat_log and adapt_graph_data."""
from __future__ import annotations

from simswarm.adapter import adapt_chat_log, adapt_graph_data
from simswarm.types import ActionRecord, GraphSnapshot
from tests.contracts.schemas import ChatLogEntry, GraphData
from tests.engine.adapter_fixtures import make_graph, make_records


class TestAdaptChatLog:
    def test_returns_list_of_dicts(self):
        result = adapt_chat_log(make_records())
        assert isinstance(result, list)
        assert all(isinstance(e, dict) for e in result)

    def test_agent_id_converted_to_int(self):
        for entry in adapt_chat_log(make_records()):
            assert isinstance(entry["agent_id"], int)

    def test_agent_id_hash_formula(self):
        record = ActionRecord(
            round_num=1, agent_id="agent-abc", agent_name="TestBot",
            action_type="CREATE_POST", platform="twitter", action_args={},
        )
        result = adapt_chat_log([record])
        assert result[0]["agent_id"] == abs(hash("agent-abc")) % 10**9

    def test_same_agent_id_str_maps_to_same_int(self):
        result = adapt_chat_log(make_records())
        # agent-abc appears at indices 0, 2, 3
        assert result[0]["agent_id"] == result[2]["agent_id"] == result[3]["agent_id"]

    def test_different_agent_ids_map_to_different_ints(self):
        result = adapt_chat_log(make_records())
        assert result[0]["agent_id"] != result[1]["agent_id"]

    def test_preserves_core_fields(self):
        entry = adapt_chat_log(make_records())[0]
        assert entry["round_num"] == 1
        assert entry["agent_name"] == "TraderBot"
        assert entry["action_type"] == "CREATE_POST"
        assert entry["platform"] == "twitter"
        assert entry["action_args"] == {"content": "Markets looking bearish"}
        assert entry["timestamp"] == "2026-04-08T10:00:00Z"

    def test_none_timestamp_preserved(self):
        assert adapt_chat_log(make_records())[1]["timestamp"] is None

    def test_all_entries_validate_against_schema(self):
        for entry in adapt_chat_log(make_records()):
            ChatLogEntry.model_validate(entry)

    def test_empty_list_returns_empty_list(self):
        assert adapt_chat_log([]) == []


class TestAdaptGraphData:
    def test_returns_dict_with_required_keys(self):
        result = adapt_graph_data(make_graph())
        assert set(result.keys()) >= {"nodes", "edges", "metadata"}

    def test_validates_against_schema(self):
        validated = GraphData.model_validate(adapt_graph_data(make_graph()))
        assert validated.metadata.total_nodes == 2
        assert validated.metadata.total_edges == 1

    def test_preserves_node_sentiment(self):
        nodes = {n["uuid"]: n for n in adapt_graph_data(make_graph())["nodes"]}
        assert nodes["n1"]["sentiment"] == 0.5
        assert nodes["n2"]["sentiment"] == -0.3

    def test_preserves_node_stance(self):
        nodes = {n["uuid"]: n for n in adapt_graph_data(make_graph())["nodes"]}
        assert nodes["n1"]["stance"] == "supportive"

    def test_preserves_node_influence_weight(self):
        nodes = {n["uuid"]: n for n in adapt_graph_data(make_graph())["nodes"]}
        assert nodes["n1"]["influence_weight"] == 1.5

    def test_preserves_edge_fields(self):
        edge = adapt_graph_data(make_graph())["edges"][0]
        assert edge["uuid"] == "e1"
        assert edge["source_node_uuid"] == "n1"
        assert edge["target_node_uuid"] == "n2"
        assert edge["fact"] == "bilateral trade 600B"

    def test_metadata_entity_types_preserved(self):
        result = adapt_graph_data(make_graph())
        assert result["metadata"]["entity_types"] == ["Economy", "Trade"]

    def test_empty_graph_validates(self):
        graph = GraphSnapshot(
            nodes=[], edges=[],
            metadata={"entity_types": [], "total_nodes": 0, "total_edges": 0},
        )
        validated = GraphData.model_validate(adapt_graph_data(graph))
        assert validated.metadata.total_nodes == 0
