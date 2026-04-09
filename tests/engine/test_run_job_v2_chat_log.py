"""Tests for run_job_v2: chat_log.json contract validation.

Verifies that write_results produces a chat_log.json whose entries
conform to the ChatLogEntry contract schema (integer agent_id, required fields).
"""
from __future__ import annotations

import json

import pytest

from tests.engine.run_job_v2_fixtures import (
    make_report,
    make_simulation_result,
    rjv2,  # noqa: F401
)


class TestChatLogJson:
    def test_parses_as_list(self, rjv2, tmp_path):
        result = make_simulation_result()
        rjv2.write_results(result, make_report(), str(tmp_path))
        data = json.loads((tmp_path / "chat_log.json").read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert len(data) == len(result.chat_log)

    def test_agent_id_is_integer(self, rjv2, tmp_path):
        """adapt_chat_log must convert string agent_id to int via hash."""
        rjv2.write_results(make_simulation_result(), make_report(), str(tmp_path))
        data = json.loads((tmp_path / "chat_log.json").read_text(encoding="utf-8"))
        for entry in data:
            assert isinstance(entry["agent_id"], int), (
                f"agent_id must be int, got {type(entry['agent_id'])!r}"
            )

    def test_entries_validate_against_contract_schema(self, rjv2, tmp_path):
        from tests.contracts.schemas import ChatLogEntry

        rjv2.write_results(make_simulation_result(), make_report(), str(tmp_path))
        data = json.loads((tmp_path / "chat_log.json").read_text(encoding="utf-8"))
        for entry in data:
            validated = ChatLogEntry.model_validate(entry)
            assert isinstance(validated.agent_id, int)
            assert isinstance(validated.round_num, int)
            assert validated.platform != ""

    def test_action_types_preserved(self, rjv2, tmp_path):
        rjv2.write_results(make_simulation_result(), make_report(), str(tmp_path))
        data = json.loads((tmp_path / "chat_log.json").read_text(encoding="utf-8"))
        action_types = {e["action_type"] for e in data}
        assert "CREATE_POST" in action_types

    def test_required_fields_present_in_every_entry(self, rjv2, tmp_path):
        rjv2.write_results(make_simulation_result(), make_report(), str(tmp_path))
        data = json.loads((tmp_path / "chat_log.json").read_text(encoding="utf-8"))
        required = {"round_num", "agent_id", "agent_name", "action_type", "platform", "action_args"}
        for entry in data:
            missing = required - entry.keys()
            assert not missing, f"Entry missing fields: {missing}"
