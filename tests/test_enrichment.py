"""Tests for seed enrichment via xAI search."""
import sys
from unittest.mock import MagicMock


def _make_openai_mock():
    """Return a (module_mock, OpenAI_class_mock) pair injected into sys.modules."""
    openai_mod = MagicMock()
    openai_cls = MagicMock()
    openai_mod.OpenAI = openai_cls
    return openai_mod, openai_cls


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


def test_enrich_seed_returns_result_on_success(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "test-key")
    openai_mod, openai_cls = _make_openai_mock()
    mock_response = MagicMock()
    mock_response.output_text = "Research summary about the topic."
    mock_response.citations = [
        MagicMock(url="https://example.com/1", title="Source 1"),
        MagicMock(url="https://example.com/2", title="Source 2"),
    ]
    openai_cls.return_value.responses.create.return_value = mock_response
    monkeypatch.setitem(sys.modules, "openai", openai_mod)

    from saas.workers.enrichment import enrich_seed
    result = enrich_seed("seed text", "research goal")

    assert result is not None
    assert result.summary == "Research summary about the topic."
    assert len(result.citations) == 2
    assert result.citations[0]["url"] == "https://example.com/1"
