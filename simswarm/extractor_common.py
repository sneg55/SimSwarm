"""Shared helpers for extractor submodules.

Action-type predicates and the keyword-based sentiment scorer live here so the
posts/activity/market submodules can stay focused on their own concerns.
"""
from __future__ import annotations

from simswarm.adapter import NEGATIVE_WORDS, POSITIVE_WORDS


def post_text(action_args: dict | None) -> str:
    """Return the post body text from an ActionRecord's action_args.

    The native social environment stores post bodies under the ``text`` key
    (see simswarm/environments/social.py:_handle_create_post) but older
    fixtures and some tests use ``content``. Check both, preferring ``text``
    since that is what production records actually contain.
    """
    if not action_args:
        return ""
    return str(action_args.get("text") or action_args.get("content") or "")


# Case-insensitive predicates over ActionRecord.action_type. Keep these cheap
# and pure — every extractor iterates the full chat log at least once.

def is_post(action_type: str) -> bool:
    return action_type.lower() == "create_post"


def is_like(action_type: str) -> bool:
    return action_type.lower() == "like_post"


def is_comment(action_type: str) -> bool:
    return action_type.lower() == "create_comment"


def is_follow(action_type: str) -> bool:
    return action_type.lower() == "follow"


def is_trade(action_type: str) -> bool:
    return action_type.lower() in ("buy_shares", "sell_shares")


def score_sentiment(text: str) -> float:
    """Keyword-based sentiment score in [-1.0, 1.0].

    Counts positive and negative word hits (case-insensitive), normalises by
    total word count. Returns 0.0 for empty text.
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
    return max(-1.0, min(1.0, raw))
