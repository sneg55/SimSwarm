import os
import pytest
from saas.config import Settings


def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:8000/v1")
    monkeypatch.setenv("LLM_MODEL_NAME", "test-model")
    monkeypatch.setenv("ZEP_API_KEY", "test-zep")

    settings = Settings()
    assert settings.DATABASE_URL == "postgresql+asyncpg://test:test@localhost/test"
    assert settings.SECRET_KEY == "test-secret"
    assert settings.LLM_API_KEY == "test-key"


def test_settings_has_defaults():
    """LLM_BASE_URL and LLM_MODEL_NAME have sensible defaults."""
    settings = Settings(
        DATABASE_URL="postgresql+asyncpg://x:x@localhost/x",
        SECRET_KEY="x",
        LLM_API_KEY="x",
        ZEP_API_KEY="x",
    )
    assert settings.LLM_BASE_URL == "http://localhost:8000/v1"
    assert settings.LLM_MODEL_NAME == "Qwen2.5-32B-Instruct-AWQ"


def test_test_database_url_override():
    """In test mode, DATABASE_URL can use sqlite."""
    settings = Settings(
        DATABASE_URL="sqlite+aiosqlite:///test.db",
        SECRET_KEY="x",
        LLM_API_KEY="x",
        ZEP_API_KEY="x",
    )
    assert "sqlite" in settings.DATABASE_URL
