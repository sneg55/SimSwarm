"""
Stripe billing purchase flow tests.

Covers:
- Creating checkout sessions for all packs (starter, pro, heavy)
- Stripe metadata verification
- Invalid pack handling
- Auth guards
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from saas.billing.credit_packs import CREDIT_PACKS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_stripe_session_mock(
    session_id: str = "cs_test_abc123",
    checkout_url: str = "https://checkout.stripe.com/pay/cs_test_abc123",
) -> MagicMock:
    """Return a minimal mock of a Stripe checkout Session object."""
    mock = MagicMock()
    mock.id = session_id
    mock.url = checkout_url
    return mock


# ---------------------------------------------------------------------------
# Purchase flow tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_purchase_starter_returns_checkout_url(client, auth_headers):
    """POST /billing/purchase with pack_id=starter returns a checkout_url."""
    mock_session = _make_stripe_session_mock("cs_test_starter", "https://checkout.stripe.com/pay/cs_test_starter")

    with patch("stripe.checkout.Session.create", return_value=mock_session):
        response = await client.post(
            "/api/billing/purchase",
            headers=auth_headers,
            json={"pack_id": "starter"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "cs_test_starter"
    assert data["checkout_url"] == "https://checkout.stripe.com/pay/cs_test_starter"


@pytest.mark.asyncio
async def test_purchase_pro_returns_checkout_url(client, auth_headers):
    """POST /billing/purchase with pack_id=pro returns a checkout_url."""
    mock_session = _make_stripe_session_mock("cs_test_pro", "https://checkout.stripe.com/pay/cs_test_pro")

    with patch("stripe.checkout.Session.create", return_value=mock_session):
        response = await client.post(
            "/api/billing/purchase",
            headers=auth_headers,
            json={"pack_id": "pro"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "cs_test_pro"
    assert "checkout_url" in data


@pytest.mark.asyncio
async def test_purchase_heavy_returns_checkout_url(client, auth_headers):
    """POST /billing/purchase with pack_id=heavy returns a checkout_url."""
    mock_session = _make_stripe_session_mock("cs_test_heavy", "https://checkout.stripe.com/pay/cs_test_heavy")

    with patch("stripe.checkout.Session.create", return_value=mock_session):
        response = await client.post(
            "/api/billing/purchase",
            headers=auth_headers,
            json={"pack_id": "heavy"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "cs_test_heavy"
    assert "checkout_url" in data


@pytest.mark.asyncio
async def test_purchase_stripe_receives_correct_metadata(client, auth_headers):
    """Verify Stripe.create is called with correct metadata for the starter pack."""
    pack = CREDIT_PACKS["starter"]
    mock_session = _make_stripe_session_mock()
    user_id = auth_headers["_user_id"]

    with patch("stripe.checkout.Session.create", return_value=mock_session) as mock_create:
        await client.post(
            "/api/billing/purchase",
            headers=auth_headers,
            json={"pack_id": "starter"},
        )

    mock_create.assert_called_once()
    kwargs = mock_create.call_args.kwargs
    metadata = kwargs["metadata"]
    assert metadata["user_id"] == user_id
    assert metadata["pack_id"] == "starter"
    assert metadata["credits"] == str(pack.credits)

    line_items = kwargs["line_items"]
    assert len(line_items) == 1
    assert line_items[0]["price_data"]["unit_amount"] == pack.price_cents
    assert kwargs["mode"] == "payment"


@pytest.mark.asyncio
async def test_purchase_invalid_pack_returns_400(client, auth_headers):
    """Unknown pack_id returns HTTP 400."""
    response = await client.post(
        "/api/billing/purchase",
        headers=auth_headers,
        json={"pack_id": "invalid_pack_xyz"},
    )
    assert response.status_code == 400
    assert "invalid_pack_xyz" in response.json()["detail"]


@pytest.mark.asyncio
async def test_purchase_requires_auth(client):
    """POST /billing/purchase without a JWT token returns 401."""
    response = await client.post(
        "/api/billing/purchase",
        json={"pack_id": "starter"},
    )
    assert response.status_code == 401
