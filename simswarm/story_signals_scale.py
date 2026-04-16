"""Sim-scale aggregates + disagreement-axis extraction.

Split out from story_signals.py to respect the repo's 300-line file cap.
Public API is re-exported via simswarm.story_signals for stable imports.
"""
from __future__ import annotations

from typing import Any

from simswarm.story_signals_constants import OPPOSED_SIGNALS, SUPPORT_SIGNALS


def compute_sim_scale(
    chat_log: list[dict[str, Any]],
    forecast_days: int,
    bloc_count: int,
) -> dict[str, Any]:
    """Honest sim-scale aggregates. Renames the old 'confidence' grid."""
    participants = len({a.get("agent_name", "") for a in chat_log if a.get("agent_name")})
    has_trade = any(
        a.get("action_type", "").lower() in ("buy_shares", "sell_shares", "buy", "sell")
        and a.get("success")
        for a in chat_log
    )
    return {
        "participants": participants,
        "horizon_days": forecast_days,
        "bloc_count": bloc_count,
        "market_stress": "present" if has_trade else "none_observed",
    }


def extract_disagreement_axis(chat_log: list[dict[str, Any]]) -> str:
    """Top keyword from opposed posts 'vs' top keyword from supports posts."""
    # Imported here to avoid a circular import: story_signals.py re-exports
    # us, and we use internal helpers from there.
    from simswarm.story_signals import _classify_stance, _post_text, _top_keywords

    opposed_texts: list[str] = []
    support_texts: list[str] = []
    for action in chat_log:
        if action.get("action_type", "").lower() not in ("create_post", "create_comment"):
            continue
        text = _post_text(action)
        stance = _classify_stance(text)
        if stance == "opposed":
            opposed_texts.append(text)
        elif stance == "supports":
            support_texts.append(text)

    # Filter stance vocabulary so the axis doesn't trivially become "support vs oppose".
    extra = OPPOSED_SIGNALS | SUPPORT_SIGNALS
    opposed_kw = _top_keywords(opposed_texts, limit=1, extra_stopwords=extra)
    support_kw = _top_keywords(support_texts, limit=1, extra_stopwords=extra)
    if opposed_kw and support_kw:
        return f"{support_kw[0]} vs {opposed_kw[0]}"
    return opposed_kw[0] if opposed_kw else (support_kw[0] if support_kw else "")
