"""ReportTools: query tools over SimulationResult for LLM tool-calling loops."""
from __future__ import annotations

import json
import logging
from typing import Any

from simswarm.adapter import _detect_coalitions
from simswarm.extractor import extract_agent_trajectories, extract_posts
from simswarm.types import SimulationResult

logger = logging.getLogger(__name__)


def _adapt_log(chat_log: list) -> list[dict[str, Any]]:
    """Convert ActionRecord list to the dict format expected by adapter helpers."""
    return [
        {
            "round_num": r.round_num,
            "agent_id": r.agent_id,
            "agent_name": r.agent_name,
            "action_type": r.action_type,
            "platform": r.platform,
            "action_args": r.action_args,
            "timestamp": r.timestamp,
            "success": r.success,
        }
        for r in chat_log
    ]


class ReportTools:
    """Query tools over a SimulationResult for use in LLM tool-calling loops."""

    def __init__(self, result: SimulationResult) -> None:
        self._result = result
        self._adapted_log: list[dict[str, Any]] = _adapt_log(result.chat_log)

    # ------------------------------------------------------------------
    # Public query methods
    # ------------------------------------------------------------------

    def get_top_posts(self, limit: int = 10) -> list[dict]:
        """Return up to *limit* post dicts from the simulation chat log."""
        return extract_posts(self._result.chat_log)[:limit]

    def get_coalitions(self) -> list[dict]:
        """Detect and return coalitions from mutual-follow patterns."""
        return _detect_coalitions(self._adapted_log)

    def get_agent_summary(self, agent_id: str) -> dict:
        """Return a summary dict for *agent_id*.

        Keys: name, total_actions, total_posts, rounds_active, sample_posts.
        Falls back to agent_id as name for unknown agents.
        """
        actions = [r for r in self._result.chat_log if r.agent_id == agent_id]
        if not actions:
            return {
                "name": agent_id,
                "total_actions": 0,
                "total_posts": 0,
                "rounds_active": 0,
                "sample_posts": [],
            }

        posts = [r for r in actions if r.action_type.lower() == "create_post"]
        return {
            "name": actions[0].agent_name,
            "total_actions": len(actions),
            "total_posts": len(posts),
            "rounds_active": len({r.round_num for r in actions}),
            "sample_posts": [r.action_args.get("content", "") for r in posts[:3]],
        }

    def get_trajectory(self, agent_id: str) -> list[dict]:
        """Return per-round trajectory for *agent_id*. Returns [] for unknown agents."""
        for entry in extract_agent_trajectories(self._result.chat_log):
            if entry["agent_id"] == agent_id:
                return entry.get("rounds", [])
        return []

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def dispatch(self, tool_name: str, args: dict) -> str:
        """Dispatch *tool_name* with *args*, returning a JSON string."""
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

    # ------------------------------------------------------------------
    # Schemas
    # ------------------------------------------------------------------

    @staticmethod
    def tool_schemas() -> list[dict]:
        """Return OpenAI function-calling tool schemas for all query tools."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_top_posts",
                    "description": "Return the top posts from the simulation chat log.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of posts to return (default 10).",
                            }
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_coalitions",
                    "description": "Detect mutual-follow coalitions among agents.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_agent_summary",
                    "description": (
                        "Return a summary for a specific agent: name, total_actions, "
                        "total_posts, rounds_active, sample_posts."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "agent_id": {
                                "type": "string",
                                "description": "The agent's ID string.",
                            }
                        },
                        "required": ["agent_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_trajectory",
                    "description": "Return per-round activity trajectory for an agent.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "agent_id": {
                                "type": "string",
                                "description": "The agent's ID string.",
                            }
                        },
                        "required": ["agent_id"],
                    },
                },
            },
        ]
