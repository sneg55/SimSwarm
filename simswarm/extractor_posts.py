"""Post extractors: raw posts + ranked top-posts feed.

Both produce input for the frontend Data tab. `extract_top_posts` is what
the post-MiroShark runner was missing — without it the DataDashboard renders
"No posts available" for every job.
"""
from __future__ import annotations

from collections import defaultdict

from simswarm.extractor_common import is_post, post_text
from simswarm.types import ActionRecord


def extract_posts(chat_log: list[ActionRecord]) -> list[dict]:
    """Return post records from the chat log.

    Filters create_post / CREATE_POST actions and returns dicts with:
    agent_id, agent_name, platform, content, round_num, action_type, timestamp.
    """
    result = []
    for record in chat_log:
        if not is_post(record.action_type):
            continue
        result.append({
            "agent_id": record.agent_id,
            "agent_name": record.agent_name,
            "platform": record.platform,
            "content": post_text(record.action_args),
            "round_num": record.round_num,
            "action_type": record.action_type,
            "timestamp": record.timestamp,
            "success": record.success,
        })
    return result


def extract_top_posts(chat_log: list[ActionRecord], limit: int = 20) -> list[dict]:
    """Return posts ranked by engagement with TopPostsFeed-friendly fields.

    Engagement = likes + comments + reposts targeting each post. We first
    stamp every post with a stable post_id (preferring an explicit
    `post_id` in the create action's args, else synthesising one from
    agent+round+index), then tally likes/comments/reposts whose
    `post_id`/`target_id` arg matches.
    """
    ids_by_post: dict[int, str] = {}
    posts: list[dict] = []
    synth_counter = 0
    for record in chat_log:
        if not is_post(record.action_type):
            continue
        args = record.action_args or {}
        explicit = args.get("post_id") or args.get("id")
        pid = str(explicit) if explicit else f"{record.agent_id}-r{record.round_num}-{synth_counter}"
        synth_counter += 1
        ids_by_post[id(record)] = pid
        posts.append({
            "post_id": pid,
            "agent_id": record.agent_id,
            "agent_name": record.agent_name,
            "platform": record.platform,
            "content": post_text(args),
            "round_num": record.round_num,
            "timestamp": record.timestamp,
            "num_likes": 0,
            "num_shares": 0,
            "num_dislikes": 0,
            "engagement": 0,
        })

    if not posts:
        return []

    likes: dict[str, int] = defaultdict(int)
    dislikes: dict[str, int] = defaultdict(int)
    shares: dict[str, int] = defaultdict(int)
    comments: dict[str, int] = defaultdict(int)
    for record in chat_log:
        args = record.action_args or {}
        target = str(args.get("post_id") or args.get("target_id") or "")
        if not target:
            continue
        t = record.action_type.lower()
        if t in ("like_post", "like"):
            likes[target] += 1
        elif t == "vote":
            # Native social env encodes vote direction in args["value"]:
            # +1 is a like, -1 is a dislike. See environments/social.py:142.
            try:
                value = int(args.get("value", 0))
            except (TypeError, ValueError):
                value = 0
            if value > 0:
                likes[target] += 1
            elif value < 0:
                dislikes[target] += 1
        elif t in ("repost", "retweet", "share"):
            shares[target] += 1
        elif t in ("create_comment", "comment", "reply"):
            comments[target] += 1

    for p in posts:
        pid = p["post_id"]
        p["num_likes"] = likes.get(pid, 0)
        p["num_dislikes"] = dislikes.get(pid, 0)
        p["num_shares"] = shares.get(pid, 0) + comments.get(pid, 0)
        p["engagement"] = p["num_likes"] + p["num_shares"]

    posts.sort(key=lambda p: p["engagement"], reverse=True)
    return posts[:limit]
