"""Coverage for saas.jobs.ai /generate-goal endpoint."""
import sys
from unittest.mock import MagicMock


async def test_generate_goal_no_api_key(client, auth_headers, monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "")
    resp = await client.post(
        "/api/ai/generate-goal",
        json={"seed_text": "x" * 100, "category": "market-reaction"},
        headers=auth_headers,
    )
    assert resp.status_code == 503


async def test_generate_goal_unauth(client):
    resp = await client.post(
        "/api/ai/generate-goal",
        json={"seed_text": "x", "category": "market-reaction"},
    )
    assert resp.status_code == 401


async def test_generate_goal_success(client, auth_headers, monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "test-key")

    openai_mod = MagicMock()
    cls = MagicMock()
    openai_mod.OpenAI = cls

    message = MagicMock()
    message.content = '"What will AAPL do over 30 days?"'
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    cls.return_value.chat.completions.create.return_value = response

    monkeypatch.setitem(sys.modules, "openai", openai_mod)

    resp = await client.post(
        "/api/ai/generate-goal",
        json={"seed_text": "y" * 100, "category": "market-reaction"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    # quote-stripped
    assert "AAPL" in resp.json()["goal"]


async def test_generate_goal_api_error(client, auth_headers, monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "test-key")

    openai_mod = MagicMock()
    cls = MagicMock()
    openai_mod.OpenAI = cls
    cls.return_value.chat.completions.create.side_effect = RuntimeError("xAI down")
    monkeypatch.setitem(sys.modules, "openai", openai_mod)

    resp = await client.post(
        "/api/ai/generate-goal",
        json={"seed_text": "x" * 100, "category": "unknown-category"},
        headers=auth_headers,
    )
    assert resp.status_code == 500
