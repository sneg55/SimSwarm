"""Golden file tests: validate saved engine outputs against contract schemas.

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
