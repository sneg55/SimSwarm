"""
Stripe billing webhook processing tests.

Covers:
- Valid checkout.session.completed webhook crediting the account
- Invalid signature rejection
- Non-checkout event handling
- Missing metadata graceful handling
- Unknown pack_id handling
"""

from __future__ import annotations

import time
import hashlib
import hmac
import pytest
from unittest.mock import MagicMock, patch

from saas.billing.credit_packs import CREDIT_PACKS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _build_stripe_signature(payload: bytes, secret: str) -> str:
    """
    Build a valid-looking Stripe webhook signature header.
    Format: t=<timestamp>,v1=<hmac_sha256>
    """
    timestamp = int(time.time())
    signed_payload = f"{timestamp}.".encode() + payload
    sig = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={sig}"


# ---------------------------------------------------------------------------
# Webhook tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_webhook_completes_checkout_credits_account(client, auth_headers):
    """
    Simulate a checkout.session.completed webhook with a mocked valid signature.
    Verify that credits are added to the user's ledger.
    """
    user_id = auth_headers["_user_id"]
    pack = CREDIT_PACKS["starter"]
    event_mock = _make_checkout_completed_event(
        user_id=user_id,
        credits=pack.credits,
        pack_id="starter",
        session_id="cs_test_wh_001",
    )

    with patch("saas.billing.stripe_service.stripe.Webhook.construct_event", return_value=event_mock):
        response = await client.post(
            "/api/billing/webhook",
            content=b'{"type": "checkout.session.completed"}',
            headers={"stripe-signature": "t=1,v1=fake"},
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    # Verify balance was credited
    balance_resp = await client.get("/api/billing/balance", headers=auth_headers)
    assert balance_resp.status_code == 200
    assert balance_resp.json()["balance"] == pack.credits


@pytest.mark.asyncio
async def test_webhook_invalid_signature_returns_400(client):
    """A webhook with a bad signature should return HTTP 400."""
    import stripe as stripe_module

    with patch(
        "saas.billing.stripe_service.stripe.Webhook.construct_event",
        side_effect=stripe_module.SignatureVerificationError("bad sig", "sig_header"),
    ):
        response = await client.post(
            "/api/billing/webhook",
            content=b'{"type": "checkout.session.completed"}',
            headers={"stripe-signature": "t=1,v1=badsignature"},
        )

    assert response.status_code == 400
    assert "signature" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_webhook_ignores_non_checkout_events(client, auth_headers):
    """
    Events other than checkout.session.completed should be accepted (200)
    but no credits should be added.
    """
    other_event = MagicMock()
    other_event.type = "payment_intent.succeeded"

    with patch("saas.billing.stripe_service.stripe.Webhook.construct_event", return_value=other_event):
        response = await client.post(
            "/api/billing/webhook",
            content=b'{"type": "payment_intent.succeeded"}',
            headers={"stripe-signature": "t=1,v1=fake"},
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    # Balance must remain zero — no credits added
    balance_resp = await client.get("/api/billing/balance", headers=auth_headers)
    assert balance_resp.json()["balance"] == 0


@pytest.mark.asyncio
async def test_webhook_missing_user_id_does_not_crash(client):
    """Webhook with missing user_id metadata should still return 200 gracefully."""
    event_mock = MagicMock()
    event_mock.type = "checkout.session.completed"
    event_mock.data.object.id = "cs_test_no_user"
    event_mock.data.object.metadata = {}  # no user_id or credits

    with patch("saas.billing.stripe_service.stripe.Webhook.construct_event", return_value=event_mock):
        response = await client.post(
            "/api/billing/webhook",
            content=b'{"type": "checkout.session.completed"}',
            headers={"stripe-signature": "t=1,v1=fake"},
        )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_webhook_unknown_pack_does_not_credit_account(client, auth_headers):
    """A completed checkout with an unknown pack_id should not alter the balance."""
    user_id = auth_headers["_user_id"]
    event_mock = _make_checkout_completed_event(
        user_id=user_id,
        credits=100,
        pack_id="nonexistent_pack",
        session_id="cs_test_unknown_pack",
    )

    with patch("saas.billing.stripe_service.stripe.Webhook.construct_event", return_value=event_mock):
        await client.post(
            "/api/billing/webhook",
            content=b'{}',
            headers={"stripe-signature": "t=1,v1=fake"},
        )

    balance_resp = await client.get("/api/billing/balance", headers=auth_headers)
    assert balance_resp.json()["balance"] == 0
