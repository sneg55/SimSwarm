import pytest
from unittest.mock import patch, MagicMock


async def test_missing_routing_does_not_charge_credits(client, auth_headers, funded_user):
    """If model routing is not configured, credits must not be deducted."""
    resp = await client.post(
        "/api/jobs",
        headers=auth_headers,
        json={"seed_text": "Test seed text.", "goal": "Test", "tier": "small"},
    )
    assert resp.status_code == 500
    assert "routing" in resp.json()["detail"].lower()

    balance_resp = await client.get("/api/billing/balance", headers=auth_headers)
    assert balance_resp.json()["balance"] == 10000


async def test_dispatch_failure_does_not_charge_credits(client, auth_headers, funded_user, seeded_routing):
    """If Celery dispatch fails, credits must not be deducted."""
    with patch("saas.api.jobs.run_simulation_task.delay", side_effect=Exception("broker down")):
        resp = await client.post(
            "/api/jobs",
            headers=auth_headers,
            json={"seed_text": "Test seed text.", "goal": "Test", "tier": "small"},
        )
    assert resp.status_code == 500

    balance_resp = await client.get("/api/billing/balance", headers=auth_headers)
    assert balance_resp.json()["balance"] == 10000
