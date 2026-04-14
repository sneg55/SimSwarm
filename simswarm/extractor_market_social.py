"""Market trade and social-graph extractors."""
from __future__ import annotations

from typing import Any

from simswarm.extractor_common import is_follow, is_trade
from simswarm.types import ActionRecord


def extract_social_graph(chat_log: list[ActionRecord]) -> dict:
    """Extract follow relationships from the chat log.

    Returns:
        {
            edges: [{follower_id, follower_name, followee_id, followee_name, platform}],
            mutual_follows: [{agent_a, agent_b}],
        }
    """
    edges: list[dict] = []
    follow_set: set[tuple[str, str]] = set()

    for record in chat_log:
        if not is_follow(record.action_type):
            continue
        args = record.action_args or {}
        followee_id = args.get("target_id", "")
        followee_name = args.get("target_name", "")
        if not followee_id:
            continue
        edges.append({
            "follower_id": record.agent_id,
            "follower_name": record.agent_name,
            "followee_id": followee_id,
            "followee_name": followee_name,
            "platform": record.platform,
        })
        follow_set.add((record.agent_id, followee_id))

    seen: set[frozenset[str]] = set()
    mutual_follows: list[dict] = []
    for (a, b) in follow_set:
        if (b, a) in follow_set:
            key = frozenset({a, b})
            if key not in seen:
                seen.add(key)
                mutual_follows.append({"agent_a": a, "agent_b": b})

    return {"edges": edges, "mutual_follows": mutual_follows}


def extract_market_data(chat_log: list[ActionRecord]) -> list[dict]:
    """Extract trade records from buy_shares / sell_shares actions.

    Each entry: agent_id, agent_name, round_num, action_type, market, amount,
    and optionally price.
    """
    result = []
    for record in chat_log:
        if not is_trade(record.action_type):
            continue
        args = record.action_args or {}
        entry: dict[str, Any] = {
            "agent_id": record.agent_id,
            "agent_name": record.agent_name,
            "round_num": record.round_num,
            "action_type": record.action_type,
            "platform": record.platform,
            "market": args.get("market", ""),
            "amount": args.get("amount"),
            "timestamp": record.timestamp,
            "success": record.success,
        }
        if "price" in args:
            entry["price"] = args["price"]
        result.append(entry)
    return result
