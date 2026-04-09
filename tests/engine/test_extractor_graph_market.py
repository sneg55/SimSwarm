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
            assert trade["action_type"].lower() in ("buy_shares", "sell_shares")

    def test_correct_trade_count(self):
        # buy_shares (Bob r2) + sell_shares (Alice r3) = 2
        assert len(extract_market_data(SAMPLE_LOG)) == 2

    def test_required_fields_present(self):
        for trade in extract_market_data(SAMPLE_LOG):
            for field in ("agent_id", "agent_name", "round_num", "action_type", "market", "amount"):
                assert field in trade

    def test_market_field_extracted(self):
        trades = {t["market"]: t for t in extract_market_data(SAMPLE_LOG)}
        assert "gdp_rise_q4" in trades
        assert "inflation_below_3pct" in trades

    def test_amount_extracted_correctly(self):
        trades = {t["market"]: t for t in extract_market_data(SAMPLE_LOG)}
        assert trades["gdp_rise_q4"]["amount"] == 250
        assert trades["inflation_below_3pct"]["amount"] == 100

    def test_price_included_when_present(self):
        trades = {t["market"]: t for t in extract_market_data(SAMPLE_LOG)}
        assert trades["gdp_rise_q4"]["price"] == pytest.approx(0.62)
        assert trades["inflation_below_3pct"]["price"] == pytest.approx(0.45)

    def test_empty_log_returns_empty_list(self):
        assert extract_market_data([]) == []
