"""Unit tests for saas.jobs.market_derivation."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from saas.jobs.market_derivation import (
    DERIVATION_SOURCE_FALLBACK,
    DERIVATION_SOURCE_LLM,
    derive_markets,
)


def _fake_grok_client(payload: dict | str):
    """Build a MagicMock emulating the OpenAI-compatible Grok client.

    The deriver calls ``client.responses.create(...)`` and reads
    ``response.output_text``. The payload is what the "LLM" returns.
    """
    text = payload if isinstance(payload, str) else json.dumps(payload)
    client = MagicMock()
    client.responses.create.return_value = MagicMock(output_text=text)
    return client


class TestDeriveMarkets:
    def test_happy_path_returns_validated_markets(self, monkeypatch):
        client = _fake_grok_client({
            "markets": [
                {"question": "Fed cuts 50bp+?", "initial_price_yes": 0.45, "rationale": "labor market softening"},
                {"question": "Fed cuts 25bp?",   "initial_price_yes": 0.30, "rationale": "inflation still high"},
                {"question": "Fed holds rates?", "initial_price_yes": 0.25, "rationale": "base case"},
            ]
        })
        monkeypatch.setattr("saas.jobs.market_derivation._build_client", lambda: client)
        out = derive_markets(goal="Will the Fed cut rates?", enriched_seed="…", tier="small")
        assert out["source"] == DERIVATION_SOURCE_LLM
        assert len(out["markets"]) == 3
        assert out["markets"][0]["question"] == "Fed cuts 50bp+?"
        assert out["markets"][0]["rationale"] == "labor market softening"

    def test_tier_cap_slices(self, monkeypatch):
        markets = [{"question": f"Q{i}", "initial_price_yes": 0.5} for i in range(7)]
        client = _fake_grok_client({"markets": markets})
        monkeypatch.setattr("saas.jobs.market_derivation._build_client", lambda: client)
        assert len(derive_markets("g", "s", "small")["markets"]) == 3
        assert len(derive_markets("g", "s", "medium")["markets"]) == 4
        assert len(derive_markets("g", "s", "large")["markets"]) == 5

    def test_initial_price_clamped(self, monkeypatch):
        client = _fake_grok_client({
            "markets": [
                {"question": "Too high?", "initial_price_yes": 1.0},
                {"question": "Too low?",  "initial_price_yes": 0.0},
                {"question": "Just right?", "initial_price_yes": 0.5},
            ]
        })
        monkeypatch.setattr("saas.jobs.market_derivation._build_client", lambda: client)
        prices = [m["initial_price_yes"] for m in derive_markets("g", "s", "large")["markets"]]
        assert prices == [0.95, 0.05, 0.5]

    def test_duplicates_are_deduped_case_insensitive(self, monkeypatch):
        client = _fake_grok_client({
            "markets": [
                {"question": "Will X happen?", "initial_price_yes": 0.5},
                {"question": "will x happen?", "initial_price_yes": 0.5},
                {"question": "Something else?", "initial_price_yes": 0.4},
            ]
        })
        monkeypatch.setattr("saas.jobs.market_derivation._build_client", lambda: client)
        out = derive_markets("g", "s", "large")["markets"]
        assert len(out) == 2
        assert out[0]["question"] == "Will X happen?"
        assert out[1]["question"] == "Something else?"

    def test_question_too_long_rejected(self, monkeypatch):
        client = _fake_grok_client({
            "markets": [
                {"question": "x" * 121, "initial_price_yes": 0.5},
                {"question": "Valid Q?", "initial_price_yes": 0.5},
            ]
        })
        monkeypatch.setattr("saas.jobs.market_derivation._build_client", lambda: client)
        out = derive_markets("g", "s", "large")["markets"]
        assert len(out) == 1
        assert out[0]["question"] == "Valid Q?"

    def test_empty_question_rejected(self, monkeypatch):
        client = _fake_grok_client({
            "markets": [
                {"question": "   ", "initial_price_yes": 0.5},
                {"question": "Valid?", "initial_price_yes": 0.5},
            ]
        })
        monkeypatch.setattr("saas.jobs.market_derivation._build_client", lambda: client)
        out = derive_markets("g", "s", "large")["markets"]
        assert [m["question"] for m in out] == ["Valid?"]

    def test_malformed_json_falls_back_to_single_market(self, monkeypatch):
        client = _fake_grok_client("this is not JSON")
        monkeypatch.setattr("saas.jobs.market_derivation._build_client", lambda: client)
        out = derive_markets(goal="My Goal?", enriched_seed="", tier="small")
        assert out["source"] == DERIVATION_SOURCE_FALLBACK
        assert out["markets"] == [{"question": "My Goal?", "initial_price_yes": 0.5, "rationale": ""}]

    def test_empty_markets_list_falls_back(self, monkeypatch):
        client = _fake_grok_client({"markets": []})
        monkeypatch.setattr("saas.jobs.market_derivation._build_client", lambda: client)
        out = derive_markets(goal="G?", enriched_seed="", tier="small")
        assert out["source"] == DERIVATION_SOURCE_FALLBACK

    def test_missing_api_key_falls_back(self, monkeypatch):
        monkeypatch.setattr("saas.jobs.market_derivation._build_client", lambda: None)
        out = derive_markets(goal="Goal text?", enriched_seed="", tier="medium")
        assert out["source"] == DERIVATION_SOURCE_FALLBACK
        assert out["markets"] == [{"question": "Goal text?", "initial_price_yes": 0.5, "rationale": ""}]

    def test_client_exception_falls_back(self, monkeypatch):
        client = MagicMock()
        client.responses.create.side_effect = RuntimeError("grok down")
        monkeypatch.setattr("saas.jobs.market_derivation._build_client", lambda: client)
        out = derive_markets(goal="G?", enriched_seed="", tier="small")
        assert out["source"] == DERIVATION_SOURCE_FALLBACK
