"""Tests for simswarm.story_signals.build_story_signals and helpers.

Populated progressively by Tasks 2-8. Task 1 ships a bare class so the file
is importable without carrying unused imports (ruff F401).
"""
from __future__ import annotations

from simswarm import story_signals
from tests.engine.story_signals_fixtures import make_chat_log


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


class TestExtractStakeholderPositions:
    def test_groups_opposed_agents(self):
        positions = story_signals.extract_stakeholder_positions(make_chat_log())
        opposed = next((p for p in positions if p["stance"] == "opposed"), None)
        assert opposed is not None
        assert "Morgan Stanley" in opposed["members"]
        assert "Microsoft" in opposed["members"]

    def test_groups_supportive_agents(self):
        positions = story_signals.extract_stakeholder_positions(make_chat_log())
        supportive = next((p for p in positions if p["stance"] == "supports"), None)
        assert supportive is not None
        assert "SEC" in supportive["members"]
        assert "Investor Advisory Committee" in supportive["members"]

    def test_position_has_required_keys(self):
        positions = story_signals.extract_stakeholder_positions(make_chat_log())
        assert positions
        for p in positions:
            assert set(p.keys()) >= {"name", "stance", "members", "member_count", "rationale_keywords"}

    def test_member_count_matches_members(self):
        positions = story_signals.extract_stakeholder_positions(make_chat_log())
        for p in positions:
            assert p["member_count"] == len(p["members"])

    def test_empty_chat_log_returns_empty_list(self):
        assert story_signals.extract_stakeholder_positions([]) == []

    def test_position_name_reflects_stance(self):
        positions = story_signals.extract_stakeholder_positions(make_chat_log())
        names = {p["name"] for p in positions}
        assert any("oppos" in n.lower() or "against" in n.lower() or "industry" in n.lower() for n in names) \
            or any("support" in n.lower() or "regulator" in n.lower() or "transparency" in n.lower() for n in names)

    def test_tied_agent_resolves_to_split(self):
        """An agent with equal opposed+supports posts lands in split, not whichever came first."""
        tied_log = [
            {"round_num": 1, "agent_id": "a", "agent_name": "Tied",
             "action_type": "CREATE_POST", "platform": "twitter",
             "action_args": {"text": "We oppose prescriptive mandates."},
             "timestamp": None, "success": True},
            {"round_num": 2, "agent_id": "a", "agent_name": "Tied",
             "action_type": "CREATE_POST", "platform": "twitter",
             "action_args": {"text": "We endorse standardized frameworks."},
             "timestamp": None, "success": True},
        ]
        positions = story_signals.extract_stakeholder_positions(tied_log)
        split_bucket = next((p for p in positions if p["stance"] == "split"), None)
        assert split_bucket is not None
        assert "Tied" in split_bucket["members"]

    def test_rationale_keywords_exclude_stance_words(self):
        """Stance keywords like 'oppose', 'prescriptive' must not dominate rationale output."""
        positions = story_signals.extract_stakeholder_positions(make_chat_log())
        opposed = next((p for p in positions if p["stance"] == "opposed"), None)
        assert opposed is not None
        # stance keywords that appear in the opposed bloc's posts but should be filtered
        assert "oppose" not in opposed["rationale_keywords"]
        assert "prescriptive" not in opposed["rationale_keywords"]
