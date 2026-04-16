"""Deterministic extraction of Story signals from chat_log + graph_data.

Pure functions only. No LLM calls, no I/O. The output feeds both the Story
view directly and the report.j2 prompt as grounding context.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any

from simswarm.extractor_common import post_text as _extractor_post_text
from simswarm.story_signals_constants import (
    COALITION_LABEL as _COALITION_LABEL,
    OPPOSED_SIGNALS,
    SLOT_COLORS,  # re-exported for saas.jobs.report consumers  # noqa: F401
    STANCE_BLOC_NAME as _STANCE_BLOC_NAME,
    SUPPORT_SIGNALS,
)
from simswarm.story_signals_scale import (  # noqa: F401 — public re-export
    compute_sim_scale,
    extract_disagreement_axis,
)


def _classify_stance(text: str) -> str:
    """Return 'opposed' | 'supports' | 'neutral' | 'split' based on keyword signals."""
    lowered = text.lower()
    has_opposed = any(kw in lowered for kw in OPPOSED_SIGNALS)
    has_support = any(kw in lowered for kw in SUPPORT_SIGNALS)
    if has_opposed and has_support:
        return "split"
    if has_opposed:
        return "opposed"
    if has_support:
        return "supports"
    return "neutral"


def _post_text(action: dict[str, Any]) -> str:
    """Defensive accessor for post body text; delegates to extractor_common."""
    return _extractor_post_text(action.get("action_args"))


def _agent_dominant_stance(agent_posts: list[dict[str, Any]]) -> str:
    """A single agent's overall stance = majority stance across their posts.

    Ties between directional stances resolve to "split" rather than being
    order-dependent.
    """
    if not agent_posts:
        return "neutral"
    counts = Counter(_classify_stance(_post_text(p)) for p in agent_posts)
    # Drop neutral when any directional stance exists — neutral shouldn't win by default.
    directional = {k: v for k, v in counts.items() if k != "neutral"}
    if directional:
        top_count = max(directional.values())
        top_stances = [k for k, v in directional.items() if v == top_count]
        if len(top_stances) > 1:
            return "split"
        return top_stances[0]
    return "neutral"


def _top_keywords(
    texts: list[str],
    limit: int = 3,
    extra_stopwords: frozenset[str] = frozenset(),
) -> list[str]:
    """Top non-stopword tokens across a bag of texts.

    `extra_stopwords` lets callers exclude domain-specific tokens they don't
    want dominating the output — e.g., stance words when naming a bloc's
    rationale, so "oppose" doesn't become the top keyword for an opposed
    bloc.
    """
    stopwords = {"the", "a", "an", "is", "are", "to", "of", "for", "and", "or",
                 "in", "on", "we", "our", "this", "that", "it", "be", "by",
                 "with", "as", "at", "from", "will", "not", "but"}
    stopwords |= set(extra_stopwords)
    tokens: Counter[str] = Counter()
    for t in texts:
        for word in re.findall(r"[a-z][a-z\-]{3,}", t.lower()):
            if word not in stopwords:
                tokens[word] += 1
    return [w for w, _ in tokens.most_common(limit)]


def extract_stakeholder_positions(chat_log: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Cluster agents by dominant stance and return stakeholder position dicts."""
    posts_by_agent: dict[str, list[dict]] = defaultdict(list)
    for action in chat_log:
        if action.get("action_type") in ("CREATE_POST", "CREATE_COMMENT"):
            posts_by_agent[action.get("agent_name", "")].append(action)

    agent_stances: dict[str, str] = {
        name: _agent_dominant_stance(posts) for name, posts in posts_by_agent.items() if name
    }

    buckets: dict[str, list[str]] = defaultdict(list)
    for name, stance in agent_stances.items():
        buckets[stance].append(name)

    positions: list[dict[str, Any]] = []
    for stance, members in buckets.items():
        if not members:
            continue
        bucket_texts: list[str] = []
        for name in members:
            bucket_texts.extend(_post_text(p) for p in posts_by_agent[name])
        positions.append({
            "name": _STANCE_BLOC_NAME[stance],
            "stance": stance,
            "members": sorted(members),
            "member_count": len(members),
            "rationale_keywords": _top_keywords(
                bucket_texts, limit=3,
                extra_stopwords=OPPOSED_SIGNALS | SUPPORT_SIGNALS,
            ),
        })
    # Stable order: opposed, supports, split, neutral
    order = {"opposed": 0, "supports": 1, "split": 2, "neutral": 3}
    positions.sort(key=lambda p: order.get(p["stance"], 99))
    return positions


def name_coalitions(positions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Promote stakeholder_positions with ≥2 members to named coalitions."""
    coalitions: list[dict[str, Any]] = []
    for p in positions:
        if p["member_count"] < 2:
            continue
        # Prefer a keyword-derived name when rationale keywords are present;
        # fall back to stance label.
        kw = p.get("rationale_keywords") or []
        if kw:
            name = f"{kw[0].capitalize()}-focused {p['stance']} group"
        else:
            name = _COALITION_LABEL.get(p["stance"], "Group")
        coalitions.append({
            "name": name,
            "members": list(p["members"]),
            "size": p["member_count"],
            "stance": p["stance"],
        })
    return coalitions


def _days_to_week_range(day_start: int, day_end: int) -> str:
    """Render a day-range as 'Week N' or 'Weeks N-M'. 1-indexed."""
    week_start = max(1, (day_start + 6) // 7)
    week_end = max(1, (day_end + 6) // 7)
    if week_start == week_end:
        return f"Week {week_start}"
    return f"Weeks {week_start}-{week_end}"


def extract_phase_boundaries(
    chat_log: list[dict[str, Any]],
    forecast_days: int,
) -> list[dict[str, Any]]:
    """Chunk simulation into thirds (or one 'Full horizon' if <3 rounds)."""
    max_round = max((a.get("round_num", 0) for a in chat_log), default=0)

    if max_round < 3:
        topics = _top_keywords([_post_text(a) for a in chat_log], limit=1)
        return [{
            "phase": "Full horizon",
            "rounds": [1, max(1, max_round)],
            "week_range": _days_to_week_range(1, forecast_days),
            "dominant_topic": topics[0] if topics else "",
        }]

    labels = ["Early", "Mid", "Late"]
    third = max_round / 3
    phases: list[dict[str, Any]] = []
    for i, label in enumerate(labels):
        r_start = int(i * third) + 1
        r_end = int((i + 1) * third) if i < 2 else max_round
        d_start = int(i * forecast_days / 3) + 1
        d_end = int((i + 1) * forecast_days / 3) if i < 2 else forecast_days
        bucket = [a for a in chat_log if r_start <= a.get("round_num", 0) <= r_end]
        topics = _top_keywords([_post_text(a) for a in bucket], limit=1)
        phases.append({
            "phase": label,
            "rounds": [r_start, r_end],
            "week_range": _days_to_week_range(d_start, d_end),
            "dominant_topic": topics[0] if topics else "",
        })
    return phases


def _role_map(graph_data: dict[str, Any]) -> dict[str, str]:
    """Map agent_name → first non-'Entity' label from graph nodes, for role chips."""
    roles: dict[str, str] = {}
    for node in graph_data.get("nodes", []):
        name = node.get("name", "")
        labels = [lab for lab in node.get("labels", []) if lab and lab != "Entity"]
        if name and labels:
            roles[name] = labels[0]
    return roles


def _phase_for_round(round_num: int, phases: list[dict]) -> str:
    for p in phases:
        r_start, r_end = p["rounds"]
        if r_start <= round_num <= r_end:
            return p["phase"]
    return phases[0]["phase"] if phases else ""


def _engagement_for_post(
    post: dict[str, Any],
    chat_log: list[dict[str, Any]],
) -> int:
    """Heuristic engagement: count LIKE_POST / REPOST actions targeting this post.

    Target matching uses agent_id + round_num prefix in target_post field,
    which is the convention the extractor produces (e.g., "ms_r8").
    """
    agent = post.get("agent_id", "")
    round_num = post.get("round_num", 0)
    target_marker = f"{agent}_r{round_num}"
    count = 0
    for action in chat_log:
        if action.get("action_type") in ("LIKE_POST", "REPOST"):
            target = (action.get("action_args") or {}).get("target_post", "")
            if target_marker in target:
                count += 1
    return count


def extract_quotable_posts(
    chat_log: list[dict[str, Any]],
    phases: list[dict[str, Any]],
    graph_data: dict[str, Any],
) -> list[dict[str, Any]]:
    """Top-engagement post per phase per stance, deduped by agent."""
    roles = _role_map(graph_data)
    posts = [a for a in chat_log if a.get("action_type") == "CREATE_POST"]

    # Group candidates by (phase, stance)
    candidates: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for post in posts:
        text = _post_text(post)
        if not text:
            continue
        phase = _phase_for_round(post.get("round_num", 0), phases)
        stance = _classify_stance(text)
        candidates[(phase, stance)].append(post)

    selected: list[dict[str, Any]] = []
    seen_agents: set[str] = set()
    for (phase, stance), posts_list in candidates.items():
        posts_list.sort(key=lambda p: _engagement_for_post(p, chat_log), reverse=True)
        for post in posts_list:
            name = post.get("agent_name", "")
            if name and name not in seen_agents:
                seen_agents.add(name)
                selected.append({
                    "agent_name": name,
                    "agent_role": roles.get(name, ""),
                    "phase": phase,
                    "text": _post_text(post),
                    "engagement": _engagement_for_post(post, chat_log),
                })
                break
    return selected


def build_story_signals(
    chat_log: list[dict[str, Any]],
    graph_data: dict[str, Any],
    forecast_days: int,
) -> dict[str, Any]:
    """Top-level entry. Returns the deterministic signals dict.

    Args:
        chat_log: List of dicts matching the ActionRecord schema serialized
            to MinIO (i.e., already-parsed JSON). Each row has keys
            round_num, agent_id, agent_name, action_type, platform,
            action_args, timestamp, success. Post body lives at
            action_args["text"] (or action_args["content"] for legacy rows).
        graph_data: {"nodes": [...], "edges": [...], "metadata": {...}} dict.
        forecast_days: User-chosen horizon from JobCreate; required.
    """
    positions = extract_stakeholder_positions(chat_log)
    named = name_coalitions(positions)
    phases = extract_phase_boundaries(chat_log, forecast_days)
    quotes = extract_quotable_posts(chat_log, phases, graph_data)
    axis = extract_disagreement_axis(chat_log)
    scale = compute_sim_scale(chat_log, forecast_days, bloc_count=len(named))
    return {
        "stakeholder_positions": positions,
        "named_coalitions": named,
        "phase_boundaries": phases,
        "quotable_posts": quotes,
        "disagreement_axis": axis,
        "sim_scale": scale,
    }
