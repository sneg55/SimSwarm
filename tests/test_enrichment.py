"""Tests for seed enrichment via xAI search."""
import os
import sys
from unittest.mock import MagicMock

import pytest


def _make_openai_mock():
    """Return a (module_mock, OpenAI_class_mock) pair injected into sys.modules."""
    openai_mod = MagicMock()
    openai_cls = MagicMock()
    openai_mod.OpenAI = openai_cls
    return openai_mod, openai_cls


def _make_mock_response(text, citations=None):
    """Build a mock xAI response with the correct output structure."""
    response = MagicMock()
    response.output_text = text

    annotations = []
    for c in (citations or []):
        ann = MagicMock()
        ann.url = c["url"]
        ann.title = c.get("title", "")
        annotations.append(ann)

    content_item = MagicMock()
    content_item.annotations = annotations

    message_item = MagicMock()
    message_item.content = [content_item]

    search_item = MagicMock()
    search_item.content = []

    response.output = [search_item, message_item]
    return response


def test_enrich_seed_returns_none_when_no_api_key(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "")
    from saas.workers.enrichment import enrich_seed
    result = enrich_seed("some seed", "some goal")
    assert result is None


def test_enrich_seed_returns_none_on_api_error(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "test-key")
    openai_mod, openai_cls = _make_openai_mock()
    openai_cls.return_value.responses.create.side_effect = Exception("API error")
    monkeypatch.setitem(sys.modules, "openai", openai_mod)

    from saas.workers.enrichment import enrich_seed
    result = enrich_seed("some seed", "some goal")
    assert result is None


def test_enrich_seed_returns_result_with_citations(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "test-key")
    openai_mod, openai_cls = _make_openai_mock()

    mock_response = _make_mock_response(
        "Research summary about the topic.",
        [
            {"url": "https://example.com/1", "title": "Source 1"},
            {"url": "https://example.com/2", "title": "Source 2"},
        ],
    )
    openai_cls.return_value.responses.create.return_value = mock_response
    monkeypatch.setitem(sys.modules, "openai", openai_mod)

    from saas.workers.enrichment import enrich_seed
    result = enrich_seed("seed text", "research goal")

    assert result is not None
    assert result.summary == "Research summary about the topic."
    assert len(result.citations) == 2
    assert result.citations[0]["url"] == "https://example.com/1"
    assert result.citations[1]["title"] == "Source 2"


def test_enrich_seed_deduplicates_citation_urls(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "test-key")
    openai_mod, openai_cls = _make_openai_mock()

    mock_response = _make_mock_response(
        "Summary with repeated sources.",
        [
            {"url": "https://example.com/same", "title": "A"},
            {"url": "https://example.com/same", "title": "A again"},
            {"url": "https://example.com/other", "title": "B"},
        ],
    )
    openai_cls.return_value.responses.create.return_value = mock_response
    monkeypatch.setitem(sys.modules, "openai", openai_mod)

    from saas.workers.enrichment import enrich_seed
    result = enrich_seed("seed", "goal")

    assert result is not None
    assert len(result.citations) == 2  # deduped


def test_enrich_seed_returns_none_on_empty_summary(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "test-key")
    openai_mod, openai_cls = _make_openai_mock()

    mock_response = _make_mock_response("", [])
    openai_cls.return_value.responses.create.return_value = mock_response
    monkeypatch.setitem(sys.modules, "openai", openai_mod)

    from saas.workers.enrichment import enrich_seed
    result = enrich_seed("seed", "goal")
    assert result is None


@pytest.mark.skipif(
    not os.getenv("XAI_API_KEY"),
    reason="XAI_API_KEY not set — skipping live API test",
)
def test_enrich_seed_live_api():
    """End-to-end test against real xAI API. Only runs when XAI_API_KEY is set."""
    from saas.workers.enrichment import enrich_seed

    result = enrich_seed(
        "The European Union passed the AI Act regulating artificial intelligence systems.",
        "Predict how tech companies will respond to EU AI regulation over 60 days",
    )

    assert result is not None
    assert len(result.summary) > 100
    assert isinstance(result.citations, list)
