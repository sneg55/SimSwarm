"""Sentiment scoring for belief updates using VADER.

Pure function: given a text fragment, return a stance in [-1, 1].
Uses VADER's compound score, which handles negation, intensifiers,
and punctuation. Already pinned in pyproject.toml (vaderSentiment==3.3.2)
and warmed in the worker Dockerfile.
"""
from __future__ import annotations

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_VADER = SentimentIntensityAnalyzer()


def score_stance(text: str) -> float:
    """Return a stance score in [-1.0, 1.0] from VADER's compound score."""
    if not text:
        return 0.0
    return _VADER.polarity_scores(text)["compound"]
