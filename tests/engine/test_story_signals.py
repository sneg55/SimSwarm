"""Tests for simswarm.story_signals.build_story_signals and helpers.

Populated progressively by Tasks 2-8. Task 1 ships a bare class so the file
is importable without carrying unused imports (ruff F401).
"""
from __future__ import annotations

from simswarm import story_signals


class TestBuildStorySignals:
    """Placeholder — filled in by Task 8 once build_story_signals is wired up."""
    pass


class TestClassifyStance:
    def test_opposed_keyword_returns_opposed(self):
        assert story_signals._classify_stance("we oppose this") == "opposed"

    def test_support_keyword_returns_supports(self):
        assert story_signals._classify_stance("we endorse standardized rules") == "supports"

    def test_no_keyword_returns_neutral(self):
        assert story_signals._classify_stance("the sky is blue") == "neutral"

    def test_both_keywords_returns_split(self):
        assert story_signals._classify_stance("we oppose prescriptive rules but support transparency") == "split"

    def test_case_insensitive(self):
        assert story_signals._classify_stance("WE OPPOSE THIS") == "opposed"
