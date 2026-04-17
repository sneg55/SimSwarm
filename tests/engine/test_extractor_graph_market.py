"""Tests for extract_social_graph and extract_market_data."""
from __future__ import annotations

import pytest

from simswarm.extractor import extract_market_data, extract_social_graph
from tests.engine.extractor_fixtures import SAMPLE_LOG


class TestExtractSocialGraph:
    def test_returns_dict_with_required_keys(self):
        result = extract_social_graph(SAMPLE_LOG)
        assert "edges" in result
        assert "mutual_follows" in result

    def test_edges_have_required_fields(self):
        for edge in extract_social_graph(SAMPLE_LOG)["edges"]:
            for field in ("follower_id", "follower_name", "followee_id", "followee_name", "platform"):
                assert field in edge

    def test_correct_edge_count(self):
        # Three follow actions: Carol→Alice, Alice→Carol, Carol→Bob
        result = extract_social_graph(SAMPLE_LOG)
        assert len(result["edges"]) == 3

    def test_follower_ids_present(self):
        follower_ids = [e["follower_id"] for e in extract_social_graph(SAMPLE_LOG)["edges"]]
        assert "agent-gamma" in follower_ids
        assert "agent-alpha" in follower_ids

    def test_detects_mutual_follows(self):
        result = extract_social_graph(SAMPLE_LOG)
        # Alice and Carol follow each other
        mutual_ids = set()
        for mf in result["mutual_follows"]:
            mutual_ids.add(mf["agent_a"])
            mutual_ids.add(mf["agent_b"])
        assert "agent-alpha" in mutual_ids
        assert "agent-gamma" in mutual_ids

    def test_one_way_follow_not_in_mutual(self):
        result = extract_social_graph(SAMPLE_LOG)
        for mf in result["mutual_follows"]:
            pair = {mf["agent_a"], mf["agent_b"]}
            assert pair != {"agent-gamma", "agent-beta"}

    def test_platform_preserved_in_edge(self):
        edges_by_pair = {
            (e["follower_id"], e["followee_id"]): e
            for e in extract_social_graph(SAMPLE_LOG)["edges"]
        }
        assert edges_by_pair[("agent-gamma", "agent-alpha")]["platform"] == "twitter"
        assert edges_by_pair[("agent-gamma", "agent-beta")]["platform"] == "reddit"

    def test_empty_log_returns_empty_graph(self):
        result = extract_social_graph([])
        assert result["edges"] == []
        assert result["mutual_follows"] == []


class TestExtractMarketData:
    def test_returns_list_of_dicts(self):
        result = extract_market_data(SAMPLE_LOG)
        assert isinstance(result, list)
        assert all(isinstance(t, dict) for t in result)

    def test_only_trade_actions_returned(self):
        for trade in extract_market_data(SAMPLE_LOG):
            assert trade["side"] in ("buy", "sell")

    def test_correct_trade_count(self):
        assert len(extract_market_data(SAMPLE_LOG)) == 2

    def test_frontend_schema_fields_present(self):
        # TradeFeed.vue reads: trade_id, side, agent_name, outcome, price, cost
        for trade in extract_market_data(SAMPLE_LOG):
            for field in ("trade_id", "side", "agent_name", "outcome", "price", "cost"):
                assert field in trade, f"missing {field} in {trade}"

    def test_side_derived_from_action_type(self):
        sides = {t["side"] for t in extract_market_data(SAMPLE_LOG)}
        assert sides == {"buy", "sell"}

    def test_buy_cost_from_action_result(self):
        buys = [t for t in extract_market_data(SAMPLE_LOG) if t["side"] == "buy"]
        assert buys[0]["cost"] == pytest.approx(250.0)
        assert buys[0]["price"] == pytest.approx(0.62)
        assert buys[0]["outcome"] == "yes"

    def test_sell_cost_is_proceeds(self):
        sells = [t for t in extract_market_data(SAMPLE_LOG) if t["side"] == "sell"]
        assert sells[0]["cost"] == pytest.approx(45.0)
        assert sells[0]["price"] == pytest.approx(0.45)
        assert sells[0]["outcome"] == "no"

    def test_trade_id_is_stable_and_unique(self):
        trades = extract_market_data(SAMPLE_LOG)
        ids = [t["trade_id"] for t in trades]
        assert len(ids) == len(set(ids))

    def test_empty_log_returns_empty_list(self):
        assert extract_market_data([]) == []
