"""Tests for the Anthropic Messages API adapter."""
from __future__ import annotations

import pytest

from saas.adapters.anthropic_client import AnthropicClient


def test_client_constructs_with_required_fields():
    c = AnthropicClient(api_key="test-key", model="claude-opus-4-6")
    assert c.model == "claude-opus-4-6"
    assert c.api_key == "test-key"
