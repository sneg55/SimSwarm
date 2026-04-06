"""
End-to-end Stripe billing integration tests.

Covers:
- Full purchase -> webhook -> balance verification flow
- Heavy pack full flow
- Multiple purchases accumulating credits
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


def _make_checkout_completed_event(
    user_id: str,
    credits: int,
    pack_id: str = "starter",
    session_id: str = "cs_test_abc123",
    payment_intent: str | None = None,
) -> MagicMock:
    """Return a mock of a checkout.session.completed Stripe Event."""
    event = MagicMock()
    event.type = "checkout.session.completed"
    event.data.object.id = session_id
    event.data.object.payment_intent = payment_intent
    event.data.object.metadata = {
        "user_id": user_id,
        "pack_id": pack_id,
        "credits": str(credits),
    }
    return event


# ---------------------------------------------------------------------------
# End-to-end integration tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_purchase_to_credit_flow(client, auth_headers):
    """
    Full flow:
    1. Create a checkout session (mocked Stripe API).
    2. Simulate the checkout.session.completed webhook.
    3. Assert balance increased by the correct pack amount.
    """
    user_id = auth_headers["_user_id"]
    pack_id = "pro"
    pack = CREDIT_PACKS[pack_id]
    session_id = "cs_test_full_flow_001"

    # Step 1 — initiate purchase
    mock_session = _make_stripe_session_mock(
        session_id=session_id,
        checkout_url=f"https://checkout.stripe.com/pay/{session_id}",
    )
    with patch("stripe.checkout.Session.create", return_value=mock_session):
        purchase_resp = await client.post(
            "/api/billing/purchase",
            headers=auth_headers,
            json={"pack_id": pack_id},
        )
    assert purchase_resp.status_code == 200
    assert purchase_resp.json()["session_id"] == session_id

    # Step 2 — simulate Stripe webhook
    event_mock = _make_checkout_completed_event(
        user_id=user_id,
        credits=pack.credits,
        pack_id=pack_id,
        session_id=session_id,
    )
    with patch("saas.billing.stripe_service.stripe.Webhook.construct_event", return_value=event_mock):
        webhook_resp = await client.post(
            "/api/billing/webhook",
            content=b'{"type": "checkout.session.completed"}',
            headers={"stripe-signature": "t=1,v1=fake"},
        )
    assert webhook_resp.status_code == 200

    # Step 3 — verify balance
    balance_resp = await client.get("/api/billing/balance", headers=auth_headers)
    assert balance_resp.status_code == 200
    assert balance_resp.json()["balance"] == pack.credits  # 500 for pro

    # Step 4 — verify history has exactly one entry from the webhook
    history_resp = await client.get("/api/billing/history", headers=auth_headers)
    entries = history_resp.json()
    assert len(entries) == 1
    assert entries[0]["amount"] == pack.credits
    assert session_id in entries[0]["description"]
    assert entries[0]["stripe_session_id"] == session_id


@pytest.mark.asyncio
async def test_full_purchase_heavy_pack_flow(client, auth_headers):
    """Full flow for the heavy pack — verifies 2000 credits are applied."""
    user_id = auth_headers["_user_id"]
    pack = CREDIT_PACKS["heavy"]
    session_id = "cs_test_heavy_flow"

    mock_session = _make_stripe_session_mock(session_id=session_id)
    with patch("stripe.checkout.Session.create", return_value=mock_session):
        resp = await client.post(
            "/api/billing/purchase",
            headers=auth_headers,
            json={"pack_id": "heavy"},
        )
    assert resp.status_code == 200

    event_mock = _make_checkout_completed_event(
        user_id=user_id,
        credits=pack.credits,
        pack_id="heavy",
        session_id=session_id,
    )
    with patch("saas.billing.stripe_service.stripe.Webhook.construct_event", return_value=event_mock):
        await client.post(
            "/api/billing/webhook",
            content=b'{}',
            headers={"stripe-signature": "t=1,v1=fake"},
        )

    balance_resp = await client.get("/api/billing/balance", headers=auth_headers)
    assert balance_resp.json()["balance"] == 2000


@pytest.mark.asyncio
async def test_multiple_purchases_accumulate_credits(client, auth_headers):
    """Two separate webhook events for the same user accumulate credits."""
    user_id = auth_headers["_user_id"]
    pack = CREDIT_PACKS["starter"]  # 100 credits

    for i in range(2):
        event_mock = _make_checkout_completed_event(
            user_id=user_id,
            credits=pack.credits,
            pack_id="starter",
            session_id=f"cs_test_multi_{i}",
        )
        with patch("saas.billing.stripe_service.stripe.Webhook.construct_event", return_value=event_mock):
            await client.post(
                "/api/billing/webhook",
                content=b'{}',
                headers={"stripe-signature": "t=1,v1=fake"},
            )

    balance_resp = await client.get("/api/billing/balance", headers=auth_headers)
    assert balance_resp.json()["balance"] == pack.credits * 2  # 200
