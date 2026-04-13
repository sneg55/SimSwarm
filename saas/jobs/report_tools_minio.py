"""ReportTools variant that queries MinIO-sourced JSON dicts.

Public surface matches simswarm.report_tools.ReportTools exactly so the
5-turn tool loop is source-portable. Only the data source differs.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ReportArtifacts:
    """MinIO-sourced artifacts required for report generation.

    Shapes match the JSON written by the pod (see simswarm/extractor.py and
    simswarm/adapter.py for the canonical schemas).
    """
    chat_log: list[dict[str, Any]] = field(default_factory=list)
    posts: list[dict[str, Any]] = field(default_factory=list)
    trades: list[dict[str, Any]] = field(default_factory=list)
    trajectories: list[dict[str, Any]] = field(default_factory=list)


def _detect_coalitions(chat_log: list[dict[str, Any]]) -> list[dict]:
    """Mutual-follow coalition detection over an already-dict chat log."""
    follows: dict[str, set[str]] = {}
    for row in chat_log:
        if row.get("action_type", "").lower() != "follow":
            continue
        agent = row.get("agent_id", "")
        target = (row.get("action_args") or {}).get("target_id", "")
        if agent and target:
            follows.setdefault(agent, set()).add(target)

    coalitions: list[dict] = []
    seen: set[frozenset] = set()
    for a, a_follows in follows.items():
        for b in a_follows:
            if b in follows and a in follows[b]:
                key = frozenset({a, b})
                if key in seen:
                    continue
                seen.add(key)
                coalitions.append({"members": sorted(key), "type": "mutual_follow"})
    return coalitions


class ReportTools:
    """Query tools over MinIO-sourced ReportArtifacts."""

    def __init__(self, artifacts: ReportArtifacts) -> None:
        self._artifacts = artifacts

    def get_top_posts(self, limit: int = 10) -> list[dict]:
        return self._artifacts.posts[:limit]

    def get_coalitions(self) -> list[dict]:
        return _detect_coalitions(self._artifacts.chat_log)

    def get_agent_summary(self, agent_id: str) -> dict:
        actions = [r for r in self._artifacts.chat_log if r.get("agent_id") == agent_id]
        if not actions:
            return {
                "name": agent_id,
                "total_actions": 0,
                "total_posts": 0,
                "rounds_active": 0,
                "sample_posts": [],
            }
        posts = [r for r in actions if r.get("action_type", "").lower() == "create_post"]
        return {
            "name": actions[0].get("agent_name", agent_id),
            "total_actions": len(actions),
            "total_posts": len(posts),
            "rounds_active": len({r.get("round_num") for r in actions}),
            "sample_posts": [
                (r.get("action_args") or {}).get("content", "") for r in posts[:3]
            ],
        }

    def get_trajectory(self, agent_id: str) -> list[dict]:
        for entry in self._artifacts.trajectories:
            if entry.get("agent_id") == agent_id:
                return entry.get("rounds", [])
        return []

    def dispatch(self, tool_name: str, args: dict) -> str:
        try:
            if tool_name == "get_top_posts":
                return json.dumps(self.get_top_posts(**args))
            if tool_name == "get_coalitions":
                return json.dumps(self.get_coalitions())
            if tool_name == "get_agent_summary":
                return json.dumps(self.get_agent_summary(**args))
            if tool_name == "get_trajectory":
                return json.dumps(self.get_trajectory(**args))
            return json.dumps({"error": f"Unknown tool: {tool_name}"})
        except Exception as exc:  # noqa: BLE001
            logger.warning("Tool %s raised: %s", tool_name, exc)
            return json.dumps({"error": str(exc)})

    @staticmethod
    def tool_schemas() -> list[dict]:
        from simswarm.report_tools import ReportTools as RefTools
        return RefTools.tool_schemas()
