"""Shared fixtures for story_signals tests."""
from __future__ import annotations


def make_chat_log() -> list[dict]:
    """A minimal chat log covering 15 rounds with two clear stance blocs."""
    return [
        # Industry bloc — opposed stance
        {"round_num": 1, "agent_id": "ms", "agent_name": "Morgan Stanley",
         "action_type": "CREATE_POST", "platform": "twitter",
         "action_args": {"text": "We oppose prescriptive mandates; adaptable frameworks serve markets better."},
         "timestamp": None, "success": True},
        {"round_num": 5, "agent_id": "msft", "agent_name": "Microsoft",
         "action_type": "CREATE_POST", "platform": "twitter",
         "action_args": {"text": "Overly strict data transparency requirements would be a compliance cost burden."},
         "timestamp": None, "success": True},
        {"round_num": 8, "agent_id": "ms", "agent_name": "Morgan Stanley",
         "action_type": "CREATE_POST", "platform": "twitter",
         "action_args": {"text": "Compliance coalitions should be industry-led, not prescriptive."},
         "timestamp": None, "success": True},
        # Regulator bloc — supportive stance
        {"round_num": 2, "agent_id": "sec", "agent_name": "SEC",
         "action_type": "CREATE_POST", "platform": "twitter",
         "action_args": {"text": "Standardized transparency is essential; we endorse accountability."},
         "timestamp": None, "success": True},
        {"round_num": 6, "agent_id": "iac", "agent_name": "Investor Advisory Committee",
         "action_type": "CREATE_POST", "platform": "twitter",
         "action_args": {"text": "We support standardized disclosure frameworks with clarity."},
         "timestamp": None, "success": True},
        # Neutral — Fed
        {"round_num": 10, "agent_id": "fed", "agent_name": "Federal Reserve",
         "action_type": "CREATE_POST", "platform": "twitter",
         "action_args": {"text": "Accountability must be balanced against systemic stability."},
         "timestamp": None, "success": True},
        # Engagement signals — one like on Morgan Stanley's post
        {"round_num": 9, "agent_id": "gs", "agent_name": "Goldman Sachs",
         "action_type": "LIKE_POST", "platform": "twitter",
         "action_args": {"target_post": "ms_r8"},
         "timestamp": None, "success": True},
    ]


def make_graph_data() -> dict:
    return {
        "nodes": [
            {"uuid": "n1", "name": "Morgan Stanley", "labels": ["Entity", "Bank"], "summary": ""},
            {"uuid": "n2", "name": "Microsoft", "labels": ["Entity", "Tech"], "summary": ""},
            {"uuid": "n3", "name": "SEC", "labels": ["Entity", "Regulator"], "summary": ""},
        ],
        "edges": [],
        "metadata": {"entity_types": ["Bank", "Tech", "Regulator"], "total_nodes": 3, "total_edges": 0},
    }
