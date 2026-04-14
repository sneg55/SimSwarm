"""Per-round and per-agent activity extractors.

engagement_summary aggregates by round, agent_trajectories by agent, profiles
emits one card per agent for the Data tab's profile grid.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from simswarm.extractor_common import (
    is_comment, is_like, is_post, post_text, score_sentiment,
)
from simswarm.types import ActionRecord


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
        if is_post(record.action_type):
            r["total_posts"] += 1
        elif is_like(record.action_type):
            r["total_likes"] += 1
        elif is_comment(record.action_type):
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
        if is_post(record.action_type) or is_comment(record.action_type):
            if is_post(record.action_type):
                rd["posts"] += 1
            content = post_text(record.action_args)
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
                "sentiment": score_sentiment(combined_text),
            })
        result.append({
            "agent_id": aid,
            "name": meta["name"],
            "rounds": rounds_list,
        })
    return result


def extract_profiles(chat_log: list[ActionRecord]) -> list[dict]:
    """Return one profile card per unique agent seen in the chat log.

    Output fields match what AgentProfileCards.vue reads: name + persona/bio.
    Persona is a one-line activity summary since the native engine doesn't
    ship personality traits — a short activity description beats an empty card.
    """
    if not chat_log:
        return []

    agg: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"name": "", "posts": 0, "actions": 0, "rounds": set(), "platforms": set()}
    )
    for record in chat_log:
        a = agg[record.agent_id]
        a["name"] = record.agent_name or a["name"]
        a["actions"] += 1
        a["rounds"].add(record.round_num)
        if record.platform:
            a["platforms"].add(record.platform)
        if is_post(record.action_type):
            a["posts"] += 1

    return [
        {
            "agent_id": aid,
            "name": data["name"] or aid,
            "persona": _profile_summary(data),
            "total_posts": data["posts"],
            "total_actions": data["actions"],
            "rounds_active": len(data["rounds"]),
            "platforms": sorted(data["platforms"]),
        }
        for aid, data in sorted(agg.items())
    ]


def _profile_summary(data: dict[str, Any]) -> str:
    platforms = sorted(data.get("platforms") or [])
    plat = f" on {', '.join(platforms)}" if platforms else ""
    rounds = len(data.get("rounds") or set())
    return (
        f"{data.get('posts', 0)} posts, {data.get('actions', 0)} actions "
        f"across {rounds} round{'' if rounds == 1 else 's'}{plat}."
    )


def agent_sentiment_from_trajectories(
    trajectories: list[dict],
) -> dict[str, float]:
    """Return {agent_id: mean_sentiment} from an agent-trajectory list.

    Sentiments are per-round scores from ``extract_agent_trajectories``.
    Agents with no rounds are skipped; missing per-round sentiment fields
    are treated as 0.0. Returned floats are NOT clamped.
    """
    result: dict[str, float] = {}
    for traj in trajectories:
        rounds = traj.get("rounds") or []
        if not rounds:
            continue
        total = sum(float(r.get("sentiment", 0.0)) for r in rounds)
        result[traj["agent_id"]] = round(total / len(rounds), 10)
    return result
