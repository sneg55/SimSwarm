"""Tests for simswarm.story_signals.build_story_signals and helpers."""
from __future__ import annotations

import pytest

from simswarm import story_signals
from tests.engine.story_signals_fixtures import make_chat_log, make_graph_data


class TestBuildStorySignals:
    def test_returns_expected_top_level_keys(self):
        pytest.skip("implemented in Task 8")
