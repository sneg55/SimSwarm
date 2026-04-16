"""Named constants for story_signals — stance keyword sets, slot colors, labels.

Kept in a dedicated module so story_signals.py stays focused on extraction
logic and stays within the 300-line budget.
"""
from __future__ import annotations

# Curated stance-signal keyword sets. Extracted from a corpus of prod goals
# (policy/markets/crisis/competitive/public-opinion verticals). These are
# intentionally conservative — a post that triggers neither set is neutral.
OPPOSED_SIGNALS: frozenset[str] = frozenset({
    "oppose", "against", "reject", "block", "resist", "pushback",
    "overreach", "mandate", "prescriptive", "burden", "compliance cost",
    "unworkable", "chilling", "harmful",
})

SUPPORT_SIGNALS: frozenset[str] = frozenset({
    "support", "endorse", "align with", "back the", "welcome", "approve",
    "transparency", "accountability", "standardized", "enforce",
    "strengthen", "clarity",
})

# Phase accent colors — aligned with tailwind.config.js tokens. Public so
# saas/jobs/report.py can tag LLM-produced findings with the correct hex
# without duplicating the mapping.
SLOT_COLORS: dict[str, str] = {
    "industry":      "#F97316",  # coral-amber
    "regulator":     "#22D3EE",  # ocean-glow
    "intermediary":  "#A78BFA",  # organic-violet
    "market":        "#6EE7B7",  # organic-seafoam
    "turning_point": "#FF6B6B",  # coral
}

STANCE_BLOC_NAME: dict[str, str] = {
    "opposed":  "Opposition bloc",
    "supports": "Support bloc",
    "neutral":  "Neutral bloc",
    "split":    "Split bloc",
}

COALITION_LABEL: dict[str, str] = {
    "opposed":  "Opposition alignment",
    "supports": "Support alignment",
    "split":    "Mixed-stance group",
    "neutral":  "Neutral observers",
}
