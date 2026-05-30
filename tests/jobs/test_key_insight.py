"""Tests for _derive_key_insight — sources from LLM verdict with heuristic fallback."""
from __future__ import annotations

from saas.jobs.persistence import _derive_key_insight


class TestDeriveKeyInsight:
    def test_key_insight_comes_from_verdict_field(self):
        assert _derive_key_insight(
            verdict="Unlikely to pass — 3 of 5 blocs opposed.",
            report_markdown="## Executive Summary\nSomething else.",
        ) == "Unlikely to pass — 3 of 5 blocs opposed."

    def test_key_insight_falls_back_to_first_non_heading_when_verdict_empty(self):
        md = "## Executive Summary\nSome fallback insight over 30 characters long."
        assert _derive_key_insight(verdict="", report_markdown=md).startswith("Some fallback")

    def test_key_insight_truncates_verdict_at_200_chars(self):
        long_verdict = "a" * 300
        assert len(_derive_key_insight(verdict=long_verdict, report_markdown="")) == 200

    def test_key_insight_returns_none_when_both_empty(self):
        assert _derive_key_insight(verdict="", report_markdown="") is None

    def test_whitespace_only_verdict_falls_back(self):
        md = "## Executive Summary\nA decent fallback that is over thirty chars for sure."
        result = _derive_key_insight(verdict="   \n  ", report_markdown=md)
        assert result is not None
        assert "fallback" in result.lower()
