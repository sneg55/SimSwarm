"""Tests for extract_posts and _score_sentiment."""
from __future__ import annotations

import pytest

from simswarm.extractor import _score_sentiment, extract_posts
from tests.engine.extractor_fixtures import SAMPLE_LOG


class TestExtractPosts:
    def test_returns_list_of_dicts(self):
        result = extract_posts(SAMPLE_LOG)
        assert isinstance(result, list)
        assert all(isinstance(p, dict) for p in result)

    def test_only_post_actions_returned(self):
        result = extract_posts(SAMPLE_LOG)
        for p in result:
            assert "post" in p["action_type"].lower()

    def test_correct_post_count(self):
        # create_post/CREATE_POST: alice r1, bob r1, bob r2, dave r3 (failed) = 4
        result = extract_posts(SAMPLE_LOG)
        assert len(result) == 4

    def test_includes_required_fields(self):
        post = extract_posts(SAMPLE_LOG)[0]
        for field in ("agent_id", "agent_name", "platform", "content", "round_num"):
            assert field in post

    def test_content_extracted_from_action_args(self):
        contents = [p["content"] for p in extract_posts(SAMPLE_LOG)]
        assert "Support the new trade deal — great opportunity!" in contents

    def test_round_num_preserved(self):
        posts = {p["content"]: p for p in extract_posts(SAMPLE_LOG)}
        assert posts["Support the new trade deal — great opportunity!"]["round_num"] == 1
        assert posts["Recovery looking good — progress on all fronts."]["round_num"] == 2

    def test_case_insensitive_action_type_matching(self):
        # Both "create_post" and "CREATE_POST" should be included
        result = extract_posts(SAMPLE_LOG)
        agent_names = [p["agent_name"] for p in result]
        assert "Alice" in agent_names
        assert "Bob" in agent_names

    def test_timestamp_included_when_present(self):
        result = extract_posts(SAMPLE_LOG)
        first = next(p for p in result if p["agent_name"] == "Alice" and p["round_num"] == 1)
        assert first["timestamp"] == "2026-04-08T10:00:00Z"

    def test_empty_log_returns_empty_list(self):
        assert extract_posts([]) == []


class TestScoreSentiment:
    def test_positive_text_gives_positive_score(self):
        score = _score_sentiment("support the new policy, great progress and growth")
        assert score > 0.0

    def test_negative_text_gives_negative_score(self):
        score = _score_sentiment("oppose and condemn the crisis, danger and conflict")
        assert score < 0.0

    def test_neutral_text_gives_zero_score(self):
        score = _score_sentiment("the quick brown fox jumps over the lazy dog")
        assert score == 0.0

    def test_score_within_range(self):
        for text in [
            "great growth progress success",
            "danger conflict risk crisis",
            "",
        ]:
            assert -1.0 <= _score_sentiment(text) <= 1.0

    def test_empty_string_returns_zero(self):
        assert _score_sentiment("") == 0.0
