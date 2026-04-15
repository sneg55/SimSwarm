"""Verify _build_structured produces the full 5-key shape via adapt_structured."""
from __future__ import annotations

import json
from unittest.mock import patch

from saas.jobs.report import ReportResult
from saas.jobs.tasks_report import _build_structured


def _fake_artifacts():
    chat_log = [
        {"round_num": 1, "agent_id": "a1", "agent_name": "Alice",
         "action_type": "CREATE_POST", "platform": "twitter",
         "action_args": {"text": "Hi"}, "success": True, "timestamp": None},
        {"round_num": 2, "agent_id": "a2", "agent_name": "Bob",
         "action_type": "BUY", "platform": "polymarket",
         "action_args": {"qty": 10}, "success": True, "timestamp": None},
    ]
    graph = {
        "nodes": [{"id": "a1", "uuid": "a1", "name": "Alice", "labels": ["Person"],
                   "summary": "", "connection_count": 0, "sentiment": 0.0}],
        "edges": [],
        "metadata": {"total_nodes": 1, "total_edges": 0, "entity_types": ["Person"]},
    }
    return json.dumps(chat_log), json.dumps(graph)


def test_build_structured_emits_all_five_keys():
    chat_json, graph_json = _fake_artifacts()
    result = ReportResult(
        report_markdown="## Executive Summary\nSomething.\n## Key Findings\n### Finding 1: X\nBody.",
        executive_brief="Something.",
        findings=[{"title": "Finding 1: X", "content": "Body."}],
    )
    with patch("saas.jobs.tasks_report._load_job_artifacts",
               return_value=(chat_json, graph_json)):
        out = json.loads(_build_structured(job_id=42, result=result))
    assert set(out.keys()) == {"brief", "findings", "confidence", "coalitions", "sentiment"}
    assert out["brief"] == "Something."
    assert any(c["label"] == "Agents" for c in out["confidence"])
    assert all({"label", "title", "description", "metric", "accentColor"} <= set(f)
               for f in out["findings"])


def test_build_structured_empty_artifacts_still_valid():
    with patch("saas.jobs.tasks_report._load_job_artifacts",
               return_value=("[]", '{"nodes": [], "edges": [], "metadata": {}}')):
        out = json.loads(_build_structured(
            job_id=1,
            result=ReportResult(report_markdown="", executive_brief="", findings=[]),
        ))
    assert out["brief"] == ""
    assert out["findings"] == []
    assert isinstance(out["confidence"], list)
    assert isinstance(out["coalitions"], list)
    assert isinstance(out["sentiment"], list)
