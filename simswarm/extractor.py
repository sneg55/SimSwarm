"""Rich simulation data extractor (public API).

Extracts posts, engagement metrics, agent trajectories, social graph, market
trades, and agent profiles from the engine's ActionRecord chat log. This
module re-exports the extractors defined in the extractor_* sibling modules
so callers continue to import from `simswarm.extractor`.
"""
from __future__ import annotations

from simswarm.extractor_activity import (
    extract_agent_trajectories,
    extract_engagement_summary,
    extract_profiles,
)
from simswarm.extractor_common import score_sentiment as _score_sentiment
from simswarm.extractor_market_social import extract_market_data, extract_social_graph
from simswarm.extractor_posts import extract_posts, extract_top_posts

__all__ = [
    "extract_agent_trajectories",
    "extract_engagement_summary",
    "extract_market_data",
    "extract_posts",
    "extract_profiles",
    "extract_social_graph",
    "extract_top_posts",
    "_score_sentiment",
]
