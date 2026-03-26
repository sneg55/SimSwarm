import pytest
from unittest.mock import patch, MagicMock


async def test_balance_zero_new_user(client):
    response = await client.get("/api/billing/balance", params={"user_id": "new-user-999"})
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == "new-user-999"
    assert data["balance"] == 0


async def test_purchase_creates_checkout(client):
    mock_session = MagicMock()
    mock_session.id = "cs_test_abc"
    mock_session.url = "https://checkout.stripe.com/pay/cs_test_abc"

    with patch("stripe.checkout.Session.create", return_value=mock_session):
        response = await client.post(
            "/api/billing/purchase",
            json={"user_id": "user-123", "pack_id": "starter"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "cs_test_abc"
    assert "checkout_url" in data


async def test_purchase_invalid_pack(client):
    response = await client.post(
        "/api/billing/purchase",
        json={"user_id": "user-123", "pack_id": "nonexistent"},
    )
    assert response.status_code == 400


async def test_history_empty(client):
    response = await client.get("/api/billing/history", params={"user_id": "no-history-user"})
    assert response.status_code == 200
    data = response.json()
    assert data == []
