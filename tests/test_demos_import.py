"""Verify the demo importer writes structured dicts compatible with the
post-cutover SimulationResults Story template (Path-3 shape: brief/verdict/
findings + deterministic signals). Prevents regression where imported demos
rendered old-shape cards."""
from __future__ import annotations

import json

from infra.scripts.import_demos import build_structured_payload


def test_build_structured_payload_has_required_keys():
    # build_structured_payload must accept the same minimal inputs tasks_report
    # uses: executive brief string, findings list, chat_log list, graph dict.
    payload = build_structured_payload(
        brief="demo brief",
        findings=[{"title": "F1", "content": "body"}],
        chat_log=[],
        graph_data={"nodes": [], "edges": [],
                    "metadata": {"total_nodes": 0, "total_edges": 0, "entity_types": []}},
    )
    data = json.loads(payload) if isinstance(payload, str) else payload
    expected_keys = {
        "brief", "verdict", "findings",
        "stakeholder_positions", "named_coalitions", "phase_boundaries",
        "quotable_posts", "disagreement_axis", "sim_scale",
    }
    assert expected_keys <= set(data)
    assert data["brief"] == "demo brief"
    # Path-3 findings shape (legacy {title, content} wrapper path)
    assert all("accent_color" in f for f in data["findings"])
