"""Lightweight sentiment scoring for belief updates.

Pure function: given a text fragment, return a stance in [-1, 1]. Word lists
are shared with simswarm.adapter so platform-level sentiment and per-post
belief updates stay consistent.
"""
from __future__ import annotations

POSITIVE_WORDS = frozenset({
    "support", "approve", "praise", "welcome", "benefit", "success", "agree",
    "positive", "progress", "growth", "improve", "achieve", "gain", "boost",
    "encourage", "optimistic", "favorable", "advance", "strengthen", "celebrate",
    "endorse", "commend", "constructive", "prosper", "thrive", "cooperate",
    "alliance", "partnership", "diplomatic", "peaceful", "stable", "recovery",
    "innovation", "opportunity", "confident", "resolve", "protect", "invest",
    "expand", "lead", "unite", "embrace", "recommend", "affirm", "uphold",
    "champion", "reform", "empower", "sustain", "reliable",
})

NEGATIVE_WORDS = frozenset({
    "oppose", "condemn", "reject", "threaten", "crisis", "fail", "warn",
    "attack", "ban", "sanction", "conflict", "damage", "destroy", "collapse",
    "risk", "danger", "decline", "loss", "struggle", "tension", "hostile",
    "aggressive", "escalate", "violate", "disrupt", "undermine", "restrict",
    "protest", "controversy", "criticism", "backlash", "concern", "fear",
    "instability", "vulnerable", "deficit", "recession", "inflation", "corrupt",
    "exploit", "abuse", "negligence", "incompetent", "reckless", "toxic",
    "polarize", "divide", "obstruct", "retaliate", "assassinate",
})


def score_stance(text: str) -> float:
    """Return a stance score in [-1.0, 1.0] from keyword counts.

    +1.0 = fully positive, -1.0 = fully negative, 0 = neutral or mixed.
    Non-alphanumeric tokens are ignored; comparison is case-insensitive.
    """
    if not text:
        return 0.0

    tokens = [t.strip(".,!?;:\"'()-[]").lower() for t in text.split()]
    pos = sum(1 for t in tokens if t in POSITIVE_WORDS)
    neg = sum(1 for t in tokens if t in NEGATIVE_WORDS)
    total = pos + neg
    if total == 0:
        return 0.0
    return (pos - neg) / total
