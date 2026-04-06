"""
Module-level constants for the GPU worker job runner.
"""

VLLM_URL = "http://localhost:8000/v1"
MIROSHARK_BACKEND = "/app/miroshark/backend"

# ---------------------------------------------------------------------------
# Sentiment word sets
# ---------------------------------------------------------------------------

POSITIVE_WORDS = {
    "support", "approve", "praise", "welcome", "benefit", "success", "agree",
    "positive", "progress", "growth", "improve", "achieve", "gain", "boost",
    "encourage", "optimistic", "favorable", "advance", "strengthen", "celebrate",
    "endorse", "commend", "constructive", "prosper", "thrive", "cooperate",
    "alliance", "partnership", "diplomatic", "peaceful", "stable", "recovery",
    "innovation", "opportunity", "confident", "resolve", "protect", "invest",
    "expand", "lead", "unite", "embrace", "recommend", "affirm", "uphold",
    "champion", "reform", "empower", "sustain", "reliable",
}

NEGATIVE_WORDS = {
    "oppose", "condemn", "reject", "threaten", "crisis", "fail", "warn",
    "attack", "ban", "sanction", "conflict", "damage", "destroy", "collapse",
    "risk", "danger", "decline", "loss", "struggle", "tension", "hostile",
    "aggressive", "escalate", "violate", "disrupt", "undermine", "restrict",
    "protest", "controversy", "criticism", "backlash", "concern", "fear",
    "instability", "vulnerable", "deficit", "recession", "inflation", "corrupt",
    "exploit", "abuse", "negligence", "incompetent", "reckless", "toxic",
    "polarize", "divide", "obstruct", "retaliate", "assassinate",
}

# ---------------------------------------------------------------------------
# Finding accent colors
# ---------------------------------------------------------------------------

FINDING_COLORS = ["#22D3EE", "#A78BFA", "#F97316", "#6EE7B7", "#FF6B6B", "#FBBF24"]
