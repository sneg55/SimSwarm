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

    Emits the schema consumed by frontend/src/components/data/TradeFeed.vue:
      - trade_id: stable synthetic id (agent_id + round + index)
      - side: "buy" | "sell" (derived from action_type)
      - agent_id, agent_name, round_num, platform
      - market_id, outcome
      - price: executed price at fill time
      - cost: USD spent (buys) or proceeds received (sells) — dollar magnitude
      - shares: shares bought or sold
      - amount_requested: original USD the agent asked to spend (buys only)
      - timestamp, success

    Reads executed values from record.action_result (populated by the engine
    from the env's ActionResult.data). Falls back to action_args for backward
    compatibility with pre-T1 chat logs.
    """
    result: list[dict] = []
    for idx, record in enumerate(chat_log):
        if not is_trade(record.action_type):
            continue
        args = record.action_args or {}
        res = record.action_result or {}
        side = "buy" if record.action_type.lower() == "buy_shares" else "sell"

        if side == "buy":
            cost = res.get("cost", args.get("amount"))
            shares = res.get("shares")
        else:
            # Sell: expose proceeds under `cost` so the UI column stays non-negative.
            cost = res.get("proceeds")
            shares = res.get("shares", args.get("shares"))

        entry: dict[str, Any] = {
            "trade_id": f"{record.agent_id}-r{record.round_num}-{idx}",
            "side": side,
            "agent_id": record.agent_id,
            "agent_name": record.agent_name,
            "round_num": record.round_num,
            "platform": record.platform,
            "market_id": res.get("market_id", args.get("market_id", args.get("market", ""))),
            "outcome": res.get("outcome", args.get("outcome", "")),
            "price": res.get("price"),
            "cost": cost,
            "shares": shares,
            "amount_requested": args.get("amount"),
            "timestamp": record.timestamp,
            "success": record.success,
        }
        result.append(entry)
    return result
