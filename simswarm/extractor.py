"""Rich simulation data extractor.

Extracts posts, engagement metrics, agent trajectories, social graph, and
market trades from the engine's ActionRecord chat log.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from simswarm.adapter import NEGATIVE_WORDS, POSITIVE_WORDS
from simswarm.types import ActionRecord

# ---------------------------------------------------------------------------
# Action-type sets (case-insensitive comparison used throughout)
# ---------------------------------------------------------------------------

_POST_TYPES = {"create_post", "CREATE_POST"}
_LIKE_TYPES = {"like_post", "LIKE_POST", "like"}
_COMMENT_TYPES = {"create_comment", "CREATE_COMMENT", "comment"}
_FOLLOW_TYPES = {"follow", "FOLLOW"}
_TRADE_TYPES = {"buy_shares", "BUY_SHARES", "sell_shares", "SELL_SHARES"}


def _is_post(action_type: str) -> bool:
    return action_type.lower() == "create_post"


def _is_like(action_type: str) -> bool:
    return action_type.lower() == "like_post"


def _is_comment(action_type: str) -> bool:
    return action_type.lower() == "create_comment"


def _is_follow(action_type: str) -> bool:
    return action_type.lower() == "follow"


def _is_trade(action_type: str) -> bool:
    return action_type.lower() in ("buy_shares", "sell_shares")


# ---------------------------------------------------------------------------
# Public extraction functions
# ---------------------------------------------------------------------------


def extract_posts(chat_log: list[ActionRecord]) -> list[dict]:
    """Return post records from the chat log.

    Filters create_post / CREATE_POST actions and returns dicts with:
    agent_id, agent_name, platform, content, round_num, action_type, timestamp.
    """
    result = []
    for record in chat_log:
        if not _is_post(record.action_type):
            continue
        result.append({
            "agent_id": record.agent_id,
            "agent_name": record.agent_name,
            "platform": record.platform,
            "content": record.action_args.get("content", ""),
            "round_num": record.round_num,
            "action_type": record.action_type,
            "timestamp": record.timestamp,
            "success": record.success,
        })
    return result


def extract_engagement_summary(chat_log: list[ActionRecord]) -> list[dict]:
    """Return per-round engagement metrics.

    Each entry: round, total_posts, total_likes, total_comments, active_agents.
    """
    if not chat_log:
        return []

    rounds: dict[int, dict[str, Any]] = defaultdict(
        lambda: {"total_posts": 0, "total_likes": 0, "total_comments": 0, "agents": set()}
    )

    for record in chat_log:
        r = rounds[record.round_num]
        r["agents"].add(record.agent_id)
        if _is_post(record.action_type):
            r["total_posts"] += 1
        elif _is_like(record.action_type):
            r["total_likes"] += 1
        elif _is_comment(record.action_type):
            r["total_comments"] += 1

    return [
        {
            "round": rnum,
            "total_posts": data["total_posts"],
            "total_likes": data["total_likes"],
            "total_comments": data["total_comments"],
            "active_agents": len(data["agents"]),
        }
        for rnum, data in sorted(rounds.items())
    ]


def extract_agent_trajectories(chat_log: list[ActionRecord]) -> list[dict]:
    """Return per-agent activity over rounds.

    Each entry: agent_id, name, rounds (list of {round, posts, actions, sentiment}).
    Sentiment is scored from post/comment content using keyword matching.
    """
    if not chat_log:
        return []

    # agent_id -> round_num -> accumulator
    agents: dict[str, dict[str, Any]] = {}
    round_data: dict[str, dict[int, dict[str, Any]]] = defaultdict(
        lambda: defaultdict(lambda: {"posts": 0, "actions": 0, "texts": []})
    )

    for record in chat_log:
        aid = record.agent_id
        if aid not in agents:
            agents[aid] = {"name": record.agent_name}

        rd = round_data[aid][record.round_num]
        rd["actions"] += 1
        if _is_post(record.action_type):
            rd["posts"] += 1
            content = record.action_args.get("content", "")
            if content:
                rd["texts"].append(content)
        elif _is_comment(record.action_type):
            content = record.action_args.get("content", "")
            if content:
                rd["texts"].append(content)

    result = []
    for aid, meta in agents.items():
        rounds_list = []
        for rnum, rd in sorted(round_data[aid].items()):
            combined_text = " ".join(rd["texts"])
            rounds_list.append({
                "round": rnum,
                "posts": rd["posts"],
                "actions": rd["actions"],
                "sentiment": _score_sentiment(combined_text),
            })
        result.append({
            "agent_id": aid,
            "name": meta["name"],
            "rounds": rounds_list,
        })
    return result


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
        if not _is_follow(record.action_type):
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

    # Detect mutual follows (A→B and B→A)
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
        if not _is_trade(record.action_type):
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


# ---------------------------------------------------------------------------
# Sentiment helper
# ---------------------------------------------------------------------------


def _score_sentiment(text: str) -> float:
    """Keyword-based sentiment score in [-1.0, 1.0].

    Counts positive and negative word hits (case-insensitive), normalises by
    total word count.  Returns 0.0 for empty text.
    """
    if not text:
        return 0.0

    words = text.lower().split()
    if not words:
        return 0.0

    pos = sum(1 for w in words if w.strip(".,!?;:\"'") in POSITIVE_WORDS)
    neg = sum(1 for w in words if w.strip(".,!?;:\"'") in NEGATIVE_WORDS)
    total = len(words)

    raw = (pos - neg) / total
    # Clamp to [-1.0, 1.0]
    return max(-1.0, min(1.0, raw))
