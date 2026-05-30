"""Additional enrichment edge cases."""
import sys
from unittest.mock import MagicMock


def test_enrichment_import_error(monkeypatch):
    """Simulate openai not installed -> ImportError path returns None."""
    monkeypatch.setenv("XAI_API_KEY", "test-key")
    # Force ImportError by setting sys.modules['openai'] to a module without OpenAI
    broken_mod = MagicMock(spec=[])  # has no OpenAI attr
    monkeypatch.setitem(sys.modules, "openai", broken_mod)

    from saas.jobs.enrichment import enrich_seed
    # Accessing .OpenAI will raise AttributeError which is caught by generic Exception
    result = enrich_seed("seed", "goal")
    assert result is None


def test_enrichment_result_has_no_citations(monkeypatch):
    """Response items without annotations -> empty citations list but valid summary."""
    monkeypatch.setenv("XAI_API_KEY", "test-key")

    openai_mod = MagicMock()
    cls = MagicMock()
    openai_mod.OpenAI = cls
    monkeypatch.setitem(sys.modules, "openai", openai_mod)

    # Response with no content/annotations at all
    response = MagicMock()
    response.output_text = "Some summary"
    response.output = []

    cls.return_value.responses.create.return_value = response

    from saas.jobs.enrichment import enrich_seed
    result = enrich_seed("seed", "goal")
    assert result is not None
    assert result.summary == "Some summary"
    assert result.citations == []
